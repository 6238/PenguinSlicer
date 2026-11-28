// A face on which the part would rest on no face of its own is not offered: the slice service's
// rule for slice.rests_on_an_edge, with its figures (wizard/README-details.md, "Finding the faces
// a part can lie on", step 5). The real Orca refuses such a pose (the slice service's real-Orca
// suite slices every offered face of the real parts, tests_orca/test_offered_faces.py).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { contactArea, firstLayerHoldsALine, restsOnNoFace } from '../../src/geometry/first-layer.js';
import { findFaces } from '../../src/geometry/faces.js';
import { convexHull } from '../../src/geometry/hull.js';
import { box, cylinder, meshOf, moved, prism, rotationX, starPrism, turned, union } from './shapes.js';

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

// The mesh with the triangles numbered in `which` (all of them when it is left out) wound the
// other way round, as an STL exported inside out, or partly so, has them.
function rewound(mesh, which = null) {
  const out = new Float64Array(mesh.positions);
  for (let t = 0; t < mesh.triangles; t++) {
    if (which && !which.includes(t)) continue;
    for (let k = 0; k < 3; k++) [out[9 * t + 3 + k], out[9 * t + 6 + k]] = [out[9 * t + 6 + k], out[9 * t + 3 + k]];
  }
  return { ...mesh, positions: out };
}

