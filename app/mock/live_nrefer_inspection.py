"""Run the real Edge worker against nRefer with synthetic data and --no-save.

Uses an isolated temporary database and browser profile. Never copies patient
data, credentials, or the normal Edge profile. Login is performed by the user.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    source = Path(__file__).resolve().parents[1]
    case = {
        'x_a2': 'SYNTHETIC-NOT-PATIENT', 'cf_an': 'SYNTHETIC-NOT-VISIT',
        'x_fname': 'ทดสอบ ห้ามบันทึก', 'x_pid': '',
        'x_b6': '1', 'x_a4': '2', 'x_a3': '67', 'x_b1_1': '7883',
        'x_b3_2_date': '2026-09-01', 'x_b3_2_hhmm': '11:00',
        'x_b4_date': '2026-09-05', 'x_b4_hhmm': '14:00',
        'cf_birth': '1959-03-04', 'x_b11': '0', 'x_b12': '4',
        'x_b16': '2', 'x_b16_date': '2026-09-01', 'x_b16_hhmm': '10:20',
        'x_c10': '1', 'x_d2': '1', 'cf_sbp': '168', 'cf_dbp': '92',
        'cf_nrefer_ctscan': '1', 'cf_nrefer_ct_date': '2026-09-01',
        'cf_nrefer_ct_time': '09:55', 'cf_nrefer_carry': 'EMS',
        'cf_nrefer_visit_result': '1', 'cf_nrefer_gcs_eye': '3',
        'cf_nrefer_gcs_verbal': '4', 'cf_nrefer_gcs_motor': '5', 'x_b7': '12',
    }
    with tempfile.TemporaryDirectory(prefix='sscc-nrefer-live-') as folder:
        target = Path(folder)
        for name in ('db.py', 'nrefer_map.py', 'nrefer_ui.py', 'nrefer_save.py',
                     'nrefer_guard.py', 'fill_nrefer.py', 'runlock.py'):
            shutil.copy2(source / name, target / name)
        (target / 'config.json').write_text(json.dumps({'browser_channel': 'msedge'}), encoding='utf-8')
        (target / 'synthetic.json').write_text(json.dumps(case, ensure_ascii=False), encoding='utf-8')
        seed = "import json,db; from pathlib import Path; db.init(); db.save_case(None,json.loads(Path('synthetic.json').read_text(encoding='utf-8')))"
        subprocess.run([sys.executable, '-c', seed], cwd=target, check=True)
        print('Synthetic inspection only; isolated database/profile; manual ThaID login; writes blocked after login.', flush=True)
        result = subprocess.run(
            [sys.executable, '-u', 'fill_nrefer.py', '--cases', '1', '--no-save'],
            cwd=target, env=dict(os.environ, SSCC_NREFER_REVIEW_MS='900000', SSCC_NREFER_TRACE='1'))
        print('Inspection worker exit code:', result.returncode, flush=True)
        # The worker returns 6 when nothing was submitted, including --no-save.
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
