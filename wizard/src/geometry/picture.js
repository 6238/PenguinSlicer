// A part's picture: the small picture on its row of the Parts step, drawn in the worker so that a
// part of 150,000 triangles never holds the main thread (wizard/README.md, "Keeping the page
// answering"), and without a WebGL context of its own, of which a browser gives a page only a few.
// It is drawn from the part as read (in millimetres, as modelled), flat shaded in the part's
// colour, seen from the front, the right and above, as the mockup draws its pictures
// (docs/mockups/print-wizard/js/wizard.js, "thumbnails"): a camera of 30 degrees looking at the
// part's middle from the direction (0.55, -0.7, 0.45), far enough for the part's bounding sphere
// to fit with a twentieth to spare, lit by a sky above and a ground below and by two lights, the
// mockup's. Each pixel is the average of SUPERSAMPLE by SUPERSAMPLE samples, so edges are smooth;
// the ground is transparent, so the row's own background shows through.

export const MIN_PICTURE_PX = 16;
export const MAX_PICTURE_PX = 512;
const SUPERSAMPLE = 2;
const HALF_FOV = (15 * Math.PI) / 180;
const FIT = 1.05;
const VIEW = normalise([0.55, -0.7, 0.45]);
const SKY = [1, 1, 1];
const GROUND = [0x3a / 255, 0x44 / 255, 0x50 / 255];
const HEMISPHERE = 0.85;
const LIGHTS = [[normalise([-200, -300, 500]), 0.7], [normalise([400, 500, 200]), 0.3]];
// The light's sum reaches about 1.5 on a face turned to both the sky and the first light; this
// brings that face near the part's own colour rather than white, as the mockup's pictures show it.
const EXPOSURE = 0.72;

function normalise(v) {
  const l = Math.hypot(v[0], v[1], v[2]);
  return [v[0] / l, v[1] / l, v[2] / l];
}

