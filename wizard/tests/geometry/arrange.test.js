// Arrange: every instance placed in a compact pile about the plate's middle, at the spacing the
// settings ask for, never turned (wizard/README-details.md, "Arrange and the placement check").
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { arrangePlate } from '../../src/geometry/arrange.js';
import { checkPlate, placedOutlines, plateOf } from '../../src/geometry/placement.js';
import { bounds } from '../../src/geometry/outline.js';
import { convexHull } from '../../src/geometry/hull.js';
import { box, cylinder, prism } from './shapes.js';
import { readMadePart } from './helpers.js';

const H2S = { min: [0, 0], max: [340, 320], height: 340 };
const plain = (supports = false) => plateOf(H2S, supports);

function plateOfMany(ref, count, extra = {}) {
  return {
    parts: { [ref]: { name: ref } },
    instances: Array.from({ length: count }, () => ({ ref, orientation: '+z', angle: 0, x: 0, y: 0, ...extra })),
  };
}

function pileBounds(pc, points, placedFlags) {
  const outlines = placedOutlines({ ...pc, instances: pc.instances.filter((_, i) => placedFlags[i]) }, points);
  const all = outlines.flatMap((o) => o.hull);
  return bounds(all);
}

test('one instance goes to the plate\'s middle', () => {
  const points = { block: convexHull(box(40, 20, 10).positions).points };
  const result = arrangePlate(plateOfMany('block', 1), points, plain());
  assert.deepEqual(result.placed, [true]);
  const [x0, y0, x1, y1] = pileBounds(result.plateConfiguration, points, result.placed);
  assert.ok(Math.abs((x0 + x1) / 2 - 170) < 1e-6 && Math.abs((y0 + y1) / 2 - 160) < 1e-6);
});

test('150 spacers all fit, and the plate passes the placement check', () => {
  const points = { spacer: convexHull(readMadePart('hex-spacer.stl').positions).points };
  const result = arrangePlate(plateOfMany('spacer', 150), points, plain());
  assert.equal(result.placed.filter(Boolean).length, 150);
  assert.deepEqual(checkPlate(result.plateConfiguration, points, plain()), []);
});

test('with supports on the instances are spaced 12 mm, and the plate passes', () => {
  const points = { block: convexHull(box(30, 30, 10).positions).points };
  const result = arrangePlate(plateOfMany('block', 20), points, plain(true));
  assert.equal(result.placed.filter(Boolean).length, 20);
  assert.deepEqual(checkPlate(result.plateConfiguration, points, plain(true)), []);
  // At 5 mm they would be too close for supports: the check with 12 mm is the one that passed.
});

test('the pile sits about the plate\'s middle', () => {
  const points = { block: convexHull(box(30, 20, 10).positions).points };
  const result = arrangePlate(plateOfMany('block', 12), points, plain());
  const [x0, y0, x1, y1] = pileBounds(result.plateConfiguration, points, result.placed);
  assert.ok(Math.abs((x0 + x1) / 2 - 170) < 1e-6);
  assert.ok(Math.abs((y0 + y1) / 2 - 160) < 1e-6);
});

test('Arrange never turns an instance: a 37 degree instance is still at 37 degrees', () => {
  const points = { rib: convexHull(prism([[0, 0], [120, 0], [120, 15], [0, 30]], 0, 8).positions).points };
  const pc = plateOfMany('rib', 6, { angle: 37 });
  pc.instances[2] = { ref: 'rib', rotation: [0.9238795325, 0.3826834324, 0, 0], angle: 200, x: 5, y: 5 };
  const result = arrangePlate(pc, points, plain());
  result.plateConfiguration.instances.forEach((instance, i) => {
    const { x, y, ...turn } = instance;
    const { x: _x, y: _y, ...before } = pc.instances[i];
    assert.deepEqual(turn, before);
  });
  assert.deepEqual(checkPlate(result.plateConfiguration, points, plain()), []);
});

test('what does not fit waits beside the plate, and what fits passes the check', () => {
  const points = { slab: convexHull(box(100, 100, 5).positions).points };
  const result = arrangePlate(plateOfMany('slab', 12), points, plain());
  const placed = result.placed.filter(Boolean).length;
  assert.ok(placed >= 6 && placed < 12, `placed ${placed}`);
  const onPlate = { ...result.plateConfiguration, instances: result.plateConfiguration.instances.filter((_, i) => result.placed[i]) };
  assert.deepEqual(checkPlate(onPlate, points, plain()), []);
  // Those left wait to the right of the plate, clear of it.
  result.plateConfiguration.instances.forEach((instance, i) => {
    if (!result.placed[i]) assert.ok(instance.x - 50 > 340, `instance ${i} at x ${instance.x}`);
  });
});

test('an instance too long for the plate as it is turned is left beside it', () => {
  const points = { rib: convexHull(box(353, 10, 10).positions).points, block: convexHull(box(20, 20, 20).positions).points };
  const pc = {
    parts: { rib: { name: 'Rib' }, block: { name: 'Block' } },
    instances: [{ ref: 'rib', orientation: '+z', angle: 0, x: 0, y: 0 }, { ref: 'block', orientation: '+z', angle: 0, x: 0, y: 0 }],
  };
  const result = arrangePlate(pc, points, plain());
  assert.deepEqual(result.placed, [false, true]);
});

test('largest first: a mix of parts packs every instance, the large ones and the small', () => {
  const points = {
    disc: convexHull(cylinder(64, 40, 6).positions).points,
    block: convexHull(box(60, 25, 10).positions).points,
    pin: convexHull(box(8, 8, 30).positions).points,
  };
  const instances = [];
  for (let i = 0; i < 4; i++) instances.push({ ref: 'disc', orientation: '+z', angle: 0, x: 0, y: 0 });
  for (let i = 0; i < 10; i++) instances.push({ ref: 'block', orientation: '+z', angle: 45, x: 0, y: 0 });
  for (let i = 0; i < 40; i++) instances.push({ ref: 'pin', orientation: '+z', angle: 0, x: 0, y: 0 });
  const pc = { parts: { disc: { name: 'Disc' }, block: { name: 'Block' }, pin: { name: 'Pin' } }, instances };
  const result = arrangePlate(pc, points, plain());
  assert.equal(result.placed.filter(Boolean).length, 54);
  assert.deepEqual(checkPlate(result.plateConfiguration, points, plain()), []);
});

test('the two packers both run and the better is kept', () => {
  const points = { block: convexHull(box(30, 20, 10).positions).points };
  const result = arrangePlate(plateOfMany('block', 30), points, plain());
  assert.ok(['shelf', 'pile'].includes(result.packer));
  assert.equal(result.tried.length, 2);
  const kept = result.tried.find((t) => t.packer === result.packer);
  for (const other of result.tried) {
    assert.ok(kept.placed > other.placed || (kept.placed === other.placed && kept.area <= other.area));
  }
});
