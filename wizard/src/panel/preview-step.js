// The Preview step's drawing (wizard/README-details.md, "The slicing card", "No room to wait", "When
// a slice fails", "The result", "A sliced plate that expires"), into the mockup's markup of the step:
// the slicing card (#slice-card: the ring gauge, the percentage and the stage, the times, the bar,
// the list of stages, the connection line and the line under the card), the messages
// (#preview-errors: no room to wait, a failure, the expired message) and, once the plate is sliced,
// the result (#preview-result): the print time and filament large, the quiet line, the warnings in
// amber, the layer preview in #viewer-container with the colour key at its top left, and under it
// the readout with its two buttons, Reset view and the "?". Its behaviour is slicing.js's and
// result.js's; this module draws their models and passes on the buttons. Every sentence is set as
// text, never as markup. While the card shows, it is drawn again each second, for the times on it.
//
// The layer preview is made when the Preview step is in sight with a sliced plate, and kept while
// that plate stays sliced, so that coming back to the step finds it drawn; a new slice, a failure
// or the expiry lets it go. Its sliced file is fetched for it and never stored.
import * as R from '../result-sentences.js';
import * as T from '../slicing-sentences.js';
import { el, message } from './telling.js';
import { readout } from '../preview/layer-bar.js';

const RING = 2 * Math.PI * 27;          // the gauge's circle, r = 27 in the mockup's 64 by 64
// The preview's own failure that a new slice can mend.
const UNREADABLE = 'wizard.preview_unreadable';
// Whether the preview's own failure of this code offers Slice again: only the one a new slice can mend.
export const offersSliceAgain = (code) => code === UNREADABLE;

