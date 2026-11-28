// The Parts step's behaviour without a browser window (src/parts.js; wizard/README-details.md,
// "The Parts step"): a part set from files, one part one row, the page's own limits,
// POST /api/parts and each refusal and warning, a part the page cannot draw, a part arriving
// after the user left, New plate, removing a part, the switch that says how STL files are read,
// and a refreshed page taking up its stored parts. The pages here run on the fake front server,
// the fake clock, the fakes of the browser's storage and locks, and the real worker's code in
// the test's own thread.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

import { createApi } from '../src/api.js';
import { createGeometryClient } from '../src/geometry-client.js';
import { MAX_PART_BYTES } from '../src/geometry/constants.js';
import { createParts, partName, partSetOf } from '../src/parts.js';
import * as sentences from '../src/sentences.js';
import { createStore } from '../src/state.js';
import { createStorage } from '../src/storage.js';
import { FakeClock, settle } from './fakes/clock.js';
import { FakeFrontServer, errorReport, example, partRecordOf, steps } from './fakes/front_server.js';
import { boxFile, filler, largestFile } from './fakes/stl.js';
import { FakeLocks, FakeRecords, FakeTab } from './fakes/storage.js';
import { InThreadWorker } from './fakes/worker.js';

const S = 1000;
const ME = example('wizard-front/me.json');
const GROUP = ME.groups[0].id;
const hex = (bytes) => createHash('sha256').update(new Uint8Array(bytes)).digest('hex');

function fakePanel() {
  return {
    notices: [],
    notify(notice) {
      const at = this.notices.findIndex((n) => n.key === notice.key);
      if (at >= 0) this.notices.splice(at, 1);
      this.notices.push(notice);
    },
    dropNotice(key) { this.notices = this.notices.filter((n) => n.key !== key); },
  };
}

// One page on one browser: `b` is shared by the pages of a browser (a refresh reuses it).
function browser() {
  let n = 0;
  return { records: new FakeRecords(), locks: new FakeLocks(), clock: new FakeClock(), server: new FakeFrontServer(), tab: new FakeTab(), newId: () => `plate-${(n += 1)}` };
}

async function openPage(b = browser(), { uploadUnits = 'in', hash } = {}) {
  const store = createStore();
  const api = createApi({ transport: b.server.transport, clock: b.clock, version: 'v', currentGroup: () => store.get().group, random: () => 0.5 });
  const reports = [];
  const report = (what, fields = {}) => { reports.push({ what, ...fields }); return Promise.resolve(true); };
  const storage = createStorage({ openRecords: () => b.records.open(), locks: b.locks.forTab('A'), tab: b.tab, clock: b.clock, newId: b.newId, report });
  const { plate, group } = await storage.begin({ user: ME.user.id, groups: ME.groups });
  const configuration = { ...example('configuration-default.json'), upload_units: uploadUnits };
  store.set({ user: ME.user, groups: ME.groups, group, plateId: plate.plate_id, step: plate.step, configuration });
  const worker = new InThreadWorker();
  const geometry = createGeometryClient(worker.port, { report });
  const panel = fakePanel();
  const parts = createParts({ api, storage, geometry, store, panel, report, ...(hash ? { hash } : {}) });
  await parts.resume();
  return { b, store, api, storage, geometry, worker, panel, reports, parts, server: b.server, clock: b.clock };
}

const uploads = (server) => server.made('POST', '/api/parts');
// A file as the browser hands it over (a File): its name, its size and its bytes read on demand.
const file = (name, bytes = boxFile(name)) => ({ name, size: bytes.byteLength, arrayBuffer: async () => bytes });
// A file the browser cannot read (moved, deleted or locked after it was chosen): its read fails
// as Chromium's File.arrayBuffer does.
const unreadable = (name, size = 684) => ({
  name, size, reads: 0,
  arrayBuffer() { this.reads += 1; return Promise.reject(Object.assign(new Error('A requested file or directory could not be found.'), { name: 'NotReadableError' })); },
});
const rowsOf = (parts) => parts.rows().map((r) => ({ name: r.name, units: r.units, quantity: r.quantity, arriving: r.arriving }));

// ---- the part set a file upload makes

test('a file\'s part takes the file\'s name less a final .stl in any case, cut to 200 characters, "part" when nothing is left', () => {
  assert.equal(partName('Gusset Plate.STL'), 'Gusset Plate');
  assert.equal(partName('bracket.stl'), 'bracket');
  assert.equal(partName('bracket.stl.stl'), 'bracket.stl');
  assert.equal(partName('notes.txt'), 'notes.txt');
  assert.equal(partName('.stl'), 'part');
  assert.equal(partName(`${'é'.repeat(250)}.stl`), 'é'.repeat(200));
});

test('files make one part set: source file, quantity 1, the switch\'s units, the bytes unchanged', () => {
  const a = boxFile('a');
  const set = partSetOf([{ name: 'a.stl', bytes: a }], 'mm');
  assert.deepEqual(set, { format: 1, source: 'file', parts: [{ name: 'a', quantity: 1, units: 'mm', stl_bytes: a }] });
  assert.equal(set.parts[0].stl_bytes, a);
});

