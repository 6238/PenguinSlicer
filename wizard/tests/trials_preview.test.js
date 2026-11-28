// The layer preview trial's reading of a sliced file (wizard/trials/preview/gcode.js): the
// archive, the G-code's layers, line types, widths and moves, arcs and merged runs.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { deflateRawSync, crc32 } from 'node:zlib';
import { readZipEntry, parseGcode, GROUPS, groupOf } from '../trials/preview/gcode.js';
import { decimationFor } from '../trials/preview/methods-prepare.js';
import { readStl, placeInstance, ghostOf, boxes, cull, fullPieces, boxVertices, VERTEX_BYTES, SEGMENT_VERTICES } from '../trials/preview/prepare.js';
import { sortPixels, changedShare, BACKGROUND, COLOURS } from '../trials/preview/look.js';

// A zip of `entries` ({name: string or bytes}), deflated unless `stored`.
function zip(entries, stored = false) {
  const local = [], central = [];
  let offset = 0;
  for (const [name, content] of Object.entries(entries)) {
    const data = Buffer.from(content);
    const body = stored ? data : deflateRawSync(data);
    const nameBytes = Buffer.from(name);
    const head = Buffer.alloc(30);
    head.writeUInt32LE(0x04034b50, 0); head.writeUInt16LE(20, 4); head.writeUInt16LE(stored ? 0 : 8, 8);
    head.writeUInt32LE(crc32(data), 14); head.writeUInt32LE(body.length, 18); head.writeUInt32LE(data.length, 22);
    head.writeUInt16LE(nameBytes.length, 26);
    const dir = Buffer.alloc(46);
    dir.writeUInt32LE(0x02014b50, 0); dir.writeUInt16LE(20, 4); dir.writeUInt16LE(20, 6); dir.writeUInt16LE(stored ? 0 : 8, 10);
    dir.writeUInt32LE(crc32(data), 16); dir.writeUInt32LE(body.length, 20); dir.writeUInt32LE(data.length, 24);
    dir.writeUInt16LE(nameBytes.length, 28); dir.writeUInt32LE(offset, 42);
    local.push(head, nameBytes, body);
    central.push(dir, nameBytes);
    offset += 30 + nameBytes.length + body.length;
  }
  const dirBytes = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(central.length / 2, 8); end.writeUInt16LE(central.length / 2, 10);
  end.writeUInt32LE(dirBytes.length, 12); end.writeUInt32LE(offset, 16);
  return new Uint8Array(Buffer.concat([...local, dirBytes, end]));
}

const text = (bytes) => new TextDecoder().decode(bytes);
const gcode = (lines) => new TextEncoder().encode(lines.join('\n') + '\n');

test('an entry of the archive is read, deflated or stored', async () => {
  const archive = zip({ 'Metadata/plate_1.json': '{"a":1}', 'Metadata/plate_1.gcode': 'G1 X1\n'.repeat(1000) });
  assert.equal(text(await readZipEntry(archive, 'Metadata/plate_1.gcode')), 'G1 X1\n'.repeat(1000));
  assert.equal(text(await readZipEntry(zip({ 'a.txt': 'plain' }, true), 'a.txt')), 'plain');
});

test('an archive without the entry, or not an archive, says so', async () => {
  await assert.rejects(readZipEntry(zip({ 'a.txt': 'x' }), 'Metadata/plate_1.gcode'),
    { message: 'The sliced file has no Metadata/plate_1.gcode.' });
  await assert.rejects(readZipEntry(new TextEncoder().encode('not a zip at all, just words'), 'a.txt'),
    { message: 'The sliced file is not a zip archive.' });
});

const LAYERS = [
  'M83', 'G90',
  '; FEATURE: Custom', 'G1 X0 Y0 E5', 'G1 X100 Y0 E5',          // the prime line, before the first layer
  '; CHANGE_LAYER', '; Z_HEIGHT: 0.3', '; LAYER_HEIGHT: 0.3', 'G1 Z.3',
  '; FEATURE: Outer wall', '; LINE_WIDTH: 0.62', 'G1 X10 Y10 F3000', 'G1 X20 Y10 E1', 'G1 X20 Y20 E1',
  '; WIPE_START', 'G1 X20 Y15 E-.2', '; WIPE_END',
  'G1 X30 Y30', '; FEATURE: Sparse infill', '; LINE_WIDTH: 0.45', 'G1 X40 Y30 E.5',
  '; CHANGE_LAYER', '; Z_HEIGHT: 0.54', '; LAYER_HEIGHT: 0.24', 'G1 Z.54',
  '; FEATURE: Top surface', 'G1 X50 Y30 E.5', '; FEATURE: Support', 'G1 X50 Y40 E.5',
  '; FEATURE: Brim', 'G1 X60 Y40 E.5', '; FEATURE: Inner wall', 'G1 X60 Y40 E.5',   // no move: no segment
];

