# -*- coding: utf-8 -*-
"""แอปกรอกข้อมูล SSCC ครั้งเดียว — Flask local (127.0.0.1 เท่านั้น, ไม่เปิดสู่ LAN)"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, jsonify, redirect, render_template, request, url_for

import checks
import db
import excel_export
import runlock

APP_DIR = Path(__file__).parent
CONFIG = json.loads((APP_DIR / "config.json").read_text(encoding="utf-8"))
CUSTOM_PATH = APP_DIR / "schema" / "custom_fields.json"
DEFAULTS_PATH = APP_DIR / "schema" / "custom_fields_defaults.json"
CF_TYPES = {"text", "number", "select", "checkbox-group", "date", "time", "textarea"}

app = Flask(__name__)


def read_custom_raw():
    if CUSTOM_PATH.exists():
        return json.loads(CUSTOM_PATH.read_text(encoding="utf-8"))
    return {"fields": []}


def merge_default_custom_fields():
    """เติมฟิลด์ รพ. ตั้งต้นที่มากับเวอร์ชันใหม่ (schema/custom_fields_defaults.json) เข้า custom_fields.json
    — update.bat ไม่แตะ custom_fields.json (กันทับของที่ รพ. แก้เอง) ฟิลด์ใหม่จึงต้องเติมตอนเปิดโปรแกรม
    กติกา: เติมเฉพาะ key ที่ไม่เคยเห็น; ฟิลด์ที่ รพ. แก้/ปิด/ลบไปแล้วไม่ถูกทับและไม่โผล่กลับมา"""
    if not DEFAULTS_PATH.exists():
        return
    try:
        defaults = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8")).get("fields", [])
    except Exception:
        return
    raw = read_custom_raw()
    fields = raw.get("fields", [])
    have = {f.get("key") for f in fields}
    seen = set(raw.get("_defaults_seen") or [])
    changed = False
    for f in defaults:
        k = f.get("key")
        if not k:
            continue
        if k not in have and k not in seen:
            fields.append(dict(f))
            have.add(k)
            changed = True
        if k not in seen:
            seen.add(k)
            changed = True
    if changed:
        raw["fields"] = fields
        raw["_defaults_seen"] = sorted(seen)
        CUSTOM_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


_FREQ_CACHE = {"at": None, "data": {}}
FREQ_MIN_OPTIONS = 12   # select ที่ตัวเลือกยาวกว่านี้ จะมีกลุ่ม "ใช้บ่อย" ขึ้นก่อน (จากสถิติเคสจริงในเครื่อง)
FREQ_TOP_N = 8


def frequent_options():
    """นับค่าที่ รพ. นี้ใช้จริงต่อฟิลด์ select (จากเคสทั้งหมดในฐาน) — คำนวณใหม่ทุก 30 นาที
    ใช้ยกตัวเลือกที่เจอบ่อยขึ้นบนสุด โดยไม่ตัดตัวเลือกอื่นออก (เช่น สิทธิการรักษา 64 ตัว แต่ชุมแพใช้จริง ~8)"""
    now = datetime.now()
    if _FREQ_CACHE["at"] and (now - _FREQ_CACHE["at"]).total_seconds() < 1800:
        return _FREQ_CACHE["data"]
    counts = {}
    try:
        for c in db.all_cases_full():
            for k, v in c["data"].items():
                if isinstance(v, str) and v:
                    counts.setdefault(k, {}).setdefault(v, 0)
                    counts[k][v] += 1
    except Exception:
        counts = {}
    _FREQ_CACHE.update(at=now, data=counts)
    return counts


def load_schema():
    schema = json.loads((APP_DIR / "schema" / "sscc_fields.json").read_text(encoding="utf-8"))
    freq = frequent_options()
    for f in schema["fields"]:
        opts = f.get("options") or []
        if f["type"] == "select" and len(opts) > FREQ_MIN_OPTIONS and not f.get("special"):
            used = freq.get(field_key(f)) or {}
            valid = {o["v"] for o in opts}
            top = [v for v, _ in sorted(used.items(), key=lambda kv: -kv[1]) if v in valid][:FREQ_TOP_N]
            if len(top) >= 3:
                f["frequent"] = top
    custom = []
    for f in read_custom_raw().get("fields", []):
        if not f.get("enabled", True):
            continue
        f = dict(f)
        f.setdefault("sscc", None)
        f["section"] = "CF"
        f["section_title"] = "ข้อมูลเพิ่มเติมของ รพ. (ไม่ส่งเข้า SSCC)"
        custom.append(f)
    return schema["fields"] + custom


def field_key(f):
    return f.get("sscc") or f["key"]


def show_if_map(fields):
    return {field_key(f): f["show_if"] for f in fields if f.get("show_if")}


def spawn_fill(case_ids, base_url):
    """เปิดโปรเซสกรอกเว็บ SSCC + เขียนล็อกทันที (กันกดส่งซ้อนช่วงโปรเซสยังไม่ทันตั้งตัว)"""
    proc = subprocess.Popen(
        [sys.executable, str(APP_DIR / "fill_sscc.py"), "--cases", ",".join(map(str, case_ids)),
         "--base-url", base_url],
        cwd=str(APP_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )
    runlock.write({"pid": proc.pid, "cases": list(case_ids), "current": case_ids[0]})


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    status_f = request.args.get("status", "").strip()
    cases = db.list_cases(q, status_f)
    counts = db.status_counts(q)
    counts["all"] = sum(counts.values())
    return render_template("list.html", cases=cases, q=q, status_f=status_f,
                           counts=counts, config=CONFIG,
                           master_dir=str(excel_export.master_dir()),
                           excel=excel_export.status())


@app.route("/case/new")
def case_new():
    fields = load_schema()
    return render_template("form.html", fields=fields, case=None, values={},
                           config=CONFIG, field_key=field_key, show_if_map=show_if_map(fields))


@app.route("/case/<int:case_id>")
def case_edit(case_id):
    case = db.get_case(case_id)
    if not case:
        return redirect(url_for("index"))
    fields = load_schema()
    dq_init = {"warnings": checks.unacked(case["data"]), "blocking": checks.blocking(case["data"]),
               "derived": checks.run(case["data"])["derived"],
               "acked": bool((case["data"].get("_dq") or {}).get("ack"))}
    return render_template("form.html", fields=fields, case=case, values=case["data"],
                           config=CONFIG, field_key=field_key, show_if_map=show_if_map(fields),
                           dq_init=dq_init)


@app.route("/case/save", methods=["POST"])
def case_save():
    payload = request.get_json(force=True)
    case_id = payload.get("case_id") or None
    data = payload.get("data") or {}
    if not (data.get("x_a2") or "").strip():
        return jsonify(ok=False, error="ต้องกรอก HN ก่อนบันทึก"), 400
    if case_id:
        # เก็บ key ที่ฟอร์มไม่ได้ render (เช่น legacy จาก import / custom ที่ปิดไว้ / _dq) ไม่ให้หาย
        old = db.get_case(case_id)
        if old:
            known = {field_key(f) for f in load_schema()}
            preserved = {k: v for k, v in old["data"].items() if k not in known}
            data = {**preserved, **data}
    # ตรวจ timeline/ความสอดคล้อง — บันทึกได้เสมอ (ไม่ทำข้อมูลหาย) แต่เก็บธงไว้กับเคส
    result = checks.run(data)
    codes = [f["code"] for f in result["flags"]]
    dq = dict(data.get("_dq") or {})
    dq["flags"] = codes
    dq["checked_at"] = datetime.now().isoformat(timespec="seconds")
    ack_in = payload.get("ack")
    if ack_in and codes:
        # รับทราบธงชุดปัจจุบันพร้อมเหตุผล — ถ้าข้อมูลเปลี่ยนจนธงชุดใหม่โผล่ ต้องรับทราบใหม่
        dq["ack"] = {"codes": codes, "reason": str(ack_in.get("reason") or "").strip(),
                     "at": datetime.now().isoformat(timespec="seconds")}
    if not codes:
        dq.pop("ack", None)   # ข้อมูลถูกแก้จนไม่มีธงแล้ว — เหตุผลเก่าไม่จำเป็น
    data["_dq"] = dq
    new_id = db.save_case(case_id, data)
    # Excel เขียนเบื้องหลัง — ไฟล์ใหญ่ขึ้นตามจำนวนเคส (4 พันเคส ~15 วิ) ห้ามให้ปุ่มบันทึกรอ
    excel_export.schedule_export()
    return jsonify(ok=True, case_id=new_id, warnings=checks.unacked(data), blocking=checks.blocking(data),
                   derived=result["derived"], acked=bool(dq.get("ack")))


@app.route("/api/check", methods=["POST"])
def api_check():
    """ตรวจสดระหว่างกรอก (ไม่บันทึก) — ให้ฟอร์มโชว์นาทีที่คำนวณได้ + ธงทันที"""
    data = (request.get_json(force=True) or {}).get("data") or {}
    return jsonify(checks.run(data))


@app.route("/dq")
def dq_page():
    """เคสที่มีธงคุณภาพข้อมูล — ไล่แก้ก่อนส่ง/ก่อนสรุปตัวชี้วัด"""
    rows = []
    counts = {}
    for c in db.all_cases_full():
        d = c["data"]
        res = checks.run(d)
        if not res["flags"]:
            continue
        ack = (d.get("_dq") or {}).get("ack") or {}
        acked = set(ack.get("codes") or [])
        for f in res["flags"]:
            counts[f["code"]] = counts.get(f["code"], 0) + 1
        rows.append({"id": c["id"], "hn": c["hn"], "status": c["status"],
                     "door": d.get("x_b3_1_date") or d.get("x_b3_2_date") or "",
                     "flags": res["flags"], "derived": res["derived"],
                     "unacked": [f for f in res["flags"] if f["code"] not in acked],
                     "ack_reason": ack.get("reason") or ""})
    rows.sort(key=lambda r: (r["door"] or ""), reverse=True)
    return render_template("dq.html", rows=rows, counts=counts, config=CONFIG,
                           total=len(rows), n_unacked=sum(1 for r in rows if r["unacked"]))


@app.route("/case/<int:case_id>/submit", methods=["POST"])
def case_submit(case_id):
    case = db.get_case(case_id)
    if not case:
        return jsonify(ok=False, error="ไม่พบเคส"), 404
    if case["status"] == "imported":
        return jsonify(ok=False, error="เคสนำเข้า = ข้อมูลมาจากเว็บอยู่แล้ว — ถ้าจะแก้ ให้แก้บนเว็บโดยตรง"), 400
    if case["status"] == "submitted" and not case.get("sscc_patient_id"):
        return jsonify(ok=False, error="เคสนี้ส่งแล้วแต่ไม่มีเลขที่ผู้ป่วยบันทึกไว้ — ตรวจ/แก้บนเว็บโดยตรง"), 400
    if runlock.read():
        return jsonify(ok=False, error="มีการส่งเข้า SSCC ทำงานค้างอยู่ — ทำเคสในหน้าต่าง Edge ให้เสร็จก่อน"), 409
    pending = checks.blocking(case["data"])
    if pending:
        return jsonify(ok=False, error="มีข้อสงสัยเรื่อง timeline ที่ยังไม่ได้รับทราบ — แก้ข้อมูล หรือกดรับทราบพร้อมเหตุผลก่อนส่ง",
                       warnings=pending), 400
    base_url = request.get_json(force=True).get("base_url") or CONFIG["sscc_base_url"]
    db.append_log(case_id, f"เริ่มส่งเข้า SSCC ({base_url})")
    spawn_fill([case_id], base_url)
    return jsonify(ok=True)


@app.route("/queue/submit", methods=["POST"])
def queue_submit():
    payload = request.get_json(force=True)
    try:
        ids = [int(i) for i in payload.get("case_ids", [])]
    except (TypeError, ValueError):
        return jsonify(ok=False, error="รายการเคสไม่ถูกต้อง"), 400
    if not ids:
        return jsonify(ok=False, error="ยังไม่ได้เลือกเคส"), 400
    if runlock.read():
        return jsonify(ok=False, error="มีการส่งเข้า SSCC ทำงานค้างอยู่ — ทำเคสในหน้าต่าง Edge ให้เสร็จก่อน"), 409
    bad = [i for i in ids if not db.get_case(i) or db.get_case(i)["status"] != "draft"]
    if bad:
        return jsonify(ok=False, error=f"เคสต่อไปนี้ไม่ใช่สถานะร่าง หรือไม่พบ: {bad}"), 400
    bad_dq = [i for i in ids if checks.blocking(db.get_case(i)["data"])]
    if bad_dq:
        return jsonify(ok=False, error="เคสต่อไปนี้มีข้อสงสัยเรื่องเวลาที่ยังไม่รับทราบ — เปิดเคสแล้วแก้ หรือกดรับทราบพร้อมเหตุผลก่อน: "
                       + ", ".join(f"#{i}" for i in bad_dq)), 400
    base_url = payload.get("base_url") or CONFIG["sscc_base_url"]
    for i in ids:
        db.append_log(i, f"เข้าคิวส่ง SSCC (ทั้งหมด {len(ids)} เคส)")
    spawn_fill(ids, base_url)
    return jsonify(ok=True, count=len(ids))


@app.route("/queue/status")
def queue_status():
    info = runlock.read()
    if not info:
        return jsonify(running=False)
    out = []
    for i in info.get("cases", []):
        c = db.get_case(i)
        if c:
            out.append({"id": c["id"], "hn": c["hn"], "status": c["status"],
                        "sscc_patient_id": c.get("sscc_patient_id")})
    return jsonify(running=True, current=info.get("current"), cases=out)


@app.route("/case/<int:case_id>/status")
def case_status(case_id):
    case = db.get_case(case_id)
    if not case:
        return jsonify(ok=False), 404
    return jsonify(ok=True, status=case["status"],
                   sscc_patient_id=case.get("sscc_patient_id"),
                   submitted_at=case.get("submitted_at"), log=case.get("fill_log") or "")


@app.route("/export")
def export_now():
    try:
        path = excel_export.export_master()
    except PermissionError:
        return jsonify(ok=False, error="ไฟล์ Excel master เปิดค้างอยู่ — ปิดไฟล์แล้วกดใหม่")
    return jsonify(ok=True, path=path)


def save_config():
    (APP_DIR / "config.json").write_text(
        json.dumps(CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")


def choose_dir_dialog():
    """เปิดหน้าต่างเลือกโฟลเดอร์ของ Windows (รันใน subprocess กันปัญหา tkinter กับ thread)"""
    script = ("import tkinter as tk\n"
              "from tkinter import filedialog\n"
              "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
              "print(filedialog.askdirectory(title='เลือกโฟลเดอร์เก็บไฟล์ Excel'))")
    try:
        out = subprocess.run([sys.executable, "-X", "utf8", "-c", script],
                             capture_output=True, text=True, encoding="utf-8", timeout=300)
        return (out.stdout or "").strip()
    except Exception:
        return ""


@app.route("/settings/master_dir", methods=["POST"])
def set_master_dir():
    payload = request.get_json(force=True)
    if payload.get("action") == "reset":
        path = ""
    elif "path" in payload:
        path = str(payload.get("path") or "").strip()
    else:
        path = choose_dir_dialog()
        if not path:
            return jsonify(ok=False, error="ยกเลิกการเลือกโฟลเดอร์")
    if path:
        p = Path(path)
        if not p.is_dir():
            return jsonify(ok=False, error=f"ไม่พบโฟลเดอร์ {path}"), 400
        path = str(p)
    CONFIG["master_dir"] = path
    save_config()
    warn = ""
    low = path.lower()
    if path.startswith("\\\\") or "onedrive" in low or "google drive" in low or "dropbox" in low:
        warn = "⚠️ ที่เก็บนี้อยู่บนไดรฟ์แชร์/cloud — ไฟล์มีข้อมูลผู้ป่วย ระวังเรื่อง PDPA"
    try:
        excel_export.export_master()
    except PermissionError:
        warn = (warn + " • " if warn else "") + "ยังเขียนไฟล์ไม่ได้ (Excel เปิดค้างอยู่)"
    return jsonify(ok=True, path=str(excel_export.master_dir()), warn=warn)


@app.route("/settings/open_output", methods=["POST"])
def open_output():
    d = excel_export.master_dir()
    d.mkdir(parents=True, exist_ok=True)
    import os
    os.startfile(str(d))  # เปิด File Explorer (แอปรันบนเครื่องเดียวกับผู้ใช้เสมอ)
    return jsonify(ok=True)


@app.route("/settings/open_excel", methods=["POST"])
def open_excel():
    """เปิดไฟล์ master ใน Excel ให้เลย — ผู้ใช้ไม่ต้องคลำหาไฟล์เองในโฟลเดอร์"""
    p = excel_export.master_dir() / "SSCC_master.xlsx"
    if not p.exists():
        return jsonify(ok=False, error="ยังไม่มีไฟล์ Excel — กด '📄 สร้าง Excel ใหม่' ก่อน")
    import os
    os.startfile(str(p))
    return jsonify(ok=True)


@app.route("/fields")
def fields_page():
    return render_template("fields.html", fields=read_custom_raw().get("fields", []), config=CONFIG)


@app.route("/api/custom_fields", methods=["POST"])
def custom_fields_save():
    raw = read_custom_raw()
    incoming = (request.get_json(force=True) or {}).get("fields", [])
    # เลข running สำหรับ key ใหม่ — ไม่ใช้ซ้ำแม้ฟิลด์เก่าถูกลบ (กันข้อมูลเก่าในฐานปนกับฟิลด์ใหม่)
    next_id = int(raw.get("_next_id") or 1)
    for f in raw.get("fields", []):
        m = re.match(r"^cf_(\d+)$", f.get("key") or "")
        if m:
            next_id = max(next_id, int(m.group(1)) + 1)
    out = []
    for f in incoming:
        label = str(f.get("label") or "").strip()
        ftype = f.get("type")
        if not label:
            return jsonify(ok=False, error="มีหัวข้อที่ยังไม่ได้ตั้งชื่อ"), 400
        if ftype not in CF_TYPES:
            return jsonify(ok=False, error=f"รูปแบบการกรอกไม่ถูกต้อง: {ftype}"), 400
        g = {"key": str(f.get("key") or "").strip(), "label": label, "type": ftype,
             "enabled": f.get("enabled", True) is not False}
        if not g["key"]:
            g["key"] = f"cf_{next_id}"
            next_id += 1
        if ftype in ("select", "checkbox-group"):
            opts = [{"v": str(o.get("v", "")).strip(), "t": str(o.get("t", "")).strip()}
                    for o in (f.get("options") or [])]
            opts = [o for o in opts if o["t"]]
            if len(opts) < 2:
                return jsonify(ok=False, error=f"'{label}': ต้องมีตัวเลือกอย่างน้อย 2 ตัวเลือก"), 400
            g["options"] = opts
        # เงื่อนไขการแสดง (ตั้งได้จากไฟล์ schema เท่านั้น) — เก็บผ่านไม่ให้หายเวลาแก้จากหน้า UI
        cond = f.get("show_if")
        if isinstance(cond, dict) and all(isinstance(v, list) for v in cond.values()):
            g["show_if"] = cond
        if ftype == "number":
            for k in ("min", "max"):
                if f.get(k) not in (None, ""):
                    g[k] = f[k]
        if str(f.get("hint") or "").strip():
            g["hint"] = str(f["hint"]).strip()
        if f.get("required"):
            g["required"] = True
        out.append(g)
    keys = [g["key"] for g in out]
    if len(keys) != len(set(keys)):
        return jsonify(ok=False, error="มี key ซ้ำกัน — รีเฟรชหน้าแล้วลองใหม่"), 400
    raw["fields"] = out
    raw["_next_id"] = next_id
    CUSTOM_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    # คอลัมน์ใน Excel ต้องตามฟิลด์ทันที — ไม่ใช่รอจนมีคนบันทึกเคสถัดไป (บั๊กจริงที่ รพ. 2026-08-18)
    excel_export.schedule_export()
    return jsonify(ok=True, fields=out)


@app.route("/excel/status")
def excel_status():
    return jsonify(excel_export.status())


if __name__ == "__main__":
    merge_default_custom_fields()
    port = CONFIG.get("port", 8547)
    print(f"* เปิดใช้งานที่ http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
