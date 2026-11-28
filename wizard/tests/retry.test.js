// Retrying, on the fake clock, with the fake front server dropping, holding or refusing answers
// (wizard/README-details.md, "Retrying"): quiet for 20 seconds, then the panel line in amber
// counting down to the next attempt, then after 300 seconds the line in red with Try again.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../src/api.js';
import { retryWaitS, isQuietRetry } from '../src/retry.js';
import { FakeClock } from './fakes/clock.js';
import { FakeFrontServer, errorReport, steps } from './fakes/front_server.js';

const S = 1000;

function setUp({ random = () => 0.5 } = {}) {
  const clock = new FakeClock();
  const server = new FakeFrontServer();
  const api = createApi({ transport: server.transport, clock, version: 'v-page', currentGroup: () => 'g', random });
  const lines = [];
  api.board.subscribe((state) => lines.push(state));
  return { clock, server, api, lines };
}

// The moments, in seconds since the clock started, at which `path` was asked for.
function moments(server, clock, method, path) {
  return server.made(method, path).map((r) => r.atS);
}

function recordMoments(server, clock) {
  const receive = server.receive.bind(server);
  server.receive = (request) => {
    const promise = receive(request);
    server.requests[server.requests.length - 1].atS = (clock.elapsed) / S;
    return promise;
  };
}

function dropAll(server, method, path, count) {
  server.script(method, path, ...Array.from({ length: count }, () => steps.drop()));
}

test('the waits double from 1 s to 30 s, each within its spread of a tenth', () => {
  assert.deepEqual([0, 1, 2, 3, 4, 5, 6, 7].map((i) => retryWaitS(i, () => 0.5)), [1, 2, 4, 8, 16, 30, 30, 30]);
  assert.deepEqual([0, 4, 5].map((i) => retryWaitS(i, () => 0)), [0.9, 14.4, 27]);
  assert.deepEqual([0, 4, 5].map((i) => retryWaitS(i, () => 1)), [1.1, 17.6, 33]);
});

test('a request that fails once and succeeds on the attempt at 1 s shows nothing', async () => {
  const { clock, server, api, lines } = setUp();
  recordMoments(server, clock);
  server.script('GET', '/api/me', steps.drop());
  const result = api.get('/api/me');
  await clock.advance(1 * S);
  assert.equal((await result).ok, true);
  assert.deepEqual(moments(server, clock, 'GET', '/api/me'), [0, 1]);
  assert.deepEqual(lines.filter((l) => l.kind !== 'none'), []);
});

test('attempts fall at 1, 3, 7, 15, 31, 61 … 271 s, and none after 300 s', async () => {
  const { clock, server, api } = setUp();
  recordMoments(server, clock);
  dropAll(server, 'GET', '/api/me', 100);
  api.get('/api/me');
  await clock.advance(600 * S);
  assert.deepEqual(moments(server, clock, 'GET', '/api/me'), [0, 1, 3, 7, 15, 31, 61, 91, 121, 151, 181, 211, 241, 271]);
});

test('with the spread, the waits stay within a tenth of 1, 2, 4 … 30 s', async () => {
  let n = 0;
  const { clock, server, api } = setUp({ random: () => [0, 1][(n += 1) % 2] });
  recordMoments(server, clock);
  dropAll(server, 'GET', '/api/me', 100);
  api.get('/api/me');
  await clock.advance(600 * S);
  const at = moments(server, clock, 'GET', '/api/me');
  const waits = at.slice(1).map((t, i) => t - at[i]);
  const plain = (i) => Math.min(2 ** i, 30);
  assert.ok(waits.length >= 13);
  waits.forEach((w, i) => assert.ok(Math.abs(w - plain(i)) <= plain(i) * 0.1 + 1e-9, `wait ${i}: ${w}`));
  assert.ok(waits.some((w, i) => w !== plain(i)), 'the spread changed no wait');
  assert.ok(at[at.length - 1] <= 300);
});

