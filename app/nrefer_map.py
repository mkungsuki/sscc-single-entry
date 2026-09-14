# -*- coding: utf-8 -*-
"""แปลงข้อมูลเคสในโปรแกรม (key ตาม SSCC + cf_*) → ค่าที่กรอกในฟอร์ม nRefer DMIS

ที่มา: แกะจาก JS ของ nrefer.moph.go.th/beta (component dmis patient, method savePatient) 2026-09-09
ลำดับที่หน้าเว็บ nRefer บันทึกเอง:
  1) POST /dmis/imc/save-person  {data: person}
  2) POST /dmis/imc/person       {where: {hn}}      → person_ref
  3) POST /dmis/imc/save-patient {data: patient + person_ref}   (ref=0 สร้างใหม่ / ref>0 แก้ของเดิม)

รหัสตัวเลือกฝั่ง nRefer (จาก template ของฟอร์ม):
  sex 1 ชาย 2 หญิง | rtpa/ctscan/stroke_unit/surgery: 1 ได้รับ/ทำ, 2 ไม่ได้, 0 ไม่ทราบ
  visit_result: '' ไม่ทราบ, 1 ทุเลา/กลับบ้าน, 4 ส่งต่อ, 9 เสียชีวิต
  carry: '' มาเอง, EMS = EMS รพ., FR = EMS ท้องถิ่น, RELATE = ญาติ
  imc: 1 เข้าเกณฑ์, 0 ไม่เข้าเกณฑ์, 2 ไม่เข้าเกณฑ์แต่ส่งดูแลต่อเนื่อง
  dmis (กลุ่ม): 2 Ischemic (I63–I69), 1 Hemorrhage (I60–I62)   dx = ICD-10 3 ตัว
"""
import re
from datetime import date, datetime

# --- รหัสฝั่ง SSCC ที่ใช้ตัดสิน ---
SSCC_YES_RTPA = "2"      # x_b16
SSCC_YES_SURG = "2"      # x_d2
SSCC_YES_SU = "1"        # x_c10
SSCC_DEAD = "1"          # x_c20
SSCC_REFER_OUT = "2"     # x_b4_1
SSCC_EMS = "Y"           # x_a6_1
WARD_STROKE_UNIT = "7883"  # x_b1_1 ของ รพ.ชุมแพ

# Final Dx (x_b6) / First Dx (x_b5) → (ICD, กลุ่ม DMIS, หมายเหตุ)
DX_MAP = {
    "1": ("I63", "2", None),
    "2": ("I61", "1", None),
    "3": (None, None, None),  # Requires a user-confirmed nRefer ICD, below.
    "4": ("I60", "1", None),
    "5": (None, None, None),
}

PRENAMES = ["นางสาว", "เด็กหญิง", "เด็กชาย", "น.ส.", "ด.ญ.", "ด.ช.", "นาง", "นาย", "พระ", "สามเณร",
            "แม่ชี", "ร.ต.อ.", "ร.ต.ท.", "ร.ต.ต.", "พ.ต.อ.", "พ.ต.ท.", "พ.ต.ต.", "ส.ต.อ.", "ส.ต.ท.", "ส.ต.ต.",
            "จ.ส.อ.", "จ.ส.ท.", "จ.ส.ต.", "ส.อ.", "ส.ท.", "ส.ต.", "ร.อ.", "ร.ท.", "ร.ต.", "พ.อ.", "พ.ท.", "พ.ต.",
            "พล.ต.", "พล.ท.", "พล.อ.", "น.อ.", "น.ท.", "น.ต.", "ว่าที่ ร.ต.", "ดร.", "นพ.", "พญ.", "Mr.", "Mrs.", "Miss"]


def split_name(full):
    """'นางสาวสมหญิง ใจดี' → ('นางสาว', 'สมหญิง', 'ใจดี') — ถ้าไม่มีคำนำหน้า prename=''"""
    s = (full or "").strip()
    s = re.sub(r"\s+", " ", s)
    pre = ""
    for p in sorted(PRENAMES, key=len, reverse=True):
        if s.startswith(p):
            pre, s = p, s[len(p):].strip()
            break
    parts = s.split(" ", 1)
    fname = parts[0] if parts else ""
    lname = parts[1].strip() if len(parts) > 1 else ""
    return pre, fname, lname


def _dt(d, t):
    """'YYYY-MM-DD' + 'HH:MM' → 'YYYY-MM-DD HH:MM:SS' (รูปแบบเดียวกับ concatDatetime ของ nRefer)"""
    if not d:
        return None
    try:
        date.fromisoformat(d)
    except (TypeError, ValueError):
        return None
    t = (t or "").strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t):
        return d  # Known date, unknown time: never invent midnight.
    return f"{d} {t}:00"


