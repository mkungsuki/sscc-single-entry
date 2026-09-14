# ความเห็นของ Claude ต่อรายงานส่งต่อ 2026-09-11 (nRefer form filler)

อ่านจาก `claude-handoff-20260911.md` + เอกสารย่อย + โค้ดปัจจุบันใน `C:\SSCC\app` + JS สาธารณะของ nRefer 5.0.8 (chunk-UIVIL3PE / T5BZUTSZ / HIED3E66)
รันชุดทดสอบของ codex บนเครื่องนี้แล้ว: **40 tests OK (77.8 s)** — ยืนยันว่า suite ผ่านจริง แต่ไม่ใช่หลักฐานเรื่องเว็บจริง (ดูข้อ E)

ไม่ได้แตะเว็บจริง ไม่ได้เปิดฟอร์ม ไม่ได้กดอะไรใน Edge — ความเห็นนี้มาจากการอ่านโค้ดล้วน

---

## A. ข้อบกพร่องที่ยืนยันจากโค้ด (อ่านได้ตรงตัว ไม่ต้องเดา)

### A1. ต้นตอ "พิมพ์ HN แล้ววันที่ล็อก" คือบั๊กของ nRefer เองเมื่อ รพ. ไม่ได้ตั้งค่า HIS — ไม่ใช่ guard ของเรา

เส้นทางในโค้ดสาธารณะ (ตัดจากจริง):

```
input HN  → (change) → checkHN()
checkHN   → yield this.getPerson() ; yield this.getAdmission("hn", hn)
getPerson (component, chunk-UIVIL3PE):
    this.loading = true
    let e = yield this.hisService.getPerson(hn, hcode)     ← ถ้า reject ตรงนี้ บรรทัดล่างไม่ถูกรัน
    if (e.statusCode==200) {...} else toastr.error(...)
    this.loading = false                                    ← ไม่มี try/finally
hisService.getPerson (chunk-T5BZUTSZ):
    return this.token || (yield this.getTokenHis()),
           k(this.http.post(`${this.urlHisRefer}/person`, {...}))   ← ไม่มี try/catch, ไม่มี .catch()
```

- `k` คือ `firstValueFrom/lastValueFrom` (import `i as k` จาก chunk-VJGONYAB) → HTTP error = promise reject
- method อื่นในไฟล์เดียวกัน (getAddress, getAdmission, getDrugOpd…) มี `.catch(l=>l)` หรือ try/catch — **getPerson เป็นตัวเดียวที่ไม่มี** → นี่คือจุดที่ทำให้ `loading` ค้าง
- `urlHisRefer` ถูกตั้งเฉพาะเมื่อ `hisUrl.startsWith("http") && length>10` (ใน `checkHis`) → ถ้า `local_api` ว่าง `urlHisRefer` = `""` → POST ไป `/person` บน origin ของ nRefer → 404 (สอดคล้อง screenshot 404 ที่ `/his/alive`) → reject → `loading` ค้าง
- ตัวที่ผูกกับ `loading` (นับจาก template update block): pk-datepicker + input[type=time] **ทุกช่อง** (`m("disabled", e.loading)` ×9 และ `e.loading || rtpa!=1` ฯลฯ) → ตรงกับอาการ "วันที่/เวลาหลายช่อง disabled แม้กรอกมือ" และ "รอบ 8051 fail ทั้ง 8 date groups แต่ text/number ลงได้" (text/number ผูกกับ `!isOwner` ไม่ใช่ `loading`)
- **ปุ่ม [บันทึก] ไม่ผูกกับ `loading`** — disabled เฉพาะ `!dmis || !hn || !fname || !lname` → หลังค้าง พยาบาลยังกดบันทึกได้ ค่าที่อยู่ใน model แล้วไม่หาย

