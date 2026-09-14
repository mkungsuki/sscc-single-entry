# nRefer integration — ใบส่งต่องาน (handoff ให้ผู้พัฒนา/AI คนถัดไป)

อัปเดต 2026-09-09 · โปรเจกต์ SSCC single-entry (`C:\SSCC\app`) · รพ.ชุมแพ ขอนแก่น

---

## 1. เป้าหมายของงานนี้

ขอนแก่นสั่งให้พยาบาล stroke คีย์เคสเข้า **nRefer → Service Plan → Stroke & IMC (DMIS)** ที่ `https://nrefer.moph.go.th/beta/#/dmis/patient`
ซึ่งเป็นข้อมูล **ชุดเดียวกับที่คีย์ SSCC อยู่แล้ว** เป้าหมาย = ให้โปรแกรม SSCC single-entry ส่งเข้า nRefer ให้ ไม่ต้องคีย์ซ้ำ

โปรแกรมนี้เดิมทำงานกับเว็บ SSCC (neuronetworks.org/stroke, PHPMaker) โดยหลักคือ **หุ่นยนต์กรอกฟอร์มให้ แล้วหยุด ให้พยาบาลตรวจและกด [บันทึก] เอง** (`fill_sscc.py`)
งาน nRefer ต้องยึดหลักเดียวกันเป๊ะ

---

## 2. หลักที่ห้ามละเมิด (สำคัญกว่าความสวยของโค้ด — ผู้ใช้ย้ำแล้ว)

1. **ผู้ใช้ต้องเป็นคนกดบันทึกจริงเสมอ** เห็นข้อมูลในหน้าจอที่คุ้น แก้ได้ก่อนบันทึก โปรแกรม **ห้ามกดบันทึกเอง ห้ามยิง API เขียนข้อมูลเอง**
   (เวอร์ชันแรกของงานนี้ยิง POST `/dmis/imc/save-patient` ตรงเพราะฟอร์มกรอกยาก → ถูกตำหนิและถอดทิ้ง)
2. **ห้ามชวนผู้ใช้ทดสอบกับระบบจริงด้วยข้อมูลผู้ป่วยจริงเมื่อผ่านแค่ mock** — การทดสอบกับของจริงต้องเป็นขั้นที่ **ไม่เกิดเรคคอร์ด** (กรอกแล้วปิดโดยไม่บันทึก / อ่าน DOM เฉยๆ) และบอกชัดว่าขั้นไหนจะเขียนจริง
3. ไม่เก็บรหัสผ่าน/ความลับผู้ใช้ ข้อมูลอยู่เครื่องเดียว (PDPA)

> ประวัติเสีย: เวอร์ชัน API เก่าสร้างเรคคอร์ดจริงหลุดเข้า nRefer 2 ตัว (ref 2693, 2694) โดยไม่ผ่านการตรวจ — **ลบออกหมดแล้ว** 2026-09-09
> (วิธีที่ใช้ลบ: query `/dmis/imc/patient {where:{hospcode}}` แล้วกรอง `patient_raw_data.sscc_source == "SSCC-single-entry"` → `/dmis/imc/delete-patient {data:{ref,hospcode}}`)

---

## 3. สิ่งที่ทำไปแล้ว (สถานะปัจจุบันของโค้ดใน repo)

ไฟล์ที่เพิ่ม/แก้ (ยังไม่ commit):
- `app/nrefer_map.py` — แปลงข้อมูลเคส (key ตาม SSCC + cf_*) → โครงข้อมูล nRefer
  - `build(data, hcode, uid)` → person/patient/raw + summary + notes (มี logic: Dx→ICD/กลุ่ม DMIS, rtpa/ct/su/surgery tri-state, carry, visit_result, LOS, แยกคำนำหน้าชื่อ)
  - `form_values(built)` → ค่าที่จะกรอกลงฟอร์ม จัดกลุ่มเป็น text/radio/select/date/time/mrs/ward_name (key = `editRow.*` ตรงกับ ngModel บนเว็บ)
