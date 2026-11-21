/* PenguinSlicer mockup, version 5: the faces an instance can be laid on, found on its part's
 * convex hull, as Orca Slicer's "Lay on face" tool offers them. Written afresh from our own
 * note (docs/research/2026-11-21-lay-on-face-hull-faces.md); no Orca code is used.
 *
 *   1. the convex hull of the part's corners (an incremental hull, built here);
 *   2. hull triangles that meet along an edge and point the same way (within a quarter of a
 *      degree) form one flat face;
 *   3. a face is dropped when it is a lone triangle with a side under 1 mm, when its outline
 *      covers under 5 mm², or when its outline has a corner sharper than 1 degree; the 254
 *      largest of the rest are kept (the filters and figures Orca uses);
 *   4. our own rule for round parts: a face is dropped when a neighbouring hull face bends
 *      away from it by under 20 degrees and is at least half its size. Those are the thin
 *      facets of a round side (a pulley's rim), not faces a student would choose.
 * Each face kept is drawn as a patch: its outline drawn in 10% toward its middle, its corners
 * rounded by corner cutting, raised 0.1 mm off the face. Worked out in the browser the first
 * time a part's faces are asked for, and timed. */
(function () {
  'use strict';
  var T = THREE;
  var ON_PLANE = 1e-3;             // mm: a point this close to a hull plane counts as on it
  var SAME_FACE_DEG = 0.25;        // hull triangles pointing the same way within this are one face
  var SMALLEST_FACE_MM2 = 5;                // mm²: smaller faces are not offered (Orca's figure)
  var SHORTEST_LONE_EDGE_MM = 1;                // mm: a face that is one triangle with a side this short is dropped
  var SLIVER_CORNER_DEG = 1;          // a corner sharper than this marks a sliver
  var FACES_OFFERED_CAP = 254;             // at most this many faces, the largest (Orca's figure)
  var BEND_DEG = 20;               // ours: a neighbour bending away less than this ...
  var BEND_SHARE = 0.5;            // ... and at least this share of the face's size makes it a facet of a round side
  var SHRINK = 0.9, ROUNDINGS = 4, LIFT = 0.1;

  /* ------------------------------------------------------------ the distinct corners */
  function corners(pos) {
    var seen = {}, out = [];
    for (var i = 0; i < pos.length; i += 3) {
      var k = Math.round(pos[i] * 1000) + ',' + Math.round(pos[i + 1] * 1000) + ',' + Math.round(pos[i + 2] * 1000);
      if (seen[k]) continue;
      seen[k] = true; out.push(new T.Vector3(pos[i], pos[i + 1], pos[i + 2]));
    }
    return out;
  }

  /* ------------------------------------------------------------ the convex hull */
  // Start from a tetrahedron of far-apart corners; add the other corners one at a time in a
  // fixed shuffled order. A corner outside the hull sees some of its triangles: those go, and
  // the edges between seen and unseen triangles (the horizon) are joined to the new corner.
  function convexHull(P) {
    var n = P.length, faces = [], edges = new Map();
    function key(a, b) { return a * n + b; }
    function addFace(a, b, c) {
      var e1 = new T.Vector3().subVectors(P[b], P[a]), e2 = new T.Vector3().subVectors(P[c], P[a]);
      var nn = new T.Vector3().crossVectors(e1, e2), L = nn.length();
      var f = { v: [a, b, c], n: L > 1e-12 ? nn.divideScalar(L) : new T.Vector3(), area: L / 2, alive: true };
      f.d = f.n.dot(P[a]);
      faces.push(f);
      edges.set(key(a, b), f); edges.set(key(b, c), f); edges.set(key(c, a), f);
      return f;
    }
    function far(fn) { var best = -1, bi = -1; for (var i = 0; i < n; i++) { var s = fn(P[i]); if (s > best) { best = s; bi = i; } } return bi; }
    var i0 = 0; for (var i = 1; i < n; i++) if (P[i].x < P[i0].x) i0 = i;
    var i1 = far(function (p) { return p.distanceToSquared(P[i0]); });
    var dir = new T.Vector3().subVectors(P[i1], P[i0]).normalize();
    var i2 = far(function (p) { var v = new T.Vector3().subVectors(p, P[i0]); return v.lengthSq() - Math.pow(v.dot(dir), 2); });
    var pn = new T.Vector3().crossVectors(new T.Vector3().subVectors(P[i1], P[i0]), new T.Vector3().subVectors(P[i2], P[i0])).normalize();
    var i3 = far(function (p) { return Math.abs(pn.dot(new T.Vector3().subVectors(p, P[i0]))); });
    var start = [i0, i1, i2, i3];
    // the tetrahedron's four triangles, each turned to face away from the corner opposite it
    [[i0, i1, i2, i3], [i0, i1, i3, i2], [i0, i2, i3, i1], [i1, i2, i3, i0]].forEach(function (t) {
      var a = t[0], b = t[1], c = t[2], o = P[t[3]];
      var nn = new T.Vector3().crossVectors(new T.Vector3().subVectors(P[b], P[a]), new T.Vector3().subVectors(P[c], P[a]));
      if (nn.dot(new T.Vector3().subVectors(o, P[a])) > 0) addFace(a, c, b); else addFace(a, b, c);
    });
    // a fixed shuffle, so the hull (and the faces) come out the same on every load
    var order = [], seed = 12345;
    for (var j = 0; j < n; j++) if (start.indexOf(j) < 0) order.push(j);
    for (var s = order.length - 1; s > 0; s--) { seed = (seed * 1103515245 + 12345) % 2147483648; var r = seed % (s + 1), tmp = order[s]; order[s] = order[r]; order[r] = tmp; }
    var live = faces.slice();
    order.forEach(function (pi) {
      var p = P[pi], seen = live.filter(function (f) { return f.n.dot(p) - f.d > ON_PLANE; });
      if (!seen.length) return;
      seen.forEach(function (f) { f.seen = true; });
      var horizon = [];
      seen.forEach(function (f) {
        for (var k = 0; k < 3; k++) {
          var a = f.v[k], b = f.v[(k + 1) % 3], other = edges.get(key(b, a));
          if (other && !other.seen) horizon.push([a, b]);
        }
      });
      seen.forEach(function (f) {
        f.alive = false;
        for (var k = 0; k < 3; k++) { var kk = key(f.v[k], f.v[(k + 1) % 3]); if (edges.get(kk) === f) edges.delete(kk); }
      });
      horizon.forEach(function (e) { addFace(e[0], e[1], pi); });
      live = faces.filter(function (f) { return f.alive; });
    });
    live.forEach(function (f, idx) { f.id = idx; });
    return { tris: live, neighbour: function (f, k) { return edges.get(key(f.v[(k + 1) % 3], f.v[k])); } };
  }

  /* ------------------------------------------------------------ flat outlines */
  function outline2(pts) {                       // the convex outline of points in a plane, anticlockwise
    var q = pts.slice().sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    if (q.length < 3) return q;
    function turn(o, a, b) { return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]); }
    var lo = [], hi = [], i;
    for (i = 0; i < q.length; i++) { while (lo.length > 1 && turn(lo[lo.length - 2], lo[lo.length - 1], q[i]) <= 1e-9) lo.pop(); lo.push(q[i]); }
    for (i = q.length - 1; i >= 0; i--) { while (hi.length > 1 && turn(hi[hi.length - 2], hi[hi.length - 1], q[i]) <= 1e-9) hi.pop(); hi.push(q[i]); }
    lo.pop(); hi.pop();
    return lo.concat(hi);
  }
  function areaOf(poly) {
    var a = 0;
    for (var i = 0; i < poly.length; i++) { var p = poly[i], q = poly[(i + 1) % poly.length]; a += p[0] * q[1] - q[0] * p[1]; }
    return Math.abs(a) / 2;
  }
  function sharpestCorner(poly) {                // degrees
    var min = 180;
    for (var i = 0; i < poly.length; i++) {
      var p = poly[(i + poly.length - 1) % poly.length], c = poly[i], q = poly[(i + 1) % poly.length];
      var ax = p[0] - c[0], ay = p[1] - c[1], bx = q[0] - c[0], by = q[1] - c[1];
      var cos = (ax * bx + ay * by) / (Math.hypot(ax, ay) * Math.hypot(bx, by) || 1);
      min = Math.min(min, Math.acos(Math.max(-1, Math.min(1, cos))) * 180 / Math.PI);
    }
    return min;
  }
  function narrowest(poly) {                     // the outline's least width, for the record
    var w = Infinity;
    for (var i = 0; i < poly.length; i++) {
      var a = poly[i], b = poly[(i + 1) % poly.length], L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, far = 0;
      poly.forEach(function (p) { far = Math.max(far, Math.abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / L); });
      w = Math.min(w, far);
    }
    return w;
  }
  function middle(poly) {                        // the outline's centre of area
    var cx = 0, cy = 0, A = 0;
    for (var i = 0; i < poly.length; i++) {
      var p = poly[i], q = poly[(i + 1) % poly.length], c = p[0] * q[1] - q[0] * p[1];
      A += c; cx += (p[0] + q[0]) * c; cy += (p[1] + q[1]) * c;
    }
    return A ? [cx / (3 * A), cy / (3 * A)] : poly[0];
  }
  // The patch: the outline drawn in toward its middle, then its corners cut off again and again
  // (each pass replaces every side by the points a quarter and three quarters along it), which
  // leaves a rounded shape inside the face.
  function patch(poly) {
    var c = middle(poly), pts = poly.map(function (p) { return [c[0] + (p[0] - c[0]) * SHRINK, c[1] + (p[1] - c[1]) * SHRINK]; });
    for (var r = 0; r < ROUNDINGS; r++) {
      var next = [];
      for (var i = 0; i < pts.length; i++) {
        var a = pts[i], b = pts[(i + 1) % pts.length];
        next.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25], [a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
      }
      pts = next;
    }
    return { ring: pts, middle: c };
  }

  /* ------------------------------------------------------------ the faces */
  var cache = {};
  function compute(key) {
    if (cache[key]) return cache[key];
    var def = MockParts.byKey[key], t0 = performance.now();
    var P = corners(def.geometry.attributes.position.array);
    var H = convexHull(P), tris = H.tris, cosSame = Math.cos(SAME_FACE_DEG * Math.PI / 180);
    // 2. join hull triangles into flat faces: from a first triangle, spread across edges to
    //    triangles that point the same way as that first one
    var groups = [], groupOf = new Map();
    tris.forEach(function (t0) {
      if (groupOf.has(t0) || t0.area < 1e-12) return;
      var g = { tris: [], id: groups.length }, stack = [t0];
      groupOf.set(t0, g); groups.push(g);
      while (stack.length) {
        var t = stack.pop(); g.tris.push(t);
        for (var k = 0; k < 3; k++) {
          var nb = H.neighbour(t, k);
          if (nb && !groupOf.has(nb) && nb.area >= 1e-12 && nb.n.dot(t0.n) > cosSame) { groupOf.set(nb, g); stack.push(nb); }
        }
      }
    });
    groups.forEach(function (g) {
      var n = new T.Vector3(), ids = {};
      g.tris.forEach(function (t) { n.addScaledVector(t.n, t.area); t.v.forEach(function (v) { ids[v] = true; }); });
      n.normalize(); g.n = n;
      var u = (Math.abs(n.z) < 0.9 ? new T.Vector3(0, 0, 1) : new T.Vector3(1, 0, 0)).cross(n).normalize(), w = new T.Vector3().crossVectors(n, u);
      var verts = Object.keys(ids).map(function (i) { return P[+i]; }), d = 0;
      verts.forEach(function (v) { d += n.dot(v); }); d /= verts.length;
      g.u = u; g.w = w; g.d = d;
      g.poly = outline2(verts.map(function (v) { return [v.dot(u), v.dot(w)]; }));
      g.area = areaOf(g.poly);
      g.lone = g.tris.length === 1;
      g.shortSide = g.lone ? Math.min(P[g.tris[0].v[0]].distanceTo(P[g.tris[0].v[1]]), P[g.tris[0].v[1]].distanceTo(P[g.tris[0].v[2]]), P[g.tris[0].v[2]].distanceTo(P[g.tris[0].v[0]])) : Infinity;
      g.corner = sharpestCorner(g.poly);
      g.width = narrowest(g.poly);
      // neighbouring faces, for our rule
      g.next = {};
      g.tris.forEach(function (t) { for (var k = 0; k < 3; k++) { var nb = H.neighbour(t, k), ng = nb && groupOf.get(nb); if (ng && ng !== g) g.next[ng.id] = ng; } });
    });
    // 3. Orca's filters, then 4. our rule for round parts. Each face keeps the reason it went.
    var cosBend = Math.cos(BEND_DEG * Math.PI / 180), largest = 0;
    groups.forEach(function (g) {
      if (g.lone && g.shortSide < SHORTEST_LONE_EDGE_MM) g.dropped = 'lone thin triangle';
      else if (g.area < SMALLEST_FACE_MM2) g.dropped = 'under ' + SMALLEST_FACE_MM2 + ' mm²';
      else if (g.corner < SLIVER_CORNER_DEG) g.dropped = 'sliver corner';
      if (!g.dropped) largest = Math.max(largest, g.area);
    });
    var orca = groups.filter(function (g) { return !g.dropped; }).sort(function (a, b) { return b.area - a.area; });
    orca.slice(FACES_OFFERED_CAP).forEach(function (g) { g.dropped = 'beyond the ' + FACES_OFFERED_CAP + ' largest'; });
    orca = orca.slice(0, FACES_OFFERED_CAP);
    orca.forEach(function (g) {
      g.share = g.area / largest;
      g.bend = 180;
      Object.keys(g.next).forEach(function (id) {
        var o = g.next[id], ang = Math.acos(Math.max(-1, Math.min(1, o.n.dot(g.n)))) * 180 / Math.PI;
        g.bend = Math.min(g.bend, ang);
        if (ang < BEND_DEG && o.area >= BEND_SHARE * g.area) g.round = true;
      });
    });
    var kept = orca.filter(function (g) { return !g.round; });
    // the patch of each face kept, in the part's own coordinates; and how tall the part
    // stands laid on it
    var faces = kept.map(function (g) {
      var pt = patch(g.poly), n = g.n, lift = g.d + LIFT;
      function to3(p) { return new T.Vector3().addScaledVector(g.u, p[0]).addScaledVector(g.w, p[1]).addScaledVector(n, lift); }
      var centre = to3(pt.middle), ring = pt.ring.map(to3), arr = new Float32Array(ring.length * 9);
      ring.forEach(function (a, i) {
        var b = ring[(i + 1) % ring.length];
        arr.set([centre.x, centre.y, centre.z, a.x, a.y, a.z, b.x, b.y, b.z], i * 9);
      });
      var geo = new T.BufferGeometry(); geo.setAttribute('position', new T.BufferAttribute(arr, 3));
      var lo = Infinity; P.forEach(function (v) { lo = Math.min(lo, n.dot(v)); });
      return { n: n.clone(), area: g.area, width: g.width, height: g.d - lo, centre: centre, geometry: geo };
    });
    var ms = performance.now() - t0;
    cache[key] = {
      faces: faces, ms: ms,
      record: { corners: P.length, hullTriangles: tris.length, hullFaces: groups.length, orcaOffers: orca.length, offered: faces.length,
                dropped: groups.filter(function (g) { return g.dropped; }).length, round: orca.length - faces.length,
                faces: orca.map(function (g) { return { area: +g.area.toFixed(1), width: +g.width.toFixed(1), share: +g.share.toFixed(3), bend: +g.bend.toFixed(1), round: !!g.round }; }) }
    };
    return cache[key];
  }

  window.MockHullFaces = { faces: compute, BEND_DEG: BEND_DEG, BEND_SHARE: BEND_SHARE };
})();
