// The panel as a whole (wizard/README-details.md, "The panel as a whole"), drawn into the
// markup of index.html, which is the mockup's from #wizard down: the header (the name, the
// configuration line with its reload glyph, the step tabs, the panel line), the plate summary
// and its change details, the notifications, each step's body, and Back and Next. Every part is
// drawn from the store, so the panel shows one state.
import { createPanelLine } from './panel-line.js';
import { STEPS, heldBy, stepIndex } from './steps.js';
import { summaryModel } from './summary.js';
import { card, confirmation, el, joinedBox, line, message, notification } from './telling.js';
import { bindTooltips } from './tooltips.js';
import { MAX_INSTANCES } from '../geometry/constants.js';

// Why a step cannot be left, in the words of the panel line after "<Step> first: ", or null.
// The steps' own rules come with their steps; these are the ones the panel knows already.
export function whyNotLeave(step, state) {
  const { plate } = state;
  if (step === 'parts') {
    if (plate.parts === 0) return 'add a part.';
    if (plate.instances > MAX_INSTANCES) return `a plate holds up to ${MAX_INSTANCES} instances.`;
  }
  if (step === 'layout') {
    if (plate.instances === 0) return 'there are no instances.';
    if (state.layoutProblem) return state.layoutProblem;
  }
  if (step === 'preview' && !state.sliced) return 'the plate is not sliced yet.';
  return null;
}

