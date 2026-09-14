"""UI contract observed on nRefer 5.0.8, 2026-09-09. Never clicks Save."""
import re
import os
from contextlib import contextmanager
from datetime import date
from playwright.sync_api import expect

FIELD_LABELS = {
    "hn": "HN", "an": "AN", "person_id": "เลขบัตรประชาชน", "vn": "VN",
    "prename": "คำนำหน้า", "fname": "ชื่อ", "lname": "นามสกุล", "tel": "โทรศัพท์",
    "age[2]": "อายุปี", "age[1]": "อายุเดือน", "los": "LOS", "sbp": "ความดันตัวบน", "dbp": "ความดันตัวล่าง",
    "dx": "Diagnosis", "dmis": "กลุ่มโรค", "carry": "ผู้นำส่ง", "visit_result": "ผลจำหน่าย",
    "sex": "เพศ", "rtpa": "rt-PA", "ctscan": "CT Scan", "stroke_unit": "Stroke Unit", "surgery": "ผ่าตัด",
    "ill_time": "วันเวลาเริ่มอาการ", "arrival_time": "วันเวลาถึง รพ.แรก", "admit_time": "วันเวลารับไว้",
    "disc_time": "วันเวลาจำหน่าย", "rtpa_time": "วันเวลา rt-PA", "ctscan_time": "วันเวลาทำ CT",
    "stroke_unit_time": "วันเวลาเข้า Stroke Unit", "surgery_start_time": "วันเวลาเริ่มผ่าตัด",
    "surgery_end_time": "วันเวลาสิ้นสุดผ่าตัด", "birth": "วันเกิด",
    "gcs_eye": "GCS Eye", "gcs_verbal": "GCS Verbal", "gcs_motor": "GCS Motor",
}


def label_for(name):
    return FIELD_LABELS.get(name.removeprefix("editRow."), name)


@contextmanager
def form_load_barrier(page):
    """Subscribe before navigation/click so in-flight initialization is not missed."""
    pending = set()
    def started(req):
        if req.resource_type in ('xhr', 'fetch'):
            pending.add(req)
    def finished(req):
        pending.discard(req)
    def wait():
        quiet = 0
        for _ in range(120):
            page.wait_for_timeout(250)
            quiet = 0 if pending else quiet + 1
            if quiet >= 4:
                return
        raise RuntimeError('ฟอร์ม nRefer ยังโหลดอยู่ — หยุดก่อนกรอกข้อมูล')
    page.on('request', started)
    page.on('requestfinished', finished)
    page.on('requestfailed', finished)
    try:
        yield wait
    finally:
        page.remove_listener('request', started)
        page.remove_listener('requestfinished', finished)
        page.remove_listener('requestfailed', finished)


def fill_input(page, name, value):
    loc = page.locator(f'input[name="{name}"]')
    if name in ("editRow.gcs_eye", "editRow.gcs_verbal", "editRow.gcs_motor"):
        # Live UI: fill + Tab changes the inputs but leaves the total stale.
        loc.click()
        loc.press("ControlOrMeta+A")
        if value:
            loc.press_sequentially(value)
        else:
            loc.press("Backspace")
    else:
        loc.fill(value)
    loc.press("Tab")


def date_input(page, name):
    if name == "birth":
        return page.locator("xpath=//label[contains(normalize-space(.),'วันเกิด')]/following::pk-datepicker[1]//input")
    return page.locator(f'input[name="{name}"]').locator(
        "xpath=preceding-sibling::pk-datepicker[1]//input")


def normalized_date(value):
    value = value.strip()
    if not value:
        return ""
    if "/" in value:
        d, m, y = map(int, value.split("/"))
        return date(y - 543 if y > 2400 else y, m, d).isoformat()
    return date.fromisoformat(value).isoformat()


