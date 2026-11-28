// Auto-orient (wizard/README.md, "Choosing how a part lies: auto-orient"): every way the part
// can rest is scored and the best taken. The candidates are its patches and the part as
// modelled. A candidate counts only if it is stable (the centre of mass, dropped straight down,
// lands inside what touches the plate) and at least MIN_CONTACT_MM2 touches. The cost, lower
// being better: the area hanging over air divided by the area touching, plus a small charge for
// height, plus a large penalty when almost nothing touches. PenguinSlicer's own small score.
import {
  AS_MODELLED_MARGIN, CONTACT_GAP_MM, HEIGHT_CHARGE_PER_MM, MIN_CONTACT_MM2, NO_CONTACT_PENALTY, OVERHANG_DEG,
} from './constants.js';
import { planeBasis } from './faces.js';
import { containsPoint, convexHull2d } from './outline.js';
import { AS_MODELLED, layFor } from './turn.js';

const OVERHANG_COS = Math.cos((OVERHANG_DEG * Math.PI) / 180);
const SAME = 1 - 1e-9;
const TIE = 1e-9;

// How the part rests with the unit direction `d` (in its own coordinates) pointing down.
export function score(part, d) {
  const p = part.mesh.positions;
  const hp = part.hull.points;
  let low = Infinity, high = -Infinity;
  for (let i = 0; i < hp.length; i += 3) {
    const z = -(hp[i] * d[0] + hp[i + 1] * d[1] + hp[i + 2] * d[2]);
    if (z < low) low = z;
    if (z > high) high = z;
  }
  const [u, w] = planeBasis(d);
  const n = part.triangleNormals;
  const a = part.triangleAreas;
  const touching = [];
  let contact = 0, overhang = 0;
  const gap = low + CONTACT_GAP_MM;
  for (let t = 0; t < a.length; t++) {
    const o = t * 9;
    let top = -Infinity;
    for (let k = 0; k < 9; k += 3) {
      const z = -(p[o + k] * d[0] + p[o + k + 1] * d[1] + p[o + k + 2] * d[2]);
      if (z > top) top = z;
    }
    if (top < gap) {
      contact += a[t];
      for (let k = 0; k < 9; k += 3) {
        const x = p[o + k], y = p[o + k + 1], z = p[o + k + 2];
        touching.push([x * u[0] + y * u[1] + z * u[2], x * w[0] + y * w[1] + z * w[2]]);
      }
    } else if (n[t * 3] * d[0] + n[t * 3 + 1] * d[1] + n[t * 3 + 2] * d[2] > OVERHANG_COS) {
      overhang += a[t];
    }
  }
  const c = part.centre;
  const footing = convexHull2d(touching);
  const stable = footing.length >= 3 && containsPoint(footing, c[0] * u[0] + c[1] * u[1] + c[2] * u[2], c[0] * w[0] + c[1] * w[1] + c[2] * w[2]);
  const height = high - low;
  // The contact is counted as at least 1 mm², so that a candidate touching along a line only
  // gets a large cost rather than an endless one.
  const cost = overhang / Math.max(contact, 1) + HEIGHT_CHARGE_PER_MM * height + (contact < MIN_CONTACT_MM2 ? NO_CONTACT_PENALTY : 0);
  return { contact, overhang, height, stable, cost };
}

// The best way for `part` (from analysePart) to lie, as {lay, normal, modelled, patch, contact,
// overhang, height, stable, cost, counted, candidates}. `patch` is the index of the patch it
// lies on, or -1 as modelled; `counted` how many candidates counted. Each patch of the part is
// given `stable`, whether the part would stand on it, and `height`, how tall it would stand.
export function autoOrient(part) {
  const candidates = part.patches.map((patch, index) => {
    const s = score(part, patch.normal);
    patch.stable = s.stable;
    patch.height = s.height;
    const modelled = patch.normal[2] <= -SAME;
    return { ...s, normal: patch.normal, patch: index, modelled, lay: modelled ? AS_MODELLED.slice() : layFor(patch.normal) };
  });
  if (!candidates.some((c) => c.modelled)) {
    candidates.push({ ...score(part, [0, 0, -1]), normal: [0, 0, -1], patch: -1, modelled: true, lay: AS_MODELLED.slice() });
  }
  const counted = candidates.filter((c) => c.stable && c.contact >= MIN_CONTACT_MM2);
  if (counted.length === 0) {
    const modelled = candidates.find((c) => c.modelled);
    return { ...modelled, counted: 0, candidates };
  }
  const least = Math.min(...counted.map((c) => c.cost));
  const best = counted.filter((c) => c.cost <= least + TIE);
  // The part as modelled is kept when it is nearly as good: a turn for a few per cent of the
  // cost (two ends of a hub cut a little differently) only surprises the user.
  const modelled = counted.find((c) => c.modelled && c.cost <= least * (1 + AS_MODELLED_MARGIN) + TIE);
  const choice = modelled || best[0];
  return { ...choice, counted: counted.length, candidates };
}
