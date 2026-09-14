# บรีฟ codex: nRefer เฟส 2 — แท็บหลังบันทึก (4–8) + ข้อสรุปเรื่อง HN/AN

2026-09-11 · ต่อจาก `claude-assessment-20260911.md` · ข้อเท็จจริงจาก JS สาธารณะ nRefer 5.0.8 (chunk-UIVIL3PE / TO245DYV) + screenshot ของผู้ใช้

---

## 0. ข้อสรุปที่ผู้ใช้ตัดสินแล้ว (ทำก่อน ไม่ต้องถามซ้ำ)

**HN/AN ให้พยาบาลพิมพ์เองท้ายสุด โปรแกรมไม่กรอกสองช่องนี้**
- ต้นตอ (ยืนยันใน Brave ปกติแล้ว): พิมพ์ HN หรือ AN → เว็บเรียกค้น HIS → รพ. ไม่มี HIS → error ไม่ถูก catch → `loading` ค้าง → ช่องวันที่/เวลาทุกช่อง disabled ถาวร (ปุ่ม [บันทึก] ไม่ผูก loading จึงยังกดได้)
- **AN ก็ trigger เหมือน HN** (`checkAN` → `getPerson()` เส้นเดียวกัน) → ต้องเว้นทั้งคู่
- โปรแกรม: กรอกทุกอย่างที่เหลือ (Dx, ชื่อ, เพศ, วันเกิด, อายุ, วัน-เวลาทั้งหมด, LOS, ward, ผลจำหน่าย, ผู้นำส่ง, BP, GCS E/V/M, radio + วันเวลา rt-PA/CT/SU, mRS) → readback → แถบเขียว
- แถบต้องบอก 3 อย่างตรงๆ: (1) ตรวจวันที่/เวลา/mRS/ward ให้เสร็จ **ก่อน** พิมพ์ HN เพราะหลังพิมพ์จะแก้ช่องเหล่านั้นไม่ได้ (2) **AN แล้ว HN** ที่ต้องพิมพ์คือ `<AN>` / `<HN>` (โชว์ให้ก๊อป — ตรงทุกตัวอักษรรวมศูนย์นำหน้า ไม่งั้น SaveObserver จับคู่ไม่ได้) (3) วงกลมหมุนค้างหลังพิมพ์ HN เป็นอาการปกติของเว็บ กดบันทึกได้เลย
- ใส่ตัวตรวจ "ช่องวันที่ถูก disable ทั้งที่ยังไม่ได้พิมพ์ HN" → หยุดพร้อมบอกเหตุ (กันกรณีอื่นที่ทำให้ loading ค้าง)
- เกณฑ์ผ่านรอบพิสูจน์: readback ผ่านทุกช่องยกเว้น HN/AN บนเว็บจริงโหมดไม่บันทึก → พยาบาลพิมพ์ AN, HN แล้วปุ่มบันทึกกดได้ → ปิดไม่บันทึก → รอบถัดไปพยาบาลกดบันทึกจริง 1 เคส → ทะเบียนแสดง HN/AN/วันที่ตรง
- คู่ขนาน: แจ้ง nRefer (บั๊ก getPerson ไม่ catch) + ถาม IT ชุมแพเรื่อง his-connect

---

## 1. สิ่งที่ยังไม่ได้ทำ: แท็บที่โผล่หลังบันทึกเรคคอร์ดหลัก

จาก screenshot ของผู้ใช้ เคสจริงของ รพ. มีข้อมูลในแท็บเหล่านี้ที่พยาบาลต้องกรอกต่อ:

