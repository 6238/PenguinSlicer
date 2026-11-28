// The browser's storage (src/storage.js; wizard/README-details.md, "What the browser keeps" and
// "Which plate a tab shows"): a plate for each tab, kept through a refresh; a new tab taking up
// only a plate no other tab holds and used less than 12 hours ago; the locks the browser releases
// when a tab closes; a plate no tab holds dropped at 12 hours; `owner` stored from the start and
// every plate cleared for a different user; a refused write and a cleared storage, each with one
// report. Several tabs are several pages on one fake storage, with the fake of the browser's locks.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { PLATE_UNUSED_H, PLATE_FORMAT, createStorage, plateLock } from '../src/storage.js';
import { FakeClock } from './fakes/clock.js';
import { FakeLocks, FakeRecords, FakeTab } from './fakes/storage.js';

const USER = '5f0c2a9e1b7d4c3a8e6f1234';
const OTHER_USER = '0000aaaa1111bbbb2222cccc';
const GROUPS = [{ id: '61a9c0d2e4b7f80012345678', name: '6238 (Popcorn Penguins)' }, { id: '6202bb11c0ffee0098765432', name: 'FRC 1678' }];
const HOUR = 3600 * 1000;

// One browser: one storage and one set of locks shared by its tabs, and one clock.
function browser() {
  let n = 0;
  return {
    records: new FakeRecords(),
    locks: new FakeLocks(),
    clock: new FakeClock(),
    reports: [],
    newId: () => { n += 1; return `plate-${n}`; },
  };
}

// One tab of that browser, opened (or refreshed, given the same `tab`): its storage module begun
// for `user`.
async function openTab(b, name, { tab = new FakeTab(), user = USER, groups = GROUPS, locks = b.locks.forTab(name) } = {}) {
  const storage = createStorage({
    openRecords: () => b.records.open(), locks, tab, clock: b.clock, newId: b.newId,
    report: (what, fields = {}) => b.reports.push({ tab: name, what, ...fields }),
  });
  const begun = await storage.begin({ user, groups });
  return { name, tab, storage, ...begun };
}

// A refresh: the browser releases the tab's locks, keeps its sessionStorage, and the page opens again.
async function refresh(b, t) {
  b.locks.closeTab(t.name);
  return openTab(b, t.name, { tab: t.tab });
}

const bytes = (n, fill) => new Uint8Array(n).fill(fill).buffer;

test('the figure of the 12 hours is the details file\'s', () => {
  assert.equal(PLATE_UNUSED_H, 12);
});

test('the first opening stores the owner from the start and begins an empty plate, held and named in the tab', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  assert.equal(b.records.value('owner'), USER);
  assert.equal(a.plate.plate_id, 'plate-1');
  assert.deepEqual(a.plate, {
    format: PLATE_FORMAT, plate_id: 'plate-1', user: USER, group: GROUPS[0].id, parts: [], instances: [],
    settings: { filament: null, profile: null, changes: {} }, slice: null, step: 'parts', advanced: false,
    last_used_ms: b.clock.now(),
  });
  assert.equal(a.group, GROUPS[0].id);
  assert.deepEqual(b.records.value('plates/plate-1'), a.plate);
  assert.equal(a.tab.get('penguinslicer.plate_id'), 'plate-1');
  assert.deepEqual(b.locks.heldBy('A'), [plateLock('plate-1')]);
  assert.deepEqual(b.reports, []);
});

test('a refresh keeps the tab\'s plate, with every change written at once', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.update({ step: 'layout', settings: { filament: 'PLA', profile: 'Standard', changes: { wall_loops: '4' } } });
  const again = await refresh(b, a);
  assert.equal(again.plate.plate_id, 'plate-1');
  assert.equal(again.plate.step, 'layout');
  assert.deepEqual(again.plate.settings, { filament: 'PLA', profile: 'Standard', changes: { wall_loops: '4' } });
});

test('two tabs open at once each work with their own plate, and neither writes over the other', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  const c = await openTab(b, 'B');
  assert.notEqual(a.plate.plate_id, c.plate.plate_id);
  await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  await c.storage.update({ step: 'settings' });
  assert.equal(b.records.value(`plates/${c.plate.plate_id}`).parts.length, 0);
  assert.equal(b.records.value(`plates/${a.plate.plate_id}`).parts.length, 1);
  assert.equal(b.records.value(`plates/${a.plate.plate_id}`).step, 'parts');
});

