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
INCLUDE_FILES = ["server.py", "checks.py", "fill_sscc.py", "db.py", "excel_export.py", "import_export.py",
                 "runlock.py", "setup.bat", "start.bat", "update.bat", "requirements.txt", "README.md"]
INCLUDE_DIRS = ["schema", "templates"]

INSTALL_TXT = """วิธีติดตั้ง SSCC Stroke — กรอกครั้งเดียว (เครื่องใหม่)
=====================================================

สิ่งที่เครื่องต้องมี: Windows 10/11 (มี Microsoft Edge อยู่แล้ว) + อินเทอร์เน็ตตอนติดตั้งครั้งแรก

ทำแค่ 2 ขั้น:

1) แตกไฟล์ zip นี้ไว้ที่ไหนก็ได้ เช่น C:\\SSCC-app
   {overwrite_note}

2) ดับเบิลคลิก setup.bat แล้วรอจนเสร็จ (2-5 นาที)
   โปรแกรมจะติดตั้ง Python + ไลบรารีให้เอง สร้างทางลัด "SSCC Stroke"
   บนหน้าจอ แล้วเปิดโปรแกรมขึ้นมาเลย

วันต่อไป: ดับเบิลคลิกทางลัด "SSCC Stroke" บนหน้าจอ — วิธีใช้ประจำวันอ่านใน README.md
อัปเดตโปรแกรมครั้งถัดไป: ดับเบิลคลิก update.bat (โหลดเวอร์ชันล่าสุดจาก GitHub ให้เอง)

ถ้า setup.bat ติดตั้ง Python อัตโนมัติไม่ได้ มันจะเปิดหน้าเว็บ python.org ให้
ติดตั้งเองโดยติ๊ก "Add python.exe to PATH" แล้วดับเบิลคลิก setup.bat ซ้ำอีกครั้ง

หมายเหตุ
- ไม่ต้องติดตั้งเบราว์เซอร์เพิ่ม — โปรแกรมใช้ Microsoft Edge ที่มากับ Windows
- โปรแกรมไม่เก็บรหัสผ่าน SSCC — พยาบาล login ด้วยบัญชีตัวเองเสมอ
- ข้อมูลทั้งหมดอยู่ในเครื่องนี้เครื่องเดียว (โฟลเดอร์ data\\ และไฟล์ Excel)
  ห้ามแชร์โฟลเดอร์พวกนี้ขึ้น cloud/ไดรฟ์แชร์ (PDPA)
- เครื่องไม่มีเน็ตเลย: บนเครื่องที่มีเน็ตรัน  pip download -r requirements.txt -d libs
  ก๊อปโฟลเดอร์ libs ไปด้วย แล้วรัน  pip install --no-index --find-links libs -r requirements.txt
"""


def main():
    with_data = "--with-data" in sys.argv
    stamp = datetime.now().strftime("%Y%m%d")
    name = f"SSCC_deploy_{stamp}{'_มีข้อมูล' if with_data else ''}.zip"
    dest = DEST_DIR / name

    if with_data:
        overwrite_note = ("⚠️ zip นี้มีฐานข้อมูลติดมาด้วย — ใช้กับ \"เครื่องใหม่\" เท่านั้น\n"
                          "   ห้ามแตกทับเครื่องที่ใช้งานอยู่ เพราะฐานข้อมูลในเครื่องจะถูกทับหาย!\n"
                          "   (จะอัปเดตโปรแกรมบนเครื่องที่ใช้อยู่ ให้ใช้ zip แบบไม่มีข้อมูลแทน)")
    else:
        overwrite_note = "(ถ้าเครื่องนี้เคยลงโปรแกรมนี้แล้ว แตกทับได้เลย — ฐานข้อมูลเดิมไม่หาย)"
    install_txt = INSTALL_TXT.replace("{overwrite_note}", overwrite_note)

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
        z.writestr("อ่านก่อน-วิธีติดตั้ง.txt", install_txt)

    n = len(files) + 2
    print(f"สร้างแล้ว: {dest}  ({n} ไฟล์, {'มี' if with_data else 'ไม่มี'}ข้อมูลผู้ป่วย)")
    if with_data:
        print("⚠️ zip นี้มีข้อมูลผู้ป่วย — ย้ายด้วย USB เท่านั้น ห้ามส่งผ่าน LINE/email/cloud")


if __name__ == "__main__":
    main()
