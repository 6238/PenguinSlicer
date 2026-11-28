// The module that makes every request (src/api.js): the headers the contract's "Rules for every
// request" require, how an answer becomes what the caller gets, the version on every answer,
// and the wizard's own report for an answer it cannot read.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../src/api.js';
import { readBody } from '../src/seams/transport.js';
import { FakeClock } from './fakes/clock.js';
import { FakeFrontServer, errorReport, errorReportProblems, example, steps } from './fakes/front_server.js';

const PAGE = '20261126T101010Z-abcdef0';
const GROUP = '61a9c0d2e4b7f80012345678';

function setUp({ group = GROUP } = {}) {
  const clock = new FakeClock();
  const server = new FakeFrontServer();
  const api = createApi({ transport: server.transport, clock, version: PAGE, currentGroup: () => group, random: () => 0.5 });
  return { clock, server, api };
}

test('every request carries the page version, and none carries the mark unless it changes something', async () => {
  const { server, api } = setUp();
  await api.get('/api/me');
  await api.get('/api/configuration');
  const [me, configuration] = server.requests;
  assert.equal(me.headers['x-penguinslicer-page'], PAGE);
  assert.equal(configuration.headers['x-penguinslicer-page'], PAGE);
  assert.equal(me.headers['x-penguinslicer-wizard'], undefined);
  assert.equal(configuration.headers['x-penguinslicer-wizard'], undefined);
});

test('every POST, PUT and DELETE carries the wizard mark', async () => {
  const { server, api } = setUp();
  await api.post('/api/slices', { json: example('plate-configuration-phase-2.json') });
  await api.put('/api/configuration', { json: example('wizard-front/configuration-write-request.json') });
  await api.request('DELETE', '/api/printer/pairing');
  assert.deepEqual(server.requests.map((r) => [r.method, r.headers['x-penguinslicer-wizard']]),
    [['POST', '1'], ['PUT', '1'], ['DELETE', '1']]);
});

test('a request that acts for a group names the current group; one that does not, does not', async () => {
  const { server, api } = setUp();
  await api.get('/api/me');
  await api.get('/api/settings-table');
  await api.get('/api/configuration');
  await api.post('/api/slices', { json: {} });
  assert.deepEqual(server.requests.map((r) => [r.path, r.headers['x-penguinslicer-group']]), [
    ['/api/me', undefined], ['/api/settings-table', undefined], ['/api/configuration', GROUP], ['/api/slices', GROUP]]);
});

test('before the current group is known, no group is named', async () => {
  const { server, api } = setUp({ group: null });
  await api.get('/api/configuration');
  assert.equal(server.requests[0].headers['x-penguinslicer-group'], undefined);
});

test('a plain download link names the group in its query', () => {
  const { api } = setUp();
  assert.equal(api.link('/api/slices/3f9a1c2b/file'), `/api/slices/3f9a1c2b/file?group=${GROUP}`);
  assert.equal(api.link('/api/slices/3f9a1c2b/file?x=1'), `/api/slices/3f9a1c2b/file?x=1&group=${GROUP}`);
});

test('a JSON body is sent as JSON, and bytes as they are', async () => {
  const { server, api } = setUp();
  const bytes = new Uint8Array([1, 2, 3]);
  await api.post('/api/slices', { json: { plate_id: 'p' } });
  await api.post('/api/parts?units=in', { bytes, upload: true });
  assert.equal(server.requests[0].headers['content-type'], 'application/json');
  assert.equal(server.requests[0].body, '{"plate_id":"p"}');
  assert.equal(server.requests[1].headers['content-type'], 'application/octet-stream');
  assert.equal(server.requests[1].body, bytes);
});

test('the page never names the user or a cookie', async () => {
  const { server, api } = setUp();
  await api.get('/api/me');
  await api.post('/api/slices', { json: {} });
  for (const request of server.requests) {
    assert.deepEqual(Object.keys(request.headers).filter((h) => /cookie|user/.test(h)), []);
  }
});

test('a successful answer gives its status and its JSON body', async () => {
  const { api } = setUp();
  assert.deepEqual(await api.get('/api/me'), { ok: true, status: 200, body: example('wizard-front/me.json') });
  assert.deepEqual(await api.post('/api/reports/failure', { json: {}, once: true }), { ok: true, status: 204, body: null });
});

