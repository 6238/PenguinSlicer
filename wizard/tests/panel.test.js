// The panel as a whole, in the parts that need no drawing (wizard/README-details.md, "The panel
// as a whole"): the panel line's two uses, the step a tab click is held by, the plate summary's
// lines, the tooltip's timing and its place inside the panel. What needs the browser (the
// widths, focus, the joined boxes opening and closing) is in tests_browser/.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createPanelLine, lineContent } from '../src/panel/panel-line.js';
import { STEPS, heldBy, stepIndex } from '../src/panel/steps.js';
import { whyNotLeave } from '../src/panel/panel.js';
import { MAX_INSTANCES } from '../src/geometry/constants.js';
import { summaryModel, changeLine } from '../src/panel/summary.js';
import { createTooltips, placeTooltip } from '../src/panel/tooltips.js';
import * as constants from '../src/page-constants.js';
import { FakeClock } from './fakes/clock.js';

test('the five steps, in order, with the names the panel shows', () => {
  assert.deepEqual(STEPS.map((s) => [s.id, s.name]),
    [['parts', 'Parts'], ['settings', 'Settings'], ['layout', 'Layout'], ['preview', 'Preview'], ['send', 'Send']]);
  assert.equal(stepIndex('layout'), 2);
});

test('the figures of the panel are the details file\'s', () => {
  assert.equal(constants.PANEL_MIN_PX, 320);
  assert.deepEqual([constants.WIDTH_TABS_PX, constants.WIDTH_FIGURES_PX, constants.WIDTH_COLUMNS_PX], [480, 520, 680]);
  assert.deepEqual([constants.TOOLTIP_DELAY_MS, constants.TOOLTIP_EDGE_PX], [150, 6]);
  assert.deepEqual([constants.ROW_SLOW_S, constants.RETRY_QUIET_S, constants.RETRY_TOTAL_S], [4, 20, 300]);
  assert.deepEqual([constants.RETRY_FIRST_WAIT_S, constants.RETRY_MAX_WAIT_S, constants.RETRY_SPREAD], [1, 30, 0.1]);
});

// --- the step a click on a tab is held by

const rules = (whys) => (step) => whys[step] ?? null;

test('a click on a later tab goes there when every step before it allows it', () => {
  assert.equal(heldBy('preview', 'parts', rules({})), null);
});

test('a click on a later tab is held by the first step before it that does not allow it, and says why', () => {
  const why = rules({ settings: null, layout: '23 instances are closer than 12 mm with supports on.', parts: null });
  assert.deepEqual(heldBy('send', 'settings', why), { step: 'layout', text: 'Layout first: 23 instances are closer than 12 mm with supports on.' });
  assert.deepEqual(heldBy('layout', 'parts', rules({ parts: 'add a part.' })), { step: 'parts', text: 'Parts first: add a part.' });
});

// --- each reason a step holds a click (whyNotLeave), each reached, and the limit at its edge

const at = (fields, rest = {}) => ({ plate: { parts: 1, instances: 1, ...fields }, layoutProblem: null, sliced: false, ...rest });

test('the Parts step holds a click with no part', () => {
  assert.equal(whyNotLeave('parts', at({ parts: 0, instances: 0 })), 'add a part.');
});

test('the Parts step lets a plate of exactly 150 instances go on, and holds one of 151', () => {
  assert.equal(MAX_INSTANCES, 150);
  assert.equal(whyNotLeave('parts', at({ parts: 2, instances: 150 })), null);
  assert.equal(whyNotLeave('parts', at({ parts: 2, instances: 151 })), 'a plate holds up to 150 instances.');
});

test('the Layout step holds a click with no instances', () => {
  assert.equal(whyNotLeave('layout', at({ parts: 1, instances: 0 })), 'there are no instances.');
});

test('the Layout step holds a click with its first problem, and lets one go with none', () => {
  const problem = '23 instances are closer than 12 mm with supports on.';
  assert.equal(whyNotLeave('layout', at({ instances: 23 }, { layoutProblem: problem })), problem);
  assert.equal(whyNotLeave('layout', at({ instances: 23 })), null);
});

test('the Preview step holds a click until the plate is sliced; Settings and Send never do', () => {
  assert.equal(whyNotLeave('preview', at({})), 'the plate is not sliced yet.');
  assert.equal(whyNotLeave('preview', at({}, { sliced: true })), null);
  assert.equal(whyNotLeave('settings', at({ parts: 0, instances: 0 })), null);
  assert.equal(whyNotLeave('send', at({ parts: 0, instances: 0 })), null);
});

