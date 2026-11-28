// What is drawn of a sliced file (src/preview/boxes.js; wizard/README-details.md, "The layer
// preview", method C of the first trial): every segment a box of six vertices of its own, the
// layers dropped while moving within the budget and never so many that a box is too tall for
// its byte, and the order the full look is drawn in.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { MAX_BOX_MM, MOVING_BUDGET, SEGMENT_VERTICES, VERTEX_BYTES, boxVertices, decimationFor, fullPieces } from '../../src/preview/boxes.js';
import { parseGcode } from '../../src/preview/gcode.js';
import { PREVIEW_UNREADABLE, PreviewError } from '../../src/preview/preview-errors.js';
import { LAYERS, gcode } from './helpers.js';

test('the budget of the look while moving and the tallest box are the trial\'s', () => {
  assert.equal(MOVING_BUDGET, 200000);
  assert.equal(MAX_BOX_MM, 5.1);
  assert.equal(VERTEX_BYTES, 12);
  assert.equal(SEGMENT_VERTICES, 6);
});

test('each segment is six vertices of a box, layer by layer', () => {
  const p = parseGcode(gcode(LAYERS));
  const { vertices, layerStart, count } = boxVertices(p);
  assert.equal(count, 6);
  assert.deepEqual([...layerStart], [0, 3, 6]);
  assert.equal(vertices.length, 6 * SEGMENT_VERTICES * VERTEX_BYTES);
  const u16 = new Uint16Array(vertices.buffer), i8 = new Int8Array(vertices.buffer);
  // The first segment, (10, 10) to (20, 10), 0.62 wide: its ends pushed out by 0.31 mm.
  assert.deepEqual([...u16.slice(0, 3)], [969, 1000, 30]);
  assert.deepEqual([...u16.slice(6, 9)], [2031, 1000, 30]);
  assert.deepEqual([i8[6], i8[7], vertices[8], vertices[9], vertices[10]], [0, 127, 62, 15, 0]);
  assert.equal(vertices[4 * VERTEX_BYTES + 10], 2 << 2, 'the fifth vertex is the bottom of the near side');
  assert.equal(vertices[2 * VERTEX_BYTES * SEGMENT_VERTICES + 10] & 3, 1, 'the third segment is infill');
  assert.equal(vertices[5 * VERTEX_BYTES * SEGMENT_VERTICES + 10] & 3, 3, 'the sixth, the brim, is a support');
});

