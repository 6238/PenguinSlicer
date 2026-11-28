// The result of a sliced plate, a sliced plate that expires, and the Send step's Download
// (src/result.js and src/slicing.js; wizard/README-details.md, "The result", "A sliced plate that
// expires", "The Send step"), reached on purpose from the fake front server on the fake clock. What
// needs the browser (the layer preview drawn, the colour key, the buttons) is in
// tests_browser/test_result_send.py.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { STILL_HERE_NOTICE, createResult, hoursMinutes, sizeText } from '../src/result.js';
import { createSlicing } from '../src/slicing.js';
import { createStore } from '../src/state.js';
import { offersSliceAgain } from '../src/panel/preview-step.js';
import * as R from '../src/result-sentences.js';
import * as T from '../src/slicing-sentences.js';
import { SLICED_FILE_KEEP_S } from '../src/page-constants.js';
import { errorReport, events, example, steps } from './fakes/front_server.js';
import {
  A, B, EVENTS, JOB, S, accepted, doneReport, feedStream, hex, openPage, progress,
} from './fakes/preview-page.js';

const SUMMARY = `/api/slices/${JOB}/summary`;
const FILE = `/api/slices/${JOB}/file`;
const details = (fields = {}) => ({ ...example('wizard-front/slice-summary.json').sliced_file, ...fields });

// A page whose plate is sliced on the Preview step, its done report carrying these details.
async function sliced(fields = {}, page = null) {
  const p = page ?? await openPage();
  feedStream(p, events.progress(progress()), events.progress(doneReport(41, fields)));
  await p.enter();
  assert.equal(p.view().kind, 'done');
  return p;
}

// ---- the result

test('a sliced plate shows the print time and filament large, and one quiet line of instances, layers and how long it took', async () => {
  const page = await sliced();
  const r = page.result.preview();
  assert.deepEqual(r.stats, [{ label: R.PRINT_TIME, value: '36 min' }, { label: R.FILAMENT, value: '16 g PETG' }]);
  assert.equal(r.line, '3 instances · 200 layers · sliced in 0:52');
  assert.deepEqual(r.warnings, []);
  assert.equal(page.store.get().sliced, true);
  assert.equal(page.view().details.file, 'Bracket_plus1-20261009-1432.gcode.3mf');
});

test('the summary\'s warnings and the part warnings\' messages are the result\'s warnings', async () => {
  const summary = { ...details().summary, warnings: ['Floating regions on Bracket #2'], part_warnings: [{ code: 'slice.part_not_watertight', message: 'Spacer is not watertight.', where: { part: 'p2' }, detail: 'x' }] };
  const page = await sliced({ summary });
  assert.deepEqual(page.result.preview().warnings, ['Floating regions on Bracket #2', 'Spacer is not watertight.']);
});

test('a figure the summary gives as null is left out of its line, never shown as a failure', async () => {
  const summary = { ...details().summary, print_time_s: null, layer_count: null, instances: 1 };
  const page = await sliced({ summary });
  const r = page.result.preview();
  assert.deepEqual(r.stats, [{ label: R.FILAMENT, value: '16 g PETG' }]);
  assert.equal(r.line, '1 instance · sliced in 0:52');
  const noGrams = await sliced({ summary: { ...details().summary, filament_g: null } });
  assert.deepEqual(noGrams.result.preview().stats.map((s) => s.label), [R.PRINT_TIME]);
});

test('a done report without the sliced file\'s details: the page asks the summary, and shows its figures', async () => {
  const page = await openPage();
  const { sliced_file: _gone, ...bare } = doneReport();
  page.server.script('GET', SUMMARY, steps.answer(200, { sliced_file: details({ summary: { ...details().summary, filament_g: 84.2 } }) }));
  feedStream(page, events.progress(bare));
  await page.enter();
  assert.equal(page.server.made('GET', SUMMARY).length, 1);
  assert.equal(page.result.preview().stats[1].value, '84 g PETG');
});

test('the summary refused as expired: the expired message with the front server\'s sentence', async () => {
  const page = await openPage();
  const { sliced_file: _gone, ...bare } = doneReport();
  const gone = errorReport('front.sliced_file_expired');
  page.server.script('GET', SUMMARY, steps.report(gone));
  feedStream(page, events.progress(bare));
  await page.enter();
  assert.equal(page.view().kind, 'expired');
  assert.equal(page.view().what, gone.message);
  assert.equal(page.view().todo, gone.remedy);
});

