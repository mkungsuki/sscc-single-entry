# -*- coding: utf-8 -*-
"""Mock nRefer สำหรับทดสอบ fill_nrefer.py (โหมดกรอกฟอร์ม) — เลียนแบบ DOM ของฟอร์ม 'เพิ่มข้อมูล' จริงที่สำรวจไว้ 2026-09-09:
- หน้าแรก: ตั้ง sessionStorage.tokenRefer = JWT ปลอม (hcode/uid) เหมือนหลัง login ThaID
- #/dmis/patient: ปุ่ม "Add new" → ฟอร์มที่มี input name="editRow.*", radio id="editRow.rtpa1", select, pk-datepicker
  (input.datepicker-input parse ค่าเมื่อ 'change' แบบเดียวกับเว็บ), pk-select (trigger/option/search), ปุ่ม "บันทึก"
- ปุ่มบันทึกยิง POST /api/beta/dmis/imc/save-patient (เหมือนเว็บ) → เก็บทุกค่าลง mock_nrefer_store.json
- /api/beta/dmis/imc/patient ตอบรายการที่บันทึกไว้ (ใช้หาเลข ref)
ใช้: python mock/mock_nrefer.py [port]   (ค่าเริ่มต้น 8590)
"""
import base64
import json
import sys
import time
from pathlib import Path

from flask import Flask, jsonify, request

HERE = Path(__file__).parent
STORE = HERE / "mock_nrefer_store.json"
HCODE = "10995"
UID = 5286

app = Flask(__name__)


def load():
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"patients": [], "next_ref": 7001}


def save(s):
    STORE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def fake_jwt():
    def b64(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'HS256', 'typ': 'JWT'})}.{b64({'uid': UID, 'hcode': HCODE, 'exp': 4102444800})}.sig"


def dp(time_name=None):
    return (f'<pk-datepicker><div class="datepicker-container"><input type="text" class="datepicker-input" placeholder="วว/ดด/ปปปป"></div></pk-datepicker>'
            + (f'<input type="time" name="{time_name}">' if time_name else ""))


def pksel(options):
    opts = "".join(f'<div class="pk-select-option"><span class="pk-select-option-label">{o}</span></div>' for o in options)
    return (f'<pk-select><div class="pk-select-container"><div class="pk-select-trigger"><span class="pk-select-value">'
            f'<span class="pk-select-placeholder">Select</span></span><span class="pk-select-arrow">▼</span></div>'
            f'<div class="pk-select-dropdown" style="display:none"><div class="pk-select-search"><input class="pk-select-search-input" placeholder="ค้นหา..."></div>'
            f'<div class="pk-select-options">{opts}</div></div></div></pk-select>')


MRS = ["*** ไม่ได้ประเมิน", "0. No symptoms", "1. No significant disability", "2. Slight disability", "3. Moderate disability",
       "4. Moderately severe disability", "5. Severe disability", "6. Death"]
WARDS = ["CCU, 23", "MICU, 06", "Stroke Unit, 24", "อายุรกรรมชาย, 11"]


def radios(name, labels):
    return "".join(f'<input type="radio" id="{name}{v}" name="{name}" value="{v}"> {t} ' for v, t in labels)


