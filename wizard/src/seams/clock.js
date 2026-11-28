// The clock seam: the one place the page reads the time or sets a timer. Every other module
// takes a clock with this shape, and the tests give it the fake clock they move
// (tests/fakes/clock.js), so no test waits on the wall clock.
//   now()            milliseconds since 1970, as Date.now()
//   after(ms, fn)    calls fn once, ms from now; returns a handle
//   cancel(handle)   stops a timer that has not yet fired
// A browser's timer holds at most 2^31 - 1 ms (about 24.8 days) and fires a longer one at once, so
// a longer wait is cut into waits it can hold, each counted from the moment the wait began.
export const LONGEST_TIMER_MS = 2 ** 31 - 1;

// The clock on the timers it is handed: setTimer(fn, ms) returns an id that clearTimer(id) stops.
export function timerClock({ now, setTimer, clearTimer }) {
  return {
    now,
    after(ms, fn) {
      const handle = { id: null };
      const at = now() + ms;
      const arm = (left) => {
        handle.id = left > LONGEST_TIMER_MS ? setTimer(() => arm(at - now()), LONGEST_TIMER_MS) : setTimer(fn, Math.max(0, left));
      };
      arm(ms);
      return handle;
    },
    cancel: (handle) => { if (handle) clearTimer(handle.id); },
  };
}

export const realClock = timerClock({
  now: () => Date.now(),
  setTimer: (fn, ms) => setTimeout(fn, ms),
  clearTimer: (handle) => clearTimeout(handle),
});
