// The Settings step's behaviour and advanced mode's, without a browser window (src/settings.js;
// wizard/README-details.md, "The Settings step", "Advanced mode", "The profile's value of a
// setting"): the Filament and Profile menus, the quick changes and their values, a value off a
// menu's list, the one shared set of changes, each setting's value read from what is typed and
// refused when it does not fit, the change details' lines, and the changes kept in the browser's
// storage. The pages run on the contract's example table of settings and configurations, and on
// the fakes of the browser's storage and locks.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  QUICK, createSettings, formatValue, profileValues, quickMenu, readInput, sameValue, sectionsOf,
} from '../src/settings.js';
import { createStore } from '../src/state.js';
import { createStorage } from '../src/storage.js';
import { FakeClock, settle } from './fakes/clock.js';
import { example } from './fakes/front_server.js';
import { FakeLocks, FakeRecords, FakeTab } from './fakes/storage.js';

const TABLE = example('settings-table.json');
const DEFAULT = example('configuration-default.json');
const HAND = example('configuration-hand-written.json');
const ME = example('wizard-front/me.json');
const entry = (name) => TABLE.settings.find((s) => s.name === name);

function browser() {
  let n = 0;
  return { records: new FakeRecords(), locks: new FakeLocks(), clock: new FakeClock(), tab: new FakeTab(), newId: () => `plate-${(n += 1)}` };
}

// One page: the storage begun, the store holding what the opening puts there, the settings module
// taking up the stored plate's changes.
async function openPage(b = browser(), { configuration = DEFAULT, table = TABLE, filament, profile } = {}) {
  const store = createStore();
  const reports = [];
  const storage = createStorage({ openRecords: () => b.records.open(), locks: b.locks.forTab('A'), tab: b.tab, clock: b.clock, newId: b.newId, report: (what, f) => reports.push({ what, ...f }) });
  const settings = createSettings({ store, storage });
  const { plate, group } = await storage.begin({ user: ME.user.id, groups: ME.groups });
  const stored = plate.settings;
  const f = filament ?? stored.filament ?? configuration.filaments[0].name;
  const fil = configuration.filaments.find((x) => x.name === f) ?? configuration.filaments[0];
  const p = profile ?? (fil.profiles.some((x) => x.name === stored.profile) ? stored.profile : fil.profiles[0].name);
  store.set({ user: ME.user, groups: ME.groups, group, plateId: plate.plate_id, step: plate.step, plate: { filament: stored.filament, profile: stored.profile } });
  store.set({ configuration, settingsTable: table, plate: { filament: fil.name, filamentFull: fil.name, profile: p } });
  await settings.resume();
  await storage.written();
  return { b, store, storage, settings, reports };
}

const stored = (page) => page.storage.plate().settings;

// ---- the Filament and Profile menus

test('the Filament menu offers each filament with its colour, the Profile menu the chosen filament\'s profiles with their purposes', async () => {
  const page = await openPage(undefined, { configuration: HAND });
  assert.deepEqual(page.settings.filaments(), [
    { name: 'Black PETG', colour: '#202020' }, { name: 'Orange PETG', colour: '#e8742a' }, { name: 'PETG-CF', colour: '#5a5a5a' }]);
  assert.deepEqual(page.settings.profiles(), [
    { name: 'Structural', purpose: 'strong brackets and plates' }, { name: 'Draft', purpose: 'fit checks and test prints' }]);
});

test('picking a filament picks its first profile and clears every change', async () => {
  const page = await openPage(undefined, { configuration: HAND });
  page.settings.setQuick('walls', '6');
  assert.equal(page.settings.changes().length, 1);
  page.settings.chooseFilament('PETG-CF');
  assert.equal(page.store.get().plate.filament, 'PETG-CF');
  assert.equal(page.store.get().plate.profile, 'Stiff bracket');
  assert.deepEqual(page.settings.changes(), []);
  await page.storage.written();
  assert.deepEqual(stored(page).changes, {});
  assert.equal(stored(page).filament, 'PETG-CF');
});