**ผลที่ตามมา:** guard ของ codex (abort POST ที่ไม่รู้จัก) กับ browser ปกติ (404) ให้ผลเหมือนกันคือ reject → ค้าง ดังนั้น
- การขยาย HIS read allowlist ช่วยไม่ได้เลยเมื่อ `local_api` ว่าง (guard ไม่ใช่ตัวแปร)
- อาการนี้ **ควรเกิดใน Brave/Chrome ปกติของผู้ใช้ด้วย** ถ้า profile นั้นก็ไม่มี HIS config — นี่คือการทดลองชี้ขาดที่ยังไม่มีใครทำ (ดู B1)
- `checkAN` → `checkDup` (OK) → `getAdmission` (มี try/catch, OK) → `getPerson()` อีกรอบ → ค้างซ้ำด้วยเหตุเดียวกัน

### A2. ลำดับกรอกของ `nrefer_ui.fill_form` ทำให้บั๊ก A1 กระทบมากที่สุด
กรอก HN → Tab → AN → Tab **ก่อน** ทุกอย่าง แล้วค่อยวันที่/เวลา/mRS → พอ HN ทำ `loading` ค้าง ช่องวันที่ทั้งหมดถูกล็อกก่อนที่โปรแกรมจะไปถึง → ทุก date step ล้มเหลวเป็นแถบ (ตรงกับ 8051)

### A3. readiness barrier ตรวจแค่ "เครือข่ายเงียบ" ตรวจไม่ได้ว่า `loading` ค้าง
`form_load_barrier`/`wait_his` รอ pending request = 0 แล้วถือว่าพร้อม แต่กรณี A1 request จบด้วย error เร็วมาก เครือข่ายเงียบทันทีในขณะที่ฟอร์มค้างถาวร → โปรแกรมเดินต่อไปกรอกช่อง disabled ทีละช่องจน timeout ต่อกัน (รายงานข้อ 10.3 เห็นถูกแล้ว แต่ยังไม่มีโค้ดตรวจ)

### A4. SaveObserver ไม่มีทางได้ `ref` จาก response จริง
response จริงของ `/save-patient` คือ `{statusCode:200, rows:[], message:"ok"}` (เห็นจากการทดสอบ 2026-09-09) → เงื่อนไข `len(rows)==1` ไม่มีวันจริง → ทุกเคสจะได้สถานะ "ส่งแล้วโดยไม่มีเลข ref" เสมอ การกันซ้ำจึงพึ่งฐานเครื่องอย่างเดียว (รายงานยอมรับแล้ว แต่ควรรู้ว่าเป็น "เสมอ" ไม่ใช่ "บางครั้ง")

### A5. เรื่องเล็กที่ควรรู้: `person_id` fallback
codex ถอด "ใช้ HN แทนเลข ปชช." ออกจาก mapper — ถูกหลัก แต่ตัวเว็บเองทำแบบนั้นตอนกดบันทึกอยู่ดี (`person_id: e.person_id || e.hn` ใน savePatient) ดังนั้นสิ่งที่ nRefer เก็บจะไม่ต่างกัน แค่ไม่ใช่เราเป็นคนตัดสินใจ — ไม่ต้องแก้อะไร แต่เอกสารไม่ควรอ้างว่าแก้ผลลัพธ์ที่เก็บได้

---

## B. สมมติฐานที่ต้อง reproduce (ยังสรุปไม่ได้จากโค้ด)

### B1. (ชี้ขาดที่สุด, ทำโดยผู้ใช้ 2 นาที ไม่บันทึกอะไร)
ใน **Brave ปกติ** ที่ login nRefer อยู่: ทะเบียน → Add new → ลองเปิดปฏิทิน (ควรเปิดได้) → พิมพ์ HN อะไรก็ได้ → Tab → **ปฏิทิน/ช่องเวลายังกดได้ไหม?** แล้วปิดแท็บ
- ล็อกเหมือนกัน → ยืนยัน A1 = บั๊ก nRefer สำหรับ รพ. ไม่มี HIS; ต้องแจ้งกระทรวง/ตั้ง HIS; โค้ดเราแก้ได้แค่ workaround
- ไม่ล็อก → มีตัวแปรที่ต่างกันระหว่าง profile Edge ของโปรแกรมกับ Brave (น่าจะ `local_api` ใน localStorage) → ไปดู Settings → HIS API Connection ของทั้งสอง profile เทียบกัน (ไม่ต้องบอกค่า key ใคร)

