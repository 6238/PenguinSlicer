// Shared by the geometry's tests: the real parts and the made parts, read as the worker reads
// them, and a check that a hull really is the convex hull of its points.
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { readBinaryStl } from '../../src/geometry/stl.js';

const HERE = dirname(fileURLToPath(import.meta.url));
export const WIZARD = join(HERE, '..', '..');
export const REAL_PARTS = join(WIZARD, '..', 'contracts', 'examples', 'parts', 'real');
export const CONTRACT_PARTS = join(WIZARD, '..', 'contracts', 'examples', 'parts');
export const MADE_PARTS = join(WIZARD, 'trials', 'parts');
export const PLACEMENT_PLATES = join(WIZARD, '..', 'contracts', 'examples', 'placement');

function bufferOf(path) {
  const bytes = readFileSync(path);
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

export const readRealPart = (file) => readBinaryStl(bufferOf(join(REAL_PARTS, file)), 'mm');
export const readMadePart = (file) => readBinaryStl(bufferOf(join(MADE_PARTS, file)), 'mm');
export const readContractPart = (file) => readBinaryStl(bufferOf(join(CONTRACT_PARTS, file)), 'mm');
export const fileBuffer = bufferOf;

// Every way `hull` could fail to be the convex hull of `points`: a point outside a face, a
// face whose neighbour does not share its edge, a face with no area. Empty when it is valid.
export function hullIsValid(hull, points, tolerance = 1e-4) {
  const problems = [];
  const p = hull.points;
  const t = hull.triangles;
  for (let f = 0; f < t.length / 3; f++) {
    const a = t[f * 3] * 3;
    const b = t[f * 3 + 1] * 3;
    const c = t[f * 3 + 2] * 3;
    const ux = p[b] - p[a], uy = p[b + 1] - p[a + 1], uz = p[b + 2] - p[a + 2];
    const vx = p[c] - p[a], vy = p[c + 1] - p[a + 1], vz = p[c + 2] - p[a + 2];
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz);
    if (!(len > 0)) { problems.push(`face ${f} has no area`); continue; }
    nx /= len; ny /= len; nz /= len;
    const d = nx * p[a] + ny * p[a + 1] + nz * p[a + 2];
    for (let i = 0; i < points.length; i += 3) {
      const out = nx * points[i] + ny * points[i + 1] + nz * points[i + 2] - d;
      if (out > tolerance) { problems.push(`point ${i / 3} is ${out} mm outside face ${f}`); break; }
    }
    if (problems.length > 5) break;
    for (let e = 0; e < 3; e++) {
      const g = hull.neighbours[f * 3 + e];
      const ea = t[f * 3 + e];
      const eb = t[f * 3 + ((e + 1) % 3)];
      const shares = [0, 1, 2].some((k) => t[g * 3 + k] === eb && t[g * 3 + ((k + 1) % 3)] === ea);
      if (!shares) problems.push(`face ${f} edge ${e}: neighbour ${g} does not share it`);
    }
  }
  return problems;
}
