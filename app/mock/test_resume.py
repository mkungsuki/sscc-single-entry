# -*- coding: utf-8 -*-
"""ทดสอบการจำเลขเคสฝั่ง SSCC (กันสร้างซ้ำ — บทเรียนจากหน้างานจริง 2026-08):
1. ส่งเคสปกติ → เลขเคสถูกจำไว้ใน db ตั้งแต่ขั้นสร้าง
2. เคสที่มีเลขจำไว้ → เปิดกรอกที่เคสเดิม ไม่ add ใหม่ (จำนวน record บน mock ไม่เพิ่ม)
3. เลขที่จำไว้ใช้ไม่ได้ (เคสถูกลบจากเว็บ) → สร้างใหม่ให้เอง"""
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

BASE = {
    "x_pid": "1234567890123", "x_a3": "65", "x_a4": "2",
    "x_a5": "UC", "x_a6_1": "Y", "x_a6": "1", "x_a6_address": "400000",
    "x_a6_hospcode": "โรงพยาบาลสีชมพู", "x_b5": "1", "x_b7": "12",
}


def run_fill(case_id):
    return subprocess.run(
        [sys.executable, str(APP / "fill_sscc.py"), "--case", str(case_id),
         "--base-url", "http://127.0.0.1:8548/stroke", "--auto-confirm", "--headless"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)


def store():
    return json.loads((HERE / "mock_store.json").read_text(encoding="utf-8"))


def main():
    sp = HERE / "mock_store.json"
    if sp.exists():
        sp.unlink()
    mock = subprocess.Popen([sys.executable, str(HERE / "mock_sscc.py")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fails = []

    def check(name, cond, detail=""):
        print(("PASS" if cond else "FAIL"), name, detail if not cond else "")
        if not cond:
            fails.append(name)

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

        # 1) ส่งปกติ — เลขเคสต้องถูกจำ
        c1 = db.save_case(None, dict(BASE, x_a2="TESTR901", x_fname="จำเลข หนึ่ง"))
        r = run_fill(c1)
        check("เคสแรกส่งสำเร็จ", r.returncode == 0, r.stdout[-400:])
        case1 = db.get_case(c1)
        pid1 = case1.get("sscc_patient_id")
        check("เลขเคสถูกจำใน db", bool(pid1), case1)
        check("mock มี 1 record", len(store()["records"]) == 1)

        # 2) เคสร่างที่มีเลขจำไว้ → ต้องเปิดเคสเดิม ไม่ add ใหม่
        c2 = db.save_case(None, dict(BASE, x_a2="TESTR902", x_fname="จำเลข สอง", x_b7="9"))
        db.set_draft_pid(c2, pid1)  # จำลอง "รอบก่อนสร้างค้างไว้ที่เคสนี้"
        r = run_fill(c2)
        check("เคสที่จำเลขไว้ส่งสำเร็จ", r.returncode == 0, r.stdout[-400:])
        check("ไม่สร้าง record ใหม่", len(store()["records"]) == 1, store()["records"].keys())
        rec = store()["records"][pid1]
        check("กรอกทับเคสเดิมถูกตัว", rec.get("x_a2") == "TESTR902" and rec.get("x_b7") == "9", rec.get("x_a2"))
        check("ใช้เลขเดิม", db.get_case(c2)["sscc_patient_id"] == pid1)
        check("log บอกว่าเปิดเคสเดิม", "ไม่สร้างซ้ำ" in r.stdout)

        # 3) เลขที่จำไว้ใช้ไม่ได้ (ถูกลบจากเว็บ) → สร้างใหม่ให้เอง
        c3 = db.save_case(None, dict(BASE, x_a2="TESTR903", x_fname="จำเลข สาม"))
        db.set_draft_pid(c3, "888888")
        r = run_fill(c3)
        check("เคสเลขเสียส่งสำเร็จ (สร้างใหม่)", r.returncode == 0, r.stdout[-400:])
        check("มี record เพิ่มเป็น 2", len(store()["records"]) == 2)
        pid3 = db.get_case(c3)["sscc_patient_id"]
        check("ได้เลขใหม่ ไม่ใช่เลขเสีย", pid3 and pid3 != "888888", pid3)
        check("log บอกว่าสร้างใหม่แทน", "จะสร้างเคสใหม่บนเว็บแทน" in r.stdout)
    finally:
        mock.kill()
        with sqlite3.connect(APP / "data" / "sscc.db") as c:
            c.execute("DELETE FROM cases WHERE hn LIKE 'TESTR%'")

    if fails:
        print(f"\nFAIL: {fails}")
        sys.exit(1)
    print("\nPASS: จำเลขเคส/ไม่สร้างซ้ำ/สร้างใหม่เมื่อเคสหาย ครบทุกข้อ")


if __name__ == "__main__":
    main()
