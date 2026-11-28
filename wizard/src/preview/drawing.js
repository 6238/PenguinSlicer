// The layer preview's drawing, on WebGL 2 directly (wizard/README-details.md, "The layer
// preview"): method C of the first trial (wizard/trials/preview/methods.js and viewer.js, and the
// trial's record for its figures and why). Every segment is a box as wide as its line and as tall
// as its layer, its top and its long side towards the camera drawn, so that stacked layers close
// into surfaces with no combs and no show-through. While the view moves (turned, or the layer bar
// dragged) it draws every D-th layer of a coarser reading, each box D layers tall, and no ghost.
// At rest it draws the full look into an image off the screen, at most PIECE boxes a frame, each
// piece only after a fence shows the one before is drawn, then the ghost as a piece of its own,
// and copies the image to the screen when it is whole. The vertices and the ghost go to the
// graphics side UPLOAD_BYTES a frame behind a fence. Nothing here survives a lost drawing
// context: the view builds a new drawing from the same prepared data when the context returns.
import { GROUP_COLOURS } from './gcode.js';
import { fullPieces } from './boxes.js';

const rgb = (hex) => [((hex >> 16) & 255) / 255, ((hex >> 8) & 255) / 255, (hex & 255) / 255];
export const BACKGROUND = rgb(0xf2f4f7);           // the view's background, the mockup's --canvas-bg
export const COLOURS = GROUP_COLOURS.map(rgb);
// The walls' light, as the mockup's: from the front left, above.
export const LIGHT = (() => { const x = -0.4, y = -0.6, l = Math.hypot(x, y); return [x / l, y / l]; })();
const GHOST = [...rgb(0x95a0ac), 0.36];            // the mockup's ghost: grey, 36 % opaque
const PLATE = rgb(0xe3e7ec), GRID = rgb(0xcfd5dc);
// The most boxes drawn into the image off the screen in one frame at rest (the record, decision 9).
export const PIECE = 100000;
// The most bytes sent to the graphics side in one frame.
export const UPLOAD_BYTES = 8 * 1024 * 1024;
const VERTEX_BYTES = 12, SEGMENT_BYTES = 72, BATCH = Math.floor(65536 / 6);

/* ---------------------------------------------------------------- the boxes
 * A box is never narrower than `minPx` pixels (1; 2 for the current layer, which is also
 * unshaded). Walls' sides are darkened by the way they face the light, never lightened. Software
 * drawing is slow for instanced drawing (the record's bench), so each box is six vertices of its
 * own, drawn in batches of BATCH boxes with 16-bit indices. */
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
  // Lines of one layer overlap where Orca lays infill and surfaces over the walls' edge; the
  // walls' tops sit 0.01 mm higher, so the walls' smooth edge is drawn over the lines' ends.
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

const FLAT_VS = `#version 300 es
in vec3 position; uniform mat4 viewProj; out vec3 vPos;
void main() { vPos = position; gl_Position = viewProj * vec4(position, 1.0); }`;
const FLAT_FS = `#version 300 es
precision highp float; uniform vec4 colour; out vec4 o;
void main() { o = colour; }`;
// The ghost: what is above the cut, faint grey, its faces a little darker as they turn from the
// light so its shape reads.
const GHOST_FS = `#version 300 es
precision highp float; in vec3 vPos; uniform vec4 colour; uniform float cut; out vec4 o;
void main() {
  if (vPos.z < cut) discard;
  vec3 n = normalize(cross(dFdx(vPos), dFdy(vPos)));
  float shade = 0.82 + 0.18 * abs(dot(n, normalize(vec3(-0.4, -0.6, 0.7))));
  o = vec4(colour.rgb * shade, colour.a);
}`;