def _days(d1, d2):
    try:
        a = datetime.strptime(d1, "%Y-%m-%d").date()
        b = datetime.strptime(d2, "%Y-%m-%d").date()
        return max((b - a).days, 0)
    except (TypeError, ValueError):
        return 0


def _int(v, default=None):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def _tri(v, yes, no):
    """แปลงรหัส SSCC → 1 ได้/2 ไม่ได้/0 ไม่ทราบ"""
    v = (v or "").strip()
    if v == "":
        return 0
    if v == yes:
        return 1
    if v in no:
        return 2
    return 0


def build(data: dict, hospcode: str, uid) -> dict:
    """คืน {"ok": bool, "reason": str, "person": {...}, "patient": {...}, "raw": {...},
             "notes": [...], "summary": [(label, value), ...]}
    ไม่เรียก API; mRS เลือกผ่าน UI และ ref ยืนยันจากผลบันทึกของผู้ใช้เท่านั้น"""
    g = lambda k: str(data[k]).strip() if data.get(k) is not None else None
    notes = []
    date_keys = ("cf_birth", "x_b2_1_date", "x_b3_1_date", "x_b3_2_date", "x_b4_date", "x_b16_date",
                 "cf_nrefer_ct_date", "cf_nrefer_su_date", "cf_nrefer_surgery_date", "cf_nrefer_surgery_end_date")
    if g("cf_nrefer_ctscan") == "1" and g("cf_nrefer_ct_use_c5") == "1":
        date_keys += ("x_c5_date",)
    for key in date_keys:
        if g(key):
            try:
                date.fromisoformat(g(key))
            except ValueError:
                return {"ok": False, "reason": f"วันที่ {key} ไม่ถูกต้อง — ต้องเป็นวันจริงในรูปแบบ ค.ศ. YYYY-MM-DD"}

    hn = g("x_a2")
    if not hn:
        return {"ok": False, "reason": "ไม่มี HN (A2) — nRefer ใช้ HN เป็นกุญแจหลัก"}

    dx_code = g("x_b6") or g("x_b5")
    if dx_code == "6" or (not dx_code):
        return {"ok": False, "reason": "ไม่มี Final/First Diagnosis หรือเป็น Stroke mimics — ไม่เข้าทะเบียน DMIS Stroke"}
    if dx_code not in DX_MAP:
        return {"ok": False, "reason": f"รหัสวินิจฉัย {dx_code} แปลงเป็น ICD ของ DMIS ไม่ได้"}
    dx, dmis, dx_note = DX_MAP[dx_code]
    if dx_code in ("3", "5"):
        override = g("cf_nrefer_dx")
        groups = {**{f"I{i}": "1" for i in range(60, 63)},
                  **{f"I{i}": "2" for i in range(63, 70)}}
        if override not in groups:
            return {"ok": False, "reason": "TIA/CVT: ต้องให้เจ้าของทะเบียนระบุ ICD สำหรับ nRefer ก่อน — ไม่เดากลุ่มโรค"}
        dx, dmis, dx_note = override, groups[override], "ใช้ ICD nRefer ที่ผู้ใช้ระบุสำหรับ TIA/CVT — ตรวจเกณฑ์ทะเบียนด้วย"
    if dx_note:
        notes.append(dx_note)
    if not g("x_b6") and g("x_b5"):
        notes.append("ยังไม่มี Final Dx — ใช้ First Dx แทน")

    pre, fname, lname = split_name(g("x_fname"))
    if not lname:
        notes.append("ชื่อ-สกุลแยกนามสกุลไม่ได้ (ไม่มีช่องว่าง) — ตรวจชื่อบน nRefer")
    cf_pre = g("cf_prename")
    if cf_pre:
        pre = cf_pre

    admit_d, admit_t = g("x_b3_2_date"), g("x_b3_2_hhmm")
    if not admit_d:
        # OPD case / ยังไม่ admit → ใช้วันมาถึง รพ. เป็นวันรักษา (nRefer ต้องมี admit เพื่อคิด LOS)
        admit_d, admit_t = g("x_b3_1_date"), g("x_b3_1_hhmm")
        if admit_d:
            notes.append("ไม่มีวันที่รับไว้ใน รพ. (B3.2) — ใช้วันมาถึง OPD/ER (B3.1) เป็นวันที่รักษา")
    disc_d, disc_t = g("x_b4_date"), g("x_b4_hhmm")
    if admit_d and disc_d and disc_d < admit_d:
        return {"ok": False, "reason": "วันจำหน่ายอยู่ก่อนวันรับไว้ — ตรวจวันที่ก่อนกรอก nRefer"}

    sex = g("x_a4") if g("x_a4") in ("1", "2") else ""
    if not sex:
        notes.append("ไม่ได้ระบุเพศ")

    birth = g("cf_birth") or None
    if birth and not re.match(r"^\d{4}-\d{2}-\d{2}$", birth):
        birth = None
    age_year = _int(g("x_a3"))

    rtpa = _tri(g("x_b16"), SSCC_YES_RTPA, ("1",))
    ctscan = _int(g("cf_nrefer_ctscan"), 0)
    if ctscan not in (0, 1, 2):
        ctscan = 0
    if not g("cf_nrefer_ctscan"):
        notes.append("CT Scan: SSCC รวม CT/MRI ภายใน 24 ชม. — เลือกผล CT สำหรับ nRefer เอง (ขณะนี้ไม่ทราบ)")
    stroke_unit = _tri(g("x_c10"), SSCC_YES_SU, ("2",))
    surgery = _tri(g("x_d2"), SSCC_YES_SURG, ("1",))

    su_date = None
    if stroke_unit == 1:
        if g("cf_nrefer_su_date"):
            su_date = _dt(g("cf_nrefer_su_date"), g("cf_nrefer_su_time"))
        elif g("x_b1_1") == WARD_STROKE_UNIT and admit_d:
            su_date = _dt(admit_d, admit_t)
            notes.append("เวลาเข้า Stroke Unit ใช้เวลารับไว้ใน รพ. (ward แรกรับคือ Stroke Unit)")
        else:
            notes.append("SSCC ไม่มีช่องเวลาเข้า Stroke Unit — เว้นไว้ให้เติมบน nRefer")
    if surgery == 1 and not (g("cf_nrefer_surgery_date") and g("cf_nrefer_surgery_end_date")):
        notes.append("SSCC ไม่มีเวลาเข้า/สิ้นสุดผ่าตัด — เว้นไว้ให้เติมบน nRefer")

    if g("x_c20") == SSCC_DEAD:
        visit_result = "9"
    elif g("x_b4_1") == SSCC_REFER_OUT:
        visit_result = "4"
    elif g("cf_nrefer_visit_result") in ("1", "4", "9"):
        visit_result = g("cf_nrefer_visit_result")
    else:
        visit_result = ""

    carry = {"SELF": "", "EMS": "EMS", "FR": "FR", "RELATE": "RELATE"}.get(g("cf_nrefer_carry"))
    if carry is None:
        notes.append("ผู้นำส่ง: SSCC ไม่แยกประเภทตรงกับ nRefer — ต้องเลือกบนฟอร์มจริง")

    sbp = _int(g("cf_sbp"), 0) or 0
    dbp = _int(g("cf_dbp"), 0) or 0
    gcs = _int(g("x_b7"), 0) or 0
    if not (sbp and dbp):
        notes.append("ไม่มีค่า BP แรกรับ (ฟิลด์ รพ. cf_sbp/cf_dbp) — เว้นไว้")
    if gcs:
        notes.append(f"GCS รวมจาก SSCC = {gcs}; ช่องรวม nRefer อ่านอย่างเดียว — ต้องตรวจ E/V/M และผลรวมบนเว็บ")

    an = g("cf_an") or ""
    if not an:
        notes.append("ไม่มี AN (ฟิลด์ รพ. cf_an) — nRefer ใช้ AN แยกการมาแต่ละครั้ง ควรกรอกถ้ามี")

    person = {
        "hospcode": hospcode, "hn": hn, "person_id": g("x_pid") or "",
        "prename": pre, "fname": fname, "lname": lname,
        "birth": birth, "sex": sex, "tel": g("cf_tel") or g("cf_phone") or "",
        "lat": None, "lng": None, "user_input": uid,
    }
    patient = {
        "ref": 0, "dx": dx, "dmis": dmis, "hospcode": hospcode,
        "hn": hn, "an": an, "vn": g("cf_vn") or "",
        "age_year": age_year, "age_month": 0,
        "dateadmit": _dt(admit_d, admit_t), "datedisc": _dt(disc_d, disc_t),
        "admit": admit_d or None, "disc": disc_d or None,
        "los": _days(admit_d, disc_d) if admit_d and disc_d else 0,
        "ward": "", "rtpa": rtpa, "carry": carry, "imc": "0", "caregiver": 0, "status": 1,
        "date_completed": None, "date_dead": None, "completed_detail": None,
        "completed_user": None, "completed_hospcode": None,
        "remark": "", "detail": "", "patient_goal": "",
        "complication": "[]", "gps_lat": None, "gps_lng": None, "user_input": uid,
        "evaluate": None,
        "impairement": '{"swallowing":false,"communication":false,"mobility":false,"cognitive":false,"bowel":false}',
    }
    raw = {
        "dateadmit": patient["dateadmit"], "datedisc": patient["datedisc"],
        "ill_date": _dt(g("x_b2_1_date"), g("x_b2_1_hhmm")),
        "arrival_date": _dt(g("x_b3_1_date"), g("x_b3_1_hhmm")),
        "rtpa": rtpa, "rtpa_date": _dt(g("x_b16_date"), g("x_b16_hhmm")) if rtpa == 1 else None,
        "ctscan": ctscan, "ctscan_date": (_dt(g("x_c5_date"), g("x_c5_hhmm"))
            if g("cf_nrefer_ct_use_c5") == "1" else _dt(g("cf_nrefer_ct_date"), g("cf_nrefer_ct_time"))) if ctscan == 1 else None,
        "stroke_unit": stroke_unit, "stroke_unit_date": su_date,
        "surgery": surgery,
        "surgery_start_date": _dt(g("cf_nrefer_surgery_date"), g("cf_nrefer_surgery_time")) if surgery == 1 else None,
        "surgery_end_date": _dt(g("cf_nrefer_surgery_end_date"), g("cf_nrefer_surgery_end_time")) if surgery == 1 else None,
        "visit_result": visit_result, "his_opdvisit": None, "his_ipdvisit": None,
        "mrscale_before": None, "mrscale_after": None,   # เติมหลัง lookup รายการ mRS ของ nRefer
        "sbp": sbp, "dbp": dbp, "gcs": gcs, "gcs_eye": 0, "gcs_verbal": 0, "gcs_motor": 0,
        "his_ipddx": None,
        "sscc_source": "SSCC-single-entry",
    }
    mrs = {"before": g("x_b11"), "after": g("x_b12")}

    TRI = {1: "ได้รับ/ทำ", 2: "ไม่ได้", 0: "ไม่ทราบ"}
    VR = {"": "ไม่ทราบ", "1": "ทุเลา/กลับบ้าน", "4": "ส่งต่อ", "9": "เสียชีวิต"}
    summary = [
        ("HN / AN", f"{hn} / {an or '-'}"),
        ("ชื่อ", f"{pre} {fname} {lname}".strip()),
        ("เลขบัตร ปชช.", person["person_id"]),
        ("เพศ / อายุ", f"{'ชาย' if sex == '1' else 'หญิง' if sex == '2' else '-'} / {age_year if age_year is not None else '-'} ปี"),
        ("Dx (กลุ่ม DMIS)", f"{dx} ({'Ischemic' if dmis == '2' else 'Hemorrhage'})"),
        ("เวลาเริ่มอาการ", raw["ill_date"] or "-"),
        ("เวลาถึง รพ.", raw["arrival_date"] or "-"),
        ("Admission → Discharge", f"{patient['dateadmit'] or '-'} → {patient['datedisc'] or '-'} (LOS {patient['los']} วัน)"),
        ("ผลการรักษาวันจำหน่าย", VR[visit_result]),
        ("ผู้นำส่ง", {None: "ต้องเลือกเอง", "": "มาเอง", "EMS": "EMS รพ.", "FR": "EMS ท้องถิ่น", "RELATE": "ญาติ"}[carry]),
        ("rt-PA", TRI[rtpa] + (f" — {raw['rtpa_date']}" if raw["rtpa_date"] else "")),
        ("CT Scan", TRI[ctscan] + (f" — {raw['ctscan_date']}" if raw["ctscan_date"] else "")),
        ("Stroke Unit", TRI[stroke_unit] + (f" — {su_date}" if su_date else "")),
        ("ผ่าตัด", TRI[surgery]),
        ("BP / GCS", f"{sbp or '-'}/{dbp or '-'} / {gcs or '-'}"),
        ("mRS แรกรับ / ก่อนจำหน่าย", f"{mrs['before'] or '-'} / {mrs['after'] or '-'}"),
    ]
    # ชื่อ ward ตาม SSCC (x_b1_1) → ใช้ค้นในรายการ ward ของ nRefer (label เช่น "Stroke Unit, 24")
    ward_name = g("cf_nrefer_ward") or WARD_NAMES.get(g("x_b1_1") or "", "")
    if not ward_name:
        notes.append("Ward ยังจับคู่ไม่ได้ — เลือกจากรายการ nRefer")
    components = {k: _int(g("cf_nrefer_gcs_" + k)) for k in ("eye", "verbal", "motor")}
    if any(components[k] is not None and not 1 <= components[k] <= limit
           for k, limit in (("eye", 4), ("verbal", 5), ("motor", 6))):
        return {"ok": False, "reason": "GCS E/V/M ต้องอยู่ในช่วง E 1–4, V 1–5, M 1–6"}
    if all(v is not None for v in components.values()) and gcs and sum(components.values()) != gcs:
        return {"ok": False, "reason": "GCS E/V/M รวมไม่ตรงคะแนน SSCC — ตรวจข้อมูลก่อนกรอก"}
    return {"ok": True, "person": person, "patient": patient, "raw": raw, "mrs": mrs,
            "notes": notes, "summary": summary, "ward_name": ward_name, "gcs_components": components}


