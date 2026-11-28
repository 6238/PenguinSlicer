// A face on which the part would rest on no face of its own is not offered: the slice service's
// rule for slice.rests_on_an_edge, with its figures (wizard/README-details.md, "Finding the faces
// a part can lie on", step 5). The real Orca refuses such a pose (the slice service's real-Orca
// suite slices every offered face of the real parts, tests_orca/test_offered_faces.py).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { contactArea, firstLayerHoldsALine, restsOnNoFace } from '../../src/geometry/first-layer.js';
import { findFaces } from '../../src/geometry/faces.js';
import { convexHull } from '../../src/geometry/hull.js';
import { box, cylinder, moved, prism, union } from './shapes.js';

const facesOf = (mesh) => findFaces(convexHull(mesh.positions), mesh);
const near = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 1e-6);
const DOWN_Y = [0, -1, 0];
const ACROSS = [Math.SQRT1_2, Math.SQRT1_2, 0];

// An L, 10 mm thick arms 40 mm long, 10 mm tall: its hull face across the open corner (normal
// (1, 1, 0)/√2) touches the part along two edges, and half a first layer above it the section is
// two strips 0.3 mm wide, as the slice service measures the bracket on its hull face.
const ell = () => prism([[10, 10], [10, 40], [0, 40], [0, 0], [40, 0], [40, 10]], 0, 10);

// A body standing on two ridges along z, whose sides slope `deg` degrees from the plate: its
// bottom (normal -y) touches the part along the ridges only, and half a first layer up each ridge
// is 2 × 0.15 / tan(deg) mm wide.
function ridges(deg) {
  const h = 10 * Math.tan((deg * Math.PI) / 180);
  const foot = (x) => prism([[x, 0], [x + 10, h], [x - 10, h]], 0, 20);
  return union(foot(0), foot(40), moved(box(60, 10, 20), [-10, h, 0]));
}

// Two rods 10 mm across, 30 mm apart: the hull face beneath both touches each along a line, yet
// half a first layer up each is 2.4 mm wide, as a lying tube is, and prints.
const rods = () => union(cylinder(48, 5, 20), moved(cylinder(48, 5, 20), [30, 0, 0]));

test('a part laid on its own flat face has that face on the plate', () => {
  assert.ok(Math.abs(contactArea(box(20, 30, 10), [0, 0, -1]) - 600) < 1e-9);
  assert.equal(restsOnNoFace(box(20, 30, 10), [0, 0, -1]), false);
});

test('the L on the face across its open corner touches the plate with nothing and holds no line', () => {
  const mesh = ell();
  assert.equal(contactArea(mesh, ACROSS), 0);
  assert.equal(firstLayerHoldsALine(mesh, ACROSS), false);
  assert.equal(restsOnNoFace(mesh, ACROSS), true);
});

test('the face across the L\'s open corner is not offered, and its other faces are', () => {
  const result = facesOf(ell());
  const across = result.faces.find((f) => near(f.normal, ACROSS));
  assert.equal(across.dropped, 'no_first_layer');
  assert.ok(!result.patches.some((p) => near(p.normal, ACROSS)));
  // The hull is a five-sided prism: its top, its bottom and four of its five sides.
  assert.equal(result.patches.filter((p) => p.kind === 'hull').length, 6);
  assert.deepEqual(result.patches.filter((p) => p.kind === 'box'), []);
});

test('two rods laid on the face beneath both touch along lines and still hold a line', () => {
  const mesh = rods();
  assert.equal(contactArea(mesh, DOWN_Y), 0);
  assert.equal(firstLayerHoldsALine(mesh, DOWN_Y), true);
  const result = facesOf(mesh);
  const beneath = result.patches.find((p) => p.kind === 'hull' && near(p.normal, DOWN_Y));
  assert.ok(beneath, 'the face beneath both rods is offered');
});

test('a ridge holds a line of the first layer when it is wider than one line half a layer up', () => {
  // 30 degrees: 0.52 mm across, under the 0.62 mm line; 20 degrees: 0.82 mm, over it. Taken a
  // whole first layer up (0.3 mm) the 30-degree ridge would be 1.04 mm, so the height is pinned
  // too.
  assert.equal(firstLayerHoldsALine(ridges(30), DOWN_Y), false);
  assert.equal(restsOnNoFace(ridges(30), DOWN_Y), true);
  assert.equal(firstLayerHoldsALine(ridges(20), DOWN_Y), true);
  assert.equal(restsOnNoFace(ridges(20), DOWN_Y), false);
  assert.equal(facesOf(ridges(30)).faces.find((f) => near(f.normal, DOWN_Y)).dropped, 'no_first_layer');
  assert.equal(facesOf(ridges(20)).faces.find((f) => near(f.normal, DOWN_Y)).dropped, null);
});

test('faces of its own on the plate of 0.01 mm² or more are enough, as the slice service counts them', () => {
  // The 30-degree ridges, which hold no line, with their tips cut flat along their 20 mm: cut
  // 0.0003 mm wide the two flats add up to 0.012 mm² and the part stands on faces of its own; cut
  // 0.0002 mm wide, to 0.008 mm², it does not.
  const cut = (w) => {
    const h = 10 * Math.tan(Math.PI / 6);
    const foot = (x) => prism([[x + w / 2, 0], [x + 10, h], [x - 10, h], [x - w / 2, 0]], 0, 20);
    return union(foot(0), foot(40), moved(box(60, 10, 20), [-10, h, 0]));
  };
  assert.ok(Math.abs(contactArea(cut(0.0003), DOWN_Y) - 0.012) < 1e-9);
  assert.equal(restsOnNoFace(cut(0.0003), DOWN_Y), false);
  assert.ok(Math.abs(contactArea(cut(0.0002), DOWN_Y) - 0.008) < 1e-9);
  assert.equal(restsOnNoFace(cut(0.0002), DOWN_Y), true);
});
