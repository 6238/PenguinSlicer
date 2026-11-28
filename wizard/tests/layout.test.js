// The Layout step's behaviour without a browser window (src/layout.js; wizard/README-details.md,
// "The Layout step"): instances following the Parts step's quantities, laid their best way and
// arranged; the placement check and every problem's message and button; laying an instance on a
// face, auto-orient, Arrange and its offer; the four moments the wizard turns an instance; the
// supports' spacing; the messages that go when the user leaves the step; the stored layout taken
// up again. The pages run on the fake front server, the fake clock, the fakes of the browser's
// storage and locks, and the real worker's code in the test's own thread, on real parts and parts
// made in the tests.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { createApi } from '../src/api.js';
import { createGeometryClient } from '../src/geometry-client.js';
import { createLayout, downOf, plateAngle, printerOf, supportsFor } from '../src/layout.js';
import * as W from '../src/layout-sentences.js';
import { createParts } from '../src/parts.js';
import { createStore } from '../src/state.js';
import { createStorage } from '../src/storage.js';
import { FakeClock, settle } from './fakes/clock.js';
import { FakeFrontServer, example } from './fakes/front_server.js';
import { stlFile } from './fakes/stl.js';
import { FakeLocks, FakeRecords, FakeTab } from './fakes/storage.js';
import { InThreadWorker } from './fakes/worker.js';
import { box, cylinder, rotationX, turned } from './geometry/shapes.js';
import { CONTRACT_PARTS } from './geometry/helpers.js';

const ME = example('wizard-front/me.json');
const TABLE = example('settings-table.json');

function fakePanel() {
  return {
    notices: [],
    notify(notice) { this.notices = this.notices.filter((n) => n.key !== notice.key).concat([notice]); },
    dropNotice(key) { this.notices = this.notices.filter((n) => n.key !== key); },
  };
}

function browser() {
  let n = 0;
  return { records: new FakeRecords(), locks: new FakeLocks(), clock: new FakeClock(), server: new FakeFrontServer(), tab: new FakeTab(), newId: () => `plate-${(n += 1)}` };
}

async function openPage(b = browser(), { profile = 'Standard' } = {}) {
  const store = createStore();
  const api = createApi({ transport: b.server.transport, clock: b.clock, version: 'v', currentGroup: () => store.get().group, random: () => 0.5 });
  const report = () => Promise.resolve(true);
  const storage = createStorage({ openRecords: () => b.records.open(), locks: b.locks.forTab('A'), tab: b.tab, clock: b.clock, newId: b.newId, report });
  const { plate, group } = await storage.begin({ user: ME.user.id, groups: ME.groups });
  const configuration = { ...example('configuration-default.json'), upload_units: 'mm' };
  store.set({
    user: ME.user, groups: ME.groups, group, plateId: plate.plate_id, step: plate.step, configuration, settingsTable: TABLE,
    printer: TABLE.catalog.printers[0], plate: { filament: 'PETG', profile },
  });
  const worker = new InThreadWorker();
  const geometry = createGeometryClient(worker.port, { report });
  const panel = fakePanel();
  const parts = createParts({ api, storage, geometry, store, panel, report });
  const layout = createLayout({ geometry, storage, store, parts, panel });
  await parts.resume();
  layout.resume();
  return { b, store, storage, geometry, worker, panel, parts, layout };
}

const file = (name, bytes) => ({ name, size: bytes.byteLength, arrayBuffer: async () => bytes });
const contractPart = (name) => {
  const bytes = readFileSync(join(CONTRACT_PARTS, name));
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
};
const boxPart = (header, size) => stlFile(box(...size), header);
// A rod 20 mm across and 200 mm long, modelled lying along y: it lies best standing on an end,
// since on its side it touches the plate along a line only.
const lyingRod = () => stlFile(turned(cylinder(64, 10, 200), rotationX(90)), 'rod');

async function addParts(page, files) {
  await page.parts.addFiles(files.map(([name, bytes]) => file(name, bytes)));
  await page.parts.idle();
}

async function enterLayout(page) {
  page.store.set({ step: 'layout' });
  await settleAll(page);
}

