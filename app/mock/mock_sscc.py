# -*- coding: utf-8 -*-
"""Mock เว็บ SSCC สำหรับทดสอบใน sandbox — จำลองพฤติกรรมสำคัญของเว็บจริง:
- login.php (auto-login จำลอง session)
- stroke_formadd.php: มีเฉพาะ A1-A6 บันทึกแล้ว redirect ไป list
- stroke_formlist.php: ตารางเคส + ?psearch= + ลิงก์ formedit
- stroke_formedit.php: ฟอร์มเดียว 8 แท็บ (แท็บที่ไม่เปิด = display:none เหมือนจริง)
  วันที่/เวลาเป็น text input, x_c18_drug เป็น hidden, รพ.ส่งต่อโหลดตามจังหวัดผ่าน AJAX
- เก็บค่าที่ POST ลง mock_store.json ให้เทสต์ตรวจ
"""
import json
from pathlib import Path

from flask import Flask, redirect, request

HERE = Path(__file__).parent
STORE = HERE / "mock_store.json"
SCHEMA = json.loads((HERE.parent / "schema" / "sscc_fields.json").read_text(encoding="utf-8"))

SECTION_ORDER = ["A", "A7", "B", "C1", "C2", "D", "E", "F"]
TAB_TITLES = {"A": "A1-A6", "A7": "A7", "B": "B1-B19", "C1": "C2-C12",
              "C2": "C13-C21", "D": "D1-D3", "E": "E1-E2", "F": "F1"}

app = Flask(__name__)


def load_store():
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"next_id": 900001, "records": {}}


def save_store(s):
    STORE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def render_input(f, value=""):
    name = f["sscc"]
    if f["type"] == "checkbox-group":
        out = ""
        for o in f.get("options", []):
            chk = "checked" if isinstance(value, list) and o["v"] in value else ""
            out += f'<label><input type="checkbox" name="{name}" value="{o["v"]}" {chk}> {o["t"]}</label><br>'
        return out
    if f.get("special") == "drug_lookup":
        return f'<input type="hidden" name="{name}" id="{name}" value="{value}"><span id="lu_{name}">(lookup)</span>'
    if f["type"] == "select" and not f.get("special") == "cascade_hospital":
        opts = '<option value="">โปรดเลือก</option>'
        for o in f.get("options", []):
            sel = "selected" if value == o["v"] else ""
            opts += f'<option value="{o["v"]}" {sel}>{o["t"]}</option>'
        return f'<select name="{name}" id="{name}">{opts}</select>'
    if f.get("special") == "cascade_hospital":
        # เริ่มว่าง — โหลดผ่าน AJAX ตามจังหวัด (เหมือนเว็บจริง)
        return f'<select name="{name}" id="{name}" data-cascade><option value="">โปรดเลือก</option></select>'
    if f["type"] == "textarea":
        return f'<textarea name="{name}">{value}</textarea>'
    # วันที่/เวลา/ตัวเลข บนเว็บจริงเป็น text input ธรรมดา
    return f'<input type="text" name="{name}" value="{value}">'


CASCADE_JS = """
<script>
function loadHosp(sel, provinceName) {
  const prov = document.querySelector(`[name="${provinceName}"]`);
  if (!prov || !prov.value) return;
  fetch('hosp_options.php?province=' + prov.value).then(r => r.json()).then(list => {
    sel.innerHTML = '<option value="">โปรดเลือก</option>' +
      list.map(o => `<option value="${o.v}">${o.t}</option>`).join('');
  });
}
document.querySelectorAll('[data-cascade]').forEach(sel => {
  const provName = sel.name.replace('_hospcode', '_address');
  const prov = document.querySelector(`[name="${provName}"]`);
  if (prov) prov.addEventListener('change', () => loadHosp(sel, provName));
});
</script>
"""

TAB_JS = """
<style>.tab-pane { display: none; } .tab-pane.active { display: block; }
.nav-tabs a { margin-right: 10px; cursor: pointer; }</style>
<script>
document.querySelectorAll('.nav-tabs a').forEach((a, i) => {
  a.addEventListener('click', e => {
    e.preventDefault();
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-pane')[i].classList.add('active');
  });
});
</script>
"""


@app.route("/stroke/login.php")
def login():
    # จำลองว่า login แล้ว — เว็บจริงมีฟอร์ม user/pass แต่การทดสอบ flow ไม่ต้องมี
    return redirect("/stroke/stroke_formlist.php")


