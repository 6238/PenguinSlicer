// A progress stream opened through the module that makes every request (src/api.js, expect
// 'stream'): its opening follows every rule of a request (the headers, the version, retrying),
// and once its headers arrive the caller reads its body piece by piece, for as long as it lasts,
// with no attempt time on it (wizard/README-details.md, "Progress streams").
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../src/api.js';
import { fetchTransport } from '../src/seams/transport.js';
import { FakeClock } from './fakes/clock.js';
import { FakeFrontServer, errorReport, events, steps } from './fakes/front_server.js';

const PAGE = '20261126T101010Z-abcdef0';
const GROUP = '61a9c0d2e4b7f80012345678';
const EVENTS = '/api/slices/3f9a1c2b/events';

function setUp() {
  const clock = new FakeClock();
  const server = new FakeFrontServer();
  const api = createApi({ transport: server.transport, clock, version: PAGE, currentGroup: () => GROUP, random: () => 0.5 });
  return { clock, server, api };
}

test('a stream is opened with the headers of any request and handed over once its headers arrive', async () => {
  const { server, api } = setUp();
  const stream = steps.stream([events.version()]);
  server.script('GET', EVENTS, stream);
  const answer = await api.get(EVENTS, { expect: 'stream' });
  assert.equal(answer.ok, true);
  assert.equal(answer.status, 200);
  const [request] = server.made('GET', EVENTS);
  assert.equal(request.headers['x-penguinslicer-page'], PAGE);
  assert.equal(request.headers['x-penguinslicer-group'], GROUP);
  const got = [];
  const reading = answer.stream.chunks((text) => got.push(text));
  stream.feed.send(events.keepAlive());
  stream.feed.end();
  await reading;
  assert.deepEqual(got, [events.version(), events.keepAlive()]);
  assert.equal(api.pending(), 0);              // an open stream is not a pending request
});

test('an open stream has no attempt time: it is read for as long as it lasts', async () => {
  const { clock, server, api } = setUp();
  const stream = steps.stream();
  server.script('GET', EVENTS, stream);
  const answer = await api.get(EVENTS, { expect: 'stream' });
  const got = [];
  const reading = answer.stream.chunks((text) => got.push(text));
  await clock.advance(600_000);
  assert.equal(stream.feed.reading, true);
  assert.equal(stream.feed.aborted, false);
  stream.feed.send('x');
  stream.feed.end();
  await reading;
  assert.deepEqual(got, ['x']);
});

test('the caller\'s signal ends the stream it is reading', async () => {
  const { server, api } = setUp();
  const stream = steps.stream();
  server.script('GET', EVENTS, stream);
  const controller = new AbortController();
  const answer = await api.get(EVENTS, { expect: 'stream', signal: controller.signal });
  const reading = answer.stream.chunks(() => {});
  controller.abort();
  await assert.rejects(reading, { name: 'AbortError' });
  assert.equal(stream.feed.aborted, true);
});

test('a stream that cannot be opened is retried with the waits of any request, and the line shows at 20 s', async () => {
  const { clock, server, api } = setUp();
  // attempts at 0, 1, 3, 7 and 15 s fail; the one at 31 s is answered
  server.script('GET', EVENTS, steps.drop(), steps.drop(), steps.drop(), steps.drop(), steps.drop());
  const answer = api.get(EVENTS, { expect: 'stream' });
  await clock.advance(19_900);
  assert.equal(api.board.state().kind, 'none');
  await clock.advance(100);
  assert.equal(api.board.state().kind, 'slow');
  await clock.advance(11_000);                 // the attempt at 31 s is answered by the default stream
  const opened = await answer;
  assert.equal(opened.ok, true);
  assert.equal(api.board.state().kind, 'none');
});

test('a refused stream is the refusal\'s report, not retried: too many streams', async () => {
  const { clock, server, api } = setUp();
  server.script('GET', EVENTS, steps.report(errorReport('front.too_many_streams')));
  const answer = await api.get(EVENTS, { expect: 'stream' });
  assert.equal(answer.ok, false);
  assert.equal(answer.report.code, 'front.too_many_streams');
  await clock.advance(60_000);
  assert.equal(server.made('GET', EVENTS).length, 1);
});

test('a request said to be failing since a moment shows the line at once when that is 20 s ago', async () => {
  const { clock, server, api } = setUp();
  server.script('GET', EVENTS, steps.drop());
  const answer = api.get(EVENTS, { expect: 'stream', failingSince: clock.now() - 20_000 });
  await clock.advance(0);
  assert.equal(api.board.state().kind, 'slow');
  await clock.advance(1_000);
  assert.equal((await answer).ok, true);
  assert.equal(api.board.state().kind, 'none');
});

test('a request failing since a moment, answered at once, ends with the line gone', async () => {
  const { clock, api } = setUp();
  const answer = await api.get(EVENTS, { expect: 'stream', failingSince: clock.now() - 20_000 });
  assert.equal(answer.ok, true);
  assert.equal(api.board.state().kind, 'none');
});

test('a version heard on a stream is told as any answer\'s is', async () => {
  const { api } = setUp();
  const heard = [];
  api.onVersion((v) => heard.push(v));
  api.heard('20261201T000000Z-1111111');
  assert.deepEqual(heard, ['20261201T000000Z-1111111']);
});

test('the browser\'s own transport reads a stream piece by piece, and joins a character split between pieces', async () => {
  const original = globalThis.fetch;
  const pieces = [new TextEncoder().encode('event: version\n'), new Uint8Array([0xc2]), new Uint8Array([0xb0, 0x0a])];
  globalThis.fetch = async () => new Response(new ReadableStream({
    start(controller) { for (const p of pieces) controller.enqueue(p); controller.close(); },
  }), { status: 200, headers: { 'X-PenguinSlicer-Version': 'v', 'Content-Type': 'text/event-stream' } });
  try {
    const api = createApi({ transport: fetchTransport, clock: new FakeClock(), version: PAGE, random: () => 0.5 });
    const answer = await api.get(EVENTS, { expect: 'stream' });
    const got = [];
    await answer.stream.chunks((text) => got.push(text));
    assert.equal(got.join(''), 'event: version\n°\n');
  } finally {
    globalThis.fetch = original;
  }
});
