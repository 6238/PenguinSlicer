// The layer preview's frame rate, as its drawing summary gives it (src/preview/frame-stats.js;
// contracts/wizard-front-server.md, "POST /api/reports/drawing"): the frames drawn while the view
// moves, typical over the median interval and worst over the longest, the pauses between two
// gestures never counted as a frame.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createFrameStats } from '../../src/preview/frame-stats.js';

test('frames drawn while moving give the typical and the worst frame rate', () => {
  const stats = createFrameStats();
  for (const t of [0, 100, 200, 300, 550, 650]) stats.frame(t, true);
  // intervals 100, 100, 100, 250, 100: the median 100 ms is 10 a second, the longest 250 ms is 4
  assert.deepEqual(stats.summary(), { fps_typical: 10, fps_worst: 4, frames: 6 });
});

test('a frame at rest ends a gesture: the time until the next gesture is no frame', () => {
  const stats = createFrameStats();
  stats.frame(0, true); stats.frame(50, true);
  stats.frame(60, false);
  stats.frame(5000, true); stats.frame(5050, true);
  assert.deepEqual(stats.summary(), { fps_typical: 20, fps_worst: 20, frames: 4 });
});

test('a view that never moved has no frame rate', () => {
  const stats = createFrameStats();
  stats.frame(0, false); stats.frame(10, false);
  assert.deepEqual(stats.summary(), { fps_typical: null, fps_worst: null, frames: 0 });
  stats.frame(20, true);
  assert.deepEqual(stats.summary(), { fps_typical: null, fps_worst: null, frames: 1 }, 'one frame is no interval');
});

test('the figures are kept to a tenth', () => {
  const stats = createFrameStats();
  for (const t of [0, 30, 60, 90]) stats.frame(t, true);
  assert.deepEqual(stats.summary(), { fps_typical: 33.3, fps_worst: 33.3, frames: 4 });
});

test('the median of an even number of intervals is the upper middle one, as the trial took it', () => {
  const stats = createFrameStats();
  for (const t of [0, 100, 300]) stats.frame(t, true);         // 100 and 200
  assert.equal(stats.summary().fps_typical, 5);
});
