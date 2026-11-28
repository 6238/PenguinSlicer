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

// The section of the part `at` above the plate, as segments [x0, y0, x1, y1] in the plate's own
// directions, each with the direction into the part beside it ([nx, ny], or null for a triangle
// lying nearly flat).
function section(mesh, down, at) {
  const p = mesh.positions;
  const top = topOf(p, down);
  const [u, w] = planeBasis(down);
  const segments = [];
  const inward = [];
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
      const a = k, b = (k + 1) % 3;
      if ((corner[a] >= at) === (corner[b] >= at)) continue;
      const t = (at - corner[a]) / (corner[b] - corner[a]);
      const pa = o + 3 * a, pb = o + 3 * b;
      cut.push(dot(p, pa, u) + t * (dot(p, pb, u) - dot(p, pa, u)), dot(p, pa, w) + t * (dot(p, pb, w) - dot(p, pa, w)));
    }
    // The triangle's outward normal, seen from above: the part lies on the other side.
    const e1 = [p[o + 3] - p[o], p[o + 4] - p[o + 1], p[o + 5] - p[o + 2]];
    const e2 = [p[o + 6] - p[o], p[o + 7] - p[o + 1], p[o + 8] - p[o + 2]];
    const n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
    const [x0, y0, x1, y1] = cut;
    const len = Math.hypot(x1 - x0, y1 - y0);
    const tx = len > 0 ? (x1 - x0) / len : 0, ty = len > 0 ? (y1 - y0) / len : 0;
    let nx = -(n[0] * u[0] + n[1] * u[1] + n[2] * u[2]);
    let ny = -(n[0] * w[0] + n[1] * w[1] + n[2] * w[2]);
    const along = nx * tx + ny * ty;
    nx -= along * tx; ny -= along * ty;
    const m = Math.hypot(nx, ny);
    segments.push(cut);
    inward.push(len > 0 && m > 1e-9 * Math.hypot(...n) ? [nx / m, ny / m] : null);
  }
  return { segments, inward };
}

function distanceToSegment(px, py, [x0, y0, x1, y1]) {
  const dx = x1 - x0, dy = y1 - y0;
  const l2 = dx * dx + dy * dy;
  const t = l2 > 0 ? Math.max(0, Math.min(1, ((px - x0) * dx + (py - y0) * dy) / l2)) : 0;
  return Math.hypot(px - x0 - t * dx, py - y0 - t * dy);
}

const SAMPLE_MM = 0.02;               // the step along the section's edge at which discs are tried
const SLACK_MM = 1e-6;

// Whether one line of the first layer fits in the part's section half a first layer above the
// plate: whether a disc FIRST_LINE_MM across fits inside it. A disc that fits can be moved until
// it touches the edge, so the discs tried are those touching the edge from inside, every
// SAMPLE_MM along it.
export function firstLayerHoldsALine(mesh, down) {
  const r = FIRST_LINE_MM / 2;
  const { segments, inward } = section(mesh, down, FIRST_LAYER_MM / 2);
  const cell = 2 * r;
  const grid = new Map();
  const key = (i, j) => `${i},${j}`;
  segments.forEach(([x0, y0, x1, y1], s) => {
    for (let i = Math.floor(Math.min(x0, x1) / cell); i <= Math.floor(Math.max(x0, x1) / cell); i++) {
      for (let j = Math.floor(Math.min(y0, y1) / cell); j <= Math.floor(Math.max(y0, y1) / cell); j++) {
        const k = key(i, j);
        if (!grid.has(k)) grid.set(k, []);
        grid.get(k).push(s);
      }
    }
  });
  const fits = (cx, cy) => {
    for (let i = Math.floor((cx - r) / cell); i <= Math.floor((cx + r) / cell); i++) {
      for (let j = Math.floor((cy - r) / cell); j <= Math.floor((cy + r) / cell); j++) {
        for (const s of grid.get(key(i, j)) || []) {
          if (distanceToSegment(cx, cy, segments[s]) < r - SLACK_MM) return false;
        }
      }
    }
    return true;
  };
  for (let s = 0; s < segments.length; s++) {
    if (!inward[s]) continue;
    const [x0, y0, x1, y1] = segments[s];
    const [nx, ny] = inward[s];
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
