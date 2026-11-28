// Following a slice job (src/following.js; wizard/README-details.md, "Progress streams"): its
// progress stream read event by event, a stream that closes before a final report reopened
// silently, the 20 s of failing to reopen and the 45 s of silence after which the stream counts as
// a failed request, the keep-alive comments, a refusal, a fifth stream answered by asking, and
// asking every POLL_S behind the same interface. The fake front server closes, silences and
// refuses streams at the moments each test chooses, on the fake clock.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../src/api.js';
import { createEventParser, followJob } from '../src/following.js';
import { POLL_S, STREAM_REOPEN_FAIL_S, STREAM_SILENT_S } from '../src/page-constants.js';
import { RETRY_QUIET_S } from '../src/page-constants.js';
import { FakeClock } from './fakes/clock.js';
import { FakeFrontServer, errorReport, events, example, steps } from './fakes/front_server.js';

const JOB = '3f9a1c2b';
const PATH = `/api/slices/${JOB}`;
const EVENTS = `${PATH}/events`;

function report(sequence, fields = {}) {
  return { job: JOB, state: 'running', stage: 'generating_infill', stage_label: 'Generating infill', fraction: sequence / 100, elapsed_s: sequence, expected_s: 75, sequence, ...fields };
}
const done = (sequence) => ({ ...example('wizard-front/slice-done.json').progress, sequence });

function setUp() {
  const clock = new FakeClock();
  const server = new FakeFrontServer();
  const api = createApi({ transport: server.transport, clock, version: 'v', currentGroup: () => 'g', random: () => 0.5 });
  const got = [];
  const refused = [];
  const follow = (mode) => followJob({
    api, clock, path: PATH, mode, random: () => 0.5,
    onReport: (r) => got.push(r), onRefused: (r) => refused.push(r),
  });
  return { clock, server, api, got, refused, follow };
}

test('the parser reads events, ids and comments, across pieces split anywhere', () => {
  const seen = [];
  const parser = createEventParser((event) => seen.push(event));
  const text = `${events.version('X')}: keep-alive\n\nevent: progress\r\nid: 3\r\ndata: {"a":\r\ndata: 1}\r\n\r\n`;
  for (const ch of text) parser.push(ch);
  assert.deepEqual(seen, [{ event: 'version', data: '{"version":"X"}', id: null }, { event: 'progress', data: '{"a":\n1}', id: '3' }]);
});

test('the reports are delivered in order, and one not above the last is ignored', async () => {
  const { clock, server, got, follow } = setUp();
  const stream = steps.stream([events.version(), events.progress(report(17))]);
  server.script('GET', EVENTS, stream);
  follow('stream');
  await clock.advance(0);
  stream.feed.send(events.progress(report(17)));
  stream.feed.send(events.progress(report(16)));
  stream.feed.send(events.progress(report(18)));
  await clock.advance(0);
  assert.deepEqual(got.map((r) => r.sequence), [17, 18]);
});

test('the version event is told as any answer\'s version is', async () => {
  const { clock, server, api, follow } = setUp();
  const heard = [];
  api.onVersion((v) => heard.push(v));
  server.script('GET', EVENTS, steps.stream([events.version('20261201T000000Z-1111111')]));
  follow('stream');
  await clock.advance(0);
  assert.ok(heard.includes('20261201T000000Z-1111111'));
});

test('a stream closed mid-slice is reopened at once, and the latest report shown', async () => {
  const { clock, server, got, follow } = setUp();
  const first = steps.stream([events.version(), events.progress(report(17))]);
  const second = steps.stream([events.version(), events.progress(report(23))]);
  server.script('GET', EVENTS, first, second);
  follow('stream');
  await clock.advance(0);
  first.feed.end();
  await clock.advance(0);
  assert.equal(server.made('GET', EVENTS).length, 2);
  assert.deepEqual(got.map((r) => r.sequence), [17, 23]);
});