// ---- adding and uploading

test('a part is kept first, its row arriving, and uploaded with its bytes exactly, its units, the mark and the group', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/parts', steps.hold());
  const bytes = boxFile('gusset');
  const adding = page.parts.addFiles([file('Gusset Plate.stl', bytes)]);
  const request = await page.server.arrived(1);
  await adding;
  assert.deepEqual(rowsOf(page.parts), [{ name: 'Gusset Plate', units: 'in', quantity: 1, arriving: true }]);
  const sha = hex(bytes);
  assert.deepEqual(page.b.records.value(`part-bytes/${page.store.get().plateId}/${sha}.in`), bytes);
  assert.equal(page.storage.plate().parts[0].quantity, 1);
  assert.equal(request.path, '/api/parts?units=in');
  assert.equal(request.body, bytes);
  assert.deepEqual(new Uint8Array(request.body), new Uint8Array(bytes));
  assert.equal(request.headers['content-type'], 'application/octet-stream');
  assert.equal(request.headers['x-penguinslicer-wizard'], '1');
  assert.equal(request.headers['x-penguinslicer-group'], GROUP);
  assert.deepEqual(page.store.get().plate, { ...page.store.get().plate, parts: 0, instances: 0, arriving: 1, arrivingInstances: 1 });
  request.held.release();
  await page.parts.idle();
  const [row] = page.parts.rows();
  assert.equal(row.arriving, false);
  assert.equal(row.record.sha256, sha);
  assert.equal(row.drawn, true);
  assert.deepEqual(page.storage.plate().parts[0].record, partRecordOf('/api/parts?units=in', bytes));
  assert.deepEqual(page.store.get().plate, { ...page.store.get().plate, parts: 1, instances: 1, arriving: 0, arrivingInstances: 0 });
  assert.deepEqual(page.panel.notices, []);
});

test('the same file added twice is one row with quantity 2, uploaded once; the same bytes under the other units are another part', async () => {
  const page = await openPage();
  const bytes = boxFile('same');
  await page.parts.addFiles([file('same.stl', bytes), file('same copy.stl', bytes)]);
  await page.parts.idle();
  assert.deepEqual(rowsOf(page.parts), [{ name: 'same', units: 'in', quantity: 2, arriving: false }]);
  assert.equal(uploads(page.server).length, 1);
  assert.equal(page.storage.plate().parts[0].quantity, 2);
  page.parts.setUnits('mm');
  await page.parts.addFiles([file('same.stl', bytes)]);
  await page.parts.idle();
  assert.deepEqual(rowsOf(page.parts).map((r) => [r.units, r.quantity]), [['in', 2], ['mm', 1]]);
  assert.deepEqual(uploads(page.server).map((r) => r.path), ['/api/parts?units=in', '/api/parts?units=mm']);
});

test('a part already listed raises its quantity by the part set\'s, to at most 150', async () => {
  const page = await openPage();
  const bytes = boxFile('q');
  await page.parts.addPartSet({ format: 1, source: 'file', parts: [{ name: 'q', quantity: 140, units: 'in', stl_bytes: bytes }] });
  await page.parts.addPartSet({ format: 1, source: 'file', parts: [{ name: 'q', quantity: 20, units: 'in', stl_bytes: bytes }] });
  assert.equal(page.parts.rows()[0].quantity, 150);
});

test('a quantity cannot be set past 150 or under 1, and is a whole number', async () => {
  const page = await openPage();
  await page.parts.addFiles([file('q.stl')]);
  const { key } = page.parts.rows()[0];
  page.parts.setQuantity(key, 151);
  assert.equal(page.parts.rows()[0].quantity, 150);
  page.parts.setQuantity(key, 0);
  assert.equal(page.parts.rows()[0].quantity, 1);
  page.parts.setQuantity(key, Number.NaN);
  assert.equal(page.parts.rows()[0].quantity, 1);
  page.parts.setQuantity(key, 7.6);
  assert.equal(page.parts.rows()[0].quantity, 8);
  await page.storage.written();
  assert.equal(page.storage.plate().parts[0].quantity, 8);
});

// ---- the page's own limits

test('a file of 7,500,084 bytes is uploaded, and one of 7,500,085 is refused with the wizard\'s sentence and nothing sent', async () => {
  const page = await openPage();
  const largest = largestFile();
  assert.equal(largest.byteLength, MAX_PART_BYTES);
  await page.parts.addFiles([file('largest.stl', largest)]);
  await page.parts.idle();
  assert.equal(uploads(page.server).length, 1);
  assert.equal(page.parts.rows().length, 1);
  const over = new Uint8Array(MAX_PART_BYTES + 1);
  over.set(new Uint8Array(largest));
  await page.parts.addFiles([file('bracket.stl', over.buffer)]);
  assert.equal(uploads(page.server).length, 1);
  assert.equal(page.parts.rows().length, 1);
  assert.deepEqual(page.panel.notices.map(({ kind, what, todo }) => ({ kind, what, todo })), [{
    kind: 'error',
    what: 'bracket.stl is 7.6 MB. PenguinSlicer takes parts up to 7.5 MB (150,000 triangles), so it was not added.',
    todo: 'Your other parts are fine. Export it again from your CAD program at a coarser resolution.',
  }]);
});

