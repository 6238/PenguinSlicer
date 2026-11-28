// One drawing summary for each use of a view (wizard/README-details.md, "What the wizard reports
// about itself"; contracts/wizard-front-server.md, "POST /api/reports/drawing"): the Layout step and
// the Preview step, built on a fake document with a fake view, each begin a use of their view when
// the step is shown and send exactly one summary when the user leaves it, a second use included.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createLayoutStep } from '../src/panel/layout-step.js';
import { createPreviewStep } from '../src/panel/preview-step.js';
import { createStore } from '../src/state.js';
import { FakeClock, settle } from './fakes/clock.js';
import { installDocument } from './fakes/dom.js';

function fakeFrames() {
  let t = 1000;
  return { now: () => t, move: (ms) => { t += ms; }, next: () => 1, cancel: () => {} };
}

// ---- the Layout step

function layoutPage({ step = 'parts' } = {}) {
  const { section } = installDocument();
  const store = createStore();
  store.set({ step });
  const reported = [];
  let uses = 0;
  let views = 0;
  const layout = {
    model: () => ({ status: { ok: true, first: '' }, selected: [], selection: { strong: null, text: '' }, link: null, notes: [], problems: [], figures: '' }),
    subscribe: () => {}, arrange: () => {}, autoOrient: () => {}, select: () => {},
  };
  const createView = () => {
    views += 1;
    let using = null;
    return {
      beginUse() { uses += 1; using = uses; },
      endUse() { if (using === null) return null; const s = { view: 'layout', use: using }; using = null; return s; },
      resize() {}, sync() {}, zoomToInstances() {}, viewPlate() {}, topView() {},
    };
  };
  createLayoutStep(section, {
    layout, parts: { rows: () => [] }, geometry: {}, frames: fakeFrames(), store, createView,
    reportDrawing: (s) => reported.push(s),
  });
  return { store, reported, views: () => views };
}

test('the Layout step sends one drawing summary for each use of its view, a second use included', () => {
  const p = layoutPage();
  assert.deepEqual(p.reported, [], 'the view is not yet in sight');
  p.store.set({ step: 'layout' });
  assert.deepEqual(p.reported, []);
  p.store.set({ step: 'settings' });
  assert.deepEqual(p.reported, [{ view: 'layout', use: 1 }], 'leaving the step sends the first use');
  p.store.set({ step: 'parts' });
  assert.equal(p.reported.length, 1, 'a move between two other steps sends nothing');
  p.store.set({ step: 'layout' });
  p.store.set({ step: 'preview' });
  assert.deepEqual(p.reported, [{ view: 'layout', use: 1 }, { view: 'layout', use: 2 }], 'the second use is begun afresh and sent once');
  assert.equal(p.views(), 1, 'one view, kept across the uses');
});

test('a page opening on the Layout step begins the first use at once', () => {
  const p = layoutPage({ step: 'layout' });
  p.store.set({ step: 'settings' });
  assert.deepEqual(p.reported, [{ view: 'layout', use: 1 }]);
});

// ---- the Preview step

function previewPage() {
  const { section } = installDocument();
  const store = createStore();
  store.set({ step: 'layout' });
  const frames = fakeFrames();
  const reported = [];
  const begun = [];
  let uses = 0;
  const slicing = { model: () => ({ kind: 'done', slice: 's1', actions: [] }), subscribe: () => {}, sliceAgain: () => {} };
  const result = {
    preview: () => ({ stats: [], line: null, warnings: [] }),
    file: async () => ({ ok: true, bytes: new Uint8Array(4) }),
    ghost: () => null,
  };
  const createView = () => {
    let use = null;
    return {
      async show(bytes, ghost, { since }) { uses += 1; use = { use: uses, since }; return { ok: true }; },
      beginUse(opened) { uses += 1; use = { use: uses, since: opened }; begun.push(opened); },
      summary: () => ({ view: 'preview', ...use }),
      destroy() {}, stepLayer() {}, resetView() {},
    };
  };
  createPreviewStep(section, { slicing, store, clock: new FakeClock(), result, createView, frames, reportDrawing: (s) => reported.push(s) });
  return { store, frames, reported, begun };
}

test('the Preview step sends one drawing summary for each use of the layer preview, its second use measured from its own opening', async () => {
  const p = previewPage();
  p.frames.move(500);                                  // the Preview step opened at 1500
  p.store.set({ step: 'preview' });
  await settle();
  p.store.set({ step: 'send' });
  assert.deepEqual(p.reported, [{ view: 'preview', use: 1, since: 1500 }]);
  p.frames.move(4000);                                 // opened again at 5500, on the same sliced plate
  p.store.set({ step: 'preview' });
  await settle();
  assert.deepEqual(p.begun, [5500], 'coming back begins a new use, timed from the new opening');
  p.store.set({ step: 'layout' });
  assert.deepEqual(p.reported, [{ view: 'preview', use: 1, since: 1500 }, { view: 'preview', use: 2, since: 5500 }]);
  p.store.set({ step: 'parts' });
  assert.equal(p.reported.length, 2, 'a move between two other steps sends nothing');
});
