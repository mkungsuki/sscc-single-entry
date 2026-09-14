# ขอบเขตการอ่านหน้าจอ nRefer เพื่อวางแผน

ผู้ใช้อนุญาตให้ตรวจส่วนล่างตามภาพ และกำหนดว่าต้องไม่เห็นชื่อผู้ป่วย HN หรือ AN (11 กันยายน 2026)

## วิธีที่ทดลองใช้สำเร็จ

ใช้ CUA Playwright read-only evaluate ภายใน scope ที่กำหนด แล้วคืนเฉพาะ metadata ตามรายการอนุญาต การกรองเกิดภายใน browser ก่อนผลเครื่องมือถูกส่งให้โมเดล ไม่ส่ง full-page snapshot มาเพื่อลบทีหลัง

- ส่วนแผน: `core-patient-stroke` → กลุ่ม `pk-tabs` ด้านล่างที่มีหัวแท็บแผนจำหน่าย → ชื่อ input ของ impairment/needs ที่อยู่ใน allowlist, ชนิด control, ค่า option ของ IMC/caregiver และชื่อช่อง goal/detail เท่านั้น
- BI: `core-patient-stroke dmis-disc-evaluate .evaluate-choice` → label ของคำถาม และ direct text nodes ของ span ที่มี radio (ข้อความตัวเลือกอ้างอิง); ไม่อ่าน checked, คะแนนรวม, รายการประเมิน, วันที่, ผู้ประเมิน หรือ detail
- สถานะ: ภายใน lower tabs อ่าน `select[name="editRow.status"]` เฉพาะ options code/label; ไม่อ่าน selectedIndex, select.value, วันที่หรือข้อความของเคส
- การเปลี่ยนแท็บใช้เฉพาะ `span.tab-title` ที่ระบุข้อความหมวดไว้ ไม่กดปุ่ม Save, Add new, copy last, +Add, ลบ หรือ upload
- หลังเปลี่ยนแท็บ ตรวจเฉพาะผลที่มี scope เดิม ไม่เรียก getAXState/domSnapshot ทั้งหน้า

## สิ่งที่ไม่ส่งให้โมเดลหรือเก็บในไฟล์

ชื่อ/สกุล/คำนำหน้าผู้ป่วย, HN, AN, เลขบัตร, VN, ref ของเคส, เบอร์โทร, ที่อยู่, พิกัด, token, current field values, free-text goal/detail, คะแนนหรือ checkbox ที่เลือกไว้, ชื่อผู้ประเมิน, ข้อมูลในทะเบียน และแถวสถานพยาบาลปลายทางของผู้ป่วย

ชื่อ field เช่น `editRow.patient_goal` เป็นชื่อโครงสร้าง ไม่ใช่ข้อความที่ผู้ป่วยหรือเจ้าหน้าที่กรอก

ไม่ใช้ screenshot ทั้งหน้า, page.innerText, body.textContent, full accessibility tree, export DOM/HTML หรือ network response ที่รวมข้อมูลเคส ในขอบเขตการสำรวจนี้

หากจำเป็นต้องใช้ภาพ ให้ผู้ใช้ส่งภาพเฉพาะส่วนที่ตัดตัวระบุออกแล้ว หรือใช้ screenshot clip เฉพาะบริเวณที่ตรวจสอบขอบเขตได้จาก DOM โดยไม่ต้องดูภาพเต็มก่อน ถ้าขอบเขตไม่แน่นอนให้หยุด

หากไม่พบ component/หัวแท็บ/field ที่กำหนด ให้คืนเพียง error code หรือจำนวน element; ห้าม fallback ไปอ่านทั้งหน้า

## ขอบเขตของข้อยืนยัน

วิธีนี้ป้องกันการอ่าน/ส่งตัวระบุผ่านชุดคำสั่งที่จำกัด scope และผลลัพธ์นี้ ไม่ใช่การติดตั้งระบบปิดบังข้อมูลทั้งเบราว์เซอร์ และไม่ได้รับรองว่าข้อมูลทางคลินิกที่ไม่มีชื่อจะระบุตัวไม่ได้ในทุกบริบท

สำหรับตัวกรอก production การจับคู่ HN/AN ควรทำใน local worker และคืนเพียงตรง/ไม่ตรง โดยไม่ส่งค่าจริงเข้า model หรือ log; เป็นงานในแผน ยังไม่ได้ implement ในรอบสำรวจนี้

## ผลสำรวจภายใต้ขอบเขตนี้

- Plan: impairment 5 ช่อง, care needs 15 ช่อง, IMC 3 ตัวเลือก, caregiver 2 ตัวเลือก, textarea 2 ช่อง (ไม่อ่านเนื้อหา)
- BI: 10 ข้อ, 30 ตัวเลือก, คะแนนสูงสุดรวม 20; radio ไม่มี name/value attributes และ id ซ้ำในข้อเดียวกัน
- Status: 7 options โดยไม่อ่านสถานะปัจจุบัน
- ไม่มีการแก้หรือบันทึกข้อมูลเคสในรอบ scoped inspection
