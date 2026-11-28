// The second trial's page: drives the wizard's own worker (wizard/src/geometry.worker.js) in
// Chromium, times each step from the moment the page asks to the moment the answer arrives, and
// draws each part's picture. run.py calls the functions on window.trial and saves what they
// return.
import { drawPart } from './render.js';
import { readBinaryStl } from '/src/geometry/stl.js';
import { analysePart } from '/src/geometry/part.js';
import { placedOutlines } from '/src/geometry/placement.js';

// The part's flat faces: the faces of its hull of at least 25 mm² that are mostly the part's
// own material (not a bridge across a hollow), and whether each got a hull patch. Worked out on
// the main thread, untimed, for the trial's question "every real part given hull patches on its
// flat faces".
function flatFaces(bytes, units) {
  const part = analysePart(readBinaryStl(bytes, units));
  const p = part.mesh.positions;
  const n = part.triangleNormals;
  const a = part.triangleAreas;
  const near = Math.cos(Math.PI / 180);
  const out = [];
  part.faces.forEach((face, index) => {
    if (face.area < 25) return;
    const d = face.outline.reduce((s, q) => s + q[0] * face.normal[0] + q[1] * face.normal[1] + q[2] * face.normal[2], 0) / face.outline.length;
    let material = 0;
    for (let t = 0; t < a.length; t++) {
      if (n[t * 3] * face.normal[0] + n[t * 3 + 1] * face.normal[1] + n[t * 3 + 2] * face.normal[2] < near) continue;
      const c = [0, 1, 2].map((k) => (p[t * 9 + k] + p[t * 9 + 3 + k] + p[t * 9 + 6 + k]) / 3);
      if (Math.abs(c[0] * face.normal[0] + c[1] * face.normal[1] + c[2] * face.normal[2] - d) < 0.01) material += a[t];
    }
    if (material < 0.5 * face.area) return;
    const boxCovers = part.patches.some((q) => q.kind === 'box' && q.normal[0] * face.normal[0] + q.normal[1] * face.normal[1] + q.normal[2] * face.normal[2] >= Math.cos((30.5 * Math.PI) / 180));
    out.push({
      face: index, normal: face.normal.map((v) => +v.toFixed(4)), area: +face.area.toFixed(1), material: +material.toFixed(1),
      patch: !face.dropped, dropped: face.dropped, coveredByBoxPatch: boxCovers,
    });
  });
  return out;
}

let worker = null;
let next = 1;
const waiting = new Map();

function startWorker() {
  if (worker) worker.terminate();
  worker = new Worker('/src/geometry.worker.js', { type: 'module' });
  worker.onmessage = (event) => {
    const done = waiting.get(event.data.id);
    waiting.delete(event.data.id);
    done(event.data);
  };
  worker.onerror = (event) => { throw new Error(`the worker failed: ${event.message}`); };
}

// Posts one message and resolves with {reply, ms}, ms from posting to the answer's arrival.
function ask(message, transfer = []) {
  const id = next++;
  return new Promise((resolve) => {
    const t0 = performance.now();
    waiting.set(id, (reply) => resolve({ reply, ms: performance.now() - t0 }));
    worker.postMessage({ ...message, id }, transfer);
  });
}

function must({ reply, ms }) {
  if (!reply.ok) throw new Error(`${reply.error.code}: ${reply.error.detail}`);
  return { result: reply.result, ms };
}

const fetchPart = async (url) => (await fetch(url)).arrayBuffer();

