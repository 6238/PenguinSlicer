// The page's reports about its own failures (src/reports.js; wizard/README-details.md, "What the
// wizard reports about itself"): each sent once with exactly the contract's fields, held to
// REPORTS_PER_MIN on the fake clock, and dropped, never retried, when it cannot be sent or is
// refused.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../src/api.js';
import { REPORTS_PER_MIN, createReports, watchUncaught } from '../src/reports.js';
import { FakeClock } from './fakes/clock.js';
import { FakeFrontServer, errorReport, example, steps } from './fakes/front_server.js';

const ENVIRONMENT = { browser: 'Chrome', browser_version: '131.0', software_3d: () => true };

function setUp({ step = () => 'parts', environment = ENVIRONMENT } = {}) {
  const clock = new FakeClock();
  const server = new FakeFrontServer();
  const api = createApi({ transport: server.transport, clock, version: 'v', currentGroup: () => 'g-1', random: () => 0.5 });
  const reports = createReports({ api, clock, page: 'c1e0aa', step, environment });
  return { clock, server, reports };
}

const sent = (server) => server.made('POST', '/api/reports/failure').map((r) => JSON.parse(r.body));

test('the figure is the details file\'s proposal: a few a minute', () => {
  assert.equal(REPORTS_PER_MIN, 4);
});

test('a failure report carries exactly the contract\'s fields, the page\'s mark and its group', async () => {
  const { server, reports } = setUp();
  await reports.failure('part_not_drawable', { part_sha256: '9f2c', detail: 'RangeError at mesh.js:212' });
  const [body] = sent(server);
  assert.deepEqual(body, {
    page: 'c1e0aa', what: 'part_not_drawable', step: 'parts', browser: 'Chrome', browser_version: '131.0',
    software_3d: true, part_sha256: '9f2c', detail: 'RangeError at mesh.js:212',
  });
  assert.deepEqual(Object.keys(body).sort(), Object.keys(example('wizard-front/report-failure-request.json')).sort());
  const [request] = server.made('POST', '/api/reports/failure');
  assert.equal(request.headers['x-penguinslicer-wizard'], '1');
  assert.equal(request.headers['x-penguinslicer-group'], 'g-1');
});

test('a report without a part or a detail leaves those fields out', async () => {
  const { server, reports } = setUp({ step: () => 'none' });
  await reports.failure('storage_cleared');
  assert.deepEqual(sent(server), [{ page: 'c1e0aa', what: 'storage_cleared', step: 'none', browser: 'Chrome', browser_version: '131.0', software_3d: true }]);
});

test('the detail is cut to 1,000 characters and the browser\'s words to 40', async () => {
  const { server, reports } = setUp({ environment: { browser: 'B'.repeat(50), browser_version: '9'.repeat(45), software_3d: () => false } });
  await reports.failure('page_failed', { detail: 'x'.repeat(1500) });
  const [body] = sent(server);
  assert.equal(body.detail.length, 1000);
  assert.equal(body.browser.length, 40);
  assert.equal(body.browser_version.length, 40);
  assert.equal(body.software_3d, false);
});

test('a what the contract does not list is a fault of the page and is not sent', async () => {
  const { server, reports } = setUp();
  await assert.rejects(() => reports.failure('something_else'), /not a failure the contract lists/);
  assert.deepEqual(sent(server), []);
});

test('at REPORTS_PER_MIN reports in a minute, the next in that minute is dropped, and one a minute later is sent', async () => {
  const { clock, server, reports } = setUp();
  for (let i = 0; i < REPORTS_PER_MIN; i += 1) assert.equal(await reports.failure('page_failed', { detail: `${i}` }), true);
  await clock.advance(59_999);
  assert.equal(await reports.failure('page_failed', { detail: 'dropped' }), false);
  assert.equal(sent(server).length, REPORTS_PER_MIN);
  await clock.advance(1);
  assert.equal(await reports.failure('page_failed', { detail: 'sent' }), true);
  assert.deepEqual(sent(server).map((b) => b.detail), ['0', '1', '2', '3', 'sent']);
});

