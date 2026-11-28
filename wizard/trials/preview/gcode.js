// Reading a sliced file for the layer preview trial: the archive's Metadata/plate_1.gcode,
// and from it every extrusion as a straight segment with its layer, line type, width and
// height. Shared by every candidate method (each draws the same segments) and run in a worker.
// Written from the G-code itself, Orca's comments as Orca 2.4.2 writes them; no Orca code.

// The four groups of line types, each with its fixed colour (wizard/README.md, "The result").
export const GROUPS = ['walls', 'infill', 'surfaces', 'supports'];
export const GROUP_COLOURS = [0x2b5c9e, 0xe0912f, 0x2f9e7a, 0x9a8fb8];
export const GROUP_NAMES = ['Walls', 'Infill', 'Top and bottom surfaces', 'Supports and brim'];
const WALLS = 0, INFILL = 1, SURFACES = 2, SUPPORTS = 3;

// Orca's line types, as its "; FEATURE:" comments name them, in their groups. A type Orca adds
// later and this list does not know is drawn as a wall, the group every part has.
const FEATURE_GROUP = {
  'Outer wall': WALLS, 'Inner wall': WALLS, 'Overhang wall': WALLS,
  'Sparse infill': INFILL, 'Internal solid infill': INFILL, 'Gap infill': INFILL, 'Internal Bridge': INFILL,
  'Top surface': SURFACES, 'Bottom surface': SURFACES, 'Bridge': SURFACES, 'Ironing': SURFACES,
  'Support': SUPPORTS, 'Support interface': SUPPORTS, 'Support transition': SUPPORTS, 'Brim': SUPPORTS,
  'Skirt': SUPPORTS, 'Prime tower': SUPPORTS, 'Custom': SUPPORTS,
};
export const FEATURES = Object.keys(FEATURE_GROUP);
export function groupOf(feature) { return FEATURE_GROUP[feature] ?? WALLS; }
// Line types inside a part, which the layers above and below can hide (used by culling methods).
export const INTERIOR = new Set(['Inner wall', 'Sparse infill', 'Internal solid infill', 'Gap infill', 'Internal Bridge']);

/* ------------------------------------------------------------------ the archive */

// The bytes of entry `name` of the zip archive `bytes`, inflated by the browser's own
// DecompressionStream (no third-party code).
export async function readZipEntry(bytes, name) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let end = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 65535); i--) {
    if (view.getUint32(i, true) === 0x06054b50) { end = i; break; }
  }
  if (end < 0) throw new Error('The sliced file is not a zip archive.');
  const entries = view.getUint16(end + 10, true);
  let at = view.getUint32(end + 16, true);
  const decoder = new TextDecoder();
  for (let k = 0; k < entries; k++) {
    if (view.getUint32(at, true) !== 0x02014b50) throw new Error('The sliced file is not a zip archive.');
    const method = view.getUint16(at + 10, true), size = view.getUint32(at + 20, true);
    const nameLength = view.getUint16(at + 28, true), extra = view.getUint16(at + 30, true);
    const comment = view.getUint16(at + 32, true), local = view.getUint32(at + 42, true);
    const entryName = decoder.decode(bytes.subarray(at + 46, at + 46 + nameLength));
    if (entryName === name) {
      const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true);
      const body = bytes.subarray(start, start + size);
      if (method === 0) return body.slice();
      const stream = new Blob([body]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
      return new Uint8Array(await new Response(stream).arrayBuffer());
    }
    at += 46 + nameLength + extra + comment;
  }
  throw new Error(`The sliced file has no ${name}.`);
}

/* ------------------------------------------------------------------ the G-code */

class Grow {                                   // a typed array that doubles as it fills
  constructor(Type, size) { this.Type = Type; this.a = new Type(size); this.n = 0; }
  push(v) { if (this.n === this.a.length) { const b = new this.Type(this.a.length * 2); b.set(this.a); this.a = b; } this.a[this.n++] = v; }
  done() { return this.a.slice(0, this.n); }
}

const NL = 10, SEMI = 59, SPACE = 32, TAB = 9, CR = 13;

// Reads a number at bytes[i..end) as G-code writes it ("-.4", "12", "3.25"); NaN when none.
function readNumber(bytes, i, end) {
  let sign = 1, v = 0, seen = false;
  if (bytes[i] === 45) { sign = -1; i++; } else if (bytes[i] === 43) i++;
  while (i < end && bytes[i] >= 48 && bytes[i] <= 57) { v = v * 10 + bytes[i] - 48; i++; seen = true; }
  if (bytes[i] === 46) {
    i++;
    let f = 0.1;
    while (i < end && bytes[i] >= 48 && bytes[i] <= 57) { v += (bytes[i] - 48) * f; f *= 0.1; i++; seen = true; }
  }
  return seen ? sign * v : NaN;
}