test('a part over the limit on an empty plate does not say the other parts are fine', async () => {
  const page = await openPage();
  await page.parts.addFiles([file('big.stl', filler(9_100_000))]);
  assert.deepEqual(page.panel.notices.map((n) => n.todo), ['Export it again from your CAD program at a coarser resolution.']);
  assert.equal(page.panel.notices[0].what, 'big.stl is 9.1 MB. PenguinSlicer takes parts up to 7.5 MB (150,000 triangles), so it was not added.');
});

test('a file over the size limit is refused by its size alone, before its bytes are read', async () => {
  const page = await openPage();
  const big = unreadable('bracket.stl', MAX_PART_BYTES + 1);
  await page.parts.addFiles([big]);
  assert.equal(big.reads, 0);
  assert.deepEqual(page.panel.notices.map(({ kind, what }) => ({ kind, what })), [{
    kind: 'error', what: 'bracket.stl is 7.6 MB. PenguinSlicer takes parts up to 7.5 MB (150,000 triangles), so it was not added.',
  }]);
  assert.equal(uploads(page.server).length, 0);
});

test('a file the browser cannot read is the wizard\'s notification naming it, and the other files of the drop are added', async () => {
  const page = await openPage();
  const gone = unreadable('gone.stl');
  await page.parts.addFiles([file('good.stl'), gone, file('other.stl')]);
  await page.parts.idle();
  assert.equal(gone.reads, 1);
  assert.deepEqual(rowsOf(page.parts).map((r) => [r.name, r.arriving]), [['good', false], ['other', false]]);
  assert.equal(uploads(page.server).length, 2);
  assert.deepEqual(page.panel.notices.map(({ kind, what, todo }) => ({ kind, what, todo })), [{
    kind: 'error',
    what: 'gone.stl could not be read, so it was not added.',
    todo: 'Your other parts are fine. Check that the file is still there, then add it again.',
  }]);
  assert.deepEqual(page.reports, []);
  await page.storage.written();
  assert.deepEqual(page.storage.plate().parts.map((p) => p.name), ['good', 'other']);
});

test('a file the browser cannot read on an empty plate does not say the other parts are fine', async () => {
  const page = await openPage();
  await page.parts.addFiles([unreadable('gone.stl')]);
  assert.deepEqual(page.panel.notices.map((n) => n.todo), ['Check that the file is still there, then add it again.']);
  assert.deepEqual(page.parts.rows(), []);
});

test('the wizard\'s sentence for a file it cannot read is an error report of its own', () => {
  const report = sentences.fileUnreadable('gone.stl', 'NotReadableError: gone');
  assert.equal(report.code, 'wizard.file_unreadable');
  assert.equal(report.retryable, false);
  assert.equal(report.message, 'gone.stl could not be read, so it was not added.');
  assert.equal(report.detail, 'NotReadableError: gone');
});

test('the twenty-sixth different part is refused with the wizard\'s sentence, and a listed part\'s quantity still rises', async () => {
  const page = await openPage();
  await page.parts.addFiles(Array.from({ length: 25 }, (_, i) => file(`p${i}.stl`)));
  assert.equal(page.parts.rows().length, 25);
  await page.parts.addFiles([file('Gusset Plate.stl')]);
  assert.equal(page.parts.rows().length, 25);
  assert.equal(uploads(page.server).length, 25);
  assert.deepEqual(page.panel.notices.map(({ kind, what, todo }) => ({ kind, what, todo })), [{
    kind: 'error', what: 'A plate takes up to 25 different parts, so Gusset Plate was not added.', todo: 'Remove a part, or print it on a new plate.',
  }]);
  await page.parts.addFiles([file('p3 again.stl', boxFile('p3.stl'))]);
  assert.equal(page.parts.rows()[3].quantity, 2);
});

test('parts that together pass 150 instances give the wizard\'s red message, and the store holds Next', async () => {
  const page = await openPage();
  await page.parts.addFiles([file('a.stl'), file('b.stl')]);
  await page.parts.idle();
  const [a, b] = page.parts.rows();
  page.parts.setQuantity(a.key, 149);
  assert.equal(page.parts.instanceProblem(), null);
  assert.equal(page.store.get().plate.instances, 150);
  page.parts.setQuantity(a.key, 150);
  page.parts.setQuantity(b.key, 13);
  const problem = page.parts.instanceProblem();
  assert.equal(problem.code, 'wizard.too_many_instances');
  assert.equal(problem.message, 'This plate would hold 163 instances.');
  assert.equal(problem.remedy, 'Up to 150 instances per plate; print the rest on a new plate.');
  assert.equal(page.store.get().plate.instances, 163);
  page.parts.setQuantity(b.key, 1);
  assert.equal(page.store.get().plate.instances, 151);
  assert.equal(page.parts.instanceProblem().message, 'This plate would hold 151 instances.');
});