async function settleAll(page) {
  for (let k = 0; k < 5; k++) {
    await settle();
    await page.parts.idle();
    await page.layout.idle();
  }
}

const statusOf = (page) => page.layout.model().status;
const problemWhats = (page) => page.layout.model().problems.map((p) => p.what);
const ids = (page) => page.layout.model().instances.map((i) => i.id);
const inst = (page, n) => page.layout.model().instances[n];

async function moveTo(page, id, x, y) {
  page.layout.place([{ id, x, y }]);
  await page.layout.endDrag();
  await settleAll(page);
}

// ---- the plate's figures and its rules

test('the printer\'s plate comes from the table\'s catalog entry of the configuration\'s printer', () => {
  const state = { printer: TABLE.catalog.printers[0], configuration: { printer: 'Bambu Lab H2S 0.6 nozzle' } };
  assert.deepEqual(printerOf(state), { min: [0, 0], max: [340, 320], height: 340, name: 'Bambu Lab H2S 0.6 nozzle' });
  assert.equal(printerOf({ printer: null }), null);
});

test('supports are on by the user\'s change, else the profile\'s own override, else the table\'s value for its process', () => {
  const configuration = example('configuration-default.json');
  configuration.filaments[0].profiles[1].overrides = { enable_support: '1' };
  const state = { configuration, settingsTable: TABLE, plate: { filament: 'PETG', profile: 'Standard' } };
  assert.equal(supportsFor(state), false);
  assert.equal(supportsFor(state, { enable_support: '1' }), true);
  assert.equal(supportsFor({ ...state, plate: { filament: 'PETG', profile: 'Structural' } }), true);
  assert.equal(supportsFor({ ...state, plate: { filament: 'PETG', profile: 'Structural' } }, { enable_support: '0' }), false);
  const table = structuredClone(TABLE);
  table.process_values['0.24mm Balanced Quality @BBL H2S 0.6 nozzle'].enable_support = '1';
  assert.equal(supportsFor({ ...state, settingsTable: table }), true);
});

test('an instance\'s orientation on the plate is its angle and any turn about the vertical in how it lies', () => {
  assert.equal(plateAngle({ lay: [1, 0, 0, 0], angle: 37 }), 37);
  const c = Math.cos(Math.PI / 8), s = Math.sin(Math.PI / 8);
  assert.ok(Math.abs(plateAngle({ lay: [c, 0, 0, s], angle: 10 }) - 55) < 1e-9);
  // laid on its +x side: still square to the plate
  assert.ok(Math.abs(plateAngle({ lay: [Math.SQRT1_2, 0, -Math.SQRT1_2, 0], angle: 0 })) < 1e-9);
  assert.deepEqual(downOf([1, 0, 0, 0]).map((v) => Math.round(v)), [0, 0, -1]);
});

// ---- instances follow the parts

test('a part\'s instances join the plate when the Layout step is shown, lying their best way, arranged, and nothing is said', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 3);
  assert.equal(page.layout.model().instances.length, 0, 'not before the step is shown');
  await enterLayout(page);
  const m = page.layout.model();
  assert.equal(m.instances.length, 3);
  assert.deepEqual(m.instances.map((i) => i.label), ['Spacer #1', 'Spacer #2', 'Spacer #3']);
  assert.deepEqual(m.status, { ok: true, first: '✓ All 3 instances fit the plate.' });
  assert.deepEqual(m.notes, []);
  assert.deepEqual(m.problems, []);
  assert.deepEqual(m.selection, { text: '3 instances on the plate.' });
  assert.equal(m.figures, 'Bambu Lab H2S 0.6 nozzle: plate 340 × 320 mm, up to 340 mm tall, 5 mm apart');
  assert.equal(page.store.get().layoutProblem, null);
  // the pile about the plate's middle
  const xs = m.instances.map((i) => i.x), ys = m.instances.map((i) => i.y);
  assert.ok(Math.abs((Math.min(...xs) + Math.max(...xs)) / 2 - 170) < 25 && Math.abs((Math.min(...ys) + Math.max(...ys)) / 2 - 160) < 25);
  // and kept in the stored plate
  assert.equal(page.storage.plate().instances.length, 3);
});

test('one instance: the status line names it', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  await enterLayout(page);
  assert.equal(statusOf(page).first, '✓ Spacer #1 fits the plate.');
});

