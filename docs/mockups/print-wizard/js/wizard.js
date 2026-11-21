/* PenguinSlicer mockup, version 4: the wizard in the panel. Five steps (Setup, Parts,
 * Layout, Preview, Send), advanced mode, mocked export with its two ways to fail, slicing
 * progress, layer preview, the Send step with delivery and print progress, the printer
 * status in the header, coming back to running work, and every armed error from the
 * scenario strip. Everything here is fake: no request leaves the page. */
(function () {
  'use strict';
  var T = THREE, P = MockParts, ST = MockSettings, PL = MockPlate;
  var PLATE = ST.PRINTER.plate;
  var ORDER = ['setup', 'parts', 'layout', 'preview', 'send'];
  var MAX_INSTANCES = 150;                                // the slice service's limit (slice/limits.py)
  var PLATE_VOLUME_CAP_CM3 = 600;                         // invented: a volume cap from the memory model
  var SLICE_TIMEOUT_S = 240;                              // print/limits.py PLATE_SLICE_TIMEOUT_S
  var TOO_MANY_INSTANCES_MESSAGE = 'Up to ' + MAX_INSTANCES + ' instances per plate; print the rest on a second plate.';
  var ME = 'Sam Rivera', OTHER = 'Alex Chen';             // Onshape names: this student, and another
  var RETRY_SLOW_S = 4, RETRY_GIVE_UP_S = 20;             // our server: "taking longer" after 4 s, give up after 20 s

  function $(s) { return document.querySelector(s); }
  function $all(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, fn, cls) { var b = el('button', 'btn small' + (cls ? ' ' + cls : ''), label); b.type = 'button'; b.addEventListener('click', fn); return b; }

  /* ------------------------------------------------------------------ mock controls */
  var Mock = {
    armed: [], speed: 'fast',
    factor: function (kind) {
      var fast = this.speed === 'fast';
      if (kind === 'print') return fast ? 900 : 60;
      if (kind === 'other') return fast ? 30 : 1;          // someone else's print: slow enough to watch the busy printer
      if (kind === 'export') return fast ? 3 : 1;
      return fast ? 6 : 1;
    },
    has: function (k) { return this.armed.indexOf(k) >= 0; },
    take: function (k) { var i = this.armed.indexOf(k); if (i < 0) return false; this.armed.splice(i, 1); if (this.onChange) this.onChange(); return true; },
    arm: function (k) { if (!this.has(k)) this.armed.push(k); if (this.onChange) this.onChange(); },
    disarm: function (k) { var i = this.armed.indexOf(k); if (i >= 0) this.armed.splice(i, 1); if (this.onChange) this.onChange(); }
  };

  /* ------------------------------------------------------------------ state */
  var S;
  function fresh(ctx) {
    return { ctx: ctx, step: 'setup', filament: 'petg', profile: 'structural', changes: {}, parts: [], instances: [],
             selected: [], nextId: 1, laidOut: false, problems: [], job: null, result: null, resultSig: null,
             action: 'print', layer: 0, advTab: 'Quality', advSearch: '', advOnlyChanged: false, advTier: 'common', advOpen: {},
             layoutNotes: [], previewMsg: null, undo: [], redo: [], hiddenTypes: {}, notices: [] };
  }
  // The choices made in the scenario strip; they outlast Reset, since they are the owner's,
  // not the student's: how an instance is laid on a face, the mouse scheme, how parts arrive.
  var Opt = { lay: 'strip', scheme: 'O', arrival: 'auto' };
  function profileObj() { return ST.PROFILES.filter(function (p) { return p.id === S.profile; })[0]; }
  function filamentObj() { return ST.FILAMENTS.filter(function (f) { return f.id === S.filament; })[0]; }
  function eff() {
    var v = {}, pv = profileObj().values;
    Object.keys(pv).forEach(function (k) { v[k] = pv[k]; });
    Object.keys(S.changes).forEach(function (k) { v[k] = S.changes[k]; });
    return v;
  }
  function setSetting(key, value) {
    var pv = profileObj().values[key];
    if (value === pv) delete S.changes[key]; else S.changes[key] = value;
  }
  function changeCount() { return Object.keys(S.changes).length; }
  function partById(id) { return S.parts.filter(function (p) { return p.id === id; })[0]; }
  function instanceById(id) { return S.instances.filter(function (c) { return c.id === id; })[0]; }
  function instanceLabel(c) {
    var n = 0, name = partById(c.partId) ? partById(c.partId).name : P.byKey[c.partKey].name;
    for (var i = 0; i < S.instances.length; i++) { if (S.instances[i].partId === c.partId) n++; if (S.instances[i] === c) break; }
    return name + ' #' + n;
  }
  function totalInstances() { return S.parts.reduce(function (a, p) { return a + (p.status === 'ready' ? p.qty : 0); }, 0); }
  function docName() { return S.ctx === 'standalone' ? 'Upload' : P.PART_STUDIO.name; }
  // A plate is named to a student in words ("Plate 1, 16 instances"), never by the sliced
  // file's generated name. The mockup has one plate per Part Studio, so it is always Plate 1.
  function plateName(n) { return 'Plate 1, ' + n + ' instance' + (n === 1 ? '' : 's'); }

  /* ------------------------------------------------------------------ time */
  var jobs = [];
  var last = performance.now();
  setInterval(function () {
    var now = performance.now(), dt = Math.min(0.5, (now - last) / 1000); last = now;
    jobs.slice().forEach(function (j) { j.tick(dt); });
  }, 100);
  function addJob(j) { jobs.push(j); return j; }
  function dropJob(j) { var i = jobs.indexOf(j); if (i >= 0) jobs.splice(i, 1); }
  function after(mockSeconds, kind, fn) {          // a one-shot timer on the mock clock
    var t = 0, j = addJob({ tick: function (dt) { t += dt * Mock.factor(kind); if (t >= mockSeconds) { dropJob(j); fn(); } } });
    return j;
  }
  function clock(s) { s = Math.max(0, Math.floor(s)); return Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2); }
  function hm(s) { s = Math.round(s / 60); var h = Math.floor(s / 60), m = s % 60; return h ? h + ' h ' + m + ' min' : m + ' min'; }
  function sizeText(sz) { return sz.x + ' × ' + sz.y + ' × ' + sz.z + ' mm'; }
  function clockTime(d) {                               // a time of day, as a student reads a clock
    var h = d.getHours(), m = d.getMinutes(), pm = h >= 12; h = h % 12 || 12;
    return h + ':' + ('0' + m).slice(-2) + (pm ? ' pm' : ' am');
  }

  /* ------------------------------------------------------------------ messages */
  // what happened; what to do next; remedy buttons; optional words for a mentor. The mentor's
  // words say what is wrong with the part or the plate and where to look in Onshape or at the
  // printer; never a route, a status code, a page id or anything else inside PenguinSlicer.
  function msg(kind, what, todo, acts, mentor) {
    var d = el('div', 'msg ' + kind);
    d.appendChild(el('div', 'what', what));
    if (todo) d.appendChild(el('div', 'todo', todo));
    if (acts && acts.length) {
      var a = el('div', 'acts');
      acts.forEach(function (x) { a.appendChild(btn(x[0], x[1], x[2])); });
      d.appendChild(a);
    }
    if (mentor) {
      var det = el('details'); det.appendChild(el('summary', null, 'For a mentor'));
      det.appendChild(el('div', null, mentor)); d.appendChild(det);
    }
    return d;
  }
  // A notification: at the top of the step, until the student closes it (×) or it is replaced.
  // Used when something happened that is not on a row of a list: a part that did not arrive.
  function notify(kind, what, todo, key) {
    S.notices = S.notices.filter(function (n) { return !key || n.key !== key; });
    S.notices.push({ kind: kind, what: what, todo: todo, key: key || ('n' + Math.random()) });
    renderNotices();
  }
  function renderNotices() {
    var box = $('#notices'); box.innerHTML = '';
    S.notices.forEach(function (n) {
      var d = el('div', 'notice ' + n.kind), b = el('div', 'n-body');
      b.appendChild(el('div', 'n-what', n.what)); if (n.todo) b.appendChild(el('div', 'n-todo', n.todo));
      d.appendChild(b);
      var x = el('button', 'n-x', '×'); x.type = 'button'; x.title = 'Close'; x.setAttribute('aria-label', 'Close this notification');
      x.addEventListener('click', function () { S.notices = S.notices.filter(function (m) { return m !== n; }); renderNotices(); });
      d.appendChild(x); box.appendChild(d);
    });
  }

  /* ------------------------------------------------------------------ thumbnails */
  var thumbR = null, thumbs = {};
  function thumbRenderer(px) {
    if (!thumbR) thumbR = new T.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    thumbR.setSize(px, px);
    return thumbR;
  }
  // A small picture of a part lying one way, seen from the front and above, on a patch of
  // plate so that "down" reads at a glance. Cached per part and position.
  function restThumb(key, idx, q) {
    var ck = key + '#' + idx;
    if (thumbs[ck] !== undefined) return thumbs[ck];
    try {
      var r = thumbRenderer(104), def = P.byKey[key], scene = new T.Scene();
      Layout3D.lights(scene);
      var m = new T.Mesh(def.geometry, new T.MeshStandardMaterial({ color: def.color, flatShading: true, roughness: 0.6 }));
      m.quaternion.copy(q); m.updateMatrixWorld();
      var box = new T.Box3().setFromObject(m), c = new T.Vector3(), sz = new T.Vector3(); box.getCenter(c); box.getSize(sz);
      m.position.set(-c.x, -c.y, -box.min.z); scene.add(m);
      var span = Math.max(sz.x, sz.y, sz.z);
      var pl = new T.Mesh(new T.PlaneGeometry(Math.max(sz.x, sz.y) * 1.25 + 6, Math.max(sz.x, sz.y) * 1.25 + 6), new T.MeshBasicMaterial({ color: 0xdde2e8 }));
      pl.position.z = -0.2; scene.add(pl);
      var cam = new T.PerspectiveCamera(30, 1, 0.5, 10000); cam.up.set(0, 0, 1);
      var dist = span * 0.62 / Math.sin(15 * Math.PI / 180);
      cam.position.set(dist * 0.35, -dist * 0.8, sz.z / 2 + dist * 0.5); cam.lookAt(0, 0, sz.z / 2);
      r.render(scene, cam);
      thumbs[ck] = r.domElement.toDataURL();
    } catch (e) { thumbs[ck] = ''; }
    return thumbs[ck];
  }
  function thumb(key) {
    if (thumbs[key]) return thumbs[key];
    try {
      thumbRenderer(80);
      var def = P.byKey[key], scene = new T.Scene();
      Layout3D.lights(scene);
      scene.add(new T.Mesh(def.geometry, new T.MeshStandardMaterial({ color: def.color, flatShading: true, roughness: 0.6 })));
      var r = def.geometry.boundingSphere || (def.geometry.computeBoundingSphere(), def.geometry.boundingSphere);
      var cam = new T.PerspectiveCamera(30, 1, 1, 5000); cam.up.set(0, 0, 1);
      var dist = r.radius / Math.sin(15 * Math.PI / 180) * 1.05;
      cam.position.set(dist * 0.55, -dist * 0.7, dist * 0.45); cam.lookAt(0, 0, 0);
      thumbR.render(scene, cam);
      thumbs[key] = thumbR.domElement.toDataURL();
    } catch (e) { thumbs[key] = ''; }
    return thumbs[key];
  }

  /* ================================================================== navigation */
  // Next is gated only by what the next step needs. A part still arriving never holds it.
  function canLeave(step) {
    if (step === 'parts') {
      var ready = S.parts.filter(function (p) { return p.status === 'ready'; }).length;
      return ready > 0 && totalInstances() <= MAX_INSTANCES;
    }
    if (step === 'layout') return S.instances.length > 0 && S.problems.length === 0;
    if (step === 'preview') return sliceReady();
    return true;
  }
  function sliceReady() { return !!S.result && S.resultSig === signature() && !(S.job && S.job.state === 'running'); }
  function navigateTo(name) {
    var target = ORDER.indexOf(name), cur = ORDER.indexOf(S.step);
    if (target === cur) return;
    if (target > cur) { for (var i = cur; i < target; i++) { if (i === 2) enterLayoutData(); if (!canLeave(ORDER[i])) return; } }
    gotoStep(name);
  }
  // Moving back and forth always works. Leaving the Preview step while it slices leaves the
  // slice running on the server; coming back to it with the same plate finds it still going,
  // or finished. A changed plate starts a new slice (see enterPreview).
  function gotoStep(name) {
    if (S.step !== name) S.notices = [];     // a notification belongs to the step it was given on
    S.step = name;
    closePrinterPop();
    $all('#wizard .step').forEach(function (s) { s.hidden = s.getAttribute('data-step') !== name; });
    $all('#stepbar li').forEach(function (li) {
      var s = li.getAttribute('data-step');
      li.classList.toggle('active', s === name);
      li.classList.toggle('done', ORDER.indexOf(s) < ORDER.indexOf(name));
    });
    $('#btn-back').disabled = name === 'setup';
    $('#btn-next').hidden = name === 'send';
    $('#final-action').hidden = name !== 'send';
    $('#do-menu').hidden = true;
    $('#wiz-body').scrollTop = 0;
    if (name === 'setup') renderSetup();
    if (name === 'parts') renderParts();
    if (name === 'layout') enterLayout();
    if (name === 'preview') enterPreview();
    if (name === 'send') renderSend();
    updateNext(); updateSummary(); renderNotices();
  }
  function updateNext() {
    if (S.step !== 'send') $('#btn-next').disabled = !canLeave(S.step);
    var b = $('#btn-do'), ready = sliceReady(), why = sendBlocked();
    if (S.action === 'download') { b.textContent = 'Download the sliced file'; b.disabled = !ready; }
    else {
      var mine = PRN.job && PRN.job.mine && isLive(PRN.job);
      // while this student's plate is on its way or printing, the button says so and cannot send again
      var ph = mine ? PRN.job.phase : null;
      b.textContent = mine ? (ph === 'upload' || ph === 'starting' ? 'Sending…' : ph === 'prepare' ? 'Heating…' : ph === 'waiting' ? 'Waiting for a person…' : 'Printing…')
        : PRN.paired ? 'Send to ' + ST.PRINTER.name : 'Send to printer';
      b.disabled = !ready || !!why;
    }
    $('#btn-do-caret').disabled = !ready;
  }
  function updateSummary() {
    var box = $('#wiz-summary'), idx = ORDER.indexOf(S.step);
    box.innerHTML = '';
    if (idx < 1) { box.hidden = true; return; }
    box.hidden = false;
    function chip(t, cls) { box.appendChild(el('span', 'chip' + (cls ? ' ' + cls : ''), t)); }
    chip(filamentObj().type); chip(profileObj().name);
    var n = changeCount(); if (n) chip('+' + n + ' change' + (n > 1 ? 's' : ''), 'adv');
    if (idx >= 2) {
      var parts = S.parts.filter(function (p) { return p.status === 'ready'; }).length;
      chip(parts + ' part' + (parts === 1 ? '' : 's') + ' · ' + totalInstances() + ' instance' + (totalInstances() === 1 ? '' : 's'));
    }
    if (idx >= 3 && S.instances.length) {
      var b = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
      S.instances.forEach(function (c) { var h = PL.bbox(PL.worldHull(c)); b.minX = Math.min(b.minX, h.minX); b.maxX = Math.max(b.maxX, h.maxX); b.minY = Math.min(b.minY, h.minY); b.maxY = Math.max(b.maxY, h.maxY); });
      chip(Math.round(b.maxX - b.minX) + ' × ' + Math.round(b.maxY - b.minY) + ' mm of plate');
    }
    if (idx >= 4 && S.result) chip(hm(S.result.est.seconds) + ' · ' + Math.round(S.result.est.grams) + ' g');
  }

  /* ================================================================== Setup step */
  function renderConfig() {
    var box = $('#config-info');
    box.innerHTML = '';
    var p = el('p', 'config-status');
    p.appendChild(document.createTextNode('Config: '));
    var a = el('a', null, '6238 (Popcorn Penguins)'); a.href = '#'; a.title = 'Open PenguinCAM-config.yaml (mockup: does nothing)';
    a.addEventListener('click', function (e) { e.preventDefault(); });
    p.appendChild(a);
    var r = el('a', 'config-refresh', '↻'); r.href = '#'; r.title = 'Reload team configuration from Onshape';
    r.addEventListener('click', function (e) { e.preventDefault(); });
    p.appendChild(r);
    box.appendChild(p);
    if (S.ctx === 'standalone') box.appendChild(el('p', 'config-status-reason', 'Loaded from your saved team configuration link.'));
  }

  function renderPrinterLine() {
    var box = $('#p-printer'); if (!box) return; box.innerHTML = '';
    // With no printer paired, the line names no printer, only the model the team's profiles slice for.
    if (!PRN.paired) { box.appendChild(el('span', 'pstate off', 'No printer paired')); box.appendChild(el('span', 'model', '(the profiles are for a ' + ST.PRINTER.model + ')')); return; }
    box.appendChild(el('span', null, ST.PRINTER.name));
    box.appendChild(el('span', 'model', ST.PRINTER.model));
    var st = printerStatus(), j = PRN.job;
    box.appendChild(el('span', 'pstate ' + st.chip, st.short));
    if (j && isLive(j) && PRN.online && PRN.paired) box.appendChild(el('span', 'model', 'for ' + (j.mine ? 'you' : j.who) + ', ' + hm(remainingS(j)) + ' left'));
  }

  function fillSelect(sel, options, value) {
    sel.innerHTML = '';
    options.forEach(function (o) { var op = el('option', null, o.text); op.value = o.value; sel.appendChild(op); });
    sel.value = value;
  }

  function renderSetup() {
    renderConfig(); renderPrinterLine();
    fillSelect($('#p-filament'), ST.FILAMENTS.map(function (f) { return { value: f.id, text: f.name + (f.id === 'petg' ? ' (most prints)' : '') }; }), S.filament);
    fillSelect($('#p-profile'), ST.PROFILES.map(function (p) { return { value: p.id, text: p.name }; }), S.profile);
    $('#p-profile-about').textContent = 'For ' + profileObj().about + '. ' + ST.formatValue(ST.byKey.layer_height, profileObj().values.layer_height) + ' layers.';
    // Picking another profile clears every change. Said here, beside the menu, before it happens.
    var nc = changeCount(), clr = $('#p-profile-clears');
    clr.hidden = !nc;
    clr.textContent = nc ? 'Picking another profile clears your ' + (nc === 1 ? 'change' : nc + ' changes') + ' and uses that profile’s own settings.' : '';
    var v = eff(), pv = profileObj().values;
    Object.keys(ST.QUICK).forEach(function (qk) {
      var q = ST.QUICK[qk], s = ST.byKey[q.key], sel = $('#ov-' + qk);
      var opts = [{ value: '', text: 'Default (' + q.text(pv[q.key]) + ')' }];
      q.choices.forEach(function (c) { if (c !== pv[q.key]) opts.push({ value: String(c), text: q.text(c) }); });
      var changed = S.changes.hasOwnProperty(q.key);
      if (changed && q.choices.indexOf(v[q.key]) < 0) opts.push({ value: String(v[q.key]), text: q.text(v[q.key]) + ' (advanced mode)' });
      fillSelect(sel, opts, changed ? String(v[q.key]) : '');
      sel.classList.toggle('changed', changed);
      sel.title = s.label + ' in advanced mode';
    });
    var n = changeCount(), box = $('#adv-effect');
    box.hidden = !n; box.innerHTML = '';
    if (n) {
      var head = el('div'); head.innerHTML = '<strong>' + n + ' setting' + (n > 1 ? 's' : '') + ' changed from ' + profileObj().name + '</strong> for this print:';
      box.appendChild(head);
      var ul = el('ul');
      Object.keys(S.changes).forEach(function (k) {
        var s = ST.byKey[k];
        ul.appendChild(el('li', null, s.group + ' › ' + s.label + ': ' + ST.formatValue(s, S.changes[k]) + ' (profile ' + ST.formatValue(s, pv[k]) + ')'));
      });
      box.appendChild(ul);
      var row = el('div', 'row');
      row.appendChild(btn('Review in advanced mode', openAdvanced));
      row.appendChild(btn('Reset all', function () { S.changes = {}; $('#setup-notes').hidden = true; renderSetup(); updateSummary(); }));
      box.appendChild(row);
    }
    $('#setup-hint').textContent = 'Your team’s configuration lists these printers, filaments and profiles; a mentor changes them there.';
  }

  function bindSetup() {
    $('#p-filament').addEventListener('change', function () { S.filament = this.value; $('#setup-notes').hidden = true; updateSummary(); });
    $('#p-profile').addEventListener('change', function () {
      var n = changeCount();
      S.profile = this.value;
      S.changes = {};
      var notes = $('#setup-notes');
      notes.hidden = !n;
      notes.textContent = n ? 'Cleared your ' + (n === 1 ? 'change' : n + ' changes') + ': this print uses ' + profileObj().name + ' as it is.' : '';
      renderSetup(); updateSummary();
    });
    Object.keys(ST.QUICK).forEach(function (qk) {
      $('#ov-' + qk).addEventListener('change', function () {
        var q = ST.QUICK[qk], raw = this.value;
        if (raw === '') delete S.changes[q.key];
        else {
          var val = q.choices.filter(function (c) { return String(c) === raw; })[0];
          if (val === undefined) val = S.changes[q.key];
          setSetting(q.key, val);
        }
        renderSetup(); updateSummary();
      });
    });
    $('#btn-advanced').addEventListener('click', openAdvanced);
  }

  /* ================================================================== advanced mode */
  var advResetArmed = false;
  // Advanced mode fills the panel, header included; the printer-status icon (and its details)
  // moves into advanced mode's own name line, so it stays visible on top of every step.
  function placePrinterIcon(inAdvanced) {
    closePrinterPop();
    var row = inAdvanced ? $('#adv-brand') : $('#wiz-header .brand-row'), pop = $('#pstat-pop');
    row.appendChild($('#pstat'));
    if (inAdvanced) row.appendChild(pop); else $('#wiz-header').appendChild(pop);
  }
  function openAdvanced() { placePrinterIcon(true); $('#advanced').hidden = false; S.advSearch = ''; $('#adv-search').value = ''; renderAdvanced(); fitAdvanced(); $('#adv-search').focus(); }
  function closeAdvanced() { $('#advanced').hidden = true; placePrinterIcon(false); advResetArmed = false; renderSetup(); updateSummary(); }
  // Advanced mode follows the panel's width (a ResizeObserver, not a media query, so it also
  // follows a panel the student drags wider): a row of tabs when narrow, a rail of tabs on
  // the left from 480 px, and the groups in two columns from 700 px.
  function fitAdvanced() {
    var a = $('#advanced'), w = a.clientWidth;
    if (!w) return;
    a.classList.toggle('wide', w >= 480);
    a.classList.toggle('xwide', w >= 700);
  }
  function inTier(s) { return S.advTier === 'all' || !s.more; }
  function renderAdvanced() {
    var pv = profileObj().values, v = eff(), n = changeCount();
    $('#adv-sub').textContent = profileObj().name + (n ? ', ' + n + ' changed' : ', no changes');
    var ra = $('#adv-reset-all'); ra.disabled = !n; ra.textContent = advResetArmed ? 'Reset all ' + n + '?' : 'Reset all';
    ra.classList.toggle('primary', advResetArmed);
    $all('#adv-tier button').forEach(function (b) { var on = b.getAttribute('data-tier') === S.advTier; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
    var tabs = $('#adv-tabs'); tabs.innerHTML = '';
    ST.GROUPS.forEach(function (g) {
      var b = el('button', g === S.advTab && !S.advSearch ? 'on' : '', g); b.type = 'button'; b.setAttribute('role', 'tab');
      var cnt = Object.keys(S.changes).filter(function (k) { return ST.byKey[k].group === g; }).length;
      if (cnt) b.appendChild(el('span', 'n', String(cnt)));
      b.addEventListener('click', function () { S.advTab = g; S.advSearch = ''; $('#adv-search').value = ''; renderAdvanced(); });
      tabs.appendChild(b);
    });
    var list = $('#adv-list'); list.innerHTML = '';
    var q = S.advSearch.trim().toLowerCase();
    // Search and "Changed only" look through every setting, whatever the Common/All switch says.
    var rows = ST.SETTINGS.filter(function (s) {
      if (S.advOnlyChanged && !S.changes.hasOwnProperty(s.key)) return false;
      if (q) return (s.label + ' ' + s.sub + ' ' + s.group + ' ' + s.key.replace(/_/g, ' ')).toLowerCase().indexOf(q) >= 0;
      return S.advOnlyChanged || (s.group === S.advTab && inTier(s));
    });
    if (!rows.length) { list.appendChild(el('div', 'adv-empty', q ? 'No setting matches “' + S.advSearch + '”.' : 'No settings changed from ' + profileObj().name + '.')); return; }
    // Subgroups collapse. In Common every one starts open; in All only the first, so a long
    // tab reads as a list of headings to open. Search and "Changed only" open them all.
    var groups = [], cur = null, firstOfTab = {};
    rows.forEach(function (s) {
      if (!cur || cur.group !== s.group || cur.sub !== s.sub) { cur = { group: s.group, sub: s.sub, rows: [] }; groups.push(cur); if (!firstOfTab[s.group]) firstOfTab[s.group] = cur; }
      cur.rows.push(s);
    });
    var lastGroup = null, cols = el('div', 'adv-cols');
    groups.forEach(function (g) {
      if ((q || S.advOnlyChanged) && g.group !== lastGroup) cols.appendChild(el('div', 'adv-group', g.group));
      lastGroup = g.group;
      var key = S.advTier + '|' + g.group + '|' + g.sub;
      var ch = g.rows.filter(function (s) { return S.changes.hasOwnProperty(s.key); }).length;
      var open = q || S.advOnlyChanged ? true : (S.advOpen.hasOwnProperty(key) ? S.advOpen[key] : (S.advTier === 'common' || firstOfTab[g.group] === g || ch > 0));
      var box = el('div', 'adv-grp' + (open ? ' open' : ''));
      var head = el('button', 'adv-sub'); head.type = 'button'; head.setAttribute('aria-expanded', open ? 'true' : 'false');
      head.appendChild(el('span', 'car', open ? '▾' : '▸'));
      head.appendChild(el('span', 'nm', g.sub));
      head.appendChild(el('span', 'ct', g.rows.length + (ch ? ' · ' + ch + ' changed' : '')));
      if (ch) head.classList.add('has-changes');
      head.addEventListener('click', function () { S.advOpen[key] = !open; renderAdvanced(); });
      box.appendChild(head);
      if (open) g.rows.forEach(function (s) { box.appendChild(advRow(s, v[s.key], pv[s.key], q)); });
      cols.appendChild(box);
    });
    list.appendChild(cols);
    if (!q && !S.advOnlyChanged) {
      var shown = rows.length, total = ST.SETTINGS.filter(function (s) { return s.group === S.advTab; }).length;
      list.appendChild(el('div', 'adv-mock', S.advTier === 'common'
        ? 'Common shows the ' + shown + ' ' + S.advTab + ' settings teams change most; All settings shows ' + total + '. Mockup note: in Orca this tab has about ' + ST.ORCA_COUNT[S.advTab] + '; the product lists every one, taken from Orca’s own definitions.'
        : 'Mockup note: All settings shows ' + total + ' of Orca’s about ' + ST.ORCA_COUNT[S.advTab] + ' ' + S.advTab + ' settings as a sample; the product lists every one, taken from Orca’s own definitions.'));
    }
  }
  function advRow(s, value, profVal, q) {
    var changed = S.changes.hasOwnProperty(s.key);
    var row = el('div', 'adv-row' + (changed ? ' changed' : ''));
    var id = 'adv-' + s.key;
    var lab = el('label'); lab.htmlFor = id;
    if (q) {
      var i = s.label.toLowerCase().indexOf(q);
      if (i >= 0) { lab.appendChild(document.createTextNode(s.label.slice(0, i))); lab.appendChild(el('mark', null, s.label.slice(i, i + q.length))); lab.appendChild(document.createTextNode(s.label.slice(i + q.length))); }
      else lab.textContent = s.label;
    } else lab.textContent = s.label;
    if (s.quick) lab.title = 'Also on the Setup step as ' + ST.QUICK[s.quick].label;
    var ctl = el('div', 'ctl'), input;
    if (s.type === 'num') {
      input = el('input'); input.type = 'number'; input.step = String(s.step); input.min = String(s.min); input.max = String(s.max); input.value = String(value);
      ctl.appendChild(input); ctl.appendChild(el('span', 'unit', s.unit));
      input.addEventListener('change', function () {
        var x = parseFloat(input.value);
        var bad = row.querySelector('.bad'); if (bad) bad.remove();
        if (isNaN(x) || x < s.min || x > s.max) {
          input.classList.add('invalid');
          row.appendChild(el('div', 'bad', s.label + ' must be between ' + s.min + ' and ' + s.max + (s.unit ? ' ' + s.unit : '') + '. Kept ' + ST.formatValue(s, value) + '.'));
          return;
        }
        if (s.step >= 1) x = Math.round(x);
        setSetting(s.key, x); renderAdvanced();
      });
    } else if (s.type === 'sel') {
      input = el('select');
      s.options.forEach(function (o) { var op = el('option', null, o.text); op.value = o.value; input.appendChild(op); });
      input.value = value;
      input.addEventListener('change', function () { setSetting(s.key, input.value); renderAdvanced(); });
      ctl.appendChild(input);
    } else {
      input = el('input'); input.type = 'checkbox'; input.checked = !!value;
      input.addEventListener('change', function () { setSetting(s.key, input.checked); renderAdvanced(); });
      ctl.appendChild(input);
    }
    input.id = id;
    var reset = el('button', 'reset', '↶'); reset.type = 'button';
    reset.title = 'Undo this change: back to ' + profileObj().name + '’s ' + ST.formatValue(s, profVal);
    reset.setAttribute('aria-label', 'Reset ' + s.label);
    reset.addEventListener('click', function () { delete S.changes[s.key]; renderAdvanced(); });
    row.appendChild(lab); row.appendChild(ctl); row.appendChild(reset);
    if (changed) row.appendChild(el('div', 'was', profileObj().name + ': ' + ST.formatValue(s, profVal)));
    return row;
  }
  function bindAdvanced() {
    $('#adv-back').addEventListener('click', closeAdvanced);
    $('#adv-done').addEventListener('click', closeAdvanced);
    $('#adv-search').addEventListener('input', function () { S.advSearch = this.value; renderAdvanced(); });
    $('#adv-only-changed').addEventListener('change', function () { S.advOnlyChanged = this.checked; renderAdvanced(); });
    $('#adv-reset-all').addEventListener('click', function () {
      if (!advResetArmed) { advResetArmed = true; renderAdvanced(); return; }
      advResetArmed = false; S.changes = {}; renderAdvanced();
    });
    $('#advanced').addEventListener('keydown', function (e) { if (e.key === 'Escape') closeAdvanced(); });
    $all('#adv-tier button').forEach(function (b) {
      b.addEventListener('click', function () { S.advTier = b.getAttribute('data-tier'); renderAdvanced(); });
    });
    if (window.ResizeObserver) new ResizeObserver(fitAdvanced).observe($('#advanced'));
  }

  /* ================================================================== Parts step */
  var partsNote = null;      // one transient message above the list
  function setPartsNote(node) { partsNote = node; renderPartsMessages(); }
  function renderPartsMessages() {
    var box = $('#parts-messages'); box.innerHTML = '';
    if (partsNote) box.appendChild(partsNote);
  }

  function flashRow(part) {
    var li = document.querySelector('[data-part="' + part.id + '"]');
    if (li) { li.classList.remove('flash'); void li.offsetWidth; li.classList.add('flash'); }
  }
  function addPart(key, o) {
    o = o || {};
    var def = P.byKey[key];
    var existing = S.parts.filter(function (p) { return p.key === key && !o.fileName; })[0];
    if (existing && !o.qty) {
      // a click on a part already listed raises its quantity by one, and its row flashes
      existing.qty = Math.min(MAX_INSTANCES, existing.qty + 1);
      partsNote = null; lastAdded = existing.name + ': ' + existing.qty + ' instances.';
      renderParts(); flashRow(existing); updateSummary();
      return existing;
    }
    if (existing && o.qty) { existing.qty = Math.min(MAX_INSTANCES, Math.max(existing.qty, o.qty)); renderParts(); return existing; }
    var part = { id: 'p' + (S.nextId++), key: key, name: o.fileName ? o.fileName.replace(/\.(stl|3mf)$/i, '') : def.name,
                 file: o.fileName || null, qty: o.qty || 1, status: 'exporting', warn: null, error: null, progress: 0, slow: false };
    S.parts.push(part);
    lastAdded = null;
    renderParts();
    exportPart(part, o);
    return part;
  }
  var lastAdded = null;       // the select-status line's last sentence: "HTD Pulley 24T: 2 instances."
  // Bringing a part in. Three ways it can go:
  //  - it arrives (a second or so, with progress on its row);
  //  - Onshape cannot export it (a broken part): a notification, and the part is not added;
  //  - our server cannot be reached: retried quietly; "taking longer than usual" after a few
  //    seconds; a notification only when every retry has failed. The list never holds a
  //    broken entry, and nothing here holds Next.
  function exportPart(part, o) {
    part.status = 'exporting'; part.error = null; part.progress = 0; part.slow = false;
    var fail = o.fail || (!o.noArm && Mock.take('export_fail'));
    var net = !fail && !o.noArm ? (Mock.take('server_down') ? 'down' : Mock.take('server_slow') ? 'slow' : null) : null;
    var warn = o.warn || (!o.noArm && !fail && !net && Mock.take('not_watertight'));
    var need = net === 'slow' ? 9 : net === 'down' ? RETRY_GIVE_UP_S : (o.delay || 0) + 0.7 + Math.random() * 0.8;
    var t = 0;
    // A network outage runs on the real clock; an export on the mock clock.
    var j = addJob({ tick: function (dt) {
      if (S.parts.indexOf(part) < 0) { dropJob(j); return; }
      t += net ? dt : dt * Mock.factor('export');
      part.progress = net === 'down' ? Math.min(0.85, t / RETRY_GIVE_UP_S) : Math.min(0.97, t / need);
      var slowNow = !!net && t >= RETRY_SLOW_S;
      if (slowNow !== part.slow) { part.slow = slowNow; renderParts(); } else updateArriveRow(part);
      if (t < need) return;
      dropJob(j);
      if (o.refresh && (fail || net === 'down')) {
        // bringing in a new version failed: the version already in the list stays
        part.status = 'ready'; part.progress = 1; part.slow = false; renderParts(); updateNext();
        notify('error', 'Could not bring in the new version of ' + part.name + '; the list keeps the version you had.',
          fail ? 'The part is probably broken in Onshape now: a mechanical mentor can check that it is one closed solid and that its Part Studio rebuilds with no errors.'
               : 'PenguinSlicer’s server did not answer for ' + RETRY_GIVE_UP_S + ' seconds. Check that this computer is online, then press ↻ again.', 'refresh-' + part.id);
        return;
      }
      if (fail) { dropPart(part); failNotice(part, 'export'); }
      else if (net === 'down') { dropPart(part); failNotice(part, 'server'); }
      else arrived(part, warn);
    } });
  }
  function dropPart(part) { S.parts = S.parts.filter(function (q) { return q !== part; }); renderParts(); updateNext(); updateSummary(); }
  // Called after the part was dropped from the list. "Your other parts are fine" is said only
  // while the list holds other parts that arrived; a repeat for the same part replaces its notice.
  function failNotice(part, why) {
    var others = S.parts.some(function (p) { return p.status === 'ready'; });
    var fine = others ? (why === 'export' && S.ctx !== 'standalone' ? 'Your other parts are fine, and you can go on without it. ' : 'Your other parts are fine. ') : '';
    var key = 'fail-' + why + '-' + (S.ctx === 'standalone' ? part.file : part.key);
    if (why === 'export' && S.ctx === 'standalone') {
      notify('error', 'Could not read ' + part.file + ', so it was not added: it is not a valid STL or 3MF file.',
        fine + 'Export it again from your CAD program as STL in millimetres, then upload the new file.', key);
    } else if (why === 'export') {
      notify('error', 'Onshape could not export ' + part.name + ', so it was not added.',
        fine + 'The part itself is probably broken in Onshape: a mechanical mentor can check that ' + part.name +
        ' is one closed solid (not a surface, and not several bodies) and that its Part Studio rebuilds with no errors (no red features in the feature list). Then click it again.', key);
    } else {
      notify('error', 'Could not bring in ' + part.name + ': PenguinSlicer’s server did not answer for ' + RETRY_GIVE_UP_S + ' seconds, so it was not added.',
        fine + 'Check that this computer is online, then ' + (S.ctx === 'standalone' ? 'upload ' + part.file + ' again.' : 'click ' + part.name + ' in Onshape again.') + ' If it keeps happening, tell a mentor.', key);
    }
  }
  function arrived(part, warn) {
    part.status = 'ready'; part.progress = 1; part.slow = false;
    if (warn) part.warn = { what: part.name + ' is not watertight: its mesh has 14 open edges in 2 places.', todo: 'It may still slice and print. If the slice fails, a mentor can look in Onshape for faces that do not meet, then ' + (S.ctx === 'standalone' ? 'upload the repaired file.' : 'press ↻ on this row to bring in the repaired version.') };
    renderParts();
    // It may arrive after the student moved on. On the Layout step it joins the plate at once;
    // later than that, it joins the plate the next time the Layout step is shown.
    if (S.step === 'layout') {
      enterLayoutData(); layHint = msg('ok', part.name + ' arrived and joined the plate.', null);
      editor.sync(); scheduleLayoutRender();
    } else if (ORDER.indexOf(S.step) > 2) {
      notify('info', part.name + ' arrived after you left the Parts step.', 'It is in the list of parts, and joins the plate when you go back to the Layout step.', 'late-' + part.id);
    }
    updateNext(); updateSummary();
  }
  function updateArriveRow(part) {
    var li = document.querySelector('[data-part="' + part.id + '"] .arrive-bar div');
    if (li) li.style.width = Math.round(part.progress * 100) + '%';
  }

  function renderParts() {
    var ctx = S.ctx;
    $('#parts-onshape').hidden = ctx === 'standalone';
    $('#parts-upload').hidden = ctx !== 'standalone';
    $('#parts-assembly').hidden = ctx !== 'assembly';
    var busy = S.parts.some(function (p) { return p.status === 'exporting'; });
    var ss = $('#select-status');
    ss.classList.toggle('busy', busy);
    ss.innerHTML = '';
    if (busy) { ss.appendChild(el('span', 'spin')); ss.appendChild(document.createTextNode(' Bringing parts in from Onshape… keep clicking to add more.')); }
    else ss.textContent = lastAdded ? 'Added one more: ' + lastAdded : (ctx === 'assembly' ? 'Click a part in the assembly…' : 'Click a part in Onshape…');
    $('#parts-hint').textContent = ctx === 'assembly'
      ? 'Click instances in the list or the graphics area to add one part at a time, or bring them all in with the button. Click a part again for one more.'
      : 'Click a part in the Parts list or the graphics area; it comes in automatically. Click it again for one more, or set the quantity on its row.';
    renderPartsMessages();
    var list = $('#parts-list'); list.innerHTML = '';
    S.parts.forEach(function (p) {
      var def = P.byKey[p.key];
      var li = el('li', 'part-item' + (p.status === 'exporting' ? ' arriving' : '')); li.setAttribute('data-part', p.id);
      var row = el('div', 'row');
      var img = el('img'); img.alt = ''; img.src = thumb(p.key); row.appendChild(img);
      var meta = el('div', 'meta');
      var nm = el('div', 'name', p.name); nm.title = p.name; meta.appendChild(nm);
      var dims = el('div', 'dims' + (p.slow ? ' slow' : ''));
      if (p.status === 'exporting') {
        dims.textContent = p.slow ? 'Taking longer than usual; still trying…' : (ctx === 'standalone' ? 'Uploading…' : 'Arriving from Onshape…');
        meta.appendChild(dims);
        var bar = el('div', 'arrive-bar'), fill = el('div'); fill.style.width = Math.round(p.progress * 100) + '%'; bar.appendChild(fill); meta.appendChild(bar);
      } else { dims.textContent = sizeText(def.size); dims.title = 'Size as modelled; ' + (def.volume / 1000).toFixed(1) + ' cm³ of plastic'; meta.appendChild(dims); }
      row.appendChild(meta);
      if (ctx !== 'standalone' && p.status === 'ready') {
        var rf = el('button', 'refresh', '↻'); rf.type = 'button';
        rf.title = 'Refresh ' + p.name + ' from Onshape (after you change it there)'; rf.setAttribute('aria-label', rf.title);
        rf.addEventListener('click', function () { p.warn = null; partsNote = null; exportPart(p, { refresh: true }); renderParts(); });
        row.appendChild(rf);
      }
      var qty = el('input', 'part-qty'); qty.type = 'number'; qty.min = '1'; qty.max = String(MAX_INSTANCES); qty.step = '1';
      qty.value = String(p.qty); qty.disabled = p.status !== 'ready'; qty.setAttribute('aria-label', 'Instances of ' + p.name);
      qty.addEventListener('change', function () {
        var n = Math.round(Number(qty.value)); if (!(n >= 1)) n = 1; if (n > MAX_INSTANCES) n = MAX_INSTANCES;
        p.qty = n; qty.value = String(n); renderPartsTotal(); updateNext(); updateSummary();
      });
      row.appendChild(qty);
      var rm = el('button', 'remove', '×'); rm.type = 'button'; rm.setAttribute('aria-label', 'Remove ' + p.name); rm.title = 'Remove ' + p.name;
      rm.addEventListener('click', function () {
        S.parts = S.parts.filter(function (q) { return q !== p; });
        S.instances = S.instances.filter(function (c) { return c.partId !== p.id; });
        partsNote = null; renderParts(); updateNext(); updateSummary();
      });
      row.appendChild(rm);
      li.appendChild(row);
      if (p.status === 'ready' && p.warn) {
        var w = el('div', 'sub'); w.appendChild(msg('warn', p.warn.what, p.warn.todo)); li.appendChild(w);
      }
      list.appendChild(li);
    });
    renderPartsTotal();
    if (S.step === 'parts') updateNext();
  }
  function renderPartsTotal() {
    var box = $('#parts-total'), n = totalInstances(), parts = S.parts.filter(function (p) { return p.status === 'ready'; }).length;
    var coming = S.parts.length - parts;
    box.innerHTML = '';
    if (!S.parts.length) { box.textContent = 'No parts yet.'; return; }
    box.textContent = parts + ' part' + (parts === 1 ? '' : 's') + ', ' + n + ' instance' + (n === 1 ? '' : 's') + ' on one plate (up to ' + MAX_INSTANCES + ')' +
      (coming ? '; ' + coming + ' more arriving. Next does not wait for ' + (coming === 1 ? 'it' : 'them') + '.' : '.');
    if (n > MAX_INSTANCES) box.appendChild(msg('error', 'This plate would hold ' + n + ' instances.', TOO_MANY_INSTANCES_MESSAGE));
  }

  // Onshape selection from the page (Part Studio or Assembly)
  function onOnshapeSelect(key) {
    if (S.step !== 'parts' || S.ctx === 'standalone') return false;
    addPart(key, {});
    return true;
  }

  function importAssembly() {
    var A = P.ASSEMBLY, failAt = Mock.take('export_fail') ? 2 : -1, warnAt = Mock.take('not_watertight') ? 1 : -1;
    var added = 0;
    A.instances.forEach(function (inst, i) {
      var have = S.parts.filter(function (p) { return p.key === inst.key; })[0];
      if (have) { have.qty = inst.count; return; }
      addPart(inst.key, { qty: inst.count, delay: i * 0.35, noArm: true, fail: i === failAt, warn: i === warnAt });
      added++;
    });
    var std = A.standardContent.map(function (s) { return s.count + ' × ' + s.name; }).join('; ');
    setPartsNote(msg('info', 'Added the ' + A.instances.length + ' parts of ' + A.name + ', each with its count in the assembly.',
      'Remove what you do not print (for example the hex shafts). Left out as bought, not printed: ' + std + '.'));
    renderParts();
  }

  function bindParts() {
    $('#btn-import-assembly').addEventListener('click', importAssembly);
    var dz = $('#dropzone'), input = $('#f-upload'), next = 0;
    var keys = P.LIB.map(function (d) { return d.key; }).filter(function (k) { return k !== 'shaft'; });
    function addFiles(files) {
      Array.prototype.slice.call(files).forEach(function (f) {
        var key = keys[next++ % keys.length];
        addPart(key, { fileName: f.name || (P.byKey[key].name.replace(/\s+/g, '_') + '.stl') });
      });
      setPartsNote(msg('info', 'Mockup: each file you choose becomes one of the mock parts; the file itself is not read.', null));
    }
    dz.addEventListener('click', function () { input.click(); });
    dz.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
    input.addEventListener('change', function () { if (input.files.length) addFiles(input.files); input.value = ''; });
    ['dragenter', 'dragover'].forEach(function (n) { dz.addEventListener(n, function (e) { e.preventDefault(); dz.classList.add('drag'); }); });
    ['dragleave', 'drop'].forEach(function (n) { dz.addEventListener(n, function (e) { e.preventDefault(); dz.classList.remove('drag'); }); });
    dz.addEventListener('drop', function (e) { if (e.dataTransfer && e.dataTransfer.files.length) addFiles(e.dataTransfer.files); });
    // for the scenario walk: a fake upload without a file dialog
    window.__mockUpload = function (name) { addFiles([{ name: name }]); };
  }

  /* ================================================================== Layout step */
  var editor = null;
  // A new instance lies the way auto-orient chose for its part (unless the scenario strip says
  // parts arrive as modelled); instance.auto says the choice was automatic, so the panel can say so.
  function newInstance(part) {
    var c = { id: 'c' + (S.nextId++), partId: part.id, partKey: part.key, q: new T.Quaternion(), x: 0, y: 0, auto: false };
    if (Opt.arrival === 'auto') {
      var best = P.resting(part.key).list[0];
      if (best && !best.modelled) { c.q = best.q.clone(); c.auto = true; }
    }
    return c;
  }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function arrangeNote(res, offer) {
    if (!res.parked) return [];
    // Arrange keeps how each instance lies. `offer`, when given, is a plate Arrange also tried
    // with every instance laid its best way, and which left fewer instances over: one button takes it.
    var acts = [['Back to Parts', function () { gotoStep('parts'); }]];
    if (offer) acts.unshift(['Lay them the best way: ' + (offer.parked ? (res.parked - offer.parked) + ' more fit' : 'all fit'), function () {
      // done afresh on the plate as it is now, in case it changed since Arrange was pressed
      pushUndo();
      var n = 0;
      S.instances.forEach(function (c) { var best = P.resting(c.partKey).list[0]; if (best && P.restIndex(c.partKey, c.q) !== 0 && turnToRest(c, best)) { c.auto = true; n++; } });
      var now = PL.bestArrange(S.instances, PLATE);
      S.layoutNotes = arrangeNote(now);
      layHint = msg('ok', 'Laid ' + plural(n, 'instance', 'instances') + ' the best way and arranged again: ' + (now.parked ? plural(now.placed, 'instance fits', 'instances fit') + ' now.' : 'every instance now fits.'), null);
      recheck(); editor.resetHandle(); editor.sync(); editor.resetView(); scheduleLayoutRender();
    }]);
    return [msg('error', 'Arrange placed ' + res.placed + ' of ' + (res.placed + res.parked) + ' instances' + (res.turned ? ', turning ' + res.turned : '') + '; ' + plural(res.parked, 'instance does', 'instances do') + ' not fit and ' + (res.parked === 1 ? 'waits' : 'wait') + ' beside the plate.',
      offer ? 'Arrange keeps how each instance lies. With ' + plural(offer.changed, 'instance', 'instances') + ' laid the best way, ' + (offer.parked ? 'more would fit' : 'everything would fit') + '. Or lower the quantities and print the rest on a second plate.'
            : 'Lower the quantities and print the rest on a second plate, or lay instances another way to make room.', acts)];
  }
  // Arrange keeps how each instance lies. When that leaves instances over and some do not lie
  // their best way, it also tries the plate with every instance laid its best way; only when
  // that leaves fewer over is it offered. Returns { snap, parked, changed } or null, and
  // leaves the plate as Arrange made it.
  function tryBestWay(res) {
    var notBest = S.instances.filter(function (c) { return P.resting(c.partKey).list[0] && P.restIndex(c.partKey, c.q) !== 0; });
    if (!res.parked || !notBest.length) return null;
    var keep = S.instances.map(function (c) { return { c: c, x: c.x, y: c.y, q: c.q.clone(), auto: c.auto }; });
    notBest.forEach(function (c) { if (turnToRest(c, P.resting(c.partKey).list[0])) c.auto = true; });
    var res2 = PL.bestArrange(S.instances, PLATE), offer = res2.parked < res.parked ? { parked: res2.parked, changed: notBest.length } : null;
    keep.forEach(function (k) { k.c.x = k.x; k.c.y = k.y; k.c.q = k.q; k.c.auto = k.auto; k.c.d = null; });
    return offer;
  }
  // Instances follow the Parts step's quantities.
  function enterLayoutData() {
    var fresh = [], before = S.instances.length;
    S.instances = S.instances.filter(function (c) { var p = partById(c.partId); return p && p.status === 'ready'; });
    S.parts.forEach(function (p) {
      if (p.status !== 'ready') return;
      var have = S.instances.filter(function (c) { return c.partId === p.id; });
      while (have.length > p.qty) { var gone = have.pop(); S.instances.splice(S.instances.indexOf(gone), 1); }
      while (have.length < p.qty) { var c = newInstance(p); S.instances.push(c); have.push(c); fresh.push(c); }
    });
    // Undo works within the Layout step; a change made on the Parts step starts afresh.
    if (fresh.length || S.instances.length !== before + fresh.length) { S.undo = []; S.redo = []; }
    // say once per part that it was laid down automatically, and how much lower it now stands
    var told = [];
    fresh.forEach(function (c) {
      var p = partById(c.partId);
      if (!c.auto || p.autoTold) return;
      p.autoTold = true;
      told.push(p.name + ' (' + Math.round(PL.derive(c).height) + ' mm tall instead of ' + Math.round(P.resting(c.partKey).modelled.height) + ' mm)');
    });
    if (told.length) layHint = msg('ok', 'Laid down automatically: ' + told.join(', ') + '.',
      'Chosen by how much touches the plate, how much hangs over air and how tall it stands. Select an instance to see the other ways it can lie, or to put it back as modelled.');
    if (!S.laidOut || fresh.length === S.instances.length) {
      var res = PL.bestArrange(S.instances, PLATE); S.laidOut = true;
      S.layoutNotes = arrangeNote(res);
    } else {
      // instances added to a plate the student already laid out join the group: each takes the
      // free spot nearest the middle of the instances already there, turned if that is what it
      // takes, and nothing else moves
      fresh.forEach(function (c) {
        var others = S.instances.filter(function (o) { return o !== c && fresh.indexOf(o) < 0 || (fresh.indexOf(o) >= 0 && fresh.indexOf(o) < fresh.indexOf(c)); });
        var mid = PL.centre(others, PLATE), q0 = c.q.clone(), turns = [0, 90, 45, 90], ok = false;
        for (var t = 0; t < turns.length && !ok; t++) { if (turns[t]) PL.yaw(c, turns[t]); ok = PL.placeNear(c, others, PLATE, mid[0], mid[1], turns[t] ? 3 : 4); }
        if (!ok) { c.q = q0; c.d = null; PL.place(c, others, PLATE); }
      });
    }
    if (fresh.length) needFit = true;
    S.selected = S.selected.filter(function (id) { return !!instanceById(id); });
    recheck();
  }

  /* ---------------------------------------------------------------- snapshots */
  // Version 4 has no undo on the Layout step (the owner: expensive, and not needed). The
  // snapshots below remain only as plumbing the layout code calls; nothing reads them back.
  var pendingSnap = null;
  function snapshot() {
    return { instances: S.instances.map(function (c) { return { id: c.id, partId: c.partId, partKey: c.partKey, q: c.q.clone(), x: c.x, y: c.y, auto: c.auto }; }),
             parts: S.parts.map(function (p) { return { ref: p, qty: p.qty }; }), selected: S.selected.slice(), notes: S.layoutNotes };
  }
  function restoreSnap(s) {
    S.instances = s.instances.map(function (c) { return { id: c.id, partId: c.partId, partKey: c.partKey, q: c.q.clone(), x: c.x, y: c.y, auto: c.auto }; });
    S.parts = s.parts.map(function (p) { p.ref.qty = p.qty; return p.ref; });
    S.selected = s.selected.slice(); S.layoutNotes = s.notes;
    layHint = null; recheck(); editor.resetHandle(); scheduleLayoutRender(); updateSummary();
  }
  function pushUndo(s) { S.undo.push(s || snapshot()); if (S.undo.length > 60) S.undo.shift(); S.redo = []; }
  function undo() { if (!S.undo.length) return; S.redo.push(snapshot()); restoreSnap(S.undo.pop()); }
  function redo() { if (!S.redo.length) return; S.undo.push(snapshot()); restoreSnap(S.redo.pop()); }

  /* ---------------------------------------------------------------- laying instances down */
  // Turn an instance so that a resting position's face is down, keeping its turn on the plate.
  function turnToRest(c, cand) {
    if (cand.modelled) { if (P.isModelled(c.q)) return false; c.q = new T.Quaternion(); c.d = null; return true; }
    var wn = cand.n.clone().applyQuaternion(c.q);
    if (wn.z < -0.999) return false;
    c.q = new T.Quaternion().setFromUnitVectors(wn.normalize(), P.DOWN).multiply(c.q); c.d = null;
    return true;
  }
  // After instances were laid another way: find each a free spot if it needs one, then one
  // sentence on what happened.
  function afterLay(instances, what) {
    var how = instances.map(function (c) { recheck(); return settle(c); });
    var c0 = instances[0], h = Math.round(PL.derive(c0).height);
    var head = instances.length === 1 ? instanceLabel(c0) + ' now lies ' + what + ': ' + h + ' mm tall.'
                                   : instances.length + ' instances of ' + partById(c0.partId).name + ' now lie ' + what + ': ' + h + ' mm tall.';
    var parked = how.filter(function (h) { return h === 'parked'; }).length, moved = how.filter(Boolean).length - parked;
    layHint = msg(parked ? 'warn' : 'ok', head, parked
      ? (instances.length === 1 ? 'It needs more room lying this way and no spot on the plate is free, so it waits beside the plate. The other instances stay where you put them; press Arrange to make room.'
                                : parked + ' need more room lying this way and wait beside the plate. The other instances stay where you put them; press Arrange to make room.')
      : moved ? (instances.length === 1 ? 'It no longer fitted where it stood, so it was moved' + (how[0] === 'turned' ? ' and turned' : '') + ' to the nearest free spot.' : moved + ' no longer fitted where they stood and moved to the nearest free spots.') : null);
    if (parked) needRefit = true;
    recheck(); scheduleLayoutRender();
  }
  // The resting-position strip, the "As modelled" link and Auto-orient all end here.
  function layInstances(instances, pick, what) {
    var snap = snapshot(), changed = [];
    instances.forEach(function (c) {
      var cand = pick(c);
      if (cand && turnToRest(c, cand)) changed.push(c);
      if (cand) c.auto = what === 'auto';
    });
    if (!changed.length) { layHint = msg('info', (instances.length === 1 ? instanceLabel(instances[0]) + ' already lies' : 'They already lie') + ' that way.', null); scheduleLayoutRender(); return; }
    pushUndo(snap);
    afterLay(changed, what === 'auto' ? 'its best way' : what === 'modelled' ? 'as modelled' : 'that way');
  }
  // Auto-orient: the selection, or every instance when nothing is selected. When every instance
  // changes at once, the plate is arranged again after (as Orca's Q then A).
  function autoOrient(ids) {
    var list = (ids && ids.length ? ids : S.instances.map(function (c) { return c.id; })).map(instanceById).filter(Boolean);
    var whole = !(ids && ids.length);
    if (!whole) return layInstances(list, function (c) { return P.resting(c.partKey).list[0]; }, 'auto');
    var snap = snapshot(), changed = 0;
    list.forEach(function (c) { var best = P.resting(c.partKey).list[0]; if (best && turnToRest(c, best)) changed++; if (best) c.auto = true; });
    if (!changed) { layHint = msg('info', 'Every instance already lies its best way.', null); scheduleLayoutRender(); return; }
    pushUndo(snap); recheck();
    var res = null;
    if (S.problems.some(function (p) { return p.rule !== 'too_tall'; })) { res = PL.bestArrange(S.instances, PLATE); S.layoutNotes = arrangeNote(res); needRefit = true; }
    layHint = msg('ok', 'Auto-orient laid ' + plural(changed, 'instance', 'instances') + (changed === 1 ? ' its' : ' their') + ' best way' + (res ? ', then arranged the plate to make room.' : '.'), null);
    recheck(); scheduleLayoutRender();
  }
  // The tip handle: each selected instance steps to its next resting position (Shift: the one before).
  function tipSelected(back) {
    var list = S.selected.map(instanceById).filter(Boolean);
    if (!list.length) return;
    var snap = snapshot(), changed = [];
    list.forEach(function (c) {
      var R = P.resting(c.partKey).list, n = R.length; if (!n) return;
      var i = P.restIndex(c.partKey, c.q);
      var next = i < 0 ? (back ? n - 1 : 0) : (i + (back ? n - 1 : 1)) % n;
      if (next !== i && turnToRest(c, R[next])) { c.auto = false; changed.push(c); }
    });
    if (!changed.length) { layHint = msg('info', instanceLabel(list[0]) + ' has only one way to lie flat.', null); scheduleLayoutRender(); return; }
    pushUndo(snap);
    var c0 = changed[0], k = P.restIndex(c0.partKey, c0.q), n0 = P.resting(c0.partKey).list.length;
    afterLay(changed, 'on its ' + ordinal(k + 1) + ' of ' + n0 + ' sides' + (k === 0 ? ' (the best)' : ''));
  }
  function ordinal(n) { return ['first', 'second', 'third', 'fourth', 'fifth', 'sixth'][n - 1] || n + 'th'; }
  // One sentence per instance that is too close to two or more others.
  function recheck() {
    var raw = PL.check(S.instances, PLATE, instanceLabel), close = raw.filter(function (p) { return p.rule === 'too_close'; });
    var count = {};
    close.forEach(function (p) { p.instances.forEach(function (id) { count[id] = (count[id] || 0) + 1; }); });
    var hubs = Object.keys(count).filter(function (id) { return count[id] >= 2; }).sort(function (a, b) { return count[b] - count[a]; });
    var used = {}, merged = [];
    hubs.forEach(function (id) {
      var mine = close.filter(function (p) { return !used[p.instances.join()] && p.instances.indexOf(id) >= 0; });
      if (mine.length < 2) return;
      mine.forEach(function (p) { used[p.instances.join()] = 1; });
      var others = mine.map(function (p) { return instanceLabel(instanceById(p.instances[0] === id ? p.instances[1] : p.instances[0])); });
      var list = others.length > 1 ? others.slice(0, -1).join(', ') + ' and ' + others[others.length - 1] : others[0];
      merged.push({ rule: 'too_close', instances: [id].concat(mine.map(function (p) { return p.instances[0] === id ? p.instances[1] : p.instances[0]; })),
                    message: instanceLabel(instanceById(id)) + ' overlaps or is closer than ' + PLATE.spacing + ' mm to ' + list + '. Drag it to a clear spot, or press Arrange.' });
    });
    S.problems = raw.filter(function (p) { return p.rule !== 'too_close' || !used[p.instances.join()]; }).concat(merged);
  }
  function isBad(id) { return S.problems.some(function (p) { return p.instances.indexOf(id) >= 0; }); }
  // An instance that was just laid down has a new footprint. If it now overlaps a neighbour or
  // crosses the plate edge, find it a free spot, turning it if that is what it takes.
  // It takes the free spot nearest to where it stood, so it stays beside its neighbours.
  // When no spot is free with the others where they are (a long part laid flat among small
  // ones), the whole plate is arranged again, which is what the student would press next.
  // Returns 'moved', 'turned', 'arranged', or null when it was fine or nothing fits at all.
  function settle(instance) {
    function placeProblem() { return S.problems.some(function (p) { return p.rule !== 'too_tall' && p.instances.indexOf(instance.id) >= 0; }); }
    if (!placeProblem()) return null;
    var keep = { x: instance.x, y: instance.y, q: instance.q.clone() }, others = S.instances.filter(function (o) { return o !== instance; });
    var turns = [0, 90, 45, 90], how = 'moved';
    for (var t = 0; t < turns.length; t++) {
      if (turns[t]) { PL.yaw(instance, turns[t]); how = 'turned'; }
      if (PL.placeNear(instance, others, PLATE, keep.x, keep.y, turns[t] ? 3 : 4)) { recheck(); return how; }
    }
    // No free spot with the others where they are. The owner (M9): never move other instances.
    // This one waits beside the plate, marked off the plate, until the student presses Arrange.
    instance.q = keep.q; instance.d = null;
    var d = PL.derive(instance), sideY = 0;
    S.instances.forEach(function (o) { if (o === instance) return; var h = PL.bbox(PL.worldHull(o)); if (h.minX > PLATE.x) sideY = Math.max(sideY, h.maxY + PLATE.spacing); });
    instance.x = PLATE.x + PLATE.spacing * 4 + d.w / 2; instance.y = sideY + d.l / 2;
    recheck();
    return 'parked';
  }

  function enterLayout() {
    enterLayoutData();
    $('#layout-info').textContent = (PRN.paired ? ST.PRINTER.name : 'The ' + ST.PRINTER.model) + ': plate ' + PLATE.x + ' × ' + PLATE.y + ' mm, instances up to ' + PLATE.height + ' mm tall and ' + PLATE.spacing + ' mm apart.';
    if (!editor) {
      editor = Layout3D.create($('#layout-view'), {
        plate: PLATE,
        getInstances: function () { return S.instances; },
        isSelected: function (id) { return S.selected.indexOf(id) >= 0; },
        isBad: isBad,
        labelFor: function (id) { var c = instanceById(id); return c ? instanceLabel(c) : ''; },
        select: function (id, how) {
          if (how === 'none') S.selected = [];
          else if (how === 'only') S.selected = [id];
          else if (how === 'toggle') { var i = S.selected.indexOf(id); if (i >= 0) S.selected.splice(i, 1); else S.selected.push(id); }
          if (how !== 'toggle' || S.selected.length <= 1) editor.resetHandle();
          renderLayoutSide(); editor.sync();
        },
        // a drag or a lay-down is about to change the plate: keep what it was, for undo
        begin: function () { pendingSnap = snapshot(); },
        changed: function (why, instance) {
          if (pendingSnap && (why === 'move' || why === 'rotate' || why === 'lay')) { pushUndo(pendingSnap); pendingSnap = null; }
          recheck();
          if (why === 'lay' && instance) { afterLay([instance], 'on that ' + (Opt.lay === 'box' ? 'side' : 'face')); return; }
          scheduleLayoutRender();
          // a click (not a drag) just selected an instance: bring what can be done with it into
          // sight under the picture. Done on release, so the picture never moves under a press.
          if (why === 'select' && S.selected.length) requestAnimationFrame(function () { requestAnimationFrame(revealSelectionTools); });
        },
        tip: tipSelected,
        hint: function (text) { layHint = msg('warn', text, null); renderLayoutSide(); },
        onKey: function (k) {
          if (k === 'escape') { S.selected = []; renderLayoutSide(); editor.sync(); }
          if (k === 'all') { S.selected = S.instances.map(function (c) { return c.id; }); renderLayoutSide(); editor.sync(); }
          if (k === 'fit') editor.resetView();
          if (k === 'top') editor.topView();
        }
      });
      editor.setScheme(Opt.scheme); editor.setLayOption(Opt.lay);
    }
    applyLayoutArms();
    var fit = needFit; needFit = false;
    setTimeout(function () { editor.resize(); editor.sync(); if (fit) editor.resetView(); }, 0);
    renderLayoutSide();
  }
  // Scroll the panel just far enough that the selection's row, and the resting-position
  // strip when it is the chosen way, are in sight; never so far that the picture's top goes.
  function revealSelectionTools() {
    var body = $('#wiz-body'), last = Opt.lay === 'strip' && !$('#rest-strip').hidden ? $('#rest-strip') : $('#layout-selrow');
    var b = body.getBoundingClientRect(), r = last.getBoundingClientRect(), top = $('#layout-alert').getBoundingClientRect().top;
    var over = r.bottom + 6 - b.bottom;
    if (over > 0) body.scrollTop += Math.min(over, Math.max(0, top - b.top));
  }
  var needFit = false;      // the instances were just arranged or added to: zoom to them on entry
  var needRefit = false;    // the plate was arranged again behind a lay-down: show all of it
  var layHint = null, rafPending = false;
  function scheduleLayoutRender() {
    if (rafPending) return; rafPending = true;
    requestAnimationFrame(function () {
      rafPending = false; editor.sync(); renderLayoutSide(); updateNext();
      if (needRefit) { needRefit = false; editor.resetHandle(); editor.resetView(); }
    });
  }
  function renderLayoutSide() {
    var sel = S.selected.map(instanceById).filter(Boolean);
    var s = $('#layout-selection');
    $('#layout-selrow').classList.toggle('has-sel', sel.length > 0);
    if (!sel.length) s.textContent = S.instances.length + ' instance' + (S.instances.length === 1 ? '' : 's') + ' on the plate. Click one to select it.';
    else if (sel.length === 1) { var d = PL.derive(sel[0]); s.innerHTML = ''; s.appendChild(el('strong', null, instanceLabel(sel[0]))); s.appendChild(document.createTextNode(' ' + Math.round(d.w) + ' × ' + Math.round(d.l) + ' mm, ' + Math.round(d.height) + ' mm tall')); }
    else { s.innerHTML = ''; s.appendChild(el('strong', null, sel.length + ' instances')); s.appendChild(document.createTextNode(' move and turn together')); }
    renderOrientLine(sel); renderStrip(sel); renderGestures();
    $('#btn-tilt').hidden = Opt.scheme !== 'T'; $('#btn-top').hidden = Opt.scheme === 'T';
    // The first problem is also said inside the picture, where the student is looking; the
    // full sentences and their remedy buttons are below it.
    var alertBox = $('#layout-alert');
    alertBox.innerHTML = ''; alertBox.classList.toggle('ok', !S.problems.length); alertBox.disabled = !S.problems.length;
    if (S.problems.length) {
      var first = S.problems[0].message.split('. ')[0] + '.';
      alertBox.appendChild(el('span', 'first', first)); alertBox.title = first;
      alertBox.appendChild(el('span', 'more', S.problems.length > 1 ? '+' + (S.problems.length - 1) + ' more ↓' : 'Fix ↓'));
    } else {
      alertBox.title = '';
      alertBox.appendChild(el('span', 'first', S.instances.length ? '✓ ' + (S.instances.length === 1 ? instanceLabel(S.instances[0]) + ' fits' :'All ' + S.instances.length + ' instances fit') + ' the plate.' : 'No instances yet: add parts on the Parts step.'));
    }
    var box = $('#layout-errors'); box.innerHTML = '';
    if (layHint) box.appendChild(layHint);
    S.layoutNotes.forEach(function (n) { box.appendChild(n); });
    if (S.problems.length) {
      box.appendChild(el('div', 'hint fix-first', S.problems.length === 1 ? 'Fix this before Next:' : 'Fix these ' + S.problems.length + ' before Next (click one to select its instances):'));
      S.problems.forEach(function (p) {
        // an instance Arrange left beside the plate: pressing Arrange again cannot help
        var parkedInstance = p.rule === 'off_plate' && S.layoutNotes.length && PL.bbox(PL.worldHull(instanceById(p.instances[0]))).minX > PLATE.x;
        var acts = p.rule === 'too_tall' ? [['Auto-orient', function (e) { e.stopPropagation(); S.selected = p.instances.slice(); autoOrient(p.instances); }]]
                 : parkedInstance ? [['Back to Parts', function (e) { e.stopPropagation(); gotoStep('parts'); }]]
                 : [['Arrange', function (e) { e.stopPropagation(); doArrange(); }]];
        var m = msg('error', p.message.split('. ')[0] + '.', parkedInstance ? 'It did not fit: lower its quantity, or lay instances another way to make room.' : p.message.split('. ').slice(1).join('. '), acts);
        m.classList.add('clickable');
        m.addEventListener('click', function () { S.selected = p.instances.slice(); editor.resetHandle(); editor.sync(); renderLayoutSide(); });
        box.appendChild(m);
      });
    }
  }
  // Under the selection: whether it lies as chosen automatically, and the one way back to
  // how it was modelled.
  function renderOrientLine(sel) {
    var box = $('#layout-orient'); box.innerHTML = '';
    var same = sel.length && sel.every(function (c) { return c.partKey === sel[0].partKey; });
    box.hidden = !same;
    if (!same) return;
    var modelled = sel.every(function (c) { return P.isModelled(c.q); }), auto = sel.every(function (c) { return c.auto; });
    var best = P.resting(sel[0].partKey).list[0];
    function link(t, fn) { var b = el('button', 'linkish', t); b.type = 'button'; b.addEventListener('click', fn); box.appendChild(b); }
    if (auto && !modelled) {
      box.appendChild(el('span', 'auto-chip', 'Laid down automatically'));
      link('Put back as modelled', function () { layInstances(sel, function () { return P.resting(sel[0].partKey).modelled; }, 'modelled'); });
    } else if (!modelled) {
      box.appendChild(document.createTextNode('Laid down by you. '));
      link('Put back as modelled', function () { layInstances(sel, function () { return P.resting(sel[0].partKey).modelled; }, 'modelled'); });
    } else if (best && !best.modelled) {
      box.appendChild(document.createTextNode('As modelled. '));
      link('Lay it the best way', function () { autoOrient(sel.map(function (c) { return c.id; })); });
    } else box.appendChild(document.createTextNode('As modelled, which is already its best way.'));
  }
  // The resting-position strip: under the view, while the selection is instances of one part,
  // a picture of each way that part can lie, the auto-orient choice first and marked Best,
  // the way it lies now outlined. A click lays every selected instance that way.
  function renderStrip(sel) {
    var box = $('#rest-strip'); box.innerHTML = '';
    box.hidden = Opt.lay !== 'strip' || !sel.length;
    if (box.hidden) return;
    var key = sel[0].partKey;
    if (sel.some(function (c) { return c.partKey !== key; })) { box.appendChild(el('div', 'hint', 'Select instances of one part to choose how they lie.')); return; }
    var R = P.resting(key), cur = P.restIndex(key, sel[0].q);
    if (sel.some(function (c) { return P.restIndex(key, c.q) !== cur; })) cur = -2;
    var nWays = R.list.length + (R.modelledListed ? 0 : 1);
    box.appendChild(el('div', 'rs-head', nWays === 1 ? 'It can lie flat only this way.' : 'The ' + nWays + ' ways ' + (sel.length > 1 ? 'they' : 'it') + ' can lie. Click one to lay ' + (sel.length > 1 ? 'them' : 'it') + ' that way:'));
    var row = el('div', 'rs-row');
    var items = R.list.map(function (c, i) { return { cand: c, i: i }; });
    if (!R.modelledListed) items.push({ cand: R.modelled, i: 'm' });
    items.forEach(function (it) {
      var c = it.cand, on = it.i === 'm' ? cur === -1 && P.isModelled(sel[0].q) : it.i === cur;
      var b = el('button', 'rs-item' + (on ? ' on' : '')); b.type = 'button';
      var img = el('img'); img.alt = ''; img.src = restThumb(key, it.i, c.q); b.appendChild(img);
      if (it.i === 0) b.appendChild(el('span', 'rs-best', 'Best'));
      var tall = c.height > PLATE.height;
      b.appendChild(el('span', 'rs-line', Math.round(c.height) + ' mm tall'));
      if (it.i === 'm') b.appendChild(el('span', 'rs-line', 'as modelled'));
      if (tall) b.appendChild(el('span', 'rs-line bad', 'too tall'));
      else if (c.supports) b.appendChild(el('span', 'rs-line warn', 'overhangs'));
      b.title = (it.i === 0 ? 'The best way, chosen automatically: ' : it.i === 'm' ? 'As modelled: ' : '') + Math.round(c.height) + ' mm tall, ' + Math.round(c.contact) + ' mm² on the plate' + (c.overhang > 1 ? ', ' + Math.round(c.overhang) + ' mm² over air' : '') + (c.supports ? '. Much of it hangs over air, so it will probably need Supports.' : '');
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.addEventListener('click', function () { layInstances(sel, function () { return c; }, it.i === 0 ? 'auto' : it.i === 'm' ? 'modelled' : 'pick'); });
      row.appendChild(b);
    });
    box.appendChild(row);
  }
  // One line under the view: the gestures of the mouse scheme and of the way to lay an instance
  // down, chosen in the scenario strip, so a student need not be told.
  var GESTURES = {
    O: 'Drag an instance to move it, its round handle to turn it. Right-drag to look around, Shift-drag to slide, scroll to zoom.',
    S: 'Drag an instance to move it, its round handle to turn it. Drag empty space to look around, right-drag to slide, scroll to zoom.',
    T: 'Seen from above. Drag an instance to move it, its round handle to turn it. Drag empty space to slide, scroll to zoom, right-drag or 3D to tilt.'
  };
  var LAY_GESTURE = {
    strip: 'Select an instance to see pictures of the ways it can lie; click one to lay it that way.',
    markers: 'Select an instance, then click an arrow (↓) on one of its faces to lay it on that face.',
    box: 'Select an instance, then click a side of the box around it to put that side down, or drag the box to roll it.',
    tip: 'Select an instance, then click ⤵ beside its round handle to tip it onto its next side.'
  };
  var MORE = {
    O: ['Left-drag on empty plate also looks around; middle-drag, Ctrl + right-drag or Shift-drag slides the view.'],
    S: ['Shift-drag also slides the view.'],
    T: ['Middle-drag also slides; Top puts the view back above the plate.']
  };
  function renderGestures() {
    $('#layout-gestures').textContent = GESTURES[Opt.scheme] + ' ' + LAY_GESTURE[Opt.lay];
    var ul = $('#layout-more'); ul.innerHTML = '';
    MORE[Opt.scheme].concat([
      'Shift- or Ctrl-click adds an instance to the selection; drag one to move them all.',
      'The handle snaps every 45 degrees.',
      'Double-click a flat face to lay the instance down on it.',
      'F zooms to the instances; Ctrl+1 looks from above; Ctrl+A selects every instance; Escape clears the selection.',
      'To print more or fewer of a part, go Back to the Parts step and change its quantity.'
    ]).forEach(function (t) { ul.appendChild(el('li', null, t)); });
  }
  function doArrange() {
    pushUndo();
    var res = PL.bestArrange(S.instances, PLATE);
    S.layoutNotes = arrangeNote(res, tryBestWay(res));
    layHint = res.parked ? null : msg('ok', 'Arranged ' + plural(res.placed, 'instance', 'instances') + (res.turned ? ', turning ' + res.turned : '') + '.', null);
    recheck(); editor.resetHandle(); editor.sync(); editor.resetView(); scheduleLayoutRender();
  }
  function bindLayout() {
    $('#btn-arrange').addEventListener('click', doArrange);
    $('#btn-orient').addEventListener('click', function () { autoOrient(S.selected.slice()); });
    $('#btn-view').addEventListener('click', function () { editor && editor.resetView(); });
    $('#btn-view-plate').addEventListener('click', function () { editor && editor.viewPlate(); });
    $('#btn-top').addEventListener('click', function () { editor && editor.topView(); });
    $('#btn-tilt').addEventListener('click', function () { if (editor) $('#btn-tilt').textContent = editor.toggleTilt() ? 'Above' : '3D'; });
    $('#layout-alert').addEventListener('click', function () { $('#layout-errors').scrollIntoView({ block: 'start', behavior: 'smooth' }); });
  }
  function setOption(name, value) {
    Opt[name] = value;
    if (name === 'scheme') $('#btn-tilt').textContent = '3D';
    if (editor) { if (name === 'scheme') editor.setScheme(value); if (name === 'lay') editor.setLayOption(value); }
    if (S.step === 'layout') renderLayoutSide();
  }

  // put an instance at the candidate spot that causes the fewest problems besides the wanted one
  function bestSpot(c, spots, rule) {
    var best = null;
    spots.forEach(function (s) {
      c.x = s[0]; c.y = s[1];
      var ps = PL.check(S.instances, PLATE, instanceLabel), wanted = ps.filter(function (p) { return p.rule === rule; }).length;
      var score = wanted ? ps.length - wanted : 99;
      if (!best || score < best.score) best = { score: score, s: s };
    });
    c.x = best.s[0]; c.y = best.s[1];
  }

  // armed layout errors: applied now if on the Layout step, else when it is next entered
  function applyLayoutArms() {
    if (S.step !== 'layout' || !S.instances.length) return;
    var c0 = S.instances[0], d0, note = null;
    if (Mock.take('too_close')) {
      if (S.instances.length < 2) { var p = partById(c0.partId), n = newInstance(p); n.q = c0.q.clone(); S.instances.push(n); p.qty++; }
      // put one instance 2 mm from another: the pair and the side that break no other rule.
      // When the pair would cross the plate's edge there, both slide inward together, so the
      // armed error shows as "too close" and never as "not fully on the plate".
      var pick = null;
      function intoPlate(a, b) {
        var ha = PL.bbox(PL.worldHull(a)), hb = PL.bbox(PL.worldHull(b)), m = PLATE.margin + 0.5;
        var minX = Math.min(ha.minX, hb.minX), maxX = Math.max(ha.maxX, hb.maxX), minY = Math.min(ha.minY, hb.minY), maxY = Math.max(ha.maxY, hb.maxY);
        var dx = minX < m ? m - minX : maxX > PLATE.x - m ? PLATE.x - m - maxX : 0;
        var dy = minY < m ? m - minY : maxY > PLATE.y - m ? PLATE.y - m - maxY : 0;
        return [dx, dy];
      }
      S.instances.forEach(function (a) {
        S.instances.forEach(function (b) {
          if (a === b) return;
          var da = PL.derive(a), db = PL.derive(b), keepA = [a.x, a.y], keepB = [b.x, b.y];
          var hx = da.w / 2 + db.w / 2, hy = da.l / 2 + db.l / 2;
          // Boxes 2 mm apart can leave outlines farther apart than 5 mm (a slanted or notched
          // part), so the gap closes a millimetre at a time until the pair is too close.
          [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(function (dir) {
            for (var g = 2; g >= -40; g -= 1) {
              a.x = keepA[0]; a.y = keepA[1]; b.x = a.x + dir[0] * (hx + g); b.y = a.y + dir[1] * (hy + g);
              var sh = intoPlate(a, b); a.x += sh[0]; a.y += sh[1]; b.x += sh[0]; b.y += sh[1];
              var ps = PL.check(S.instances, PLATE, instanceLabel), wanted = ps.filter(function (p) { return p.rule === 'too_close'; }).length;
              if (!wanted) continue;
              var score = ps.length - wanted;
              if (!pick || score < pick.score) pick = { score: score, a: a, b: b, sa: [a.x, a.y], sb: [b.x, b.y] };
              break;
            }
          });
          a.x = keepA[0]; a.y = keepA[1]; b.x = keepB[0]; b.y = keepB[1];
        });
      });
      if (pick) { pick.a.x = pick.sa[0]; pick.a.y = pick.sa[1]; pick.b.x = pick.sb[0]; pick.b.y = pick.sb[1]; }
    }
    if (Mock.take('off_plate')) {
      var c = S.instances[S.instances.length - 1], d = PL.derive(c);
      var yy = Math.min(Math.max(c.y, d.l / 2 + 10), PLATE.y - d.l / 2 - 10), xx = Math.min(Math.max(c.x, d.w / 2 + 10), PLATE.x - d.w / 2 - 10);
      bestSpot(c, [[PLATE.x - d.w * 0.25, yy], [d.w * 0.25, yy], [xx, PLATE.y - d.l * 0.25], [xx, d.l * 0.25]], 'off_plate');
    }
    if (Mock.take('too_tall')) {
      var rib = S.instances.filter(function (x) { return x.partKey === 'rib'; })[0];
      if (!rib) {
        var part = { id: 'p' + (S.nextId++), key: 'rib', name: P.byKey.rib.name, qty: 1, status: 'ready', warn: null, error: null };
        S.parts.push(part); rib = newInstance(part); rib.q = new T.Quaternion(); rib.auto = false; S.instances.push(rib);
        var ribOthers = S.instances.filter(function (x) { return x !== rib; }), ribMid = PL.centre(ribOthers, PLATE);
        if (!PL.placeNear(rib, ribOthers, PLATE, ribMid[0], ribMid[1])) PL.place(rib, ribOthers, PLATE);
        note = msg('info', 'Mockup: added a ' + part.name + ' standing up, to show the height rule.', null);
      } else { rib.q = new T.Quaternion(); rib.d = null; rib.auto = false; note = msg('info', 'Mockup: stood ' + instanceLabel(rib) + ' up as modelled, to show the height rule.', null); }
    }
    if (note) layHint = note;
    recheck();
    if (editor) { editor.sync(); renderLayoutSide(); updateNext(); updateSummary(); }
  }

  /* ================================================================== Preview step */
  var viewer = null, gen = null;
  var STAGES = [
    { name: 'Sending the plate to the slicer', w: 0.06 },
    { name: 'Slicing mesh', w: 0.12 },
    { name: 'Generating perimeters', w: 0.18 },
    { name: 'Preparing infill', w: 0.1 },
    { name: 'Generating infill toolpath', w: 0.22 },
    { name: 'Generating support', w: 0.12, support: true },
    { name: 'Generating skirt & brim', w: 0.04 },
    { name: 'Generating G-code', w: 0.16 }
  ];
  function signature() {
    return JSON.stringify({ c: S.instances.map(function (c) { return [c.partKey, c.q.toArray().map(function (x) { return +x.toFixed(4); }), +c.x.toFixed(1), +c.y.toFixed(1)]; }), s: eff(), f: S.filament });
  }
  function plateVolume() { return S.instances.reduce(function (a, c) { return a + P.byKey[c.partKey].volume; }, 0) / 1000; }

  // The Preview step's lead always says where the slice stands: running, sliced, failed,
  // stopped at the time limit, cancelled, or never started.
  var SLICING_LEAD = 'Slicing the plate on the server. You can step back meanwhile; it goes on.';
  function previewLead(t) { $('#preview-lead').textContent = t; }
  function enterPreview() {
    if (S.result && S.resultSig === signature()) { showResult(); return; }
    if (S.job && S.job.state === 'running') {
      if (S.job.sig === signature()) { $('#slice-card').hidden = false; previewLead(SLICING_LEAD); return; }   // still slicing this plate
      cancelSlice('changed');                                                          // the plate changed: slice it afresh
    }
    startSlice();
  }
  function clearPreview() {
    $('#preview-errors').innerHTML = ''; $('#preview-result').hidden = true; $('#slice-card').hidden = true; $('#preview-toast').hidden = true;
  }
  function startSlice() {
    clearPreview(); S.result = null; S.resultSig = null; updateNext();
    previewLead(SLICING_LEAD);
    var v = eff(), vol = plateVolume(), instances = S.instances.slice();
    var forced = Mock.take('too_large');
    if (forced || vol > PLATE_VOLUME_CAP_CM3) {
      previewLead('This plate was not sliced: it is too large for the server. Nothing to preview yet.');
      var cap = forced ? Math.max(10, Math.floor(vol * 0.75 / 10) * 10) : PLATE_VOLUME_CAP_CM3;
      $('#preview-errors').appendChild(msg('error',
        'This plate is too large for the server to slice: its ' + instances.length + ' instances hold about ' + Math.round(vol) + ' cm³ of plastic, and the server slices up to ' + cap + ' cm³ at once.',
        instances.length > 1 ? 'Lower the quantities and print the rest on a second plate.'
                          : 'This part alone is more than the server can slice, so it cannot be printed from here. Slice it in Orca Slicer on a shop computer.',
        instances.length > 1 ? [['Back to Parts', function () { gotoStep('parts'); }, 'primary'], ['Back to Layout', function () { gotoStep('layout'); }]]
                          : [['Back to Parts', function () { gotoStep('parts'); }]]));
      if (forced) $('#preview-errors').appendChild(msg('info', 'Mockup: the cap was lowered for this plate to show the message. The mockup’s real cap is ' + PLATE_VOLUME_CAP_CM3 + ' cm³.', null));
      return;
    }
    // which failure, if any, this slice will meet
    var fail = null, suspect = pickSuspect();
    var armedEmpty = Mock.has('empty_layers'), armedFaulty = Mock.has('faulty_mesh');
    if (!v.enable_support && (armedEmpty || armedFaulty)) { if (armedEmpty) Mock.take('empty_layers'); fail = { type: 'empty', at: 0.18 }; }
    else if (v.enable_support && armedFaulty) { Mock.take('faulty_mesh'); fail = { type: 'faulty', at: 0.18 }; }
    else if (v.enable_support && armedEmpty) Mock.take('empty_layers');        // Supports on is the fix: it slices
    var timeout = Mock.take('timeout'), conn = Mock.take('conn_lost'), autoCancel = Mock.take('cancel');
    var layers = Math.max.apply(null, instances.map(function (c) { return Math.ceil(PL.derive(c).height / v.layer_height); }));
    var expected = Math.round(8 + 1.6 * instances.length + vol * 0.12 + layers * 0.04 + (v.enable_support ? 6 : 0));
    var job = S.job = { state: 'running', t: 0, shown: 0, expected: expected, actual: expected * (0.88 + Math.random() * 0.24),
                        fail: fail, suspect: suspect, timeout: timeout, conn: conn ? { at: 0.35 + Math.random() * 0.1 } : null,
                        autoCancel: autoCancel, tp: null, support: v.enable_support, settings: v, sig: signature(), instances: instances };
    gen = Preview3D.generate(instances, v, function (res) { job.tp = res; });
    renderStages(job, 0);
    $('#slice-card').hidden = false; $('#slice-card').classList.remove('stalled');
    $('#slice-expected').textContent = 'about ' + clock(expected) + ' left';
    $('#slice-conn').hidden = true;
    job.ticker = addJob({ tick: function (dt) { tickSlice(job, dt); } });
    job.ticker.server = true;              // the slice runs on the server: a refresh does not stop it
    tickSlice(job, 0);
  }
  function pickSuspect() {
    var warned = S.instances.filter(function (c) { var p = partById(c.partId); return p && p.warn; })[0];
    if (warned) return warned;
    return S.instances.slice().sort(function (a, b) { return PL.derive(b).height - PL.derive(a).height; })[0];
  }
  function activeStages(job) { return STAGES.filter(function (s) { return !s.support || job.support; }); }
  function stageAt(job, p) {
    var st = activeStages(job), tot = st.reduce(function (a, s) { return a + s.w; }, 0), acc = 0;
    for (var i = 0; i < st.length; i++) { acc += st[i].w / tot; if (p < acc - 1e-9) return { i: i, name: st[i].name }; }
    return { i: st.length - 1, name: st[st.length - 1].name };
  }
  function renderStages(job, p) {
    var ol = $('#slice-stages'); ol.innerHTML = '';
    var cur = stageAt(job, p).i, n = 0;
    STAGES.forEach(function (s) {
      var li = el('li', null, s.name);
      if (s.support && !job.support) { li.className = 'skip'; li.title = 'Supports is off'; ol.appendChild(li); return; }
      li.className = n < cur || p >= 1 ? 'done' : (n === cur ? 'now' : '');
      n++; ol.appendChild(li);
    });
  }
  function tickSlice(job, dt) {
    if (job.state !== 'running') return;
    job.t += dt * Mock.factor('slice');
    var p = Math.min(1, job.t / job.actual);
    if (job.timeout) p = Math.min(0.93, 0.62 * (1 - Math.exp(-job.t / 25)) + 0.3 * Math.min(1, job.t / SLICE_TIMEOUT_S));
    // connection lost: the page stops hearing for a while; the clock keeps going
    var lost = false;
    if (job.conn && p >= job.conn.at && !job.conn.done) {
      if (job.conn.start == null) { job.conn.start = job.t; job.conn.real = performance.now(); }
      var gone = (performance.now() - job.conn.real) / 1000;          // a network outage runs on the real clock
      if (gone < 8) {
        lost = true;
        var c = $('#slice-conn'); c.hidden = false; c.className = 'conn lost';
        c.innerHTML = ''; c.appendChild(el('span', 'spin'));
        c.appendChild(document.createTextNode(' Lost the connection to the server at ' + clock(job.conn.start) + '. Reconnecting (try ' + (1 + Math.floor(gone / 2.5)) + ')…'));
        // the owner (M15): Cancel cannot reach the server now, so it is disabled and says why
        c.appendChild(el('div', null, 'Cancel slice is off until the server can be reached again; the slice may still be running.'));
      } else {
        job.conn.done = true;
        var cc = $('#slice-conn'); cc.className = 'conn back';
        cc.textContent = 'Reconnected at ' + clock(job.t) + '. The slice kept running; the progress below is up to date.';
        after(5, 'slice', function () { if (job.conn.done) $('#slice-conn').hidden = true; });
      }
    }
    $('#btn-cancel').disabled = lost;
    $('#btn-cancel').title = lost ? 'The server cannot be reached; the slice may still be running' : '';
    if (lost) {                         // the page hears nothing: only its own clock moves
      $('#slice-elapsed').textContent = clock(job.t);
      $('#slice-stage').textContent = stageAt(job, job.shown).name + ' (last heard)';
      var exl = $('#slice-expected'); exl.className = 'late'; exl.textContent = 'no news since ' + clock(job.conn.start);
      $('#slice-card').classList.add('stalled');
      $all('#g-layers rect').forEach(function (r) { r.classList.remove('on'); });
      return;
    }
    job.shown = p;
    if (job.conn && job.conn.done && p >= 1 && !job.conn.told) {
      job.conn.told = true;
      $('#slice-conn').textContent = 'Reconnected at ' + clock(job.t) + '. The slice finished on the server while the connection was down.';
    }
    if (job.timeout && job.t >= SLICE_TIMEOUT_S) return failSlice(job, 'timeout');
    if (job.fail && p >= job.fail.at) return failSlice(job, job.fail.type);
    if (job.autoCancel && p >= 0.5) return cancelSlice('auto');
    var shown = job.shown;
    if (p >= 1 && !job.tp) shown = 0.99;
    $('#slice-pct').textContent = Math.floor(shown * 100) + '%';
    $('#slice-stage').textContent = stageAt(job, shown).name;
    $('#slice-elapsed').textContent = clock(job.t);
    var late = job.t > job.expected * 1.3;
    var ex = $('#slice-expected'); ex.className = late ? 'late' : '';
    var left = job.expected - job.t;
    ex.textContent = late ? 'taking longer than the expected ' + clock(job.expected)
      : left > 1 ? 'about ' + clock(left) + ' left' : 'finishing';
    $('#slice-card').classList.toggle('stalled', lost || late);
    $('#g-fill').style.strokeDasharray = String(2 * Math.PI * 27);
    $('#g-fill').style.strokeDashoffset = String(2 * Math.PI * 27 * (1 - shown));
    $('#slice-bar-fill').style.width = (shown * 100).toFixed(1) + '%';
    var lit = lost ? -1 : Math.floor(job.t * 2 / Math.max(1, Mock.factor('slice') / 2)) % 5;
    $all('#g-layers rect').forEach(function (r, i) { r.classList.toggle('on', 3 - i < lit); });
    renderStages(job, shown);
    if (p >= 1 && job.tp) finishSlice(job);
  }
  function stopJob(job) { job.state = job.state === 'running' ? 'stopped' : job.state; dropJob(job.ticker); if (gen) gen.cancel(); }
  function failSlice(job, type) {
    stopJob(job); job.state = 'failed';
    $('#slice-card').hidden = true;
    previewLead(type === 'timeout' ? 'The slice was stopped at the server’s time limit. Nothing to preview yet.'
                                   : 'The slice failed, so there is nothing to preview yet. What to change is below.');
    var box = $('#preview-errors'); box.innerHTML = '';
    var sus = job.suspect, label = sus ? instanceLabel(sus) : 'An instance', h = sus ? PL.derive(sus).height : 40;
    var z1 = +(h * 0.62).toFixed(2), z2 = +(z1 + 0.72).toFixed(2), zr = Math.round(z1 * 10) / 10;
    var name = sus && partById(sus.partId) ? partById(sus.partId).name : 'the part';
    // For a mentor: Orca Slicer's own sentence, which names the heights; nothing of PenguinSlicer's.
    var orca = 'Orca Slicer says: “Object can’t be printed for empty layer between ' + z1 + ' and ' + z2 + ' mm. Make sure the object is printable or the object has faulty mesh.” ';
    if (type === 'empty') {
      box.appendChild(msg('error', 'The slice failed: ' + label + ' has empty layers at about ' + zr + ' mm above the plate.',
        'Part of it starts in mid-air there, and Supports is off, so nothing would hold it up while it prints. Turn Supports on and slice again.',
        [['Turn on Supports and slice again', function () { setSetting('enable_support', true); startSlice(); updateSummary(); }, 'primary'], ['Back to Layout', function () { gotoStep('layout'); }]],
        orca + 'Look at ' + name + ' at that height as it lies on the plate: a piece that starts in mid-air (an overhang with nothing under it) needs Supports, or the part laid another way.'));
    } else if (type === 'faulty') {
      box.appendChild(msg('error', 'The slice failed: ' + label + ' has a faulty mesh at about ' + zr + ' mm above the plate.',
        'Supports is already on, so the model itself has gaps or zero-thickness pieces there. Repair ' + name + ' in Onshape (look for faces that do not meet near ' + zr + ' mm), then ' +
          (S.ctx === 'standalone' ? 'upload the repaired file on the Parts step.' : 'press ↻ on its row on the Parts step to bring in the repaired version.'),
        [['Back to Parts', function () { gotoStep('parts'); }, 'primary']],
        orca + 'In Onshape, check that ' + name + ' is one closed solid with no zero-thickness walls or faces that only touch along an edge near that height, and that its Part Studio rebuilds with no errors.'));
    } else if (type === 'timeout') {
      box.appendChild(msg('error', 'The slice took longer than ' + (SLICE_TIMEOUT_S / 60) + ' minutes, the server’s limit, and was stopped.',
        job.instances.length > 1
          ? 'Slice again first: the server may have been busy. If it stops again, this plate of ' + job.instances.length + ' instances is too much at once: lower the quantities and print the rest on a second plate, or pick the Draft profile.'
          : 'Slice again first: the server may have been busy. If it stops again, pick the Draft profile, whose thicker layers slice faster.',
        job.instances.length > 1 ? [['Slice again', startSlice, 'primary'], ['Back to Parts', function () { gotoStep('parts'); }]]
                              : [['Slice again', startSlice, 'primary'], ['Back to Setup', function () { gotoStep('setup'); }]]));
    }
    updateNext();
  }
  function cancelSlice(why) {
    var job = S.job; if (!job || job.state !== 'running') return;
    var at = clock(job.t), stage = stageAt(job, job.shown).name;
    stopJob(job); job.state = 'cancelled';
    $('#slice-card').hidden = true;
    if (why === 'changed') return;         // the plate changed while it sliced: a new slice starts at once
    previewLead('The slice was cancelled, so there is nothing to preview.');
    var box = $('#preview-errors'); box.innerHTML = '';
    box.appendChild(msg('info', 'Slice cancelled at ' + at + ', during “' + stage + '”. Nothing was saved or sent to the printer.',
      'Change the plate or the settings with Back, or slice again.',
      [['Slice again', startSlice, 'primary'], ['Back to Layout', function () { gotoStep('layout'); }]]));
    updateNext();
  }
  function finishSlice(job) {
    stopJob(job); job.state = 'done';
    var est = Preview3D.estimate(job.tp, job.settings, filamentObj());
    S.result = { tp: job.tp, est: est, instances: job.instances, settings: job.settings, filament: filamentObj(), sliceTime: job.t };
    S.resultSig = job.sig;
    $('#slice-card').hidden = true;
    showResult(); updateSummary();
    if (job.conn && job.conn.done) {
      var t = $('#preview-toast'); t.hidden = false;
      t.textContent = 'The connection to the server dropped at ' + clock(job.conn.start) + ' and came back; the slice kept running and finished normally.';
      $('#preview-result').parentNode.insertBefore(t, $('#preview-result'));
    }
  }
  function showResult() {
    clearPreview();
    var r = S.result; $('#preview-result').hidden = false;
    var stats = $('#preview-stats'); stats.innerHTML = '';
    // the two numbers a student plans around, large; the rest on one quiet line
    [['Print time', hm(r.est.seconds)], ['Filament', Math.round(r.est.grams) + ' g ' + r.filament.type]].forEach(function (s) {
      var d = el('div', 'stat'); d.appendChild(el('strong', null, s[1])); d.appendChild(document.createTextNode(s[0])); stats.appendChild(d);
    });
    stats.appendChild(el('div', 'stat-line', r.instances.length + ' instance' + (r.instances.length === 1 ? '' : 's') + ' · ' + r.tp.layers + ' layers of ' + r.settings.layer_height + ' mm · sliced in ' + clock(r.sliceTime)));
    if (!viewer) viewer = Preview3D.createViewer($('#viewer-container'), PLATE);
    setTimeout(function () {
      viewer.resize(); viewer.show(r.tp, r.instances);
      Object.keys(S.hiddenTypes).forEach(function (k) { if (S.hiddenTypes[k]) viewer.setVisible(k, false); });
      setLayer(r.tp.layers - 1);
    }, 0);
    renderLegend(r);
    $('#preview-lead').textContent = 'Sliced. Check the layers, then Next to send it to the printer.';
    updateNext();
  }
  // The legend, as Orca's for line types: each type's share of the print time, and a click
  // on a row hides that type in the layer preview (and shows it again).
  function renderLegend(r) {
    var lg = $('#legend'); lg.innerHTML = '';
    var total = r.est.seconds;
    function short(s) { return s < 60 ? '<1 min' : hm(s); }
    function pct(s) { var p = s / total * 100; return p < 1 ? '<1%' : Math.round(p) + '%'; }
    Preview3D.TYPES.forEach(function (ty) {
      if (!r.tp.acc[ty.id].pos.length) return;
      var off = !!S.hiddenTypes[ty.id], secs = r.est.byType[ty.id] || 0;
      var li = el('li', 'lg-row' + (off ? ' off' : '')); li.setAttribute('role', 'button'); li.tabIndex = 0;
      li.setAttribute('aria-pressed', off ? 'false' : 'true');
      li.title = (off ? 'Show ' : 'Hide ') + ty.label.toLowerCase() + ' in the layer preview';
      var sw = el('i'); sw.style.background = '#' + ('00000' + ty.color.toString(16)).slice(-6); li.appendChild(sw);
      li.appendChild(el('span', 'lg-name', ty.label));
      li.appendChild(el('span', 'lg-time', short(secs)));
      li.appendChild(el('span', 'lg-pct', pct(secs)));
      function flip() { S.hiddenTypes[ty.id] = !S.hiddenTypes[ty.id]; if (viewer) viewer.setVisible(ty.id, !S.hiddenTypes[ty.id]); renderLegend(r); }
      li.addEventListener('click', flip);
      li.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flip(); } });
      lg.appendChild(li);
    });
    var other = el('li', 'lg-row fixed');
    other.appendChild(el('i', 'none')); other.appendChild(el('span', 'lg-name', 'Heating, travel, layer changes'));
    other.appendChild(el('span', 'lg-time', short(r.est.overhead))); other.appendChild(el('span', 'lg-pct', pct(r.est.overhead)));
    lg.appendChild(other);
  }
  function setLayer(k) {
    var r = S.result; if (!r) return;
    k = Math.max(0, Math.min(r.tp.layers - 1, Math.round(k)));
    S.layer = k;
    if (viewer) viewer.setLayer(k);
    var frac = r.tp.layers > 1 ? k / (r.tp.layers - 1) : 1;
    $('#ls-thumb').style.top = ((1 - frac) * 100) + '%';
    $('#ls-fill').style.height = (frac * 100) + '%';
    var z = r.tp.zs[k] || 0;
    $('#ls-label').textContent = 'Layer ' + (k + 1);
    $('#layer-readout').textContent = (k + 1) + ' of ' + r.tp.layers + ' · ' + z.toFixed(1) + ' mm high';
  }
  function bindPreview() {
    $('#btn-cancel').addEventListener('click', function () { cancelSlice('button'); });
    var slider = $('#layer-slider'), dragging = false;
    function fromY(e) {
      var r = slider.getBoundingClientRect(), f = 1 - (e.clientY - r.top) / r.height;
      if (S.result) setLayer(f * (S.result.tp.layers - 1));
    }
    slider.addEventListener('pointerdown', function (e) { dragging = true; slider.setPointerCapture(e.pointerId); fromY(e); e.preventDefault(); e.stopPropagation(); });
    slider.addEventListener('pointermove', function (e) { if (dragging) fromY(e); });
    slider.addEventListener('pointerup', function () { dragging = false; });
    slider.addEventListener('keydown', function (e) {
      if (!S.result) return;
      var n = S.result.tp.layers, k = S.layer;
      var map = { ArrowUp: k + 1, ArrowRight: k + 1, ArrowDown: k - 1, ArrowLeft: k - 1, PageUp: k + 10, PageDown: k - 10, Home: 0, End: n - 1 };
      if (map[e.key] !== undefined) { e.preventDefault(); setLayer(map[e.key]); }
    });
    $('#btn-layer-up').addEventListener('click', function () { setLayer(S.layer + 1); });
    $('#btn-layer-down').addEventListener('click', function () { setLayer(S.layer - 1); });
    $('#btn-preview-view').addEventListener('click', function () { if (viewer && S.result) viewer.reset(S.result.instances); });
    // final action on the Send step: PenguinCAM's split button. The button sends at once; the
    // caret's menu offers Download instead.
    $('#btn-do').addEventListener('click', function () { doAction(S.action); });
    $('#btn-do-caret').addEventListener('click', function (e) { e.stopPropagation(); $('#do-menu').hidden = !$('#do-menu').hidden; });
    $all('#do-menu li').forEach(function (li) {
      li.addEventListener('click', function () {
        // Choosing from the menu only changes what the button does; a separate press acts.
        // (On the first hardware test, a menu choice that printed at once surprised the owner.)
        S.action = li.getAttribute('data-action'); $('#do-menu').hidden = true;
        updateNext();
      });
    });
    document.addEventListener('click', function () { $('#do-menu').hidden = true; });
  }
  function doAction(a) {
    if (!S.result) return;
    if (a === 'download') {
      var t = $('#send-toast'); t.hidden = false;
      t.textContent = 'Downloaded the sliced file of ' + plateName(S.result.instances.length) + ' (' +(0.4 + S.result.instances.length * 0.21).toFixed(1) + ' MB). Mockup: no file is saved.';
      return;
    }
    sendToPrinter();
  }

  /* ================================================================== old printing (version 3), replaced below */
  /* ================================================================== the printer */
  // The shop printer, as the relay reports it: the real world, not this page. It outlives a
  // refresh, a closed panel and the scenario strip's Reset of the student's work. One delivery
  // job at a time (the relay's job slot); nothing queues.
  //   job: { mine, who, plate, what, phase: upload | starting | prepare | printing | waiting |
  //          finished | failed, up, t, prep, total, layers, pct, layer, sentAt, expectedEnd,
  //          waitingFor: { label, todo }, failAt (fraction), waitAt (fraction) }
  var PRN = { paired: true, online: true, heardAgoMin: 0, job: null };
  var PRINT_TRACK = ['Sending', 'Starting', 'Heating', 'Printing', 'Done'];
  function isLive(j) { return !!j && ['upload', 'starting', 'prepare', 'printing', 'waiting'].indexOf(j.phase) >= 0; }
  function nowMs() { return Date.now() + clockOffsetMs; }
  var clockOffsetMs = 0;           // "Come back 2 h later" moves this page's clock forward
  function newPrintJob(o) {
    var total = o.total, prep = o.prep || 270;
    var j = { mine: !!o.mine, who: o.who, plate: o.plate, what: o.what, phase: o.phase || 'upload', up: o.up || 0, t: o.t || 0, prep: prep, total: total,
              layers: o.layers, pct: 0, layer: 0, failAt: o.failAt || null, waitAt: o.waitAt || null, waitedS: 0, slowBy: o.slowBy || 1,
              el: o.t || 0, sentAt: new Date(nowMs() - (o.t || 0) * 1000) };
    // the estimate the slicer gave; the printer's own time left can drift behind it
    j.expectedEnd = new Date(j.sentAt.getTime() + (prep + total) * 1000);
    stepPrint(j, 0);
    return j;
  }
  var printTicker = null;
  function startPrintTicker() {
    if (printTicker) return;
    printTicker = addJob({ tick: function (dt) {
      var j = PRN.job;
      if (!j || !isLive(j) || !PRN.online) return;
      // a person takes a while to come to the printer: waiting runs slower, so it can be seen
      stepPrint(j, dt * Mock.factor(j.phase === 'upload' || j.phase === 'starting' ? 'slice' : j.mine && j.phase !== 'waiting' ? 'print' : 'other'));
      printerChanged(true);
    } });
    printTicker.server = true;
  }
  // Advance a print by s seconds of mock time.
  // The print keeps its own clock (j.el, mock seconds since it was sent), so its times of day
  // agree with each other whatever speed the scenario strip runs at.
  function stepPrint(j, s) {
    if (isLive(j)) j.el += s;
    stepPhase(j, s);
    if (!isLive(j) && !j.endedAt) j.endedAt = new Date(j.sentAt.getTime() + j.el * 1000);
  }
  function stepPhase(j, s) {
    if (j.phase === 'upload') { j.up = Math.min(1, j.up + s / 8); if (j.up >= 1) { j.phase = 'starting'; j.startT = 0; } return; }
    if (j.phase === 'starting') { j.startT = (j.startT || 0) + s; if (j.startT >= 4) j.phase = 'prepare'; return; }
    if (j.phase === 'waiting') {
      // the printer waits for a person; a person at the printer resumes it after a while
      j.waitedS += s; if (j.waitedS >= 600) { j.phase = 'printing'; j.waitAt = null; j.waitingFor = null; }
      return;
    }
    if (j.phase !== 'prepare' && j.phase !== 'printing') return;
    j.t += s / j.slowBy;
    if (j.t < j.prep) { j.phase = 'prepare'; return; }
    j.phase = 'printing';
    var f = Math.min(1, (j.t - j.prep) / j.total);
    j.pct = f * 100; j.layer = Math.max(1, Math.ceil(f * j.layers));
    if (j.waitAt && f >= j.waitAt) { j.phase = 'waiting'; j.waitedS = 0; j.waitingFor = { label: 'Filament ran out', todo: 'Load new filament, then resume the print on the printer’s screen.' }; return; }
    if (j.failAt && f >= j.failAt) { j.phase = 'failed'; return; }
    if (f >= 1) { j.phase = 'finished'; j.layer = j.layers; }
  }
  function remainingS(j) { return j.phase === 'upload' || j.phase === 'starting' ? j.prep + j.total : Math.max(0, (j.prep + j.total - j.t) * j.slowBy); }
  function finishAt(j) { return new Date(j.sentAt.getTime() + (j.el + remainingS(j)) * 1000); }
  function behindMin(j) { return isLive(j) ? Math.max(0, Math.round((finishAt(j) - j.expectedEnd) / 60000)) : 0; }
  // One reading of the printer for the header icon, the Setup line and the Send step.
  function printerStatus() {
    var j = PRN.job;
    if (!PRN.paired) return { key: 'none', short: 'No printer', title: 'No printer paired', chip: 'off' };
    if (!PRN.online) return { key: 'offline', short: 'Offline', title: ST.PRINTER.name + ' is not answering', chip: 'off' };
    if (!j) return { key: 'idle', short: 'Free', title: ST.PRINTER.name + ' is free', chip: '' };
    if (j.phase === 'upload' || j.phase === 'starting') return { key: 'sending', short: 'Sending ' + Math.floor(j.up * 100) + '%', title: 'Sending to ' + ST.PRINTER.name, chip: 'busy' };
    if (j.phase === 'prepare') return { key: 'printing', short: 'Heating', title: ST.PRINTER.name + ' is getting ready to print', chip: 'busy' };
    if (j.phase === 'printing') return { key: 'printing', short: 'Printing ' + Math.floor(j.pct) + '%', title: ST.PRINTER.name + ' is printing', chip: 'busy' };
    if (j.phase === 'waiting') return { key: 'waiting', short: 'Waiting', title: ST.PRINTER.name + ' is waiting for a person: ' + j.waitingFor.label.toLowerCase(), chip: 'wait' };
    if (j.phase === 'finished') return { key: 'finished', short: 'Finished', title: 'The last print finished', chip: '' };
    return { key: 'failed', short: 'Failed', title: 'The last print failed', chip: 'bad' };
  }
  // Why Send cannot send now, or null.
  function sendBlocked() {
    var st = printerStatus();
    if (st.key === 'none') return 'none';
    if (st.key === 'offline') return 'offline';
    if (PRN.job && isLive(PRN.job)) return PRN.job.mine ? 'mine' : 'other';
    return null;
  }
  // tick: only figures moved. The Send step is then rebuilt only when what it shows changes
  // (a stage, whose print it is, why Send waits), so no button is replaced under the pointer.
  var sendKey = '';
  function printerChanged(tick) {
    renderPrinterIcon();
    if (S.step === 'setup') renderPrinterLine();
    if (S.step === 'send') {
      var j = PRN.job, k = [sendBlocked(), j && j.phase, j && j.mine, !!S.result, printerStatus().key].join('|');
      if (!tick || k !== sendKey) renderSend();
      else {
        if (j && j.mine) renderPrintCard($('#send-live'), j);
        var bc = document.querySelector('#send-printer .busy-card'); if (bc && j && !j.mine) bc.parentNode.replaceChild(busyCard(j), bc);
        var chip = document.querySelector('#send-summary .pstate'); if (chip && PRN.paired) chip.textContent = printerStatus().short;
      }
    }
    updateNext();
  }
  function renderPrinterIcon() {
    var st = printerStatus(), b = $('#pstat'), j = PRN.job;
    b.className = 'pstat s-' + st.key + (j && behindMin(j) >= 5 ? ' behind' : '');
    b.querySelector('.ptext').textContent = st.short;
    b.title = st.title + ': click for details';
    if (!$('#pstat-pop').hidden) renderPrinterPop();
  }
  function dl(grid, k, v, cls) { grid.appendChild(el('dt', null, k)); var d = el('dd', cls || null, v); grid.appendChild(d); return d; }
  function renderPrinterPop() {
    var pop = $('#pstat-pop'), st = printerStatus(), j = PRN.job; pop.innerHTML = '';
    var head = el('div', 'pp-head'); head.appendChild(el('span', 'pp-title', st.title + '.'));
    var x = el('button', 'pp-close', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Close'); x.addEventListener('click', closePrinterPop); head.appendChild(x);
    pop.appendChild(head);
    if (st.key === 'none') { pop.appendChild(el('div', 'pp-note', 'Your team has not paired a printer with PenguinSlicer yet. A mentor pairs it once, from the shop computer beside the printer.')); return; }
    pop.appendChild(el('div', 'pp-sub', ST.PRINTER.name + ', ' + ST.PRINTER.model));
    if (st.key === 'offline') { pop.appendChild(el('div', 'pp-note', 'Not heard from for ' + PRN.heardAgoMin + ' minutes. Check that the printer and the shop computer beside it are on and connected to the network.')); return; }
    if (!j) { pop.appendChild(el('div', 'pp-note', 'Nothing is printing. It is free for the next plate.')); return; }
    var g = el('dl', 'pp-grid');
    // the first row's label follows the phase: a plate on its way is not printing yet
    dl(g, j.phase === 'upload' || j.phase === 'starting' ? 'Sending' : j.phase === 'finished' ? 'Printed' : j.phase === 'failed' ? 'Was printing' : 'Printing', j.what);
    dl(g, 'For', j.mine ? j.who + ' (you)' : j.who);
    if (isLive(j)) {
      dl(g, 'Done', j.phase === 'upload' || j.phase === 'starting' ? 'sending ' + Math.floor(j.up * 100) + '%' : j.phase === 'prepare' ? 'heating, 0%' : Math.floor(j.pct) + '%, layer ' + j.layer + ' of ' + j.layers);
      dl(g, 'Time left', hm(remainingS(j)));
      dl(g, 'Expected finish', clockTime(finishAt(j)));
      var late = behindMin(j);
      dl(g, 'Estimate', late >= 5 ? late + ' min behind its estimate (' + clockTime(j.expectedEnd) + ')' : 'on time', late >= 5 ? 'pp-late' : null);
    } else {
      dl(g, j.phase === 'finished' ? 'Finished' : 'Stopped', clockTime(j.endedAt) + (j.phase === 'failed' ? ', layer ' + j.layer + ' of ' + j.layers : ''));
    }
    pop.appendChild(g);
    if (isLive(j)) { var bar = el('div', 'pp-bar'), f = el('div'); f.style.width = (j.phase === 'upload' || j.phase === 'starting' ? j.up * 100 : j.pct) + '%'; bar.appendChild(f); pop.appendChild(bar); }
    if (j.phase === 'waiting') pop.appendChild(el('div', 'pp-note pp-late', j.waitingFor.label + '. ' + j.waitingFor.todo));
    pop.appendChild(el('div', 'pp-note', isLive(j) ? 'The printer’s own report, a few seconds behind. To pause or stop a print, use the printer’s screen.'
                                                    : j.phase === 'finished' ? 'Take the plate off before the next print.' : 'Clear the plate at the printer before the next print.'));
  }
  function togglePrinterPop(e) {
    e.stopPropagation();
    var pop = $('#pstat-pop'), open = pop.hidden;
    pop.hidden = !open; $('#pstat').setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) renderPrinterPop();
  }
  function closePrinterPop() { $('#pstat-pop').hidden = true; $('#pstat').setAttribute('aria-expanded', 'false'); }

  // The scenario strip's Printer menu: what someone else is doing at the shop printer.
  function setPrinter(kind, quiet) {
    PRN.paired = kind !== 'unpaired'; PRN.online = kind !== 'offline'; PRN.heardAgoMin = kind === 'offline' ? 7 : 0;
    var other = { mine: false, who: OTHER, plate: plateName(8), what: '8 instances of Gusset Plate', layers: 96, total: 2 * 3600 + 25 * 60 };
    if (kind === 'idle') PRN.job = null;          // offline and not paired keep whatever the printer was doing
    if (kind === 'other_sending') PRN.job = newPrintJob(Object.assign(other, { phase: 'upload', up: 0.35 }));
    if (kind === 'other_printing') PRN.job = newPrintJob(Object.assign(other, { phase: 'printing', t: 270 + 0.61 * other.total }));
    if (kind === 'other_behind') { PRN.job = newPrintJob(Object.assign(other, { phase: 'printing', t: 270 + 0.48 * other.total })); PRN.job.expectedEnd = new Date(finishAt(PRN.job).getTime() - 22 * 60000); }
    if (kind === 'other_waiting') { PRN.job = newPrintJob(Object.assign(other, { phase: 'printing', t: 270 + 0.3 * other.total })); PRN.job.phase = 'waiting'; PRN.job.waitingFor = { label: 'Front door open', todo: 'Close the front door, then resume the print on the printer’s screen.' }; }
    if (kind === 'finished') { PRN.job = newPrintJob(Object.assign(other, { phase: 'printing', t: 270 + other.total })); PRN.job.endedAt = new Date(nowMs() - 25 * 60000); }
    if (kind === 'failed') { PRN.job = newPrintJob(Object.assign(other, { phase: 'printing', t: 270 + 0.2 * other.total, failAt: 0.2 })); stepPrint(PRN.job, 1); PRN.job.endedAt = new Date(nowMs() - 12 * 60000); }
    startPrintTicker();
    if (!quiet && S) printerChanged();
  }

  /* ================================================================== Send step */
  function partsLine() {
    return S.parts.filter(function (p) { return p.status === 'ready'; }).map(function (p) { return (p.qty > 1 ? p.qty + ' × ' : '') + p.name; });
  }
  function renderSend() {
    var r = S.result, why = sendBlocked(), j = PRN.job, mineLive = j && j.mine && isLive(j), mineEnded = j && j.mine && !isLive(j);
    sendKey = [why, j && j.phase, j && j.mine, !!r, printerStatus().key].join('|');
    var live = $('#send-live'), sum = $('#send-summary'), pr = $('#send-printer');
    // the progress of this student's own plate, at the top, once sent
    if (j && j.mine) renderPrintCard(live, j); else { live.innerHTML = ''; live.removeAttribute('data-key'); }
    // the lead follows the phase of this student's print, and the printer's state otherwise
    var ph = j && j.phase, atScreen = ' Pausing or stopping a print is done at the printer’s screen.';
    $('#send-lead').textContent = mineLive ? (ph === 'upload' || ph === 'starting' ? 'Your plate is on its way to ' + ST.PRINTER.name + '.' + atScreen
                                            : ph === 'prepare' ? ST.PRINTER.name + ' is heating up to print your plate.' + atScreen
                                            : ph === 'waiting' ? 'Your print is waiting for a person at the printer: ' + j.waitingFor.label.toLowerCase() + '.'
                                            : 'Your plate is printing on ' + ST.PRINTER.name + '.' + atScreen)
      : mineEnded ? (j.phase === 'finished' ? 'Your print finished.' : 'Your print stopped.')
      : why === 'other' ? ST.PRINTER.name + ' is busy with someone else’s print, so Send waits until it is free.'
      : why === 'none' ? 'No printer is paired with your team, so Send is off.'
      : why === 'offline' ? 'Send waits until ' + ST.PRINTER.name + ' can be reached.'
      : 'Check the plate on the printer, then send. It starts printing as soon as it arrives.';
    // what will be printed
    sum.innerHTML = '';
    if (!r) { sum.appendChild(msg('info', 'Nothing sliced yet.', 'Go Back to the Preview step: the plate is sliced there.', [['Back to Preview', function () { gotoStep('preview'); }]])); pr.innerHTML = ''; return; }
    var c = el('div', 'card'), g = el('dl', 'send-sum');
    var p = dl(g, 'Printer', ''), st = printerStatus();
    if (st.key === 'none') p.appendChild(el('span', 'pstate off', 'No printer paired'));
    else { p.appendChild(document.createTextNode(ST.PRINTER.name + ' ')); p.appendChild(el('span', 'pstate ' + st.chip, st.short)); }
    var ul = el('ul'); partsLine().forEach(function (t) { ul.appendChild(el('li', null, t)); });
    var ii = dl(g, 'Instances', ''); ii.appendChild(el('div', 'big', r.instances.length + ' on one plate')); ii.appendChild(ul);
    var tt = dl(g, 'Print time', ''); tt.appendChild(el('span', 'big', hm(r.est.seconds)));
    var ff = dl(g, 'Filament', ''); ff.appendChild(el('span', 'big', Math.round(r.est.grams) + ' g')); ff.appendChild(document.createTextNode(' of ' + r.filament.name));
    c.appendChild(g); sum.appendChild(c);
    // the printer, and why Send waits
    pr.innerHTML = '';
    if (!mineLive) {
      if (!why) {
        var cp = el('div', 'clear-plate');
        cp.appendChild(el('span', null, '⚠'));
        var t = el('div'); t.appendChild(el('strong', null, 'Check that the plate is clear')); t.appendChild(document.createTextNode(' and ' + r.filament.type + ' is loaded. Send starts the print at once; nobody is asked again.'));
        cp.appendChild(t); pr.appendChild(cp);
      } else if (why === 'other') pr.appendChild(busyCard(j));
      else if (why === 'offline') pr.appendChild(msg('warn', ST.PRINTER.name + ' has not been heard from for ' + PRN.heardAgoMin + ' minutes, so Send waits.',
        'Your sliced plate stays ready. Check that the printer and the shop computer beside it are on and connected to the network; Send comes back as soon as the printer answers. Or download the file.',
        [['Download the sliced file', function () { doAction('download'); }]]));
      else if (why === 'none') pr.appendChild(msg('warn', 'Your team has no printer paired with PenguinSlicer, so nothing can be sent.',
        'A mentor pairs the printer once, from the shop computer beside it. Meanwhile, download the file and print it from Orca Slicer or Bambu Studio.',
        [['Download the sliced file', function () { doAction('download'); }]]));
    }
  }
  // Another student's print or send: whose, what, how far, when it should finish. Send waits;
  // the sliced plate stays ready; nothing queues.
  function busyCard(j) {
    var c = el('div', 'card busy-card');
    var sending = j.phase === 'upload' || j.phase === 'starting', waiting = j.phase === 'waiting';
    c.appendChild(el('div', 'bc-title', ST.PRINTER.name + ' is busy: ' + (sending ? 'receiving a plate from ' : waiting ? 'waiting for a person, printing for ' : 'printing for ') + j.who + '.'));
    c.appendChild(el('div', 'hint', j.what));
    var g = el('div', 'bc-grid');
    function cell(v, k, cls) { var d = el('div', cls || null); d.appendChild(el('strong', null, v)); d.appendChild(document.createTextNode(k)); g.appendChild(d); }
    cell(sending ? Math.floor(j.up * 100) + '%' : Math.floor(j.pct) + '%', sending ? 'sent' : 'done');
    cell(sending ? '0 of ' + j.layers : j.layer + ' of ' + j.layers, 'layer');
    cell(hm(remainingS(j)), 'time left');
    var late = behindMin(j);
    cell(clockTime(finishAt(j)), late >= 5 ? late + ' min behind' : 'should finish', late >= 5 ? 'late' : null);
    c.appendChild(g);
    if (waiting) c.appendChild(el('div', 'bc-note pp-late', j.waitingFor.label + ': someone at the printer has to ' + j.waitingFor.todo.charAt(0).toLowerCase() + j.waitingFor.todo.slice(1)));
    c.appendChild(el('div', 'bc-note', 'Send waits until the printer is free; your sliced plate stays ready here. Nothing queues: come back, or keep this panel open, and send when it is free.'));
    return c;
  }
  function sendToPrinter() {
    if (!sliceReady() || sendBlocked()) return;
    $('#send-errors').innerHTML = ''; $('#send-toast').hidden = true;
    var r = S.result;
    PRN.job = newPrintJob({ mine: true, who: ME, plate: plateName(r.instances.length), what: plural(r.instances.length, 'instance', 'instances') + ': ' + partsLine().join(', '),
                            layers: r.tp.layers, total: r.est.seconds, failAt: Mock.take('print_fail') ? 0.38 : null, waitAt: Mock.take('print_wait') ? 0.3 : null });
    PRN.job.sliceSig = S.resultSig;
    startPrintTicker(); printerChanged();
    $('#wiz-body').scrollTop = 0;
  }
  // This student's own delivery job and print: stages, percent, layer, time left, expected
  // finish. The card is built once per stage; between stages only its figures change, so a
  // button in it is never replaced under the pointer.
  function printCells(j) {
    if (j.phase === 'failed') return [[j.layer + ' of ' + j.layers, 'layer reached'], [clockTime(j.endedAt), 'stopped at']];
    if (j.phase === 'finished') return [[j.layers + ' of ' + j.layers, 'layers'], [clockTime(j.endedAt), 'finished at']];
    var late = behindMin(j);
    return [
      [j.phase === 'printing' || j.phase === 'waiting' ? j.layer + ' of ' + j.layers : '0 of ' + j.layers, 'layer'],
      [hm(remainingS(j)), 'time left'],
      [clockTime(finishAt(j)), late >= 5 ? late + ' min behind' : 'expected finish', late >= 5 ? 'late' : null],
      [clockTime(j.sentAt), 'sent at']
    ];
  }
  function renderPrintCard(card, j) {
    var at = j.phase === 'upload' ? 0 : j.phase === 'starting' ? 1 : j.phase === 'prepare' ? 2 : j.phase === 'finished' ? 4 : 3;
    var key = j.phase + ':' + at;
    if (card.getAttribute('data-key') === key && card.firstChild) {
      var pc = card.querySelector('.pc-pct'), bf = card.querySelector('.pc-bar div'), strongs = card.querySelectorAll('.pc-grid strong');
      if (pc) pc.textContent = j.phase === 'upload' || j.phase === 'starting' ? Math.floor(j.up * 100) + '%' : Math.floor(j.pct) + '%';
      if (bf) bf.style.width = (j.phase === 'upload' || j.phase === 'starting' ? j.up * 100 : j.pct) + '%';
      printCells(j).forEach(function (c, i) { if (strongs[i]) strongs[i].textContent = c[0]; });
      return;
    }
    card.setAttribute('data-key', key); card.innerHTML = '';
    var box = el('div', 'print-card' + (j.phase === 'upload' || j.phase === 'starting' ? ' uploading' : '') + (j.phase === 'waiting' ? ' waiting' : '') + (j.phase === 'failed' ? ' failed' : ''));
    var head = el('div', 'pc-head');
    var states = { upload: 'Sending to ' + ST.PRINTER.name, starting: 'Starting the print', prepare: 'Heating the bed and nozzle', printing: 'Printing',
                   waiting: 'Waiting for a person: ' + (j.waitingFor ? j.waitingFor.label.toLowerCase() : ''), finished: 'Print finished', failed: 'Print stopped' };
    var dot = el('span', 'dot' + (isLive(j) ? ' pulse' : ''));
    if (j.phase === 'failed') dot.style.background = 'var(--danger)';
    if (j.phase === 'upload' || j.phase === 'starting') dot.style.background = 'var(--accent)';
    if (j.phase === 'waiting') dot.style.background = 'var(--warn-line)';
    head.appendChild(dot); head.appendChild(el('span', 'pc-state', states[j.phase]));
    var big = j.phase === 'upload' || j.phase === 'starting' ? Math.floor(j.up * 100) + '%' : j.phase === 'prepare' ? '' : Math.floor(j.pct) + '%';
    if (big) head.appendChild(el('span', 'pc-pct', big));
    box.appendChild(head);
    box.appendChild(el('div', 'pc-file', j.plate + ', on ' + ST.PRINTER.name));
    var track = el('ol', 'pc-track');
    PRINT_TRACK.forEach(function (name, i) {
      track.appendChild(el('li', i < at ? 'done' : i === at ? (j.phase === 'failed' ? 'bad' : j.phase === 'finished' ? 'done' : j.phase === 'waiting' ? 'wait' : 'now') : '', name));
    });
    box.appendChild(track);
    var bar = el('div', 'pc-bar'), fill = el('div'); fill.style.width = (j.phase === 'upload' || j.phase === 'starting' ? j.up * 100 : j.pct) + '%'; bar.appendChild(fill); box.appendChild(bar);
    var g = el('div', 'pc-grid');
    printCells(j).forEach(function (c) { var d = el('div', c[2] || null); d.appendChild(el('strong', null, c[0])); d.appendChild(document.createTextNode(c[1])); g.appendChild(d); });
    box.appendChild(g);
    if (j.phase === 'upload') {
      box.appendChild(el('div', 'pc-note', 'Nothing prints until the whole file has arrived.'));
      var ua = el('div', 'pc-acts');
      ua.appendChild(btn('Cancel sending', function () {
        PRN.job = null; printerChanged();
        notify('info', 'Sending cancelled. Nothing reached ' + ST.PRINTER.name + ' and nothing will print.', 'Your sliced plate is still here: send it again when you are ready.', 'cancel-send');
      }, 'danger-outline'));
      box.appendChild(ua);
    } else if (isLive(j)) {
      box.appendChild(el('div', 'pc-note', 'From the printer’s own report, a few seconds behind. To pause or stop the print, use the printer’s screen; this panel cannot.'));
    }
    if (j.phase === 'waiting') box.appendChild(msg('warn', j.waitingFor.label + '.', j.waitingFor.todo));
    if (j.phase === 'finished') box.appendChild(msg('ok', 'The print finished: layer ' + j.layers + ' of ' + j.layers + '.', 'Take the plate off once the bed has cooled; PETG lets go more easily when cool.'));
    if (j.phase === 'failed') box.appendChild(msg('error', 'The print stopped at layer ' + j.layer + ' of ' + j.layers + ' (' + Math.floor(j.pct) + '%): the printer reported a filament tangle or a clogged nozzle.',
      'Clear the plate and check the filament path at the printer, then send the plate again from here. The sliced file is still here.', null,
      'The printer’s screen shows the fault and its own help for it. Check the filament path from the spool to the nozzle, and the nozzle for a clog.'));
    card.appendChild(box);
  }

  /* ================================================================== wiring */
  function bindNav() {
    $('#btn-next').addEventListener('click', function () { var i = ORDER.indexOf(S.step); if (i < ORDER.length - 1 && canLeave(S.step)) gotoStep(ORDER[i + 1]); });
    $('#btn-back').addEventListener('click', function () { var i = ORDER.indexOf(S.step); if (i > 0) gotoStep(ORDER[i - 1]); });
    $all('#stepbar li').forEach(function (li) {
      li.addEventListener('click', function () { navigateTo(li.getAttribute('data-step')); });
      li.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigateTo(li.getAttribute('data-step')); } });
    });
    $('#pstat').addEventListener('click', togglePrinterPop);
    $('#pstat-pop').addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', closePrinterPop);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePrinterPop(); });
  }

  // Start the page afresh. Work that runs on the server (a slice job, the printer) is not the
  // page's: it survives unless `wipe` says the scenario strip's Reset threw the student's work away.
  function reset(ctx, keep) {
    jobs.slice().forEach(function (j) { if (!j.server) dropJob(j); });
    if (!keep && S && S.job && S.job.state === 'running') { stopJob(S.job); S.job.state = 'cancelled'; }
    S = fresh(ctx || 'partstudio');
    partsNote = null; layHint = null; lastAdded = null;
    $('#advanced').hidden = true; placePrinterIcon(false);
    pendingSnap = null;
    if (editor) editor.sync();
    if (viewer) viewer.clear();
    clearPreview();
    $('#send-live').innerHTML = ''; $('#send-live').removeAttribute('data-key');
    renderPrinterIcon();
    gotoStep('setup');
  }

  /* ================================================================== coming back */
  // The scenario strip's Refresh page, Close and reopen, and Come back 2 h later. The page's
  // own state is lost each time; what the server holds is not: this student's slice job (with
  // its plate configuration) and delivery job, and the printer. When this student's slice or
  // send is still running, the wizard opens on that step with the parts and layout restored.
  // Otherwise it starts at Setup, and the printer-status icon shows what anyone else is doing.
  function comeBack(kind) {
    var held = S.job && (S.job.state === 'running' || S.job.state === 'done') ? S.job : null;
    var plate = { ctx: S.ctx, parts: S.parts.filter(function (p) { return p.status === 'ready'; }), instances: S.instances, filament: S.filament,
                  profile: S.profile, changes: S.changes, result: S.result, resultSig: S.resultSig, job: held, laidOut: S.laidOut, old: S, nextId: S.nextId };
    if (kind === 'later') {
      clockOffsetMs += 2 * 3600 * 1000;
      if (held && held.state === 'running' && held.tp && !held.fail && !held.timeout) { held.t = held.actual; tickSlice(held, 0); plate.result = S.result; plate.resultSig = S.resultSig; }
      if (PRN.job) for (var k = 0; k < 400 && isLive(PRN.job); k++) stepPrint(PRN.job, 18);     // 400 × 18 s = two hours
      renderPrinterIcon();
    }
    var curtain = $('#curtain');
    curtain.hidden = false; curtain.className = 'curtain' + (kind === 'reopen' ? ' closed' : '');
    curtain.textContent = kind === 'refresh' ? 'Reloading the page…' : kind === 'reopen' ? 'The PenguinSlicer panel is closed.' : 'Two hours later…';
    setTimeout(function () {
      if (kind !== 'refresh') curtain.textContent = 'Opening PenguinSlicer…';
      setTimeout(function () { curtain.hidden = true; reopen(plate, kind); }, 500);
    }, kind === 'refresh' ? 400 : 900);
  }
  function reopen(plate, kind) {
    // a slice that finished while the page was away left its result with the server
    if (plate.job && plate.job.state === 'done' && plate.old.result && plate.old.resultSig === plate.job.sig) { plate.result = plate.old.result; plate.resultSig = plate.old.resultSig; }
    reset(plate.ctx, true);
    var j = PRN.job, sending = j && j.mine && isLive(j) && j.sliceSig === plate.resultSig;
    var slicing = plate.job && plate.job.state === 'running';
    var sliced = kind !== 'later' && plate.result && plate.resultSig;          // a finished slice the server still holds
    if (sending || slicing || sliced) {
      S.parts = plate.parts; S.instances = plate.instances; S.filament = plate.filament; S.profile = plate.profile; S.changes = plate.changes;
      S.laidOut = plate.laidOut; S.job = plate.job; S.result = plate.result; S.resultSig = plate.resultSig; S.nextId = plate.nextId;
      S.parts.forEach(function (p) { p.autoTold = true; });
      gotoStep(sending ? 'send' : 'preview');
      // Said in the past tense, of the moment the page went away, and pointing below: the card
      // under it moves on (a slice finishes, a print goes from sending to done), this does not.
      notify('info', sending ? 'Back where you were. You had sent your plate to ' + ST.PRINTER.name + ' before you left; its progress is below.'
                             : slicing ? 'Back where you were. Your plate was still slicing when you left; see below.' : 'Back where you were. Your plate was sliced and ready to send when you left.',
        'Your parts and layout are as you left them.', 'resumed');
    } else {
      if (j && j.mine && !isLive(j) && kind === 'later') {
        notify(j.phase === 'finished' ? 'ok' : 'error', j.phase === 'finished' ? 'Your print finished at ' + clockTime(j.endedAt) + '.' : 'Your print stopped at ' + clockTime(j.endedAt) + ', at layer ' + j.layer + ' of ' + j.layers + '.',
          j.phase === 'finished' ? 'Take it off the plate if nobody has yet. Start a new plate here.' : 'Clear the plate at the printer. Your parts were not kept; add them again to print again.', 'resumed');
      }
      // a finished slice that was never sent does not outlast two hours away (M18); say so in one line
      var sentIt = j && j.mine && j.sliceSig === plate.resultSig;
      if (kind === 'later' && plate.result && plate.resultSig && !sentIt) notify('info', 'The slice of your earlier plate has expired; add its parts again to print it.', null, 'expired');
    }
  }

  bindNav(); bindSetup(); bindAdvanced(); bindParts(); bindLayout(); bindPreview();

  window.Wizard = {
    Mock: Mock, reset: reset, onOnshapeSelect: onOnshapeSelect, setOption: setOption,
    setPrinter: setPrinter, comeBack: comeBack,
    armed: function () { if (S.step === 'layout') applyLayoutArms(); },
    state: function () { return S; },
    printer: function () { return PRN; },
    step: function () { return S.step; },
    resize: function () { if (editor) editor.resize(); if (viewer) viewer.resize(); }
  };
})();
