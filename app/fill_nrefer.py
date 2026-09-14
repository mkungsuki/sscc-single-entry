# -*- coding: utf-8 -*-
"""กรอกฟอร์ม nRefer (Stroke & IMC / DMIS) ให้จากข้อมูลในโปรแกรม แล้ว "หยุด" ให้พยาบาลตรวจและกด [บันทึก] เอง
หลักเดียวกับ fill_sscc.py: โปรแกรมไม่บันทึกอะไรเอง ไม่มีการเรียก API เขียนข้อมูล — การบันทึกเกิดจากปุ่มของ nRefer เท่านั้น

ขั้นตอน: เปิด Edge (โปรไฟล์เดิม) → ไป nRefer → ถ้ายังไม่ login รอสแกน ThaID (ไม่เก็บหรือฉีด token)
        → หน้าทะเบียน กด "Add new" → กรอกช่องตามข้อมูลเคส → แถบเขียว "ตรวจแล้วกด [บันทึก]"
        → รอจนเว็บบันทึกสำเร็จ (ดักผลตอบกลับของ /save-patient จากปุ่มบันทึกของเว็บ) → จำเลข ref ไว้ในเคส

โครงฟอร์ม (สำรวจ 2026-09-09 แบบอ่านอย่างเดียว + แกะจากโค้ดเว็บ):
  ช่องข้อความ/ตัวเลข/เวลา: <input name="editRow.xxx">, radio id="editRow.rtpa1" (1 ได้/2 ไม่/0 ไม่ทราบ)
  select: editRow.dx / editRow.dmis / editRow.visit_result / editRow.carry
  ปฏิทิน: <pk-datepicker> มี input.datepicker-input — เว็บ parse ค่าเมื่อเกิด event 'change'
          (รับ dd/mm/ปปปป พ.ศ. หรือ ISO ค.ศ.); ตัวปฏิทินอยู่ก่อน input[type=time] ในกล่องเดียวกัน
  dropdown: <pk-select> .pk-select-trigger → .pk-select-option (label เช่น "4. Moderately severe...", "Stroke Unit, 24")
  อายุ/LOS ไม่คำนวณเองจากวันที่ (เว็บคำนวณเฉพาะตอนดึงจาก HIS) → โปรแกรมกรอกให้
"""
import argparse
import base64
import json
import os
from urllib.parse import urlsplit
import sys
import time
from pathlib import Path

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

import db
import nrefer_map
import runlock
from nrefer_ui import fill_form, form_load_barrier
from nrefer_save import SaveObserver
from nrefer_guard import install_read_only_guard

APP_DIR = Path(__file__).parent
CONFIG = json.loads((APP_DIR / "config.json").read_text(encoding="utf-8"))

NREFER_UI = CONFIG.get("nrefer_base_url", "https://nrefer.moph.go.th/beta")
LOGIN_WAIT_MS = 10 * 60 * 1000
REVIEW_WAIT_MS = int(os.environ.get("SSCC_NREFER_REVIEW_MS") or 60 * 60 * 1000)   # รอพยาบาลตรวจ/กดบันทึก สูงสุด 60 นาที (env ไว้ย่อเวลาตอนเทสต์)

def log(case_id, msg):
    print(msg, flush=True)
    try:
        db.append_log(case_id, msg)
    except Exception:
        pass


def jwt_payload(token):
    try:
        if not isinstance(token, str) or len(token.split(".")) != 3:
            return {}
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        result = json.loads(base64.urlsafe_b64decode(part.encode()).decode("utf-8"))
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


def token_ok(token):
    if not token:
        return False
    exp = jwt_payload(token).get("exp")
    return isinstance(exp, (int, float)) and exp > time.time() + 60 and bool(jwt_payload(token).get("hcode"))


def read_token(page):
    try:
        return page.evaluate("() => sessionStorage.getItem('tokenRefer') || ''")
    except Exception:
        return ""


