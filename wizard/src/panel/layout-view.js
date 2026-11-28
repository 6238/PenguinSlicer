// The Layout step's 3D view (wizard/README-details.md, "Moving, turning and looking", "Laying an
// instance on a face"): the plate the user works in directly, with no modes. Its gestures are
// the mockup's (docs/mockups/print-wizard/js/layout3d.js), written again against the real parts:
//   select   click an instance; Shift- or Ctrl-click adds or removes it; a click on empty plate
//            clears the selection
//   move     a left drag that starts on an instance; dragging one of a selection moves them all
//   turn     drag the round handle beside the selection; Shift snaps the first selected
//            instance's orientation on the plate to multiples of 45 degrees
//   lay down click a patch of the one selected instance, or double-click a flat face
//   look     right-drag, or left-drag on empty plate, turns the view; Shift-drag, middle-drag or
//            Ctrl with right-drag slides it; the wheel zooms towards the pointer
//   keys     F zooms to the instances, Ctrl+1 looks from above, Ctrl+A selects every instance,
//            Escape clears the selection; no other key does anything here
// The view draws what the layout's model says (layout.js) and tells the layout each change; it
// draws only when something changed, on the frame seam.
import * as THREE from 'three';
import { OrbitControls } from '../../vendor/three/examples/jsm/controls/OrbitControls.js';

import { createHoldMeter } from '../hold-meter.js';
import { PART_COLOURS } from '../page-constants.js';
import * as W from '../layout-sentences.js';
import { createFrameStats } from '../preview/frame-stats.js';

// PenguinCAM's light theme, as the mockup's view has it.
const COL = { background: 0xf2f4f7, accent: 0x2f81f7, danger: 0xd1242f, plate: 0xdde2e8, grid: 0xc7cfd8, grid5: 0xa9b3be, margin: 0x7d8894, volume: 0x9aa5b1, front: 0x8a96a3 };
const PATCH_REST = 0.22;
const PATCH_HOVER = 0.55;
const GAP_PX = 28;           // the rotation handle's distance outside the selection's box
const HANDLE_PX = 7;         // its radius
const DRAG_PX = 4;           // a press that moves less than this is a click
const FLAT_DEG = 1;          // a triangle this near a patch's direction lies on that face
// While the view moves (a drag, a turn, the camera turning), a plate drawing more triangles than
// this draws each part's coarse copy (geometry/coarse.js), each instance's share of the figure:
// without a graphics card Chromium drew about three million triangles a second, and the target
// is 10 frames a second. At rest every part is drawn whole.
const MOVING_TRIANGLES = 250000;
// At rest, a plate of more triangles than this draws coarse copies but for the selected
// instances, so that no frame holds the main thread past its 250 ms.
const REST_TRIANGLES = 500000;
const MIN_COARSE_TRIANGLES = 200;

const quat = ([w, x, y, z]) => new THREE.Quaternion(x, y, z, w);
const aboutZ = (deg) => new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), (deg * Math.PI) / 180);

// The footprint centre (x, y) and the lowest point of the part turned by `lay`: the offset of
// the plate configuration's transform (contracts/plate-configuration.md, "Coordinates").
function offsetOf(positions, lay) {
  const m = new THREE.Matrix4().makeRotationFromQuaternion(quat(lay)).elements;
  let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < positions.length; i += 3) {
    const px = positions[i], py = positions[i + 1], pz = positions[i + 2];
    const x = m[0] * px + m[4] * py + m[8] * pz;
    const y = m[1] * px + m[5] * py + m[9] * pz;
    const z = m[2] * px + m[6] * py + m[10] * pz;
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
    if (z < z0) z0 = z;
  }
  return new THREE.Vector3((x0 + x1) / 2, (y0 + y1) / 2, z0);
}

function makePlate(scene, printer) {
  const [x0, y0] = printer.min;
  const [x1, y1] = printer.max;
  const w = x1 - x0, d = y1 - y0;
  const group = new THREE.Group();
  const bed = new THREE.Mesh(new THREE.BoxGeometry(w, d, 2), new THREE.MeshLambertMaterial({ color: COL.plate }));
  bed.position.set(x0 + w / 2, y0 + d / 2, -1.01);
  group.add(bed);
  const fine = [], coarse = [];
  for (let x = 0; x <= w + 1e-6; x += 10) (Math.round(x) % 50 ? fine : coarse).push(x0 + x, y0, 0.02, x0 + x, y1, 0.02);
  for (let y = 0; y <= d + 1e-6; y += 10) (Math.round(y) % 50 ? fine : coarse).push(x0, y0 + y, 0.02, x1, y0 + y, 0.02);
  for (const [pts, colour] of [[fine, COL.grid], [coarse, COL.grid5]]) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    group.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: colour })));
  }
  const mg = 3;
  const ml = new THREE.BufferGeometry();
  ml.setAttribute('position', new THREE.Float32BufferAttribute([
    x0 + mg, y0 + mg, 0.05, x1 - mg, y0 + mg, 0.05, x1 - mg, y0 + mg, 0.05, x1 - mg, y1 - mg, 0.05,
    x1 - mg, y1 - mg, 0.05, x0 + mg, y1 - mg, 0.05, x0 + mg, y1 - mg, 0.05, x0 + mg, y0 + mg, 0.05], 3));
  const marginLine = new THREE.LineSegments(ml, new THREE.LineDashedMaterial({ color: COL.margin, dashSize: 4, gapSize: 3 }));
  marginLine.computeLineDistances();
  group.add(marginLine);
  const volume = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w, d, printer.height)),
    new THREE.LineBasicMaterial({ color: COL.volume, transparent: true, opacity: 0.5 }));
  volume.position.set(x0 + w / 2, y0 + d / 2, printer.height / 2);
  group.add(volume);
  // a mark at the front, so that "the front edge" has a meaning
  const front = new THREE.Mesh(new THREE.CircleGeometry(5, 3), new THREE.MeshBasicMaterial({ color: COL.front }));
  front.rotation.z = -Math.PI / 2;
  front.position.set(x0 + w / 2, y0 - 8, 0.05);
  group.add(front);
  scene.add(group);
  return group;
}

