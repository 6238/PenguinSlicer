// Submitting and following a plate, and every slice failure (src/slicing.js;
// wizard/README-details.md, "The Preview step": "Submitting a plate", "The slicing card", "While
// the slice service is stopping", "No room to wait", "When a slice fails", "Orca's own sentence
// under Details"). Each row of those tables is reached on purpose here from the fake front server,
// on the fake clock, with the real storage module over the fakes of the browser's storage; the
// Settings and Layout steps are stood in for by what the Preview step asks of them.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

import { createApi } from '../src/api.js';
import { RECONNECTED_LINE_S, SLICED_FILE_KEEP_S, STREAM_SILENT_S } from '../src/page-constants.js';
import { failureButtons, createSlicing } from '../src/slicing.js';
import * as T from '../src/slicing-sentences.js';
import { createStore } from '../src/state.js';
import { createStorage } from '../src/storage.js';
import { FakeClock } from './fakes/clock.js';
import { FakeFrontServer, errorReport, events, example, steps } from './fakes/front_server.js';
import { boxFile } from './fakes/stl.js';
import { FakeLocks, FakeRecords, FakeTab } from './fakes/storage.js';

const S = 1000;
const ME = example('wizard-front/me.json');
const JOB = '3f9a1c2b';
const EVENTS = /^\/api\/slices\/[\w-]+\/events$/;
const hex = (bytes) => createHash('sha256').update(new Uint8Array(bytes)).digest('hex');
const A = boxFile('bracket');
const B = boxFile('spacer', [40, 30, 10]);
const CONFIGURATION = example('configuration-default.json');

const progress = (fields) => ({ job: JOB, state: 'running', stage: 'generating_infill', stage_label: 'Generating infill', fraction: 0.42, elapsed_s: 31.5, expected_s: 75, sequence: 17, ...fields });
const accepted = (fields = {}) => ({ slice: { id: JOB, plate_id: 'x', submission_id: 'y', progress: progress({ state: 'queued', stage: 'queued', stage_label: 'Waiting for the slicer', ahead: 2, elapsed_s: 0, sequence: 1, fraction: undefined, ...fields }) } });
const doneReport = (sequence = 41) => ({ ...example('wizard-front/slice-done.json').progress, sequence });
const failedReport = (error, sequence = 30) => progress({ state: 'failed', error, sequence });

async function openPage({ step = 'layout', changes = {} } = {}) {
  const clock = new FakeClock();
  const server = new FakeFrontServer();
  const records = new FakeRecords();
  const store = createStore();
  let ids = 0;
  const newId = () => `id-${(ids += 1)}`;
  const api = createApi({ transport: server.transport, clock, version: 'v', currentGroup: () => store.get().group, random: () => 0.5 });
  const reports = [];
  const report = (what, fields = {}) => { reports.push({ what, ...fields }); };
  const storage = createStorage({ openRecords: () => records.open(), locks: new FakeLocks().forTab('A'), tab: new FakeTab(), clock, newId: () => 'plate-1', report });
  const { plate, group } = await storage.begin({ user: ME.user.id, groups: ME.groups });
  await storage.addPart({ sha256: hex(A), units: 'mm', name: 'Bracket', quantity: 2, record: null }, A);
  await storage.addPart({ sha256: hex(B), units: 'in', name: 'Spacer', quantity: 1, record: null }, B);
  await storage.update({
    settings: { filament: 'PETG', profile: 'Structural', changes },
    instances: [
      { part: `${hex(A)}.mm`, lay: [1, 0, 0, 0], angle: 0, x: 80, y: 80 },
      { part: `${hex(A)}.mm`, lay: [1, 0, 0, 0], angle: 90, x: 150, y: 80 },
      { part: `${hex(B)}.in`, lay: [1, 0, 0, 0], angle: 0, x: 240, y: 200 },
    ],
  });
  store.set({ user: ME.user, groups: ME.groups, group, plateId: plate.plate_id, step, configuration: CONFIGURATION, plate: { filament: 'PETG', profile: 'Structural' } });
  const layout = {
    problem: null, notes: [],
    async idle() { store.set({ layoutProblem: layout.problem }); },
    notSliced(text) { layout.notes.push(text); },
  };
  const settings = {
    setQuick(id, v) {
      const plateNow = storage.plate();
      storage.update({ settings: { ...plateNow.settings, changes: { ...plateNow.settings.changes, enable_support: v, support_type: 'tree(auto)' } } });
    },
  };
  const panel = { goTo: (s) => store.set({ step: s }) };
  const slicing = createSlicing({ api, clock, storage, store, settings, layout, panel, report, newId, random: () => 0.5 });
  const page = { clock, server, store, api, storage, slicing, reports, layout, records };
  page.enter = async () => { store.set({ step: 'preview' }); await clock.advance(0); };
  page.leave = async (to = 'layout') => { store.set({ step: to }); await clock.advance(0); };
  page.view = () => slicing.model();
  page.card = () => slicing.model().card;
  page.submissions = () => server.made('POST', '/api/slices').map((r) => JSON.parse(r.body));
  return page;
}

