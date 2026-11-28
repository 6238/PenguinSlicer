// The trial's pictures: a part drawn on a 2D canvas, flat-shaded, by painting its triangles far
// to near, with its patches on it. No 3D drawing context is needed, so the pictures come out the
// same on a machine without a graphics card. Only the trial uses this; the Layout step's view is
// drawn with three.js.

const PART = [184, 178, 166];
const HULL_PATCH = 'rgba(28, 110, 220, 0.50)';
const BOX_PATCH = 'rgba(28, 110, 220, 0.30)';
const PATCH_EDGE = 'rgba(10, 60, 150, 0.95)';
const CHOSEN_EDGE = 'rgba(200, 40, 30, 0.95)';

function matrixOf(q) {
  const len = Math.hypot(...q);
  const [w, x, y, z] = q.map((v) => v / len);
  return [
    [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
    [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
    [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
  ];
}

const apply = (m, p) => [0, 1, 2].map((r) => m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2]);

// The camera: looking from azimuth `az` and elevation `el` (degrees) at the origin, orthographic.
function camera(az, el) {
  const a = (az * Math.PI) / 180, e = (el * Math.PI) / 180;
  const eye = [Math.cos(e) * Math.cos(a), Math.cos(e) * Math.sin(a), Math.sin(e)];
  const right = [-Math.sin(a), Math.cos(a), 0];
  const up = [-Math.sin(e) * Math.cos(a), -Math.sin(e) * Math.sin(a), Math.cos(e)];
  return { eye, right, up };
}

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

// Draws, in the rectangle (x, y, w, h) of `ctx`, the part whose corners are `positions` (part
// coordinates) laid by the quaternion `lay`, seen from (az, el), with `patches` drawn on it
// (each {kind, normal, outline}); `chosen` is the patch it lies on, drawn with a red edge.
export function drawPart(ctx, rect, { positions, lay, patches = [], az = -50, el = 28, plate = true, label = '' }) {
  const m = matrixOf(lay);
  const n = positions.length / 3;
  const pts = new Float64Array(n * 3);
  const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < n; i++) {
    const p = apply(m, [positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]]);
    for (let k = 0; k < 3; k++) {
      pts[i * 3 + k] = p[k];
      if (p[k] < lo[k]) lo[k] = p[k];
      if (p[k] > hi[k]) hi[k] = p[k];
    }
  }
  const shift = [-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]];
  const place = (p) => [p[0] + shift[0], p[1] + shift[1], p[2] + shift[2]];
  const cam = camera(az, el);
  const project = (p) => [dot(p, cam.right), dot(p, cam.up), dot(p, cam.eye)];
  // Fit the part (and its plate square) into the rectangle.
  const size = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);
  const corners = [];
  for (const x of [-0.6, 0.6]) for (const y of [-0.6, 0.6]) for (const z of [0, 1]) corners.push(project([x * size, y * size, z * (hi[2] - lo[2])]));
  const us = corners.map((c) => c[0]), vs = corners.map((c) => c[1]);
  const scale = 0.9 * Math.min(rect.w / (Math.max(...us) - Math.min(...us)), (rect.h - 30) / (Math.max(...vs) - Math.min(...vs)));
  const cu = (Math.max(...us) + Math.min(...us)) / 2, cv = (Math.max(...vs) + Math.min(...vs)) / 2;
  const toScreen = (q) => [rect.x + rect.w / 2 + (q[0] - cu) * scale, rect.y + 24 + (rect.h - 30) / 2 - (q[1] - cv) * scale];

  ctx.save();
  ctx.beginPath();
  ctx.rect(rect.x, rect.y, rect.w, rect.h);
  ctx.clip();
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
  if (plate) {
    const s = 0.6 * size;
    const grid = Math.max(1, 10 ** Math.floor(Math.log10(size / 2)));
    ctx.strokeStyle = '#d9dde3';
    ctx.lineWidth = 1;
    for (let g = -Math.floor(s / grid) * grid; g <= s; g += grid) {
      for (const [a, b] of [[[g, -s, 0], [g, s, 0]], [[-s, g, 0], [s, g, 0]]]) {
        const p = toScreen(project(a)), q = toScreen(project(b));
        ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); ctx.stroke();
      }
    }
  }
  // Triangles, and the patches as polygons among them, painted far to near.
  const items = [];
  const light = [0.35 * cam.eye[0] + 0.3, 0.35 * cam.eye[1] - 0.2, 0.35 * cam.eye[2] + 0.8];
  const ll = Math.hypot(...light);
  for (let t = 0; t < n / 3; t++) {
    const a = place([pts[t * 9], pts[t * 9 + 1], pts[t * 9 + 2]]);
    const b = place([pts[t * 9 + 3], pts[t * 9 + 4], pts[t * 9 + 5]]);
    const c = place([pts[t * 9 + 6], pts[t * 9 + 7], pts[t * 9 + 8]]);
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    const nrm = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const len = Math.hypot(...nrm);
    if (!(len > 0) || dot(nrm, cam.eye) <= 0) continue;
    const shade = 0.35 + 0.65 * Math.max(0, dot(nrm, light) / (len * ll));
    const qa = project(a), qb = project(b), qc = project(c);
    items.push({ depth: (qa[2] + qb[2] + qc[2]) / 3, poly: [qa, qb, qc], fill: `rgb(${PART.map((k) => Math.round(k * shade)).join(',')})` });
  }
  for (const patch of patches) {
    const normal = apply(m, patch.normal);
    if (dot(normal, cam.eye) <= 0.02) continue;
    const ring = patch.outline.map((p) => place(apply(m, p)));
    const mid = [0, 1, 2].map((k) => ring.reduce((s, p) => s + p[k], 0) / ring.length);
    // Drawn in 10% toward its middle and lifted off the face, as the Layout step draws it.
    const lifted = ring.map((p) => [0, 1, 2].map((k) => mid[k] + 0.9 * (p[k] - mid[k]) + 0.002 * size * normal[k]));
    const poly = lifted.map(project);
    const depth = Math.max(...poly.map((q) => q[2])) + 0.01 * size;
    items.push({ depth, poly, fill: patch.kind === 'box' ? BOX_PATCH : HULL_PATCH, edge: patch.chosen ? CHOSEN_EDGE : PATCH_EDGE, dashed: patch.kind === 'box' });
  }
  items.sort((p, q) => p.depth - q.depth);
  for (const item of items) {
    ctx.beginPath();
    item.poly.forEach((q, i) => {
      const [x, y] = toScreen(q);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle = item.fill;
    ctx.fill();
    if (item.edge) {
      ctx.setLineDash(item.dashed ? [5, 4] : []);
      ctx.strokeStyle = item.edge;
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.setLineDash([]);
    } else {
      ctx.strokeStyle = item.fill;
      ctx.lineWidth = 0.5;
      ctx.stroke();
    }
  }
  ctx.fillStyle = '#1f2328';
  ctx.font = '14px sans-serif';
  ctx.fillText(label, rect.x + 8, rect.y + 18);
  ctx.restore();
}