def set_date(page, name, iso):
    """Type like a user, blur, and prove the calendar selected the requested date."""
    loc = date_input(page, name)
    host = loc.locator("xpath=ancestor::pk-datepicker[1]")
    if not iso and not loc.is_enabled():
        if loc.input_value():
            raise ValueError("ช่องวันที่ถูกล็อกแต่มีค่าค้าง")
        return
    expect(loc).to_be_enabled()
    if not iso:
        loc.click()
        host.get_by_role("button", name="ลบ", exact=True).click()
        expect(loc).to_have_value("")
        return
    target = date.fromisoformat(iso)
    year = target.year + 543
    loc.click()
    loc.press("ControlOrMeta+A")
    loc.press_sequentially(f"{target.day:02d}/{target.month:02d}/{year}")
    loc.press("Tab")
    page.locator('input[name="editRow.hn"]').click()
    if normalized_date(loc.input_value()) != iso:
        raise ValueError("วันที่แสดงไม่ตรง")
    loc.click()
    selected = host.locator(".days button.selected:not(.other-month)")
    expect(selected).to_have_text(re.compile(rf"^\s*{target.day}\s*$"))
    # Old birth years are valid but absent from the fixed year dropdown.
    expect(host.locator(".month-year-display")).to_have_text(re.compile(rf"\s{year}$"))
    expect(host.locator(".calendar-header select").nth(0)).to_have_value(str(target.month - 1))
    page.locator('input[name="editRow.hn"]').click()


def pk_field(page, key):
    if key == "ward":
        return page.locator('input[name="editRow.ward"]').locator("xpath=following-sibling::pk-select[1]")
    label = "แรกรับรักษา" if key == "before" else "ก่อนการจำหน่าย"
    return page.locator(f"xpath=//span[contains(normalize-space(.),'{label}')]/following-sibling::pk-select[1]")


def pick(page, key, value):
    sel = pk_field(page, key)
    sel.locator(".pk-select-trigger").click()
    options = sel.locator(".pk-select-option")
    expect(options.first).to_be_visible()
    labels = options.all_text_contents()
    matches = []
    for index, label in enumerate(labels):
        label = label.strip()
        match = (label == value or label.rsplit(",", 1)[0].strip() == value) if key == "ward" else label.startswith(value + ".")
        if match:
            matches.append(index)
    if len(matches) != 1:
        sel.locator(".pk-select-trigger").click()
        raise ValueError("ไม่พบตัวเลือกที่ตรงเพียงรายการเดียว")
    chosen = labels[matches[0]].strip()
    options.nth(matches[0]).click()
    expect(sel.locator(".pk-select-value")).to_have_text(chosen)
    if key == "ward":
        expect(page.locator('input[name="editRow.ward"]')).to_have_value(chosen.rsplit(",", 1)[-1].strip())


