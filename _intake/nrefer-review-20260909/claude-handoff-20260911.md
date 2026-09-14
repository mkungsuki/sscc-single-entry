# SSCC → nRefer: รายงานส่งต่อให้ Claude ประเมิน

วันที่ 11 กันยายน 2026 · Workspace `C:\SSCC` · โปรแกรม `C:\SSCC\app`

รายงานนี้รวบรวมการตรวจ แก้ไข ทดสอบ และข้อสังเกตของผู้ใช้ช่วง 9–11 กันยายน 2026 เพื่อให้ผู้ประเมินตรวจต่อจากหลักฐาน ไม่ต้องเริ่มเดาสาเหตุใหม่ ใช้อ่านคู่กับโค้ดปัจจุบันและรายงานย่อยท้ายเอกสาร

**สถานะรวม: ยังไม่พร้อมรับรองใช้งานจริงเต็มรูปแบบ** เคยกรอกข้อมูลสมมติผ่าน Python worker ลงเว็บ nRefer จริงได้จน final readback ไม่มี field failure warnings แต่รอบล่าสุดยังเกิดฟอร์มค้างหลังกรอก HN แม้พิมพ์ด้วยมือ ช่องวันที่ใช้งานไม่ได้ การแก้ guard ล่าสุดยังไม่ทำให้อาการจริงหาย

การเขียนรายงานครั้งนี้ไม่ได้รันทดสอบใหม่ ไม่รีสตาร์ตแอป ไม่เปลี่ยนฟอร์มที่ผู้ใช้เปิด และไม่กดบันทึกเว็บจริง ตัวเลขผลทดสอบด้านล่างเป็นผลที่บันทึกไว้ในรอบก่อนหน้า ไม่ใช่การรับรอง runtime ขณะเปิดอ่านรายงาน

## 1. เป้าหมายและข้อตกลงกับผู้ใช้

- พยาบาลกรอกข้อมูล stroke ในโปรแกรมท้องถิ่นครั้งเดียว แล้วให้โปรแกรมช่วยกรอก SSCC และ nRefer → Service Plan → Stroke & IMC → DMIS
- หน้าปลายทาง nRefer คือ `https://nrefer.moph.go.th/beta/#/dmis/patient` ตรวจพบเวอร์ชัน 5.0.8 ระหว่างงาน
- ผู้ใช้ตรวจฟอร์มและกดบันทึกเอง ห้ามตัวกรอกกด Save หรือเรียก API เขียนข้อมูลแทน
- ทดสอบเว็บจริงด้วยข้อมูลสมมติในโหมดไม่บันทึก ไม่ใช้ mock ผ่านเป็นเหตุให้ทดลองบันทึกข้อมูลผู้ป่วยจริง
- ใช้งานหลายเคสต่อกันโดยคงเบราว์เซอร์ ไม่ปิดให้สแกน ThaID ใหม่ทุกเคส แต่ไม่ข้ามการหมดอายุ session ที่เซิร์ฟเวอร์กำหนด
- UX ต้องเหมาะกับคนคีย์: ไม่ถามข้อมูลซ้ำโดยไม่จำเป็น, GCS รวมกับคะแนนย่อยต้องอยู่ด้วยกัน, ICD ต้องมีชื่อ, สถานะต้องอ่านรู้เรื่อง
- เคสทดสอบที่ผู้ใช้ขอให้สร้างไม่ใช้การผ่าตัด ไม่ได้หมายถึงตัดความสามารถเรื่องผ่าตัดออกจากระบบทั้งหมด

ใบส่งต่อเดิมระบุว่ารุ่นก่อนเคยสร้าง nRefer record ผ่าน API โดยไม่ผ่านการตรวจ และลบแล้ว เรื่องการลบเป็นข้อมูลจาก handoff เดิม ไม่ได้ตรวจซ้ำในงานนี้ รายงานนี้ไม่ถือว่าการกระทำดังกล่าวเป็นแนวทางที่ใช้ต่อได้

## 2. ผลตรวจโค้ดแรกเริ่มและสิ่งที่แก้