### B2. ทำไม live run #10 (ledger 10 ก.ย.) "ผ่านทุก date step" ทั้งที่กรอก HN ก่อน?
ตามโค้ด A1 มันควรค้าง คำอธิบายที่เป็นไปได้: ณ เวลานั้น profile มี `local_api` ตั้งอยู่และปลายทางตอบ JSON (แม้ statusCode≠200 ก็ resolve → loading=false) แล้วต่อมามีการเปิดหน้า Settings ระหว่างรัน (ledger บันทึกไว้) ทำให้ค่าหาย/เปลี่ยน → รอบหลังค้าง **ต้องตรวจ**: ดู localStorage `local_api` ของ profile Edge ตอนนี้ (มีค่าหรือว่าง — ไม่ต้องรายงานค่า) และถามผู้ใช้ว่าเคยกดอะไรในหน้า HIS API Connection

### B3. TS 027
รายงานยังไม่มีสาเหตุ ผมก็ไม่มีหลักฐานเพิ่ม สิ่งที่รู้: login เคยผ่านหลังซิงก์นาฬิกา (`Forbidden (check your clock)` เป็นหลักฐานตรงว่า server ตรวจเวลา) — ถือเป็น "แก้ได้ด้วยซิงก์เวลา" ได้เฉพาะเมื่อไม่เกิดซ้ำอีก 3–5 ครั้งใน 1–2 วัน ห้ามปิดประเด็นจากครั้งเดียว

---

## C. ข้อเสนอแก้ขั้นต่ำ (ไม่แตะ internal ของเว็บ)

### C1. ตรวจ `loading` ค้างแบบตรงๆ แล้วหยุดพร้อมบอกเหตุ (ควรทำก่อนอย่างอื่น)
หลัง HN/AN + wait_his: ถ้า `pk-datepicker input` ตัวแรก (หรือ `input[name="editRow.admit_time"]`) ยัง `disabled` เกิน ~3 วิ → หยุดทันที ข้อความ: "nRefer ล็อกช่องวันที่หลังค้นหา HN (การเชื่อม HIS ของ รพ. ล้มเหลว/ไม่ได้ตั้งค่า) — โปรแกรมกรอกวันที่ให้ไม่ได้ในสภาพนี้" — 5 บรรทัด ตัด timeout ต่อกันทิ้ง และให้ diagnostics ชัดกว่า "date group fail"

### C2. เปลี่ยนลำดับกรอก: HN/AN **ท้ายสุด**
กรอก Dx → text อื่น → radio → **วันที่/เวลา → mRS/ward** → readback → แล้วค่อย HN, AN
- ถ้า A1 เกิด ค่าวันที่อยู่ใน model แล้ว, ปุ่มบันทึกไม่ถูกล็อก, พยาบาลยังบันทึกได้
- ข้อเสีย: หลัง HN พยาบาล**แก้วันที่ไม่ได้** → banner ต้องบอกชัด "ถ้าวันที่ผิด ให้กด 'จบรอบนี้' แล้วแก้ในโปรแกรมก่อนส่งใหม่"
- ระวังลำดับที่ codex เจอเอง: radio ต้องมาก่อน date/time ที่ radio เปิดใช้ (ยังคงไว้)

