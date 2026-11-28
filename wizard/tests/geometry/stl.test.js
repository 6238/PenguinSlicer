// Reading a binary STL without changing it: the worker's reader, bounded by the part limits and
// checking the triangle count against the file's length before it reads anything.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';

import { readBinaryStl } from '../../src/geometry/stl.js';
import { GeometryError } from '../../src/geometry/errors.js';
import { MAX_PART_BYTES } from '../../src/geometry/constants.js';
import { fileBuffer, REAL_PARTS } from './helpers.js';

function stl(triangles, { count = triangles.length, extra = 0 } = {}) {
  const buf = new ArrayBuffer(84 + 50 * triangles.length + extra);
  const view = new DataView(buf);
  view.setUint32(80, count, true);
  triangles.forEach((tri, i) => {
    tri.forEach((value, k) => view.setFloat32(84 + 50 * i + 12 + 4 * k, value, true));
  });
  return buf;
}

const ONE = [[0, 0, 0, 1, 0, 0, 0, 1, 0]];

function refusal(buffer, units = 'mm') {
  try {
    readBinaryStl(buffer, units);
  } catch (err) {
    assert.ok(err instanceof GeometryError, `not a GeometryError: ${err}`);
    assert.equal(err.report.code, 'wizard.part_not_drawable');
    assert.equal(err.report.retryable, false);
    assert.ok(err.report.message.length > 0 && err.report.remedy.length > 0);
    return err.report.detail;
  }
  assert.fail('the file was read');
}

test('a real part is read with every triangle, and its bytes are left as they were', () => {
  const buffer = fileBuffer(join(REAL_PARTS, 'pulley-v3.stl'));
  const before = new Uint8Array(buffer.slice(0));
  const mesh = readBinaryStl(buffer, 'mm');
  assert.equal(mesh.triangles, 4608);
  assert.equal(mesh.positions.length, 4608 * 9);
  assert.deepEqual(new Uint8Array(buffer), before);
  // The README gives its size as 17.78 x 19.05 x 19.05 mm.
  const size = [0, 1, 2].map((k) => mesh.max[k] - mesh.min[k]);
  assert.deepEqual(size.map((s) => s.toFixed(2)), ['17.78', '19.05', '19.05']);
});

test('an inch part is measured in millimetres, in memory only', () => {
  const mesh = readBinaryStl(stl([[0, 0, 0, 1, 0, 0, 0, 2, 0]]), 'in');
  assert.deepEqual(Array.from(mesh.positions), [0, 0, 0, 25.4, 0, 0, 0, 50.8, 0]);
});

test('units other than mm and in are refused by the code that asks, not guessed', () => {
  assert.throws(() => readBinaryStl(stl(ONE), 'cm'), /units/);
});

test('a file shorter than the header cannot be drawn', () => {
  assert.match(refusal(new ArrayBuffer(83)), /83 bytes/);
});

test('a file cut off before its last triangle cannot be drawn', () => {
  assert.match(refusal(stl(ONE, { count: 2 })), /2 triangles/);
});

test('a file padded after its last triangle cannot be drawn', () => {
  assert.match(refusal(stl(ONE, { extra: 7 })), /141 bytes/);
});

test('a file with no triangles cannot be drawn', () => {
  assert.match(refusal(stl([])), /no triangles/);
});

test('a file over the size limit is refused before it is read', () => {
  assert.match(refusal(new ArrayBuffer(MAX_PART_BYTES + 1)), /7500085 bytes/);
});

test('a header claiming more triangles than the limit is refused, whatever the length says', () => {
  assert.match(refusal(stl(ONE, { count: 0xffffffff })), /4294967295 triangles/);
});

test('a coordinate that is not a finite number cannot be drawn', () => {
  assert.match(refusal(stl([[0, 0, 0, NaN, 0, 0, 0, 1, 0]])), /triangle 1/);
  assert.match(refusal(stl([[0, 0, 0, 1, 0, 0, 0, Infinity, 0]])), /triangle 1/);
});
