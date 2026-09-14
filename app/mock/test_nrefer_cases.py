"""Executed in test_nrefer.py's disposable source copy."""
from pathlib import Path
import os
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
if Path(os.environ.get('SSCC_TEST_ROOT', '.')).resolve() != ROOT or not (ROOT / '.nrefer-test-sandbox').exists():
    raise SystemExit('Run python mock/test_nrefer.py; this file must not access the real app database.')
sys.path.insert(0, str(ROOT))
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
import db
import nrefer_map as mapping
import nrefer_ui as ui
from nrefer_save import SaveObserver
import fill_nrefer as filler
import mock_nrefer as mock
import server
from nrefer_guard import install_read_only_guard


class GuardTests(unittest.TestCase):
    def test_his_reads_only_on_configured_base(self):
        class Context:
            def route(self, pattern, handler): self.handler = handler
        ctx = Context()
        install_read_only_guard(ctx, 'https://nrefer.test/api/beta', 'http://his.test/local')
        def allowed(method, url):
            result = []
            ctx.handler(SimpleNamespace(request=SimpleNamespace(method=method,url=url),
                abort=lambda reason:result.append(False), continue_=lambda:result.append(True)))
            return result == [True]
        for leaf in ('person','admission','service','diagnosis-ipd'):
            self.assertTrue(allowed('POST', 'http://his.test/local/refer/'+leaf))
            self.assertFalse(allowed('POST', 'http://other.test/local/refer/'+leaf))
            self.assertFalse(allowed('DELETE', 'http://his.test/local/refer/'+leaf))
        for leaf in ('save-person','save-patient','save-lib-ward','delete','unknown'):
            self.assertFalse(allowed('POST', 'http://his.test/local/refer/'+leaf))
        self.assertFalse(allowed('POST','https://nrefer.test/api/beta/dmis/imc/save-patient'))
    def test_auth_and_reference_methods_only(self):
        class Context:
            def route(self, pattern, handler):
                self.handler = handler
        context = Context()
        install_read_only_guard(context, 'https://example.test/api/beta')
        def allowed(method, path, origin='https://example.test'):
            route = SimpleNamespace(request=SimpleNamespace(method=method, url=origin+path))
            result = []
            route.abort = lambda reason: result.append(False)
            route.continue_ = lambda: result.append(True)
            context.handler(route)
            return result == [True]
        for path in ('user/user-status','user/user-by-key','admin/thaid/authenticated','libs/lib-ward'):
            self.assertTrue(allowed('POST','/api/beta/'+path))
            self.assertFalse(allowed('DELETE','/api/beta/'+path))
        self.assertTrue(allowed('GET','/api/beta/dmis/imc/evaluate-choice'))
        self.assertFalse(allowed('POST','/api/beta/dmis/imc/evaluate-choice'))
        self.assertFalse(allowed('POST','/api/beta/libs/save-lib-ward'))
        for method in ('GET','POST','PUT','DELETE'):
            for path in ('save-person','save-patient','delete-person','delete-patient','unknown'):
                self.assertFalse(allowed(method,'/api/beta/dmis/imc/'+path))
        self.assertFalse(allowed('POST','/api/beta/user/user-status','https://other.test'))

CASE = {'x_a2':'SYNTHETIC-1','cf_an':'SYNTHETIC-AN-1','x_fname':'ทดสอบ ระบบ',
        'x_pid':'','x_b6':'1','x_a4':'2','x_a3':'67','x_b1_1':'7883',
        'x_b3_2_date':'2026-09-01','x_b3_2_hhmm':'11:00','x_b4_date':'2026-09-05','x_b4_hhmm':'14:00',
        'cf_birth':'1959-03-04','x_b11':'0','x_b12':'4','x_b16':'2','x_b16_date':'2026-09-01','x_b16_hhmm':'10:20',
        'x_c10':'1','x_d2':'1','cf_sbp':'168','cf_dbp':'92','cf_nrefer_ctscan':'1',
        'cf_nrefer_ct_date':'2026-09-01','cf_nrefer_ct_time':'09:55','cf_nrefer_carry':'EMS',
        'cf_nrefer_visit_result':'1'}