test('each extrusion after the first layer change is a segment of its layer, type and width', () => {
  const p = parseGcode(gcode(LAYERS));
  assert.equal(p.count, 6);
  assert.deepEqual([...p.layerStart], [0, 3, 6]);
  assert.deepEqual([...p.layerZ].map((z) => +z.toFixed(2)), [0.3, 0.54]);
  assert.deepEqual([...p.layerHeight].map((h) => +h.toFixed(2)), [0.3, 0.24]);
  assert.deepEqual([...p.x0], [10, 20, 30, 40, 50, 50]);
  assert.deepEqual([...p.y1], [10, 20, 30, 30, 40, 40]);
  assert.deepEqual([...p.group].map((g) => GROUPS[g]), ['walls', 'walls', 'infill', 'surfaces', 'supports', 'supports']);
  assert.deepEqual([...p.width].map((w) => +w.toFixed(2)), [0.62, 0.62, 0.45, 0.45, 0.45, 0.45]);
  assert.deepEqual([...p.z].map((z) => +z.toFixed(2)), [0.3, 0.3, 0.3, 0.54, 0.54, 0.54]);
});

test('every line type of Orca is in one of the four groups', () => {
  const expected = {
    'Outer wall': 'walls', 'Inner wall': 'walls', 'Overhang wall': 'walls',
    'Sparse infill': 'infill', 'Internal solid infill': 'infill', 'Gap infill': 'infill', 'Internal Bridge': 'infill',
    'Top surface': 'surfaces', 'Bottom surface': 'surfaces', 'Bridge': 'surfaces', 'Ironing': 'surfaces',
    'Support': 'supports', 'Support interface': 'supports', 'Support transition': 'supports', 'Brim': 'supports',
    'Skirt': 'supports', 'Prime tower': 'supports', 'Custom': 'supports', 'Something new': 'walls',
  };
  for (const [feature, group] of Object.entries(expected)) assert.equal(GROUPS[groupOf(feature)], group, feature);
});

test('straight runs of one type are merged, and a turn ends the run', () => {
  const p = parseGcode(gcode(['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    '; FEATURE: Outer wall', 'G1 X0 Y0', 'G1 X1 Y0 E.1', 'G1 X2 Y0.001 E.1', 'G1 X3 Y0 E.1', 'G1 X3 Y5 E.1',
    '; FEATURE: Inner wall', 'G1 X3 Y9 E.1']));
  assert.deepEqual([...p.x0], [0, 3, 3]);
  assert.deepEqual([...p.y0], [0, 0, 5]);
  assert.deepEqual([...p.x1], [3, 3, 3]);
  assert.deepEqual([...p.y1], [0, 5, 9]);
  assert.equal(p.moves, 5);
});

test('an arc becomes chords within the tolerance, ending exactly at its end', () => {
  // A half circle of radius 10 about (10, 0), counterclockwise from (0, 0) to (20, 0) through (10, -10).
  const lines = ['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    '; FEATURE: Outer wall', 'G1 X0 Y0', 'G3 X20 Y0 I10 J0 E2'];
  const p = parseGcode(gcode(lines), { arcTolerance: 0.02 });
  const chords = p.count;
  assert.ok(chords >= 20 && chords <= 30, `${chords} chords`);
  assert.equal(p.x1[chords - 1], 20);
  assert.equal(p.y1[chords - 1], 0);
  for (let k = 0; k < chords; k++) {
    const mx = (p.x0[k] + p.x1[k]) / 2, my = (p.y0[k] + p.y1[k]) / 2;
    assert.ok(my <= 1e-6, 'counterclockwise from (0, 0) goes below the centre');
    assert.ok(10 - Math.hypot(mx - 10, my) <= 0.021, 'the chord stays within the tolerance');
  }
  const clockwise = parseGcode(gcode(lines.slice(0, -1).concat(['G2 X20 Y0 I10 J0 E2'])));
  assert.ok(clockwise.y0[1] > 0, 'clockwise goes above');
});

test('absolute extrusion, a reset of E and relative moves are followed', () => {
  const p = parseGcode(gcode(['M82', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    '; FEATURE: Inner wall', 'G1 X0 Y0 E1', 'G1 X0 Y5 E2', 'G1 X5 Y5 E1.5', 'G92 E0', 'G1 X9 Y5 E0.5',
    'G91', 'G1 X1 Y1 E1', 'G90', 'G1 X0 Y0 E1']));
  // (0,0)-(0,5) extrudes; (0,5)-(5,5) retracts; after the reset (5,5)-(9,5) extrudes; relative
  // X and Y (9,5)-(10,6) with E still absolute; back at (0,0) E has not grown, so no segment.
  assert.deepEqual([...p.x1], [0, 9, 10]);
  assert.deepEqual([...p.y1], [5, 5, 6]);
});

// A binary STL of the given triangles (each nine numbers).
function stl(triangles) {
  const b = Buffer.alloc(84 + 50 * triangles.length);
  b.writeUInt32LE(triangles.length, 80);
  triangles.forEach((t, k) => t.forEach((v, j) => b.writeFloatLE(v, 84 + 50 * k + 12 + 4 * j)));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.length);
}

