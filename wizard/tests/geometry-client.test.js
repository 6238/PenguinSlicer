// The main thread's side of the worker (src/geometry-client.js, src/part-picture.js and
// src/hold-meter.js; wizard/README-details.md, "The geometry, in a worker"): each question asked
// by one message and answered by its own reply, whatever the order; a part's bytes copied to the
// worker and never taken from the page; a worker that fails answering every question waiting with
// the wizard's own report; the size of a part's picture; the heartbeat that measures the longest
// hold of the main thread.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';

import { createGeometryClient } from '../src/geometry-client.js';
import { HEARTBEAT_MS, createHoldMeter } from '../src/hold-meter.js';
import { PART_COLOURS, PICTURE_CSS_PX } from '../src/page-constants.js';
import { partColour, picturePx } from '../src/part-picture.js';
import { fileBuffer, REAL_PARTS } from './geometry/helpers.js';
import { FakeClock } from './fakes/clock.js';
import { InThreadWorker } from './fakes/worker.js';

const pulley = () => fileBuffer(join(REAL_PARTS, 'pulley-v3.stl'));

test('a part is read and its picture drawn, each by one question to the worker', async () => {
  const worker = new InThreadWorker();
  const geometry = createGeometryClient(worker.port);
  const read = await geometry.read('p-1', pulley(), 'mm');
  assert.equal(read.ok, true);
  assert.equal(read.result.triangles, 4608);
  const picture = await geometry.picture('p-1', 88, PART_COLOURS[0]);
  assert.equal(picture.ok, true);
  assert.equal(picture.result.width, 88);
  assert.equal(picture.result.pixels.length, 88 * 88 * 4);
  assert.deepEqual(worker.posted.map((p) => p.message.op), ['read', 'picture']);
});

test('a part read is kept for the Layout view\'s drawing until it is forgotten; one the worker could not read is not', async () => {
  const worker = new InThreadWorker();
  const geometry = createGeometryClient(worker.port);
  assert.equal(geometry.mesh('p-1'), null);
  await geometry.read('p-1', pulley(), 'mm');
  assert.equal(geometry.mesh('p-1').positions.length, 4608 * 9);
  await geometry.read('bad', new ArrayBuffer(10), 'mm');
  assert.equal(geometry.mesh('bad'), null);
  await geometry.forget('p-1');
  assert.equal(geometry.mesh('p-1'), null);
});

test('the part\'s bytes are copied to the worker, never taken from the page', async () => {
  const worker = new InThreadWorker();
  const geometry = createGeometryClient(worker.port);
  const bytes = pulley();
  await geometry.read('p-1', bytes, 'mm');
  assert.deepEqual(worker.posted[0].transfer, []);
  assert.equal(bytes.byteLength, 84 + 50 * 4608);
});

test('each reply answers its own question, in whatever order the replies come', async () => {
  const worker = new InThreadWorker();
  const geometry = createGeometryClient(worker.port);
  await geometry.read('p-1', pulley(), 'mm');
  worker.hold();
  const big = geometry.picture('p-1', 96, PART_COLOURS[0]);
  const small = geometry.picture('p-1', 32, PART_COLOURS[1]);
  const [a, b] = worker.holding.splice(0, 2);
  worker.holding.push(b, a);                       // the second question's reply first
  worker.release();
  assert.equal((await big).result.width, 96);
  assert.equal((await small).result.width, 32);
});

test('a malformed STL is answered with the worker\'s report, wizard.part_not_drawable', async () => {
  const worker = new InThreadWorker();
  const geometry = createGeometryClient(worker.port);
  const buffer = new ArrayBuffer(100);
  new DataView(buffer).setUint32(80, 1, true);
  const read = await geometry.read('bad', buffer, 'mm');
  assert.equal(read.ok, false);
  assert.equal(read.error.code, 'wizard.part_not_drawable');
  assert.equal(read.error.message, 'PenguinSlicer could not show this part, so it cannot be imported.');
});

test('a worker that fails as a whole answers every question waiting with wizard.layout_failed, and every later one', async () => {
  const worker = new InThreadWorker();
  const geometry = createGeometryClient(worker.port);
  worker.hold();
  const waiting = geometry.read('p-1', pulley(), 'mm');
  worker.fail({ message: 'Failed to load the worker script' });
  const answer = await waiting;
  assert.equal(answer.ok, false);
  assert.equal(answer.error.code, 'wizard.layout_failed');
  assert.match(answer.error.detail, /Failed to load the worker script/);
  const later = await geometry.picture('p-1', 88, PART_COLOURS[0]);
  assert.equal(later.ok, false);
  assert.equal(later.error.code, 'wizard.layout_failed');
});

test('a worker that fails as a whole sends one layout_failed report to the server\'s log, however often it fails', async () => {
  const worker = new InThreadWorker();
  const reports = [];
  const geometry = createGeometryClient(worker.port, { report: (what, fields) => reports.push({ what, ...fields }) });
  worker.hold();
  const waiting = geometry.read('p-1', pulley(), 'mm');
  worker.fail({ message: 'Failed to load the worker script' });
  worker.fail({ message: 'a second error event' });
  await waiting;
  await geometry.picture('p-1', 88, PART_COLOURS[0]);
  assert.deepEqual(reports, [{ what: 'layout_failed', detail: 'the worker failed: Failed to load the worker script' }]);
});