// A stream the test feeds, for the next progress stream the page opens.
function feedStream(page, ...chunks) {
  const stream = steps.stream([events.version(), ...chunks]);
  page.server.script('GET', EVENTS, stream);
  return stream.feed;
}

// ---- submitting

test('entering the Preview step submits the plate configuration, with the plate\'s id and a new submission value', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/slices', steps.answer(202, accepted()));
  feedStream(page);
  await page.enter();
  const [sent] = page.submissions();
  assert.equal(sent.plate_id, 'plate-1');
  assert.equal(sent.submission_id, 'id-1');
  assert.deepEqual(Object.keys(sent), ['plate_id', 'submission_id', 'parts', 'instances', 'printer', 'filament', 'process', 'overrides', 'local_time']);
  assert.deepEqual(sent.parts, { p1: { name: 'Bracket', sha256: hex(A), units: 'mm' }, p2: { name: 'Spacer', sha256: hex(B), units: 'in' } });
  assert.deepEqual(sent.instances, [
    { ref: 'p1', orientation: '+z', angle: 0, x: 80, y: 80 },
    { ref: 'p1', orientation: '+z', angle: 90, x: 150, y: 80 },
    { ref: 'p2', orientation: '+z', angle: 0, x: 240, y: 200 },
  ]);
  assert.deepEqual(sent.overrides, { wall_loops: '4', sparse_infill_density: '40%' });
  assert.equal(sent.local_time.length, 13);
  const request = page.server.made('POST', '/api/slices')[0];
  assert.equal(request.headers['x-penguinslicer-wizard'], '1');
  const kept = page.storage.plate().slice;
  assert.equal(kept.id, JOB);
  assert.equal(kept.submission_id, 'id-1');
  assert.equal(typeof kept.fingerprint, 'string');
  assert.equal(kept.submitted_ms, page.clock.now());
  assert.equal(page.view().kind, 'card');
  assert.equal(page.card().stage, T.WAITING_AHEAD(2));
  assert.equal(page.server.made('GET', EVENTS).length, 1);
});

test('the user\'s changes ride on the profile\'s own overrides', async () => {
  const page = await openPage({ changes: { wall_loops: '6', layer_height: '0.16' } });
  await page.enter();
  assert.deepEqual(page.submissions()[0].overrides, { wall_loops: '6', sparse_infill_density: '40%', layer_height: '0.16' });
});

test('a submission whose answer was lost is repeated with the same value, and one slice job is followed', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/slices', steps.drop(), steps.answer(202, accepted()));
  feedStream(page);
  await page.enter();
  await page.clock.advance(1 * S);
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.equal(sent[0].submission_id, sent[1].submission_id);
  assert.equal(page.server.made('GET', EVENTS).length, 1);
});

test('front.too_many_requests and front.slice_unreachable are retried quietly with the same value', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/slices', steps.report(errorReport('front.too_many_requests'), { retryAfter: 3 }), steps.report(errorReport('front.slice_unreachable')), steps.answer(202, accepted()));
  feedStream(page);
  await page.enter();
  await page.clock.advance(10 * S);
  const sent = page.submissions();
  assert.equal(sent.length, 3);
  assert.equal(new Set(sent.map((s) => s.submission_id)).size, 1);
  assert.equal(page.view().kind, 'card');
});

test('coming back to a plate unchanged submits nothing; a changed plate submits anew and the old slice is not followed', async () => {
  const page = await openPage();
  const first = feedStream(page, events.progress(progress()));
  await page.enter();
  await page.leave();
  await page.enter();
  assert.equal(page.submissions().length, 1);
  await page.leave();
  const plate = page.storage.plate();
  await page.storage.update({ instances: plate.instances.map((i, n) => (n === 0 ? { ...i, x: 90 } : i)) });
  feedStream(page);
  await page.enter();
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.equal(sent[1].plate_id, sent[0].plate_id);
  assert.notEqual(sent[1].submission_id, sent[0].submission_id);
  assert.equal(first.aborted, true);
});

test('a slice goes on when the user leaves the step: the page keeps following it', async () => {
  const page = await openPage();
  const feed = feedStream(page, events.progress(progress()));
  await page.enter();
  await page.leave('parts');
  feed.send(events.progress(doneReport()));
  await page.clock.advance(0);
  assert.equal(page.view().kind, 'done');
  assert.equal(page.store.get().sliced, true);
});