test('the summary refused otherwise is that refusal, shown with Slice again', async () => {
  const page = await openPage();
  const { sliced_file: _gone, ...bare } = doneReport();
  const unknown = errorReport('front.slice_unknown');
  page.server.script('GET', SUMMARY, steps.report(unknown));
  feedStream(page, events.progress(bare));
  await page.enter();
  assert.equal(page.view().kind, 'failed');
  assert.equal(page.view().what, unknown.message);
  assert.deepEqual(page.view().actions.map((a) => a.id), ['again', 'layout']);
  assert.equal(page.store.get().sliced, false);
});

test('the summary answered 200 without valid details: wizard.bad_answer, shown with its buttons, and the plate not sliced', async () => {
  for (const body of [{}, { sliced_file: null }, { sliced_file: { summary: {} } }, { sliced_file: { file: 'x.gcode.3mf' } }]) {
    const page = await openPage();
    const { sliced_file: _gone, ...bare } = doneReport();
    page.server.script('GET', SUMMARY, steps.answer(200, body));
    feedStream(page, events.progress(bare));
    await page.enter();
    assert.equal(page.server.made('GET', SUMMARY).length, 1);
    assert.equal(page.view().kind, 'failed');
    assert.equal(page.view().report.code, 'wizard.bad_answer');
    assert.ok(page.view().what);
    assert.deepEqual(page.view().actions.map((a) => a.id), ['again', 'layout']);
    assert.equal(page.store.get().sliced, false);
    assert.equal(page.result.preview(), null);
  }
});

test('the sliced file is fetched for the layer preview with the page\'s headers, its bytes as they came', async () => {
  const page = await sliced();
  page.server.script('GET', FILE, { kind: 'answer', status: 200, body: 'PK-sliced', headers: { 'Content-Type': 'application/octet-stream' } });
  const got = await page.result.file();
  assert.equal(got.ok, true);
  assert.equal(new TextDecoder().decode(got.bytes), 'PK-sliced');
  const [request] = page.server.made('GET', FILE);
  assert.equal(request.headers['x-penguinslicer-group'], page.store.get().group);
});

test('the sliced file refused as expired for the preview: the expired message in place of the result, with the front server\'s sentence', async () => {
  const page = await sliced();
  const gone = errorReport('front.sliced_file_expired');
  page.server.script('GET', FILE, steps.report(gone));
  const got = await page.result.file();
  assert.equal(got.ok, false);
  assert.equal(got.expired, true);
  assert.equal(page.view().kind, 'expired');
  assert.equal(page.view().what, gone.message);
  assert.equal(page.store.get().sliced, false);
});

test('the sliced file refused otherwise is that refusal, for the preview to show in place of the view', async () => {
  const page = await sliced();
  const busy = errorReport('front.sliced_file_not_ready');
  page.server.script('GET', FILE, steps.report(busy));
  const got = await page.result.file();
  assert.equal(got.ok, false);
  assert.equal(got.report.code, 'front.sliced_file_not_ready');
  assert.equal(page.view().kind, 'done');
});

test('the ghost is the sliced plate configuration\'s instances with each part\'s corners under its key; none when a part has none', async () => {
  const page = await sliced();
  const a = new Float32Array(9);
  page.meshes.set(`${hex(A)}.mm`, { positions: a });
  assert.equal(page.result.ghost(), null);
  const b = new Float32Array(18);
  page.meshes.set(`${hex(B)}.in`, { positions: b });
  const ghost = page.result.ghost();
  assert.deepEqual(Object.keys(ghost.meshes), ['p1', 'p2']);
  assert.equal(ghost.meshes.p1, a);
  assert.equal(ghost.meshes.p2, b);
  assert.deepEqual(ghost.instances.map((i) => i.ref), ['p1', 'p1', 'p2']);
});

test('of the preview\'s own failures only a file it cannot read offers Slice again', () => {
  assert.equal(offersSliceAgain('wizard.preview_unreadable'), true);
  for (const code of ['wizard.preview_failed', 'wizard.preview_not_drawable', 'front.sliced_file_not_ready', 'wizard.bad_answer']) {
    assert.equal(offersSliceAgain(code), false, code);
  }
});

// ---- a sliced plate that expires