| ประเด็นที่พบ | การเปลี่ยนแปลง | ขอบเขตหลักฐาน / สิ่งที่ยังเหลือ |
|---|---|---|
| รับ response Save ที่ดูสำเร็จโดยไม่ผูกคนและครั้งรักษา แล้วหา ref สูงสุดจาก HN | แยก `nrefer_save.py`; ตรวจ request/response ตาม origin, method, endpoint และ HN+AN+หน่วยงาน; ไม่เลือก ref สูงสุดแบบเหมารวม | มี observer tests กรณีคนละ admission, หน่วยงานผิด, HTTP error, บันทึกบางส่วน และผลยืนยันไม่ได้; ยังไม่ได้ pilot บันทึกจริง |
| ส่งซ้ำเรียก Add new แต่ UI เรียกว่าอัปเดต | กันเคสที่มี ref/สถานะไม่แน่ชัด, ตรวจซ้ำใน DB ด้วย transaction, deduplicate คิว, ให้ตรวจทะเบียนก่อนคืนสถานะ | กันซ้ำในเครื่อง ไม่ใช่หลักฐานว่าไม่มี record จากเครื่องอื่น; ยังไม่มี automatic edit flow |
| เอา HN แทนเลขประชาชนเมื่อไม่ทราบ | ยกเลิกการสร้างเลขประชาชนจาก HN | ต้องตรวจความหมาย person_id ของเว็บแยกจากเลขประชาชน ห้ามเปลี่ยนข้อมูลระบุตัวตนเพื่อให้ผ่านฟอร์ม |
| เวลาไม่ทราบกลายเป็น 00:00 | คง unknown/ว่างและแจ้งข้อมูลขาด | ทดสอบวันที่ผิดและเวลาไม่ทราบ |
| C5 ซึ่งหมายถึง CT และ/หรือ MRI ถูกแปลงเป็นได้ CT | แยกข้อมูล CT และให้เลือกใช้เวลา C5 ร่วมอย่างชัดเจน | ต้องไม่ตีความ MRI-only เป็น CT; ผู้ใช้ยืนยันการใช้ร่วม |
| มีวันจำหน่ายแล้วสมมติทุเลา, EMS แบบรวมถูกเดาว่า EMS รพ. | ไม่แต่งผลจำหน่าย/ชนิดผู้นำส่ง; ใช้ข้อมูลเดิมเมื่อความหมายตรงหรือถามเพิ่ม | เจ้าของทะเบียนยังต้องรับรอง mapping โดยเฉพาะ TIA/CVT และรายการเฉพาะหน่วยงาน |
| กรอกแล้วไม่ตรวจกลับ, HIS อาจตอบมาทับ | เพิ่ม readback, รอคำขอ, หยุดเมื่อ identity ไม่ตรง, แจ้งช่องที่กรอกไม่ได้ | เครือข่ายเงียบไม่ได้แปลว่า Angular loading จบ; ยังเป็นช่องโหว่สำคัญของ readiness |
| auto-confirm สำหรับ mock อยู่ใน production path และเช็ก localhost ด้วย substring | ย้ายการกด Save จำลองไป test harness; production nRefer ไม่มี auto-confirm | ทดสอบ Save จำลองเฉพาะ localhost ไม่ใช่การกด Save จริง |
| malformed token ถูกยอมรับจากการตรวจแบบหลวม | เพิ่มการตรวจ token ที่เสีย/หมดอายุ | decode token ไม่เท่ากับยืนยันว่า server รับ session; ไม่ใช่หลักฐานต้นเหตุ TS027 |
| preview ใส่ข้อมูลผู้ป่วยผ่าน innerHTML | เปลี่ยนการแสดงค่าให้เป็นข้อความอย่างปลอดภัย | มี template/JavaScript tests; ให้ผู้ประเมินตรวจเส้นทางแสดงผลอื่นด้วย |
| tests เดิมใช้ DB แอปและลบด้วย HN | ใช้สำเนา source/config/DB/profile ชั่วคราว และ mock services | ไม่คัดลอกฐานผู้ป่วยหรือความลับเข้า test fixture |

รายละเอียดข้อค้นพบเดิม F1–F7 และโพรบอยู่ใน `review-and-plan.md` เลขบรรทัดในเอกสารนั้นเป็นของโค้ดก่อนแก้ ห้ามใช้เป็นตำแหน่งปัจจุบันโดยไม่ค้นใหม่

## 3. ลำดับเหตุการณ์ login และ guard

