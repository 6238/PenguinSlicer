// The page every candidate method shares: the view, the plate, the ghost, the layer bar, the
// camera and its controls, and the measuring the trial reads (window.trial). A method only
// draws the toolpaths. WebGL 2 is used directly; three.js gives the camera and its controls.
import * as THREE from 'three';
import { OrbitControls } from '/vendor/three/examples/jsm/controls/OrbitControls.js';
import { GROUP_COLOURS, GROUP_NAMES } from './gcode.js';
import { BACKGROUND, COLOURS, sortPixels, changedShare } from './look.js';
export { BACKGROUND, COLOURS };

const rgb = (hex) => [(hex >> 16 & 255) / 255, (hex >> 8 & 255) / 255, (hex & 255) / 255];
// The walls' light, as the mockup's: from the front left, above.
export const LIGHT = (() => { const x = -0.4, y = -0.6, l = Math.hypot(x, y); return [x / l, y / l]; })();
const GHOST = [...rgb(0x95a0ac), 0.36];           // the mockup's ghost: grey, 36 % opaque
const PLATE = rgb(0xe3e7ec), GRID = rgb(0xcfd5dc);
const PLATE_MM = [340, 320];

export function program(gl, vs, fs) {
  const compile = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS) && !gl.isContextLost()) throw new Error(gl.getShaderInfoLog(s));
    return s;
  };
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl.VERTEX_SHADER, vs)); gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS) && !gl.isContextLost()) throw new Error(gl.getProgramInfoLog(p));
  const u = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS) || 0;
  for (let i = 0; i < n; i++) { const name = gl.getActiveUniform(p, i).name.replace(/\[0\]$/, ''); u[name] = gl.getUniformLocation(p, name); }
  return { p, u, a: (name) => gl.getAttribLocation(p, name) };
}

export function buffer(gl, data, target = gl.ARRAY_BUFFER) {
  const b = gl.createBuffer();
  gl.bindBuffer(target, b); gl.bufferData(target, data, gl.STATIC_DRAW);
  return b;
}

const FLAT_VS = `#version 300 es
in vec3 position; uniform mat4 viewProj; out vec3 vPos;
void main() { vPos = position; gl_Position = viewProj * vec4(position, 1.0); }`;
const FLAT_FS = `#version 300 es
precision highp float; uniform vec4 colour; out vec4 o;
void main() { o = colour; }`;
// The ghost: what is above the cut, faint grey, its faces a little darker as they turn from
// the light so its shape reads.
const GHOST_FS = `#version 300 es
precision highp float; in vec3 vPos; uniform vec4 colour; uniform float cut; out vec4 o;
void main() {
  if (vPos.z < cut) discard;
  vec3 n = normalize(cross(dFdx(vPos), dFdy(vPos)));
  float shade = 0.82 + 0.18 * abs(dot(n, normalize(vec3(-0.4, -0.6, 0.7))));
  o = vec4(colour.rgb * shade, colour.a);
}`;

