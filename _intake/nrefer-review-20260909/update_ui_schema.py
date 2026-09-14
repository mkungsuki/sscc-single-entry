import json
from pathlib import Path
root = Path('C:/SSCC/app')
p = root / 'schema/custom_fields_defaults.json'
data = json.loads(p.read_text(encoding='utf-8'))
for f in data['fields']:
    if f['key'] == 'cf_an':
        f['hint'] = 'ต้องระบุ AN ก่อนกรอก nRefer เพื่อแยกครั้งรักษา — ไม่ใช้วันที่แทน AN'
fields = [
 ('cf_nrefer_dx','ICD nRefer สำหรับ TIA/CVT (ให้เจ้าของทะเบียนยืนยัน)','select',[(f'I{i}',f'I{i}') for i in range(60,70)]),
 ('cf_nrefer_ctscan','ผล CT สำหรับ nRefer (แยกจาก MRI)','select',[('0','ไม่ทราบ'),('1','ได้ทำ CT'),('2','ไม่ได้ทำ CT')]),
 ('cf_nrefer_carry','ผู้นำส่งสำหรับ nRefer','select',[('SELF','มาเอง'),('EMS','EMS รพ.'),('FR','EMS ท้องถิ่น'),('RELATE','ญาติ')]),
 ('cf_nrefer_visit_result','ผลจำหน่ายสำหรับ nRefer','select',[('1','ทุเลา/กลับบ้าน'),('4','ส่งต่อ'),('9','เสียชีวิต')]),
 ('cf_nrefer_ward','ชื่อ Ward nRefer (ถ้ารหัส SSCC จับคู่ไม่ได้)','text',None),
 ('cf_nrefer_ct_date','วันที่ทำ CT (nRefer)','date',None),
 ('cf_nrefer_ct_time','เวลาทำ CT (nRefer)','time',None),
 ('cf_nrefer_surgery_date','วันเริ่มผ่าตัด (nRefer)','date',None),
 ('cf_nrefer_surgery_time','เวลาเริ่มผ่าตัด (nRefer)','time',None),
 ('cf_nrefer_surgery_end_date','วันสิ้นสุดผ่าตัด (nRefer)','date',None),
 ('cf_nrefer_surgery_end_time','เวลาสิ้นสุดผ่าตัด (nRefer)','time',None),
 ('cf_nrefer_gcs_eye','GCS Eye (nRefer)','number',None),
 ('cf_nrefer_gcs_verbal','GCS Verbal (nRefer)','number',None),
 ('cf_nrefer_gcs_motor','GCS Motor (nRefer)','number',None),
]
existing = {f['key'] for f in data['fields']}
for key,label,kind,options in fields:
    if key in existing:
        continue
    f = {'key':key,'label':label,'type':kind,'enabled':True}
    if options is not None:
        f['options'] = [{'v':v,'t':t} for v,t in options]
    if key.startswith('cf_nrefer_gcs_'):
        f.update(min=1,max={'eye':4,'verbal':5,'motor':6}[key.rsplit('_',1)[1]])
    data['fields'].append(f)
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

p = root / 'templates/form.html'
s = p.read_text(encoding='utf-8')
s = s.replace('☁ กรอก nRefer อีกครั้ง', '☁ ตรวจรายการ nRefer')
s = s.replace("  if (!(await saveDraft(true))) return;\n  if (blockingWarnings.length)", "  if ({{ (case.nrefer_ref if case else none) | tojson }}) { window.open({{ (config.get('nrefer_base_url', 'https://nrefer.moph.go.th/beta') + '/#/dmis/patient') | tojson }}, '_blank', 'noopener'); return; }\n  if (!(await saveDraft(true))) return;\n  if (blockingWarnings.length)")
start = s.index("  document.getElementById('nreferTable').innerHTML")
end = s.index("  document.getElementById('nreferSub')",start)
s = s[:start] + '''  const table = document.getElementById('nreferTable');
  table.replaceChildren();
  for (const pair of d.summary) {
    const row = document.createElement('tr');
    for (const value of pair) { const cell = document.createElement('td'); cell.textContent = value ?? ''; row.appendChild(cell); }
    table.appendChild(row);
  }
  const notes = document.getElementById('nreferNotes');
  notes.replaceChildren();
  for (const note of d.notes) { const li = document.createElement('li'); li.textContent = note; notes.appendChild(li); }
''' + s[end:]
s = s.replace(' — โปรแกรมจะเปิดฟอร์ม "เพิ่มข้อมูล" ใหม่ ถ้าจะแก้เคสเดิมให้ปิดฟอร์มนั้นแล้วเปิดเคสเดิมจากทะเบียน (nRefer เตือนถ้า AN ซ้ำ)', ' — ตรวจ/แก้รายการเดิมจากทะเบียน nRefer')
s = s.replace("if (btnNrefer) btnNrefer.textContent = '☁ ส่ง nRefer อีกครั้ง (อัปเดต)';", "if (btnNrefer) { btnNrefer.textContent = '☁ บันทึกแล้ว — รีเฟรชเพื่อตรวจรายการ'; btnNrefer.disabled = true; }")
s = s.replace("  setTimeout(pollNrefer, 3000);", "  if (d.ok && !d.fill_running) { toast(d.nrefer_state === 'uncertain' || d.nrefer_state === 'review' ? 'ต้องตรวจผลในทะเบียน nRefer ก่อนส่งซ้ำ' : 'จบการกรอก nRefer แล้ว', 5000); return; }\n  setTimeout(pollNrefer, 3000);")
p.write_text(s,encoding='utf-8')
p = root / 'templates/list.html'
s = p.read_text(encoding='utf-8')
s = s.replace("  if (!confirm(`กรอกฟอร์ม nRefer", "  if (again) { toast('มีเคสที่เคยบันทึกแล้ว — เปิดตรวจรายการเดิมใน nRefer และนำออกจากคิว', 5000); return; }\n  if (!confirm(`กรอกฟอร์ม nRefer")
s = s.replace('จะเปิดฟอร์มเพิ่มข้อมูลใหม่ ระวังซ้ำ', 'ให้ตรวจรายการเดิมก่อน')
p.write_text(s,encoding='utf-8')
