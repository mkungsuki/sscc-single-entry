# -*- coding: utf-8 -*-
"""ตรวจความสอดคล้องของ timeline / ข้อมูลคลินิกในเคส (data quality checks)

หลักการ: เตือนแบบนุ่ม (soft) — ไม่บล็อกการบันทึก แต่ต้อง "รับทราบพร้อมเหตุผล" ก่อนส่ง SSCC
เหตุผลถูกเก็บไว้ในเคส (data["_dq"]["ack"]) เพื่อให้ตรวจย้อนหลังได้ ไม่ใช่เพื่อบังคับให้ตัวเลขสวย

รับ data = dict ค่าฟิลด์ตามที่ฟอร์มเก็บ (วันที่ 'YYYY-MM-DD', เวลา 'HH:MM')
คืน dict: {"flags": [ {code, level, msg} ], "derived": {...นาทีที่คำนวณได้...}}
level: "high" = แทบจะเป็นไปไม่ได้ทางคลินิก/น่าจะพิมพ์ผิด, "low" = ควรเช็ค
"""
from datetime import datetime

# ค่าจากฟอร์ม (schema/sscc_fields.json)
RTPA_YES = "2"          # x_b16
AF_YES = "2"            # x_a7_4
DX_ISCH, DX_TIA = "1", "3"   # x_b6
C18_ANTIPLATELET, C18_ANTICOAG = "1", "2"
C5_OUTSIDE_BEFORE = "3"      # CT จากภายนอกก่อนเข้ารับการรักษา
CF_EVENT_INHOSP = "inhosp"   # cf_rtpa_event


def _dt(d, t):
    if not d:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime((d + " " + t).strip() if t else d, fmt)
        except ValueError:
            continue
    return None


def _mins(a, b):
    return (b - a).total_seconds() / 60 if a and b else None


def _looks_like_date_typo(mins):
    """ต่างกัน ~1 วัน หรือ ~1 เดือน (28–31 วัน) แต่เศษเวลาอยู่ใน ±3 ชม. → น่าจะพิมพ์วัน/เดือนผิด"""
    if mins is None:
        return False
    day = 1440
    for span in (day, 28 * day, 29 * day, 30 * day, 31 * day):
        if abs(abs(mins) - span) <= 180:
            return True
    return False