test('a diagonal segment is pushed out along its own direction at both ends', () => {
  // (10, 10) to (13, 14): 5 mm long, along (0.6, 0.8), 0.5 mm wide, so each end moves 0.25 mm.
  const p = parseGcode(gcode(['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    '; FEATURE: Outer wall', '; LINE_WIDTH: 0.5', 'G1 X10 Y10', 'G1 X13 Y14 E1']));
  const { vertices } = boxVertices(p);
  const u16 = new Uint16Array(vertices.buffer), i8 = new Int8Array(vertices.buffer);
  const at = (v) => [...u16.slice(v * VERTEX_BYTES / 2, v * VERTEX_BYTES / 2 + 2)];
  for (let role = 0; role < 3; role++) {
    assert.deepEqual(at(role * 2), [985, 980], `the near end, role ${role}`);
    assert.deepEqual(at(role * 2 + 1), [1315, 1420], `the far end, role ${role}`);
  }
  assert.deepEqual([i8[6], i8[7]], [-102, 76], 'the normal, (-0.8, 0.6)');
});

test('a point off the plate\'s grid of hundredths is held at its edge, never wrapped', () => {
  const p = parseGcode(gcode(['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    '; FEATURE: Outer wall', '; LINE_WIDTH: 0.5', 'G1 X-3 Y10', 'G1 X700 Y10 E1']));
  const u16 = new Uint16Array(boxVertices(p).vertices.buffer);
  assert.equal(u16[0], 0);
  assert.equal(u16[6], 65535);
});

function tall(layers, height) {
  const lines = ['M83'];
  for (let l = 1; l <= layers; l++) lines.push('; CHANGE_LAYER', `; Z_HEIGHT: ${(l * height).toFixed(2)}`,
    `; LAYER_HEIGHT: ${height}`, `G1 Z${(l * height).toFixed(2)}`, '; FEATURE: Outer wall', `G1 X0 Y${l}`, `G1 X5 Y${l} E1`);
  return parseGcode(gcode(lines));
}

test('a box taller than its byte can hold is refused as unreadable, naming its layer, never clipped', () => {
  const p = tall(16, 0.4);
  assert.equal(boxVertices(p, { decimate: 8 }).vertices[9], 160, 'eight layers of 0.4 mm, in fiftieths');
  assert.throws(() => boxVertices(p, { decimate: 16 }), (error) => {
    assert.ok(error instanceof PreviewError);
    assert.equal(error.report.code, PREVIEW_UNREADABLE);
    assert.match(error.report.detail, /a box of layer 16 would be 6\.40 mm tall, over the 5\.10 mm a box can be/);
    return true;
  });
});

test('a box of exactly 5.10 mm is kept, and one of 5.12 mm, a fiftieth over, is refused', () => {
  assert.equal(boxVertices(tall(15, 0.34), { decimate: 15 }).vertices[9], 255, 'fifteen layers of 0.34 mm');
  assert.throws(() => boxVertices(tall(16, 0.32), { decimate: 16 }), /5\.12 mm tall/);
  assert.throws(() => boxVertices(tall(1, 5.2)), /a box of layer 1 would be 5\.20 mm tall/);
});

test('decimated, only every D-th layer is kept, as tall as the layers it stands for', () => {
  const { layerStart, count, vertices } = boxVertices(tall(4, 0.2), { decimate: 2 });
  assert.equal(count, 2);
  assert.deepEqual([...layerStart], [0, 0, 1, 1, 2]);
  assert.equal(vertices[9], 20, 'two layers of 0.2 mm, in fiftieths');
});

test('the look while moving drops the fewest layers that bring it within the budget', () => {
  // 8 layers of 10 segments: 80 in all, 40 at every 2nd layer, 20 at every 4th, 10 at every 8th.
  const p = { layerStart: Uint32Array.from({ length: 9 }, (_, l) => l * 10), layerZ: Float32Array.from({ length: 8 }, (_, l) => (l + 1) * 0.2) };
  assert.equal(decimationFor(p, 80), 1);
  assert.equal(decimationFor(p, 79), 2);
  assert.equal(decimationFor(p, 20), 4);
  assert.equal(decimationFor(p, 10), 8);
  assert.equal(decimationFor(p, 1), 16, 'never more than every 16th layer');
});

test('the look while moving never drops so many layers that a box is too tall to hold', () => {
  const p = { layerStart: Uint32Array.from({ length: 17 }, (_, l) => l), layerZ: Float32Array.from({ length: 16 }, (_, l) => (l + 1) * 0.4) };
  assert.equal(decimationFor(p, 1), 8);
  const thin = { layerStart: p.layerStart, layerZ: Float32Array.from({ length: 16 }, (_, l) => (l + 1) * 0.2) };
  assert.equal(decimationFor(thin, 1), 16, 'sixteen layers of 0.2 mm fit');
});

test('the full look is drawn the current layer first, then bands from the top down', () => {
  const layerStart = Uint32Array.from([0, 10, 20, 30, 40, 50]);   // five layers of ten
  assert.deepEqual(fullPieces(layerStart, 4), [[40, 50, true], [0, 40, false]]);
  assert.deepEqual(fullPieces(layerStart, 4, 20), [[40, 50, true], [20, 40, false], [0, 20, false]]);
  assert.deepEqual(fullPieces(layerStart, 3, 5), [[30, 40, true], [20, 30, false], [10, 20, false], [0, 10, false]]);
  assert.deepEqual(fullPieces(layerStart, 0), [[0, 10, true]]);
});
