// The layer preview's frame rate for its drawing summary (contracts/wizard-front-server.md,
// "POST /api/reports/drawing"), measured as the first trial measured it (its record, decision
// 11): the intervals between frames drawn while the view moves (turned, or the layer bar
// dragged), typical 1000 over the median interval and worst 1000 over the longest. A frame drawn
// at rest ends a gesture, so the pause before the next one is never counted as a frame.

const tenth = (v) => Math.round(v * 10) / 10;

export function createFrameStats() {
  const intervals = [];
  let last = null;           // the time of the last frame drawn while moving, in this gesture
  let frames = 0;
  return {
    // A frame drawn at `now` (milliseconds of the frame seam), while moving or not.
    frame(now, moving) {
      if (!moving) { last = null; return; }
      frames += 1;
      if (last !== null) intervals.push(now - last);
      last = now;
    },
    summary() {
      if (!intervals.length) return { fps_typical: null, fps_worst: null, frames };
      const sorted = [...intervals].sort((a, b) => a - b);
      const median = sorted[Math.floor(sorted.length / 2)];
      return { fps_typical: tenth(1000 / median), fps_worst: tenth(1000 / sorted.at(-1)), frames };
    },
  };
}