test('a part still arriving that takes the plate past 150 instances gives the red message while it arrives', async () => {
  const page = await openPage();
  await page.parts.addFiles([file('a.stl')]);
  await page.parts.idle();
  page.parts.setQuantity(page.parts.rows()[0].key, 150);
  assert.equal(page.parts.instanceProblem(), null);
  page.server.script('POST', '/api/parts', steps.hold());
  const before = page.server.requests.length;
  await page.parts.addFiles([file('b.stl')]);
  const request = await page.server.arrived(before + 1);
  assert.deepEqual(rowsOf(page.parts).map((r) => r.arriving), [false, true]);
  assert.deepEqual(page.store.get().plate, { ...page.store.get().plate, instances: 150, arrivingInstances: 1 });
  const problem = page.parts.instanceProblem();
  assert.equal(problem.code, 'wizard.too_many_instances');
  assert.equal(problem.message, 'This plate would hold 151 instances.');
  request.held.release();
  await page.parts.idle();
});

// ---- the refusals of POST /api/parts

const REFUSALS = [
  ['slice.part_too_detailed', 413],
  ['slice.part_unreadable', 422],
  ['slice.part_not_binary', 422],
  ['slice.part_too_small', 422],
  ['slice.part_no_volume', 422],
  ['slice.part_too_large', 422],
];

for (const [code, status] of REFUSALS) {
  test(`a part refused with ${code} is a notification naming it with the slice service's sentences, and is not added`, async () => {
    const page = await openPage();
    page.server.script('POST', '/api/parts', steps.report(errorReport(code), { status }));
    const bytes = boxFile('refused');
    await page.parts.addFiles([file('Shooter Hood Rib.stl', bytes)]);
    await page.parts.idle();
    assert.deepEqual(page.parts.rows(), []);
    const report = errorReport(code);
    const reminder = code === 'slice.part_too_large' ? ' STL files are being read in inches.' : '';
    assert.deepEqual(page.panel.notices.map(({ kind, what, todo }) => ({ kind, what, todo })), [{
      kind: 'error', what: `Shooter Hood Rib: ${report.message}`, todo: `${report.remedy}${reminder}`,
    }]);
    assert.ok(!JSON.stringify(page.panel.notices).includes('fake detail'));
    await page.storage.written();
    assert.deepEqual(page.storage.plate().parts, []);
    assert.equal(page.b.records.keys().filter((k) => k.startsWith('part-bytes/')).length, 0);
    assert.deepEqual(page.store.get().plate, { ...page.store.get().plate, parts: 0, arriving: 0 });
    assert.deepEqual(page.reports, []);
  });
}

test('"Your other parts are fine." is said only while the list holds other parts', async () => {
  const page = await openPage();
  await page.parts.addFiles([file('kept.stl')]);
  page.server.script('POST', '/api/parts', steps.report(errorReport('slice.part_no_volume')));
  await page.parts.addFiles([file('flat.stl')]);
  await page.parts.idle();
  assert.equal(page.panel.notices[0].todo, `Your other parts are fine. ${errorReport('slice.part_no_volume').remedy}`);
});

test('a second failure of the same part replaces its notification', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/parts', steps.report(errorReport('slice.part_unreadable')), steps.report(errorReport('slice.part_unreadable', { message: 'Second.' })));
  const bytes = boxFile('twice');
  await page.parts.addFiles([file('twice.stl', bytes)]);
  await page.parts.idle();
  await page.parts.addFiles([file('twice.stl', bytes)]);
  await page.parts.idle();
  assert.deepEqual(page.panel.notices.map((n) => n.what), ['twice: Second.']);
});

test('a file refused as too large is followed by the reminder of the units it was read in', async () => {
  const page = await openPage(browser(), { uploadUnits: 'in' });
  page.parts.setUnits('mm');
  page.server.script('POST', '/api/parts', steps.report(errorReport('slice.part_too_large')));
  await page.parts.addFiles([file('big.stl')]);
  await page.parts.idle();
  assert.ok(page.panel.notices[0].todo.endsWith(' STL files are being read in millimetres.'));
});

test('the reminder says how the file was read even when the switch is turned during its upload', async () => {
  const page = await openPage(browser(), { uploadUnits: 'in' });
  page.server.script('POST', '/api/parts', steps.hold());
  await page.parts.addFiles([file('big.stl')]);
  const request = await page.server.arrived(1);
  page.parts.setUnits('mm');
  request.held.release(steps.report(errorReport('slice.part_too_large')));
  await page.parts.idle();
  assert.ok(page.panel.notices[0].todo.endsWith(' STL files are being read in inches.'), page.panel.notices[0].todo);
});

