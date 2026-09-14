"""Synthetic-only tests, imported by the disposable nRefer test launcher."""
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright, expect
import db
import server
import stroke_motor as motor
import stroke_motor_ui as ui

ROOT = Path(__file__).resolve().parents[1]
if Path(os.environ.get('SSCC_TEST_ROOT', '.')).resolve() != ROOT:
    raise RuntimeError('Use mock/test_nrefer.py; synthetic database only')
DATA = {'x_a2':'MOTOR-SYNTHETIC', 'cf_an':'MOTOR-AN', 'x_b6':'1',
        'cf_motor_arm_left':'4', 'cf_motor_arm_right':'5',
        'cf_motor_leg_left':'0', 'cf_motor_leg_right':'3'}


class MotorTests(unittest.TestCase):
    def test_copy_all_grades_and_sides_with_override(self):
        for grade in range(6):
            data = {key:grade for key, _, _, _ in motor.LIMBS}
            result = motor.project(data)
            self.assertTrue(result['complete'])
            self.assertEqual([r['score'] for r in result['rows']], [grade]*20)
        data = dict(DATA, _motor_overrides={'C8_left':'0'})
        result = {r['key']:r for r in motor.project(data)['rows']}
        self.assertEqual(result['C5_left']['score'],4)
        self.assertEqual(result['C8_left']['score'],0)
        self.assertEqual(result['T1_right']['score'],5)
        self.assertEqual(result['L2_left']['score'],0)
        self.assertEqual(result['S1_right']['score'],3)
        data['cf_motor_arm_left'] = '2'
        rows = {r['key']:r for r in motor.project(data)['rows']}
        self.assertEqual(rows['C5_left']['score'],2)
        self.assertEqual(rows['C8_left']['score'],0)
        self.assertEqual(rows['C8_left']['source'],'override')

    def test_missing_is_not_zero_and_invalid_scores_fail(self):
        self.assertFalse(motor.project({})['complete'])
        self.assertTrue(all(r['score'] is None for r in motor.project({})['rows']))
        self.assertFalse(motor.project(dict(DATA, _motor_overrides={'C5_left':'unset'}))['complete'])
        for value in (-1,6,True,2.5,'bad','00',[]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                motor.project(dict(DATA,cf_motor_arm_left=value))
        with self.assertRaises(ValueError):
            motor.project(dict(DATA,_motor_overrides={'C5_wrong':'4'}))

    def test_local_save_roundtrip_and_dispatch_saved_admission(self):
        client=server.app.test_client()
        with patch.object(server.excel_export,'schedule_export'):
            response=client.post('/case/save',json={'data':dict(DATA,_motor_overrides={'C8_left':'0'})})
            self.assertEqual(response.status_code,200)
            cid=response.json['case_id']
            stored=db.get_case(cid)['data']
            self.assertEqual(stored['cf_motor_leg_left'],'0')
            self.assertEqual(stored['_motor_projection']['rule'],motor.RULE)
            original=stored.copy()
            bad=client.post('/case/save',json={'case_id':cid,'data':dict(DATA,cf_motor_arm_left='8')})
            self.assertEqual(bad.status_code,400)
            self.assertEqual(db.get_case(cid)['data'],original)
            db.set_nrefer(cid,'7123')
            with patch.object(server.browser_session,'submit') as submit:
                self.assertEqual(client.post(f'/case/{cid}/nrefer/motor').status_code,200)
                submit.assert_called_once_with('nrefer',[cid],mode='motor')
            client.post('/case/save',json={'case_id':cid,'data':{'x_a2':'MOTOR-SYNTHETIC','cf_an':'MOTOR-AN','_motor_overrides':{}}})
            stored=db.get_case(cid)['data']
            self.assertNotIn('cf_motor_leg_left',stored)
            self.assertEqual(stored['_motor_overrides'],{})
            with patch.object(server.browser_session,'submit') as submit:
                self.assertEqual(client.post(f'/case/{cid}/nrefer/motor').status_code,400)
                submit.assert_not_called()


class MotorBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=make_server('127.0.0.1',0,server.app,threaded=True)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.http.server_port}'
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.http.shutdown();cls.thread.join()

    def setUp(self):
        self.export=patch.object(server.excel_export,'schedule_export');self.export.start()
        self.page=self.browser.new_page(viewport={'width':1280,'height':1000})
        self.page.set_default_timeout(2500)

    def tearDown(self):
        self.page.close();self.export.stop()

    def test_main_form_keyboard_override_save_reload_and_layout(self):
        cid=db.save_case(None, {'x_a2':'MOTOR-SYNTHETIC','cf_an':'MOTOR-AN','x_a3':'65','x_a4':'2','x_b2_2':'1'})
        self.page.goto(f'{self.url}/case/{cid}')
        panel=self.page.locator('.motor-panel')
        self.assertEqual(panel.locator('input:checked').count(),0)
        self.assertEqual(self.page.locator('.gcs-panel [data-field]').count(),4)
        for key, _, _, _ in motor.LIMBS:
            self.page.locator(f'[data-key="{key}"] .pill').filter(has_text=DATA[key]).click()
        limb=self.page.locator('[data-key="cf_motor_arm_left"]').locator('..')
        limb.locator('summary').click()
        override=limb.locator('[data-motor-override="C8_left"]')
        override.select_option('0')
        # Native arrow-key behavior should change the summary without clearing the override.
        radio=limb.locator('input[value="4"]');radio.focus();radio.press('ArrowLeft')
        expect(limb.locator('input[value="3"]')).to_be_checked()
        self.assertEqual(override.input_value(),'0')
        self.assertTrue(self.page.evaluate('saveDraft(true)'))
        self.page.reload()
        expect(self.page.locator('[data-key="cf_motor_leg_left"] input[value="0"]')).to_be_checked()
        self.assertEqual(self.page.locator('[data-motor-override="C8_left"]').input_value(),'0')
        with patch.object(server.browser_session,'submit') as submit:
            with self.page.expect_response(f'{self.url}/case/{cid}/nrefer/motor') as response:
                self.page.locator('#btnMotorFill').click()
            self.assertEqual(response.value.status,200)
            submit.assert_called_once_with('nrefer',[cid],mode='motor')
        artifact=os.environ.get('SSCC_MOTOR_QA_DIR')
        if artifact:
            Path(artifact).mkdir(parents=True,exist_ok=True)
            panel.screenshot(path=str(Path(artifact)/'motor-desktop.png'), style='#toast { visibility:hidden; }')
        self.page.set_viewport_size({'width':390,'height':900})
        self.assertLessEqual(panel.bounding_box()['width'],390)
        self.assertTrue(panel.evaluate('(el)=>el.scrollWidth<=el.clientWidth'))
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),390)
        if artifact: panel.screenshot(path=str(Path(artifact)/'motor-mobile.png'), style='#toast { visibility:hidden; }')
        self.page.locator('[data-key="cf_motor_leg_left"] [data-motor-clear]').click()
        self.assertTrue(self.page.evaluate('saveDraft(true)'))
        self.page.reload()
        self.assertEqual(self.page.locator('[data-key="cf_motor_leg_left"] input:checked').count(),0)
        self.assertNotIn('cf_motor_leg_left',db.get_case(cid)['data'])

    def render_target(self, data=DATA):
        # Names/values and change-driven sum mirror public za/ja/Ua template functions.
        radios=[]
        for row in motor.project(data)['rows']:
            name='patientEvaluate.'+row['key'].replace('_','')
            radios.append('<div>'+row['label'])
            for i in range(6):
                radios.append(f'<input type="radio" name="{name}" value="{i}" {"checked" if i==5 else ""} onchange="sum()">')
            radios.append('</div>')
        html='<input name="editRow.hn" value="MOTOR-SYNTHETIC"><input name="editRow.an" value="MOTOR-AN">'
        html+='<dmis-asia-score style="display:block">'+''.join(radios)+'<span id="total">100</span><button onclick="window.saved=true">Save</button></dmis-asia-score>'
        html+='<script>window.saved=false;function sum(){document.querySelector("#total").textContent=[...document.querySelectorAll("input:checked")].reduce((n,e)=>n+Number(e.value),0)}</script>'
        self.page.set_content(html)

    def test_target_zero_override_and_no_save(self):
        self.render_target()
        data=dict(DATA,_motor_overrides={'C8_left':'0'})
        ui.fill_motor(self.page,data)
        self.assertEqual(self.page.locator('[name="patientEvaluate.C8left"]:checked').input_value(),'0')
        self.assertEqual(self.page.locator('#total').inner_text(),'56')
        self.assertFalse(self.page.evaluate('window.saved'))
        ui.fill_motor(self.page,dict(DATA,**{k:'0' for k,_,_,_ in motor.LIMBS}))
        self.assertEqual(self.page.locator('#total').inner_text(),'0')

    def test_wrong_case_or_changed_contract_does_not_touch_table(self):
        self.render_target()
        with self.assertRaises(ValueError): ui.fill_motor(self.page,dict(DATA,cf_an='WRONG'))
        self.assertEqual(self.page.locator('input[value="5"]:checked').count(),20)
        self.page.locator('[name="patientEvaluate.S1right"][value="5"]').evaluate('(el)=>el.value="9"')
        with self.assertRaises(ValueError): ui.fill_motor(self.page,DATA)
        self.assertEqual(self.page.locator('input[value="5"]:checked').count(),19)

    def test_review_button_fills_once_without_saving(self):
        self.page.goto(self.url+'/motor-target')
        self.render_target()
        self.page.evaluate('''() => {window.motorClick=setInterval(() => {
          const button=document.querySelector('#sscc_motor_apply');
          if(button){button.click();clearInterval(window.motorClick);}
        },20);}''')
        cid=db.save_case(None,DATA)
        reviewed=[]
        args=SimpleNamespace(on_review=lambda:reviewed.append(True),cancel_check=lambda:False)
        ui.process_motor(self.page,self.url,db.get_case(cid),args)
        self.assertEqual(reviewed,[True])
        self.assertEqual(self.page.locator('#total').inner_text(),'60')
        self.assertFalse(self.page.evaluate('window.saved'))
        self.assertIn('20',self.page.locator('#sscc_robot_banner').inner_text())
        self.assertIsNone(db.get_case(cid)['nrefer_ref'])