test('at 19.9 s the line is empty; at 20 s it is amber, counting down to the attempt at 31 s', async () => {
  const { clock, server, api } = setUp();
  dropAll(server, 'GET', '/api/me', 100);
  api.get('/api/me');
  await clock.advanceTo(19.9 * S);
  assert.deepEqual(api.board.state(), { kind: 'none' });
  await clock.advanceTo(20 * S);
  assert.deepEqual(api.board.state(), { kind: 'slow', seconds: 11 });
  for (let s = 21; s <= 30; s += 1) {
    await clock.advanceTo(s * S);
    assert.deepEqual(api.board.state(), { kind: 'slow', seconds: 31 - s }, `at ${s} s`);
  }
  await clock.advanceTo(31 * S);
  assert.deepEqual(api.board.state(), { kind: 'slow', seconds: 30 });
});

test('the countdown is told to the line each second as the clock moves', async () => {
  const { clock, server, api, lines } = setUp();
  dropAll(server, 'GET', '/api/me', 100);
  api.get('/api/me');
  await clock.advanceTo(24 * S);
  assert.deepEqual(lines.filter((l) => l.kind === 'slow').map((l) => l.seconds), [11, 10, 9, 8, 7]);
});

test('at 300 s the line is red; Try again attempts at once and starts the 300 s afresh', async () => {
  const { clock, server, api } = setUp();
  recordMoments(server, clock);
  dropAll(server, 'GET', '/api/me', 100);
  const result = api.get('/api/me');
  await clock.advanceTo(299.9 * S);
  assert.equal(api.board.state().kind, 'slow');
  await clock.advanceTo(300 * S);
  assert.deepEqual(api.board.state(), { kind: 'unreachable' });
  await clock.advanceTo(400 * S);
  assert.equal(server.made('GET', '/api/me').length, 14);

  api.board.tryAgain();
  await clock.advance(0);
  assert.deepEqual(moments(server, clock, 'GET', '/api/me').slice(14), [400]);
  assert.deepEqual(api.board.state(), { kind: 'none' });
  await clock.advanceTo(419.9 * S);
  assert.deepEqual(api.board.state(), { kind: 'none' });
  await clock.advanceTo(420 * S);
  assert.equal(api.board.state().kind, 'slow');

  server.scripts = [];
  await clock.advanceTo(431 * S);
  assert.equal((await result).ok, true);
  assert.deepEqual(api.board.state(), { kind: 'none' });
});

test('Retry now attempts at once and does not restart the count', async () => {
  const { clock, server, api } = setUp();
  recordMoments(server, clock);
  dropAll(server, 'GET', '/api/me', 100);
  api.get('/api/me');
  await clock.advanceTo(22 * S);
  api.board.retryNow();
  await clock.advance(0);
  assert.deepEqual(moments(server, clock, 'GET', '/api/me'), [0, 1, 3, 7, 15, 22]);
  // the count still runs from the first failure, and the next wait follows on
  assert.deepEqual(api.board.state(), { kind: 'slow', seconds: 30 });
  await clock.advanceTo(52 * S);
  assert.deepEqual(moments(server, clock, 'GET', '/api/me').slice(-1), [52]);
  await clock.advanceTo(300 * S);
  assert.equal(api.board.state().kind, 'unreachable');
});

test('Retry-After: 7 holds the next attempt for 7 s', async () => {
  const { clock, server, api } = setUp();
  recordMoments(server, clock);
  server.script('POST', '/api/parts', steps.report(errorReport('front.too_many_requests'), { retryAfter: 7 }));
  const result = api.post('/api/parts', { bytes: new Uint8Array(4), upload: true });
  await clock.advanceTo(6.9 * S);
  assert.equal(server.made('POST', '/api/parts').length, 1);
  await clock.advanceTo(7 * S);
  assert.equal((await result).ok, true);
  assert.deepEqual(moments(server, clock, 'POST', '/api/parts'), [0, 7]);
});