| แท็บ | คอมโพเนนต์/ที่เก็บ | ปุ่มบันทึกของแท็บยิง | ใครกรอกในชีวิตจริง | เฟสนี้ |
|---|---|---|---|---|
| 4. ประเมินก่อนจำหน่าย (BI) | `dmis-disc-evaluate` — ต่อครั้ง: วันที่/เวลา/ผู้ประเมิน + BI 10 ข้อ + mRS + complication + detail + next_goal | `POST /dmis/imc/save-dmis-evaluate` (evaluate_type `discharge`) | พยาบาล stroke unit ตอนจำหน่าย | **ทำ** |
| 5. วางแผนจำหน่าย | อยู่ใน `editRow` ของเรคคอร์ดหลัก: impairment 5 ข้อ, ความต้องการดูแล 15 ข้อ, Case IMC, ความพร้อมญาติ, complication, patient goal, รายละเอียด + **สถานพยาบาลปลายทาง (hospcare)** | ปุ่มบันทึกของแท็บ = `savePatient()` → `/save-patient` (ref เดิม) **ยกเว้น** ปลายทาง: `addHospcare()` ยิง `/save-hospcare` **ทันทีที่เลือก** โดยไม่รอปุ่มบันทึก | พยาบาล stroke unit ตอนจำหน่าย | **ทำ** (ยกเว้นปลายทาง — ดู 3.3) |
| 6. ข้อมูลเยี่ยมบ้าน/ประเมิน BI | home visit (`save-imc-evaluate`, type `home`) + vital sign + BI | `/save-imc-evaluate` | รพ.สต./PCU หลังจำหน่าย | ไม่ทำ (ไม่ใช่งาน stroke unit) |
| 7. ประเมิน Motor power (ASIA) | `dmis-asia-score` ตาราง C5–S1 ซ้าย/ขวา 0–5 | endpoint ของ ASIA (`save-visit-evaluate`?) | ออกแบบมาเพื่อ SCI; screenshot ผู้ใช้กดเองตอนสำรวจ ("*** เพิ่ม ***" ยังไม่บันทึก) | **ถามขอนแก่น**ว่า stroke ต้องกรอกไหม ถ้าต้อง = ค่าปกติ 5 ทุกช่อง → ค่อยทำ |
| 8. สิ้นสุดการตามเยี่ยม | `editRow.status` (รายการจาก `/dmis/imc/service-status`; ค่าเริ่มต้น 1 = อยู่ระหว่างการรักษา/ติดตามเยี่ยม), date_completed, completed_detail | `savePatient()` | ปิดเคสตอนติดตามจบ | ไม่ทำตอนจำหน่าย (ค่าเริ่มต้น 1 ถูกแล้ว) |
| ข้อมูล nRefer | `nrefer-visit` อ่านอย่างเดียว ผูกด้วย cid | — | — | ไม่ทำ |

เงื่อนไขสำคัญ: กลุ่มแท็บนี้ render เฉพาะเมื่อ `editRow.ref` มีค่า = **หลังกดบันทึกเรคคอร์ดหลักและเว็บโหลดเคสกลับมา** ดังนั้น flow เป็นหลายขั้น ไม่ใช่ฟอร์มเดียว

---

## 2. Flow ที่เสนอ (ยังยึดหลัก: โปรแกรมกรอก คนกดบันทึก ทุกขั้น)

```
ขั้น 1  เปิด Add new → กรอกทุกอย่างยกเว้น HN/AN → แถบเขียว
        พยาบาล: ตรวจ → พิมพ์ AN, HN → กด [บันทึก]        ← observer: /save-patient 200 (identity จาก request body)
ขั้น 2  รอเว็บโหลดเคสกลับ (ref>0, แท็บ 4–8 โผล่)           ← barrier ใหม่: รอ pk-tabs + dmis-disc-evaluate ปรากฏ
        เปิดแท็บ 4 → กด "+ Add new" → กรอกวันที่/เวลา/ผู้ประเมิน + BI 10 ข้อ (+ mRS, complication ถ้ามี) → readback
        พยาบาล: ตรวจ → กด [บันทึก] ของแท็บ 4                ← observer: /save-dmis-evaluate 200 (patient_ref ตรง)
ขั้น 3  เปิดแท็บ 5 → ติ๊ก impairment / ความต้องการดูแล / Case IMC / ความพร้อมญาติ / complication / goal → readback
        **ไม่แตะช่องสถานพยาบาลปลายทาง** (ยิง API ทันที ดู 3.3)
        พยาบาล: (เลือกปลายทางเอง) → กด [บันทึก] ของแท็บ 5      ← observer: /save-patient 200 (ref เดิม)
จบ      สถานะเคสในโปรแกรม: หลัก ✓ / BI ✓ / แผนจำหน่าย ✓ แยกกัน — ขั้นไหนไม่ได้กดก็ค้างเป็น "ยังไม่ทำ" ส่งซ้ำได้เฉพาะขั้นนั้น
```

