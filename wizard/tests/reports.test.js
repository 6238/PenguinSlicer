// The page's reports about its own failures (src/reports.js; wizard/README-details.md, "What the
// wizard reports about itself"): each sent once with exactly the contract's fields, held to
// REPORTS_PER_MIN on the fake clock, and dropped, never retried, when it cannot be sent or is
// refused.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../src/api.js';
import { REPORTS_PER_MIN, createReports } from '../src/reports.js';
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
