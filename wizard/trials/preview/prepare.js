// What the worker prepares for drawing, from the segments of gcode.js: which segments can be
// seen, the vertex buffers the methods upload as they are, and the ghost of each instance.
// Pure functions, run in the worker and in the tests.

// The contract's six orientations (contracts/plate-configuration.md, "Coordinates"), row-major.
const ORIENTATION = {
  '+z': [1, 0, 0, 0, 1, 0, 0, 0, 1], '-z': [1, 0, 0, 0, -1, 0, 0, 0, -1],
  '+x': [0, 0, -1, 0, 1, 0, 1, 0, 0], '-x': [0, 0, 1, 0, 1, 0, -1, 0, 0],
  '+y': [1, 0, 0, 0, 0, -1, 0, 1, 0], '-y': [1, 0, 0, 0, 0, 1, 0, -1, 0],
};

// One float32 x, y, z for each corner of each triangle of a binary STL.
export function readStl(buffer) {
  const view = new DataView(buffer);
  const count = view.getUint32(80, true);
  if (buffer.byteLength < 84 + 50 * count) throw new Error('The part is not a whole binary STL.');
  const out = new Float32Array(count * 9);
  for (let t = 0; t < count; t++) {
    const at = 84 + 50 * t + 12;
    for (let k = 0; k < 9; k++) out[t * 9 + k] = view.getFloat32(at + 4 * k, true);
  }
  return out;
}

// The instance's corners on the plate: turned by its orientation, its footprint's centre (the
// middle of the turned part's bounding box in x and y) moved to (x, y) after turning by its
// angle, its lowest point on z = 0.
export function placeInstance(corners, instance) {
  const m = ORIENTATION[instance.orientation];
  if (!m) throw new Error(`Unknown orientation ${instance.orientation}.`);
  const n = corners.length / 3, turned = new Float32Array(corners.length);
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity;
  for (let i = 0; i < n; i++) {
    const x = corners[i * 3], y = corners[i * 3 + 1], z = corners[i * 3 + 2];
    const tx = m[0] * x + m[1] * y + m[2] * z, ty = m[3] * x + m[4] * y + m[5] * z, tz = m[6] * x + m[7] * y + m[8] * z;
    turned[i * 3] = tx; turned[i * 3 + 1] = ty; turned[i * 3 + 2] = tz;
    if (tx < minX) minX = tx; if (tx > maxX) maxX = tx; if (ty < minY) minY = ty; if (ty > maxY) maxY = ty;
    if (tz < minZ) minZ = tz;
  }
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  const a = (instance.angle || 0) * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
  for (let i = 0; i < n; i++) {
    const x = turned[i * 3] - cx, y = turned[i * 3 + 1] - cy;
    turned[i * 3] = c * x - s * y + instance.x;
    turned[i * 3 + 1] = s * x + c * y + instance.y;
    turned[i * 3 + 2] -= minZ;
  }
  return turned;
}

// Every instance of the plate configuration placed, as one array of triangle corners, and the
// bounds of each instance (minX, minY, minZ, maxX, maxY, maxZ; for framing the view).
// `partCorners` holds each part's corners under its key in the plate configuration; a part in
// inches is scaled to millimetres first, as the contract says.
export function ghostOf(plate, partCorners) {
  const inMm = {};
  for (const [key, part] of Object.entries(plate.parts)) {
    const corners = partCorners[key];
    inMm[key] = part.units === 'in' ? corners.map((v) => v * 25.4) : corners;
  }
  const placed = plate.instances.map((i) => placeInstance(inMm[i.ref], i));
  const corners = new Float32Array(placed.reduce((n, p) => n + p.length, 0));
  const bounds = new Float32Array(placed.length * 6);
  let at = 0;
  placed.forEach((p, k) => {
    corners.set(p, at); at += p.length;
    const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
    for (let i = 0; i < p.length; i += 3) {
      for (let a = 0; a < 3; a++) { b[a] = Math.min(b[a], p[i + a]); b[a + 3] = Math.max(b[a + 3], p[i + a]); }
    }
    bounds.set(b, k * 6);
  });
  return { corners, bounds };
}

/* ------------------------------------------------------------------ what can be seen */

