// What the layer preview's tests share: a zip archive made in the test, G-code from lines, a
// binary STL from triangles, and the small real sliced files committed in tests/sliced/.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateRawSync, crc32 } from 'node:zlib';

export const SLICED = join(dirname(fileURLToPath(import.meta.url)), '..', 'sliced');
export const REAL_PARTS = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'contracts', 'examples', 'parts', 'real');

// The bytes of a committed sliced file, as an ArrayBuffer of its own.
export function slicedFile(name) {
  const b = readFileSync(join(SLICED, `${name}.gcode.3mf`));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.length);
}

// A committed plate configuration of tests/sliced/.
export function slicedPlate(name) {
  return JSON.parse(readFileSync(join(SLICED, `${name}.json`), 'utf8'));
}

// A zip of `entries` ({name: string or bytes}), deflated unless `stored`.
export function zip(entries, stored = false) {
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

export const gcode = (lines) => new TextEncoder().encode(lines.join('\n') + '\n');

// A sliced file holding the G-code of `lines`, as an ArrayBuffer.
export function slicedOf(lines) {
  const z = zip({ 'Metadata/plate_1.json': '{}', 'Metadata/plate_1.gcode': gcode(lines) });
  return z.buffer.slice(z.byteOffset, z.byteOffset + z.byteLength);
}

// The corners of a binary STL's triangles (each nine numbers), as the geometry client gives a
// part's corners for drawing: a Float32Array, in millimetres.
export const corners = (triangles) => Float32Array.from(triangles.flat());

// Two layers of every group: the plate of most tests.
export const LAYERS = [
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