1. Handoff เดิมติด ThaID TS027 และเคยถอด token injection แล้ว อาการยังมี จึงยังไม่ทราบต้นเหตุ TS027 ห้ามสรุปว่า automation flag หรือ token injection เป็นสาเหตุที่พิสูจน์แล้ว
2. ผู้ใช้พบ callback ไป Not found แล้วต่อมาเข้าได้เอง แสดงว่า login เคยผ่านจริง แต่ยังไม่มี controlled comparison ที่อธิบายความไม่แน่นอนได้
3. Worker รอบแรกเข้าได้แล้ว timeout; logging เดิมไม่ระบุขั้นตอน จึงเพิ่ม stage diagnostics
4. รอบถัดมาผู้ใช้เห็น API expire/เด้งออก ตรวจพบว่า no-save guard บล็อก POST ที่จริงเป็นคำขออ่าน/ตรวจ session ได้แก่ `user/user-status`, `user/user-by-key`, `admin/thaid/authenticated` รวม reference lookups บางส่วน
5. อ่าน public JavaScript ก่อนอนุญาต method/path เหล่านั้น เป็นข้อบกพร่องของ guard เราจริง แต่ไม่อธิบาย TS027 ทั้งหมด
6. ผู้ใช้พบ `Forbidden (check your clock)` วัดเวลาพบเครื่องช้ากว่าแหล่งเทียบประมาณ 2.51 วินาที, timezone ถูกต้อง; W32Time service หยุดอยู่
7. เริ่ม service ไม่ได้เพราะสิทธิ์ Windows ไม่พอ ผู้ใช้กด Sync now เอง วัดภายหลัง offset ใกล้ศูนย์ประมาณ -0.0009 ถึง +0.0016 วินาที แม้ query service ยังบอก stopped ดังนั้นห้ามใช้ service status เพียงอย่างเดียวตัดสินว่าซิงก์ไม่สำเร็จ
8. หลังซิงก์ รอบใหม่ล็อกอินและกรอกผ่าน แต่ความสัมพันธ์ตามเวลาไม่พิสูจน์ tolerance หรือกลไก rejection ของ server
9. Ward ไม่แสดงรายการ เพราะยังบล็อก POST `/libs/lib-ward`; เพิ่มเฉพาะ read endpoint หลังตรวจ public service definition โดยยังบล็อก save ward
10. รอบ live ถัดมา final readback ไม่มี field failure warnings รวม HN, Ward, dates, mRS และ GCS total มีเพียง mapping reminders ไม่มีการกด Save

ข้อเรียนรู้: no-save mode สามารถรบกวนการทำงานของเว็บได้ เพราะ POST ไม่ได้แปลว่าเขียนข้อมูลเสมอ ต้องตรวจแต่ละ endpoint; ในทางกลับกัน ห้ามปลดบล็อก POST ทั้งหมดเพียงเพื่อให้ฟอร์มทำงาน

## 4. การกรอก widget จริง

- Diagnosis เป็นตัวให้เว็บคำนวณกลุ่มโรค ใช้ readback ตรวจแทนกรอกช่องกลุ่มที่ disabled
- วันที่ใช้ keyboard interaction และตรวจวันที่ selected ในปฏิทิน รองรับ พ.ศ./ค.ศ. และวันเกิดเก่ากว่าช่วงปี dropdown; ไม่ใช้การยัด model ภายใน Angular เป็นทางลัด
- GCS E/V/M ใช้ keyboard เพื่อกระตุ้นพฤติกรรมคำนวณจริง พบว่า fill อย่างเดียวไม่ทำให้ยอดรวมเปลี่ยนในบางเส้นทาง ไม่กรอก total ที่ readonly และไม่ย้อนเดา E/V/M จาก total
- ตั้ง radio ก่อนวันที่/เวลาที่ radio เปิดใช้งาน
- เลือก Ward/mRS จากรายการจริง และตรวจกลับ กรณีไม่มีรายการตรงต้องแจ้ง ไม่เลือกค่าที่ใกล้เคียงโดยเดา
- ไม่เติมข้อมูลที่ไม่ทราบให้ดูครบ วันที่ที่ไม่มีเวลาต้องไม่กลายเป็นเที่ยงคืนเอง
- เคยมี live run ผ่านทั้งหมด แต่พฤติกรรมรอบล่าสุดไม่ผ่าน จึงไม่ถือว่างาน widget ถูกปิดแล้วทุกเงื่อนไข

