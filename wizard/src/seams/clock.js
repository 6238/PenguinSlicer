// The clock seam: the one place the page reads the time or sets a timer. Every other module
// takes a clock with this shape, and the tests give it the fake clock they move
// (tests/fakes/clock.js), so no test waits on the wall clock.
//   now()            milliseconds since 1970, as Date.now()
//   after(ms, fn)    calls fn once, ms from now; returns a handle
//   cancel(handle)   stops a timer that has not yet fired
export const realClock = {
  now: () => Date.now(),
  after: (ms, fn) => setTimeout(fn, ms),
  cancel: (handle) => clearTimeout(handle),
};
