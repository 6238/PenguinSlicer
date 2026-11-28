// A part's picture (src/geometry/picture.js): the small picture on a part's row, drawn in the
// worker from the part as read, flat shaded in the part's colour, seen from the front, the right
// and above as the mockup's pictures are, on a transparent ground; and the worker's `picture`
// message that hands it to the main thread as a transferred buffer.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';

import { createGeometry } from '../../src/geometry/messages.js';
import { MAX_PICTURE_PX, MIN_PICTURE_PX, drawPicture } from '../../src/geometry/picture.js';
import { fileBuffer, readRealPart, REAL_PARTS } from './helpers.js';
import { prism } from './shapes.js';

const COLOUR = 0x9fb4c8;
const cube = () => prism([[0, 0], [20, 0], [20, 20], [0, 20]], 0, 20);
const at = (picture, x, y) => [...picture.pixels.subarray((y * picture.width + x) * 4, (y * picture.width + x) * 4 + 4)];

function opaqueBox(picture) {
  let minX = Infinity, minY = Infinity, maxX = -1, maxY = -1;
  for (let y = 0; y < picture.height; y++) {
    for (let x = 0; x < picture.width; x++) {
      if (at(picture, x, y)[3] > 0) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y); }
    }
  }
  return { minX, minY, maxX, maxY };
}

test('a picture is px by px, its corners transparent and its middle the part, opaque', () => {
  const picture = drawPicture(cube(), { px: 88, colour: COLOUR });
  assert.equal(picture.width, 88);
  assert.equal(picture.height, 88);
  assert.ok(picture.pixels instanceof Uint8ClampedArray);
  assert.equal(picture.pixels.length, 88 * 88 * 4);
  assert.deepEqual(at(picture, 0, 0), [0, 0, 0, 0]);
  assert.deepEqual(at(picture, 87, 87), [0, 0, 0, 0]);
  assert.equal(at(picture, 44, 44)[3], 255);
});

test('the part fills the picture, with a margin, and none of it is cut off at an edge', () => {
  const picture = drawPicture(readRealPart('outer-clamp.stl'), { px: 88, colour: COLOUR });
  const box = opaqueBox(picture);
  assert.ok(box.minX > 0 && box.minY > 0 && box.maxX < 87 && box.maxY < 87, JSON.stringify(box));
  assert.ok(Math.max(box.maxX - box.minX, box.maxY - box.minY) > 88 * 0.5, JSON.stringify(box));
});

test('the faces are shaded by the light: three sides of a cube in sight, each its own shade of the part\'s colour', () => {
  const picture = drawPicture(cube(), { px: 88, colour: COLOUR });
  const shades = new Set();
  for (let i = 0; i < picture.pixels.length; i += 4) {
    if (picture.pixels[i + 3] === 255) shades.add(`${picture.pixels[i]},${picture.pixels[i + 1]},${picture.pixels[i + 2]}`);
  }
  const counts = {};
  for (let i = 0; i < picture.pixels.length; i += 4) {
    if (picture.pixels[i + 3] !== 255) continue;
    const key = `${picture.pixels[i]},${picture.pixels[i + 1]},${picture.pixels[i + 2]}`;
    counts[key] = (counts[key] || 0) + 1;
  }
  const large = Object.values(counts).filter((n) => n > 100);
  assert.equal(large.length, 3, JSON.stringify(counts));
  // The colour is the part's: blue the largest channel of every face, as in 0x9fb4c8.
  for (const key of Object.keys(counts)) {
    if (counts[key] <= 100) continue;
    const [r, g, b] = key.split(',').map(Number);
    assert.ok(b >= g && g >= r, key);
  }
});

test('a part read in inches draws as the same part read in millimetres: only its size differs', () => {
  const g = createGeometry();
  const buffer = fileBuffer(join(REAL_PARTS, 'inner-spacer.stl'));
  g.handle({ id: 1, op: 'read', key: 'mm', buffer, units: 'mm' });
  g.handle({ id: 2, op: 'read', key: 'in', buffer, units: 'in' });
  const mm = g.handle({ id: 3, op: 'picture', key: 'mm', px: 64, colour: COLOUR }).reply.result;
  const inch = g.handle({ id: 4, op: 'picture', key: 'in', px: 64, colour: COLOUR }).reply.result;
  let differ = 0;
  for (let i = 0; i < mm.pixels.length; i++) if (Math.abs(mm.pixels[i] - inch.pixels[i]) > 2) differ += 1;
  assert.ok(differ < mm.pixels.length * 0.002, `${differ} values differ`);
});

test('the same part draws the same picture each time', () => {
  const a = drawPicture(cube(), { px: 48, colour: COLOUR });
  const b = drawPicture(cube(), { px: 48, colour: COLOUR });
  assert.deepEqual(a.pixels, b.pixels);
});

test('a part with no size draws an empty picture, not a failure', () => {
  const point = { triangles: 1, positions: new Float64Array(9).fill(5), min: [5, 5, 5], max: [5, 5, 5] };
  const picture = drawPicture(point, { px: 32, colour: COLOUR });
  assert.ok(picture.pixels.every((v) => v === 0));
});

test('the worker\'s picture message answers the picture as a transferred buffer', () => {
  const g = createGeometry();
  g.handle({ id: 1, op: 'read', key: 'pulley', buffer: fileBuffer(join(REAL_PARTS, 'pulley-v3.stl')), units: 'mm' });
  const { reply, transfer } = g.handle({ id: 2, op: 'picture', key: 'pulley', px: 88, colour: COLOUR });
  assert.equal(reply.ok, true);
  assert.equal(reply.result.width, 88);
  assert.ok(reply.result.pixels instanceof Uint8ClampedArray);
  assert.deepEqual(transfer, [reply.result.pixels.buffer]);
});

test('a picture of a part never read, or of a size out of bounds, is the page\'s fault: wizard.layout_failed', () => {
  const g = createGeometry();
  const never = g.handle({ id: 1, op: 'picture', key: 'nothing', px: 88, colour: COLOUR }).reply;
  assert.equal(never.ok, false);
  assert.equal(never.error.code, 'wizard.layout_failed');
  g.handle({ id: 2, op: 'read', key: 'pulley', buffer: fileBuffer(join(REAL_PARTS, 'pulley-v3.stl')), units: 'mm' });
  for (const px of [MIN_PICTURE_PX - 1, MAX_PICTURE_PX + 1, 40.5, '88']) {
    const reply = g.handle({ id: 3, op: 'picture', key: 'pulley', px, colour: COLOUR }).reply;
    assert.equal(reply.ok, false, String(px));
    assert.equal(reply.error.code, 'wizard.layout_failed');
    assert.match(reply.error.detail, /px/);
  }
  const badColour = g.handle({ id: 4, op: 'picture', key: 'pulley', px: 88, colour: -1 }).reply;
  assert.equal(badColour.ok, false);
  assert.match(badColour.error.detail, /colour/);
});
