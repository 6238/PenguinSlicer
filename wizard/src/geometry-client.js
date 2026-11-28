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
    const entry = waiting.get(reply.id);
    if (!entry) return;
    waiting.delete(reply.id);
    if (!reply.ok) tellFault(reply, entry);
    entry.resolve(reply.ok ? { ok: true, result: reply.result } : { ok: false, error: reply.error });
  }, (error) => {
    const detail = `the worker failed: ${error && error.message ? error.message : String(error)}`;
    if (!failed) report('layout_failed', { detail });
    failed = failed ?? errorReport(LAYOUT_FAILED, detail);
    for (const entry of waiting.values()) entry.resolve({ ok: false, error: failed });
    waiting.clear();
  });

  // A failed answer whose fault is the page's (it asked for something wrong) or the geometry's own
  // code is reported once, as page_failed or layout_failed, naming the part by its hash when the
  // question was about one; a part the geometry cannot read is the Parts step's to report.
  function tellFault(reply, { op, key }) {
    if (reply.fault !== 'page' && reply.fault !== 'layout') return;
    const fields = { detail: `${op}: ${reply.error && reply.error.detail}` };
    const sha = typeof key === 'string' ? key.match(/^([0-9a-f]{64})\.(mm|in)$/) : null;
    report(reply.fault === 'page' ? 'page_failed' : 'layout_failed', sha ? { part_sha256: sha[1], ...fields } : fields);
  }

  function ask(op, fields = {}, transfer = []) {
    if (failed) return Promise.resolve({ ok: false, error: failed });
    next += 1;
    const id = next;
    return new Promise((resolve) => {
      waiting.set(id, { resolve, op, key: fields.key });
      port.post({ id, op, ...fields }, transfer);
    });
  }

  // Each part's corners for drawing, as the worker read them, kept for the Layout step's view.
  const meshes = new Map();

  return {
    ask,
    // Reads a binary STL under `key`: its triangles, its box and its corners for drawing.
    read: (key, buffer, units) => ask('read', { key, buffer, units }).then((answer) => {
      if (answer.ok) meshes.set(key, { positions: answer.result.positions, min: answer.result.min, max: answer.result.max });
      else meshes.delete(key);
      return answer;
    }),
    // The corners for drawing of the part read under `key` ({positions, min, max}), or null.
    mesh: (key) => meshes.get(key) ?? null,
    // The part's picture for its row: px by px RGBA pixels in `colour` (0xrrggbb).
    picture: (key, px, colour) => ask('picture', { key, px, colour }),
    forget: (key) => { meshes.delete(key); return ask('forget', { key }); },
    // The Layout step's questions (geometry/messages.js): a part's patches and its best way, and,
    // for a plate (`plate` is {plateConfiguration, geometry, printer, supports}), the placement
    // check, Arrange, where one instance goes after a lay-down and the turn that makes it fit.
    faces: (key) => ask('faces', { key }),
    orient: (key) => ask('orient', { key }),
    check: (plate) => ask('check', plate),
    arrange: (plate) => ask('arrange', plate),
    settle: (plate, index) => ask('settle', { ...plate, index }),
    coarse: (key, maxTriangles) => ask('coarse', { key, maxTriangles }),
    fit: (plate, index) => ask('fit', { ...plate, index }),
    // How many questions are waiting for their reply.
    waiting: () => waiting.size,
  };
}
