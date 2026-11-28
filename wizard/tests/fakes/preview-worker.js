// The layer preview's worker, run in the test's own thread through the same messages: a port of
// the preview worker seam's shape (src/seams/preview-worker.js) whose other end is
// createPreviewReading() of src/preview/reading.js, the code the real worker runs. Each message
// is copied as the browser copies a message between threads, and each message back comes on a
// later turn. `fail(error)` stands for the worker failing as a whole; `hold()` keeps the final
// reply (progress still passes) until `release()`; `terminated` says the page stopped it.
import { createPreviewReading } from '../../src/preview/reading.js';

export class InThreadPreviewWorker {
  constructor(options) {
    this.reading = createPreviewReading(options);
    this.posted = [];
    this.terminated = false;
    this.holding = null;
    this.onMessage = null;
    this.onFailure = null;
    this.port = {
      post: (message, transfer = []) => this.receive(message, transfer),
      listen: (onMessage, onFailure) => { this.onMessage = onMessage; this.onFailure = onFailure; },
      terminate: () => { this.terminated = true; },
    };
  }

  receive(message, transfer) {
    this.posted.push({ message, transfer });
    const copy = structuredClone(message);
    const send = (m) => setImmediate(() => { if (!this.terminated) this.onMessage(m); });
    this.done = this.reading.handle(copy, send).then(({ reply }) => {
      if (this.holding) this.holding.push(reply);
      else send(reply);
    });
  }

  hold() { this.holding = []; }

  release() {
    const waiting = this.holding || [];
    this.holding = null;
    for (const reply of waiting) setImmediate(() => { if (!this.terminated) this.onMessage(reply); });
  }

  fail(error) { this.onFailure(error); }
}