for (const [report, status] of [[errorReport('slice.bad_units'), 400], [errorReport('front.bad_request'), 400]]) {
  test(`${report.code} is a fault of the page: shown as a notification, reported as page_failed, and the part is not added`, async () => {
    const page = await openPage();
    page.server.script('POST', '/api/parts', steps.report(report, { status }));
    const bytes = boxFile('fault');
    await page.parts.addFiles([file('fault.stl', bytes)]);
    await page.parts.idle();
    assert.deepEqual(page.parts.rows(), []);
    assert.equal(page.panel.notices[0].what, `fault: ${report.message}`);
    assert.deepEqual(page.reports.map((r) => [r.what, r.part_sha256]), [['page_failed', hex(bytes)]]);
    assert.match(page.reports[0].detail, new RegExp(report.code.replace('.', '\\.')));
  });
}

test('any other refusal of the front server is shown as it is and the part is not added', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/parts', steps.report(errorReport('front.group_not_allowed')));
  await page.parts.addFiles([file('x.stl')]);
  await page.parts.idle();
  assert.deepEqual(page.parts.rows(), []);
  assert.equal(page.panel.notices[0].what, `x: ${errorReport('front.group_not_allowed').message}`);
});

test('a warning stays on its row and the part is added', async () => {
  const page = await openPage();
  const bytes = boxFile('leaky');
  const record = { ...partRecordOf('/api/parts?units=in', bytes), warnings: example('wizard-front/part-record.json').warnings };
  page.server.script('POST', '/api/parts', steps.answer(201, record));
  await page.parts.addFiles([file('Gusset Plate.stl', bytes)]);
  await page.parts.idle();
  const [row] = page.parts.rows();
  assert.equal(row.arriving, false);
  assert.deepEqual(row.warnings.map((w) => w.message), [record.warnings[0].message]);
  assert.equal(page.store.get().plate.parts, 1);
  assert.deepEqual(page.panel.notices, []);
});

test('an answer that is not a part\'s record is the wizard\'s bad_answer, and the part is not added', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/parts', steps.answer(201, { sha256: 'abc' }));
  await page.parts.addFiles([file('odd.stl')]);
  await page.parts.idle();
  assert.deepEqual(page.parts.rows(), []);
  assert.equal(page.panel.notices[0].what, 'odd: The server gave an answer this page cannot read.');
});

const BAD_RECORDS = [
  ['not an object', () => 'a part'],
  ['a hash of the wrong form', (r) => ({ ...r, sha256: r.sha256.toUpperCase() })],
  ['units neither in nor mm', (r) => ({ ...r, units: 'cm' })],
  ['no measurements', (r) => ({ ...r, measurements: null })],
  ['a size of two figures', (r) => ({ ...r, measurements: { ...r.measurements, size_mm: [1, 2] } })],
  ['a size that is not a number', (r) => ({ ...r, measurements: { ...r.measurements, size_mm: [1, 2, 'x'] } })],
  ['warnings that are not a list', (r) => ({ ...r, warnings: {} })],
  ['a warning without its sentence', (r) => ({ ...r, warnings: [{ code: 'slice.part_inside_out' }] })],
];

for (const [what, spoil] of BAD_RECORDS) {
  test(`a record with ${what} is the wizard's bad_answer, and the part is not added`, async () => {
    const page = await openPage();
    const bytes = boxFile(what);
    page.server.script('POST', '/api/parts', steps.answer(201, spoil(partRecordOf('/api/parts?units=in', bytes))));
    await page.parts.addFiles([file('odd.stl', bytes)]);
    await page.parts.idle();
    assert.deepEqual(page.parts.rows(), []);
    assert.equal(page.panel.notices[0].what, 'odd: The server gave an answer this page cannot read.');
  });
}

test('a stored part whose bytes are gone is dropped from the plate when the page opens again', async () => {
  const b = browser();
  const first = await openPage(b);
  await first.parts.addFiles([file('kept.stl'), file('lost.stl')]);
  await first.parts.idle();
  const lost = first.parts.rows()[1];
  await first.storage.written();
  b.records.map.delete(`part-bytes/${first.store.get().plateId}/${lost.sha256}.in`);
  b.locks.closeTab('A');
  const again = await openPage(b);
  assert.deepEqual(again.parts.rows().map((r) => r.name), ['kept']);
  await again.storage.written();
  assert.deepEqual(again.storage.plate().parts.map((p) => p.name), ['kept']);
});

