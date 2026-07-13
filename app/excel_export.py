# -*- coding: utf-8 -*-
"""สร้างไฟล์ Excel master จากฐานข้อมูล — 1 แถวต่อเคส + backup อัตโนมัติ"""
import json
import shutil
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

import db

APP_DIR = Path(__file__).parent
CONFIG = json.loads((APP_DIR / "config.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((APP_DIR / "schema" / "sscc_fields.json").read_text(encoding="utf-8"))
CUSTOM_PATH = APP_DIR / "schema" / "custom_fields.json"


def _custom_fields():
    if not CUSTOM_PATH.exists():
        return []
    data = json.loads(CUSTOM_PATH.read_text(encoding="utf-8"))
    return [f for f in data.get("fields", []) if f.get("enabled", True)]


def _label_for_value(field, v):
    """แปลงรหัสเป็นข้อความอ่านได้ (เก็บทั้งรหัสและข้อความใน Excel)"""
    for o in field.get("options", []) or []:
        if o["v"] == v:
            return o["t"]
    return v


def export_master():
    out_dir = Path(CONFIG.get("master_dir") or (APP_DIR / "output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "SSCC_master.xlsx"

    fields = [f for f in SCHEMA["fields"]] + _custom_fields()
    meta_cols = ["case_id", "สถานะ", "เลขที่ผู้ป่วย SSCC", "วันที่บันทึก", "วันที่ส่ง SSCC"]

    cases = db.all_cases_full()
    known = {f.get("sscc") or f["key"] for f in fields}
    extra_keys = sorted({k for c in cases for k in c["data"] if k not in known})

    wb = Workbook()
    ws = wb.active
    ws.title = "master"
    ws2 = wb.create_sheet("รหัส (อ่านได้)")

    header = meta_cols + [f.get("sscc") or f["key"] for f in fields] + extra_keys
    header_labels = meta_cols + [f["label"] for f in fields] + [k.replace("legacy|", "") for k in extra_keys]
    for ws_, hdr in ((ws, header), (ws2, header_labels)):
        ws_.append(hdr)
        for c in ws_[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="DDEBF7")
        ws_.freeze_panes = "A2"

    for case in cases:
        d = case["data"]
        meta = [case["id"], case["status"], case.get("sscc_patient_id") or "",
                case.get("created_at") or "", case.get("submitted_at") or ""]
        raw_row, readable_row = list(meta), list(meta)
        for f in fields:
            key = f.get("sscc") or f["key"]
            v = d.get(key, "")
            if isinstance(v, list):
                v = ", ".join(v)
            raw_row.append(v)
            readable_row.append(_label_for_value(f, v) if f.get("options") else v)
        for k in extra_keys:
            raw_row.append(d.get(k, ""))
            readable_row.append(d.get(k, ""))
        ws.append(raw_row)
        ws2.append(readable_row)

    for ws_ in (ws, ws2):
        for i in range(1, min(ws_.max_column, 60) + 1):
            ws_.column_dimensions[get_column_letter(i)].width = 14

    wb.save(out_path)

    # backup รายวัน
    bak_dir = out_dir / "backups"
    bak_dir.mkdir(exist_ok=True)
    bak = bak_dir / f"SSCC_master_{datetime.now():%Y%m%d}.xlsx"
    shutil.copy2(out_path, bak)
    return str(out_path)


if __name__ == "__main__":
    print(export_master())