test('a part is placed as the contract places an instance', () => {
  // One triangle spanning x 0..10, y 0..4, z 2..6.
  const corners = readStl(stl([[0, 0, 2, 10, 0, 2, 10, 4, 6]]));
  assert.deepEqual([...corners], [0, 0, 2, 10, 0, 2, 10, 4, 6]);
  // +z, turned 90 degrees, footprint centre (5, 2) to (100, 50), lowest z (2) to 0.
  const turned = placeInstance(corners, { orientation: '+z', angle: 90, x: 100, y: 50 });
  assert.deepEqual([...turned].map((v) => +v.toFixed(4)), [102, 45, 0, 102, 55, 0, 98, 55, 4]);
  // -z: y and z change sign: y 0..-4, z -2..-6, so the footprint centre is (5, -2) and the lowest z -6.
  const flipped = placeInstance(corners, { orientation: '-z', angle: 0, x: 0, y: 0 });
  assert.deepEqual([...flipped].map((v) => +v.toFixed(4)), [-5, 2, 4, 5, 2, 4, 5, -2, 0]);
  assert.throws(() => placeInstance(corners, { orientation: 'up', angle: 0, x: 0, y: 0 }), /Unknown orientation up/);
  assert.throws(() => readStl(stl([[0, 0, 0, 1, 0, 0, 0, 1, 0]]).slice(0, 100)), /not a whole binary STL/);
});

test('the ghost holds every instance of the plate, each part found by its key', () => {
  const corners = readStl(stl([[0, 0, 0, 1, 0, 0, 0, 1, 1]]));
  const plate = { parts: { a: { name: 'A', sha256: '0'.repeat(64), units: 'mm' } },
    instances: [{ ref: 'a', orientation: '+z', angle: 0, x: 10, y: 10 }, { ref: 'a', orientation: '+z', angle: 0, x: 30, y: 10 }] };
  const ghost = ghostOf(plate, { a: corners });
  assert.equal(ghost.corners.length, 18);
  assert.equal(ghost.corners[9], 29.5);
  assert.deepEqual([...ghost.bounds], [9.5, 9.5, 0, 10.5, 10.5, 1, 29.5, 9.5, 0, 30.5, 10.5, 1]);
});

test('a part in inches is scaled to millimetres before it is placed', () => {
  const corners = readStl(stl([[0, 0, 0, 1, 0, 0, 0, 1, 1]]));
  const plate = { parts: { a: { name: 'A', sha256: '0'.repeat(64), units: 'in' } },
    instances: [{ ref: 'a', orientation: '+z', angle: 0, x: 100, y: 100 }] };
  const { bounds } = ghostOf(plate, { a: corners });
  assert.deepEqual([...bounds].map((v) => +v.toFixed(3)), [87.3, 87.3, 0, 112.7, 112.7, 25.4]);
});

test('the look is sorted into the background, the four colours and the walls\' shades', () => {
  const bg = BACKGROUND.map((v) => Math.round(v * 255));
  const colour = (g, shade = 1) => COLOURS[g].map((v) => Math.round(v * shade * 255));
  const pixels = [bg, bg, bg, bg, colour(0), colour(0, 0.7), colour(1), colour(2), colour(3), [255, 0, 0]];
  const px = new Uint8Array(pixels.flatMap((c) => [...c, 255]));
  const look = sortPixels(px);
  assert.equal(look.covered, 0.6);
  assert.deepEqual(look.groups, [0.2, 0.1, 0.1, 0.1]);
});

