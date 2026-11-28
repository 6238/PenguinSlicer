// The Parts step's drawing (wizard/README-details.md, "The Parts step"), into the mockup's markup
// of the step (#parts-upload with #dropzone and #upload-units, #parts-list, #parts-total) and the
// New plate button the guide adds. Its behaviour is parts.js's; this module draws its rows and
// passes on what the user does. Every name and sentence is set as text, never as markup.
//   - The upload area: a drop, a click or Enter or Space on it, which opens the file chooser.
//   - The switch "Read STL files in: inches / millimetres", two radio buttons.
//   - One row for each part: its picture, name, size in its own units, quantity and remove
//     button; while it arrives, a thin bar and "Uploading…", or "Taking longer than usual; still
//     trying…" once its upload is slow; under it, each warning in amber, and the amber line of a
//     part the browser could not save.
//   - Under the list, the line counting the plate, and the red message past 150 instances.
//   - New plate, shown while the plate holds parts, which asks first.
import { MAX_INSTANCES } from '../geometry/constants.js';
import { partColour, partPicture } from '../part-picture.js';
import {
  INSTANCES_OF, KEEP_PLATE, NEW_PLATE, NEW_PLATE_QUESTION, NO_PARTS, PARTS_LINE, PART_NOT_SAVED, READ_STL_IN,
  REMOVE_PART, ROW_SLOW, SIZE_TIP, UNIT_WORDS, UPLOADING, UPLOAD_PROMPT,
} from '../sentences.js';
import { formatSize } from '../units.js';
import { el, message } from './telling.js';

// A warning's sentences as a message's two lines: the first sentence, and the rest, the words
// unchanged. A sentence ends at a full stop, question or exclamation mark followed by a space and
// a capital letter, so that "e.g. on" or "i.e. 0.2 in" does not end one.
export function firstSentence(text) {
  const match = /^(.+?[.!?])\s+(\p{Lu}[\s\S]*)$/u.exec(text);
  return match ? [match[1], match[2]] : [text, null];
}

