// Finding the faces a part can lie on: the hull's flat faces, the filters, the rule for round
// sides and the bounding-box patches (wizard/README-details.md, "Finding the faces a part can
// lie on").
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { findFaces } from '../../src/geometry/faces.js';
import { convexHull } from '../../src/geometry/hull.js';
import { box, cylinder, prism, regularPolygon, turned, rotationX, rotationZ } from './shapes.js';

const facesOf = (mesh) => findFaces(convexHull(mesh.positions), mesh);
const kinds = (result) => result.patches.map((p) => p.kind);
const sides = (result) => result.patches.filter((p) => p.kind === 'box').map((p) => p.side).sort();
const near = (a, b, tol = 1e-9) => a.every((v, i) => Math.abs(v - b[i]) <= tol);

test('a box has six flat faces, each a hull patch, and no bounding-box patch', () => {
  const result = facesOf(box(20, 30, 10));
  assert.equal(result.faces.length, 6);
  assert.deepEqual(kinds(result), Array(6).fill('hull'));
  const areas = result.patches.map((p) => p.area).sort((a, b) => a - b);
  assert.deepEqual(areas.map((a) => +a.toFixed(6)), [200, 200, 300, 300, 600, 600]);
});

test('a face\'s normal points outwards and its outline lies on it', () => {
  const result = facesOf(box(20, 30, 10));
  const bottom = result.patches.find((p) => near(p.normal, [0, 0, -1]));
  assert.ok(bottom, 'no patch facing down');
  assert.equal(bottom.outline.length, 4);
  for (const corner of bottom.outline) assert.ok(Math.abs(corner[2]) < 1e-9);
});

test('the facets of a round side are dropped; its ends stay and its four sides get bounding-box patches', () => {
  const result = facesOf(cylinder(48, 10, 5));
  const hull = result.patches.filter((p) => p.kind === 'hull');
  assert.equal(hull.length, 2);
  assert.ok(hull.every((p) => Math.abs(Math.abs(p.normal[2]) - 1) < 1e-9));
  assert.deepEqual(sides(result), ['+x', '+y', '-x', '-y']);
  assert.equal(result.faces.filter((f) => f.dropped === 'round_side').length, 48);
});

test('a hex prism lies on its flats: every box side is within 30 degrees of one, so no box patch', () => {
  const result = facesOf(prism(regularPolygon(6, 8, Math.PI / 6), 0, 3.175));
  assert.deepEqual(kinds(result), Array(8).fill('hull'));
});

test('a flat exactly 30 degrees off a box side covers it, allowing half a degree for rounding', () => {
  // A hexagon with a corner on +x: its flats face 30, 90, 150... degrees, so +x and -x are
  // exactly 30 degrees from the nearest flat.
  const result = facesOf(prism(regularPolygon(6, 8, 0), 0, 3));
  assert.deepEqual(sides(result), []);
});

test('a box modelled turned 30 degrees about its height has every side covered; at 31 degrees none', () => {
  const at = (deg) => facesOf(turned(box(20, 30, 10), rotationZ(deg)));
  assert.deepEqual(sides(at(30)), []);
  assert.deepEqual(sides(at(31)), ['+x', '+y', '-x', '-y']);
});

test('a wedge leaves the two sides 45 degrees from its slope uncovered', () => {
  // Its flats face -y, -x and the slope at 45 degrees, between +x and +y.
  const result = facesOf(prism([[0, 0], [10, 0], [0, 10]], 0, 5));
  assert.deepEqual(sides(result), ['+x', '+y']);
});

test('a flat face beside a shallow chamfer keeps its patch; the chamfer loses its own', () => {
  // A 40 x 40 block 10 tall whose top edge along +x is cut by a 1 mm chamfer at 10 degrees.
  const outline = [[0, 0], [40, 0], [40, 10 - 1 * Math.tan((10 * Math.PI) / 180)], [39, 10], [0, 10]];
  const mesh = turned(prism(outline, 0, 40), rotationX(0));
  const result = facesOf(mesh);
  const dropped = result.faces.filter((f) => f.dropped === 'round_side');
  assert.equal(dropped.length, 1);
  assert.ok(dropped[0].area < 50, 'the chamfer, not the large face, was dropped');
});

test('a chamfer at 45 degrees bends too far to be caught and keeps its patch', () => {
  const outline = [[0, 0], [40, 0], [40, 8], [38, 10], [0, 10]];
  const result = facesOf(prism(outline, 0, 40));
  assert.equal(result.faces.filter((f) => f.dropped).length, 0);
  assert.equal(result.patches.filter((p) => p.kind === 'hull').length, 7);
});

test('a face under 5 mm² is dropped as too small', () => {
  // A 20 mm cube with one corner cut off by a triangle of about 2 mm².
  const outline = [[0, 0], [20, 0], [20, 18], [18, 20], [0, 20]];
  const result = facesOf(prism(outline, 0, 0.9));
  assert.ok(result.faces.some((f) => f.dropped === 'small' && f.area < 5));
});

test('a face with a corner sharper than one degree is dropped as a sliver', () => {
  const tip = 0.5;
  const outline = [[0, 0], [100, 0], [100, 100 * Math.tan((tip * Math.PI) / 180)]];
  const result = facesOf(prism(outline, 0, 20));
  const slivers = result.faces.filter((f) => f.dropped === 'sliver');
  assert.equal(slivers.length, 2, 'both ends of the wedge have the sharp corner');
});

test('only the 254 largest faces are kept', () => {
  // A ring of 400 facets, each about 31 mm², and two ends far larger: 148 facets beyond the 254.
  const result = facesOf(cylinder(400, 200, 10));
  assert.equal(result.faces.length, 402);
  assert.equal(result.faces.filter((f) => f.dropped === 'beyond_max').length, 148);
});

test('faces are found in the part\'s own coordinates, so a part modelled turned has its faces turned', () => {
  const result = facesOf(turned(box(20, 30, 10), rotationX(30)));
  assert.equal(result.patches.filter((p) => p.kind === 'hull').length, 6);
  assert.ok(result.patches.some((p) => near(p.normal, [0, Math.sin(Math.PI / 6), -Math.cos(Math.PI / 6)], 1e-9)));
});
