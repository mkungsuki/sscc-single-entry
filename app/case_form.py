"""Presentation only: one clinical workflow, preserving existing storage keys."""
from copy import deepcopy
from stroke_motor import LIMBS

# ICD-10 category names: NHS ICD-10 tabular list, block I60-I69.
# https://classbrowser.nhs.uk/ICD-10-5TH-Edition/vol1/block-i60-i69.htm
ICD_NAMES = {
    'I60': 'Subarachnoid haemorrhage', 'I61': 'Intracerebral haemorrhage',
    'I62': 'Other nontraumatic intracranial haemorrhage', 'I63': 'Cerebral infarction',
    'I64': 'Stroke, not specified as haemorrhage or infarction',
    'I65': 'Occlusion and stenosis of precerebral arteries, not resulting in cerebral infarction',
    'I66': 'Occlusion and stenosis of cerebral arteries, not resulting in cerebral infarction',
    'I67': 'Other cerebrovascular diseases',
    'I68': 'Cerebrovascular disorders in diseases classified elsewhere',
    'I69': 'Sequelae of cerebrovascular disease',
}
GROUPS = {
    'x_a2': ['cf_an'], 'x_a3': ['cf_birth'],
    'x_b1_1': ['cf_nrefer_ward'], 'x_a6_1': ['cf_nrefer_carry'],
    'x_b6': ['cf_nrefer_dx'],
    'x_b7': ['cf_nrefer_gcs_eye','cf_nrefer_gcs_verbal','cf_nrefer_gcs_motor',
             *[limb[0] for limb in LIMBS], 'cf_sbp','cf_dbp'],
    'x_c5_hhmm': ['cf_nrefer_ctscan','cf_nrefer_ct_use_c5','cf_nrefer_ct_date','cf_nrefer_ct_time'],
    'x_c10': ['cf_nrefer_su_date','cf_nrefer_su_time'],
    'x_c20': ['cf_nrefer_visit_result'],
    'x_d2_intracerebral': ['cf_nrefer_surgery_date','cf_nrefer_surgery_time','cf_nrefer_surgery_end_date','cf_nrefer_surgery_end_time'],
    # ฟิลด์ รพ. เดิมที่เคยกองอยู่ท้ายฟอร์ม → ย้ายไปติดคำถามที่มันขยาย (rtPA → ท้ายกลุ่ม B16, AF/OAC → ท้ายกลุ่ม C18)
    'x_b16_2_amount': ['cf_rtpa_event','cf_rtpa_recog_date','cf_rtpa_recog_hhmm','cf_dtn_delay','cf_dtn_delay_note'],
    'x_c18_note': ['cf_af_no_oac','cf_af_no_oac_note'],
}

