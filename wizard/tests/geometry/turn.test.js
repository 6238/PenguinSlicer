// An instance's turn: the rotation that lays it down, as a unit quaternion, and how the plate
// configuration carries it (contracts/plate-configuration.md, "An instance in phase 2").
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  ORIENTATION_MATRICES, instanceMatrix, instanceTurn, layOnFace, matrixOfQuaternion, rotateVector,
  shortestRotation,
} from '../../src/geometry/turn.js';

const close = (a, b, tol = 1e-9) => a.every((v, i) => Math.abs(v - b[i]) <= tol);
const closeM = (a, b, tol = 1e-9) => a.every((row, i) => close(row, b[i], tol));

test('the matrix of a quaternion is the contract\'s, row-major', () => {
  // A quarter turn about z: x goes to y.
  const s = Math.SQRT1_2;
  assert.ok(closeM(matrixOfQuaternion([s, 0, 0, s]), [[0, -1, 0], [1, 0, 0], [0, 0, 1]]));
});

test('the shortest rotation turns one direction onto another', () => {
  for (const n of [[1, 0, 0], [0, 1, 0], [0.6, 0, 0.8], [0, -0.6, -0.8], [0.48, 0.6, 0.64]]) {
    const q = shortestRotation(n, [0, 0, -1]);
    assert.ok(close(rotateVector(q, n), [0, 0, -1]), `for ${n}`);
  }
});

test('laying on a face whose normal is one of the six axes gives exactly the contract\'s orientation', () => {
  const cases = { '+z': [0, 0, -1], '-z': [0, 0, 1], '+x': [-1, 0, 0], '-x': [1, 0, 0], '+y': [0, -1, 0], '-y': [0, 1, 0] };
  for (const [orientation, normal] of Object.entries(cases)) {
    const lay = shortestRotation(normal, [0, 0, -1]);
    assert.ok(closeM(matrixOfQuaternion(lay), ORIENTATION_MATRICES[orientation], 1e-12), orientation);
    assert.deepEqual(instanceTurn(lay, 0), { orientation, angle: 0 });
  }
});

test('an axis lay followed by a whole-degree turn is still sent as an orientation, the turn added to the angle', () => {
  // The +x lay, then 90 degrees about the vertical: Rz(90) M(+x), sent at angle 10 as +x at 100.
  const s = Math.SQRT1_2;
  const lay = shortestRotation([-1, 0, 0], [0, 0, -1]);
  const rz90 = [s, 0, 0, s];
  const turned = multiply(rz90, lay);
  assert.deepEqual(instanceTurn(turned, 10), { orientation: '+x', angle: 100 });
  assert.deepEqual(instanceTurn(turned, 300), { orientation: '+x', angle: 30 });
});

test('a lay on any other face is sent as a rotation, the unit quaternion of nine decimals', () => {
  const lay = shortestRotation([0.6, 0, -0.8], [0, 0, -1]);
  const sent = instanceTurn(lay, 15);
  assert.deepEqual(Object.keys(sent).sort(), ['angle', 'rotation']);
  assert.equal(sent.angle, 15);
  const [w, x, y, z] = sent.rotation;
  assert.ok(Math.abs(Math.hypot(w, x, y, z) - 1) <= 1e-6);
  assert.ok(sent.rotation.every((v) => Math.abs(v * 1e9 - Math.round(v * 1e9)) < 1e-6));
});

test('laying an instance on a face keeps its turn about the vertical', () => {
  const lay = [1, 0, 0, 0];
  const after = layOnFace(lay, [-1, 0, 0]);
  assert.ok(close(rotateVector(after, [-1, 0, 0]), [0, 0, -1]));
  // Laid on an already laid instance's face: the new lay starts from the current one.
  const again = layOnFace(after, [0, 1, 0]);
  assert.ok(close(rotateVector(again, [0, 1, 0]), [0, 0, -1]));
});

test('an instance\'s matrix comes from its orientation or its rotation', () => {
  assert.ok(closeM(instanceMatrix({ orientation: '-y' }), ORIENTATION_MATRICES['-y']));
  const s = Math.SQRT1_2;
  assert.ok(closeM(instanceMatrix({ rotation: [s, 0, 0, s] }), [[0, -1, 0], [1, 0, 0], [0, 0, 1]]));
  // A rotation a little off unit length is divided by its length, as the slice service does.
  assert.ok(closeM(instanceMatrix({ rotation: [2 * s, 0, 0, 2 * s] }), [[0, -1, 0], [1, 0, 0], [0, 0, 1]]));
});

function multiply(a, b) {
  const [aw, ax, ay, az] = a;
  const [bw, bx, by, bz] = b;
  return [
    aw * bw - ax * bx - ay * by - az * bz,
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
  ];
}
