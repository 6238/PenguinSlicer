// The convex hull of a part's corners: the shape every face a part can lie on comes from.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { convexHull } from '../../src/geometry/hull.js';
import { GeometryError } from '../../src/geometry/errors.js';
import { readRealPart, hullIsValid } from './helpers.js';

// A small deterministic generator, so a failing case can be repeated exactly.
function random(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

test('a cube with points inside it has the cube as its hull: 8 corners, 12 triangles', () => {
  const pts = [];
  for (const x of [0, 10]) for (const y of [0, 10]) for (const z of [0, 10]) pts.push(x, y, z);
  const r = random(1);
  for (let i = 0; i < 500; i++) pts.push(1 + 8 * r(), 1 + 8 * r(), 1 + 8 * r());
  const hull = convexHull(new Float64Array(pts));
  assert.equal(hull.triangles.length / 3, 12);
  assert.equal(new Set(hull.triangles).size, 8);
  assert.deepEqual(hullIsValid(hull, new Float64Array(pts)), []);
});

test('points on a sphere: every point is inside every face, the faces face outwards and close up', () => {
  const r = random(7);
  const pts = [];
  for (let i = 0; i < 3000; i++) {
    const u = 2 * r() - 1;
    const t = 2 * Math.PI * r();
    const s = Math.sqrt(1 - u * u);
    pts.push(20 * s * Math.cos(t), 20 * s * Math.sin(t), 20 * u);
  }
  const hull = convexHull(new Float64Array(pts));
  assert.deepEqual(hullIsValid(hull, new Float64Array(pts)), []);
  // Euler: a closed surface of triangles has F = 2V - 4.
  const v = new Set(hull.triangles).size;
  assert.equal(hull.triangles.length / 3, 2 * v - 4);
});

test('repeated corners, as an STL repeats each corner in every triangle, change nothing', () => {
  const pts = [];
  for (let k = 0; k < 6; k++) for (const x of [0, 5]) for (const y of [0, 7]) for (const z of [0, 3]) pts.push(x, y, z);
  const hull = convexHull(new Float64Array(pts));
  assert.equal(hull.triangles.length / 3, 12);
});

test('each hull triangle knows its three neighbours, each across the edge it names', () => {
  const pts = [];
  for (const x of [0, 10]) for (const y of [0, 10]) for (const z of [0, 10]) pts.push(x, y, z);
  const hull = convexHull(new Float64Array(pts));
  const t = hull.triangles;
  for (let f = 0; f < t.length / 3; f++) {
    for (let e = 0; e < 3; e++) {
      const g = hull.neighbours[f * 3 + e];
      const a = t[f * 3 + e];
      const b = t[f * 3 + ((e + 1) % 3)];
      // The neighbour has the same edge, the other way round.
      const back = [0, 1, 2].some((k) => t[g * 3 + k] === b && t[g * 3 + ((k + 1) % 3)] === a);
      assert.ok(back, `triangle ${f} edge ${e}: neighbour ${g} does not share it`);
    }
  }
});

test('a flat part has no hull: an error the page can show, not an exception of its own', () => {
  const pts = new Float64Array([0, 0, 0, 10, 0, 0, 0, 10, 0, 10, 10, 0, 5, 5, 0]);
  assert.throws(() => convexHull(pts), (err) => err instanceof GeometryError && err.report.code === 'wizard.part_not_drawable');
});

test('fewer than four points have no hull', () => {
  assert.throws(() => convexHull(new Float64Array([0, 0, 0, 1, 0, 0, 0, 1, 0])), GeometryError);
});

test('the real Pulley v3 gets a valid hull holding every one of its corners', () => {
  const mesh = readRealPart('pulley-v3.stl');
  const hull = convexHull(mesh.positions);
  assert.deepEqual(hullIsValid(hull, mesh.positions), []);
});
