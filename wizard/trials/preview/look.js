// The coarse checks of the look, on the pixels a method put on the screen at rest (viewer.js
// reads them on the frame that finished the full look, ghost included). Pure functions, run in
// the page and in the tests.
import { GROUP_COLOURS } from './gcode.js';

const rgb = (hex) => [(hex >> 16 & 255) / 255, (hex >> 8 & 255) / 255, (hex & 255) / 255];
export const BACKGROUND = rgb(0xf2f4f7);          // the view's background, as the mockup's
export const COLOURS = GROUP_COLOURS.map(rgb);
// The walls' sides are darkened by the way they face the light, by 0.66 at most (methods.js).
const WALL_SHADES = [0.66, 0.75, 0.83, 0.92, 1];
const NEAR = 24;                                  // a pixel this close to a colour, summed over r, g, b, is it

// The share of the view (RGBA pixels) that is not background, and the share in each group's
// colour, the walls at any of their shades.
export function sortPixels(px) {
  const ramps = COLOURS.map((c, g) => (g === 0 ? WALL_SHADES : [1]).map((s) => c.map((v) => v * s * 255)));
  const bg = BACKGROUND.map((v) => v * 255);
  const counts = [0, 0, 0, 0];
  let background = 0;
  for (let i = 0; i < px.length; i += 4) {
    const r = px[i], g = px[i + 1], b = px[i + 2];
    if (Math.abs(r - bg[0]) < 3 && Math.abs(g - bg[1]) < 3 && Math.abs(b - bg[2]) < 3) { background++; continue; }
    ramps.forEach((ramp, k) => {
      if (ramp.some((c) => Math.abs(c[0] - r) + Math.abs(c[1] - g) + Math.abs(c[2] - b) < NEAR)) counts[k]++;
    });
  }
  const all = px.length / 4;
  return { covered: 1 - background / all, groups: counts.map((c) => c / all) };
}

// The share of the view whose colour differs between two looks of the same size.
export function changedShare(a, b) {
  let changed = 0;
  for (let i = 0; i < a.length; i += 4) if (a[i] !== b[i] || a[i + 1] !== b[i + 1] || a[i + 2] !== b[i + 2]) changed++;
  return changed / (a.length / 4);
}
