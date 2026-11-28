// The Layout step's drawing (wizard/README-details.md, "What is on the step"), into the mockup's
// markup of the step: the toolbar (Arrange, Auto-orient, and "?" with the list of gestures), the
// status line, the view (panel/layout-view.js, made the first time the step is shown, since it
// takes one of the few WebGL contexts a browser gives a page), the selection line and its link,
// the messages and the figures line. Its behaviour is layout.js's; this module draws the model
// and passes on what the user does. Every name and sentence is set as text, never as markup.
import * as W from '../layout-sentences.js';
import { PART_COLOURS } from '../page-constants.js';
import { el, message } from './telling.js';

// createLayoutStep(section, {layout, parts, geometry, frames, store, createView}): `createView`
// makes the 3D view (createLayoutView), and is left out where there is no WebGL.
export function createLayoutStep(section, { layout, parts, geometry, frames, store, createView }) {
  const $ = (selector) => section.querySelector(selector);
  const doc = section.ownerDocument;
  let view = null;

  // ---- the toolbar and its help
  const arrange = $('#btn-arrange');
  arrange.textContent = W.ARRANGE;
  arrange.title = W.ARRANGE_TIP;
  arrange.addEventListener('click', () => layout.arrange());
  const orient = $('#btn-orient');
  orient.textContent = W.AUTO_ORIENT;
  orient.title = W.AUTO_ORIENT_TIP;
  orient.addEventListener('click', () => layout.autoOrient());
  const helpButton = $('#btn-layout-help');
  const help = $('#layout-help');
  helpButton.title = W.HELP;
  helpButton.setAttribute('aria-label', W.HELP);
  help.setAttribute('aria-label', W.HELP);
  $('#layout-gestures').textContent = W.GESTURES;
  $('#layout-more').replaceChildren(...W.MORE_GESTURES.map((t) => el('li', null, t)));
  const closeHelp = () => { help.hidden = true; helpButton.setAttribute('aria-expanded', 'false'); };
  helpButton.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = help.hidden;
    help.hidden = !open;
    helpButton.setAttribute('aria-expanded', String(open));
  });
  help.addEventListener('click', (e) => e.stopPropagation());
  doc.addEventListener('click', closeHelp);
  doc.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !help.hidden) { closeHelp(); helpButton.focus(); } });

  // ---- the view's buttons
  const buttons = [['#btn-view', W.VIEW_FIT, W.VIEW_FIT_TIP, () => view?.zoomToInstances()],
    ['#btn-view-plate', W.VIEW_PLATE, W.VIEW_PLATE_TIP, () => view?.viewPlate()],
    ['#btn-top', W.VIEW_TOP, W.VIEW_TOP_TIP, () => view?.topView()]];
  for (const [selector, text, title, run] of buttons) {
    const b = $(selector);
    b.textContent = text;
    b.title = title;
    b.addEventListener('click', run);
  }

  // ---- the status line: a click on a red one scrolls to the messages
  const alert = $('#layout-alert');
  alert.addEventListener('click', () => $('#layout-errors').scrollIntoView({ block: 'start' }));

  // A part's colour on the plate is its colour on the Parts step: by its place in the list.
  const colourOf = (key) => {
    const n = parts.rows().findIndex((r) => r.key === key);
    return PART_COLOURS[(n < 0 ? 0 : n) % PART_COLOURS.length];
  };

  function ensureView() {
    if (view || !createView) return;
    view = createView($('#layout-view'), { layout, geometry, frames, colourOf });
  }

  function drawStatus(m) {
    alert.replaceChildren();
    alert.classList.toggle('ok', m.status.ok);
    alert.disabled = m.status.ok;
    alert.append(el('span', 'first', m.status.first));
    alert.title = m.status.ok ? '' : m.status.first;
    if (!m.status.ok) alert.append(el('span', 'more', m.status.more));
  }

  function drawSelection(m) {
    const box = $('#layout-selection');
    $('#layout-selrow').classList.toggle('has-sel', m.selected.length > 0);
    box.replaceChildren();
    if (m.selection.strong) box.append(el('strong', null, m.selection.strong));
    box.append(doc.createTextNode(m.selection.text));
    const link = $('#layout-orient');
    link.replaceChildren();
    link.hidden = !m.link;
    if (m.link) {
      const b = el('button', 'linkish', m.link.label);
      b.type = 'button';
      b.addEventListener('click', () => m.link.run());
      link.append(b);
    }
  }

  function drawMessages(m) {
    const box = $('#layout-errors');
    const out = [];
    const selecting = (node, ids) => {
      if (!ids || !ids.length) return node;
      node.classList.add('clickable');
      // a click on a message selects the instances it names
      node.addEventListener('click', () => layout.select(ids, 'set'));
      return node;
    };
    const act = (a) => ({ label: a.label, onClick: (e) => { e.stopPropagation(); a.run(); } });
    for (const note of m.notes) {
      out.push(selecting(message({ kind: note.kind, what: note.what, todo: note.todo, actions: (note.actions || []).map(act) }), note.kind === 'ok' ? null : note.instances));
    }
    if (m.problems.length) {
      out.push(el('div', 'hint fix-first', W.FIX_THESE(m.problems.length)));
      for (const p of m.problems) {
        out.push(selecting(message({ kind: 'error', what: p.what, todo: p.todo, actions: p.action ? [act(p.action)] : [] }), p.instances));
      }
    }
    box.replaceChildren(...out);
  }

  function draw() {
    const m = layout.model();
    drawStatus(m);
    drawSelection(m);
    drawMessages(m);
    $('#layout-info').textContent = m.figures;
  }

  layout.subscribe(() => { if (store.get().step === 'layout') draw(); });
  store.subscribe((state, before) => {
    if (state.step === 'layout' && before.step !== 'layout') {
      ensureView();
      draw();
      view?.resize();
      view?.sync();
    }
    if (state.step !== 'layout' && before.step === 'layout') closeHelp();
  });
  if (store.get().step === 'layout') { ensureView(); draw(); }

  return { view: () => view, draw };
}
