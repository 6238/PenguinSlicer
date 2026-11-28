// The page opening (src/opening.js; wizard/README-details.md, "The current group", "The
// configuration and the table of settings" and "What the browser keeps"): GET /api/me, then the
// tab's plate from the browser's storage, then GET /api/configuration for the current group, with
// GET /api/settings-table asked beside them; the header's name; the reload glyph; every failure
// the page meets on the way, each an error report shown as a notification. The pages here run on
// the fake front server, the fake clock and the fakes of the browser's storage and locks.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../src/api.js';
import { endOpening, openWizard } from '../src/opening.js';
import { createReports } from '../src/reports.js';
import { createStore } from '../src/state.js';
import { createStorage } from '../src/storage.js';
import * as sentences from '../src/sentences.js';
import { FakeClock, settle } from './fakes/clock.js';
import { FakeFrontServer, errorReport, example, steps } from './fakes/front_server.js';
import { FakeLocks, FakeRecords, FakeTab } from './fakes/storage.js';

const ME = example('wizard-front/me.json');
const DEFAULT = example('configuration-default.json');
const HAND = example('configuration-hand-written.json');
const TABLE = example('settings-table.json');
const FIRST_GROUP = ME.groups[0].id;

const configurationAnswer = (configuration = DEFAULT, source = 'default', name = 'PenguinSlicer default', revision = null) =>
  steps.answer(200, { configuration, source, name, revision });

// One browser: a storage, its locks, a clock and a front server shared by its pages.
function browser() {
  let n = 0;
  return { records: new FakeRecords(), locks: new FakeLocks(), clock: new FakeClock(), server: new FakeFrontServer(), newId: () => `plate-${(n += 1)}` };
}

// A stand-in for the panel: what the opening asks of it (notify, onReloadConfiguration).
function fakePanel() {
  return {
    notices: [],
    reload: null,
    notify(notice) { this.notices.push(notice); },
    onReloadConfiguration(listener) { this.reload = listener; },
  };
}

// One page of that browser, in the tab `name` (a refresh reuses the tab), opened.
async function openPage(b, name, { tab = new FakeTab() } = {}) {
  const store = createStore();
  const api = createApi({ transport: b.server.transport, clock: b.clock, version: 'v', currentGroup: () => store.get().group, random: () => 0.5 });
  const reports = createReports({ api, clock: b.clock, page: `page-${name}`, step: () => store.get().step, environment: { browser: 'Chrome', browser_version: '131.0', software_3d: () => true } });
  const storage = createStorage({
    openRecords: () => b.records.open(), locks: b.locks.forTab(name), tab, clock: b.clock, newId: b.newId,
    report: (what, fields) => reports.failure(what, fields),
  });
  const panel = fakePanel();
  const opening = openWizard({ api, store, panel, storage });
  return { name, tab, store, api, storage, panel, opening, opened: await opening };
}

const apiRequests = (server) => server.requests.filter((r) => r.path.startsWith('/api/') && !r.path.startsWith('/api/reports/')).map((r) => `${r.method} ${r.path}`);

test('the page asks who the user is and the table of settings at once, then the configuration for the first of the user\'s groups', async () => {
  const b = browser();
  b.server.script('GET', '/api/me', steps.hold());
  const store = createStore();
  const api = createApi({ transport: b.server.transport, clock: b.clock, version: 'v', currentGroup: () => store.get().group, random: () => 0.5 });
  const storage = createStorage({ openRecords: () => b.records.open(), locks: b.locks.forTab('A'), tab: new FakeTab(), clock: b.clock, newId: b.newId, report: () => {} });
  const opening = openWizard({ api, store, panel: fakePanel(), storage });
  await settle();
  assert.deepEqual(apiRequests(b.server), ['GET /api/settings-table', 'GET /api/me']);
  b.server.requests[1].held.release();
  assert.equal((await opening).opened, true);
  assert.deepEqual(apiRequests(b.server), ['GET /api/settings-table', 'GET /api/me', 'GET /api/configuration']);
  const [table, me, configuration] = b.server.requests;
  assert.equal(me.headers['x-penguinslicer-group'], undefined);
  assert.equal(table.headers['x-penguinslicer-group'], undefined);
  assert.equal(configuration.headers['x-penguinslicer-group'], FIRST_GROUP);
});

