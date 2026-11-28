// The geometry on the real exported parts kept in the repository, and on the trials' made
// parts: the expected answers are the second trial's recorded results
// (wizard/trials/geometry/results/), written down here so that a change to the rules that
// changes what a user is offered fails a test. Since the faces on which a part rests on no face
// of its own are not offered (first-layer.js), Elevator Block Bottom Inner has two hull patches
// fewer than the trial recorded and Elevator Block Carriage and Elevator Block Top one each: the
// hull faces across their pockets whose first layer the slice service judges too narrow.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { analysePart } from '../../src/geometry/part.js';
import { autoOrient } from '../../src/geometry/orient.js';
import { instanceTurn } from '../../src/geometry/turn.js';
import { FLAT_GAP_MM, FLAT_TURN_DEG, MIN_CONTACT_MM2 } from '../../src/geometry/constants.js';
import { readMadePart, readRealPart } from './helpers.js';

const EXPECTED = {
  'clamp-plate-inner': { hullTriangles: 604, faces: 150, hull: 6, box: [], modelled: false, normal: [1, 0, 0], height: 4.76, contact: 2334, overhang: 0, turn: { orientation: '-x', angle: 0 } },
  'elevator-block-bottom-inner': { hullTriangles: 2722, faces: 1100, hull: 10, box: [], modelled: false, normal: [0, 0, 1], height: 82.55, contact: 1575, overhang: 3685, turn: { orientation: '-z', angle: 0 } },
  'elevator-block-carriage': { hullTriangles: 8796, faces: 3309, hull: 8, box: [], modelled: false, normal: [0, -1, 0], height: 31.75, contact: 1836, overhang: 2160, turn: { orientation: '+y', angle: 0 } },
  'elevator-block-top': { hullTriangles: 7652, faces: 3005, hull: 8, box: [], modelled: false, normal: [0, -1, 0], height: 31.75, contact: 3148, overhang: 2768, turn: { orientation: '+y', angle: 0 } },
  'elevator-top-inner': { hullTriangles: 11350, faces: 4586, hull: 6, box: [], modelled: false, normal: [0, 0, 1], height: 57.15, contact: 1111, overhang: 550, turn: { orientation: '-z', angle: 0 } },
  'inner-spacer': { hullTriangles: 588, faces: 150, hull: 6, box: [], modelled: false, normal: [1, 0, 0], height: 1.26, contact: 2464, overhang: 0, turn: { orientation: '-x', angle: 0 } },
  'outer-clamp': { hullTriangles: 592, faces: 150, hull: 6, box: [], modelled: false, normal: [1, 0, 0], height: 4.76, contact: 2495, overhang: 0, turn: { orientation: '-x', angle: 0 } },
  'pulley-v3': { hullTriangles: 940, faces: 146, hull: 2, box: ['+y', '+z', '-y', '-z'], modelled: false, normal: [-1, 0, 0], height: 17.78, contact: 158, overhang: 150, turn: { orientation: '+x', angle: 0 } },
  'hub-150k': { hullTriangles: 25560, faces: 6723, hull: 2, box: ['+x', '+y', '-x', '-y'], modelled: true, normal: [0, 0, -1], height: 20, contact: 754, overhang: 275, turn: { orientation: '+z', angle: 0 } },
  'hex-spacer': { hullTriangles: 188, faces: 50, hull: 2, box: ['+x', '+y', '-x', '-y'], modelled: true, normal: [0, 0, -1], height: 3.17, contact: 119, overhang: 0, turn: { orientation: '+z', angle: 0 } },
};
const MADE = new Set(['hub-150k', 'hex-spacer']);

const analysed = new Map();
function partOf(key) {
  if (!analysed.has(key)) {
    const part = analysePart(MADE.has(key) ? readMadePart(`${key}.stl`) : readRealPart(`${key}.stl`));
    analysed.set(key, { part, choice: autoOrient(part) });
  }
  return analysed.get(key);
}

