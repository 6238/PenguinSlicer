// The worker's half of the layer preview (src/preview/reading.js, run by src/preview.worker.js;
// wizard/README-details.md, "The layer preview"): one message gives the sliced file's bytes and
// the plate's instances with their parts' corners, and the reply holds everything the page
// uploads as it is, with its buffers transferred; progress reports on the way; every failure the
// wizard's own error report. Run here in the test's own thread, on real sliced files.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { MOVING_BUDGET, SEGMENT_VERTICES, VERTEX_BYTES } from '../../src/preview/boxes.js';
import { PREVIEW_FAILED, PREVIEW_UNREADABLE } from '../../src/preview/preview-errors.js';
import { createPreviewReading } from '../../src/preview/reading.js';
import { readBinaryStl } from '../../src/geometry/stl.js';
import { LAYERS, REAL_PARTS, corners, slicedFile, slicedOf, slicedPlate } from './helpers.js';

async function prepare(message) {
  const posted = [];
  const reading = createPreviewReading();
  const { reply, transfer } = await reading.handle({ id: 7, op: 'prepare', ...message }, (m) => posted.push(m));
  return { reply, transfer, posted };
}

// A part's corners for drawing, as the geometry client gives them: a Float32Array in millimetres.
function partCorners(file) {
  const b = readFileSync(file);
  return new Float32Array(readBinaryStl(b.buffer.slice(b.byteOffset, b.byteOffset + b.length), 'mm').positions);
}
const PART_FILES = {
  'hex-spacer': join(REAL_PARTS, '..', '..', '..', '..', 'wizard', 'trials', 'parts', 'hex-spacer.stl'),
  'elevator-block-top': join(REAL_PARTS, 'elevator-block-top.stl'),
  'elevator-block-carriage': join(REAL_PARTS, 'elevator-block-carriage.stl'),
};
function plateOf(name) {
  const plate = slicedPlate(name);
  const meshes = Object.fromEntries(Object.keys(plate.parts).map((ref) => [ref, partCorners(PART_FILES[ref])]));
  return { instances: plate.instances, meshes };
}

test('a real sliced file with supports is prepared: both looks, the ghost, the layers and its figures', async () => {
  const bytes = slicedFile('pair-supports');
  const { reply, transfer } = await prepare({ bytes, plate: plateOf('pair-supports') });
  assert.equal(reply.id, 7);
  assert.equal(reply.ok, true, JSON.stringify(reply.error));
  const r = reply.result;
  assert.equal(r.layers, 132);
  assert.equal(r.layerZ.length, 132);
  assert.ok(r.groups.every((n) => n > 0), `every group drawn: ${r.groups}`);
  assert.equal(r.full.count, r.groups.reduce((a, b) => a + b, 0));
  assert.equal(r.full.vertices.byteLength, r.full.count * SEGMENT_VERTICES * VERTEX_BYTES);
  assert.equal(r.full.layerStart.length, 133);
  // The coarser reading of the arcs and runs alone brings it under the budget: no layer dropped.
  assert.equal(r.decimate, 1);
  assert.ok(r.moving.count <= MOVING_BUDGET && r.moving.count < r.full.count, `${r.moving.count} boxes while moving, ${r.full.count} at rest`);
  assert.equal(r.moving.layerStart.length, 133);
  assert.equal(r.ghost.bounds.length, 2 * 6);
  assert.ok(r.ghost.corners.length > 0);
  assert.deepEqual(r.stats, { sliced_file_bytes: bytes.byteLength, sliced_file_lines: r.stats.sliced_file_lines, segments: r.full.count, instances: 2 });
  assert.ok(r.stats.sliced_file_lines > 200000);
  for (const buffer of [r.full.vertices.buffer, r.full.layerStart.buffer, r.moving.vertices.buffer, r.moving.layerStart.buffer, r.ghost.corners.buffer, r.ghost.bounds.buffer, r.layerZ.buffer]) {
    assert.ok(transfer.includes(buffer), 'every buffer of the reply is transferred, never copied');
  }
});

test('a real sliced file of a few layers keeps every layer while moving', async () => {
  const { reply } = await prepare({ bytes: slicedFile('spacer-1'), plate: plateOf('spacer-1') });
  assert.equal(reply.ok, true, JSON.stringify(reply.error));
  assert.equal(reply.result.layers, 13);
  assert.equal(reply.result.decimate, 1);
  assert.equal(reply.result.groups[3], 0, 'supports off: no supports');
  // The ghost of the spacer stands on the plate where the plate configuration put it.
  const b = reply.result.ghost.bounds;
  assert.ok(Math.abs((b[0] + b[3]) / 2 - 170) < 1e-3 && Math.abs((b[1] + b[4]) / 2 - 160) < 1e-3 && b[2] === 0, [...b].join(', '));
});

test('the toolpaths and the ghost agree on where the plate\'s instances are', async () => {
  const { reply } = await prepare({ bytes: slicedFile('pair-supports'), plate: plateOf('pair-supports') });
  const r = reply.result, u16 = new Uint16Array(r.full.vertices.buffer);
  let minX = Infinity, maxX = -Infinity;
  for (let v = 0; v < r.full.count * SEGMENT_VERTICES; v += 1) {
    const flags = r.full.vertices[v * VERTEX_BYTES + 10];
    if ((flags & 3) !== 0) continue;                               // the walls: the parts' own outline
    const x = u16[v * VERTEX_BYTES / 2] / 100;
    minX = Math.min(minX, x); maxX = Math.max(maxX, x);
  }
  const b = r.ghost.bounds;
  assert.ok(Math.abs(minX - b[0]) < 1.5, `walls from ${minX}, ghost from ${b[0]}`);
  assert.ok(Math.abs(maxX - b[9]) < 1.5, `walls to ${maxX}, ghost to ${b[9]}`);
});

