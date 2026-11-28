// The poses of the faces the wizard offers on the real parts
// (contracts/examples/placement/offered-faces/real-parts.json), which the slice service's
// real-Orca suite slices one by one as the oracle of the faces offered. The committed file must
// be exactly what the wizard's code writes (make -C wizard offered-faces), so that a change to
// the rules that changes what is offered changes the file, and the oracle slices the new poses.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { OFFERED_FACES_FILE, offeredFaces, offeredFacesText } from '../../scripts/offered-faces.js';
import { analysePart } from '../../src/geometry/part.js';
import { instanceMatrix } from '../../src/geometry/turn.js';
import { readRealPart } from './helpers.js';

const written = offeredFaces();

test('the committed poses are exactly what the wizard offers today', () => {
  assert.equal(readFileSync(OFFERED_FACES_FILE, 'utf8'), offeredFacesText(written));
});

test('every patch of every real part is one pose, and nothing else is', () => {
  const keys = Object.keys(written.parts);
  assert.equal(keys.length, 8);
  for (const key of keys) {
    const part = analysePart(readRealPart(`${key}.stl`));
    const poses = written.poses.filter((p) => p.instance.ref === key);
    assert.equal(poses.length, part.patches.length, key);
    assert.deepEqual(poses.map((p) => p.patch.index), part.patches.map((_, i) => i), key);
  }
});

test('each pose\'s instance has the contract\'s form and lays its patch on the plate', () => {
  for (const pose of written.poses) {
    const { instance, patch } = pose;
    assert.deepEqual(Object.keys(instance).sort(), ['angle', instance.rotation ? 'rotation' : 'orientation', 'ref', 'x', 'y'].sort());
    assert.ok(Object.hasOwn(written.parts, instance.ref));
    assert.equal(instance.angle, 0);
    if (instance.rotation) {
      assert.equal(instance.rotation.length, 4);
      assert.ok(Math.abs(Math.hypot(...instance.rotation) - 1) <= 1e-6);
    }
    const m = instanceMatrix(instance);
    const down = m.map((row) => row[0] * patch.normal[0] + row[1] * patch.normal[1] + row[2] * patch.normal[2]);
    assert.ok(Math.abs(down[0]) < 1e-5 && Math.abs(down[1]) < 1e-5 && Math.abs(down[2] + 1) < 1e-5, `${pose.id}: ${down}`);
  }
});

test('each pose has its own id, its part\'s ranks, and the part named as the contract names a part', () => {
  const ids = written.poses.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const [key, part] of Object.entries(written.parts)) {
    assert.deepEqual(Object.keys(part), ['name', 'sha256', 'units']);
    assert.match(part.sha256, /^[0-9a-f]{64}$/);
    assert.equal(part.units, 'mm');
    const ranks = written.poses.filter((p) => p.instance.ref === key).map((p) => p.orient_rank).sort((a, b) => a - b);
    assert.deepEqual(ranks, ranks.map((_, i) => i + 1), key);
    const sizes = written.poses.filter((p) => p.instance.ref === key).map((p) => p.area_rank).sort((a, b) => a - b);
    assert.deepEqual(sizes, sizes.map((_, i) => i + 1), key);
  }
});