def robot_banner(page, text, color="#b45309"):
    try:
        page.evaluate(
            """([t, c]) => {
                let b = document.getElementById('sscc_robot_banner');
                if (!b) { b = document.createElement('div'); b.id = 'sscc_robot_banner'; document.body.prepend(b); }
                b.style.cssText = 'position:fixed;bottom:8px;right:8px;width:360px;max-width:90vw;z-index:2147483646;background:' + c +
                    ';max-height:30vh;overflow:auto;color:#fff;font:600 14px/1.4 sans-serif;padding:10px;box-shadow:0 2px 8px rgba(0,0,0,.25)';
                b.replaceChildren();
                const details = document.createElement('details'); details.open = false;
                const summary = document.createElement('summary'); summary.textContent = 'SSCC → nRefer: ' + t.split(' — ')[0];
                const body = document.createElement('div'); body.textContent = t;
                details.append(summary, body); b.append(details);
            }""", [text, color])
    except Exception:
        pass


def ensure_login(page, ui_url, case_id):
    """เปิด nRefer แล้วรอจนพยาบาล login ThaID เสร็จ (สแกน QR เอง โปรแกรมไม่ยุ่งกับการ login)
    ไม่ยัด token เก่ากลับเข้าเว็บ; ใช้ session ที่เว็บสร้างเองและตรวจหน้า authenticated
    สาเหตุ TS 027 ยังไม่ยืนยัน ไม่แก้ด้วยการฉีด token"""
    page.goto(ui_url + "/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    told = False
    deadline = time.time() + LOGIN_WAIT_MS / 1000
    while time.time() < deadline:
        tok = read_token(page)
        if token_ok(tok) and "/login" not in page.url:
            if told:
                log(case_id, "login nRefer สำเร็จ")
            return tok
        if not told:
            log(case_id, "กรุณา login nRefer ด้วย ThaID ในหน้าต่าง Edge (สแกน QR ด้วยแอป ThaID) — โปรแกรมจะไปต่อเองเมื่อ login เสร็จ")
            robot_banner(page, "🔐 กรุณา login ด้วย ThaID — โปรแกรมจะกรอกฟอร์มให้เองเมื่อ login เสร็จ")
            told = True
        page.wait_for_timeout(2000)
    raise RuntimeError("login nRefer ไม่สำเร็จภายในเวลาที่กำหนด")


def open_add_form(page, ui_url, case_id):
    # HN being visible does not mean getStrokePatient() has finished resetting editRow.
    with form_load_barrier(page) as wait_loaded:
        _open_add_form(page, ui_url, case_id)
        log(case_id, "ขั้นตอน: รอข้อมูลเริ่มต้นฟอร์มโหลดเสร็จก่อนกรอก HN/AN")
        wait_loaded()
        page.locator('input[name="editRow.hn"]').wait_for(state='visible')


def _open_add_form(page, ui_url, case_id):
    log(case_id, "ขั้นตอน: เปิดทะเบียน nRefer")
    page.goto(ui_url + "/#/dmis/patient", wait_until="domcontentloaded", timeout=60000)
    log(case_id, "ขั้นตอน: รอปุ่ม Add new")
    btn = page.get_by_role("button", name="Add new")
    btn.first.wait_for(timeout=30000)
    btn.first.click()
    log(case_id, "ขั้นตอน: รอช่อง HN ในฟอร์มเพิ่มข้อมูล")
    page.locator('input[name="editRow.hn"]').wait_for(timeout=15000)
    if page.get_by_text("เพิ่มข้อมูล").count() == 0:
        raise RuntimeError("เปิดฟอร์ม 'เพิ่มข้อมูล' ไม่ได้ (หน้าเว็บอาจเปลี่ยน)")


def process_case(page, ui_url, case, args):
    cid = case["id"]
    if case.get("nrefer_ref") or case.get("nrefer_state") in ("review", "uncertain"):
        log(cid, "เคสนี้เคยบันทึกหรือรอยืนยันผล — ตรวจทะเบียน nRefer ก่อน ไม่เปิดเพิ่มข้อมูลซ้ำ")
        return "draft"
    built = nrefer_map.build(case["data"], "", 0)
    if not built["ok"]:
        log(cid, built["reason"])
        return "failed"
    token = read_token(page)
    if not token_ok(token):
        raise RuntimeError("session nRefer ไม่พร้อม — login ใหม่ก่อนกรอก")
    hcode = str(jwt_payload(token).get("hcode") or "")
    expected_hcode = CONFIG.get("nrefer_hcode")
    if expected_hcode and hcode != str(expected_hcode):
        raise RuntimeError("หน่วยงานที่ login ไม่ตรงกับ nrefer_hcode ใน config")
    hn, an = built["patient"]["hn"], built["patient"]["an"]
    if not an:
        log(cid, "ไม่มี AN — ตรวจทะเบียนและกรอก AN ใน SSCC ก่อน เพื่อแยกครั้งรักษา")
        return "draft"
    identity = {"hn": hn, "an": an, "hospcode": hcode}
    # Listen before filling: a very early user click cannot escape observation.
    if not db.claim_nrefer(cid):
        log(cid, "มีเคส HN/AN นี้เคยส่งหรือกำลังตรวจอยู่ — ไม่เปิดเพิ่มข้อมูลซ้ำ")
        return "draft"
    no_save = getattr(args, "no_save", False)
    blocked = []
    if no_save:
        # Public HIS client reads its configured base from local_api. No token is exported.
        his_url = page.evaluate("() => localStorage.getItem('local_api') || ''")
        blocked = install_read_only_guard(page.context, args.api_url, his_url=his_url)
        if hasattr(args, "guard_handles"):
            args.guard_handles.append(blocked)
    with SaveObserver(page, args.api_url, identity) as observer:
        try:
            open_add_form(page, ui_url, cid)
            robot_banner(page, "กำลังกรอก nRefer — กรุณารอให้ตรวจค่าครบก่อน", "#b45309")
            log(cid, "ขั้นตอน: กรอกและตรวจค่าฟอร์ม")
            warnings = fill_form(page, nrefer_map.form_values(built), cid)
            warnings = list(dict.fromkeys(built["notes"] + warnings))
            for warning in warnings:
                log(cid, "⚠️ " + warning)
            details = " | ".join(warnings)
            instruction = ("โหมดตรวจฟอร์ม: บล็อกการบันทึก — ตรวจช่องแล้วกดจบรอบนี้ในโปรแกรม"
                           if no_save and getattr(args, "keep_open", False) else
                           "โหมดตรวจฟอร์ม: บล็อกการบันทึก — ตรวจช่องแล้วปิดหน้าต่าง" if no_save else
                           "ตรวจข้อมูลทุกช่องแล้วกดบันทึกเอง")
            robot_banner(page, instruction + (" — " + details if details else ""), "#b45309" if warnings or no_save else "#1a7f37")
            log(cid, instruction)
            if getattr(args, "on_review", None):
                args.on_review()
            if getattr(args, "cancel_check", None):
                ok, ref = observer.wait(REVIEW_WAIT_MS, cancel_check=args.cancel_check)
            else:
                ok, ref = observer.wait(REVIEW_WAIT_MS)
            if ok and not no_save:
                db.set_nrefer(cid, ref or "sent")
                log(cid, "ยืนยัน response บันทึกตรง HN/AN/หน่วยงานแล้ว" + (f" — ref {ref}" if ref else " — เว็บไม่คืน ref ที่ยืนยันได้"))
                return "submitted"
            db.set_nrefer_state(cid, "uncertain" if observer.attempted and not no_save else "draft")
            if no_save:
                log(cid, "จบโหมดตรวจฟอร์ม — คำขอเขียน API ถูกบล็อก")
            else:
                log(cid, "ยังยืนยันผลบันทึกไม่ได้ — ตรวจทะเบียนก่อนลองใหม่" if observer.attempted else "ไม่พบการกดบันทึกในรอบนี้ — จบการกรอก")
            return "draft"
        except Exception:
            if no_save:
                for path in sorted(set(blocked)):
                    log(cid, "โหมดตรวจฟอร์มบล็อก endpoint: " + path)
            db.set_nrefer_state(cid, "uncertain" if observer.attempted and not no_save else "draft")
            raise


def _page_alive(page):
    try:
        page.evaluate("1")
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True, help="เช่น --cases 12,15")
    ap.add_argument("--ui-url", default=NREFER_UI)
    ap.add_argument("--api-url", default=CONFIG.get("nrefer_api_url", "https://nrefer.moph.go.th/api/beta"))
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--no-save", action="store_true", help="ตรวจฟอร์ม: อนุญาตเฉพาะตรวจ session และอ่านข้อมูลตามรายการที่ยืนยันไว้; บล็อกบันทึก")
    args = ap.parse_args()

    ids = list(dict.fromkeys(int(x) for x in args.cases.split(",") if x.strip()))
    if not ids:
        ap.error("ต้องมี case id อย่างน้อยหนึ่งรายการ")
    cases = []
    for i in ids:
        c = db.get_case(i)
        if not c:
            print(f"ไม่พบเคส {i}")
            sys.exit(1)
        cases.append(c)

    is_mock = urlsplit(args.ui_url).hostname in ("127.0.0.1", "localhost", "::1")
    if not is_mock:
        other = runlock.read() or runlock.read_session()
        if other and other.get("pid") != os.getpid():
            for c in cases:
                log(c["id"], "❌ มีการส่ง SSCC/nRefer อีกชุดทำงานค้างอยู่ — รอให้เสร็จแล้วค่อยส่งใหม่")
            sys.exit(5)
        runlock.write({"pid": os.getpid(), "cases": ids, "current": ids[0], "target": "nrefer"})

    sent = 0
    try:
        with sync_playwright() as p:
            if is_mock:
                context = p.chromium.launch(headless=args.headless)
                page = context.new_page(service_workers="block")
            else:
                profile_dir = str(APP_DIR / "data" / "edge_profile")
                context = p.chromium.launch_persistent_context(
                    profile_dir, channel=CONFIG.get("browser_channel", "msedge"),
                    headless=args.headless, no_viewport=True, chromium_sandbox=True, service_workers="block")
                page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(10000)
            log(ids[0], "เปิดเบราว์เซอร์แล้ว — เชื่อม nRefer")
            try:
                token = ensure_login(page, args.ui_url, ids[0])
                hcode = str(jwt_payload(token).get("hcode") or "")
                log(ids[0], f"เชื่อม nRefer สำเร็จ (รพ. {hcode})")
                if args.no_save:
                    log(ids[0], "โหมดตรวจฟอร์ม: บล็อกการเขียน API หลัง login (บางรายการอ้างอิงอาจโหลดไม่ได้)")
                for pos, case in enumerate(cases, 1):
                    cid = case["id"]
                    if len(cases) > 1:
                        log(cid, f"━━ nRefer คิวที่ {pos}/{len(cases)} — เคส #{cid} HN {case.get('hn') or '-'} ━━")
                        if not is_mock:
                            runlock.write({"pid": os.getpid(), "cases": ids, "current": cid, "target": "nrefer"})
                    try:
                        result = process_case(page, args.ui_url, case, args)
                    except Exception as e:
                        log(cid, f"❌ เกิดข้อผิดพลาด: {type(e).__name__} — ตรวจหน้าต่าง nRefer และสถานะเคส")
                        if not _page_alive(page):
                            for rest in cases[pos:]:
                                log(rest["id"], "⏭ ยกเลิก (เบราว์เซอร์ถูกปิด) — ส่งใหม่ได้ทุกเมื่อ")
                            break
                        break  # Don't navigate away from a failed/partial form into the next case.
                    if result == "submitted":
                        sent += 1
                    elif result == "draft" and len(cases) > 1:
                        for rest in cases[pos:]:
                            log(rest["id"], "⏭ ยกเลิก (เคสก่อนหน้าไม่ได้บันทึก) — ส่งใหม่ได้ทุกเมื่อ")
                        break
                if len(cases) > 1:
                    log(cases[-1]["id"], f"🏁 จบคิว nRefer: บันทึกสำเร็จ {sent}/{len(cases)} เคส")
            finally:
                try:
                    context.close()
                except Exception:
                    pass
    except Exception as e:
        log(ids[0], f"❌ เกิดข้อผิดพลาด: {type(e).__name__} — ตรวจหน้าต่าง nRefer")
        sys.exit(6)
    finally:
        if not is_mock:
            runlock.release()
    if sent < len(cases):
        sys.exit(6)


if __name__ == "__main__":
    main()
