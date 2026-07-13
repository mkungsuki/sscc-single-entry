# -*- coding: utf-8 -*-
"""สร้างไฟล์ zip สำหรับเอาไปติดตั้งเครื่องพยาบาล
ใช้: python tools\\make_deploy_zip.py            -> โปรแกรมเปล่า (ไม่มีข้อมูลผู้ป่วย)
     python tools\\make_deploy_zip.py --with-data -> พกฐานข้อมูลเคสทั้งหมดไปด้วย (ย้ายเครื่องหลัก)
zip แบบ --with-data มีข้อมูลผู้ป่วย — ย้ายด้วย USB เท่านั้น ห้ามส่งผ่าน LINE/email/cloud (PDPA)
"""
import sys
import zipfile
from datetime import datetime
from pathlib import Path

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP = Path(__file__).parent.parent
DEST_DIR = APP.parent  # C:\SSCC

# ไฟล์/โฟลเดอร์ที่เครื่องพยาบาลต้องใช้ — ไม่รวม data/ (session+ฐานข้อมูล), output/, mock/, __pycache__
INCLUDE_FILES = ["server.py", "fill_sscc.py", "db.py", "excel_export.py", "import_export.py",
                 "runlock.py", "start.bat", "requirements.txt", "README.md"]
INCLUDE_DIRS = ["schema", "templates"]

INSTALL_TXT = """วิธีติดตั้ง SSCC Stroke — กรอกครั้งเดียว (เครื่องใหม่)
=====================================================

สิ่งที่เครื่องต้องมี: Windows 10/11 (มี Microsoft Edge อยู่แล้ว) + อินเทอร์เน็ตตอนติดตั้งครั้งแรก

1) ติดตั้ง Python (ครั้งเดียว)
   - โหลดจาก https://www.python.org/downloads/ (เวอร์ชัน 3.10 ขึ้นไป)
   - ตอนติดตั้ง **ติ๊ก "Add python.exe to PATH"** ก่อนกด Install

2) แตกไฟล์ zip นี้ไว้ที่ไหนก็ได้ เช่น C:\\SSCC-app
   (ถ้าในเครื่องนี้เคยลงโปรแกรมนี้แล้ว ให้แตกทับได้ — ฐานข้อมูลเดิมไม่หาย)

3) ติดตั้งไลบรารี (ครั้งเดียว)
   - เปิดโฟลเดอร์ที่แตกไว้ → คลิกที่แถบที่อยู่ (address bar) พิมพ์ cmd แล้วกด Enter
   - พิมพ์:  pip install -r requirements.txt
   - รอจนเสร็จ (ต้องต่อเน็ต)

4) เปิดใช้งาน: ดับเบิลคลิก start.bat
   - หน้าเว็บโปรแกรมจะเปิดเอง (http://127.0.0.1:8547)
   - วิธีใช้ประจำวันอ่านใน README.md

หมายเหตุ
- ไม่ต้องติดตั้งเบราว์เซอร์เพิ่ม — โปรแกรมใช้ Microsoft Edge ที่มากับ Windows
- โปรแกรมไม่เก็บรหัสผ่าน SSCC — พยาบาล login ด้วยบัญชีตัวเองเสมอ
- ข้อมูลทั้งหมดอยู่ในเครื่องนี้เครื่องเดียว (โฟลเดอร์ data\\ และไฟล์ Excel)
  ห้ามแชร์โฟลเดอร์พวกนี้ขึ้น cloud/ไดรฟ์แชร์ (PDPA)
- เครื่องไม่มีเน็ต: บนเครื่องที่มีเน็ตรัน  pip download -r requirements.txt -d libs
  ก๊อป libs ไปด้วย แล้วรัน  pip install --no-index --find-links libs -r requirements.txt
"""


def main():
    with_data = "--with-data" in sys.argv
    stamp = datetime.now().strftime("%Y%m%d")
    name = f"SSCC_deploy_{stamp}{'_มีข้อมูล' if with_data else ''}.zip"
    dest = DEST_DIR / name

    files = [(APP / f, f) for f in INCLUDE_FILES]
    for d in INCLUDE_DIRS:
        for p in sorted((APP / d).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                files.append((p, str(p.relative_to(APP))))
    if with_data:
        dbfile = APP / "data" / "sscc.db"
        if dbfile.exists():
            files.append((dbfile, "data/sscc.db"))
        else:
            print("⚠️ ไม่พบ data/sscc.db — zip นี้จะไม่มีข้อมูล")

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in files:
            if not src.exists():
                print(f"⚠️ ข้าม (ไม่พบ): {arc}")
                continue
            # config.json แยกจัดการข้างล่าง — ที่เก็บ Excel ของเครื่องเก่าไม่ควรติดไปเครื่องใหม่
            z.write(src, arc)
        import json
        cfg = json.loads((APP / "config.json").read_text(encoding="utf-8"))
        cfg["master_dir"] = ""
        z.writestr("config.json", json.dumps(cfg, ensure_ascii=False, indent=2))
        z.writestr("อ่านก่อน-วิธีติดตั้ง.txt", INSTALL_TXT)

    n = len(files) + 2
    print(f"สร้างแล้ว: {dest}  ({n} ไฟล์, {'มี' if with_data else 'ไม่มี'}ข้อมูลผู้ป่วย)")
    if with_data:
        print("⚠️ zip นี้มีข้อมูลผู้ป่วย — ย้ายด้วย USB เท่านั้น ห้ามส่งผ่าน LINE/email/cloud")


if __name__ == "__main__":
    main()
