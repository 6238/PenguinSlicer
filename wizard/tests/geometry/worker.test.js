// The worker's messages, run in the test's own thread through the same messages the page posts
// (wizard/README-details.md, "The project and its tools": the worker is run in the same thread
// by the tests).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';

import { createGeometry } from '../../src/geometry/messages.js';
import { fileBuffer, REAL_PARTS, MADE_PARTS } from './helpers.js';

const H2S = { min: [0, 0], max: [340, 320], height: 340 };

function ask(geometry, message) {
  const { reply, transfer } = geometry.handle(message);
  assert.equal(reply.id, message.id);
  return { reply, transfer };
}

test('a part is read, its faces found and its best way chosen, each by one message', () => {
  const g = createGeometry();
  const read = ask(g, { id: 1, op: 'read', key: 'pulley', buffer: fileBuffer(join(REAL_PARTS, 'pulley-v3.stl')), units: 'mm' });
  assert.equal(read.reply.ok, true);
  assert.equal(read.reply.result.triangles, 4608);
  // The drawing's corners go back as a transferable buffer, not copied.
  assert.ok(read.reply.result.positions instanceof Float32Array);
  assert.deepEqual(read.transfer, [read.reply.result.positions.buffer]);
  const faces = ask(g, { id: 2, op: 'faces', key: 'pulley' }).reply;
  assert.equal(faces.ok, true);
  assert.equal(faces.result.patches.length, 6);
  const orient = ask(g, { id: 3, op: 'orient', key: 'pulley' }).reply;
  assert.equal(orient.ok, true);
  assert.ok('orientation' in orient.result.turn);
});

test('the faces are found once for each part: asking again answers from what was found', () => {
  const g = createGeometry();
  ask(g, { id: 1, op: 'read', key: 'spacer', buffer: fileBuffer(join(MADE_PARTS, 'hex-spacer.stl')), units: 'mm' });
  const first = ask(g, { id: 2, op: 'faces', key: 'spacer' }).reply.result;
  const second = ask(g, { id: 3, op: 'faces', key: 'spacer' }).reply.result;
  assert.equal(first.computed, true);
  assert.equal(second.computed, false);
  assert.deepEqual(second.patches, first.patches);
});

test('a malformed STL ends in an error report the main thread shows as a notification', () => {
  const g = createGeometry();
  const buffer = new ArrayBuffer(100);
  new DataView(buffer).setUint32(80, 1, true);
  const { reply } = ask(g, { id: 7, op: 'read', key: 'bad', buffer, units: 'mm' });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'wizard.part_not_drawable');
  assert.match(reply.error.detail, /100 bytes/);
});

test('a flat part is read, and its faces end in an error report, not an exception', () => {
  const g = createGeometry();
  const buffer = new ArrayBuffer(84 + 50);
  const view = new DataView(buffer);
  view.setUint32(80, 1, true);
  [0, 0, 0, 1, 0, 0, 0, 1, 0].forEach((v, k) => view.setFloat32(96 + 4 * k, v, true));
  assert.equal(ask(g, { id: 1, op: 'read', key: 'flat', buffer, units: 'mm' }).reply.ok, true);
  const { reply } = ask(g, { id: 2, op: 'faces', key: 'flat' });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'wizard.part_not_drawable');
});

test('a part never read, or a message the worker does not know, is the page\'s fault, reported as one', () => {
  const g = createGeometry();
  for (const message of [{ id: 1, op: 'faces', key: 'nobody' }, { id: 2, op: 'paint', key: 'x' }]) {
    const { reply } = ask(g, message);
    assert.equal(reply.ok, false);
    assert.equal(reply.error.code, 'wizard.layout_failed');
    assert.ok(reply.error.detail.length > 0);
  }
});

