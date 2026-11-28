// Arrange (wizard/README.md, "Arranging the plate"): every instance's convex outline seen from
// above, as it lies and as it is turned, grown by the spacing, placed on the plate; never turned.
// Two packers run and the better result is kept: fewer instances left beside the plate wins,
// the smaller pile breaking a tie.
//   - The shelf packer takes the instances largest first and puts each at the first free spot
//     scanning from the plate's front-left corner, then slides the group to the plate's middle.
//   - The pile packer takes them largest first and tries every free spot on a PILE_GRID_MM grid,
//     scored by how small and square the pile stays and how near the plate's middle it is,
//     refines the best at PILE_REFINE_MM, and centres the pile.
// Whether a spot is free is read from a map of the plate in squares ARRANGE_CELL_MM across, each
// marked when an outline grown by half the spacing (and a little slack) touches it. Two outlines
// whose grown shapes share no square are at least the spacing apart, so a plate Arrange makes
// always passes the placement check; it may leave up to about a millimetre more than the spacing.
import { ARRANGE_CELL_MM, ARRANGE_SLACK_MM, PILE_GRID_MM, PILE_REFINE_MM } from './constants.js';
import { area as outlineArea, bounds, grown } from './outline.js';
import { turnedFootprint } from './placement.js';

const BESIDE_GAP_MM = 20;

// The rows of the map's squares that the convex `outline` (in squares, about its centre at a
// spot on a corner of the squares) touches: [row, first column, last column], relative to the spot.
function spans(outline) {
  const [, y0, , y1] = bounds(outline);
  const out = [];
  const n = outline.length;
  for (let row = Math.floor(y0); row < Math.ceil(y1); row++) {
    const lo = Math.max(row, y0), hi = Math.min(row + 1, y1);
    let x0 = Infinity, x1 = -Infinity;
    for (let i = 0; i < n; i++) {
      const a = outline[i], b = outline[(i + 1) % n];
      if (a[1] >= lo && a[1] <= hi) { x0 = Math.min(x0, a[0]); x1 = Math.max(x1, a[0]); }
      for (const y of [lo, hi]) {
        if ((a[1] - y) * (b[1] - y) <= 0 && a[1] !== b[1]) {
          const x = a[0] + ((y - a[1]) / (b[1] - a[1])) * (b[0] - a[0]);
          x0 = Math.min(x0, x); x1 = Math.max(x1, x);
        }
      }
    }
    if (x0 <= x1) out.push([row, Math.floor(x0), Math.floor(x1)]);
  }
  return out;
}

// The plate's map: which squares are taken, with each row's running count for quick tests.
class PlateMap {
  constructor(width, depth) {
    this.w = width;
    this.h = depth;
    this.taken = new Uint8Array(width * depth);
    this.sums = new Int32Array((width + 1) * depth);
  }

  free(mask, i, j) {
    const { w, h, sums } = this;
    for (const [row, c0, c1] of mask) {
      const r = row + j;
      if (r < 0 || r >= h) continue;
      const a = Math.max(0, c0 + i), b = Math.min(w - 1, c1 + i);
      if (a > b) continue;
      if (sums[r * (w + 1) + b + 1] - sums[r * (w + 1) + a] > 0) return false;
    }
    return true;
  }

  take(mask, i, j) {
    const { w, h, taken, sums } = this;
    for (const [row, c0, c1] of mask) {
      const r = row + j;
      if (r < 0 || r >= h) continue;
      const a = Math.max(0, c0 + i), b = Math.min(w - 1, c1 + i);
      for (let c = a; c <= b; c++) taken[r * w + c] = 1;
      let s = 0;
      for (let c = 0; c < w; c++) { sums[r * (w + 1) + c] = s; s += taken[r * w + c]; }
      sums[r * (w + 1) + w] = s;
    }
  }
}