for (const [key, want] of Object.entries(EXPECTED)) {
  test(`${key}: the faces, patches and best way recorded by the trial`, () => {
    const { part, choice } = partOf(key);
    assert.equal(part.hullTriangles, want.hullTriangles);
    assert.equal(part.faces.length, want.faces);
    assert.equal(part.patches.filter((p) => p.kind === 'hull').length, want.hull);
    assert.deepEqual(part.patches.filter((p) => p.kind === 'box').map((p) => p.side).sort(), want.box);
    assert.equal(choice.modelled, want.modelled);
    assert.ok(choice.normal.every((v, i) => Math.abs(v - want.normal[i]) < 1e-3), `laid on ${choice.normal}`);
    assert.ok(Math.abs(choice.height - want.height) < 0.01, `height ${choice.height}`);
    assert.ok(Math.abs(choice.contact - want.contact) < 1, `contact ${choice.contact}`);
    assert.ok(Math.abs(choice.overhang - want.overhang) < 1, `overhang ${choice.overhang}`);
    assert.deepEqual(instanceTurn(choice.lay, 0), want.turn);
  });
}

// The part's flat faces: hull faces of at least MIN_CONTACT_MM2 that are mostly the part's own
// surface. The trial's page makes the same count (wizard/trials/geometry/trial.js).
function flatFacesWithoutPatch(part) {
  const p = part.mesh.positions;
  const n = part.triangleNormals;
  const a = part.triangleAreas;
  const near = Math.cos((FLAT_TURN_DEG * Math.PI) / 180);
  const missing = [];
  for (const face of part.faces) {
    if (face.area < MIN_CONTACT_MM2 || !face.dropped) continue;
    const d = face.outline.reduce((s, q) => s + q[0] * face.normal[0] + q[1] * face.normal[1] + q[2] * face.normal[2], 0) / face.outline.length;
    let material = 0;
    for (let t = 0; t < a.length; t++) {
      if (n[t * 3] * face.normal[0] + n[t * 3 + 1] * face.normal[1] + n[t * 3 + 2] * face.normal[2] < near) continue;
      const c = [0, 1, 2].map((k) => (p[t * 9 + k] + p[t * 9 + 3 + k] + p[t * 9 + 6 + k]) / 3);
      if (Math.abs(c[0] * face.normal[0] + c[1] * face.normal[1] + c[2] * face.normal[2] - d) < FLAT_GAP_MM) material += a[t];
    }
    if (material >= 0.5 * face.area) missing.push({ normal: face.normal, area: face.area, dropped: face.dropped });
  }
  return missing;
}

// The hull faces on which the part would rest on no face of its own: the slice service, measuring
// each pose of the trial's patches with its own code (contact_area_mm2 and first_layer_section),
// names exactly these four slanting hull faces of the three blocks (normals to two decimals), and
// the real Orca refuses the one of normal (0, -0.87, -0.49).
const NO_FIRST_LAYER = {
  'elevator-block-bottom-inner': [[0, 0.71, 0.71], [0, -0.87, -0.49]],
  'elevator-block-carriage': [[0, 0.71, 0.71]],
  'elevator-block-top': [[0, 0.71, 0.71]],
};

for (const key of Object.keys(EXPECTED)) {
  test(`${key}: the faces not offered for want of a first layer are those the slice service names`, () => {
    const dropped = partOf(key).part.faces.filter((f) => f.dropped === 'no_first_layer').map((f) => f.normal.map((v) => Math.round(v * 100) / 100 || 0));
    assert.deepEqual(dropped.map(String).sort(), (NO_FIRST_LAYER[key] || []).map(String).sort());
  });
}

for (const key of Object.keys(EXPECTED).filter((k) => !MADE.has(k))) {
  test(`${key}: every flat face of the part has a hull patch`, () => {
    assert.deepEqual(flatFacesWithoutPatch(partOf(key).part), []);
  });
}