test('a raised quantity adds instances near the others, which stay where they are; a lowered one takes the last away', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  const before = page.layout.model().instances.map(({ id, x, y }) => ({ id, x, y }));
  page.store.set({ step: 'parts' });
  page.parts.setQuantity(page.parts.rows()[0].key, 4);
  await enterLayout(page);
  const after = page.layout.model().instances;
  assert.equal(after.length, 4);
  assert.deepEqual(after.slice(0, 2).map(({ id, x, y }) => ({ id, x, y })), before);
  assert.deepEqual(page.layout.model().problems, []);
  page.store.set({ step: 'parts' });
  page.parts.setQuantity(page.parts.rows()[0].key, 1);
  await enterLayout(page);
  assert.deepEqual(ids(page), [before[0].id]);
});

test('a part that arrives while the user is on the Layout step joins the plate at once', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  await enterLayout(page);
  await addParts(page, [['Bracket.stl', contractPart('bracket.stl')]]);
  await settleAll(page);
  assert.deepEqual(page.layout.model().instances.map((i) => i.label), ['Spacer #1', 'Bracket #1']);
  assert.deepEqual(page.layout.model().problems, []);
});

test('a removed part\'s instances leave the plate', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')], ['Bracket.stl', contractPart('bracket.stl')]]);
  await enterLayout(page);
  page.store.set({ step: 'parts' });
  await page.parts.remove(page.parts.rows()[0].key);
  await enterLayout(page);
  assert.deepEqual(page.layout.model().instances.map((i) => i.label), ['Bracket #1']);
});

test('the stored layout is taken up when the page opens again, every instance where it was', async () => {
  const b = browser();
  const page = await openPage(b);
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  await moveTo(page, ids(page)[1], 250, 250);
  const kept = page.layout.model().instances.map(({ lay, angle, x, y }) => ({ lay, angle, x, y }));
  await page.storage.written();
  b.locks.closeTab('A');                       // the refresh: the browser lets the tab's lock go
  const again = await openPage(b);
  again.store.set({ step: 'layout' });
  await settleAll(again);
  assert.deepEqual(again.layout.model().instances.map(({ lay, angle, x, y }) => ({ lay, angle, x, y })), kept);
});

test('a stored instance the page cannot use is dropped, and the part\'s quantity is made up with a new one', async () => {
  const b = browser();
  const page = await openPage(b);
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  const stored = page.storage.plate().instances;
  await page.storage.update({ instances: [stored[0], { ...stored[1], lay: [2, 0, 0, 0] }, { part: 'gone.mm', lay: [1, 0, 0, 0], angle: 0, x: 0, y: 0 }] });
  await page.storage.written();
  b.locks.closeTab('A');
  const again = await openPage(b);
  again.store.set({ step: 'parts' });
  again.store.set({ step: 'layout' });
  await settleAll(again);
  const m = again.layout.model();
  assert.equal(m.instances.length, 2);
  assert.deepEqual([m.instances[0].x, m.instances[0].y], [stored[0].x, stored[0].y]);
});

// ---- the placement rules and their messages

test('two instances too close: the pair named, the distance, the spacing, and Arrange as its button; Next held', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  const [a, b] = page.layout.model().instances;
  await moveTo(page, b.id, a.x, a.y + 33);     // the spacer is 30 mm deep: 3 mm apart
  const [problem] = page.layout.model().problems;
  assert.equal(problem.what, 'Spacer #1 and Spacer #2 are 3 mm apart; instances need 5 mm between them with supports off.');
  assert.equal(problem.todo, 'Drag one away, or press Arrange.');
  assert.equal(problem.action.label, 'Arrange');
  assert.deepEqual(problem.instances, [a.id, b.id]);
  assert.equal(statusOf(page).ok, false);
  assert.equal(statusOf(page).first, problem.what);
  assert.equal(statusOf(page).more, 'Fix ↓');
  assert.equal(page.store.get().layoutProblem, problem.what);
  assert.ok(page.layout.model().marked.has(a.id) && page.layout.model().marked.has(b.id));
  await problem.action.run();
  await settleAll(page);
  assert.deepEqual(page.layout.model().problems, []);
  assert.deepEqual(page.layout.model().notes.map((n) => [n.kind, n.what]), [['ok', 'Arranged 2 instances.']]);
  assert.equal(page.store.get().layoutProblem, null);
});

