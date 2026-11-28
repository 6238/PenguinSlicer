// Reloading for a new version (wizard/README-details.md, "Reloading for a new version";
// contracts/wizard-front-server.md, "The version on every answer"). Every answer carries the
// front server's version, and a progress stream its `version` event; the module that makes every
// request tells each one here. A page that sees a newer version than its own reloads itself, and
// never under a person looking at it or touching it, so only at two moments:
//   - when the user moves between steps, where the panel is redrawn anyway; or
//   - once RELOAD_IDLE_S have passed since the user last interacted (a pointer movement, a key or a
//     scroll).
// In either case it waits while a request of its own is pending; an open progress stream is not
// one, since the reloaded page reconnects and is told the latest report at once. A move between
// steps made while a request was pending reloads when the last request ends, unless the user has
// interacted since the move: then the next moment does. Before reloading, the page notes that the
// reload is its own (beforeReload), so that the next load says nothing. A reload that would lose
// the tab's work, a part whose bytes the browser refused to store or a plate the storage refused,
// is not made: the page stays on its version until a later moment finds the work stored.
import { RELOAD_IDLE_S } from './page-constants.js';

// A version is `YYYYMMDDTHHMMSSZ-<commit>`, ordered by the part before the hyphen.
const VERSION = /^(\d{8}T\d{6}Z)-[0-9a-f]+$/;

// Whether `seen` is a version newer than `own`; never when either is not of the version's form,
// so that a page that does not know its own version never reloads.
export function isNewer(seen, own) {
  const a = typeof seen === 'string' ? seen.match(VERSION) : null;
  const b = typeof own === 'string' ? own.match(VERSION) : null;
  return Boolean(a && b) && a[1] > b[1];
}

// createReloader({api, clock, store, version, onInput, beforeReload, reload}):
//   version        the page's own version
//   onInput(listener)  calls listener at each pointer movement, key or scroll of the user's
//   beforeReload() resolves once every write of the browser's storage asked for so far is done:
//                  to true when it has noted that the reload is its own, to false when a reload
//                  would lose the tab's work, and then no reload is made
//   reload()       the reload itself (the location seam)
// Returns {due()}: whether a newer version has been seen.
export function createReloader({ api, clock, store, version, onInput, beforeReload, reload }) {
  let newer = false;
  let lastInput = clock.now();
  let idleTimer = null;
  let stepMovedAt = null;       // a move between steps waiting for the pending requests to end
  let reloading = false;

  function go() {
    if (reloading) return;
    reloading = true;
    if (idleTimer !== null) clock.cancel(idleTimer);
    idleTimer = null;
    // after every listener of the move between steps has run, so that the step it moved to is among
    // the writes the reload waits for. beforeReload resolving to false means a reload would lose
    // the tab's work (a part the browser refused to store, or a storage refused): the page stays,
    // and the next moment asks again.
    Promise.resolve().then(() => beforeReload()).then(
      (go) => { if (go === false) reloading = false; else reload(); },
      () => reload(),
    );
  }

  // A moment has come: reload now unless a request is pending, when the end of the last one
  // decides (settled, below).
  function moment() {
    if (!newer || reloading) return;
    if (api.pending() === 0) go();
  }

  function armIdle() {
    if (idleTimer !== null) clock.cancel(idleTimer);
    idleTimer = null;
    if (!newer || reloading) return;
    const at = lastInput + RELOAD_IDLE_S * 1000;
    idleTimer = clock.after(Math.max(0, at - clock.now()), () => { idleTimer = null; moment(); });
  }

  const idle = () => clock.now() - lastInput >= RELOAD_IDLE_S * 1000;

  api.onVersion((seen) => {
    if (newer || !isNewer(seen, version)) return;
    newer = true;
    armIdle();
  });

  api.onSettled(() => {
    if (!newer || reloading) return;
    const moved = stepMovedAt !== null && lastInput <= stepMovedAt;
    stepMovedAt = null;
    if (moved || idle()) go();
  });

  onInput(() => {
    lastInput = clock.now();
    if (newer) armIdle();
  });

  store.subscribe((state, before) => {
    if (state.step === before.step || !newer) return;
    stepMovedAt = clock.now();
    moment();
  });

  return { due: () => newer };
}
