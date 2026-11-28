// The heartbeat that measures how long the main thread was held (wizard/README-details.md, "The
// geometry, in a worker"): a HEARTBEAT_MS timer on the main thread, the hold being the longest gap
// between two beats, since a beat comes late exactly when something held the thread, and the gap
// still open since the last beat when the measure is read or stopped. It reads the
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

  // The longest gap, the open one since the last beat included: a thread held after the last
  // beat has held it as surely as one held between two beats.
  const sofar = () => (timer === null ? longest : Math.max(longest, clock.now() - last));

  return {
    // Starts measuring afresh.
    start() {
      if (timer !== null) clock.cancel(timer);
      last = clock.now();
      longest = 0;
      beat();
    },
    // The longest gap so far, in milliseconds, the open gap since the last beat included.
    longest: sofar,
    // Stops the heartbeat and gives the longest gap, the open gap up to the stop included.
    stop() {
      longest = sofar();
      if (timer !== null) clock.cancel(timer);
      timer = null;
      return longest;
    },
  };
}