// Every object a drawing makes on the graphics side is kept by `keep(kind, object)`, so that
// dispose() gives each back at once rather than leaving it for garbage collection: a second
// show would otherwise hold two drawings' worth of memory for a while.
function program(gl, vs, fs, keep) {
  const compile = (type, src) => {
    const s = keep('Shader', gl.createShader(type));
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS) && !gl.isContextLost()) throw new Error(`a shader did not compile: ${gl.getShaderInfoLog(s)}`);
    return s;
  };
  const p = keep('Program', gl.createProgram());
  gl.attachShader(p, compile(gl.VERTEX_SHADER, vs)); gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS) && !gl.isContextLost()) throw new Error(`a program did not link: ${gl.getProgramInfoLog(p)}`);
  const u = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS) || 0;
  for (let i = 0; i < n; i++) { const name = gl.getActiveUniform(p, i).name.replace(/\[0\]$/, ''); u[name] = gl.getUniformLocation(p, name); }
  return { p, u, a: (name) => gl.getAttribLocation(p, name) };
}

function buffer(gl, keep, data, target = gl.ARRAY_BUFFER) {
  const b = keep('Buffer', gl.createBuffer());
  gl.bindBuffer(target, b); gl.bufferData(target, data, gl.STATIC_DRAW);
  return b;
}

// Sends `bytes` into `buf` UPLOAD_BYTES at a time, each piece once a fence shows the one before
// has arrived, so that no frame holds the browser for a whole plate. step() returns true once
// every byte is on the graphics side; step.drop() gives back a fence still waited on.
function uploader(gl, buf, bytes) {
  let sent = -1, fence = null;
  const step = () => {
    if (fence) {
      if (gl.getSyncParameter(fence, gl.SYNC_STATUS) !== gl.SIGNALED) return false;
      gl.deleteSync(fence); fence = null;
    }
    if (sent >= bytes.length) return true;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    if (sent < 0) { gl.bufferData(gl.ARRAY_BUFFER, Math.max(4, bytes.length), gl.STATIC_DRAW); sent = 0; }
    else {
      const n = Math.min(UPLOAD_BYTES, bytes.length - sent);
      gl.bufferSubData(gl.ARRAY_BUFFER, sent, bytes, sent, n);
      sent += n;
    }
    fence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
    gl.flush();
    return false;
  };
  step.drop = () => { if (fence) gl.deleteSync(fence); fence = null; };
  return step;
}

function boxIndex() {
  const idx = new Uint16Array(BATCH * 12);
  for (let i = 0; i < BATCH; i++) {
    const b = i * 6;
    // the top: provoking vertex 2 (the far top edge); the near side: provoking vertex 4
    idx.set([b, b + 1, b + 2, b + 1, b + 3, b + 2, b, b + 1, b + 4, b + 1, b + 5, b + 4], i * 12);
  }
  return idx;
}

