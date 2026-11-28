// The convex hull of a part's corners, by the quickhull method: a tetrahedron of far-apart
// corners, then, face by face, the corner farthest outside it is added and the faces it sees are
// replaced by a fan to the edge of what it sees. Each face keeps the corners outside it, so a
// corner is only ever compared with the faces near it; the time grows with the corners times
// the log of the hull's size, not with their product. Written fresh for PenguinSlicer.
import { HULL_EPS_MM } from './constants.js';
import { GeometryError } from './errors.js';

function makeFace(pts, a, b, c) {
  const ax = pts[a * 3], ay = pts[a * 3 + 1], az = pts[a * 3 + 2];
  const ux = pts[b * 3] - ax, uy = pts[b * 3 + 1] - ay, uz = pts[b * 3 + 2] - az;
  const vx = pts[c * 3] - ax, vy = pts[c * 3 + 1] - ay, vz = pts[c * 3 + 2] - az;
  let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
  const len = Math.hypot(nx, ny, nz) || 1;
  nx /= len; ny /= len; nz /= len;
  return { v: [a, b, c], nx, ny, nz, d: nx * ax + ny * ay + nz * az, nb: [null, null, null], alive: true, out: [], seen: 0 };
}

const distance = (pts, f, i) => f.nx * pts[i * 3] + f.ny * pts[i * 3 + 1] + f.nz * pts[i * 3 + 2] - f.d;

function farthestFromLine(pts, n, i0, i1) {
  const ax = pts[i0 * 3], ay = pts[i0 * 3 + 1], az = pts[i0 * 3 + 2];
  let dx = pts[i1 * 3] - ax, dy = pts[i1 * 3 + 1] - ay, dz = pts[i1 * 3 + 2] - az;
  const len = Math.hypot(dx, dy, dz);
  dx /= len; dy /= len; dz /= len;
  let best = -1, bestD = -1;
  for (let i = 0; i < n; i++) {
    const px = pts[i * 3] - ax, py = pts[i * 3 + 1] - ay, pz = pts[i * 3 + 2] - az;
    const along = px * dx + py * dy + pz * dz;
    const d2 = px * px + py * py + pz * pz - along * along;
    if (d2 > bestD) { bestD = d2; best = i; }
  }
  return [best, Math.sqrt(Math.max(0, bestD))];
}

function initialSimplex(pts, n) {
  const extremes = [];
  for (let k = 0; k < 3; k++) {
    let lo = 0, hi = 0;
    for (let i = 1; i < n; i++) {
      if (pts[i * 3 + k] < pts[lo * 3 + k]) lo = i;
      if (pts[i * 3 + k] > pts[hi * 3 + k]) hi = i;
    }
    extremes.push(lo, hi);
  }
  let i0 = extremes[0], i1 = extremes[1], far = -1;
  for (const a of extremes) {
    for (const b of extremes) {
      const d = Math.hypot(pts[a * 3] - pts[b * 3], pts[a * 3 + 1] - pts[b * 3 + 1], pts[a * 3 + 2] - pts[b * 3 + 2]);
      if (d > far) { far = d; i0 = a; i1 = b; }
    }
  }
  if (!(far > HULL_EPS_MM)) throw new GeometryError('the part has no size: every corner is at one point');
  const [i2, lineD] = farthestFromLine(pts, n, i0, i1);
  if (!(lineD > HULL_EPS_MM)) throw new GeometryError('the part has no width: every corner is on one line');
  const base = makeFace(pts, i0, i1, i2);
  let i3 = -1, planeD = 0;
  for (let i = 0; i < n; i++) {
    const d = distance(pts, base, i);
    if (Math.abs(d) > Math.abs(planeD)) { planeD = d; i3 = i; }
  }
  if (!(Math.abs(planeD) > HULL_EPS_MM)) throw new GeometryError('the part is flat: every corner is in one plane');
  return [i0, i1, i2, i3];
}

// The corners with each repeat left out: an STL repeats every corner in each triangle that
// meets there, six times on average. Corners are equal only when every coordinate is.
function uniquePoints(points) {
  const n = Math.floor(points.length / 3);
  let size = 1;
  while (size < n * 2) size *= 2;
  const table = new Int32Array(size).fill(-1);
  const out = new Float64Array(n * 3);
  const bits = new Uint32Array(new Float64Array([0]).buffer);
  const f64 = new Float64Array(bits.buffer);
  let count = 0;
  for (let i = 0; i < n; i++) {
    const x = points[i * 3], y = points[i * 3 + 1], z = points[i * 3 + 2];
    let h = 2166136261;
    for (const v of [x, y, z]) {
      f64[0] = v;
      h = Math.imul(h ^ bits[0], 16777619);
      h = Math.imul(h ^ bits[1], 16777619);
    }
    let slot = (h >>> 0) & (size - 1);
    for (;;) {
      const k = table[slot];
      if (k < 0) {
        table[slot] = count;
        out[count * 3] = x; out[count * 3 + 1] = y; out[count * 3 + 2] = z;
        count += 1;
        break;
      }
      if (out[k * 3] === x && out[k * 3 + 1] === y && out[k * 3 + 2] === z) break;
      slot = (slot + 1) & (size - 1);
    }
  }
  return out.subarray(0, count * 3);
}