## 5. HN/AN ว่าง: แก้ race แต่ไม่ใช่ปัญหาเดียวกับฟอร์มค้าง

ผู้ใช้พบต้นทางมี HN/AN แต่ปลายทางว่าง ทั้งที่ชื่อและข้อมูลอื่นกรอกแล้ว ผู้ใช้พิมพ์ HN ตัวเดิมเองแล้วกด Tab ค่ายังค้าง จึงไม่มีหลักฐานว่าเว็บปฏิเสธ HN แบบตัวอักษรใน interaction นั้น

Public `getStrokePatient()` รอ `getEvaluateChoice()` ก่อนสร้าง/แทน `editRow` ของรายการใหม่ แต่ตัวกรอกเดิมรอเพียง input HN มองเห็น และเริ่มติดตาม request หลังเปิดฟอร์มแล้ว จึงพลาด request ที่เริ่มก่อนหน้าได้

แก้โดยติด request tracker ก่อน navigation/Add new รอ fetch/XHR จบและ quiet หนึ่งวินาทีก่อนพิมพ์ ถอด listeners ใน finally รอ lookup หลัง HN และ AN แยกกันและตรวจ identity ถ้าค่าเปลี่ยนต้องหยุด ไม่พิมพ์ทับซ้ำอัตโนมัติ

Mock delayed-initialization ทำให้เทสต์ล้มก่อนแก้และผ่านหลังแก้ Live screenshot รอบต่อมา HN/AN ปรากฏแล้ว อย่างไรก็ตามยังไม่ได้จับ runtime trace ของ editRow reset ในรอบจริงที่เคยว่าง จึงอ้างได้ว่าแก้ race ที่พิสูจน์ใน reproduction และอาการ live ดีขึ้น ไม่ใช่พิสูจน์ต้นเหตุทุกครั้งที่เคยเกิด

## 6. คงเบราว์เซอร์และใช้ต่อเนื่องหลายเคส

ผู้ใช้ย้ำว่าให้สแกนมือถือใหม่ทุกเคสไม่เหมาะกับงานจริง จึงเพิ่ม `browser_session.py` ให้ Playwright มี owner thread เดียว คง persistent context และแท็บแยก SSCC/nRefer งานใหม่จากหน้าแอปใช้แท็บเดิม

- บันทึกที่ยืนยันแล้วกลับ idle โดยไม่ปิดเบราว์เซอร์
- ระหว่าง working/review/held ไม่ให้ job ใหม่ทับฟอร์มเดิม
- “จบรอบนี้ — คงเบราว์เซอร์ไว้” ยุติ review โดยผู้ใช้รับทราบว่าจะทิ้งข้อมูลที่ยังไม่บันทึกและยกเลิกคิวที่เหลือ
- โหมดตรวจต้องคง guard ตลอดเวลาที่ฟอร์มเปิด; กลับทะเบียนก่อนถอด guard เฉพาะงานนั้น ถ้ากลับไม่ได้ให้ปิดแท็บนั้นก่อนถอด
- กัน CLI/worker อื่นเปิด profile เดียวกันพร้อมกัน
- ไม่คัดลอก/ฉีด token; เส้นทาง SSCC ผ่าน session manager ไม่ export/restore legacy cookie file
- CLI และ isolated inspection tools ยังเป็น one-shot อย่าใช้มันสรุปพฤติกรรม workflow ต่อเนื่องของปุ่มในแอป

ทดสอบ local mock ด้วยตัวกรอกจริงทั้งสองระบบ 3 jobs คนละเคส ใช้แท็บเดิมและ session marker เดิม nRefer เรียก login routine ครั้งเดียว และตรวจ HN/AN แตกต่างถูกต้องแต่ละรอบ **ยังไม่ผ่านการพิสูจน์ 3 เคสต่อเนื่องบนเว็บไซต์จริง** และไม่รับรอง session ตลอดวันหรือหลังแอป restart

ข้อความ “มีการส่ง SSCC/nRefer ทำงานค้างอยู่” ที่ผู้ใช้พบสัมพันธ์กับ busy/review lock ไม่ใช่หลักฐานว่าข้อมูลส่งสำเร็จ ต้องอ่าน state และจบรอบเดิมอย่างชัดเจน ไม่ปลด lock แบบลบทิ้งทุกครั้ง