### C3. (ทางเลือก ต้องให้ผู้ใช้ตัดสิน) ใส่ HN/AN โดยไม่ยิง `change`
ตั้งค่าผ่าน `value` + dispatch `input` (ngModel รับ) โดยไม่ focus/blur → `change` ไม่เกิด → ไม่เรียก HIS → ไม่ค้าง; พยาบาลคลิกเข้าออกช่อง HN โดยไม่แก้ก็ไม่ trigger (change ต้องมีค่าเปลี่ยนระหว่าง focus)
- ไม่ได้แก้ internal ของเว็บ แต่ **ข้ามพฤติกรรม lookup ที่เว็บตั้งใจ** (ซึ่งล้มเหลวอยู่ดีเมื่อไม่มี HIS) — ผิดจากหลัก "type like a user" ของ codex → ต้องให้เจ้าของงานเลือกโดยรู้ trade-off; ถ้า รพ. ตั้ง HIS ในอนาคต ควรกลับไปใช้ change ปกติเพื่อได้ demographic จาก HIS

### C4. หาเลข ref หลังบันทึกด้วยวิธีเดียวกับที่เว็บใช้กันซ้ำ (read-only, ตรงตัว ไม่ใช่ max)
หลัง observer เห็น 200: `POST /dmis/imc/patient {where:{hospcode, an}}` (= `checkDup()` ของเว็บเอง) → ได้ 1 แถว → `ref` ตรง AN — แม่นกว่าคาดหวัง `rows` ใน response save ซึ่งไม่มีวันมา; ถ้าไม่มี AN ให้คง "ส่งแล้วไม่มี ref" ตามเดิม

### C5. เรื่องนอกโค้ดที่แก้ปัญหาจริง
- แจ้งบั๊ก A1 ให้ทีม nRefer (ข้อความสั้น: `getPerson` ใน HIS service ไม่ catch error → `loading` ค้าง ล็อกวันที่ทั้งฟอร์มสำหรับ รพ. ที่ไม่ได้ต่อ HIS; fix ฝั่งเขา = try/finally 1 บรรทัด)
- ถาม IT รพ.ชุมแพ ว่ามี his-connect (`superpck/his-connect` ตามที่ bundle อ้าง) ให้ nRefer ต่อไหม — ถ้ามี ฟอร์มจะทั้งไม่ค้างและเติมชื่อ/วันเกิดให้เอง นี่คือ "วิธีที่ระบบตั้งใจ" ไม่ใช่งานที่ต้องผลักให้พยาบาลตั้ง

---

## D. หลักฐานรับรองที่ยังขาด (ก่อนพูดว่า "พร้อมใช้")

1. ผล B1 จากผู้ใช้ (Brave ปกติ) — ไม่มีอันนี้ ทุกอย่างข้างบนยังเป็นการอ่านโค้ด
2. live no-save **หลัง** C1+C2: 3 เคสต่อเนื่อง คนละ HN/AN, readback วันที่/mRS/ward ผ่านทุกเคส โดยไม่มีคนเปิดหน้า Settings ระหว่างรัน
3. TS 027 ไม่เกิดซ้ำหลายวันหลังซิงก์นาฬิกา (หรือเกิดแล้วอธิบายได้)
4. pilot บันทึกจริง 1 เคสโดยพยาบาลกดเอง + ตรวจว่า record ที่เกิดมี HN/AN/วันที่ตรง และ ref ที่ C4 ดึงมาตรงกับที่เห็นในทะเบียน
5. ยืนยันจากเจ้าของทะเบียน (ขอนแก่น) เรื่อง mapping TIA→G45 / CVT→I67 และการใช้เวลา C5 เป็นเวลา CT — ตอนนี้เป็นการเดาของเราทั้งคู่ (ผมเป็นคนเริ่ม, codex ทำเป็น "ต้องยืนยัน" แล้ว ถูกต้อง)

---

## E. ท้วง mock/เทสต์ที่เลียนแบบ implementation มากไป