// Joins `faces`, closed as a surface, across their shared edges.
function link(faces) {
  const edges = new Map();
  for (const f of faces) for (let e = 0; e < 3; e++) edges.set(`${f.v[e]},${f.v[(e + 1) % 3]}`, [f, e]);
  for (const f of faces) {
    for (let e = 0; e < 3; e++) {
      const [g] = edges.get(`${f.v[(e + 1) % 3]},${f.v[e]}`);
      f.nb[e] = g;
    }
  }
}

// `points` is a flat array of corners (x, y, z, ...), repeated corners allowed. The result's
// `points` are the hull's corners, `triangles` three indices into them for each face, wound
// outwards, and `neighbours` for each face the face across each of its edges (edge e runs from
// corner e to corner e + 1).
export function convexHull(points) {
  const pts = uniquePoints(points);
  const n = Math.floor(pts.length / 3);
  if (n < 4) throw new GeometryError(`the part has ${n} corners, too few to enclose anything`);
  const [a, b, c, d] = initialSimplex(pts, n);
  const faces = [[a, b, c], [a, c, d], [a, d, b], [b, d, c]].map(([p, q, r], k) => {
    const opposite = [d, b, c, a][k];
    let f = makeFace(pts, p, q, r);
    if (distance(pts, f, opposite) > 0) f = makeFace(pts, p, r, q);
    return f;
  });
  link(faces);
  const all = faces.slice();
  for (let i = 0; i < n; i++) {
    if (i === a || i === b || i === c || i === d) continue;
    let best = null, bestD = HULL_EPS_MM;
    for (const f of faces) {
      const dist = distance(pts, f, i);
      if (dist > bestD) { bestD = dist; best = f; }
    }
    if (best) best.out.push(i);
  }
  const pending = faces.filter((f) => f.out.length > 0);
  let round = 0;
  while (pending.length > 0) {
    const face = pending.pop();
    if (!face.alive || face.out.length === 0) continue;
    round += 1;
    let eye = -1, eyeD = -Infinity;
    for (const i of face.out) {
      const dist = distance(pts, face, i);
      if (dist > eyeD) { eyeD = dist; eye = i; }
    }
    // The faces the eye sees, and the edge of what it sees (the horizon).
    const visible = [face];
    const horizon = [];
    face.seen = round;
    for (let k = 0; k < visible.length; k++) {
      const f = visible[k];
      for (let e = 0; e < 3; e++) {
        const g = f.nb[e];
        if (g.seen === round) continue;
        if (distance(pts, g, eye) > HULL_EPS_MM) {
          g.seen = round;
          visible.push(g);
        } else {
          horizon.push([f, e]);
        }
      }
    }
    // A face the eye does not see but which neighbours two visible faces is still on the
    // horizon twice; each of its edges is a separate horizon edge, so nothing more is needed.
    const orphans = [];
    for (const f of visible) {
      f.alive = false;
      for (const i of f.out) if (i !== eye) orphans.push(i);
      f.out = [];
    }
    const fresh = [];
    const startingAt = new Map();
    for (const [f, e] of horizon) {
      const p = f.v[e];
      const q = f.v[(e + 1) % 3];
      const g = f.nb[e];
      const nf = makeFace(pts, p, q, eye);
      nf.nb[0] = g;
      for (let k = 0; k < 3; k++) if (g.nb[k] === f) g.nb[k] = nf;
      if (startingAt.has(p)) throw new GeometryError('the hull could not be closed: the part\'s corners are too close to tell apart');
      startingAt.set(p, nf);
      fresh.push(nf);
    }
    for (const nf of fresh) {
      const next = startingAt.get(nf.v[1]);
      if (!next) throw new GeometryError('the hull could not be closed: the part\'s corners are too close to tell apart');
      nf.nb[1] = next;
      next.nb[2] = nf;
    }
    for (const i of orphans) {
      let best = null, bestD = HULL_EPS_MM;
      for (const nf of fresh) {
        const dist = distance(pts, nf, i);
        if (dist > bestD) { bestD = dist; best = nf; }
      }
      if (best) best.out.push(i);
    }
    for (const nf of fresh) {
      all.push(nf);
      if (nf.out.length > 0) pending.push(nf);
    }
  }
  const alive = all.filter((f) => f.alive);
  const index = new Map(alive.map((f, k) => [f, k]));
  const corner = new Map();
  const out = [];
  const triangles = new Int32Array(alive.length * 3);
  const neighbours = new Int32Array(alive.length * 3);
  alive.forEach((f, k) => {
    for (let e = 0; e < 3; e++) {
      const v = f.v[e];
      if (!corner.has(v)) {
        corner.set(v, corner.size);
        out.push(pts[v * 3], pts[v * 3 + 1], pts[v * 3 + 2]);
      }
      triangles[k * 3 + e] = corner.get(v);
      neighbours[k * 3 + e] = index.get(f.nb[e]);
    }
  });
  return { points: new Float64Array(out), triangles, neighbours };
}
