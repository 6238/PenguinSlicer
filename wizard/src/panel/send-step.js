// The Send step in phase 2 (wizard/README-details.md, "The Send step"), into the mockup's markup of
// the step: the card of what will be printed (#send-summary: the instances by part, the print time
// and the grams, and no printer's name), the expired message in place of Send (#send-printer, where
// the printer's messages go from phase 5) and a refused Download's message (#send-errors); and the
// footer's one button, Download the sliced file (#btn-do), which the panel shows on this step and
// hides while the expired message shows. No plate-clear line, no caret, no printer-status icon and
// nothing about pairing: those come with the printer in phase 5. Every sentence is set as text.
import * as R from '../result-sentences.js';
import { el, message } from './telling.js';

// createSendStep(section, {slicing, result, store, root}): `root` is the panel, which holds the
// footer's button.
export function createSendStep(section, { slicing, result, store, root }) {
  const $ = (selector) => section.querySelector(selector);
  const summary = $('#send-summary');
  const printer = $('#send-printer');
  const errors = $('#send-errors');
  const button = root.querySelector('#btn-do');
  button.textContent = R.DOWNLOAD;
  // the button is busy (aria-busy, the progress pointer) while a Download asks its details
  const setBusy = (on) => { busy = on; button.setAttribute('aria-busy', String(on)); };
  let card = null;             // {slice, model}: the card of the sliced plate, kept through its expiry
  let refused = null;           // {slice, report}: a Download refused, shown until the plate changes
  let busy = false;
  button.setAttribute('aria-busy', 'false');

  function dl(grid, term, ...content) {
    grid.append(el('dt', null, term));
    const dd = el('dd');
    dd.append(...content);
    grid.append(dd);
  }

  function drawCard(c) {
    const box = el('div', 'card');
    const grid = el('dl', 'send-sum');
    const list = el('ul');
    list.append(...c.parts.map((p) => el('li', null, p)));
    dl(grid, R.SEND_INSTANCES, el('div', 'big', c.count), list);
    if (c.printTime) dl(grid, R.PRINT_TIME, el('span', 'big', c.printTime));
    if (c.grams) dl(grid, R.FILAMENT, el('span', 'big', c.grams), section.ownerDocument.createTextNode(c.filament));
    box.append(grid);
    summary.replaceChildren(box);
  }

  function draw() {
    const m = slicing.model();
    if (m.kind === 'done') {
      const model = result.send();
      if (model) card = { slice: m.slice, model };
    } else if (m.kind !== 'expired') card = null;
    if (card) drawCard(card.model); else summary.replaceChildren();
    if (m.kind === 'expired') {
      printer.replaceChildren(message({
        kind: 'info', what: m.what, todo: m.todo,
        actions: m.actions.map((a) => ({ label: a.label, primary: a.primary, onClick: () => a.run() })),
      }));
    } else printer.replaceChildren();
    // the message of a refused Download stays until the plate is no longer this sliced plate: a
    // changed plate reaches this step only through a new slice, which leaves `done` first
    if (refused && (m.kind !== 'done' || refused.slice !== m.slice)) refused = null;
    errors.replaceChildren(...(refused ? [message({ kind: 'error', what: refused.report.message, todo: refused.report.remedy })] : []));
  }

  button.addEventListener('click', async () => {
    if (busy || store.get().step !== 'send') return;
    setBusy(true);
    const slice = result.slice();
    try {
      const outcome = await result.download();
      refused = outcome.report ? { slice, report: outcome.report } : null;
    } finally {
      setBusy(false);
      draw();
    }
  });

  slicing.subscribe(draw);
  store.subscribe((state, before) => { if (state.step !== before.step) draw(); });
  draw();
  return { draw };
}