- ทุกขั้นพยาบาลกดบันทึกเอง; โปรแกรมไม่กด ไม่ยิง API เขียน (เหมือนเดิม)
- ถ้าพยาบาลปิด/ไม่กดที่ขั้นใด → บันทึกสถานะขั้นก่อนหน้าไว้ ไม่ต้องทำใหม่ทั้งหมด (ต้องออกแบบ state: `nrefer_main`, `nrefer_bi`, `nrefer_plan` แทน flag เดียว)
- โหมดตรวจ (no-save) ต้องครอบ endpoint ใหม่ด้วย: `save-dmis-evaluate`, `save-hospcare`, `save-imc-evaluate`, `save-visit*` = block; `evaluate-choice`, `dmis-evaluate` (อ่านรายการประเมิน), `hospcare` (อ่าน), `service-status` = allow

---

## 3. ข้อมูลต้นทางที่ SSCC ไม่มี → ต้องเพิ่มฟิลด์ รพ. ในโปรแกรม (นี่คือจุดที่ "กรอกครั้งเดียว" ได้ผลจริง)

### 3.1 แท็บ 4 — BI 10 ข้อ
- SSCC มีแค่ **คะแนนรวม** (x_b9 แรกรับ, x_b10 จำหน่าย) แยกกลับเป็น 10 ข้อไม่ได้
- เพิ่มหมวดในฟอร์ม SSCC "ประเมิน Barthel ก่อนจำหน่าย (nRefer)": 10 select (feeding/transfer/grooming/toilet/bathing/mobility/stairs/dressing/bowel/urine) ตัวเลือก+คะแนน **ดึงจาก `/dmis/imc/evaluate-choice` (group_type BI)** ครั้งเดียวแล้วเก็บเป็น schema ไม่ hardcode; + วันที่/เวลา/ผู้ประเมิน (default = วันจำหน่าย, ชื่อคน login)
- **คำนวณรวมแล้วเติม x_b10 ให้อัตโนมัติ** (ถ้ามีค่าอยู่แล้วและไม่ตรง → ถามผู้ใช้ ไม่ทับเงียบ เหมือนที่ทำกับ GCS)
- ⚠️ พฤติกรรมเว็บ: กด "+ Add new" แล้ว **ทุกข้อ default = คะแนนสูงสุด (รวม 20 = ช่วยเหลือตัวเองได้หมด)** — ถ้าโปรแกรมไม่กรอกและพยาบาลกดบันทึกเผลอ จะได้ข้อมูลผิดแบบเนียนๆ → ต้อง readback ทุกข้อ และถ้าต้นทางไม่มีค่า ต้อง**ไม่**ปล่อยให้ค่า default ผ่านโดยไม่เตือน
- ในแท็บเดียวกันมี mRS (มีใน SSCC x_b12), complication (autocomplete multi จาก `complicationList`: Pressure sore gr.1–4, Pneumonia, CA_UTI, Joint Stiffness, VAP), detail, next_goal

### 3.2 แท็บ 5 — แผนจำหน่าย
| ช่องบน nRefer | key ใน editRow | ต้นทาง |
|---|---|---|
| Impairment 5 ข้อ (swallowing/communication/mobility/cognitive/bowel) | `evaluates.swallowing …` → `impairement` JSON | **ใหม่**: checkbox-group ใน SSCC (x_c11 การกลืน "ไม่ได้รับเนื่องจาก" ไม่เท่ากับ swallowing problem — อย่า map) |
| ความต้องการดูแลหลังจำหน่าย 15 ข้อ | `evaluates.disc_*` (เช่น `disc_healthrisk`, `disc_eqm`, `disc_env`; ต้อง grep ชื่อครบ 15 จาก template) → `evaluate` JSON | **ใหม่**: checkbox-group 15 ข้อ |
| Case IMC | `imc` = 1 เข้าเกณฑ์ / 0 ไม่เข้า / 2 ไม่เข้าแต่ส่งดูแลต่อเนื่อง | **ใหม่**: select (ค่าเริ่มต้นของเว็บ = 0 — เว็บบังคับความหมาย ถ้าไม่เลือก = "ไม่เข้าเกณฑ์") |
| ความพร้อมของญาติ | `caregiver` (radio 2 ค่า — ตรวจค่าจริงจาก consts 156/157) | **ใหม่**: select |
| Complication ก่อนจำหน่าย | `complication` (list) | map บางส่วนจาก SSCC C13: Pneumonia→"Pneumonia", Pressure sore→ต้องรู้ grade (SSCC ไม่มี), **UTI ของ SSCC ≠ CA_UTI** (catheter-associated) → ห้าม map ตรง ให้ผู้ใช้ยืนยัน |
| เป้าหมายการรักษา / รายละเอียด | `patient_goal`, `dmis_detail` | **ใหม่**: textarea (ไม่บังคับ) |
| สถานพยาบาลปลายทาง (จังหวัด/รพ./PCU) | hospcare rows | SSCC มี B4.1 รพ.ส่งต่อ แต่ปลายทาง IMC มักเป็น รพ.สต. ใกล้บ้าน ≠ B4.1 → **ไม่ auto** ดู 3.3 |