- `app/fill_nrefer.py` — หุ่นยนต์เปิด Edge → login → กด "Add new" → **กรอกฟอร์ม "เพิ่มข้อมูล"** → หยุดรอ → ดักว่าพยาบาลกด [บันทึก] สำเร็จด้วยการฟัง response ของ `/dmis/imc/save-patient` (200) → จำ ref ไว้ในเคส **(ไม่เรียก API เขียนเอง)**
- `app/mock/mock_nrefer.py` + `app/mock/test_nrefer.py` — nRefer จำลอง (DOM เลียนแบบฟอร์มจริง) + เทสต์
- `app/db.py` — คอลัมน์ `nrefer_ref`, `nrefer_at` (+ set_nrefer)
- `app/server.py` — route `/case/<id>/nrefer/preview`, `/case/<id>/nrefer/submit`, `/queue/nrefer`, spawn_nrefer, _nrefer_ready
- `app/templates/form.html`, `list.html` — ปุ่ม "☁ กรอกฟอร์ม nRefer" + modal ดูข้อมูลก่อน + ปุ่มคิวหน้ารวม + คอลัมน์ nRefer
- `app/config.json` — `nrefer_enabled`, `nrefer_base_url`, `nrefer_api_url`
- `app/schema/custom_fields_defaults.json` — ฟิลด์ รพ. ที่ nRefer มีแต่ SSCC ไม่มี: `cf_an`, `cf_birth`, `cf_sbp`, `cf_dbp`

**เทสต์ mock ผ่าน** (`python mock\test_nrefer.py`): กรอกครบทุกช่อง + โหมดไม่กดบันทึกต้องไม่เกิดเรคคอร์ด

---

## 4. ติดอะไรอยู่ (blocker หลัก) 🔴

**เปิด Edge ไป nRefer แล้ว login ThaID ไม่ผ่าน — พยาบาลสแกน QR แล้วแอป ThaID ขึ้น error "TS 027"**

ไล่มาแล้ว:
- เดิมโปรแกรมมีลูกเล่น "จำ token ThaID (sessionStorage `tokenRefer`) แล้วยัดกลับเข้าเว็บรอบถัดไป" → **nRefer ไม่รับ token ที่ยัดเอง** ทำให้หน้าอยู่ในสถานะกึ่งล็อกอิน พอสแกนทับเลยพัง → **ถอดลูกเล่นนี้ทิ้งแล้ว** (ลบ `data/nrefer_token.json`, `ensure_login` เหลือแค่รอ token สดจากการสแกน)
- แต่หลังถอดแล้ว **ยังติด TS 027 เหมือนเดิม** → แปลว่าไม่ใช่แค่เรื่อง token injection

**สมมติฐานที่ยังไม่พิสูจน์ (ให้ codex ไล่ต่อ):**
- (ก) Edge เปิดด้วย flag `--no-sandbox` (จาก Playwright `launch_persistent_context`) — บนหน้าเว็บมี banner "unsupported command-line flag: --no-sandbox" ขึ้นตลอด อาจกระทบ redirect/cookie ของ ThaID OAuth
- (ข) ThaID login เป็น OAuth redirect flow (ดูข้อ 7) — เปิดใน context อัตโนมัติของ Playwright อาจโดน ThaID ตรวจว่าเป็น automated browser หรือ redirect_uri/callback ไม่ตรง
- (ค) โปรไฟล์ Edge ที่ Playwright ใช้ (`data/edge_profile`) แชร์กับ fill_sscc — อาจมี state ค้าง หรือ ThaID ผูก device/session กับการเปิดครั้งก่อน
- (ง) TS 027 อาจเป็น error ฝั่ง ThaID เอง (เชิงนโยบาย/ device binding / เวลาไม่ตรง) — ต้องหาความหมายของโค้ดนี้จากเอกสาร ThaID/DGA

---

## 5. อยากให้ codex ทำอะไร

**A. แก้ blocker login (สำคัญสุด)**
- หาสาเหตุ TS 027 ให้ชัด: ลอง login ThaID บน nRefer ใน Edge โปรไฟล์นี้ **ด้วยมือ** (ไม่ผ่าน Playwright) ว่าผ่านไหม → แยกว่าปัญหาอยู่ที่ automation หรือที่บัญชี/ThaID
- ถ้าผ่านเมื่อเปิดเอง แต่ไม่ผ่านเมื่อ Playwright เปิด → ลองเอา `--no-sandbox` ออก / ใช้ `channel=msedge` แบบ attach โปรไฟล์จริงของผู้ใช้ / หรือให้ผู้ใช้เปิด Edge login ค้างไว้แล้วโปรแกรม attach แทน launch
- พิจารณาทางเลือก: ให้พยาบาล login ครั้งเดียวในหน้าต่างที่โปรแกรม "ไม่ปิด" ระหว่างวัน (คง context ไว้) แทนเปิด-ปิดทุกครั้ง