test('many instances too close: one message for all of them, each marked', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 3);
  await enterLayout(page);
  const all = page.layout.model().instances;
  page.layout.place(all.map((i, n) => ({ id: i.id, x: 100, y: 60 + 32 * n })));
  await page.layout.endDrag();
  await settleAll(page);
  const problems = page.layout.model().problems;
  assert.deepEqual(problems.map((p) => p.what), ['3 instances are closer than 5 mm with supports off.']);
  assert.equal(problems[0].todo, 'Press Arrange, or drag them apart.');
  assert.deepEqual(problems[0].instances, all.map((i) => i.id));
});

test('an instance across the plate\'s edge names the edge it crosses', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  await enterLayout(page);
  const [a] = page.layout.model().instances;
  await moveTo(page, a.id, 10, 160);
  assert.deepEqual(problemWhats(page), ['Spacer #1 is not fully on the plate: it crosses the left edge.']);
  assert.equal(page.layout.model().problems[0].todo, 'Drag it inward, or press Arrange.');
  await moveTo(page, a.id, 335, 318);
  assert.deepEqual(problemWhats(page), ['Spacer #1 is not fully on the plate: it crosses the right and back edges.']);
});

test('the status line counts the other problems: "+1 more ↓"', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 3);
  await enterLayout(page);
  const [a, b, c] = page.layout.model().instances;
  page.layout.place([{ id: a.id, x: 10, y: 160 }, { id: b.id, x: 200, y: 100 }, { id: c.id, x: 200, y: 133 }]);
  await page.layout.endDrag();
  await settleAll(page);
  assert.equal(page.layout.model().problems.length, 2);
  assert.equal(statusOf(page).more, '+1 more ↓');
  assert.equal(statusOf(page).first, 'Spacer #1 is not fully on the plate: it crosses the left edge.');
});

test('too tall: the height in both units for an inch part, the printer\'s limit, and Auto-orient as its button', async () => {
  const page = await openPage();
  await addParts(page, [['Post.stl', contractPart('post-341.stl')]]);
  await enterLayout(page);
  // it arrives lying down, its best way; put back as modelled it stands 341 mm
  page.layout.select(ids(page)[0]);
  const link = page.layout.model().link;
  assert.equal(link.label, 'Put back as modelled');
  await link.run();
  await settleAll(page);
  const [problem] = page.layout.model().problems;
  assert.equal(problem.what, 'Post #1 stands 341 mm tall; the printer prints up to 340 mm.');
  assert.equal(problem.todo, 'Lay it down another way, or press Auto-orient.');
  assert.equal(problem.action.label, 'Auto-orient');
  assert.equal(page.layout.model().link.label, 'Lay it the best way');
  await problem.action.run();
  await settleAll(page);
  assert.deepEqual(page.layout.model().problems, []);
  assert.equal(page.layout.model().link.label, 'Put back as modelled');
});

test('an inch part\'s figure against the printer\'s is in millimetres with its inches in brackets', () => {
  assert.equal(W.TOO_TALL('Shooter Hood Rib #1', 352.68, 'in', 340).what, 'Shooter Hood Rib #1 stands 352.7 mm (13.885 in) tall; the printer prints up to 340 mm.');
  assert.equal(W.TOO_LONG('Shooter Hood Rib #1', 'x', 352.68, 'in', 334, false, true).what,
    'Shooter Hood Rib #1 is 352.7 mm (13.885 in) from left to right as it is turned; the plate takes 334 mm.');
});