class MappingTests(unittest.TestCase):
    def test_ct_time_reuses_c5_only_when_selected(self):
        data = dict(CASE, x_c5_date='2026-09-02', x_c5_hhmm='12:34', cf_nrefer_ct_use_c5='1')
        self.assertEqual(mapping.build(data,'',0)['raw']['ctscan_date'],'2026-09-02 12:34:00')
        self.assertFalse(mapping.build(dict(data,x_c5_date='2026-02-30'),'',0)['ok'])
        data['cf_nrefer_ct_use_c5']='2'
        self.assertEqual(mapping.build(data,'',0)['raw']['ctscan_date'],'2026-09-01 09:55:00')
    def test_unknowns_not_invented(self):
        b=mapping.build({'x_a2':'SYNTHETIC','x_b6':'1','x_b3_2_date':'2026-09-01'},'',0)
        fv=mapping.form_values(b)
        self.assertEqual(fv['text']['editRow.person_id'],'')
        self.assertEqual(fv['time']['editRow.admit_time'],'')
        self.assertIsNone(fv['select']['editRow.carry'])
        self.assertEqual(fv['radio']['editRow.ctscan'],'0')
        self.assertNotIn('editRow.gcs',fv['text'])
    def test_invalid_token(self):
        self.assertFalse(filler.token_ok('not-a-jwt'))
        self.assertFalse(filler.token_ok('a.e30.c'))
        self.assertTrue(filler.token_ok(mock.fake_jwt()))
    def test_tia_requires_explicit_mapping(self):
        self.assertFalse(mapping.build(dict(CASE,x_b6='3'),'',0)['ok'])
    def test_gcs_conflict(self):
        self.assertFalse(mapping.build(dict(CASE,x_b7='15',cf_nrefer_gcs_eye='4',cf_nrefer_gcs_verbal='4',cf_nrefer_gcs_motor='6'),'',0)['ok'])
    def test_zero_age_and_empty_carry(self):
        fv=mapping.form_values(mapping.build(dict(CASE,x_a3=0,cf_nrefer_carry='',x_b11=0),'',0))
        self.assertEqual(fv['text']['editRow.age[2]'],'0')
        self.assertIsNone(fv['select']['editRow.carry'])
        self.assertEqual(fv['mrs']['before'],'0')
    def test_invalid_calendar_date(self):
        self.assertFalse(mapping.build(dict(CASE,cf_birth='1959-02-30'),'',0)['ok'])

