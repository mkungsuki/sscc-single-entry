"""Imported only by the isolated nRefer test launcher."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server
import db
import runlock
import fill_nrefer
import mock_nrefer as mock
import mock_sscc
import fill_sscc
import excel_export
from browser_session import BrowserSession, BusyError


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = make_server('127.0.0.1', 0, mock.app, threaded=True)
        cls.http_thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.http_thread.start()
        cls.url = f'http://127.0.0.1:{cls.http.server_port}/beta'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http_thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='browser-session-test-')
        self.config = {'browser_channel': None, 'session_profile_dir': self.temp.name,
                       'nrefer_base_url': self.url, 'nrefer_api_url': self.url.replace('/beta','/api/beta')}
        self.cid = db.save_case(None, {'x_a2':'SESSION-TEST','cf_an':'SESSION-AN','x_b6':'1',
                                     'x_fname':'ทดสอบ ระบบ','x_b3_2_date':'2026-09-01',
                                     'cf_nrefer_carry':'EMS','cf_nrefer_visit_result':'1',
                                     'x_b1_1':'7883','x_b11':'0','x_b12':'4'})
        self.manager = None

    def wait_state(self, state, timeout=45):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if self.manager.status()['state'] == state:
                return
            if self.manager.status()['state'] == 'closed' and state != 'closed':
                with db._conn() as conn:
                    logs = [r[0] for r in conn.execute("SELECT fill_log FROM cases WHERE fill_log != '' ORDER BY id DESC LIMIT 3")]
                self.fail(f'Browser stopped before {state}; synthetic test logs: {logs}')
            time.sleep(.05)
        self.fail(f'Expected {state}, got {self.manager.status()}')

    def tearDown(self):
        if self.manager:
            state = self.manager.status()['state']
            if state in ('held','review'):
                self.manager.finish_review()
                self.wait_state('idle')
            if self.manager.status()['state'] == 'idle':
                self.manager.runner = lambda page, job, manager, guards: page.context.close()
                self.manager.submit('nrefer',[self.cid])
                self.wait_state('closed')
        self.temp.cleanup()

    def test_three_nrefer_cases_reuse_live_tab_without_login(self):
        seen = []
        original_login = fill_nrefer.ensure_login
        login_calls = []
        def login(*args):
            login_calls.append(True)
            return original_login(*args)
        def runner(page, job, manager, guards):
            seen.append(page)
            if len(seen) > 1:
                self.assertEqual(page.evaluate("sessionStorage.getItem('test-session-marker')"),'retained')
            manager._execute(page, job, guards)
            expected = db.get_case(job['ids'][0])['data']
            self.assertEqual(page.locator('input[name="editRow.hn"]').input_value(), expected['x_a2'])
            self.assertEqual(page.locator('input[name="editRow.an"]').input_value(), expected['cf_an'])
            page.evaluate("sessionStorage.setItem('test-session-marker','retained')")
        self.manager = BrowserSession(self.config, runner=runner, headless=True)
        with patch.object(fill_nrefer,'ensure_login',side_effect=login):
            for index in range(3):
                data = dict(db.get_case(self.cid)['data'], x_a2=f'SESSION-HN-{index}', cf_an=f'SESSION-AN-{index}')
                cid = db.save_case(None, data)
                self.manager.submit('nrefer',[cid],no_save=True)
                self.wait_state('review')
                with self.assertRaises(BusyError):
                    self.manager.submit('sscc',[self.cid],base_url=self.url)
                self.manager.finish_review()
                self.wait_state('idle')
                self.assertIsNone(runlock.read())
                self.assertIsNotNone(runlock.read_session())
            self.assertIs(seen[0],seen[1])
            self.assertIs(seen[1],seen[2])
            self.assertEqual(len(login_calls),1)
            self.assertIsNone(db.get_case(self.cid).get('nrefer_ref'))
            self.assertFalse(Path(self.temp.name,'sscc_session.json').exists())

    def test_target_tabs_preserved_and_failure_does_not_close_them(self):
        seen = {}
        def runner(page, job, manager, guards):
            target = job['target']
            if target in seen:
                self.assertIs(page,seen[target])
                self.assertEqual(page.evaluate("sessionStorage.getItem('marker')"),target)
            else:
                page.goto(self.url)
                page.evaluate('(value)=>sessionStorage.setItem("marker",value)',target)
                seen[target] = page
            if job.get('fail'):
                raise RuntimeError('synthetic failure')
        self.manager = BrowserSession(self.config,runner=runner,headless=True)
        for target in ('sscc','nrefer','sscc'):
            self.manager.submit(target,[self.cid],base_url=self.url)
            self.wait_state('idle')
        self.assertIsNot(seen['sscc'],seen['nrefer'])
        self.manager.submit('nrefer',[self.cid],base_url=self.url,fail=True,no_save=True)
        self.wait_state('held')
        with self.assertRaises(BusyError):
            self.manager.submit('sscc',[self.cid],base_url=self.url)
        self.manager.finish_review()
        self.wait_state('idle')
        self.manager.submit('nrefer',[self.cid],base_url=self.url)
        self.wait_state('idle')

    def test_cannot_finish_during_fill(self):
        self.manager = BrowserSession(self.config,headless=True)
        with self.assertRaises(BusyError):
            self.manager.finish_review()
        self.manager._set(state='working')
        with self.assertRaises(BusyError):
            self.manager.finish_review()
        self.manager._set(state='closed')

    def test_actual_sscc_filler_three_separate_jobs(self):
        http = make_server('127.0.0.1',0,mock_sscc.app,threaded=True)
        thread = threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{http.server_port}/stroke'
        seen = []
        original = fill_sscc.process_case
        def local_user_save(page, base, case, args, queue_mode):
            self.assertTrue(base.startswith('http://127.0.0.1:'))
            args.auto_confirm = True  # Local test-only user surrogate; never a production option.
            return original(page,base,case,args,queue_mode)
        def runner(page,job,manager,guards):
            seen.append(page)
            if len(seen)>1:
                self.assertEqual(page.evaluate("sessionStorage.getItem('sscc-test-marker')"),'kept')
            manager._execute(page,job,guards)
            page.evaluate("sessionStorage.setItem('sscc-test-marker','kept')")
        self.manager = BrowserSession(self.config,runner=runner,headless=True)
        try:
            with patch.object(fill_sscc,'process_case',side_effect=local_user_save), patch.object(excel_export,'schedule_export'):
                for index in range(3):
                    cid = db.save_case(None,{'x_a2':f'SESSION-SSCC-{index}','x_fname':'ทดสอบ ระบบ',
                                            'x_a3':'67','x_a4':'2','x_b6':'1','x_b7':'12'})
                    self.manager.submit('sscc',[cid],base_url=url)
                    self.wait_state('idle',timeout=70)
                    self.assertEqual(db.get_case(cid)['status'],'submitted')
                self.assertIs(seen[0],seen[1])
                self.assertIs(seen[1],seen[2])
                self.assertFalse(fill_sscc.SESSION_PATH.exists())
        finally:
            http.shutdown()
            thread.join()