test('a report refused with front.too_many_reports is dropped and not sent again', async () => {
  const { clock, server, reports } = setUp();
  server.script('POST', '/api/reports/failure', steps.report(errorReport('front.too_many_reports')));
  assert.equal(await reports.failure('storage_refused'), false);
  await clock.advance(600_000);
  assert.equal(sent(server).length, 1);
});

test('a report that cannot be sent is dropped and never retried', async () => {
  const { clock, server, reports } = setUp();
  server.script('POST', '/api/reports/failure', steps.drop());
  assert.equal(await reports.failure('storage_refused'), false);
  await clock.advance(600_000);
  assert.equal(sent(server).length, 1);
  assert.equal(clock.pending, 0);
});

test('a page that is not signed in drops its reports, sending nothing', async () => {
  let signedIn = false;
  const clock = new FakeClock();
  const server = new FakeFrontServer();
  const api = createApi({ transport: server.transport, clock, version: 'v', random: () => 0.5 });
  const reports = createReports({ api, clock, page: 'p', step: () => 'none', environment: MACHINE, signedIn: () => signedIn });
  assert.equal(await reports.failure('page_failed', { detail: 'before /api/me' }), false);
  assert.equal(await reports.drawing(LAYOUT_SUMMARY), false);
  assert.equal(server.requests.length, 0);
  signedIn = true;
  assert.equal(await reports.failure('page_failed'), true);
});

// ---- the drawing summaries, POST /api/reports/drawing

const MACHINE = {
  ...ENVIRONMENT, os: 'macOS', graphics_card: () => 'Apple M2', processors: 8, memory_gb: 8,
  pixel_ratio: () => 2, panel_width_px: () => 360, in_onshape: false,
};
const LAYOUT_SUMMARY = { view: 'layout', fps_typical: 18.5, fps_worst: 9.4, longest_hold_ms: 212.6, instances: 150 };
const PREVIEW_SUMMARY = {
  view: 'preview', fps_typical: 58.5, fps_worst: 31, first_layer_ms: 412, longest_hold_ms: 96,
  instances: 4, sliced_file_bytes: 1843207, sliced_file_lines: 120345,
};
const drawn = (server) => server.made('POST', '/api/reports/drawing').map((r) => JSON.parse(r.body));

test('a drawing summary of the Preview step carries exactly the contract\'s fields, the machine\'s from the browser', async () => {
  const { server, reports } = setUp({ environment: { ...MACHINE, software_3d: () => false } });
  assert.equal(await reports.drawing(PREVIEW_SUMMARY), true);
  const [body] = drawn(server);
  const want = { ...example('wizard-front/report-drawing-request.json'), page: 'c1e0aa' };
  assert.deepEqual(body, want);
  assert.deepEqual(Object.keys(body), Object.keys(want), 'in the contract\'s order');
  assert.equal(server.made('POST', '/api/reports/drawing')[0].headers['x-penguinslicer-wizard'], '1');
});

test('a drawing summary of the Layout view leaves out the Preview step\'s fields, says software drawing, and rounds the hold', async () => {
  const { server, reports } = setUp({ environment: { ...MACHINE, graphics_card: () => null, processors: undefined, memory_gb: undefined } });
  await reports.drawing({ ...LAYOUT_SUMMARY, first_layer_ms: 5, sliced_file_bytes: 1 });
  assert.deepEqual(drawn(server), [{
    page: 'c1e0aa', view: 'layout', fps_typical: 18.5, fps_worst: 9.4, longest_hold_ms: 213, instances: 150,
    browser: 'Chrome', browser_version: '131.0', os: 'macOS', drawing: 'software', panel_width_px: 360, pixel_ratio: 2, in_onshape: false,
  }]);
});

test('a drawing summary holds no part name, whatever its caller gives it', async () => {
  const { server, reports } = setUp({ environment: MACHINE });
  await reports.drawing({ ...LAYOUT_SUMMARY, name: 'Elevator Block Top', parts: ['Elevator Block Top'] });
  const text = server.made('POST', '/api/reports/drawing')[0].body;
  assert.equal(text.includes('Elevator'), false);
});

