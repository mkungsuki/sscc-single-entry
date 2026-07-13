# ข้อค้นพบเชิงเทคนิคจากการสำรวจเว็บ SSCC จริง (2026-07-13)

สำรวจผ่าน Claude Browser ขณะ login อยู่ — ดูอย่างเดียว ไม่มีการบันทึก/แก้ข้อมูลใดๆ
ไฟล์ schema: panes-1-2.json, pane-3.json, pane-4.json, panes-5-8.json (โครงสร้างฟอร์มล้วน ไม่มีข้อมูลผู้ป่วย)

## โครงสร้างระบบ
- เว็บสร้างด้วย **PHPMaker** (สังเกตจาก id pattern: `el_stroke_form_*`, `lu_*`, `r_*`, hidden `token`/`a_edit`) — โครงสร้างคาดเดาได้ เสถียร
- **หน้าแก้ไข (stroke_formedit.php?patient_id=N) — VERIFIED 2026-07-13:** ฟอร์มเดียว `fstroke_formedit` ครอบ 8 tab panes, 160 ฟิลด์, **ปุ่ม submit "บันทึก" มีเพียง 1 ปุ่ม อยู่นอก tab panes** (ที่เห็นใต้ทุกแท็บคือปุ่มเดียวกัน) → **เติมครบทุกแท็บแล้วกดบันทึกครั้งเดียวเซฟทั้งหมด — ยืนยันจากโครงสร้าง DOM แล้ว**
- **หน้าเพิ่ม (stroke_formadd.php) — VERIFIED:** ไม่มีแท็บเลย (0 tab panes, 0 nav-tabs) มีเฉพาะ A1-A6: `x_pid, x_fname, x_a2, x_a3, x_a4, x_a5, x_a6_1, x_a6, x_a6_address, x_a6_hospcode` + CSRF `token`, hidden `a_add=A` — บันทึกแล้วต้องกลับเข้า formedit เพื่อกรอกส่วนที่เหลือ (ตรงกับที่ผู้ใช้เล่า: เพิ่มคนไข้ใหม่ต้องไล่ทีละหน้า)
- **นัยต่อ auto-fill:** ปฏิสัมพันธ์กับ SSCC ต่อเคส = บันทึกแค่ 2 ครั้ง (add A1-A6 → edit เติมทุกอย่าง → save เดียว) ไม่ใช่ 9 ครั้งแบบที่พยาบาลทำมือ; การสลับแท็บเป็นแค่ CSS show/hide — โปรแกรม set ค่าได้ทุกฟิลด์โดยไม่ต้องคลิกแท็บ แต่พยาบาลยังเปิดไล่ดูทีละแท็บเพื่อตรวจได้ตามปกติ
- Flow ที่ต้องใช้: เพิ่ม (A1-A6) → บันทึก → ได้ patient_id → เปิด formedit → เติมที่เหลือ → บันทึก
- URL patterns: `stroke_formlist.php`, `stroke_formadd.php`, `stroke_formedit.php?patient_id=`, `stroke_formview.php?patient_id=`, `stroke_post_carelist.php?fk_patient_id=` (โมดูลดูแลหลังกลับบ้าน — ใช้ต่อยอด follow-up 90 วันได้)

## จุดพิเศษที่ auto-fill ต้องจัดการ
1. **x_c18_drug** (C18 ยาที่ได้รับ): เป็น `input hidden` + lookup modal ค้นหายา (`lu_x_c18_drug`) — ต้อง set ค่า hidden + text แสดงผล หรือ drive modal
2. **x_b4_1_hospcode** (B4.1 โรงพยาบาลส่งต่อ): cascading dropdown โหลดรายชื่อ รพ. ตามจังหวัดผ่าน AJAX — ต้องเลือกจังหวัดก่อนแล้วรอ options โหลด
3. **Checkbox groups** (`x_d1[]`, `x_d3[]`, `x_e2[]`, `x_f1[]`): มีแถว template `value="{value}"` ต้องข้าม
4. **x_e2[]**: การจับคู่ value↔label ตอน extract เพี้ยน (label "Bypass" ไปคู่กับ value อื่น) — ต้อง verify การ map ก่อนใช้จริง
5. **Ward list (B1.1/B1.2)** เป็นของ รพ.ชุมแพ เฉพาะ: ARI, ICU, Stroke Unit, VIP Med, อายุรกรรมชาย, อายุรกรรมหญิง — รพ.อื่นจะต่างกัน (ผูกกับ hospital_id)
6. วันที่ใช้รูปแบบ dd/mm/yyyy (ค.ศ.) เวลา hh:mm:ss — มี datepicker แต่พิมพ์ตรงลง input ได้
7. Dropdown ส่วนใหญ่ค่าจริงเป็นรหัส (1/2/3, Y/N, รหัสจังหวัด 6 หลัก, รหัส รพ. 5 หลัก) — mapping เก็บครบใน schema files แล้ว

