// The fake front server answers in the contract's shapes: its default answers are the
// contract's examples, whole, and every error report it makes has the error report's fields.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdirSync } from 'node:fs';
import { join } from 'node:path';

import { EXAMPLES, FRONT_CODES, FakeFrontServer, errorReport, errorReportProblems, example, exampleEvents, steps } from './fakes/front_server.js';

async function ask(server, method, path) {
  const answer = await server.transport.send({ method, path, headers: {} });
  return { status: answer.status, version: answer.header('X-PenguinSlicer-Version'), body: answer.status === 204 ? null : await answer.json() };
}

test('the default answers are the contract examples, whole, with their statuses', async () => {
  const server = new FakeFrontServer();
  assert.deepEqual(await ask(server, 'GET', '/api/me'), { status: 200, version: server.version, body: example('wizard-front/me.json') });
  assert.equal((await ask(server, 'POST', '/api/parts?units=in')).status, 201);
  assert.deepEqual(await ask(server, 'POST', '/api/slices'), { status: 202, version: server.version, body: example('wizard-front/slice-accepted.json') });
  assert.deepEqual((await ask(server, 'GET', '/api/slices/3f9a1c2b')).body, example('wizard-front/slice-done.json'));
  assert.deepEqual((await ask(server, 'GET', '/api/slices/3f9a1c2b/summary')).body, example('wizard-front/slice-summary.json'));
  assert.deepEqual((await ask(server, 'PUT', '/api/configuration')).body, example('wizard-front/configuration-written.json'));
  assert.deepEqual((await ask(server, 'GET', '/api/settings-table')).body, example('settings-table.json'));
  const configuration = (await ask(server, 'GET', '/api/configuration')).body;
  assert.deepEqual(configuration, { configuration: example('configuration-default.json'), source: 'default', name: 'PenguinSlicer default', revision: null });
  assert.deepEqual(await ask(server, 'POST', '/api/reports/failure'), { status: 204, version: server.version, body: null });
});

test('a progress stream is by default the contract\'s example, whole, and then closed', async () => {
  const server = new FakeFrontServer();
  const answer = await server.transport.send({ method: 'GET', path: '/api/slices/3f9a1c2b/events', headers: {} });
  assert.equal(answer.status, 200);
  assert.equal(answer.header('Content-Type'), 'text/event-stream');
  const got = [];
  await answer.chunks((text) => got.push(text));
  assert.equal(got.join(''), exampleEvents());
});

test('a stream the test feeds gives each piece in order, then ends, or is cut off', async () => {
  const server = new FakeFrontServer();
  const one = steps.stream(['a']);
  const two = steps.stream();
  server.script('GET', '/api/slices/j/events', one, two);
  const first = await server.transport.send({ method: 'GET', path: '/api/slices/j/events', headers: {} });
  const got = [];
  const reading = first.chunks((text) => got.push(text));
  one.feed.send('b');
  one.feed.end();
  await reading;
  assert.deepEqual(got, ['a', 'b']);
  const second = await server.transport.send({ method: 'GET', path: '/api/slices/j/events', headers: {} });
  const cut = second.chunks(() => {});
  two.feed.cut();
  await assert.rejects(cut, TypeError);
});

test('an upload is answered with the record of the bytes sent: their hash, the query\'s units, no warning, the example\'s measurements', async () => {
  const server = new FakeFrontServer();
  const bytes = new Uint8Array([1, 2, 3, 4]);
  const answer = await server.transport.send({ method: 'POST', path: '/api/parts?units=mm', headers: {}, body: bytes.buffer });
  const record = await answer.json();
  assert.equal(answer.status, 201);
  assert.equal(record.sha256, createHash('sha256').update(bytes).digest('hex'));
  assert.equal(record.units, 'mm');
  assert.deepEqual(record.warnings, []);
  assert.deepEqual(record.measurements, example('wizard-front/part-record.json').measurements);
});

test('a request the contract does not have is answered as the front server answers it', async () => {
  const answer = await ask(new FakeFrontServer(), 'GET', '/api/nothing');
  assert.equal(answer.status, 404);
  assert.equal(answer.body.code, 'front.no_such_request');
});

test('every example error report passes the check of an error report, and the check can fail', () => {
  const files = readdirSync(EXAMPLES).filter((name) => name.startsWith('error-report'));
  assert.ok(files.length >= 5);
  for (const name of files) assert.deepEqual(errorReportProblems(example(name)), [], name);
  assert.deepEqual(errorReportProblems({ code: 'slice.busy', message: 'm', remedy: 'r', retryable: 'no', detail: '' }), ['retryable is not a boolean']);
  assert.deepEqual(errorReportProblems({ code: 'x', message: 'm', remedy: 'r', retryable: true, detail: '', extra: 1 }),
    ['extra is not a field of an error report', 'code is not component.what']);
});

test('every error report the fake makes has the shape of an error report and the contract status', async () => {
  const server = new FakeFrontServer();
  for (const [code, [status, retryable]] of Object.entries(FRONT_CODES)) {
    const report = errorReport(code);
    assert.deepEqual(errorReportProblems(report), [], code);
    assert.equal(report.retryable, retryable, code);
    server.script('GET', '/api/me', steps.report(report));
    const answer = await ask(server, 'GET', '/api/me');
    assert.equal(answer.status, status, code);
    assert.deepEqual(answer.body, report);
  }
});

test('a held request waits for the test and an aborted one fails', async () => {
  const server = new FakeFrontServer();
  server.script('GET', '/api/me', steps.hold(), steps.hold());
  const first = ask(server, 'GET', '/api/me');
  const record = await server.arrived(1);
  record.held.release(steps.answer(200, { held: true }));
  assert.deepEqual((await first).body, { held: true });

  const controller = new AbortController();
  const second = server.transport.send({ method: 'GET', path: '/api/me', headers: {}, signal: controller.signal });
  await server.arrived(2);
  controller.abort();
  await assert.rejects(second, { name: 'AbortError' });
});

test('a dropped request fails as a lost connection, and an answer without the version is not the front server', async () => {
  const server = new FakeFrontServer();
  server.script('GET', '/api/me', steps.drop(), steps.noVersion());
  await assert.rejects(server.transport.send({ method: 'GET', path: '/api/me', headers: {} }), TypeError);
  const answer = await server.transport.send({ method: 'GET', path: '/api/me', headers: {} });
  assert.equal(answer.status, 502);
  assert.equal(answer.header('X-PenguinSlicer-Version'), null);
});
