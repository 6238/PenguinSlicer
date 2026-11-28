// The sign-in trip (src/signing-in.js; wizard/README-details.md, "Signing in and signing out"):
// the first refusal notes the trip in the tab and goes to /signin with the page's address to
// come back to, at a quiet moment; a refusal while the note stands, on the page loaded again
// after the trip, is a trip that failed, shown and not made again; an answer of a signed-in
// request clears the note.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { SIGN_IN_TRIP, createSignInTrip, quietMoments } from '../src/signing-in.js';

// A window and a document that the test fires events on.
function page() {
  const listeners = new Map();
  const target = () => ({
    addEventListener: (type, fn) => listeners.set(type, [...(listeners.get(type) ?? []), fn]),
  });
  const win = target();
  const doc = { ...target(), activeElement: { tagName: 'BODY' } };
  const fire = (type, event = {}) => { for (const fn of listeners.get(type) ?? []) fn(event); };
  return { win, doc, fire };
}

test('a quiet moment: no pointer down and no field being typed in', async () => {
  const { win, doc, fire } = page();
  const whenQuiet = quietMoments(win, doc);
  const ran = [];
  whenQuiet(() => ran.push('now'));
  assert.deepEqual(ran, ['now']);
  fire('pointerdown', { pointerId: 1 });
  whenQuiet(() => ran.push('after the drag'));
  assert.deepEqual(ran, ['now']);
  doc.activeElement = { tagName: 'INPUT', type: 'text' };
  fire('pointerup', { pointerId: 1 });
  assert.deepEqual(ran, ['now'], 'a field still being typed in');
  doc.activeElement = { tagName: 'INPUT', type: 'checkbox' };
  fire('focusout');
  await Promise.resolve();
  assert.deepEqual(ran, ['now', 'after the drag']);
});

// One page load: its trip, over a tab kept across loads.
function load(kept, { here = '/', whenQuiet } = {}) {
  const tab = { get: (name) => (kept.has(name) ? kept.get(name) : null), set: (name, value) => kept.set(name, String(value)) };
  const went = [];
  const trip = createSignInTrip({ tab, clock: { now: () => 1_000 }, here: () => here, go: (address) => went.push(address), whenQuiet });
  return { trip, went };
}

test('the first refusal notes the trip and goes to sign in, coming back to the same address', () => {
  const kept = new Map();
  const { trip, went } = load(kept, { here: '/?in=x&y=1' });
  assert.equal(trip.refused(), true);
  assert.deepEqual(went, ['/signin?return=%2F%3Fin%3Dx%26y%3D1']);
  assert.equal(kept.get(SIGN_IN_TRIP), '1000');
});

test('the page leaves only at a quiet moment, and once, whatever else is refused meanwhile', () => {
  const kept = new Map();
  const waiting = [];
  const { trip, went } = load(kept, { whenQuiet: (run) => waiting.push(run) });
  assert.equal(trip.refused(), true);
  assert.equal(trip.refused(), true, 'another request refused while the page waits to leave waits too');
  assert.deepEqual(went, []);
  assert.equal(kept.has(SIGN_IN_TRIP), false);
  trip.answered();
  assert.equal(waiting.length, 1);
  waiting[0]();
  assert.equal(went.length, 1);
  assert.equal(kept.get(SIGN_IN_TRIP), '1000');
});

test('the page loaded again after its trip and refused again does not leave: the refusal is shown', () => {
  const kept = new Map();
  load(kept).trip.refused();
  const { trip, went } = load(kept);
  assert.equal(trip.refused(), false);
  assert.deepEqual(went, [], 'a browser that withholds the cookie makes one trip only');
});

test('an answer of a signed-in request clears the note, so a later refusal makes the trip again', () => {
  const kept = new Map();
  load(kept).trip.refused();
  const { trip, went } = load(kept);
  trip.answered();
  assert.equal(kept.get(SIGN_IN_TRIP), '');
  assert.equal(trip.refused(), true);
  assert.equal(went.length, 1);
});