// One set of boxes (boxes.js boxVertices) on the graphics side.
function boxSet(gl, keep, prog, index, set) {
  const vao = keep('VertexArray', gl.createVertexArray());
  gl.bindVertexArray(vao);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, index);
  const data = keep('Buffer', gl.createBuffer());
  const upload = uploader(gl, data, set.vertices);
  gl.bindBuffer(gl.ARRAY_BUFFER, data);
  const at = { pos: prog.a('aPos'), nrm: prog.a('aNrm'), wh: prog.a('aWH'), flags: prog.a('aFlags') };
  for (const a of Object.values(at)) if (a >= 0) gl.enableVertexAttribArray(a);
  gl.bindVertexArray(null);
  const colours = new Float32Array(COLOURS.flat());
  return {
    layerStart: set.layerStart,
    upload,
    drop: upload.drop,
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

// The plate, its grid and the ghost. `printer` is the printable area ({min: [x, y], max: [x, y]}).
function scenery(gl, keep, ghostCorners, printer) {
  const flat = program(gl, FLAT_VS, FLAT_FS, keep), ghost = program(gl, FLAT_VS, GHOST_FS, keep);
  const [x0, y0] = printer.min, [x1, y1] = printer.max;
  const plate = buffer(gl, keep, new Float32Array([x0, y0, -0.02, x1, y0, -0.02, x1, y1, -0.02, x0, y0, -0.02, x1, y1, -0.02, x0, y1, -0.02]));
  const grid = [];
  for (let x = x0; x <= x1 + 1e-6; x += 10) grid.push(x, y0, -0.01, x, y1, -0.01);
  for (let y = y0; y <= y1 + 1e-6; y += 10) grid.push(x0, y, -0.01, x1, y, -0.01);
  const gridBuf = buffer(gl, keep, new Float32Array(grid));
  const ghostBuf = keep('Buffer', gl.createBuffer());
  const ghostBytes = new Uint8Array(ghostCorners.buffer, ghostCorners.byteOffset, ghostCorners.byteLength);
  const ghostUpload = uploader(gl, ghostBuf, ghostBytes);
  let ghostReady = ghostBytes.length === 0;
  const vao = keep('VertexArray', gl.createVertexArray());
  const draw = (prog, buf, mode, count) => {
    gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    const a = prog.a('position');
    gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 3, gl.FLOAT, false, 0, 0);
    gl.drawArrays(mode, 0, count);
  };
  return {
    // One more piece of the ghost's upload; true once it is all on the graphics side.
    upload() { if (!ghostReady) ghostReady = ghostUpload(); return ghostReady; },
    drop: ghostUpload.drop,
    hasGhost: ghostBytes.length > 0,
    plate(viewProj) {
      gl.useProgram(flat.p); gl.uniformMatrix4fv(flat.u.viewProj, false, viewProj);
      gl.uniform4f(flat.u.colour, ...PLATE, 1); draw(flat, plate, gl.TRIANGLES, 6);
      gl.uniform4f(flat.u.colour, ...GRID, 1); draw(flat, gridBuf, gl.LINES, grid.length / 3);
    },
    ghost(viewProj, cut) {
      if (!ghostReady || !ghostBytes.length) return;
      gl.useProgram(ghost.p); gl.uniformMatrix4fv(ghost.u.viewProj, false, viewProj);
      gl.uniform4f(ghost.u.colour, ...GHOST); gl.uniform1f(ghost.u.cut, cut);
      gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false);
      gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK);
      draw(ghost, ghostBuf, gl.TRIANGLES, ghostCorners.length / 3);
      gl.disable(gl.CULL_FACE); gl.depthMask(true); gl.disable(gl.BLEND);
    },
  };
}

function clear(gl) {
  gl.clearColor(...BACKGROUND, 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL);
}

