# -*- coding: utf-8 -*-
"""รวมไฟล์ schema จาก _intake/schema/*.json เป็น schema กลาง app/schema/sscc_fields.json
รันซ้ำได้เสมอ (idempotent) — แก้ OVERRIDES แล้วรันใหม่เพื่อปรับ schema
"""
import json
import re
from pathlib import Path

SRC = Path(r"C:\SSCC\_intake\schema")
OUT = Path(r"C:\SSCC\app\schema\sscc_fields.json")

SECTIONS = {
    "tab_stroke_form1": ("A", "ข้อมูลผู้ป่วย (A1–A6)"),
    "tab_stroke_form2": ("A7", "ประวัติ/ปัจจัยเสี่ยง (A7)"),
    "tab_stroke_form3": ("B", "ข้อมูลทางคลินิก (B1–B19)"),
    "tab_stroke_form4": ("C1", "ตัวชี้วัดการดูแลรักษา (C2–C12)"),
    "tab_stroke_form5": ("C2", "ตัวชี้วัดการดูแลรักษา ต่อ (C13–C21)"),
    "tab_stroke_form6": ("D", "การหาสาเหตุโรค (D1–D3)"),
    "tab_stroke_form7": ("E", "Subarachnoid hemorrhage (E1–E2)"),
    "tab_stroke_form8": ("F", "Cerebral venous thrombosis (F1)"),
}

# ฟิลด์ A1-A6 ที่อยู่บนหน้า "เพิ่ม" (stroke_formadd.php) ด้วย
ADD_PAGE_FIELDS = {"x_pid", "x_fname", "x_a2", "x_a3", "x_a4", "x_a5",
                   "x_a6_1", "x_a6", "x_a6_address", "x_a6_hospcode"}

