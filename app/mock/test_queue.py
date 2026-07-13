# -*- coding: utf-8 -*-
"""ทดสอบส่งแบบคิว (หลายเคสต่อกันในเบราว์เซอร์เดียว) กับ mock SSCC
สร้าง 3 เคส → รัน fill_sscc.py --cases a,b,c → ตรวจว่าทุกเคสถูก POST ครบและสถานะเป็น submitted"""
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

BASE_DATA = {
    "x_pid": "1234567890123", "x_a3": "70", "x_a4": "1",
    "x_a5": "UC", "x_a6_1": "Y", "x_a6": "1", "x_a6_address": "400000",
    "x_a6_hospcode": "โรงพยาบาลสีชมพู",
    "x_b5": "1", "x_b6": "2", "x_b7": "10",
    "x_b2_1_date": "2026-07-10", "x_b2_1_hhmm": "08:30",
}


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

        case_ids = []
        for n in range(1, 4):
            data = dict(BASE_DATA, x_a2=f"TESTQ90{n}", x_fname=f"คิวทดสอบ {n}", x_b7=str(5 + n))
            case_ids.append(db.save_case(None, data))
        print(f"สร้างเคสทดสอบ {case_ids}")

        r = subprocess.run(
            [sys.executable, str(APP / "fill_sscc.py"), "--cases", ",".join(map(str, case_ids)),
             "--base-url", "http://127.0.0.1:8548/stroke", "--auto-confirm", "--headless"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        print(r.stdout)
        if r.returncode != 0:
            print("FAIL: fill_sscc.py exit", r.returncode)
            print(r.stderr[-3000:])
            sys.exit(1)

        store = json.loads(store_path.read_text(encoding="utf-8"))
        failures = []
        if len(store["records"]) != 3:
            failures.append(("(จำนวน record บน mock)", 3, len(store["records"])))
        by_hn = {rec.get("x_a2"): rec for rec in store["records"].values()}
        for n, cid in enumerate(case_ids, 1):
            hn = f"TESTQ90{n}"
            rec = by_hn.get(hn)
            if not rec:
                failures.append((f"เคส {hn}", "มี record บน mock", "ไม่พบ"))
                continue
            if rec.get("x_b7") != str(5 + n):
                failures.append((f"{hn}: x_b7", str(5 + n), rec.get("x_b7")))
            if rec.get("x_b2_1_date") != "10/07/2026":
                failures.append((f"{hn}: x_b2_1_date", "10/07/2026", rec.get("x_b2_1_date")))
            case = db.get_case(cid)
            if case["status"] != "submitted":
                failures.append((f"{hn}: สถานะในแอป", "submitted", case["status"]))

        if failures:
            print(f"\nFAIL: {len(failures)} จุดไม่ตรง")
            for name, exp, got in failures:
                print(f"  {name}: คาด {exp!r} ได้ {got!r}")
            sys.exit(1)
        print("\nPASS: คิว 3 เคสส่งครบ ค่าถูกต้อง สถานะเป็น submitted ทั้งหมด")
    finally:
        mock.kill()
        with sqlite3.connect(APP / "data" / "sscc.db") as c:
            c.execute("DELETE FROM cases WHERE hn LIKE 'TESTQ%'")


if __name__ == "__main__":
    main()