// Which segments air can reach: 1 for each segment that can be seen from some view of the
// whole plate, 0 for one that no view shows. Each layer is drawn into a grid of `cell` mm
// squares (a square is filled when its centre lies on a line). Air is every empty square that
// can be reached from outside the parts: in its own layer from the edge of the grid, and from
// the air of the layer above or below through an empty square; the space above the last layer
// is air, and the plate is not. A segment is seen when air touches it: above or below it,
// beside it, or beyond either end. A sealed void, such as the sparse infill under a top
// surface, is not air, so what faces only into it is hidden. Cutting the plate at a layer
// opens such voids from above; the methods draw the layers just below the cut whole for that.
export function cull(p, { cell = 0.25 } = {}) {
  const keep = new Uint8Array(p.count);
  const layers = p.layerStart.length - 1;
  if (!p.count || !layers) return keep;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (let s = 0; s < p.count; s++) {
    const r = p.width[s];
    minX = Math.min(minX, p.x0[s] - r, p.x1[s] - r); maxX = Math.max(maxX, p.x0[s] + r, p.x1[s] + r);
    minY = Math.min(minY, p.y0[s] - r, p.y1[s] - r); maxY = Math.max(maxY, p.y0[s] + r, p.y1[s] + r);
  }
  const ox = minX - 2 * cell, oy = minY - 2 * cell;
  const nx = Math.ceil((maxX - ox) / cell) + 3, ny = Math.ceil((maxY - oy) / cell) + 3, cells = nx * ny;
  const grid = new Uint8Array(cells);            // 0 empty, 1 filled, 2 air
  const air = new Uint8Array(layers * cells);     // the air of every layer, 1 where air
  const queue = new Int32Array(cells);
  const ci = (x) => Math.floor((x - ox) / cell), cj = (y) => Math.floor((y - oy) / cell);

  function draw(layer) {
    grid.fill(0);
    for (let s = p.layerStart[layer]; s < p.layerStart[layer + 1]; s++) {
      const x0 = p.x0[s], y0 = p.y0[s], x1 = p.x1[s], y1 = p.y1[s], r = p.width[s] / 2;
      const dx = x1 - x0, dy = y1 - y0, l2 = dx * dx + dy * dy;
      const i0 = ci(Math.min(x0, x1) - r), i1 = ci(Math.max(x0, x1) + r);
      const j0 = cj(Math.min(y0, y1) - r), j1 = cj(Math.max(y0, y1) + r);
      for (let j = j0; j <= j1; j++) {
        const cy = oy + (j + 0.5) * cell;
        for (let i = i0; i <= i1; i++) {
          const cx = ox + (i + 0.5) * cell;
          let t = l2 > 0 ? ((cx - x0) * dx + (cy - y0) * dy) / l2 : 0;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          const ex = x0 + t * dx - cx, ey = y0 + t * dy - cy;
          if (ex * ex + ey * ey <= r * r) grid[j * nx + i] = 1;
        }
      }
    }
  }
  // Fills the air of `layer` in `grid` from the grid's edge and from the air of layer `from`
  // (above or below; -1 for none, `layers` for the open space above the last layer), adding
  // to the air already found for the layer.
  function flood(layer, from) {
    let head = 0, tail = 0;
    const seed = (k) => { if (grid[k] === 0) { grid[k] = 2; queue[tail++] = k; } };
    for (let i = 0; i < nx; i++) { seed(i); seed((ny - 1) * nx + i); }
    for (let j = 0; j < ny; j++) { seed(j * nx); seed(j * nx + nx - 1); }
    const own = layer * cells;
    for (let k = 0; k < cells; k++) if (air[own + k]) seed(k);
    if (from === layers) { for (let k = 0; k < cells; k++) seed(k); }
    else if (from >= 0) { const f = from * cells; for (let k = 0; k < cells; k++) if (air[f + k]) seed(k); }
    while (head < tail) {
      const k = queue[head++], i = k % nx;
      if (i > 0) seed(k - 1);
      if (i < nx - 1) seed(k + 1);
      if (k >= nx) seed(k - nx);
      if (k < cells - nx) seed(k + nx);
    }
    for (let k = 0; k < cells; k++) if (grid[k] === 2) air[own + k] = 1;
  }
  for (let layer = layers - 1; layer >= 0; layer--) { draw(layer); flood(layer, layer + 1 < layers ? layer + 1 : layers); }
  for (let layer = 1; layer < layers; layer++) { draw(layer); flood(layer, layer - 1); }

  const isAir = (layer, x, y) => {
    if (layer >= layers) return true;
    if (layer < 0) return false;
    const i = ci(x), j = cj(y);
    if (i < 0 || j < 0 || i >= nx || j >= ny) return true;
    return air[layer * cells + j * nx + i] === 1;
  };
  for (let layer = 0; layer < layers; layer++) {
    for (let s = p.layerStart[layer]; s < p.layerStart[layer + 1]; s++) {
      const x0 = p.x0[s], y0 = p.y0[s], x1 = p.x1[s], y1 = p.y1[s];
      const dx = x1 - x0, dy = y1 - y0, len = Math.hypot(dx, dy);
      const ux = len > 0 ? dx / len : 1, uy = len > 0 ? dy / len : 0;
      const off = p.width[s] / 2 + cell, half = p.width[s] / 2 * 0.9;
      const steps = Math.max(1, Math.ceil(len / (cell / 2)));
      let seen = isAir(layer, x0 - ux * off, y0 - uy * off) || isAir(layer, x1 + ux * off, y1 + uy * off);
      for (let k = 0; k <= steps && !seen; k++) {
        const x = x0 + dx * k / steps, y = y0 + dy * k / steps;
        seen = isAir(layer, x - uy * off, y + ux * off) || isAir(layer, x + uy * off, y - ux * off);
        for (const o of [0, half, -half]) {
          if (seen) break;
          const px = x - uy * o, py = y + ux * o;
          seen = isAir(layer + 1, px, py) || isAir(layer - 1, px, py);
        }
      }
      keep[s] = seen ? 1 : 0;
    }
  }
  return keep;
}