test('the expired message replaces the result exactly expires_in_s after the answer arrived, whatever its expires_at says', async () => {
  const page = await sliced({ expires_in_s: 600, expires_at: '2020-01-01T00:00:00Z' });
  await page.clock.advance(600 * S - 1);
  assert.equal(page.view().kind, 'done');
  assert.equal(page.store.get().sliced, true);
  await page.clock.advance(1);
  const view = page.view();
  assert.equal(view.kind, 'expired');
  assert.equal(view.what, T.EXPIRED_WHAT);
  assert.equal(view.todo, T.EXPIRED_TODO);
  assert.deepEqual(view.actions.map((a) => [a.id, a.label, a.primary]), [['again', T.SLICE_AGAIN, true]]);
  assert.equal(page.store.get().sliced, false);
  assert.equal(page.store.get().expired, true);
  assert.equal(page.submissions().length, 1);                 // never sliced again by itself
  await page.clock.advance(3600 * S);
  assert.equal(page.submissions().length, 1);
});

test('the wizard\'s expired sentence is the guide\'s', () => {
  assert.equal(`${T.EXPIRED_WHAT} ${T.EXPIRED_TODO}`, 'This plate\'s slice has expired. A sliced plate is kept for two hours after it is sliced or after its last print ends. Slice it again to print it; your parts, layout and settings are unchanged.');
});

test('on the Send step the expired message takes the place of Send; Slice again goes to the Preview step and submits once, with a new value', async () => {
  const page = await sliced({ expires_in_s: 60 });
  await page.leave('send');
  await page.clock.advance(60 * S);
  assert.equal(page.view().kind, 'expired');
  assert.equal(page.store.get().expired, true);
  feedStream(page);
  await page.view().actions[0].run();
  await page.clock.advance(0);
  assert.equal(page.store.get().step, 'preview');
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.notEqual(sent[1].submission_id, sent[0].submission_id);
  assert.equal(page.view().kind, 'card');
  assert.equal(page.store.get().expired, false);
});

test('Slice again on the Preview step submits with a new value', async () => {
  const page = await sliced({ expires_in_s: 5 });
  await page.clock.advance(5 * S);
  feedStream(page);
  await page.view().actions[0].run();
  await page.clock.advance(0);
  assert.equal(page.submissions().length, 2);
  assert.equal(page.view().kind, 'card');
});

test('on the Layout step nothing is shown of the expiry, and entering the Preview step afterwards slices', async () => {
  const page = await sliced({ expires_in_s: 60 });
  await page.leave('layout');
  await page.clock.advance(60 * S);
  assert.equal(page.store.get().sliced, false);
  assert.equal(page.notices.length, 0);
  feedStream(page);
  await page.enter();
  assert.equal(page.submissions().length, 2);
  assert.equal(page.view().kind, 'card');
});

test('a notification that the sliced plate "is still here" goes at the moment it expires', async () => {
  const page = await sliced({ expires_in_s: 60 });
  page.notices.push({ key: STILL_HERE_NOTICE, what: 'Your sliced plate is still here.' }, { key: 'other', what: 'Something else.' });
  await page.clock.advance(60 * S);
  assert.deepEqual(page.notices.map((n) => n.key), ['other']);
});

test('expires_in_s null shows no expiry until a later answer gives one', async () => {
  const page = await sliced({ expires_in_s: null, expires_at: null });
  await page.clock.advance(3 * 3600 * S);
  assert.equal(page.view().kind, 'done');
  await page.leave('send');
  page.server.script('GET', SUMMARY, steps.answer(200, { sliced_file: details({ expires_in_s: 60 }) }));
  await page.result.download();
  await page.clock.advance(60 * S - 1);
  assert.equal(page.view().kind, 'done');
  await page.clock.advance(1);
  assert.equal(page.view().kind, 'expired');
});

test('a new slice of the plate ends the earlier slice\'s count to its expiry', async () => {
  const page = await sliced({ expires_in_s: 60 });
  await page.leave();
  const plate = page.storage.plate();
  await page.storage.update({ instances: plate.instances.map((i, n) => (n === 0 ? { ...i, x: 90 } : i)) });
  const feed = feedStream(page, events.progress(progress()));
  await page.enter();
  for (let t = 0; t < 120; t += 15) { await page.clock.advance(15 * S); feed.send(events.keepAlive()); }
  assert.equal(page.view().kind, 'card');
  assert.equal(page.store.get().expired, false);
});

