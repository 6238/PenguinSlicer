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

test('an instance the slice service would refuse as malformed is the page\'s fault, never a plate that passes', () => {
  // The forms the contract refuses (slice.bad_plate_configuration): the wizard would otherwise
  // show such a plate green.
  const g = createGeometry();
  ask(g, { id: 1, op: 'read', key: 'spacer-key', buffer: fileBuffer(join(MADE_PARTS, 'hex-spacer.stl')), units: 'mm' });
  const good = { ref: 'spacer', orientation: '+z', angle: 0, x: 170, y: 160 };
  const { orientation, ...bare } = good;
  const bad = {
    'x not a number': { ...good, x: NaN },
    'y infinite': { ...good, y: Infinity },
    'x a string': { ...good, x: '170' },
    'angle a fraction': { ...good, angle: 10.5 },
    'angle 360': { ...good, angle: 360 },
    'an unknown orientation': { ...good, orientation: 'up' },
    'neither orientation nor rotation': bare,
    'both orientation and rotation': { ...good, rotation: [1, 0, 0, 0] },
    'a rotation of zero length': { ...bare, rotation: [0, 0, 0, 0] },
    'a rotation of three elements': { ...bare, rotation: [1, 0, 0] },
    'a rotation not of unit length': { ...bare, rotation: [1.00001, 0, 0, 0] },
    'a rotation with NaN': { ...bare, rotation: [NaN, 0, 0, 0] },
    'a ref to no part': { ...good, ref: 'washer' },
    'a ref to a part the worker was not told of': { ...good, ref: 'pulley' },
    'a ref inherited by every object': { ...good, ref: 'toString' },
  };
  const geometry = { spacer: 'spacer-key' };
  let id = 2;
  for (const [what, instance] of Object.entries(bad)) {
    const plateConfiguration = { parts: { spacer: { name: 'Spacer' }, pulley: { name: 'Pulley' } }, instances: [good, instance] };
    for (const op of ['check', 'arrange']) {
      const { reply } = ask(g, { id: id++, op, plateConfiguration, geometry, printer: H2S, supports: false });
      assert.equal(reply.ok, false, `${op}: ${what}`);
      assert.equal(reply.error.code, 'wizard.layout_failed', `${op}: ${what}`);
      assert.match(reply.error.detail, /instance 1/, `${op}: ${what}`);
    }
  }
  // A rotation within a millionth of unit length, as the page sends it, is fine.
  const sent = { ...bare, rotation: [0.628064719, -0.324861061, -0.628064719, -0.324861061] };
  const { reply } = ask(g, { id: id++, op: 'check', plateConfiguration: { parts: { spacer: { name: 'Spacer' } }, instances: [sent] }, geometry, printer: H2S, supports: false });
  assert.deepEqual(reply.result.problems, []);
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

test('the check gives each instance\'s footprint bounds and height, for the Layout step\'s drawing and lines', () => {
  const g = createGeometry();
  ask(g, { id: 1, op: 'read', key: 'spacer-key', buffer: fileBuffer(join(MADE_PARTS, 'hex-spacer.stl')), units: 'mm' });
  const plateConfiguration = { parts: { spacer: { name: 'Spacer' } }, instances: [{ ref: 'spacer', orientation: '+z', angle: 0, x: 100, y: 50 }] };
  const { result } = ask(g, { id: 2, op: 'check', plateConfiguration, geometry: { spacer: 'spacer-key' }, printer: H2S, supports: false }).reply;
  const [[x0, y0, x1, y1]] = result.bounds;
  // The spacer is 5/8 inch across (15.875 mm) and 1/8 inch thick (3.175 mm).
  assert.ok(Math.abs(x1 - x0 - 15.875) < 0.01 && Math.abs((x0 + x1) / 2 - 100) < 1e-6 && Math.abs((y0 + y1) / 2 - 50) < 1e-6);
  assert.ok(Math.abs(result.heights[0] - 3.175) < 1e-3);
});

test('settle and fit answer through the messages, and a malformed instance is the page\'s fault', () => {
  const g = createGeometry();
  ask(g, { id: 1, op: 'read', key: 'spacer-key', buffer: fileBuffer(join(MADE_PARTS, 'hex-spacer.stl')), units: 'mm' });
  const geometry = { spacer: 'spacer-key' };
  const plateConfiguration = {
    parts: { spacer: { name: 'Spacer' } },
    instances: [{ ref: 'spacer', orientation: '+z', angle: 0, x: 100, y: 50 }, { ref: 'spacer', orientation: '+z', angle: 0, x: 102, y: 50 }],
  };
  const settled = ask(g, { id: 2, op: 'settle', plateConfiguration, geometry, printer: H2S, supports: false, index: 1 }).reply;
  assert.equal(settled.ok, true);
  assert.equal(settled.result.how, 'moved');
  const fit = ask(g, { id: 3, op: 'fit', plateConfiguration, geometry, printer: H2S, supports: false, index: 0 }).reply;
  assert.deepEqual(fit.result, { fits: true, angle: 0 });
  for (const [id, index] of [[4, 2], [5, -1], [6, 0.5]]) {
    const { reply } = ask(g, { id, op: 'settle', plateConfiguration, geometry, printer: H2S, supports: false, index });
    assert.equal(reply.error.code, 'wizard.layout_failed');
    assert.match(reply.error.detail, /index/);
  }
});

test('forgetting a part lets its memory go; asking about it after is the page\'s fault', () => {
  const g = createGeometry();
  ask(g, { id: 1, op: 'read', key: 'spacer', buffer: fileBuffer(join(MADE_PARTS, 'hex-spacer.stl')), units: 'mm' });
  assert.equal(ask(g, { id: 2, op: 'forget', key: 'spacer' }).reply.ok, true);
  assert.equal(ask(g, { id: 3, op: 'faces', key: 'spacer' }).reply.error.code, 'wizard.layout_failed');
});
