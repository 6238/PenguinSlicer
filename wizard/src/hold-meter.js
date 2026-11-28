// The heartbeat that measures how long the main thread was held (wizard/README-details.md, "The
// geometry, in a worker"): a HEARTBEAT_MS timer on the main thread, the hold being the longest gap
// between two beats, since a beat comes late exactly when something held the thread. It reads the
// time only through the clock seam, so a test moves it; the page's tests and its reports about
// itself use the same measure. The browser's long-task timing is not the measure: in the second
// trial it reported long tasks the heartbeat never saw (wizard/trials/geometry/README.md).
export const HEARTBEAT_MS = 10;

export function createHoldMeter(clock) {
  let last = 0;
  let longest = 0;
  let timer = null;

  function beat() {
    timer = clock.after(HEARTBEAT_MS, () => {
      const now = clock.now();
      longest = Math.max(longest, now - last);
      last = now;
      beat();
    });
  }

  return {
    // Starts measuring afresh.
    start() {
      if (timer !== null) clock.cancel(timer);
      last = clock.now();
      longest = 0;
      beat();
    },
    // The longest gap so far, in milliseconds.
    longest: () => longest,
    // Stops the heartbeat and gives the longest gap.
    stop() {
      if (timer !== null) clock.cancel(timer);
      timer = null;
      return longest;
    },
  };
}