test('the opened page holds the user, the current group, the configuration, its name and the printer\'s plate from the table', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  const state = a.store.get();
  assert.deepEqual(state.user, ME.user);
  assert.deepEqual(state.groups, ME.groups);
  assert.equal(state.group, FIRST_GROUP);
  assert.equal(state.configName, 'PenguinSlicer default');
  assert.equal(state.configSource, 'default');
  assert.deepEqual(state.configuration, DEFAULT);
  assert.deepEqual(state.settingsTable, TABLE);
  assert.deepEqual(state.printer, TABLE.catalog.printers.find((p) => p.name === DEFAULT.printer));
  assert.equal(state.plateId, a.storage.plate().plate_id);
  assert.equal(state.step, 'parts');
  assert.deepEqual(a.panel.notices, []);
});

test('a new plate starts with the first filament and its first profile, shown in the plate summary and written to the stored plate', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  assert.equal(a.store.get().plate.filament, 'PETG');
  assert.equal(a.store.get().plate.filamentFull, 'PETG');
  assert.equal(a.store.get().plate.profile, 'Standard');
  await a.storage.written();
  assert.deepEqual(b.records.value(`plates/${a.store.get().plateId}`).settings, { filament: 'PETG', profile: 'Standard', changes: {} });
});

test('the header names the group\'s own configuration by the name the front server gives', async () => {
  const b = browser();
  b.server.script('GET', '/api/configuration', configurationAnswer(HAND, 'group', '6238 (Popcorn Penguins)', 'r-1'));
  const a = await openPage(b, 'A');
  assert.equal(a.store.get().configName, '6238 (Popcorn Penguins)');
  assert.equal(a.store.get().configSource, 'group');
  assert.equal(a.store.get().plate.filament, 'Black PETG');
});

test('a refreshed tab reopens its plate on its stored step, with its filament and profile', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  a.store.set({ step: 'layout', plate: { filament: 'PLA', filamentFull: 'PLA', profile: 'Standard' } });
  await a.storage.written();
  b.locks.closeTab('A');
  const again = await openPage(b, 'A', { tab: a.tab });
  assert.equal(again.store.get().plateId, a.store.get().plateId);
  assert.equal(again.store.get().step, 'layout');
  assert.equal(again.store.get().plate.filament, 'PLA');
  assert.deepEqual(again.panel.notices, []);
});

test('two tabs open at once have two plates; a closed tab\'s plate is taken up by the next tab', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  const c = await openPage(b, 'B');
  assert.notEqual(a.store.get().plateId, c.store.get().plateId);
  b.locks.closeTab('A');
  const d = await openPage(b, 'D');
  assert.equal(d.store.get().plateId, a.store.get().plateId);
});

test('a stored filament gone from the configuration since the plate was used is replaced on opening, and a notification says which', async () => {
  const b = browser();
  b.server.script('GET', '/api/configuration', configurationAnswer(HAND, 'group', '6238 (Popcorn Penguins)'));
  const a = await openPage(b, 'A');
  a.store.set({ plate: { filament: 'PETG-CF', filamentFull: 'PETG-CF', profile: 'Stiff bracket' } });
  await a.storage.written();
  b.locks.closeTab('A');
  const again = await openPage(b, 'A', { tab: a.tab });          // the default now: no PETG-CF
  assert.equal(again.store.get().plate.filament, 'PETG');
  assert.equal(again.store.get().plate.profile, 'Standard');
  assert.deepEqual(again.panel.notices.map(({ kind, what, todo }) => ({ kind, what, todo })), [
    { kind: 'warn', what: 'PETG-CF is no longer in the configuration.', todo: 'The plate now uses PETG · Standard.' },
  ]);
});

