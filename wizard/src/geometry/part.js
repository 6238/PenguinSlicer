// What the worker works out once for each part: its hull, the faces and patches it can be laid
// down by, and what auto-orient scores with (each triangle's normal and area, the part's volume
// and centre of mass). Everything is in the part's own coordinates, in millimetres.
import { convexHull } from './hull.js';
import { findFaces } from './faces.js';

function massAndTriangles(positions) {
  const count = positions.length / 9;
  const normals = new Float64Array(count * 3);
  const areas = new Float64Array(count);
  let volume = 0, cx = 0, cy = 0, cz = 0;
  for (let t = 0; t < count; t++) {
    const o = t * 9;
    const ax = positions[o], ay = positions[o + 1], az = positions[o + 2];
    const bx = positions[o + 3], by = positions[o + 4], bz = positions[o + 5];
    const qx = positions[o + 6], qy = positions[o + 7], qz = positions[o + 8];
    const ux = bx - ax, uy = by - ay, uz = bz - az, vx = qx - ax, vy = qy - ay, vz = qz - az;
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz);
    areas[t] = len / 2;
    if (len > 0) { normals[t * 3] = nx / len; normals[t * 3 + 1] = ny / len; normals[t * 3 + 2] = nz / len; }
    // The signed volume of the tetrahedron from the origin, and its centre.
    const v = (ax * (by * qz - bz * qy) - ay * (bx * qz - bz * qx) + az * (bx * qy - by * qx)) / 6;
    volume += v;
    cx += (v * (ax + bx + qx)) / 4; cy += (v * (ay + by + qy)) / 4; cz += (v * (az + bz + qz)) / 4;
  }
  const centre = volume !== 0 ? [cx / volume, cy / volume, cz / volume] : null;
  return { normals, areas, volume: Math.abs(volume), centre };
}

export function analysePart(mesh) {
  const hull = convexHull(mesh.positions);
  const tri = massAndTriangles(mesh.positions);
  let centre = tri.centre;
  if (!centre) {
    // A surface enclosing nothing: the middle of its box stands in for the centre of mass.
    centre = [0, 1, 2].map((k) => (mesh.min[k] + mesh.max[k]) / 2);
  }
  const found = findFaces(hull, mesh, { triangles: tri });
  return {
    mesh, hull, faces: found.faces, patches: found.patches, hullTriangles: found.hullTriangles,
    triangleNormals: tri.normals, triangleAreas: tri.areas, volume: tri.volume, centre,
  };
}