test('an error report reaches the caller whole, by its code, with its status', async () => {
  const { server, api } = setUp();
  const report = errorReport('slice.busy', { retryable: true });
  server.script('POST', '/api/slices', steps.report(report, { status: 503 }));
  assert.deepEqual(await api.post('/api/slices', { json: {} }), { ok: false, status: 503, report });
});

test('every answer\'s version is told, whatever its status', async () => {
  const { server, api } = setUp();
  const seen = [];
  api.onVersion((version) => seen.push(version));
  server.script('GET', '/api/configuration', steps.report(errorReport('front.group_not_allowed')));
  await api.get('/api/me');
  await api.get('/api/configuration');
  assert.deepEqual(seen, [server.version, server.version]);
});

test('an answer of the front server that is not JSON is the wizard\'s own report, shown and not retried', async () => {
  const { server, api } = setUp();
  server.script('GET', '/api/me', steps.notJson(200));
  const result = await api.get('/api/me');
  assert.equal(result.ok, false);
  assert.equal(result.report.code, 'wizard.bad_answer');
  assert.deepEqual(errorReportProblems(result.report), []);
  assert.equal(server.requests.length, 1);
});

test('the bad answer\'s detail is the path, the status and the start of the body', async () => {
  const { server, api } = setUp();
  server.script('GET', '/api/me', { kind: 'answer', status: 200, body: `<html>${'x'.repeat(400)}`, headers: { 'Content-Type': 'text/html' } });
  server.script('GET', '/api/configuration', steps.answer(404, { not: 'a report' }));
  const html = await api.get('/api/me');
  assert.equal(html.report.detail, `/api/me answered 200: <html>${'x'.repeat(194)}`);
  const notReport = await api.get('/api/configuration');
  assert.equal(notReport.report.detail, '/api/configuration answered 404: {"not":"a report"}');
});

test('an error status whose body is not an error report is the same report of the wizard\'s', async () => {
  const { server, api } = setUp();
  server.script('GET', '/api/me', steps.answer(404, { not: 'a report' }));
  const result = await api.get('/api/me');
  assert.equal(result.report.code, 'wizard.bad_answer');
  assert.equal(result.status, 404);
});

test('the sliced file comes back as bytes', async () => {
  const { server, api } = setUp();
  server.script('GET', '/api/slices/3f9a1c2b/file', { kind: 'answer', status: 200, body: 'G1 X0', headers: { 'Content-Type': 'application/octet-stream' } });
  const result = await api.get('/api/slices/3f9a1c2b/file', { expect: 'bytes' });
  assert.equal(new TextDecoder().decode(result.body), 'G1 X0');
});

test('the browser\'s transport reads a body whole and tells of each part as it arrives', async () => {
  const parts = ['G1 X0\n', 'G1 X1\n', 'G1 X22\n'].map((p) => new TextEncoder().encode(p));
  const stream = new ReadableStream({ start(c) { for (const p of parts) c.enqueue(p); c.close(); } });
  const told = [];
  const whole = await readBody(new Response(stream), (n) => told.push(n));
  assert.equal(new TextDecoder().decode(whole), 'G1 X0\nG1 X1\nG1 X22\n');
  assert.deepEqual(told, [6, 6, 7]);
  assert.equal((await readBody(new Response(null))).byteLength, 0);
});

test('a request counts as pending from its sending until its answer', async () => {
  const { server, api } = setUp();
  server.script('GET', '/api/me', steps.hold());
  const answer = api.get('/api/me');
  const record = await server.arrived(1);
  assert.equal(api.pending(), 1);
  record.held.release();
  await answer;
  assert.equal(api.pending(), 0);
});

test('a report about the page is sent once: a failure drops it and nothing retries it', async () => {
  const { clock, server, api } = setUp();
  server.script('POST', '/api/reports/failure', steps.drop());
  assert.deepEqual(await api.post('/api/reports/failure', { json: {}, once: true }), { ok: false, dropped: true });
  server.script('POST', '/api/reports/failure', steps.report(errorReport('front.unexpected')));
  assert.deepEqual(await api.post('/api/reports/failure', { json: {}, once: true }), { ok: false, dropped: true });
  await clock.advance(600_000);
  assert.equal(server.made('POST', '/api/reports/failure').length, 2);
  assert.equal(api.board.state().kind, 'none');
});
