# -*- coding: utf-8 -*-
"""แอปกรอกข้อมูล SSCC ครั้งเดียว — Flask local (127.0.0.1 เท่านั้น, ไม่เปิดสู่ LAN)"""
import json
import subprocess
import sys
from pathlib import Path

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, jsonify, redirect, render_template, request, url_for

import db
import excel_export

APP_DIR = Path(__file__).parent
CONFIG = json.loads((APP_DIR / "config.json").read_text(encoding="utf-8"))

app = Flask(__name__)


def load_schema():
    schema = json.loads((APP_DIR / "schema" / "sscc_fields.json").read_text(encoding="utf-8"))
    custom_path = APP_DIR / "schema" / "custom_fields.json"
    custom = []
    if custom_path.exists():
        raw = json.loads(custom_path.read_text(encoding="utf-8"))
        for f in raw.get("fields", []):
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


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    cases = db.list_cases(q)
    return render_template("list.html", cases=cases, q=q, config=CONFIG)


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
    return render_template("form.html", fields=fields, case=case, values=case["data"],
                           config=CONFIG, field_key=field_key, show_if_map=show_if_map(fields))


@app.route("/case/save", methods=["POST"])
def case_save():
    payload = request.get_json(force=True)
    case_id = payload.get("case_id") or None
    data = payload.get("data") or {}
    if not (data.get("x_a2") or "").strip():
        return jsonify(ok=False, error="ต้องกรอก HN ก่อนบันทึก"), 400
    if case_id:
        # เก็บ key ที่ฟอร์มไม่ได้ render (เช่น legacy จาก import / custom ที่ปิดไว้) ไม่ให้หาย
        old = db.get_case(case_id)
        if old:
            known = {field_key(f) for f in load_schema()}
            preserved = {k: v for k, v in old["data"].items() if k not in known}
            data = {**preserved, **data}
    new_id = db.save_case(case_id, data)
    try:
        excel_export.export_master()
    except PermissionError:
        return jsonify(ok=True, case_id=new_id,
                       warn="บันทึกแล้ว แต่เขียน Excel ไม่ได้ (ไฟล์ master เปิดค้างอยู่ — ปิดแล้วบันทึกอีกครั้ง)")
    return jsonify(ok=True, case_id=new_id)


@app.route("/case/<int:case_id>/submit", methods=["POST"])
def case_submit(case_id):
    case = db.get_case(case_id)
    if not case:
        return jsonify(ok=False, error="ไม่พบเคส"), 404
    if case["status"] == "submitted":
        return jsonify(ok=False, error="เคสนี้ส่งเข้า SSCC แล้ว"), 400
    base_url = request.get_json(force=True).get("base_url") or CONFIG["sscc_base_url"]
    db.append_log(case_id, f"เริ่มส่งเข้า SSCC ({base_url})")
    subprocess.Popen(
        [sys.executable, str(APP_DIR / "fill_sscc.py"), "--case", str(case_id), "--base-url", base_url],
        cwd=str(APP_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )
    return jsonify(ok=True)


@app.route("/case/<int:case_id>/status")
def case_status(case_id):
    case = db.get_case(case_id)
    if not case:
        return jsonify(ok=False), 404
    return jsonify(ok=True, status=case["status"],
                   sscc_patient_id=case.get("sscc_patient_id"), log=case.get("fill_log") or "")


@app.route("/export")
def export_now():
    path = excel_export.export_master()
    return jsonify(ok=True, path=path)


if __name__ == "__main__":
    port = CONFIG.get("port", 8547)
    print(f"* เปิดใช้งานที่ http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
