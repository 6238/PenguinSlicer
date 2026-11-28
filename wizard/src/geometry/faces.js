// Finding the faces a part can lie on (wizard/README.md, "Finding the faces a part can lie on";
// the method of docs/research/2026-11-21-lay-on-face-hull-faces.md, written fresh):
//   1. the part's convex hull (hull.js);
//   2. hull triangles joined into flat faces, spreading to neighbours whose normal is within
//      FACE_JOIN_DEG of the first triangle's;
//   3. faces dropped under MIN_FACE_MM2, with a corner sharper than SLIVER_DEG, and beyond the
//      MAX_FACES largest;
//   4. a face dropped when a neighbouring hull face bends from it by less than ROUND_SIDE_DEG
//      and is at least half its size (the facets of a round side);
//   5. a bounding-box patch for each side of the part's bounding box that no kept face points
//      within BBOX_COVER_DEG of.
// Everything is in the part's own coordinates, so the faces turn with an instance for free.
import {
  BBOX_COVER_DEG, FACE_JOIN_DEG, MAX_FACES, MIN_FACE_MM2, ROUND_SIDE_DEG, SLIVER_DEG,
} from './constants.js';
import { area as outlineArea, convexHull2d, sharpestCorner } from './outline.js';

const COS = (deg) => Math.cos((deg * Math.PI) / 180);

export const BOX_SIDES = [
  ['+x', [1, 0, 0]], ['-x', [-1, 0, 0]],
  ['+y', [0, 1, 0]], ['-y', [0, -1, 0]],
  ['+z', [0, 0, 1]], ['-z', [0, 0, -1]],
];

// Two directions square to `n`, so that (u, w, n) is right-handed.
export function planeBasis(n) {
  const e = Math.abs(n[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
  let u = [n[1] * e[2] - n[2] * e[1], n[2] * e[0] - n[0] * e[2], n[0] * e[1] - n[1] * e[0]];
  const len = Math.hypot(...u);
  u = u.map((v) => v / len);
  const w = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0]];
  return [u, w];
}

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

function triangleNormals(hull) {
  const p = hull.points;
  const t = hull.triangles;
  const count = t.length / 3;
  const normals = new Float64Array(count * 3);
  const areas = new Float64Array(count);
  for (let f = 0; f < count; f++) {
    const a = t[f * 3] * 3, b = t[f * 3 + 1] * 3, c = t[f * 3 + 2] * 3;
    const ux = p[b] - p[a], uy = p[b + 1] - p[a + 1], uz = p[b + 2] - p[a + 2];
    const vx = p[c] - p[a], vy = p[c + 1] - p[a + 1], vz = p[c + 2] - p[a + 2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz);
    areas[f] = len / 2;
    if (len > 0) {
      normals[f * 3] = nx / len; normals[f * 3 + 1] = ny / len; normals[f * 3 + 2] = nz / len;
    }
  }
  return { normals, areas };
}

// Step 2: each hull triangle's face, and the faces' triangles.
function joinTriangles(hull, normals) {
  const count = hull.triangles.length / 3;
  const faceOf = new Int32Array(count).fill(-1);
  const groups = [];
  const limit = COS(FACE_JOIN_DEG);
  for (let start = 0; start < count; start++) {
    if (faceOf[start] >= 0) continue;
    const id = groups.length;
    const members = [start];
    faceOf[start] = id;
    const n0 = [normals[start * 3], normals[start * 3 + 1], normals[start * 3 + 2]];
    for (let k = 0; k < members.length; k++) {
      const f = members[k];
      for (let e = 0; e < 3; e++) {
        const g = hull.neighbours[f * 3 + e];
        if (faceOf[g] >= 0) continue;
        if (n0[0] * normals[g * 3] + n0[1] * normals[g * 3 + 1] + n0[2] * normals[g * 3 + 2] >= limit) {
          faceOf[g] = id;
          members.push(g);
        }
      }
    }
    groups.push(members);
  }
  return { faceOf, groups };
}

