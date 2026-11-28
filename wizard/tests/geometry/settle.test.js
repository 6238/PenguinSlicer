// What the Layout step asks of the geometry beyond Arrange (wizard/README-details.md, "Laying an
// instance on a face", "Arrange"): the nearest free spot for one instance with every other
// where it stands, the turn that makes an instance too long for the plate fit, and settling an
// instance after a lay-down (it still fits; it is moved, turned if need be; it waits beside).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { placeNear, turnToFit, settleInstance } from '../../src/geometry/arrange.js';
import { checkPlate, placedOutlines, plateOf } from '../../src/geometry/placement.js';
import { convexHull } from '../../src/geometry/hull.js';
import { box } from './shapes.js';

const H2S = { min: [0, 0], max: [340, 320], height: 340 };
const plain = (supports = false) => plateOf(H2S, supports);

const block = (x, y, extra = {}) => ({ ref: 'block', orientation: '+z', angle: 0, x, y, ...extra });

function plate(instances, parts = { block: { name: 'Block' } }) {
  return { parts, instances };
}

const points = {
  block: convexHull(box(40, 40, 10).positions).points,
  rib: convexHull(box(353, 10, 10).positions).points,
  long: convexHull(box(450, 10, 10).positions).points,
  slab: convexHull(box(200, 200, 5).positions).points,
};

test('the nearest free spot keeps every other instance where it stands and passes the check', () => {
  const pc = plate([block(100, 100), block(105, 100), block(200, 200)]);
  const spot = placeNear(pc, points, plain(), 1, [105, 100]);
  assert.ok(spot, 'a free spot exists');
  const after = plate([block(100, 100), block(spot.x, spot.y), block(200, 200)]);
  assert.deepEqual(checkPlate(after, points, plain()), []);
  // Near where it stood: the closest spot is 45 mm from the first block's centre, 40 mm to the
  // right of where it stood; the map's squares and slack may add about a millimetre.
  const d = Math.hypot(spot.x - 105, spot.y - 100);
  assert.ok(d >= 39.9 && d < 42, `moved ${d} mm`);
});

test('with supports on the nearest free spot keeps 12 mm', () => {
  const pc = plate([block(100, 100), block(110, 100)]);
  const spot = placeNear(pc, points, plain(true), 1, [110, 100]);
  const after = plate([block(100, 100), block(spot.x, spot.y)]);
  assert.deepEqual(checkPlate(after, points, plain(true)), []);
});

test('no free spot: placeNear answers null', () => {
  const pc = plate([
    { ref: 'slab', orientation: '+z', angle: 0, x: 106, y: 106 },
    { ref: 'slab', orientation: '+z', angle: 0, x: 120, y: 120 },
  ], { slab: { name: 'Slab' } });
  assert.equal(placeNear(pc, points, plain(), 1, [120, 120]), null);
});

test('an instance that fits as it is turned needs no turn', () => {
  assert.deepEqual(turnToFit(block(0, 0), points, plain()), { fits: true, angle: 0 });
});

test('a 353 mm rib on a 340 by 320 mm plate fits only on the diagonal: an eighth of a turn', () => {
  // a quarter turn leaves it 353 mm front to back on a 314 mm frame; an eighth fits
  const rib = { ref: 'rib', orientation: '+z', angle: 0, x: 0, y: 0 };
  assert.deepEqual(turnToFit(rib, points, plain()), { fits: true, angle: 45 });
});

test('a part too long at every turn does not fit', () => {
  const long = { ref: 'long', orientation: '+z', angle: 0, x: 0, y: 0 };
  assert.deepEqual(turnToFit(long, points, plain()), { fits: false, angle: 0 });
});

test('settling an instance that still fits where it stood changes nothing', () => {
  const pc = plate([block(100, 100), block(200, 200)]);
  const outcome = settleInstance(pc, points, plain(), 1);
  assert.equal(outcome.how, 'fits');
  assert.deepEqual(outcome.instance, pc.instances[1]);
});

test('settling an instance that no longer fits moves it to the nearest free spot', () => {
  const pc = plate([block(100, 100), block(120, 100)]);
  const outcome = settleInstance(pc, points, plain(), 1);
  assert.equal(outcome.how, 'moved');
  assert.equal(outcome.instance.angle, 0);
  assert.deepEqual(checkPlate(plate([pc.instances[0], outcome.instance]), points, plain()), []);
});

test('settling an instance with no free spot leaves it beside the plate, to its right', () => {
  const pc = plate([
    { ref: 'slab', orientation: '+z', angle: 0, x: 106, y: 106 },
    { ref: 'slab', orientation: '+z', angle: 0, x: 120, y: 120 },
  ], { slab: { name: 'Slab' } });
  const outcome = settleInstance(pc, points, plain(), 1);
  assert.equal(outcome.how, 'beside');
  const [, placed] = placedOutlines(plate([pc.instances[0], outcome.instance], pc.parts), points);
  assert.ok(placed.bounds[0] > 340, `its left edge at ${placed.bounds[0]}`);
});

test('an instance left beside the plate too long as it lay waits turned to fit', () => {
  const pc = plate([
    { ref: 'slab', orientation: '+z', angle: 0, x: 106, y: 106 },
    { ref: 'slab', orientation: '+z', angle: 0, x: 230, y: 214 },
    { ref: 'rib', orientation: '+z', angle: 0, x: 170, y: 160 },
  ], { slab: { name: 'Slab' }, rib: { name: 'Rib' } });
  const outcome = settleInstance(pc, points, plain(), 2);
  assert.equal(outcome.how, 'beside');
  assert.equal(outcome.instance.angle, 45);
});

test('an instance moved to the nearest free spot is turned when that is what it takes', () => {
  // a rib lying across the plate, square: no spot fits it unturned, the diagonal does
  const pc = plate([{ ref: 'rib', orientation: '+z', angle: 0, x: 170, y: 160 }], { rib: { name: 'Rib' } });
  const outcome = settleInstance(pc, points, plain(), 0);
  assert.equal(outcome.how, 'turned');
  assert.equal(outcome.instance.angle, 45);
  assert.deepEqual(checkPlate(plate([outcome.instance], pc.parts), points, plain()), []);
});

test('the instances beside the plate wait one under another, never too close', () => {
  const parts = { slab: { name: 'Slab' } };
  const pc = plate([
    { ref: 'slab', orientation: '+z', angle: 0, x: 106, y: 106 },
    { ref: 'slab', orientation: '+z', angle: 0, x: 460, y: 103 },
    { ref: 'slab', orientation: '+z', angle: 0, x: 120, y: 120 },
  ], parts);
  const outcome = settleInstance(pc, points, plain(), 2);
  assert.equal(outcome.how, 'beside');
  const both = plate([pc.instances[1], outcome.instance], parts);
  assert.deepEqual([...new Set(checkPlate(both, points, plain()).map((p) => p.rule))], ['off_plate']);
});