test('picking another profile clears every change; picking the same one keeps them', async () => {
  const page = await openPage();
  page.settings.setQuick('walls', '6');
  page.settings.chooseProfile('Standard');
  assert.equal(page.settings.changes().length, 1);
  page.settings.chooseProfile('Draft');
  assert.equal(page.store.get().plate.profile, 'Draft');
  assert.deepEqual(page.settings.changes(), []);
});

test('a profile the configuration read again no longer has clears the changes, which are a departure from it', async () => {
  const page = await openPage(undefined, { configuration: HAND, filament: 'Black PETG', profile: 'Draft' });
  page.settings.setQuick('walls', '6');
  page.store.set({ plate: { profile: 'Structural' } });      // as the opening does when Draft is gone
  assert.deepEqual(page.settings.changes(), []);
  await page.storage.written();
  assert.deepEqual(stored(page).changes, {});
});

test('the caution counts the changes, singular and plural, and says nothing without one', async () => {
  const page = await openPage();
  assert.equal(page.settings.caution(), null);
  page.settings.setQuick('walls', '6');
  assert.equal(page.settings.caution(), 'Changing the filament or the profile clears your change.');
  page.settings.setQuick('brim', 'no_brim');
  assert.equal(page.settings.caution(), 'Changing the filament or the profile clears your 2 changes.');
  page.settings.resetAll();
  assert.equal(page.settings.caution(), null);
});

// ---- the profile's value

test('the profile\'s value is the configuration profile\'s override when it has one, and otherwise the process value', async () => {
  const page = await openPage(undefined, { profile: 'Structural' });
  assert.equal(page.settings.profileValue('wall_loops'), '4');
  assert.equal(page.settings.profileValue('sparse_infill_density'), '40%');
  assert.equal(page.settings.profileValue('layer_height'), '0.24');
  const values = profileValues(TABLE, DEFAULT.filaments[0].profiles[2]);
  assert.equal(values.layer_height, '0.3');
  assert.equal(values.outer_wall_speed, '500');
});

// ---- the quick changes

test('the quick changes\' menus offer the mockup\'s values, each written as Orca writes it', () => {
  const words = Object.fromEntries(QUICK.map((q) => [q.id, q.entries.map((e) => [e.text, e.value])]));
  assert.deepEqual(QUICK.map((q) => [q.id, q.label, q.name]), [
    ['infill', 'Infill', 'sparse_infill_density'], ['walls', 'Walls', 'wall_loops'],
    ['supports', 'Supports', 'enable_support'], ['brim', 'Brim', 'brim_type']]);
  assert.deepEqual(words.infill, [['15 %', '15%'], ['25 %', '25%'], ['40 %', '40%'], ['60 %', '60%'], ['100 %', '100%']]);
  assert.deepEqual(words.walls, [['2', '2'], ['3', '3'], ['4', '4'], ['6', '6']]);
  assert.deepEqual(words.supports, [['Off', '0'], ['On (tree, auto)', '1']]);
  assert.deepEqual(words.brim, [['Auto', 'auto_brim'], ['Off', 'no_brim'], ['Outer only', 'outer_only']]);
});

test('a menu shows the profile\'s value with no change, and the user\'s change once there is one', async () => {
  const page = await openPage(undefined, { profile: 'Structural' });
  const chosen = () => Object.fromEntries(page.settings.quick().map((q) => [q.id, q.chosen]));
  assert.deepEqual(chosen(), { infill: '40%', walls: '4', supports: '0', brim: 'auto_brim' });
  page.settings.setQuick('infill', '60%');
  assert.equal(chosen().infill, '60%');
  assert.deepEqual(page.settings.changes(), [{ name: 'sparse_infill_density', value: '60%' }]);
  assert.equal(page.settings.quick().find((q) => q.id === 'infill').changed, true);
});

