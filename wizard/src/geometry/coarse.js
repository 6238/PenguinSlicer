// A coarse copy of a part for drawing while the Layout view moves (a drag, a turn, the camera
// turning): the part's corners gathered into the squares of a grid over its box, each square's
// corners drawn at their mean, and every triangle whose three corners fall in three different
// squares kept once. The part itself is never changed. Without a graphics card the view draws
// about three million triangles a second, so 150 instances of real parts (800,000 triangles) draw
// at 4 frames a second and the coarse copies at the target's 10.

// The coarse copy of `positions` (each triangle's three corners, x y z) with at most
// `maxTriangles` triangles where a grid can give that: grids of 64 down to 4 squares along the
// box's longest side are tried in turn, the finest within the figure kept. Answers
// {positions: Float32Array, triangles, cells}.
export function coarseCopy(positions, maxTriangles) {
  const n = positions.length / 3;
  let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
  for (let i = 0; i < n; i++) {
    const x = positions[i * 3], y = positions[i * 3 + 1], z = positions[i * 3 + 2];
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
    if (z < z0) z0 = z; if (z > z1) z1 = z;
  }
  if (n / 3 <= maxTriangles) return { positions: Float32Array.from(positions), triangles: n / 3, cells: 0 };
  const longest = Math.max(x1 - x0, y1 - y0, z1 - z0) || 1;
  let best = null;
  for (const cells of [64, 48, 32, 24, 16, 12, 8, 6, 4]) {
    best = gather(positions, n, [x0, y0, z0], longest / cells, cells);
    if (best.triangles <= maxTriangles) break;
  }
  return best;
}

function gather(positions, n, origin, size, cells) {
  const span = cells + 1;
  const keyOf = new Int32Array(n);
  const sums = new Map();
  for (let i = 0; i < n; i++) {
    const cx = Math.min(cells, Math.floor((positions[i * 3] - origin[0]) / size));
    const cy = Math.min(cells, Math.floor((positions[i * 3 + 1] - origin[1]) / size));
    const cz = Math.min(cells, Math.floor((positions[i * 3 + 2] - origin[2]) / size));
    const key = (cx * span + cy) * span + cz;
    keyOf[i] = key;
    let s = sums.get(key);
    if (!s) { s = [0, 0, 0, 0]; sums.set(key, s); }
    s[0] += positions[i * 3]; s[1] += positions[i * 3 + 1]; s[2] += positions[i * 3 + 2]; s[3] += 1;
  }
  const kept = [];
  const seen = new Set();
  for (let t = 0; t < n / 3; t++) {
    const a = keyOf[t * 3], b = keyOf[t * 3 + 1], c = keyOf[t * 3 + 2];
    if (a === b || b === c || a === c) continue;
    // the same three squares in the same turning order are one triangle
    const r = a < b && a < c ? [a, b, c] : b < c ? [b, c, a] : [c, a, b];
    const id = `${r[0]},${r[1]},${r[2]}`;
    if (seen.has(id)) continue;
    seen.add(id);
    kept.push(a, b, c);
  }
  const out = new Float32Array(kept.length * 3);
  kept.forEach((key, k) => {
    const s = sums.get(key);
    out[k * 3] = s[0] / s[3]; out[k * 3 + 1] = s[1] / s[3]; out[k * 3 + 2] = s[2] / s[3];
  });
  return { positions: out, triangles: kept.length / 3, cells };
}
