// The sign-in trip (wizard/README-details.md, "Signing in and signing out"; the contract's
// "Signed in"): a request answered front.not_signed_in on an open page sends the page to
// /signin with its own address to come back to. In phase 2 the front server's development
// identity signs in again at once there, which is what a front server restarted on one machine
// with no cookie key given needs; from phase 3 the trip goes through Onshape.
//
// Before it leaves, the page notes the trip in the tab (SIGN_IN_TRIP, the moment), which
// survives the navigation and dies with the tab. A refusal while the note stands is a trip that
// failed: the page does not leave again by itself, so a browser that withholds the cookie
// cannot repeat sign-ins without end, and the refusal is shown as it is. Any answer of the
// front server to a signed-in request clears the note.
//
// The page leaves at a quiet moment (the guide's "Signing in": no pointer down, no field being
// typed in), so that nobody is taken away in the middle of a drag; its plate and step are in the
// browser's storage, written at each change, so the trip loses nothing.
export const SIGN_IN_TRIP = 'penguinslicer.sign_in_trip';

const NOT_TYPED = new Set(['button', 'checkbox', 'file', 'radio', 'range', 'reset', 'submit']);

// quietMoments(window, document): whenQuiet(run) for the trip, from the page's own events: a
// moment is quiet when no pointer is down and the focus is in no field one types in.
export function quietMoments(win, doc) {
  const down = new Set();
  let waiting = [];
  const typing = () => {
    const a = doc.activeElement;
    return Boolean(a) && (a.tagName === 'TEXTAREA' || (a.tagName === 'INPUT' && !NOT_TYPED.has(a.type)));
  };
  const quiet = () => down.size === 0 && !typing();
  const changed = () => {
    if (!waiting.length || !quiet()) return;
    const runs = waiting;
    waiting = [];
    for (const run of runs) run();
  };
  const options = { capture: true, passive: true };
  win.addEventListener('pointerdown', (e) => down.add(e.pointerId), options);
  for (const type of ['pointerup', 'pointercancel']) win.addEventListener(type, (e) => { down.delete(e.pointerId); changed(); }, options);
  // the focus has left the field once the event is over
  doc.addEventListener('focusout', () => queueMicrotask(changed), options);
  return (run) => { if (quiet()) run(); else waiting.push(run); };
}

// createSignInTrip({tab, clock, here, go, whenQuiet}):
//   tab             the tab seam (get, set)
//   here()          the page's address to come back to: its path and query
//   go(url)         the navigation
//   whenQuiet(run)  runs `run` at the next quiet moment, at once when it is one now
// refused(): true when the page leaves on the trip, false when the trip already failed.
// answered(): the sign-in works.
export function createSignInTrip({ tab, clock, here, go, whenQuiet = (run) => run() }) {
  let leaving = false;
  return {
    refused() {
      if (leaving) return true;
      if (tab.get(SIGN_IN_TRIP)) return false;
      leaving = true;
      whenQuiet(() => {
        tab.set(SIGN_IN_TRIP, String(clock.now()));
        go(`/signin?return=${encodeURIComponent(here())}`);
      });
      return true;
    },
    answered() {
      if (!leaving && tab.get(SIGN_IN_TRIP)) tab.set(SIGN_IN_TRIP, '');
    },
  };
}