function lights(scene) {
  scene.add(new THREE.HemisphereLight(0xffffff, 0x3a4450, 2.6));
  const d = new THREE.DirectionalLight(0xffffff, 2.2);
  d.position.set(-200, -300, 500);
  scene.add(d);
  const d2 = new THREE.DirectionalLight(0xffffff, 0.9);
  d2.position.set(400, 500, 200);
  scene.add(d2);
}

// createLayoutView(container, {layout, geometry, frames, partOrder, unitsOf, onSelect}):
//   container  #layout-view, which holds the view buttons
//   layout     the Layout step's behaviour (layout.js)
//   geometry   the worker's client: each part's corners for drawing
//   frames     the frame seam
//   colourOf(partKey)  the part's colour, by its place on the plate
//   software   whether the browser draws 3D in software: then without antialiasing, which costs
//              a software renderer several times the work of each frame
//   clock      the clock seam, for the heartbeat that measures the main thread's longest hold in
//              each use of the view (its drawing summary)
export function createLayoutView(container, { layout, geometry, frames, colourOf, software = false, clock = null }) {
  const canvas = document.createElement('canvas');
  canvas.className = 'gl-canvas';
  canvas.tabIndex = 0;
  canvas.setAttribute('aria-label', 'The plate');
  container.prepend(canvas);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !software });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(COL.background);
  const camera = new THREE.PerspectiveCamera(40, 1, 1, 5000);
  camera.up.set(0, 0, 1);
  lights(scene);

  const tip = document.createElement('div');
  tip.className = 'gl-tip';
  tip.hidden = true;
  container.append(tip);
  const overlay = document.createElement('div');
  overlay.className = 'gl-overlay';
  container.append(overlay);

  canvas.addEventListener('pointerdown', onDown, true);
  canvas.addEventListener('wheel', onWheel, { capture: true, passive: false });
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = false;
  controls.rotateSpeed = 0.55;
  controls.screenSpacePanning = true;
  controls.maxPolarAngle = Math.PI * 0.49;
  // the mouse as in Onshape (M2): right-drag and a left-drag on empty plate look around,
  // middle-drag slides; OrbitControls slides on Shift-drag and Ctrl with a right-drag
  controls.mouseButtons = { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.PAN, RIGHT: THREE.MOUSE.ROTATE };
  controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
  controls.addEventListener('change', invalidate);

  let printer = null;
  let plateGroup = null;
  let model = layout.model();
  const geometries = new Map();     // part key -> BufferGeometry
  const offsets = new Map();        // part key + lay -> offset
  const meshes = new Map();         // instance id -> Mesh
  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let drag = null;
  let hoverKey = null;
  let patches = null;               // {id, part, list: [{mesh, patch}], group}
  let hoverPatch = -1;
  let lastHandle = null;
  let handleAngle = Math.PI / 2;
  let sized = false;
  let fitted = false;

  const disc = new THREE.Mesh(new THREE.CircleGeometry(1, 24), new THREE.MeshBasicMaterial({ color: COL.accent, depthTest: false, transparent: true }));
  const ring = new THREE.Mesh(new THREE.RingGeometry(1.25, 1.6, 32), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.8, depthTest: false }));
  disc.renderOrder = 10;
  ring.renderOrder = 10;
  const handle = new THREE.Group();
  handle.add(disc, ring);
  const stemGeometry = new THREE.BufferGeometry();
  stemGeometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 1, 0, 0], 3));
  const stem = new THREE.Line(stemGeometry, new THREE.LineBasicMaterial({ color: COL.accent, depthTest: false, transparent: true }));
  stem.renderOrder = 9;
  const selBox = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineDashedMaterial({ color: COL.accent, dashSize: 3, gapSize: 2 }));
  scene.add(handle, stem, selBox);

  // ---- drawing, only when something changed
  let needs = true;
  let frame = null;
  let drawn = 0;
  function invalidate() {
    needs = true;
    if (frame === null) frame = frames.next(loop);
  }
  function loop() {
    frame = null;
    if (!needs || !container.offsetParent) return;
    needs = false;
    placeOverlays();
    renderer.render(scene, camera);
    drawn += 1;
    stats.frame(frames.now(), moving);
  }

  // ---- its drawing summary: the frames drawn while the view moves (a drag, a turn, the camera
  // turning) and the main thread's longest hold, for each use of the view, measured as the layer
  // preview measures its own (preview/frame-stats.js, hold-meter.js)
  let stats = createFrameStats();
  const holds = clock ? createHoldMeter(clock) : null;
  let using = false;

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (!sized && printer) { sized = true; viewPlate(); }
    invalidate();
  }
  new ResizeObserver(resize).observe(container);

  // ---- the meshes follow the model
  function geometryOf(key) {
    if (geometries.has(key)) return geometries.get(key);
    const mesh = geometry.mesh(key);
    if (!mesh) return null;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(mesh.positions, 3));
    g.computeVertexNormals();
    g.computeBoundingSphere();
    geometries.set(key, g);
    return g;
  }

  // ---- the coarse copies drawn while the view moves, and at rest on a plate too heavy to draw
  // whole within the main thread's 250 ms
  const coarse = new Map();          // "key|budget" -> BufferGeometry, or null while asked for
  let moving = false;
  function budget(total) {
    const n = Math.max(1, model.instances.length);
    const share = Math.floor(total / n);
    // in steps of a power of two, so that a quantity changed by one asks for no new copies
    return Math.max(MIN_COARSE_TRIANGLES, 2 ** Math.floor(Math.log2(Math.max(1, share))));
  }
  function wholeTriangles() {
    let t = 0;
    for (const i of model.instances) { const m = geometry.mesh(i.part); if (m) t += m.positions.length / 9; }
    return t;
  }
  function coarseOf(key, total) {
    const b = budget(total);
    const id = `${key}|${b}`;
    if (coarse.has(id)) return coarse.get(id);
    coarse.set(id, null);
    geometry.coarse(key, b).then((answer) => {
      if (!answer.ok) return;
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(answer.result.positions, 3));
      g.computeVertexNormals();
      g.computeBoundingSphere();
      coarse.set(id, g);
      showMoving(moving);
    });
    return null;
  }
  // Each mesh's drawing: whole, unless the plate is over the figure for the moment (moving or at
  // rest), when each instance draws its part's coarse copy; at rest the selected ones stay whole.
  function showMoving(on) {
    moving = on;
    const total = on ? MOVING_TRIANGLES : REST_TRIANGLES;
    const coarseNeeded = wholeTriangles() > total;
    for (const mesh of meshes.values()) {
      const instance = model.instances.find((i) => i.id === mesh.userData.id);
      if (!instance) continue;
      const whole = !coarseNeeded || (!on && model.selected.includes(instance.id));
      const g = whole ? null : coarseOf(instance.part, total);
      mesh.geometry = g || geometries.get(instance.part) || mesh.geometry;
      // at rest, an instance whose coarse copy has not arrived yet waits for it, rather than
      // holding the page with its whole part
      mesh.visible = whole || Boolean(g) || on;
    }
    invalidate();
  }
  controls.addEventListener('start', () => showMoving(true));
  controls.addEventListener('end', () => showMoving(false));

  function offsetFor(instance) {
    const key = `${instance.part}|${instance.lay.join(',')}`;
    if (!offsets.has(key)) {
      const mesh = geometry.mesh(instance.part);
      offsets.set(key, mesh ? offsetOf(mesh.positions, instance.lay) : new THREE.Vector3());
      if (offsets.size > 2000) offsets.delete(offsets.keys().next().value);
    }
    return offsets.get(key);
  }

  // Where the mesh goes: turned by Rz(angle) M, its footprint centre at (x, y), its lowest
  // point on the plate. The mesh moves before the frame is drawn, so the handle and the
  // selection box never lead it.
  function placeMesh(mesh, instance) {
    const turn = aboutZ(instance.angle);
    mesh.quaternion.copy(turn).multiply(quat(instance.lay));
    const off = offsetFor(instance).clone().applyQuaternion(turn);
    mesh.position.set(instance.x - off.x, instance.y - off.y, -off.z);
  }

  function setPrinter(p) {
    const same = printer && p && printer.min.join() === p.min.join() && printer.max.join() === p.max.join() && printer.height === p.height;
    if (same || !p) return;
    if (plateGroup) scene.remove(plateGroup);
    printer = p;
    plateGroup = makePlate(scene, p);
    if (!sized) resize();
  }

  function sync(next = layout.model()) {
    model = next;
    if (model.printer) setPrinter(model.printer);
    const live = new Set();
    for (const instance of model.instances) {
      const g = geometryOf(instance.part);
      if (!g) continue;
      live.add(instance.id);
      let mesh = meshes.get(instance.id);
      if (!mesh) {
        mesh = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color: colourOf(instance.part), flatShading: true }));
        mesh.userData.id = instance.id;
        meshes.set(instance.id, mesh);
        scene.add(mesh);
      }
      if (!(drag && drag.moving && drag.ids.has(instance.id))) placeMesh(mesh, instance);
      const bad = model.marked.has(instance.id);
      const sel = model.selected.includes(instance.id);
      mesh.material.color.set(bad ? COL.danger : colourOf(instance.part));
      mesh.material.emissive.set(sel ? (bad ? 0x3a0000 : 0x0b2a5c) : 0x000000);
    }
    for (const [id, mesh] of meshes) {
      if (live.has(id)) continue;
      scene.remove(mesh);
      mesh.material.dispose();
      meshes.delete(id);
    }
    if (!fitted && model.instances.length && sized) { fitted = true; zoomToInstances(); }
    // the coarse copies asked for ahead of the first drag, where the plate will need them
    if (wholeTriangles() > MOVING_TRIANGLES) for (const key of new Set(model.instances.map((i) => i.part))) coarseOf(key, MOVING_TRIANGLES);
    if (!drag) showMoving(moving);
    else invalidate();
  }

  // ---- the camera
  function lookAt(cx, cy, w, l, tall, above) {
    const aspect = Math.max(0.5, camera.aspect || 1);
    const half = Math.tan((camera.fov * Math.PI) / 360);
    if (above) {
      const fit = Math.max(l + 20, (w + 20) / aspect);
      const d0 = (fit / (2 * half)) * 1.04;
      controls.target.set(cx, cy, 0);
      camera.position.set(cx, cy - d0 * 0.0005, d0 + tall * 0.5);
    } else {
      controls.target.set(cx, cy, Math.min(tall, 60) / 3);
      const fitH = l * 0.75 + tall * 0.7 + 30, fitW = (w + 30) / aspect;
      const dist = (Math.max(fitH, fitW) / (2 * half)) * 1.08;
      camera.position.set(cx, cy - dist * 0.5, controls.target.z + dist * 0.866);
    }
    controls.update();
    invalidate();
  }
  function boxOf(list) {
    const b = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity, tall: 0 };
    for (const i of list) {
      if (!i.bounds) continue;
      b.x0 = Math.min(b.x0, i.bounds[0]); b.y0 = Math.min(b.y0, i.bounds[1]);
      b.x1 = Math.max(b.x1, i.bounds[2]); b.y1 = Math.max(b.y1, i.bounds[3]);
      b.tall = Math.max(b.tall, Math.min(i.height ?? 0, printer ? printer.height : 340));
    }
    return Number.isFinite(b.x0) ? b : null;
  }
  // The whole plate, widened to take in any instance waiting beside it.
  function viewPlate(above = false) {
    if (!printer) return;
    const b = boxOf(model.instances);
    const x0 = Math.min(printer.min[0], b ? b.x0 : Infinity), x1 = Math.max(printer.max[0], b ? b.x1 : -Infinity);
    const y0 = Math.min(printer.min[1], b ? b.y0 : Infinity), y1 = Math.max(printer.max[1], b ? b.y1 : -Infinity);
    lookAt((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0 + 50, y1 - y0 + 30, 0, above);
  }
  function zoomToInstances(above = false) {
    const b = boxOf(model.instances);
    if (!b || !printer) { viewPlate(above); return; }
    const w = Math.max(120, b.x1 - b.x0 + 50), l = Math.max(100, b.y1 - b.y0 + 50);
    if (w >= printer.max[0] - printer.min[0] || l >= printer.max[1] - printer.min[1]) { viewPlate(above); return; }
    lookAt((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2, w, l, b.tall, above);
  }
  const topView = () => zoomToInstances(true);

  function onWheel(e) {
    e.preventDefault();
    e.stopImmediatePropagation();
    setRay(e);
    let p = planePoint(0);
    if (!p || p.distanceTo(camera.position) > 3000) p = controls.target.clone();
    const dist = camera.position.distanceTo(p);
    let s = 1.0018 ** Math.max(-300, Math.min(300, e.deltaY));
    const nd = Math.min(2600, Math.max(30, dist * s));
    s = nd / Math.max(1e-6, dist);
    camera.position.sub(p).multiplyScalar(s).add(p);
    controls.target.sub(p).multiplyScalar(s).add(p);
    controls.update();
    invalidate();
  }

  // ---- picking
  function setRay(e) {
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
  }
  function planePoint(z) {
    const p = new THREE.Vector3();
    return raycaster.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 0, 1), -z), p) ? p : null;
  }
  function hitInstance() {
    const hits = raycaster.intersectObjects([...meshes.values()], false);
    return hits.length ? hits[0] : null;
  }
  // A press through a hole of an instance (a pulley's bore) still means that instance: the one
  // whose footprint's box the pointer is over, at the plate, half way up or at its top.
  function hitFootprint() {
    let best = null;
    for (const i of model.instances) {
      if (!i.bounds) continue;
      for (const z of [0, (i.height ?? 0) / 2, i.height ?? 0]) {
        const p = planePoint(z);
        if (p && p.x >= i.bounds[0] && p.x <= i.bounds[2] && p.y >= i.bounds[1] && p.y <= i.bounds[3]) {
          const d = p.distanceTo(camera.position);
          if (!best || d < best.d) best = { id: i.id, d, z };
          break;
        }
      }
    }
    return best;
  }
  function hitHandle() {
    return handle.visible && (raycaster.intersectObject(disc, false).length > 0 || raycaster.intersectObject(ring, false).length > 0);
  }
  function hitPatch() {
    if (!patches || !patches.group.visible) return null;
    const mesh = meshes.get(patches.id);
    if (!mesh) return null;
    mesh.updateMatrixWorld(true);
    const visible = patches.list.filter((p) => p.mesh.visible).map((p) => p.mesh);
    const h = raycaster.intersectObjects(visible, false)[0];
    if (!h) return null;
    const front = hitInstance();
    if (front && front.object !== mesh && front.distance < h.distance - 0.5) return null;
    return { i: h.object.userData.patch, patch: patches.list[h.object.userData.patch].patch, id: patches.id };
  }

  // ---- the patches of the one selected instance
  function clearPatches() {
    if (!patches) return;
    patches.group.parent?.remove(patches.group);
    for (const p of patches.list) { p.mesh.geometry.dispose(); p.mesh.material.dispose(); }
    patches = null;
    hoverPatch = -1;
  }
  let asking = null;
  function wantPatches(one) {
    if (patches && patches.id === one.id && patches.part === one.part && patches.lay === one.lay.join()) return;
    if (asking === one.id) return;
    asking = one.id;
    layout.patches(one.id).then((list) => {
      asking = null;
      const now = model.selected.length === 1 ? model.instances.find((i) => i.id === model.selected[0]) : null;
      if (!now || now.id !== one.id) return;
      clearPatches();
      const group = new THREE.Group();
      const entries = list.map((patch, n) => {
        const pts = [];
        const o = patch.outline;
        const lift = 0.15;
        for (let k = 1; k < o.length - 1; k++) {
          for (const q of [o[0], o[k], o[k + 1]]) pts.push(q[0] + patch.normal[0] * lift, q[1] + patch.normal[1] * lift, q[2] + patch.normal[2] * lift);
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
        const mesh = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: COL.accent, transparent: true, opacity: PATCH_REST, depthWrite: false, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
        mesh.renderOrder = 3;
        mesh.userData.patch = n;
        group.add(mesh);
        return { mesh, patch };
      });
      meshes.get(one.id)?.add(group);
      patches = { id: one.id, part: one.part, lay: now.lay.join(), group, list: entries };
      invalidate();
    }, () => { asking = null; });
  }
  function showPatches(one, moving) {
    if (!one || !meshes.has(one.id)) { clearPatches(); return; }
    wantPatches(one);
    if (!patches || patches.id !== one.id) return;
    const mesh = meshes.get(one.id);
    mesh.updateMatrixWorld(true);
    const eye = camera.position;
    for (const [n, p] of patches.list.entries()) {
      const wn = new THREE.Vector3(...p.patch.normal).applyQuaternion(mesh.quaternion);
      const c = p.patch.outline.reduce((s, q) => s.add(new THREE.Vector3(...q)), new THREE.Vector3()).divideScalar(p.patch.outline.length).applyMatrix4(mesh.matrixWorld);
      // only the patches in sight; the face it lies on has none
      p.mesh.visible = wn.z > -0.999 && wn.dot(eye.clone().sub(c)) > 0;
      p.mesh.material.opacity = n === hoverPatch ? PATCH_HOVER : PATCH_REST;
    }
    patches.group.visible = !moving;
  }

  // ---- the rotation handle and the selection's box
  const selectedInstances = () => model.instances.filter((i) => model.selected.includes(i.id));
  function selectionBox() {
    const b = boxOf(selectedInstances());
    if (!b) return null;
    return { ...b, cx: (b.x0 + b.x1) / 2, cy: (b.y0 + b.y1) / 2 };
  }
  function toPx(v) {
    const p = v.clone().project(camera);
    return { x: ((p.x + 1) / 2) * container.clientWidth, y: ((1 - p.y) / 2) * container.clientHeight };
  }
  function pxSize(b) {
    const dist = camera.position.distanceTo(new THREE.Vector3(b.cx, b.cy, 0));
    return (dist * Math.tan((camera.fov * Math.PI) / 360) * 2) / Math.max(1, container.clientHeight);
  }
  // Whether a patch in sight is under the handle (or close round it) were it at `end`.
  function patchUnder(end, r) {
    if (!patches || !patches.group.visible) return false;
    const saved = raycaster.ray.clone();
    let under = false;
    const v = new THREE.Vector2();
    for (let k = -1; k < 8 && !under; k++) {
      const p = end.clone();
      if (k >= 0) { p.x += Math.cos((k * Math.PI) / 4) * 2.2 * r; p.y += Math.sin((k * Math.PI) / 4) * 2.2 * r; }
      p.project(camera);
      v.set(p.x, p.y);
      raycaster.setFromCamera(v, camera);
      under = Boolean(hitPatch());
    }
    raycaster.ray.copy(saved);
    return under;
  }
  function placeHandle() {
    const b = drag && drag.type === 'turn' ? drag.box : selectionBox();
    handle.visible = stem.visible = selBox.visible = Boolean(b);
    if (!b) { lastHandle = null; return null; }
    const px = pxSize(b);
    const r = HANDLE_PX * px;
    const at = (a) => {
      const dx = Math.cos(a), dy = Math.sin(a);
      const reach = (Math.abs(dx) * (b.x1 - b.x0)) / 2 + (Math.abs(dy) * (b.y1 - b.y0)) / 2;
      return { a, end: new THREE.Vector3(b.cx + dx * (reach + GAP_PX * px), b.cy + dy * (reach + GAP_PX * px), 0.4) };
    };
    let spot;
    if (drag && drag.type === 'turn') {
      // on the circle the press fixed, turned through the same angle as the selection
      const a = drag.h0 + drag.turnRad;
      spot = { a, end: new THREE.Vector3(drag.pivot.x + Math.cos(a) * drag.R0, drag.pivot.y + Math.sin(a) * drag.R0, 0.4) };
    } else {
      spot = at(handleAngle);
      // out of the way of the patches in sight, only while no drag is going on
      if (patchUnder(spot.end, r)) {
        const a0 = spot.a;
        spot = null;
        for (let k = 1; k < 8 && !spot; k++) { const s = at(a0 + (k * Math.PI) / 4); if (!patchUnder(s.end, r)) spot = s; }
        if (!spot) { handle.visible = stem.visible = false; lastHandle = null; return null; }
        handleAngle = spot.a;
      }
    }
    const { end } = spot;
    const dx = Math.cos(spot.a), dy = Math.sin(spot.a);
    const edge = new THREE.Vector3(end.x - dx * GAP_PX * px, end.y - dy * GAP_PX * px, 0.4);
    lastHandle = { end: end.clone(), a: spot.a, pivot: new THREE.Vector2(b.cx, b.cy), box: b };
    handle.position.copy(end);
    handle.scale.setScalar(r);
    const sp = stem.geometry.attributes.position;
    sp.setXYZ(0, edge.x, edge.y, edge.z);
    sp.setXYZ(1, end.x, end.y, end.z);
    sp.needsUpdate = true;
    stem.geometry.computeBoundingSphere();
    if (!(drag && drag.type === 'turn')) {
      const z = 0.3;
      selBox.geometry.setAttribute('position', new THREE.Float32BufferAttribute([
        b.x0, b.y0, z, b.x1, b.y0, z, b.x1, b.y0, z, b.x1, b.y1, z, b.x1, b.y1, z, b.x0, b.y1, z, b.x0, b.y1, z, b.x0, b.y0, z], 3));
      selBox.computeLineDistances();
    }
    selBox.visible = !(drag && drag.type === 'turn');
    return { end: toPx(end) };
  }

  function placeOverlays() {
    const moving = Boolean(drag && drag.moved && (drag.type === 'move' || drag.type === 'turn'));
    const one = model.selected.length === 1 ? model.instances.find((i) => i.id === model.selected[0]) : null;
    showPatches(one, moving);
    const hp = placeHandle();
    overlay.replaceChildren();
    if (hp && drag && drag.type === 'turn' && drag.moved) {
      const readout = document.createElement('span');
      readout.className = 'turn-readout';
      readout.textContent = W.turnReadout(drag.first0 + drag.turnDeg);
      readout.style.left = `${hp.end.x + 14}px`;
      readout.style.top = `${hp.end.y - 22}px`;
      overlay.append(readout);
    }
  }

  // ---- the pointer
  function onDown(e) {
    if (e.button !== 0) return;          // the middle and right buttons belong to the camera
    const mod = e.shiftKey || e.ctrlKey || e.metaKey;
    setRay(e);
    canvas.focus();
    const base = { sx: e.clientX, sy: e.clientY, moved: false, mod };
    const take = (d) => {
      e.preventDefault();
      controls.enabled = false;
      drag = Object.assign(base, d);
      canvas.setPointerCapture?.(e.pointerId);
    };
    if (hitHandle() && lastHandle) {
      const sel = selectedInstances();
      const p0 = planePoint(0.4) || lastHandle.end;
      take({
        type: 'turn', pivot: lastHandle.pivot.clone(), box: lastHandle.box, h0: lastHandle.a,
        a0: Math.atan2(p0.y - lastHandle.pivot.y, p0.x - lastHandle.pivot.x), prevA: null, raw: 0, turnRad: 0, turnDeg: 0,
        R0: Math.hypot(lastHandle.end.x - lastHandle.pivot.x, lastHandle.end.y - lastHandle.pivot.y), shift: e.shiftKey,
        first0: sel.length ? layout.plateAngle(sel[0].id) : 0,
        start: sel.map((i) => ({ id: i.id, x: i.x, y: i.y, angle: i.angle })), ids: new Set(sel.map((i) => i.id)),
      });
      return;
    }
    const patch = hitPatch();
    if (patch) {
      take(moveFrom(patch.id, 0, false));
      drag.patch = patch;
      return;
    }
    const hit = hitInstance();
    const near = hit ? null : hitFootprint();
    if (!hit && !near) { drag = Object.assign(base, { type: 'empty' }); return; }   // the camera takes it
    const id = hit ? hit.object.userData.id : near.id;
    if (mod) layout.select(id, 'toggle');
    else if (!model.selected.includes(id)) layout.select(id, 'only');
    take(moveFrom(id, hit ? hit.point.z : near.z, true));
  }
  function moveFrom(id, z) {
    const sel = layout.model().instances.filter((i) => layout.model().selected.includes(i.id));
    const list = sel.length && sel.some((i) => i.id === id) ? sel : layout.model().instances.filter((i) => i.id === id);
    return { type: 'move', id, z, p0: planePoint(z), start: list.map((i) => ({ id: i.id, x: i.x, y: i.y })), ids: new Set(list.map((i) => i.id)) };
  }

  function applyTurn(d) {
    if (d.lastA === undefined) return;
    if (d.prevA === null) d.prevA = d.a0;
    let da = d.lastA - d.prevA;
    while (da > Math.PI) da -= 2 * Math.PI;
    while (da < -Math.PI) da += 2 * Math.PI;
    d.raw += da;
    d.prevA = d.lastA;
    let deg = (d.raw * 180) / Math.PI;
    // Shift: the first selected instance's orientation on the plate to a multiple of 45 degrees
    if (d.shift) deg = Math.round((d.first0 + deg) / 45) * 45 - d.first0;
    d.turnDeg = deg;
    d.turnRad = (deg * Math.PI) / 180;
    const c = Math.cos(d.turnRad), s = Math.sin(d.turnRad);
    // each instance turns rigidly about the pivot: its footprint centre round the pivot, its
    // angle by the same amount
    const moves = d.start.map((st) => {
      const vx = st.x - d.pivot.x, vy = st.y - d.pivot.y;
      return { id: st.id, x: d.pivot.x + vx * c - vy * s, y: d.pivot.y + vx * s + vy * c, angle: st.angle + deg };
    });
    layout.place(moves);
    model = layout.model();
    for (const m of moves) {
      const mesh = meshes.get(m.id);
      const instance = model.instances.find((i) => i.id === m.id);
      if (mesh && instance) placeMesh(mesh, instance);
    }
    invalidate();
  }

  canvas.addEventListener('pointermove', (e) => {
    setRay(e);
    if (drag && drag.type !== 'empty') {
      if (Math.abs(e.clientX - drag.sx) + Math.abs(e.clientY - drag.sy) > DRAG_PX) drag.moved = true;
      if (!drag.moved) return;
      if (!moving) showMoving(true);
      if (drag.type === 'move') {
        const p = planePoint(drag.z);
        if (!p || !drag.p0) return;
        const dx = p.x - drag.p0.x, dy = p.y - drag.p0.y;
        drag.moving = true;
        const moves = drag.start.map((st) => ({ id: st.id, x: st.x + dx, y: st.y + dy }));
        layout.place(moves);
        model = layout.model();
        for (const m of moves) {
          const mesh = meshes.get(m.id);
          const instance = model.instances.find((i) => i.id === m.id);
          if (mesh && instance) placeMesh(mesh, instance);
        }
        invalidate();
      } else if (drag.type === 'turn') {
        const q = planePoint(0.4);
        if (!q) return;
        drag.lastA = Math.atan2(q.y - drag.pivot.y, q.x - drag.pivot.x);
        drag.shift = e.shiftKey;
        drag.moving = true;
        applyTurn(drag);
      }
      return;
    }
    if (drag) return;
    hover();
  });

  function onShift(e) {
    if (e.key !== 'Shift' || !drag || drag.type !== 'turn' || !drag.moved) return;
    drag.shift = e.type === 'keydown';
    applyTurn(drag);
  }
  window.addEventListener('keydown', onShift);
  window.addEventListener('keyup', onShift);

  function hover() {
    let key = null, cursor = 'default', text = null;
    let patch = null;
    if (hitHandle()) { key = 'handle'; cursor = 'grab'; text = W.POINTER_HANDLE; }
    else if ((patch = hitPatch())) {
      key = `patch${patch.i}`;
      cursor = 'pointer';
      text = W.POINTER_PATCH(patch.patch.kind, patch.patch.height, model.instances.find((i) => i.id === patch.id).part.split('.')[1]);
    } else {
      const hit = hitInstance();
      const near = hit ? null : hitFootprint();
      const id = hit ? hit.object.userData.id : near ? near.id : null;
      if (id !== null) { key = `instance:${id}`; cursor = 'move'; text = model.instances.find((i) => i.id === id)?.label ?? null; }
    }
    const hp = patch ? patch.i : -1;
    if (hp !== hoverPatch) { hoverPatch = hp; invalidate(); }
    canvas.style.cursor = cursor;
    if (key !== hoverKey) {
      hoverKey = key;
      tip.textContent = text ?? '';
      tip.hidden = !text;
    }
  }

  canvas.addEventListener('pointerup', (e) => {
    const d = drag;
    drag = null;
    controls.enabled = true;
    if (moving) showMoving(false);
    if (!d) return;
    const still = !d.moved && Math.abs(e.clientX - d.sx) + Math.abs(e.clientY - d.sy) <= DRAG_PX;
    if (d.type === 'empty') { if (still && !d.mod) layout.clearSelection(); return; }
    if (d.type === 'move' && d.patch && still) {
      hoverKey = null; hoverPatch = -1; tip.hidden = true;
      layout.layOnNormal(d.patch.id, d.patch.patch.normal);
      return;
    }
    if (d.type === 'turn' && d.moved) handleAngle = d.h0 + d.turnRad;
    if (d.type === 'move' && still && !d.mod) layout.select(d.id, 'only');
    if (d.moved) layout.endDrag();
    invalidate();
  });
  canvas.addEventListener('pointercancel', () => { if (drag && drag.moved) layout.endDrag(); drag = null; controls.enabled = true; });

  // A double-click on a flat face lays the instance down on it: the face of a patch the
  // triangle under the pointer lies on.
  canvas.addEventListener('dblclick', (e) => {
    setRay(e);
    const hit = hitInstance();
    if (!hit || !hit.face) return;
    e.preventDefault();
    const id = hit.object.userData.id;
    const n = hit.face.normal.clone().normalize();
    layout.patches(id).then((list) => {
      const cos = Math.cos((FLAT_DEG * Math.PI) / 180);
      const match = list.find((p) => p.kind === 'hull' && n.x * p.normal[0] + n.y * p.normal[1] + n.z * p.normal[2] > cos);
      if (match) layout.layOnNormal(id, match.normal);
    });
  });
  canvas.addEventListener('pointerleave', () => {
    if (drag) return;
    tip.hidden = true;
    hoverKey = null;
    if (hoverPatch !== -1) { hoverPatch = -1; invalidate(); }
  });
  // The four keys of the step; Delete, Ctrl+D, Ctrl+Z and Ctrl+Y do nothing here.
  canvas.addEventListener('keydown', (e) => {
    const mod = e.ctrlKey || e.metaKey;
    if (e.key === 'Escape') { layout.clearSelection(); return; }
    if (mod && (e.key === 'a' || e.key === 'A')) { e.preventDefault(); layout.selectAll(); return; }
    if (mod && e.key === '1') { e.preventDefault(); topView(); return; }
    if (!mod && (e.key === 'f' || e.key === 'F')) { e.preventDefault(); zoomToInstances(); }
  });

  layout.subscribe(() => { if (!drag || !drag.moving) sync(); });
  sync();

  // ---- for the tests and the measurements: where things are on the page
  const pagePx = (v) => { const r = canvas.getBoundingClientRect(); const s = toPx(v); return { x: r.left + s.x, y: r.top + s.y }; };
  return {
    canvas,
    renderer,
    sync,
    resize,
    invalidate,
    zoomToInstances,
    viewPlate,
    topView,
    frames: () => drawn,
    // A use of the view begins (the Layout step shown): its frame rates and longest hold are
    // measured afresh.
    beginUse() {
      stats = createFrameStats();
      if (holds) holds.start();
      using = true;
    },
    // The use ends (the step left): the drawing summary of it (contracts/wizard-front-server.md,
    // "POST /api/reports/drawing"), with what the view itself knows; the caller adds the
    // machine's. Null when no use was begun.
    endUse() {
      if (!using) return null;
      using = false;
      const s = stats.summary();
      return {
        view: 'layout', fps_typical: s.fps_typical, fps_worst: s.fps_worst,
        longest_hold_ms: holds ? holds.stop() : null, instances: model.instances.length,
      };
    },
    // The picture drawn now, read back at once (the drawing buffer is not kept between frames):
    // {width, height, pixels}, RGBA from the bottom row up.
    snapshot() {
      placeOverlays();
      renderer.render(scene, camera);
      const gl = renderer.getContext();
      const width = gl.drawingBufferWidth, height = gl.drawingBufferHeight;
      const pixels = new Uint8Array(width * height * 4);
      gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      return { width, height, pixels };
    },
    // an instance's footprint centre, half way up, on the page
    screenOf(id) {
      const i = model.instances.find((n) => n.id === id);
      return i ? pagePx(new THREE.Vector3(i.x, i.y, (i.height ?? 0) / 2)) : null;
    },
    // a point of the plate on the page
    plateAt: (x, y) => pagePx(new THREE.Vector3(x, y, 0)),
    handleAt: () => (handle.visible && lastHandle ? pagePx(handle.position) : null),
    // the handle's distance from the pivot and its angle, while a turn goes on
    handleCircle: () => (lastHandle ? { r: Math.hypot(handle.position.x - lastHandle.pivot.x, handle.position.y - lastHandle.pivot.y), a: Math.atan2(handle.position.y - lastHandle.pivot.y, handle.position.x - lastHandle.pivot.x) } : null),
    // the patches in sight of the selected instance: each one's middle on the page and whether
    // a press there takes it
    patchesInSight() {
      if (!patches || !patches.group.visible) return [];
      const mesh = meshes.get(patches.id);
      mesh.updateMatrixWorld(true);
      return patches.list.map((p, n) => {
        if (!p.mesh.visible) return null;
        const c = p.patch.outline.reduce((s, q) => s.add(new THREE.Vector3(...q)), new THREE.Vector3()).divideScalar(p.patch.outline.length).applyMatrix4(mesh.matrixWorld);
        const at = pagePx(c);
        setRay({ clientX: at.x, clientY: at.y });
        const h = hitHandle() ? null : hitPatch();
        return { i: n, x: at.x, y: at.y, kind: p.patch.kind, height: p.patch.height, pickable: Boolean(h && h.i === n) };
      }).filter(Boolean);
    },
    pointerLine: () => (tip.hidden ? '' : tip.textContent),
  };
}