# ปรับแต่งรายฟิลด์: required / ชนิด / พิสัย / เงื่อนไขแสดงผล / default / การจัดการพิเศษ
OVERRIDES = {
    "x_pid":  {"type": "text", "pattern": r"^\d{13}$", "hint": "เลข 13 หลัก"},
    "x_a2":   {"required": True},
    "x_a3":   {"required": True, "type": "number", "min": 0, "max": 120},
    "x_a4":   {"required": True},
    "x_a6_address":  {"show_if": {"x_a6": ["1"]}, "default": "400000"},
    "x_a6_hospcode": {"show_if": {"x_a6": ["1"]}, "special": "cascade_hospital"},
    "x_a7_1_year":   {"type": "number", "min": 0, "max": 99, "show_if": {"x_a7_1": ["2"]}},
    "x_a7_1_month":  {"type": "number", "min": 0, "max": 11, "show_if": {"x_a7_1": ["2"]}},
    "x_a7_2_year":   {"type": "number", "min": 0, "max": 99, "show_if": {"x_a7_2": ["2"]}},
    "x_a7_2_month":  {"type": "number", "min": 0, "max": 11, "show_if": {"x_a7_2": ["2"]}},
    "x_a7_3_year":   {"type": "number", "min": 0, "max": 99, "show_if": {"x_a7_3": ["2"]}},
    "x_a7_3_month":  {"type": "number", "min": 0, "max": 11, "show_if": {"x_a7_3": ["2"]}},
    "x_a7_4_year":   {"type": "number", "min": 0, "max": 99, "show_if": {"x_a7_4": ["2"]}},
    "x_a7_4_month":  {"type": "number", "min": 0, "max": 11, "show_if": {"x_a7_4": ["2"]}},
    "x_a7_5_1":      {"show_if": {"x_a7_5": ["2"]}},
    "x_a7_6_1":      {"show_if": {"x_a7_6": ["2"]}},
    "x_a7_6_amount": {"type": "number", "min": 0, "max": 200, "show_if": {"x_a7_6": ["2"]}},
    "x_a7_7_1":      {"show_if": {"x_a7_7": ["2"]}},
    "x_a7_7_amount": {"type": "number", "min": 0, "max": 999, "show_if": {"x_a7_7": ["2"]}},
    "x_b2_1_date": {"type": "date"}, "x_b2_1_hhmm": {"type": "time"},
    "x_b2_2":      {"required": True},
    "x_b3_1_date": {"type": "date"}, "x_b3_1_hhmm": {"type": "time"},
    "x_b3_2_date": {"type": "date"}, "x_b3_2_hhmm": {"type": "time"},
    "x_b4_date":   {"type": "date"}, "x_b4_hhmm": {"type": "time"},
    "x_b4_followup_date":     {"type": "date", "show_if": {"x_b4_followup": ["Y"]}},
    "x_b4_not_followup_note": {"show_if": {"x_b4_followup": ["N"]}},
    "x_b4_1_address":  {"show_if": {"x_b4_1": ["2"]}, "default": "400000"},
    "x_b4_1_hospcode": {"show_if": {"x_b4_1": ["2"]}, "special": "cascade_hospital"},
    "x_b4_1_date":     {"type": "date", "show_if": {"x_b4_1": ["2"]}},
    "x_b4_1_time":     {"type": "time", "show_if": {"x_b4_1": ["2"]}},
    "x_b4_1_note":     {"show_if": {"x_b4_1": ["2"]}},
    "x_b7":  {"type": "number", "min": 3, "max": 15},
    "x_b8":  {"type": "number", "min": 3, "max": 15},
    "x_b9":  {"type": "number", "min": 0, "max": 100, "step": 5},
    "x_b10": {"type": "number", "min": 0, "max": 100, "step": 5},
    "x_b11": {"type": "number", "min": 0, "max": 5},
    "x_b12": {"type": "number", "min": 0, "max": 6},
    "x_b13": {"type": "number", "min": 0, "max": 42},
    "x_b14": {"type": "number", "min": 0, "max": 42},
    "x_b15_glycemic": {"type": "number", "min": 0, "max": 2000},
    "x_b15_date": {"type": "date"}, "x_b15_hhmm": {"type": "time"},
    "x_b16_date":     {"type": "date", "show_if": {"x_b16": ["2"]}},
    "x_b16_hhmm":     {"type": "time", "show_if": {"x_b16": ["2"]}},
    "x_b16_1":        {"show_if": {"x_b16": ["2"]}},
    "x_b16_1_note":   {"show_if": {"x_b16_1": ["2"]}},
    "x_b16_2":        {"show_if": {"x_b16": ["2"]}},
    "x_b16_2_amount": {"show_if": {"x_b16": ["2"]}},
    "x_b17_date": {"type": "date", "show_if": {"x_b17": ["2"]}},
    "x_b17_hhmm": {"type": "time", "show_if": {"x_b17": ["2"]}},
    "x_b18": {"type": "number", "min": 0, "max": 1000},
    "x_c2_amount": {"type": "number", "min": 0, "max": 28, "show_if": {"x_c2": ["1"]}},
    "x_c2_note":   {"show_if": {"x_c2": ["1"]}},
    "x_c3_date": {"type": "date", "show_if": {"x_c3": ["1"]}},
    "x_c3_hhmm": {"type": "time", "show_if": {"x_c3": ["1"]}},
    "x_c5_date": {"type": "date", "show_if": {"x_c5": ["1", "2", "3"]}},
    "x_c5_hhmm": {"type": "time", "show_if": {"x_c5": ["1", "2", "3"]}},
    "x_c7_date":    {"type": "date", "show_if": {"x_c7": ["1"]}},
    "x_c7_hhmm":    {"type": "time", "show_if": {"x_c7": ["1"]}},
    "x_c7_causeid": {"show_if": {"x_c7": ["3"]}},
    "x_c7_note":    {"show_if": {"x_c7": ["3"]}},
    "x_c8_1": {"show_if": {"x_c8": ["1"]}},
    "x_c8_2": {"show_if": {"x_c8": ["1"]}},
    "x_c11_note": {"show_if": {"x_c11": ["2"]}},
    "x_c12_note": {"show_if": {"x_c12": ["2", "3"]}},
    "x_c13_1houramt": {"type": "number", "min": 0, "show_if": {"x_c13_1": ["1"]}},
    "x_c13_2houramt": {"type": "number", "min": 0, "show_if": {"x_c13_2": ["1"]}},
    "x_c13_3houramt": {"type": "number", "min": 0, "show_if": {"x_c13_3": ["1"]}},
    "x_c13_4houramt": {"type": "number", "min": 0, "show_if": {"x_c13_4": ["1"]}},
    "x_c16_note": {"show_if": {"x_c16": ["2"]}},
    "x_c18_causeok": {"show_if": {"x_c18": ["2"]}},
    "x_c18_cause":   {"show_if": {"x_c18": ["3"]}},
    "x_c18_note":    {"show_if": {"x_c18": ["3"]}},
    "x_c19_note": {"show_if": {"x_c19": ["2"]}},
    "x_c20_date": {"type": "date", "show_if": {"x_c20": ["1"]}},
    "x_c21": {"type": "number", "min": 0},
    "x_c21_currency": {"default": "1"},
    "x_d2_intracerebral": {"show_if": {"x_d2": ["2"]}},
    "x_d3[]": {"show_if": {"x_b6": ["2"]}},
    # แท็บ E เฉพาะ SAH (B6=4), แท็บ F เฉพาะ CVT (B6=5)
    "x_e1":   {"show_if": {"x_b6": ["4"]}},
    # E2: เว็บจริง value กับ label ที่แสดงเหลื่อมกัน (บั๊กของ SSCC เอง) —
    # เราเก็บ "ข้อความที่ตาเห็น" แล้วให้ filler คลิกตาม label เพื่อให้ได้ผลเท่ากรอกมือ
    "x_e2[]": {"show_if": {"x_b6": ["4"]}, "check_by_label": True, "options": [
        {"v": "Endovascular(coiling)", "t": "Endovascular(coiling)"},
        {"v": "Neurosurgical(clipping)", "t": "Neurosurgical(clipping)"},
        {"v": "Bypass", "t": "Bypass"},
        {"v": "Other neurosurgical treatment(decompression/drainage)",
         "t": "Other neurosurgical treatment(decompression/drainage)"},
        {"v": "Patient referred to another hospital for intervention",
         "t": "Patient referred to another hospital for intervention"},
    ]},
    "x_f1[]": {"show_if": {"x_b6": ["5"]}},
}

