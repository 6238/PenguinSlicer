// The clock seam (src/seams/clock.js) on timers that it is handed, so that no test waits on the
// wall clock: a wait longer than a browser's timer can hold (2,147,483,647 ms, about 24.8 days)
// is cut into waits it can, since a longer one fires at once.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { LONGEST_TIMER_MS, timerClock } from '../src/seams/clock.js';

// Timers the test fires by hand, on a time it moves.
function fakeTimers() {
  let t = 0;
  let next = 1;
  const timers = new Map();
  return {
    now: () => t,
    setTimer(fn, ms) {
      assert.ok(ms >= 0 && ms <= LONGEST_TIMER_MS, `a timer of ${ms} ms, longer than a browser holds`);
      const id = next++;
      timers.set(id, { at: t + ms, fn });
      return id;
    },
    clearTimer(id) { timers.delete(id); },
    // Moves the time to the next timer and fires it; false when there is none.
    fireNext() {
      const [id, timer] = [...timers].sort((a, b) => a[1].at - b[1].at)[0] ?? [];
      if (id === undefined) return false;
      timers.delete(id);
      t = timer.at;
      timer.fn();
      return true;
    },
    pending: () => timers.size,
  };
}

test('the longest timer a browser holds is 2,147,483,647 ms', () => {
  assert.equal(LONGEST_TIMER_MS, 2 ** 31 - 1);
});

test('a short wait is one timer', () => {
  const timers = fakeTimers();
  const clock = timerClock(timers);
  let fired = 0;
  clock.after(5000, () => { fired += 1; });
  assert.equal(timers.pending(), 1);
  timers.fireNext();
  assert.equal(fired, 1);
  assert.equal(timers.now(), 5000);
  assert.equal(timers.pending(), 0);
});

test('a wait longer than a browser\'s timer holds fires at its moment, not at once', () => {
  const timers = fakeTimers();
  const clock = timerClock(timers);
  const ms = 30 * 24 * 3600 * 1000;               // thirty days
  let firedAt = null;
  clock.after(ms, () => { firedAt = timers.now(); });
  while (firedAt === null && timers.fireNext());
  assert.equal(firedAt, ms);
});

test('a long wait cancelled between its parts never fires', () => {
  const timers = fakeTimers();
  const clock = timerClock(timers);
  let fired = false;
  const handle = clock.after(LONGEST_TIMER_MS * 2 + 10, () => { fired = true; });
  timers.fireNext();                              // the first part
  assert.equal(timers.pending(), 1);
  clock.cancel(handle);
  assert.equal(timers.pending(), 0);
  while (timers.fireNext());
  assert.equal(fired, false);
});

test('now is the clock it is given', () => {
  const timers = fakeTimers();
  assert.equal(timerClock(timers).now(), 0);
});