export function createPanel(root, { api, clock, store }) {
  const $ = (selector) => root.querySelector(selector);
  const tabs = [...root.querySelectorAll('#stepbar li')];
  const why = (step) => whyNotLeave(step, store.get());
  const notices = [];
  let changeDetails = null;
  let reloadConfiguration = () => {};

  bindTooltips(root, clock);

  // ---- the panel line
  const lineBox = $('#step-why');
  const panelLine = createPanelLine({
    board: api.board,
    clock,
    show(content) {
      lineBox.replaceChildren();
      lineBox.classList.toggle('slow', content.kind === 'slow');
      lineBox.hidden = content.kind === 'none';
      if (content.kind === 'none') return;
      lineBox.append(document.createTextNode(content.kind === 'passing' ? content.text : `${content.text} `));
      if (content.kind === 'slow') {
        const retry = el('button', 'linkish', content.action);
        retry.type = 'button';
        retry.addEventListener('click', () => api.board.retryNow());
        lineBox.append(retry);
      } else if (content.kind === 'unreachable') {
        const again = el('button', 'btn small', content.action);
        again.type = 'button';
        again.addEventListener('click', () => api.board.tryAgain());
        lineBox.append(again);
      }
    },
  });
  // the user's next move ends the passing line; the click that held a tab is not that move
  let holding = false;
  const moved = () => { if (!holding) panelLine.moved(); };
  root.addEventListener('pointerdown', moved, true);
  root.addEventListener('keydown', moved, true);

  // ---- moving between steps
  function goTo(target) {
    const { step } = store.get();
    if (target === step) return;
    const held = heldBy(target, step, why);
    if (held) {
      holding = true;
      panelLine.held(held.text);
      queueMicrotask(() => { holding = false; });
      return;
    }
    store.set({ step: target });
  }
  for (const tab of tabs) {
    tab.addEventListener('click', () => goTo(tab.dataset.step));
    tab.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        holding = true;
        goTo(tab.dataset.step);
        queueMicrotask(() => { holding = false; });
      }
    });
  }
  $('#btn-next').addEventListener('click', () => {
    const i = stepIndex(store.get().step);
    if (i < STEPS.length - 1 && !why(STEPS[i].id)) store.set({ step: STEPS[i + 1].id });
  });
  $('#btn-back').addEventListener('click', () => {
    const i = stepIndex(store.get().step);
    if (i > 0) store.set({ step: STEPS[i - 1].id });
  });
  $('#config-refresh').addEventListener('click', (event) => { event.preventDefault(); reloadConfiguration(); });

  // ---- drawing
  function drawHeader(state) {
    $('#config-status').hidden = !state.configName;
    $('#config-name').textContent = state.configName ?? '';
    const current = stepIndex(state.step);
    tabs.forEach((tab, i) => {
      tab.classList.toggle('active', i === current);
      tab.classList.toggle('done', i < current);
      if (i === current) tab.setAttribute('aria-current', 'step'); else tab.removeAttribute('aria-current');
    });
  }

  function drawSteps(state) {
    for (const section of root.querySelectorAll('section.step')) section.hidden = section.dataset.step !== state.step;
    const last = state.step === STEPS[STEPS.length - 1].id;
    $('#btn-back').disabled = state.step === STEPS[0].id;
    $('#btn-next').hidden = last;
    $('#btn-next').disabled = Boolean(why(state.step));
    $('#final-action').hidden = !last;
    $('#wiz-nav').classList.toggle('on-send', last);
    $('#btn-do').disabled = !state.sliced;
  }

  function drawSummary(state) {
    const box = $('#wiz-summary');
    const model = state.plate.filament && state.plate.profile ? summaryModel(state.step, state.plate)
      : summaryModel(state.step, { ...state.plate, filament: '', profile: '' });
    box.replaceChildren();
    box.hidden = model === null;
    if (model === null) { if (changeDetails) changeDetails.close(); return; }
    box.append(el('div', 'sum-line', model.first));
    const second = el('div', 'sum-line sum-set');
    const text = el('span', 'sum-text', state.plate.filament ? model.second : '');
    if (state.plate.filament) text.title = model.secondFull;
    second.append(text);
    box.append(second);
    if (!model.pill) { if (changeDetails) changeDetails.close(); return; }
    const pill = el('button', 'chip adv chg-chip', model.pill.text);
    pill.type = 'button';
    pill.id = 'chg-chip';
    pill.title = model.pill.tip;
    pill.setAttribute('aria-controls', 'chg-pop');
    const open = Boolean(changeDetails && changeDetails.isOpen());
    pill.setAttribute('aria-expanded', String(open));
    pill.classList.toggle('open', open);
    pill.addEventListener('click', () => toggleChangeDetails(model.pill.lines));
    second.append(pill);
    if (open) fillChangeDetails(model.pill.lines, pill);
  }

  function fillChangeDetails(lines, pill) {
    const pop = $('#chg-pop');
    const list = el('ul');
    for (const text of lines) list.append(el('li', null, text));
    pop.replaceChildren(list);
    if (changeDetails) changeDetails.close();
    changeDetails = joinedBox({
      anchor: pill, box: pop, within: $('.summary-wrap'),
      onClose: () => {
        const chip = $('#chg-chip');
        if (chip) { chip.setAttribute('aria-expanded', 'false'); chip.classList.remove('open'); }
      },
    });
    pill.setAttribute('aria-expanded', 'true');
    pill.classList.add('open');
  }

  function toggleChangeDetails(lines) {
    if (changeDetails && changeDetails.isOpen()) { changeDetails.close(); return; }
    fillChangeDetails(lines, $('#chg-chip'));
  }

  function drawNotices() {
    $('#notices').replaceChildren(...notices.map((n) => notification({
      ...n, onClose: () => { dropNotice(n.key); },
    })));
  }

  function notify({ kind, what, todo, key }) {
    const id = key ?? `n${notices.length}-${what}`;
    const at = notices.findIndex((n) => n.key === id);
    if (at >= 0) notices.splice(at, 1);
    notices.push({ kind, what, todo, key: id });
    drawNotices();
  }

  function dropNotice(key) {
    const at = notices.findIndex((n) => n.key === key);
    if (at >= 0) { notices.splice(at, 1); drawNotices(); }
  }

  function draw(state, before) {
    if (before && before.step !== state.step) {
      notices.length = 0;                // a notification belongs to its step
      panelLine.moved();
      if (changeDetails) changeDetails.close();
      $('#wiz-body').scrollTop = 0;
    }
    drawHeader(state);
    drawSteps(state);
    drawSummary(state);
    drawNotices();
  }

  store.subscribe(draw);
  draw(store.get(), null);

  return {
    goTo,
    notify,
    dropNotice,
    onReloadConfiguration(listener) { reloadConfiguration = listener; },
    tell: {
      message, card, line,
      confirm: (anchor, spec) => confirmation(root, anchor, spec),
    },
  };
}