test('progress is reported from start to finish: unpacking, reading with how far, preparing', async () => {
  const { posted, reply } = await prepare({ bytes: slicedFile('pair-supports'), plate: null });
  assert.equal(reply.ok, true);
  assert.ok(posted.every((m) => m.id === 7 && m.progress), 'each report names the message it is for');
  const stages = [...new Set(posted.map((m) => m.progress.stage))];
  assert.deepEqual(stages, ['unpacking', 'reading', 'preparing']);
  const reading = posted.filter((m) => m.progress.stage === 'reading').map((m) => m.progress.fraction);
  assert.ok(reading.length >= 4 && reading.at(-1) === 1, reading.join(', '));
  for (const m of posted) if (m.progress.stage !== 'reading') assert.equal(m.progress.fraction, null, 'no fraction is invented');
});

test('a sliced file without a plate is drawn without a ghost', async () => {
  const { reply } = await prepare({ bytes: slicedOf(LAYERS), plate: null });
  assert.equal(reply.ok, true);
  assert.equal(reply.result.ghost.corners.length, 0);
  assert.equal(reply.result.stats.instances, 0);
  assert.equal(reply.result.layers, 2);
});

test('a sliced file that is not an archive, or whose G-code has no layers, is refused as unreadable', async () => {
  const notZip = await prepare({ bytes: new TextEncoder().encode('words').buffer, plate: null });
  assert.equal(notZip.reply.ok, false);
  assert.equal(notZip.reply.id, 7);
  assert.equal(notZip.reply.error.code, PREVIEW_UNREADABLE);
  assert.equal(notZip.reply.error.message, 'PenguinSlicer could not read this plate\'s sliced file to draw its preview.');
  assert.match(notZip.reply.error.detail, /not a zip archive/);
  const empty = await prepare({ bytes: slicedOf(['M83', 'G1 X1 Y1 E1']), plate: null });
  assert.equal(empty.reply.error.code, PREVIEW_UNREADABLE);
  assert.match(empty.reply.error.detail, /the G-code has no layers/);
});

test('a sliced file whose layers hold no extrusion has nothing to draw and is refused as unreadable', async () => {
  const { reply } = await prepare({ bytes: slicedOf(['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2', 'G1 X5 Y5']), plate: null });
  assert.equal(reply.ok, false);
  assert.equal(reply.error.code, PREVIEW_UNREADABLE);
  assert.match(reply.error.detail, /1 layer but no extrusion to draw/);
});

test('a sliced file over the budget of the look while moving drops layers for it, every group standing for its layers', async () => {
  // 40 layers of 6,000 zigzag segments, none of which the coarser reading can merge: 240,000 boxes,
  // over the budget, so every second layer is kept while moving, each box two layers tall.
  const lines = ['M83'];
  for (let l = 1; l <= 40; l++) {
    lines.push('; CHANGE_LAYER', `; Z_HEIGHT: ${(l * 0.2).toFixed(1)}`, '; LAYER_HEIGHT: 0.2', `G1 Z${(l * 0.2).toFixed(1)}`, '; FEATURE: Sparse infill', 'G1 X0 Y0');
    for (let s = 1; s <= 6000; s++) lines.push(`G1 X${s % 2 ? 10 : 0} Y${(s * 0.04).toFixed(2)} E.1`);
  }
  const { reply } = await prepare({ bytes: slicedOf(lines), plate: null });
  assert.equal(reply.ok, true, JSON.stringify(reply.error));
  const r = reply.result;
  assert.equal(r.full.count, 240000);
  assert.equal(r.decimate, 2);
  assert.equal(r.moving.count, 120000);
  assert.ok(r.moving.count <= MOVING_BUDGET);
  assert.equal(r.moving.layerStart[1], 0, 'the first layer is dropped while moving');
  assert.equal(r.moving.layerStart[2], 6000);
  assert.equal(r.moving.vertices[9], 20, 'each box two layers of 0.2 mm tall, in fiftieths');
});

test('a message the reading does not know, or without bytes, is the page\'s own fault', async () => {
  const reading = createPreviewReading();
  const unknown = await reading.handle({ id: 1, op: 'draw' }, () => {});
  assert.equal(unknown.reply.error.code, PREVIEW_FAILED);
  assert.match(unknown.reply.error.detail, /no message "draw"/);
  const noBytes = await reading.handle({ id: 2, op: 'prepare', bytes: 'abc', plate: null }, () => {});
  assert.equal(noBytes.reply.error.code, PREVIEW_FAILED);
  assert.match(noBytes.reply.error.detail, /bytes must be an ArrayBuffer/);
  const badPlate = await prepare({ bytes: slicedOf(LAYERS), plate: { instances: [{ ref: 'x', orientation: '+z', angle: 0, x: 0, y: 0 }], meshes: { a: corners([[0, 0, 0, 1, 0, 0, 0, 1, 0]]) } } });
  assert.equal(badPlate.reply.error.code, PREVIEW_FAILED);
  assert.equal(badPlate.reply.error.message, 'PenguinSlicer could not draw the layer preview of this plate.');
  assert.equal(badPlate.reply.error.remedy, 'Reload the page; your parts, layout and settings are kept in this browser.');
});

test('the reading\'s own code failing is the page\'s fault, with the error in its detail', async () => {
  const reading = createPreviewReading({ parse: () => { throw new RangeError('out of room'); } });
  const { reply } = await reading.handle({ id: 3, op: 'prepare', bytes: slicedOf(LAYERS), plate: null }, () => {});
  assert.equal(reply.error.code, PREVIEW_FAILED);
  assert.equal(reply.error.detail, 'RangeError: out of room');
});