function startsWith(bytes, i, end, prefix) {
  if (end - i < prefix.length) return false;
  for (let k = 0; k < prefix.length; k++) if (bytes[i + k] !== prefix[k]) return false;
  return true;
}
const enc = (s) => new TextEncoder().encode(s);
const C_FEATURE = enc('; FEATURE: '), C_WIDTH = enc('; LINE_WIDTH: '), C_LAYER = enc('; CHANGE_LAYER');
const C_ZH = enc('; Z_HEIGHT: '), C_LH = enc('; LAYER_HEIGHT: ');

// Every extrusion of the G-code as a straight segment. Options:
//   arcTolerance: the most a chord of a G2/G3 arc may stray from the arc, in mm (0.02).
//   mergeTolerance: consecutive segments of one type are merged into one while no merged point
//     strays from the merged segment by more than this, in mm (0.01); 0 merges nothing.
export function parseGcode(bytes, { arcTolerance = 0.02, mergeTolerance = 0.01 } = {}) {
  const cap = 1 << 16;
  const X0 = new Grow(Float32Array, cap), Y0 = new Grow(Float32Array, cap), X1 = new Grow(Float32Array, cap);
  const Y1 = new Grow(Float32Array, cap), Z = new Grow(Float32Array, cap), W = new Grow(Float32Array, cap);
  const G = new Grow(Uint8Array, cap), F = new Grow(Uint8Array, cap);
  const layerZ = [], layerHeight = [], layerStart = [];
  const features = FEATURES.slice();             // this reading's line types: the known ones, then any new
  const decoder = new TextDecoder();
  let x = 0, y = 0, z = 0, e = 0, relXYZ = false, relE = false;
  let feature = 'Custom', featureId = features.indexOf('Custom'), group = SUPPORTS, width = 0.4;
  let layer = -1, pendingZ = 0, pendingH = 0.2, lines = 0, moves = 0;
  // The run being merged: its start, its points so far, and whether it may take another point.
  let run = false, rx = 0, ry = 0, ex = 0, ey = 0;
  const pts = [];
  const tol2 = mergeTolerance * mergeTolerance;

  function flush() {
    if (!run) return;
    X0.push(rx); Y0.push(ry); X1.push(ex); Y1.push(ey); Z.push(z); W.push(width); G.push(group); F.push(featureId);
    run = false; pts.length = 0;
  }
  function straysFrom(ax, ay, bx, by) {          // does a point of the run stray from a-b?
    const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
    for (let k = 0; k < pts.length; k += 2) {
      const px = pts[k] - ax, py = pts[k + 1] - ay;
      const c = px * dy - py * dx;
      if (c * c > tol2 * l2) return true;
      const t = px * dx + py * dy;
      if (t < 0 || t > l2) return true;
    }
    return false;
  }
  function segment(ax, ay, bx, by) {
    if (ax === bx && ay === by) return;
    moves++;
    if (layer < 0) return;
    if (run && ex === ax && ey === ay && mergeTolerance > 0 && pts.length < 128) {
      pts.push(ax, ay);
      if (!straysFrom(rx, ry, bx, by)) { ex = bx; ey = by; return; }
      pts.length -= 2;
    }
    flush();
    run = true; rx = ax; ry = ay; ex = bx; ey = by;
  }

  const n = bytes.length;
  let i = 0;
  while (i < n) {
    let end = bytes.indexOf(NL, i);
    if (end < 0) end = n;
    let lineEnd = end;
    if (lineEnd > i && bytes[lineEnd - 1] === CR) lineEnd--;
    lines++;
    const c = bytes[i];
    if (c === SEMI) {
      if (startsWith(bytes, i, lineEnd, C_FEATURE)) {
        flush();
        feature = decoder.decode(bytes.subarray(i + C_FEATURE.length, lineEnd)).trim();
        featureId = features.indexOf(feature);
        if (featureId < 0) { features.push(feature); featureId = features.length - 1; }
        group = groupOf(feature);
      } else if (startsWith(bytes, i, lineEnd, C_WIDTH)) {
        const w = readNumber(bytes, i + C_WIDTH.length, lineEnd);
        if (w > 0 && w !== width) { flush(); width = w; }
      } else if (startsWith(bytes, i, lineEnd, C_LAYER)) {
        flush();
        layer++;
        layerStart.push(X0.n); layerZ.push(pendingZ); layerHeight.push(pendingH);
      } else if (startsWith(bytes, i, lineEnd, C_ZH)) {
        pendingZ = readNumber(bytes, i + C_ZH.length, lineEnd);
        if (layer >= 0) layerZ[layer] = pendingZ;
      } else if (startsWith(bytes, i, lineEnd, C_LH)) {
        pendingH = readNumber(bytes, i + C_LH.length, lineEnd);
        if (layer >= 0) layerHeight[layer] = pendingH;
      }
    } else if (c === 71 || c === 77) {           // G or M
      const code = readNumber(bytes, i + 1, lineEnd);
      if (c === 77) {
        if (code === 82) relE = false; else if (code === 83) relE = true;
      // G90 and G91 change X, Y and Z only: Orca writes M83 once and G90 after it, relying on
      // the extruder staying relative.
      } else if (code === 90) relXYZ = false;
      else if (code === 91) relXYZ = true;
      else if (code === 92) {
        const k = bytes.indexOf(69, i);          // 'E'
        if (k >= 0 && k < lineEnd) e = readNumber(bytes, k + 1, lineEnd);
      } else if (code === 0 || code === 1 || code === 2 || code === 3) {
        let nx = NaN, ny = NaN, nz = NaN, ne = NaN, ci = 0, cj = 0, r = NaN;
        for (let k = i + 2; k < lineEnd; k++) {
          const b = bytes[k];
          if (b === SEMI) break;
          if (b === SPACE || b === TAB) continue;
          const v = readNumber(bytes, k + 1, lineEnd);
          if (b === 88) nx = v; else if (b === 89) ny = v; else if (b === 90) nz = v; else if (b === 69) ne = v;
          else if (b === 73) ci = v; else if (b === 74) cj = v; else if (b === 82) r = v;
          while (k + 1 < lineEnd && bytes[k + 1] !== SPACE && bytes[k + 1] !== TAB) k++;
        }
        const tx = isNaN(nx) ? x : (relXYZ ? x + nx : nx), ty = isNaN(ny) ? y : (relXYZ ? y + ny : ny);
        if (!isNaN(nz)) { const tz = relXYZ ? z + nz : nz; if (tz !== z) { flush(); z = tz; } }
        let extrudes = false;
        if (!isNaN(ne)) {
          const delta = relE ? ne : ne - e;
          e = relE ? e + ne : ne;
          extrudes = delta > 0;
        }
        if (extrudes) {
          if (code <= 1 || (isNaN(r) && ci === 0 && cj === 0)) segment(x, y, tx, ty);
          else arc(x, y, tx, ty, ci, cj, code === 2, arcTolerance, segment);
        } else if (tx !== x || ty !== y) flush();
        x = tx; y = ty;
      }
    }
    i = end + 1;
  }
  flush();
  layerStart.push(X0.n);
  return {
    count: X0.n, x0: X0.done(), y0: Y0.done(), x1: X1.done(), y1: Y1.done(), z: Z.done(), width: W.done(),
    group: G.done(), feature: F.done(), features,
    height: heightsOf(layerStart, layerHeight, X0.n),
    layers: layerZ.length, layerZ: Float32Array.from(layerZ), layerHeight: Float32Array.from(layerHeight),
    layerStart: Uint32Array.from(layerStart), lines, moves,
  };
}

