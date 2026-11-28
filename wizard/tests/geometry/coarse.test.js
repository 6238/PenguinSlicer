// The coarse copy of a part the Layout view draws while it moves (src/geometry/coarse.js).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';

import { coarseCopy } from '../../src/geometry/coarse.js';
import { createGeometry } from '../../src/geometry/messages.js';
import { fileBuffer, MADE_PARTS, readMadePart, readRealPart } from './helpers.js';

function box(positions) {
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i++) {
    min[i % 3] = Math.min(min[i % 3], positions[i]);
    max[i % 3] = Math.max(max[i % 3], positions[i]);
  }
  return { min, max };
}

test('a part already within the figure is drawn as it is', () => {
  const part = readMadePart('hex-spacer.stl');
  const copy = coarseCopy(part.positions, 1000);
  assert.equal(copy.triangles, 216);
  assert.equal(copy.cells, 0);
  assert.deepEqual(Array.from(copy.positions), Array.from(Float32Array.from(part.positions)));
});

test('the largest part allowed comes down within the figure, keeping its size within a grid square', () => {
  const part = readMadePart('hub-150k.stl');
  const copy = coarseCopy(part.positions, 1600);
  assert.ok(copy.triangles <= 1600 && copy.triangles > 200, `${copy.triangles} triangles`);
  const a = box(part.positions), b = box(copy.positions);
  const square = 40 / copy.cells;
  for (let k = 0; k < 3; k++) {
    assert.ok(Math.abs(a.min[k] - b.min[k]) <= square && Math.abs(a.max[k] - b.max[k]) <= square, `axis ${k}`);
  }
});

test('a real part comes down within the figure', () => {
  const part = readRealPart('elevator-block-bottom-inner.stl');
  const copy = coarseCopy(part.positions, 1600);
  assert.ok(copy.triangles <= 1600 && copy.triangles > 50, `${copy.triangles} triangles`);
});

test('the coarse message answers through the worker as a transferred buffer, and refuses a figure that is no whole number', () => {
  const g = createGeometry();
  g.handle({ id: 1, op: 'read', key: 'hub', buffer: fileBuffer(join(MADE_PARTS, 'hub-150k.stl')), units: 'mm' });
  const { reply, transfer } = g.handle({ id: 2, op: 'coarse', key: 'hub', maxTriangles: 2000 });
  assert.equal(reply.ok, true);
  assert.ok(reply.result.positions instanceof Float32Array);
  assert.deepEqual(transfer, [reply.result.positions.buffer]);
  assert.ok(reply.result.triangles <= 2000);
  for (const [id, maxTriangles] of [[3, 0], [4, 1.5], [5, 'many']]) {
    const bad = g.handle({ id, op: 'coarse', key: 'hub', maxTriangles }).reply;
    assert.equal(bad.error.code, 'wizard.layout_failed');
  }
});