@app.route("/stroke/stroke_formlist.php")
def formlist():
    s = load_store()
    q = request.args.get("psearch", "")
    desc = request.args.get("ordertype") == "DESC"
    rows = ""
    for pid, rec in sorted(s["records"].items(), reverse=desc):
        hn = rec.get("x_a2", "")
        if q and q not in hn and q not in rec.get("x_fname", ""):
            continue
        rows += (f'<tr><td><a href="stroke_formedit.php?showdetail=&patient_id={pid}">แก้ไข</a></td>'
                 f'<td>{pid}</td><td>{hn}</td><td>{rec.get("x_fname", "")}</td></tr>')
    return (f'<html><body><div id="menu"><a href="stroke_formadd.php?showdetail=">เพิ่ม</a></div>'
            f'<table><tr><th></th><th>เลขที่ผู้ป่วย</th><th>A2: HN</th><th>ชื่อ</th></tr>{rows}</table>'
            f'</body></html>')


@app.route("/stroke/stroke_formadd.php", methods=["GET", "POST"])
def formadd():
    if request.method == "POST":
        s = load_store()
        pid = str(s["next_id"])
        s["next_id"] += 1
        rec = {}
        for f in SCHEMA["fields"]:
            if not f.get("on_add_page"):
                continue
            name = f["sscc"]
            rec[name] = request.form.get(name, "")
        s["records"][pid] = rec
        save_store(s)
        return redirect("/stroke/stroke_formlist.php")
    body = ""
    for f in SCHEMA["fields"]:
        if f.get("on_add_page"):
            body += f'<div><label>{f["label"]}</label>{render_input(f)}</div>'
    return (f'<html><body><div id="menu"></div><form method="post">{body}'
            f'<button type="submit">บันทึก</button></form>{CASCADE_JS}</body></html>')


@app.route("/stroke/stroke_formedit.php", methods=["GET", "POST"])
def formedit():
    s = load_store()
    pid = request.args.get("patient_id", "")
    if pid not in s["records"]:
        return "ไม่พบเคส", 404
    if request.method == "POST":
        rec = s["records"][pid]
        for f in SCHEMA["fields"]:
            name = f["sscc"]
            if f["type"] == "checkbox-group":
                v = request.form.getlist(name)
                if v:
                    rec[name] = v
            else:
                v = request.form.get(name)
                if v not in (None, ""):
                    rec[name] = v
        save_store(s)
        # เหมือนเว็บจริง: บันทึกหน้าแก้ไขสำเร็จ -> เด้งไปหน้า view
        return redirect(f"/stroke/stroke_formview.php?patient_id={pid}")

    rec = s["records"][pid]
    tabs, panes = "", ""
    for i, sec in enumerate(SECTION_ORDER):
        fields = [f for f in SCHEMA["fields"] if f["section"] == sec]
        inner = ""
        for f in fields:
            inner += f'<div><label>{f["label"]}</label>{render_input(f, rec.get(f["sscc"], ""))}</div>'
        active = "active" if i == 0 else ""
        tabs += f'<li><a>{TAB_TITLES[sec]}</a></li>'
        panes += f'<div class="tab-pane {active}" id="tab_stroke_form{i + 1}">{inner}</div>'
    return (f'<html><body><div id="menu"></div><ul class="nav-tabs">{tabs}</ul>'
            f'<form method="post" id="fstroke_formedit">{panes}'
            f'<button type="submit">บันทึก</button></form>{TAB_JS}{CASCADE_JS}</body></html>')


@app.route("/stroke/stroke_formview.php")
def formview():
    return '<html><body><div id="menu"></div><div>ปรับปรุงสำเร็จแล้ว</div></body></html>'


@app.route("/stroke/hosp_options.php")
def hosp_options():
    prov = request.args.get("province", "")
    if prov == "400000":  # ขอนแก่น — ใช้รายชื่อจริงจาก schema
        f = next(f for f in SCHEMA["fields"] if f["sscc"] == "x_a6_hospcode")
        return json.dumps(f["options"], ensure_ascii=False)
    return json.dumps([{"v": "99001", "t": "โรงพยาบาลทดสอบ 1"}, {"v": "99002", "t": "โรงพยาบาลทดสอบ 2"}],
                      ensure_ascii=False)


if __name__ == "__main__":
    if STORE.exists():
        STORE.unlink()
    app.run(host="127.0.0.1", port=8548, debug=False)