## 7. UX หลังผู้ใช้ตรวจ

ผู้ใช้พบแบบฟอร์มส่วน nRefer แยกเป็น appendix ยาว ทำให้ถามข้อมูลที่เคยกรอกและต้องเลื่อนตาม GCS หลายจุด แก้ด้วย `case_form.arrange()` จัด field เดิมเข้ากลุ่ม ไม่เปลี่ยนชื่อ stored keys หรือ rewrite ข้อมูลผู้ป่วย

- AN อยู่ใกล้ HN, วันเกิดใกล้อายุ, ผู้นำส่งใกล้ EMS
- GCS รวมและ E/V/M อยู่ panel เดียว BP อยู่ใกล้กัน; E/V/M ครบและถูกต้องคำนวณ total; total-only ยังใช้ได้; ค่าเดิมขัดกันให้ผู้ใช้ยืนยัน ไม่แก้เงียบ ๆ ตอนเปิดฟอร์ม
- CT/Stroke Unit/ผ่าตัด อยู่กับคำถามคลินิกที่สัมพันธ์กัน วันที่ผ่าตัดไม่ใช่ข้อบังคับของเคสทดสอบ
- Ward และ diagnosis ที่ map ได้แสดงแหล่งข้อมูลเดิม ไม่ถามซ้ำ; explicit overrides เดิมยังอยู่และตรวจได้
- ชื่อ ICD I60–I69 แสดงร่วมรหัส; TIA/CVT ยังต้องเจ้าของทะเบียนยืนยัน ไม่สร้าง diagnosis inference ใหม่
- เวลา CT เลือกใช้ C5 ร่วมได้เมื่อผู้ใช้ยืนยันว่าเป็น CT; สลับตัวเลือกไม่ลบข้อมูล override เก่า
- เวลาเข้า Stroke Unit ที่ใช้จาก admission แสดงวันที่/เวลาจริง ไม่ให้ผู้ใช้ต้องเดาว่าใช้ค่าไหน

อีกปัญหาคือ panel คืนสถานะ nRefer หน้าตาเหมือน error และปรากฏแม้กำลังกรอกตามปกติ จึงเปลี่ยนให้ซ่อนเริ่มต้นและแสดงเมื่อ browser job จบและสถานะเคสยังต้องตรวจผล, ใช้ภาษาคนคีย์, จัด checkbox/label ให้อยู่ด้วยกัน, ซ่อนเลขอ้างอิง optional ไว้ในรายละเอียด การยืนยันนี้เปลี่ยนสถานะเฉพาะแอปท้องถิ่น ไม่ได้บันทึก nRefer ให้

การแก้ UI/guard ล่าสุดถูกโหลดโดย restart รอบที่ browser status เป็น closed ตามบันทึก ส่วนเอกสารเก่าที่บอก “ยังรอ restart” เป็นสถานะ ณ เวลานั้น ไม่ใช่สถานะสุดท้าย

## 8. Blocker ปัจจุบัน: พิมพ์ HN แล้ววันที่ล็อก

### หลักฐาน live จากผู้ใช้

- เริ่มหน้าใหม่ยังเปิด calendar และเลือกวันได้
- พิมพ์ HN แล้ว spinner ค้าง วันที่/เวลาหลายช่อง disabled แม้พยายามกรอกด้วยมือ
- HN แบบตัวเลขก็ทำให้พบอาการ จึงไม่ควรมุ่งแก้เฉพาะรูปแบบ TEST... ของ mock
- รอบ 8051 หลัง HN/AN แก้แล้ว worker เคยรายงาน failure ของ date groups ทั้งแปด รวมวันเกิดและ Stroke Unit ขณะที่ข้อความ/ตัวเลขบางส่วนลงได้
- รอบ 8052 หลังแก้ HIS read allowlist ผู้ใช้ยังแจ้งเหมือนเดิม
- หน้า HIS API Connection แสดง checks fail, ช่อง HIS API/Request Key ดูว่าง และ JSON response เป็น 404 จาก `https://nrefer.moph.go.th/his/alive`

### Source trace ที่พบ

Public `chunk-UIVIL3PE.js`:

```text
checkHN → await getPerson → getAdmission("hn", hn)
getPerson → loading=true → await hisService.getPerson(...) → loading=false
date controls → disabled อิง loading (และเงื่อนไขเฉพาะช่อง)
```