# ฟิลด์ที่ต้องแทรกเพิ่ม (ไม่อยู่ในไฟล์ extract): (หลังฟิลด์ไหน, นิยาม)
_drug_map = json.loads((Path(r"C:\SSCC\app\schema\drug_map.json")).read_text(encoding="utf-8"))
EXTRA_FIELDS = [
    ("x_c18", {
        "sscc": "x_c18_drug", "label": "C18: ยาที่ได้รับ", "type": "select",
        "special": "drug_lookup", "show_if": {"x_c18": ["1", "2"]},
        "options": _drug_map["drugs"],
        "hint": "รหัสยาตรงกับระบบ SSCC — ยาใหม่ที่ไม่มีในรายการ เพิ่มได้ใน schema/drug_map.json",
    }),
]


def norm_options(raw):
    out = []
    for o in raw:
        if "รายการจังหวัดเดียวกับ" in o:
            return "COPY_PROVINCE"
        if "โหลดตามจังหวัด" in o:
            return []
        if "|" not in o:
            continue
        v, t = o.split("|", 1)
        if v == "" and "โปรดเลือก" in t:
            continue  # ตัวเลือกว่าง ไม่ต้องเก็บ
        out.append({"v": v, "t": t})
    return out


def main():
    files = ["panes-1-2.json", "pane-3.json", "pane-4.json", "panes-5-8.json"]
    panes = []
    for f in files:
        data = json.loads((SRC / f).read_text(encoding="utf-8"))
        panes.extend(data if isinstance(data, list) else [data])

    fields = []
    province_opts = None
    for pane in panes:
        sec_key, sec_title = SECTIONS[pane["pane"]]
        for fl in pane["fields"]:
            name = fl["n"]
            entry = {
                "sscc": name,
                "label": fl.get("lb", ""),
                "type": fl.get("t", "text"),
                "section": sec_key,
                "section_title": sec_title,
            }
            if fl.get("t") == "checkbox-group" or name.endswith("[]"):
                entry["type"] = "checkbox-group"
                vals = fl.get("values") or [v for v in (fl.get("o") or []) if v and v != "{value}"]
                entry["options"] = [{"v": v, "t": v} for v in vals if v and v != "{value}"]
            elif fl.get("o"):
                opts = norm_options(fl["o"])
                if opts == "COPY_PROVINCE":
                    entry["options"] = province_opts
                else:
                    entry["options"] = opts
                if name == "x_a6_address":
                    province_opts = entry["options"]
            ov = OVERRIDES.get(name, {})
            entry.update(ov)
            if name in ADD_PAGE_FIELDS:
                entry["on_add_page"] = True
            fields.append(entry)
            for after, extra in EXTRA_FIELDS:
                if name == after:
                    e = dict(extra)
                    e["section"] = sec_key
                    e["section_title"] = sec_title
                    fields.append(e)

    # กันชื่อซ้ำ
    seen = {}
    for f in fields:
        seen[f["sscc"]] = seen.get(f["sscc"], 0) + 1
    dups = {k: v for k, v in seen.items() if v > 1}
    assert not dups, f"duplicate field names: {dups}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "version": "1.0",
        "source": "แกะจาก stroke_formedit.php จริง 2026-07-13",
        "date_format": "dd/mm/yyyy (ค.ศ.)",
        "time_format": "HH:MM:SS",
        "fields": fields,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(fields)} fields -> {OUT}")
    print(f"  add-page fields: {sum(1 for f in fields if f.get('on_add_page'))}")
    print(f"  selects: {sum(1 for f in fields if f['type'] == 'select')}")
    print(f"  with show_if: {sum(1 for f in fields if f.get('show_if'))}")


if __name__ == "__main__":
    main()