**B. ทดสอบการกรอกฟอร์มจริง (ขั้นไม่เขียนข้อมูล)**
- Claude Code เครื่องนี้ติด classifier ที่บล็อกสคริปต์พิมพ์ลงฟอร์มจริง เลย **ยังไม่เคยเห็นการกรอกฟอร์มจริงด้วยตา** — ยืนยันแค่ mock
- ให้ codex รันกรอกจริง **แล้วปิดโดยไม่กดบันทึก** ตรวจทีละช่องว่าลงถูก โดยเฉพาะ:
  - `pk-datepicker` (ปฏิทินปี พ.ศ.) — โปรแกรม set `input.datepicker-input.value = ISO` แล้ว dispatch `change` (เว็บ parse ทั้ง ISO และ dd/mm/พ.ศ.) → เช็คว่าวันโชว์ถูกและ model รับจริง
  - `pk-select` mRS / ward — คลิก `.pk-select-trigger` → คลิก `.pk-select-option` ตามข้อความขึ้นต้น → เช็คค่าที่เลือก
  - radio `id="editRow.rtpa1/2/0"`, select `editRow.dx/dmis/visit_result/carry`
  - อายุ(ปี)/LOS — nRefer ไม่คำนวณเองจากวันที่ (คำนวณเฉพาะตอนดึง HIS) โปรแกรมกรอกให้ → เช็คว่าถูก

**C. ออกแบบ/ตัดสินใจที่ยังค้าง**
- **การจับคู่เคสเดิม/กันซ้ำ**: nRefer ใช้ HN+AN แยกการมาแต่ละครั้ง (มี checkDup เตือน AN ซ้ำ) — ควรตรวจก่อนกรอกไหม? SSCC บางเคสไม่มี AN (cf_an ว่าง) จะทำยังไง
- **ward**: SSCC เก็บเป็นรหัส ward ของ รพ. (เช่น 7883) ไม่ตรงรหัส ward ของ nRefer (เช่น "Stroke Unit, 24") — ตอนนี้ map ด้วยชื่อ (WARD_NAMES ใน nrefer_map.py) เฉพาะ 6 ward ของชุมแพ ควรทำเป็น config ไหม
- **Dx ที่ไม่เข้ากลุ่ม DMIS**: TIA→G45, CVT→I67 (ดู DX_MAP) — ยืนยันกับพยาบาล/ขอนแก่นว่าถูกต้อง หรือควรตัดออกจากการส่ง
- **การแก้เคสที่ส่งแล้ว**: ตอนนี้ให้ไปแก้บนเว็บ nRefer ตรงๆ (ปุ่ม "กรอกอีกครั้ง" เปิดฟอร์มเพิ่มข้อมูลใหม่) — ควรทำโหมดเปิดเคสเดิมมาแก้ไหม

---

## 6. วิธีรันของที่มี

```
cd C:\SSCC\app
python mock\test_nrefer.py         # เทสต์กับ nRefer จำลอง (ควรผ่าน)
python server.py                    # เปิดโปรแกรม http://127.0.0.1:8547 → เปิดเคส → ปุ่ม "☁ กรอกฟอร์ม nRefer"
python fill_nrefer.py --cases <id>  # ยิงตรง (จะเปิด Edge จริงไป nRefer จริง — ระวัง ทดสอบให้ปิดโดยไม่บันทึก)
```
สลับปิดฟีเจอร์: `nrefer_enabled: false` ใน `config.json`

---

## 7. Lead ทางเทคนิค (แกะจาก JS ของ nrefer.moph.go.th/beta 2026-09-09)

> bundle ต้นฉบับดาวน์โหลดใหม่ได้จาก `https://nrefer.moph.go.th/beta/` (ดู `<script src>` แล้วโหลด chunk-*.js)
> ตัวหลัก: `chunk-UIVIL3PE.js` (component ฟอร์ม DMIS), `chunk-TO245DYV.js` (service/API), `chunk-HIED3E66.js` (pk-datepicker)

