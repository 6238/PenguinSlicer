// The panel line, the one line under the step tabs, with its two uses (wizard/README-details.md,
// "The header"):
// - passing: the step that holds a click on a tab, and why; it goes at the user's next move or
//   after PANEL_LINE_PASSING_S;
// - lasting: the retry messages, from the retry board, until a request is answered.
// When both apply, the lasting use is shown and the passing one is not.
import { PANEL_LINE_PASSING_S } from '../page-constants.js';
import { RETRY_NOW, SERVER_SLOW, SERVER_UNREACHABLE, TRY_AGAIN } from '../sentences.js';

// What the line shows, from the retry board's state and the passing text (or null).
export function lineContent(boardState, passing) {
  if (boardState.kind === 'slow') return { kind: 'slow', text: SERVER_SLOW(boardState.seconds), action: RETRY_NOW };
  if (boardState.kind === 'unreachable') return { kind: 'unreachable', text: SERVER_UNREACHABLE, action: TRY_AGAIN };
  if (passing) return { kind: 'passing', text: passing };
  return { kind: 'none' };
}

const same = (a, b) => a.kind === b.kind && a.text === b.text && a.action === b.action;

// createPanelLine({board, clock, show}): `show(content)` is called each time what the line
// shows changes. held(text) gives the passing use; moved() is the user's next move.
export function createPanelLine({ board, clock, show }) {
  let passing = null;
  let timer = null;
  let shown = { kind: 'none' };

  function update() {
    const now = lineContent(board.state(), passing);
    if (!same(now, shown)) {
      shown = now;
      show(now);
    }
  }

  function clearPassing() {
    if (timer !== null) { clock.cancel(timer); timer = null; }
    if (passing !== null) { passing = null; update(); }
  }

  const unsubscribe = board.subscribe(update);
  return {
    content: () => shown,
    held(text) {
      if (timer !== null) clock.cancel(timer);
      passing = text;
      timer = clock.after(PANEL_LINE_PASSING_S * 1000, () => { timer = null; clearPassing(); });
      update();
    },
    moved: clearPassing,
    dispose() { unsubscribe(); if (timer !== null) clock.cancel(timer); },
  };
}