test('a stored part whose record the page cannot use is uploaded again when the page opens, and never drawn from that record', async () => {
  const b = browser();
  const first = await openPage(b);
  await first.parts.addFiles([file('damaged.stl')]);
  await first.parts.idle();
  await first.storage.update({ parts: first.storage.plate().parts.map((p) => ({ ...p, record: { ...p.record, measurements: null } })) });
  await first.storage.written();
  b.locks.closeTab('A');
  const made = uploads(b.server).length;
  const again = await openPage(b);
  assert.deepEqual(rowsOf(again.parts), [{ name: 'damaged', units: 'in', quantity: 1, arriving: true }]);
  assert.equal(again.parts.rows()[0].record, null);
  await again.parts.idle();
  assert.equal(uploads(b.server).length, made + 1);
  assert.equal(again.parts.rows()[0].arriving, false);
  assert.equal(again.parts.rows()[0].record.measurements.size_mm.length, 3);
});

// ---- the hash

test('a record naming another hash is uploaded once more; a second difference is a page_failed report and the part is not added', async () => {
  const page = await openPage();
  const bytes = boxFile('h');
  const wrong = { ...partRecordOf('/api/parts?units=in', bytes), sha256: 'f'.repeat(64) };
  page.server.script('POST', '/api/parts', steps.answer(201, wrong), steps.answer(201, wrong));
  await page.parts.addFiles([file('h.stl', bytes)]);
  await page.parts.idle();
  assert.equal(uploads(page.server).length, 2);
  assert.deepEqual(page.parts.rows(), []);
  assert.deepEqual(page.reports.map((r) => [r.what, r.part_sha256]), [['page_failed', hex(bytes)]]);
  assert.equal(page.panel.notices[0].what, 'h: The server gave an answer this page cannot read.');
});

test('a record with the right hash and the other units is uploaded once more; a second difference is a page_failed report and the part is not added', async () => {
  const page = await openPage();
  const bytes = boxFile('u');
  const otherUnits = { ...partRecordOf('/api/parts?units=in', bytes), units: 'mm' };
  assert.equal(otherUnits.sha256, hex(bytes));
  page.server.script('POST', '/api/parts', steps.answer(201, otherUnits), steps.answer(201, otherUnits));
  await page.parts.addFiles([file('u.stl', bytes)]);
  await page.parts.idle();
  assert.equal(uploads(page.server).length, 2);
  assert.deepEqual(page.parts.rows(), []);
  assert.deepEqual(page.reports.map((r) => [r.what, r.part_sha256]), [['page_failed', hex(bytes)]]);
  assert.equal(page.panel.notices[0].what, 'u: The server gave an answer this page cannot read.');
  await page.storage.written();
  assert.deepEqual(page.storage.plate().parts, []);
});

test('a record naming another hash once, then the right one, adds the part', async () => {
  const page = await openPage();
  const bytes = boxFile('h2');
  page.server.script('POST', '/api/parts', steps.answer(201, { ...partRecordOf('/api/parts?units=in', bytes), sha256: '0'.repeat(64) }));
  await page.parts.addFiles([file('h2.stl', bytes)]);
  await page.parts.idle();
  assert.equal(uploads(page.server).length, 2);
  assert.equal(page.parts.rows()[0].arriving, false);
  assert.deepEqual(page.reports, []);
});

test('the page hashes the bytes with SHA-256 by the browser\'s own digest', async () => {
  const page = await openPage();
  const bytes = boxFile('digest');
  await page.parts.addFiles([file('digest.stl', bytes)]);
  assert.equal(page.parts.rows()[0].sha256, hex(bytes));
});

// ---- a part the page cannot draw

test('a part the front server accepts and the page cannot draw is not added: the wizard\'s notification and one part_not_drawable report', async () => {
  const page = await openPage();
  const bytes = filler(84);
  await page.parts.addFiles([file('broken.stl', bytes)]);
  await page.parts.idle();
  assert.deepEqual(page.parts.rows(), []);
  assert.deepEqual(page.panel.notices.map(({ kind, what, todo }) => ({ kind, what, todo })), [{
    kind: 'error',
    what: 'broken: PenguinSlicer could not show this part, so it cannot be imported.',
    todo: 'Export the part again as a binary STL and add it again.',
  }]);
  assert.deepEqual(page.reports.map((r) => [r.what, r.part_sha256]), [['part_not_drawable', hex(bytes)]]);
  assert.equal(page.storage.plate().parts.length, 0);
});

test('a file both refuse shows the slice service\'s notification and sends no report', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/parts', steps.report(errorReport('slice.part_unreadable')));
  await page.parts.addFiles([file('junk.stl', filler(10))]);
  await page.parts.idle();
  assert.deepEqual(page.panel.notices.map((n) => n.what), [`junk: ${errorReport('slice.part_unreadable').message}`]);
  assert.deepEqual(page.reports, []);
});

test('a worker that fails as a whole leaves no part added, with the worker\'s own sentences', async () => {
  const page = await openPage();
  page.worker.fail(new Error('the script could not load'));
  await page.parts.addFiles([file('a.stl')]);
  await page.parts.idle();
  assert.deepEqual(page.parts.rows(), []);
  assert.equal(page.panel.notices[0].what, 'a: PenguinSlicer could not work out the layout of this plate.');
  assert.ok(!page.reports.some((r) => r.what === 'part_not_drawable'));
});

