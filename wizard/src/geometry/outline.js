// Convex outlines in a plane: a face's outline in its own plane, an instance's footprint seen
// from above. An outline is an array of [x, y] corners, counterclockwise, with no corner
// repeated and none on a straight line between its neighbours.

const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);

// The convex hull of `points` ([x, y] each), by the monotone chain.
export function convexHull2d(points) {
  const q = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (q.length < 3) return q;
  const lower = [];
  for (const p of q) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper = [];
  for (let i = q.length - 1; i >= 0; i--) {
    const p = q[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}

export function area(outline) {
  let s = 0;
  for (let i = 0, j = outline.length - 1; i < outline.length; j = i++) {
    s += outline[j][0] * outline[i][1] - outline[i][0] * outline[j][1];
  }
  return s / 2;
}

// The sharpest corner of a convex outline, in degrees.
export function sharpestCorner(outline) {
  const n = outline.length;
  let least = 180;
  for (let i = 0; i < n; i++) {
    const p = outline[(i + n - 1) % n];
    const o = outline[i];
    const q = outline[(i + 1) % n];
    const ax = p[0] - o[0], ay = p[1] - o[1], bx = q[0] - o[0], by = q[1] - o[1];
    const cos = (ax * bx + ay * by) / (Math.hypot(ax, ay) * Math.hypot(bx, by));
    const deg = (Math.acos(Math.max(-1, Math.min(1, cos))) * 180) / Math.PI;
    if (deg < least) least = deg;
  }
  return least;
}

// Whether the point (x, y) is inside the convex outline, or on its edge within `tol`.
export function containsPoint(outline, x, y, tol = 0) {
  const n = outline.length;
  if (n < 3) return false;
  for (let i = 0; i < n; i++) {
    const a = outline[i];
    const b = outline[(i + 1) % n];
    const ex = b[0] - a[0], ey = b[1] - a[1];
    const len = Math.hypot(ex, ey);
    if (len === 0) continue;
    // Distance of the point to the right of the edge (outside, for a counterclockwise outline).
    if ((ex * (y - a[1]) - ey * (x - a[0])) / len < -tol) return false;
  }
  return true;
}

function segmentPointDistance2(a, b, p) {
  const ex = b[0] - a[0], ey = b[1] - a[1];
  const len2 = ex * ex + ey * ey;
  let t = len2 > 0 ? ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / len2 : 0;
  t = Math.max(0, Math.min(1, t));
  const dx = a[0] + t * ex - p[0], dy = a[1] + t * ey - p[1];
  return dx * dx + dy * dy;
}

// Whether two convex outlines overlap (touching counts), by separating axes.
function overlap(a, b) {
  for (const [p, q] of [[a, b], [b, a]]) {
    const n = p.length;
    for (let i = 0; i < n; i++) {
      const s = p[i];
      const e = p[(i + 1) % n];
      const nx = e[1] - s[1], ny = s[0] - e[0];
      let minQ = Infinity;
      for (const c of q) minQ = Math.min(minQ, (c[0] - s[0]) * nx + (c[1] - s[1]) * ny);
      if (minQ > 0) return false;
    }
  }
  return true;
}

// The least distance between two convex outlines; 0 when they overlap or one holds the other.
export function distance(a, b) {
  if (overlap(a, b)) return 0;
  let best = Infinity;
  for (const [p, q] of [[a, b], [b, a]]) {
    for (let i = 0; i < p.length; i++) {
      const s = p[i];
      const e = p[(i + 1) % p.length];
      for (const c of q) best = Math.min(best, segmentPointDistance2(s, e, c));
    }
  }
  return Math.sqrt(best);
}

// The outline's bounds: [minX, minY, maxX, maxY].
export function bounds(outline) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of outline) {
    if (x < x0) x0 = x;
    if (y < y0) y0 = y;
    if (x > x1) x1 = x;
    if (y > y1) y1 = y;
  }
  return [x0, y0, x1, y1];
}

// An outline of at most `directions` corners that holds `outline`: the intersection of its
// supporting half-planes in that many evenly spread directions. Arrange packs these, so that
// it compares a few corners where a round part's footprint has hundreds; it never lets two
// instances closer than the true outlines are, only (by at most a few hundredths of the
// part's size) farther.
export function simplified(outline, directions = 32) {
  return outline.length <= directions ? outline : grown(outline, 0, directions);
}

// An outline of `directions` corners holding every point within `r` of `outline`: its
// supporting half-planes in that many directions, each moved out by `r`.
export function grown(outline, r, directions = 32) {
  const lines = [];
  for (let k = 0; k < directions; k++) {
    const t = (2 * Math.PI * k) / directions;
    const nx = Math.cos(t), ny = Math.sin(t);
    let h = -Infinity;
    for (const [x, y] of outline) h = Math.max(h, x * nx + y * ny);
    lines.push([nx, ny, h + r]);
  }
  const out = [];
  for (let k = 0; k < directions; k++) {
    const [ax, ay, ah] = lines[k];
    const [bx, by, bh] = lines[(k + 1) % directions];
    const det = ax * by - ay * bx;
    out.push([(ah * by - bh * ay) / det, (ax * bh - bx * ah) / det]);
  }
  return out;
}

export function turnedOutline(outline, deg) {
  if (deg % 360 === 0) return outline.map(([x, y]) => [x, y]);
  const [c, s] = cosSin(deg);
  return outline.map(([x, y]) => [c * x - s * y, s * x + c * y]);
}

// cos and sin of `deg` degrees, exact on multiples of 90, as the slice service computes them.
export function cosSin(deg) {
  if (deg % 90 === 0) return [[1, 0], [0, 1], [-1, 0], [0, -1]][((deg / 90) % 4 + 4) % 4];
  const t = (deg * Math.PI) / 180;
  return [Math.cos(t), Math.sin(t)];
}
