// Finding the faces a part can lie on: the hull's flat faces, the filters, the rule for round
// sides and the bounding-box patches (wizard/README-details.md, "Finding the faces a part can
// lie on").
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { findFaces } from '../../src/geometry/faces.js';
import { convexHull } from '../../src/geometry/hull.js';
import { box, cylinder, meshOf, moved, prism, regularPolygon, turned, union, rotationX, rotationZ } from './shapes.js';

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

test('a round side whose facets have thin slivers between them is still one round side', () => {
  // 36 facets 10 degrees apart, each pair separated by a facet 0.2 mm wide: no facet has a
  // neighbour half its size, but each reaches the next across a sliver bending 5 degrees.
  const outline = [];
  for (let i = 0; i < 36; i++) {
    const t = (2 * Math.PI * i) / 36;
    const dt = 0.2 / 20;
    outline.push([20 * Math.cos(t), 20 * Math.sin(t)], [20 * Math.cos(t + dt), 20 * Math.sin(t + dt)]);
  }
  const result = facesOf(prism(outline, 0, 10));
  assert.equal(result.patches.filter((p) => p.kind === 'hull').length, 2);
  assert.deepEqual(sides(result), ['+x', '+y', '-x', '-y']);
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

test('a flat face of the part beside a hull face that bridges a step keeps its patch; the bridge loses its own', () => {
  // A 40 x 40 block 20 tall on one set back 1.05 mm on +x: on +x the hull has the upper block's
  // flat face (800 mm² of the part's own surface) and, 3 degrees from it, a face of the same size
  // bridging down to the lower block's bottom edge, which touches the part only along its edges.
  const mesh = union(moved(box(40, 40, 20), [0, 0, 20]), box(38.95, 40, 20));
  const result = findFaces(convexHull(mesh.positions), mesh);
  const plusX = result.patches.filter((p) => p.normal[0] > 0.99);
  assert.equal(plusX.length, 1);
  assert.ok(Math.abs(plusX[0].normal[0] - 1) < 1e-9, 'the patch is on the flat face, not the bridge');
  assert.deepEqual(sides(result), []);
});

test('a flat face keeps its patch beside a bridge four times its size; a strip under 25 mm² does not', () => {
  const plusX = (upper) => {
    const mesh = union(moved(box(40, 40, upper), [0, 0, 40]), box(38, 40, 40));
    return findFaces(convexHull(mesh.positions), mesh).patches.filter((p) => p.kind === 'hull' && p.normal[0] > 0.999);
  };
  assert.equal(plusX(10).length, 1, 'a 400 mm² flat face beside a 1,600 mm² bridge');
  assert.equal(plusX(0.5).length, 0, 'a 20 mm² strip beside a bridge');
});

test('the facets of a round side are all the part\'s own surface, so the rule for them is unchanged', () => {
  const result = facesOf(cylinder(48, 10, 5));
  assert.equal(result.faces.filter((f) => f.dropped === 'round_side').length, 48);
});

test('a hull face the part would tip over from keeps its patch: the plate holds the first layer', () => {
  // A post 10 x 10 x 50 with an arm 60 long on top: on the post's foot the centre of mass is
  // far out over the arm, and the foot is still offered (auto-orient marks it unstable).
  const gamma = union(box(10, 10, 50), moved(box(60, 10, 10), [10, 0, 40]));
  const result = findFaces(convexHull(gamma.positions), gamma);
  assert.ok(result.patches.some((p) => p.kind === 'hull' && p.normal[2] < -0.999));
});

test('a strip of the hull a few thousandths of a millimetre off a face\'s plane is part of that face', () => {
  // A corner 0.4 mm out from the top's edge and 0.005 mm below it: the hull's top then has a
  // strip tilted 0.7 degrees, too far to be joined by direction, close enough to be the same flat.
  const mesh = union(box(40, 40, 10), meshOf([[[20, 40.4, 9.995], [20, 40.4, 9.995], [20, 40.4, 9.995]]]));
  const result = findFaces(convexHull(mesh.positions), mesh);
  const tops = result.faces.filter((f) => f.normal[2] > 0.99);
  assert.equal(tops.length, 1);
  assert.ok(Math.abs(tops[0].area - 1608) < 0.1, `area ${tops[0].area}`);
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
