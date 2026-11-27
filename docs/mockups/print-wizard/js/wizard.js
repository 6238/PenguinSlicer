/* PenguinSlicer mockup, version 8: the wizard in the panel. Five steps (Parts, Settings,
 * Layout, Preview, Send), advanced mode, mocked export with its two ways to fail, slicing
 * progress, layer preview, the Send step with delivery and print progress, the printer
 * status in the header, coming back to running work, and every armed error from the
 * scenario strip. Everything here is fake: no request leaves the page. */
(function () {
  'use strict';
  var T = THREE, P = MockParts, ST = MockSettings, PL = MockPlate, U = MockUnits;
  var PLATE = ST.PRINTER.plate;
  // 'setup' is the Settings step's internal name (it was called Setup until version 5)
  var ORDER = ['parts', 'setup', 'layout', 'preview', 'send'];
  var MAX_INSTANCES = 150;                                // the slice service's limit (slice/limits.py)
  var PLATE_VOLUME_CAP_CM3 = 600;                         // invented: a volume cap from the memory model
  var SLICE_TIMEOUT_S = 240;                              // print/limits.py PLATE_SLICE_TIMEOUT_S
  var TOO_MANY_INSTANCES_MESSAGE = 'Up to ' + MAX_INSTANCES + ' instances per plate; print the rest on a second plate.';
  var ME = 'Sam Rivera', OTHER = 'Alex Chen';             // Onshape names: this user, and another
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
    return { ctx: ctx, step: ORDER[0], filament: 'petg', profile: ST.profilesOf('petg')[0].id, changes: {}, parts: [], instances: [],
             selected: [], nextId: 1, laidOut: false, problems: [], job: null, result: null, resultSig: null,
             action: 'print', layer: 0, advTab: 'Quality', advOpen: {}, advSecOpen: {}, advFocus: null,
             layoutNotes: [], previewMsg: null, undo: [], redo: [], notices: [] };
  }
  // The choices made in the scenario strip; they outlast Reset, since they are the owner's,
  // not the user's: how an instance is laid on a face, the mouse scheme, how parts arrive.
  var Opt = { lay: 'hull', scheme: 'O', arrival: 'auto' };
  // The configuration (the one the header names), set once by an administrator: the units
  // an uploaded file is read in. Inches unless the configuration says millimetres.
  var Config = { uploadUnits: 'in' };
  function profileObj() { return ST.profileById[S.profile]; }
  function filamentObj() { return ST.FILAMENTS.filter(function (f) { return f.id === S.filament; })[0]; }
  function readyParts() { return S.parts.filter(function (p) { return p.status === 'ready'; }); }
  // Version 7 (the owner): printer and plate figures (the plate, the height limit, spacing,
  // layer heights) are always in millimetres, so MockUnits' default stays 'mm'; only a part's
  // own size follows its part's units (unitsOf). And the spacing the slice service requires
  // for the Settings step's supports setting.
  function unitsOf(c) { var p = c && partById(c.partId); return p && p.units === 'in' ? 'in' : 'mm'; }
  PLATE.unitsOf = unitsOf;
  function syncPlateRules() {
    U.unit = 'mm';
    var on = !!eff().enable_support;
    PLATE.supportsOn = on; PLATE.spacing = on ? PLATE.spacingOn : PLATE.spacingOff;
  }
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
  // A plate is named to a user in words ("Plate 1, 16 instances"), never by the sliced
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
  function clockTime(d) {                               // a time of day, as anyone reads a clock
    var h = d.getHours(), m = d.getMinutes(), pm = h >= 12; h = h % 12 || 12;
    return h + ':' + ('0' + m).slice(-2) + (pm ? ' pm' : ' am');
  }

  /* ------------------------------------------------------------------ messages */
  // what happened; what to do next; remedy buttons; optional details, folded. The details say
  // what is wrong with the part or the plate and where to look in Onshape or at the printer;
  // never a route, a status code, a page id or anything else inside PenguinSlicer.
  function msg(kind, what, todo, acts, details) {
    var d = el('div', 'msg ' + kind);
    d.appendChild(el('div', 'what', what));
    if (todo) d.appendChild(el('div', 'todo', todo));
    if (acts && acts.length) {
      var a = el('div', 'acts');
      acts.forEach(function (x) { a.appendChild(btn(x[0], x[1], x[2])); });
      d.appendChild(a);
    }
    if (details) {
      var det = el('details'); det.appendChild(el('summary', null, 'Details'));
      det.appendChild(el('div', null, details)); d.appendChild(det);
    }
    return d;
  }
  // A notification: at the top of the step, until the user closes it (×) or it is replaced.
  // Used when something happened that is not on a row of a list: a part that did not arrive.
  function notify(kind, what, todo, key) {
    S.notices = S.notices.filter(function (n) { return !key || n.key !== key; });
    S.notices.push({ kind: kind, what: what, todo: todo, key: key || ('n' + Math.random()) });
    renderNotices();
  }
  // A notification that stops being true goes away when its state ends.
  function dropNotice(key) {
    var n = S.notices.length;
    S.notices = S.notices.filter(function (m) { return m.key !== key; });
    if (S.notices.length !== n) renderNotices();
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
    if (target > cur) {
      for (var i = cur; i < target; i++) {
        if (i === 2) enterLayoutData();
        if (!canLeave(ORDER[i])) { sayWhy(ORDER[i]); return; }
      }
    }
    gotoStep(name);
  }
  // A click on a later step tab that an earlier step holds back: one line under the tabs,
  // where the user is looking, says which step and why. It goes at the next move, or after a while.
  var STEP_NAME = { parts: 'Parts', setup: 'Settings', layout: 'Layout', preview: 'Preview', send: 'Send' };
  var whyTimer = null;
  function sayWhy(step) {
    var why;
    if (step === 'parts') why = totalInstances() > MAX_INSTANCES ? 'a plate holds up to ' + MAX_INSTANCES + ' instances.' : S.parts.length ? 'no part has arrived yet.' : 'add a part.';
    else if (step === 'layout') {
      var p = S.problems;
      why = !S.instances.length ? 'there are no instances.' : p[0].message.split('. ')[0] + '.' + (p.length > 1 ? ' (+' + (p.length - 1) + ' more)' : '');
    } else if (step === 'preview') why = 'the plate is not sliced yet.';
    var line = $('#step-why'); line.hidden = false;
    line.textContent = STEP_NAME[step] + ' first: ' + why;
    clearTimeout(whyTimer); whyTimer = setTimeout(clearWhy, 8000);
  }
  function clearWhy() { clearTimeout(whyTimer); var line = $('#step-why'); if (line) { line.hidden = true; line.textContent = ''; } }
  // Moving back and forth always works. Leaving the Preview step while it slices leaves the
  // slice running on the server; coming back to it with the same plate finds it still going,
  // or finished. A changed plate starts a new slice (see enterPreview).
  function gotoStep(name) {
    if (S.step !== name) { S.notices = []; S.lastNoteOn = null; }    // a notification belongs to the step it was given on; so does the last-print note
    if (S.step === 'layout' && name !== 'layout') layHint = null;   // so does the Layout step's message ("Arranged 5 instances.")
    S.step = name;
    closePrinterPop(); closeChangesPop(); clearWhy(); closeLayoutHelp(); closeKey(); setPreviewHelp(false); hideTip();
    $all('#wizard .step').forEach(function (s) { s.hidden = s.getAttribute('data-step') !== name; });
    $all('#stepbar li').forEach(function (li) {
      var s = li.getAttribute('data-step');
      li.classList.toggle('active', s === name);
      li.classList.toggle('done', ORDER.indexOf(s) < ORDER.indexOf(name));
    });
    $('#btn-back').disabled = name === ORDER[0];
    $('#btn-next').hidden = name === 'send';
    $('#final-action').hidden = name !== 'send'; $('#wiz-nav').classList.toggle('on-send', name === 'send');
    $('#do-menu').hidden = true; $('#btn-do-caret').setAttribute('aria-expanded', 'false');
    $('#wiz-body').scrollTop = 0;
    if (name === 'setup') renderSetup();
    if (name === 'parts') renderParts();
    if (name === 'layout') enterLayout();
    if (name === 'preview') enterPreview();
    if (name === 'send') renderSend();
    updateNext(); updateSummary(); renderNotices(); renderLastPrint();
  }
  function updateNext() {
    if (S.step !== 'send') $('#btn-next').disabled = !canLeave(S.step);
    var b = $('#btn-do'), ready = sliceReady(), why = sendBlocked();
    if (S.action === 'download') { b.textContent = 'Download the sliced file'; b.disabled = !ready; }
    else {
      var mine = PRN.job && PRN.job.mine && isLive(PRN.job);
      // while this user's plate is on its way or printing, the button says so and cannot send again
      var ph = mine ? PRN.job.phase : null;
      b.textContent = mine ? (ph === 'upload' || ph === 'starting' ? 'Sending…' : ph === 'prepare' ? 'Heating…' : ph === 'waiting' ? 'Waiting for a person…' : 'Printing…')
        : PRN.paired ? 'Send to ' + ST.PRINTER.name : 'Send to printer';
      b.disabled = !ready || !!why;
    }
    $('#btn-do-caret').disabled = !ready;
    // the menu's Send item has the button's own label ("Send to Shop H2S")
    $('#do-print').textContent = PRN.paired ? 'Send to ' + ST.PRINTER.name : 'Send to printer';
  }
  function updateSummary() {
    var box = $('#wiz-summary'), idx = ORDER.indexOf(S.step);
    syncPlateRules();
    box.innerHTML = '';
    if (idx < 1) { box.hidden = true; closeChangesPop(); return; }
    box.hidden = false;
    // Version 7 (the owner): the plate summary is two lines of text, not a row of chips, on
    // every step from Settings on. First line: parts and instances. Second line: filament and
    // profile, cut with an ellipsis when too long (never wrapped), then the "+2 changes" pill,
    // which stays whole and opens the change details. No plate area, no time and grams.
    var parts = readyParts().length;
    box.appendChild(el('div', 'sum-line', parts + ' part' + (parts === 1 ? '' : 's') + ' · ' + totalInstances() + ' instance' + (totalInstances() === 1 ? '' : 's')));
    var line2 = el('div', 'sum-line sum-set'), set = filamentObj().type + ' · ' + profileObj().name, st = el('span', 'sum-text', set);
    st.title = filamentObj().name + ' · ' + profileObj().name;
    line2.appendChild(st); box.appendChild(line2);
    var n = changeCount();
    if (n) {
      // the "+1 change" pill opens the change details, joined to it as the printer details are
      var cb = el('button', 'chip adv chg-chip', '+' + n + ' change' + (n > 1 ? 's' : '')); cb.type = 'button'; cb.id = 'chg-chip';
      cb.setAttribute('aria-expanded', $('#chg-pop').hidden ? 'false' : 'true'); cb.setAttribute('aria-controls', 'chg-pop');
      cb.classList.toggle('open', !$('#chg-pop').hidden);
      cb.title = 'The settings changed from ' + profileObj().name;
      cb.addEventListener('click', toggleChangesPop);
      line2.appendChild(cb);
      if (!$('#chg-pop').hidden) renderChangesPop();
    } else closeChangesPop();
  }
  // One line per change, in the changes box's wording: "Quality › Resolution: 0.014 mm (profile 0.012 mm)".
  // A setting that has a quick change is named in the quick change's words ("Support ›
  // Supports: On (tree, auto)"), so the menu and the changes box say the same thing.
  function changeLine(k) {
    var s = ST.byKey[k], q = s.quick ? ST.QUICK[s.quick] : null;
    function val(v) { return q ? q.text(v) : ST.formatValue(s, v); }
    return s.group + ' › ' + (q ? q.label : s.label) + ': ' + val(S.changes[k]) + ' (profile ' + val(profileObj().values[k]) + ')';
  }
  // The change details: plain text, no links, joined to the chip like a tab opened from it.
  function renderChangesPop() {
    var pop = $('#chg-pop'), chipEl = $('#chg-chip'); if (!chipEl) { closeChangesPop(); return; }
    pop.innerHTML = '';
    var ul = el('ul'); Object.keys(S.changes).forEach(function (k) { ul.appendChild(el('li', null, changeLine(k))); });
    pop.appendChild(ul);
    // under the chip, its left edge on the chip's; kept inside the panel when the chip sits far right
    var wrap = pop.parentNode, wr = wrap.getBoundingClientRect(), cr = chipEl.getBoundingClientRect();
    pop.style.top = (cr.bottom - wr.top - 1) + 'px';
    var left = cr.left - wr.left, w = Math.min(wr.width, 380);
    pop.style.width = w + 'px';
    if (left + w > wr.width) { pop.style.left = Math.max(0, wr.width - w) + 'px'; pop.classList.add('shifted'); }
    else { pop.style.left = left + 'px'; pop.classList.remove('shifted'); }
  }
  function toggleChangesPop(e) {
    e.stopPropagation();
    var pop = $('#chg-pop'), open = pop.hidden;
    closePrinterPop();
    pop.hidden = !open;
    var c = $('#chg-chip'); if (c) { c.setAttribute('aria-expanded', open ? 'true' : 'false'); c.classList.toggle('open', open); }
    if (open) renderChangesPop();
  }
  function closeChangesPop() {
    var pop = $('#chg-pop'); if (pop) pop.hidden = true;
    var c = $('#chg-chip'); if (c) { c.setAttribute('aria-expanded', 'false'); c.classList.remove('open'); }
  }

  /* ================================================================== Settings step */
  function renderConfig() {
    var box = $('#config-info');
    box.innerHTML = '';
    var p = el('p', 'config-status');
    p.appendChild(document.createTextNode('Config: '));
    var a = el('a', null, '6238 (Popcorn Penguins)'); a.href = '#'; a.title = 'Open the configuration';
    a.addEventListener('click', function (e) { e.preventDefault(); });
    p.appendChild(a);
    var r = el('a', 'config-refresh', '↻'); r.href = '#'; r.title = S.ctx === 'standalone' ? 'Reload the configuration' : 'Reload the configuration from Onshape';
    r.addEventListener('click', function (e) { e.preventDefault(); });
    p.appendChild(r);
    box.appendChild(p);
    // version 7: no "Loaded from your saved configuration link." (the name says enough)
  }

  function fillSelect(sel, options, value) {
    sel.innerHTML = '';
    options.forEach(function (o) { var op = el('option', null, o.text); op.value = o.value; if (o.title) op.title = o.title; sel.appendChild(op); });
    sel.value = value;
  }

  // The Settings step: filament, the profiles of that filament, four quick changes, and either
  // the Advanced mode button or, once a setting is changed, the changes box in its place.
  function renderSetup() {
    renderConfig();
    fillSelect($('#p-filament'), ST.FILAMENTS.map(function (f) { return { value: f.id, text: f.name }; }), S.filament);
    fillSelect($('#p-profile'), ST.profilesOf(S.filament).map(function (p) { return { value: p.id, text: p.name, title: 'For ' + p.about }; }), S.profile);
    // Changing the filament (which changes the profile) or the profile clears every change.
    // A caution says so under the Profile menu from the first change until they are cleared.
    var nc = changeCount(), clr = $('#p-profile-clears');
    clr.hidden = !nc; clr.innerHTML = '';
    if (nc) {
      clr.appendChild(el('span', 'caution-icon', '⚠')); clr.lastChild.setAttribute('aria-hidden', 'true');
      clr.appendChild(document.createTextNode('Changing the filament or the profile clears your ' + (nc === 1 ? 'change' : nc + ' changes') + '.'));
    }
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
    // The changes box (yellow) takes the Advanced mode button's place once a setting is
    // changed: its one button is Advanced mode, and each line opens advanced mode at that setting.
    var n = changeCount(), box = $('#adv-effect');
    box.hidden = !n; box.innerHTML = ''; $('#adv-entry').hidden = !!n;
    if (n) {
      box.appendChild(el('strong', null, n + ' setting' + (n > 1 ? 's' : '') + ' changed from ' + profileObj().name));
      var ul = el('ul');
      Object.keys(S.changes).forEach(function (k) {
        var li = el('li'), a = el('button', 'linkish', changeLine(k)); a.type = 'button'; a.id = 'chg-line-' + k;
        a.title = 'Open advanced mode at ' + ST.byKey[k].label;
        a.addEventListener('click', function () { openAdvanced(k); });
        li.appendChild(a); ul.appendChild(li);
      });
      box.appendChild(ul);
      var ab = btn('Advanced mode', function () { openAdvanced(); }); ab.id = 'adv-effect-btn';
      box.appendChild(ab);
    }
  }

  function bindSetup() {
    // A filament has its own profiles: changing it picks that filament's first profile, and
    // so, like changing the profile, clears every change.
    $('#p-filament').addEventListener('change', function () {
      S.filament = this.value; S.profile = ST.profilesOf(S.filament)[0].id; S.changes = {};
      renderSetup(); updateSummary();
    });
    $('#p-profile').addEventListener('change', function () {
      S.profile = this.value; S.changes = {};
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
    $('#btn-advanced').addEventListener('click', function () { openAdvanced(); });
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
  // openAdvanced(key): with a setting's key (a line of the changes box), advanced mode opens
  // at that setting: its section and group open, the setting scrolled into sight and flashed.
  // What opened advanced mode (a line of the changes box, by its setting's key, or the button),
  // so that closing it puts focus back there. While it is open, what it covers is inert.
  var advOpener = null;
  function setCoveredInert(on) { ['#wiz-header', '#wiz-body', '#wiz-nav'].forEach(function (s) { $(s).inert = on; }); }
  function openAdvanced(key) {
    advOpener = key || 'button';
    setCoveredInert(true);
    placePrinterIcon(true); $('#advanced').hidden = false;
    if (key) { var s = ST.byKey[key]; S.advTab = s.group; S.advSecOpen[s.group] = true; S.advOpen[s.group + '|' + s.sub] = true; S.advFocus = key; }
    fitAdvanced(); renderAdvanced();
    if (key) {
      var row = $('#adv-row-' + key);
      if (row) { row.scrollIntoView({ block: 'center' }); row.classList.add('flash'); var inp = $('#adv-' + key); if (inp) inp.focus({ preventScroll: true }); }
      S.advFocus = null;
    } else ($('#adv-body button') || $('#adv-done')).focus();     // the first section's heading or name
  }
  function closeAdvanced() {
    $('#advanced').hidden = true; setCoveredInert(false); placePrinterIcon(false); advResetArmed = false; renderSetup(); updateSummary();
    // back to the line that opened it if it is still there, else to whichever Advanced mode button shows
    var to = (advOpener && advOpener !== 'button' && document.getElementById('chg-line-' + advOpener)) ||
             (!$('#adv-entry').hidden ? $('#btn-advanced') : document.getElementById('adv-effect-btn'));
    advOpener = null;
    if (to) to.focus();
  }
  // Advanced mode follows the panel's width (a ResizeObserver, not a media query, so it also
  // follows a panel the user drags wider): an accordion of the five sections below 480 px, a
  // rail of section names down the left from 480 px. The groups are always one column.
  function fitAdvanced() {
    var a = $('#advanced'), w = a.clientWidth;
    if (!w) return;
    var wide = w >= 480;
    if (a.classList.contains('wide') !== wide) { a.classList.toggle('wide', wide); if (!a.hidden) renderAdvanced(); }
  }
  var CHEVRON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8.59 16.59 13.17 12 8.59 7.41 10 6l6 6-6 6z"/></svg>';
  var UNFOLD_MORE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 5.83 15.17 9l1.41-1.41L12 3 7.41 7.59 8.83 9zm0 12.34L8.83 15l-1.41 1.41L12 21l4.59-4.59L15.17 15z"/></svg>';
  var UNFOLD_LESS = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7.41 18.59 8.83 20 12 16.83 15.17 20l1.41-1.41L12 14zm9.18-13.18L15.17 4 12 7.17 8.83 4 7.41 5.41 12 10z"/></svg>';
  function chevron(open) { var c = el('span', 'chev' + (open ? ' open' : '')); c.innerHTML = CHEVRON; return c; }
  // the groups of one section, in Orca's order
  function sectionGroups(section) {
    var groups = [], cur = null;
    ST.SETTINGS.forEach(function (s) {
      if (s.group !== section) return;
      if (!cur || cur.sub !== s.sub) { cur = { group: s.group, sub: s.sub, rows: [] }; groups.push(cur); }
      cur.rows.push(s);
    });
    return groups;
  }
  function changedIn(rows) { return rows.filter(function (s) { return S.changes.hasOwnProperty(s.key); }).length; }
  function changedInSection(section) { return Object.keys(S.changes).filter(function (k) { return ST.byKey[k].group === section; }).length; }
  // Version 8 (the owner): every section and every group starts open, and advanced mode
  // remembers each one's open or closed state for as long as the page is open (in memory, not
  // in the browser's storage): across steps, closing and reopening advanced mode, and the
  // accordion and the rail as the panel crosses 480 px. A reload forgets it.
  function groupOpen(g) { var k = g.group + '|' + g.sub; return S.advOpen.hasOwnProperty(k) ? S.advOpen[k] : true; }
  function sectionOpen(section) { return S.advSecOpen.hasOwnProperty(section) ? S.advSecOpen[section] : true; }
  // Expand all / Collapse all: one icon button for a section's groups.
  function expandButton(section) {
    var groups = sectionGroups(section), allOpen = groups.every(groupOpen);
    var b = el('button', 'icon-btn adv-expand'); b.type = 'button'; b.id = 'adv-expand-' + idPart(section);
    b.innerHTML = allOpen ? UNFOLD_LESS : UNFOLD_MORE;
    b.title = allOpen ? 'Collapse all' : 'Expand all'; b.setAttribute('aria-label', b.title + ' in ' + section);
    b.addEventListener('click', function (e) { e.stopPropagation(); groups.forEach(function (g) { S.advOpen[g.group + '|' + g.sub] = !allOpen; }); renderAdvanced(); });
    return b;
  }
  function countText(n) { return n ? n + ' changed' : ''; }
  function renderGroups(section, into) {
    var pv = profileObj().values, v = eff();
    sectionGroups(section).forEach(function (g) {
      var key = g.group + '|' + g.sub, open = groupOpen(g), ch = changedIn(g.rows);
      var box = el('div', 'adv-grp' + (open ? ' open' : ''));
      var head = el('button', 'adv-sub' + (ch ? ' has-changes' : '')); head.type = 'button'; head.id = 'adv-grp-' + idPart(key); head.setAttribute('aria-expanded', open ? 'true' : 'false');
      head.appendChild(chevron(open));
      // the group's name, and its changed count only when a setting in it is changed: "Precision · 1 changed"
      head.appendChild(el('span', 'nm', g.sub));
      if (ch) head.appendChild(el('span', 'ct', '· ' + countText(ch)));
      head.addEventListener('click', function () { S.advOpen[key] = !open; renderAdvanced(); });
      box.appendChild(head);
      if (open) { var rows = el('div', 'adv-rows'); g.rows.forEach(function (s) { rows.appendChild(advRow(s, v[s.key], pv[s.key])); }); box.appendChild(rows); }
      into.appendChild(box);
    });
  }
  // Every action in advanced mode redraws it; focus goes back to the control with the same id
  // (a Reset link that is gone hands it to its setting's control), so the keyboard keeps its place.
  function renderAdvanced() {
    var n = changeCount(), body = $('#adv-body'), keep = body.querySelector('.adv-list');
    var scroll = keep ? keep.scrollTop : 0;
    var act = document.activeElement, fid = act && $('#advanced').contains(act) ? act.id : null;
    $('#adv-sub').textContent = profileObj().name + (n ? ', ' + n + ' changed' : ', no changes');
    var ra = $('#adv-reset-all'); ra.disabled = !n; ra.textContent = advResetArmed ? 'Reset all ' + n + '?' : 'Reset all';
    ra.classList.toggle('primary', advResetArmed);
    body.innerHTML = '';
    renderAdvancedBody(body, scroll);
    if (fid) {
      var f = document.getElementById(fid) || (fid.indexOf('adv-reset-') === 0 ? document.getElementById('adv-' + fid.slice(10)) : null);
      if (f && f.disabled) f = $('#adv-done');
      if (f && f !== document.activeElement) f.focus({ preventScroll: true });
    }
  }
  function idPart(t) { return t.replace(/[^A-Za-z0-9]+/g, '-'); }
  function renderAdvancedBody(body, scroll) {
    var wide = $('#advanced').classList.contains('wide');
    if (wide) {
      // the rail of section names down the left; the open section's groups beside it, in one
      // column whose width is capped so each value stays near its name
      var rail = el('div', 'adv-rail'); rail.setAttribute('role', 'tablist'); rail.setAttribute('aria-orientation', 'vertical');
      if (!S.advTab) S.advTab = ST.GROUPS[0];
      ST.GROUPS.forEach(function (g) {
        var b = el('button', g === S.advTab ? 'on' : '', g); b.type = 'button'; b.id = 'adv-tab-' + idPart(g); b.setAttribute('role', 'tab'); b.setAttribute('aria-selected', g === S.advTab ? 'true' : 'false');
        var cnt = changedInSection(g); if (cnt) b.appendChild(el('span', 'n', String(cnt)));
        b.addEventListener('click', function () { S.advTab = g; renderAdvanced(); var l = $('#adv-body .adv-list'); if (l) l.scrollTop = 0; });
        rail.appendChild(b);
      });
      body.appendChild(rail);
      var list = el('div', 'adv-list'), col = el('div', 'adv-col');
      var top = el('div', 'adv-col-top'); top.appendChild(el('span', 'adv-col-name', S.advTab)); top.appendChild(expandButton(S.advTab));
      col.appendChild(top);
      renderGroups(S.advTab, col);
      list.appendChild(col); body.appendChild(list);
      list.scrollTop = scroll;
    } else {
      // the accordion: each section a card with a bold heading, a chevron and its changed count;
      // version 8: each opens and closes by itself, and all start open
      var acc = el('div', 'adv-list adv-accordion');
      ST.GROUPS.forEach(function (g) {
        var open = sectionOpen(g), cnt = changedInSection(g);
        var sec = el('div', 'adv-sec' + (open ? ' open' : ''));
        var hrow = el('div', 'adv-sec-head');
        var h = el('button', 'adv-sec-btn'); h.type = 'button'; h.id = 'adv-sec-' + idPart(g); h.setAttribute('aria-expanded', open ? 'true' : 'false');
        h.appendChild(chevron(open)); h.appendChild(el('span', 'nm', g));
        if (cnt) h.appendChild(el('span', 'ct', '· ' + countText(cnt)));
        // fix round 1 of version 8: only opening a section makes it the rail's section; a closing is not a choosing
        h.addEventListener('click', function () { S.advSecOpen[g] = !open; if (!open) S.advTab = g; renderAdvanced(); });
        hrow.appendChild(h);
        if (open) hrow.appendChild(expandButton(g));
        sec.appendChild(hrow);
        if (open) { var inner = el('div', 'adv-sec-body'); renderGroups(g, inner); sec.appendChild(inner); }
        acc.appendChild(sec);
      });
      body.appendChild(acc);
      acc.scrollTop = scroll;
    }
  }
  function advRow(s, value, profVal) {
    var changed = S.changes.hasOwnProperty(s.key);
    var row = el('div', 'adv-row' + (changed ? ' changed' : '')); row.id = 'adv-row-' + s.key;
    var id = 'adv-' + s.key;
    var lab = el('label'); lab.htmlFor = id;
    lab.textContent = s.label;
    if (s.quick) lab.title = 'Also on the Settings step as ' + ST.QUICK[s.quick].label;
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
        // redrawn after the focus has moved, so a Tab out of the box lands where it was going
        setSetting(s.key, x); setTimeout(renderAdvanced, 0);
      });
    } else if (s.type === 'sel') {
      input = el('select');
      s.options.forEach(function (o) { var op = el('option', null, o.text); op.value = o.value; input.appendChild(op); });
      input.value = value;
      input.addEventListener('change', function () { setSetting(s.key, input.value); renderAdvanced(); });
      ctl.appendChild(input); ctl.appendChild(el('span', 'unit'));      // an empty unit slot keeps every control's right edge in line
    } else {
      input = el('input'); input.type = 'checkbox'; input.checked = !!value;
      input.addEventListener('change', function () { setSetting(s.key, input.checked); renderAdvanced(); });
      ctl.appendChild(input); ctl.appendChild(el('span', 'unit'));
    }
    input.id = id;
    row.appendChild(lab); row.appendChild(ctl);
    // a changed setting: "Profile 0.012 mm", then a Reset link that puts the profile's value back
    if (changed) {
      var was = el('div', 'was'); was.appendChild(document.createTextNode('Profile ' + ST.formatValue(s, profVal) + ' '));
      var reset = el('button', 'linkish reset', 'Reset'); reset.type = 'button'; reset.id = 'adv-reset-' + s.key;
      reset.setAttribute('aria-label', 'Reset ' + s.label + ' to the profile’s ' + ST.formatValue(s, profVal));
      reset.addEventListener('click', function () { delete S.changes[s.key]; renderAdvanced(); });
      was.appendChild(reset); row.appendChild(was);
    }
    return row;
  }
  function bindAdvanced() {
    $('#adv-done').addEventListener('click', closeAdvanced);
    $('#adv-reset-all').addEventListener('click', function () {
      if (!advResetArmed) { advResetArmed = true; renderAdvanced(); return; }
      advResetArmed = false; S.changes = {}; renderAdvanced();
    });
    // version 7: Escape no longer closes advanced mode; "Back to Settings" at the bottom is the only way back
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
    if (existing) {
      // a click on a part already listed raises its quantity by one, and its row flashes;
      // the prompt above the list does not change (the owner, version 6)
      existing.qty = Math.min(MAX_INSTANCES, existing.qty + 1);
      partsNote = null;
      renderParts(); flashRow(existing); updateSummary();
      return existing;
    }
    // units: a part picked in Onshape has its Part Studio's or Assembly's units; an uploaded
    // file is read in the configuration's units for uploads (inches unless it says millimetres)
    var part = { id: 'p' + (S.nextId++), key: key, name: o.fileName ? o.fileName.replace(/\.(stl|3mf)$/i, '') : def.name,
                 file: o.fileName || null, qty: 1, status: 'exporting', warn: null, error: null, progress: 0, slow: false,
                 units: o.units || (o.fileName ? Config.uploadUnits : 'mm') };
    S.parts.push(part);
    renderParts();
    exportPart(part, o);
    return part;
  }
  // Bringing a part in. Three ways it can go:
  //  - it arrives (a second or so, with progress on its row);
  //  - Onshape cannot export it (a broken part): a notification, and the part is not added;
  //  - our server cannot be reached: retried quietly; "taking longer than usual" after a few
  //    seconds; a notification only when every retry has failed. The list never holds a
  //    broken entry, and nothing here holds Next.
  function exportPart(part, o) {
    part.status = 'exporting'; part.error = null; part.progress = 0; part.slow = false;
    var fail = Mock.take('export_fail');
    var net = !fail ? (Mock.take('server_down') ? 'down' : Mock.take('server_slow') ? 'slow' : null) : null;
    var warn = !fail && !net && Mock.take('not_watertight');
    var need = net === 'slow' ? 9 : net === 'down' ? RETRY_GIVE_UP_S : 0.7 + Math.random() * 0.8;
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
        fine + 'The file may be cut short or saved in another format under that name. Export it again from your CAD program as STL or 3MF, then upload the new file.', key);
    } else if (why === 'export') {
      notify('error', 'Onshape could not export ' + part.name + ', so it was not added.',
        fine + 'The part itself is probably broken in Onshape. Check in Onshape that ' + part.name +
        ' is one closed solid (not a surface, and not several bodies) and that its Part Studio rebuilds with no errors (no red features in the feature list). Then click it again.', key);
    } else {
      notify('error', 'Could not bring in ' + part.name + ': PenguinSlicer’s server did not answer for ' + RETRY_GIVE_UP_S + ' seconds, so it was not added.',
        fine + (S.ctx === 'standalone' ? 'Upload ' + part.file + ' again to try once more.' : 'Click ' + part.name + ' in Onshape again to try once more.'), key);
    }
  }
  function arrived(part, warn) {
    part.status = 'ready'; part.progress = 1; part.slow = false;
    if (warn) part.warn = { what: part.name + ' is not watertight: its mesh has 14 open edges in 2 places.', todo: 'It may still slice and print. If the slice fails, look in ' + (S.ctx === 'standalone' ? 'your CAD program' : 'Onshape') + ' for faces that do not meet, then ' + (S.ctx === 'standalone' ? 'remove this row and upload the repaired file.' : 'remove this row and click the repaired part again.') };
    renderParts();
    // It may arrive after the user moved on. On the Layout step it joins the plate at once;
    // later than that, it joins the plate the next time the Layout step is shown.
    if (S.step === 'layout') {
      enterLayoutData(); layHint = msg('ok', part.name + ' arrived and joined the plate.', null);
      editor.sync(); scheduleLayoutRender();
    } else if (ORDER.indexOf(S.step) > 2) {
      notify('info', part.name + ' arrived after you left the Parts step.', 'It joins the plate when you go back to the Layout step.', 'late-' + part.id);
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
    // the prompt says one thing and does not change as parts arrive; only the list updates
    $('#select-status').textContent = ctx === 'assembly' ? 'Click a part in the assembly' : 'Click a part in the Part Studio';
    // STL files carry no units (a 3MF file states its own): what an STL is read in is a
    // consequence the user cannot see
    $('#upload-units').textContent = 'STL files are read in ' + (Config.uploadUnits === 'in' ? 'inches.' : 'millimetres.');
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
      } else {
        // the size in the part's own units, as Onshape (or the configuration, for a file) gives them
        dims.textContent = U.size(def.size, p.units);
        dims.title = 'Size as modelled, in ' + (p.units === 'in' ? 'inches' : 'millimetres') +
          (p.file ? (/\.3mf$/i.test(p.file) ? ' (the units the file states)' : ' (STL files are read in ' + (p.units === 'in' ? 'inches' : 'millimetres') + ')') : ' (the units of its ' + (ctx === 'assembly' ? 'assembly' : 'Part Studio') + ')');
        meta.appendChild(dims);
      }
      row.appendChild(meta);
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
    box.textContent = parts + ' part' + (parts === 1 ? '' : 's') + ', ' + n + ' instance' + (n === 1 ? '' : 's') + ' on one plate' +
      (coming ? '; ' + coming + ' more arriving.' : '.');
    if (n > MAX_INSTANCES) box.appendChild(msg('error', 'This plate would hold ' + n + ' instances.', TOO_MANY_INSTANCES_MESSAGE));
  }

  // Onshape selection from the page (Part Studio or Assembly)
  // units: the units of the Part Studio or Assembly the part was picked in
  function onOnshapeSelect(key, units) {
    if (S.step !== 'parts' || S.ctx === 'standalone') return false;
    addPart(key, { units: units });
    return true;
  }

  function bindParts() {
    var dz = $('#dropzone'), input = $('#f-upload'), next = 0;
    var keys = P.LIB.map(function (d) { return d.key; }).filter(function (k) { return k !== 'shaft'; });
    function addFiles(files) {
      Array.prototype.slice.call(files).forEach(function (f) {
        var key = keys[next++ % keys.length];
        addPart(key, { fileName: f.name || (P.byKey[key].name.replace(/\s+/g, '_') + '.stl') });
      });
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
    // An instance too long for the plate as it is turned has its own card, with "Turn it to
    // fit" (fix round 1 of version 8); this message counts only the others.
    var long = S.instances.filter(function (c) { var t = isParked(c) && PL.tooLong(c, PLATE); return t && t.turn; }).length;
    res = { parked: res.parked - long, placed: res.placed };
    if (offer && offer.parked >= res.parked) offer = null;
    if (res.parked <= 0) return [];
    // Arrange keeps how each instance lies. `offer`, when given, is a plate Arrange also tried
    // with every instance laid its best way, and which left fewer instances over: one button takes it.
    var acts = [['Back to Parts', function () { gotoStep('parts'); }]];
    if (offer) acts.unshift(['Lay them the best way: ' + (offer.parked ? (res.parked - offer.parked) + ' more fit' : 'all fit'), function () {
      // done afresh on the plate as it is now, in case it changed since Arrange was pressed
      pushUndo();
      var n = 0;
      S.instances.forEach(function (c) { var best = P.resting(c.partKey).list[0]; if (best && P.restIndex(c.partKey, c.q) !== 0 && turnToRest(c, best)) { c.auto = true; n++; PL.fitTurn(c, PLATE); } });
      var now = PL.bestArrange(S.instances, PLATE);
      S.layoutNotes = arrangeNote(now);
      layHint = msg('ok', 'Laid ' + plural(n, 'instance', 'instances') + ' the best way and arranged again: ' + (now.parked ? plural(now.placed, 'instance fits', 'instances fit') + ' now.' : 'every instance now fits.'), null);
      recheck(); editor.resetHandle(); editor.sync(); editor.resetView(); scheduleLayoutRender();
    }]);
    return [msg('error', 'Arrange placed ' + res.placed + ' of ' + (res.placed + res.parked) + ' instances; ' + plural(res.parked, 'instance does', 'instances do') + ' not fit and ' + (res.parked === 1 ? 'waits' : 'wait') + ' beside the plate.',
      offer ? 'Arrange keeps how each instance lies. With ' + plural(offer.changed, 'instance', 'instances') + ' laid the best way, ' + (offer.parked ? 'more would fit' : 'everything would fit') + '. Or lower the quantities and print the rest on a second plate.'
            : 'Lower the quantities and print the rest on a second plate, or turn or lay instances another way to make room.', acts)];
  }
  // Arrange keeps how each instance lies. When that leaves instances over and some do not lie
  // their best way, it also tries the plate with every instance laid its best way; only when
  // that leaves fewer over is it offered. Returns { snap, parked, changed } or null, and
  // leaves the plate as Arrange made it.
  function tryBestWay(res) {
    var notBest = S.instances.filter(function (c) { return P.resting(c.partKey).list[0] && P.restIndex(c.partKey, c.q) !== 0; });
    if (!res.parked || !notBest.length) return null;
    var keep = S.instances.map(function (c) { return { c: c, x: c.x, y: c.y, q: c.q.clone(), auto: c.auto }; });
    notBest.forEach(function (c) { if (turnToRest(c, P.resting(c.partKey).list[0])) { c.auto = true; PL.fitTurn(c, PLATE); } });
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
    // Version 7 (the owner: no text about orientation): nothing is said when a part arrives laid
    // down automatically; the view shows it, and its selection's "Put back as modelled" undoes it.
    if (!S.laidOut || fresh.length === S.instances.length) {
      // version 8: an instance that arrives too long for the plate is turned by the wizard to
      // fit, once, on arrival; the Arrange below keeps every orientation as it is
      fresh.forEach(function (c) { PL.fitTurn(c, PLATE); });
      var res = PL.bestArrange(S.instances, PLATE); S.laidOut = true;
      S.layoutNotes = arrangeNote(res);
    } else {
      // instances added to a plate the user already laid out join the group: each takes the
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
  // After instances were laid another way: find each a free spot if it needs one. Version 7
  // (the owner: no text about orientation): nothing is said of how it lies now, which the view
  // shows; only a move the wizard made, or an instance left beside the plate, is said.
  function afterLay(instances) {
    var how = instances.map(function (c) { recheck(); return settle(c); });
    var c0 = instances[0];
    var parked = how.filter(function (h) { return h === 'parked'; }).length, moved = how.filter(Boolean).length - parked;
    layHint = parked
      ? msg('warn', instances.length === 1 ? instanceLabel(c0) + ' no longer fits on the plate and waits beside it.' : parked + ' instances no longer fit on the plate and wait beside it.',
            'No spot on the plate is free for ' + (parked === 1 ? 'it' : 'them') + ' lying this way. The other instances stay where you put them; press Arrange to make room.')
      : moved ? msg('ok', instances.length === 1 ? instanceLabel(c0) + ' no longer fitted where it stood, so it was moved' + (how[0] === 'turned' ? ' and turned' : '') + ' to the nearest free spot.'
                                               : moved + ' instances no longer fitted where they stood and moved to the nearest free spots.', null)
      : null;
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
    if (!changed.length) { layHint = null; scheduleLayoutRender(); return; }       // version 7: no "already lies that way"
    pushUndo(snap);
    afterLay(changed);
  }
  // Auto-orient: the selection, or every instance when nothing is selected. When every instance
  // changes at once, the plate is arranged again after (as Orca's Q then A).
  function autoOrient(ids) {
    var list = (ids && ids.length ? ids : S.instances.map(function (c) { return c.id; })).map(instanceById).filter(Boolean);
    var whole = !(ids && ids.length);
    if (!whole) return layInstances(list, function (c) { return P.resting(c.partKey).list[0]; }, 'auto');
    var snap = snapshot(), changed = 0;
    // version 8: the wizard turns an instance it laid that is now too long for the plate (Arrange will not)
    list.forEach(function (c) { var best = P.resting(c.partKey).list[0]; if (best && turnToRest(c, best)) { changed++; PL.fitTurn(c, PLATE); } if (best) c.auto = true; });
    if (!changed) { layHint = null; scheduleLayoutRender(); return; }
    pushUndo(snap); recheck();
    var res = null;
    if (S.problems.some(function (p) { return p.rule !== 'too_tall'; })) { res = PL.bestArrange(S.instances, PLATE); S.layoutNotes = arrangeNote(res); needRefit = true; }
    // version 7: nothing about how they lie now; only that the plate was arranged again, which moved everything
    layHint = res ? msg('ok', 'Arranged the plate again to make room.', null) : null;
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
    if (!changed.length) { layHint = null; scheduleLayoutRender(); return; }
    pushUndo(snap);
    afterLay(changed);
  }
  // One error for every instance that is too close: one pair is named; more say how many,
  // with one Arrange button. Every instance in it stays marked in the view.
  // The spacing follows the Settings step's supports setting (12 mm on, 5 mm off). Turning
  // supports on after arranging moves nothing: instances now too close are reported here until
  // the user presses Arrange or drags them.
  function recheck() {
    syncPlateRules();
    var raw = PL.check(S.instances, PLATE, instanceLabel), close = raw.filter(function (p) { return p.rule === 'too_close'; });
    var rest = raw.filter(function (p) { return p.rule !== 'too_close'; });
    if (close.length > 1) {
      var ids = [];
      close.forEach(function (p) { p.instances.forEach(function (id) { if (ids.indexOf(id) < 0) ids.push(id); }); });
      close = [{ rule: 'too_close', instances: ids,
                 message: ids.length + ' instances are closer than ' + U.len(PLATE.spacing, 0, 'mm') + ' with supports ' + (PLATE.supportsOn ? 'on' : 'off') + '. Press Arrange, or drag them apart.' }];
    }
    S.problems = rest.concat(close);
  }
  function isBad(id) { return S.problems.some(function (p) { return p.instances.indexOf(id) >= 0; }); }
  // an instance waiting beside the plate (to its right), where Arrange or a lay-down left it
  function isParked(c) { return !!c && PL.bbox(PL.worldHull(c)).minX > PLATE.x; }
  // An instance that was just laid down has a new footprint. If it now overlaps a neighbour or
  // crosses the plate edge, find it a free spot, turning it if that is what it takes.
  // It takes the free spot nearest to where it stood, so it stays beside its neighbours.
  // When no spot is free with the others where they are (a long part laid flat among small
  // ones), the whole plate is arranged again, which is what the user would press next.
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
    // This one waits beside the plate, marked off the plate, until the user presses Arrange.
    // Fix round 1 of version 8: it waits turned as the wizard turns an instance too long for
    // the plate (fitTurn), so that Arrange, which never turns, can then place it.
    instance.q = keep.q; instance.d = null;
    PL.fitTurn(instance, PLATE);
    var d = PL.derive(instance), sideY = 0;
    S.instances.forEach(function (o) { if (o === instance) return; var h = PL.bbox(PL.worldHull(o)); if (h.minX > PLATE.x) sideY = Math.max(sideY, h.maxY + PLATE.spacing); });
    instance.x = PLATE.x + PLATE.spacing * 4 + d.w / 2; instance.y = sideY + d.l / 2;
    recheck();
    return 'parked';
  }

  function enterLayout() {
    enterLayoutData();
    // version 7 (the owner): every figure of the printer and the plate in millimetres, whatever
    // the parts' units: "Shop H2S: plate 340 × 320 mm, up to 340 mm tall, 12 mm apart"
    $('#layout-info').textContent = (PRN.paired ? ST.PRINTER.name : 'The ' + ST.PRINTER.model) + ': plate ' + PLATE.x + ' × ' + PLATE.y + ' mm, up to ' +
      U.len(PLATE.height, 0, 'mm') + ' tall, ' + U.len(PLATE.spacing, 0, 'mm') + ' apart';
    if (!editor) {
      editor = Layout3D.create($('#layout-view'), {
        plate: PLATE,
        getInstances: function () { return S.instances; },
        isSelected: function (id) { return S.selected.indexOf(id) >= 0; },
        isBad: isBad,
        labelFor: function (id) { var c = instanceById(id); return c ? instanceLabel(c) : ''; },
        unitsOf: function (id) { return unitsOf(instanceById(id)); },
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
    var beside = S.instances.filter(isParked).length, onPlate = S.instances.length - beside;
    if (!sel.length) s.textContent = plural(onPlate, 'instance', 'instances') + ' on the plate' + (beside ? ', ' + beside + ' beside it.' : '.');
    else if (sel.length === 1) { var d = PL.derive(sel[0]); s.innerHTML = ''; s.appendChild(el('strong', null, instanceLabel(sel[0]))); var un = unitsOf(sel[0]); s.appendChild(document.createTextNode(' ' + U.area(d.w, d.l, un) + ', ' + U.len(d.height, 0, un) + ' tall')); }
    else { s.innerHTML = ''; s.appendChild(el('strong', null, sel.length + ' instances')); s.appendChild(document.createTextNode(' move and turn together')); }
    renderOrientLine(sel); renderStrip(sel); renderGestures();
    $('#btn-tilt').hidden = Opt.scheme !== 'T'; $('#btn-top').hidden = Opt.scheme === 'T';
    // The first problem is also said inside the picture, where the user is looking; the
    // full sentences and their remedy buttons are below it.
    var alertBox = $('#layout-alert');
    alertBox.innerHTML = ''; alertBox.classList.toggle('ok', !S.problems.length); alertBox.disabled = !S.problems.length;
    // An instance Arrange left beside the plate gets no card of its own: Arrange's message
    // below already says how many do not fit, with what to do.
    // One too long for the plate as it is turned keeps its card: Arrange cannot help it.
    var shown = S.problems.filter(function (p) { return !(p.rule === 'off_plate' && !p.turnToFit && S.layoutNotes.length && isParked(instanceById(p.instances[0]))); });
    var lines = (beside && shown.length < S.problems.length ? 1 : 0) + shown.length;
    if (S.problems.length) {
      var first = shown.length ? shown[0].message.split('. ')[0] + '.' : plural(beside, 'instance does', 'instances do') + ' not fit on the plate.';
      alertBox.appendChild(el('span', 'first', first)); alertBox.title = first;
      alertBox.appendChild(el('span', 'more', lines > 1 ? '+' + (lines - 1) + ' more ↓' : 'Fix ↓'));
    } else {
      alertBox.title = '';
      alertBox.appendChild(el('span', 'first', S.instances.length ? '✓ ' + (S.instances.length === 1 ? instanceLabel(S.instances[0]) + ' fits' :'All ' + S.instances.length + ' instances fit') + ' the plate.' : 'No instances yet: add parts on the Parts step.'));
    }
    var box = $('#layout-errors'); box.innerHTML = '';
    if (layHint) box.appendChild(layHint);
    S.layoutNotes.forEach(function (n) { box.appendChild(n); });
    if (shown.length) {
      box.appendChild(el('div', 'hint fix-first', shown.length === 1 ? 'Fix this before Next:' : 'Fix these ' + shown.length + ' before Next:'));
      shown.forEach(function (p) {
        // an instance laid down with no room left waits beside the plate: Arrange makes room
        // and one too long for the plate as it is turned: the wizard turns it (Arrange never turns)
        var acts = p.rule === 'too_tall' ? [['Auto-orient', function (e) { e.stopPropagation(); S.selected = p.instances.slice(); autoOrient(p.instances); }]]
                 : p.turnToFit ? [['Turn it to fit', function (e) { e.stopPropagation(); turnToFit(p.instances); }]]
                 : [['Arrange', function (e) { e.stopPropagation(); doArrange(); }]];
        var m = msg('error', p.message.split('. ')[0] + '.', p.message.split('. ').slice(1).join('. '), acts);
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
    var modelled = sel.every(function (c) { return P.isModelled(c.q); });
    var best = P.resting(sel[0].partKey).list[0];
    function link(t, fn) { var b = el('button', 'linkish', t); b.type = 'button'; b.addEventListener('click', fn); box.appendChild(b); }
    // Version 7 (the owner: no text about orientation): the controls only, no sentence beside
    // them, and nothing at all when the instance lies as modelled and that is its best way.
    if (!modelled) {
      link('Put back as modelled', function () { layInstances(sel, function () { return P.resting(sel[0].partKey).modelled; }, 'modelled'); });
    } else if (best && !best.modelled) {
      link('Lay it the best way', function () { autoOrient(sel.map(function (c) { return c.id; })); });
    } else box.hidden = true;
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
    var R = P.resting(key), cur = P.restIndex(key, sel[0].q), un = unitsOf(sel[0]);     // heights in the part's units
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
      b.appendChild(el('span', 'rs-line', U.len(c.height, 0, un) + ' tall'));
      if (it.i === 'm') b.appendChild(el('span', 'rs-line', 'as modelled'));
      if (tall) b.appendChild(el('span', 'rs-line bad', 'too tall'));
      else if (c.supports) b.appendChild(el('span', 'rs-line warn', 'overhangs'));
      function sq(a) { return un === 'in' ? (a / 645.16).toFixed(2) + ' in²' : Math.round(a) + ' mm²'; }
      b.title = (it.i === 0 ? 'The best way, chosen automatically: ' : it.i === 'm' ? 'As modelled: ' : '') + U.len(c.height, 0, un) + ' tall, ' + sq(c.contact) + ' on the plate' + (c.overhang > 1 ? ', ' + sq(c.overhang) + ' over air' : '') + (c.supports ? '. Much of it hangs over air, so it will probably need Supports.' : '');
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      b.addEventListener('click', function () { layInstances(sel, function () { return c; }, it.i === 0 ? 'auto' : it.i === 'm' ? 'modelled' : 'pick'); });
      row.appendChild(b);
    });
    box.appendChild(row);
  }
  // One line under the view: the gestures of the mouse scheme and of the way to lay an instance
  // down, chosen in the scenario strip, so a user need not be told.
  var GESTURES = {
    O: 'Drag an instance to move it, its round handle to turn it. Right-drag to look around, Shift-drag to slide, scroll to zoom.',
    S: 'Drag an instance to move it, its round handle to turn it. Drag empty space to look around, right-drag to slide, scroll to zoom.',
    T: 'Seen from above. Drag an instance to move it, its round handle to turn it. Drag empty space to slide, scroll to zoom, right-drag or 3D to tilt.'
  };
  var LAY_GESTURE = {
    hull: 'Select an instance: its faces show as pale blue patches; click one to lay it on that face.',
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
  // The gestures and the other ways to move and look are behind the "?" icon of the toolbar
  // (version 6, fix round 1): nothing is written under the view.
  function toggleLayoutHelp(e) {
    e.stopPropagation();
    var pop = $('#layout-help'), open = pop.hidden;
    pop.hidden = !open; $('#btn-layout-help').setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function closeLayoutHelp() { var pop = $('#layout-help'); if (pop) pop.hidden = true; var b = $('#btn-layout-help'); if (b) b.setAttribute('aria-expanded', 'false'); }
  function renderGestures() {
    $('#layout-gestures').textContent = GESTURES[Opt.scheme] + ' ' + LAY_GESTURE[Opt.lay];
    var ul = $('#layout-more'); ul.innerHTML = '';
    MORE[Opt.scheme].concat([
      'Shift- or Ctrl-click adds an instance to the selection; drag one to move them all.',
      'Hold Shift while turning to turn in 45° steps.',
      'Double-click a flat face to lay the instance down on it.',
      'F zooms to the instances; Ctrl+1 looks from above; Ctrl+A selects every instance; Escape clears the selection.'
    ]).forEach(function (t) { ul.appendChild(el('li', null, t)); });
  }
  function doArrange() {
    pushUndo();
    var res = PL.bestArrange(S.instances, PLATE);
    S.layoutNotes = arrangeNote(res, tryBestWay(res));
    layHint = res.parked ? null : msg('ok', 'Arranged ' + plural(res.placed, 'instance', 'instances') + '.', null);
    recheck(); editor.resetHandle(); editor.sync(); editor.resetView(); scheduleLayoutRender();
  }
  // "Turn it to fit" (fix round 1 of version 8): the wizard turns an instance that is too long
  // for the plate as it is turned, as fitTurn does on arrival, and arranges the plate again.
  function turnToFit(ids) {
    pushUndo();
    var list = ids.map(instanceById).filter(Boolean);
    list.forEach(function (c) { PL.fitTurn(c, PLATE); });
    var res = PL.bestArrange(S.instances, PLATE);
    S.layoutNotes = arrangeNote(res, tryBestWay(res));
    layHint = res.parked ? null : msg('ok', 'Turned ' + (list.length === 1 ? instanceLabel(list[0]) : plural(list.length, 'instance', 'instances')) +
      ' and arranged ' + plural(res.placed, 'instance', 'instances') + '.', null);
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
    $('#btn-layout-help').addEventListener('click', toggleLayoutHelp);
    $('#layout-help').addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', closeLayoutHelp);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !$('#layout-help').hidden) { closeLayoutHelp(); $('#btn-layout-help').focus(); }
    });
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
    var c0 = S.instances[0], d0, note = null, refitAfterArm = false;
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
              // wanted: this pair too close but not touching, so the option shows "… mm apart",
              // never "overlap"; an overlap anywhere else weighs heavily against the spot
              var ps = PL.check(S.instances, PLATE, instanceLabel), wanted = ps.filter(function (p) {
                return p.rule === 'too_close' && p.gap > 0 && p.instances.indexOf(a.id) >= 0 && p.instances.indexOf(b.id) >= 0; }).length;
              if (!wanted) continue;
              var overlaps = ps.filter(function (p) { return p.rule === 'too_close' && p.gap === 0; }).length;
              var score = ps.length - wanted + 100 * overlaps;
              if (!pick || score < pick.score) pick = { score: score, a: a, b: b, sa: [a.x, a.y], sb: [b.x, b.y] };
              break;
            }
          });
          a.x = keepA[0]; a.y = keepA[1]; b.x = keepB[0]; b.y = keepB[1];
        });
      });
      if (pick) { pick.a.x = pick.sa[0]; pick.a.y = pick.sa[1]; pick.b.x = pick.sb[0]; pick.b.y = pick.sb[1]; }
      refitAfterArm = true;                 // the pair may have moved out of the picture
    }
    if (Mock.take('off_plate')) {
      var c = S.instances[S.instances.length - 1], d = PL.derive(c);
      var yy = Math.min(Math.max(c.y, d.l / 2 + 10), PLATE.y - d.l / 2 - 10), xx = Math.min(Math.max(c.x, d.w / 2 + 10), PLATE.x - d.w / 2 - 10);
      bestSpot(c, [[PLATE.x - d.w * 0.25, yy], [d.w * 0.25, yy], [xx, PLATE.y - d.l * 0.25], [xx, d.l * 0.25]], 'off_plate');
    }
    if (Mock.take('too_tall')) {
      var rib = S.instances.filter(function (x) { return x.partKey === 'rib'; })[0];
      if (!rib) {
        var part = { id: 'p' + (S.nextId++), key: 'rib', name: P.byKey.rib.name, qty: 1, status: 'ready', warn: null, error: null,
                     units: S.parts.length ? S.parts[0].units : 'in' };      // from the same Part Studio as the first part
        S.parts.push(part); rib = newInstance(part); rib.q = new T.Quaternion(); rib.auto = false; S.instances.push(rib);
        var ribOthers = S.instances.filter(function (x) { return x !== rib; }), ribMid = PL.centre(ribOthers, PLATE);
        if (!PL.placeNear(rib, ribOthers, PLATE, ribMid[0], ribMid[1])) PL.place(rib, ribOthers, PLATE);
      } else { rib.q = new T.Quaternion(); rib.d = null; rib.auto = false; }
      // version 7: no "Mockup: …" note in the panel; the scenario strip's option says what it does
      layHint = null;
    }
    recheck();
    if (editor) { editor.sync(); if (refitAfterArm) editor.resetView(); renderLayoutSide(); updateNext(); updateSummary(); }
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

  // Version 6 has no line under the Preview step's title: the slicing card, the result or the
  // error message says where the slice stands.
  function enterPreview() {
    if (S.result && S.resultSig === signature()) { showResult(); return; }
    if (S.job && S.job.state === 'running') {
      if (S.job.sig === signature()) { $('#slice-card').hidden = false; return; }   // still slicing this plate
      cancelSlice('changed');                                                          // the plate changed: slice it afresh
    }
    startSlice();
  }
  function clearPreview() {
    $('#preview-errors').innerHTML = ''; $('#preview-result').hidden = true; $('#slice-card').hidden = true; $('#preview-toast').hidden = true;
  }
  function startSlice() {
    clearPreview(); S.result = null; S.resultSig = null; updateNext();
    var v = eff(), vol = plateVolume(), instances = S.instances.slice();
    var forced = Mock.take('too_large');
    if (forced || vol > PLATE_VOLUME_CAP_CM3) {
      var cap = forced ? Math.max(10, Math.floor(vol * 0.75 / 10) * 10) : PLATE_VOLUME_CAP_CM3;
      $('#preview-errors').appendChild(msg('error',
        'This plate is too large for the server to slice: its ' + instances.length + ' instances hold about ' + Math.round(vol) + ' cm³ of plastic, and the server slices up to ' + cap + ' cm³ at once.',
        instances.length > 1 ? 'Lower the quantities and print the rest on a second plate.'
                          : 'This part alone is more than the server can slice, so it cannot be printed from here. Slice it in Orca Slicer on your own computer.',
        instances.length > 1 ? [['Back to Parts', function () { gotoStep('parts'); }, 'primary'], ['Back to Layout', function () { gotoStep('layout'); }]]
                          : [['Back to Parts', function () { gotoStep('parts'); }]]));
      // version 7: the lowered cap is said by the scenario strip's option, not in the panel
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
    var box = $('#preview-errors'); box.innerHTML = '';
    var sus = job.suspect, label = sus ? instanceLabel(sus) : 'An instance', h = sus ? PL.derive(sus).height : 40;
    var z1 = +(h * 0.62).toFixed(2), z2 = +(z1 + 0.72).toFixed(2), zr = U.len(z1, 1, 'mm');      // a height on the plate: millimetres
    var name = sus && partById(sus.partId) ? partById(sus.partId).name : 'the part';
    // The details: Orca Slicer's own sentence (in millimetres, as Orca writes it), which names
    // the heights; nothing of PenguinSlicer's.
    var orca = 'Orca Slicer says: “Object can’t be printed for empty layer between ' + z1 + ' and ' + z2 + ' mm. Make sure the object is printable or the object has faulty mesh.” ';
    if (type === 'empty') {
      box.appendChild(msg('error', 'The slice failed: ' + label + ' has empty layers at about ' + zr + ' above the plate.',
        'Part of it starts in mid-air there, and Supports is off, so nothing would hold it up while it prints. Turn Supports on and slice again.',
        [['Turn on Supports and slice again', supportsOnAndSlice, 'primary'], ['Back to Layout', function () { gotoStep('layout'); }]],
        orca + 'Look at ' + name + ' at that height as it lies on the plate: a piece that starts in mid-air (an overhang with nothing under it) needs Supports, or the part laid another way.'));
    } else if (type === 'faulty') {
      box.appendChild(msg('error', 'The slice failed: ' + label + ' has a faulty mesh at about ' + zr + ' above the plate.',
        'Supports is already on, so the model itself has gaps or zero-thickness pieces there. Repair ' + name + ' in ' + (S.ctx === 'standalone' ? 'your CAD program' : 'Onshape') + ' (look for faces that do not meet near ' + zr + '), then ' +
          (S.ctx === 'standalone' ? 'on the Parts step remove its row and upload the repaired file.' : 'on the Parts step remove its row and click the repaired part again.'),
        [['Back to Parts', function () { gotoStep('parts'); }, 'primary']],
        orca + (S.ctx === 'standalone'
          ? 'In your CAD program, check that ' + name + ' is one closed solid with no zero-thickness walls or faces that only touch along an edge near that height, and that the model rebuilds with no errors before you export it again.'
          : 'In Onshape, check that ' + name + ' is one closed solid with no zero-thickness walls or faces that only touch along an edge near that height, and that its Part Studio rebuilds with no errors.')));
    } else if (type === 'timeout') {
      box.appendChild(msg('error', 'The slice took longer than ' + (SLICE_TIMEOUT_S / 60) + ' minutes, the server’s limit, and was stopped.',
        job.instances.length > 1
          ? 'Slice again first: the server may have been busy. If it stops again, this plate of ' + job.instances.length + ' instances is too much at once: lower the quantities and print the rest on a second plate, or pick a profile with thicker layers.'
          : 'Slice again first: the server may have been busy. If it stops again, pick a profile with thicker layers, which slices faster.',
        job.instances.length > 1 ? [['Slice again', startSlice, 'primary'], ['Back to Parts', function () { gotoStep('parts'); }]]
                              : [['Slice again', startSlice, 'primary'], ['Back to Settings', function () { gotoStep('setup'); }]]));
    }
    updateNext();
  }
  // The empty-layers remedy. Supports on needs 12 mm between instances, so the placement
  // check runs first: a plate that passes is sliced; one that does not goes to the Layout
  // step, where its usual message and Arrange are. Nothing moves by itself.
  function supportsOnAndSlice() {
    setSetting('enable_support', true);
    recheck();
    if (S.problems.length) {
      layHint = msg('info', 'Not sliced: with Supports on, instances need ' + U.len(PLATE.spacing, 0, 'mm') + ' between them.', null);
      gotoStep('layout'); return;
    }
    startSlice(); updateSummary();
  }
  function cancelSlice(why) {
    var job = S.job; if (!job || job.state !== 'running') return;
    var at = clock(job.t), stage = stageAt(job, job.shown).name;
    stopJob(job); job.state = 'cancelled';
    $('#slice-card').hidden = true;
    if (why === 'changed') return;         // the plate changed while it sliced: a new slice starts at once
    var box = $('#preview-errors'); box.innerHTML = '';
    box.appendChild(msg('info', 'Slice cancelled at ' + at + ', during “' + stage + '”. Nothing was saved or sent to the printer.',
      null,
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
    // the two numbers a user plans around, large; the rest on one quiet line (layer height in mm: a slicer setting)
    [['Print time', hm(r.est.seconds)], ['Filament', Math.round(r.est.grams) + ' g ' + r.filament.type]].forEach(function (s) {
      var d = el('div', 'stat'); d.appendChild(el('strong', null, s[1])); d.appendChild(document.createTextNode(s[0])); stats.appendChild(d);
    });
    stats.appendChild(el('div', 'stat-line', r.instances.length + ' instance' + (r.instances.length === 1 ? '' : 's') + ' · ' + r.tp.layers + ' layers of ' + r.settings.layer_height + ' mm · sliced in ' + clock(r.sliceTime)));
    if (!viewer) viewer = Preview3D.createViewer($('#viewer-container'), PLATE);
    setTimeout(function () {
      viewer.resize(); viewer.show(r.tp, r.instances);
      setLayer(r.tp.layers - 1);
    }, 0);
    renderKey();
    updateNext();
  }
  // Version 8 (the owner): four fixed colours, one per group, whatever the filament. Their key
  // is behind a small icon at the view's top left, closed by default: four rows, always the
  // same, so the key never changes with the plate or the settings.
  function renderKey() {
    var lg = $('#pv-key'); if (lg.children.length) return;
    function hex(c) { return '#' + ('00000' + c.toString(16)).slice(-6); }
    Preview3D.GROUPS.forEach(function (g) {
      var li = el('li'), sw = el('i'); sw.style.background = hex(g.color); li.appendChild(sw);
      li.appendChild(el('span', null, g.label)); lg.appendChild(li);
    });
  }
  function setKey(open) { $('#pv-key').hidden = !open; $('#btn-key').setAttribute('aria-expanded', open ? 'true' : 'false'); }
  function closeKey() { setKey(false); }
  function setPreviewHelp(open) { $('#preview-help').hidden = !open; $('#btn-preview-help').setAttribute('aria-expanded', open ? 'true' : 'false'); }
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
    // version 7: a layer's height is a printer figure, always in millimetres
    $('#layer-readout').textContent = (k + 1) + ' / ' + r.tp.layers + ' · ' + U.len(z, 1, 'mm');
    var sl = $('#layer-slider');
    sl.setAttribute('aria-valuemin', '1'); sl.setAttribute('aria-valuemax', String(r.tp.layers)); sl.setAttribute('aria-valuenow', String(k + 1));
    sl.setAttribute('aria-valuetext', 'Layer ' + (k + 1) + ' of ' + r.tp.layers + ', ' + U.len(z, 1) + ' high');
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
    // the colour key: the icon opens and closes it; a click elsewhere or Escape closes it
    $('#btn-key').addEventListener('click', function (e) { e.stopPropagation(); setKey($('#pv-key').hidden); });
    $('#btn-key').addEventListener('pointerdown', function (e) { e.stopPropagation(); });     // not a turn of the view
    $('#pv-key').addEventListener('click', function (e) { e.stopPropagation(); });
    $('#pv-key').addEventListener('pointerdown', function (e) { e.stopPropagation(); });
    // how to move the view: behind a "?" icon, as on the Layout step (fix round 1 of version 8)
    $('#btn-preview-help').addEventListener('click', function (e) {
      e.stopPropagation(); var open = $('#preview-help').hidden; setPreviewHelp(open);
    });
    $('#preview-help').addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', function () { setPreviewHelp(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !$('#preview-help').hidden) { setPreviewHelp(false); $('#btn-preview-help').focus(); }
    });
    // final action on the Send step: PenguinCAM's split button. The button sends at once; the
    // caret's menu offers Download instead.
    $('#btn-do').addEventListener('click', function () { doAction(S.action); });
    // The caret's menu works by keyboard too: Enter opens it on its first item, the arrow keys
    // move between the items, Escape closes it and puts focus back on the caret.
    var caret = $('#btn-do-caret'), menu = $('#do-menu');
    function items() { return $all('#do-menu [role="menuitem"]'); }
    function setMenu(open, focusFirst) {
      menu.hidden = !open; caret.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open && focusFirst) items()[0].focus();
    }
    caret.addEventListener('click', function (e) { e.stopPropagation(); setMenu(menu.hidden, e.detail === 0); });   // detail 0: a key, not a mouse
    items().forEach(function (b) {
      b.addEventListener('click', function () {
        // Choosing from the menu only changes what the button does; a separate press acts.
        // (On the first hardware test, a menu choice that printed at once surprised the owner.)
        S.action = b.getAttribute('data-action'); setMenu(false);
        updateNext(); $('#btn-do').focus();
      });
    });
    menu.addEventListener('keydown', function (e) {
      var list = items(), i = list.indexOf(document.activeElement);
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); setMenu(false); caret.focus(); }
      else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); list[(i + (e.key === 'ArrowDown' ? 1 : list.length - 1)) % list.length].focus(); }
    });
    document.addEventListener('click', function () { setMenu(false); });
  }
  function doAction(a) {
    if (!S.result) return;
    if (a === 'download') {
      var t = $('#send-toast'); t.hidden = false; t.setAttribute('data-sig', S.resultSig);
      t.textContent = 'Downloaded the sliced file of ' + plateName(S.result.instances.length) + ' (' +(0.4 + S.result.instances.length * 0.21).toFixed(1) + ' MB).';
      return;
    }
    sendToPrinter();
  }

  /* ================================================================== old printing (version 3), replaced below */
  /* ================================================================== the printer */
  // The shop printer, as the relay reports it: the real world, not this page. It outlives a
  // refresh, a closed panel and the scenario strip's Reset of the user's work. One delivery
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
  // Version 7 (the owner): the printer reports that a print ended; it cannot tell whether a
  // person has cleared the plate. So a print that finished leaves the printer Free (ruling R8);
  // what remains is one line, "Last print finished 11:25 am (Alex Chen)" in the printer details
  // and "Your print finished at 11:25 am." for its sender, until another plate is sent or 12
  // hours after it finished, whichever comes first (M19).
  var LAST_PRINT_KEEP_MS = 12 * 3600 * 1000;
  function lastFinished() {
    var j = PRN.job;
    return j && j.phase === 'finished' && j.endedAt && nowMs() - j.endedAt.getTime() < LAST_PRINT_KEEP_MS ? j : null;
  }
  function remainingS(j) { return j.phase === 'upload' || j.phase === 'starting' ? j.prep + j.total : Math.max(0, (j.prep + j.total - j.t) * j.slowBy); }
  function finishAt(j) { return new Date(j.sentAt.getTime() + (j.el + remainingS(j)) * 1000); }
  // One reading of the printer for the header icon and the Send step. Version 6 shows no
  // "behind its estimate" and no "late" anywhere (the owner, M24).
  function printerStatus() {
    var j = PRN.job;
    if (!PRN.paired) return { key: 'none', short: 'No printer', title: 'No printer paired', chip: 'off' };
    if (!PRN.online) return { key: 'offline', short: 'Offline', title: ST.PRINTER.name + ' is not answering', chip: 'off' };
    // a print that finished: Free at once, never "Finished" (version 7)
    if (!j || j.phase === 'finished') return { key: 'idle', short: 'Free', title: ST.PRINTER.name + ' is free', chip: '' };
    if (j.phase === 'upload' || j.phase === 'starting') return { key: 'sending', short: 'Sending ' + Math.floor(j.up * 100) + '%', title: 'Sending to ' + ST.PRINTER.name, chip: 'busy' };
    if (j.phase === 'prepare') return { key: 'printing', short: 'Heating', title: ST.PRINTER.name + ' is getting ready to print', chip: 'busy' };
    if (j.phase === 'printing') return { key: 'printing', short: 'Printing ' + Math.floor(j.pct) + '%', title: ST.PRINTER.name + ' is printing', chip: 'busy' };
    if (j.phase === 'waiting') return { key: 'waiting', short: 'Waiting', title: ST.PRINTER.name + ' is waiting for a person: ' + j.waitingFor.label.toLowerCase(), chip: 'wait' };
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
  // The user's own last print: one line, "Your print finished at 11:25 am.", not a card. It
  // shows on the Send step, and on whichever step opens when the user comes back (S.lastNoteOn),
  // until another plate is sent or 12 hours after the print finished.
  function renderLastPrint() {
    var p = $('#last-print'), lf = lastFinished();
    var show = !!lf && lf.mine && (S.step === 'send' || S.lastNoteOn === S.step);
    p.hidden = !show;
    p.textContent = show ? 'Your print finished at ' + clockTime(lf.endedAt) + '.' : '';
  }
  function printerChanged(tick) {
    renderPrinterIcon(); renderLastPrint();
    if (S.step === 'send') {
      var j = PRN.job, k = [sendBlocked(), j && j.phase, j && j.mine, !!S.result, printerStatus().key].join('|');
      if (!tick || k !== sendKey) renderSend();
      else {
        if (j && j.mine && j.phase !== 'finished') renderPrintCard($('#send-live'), j);
        var bc = document.querySelector('#send-printer .busy-card'); if (bc && j && !j.mine) bc.parentNode.replaceChild(busyCard(j), bc);
      }
    }
    updateNext();
  }
  function renderPrinterIcon() {
    var st = printerStatus(), b = $('#pstat');
    b.className = 'pstat s-' + st.key;
    b.querySelector('.ptext').textContent = st.short;
    // version 8: no tooltip; the details themselves open on hover. A screen reader hears the state.
    b.setAttribute('aria-description', st.title);
    if (!$('#pstat-pop').hidden) renderPrinterPop();
  }
  function dl(grid, k, v, cls) { grid.appendChild(el('dt', null, k)); var d = el('dd', cls || null, v); grid.appendChild(d); return d; }
  // The printer details: basic information only (the owner, version 6); print management is
  // done at the printer. They open as part of the icon, a tab joined to it.
  var PAIRING_DOC = '#pairing';      // the documentation page on pairing a printer, to be written
  function renderPrinterPop() {
    var pop = $('#pstat-pop'), st = printerStatus(), j = PRN.job; pop.innerHTML = '';
    var head = el('div', 'pp-head'); head.appendChild(el('span', 'pp-title', st.key === 'none' ? 'No printer' : ST.PRINTER.name));
    var x = el('button', 'pp-close', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Close the printer details'); x.addEventListener('click', closePrinterPop); head.appendChild(x);
    pop.appendChild(head);
    if (st.key === 'none') {
      var p = el('div', 'pp-note', 'PenguinSlicer needs to be paired with a printer. ');
      var a = el('a', null, 'How to pair a printer'); a.href = PAIRING_DOC; a.title = 'Documentation';
      a.addEventListener('click', function (e) { e.preventDefault(); });
      p.appendChild(a); pop.appendChild(p); placePrinterPop(); return;
    }
    if (st.key === 'offline') { pop.appendChild(el('div', 'pp-note', 'Not heard from for ' + PRN.heardAgoMin + ' minutes.')); placePrinterPop(); return; }
    if (!j || j.phase === 'finished') {
      pop.appendChild(el('div', 'pp-note', 'Nothing is printing.'));
      var lf = lastFinished();
      if (lf) pop.appendChild(el('div', 'pp-note', 'Last print finished ' + clockTime(lf.endedAt) + ' (' + (lf.mine ? 'you' : lf.who) + ')'));
      placePrinterPop(); return;
    }
    var g = el('dl', 'pp-grid'), sending = j.phase === 'upload' || j.phase === 'starting';
    var who = j.mine ? j.who + ' (you)' : j.who;
    if (sending) {
      // sending: as version 5 had it (the owner: good as it is), less the estimate row and the note
      dl(g, 'Sending', j.what); dl(g, 'Sent by', who);
      dl(g, 'Done', 'sending ' + Math.floor(j.up * 100) + '%');
      dl(g, 'Time left', hm(remainingS(j))); dl(g, 'Expected finish', clockTime(finishAt(j)));
    } else if (isLive(j)) {
      // printing: who sent it, percent done, time left and the finish time; nothing more
      dl(g, 'Sent by', who);
      dl(g, 'Done', j.phase === 'prepare' ? 'heating' : Math.floor(j.pct) + '%');
      if (j.phase !== 'waiting') { dl(g, 'Time left', hm(remainingS(j))); dl(g, 'Expected finish', clockTime(finishAt(j))); }
    } else {
      dl(g, 'Sent by', who);
      dl(g, j.phase === 'finished' ? 'Finished' : 'Stopped', clockTime(j.endedAt) + (j.phase === 'failed' ? ', layer ' + j.layer + ' of ' + j.layers : ''));
    }
    pop.appendChild(g);
    if (sending) { var bar = el('div', 'pp-bar'), f = el('div'); f.style.width = (j.up * 100) + '%'; bar.appendChild(f); pop.appendChild(bar); }
    if (j.phase === 'waiting') pop.appendChild(el('div', 'pp-note pp-late', j.waitingFor.label + '. ' + j.waitingFor.todo));
    placePrinterPop();
  }
  // Joined to the icon: the details' top-right corner sits under the icon's right edge, and the
  // open icon loses its bottom border, so the two read as one tab.
  function placePrinterPop() {
    var pop = $('#pstat-pop'), b = $('#pstat'), host = pop.parentNode;
    if (pop.hidden || !host) return;
    var hr = host.getBoundingClientRect(), br = b.getBoundingClientRect();
    pop.style.top = (br.bottom - hr.top - 1) + 'px';
    pop.style.right = Math.max(0, hr.right - br.right) + 'px';
    pop.style.left = 'auto';
    pop.style.width = Math.min(br.right - hr.left - 8, 340) + 'px';    // at least 8 px clear of the panel's left edge
  }
  // Version 8 (the owner): the details open when the pointer rests on the icon, and still on a
  // click. Opened by the pointer, they stay open while it is over the icon or the details and
  // close a short while after it leaves both. A click pins them open: then only a click
  // elsewhere, Escape, × or a second click on the icon closes them. Touch and keyboard work as
  // before (a tap or Enter is a click).
  var pstatPinned = false, pstatHoverTimer = null, pstatLeaveTimer = null;
  var PSTAT_OPEN_MS = 150, PSTAT_GRACE_MS = 300;
  function openPrinterPop(pinned) {
    var pop = $('#pstat-pop');
    pstatPinned = pstatPinned || pinned;
    if (!pop.hidden) return;
    closeChangesPop(); hideTip();
    pop.hidden = false; $('#pstat').setAttribute('aria-expanded', 'true');
    renderPrinterPop();
  }
  function togglePrinterPop(e) {
    e.stopPropagation();
    clearTimeout(pstatHoverTimer); clearTimeout(pstatLeaveTimer);
    var pop = $('#pstat-pop');
    if (pop.hidden) openPrinterPop(true);
    else if (!pstatPinned) pstatPinned = true;            // opened by the pointer: the click pins it
    else closePrinterPop();
  }
  function closePrinterPop() {
    clearTimeout(pstatHoverTimer); clearTimeout(pstatLeaveTimer); pstatPinned = false;
    $('#pstat-pop').hidden = true; $('#pstat').setAttribute('aria-expanded', 'false');
  }
  function bindPrinterHover() {
    function enter(e) {
      if (e.pointerType === 'touch') return;
      clearTimeout(pstatLeaveTimer);
      if ($('#pstat-pop').hidden && e.currentTarget.id === 'pstat') { clearTimeout(pstatHoverTimer); pstatHoverTimer = setTimeout(function () { openPrinterPop(false); }, PSTAT_OPEN_MS); }
    }
    function leave(e) {
      if (e.pointerType === 'touch') return;
      clearTimeout(pstatHoverTimer);
      if (pstatPinned || $('#pstat-pop').hidden) return;
      clearTimeout(pstatLeaveTimer);
      pstatLeaveTimer = setTimeout(function () { if (!pstatPinned) closePrinterPop(); }, PSTAT_GRACE_MS);
    }
    ['#pstat', '#pstat-pop'].forEach(function (s) { $(s).addEventListener('pointerenter', enter); $(s).addEventListener('pointerleave', leave); });
  }

  // The scenario strip's Printer menu: what someone else is doing at the shop printer.
  function setPrinter(kind, quiet) {
    PRN.paired = kind !== 'unpaired'; PRN.online = kind !== 'offline'; PRN.heardAgoMin = kind === 'offline' ? 7 : 0;
    var other = { mine: false, who: OTHER, plate: plateName(8), what: '8 instances of Gusset Plate', layers: 96, total: 2 * 3600 + 25 * 60 };
    if (kind === 'idle') PRN.job = null;          // offline and not paired keep whatever the printer was doing
    if (kind === 'other_sending') PRN.job = newPrintJob(Object.assign(other, { phase: 'upload', up: 0.35 }));
    if (kind === 'other_printing') PRN.job = newPrintJob(Object.assign(other, { phase: 'printing', t: 270 + 0.61 * other.total }));
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
    // "Back where you were … its progress is below" holds only while this user's print runs
    if (!mineLive) dropNotice('resumed-send');
    var live = $('#send-live'), sum = $('#send-summary'), pr = $('#send-printer');
    // "Downloaded the sliced file of …" belongs to the slice it was said of
    var toast = $('#send-toast'); if (!toast.hidden && toast.getAttribute('data-sig') !== S.resultSig) toast.hidden = true;
    // the progress of this user's own plate, at the top, once sent (version 6: no line under
    // the step title; the print card, the busy card or the message says where things stand)
    // version 7: a print of this user's that finished is no card but the one-line note above
    // (#last-print), and the new plate's Send is offered below it
    if (j && j.mine && j.phase !== 'finished') renderPrintCard(live, j); else { live.innerHTML = ''; live.removeAttribute('data-key'); }
    renderLastPrint();
    // what will be printed
    sum.innerHTML = '';
    if (!r) { sum.appendChild(msg('info', 'Nothing sliced yet.', 'The plate is sliced on the Preview step.', [['Back to Preview', function () { gotoStep('preview'); }]])); pr.innerHTML = ''; return; }
    var c = el('div', 'card'), g = el('dl', 'send-sum');
    // the printer by name only: its state is the printer-status icon's, and the card or message beside this
    dl(g, 'Printer', printerStatus().key === 'none' ? 'None paired' : ST.PRINTER.name);
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
        var t = el('div'); t.appendChild(el('strong', null, 'Check that the plate is clear')); t.appendChild(document.createTextNode(' and ' + r.filament.type + ' is loaded. Send starts the print at once.'));
        cp.appendChild(t); pr.appendChild(cp);
      } else if (why === 'other') pr.appendChild(busyCard(j));
      else if (why === 'offline') pr.appendChild(msg('warn', ST.PRINTER.name + ' has not been heard from for ' + PRN.heardAgoMin + ' minutes, so Send waits.',
        'Your sliced plate stays ready, and Send comes back as soon as the printer answers. Or download the file.',
        [['Download the sliced file', function () { doAction('download'); }]]));
      else if (why === 'none') {
        var nm = msg('warn', 'No printer is paired with PenguinSlicer, so nothing can be sent.',
          'An administrator pairs the printer once, from the computer beside it. Meanwhile, download the file and print it from Orca Slicer or Bambu Studio. ',
          [['Download the sliced file', function () { doAction('download'); }]]);
        // the same link as the printer details give
        var a = el('a', null, 'How to pair a printer'); a.href = PAIRING_DOC; a.title = 'Documentation';
        a.addEventListener('click', function (e) { e.preventDefault(); });
        nm.querySelector('.todo').appendChild(a); pr.appendChild(nm);
      }
    }
  }
  // Another user's print or send: whose, what, how far, when it should finish. Send waits;
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
    cell(clockTime(finishAt(j)), 'expected finish');
    c.appendChild(g);
    if (waiting) c.appendChild(el('div', 'bc-note pp-late', j.waitingFor.label + ': someone at the printer has to ' + j.waitingFor.todo.charAt(0).toLowerCase() + j.waitingFor.todo.slice(1)));
    // a consequence the user cannot see: nothing queues
    c.appendChild(el('div', 'bc-note', 'Send comes back when the printer is free; nothing queues.'));
    return c;
  }
  function sendToPrinter() {
    if (!sliceReady() || sendBlocked()) return;
    $('#send-errors').innerHTML = ''; $('#send-toast').hidden = true;
    dropNotice('cancel-send');            // "nothing will print" stops being true
    var r = S.result;
    PRN.job = newPrintJob({ mine: true, who: ME, plate: plateName(r.instances.length), what: plural(r.instances.length, 'instance', 'instances') + ': ' + partsLine().join(', '),
                            layers: r.tp.layers, total: r.est.seconds, failAt: Mock.take('print_fail') ? 0.38 : null, waitAt: Mock.take('print_wait') ? 0.3 : null });
    PRN.job.sliceSig = S.resultSig;
    startPrintTicker(); printerChanged();
    $('#wiz-body').scrollTop = 0;
  }
  // This user's own delivery job and print: stages, percent, layer, time left, expected
  // finish. The card is built once per stage; between stages only its figures change, so a
  // button in it is never replaced under the pointer.
  function printCells(j) {
    if (j.phase === 'failed') return [[j.layer + ' of ' + j.layers, 'layer reached'], [clockTime(j.endedAt), 'stopped at']];
    if (j.phase === 'finished') return [[j.layers + ' of ' + j.layers, 'layers'], [clockTime(j.endedAt), 'finished at']];
    return [
      [j.phase === 'printing' || j.phase === 'waiting' ? j.layer + ' of ' + j.layers : '0 of ' + j.layers, 'layer'],
      [hm(remainingS(j)), 'time left'],
      [clockTime(finishAt(j)), 'expected finish'],
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
      var ua = el('div', 'pc-acts');
      ua.appendChild(btn('Cancel sending', function () {
        PRN.job = null; printerChanged();
        notify('info', 'Sending cancelled. Nothing reached ' + ST.PRINTER.name + ' and nothing will print.', 'Your sliced plate is still here.', 'cancel-send');
      }, 'danger-outline'));
      box.appendChild(ua);
    }
    if (j.phase === 'waiting') box.appendChild(msg('warn', j.waitingFor.label + '.', j.waitingFor.todo));
    if (j.phase === 'failed') box.appendChild(msg('error', 'The print stopped at layer ' + j.layer + ' of ' + j.layers + ' (' + Math.floor(j.pct) + '%): the printer reported a filament tangle or a clogged nozzle.',
      'Clear the plate and check the filament path at the printer, then send the plate again from here. The sliced file is still here.', null,
      'The printer’s screen shows the fault and its own help for it. Check the filament path from the spool to the nozzle, and the nozzle for a clog.'));
    card.appendChild(box);
  }

  /* ================================================================== tooltips (version 8) */
  // The owner: the step circles' tooltips appear faster, look like the rest of PenguinSlicer
  // and have larger text. Every `title` in the panel becomes the panel's own tooltip: shown
  // 150 ms after the pointer comes to rest on it and at once on keyboard focus, hidden on
  // Escape, when the pointer leaves, on a press and on blur; in the panel's font at the body
  // text size (14 px), styled like the printer details, and kept inside the panel. A title set
  // later (the code sets many as things change) is taken over as soon as it is set. Option
  // elements and the 3D views keep the browser's tooltip.
  var tip = null, tipFor = null, tipPending = null, tipTimer = null, TIP_DELAY_MS = 150;
  var TIP_SKIP = 'option, canvas, .gl-view';
  function letters(s) { return (s || '').toLowerCase().replace(/[^a-z]+/g, ''); }
  function adoptTitle(n) {
    if (!n.hasAttribute || !n.hasAttribute('title') || n.matches(TIP_SKIP)) return;
    var t = n.getAttribute('title'); n.removeAttribute('title');
    if (t) n.setAttribute('data-tip', t); else n.removeAttribute('data-tip');
    // a screen reader still hears the text, as it heard the title, unless the element's name
    // already says it (a step circle is named "Step 3: Layout")
    var name = n.getAttribute('aria-label');
    if (t && !(name && letters(name).indexOf(letters(t)) >= 0)) n.setAttribute('aria-description', t); else n.removeAttribute('aria-description');
    if (n === tipFor) { if (t) showTip(n); else hideTip(); }
  }
  // Fix round 1 of version 8: a tooltip says only what is not on screen.
  function visibleText(n) { return letters(n.innerText); }
  function cutShort(n) {
    return [n].concat([].slice.call(n.querySelectorAll('*'))).some(function (x) {
      return x.clientWidth > 0 && (x.scrollWidth > x.clientWidth + 1 || x.scrollHeight > x.clientHeight + 1);
    });
  }
  function tipWanted(n, text) {
    // a step pill, or the current step's circle, already shows its name
    if (n.matches('#stepbar li')) { var sn = n.querySelector('.sn'); if (sn && sn.offsetWidth > 0) return false; }
    // a tooltip that repeats the element's own visible text shows only when that text is cut short
    var own = visibleText(n), t = letters(text);
    if (own && t && own.indexOf(t) >= 0) return cutShort(n);
    return true;
  }
  function showTip(n) {
    var text = n.getAttribute('data-tip'); if (!text || !n.isConnected || !n.offsetParent) return;
    if (!tipWanted(n, text)) return;
    var root = $('#wizard');
    tipFor = n; tip.textContent = text; tip.style.left = '0px'; tip.style.top = '0px'; tip.hidden = false;
    // not where adoptTitle gave no description: the element's name already says it (a step circle)
    if (!n.hasAttribute('aria-describedby') && n.hasAttribute('aria-description')) n.setAttribute('aria-describedby', 'wiz-tip');
    var w = root.getBoundingClientRect(), r = n.getBoundingClientRect(), tw = tip.offsetWidth, th = tip.offsetHeight, M = 6;
    var left = Math.max(M, Math.min(r.left + r.width / 2 - tw / 2 - w.left, w.width - tw - M));
    var top = r.bottom - w.top + 6;                                   // below the element, else above it
    if (top + th > w.height - M) top = Math.max(M, r.top - w.top - th - 6);
    tip.style.left = left + 'px'; tip.style.top = top + 'px';
  }
  function hideTip() {
    clearTimeout(tipTimer); tipPending = null;
    if (!tip) return;
    if (tipFor && tipFor.getAttribute('aria-describedby') === 'wiz-tip') tipFor.removeAttribute('aria-describedby');
    tipFor = null; tip.hidden = true;
  }
  function bindTips() {
    var root = $('#wizard');
    tip = el('div', 'wiz-tip'); tip.id = 'wiz-tip'; tip.setAttribute('role', 'tooltip'); tip.hidden = true; root.appendChild(tip);
    $all('#wizard [title]').forEach(adoptTitle);
    new MutationObserver(function (list) {
      list.forEach(function (m) {
        if (m.type === 'attributes') { adoptTitle(m.target); return; }
        m.addedNodes.forEach(function (n) { if (n.nodeType !== 1) return; adoptTitle(n); n.querySelectorAll('[title]').forEach(adoptTitle); });
      });
    }).observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ['title'] });
    root.addEventListener('pointerover', function (e) {
      if (e.pointerType === 'touch') return;
      var n = e.target.closest && e.target.closest('[data-tip]');
      if (!n || n === tipFor || n === tipPending) return;
      hideTip(); tipPending = n;
      tipTimer = setTimeout(function () { tipPending = null; showTip(n); }, TIP_DELAY_MS);
    });
    root.addEventListener('pointerout', function (e) {
      var n = tipFor || tipPending;
      if (!n || !n.contains(e.target) || (e.relatedTarget && n.contains(e.relatedTarget))) return;
      hideTip();
    });
    root.addEventListener('pointerdown', hideTip, true);
    root.addEventListener('focusin', function (e) {
      var n = e.target.closest && e.target.closest('[data-tip]');
      // at once on focus only for an element with no visible text (an icon, a step circle); a
      // menu or a text field shows its tooltip on hover only (fix round 1 of version 8)
      if (!n || n.matches('select, input, textarea') || visibleText(n)) return;
      if (e.target.matches(':focus-visible')) { hideTip(); showTip(n); }
    });
    root.addEventListener('focusout', function (e) { if (tipFor && tipFor.contains(e.target)) hideTip(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') hideTip(); }, true);
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
    $('#chg-pop').addEventListener('click', function (e) { e.stopPropagation(); });
    // version 8: the printer details also open when the pointer rests on the icon
    bindPrinterHover();
    document.addEventListener('click', function () { closePrinterPop(); closeChangesPop(); closeKey(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closePrinterPop(); closeChangesPop(); closeKey(); } });
    // a joined pop follows its icon or chip when the panel is widened
    window.addEventListener('resize', function () { placePrinterPop(); if (!$('#chg-pop').hidden) renderChangesPop(); });
  }

  // Start the page afresh. Work that runs on the server (a slice job, the printer) is not the
  // page's: it survives unless `wipe` says the scenario strip's Reset threw the user's work away.
  function reset(ctx, keep) {
    jobs.slice().forEach(function (j) { if (!j.server) dropJob(j); });
    if (!keep && S && S.job && S.job.state === 'running') { stopJob(S.job); S.job.state = 'cancelled'; }
    S = fresh(ctx || 'partstudio');
    partsNote = null; layHint = null;
    closeChangesPop();
    $('#advanced').hidden = true; setCoveredInert(false); advOpener = null; placePrinterIcon(false);
    pendingSnap = null;
    $('#send-toast').hidden = true; clearWhy(); closeLayoutHelp();
    if (editor) editor.sync();
    if (viewer) viewer.clear();
    clearPreview();
    $('#send-live').innerHTML = ''; $('#send-live').removeAttribute('data-key');
    renderPrinterIcon(); renderConfig();
    gotoStep(ORDER[0]);
  }

  /* ================================================================== coming back */
  // The scenario strip's Refresh page, Close and reopen, and Come back 2 h later. The page's
  // own state is lost each time; what the server holds is not: this user's slice job (with
  // its plate configuration) and delivery job, and the printer. When this user's slice or
  // send is still running, the wizard opens on that step with the parts and layout restored.
  // Otherwise it starts at Parts, the first step, and the printer-status icon shows what
  // anyone else is doing.
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
        null, sending ? 'resumed-send' : 'resumed');
    } else {
      // version 7: a print that finished is the one-line note (below), not a notification
      if (j && j.mine && j.phase === 'failed' && kind === 'later') {
        notify('error', 'Your print stopped at ' + clockTime(j.endedAt) + ', at layer ' + j.layer + ' of ' + j.layers + '.',
          'Your parts were not kept; add them again to print again.', 'resumed');
      }
      // a finished slice that was never sent does not outlast two hours away (M18); say so in one line
      var sentIt = j && j.mine && j.sliceSig === plate.resultSig;
      if (kind === 'later' && plate.result && plate.resultSig && !sentIt) notify('info', 'The slice of your earlier plate has expired; add its parts again to print it.', null, 'expired');
    }
    // the user's own print that finished: its one-line note shows on whichever step opened
    S.lastNoteOn = S.step; renderLastPrint();
  }
  // The scenario strip's "12 hours later": the clock moves on with the panel left open. A print
  // still running ends; a print that finished more than 12 hours ago loses its line and note.
  function twelveHoursLater() {
    var j = PRN.job;
    if (j) for (var k = 0; k < 4000 && isLive(j); k++) stepPrint(j, 18);
    var add = LAST_PRINT_KEEP_MS + 60000;
    // at Fast speed a print's own clock runs ahead of the page's: move on past its end too
    if (j && j.endedAt) add = Math.max(add, j.endedAt.getTime() + LAST_PRINT_KEEP_MS + 60000 - nowMs());
    clockOffsetMs += add;
    printerChanged();
    if (S.step === 'send') renderSend();
  }

  bindTips(); bindNav(); bindSetup(); bindAdvanced(); bindParts(); bindLayout(); bindPreview();

  window.Wizard = {
    Mock: Mock, reset: reset, onOnshapeSelect: onOnshapeSelect, setOption: setOption,
    setPrinter: setPrinter, comeBack: comeBack, twelveHoursLater: twelveHoursLater,
    armed: function () { if (S.step === 'layout') applyLayoutArms(); },
    state: function () { return S; },
    printer: function () { return PRN; },
    step: function () { return S.step; },
    setUploadUnits: function (u) { Config.uploadUnits = u; if (S.step === 'parts') renderParts(); },
    resize: function () { if (editor) editor.resize(); if (viewer) viewer.resize(); placePrinterPop(); if (!$('#chg-pop').hidden) renderChangesPop(); }
  };
})();
