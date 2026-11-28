// What the layer preview draws of a sliced file's segments (wizard/README-details.md, "The layer
// preview": method C of the first trial, wizard/trials/preview/): each segment a box of six
// vertices of its own, ready to upload as it is; the layers dropped while the view moves; and
// the order in which the full look is drawn. Pure functions, run in the preview's worker and in
// the tests.
import { PreviewError } from './preview-errors.js';

// Each box drawn is its top and the long side towards the camera, as six vertices of 12 bytes:
// x, y, z as unsigned 16-bit hundredths of a millimetre (the end of the segment, pushed out
// along it by half its width; z the top of the box), the segment's normal as two signed bytes,
// its width in hundredths and its height in fiftieths of a millimetre as bytes (so a box is at
// most MAX_BOX_MM tall; a taller one is refused, never clipped), and a byte of flags: the group
// (bits 0 and 1) and the vertex's role (bits 2 and 3: 0 the near top edge, 1 the far top edge,
// 2 the bottom of the near side). The vertex shader picks the near side from the camera.
export const VERTEX_BYTES = 12, SEGMENT_VERTICES = 6;
// The tallest box the height byte holds: 255 fiftieths of a millimetre.
export const MAX_BOX_MM = 255 / 50;
// The most boxes the look while moving may draw: 0.8 million triangles, which software drawing
// on the machine without a graphics card does in about 70 ms, leaving room for a busy machine
// (the trial's record, decision 7).
export const MOVING_BUDGET = 200000;
const DECIMATIONS = [1, 2, 4, 8, 16];

// The vertices of every segment of `p` (gcode.js parseGcode), layer by layer, and where each
// layer's boxes start. With `decimate` D above 1 only every D-th layer is kept (the layers D-1,
// 2D-1, ...), each box as tall as the D layers it stands for.
export function boxVertices(p, { decimate = 1 } = {}) {
  const layers = p.layerStart.length - 1;
  const layerStart = new Uint32Array(layers + 1);
  let count = 0;
  for (let l = 0; l < layers; l++) {
    layerStart[l] = count;
    if (decimate > 1 && l % decimate !== decimate - 1) continue;
    count += p.layerStart[l + 1] - p.layerStart[l];
  }
  layerStart[layers] = count;
  const bytes = new Uint8Array(count * SEGMENT_VERTICES * VERTEX_BYTES);
  const u16 = new Uint16Array(bytes.buffer), i8 = new Int8Array(bytes.buffer);
  const q = (v) => Math.max(0, Math.min(65535, Math.round(v * 100)));
  let v = 0;
  for (let l = 0; l < layers; l++) {
    if (decimate > 1 && l % decimate !== decimate - 1) continue;
    const below = l - decimate >= 0 ? p.layerZ[l - decimate] : 0;
    const tall = decimate > 1 ? p.layerZ[l] - below : null;
    for (let s = p.layerStart[l]; s < p.layerStart[l + 1]; s++) {
      const dx = p.x1[s] - p.x0[s], dy = p.y1[s] - p.y0[s], len = Math.hypot(dx, dy) || 1;
      const ux = dx / len, uy = dy / len, r = p.width[s] / 2;
      const h = tall ?? p.height[s];
      if (Math.round(h * 50) > 255) {
        throw new PreviewError(`The G-code is too tall to draw: a box of layer ${l + 1} would be ${h.toFixed(2)} mm tall, over the ${MAX_BOX_MM.toFixed(2)} mm a box can be.`);
      }
      const ax = p.x0[s] - ux * r, ay = p.y0[s] - uy * r, bx = p.x1[s] + ux * r, by = p.y1[s] + uy * r;
      const nx = Math.round(-uy * 127), ny = Math.round(ux * 127);
      const w = Math.min(255, Math.round(p.width[s] * 100)), hb = Math.round(h * 50), zq = q(p.z[s]);
      for (let role = 0; role < 3; role++) {
        for (let end = 0; end < 2; end++) {
          const o = v * VERTEX_BYTES;
          u16[o / 2] = q(end ? bx : ax); u16[o / 2 + 1] = q(end ? by : ay); u16[o / 2 + 2] = zq;
          i8[o + 6] = nx; i8[o + 7] = ny;
          bytes[o + 8] = w;
          bytes[o + 9] = hb;
          bytes[o + 10] = p.group[s] | (role << 2);
          v++;
        }
      }
    }
  }
  return { vertices: bytes, layerStart, count };
}

// The fewest layers to drop so that what is drawn while moving is within the budget, among
// those whose boxes, each as tall as the D layers it stands for, fit in MAX_BOX_MM; when none
// is within the budget, the most that fits.
export function decimationFor(p, budget = MOVING_BUDGET) {
  const layers = p.layerStart.length - 1;
  const fits = (d) => {
    for (let l = d - 1; l < layers; l += d) if (p.layerZ[l] - (l - d >= 0 ? p.layerZ[l - d] : 0) > MAX_BOX_MM) return false;
    return true;
  };
  let most = 1;
  for (const d of DECIMATIONS) {
    if (!fits(d)) break;
    most = d;
    let n = 0;
    for (let l = d - 1; l < layers; l += d) n += p.layerStart[l + 1] - p.layerStart[l];
    if (n <= budget) return d;
  }
  return most;
}

// The pieces of the full look for the cut at layer k, in drawing order: the current layer,
// then the layers below it from the top down in bands of at most `most` boxes (seen from
// above, the nearer layers so fill the depth buffer first), as [from, to, current]. A single
// layer over `most` is a band of its own.
export function fullPieces(layerStart, k, most = Infinity) {
  const pieces = [[layerStart[k], layerStart[k + 1], true]];
  let top = layerStart[k];
  while (top > 0) {
    let bottomLayer = k;
    while (bottomLayer > 0 && top - layerStart[bottomLayer - 1] <= most) bottomLayer--;
    if (bottomLayer === k) bottomLayer = k - 1;
    const bottom = layerStart[bottomLayer];
    if (bottom < top) pieces.push([bottom, top, false]);
    top = bottom;
    k = bottomLayer;
  }
  return pieces;
}