## Login
- username + password เท่านั้น ไม่มี CAPTCHA/OTP — พยาบาล login เองเสมอ (ตัดสินใจแล้ว: ไม่เก็บ credentials)

## ผล PILOT บนเว็บจริง (2026-07-13) — ทำผ่าน Claude Browser (session ที่ login ค้าง) ได้ patient_id 737783
ยืนยันว่า data + mapping + save ทำงานครบบนเว็บจริง (reload กลับมาค่าครบทุกฟิลด์ทุกแท็บ) พบ 3 พฤติกรรมจริงที่แก้ตัว fill_sscc.py แล้ว:
1. **add บันทึกสำเร็จ → เด้งไป stroke_formedit.php?patient_id=NEW ทันที** (ไม่ต้องค้น list) — find_patient_id อ่านจาก URL ได้เลย
2. **edit บันทึกสำเร็จ → เด้งไป stroke_formview.php** (ไม่ใช่ formlist) มีข้อความ "ปรับปรุงสำเร็จแล้ว" — แก้ regex/ตัวจับ save แล้ว
3. **B5 (First Dx) มี JS รีเซ็ต B6 (Final Dx) เมื่อเปลี่ยนค่า** — ตั้ง B6 พร้อม B5 จะโดนล้าง; แก้ด้วยรอบ verify_and_refill (ตรวจค่าจริงใน DOM แล้วเติมซ้ำเฉพาะตัวที่เพี้ยน) — เป็น safety ทั่วไปเผื่อ field dependency อื่น
- cascade รพ.ส่งต่อ (A6.2 x_a6_hospcode) ผ่าน AJOX ทำงานถูก: จังหวัด 400000 → เลือก "โรงพยาบาลสีชมพู" ได้รหัส 10999
- ยา C18: hidden x_c18_drug เก็บ "รหัสยา" (Aspirin=1) + span #lu_x_c18_drug แสดงชื่อ — set รหัสตรง + อัปเดต span พอ (ไม่ต้องเปิด modal ค้นหา)

## ผล PILOT ผ่านตัว Playwright จริง (รอบ 2, 2026-07-13) — patient_id 737795 สำเร็จครบ mismatches:0
รัน fill_sscc.py กับเว็บจริง: ข้าม login (session ค้าง) → สร้างเคส → เติมทุกแท็บ → พยาบาลกดบันทึก → detect formview → reload ตรวจค่าครบ (7 เวลา + B6 + ยา + cascade + checkbox)
พบบั๊กเพิ่ม 1 จุด แก้แล้ว:
- **ช่องวันที่/เวลาเป็น readonly + มี date/time-picker → Playwright `.fill()` ค้าง (timeout 30s/ช่อง)** แก้เป็น `el.evaluate((e,val)=>{e.value=val; dispatchEvent(change)})` — ค่าคงอยู่ตอนบันทึกจริง (เดิม fill() ใช้กับ date ได้แต่ time ไม่ได้ เพราะ time readonly)

## การลบเรคคอร์ด (ยืนยันวิธีจากเว็บจริง)
เมนู toolbar: ติ๊ก checkbox (value = patient_id) → คลิกปุ่มลบ (`[onclick*="stroke_formdelete.php"]`) → **Bootstrap modal เด้ง** (ไม่ใช่ native confirm) → คลิกปุ่ม "ตกลง" ใน `.modal-footer` → ขึ้น "ลบเรียบร้อยแล้ว"
เรคคอร์ดทดสอบทั้งหมด (737771, 737783, 737791, 737795) ลบออกหมดแล้ว — เว็บจริงกลับมา 3999 เคส เคสจริงครบ

## หลุมพราง UX ที่เจอ (production ควรกันไว้)
- run ที่ถูก kill กลางคันอาจทิ้งหน้าต่าง Edge ค้าง (คนละ patient_id กับ run ใหม่) → เคยทำผู้ใช้เกือบกดเซฟบานเก่าที่ลบไปแล้ว (เซฟทับเรคคอร์ดที่ลบแล้ว = no-op ไม่ re-create โชคดี) — production ปกติ run จบเองปิดหน้าต่าง แต่ถ้าจะกันควรปิดหน้าต่างเก่า/แสดง patient_id เด่นๆ
