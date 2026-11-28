// The second trial's page: drives the wizard's own worker (wizard/src/geometry.worker.js) in
// Chromium, times each step from the moment the page asks to the moment the answer arrives, and
// draws each part's picture. run.py calls the functions on window.trial and saves what they
// return.
import { drawPart } from './render.js';
import { readBinaryStl } from '/src/geometry/stl.js';
import { analysePart } from '/src/geometry/part.js';

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

// The longest stretch the main thread was held, by the browser's long-task timing.
let longest = 0;
new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) longest = Math.max(longest, entry.duration);
}).observe({ type: 'longtask', buffered: true });

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
  for (let r = 0; r < runs; r++) {
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
  }
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
  for (let r = 0; r < runs; r++) {
    const a = must(await ask({ op: 'arrange', plateConfiguration, geometry, printer, supports }));
    times.push(a.ms);
    result = a.result;
  }
  const check = must(await ask({ op: 'check', plateConfiguration: onPlate(result), geometry, printer, supports }));
  return {
    instances: instances.length, placed: result.placed.filter(Boolean).length, packer: result.packer, tried: result.tried,
    arrangeMs: stats(times), problemsAfter: check.result.problems.length, plateConfiguration: result.plateConfiguration, placedFlags: result.placed,
  };
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
  for (let s = 0; s < steps; s++) {
    moving.x = x0 + ((s % 30) - 15) * stepMm;
    const c = must(await ask({ op: 'check', plateConfiguration: pc, geometry, printer, supports }));
    times.push(c.ms);
    problems = Math.max(problems, c.result.problems.length);
  }
  return { instances: pc.instances.length, steps, checkMs: stats(times), firstCheckMs: +times[0].toFixed(2), mostProblems: problems };
}

window.trial = {
  part, arrange, drag,
  longestTaskMs: () => longest,
  machine: () => ({ userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency, deviceMemory: navigator.deviceMemory ?? null }),
};
document.documentElement.dataset.ready = 'true';