test('the row shows its picture only once the worker has read the part', async () => {
  const page = await openPage();
  page.worker.hold();
  await page.parts.addFiles([file('slow.stl')]);
  await settle();
  assert.equal(page.parts.rows()[0].drawn, false);
  page.worker.release();
  await page.parts.idle();
  assert.equal(page.parts.rows()[0].drawn, true);
  assert.equal(page.parts.rows()[0].key, `${page.parts.rows()[0].sha256}.in`);
});

// ---- an upload with no answer

test('a part whose upload gets no answer keeps its row, says it is slow at 4 s, and after 300 s still keeps it; Try again adds it', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/parts', ...Array.from({ length: 40 }, () => steps.drop()));
  await page.parts.addFiles([file('far.stl')]);
  await page.clock.advance(3.9 * S);
  assert.equal(page.parts.rows()[0].slow, false);
  await page.clock.advance(0.1 * S);
  assert.equal(page.parts.rows()[0].slow, true);
  assert.equal(page.parts.rows()[0].arriving, true);
  await page.clock.advance(400 * S);
  assert.deepEqual(rowsOf(page.parts), [{ name: 'far', units: 'in', quantity: 1, arriving: true }]);
  assert.equal(page.storage.plate().parts.length, 1);
  page.server.scripts.length = 0;
  page.api.board.tryAgain();
  await page.parts.idle();
  assert.equal(page.parts.rows()[0].arriving, false);
  assert.equal(page.parts.rows()[0].slow, false);
});

test('an upload whose answer was lost is sent again and leaves one row', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/parts', steps.stallBody(201));
  await page.parts.addFiles([file('lost.stl')]);
  await page.clock.advance(62 * S);
  await page.parts.idle();
  assert.equal(uploads(page.server).length, 2);
  assert.equal(page.parts.rows().length, 1);
  assert.equal(page.parts.rows()[0].arriving, false);
});

// ---- a part arriving after the user left

for (const step of ['settings', 'preview', 'send']) {
  test(`a part arriving while the user is on the ${step} step says so in a notification`, async () => {
    const page = await openPage();
    page.server.script('POST', '/api/parts', steps.hold());
    await page.parts.addFiles([file('Gusset Plate.stl')]);
    page.store.set({ step });
    (await page.server.arrived(1)).held.release();
    await page.parts.idle();
    assert.deepEqual(page.panel.notices.map(({ kind, what, todo }) => ({ kind, what, todo })), [{
      kind: 'info', what: 'Gusset Plate arrived after you left the Parts step.', todo: 'It joins the plate when you go back to the Layout step.',
    }]);
  });
}

test('a part arriving on the Parts step or the Layout step says nothing', async () => {
  for (const step of ['parts', 'layout']) {
    const page = await openPage();
    page.server.script('POST', '/api/parts', steps.hold());
    await page.parts.addFiles([file('x.stl')]);
    page.store.set({ step });
    (await page.server.arrived(1)).held.release();
    await page.parts.idle();
    assert.deepEqual(page.panel.notices, [], step);
  }
});

// ---- removing a part, New plate

test('removing a part drops its row, its bytes and its stored entry, stops its upload and the worker forgets it', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/parts', ...Array.from({ length: 5 }, () => steps.drop()));
  await page.parts.addFiles([file('gone.stl')]);
  await page.clock.advance(2 * S);
  const made = uploads(page.server).length;
  const { key } = page.parts.rows()[0];
  await page.parts.remove(key);
  await page.clock.advance(100 * S);
  assert.equal(uploads(page.server).length, made);
  assert.deepEqual(page.parts.rows(), []);
  assert.deepEqual(page.storage.plate().parts, []);
  assert.equal(page.b.records.keys().filter((k) => k.startsWith('part-bytes/')).length, 0);
  assert.equal(page.api.pending(), 0);
  assert.ok(page.worker.posted.some((p) => p.message.op === 'forget' && p.message.key === key));
  assert.deepEqual(page.panel.notices, []);
});

test('New plate empties the plate with a new plate_id, keeps the filament, profile and changes, and stops every upload', async () => {
  const page = await openPage();
  await page.storage.update({ settings: { filament: 'PLA', profile: 'Draft', changes: { wall_loops: '5' } } });
  await page.parts.addFiles([file('a.stl')]);
  await page.parts.idle();
  page.server.script('POST', '/api/parts', steps.hold());
  await page.parts.addFiles([file('b.stl')]);
  const before = page.store.get().plateId;
  page.store.set({ sliced: true });
  await page.parts.newPlate();
  assert.notEqual(page.store.get().plateId, before);
  assert.equal(page.store.get().plateId, page.storage.plate().plate_id);
  assert.deepEqual(page.parts.rows(), []);
  assert.deepEqual(page.storage.plate().parts, []);
  assert.deepEqual(page.storage.plate().settings, { filament: 'PLA', profile: 'Draft', changes: { wall_loops: '5' } });
  assert.equal(page.store.get().sliced, false);
  assert.deepEqual(page.store.get().plate, { ...page.store.get().plate, parts: 0, instances: 0, arriving: 0, arrivingInstances: 0 });
  assert.equal(page.b.records.keys().filter((k) => k.includes(before)).length, 0);
  assert.equal(page.api.pending(), 0);
  await page.parts.idle();
  assert.deepEqual(page.parts.rows(), []);
});