test('the share of the view two looks differ in counts every pixel that changed', () => {
  const a = new Uint8Array([1, 2, 3, 255, 1, 2, 3, 255, 1, 2, 3, 255, 1, 2, 3, 255]);
  const b = Uint8Array.from(a);
  assert.equal(changedShare(a, b), 0);
  b[2] = 9; b[12] = 0;
  assert.equal(changedShare(a, b), 0.5);
  b[7] = 0;                                    // the alpha byte is not a colour
  assert.equal(changedShare(a, b), 0.5);
});

test('each segment is packed as eight floats for the box methods', () => {
  const p = parseGcode(gcode(LAYERS));
  const packed = boxes(p);
  assert.equal(packed.length, 48);
  assert.deepEqual([...packed.slice(0, 8)].map((v) => +v.toFixed(2)), [10, 10, 20, 10, 0.3, 0.62, 0.3, 0]);
});

// A block of layers, each { lines, gap, closed, skip }: `lines` parallel lines 10 mm long at
// (50, 50), 0.5 mm wide and `gap` mm apart, closed at both ends by a line across when `closed`,
// the lines numbered in `skip` left out.
function block(layers) {
  const w = 0.5, g = ['M83'];
  layers.forEach(({ lines = 3, gap = 0, closed = true, skip = [] }, l) => {
    g.push('; CHANGE_LAYER', `; Z_HEIGHT: ${(l + 1) * 0.2}`, '; LAYER_HEIGHT: 0.2', `G1 Z${(l + 1) * 0.2}`,
      '; FEATURE: Internal solid infill', `; LINE_WIDTH: ${w}`);
    for (let i = 0; i < lines; i++) {
      if (skip.includes(i)) continue;
      const y = 50 + i * (w + gap);
      g.push(`G1 X50 Y${y}`, `G1 X60 Y${y} E1`);
    }
    const top = 50 + (lines - 1) * (w + gap);
    if (closed) g.push(`G1 X${50 - w} Y${50 - w}`, `G1 X${50 - w} Y${top + w} E1`, `G1 X${60 + w} Y${50 - w}`, `G1 X${60 + w} Y${top + w} E1`);
  });
  return parseGcode(gcode(g));
}
const solid = { lines: 3 };

test('a segment no air reaches is hidden, and no other', () => {
  // Layer 0 lies on the plate: its middle line is enclosed. Layer 1's middle line too. Layer 2,
  // the top, the outside lines and the closing lines are seen.
  assert.deepEqual([...cull(block([solid, solid, solid]))], [1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1]);
});

test('a line whose end is open is seen', () => {
  const open = { lines: 3, closed: false };
  assert.ok(cull(block([open, open, open])).every((v) => v === 1));
});

test('lines over an open channel, as sparse infill has under the top layer, are all seen', () => {
  const sparse = { lines: 3, gap: 2 };
  assert.ok(cull(block([sparse, sparse, sparse])).every((v) => v === 1));
});

test('lines round a void closed on every side are hidden, as sparse infill under a top surface is', () => {
  const sparse = { lines: 3, gap: 2 }, lid = { lines: 11 };     // 11 lines 0.5 mm apart span the 5 mm
  const keep = cull(block([sparse, sparse, lid, lid]));
  // Layers 0 and 1: the outside lines and the closing lines are seen; the middle lines face
  // only the closed void. The lid's lower layer is enclosed but for its outside lines.
  assert.deepEqual([...keep.slice(0, 5)], [1, 0, 1, 1, 1]);
  assert.deepEqual([...keep.slice(5, 10)], [1, 0, 1, 1, 1]);
  assert.equal(keep[10 + 5], 0);
  assert.ok(keep.slice(23).every((v) => v === 1));
});

test('a line under a gap in the layer above is seen', () => {
  assert.ok(cull(block([solid, { lines: 3, skip: [1] }])).every((v) => v === 1));
});

test('a line over a gap that air reaches from the side is seen from below', () => {
  // Layer 0's middle line is missing and its ends are open, so air reaches under layer 1's
  // middle line, which is otherwise enclosed.
  const keep = cull(block([{ lines: 3, skip: [1], closed: false }, solid, solid]));
  assert.equal(keep[2 + 1], 1);
  assert.equal(cull(block([{ lines: 3, skip: [1] }, solid, solid]))[4 + 1], 0, 'a sealed gap lets no air in');
});

