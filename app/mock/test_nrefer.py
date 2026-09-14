"""Run nRefer tests in a disposable copy; never touch the app database/profile."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if __name__ == '__main__':
    app = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='sscc-nrefer-test-') as folder:
        target = Path(folder)
        (target / 'mock').mkdir()
        for name in ('db.py','nrefer_map.py','nrefer_ui.py','nrefer_save.py','nrefer_guard.py','fill_nrefer.py','runlock.py',
                     'server.py','checks.py','excel_export.py','browser_session.py','fill_sscc.py','case_form.py',
                     'stroke_motor.py','stroke_motor_ui.py'):
            shutil.copy2(app / name, target / name)
        for folder_name in ('schema', 'templates'):
            shutil.copytree(app / folder_name, target / folder_name)
        for name in ('mock_nrefer.py','mock_sscc.py','nrefer_widgets.js','test_nrefer_cases.py','test_browser_session_cases.py','test_stroke_motor_cases.py'):
            shutil.copy2(app / 'mock' / name, target / 'mock' / name)
        (target / 'config.json').write_text('{}',encoding='utf-8')
        (target / '.nrefer-test-sandbox').touch()
        result = subprocess.run([sys.executable, '-u', 'mock/test_nrefer_cases.py', *sys.argv[1:]], cwd=target,
                                env=dict(os.environ, SSCC_NREFER_REVIEW_MS='1000', SSCC_TEST_ROOT=str(target)))
        sys.exit(result.returncode)
