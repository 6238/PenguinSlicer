// Whether a part laid with the unit direction `down` (in its own coordinates) pointing straight
// down rests on no face of its own: the slice service's rule for slice.rests_on_an_edge, with its
// figures (constants.js). A part laid on a hull face that bridges a hollow touches the plate only
// along edges, its first layer is strips narrower than a line, and the pinned Orca refuses it; a
// part that touches along a line but is curved there (a lying tube, rods, fillets) is millimetres
// across half a layer up, and prints. Both measures are taken as the slice service takes them:
// the part's faces on the plate, and its section half a first layer up shrunk by half a line.
import { FIRST_LAYER_MM, FIRST_LINE_MM, ON_THE_PLATE_MM, REST_AREA_MM2 } from './constants.js';

// Two directions square to `n`, so that (u, w, n) is right-handed (faces.js gives it out as its
// own, as it did before this module).
export function planeBasis(n) {
  const e = Math.abs(n[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
  let u = [n[1] * e[2] - n[2] * e[1], n[2] * e[0] - n[0] * e[2], n[0] * e[1] - n[1] * e[0]];
  const len = Math.hypot(...u);
  u = u.map((v) => v / len);
  const w = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0]];
  return [u, w];
}

const dot = (p, o, d) => p[o] * d[0] + p[o + 1] * d[1] + p[o + 2] * d[2];

// How far below the lowest point each corner is not: its height above the plate is top - v·down.
function topOf(p, down) {
  let top = -Infinity;
  for (let i = 0; i < p.length; i += 3) {
    const h = dot(p, i, down);
    if (h > top) top = h;
  }
  return top;
}

// The area, seen from above, of the part's triangles whose three corners all lie within
// ON_THE_PLATE_MM of the plate.
export function contactArea(mesh, down) {
  const p = mesh.positions;
  const top = topOf(p, down);
  const [u, w] = planeBasis(down);
  let area = 0;
  for (let o = 0; o < p.length; o += 9) {
    if (top - dot(p, o, down) > ON_THE_PLATE_MM || top - dot(p, o + 3, down) > ON_THE_PLATE_MM
      || top - dot(p, o + 6, down) > ON_THE_PLATE_MM) continue;
    const ax = dot(p, o, u), ay = dot(p, o, w);
    const cross = (dot(p, o + 3, u) - ax) * (dot(p, o + 6, w) - ay) - (dot(p, o + 3, w) - ay) * (dot(p, o + 6, u) - ax);
    area += Math.abs(cross) / 2;
  }
  return area;
}

// Whether the corner at offset pa comes before the one at pb in a fixed order of the corners'
// coordinates, so that an edge two triangles share is always cut from the same end and
// both give the same point, to the last bit.
function before(p, pa, pb) {
  if (p[pa] !== p[pb]) return p[pa] < p[pb];
  if (p[pa + 1] !== p[pb + 1]) return p[pa + 1] < p[pb + 1];
  return p[pa + 2] < p[pb + 2];
}

// The triangles' cuts `at` above the plate, as segments [x0, y0, x1, y1] in the plate's own
// directions, before they are joined into rings (rings below).
function cuts(mesh, down, at) {
  const p = mesh.positions;
  const top = topOf(p, down);
  const [u, w] = planeBasis(down);
  const segments = [];
  const corner = new Array(3);
  for (let o = 0; o < p.length; o += 9) {
    let above = 0;
    for (let k = 0; k < 3; k++) {
      const h = top - dot(p, o + 3 * k, down);
      corner[k] = h;
      if (h >= at) above++;
    }
    if (above === 0 || above === 3) continue;
    const cut = [];
    for (let k = 0; k < 3; k++) {
      let a = k, b = (k + 1) % 3;
      if ((corner[a] >= at) === (corner[b] >= at)) continue;
      if (before(p, o + 3 * b, o + 3 * a)) [a, b] = [b, a];
      const t = (at - corner[a]) / (corner[b] - corner[a]);
      const pa = o + 3 * a, pb = o + 3 * b;
      cut.push(dot(p, pa, u) + t * (dot(p, pb, u) - dot(p, pa, u)), dot(p, pa, w) + t * (dot(p, pb, w) - dot(p, pa, w)));
    }
    segments.push(cut);
  }
  return segments;
}

