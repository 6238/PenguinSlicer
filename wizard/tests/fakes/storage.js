// Fakes of the browser's storage, its per-tab storage and its locks, with the shapes of the seams
// in src/seams/browser-storage.js and src/seams/locks.js, so that several pages (several tabs) run on one
// storage in one test, and a test makes the browser refuse a write or clear the site's storage
// on purpose.
//
// FakeRecords: the storage (IndexedDB in the browser), shared by every page of one browser.
//   open()                 what the seam's openRecords gives: the records, or a refusal when
//                          the test made the storage unavailable
//   refuse(match)          the next writes whose key `match` accepts (a string prefix or a
//                          function) fail as a full allowance fails (QuotaExceededError)
//   holdPuts()             holds every write until the function it returns is called
//   clearAll()             the browser clears the site's storage
// FakeTab: one tab's sessionStorage, kept across a refresh of that tab and dying with it.
// FakeLocks: the browser's locks, shared by every tab; forTab(name) gives one tab's seam, and
//   closeTab(name) releases every lock that tab holds, as the browser does when a tab closes or
//   crashes.

function quotaError() {
  const error = new Error('The quota has been exceeded.');
  error.name = 'QuotaExceededError';
  return error;
}

export class FakeRecords {
  constructor() {
    this.map = new Map();
    this.refusals = [];
    this.unavailable = false;
    this.puts = [];
    this.gate = null;
  }

  async open() {
    if (this.unavailable) throw new Error('The browser refused to open the storage.');
    const records = this;
    return {
      async get(key) { return records.map.has(key) ? structuredClone(records.map.get(key)) : undefined; },
      async put(key, value) {
        if (records.gate) await records.gate;
        const refusal = records.refusals.find((r) => r(key));
        if (refusal) throw quotaError();
        records.puts.push(key);
        records.map.set(key, structuredClone(value));
      },
      async delete(key) { records.map.delete(key); },
      async keys() { return [...records.map.keys()]; },
    };
  }

  refuse(match = () => true) {
    this.refusals.push(typeof match === 'string' ? (key) => key.startsWith(match) : match);
  }

  allow() { this.refusals = []; }

  // Holds every write from now on until the function returned is called, as a slow disk would.
  holdPuts() {
    let release;
    this.gate = new Promise((resolve) => { release = resolve; });
    return () => { this.gate = null; release(); };
  }

  clearAll() { this.map.clear(); }

  keys() { return [...this.map.keys()].sort(); }

  value(key) { return this.map.get(key); }
}

export class FakeTab {
  constructor(entries = {}) { this.entries = { ...entries }; }
  get(name) { return Object.hasOwn(this.entries, name) ? this.entries[name] : null; }
  set(name, value) { this.entries[name] = String(value); }
  // What a duplicated tab starts with: a copy of this tab's sessionStorage, as Chrome makes.
  duplicate() { return new FakeTab(this.entries); }
}

export class FakeLocks {
  constructor() { this.holders = new Map(); }

  forTab(tab) {
    const locks = this;
    return {
      async tryHold(name) {
        if (locks.holders.has(name)) return null;
        locks.holders.set(name, tab);
        return () => { if (locks.holders.get(name) === tab) locks.holders.delete(name); };
      },
      async held() { return new Set(locks.holders.keys()); },
    };
  }

  closeTab(tab) {
    for (const [name, holder] of [...this.holders]) if (holder === tab) this.holders.delete(name);
  }

  heldBy(tab) { return [...this.holders].filter(([, holder]) => holder === tab).map(([name]) => name); }
}