test('a stream cut off as by a restart is reopened too, and nothing is said', async () => {
  const { clock, server, api, got, follow } = setUp();
  const first = steps.stream([events.progress(report(5))]);
  server.script('GET', EVENTS, first, steps.stream([events.progress(report(6))]));
  follow('stream');
  await clock.advance(0);
  first.feed.cut();
  await clock.advance(0);
  assert.deepEqual(got.map((r) => r.sequence), [5, 6]);
  assert.equal(api.board.state().kind, 'none');
});

test('after a final report the stream is not opened again', async () => {
  const { clock, server, got, follow } = setUp();
  server.script('GET', EVENTS, steps.stream([events.progress(report(5)), events.progress(done(41))], { end: true }));
  follow('stream');
  await clock.advance(600_000);
  assert.equal(server.made('GET', EVENTS).length, 1);
  assert.deepEqual(got.map((r) => r.state), ['running', 'done']);
});

test('the final report ends the stream even when the front server leaves it open', async () => {
  const { clock, server, follow } = setUp();
  const stream = steps.stream([events.progress(done(41))]);
  server.script('GET', EVENTS, stream);
  follow('stream');
  await clock.advance(0);
  assert.equal(stream.feed.aborted, true);
  await clock.advance(600_000);
  assert.equal(server.made('GET', EVENTS).length, 1);
});

test('failing to reopen for 19.9 s shows nothing, and 20 s shows the panel line', async () => {
  const { clock, server, api, follow } = setUp();
  const first = steps.stream([events.progress(report(5))]);
  server.script('GET', EVENTS, first, ...Array.from({ length: 8 }, () => steps.drop()));
  follow('stream');
  await clock.advance(0);
  first.feed.end();
  await clock.advance(STREAM_REOPEN_FAIL_S * 1000 - 100);
  assert.equal(api.board.state().kind, 'none');
  await clock.advance(100);
  assert.equal(api.board.state().kind, 'slow');
  assert.equal(STREAM_REOPEN_FAIL_S, RETRY_QUIET_S);
});

test('an open stream silent for 44.9 s shows nothing; at 45 s it counts as failed, is closed and reopened', async () => {
  const { clock, server, api, follow } = setUp();
  const first = steps.stream([events.progress(report(5))]);
  server.script('GET', EVENTS, first, steps.hold());
  follow('stream');
  await clock.advance(STREAM_SILENT_S * 1000 - 100);
  assert.equal(first.feed.aborted, false);
  assert.equal(api.board.state().kind, 'none');
  assert.equal(server.made('GET', EVENTS).length, 1);
  await clock.advance(100);
  assert.equal(first.feed.aborted, true);
  assert.equal(server.made('GET', EVENTS).length, 2);
  assert.equal(api.board.state().kind, 'slow');
});

test('a reopened stream after silence ends the line once it is answered', async () => {
  const { clock, server, api, got, follow } = setUp();
  server.script('GET', EVENTS, steps.stream([events.progress(report(5))]), steps.stream([events.progress(report(9))]));
  follow('stream');
  await clock.advance(STREAM_SILENT_S * 1000);
  assert.equal(api.board.state().kind, 'none');
  assert.deepEqual(got.map((r) => r.sequence), [5, 9]);
});

test('comment lines every 15 s keep a stream alive for as long as it lasts', async () => {
  const { clock, server, api, follow } = setUp();
  const stream = steps.stream([events.progress(report(5))]);
  server.script('GET', EVENTS, stream);
  follow('stream');
  for (let i = 0; i < 60; i += 1) {
    await clock.advance(15_000);
    stream.feed.send(events.keepAlive());
  }
  assert.equal(server.made('GET', EVENTS).length, 1);
  assert.equal(stream.feed.aborted, false);
  assert.equal(api.board.state().kind, 'none');
});

test('a stream that closes before saying anything is reopened with the waits of retrying', async () => {
  const { clock, server, follow } = setUp();
  server.script('GET', EVENTS, ...Array.from({ length: 6 }, () => steps.stream([], { end: true })));
  follow('stream');
  await clock.advance(0);
  assert.equal(server.made('GET', EVENTS).length, 1);
  await clock.advance(1_000);
  assert.equal(server.made('GET', EVENTS).length, 2);
  await clock.advance(2_000);
  assert.equal(server.made('GET', EVENTS).length, 3);
});