FORM = f"""
<div id="form" style="display:none">
<pk-tab><span>เพิ่มข้อมูล</span> หน่วยงาน: mock</pk-tab>
<div><label>Diagnosis (ICD):</label> <input type="text" name="editRow.dx" value="I61">
 <select name="editRow.dx"><option value="I60">I60</option><option value="I61" selected>I61</option><option value="I63">I63</option><option value="G45">G45</option><option value="I67">I67</option></select>
 <select name="editRow.dmis"><option value="1" selected>Hemorrhagic Stroke, 1</option><option value="2">Ischemic Stroke, 2</option></select></div>
<div><label>AN:</label><input type="text" name="editRow.an"> <label>HN:</label><input type="text" name="editRow.hn">
 <label>เลขที่บัตรประชาชน:</label><input type="text" name="editRow.person_id"> <label>VN:</label><input type="text" name="editRow.vn"></div>
<div><label>คำนำหน้า:</label><input type="text" name="editRow.prename"> <label>ชื่อ:</label><input type="text" name="editRow.fname">
 <label>สกุล:</label><input type="text" name="editRow.lname"> <label>เพศ:</label>{radios("editRow.sex", [("1", "ชาย"), ("2", "หญิง")])}</div>
<div><label>วันเกิด:</label><br>{dp()} <label>อายุ (ปี):</label><input type="number" name="editRow.age[2]">
 <label>เดือน:</label><input type="number" name="editRow.age[1]"> <label>โทร:</label><input type="text" name="editRow.tel"></div>
<div><label>เวลาเริ่มป่วย/แสดงอาการ:</label><br>{dp("editRow.ill_time")}</div>
<div><label>เวลามาถึง รพ.(แรก):</label><br>{dp("editRow.arrival_time")}</div>
<div><label>วันที่รักษา/Admission:</label><br>{dp("editRow.admit_time")}</div>
<div><label>Discharge/กลับ:</label><br>{dp("editRow.disc_time")}</div>
<div><label>LOS (วัน):</label><input type="number" name="editRow.los">
 <label>Ward:</label><input type="text" name="editRow.ward">{pksel(WARDS)}
 <label>ผลการรักษาวันจำหน่าย:</label><select name="editRow.visit_result"><option value="">ไม่ทราบ</option><option value="1">ทุเลา/กลับบ้าน</option><option value="4">ส่งต่อ</option><option value="9">เสียชีวิต</option></select>
 <label>ผู้นำส่ง:</label><select name="editRow.carry"><option value="">มาเอง</option><option value="EMS">EMS รพ.</option><option value="FR">EMS ท้องถิ่น</option><option value="RELATE">ญาติ</option></select></div>
<div><label>BP:</label><input type="number" name="editRow.sbp"> / <input type="number" name="editRow.dbp">
 <label>GCS:</label><input type="number" name="editRow.gcs_eye"><input type="number" name="editRow.gcs_verbal"><input type="number" name="editRow.gcs_motor"><input type="number" name="editRow.gcs"></div>
<div><label>ได้รับยา rt-PA:</label>{radios("editRow.rtpa", [("1", "ได้รับ"), ("2", "ไม่ได้รับ"), ("0", "ไม่ทราบ")])}</div>
<div><label>เวลารับยา rt-PA:</label><br>{dp("editRow.rtpa_time")}</div>
<div><label>CT Scan:</label>{radios("editRow.ctscan", [("1", "ได้ทำ"), ("2", "ไม่ได้ทำ"), ("0", "ไม่ทราบ")])}</div>
<div><label>เวลาทำ CT Scan:</label><br>{dp("editRow.ctscan_time")}</div>
<div><label>เข้า Stroke Unit:</label>{radios("editRow.stroke_unit", [("1", "เข้า"), ("2", "ไม่ได้เข้า"), ("0", "ไม่ทราบ")])}</div>
<div><label>เวลาเข้า Stroke Unit:</label><br>{dp("editRow.stroke_unit_time")}</div>
<div><label>มีการผ่าตัด:</label>{radios("editRow.surgery", [("1", "มี"), ("2", "ไม่มี"), ("0", "ไม่ทราบ")])}</div>
<div><label>เวลาเข้าผ่าตัด:</label><br>{dp("editRow.surgery_start_time")}</div>
<div><span>แรกรับรักษา:</span>{pksel(MRS)}</div>
<div><span>ก่อนการจำหน่าย:</span>{pksel(MRS)}</div>
<button id="save">บันทึก</button>
</div>
"""

