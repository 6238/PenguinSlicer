// The placement check: the slice service's three rules (contracts/plate-configuration.md,
// "Checks", step 5), with the footprint and its centre exactly as "Coordinates" defines them, so
// that a plate the wizard shows green is one the slice service accepts. The two checks are kept
// in agreement by the shared plates of contracts/examples/placement/.
import { EPS_MM, MARGIN_MM, SPACING_MM, SPACING_SUPPORTS_MM } from './constants.js';
import { bounds, convexHull2d, cosSin, distance, simplified, turnedOutline } from './outline.js';
import { instanceMatrix } from './turn.js';

export const CODES = {
  off_plate: 'slice.placement_off_plate',
  too_tall: 'slice.placement_too_tall',
  too_close: 'slice.placement_too_close',
};

// Supports are on when the plate's changes set enable_support to "1", or, with no change, when
// the process profile's value (`profileValue`) is "1".
export function supportsOn(plateConfiguration, profileValue) {
  const overrides = plateConfiguration.overrides || {};
  const value = 'enable_support' in overrides ? overrides.enable_support : profileValue;
  return value === '1';
}

// The plate the rules are judged on: the printable area's corners `min` and `max` and its
// `height`, from the printer's profile, with the margin and the spacing the supports ask for.
export function plateOf({ min, max, height }, supports) {
  return { min, max, height, margin: MARGIN_MM, spacing: supports ? SPACING_SUPPORTS_MM : SPACING_MM, supports };
}

// `<name> #<n>`, the part's name reduced as the slice service reduces it: each character (each
// code point, so an emoji is one, not its two UTF-16 halves) outside A-Z, a-z, 0-9, _ and -
// becomes _, then the first 40 are kept.
export function instanceLabels(plateConfiguration) {
  const counts = new Map();
  return plateConfiguration.instances.map((instance) => {
    const clean = plateConfiguration.parts[instance.ref].name.replace(/[^A-Za-z0-9_-]/gu, '_').slice(0, 40) || 'part';
    const n = (counts.get(clean) || 0) + 1;
    counts.set(clean, n);
    return `${clean} #${n}`;
  });
}

// The footprint of the part whose hull corners are `points`, turned by the matrix `m`: the
// convex hull of the turned corners seen from above, about the centre of their bounding box in x
// and y; `minZ` its lowest point and `height` its height.
export function footprint(points, m) {
  const n = points.length / 3;
  const flat = new Array(n);
  let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
  for (let i = 0; i < n; i++) {
    const px = points[i * 3], py = points[i * 3 + 1], pz = points[i * 3 + 2];
    const x = m[0][0] * px + m[0][1] * py + m[0][2] * pz;
    const y = m[1][0] * px + m[1][1] * py + m[1][2] * pz;
    const z = m[2][0] * px + m[2][1] * py + m[2][2] * pz;
    flat[i] = [x, y];
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
    if (z < z0) z0 = z; if (z > z1) z1 = z;
  }
  const centre = [(x0 + x1) / 2, (y0 + y1) / 2];
  const hull = convexHull2d(flat).map(([x, y]) => [x - centre[0], y - centre[1]]);
  return { hull, centre, minZ: z0, height: z1 - z0 };
}

// An instance's footprint as it lies and as it is turned, about its centre: `hull`, `coarse`
// (at most 32 corners, holding `hull`), `height` and `bounds`. Footprints are worked out once
// for each part and turn. The cache is keyed by the part's hull corners themselves, never by
// the plate configuration's part key, which means nothing beyond one plate configuration: a
// part key that comes to point at another part (read again in other units, or a key used
// again) finds no footprint of the part it pointed at before, and a part forgotten takes its
// footprints with it.
export function turnedFootprint(instance, pointsByPart, cache = new WeakMap()) {
  const points = pointsByPart[instance.ref];
  let byTurn = cache.get(points);
  if (!byTurn) {
    byTurn = new Map();
    cache.set(points, byTurn);
  }
  const turn = instance.rotation ? `r${instance.rotation.join(',')}` : `o${instance.orientation}`;
  const key = `${turn}|${instance.angle}`;
  let fp = byTurn.get(key);
  if (!fp) {
    const base = footprint(points, instanceMatrix(instance));
    const hull = turnedOutline(base.hull, instance.angle);
    fp = { hull, coarse: simplified(hull), height: base.height, bounds: bounds(hull) };
    byTurn.set(key, fp);
  }
  return fp;
}