test('choosing the profile\'s own value on a menu removes the change', async () => {
  const page = await openPage(undefined, { profile: 'Structural' });
  page.settings.setQuick('walls', '6');
  page.settings.setQuick('walls', '4');
  assert.deepEqual(page.settings.changes(), []);
});

test('Supports On writes enable_support and support_type tree(auto), whatever the profile\'s type; Off writes nothing for support_type', async () => {
  const table = structuredClone(TABLE);
  for (const v of Object.values(table.process_values)) v.support_type = 'normal(auto)';
  const page = await openPage(undefined, { table });
  page.settings.setQuick('supports', '1');
  assert.deepEqual(page.settings.changes(), [{ name: 'enable_support', value: '1' }, { name: 'support_type', value: 'tree(auto)' }]);
  page.settings.setQuick('supports', '0');
  assert.deepEqual(page.settings.changes(), [{ name: 'support_type', value: 'tree(auto)' }]);
  // with the profile's own tree(auto), On is one change
  const plain = await openPage();
  plain.settings.setQuick('supports', '1');
  assert.deepEqual(plain.settings.changes(), [{ name: 'enable_support', value: '1' }]);
});

test('Supports shows On when enable_support is "1", whatever support_type is', async () => {
  const page = await openPage();
  assert.equal(page.settings.set('enable_support', '1').ok, true);
  assert.equal(page.settings.set('support_type', 'normal(manual)').ok, true);
  assert.equal(page.settings.quick().find((q) => q.id === 'supports').chosen, '1');
});

// ---- a quick change whose value is not on its menu (the guide's recommendation)

test('a profile\'s value off the list is one more entry at the top of the menu, written as advanced mode writes it, and chosen', () => {
  const infill = QUICK.find((q) => q.id === 'infill');
  const menu = quickMenu(infill, entry('sparse_infill_density'), '35%', '35%');
  assert.deepEqual(menu.entries[0], { value: '35%', text: '35 %' });
  assert.equal(menu.entries.length, 6);
  assert.equal(menu.chosen, '35%');
  const brim = QUICK.find((q) => q.id === 'brim');
  const ears = quickMenu(brim, entry('brim_type'), 'brim_ears', 'brim_ears');
  assert.deepEqual(ears.entries[0], { value: 'brim_ears', text: 'Mouse ear' });
});

test('the profile\'s entry off the list stays while it is the profile\'s value, when another value is chosen', async () => {
  const page = await openPage(undefined, { configuration: HAND, filament: 'PETG-CF' });   // Stiff bracket: 35 % infill
  const infill = () => page.settings.quick().find((q) => q.id === 'infill');
  assert.deepEqual(infill().entries.map((e) => e.text), ['35 %', '15 %', '25 %', '40 %', '60 %', '100 %']);
  assert.equal(infill().chosen, '35%');
  page.settings.setQuick('infill', '60%');
  assert.deepEqual(infill().entries.map((e) => e.text), ['35 %', '15 %', '25 %', '40 %', '60 %', '100 %']);
  assert.equal(infill().chosen, '60%');
  page.settings.setQuick('infill', '35%');
  assert.deepEqual(page.settings.changes(), []);
});

test('a change set in advanced mode off the list is the menu\'s top entry while it lasts; picking a listed value replaces it', async () => {
  const page = await openPage();
  assert.equal(page.settings.set('wall_loops', '5').ok, true);
  const walls = () => page.settings.quick().find((q) => q.id === 'walls');
  assert.deepEqual(walls().entries.map((e) => e.text), ['5', '2', '3', '4', '6']);
  assert.equal(walls().chosen, '5');
  page.settings.setQuick('walls', '3');
  assert.deepEqual(walls().entries.map((e) => e.text), ['2', '3', '4', '6']);
});

test('a value written another way than the list\'s is the list\'s entry, not one more ("40.0%" is "40 %")', () => {
  const infill = QUICK.find((q) => q.id === 'infill');
  const menu = quickMenu(infill, entry('sparse_infill_density'), '40.0%', '40.0%');
  assert.equal(menu.entries.length, 5);
  assert.equal(menu.chosen, '40%');
});

