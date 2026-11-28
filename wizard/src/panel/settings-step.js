// The Settings step's drawing and advanced mode's (wizard/README-details.md, "The Settings step",
// "Advanced mode"), into the mockup's markup: the step's #p-filament, #p-profile,
// #p-profile-clears, #p-overrides with its four menus, #adv-entry and #adv-effect, and #advanced.
// Their behaviour is settings.js's; this module draws them and passes on what the user does.
// Every name and sentence, Orca's words for a setting included, is set as text, never as markup.
//   - The Filament menu with the chosen filament's colour beside it; the Profile menu, each
//     profile's purpose its option's tooltip; the caution under it while there are changes.
//   - The four quick changes; then either the Advanced mode button alone or the changes box: its
//     heading, one line for each change, each a link that opens advanced mode at that setting,
//     and the Advanced mode button.
//   - Advanced mode, filling the panel: its header with Reset all, which asks first; below 480 px
//     of panel an accordion of the table's sections, from 480 px a rail of them; each section's
//     setting groups, each setting's control drawn from its kind; Back to Settings, the only way
//     out. What it covers is inert while it is open. Which sections and setting groups are closed
//     is kept here, in the page's memory only, for as long as the page is loaded.
import { formatValue } from '../settings.js';
import {
  ADVANCED_MODE, ADVANCED_SUB, ALSO_QUICK, CHANGED_COUNT, COLLAPSE_ALL, EXPAND_ALL, IN_SECTION, KEEP_CHANGES,
  OPEN_AT, PROFILE_PURPOSE, PROFILE_WAS, RESET, RESET_ALL, RESET_ALL_QUESTION, RESET_TO,
} from '../sentences.js';
import { changeLine } from './summary.js';
import { confirmation, el } from './telling.js';

export const ADVANCED_WIDE_PX = 480;          // from this width of panel, the rail of sections
const COVERED = ['#wiz-header', '#wiz-body', '#wiz-nav'];
const SVG = 'http://www.w3.org/2000/svg';
// The mockup's icons: a chevron, and the double chevrons of Expand all and Collapse all.
const CHEVRON = 'M8.59 16.59 13.17 12 8.59 7.41 10 6l6 6-6 6z';
const UNFOLD_MORE = 'M12 5.83 15.17 9l1.41-1.41L12 3 7.41 7.59 8.83 9zm0 12.34L8.83 15l-1.41 1.41L12 21l4.59-4.59L15.17 15z';
const UNFOLD_LESS = 'M7.41 18.59 8.83 20 12 16.83 15.17 20l1.41-1.41L12 14zm9.18-13.18L15.17 4 12 7.17 8.83 4 7.41 5.41 12 10z';
const COLOUR = /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i;

// A part of an id made from Orca's words for a section or a setting group.
export const idPart = (text) => String(text).replace(/[^A-Za-z0-9]+/g, '-');