function describeFace(hull, members, normals, areas) {
  const p = hull.points;
  const t = hull.triangles;
  let nx = 0, ny = 0, nz = 0, total = 0;
  const corners = new Set();
  for (const f of members) {
    nx += normals[f * 3] * areas[f]; ny += normals[f * 3 + 1] * areas[f]; nz += normals[f * 3 + 2] * areas[f];
    total += areas[f];
    for (let e = 0; e < 3; e++) corners.add(t[f * 3 + e]);
  }
  let len = Math.hypot(nx, ny, nz);
  if (!(len > 0)) {
    const f = members[0];
    nx = normals[f * 3]; ny = normals[f * 3 + 1]; nz = normals[f * 3 + 2];
    len = Math.hypot(nx, ny, nz) || 1;
  }
  const normal = [nx / len, ny / len, nz / len];
  const [u, w] = planeBasis(normal);
  let offset = 0;
  const flat = [];
  for (const c of corners) {
    const q = [p[c * 3], p[c * 3 + 1], p[c * 3 + 2]];
    offset += dot(q, normal);
    flat.push([dot(q, u), dot(q, w)]);
  }
  offset /= corners.size;
  const outline2d = convexHull2d(flat);
  const outline = outline2d.map(([a, b]) => [0, 1, 2].map((k) => a * u[k] + b * w[k] + offset * normal[k]));
  const measured = outline2d.length >= 3 ? outlineArea(outline2d) : 0;
  return {
    normal, area: measured > 0 ? measured : total, outline,
    sharpest: outline2d.length >= 3 ? sharpestCorner(outline2d) : 0,
    triangles: members.length, neighbours: new Set(), dropped: null,
  };
}

function boxPatch(side, direction, box) {
  const [lo, hi] = [box.min, box.max];
  const axis = direction.findIndex((v) => v !== 0);
  const at = direction[axis] > 0 ? hi[axis] : lo[axis];
  const [a, b] = [0, 1, 2].filter((k) => k !== axis);
  // The side's rectangle, counterclockwise seen from outside.
  let corners = [[lo[a], lo[b]], [hi[a], lo[b]], [hi[a], hi[b]], [lo[a], hi[b]]];
  // (a, b, axis) is right-handed for x (y, z), y (z, x)... only with a and b in cyclic order.
  const cyclic = (axis + 1) % 3 === a;
  if (cyclic !== direction[axis] > 0) corners = corners.reverse();
  const outline = corners.map(([va, vb]) => {
    const q = [0, 0, 0];
    q[axis] = at; q[a] = va; q[b] = vb;
    return q;
  });
  const area = (hi[a] - lo[a]) * (hi[b] - lo[b]);
  return { kind: 'box', side, normal: direction.slice(), area, outline };
}

// The faces of `hull` and the patches a part can be laid down by. `box` holds the part's
// bounding box (`min`, `max`). Each face is {normal, area, outline, dropped}, `dropped` naming
// the step that left it out ('small', 'sliver', 'beyond_max', 'round_side') or null; each patch
// {kind: 'hull' | 'box', normal, area, outline, face | side}.
export function findFaces(hull, box) {
  const { normals, areas } = triangleNormals(hull);
  const { faceOf, groups } = joinTriangles(hull, normals);
  const faces = groups.map((members) => describeFace(hull, members, normals, areas));
  const t = hull.triangles;
  for (let f = 0; f < t.length / 3; f++) {
    for (let e = 0; e < 3; e++) {
      const a = faceOf[f];
      const b = faceOf[hull.neighbours[f * 3 + e]];
      if (a !== b) faces[a].neighbours.add(b);
    }
  }
  // Step 3.
  for (const face of faces) {
    if (face.area < MIN_FACE_MM2) face.dropped = 'small';
    else if (face.sharpest < SLIVER_DEG) face.dropped = 'sliver';
  }
  const ranked = faces.filter((f) => !f.dropped).sort((a, b) => b.area - a.area);
  for (const face of ranked.slice(MAX_FACES)) face.dropped = 'beyond_max';
  // Step 4, judged against every neighbour on the hull, whatever became of it.
  const round = COS(ROUND_SIDE_DEG);
  const facets = faces.filter((face) => !face.dropped && [...face.neighbours].some((k) => {
    const other = faces[k];
    return dot(face.normal, other.normal) > round && other.area >= face.area / 2;
  }));
  for (const face of facets) face.dropped = 'round_side';
  const kept = faces.filter((f) => !f.dropped);
  const patches = kept.map((face) => ({
    kind: 'hull', face: faces.indexOf(face), normal: face.normal, area: face.area, outline: face.outline,
  }));
  // Step 5.
  const cover = COS(BBOX_COVER_DEG);
  for (const [side, direction] of BOX_SIDES) {
    if (!kept.some((face) => dot(face.normal, direction) >= cover)) patches.push(boxPatch(side, direction, box));
  }
  return {
    hullTriangles: t.length / 3,
    faces: faces.map(({ neighbours, ...rest }) => ({ ...rest, neighbours: [...neighbours] })),
    patches,
  };
}
