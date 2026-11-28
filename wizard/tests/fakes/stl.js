// Binary STL files for the tests, as a user's disk holds them: an 80-byte header, a count of
// triangles, and 50 bytes for each. `header` tells two files of the same solid apart, so that
// their hashes differ.
import { box } from '../geometry/shapes.js';

export function stlFile(mesh, header = 'test part') {
  const buffer = new ArrayBuffer(84 + 50 * mesh.triangles);
  const view = new DataView(buffer);
  new Uint8Array(buffer, 0, 80).set(new TextEncoder().encode(header.slice(0, 80)));
  view.setUint32(80, mesh.triangles, true);
  for (let t = 0; t < mesh.triangles; t++) {
    for (let k = 0; k < 9; k++) view.setFloat32(84 + 50 * t + 12 + 4 * k, mesh.positions[t * 9 + k], true);
  }
  return buffer;
}

// A box `x` by `y` by `z`, its header `header`.
export const boxFile = (header = 'box', [x, y, z] = [20, 10, 5]) => stlFile(box(x, y, z), header);

// The largest part allowed, 150,000 triangles (7,500,084 bytes): a box's twelve triangles over
// and over, a file the page reads.
export function largestFile(header = 'largest') {
  const one = box(20, 10, 5);
  const count = 150_000;
  const positions = new Float64Array(count * 9);
  for (let t = 0; t < count; t++) positions.set(one.positions.subarray((t % 12) * 9, (t % 12) * 9 + 9), t * 9);
  return stlFile({ triangles: count, positions }, header);
}

// A file of exactly `length` bytes that is no STL the page can read: its header says no triangle.
export const filler = (length) => new ArrayBuffer(length);