ในเส้นทางที่อ่านพบ ไม่มี try/finally ครอบ await ให้ reset loading เมื่อ reject จึงมีทางที่ lookup ล้มเหลวแล้วฟอร์มติด loading

Public `chunk-T5BZUTSZ.js`:

- HIS base มาจาก localStorage config; ถ้าไม่พบเป็น empty string
- person lookup ใช้ POST ไป `<HIS base>/<HIS name หรือ refer>/person`
- คำขออ่านอื่นรวม admission/service/diagnosis-ipd
- alive ใช้ `<HIS base>/his/alive`; ถ้า base ว่าง URL จะตกบน origin ของ nRefer ซึ่งสอดคล้องกับ screenshot 404

Public config `chunk-HIED3E66.js` ยืนยันชื่อ config `local_api` และ `request_local_api`; ห้ามส่งออกค่าความลับหรือขอ Request Key จากผู้ใช้เพื่อใส่รายงาน

### สิ่งที่แก้ไปแล้ว

`nrefer_guard.py` รับ HIS base ที่ browser ตั้งอยู่ อนุญาตเฉพาะ POST read สี่รายการ person/admission/service/diagnosis-ipd บน origin/path ของ base นั้น จำกัดรูปแบบหนึ่ง segment ของ HIS name ปฏิเสธ base ที่ทับ nRefer API และยังบล็อก writes/unknown requests ไม่คืน response ปลอม ไม่บังคับ enabled หรือแก้ Angular loading

Mock จำลอง rejected HIS read ทำให้ date disabled ค้างก่อนแก้ และกลับกรอกได้เมื่อ allowlist อนุญาต read เป็นการยืนยันกลไกใน reproduction **ไม่ใช่หลักฐานว่าจับ request ที่เสียจริงได้แล้ว**

### ข้อสรุปที่อนุญาต / ไม่อนุญาต

- ยืนยันได้ว่า guard เดิมมีข้อบกพร่องในการบล็อก read และ source มีเส้นทาง loading ค้าง
- 404 กับช่อง config ดูว่างสอดคล้องกับ HIS base ขาด/ผิดใน browser profile นี้ แต่ยังไม่พิสูจน์ค่าจริงหรือความต่างกับ browser ปกติ
- ยังสรุปไม่ได้ว่าโรงพยาบาล HIS ล่ม, key ผิด, HOSxP มีปัญหา, หรือ nRefer DMIS บังคับเชื่อม HIS จึงกรอกเองได้
- HIS เป็นคำรวมระบบข้อมูลโรงพยาบาล HOSxP เป็นผลิตภัณฑ์หนึ่ง Login nRefer กับการเชื่อม HIS เป็นคนละเรื่อง ไม่ควรผลักงานตั้งค่าให้พยาบาลทุกครั้ง
- การแก้ allowlist ไม่สร้างการเชื่อม HIS ที่ยังไม่ได้ตั้งค่า และอาการ live ยังไม่หาย
- บางรอบผู้ใช้เปิดหน้า settings ระหว่าง worker กำลังกรอก ทำให้รอบนั้นไม่ใช่ final-readback test ที่สะอาด ต้องแยกเหตุการณ์นี้จากการพิมพ์มือบนฟอร์มแล้วค้าง

## 9. เคสสมมติและผลทดสอบ

| เคส local | หน้าที่ |
|---|---|
| 8001 | เคสเดิมของผู้ใช้ ไม่ถือเป็น disposable fixture และไม่ควร overwrite |
| 8051 | “ทดสอบครบ ห้ามบันทึกจริง”; HN TEST26091001, AN TESTAN26091001; complete no-surgery fixture |
| 8052 | “ทดสอบต่อเนื่องสาม ห้ามบันทึกจริง”; HN TEST26091103, AN TESTAN26091103; เพิ่มใหม่เพื่อทดสอบต่อเนื่อง ไม่แก้ทับสองเคสก่อน |

Fixtures อยู่ใน `synthetic-full-no-surgery.json` และ `synthetic-third-no-surgery.json` มี marker ข้อมูลสมมติ เคส 8052 สร้างโดยไม่ใส่เลขประชาชนและตรวจ timeline แล้ว แต่ข้อมูลบนฟอร์มสดอาจถูกผู้ใช้แก้ต่อได้ ห้ามถือว่า fixture เท่ากับค่าปัจจุบันทุกช่อง

