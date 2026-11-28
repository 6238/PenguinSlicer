// The Preview step's drawing while a plate is submitted and sliced (wizard/README-details.md, "The
// slicing card", "No room to wait", "When a slice fails"), into the mockup's markup of the step:
// the slicing card (#slice-card: the ring gauge, the percentage and the stage, the times, the bar,
// the list of stages, the connection line and the line under the card), the messages
// (#preview-errors) and, once the plate is sliced, the place of the result (#preview-result). Its
// behaviour is slicing.js's; this module draws the model and passes on the buttons. Every sentence
// is set as text, never as markup. While the card shows, it is drawn again each second, for the
// times on it.
import * as T from '../slicing-sentences.js';
import { el, message } from './telling.js';

const RING = 2 * Math.PI * 27;          // the gauge's circle, r = 27 in the mockup's 64 by 64

export function createPreviewStep(section, { slicing, store, clock }) {
  const $ = (selector) => section.querySelector(selector);
  const cardBox = $('#slice-card');
  const errors = $('#preview-errors');
  const result = $('#preview-result');
  const fill = $('#g-fill');
  const layers = [...section.querySelectorAll('#g-layers rect')];
  const word = section.querySelector('.slice-word');
  const sep = section.querySelector('.slice-sep');
  section.querySelector('.slice-actions .hint').textContent = T.SLICING_GOES_ON;
  fill.style.strokeDasharray = String(RING);
  let tick = null;
  let shownMessage = null;

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
    conn.className = c.conn && c.conn.kind === 'back' ? 'conn back' : 'conn';
    conn.textContent = c.conn ? c.conn.text : '';
  }

  // A message is drawn again only when what it says changes, so that a button keeps its focus.
  function drawMessage(m, kind) {
    const key = JSON.stringify([kind, m.what, m.todo, m.details, m.actions.map((a) => a.label)]);
    if (key === shownMessage && errors.firstChild) return;
    shownMessage = key;
    errors.replaceChildren(message({
      kind, what: m.what, todo: m.todo, details: m.details ?? null,
      actions: m.actions.map((a) => ({ label: a.label, primary: a.primary, onClick: () => a.run() })),
    }));
  }

  function draw() {
    if (tick !== null) { clock.cancel(tick); tick = null; }
    const m = slicing.model();
    cardBox.hidden = m.kind !== 'card';
    result.hidden = m.kind !== 'done';
    if (m.kind !== 'busy' && m.kind !== 'failed') { errors.replaceChildren(); shownMessage = null; }
    if (m.kind === 'card') drawCard(m.card);
    else if (m.kind === 'busy') drawMessage(m, 'warn');
    else if (m.kind === 'failed') drawMessage(m, 'error');
    if (m.kind === 'done') result.replaceChildren(el('p', 'hint', m.text));
    else result.replaceChildren();
    // the times on the card move each second while it is in sight
    if (m.kind === 'card' && store.get().step === 'preview') {
      tick = clock.after(1000, draw);
    }
  }

  slicing.subscribe(draw);
  store.subscribe((state, before) => { if (state.step !== before.step) draw(); });
  draw();
  return { draw };
}