// The plate, its grid and the ghost.
function scenery(gl, ghostCorners) {
  const flat = program(gl, FLAT_VS, FLAT_FS), ghost = program(gl, FLAT_VS, GHOST_FS);
  const [px, py] = PLATE_MM;
  const plate = buffer(gl, new Float32Array([0, 0, -0.02, px, 0, -0.02, px, py, -0.02, 0, 0, -0.02, px, py, -0.02, 0, py, -0.02]));
  const grid = [];
  for (let x = 0; x <= px; x += 10) grid.push(x, 0, -0.01, x, py, -0.01);
  for (let y = 0; y <= py; y += 10) grid.push(0, y, -0.01, px, y, -0.01);
  const gridBuf = buffer(gl, new Float32Array(grid));
  // The ghost goes to the graphics side 8 MB a frame behind a fence, as the boxes do: twelve
  // blocks' ghost alone is 17 MB.
  const ghostBuf = gl.createBuffer();
  let ghostSent = -1, ghostFence = null;
  const ghostBytes = new Uint8Array(ghostCorners.buffer, ghostCorners.byteOffset, ghostCorners.byteLength);
  const vao = gl.createVertexArray();
  const draw = (prog, buf, mode, count) => {
    gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    const a = prog.a('position');
    gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 3, gl.FLOAT, false, 0, 0);
    gl.drawArrays(mode, 0, count);
  };
  return {
    // One more piece of the ghost's upload; true once it is all on the graphics side.
    upload() {
      if (ghostFence) {
        if (gl.getSyncParameter(ghostFence, gl.SYNC_STATUS) !== gl.SIGNALED) return false;
        gl.deleteSync(ghostFence); ghostFence = null;
      }
      if (ghostSent >= ghostBytes.length) return true;
      gl.bindBuffer(gl.ARRAY_BUFFER, ghostBuf);
      if (ghostSent < 0) { gl.bufferData(gl.ARRAY_BUFFER, Math.max(4, ghostBytes.length), gl.STATIC_DRAW); ghostSent = 0; }
      else {
        const n = Math.min(8 * 1024 * 1024, ghostBytes.length - ghostSent);
        gl.bufferSubData(gl.ARRAY_BUFFER, ghostSent, ghostBytes, ghostSent, n);
        ghostSent += n;
      }
      ghostFence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
      gl.flush();
      return false;
    },
    ghostReady: () => ghostSent >= ghostBytes.length && !ghostFence,
    plate(viewProj) {
      gl.useProgram(flat.p); gl.uniformMatrix4fv(flat.u.viewProj, false, viewProj);
      gl.uniform4f(flat.u.colour, ...PLATE, 1); draw(flat, plate, gl.TRIANGLES, 6);
      gl.uniform4f(flat.u.colour, ...GRID, 1); draw(flat, gridBuf, gl.LINES, grid.length / 3);
    },
    ghost(viewProj, cut) {
      if (ghostSent < ghostBytes.length) return;
      gl.useProgram(ghost.p); gl.uniformMatrix4fv(ghost.u.viewProj, false, viewProj);
      gl.uniform4f(ghost.u.colour, ...GHOST); gl.uniform1f(ghost.u.cut, cut);
      gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false);
      gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK);
      draw(ghost, ghostBuf, gl.TRIANGLES, ghostCorners.length / 3);
      gl.disable(gl.CULL_FACE); gl.depthMask(true); gl.disable(gl.BLEND);
    },
  };
}

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : null; };

