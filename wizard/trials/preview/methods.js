// The page's half of each candidate method: how it draws what its worker half prepared.
// Every method draws each segment as a box (prepare.js, "the boxes' vertices"); they differ in
// what they draw while the view moves and in how they spread the drawing over frames.
import { program, buffer, COLOURS, LIGHT, BACKGROUND } from './viewer.js';
import { fullPieces } from './prepare.js';

/* ---------------------------------------------------------------- the boxes
 * A box is as wide as its line and as tall as its layer, its ends pushed out by half its width
 * so the boxes of a path overlap at the corners. Two of its faces are drawn: the top (the
 * bottom, seen from under it) and the long side towards the camera. Stacked layers so make a
 * closed surface, which shows no combs and nothing behind it. A box is never narrower than
 * `minPx` pixels (1; 2 for the current layer, which is also unshaded). Walls' sides are
 * darkened by the way they face the light, never lightened. Software drawing in this browser
 * is slow for instanced drawing (the first measurement in the record), so each box is six
 * vertices of its own, drawn in batches of BATCH boxes with 16-bit indices. */
const BOX_VS = `#version 300 es
precision highp float;
in vec3 aPos; in vec2 aNrm; in vec2 aWH; in float aFlags;
uniform mat4 viewProj;
uniform vec3 camPos;
uniform float pxPerUnit, minPx, current;
uniform vec2 light;
uniform vec3 colours[4];
flat out vec3 vColour;
void main() {
  vec3 base = aPos * 0.01;
  float w = aWH.x * 0.01, h = aWH.y * 0.02;
  int flags = int(aFlags + 0.5), g = flags & 3, role = (flags >> 2) & 3;
  vec2 n = aNrm / max(length(aNrm), 1e-6);
  float side = dot(n, camPos.xy - base.xy) >= 0.0 ? 1.0 : -1.0;
  vec4 c0 = viewProj * vec4(base, 1.0);
  float ppu = pxPerUnit / max(c0.w, 1e-3);
  float halfW = 0.5 * max(w, minPx / ppu);
  float hh = current > 0.5 ? max(h, minPx / ppu) : h * 1.04;     // a little overlap closes cracks
  bool under = camPos.z < base.z - hh;
  // Lines of one layer overlap where Orca lays infill and surfaces over the walls' edge. Their
  // tops lying at one height would fight in the depth buffer and speckle; the walls' tops sit
  // 0.01 mm higher, so the walls' smooth edge is drawn over the ends of the lines that meet
  // them, the same at every angle.
  float lift = (g == 0 && !under) ? 0.01 : 0.0;
  float zFace = under ? base.z - hh : base.z + lift, zOther = under ? base.z : base.z - hh;
  vec3 pos;
  if (role == 0) pos = vec3(base.xy + n * side * halfW, zFace);
  else if (role == 1) pos = vec3(base.xy - n * side * halfW, zFace);
  else pos = vec3(base.xy + n * side * halfW, zOther);
  vec3 c = colours[g];
  if (g == 0 && role == 2 && current < 0.5) c *= 0.66 + 0.34 * (0.5 + 0.5 * dot(n * side, light));
  vColour = c;
  gl_Position = viewProj * vec4(pos, 1.0);
}`;
const BOX_FS = `#version 300 es
precision mediump float;
flat in vec3 vColour; out vec4 o;
void main() { o = vec4(vColour, 1.0); }`;
const VERTEX_BYTES = 12, SEGMENT_BYTES = 72, BATCH = Math.floor(65536 / 6);
const UPLOAD_BYTES = 8 * 1024 * 1024;

function boxIndex() {
  const idx = new Uint16Array(BATCH * 12);
  for (let i = 0; i < BATCH; i++) {
    const b = i * 6;
    // the top: provoking vertex 2 (the far top edge); the near side: provoking vertex 4
    idx.set([b, b + 1, b + 2, b + 1, b + 3, b + 2, b, b + 1, b + 4, b + 1, b + 5, b + 4], i * 12);
  }
  return idx;
}