// ---- each setting's value, as typed

test('a value is formatted as advanced mode shows it: a number with Orca\'s unit, a choice by its label', () => {
  assert.equal(formatValue(entry('layer_height'), '0.24'), '0.24 mm');
  assert.equal(formatValue(entry('sparse_infill_density'), '40%'), '40 %');
  assert.equal(formatValue(entry('initial_layer_line_width'), '0.62'), '0.62 mm');
  assert.equal(formatValue(entry('initial_layer_line_width'), '120%'), '120 %');
  assert.equal(formatValue(entry('wall_loops'), '3'), '3');
  assert.equal(formatValue(entry('sparse_infill_pattern'), 'gyroid'), 'Gyroid');
  assert.equal(formatValue(entry('enable_support'), '1'), 'On');
  assert.equal(formatValue({ name: 'x', kind: 'text', max_length: 5 }, 'abc'), 'abc');
});

test('a number is read in its form: a whole number, a decimal, a percentage with or without its sign, either where both are allowed', () => {
  assert.deepEqual(readInput(entry('wall_loops'), ' 5 '), { ok: true, value: '5' });
  assert.deepEqual(readInput(entry('layer_height'), '0.2'), { ok: true, value: '0.2' });
  assert.deepEqual(readInput(entry('sparse_infill_density'), '35'), { ok: true, value: '35%' });
  assert.deepEqual(readInput(entry('sparse_infill_density'), '35%'), { ok: true, value: '35%' });
  assert.deepEqual(readInput(entry('initial_layer_line_width'), '0.7'), { ok: true, value: '0.7' });
  assert.deepEqual(readInput(entry('initial_layer_line_width'), '110%'), { ok: true, value: '110%' });
});

test('a value that does not fit is refused where it is typed, with the wizard\'s own sentences and the value kept', () => {
  const cases = [
    [entry('wall_loops'), '2.5', 'Wall loops must be a whole number.'],
    [entry('wall_loops'), '1001', 'Wall loops must be between 0 and 1000.'],
    [entry('wall_loops'), '-1', 'Wall loops must be between 0 and 1000.'],
    [entry('layer_height'), '-0.1', 'Layer height must be at least 0 mm.'],
    [entry('layer_height'), 'abc', 'Layer height must be a number.'],
    [entry('layer_height'), '', 'Layer height must be a number.'],
    [entry('layer_height'), '١٢', 'Layer height must be a number.'],
    [entry('layer_height'), '1e3', 'Layer height must be a number.'],
    [entry('sparse_infill_density'), '101', 'Sparse infill density must be between 0 and 100 %.'],
    [{ name: 't', kind: 'number', label: 'Height', number_form: 'decimal', unit: 'mm', min: 0.08, max: 0.42 }, '0.9', 'Height must be between 0.08 and 0.42 mm.'],
    [entry('initial_layer_line_width'), '10%%', 'First layer must be a number or a percentage.'],
    [{ name: 't', kind: 'number', label: 'Big', number_form: 'decimal', max: 9 }, '10', 'Big must be at most 9.'],
    [entry('wall_loops'), '9'.repeat(41), 'Wall loops must be a whole number.'],
    [{ name: 't', kind: 'number', label: 'Count', number_form: 'integer' }, '3000000000', 'Count must be a whole number.'],
  ];
  for (const [setting, text, message] of cases) {
    const read = readInput(setting, text);
    assert.equal(read.ok, false, `${setting.name} ${text}`);
    assert.equal(read.report.code, 'wizard.setting_refused');
    assert.equal(read.report.message, message, text);
    assert.equal(read.report.retryable, false);
  }
  const page = { formatted: formatValue(entry('wall_loops'), '3') };
  assert.equal(readInput(entry('wall_loops'), 'x', '3').report.remedy, `Kept ${page.formatted}.`);
});