// Below, every length is in squares of the map, ARRANGE_CELL_MM across.
const K = 1 / ARRANGE_CELL_MM;
const GRID = Math.round(PILE_GRID_MM * K);
const REFINE = Math.round(PILE_REFINE_MM * K);

function prepare(plateConfiguration, pointsByPart, plate) {
  const cache = new WeakMap();
  const r = (plate.spacing + ARRANGE_SLACK_MM) / 2;
  const masks = new Map();
  const items = plateConfiguration.instances.map((instance, index) => {
    const fp = turnedFootprint(instance, pointsByPart, cache);
    let mask = masks.get(fp);
    if (!mask) { mask = spans(grown(fp.coarse, r).map(([x, y]) => [x * K, y * K])); masks.set(fp, mask); }
    return { index, fp, mask, bounds: fp.bounds.map((v) => v * K), area: outlineArea(fp.hull) };
  });
  // Largest first, the plate's order breaking a tie.
  return items.sort((a, b) => b.area - a.area || a.index - b.index);
}

// The area the outlines' bounds may use: the printable area less the margin, `w` by `h`
// squares. A spot (i, j) puts an outline's centre at (x0 + i, y0 + j) squares.
function frame(plate) {
  const x0 = plate.min[0] + plate.margin, y0 = plate.min[1] + plate.margin;
  const x1 = plate.max[0] - plate.margin, y1 = plate.max[1] - plate.margin;
  const width = (x1 - x0) * K, depth = (y1 - y0) * K;
  return { x0, y0, width, depth, w: Math.ceil(width), h: Math.ceil(depth) };
}

// The spots at which the item's outline stays inside the frame.
function range(item, f) {
  const [bx0, by0, bx1, by1] = item.bounds;
  return { i0: Math.ceil(-bx0), i1: Math.floor(f.width - bx1), j0: Math.ceil(-by0), j1: Math.floor(f.depth - by1) };
}

function boxOf(item, i, j) {
  const [bx0, by0, bx1, by1] = item.bounds;
  return [bx0 + i, by0 + j, bx1 + i, by1 + j];
}

const union = (a, b) => (a ? [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])] : b);

function shelf(items, f) {
  const map = new PlateMap(f.w, f.h);
  const spots = new Map();
  let pile = null;
  for (const item of items) {
    const { i0, i1, j0, j1 } = range(item, f);
    let found = null;
    for (let j = j0; j <= j1 && !found; j += GRID) {
      for (let i = i0; i <= i1; i += GRID) {
        if (map.free(item.mask, i, j)) { found = [i, j]; break; }
      }
    }
    if (!found) continue;
    // Slide it towards the front-left corner a square at a time while the spot stays free.
    let [i, j] = found;
    for (let moved = true; moved;) {
      moved = false;
      while (j - 1 >= j0 && map.free(item.mask, i, j - 1)) { j -= 1; moved = true; }
      while (i - 1 >= i0 && map.free(item.mask, i - 1, j)) { i -= 1; moved = true; }
    }
    map.take(item.mask, i, j);
    spots.set(item.index, [i, j]);
    pile = union(pile, boxOf(item, i, j));
  }
  return { spots, pile };
}

function pileScore(box, f) {
  const w = box[2] - box[0], h = box[3] - box[1];
  const dx = (box[0] + box[2]) / 2 - f.width / 2, dy = (box[1] + box[3]) / 2 - f.depth / 2;
  return w * h + 0.5 * (w - h) * (w - h) + 0.25 * (dx * dx + dy * dy);
}