for (const code of ['front.slice_unreachable', 'front.state_bucket_unreachable', 'front.onshape_unreachable', 'front.too_many_requests', 'front.unexpected']) {
  test(`${code} is retried quietly`, async () => {
    const { clock, server, api } = setUp();
    server.script('GET', '/api/configuration', steps.report(errorReport(code)));
    const result = api.get('/api/configuration');
    await clock.advance(1 * S);
    assert.equal((await result).ok, true);
    assert.equal(server.requests.length, 2);
  });
}

test('an answer without the front server\'s version is retried quietly', async () => {
  const { clock, server, api } = setUp();
  server.script('GET', '/api/me', steps.noVersion(502), steps.noVersion(200, '{"user": {}}'));
  const result = api.get('/api/me');
  await clock.advance(3 * S);
  assert.equal((await result).ok, true);
  assert.equal(server.requests.length, 3);
});

for (const [name, report, status] of [
  ['slice.busy', errorReport('slice.busy', { retryable: true }), 503],
  ['a refusal of printer delivery', errorReport('delivery.printer_busy', { retryable: true }), 409],
  ['a code the page does not know', errorReport('front.something_new', { retryable: true }), 503],
  ['slice.stopping, which has a rule of its own', errorReport('slice.stopping', { retryable: true }), 503],
]) {
  test(`${name} is given to the caller at once and not retried`, async () => {
    const { clock, server, api } = setUp();
    server.script('POST', '/api/slices', steps.report(report, { status }));
    const result = await api.post('/api/slices', { json: {} });
    assert.deepEqual(result, { ok: false, status, report });
    await clock.advance(600 * S);
    assert.equal(server.requests.length, 1);
    assert.equal(api.board.state().kind, 'none');
  });
}

test('an attempt with no answer in 15 s counts as failed, and an upload\'s in 60 s', async () => {
  const { clock, server, api } = setUp();
  recordMoments(server, clock);
  server.script('GET', '/api/me', steps.hold());
  server.script('POST', '/api/parts', steps.hold());
  const me = api.get('/api/me');
  const part = api.post('/api/parts', { bytes: new Uint8Array(4), upload: true });
  await clock.advanceTo(14.9 * S);
  assert.equal(server.requests.length, 2);
  await clock.advanceTo(16 * S);
  assert.equal((await me).ok, true);
  assert.deepEqual(moments(server, clock, 'GET', '/api/me'), [0, 16]);
  await clock.advanceTo(59.9 * S);
  assert.equal(server.made('POST', '/api/parts').length, 1);
  await clock.advanceTo(61 * S);
  assert.equal((await part).ok, true);
  assert.deepEqual(moments(server, clock, 'POST', '/api/parts'), [0, 61]);
});

test('while the attempt is being made the line says the browser is retrying now', async () => {
  const { clock, server, api } = setUp();
  server.script('GET', '/api/me', steps.drop(), steps.drop(), steps.drop(), steps.drop(), steps.drop(), steps.hold());
  api.get('/api/me');
  await clock.advanceTo(31 * S);
  assert.deepEqual(api.board.state(), { kind: 'slow', seconds: 0 });
});

test('a row learns its request is slow at 4 s and not at 3.9 s', async () => {
  const { clock, server, api } = setUp();
  dropAll(server, 'POST', '/api/parts', 3);
  let slow = 0;
  api.post('/api/parts', { bytes: new Uint8Array(4), upload: true, onSlow: () => { slow += 1; } });
  await clock.advanceTo(3.9 * S);
  assert.equal(slow, 0);
  await clock.advanceTo(4 * S);
  assert.equal(slow, 1);
  await clock.advanceTo(10 * S);
  assert.equal(slow, 1);
});