// ---- the reload glyph

test('the reload glyph reads the configuration again; with the choice still there nothing is said', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  b.server.script('GET', '/api/configuration', configurationAnswer(DEFAULT, 'group', '6238 (Popcorn Penguins)', 'r-2'));
  await a.panel.reload();
  assert.equal(a.store.get().configName, '6238 (Popcorn Penguins)');
  assert.equal(a.store.get().configSource, 'group');
  assert.equal(b.server.made('GET', '/api/configuration').length, 2);
  assert.equal(b.server.made('GET', '/api/configuration')[1].headers['x-penguinslicer-group'], FIRST_GROUP);
  assert.deepEqual(a.panel.notices, []);
});

test('the reload glyph with the chosen filament gone picks the first filament and its first profile, and says which', async () => {
  const b = browser();
  b.server.script('GET', '/api/configuration', configurationAnswer(HAND, 'group', '6238 (Popcorn Penguins)'));
  const a = await openPage(b, 'A');
  a.store.set({ plate: { filament: 'Orange PETG', filamentFull: 'Orange PETG', profile: 'Structural' } });
  await a.panel.reload();                                       // the default: no Orange PETG
  assert.equal(a.store.get().plate.filament, 'PETG');
  assert.equal(a.store.get().plate.profile, 'Standard');
  assert.deepEqual(a.panel.notices.map((n) => [n.kind, n.what, n.todo]),
    [['warn', 'Orange PETG is no longer in the configuration.', 'The plate now uses PETG · Standard.']]);
  await a.storage.written();
  assert.equal(b.records.value(`plates/${a.store.get().plateId}`).settings.filament, 'PETG');
});

test('the reload glyph with the chosen profile gone from its filament picks the filament\'s first profile, and says which', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  a.store.set({ plate: { filament: 'PETG', filamentFull: 'PETG', profile: 'Fine' } });
  const withoutFine = structuredClone(DEFAULT);
  withoutFine.filaments[0].profiles = withoutFine.filaments[0].profiles.filter((p) => p.name !== 'Fine');
  b.server.script('GET', '/api/configuration', configurationAnswer(withoutFine));
  await a.panel.reload();
  assert.equal(a.store.get().plate.profile, 'Standard');
  assert.deepEqual(a.panel.notices.map((n) => [n.kind, n.what, n.todo]),
    [['warn', 'Fine is no longer offered for PETG.', 'The plate now uses PETG · Standard.']]);
});

test('the reload glyph asks for the table of settings again only when the configuration names a printer the table lacks', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  await a.panel.reload();
  assert.equal(b.server.made('GET', '/api/settings-table').length, 1);
  const otherPrinter = { ...structuredClone(DEFAULT), printer: 'Bambu Lab X9 0.4 nozzle' };
  const tableWithIt = structuredClone(TABLE);
  tableWithIt.catalog.printers.push({ name: 'Bambu Lab X9 0.4 nozzle', printable_area: [[0, 0], [250, 0], [250, 250], [0, 250]], printable_height: 250 });
  b.server.script('GET', '/api/configuration', configurationAnswer(otherPrinter));
  b.server.script('GET', '/api/settings-table', steps.answer(200, tableWithIt));
  await a.panel.reload();
  assert.equal(b.server.made('GET', '/api/settings-table').length, 2);
  assert.equal(a.store.get().printer.printable_height, 250);
});

test('the reload glyph pressed again while the configuration is being read asks once', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  b.server.script('GET', '/api/configuration', steps.hold());
  const first = a.panel.reload();
  const second = a.panel.reload();
  await settle();
  assert.equal(b.server.made('GET', '/api/configuration').length, 2);
  b.server.made('GET', '/api/configuration')[1].held.release();
  await Promise.all([first, second]);
  assert.equal(b.server.made('GET', '/api/configuration').length, 2);
});