// The segments that lie on closed rings, joined as the slice service joins them (its
// first_layer_section merges the cuts into lines and keeps only the closed ones): the cuts are
// chained end to end through every point where exactly two of them meet; a chain that ends where
// it began, with three segments or more, is a ring; any other chain (one left open by a missing
// triangle, or broken where a doubled triangle makes three or four cuts meet) is no part of the
// section. A cut of no length joins nothing.
function rings(segments) {
  const n = segments.length;
  // The ends (end e is end e & 1 of segment e >> 1) sorted by their coordinates, so that equal
  // points, to the last bit, become one node.
  const xs = new Float64Array(2 * n), ys = new Float64Array(2 * n);
  for (let s = 0; s < n; s++) {
    const g = segments[s];
    xs[2 * s] = g[0]; ys[2 * s] = g[1]; xs[2 * s + 1] = g[2]; ys[2 * s + 1] = g[3];
  }
  const order = new Uint32Array(2 * n);
  for (let e = 0; e < 2 * n; e++) order[e] = e;
  order.sort((a, b) => xs[a] - xs[b] || ys[a] - ys[b]);
  const node = new Int32Array(2 * n);
  let nodes = 0;
  for (let k = 0; k < 2 * n; k++) {
    if (k > 0 && (xs[order[k]] !== xs[order[k - 1]] || ys[order[k]] !== ys[order[k - 1]])) nodes++;
    node[order[k]] = nodes;
  }
  nodes++;
  // The segments at each node: at[first[v]] to at[first[v + 1] - 1].
  const joins = (s) => node[2 * s] !== node[2 * s + 1];
  const first = new Int32Array(nodes + 1);
  for (let s = 0; s < n; s++) if (joins(s)) { first[node[2 * s] + 1]++; first[node[2 * s + 1] + 1]++; }
  for (let v = 0; v < nodes; v++) first[v + 1] += first[v];
  const at = new Int32Array(first[nodes]);
  const fill = first.slice(0, nodes);
  for (let s = 0; s < n; s++) if (joins(s)) { at[fill[node[2 * s]]++] = s; at[fill[node[2 * s + 1]]++] = s; }
  const degree = (v) => first[v + 1] - first[v];
  const used = new Uint8Array(n);
  const kept = [];
  const walk = (start, s) => {
    const chain = [];
    let v = start;
    for (;;) {
      used[s] = 1;
      chain.push(s);
      v = node[2 * s] === v ? node[2 * s + 1] : node[2 * s];
      if (v === start || degree(v) !== 2) break;
      s = at[first[v]] === s ? at[first[v] + 1] : at[first[v]];
      if (used[s]) break;
    }
    if (v === start && chain.length >= 3) for (const c of chain) kept.push(segments[c]);
  };
  for (let v = 0; v < nodes; v++) {
    if (degree(v) === 2) continue;
    for (let k = first[v]; k < first[v + 1]; k++) if (!used[at[k]]) walk(v, at[k]);
  }
  for (let s = 0; s < n; s++) if (joins(s) && !used[s]) walk(node[2 * s], s);
  return kept;
}

// The section of the part `at` above the plate: the segments of its rings. Which side of a
// segment is inside is not taken from the triangles' winding: the slice service takes the
// section by the even-odd rule and slices a part wound inside out, so the inside is found by the
// same rule (insideOf below).
function section(mesh, down, at) {
  return rings(cuts(mesh, down, at));
}

// The square of the distance from (px, py) to the segment g ([x0, y0, x1, y1]).
function squaredDistanceToSegment(px, py, g) {
  const x0 = g[0], y0 = g[1], dx = g[2] - x0, dy = g[3] - y0;
  const l2 = dx * dx + dy * dy;
  const t = l2 > 0 ? Math.max(0, Math.min(1, ((px - x0) * dx + (py - y0) * dy) / l2)) : 0;
  const ex = px - x0 - t * dx, ey = py - y0 - t * dy;
  return ex * ex + ey * ey;
}

const SAMPLE_MM = 0.02;              // the step along the section's edge at which discs are tried
const SLACK_MM = 1e-6;
const SIDE_MM = 1e-5;                 // how far off a segment's middle its inside is looked for
const RAY_CELL_MM = 1e-4;             // the narrowest row or column a ray looks in