test('a click on an earlier tab, or on the current one, is never held', () => {
  const allHeld = () => 'held.';
  assert.equal(heldBy('parts', 'send', allHeld), null);
  assert.equal(heldBy('layout', 'layout', allHeld), null);
});

// --- the panel line

test('the panel line shows nothing, the passing use, or the lasting use', () => {
  assert.deepEqual(lineContent({ kind: 'none' }, null), { kind: 'none' });
  assert.deepEqual(lineContent({ kind: 'none' }, 'Layout first: there are no instances.'),
    { kind: 'passing', text: 'Layout first: there are no instances.' });
  assert.deepEqual(lineContent({ kind: 'slow', seconds: 28 }, null),
    { kind: 'slow', text: 'The server is being slow. Your browser is retrying in 28 s.', action: 'Retry now' });
  assert.deepEqual(lineContent({ kind: 'slow', seconds: 0 }, null),
    { kind: 'slow', text: 'The server is being slow. Your browser is retrying now.', action: 'Retry now' });
  assert.deepEqual(lineContent({ kind: 'unreachable' }, null),
    { kind: 'unreachable', text: 'The server could not be reached.', action: 'Try again' });
});

test('with the retry message showing, a held click shows no passing line', () => {
  assert.equal(lineContent({ kind: 'slow', seconds: 9 }, 'Parts first: add a part.').kind, 'slow');
  assert.equal(lineContent({ kind: 'unreachable' }, 'Parts first: add a part.').kind, 'unreachable');
});

function fakeBoard() {
  const listeners = new Set();
  let state = { kind: 'none' };
  return {
    state: () => state,
    subscribe: (l) => { listeners.add(l); return () => listeners.delete(l); },
    set(next) { state = next; for (const l of listeners) l(next); },
  };
}

test('the passing line goes at the user\'s next move', async () => {
  const clock = new FakeClock();
  const board = fakeBoard();
  const shown = [];
  const line = createPanelLine({ board, clock, show: (content) => shown.push(content) });
  line.held('Parts first: add a part.');
  assert.equal(line.content().kind, 'passing');
  line.moved();
  assert.deepEqual(line.content(), { kind: 'none' });
  assert.deepEqual(shown.map((c) => c.kind), ['passing', 'none']);
});

test(`the passing line goes after ${constants.PANEL_LINE_PASSING_S} s when the user does not move, and not before`, async () => {
  const clock = new FakeClock();
  const line = createPanelLine({ board: fakeBoard(), clock, show: () => {} });
  line.held('Parts first: add a part.');
  await clock.advance(constants.PANEL_LINE_PASSING_S * 1000 - 1);
  assert.equal(line.content().kind, 'passing');
  await clock.advance(1);
  assert.deepEqual(line.content(), { kind: 'none' });
});

test('a second held click starts the passing line\'s seconds again', async () => {
  const clock = new FakeClock();
  const line = createPanelLine({ board: fakeBoard(), clock, show: () => {} });
  line.held('Parts first: add a part.');
  await clock.advance(5000);
  line.held('Layout first: there are no instances.');
  await clock.advance(5000);
  assert.equal(line.content().text, 'Layout first: there are no instances.');
});

test('the lasting use follows the retry board as it changes', () => {
  const board = fakeBoard();
  const shown = [];
  const line = createPanelLine({ board, clock: new FakeClock(), show: (c) => shown.push(c) });
  board.set({ kind: 'slow', seconds: 11 });
  board.set({ kind: 'slow', seconds: 10 });
  board.set({ kind: 'none' });
  assert.deepEqual(shown.map((c) => c.text ?? c.kind),
    ['The server is being slow. Your browser is retrying in 11 s.', 'The server is being slow. Your browser is retrying in 10 s.', 'none']);
  line.dispose();
});

// --- the plate summary

const plate = (fields = {}) => ({
  parts: 1, instances: 1, filament: 'PETG', filamentFull: 'PETG (Bambu Basic)', profile: 'Structural', changes: [], ...fields,
});

test('none on the Parts step', () => {
  assert.equal(summaryModel('parts', plate()), null);
});

test('from the Settings step on, two lines: parts and instances; filament and profile', () => {
  for (const step of ['settings', 'layout', 'preview', 'send']) {
    assert.deepEqual(summaryModel(step, plate()), {
      first: '1 part · 1 instance', second: 'PETG · Structural', secondFull: 'PETG (Bambu Basic) · Structural', pill: null,
    });
  }
  assert.equal(summaryModel('layout', plate({ parts: 3, instances: 16 })).first, '3 parts · 16 instances');
});