test('a part that arrives too long for the plate as it lies is turned to fit before it is first arranged; squared again, Turn it to fit turns it and arranges', async () => {
  const page = await openPage();
  await addParts(page, [['Rib.stl', boxPart('rib', [353, 10, 10])]]);
  await enterLayout(page);
  assert.equal(inst(page, 0).angle, 45);
  assert.deepEqual(page.layout.model().problems, []);
  // the user squares it with the rotation handle
  page.layout.place([{ id: inst(page, 0).id, x: 170, y: 160, angle: 0 }]);
  await page.layout.endDrag();
  await settleAll(page);
  const [problem] = page.layout.model().problems;
  assert.equal(problem.what, 'Rib #1 is not fully on the plate: it is 353 mm from left to right as it is turned; the plate takes 334 mm.');
  assert.equal(problem.todo, 'Turn it to fit turns it and arranges the plate again.');
  assert.equal(problem.action.label, 'Turn it to fit');
  await problem.action.run();
  await settleAll(page);
  assert.equal(inst(page, 0).angle, 45);
  assert.deepEqual(page.layout.model().problems, []);
  assert.deepEqual(page.layout.model().notes.map((n) => n.what), ['Turned Rib #1 and arranged 1 instance.']);
});

test('a part that fits the plate at no turn: the same first sentence, then "Lay it down another way.", no button', async () => {
  const page = await openPage();
  await addParts(page, [['Beam.stl', boxPart('beam', [460, 12, 12])]]);
  await enterLayout(page);
  const [problem] = page.layout.model().problems;
  assert.equal(problem.what, 'Beam #1 is 460 mm from left to right as it is turned; the plate takes 334 mm.');
  assert.equal(problem.todo, 'Lay it down another way.');
  assert.equal(problem.action, null);
});

// ---- Arrange

