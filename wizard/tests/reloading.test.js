// Reloading for a new version (src/reloading.js; wizard/README-details.md, "Reloading for a new
// version"): the fake front server announces a newer version on its answers, and the page reloads
// itself only when the user moves between steps or after RELOAD_IDLE_S without input, never while
// a request of its own is pending, an open progress stream not counting.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createApi } from '../src/api.js';
import { RELOAD_IDLE_S } from '../src/page-constants.js';
import { createReloader, isNewer } from '../src/reloading.js';
import { createStore } from '../src/state.js';
import { FakeClock } from './fakes/clock.js';
import { FakeFrontServer, events, steps } from './fakes/front_server.js';

const OWN = '20261127T221405Z-ab12cd3';
const NEWER = '20261128T090000Z-ef45ab6';
const OLDER = '20261126T090000Z-0000000';

function page({ own = OWN, serverVersion = NEWER } = {}) {
  const clock = new FakeClock();
  const server = new FakeFrontServer({ version: serverVersion });
  const store = createStore();
  const api = createApi({ transport: server.transport, clock, version: own, random: () => 0.5 });
  const inputs = new Set();
  const order = [];
  const reloads = [];
  const reloader = createReloader({
    api, clock, store, version: own,
    onInput: (listener) => inputs.add(listener),
    beforeReload: async () => { order.push('marked'); },
    reload: () => { order.push('reload'); reloads.push(clock.elapsed); },
  });
  const touch = () => { for (const listener of inputs) listener(); };
  return { clock, server, store, api, reloader, reloads, order, touch };
}

test('versions are compared by the part before the hyphen; a version of another form is never newer', () => {
  assert.equal(isNewer(NEWER, OWN), true);
  assert.equal(isNewer(OWN, OWN), false);
  assert.equal(isNewer(OLDER, OWN), false);
  assert.equal(isNewer('20261127T221405Z-fffffff', OWN), false, 'the same moment with another commit is not newer');
  assert.equal(isNewer(NEWER, ''), false, 'a page that does not know its own version never reloads');
  assert.equal(isNewer('99999999', OWN), false);
  assert.equal(isNewer(null, OWN), false);
});

test('with no input, a newer version reloads the page at exactly 120 s after the last input, and not at 119.9 s', async () => {
  const p = page();
  await p.api.get('/api/me');
  await p.clock.advance(RELOAD_IDLE_S * 1000 - 100);
  assert.deepEqual(p.reloads, []);
  await p.clock.advance(100);
  assert.deepEqual(p.reloads, [RELOAD_IDLE_S * 1000]);
  assert.deepEqual(p.order, ['marked', 'reload'], 'the reload is marked as the page\'s own before it is made');
});

test('each input moves the 120 s on, and the page reloads 120 s after the last one', async () => {
  const p = page();
  await p.api.get('/api/me');
  await p.clock.advance(100 * 1000);
  p.touch();
  await p.clock.advance(100 * 1000);
  assert.deepEqual(p.reloads, [], 'touched 100 s ago: not yet');
  await p.clock.advance(20 * 1000);
  assert.deepEqual(p.reloads, [220 * 1000]);
});

test('a move between steps reloads at once', async () => {
  const p = page();
  await p.api.get('/api/me');
  p.touch();
  p.store.set({ step: 'settings' });
  await p.clock.advance(0);
  assert.deepEqual(p.reloads, [0]);
});

test('the reload is marked after every listener of the move between steps has run, so the step moved to is written first', async () => {
  const p = page();
  await p.api.get('/api/me');
  p.store.subscribe((state, before) => { if (state.step !== before.step) p.order.push(`written ${state.step}`); });
  p.store.set({ step: 'layout' });
  await p.clock.advance(0);
  assert.deepEqual(p.order, ['written layout', 'marked', 'reload']);
});

test('a move between steps before any newer version is heard reloads nothing', async () => {
  const p = page({ serverVersion: OWN });
  await p.api.get('/api/me');
  p.store.set({ step: 'settings' });
  await p.clock.advance(RELOAD_IDLE_S * 1000 * 3);
  assert.deepEqual(p.reloads, []);
});

test('no reload while a request of the page\'s is pending, and a reload once it is answered', async () => {
  const p = page();
  await p.api.get('/api/me');
  const held = steps.hold();
  p.server.script('GET', '/api/configuration', held);
  const answer = p.api.get('/api/configuration');
  await p.clock.advance(0);
  p.store.set({ step: 'layout' });
  await p.clock.advance(10 * 1000);
  assert.deepEqual(p.reloads, [], 'the request is still pending');
  p.server.made('GET', '/api/configuration')[0].held.release();
  await answer;
  await p.clock.advance(0);
  assert.deepEqual(p.reloads, [10 * 1000]);
});