class AppTests(unittest.TestCase):
    def test_clinical_fields_are_adjacent_and_unique(self):
        fields=server.load_schema()
        keys=[server.field_key(f) for f in fields]
        self.assertEqual(len(keys),len(set(keys)))
        index=keys.index('x_b7')
        self.assertEqual(keys[index:index+4],['x_b7','cf_nrefer_gcs_eye','cf_nrefer_gcs_verbal','cf_nrefer_gcs_motor'])
        self.assertEqual(keys[keys.index('x_c5_hhmm')+1],'cf_nrefer_ctscan')
        dx=next(f for f in fields if server.field_key(f)=='cf_nrefer_dx')
        self.assertIn('Cerebral infarction',next(o['t'] for o in dx['options'] if o['v']=='I63'))
    def test_browser_finish_requires_explicit_discard(self):
        self.assertEqual(self.client.post('/browser/finish',json={}).status_code,400)
        with patch.object(server.browser_session,'finish_review') as finish:
            self.assertEqual(self.client.post('/browser/finish',json={'discard_unfinished':True}).status_code,200)
            finish.assert_called_once_with()
    def test_both_targets_dispatch_to_persistent_session(self):
        with patch.object(server.browser_session,'submit') as submit:
            server.spawn_fill([self.cid],'http://localhost/test')
            submit.assert_called_with('sscc',[self.cid],base_url='http://localhost/test')
            server.spawn_nrefer([self.cid],no_save=True)
            submit.assert_called_with('nrefer',[self.cid],no_save=True)
    def setUp(self):
        with db._conn() as conn: conn.execute('DELETE FROM cases')
        self.cid=db.save_case(None,CASE)
        self.client=server.app.test_client()
    def test_duplicate_local_admission(self):
        other=db.save_case(None,CASE)
        self.assertTrue(db.claim_nrefer(self.cid))
        self.assertFalse(db.claim_nrefer(other))
        self.assertIn(str(self.cid),server._nrefer_ready(db.get_case(other)))
        different=db.save_case(None,dict(CASE,cf_an='AN-OTHER'))
        self.assertTrue(db.claim_nrefer(different))
    def test_reconcile_requires_explicit_check_and_idle_worker(self):
        db.set_nrefer_state(self.cid,'uncertain')
        url=f'/case/{self.cid}/nrefer/reconcile'
        self.assertEqual(self.client.post(url,json={'outcome':'not_found'}).status_code,400)
        with patch.object(server.runlock,'read',return_value={'pid':123}):
            self.assertEqual(self.client.post(url,json={'outcome':'not_found','checked_register':True}).status_code,409)
        self.assertEqual(db.get_case(self.cid)['nrefer_state'],'uncertain')
        self.assertEqual(self.client.post(url,json={'outcome':'not_found','checked_register':True}).status_code,200)
        self.assertEqual(db.get_case(self.cid)['nrefer_state'],'draft')
    def test_reconcile_found_and_invalid_ref(self):
        db.set_nrefer_state(self.cid,'uncertain')
        url=f'/case/{self.cid}/nrefer/reconcile'
        self.assertEqual(self.client.post(url,json={'outcome':'found','ref':'-1','checked_register':True}).status_code,400)
        self.assertEqual(self.client.post(url,json={'outcome':'found','ref':'912','checked_register':True}).status_code,200)
        self.assertEqual(db.get_case(self.cid)['nrefer_ref'],'912')
        self.assertEqual(self.client.post(url,json={'outcome':'not_found','checked_register':True}).status_code,409)
    def test_queue_deduplicates_ids_without_spawning_browser(self):
        with patch.object(server,'spawn_nrefer') as spawn, patch.object(server.checks,'blocking',return_value=[]):
            response=self.client.post('/queue/nrefer',json={'case_ids':[self.cid,self.cid]})
            self.assertEqual(response.status_code,200)
            spawn.assert_called_once_with([self.cid])
    def test_inspection_mode_is_forwarded_to_worker(self):
        with patch.object(server,'spawn_nrefer') as spawn, patch.object(server.checks,'blocking',return_value=[]):
            response=self.client.post(f'/case/{self.cid}/nrefer/submit',json={'no_save':True})
            self.assertEqual(response.status_code,200)
            spawn.assert_called_once_with([self.cid],no_save=True)
    def test_preview_and_recovery_template(self):
        self.assertEqual(self.client.get(f'/case/{self.cid}/nrefer/preview').status_code,200)
        db.set_nrefer_state(self.cid,'uncertain')
        self.assertEqual(self.client.get(f'/case/{self.cid}/nrefer/preview').status_code,400)
        # Use the actual route, not an isolated Jinja string, to cover application context.
        response=self.client.get(f'/case/{self.cid}')
        self.assertEqual(response.status_code,200)
        self.assertIn('nreferRecovery',response.get_data(as_text=True))

class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.identity={'hn':'SYNTHETIC','an':'AN-1','hospcode':'10995'}
        self.observer=SaveObserver(None,'https://example.invalid/api/beta',self.identity)
    def req(self,identity=None,path='save-patient',method='POST'):
        class Request: pass
        req=Request(); req.method=method;req.url='https://example.invalid/api/beta/dmis/imc/'+path
        req.post_data_json={'data':identity or self.identity}
        return req
    def test_person_only_save_is_uncertain(self):
        self.observer.on_request(self.req(path='save-person'))
        self.assertTrue(self.observer.attempted)
        self.assertFalse(self.observer.saved)
    def test_wrong_hospital_and_http_error(self):
        self.observer.on_request(self.req(dict(self.identity,hospcode='OTHER')))
        self.assertTrue(self.observer.mismatch)
        req=self.req(); self.observer.on_request(req)
        response=SimpleNamespace(request=req,status=500,json=lambda:{'statusCode':200})
        self.observer.on_response(response)
        self.assertFalse(self.observer.saved)
    def test_response_ref_requires_matching_admission(self):
        req=self.req();self.observer.on_request(req)
        response=SimpleNamespace(request=req,status=200,json=lambda:{'statusCode':200,'rows':[dict(self.identity,an='OTHER',ref=99)]})
        self.observer.on_response(response)
        self.assertTrue(self.observer.saved);self.assertIsNone(self.observer.ref)
        response.json=lambda:{'statusCode':200,'rows':[dict(self.identity,ref=11)]}
        self.observer.on_response(response)
        self.assertEqual(self.observer.ref,'11')
    def test_wrong_origin_and_get_are_ignored(self):
        req=self.req();req.url='https://other.invalid/api/beta/dmis/imc/save-patient'
        self.observer.on_request(req);self.observer.on_request(self.req(method='GET'))
        self.assertFalse(self.observer.attempted)