// createPartsStep(section, {parts, geometry, panel, window}) draws the step and keeps it drawn.
export function createPartsStep(section, { parts, geometry, panel, window: win = globalThis }) {
  const doc = section.ownerDocument;
  const $ = (selector) => section.querySelector(selector);
  const dropzone = $('#dropzone');
  const input = $('#f-upload');
  const list = $('#parts-list');
  const total = $('#parts-total');
  const newPlate = $('.new-plate .btn');
  const items = new Map();            // key: its <li>
  const pictures = new Map();         // "key colour": a canvas, or a promise of one

  dropzone.querySelector('p').textContent = UPLOAD_PROMPT;
  newPlate.textContent = NEW_PLATE;

  // ---- the switch
  const units = $('#upload-units');
  units.append(doc.createTextNode(`${READ_STL_IN} `));
  const radios = {};
  ['in', 'mm'].forEach((value, i) => {
    if (i) units.append(doc.createTextNode(' / '));
    const label = el('label');
    const radio = el('input');
    radio.type = 'radio';
    radio.name = 'upload-units';
    radio.value = value;
    radio.addEventListener('change', () => { if (radio.checked) parts.setUnits(value); });
    label.append(radio, doc.createTextNode(` ${UNIT_WORDS[value]}`));
    units.append(label);
    radios[value] = radio;
  });

  // ---- adding files: handed over as the browser gives them; parts.js checks each one's size and
  // reads it in its turn, refusing alone a file it cannot read
  function add(files) {
    const chosen = Array.from(files);
    if (chosen.length) parts.addFiles(chosen);
  }
  dropzone.addEventListener('click', () => input.click());
  dropzone.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); input.click(); }
  });
  input.addEventListener('change', () => {
    const files = Array.from(input.files);
    input.value = '';
    add(files);
  });
  for (const name of ['dragenter', 'dragover']) {
    dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.add('drag'); });
  }
  for (const name of ['dragleave', 'drop']) {
    dropzone.addEventListener(name, (event) => { event.preventDefault(); dropzone.classList.remove('drag'); });
  }
  dropzone.addEventListener('drop', (event) => {
    if (event.dataTransfer && event.dataTransfer.files.length) add(event.dataTransfer.files);
  });

  // Shown only while the plate holds parts, so it always asks first.
  newPlate.addEventListener('click', async () => {
    const go = await panel.tell.confirm(newPlate, { question: NEW_PLATE_QUESTION, go: NEW_PLATE, keep: KEEP_PLATE });
    if (go) await parts.newPlate();
  });

  // ---- a row
  function picture(row, index, holder) {
    const id = `${row.key} ${partColour(index)}`;
    const ready = pictures.get(id);
    if (ready instanceof win.HTMLCanvasElement) { holder.replaceChildren(ready); return; }
    if (ready) return;
    pictures.set(id, partPicture({ geometry, key: row.key, colour: partColour(index), pixelRatio: win.devicePixelRatio, document: doc })
      .then((answer) => {
        if (!answer.ok) { pictures.delete(id); return; }
        pictures.set(id, answer.canvas);
        draw();
      }));
  }

  function makeItem(row) {
    const li = el('li', 'part-item');
    li.dataset.part = row.key;
    const line = el('div', 'row');
    const thumb = el('div', 'thumb-holder');
    const meta = el('div', 'meta');
    const name = el('div', 'name');
    const dims = el('div', 'dims');
    const bar = el('div', 'arrive-bar');
    bar.append(el('div'));
    meta.append(name, dims, bar);
    const qty = el('input', 'part-qty');
    qty.type = 'number';
    qty.min = '1';
    qty.max = String(MAX_INSTANCES);
    qty.step = '1';
    // never typed past 150: the figure is held at 150 as it is typed
    qty.addEventListener('input', () => { if (Number(qty.value) > MAX_INSTANCES) qty.value = String(MAX_INSTANCES); });
    qty.addEventListener('change', () => { parts.setQuantity(row.key, qty.value); });
    const remove = el('button', 'remove', '×');
    remove.type = 'button';
    remove.addEventListener('click', () => { parts.remove(row.key); });
    line.append(thumb, meta, qty, remove);
    const sub = el('div', 'sub');
    li.append(line, sub);
    return li;
  }

  function fill(li, row, index) {
    li.classList.toggle('arriving', row.arriving);
    const thumb = li.querySelector('.thumb-holder');
    if (row.drawn) picture(row, index, thumb);
    if (!thumb.firstChild) thumb.replaceChildren(el('div', 'thumb'));
    const name = li.querySelector('.name');
    name.textContent = row.name;
    name.title = row.name;
    const dims = li.querySelector('.dims');
    dims.classList.toggle('slow', row.arriving && row.slow);
    if (row.arriving) {
      dims.textContent = row.slow ? ROW_SLOW : UPLOADING;
      dims.removeAttribute('title');
      delete dims.dataset.tip;          // the panel's own tooltip, which a title becomes
    } else {
      dims.textContent = formatSize(row.record.measurements.size_mm, row.units);
      dims.title = SIZE_TIP(row.units);
    }
    li.querySelector('.arrive-bar').hidden = !row.arriving;
    const qty = li.querySelector('.part-qty');
    if (doc.activeElement !== qty || qty.value === '') qty.value = String(row.quantity);
    qty.disabled = row.arriving;
    qty.setAttribute('aria-label', INSTANCES_OF(row.name));
    const remove = li.querySelector('.remove');
    remove.setAttribute('aria-label', REMOVE_PART(row.name));
    remove.title = REMOVE_PART(row.name);
    const sub = li.querySelector('.sub');
    const notes = [];
    for (const warning of row.arriving ? [] : row.warnings) {
      const [what, todo] = firstSentence(warning.message);
      notes.push(message({ kind: 'warn', what, todo }));
    }
    if (!row.saved) notes.push(el('p', 'hint not-saved', PART_NOT_SAVED));
    sub.replaceChildren(...notes);
    sub.hidden = notes.length === 0;
  }

  function draw() {
    const rows = parts.rows();
    const keys = new Set(rows.map((r) => r.key));
    for (const [key, li] of items) if (!keys.has(key)) { li.remove(); items.delete(key); }
    for (const id of pictures.keys()) if (!keys.has(id.split(' ')[0])) pictures.delete(id);
    rows.forEach((row, index) => {
      let li = items.get(row.key);
      if (!li) { li = makeItem(row); items.set(row.key, li); }
      fill(li, row, index);
      if (list.children[index] !== li) list.insertBefore(li, list.children[index] ?? null);
    });
    const arrived = rows.filter((r) => !r.arriving);
    total.replaceChildren(doc.createTextNode(rows.length
      ? PARTS_LINE(arrived.length, arrived.reduce((n, r) => n + r.quantity, 0), rows.length - arrived.length)
      : NO_PARTS));
    const problem = parts.instanceProblem();
    if (problem) total.append(message({ kind: 'error', what: problem.message, todo: problem.remedy }));
    for (const [value, radio] of Object.entries(radios)) radio.checked = parts.units() === value;
    // New plate empties a plate that holds parts; an empty plate has nothing to empty
    newPlate.parentElement.hidden = rows.length === 0;
  }

  parts.subscribe(draw);
  draw();
  return { draw };
}
