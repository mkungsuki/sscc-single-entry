"""Offline review probes. Imports only the isolated source snapshot; no real records/network."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'sandbox'))
import fill_nrefer as f
import nrefer_map as m

class Response:
    url = 'https://example.invalid/dmis/imc/save-patient'
    status = 200
    def json(self):
        return {'statusCode': 200}

class Page:
    def on(self, event, callback):
        self.callback = callback
    def once(self, *args):
        pass
    def remove_listener(self, *args):
        pass
    def wait_for_timeout(self, *args):
        self.callback(Response())
    def evaluate(self, source, args=None):
        if args is None:
            return ''
        return [{'ref': 11, 'an': 'CURRENT'}, {'ref': 99, 'an': 'OTHER-VISIT'}]

ok, ref = f.wait_for_save(Page(), 'SYNTHETIC', 0, 1000, 'https://example.invalid')
assert ok and ref == 99
print('CONFIRMED: unrelated save response accepted; highest HN ref selected across visits')

assert f.token_ok('not-a-jwt') is True
print('CONFIRMED: malformed token accepted as login readiness')

url = 'https://example.invalid/?next=localhost'
assert ('127.0.0.1' in url or 'localhost' in url)
print('CONFIRMED: production mock guard treats a remote URL containing localhost as mock')

b = m.build({'x_a2': 'SYNTHETIC-HN', 'x_b6': '1', 'x_fname': 'Test Person',
             'x_b3_2_date': '2026-09-01', 'x_b3_2_hhmm': ''}, '', 0)
v = m.form_values(b)
assert v['text']['editRow.person_id'] == 'SYNTHETIC-HN'
assert v['time']['editRow.admit_time'] == '00:00'
print('CONFIRMED: missing citizen ID becomes HN; missing admission time becomes midnight')

class Field:
    def __init__(self, page, key):
        self.page, self.key = page, key
    def fill(self, value):
        self.page.values[self.key] = value
    def press(self, key):
        pass
class FormPage:
    def __init__(self):
        self.values = {'input[name="editRow.tel"]': 'STALE-HIS-VALUE'}
    def locator(self, key):
        return Field(self, key)
    def wait_for_timeout(self, *args):
        pass
p = FormPage()
f.fill_form(p, {'text': {'editRow.hn': 'SYNTHETIC', 'editRow.an': '', 'editRow.tel': ''},
                'select': {}, 'radio': {}, 'date': {}, 'time': {}, 'mrs': {}, 'ward_name': ''}, 0)
assert p.values['input[name="editRow.tel"]'] == 'STALE-HIS-VALUE'
print('CONFIRMED: empty source field leaves a prepopulated form value untouched')
