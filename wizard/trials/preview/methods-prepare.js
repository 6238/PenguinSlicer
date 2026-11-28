// The worker's half of each candidate method: what it prepares from the segments. Each
// returns { data, transfer }, data holding typed arrays the page uploads as they are.
// `coarse()` reads the G-code again with coarser arcs, for the look while moving.
import { boxVertices } from './prepare.js';

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

// The fewest layers to drop so that what is drawn while moving is within the budget.
export function decimationFor(p, budget = MOVING_BUDGET) {
  const layers = p.layerStart.length - 1;
  for (const d of DECIMATIONS) {
    let n = 0;
    for (let l = d - 1; l < layers; l += d) n += p.layerStart[l + 1] - p.layerStart[l];
    if (n <= budget) return d;
  }
  return DECIMATIONS[DECIMATIONS.length - 1];
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