function icon(doc, path) {
  const svg = doc.createElementNS(SVG, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  const p = doc.createElementNS(SVG, 'path');
  p.setAttribute('fill', 'currentColor');
  p.setAttribute('d', path);
  svg.append(p);
  return svg;
}

function chevron(doc, open) {
  const c = el('span', `chev${open ? ' open' : ''}`);
  c.append(icon(doc, CHEVRON));
  return c;
}

function fillSelect(select, options, value) {
  select.replaceChildren(...options.map((o) => {
    const option = el('option', null, o.text);
    option.value = o.value;
    if (o.title) option.title = o.title;
    return option;
  }));
  select.value = value ?? '';
}

// createSettingsStep({root, settings, store, window}) draws the step and advanced mode, and keeps
// them drawn. `root` is the panel, #wizard.
export function createSettingsStep({ root, settings, store, window: win = globalThis }) {
  const doc = root.ownerDocument;
  const $ = (selector) => root.querySelector(selector);
  const section = $('section.step[data-step="settings"]');
  const filamentMenu = $('#p-filament');
  const profileMenu = $('#p-profile');
  const caution = $('#p-profile-clears');
  const entry = $('#adv-entry');
  const box = $('#adv-effect');
  const advanced = $('#advanced');
  const body = $('#adv-body');
  const resetAll = $('#adv-reset-all');

  // ---- the Filament menu's colour: beside the chosen filament's name, inside the menu's box
  const pick = el('span', 'filament-pick');
  const swatch = el('span', 'filament-swatch');
  swatch.setAttribute('aria-hidden', 'true');
  filamentMenu.replaceWith(pick);
  pick.append(swatch, filamentMenu);

  filamentMenu.addEventListener('change', () => settings.chooseFilament(filamentMenu.value));
  profileMenu.addEventListener('change', () => settings.chooseProfile(profileMenu.value));
  for (const quick of settings.QUICK) {
    const menu = $(`#ov-${quick.id}`);
    menu.addEventListener('change', () => settings.setQuick(quick.id, menu.value));
  }
  $('#btn-advanced').addEventListener('click', () => open(null));

  function drawStep() {
    const filaments = settings.filaments();
    const { plate } = store.get();
    fillSelect(filamentMenu, filaments.map((f) => ({ value: f.name, text: f.name })), plate.filament);
    const colour = (filaments.find((f) => f.name === plate.filament) ?? {}).colour;
    swatch.hidden = !COLOUR.test(colour ?? '');
    pick.classList.toggle('has-colour', !swatch.hidden);
    if (!swatch.hidden) swatch.style.backgroundColor = colour;
    fillSelect(profileMenu, settings.profiles().map((p) => ({ value: p.name, text: p.name, title: p.purpose ? PROFILE_PURPOSE(p.purpose) : null })), plate.profile);

    const warning = settings.caution();
    caution.hidden = !warning;
    caution.replaceChildren();
    if (warning) {
      const mark = el('span', 'caution-icon', '⚠');
      mark.setAttribute('aria-hidden', 'true');
      caution.append(mark, doc.createTextNode(warning));
    }

    for (const quick of settings.quick()) {
      const menu = $(`#ov-${quick.id}`);
      fillSelect(menu, quick.entries, quick.chosen);
      menu.classList.toggle('changed', quick.changed);
      menu.title = quick.title;
    }

    const changes = store.get().plate.changes ?? [];
    entry.hidden = changes.length > 0;
    box.hidden = changes.length === 0;
    box.replaceChildren();
    if (changes.length) {
      box.append(el('strong', null, settings.boxTitle()));
      const list = el('ul');
      for (const change of changes) {
        const item = el('li');
        const link = el('button', 'linkish', changeLine(change));
        link.type = 'button';
        link.id = `chg-line-${change.name}`;
        const setting = settings.entry(change.name);
        link.title = OPEN_AT(setting ? setting.label : change.label);
        link.addEventListener('click', () => open(change.name));
        item.append(link);
        list.append(item);
      }
      const again = el('button', 'btn small', ADVANCED_MODE);
      again.type = 'button';
      again.id = 'adv-effect-btn';
      again.addEventListener('click', () => open(null));
      box.append(list, again);
    }
  }

  // ---- advanced mode
  const closedSections = new Map();     // section: false when the user closed it
  const closedGroups = new Map();       // "section|group": false when closed
  let railSection = null;               // the rail's chosen section
  let opener = null;                    // the setting whose line opened advanced mode, or null
  let target = null;                    // the setting to bring into sight when it opens
  let shown = false;
  let rows = new Map();                 // name: {row, input, entry}
  let counts = [];                      // [{node, test, rail}] the changed counts drawn

  const sectionOpen = (s) => closedSections.get(s) ?? true;
  const groupKey = (s, g) => `${s}|${g}`;
  const groupOpen = (s, g) => closedGroups.get(groupKey(s, g)) ?? true;
  const wide = () => advanced.classList.contains('wide');

  function open(name) {
    opener = name;
    target = name;
    if (name) {
      const setting = settings.entry(name);
      if (setting) {
        railSection = setting.section;
        closedSections.set(setting.section, true);
        closedGroups.set(groupKey(setting.section, setting.group), true);
      }
    }
    settings.openAdvanced();
  }

  function fit() {
    const width = advanced.clientWidth || root.clientWidth;
    if (!width) return false;
    const isWide = width >= ADVANCED_WIDE_PX;
    if (isWide === wide()) return false;
    advanced.classList.toggle('wide', isWide);
    return true;
  }

  function show() {
    shown = true;
    for (const selector of COVERED) { const covered = $(selector); if (covered) covered.inert = true; }
    advanced.hidden = false;
    fit();
    render();
    if (target && rows.has(target)) {
      const { row, input } = rows.get(target);
      row.scrollIntoView({ block: 'center' });
      row.classList.remove('flash');
      void row.offsetWidth;            // so that the flash runs again on a second opening
      row.classList.add('flash');
      input.focus({ preventScroll: true });
    } else {
      (body.querySelector('button') ?? $('#adv-done')).focus();
    }
    target = null;
  }

  function hide() {
    shown = false;
    advanced.hidden = true;
    for (const selector of COVERED) { const covered = $(selector); if (covered) covered.inert = false; }
    drawStep();
    const back = (opener && doc.getElementById(`chg-line-${opener}`))
      || (!entry.hidden ? $('#btn-advanced') : doc.getElementById('adv-effect-btn'));
    opener = null;
    if (back) back.focus();
  }

  function countText(n) { return n ? CHANGED_COUNT(n) : ''; }

  function expandButton(sectionName, groups) {
    const allOpen = groups.every((g) => groupOpen(sectionName, g.group));
    const b = el('button', 'icon-btn adv-expand');
    b.type = 'button';
    b.id = `adv-expand-${idPart(sectionName)}`;
    b.append(icon(doc, allOpen ? UNFOLD_LESS : UNFOLD_MORE));
    b.title = allOpen ? COLLAPSE_ALL : EXPAND_ALL;
    b.setAttribute('aria-label', IN_SECTION(b.title, sectionName));
    b.addEventListener('click', (event) => {
      event.stopPropagation();
      for (const g of groups) closedGroups.set(groupKey(sectionName, g.group), !allOpen);
      render();
    });
    return b;
  }

  function control(setting) {
    const id = `adv-${setting.name}`;
    let input;
    let unit = '';
    if (setting.kind === 'choice') {
      input = el('select');
      for (const choice of setting.choices) {
        const option = el('option', null, choice.label);
        option.value = choice.value;
        input.append(option);
      }
    } else if (setting.kind === 'number' && setting.number_form !== 'decimal_or_percent') {
      input = el('input');
      input.type = 'number';
      input.step = setting.number_form === 'integer' ? '1' : 'any';
      if ('min' in setting) input.min = String(setting.min);
      if ('max' in setting) input.max = String(setting.max);
      unit = setting.unit ?? '';
    } else {
      // a text, or a number that may be a percentage, which a number field cannot hold
      input = el('input', setting.kind === 'number' ? 'num-text' : 'text-value');
      input.type = 'text';
      if (setting.kind === 'number') input.inputMode = 'decimal';
      else input.maxLength = setting.max_length;
      unit = setting.unit ?? '';
    }
    input.id = id;
    return { input, unit };
  }

  function showValue(setting, input) {
    const value = settings.value(setting.name) ?? '';
    if (setting.kind === 'choice' && ![...input.options].some((o) => o.value === value)) {
      const option = el('option', null, formatValue(setting, value));
      option.value = value;
      input.prepend(option);
    }
    input.value = setting.kind === 'number' && setting.number_form === 'percent' ? String(value).replace(/%$/, '') : value;
  }

  function settingRow(setting) {
    const row = el('div', 'adv-row');
    row.id = `adv-row-${setting.name}`;
    const label = el('label', null, setting.label);
    label.htmlFor = `adv-${setting.name}`;
    const quick = settings.QUICK.find((q) => q.name === setting.name);
    const tip = [setting.explanation, quick ? ALSO_QUICK(quick.label) : ''].filter(Boolean).join(' ');
    if (tip) label.title = tip;
    const ctl = el('div', 'ctl');
    const { input, unit } = control(setting);
    ctl.append(input, el('span', 'unit', unit));
    row.append(label, ctl);
    input.addEventListener('change', () => {
      const read = settings.set(setting.name, input.value);
      const bad = row.querySelector('.bad');
      if (bad) bad.remove();
      input.classList.toggle('invalid', !read.ok);
      if (!read.ok) row.append(el('div', 'bad', `${read.report.message} ${read.report.remedy}`));
    });
    rows.set(setting.name, { row, input, setting });
    refreshRow(setting.name);
    return row;
  }

  // A row drawn again in place after its value changed: its value, its look as changed, and the
  // line under it with the profile's value and Reset.
  function refreshRow(name) {
    const { row, input, setting } = rows.get(name);
    if (!input.classList.contains('invalid')) showValue(setting, input);
    const changed = settings.isChanged(name);
    row.classList.toggle('changed', changed);
    const was = row.querySelector('.was');
    if (!changed) { if (was) was.remove(); return; }
    const shownValue = formatValue(setting, settings.profileValue(name));
    if (was) {
      // kept in place, so that a press on Reset that blurs a field and so changes it still lands
      was.firstChild.textContent = PROFILE_WAS(shownValue);
      was.querySelector('.reset').setAttribute('aria-label', RESET_TO(setting.label, shownValue));
      return;
    }
    const line = el('div', 'was');
    line.append(doc.createTextNode(PROFILE_WAS(shownValue)));
    const reset = el('button', 'linkish reset', RESET);
    reset.type = 'button';
    reset.id = `adv-reset-${name}`;
    reset.setAttribute('aria-label', RESET_TO(setting.label, shownValue));
    reset.addEventListener('click', () => {
      input.classList.remove('invalid');
      const bad = row.querySelector('.bad');
      if (bad) bad.remove();
      settings.reset(name);
      input.focus({ preventScroll: true });       // the Reset link is gone; its setting keeps the focus
    });
    line.append(reset);
    const bad = row.querySelector('.bad');
    row.insertBefore(line, bad);
  }

  function refreshCounts() {
    const n = settings.changes().length;
    $('#adv-sub').textContent = ADVANCED_SUB(store.get().plate.profile ?? '', n);
    resetAll.disabled = n === 0;
    for (const count of counts) {
      const c = settings.changedIn(count.test);
      if (count.rail) {
        count.node.textContent = c ? String(c) : '';
        count.node.hidden = !c;
      } else {
        count.node.textContent = countText(c);
        count.node.hidden = !c;
        count.head.classList.toggle('has-changes', c > 0);
      }
    }
  }

  function countNode(head, test, className = 'ct') {
    const node = el('span', className);
    head.append(node);
    counts.push({ node, test, head, rail: className === 'n' });
  }

  function groupsInto(into, sectionName, groups) {
    for (const g of groups) {
      const isOpen = groupOpen(sectionName, g.group);
      const group = el('div', `adv-grp${isOpen ? ' open' : ''}`);
      const head = el('button', 'adv-sub');
      head.type = 'button';
      head.id = `adv-grp-${idPart(groupKey(sectionName, g.group))}`;
      head.setAttribute('aria-expanded', String(isOpen));
      head.append(chevron(doc, isOpen), el('span', 'nm', g.group));
      countNode(head, (s) => s.section === sectionName && s.group === g.group);
      head.addEventListener('click', () => { closedGroups.set(groupKey(sectionName, g.group), !isOpen); render(); });
      group.append(head);
      if (isOpen) {
        const list = el('div', 'adv-rows');
        for (const setting of g.settings) list.append(settingRow(setting));
        group.append(list);
      }
      into.append(group);
    }
  }

  // Draws advanced mode's body again, keeping the list's scroll and the focus on the control of
  // the same id.
  function render() {
    const kept = body.querySelector('.adv-list');
    const scroll = kept ? kept.scrollTop : 0;
    const active = doc.activeElement;
    const focusId = active && advanced.contains(active) && active.id ? active.id : null;
    rows = new Map();
    counts = [];
    body.replaceChildren();
    const sections = settings.sections();
    if (wide()) {
      const rail = el('div', 'adv-rail');
      rail.setAttribute('role', 'tablist');
      rail.setAttribute('aria-orientation', 'vertical');
      if (!sections.some((s) => s.section === railSection)) railSection = sections.length ? sections[0].section : null;
      for (const s of sections) {
        const on = s.section === railSection;
        const b = el('button', on ? 'on' : '', s.section);
        b.type = 'button';
        b.id = `adv-tab-${idPart(s.section)}`;
        b.setAttribute('role', 'tab');
        b.setAttribute('aria-selected', String(on));
        countNode(b, (x) => x.section === s.section, 'n');
        b.addEventListener('click', () => {
          railSection = s.section;
          render();
          const list = body.querySelector('.adv-list');
          if (list) list.scrollTop = 0;
        });
        rail.append(b);
      }
      body.append(rail);
      const list = el('div', 'adv-list');
      const col = el('div', 'adv-col');
      const chosen = sections.find((s) => s.section === railSection);
      if (chosen) {
        const top = el('div', 'adv-col-top');
        top.append(el('span', 'adv-col-name', chosen.section), expandButton(chosen.section, chosen.groups));
        col.append(top);
        groupsInto(col, chosen.section, chosen.groups);
      }
      list.append(col);
      body.append(list);
      list.scrollTop = scroll;
    } else {
      const accordion = el('div', 'adv-list adv-accordion');
      for (const s of sections) {
        const isOpen = sectionOpen(s.section);
        const card = el('div', `adv-sec${isOpen ? ' open' : ''}`);
        const headRow = el('div', 'adv-sec-head');
        const head = el('button', 'adv-sec-btn');
        head.type = 'button';
        head.id = `adv-sec-${idPart(s.section)}`;
        head.setAttribute('aria-expanded', String(isOpen));
        head.append(chevron(doc, isOpen), el('span', 'nm', s.section));
        countNode(head, (x) => x.section === s.section);
        // only opening a section makes it the rail's section; a closing is not a choosing
        head.addEventListener('click', () => {
          closedSections.set(s.section, !isOpen);
          if (!isOpen) railSection = s.section;
          render();
        });
        headRow.append(head);
        if (isOpen) headRow.append(expandButton(s.section, s.groups));
        card.append(headRow);
        if (isOpen) {
          const inner = el('div', 'adv-sec-body');
          groupsInto(inner, s.section, s.groups);
          card.append(inner);
        }
        accordion.append(card);
      }
      body.append(accordion);
      accordion.scrollTop = scroll;
    }
    refreshCounts();
    if (focusId) {
      const again = doc.getElementById(focusId);
      if (again && again !== doc.activeElement) again.focus({ preventScroll: true });
    }
  }

  $('#adv-done').addEventListener('click', () => settings.closeAdvanced());
  resetAll.textContent = RESET_ALL;
  resetAll.addEventListener('click', async () => {
    const n = settings.changes().length;
    if (!n) return;
    const go = await confirmation(advanced, resetAll, {
      question: RESET_ALL_QUESTION(n, store.get().plate.profile ?? ''), go: RESET_ALL, keep: KEEP_CHANGES,
    });
    if (go) settings.resetAll();
    resetAll.focus();
  });
  if (win.ResizeObserver) {
    new win.ResizeObserver(() => { if (fit() && shown) render(); }).observe(advanced);
  }

  // ---- kept drawn
  settings.subscribe(() => {
    drawStep();
    if (!shown) return;
    for (const name of rows.keys()) refreshRow(name);
    refreshCounts();
  });
  store.subscribe((state, before) => {
    if (state.advanced && !shown && state.step === 'settings') show();
    else if (!state.advanced && shown) hide();
    if (state.configuration !== before.configuration || state.settingsTable !== before.settingsTable
        || state.plate.filament !== before.plate.filament || state.plate.profile !== before.plate.profile
        || state.plate.changes !== before.plate.changes) {
      drawStep();
      if (shown && state.settingsTable !== before.settingsTable) render();
    }
  });
  drawStep();

  return { draw: drawStep, open, section };
}
