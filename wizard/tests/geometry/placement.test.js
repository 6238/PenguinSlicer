// The placement check: the slice service's three rules, run on the shared set of plates
// (contracts/plate-configuration.md, "Shared plates for the placement checks"), which both
// components' tests run and on which both must give exactly the expected answer.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { checkPlate, expectedAnswer, footprint, instanceLabels, plateOf, supportsOn } from '../../src/geometry/placement.js';
import { convexHull } from '../../src/geometry/hull.js';
import { CONTRACT_PARTS, PLACEMENT_PLATES, readContractPart } from './helpers.js';
import { box } from './shapes.js';

// The H2S of the default set of profiles, which every shared plate is over.
const H2S = { min: [0, 0], max: [340, 320], height: 340 };

function partsByHash() {
  const out = {};
  for (const file of readdirSync(CONTRACT_PARTS).filter((f) => f.endsWith('.stl'))) {
    const sha = createHash('sha256').update(readFileSync(join(CONTRACT_PARTS, file))).digest('hex');
    out[sha] = convexHull(readContractPart(file).positions).points;
  }
  return out;
}

const plates = readdirSync(PLACEMENT_PLATES).filter((f) => f.endsWith('.json')).sort();
const hulls = partsByHash();

test('the shared set has its thirteen plates', () => {
  assert.equal(plates.length, 13);
});

for (const file of plates) {
  test(`shared plate ${file}: the expected answer exactly`, () => {
    const { plate_configuration: pc, expected } = JSON.parse(readFileSync(join(PLACEMENT_PLATES, file), 'utf8'));
    const points = Object.fromEntries(Object.entries(pc.parts).map(([key, part]) => [key, hulls[part.sha256]]));
    for (const [key, p] of Object.entries(points)) assert.ok(p, `no part file for ${key}`);
    const plate = plateOf(H2S, supportsOn(pc, '0'));
    const problems = checkPlate(pc, points, plate);
    assert.deepEqual(expectedAnswer(problems, instanceLabels(pc)), expected);
  });
}

test('supports are on when the changes say so, else when the profile does', () => {
  assert.equal(supportsOn({ overrides: { enable_support: '1' } }, '0'), true);
  assert.equal(supportsOn({ overrides: { enable_support: '0' } }, '1'), false);
  assert.equal(supportsOn({ overrides: {} }, '1'), true);
  assert.equal(supportsOn({}, '0'), false);
  assert.equal(plateOf(H2S, true).spacing, 12);
  assert.equal(plateOf(H2S, false).spacing, 5);
});

test('instances are named as the slice service names them', () => {
  const pc = {
    parts: { a: { name: 'L Bracket' }, b: { name: 'L-Bracket' }, c: { name: '' } },
    instances: [{ ref: 'a' }, { ref: 'b' }, { ref: 'a' }, { ref: 'c' }],
  };
  assert.deepEqual(instanceLabels(pc), ['L_Bracket #1', 'L-Bracket #1', 'L_Bracket #2', 'part #1']);
});

test('the problems come in the slice service\'s order: every edge, then every height, then every pair', () => {
  const points = { post: convexHull(box(10, 10, 341).positions).points };
  const pc = {
    parts: { post: { name: 'Post' } },
    instances: [
      { ref: 'post', orientation: '+z', angle: 0, x: 100, y: 100 },
      { ref: 'post', orientation: '+z', angle: 0, x: 104, y: 100 },
      { ref: 'post', orientation: '+x', angle: 0, x: 1, y: 300 },
    ],
  };
  const problems = checkPlate(pc, points, plateOf(H2S, false));
  assert.deepEqual(problems.map((p) => [p.rule, p.instances]), [
    ['off_plate', [2]], ['too_tall', [0]], ['too_tall', [1]], ['too_close', [0, 1]],
  ]);
  assert.deepEqual(expectedAnswer(problems, instanceLabels(pc)), { code: 'slice.placement_off_plate', instance: 'Post #3' });
});

test('a problem carries what the Layout step\'s messages need: the edges crossed, the distance, the size', () => {
  const points = { block: convexHull(box(40, 20, 10).positions).points };
  const pc = {
    parts: { block: { name: 'Block' } },
    instances: [
      { ref: 'block', orientation: '+z', angle: 0, x: 10, y: 160 },
      { ref: 'block', orientation: '+z', angle: 0, x: 200, y: 160 },
      { ref: 'block', orientation: '+z', angle: 0, x: 243.5, y: 160 },
    ],
  };
  const problems = checkPlate(pc, points, plateOf(H2S, false));
  const off = problems.find((p) => p.rule === 'off_plate');
  assert.deepEqual(off.edges, ['left']);
  const close = problems.find((p) => p.rule === 'too_close');
  assert.ok(Math.abs(close.distance - 3.5) < 1e-9);
  assert.deepEqual(off.size.map((v) => +v.toFixed(6)), [40, 20]);
});

test('a footprint is the turned part\'s outline seen from above, centred on its bounding box', () => {
  const points = convexHull(box(40, 20, 10).positions).points;
  const fp = footprint(points, [[1, 0, 0], [0, 1, 0], [0, 0, 1]]);
  assert.deepEqual(fp.centre, [20, 10]);
  assert.equal(fp.height, 10);
  assert.equal(fp.hull.length, 4);
});

test('a plate of 150 instances is checked in one pass', () => {
  const points = { block: convexHull(box(10, 10, 10).positions).points };
  const instances = [];
  for (let i = 0; i < 150; i++) instances.push({ ref: 'block', orientation: '+z', angle: 0, x: 10 + (i % 15) * 21, y: 10 + Math.floor(i / 15) * 21 });
  const pc = { parts: { block: { name: 'Block' } }, instances };
  assert.deepEqual(checkPlate(pc, points, plateOf(H2S, false)), []);
});
