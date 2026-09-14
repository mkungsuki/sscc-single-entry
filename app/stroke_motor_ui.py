"""Fill the user-selected Motor table through native radios; never click Save.

Radio contract: public nRefer chunk-UIVIL3PE.js, functions za/ja/Ua,
2026-09-11. Values are grade strings; names omit the underscore in the model key.
"""
import time
from urllib.parse import urlsplit
from playwright.sync_api import expect
from stroke_motor import project


def same_case(page, data):
    # Only return a boolean. No identity is printed or copied into a screenshot/log.
    for name, key in (('hn', 'x_a2'), ('an', 'cf_an')):
        expected = str(data.get(key) or '').strip()
        field = page.locator(f'input[name="editRow.{name}"]')
        if not expected or field.count() != 1 or field.input_value().strip() != expected:
            return False
    return True


def fill_motor(page, data):
    projected = project(data)
    if not projected['complete']:
        raise ValueError('ยังมีคะแนน Motor power ว่างอยู่')
    if not same_case(page, data):
        raise ValueError('เคสบน nRefer ไม่ตรงกับเคสที่เลือก — ไม่ได้กรอกคะแนน')
    root = page.locator('dmis-asia-score:visible')
    expect(root).to_have_count(1)
    controls = []
    # Preflight the entire table before changing any score (including default 5s).
    for row in projected['rows']:
        name = 'patientEvaluate.' + row['key'].replace('_', '')
        group = root.locator(f'input[type="radio"][name="{name}"]')
        expect(group).to_have_count(6)
        if sorted(group.evaluate_all('(els) => els.map(el => el.value)')) != ['0','1','2','3','4','5']:
            raise ValueError('ตัวเลือก Motor power บนเว็บเปลี่ยนไป — ไม่ได้กรอกคะแนน')
        radio = root.locator(f'input[type="radio"][name="{name}"][value="{row["score"]}"]')
        expect(radio).to_have_count(1)
        expect(radio).to_be_visible()
        expect(radio).to_be_enabled()
        controls.append(radio)
    for radio in controls:
        if not same_case(page, data):
            raise ValueError('เคสเปลี่ยนระหว่างกรอก Motor power — หยุดให้ตรวจ')
        radio.check()
    for radio in controls:
        expect(radio).to_be_checked()
    if not same_case(page, data):
        raise ValueError('เคสเปลี่ยนหลังกรอก Motor power — หยุดให้ตรวจ')
    return projected


def process_motor(page, ui_url, case, args):
    from fill_nrefer import robot_banner, log, REVIEW_WAIT_MS
    expected_origin = urlsplit(ui_url)
    if urlsplit(page.url).netloc != expected_origin.netloc:
        page.goto(ui_url.rstrip('/') + '/#/dmis/patient', wait_until='domcontentloaded')
    data = case['data']
    if not project(data)['complete']:
        raise ValueError('คะแนน Motor power ไม่ครบ')
    robot_banner(page, 'เปิดเคสที่ตรงกันและแท็บ 7 Motor power แล้วกดปุ่มเติมคะแนนในตารางนี้', '#24695d')
    page.evaluate('''() => {
      const banner = document.getElementById('sscc_robot_banner');
      const button = document.createElement('button');
      button.id = 'sscc_motor_apply'; button.textContent = 'เติมคะแนนในตารางนี้';
      button.style.cssText = 'display:block;margin-top:8px;padding:10px;border:0;border-radius:6px;cursor:pointer';
      button.addEventListener('click', () => {button.dataset.requested='1';});
      const status = document.createElement('div'); status.id='sscc_motor_status';
      status.style.marginTop='8px'; status.setAttribute('aria-live','polite');
      banner.append(button, status);
    }''')
    if getattr(args, 'on_review', None):
        args.on_review()
    deadline = time.monotonic() + REVIEW_WAIT_MS / 1000
    while time.monotonic() < deadline and not page.is_closed():
        if getattr(args, 'cancel_check', lambda: False)():
            return
        button = page.locator('#sscc_motor_apply')
        if button.count() and button.get_attribute('data-requested') == '1':
            button.evaluate('(el) => {delete el.dataset.requested;}')
            origin = urlsplit(page.url)
            if (origin.scheme, origin.netloc) != (expected_origin.scheme, expected_origin.netloc):
                raise ValueError('หน้าที่เปิดไม่ใช่ nRefer ที่ตั้งค่าไว้')
            ready = same_case(page, data) and page.locator('dmis-asia-score:visible').count() == 1
            if not ready:
                page.locator('#sscc_motor_status').evaluate("el => {el.textContent='ยังไม่พบเคสที่ตรงกันพร้อมแท็บ 7 — กรุณาเปิดให้ตรงก่อน';}")
                continue
            button.evaluate('(el) => {el.disabled=true;}')
            fill_motor(page, data)
            robot_banner(page, 'กรอก Motor power ครบ 20 ช่องแล้ว — คัดลอกจากคะแนนแขนขาและใช้ค่าที่แก้รายช่อง ตรวจวันที่ ผู้ประเมิน และคะแนน แล้วกดบันทึกเอง', '#24695d')
            log(case['id'], 'Motor power: กรอกและอ่านกลับครบ 20 ช่องตาม stroke-limb-copy-v1; รอผู้ใช้บันทึก')
            # Keep review active so manual edits are never overwritten by another pass.
        page.wait_for_timeout(250)