test('a request retried past the 120 s holds the reload until it is answered', async () => {
  const p = page();
  await p.api.get('/api/me');
  p.server.script('GET', '/api/configuration', ...Array.from({ length: 12 }, () => steps.drop()));
  const answer = p.api.get('/api/configuration');
  await p.clock.advance(RELOAD_IDLE_S * 1000 + 5000);
  assert.deepEqual(p.reloads, [], 'retried quietly and still pending at 125 s');
  await p.clock.advance(200 * 1000);
  assert.equal((await answer).ok, true);
  assert.equal(p.reloads.length, 1);
  assert.ok(p.reloads[0] > RELOAD_IDLE_S * 1000);
});

test('a request answered after the user moves again holds the step change\'s reload for the next moment', async () => {
  const p = page();
  await p.api.get('/api/me');
  p.server.script('GET', '/api/configuration', steps.hold());
  const answer = p.api.get('/api/configuration');
  await p.clock.advance(0);
  p.store.set({ step: 'layout' });
  await p.clock.advance(1000);
  p.touch();                                     // the user is at work on the new step
  p.server.made('GET', '/api/configuration')[0].held.release();
  await answer;
  await p.clock.advance(0);
  assert.deepEqual(p.reloads, [], 'not under a user who has just moved');
  await p.clock.advance(RELOAD_IDLE_S * 1000);
  assert.equal(p.reloads.length, 1, 'then at the 120 s');
});

test('an open progress stream does not hold the reload', async () => {
  const p = page();
  p.server.script('GET', /\/events$/, steps.stream([events.version(NEWER)]));
  const answer = await p.api.get('/api/slices/3f9a1c2b/events', { expect: 'stream' });
  assert.equal(answer.ok, true);
  answer.stream.chunks(() => {});
  p.store.set({ step: 'preview' });
  await p.clock.advance(0);
  assert.equal(p.reloads.length, 1);
});

test('a newer version told by a progress stream\'s version event counts as one on an answer', async () => {
  const p = page({ serverVersion: OWN });
  await p.api.get('/api/me');
  p.api.heard(NEWER);
  p.store.set({ step: 'settings' });
  await p.clock.advance(0);
  assert.equal(p.reloads.length, 1);
});

test('an older version, or the page\'s own, does nothing', async () => {
  for (const version of [OLDER, OWN]) {
    const p = page({ serverVersion: version });
    await p.api.get('/api/me');
    p.store.set({ step: 'settings' });
    await p.clock.advance(RELOAD_IDLE_S * 1000 * 2);
    assert.deepEqual(p.reloads, [], version);
  }
});

test('a reload that would lose the tab\'s work is not made, and the next moment after the work is safe makes it', async () => {
  const clock = new FakeClock();
  const server = new FakeFrontServer({ version: NEWER });
  const store = createStore();
  const api = createApi({ transport: server.transport, clock, version: OWN, random: () => 0.5 });
  const inputs = new Set();
  let keeps = false;
  const reloads = [];
  createReloader({
    api, clock, store, version: OWN, onInput: (l) => inputs.add(l),
    beforeReload: async () => keeps,
    reload: () => reloads.push(clock.elapsed),
  });
  await api.get('/api/me');
  store.set({ step: 'layout' });
  await clock.advance(RELOAD_IDLE_S * 1000 * 3);
  assert.deepEqual(reloads, [], 'neither the move nor 360 s idle reloads a page holding unsaved work');
  keeps = true;                                   // the unsaved part removed
  for (const listener of inputs) listener();
  await clock.advance(RELOAD_IDLE_S * 1000 - 1);
  assert.deepEqual(reloads, []);
  await clock.advance(1);
  assert.deepEqual(reloads, [RELOAD_IDLE_S * 1000 * 4], 'then 120 s after the last input');
  store.set({ step: 'settings' });
  await clock.advance(RELOAD_IDLE_S * 1000);
  assert.equal(reloads.length, 1, 'once');
});

test('a move between steps, once the work is safe, reloads after a reload was held', async () => {
  const p = page();
  let keeps = false;
  const reloads = [];
  const store = createStore();
  createReloader({
    api: p.api, clock: p.clock, store, version: OWN, onInput: () => {},
    beforeReload: async () => keeps, reload: () => reloads.push(p.clock.elapsed),
  });
  await p.api.get('/api/me');
  store.set({ step: 'layout' });
  await p.clock.advance(1000);
  assert.deepEqual(reloads, []);
  keeps = true;
  store.set({ step: 'settings' });
  await p.clock.advance(0);
  assert.deepEqual(reloads, [1000]);
});

test('the page reloads once, however many moments come while the reload is being made', async () => {
  const p = page();
  let finish;
  const marking = new Promise((resolve) => { finish = resolve; });
  const reloads = [];
  const store = createStore();
  const inputs = new Set();
  createReloader({
    api: p.api, clock: p.clock, store, version: OWN, onInput: (l) => inputs.add(l),
    beforeReload: () => marking, reload: () => reloads.push(p.clock.elapsed),
  });
  await p.api.get('/api/me');
  store.set({ step: 'settings' });
  store.set({ step: 'layout' });
  await p.clock.advance(RELOAD_IDLE_S * 1000);
  finish();
  await p.clock.advance(0);
  assert.equal(reloads.length, 1);
});