// The stretches the main thread was held, by the browser's long-task timing, and the windows in
// which the steps were timed: the page's own drawing of pictures and its untimed checks hold the
// main thread too, which the wizard would not do there, so only the timed windows count.
const tasks = [];
const windows = [];
new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) tasks.push([entry.startTime, entry.duration]);
}).observe({ type: 'longtask', buffered: true });
// A heartbeat on the main thread every 10 ms while a step is timed: the longest gap between two
// beats is the longest the main thread could not answer, however the browser counts its tasks.
async function timed(label, work) {
  const start = performance.now();
  let last = start, gap = 0;
  const beat = setInterval(() => {
    const now = performance.now();
    gap = Math.max(gap, now - last);
    last = now;
  }, 10);
  try {
    return await work();
  } finally {
    clearInterval(beat);
    windows.push([start, performance.now(), label, gap]);
    // What follows (a picture drawn) starts in a task of its own, outside the window.
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}
// For each timed step: the longest long task the browser reported in it, and the longest gap
// between heartbeats: [{step, longTaskMs, heartbeatGapMs}].
const heldWhileTimed = () => windows.map(([a, b, label, gap]) => ({
  step: label,
  longTaskMs: Math.max(0, ...tasks.filter(([at]) => at >= a && at <= b).map(([, d]) => d)),
  heartbeatGapMs: +gap.toFixed(1),
}));
const longestAnyMs = () => Math.max(0, ...tasks.map(([, d]) => d));

const stats = (values) => {
  const s = values.slice().sort((a, b) => a - b);
  return { median: s[Math.floor(s.length / 2)], worst: s[s.length - 1], runs: s.length, each: values.map((v) => +v.toFixed(2)) };
};

// One part: read, laid down its best way and its faces found as when it arrives (from a fresh
// worker, `runs` times), and the patches asked for again as when it is selected; then its picture.
async function part({ url, key, name, units = 'mm', runs = 5 }) {
  const bytes = await fetchPart(url);
  const read = [], arrival = [], selecting = [], cold = [];
  let faces = null, orient = null, positions = null;
  await timed(`${key}: read, auto-orient, faces`, async () => { for (let r = 0; r < runs; r++) {
    // As on arrival: read, then auto-orient, which finds the faces on the way.
    startWorker();
    const a = must(await ask({ op: 'read', key, buffer: bytes.slice(0), units }));
    const o = must(await ask({ op: 'orient', key }));
    read.push(a.ms);
    arrival.push(a.ms + o.ms);
    const f = must(await ask({ op: 'faces', key }));
    selecting.push(f.ms);
    positions = a.result.positions;
    faces = f.result;
    orient = o.result;
    // The faces found from nothing, with no auto-orient before them.
    startWorker();
    must(await ask({ op: 'read', key, buffer: bytes.slice(0), units }));
    cold.push(must(await ask({ op: 'faces', key })).ms);
  } });
  const picture = drawPicture({ name, positions, faces, orient });
  return {
    name, key, triangles: positions.length / 9, flatFaces: flatFaces(bytes.slice(0), units),
    faces: { hullTriangles: faces.hullTriangles, faces: faces.faces, dropped: faces.dropped, patches: faces.patches },
    orient,
    timing: { readMs: stats(read), arrivalToBestWayMs: stats(arrival), selectingToPatchesMs: stats(selecting), facesFromNothingMs: stats(cold) },
    picture,
  };
}

function drawPicture({ name, positions, faces, orient }) {
  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 900;
  const ctx = canvas.getContext('2d');
  const patches = faces.patches.map((p, i) => ({ ...p, chosen: i === orient.patch }));
  const hull = patches.filter((p) => p.kind === 'hull').length;
  const box = patches.length - hull;
  const asModelled = [1, 0, 0, 0];
  const where = orient.patch < 0 ? 'as modelled' : `on patch ${orient.patch} (${patches[orient.patch].kind === 'box' ? 'bounding-box side ' + patches[orient.patch].side : 'hull face'})`;
  drawPart(ctx, { x: 0, y: 0, w: 600, h: 450 }, { positions, lay: asModelled, patches, az: -50, el: 28, label: `${name}: as modelled, from above; ${hull} hull and ${box} bounding-box patches` });
  drawPart(ctx, { x: 600, y: 0, w: 600, h: 450 }, { positions, lay: asModelled, patches, az: 130, el: -30, plate: false, label: 'As modelled, from below and behind (red edge: the patch it is laid on)' });
  drawPart(ctx, { x: 0, y: 450, w: 600, h: 450 }, { positions, lay: orient.lay, patches, az: -50, el: 28, label: `Auto-orient: ${where}, ${orient.height.toFixed(1)} mm tall` });
  drawPart(ctx, { x: 600, y: 450, w: 600, h: 450 }, { positions, lay: orient.lay, patches, az: 130, el: 28, label: 'Auto-orient, from the other side' });
  ctx.strokeStyle = '#8a9099';
  ctx.beginPath(); ctx.moveTo(600, 0); ctx.lineTo(600, 900); ctx.moveTo(0, 450); ctx.lineTo(1200, 450); ctx.stroke();
  return canvas.toDataURL('image/png');
}

// Arrange of a plate: `parts` [{url, key, name, count}], each laid its best way first; timed
// `runs` times on a worker that has the parts already.
async function arrange({ parts, printer, supports = false, runs = 5 }) {
  startWorker();
  const geometry = {};
  const instances = [];
  const plateParts = {};
  for (const p of parts) {
    must(await ask({ op: 'read', key: p.key, buffer: await fetchPart(p.url), units: 'mm' }));
    const o = must(await ask({ op: 'orient', key: p.key })).result;
    geometry[p.key] = p.key;
    plateParts[p.key] = { name: p.name };
    for (let i = 0; i < p.count; i++) instances.push({ ref: p.key, ...o.turn, x: 0, y: 0 });
  }
  const plateConfiguration = { parts: plateParts, instances };
  const times = [];
  let result = null;
  await timed(`Arrange of ${instances.length} instances`, async () => {
    for (let r = 0; r < runs; r++) {
      const a = must(await ask({ op: 'arrange', plateConfiguration, geometry, printer, supports }));
      times.push(a.ms);
      result = a.result;
    }
  });
  const check = must(await ask({ op: 'check', plateConfiguration: onPlate(result), geometry, printer, supports }));
  const points = {};
  for (const p of parts) points[p.key] = analysePart(readBinaryStl(await fetchPart(p.url), 'mm')).hull.points;
  const outlines = placedOutlines(onPlate(result), points).map((o) => o.hull);
  return {
    instances: instances.length, placed: result.placed.filter(Boolean).length, packer: result.packer, tried: result.tried,
    arrangeMs: stats(times), problemsAfter: check.result.problems.length, plateConfiguration: result.plateConfiguration, placedFlags: result.placed,
    picture: drawPlate(outlines, printer, plateParts, onPlate(result)),
  };
}

// The arranged plate seen from above: the printable area, its 3 mm margin, and each instance's
// outline as the placement check measures it.
function drawPlate(outlines, printer, plateParts, pc) {
  const scale = 2;
  const canvas = document.createElement('canvas');
  canvas.width = (printer.max[0] - printer.min[0]) * scale + 40;
  canvas.height = (printer.max[1] - printer.min[1]) * scale + 60;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const at = ([x, y]) => [20 + (x - printer.min[0]) * scale, 40 + (printer.max[1] - y) * scale];
  const rect = (x0, y0, x1, y1) => { const [a, b] = at([x0, y1]); const [c, d] = at([x1, y0]); return [a, b, c - a, d - b]; };
  ctx.strokeStyle = '#1f2328';
  ctx.strokeRect(...rect(printer.min[0], printer.min[1], printer.max[0], printer.max[1]));
  ctx.setLineDash([4, 4]);
  ctx.strokeRect(...rect(printer.min[0] + 3, printer.min[1] + 3, printer.max[0] - 3, printer.max[1] - 3));
  ctx.setLineDash([]);
  const colours = ['#9fb4c8', '#b7a6d6', '#9cc9b0', '#d6c08f', '#c9a0a0', '#8fc3d6', '#b0b0b0', '#d9a5c4'];
  const keys = Object.keys(plateParts);
  outlines.forEach((outline, i) => {
    ctx.beginPath();
    outline.forEach((q, k) => { const [x, y] = at(q); if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
    ctx.closePath();
    ctx.fillStyle = colours[keys.indexOf(pc.instances[i].ref) % colours.length];
    ctx.fill();
    ctx.strokeStyle = '#3b4148';
    ctx.stroke();
  });
  ctx.fillStyle = '#1f2328';
  ctx.font = '16px sans-serif';
  ctx.fillText(`${outlines.length} instances on the plate, seen from above (dashed: the 3 mm margin)`, 20, 24);
  return canvas.toDataURL('image/png');
}

const onPlate = (result) => ({
  ...result.plateConfiguration,
  instances: result.plateConfiguration.instances.filter((_, i) => result.placed[i]),
});

// A drag: one instance moved across a plate of `count` instances, `steps` times, the placement
// check of the whole plate asked for at each movement, as the Layout step does while dragging.
async function drag({ plateConfiguration, parts, printer, supports = false, steps = 60, stepMm = 4 }) {
  const geometry = {};
  for (const p of parts) geometry[p.key] = p.key;
  const pc = JSON.parse(JSON.stringify(plateConfiguration));
  const moving = pc.instances[0];
  const x0 = moving.x;
  const times = [];
  let problems = 0;
  await timed(`a drag at ${pc.instances.length} instances`, async () => {
    for (let s = 0; s < steps; s++) {
      moving.x = x0 + ((s % 30) - 15) * stepMm;
      const c = must(await ask({ op: 'check', plateConfiguration: pc, geometry, printer, supports }));
      times.push(c.ms);
      problems = Math.max(problems, c.result.problems.length);
    }
  });
  return { instances: pc.instances.length, steps, checkMs: stats(times), firstCheckMs: +times[0].toFixed(2), mostProblems: problems };
}

window.trial = {
  part, arrange, drag,
  heldWhileTimed, longestAnyMs,
  machine: () => ({ userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency, deviceMemory: navigator.deviceMemory ?? null }),
};
document.documentElement.dataset.ready = 'true';