test('a slice job answered failed with front.sliced_file_expired: the expired message with the front server\'s sentence', async () => {
  const page = await openPage();
  const gone = errorReport('front.sliced_file_expired');
  feedStream(page, events.progress(progress({ state: 'failed', error: gone, sequence: 42 })));
  await page.enter();
  assert.equal(page.view().kind, 'expired');
  assert.equal(page.view().what, gone.message);
  assert.equal(page.view().todo, gone.remedy);
  assert.equal(page.store.get().expired, true);
});

test('a progress stream refused with 410 front.sliced_file_expired: the expired message with the front server\'s sentence, and nothing sliced again', async () => {
  const page = await openPage();
  const feed = feedStream(page, events.progress(progress()));
  await page.enter();
  const gone = errorReport('front.sliced_file_expired');
  page.server.script('GET', EVENTS, steps.report(gone));
  feed.end();
  await page.clock.advance(0);
  assert.equal(page.server.made('GET', EVENTS).length, 2);
  assert.equal(page.view().kind, 'expired');
  assert.equal(page.view().what, gone.message);
  assert.equal(page.view().todo, gone.remedy);
  assert.equal(page.store.get().expired, true);
  await page.clock.advance(3600 * S);
  assert.equal(page.submissions().length, 1);
  assert.equal(page.server.made('GET', EVENTS).length, 2);
});

test('a slice job unknown two hours or more after it was submitted: the expired message with the wizard\'s sentence; entering the step again slices', async () => {
  const page = await openPage();
  const feed = feedStream(page, events.progress(progress()));
  await page.enter();
  for (let t = 0; t < SLICED_FILE_KEEP_S; t += 15) { await page.clock.advance(15 * S); feed.send(events.keepAlive()); }
  page.server.script('GET', EVENTS, steps.report(errorReport('front.slice_unknown')));
  feed.end();
  await page.clock.advance(0);
  assert.equal(page.submissions().length, 1);
  assert.equal(page.view().kind, 'expired');
  assert.equal(page.view().what, T.EXPIRED_WHAT);
  await page.leave();
  feedStream(page);
  await page.enter();
  assert.equal(page.submissions().length, 2);
  assert.equal(page.view().kind, 'card');
});

// ---- the Send step

test('the Send step\'s card: the instances by part, the print time and the grams, and no printer', async () => {
  const page = await sliced();
  assert.deepEqual(page.result.send(), { count: R.ON_ONE_PLATE(3), parts: ['2 × Bracket', 'Spacer'], printTime: '36 min', grams: '16 g', filament: R.OF_FILAMENT('PETG') });
});

test('Download asks the details first, then saves the file by a plain link naming the current group, with a notification of the plate and its true size', async () => {
  const page = await sliced();
  await page.leave('send');
  page.server.script('GET', SUMMARY, steps.answer(200, { sliced_file: details({ size_bytes: 3_984_588 }) }));
  const outcome = await page.result.download();
  assert.equal(outcome.ok, true);
  assert.equal(page.server.made('GET', SUMMARY)[0].headers['x-penguinslicer-group'], page.store.get().group);
  assert.deepEqual(page.saved, [{ href: `${FILE}?group=${encodeURIComponent(page.store.get().group)}`, name: 'Bracket_plus1-20261009-1432.gcode.3mf' }]);
  assert.equal(page.notices.length, 1);
  assert.equal(page.notices[0].what, R.DOWNLOADED(3, '3.8 MB'));
  assert.equal(page.notices[0].what, 'Downloaded the sliced file of 3 instances (3.8 MB).');
});

test('Download refused as expired: the expired message in place of Send with the front server\'s sentence, and nothing saved', async () => {
  const page = await sliced();
  await page.leave('send');
  const gone = errorReport('front.sliced_file_expired');
  page.server.script('GET', SUMMARY, steps.report(gone));
  const outcome = await page.result.download();
  assert.equal(outcome.expired, true);
  assert.deepEqual(page.saved, []);
  assert.equal(page.view().kind, 'expired');
  assert.equal(page.view().what, gone.message);
  assert.equal(page.store.get().expired, true);
  assert.equal(page.notices.length, 0);
});

