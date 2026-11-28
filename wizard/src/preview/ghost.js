// The ghost of what is still to print (wizard/README-details.md, "The layer preview"): each
// instance's part placed on the plate by the plate configuration's one transform,
// p_plate = Rz(angle) M p_part + t (contracts/plate-configuration.md, "Coordinates" and "An
// instance in phase 2"), the same the slice service gives Orca. The parts' corners are those the
// geometry client keeps for drawing, already in millimetres. Run in the preview's worker.
import { ORIENTATION_MATRICES, matrixOfQuaternion } from '../geometry/turn.js';
import { PREVIEW_FAILED, PreviewError } from './preview-errors.js';

function matrixOf(instance, i) {
  if (Array.isArray(instance.rotation) && instance.rotation.length === 4 && instance.rotation.every(Number.isFinite)) {
    return matrixOfQuaternion(instance.rotation);
  }
  if (Object.hasOwn(ORIENTATION_MATRICES, instance.orientation)) return ORIENTATION_MATRICES[instance.orientation];
  throw new PreviewError(`instance ${i} has no orientation or rotation the contract knows`, PREVIEW_FAILED);
}

// One instance's corners on the plate, from its part's corners.
function place(corners, instance, i) {
  const m = matrixOf(instance, i);
  const n = corners.length / 3, out = new Float32Array(corners.length);
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity;
  for (let k = 0; k < n; k++) {
    const x = corners[k * 3], y = corners[k * 3 + 1], z = corners[k * 3 + 2];
    const tx = m[0][0] * x + m[0][1] * y + m[0][2] * z;
    const ty = m[1][0] * x + m[1][1] * y + m[1][2] * z;
    const tz = m[2][0] * x + m[2][1] * y + m[2][2] * z;
    out[k * 3] = tx; out[k * 3 + 1] = ty; out[k * 3 + 2] = tz;
    if (tx < minX) minX = tx; if (tx > maxX) maxX = tx;
    if (ty < minY) minY = ty; if (ty > maxY) maxY = ty;
    if (tz < minZ) minZ = tz;
  }
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  const a = ((instance.angle || 0) * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  for (let k = 0; k < n; k++) {
    const x = out[k * 3] - cx, y = out[k * 3 + 1] - cy;
    out[k * 3] = c * x - s * y + instance.x;
    out[k * 3 + 1] = s * x + c * y + instance.y;
    out[k * 3 + 2] -= minZ;
  }
  return out;
}

// Every instance of `plate` ({instances, meshes}: the plate configuration's instances, and each
// part's corners under the key its instances name) placed, as one array of triangle corners,
// and each instance's bounds (minX, minY, minZ, maxX, maxY, maxZ), for framing the view. No
// plate is no ghost.
export function placeInstances(plate) {
  if (!plate) return { corners: new Float32Array(0), bounds: new Float32Array(0) };
  const placed = plate.instances.map((instance, i) => {
    const corners = plate.meshes[instance.ref];
    if (!(corners instanceof Float32Array)) {
      throw new PreviewError(`instance ${i} names the part ${JSON.stringify(instance.ref)}, whose corners the preview was not given`, PREVIEW_FAILED);
    }
    return place(corners, instance, i);
  });
  const corners = new Float32Array(placed.reduce((n, p) => n + p.length, 0));
  const bounds = new Float32Array(placed.length * 6);
  let at = 0;
  placed.forEach((p, k) => {
    corners.set(p, at); at += p.length;
    const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
    for (let i = 0; i < p.length; i += 3) {
      for (let a = 0; a < 3; a++) {
        if (p[i + a] < b[a]) b[a] = p[i + a];
        if (p[i + a] > b[a + 3]) b[a + 3] = p[i + a];
      }
    }
    bounds.set(b, k * 6);
  });
  return { corners, bounds };
}
