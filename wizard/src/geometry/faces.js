// Finding the faces a part can lie on (wizard/README.md, "Finding the faces a part can lie on";
// the method of docs/research/2026-11-21-lay-on-face-hull-faces.md, written fresh):
//   1. the part's convex hull (hull.js);
//   2. hull triangles joined into flat faces, spreading to neighbours whose normal is within
//      FACE_JOIN_DEG of the first triangle's;
//   3. faces dropped under MIN_FACE_MM2, with a corner sharper than SLIVER_DEG, and beyond the
//      MAX_FACES largest;
//   4. a face dropped when a neighbouring hull face bends from it by less than ROUND_SIDE_DEG
//      and is at least half its size (the facets of a round side), unless the face is the
//      part's own surface, at least MIN_CONTACT_MM2, and that neighbour mostly bridges a
//      hollow or a step;
//   5. a bounding-box patch for each side of the part's bounding box that no kept face points
//      within BBOX_COVER_DEG of.
// Everything is in the part's own coordinates, so the faces turn with an instance for free.
import {
  BBOX_COVER_DEG, FACE_JOIN_DEG, FLAT_GAP_MM, FLAT_TURN_DEG, MAX_FACES, MIN_CONTACT_MM2, MIN_FACE_MM2,
  ROUND_SIDE_DEG, SLIVER_DEG,
} from './constants.js';
import { area as outlineArea, containsPoint, convexHull2d, sharpestCorner } from './outline.js';

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

// Each mesh triangle's unit normal and area.
function meshTriangles(positions) {
  const count = positions.length / 9;
  const normals = new Float64Array(count * 3);
  const areas = new Float64Array(count);
  for (let t = 0; t < count; t++) {
    const o = t * 9;
    const ux = positions[o + 3] - positions[o], uy = positions[o + 4] - positions[o + 1], uz = positions[o + 5] - positions[o + 2];
    const vx = positions[o + 6] - positions[o], vy = positions[o + 7] - positions[o + 1], vz = positions[o + 8] - positions[o + 2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz);
    areas[t] = len / 2;
    if (len > 0) { normals[t * 3] = nx / len; normals[t * 3 + 1] = ny / len; normals[t * 3 + 2] = nz / len; }
  }
  return { normals, areas };
}

const BUCKET = 16;                // normals sorted into cells about 3.6 degrees across

// For each face of `faces`, the area of the part's own surface lying on it: all of it for a
// flat face of the part, little or none for a hull face that bridges a hollow or a step.
function materialAreas(faces, positions, tri) {
  const key = (x, y, z) => `${x},${y},${z}`;
  const cells = new Map();
  faces.forEach((face, i) => {
    const k = face.normal.map((v) => Math.round(v * BUCKET));
    const d = face.outline.reduce((s, q) => s + dot(q, face.normal), 0) / face.outline.length;
    const [u, w] = planeBasis(face.normal);
    const flat = convexHull2d(face.outline.map((q) => [dot(q, u), dot(q, w)]));
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
      const id = key(k[0] + a, k[1] + b, k[2] + c);
      if (!cells.has(id)) cells.set(id, []);
      cells.get(id).push([i, d, u, w, flat]);
    }
  });
  const material = new Float64Array(faces.length);
  const near = COS(FLAT_TURN_DEG);
  const n = tri.normals;
  for (let t = 0; t < tri.areas.length; t++) {
    const nx = n[t * 3], ny = n[t * 3 + 1], nz = n[t * 3 + 2];
    const list = cells.get(key(Math.round(nx * BUCKET), Math.round(ny * BUCKET), Math.round(nz * BUCKET)));
    if (!list) continue;
    const o = t * 9;
    const cx = (positions[o] + positions[o + 3] + positions[o + 6]) / 3;
    const cy = (positions[o + 1] + positions[o + 4] + positions[o + 7]) / 3;
    const cz = (positions[o + 2] + positions[o + 5] + positions[o + 8]) / 3;
    const c = [cx, cy, cz];
    for (const [i, d, u, w, flat] of list) {
      const f = faces[i].normal;
      if (nx * f[0] + ny * f[1] + nz * f[2] < near) continue;
      if (Math.abs(cx * f[0] + cy * f[1] + cz * f[2] - d) >= FLAT_GAP_MM) continue;
      // Faces side by side in one plane each count only what lies on them.
      if (!containsPoint(flat, dot(c, u), dot(c, w), FLAT_GAP_MM)) continue;
      material[i] += tri.areas[t];
      break;
    }
  }
  return material;
}