test('a summary of a use with no frame drawn while moving, or no first layer, is not sent: the contract has no figure for it', async () => {
  const { server, reports } = setUp();
  assert.equal(await reports.drawing({ ...LAYOUT_SUMMARY, fps_typical: null, fps_worst: null }), false);
  assert.equal(await reports.drawing({ ...PREVIEW_SUMMARY, first_layer_ms: null }), false);
  assert.equal(await reports.drawing({ ...LAYOUT_SUMMARY, longest_hold_ms: Number.NaN }), false);
  assert.deepEqual(drawn(server), []);
});

test('the machine\'s strings are cut to the contract\'s lengths', async () => {
  const { server, reports } = setUp({ environment: { ...MACHINE, os: 'o'.repeat(60), graphics_card: () => 'g'.repeat(200) } });
  await reports.drawing(LAYOUT_SUMMARY);
  const [body] = drawn(server);
  assert.equal(body.os.length, 40);
  assert.equal(body.graphics_card.length, 120);
});

test('drawing summaries and failures share the one limit of REPORTS_PER_MIN', async () => {
  const { server, reports } = setUp({ environment: MACHINE });
  for (let i = 0; i < REPORTS_PER_MIN - 1; i += 1) await reports.failure('page_failed');
  assert.equal(await reports.drawing(LAYOUT_SUMMARY), true);
  assert.equal(await reports.drawing(LAYOUT_SUMMARY), false);
  assert.equal(await reports.failure('page_failed'), false);
  assert.equal(drawn(server).length, 1);
});

test('a drawing summary that cannot be sent is dropped and never retried', async () => {
  const { clock, server, reports } = setUp({ environment: MACHINE });
  server.script('POST', '/api/reports/drawing', steps.drop());
  assert.equal(await reports.drawing(LAYOUT_SUMMARY), false);
  await clock.advance(600_000);
  assert.equal(server.made('POST', '/api/reports/drawing').length, 1);
});

// ---- the handler for every uncaught error and rejected promise

function fakeWindow() {
  const listeners = new Map();
  return {
    addEventListener: (type, fn) => listeners.set(type, fn),
    fire: (type, event) => listeners.get(type)(event),
    has: (type) => listeners.has(type),
  };
}

test('an uncaught error is reported as page_failed with its message and where it arose', async () => {
  const { server, reports } = setUp({ step: () => 'layout' });
  const target = fakeWindow();
  watchUncaught(target, reports);
  const error = new TypeError('instance.lay is undefined');
  target.fire('error', { message: 'Uncaught TypeError: instance.lay is undefined', filename: 'http://localhost/assets/layout.0123456789ab.js', lineno: 212, colno: 9, error });
  await new Promise((r) => setImmediate(r));
  const [body] = sent(server);
  assert.equal(body.what, 'page_failed');
  assert.equal(body.step, 'layout');
  assert.match(body.detail, /^uncaught: TypeError: instance\.lay is undefined at \/assets\/layout\.0123456789ab\.js:212:9/);
});

test('a rejected promise no one handled is reported as page_failed with its reason', async () => {
  const { server, reports } = setUp();
  const target = fakeWindow();
  watchUncaught(target, reports);
  target.fire('unhandledrejection', { reason: new RangeError('Invalid array length') });
  target.fire('unhandledrejection', { reason: 'a plain string' });
  await new Promise((r) => setImmediate(r));
  assert.deepEqual(sent(server).map((b) => b.detail.split('\n')[0]), ['unhandled rejection: RangeError: Invalid array length', 'unhandled rejection: a plain string']);
});

test('a storm of uncaught errors sends at most REPORTS_PER_MIN reports a minute, and none about a report that failed', async () => {
  const { server, reports } = setUp();
  const target = fakeWindow();
  watchUncaught(target, reports);
  server.script('POST', '/api/reports/failure', steps.drop());
  for (let i = 0; i < 20; i += 1) target.fire('error', { message: `boom ${i}`, error: new Error(`boom ${i}`) });
  await new Promise((r) => setImmediate(r));
  assert.equal(sent(server).length, REPORTS_PER_MIN);
});
