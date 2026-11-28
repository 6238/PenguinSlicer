// The layer preview's view (wizard/README-details.md, "The layer preview"; wizard/README.md, "The
// layer preview, as a requirement"): a sliced file's own toolpaths in 3D with the layer bar at the
// view's right, drawn by method C of the first trial (preview/drawing.js), the file read and
// prepared by a worker of its own (preview/preview-client.js), so that the page keeps answering.
// It is given the element to draw in (the mockup's #viewer-container, a .gl-view) and a sliced
// file's bytes; it reports its progress, that it is ready, a failure as an error report, and its
// drawing summary. The result's card, the readout, the colour key and the buttons under the view
// are the Preview step's, around it.
//   look   a left-drag turns the view, a right-drag slides it, the wheel zooms (the mouse of the
//          Preview step, unlike the Layout step's); the layer bar is dragged, or moved by the
//          arrow keys, Page Up and Page Down, Home and End
//   moving while the view turns or the bar is dragged a simpler look, the four colours kept; the
//          full look returns when it comes to rest
//   lost   after a lost drawing context the view draws again, without a reload, from the data it
//          kept
import * as THREE from 'three';
import { OrbitControls } from '../../vendor/three/examples/jsm/controls/OrbitControls.js';

import { createHoldMeter } from '../hold-meter.js';
import { createDrawing } from '../preview/drawing.js';
import { createFrameStats } from '../preview/frame-stats.js';
import { barFraction, clampLayer, layerAtFraction, layerForKey, thumbLabel, valueText } from '../preview/layer-bar.js';
import { prepareSlicedFile } from '../preview/preview-client.js';
import { PREVIEW_FAILED, PREVIEW_NOT_DRAWABLE, errorReport } from '../preview/preview-errors.js';

// The plate of every printer in the profile catalog today (contracts/plate-configuration.md,
// "Coordinates"), for a caller that gives none.
const DEFAULT_PRINTER = { min: [0, 0], max: [340, 320] };
// The near plane at 5 mm keeps the depth buffer fine enough for layers 0.2 mm apart seen from
// across the plate (the trial's viewer).
const NEAR_MM = 5, FAR_MM = 3000;