test('each segment kept is six vertices of a box, layer by layer', () => {
  const p = parseGcode(gcode(LAYERS));
  const { vertices, layerStart, count } = boxVertices(p, Uint8Array.from([1, 0, 1, 1, 1, 1]));
  assert.equal(count, 5);
  assert.deepEqual([...layerStart], [0, 2, 5]);
  assert.equal(vertices.length, 5 * SEGMENT_VERTICES * VERTEX_BYTES);
  const u16 = new Uint16Array(vertices.buffer), i8 = new Int8Array(vertices.buffer);
  // The first segment, (10, 10) to (20, 10), 0.62 wide: its ends pushed out by 0.31 mm.
  assert.deepEqual([...u16.slice(0, 3)], [969, 1000, 30]);
  assert.deepEqual([...u16.slice(6, 9)], [2031, 1000, 30]);
  assert.deepEqual([i8[6], i8[7], vertices[8], vertices[9], vertices[10]], [0, 127, 62, 15, 0]);
  assert.equal(vertices[4 * VERTEX_BYTES + 10], 2 << 2, 'the fifth vertex is the bottom of the near side');
  assert.equal(vertices[1 * VERTEX_BYTES * SEGMENT_VERTICES + 10] & 3, 1, 'the second kept segment is infill');
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

test('a box taller than its byte can hold is refused, never clipped', () => {
  const lines = ['M83'];
  for (let l = 1; l <= 16; l++) lines.push('; CHANGE_LAYER', `; Z_HEIGHT: ${(l * 0.4).toFixed(1)}`, '; LAYER_HEIGHT: 0.4',
    `G1 Z${(l * 0.4).toFixed(1)}`, '; FEATURE: Outer wall', `G1 X0 Y${l}`, `G1 X5 Y${l} E1`);
  const p = parseGcode(gcode(lines));
  assert.equal(boxVertices(p, null, { decimate: 8 }).vertices[9], 160, 'eight layers of 0.4 mm, in fiftieths');
  assert.throws(() => boxVertices(p, null, { decimate: 16 }), /6\.40 mm tall, over the 5\.10 mm a box can be/);
});

test('the look while moving never drops so many layers that a box is too tall to hold', () => {
  // 16 layers of 0.4 mm, one segment each: every 16th layer would be a box 6.4 mm tall.
  const p = { layerStart: Uint32Array.from({ length: 17 }, (_, l) => l), layerZ: Float32Array.from({ length: 16 }, (_, l) => (l + 1) * 0.4) };
  assert.equal(decimationFor(p, 1), 8);
  const thin = { layerStart: p.layerStart, layerZ: Float32Array.from({ length: 16 }, (_, l) => (l + 1) * 0.2) };
  assert.equal(decimationFor(thin, 1), 16, 'sixteen layers of 0.2 mm fit');
});

test('a line type the reading does not know is not carried into the next reading', () => {
  const lines = (feature) => ['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    `; FEATURE: ${feature}`, 'G1 X0 Y0', 'G1 X5 Y0 E1'];
  const first = parseGcode(gcode(lines('Something new')));
  assert.equal(first.features[first.feature[0]], 'Something new');
  const second = parseGcode(gcode(lines('Outer wall')));
  assert.ok(!second.features.includes('Something new'), second.features.join(', '));
  assert.equal(second.features[second.feature[0]], 'Outer wall');
});

test('decimated, only every D-th layer is kept, as tall as the layers it stands for', () => {
  const lines = ['M83'];
  for (let l = 1; l <= 4; l++) lines.push('; CHANGE_LAYER', `; Z_HEIGHT: ${l * 0.2}`, '; LAYER_HEIGHT: 0.2', `G1 Z${l * 0.2}`,
    '; FEATURE: Outer wall', `G1 X0 Y${l}`, `G1 X5 Y${l} E1`);
  const { layerStart, count, vertices } = boxVertices(parseGcode(gcode(lines)), null, { decimate: 2 });
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

test('the full look is drawn the current layer first, then bands from the top down', () => {
  const layerStart = Uint32Array.from([0, 10, 20, 30, 40, 50]);   // five layers of ten
  assert.deepEqual(fullPieces(layerStart, 4), [[40, 50, true], [0, 40, false]]);
  assert.deepEqual(fullPieces(layerStart, 4, 20), [[40, 50, true], [20, 40, false], [0, 20, false]]);
  assert.deepEqual(fullPieces(layerStart, 3, 5), [[30, 40, true], [20, 30, false], [10, 20, false], [0, 10, false]]);
  assert.deepEqual(fullPieces(layerStart, 0), [[0, 10, true]]);
});

test('the counts of lines and of segments are reported', () => {
  const p = parseGcode(gcode(LAYERS));
  assert.equal(p.lines, LAYERS.length);
  assert.equal(p.layers, 2);
});
