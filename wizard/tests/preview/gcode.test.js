// The layer preview's reading of a sliced file (src/preview/gcode.js; wizard/README-details.md,
// "The layer preview"): the archive's Metadata/plate_1.gcode, and from it every extrusion as a
// straight segment with its layer, line type, width and height, arcs as chords, straight runs
// merged; a file it cannot read refused with the wizard's own error report.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { GROUPS, GROUP_COLOURS, GROUP_NAMES, groupOf, parseGcode, readZipEntry } from '../../src/preview/gcode.js';
import { PREVIEW_UNREADABLE, PreviewError } from '../../src/preview/preview-errors.js';
import { LAYERS, gcode, zip } from './helpers.js';

const text = (bytes) => new TextDecoder().decode(bytes);

test('an entry of the archive is read, deflated or stored', async () => {
  const archive = zip({ 'Metadata/plate_1.json': '{"a":1}', 'Metadata/plate_1.gcode': 'G1 X1\n'.repeat(1000) });
  assert.equal(text(await readZipEntry(archive, 'Metadata/plate_1.gcode')), 'G1 X1\n'.repeat(1000));
  assert.equal(text(await readZipEntry(zip({ 'a.txt': 'plain' }, true), 'a.txt')), 'plain');
});

// Each way a sliced file can be unreadable is the wizard's report, its detail saying what.
async function refused(bytes, detail) {
  await assert.rejects(readZipEntry(bytes, 'Metadata/plate_1.gcode'), (error) => {
    assert.ok(error instanceof PreviewError, String(error));
    assert.equal(error.report.code, PREVIEW_UNREADABLE);
    assert.match(error.report.detail, detail);
    return true;
  });
}

test('an archive without the G-code, or not an archive at all, is refused as unreadable', async () => {
  await refused(zip({ 'a.txt': 'x' }), /has no Metadata\/plate_1\.gcode/);
  await refused(new TextEncoder().encode('not a zip at all, just words'), /not a zip archive/);
  await refused(new Uint8Array(0), /not a zip archive/);
});

test('an archive cut short, a damaged deflate stream or an unknown compression is refused as unreadable', async () => {
  const whole = zip({ 'Metadata/plate_1.gcode': 'G1 X1 E1\n'.repeat(500) });
  await refused(whole.slice(0, whole.length - 30), /not a zip archive/);
  const damaged = Uint8Array.from(whole);
  for (let i = 40; i < 60; i++) damaged[i] = 0xff;                     // inside the deflated body
  await refused(damaged, /could not be inflated/);
  const odd = Uint8Array.from(whole);
  const dir = odd.length - 22 - 46 - 'Metadata/plate_1.gcode'.length;
  odd[dir + 10] = 14;                                                  // LZMA, which no browser inflates
  await refused(odd, /compression method 14/);
  const pointsAway = Uint8Array.from(whole);
  new DataView(pointsAway.buffer).setUint32(dir + 42, 0x7fffffff, true);   // its local header past the end
  await refused(pointsAway, /lies outside the file/);
});

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
  assert.equal(p.lines, LAYERS.length);
  assert.equal(p.layers, 2);
});

test('the four groups have the guide\'s colours and names, in its order', () => {
  assert.deepEqual(GROUPS, ['walls', 'infill', 'surfaces', 'supports']);
  assert.deepEqual(GROUP_COLOURS, [0x2b5c9e, 0xe0912f, 0x2f9e7a, 0x9a8fb8]);
  assert.deepEqual(GROUP_NAMES, ['Walls', 'Infill', 'Top and bottom surfaces', 'Supports and brim']);
});

test('every line type of Orca is in one of the four groups, and a new one is drawn as a wall', () => {
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
  const coarse = parseGcode(gcode(lines), { arcTolerance: 0.1 });
  assert.ok(coarse.count < chords, 'a coarser reading cuts the arc into fewer chords');
});

test('an arc of a damaged file, a kilometre across, is cut into a bounded number of chords', () => {
  const p = parseGcode(gcode(['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    '; FEATURE: Outer wall', 'G1 X0 Y0', 'G3 X0.001 Y0 I500000 J0 E2']), { mergeTolerance: 0 });
  assert.equal(p.count, 4096);
});

test('absolute extrusion, a reset of E and relative moves are followed', () => {
  const p = parseGcode(gcode(['M82', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    '; FEATURE: Inner wall', 'G1 X0 Y0 E1', 'G1 X0 Y5 E2', 'G1 X5 Y5 E1.5', 'G92 E0', 'G1 X9 Y5 E0.5',
    'G91', 'G1 X1 Y1 E1', 'G90', 'G1 X0 Y0 E1']));
  assert.deepEqual([...p.x1], [0, 9, 10]);
  assert.deepEqual([...p.y1], [5, 5, 6]);
});

test('a line type the reading does not know is not carried into the next reading', () => {
  const lines = (feature) => ['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    `; FEATURE: ${feature}`, 'G1 X0 Y0', 'G1 X5 Y0 E1'];
  const first = parseGcode(gcode(lines('Something new')));
  assert.equal(first.features[first.feature[0]], 'Something new');
  const second = parseGcode(gcode(lines('Outer wall')));
  assert.ok(!second.features.includes('Something new'), second.features.join(', '));
});

test('lines ending in a carriage return and a last line without its newline are read', () => {
  const crlf = new TextEncoder().encode(['M83', '; CHANGE_LAYER', '; Z_HEIGHT: 0.2', '; LAYER_HEIGHT: 0.2', 'G1 Z.2',
    '; FEATURE: Outer wall', 'G1 X0 Y0', 'G1 X5 Y0 E1'].join('\r\n'));
  const p = parseGcode(crlf);
  assert.equal(p.count, 1);
  assert.equal(p.group[0], 0);
  assert.equal(p.x1[0], 5);
});

test('the reading says how far through the G-code it is, rising to the whole', () => {
  const lines = ['M83'];
  for (let l = 1; l <= 200; l++) lines.push('; CHANGE_LAYER', `; Z_HEIGHT: ${(l * 0.2).toFixed(1)}`, '; LAYER_HEIGHT: 0.2',
    `G1 Z${(l * 0.2).toFixed(1)}`, '; FEATURE: Outer wall', `G1 X0 Y${l}`, `G1 X5 Y${l} E1`);
  const seen = [];
  parseGcode(gcode(lines), { onProgress: (f) => seen.push(f) });
  assert.ok(seen.length >= 8, `${seen.length} reports`);
  assert.ok(seen.every((f, i) => f > 0 && f <= 1 && (i === 0 || f > seen[i - 1])), seen.join(', '));
  assert.equal(seen.at(-1), 1);
});
