"""User-specified registry copy rule; not an ASIA examination or AIS classification."""
LIMBS = (
    ('cf_motor_arm_left', 'แขนซ้าย', 'left', ('C5', 'C6', 'C7', 'C8', 'T1')),
    ('cf_motor_arm_right', 'แขนขวา', 'right', ('C5', 'C6', 'C7', 'C8', 'T1')),
    ('cf_motor_leg_left', 'ขาซ้าย', 'left', ('L2', 'L3', 'L4', 'L5', 'S1')),
    ('cf_motor_leg_right', 'ขาขวา', 'right', ('L2', 'L3', 'L4', 'L5', 'S1')),
)
RULE = 'stroke-limb-copy-v1'


def score(value):
    if value is None or value == '':
        return None
    if type(value) not in (str, int) or str(value) not in ('0', '1', '2', '3', '4', '5'):
        raise ValueError('Motor power ต้องเป็นคะแนน 0–5 หรือเว้นว่าง')
    return int(value)


def project(data):
    overrides = data.get('_motor_overrides') or {}
    if not isinstance(overrides, dict):
        raise ValueError('ข้อมูลแก้คะแนนรายช่องไม่ถูกต้อง')
    allowed = {f'{level}_{side}' for _, _, side, levels in LIMBS for level in levels}
    if set(overrides) - allowed:
        raise ValueError('ตำแหน่ง Motor power ไม่ถูกต้อง')
    rows = []
    for key, label, side, levels in LIMBS:
        summary = score(data.get(key))
        for level in levels:
            dest = f'{level}_{side}'
            override = overrides.get(dest)
            explicit = override is not None and override != ''
            value = (None if override == 'unset' else score(override)) if explicit else summary
            rows.append(dict(key=dest, label=f'{level} {"Left" if side == "left" else "Right"}',
                             score=value, source='override' if explicit else 'limb-copy', source_key=key))
    return dict(rule=RULE, rows=rows, complete=all(r['score'] is not None for r in rows))


def annotate(data):
    """Rebuild provenance server-side, rather than trusting a browser-generated result."""
    data['_motor_projection'] = project(data)
    for key, _, _, _ in LIMBS:
        value = score(data.get(key))
        if value is not None:
            data[key] = str(value)