PAGE_JS = r"""
sessionStorage.setItem('tokenRefer', TOKEN);
document.getElementById('addnew').onclick = async () => {
  document.getElementById('form').style.display = '';
  if (new URLSearchParams(location.search).has('slow_init')) {
    await (await fetch('/test/init')).json();
    for (const key of ['hn','an']) document.querySelector(`[name="editRow.${key}"]`).value = '';
    document.getElementById('form').dataset.initialized = 'yes';
  }
};
// pk-datepicker: parse ตอน change เหมือน onChangeDate ของเว็บ (dd/mm/ปปปป พ.ศ. หรือ ISO)
document.querySelectorAll('pk-datepicker input.datepicker-input').forEach(inp => {
  inp.addEventListener('change', e => {
    let t = e.target.value; const m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (m && parseInt(m[3]) > 2400) t = `${parseInt(m[3]) - 543}-${m[2]}-${m[1]}`;
    const d = new Date(t);
    if (!isNaN(d.getTime())) { inp.dataset.iso = d.toISOString().slice(0, 10) === t.slice(0, 10) ? t.slice(0, 10) : d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
      inp.value = d.toLocaleDateString('th-TH', {day: '2-digit', month: '2-digit', year: 'numeric'}); }
  });
});
// pk-select
document.querySelectorAll('pk-select').forEach(sel => {
  const trig = sel.querySelector('.pk-select-trigger'), dd = sel.querySelector('.pk-select-dropdown');
  trig.onclick = () => { dd.style.display = dd.style.display === 'none' ? '' : 'none'; };
  sel.querySelector('.pk-select-search-input').oninput = e => {
    const q = e.target.value.toLowerCase();
    sel.querySelectorAll('.pk-select-option').forEach(o => o.style.display = o.textContent.toLowerCase().includes(q) ? '' : 'none');
  };
  sel.querySelectorAll('.pk-select-option').forEach(o => o.onclick = () => {
    sel.dataset.value = o.textContent.trim(); sel.querySelector('.pk-select-value').textContent = o.textContent.trim(); dd.style.display = 'none';
    const w = sel.previousElementSibling; if (w && w.name === 'editRow.ward') w.value = o.textContent.trim().split(',').pop().trim();
  });
});
document.getElementById('save').onclick = async () => {
  const data = {};
  document.querySelectorAll('#form input[name], #form select[name]').forEach(el => {
    if (el.type === 'radio') { if (el.checked) data[el.name] = el.value; }
    else if (el.tagName === 'SELECT' || el.type !== 'text' || !data[el.name]) data[el.name] = el.value;
  });
  const dates = {}; document.querySelectorAll('pk-datepicker').forEach(dp => {
    const inp = dp.querySelector('input'); const tm = dp.nextElementSibling; dates[(tm && tm.type === 'time' && tm.name) || 'birth'] = inp.dataset.iso || null; });
  data._dates = dates;
  const sels = {}; document.querySelectorAll('pk-select').forEach((s, i) => sels['pkselect' + i] = s.dataset.value || null); data._pkselect = sels;
  data.hn=data['editRow.hn']; data.an=data['editRow.an']; data.hospcode='10995';
  const r = await fetch('/api/beta/dmis/imc/save-patient', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({data})});
  const j = await r.json(); document.getElementById('toast').textContent = j.statusCode === 200 ? 'บันทึก Admission/Visit เรียบร้อย' : 'error';
  document.getElementById('form').style.display = 'none';
};
"""


@app.route("/beta/")
@app.route("/beta")
def index():
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>mock nRefer</title></head>
<body><h3>mock nRefer</h3><button id="addnew">Add new</button><div id="toast"></div>{FORM}
<script>const TOKEN = {json.dumps(fake_jwt())};{PAGE_JS}\n{(HERE / 'nrefer_widgets.js').read_text(encoding='utf-8')}</script></body></html>"""

@app.route('/test/init')
def delayed_init():
    time.sleep(2)
    return jsonify(ok=True)

@app.route('/his/refer/person', methods=['POST'])
def his_person():
    return jsonify(statusCode=200, rows=[])


@app.route("/api/beta/dmis/imc/save-patient", methods=["POST"])
def save_patient():
    s = load()
    d = request.get_json(force=True)["data"]
    d["ref"] = s["next_ref"]
    s["next_ref"] += 1
    s["patients"].append(d)
    save(s)
    return jsonify(statusCode=200, rows=[], message="ok")


@app.route("/api/beta/dmis/imc/patient", methods=["POST"])
def patient():
    s = load()
    w = request.get_json(force=True)["where"]
    rows = [{"ref": p["ref"], "hn": p.get("editRow.hn"), "hospcode": HCODE} for p in s["patients"] if p.get("editRow.hn") == w.get("hn")]
    return jsonify(statusCode=200, rows=rows)


@app.route("/test/his")
def delayed_his():
    time.sleep(1.5)
    return jsonify(fname="HIS-STALE", tel="HIS-STALE")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8590
    app.run(port=port, debug=False)