test('while there are changes, the pill counts them, and the change details hold one line for each', () => {
  const changes = [
    { section: 'Quality', label: 'Resolution', value: '0.014 mm', profile: '0.012 mm' },
    { section: 'Others', label: 'Brim', value: 'Off', profile: 'Auto' },
  ];
  const model = summaryModel('settings', plate({ changes }));
  assert.deepEqual(model.pill, {
    text: '+2 changes', tip: 'The settings changed from Structural',
    lines: ['Quality › Resolution: 0.014 mm (profile 0.012 mm)', 'Others › Brim: Off (profile Auto)'],
  });
  assert.equal(summaryModel('settings', plate({ changes: changes.slice(0, 1) })).pill.text, '+1 change');
  assert.equal(changeLine(changes[1]), 'Others › Brim: Off (profile Auto)');
});

// --- the tooltip

function fakeElements() {
  return {
    icon: { name: 'icon', tip: 'Reload the configuration', hasVisibleText: false },
    circle: { name: 'circle', tip: '3. Layout', hasVisibleText: false },
    field: { name: 'field', tip: 'A field', hasVisibleText: false, isField: true },
    named: { name: 'named', tip: 'Next', hasVisibleText: true },
  };
}

function setUpTips() {
  const clock = new FakeClock();
  const shown = [];
  const tips = createTooltips({ clock, show: (el) => shown.push(el.name), hide: () => shown.push('hidden'), wanted: (el) => !el.hasVisibleText });
  return { clock, tips, shown, el: fakeElements() };
}

test('a tooltip shows at 150 ms of rest and not at 149', async () => {
  const { clock, tips, shown, el } = setUpTips();
  tips.rest(el.circle);
  await clock.advance(149);
  assert.deepEqual(shown, []);
  await clock.advance(1);
  assert.deepEqual(shown, ['circle']);
});

test('a tooltip shows at once on keyboard focus of an icon or a step circle, and not of a field', async () => {
  const { tips, shown, el } = setUpTips();
  tips.focused(el.circle, { keyboard: true });
  tips.focused(el.icon, { keyboard: true });
  tips.focused(el.field, { keyboard: true });
  tips.focused(el.circle, { keyboard: false });
  assert.deepEqual(shown, ['circle', 'hidden', 'icon', 'hidden']);
});

test('a tooltip goes on leave, press, Escape and loss of focus', async () => {
  const { clock, tips, shown, el } = setUpTips();
  for (const end of ['left', 'pressed', 'escape', 'blurred']) {
    tips.rest(el.icon);
    await clock.advance(150);
    shown.length = 0;
    if (end === 'left') tips.left(el.icon);
    if (end === 'pressed') tips.pressed();
    if (end === 'escape') tips.escape();
    if (end === 'blurred') tips.blurred(el.icon);
    assert.deepEqual(shown, ['hidden'], end);
  }
});

test('leaving before 150 ms shows nothing', async () => {
  const { clock, tips, shown, el } = setUpTips();
  tips.rest(el.icon);
  await clock.advance(100);
  tips.left(el.icon);
  await clock.advance(1000);
  assert.deepEqual(shown.filter((s) => s !== 'hidden'), []);
});

test('an element whose text shows in full has no tooltip', async () => {
  const { clock, tips, shown, el } = setUpTips();
  tips.rest(el.named);
  await clock.advance(1000);
  assert.deepEqual(shown.filter((s) => s !== 'hidden'), []);
});

test('a tooltip sits centred under its element, inside the panel by 6 px', () => {
  const panel = { width: 320, height: 600 };
  assert.deepEqual(placeTooltip(panel, { left: 100, right: 140, top: 50, bottom: 70 }, { width: 80, height: 30 }), { left: 80, top: 76 });
  // at the panel's left and right edges it stays 6 px inside a 320 px panel
  assert.deepEqual(placeTooltip(panel, { left: 0, right: 20, top: 50, bottom: 70 }, { width: 120, height: 30 }).left, 6);
  assert.deepEqual(placeTooltip(panel, { left: 300, right: 320, top: 50, bottom: 70 }, { width: 120, height: 30 }).left, 194);
  // wider than the panel allows: held at the left edge
  assert.deepEqual(placeTooltip(panel, { left: 150, right: 170, top: 50, bottom: 70 }, { width: 308, height: 30 }).left, 6);
});

test('above its element where the panel ends below', () => {
  const panel = { width: 320, height: 600 };
  assert.deepEqual(placeTooltip(panel, { left: 100, right: 140, top: 560, bottom: 580 }, { width: 80, height: 30 }), { left: 80, top: 524 });
  assert.deepEqual(placeTooltip(panel, { left: 100, right: 140, top: 10, bottom: 590 }, { width: 80, height: 30 }).top, 6);
});