test('a request answered before 4 s never tells its row it is slow', async () => {
  const { clock, server, api } = setUp();
  server.script('POST', '/api/parts', steps.drop());
  let slow = 0;
  const result = api.post('/api/parts', { bytes: new Uint8Array(4), upload: true, onSlow: () => { slow += 1; } });
  await clock.advanceTo(10 * S);
  assert.equal((await result).ok, true);
  assert.equal(slow, 0);
});

test('after 300 s the request is kept, not dropped, and Try again sends it again', async () => {
  const { clock, server, api } = setUp();
  dropAll(server, 'POST', '/api/parts', 14);
  let settled = false;
  const result = api.post('/api/parts', { bytes: new Uint8Array(4), upload: true });
  result.then(() => { settled = true; });
  await clock.advanceTo(900 * S);
  assert.equal(settled, false);
  assert.equal(api.pending(), 1);
  api.board.tryAgain();
  assert.equal((await result).ok, true);
});

test('the line goes the moment any request of the page is answered', async () => {
  const { clock, server, api, lines } = setUp();
  dropAll(server, 'GET', '/api/configuration', 100);
  api.get('/api/configuration');
  await clock.advanceTo(25 * S);
  assert.equal(api.board.state().kind, 'slow');
  const before = lines.length;
  let atAnswer = null;
  server.script('GET', '/api/me', steps.hold());
  const n = server.requests.length + 1;
  const me = api.get('/api/me');
  const record = await server.arrived(n);
  api.board.subscribe((state) => { if (atAnswer === null) atAnswer = state; });
  record.held.release();
  await me;
  assert.deepEqual(atAnswer, { kind: 'none' });
  assert.deepEqual(lines[before], { kind: 'none' });
});

test('a request still failing after another is answered brings the line back at its next failure', async () => {
  const { clock, server, api } = setUp();
  dropAll(server, 'GET', '/api/configuration', 100);
  api.get('/api/configuration');
  await clock.advanceTo(25 * S);
  await api.get('/api/me');
  await clock.advance(0);
  // /api/configuration was sent again at once, failed again, and its count still runs from 0 s
  assert.equal(api.board.state().kind, 'slow');
});

test('an answer to another request sends every waiting request again at once', async () => {
  const { clock, server, api } = setUp();
  recordMoments(server, clock);
  server.script('GET', '/api/configuration', ...Array.from({ length: 5 }, () => steps.drop()));
  const configuration = api.get('/api/configuration');
  await clock.advanceTo(25 * S);
  await api.get('/api/me');
  await clock.advance(0);
  assert.equal((await configuration).ok, true);
  assert.deepEqual(moments(server, clock, 'GET', '/api/configuration'), [0, 1, 3, 7, 15, 25]);
});

test('the line shows the countdown of the request that failed earliest', async () => {
  const { clock, server, api } = setUp();
  dropAll(server, 'GET', '/api/me', 100);
  dropAll(server, 'GET', '/api/configuration', 100);
  api.get('/api/me');
  await clock.advanceTo(10 * S);
  api.get('/api/configuration');
  await clock.advanceTo(20 * S);
  // /api/me failed at 0 and next tries at 31; /api/configuration failed at 10 and tries at 25
  assert.deepEqual(api.board.state(), { kind: 'slow', seconds: 11 });
  await clock.advanceTo(300 * S);
  assert.deepEqual(api.board.state(), { kind: 'unreachable' });
});

test('which answers are quiet retries', () => {
  assert.equal(isQuietRetry({ code: 'front.unexpected' }, '/api/me'), true);
  assert.equal(isQuietRetry({ code: 'front.onshape_unreachable' }, '/api/me'), true);
  assert.equal(isQuietRetry({ code: 'front.onshape_unreachable' }, '/signin'), false);
  assert.equal(isQuietRetry({ code: 'slice.busy' }, '/api/slices'), false);
  assert.equal(isQuietRetry({ code: 'front.too_many_streams' }, '/api/slices/x/events'), false);
});