test('a reload whose answer is refused shows the report\'s sentences and keeps the configuration the page has', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  b.server.script('GET', '/api/configuration', steps.report(errorReport('front.group_not_allowed')));
  await a.panel.reload();
  assert.equal(a.store.get().configName, 'PenguinSlicer default');
  assert.deepEqual(a.panel.notices.map((n) => [n.kind, n.what, n.todo]), [['error',
    "The fake front server's sentence of what happened for front.group_not_allowed.",
    "The fake front server's sentence of what to do for front.group_not_allowed."]]);
});

// ---- retrying and failing on the way in

test('a quiet failure of /api/me is retried and the page opens once it is answered', async () => {
  const b = browser();
  b.server.script('GET', '/api/me', steps.report(errorReport('front.unexpected')), steps.drop());
  const store = createStore();
  const api = createApi({ transport: b.server.transport, clock: b.clock, version: 'v', currentGroup: () => store.get().group, random: () => 0.5 });
  const storage = createStorage({ openRecords: () => b.records.open(), locks: b.locks.forTab('A'), tab: new FakeTab(), clock: b.clock, newId: b.newId, report: () => {} });
  const opening = openWizard({ api, store, panel: fakePanel(), storage });
  await b.clock.advance(1000);
  await b.clock.advance(2000);
  assert.equal((await opening).opened, true);
  assert.equal(b.server.made('GET', '/api/me').length, 3);
  assert.equal(store.get().configName, 'PenguinSlicer default');
});

test('the table of settings answered 503 front.slice_unreachable is retried quietly', async () => {
  const b = browser();
  b.server.script('GET', '/api/settings-table', steps.report(errorReport('front.slice_unreachable')));
  const store = createStore();
  const api = createApi({ transport: b.server.transport, clock: b.clock, version: 'v', currentGroup: () => store.get().group, random: () => 0.5 });
  const storage = createStorage({ openRecords: () => b.records.open(), locks: b.locks.forTab('A'), tab: new FakeTab(), clock: b.clock, newId: b.newId, report: () => {} });
  const panel = fakePanel();
  const opening = openWizard({ api, store, panel, storage });
  await b.clock.advance(1000);
  assert.equal((await opening).opened, true);
  assert.deepEqual(store.get().settingsTable, TABLE);
  assert.deepEqual(panel.notices, []);
});

test('/api/me refused with a report shows its sentences, and the page asks nothing for a group', async () => {
  const b = browser();
  b.server.script('GET', '/api/me', steps.report(errorReport('front.not_signed_in')));
  const a = await openPage(b, 'A');
  assert.equal(a.opened.opened, false);
  assert.deepEqual(a.panel.notices.map((n) => [n.kind, n.what, n.todo]), [['error',
    "The fake front server's sentence of what happened for front.not_signed_in.",
    "The fake front server's sentence of what to do for front.not_signed_in."]]);
  assert.equal(b.server.made('GET', '/api/configuration').length, 0);
  assert.deepEqual(b.records.keys(), []);                       // nothing stored for nobody
});

test('an answer to /api/me the page cannot use is the wizard\'s own report, shown and not retried', async () => {
  const b = browser();
  b.server.script('GET', '/api/me', steps.answer(200, { user: { name: 'No id' }, groups: [] }));
  const a = await openPage(b, 'A');
  assert.equal(a.opened.opened, false);
  assert.equal(a.panel.notices.length, 1);
  assert.equal(a.panel.notices[0].what, 'The server gave an answer this page cannot read.');
  assert.equal(a.panel.notices[0].todo, 'Reload the page to try again.');
  assert.equal(b.server.made('GET', '/api/me').length, 1);
});

