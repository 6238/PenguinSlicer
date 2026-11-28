// The fake clock: the clock seam's shape (src/seams/clock.js), with time that moves only when a
// test moves it. advance(ms) fires every timer that falls due, in the order of its moment (and
// of its setting, for timers due at the same moment), letting the page's promises settle
// before and after each, so a test sees exactly the state at each moment.
const START = Date.UTC(2026, 10, 28, 20, 0, 0);

// Lets every promise that is ready run: a few turns of the event loop, which waits on no time.
export async function settle() {
  for (let i = 0; i < 10; i += 1) await new Promise((resolve) => setImmediate(resolve));
}

export class FakeClock {
  constructor(start = START) {
    this.start = start;
    this.t = start;
    this.timers = new Map();
    this.seq = 0;
  }

  now() { return this.t; }

  after(ms, fn) {
    this.seq += 1;
    this.timers.set(this.seq, { at: this.t + Math.max(0, ms), fn, seq: this.seq });
    return this.seq;
  }

  cancel(handle) { this.timers.delete(handle); }

  // How many timers are set and not yet fired.
  get pending() { return this.timers.size; }

  // Moves the time on by `ms`, firing each timer as its moment comes.
  async advance(ms) {
    const end = this.t + ms;
    await settle();
    for (;;) {
      let next = null;
      for (const timer of this.timers.values()) {
        if (timer.at <= end && (!next || timer.at < next.at || (timer.at === next.at && timer.seq < next.seq))) next = timer;
      }
      if (!next) break;
      this.timers.delete(next.seq);
      this.t = next.at;
      next.fn();
      await settle();
    }
    this.t = end;
    await settle();
  }

  // Moves the time on to a moment given in milliseconds since the clock started.
  async advanceTo(msSinceStart) {
    await this.advance(this.start + msSinceStart - this.t);
  }

  // Milliseconds since the clock started.
  get elapsed() { return this.t - this.start; }
}
