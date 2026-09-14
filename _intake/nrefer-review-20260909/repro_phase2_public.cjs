// Runs extracted methods from the public snapshot with synthetic service stubs.
// No browser, HTTP, authentication, patient data, or application DB access.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const dir = path.join(__dirname, 'public-phase2-20260911');
const source = fs.readFileSync(path.join(dir, 'chunk-UIVIL3PE.js'), 'utf8');
function method(start, end, after = 0) {
  const a = source.indexOf(start, after), b = source.indexOf(end, a + start.length);
  assert(a >= 0 && b > a, 'Expected public method boundaries');
  return source.slice(a, b);
}
function y(self, unused, generator) {
  const iterator = generator.call(self);
  function step(kind, value) {
    let result;
    try { result = iterator[kind](value); } catch (e) { return Promise.reject(e); }
    return result.done ? Promise.resolve(result.value) : Promise.resolve(result.value).then(
      value => step('next', value), error => step('throw', error));
  }
  return step('next');
}
function instance(code) {
  const dateStub = { default: () => ({ format: () => '2026-09-11 10:00:00' }) };
  return vm.runInNewContext(`new (class { ${code} })()`, {
    y, Ut: dateStub, H: dateStub, ge: Object.assign, Ze: Object.assign,
  }, { timeout: 1000 });
}
const results = [];
function record(test, observed, limit) { results.push({ test, observed, limit }); }
(async () => {
  const person = method('getPerson(){', 'getAdmission(e,o){');
  for (const mode of ['reject', 'resolved_error', 'empty_hn']) {
    const obj = instance(person);
    Object.assign(obj, { editRow: { hn: mode === 'empty_hn' ? '' : 'SYNTHETIC' },
      userInfo: { hcode: 'SYNTHETIC' }, loading: false,
      toastrService: { error() {}, warning() {} },
      hisService: { getPerson: () => mode === 'reject'
        ? Promise.reject(new Error('synthetic lookup rejection'))
        : Promise.resolve({ statusCode: 500, message: 'synthetic error response' }) } });
    let rejected = false;
    try { await obj.getPerson(); } catch { rejected = true; }
    assert.equal(obj.loading, mode === 'reject');
    assert.equal(rejected, mode === 'reject');
    record('getPerson/' + mode, { loading: obj.loading, rejected }, 'Extracted method; not a live HIS request.');
  }
  const edit = method('editItem(e,o=0){', 'saveEvaluate(){');
  for (const value of [0, '0']) {
    const obj = instance(edit);
    Object.assign(obj, { evaluateChoice: [{ name: 'synthetic_item', max_score: 3 }],
      sumBIScore: async function(e) { e.sum_score = Number(e.synthetic_item); } });
    await obj.editItem({ date: '2026-09-11', evaluate: { synthetic_item: value, sum_score: 0 } });
    assert.equal(obj.currentVisit.evaluate.synthetic_item, typeof value === 'number' ? '3' : '0');
    record('BI/reload/' + typeof value, obj.currentVisit.evaluate,
      'Whether backend returns numeric or string scores is not observed.');
  }
  const save = method('saveEvaluate(){', 'deleteEvaluate(){');
  for (const oldScore of [undefined, 12]) {
    const obj = instance(save); let payload;
    Object.assign(obj, { currentVisit: { date: '2026-09-11', time: '10:00',
      evaluate: { sum_score: 0, synthetic_item: '0' }, score: oldScore },
      userInfo: { hcode: 'SYNTHETIC', uid: 'SYNTHETIC' }, dmisPatientRef: 123,
      evaluateType: 'discharge', imcService: { saveDmisEvaluate: async data => {
        payload = data; return { statusCode: 200 }; } }, getData: async () => {},
      toastrService: { success() {} }, alert: { error() {} } });
    await obj.saveEvaluate();
    assert.equal(payload.score, oldScore);
    record('BI/save-zero/' + (oldScore ?? 'no-old-score'),
      { score: payload.score ?? null, scoreOmittedInJson: !JSON.stringify(payload).includes('"score":') },
      'Confirms client payload only; backend handling is unknown.');
  }
  const mainSave = method('savePatient(){', 'concatDatetime(e,o){');
  for (const ref of [0, 123]) {
    const obj = instance(mainSave); const events = [];
    Object.assign(obj, { editRow: { ref, age: [0, 0, 50], evaluates: {}, hn: 'SYNTHETIC', an: 'SYNTHETIC' },
      userInfo: { hcode: 'SYNTHETIC', uid: 'SYNTHETIC' },
      imcService: { savePerson: async () => ({ statusCode: 200 }),
        person: async () => ({ statusCode: 200, rows: [{ person_ref: 1 }] }),
        savePatient: async () => ({ statusCode: 200, rows: [] }) },
      toastrService: { success() {}, error() {} },
      onDataChange: { emit: e => events.push({ emit: e }) },
      getStrokePatient: async value => events.push({ reload: value }) });
    await obj.savePatient();
    assert.equal(ref === 0 ? events[0].emit.saved : events[0].reload, 1);
    record('main/save/ref=' + ref, events, 'Service responses stubbed; DOM navigation not exercised.');
  }
  const parent = instance(method('onDataChange(e){', 'resetVar(){', 140000));
  Object.assign(parent, { activeTab: 'detail', getPatient: async () => {} });
  await parent.onDataChange({ saved: 1 });
  assert.equal(parent.activeTab, 'search');
  record('main/parent-after-new-save', { activeTab: parent.activeTab }, 'Extracted parent method.');
  fs.writeFileSync(path.join(dir, 'repro-results.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