test('parts the slice service no longer holds are uploaded again from the browser\'s storage and the plate submitted again with the same value', async () => {
  const page = await openPage();
  const missing = errorReport('slice.part_missing', { action: 'refresh_parts', where: { stage: 'checking', missing_parts: [{ key: 'p1', sha256: hex(A), units: 'mm' }, { key: 'p2', sha256: hex(B), units: 'in' }] } });
  page.server.script('POST', '/api/slices', steps.report(missing, { status: 422 }), steps.answer(202, accepted()));
  feedStream(page);
  await page.enter();
  const uploads = page.server.made('POST', '/api/parts');
  assert.deepEqual(uploads.map((r) => r.path), ['/api/parts?units=mm', '/api/parts?units=in']);
  assert.deepEqual(new Uint8Array(uploads[0].body), new Uint8Array(A));
  assert.deepEqual(new Uint8Array(uploads[1].body), new Uint8Array(B));
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.equal(sent[1].submission_id, sent[0].submission_id);
  assert.equal(page.view().kind, 'card');
});

test('a second slice.part_missing is handled the same; a third is shown and reported, so that it never loops', async () => {
  const page = await openPage();
  const missing = errorReport('slice.part_missing', { action: 'refresh_parts', where: { stage: 'checking', missing_parts: [{ key: 'p1', sha256: hex(A), units: 'mm' }] } });
  page.server.script('POST', '/api/slices', ...[1, 2, 3].map(() => steps.report(missing, { status: 422 })));
  await page.enter();
  await page.clock.advance(60 * S);
  assert.equal(page.submissions().length, 3);
  assert.equal(page.server.made('POST', '/api/parts').length, 2);
  assert.equal(page.view().kind, 'failed');
  assert.equal(page.view().what, missing.message);
  assert.deepEqual(page.reports.map((r) => r.what), ['page_failed']);
});

test('slice.part_missing with no list of parts is a fault of the page, shown and reported', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/slices', steps.report(errorReport('slice.part_missing'), { status: 422 }));
  await page.enter();
  assert.equal(page.view().kind, 'failed');
  assert.deepEqual(page.view().actions.map((a) => a.id), ['again', 'layout']);
  assert.deepEqual(page.reports.map((r) => r.what), ['page_failed']);
  assert.equal(page.server.made('POST', '/api/parts').length, 0);
});

test('a part to upload again that the upload refuses is that refusal, shown', async () => {
  const page = await openPage();
  const missing = errorReport('slice.part_missing', { where: { stage: 'checking', missing_parts: [{ key: 'p1', sha256: hex(A), units: 'mm' }] } });
  page.server.script('POST', '/api/slices', steps.report(missing, { status: 422 }));
  page.server.script('POST', '/api/parts', steps.report(errorReport('slice.part_too_large'), { status: 422 }));
  await page.enter();
  assert.equal(page.view().kind, 'failed');
  assert.equal(page.view().report.code, 'slice.part_too_large');
});

test('a missing part whose bytes the browser no longer holds shows the slice service\'s own sentences', async () => {
  const page = await openPage();
  const missing = errorReport('slice.part_missing', { where: { stage: 'checking', missing_parts: [{ key: 'p9', sha256: 'f'.repeat(64), units: 'mm' }] } });
  page.server.script('POST', '/api/slices', steps.report(missing, { status: 422 }));
  await page.enter();
  assert.equal(page.view().kind, 'failed');
  assert.equal(page.view().what, missing.message);
  assert.equal(page.view().todo, missing.remedy);
});

test('a body over 1 MB is not sent: the wizard\'s own sentences, and Back to Parts', async () => {
  const page = await openPage();
  await page.storage.update({ parts: page.storage.plate().parts.map((p) => ({ ...p, name: 'n' })), settings: { filament: 'PETG', profile: 'Structural', changes: { filename_format: 'x'.repeat(1_100_000) } } });
  await page.enter();
  assert.equal(page.submissions().length, 0);
  assert.equal(page.view().kind, 'failed');
  assert.equal(page.view().report.code, 'wizard.plate_configuration_over_size');
  assert.deepEqual(page.view().actions.map((a) => a.id), ['parts']);
});

test('a plate whose profile the configuration no longer offers is not sent: Back to Settings', async () => {
  const page = await openPage();
  await page.storage.update({ settings: { filament: 'Nylon', profile: 'Standard', changes: {} } });
  await page.enter();
  assert.equal(page.submissions().length, 0);
  assert.equal(page.view().report.code, 'wizard.plate_not_ready');
  assert.deepEqual(page.view().actions.map((a) => a.id), ['settings']);
});