// createPreviewStep(section, {slicing, store, clock, result, createView, frames}):
//   result      result.js: the result's figures, the sliced file and the ghost
//   createView(element, {onLayer, onProgress, onFailure})  the layer preview (panel/layer-preview.js)
//   frames      the frame seam: the moment the step opened, from which the first layer is timed
export function createPreviewStep(section, { slicing, store, clock, result = null, createView = null, frames = null }) {
  const $ = (selector) => section.querySelector(selector);
  const cardBox = $('#slice-card');
  const errors = $('#preview-errors');
  const resultBox = $('#preview-result');
  const fill = $('#g-fill');
  const layers = [...section.querySelectorAll('#g-layers rect')];
  const word = section.querySelector('.slice-word');
  const sep = section.querySelector('.slice-sep');
  section.querySelector('.slice-actions .hint').textContent = T.SLICING_GOES_ON;
  fill.style.strokeDasharray = String(RING);
  let tick = null;
  let shownMessage = null;

  // ---- the result's controls, their words set once
  const container = $('#viewer-container');
  const viewBox = $('.preview-view-box');
  const viewMessage = $('.preview-view-message');
  const warnings = $('.result-warnings');
  const readoutBox = $('#layer-readout');
  const down = $('#btn-layer-down');
  const up = $('#btn-layer-up');
  const reset = $('#btn-preview-view');
  const keyButton = $('#btn-key');
  const key = $('#pv-key');
  const helpButton = $('#btn-preview-help');
  const help = $('#preview-help');
  down.setAttribute('aria-label', R.LAYER_DOWN);
  up.setAttribute('aria-label', R.LAYER_UP);
  reset.textContent = R.RESET_VIEW;
  keyButton.setAttribute('aria-label', R.KEY_LABEL);
  keyButton.title = R.KEY_LABEL;
  key.setAttribute('aria-label', R.KEY_LABEL);
  key.replaceChildren(...R.KEY.map((k) => {
    const row = el('li');
    const stripe = el('i');
    stripe.style.background = k.colour;
    row.append(stripe, el('span', null, k.label));
    return row;
  }));
  helpButton.setAttribute('aria-label', R.HELP_LABEL);
  helpButton.title = R.HELP_LABEL;
  help.setAttribute('aria-label', R.HELP_LABEL);
  help.querySelector('p').textContent = R.HELP;

  // The colour key and the "?" each open from their icon and close on a click elsewhere or Escape;
  // a press on them is never a turn of the view.
  const setKey = (open) => { key.hidden = !open; keyButton.setAttribute('aria-expanded', String(open)); };
  const setHelp = (open) => { help.hidden = !open; helpButton.setAttribute('aria-expanded', String(open)); };
  keyButton.addEventListener('click', (e) => { e.stopPropagation(); setKey(key.hidden); });
  for (const node of [keyButton, key]) node.addEventListener('pointerdown', (e) => e.stopPropagation());
  key.addEventListener('click', (e) => e.stopPropagation());
  helpButton.addEventListener('click', (e) => { e.stopPropagation(); setHelp(help.hidden); });
  help.addEventListener('click', (e) => e.stopPropagation());
  const doc = section.ownerDocument;
  doc.addEventListener('click', () => { setKey(false); setHelp(false); });
  doc.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!key.hidden) { setKey(false); keyButton.focus(); }
    if (!help.hidden) { setHelp(false); helpButton.focus(); }
  });

  // ---- the layer preview
  let shown = null;          // {slice, view, ready}
  let openedAt = frames ? frames.now() : 0;
  const controls = (on) => { for (const b of [down, up, reset]) b.disabled = !on; };
  // The readout is a polite live region for the layer; while the file is read it says so with a
  // percentage that moves, which it holds back from a screen reader by being busy.
  const reading = (on) => readoutBox.setAttribute('aria-busy', String(on));
  function dropView() {
    if (!shown) return;
    shown.view.destroy();
    shown = null;
    controls(false);
    reading(false);
    readoutBox.textContent = '';
    viewMessage.replaceChildren();
    viewBox.hidden = false;
    setKey(false);
  }
  // The preview's own failure, in place of the view: an amber message, since the plate is sliced
  // and Next stays on; Slice again where a new slice can mend it.
  function viewFailed(error) {
    controls(false);
    viewBox.hidden = true;
    reading(false);
    readoutBox.textContent = '';
    const actions = offersSliceAgain(error.code) ? [{ label: T.SLICE_AGAIN, primary: true, onClick: () => slicing.sliceAgain() }] : [];
    viewMessage.replaceChildren(message({ kind: 'warn', what: error.message, todo: error.remedy, actions }));
  }
  async function startView(slice) {
    const mine = {
      slice, ready: false,
      view: createView(container, {
        onLayer: ({ index, layers: total, z }) => { readoutBox.textContent = readout(index, total, z); },
        onProgress: ({ fraction }) => { if (!mine.ready) readoutBox.textContent = R.READING(fraction); },
        onFailure: (error) => { if (shown === mine) viewFailed(error); },
      }),
    };
    shown = mine;
    reading(true);
    readoutBox.textContent = R.READING(null);
    const got = await result.file();
    if (shown !== mine) return;
    if (!got.ok) {
      if (got.report) viewFailed(got.report);
      return;              // expired or no longer this plate: slicing.js has changed the step
    }
    const answer = await mine.view.show(got.bytes, result.ghost(), { since: openedAt });
    if (shown !== mine) return;
    if (answer.ok) { mine.ready = true; controls(true); reading(false); }
    else if (answer.error) viewFailed(answer.error);
  }
  down.addEventListener('click', () => { if (shown) shown.view.stepLayer(-1); });
  up.addEventListener('click', () => { if (shown) shown.view.stepLayer(1); });
  reset.addEventListener('click', () => { if (shown) shown.view.resetView(); });

  function drawResult(m) {
    const r = result.preview();
    const stats = $('#preview-stats');
    if (!r) { stats.replaceChildren(); warnings.hidden = true; return; }
    stats.replaceChildren(...r.stats.map((s) => {
      const box = el('div', 'stat');
      box.append(el('strong', null, s.value), doc.createTextNode(s.label));
      return box;
    }), ...(r.line ? [el('div', 'stat-line', r.line)] : []));
    warnings.replaceChildren(...r.warnings.map((w) => el('li', null, w)));
    warnings.hidden = r.warnings.length === 0;
    if (createView && store.get().step === 'preview' && (!shown || shown.slice !== m.slice)) {
      dropView();
      startView(m.slice);
    }
  }

  function drawCard(c) {
    cardBox.classList.toggle('stalled', c.stalled);
    $('#slice-pct').textContent = c.pct;
    $('#slice-stage').textContent = c.stage;
    $('#slice-elapsed').textContent = c.elapsed;
    word.textContent = c.elapsedWord;
    sep.hidden = !c.left;
    const left = $('#slice-expected');
    left.textContent = c.left;
    left.className = c.late || c.stalled ? 'late' : '';
    fill.style.strokeDashoffset = String(RING * (1 - c.fraction));
    $('#slice-bar-fill').style.width = `${(c.fraction * 100).toFixed(1)}%`;
    layers.forEach((rect, i) => rect.classList.toggle('on', i < c.litLayers));
    const list = $('#slice-stages');
    const items = c.stages.map((s) => el('li', s.state || null, s.label));
    list.replaceChildren(...items);
    const now = list.querySelector('li.now');
    if (now) now.setAttribute('aria-current', 'step');
    const conn = $('#slice-conn');
    conn.hidden = !c.conn;
    conn.className = c.conn ? `conn ${c.conn.kind}` : 'conn';
    conn.textContent = c.conn ? c.conn.text : '';
  }

  // A message is drawn again only when what it says changes, so that a button keeps its focus.
  function drawMessage(m, kind) {
    const key2 = JSON.stringify([kind, m.what, m.todo, m.details, m.actions.map((a) => a.label)]);
    if (key2 === shownMessage && errors.firstChild) return;
    shownMessage = key2;
    errors.replaceChildren(message({
      kind, what: m.what, todo: m.todo, details: m.details ?? null,
      actions: m.actions.map((a) => ({ label: a.label, primary: a.primary, onClick: () => a.run() })),
    }));
  }

  function draw() {
    if (tick !== null) { clock.cancel(tick); tick = null; }
    const m = slicing.model();
    cardBox.hidden = m.kind !== 'card';
    resultBox.hidden = m.kind !== 'done';
    if (m.kind !== 'busy' && m.kind !== 'failed' && m.kind !== 'expired') { errors.replaceChildren(); shownMessage = null; }
    if (m.kind === 'card') drawCard(m.card);
    else if (m.kind === 'busy') drawMessage(m, 'warn');
    else if (m.kind === 'failed') drawMessage(m, 'error');
    else if (m.kind === 'expired') drawMessage(m, 'info');
    if (m.kind === 'done' && result) drawResult(m);
    else dropView();
    // the times on the card move each second while it is in sight
    if (m.kind === 'card' && store.get().step === 'preview') {
      tick = clock.after(1000, draw);
    }
  }

  slicing.subscribe(draw);
  store.subscribe((state, before) => {
    if (state.step === before.step) return;
    if (state.step === 'preview' && frames) openedAt = frames.now();
    if (before.step === 'preview') { setKey(false); setHelp(false); }
    draw();
  });
  draw();
  return { draw, view: () => (shown ? shown.view : null) };
}
