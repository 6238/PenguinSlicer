// The six ways the panel tells the user something (wizard/README-details.md, "How the panel
// tells the user something"), one builder each, so that each kind of news always looks the
// same. Every sentence is set as text, never as markup: a part's name, a group's name and an
// error report's sentences are hostile until shown. Their look is the mockup's css/panel.css;
// the confirmation, which the mockup never drew, is in css/wizard.css.
//   notification   a card at the top of a step, under the plate summary, closed with ×
//   message        a block in a step's body: what happened, what to do, its buttons, its Details
//   card           a white bordered box holding a state for as long as it lasts
//   joined box     a small box joined to the header element or icon it belongs to
//   line           one short sentence in a fixed place
//   confirmation   a small box joined to the pressed control: a question, go ahead or keep
import { CLOSE_NOTIFICATION } from '../sentences.js';

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function button(label, className, onClick) {
  const b = el('button', className, label);
  b.type = 'button';
  if (onClick) b.addEventListener('click', onClick);
  return b;
}

// A notification: kind 'info', 'ok', 'warn' or 'error' (the colour of its left edge).
export function notification({ kind = 'info', what, todo, onClose }) {
  const box = el('div', `notice ${kind}`);
  const body = el('div', 'n-body');
  body.append(el('div', 'n-what', what));
  if (todo) body.append(el('div', 'n-todo', todo));
  const close = button('×', 'n-x', onClose);
  close.setAttribute('aria-label', CLOSE_NOTIFICATION);
  box.append(body, close);
  return box;
}

// A message: kind 'error' (red, it holds Next), 'warn' (amber, a caution), 'info' (it only
// informs) or 'ok' (green, something was done). `actions` are [{label, primary, onClick}];
// `details` is the folded part, opened by the word "Details".
export function message({ kind = 'info', what, todo, actions = [], details }) {
  const box = el('div', `msg ${kind}`);
  box.append(el('div', 'what', what));
  if (todo) box.append(el('div', 'todo', todo));
  if (actions.length) {
    const row = el('div', 'acts');
    for (const action of actions) row.append(button(action.label, `btn small${action.primary ? ' primary' : ''}`, action.onClick));
    box.append(row);
  }
  if (details) {
    const folded = el('details');
    folded.append(el('summary', null, 'Details'), el('div', null, details));
    box.append(folded);
  }
  return box;
}

// A card: its content a sentence or nodes.
export function card(...content) {
  const box = el('div', 'card');
  box.append(...content);
  return box;
}

// A line: one short sentence.
export function line(text) {
  return el('p', 'hint', text);
}

// Opens a joined box: `box` shown under `anchor`, its left edge on the anchor's, kept inside
// `within` (the positioned element both sit in); closed by a click elsewhere, Escape, or
// `close()`. `onClose` is told once, however it closes.
export function joinedBox({ anchor, box, within, width = 380, onClose }) {
  const place = () => {
    const outer = within.getBoundingClientRect();
    const a = anchor.getBoundingClientRect();
    const w = Math.min(outer.width, width);
    box.style.top = `${a.bottom - outer.top - 1}px`;
    box.style.width = `${w}px`;
    const left = a.left - outer.left;
    if (left + w > outer.width) {
      box.style.left = `${Math.max(0, outer.width - w)}px`;
      box.classList.add('shifted');
    } else {
      box.style.left = `${left}px`;
      box.classList.remove('shifted');
    }
  };
  let open = true;
  const close = () => {
    if (!open) return;
    open = false;
    box.hidden = true;
    document.removeEventListener('click', outside, true);
    document.removeEventListener('keydown', escape, true);
    window.removeEventListener('resize', place);
    if (onClose) onClose();
  };
  const outside = (event) => { if (!box.contains(event.target) && !anchor.contains(event.target)) close(); };
  const escape = (event) => { if (event.key === 'Escape') close(); };
  box.hidden = false;
  place();
  document.addEventListener('click', outside, true);
  document.addEventListener('keydown', escape, true);
  window.addEventListener('resize', place);
  return { close, place, isOpen: () => open };
}

// A confirmation joined to `anchor`, inside the panel `root`: resolves true when the user goes
// ahead, false when they keep things (its button, Escape, or a click elsewhere). It is under its
// control, or above it where the panel ends below.
export function confirmation(root, anchor, { question, go, keep }) {
  return new Promise((resolve) => {
    const box = el('div', 'confirm-pop');
    box.setAttribute('role', 'alertdialog');
    const text = el('p', null, question);
    const row = el('div', 'acts');
    let done = false;
    const finish = (answer) => {
      if (done) return;
      done = true;
      document.removeEventListener('click', outside, true);
      document.removeEventListener('keydown', escape, true);
      box.remove();
      resolve(answer);
    };
    const outside = (event) => { if (!box.contains(event.target) && !anchor.contains(event.target)) finish(false); };
    const escape = (event) => { if (event.key === 'Escape') { event.stopPropagation(); finish(false); } };
    row.append(button(keep, 'btn small', () => finish(false)), button(go, 'btn small primary', () => finish(true)));
    box.append(text, row);
    root.append(box);
    const outer = root.getBoundingClientRect();
    const a = anchor.getBoundingClientRect();
    const width = Math.min(outer.width - 12, 300);
    box.style.width = `${width}px`;
    box.style.left = `${Math.max(6, Math.min(a.left - outer.left, outer.width - width - 6))}px`;
    box.style.top = `${a.bottom - outer.top + 4}px`;
    // a control near the panel's foot (New plate under a long list) gets its question above it,
    // so that the box never reaches past the panel
    const height = box.getBoundingClientRect().height;
    if (a.bottom + 4 + height > outer.bottom - 6 && a.top - 4 - height >= outer.top + 6) {
      box.style.top = `${a.top - outer.top - 4 - height}px`;
    }
    document.addEventListener('click', outside, true);
    document.addEventListener('keydown', escape, true);
    box.querySelector('.btn').focus();
  });
}