function heightsOf(layerStart, layerHeight, count) {
  const h = new Float32Array(count);
  for (let l = 0; l < layerHeight.length; l++) h.fill(layerHeight[l], layerStart[l], layerStart[l + 1]);
  return h;
}

// A G2 (clockwise) or G3 arc from (ax, ay) to (bx, by) about (ax + i, ay + j), as chords that
// stray at most `tol` from it.
function arc(ax, ay, bx, by, i, j, clockwise, tol, emit) {
  const cx = ax + i, cy = ay + j, r = Math.hypot(i, j);
  const a0 = Math.atan2(ay - cy, ax - cx);
  let sweep = Math.atan2(by - cy, bx - cx) - a0;
  if (clockwise) { if (sweep >= 0) sweep -= 2 * Math.PI; } else if (sweep <= 0) sweep += 2 * Math.PI;
  const step = r > tol ? 2 * Math.acos(1 - tol / r) : Math.PI;
  const k = Math.max(1, Math.ceil(Math.abs(sweep) / step));
  let px = ax, py = ay;
  for (let s = 1; s < k; s++) {
    const a = a0 + sweep * s / k, qx = cx + r * Math.cos(a), qy = cy + r * Math.sin(a);
    emit(px, py, qx, qy);
    px = qx; py = qy;
  }
  emit(px, py, bx, by);
}