// Each instance's outline on the plate, turned by its angle and moved to its place, with its
// height.
export function placedOutlines(plateConfiguration, pointsByPart, cache = new WeakMap()) {
  return plateConfiguration.instances.map((instance) => {
    const fp = turnedFootprint(instance, pointsByPart, cache);
    const move = ([x, y]) => [x + instance.x, y + instance.y];
    const [bx0, by0, bx1, by1] = fp.bounds;
    return {
      hull: fp.hull.map(move), coarse: fp.coarse.map(move), height: fp.height,
      bounds: [bx0 + instance.x, by0 + instance.y, bx1 + instance.x, by1 + instance.y],
    };
  });
}

// The plate's problems, in the slice service's order: every instance across the margin, then
// every instance too tall, then every pair too close (i < j). Each is {rule, instances} with
// what the Layout step's messages need: `edges` crossed and the footprint's `size` (x, y) for
// off_plate, `height` for too_tall, `distance` for too_close. An empty list passes.
export function checkPlate(plateConfiguration, pointsByPart, plate, cache) {
  const placed = placedOutlines(plateConfiguration, pointsByPart, cache);
  const lo = [plate.min[0] + plate.margin - EPS_MM, plate.min[1] + plate.margin - EPS_MM];
  const hi = [plate.max[0] - plate.margin + EPS_MM, plate.max[1] - plate.margin + EPS_MM];
  const problems = [];
  placed.forEach((p, i) => {
    const [x0, y0, x1, y1] = p.bounds;
    const edges = [];
    if (x0 < lo[0]) edges.push('left');
    if (x1 > hi[0]) edges.push('right');
    if (y0 < lo[1]) edges.push('front');
    if (y1 > hi[1]) edges.push('back');
    if (edges.length) problems.push({ rule: 'off_plate', instances: [i], edges, size: [x1 - x0, y1 - y0] });
  });
  placed.forEach((p, i) => {
    if (p.height > plate.height + EPS_MM) problems.push({ rule: 'too_tall', instances: [i], height: p.height });
  });
  const need = plate.spacing - EPS_MM;
  // Sorted by their left edge, so that each instance is compared only with those that start
  // within the spacing of its right edge.
  const order = placed.map((_, i) => i).sort((a, b) => placed[a].bounds[0] - placed[b].bounds[0]);
  const pairs = [];
  for (let k = 0; k < order.length; k++) {
    const i = order[k];
    const a = placed[i];
    for (let l = k + 1; l < order.length; l++) {
      const j = order[l];
      const b = placed[j];
      if (b.bounds[0] - a.bounds[2] >= need) break;
      if (b.bounds[1] - a.bounds[3] >= need || a.bounds[1] - b.bounds[3] >= need) continue;
      // The coarse outlines hold the true ones, so far enough apart coarse is far enough.
      if (distance(a.coarse, b.coarse) >= need) continue;
      const d = distance(a.hull, b.hull);
      if (d < need) pairs.push({ rule: 'too_close', instances: i < j ? [i, j] : [j, i], distance: d });
    }
  }
  pairs.sort((p, q) => p.instances[0] - q.instances[0] || p.instances[1] - q.instances[1]);
  return problems.concat(pairs);
}

// The shared plates' form of the answer: {accepted: true}, or the first problem's code with the
// instances its report's `where` names.
export function expectedAnswer(problems, labels) {
  if (problems.length === 0) return { accepted: true };
  const [first] = problems;
  const answer = { code: CODES[first.rule], instance: labels[first.instances[0]] };
  if (first.rule === 'too_close') answer.other_instance = labels[first.instances[1]];
  return answer;
}

export { cosSin };