test('a closed tab\'s lock is released, and a newly opened tab takes up its plate', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.addPart({ sha256: 'aa', units: 'in', name: 'Gusset Plate' }, bytes(84, 2));
  b.locks.closeTab('A');
  const c = await openTab(b, 'C');
  assert.equal(c.plate.plate_id, a.plate.plate_id);
  assert.equal(c.plate.parts[0].name, 'Gusset Plate');
  assert.deepEqual(new Uint8Array(await c.storage.partBytes('aa', 'in')), new Uint8Array(bytes(84, 2)));
});

test('a new tab takes up the most recently used plate that no tab holds', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  const c = await openTab(b, 'B');
  await b.clock.advance(HOUR);
  await a.storage.update({ step: 'settings' });            // A's plate used most recently
  b.locks.closeTab('A');
  b.locks.closeTab('B');
  const d = await openTab(b, 'D');
  assert.equal(d.plate.plate_id, a.plate.plate_id);
  const e = await openTab(b, 'E');
  assert.equal(e.plate.plate_id, c.plate.plate_id);
  const f = await openTab(b, 'F');
  assert.equal(f.plate.plate_id, 'plate-3');                // none left: an empty plate
});

test('a plate used 11 h 59 min ago is taken up; one used 12 h ago is not, and is dropped', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  b.locks.closeTab('A');
  await b.clock.advance(12 * HOUR - 60 * 1000);
  const c = await openTab(b, 'C');
  assert.equal(c.plate.plate_id, a.plate.plate_id);         // 11 h 59 min: taken up, its time of use moved on

  const b2 = browser();
  const a2 = await openTab(b2, 'A');
  await a2.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  b2.locks.closeTab('A');
  await b2.clock.advance(12 * HOUR);
  const c2 = await openTab(b2, 'C');
  assert.notEqual(c2.plate.plate_id, a2.plate.plate_id);    // 12 h: not taken up
  assert.equal(b2.records.value(`plates/${a2.plate.plate_id}`), undefined);   // and dropped, bytes and all
  assert.deepEqual(b2.records.keys().filter((k) => k.includes(a2.plate.plate_id)), []);
});

test('a plate an open tab holds is never dropped under it, however long unused', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await b.clock.advance(30 * HOUR);
  const c = await openTab(b, 'C');                           // C's opening checks for plates to drop
  assert.notEqual(c.plate.plate_id, a.plate.plate_id);
  assert.ok(b.records.value(`plates/${a.plate.plate_id}`));
  await a.storage.update({ step: 'settings' });
  assert.equal(b.records.value(`plates/${a.plate.plate_id}`).step, 'settings');
});

test('a duplicated tab, whose sessionStorage names a plate the first tab holds, begins a plate of its own', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  const copy = await openTab(b, 'A-copy', { tab: a.tab.duplicate() });
  assert.notEqual(copy.plate.plate_id, a.plate.plate_id);
  assert.equal(copy.tab.get('penguinslicer.plate_id'), copy.plate.plate_id);
  assert.equal(a.tab.get('penguinslicer.plate_id'), a.plate.plate_id);
});

test('a different user\'s sign-in clears every stored plate, the upload units and the current group', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  await a.storage.setChoice('uploadUnits', 'mm');
  await a.storage.setChoice('currentGroup', GROUPS[1].id);
  b.locks.closeTab('A');
  const c = await openTab(b, 'C', { user: OTHER_USER, groups: [{ id: OTHER_USER, name: 'Sam Lee' }] });
  assert.equal(b.records.value('owner'), OTHER_USER);
  assert.deepEqual(b.records.keys(), ['owner', `plates/${c.plate.plate_id}`]);
  assert.equal(c.plate.parts.length, 0);
  assert.equal(c.plate.user, OTHER_USER);
  assert.equal(await c.storage.choice('uploadUnits'), null);
  assert.deepEqual(b.reports, []);
});

test('the same user opening again clears nothing', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.setChoice('uploadUnits', 'mm');
  b.locks.closeTab('A');
  const c = await openTab(b, 'C');
  assert.equal(await c.storage.choice('uploadUnits'), 'mm');
  assert.equal(c.plate.plate_id, a.plate.plate_id);
});

test('a refreshed tab goes on in its own plate\'s group when the user still has it; a new tab takes up only a plate of its current group', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.update({ group: GROUPS[1].id });
  const again = await refresh(b, a);
  assert.equal(again.group, GROUPS[1].id);
  assert.equal(again.plate.plate_id, a.plate.plate_id);
  b.locks.closeTab('A');
  const c = await openTab(b, 'C');                           // its current group is the first
  assert.equal(c.group, GROUPS[0].id);
  assert.notEqual(c.plate.plate_id, a.plate.plate_id);
  const d = await openTab(b, 'D', { tab: again.tab, groups: [GROUPS[0]] });   // the group is gone
  assert.equal(d.group, GROUPS[0].id);
});