WARD_NAMES = {"7883": "Stroke Unit",
              "7885": "อายุรกรรมชาย", "7884": "อายุรกรรมหญิง"}


def _split_dt(v):
    """'YYYY-MM-DD HH:MM:SS' → ('YYYY-MM-DD', 'HH:MM')"""
    if not v:
        return None, None
    return v[:10], v[11:16]


def form_values(built: dict) -> dict:
    """ค่าที่จะกรอกลงฟอร์ม 'เพิ่มข้อมูล' ของ nRefer (ชื่อ key = ngModel บนหน้าเว็บ editRow.*)
    วันที่ส่งเป็น ISO (ปี ค.ศ.) — pk-datepicker ของ nRefer รับ ISO ผ่าน event change ได้ตรงๆ (แกะจาก onChangeDate)
    คืน dict: {"text": {name: value}, "radio": {name: value}, "select": {name: value}, "date": {label_key: iso},
               "time": {name: 'HH:MM'}, "mrs": {"before": '0'..'6', "after": ...}, "ward_name": str}"""
    p, per, raw = built["patient"], built["person"], built["raw"]
    text = {
        "editRow.an": p["an"], "editRow.hn": p["hn"], "editRow.person_id": per["person_id"], "editRow.vn": p["vn"],
        "editRow.prename": per["prename"], "editRow.fname": per["fname"], "editRow.lname": per["lname"],
        "editRow.age[2]": str(p["age_year"]) if p["age_year"] is not None else "", "editRow.age[1]": "",
        "editRow.tel": per["tel"], "editRow.los": str(p["los"]) if p["dateadmit"] and p["datedisc"] else "",
        "editRow.sbp": str(raw["sbp"] or ""), "editRow.dbp": str(raw["dbp"] or ""),
    }
    for key, value in built["gcs_components"].items():
        text["editRow.gcs_" + key] = str(value) if value is not None else ""
    radio = {"editRow.sex": per["sex"], "editRow.rtpa": str(raw["rtpa"]), "editRow.ctscan": str(raw["ctscan"]),
             "editRow.stroke_unit": str(raw["stroke_unit"]), "editRow.surgery": str(raw["surgery"])}
    select = {"editRow.dx": p["dx"], "editRow.dmis": p["dmis"], "editRow.visit_result": raw["visit_result"],
              "editRow.carry": p["carry"]}
    date, time_ = {}, {}
    for key, tname, val in (("ill", "editRow.ill_time", raw["ill_date"]), ("arrival", "editRow.arrival_time", raw["arrival_date"]),
                            ("admit", "editRow.admit_time", p["dateadmit"]), ("disc", "editRow.disc_time", p["datedisc"]),
                            ("rtpa", "editRow.rtpa_time", raw["rtpa_date"]), ("ctscan", "editRow.ctscan_time", raw["ctscan_date"]),
                            ("stroke_unit", "editRow.stroke_unit_time", raw["stroke_unit_date"]),
                            ("surgery", "editRow.surgery_start_time", raw["surgery_start_date"]),
                            ("surgery_end", "editRow.surgery_end_time", raw["surgery_end_date"])):
        d, t = _split_dt(val)
        date[tname] = d or ""
        time_[tname] = t or ""
    date["birth"] = per["birth"] or ""
    return {"text": text, "radio": radio, "select": select, "date": date, "time": time_,
            "mrs": {k: str(v).strip() if v is not None else "" for k, v in built["mrs"].items()},
            "ward_name": built["ward_name"], "gcs_total": str(raw["gcs"] or "")}
