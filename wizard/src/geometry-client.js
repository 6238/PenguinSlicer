// The main thread's side of the worker (wizard/README-details.md, "The geometry, in a worker"):
// each question is one message of geometry/messages.js, named by an id, and resolves to its own
// reply, {ok: true, result} or {ok: false, error} with an error report of the wizard's own,
// whatever order the replies come in. A part's bytes are copied to the worker, never transferred:
// the page still keeps them in the browser's storage and uploads them. A worker that fails as a
// whole (a script that cannot load, an error the worker did not catch) answers every question
// waiting, and every later one, with wizard.layout_failed, so no question waits for ever.
import { LAYOUT_FAILED, errorReport } from './geometry/errors.js';

// createGeometryClient(port, {report}): `port` is the worker seam's ({post(message, transfer),
// listen(onReply, onFailure)}); `report(what, {detail})` sends a failure report about the page
// itself: a worker that fails as a whole sends one `layout_failed` report, the first time only.
export function createGeometryClient(port, { report = () => {} } = {}) {
  const waiting = new Map();
  let next = 0;
  let failed = null;

  port.listen((reply) => {
    const resolve = waiting.get(reply.id);
    if (!resolve) return;
    waiting.delete(reply.id);
    resolve(reply.ok ? { ok: true, result: reply.result } : { ok: false, error: reply.error });
  }, (error) => {
    const detail = `the worker failed: ${error && error.message ? error.message : String(error)}`;
    if (!failed) report('layout_failed', { detail });
    failed = failed ?? errorReport(LAYOUT_FAILED, detail);
    for (const resolve of waiting.values()) resolve({ ok: false, error: failed });
    waiting.clear();
  });

  function ask(op, fields = {}, transfer = []) {
    if (failed) return Promise.resolve({ ok: false, error: failed });
    next += 1;
    const id = next;
    return new Promise((resolve) => {
      waiting.set(id, resolve);
      port.post({ id, op, ...fields }, transfer);
    });
  }

  return {
    ask,
    // Reads a binary STL under `key`: its triangles, its box and its corners for drawing.
    read: (key, buffer, units) => ask('read', { key, buffer, units }),
    // The part's picture for its row: px by px RGBA pixels in `colour` (0xrrggbb).
    picture: (key, px, colour) => ask('picture', { key, px, colour }),
    forget: (key) => ask('forget', { key }),
    // The Layout step's questions (geometry/messages.js): a part's patches and its best way, and,
    // for a plate (`plate` is {plateConfiguration, geometry, printer, supports}), the placement
    // check, Arrange, where one instance goes after a lay-down and the turn that makes it fit.
    faces: (key) => ask('faces', { key }),
    orient: (key) => ask('orient', { key }),
    check: (plate) => ask('check', plate),
    arrange: (plate) => ask('arrange', plate),
    settle: (plate, index) => ask('settle', { ...plate, index }),
    fit: (plate, index) => ask('fit', { ...plate, index }),
    // How many questions are waiting for their reply.
    waiting: () => waiting.size,
  };
}