/* ------------------------------------------------------------------ the boxes' vertices */

// Each segment drawn is a box: its top and the long side towards the camera, as six vertices
// of 12 bytes: x, y, z as unsigned 16-bit hundredths of a millimetre (the end of the segment,
// pushed out along it by half its width; z the top of the box), the segment's normal as two
// signed bytes, its width in hundredths and its height in fiftieths of a millimetre as bytes
// (so a box is at most MAX_BOX_MM tall; a taller one is refused, not clipped),
// and a byte of flags: the group (bits 0 and 1) and the vertex's role (bits 2 and 3: 0 the
// near top edge, 1 the far top edge, 2 the bottom of the near side). The vertex shader picks
// the near side from the camera. VERTEX_BYTES and SEGMENT_VERTICES are what the page reads.
export const VERTEX_BYTES = 12, SEGMENT_VERTICES = 6;
// The tallest box the height byte holds: 255 fiftieths of a millimetre.
export const MAX_BOX_MM = 255 / 50;

// The vertices of the segments `select` keeps (all when null), layer by layer, and where each
// layer starts. With `decimate` D above 1 only every D-th layer is kept (the layers D-1,
// 2D-1, ...), each box as tall as the D layers it stands for.
export function boxVertices(p, select = null, { decimate = 1 } = {}) {
  const layers = p.layerStart.length - 1;
  const layerStart = new Uint32Array(layers + 1);
  let count = 0;
  for (let l = 0; l < layers; l++) {
    layerStart[l] = count;
    if (decimate > 1 && l % decimate !== decimate - 1) continue;
    for (let s = p.layerStart[l]; s < p.layerStart[l + 1]; s++) if (!select || select[s]) count++;
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
      if (select && !select[s]) continue;
      const dx = p.x1[s] - p.x0[s], dy = p.y1[s] - p.y0[s], len = Math.hypot(dx, dy) || 1;
      const ux = dx / len, uy = dy / len, r = p.width[s] / 2;
      const ends = [[p.x0[s] - ux * r, p.y0[s] - uy * r], [p.x1[s] + ux * r, p.y1[s] + uy * r]];
      const h = tall ?? p.height[s];
      if (Math.round(h * 50) > 255) throw new Error(`A box of layer ${l + 1} would be ${h.toFixed(2)} mm tall, over the ${MAX_BOX_MM.toFixed(2)} mm a box can be.`);
      for (let role = 0; role < 3; role++) {
        for (const [x, y] of ends) {
          const o = v * VERTEX_BYTES;
          u16[o / 2] = q(x); u16[o / 2 + 1] = q(y); u16[o / 2 + 2] = q(p.z[s]);
          i8[o + 6] = Math.round(-uy * 127); i8[o + 7] = Math.round(ux * 127);
          bytes[o + 8] = Math.min(255, Math.round(p.width[s] * 100));
          bytes[o + 9] = Math.round(h * 50);
          bytes[o + 10] = p.group[s] | (role << 2);
          v++;
        }
      }
    }
  }
  return { vertices: bytes, layerStart, count };
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

// Each segment as 8 floats: x0, y0, x1, y1, z (its top), width, height, group (the instanced
// boxes of the first measurement, kept for the bench's comparison).
export function boxes(p) {
  const out = new Float32Array(p.count * 8);
  for (let i = 0; i < p.count; i++) {
    const o = i * 8;
    out[o] = p.x0[i]; out[o + 1] = p.y0[i]; out[o + 2] = p.x1[i]; out[o + 3] = p.y1[i];
    out[o + 4] = p.z[i]; out[o + 5] = p.width[i]; out[o + 6] = p.height[i]; out[o + 7] = p.group[i];
  }
  return out;
}