// The look while moving: every D-th layer below the cut (from the coarser set, each box as tall
// as the D layers it stands for), the few layers between the last of them and the cut from the
// full set, and the current layer; no ghost. While the full set is still uploading, only the
// coarser layers are drawn.
function drawMoving(gl, full, moving, decimate, f, scene, fullReady) {
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

// createDrawing(gl, prepared, {printer, width, height}): the drawing of one prepared sliced file
// (reading.js's result) on the context `gl`. draw(f, fresh, ghostShown) draws one frame of the
// frame state `f` ({viewProj, camPos, pxPerUnit, k, moving, layerZ, layers}); `fresh` says the
// view or the layer changed since the last frame. It returns {segments, complete, again}:
// `segments` the toolpath boxes the frame drew (0 for a frame of the plate alone), `complete`
// that the full look is on the screen, `again` that it wants another frame to go on drawing.
// dispose() gives back every object of the drawing on the graphics side at once; the drawing
// draws nothing after it.
export function createDrawing(gl, prepared, { printer, width, height }) {
  const own = [];
  const keep = (kind, o) => { if (o) own.push([kind, o]); return o; };
  // Built in a try, so that a drawing that fails while being built leaves nothing behind either.
  let boxes, index, full, moving, scene, fbo, colour, depth;
  try {
    boxes = program(gl, BOX_VS, BOX_FS, keep);
    index = buffer(gl, keep, boxIndex(), gl.ELEMENT_ARRAY_BUFFER);
    full = boxSet(gl, keep, boxes, index, prepared.full);
    moving = boxSet(gl, keep, boxes, index, prepared.moving);
    scene = scenery(gl, keep, prepared.ghost.corners, printer);
    fbo = keep('Framebuffer', gl.createFramebuffer());
    colour = keep('Renderbuffer', gl.createRenderbuffer());
    depth = keep('Renderbuffer', gl.createRenderbuffer());
  } catch (error) {
    release();
    throw error;
  }
  function release() {
    for (const s of [full, moving, scene]) if (s) s.drop();
    for (const [kind, o] of own.splice(0)) gl[`delete${kind}`](o);
  }
  const decimate = prepared.decimate;
  let w = width, h = height;
  function size() {
    gl.bindRenderbuffer(gl.RENDERBUFFER, colour); gl.renderbufferStorage(gl.RENDERBUFFER, gl.RGBA8, w, h);
    gl.bindRenderbuffer(gl.RENDERBUFFER, depth); gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT24, w, h);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.RENDERBUFFER, colour);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, depth);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }
  size();
  let work = null;          // the pieces still to draw for the view at rest, or null
  let fence = null;         // the last piece's fence: the next piece waits until it is drawn
  let shown = false;        // the full look of the present view is on the screen
  let warmed = false;       // the pipelines are built
  let ghostDone = !scene.hasGhost;

  const toScreen = () => { gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, w, h); };

  function frame(f, fresh, ghostShown) {
    const movingReady = moving.upload();
    const fullReady = movingReady && full.upload();
    toScreen();
    if (!movingReady) { clear(gl); scene.plate(f.viewProj); return { segments: 0, complete: false, again: true }; }
    if (!warmed) {
      // A first frame of one box, to the image off the screen and to the screen: software
      // drawing builds its pipelines on the first draw of each, which then holds no full frame.
      for (const target of [fbo, null]) {
        gl.bindFramebuffer(gl.FRAMEBUFFER, target);
        gl.viewport(0, 0, w, h);
        clear(gl); scene.plate(f.viewProj);
        moving.begin(f); moving.draw(0, Math.min(1, moving.layerStart[moving.layerStart.length - 1]), false);
      }
      warmed = true;
      return { segments: 0, complete: false, again: true };
    }
    if (!fullReady) {
      const n = drawMoving(gl, full, moving, decimate, f, scene, false);
      work = null;
      return { segments: n, complete: false, again: true };
    }
    if (f.moving || fresh || (!work && !shown)) {
      const n = drawMoving(gl, full, moving, decimate, f, scene, true);
      work = f.moving ? null : { pieces: fullPieces(full.layerStart, f.k, PIECE), next: 0, started: false, ghosted: false };
      shown = false;
      return { segments: n, complete: false, again: !f.moving };
    }
    if (!work) return { segments: 0, complete: true };
    // The browser queues drawing without waiting for it, so a piece is only started when the
    // graphics side has finished the one before; otherwise the pieces pile up and the copy to the
    // screen waits for all of them at once.
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
        if (ghostShown && f.k < f.layers - 1) scene.ghost(f.viewProj, f.layerZ[f.k]);
        work.ghosted = true;
      }
      toScreen();
      fence = gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0);
      gl.flush();
      return { segments: n, complete: false, again: true };
    }
    // Every piece is drawn: the copy to the screen.
    gl.bindFramebuffer(gl.READ_FRAMEBUFFER, fbo);
    gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER, null);
    gl.blitFramebuffer(0, 0, w, h, 0, 0, w, h, gl.COLOR_BUFFER_BIT, gl.NEAREST);
    gl.bindFramebuffer(gl.READ_FRAMEBUFFER, null);
    work = null;
    shown = true;
    return { segments: 0, complete: true };
  }

  return {
    decimate,
    // A new size of the drawing buffer, in pixels: the image off the screen follows it.
    resize(width2, height2) {
      if (width2 === w && height2 === h) return;
      w = width2; h = height2;
      size();
      work = null; shown = false;
    },
    dispose() {
      if (fence) gl.deleteSync(fence);
      fence = null; work = null;
      release();
    },
    draw(f, fresh, ghostShown = true) {
      const r = frame(f, fresh, ghostShown);
      // The ghost uploads behind the toolpaths; once it has arrived the view is drawn again with
      // it, and until then the full look is not counted as on the screen.
      if (!ghostDone) {
        ghostDone = scene.upload();
        if (ghostDone) { shown = false; work = null; }
        r.complete = false;
        r.again = true;
      }
      return r;
    },
  };
}