การสร้างเคสข้างต้นเป็นการบันทึกในแอปท้องถิ่น ไม่ใช่สร้าง record ใน nRefer ไม่มี production Save โดย agent ในรอบตรวจนี้

ผล suite ตามลำดับ: 27 → 33 → 36 → 37 → **40 tests passed (75.944 วินาที)** หลัง HIS guard และ UX ล่าสุด มี targeted test ต่อเนื่องพร้อมตรวจ HN/AN แต่ละรอบผ่านเพิ่มเติม (20.541 วินาที) ตัวเลขเพิ่มตามงาน ไม่ใช่เทสต์แยก 40 ชุดบนระบบจริง

คำสั่งสำหรับผู้ประเมิน จาก `C:\SSCC\app`:

```powershell
& C:\Users\kanpi\anaconda3\python.exe -X utf8 mock\test_nrefer.py
```

Coverage รวม mapping/unknown/date validity, GCS conflict/keyboard, datepicker selection, UI grouping/preservation, initialization race, delayed HIS, guard restrictions/save blocked ก่อน mock server, save identity/uncertain state/reconcile, queue/lock และ 3 jobs ต่อเนื่องทั้งสองระบบ

ข้อจำกัด: mock ไม่ใช่ Angular app ทั้งตัว, auth จำลองไม่พิสูจน์ ThaID, tests ของ loading ใช้ reproduction ย่อ, ไม่พิสูจน์ expiry ของ server จริง, ไม่ได้ยืนยัน round-trip บันทึกจริง ระหว่างพัฒนามี sandbox launch failures ที่เกิดก่อน test behavior และ suite ผ่านเมื่ออนุญาตเปิด browser; อย่านับ launch failure เป็น app regression โดยไม่อ่านสาเหตุ

## 10. แผนให้ Claude ประเมินต่อ

1. **ตรวจสมมติฐานก่อนแก้อีก:** อ่านเส้นทาง HN → HIS → loading และ guard ปัจจุบัน เทียบกับ ordinary nurse browser ภายใต้การ login ปกติ ว่าพิมพ์ HN แล้วค้างเหมือนกันหรือเฉพาะ profile ของโปรแกรม
2. เก็บ diagnostics แบบไม่เปิดเผยข้อมูล: มี HIS config หรือไม่, operation ที่ถูก block, HTTP status ของ lookup, loading/date-disabled ก่อนและหลัง HN พร้อมเวลาตรงกัน ห้าม dump headers/token/key/payload ผู้ป่วย หรือ URL ที่มี secret ใน path/query
3. แยก network quiet ออกจาก UI ready: ตรวจว่า request จบด้วย error แต่ loading ค้างหรือไม่ ให้ filler หยุดและบอกเหตุผลเร็ว แทนพยายามกรอกวันที่ disabled ทุกช่องจน timeout ต่อกัน
4. ถ้าเป็น config ขาด ให้ยืนยันวิธีใช้งาน DMIS แบบ manual และวิธีตั้งค่าจากผู้ดูแล/เอกสารก่อน อย่าคัดลอก token หรือ Request Key จาก personal browser แบบเหมารวม และอย่าประกาศว่าพยาบาลต้องตั้ง HIS จึงใช้ได้โดยยังไม่มีหลักฐาน
5. ตรวจ allowlist ทั้ง auth/reference/HIS ว่า scope แคบและครบพอ ไม่ขยายเป็น arbitrary POST, ไม่ mock HIS success บน production, ไม่แก้ loading ภายในเว็บเพื่อกลบ error
6. ตรวจ lifecycle ของ manager/guard ว่าไม่มี form ที่ยังเปิดอยู่แต่ guard หลุด, ไม่มีการทิ้ง review เงียบ ๆ, ไม่มี queued job ทับ admission เดิม และ app restart ไม่กลายเป็นวิธีแก้ประจำวัน
7. เมื่อแก้ได้ ทดสอบเว็บจริง no-save 3 เคสต่อเนื่อง: คนละ HN/AN, วันที่/เวลา, diagnosis, Ward, GCS, CT/SU, mRS ตรง, แก้มือได้, กลับพร้อมรับเคสถัดไป, session ไม่ถูกโปรแกรมปิดเอง ต้องบันทึกผลแยกแต่ละเคส
8. จากนั้นจึงประเมิน pilot บันทึกจริงโดยผู้ใช้เป็นคนกด พร้อมตรวจ record/ref/ครั้งรักษา ไม่มีการอนุญาต Save จริงจากการขอรายงานฉบับนี้

