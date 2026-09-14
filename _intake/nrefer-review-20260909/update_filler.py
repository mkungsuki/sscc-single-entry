from pathlib import Path
p = Path('C:/SSCC/app/fill_nrefer.py')
s = p.read_text(encoding='utf-8')
start = s.index('# ---------- ตัวช่วยกรอกช่องพิเศษ')
end = s.index('def open_add_form', start)
s = s[:start] + 'from nrefer_ui import fill_form\nfrom nrefer_save import SaveObserver\n\n\n' + s[end:]
start = s.index('def wait_for_save(')
end = s.index('def _page_alive(', start)
s = s[:start] + '''def process_case(page, ui_url, case, args):
    cid = case["id"]
    if case.get("nrefer_ref") or case.get("nrefer_state") in ("review", "uncertain"):
        log(cid, "เคสนี้เคยบันทึกหรือรอยืนยันผล — ตรวจทะเบียน nRefer ก่อน ไม่เปิดเพิ่มข้อมูลซ้ำ")
        return "draft"
    built = nrefer_map.build(case["data"], "", 0)
    if not built["ok"]:
        log(cid, built["reason"])
        return "failed"
    token = read_token(page)
    hcode = str(jwt_payload(token).get("hcode") or "")
    expected_hcode = CONFIG.get("nrefer_hcode")
    if expected_hcode and hcode != str(expected_hcode):
        raise RuntimeError("หน่วยงานที่ login ไม่ตรงกับ nrefer_hcode ใน config")
    hn, an = built["patient"]["hn"], built["patient"]["an"]
    if not an:
        log(cid, "ไม่มี AN — ตรวจทะเบียนและกรอก AN ใน SSCC ก่อน เพื่อแยกครั้งรักษา")
        return "draft"
    open_add_form(page, ui_url, cid)
    identity = {"hn": hn, "an": an, "hospcode": hcode}
    # Listen before filling: a very early user click cannot escape observation.
    db.set_nrefer_state(cid, "review")
    with SaveObserver(page, args.api_url, identity) as observer:
        try:
            robot_banner(page, "กำลังกรอก nRefer — กรุณารอให้ตรวจค่าครบก่อน", "#b45309")
            warnings = fill_form(page, nrefer_map.form_values(built), cid)
            warnings = list(dict.fromkeys(built["notes"] + warnings))
            for warning in warnings:
                log(cid, "⚠️ " + warning)
            details = " | ".join(warnings)
            robot_banner(page, "ตรวจข้อมูลทุกช่องแล้วกดบันทึกเอง" + (" — " + details if details else ""), "#b45309" if warnings else "#1a7f37")
            log(cid, "กรอกเสร็จ — ตรวจชื่อ HN/AN หน่วยงาน และคำเตือนบนฟอร์ม แล้วกดบันทึกเอง")
            ok, ref = observer.wait(REVIEW_WAIT_MS)
            if ok:
                db.set_nrefer(cid, ref or "sent")
                log(cid, "ยืนยัน response บันทึกตรง HN/AN/หน่วยงานแล้ว" + (f" — ref {ref}" if ref else " — เว็บไม่คืน ref ที่ยืนยันได้"))
                return "submitted"
            db.set_nrefer_state(cid, "uncertain" if observer.attempted else "draft")
            log(cid, "ยังยืนยันผลบันทึกไม่ได้ — ตรวจทะเบียนก่อนลองใหม่" if observer.attempted else "ไม่พบการกดบันทึกในรอบนี้ — จบการกรอก")
            return "draft"
        except Exception:
            db.set_nrefer_state(cid, "uncertain" if observer.attempted else "draft")
            raise


''' + s[end:]
s = s.replace('import re\n', 'import re\nfrom urllib.parse import urlsplit\n')
s = s.replace('return not exp or exp > time.time() + 60', 'return isinstance(exp, (int, float)) and exp > time.time() + 60 and bool(jwt_payload(token).get("hcode"))')
s = s.replace("sessionStorage.getItem('tokenRefer') || localStorage.getItem('tokenRefer') || ''", "sessionStorage.getItem('tokenRefer') || ''")
s = s.replace('if token_ok(tok):', 'if token_ok(tok) and "/login" not in page.url:')
s = s.replace('    ap.add_argument("--auto-confirm", action="store_true", help="กดบันทึกเองอัตโนมัติ (เฉพาะทดสอบ mock)")\n', '')
s = s.replace('ids = [int(x) for x in args.cases.split(",") if x.strip()]', 'ids = list(dict.fromkeys(int(x) for x in args.cases.split(",") if x.strip()))\n    if not ids:\n        ap.error("ต้องมี case id อย่างน้อยหนึ่งรายการ")')
start = s.index('    is_mock = ')
end = s.index('    if not is_mock:', start)
s = s[:start] + '    is_mock = urlsplit(args.ui_url).hostname in ("127.0.0.1", "localhost", "::1")\n' + s[end:]
s = s.replace('headless=args.headless, no_viewport=True)', 'headless=args.headless, no_viewport=True, chromium_sandbox=True)')
s = s.replace('color:#fff;font:600', 'max-height:30vh;overflow:auto;color:#fff;font:600')
s = s.replace('→ ถ้ายังไม่ login รอสแกน ThaID (จำ token ไว้ใช้จนหมดอายุ)', '→ ถ้ายังไม่ login รอสแกน ThaID (ไม่เก็บหรือฉีด token)')
s = s.replace('    หมายเหตุ: ไม่ยัด token เก่ากลับเข้าเว็บ — nRefer ไม่รับ token ที่ใส่เองและทำให้หน้า login ค้าง (เจอ TS 027 ตอนสแกน)\n    session ค้างในโปรไฟล์ Edge (data/edge_profile) ถ้ายัง login อยู่จะผ่านทันที ไม่งั้นสแกนครั้งเดียวใช้ได้ทั้งคิว', '    ไม่ยัด token เก่ากลับเข้าเว็บ; ใช้ session ที่เว็บสร้างเองและตรวจหน้า authenticated\n    สาเหตุ TS 027 ยังไม่ยืนยัน ไม่แก้ด้วยการฉีด token')
p.write_text(s, encoding='utf-8')
