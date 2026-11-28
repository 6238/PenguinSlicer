// The worker's half of each candidate method: what it prepares from the segments. Each
// returns { data, transfer }, data holding typed arrays the page uploads as they are.
// `coarse()` reads the G-code again with coarser arcs, for the look while moving.
import { boxVertices, MAX_BOX_MM } from './prepare.js';

// The most segments the look while moving may draw (methods B and C): 0.8 million triangles,
// which software drawing on the trial's machine does in about 70 ms, leaving room for a
// machine shared with other work.
export const MOVING_BUDGET = 200000;
const DECIMATIONS = [1, 2, 4, 8, 16];

function pack(sets) {
  const data = {}, transfer = [];
  for (const [name, set] of Object.entries(sets)) {
    data[name] = set;
    if (set && set.vertices) transfer.push(set.vertices.buffer, set.layerStart.buffer);
  }
  return { data, transfer };
}

// The fewest layers to drop so that what is drawn while moving is within the budget, among
// those whose boxes, each as tall as the D layers it stands for, fit in MAX_BOX_MM; when none
// is within the budget, the most that fits.
export function decimationFor(p, budget = MOVING_BUDGET) {
  const layers = p.layerStart.length - 1;
  const fits = (d) => {
    for (let l = d - 1; l < layers; l += d) if (p.layerZ[l] - (l - d >= 0 ? p.layerZ[l - d] : 0) > MAX_BOX_MM) return false;
    return true;
  };
  let most = 1;
  for (const d of DECIMATIONS) {
    if (!fits(d)) break;
    most = d;
    let n = 0;
    for (let l = d - 1; l < layers; l += d) n += p.layerStart[l + 1] - p.layerStart[l];
    if (n <= budget) return d;
  }
  return most;
}

// Method A: every segment a box, every frame.
export function every(p) {
  return pack({ full: boxVertices(p) });
}

// Methods B and C: every segment a box at rest; while moving, every D-th layer with coarser
// arcs, as tall as the layers it stands for.
export function moving(p, options, coarse) {
  const c = coarse();
  const decimate = decimationFor(c, options.budget || MOVING_BUDGET);
  const out = pack({ full: boxVertices(p), moving: boxVertices(c, null, { decimate }) });
  out.data.decimate = decimate;
  return out;
}