// One set of boxes (prepare.js boxVertices) on the graphics side.
export function boxSet(gl, set) {
  const prog = program(gl, BOX_VS, BOX_FS);
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  buffer(gl, boxIndex(), gl.ELEMENT_ARRAY_BUFFER);
  // The vertices go to the graphics side UPLOAD_BYTES a frame, each piece once the one before
  // has arrived (a fence), so that no frame holds the browser for a whole plate's upload.
  const total = set.vertices.byteLength;
  const data = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, data);
  gl.bufferData(gl.ARRAY_BUFFER, Math.max(total, 4), gl.STATIC_DRAW);
  let uploaded = 0, fence = null;
  const at = { pos: prog.a('aPos'), nrm: prog.a('aNrm'), wh: prog.a('aWH'), flags: prog.a('aFlags') };
  for (const a of Object.values(at)) if (a >= 0) gl.enableVertexAttribArray(a);
  gl.bindVertexArray(null);
  const colours = new Float32Array(COLOURS.flat());
  const layerStart = set.layerStart;
  return {
    layerStart,
    // One more piece of the upload; true once every byte is on the graphics side.
    upload() {
      if (fence) {
        if (gl.getSyncParameter(fence, gl.SYNC_STATUS) !== gl.SIGNALED) return false;
        gl.deleteSync(fence); fence = null;
      }
      if (uploaded >= total) return true;
      const n = Math.min(UPLOAD_BYTES, total - uploaded);
      gl.bindBuffer(gl.ARRAY_BUFFER, data);
      gl.bufferSubData(gl.ARRAY_BUFFER, uploaded, set.vertices, uploaded, n);
      uploaded += n;
      fence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
      gl.flush();
      return false;
    },
    begin(f) {
      gl.useProgram(prog.p);
      gl.uniformMatrix4fv(prog.u.viewProj, false, f.viewProj);
      gl.uniform3f(prog.u.camPos, ...f.camPos);
      gl.uniform1f(prog.u.pxPerUnit, f.pxPerUnit);
      gl.uniform2f(prog.u.light, ...LIGHT);
      gl.uniform3fv(prog.u.colours, colours);
      gl.bindVertexArray(vao);
      gl.bindBuffer(gl.ARRAY_BUFFER, data);
    },
    // Boxes [from, to), as the current layer or not; returns how many.
    draw(from, to, current) {
      if (to <= from) return 0;
      gl.uniform1f(prog.u.current, current ? 1 : 0);
      gl.uniform1f(prog.u.minPx, current ? 2 : 1);
      for (let s = from; s < to; s += BATCH) {
        const n = Math.min(BATCH, to - s), o = s * SEGMENT_BYTES;
        gl.vertexAttribPointer(at.pos, 3, gl.UNSIGNED_SHORT, false, VERTEX_BYTES, o);
        gl.vertexAttribPointer(at.nrm, 2, gl.BYTE, true, VERTEX_BYTES, o + 6);
        gl.vertexAttribPointer(at.wh, 2, gl.UNSIGNED_BYTE, false, VERTEX_BYTES, o + 8);
        gl.vertexAttribPointer(at.flags, 1, gl.UNSIGNED_BYTE, false, VERTEX_BYTES, o + 10);
        gl.drawElements(gl.TRIANGLES, n * 12, gl.UNSIGNED_SHORT, 0);
      }
      return to - from;
    },
  };
}

