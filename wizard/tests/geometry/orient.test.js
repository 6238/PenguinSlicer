// Auto-orient: every way a part can rest, scored, the best taken (wizard/README-details.md,
// "Auto-orient").
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { analysePart } from '../../src/geometry/part.js';
import { autoOrient } from '../../src/geometry/orient.js';
import { rotateVector } from '../../src/geometry/turn.js';
import { box, leaning, meshOf, moved, prism, turned, union, rotationX } from './shapes.js';

const down = (choice, normal) => rotateVector(choice.lay, normal);
const close = (a, b, tol = 1e-9) => a.every((v, i) => Math.abs(v - b[i]) <= tol);

test('a tall block is laid on one of its largest faces, as low as it goes', () => {
  const part = analysePart(box(10, 20, 60));
  const choice = autoOrient(part);
  assert.ok(Math.abs(choice.height - 10) < 1e-9);
  assert.ok(Math.abs(choice.contact - 1200) < 1e-6);
  assert.equal(choice.modelled, false);
});

test('a block already lying its best way stays as modelled', () => {
  const part = analysePart(box(60, 20, 10));
  const choice = autoOrient(part);
  assert.equal(choice.modelled, true);
  assert.deepEqual(choice.lay, [1, 0, 0, 0]);
});

test('a part modelled upside down is turned over onto its flat side', () => {
  // A wedge whose flat 40 x 40 base was modelled facing up.
  const wedge = turned(prism([[0, 0], [40, 0], [0, 20]], 0, 40), rotationX(-90));
  const part = analysePart(wedge);
  const choice = autoOrient(part);
  assert.equal(choice.modelled, false);
  assert.equal(choice.overhang, 0);
  assert.ok(choice.contact >= 1599);
});

test('a face it would tip over from is never chosen, and is marked as unstable', () => {
  // A post 10 x 10 x 50 with an arm 60 long on top: standing on the post, its centre of mass
  // is out over the arm.
  const gamma = union(box(10, 10, 50), moved(box(60, 10, 10), [10, 0, 40]));
  const part = analysePart(gamma);
  const choice = autoOrient(part);
  assert.equal(choice.modelled, false);
  const standing = choice.candidates.find((c) => c.modelled);
  assert.equal(standing.stable, false);
  assert.ok(choice.stable);
});

test('the cheapest way to rest is passed over when the part would tip over from it', () => {
  // A round post 12 across and 20 tall, leaning 16 along x (39 degrees from upright, so its
  // underside hangs over nothing), with a flat cut along its upper side. Standing on either
  // end it touches over 111 mm², nothing overhangs and it is low, but its centre of mass is
  // 8 mm out from the middle of a 6 mm radius: it would fall over. Lying on the flat it is
  // stable and costs five times as much, its round underside hanging over air.
  const cut = (25 * Math.PI) / 180;
  const outline = Array.from({ length: 64 }, (_, i) => {
    const t = Math.PI + cut + ((2 * Math.PI - 2 * cut) * i) / 63;
    return [6 * Math.cos(t), 6 * Math.sin(t)];
  });
  const part = analysePart(leaning(outline, 16, 20));
  const choice = autoOrient(part);
  const modelled = choice.candidates.find((c) => c.modelled);
  assert.equal(modelled.stable, false);
  assert.equal(modelled.overhang, 0);
  assert.ok(modelled.contact >= 25);
  const cheapest = Math.min(...choice.candidates.map((c) => c.cost));
  assert.equal(modelled.cost, cheapest);
  assert.equal(choice.modelled, false);
  assert.ok(choice.stable);
  assert.ok(choice.cost > modelled.cost, `chosen ${choice.cost}, standing ${modelled.cost}`);
  // The flat cut, facing up and away from the lean, is the one stable way.
  assert.ok(close(choice.normal, [-20 / Math.hypot(16, 20), 0, 16 / Math.hypot(16, 20)], 1e-6));
  assert.equal(choice.counted, choice.candidates.filter((c) => c.stable && c.contact >= 25).length);
});

test('a part lying as modelled within 5% of its best cost is left as modelled, not turned for nothing', () => {
  // A block 60 x 60 x 50 whose two bottom edges are chamfered at 30 degrees: as modelled the
  // chamfers hang over air, upside down nothing does.
  const chamfered = (w) => {
    const h = w * Math.tan(Math.PI / 6);
    return turned(prism([[w, 0], [60 - w, 0], [60, h], [60, 50], [0, 50], [0, h]], 0, 60), rotationX(90));
  };
  const part = analysePart(chamfered(0.26));
  const choice = autoOrient(part);
  const best = Math.min(...choice.candidates.filter((c) => c.stable && c.contact >= 25).map((c) => c.cost));
  const modelled = choice.candidates.find((c) => c.modelled);
  assert.ok(best < modelled.cost && modelled.cost <= 1.05 * best, `best ${best}, as modelled ${modelled.cost}`);
  assert.equal(choice.modelled, true);
  // Beyond 5% the better way is taken.
  assert.equal(autoOrient(analysePart(chamfered(3))).modelled, false);
});

test('a part with no candidate, as round as a ball, stays as modelled', () => {
  const tris = [];
  const rows = 24, cols = 48, r = 15;
  const at = (i, j) => {
    const t = (Math.PI * i) / rows, f = (2 * Math.PI * j) / cols;
    return [r * Math.sin(t) * Math.cos(f), r * Math.sin(t) * Math.sin(f), r * Math.cos(t)];
  };
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      const a = at(i, j), b = at(i + 1, j), c = at(i + 1, j + 1), d = at(i, j + 1);
      if (i > 0) tris.push([a, b, d]);
      if (i < rows - 1) tris.push([b, c, d]);
    }
  }
  const part = analysePart(meshOf(tris));
  const choice = autoOrient(part);
  assert.equal(choice.modelled, true);
  assert.equal(choice.counted, 0);
});

test('every patch carries whether the part would stand on it', () => {
  const gamma = union(box(10, 10, 50), moved(box(60, 10, 10), [10, 0, 40]));
  const part = analysePart(gamma);
  autoOrient(part);
  assert.ok(part.patches.every((p) => typeof p.stable === 'boolean'));
  assert.ok(part.patches.some((p) => p.stable === false));
});

test('the lay chosen puts the chosen face straight down', () => {
  const part = analysePart(box(10, 20, 60));
  const choice = autoOrient(part);
  assert.ok(close(down(choice, choice.normal), [0, 0, -1]));
});