def run(data: dict) -> dict:
    g = data.get
    flags, derived = [], {}

    def flag(code, level, msg):
        flags.append({"code": code, "level": level, "msg": msg})

    onset = _dt(g("x_b2_1_date"), g("x_b2_1_hhmm"))
    door = _dt(g("x_b3_1_date"), g("x_b3_1_hhmm"))
    admit = _dt(g("x_b3_2_date"), g("x_b3_2_hhmm"))
    disch = _dt(g("x_b4_date"), g("x_b4_hhmm"))
    ct = _dt(g("x_c5_date"), g("x_c5_hhmm"))
    needle = _dt(g("x_b16_date"), g("x_b16_hhmm")) if g("x_b16") == RTPA_YES else None
    recog = _dt(g("cf_rtpa_recog_date"), g("cf_rtpa_recog_hhmm")) if g("cf_rtpa_event") == CF_EVENT_INHOSP else None

    # ปีพิมพ์ผิด (เช่น 2066 / 2015) — เทียบกับวันนี้
    now = datetime.now()
    for label, val in (("เริ่มอาการ B2.1", onset), ("มาถึง รพ. B3.1", door), ("รับไว้ B3.2", admit),
                       ("จำหน่าย B4", disch), ("CT C5", ct), ("rtPA B16", needle)):
        if val and (val > now.replace(hour=23, minute=59) or val.year < 2010):
            flag("date_out_of_range", "high", f"วันที่ {label} = {val:%d/%m/%Y} อยู่ในอนาคต/เก่าผิดปกติ — น่าจะพิมพ์ปีผิด")
            break

    otd = _mins(onset, door)
    if otd is not None:
        derived["onset_to_door"] = round(otd)
        if otd < 0:
            flag("onset_after_door", "low",
                 "เวลาเริ่มอาการ (B2.1) อยู่หลังเวลามาถึง รพ. (B3.1) — ถ้าเป็น stroke ที่เกิดระหว่าง admit ด้วยโรคอื่น (in-hospital stroke) ให้รับทราบพร้อมระบุ ไม่งั้นเช็ควันที่/เวลา")
    if admit and door and admit < door:
        flag("admit_before_door", "low", "เวลารับไว้ในสถานพยาบาล (B3.2) อยู่ก่อนเวลามาถึง OPD/ER (B3.1)")
    if disch and admit and disch < admit:
        flag("disch_before_admit", "high", "วันที่จำหน่าย (B4) อยู่ก่อนวันรับไว้ (B3.2)")

    dtc = _mins(door, ct)
    if dtc is not None:
        derived["door_to_ct"] = round(dtc)
        if dtc < 0 and g("x_c5") != C5_OUTSIDE_BEFORE:
            flag("ct_before_door", "low",
                 "เวลา CT (C5) อยู่ก่อนเวลามาถึง รพ. — ถ้าเป็น CT จาก รพ.ต้นทาง ให้เลือก C5 = 'ตรวจจากภายนอก ก่อนเข้ารับการรักษา' (ไม่ใช่ 'หลังรับไว้') ไม่งั้นเช็ควันที่")
        if dtc > 24 * 60:
            flag("ct_after_24h", "low", "CT (C5) ห่างจากมาถึง รพ. เกิน 24 ชม. — ลงเวลา CT ครั้งแรก ไม่ใช่ CT ซ้ำ")

    if needle:
        dtn = _mins(door, needle)
        derived["door_to_needle"] = round(dtn) if dtn is not None else None
        otn = _mins(onset, needle)
        if otn is not None:
            derived["onset_to_needle"] = round(otn)
        if dtn is not None:
            if dtn < 0:
                if _looks_like_date_typo(dtn):
                    flag("dtn_neg_typo", "high",
                         "เวลาให้ rtPA อยู่ก่อนเวลามาถึง รพ. ต่างกันเกือบพอดี 1 วัน/1 เดือน — น่าจะพิมพ์วันที่ผิด (rtPA ให้ที่ชุมแพเท่านั้น จึงต้องหลังมาถึงเสมอ)")
                else:
                    flag("dtn_negative", "high",
                         "เวลาให้ rtPA (B16) อยู่ก่อนเวลามาถึง รพ. (B3.1) — เช็คว่าเวลามาถึงใช้เวลา triage/แรกพบ ไม่ใช่เวลาลงทะเบียน")
            elif dtn > 270:
                if _looks_like_date_typo(dtn):
                    flag("dtn_long_typo", "high",
                         f"door-to-needle {round(dtn)} นาที และห่างกันเกือบพอดี 1 วัน/1 เดือน — น่าจะพิมพ์วันที่ผิด")
                elif not recog:
                    flag("dtn_over_270", "high",
                         f"door-to-needle {round(dtn)} นาที (เกิน 4.5 ชม.) — ถ้าเป็นอาการที่เกิด/progress ระหว่างอยู่ใน รพ. ให้ระบุในหัวข้อ 'ลักษณะเคส rtPA' พร้อมเวลาที่พบอาการ")
            elif dtn > 60 and not recog and not g("cf_dtn_delay"):
                flag("dtn_over_60_no_reason", "low",
                     f"door-to-needle {round(dtn)} นาที — ช่วยระบุ 'เหตุที่ล่าช้า' ในหัวข้อของ รพ. (ใช้ทำ Pareto ไม่ใช่หาคนผิด)")
        if otn is not None and otn > 270 and not recog:
            flag("ont_over_270", "low",
                 f"onset-to-needle {round(otn)} นาที (เกิน 4.5 ชม.) — เช็คเวลาเริ่มอาการ หรือระบุว่าเป็น in-hospital progression")
        if otn is not None and otn < 0:
            flag("needle_before_onset", "high", "เวลาให้ rtPA อยู่ก่อนเวลาเริ่มอาการ")
        if ct and needle < ct:
            flag("needle_before_ct", "high",
                 "เวลาให้ rtPA อยู่ก่อนเวลา CT — ปกติต้อง CT ก่อนให้ยาเสมอ (ลง CT ครั้งแรก ไม่ใช่ CT ซ้ำ 24 ชม. / เวลาออกผลอ่าน)")
        if recog:
            r2n = _mins(recog, needle)
            derived["recog_to_needle"] = round(r2n) if r2n is not None else None
            if door and recog < door:
                flag("recog_before_door", "low", "เวลาที่พบอาการ (in-hospital) อยู่ก่อนเวลามาถึง รพ. — ถ้ามาถึงด้วยอาการนี้เลย ให้เลือก 'มาถึง รพ.ด้วยอาการนี้'")
            if r2n is not None and r2n < 0:
                flag("needle_before_recog", "high", "เวลาให้ rtPA อยู่ก่อนเวลาที่พบอาการ (in-hospital)")

    # ให้ rtPA แต่ final dx ไม่ใช่ ischemic → หลุดจากตัวตั้ง recanalization rate (ปี 2025+ เจอ 13/131 เคส)
    if g("x_b16") == RTPA_YES and g("x_b6") and g("x_b6") != DX_ISCH:
        flag("rtpa_final_dx_not_ischemic", "low",
             "ให้ rtPA แต่ Final Diagnosis ไม่ใช่ Ischemic Stroke — ถ้าเป็นเลือดออกหลังให้ยา (hemorrhagic transformation) ยังนับเป็น Ischemic Stroke ที่มีภาวะแทรกซ้อน ไม่ใช่ ICH; เช็คว่าไม่ได้เลือกผิดข้อ (CVT/SAH)")

    # AF + ischemic/TIA + จำหน่ายด้วย antiplatelet อย่างเดียว → ต้องมีเหตุผล (เก็บที่ฟิลด์ รพ.)
    if (g("x_a7_4") == AF_YES and g("x_b6") in (DX_ISCH, DX_TIA)
            and g("x_c18") == C18_ANTIPLATELET and not g("cf_af_no_oac")):
        flag("af_no_oac_reason", "low",
             "มี AF แต่จำหน่ายด้วยยาต้านเกล็ดเลือดอย่างเดียว — ระบุเหตุที่ไม่ได้ anticoagulant ในหัวข้อของ รพ. (ถ้ามีข้อห้ามจริง จะได้ไม่ถูกนับว่าพลาด)")

    return {"flags": flags, "derived": derived}


def unacked(data: dict, level=None) -> list:
    """ธงที่ยังไม่ได้รับทราบ (เทียบ code กับ ack ล่าสุด) — level="high" เอาเฉพาะธงแดง"""
    res = run(data)
    ack = ((data.get("_dq") or {}).get("ack") or {})
    acked = set(ack.get("codes") or [])
    return [f for f in res["flags"] if f["code"] not in acked and (level is None or f["level"] == level)]


def blocking(data: dict) -> list:
    """ธงที่กั้นการส่ง SSCC = เฉพาะธงแดง (พิมพ์ผิดชัด/เป็นไปไม่ได้ทางคลินิก) ที่ยังไม่รับทราบ
    ธงเหลืองแค่โชว์ในแถบ/หน้ารวม ไม่รบกวนคนคีย์"""
    return unacked(data, "high")
