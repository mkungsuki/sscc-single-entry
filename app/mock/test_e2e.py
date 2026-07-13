# -*- coding: utf-8 -*-
"""ทดสอบ end-to-end กับ mock SSCC: สร้างเคส → รัน fill_sscc.py → ตรวจค่าที่ถูก POST ทุกฟิลด์"""
import json
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
APP = HERE.parent
sys.path.insert(0, str(APP))
import db  # noqa: E402

SCHEMA = json.loads((APP / "schema" / "sscc_fields.json").read_text(encoding="utf-8"))
FIELDS = {f["sscc"]: f for f in SCHEMA["fields"]}

TESTDATA = {
    "x_pid": "1234567890123", "x_fname": "ทดสอบ ระบบ", "x_a2": "TEST9001", "x_a3": "69", "x_a4": "2",
    "x_a5": "UC", "x_a6_1": "Y", "x_a6": "1", "x_a6_address": "400000",
    "x_a6_hospcode": "โรงพยาบาลสีชมพู",
    "x_a7_1": "2", "x_a7_1_year": "3", "x_a7_1_month": "0",
    "x_a7_2": "2", "x_a7_2_year": "5", "x_a7_2_month": "0",
    "x_a7_3": "1", "x_a7_4": "1", "x_a7_5": "1", "x_a7_6": "1", "x_a7_7": "1",
    "x_b1_1": "7883", "x_b2_1_date": "2026-07-01", "x_b2_1_hhmm": "20:00", "x_b2_2": "OPD",
    "x_b3_1_date": "2026-07-02", "x_b3_1_hhmm": "15:44",
    "x_b3_2_date": "2026-07-02", "x_b3_2_hhmm": "17:54",
    "x_b4_date": "2026-07-05", "x_b4_hhmm": "10:00",
    "x_b4_followup": "Y", "x_b4_followup_date": "2026-07-20",
    "x_b4_1": "2", "x_b4_1_address": "400000", "x_b4_1_hospcode": "โรงพยาบาลชุมแพ",
    "x_b5": "1", "x_b6": "1", "x_b7": "15", "x_b8": "15", "x_b9": "100", "x_b10": "100",
    "x_b11": "0", "x_b12": "0", "x_b13": "2", "x_b14": "1",
    "x_b15": "0", "x_b15_glycemic": "100", "x_b15_date": "2026-07-02", "x_b15_hhmm": "15:50",
    "x_b15_1": "1", "x_b15_2": "2",
    "x_b16": "2", "x_b16_date": "2026-07-02", "x_b16_hhmm": "16:30",
    "x_b16_1": "1", "x_b16_2": "1", "x_b16_2_amount": "0.9 mg/kg",
    "x_b17": "1", "x_b18": "126", "x_b19": "2",
    "x_c2": "2", "x_c3": "1", "x_c3_date": "2026-07-02", "x_c3_hhmm": "14:13",
    "x_c4": "2", "x_c5": "1", "x_c5_date": "2026-07-02", "x_c5_hhmm": "17:13", "x_c6": "1",
    "x_c7": "1", "x_c7_date": "2026-07-02", "x_c7_hhmm": "18:00",
    "x_c8": "2", "x_c9": "1", "x_c10": "1", "x_c11": "1", "x_c12": "1",
    "x_c13_1": "2", "x_c13_2": "2", "x_c13_3": "2", "x_c13_4": "2", "x_c14": "2",
    "x_c15_1": "1", "x_c15_2": "1", "x_c15_3": "1",
    "x_c16": "2", "x_c16_note": "ไม่สูบบุหรี่",
    "x_c17": "1", "x_c18": "1", "x_c18_drug": "1", "x_c19": "1", "x_c20": "2",
    "x_c21": "7648", "x_c21_currency": "1",
    "x_d1[]": ["CTA", "MRA"], "x_d2": "1",
}