// Whether one line of the first layer fits in the part's section half a first layer above the
// plate: whether a disc FIRST_LINE_MM across fits inside it. A disc that fits can be moved until
// it touches the edge, so the discs tried are those touching the edge from inside, every
// SAMPLE_MM along it. A segment's inside is the side on which a point just off its middle is
// inside the section by the even-odd rule; a disc touching it there that crosses no segment is
// wholly inside. The ray of that even-odd test runs across the segment (along x for a segment
// nearer to y, along y for one nearer to x), so it meets the segments of its own row or column
// only: on a section of long strips cut finely along their length, a ray along the strips would
// meet every segment of the strip, once for each segment. `work`, when given, counts the
// segments the rays look at (`work.looked`), for a test that bounds it.
export function firstLayerHoldsALine(mesh, down, work = null) {
  const r = FIRST_LINE_MM / 2;
  const segments = section(mesh, down, FIRST_LAYER_MM / 2);
  const cell = 2 * r;
  const grid = new Map();
  const rows = new Map();
  const columns = new Map();
  const key = (i, j) => i * 4194304 + j;    // one number for each cell within ±1 km
  const add = (index, k, s) => {
    if (!index.has(k)) index.set(k, []);
    index.get(k).push(s);
  };
  // The rows and columns the rays look in are as wide as a segment is long on average (and no
  // narrower than RAY_CELL_MM), so that a ray meets the few segments near its own line, and the
  // two indexes hold about as many entries as there are segments.
  let total = 0;
  for (const [x0, y0, x1, y1] of segments) total += Math.abs(x1 - x0) + Math.abs(y1 - y0);
  const band = Math.max(RAY_CELL_MM, total / Math.max(1, segments.length));
  segments.forEach(([x0, y0, x1, y1], s) => {
    for (let i = Math.floor(Math.min(x0, x1) / band); i <= Math.floor(Math.max(x0, x1) / band); i++) add(columns, i, s);
    for (let j = Math.floor(Math.min(y0, y1) / band); j <= Math.floor(Math.max(y0, y1) / band); j++) add(rows, j, s);
    const i0 = Math.floor(Math.min(x0, x1) / cell), i1 = Math.floor(Math.max(x0, x1) / cell);
    for (let j = Math.floor(Math.min(y0, y1) / cell); j <= Math.floor(Math.max(y0, y1) / cell); j++) {
      for (let i = i0; i <= i1; i++) add(grid, key(i, j), s);
    }
  });
  // Even-odd: the segments a ray from (px, py) crosses, counted; towards +x, or towards +y when
  // `alongY`.
  const insideOf = (px, py, alongY) => {
    let inside = false;
    const near = (alongY ? columns.get(Math.floor(px / band)) : rows.get(Math.floor(py / band))) || [];
    if (work) work.looked += near.length;
    for (const s of near) {
      const g = segments[s];
      if (alongY) {
        if ((g[0] > px) === (g[2] > px)) continue;
        if (g[1] + ((px - g[0]) * (g[3] - g[1])) / (g[2] - g[0]) > py) inside = !inside;
      } else {
        if ((g[1] > py) === (g[3] > py)) continue;
        if (g[0] + ((py - g[1]) * (g[2] - g[0])) / (g[3] - g[1]) > px) inside = !inside;
      }
    }
    return inside;
  };
  const clear = (r - SLACK_MM) ** 2;
  const fits = (cx, cy) => {
    for (let i = Math.floor((cx - r) / cell); i <= Math.floor((cx + r) / cell); i++) {
      for (let j = Math.floor((cy - r) / cell); j <= Math.floor((cy + r) / cell); j++) {
        const here = grid.get(key(i, j));
        if (!here) continue;
        for (let k = 0; k < here.length; k++) {
          if (squaredDistanceToSegment(cx, cy, segments[here[k]]) < clear) return false;
        }
      }
    }
    return true;
  };
  for (let s = 0; s < segments.length; s++) {
    const [x0, y0, x1, y1] = segments[s];
    const len = Math.hypot(x1 - x0, y1 - y0);
    if (len === 0) continue;
    let nx = -(y1 - y0) / len, ny = (x1 - x0) / len;
    const mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
    const alongY = Math.abs(ny) > Math.abs(nx);
    if (!insideOf(mx + SIDE_MM * nx, my + SIDE_MM * ny, alongY)) {
      if (!insideOf(mx - SIDE_MM * nx, my - SIDE_MM * ny, alongY)) continue;   // inside on neither side: no edge
      nx = -nx; ny = -ny;
    }
    const steps = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / SAMPLE_MM));
    for (let k = 0; k <= steps; k++) {
      const px = x0 + ((x1 - x0) * k) / steps, py = y0 + ((y1 - y0) * k) / steps;
      if (fits(px + r * nx, py + r * ny)) return true;
    }
  }
  return false;
}

// The slice service's two conditions together: under REST_AREA_MM2 of its own faces on the
// plate, and no line of the first layer in its section.
export function restsOnNoFace(mesh, down) {
  return contactArea(mesh, down) < REST_AREA_MM2 && !firstLayerHoldsALine(mesh, down);
}
