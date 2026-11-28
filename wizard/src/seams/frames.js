// The frame seam: the one place the page asks the browser for an animation frame or reads the
// high-resolution time, for the 3D views (the Layout step's view). Every other module takes a
// frames object with this shape, so that a test can count the frames drawn.
//   next(fn)       calls fn(time) before the browser's next repaint; returns a handle
//   cancel(handle) stops a frame not yet run
//   now()          milliseconds, high resolution, for measuring frame times only
export const realFrames = {
  next: (fn) => requestAnimationFrame(fn),
  cancel: (handle) => cancelAnimationFrame(handle),
  now: () => performance.now(),
};