test('the face across the L\'s open corner is dropped however the L\'s triangles are wound', () => {
  // The slice service takes the section by the even-odd rule, which ignores winding, and slices
  // an inside-out part with a warning, so the wizard must not take the part's inside from it.
  const inside = rewound(ell());
  assert.equal(firstLayerHoldsALine(inside, ACROSS), false);
  assert.equal(restsOnNoFace(inside, ACROSS), true);
  assert.equal(facesOf(inside).faces.find((f) => near(f.normal, ACROSS)).dropped, 'no_first_layer');
  for (let t = 0; t < ell().triangles; t++) {
    assert.equal(firstLayerHoldsALine(rewound(ell(), [t]), ACROSS), false, `triangle ${t} turned`);
  }
  // And a part that holds a line still holds it inside out.
  assert.equal(firstLayerHoldsALine(rewound(rods()), DOWN_Y), true);
  assert.equal(firstLayerHoldsALine(rewound(ridges(20)), DOWN_Y), true);
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

// A ring standing on a sharp circular ridge: the triangle (R, 0), (R + 10, h), (R - 10, h) turned
// about the y axis, its sides sloping `deg` from the plate, so that half a first layer up its
// section is an annulus 0.3 / tan(deg) mm wide with no ends, where a disc must touch both rims.
function ring(deg, R = 30, steps = 360) {
  const h = 10 * Math.tan((deg * Math.PI) / 180);
  const profile = [[R, 0], [R + 10, h], [R - 10, h]];
  const at = ([r, y], k) => {
    const t = (2 * Math.PI * k) / steps;
    return [r * Math.cos(t), y, r * Math.sin(t)];
  };
  const tris = [];
  for (let e = 0; e < 3; e++) {
    const p = profile[e], q = profile[(e + 1) % 3];
    for (let k = 0; k < steps; k++) {
      tris.push([at(p, k), at(q, k), at(q, k + 1)]);
      tris.push([at(p, k), at(q, k + 1), at(p, k + 1)]);
    }
  }
  return meshOf(tris);
}

test('a ridge just narrower than one line holds none, and one just wider holds one', () => {
  // At 0.60 and 0.64 mm, either side of the 0.62 mm line, a looser disc test gets one wrong: a
  // slack of hundredths of a millimetre takes the 0.60 mm ridge, discs tried further in from the
  // edge than half a line miss the 0.64 mm ring (the straight ridges' ends would still hold them).
  const slope = (width) => (Math.atan(0.3 / width) * 180) / Math.PI;
  assert.equal(firstLayerHoldsALine(ridges(slope(0.60)), DOWN_Y), false);
  assert.equal(firstLayerHoldsALine(ridges(slope(0.64)), DOWN_Y), true);
  assert.equal(contactArea(ring(slope(0.64)), DOWN_Y), 0);
  assert.equal(firstLayerHoldsALine(ring(slope(0.60)), DOWN_Y), false);
  assert.equal(firstLayerHoldsALine(ring(slope(0.64)), DOWN_Y), true);
});

test('a face step 5 drops covers no side, so the sides it leaves empty get bounding-box patches', () => {
  // A 12-pointed star prism, 100 mm long: each of its 12 side hull faces spans two sharp tips,
  // so the part laid there rests on two edges and step 5 drops all 12. The four sides of the
  // bounding box across the star (±x, ±y), each 15 degrees from two dropped faces, are left to
  // bounding-box patches; the ends stay hull faces.
  const mesh = starPrism(12, 50, 30, 100);
  const result = facesOf(mesh);
  const sides = result.faces.filter((f) => Math.abs(f.normal[2]) < 1e-6);
  assert.equal(sides.length, 12);
  for (const face of sides) assert.equal(face.dropped, 'no_first_layer');
  assert.deepEqual(result.patches.filter((p) => p.kind === 'box').map((p) => p.side).sort(),
    ['+x', '+y', '-x', '-y']);
  assert.deepEqual(result.patches.filter((p) => p.kind === 'hull').map((p) => Math.round(p.normal[2])).sort(),
    [-1, 1]);
  // Step 5's rule is not applied to bounding-box patches, and these four rest on tips too: the
  // wizard offers them all the same (the details' step 6; a limit of the wizard, not of the
  // slice service, which answers slice.rests_on_an_edge for them).
  for (const patch of result.patches.filter((p) => p.kind === 'box')) {
    assert.equal(restsOnNoFace(mesh, patch.normal), true);
  }
});

test('faces of its own on the plate of 0.01 mm² or more are enough, as the slice service counts them', () => {
  // The 30-degree ridges, which hold no line, with their tips cut flat along their 20 mm: cut
  // 0.0003 mm wide the two flats add up to 0.012 mm² and the part stands on faces of its own; cut
  // 0.0002 mm wide, to 0.008 mm², it does not.
  const cut = (w, long = 20) => {
    const h = 10 * Math.tan(Math.PI / 6);
    const foot = (x) => prism([[x + w / 2, 0], [x + 10, h], [x - 10, h], [x - w / 2, 0]], 0, long);
    return union(foot(0), foot(40), moved(box(60, 10, 20), [-10, h, 0]));
  };
  assert.ok(Math.abs(contactArea(cut(0.0003), DOWN_Y) - 0.012) < 1e-9);
  assert.equal(restsOnNoFace(cut(0.0003), DOWN_Y), false);
  assert.ok(Math.abs(contactArea(cut(0.0002), DOWN_Y) - 0.008) < 1e-9);
  assert.equal(restsOnNoFace(cut(0.0002), DOWN_Y), true);
  // Exactly 0.01 mm² (two flats 2^-10 mm wide and 5.12 mm long, which add up without rounding)
  // is enough: the slice service refuses under 0.01 mm², not at it.
  assert.equal(contactArea(cut(2 ** -10, 5.12), DOWN_Y), 0.01);
  assert.equal(restsOnNoFace(cut(2 ** -10, 5.12), DOWN_Y), false);
});

test('a face is on the plate when every corner is within 0.001 mm of it, and not at 0.005 mm', () => {
  // A 20 mm square box whose bottom is tilted so that one edge is 0.005 mm higher than the other:
  // each of its two bottom triangles has a corner 0.005 mm up, so neither is on the plate; tilted
  // 0.0008 mm, both are.
  const tilted = (rise) => turned(box(20, 20, 10), rotationX((Math.asin(rise / 20) * 180) / Math.PI));
  assert.equal(contactArea(tilted(0.005), [0, 0, -1]), 0);
  assert.ok(Math.abs(contactArea(tilted(0.0008), [0, 0, -1]) - 400) < 1e-6);
});

test('a line is looked for every 0.02 mm along the section\'s edge, not only at its corners', () => {
  // A prism standing on its end whose section is a flat triangle 10 mm across and 0.624 mm tall:
  // a line fits only where its edge touches the long side within 0.013 mm either side of the
  // middle, far from any corner of the section; 0.62 mm tall, it fits nowhere.
  const flat = (h) => prism([[0, 0], [10, 0], [5, h]], 0, 20);
  assert.equal(firstLayerHoldsALine(flat(0.624), [0, 0, -1]), true);
  assert.equal(firstLayerHoldsALine(flat(0.62), [0, 0, -1]), false);
});
