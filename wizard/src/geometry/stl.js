// Reading a binary STL to draw, measure and lay it out, never changing its bytes. An inch part's
// coordinates are multiplied by 25.4 in memory only; the slice service alone scales what is
// sliced (wizard/README.md, "Reading a part without changing it").
import { MAX_PART_BYTES, MAX_PART_TRIANGLES } from './constants.js';
import { GeometryError } from './errors.js';

const HEADER_BYTES = 84;
const TRIANGLE_BYTES = 50;
const SCALE = { mm: 1, in: 25.4 };

// The part as the geometry uses it: `positions` holds each triangle's three corners (x, y, z)
// in millimetres, `min` and `max` its bounding box.
export function readBinaryStl(buffer, units) {
  if (!(units in SCALE)) throw new Error(`units must be "mm" or "in", not ${JSON.stringify(units)}`);
  const length = buffer.byteLength;
  if (length > MAX_PART_BYTES) {
    throw new GeometryError(`the file is ${length} bytes, over the limit of ${MAX_PART_BYTES}`);
  }
  if (length < HEADER_BYTES) throw new GeometryError(`the file is ${length} bytes, shorter than an STL header`);
  const view = new DataView(buffer);
  const count = view.getUint32(80, true);
  if (count === 0) throw new GeometryError('the file has no triangles');
  if (count > MAX_PART_TRIANGLES) {
    throw new GeometryError(`the header says ${count} triangles, over the limit of ${MAX_PART_TRIANGLES}`);
  }
  const expected = HEADER_BYTES + TRIANGLE_BYTES * count;
  if (length !== expected) {
    throw new GeometryError(`the header says ${count} triangles, which take ${expected} bytes; the file is ${length} bytes`);
  }
  const scale = SCALE[units];
  const positions = new Float64Array(count * 9);
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (let t = 0; t < count; t++) {
    const base = HEADER_BYTES + TRIANGLE_BYTES * t + 12;
    for (let k = 0; k < 9; k++) {
      const value = view.getFloat32(base + 4 * k, true);
      if (!Number.isFinite(value)) throw new GeometryError(`triangle ${t + 1} has a coordinate that is not a number`);
      const mm = value * scale;
      positions[t * 9 + k] = mm;
      const axis = k % 3;
      if (mm < min[axis]) min[axis] = mm;
      if (mm > max[axis]) max[axis] = mm;
    }
  }
  return { triangles: count, positions, min, max };
}