test('an accepted answer the page cannot use is the wizard\'s bad answer, shown with Slice again', async () => {
  const page = await openPage();
  page.server.script('POST', '/api/slices', steps.answer(202, { slice: { id: 'no spaces allowed' } }));
  await page.enter();
  assert.equal(page.view().kind, 'failed');
  assert.equal(page.view().report.code, 'wizard.bad_answer');
  assert.deepEqual(page.view().actions.map((a) => a.id), ['again', 'layout']);
});

// ---- no room to wait

test('slice.busy: an amber message with the slice service\'s sentences, "Your plate is unchanged." and Slice again; never retried by itself', async () => {
  const page = await openPage();
  const busy = errorReport('slice.busy', { retryable: true });
  page.server.script('POST', '/api/slices', steps.report(busy, { status: 503 }));
  await page.enter();
  const view = page.view();
  assert.equal(view.kind, 'busy');
  assert.equal(view.what, busy.message);
  assert.equal(view.todo, `${busy.remedy} ${T.PLATE_UNCHANGED}`);
  assert.deepEqual(view.actions.map((a) => [a.id, a.label]), [['again', T.SLICE_AGAIN]]);
  await page.clock.advance(600 * S);
  assert.equal(page.submissions().length, 1);
  assert.equal(page.api.board.state().kind, 'none');
  feedStream(page);
  await view.actions[0].run();
  await page.clock.advance(0);
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.notEqual(sent[1].submission_id, sent[0].submission_id);
  assert.equal(page.view().kind, 'card');
});

// ---- while the slice service is stopping

test('slice.stopping: the card waits with the restarting line, the same value is sent again at the waits of retrying, the panel line stays empty', async () => {
  const page = await openPage();
  const stopping = errorReport('slice.stopping', { retryable: true });
  page.server.script('POST', '/api/slices', ...Array.from({ length: 4 }, () => steps.report(stopping, { status: 503 })), steps.answer(202, accepted()));
  feedStream(page);
  await page.enter();
  assert.equal(page.view().kind, 'card');
  assert.equal(page.card().stage, T.RESTARTING);
  assert.equal(page.card().fraction, 0);
  assert.equal(page.card().left, '');
  await page.clock.advance(5 * S);
  assert.equal(page.card().elapsed, '0:05');
  assert.equal(page.card().elapsedWord, T.WAITED);
  await page.clock.advance(2 * S);                  // attempts at 0, 1, 3 and 7 s
  assert.equal(page.submissions().length, 4);
  assert.equal(page.api.board.state().kind, 'none');
  await page.clock.advance(8 * S);
  const sent = page.submissions();
  assert.equal(sent.length, 5);
  assert.equal(new Set(sent.map((s) => s.submission_id)).size, 1);
  assert.equal(page.card().stage, T.WAITING_AHEAD(2));
});

test('slice.stopping past 300 s: the red line with Try again, which submits again and starts the 300 s afresh', async () => {
  const page = await openPage();
  const stopping = errorReport('slice.stopping', { retryable: true });
  page.server.script('POST', '/api/slices', ...Array.from({ length: 40 }, () => steps.report(stopping, { status: 503 })));
  await page.enter();
  await page.clock.advance(299 * S);
  assert.equal(page.api.board.state().kind, 'none');
  await page.clock.advance(1 * S);
  assert.equal(page.api.board.state().kind, 'unreachable');
  const before = page.submissions().length;
  await page.clock.advance(600 * S);
  assert.equal(page.submissions().length, before);
  page.api.board.tryAgain();
  await page.clock.advance(0);
  assert.equal(page.submissions().length, before + 1);
  assert.equal(page.api.board.state().kind, 'none');
  await page.clock.advance(299 * S);
  assert.equal(page.api.board.state().kind, 'none');
  assert.equal(new Set(page.submissions().map((s) => s.submission_id)).size, 1);
});

// ---- the slicing card

