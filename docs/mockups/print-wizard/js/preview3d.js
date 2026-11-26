/* PenguinSlicer mockup: fake toolpaths from the mock geometry, and the layer preview.
 * Each layer is a real cross-section of the placed mesh; walls are that outline pushed
 * inward, infill is scanlines clipped to the section, solid layers are found by comparing
 * with the layers above and below, supports stand under faces that point down. It is not
 * G-code and not what Orca would produce; it only has the look of Orca's Preview tab. */
(function () {
  'use strict';
  var T = THREE;

  // Version 8 (the owner): four fixed colours, one for each group of line types. They follow
  // neither the filament nor Orca. Chosen for hue spacing, lightness against the view's
  // background #f2f4f7 and against each other, and checked by simulation for protanopia,
  // deuteranopia and tritanopia (DECISIONS.md, decision 33).
  var GROUPS = [
    { id: 'walls', label: 'Walls', color: 0x2b5c9e },
    { id: 'infill', label: 'Infill', color: 0xe0912f },
    { id: 'surfaces', label: 'Top and bottom surfaces', color: 0x2f9e7a },
    { id: 'supports', label: 'Supports and brim', color: 0x9a8fb8 }
  ];
  var TYPES = [
    { id: 'outer', label: 'Outer wall', group: 'walls' },
    { id: 'inner', label: 'Inner wall', group: 'walls' },
    { id: 'sparse', label: 'Sparse infill', group: 'infill' },
    { id: 'solid', label: 'Internal solid infill', group: 'infill' },
    { id: 'top', label: 'Top surface', group: 'surfaces' },
    { id: 'bottom', label: 'Bottom surface', group: 'surfaces' },
    { id: 'support', label: 'Support', group: 'supports' },
    { id: 'brim', label: 'Brim', group: 'supports' }
  ];
  var GROUP_COLOR = {}; GROUPS.forEach(function (g) { GROUP_COLOR[g.id] = g.color; });
  TYPES.forEach(function (t) { t.color = GROUP_COLOR[t.group]; });
  // Walls are shaded by which way they face, as if lit by the Layout view's main light (from
  // the front left, above), so the stacked walls read as surfaces and not as a flat silhouette.
  var LIGHT = (function () { var x = -0.4, y = -0.6, L = Math.sqrt(x * x + y * y); return [x / L, y / L]; })();
  function wallShade(nx, ny) { return 0.5 + 0.5 * (nx * LIGHT[0] + ny * LIGHT[1]); }     // 0 facing away, 1 facing the light

  /* --------------------------------------------------- one part in one orientation */
  function makeGroup(partKey, q, d) {
    var def = MockParts.byKey[partKey], p = def.geometry.attributes.position.array;
    var n = p.length / 9, tri = new Float32Array(p.length), v = new T.Vector3();
    for (var i = 0; i < p.length; i += 3) {
      v.set(p[i], p[i + 1], p[i + 2]).applyQuaternion(q);
      tri[i] = v.x - d.offset[0]; tri[i + 1] = v.y - d.offset[1]; tri[i + 2] = v.z - d.offset[2];
    }
    var zmin = new Float32Array(n), zmax = new Float32Array(n), nrm = new Float32Array(n * 3);
    for (var t = 0; t < n; t++) {
      var o = t * 9;
      zmin[t] = Math.min(tri[o + 2], tri[o + 5], tri[o + 8]); zmax[t] = Math.max(tri[o + 2], tri[o + 5], tri[o + 8]);
      var ax = tri[o + 3] - tri[o], ay = tri[o + 4] - tri[o + 1], az = tri[o + 5] - tri[o + 2];
      var bx = tri[o + 6] - tri[o], by = tri[o + 7] - tri[o + 1], bz = tri[o + 8] - tri[o + 2];
      var nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx, L = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
      nrm[t * 3] = nx / L; nrm[t * 3 + 1] = ny / L; nrm[t * 3 + 2] = nz / L;
    }
    return { tri: tri, n: n, zmin: zmin, zmax: zmax, nrm: nrm, height: d.height, sections: {}, bins: {}, layers: {} };
  }

  // segments [x1,y1,x2,y2,nx,ny] where the plane z cuts the mesh
  function section(g, z) {
    if (g.sections[z] !== undefined) return g.sections[z];
    var out = [], tri = g.tri;
    for (var t = 0; t < g.n; t++) {
      if (g.zmin[t] > z || g.zmax[t] < z) continue;
      var nx = g.nrm[t * 3], ny = g.nrm[t * 3 + 1], L = Math.sqrt(nx * nx + ny * ny);
      if (L < 0.05) continue;
      var o = t * 9, pts = [];
      for (var e = 0; e < 3; e++) {
        var a = o + e * 3, b = o + ((e + 1) % 3) * 3, za = tri[a + 2], zb = tri[b + 2];
        if ((za <= z) !== (zb <= z)) {
          var f = (z - za) / (zb - za);
          pts.push(tri[a] + (tri[b] - tri[a]) * f, tri[a + 1] + (tri[b + 1] - tri[a + 1]) * f);
        }
      }
      if (pts.length === 4) out.push(pts[0], pts[1], pts[2], pts[3], nx / L, ny / L);
    }
    g.sections[z] = out;
    return out;
  }

  // scanline crossings of a section, binned by scanline index for one direction
  function bins(g, z, ang, s) {
    var key = z + '|' + ang;
    if (g.bins[key]) return g.bins[key];
    var segs = section(g, z), c = Math.cos(ang), sn = Math.sin(ang), lists = {};
    for (var i = 0; i < segs.length; i += 6) {
      var u1 = segs[i] * c + segs[i + 1] * sn, v1 = -segs[i] * sn + segs[i + 1] * c;
      var u2 = segs[i + 2] * c + segs[i + 3] * sn, v2 = -segs[i + 2] * sn + segs[i + 3] * c;
      var lo = Math.ceil(Math.min(v1, v2) / s), hi = Math.floor(Math.max(v1, v2) / s);
      for (var j = lo; j <= hi; j++) {
        var vj = j * s;
        if ((v1 <= vj) === (v2 <= vj)) continue;
        (lists[j] = lists[j] || []).push(u1 + (u2 - u1) * (vj - v1) / (v2 - v1));
      }
    }
    var out = {};
    Object.keys(lists).forEach(function (j) {
      var u = lists[j].sort(function (a, b) { return a - b; }), iv = [];
      for (var k = 0; k + 1 < u.length; k += 2) iv.push([u[k], u[k + 1]]);
      out[j] = iv;
    });
    g.bins[key] = out;
    return out;
  }
  function inter(a, b) {
    var out = [], i = 0, j = 0;
    while (i < a.length && j < b.length) {
      var lo = Math.max(a[i][0], b[j][0]), hi = Math.min(a[i][1], b[j][1]);
      if (hi > lo) out.push([lo, hi]);
      if (a[i][1] < b[j][1]) i++; else j++;
    }
    return out;
  }
  function minus(a, b) {
    var out = [];
    a.forEach(function (iv) {
      var cur = [[iv[0], iv[1]]];
      b.forEach(function (cut) {
        var next = [];
        cur.forEach(function (x) {
          if (cut[1] <= x[0] || cut[0] >= x[1]) { next.push(x); return; }
          if (cut[0] > x[0]) next.push([x[0], cut[0]]);
          if (cut[1] < x[1]) next.push([cut[1], x[1]]);
        });
        cur = next;
      });
      cur.forEach(function (x) { if (x[1] - x[0] > 0.3) out.push(x); });
    });
    return out;
  }
  function shrink(a, by) {
    return a.map(function (x) { return [x[0] + by, x[1] - by]; }).filter(function (x) { return x[1] - x[0] > 0.2; });
  }

  // outer contours (not holes): nothing of the section lies further out along the normal
  function isOuter(segs, i) {
    var mx = (segs[i] + segs[i + 2]) / 2 + segs[i + 4] * 0.3, my = (segs[i + 1] + segs[i + 3]) / 2 + segs[i + 5] * 0.3;
    var dx = segs[i + 4], dy = segs[i + 5];
    for (var k = 0; k < segs.length; k += 6) {
      if (k === i) continue;
      var ax = segs[k] - mx, ay = segs[k + 1] - my, bx = segs[k + 2] - mx, by = segs[k + 3] - my;
      var c1 = dx * ay - dy * ax, c2 = dx * by - dy * bx;
      if ((c1 > 0) === (c2 > 0)) continue;
      var t = (ax * (by - ay) - ay * (bx - ax)) / (dx * (by - ay) - dy * (bx - ax));
      if (t > 0) return false;
    }
    return true;
  }

  // support cells: under faces pointing down, above whatever surface is beneath them
  function supportCells(g, S) {
    var cell = Math.max(1.5, S.support_base_pattern_spacing), lim = -Math.cos(S.support_threshold_angle * Math.PI / 180);
    var tops = {}, ups = {};
    for (var t = 0; t < g.n; t++) {
      var nz = g.nrm[t * 3 + 2], o = t * 9;
      if (nz >= lim && nz <= 0.5) continue;
      var minx = Math.min(g.tri[o], g.tri[o + 3], g.tri[o + 6]), maxx = Math.max(g.tri[o], g.tri[o + 3], g.tri[o + 6]);
      var miny = Math.min(g.tri[o + 1], g.tri[o + 4], g.tri[o + 7]), maxy = Math.max(g.tri[o + 1], g.tri[o + 4], g.tri[o + 7]);
      for (var i = Math.floor(minx / cell); i <= Math.floor(maxx / cell); i++) {
        for (var j = Math.floor(miny / cell); j <= Math.floor(maxy / cell); j++) {
          var cx = (i + 0.5) * cell, cy = (j + 0.5) * cell;
          if (!inTri(g.tri, o, cx, cy)) continue;
          var z = zAt(g.tri, o, cx, cy), k = i + ',' + j;
          if (nz < lim) { if (z > 0.6) (tops[k] = tops[k] || []).push(z); }
          else (ups[k] = ups[k] || []).push(z);
        }
      }
    }
    var cells = [];
    Object.keys(tops).forEach(function (k) {
      var ij = k.split(',').map(Number), u = ups[k] || [];
      tops[k].forEach(function (top) {
        var bottom = 0;
        u.forEach(function (z) { if (z < top - 0.5 && z > bottom) bottom = z; });
        if (S.support_on_build_plate_only && bottom > 0) return;
        if (top - bottom > 0.8) cells.push({ x: (ij[0] + 0.5) * cell, y: (ij[1] + 0.5) * cell, half: cell * 0.42, bottom: bottom, top: top - S.support_top_z_distance });
      });
    });
    return cells;
  }
  function inTri(tri, o, x, y) {
    function s(ax, ay, bx, by) { return (x - bx) * (ay - by) - (ax - bx) * (y - by); }
    var d1 = s(tri[o], tri[o + 1], tri[o + 3], tri[o + 4]), d2 = s(tri[o + 3], tri[o + 4], tri[o + 6], tri[o + 7]), d3 = s(tri[o + 6], tri[o + 7], tri[o], tri[o + 1]);
    return !((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0));
  }
  function zAt(tri, o, x, y) {
    var x1 = tri[o], y1 = tri[o + 1], z1 = tri[o + 2], x2 = tri[o + 3], y2 = tri[o + 4], z2 = tri[o + 5], x3 = tri[o + 6], y3 = tri[o + 7], z3 = tri[o + 8];
    var det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3);
    if (Math.abs(det) < 1e-9) return Math.max(z1, z2, z3);
    var l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / det, l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / det;
    return l1 * z1 + l2 * z2 + (1 - l1 - l2) * z3;
  }

  /* --------------------------------------------------- the layers */
  function layerHeights(S, height) {
    var zs = [], top = S.initial_layer_print_height;
    while (top - (zs.length ? S.layer_height : S.initial_layer_print_height) < height - 0.01) {
      zs.push(top); top += S.layer_height;
    }
    return zs;
  }

  // one layer of one group, in the group's own frame: {type: [x1,y1,x2,y2,...]}
  function layerPaths(g, k, zs, S, brimOn) {
    if (g.layers[k]) return g.layers[k];
    var w = S.line_width, out = { outer: [], inner: [], sparse: [], solid: [], top: [], bottom: [], support: [], brim: [], shade: { outer: [], inner: [] } };
    var lh = k ? S.layer_height : S.initial_layer_print_height, z = zs[k] - lh / 2;
    var segs = section(g, z), i, loops = Math.min(S.wall_loops, 4);
    for (i = 0; i < segs.length; i += 6) {
      var sh = wallShade(segs[i + 4], segs[i + 5]);
      for (var wl = 0; wl < loops; wl++) {
        var off = -w * (wl + 0.5), nx = segs[i + 4] * off, ny = segs[i + 5] * off;
        (wl ? out.inner : out.outer).push(segs[i] + nx, segs[i + 1] + ny, segs[i + 2] + nx, segs[i + 3] + ny);
        (wl ? out.shade.inner : out.shade.outer).push(sh);
      }
    }
    if (k === 0 && brimOn) {
      var rings = Math.max(1, Math.round(S.brim_width / w));
      for (i = 0; i < segs.length; i += 6) {
        if (!isOuter(segs, i)) continue;
        for (var r = 0; r < rings; r++) {
          var o2 = S.brim_object_gap + w * (r + 0.5), bx = segs[i + 4] * o2, by = segs[i + 5] * o2;
          out.brim.push(segs[i] + bx, segs[i + 1] + by, segs[i + 2] + bx, segs[i + 3] + by);
        }
      }
    }
    // fill
    var N = Math.max(1, S.top_shell_layers), NB = Math.max(1, S.bottom_shell_layers);
    function zOf(kk) { return kk < 0 || kk >= zs.length ? null : zs[kk] - (kk ? S.layer_height : S.initial_layer_print_height) / 2; }
    var angs = [(k % 2 ? 45 : -45) * Math.PI / 180];
    var sp = S.sparse_infill_density > 0 ? Math.max(1, Math.round(100 / S.sparse_infill_density)) : 0;
    var wallT = w * S.wall_loops;
    angs.forEach(function (ang) {
      var A = bins(g, z, ang, w), keys = Object.keys(A);
      var Bt = zOf(k + 1) === null ? {} : bins(g, zOf(k + 1), ang, w);
      var BN = zOf(k + N) === null ? {} : bins(g, zOf(k + N), ang, w);
      var Cb = zOf(k - 1) === null ? {} : bins(g, zOf(k - 1), ang, w);
      var CN = zOf(k - NB) === null ? {} : bins(g, zOf(k - NB), ang, w);
      var c = Math.cos(ang), s = Math.sin(ang);
      function emit(list, j, ivs) {
        var v = j * w;
        ivs.forEach(function (iv) {
          list.push(iv[0] * c - v * s, iv[0] * s + v * c, iv[1] * c - v * s, iv[1] * s + v * c);
        });
      }
      keys.forEach(function (j) {
        var a = shrink(A[j], wallT); if (!a.length) return;
        var b1 = Bt[j] || [], c1 = Cb[j] || [], bn = BN[j] || [], cn = CN[j] || [];
        var top = minus(a, b1);
        var bottom = minus(inter(a, b1), c1);
        var core = inter(inter(a, b1), c1);
        var deep = inter(inter(core, bn), cn);
        var solid = minus(core, deep);
        if (k === 0) { emit(out.bottom, j, a); return; }
        emit(out.top, j, top); emit(out.bottom, j, bottom); emit(out.solid, j, solid);
        if (sp && (+j) % sp === 0) emit(out.sparse, j, deep);
      });
      if (sp && S.sparse_infill_pattern === 'grid') {
        var ang2 = ang + Math.PI / 2, A2 = bins(g, z, ang2, w), c2 = Math.cos(ang2), s2 = Math.sin(ang2);
        var BN2 = zOf(k + N) === null ? {} : bins(g, zOf(k + N), ang2, w), CN2 = zOf(k - NB) === null ? {} : bins(g, zOf(k - NB), ang2, w);
        Object.keys(A2).forEach(function (j) {
          if ((+j) % sp) return;
          var a = shrink(A2[j], wallT), deep = inter(inter(a, BN2[j] || []), CN2[j] || []), v = j * w;
          deep.forEach(function (iv) { out.sparse.push(iv[0] * c2 - v * s2, iv[0] * s2 + v * c2, iv[1] * c2 - v * s2, iv[1] * s2 + v * c2); });
        });
      }
    });
    // supports
    if (g.cells) {
      g.cells.forEach(function (cl) {
        if (z < cl.bottom || z > cl.top) return;
        var h = cl.half, flip = k % 2 ? 1 : -1;
        out.support.push(cl.x - h, cl.y - h * flip, cl.x, cl.y + h * flip, cl.x, cl.y + h * flip, cl.x + h, cl.y - h * flip);
      });
    }
    g.layers[k] = out;
    return out;
  }

  function autoBrim(d) {
    var minSide = Math.min(d.w, d.l);
    return d.height > 2.2 * minSide || d.w * d.l < 500;
  }

  // Build every layer of the plate, a few layers per tick so the page stays live.
  function generate(instances, S, onDone) {
    var groups = {}, items = [];
    instances.forEach(function (c) {
      var d = MockPlate.derive(c), key = c.partKey + '|' + d.key;
      if (!groups[key]) {
        groups[key] = makeGroup(c.partKey, c.q, d);
        groups[key].zs = layerHeights(S, d.height);
        if (S.enable_support) groups[key].cells = supportCells(groups[key], S);
        groups[key].brim = S.brim_type === 'no_brim' ? false : (S.brim_type === 'auto_brim' ? autoBrim(d) : true);
      }
      items.push({ g: groups[key], x: c.x, y: c.y });
    });
    var layers = 0;
    Object.keys(groups).forEach(function (k) { layers = Math.max(layers, groups[k].zs.length); });
    var acc = {}; TYPES.forEach(function (t) { acc[t.id] = { pos: [], shade: [], ends: [] }; });
    var length = {}; TYPES.forEach(function (t) { length[t.id] = 0; });
    var zsAll = [], k = 0, cancelled = false;
    function step() {
      if (cancelled) return;
      var t0 = performance.now();
      while (k < layers && performance.now() - t0 < 24) {
        var zTop = null;
        items.forEach(function (it) {
          var g = it.g; if (k >= g.zs.length) return;
          zTop = g.zs[k];
          var L = layerPaths(g, k, g.zs, S, g.brim), z = g.zs[k];
          TYPES.forEach(function (t) {
            var src = L[t.id], dst = acc[t.id].pos, shs = L.shade[t.id], dsh = acc[t.id].shade;
            for (var i = 0; i < src.length; i += 4) {
              dst.push(src[i] + it.x, src[i + 1] + it.y, z, src[i + 2] + it.x, src[i + 3] + it.y, z);
              dsh.push(shs ? shs[i / 4] : 1);
              var dx = src[i + 2] - src[i], dy = src[i + 3] - src[i + 1];
              length[t.id] += Math.sqrt(dx * dx + dy * dy);
            }
          });
        });
        zsAll.push(zTop);
        TYPES.forEach(function (t) { acc[t.id].ends.push(acc[t.id].pos.length / 3); });
        k++;
      }
      if (k < layers) setTimeout(step, 0);
      else onDone({ acc: acc, layers: layers, zs: zsAll, length: length, lineWidth: S.line_width });
    }
    setTimeout(step, 0);
    return { cancel: function () { cancelled = true; } };
  }

  // Print time and filament from the fake toolpaths (plausible, not Orca's estimate).
  function estimate(result, S, filament) {
    var speeds = { outer: S.outer_wall_speed, inner: S.inner_wall_speed, sparse: S.sparse_infill_speed, solid: S.internal_solid_infill_speed,
                   top: S.top_surface_speed, bottom: S.initial_layer_infill_speed, support: S.support_speed, brim: S.initial_layer_speed };
    var secs = 0, mm3 = 0, byType = {};
    TYPES.forEach(function (t) {
      var len = result.length[t.id];
      byType[t.id] = len / (speeds[t.id] * 0.55);          // acceleration and cornering losses
      secs += byType[t.id];
      mm3 += len * S.line_width * S.layer_height * (t.id === 'support' ? 0.6 : 1);
    });
    var overhead = result.layers * 5 + 6 * 60;              // layer changes, heating and levelling
    secs += overhead;
    var grams = mm3 / 1000 * filament.density;
    return { seconds: Math.round(secs), grams: grams, meters: grams / filament.gPerM, byType: byType, overhead: overhead };
  }

  /* --------------------------------------------------- lines with a width */
  // WebGL draws a line one pixel wide whatever the zoom. Each toolpath segment is drawn instead
  // as a quad facing the camera, as wide as the sliced settings' line width seen at that distance and
  // never thinner than a set number of pixels, so lines get their real weight when zoomed in
  // and stay visible when zoomed out. One instanced quad per segment; the draw range is the
  // instance count.
  var LINE_VS = [
    'attribute vec3 iStart; attribute vec3 iEnd; attribute vec3 iColor;',
    'uniform vec2 resolution; uniform float worldWidth; uniform float minPx;',
    'varying vec3 vColor;',
    'void main() {',
    '  vColor = iColor;',
    '  vec4 s = projectionMatrix * modelViewMatrix * vec4(iStart, 1.0);',
    '  vec4 e = projectionMatrix * modelViewMatrix * vec4(iEnd, 1.0);',
    '  vec2 d = (e.xy / e.w - s.xy / s.w) * resolution;',
    '  float len = length(d);',
    '  vec2 dir = len > 1e-6 ? d / len : vec2(1.0, 0.0);',
    '  vec2 nrm = vec2(-dir.y, dir.x);',
    '  vec4 c = position.x < 0.5 ? s : e;',
    '  float px = max(minPx, worldWidth * projectionMatrix[1][1] * resolution.y * 0.5 / c.w);',
    '  vec2 off = (nrm * position.y + dir * (position.x < 0.5 ? -0.5 : 0.5) * abs(position.y)) * px * 0.5;',
    '  c.xy += off / resolution * 2.0 * c.w;',
    '  gl_Position = c;',
    '}'].join('\n');
  var LINE_FS = 'varying vec3 vColor; void main() { gl_FragColor = vec4(vColor, 1.0); }';
  var QUAD = (function () {
    var g = new T.InstancedBufferGeometry();
    g.setAttribute('position', new T.Float32BufferAttribute([0, -1, 0, 0, 1, 0, 1, -1, 0, 1, 1, 0], 3));
    g.setIndex([0, 2, 1, 2, 3, 1]);
    return g;
  })();
  function lineMaterial(minPx, worldWidth) {
    return new T.ShaderMaterial({ vertexShader: LINE_VS, fragmentShader: LINE_FS,
      uniforms: { resolution: { value: new T.Vector2(1, 1) }, worldWidth: { value: worldWidth }, minPx: { value: minPx } } });
  }
  // A segment's colour: the group's colour for a flat line and for a wall facing the light
  // (shade 1); a wall darker as it turns from the light, down to 0.66 of it (shade 0: walls
  // #1c3d68). Fix round 1 of version 8: shading only darkens, so no wall comes nearer to
  // another group's colour than the flat colour that was checked for colour blindness.
  function shaded(base, t, out, o) {
    var c = new T.Color(base), k = 0.66 + 0.34 * t;
    out[o] = c.r * k; out[o + 1] = c.g * k; out[o + 2] = c.b * k;
  }
  // pos: [x1,y1,z1,x2,y2,z2,...] from segment `from` to `to`; flat: every segment in the group's colour
  function lineMesh(pos, shade, base, from, to, material, flat) {
    var n = to - from, st = new Float32Array(n * 3), en = new Float32Array(n * 3), col = new Float32Array(n * 3);
    for (var i = 0; i < n; i++) {
      var p = (from + i) * 6;
      st[i * 3] = pos[p]; st[i * 3 + 1] = pos[p + 1]; st[i * 3 + 2] = pos[p + 2];
      en[i * 3] = pos[p + 3]; en[i * 3 + 1] = pos[p + 4]; en[i * 3 + 2] = pos[p + 5];
      shaded(base, flat ? 1 : shade[from + i], col, i * 3);
    }
    var g = new T.InstancedBufferGeometry();
    g.index = QUAD.index; g.setAttribute('position', QUAD.attributes.position);
    g.setAttribute('iStart', new T.InstancedBufferAttribute(st, 3));
    g.setAttribute('iEnd', new T.InstancedBufferAttribute(en, 3));
    g.setAttribute('iColor', new T.InstancedBufferAttribute(col, 3));
    g.instanceCount = n;
    var m = new T.Mesh(g, material); m.frustumCulled = false;
    return m;
  }

  /* --------------------------------------------------- the viewer */
  // Fix round 1 of version 8 tried the review's cull (below the current layer, no inner walls
  // or infill but for the 16 layers under it). It roughly halved the frame time on software
  // WebGL but changed the look: holes read smaller and the background showed through along
  // edges, where the inner walls fill in behind the one-line outer wall. Not kept; the cost and
  // the requirements it sets for the implementation are in DECISIONS.md, decision 33.
  function createViewer(container, plate) {
    var canvas = document.createElement('canvas'); canvas.className = 'gl-canvas';
    container.appendChild(canvas);
    var renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    var scene = new T.Scene(); scene.background = new T.Color(0xf2f4f7);
    var camera = new T.PerspectiveCamera(40, 1, 1, 5000); camera.up.set(0, 0, 1);
    Layout3D.lights(scene); Layout3D.makePlate(scene, plate);
    var controls = new T.OrbitControls(camera, canvas);
    controls.screenSpacePanning = true; controls.maxPolarAngle = Math.PI * 0.49;
    var needs = true;
    controls.addEventListener('change', function () { needs = true; });
    function loop() { requestAnimationFrame(loop); if (!needs || !container.offsetParent) return; needs = false; renderer.render(scene, camera); }
    requestAnimationFrame(loop);
    function resize() {
      var w = container.clientWidth, h = container.clientHeight; if (!w || !h) return;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); needs = true;
      if (belowMat) setResolution();
    }
    if (window.ResizeObserver) new ResizeObserver(resize).observe(container);
    var lines = {}, result = null, ghosts = [];
    function frameView(instances) {
      var b = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, h: 0 };
      instances.forEach(function (c) {
        var hb = MockPlate.bbox(MockPlate.worldHull(c));
        b.minX = Math.min(b.minX, hb.minX); b.maxX = Math.max(b.maxX, hb.maxX);
        b.minY = Math.min(b.minY, hb.minY); b.maxY = Math.max(b.maxY, hb.maxY); b.h = Math.max(b.h, MockPlate.derive(c).height);
      });
      if (!instances.length) b = { minX: 0, maxX: plate.x, minY: 0, maxY: plate.y, h: 10 };
      var cx = (b.minX + b.maxX) / 2, cy = (b.minY + b.maxY) / 2, span = Math.max(b.maxX - b.minX, b.maxY - b.minY, 60);
      controls.target.set(cx, cy, b.h / 3);
      var k = 1.42 / Math.min(1, Math.max(0.6, camera.aspect || 1));    // room for the whole group beside the layer bar
      camera.position.set(cx + span * 0.35 * k, cy - span * 1.05 * k, span * 0.9 * k + b.h);
      controls.update(); needs = true;
    }
    renderer.localClippingEnabled = true;
    // Layers below the current one: at least 1 px wide, walls shaded. The current layer: drawn
    // again over them, unshaded and at least 2 px wide, so the layer the bar is on stands out.
    // Fix round 1 of version 8: each line is as wide as the sliced settings' line width, the
    // width the mock's paths are laid apart, so a solid surface reads as one colour.
    var belowMat = lineMaterial(1, 0.62), currentMat = lineMaterial(2, 0.62), current = [];
    function setWidth(w) { belowMat.uniforms.worldWidth.value = w; currentMat.uniforms.worldWidth.value = w; }
    function setResolution() {
      var v = new T.Vector2(); renderer.getDrawingBufferSize(v);
      belowMat.uniforms.resolution.value.copy(v); currentMat.uniforms.resolution.value.copy(v);
      var dpr = renderer.getPixelRatio();
      belowMat.uniforms.minPx.value = 1 * dpr; currentMat.uniforms.minPx.value = 2 * dpr;
    }
    // The part above the current layer: a faint ghost of each instance, cut at the layer, so the
    // user sees what is still to print and where the layer sits in the part.
    var cut = new T.Plane(new T.Vector3(0, 0, 1), 0);
    var ghostAbove = new T.MeshLambertMaterial({ color: 0x95a0ac, transparent: true, opacity: 0.36, depthWrite: false, clippingPlanes: [cut] });
    function dropCurrent() { current.forEach(function (m) { scene.remove(m); m.geometry.dispose(); }); current = []; }
    function clear() {
      Object.keys(lines).forEach(function (k) { scene.remove(lines[k]); lines[k].geometry.dispose(); });
      lines = {}; result = null; dropCurrent();
      ghosts.forEach(function (m) { scene.remove(m); }); ghosts = [];
      needs = true;
    }
    function ghostMeshes(instances, material) {
      instances.forEach(function (c) {
        var def = MockParts.byKey[c.partKey], d = MockPlate.derive(c);
        var m = new T.Mesh(def.geometry, material);
        m.quaternion.copy(c.q); m.position.set(c.x - d.offset[0], c.y - d.offset[1], -d.offset[2]);
        ghosts.push(m); scene.add(m);
      });
    }
    // Version 8: four fixed colours, one per group (walls; infill; top and bottom surfaces;
    // supports and brim), whatever the filament.
    function show(res, instances) {
      clear(); result = res; setResolution(); setWidth(res.lineWidth || 0.62);
      TYPES.forEach(function (t) {
        var a = res.acc[t.id]; if (!a.pos.length) return;
        var l = lineMesh(a.pos, a.shade, t.color, 0, a.pos.length / 6, belowMat, false);
        lines[t.id] = l; scene.add(l);
      });
      ghostMeshes(instances, ghostAbove);
      frameView(instances);
      setLayer(res.layers - 1);
    }
    // the instances as grey ghosts, shown while slicing
    function showGhosts(instances) {
      clear();
      ghostMeshes(instances, new T.MeshStandardMaterial({ color: 0x8a96a3, transparent: true, opacity: 0.35, flatShading: true }));
      frameView(instances);
    }
    function setLayer(k) {
      if (!result) return;
      dropCurrent();
      TYPES.forEach(function (t) {
        if (!lines[t.id]) return;
        var a = result.acc[t.id], to = a.ends[k] / 2, from = k ? a.ends[k - 1] / 2 : 0;
        lines[t.id].geometry.instanceCount = from;          // the layers below
        if (to > from) { var m = lineMesh(a.pos, a.shade, t.color, from, to, currentMat, true); m.renderOrder = 1; current.push(m); scene.add(m); }
      });
      // the ghost: what is above the current layer, hidden once every layer is shown
      var last = k >= result.layers - 1;
      cut.constant = -(result.zs[k] || 0);
      ghosts.forEach(function (m) { m.visible = !last; });
      needs = true;
    }
    function setVisible(id, on) { if (lines[id]) { lines[id].visible = on; needs = true; } }
    return { show: show, showGhosts: showGhosts, clear: clear, setLayer: setLayer, resize: resize, frameView: frameView, setVisible: setVisible,
             reset: function (instances) { frameView(instances); } };
  }

  window.Preview3D = { TYPES: TYPES, GROUPS: GROUPS, generate: generate, estimate: estimate, createViewer: createViewer };
})();