function clear(gl) {
  gl.clearColor(...BACKGROUND, 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
}

function drawFull(gl, full, f, scene, bands = 24) {
  clear(gl);
  scene.plate(f.viewProj);
  full.begin(f);
  let n = 0;
  const most = Math.max(1, Math.ceil(full.layerStart[f.k] / bands));
  for (const [a, b, current] of fullPieces(full.layerStart, f.k, most)) n += full.draw(a, b, current);
  if (f.k < f.layers - 1) scene.ghost(f.viewProj, f.layerZ[f.k]);
  return n;
}

// The look while moving: every D-th layer below the cut (from the coarser set, each box as
// tall as the D layers it stands for), the few layers between the last of them and the cut
// from the full set, and the current layer; no ghost.
// While the full set is still uploading, only the coarser layers are drawn.
function drawMoving(gl, full, moving, decimate, f, scene, fullReady = true) {
  clear(gl);
  scene.plate(f.viewProj);
  let n = 0;
  const lastGroup = Math.floor(f.k / decimate) * decimate - 1;   // the top layer of the last whole group below k
  if (fullReady) {
    full.begin(f);
    n += full.draw(full.layerStart[f.k], full.layerStart[f.k + 1], true);
    if (lastGroup + 1 < f.k) n += full.draw(full.layerStart[lastGroup + 1], full.layerStart[f.k], false);
  }
  if (lastGroup >= 0) {
    moving.begin(f);
    n += moving.draw(0, moving.layerStart[lastGroup + 1], false);
  }
  return n;
}

// Method A: every segment a box, in every frame, moving or not.
export const methodA = {
  name: 'A: every box, every frame', prepare: 'every',
  create(gl, prepared) {
    const full = boxSet(gl, prepared.full);
    return {
      draw(f, scene) {
        if (!full.upload()) { clear(gl); scene.plate(f.viewProj); return { segments: 0, complete: false, again: true }; }
        return { segments: drawFull(gl, full, f, scene), complete: true };
      },
    };
  },
};

// Uploads the coarser set first, then the full one; says which are on the graphics side.
function uploading(moving, full) {
  const movingReady = moving.upload();
  return { movingReady, fullReady: movingReady && full.upload() };
}
const waiting = (gl, f, scene) => { clear(gl); scene.plate(f.viewProj); return { segments: 0, complete: false, again: true }; };

// Method B: while the view moves or the layer bar is dragged, every D-th layer with coarser
// arcs; at rest, every box, in one frame.
export const methodB = {
  name: 'B: fewer layers while moving, every box at rest', prepare: 'moving',
  create(gl, prepared) {
    const full = boxSet(gl, prepared.full), moving = boxSet(gl, prepared.moving);
    return {
      decimate: prepared.decimate,
      draw(f, scene) {
        const { movingReady, fullReady } = uploading(moving, full);
        if (!movingReady) return waiting(gl, f, scene);
        if (f.moving || !fullReady) {
          const n = drawMoving(gl, full, moving, prepared.decimate, f, scene, fullReady);
          return { segments: n, complete: false, again: !fullReady };
        }
        return { segments: drawFull(gl, full, f, scene), complete: true };
      },
    };
  },
};

// Method C: as B while moving; at rest, the full look is drawn into an image off the screen a
// piece at a time, at most `PIECE` boxes a frame, while the screen keeps the look while moving,
// and is copied to the screen when it is whole. No frame holds the browser for the whole plate.
export const PIECE = 100000;
export const methodC = {
  name: 'C: fewer layers while moving, every box at rest over several frames', prepare: 'moving',
  create(gl, prepared, info) {
    const full = boxSet(gl, prepared.full), moving = boxSet(gl, prepared.moving);
    const [w, h] = info.resolution;
    const fbo = gl.createFramebuffer(), colour = gl.createRenderbuffer(), depth = gl.createRenderbuffer();
    gl.bindRenderbuffer(gl.RENDERBUFFER, colour); gl.renderbufferStorage(gl.RENDERBUFFER, gl.RGBA8, w, h);
    gl.bindRenderbuffer(gl.RENDERBUFFER, depth); gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT24, w, h);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.RENDERBUFFER, colour);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, depth);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    let work = null;          // the pieces still to draw for the view at rest, or null
    let fence = null;         // the last piece's fence: the next piece waits until it is drawn
    let shown = false;        // the full look of the present view is on the screen
    let warmed = false;       // the pipelines are built
    return {
      decimate: prepared.decimate,
      // `fresh` is true when the view or the layer changed since the last frame.
      draw(f, scene, fresh) {
        const { movingReady, fullReady } = uploading(moving, full);
        if (!movingReady) return waiting(gl, f, scene);
        if (!warmed) {
          // A first frame of one box, to the screen and to the image off it: software drawing
          // builds its pipelines on the first draw of each, which then holds no full frame.
          for (const target of [fbo, null]) {
            gl.bindFramebuffer(gl.FRAMEBUFFER, target);
            gl.viewport(0, 0, w, h);
            clear(gl); scene.plate(f.viewProj);
            moving.begin(f); moving.draw(0, Math.min(1, moving.layerStart[moving.layerStart.length - 1]), false);
          }
          warmed = true;
          return { segments: 0, complete: false, again: true };       // not yet a layer on the screen
        }
        if (!fullReady) {
          const n = drawMoving(gl, full, moving, prepared.decimate, f, scene, false);
          work = null;
          return { segments: n, complete: false, again: true };
        }
        if (f.moving || fresh || (!work && !shown)) {
          const n = drawMoving(gl, full, moving, prepared.decimate, f, scene);
          work = f.moving ? null : { pieces: fullPieces(full.layerStart, f.k, PIECE), next: 0, started: false };
          shown = false;
          return { segments: n, complete: false, again: !f.moving };
        }
        if (!work) return { segments: 0, complete: true };
        // The browser queues drawing without waiting for it, so a piece is only started when
        // the graphics side has finished the one before; otherwise the pieces pile up and the
        // copy to the screen waits for all of them at once.
        if (fence) {
          if (gl.getSyncParameter(fence, gl.SYNC_STATUS) !== gl.SIGNALED) return { segments: 0, complete: false, again: true };
          gl.deleteSync(fence); fence = null;
        }
        if (work.next < work.pieces.length || !work.ghosted) {
          gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
          gl.viewport(0, 0, w, h);
          if (!work.started) { clear(gl); scene.plate(f.viewProj); work.started = true; }
          let n = 0;
          if (work.next < work.pieces.length) {
            full.begin(f);
            while (work.next < work.pieces.length) {
              const [a, b, current] = work.pieces[work.next];
              if (n > 0 && n + (b - a) > PIECE) break;
              work.next++;
              n += full.draw(a, b, current);
            }
          } else {                                     // the ghost, a frame of its own
            if (f.k < f.layers - 1) scene.ghost(f.viewProj, f.layerZ[f.k]);
            work.ghosted = true;
          }
          gl.bindFramebuffer(gl.FRAMEBUFFER, null);
          fence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
          gl.flush();
          return { segments: n, complete: false, again: true };
        }
        // Every piece is drawn: the copy to the screen.
        gl.bindFramebuffer(gl.READ_FRAMEBUFFER, fbo);
        gl.blitFramebuffer(0, 0, w, h, 0, 0, w, h, gl.COLOR_BUFFER_BIT, gl.NEAREST);
        gl.bindFramebuffer(gl.READ_FRAMEBUFFER, null);
        work = null;
        shown = true;
        return { segments: 0, complete: true };
      },
    };
  },
};