test('slicing: the percentage, the stage in words, the times and the stages with the current one marked', async () => {
  const page = await openPage();
  const feed = feedStream(page, events.progress(progress()));
  page.server.script('POST', '/api/slices', steps.answer(202, accepted()));
  await page.enter();
  let card = page.card();
  assert.equal(card.pct, '42%');
  assert.equal(card.fraction, 0.42);
  assert.equal(card.stage, 'Generating infill');
  assert.equal(card.elapsed, '0:31');
  assert.equal(card.elapsedWord, T.ELAPSED);
  assert.equal(card.left, T.ABOUT_LEFT('0:43'));
  assert.equal(card.stages.length, 13);
  assert.deepEqual(card.stages.slice(6, 9).map((s) => [s.label, s.state]), [['Generating walls', 'done'], ['Generating infill', 'now'], ['Checking and generating supports', '']]);
  assert.equal(card.line, T.SLICING_GOES_ON);
  await page.clock.advance(10 * S);
  card = page.card();
  assert.equal(card.elapsed, '0:41');
  assert.equal(card.left, T.ABOUT_LEFT('0:33'));
  feed.send(events.progress(progress({ stage: 'exporting', stage_label: 'Writing the sliced file', fraction: 0.97, elapsed_s: 74.5, sequence: 30 })));
  await page.clock.advance(0);
  assert.equal(page.card().left, T.FINISHING);
  feed.send(events.progress(progress({ stage: 'exporting', stage_label: 'Writing the sliced file', fraction: 0.98, elapsed_s: 98, sequence: 31 })));
  await page.clock.advance(0);
  assert.equal(page.card().left, T.LONGER_THAN('1:15'));
  assert.equal(page.card().late, true);
  assert.equal(page.card().stalled, true);
});

test('waiting behind others: the ring empty, how many are ahead as it falls, the time waited counting up and no time left', async () => {
  const page = await openPage();
  const feed = feedStream(page);
  await page.enter();
  assert.equal(page.card().stage, T.WAITING_AHEAD(2));
  assert.equal(page.card().fraction, 0);
  assert.equal(page.card().pct, '');
  assert.equal(page.card().left, '');
  assert.equal(page.card().stages[0].state, 'now');
  await page.clock.advance(12 * S);
  assert.equal(page.card().elapsed, '0:12');
  assert.equal(page.card().elapsedWord, T.WAITED);
  feed.send(events.progress(progress({ state: 'queued', stage: 'queued', stage_label: 'Waiting for the slicer', ahead: 1, elapsed_s: 0, sequence: 2, fraction: undefined })));
  await page.clock.advance(0);
  assert.equal(page.card().stage, T.WAITING_AHEAD(1));
  assert.equal(page.card().elapsed, '0:12');
});

test('a stage the page does not know is shown by its words alone, after the last known stage, and the list is not redrawn', async () => {
  const page = await openPage();
  feedStream(page, events.progress(progress()), events.progress(progress({ stage: 'polishing', stage_label: 'Polishing the toolpath', sequence: 18 })));
  await page.enter();
  const card = page.card();
  assert.equal(card.stage, 'Polishing the toolpath');
  assert.equal(card.stages.length, 13);
  assert.deepEqual(card.stages.filter((s) => s.state === 'done').length, 8);
  assert.equal(card.stages.some((s) => s.state === 'now'), false);
});

test('the front server cannot be reached: the figures stop and the time-left line says there is no news; the first report after says Reconnected', async () => {
  const page = await openPage();
  const first = feedStream(page, events.progress(progress()));
  page.server.script('GET', EVENTS, steps.hold());
  await page.enter();
  await page.clock.advance(10 * S);                      // 0:41 on the card
  await page.clock.advance(STREAM_SILENT_S * S);         // silent: counted as failed
  let card = page.card();
  assert.equal(first.aborted, true);
  assert.equal(card.stalled, true);
  assert.equal(card.left, T.NO_NEWS_SINCE('0:31'));           // the last report's moment
  assert.equal(card.elapsed, '1:26');                          // the time taken goes on counting
  assert.equal(card.stage, T.LAST_HEARD('Generating infill'));
  assert.equal(card.pct, '42%');
  const held = page.server.made('GET', EVENTS)[1];
  held.held.release(steps.stream([events.version(), events.progress(progress({ fraction: 0.6, elapsed_s: 90, sequence: 25 }))]));
  await page.clock.advance(0);
  card = page.card();
  assert.equal(card.stalled, false);
  assert.equal(card.pct, '60%');
  assert.equal(card.conn.kind, 'back');
  assert.equal(card.conn.text, T.RECONNECTED('1:30'));
  await page.clock.advance(RECONNECTED_LINE_S * S - 100);
  assert.equal(page.card().conn?.kind, 'back');
  await page.clock.advance(100);
  assert.equal(page.card().conn, null);
});

test('another request failing for 20 s also stops the card\'s figures', async () => {
  const page = await openPage();
  feedStream(page, events.progress(progress()));
  await page.enter();
  page.server.script('GET', '/api/configuration', ...Array.from({ length: 10 }, () => steps.drop()));
  page.api.get('/api/configuration');
  await page.clock.advance(19 * S);
  assert.equal(page.card().stalled, false);
  await page.clock.advance(1 * S);
  assert.equal(page.card().stalled, true);
  assert.match(page.card().left, /^no news since /);
});