# ช่องที่รู้ค่าได้เฉพาะตอนจำหน่าย — ใช้กรองการแสดงผลใน "โหมดจำหน่าย" (ไม่กระทบการเก็บค่า)
PHASE_DISCHARGE = {
    'x_b4_date','x_b4_hhmm','x_b4_followup','x_b4_followup_date','x_b4_not_followup_note',
    'x_b4_1','x_b4_1_address','x_b4_1_hospcode','x_b4_1_date','x_b4_1_time','x_b4_1_note',
    'x_b6','cf_nrefer_dx','x_b8','x_b10','x_b12','x_b14','x_b19',
    'x_c13_1','x_c13_1houramt','x_c13_2','x_c13_2houramt','x_c13_3','x_c13_3houramt','x_c13_4','x_c13_4houramt',
    'x_c14','x_c15_1','x_c15_2','x_c15_3','x_c16','x_c16_note','x_c17',
    'x_c18','x_c18_drug','x_c18_causeok','x_c18_cause','x_c18_note','cf_af_no_oac','cf_af_no_oac_note',
    'x_c19','x_c19_note','x_c20','cf_nrefer_visit_result','x_c20_date','x_c21','x_c21_currency',
    'x_d1[]','x_d2','x_d2_intracerebral','cf_nrefer_surgery_date','cf_nrefer_surgery_time',
    'cf_nrefer_surgery_end_date','cf_nrefer_surgery_end_time','x_d3[]','x_e1','x_e2[]','x_f1[]','cf_mrs_90d',
}
LABELS = {
    'cf_an':'AN — ครั้งรักษานี้', 'cf_birth':'วันเกิด',
    'cf_sbp':'BP แรกรับ — Systolic', 'cf_dbp':'BP แรกรับ — Diastolic',
    'cf_nrefer_gcs_eye':'E — Eye (1–4)', 'cf_nrefer_gcs_verbal':'V — Verbal (1–5)',
    'cf_nrefer_gcs_motor':'M — Motor (1–6)',
    'cf_nrefer_dx':'วินิจฉัยสำหรับทะเบียน nRefer — เฉพาะ TIA/CVT ที่ต้องยืนยัน',
    'cf_nrefer_ward':'Ward ปลายทาง — ระบุเฉพาะกรณีจับคู่ชื่อไม่ได้',
    'cf_nrefer_ctscan':'ผู้ป่วยได้ทำ CT หรือไม่ (แยกจาก MRI)',
    'cf_nrefer_carry':'ผู้นำส่ง', 'cf_nrefer_visit_result':'ผลจำหน่าย — ระบุเมื่อข้อมูลข้างต้นยังไม่สรุปผล',
    'cf_nrefer_ct_date':'วันที่ทำ CT — กรณีใช้คนละเวลากับ C5',
    'cf_nrefer_ct_time':'เวลาทำ CT — กรณีใช้คนละเวลากับ C5',
    'cf_nrefer_su_date':'วันที่เข้า Stroke Unit — ระบุเมื่อไม่ตรงกับวันรับไว้',
    'cf_nrefer_su_time':'เวลาเข้า Stroke Unit — ระบุเมื่อไม่ตรงกับเวลารับไว้',
    'cf_nrefer_surgery_date':'วันเริ่มผ่าตัด', 'cf_nrefer_surgery_time':'เวลาเริ่มผ่าตัด',
    'cf_nrefer_surgery_end_date':'วันสิ้นสุดผ่าตัด', 'cf_nrefer_surgery_end_time':'เวลาสิ้นสุดผ่าตัด',
}


def arrange(fields):
    fields = deepcopy(fields)
    by_key = {f.get('sscc') or f['key']: f for f in fields}
    if 'cf_nrefer_ctscan' in by_key and 'cf_nrefer_ct_use_c5' not in by_key:
        reuse = {'key':'cf_nrefer_ct_use_c5','sscc':None,'type':'select','enabled':True,
                 'label':'วันเวลาทำ CT', 'section':'CF','section_title':'ข้อมูลเพิ่มเติม',
                 'options':[{'v':'1','t':'ใช้วันเวลาการตรวจ C5 ที่กรอกไว้'},
                            {'v':'2','t':'ระบุแยก — CT เป็นคนละการตรวจกับ C5'}],
                 'hint':'เลือกใช้ร่วมกันเมื่อวันเวลา C5 เป็น CT ครั้งที่ต้องการบันทึก ไม่ใช่ MRI คนละเวลา'}
        fields.append(reuse)
        by_key['cf_nrefer_ct_use_c5'] = reuse
    for key, label in LABELS.items():
        if key in by_key:
            by_key[key]['label'] = label
    motor = []
    for key, label, side, levels in LIMBS:
        if key in by_key:
            f = by_key[key]
            f.update(motor_limb=True, motor_side=side, motor_levels=levels, motor_label=label)
            motor.append(f)
    if motor:
        motor[0]['motor_start'] = True
        motor[-1]['motor_end'] = True
    if 'cf_nrefer_dx' in by_key:
        for option in by_key['cf_nrefer_dx'].get('options',[]):
            if option['v'] in ICD_NAMES:
                option['t'] = option['v'] + ' — ' + ICD_NAMES[option['v']]
    moved = {k for anchor, keys in GROUPS.items() if anchor in by_key for k in keys}
    for key, f in by_key.items():
        f['phase'] = 'discharge' if key in PHASE_DISCHARGE else 'admit'
    out = []
    for field in fields:
        key = field.get('sscc') or field['key']
        if key in moved:
            continue
        out.append(field)
        for child_key in GROUPS.get(key, []):
            if child_key in by_key:
                child = by_key[child_key]
                child['section'], child['section_title'] = field['section'], field['section_title']
                out.append(child)
        if key == 'x_b7':
            parts = [by_key[k] for k in GROUPS[key][:3] if k in by_key]
            if parts:
                field['group_start'] = True
                field['label'] = 'คะแนนรวม (3–15)'
                parts[-1]['group_end'] = True
    return out