test('a fifth stream, refused, is followed by asking every POLL_S, and nothing of the refusal shows', async () => {
  const { clock, server, api, got, refused, follow } = setUp();
  server.script('GET', EVENTS, steps.report(errorReport('front.too_many_streams')));
  server.script('GET', PATH, steps.answer(200, { progress: report(3) }), steps.answer(200, { progress: report(4) }), steps.answer(200, { progress: done(41) }));
  follow('stream');
  await clock.advance(0);
  assert.deepEqual(got.map((r) => r.sequence), [3]);
  await clock.advance(POLL_S * 1000 - 1);
  assert.equal(server.made('GET', PATH).length, 1);
  await clock.advance(1);
  assert.deepEqual(got.map((r) => r.sequence), [3, 4]);
  await clock.advance(POLL_S * 1000);
  assert.deepEqual(got.map((r) => r.state), ['running', 'running', 'done']);
  await clock.advance(60_000);
  assert.equal(server.made('GET', PATH).length, 3);
  assert.deepEqual(refused, []);
  assert.equal(api.board.state().kind, 'none');
});

test('asking, chosen in place of the stream, delivers the same reports the same way', async () => {
  const { clock, server, got, follow } = setUp();
  server.script('GET', PATH, steps.answer(200, { progress: report(3) }), steps.answer(200, { progress: report(3) }), steps.answer(200, { progress: done(41) }));
  follow('ask');
  await clock.advance(POLL_S * 2000);
  assert.deepEqual(got.map((r) => r.sequence), [3, 41]);
  assert.equal(server.made('GET', EVENTS).length, 0);
});

test('a stream refused for an unknown slice job is told to the caller and not opened again', async () => {
  const { clock, server, refused, follow } = setUp();
  server.script('GET', EVENTS, steps.report(errorReport('front.slice_unknown')));
  follow('stream');
  await clock.advance(60_000);
  assert.deepEqual(refused.map((r) => r.code), ['front.slice_unknown']);
  assert.equal(server.made('GET', EVENTS).length, 1);
});

test('asking that is refused tells the caller and stops', async () => {
  const { clock, server, refused, follow } = setUp();
  server.script('GET', PATH, steps.report(errorReport('front.slice_unknown')));
  follow('ask');
  await clock.advance(60_000);
  assert.deepEqual(refused.map((r) => r.code), ['front.slice_unknown']);
  assert.equal(server.made('GET', PATH).length, 1);
});

test('an answer to asking that holds no progress report is the wizard\'s bad answer', async () => {
  const { clock, server, refused, follow } = setUp();
  server.script('GET', PATH, steps.answer(200, { nothing: true }));
  follow('ask');
  await clock.advance(0);
  assert.deepEqual(refused.map((r) => r.code), ['wizard.bad_answer']);
});

test('an event whose data is not a progress report is left aside', async () => {
  const { clock, server, got, follow } = setUp();
  const stream = steps.stream(['event: progress\nid: 4\ndata: not json\n\n', 'event: progress\ndata: {"state":"running"}\n\n', events.progress(report(6))]);
  server.script('GET', EVENTS, stream);
  follow('stream');
  await clock.advance(0);
  assert.deepEqual(got.map((r) => r.sequence), [6]);
});

test('stop() ends the stream and nothing more is asked', async () => {
  const { clock, server, follow } = setUp();
  const stream = steps.stream([events.progress(report(5))]);
  server.script('GET', EVENTS, stream);
  const following = follow('stream');
  await clock.advance(0);
  following.stop();
  await clock.advance(0);
  assert.equal(stream.feed.aborted, true);
  await clock.advance(600_000);
  assert.equal(server.made('GET', EVENTS).length, 1);
});

test('stop() while asking ends the asking', async () => {
  const { clock, server, follow } = setUp();
  server.script('GET', PATH, steps.answer(200, { progress: report(3) }));
  const following = follow('ask');
  await clock.advance(0);
  following.stop();
  await clock.advance(60_000);
  assert.equal(server.made('GET', PATH).length, 1);
});