// createLayerPreview(element, options):
//   frames       the frame seam ({next, cancel, now})
//   clock        the clock seam, for the heartbeat that measures the main thread's longest hold
//   startWorker  the preview worker seam's startPreviewWorker
//   printer      the printable area {min: [x, y], max: [x, y]} in millimetres
//   software     whether the browser draws 3D in software: then at a pixel ratio of 1
//   report(what, {detail})  a report about the page itself: drawing_context_lost, page_failed
//   onFailure(error)  a failure after show() has resolved to {ok: true}, as an error report: the
//                     drawing failing on a later frame or when built again after a lost context;
//                     the view then draws nothing more and hides its bar until the next show()
//   onProgress({stage, fraction}), onLayer({index, layers, z})
export function createLayerPreview(element, {
  frames, clock = null, startWorker, printer = DEFAULT_PRINTER, software = false,
  report = () => {}, onFailure = () => {}, onProgress = () => {}, onLayer = () => {},
} = {}) {
  const canvas = document.createElement('canvas');
  canvas.className = 'gl-canvas';
  canvas.tabIndex = 0;
  canvas.setAttribute('aria-label', 'The layer preview of the sliced plate');
  element.prepend(canvas);
  const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, preserveDrawingBuffer: false });

  // The layer bar: the mockup's markup with its ids, at the view's right (the page holds one view).
  const bar = document.createElement('div');
  bar.id = 'layer-slider';
  bar.className = 'layer-slider';
  bar.tabIndex = 0;
  bar.setAttribute('role', 'slider');
  bar.setAttribute('aria-label', 'Layer');
  bar.hidden = true;
  const track = document.createElement('div'); track.className = 'ls-track';
  const fill = document.createElement('div'); fill.className = 'ls-fill'; fill.id = 'ls-fill';
  const thumb = document.createElement('div'); thumb.className = 'ls-thumb'; thumb.id = 'ls-thumb';
  const label = document.createElement('span'); label.id = 'ls-label';
  track.append(fill); thumb.append(label); bar.append(track, thumb);
  element.append(bar);

  const camera = new THREE.PerspectiveCamera(40, 1, NEAR_MM, FAR_MM);
  camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false;
  controls.screenSpacePanning = true;
  controls.maxPolarAngle = Math.PI * 0.49;
  // the Preview step's mouse: left turns, right slides, the wheel zooms
  controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
  controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };

  const ratio = software ? 1 : Math.min(2, globalThis.devicePixelRatio || 1);
  let width = 1, height = 1;
  let data = null;          // the prepared sliced file, kept for drawing again after a lost context
  let drawing = null;
  let job = null;           // the preparation under way
  let k = 0;                // the current layer, from 0
  let moving = false, dirty = false, more = false, lost = false;
  let frame = null;
  let complete = false;
  let segments = 0;         // the toolpath boxes the last frame drew
  let ghostShown = true;
  let firstLayerMs = null, since = 0;
  let stats = createFrameStats();
  const holds = clock ? createHoldMeter(clock) : null;
  const watchers = new Set();
  let driver = null;
  let destroyed = false;
  let failed = false;       // the drawing failed: nothing more is drawn until the next show

  // ---- drawing, only when something changed or the drawing has more to do
  function invalidate() {
    dirty = true;
    if (frame === null && !destroyed && !failed) frame = frames.next(loop);
  }
  function loop(now) {
    frame = null;
    if (failed) return;
    if (driver) driver();
    if (!dirty && !more) return;
    const fresh = dirty;
    dirty = false;
    let r = { segments: 0, complete: false, again: false };
    if (drawing && !lost) {
      const f = frameState();
      gl.viewport(0, 0, width, height);
      try {
        r = drawing.draw(f, fresh, ghostShown);
      } catch (error) {
        fail(errorReport(PREVIEW_FAILED, `the drawing failed: ${error && error.message ? error.message : error}`));
        return;
      }
      stats.frame(frames.now(), moving);
    }
    complete = r.complete;
    more = Boolean(r.again);
    segments = r.segments;
    for (const w of [...watchers]) w(now, r);
    if ((more || driver) && frame === null && !destroyed) frame = frames.next(loop);
  }
  function frameState() {
    camera.updateMatrixWorld();
    const m = new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    return {
      viewProj: new Float32Array(m.elements), camPos: [camera.position.x, camera.position.y, camera.position.z],
      pxPerUnit: (camera.projectionMatrix.elements[5] * height) / 2, k, moving, layerZ: data.layerZ, layers: data.layers,
    };
  }

  function resize() {
    const w = Math.max(1, Math.round(element.clientWidth * ratio)), h = Math.max(1, Math.round(element.clientHeight * ratio));
    if (w === width && h === height) return;
    width = w; height = h;
    canvas.width = w; canvas.height = h;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (drawing) drawing.resize(w, h);
    invalidate();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(element);

  controls.addEventListener('change', invalidate);
  controls.addEventListener('start', () => { moving = true; invalidate(); });
  controls.addEventListener('end', () => { moving = false; invalidate(); });

  // ---- the layer bar
  function showLayer() {
    if (!data) return;
    const frac = barFraction(k, data.layers);
    thumb.style.top = `${(1 - frac) * 100}%`;
    fill.style.height = `${frac * 100}%`;
    label.textContent = thumbLabel(k);
    bar.setAttribute('aria-valuemin', '1');
    bar.setAttribute('aria-valuemax', String(data.layers));
    bar.setAttribute('aria-valuenow', String(k + 1));
    bar.setAttribute('aria-valuetext', valueText(k, data.layers, data.layerZ[k]));
    onLayer({ index: k, layers: data.layers, z: data.layerZ[k] });
  }
  function setLayer(index) {
    if (!data) return;
    const next = clampLayer(index, data.layers);
    if (next === k) return;
    k = next;
    showLayer();
    invalidate();
  }
  let dragging = null;
  const fromPointer = (e) => {
    const r = bar.getBoundingClientRect();
    if (data && r.height > 0) setLayer(layerAtFraction(1 - (e.clientY - r.top) / r.height, data.layers));
  };
  bar.addEventListener('pointerdown', (e) => {
    if (!data) return;
    dragging = e.pointerId;
    bar.setPointerCapture?.(e.pointerId);
    moving = true;
    fromPointer(e);
    invalidate();
    e.preventDefault();
  });
  bar.addEventListener('pointermove', (e) => { if (dragging === e.pointerId) fromPointer(e); });
  const release = (e) => { if (dragging !== e.pointerId) return; dragging = null; moving = false; invalidate(); };
  bar.addEventListener('pointerup', release);
  bar.addEventListener('pointercancel', release);
  bar.addEventListener('keydown', (e) => {
    if (!data) return;
    const to = layerForKey(e.key, k, data.layers);
    if (to === null) return;
    e.preventDefault();
    setLayer(to);
  });

  // ---- the camera
  function bounds() {
    const b = data.ghost.bounds, n = b.length / 6;
    if (!n) return [printer.min[0], printer.min[1], 0, printer.max[0], printer.max[1], data.layerZ[data.layers - 1] || 0];
    const box = [Infinity, Infinity, 0, -Infinity, -Infinity, 0];
    for (let i = 0; i < n; i++) for (let a = 0; a < 3; a++) {
      box[a] = Math.min(box[a], b[i * 6 + a]); box[a + 3] = Math.max(box[a + 3], b[i * 6 + 3 + a]);
    }
    return box;
  }
  function aim(target, dir, distance, lift = 0) {
    const l = Math.hypot(...dir);
    controls.target.set(...target);
    camera.position.set(target[0] + (dir[0] / l) * distance, target[1] + (dir[1] / l) * distance, target[2] + (dir[2] / l) * distance + lift);
    const saved = controls.maxPolarAngle;
    controls.maxPolarAngle = Math.PI / 2;           // a view exactly edge-on is allowed when set
    controls.update();
    controls.maxPolarAngle = saved;
    invalidate();
  }
  // The views the test renders are made from, each framed on the instances (the trial's).
  const VIEWS = {
    default: (box, first, span, c) => aim([c[0], c[1], box[5] / 3], [0.35, -1.05, 0.9], span * 1.6, box[5]),
    top: (box, first, span, c) => aim([c[0], c[1], 0], [0, -0.001, 1], span * 1.55),
    'edge-on': (box, first, span, c) => aim([c[0], c[1], box[5] / 2], [0, -1, 0], span * 1.6),
    'edge-on-side': (box, first, span, c) => aim([c[0], c[1], box[5] / 2], [-1, 0, 0], span * 1.6),
    zoom: (box, f) => aim([(f[0] + f[3]) / 2, (f[1] + f[4]) / 2, f[5] / 2], [0.6, -0.8, 0.7], Math.max(40, (f[3] - f[0]) * 1.4)),
    'zoom-edge-on': (box, f) => aim([(f[0] + f[3]) / 2, f[1], f[5] / 2], [0.3, -1, 0], Math.max(30, (f[3] - f[0]) * 0.9)),
    'zoom-top': (box, f) => aim([(f[0] + f[3]) / 2, (f[1] + f[4]) / 2, f[5]], [0, -0.001, 1], Math.max(30, (f[3] - f[0]) * 0.8)),
  };
  function setView(name) {
    if (!data) return;
    const box = bounds();
    const first = data.ghost.bounds.length ? [...data.ghost.bounds.slice(0, 6)] : box;
    const span = Math.max(box[3] - box[0], box[4] - box[1], 60);
    VIEWS[name](box, first, span, [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2]);
  }

  // ---- the drawing context
  // Builds the drawing from the prepared data; false, after the failure is handled, when it fails.
  function build() {
    try {
      drawing = createDrawing(gl, data, { printer, width, height });
      return true;
    } catch (error) {
      drawing = null;
      fail(errorReport(PREVIEW_FAILED, `the drawing could not be built: ${error && error.message ? error.message : error}`));
      return false;
    }
  }
  canvas.addEventListener('webglcontextlost', (e) => {
    e.preventDefault();
    lost = true;
    drawing = null;
    report('drawing_context_lost', { detail: 'the layer preview lost its 3D drawing context' });
  });
  canvas.addEventListener('webglcontextrestored', () => {
    lost = false;
    if (data && !failed && !build()) return;
    invalidate();
  });

  // ---- showing a sliced file
  let settle = null;        // resolves the show under way
  // Gives back the drawing's objects on the graphics side at once (a lost context has already
  // taken them, and the drawing is then null).
  function letGo() {
    const d = drawing;
    drawing = null;
    if (d) { try { d.dispose(); } catch { /* the context is going: nothing more to give back */ } }
  }
  // A failure of the view: reported once as page_failed (unless `reported`, as the preparation's
  // own failures already are), the drawing and the bar given up, and the caller told, by the
  // show under way or else by onFailure.
  function fail(error, { reported = false } = {}) {
    if (failed) return;
    if (!reported) report('page_failed', { detail: error.code === PREVIEW_FAILED ? error.detail : `${error.code}: ${error.detail}` });
    failed = true;
    letGo(); driver = null; moving = false;
    bar.hidden = true;
    if (frame !== null) frames.cancel(frame);
    frame = null;
    if (settle) { const s = settle; settle = null; s({ ok: false, error }); }
    else onFailure(error);
  }

  // show(bytes, plate, {since}): draws the sliced file `bytes` (an ArrayBuffer); `plate`
  // ({instances, meshes}, each part's corners under the key its instances name) gives the ghost,
  // or null for none; `since` is when the Preview step opened, on the frame seam's clock, from
  // which the first layer is timed (the call itself when left out). Resolves once the first layer
  // is drawn, to {ok: true, layers}, or to {ok: false, error} with an error report, or to
  // {ok: false, stopped: true} when a later show or destroy came first.
  function show(bytes, plate = null, { since: opened = frames.now() } = {}) {
    if (job) job.stop();
    if (settle) { const s = settle; settle = null; s({ ok: false, stopped: true }); }
    letGo();
    data = null; bar.hidden = true; complete = false; firstLayerMs = null; failed = false;
    since = opened;
    stats = createFrameStats();
    if (holds) holds.start();
    const answer = new Promise((resolve) => { settle = resolve; });
    if (!gl) {
      fail(errorReport(PREVIEW_NOT_DRAWABLE, 'the browser gave no WebGL 2 context'));
      return answer;
    }
    job = prepareSlicedFile(startWorker, bytes, plate, { onProgress, report });
    const mine = job;
    mine.done.then((prepared) => {
      if (mine !== job) return;
      job = null;
      if (!prepared.ok) { if (!prepared.stopped) fail(prepared.error, { reported: true }); return; }
      data = prepared.result;
      k = data.layers - 1;
      resize();
      if (!lost && !build()) return;
      setView('default');
      bar.hidden = false;
      showLayer();
      const first = (now, r) => {
        if (r.segments <= 0) return;
        watchers.delete(first);
        firstLayerMs = frames.now() - since;
        if (settle) { const s = settle; settle = null; s({ ok: true, layers: data.layers }); }
      };
      watchers.add(first);
      invalidate();
    });
    return answer;
  }

  // Resolves on the frame that puts the full look on the screen, after `prepare()` has run.
  function untilComplete(prepare = () => {}, read = null) {
    return new Promise((resolve) => {
      const w = (now, r) => {
        if (!r.complete) return;
        watchers.delete(w);
        resolve(read ? read() : now);
      };
      watchers.add(w);
      prepare();
      invalidate();
    });
  }
  function pixels() {
    const px = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, px);
    return { width, height, pixels: px };
  }

  return {
    canvas,
    bar,
    show,
    // The layer shown, from 0, with the plate's layers and its height in millimetres; null
    // before a sliced file is drawn.
    layer: () => (data ? { index: k, layers: data.layers, z: data.layerZ[k] } : null),
    setLayer,
    stepLayer: (d) => setLayer(k + d),
    // Puts the camera back on the instances, as it was when the file was first drawn.
    resetView: () => setView('default'),
    // The drawing summary of this use of the view (contracts/wizard-front-server.md, "POST
    // /api/reports/drawing"), with what the view itself knows; the caller adds the machine's.
    summary() {
      const s = stats.summary();
      return {
        view: 'preview', fps_typical: s.fps_typical, fps_worst: s.fps_worst, first_layer_ms: firstLayerMs,
        longest_hold_ms: holds ? holds.longest() : null,
        instances: data ? data.stats.instances : 0,
        sliced_file_bytes: data ? data.stats.sliced_file_bytes : null,
        sliced_file_lines: data ? data.stats.sliced_file_lines : null,
      };
    },
    // A new use of a view already shown (the Preview step opened again on the same sliced plate,
    // at `opened` on the frame seam's clock): its frame rates and longest hold are measured afresh,
    // and its first layer from that opening to the next frame that draws toolpaths. A view whose
    // sliced file is still being read measures its first use already.
    beginUse(opened = frames.now()) {
      if (!data || failed) return;
      stats = createFrameStats();
      if (holds) holds.start();
      firstLayerMs = null;
      since = opened;
      const first = (now, r) => {
        if (r.segments <= 0) return;
        watchers.delete(first);
        firstLayerMs = frames.now() - since;
      };
      watchers.add(first);
      invalidate();
    },
    // The use ends (the Preview step left, its summary read): the hold meter stops, as the Layout
    // view's does, so that no heartbeat beats while the view is out of sight and the summary keeps
    // this use's longest hold.
    endUse() {
      if (holds) holds.stop();
    },
    // Stops any preparation and drawing, and lets the canvas go.
    destroy() {
      destroyed = true;
      if (job) job.stop();
      job = null;
      if (settle) { const s = settle; settle = null; s({ ok: false, stopped: true }); }
      if (frame !== null) frames.cancel(frame);
      frame = null;
      if (holds) holds.stop();
      observer.disconnect();
      controls.dispose();
      letGo();
      canvas.remove(); bar.remove();
      data = null;
    },

    // ---- for the tests, the renders and the measurements
    views: Object.keys(VIEWS),
    setView: (name) => { setView(name); return untilComplete(); },
    // Whether the full look is on the screen now.
    atRest: () => complete && !moving,
    untilRest: () => untilComplete(),
    // The pixels of the full look, read on the frame that put it on the screen ({width, height,
    // pixels}, RGBA from the bottom row up); with `ghost` false, the same look without the ghost.
    look: ({ ghost = true } = {}) => untilComplete(() => { ghostShown = ghost; }, pixels).then((p) => { ghostShown = true; invalidate(); return p; }),
    // The look while moving, held on the screen until stillAgain().
    showMoving: () => new Promise((resolve) => {
      moving = true;
      const w = (now, r) => { if (r.segments > 0) { watchers.delete(w); resolve(); } };
      watchers.add(w);
      invalidate();
    }),
    stillAgain: () => untilComplete(() => { moving = false; }),
    // A path of `steps` frames, one step each frame as a drag would: `turn`, a full turn about
    // the plate tilting up and down, or `layers`, the bar from the top layer to the first and
    // back. Resolves with the frame times and the time until the full look is back.
    drive(kind, steps) {
      const stamps = [];
      const target = controls.target.clone(), offset = camera.position.clone().sub(target);
      const s = new THREE.Spherical().setFromVector3(new THREE.Vector3(offset.x, offset.z, -offset.y));
      const top = data.layers - 1;
      const step = (i) => {
        if (kind === 'turn') {
          const theta = s.theta + (2 * Math.PI * (i + 1)) / steps;
          const phi = Math.min(Math.PI * 0.49, Math.max(0.15, s.phi + 0.35 * Math.sin((2 * Math.PI * (i + 1)) / steps)));
          const v = new THREE.Vector3().setFromSphericalCoords(s.radius, phi, theta);
          camera.position.set(target.x + v.x, target.y - v.z, target.z + v.y);
          controls.update();
        } else {
          const t = (i + 1) / steps, f = t < 0.5 ? 1 - 2 * t : 2 * t - 1;
          setLayer(Math.round(f * top));
        }
        dirty = true;
      };
      return new Promise((resolve) => {
        let i = 0;
        const w = (now) => stamps.push(now);
        watchers.add(w);
        moving = true;
        driver = () => {
          if (i >= steps) {
            driver = null; watchers.delete(w); moving = false;
            const end = frames.now();
            untilComplete().then(() => {
              const intervals = stamps.slice(1).map((t, n) => t - stamps[n]).sort((a, b) => a - b);
              resolve({ frames: stamps.length, fps_typical: 1000 / intervals[Math.floor(intervals.length / 2)],
                fps_worst: 1000 / intervals.at(-1), frame_ms_worst: intervals.at(-1), rest_ms: frames.now() - end });
            });
            return;
          }
          step(i++);
        };
        invalidate();
      });
    },
    decimate: () => (drawing ? drawing.decimate : null),
    // What the frame loop is doing, for a test that finds it stuck.
    state: () => ({ complete, segments, moving, dirty, more, scheduled: frame !== null, lost, drawing: Boolean(drawing), driving: Boolean(driver), watchers: watchers.size }),
    groups: () => (data ? [...data.groups] : null),
  };
}