// Step 2, finished: a face whose corners all lie within FLAT_GAP_MM of a larger neighbour's
// plane, and which turns from it by less than FLAT_TURN_DEG, is part of that face. A flat face
// of an exported part can come out of the hull as a large piece and a few thin strips along an
// edge, tilted a tenth of a degree where the corners of a fillet sit a thousandth of a
// millimetre above the face; comparing with the larger face's own plane, not the strip's, still
// stops a curved side from creeping into one face.
function mergeFlat(hull, faceOf, groups, faces, normals, areas) {
  const p = hull.points;
  const t = hull.triangles;
  const near = COS(FLAT_TURN_DEG);
  const owner = groups.map((_, i) => i);
  const neighbours = groups.map(() => new Set());
  for (let f = 0; f < t.length / 3; f++) {
    for (let e = 0; e < 3; e++) {
      const a = faceOf[f], b = faceOf[hull.neighbours[f * 3 + e]];
      if (a !== b) neighbours[a].add(b);
    }
  }
  const order = faces.map((_, i) => i).sort((a, b) => faces[b].area - faces[a].area);
  let merged = false;
  for (const a of order) {
    if (owner[a] !== a) continue;
    const face = faces[a];
    const d = dot(face.outline[0], face.normal);
    const queue = [...neighbours[a]];
    for (let k = 0; k < queue.length; k++) {
      const b = queue[k];
      if (owner[b] !== b || b === a || faces[b].area > face.area) continue;
      if (dot(face.normal, faces[b].normal) < near) continue;
      const corners = new Set(groups[b].flatMap((tri) => [t[tri * 3], t[tri * 3 + 1], t[tri * 3 + 2]]));
      if (![...corners].every((c) => Math.abs(dot([p[c * 3], p[c * 3 + 1], p[c * 3 + 2]], face.normal) - d) < FLAT_GAP_MM)) continue;
      owner[b] = a;
      groups[a].push(...groups[b]);
      merged = true;
      for (const n of neighbours[b]) queue.push(n);
    }
  }
  if (!merged) return { faceOf, groups, faces };
  const kept = groups.map((_, i) => i).filter((i) => owner[i] === i);
  const newGroups = kept.map((g) => groups[g]);
  const newFaceOf = new Int32Array(faceOf.length);
  newGroups.forEach((members, i) => { for (const tri of members) newFaceOf[tri] = i; });
  const described = kept.map((g) => (groups[g].length === faces[g].triangles ? faces[g] : describeFace(hull, groups[g], normals, areas)));
  return { faceOf: newFaceOf, groups: newGroups, faces: described };
}

// The faces of `hull` and the patches a part can be laid down by. `mesh` is the part (its
// `positions` and its bounding box `min`, `max`); `triangles` its triangles' normals and areas,
// when already worked out. Each face is {normal, area, outline, material, dropped}, `dropped`
// naming the step that left it out ('small', 'sliver', 'beyond_max', 'round_side') or null;
// each patch {kind: 'hull' | 'box', normal, area, outline, face | side}. Whether the part
// would stand on a patch without tipping is auto-orient's test (orient.js), which marks each
// patch; no patch is dropped for it, since the plate holds a print's first layer whichever way
// its weight falls.
export function findFaces(hull, mesh, { triangles = null } = {}) {
  const box = mesh;
  const { normals, areas } = triangleNormals(hull);
  const joined = joinTriangles(hull, normals);
  const { faceOf, faces } = mergeFlat(hull, joined.faceOf, joined.groups,
    joined.groups.map((members) => describeFace(hull, members, normals, areas)), normals, areas);
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
  // Step 4, judged against every neighbour on the hull, whatever became of it; except that a
  // face that is the part's own surface, of at least MIN_CONTACT_MM2, is not dropped on account
  // of a neighbour that mostly bridges a hollow or a step (the facets of a round side are all
  // the part's own surface; a sliver of one beside a bridge, too small for a part to rest on,
  // still goes).
  const round = COS(ROUND_SIDE_DEG);
  // A face's neighbours here are those it reaches across the hull through faces that all turn
  // from it by less than ROUND_SIDE_DEG: so a round side cut into unequal facets, or into
  // facets with slivers between them, is treated as one round side.
  const survivors = faces.filter((f) => !f.dropped);
  const shallow = new Map();
  for (const face of survivors) {
    const seen = new Set([faces.indexOf(face)]);
    const queue = [...seen];
    const near = [];
    for (let q = 0; q < queue.length; q++) {
      for (const k of faces[queue[q]].neighbours) {
        if (seen.has(k) || dot(face.normal, faces[k].normal) <= round) continue;
        seen.add(k);
        queue.push(k);
        if (faces[k].area >= face.area / 2) near.push(k);
      }
    }
    if (near.length) shallow.set(face, near);
  }
  const involved = [...new Set([...shallow.keys(), ...[...shallow.values()].flat().map((k) => faces[k])])];
  const material = materialAreas(involved, mesh.positions, triangles || meshTriangles(mesh.positions));
  involved.forEach((face, i) => { face.material = material[i]; });
  const own = (face) => face.material >= face.area / 2;
  const spares = (face, other) => own(face) && !own(other) && face.area >= MIN_CONTACT_MM2;
  const facets = [...shallow].filter(([face, near]) => near.some((k) => !spares(face, faces[k]))).map(([face]) => face);
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