class BrowserTests(unittest.TestCase):
    def test_blocked_his_read_locks_dates_and_allowed_read_unlocks(self):
        # Model getPerson(): loading stays true when the awaited POST rejects.
        html = '''<input id="date" type="date"><script>
        async function loadPerson(){let input=document.querySelector('#date');input.disabled=true;
          await fetch('/his/refer/person',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
          input.disabled=false;}
        </script>'''
        self.page.route('**/loading-preview',lambda route:route.fulfill(body=html,content_type='text/html'))
        self.page.goto(self.url+'/loading-preview')
        guard=install_read_only_guard(self.page.context,self.url+'/api/beta')
        self.page.evaluate('loadPerson().catch(()=>null)')
        self.assertFalse(self.page.locator('#date').is_enabled())
        guard.close()
        guard=install_read_only_guard(self.page.context,self.url+'/api/beta',self.url+'/his')
        try:
            self.page.evaluate('loadPerson()')
            self.assertTrue(self.page.locator('#date').is_enabled())
            self.page.locator('#date').fill('2026-09-01')
        finally: guard.close()
    def test_recovery_instructions_only_after_job_ends(self):
        cid = db.save_case(None, CASE)
        db.set_nrefer_state(cid, 'review')
        html = server.app.test_client().get(f'/case/{cid}').get_data(as_text=True)
        self.page.route('**/recovery-preview', lambda route: route.fulfill(status=200,content_type='text/html',body=html))
        self.page.route(f'**/case/{cid}/status', lambda route: route.fulfill(json={'ok':True,'fill_running':False,'nrefer_state':'uncertain','nrefer_ref':None}))
        self.page.goto(self.url+'/recovery-preview')
        box = self.page.locator('#nreferRecovery')
        self.assertFalse(box.is_visible())
        self.page.evaluate("window.dispatchEvent(new CustomEvent('browser-session',{detail:{state:'working'}}))")
        self.assertFalse(box.is_visible())
        self.page.evaluate("window.dispatchEvent(new CustomEvent('browser-session',{detail:{state:'idle'}}))")
        box.wait_for(state='visible')
        self.assertFalse(self.page.locator('#nreferFoundRef').is_visible())
        self.assertIn('01/09/2569 เวลา 11:00', self.page.locator('#source_cf_nrefer_su_date').inner_text())  # วันที่ในฟอร์มแสดงเป็น พ.ศ. ทั้งหมด
        self.page.evaluate("window.dispatchEvent(new CustomEvent('browser-session',{detail:{state:'review'}}))")
        self.assertFalse(box.is_visible())
    def test_open_waits_for_form_initialization(self):
        cid = db.save_case(None, CASE)
        filler.open_add_form(self.page, self.url+'/beta?slow_init=1', cid)
        self.assertEqual(self.page.locator('#form').get_attribute('data-initialized'), 'yes')
        warnings = ui.fill_form(self.page, mapping.form_values(mapping.build(CASE,'',0)))
        self.assertEqual(self.page.locator('[name="editRow.hn"]').input_value(), CASE['x_a2'])
        self.assertEqual(self.page.locator('[name="editRow.an"]').input_value(), CASE['cf_an'])
        self.assertFalse(any(w.startswith(('HN:', 'AN:')) for w in warnings), warnings)
    def test_form_gcs_and_shared_fields_without_saving(self):
        cid=db.save_case(None,CASE)
        html=server.app.test_client().get(f'/case/{cid}').get_data(as_text=True)
        self.page.route('**/case-preview',lambda route: route.fulfill(status=200,content_type='text/html',body=html))
        self.page.goto(self.url+'/case-preview')
        self.assertEqual(self.page.locator('.gcs-panel [data-field]').count(),4)
        for key,val in [('eye','3'),('verbal','4'),('motor','5')]:
            self.page.locator(f'[data-key="cf_nrefer_gcs_{key}"] [data-input]').fill(val)
        total=self.page.locator('[data-key="x_b7"] [data-input]')
        self.assertEqual(total.input_value(),'12')
        self.assertIsNotNone(total.get_attribute('readonly'))
        self.assertFalse(self.page.locator('[data-key="cf_nrefer_ward"]').is_visible())
        self.assertIn('Stroke Unit',self.page.locator('#source_cf_nrefer_ward').inner_text())
        self.assertFalse(self.page.locator('[data-key="cf_nrefer_dx"]').is_visible())
        # โปรแกรมตั้ง "ใช้ C5" ให้อัตโนมัติเมื่อ CT=ได้ทำ และมีวันที่ C5 — คลิกซ้ำจะเป็นการยกเลิก จึงคลิกเฉพาะเมื่อยังไม่ได้เลือก
        if not self.page.locator('[data-key="cf_nrefer_ct_use_c5"] input[value="1"]').is_checked():
            self.page.locator('[data-key="cf_nrefer_ct_use_c5"] label').filter(has_text='ใช้วันเวลาการตรวจ C5').click()
        self.assertFalse(self.page.locator('[data-key="cf_nrefer_ct_date"]').is_visible())
        # Existing overrides are kept, not silently deleted when the control is hidden.
        payload=self.page.evaluate('collect()')
        self.assertEqual(payload['cf_nrefer_ct_date'],CASE['cf_nrefer_ct_date'])
        self.assertEqual(payload['x_b7'],'12')
        self.assertEqual(db.get_case(cid)['data'],CASE)
    @classmethod
    def setUpClass(cls):
        cls.server=make_server('127.0.0.1',0,mock.app)
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(headless=True)
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.server.shutdown();cls.thread.join()
    def setUp(self):
        with db._conn() as conn:
            conn.execute('DELETE FROM cases')
        mock.save({'patients':[],'next_ref':7001})
        self.page=self.browser.new_page()
        self.page.set_default_timeout(2000)
        self.page.goto(self.url+'/beta/')
        self.page.get_by_role('button',name='Add new').click()
    def tearDown(self):
        self.page.close()
    def test_full_form_without_save(self):
        self.page.locator('input[name="editRow.person_id"]').fill('STALE-HIS')
        fv=mapping.form_values(mapping.build(CASE,'10995',0))
        warnings=ui.fill_form(self.page,fv)
        self.assertEqual(warnings,[])
        self.assertEqual(mock.load()['patients'],[])
        self.assertEqual(self.page.locator('select[name="editRow.dmis"]').input_value(),'2')
        self.assertTrue(self.page.locator('select[name="editRow.dmis"]').is_disabled())
        self.assertEqual(self.page.locator('input[name="editRow.person_id"]').input_value(),'')
        self.assertEqual(self.page.locator('input[name="editRow.ward"]').input_value(),'24')
        self.assertEqual(ui.normalized_date(ui.date_input(self.page,'birth').input_value()),'1959-03-04')
        self.assertIn('0. No symptoms',ui.pk_field(self.page,'before').inner_text())
        self.assertTrue(ui.date_input(self.page,'editRow.surgery_start_time').is_disabled())
    def test_gcs_keyboard_recalculates_total(self):
        for key,value in [('gcs_eye','3'),('gcs_verbal','4'),('gcs_motor','5')]:
            ui.fill_input(self.page,'editRow.'+key,value)
        self.assertEqual(self.page.locator('input[name="editRow.gcs"]').input_value(),'12')
        self.assertTrue(self.page.locator('input[name="editRow.gcs"]').get_attribute('readonly') is not None)
        for key,value in [('gcs_eye','4'),('gcs_verbal','5'),('gcs_motor','6')]:
            ui.fill_input(self.page,'editRow.'+key,value)
        self.assertEqual(self.page.locator('input[name="editRow.gcs"]').input_value(),'15')
        self.assertEqual(mock.load()['patients'],[])
    def test_selected_date_and_unknown_time(self):
        fv=mapping.form_values(mapping.build(dict(CASE,x_b3_2_hhmm=''),'',0))
        ui.fill_form(self.page,fv)
        self.assertEqual(self.page.locator('input[name="editRow.admit_time"]').input_value(),'')
        loc=ui.date_input(self.page,'editRow.admit_time');loc.click()
        self.assertEqual(loc.locator('xpath=ancestor::pk-datepicker[1]').locator('.days button.selected').inner_text(),'1')
    def test_process_manual_save_and_resend(self):
        cid=db.save_case(None,CASE)
        args=SimpleNamespace(api_url=self.url+'/api/beta')
        original=SaveObserver.wait
        def user_click(observer,ms):
            # User surrogate exists ONLY in this loopback test harness.
            self.assertTrue(observer.endpoint.startswith(self.url+'/'))
            observer.page.get_by_role('button',name='บันทึก',exact=True).click()
            return original(observer,3000)
        with patch.object(SaveObserver,'wait',user_click):
            self.assertEqual(filler.process_case(self.page,self.url+'/beta',db.get_case(cid),args),'submitted')
        self.assertEqual(db.get_case(cid)['nrefer_ref'],'sent')
        self.assertEqual(len(mock.load()['patients']),1)
        self.assertEqual(filler.process_case(self.page,self.url+'/beta',db.get_case(cid),args),'draft')
        self.assertEqual(len(mock.load()['patients']),1)
    def test_process_no_save(self):
        cid=db.save_case(None,CASE)
        self.assertEqual(filler.process_case(self.page,self.url+'/beta',db.get_case(cid),SimpleNamespace(api_url=self.url+'/api/beta')),'draft')
        self.assertEqual(db.get_case(cid)['nrefer_state'],'draft')
        self.assertEqual(mock.load()['patients'],[])
    def test_other_visit_save_is_not_success(self):
        identity={'hn':'SYNTHETIC-1','an':'EXPECTED','hospcode':'10995'}
        self.page.locator('input[name="editRow.hn"]').fill('SYNTHETIC-1')
        self.page.locator('input[name="editRow.an"]').fill('OTHER')
        with SaveObserver(self.page,self.url+'/api/beta',identity) as observer:
            with self.page.expect_response(self.url+'/api/beta/dmis/imc/save-patient'):
                self.page.get_by_role('button',name='บันทึก',exact=True).click()
            ok,ref=observer.wait(1000)
            self.assertFalse(ok);self.assertIsNone(ref);self.assertTrue(observer.mismatch)
    def test_missing_ward_is_warning(self):
        with self.assertRaises(ValueError): ui.pick(self.page,'ward','ICU')
    def test_slow_his_does_not_overwrite_source(self):
        self.page.goto(self.url+'/beta/?slow_his=1')
        self.page.get_by_role('button',name='Add new').click()
        warnings=ui.fill_form(self.page,mapping.form_values(mapping.build(CASE,'10995',0)))
        self.assertEqual(warnings,[])
        self.assertEqual(self.page.locator('input[name="editRow.fname"]').input_value(),'ทดสอบ')
        self.assertEqual(self.page.locator('input[name="editRow.tel"]').input_value(),'')
    def test_inspection_blocks_user_save_before_server(self):
        cid=db.save_case(None,CASE)
        args=SimpleNamespace(api_url=self.url+'/api/beta',no_save=True)
        original=SaveObserver.wait
        def user_click(observer,ms):
            with observer.page.expect_event('requestfailed', predicate=lambda req:req.url.endswith('/save-patient')):
                observer.page.get_by_role('button',name='บันทึก',exact=True).click()
            return original(observer,500)
        with patch.object(SaveObserver,'wait',user_click):
            self.assertEqual(filler.process_case(self.page,self.url+'/beta',db.get_case(cid),args),'draft')
        self.assertEqual(mock.load()['patients'],[])
        self.assertEqual(db.get_case(cid)['nrefer_state'],'draft')
        self.assertIsNone(db.get_case(cid)['nrefer_ref'])
    def test_app_template_javascript_compiles(self):
        import re
        cid=db.save_case(None,CASE)
        html=server.app.test_client().get(f'/case/{cid}').get_data(as_text=True)
        scripts=re.findall(r'<script[^>]*>(.*?)</script>',html,re.S)
        self.assertTrue(scripts)
        for script in scripts:
            self.page.evaluate('(source) => { new Function(source); }',script)

from test_browser_session_cases import SessionTests
from test_stroke_motor_cases import MotorTests, MotorBrowserTests

if __name__=='__main__': unittest.main(verbosity=2)
