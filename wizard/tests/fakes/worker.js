// The worker, run in the test's own thread through the same messages (wizard/README-details.md,
// "The project and its tools"): a port of the worker seam's shape (src/seams/worker.js) whose
// other end is createGeometry() of src/geometry/messages.js, the code the real worker runs. Each
// message is copied as the browser copies a message between threads, and each reply comes on a
// later turn, as a reply from another thread does. `fail(error)` stands for the worker failing
// as a whole (a script that cannot load), and `hold()` keeps the replies until `release()`;
// `hold(op)` keeps only the replies to messages of that op, the others answered as usual.
import { createGeometry } from '../../src/geometry/messages.js';

export class InThreadWorker {
  constructor() {
    this.geometry = createGeometry();
    this.listener = null;
    this.failure = null;
    this.posted = [];
    this.holding = null;
    this.heldOp = null;
    this.port = {
      post: (message, transfer = []) => this.receive(message, transfer),
      listen: (onReply, onFailure) => { this.listener = onReply; this.failure = onFailure; },
    };
  }

  receive(message, transfer) {
    this.posted.push({ message, transfer });
    const copy = structuredClone(message);
    const answer = () => {
      const { reply } = this.geometry.handle(copy);
      this.listener(reply);
    };
    if (this.holding && (this.heldOp === null || this.heldOp === message.op)) this.holding.push(answer);
    else setImmediate(answer);
  }

  hold(op = null) { this.holding = []; this.heldOp = op; }

  release() {
    const waiting = this.holding || [];
    this.holding = null;
    this.heldOp = null;
    for (const answer of waiting) setImmediate(answer);
  }

  fail(error) { this.failure(error); }
}