### 3.3 ห้ามให้โปรแกรมเลือก "สถานพยาบาลปลายทาง"
`addHospcare()` ในโค้ดเว็บยิง `POST /dmis/imc/save-hospcare` **ทันทีที่เลือกจาก dropdown** ไม่ผ่านปุ่มบันทึกของแท็บ → ถ้าโปรแกรมคลิกเลือก = โปรแกรมเขียนข้อมูลเอง ผิดหลักข้อ 1 → ให้พยาบาลเลือกเอง แถบบอกชัด; ใน no-save mode ต้อง block endpoint นี้และเขียนเทสต์ว่าโปรแกรมไม่เคยแตะ dropdown นี้

### 3.4 การจัดฟิลด์ใหม่ใน SSCC
- ใช้กลไก `custom_fields_defaults.json` + `case_form.arrange()` ของ codex จัดเข้าหมวด "ก่อนจำหน่าย" ไม่ใช่ appendix ท้ายฟอร์ม (ผู้ใช้เคยตำหนิเรื่องนี้)
- ตัวเลือก BI ต้องมีคะแนนในข้อความ (เช่น "ทำเองได้ทุกขั้นตอน, 3") ตรงกับเว็บ ให้พยาบาลเทียบตาได้
- เก็บ stored keys ใหม่เป็น `cf_bi_*`, `cf_imp_*`, `cf_need_*`, `cf_imc`, `cf_caregiver`, `cf_goal` — ห้ามเปลี่ยน key เดิม

---

## 4. ต้องถามเจ้าของทะเบียน (ขอนแก่น) ก่อนลงแรงส่วนนี้
1. ตอนจำหน่ายจาก stroke unit ต้องกรอกแท็บไหนบ้าง: 4+5 พอไหม, 7 (Motor power) ต้องกรอกสำหรับ stroke หรือไม่
2. Case IMC ใครเป็นคนตัดสิน (แพทย์/พยาบาล/ทีม IMC) — กำหนด default ใน SSCC ได้ไหม
3. ปลายทาง hospcare ต้องใส่ตอนจำหน่ายเลยหรือทีม IMC ใส่ทีหลัง
4. complication list ของ nRefer เทียบ C13 ของ SSCC อย่างไร (โดยเฉพาะ UTI vs CA_UTI, pressure sore grade)

---

## 5. ลำดับงานที่เสนอให้ codex
1. ข้อ 0 (HN/AN ท้ายสุด + แถบ + ตัวตรวจ disabled) → live no-save → รอบพิสูจน์ — **ก่อนอย่างอื่น**
2. ดึง `evaluate-choice` (BI) + `service-status` + ชื่อ `evaluates.disc_*` ครบ 15 จาก template → เขียนเป็น schema ใน repo (มีวันที่ + เวอร์ชันเว็บ)
3. เพิ่มฟิลด์ รพ. ข้อ 3 ในโปรแกรม SSCC + auto-sum x_b10 + เทสต์ UI
4. ขั้น 2–3 ของ flow (barrier รอ ref, กรอกแท็บ 4, กรอกแท็บ 5 ยกเว้นปลายทาง, observer ต่อ endpoint, state แยกขั้น) + mock แท็บ 4/5 (ไม่ต้องเลียน Angular แค่ DOM contract + default = max score เพื่อทดสอบว่าโปรแกรมไม่ปล่อยผ่าน)
5. live no-save ทั้ง 3 ขั้น → pilot 1 เคสโดยพยาบาล
ข้อ 3–4 รอคำตอบข้อ 4 (ขอนแก่น) ได้ ไม่ต้องบล็อกข้อ 1