test('Download refused otherwise is that refusal, for the Send step to show, and nothing saved', async () => {
  const page = await sliced();
  await page.leave('send');
  page.server.script('GET', SUMMARY, steps.report(errorReport('front.slice_unknown')));
  const outcome = await page.result.download();
  assert.equal(outcome.ok, false);
  assert.equal(outcome.report.code, 'front.slice_unknown');
  assert.deepEqual(page.saved, []);
  assert.equal(page.view().kind, 'done');
});

test('Download answered 200 without valid details: wizard.bad_answer for the Send step to show, nothing saved and no notification', async () => {
  for (const body of [{}, { sliced_file: null }, { sliced_file: { summary: {} } }, { sliced_file: details({ file: '' }) }]) {
    const page = await sliced();
    await page.leave('send');
    page.server.script('GET', SUMMARY, steps.answer(200, body));
    const outcome = await page.result.download();
    assert.equal(outcome.ok, false);
    assert.equal(outcome.report.code, 'wizard.bad_answer');
    assert.ok(outcome.report.message && outcome.report.remedy);
    assert.deepEqual(page.saved, []);
    assert.equal(page.notices.length, 0);
    assert.equal(page.view().kind, 'done');
  }
});

// The request the page makes next, once it has been made.
async function nextRequest(page) {
  return page.server.arrived(page.server.requests.length + 1);
}

test('a Download whose details arrive after the plate has expired saves nothing, notifies nothing and leaves the expired message', async () => {
  const page = await sliced({ expires_in_s: 1 });
  await page.leave('send');
  page.server.script('GET', SUMMARY, steps.hold());
  const asked = nextRequest(page);
  const downloading = page.result.download();
  const request = await asked;
  await page.clock.advance(1 * S);
  assert.equal(page.view().kind, 'expired');
  request.held.release(steps.answer(200, { sliced_file: details({ expires_in_s: 7200 }) }));
  const outcome = await downloading;
  assert.deepEqual(outcome, { ok: false });
  assert.deepEqual(page.saved, []);
  assert.equal(page.notices.length, 0);
  assert.equal(page.view().kind, 'expired');
  assert.equal(page.view().what, T.EXPIRED_WHAT);
  assert.equal(page.store.get().expired, true);
});

test('a Download whose details arrive after a new slice has ended saves nothing and leaves the new slice\'s details', async () => {
  const NEW = 'b7e10d44';
  const page = await sliced();
  await page.leave('send');
  page.server.script('GET', SUMMARY, steps.hold());
  const asked = nextRequest(page);
  const downloading = page.result.download();
  const request = await asked;
  // the plate changed and sliced again while the details were on their way
  await page.leave('layout');
  const plate = page.storage.plate();
  await page.storage.update({ instances: plate.instances.map((i, n) => (n === 0 ? { ...i, x: 90 } : i)) });
  page.server.script('POST', '/api/slices', steps.answer(202, { slice: { ...accepted().slice, id: NEW } }));
  feedStream(page, events.progress({ ...doneReport(41, { file: 'Bracket_plus1-new.gcode.3mf' }), job: NEW }));
  await page.enter();
  assert.equal(page.view().kind, 'done');
  assert.equal(page.view().slice, NEW);
  await page.leave('send');
  request.held.release(steps.answer(200, { sliced_file: details({ file: 'old.gcode.3mf', expires_in_s: 5 }) }));
  const outcome = await downloading;
  assert.deepEqual(outcome, { ok: false });
  assert.deepEqual(page.saved, []);
  assert.equal(page.notices.length, 0);
  assert.equal(page.view().slice, NEW);
  assert.equal(page.view().details.file, 'Bracket_plus1-new.gcode.3mf');
  await page.clock.advance(5 * S);
  assert.equal(page.view().kind, 'done');           // the old details' expiry was not taken
});

test('the sliced file for the preview arriving after the plate has expired is not handed on', async () => {
  const page = await sliced({ expires_in_s: 1 });
  page.server.script('GET', FILE, steps.hold());
  const asked = nextRequest(page);
  const fetching = page.result.file();
  const request = await asked;
  await page.clock.advance(1 * S);
  assert.equal(page.view().kind, 'expired');
  request.held.release({ kind: 'answer', status: 200, body: 'PK-sliced', headers: { 'Content-Type': 'application/octet-stream' } });
  assert.deepEqual(await fetching, { ok: false, stopped: true });
  assert.equal(page.view().kind, 'expired');
});