// drawPicture(mesh, {px, colour}) gives {width, height, pixels}: px by px pixels, RGBA, not
// premultiplied, as an ImageData takes them. `mesh` is the part as stl.js reads it (`positions`,
// `min`, `max`, in millimetres); `colour` is 0xrrggbb.
export function drawPicture(mesh, { px, colour }) {
  const size = px * SUPERSAMPLE;
  const out = new Uint8ClampedArray(px * px * 4);
  const centre = [0, 1, 2].map((k) => (mesh.min[k] + mesh.max[k]) / 2);
  const radius = Math.hypot(mesh.max[0] - mesh.min[0], mesh.max[1] - mesh.min[1], mesh.max[2] - mesh.min[2]) / 2;
  if (!(radius > 0)) return { width: px, height: px, pixels: out };

  // The camera: forward f, right r and up u, from the eye.
  const distance = (radius / Math.sin(HALF_FOV)) * FIT;
  const eye = [0, 1, 2].map((k) => centre[k] + VIEW[k] * distance);
  const f = [-VIEW[0], -VIEW[1], -VIEW[2]];
  const r = normalise([f[1], -f[0], 0]);                     // f × (0, 0, 1)
  const u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]];
  const scale = size / 2 / Math.tan(HALF_FOV);

  const base = [(colour >> 16) & 0xff, (colour >> 8) & 0xff, colour & 0xff];
  const depth = new Float32Array(size * size);               // 1 / distance; 0 is nothing drawn
  const shade = new Uint8Array(size * size * 3);

  const p = mesh.positions;
  const sx = [0, 0, 0], sy = [0, 0, 0], iz = [0, 0, 0];
  for (let t = 0, count = p.length / 9; t < count; t++) {
    const o = t * 9;
    for (let c = 0; c < 3; c++) {
      const vx = p[o + c * 3] - eye[0], vy = p[o + c * 3 + 1] - eye[1], vz = p[o + c * 3 + 2] - eye[2];
      const z = vx * f[0] + vy * f[1] + vz * f[2];
      iz[c] = 1 / z;
      sx[c] = size / 2 + (vx * r[0] + vy * r[1] + vz * r[2]) * iz[c] * scale;
      sy[c] = size / 2 - (vx * u[0] + vy * u[1] + vz * u[2]) * iz[c] * scale;
    }
    const area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0]);
    if (area === 0) continue;

    // The face's shade: its normal turned to the eye (so a part wound inside out still draws).
    const ax = p[o + 3] - p[o], ay = p[o + 4] - p[o + 1], az = p[o + 5] - p[o + 2];
    const bx = p[o + 6] - p[o], by = p[o + 7] - p[o + 1], bz = p[o + 8] - p[o + 2];
    let n = normalise([ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx]);
    if (!Number.isFinite(n[0])) continue;
    if (n[0] * (eye[0] - p[o]) + n[1] * (eye[1] - p[o + 1]) + n[2] * (eye[2] - p[o + 2]) < 0) n = [-n[0], -n[1], -n[2]];
    const w = 0.5 * n[2] + 0.5;
    const rgb = [0, 0, 0];
    for (let k = 0; k < 3; k++) {
      let light = HEMISPHERE * (GROUND[k] * (1 - w) + SKY[k] * w);
      for (const [d, strength] of LIGHTS) light += strength * Math.max(0, n[0] * d[0] + n[1] * d[1] + n[2] * d[2]);
      rgb[k] = Math.min(255, Math.round(base[k] * light * EXPOSURE));
    }

    // Fill the samples whose centres the triangle covers, nearest first.
    const x0 = Math.max(0, Math.floor(Math.min(sx[0], sx[1], sx[2]))), x1 = Math.min(size - 1, Math.ceil(Math.max(sx[0], sx[1], sx[2])));
    const y0 = Math.max(0, Math.floor(Math.min(sy[0], sy[1], sy[2]))), y1 = Math.min(size - 1, Math.ceil(Math.max(sy[0], sy[1], sy[2])));
    const inv = 1 / area;
    for (let y = y0; y <= y1; y++) {
      const cy = y + 0.5;
      for (let x = x0; x <= x1; x++) {
        const cx = x + 0.5;
        const w0 = ((sx[1] - cx) * (sy[2] - cy) - (sx[2] - cx) * (sy[1] - cy)) * inv;
        const w1 = ((sx[2] - cx) * (sy[0] - cy) - (sx[0] - cx) * (sy[2] - cy)) * inv;
        const w2 = 1 - w0 - w1;
        if (w0 < 0 || w1 < 0 || w2 < 0) continue;
        const z = w0 * iz[0] + w1 * iz[1] + w2 * iz[2];
        const at = y * size + x;
        if (z <= depth[at]) continue;
        depth[at] = z;
        shade[at * 3] = rgb[0]; shade[at * 3 + 1] = rgb[1]; shade[at * 3 + 2] = rgb[2];
      }
    }
  }

  // Each pixel the average of its samples: its cover the share of samples drawn, its colour the
  // average of those drawn.
  for (let y = 0; y < px; y++) {
    for (let x = 0; x < px; x++) {
      let n = 0, sr = 0, sg = 0, sb = 0;
      for (let j = 0; j < SUPERSAMPLE; j++) {
        for (let i = 0; i < SUPERSAMPLE; i++) {
          const at = (y * SUPERSAMPLE + j) * size + x * SUPERSAMPLE + i;
          if (depth[at] === 0) continue;
          n += 1; sr += shade[at * 3]; sg += shade[at * 3 + 1]; sb += shade[at * 3 + 2];
        }
      }
      if (!n) continue;
      const o = (y * px + x) * 4;
      out[o] = Math.round(sr / n); out[o + 1] = Math.round(sg / n); out[o + 2] = Math.round(sb / n);
      out[o + 3] = Math.round((255 * n) / (SUPERSAMPLE * SUPERSAMPLE));
    }
  }
  return { width: px, height: px, pixels: out };
}