test('the stored current group is the group a newly opened tab starts in, when the user has it', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.setChoice('currentGroup', GROUPS[1].id);
  const c = await openTab(b, 'C');
  assert.equal(c.group, GROUPS[1].id);
  await a.storage.setChoice('currentGroup', 'not-a-group-of-the-user');
  const d = await openTab(b, 'D');
  assert.equal(d.group, GROUPS[0].id);
});

test('25 parts are stored with their bytes exactly and come back after a refresh', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  for (let i = 0; i < 25; i += 1) {
    const { saved } = await a.storage.addPart({ sha256: `h${i}`, units: i % 2 ? 'in' : 'mm', name: `part ${i}`, record: { sha256: `h${i}` } }, bytes(84 + 50 * i, i));
    assert.equal(saved, true);
  }
  const again = await refresh(b, a);
  assert.equal(again.plate.parts.length, 25);
  for (let i = 0; i < 25; i += 1) {
    assert.deepEqual(again.plate.parts[i], { sha256: `h${i}`, units: i % 2 ? 'in' : 'mm', name: `part ${i}`, record: { sha256: `h${i}` }, saved: true });
    assert.deepEqual(new Uint8Array(await again.storage.partBytes(`h${i}`, i % 2 ? 'in' : 'mm')), new Uint8Array(bytes(84 + 50 * i, i)));
  }
});

test('a part removed takes its bytes with it', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  await a.storage.removePart('aa', 'mm');
  assert.deepEqual(a.storage.plate().parts, []);
  assert.equal(await a.storage.partBytes('aa', 'mm'), null);
  assert.deepEqual(b.records.keys().filter((k) => k.startsWith('part-bytes/')), []);
});

test('a part the browser refuses to store is still added, marked unsaved, kept in memory, with one storage_refused report', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  b.records.refuse('part-bytes/');
  const { saved } = await a.storage.addPart({ sha256: 'bb', units: 'mm', name: 'Big part' }, bytes(84, 3));
  assert.equal(saved, false);
  assert.deepEqual(a.storage.plate().parts, [{ sha256: 'bb', units: 'mm', name: 'Big part', saved: false }]);
  assert.deepEqual(new Uint8Array(await a.storage.partBytes('bb', 'mm')), new Uint8Array(bytes(84, 3)));
  assert.equal(b.reports.length, 1);
  assert.equal(b.reports[0].what, 'storage_refused');
  assert.equal(b.reports[0].part_sha256, 'bb');
  assert.match(b.reports[0].detail, /QuotaExceededError/);
  // A refresh loses it, as the line on its row says.
  const again = await refresh(b, a);
  assert.deepEqual(again.plate.parts, []);
});

test('a refused write of the plate itself gives one report however many writes fail', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  b.records.refuse('plates/');
  await a.storage.update({ step: 'settings' });
  await a.storage.update({ step: 'layout' });
  assert.equal(a.storage.plate().step, 'layout');
  assert.deepEqual(b.reports.map((r) => r.what), ['storage_refused']);
  assert.equal(b.reports[0].part_sha256, undefined);
});

test('a storage the browser has cleared opens with an empty plate and one storage_cleared report', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  b.records.clearAll();
  const again = await refresh(b, a);
  assert.equal(again.plate.parts.length, 0);
  assert.notEqual(again.plate.plate_id, a.plate.plate_id);
  assert.deepEqual(b.reports.map((r) => r.what), ['storage_cleared']);
  assert.equal(b.records.value('owner'), USER);
  // Opening once more reports nothing more.
  await refresh(b, again);
  assert.equal(b.reports.length, 1);
});

test('a storage the browser will not open: the page works from memory, with one storage_refused report', async () => {
  const b = browser();
  b.records.unavailable = true;
  const a = await openTab(b, 'A');
  assert.equal(a.plate.parts.length, 0);
  assert.deepEqual(b.reports.map((r) => r.what), ['storage_refused']);
  const { saved } = await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  assert.equal(saved, false);
  await a.storage.update({ step: 'settings' });
  assert.equal(a.storage.plate().step, 'settings');
  assert.deepEqual(new Uint8Array(await a.storage.partBytes('aa', 'mm')), new Uint8Array(bytes(84, 1)));
  assert.deepEqual(b.reports.map((r) => r.what), ['storage_refused']);
});

test('without the browser\'s locks a tab keeps its own plate through a refresh and never takes up another', async () => {
  const b = browser();
  const a = await openTab(b, 'A', { locks: null });
  const again = await openTab(b, 'A', { tab: a.tab, locks: null });
  assert.equal(again.plate.plate_id, a.plate.plate_id);
  const c = await openTab(b, 'C', { locks: null });
  assert.notEqual(c.plate.plate_id, a.plate.plate_id);
});

