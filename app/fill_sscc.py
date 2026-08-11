# -*- coding: utf-8 -*-
"""ตัวกรอกเว็บ SSCC อัตโนมัติ — เปิด Edge ให้พยาบาล login เอง แล้วกรอกให้ทุกฟิลด์
หยุดรอให้ตรวจทานก่อนกดบันทึกจริงเสมอ (ยกเว้น --auto-confirm ซึ่งใช้เฉพาะทดสอบกับ mock)

flow: login (มือ) -> formadd กรอก A1-A6 -> บันทึก -> หา patient_id จาก list
      -> formedit เติมทุกฟิลด์ -> พยาบาลตรวจ + กดบันทึกเอง -> ตรวจจับผลแล้วอัปเดตฐานข้อมูล
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

if sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

import db
import runlock

APP_DIR = Path(__file__).parent
CONFIG = json.loads((APP_DIR / "config.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((APP_DIR / "schema" / "sscc_fields.json").read_text(encoding="utf-8"))

LOGIN_WAIT_MS = 10 * 60 * 1000        # รอ login สูงสุด 10 นาที
REVIEW_WAIT_MS = 60 * 60 * 1000       # รอตรวจทานสูงสุด 60 นาที

# ฟิลด์ในแท็บที่ยังไม่เปิดจะถูกซ่อน (display:none) — ต้องคลิกแท็บก่อนถึงกรอกได้
SECTION_TAB_INDEX = {"A": 0, "A7": 1, "B": 2, "C1": 3, "C2": 4, "D": 5, "E": 6, "F": 7}


def activate_tab(page, section):
    idx = SECTION_TAB_INDEX.get(section)
    if idx is None:
        return
    tabs = page.locator(".nav-tabs a")
    if tabs.count() > idx:
        tabs.nth(idx).click()
        page.wait_for_timeout(200)


def verify_and_refill(page, data, case_id, warnings):
    """ตรวจ select/text ทุกตัวว่าค่าใน DOM ตรงกับที่ตั้งใจ ถ้าไม่ตรงเติมใหม่ (กัน JS เว็บรีเซ็ต)
    คืนรายชื่อฟิลด์ที่ต้องเติมซ้ำ"""
    fields = {f["sscc"]: f for f in SCHEMA["fields"]}
    refixed = []
    for name, want in data.items():
        f = fields.get(name)
        if not f or f["type"] in ("checkbox-group",) or f.get("special"):
            continue
        el = page.locator(f'[name="{name}"]').first
        if not el.count():
            continue
        try:
            cur = el.input_value()
        except Exception:
            continue
        expect = want
        if f["type"] == "date":
            expect = to_sscc_date(str(want))
        elif f["type"] == "time":
            expect = to_sscc_time(str(want))
        if str(cur) != str(expect):
            page.wait_for_timeout(150)
            if fill_field(page, f, want, case_id, warnings):
                refixed.append(name)
    return refixed


def submit_and_wait(page, base_url, case_id, expect_re, timeout_ms=45000):
    """กดปุ่มบันทึกแล้วรอ URL เปลี่ยนไปหน้าที่คาด — คืน URL ปลายทาง หรือ None ถ้าถูก validation บล็อก
    (SSCC เป็น PHPMaker: บันทึกสำเร็จจะเด้งไปหน้า formedit/ฟอร์มลิสต์)"""
    before = page.url
    try:
        page.locator('button[type="submit"]').first.click()
    except Exception as e:
        log(case_id, f"กดปุ่มบันทึกไม่ได้: {str(e)[:80]}")
        return None
    try:
        page.wait_for_url(re.compile(expect_re), timeout=timeout_ms, wait_until="domcontentloaded")
        return page.url
    except PWTimeout:
        if page.url != before:  # navigate ไปแล้วแต่ไม่ตรง pattern
            return page.url
        # ยังอยู่หน้าเดิม — น่าจะติด validation; เก็บ error บนหน้าไปแจ้ง
        errs = page.evaluate("""() => Array.from(document.querySelectorAll('.ewError, .has-error, .invalid-feedback'))
            .filter(e => e.offsetParent && e.textContent.trim()).map(e => e.textContent.trim()).slice(0, 6)""")
        if errs:
            log(case_id, "SSCC ฟ้อง: " + " | ".join(errs))
        return None


def log(case_id, msg):
    print(msg, flush=True)
    try:
        db.append_log(case_id, msg)
    except Exception:
        pass


def to_sscc_date(v):
    """ISO yyyy-mm-dd -> dd/mm/yyyy (ค.ศ.) / ถ้าเป็น dd/mm/yyyy อยู่แล้วก็ปล่อยผ่าน"""
    if not v:
        return v
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", v)
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else v


def to_sscc_time(v):
    return f"{v}:00" if v and re.match(r"^\d{2}:\d{2}$", v) else v


def open_add_form(page, base_url, case_id):
    """เปิดหน้าเพิ่มเคสให้พร้อมกรอก (x_a2 โผล่) — ถ้ายังไม่ได้ login จะรอผู้ใช้ login แล้วลองใหม่
    session ค้างในโปรไฟล์ Edge เลยปกติ login ครั้งเดียวใช้ได้ทั้งวัน"""
    add_url = f"{base_url}/stroke_formadd.php?showdetail="
    told_login = False
    import time
    deadline = time.time() + LOGIN_WAIT_MS / 1000
    while time.time() < deadline:
        try:
            page.goto(add_url, wait_until="domcontentloaded", timeout=30000)
        except PWTimeout:
            continue
        try:
            page.wait_for_selector('[name="x_a2"]', timeout=5000)
            if told_login:
                log(case_id, "login สำเร็จ")
            return
        except PWTimeout:
            pass
        # ยังกรอกไม่ได้ — ดูว่าโดนเด้งไป login หรือหน้าโหลดช้า
        url, title = page.url, page.title()
        has_login = page.locator('input[type="password"]').count() > 0 or "login" in url.lower()
        if has_login:
            if not told_login:
                log(case_id, "กรุณา login ด้วยบัญชีของท่านในหน้าต่าง Edge (โปรแกรมไม่บันทึกรหัสผ่าน)")
                told_login = True
            try:
                page.wait_for_function(
                    "() => !document.querySelector('input[type=password]')",
                    timeout=LOGIN_WAIT_MS)
            except PWTimeout:
                pass
        else:
            log(case_id, f"หน้ายังไม่พร้อม (url={url[:60]} title={title[:40]}) — ลองใหม่")
            page.wait_for_timeout(2000)
    raise RuntimeError("เปิดหน้าเพิ่มเคสไม่สำเร็จภายในเวลาที่กำหนด (login ค้างหรือเว็บช้า)")


def fill_field(page, field, value, case_id, warnings):
    name = field["sscc"]
    ftype = field["type"]
    sel = f'[name="{name}"]'
    try:
        if ftype == "checkbox-group":
            for v in (value if isinstance(value, list) else [value]):
                cb = page.locator(f'{sel}[value="{v}"]').first
                if cb.count() and not field.get("check_by_label"):
                    cb.check()
                    continue
                # เลือกตามข้อความที่แสดง (จำเป็นกับ E2 ที่ value/label ของเว็บเหลื่อมกัน)
                lab = page.locator(f'label:has(input[name="{name}"])').filter(
                    has_text=re.compile(re.escape(v))).first
                if lab.count():
                    if not lab.locator("input").is_checked():
                        lab.click()
                elif cb.count():
                    cb.check()
                else:
                    warnings.append(f"{name}: ไม่พบ checkbox '{v}'")
            return True
        if field.get("special") == "drug_lookup":
            # ช่องยาเป็น hidden เก็บ "รหัสยา" + span แสดงชื่อ (แมปรหัสไว้ใน schema/drug_map.json)
            display = next((o["t"] for o in field.get("options", []) if o["v"] == str(value)), None)
            if display is None:
                warnings.append(f"{name}: ไม่รู้จักรหัสยา '{value}' — เลือกผ่านปุ่มค้นหาบนเว็บตอนตรวจทาน")
                return False
            page.evaluate(
                """([name, val, disp]) => {
                    const h = document.querySelector(`[name="${name}"]`);
                    if (h) { h.value = val; h.dispatchEvent(new Event('change', {bubbles: true})); }
                    const lu = document.getElementById('lu_' + name);
                    if (lu) lu.textContent = disp;
                }""", [name, str(value), display])
            return True
        el = page.locator(sel).first
        if not el.count():
            warnings.append(f"{name}: ไม่พบฟิลด์บนหน้าเว็บ")
            return False
        if ftype == "select" and not field.get("special") == "cascade_hospital":
            try:
                el.select_option(value=str(value), timeout=5000)
            except Exception:
                try:
                    el.select_option(label=str(value), timeout=3000)
                except Exception:
                    # บาง select ถูก JS ของเว็บล้าง/สร้าง option ใหม่ตามฟิลด์อื่น (เช่น B5 → B6)
                    # รอสั้นๆ ให้ option กลับมาแล้วลองอีกรอบ ก่อนยอมแพ้
                    page.wait_for_timeout(1500)
                    try:
                        el.select_option(value=str(value), timeout=3000)
                    except Exception:
                        el.select_option(label=str(value), timeout=3000)
        elif field.get("special") == "cascade_hospital":
            # รอ AJAX โหลดรายชื่อ รพ. ตามจังหวัดก่อน แล้วเลือกจากชื่อ
            page.wait_for_function(
                f"""() => document.querySelector('[name="{name}"]')?.options.length > 1""",
                timeout=15000)
            target = str(value).strip()
            try:
                el.select_option(label=target)
            except Exception:
                opts = el.evaluate("e => Array.from(e.options).map(o => o.text.trim())")
                match = next((o for o in opts if target and (target in o or o in target)), None)
                if match:
                    el.select_option(label=match)
                else:
                    warnings.append(f"{name}: ไม่พบ รพ. ชื่อ '{target}' ในรายการ — เลือกเองตอนตรวจทาน")
                    return False
        elif ftype in ("date", "time"):
            # ช่องวันที่/เวลาของ SSCC เป็น readonly + มี date/time-picker → fill() ค้าง
            # ตั้งค่าตรงผ่าน JS (พิสูจน์แล้วว่าค่าคงอยู่ตอนบันทึกจริง)
            v = to_sscc_date(str(value)) if ftype == "date" else to_sscc_time(str(value))
            el.evaluate("(e, val) => { e.value = val; e.dispatchEvent(new Event('change', {bubbles: true})); }", v)
        else:
            el.fill(str(value))
        return True
    except PWTimeout:
        warnings.append(f"{name}: หมดเวลารอ (AJAX?) — เลือกเองตอนตรวจทาน")
        return False
    except Exception as e:
        warnings.append(f"{name}: {type(e).__name__} {str(e)[:80]}")
        return False


def robot_banner(page, text, color="#b45309"):
    """แถบบอกสถานะบนหน้าเว็บ SSCC — กันพยาบาลคลิก/ปิดหน้าต่างระหว่างโปรแกรมกำลังกรอก
    (เป็นแค่ DOM ฝั่งแสดงผล ไม่มีชื่อฟิลด์ ไม่ติดไปกับการบันทึก; หายเองเมื่อเปลี่ยนหน้า)"""
    try:
        page.evaluate(
            """([t, c]) => {
                let b = document.getElementById('sscc_robot_banner');
                if (!b) {
                    b = document.createElement('div');
                    b.id = 'sscc_robot_banner';
                    document.body.prepend(b);
                    document.body.style.paddingTop = '44px';
                }
                b.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;' +
                    'background:' + c + ';color:#fff;font:600 16px/1.4 sans-serif;' +
                    'padding:10px 16px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.25)';
                b.textContent = t;
            }""", [text, color])
    except Exception:
        pass


def fill_edit_page(page, base_url, pid, data, case_id):
    """เปิดหน้าแก้ไขแล้วเติมทุกฟิลด์ — คืน ("ok"|"no_page"|"unstable", warnings)
    ถ้าหน้าเว็บถูกเปลี่ยนไประหว่างกรอก (มีคนคลิก/เว็บเด้งออก) ค่าที่กรอกไว้จะหายทั้งหน้า
    → เปิดหน้าแก้ไขใหม่แล้วกรอกซ้ำตั้งแต่ต้นให้เอง สูงสุด 3 รอบ (บทเรียนจากหน้างานจริง 2026-08)"""
    for attempt in range(1, 4):
        warnings = []
        try:
            page.goto(f"{base_url}/stroke_formedit.php?showdetail=&patient_id={pid}",
                      wait_until="domcontentloaded")
            page.wait_for_selector('[name="x_a2"]', timeout=30000)
        except PWTimeout:
            return "no_page", [f"เปิดหน้าแก้ไขเคสเลขที่ {pid} ไม่ได้ (เคสอาจถูกลบจากเว็บ)"]
        robot_banner(page, "🤖 โปรแกรมกำลังกรอกข้อมูลอัตโนมัติ — อย่าเพิ่งคลิกหรือปิดหน้าต่างนี้")
        filled = 0
        current_section = None
        disturbed = False
        for f in SCHEMA["fields"]:
            v = data.get(f["sscc"])
            if v in (None, "", []):
                continue
            if "stroke_formedit" not in page.url:
                disturbed = True
                break
            if f["section"] != current_section:
                current_section = f["section"]
                activate_tab(page, current_section)
            if fill_field(page, f, v, case_id, warnings):
                filled += 1
        if not disturbed and "stroke_formedit" in page.url:
            # รอบตรวจซ้ำ: บาง select ถูก JS ของเว็บรีเซ็ต (เช่น B5 First Dx รีเซ็ต B6 Final Dx)
            refixed = verify_and_refill(page, data, case_id, warnings)
            if refixed:
                log(case_id, f"เติมซ้ำฟิลด์ที่ถูกรีเซ็ต: {', '.join(refixed)}")
            if "stroke_formedit" in page.url:
                activate_tab(page, "A")  # กลับแท็บแรกให้พยาบาลเริ่มตรวจ
                note = f" (กรอกรอบที่ {attempt})" if attempt > 1 else ""
                log(case_id, f"ขั้นที่ 3/3: เติมข้อมูลแล้ว {filled} ฟิลด์{note}")
                for w in warnings:
                    log(case_id, f"⚠️ {w}")
                return "ok", warnings
        log(case_id, f"⚠️ หน้าเว็บถูกเปลี่ยนไประหว่างกรอก (มีการคลิกในหน้าต่าง Edge?) — "
                     f"เปิดหน้าแก้ไขใหม่แล้วกรอกซ้ำ (รอบ {attempt}/3)")
    return "unstable", warnings


def find_patient_id(page, base_url, hn, case_id):
    """หา patient_id ของเคสที่เพิ่งสร้าง: เรียง list ใหม่→เก่า แล้วหาแถวที่ HN ตรง
    (ตรวจกับเว็บจริงแล้ว 2026-07-13: ?order=patient_id&ordertype=DESC ใช้ได้ / psearch กรองไม่ได้จริง)"""
    if "patient_id=" in page.url:
        return re.search(r"patient_id=(\d+)", page.url).group(1)
    page.goto(f"{base_url}/stroke_formlist.php?order=patient_id&ordertype=DESC")
    page.wait_for_load_state("networkidle")
    links = page.locator('a[href*="stroke_formedit.php"]')
    for i in range(min(links.count(), 30)):
        href = links.nth(i).get_attribute("href") or ""
        m = re.search(r"patient_id=(\d+)", href)
        if not m:
            continue
        row_text = links.nth(i).evaluate("a => a.closest('tr')?.innerText || ''")
        if hn and hn in row_text:
            return m.group(1)  # แถวแรกที่ HN ตรง = เคสใหม่สุด
    return None


def _page_alive(page):
    try:
        return not page.is_closed()
    except Exception:
        return False


def process_case(page, base_url, case, args, queue_mode):
    """กรอกหนึ่งเคสจนจบ (สร้าง → เติมทุกแท็บ → รอพยาบาลตรวจและบันทึก)
    คืนสถานะ: submitted | draft (ออกโดยไม่บันทึก) | failed (ข้าม) | timeout (รอเกินเวลา)"""
    cid = case["id"]
    data = case["data"]
    hn = (data.get("x_a2") or "").strip()

    # เคยสร้างบนเว็บไปแล้ว (จากรอบที่ส่งไม่จบ) → เปิดเคสเดิม ไม่สร้างซ้ำ
    pid = str(case.get("sscc_patient_id") or "").strip() or None
    reused = bool(pid)
    if reused:
        log(cid, f"เคสนี้เคยถูกสร้างบนเว็บแล้ว (เลขที่ผู้ป่วย {pid}) — เปิดกรอกต่อที่เคสเดิม ไม่สร้างซ้ำ")
        if case.get("status") == "submitted":
            log(cid, "🔧 โหมดเติมให้ครบ: โปรแกรมจะเติมทุกช่องตามข้อมูลในโปรแกรมทับของเดิม "
                     "— ตรวจทานแล้วกด [บันทึก] อีกครั้งเพื่อให้เว็บได้ข้อมูลครบ")

    fill_status = None
    warnings = []
    for round_ in (1, 2):
        if not pid:
            # ---- ขั้นที่ 1: สร้างเคส (A1-A6) ----
            open_add_form(page, base_url, cid)
            robot_banner(page, "🤖 โปรแกรมกำลังสร้างเคสใหม่อัตโนมัติ — อย่าเพิ่งคลิกหรือปิดหน้าต่างนี้")
            log(cid, "ขั้นที่ 1/3: สร้างเคสใหม่ (A1-A6)")
            add_fields = [f for f in SCHEMA["fields"] if f.get("on_add_page")]
            for f in add_fields:
                v = data.get(f["sscc"])
                if v not in (None, "", []):
                    fill_field(page, f, v, cid, warnings)
            # บันทึกสำเร็จ SSCC จะพาไปหน้า formedit ของเคสใหม่ทันที (มี patient_id ใน URL)
            dest = submit_and_wait(page, base_url, cid, r"stroke_form(edit|list)\.php")
            if not dest:
                if queue_mode:
                    log(cid, "❌ บันทึก A1-A6 ไม่สำเร็จ — ข้ามเคสนี้ไว้ส่งเดี่ยวทีหลัง")
                    return "failed"
                log(cid, "❌ บันทึก A1-A6 ไม่สำเร็จ (ดูข้อความ SSCC ด้านบน) — แก้บนหน้าเว็บแล้วบันทึกเองได้")
                if not args.headless:
                    page.wait_for_timeout(REVIEW_WAIT_MS)
                sys.exit(3)
            log(cid, "บันทึก A1-A6 แล้ว")

            # ---- ขั้นที่ 2: หาเลขเคสที่เพิ่งสร้าง แล้วจำไว้ทันที (ส่งซ้ำจะไม่สร้างใหม่) ----
            pid = find_patient_id(page, base_url, hn, cid)
            if not pid:
                if queue_mode:
                    log(cid, "❌ หาเคสที่เพิ่งสร้างไม่เจอ — ข้ามเคสนี้ (เคสอาจถูกสร้างบนเว็บแล้ว ตรวจหน้า list ที)")
                    return "failed"
                log(cid, "❌ หาเคสที่เพิ่งสร้างไม่เจอ — เปิดหน้า list ให้ตรวจสอบเอง (เคสอาจถูกสร้างแล้ว)")
                if not args.headless:
                    page.wait_for_timeout(REVIEW_WAIT_MS)
                sys.exit(3)
            db.set_draft_pid(cid, pid)
            log(cid, f"ขั้นที่ 2/3: ได้เลขที่ผู้ป่วย SSCC = {pid}")

        # ---- ขั้นที่ 3: เติมข้อมูลทุกแท็บ (เปิดใหม่+กรอกซ้ำเองถ้าหน้าถูกรบกวน) ----
        fill_status, warnings = fill_edit_page(page, base_url, pid, data, cid)
        if fill_status == "ok":
            break
        if fill_status == "no_page" and reused and round_ == 1:
            # เคสเดิมบนเว็บหายไป (ถูกลบ?) — ล้างเลขที่จำไว้แล้วสร้างใหม่รอบเดียว
            log(cid, f"⚠️ เปิดเคสเดิม (เลขที่ {pid}) ไม่ได้ — จะสร้างเคสใหม่บนเว็บแทน")
            pid = None
            db.set_draft_pid(cid, None)
            reused = False
            continue
        break
    if fill_status != "ok":
        for w in warnings:
            log(cid, f"⚠️ {w}")
        msg = ("หน้าเว็บถูกรบกวนซ้ำหลายรอบระหว่างกรอก" if fill_status == "unstable"
               else "เปิดหน้าแก้ไขบนเว็บไม่ได้")
        if queue_mode:
            log(cid, f"❌ {msg} — ข้ามเคสนี้ (เคสยังเป็นร่าง ส่งใหม่ได้ จะเปิดเคสเดิมไม่สร้างซ้ำ)")
            return "failed"
        log(cid, f"❌ {msg} — เคสยังเป็นร่าง ส่งใหม่ได้ทุกเมื่อ")
        if not args.headless:
            page.wait_for_timeout(REVIEW_WAIT_MS)
        sys.exit(3)

    if args.auto_confirm:
        dest = submit_and_wait(page, base_url, cid, r"stroke_form(view|list)\.php")
        if dest:
            db.set_submitted(cid, pid, (case.get("fill_log") or "") + "auto-confirm (mock test)")
            log(cid, f"✅ (mock) บันทึกอัตโนมัติสำเร็จ — patient_id {pid}")
            return "submitted"
        log(cid, "❌ (mock) บันทึกไม่สำเร็จ")
        if queue_mode:
            return "failed"
        sys.exit(4)

    # ---- รอพยาบาลตรวจทานและกดบันทึกเอง ----
    robot_banner(page, f"🔍 กรอกเสร็จแล้ว — ตรวจทานทุกแท็บ แล้วกดปุ่ม [บันทึก] ท้ายฟอร์ม (HN {hn})",
                 color="#1a7f37")
    log(cid, "🔍 โปรดตรวจทานทุกแท็บบนหน้าเว็บ แล้วกดปุ่ม [บันทึก] ที่ท้ายฟอร์ม")
    posted = {"flag": False}

    def _nav(fr):
        if fr is page.main_frame and "stroke_formview" in fr.url:
            posted["flag"] = True

    page.on("framenavigated", _nav)
    try:
        # บันทึกสำเร็จบนหน้าแก้ไข -> เด้งไป stroke_formview.php (ยืนยันจาก pilot จริง 2026-07-13)
        page.wait_for_url(re.compile(r"stroke_form(view|list)\.php"), timeout=REVIEW_WAIT_MS)
    except PWTimeout:
        log(cid, "หมดเวลารอตรวจทาน (60 นาที) — เคสยังเป็นร่าง ส่งใหม่ได้ทุกเมื่อ (จะเปิดเคสเดิมบนเว็บ ไม่สร้างซ้ำ)")
        return "timeout"
    finally:
        try:
            page.remove_listener("framenavigated", _nav)
        except Exception:
            pass
    if posted["flag"]:
        db.set_submitted(cid, pid, case.get("fill_log") or "")
        log(cid, f"✅ ส่งเข้า SSCC สำเร็จ — เลขที่ผู้ป่วย {pid}")
        return "submitted"
    log(cid, "ออกจากหน้าแก้ไขโดยไม่ได้กดบันทึก — เคสยังเป็นร่าง ข้อมูลในโปรแกรมอยู่ครบ "
             "(ส่งใหม่ได้ทุกเมื่อ จะเปิดเคสเดิมบนเว็บ ไม่สร้างซ้ำ)")
    return "draft"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=int, help="ส่งเคสเดียว")
    ap.add_argument("--cases", help="ส่งหลายเคสต่อกันเป็นคิว เช่น --cases 12,15,18")
    ap.add_argument("--base-url", default=CONFIG["sscc_base_url"])
    ap.add_argument("--auto-confirm", action="store_true", help="กดบันทึกเองอัตโนมัติ (เฉพาะทดสอบ mock)")
    ap.add_argument("--headless", action="store_true", help="ไม่โชว์หน้าต่าง (เฉพาะทดสอบ mock)")
    args = ap.parse_args()

    ids = []
    if args.case:
        ids.append(args.case)
    if args.cases:
        ids += [int(x) for x in args.cases.split(",") if x.strip()]
    if not ids:
        print("ต้องระบุ --case หรือ --cases")
        sys.exit(1)

    cases = []
    for i in ids:
        c = db.get_case(i)
        if not c:
            print(f"ไม่พบเคส {i}")
            sys.exit(1)
        cases.append(c)

    queue_mode = len(cases) > 1
    is_mock = "127.0.0.1" in args.base_url or "localhost" in args.base_url
    if args.auto_confirm and not is_mock:
        print("--auto-confirm ใช้ได้เฉพาะกับ mock (127.0.0.1) เท่านั้น — ยกเลิก")
        sys.exit(2)

    # กันรันซ้อน: โปรไฟล์ Edge เปิดพร้อมกันสองตัวไม่ได้ (mock ใช้เบราว์เซอร์ชั่วคราว ไม่ต้องล็อก)
    if not is_mock:
        other = runlock.read()
        if other and other.get("pid") != os.getpid():
            for c in cases:
                log(c["id"], "❌ มีการส่งเข้า SSCC อีกชุดทำงานค้างอยู่ — รอให้เสร็จ (ดูหน้าต่าง Edge) แล้วค่อยส่งใหม่")
            sys.exit(5)
        runlock.write({"pid": os.getpid(), "cases": ids, "current": ids[0]})

    exit_code = 0
    sent = 0
    try:
        with sync_playwright() as p:
            if is_mock:
                context = p.chromium.launch(headless=args.headless)
                page = context.new_page()
            else:
                # โปรไฟล์ถาวร -> session login ค้างไว้ ไม่ต้อง login ใหม่ทุกเคส
                profile_dir = str(APP_DIR / "data" / "edge_profile")
                context = p.chromium.launch_persistent_context(
                    profile_dir, channel=CONFIG.get("browser_channel", "msedge"),
                    headless=args.headless, no_viewport=True)
                page = context.pages[0] if context.pages else context.new_page()
            # ยอมรับ dialog อัตโนมัติ (ค่าเริ่มต้นของ Playwright คือกด "ยกเลิก" ซึ่งจะยกเลิกการบันทึก)
            page.on("dialog", lambda d: d.accept())
            # ฟิลด์ที่มีปัญหาไม่ควรค้างนาน 30 วิ (ค่าเริ่มต้น Playwright) — 10 วิพอ แล้วไปตัวถัดไป
            page.set_default_timeout(10000)
            log(ids[0], "เปิดเบราว์เซอร์แล้ว")
            try:
                for pos, case in enumerate(cases, 1):
                    cid = case["id"]
                    if queue_mode:
                        log(cid, f"━━ คิวที่ {pos}/{len(cases)} — เคส #{cid} HN {case.get('hn') or '-'} ━━")
                        if not is_mock:
                            runlock.write({"pid": os.getpid(), "cases": ids, "current": cid})
                    if queue_mode:
                        try:
                            result = process_case(page, args.base_url, case, args, queue_mode)
                        except SystemExit:
                            raise
                        except Exception as e:
                            log(cid, f"❌ เกิดข้อผิดพลาด: {type(e).__name__}: {str(e)[:200]}")
                            if not _page_alive(page):
                                for rest in cases[pos:]:
                                    log(rest["id"], "⏭ ยกเลิก (เบราว์เซอร์ถูกปิดก่อนถึงคิว) — เคสยังเป็นร่าง ส่งใหม่ได้")
                                raise
                            continue
                    else:
                        result = process_case(page, args.base_url, case, args, queue_mode)
                    if result == "submitted":
                        sent += 1
                    elif result == "timeout" and queue_mode:
                        # พยาบาลค้างที่เคสนี้เกินเวลา — ไม่เด้งไปเคสถัดไปเอง (กันสับสน)
                        for rest in cases[pos:]:
                            log(rest["id"], "⏭ ยกเลิก (เคสก่อนหน้าค้างเกินเวลา) — เคสยังเป็นร่าง ส่งใหม่ได้")
                        break
                if queue_mode:
                    log(cases[-1]["id"], f"🏁 จบคิว: ส่งสำเร็จ {sent}/{len(cases)} เคส")
                    if sent < len(cases):
                        exit_code = 6
            finally:
                try:
                    context.close()
                except Exception:
                    pass
    except Exception as e:
        log(ids[0], f"❌ เกิดข้อผิดพลาด: {type(e).__name__}: {str(e)[:200]}")
        raise
    finally:
        if not is_mock:
            runlock.release()
        # อัปเดต Excel ครั้งเดียวตอนจบ (ไฟล์ใหญ่ เขียนราว 15 วิ — ไม่ทำระหว่างคิวให้เคสถัดไปรอ)
        if sent:
            try:
                import excel_export
                excel_export.export_master()
                log(ids[0], "อัปเดตไฟล์ Excel แล้ว")
            except Exception as e:
                log(ids[0], f"⚠️ อัปเดต Excel ไม่สำเร็จ ({type(e).__name__}) — กด 'สร้าง Excel ใหม่' ที่หน้ารวมได้")
    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