test('a summary asked after a bare done report and arriving after a new slice has ended is set aside: the new slice keeps its details and its expiry', async () => {
  const NEW = 'b7e10d44';
  for (const late of [
    steps.answer(200, { sliced_file: details({ file: 'old.gcode.3mf', expires_in_s: 5 }) }),
    steps.report(errorReport('front.slice_unknown')),
    steps.report(errorReport('front.sliced_file_expired')),
  ]) {
    const page = await openPage();
    const { sliced_file: _gone, ...bare } = doneReport();
    page.server.script('GET', SUMMARY, steps.hold());
    feedStream(page, events.progress(bare));
    await page.enter();
    assert.equal(page.view().kind, 'done');
    const [asked] = page.server.made('GET', SUMMARY);
    assert.ok(asked.held);
    // the plate changes and is sliced again while the old slice's summary is on its way
    await page.leave('layout');
    const plate = page.storage.plate();
    await page.storage.update({ instances: plate.instances.map((i, n) => (n === 0 ? { ...i, x: 90 } : i)) });
    page.server.script('POST', '/api/slices', steps.answer(202, { slice: { ...accepted().slice, id: NEW } }));
    feedStream(page, events.progress({ ...doneReport(41, { file: 'new.gcode.3mf' }), job: NEW }));
    await page.enter();
    assert.equal(page.view().slice, NEW);
    asked.held.release(late);
    await page.clock.advance(0);
    assert.equal(page.view().kind, 'done');
    assert.equal(page.view().slice, NEW);
    assert.equal(page.view().details.file, 'new.gcode.3mf');
    await page.clock.advance(5 * S);
    assert.equal(page.view().kind, 'done');           // the old summary's expiry was not taken
    assert.equal(page.store.get().sliced, true);
  }
});

test('a summary asked after a bare done report and arriving after the same slice has expired is set aside: the expired message stays', async () => {
  for (const late of [
    steps.report(errorReport('front.slice_unknown')),
    steps.answer(200, {}),
    steps.answer(200, { sliced_file: details() }),
  ]) {
    const page = await openPage();
    const { sliced_file: _gone, ...bare } = doneReport();
    page.server.script('GET', SUMMARY, steps.hold());
    feedStream(page, events.progress(bare));
    await page.enter();
    const [asked] = page.server.made('GET', SUMMARY);
    assert.ok(asked.held);
    // another request about the same sliced plate (the file for the layer preview) was refused as
    // expired while the summary was on its way; no new slice has begun
    const gone = errorReport('front.sliced_file_expired');
    page.slicing.expire(gone, JOB);
    assert.equal(page.view().kind, 'expired');
    asked.held.release(late);
    await page.clock.advance(0);
    assert.equal(page.view().kind, 'expired');
    assert.equal(page.view().what, gone.message);
    assert.equal(page.store.get().sliced, false);
  }
});

test('a page that follows the plate\'s stored slice to done has the Send step\'s card, and Download saves and notifies once', async () => {
  const page = await openPage();
  feedStream(page, events.progress(progress()));
  await page.enter();
  // a second page on the same stored plate follows the stored slice to its end
  const store = createStore();
  store.set({ ...page.store.get(), step: 'layout', sliced: false });
  const notices = [];
  const saved = [];
  const panel = { goTo: (s) => store.set({ step: s }), notify: (n) => notices.push(n), dropNotice() {} };
  const slicing = createSlicing({ api: page.api, clock: page.clock, storage: page.storage, store, settings: {}, layout: page.layout, panel, report() {}, newId: () => 'other', random: () => 0.5 });
  const result = createResult({ api: page.api, slicing, store, panel, geometry: { mesh: () => null }, save: (href, name) => saved.push({ href, name }) });
  feedStream(page, events.progress(doneReport(42)));
  store.set({ step: 'preview' });
  await page.clock.advance(0);
  assert.equal(page.submissions().length, 1);
  assert.equal(slicing.model().kind, 'done');
  store.set({ step: 'send' });
  assert.deepEqual(result.send(), { count: R.ON_ONE_PLATE(3), parts: ['2 × Bracket', 'Spacer'], printTime: '36 min', grams: '16 g', filament: R.OF_FILAMENT('PETG') });
  page.server.script('GET', SUMMARY, steps.answer(200, { sliced_file: details({ size_bytes: 3_984_588 }) }));
  assert.deepEqual(await result.download(), { ok: true });
  assert.equal(saved.length, 1);
  assert.deepEqual(notices.map((n) => n.what), [R.DOWNLOADED(3, '3.8 MB')]);
});