function pileOf(items, f) {
  const map = new PlateMap(f.w, f.h);
  const spots = new Map();
  let pile = null;
  const midI = Math.round(f.width / 2), midJ = Math.round(f.depth / 2);
  for (const item of items) {
    const { i0, i1, j0, j1 } = range(item, f);
    if (i0 > i1 || j0 > j1) continue;
    let best = null;
    const consider = (i, j) => {
      if (i < i0 || i > i1 || j < j0 || j > j1 || !map.free(item.mask, i, j)) return;
      const s = pileScore(union(pile, boxOf(item, i, j)), f);
      if (!best || s < best[2]) best = [i, j, s];
    };
    if (!pile) {
      consider(Math.min(i1, Math.max(i0, midI)), Math.min(j1, Math.max(j0, midJ)));
    } else {
      // Every grid spot near the pile first; the whole plate only when none of those is free.
      const [bx0, by0, bx1, by1] = item.bounds;
      const window = [pile[0] - bx1 - GRID, pile[1] - by1 - GRID, pile[2] - bx0 + GRID, pile[3] - by0 + GRID];
      const scan = (a0, a1, b0, b1) => {
        const s0 = Math.ceil(a0 / GRID) * GRID;
        const t0 = Math.ceil(b0 / GRID) * GRID;
        for (let j = t0; j <= b1; j += GRID) for (let i = s0; i <= a1; i += GRID) consider(i, j);
      };
      scan(Math.max(i0, window[0]), Math.min(i1, window[2]), Math.max(j0, window[1]), Math.min(j1, window[3]));
      if (!best) scan(i0, i1, j0, j1);
    }
    if (!best) continue;
    const [bi, bj] = best;
    for (let dj = -(GRID - REFINE); dj <= GRID - REFINE; dj += REFINE) {
      for (let di = -(GRID - REFINE); di <= GRID - REFINE; di += REFINE) consider(bi + di, bj + dj);
    }
    const [i, j] = best;
    map.take(item.mask, i, j);
    spots.set(item.index, [i, j]);
    pile = union(pile, boxOf(item, i, j));
  }
  return { spots, pile };
}

const pileArea = (pile) => (pile ? ((pile[2] - pile[0]) * (pile[3] - pile[1])) / (K * K) : 0);
const round3 = (v) => Math.round(v * 1000) / 1000;

// The plate configuration with every instance's `x` and `y` set by Arrange, nothing else of it
// changed. `placed[i]` says whether instance i is on the plate; one that is not waits beside
// the plate, to its right. `packer` names the packer whose result was kept, `tried` both.
export function arrangePlate(plateConfiguration, pointsByPart, plate) {
  const items = prepare(plateConfiguration, pointsByPart, plate);
  const f = frame(plate);
  const results = [['shelf', shelf(items, f)], ['pile', pileOf(items, f)]].map(([packer, r]) => ({
    packer, ...r, placed: r.spots.size, area: pileArea(r.pile),
  }));
  const [kept] = results.slice().sort((a, b) => b.placed - a.placed || a.area - b.area);
  // The pile, centred on the plate's middle.
  let dx = 0, dy = 0;
  if (kept.pile) {
    dx = (f.width - kept.pile[0] - kept.pile[2]) / (2 * K);
    dy = (f.depth - kept.pile[1] - kept.pile[3]) / (2 * K);
  }
  const instances = plateConfiguration.instances.map((instance) => ({ ...instance }));
  const placed = instances.map(() => false);
  let besideY = plate.min[1];
  for (const item of items.slice().sort((a, b) => a.index - b.index)) {
    const spot = kept.spots.get(item.index);
    const instance = instances[item.index];
    if (spot) {
      instance.x = round3(f.x0 + spot[0] / K + dx);
      instance.y = round3(f.y0 + spot[1] / K + dy);
      placed[item.index] = true;
    } else {
      const [bx0, by0, , by1] = item.fp.bounds;
      instance.x = round3(plate.max[0] + BESIDE_GAP_MM - bx0);
      instance.y = round3(besideY - by0);
      besideY += by1 - by0 + plate.spacing;
    }
  }
  return {
    plateConfiguration: { ...plateConfiguration, instances }, placed, packer: kept.packer,
    tried: results.map(({ packer, placed: count, area }) => ({ packer, placed: count, area })),
  };
}