test('the slice service asked to stop ends a waiting slice: the page submits again by itself with a new value, the card starts again with its line', async () => {
  const page = await openPage();
  const feed = feedStream(page, events.progress(progress()));
  await page.enter();
  const again = feedStream(page);
  feed.send(events.progress(progress({ state: 'cancelled', cancel_reason: 'shutdown', sequence: 18 })));
  await page.clock.advance(0);
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.notEqual(sent[1].submission_id, sent[0].submission_id);
  assert.equal(page.card().conn.text, T.SLICER_RESTARTED);
  assert.equal(page.card().stages[0].state, 'now');
  assert.equal(again.reading, true);
});

test('a slice replaced by the same plate\'s later one shows nothing', async () => {
  const page = await openPage();
  const feed = feedStream(page, events.progress(progress()));
  await page.enter();
  feed.send(events.progress(progress({ state: 'cancelled', cancel_reason: 'replaced', sequence: 18 })));
  await page.clock.advance(0);
  assert.equal(page.submissions().length, 1);
  assert.equal(page.view().kind, 'card');
});

test('a slice job the front server no longer knows, submitted less than two hours ago: the slice service restarted, so the plate is submitted again with its line', async () => {
  const page = await openPage();
  const feed = feedStream(page, events.progress(progress()));
  await page.enter();
  for (let t = 15; t < SLICED_FILE_KEEP_S; t += 15) { await page.clock.advance(15 * S); feed.send(events.keepAlive()); }
  await page.clock.advance(14_900);                      // 7,199.9 s after it was submitted
  page.server.script('GET', EVENTS, steps.report(errorReport('front.slice_unknown')));
  feedStream(page);
  feed.end();
  await page.clock.advance(0);
  assert.equal(page.submissions().length, 2);
  assert.notEqual(page.submissions()[1].submission_id, page.submissions()[0].submission_id);
  assert.equal(page.card().conn.text, T.SLICER_RESTARTED);
});

test('a slice job unknown two hours or more after it was submitted is not a restart: the plate is submitted again with no line', async () => {
  const page = await openPage();
  const feed = feedStream(page, events.progress(progress()));
  await page.enter();
  for (let t = 0; t < SLICED_FILE_KEEP_S; t += 15) { await page.clock.advance(15 * S); feed.send(events.keepAlive()); }
  page.server.script('GET', EVENTS, steps.report(errorReport('front.slice_unknown')));     // at 7,200 s exactly
  feedStream(page);
  feed.end();
  await page.clock.advance(0);
  assert.equal(page.submissions().length, 2);
  assert.equal(page.card().conn, null);
});

test('done: the step shows its placeholder, the plate is sliced, and a change to the plate makes it unsliced', async () => {
  const page = await openPage();
  feedStream(page, events.progress(progress()), events.progress(doneReport()));
  await page.enter();
  assert.equal(page.view().kind, 'done');
  assert.equal(page.view().text, T.SLICED_PLACEHOLDER);
  assert.equal(page.store.get().sliced, true);
  await page.leave();
  const plate = page.storage.plate();
  await page.storage.update({ instances: plate.instances.map((i, n) => (n === 0 ? { ...i, angle: 10 } : i)) });
  page.slicing.plateChanged();
  assert.equal(page.store.get().sliced, false);
  await page.storage.update({ instances: plate.instances });
  page.slicing.plateChanged();
  assert.equal(page.store.get().sliced, true);
  await page.enter();
  assert.equal(page.submissions().length, 1);
  assert.equal(page.view().kind, 'done');
});

test('a page opened on a plate whose stored slice is the plate as it stands follows that slice and submits nothing', async () => {
  const page = await openPage();
  feedStream(page, events.progress(progress()));
  await page.enter();
  const kept = page.storage.plate().slice;
  // a second page on the same stored plate: the stored slice is followed
  const store = createStore();
  store.set({ ...page.store.get(), step: 'layout', sliced: false });
  const slicing = createSlicing({ api: page.api, clock: page.clock, storage: page.storage, store, settings: {}, layout: page.layout, panel: { goTo() {} }, report() {}, newId: () => 'other', random: () => 0.5 });
  feedStream(page, events.progress(progress({ sequence: 20 })));
  store.set({ step: 'preview' });
  await page.clock.advance(0);
  assert.equal(page.submissions().length, 1);
  assert.equal(slicing.model().kind, 'card');
  assert.equal(page.server.made('GET', EVENTS).at(-1).path, `/api/slices/${kept.id}/events`);
});

// ---- when a slice fails

