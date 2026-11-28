// An instance's turn out of its part's own coordinates: how it lies (a unit quaternion
// [w, x, y, z], the plate configuration's `rotation`) and, after it, whole degrees about the
// vertical (`angle`). contracts/plate-configuration.md, "An instance in phase 2", fixes the
// matrix of a quaternion and the six orientations' matrices; the page and the slice service
// place an instance by the same transform, p_plate = Rz(angle) M p_part + t.

export const ORIENTATION_MATRICES = {
  '+z': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  '-z': [[1, 0, 0], [0, -1, 0], [0, 0, -1]],
  '+x': [[0, 0, -1], [0, 1, 0], [1, 0, 0]],
  '-x': [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
  '+y': [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
  '-y': [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
};

export const AS_MODELLED = Object.freeze([1, 0, 0, 0]);
const DOWN = [0, 0, -1];

export function normalise(q) {
  const len = Math.hypot(q[0], q[1], q[2], q[3]);
  return q.map((v) => v / len);
}

// a * b: the turn b, then the turn a.
export function multiply(a, b) {
  const [aw, ax, ay, az] = a;
  const [bw, bx, by, bz] = b;
  return [
    aw * bw - ax * bx - ay * by - az * bz,
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
  ];
}

export function matrixOfQuaternion(q) {
  const [w, x, y, z] = normalise(q);
  return [
    [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
    [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
    [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
  ];
}

export function rotateVector(q, v) {
  const m = matrixOfQuaternion(q);
  return m.map((row) => row[0] * v[0] + row[1] * v[1] + row[2] * v[2]);
}

// The shortest rotation turning the unit direction `a` onto the unit direction `b`. Turning a
// direction onto its opposite has no shortest rotation; the half-turn is then taken about the
// part's x axis (its y axis when `a` lies along x), which gives the contract's `-z` exactly.
export function shortestRotation(a, b) {
  const d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  if (d < -1 + 1e-12) {
    const e = Math.abs(a[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
    const along = e[0] * a[0] + e[1] * a[1] + e[2] * a[2];
    const axis = [e[0] - along * a[0], e[1] - along * a[1], e[2] - along * a[2]];
    const len = Math.hypot(...axis);
    return [0, axis[0] / len, axis[1] / len, axis[2] / len];
  }
  const c = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  return normalise([1 + d, c[0], c[1], c[2]]);
}

// The lay that puts the face whose outward normal (in the part's coordinates) is `normal`
// straight down, from the instance's current lay `lay`, keeping its turn about the vertical.
export function layOnFace(lay, normal) {
  const now = rotateVector(lay, normal);
  return normalise(multiply(shortestRotation(now, DOWN), lay));
}

// The lay that puts that face down from the part as modelled.
export const layFor = (normal) => shortestRotation(normal, DOWN);

const NEAR = 1e-9;

// The plate configuration's fields for an instance laid by `lay` and turned `angle` degrees:
// `orientation` and `angle` when the lay is one of the six axes followed by whole degrees
// about the vertical, else `rotation` (nine decimals, w not negative) and `angle`.
export function instanceTurn(lay, angle) {
  const m = matrixOfQuaternion(lay);
  for (const [orientation, o] of Object.entries(ORIENTATION_MATRICES)) {
    // R = M O^T must be a turn about the vertical alone.
    const r = [0, 1, 2].map((i) => [0, 1, 2].map((j) => m[i][0] * o[j][0] + m[i][1] * o[j][1] + m[i][2] * o[j][2]));
    if (Math.abs(r[2][2] - 1) > NEAR || Math.abs(r[0][2]) > NEAR || Math.abs(r[1][2]) > NEAR) continue;
    const k = (Math.atan2(r[1][0], r[0][0]) * 180) / Math.PI;
    if (Math.abs(k - Math.round(k)) > 1e-6) continue;
    return { orientation, angle: (((angle + Math.round(k)) % 360) + 360) % 360 };
  }
  let q = normalise(lay);
  if (q[0] < 0) q = q.map((v) => -v);
  return { rotation: q.map((v) => Math.round(v * 1e9) / 1e9), angle };
}

// The matrix M of an instance of the plate configuration, from its `orientation` or its
// `rotation` (divided by its length, as the slice service does).
export function instanceMatrix(instance) {
  if (instance.rotation) return matrixOfQuaternion(instance.rotation);
  return ORIENTATION_MATRICES[instance.orientation];
}