test('the Send step\'s card names no part without an instance', () => {
  const body = {
    parts: { p1: { name: 'Bracket' }, p2: { name: 'Unplaced' }, p3: { name: 'Spacer' } },
    instances: [{ ref: 'p1' }, { ref: 'p3' }],
  };
  const slicing = { model: () => ({ kind: 'done', slice: JOB, body, details: details(), report: doneReport() }) };
  const result = createResult({ api: null, slicing, store: createStore(), panel: {}, geometry: { mesh: () => null }, save() {} });
  assert.deepEqual(result.send().parts, ['Bracket', 'Spacer']);
});

test('a Download whose sliced plate has no plate configuration at hand is no sliced plate: nothing asked, saved or thrown', async () => {
  const slicing = { model: () => ({ kind: 'done', slice: JOB, body: undefined, details: details(), report: doneReport() }), takeDetails() {}, expire() {} };
  const saved = [];
  const page = await openPage();
  const result = createResult({ api: page.api, slicing, store: page.store, panel: { notify() {} }, geometry: { mesh: () => null }, save: (h, n) => saved.push({ h, n }) });
  assert.deepEqual(await result.download(), { ok: false });
  assert.equal(page.server.made('GET', /summary/).length, 0);
  assert.deepEqual(saved, []);
});

test('a refusal as expired naming another sliced plate leaves this one sliced', async () => {
  const page = await sliced();
  page.slicing.expire(errorReport('front.sliced_file_expired'), 'another-slice');
  assert.equal(page.view().kind, 'done');
  assert.equal(page.store.get().sliced, true);
});

test('a size the details give below nothing is left out of the notification', async () => {
  const page = await sliced();
  await page.leave('send');
  page.server.script('GET', SUMMARY, steps.answer(200, { sliced_file: details({ size_bytes: -5 }) }));
  assert.equal((await page.result.download()).ok, true);
  assert.equal(page.notices[0].what, R.DOWNLOADED_NO_SIZE(3));
});

test('Download with no sliced plate does nothing', async () => {
  const page = await openPage();
  const outcome = await page.result.download();
  assert.equal(outcome.ok, false);
  assert.equal(page.server.made('GET', /summary/).length, 0);
  assert.equal(page.result.preview(), null);
  assert.equal(page.result.send(), null);
});

// ---- the words

test('the print time in hours and minutes, as the mockup writes it', () => {
  assert.equal(hoursMinutes(11_520), '3 h 12 min');
  assert.equal(hoursMinutes(3600), '1 h 0 min');
  assert.equal(hoursMinutes(2145), '36 min');
  assert.equal(hoursMinutes(20), '1 min');
  assert.equal(hoursMinutes(0), '0 min');
});

test('a file\'s size in the units of the contracts (a megabyte of 1,048,576 bytes)', () => {
  assert.equal(sizeText(1_843_207), '1.8 MB');
  assert.equal(sizeText(52_428_800), '50.0 MB');
  assert.equal(sizeText(40_960), '40 KB');
  assert.equal(sizeText(900), '900 bytes');
  assert.equal(sizeText(1), '1 byte');
});

test('the colour key has always its four rows, in the guide\'s colours', () => {
  assert.deepEqual(R.KEY.map((k) => [k.label, k.colour]), [
    ['Walls', '#2b5c9e'], ['Infill', '#e0912f'], ['Top and bottom surfaces', '#2f9e7a'], ['Supports and brim', '#9a8fb8'],
  ]);
});

test('no sentence of the result or the Send step names a role', () => {
  const words = [R.HELP, R.RESET_VIEW, T.EXPIRED_WHAT, T.EXPIRED_TODO, R.DOWNLOADED(2, '1 MB'), R.ON_ONE_PLATE(2)].join(' ');
  assert.doesNotMatch(words, /student|mentor|team|administrator/i);
});

test('the result\'s instances are the sliced plate configuration\'s; parts of one part shown once', async () => {
  const page = await sliced();
  assert.equal(page.view().body.instances.length, 3);
  assert.deepEqual(Object.values(page.view().body.parts).map((p) => p.sha256), [hex(A), hex(B)]);
});