test('a plate written by a later page, in a format this page does not know, is left alone', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  const record = { ...b.records.value(`plates/${a.plate.plate_id}`), format: PLATE_FORMAT + 1 };
  b.records.map.set(`plates/${a.plate.plate_id}`, record);
  b.locks.closeTab('A');
  const c = await openTab(b, 'C');
  assert.notEqual(c.plate.plate_id, a.plate.plate_id);
  assert.deepEqual(b.records.value(`plates/${a.plate.plate_id}`), record);
});

test('a stored plate of this page\'s format that the page cannot read is dropped, never taken up, with one page_failed report', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  const good = b.records.value(`plates/${a.plate.plate_id}`);
  b.locks.closeTab('A');
  b.records.map.set('plates/no-list', { ...good, plate_id: 'no-list', parts: { 0: 'not a list' }, last_used_ms: good.last_used_ms + 2 });
  b.records.map.set('part-bytes/no-list/aa.mm', bytes(84, 1));
  const { settings, ...withoutSettings } = good;
  b.records.map.set('plates/no-settings', { ...withoutSettings, plate_id: 'no-settings', last_used_ms: good.last_used_ms + 1 });
  // The tab names the broken plate, as a refresh of its tab would.
  const c = await openTab(b, 'C', { tab: new FakeTab({ 'penguinslicer.plate_id': 'no-list' }) });
  assert.equal(c.plate.plate_id, a.plate.plate_id);          // the readable plate is taken up
  assert.equal(c.plate.parts.length, 1);
  assert.deepEqual(b.records.keys().filter((k) => k.includes('no-list') || k.includes('no-settings')), []);
  assert.deepEqual(b.reports.map((r) => r.what), ['page_failed']);
  assert.match(b.reports[0].detail, /2 stored plates/);
  assert.equal(c.tab.get('penguinslicer.plate_id'), a.plate.plate_id);
});

test('a stored plate the page cannot read that another tab holds is left alone', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  const record = { ...b.records.value(`plates/${a.plate.plate_id}`), parts: null };
  b.records.map.set(`plates/${a.plate.plate_id}`, record);
  const c = await openTab(b, 'C');
  assert.notEqual(c.plate.plate_id, a.plate.plate_id);
  assert.deepEqual(b.records.value(`plates/${a.plate.plate_id}`), record);
});

test('New plate drops the old plate while still holding its lock, so no tab can take it up half-deleted', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  const old = a.plate.plate_id;
  await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  const heldWhileDeleting = [];
  const forget = b.records.map.delete.bind(b.records.map);
  b.records.map.delete = (key) => {
    if (key.includes(old)) heldWhileDeleting.push(b.locks.heldBy('A').includes(plateLock(old)));
    return forget(key);
  };
  await a.storage.newPlate();
  assert.deepEqual(heldWhileDeleting, [true, true]);
  assert.equal(b.locks.heldBy('A').includes(plateLock(old)), false);
});

test('New plate drops the plate, bytes and all, and begins another with a new id, keeping the settings when asked', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  await a.storage.addPart({ sha256: 'aa', units: 'mm', name: 'Bracket' }, bytes(84, 1));
  await a.storage.update({ step: 'layout', settings: { filament: 'PLA', profile: 'Standard', changes: { brim_type: 'no_brim' } } });
  const next = await a.storage.newPlate({ keepSettings: true });
  assert.notEqual(next.plate_id, a.plate.plate_id);
  assert.deepEqual(next.parts, []);
  assert.equal(next.step, 'parts');
  assert.deepEqual(next.settings, { filament: 'PLA', profile: 'Standard', changes: { brim_type: 'no_brim' } });
  assert.deepEqual(b.records.keys(), ['owner', `plates/${next.plate_id}`]);
  assert.deepEqual(b.locks.heldBy('A'), [plateLock(next.plate_id)]);
  assert.equal(a.tab.get('penguinslicer.plate_id'), next.plate_id);
  const cleared = await a.storage.newPlate({ group: GROUPS[1].id });
  assert.deepEqual(cleared.settings, { filament: null, profile: null, changes: {} });
  assert.equal(cleared.group, GROUPS[1].id);
});

test('a write after another waits its turn, so the last change is the one kept', async () => {
  const b = browser();
  const a = await openTab(b, 'A');
  const writes = [a.storage.update({ step: 'settings' }), a.storage.update({ step: 'layout' }), a.storage.update({ step: 'preview' })];
  await Promise.all(writes);
  assert.equal(b.records.value(`plates/${a.plate.plate_id}`).step, 'preview');
});