test('a part still being added when New plate is pressed does not land on the new plate', async () => {
  let release = null;
  const page = await openPage(browser(), {
    hash: async (bytes) => { if (!release) await new Promise((r) => { release = r; }); return hex(bytes); },
  });
  const adding = page.parts.addFiles([file('late.stl')]);
  await settle();
  const renewing = page.parts.newPlate();
  release();
  await adding;
  await renewing;
  await page.parts.idle();
  assert.deepEqual(page.parts.rows(), []);
  assert.deepEqual(page.storage.plate().parts, []);
});

test('a part still being kept in the browser\'s storage when New plate is pressed is never uploaded', async () => {
  const page = await openPage();
  let release = null;
  let reached = null;
  const kept = new Promise((r) => { release = r; });
  const writing = new Promise((r) => { reached = r; });
  const addPart = page.storage.addPart;
  page.storage.addPart = async (...args) => { const out = await addPart(...args); reached(); await kept; return out; };
  const adding = page.parts.addFiles([file('late.stl')]);
  await writing;
  const renewing = page.parts.newPlate();
  release();
  await adding;
  await renewing;
  await page.parts.idle();
  assert.equal(uploads(page.server).length, 0);
  assert.deepEqual(page.parts.rows(), []);
  assert.deepEqual(page.storage.plate().parts, []);
});

// ---- the switch

test('the switch starts at the configuration\'s upload_units, and the user\'s choice is kept in the browser\'s storage', async () => {
  const b = browser();
  const first = await openPage(b, { uploadUnits: 'mm' });
  assert.equal(first.parts.units(), 'mm');
  first.parts.setUnits('in');
  assert.equal(first.parts.units(), 'in');
  await first.storage.written();
  assert.equal(b.records.value('uploadUnits'), 'in');
  b.locks.closeTab('A');
  const again = await openPage(b, { uploadUnits: 'mm' });
  assert.equal(again.parts.units(), 'in');
});

test('a switch never chosen follows the configuration as it is read', async () => {
  const page = await openPage(browser(), { uploadUnits: 'in' });
  page.store.set({ configuration: { ...page.store.get().configuration, upload_units: 'mm' } });
  assert.equal(page.parts.units(), 'mm');
});

test('units other than the two are a fault of the page', async () => {
  const page = await openPage();
  assert.throws(() => page.parts.setUnits('cm'), /units/);
});

// ---- a refreshed page

test('a refreshed page takes up its stored parts: a part with its record arrives at once, one without is uploaded again', async () => {
  const b = browser();
  const first = await openPage(b);
  await first.parts.addFiles([file('done.stl')]);
  await first.parts.idle();
  first.server.script('POST', '/api/parts', steps.hold());
  await first.parts.addFiles([file('pending.stl')]);
  first.parts.setQuantity(first.parts.rows()[0].key, 4);
  await first.storage.written();
  b.locks.closeTab('A');
  const made = uploads(b.server).length;
  const again = await openPage(b);
  assert.deepEqual(rowsOf(again.parts), [
    { name: 'done', units: 'in', quantity: 4, arriving: false },
    { name: 'pending', units: 'in', quantity: 1, arriving: true },
  ]);
  await again.parts.idle();
  assert.equal(uploads(b.server).length, made + 1);
  assert.equal(again.parts.rows()[1].arriving, false);
  assert.ok(again.parts.rows().every((r) => r.drawn));
  assert.deepEqual(again.store.get().plate, { ...again.store.get().plate, parts: 2, instances: 5 });
});

test('a part whose bytes the browser refused is added, marked not saved', async () => {
  const b = browser();
  b.records.refuse('part-bytes/');
  const page = await openPage(b);
  await page.parts.addFiles([file('unsaved.stl')]);
  await page.parts.idle();
  const [row] = page.parts.rows();
  assert.equal(row.saved, false);
  assert.equal(row.arriving, false);
  assert.ok(page.reports.some((r) => r.what === 'storage_refused'));
});

test('every listener is told of each change', async () => {
  const page = await openPage();
  let told = 0;
  page.parts.subscribe(() => { told += 1; });
  await page.parts.addFiles([file('t.stl')]);
  await page.parts.idle();
  assert.ok(told >= 2);
});

test('the sentences of the Parts step say no role words', () => {
  const all = Object.values(sentences).map((v) => JSON.stringify(typeof v === 'function' ? v('X', 2, 3) : v)).join(' ');
  assert.doesNotMatch(all, /student|mentor|team/i);
});