- `nrefer_widgets.js` + test "rejected HIS read → date disabled": จำลอง **สมมติฐานของ codex** (guard บล็อก HIS read) ไม่ได้จำลอง **สภาพจริงของชุมแพ** (ไม่มี `local_api` → request ไป origin nRefer → 404 โดยไม่เกี่ยว guard) → เทสต์ผ่านหลังเพิ่ม allowlist จึงเป็น "ผ่านโดยการสร้าง" ไม่ได้บอกว่า live จะหาย (และ live ก็ไม่หายจริงตามรายงาน) ควรเพิ่ม fixture: base ว่าง + POST `/person` บน origin mock ตอบ 404 → คาดหวังว่าโปรแกรม **หยุดพร้อมข้อความ C1** ไม่ใช่กรอกต่อ
- mock ไม่มี `loading` flag ที่ผูกกับ **ทุก** date/time control พร้อมกัน — ของจริงล็อกเป็นชุด mock ล็อกตาม radio เท่านั้น → เทสต์ "date steps" ผ่านง่ายเกินจริง
- `SaveObserver` test ที่คืน `rows:[{ref,hn,an,hospcode}]` ตรง identity: response จริงไม่มี rows แบบนั้น → เป็นการทดสอบ branch ที่ไม่มีใน production ควรเพิ่มเคส `rows:[]` เป็นเคสหลัก (คงมีแล้วในชื่อ "ผลยืนยันไม่ได้" แต่ต้องเป็นค่า default ไม่ใช่ edge)
- 40 tests ผ่านบนเครื่องนี้จริง แต่ coverage ที่ตรงกับ blocker ปัจจุบันมี 0 ข้อ เพราะยังไม่มี fixture "HIS ว่าง" — ตัวเลข 40 จึงไม่ควรใช้อ้างความพร้อม

---

## F. สิ่งที่ผมไม่ได้ตรวจ (บอกไว้กันเข้าใจผิด)
`browser_session.py`, `case_form.py`, การแก้ `server.py`/`db.py` (claim/reconcile/state), `templates/*` รอบ codex, `runlock.read_session` — อ่านแค่ผ่านตา ไม่ได้ไล่ logic; ข้อ 10.6 ของรายงาน (lifecycle guard/queue) จึงยังไม่มีความเห็นจากผม

## ผล B1 (อัปเดต 2026-09-11 หลังผู้ใช้ทดลอง)
**ยืนยันแล้ว** — ใน Brave ปกติ (ไม่มี Playwright ไม่มี guard) กด Add new → พิมพ์ HN → spinner ค้าง ช่องวันที่/เวลาล็อกทั้งฟอร์ม เหมือนใน Edge ของโปรแกรมทุกประการ
→ A1 เป็นบั๊กของ nRefer สำหรับ รพ. ที่ไม่ได้ต่อ HIS; ไม่มีตัวแปรฝั่งเรา; codex **ไม่ต้องไล่ guard / profile / HIS allowlist ต่อ** ปิดประเด็นนั้นได้
→ ข้อสังเกตสำคัญ: พยาบาลชุมแพ**คีย์มือ**ก็ติดเหมือนกัน ถ้าพิมพ์ HN ก่อนจะกรอกวันที่ไม่ได้เลย — ต้องแจ้งกระทรวง (C5) ไม่ว่าโปรแกรมเราจะทำอะไร

## ลำดับที่แนะนำ (หลัง B1 ยืนยัน)
1. C1 (ตรวจ disabled แล้วหยุดพร้อมบอกเหตุ) + C2 (HN/AN ท้ายสุด) — เจ้าของงานตัดสินใจ C3 แยก
2. fixture ข้อ E: HIS ว่าง → POST `/person` บน origin mock ตอบ 404 → คาดหวังพฤติกรรม C1/C2 ไม่ใช่ "ผ่านเพราะ allowlist"
3. live no-save 3 เคส (ห้ามเปิด Settings ระหว่างรัน) → ตรวจว่าวันที่ทั้งหมดอยู่ใน model ก่อน HN และปุ่มบันทึกยังกดได้
4. คู่ขนาน: แจ้ง nRefer/กระทรวง (ข้อความใน C5) + ถาม IT ชุมแพเรื่อง his-connect — อันนี้แก้ที่ต้นเหตุ โปรแกรมเป็นแค่ทางหลบ