test('a text is refused past its greatest length or with a control character', () => {
  const text = { name: 'filename_format', kind: 'text', label: 'Name', max_length: 4 };
  assert.deepEqual(readInput(text, 'abcd'), { ok: true, value: 'abcd' });
  assert.equal(readInput(text, 'abcde').report.message, 'Name can be at most 4 characters long.');
  assert.equal(readInput(text, 'a\nb').report.message, 'Name cannot hold a line break or other control character.');
});

test('a choice is one of its values only', () => {
  assert.deepEqual(readInput(entry('brim_type'), 'brim_ears'), { ok: true, value: 'brim_ears' });
  assert.equal(readInput(entry('brim_type'), 'everywhere').ok, false);
});

test('numbers are compared as numbers: "0.30" is the profile\'s "0.3", and a percentage is never a plain number', () => {
  assert.equal(sameValue(entry('layer_height'), '0.30', '0.3'), true);
  assert.equal(sameValue(entry('initial_layer_line_width'), '62%', '0.62'), false);
  assert.equal(sameValue(entry('brim_type'), 'auto_brim', 'auto_brim'), true);
});

test('a setting set to the profile\'s value is no change; one refused leaves the changes as they were', async () => {
  const page = await openPage();
  assert.equal(page.settings.set('layer_height', '0.20').ok, true);
  assert.deepEqual(page.settings.changes(), [{ name: 'layer_height', value: '0.2' }]);
  assert.equal(page.settings.set('layer_height', '-3').ok, false);
  assert.deepEqual(page.settings.changes(), [{ name: 'layer_height', value: '0.2' }]);
  assert.equal(page.settings.set('layer_height', '0.240').ok, true);
  assert.deepEqual(page.settings.changes(), []);
});

test('a setting the table does not hold is refused, and never becomes a change', async () => {
  const page = await openPage();
  const read = page.settings.set('post_process', 'rm -rf /');
  assert.equal(read.ok, false);
  assert.deepEqual(page.settings.changes(), []);
});

test('reset puts one setting back, Reset all every setting', async () => {
  const page = await openPage();
  page.settings.set('layer_height', '0.2');
  page.settings.set('wall_loops', '5');
  page.settings.reset('layer_height');
  assert.deepEqual(page.settings.changes(), [{ name: 'wall_loops', value: '5' }]);
  page.settings.set('layer_height', '0.2');
  page.settings.resetAll();
  assert.deepEqual(page.settings.changes(), []);
  await page.storage.written();
  assert.deepEqual(stored(page).changes, {});
});

// ---- advanced mode's sections, from the table

test('the sections and setting groups are the table\'s, in its order', () => {
  const sections = sectionsOf(TABLE);
  assert.deepEqual(sections.map((s) => s.section), ['Quality', 'Strength', 'Speed', 'Support', 'Others']);
  assert.deepEqual(sections[1].groups.map((g) => [g.group, g.settings.map((s) => s.name)]), [
    ['Walls', ['wall_loops']], ['Sparse infill', ['sparse_infill_density', 'sparse_infill_pattern']]]);
  assert.deepEqual(sectionsOf(null), []);
});

test('the changed counts are by section and by setting group', async () => {
  const page = await openPage();
  page.settings.set('sparse_infill_pattern', 'gyroid');
  page.settings.set('wall_loops', '5');
  page.settings.set('layer_height', '0.2');
  assert.equal(page.settings.changedIn((s) => s.section === 'Strength'), 2);
  assert.equal(page.settings.changedIn((s) => s.section === 'Strength' && s.group === 'Walls'), 1);
  assert.equal(page.settings.changedIn((s) => s.section === 'Speed'), 0);
});

// ---- the change details, the changes box and the plate summary

