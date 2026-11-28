// The locks seam: the browser's Web Locks (navigator.locks), through which the tabs know which
// stored plates are held, behind a small interface that the tests replace with a fake shared by
// several pages (tests/fakes/storage.js, FakeLocks). The browser releases a tab's locks when the
// tab closes or crashes, so a dead tab never holds a plate for ever.
//   tryHold(name)  resolves to a function that releases the lock, or to null when another tab
//                  holds it; never waits for it
//   held()         resolves to the set of the names every tab of this browser holds
// webLocks() is null where the browser has no Web Locks (a page served over plain HTTP from
// another machine than the browser's own).
export function webLocks(locks = globalThis.navigator ? globalThis.navigator.locks : undefined) {
  if (!locks) return null;
  return {
    tryHold(name) {
      return new Promise((resolve, reject) => {
        locks.request(name, { ifAvailable: true }, (lock) => {
          if (!lock) { resolve(null); return undefined; }
          // Held until the page lets it go, or the tab goes.
          return new Promise((letGo) => { resolve(() => letGo()); });
        }).catch(reject);
      });
    },
    async held() {
      const state = await locks.query();
      return new Set(state.held.map((lock) => lock.name));
    },
  };
}
