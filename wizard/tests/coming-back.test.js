// Coming back (src/slicing.js, comeBack; wizard/README-details.md, "When a user comes back"): a
// page that lost what it had in memory reads its plate from the browser's storage, asks
// GET /api/slices/<slice> about the plate's slice job, and opens where the user will want to be.
// Each row of the table that phase 2 can meet is reached on purpose from the fake front server, on
// the fake clock: a first page submits the plate, then a second page opens on the same stored plate,
// as a refresh does.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { SLICED_FILE_KEEP_S } from '../src/page-constants.js';
import { createSlicing } from '../src/slicing.js';
import * as T from '../src/slicing-sentences.js';
import { createStore } from '../src/state.js';
import { settle } from './fakes/clock.js';
import { errorReport, events, steps } from './fakes/front_server.js';
import { EVENTS, JOB, S, accepted, doneReport, failedReport, feedStream, openPage, progress } from './fakes/preview-page.js';

const ASK = `/api/slices/${JOB}`;

// A plate submitted and accepted by a first page, its slice kept in the stored plate.
async function sliced({ step = 'layout' } = {}) {
  const page = await openPage();
  page.server.script('POST', '/api/slices', steps.answer(202, accepted()));
  feedStream(page);
  await page.enter();
  await page.leave(step);
  return page;
}

// A second page on the same stored plate, opened on `step` (the stored step), coming back.
async function comeBack(page, { step = 'layout', quiet = false, answer = null, ids = 'again' } = {}) {
  if (answer) page.server.script('GET', ASK, answer);
  // the store begins on the Parts step and the opening sets the stored step, as opening.js does
  const store = createStore();
  const notices = [];
  const panel = {
    goTo: (s) => store.set({ step: s }),
    notify: (n) => notices.push(n),
    dropNotice: () => {},
  };
  let n = 0;
  const slicing = createSlicing({
    api: page.api, clock: page.clock, storage: page.storage, store, settings: {}, layout: page.layout, panel,
    report() {}, newId: () => `${ids}-${(n += 1)}`, random: () => 0.5, back: () => Promise.resolve({ quiet }),
  });
  const asked = page.server.made('GET', ASK).length;
  store.set({ ...page.store.get(), step, sliced: false, expired: false });
  await page.clock.advance(0);
  return { store, slicing, notices, view: () => slicing.model(), asked: () => page.server.made('GET', ASK).length - asked };
}

const progressAnswer = (report) => steps.answer(200, { progress: report });
const submitted = (page) => page.submissions().length;

test('a slice still running: the Preview step with its progress, said in a notification, followed by its stream', async () => {
  const page = await sliced();
  feedStream(page, events.progress(progress({ sequence: 30 })));
  const before = page.server.made('GET', EVENTS).length;
  const back = await comeBack(page, { answer: progressAnswer(progress({ sequence: 25 })) });
  assert.equal(back.asked(), 1, 'it asks about the slice job');
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().kind, 'card');
  assert.deepEqual(back.notices.map((x) => x.what), [T.BACK_SLICING]);
  assert.equal(back.notices[0].kind, 'info');
  assert.equal(page.server.made('GET', EVENTS).length, before + 1, 'and follows it');
  assert.equal(submitted(page), 1, 'nothing is submitted again');
});