// The worker's answer tells its own failure from the page asking wrongly, and the client reports
// each once: layout_failed when the geometry's code failed on a part, page_failed when the page
// asked for something wrong; a part it cannot read is the Parts step's part_not_drawable.
const SHA = 'a'.repeat(64);

test('a question the page asked wrongly is reported as page_failed, naming the part by its hash', async () => {
  const worker = new InThreadWorker();
  const reports = [];
  const geometry = createGeometryClient(worker.port, { report: (what, fields) => reports.push({ what, ...fields }) });
  const answer = await geometry.faces(`${SHA}.mm`);
  assert.equal(answer.ok, false);
  assert.equal(answer.error.code, 'wizard.layout_failed');
  assert.deepEqual(reports, [{ what: 'page_failed', part_sha256: SHA, detail: `faces: ${answer.error.detail}` }]);
  const unknown = await geometry.ask('nothing-of-the-sort');
  assert.equal(unknown.ok, false);
  assert.equal(reports.at(-1).what, 'page_failed');
  assert.equal('part_sha256' in reports.at(-1), false, 'no part concerned');
});

test('the geometry\'s code failing on a part is reported as layout_failed, the worker still answering', async () => {
  const worker = new InThreadWorker();
  const reports = [];
  const geometry = createGeometryClient(worker.port, { report: (what, fields) => reports.push({ what, ...fields }) });
  // a buffer that is no ArrayBuffer: the reading's own code throws, an error it did not foresee
  const answer = await geometry.read(`${SHA}.in`, 'not bytes', 'in');
  assert.equal(answer.ok, false);
  assert.equal(answer.error.code, 'wizard.layout_failed');
  assert.equal(reports.length, 1);
  assert.equal(reports[0].what, 'layout_failed');
  assert.equal(reports[0].part_sha256, SHA);
  assert.match(reports[0].detail, /^read: TypeError: /);
  assert.equal((await geometry.read('p-1', pulley(), 'mm')).ok, true, 'the worker goes on answering');
});

test('a part the worker cannot read is not reported by the client: the Parts step reports it as part_not_drawable', async () => {
  const worker = new InThreadWorker();
  const reports = [];
  const geometry = createGeometryClient(worker.port, { report: (what, fields) => reports.push({ what, ...fields }) });
  await geometry.read(`${SHA}.mm`, new ArrayBuffer(10), 'mm');
  assert.deepEqual(reports, []);
});

test('a part\'s picture is drawn at the row\'s 44 px times the screen\'s density, up to three', () => {
  assert.equal(PICTURE_CSS_PX, 44);
  assert.equal(picturePx(1), 44);
  assert.equal(picturePx(2), 88);
  assert.equal(picturePx(1.5), 66);
  assert.equal(picturePx(4), 132);
  assert.equal(picturePx(0.5), 44);
  assert.equal(picturePx(undefined), 44);
});

test('the parts\' colours are the mockup\'s, in turn', () => {
  assert.deepEqual(PART_COLOURS, [0x9fb4c8, 0xb7a6d6, 0x9cc9b0, 0xd6c08f, 0xc9a0a0, 0x8fc3d6, 0xb0b0b0]);
  assert.equal(partColour(0), 0x9fb4c8);
  assert.equal(partColour(7), 0x9fb4c8);
  assert.equal(partColour(9), 0x9cc9b0);
});

// ---- the heartbeat

// A clock whose timers fire only when the test says, late if the test says so: a held main
// thread is a beat that comes late.
function lateClock() {
  const clock = { t: 0, due: null, now: () => clock.t, after: (ms, fn) => { clock.due = { at: clock.t + ms, fn }; return 1; }, cancel: () => { clock.due = null; } };
  clock.beat = (late = 0) => { const { at, fn } = clock.due; clock.t = at + late; fn(); };
  return clock;
}

test('the heartbeat beats every 10 ms and measures the longest gap between two beats', () => {
  assert.equal(HEARTBEAT_MS, 10);
  const clock = lateClock();
  const meter = createHoldMeter(clock);
  meter.start();
  clock.beat();
  clock.beat();
  assert.equal(meter.longest(), 10);
  clock.beat(240);                        // the main thread held for 240 ms: a gap of 250
  clock.beat();
  assert.equal(meter.longest(), 250);
  assert.equal(meter.stop(), 250);
  assert.equal(clock.due, null);          // stopped: no timer left
});

test('a hold after the last beat and before stop is counted: the open gap is a gap', () => {
  const clock = lateClock();
  const meter = createHoldMeter(clock);
  meter.start();
  clock.beat();
  clock.beat();
  clock.t += 400;                         // the thread held for 400 ms; the next beat never came
  assert.equal(meter.longest(), 400);
  assert.equal(meter.stop(), 400);
  assert.equal(meter.longest(), 400);     // stopped: the figure stays as it was at the stop
  clock.t += 1000;
  assert.equal(meter.longest(), 400);
});

test('starting the heartbeat again measures afresh', async () => {
  const clock = new FakeClock();
  const meter = createHoldMeter(clock);
  meter.start();
  await clock.advance(1000);
  assert.equal(meter.stop(), HEARTBEAT_MS);
  meter.start();
  assert.equal(meter.longest(), 0);
  meter.stop();
  assert.equal(clock.pending, 0);
});