const ROWS = [
  [['slice.placement_off_plate', 'slice.placement_too_tall', 'slice.placement_too_close', 'slice.crosses_edge', 'slice.nothing_on_plate', 'slice.left_off_plate', 'slice.too_many_instances', 'slice.too_many_parts', 'slice.part_too_large', 'slice.bad_plate_configuration'], ['layout']],
  [['slice.empty_layers'], ['supports', 'layout']],
  [['slice.empty_layers_with_supports'], ['parts']],
  [['slice.unknown_printer', 'slice.profiles_not_offered', 'slice.bad_overrides', 'slice.profile_unreadable'], ['settings']],
  [['slice.orca_too_close'], ['layout']],
  [['slice.rests_on_an_edge'], ['layout']],
  [['slice.no_layers', 'slice.print_empty'], ['parts']],
  [['slice.timeout'], ['again', 'parts']],
  [['slice.output_too_large', 'front.sliced_file_too_large', 'slice.out_of_memory'], ['parts']],
  [['slice.orca_failed'], ['again', 'layout']],
  [['slice.orca_crashed', 'slice.orca_killed', 'slice.orca_missing', 'slice.orca_unstartable', 'slice.no_output', 'slice.unreadable_output', 'slice.no_gcode', 'slice.output_unwritable', 'slice.scratch_unwritable', 'slice.unexpected', 'slice.some_new_failure', 'front.something_new'], ['again', 'layout']],
];
const LABELS = { supports: T.SUPPORTS_AND_SLICE, again: T.SLICE_AGAIN, layout: T.BACK_TO.layout, parts: T.BACK_TO.parts, settings: T.BACK_TO.settings };

test('every code of the table has exactly its buttons, an unknown code those of the last row', () => {
  for (const [codes, ids] of ROWS) {
    for (const code of codes) assert.deepEqual(failureButtons(errorReport(code)).map((b) => b.id), ids, code);
  }
  assert.deepEqual(failureButtons(errorReport('slice.empty_layers')).map((b) => b.label), [T.SUPPORTS_AND_SLICE, T.BACK_TO.layout]);
});

test('a report\'s action enable_supports gives its button on any code; choose_orientation and the others give none of their own', () => {
  assert.deepEqual(failureButtons(errorReport('slice.orca_failed', { action: 'enable_supports' })).map((b) => b.id), ['supports', 'again', 'layout']);
  assert.deepEqual(failureButtons(errorReport('slice.rests_on_an_edge', { action: 'choose_orientation' })).map((b) => b.id), ['layout']);
  assert.deepEqual(failureButtons(errorReport('slice.placement_too_close', { action: 'arrange' })).map((b) => b.id), ['layout']);
  assert.deepEqual(failureButtons(errorReport('slice.timeout', { action: 'lower_quantities' })).map((b) => b.id), ['again', 'parts']);
  assert.deepEqual(failureButtons(errorReport('slice.orca_failed', { action: 'slice_again' })).map((b) => b.id), ['again', 'layout']);
  assert.deepEqual(failureButtons(errorReport('slice.orca_failed', { action: 'a_new_action' })).map((b) => b.id), ['again', 'layout']);
});

for (const [codes, ids] of ROWS) {
  for (const code of codes) {
    test(`a slice that fails with ${code} shows the report's sentences as they are, as text, with ${ids.join(', ')}`, async () => {
      const page = await openPage();
      const error = errorReport(code, { message: `<b>${code}</b> happened & failed.`, orca_sentence: 'Object can\'t be printed for empty layer between 9.9 and 11.34.' });
      feedStream(page, events.progress(progress()), events.progress(failedReport(error)));
      await page.enter();
      const view = page.view();
      assert.equal(view.kind, 'failed');
      assert.equal(view.what, error.message);
      assert.equal(view.todo, error.remedy);
      assert.deepEqual(view.actions.map((a) => a.id), ids);
      assert.deepEqual(view.actions.map((a) => a.label), ids.map((id) => LABELS[id]));
      // what the step draws: never the report's detail
      const drawn = JSON.stringify([view.what, view.todo, view.details, view.actions.map((a) => a.label)]);
      assert.ok(!drawn.includes(error.detail));
      const gap = code === 'slice.empty_layers' || code === 'slice.empty_layers_with_supports';
      assert.equal(view.details, gap ? T.ORCA_SAYS(error.orca_sentence) : null);
      assert.equal(page.store.get().sliced, false);
    });
  }
}

test('slice.rests_on_an_edge, as the slice service answers it: Back to Layout and no Slice again', async () => {
  const page = await openPage();
  const error = example('error-report-rests-on-an-edge.json');
  feedStream(page, events.progress(failedReport(error)));
  await page.enter();
  const view = page.view();
  assert.equal(view.what, error.message);
  assert.equal(view.todo, error.remedy);
  assert.deepEqual(view.actions.map((a) => a.id), ['layout']);
  assert.equal(view.details, null);
});