test('a configuration the page cannot use is the wizard\'s own report, shown', async () => {
  const b = browser();
  b.server.script('GET', '/api/configuration', steps.answer(200, { configuration: { printer: 'x', filaments: [] }, source: 'group', name: 'N', revision: null }));
  const a = await openPage(b, 'A');
  assert.equal(a.opened.opened, true);
  assert.equal(a.store.get().configName, null);
  assert.deepEqual(a.panel.notices.map((n) => n.what), ['The server gave an answer this page cannot read.']);
});

test('a table of settings refused with a report shows its sentences; the configuration is still read', async () => {
  const b = browser();
  b.server.script('GET', '/api/settings-table', steps.report(errorReport('front.bad_request')));
  const a = await openPage(b, 'A');
  assert.equal(a.store.get().configName, 'PenguinSlicer default');
  assert.equal(a.store.get().settingsTable, null);
  assert.equal(a.store.get().printer, null);
  assert.deepEqual(a.panel.notices.map((n) => n.what), ["The fake front server's sentence of what happened for front.bad_request."]);
});

// ---- the stored plate follows the page

test('a change of step is written to the stored plate at once', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  a.store.set({ step: 'settings' });
  await a.storage.written();
  assert.equal(b.records.value(`plates/${a.store.get().plateId}`).step, 'settings');
});

test('a different user at /api/me clears every stored plate before anything is shown', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, new ArrayBuffer(84));
  b.locks.closeTab('A');
  b.server.script('GET', '/api/me', steps.answer(200, { user: { id: 'someone-else', name: 'Sam Lee' }, groups: [{ id: 'someone-else', name: 'Sam Lee' }] }));
  const c = await openPage(b, 'C', { tab: a.tab });
  assert.notEqual(c.store.get().plateId, a.store.get().plateId);
  assert.equal(b.records.value('owner'), 'someone-else');
  assert.deepEqual(b.records.keys(), ['owner', `plates/${c.store.get().plateId}`]);
  assert.equal(c.store.get().group, 'someone-else');
});

test('a cleared storage sends one storage_cleared report through the front server', async () => {
  const b = browser();
  const a = await openPage(b, 'A');
  b.records.clearAll();
  b.locks.closeTab('A');
  await openPage(b, 'A', { tab: a.tab });
  const reports = b.server.made('POST', '/api/reports/failure').map((r) => JSON.parse(r.body));
  assert.deepEqual(reports.map((r) => [r.what, r.page, r.step]), [['storage_cleared', 'page-A', 'parts']]);
});

test('an opening that ends marks the page opened; one that throws is reported as page_failed and marks the page failed', async () => {
  const marks = [];
  const reports = [];
  const report = (what, fields) => reports.push({ what, ...fields });
  const ended = await endOpening(Promise.resolve({ opened: true }), { report, mark: (m) => marks.push(m) });
  assert.deepEqual(ended, { opened: true });
  assert.deepEqual(marks, ['true']);
  assert.deepEqual(reports, []);
  const failed = await endOpening(Promise.reject(new TypeError('stored.parts.filter is not a function')), { report, mark: (m) => marks.push(m) });
  assert.deepEqual(failed, { opened: false });
  assert.deepEqual(marks, ['true', 'failed']);
  assert.deepEqual(reports, [{ what: 'page_failed', detail: 'opening the page: TypeError: stored.parts.filter is not a function' }]);
});

test('the sentences of a choice gone are the wizard\'s own', () => {
  assert.equal(sentences.CONFIG_FILAMENT_GONE('PETG-CF'), 'PETG-CF is no longer in the configuration.');
  assert.equal(sentences.CONFIG_PROFILE_GONE('Fine', 'PETG'), 'Fine is no longer offered for PETG.');
  assert.equal(sentences.CONFIG_NOW_USES('PETG', 'Standard'), 'The plate now uses PETG · Standard.');
  assert.equal(sentences.PART_NOT_SAVED, 'This part could not be saved in this browser, so a refresh will lose it.');
});
