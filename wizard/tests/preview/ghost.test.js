// The ghost of what is still to print (src/preview/ghost.js): each instance's part placed on the
// plate by the plate configuration's one transform, p_plate = Rz(angle) M p_part + t
// (contracts/plate-configuration.md, "Coordinates" and "An instance in phase 2"), from the part's
// corners as the geometry client gives them for drawing (already in millimetres).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { placeInstances } from '../../src/preview/ghost.js';
import { PREVIEW_FAILED, PreviewError } from '../../src/preview/preview-errors.js';
import { corners } from './helpers.js';

// One triangle spanning x 0..10, y 0..4, z 2..6.
const triangle = corners([[0, 0, 2, 10, 0, 2, 10, 4, 6]]);
const round = (a) => [...a].map((v) => +v.toFixed(4) + 0);

test('an instance is placed as the contract places it: turned, its footprint centre moved, its lowest point on the plate', () => {
  // +z, turned 90 degrees, footprint centre (5, 2) to (100, 50), lowest z (2) to 0.
  const { corners: placed } = placeInstances({ instances: [{ ref: 'a', orientation: '+z', angle: 90, x: 100, y: 50 }], meshes: { a: triangle } });
  assert.deepEqual(round(placed), [102, 45, 0, 102, 55, 0, 98, 55, 4]);
  // -z: y and z change sign: y 0..-4, z -2..-6, so the footprint centre is (5, -2) and the lowest z -6.
  const flipped = placeInstances({ instances: [{ ref: 'a', orientation: '-z', angle: 0, x: 0, y: 0 }], meshes: { a: triangle } });
  assert.deepEqual(round(flipped.corners), [-5, 2, 4, 5, 2, 4, 5, -2, 0]);
});

test('a general rotation is turned by its quaternion\'s matrix, as the contract writes it', () => {
  // A quarter turn about x, [cos 45, sin 45, 0, 0]: (x, y, z) to (x, -z, y), the same as +y.
  const h = Math.SQRT1_2;
  const byRotation = placeInstances({ instances: [{ ref: 'a', rotation: [h, h, 0, 0], angle: 0, x: 20, y: 30 }], meshes: { a: triangle } });
  const byOrientation = placeInstances({ instances: [{ ref: 'a', orientation: '+y', angle: 0, x: 20, y: 30 }], meshes: { a: triangle } });
  assert.deepEqual(round(byRotation.corners), round(byOrientation.corners));
});

test('every instance of the plate is in the ghost, each with its bounds', () => {
  const unit = corners([[0, 0, 0, 1, 0, 0, 0, 1, 1]]);
  const ghost = placeInstances({ instances: [{ ref: 'a', orientation: '+z', angle: 0, x: 10, y: 10 }, { ref: 'a', orientation: '+z', angle: 0, x: 30, y: 10 }], meshes: { a: unit } });
  assert.equal(ghost.corners.length, 18);
  assert.equal(ghost.corners[9], 29.5);
  assert.deepEqual([...ghost.bounds], [9.5, 9.5, 0, 10.5, 10.5, 1, 29.5, 9.5, 0, 30.5, 10.5, 1]);
});

test('an instance whose part has no corners, or no turn the contract knows, is the page\'s own fault', () => {
  const fault = (plate, detail) => assert.throws(() => placeInstances(plate), (error) => {
    assert.ok(error instanceof PreviewError);
    assert.equal(error.report.code, PREVIEW_FAILED);
    assert.match(error.report.detail, detail);
    return true;
  });
  fault({ instances: [{ ref: 'b', orientation: '+z', angle: 0, x: 0, y: 0 }], meshes: { a: triangle } }, /instance 0 names the part "b", whose corners the preview was not given/);
  fault({ instances: [{ ref: 'a', orientation: 'up', angle: 0, x: 0, y: 0 }], meshes: { a: triangle } }, /instance 0 has no orientation or rotation the contract knows/);
  fault({ instances: [{ ref: 'a', angle: 0, x: 0, y: 0 }], meshes: { a: triangle } }, /instance 0 has no orientation or rotation/);
});

test('no plate is no ghost: the preview draws the toolpaths alone', () => {
  const ghost = placeInstances(null);
  assert.equal(ghost.corners.length, 0);
  assert.equal(ghost.bounds.length, 0);
});