test('Arrange keeps a 37 degree instance at 37 degrees and says how many it arranged', async () => {
  const page = await openPage();
  await addParts(page, [['Bracket.stl', contractPart('bracket.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 3);
  await enterLayout(page);
  const [a] = page.layout.model().instances;
  page.layout.place([{ id: a.id, x: a.x, y: a.y, angle: 37.4 }]);
  await page.layout.endDrag();
  await settleAll(page);
  assert.equal(inst(page, 0).angle, 37, 'a turn is kept to a whole degree when the drag ends');
  const lay = inst(page, 0).lay;
  await page.layout.arrange();
  await settleAll(page);
  assert.equal(inst(page, 0).angle, 37);
  assert.deepEqual(inst(page, 0).lay, lay);
  assert.deepEqual(page.layout.model().notes.map((n) => n.what), ['Arranged 3 instances.']);
  assert.deepEqual(page.layout.model().problems, []);
});

test('Arrange that cannot fit everything says so, and offers to lay them the best way when that would fit all', async () => {
  const page = await openPage();
  await addParts(page, [['Rod.stl', lyingRod()]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 30);
  await enterLayout(page);
  // they arrive standing on an end, their best way, and all fit
  assert.deepEqual(page.layout.model().problems, []);
  assert.equal(page.layout.model().holds, null);
  page.layout.selectAll();
  await page.layout.model().link.run();      // Put back as modelled: lying on their sides
  await settleAll(page);
  await page.layout.arrange();
  await settleAll(page);
  const m = page.layout.model();
  const [note] = m.notes;
  assert.equal(note.kind, 'error');
  assert.match(note.what, /^Arrange placed (\d+) of 30 instances; (\d+) instances do not fit and wait beside the plate\.$/);
  assert.equal(note.todo, 'Arrange keeps how each instance lies. With 30 instances laid the best way, everything would fit. Or lower the quantities and print the rest on a new plate.');
  assert.deepEqual(note.actions.map((a) => a.label), ['Lay them the best way: all fit', 'Back to Parts']);
  assert.equal(m.status.ok, false);
  assert.match(m.status.first, /^\d+ instances do not fit on the plate\.$/);
  assert.equal(page.store.get().layoutProblem, m.status.first);
  // the instances Arrange left beside the plate have no message of their own
  assert.deepEqual(m.problems, []);
  page.layout.clearSelection();
  assert.match(page.layout.model().selection.text, /^\d+ instances on the plate, \d+ beside it\.$/);
  await note.actions[0].run();
  await settleAll(page);
  assert.deepEqual(page.layout.model().problems, []);
  assert.deepEqual(page.layout.model().notes.map((n) => n.what), ['Laid 30 instances the best way and arranged again: every instance now fits.']);
  assert.equal(page.store.get().layoutProblem, null);
});

// ---- laying an instance down

test('a lay-down that still fits says nothing; one that no longer fits is moved to the nearest free spot, and says so in green', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  const [a, b] = page.layout.model().instances;
  // stand the first on its 30 mm by 10 mm side, alone in the plate's corner: it fits
  await moveTo(page, a.id, 40, 40);
  await page.layout.layOnNormal(a.id, [1, 0, 0]);
  await settleAll(page);
  assert.deepEqual(page.layout.model().notes, []);
  assert.deepEqual([inst(page, 0).x, inst(page, 0).y], [40, 40]);
  // the second, 2 mm from the first's new footprint once stood on its side: it is moved
  await moveTo(page, b.id, 40 + 5 + 2 + 20, 40);
  await page.layout.layOnNormal(b.id, [0, -1, 0]);
  await settleAll(page);
  const note = page.layout.model().notes[0];
  assert.equal(note.kind, 'ok');
  assert.equal(note.what, 'Spacer #2 no longer fitted where it stood, so it was moved to the nearest free spot.');
  assert.deepEqual(page.layout.model().problems, []);
  assert.deepEqual([inst(page, 0).x, inst(page, 0).y], [40, 40], 'laying down never moves another instance');
});

test('a lay-down with no free spot waits beside the plate, in amber, the others where they were', async () => {
  const page = await openPage();
  await addParts(page, [['Slab.stl', boxPart('slab', [10, 250, 200])]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  // they arrive lying flat (200 by 250); stand them on the 10 mm side, as modelled, side by side
  page.layout.selectAll();
  await page.layout.model().link.run();
  await settleAll(page);
  const [a, b] = page.layout.model().instances;
  page.layout.place([{ id: a.id, x: 170, y: 160 }, { id: b.id, x: 240, y: 160 }]);
  await page.layout.endDrag();
  await settleAll(page);
  assert.deepEqual(page.layout.model().problems, []);
  const before = [inst(page, 0).x, inst(page, 0).y];
  await page.layout.layOnNormal(b.id, [-1, 0, 0]);      // flat: 200 by 250, no room either side of the first
  await settleAll(page);
  const note = page.layout.model().notes[0];
  assert.equal(note.kind, 'warn');
  assert.equal(note.what, 'Slab #2 no longer fits on the plate and waits beside it.');
  assert.equal(note.todo, 'No spot on the plate is free for it lying this way. The other instances stay where you put them; press Arrange to make room.');
  assert.deepEqual([inst(page, 0).x, inst(page, 0).y], before);
  assert.equal(inst(page, 1).beside, true);
  assert.deepEqual(page.layout.model().problems, []);
  assert.equal(page.layout.model().status.first, '1 instance does not fit on the plate.');
});

test('the messages about moves go when the user leaves the step; a problem stays', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  await page.layout.arrange();
  await settleAll(page);
  assert.equal(page.layout.model().notes.length, 1);
  const [a, b] = page.layout.model().instances;
  await moveTo(page, b.id, a.x, a.y + 32);
  page.store.set({ step: 'settings' });
  await settleAll(page);
  assert.deepEqual(page.layout.model().notes, []);
  assert.equal(page.layout.model().problems.length, 1);
  assert.ok(page.store.get().layoutProblem);
});

test('Auto-orient lays every instance its best way when none is selected, and arranges the plate again when it must', async () => {
  const page = await openPage();
  await addParts(page, [['Slab.stl', boxPart('slab', [10, 250, 200])]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  page.layout.selectAll();
  await page.layout.model().link.run();
  await settleAll(page);
  const [a, b] = page.layout.model().instances;
  page.layout.place([{ id: a.id, x: 170, y: 160 }, { id: b.id, x: 240, y: 160 }]);
  await page.layout.endDrag();
  page.layout.clearSelection();
  await settleAll(page);
  await page.layout.autoOrient();
  await settleAll(page);
  const m = page.layout.model();
  assert.ok(m.instances.every((i) => Math.abs(downOf(i.lay)[0]) > 0.999), 'both lie flat on a large face');
  assert.deepEqual(m.notes.map((n) => n.what), ['Arranged the plate again to make room.', 'Arrange placed 1 of 2 instances; 1 instance does not fit and waits beside the plate.']);
});

test('an instance Auto-orient lays down that is then too long for the plate is turned to fit', async () => {
  const page = await openPage();
  await addParts(page, [['Rib.stl', boxPart('rib', [353, 10, 10])]]);
  await enterLayout(page);
  page.layout.select(ids(page)[0]);
  // stood on an end (too tall: 353 mm), square to the plate
  await page.layout.layOnNormal(ids(page)[0], [-1, 0, 0]);
  await settleAll(page);
  page.layout.place([{ id: ids(page)[0], x: 170, y: 160, angle: 0 }]);
  await page.layout.endDrag();
  await settleAll(page);
  assert.equal(page.layout.model().problems[0].action.label, 'Auto-orient');
  await page.layout.model().problems[0].action.run();
  await settleAll(page);
  assert.equal(Math.round(page.layout.plateAngle(ids(page)[0])) % 90 !== 0, true, 'turned off the square');
  assert.deepEqual(page.layout.model().problems, []);
});

// ---- supports and the spacing

test('turning supports on after arranging moves nothing: the instances now too close get the usual message', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  const [a, b] = page.layout.model().instances;
  await moveTo(page, b.id, a.x, a.y + 37);     // 7 mm apart
  assert.deepEqual(page.layout.model().problems, []);
  const where = page.layout.model().instances.map(({ x, y }) => [x, y]);
  const plate = page.storage.plate();
  await page.storage.update({ settings: { ...plate.settings, changes: { enable_support: '1' } } });
  page.layout.settingsChanged();
  await settleAll(page);
  assert.deepEqual(page.layout.model().instances.map(({ x, y }) => [x, y]), where);
  assert.deepEqual(problemWhats(page), ['Spacer #1 and Spacer #2 are 7 mm apart; instances need 12 mm between them with supports on.']);
  assert.equal(page.layout.model().figures, 'Bambu Lab H2S 0.6 nozzle: plate 340 × 320 mm, up to 340 mm tall, 12 mm apart');
});

// ---- the selection

test('the selection line: one instance\'s name, footprint and height in its part\'s units; several move and turn together', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.parts.setQuantity(page.parts.rows()[0].key, 2);
  await enterLayout(page);
  page.layout.select(ids(page)[0]);
  assert.deepEqual(page.layout.model().selection, { strong: 'Spacer #1', text: ' 40 × 30 mm, 10 mm tall' });
  page.layout.select(ids(page)[1], 'toggle');
  assert.deepEqual(page.layout.model().selection, { strong: '2 instances', text: ' move and turn together' });
  page.layout.clearSelection();
  assert.deepEqual(page.layout.model().selection, { text: '2 instances on the plate.' });
  page.layout.selectAll();
  assert.deepEqual(page.layout.model().selected, ids(page));
});

test('the link: nothing when the instance lies as modelled and that is its best way', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  await enterLayout(page);
  page.layout.select(ids(page)[0]);
  assert.equal(page.layout.model().link, null);
});

test('the patches of a selected instance\'s part, found once', async () => {
  const page = await openPage();
  await addParts(page, [['Bracket.stl', contractPart('bracket.stl')]]);
  await enterLayout(page);
  const patches = await page.layout.patches(ids(page)[0]);
  assert.ok(patches.length >= 4);
  assert.ok(patches.every((p) => ['hull', 'box'].includes(p.kind) && p.normal.length === 3 && typeof p.height === 'number'));
  const posted = page.worker.posted.filter((m) => m.message.op === 'faces').length;
  await page.layout.patches(ids(page)[0]);
  assert.equal(page.worker.posted.filter((m) => m.message.op === 'faces').length, posted);
});

// ---- a worker that fails

test('a worker that has failed as a whole ends in its notification, never a frozen step', async () => {
  const page = await openPage();
  await addParts(page, [['Spacer.stl', contractPart('spacer.stl')]]);
  page.worker.fail(new Error('gone'));
  await enterLayout(page);
  const notice = page.panel.notices.find((n) => n.key === 'layout:wizard.layout_failed');
  assert.ok(notice);
  assert.equal(notice.what, 'PenguinSlicer could not work out the layout of this plate.');
  assert.equal(notice.todo, 'Reload the page; your parts, layout and settings are kept in this browser.');
});
