// Small solids for the geometry's tests, as the worker would read them from an STL: `positions`
// holds each triangle's corners, wound outwards, with the bounding box beside them.

function boxOf(positions) {
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i++) {
    const k = i % 3;
    if (positions[i] < min[k]) min[k] = positions[i];
    if (positions[i] > max[k]) max[k] = positions[i];
  }
  return { min, max };
}

export function meshOf(triangles) {
  const positions = new Float64Array(triangles.flat(2));
  return { triangles: triangles.length, positions, ...boxOf(positions) };
}

// A prism: the polygon `outline` ([x, y] corners, counterclockwise seen from +z) from z0 to z1.
export function prism(outline, z0, z1) {
  const tris = [];
  const n = outline.length;
  for (let i = 1; i < n - 1; i++) {
    const [a, b, c] = [outline[0], outline[i], outline[i + 1]];
    tris.push([[a[0], a[1], z1], [b[0], b[1], z1], [c[0], c[1], z1]]);
    tris.push([[a[0], a[1], z0], [c[0], c[1], z0], [b[0], b[1], z0]]);
  }
  for (let i = 0; i < n; i++) {
    const p = outline[i];
    const q = outline[(i + 1) % n];
    tris.push([[p[0], p[1], z0], [q[0], q[1], z0], [q[0], q[1], z1]]);
    tris.push([[p[0], p[1], z0], [q[0], q[1], z1], [p[0], p[1], z1]]);
  }
  return meshOf(tris);
}

// Solids joined into one: their triangles together (they may touch along a face, which the hull
// and the scoring both see through).
export function union(...meshes) {
  const tris = [];
  for (const m of meshes) {
    const p = m.positions;
    for (let i = 0; i < p.length; i += 9) {
      tris.push([[p[i], p[i + 1], p[i + 2]], [p[i + 3], p[i + 4], p[i + 5]], [p[i + 6], p[i + 7], p[i + 8]]]);
    }
  }
  return meshOf(tris);
}

export function moved(mesh, [dx, dy, dz]) {
  const out = new Float64Array(mesh.positions);
  for (let i = 0; i < out.length; i += 3) { out[i] += dx; out[i + 1] += dy; out[i + 2] += dz; }
  return { triangles: mesh.triangles, positions: out, ...boxOf(out) };
}

// An oblique prism: the polygon `outline` at z = 0 and the same polygon moved by (dx, 0, h) at
// the top, so that the solid leans along x.
export function leaning(outline, dx, h) {
  const tris = [];
  const n = outline.length;
  const top = (p) => [p[0] + dx, p[1], h];
  const bottom = (p) => [p[0], p[1], 0];
  for (let i = 1; i < n - 1; i++) {
    const [a, b, c] = [outline[0], outline[i], outline[i + 1]];
    tris.push([top(a), top(b), top(c)]);
    tris.push([bottom(a), bottom(c), bottom(b)]);
  }
  for (let i = 0; i < n; i++) {
    const p = outline[i];
    const q = outline[(i + 1) % n];
    tris.push([bottom(p), bottom(q), top(q)]);
    tris.push([bottom(p), top(q), top(p)]);
  }
  return meshOf(tris);
}

export const box = (x, y, z) => prism([[0, 0], [x, 0], [x, y], [0, y]], 0, z);

export function regularPolygon(sides, radius, phase = 0) {
  return Array.from({ length: sides }, (_, i) => {
    const t = phase + (2 * Math.PI * i) / sides;
    return [radius * Math.cos(t), radius * Math.sin(t)];
  });
}

export const cylinder = (sides, radius, height) => prism(regularPolygon(sides, radius), 0, height);

// A star prism: `points` tips at radius `outer` (the first on +x) and as many notches at radius
// `inner` between them, from z = 0 to `height`. Its ends are fanned from the axis, since the star
// is not convex.
export function starPrism(points, outer, inner, height) {
  const outline = Array.from({ length: 2 * points }, (_, i) => {
    const t = (Math.PI * i) / points;
    const r = i % 2 ? inner : outer;
    return [r * Math.cos(t), r * Math.sin(t)];
  });
  const tris = [];
  const n = outline.length;
  for (let i = 0; i < n; i++) {
    const p = outline[i];
    const q = outline[(i + 1) % n];
    tris.push([[0, 0, height], [p[0], p[1], height], [q[0], q[1], height]]);
    tris.push([[0, 0, 0], [q[0], q[1], 0], [p[0], p[1], 0]]);
    tris.push([[p[0], p[1], 0], [q[0], q[1], 0], [q[0], q[1], height]]);
    tris.push([[p[0], p[1], 0], [q[0], q[1], height], [p[0], p[1], height]]);
  }
  return meshOf(tris);
}

// A mesh turned by the row-major 3 x 3 matrix `m`.
export function turned(mesh, m) {
  const p = mesh.positions;
  const out = new Float64Array(p.length);
  for (let i = 0; i < p.length; i += 3) {
    for (let r = 0; r < 3; r++) out[i + r] = m[r][0] * p[i] + m[r][1] * p[i + 1] + m[r][2] * p[i + 2];
  }
  return { triangles: mesh.triangles, positions: out, ...boxOf(out) };
}

export function rotationZ(deg) {
  const t = (deg * Math.PI) / 180;
  return [[Math.cos(t), -Math.sin(t), 0], [Math.sin(t), Math.cos(t), 0], [0, 0, 1]];
}

export function rotationX(deg) {
  const t = (deg * Math.PI) / 180;
  return [[1, 0, 0], [0, Math.cos(t), -Math.sin(t)], [0, Math.sin(t), Math.cos(t)]];
}