test('a slice waiting behind others: the Preview step with its place, said in a notification', async () => {
  const page = await sliced();
  feedStream(page);
  const back = await comeBack(page, { answer: progressAnswer(progress({ state: 'queued', stage: 'queued', ahead: 3, sequence: 3 })) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().card.stage, T.WAITING_AHEAD(3));
  assert.deepEqual(back.notices.map((x) => x.what), [T.BACK_SLICING]);
});

test('a slice finished: the Preview step with the result, said in a notification, and Next to Send', async () => {
  const page = await sliced({ step: 'parts' });
  const back = await comeBack(page, { step: 'parts', answer: progressAnswer(doneReport()) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().kind, 'done');
  assert.equal(back.view().details.file, doneReport().sliced_file.file);
  assert.equal(back.store.get().sliced, true);
  assert.deepEqual(back.notices.map((x) => x.what), [T.BACK_SLICED]);
  assert.equal(submitted(page), 1);
});

test('a page that comes back on the Send step to a finished slice opens the Preview step, as the table says', async () => {
  const page = await sliced({ step: 'send' });
  const back = await comeBack(page, { step: 'send', answer: progressAnswer(doneReport()) });
  assert.equal(back.store.get().step, 'preview');
  assert.deepEqual(back.notices.map((x) => x.what), [T.BACK_SLICED]);
});

test('a slice that failed: the Preview step with the failure, as if the page had stayed open, nothing said and nothing submitted', async () => {
  const page = await sliced();
  const error = errorReport('slice.timeout');
  const back = await comeBack(page, { answer: progressAnswer(failedReport(error)) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().kind, 'failed');
  assert.equal(back.view().what, error.message);
  assert.deepEqual(back.notices, []);
  assert.equal(submitted(page), 1, 'entering the step on coming back does not submit the failed plate again');
});

test('an expired sliced file, the page on an earlier step: the step as it was, nothing said; entering the Preview step slices', async () => {
  const page = await sliced();
  const plate = page.storage.plate();
  const back = await comeBack(page, { answer: progressAnswer(failedReport(errorReport('front.sliced_file_expired'), 42)) });
  assert.equal(back.store.get().step, 'layout');
  assert.deepEqual(back.notices, []);
  assert.equal(submitted(page), 1);
  assert.deepEqual(page.storage.plate().parts, plate.parts);
  assert.deepEqual(page.storage.plate().instances, plate.instances);
  page.server.script('POST', '/api/slices', steps.answer(202, accepted()));
  feedStream(page);
  back.store.set({ step: 'preview' });
  await page.clock.advance(0);
  assert.equal(submitted(page), 2);
  assert.equal(back.view().kind, 'card');
});

for (const step of ['preview', 'send']) {
  test(`an expired sliced file, the page on the ${step === 'preview' ? 'Preview' : 'Send'} step: the expired message with Slice again, and nothing sliced by itself`, async () => {
    const page = await sliced({ step });
    const plate = page.storage.plate();
    const expired = errorReport('front.sliced_file_expired');
    const back = await comeBack(page, { step, answer: progressAnswer(failedReport(expired, 42)) });
    assert.equal(back.store.get().step, step);
    assert.equal(back.view().kind, 'expired');
    assert.equal(back.view().what, expired.message);
    assert.deepEqual(back.view().actions.map((a) => a.label), [T.SLICE_AGAIN]);
    assert.equal(back.store.get().expired, true);
    assert.equal(submitted(page), 1);
    assert.deepEqual(page.storage.plate().parts, plate.parts);
    assert.deepEqual(page.storage.plate().instances, plate.instances);
    assert.deepEqual(page.storage.plate().settings, plate.settings);
    assert.deepEqual(back.notices, []);
  });
}

test('a slice job unknown and submitted less than two hours ago: the Preview step, and the plate submitted again with a new value, the card from the start', async () => {
  const page = await sliced();
  await page.clock.advance(SLICED_FILE_KEEP_S * S - 1);
  page.server.script('POST', '/api/slices', steps.answer(202, { slice: { ...accepted().slice, id: 'job-2' } }));
  feedStream(page);
  const back = await comeBack(page, { answer: steps.report(errorReport('front.slice_unknown')) });
  assert.equal(back.store.get().step, 'preview');
  const sent = page.submissions();
  assert.equal(sent.length, 2);
  assert.equal(sent[1].submission_id, 'again-1');
  assert.notEqual(sent[1].submission_id, sent[0].submission_id);
  assert.equal(back.view().kind, 'card');
  assert.equal(back.view().card.conn.text, T.SLICER_RESTARTED);
  assert.equal(page.storage.plate().slice.id, 'job-2');
  assert.deepEqual(back.notices, []);
});

test('a slice job unknown and submitted exactly two hours ago: expired, on the step as it was, and nothing submitted', async () => {
  const page = await sliced({ step: 'preview' });
  await page.clock.advance(SLICED_FILE_KEEP_S * S);
  const back = await comeBack(page, { step: 'preview', answer: steps.report(errorReport('front.slice_unknown')) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().kind, 'expired');
  assert.equal(back.view().what, T.EXPIRED_WHAT, 'the wizard\'s own sentence: the front server said only that it does not know the slice');
  assert.equal(submitted(page), 1);
});

test('a slice job ended because the slice service was asked to stop: the plate submitted again by itself', async () => {
  const page = await sliced();
  page.server.script('POST', '/api/slices', steps.answer(202, { slice: { ...accepted().slice, id: 'job-2' } }));
  feedStream(page);
  const back = await comeBack(page, { answer: progressAnswer(progress({ state: 'cancelled', cancel_reason: 'shutdown', sequence: 9 })) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(submitted(page), 2);
  assert.equal(back.view().card.conn.text, T.SLICER_RESTARTED);
});

test('a slice job replaced by a later one the stored plate does not name: the plate as it stands submitted again', async () => {
  const page = await sliced();
  page.server.script('POST', '/api/slices', steps.answer(202, { slice: { ...accepted().slice, id: 'job-3' } }));
  feedStream(page);
  const back = await comeBack(page, { answer: progressAnswer(progress({ state: 'cancelled', cancel_reason: 'replaced', sequence: 9 })) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(submitted(page), 2);
  assert.equal(page.storage.plate().slice.id, 'job-3');
  assert.equal(back.view().kind, 'card');
  assert.equal(back.view().card.conn, null, 'no slice service restarted');
});

test('a refusal of the asking other than an unknown slice: the Preview step with that error report', async () => {
  const page = await sliced();
  const refusal = errorReport('front.group_not_allowed');
  const back = await comeBack(page, { answer: steps.report(refusal) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().kind, 'failed');
  assert.equal(back.view().what, refusal.message);
});

test('an answer that is not a progress report: the Preview step with the wizard\'s own failure', async () => {
  const page = await sliced();
  const back = await comeBack(page, { answer: steps.answer(200, { progress: { state: 'running' } }) });
  assert.equal(back.view().kind, 'failed');
  assert.equal(back.view().report.code, 'wizard.bad_answer');
});

test('a progress report of another slice job: the wizard\'s own failure, never that job\'s result shown as this plate\'s', async () => {
  const page = await sliced();
  const back = await comeBack(page, { answer: progressAnswer({ ...doneReport(), job: 'another-job-0000' }) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().kind, 'failed');
  assert.equal(back.view().report.code, 'wizard.bad_answer');
  assert.equal(back.store.get().sliced, false);
  assert.deepEqual(back.notices, []);
});

test('a progress report without the contract\'s required job or elapsed_s: the wizard\'s own failure', async () => {
  for (const drop of ['job', 'elapsed_s']) {
    const page = await sliced();
    const report = { ...doneReport() };
    delete report[drop];
    const back = await comeBack(page, { answer: progressAnswer(report) });
    assert.equal(back.view().kind, 'failed', drop);
    assert.equal(back.view().report.code, 'wizard.bad_answer', drop);
  }
});

test('the page\'s own reload on the Send step with no slice of the plate as it stands opens the Preview step, which slices', async () => {
  const page = await openPage();
  feedStream(page);
  const back = await comeBack(page, { step: 'send', quiet: true });
  assert.equal(back.store.get().step, 'preview', 'the Send step has nothing to send');
  assert.equal(submitted(page), 1);
  assert.deepEqual(back.notices, []);
});

test('parts and no slice job: the stored step with the plate as it was, nothing asked and nothing said', async () => {
  const page = await openPage();
  for (const step of ['parts', 'settings', 'layout']) {
    const back = await comeBack(page, { step });
    assert.equal(back.store.get().step, step);
    assert.equal(back.asked(), 0);
    assert.deepEqual(back.notices, []);
    assert.equal(back.view().kind, 'idle');
  }
});

test('a plate changed since its stored slice counts as one with no slice job: nothing asked', async () => {
  const page = await sliced();
  const plate = page.storage.plate();
  await page.storage.update({ instances: plate.instances.map((i, n) => (n === 0 ? { ...i, x: 99 } : i)) });
  const back = await comeBack(page);
  assert.equal(back.store.get().step, 'layout');
  assert.equal(back.asked(), 0);
});

test('a page stored on the Send step with no slice of the plate as it stands opens the Preview step, which slices', async () => {
  const page = await openPage();
  feedStream(page);
  const back = await comeBack(page, { step: 'send' });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(submitted(page), 1);
});

test('the page\'s own reload says nothing and reopens on the stored step, with the slice followed as it was', async () => {
  const page = await sliced();
  feedStream(page, events.progress(progress({ sequence: 30 })));
  const back = await comeBack(page, { quiet: true, answer: progressAnswer(progress({ sequence: 25 })) });
  assert.equal(back.store.get().step, 'layout');
  assert.deepEqual(back.notices, []);
  assert.equal(back.view().kind, 'card');
  back.store.set({ step: 'preview' });
  await page.clock.advance(0);
  assert.equal(submitted(page), 1, 'entering the step follows the same slice');
});

test('the page\'s own reload on the Send step with a finished slice stays on the Send step, nothing said', async () => {
  const page = await sliced({ step: 'send' });
  const back = await comeBack(page, { step: 'send', quiet: true, answer: progressAnswer(doneReport()) });
  assert.equal(back.store.get().step, 'send');
  assert.equal(back.view().kind, 'done');
  assert.deepEqual(back.notices, []);
});

test('the page\'s own reload on the Preview step of a failed slice keeps the failure and submits nothing', async () => {
  const page = await sliced({ step: 'preview' });
  const back = await comeBack(page, { step: 'preview', quiet: true, answer: progressAnswer(failedReport(errorReport('slice.out_of_memory'))) });
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().kind, 'failed');
  assert.equal(submitted(page), 1);
});

test('an opening that throws leaves coming back with no rejected promise of its own: the opening\'s failure is reported once, by the opening', async () => {
  const page = await openPage();
  const unhandled = [];
  const listener = (reason) => unhandled.push(reason);
  process.on('unhandledRejection', listener);
  try {
    const failed = Promise.reject(new Error('the opening threw'));
    failed.catch(() => {});                       // the opening's own end (endOpening) handles it
    createSlicing({
      api: page.api, clock: page.clock, storage: page.storage, store: createStore(), settings: {}, layout: page.layout,
      panel: { goTo() {}, notify() {}, dropNotice() {} }, report() {}, newId: () => 'x', random: () => 0.5,
      back: () => failed, ready: () => failed,
    });
    await settle();
  } finally {
    process.off('unhandledRejection', listener);
  }
  assert.deepEqual(unhandled, []);
});

test('the asking is retried quietly like any request, and the page opens once it is answered', async () => {
  const page = await sliced();
  page.server.script('GET', ASK, steps.drop(), steps.drop());
  const back = await comeBack(page, { answer: progressAnswer(doneReport()) });
  assert.equal(back.store.get().step, 'layout', 'not yet answered');
  await page.clock.advance(5 * S);
  assert.equal(back.store.get().step, 'preview');
  assert.equal(back.view().kind, 'done');
});