# ฟิลด์ รพ. (cf_*) กรอกปนไปด้วย — ต้องอยู่ในแอปครบ แต่ห้ามหลุดไปเว็บ SSCC เด็ดขาด
CUSTOM_DATA = {"cf_test_mrs": "3", "cf_test_note": "ทดสอบฟิลด์ รพ. ห้ามไปโผล่บนเว็บ"}


def hosp_name_to_code(name):
    f = FIELDS["x_a6_hospcode"]
    for o in f["options"]:
        if o["t"] == name:
            return o["v"]
    return name


def expected_value(name, v):
    f = FIELDS[name]
    if f.get("special") == "cascade_hospital":
        return hosp_name_to_code(v)
    if f["type"] == "date":
        y, m, d = v.split("-")
        return f"{d}/{m}/{y}"
    if f["type"] == "time":
        return f"{v}:00" if len(v) == 5 else v
    return v


def main():
    store_path = HERE / "mock_store.json"
    if store_path.exists():
        store_path.unlink()

    mock = subprocess.Popen([sys.executable, str(HERE / "mock_sscc.py")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            try:
                urllib.request.urlopen("http://127.0.0.1:8548/stroke/stroke_formlist.php", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("FAIL: mock ไม่ขึ้น")
            sys.exit(1)

        case_id = db.save_case(None, {**TESTDATA, **CUSTOM_DATA})
        print(f"สร้างเคสทดสอบ #{case_id}")

        r = subprocess.run(
            [sys.executable, str(APP / "fill_sscc.py"), "--case", str(case_id),
             "--base-url", "http://127.0.0.1:8548/stroke", "--auto-confirm", "--headless"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        print(r.stdout)
        if r.returncode != 0:
            print("FAIL: fill_sscc.py exit", r.returncode)
            print(r.stderr[-3000:])
            sys.exit(1)

        store = json.loads(store_path.read_text(encoding="utf-8"))
        assert len(store["records"]) == 1, f"คาด 1 record ได้ {len(store['records'])}"
        rec = list(store["records"].values())[0]

        failures = []
        for name, v in TESTDATA.items():
            if name == "x_d1[]":
                got = rec.get(name, [])
                if sorted(got) != sorted(v):
                    failures.append((name, v, got))
                continue
            exp = expected_value(name, v)
            got = rec.get(name, "<ไม่มีค่า>")
            if str(got) != str(exp):
                failures.append((name, exp, got))

        # ฟิลด์ รพ. ต้องไม่หลุดไปเว็บ และค่าต้องยังอยู่ครบในแอป
        leaked = [k for k in rec if k.startswith("cf_")]
        if leaked:
            failures.append(("(ฟิลด์ รพ. หลุดไปเว็บ SSCC)", "ไม่มี", leaked))
        case = db.get_case(case_id)
        for k, v in CUSTOM_DATA.items():
            if case["data"].get(k) != v:
                failures.append((f"(ฟิลด์ รพ. {k} ในแอป)", v, case["data"].get(k)))

        # เช็คสถานะเคสในแอปต้องเป็น submitted
        if case["status"] != "submitted":
            failures.append(("(สถานะเคสในแอป)", "submitted", case["status"]))

        if failures:
            print(f"\nFAIL: {len(failures)} ฟิลด์ไม่ตรง")
            for name, exp, got in failures:
                print(f"  {name}: คาด {exp!r} ได้ {got!r}")
            sys.exit(1)
        print(f"\nPASS: ตรวจแล้ว {len(TESTDATA)} ฟิลด์ ถูกต้องครบ + สถานะเคสเป็น submitted")
    finally:
        mock.kill()
        # ลบเคสทดสอบออกจากฐานข้อมูลจริง
        with sqlite3.connect(APP / "data" / "sscc.db") as c:
            c.execute("DELETE FROM cases WHERE hn = 'TEST9001'")


if __name__ == "__main__":
    main()