// The trial's page. `method` is { name, prepare, options, create(gl, prepared, info) }, and
// create returns { draw(frame, scene, fresh) -> { segments, complete, again } }:
// `fresh` says the view or the layer changed since the last frame; `segments` how many
// toolpath boxes the frame drew (0 for a frame of the plate alone); `complete` that the full
// look is on the screen; `again` that the method wants another frame to go on drawing.
export async function start(method) {
  const q = new URLSearchParams(location.search);
  const plateName = q.get('plate') || 'four-each-b-supports';
  const width = +(q.get('w') || 640), height = +(q.get('h') || 480);
  const status = document.getElementById('status');
  const say = (text) => { status.textContent = text; };
  const trial = window.trial = { method: method.name, plate: plateName, holds: [], errors: [] };
  window.addEventListener('error', (e) => trial.errors.push(String(e.message)));
  window.addEventListener('unhandledrejection', (e) => trial.errors.push(String(e.reason)));
  try {
    new PerformanceObserver((list) => { for (const e of list.getEntries()) trial.holds.push([e.startTime, e.duration]); })
      .observe({ type: 'longtask', buffered: true });
  } catch { trial.holds = null; }

  // The time to the first layer starts here, where the Preview step would start fetching.
  const t0 = performance.now();
  say(`Reading ${plateName}…`);
  const worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
  const data = await new Promise((resolve) => {
    worker.onmessage = (e) => resolve(e.data);
    worker.postMessage({ plate: plateName, method: method.prepare, options: method.options || {} });
  });
  worker.terminate();
  if (!data.ok) { say(data.error); trial.failed = data.error; return; }
  const tData = performance.now();

  const view = document.getElementById('view');
  const canvas = document.createElement('canvas');
  canvas.width = width; canvas.height = height;
  canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
  view.style.width = `${width}px`;
  view.prepend(canvas);
  const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, preserveDrawingBuffer: false });
  if (!gl) { say('This browser has no WebGL 2.'); trial.failed = 'no webgl2'; return; }

  // Framing: the instances' bounds.
  const b = data.bounds, n = b.length / 6;
  const box = [Infinity, Infinity, 0, -Infinity, -Infinity, 0];
  for (let i = 0; i < n; i++) for (let a = 0; a < 3; a++) {
    box[a] = Math.min(box[a], b[i * 6 + a]); box[a + 3] = Math.max(box[a + 3], b[i * 6 + 3 + a]);
  }
  // The near plane at 5 mm keeps the depth buffer fine enough for layers 0.2 mm apart seen
  // from across the plate; no view comes nearer than 30 mm.
  const camera = new THREE.PerspectiveCamera(40, width / height, 5, 3000);
  camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, canvas);
  controls.screenSpacePanning = true;
  controls.maxPolarAngle = Math.PI * 0.49;
  const layers = data.layers;
  let k = layers - 1, moving = false, dirty = true, more = false, scene = null, drawer = null, lost = false;
  let complete = false;
  // The ghost has arrived on the graphics side; a lost drawing context loses it with the rest.
  let ghostDone = false;
  // While false, the ghost is left out of every frame (the coarse check of the ghost compares).
  let ghostShown = true;

  function build() {
    const t = performance.now();
    ghostDone = false;
    scene = scenery(gl, data.ghost);
    drawer = method.create(gl, data.prepared, { resolution: [width, height] });
    trial.build_ms = performance.now() - t;
  }
  build();
  canvas.addEventListener('webglcontextlost', (e) => { e.preventDefault(); lost = true; trial.contextLost = (trial.contextLost || 0) + 1; });
  canvas.addEventListener('webglcontextrestored', () => { lost = false; build(); dirty = true; });

  // The views the renders are made from, each from the instances' bounds.
  const centre = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2], span = Math.max(box[3] - box[0], box[4] - box[1], 60);
  const first = [0, 1, 2, 3, 4, 5].map((a) => b[a]);
  const views = {
    default: () => aim([centre[0], centre[1], box[5] / 3], [0.35, -1.05, 0.9], span * 1.6, box[5]),
    top: () => aim([centre[0], centre[1], 0], [0, -0.001, 1], span * 1.55, 0),
    'edge-on': () => aim([centre[0], centre[1], box[5] / 2], [0, -1, 0], span * 1.6, 0),
    'edge-on-side': () => aim([centre[0], centre[1], box[5] / 2], [-1, 0, 0], span * 1.6, 0),
    zoom: () => aim([(first[0] + first[3]) / 2, (first[1] + first[4]) / 2, first[5] / 2], [0.6, -0.8, 0.7], Math.max(40, (first[3] - first[0]) * 1.4), 0),
    'zoom-edge-on': () => aim([(first[0] + first[3]) / 2, first[1], first[5] / 2], [0.3, -1, 0.0], Math.max(30, (first[3] - first[0]) * 0.9), 0),
    'zoom-top': () => aim([(first[0] + first[3]) / 2, (first[1] + first[4]) / 2, first[5]], [0, -0.001, 1], Math.max(30, (first[3] - first[0]) * 0.8), 0),
  };
  function aim(target, dir, distance, lift) {
    const l = Math.hypot(...dir);
    controls.target.set(...target);
    camera.position.set(target[0] + dir[0] / l * distance, target[1] + dir[1] / l * distance, target[2] + dir[2] / l * distance + lift);
    const saved = controls.maxPolarAngle;
    controls.maxPolarAngle = Math.PI / 2;           // edge-on renders look exactly sideways
    controls.update();
    controls.maxPolarAngle = saved;
    dirty = true;
  }
  views.default();
  controls.addEventListener('change', () => { dirty = true; });
  controls.addEventListener('start', () => { moving = true; dirty = true; });
  controls.addEventListener('end', () => { moving = false; dirty = true; });

  // The layer bar and its readout. Dragging the bar counts as moving, like turning the view.
  const bar = document.getElementById('layer');
  const readout = document.getElementById('readout');
  bar.min = 1; bar.max = layers; bar.value = layers;
  const showLayer = () => { readout.textContent = `${k + 1} / ${layers} · ${data.layerZ[k].toFixed(2)} mm`; };
  bar.addEventListener('input', () => { k = +bar.value - 1; showLayer(); dirty = true; });
  bar.addEventListener('pointerdown', () => { moving = true; });
  bar.addEventListener('pointerup', () => { moving = false; dirty = true; });
  bar.addEventListener('change', () => { moving = false; dirty = true; });
  showLayer();
  const legend = document.getElementById('key');
  if (legend) legend.innerHTML = GROUP_NAMES.map((name, g) => `<span><i style="background:#${GROUP_COLOURS[g].toString(16).padStart(6, '0')}"></i>${name}</span>`).join('');

  const viewProj = new Float32Array(16), m = new THREE.Matrix4();
  function frameState() {
    camera.updateMatrixWorld();
    m.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    viewProj.set(m.elements);
    return { viewProj, camPos: [camera.position.x, camera.position.y, camera.position.z],
      pxPerUnit: camera.projectionMatrix.elements[5] * height / 2, k, moving,
      layerZ: data.layerZ, layers };
  }
  let drawnLast = 0;
  function render(fresh) {
    if (lost) return { segments: 0, complete: false };
    gl.viewport(0, 0, width, height);
    const r = drawer.draw(frameState(), ghostShown ? scene : { ...scene, ghost() {} }, fresh);
    // The ghost uploads behind the toolpaths; once it has arrived, the view is drawn again
    // with it, and until then the full look is not counted as on the screen.
    if (!ghostDone) {
      ghostDone = scene.upload() && scene.ghostReady();
      if (ghostDone) dirty = true;
      r.complete = false;
      r.again = true;
    }
    drawnLast = r.segments;
    complete = r.complete;
    more = !!r.again;
    return r;
  }

  // The frame loop: draws when something changed, or while the method has more to draw.
  // `driver`, while set, moves the view or the layer bar once each frame, as a user's drag
  // would; `onFrame` sees every frame drawn.
  let driver = null;
  const watchers = new Set();
  const sync = q.get('sync') === '1', onePixel = new Uint8Array(4);
  function loop(now) {
    requestAnimationFrame(loop);
    if (driver) driver(now);
    if (!dirty && !more) return;
    const fresh = dirty;
    dirty = false;
    const t = performance.now();
    const r = render(fresh);
    // ?sync=1: wait for each frame's drawing to finish, to check that the frame times are the
    // drawing's and not only the queueing of it.
    if (sync) gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, onePixel);
    const js = performance.now() - t;
    for (const w of [...watchers]) w(now, js, r);
  }
  requestAnimationFrame(loop);
  trial.frameLog = [];
  const logFrames = (now, js, r) => { trial.frameLog.push([Math.round(now), Math.round(js), r.segments, r.complete ? 1 : 0]); if (trial.frameLog.length > 60) watchers.delete(logFrames); };
  watchers.add(logFrames);
  const afterFrame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  // Resolves once the full look is on the screen.
  const untilComplete = () => new Promise((resolve) => {
    const w = (now, js, r) => { if (r.complete) { watchers.delete(w); resolve(now); } };
    watchers.add(w);
    dirty = true;
  });
  // The first layer drawn: the first frame that drew toolpaths, not one of the plate alone
  // while the boxes upload.
  await new Promise((resolve) => { const w = (now, js, r) => { if (r.segments > 0) { watchers.delete(w); resolve(); } }; watchers.add(w); dirty = true; });
  await afterFrame();
  const tFirst = performance.now();
  await untilComplete();
  await afterFrame();
  const tFull = performance.now();
  say(`${method.name}: ${plateName}, ${layers} layers, ${data.stats.segments.toLocaleString()} segments`);

  // A path of `steps` frames, each step(i) moving something, as a drag would; the frames
  // between are timed, and then the time until the full look is back on the screen.
  async function runPath(steps, step) {
    const stamps = [], js = [];
    await afterFrame();
    const tStart = performance.now();
    await new Promise((resolve) => {
      let i = 0;
      const w = (now, j) => { stamps.push(now); js.push(j); };
      watchers.add(w);
      moving = true;
      driver = () => {
        if (i >= steps) { driver = null; watchers.delete(w); resolve(); return; }
        step(i++); dirty = true;
      };
    });
    const tEnd = performance.now();
    moving = false;
    const restStamps = [];
    const restWatch = (now) => restStamps.push(now);
    watchers.add(restWatch);
    await untilComplete();
    await afterFrame();
    watchers.delete(restWatch);
    const tRest = performance.now();
    const intervals = stamps.slice(1).map((t, i) => t - stamps[i]);
    const restIntervals = [tEnd, ...restStamps].slice(1).map((t, i, a) => t - (i ? a[i - 1] : tEnd));
    const holds = trial.holds ? trial.holds.filter(([s]) => s >= tStart).map(([, d]) => d) : [];
    const holdsMoving = trial.holds ? trial.holds.filter(([s]) => s >= tStart && s < tEnd).map(([, d]) => d) : [];
    const worst = Math.max(...intervals);
    return {
      frames: stamps.length, fps_typical: 1000 / median(intervals), fps_worst: 1000 / worst,
      frame_ms_median: median(intervals), frame_ms_worst: worst,
      longest_hold_ms: Math.max(0, ...holds, ...js),
      longest_hold_moving_ms: Math.max(0, ...holdsMoving, ...js),
      rest_ms: tRest - tEnd, rest_frames: restStamps.length,
      rest_frame_ms_worst: Math.max(0, ...restIntervals),
      segments_drawn_moving: drawnWhileMoving,
    };
  }
  let drawnWhileMoving = 0;
  watchers.add((now, js, r) => { if (moving) drawnWhileMoving = r.segments; });

  function turnPath(steps) {          // one full turn about the plate, tilting up and down
    const target = controls.target.clone(), offset = camera.position.clone().sub(target);
    const s = new THREE.Spherical().setFromVector3(new THREE.Vector3(offset.x, offset.z, -offset.y));
    return (i) => {
      const theta = s.theta + 2 * Math.PI * (i + 1) / steps;
      const phi = Math.min(Math.PI * 0.49, Math.max(0.15, s.phi + 0.35 * Math.sin(2 * Math.PI * (i + 1) / steps)));
      const v = new THREE.Vector3().setFromSphericalCoords(s.radius, phi, theta);
      camera.position.set(target.x + v.x, target.y - v.z, target.z + v.y);
      controls.update();
    };
  }
  function layerPath(steps) {          // the bar dragged from the top to the bottom and back up
    return (i) => {
      const t = (i + 1) / steps, f = t < 0.5 ? 1 - 2 * t : 2 * t - 1;
      bar.value = String(Math.max(1, Math.round(1 + f * (layers - 1))));
      bar.dispatchEvent(new Event('input'));
    };
  }

  // The coarse checks of the look read what the method itself put on the screen at rest: the
  // view is drawn again, as after any change, and its pixels are read on the frame that put the
  // full look on the screen, ghost included, before the browser shows it and clears it. Each
  // look is kept under its name for `changed`. With `ghost` false the ghost is left out, so
  // comparing the two looks shows how much of the view the ghost takes.
  const looks = {};
  function look(name, { ghost = true } = {}) {
    return new Promise((resolve) => {
      ghostShown = ghost;
      const w = (now, js, r) => {
        if (!r.complete) return;
        watchers.delete(w);
        const px = new Uint8Array(width * height * 4);
        gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, px);
        ghostShown = true;
        dirty = true;
        looks[name] = px;
        resolve(sortPixels(px));
      };
      watchers.add(w);
      dirty = true;
    }).then(async (sorted) => { await afterFrame(); return sorted; });
  }

  Object.assign(trial, {
    ready: true, stats: data.stats, layers, segments: data.stats.segments, decimate: drawer.decimate || 1,
    first_layer_ms: tFirst - t0, full_look_ms: tFull - t0, data_ms: tData - t0,
    views: Object.keys(views),
    async setView(name) { views[name](); await untilComplete(); await afterFrame(); },
    async setLayer(layer) { bar.value = String(layer); bar.dispatchEvent(new Event('input')); await untilComplete(); await afterFrame(); },
    // The look while moving, held on the screen for a render.
    async showMoving() {
      moving = true; dirty = true;
      await new Promise((resolve) => { const w = () => { watchers.delete(w); resolve(); }; watchers.add(w); });
      await afterFrame();
    },
    async stopMoving() { moving = false; await untilComplete(); await afterFrame(); },
    turn: (steps) => runPath(steps, turnPath(steps)),
    dragLayers: (steps) => runPath(steps, layerPath(steps)),
    look,
    // The share of the view two kept looks differ in.
    changed(a, b) { return changedShare(looks[a], looks[b]); },
    memory() { return performance.memory ? { js_heap_mb: performance.memory.usedJSHeapSize / 1048576 } : {}; },
    drawn: () => drawnLast,
    async loseContext() {
      const ext = gl.getExtension('WEBGL_lose_context');
      await new Promise((resolve) => { canvas.addEventListener('webglcontextlost', resolve, { once: true }); ext.loseContext(); });
      await afterFrame();              // a restore asked for while the loss is being handled is ignored
      await new Promise((resolve) => { canvas.addEventListener('webglcontextrestored', resolve, { once: true }); ext.restoreContext(); });
      await untilComplete(); await afterFrame();
    },
  });
  document.body.dataset.ready = '1';
}
