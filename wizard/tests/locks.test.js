// The locks seam (src/seams/locks.js) over a fake of the browser's navigator.locks that behaves as
// the Web Locks standard says: a lock asked for while another holder has it is granted at once as
// null with `ifAvailable`, and is otherwise queued until the holder lets it go. A duplicated tab
// asks for the plate its open original holds, so the seam must never queue: the fake says when a
// request is queued, an event, and the test fails on that event rather than on a duration.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { webLocks } from '../src/seams/locks.js';

class FakeNavigatorLocks {
  constructor() {
    this.holding = new Map();            // name: the promise that ends the hold
    this.queue = [];                     // {name, grant}
    this.queued = new Promise((resolve) => { this.onQueued = resolve; });
    this.fail = null;
  }

  request(name, options, callback) {
    if (this.fail) return Promise.reject(this.fail);
    if (this.holding.has(name)) {
      if (options.ifAvailable) return Promise.resolve(callback(null));
      return new Promise((resolve) => {
        this.queue.push({ name, grant: () => resolve(this.grant(name, callback)) });
        this.onQueued(name);
      });
    }
    return this.grant(name, callback);
  }

  grant(name, callback) {
    const held = Promise.resolve(callback({ name, mode: 'exclusive' }));
    this.holding.set(name, held);
    return held.then((result) => {
      this.holding.delete(name);
      const next = this.queue.findIndex((q) => q.name === name);
      if (next !== -1) this.queue.splice(next, 1)[0].grant();
      return result;
    });
  }

  async query() {
    return { held: [...this.holding.keys()].map((name) => ({ name, mode: 'exclusive' })), pending: this.queue.map(({ name }) => ({ name })) };
  }
}

test('without the browser\'s locks the seam is null', () => {
  assert.equal(webLocks(null), null);
});

test('a lock another holder has is answered at once with null, never queued', async () => {
  const fake = new FakeNavigatorLocks();
  const original = webLocks(fake);
  const copy = webLocks(fake);
  const release = await original.tryHold('penguinslicer-plate/p1');
  assert.equal(typeof release, 'function');
  const outcome = await Promise.race([copy.tryHold('penguinslicer-plate/p1'), fake.queued.then(() => 'queued')]);
  assert.equal(outcome, null);
  assert.deepEqual((await fake.query()).pending, []);
});

test('a held lock is listed, and once let go another holder gets it', async () => {
  const fake = new FakeNavigatorLocks();
  const a = webLocks(fake);
  const b = webLocks(fake);
  const release = await a.tryHold('penguinslicer-plate/p1');
  assert.deepEqual([...await b.held()], ['penguinslicer-plate/p1']);
  release();
  await fake.holding.get('penguinslicer-plate/p1');
  assert.deepEqual([...await b.held()], []);
  assert.equal(typeof await b.tryHold('penguinslicer-plate/p1'), 'function');
});

test('a request the browser refuses rejects, so the opening reports it', async () => {
  const fake = new FakeNavigatorLocks();
  fake.fail = new DOMException('the lock manager is gone', 'InvalidStateError');
  await assert.rejects(webLocks(fake).tryHold('penguinslicer-plate/p1'), { name: 'InvalidStateError' });
});
