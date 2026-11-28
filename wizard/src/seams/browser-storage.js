// The storage seams: the browser's storage (IndexedDB) and a tab's own storage (sessionStorage),
// each behind a small interface that the tests replace with fakes in memory
// (tests/fakes/storage.js), so that several pages run on one storage in one test. The storage
// module (src/storage.js) is the only user of both.
//
// openIndexedDb(name) resolves to the records {get(key), put(key, value), delete(key), keys()},
// each a promise, in one object store whose keys are strings and whose values are anything the
// browser can store (an ArrayBuffer of a part's bytes among them); it rejects when the browser
// will not open its storage (blocked by the user, or a browser that gives a page none). A write
// the browser refuses (QuotaExceededError when the site's allowance is full) rejects with the
// browser's own error.
const STORE = 'records';

function wrap(db) {
  const run = (mode, act) => new Promise((resolve, reject) => {
    let tx;
    try {
      tx = db.transaction(STORE, mode);
    } catch (err) {
      reject(err);
      return;
    }
    const request = act(tx.objectStore(STORE));
    tx.oncomplete = () => resolve(request.result);
    tx.onerror = () => reject(tx.error ?? request.error);
    tx.onabort = () => reject(tx.error ?? request.error ?? new Error('The browser ended the write.'));
  });
  // Another page of a later release asking for a newer database closes this one rather than
  // blocking it; this page then meets a refused write, which it reports.
  db.onversionchange = () => db.close();
  return {
    get: (key) => run('readonly', (s) => s.get(key)),
    put: (key, value) => run('readwrite', (s) => s.put(value, key)).then(() => undefined),
    delete: (key) => run('readwrite', (s) => s.delete(key)).then(() => undefined),
    keys: () => run('readonly', (s) => s.getAllKeys()),
  };
}

export function openIndexedDb(name = 'penguinslicer', factory = globalThis.indexedDB) {
  return new Promise((resolve, reject) => {
    if (!factory) { reject(new Error('This browser gives the page no IndexedDB.')); return; }
    let request;
    try {
      request = factory.open(name, 1);
    } catch (err) {
      reject(err);
      return;
    }
    request.onupgradeneeded = () => { request.result.createObjectStore(STORE); };
    request.onsuccess = () => resolve(wrap(request.result));
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('Another page holds the storage at an older version.'));
  });
}

// A tab's own storage: {get(name), set(name, value)}, which survives a refresh and the page's own
// reload and dies with the tab. A browser that refuses it gives null and keeps nothing, so a
// refresh then begins a new plate.
export const sessionTab = {
  get(name) {
    try { return globalThis.sessionStorage.getItem(name); } catch { return null; }
  },
  set(name, value) {
    try { globalThis.sessionStorage.setItem(name, String(value)); } catch { /* kept in no tab */ }
  },
};