test('the empty-layers failure with no sentence of Orca\'s has no Details', async () => {
  const page = await openPage();
  feedStream(page, events.progress(failedReport(errorReport('slice.empty_layers', { action: 'enable_supports' }))));
  await page.enter();
  assert.equal(page.view().details, null);
});

test('the empty-layers failure as the contract\'s example has it: Orca\'s sentence under Details', async () => {
  const page = await openPage();
  const error = example('error-report-orca-sentence.json');
  feedStream(page, events.progress(failedReport(error)));
  await page.enter();
  assert.equal(page.view().details, 'Orca Slicer: Object can\'t be printed for empty layer between 9.9 and 11.34.');
});

test('a plate refused when submitted shows the refusal: Back to Layout for a placement', async () => {
  const page = await openPage();
  const refusal = errorReport('slice.placement_too_close', { action: 'arrange' });
  page.server.script('POST', '/api/slices', steps.report(refusal, { status: 422 }));
  await page.enter();
  assert.equal(page.view().kind, 'failed');
  assert.equal(page.view().what, refusal.message);
  assert.deepEqual(page.view().actions.map((a) => a.id), ['layout']);
  assert.equal(page.server.made('GET', EVENTS).length, 0);
});

test('Back to Layout, Back to Parts and Back to Settings go to their steps', async () => {
  for (const [code, step] of [['slice.placement_off_plate', 'layout'], ['slice.no_layers', 'parts'], ['slice.bad_overrides', 'settings']]) {
    const page = await openPage();
    page.server.script('POST', '/api/slices', steps.report(errorReport(code), { status: 422 }));
    await page.enter();
    page.view().actions.at(-1).run();
    assert.equal(page.store.get().step, step);
  }
});

test('Slice again after a failure submits with a new value', async () => {
  const page = await openPage();
  feedStream(page, events.progress(failedReport(errorReport('slice.timeout', { retryable: true }))));
  await page.enter();
  feedStream(page);
  await page.view().actions[0].run();
  await page.clock.advance(0);
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.notEqual(sent[0].submission_id, sent[1].submission_id);
  assert.equal(page.view().kind, 'card');
});

test('coming back to a failed plate unchanged shows the failure again and submits nothing', async () => {
  const page = await openPage();
  feedStream(page, events.progress(failedReport(errorReport('slice.out_of_memory'))));
  await page.enter();
  await page.leave('parts');
  await page.enter();
  assert.equal(page.submissions().length, 1);
  assert.equal(page.view().kind, 'failed');
});

test('Turn on Supports and slice again on a plate laid out 5 mm apart goes to the Layout step with its line and submits nothing', async () => {
  const page = await openPage();
  feedStream(page, events.progress(failedReport(errorReport('slice.empty_layers', { action: 'enable_supports' }))));
  await page.enter();
  page.layout.problem = 'Bracket #1 and Bracket #2 are 5 mm apart.';
  await page.view().actions[0].run();
  assert.equal(page.store.get().step, 'layout');
  assert.deepEqual(page.layout.notes, [T.NOT_SLICED_SUPPORTS(12)]);
  assert.equal(page.submissions().length, 1);
  assert.equal(page.storage.plate().settings.changes.enable_support, '1');
});

test('Turn on Supports and slice again on a plate 12 mm apart submits with enable_support "1"', async () => {
  const page = await openPage();
  feedStream(page, events.progress(failedReport(errorReport('slice.empty_layers', { action: 'enable_supports' }))));
  await page.enter();
  feedStream(page);
  await page.view().actions[0].run();
  await page.clock.advance(0);
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.equal(sent[1].overrides.enable_support, '1');
  assert.equal(sent[1].overrides.support_type, 'tree(auto)');
  assert.notEqual(sent[1].submission_id, sent[0].submission_id);
  assert.equal(page.store.get().step, 'preview');
});

test('a fifth stream refused: the slice is followed by asking, and nothing of the refusal shows', async () => {
  const page = await openPage();
  page.server.script('GET', EVENTS, steps.report(errorReport('front.too_many_streams'), { status: 429 }));
  page.server.script('GET', `/api/slices/${JOB}`, steps.answer(200, { progress: progress() }), steps.answer(200, { progress: doneReport() }));
  await page.enter();
  assert.equal(page.card().pct, '42%');
  await page.clock.advance(2 * S);
  assert.equal(page.view().kind, 'done');
  assert.equal(page.api.board.state().kind, 'none');
});
