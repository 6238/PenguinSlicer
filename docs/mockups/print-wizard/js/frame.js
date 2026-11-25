/* PenguinSlicer mockup: the stand-in Onshape tab (Parts list, graphics area) and the
 * scenario strip. Clicking a part here is what a click in Onshape would send the panel. */
(function () {
  'use strict';
  var T = THREE, P = MockParts;
  function $(s) { return document.querySelector(s); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  // ctx: partstudio (Part Studio 1, inches), partstudio_mm (the metric Part Studio), assembly, standalone
  var ctx = 'partstudio', selected = [];
  function studio() { return ctx === 'partstudio_mm' ? P.PART_STUDIOS[1] : P.PART_STUDIOS[0]; }
  function isStudio(c) { return c === 'partstudio' || c === 'partstudio_mm'; }
  function docUnits() { return ctx === 'assembly' ? P.ASSEMBLY.units : studio().units; }

  /* ------------------------------------------------------------ graphics area */
  var gfx = (function () {
    var host = $('#os-graphics');
    var renderer = new T.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    host.appendChild(renderer.domElement);
    var scene = new T.Scene(), camera = new T.PerspectiveCamera(35, 1, 1, 10000); camera.up.set(0, 0, 1);
    scene.add(new T.HemisphereLight(0xffffff, 0x8090a0, 0.9));
    var dl = new T.DirectionalLight(0xffffff, 0.55); dl.position.set(-300, -500, 800); scene.add(dl);
    var controls = new T.OrbitControls(camera, renderer.domElement); controls.screenSpacePanning = true;
    var meshes = [], needs = true;
    controls.addEventListener('change', function () { needs = true; });
    (function loop() { requestAnimationFrame(loop); if (!needs || !host.offsetParent) return; needs = false; renderer.render(scene, camera); })();
    function resize() { var w = host.clientWidth, h = host.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); needs = true; }
    if (window.ResizeObserver) new ResizeObserver(resize).observe(host);

    // Where each instance sits in the mock assembly, so the Assembly tab shows a mechanism
    // and not a row of loose parts: two hood ribs as side plates, two hex shafts between
    // them carrying the pulleys and spacers, gussets and brackets at the feet, the camera
    // mount on top. [key, x, y, z, turn about Y (deg), turn about Z (deg)]; z is up.
    var ASSEMBLED = [
      ['rib', -96, 0, 176.5, 0, 0], ['rib', 96, 0, 176.5, 0, 0],
      ['shaft', 0, -1.3, 55.2, 0, 0], ['shaft', 0, -1.3, 297.8, 0, 0],
      ['pulley', -62, -1.3, 55.2, 90, 0], ['pulley', -62, -1.3, 297.8, 90, 0],
      ['spacer', -28, -1.3, 55.2, 90, 0], ['spacer', 18, -1.3, 55.2, 90, 0], ['spacer', 64, -1.3, 55.2, 90, 0],
      ['spacer', -28, -1.3, 297.8, 90, 0], ['spacer', 18, -1.3, 297.8, 90, 0], ['spacer', 64, -1.3, 297.8, 90, 0],
      ['gusset', -103.5, -6, 62, 90, 0], ['gusset', 103.5, -6, 62, 90, 0],
      ['bracket', -60, -30, 20, 0, 0], ['bracket', 60, -30, 20, 0, 180], ['bracket', -60, 26, 20, 0, 0], ['bracket', 60, 26, 20, 0, 180],
      ['camera', 0, 4, 335, 0, 0]
    ];
    function buildAssembly() {
      meshes.forEach(function (m) { scene.remove(m); }); meshes = [];
      ASSEMBLED.forEach(function (a) {
        var def = P.byKey[a[0]];
        var m = new T.Mesh(def.geometry, new T.MeshStandardMaterial({ color: 0xb9c3cd, roughness: 0.55, metalness: 0.1, flatShading: true }));
        m.position.set(a[1], a[2], a[3]);
        m.rotation.set(0, a[4] * Math.PI / 180, a[5] * Math.PI / 180, 'ZYX');
        m.userData.key = a[0];
        scene.add(m); meshes.push(m);
      });
      var box = new T.Box3();
      meshes.forEach(function (m) { box.expandByObject(m); });
      var c = new T.Vector3(), sz = new T.Vector3(); box.getCenter(c); box.getSize(sz);
      var span = Math.max(sz.x, sz.y, sz.z);
      controls.target.copy(c);
      camera.position.set(c.x - span * 1.15, c.y - span * 1.7, c.z + span * 0.6);
      controls.update(); paint();
    }
    function build(items) {
      if (ctx === 'assembly') return buildAssembly();
      meshes.forEach(function (m) { scene.remove(m); }); meshes = [];
      var x = 0, rowMax = 0, maxW = 0;
      items.forEach(function (it) {
        var def = P.byKey[it.key];
        for (var i = 0; i < it.count; i++) {
          var m = new T.Mesh(def.geometry, new T.MeshStandardMaterial({ color: 0xb9c3cd, roughness: 0.55, metalness: 0.1, flatShading: true }));
          m.position.set(x + def.size.x / 2, (i % 3) * (def.size.y + 15), def.size.z / 2);
          m.userData.key = it.key; m.userData.std = !!it.std;
          scene.add(m); meshes.push(m);
          rowMax = Math.max(rowMax, (i % 3 + 1) * (def.size.y + 15));
          if (i % 3 === 2 || i === it.count - 1) x += def.size.x + 25;
        }
        maxW = x;
      });
      var box = new T.Box3();
      meshes.forEach(function (m) { box.expandByObject(m); });
      var c = new T.Vector3(), sz = new T.Vector3(); box.getCenter(c); box.getSize(sz);
      var span = Math.max(sz.x, sz.y, sz.z);
      controls.target.copy(c);
      camera.position.set(c.x - span * 0.25, c.y - span * 1.25, c.z + span * 0.7);
      controls.update(); paint();
    }
    function paint() {
      meshes.forEach(function (m) {
        var on = selected.indexOf(m.userData.key) >= 0;
        m.material.color.set(on ? 0xffc93c : 0xb9c3cd);
        m.material.emissive = new T.Color(on ? 0x332200 : 0x000000);
      });
      needs = true;
    }
    var ray = new T.Raycaster(), v = new T.Vector2(), down = null;
    renderer.domElement.addEventListener('pointerdown', function (e) { down = [e.clientX, e.clientY]; });
    renderer.domElement.addEventListener('pointerup', function (e) {
      if (!down || Math.abs(e.clientX - down[0]) + Math.abs(e.clientY - down[1]) > 4 || e.button !== 0) { down = null; return; }
      down = null;
      var r = renderer.domElement.getBoundingClientRect();
      v.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(v, camera);
      var hit = ray.intersectObjects(meshes, false)[0];
      if (hit) clickPart(hit.object.userData.key, e.shiftKey || e.ctrlKey || e.metaKey);
      else { selected = []; renderList(); paint(); }
    });
    return { build: build, paint: paint, resize: resize };
  })();

  /* ------------------------------------------------------------ the feature and parts lists */
  function features() {
    var box = $('#os-features'); box.innerHTML = '';
    var list = ctx === 'assembly' ? ['Origin', 'Mate connectors (12)', 'Fastened 1', 'Revolute 1', 'Revolute 2', 'Fastened 2']
                                  : ['Origin', 'Top', 'Front', 'Right', 'Sketch 1', 'Extrude 1', 'Sketch 2', 'Extrude 2', 'Fillet 1'];
    list.forEach(function (f) { box.appendChild(el('div', null, f)); });
    $('#os-feat-head').firstChild.textContent = ctx === 'assembly' ? 'Assembly features ' : 'Features ';
    $('#os-feat-head .count').textContent = '(' + list.length + ')';
  }
  function items() {
    if (ctx === 'assembly') return P.ASSEMBLY.instances.map(function (i) { return { key: i.key, count: i.count }; });
    return studio().parts.map(function (k) { return { key: k, count: 1 }; });
  }
  function renderList() {
    var ul = $('#os-parts'); ul.innerHTML = '';
    var its = items();
    $('#os-parts-title').textContent = ctx === 'assembly' ? 'Instances' : 'Parts';
    $('#os-parts-count').textContent = '(' + its.reduce(function (a, i) { return a + i.count; }, 0) + (ctx === 'assembly' ? ' + ' + P.ASSEMBLY.standardContent.reduce(function (a, s) { return a + s.count; }, 0) + ' standard' : '') + ')';
    its.forEach(function (it) {
      var def = P.byKey[it.key], li = el('li');
      if (selected.indexOf(it.key) >= 0) li.className = 'selected';
      li.appendChild(el('span', 'icon'));
      li.appendChild(el('span', null, def.name));
      if (ctx === 'assembly') li.appendChild(el('span', 'n', '<' + it.count + '>'));
      li.addEventListener('click', function (e) { clickPart(it.key, e.shiftKey || e.ctrlKey || e.metaKey); });
      ul.appendChild(li);
    });
    if (ctx === 'assembly') {
      P.ASSEMBLY.standardContent.forEach(function (s) {
        var li = el('li', 'std'); li.appendChild(el('span', 'icon std')); li.appendChild(el('span', null, s.name)); li.appendChild(el('span', 'n', '<' + s.count + '>'));
        li.title = 'Standard content: not printed';
        ul.appendChild(li);
      });
    }
  }
  function clickPart(key, adding) {
    if (adding) { if (selected.indexOf(key) < 0) selected.push(key); }
    else selected = [key];
    renderList(); gfx.paint();
    var took = window.Wizard.onOnshapeSelect(key, docUnits());
    $('#os-hint').textContent = took ? 'Selected ' + P.byKey[key].name + '; PenguinSlicer received it.'
                                     : 'Selected ' + P.byKey[key].name + '. PenguinSlicer adds parts only on its Parts step.';
  }

  /* ------------------------------------------------------------ scenario strip */
  var ERROR_NAMES = {};
  Array.prototype.forEach.call(document.querySelectorAll('#sc-error option'), function (o) { ERROR_NAMES[o.value] = o.textContent; });
  function renderArmed() {
    var box = $('#sc-armed'); box.innerHTML = '';
    var M = window.Wizard.Mock;
    if (!M.armed.length) { box.appendChild(el('span', 'none', 'nothing armed')); return; }
    M.armed.forEach(function (k) {
      var chip = el('span', 'armed', ERROR_NAMES[k].replace(/^\S+\s/, ''));
      var x = el('button', null, '×'); x.type = 'button'; x.title = 'Disarm';
      x.addEventListener('click', function () { M.disarm(k); });
      chip.appendChild(x); box.appendChild(chip);
    });
  }
  // Moving between the document's two Part Studios is switching Onshape tabs with the panel
  // open: the wizard keeps its plate, so inch and metric parts can share one. Any other change
  // of context starts the wizard afresh. `fresh` (Reset) always starts afresh.
  function setContext(c, fresh) {
    var keep = !fresh && isStudio(ctx) && isStudio(c);
    ctx = c; selected = [];
    var sa = c === 'standalone';
    $('#frame').hidden = sa; $('#standalone').hidden = !sa;
    var wiz = $('#wizard');
    (sa ? $('#sa-slot') : $('#panel-slot')).appendChild(wiz);
    $('#os-tab').textContent = c === 'assembly' ? P.ASSEMBLY.tab : P.PART_STUDIOS[0].tab;
    $('#os-tab2').hidden = c === 'assembly';
    $('#os-tab').classList.toggle('on', c !== 'partstudio_mm'); $('#os-tab2').classList.toggle('on', c === 'partstudio_mm');
    $('#sc-context').value = c;
    $('#os-hint').textContent = 'Click a part to select it; Shift-click to select several.';
    features(); renderList();
    if (!sa) gfx.build(items());
    if (!keep) window.Wizard.reset(isStudio(c) ? 'partstudio' : c);
    setTimeout(function () { gfx.resize(); window.Wizard.resize(); }, 0);
  }
  $('#os-tab').addEventListener('click', function () { if (ctx === 'partstudio_mm') setContext('partstudio'); });
  $('#os-tab2').addEventListener('click', function () { if (ctx === 'partstudio') setContext('partstudio_mm'); });
  function setWidth(px) {
    document.documentElement.style.setProperty('--panel-width', px + 'px');
    setTimeout(function () { gfx.resize(); window.Wizard.resize(); }, 0);
  }

  function relayout() { setTimeout(function () { gfx.resize(); window.Wizard.resize(); }, 0); }   // the page below gains or loses height
  $('#sc-more').addEventListener('click', function () {
    var open = this.getAttribute('aria-expanded') !== 'true';
    this.setAttribute('aria-expanded', open ? 'true' : 'false');
    this.textContent = open ? 'Fewer controls' : 'More controls';
    $('#sc-row2').hidden = !open; $('#sc-row3').hidden = !open;
    relayout();
  });
  $('#sc-hide').addEventListener('click', function () { $('#scenario').hidden = true; $('#sc-show').hidden = false; relayout(); });
  $('#sc-show').addEventListener('click', function () { $('#scenario').hidden = false; $('#sc-show').hidden = true; relayout(); });
  $('#sc-how').addEventListener('toggle', relayout);
  $('#sc-arm').addEventListener('click', function () { window.Wizard.Mock.arm($('#sc-error').value); window.Wizard.armed(); });
  $('#sc-printer').addEventListener('change', function () { window.Wizard.setPrinter(this.value); });
  $('#sc-refresh').addEventListener('click', function () { window.Wizard.comeBack('refresh'); });
  $('#sc-reopen').addEventListener('click', function () { window.Wizard.comeBack('reopen'); });
  $('#sc-later').addEventListener('click', function () { window.Wizard.comeBack('later'); });
  $('#sc-speed').addEventListener('change', function () { window.Wizard.Mock.speed = this.value; });
  $('#sc-width').addEventListener('change', function () { if (this.value !== 'drag') setWidth(+this.value); });
  $('#sc-lay').addEventListener('change', function () { window.Wizard.setOption('lay', this.value); });
  $('#sc-mouse').addEventListener('change', function () { window.Wizard.setOption('scheme', this.value); });
  $('#sc-arrive').addEventListener('change', function () { window.Wizard.setOption('arrival', this.value); });
  // A drag handle on the panel's left edge, as Onshape's own panel has (the owner widens
  // PenguinCAM's panel this way). The limits here, 300 to 900 px, are the mockup's: 300 px is
  // PenguinCAM's own minimum width, and the design uses extra width up to about 800 px.
  (function () {
    var grip = $('#os-right-grip'), sel = $('#sc-width'), start = null;
    var opt = document.createElement('option'); opt.value = 'drag'; opt.hidden = true; sel.appendChild(opt);
    grip.addEventListener('pointerdown', function (e) {
      start = { x: e.clientX, w: $('#os-right').clientWidth };        // the panel's width, without its border
      grip.setPointerCapture(e.pointerId); grip.classList.add('on'); e.preventDefault();
    });
    grip.addEventListener('pointermove', function (e) {
      if (!start) return;
      var w = Math.round(Math.min(900, Math.max(300, start.w + (start.x - e.clientX))));
      document.documentElement.style.setProperty('--panel-width', w + 'px');
      var preset = Array.prototype.some.call(sel.options, function (o) { return o.value === String(w); });
      if (preset) sel.value = String(w); else { opt.textContent = w + ' px (dragged)'; sel.value = 'drag'; }
      gfx.resize(); window.Wizard.resize();
    });
    grip.addEventListener('pointerup', function () { start = null; grip.classList.remove('on'); });
  })();
  $('#sc-context').addEventListener('change', function () { setContext(this.value); });
  $('#sc-upload-units').addEventListener('change', function () { window.Wizard.setUploadUnits(this.value); });
  $('#sc-reset').addEventListener('click', function () {
    window.Wizard.Mock.armed = []; renderArmed();
    $('#sc-printer').value = 'idle'; window.Wizard.setPrinter('idle', true);
    setContext($('#sc-context').value, true);
  });

  window.Wizard.Mock.onChange = renderArmed;
  window.Wizard.Mock.speed = $('#sc-speed').value;
  renderArmed();
  setContext('partstudio', true);
  window.Frame = { clickPart: clickPart, setContext: setContext, setWidth: setWidth };
})();