**Auth:**
- token เก็บที่ `sessionStorage["tokenRefer"]` (JWT, มี claim `hcode`, `uid`, `exp`, `expire`) — หายเมื่อปิดเบราว์เซอร์
- HTTP interceptor เติม header `Authorization: Bearer <token>` + `Source-Agent: nRefer-<ver>-<sub>-<hcode>-<ts>-<rand>`
- login ThaID: OAuth redirect — `GET .../thaid/create-thaID-url/...` สร้าง URL, callback `POST .../thaid/login/<YYYYMMDDHHmmss> {state, code, callbackRef, uid}` แล้ว setToken เข้า sessionStorage
- API base: `https://nrefer.moph.go.th/api/beta`

**ฟอร์ม "เพิ่มข้อมูล" (แท็บรายละเอียด → Add new):**
- input ธรรมดา: `name="editRow.hn|an|person_id|vn|prename|fname|lname|tel|los|sbp|dbp|gcs"`, `name="editRow.age[2]"`(ปี) `age[1]`(เดือน)
- radio: `id="editRow.<field><value>"` เช่น `editRow.rtpa1`(ได้รับ=1) `rtpa2`(ไม่=2) `rtpa0`(ไม่ทราบ=0); เหมือนกันกับ ctscan/stroke_unit/surgery/sex(1ชาย 2หญิง)
- select ธรรมดา: `editRow.dx`(ICD), `editRow.dmis`(กลุ่ม: 1 Hemorrhage / 2 Ischemic / 3 Hip / 4 TBI / 5 SCI), `editRow.visit_result`('' ไม่ทราบ /1 ทุเลา /4 ส่งต่อ /9 ตาย), `editRow.carry`('' มาเอง /EMS /FR /RELATE)
- `pk-datepicker`: ในนั้นมี `input.datepicker-input`; parse ตอน event `change`; รับ `dd/mm/yyyy` (พ.ศ. >2400 จะ -543) หรือ ISO; datepicker อยู่ก่อน `input[type=time name="editRow.*_time"]` ในกล่องเดียวกัน (ยกเว้นวันเกิดไม่มี time คู่)
- `pk-select` (mRS/ward): `.pk-select-trigger` เปิด, `.pk-select-search-input` ค้น, `.pk-select-option` เลือก; mRS label = "0. No symptoms"…"6. Death" (code 0-6 ตรงตัว); ward label = "Stroke Unit, 24"
- ปุ่มบันทึก: `<button>บันทึก</button>` → ยิง `POST /dmis/imc/save-patient {data:{...editRow, person_ref, raw_data:JSON}}`; ก่อนหน้ามันเรียก `/save-person` + `/person {where:{hn}}` เอาเลข person_ref

**API ที่ /patient คืน** (ใช้ตอนหาเลข ref อ่านอย่างเดียว): `{statusCode, rows:[{ref, hn, an, admit(ISO UTC!), disc, dx, dmis, person_ref, patient_raw_data, ward, status, ...}]}`
- ⚠️ วันที่จาก API เป็น ISO UTC เช่น `2023-01-07T17:00:00.000Z` = 8 ม.ค. เวลาไทย (ต้อง +7 ก่อนเทียบ — ดู `nr_date` ใน fill_nrefer)
- ⚠️ หน้าทะเบียนกรองด้วยช่วง "วันที่อยู่รักษา" ค่าเริ่มต้น ~6 เดือนล่าสุด → เคสเก่าไม่โผล่ทั้งที่บันทึกแล้ว (เคยเข้าใจผิดว่า "ไม่เข้า")

---

## 8. เอกสาร/ไฟล์อ้างอิงในเครื่อง
- โค้ด: `C:\SSCC\app\nrefer_map.py`, `fill_nrefer.py`, `mock\mock_nrefer.py`, `mock\test_nrefer.py`
- README หมวด "ส่งเข้า nRefer": `C:\SSCC\app\README.md`
- โครง SSCC เดิม (แนวทางกรอกฟอร์มที่ยึดเป็นแบบ): `C:\SSCC\app\fill_sscc.py`
- schema SSCC: `C:\SSCC\app\schema\sscc_fields.json`