def fill_form(page, fv, case_id=None):
    warnings = []
    def trace_identity(stage):
        if os.environ.get("SSCC_NREFER_TRACE") != "1":
            return
        result = []
        for key in ("hn", "an"):
            name = "editRow." + key
            actual = page.locator(f'input[name="{name}"]').input_value()
            result.append(key + "=" + ("ตรง" if actual == fv["text"][name] else "ว่าง" if not actual else "เปลี่ยน"))
        print("ตรวจ identity หลัง " + stage + ": " + ", ".join(result), flush=True)
    def attempt(label, action):
        try:
            action()
        except Exception as exc:
            # Don't put browser exception dumps (potential patient values) in local logs.
            warnings.append(f"{label_for(label)}: กรอก/ตรวจค่าไม่สำเร็จ — ตรวจเอง")

    # Readiness is driven by outstanding requests, not a fixed HIS delay.
    pending = set()
    def started(req):
        if req.resource_type in ("xhr", "fetch"):
            pending.add(req)
    def finished(req):
        pending.discard(req)
    page.on("request", started)
    page.on("requestfinished", finished)
    page.on("requestfailed", finished)
    def wait_his():
        quiet = 0
        for _ in range(120):
            page.wait_for_timeout(250)
            quiet = 0 if pending else quiet + 1
            if quiet >= 4:
                return
        raise RuntimeError("HIS ยังโหลดข้อมูลอยู่ — หยุดเพื่อป้องกันค่าถูกทับ")
    try:
        for name in ("editRow.hn", "editRow.an"):
            loc = page.locator(f'input[name="{name}"]')
            loc.fill(fv["text"][name])
            loc.press("Tab")
            wait_his()
            if loc.input_value() != fv["text"][name]:
                raise RuntimeError(label_for(name) + ': เว็บเปลี่ยนค่าหลังค้นข้อมูล — หยุดตรวจ ไม่กรอกต่อ')
            trace_identity(name)
        for name in ("editRow.hn", "editRow.an"):
            if page.locator(f'input[name="{name}"]').input_value() != fv['text'][name]:
                raise RuntimeError('HN/AN ไม่ตรงหลังค้นข้อมูล — หยุดตรวจ ไม่กรอกต่อ')
        trace_identity("รอ HIS")

        # Dx is the only editable disease control; Group is derived and disabled.
        dx = page.locator('select[name="editRow.dx"]')
        dx.select_option(fv["select"]["editRow.dx"])
        expect(page.locator('select[name="editRow.dmis"]')).to_have_value(fv["select"]["editRow.dmis"])
        trace_identity("Dx")
        for name, val in fv["select"].items():
            if name in ("editRow.dx", "editRow.dmis"):
                continue
            if val is None:
                warnings.append(f"{label_for(name)}: ต้นทางไม่ระบุ — ค่าเริ่มต้นของเว็บอาจไม่ถูก ต้องเลือกเอง")
                continue
            attempt(name, lambda n=name, v=val: page.locator(f'select[name="{n}"]').select_option(str(v)))
        for name, val in fv["text"].items():
            if name in ("editRow.hn", "editRow.an"):
                continue
            # Explicitly replace stale HIS text, including fields absent in source.
            attempt(name, lambda n=name, v=val: fill_input(page, n, str(v or "")))
            trace_identity(name)
        for name, val in fv["radio"].items():
            if val == "":
                warnings.append(f"{label_for(name)}: ไม่ทราบ — ตรวจค่าที่เว็บแสดง")
                continue
            attempt(name, lambda n=name, v=val: page.locator(f'input[id="{n}{v}"]').check())
        # Commit calendar dates before setting times; date events can reset times.
        for name, value in fv["date"].items():
            attempt(name, lambda n=name, v=value: set_date(page, n, v))
            trace_identity("วันที่ " + name)
        for name, value in fv["time"].items():
            if value or page.locator(f'input[name="{name}"]').is_enabled():
                attempt(name, lambda n=name, v=value: fill_input(page, n, v))
        for key, value in fv["mrs"].items():
            if value != "":
                attempt("mRS " + key, lambda k=key, v=value: pick(page, k, v))
            else:
                warnings.append("mRS " + key + ": ไม่มีข้อมูล — ตรวจ/เลือกเอง")
        if fv["ward_name"]:
            attempt("Ward", lambda: pick(page, "ward", fv["ward_name"]))
        else:
            warnings.append("Ward: ต้องเลือกเอง")
        # Read back after all dependent controls have updated.
        for kind in ("text", "time", "select"):
            for name, value in fv[kind].items():
                if value is None:
                    continue
                tag = "select" if kind == "select" else "input"
                attempt(name, lambda n=name, v=value, t=tag: expect(page.locator(f'{t}[name="{n}"]')).to_have_value(str(v)))
        for name, value in fv["radio"].items():
            if value != "":
                attempt(name, lambda n=name, v=value: expect(page.locator(f'input[id="{n}{v}"]')).to_be_checked())
        for name, value in fv["date"].items():
            def check_date(n=name, v=value):
                if normalized_date(date_input(page, n).input_value()) != v:
                    raise ValueError("วันที่เปลี่ยนหลังกรอก")
            attempt(name, check_date)
        if fv.get("gcs_total"):
            attempt("GCS รวม (อ่านอย่างเดียว)", lambda: expect(page.locator('input[name="editRow.gcs"]')).to_have_value(fv["gcs_total"]))
    finally:
        page.remove_listener("request", started)
        page.remove_listener("requestfinished", finished)
        page.remove_listener("requestfailed", finished)
    return list(dict.fromkeys(warnings))