test('a read in units other than mm or in is the page\'s fault, reported through the messages as one', () => {
  const g = createGeometry();
  const { reply } = ask(g, { id: 4, op: 'read', key: 'spacer', buffer: fileBuffer(join(MADE_PARTS, 'hex-spacer.stl')), units: 'cm' });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, 'wizard.layout_failed');
  assert.equal(reply.error.retryable, true);
  assert.match(reply.error.detail, /units must be "mm" or "in", not "cm"/);
  // Nothing was read under the key.
  assert.equal(ask(g, { id: 5, op: 'faces', key: 'spacer' }).reply.error.code, 'wizard.layout_failed');
  assert.match(ask(g, { id: 6, op: 'faces', key: 'spacer' }).reply.error.detail, /no part was read/);
});

test('Arrange and the placement check run on parts the worker has read', () => {
  const g = createGeometry();
  ask(g, { id: 1, op: 'read', key: 'spacer-key', buffer: fileBuffer(join(MADE_PARTS, 'hex-spacer.stl')), units: 'mm' });
  const plateConfiguration = {
    parts: { spacer: { name: 'Spacer' } },
    instances: Array.from({ length: 20 }, () => ({ ref: 'spacer', orientation: '+z', angle: 0, x: 0, y: 0 })),
  };
  const geometry = { spacer: 'spacer-key' };
  const arranged = ask(g, { id: 2, op: 'arrange', plateConfiguration, geometry, printer: H2S, supports: false }).reply;
  assert.equal(arranged.ok, true);
  assert.equal(arranged.result.placed.filter(Boolean).length, 20);
  const checked = ask(g, { id: 3, op: 'check', plateConfiguration: arranged.result.plateConfiguration, geometry, printer: H2S, supports: false }).reply;
  assert.deepEqual(checked.result.problems, []);
  const crowded = ask(g, { id: 4, op: 'check', plateConfiguration, geometry, printer: H2S, supports: false }).reply;
  assert.equal(crowded.result.problems[0].rule, 'off_plate');
});

test('the placement check follows the part each part key points at, never a footprint of the part it pointed at before', () => {
  // The same part key first points at the spacer read in millimetres, then at it read in
  // inches (25.4 times larger), then the key it was read under is read again in inches.
  const spacer = () => fileBuffer(join(MADE_PARTS, 'hex-spacer.stl'));
  const plateConfiguration = {
    parts: { p: { name: 'Spacer' } },
    instances: [
      { ref: 'p', orientation: '+z', angle: 0, x: 100, y: 160 },
      { ref: 'p', orientation: '+z', angle: 0, x: 200, y: 160 },
    ],
  };
  const check = (g, id, key) => ask(g, { id, op: 'check', plateConfiguration, geometry: { p: key }, printer: H2S, supports: false }).reply.result.problems;
  const fresh = (units) => {
    const f = createGeometry();
    ask(f, { id: 1, op: 'read', key: 'k', buffer: spacer(), units });
    return check(f, 2, 'k');
  };
  const inMm = fresh('mm');
  const inInches = fresh('in');
  assert.deepEqual(inMm, []);
  assert.deepEqual(inInches.map((p) => p.rule), ['off_plate', 'off_plate', 'too_close']);

  const g = createGeometry();
  ask(g, { id: 1, op: 'read', key: 'spacer-mm', buffer: spacer(), units: 'mm' });
  ask(g, { id: 2, op: 'read', key: 'spacer-in', buffer: spacer(), units: 'in' });
  assert.deepEqual(check(g, 3, 'spacer-mm'), inMm);
  assert.deepEqual(check(g, 4, 'spacer-in'), inInches);
  assert.deepEqual(check(g, 5, 'spacer-mm'), inMm);
  // One read key read again, without a forget between, in other units.
  ask(g, { id: 6, op: 'read', key: 'spacer-mm', buffer: spacer(), units: 'in' });
  assert.deepEqual(check(g, 7, 'spacer-mm'), inInches);
});

test('forgetting a part lets its memory go; asking about it after is the page\'s fault', () => {
  const g = createGeometry();
  ask(g, { id: 1, op: 'read', key: 'spacer', buffer: fileBuffer(join(MADE_PARTS, 'hex-spacer.stl')), units: 'mm' });
  assert.equal(ask(g, { id: 2, op: 'forget', key: 'spacer' }).reply.ok, true);
  assert.equal(ask(g, { id: 3, op: 'faces', key: 'spacer' }).reply.error.code, 'wizard.layout_failed');
});