test('each change has its line, a setting with a quick change in the quick change\'s words', async () => {
  const page = await openPage();
  page.settings.setQuick('brim', 'no_brim');
  page.settings.set('layer_height', '0.2');
  page.settings.set('sparse_infill_pattern', 'gyroid');
  page.settings.setQuick('supports', '1');
  assert.deepEqual(page.store.get().plate.changes, [
    { name: 'brim_type', section: 'Others', label: 'Brim', value: 'Off', profile: 'Auto' },
    { name: 'layer_height', section: 'Quality', label: 'Layer height', value: '0.2 mm', profile: '0.24 mm' },
    { name: 'sparse_infill_pattern', section: 'Strength', label: 'Sparse infill pattern', value: 'Gyroid', profile: 'Cross Hatch' },
    { name: 'enable_support', section: 'Support', label: 'Supports', value: 'On (tree, auto)', profile: 'Off' },
  ]);
  assert.equal(page.settings.boxTitle(), '4 settings changed from Standard');
  page.settings.resetAll();
  page.settings.set('wall_loops', '5');
  assert.equal(page.settings.boxTitle(), '1 setting changed from Standard');
});

// ---- kept in the browser's storage

test('the changes survive a reload, in the order they were made, and advanced mode reopens when it was open', async () => {
  const b = browser();
  const first = await openPage(b);
  first.store.set({ step: 'settings' });
  await first.storage.update({ step: 'settings' });           // as the opening writes the step
  first.settings.set('wall_loops', '5');
  first.settings.set('layer_height', '0.2');
  first.settings.openAdvanced();
  await first.storage.written();
  assert.equal(first.storage.plate().advanced, true);
  b.locks.closeTab('A');
  const again = await openPage(b);
  assert.deepEqual(again.settings.changes(), [{ name: 'wall_loops', value: '5' }, { name: 'layer_height', value: '0.2' }]);
  assert.equal(again.store.get().advanced, true);
  again.settings.closeAdvanced();
  await again.storage.written();
  assert.equal(again.storage.plate().advanced, false);
});

test('advanced mode does not reopen on a step other than Settings', async () => {
  const b = browser();
  const first = await openPage(b);
  first.store.set({ step: 'settings' });
  first.settings.openAdvanced();
  await first.storage.written();
  await first.storage.update({ step: 'layout' });
  b.locks.closeTab('A');
  const again = await openPage(b);
  assert.equal(again.store.get().advanced, false);
});

test('a stored change the table no longer holds, or whose value no longer fits, is dropped when the page opens', async () => {
  const b = browser();
  const first = await openPage(b);
  first.settings.set('wall_loops', '5');
  await first.storage.update({ settings: { ...first.storage.plate().settings, changes: { wall_loops: '5', gone_setting: '1', layer_height: '-4', brim_type: 'auto_brim' } } });
  b.locks.closeTab('A');
  const again = await openPage(b);
  assert.deepEqual(again.settings.changes(), [{ name: 'wall_loops', value: '5' }]);
  await again.storage.written();
  assert.deepEqual(again.storage.plate().settings.changes, { wall_loops: '5' });
});

test('stored changes wait for the table: none is dropped while the table has not arrived', async () => {
  const b = browser();
  const first = await openPage(b);
  first.settings.set('wall_loops', '5');
  await first.storage.written();
  b.locks.closeTab('A');
  const again = await openPage(b, { table: null });
  assert.deepEqual(again.settings.changes(), [{ name: 'wall_loops', value: '5' }]);
  again.store.set({ settingsTable: TABLE });
  await settle();
  assert.deepEqual(again.settings.changes(), [{ name: 'wall_loops', value: '5' }]);
});

test('New plate keeps the changes', async () => {
  const page = await openPage();
  page.settings.set('wall_loops', '5');
  const plate = await page.storage.newPlate({ keepSettings: true });
  page.store.set({ plateId: plate.plate_id });
  assert.deepEqual(page.settings.changes(), [{ name: 'wall_loops', value: '5' }]);
  assert.deepEqual(plate.settings.changes, { wall_loops: '5' });
});

test('every listener hears each change of the settings', async () => {
  const page = await openPage();
  let heard = 0;
  page.settings.subscribe(() => { heard += 1; });
  page.settings.set('wall_loops', '5');
  page.settings.reset('wall_loops');
  assert.equal(heard, 2);
});
