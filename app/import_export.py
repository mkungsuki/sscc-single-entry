# -*- coding: utf-8 -*-
"""นำเข้าข้อมูลเก่าจากไฟล์ export ของ SSCC (CSV 149 คอลัมน์) เข้าฐานข้อมูลแอป
- ค่าใน export เป็นข้อความ (label) -> แปลงกลับเป็นรหัสตาม schema
- วันที่ dd/mm/yyyy -> ISO / เวลา HH:MM:SS -> HH:MM
- ข้ามเคสที่นำเข้าแล้ว (เช็คจากเลขที่ผู้ป่วย SSCC) -> รันซ้ำได้
ใช้: python import_export.py <ไฟล์ export.csv>
"""
import csv
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP_DIR = Path(__file__).parent
SCHEMA = json.loads((APP_DIR / "schema" / "sscc_fields.json").read_text(encoding="utf-8"))
import db  # noqa: E402

SKIP_COLUMNS = {"เขตบริการ", "ระดับโรงพยาบาล", "โรงพยาบาลเครือข่าย", "Service Plan",
                "A1: อักษรแรกของชื่อ-สกุล", "ผู้บันทึก", "เวลาที่บันทึก", "ผู้ปรับปรุง", "เวลาที่ปรับปรุง"}

# หัวคอลัมน์ใน export ที่สะกดต่างจาก label ใน schema
LABEL_ALIASES = {
    "C13.1: ผู้ป่วยมีโรคแทรกซ้อนเหล่านี้หรือไม่ -> Pneumonia": "x_c13_1",
    "C13.2: ผู้ป่วยมีโรคแทรกซ้อนเหล่านี้หรือไม่ -> Urinary Tract Infection": "x_c13_2",
    "C13.3: ผู้ป่วยมีโรคแทรกซ้อนเหล่านี้หรือไม่ -> Pressure Sore/Skin Break": "x_c13_3",
    "C13.4: ผู้ป่วยมีโรคแทรกซ้อนเหล่านี้หรือไม่ -> หลอดเลือดดำที่ขาอุดตัน (DVT)": "x_c13_4",
}


def norm_label(s):
    return re.sub(r"\s+", " ", (s or "").replace("*", "")).strip()


def build_maps():
    """คืน (label -> field def), (field -> {option label -> code})"""
    by_label = {}
    opt_maps = {}
    for f in SCHEMA["fields"]:
        by_label[norm_label(f["label"])] = f
        if f.get("options"):
            opt_maps[f["sscc"]] = {norm_label(o["t"]): o["v"] for o in f["options"]}
    return by_label, opt_maps


def convert_value(field, raw, opt_maps):
    v = (raw or "").strip()
    if not v:
        return None
    if field["type"] == "checkbox-group":
        parts = [p.strip() for p in v.split(",") if p.strip()]
        return parts
    if field["type"] == "date":
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", v)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else v
    if field["type"] == "time":
        m = re.match(r"^(\d{2}:\d{2}):\d{2}$", v)
        return m.group(1) if m else v
    if field.get("special") == "cascade_hospital":
        return v  # เก็บชื่อ รพ. ตรงๆ (ระบบเราใช้ชื่อ)
    if field["type"] == "select":
        codes = opt_maps.get(field["sscc"], {})
        return codes.get(norm_label(v), v)  # ถ้า map ไม่ได้เก็บข้อความไว้ (filler เลือกด้วย label ได้)
    return v


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\SSCC\stroke_form.csv")
    if not src.exists():
        print(f"ไม่พบไฟล์ {src}")
        sys.exit(1)

    by_label, opt_maps = build_maps()

    with sqlite3.connect(db.DB_PATH) as c:
        existing = {r[0] for r in c.execute(
            "SELECT sscc_patient_id FROM cases WHERE sscc_patient_id IS NOT NULL").fetchall()}

    imported = skipped = 0
    unmapped_cols = set()
    unmatched_options = {}

    with open(src, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = [norm_label(h) for h in next(reader)]
        sscc_by_name = {f["sscc"]: f for f in SCHEMA["fields"]}
        col_fields = []
        for h in header:
            if h in SKIP_COLUMNS or h in ("เลขที่ผู้ป่วย",):
                col_fields.append(("META", h))
            elif h in LABEL_ALIASES:
                col_fields.append(("FIELD", sscc_by_name[LABEL_ALIASES[h]]))
            elif h in by_label:
                col_fields.append(("FIELD", by_label[h]))
            else:
                # ฟิลด์รุ่นเก่าที่ไม่มีในฟอร์มปัจจุบัน — เก็บดิบไว้ไม่ให้ข้อมูลวิจัยหาย
                col_fields.append(("LEGACY", h))
                unmapped_cols.add(h)

        now = datetime.now().isoformat(timespec="seconds")
        rows_batch = []
        for row in reader:
            if not any(x.strip() for x in row):
                continue
            data, pid = {}, None
            for (kind, ref), raw in zip(col_fields, row):
                if kind == "META" and ref == "เลขที่ผู้ป่วย":
                    pid = raw.strip()
                elif kind == "LEGACY":
                    if raw.strip():
                        data[f"legacy|{ref}"] = raw.strip()
                elif kind == "FIELD":
                    v = convert_value(ref, raw, opt_maps)
                    if v is not None:
                        data[ref["sscc"]] = v
                        if (ref["type"] == "select" and not ref.get("special")
                                and isinstance(v, str) and v == raw.strip()
                                and norm_label(v) not in opt_maps.get(ref["sscc"], {}).values()
                                and v not in opt_maps.get(ref["sscc"], {}).values()):
                            unmatched_options.setdefault(ref["sscc"], set()).add(v)
            if not pid or pid in existing:
                skipped += 1
                continue
            existing.add(pid)
            rows_batch.append(((data.get("x_a2") or ""), (data.get("x_fname") or ""),
                               pid, json.dumps(data, ensure_ascii=False), now))
            imported += 1

    with sqlite3.connect(db.DB_PATH) as c:
        c.executemany(
            """INSERT INTO cases (status, hn, fname, sscc_patient_id, data, created_at, updated_at, submitted_at)
               VALUES ('imported', ?, ?, ?, ?, ?, ?, ?)""",
            [(hn, fn, pid, d, now, now, now) for hn, fn, pid, d, now in rows_batch])

    print(f"นำเข้า {imported} เคส / ข้าม {skipped} เคส (ซ้ำหรือว่าง)")
    if unmapped_cols:
        print(f"คอลัมน์ที่ไม่ได้ map ({len(unmapped_cols)}): {sorted(unmapped_cols)}")
    if unmatched_options:
        print("ค่าที่ map เป็นรหัสไม่ได้ (เก็บเป็นข้อความไว้):")
        for k, vals in sorted(unmatched_options.items()):
            print(f"  {k}: {sorted(vals)[:5]}{' ...' if len(vals) > 5 else ''}")

    import excel_export
    print("อัปเดต Excel:", excel_export.export_master())


if __name__ == "__main__":
    main()