ขอ Claude ให้ความเห็นโดยแยก “ข้อบกพร่องที่ยืนยันจากโค้ด”, “สมมติฐานที่ต้อง reproduce”, “ข้อเสนอแก้ขั้นต่ำ” และ “หลักฐานรับรองที่ยังขาด” พร้อมท้วง mock ที่เลียนแบบ implementation มากเกินไป ไม่ควรตอบเพียงว่าทดสอบผ่านแล้วพร้อมใช้งาน

## 11. แผนที่โค้ดและเอกสาร

| ไฟล์ใน `C:\SSCC\app` | หน้าที่ |
|---|---|
| `nrefer_map.py` | source → mapping/form values, unknowns และ semantic notes |
| `nrefer_ui.py` | readiness, HN/AN settle, widgets, readback |
| `nrefer_guard.py` | no-save allowlist และ lifecycle handle |
| `nrefer_save.py` | ยืนยันผล Save ที่ผู้ใช้กดให้ตรง admission |
| `fill_nrefer.py` | login/open/add/fill/review/observe orchestration |
| `browser_session.py` | persistent owner thread, tabs, queue/state/finish |
| `fill_sscc.py`, `runlock.py` | SSCC integration และ lock ownership |
| `server.py`, `db.py` | routes, claim/reconcile/status, local state |
| `case_form.py`, `templates/form.html`, `templates/base.html`, `templates/list.html` | clinical grouping, progress/recovery/preview UX |
| `schema/custom_fields*.json` | ฟิลด์เพิ่มเติมโดยเก็บ stored keys เดิม |
| `mock/test_nrefer.py`, `mock/test_nrefer_cases.py`, `mock/test_browser_session_cases.py` | isolated test runner และ regression tests |
| `mock/live_nrefer_inspection.py` | isolated one-shot live no-save inspection; ไม่ใช่ workflow ต่อเนื่องของแอป |

เอกสารย่อยใน `C:\SSCC\_intake\nrefer-review-20260909`:

- `review-and-plan.md`: audit เริ่มต้น F1–F7 และแผน
- `implementation-result.md`: ชุดแก้หลักและผล 27 tests
- `live-ui-observations.md`, `live-worker-ledger.md`: หลักฐาน widget/login/clock/guard รอบจริง
- `persistent-browser-result.md`: session lifecycle และข้อจำกัด
- `form-ux-result.md`: grouping/duplicate fields/ICD/GCS
- `hn-an-initialization.md`: race/reproduction/แก้ HN และ AN
- `review-status-ux.md`: recovery panel และ date failure รอบต่อมา
- `his-read-and-third-case.md`: guard ล่าสุด, 40 tests, case8052 และ live ยังไม่หาย
- ใบส่งต่อก่อนเริ่มงาน: `C:\SSCC\_intake\nrefer-handoff.md`

Public client code ที่เคยตรวจ (ชื่อ chunks อาจเปลี่ยนเมื่อเว็บ deploy ใหม่):

- `https://nrefer.moph.go.th/beta/chunk-UIVIL3PE.js` — DMIS component/template
- `https://nrefer.moph.go.th/beta/chunk-T5BZUTSZ.js` — HIS/auth services
- `https://nrefer.moph.go.th/beta/chunk-HIED3E66.js` — environment config names
- `https://nrefer.moph.go.th/beta/chunk-EGPMWWUF.js` — user/ward reads
- `https://nrefer.moph.go.th/beta/chunk-TO245DYV.js` — reference lists

Repo ยังมี modified/untracked files หลายชุด รวมงานก่อนหน้าและงานไม่เกี่ยวข้อง ไม่มี commit เดียวที่แบ่งขอบเขตทุกอย่างได้แน่นอน ให้ตรวจ working tree โดยไม่ reset/revert งานของผู้ใช้ รายงานนี้ระบุบทบาทไฟล์ ไม่ได้อ้างว่าแต่ละไฟล์เป็นการแก้ของรอบนี้ทั้งหมด
