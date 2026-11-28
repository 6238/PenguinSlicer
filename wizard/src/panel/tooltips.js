// The panel's own tooltip (decision 63): a white box at 14 px, shown after TOOLTIP_DELAY_MS of
// rest on its element and at once on keyboard focus of an icon or a step circle; gone on
// leave, press, Escape or loss of focus; under its element, or above it where the panel ends,
// at least TOOLTIP_EDGE_PX inside the panel. A tooltip says only what is not on screen: the
// caller's `wanted(element)` says whether it is (an element whose text shows in full has
// none). Touch shows none.
import { TOOLTIP_DELAY_MS, TOOLTIP_EDGE_PX } from '../page-constants.js';

// Where the tooltip goes, in the panel's own pixels: `panel` {width, height}; `element`
// {left, right, top, bottom} relative to the panel; `tip` {width, height}.
export function placeTooltip(panel, element, tip, gap = 6) {
  const edge = TOOLTIP_EDGE_PX;
  const centre = (element.left + element.right) / 2;
  const left = Math.max(edge, Math.min(centre - tip.width / 2, panel.width - tip.width - edge));
  let top = element.bottom + gap;
  if (top + tip.height > panel.height - edge) top = Math.max(edge, element.top - tip.height - gap);
  return { left, top };
}

// The timing, apart from the drawing: show(element) and hide() draw; wanted(element) says
// whether the element's tooltip says something not on screen.
//   rest(element)                 the pointer came to rest on it (not by touch)
//   left(element)                 the pointer left it
//   pressed()                     a pointer press anywhere
//   focused(element, {keyboard})  it took focus; at once only by keyboard, and not a field
//   blurred(element), escape()
export function createTooltips({ clock, show, hide, wanted }) {
  let pending = null;        // {element, timer}
  let current = null;

  function end() {
    if (pending) { clock.cancel(pending.timer); pending = null; }
    if (current) { current = null; hide(); }
  }

  function showNow(element) {
    if (!wanted(element)) return;
    current = element;
    show(element);
  }

  return {
    rest(element) {
      if (element === current || (pending && pending.element === element)) return;
      end();
      pending = { element, timer: clock.after(TOOLTIP_DELAY_MS, () => { pending = null; showNow(element); }) };
    },
    left(element) {
      if (element === current || (pending && pending.element === element)) end();
    },
    pressed: end,
    escape: end,
    focused(element, { keyboard }) {
      end();
      if (keyboard && !element.isField && !element.hasVisibleText) showNow(element);
    },
    blurred(element) {
      if (element === current) end();
    },
    current: () => current,
  };
}

// ---- in the page: every `title` in the panel becomes the panel's own tooltip, as the mockup
// does (decision 63), a title set later included. Options of an open menu keep the browser's.

const SKIP = 'option, canvas, .gl-view';
const letters = (s) => (s || '').toLowerCase().replace(/[^a-z]+/g, '');

function cutShort(node) {
  return [node, ...node.querySelectorAll('*')].some((x) => x.clientWidth > 0
    && (x.scrollWidth > x.clientWidth + 1 || x.scrollHeight > x.clientHeight + 1));
}

// Whether the tooltip says something not on screen: a step tab whose name shows has none, and
// one that repeats its element's own visible text shows only when that text is cut short.
function wantedInPage(node) {
  if (!node.isConnected || node.offsetParent === null) return false;
  if (node.matches('#stepbar li')) {
    const name = node.querySelector('.sn');
    if (name && name.offsetWidth > 0) return false;
  }
  const own = letters(node.innerText);
  const tip = letters(node.dataset.tip);
  if (!tip) return false;
  if (own && own.includes(tip)) return cutShort(node);
  return true;
}

export function bindTooltips(root, clock) {
  const tip = document.createElement('div');
  tip.className = 'wiz-tip';
  tip.id = 'wiz-tip';
  tip.setAttribute('role', 'tooltip');
  tip.hidden = true;
  root.append(tip);

  const adopt = (node) => {
    if (!node.hasAttribute || !node.hasAttribute('title') || node.matches(SKIP)) return;
    const text = node.getAttribute('title');
    node.removeAttribute('title');
    if (text) node.dataset.tip = text; else delete node.dataset.tip;
    // a screen reader still hears it, unless the element's name already says it
    const name = node.getAttribute('aria-label');
    if (text && !(name && letters(name).includes(letters(text)))) node.setAttribute('aria-description', text);
    else node.removeAttribute('aria-description');
  };

  const tips = createTooltips({
    clock,
    wanted: wantedInPage,
    show(node) {
      tip.textContent = node.dataset.tip;
      tip.hidden = false;
      tip.style.left = '0px';
      tip.style.top = '0px';
      const panel = root.getBoundingClientRect();
      const r = node.getBoundingClientRect();
      const at = placeTooltip({ width: panel.width, height: panel.height },
        { left: r.left - panel.left, right: r.right - panel.left, top: r.top - panel.top, bottom: r.bottom - panel.top },
        tip.getBoundingClientRect());
      tip.style.left = `${at.left}px`;
      tip.style.top = `${at.top}px`;
    },
    hide() { tip.hidden = true; },
  });

  root.querySelectorAll('[title]').forEach(adopt);
  new MutationObserver((changes) => {
    for (const change of changes) {
      if (change.type === 'attributes') { adopt(change.target); continue; }
      for (const node of change.addedNodes) {
        if (node.nodeType !== 1) continue;
        adopt(node);
        node.querySelectorAll('[title]').forEach(adopt);
      }
    }
  }).observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ['title'] });

  const target = (event) => (event.target.closest ? event.target.closest('[data-tip]') : null);
  root.addEventListener('pointerover', (event) => {
    if (event.pointerType === 'touch') return;
    const node = target(event);
    if (node) tips.rest(node);
  });
  root.addEventListener('pointerout', (event) => {
    const node = target(event);
    if (node && !(event.relatedTarget && node.contains(event.relatedTarget))) tips.left(node);
  });
  root.addEventListener('pointerdown', () => tips.pressed(), true);
  root.addEventListener('focusin', (event) => {
    const node = target(event);
    if (!node) return;
    node.isField = node.matches('select, input, textarea');
    node.hasVisibleText = Boolean(letters(node.innerText)) && !node.matches('#stepbar li');
    tips.focused(node, { keyboard: event.target.matches(':focus-visible') });
  });
  root.addEventListener('focusout', (event) => { const node = target(event); if (node) tips.blurred(node); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') tips.escape(); }, true);
  return tips;
}
