// The Parts step's behaviour (wizard/README-details.md, "The Parts step", "Adding a part",
// "Uploading a part", "A part that cannot be used", "The limits on a plate"), apart from its
// drawing (panel/parts-step.js): the list of parts on the plate, each a row, and what happens
// to a part from the moment it is handed over in a part set (contracts/part-set.md) until it is
// on the plate or refused.
//
// For each part of a part set, in order:
//   1. the page's own check of its size, before anything is done with it (for a file, by the
//      file's own size, before its bytes are read; a file the browser cannot read is refused
//      alone);
//   2. its hash (SHA-256, by the browser's own digest), by which, with its units, the page knows
//      it: a part already on the plate raises that part's quantity and adds no row;
//   3. the page's own check of the number of different parts;
//   4. kept first, in the browser's storage, then its row appears, arriving;
//   5. read for drawing in the worker and uploaded (POST /api/parts) at the same time;
//   6. when both are done, the row is complete; a refusal by either removes the part and its row
//      and says so in a notification. The slice service's refusal is the one shown when both
//      refuse.
// The figures of the plate are told to the store, so that the panel (the plate summary, Next)
// shows the same plate: `parts` and `instances` count the parts that have arrived, `arriving`
// and `arrivingInstances` those still arriving.
import { MAX_INSTANCES, MAX_PART_BYTES, MAX_PARTS } from './geometry/constants.js';
import { PART_NOT_DRAWABLE } from './geometry/errors.js';
import {
  ARRIVED_LATE, JOINS_LATER, NAMED, OTHER_PARTS_FINE, READ_IN_REMINDER,
  badAnswer, fileUnreadable, partOverSize, tooManyInstances, tooManyParts,
} from './sentences.js';
import { megabytes } from './units.js';

const UNITS = ['in', 'mm'];
const NAME_CHARS = 200;
// Refusals that are a fault of the page itself: shown, and reported as page_failed.
const PAGE_FAULTS = new Set(['slice.bad_units', 'front.bad_request']);
// The steps after the Parts step on which a part that arrives late is told in a notification; on
// the Layout step it joins the plate at once.
const LATE_STEPS = new Set(['settings', 'preview', 'send']);

// A file's part's name: the file's name less a final ".stl" in any case, cut to 200 characters,
// "part" when nothing is left (contracts/part-set.md).
export function partName(fileName) {
  const name = Array.from(String(fileName).replace(/\.stl$/i, '')).slice(0, NAME_CHARS).join('');
  return name === '' ? 'part' : name;
}

// The part set a file upload makes: one part for each file, quantity 1, the switch's units, the
// file's bytes unchanged. Each file here is {name, bytes}, already read; addFiles reads each one
// in its turn and makes its part the same way.
export function partSetOf(files, units) {
  return { format: 1, source: 'file', parts: files.map((f) => ({ name: partName(f.name), quantity: 1, units, stl_bytes: f.bytes })) };
}

// The SHA-256 hash of the bytes as 64 lowercase hexadecimal characters, by the browser's own
// digest, which runs off the main thread.
export async function sha256Hex(bytes) {
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}

const finite = (v) => typeof v === 'number' && Number.isFinite(v);

// What is wrong with a part's record (contracts/wizard-front-server.md, "POST /api/parts"), or
// null when the page can use it.
function recordProblem(body) {
  if (body === null || typeof body !== 'object') return 'the record is not an object';
  if (typeof body.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(body.sha256)) return 'sha256 is not 64 hexadecimal characters';
  if (!UNITS.includes(body.units)) return 'units is neither "in" nor "mm"';
  const m = body.measurements;
  if (!m || typeof m !== 'object' || !Array.isArray(m.size_mm) || m.size_mm.length !== 3 || !m.size_mm.every(finite)) return 'measurements.size_mm is not three numbers';
  if (!Array.isArray(body.warnings) || !body.warnings.every((w) => w && typeof w.message === 'string')) return 'warnings is not a list of warnings';
  return null;
}

const clampQuantity = (n) => {
  const whole = Math.round(Number(n));
  return whole >= 1 ? Math.min(MAX_INSTANCES, whole) : 1;
};

// createParts({api, storage, geometry, store, panel, report, hash}):
//   api       the module that makes every request
//   storage   the storage module, holding the tab's plate
//   geometry  the worker's client
//   store     the panel's store: the step, the configuration, the plate's figures
//   panel     {notify, dropNotice}
//   report(what, {part_sha256, detail})  a failure report about the page itself
//   hash(bytes)  the SHA-256 of the bytes, as hexadecimal (sha256Hex)
export function createParts({ api, storage, geometry, store, panel, report, hash = sha256Hex }) {
  // Each row: {key, sha256, units, name, source, quantity, arriving, slow, drawn, record,
  // warnings, saved, stop}. `key` is "<sha256>.<units>", also the worker's key for the part.
  let rows = [];
  let chosenUnits = null;
  let generation = 0;
  let adding = Promise.resolve();
  const work = new Set();
  const listeners = new Set();

  // The switch follows the configuration until the user chooses.
  store.subscribe((state, before) => {
    if (state.configuration !== before.configuration && !chosenUnits) for (const listener of listeners) listener(rows);
  });

  const live = (row) => rows.includes(row);
  const track = (promise) => {
    work.add(promise);
    promise.finally(() => work.delete(promise)).catch(() => {});
    return promise;
  };

  function units() {
    if (chosenUnits) return chosenUnits;
    const configured = store.get().configuration?.upload_units;
    return UNITS.includes(configured) ? configured : 'in';
  }

  function publish() {
    const arrived = rows.filter((r) => !r.arriving);
    const coming = rows.filter((r) => r.arriving);
    const sum = (list) => list.reduce((n, r) => n + r.quantity, 0);
    store.set({ plate: { parts: arrived.length, instances: sum(arrived), arriving: coming.length, arrivingInstances: sum(coming) } });
    for (const listener of listeners) listener(rows);
  }

  // The stored plate's parts follow the rows: each part's quantity and record.
  function persist() {
    const byKey = new Map(rows.map((r) => [r.key, r]));
    return storage.update({
      parts: storage.plate().parts.map((p) => {
        const row = byKey.get(`${p.sha256}.${p.units}`);
        return row ? { ...p, quantity: row.quantity, record: row.record } : p;
      }),
    });
  }

  // Takes a row off the plate: its upload stopped, the worker told to forget it, its stored part
  // and bytes removed.
  function drop(row) {
    row.stop.abort();
    rows = rows.filter((r) => r !== row);
    geometry.forget(row.key);
    publish();
    return storage.removePart(row.sha256, row.units);
  }

  function tellNotAdded(row, failure) {
    const todo = [
      rows.length ? OTHER_PARTS_FINE : null,
      failure.remedy,
      // how this file was read, which the switch may since have changed
      failure.code === 'slice.part_too_large' && row.source === 'file' ? READ_IN_REMINDER(row.units) : null,
    ].filter(Boolean).join(' ');
    panel.notify({ kind: 'error', what: NAMED(row.name, failure.message), todo, key: `part:${row.key}` });
  }

  async function refuse(row, failure) {
    const removing = drop(row);
    tellNotAdded(row, failure);
    await removing;
  }

  // Uploads the part, once more when the record names another hash. Resolves to {record},
  // {failure, status} or {stopped}.
  async function upload(row, bytes) {
    const path = `/api/parts?units=${row.units}`;
    for (let tries = 0; tries < 2; tries += 1) {
      const answer = await api.post(path, {
        bytes, upload: true, signal: row.stop.signal,
        onSlow: () => { if (live(row)) { row.slow = true; publish(); } },
      });
      if (answer.stopped) return { stopped: true };
      if (!answer.ok) {
        if (PAGE_FAULTS.has(answer.report.code)) {
          report('page_failed', { part_sha256: row.sha256, detail: `POST ${path} answered ${answer.status} ${answer.report.code}: ${answer.report.detail ?? ''}` });
        }
        return { failure: answer.report, status: answer.status };
      }
      const fault = recordProblem(answer.body);
      if (fault) return { failure: { ...badAnswer(path, answer.status, JSON.stringify(answer.body)), detail: `${path}: ${fault}` } };
      if (answer.body.sha256 === row.sha256 && answer.body.units === row.units) return { record: answer.body };
    }
    const detail = `POST ${path}: the record named another hash twice; the page made ${row.sha256}`;
    report('page_failed', { part_sha256: row.sha256, detail });
    return { failure: { ...badAnswer(path, 201, ''), detail } };
  }

  // Reads the part for drawing and, unless its record is already kept, uploads it; then the row
  // is complete, or the part is refused.
  async function bring(row, bytes) {
    const reading = geometry.read(row.key, bytes, row.units).then((answer) => {
      if (answer.ok && live(row)) { row.drawn = true; publish(); }
      return answer;
    });
    const outcome = row.record ? { record: row.record } : await upload(row, bytes);
    if (outcome.stopped || !live(row)) return;
    if (outcome.failure) { await refuse(row, outcome.failure); return; }
    const read = await reading;
    if (!live(row)) return;
    if (!read.ok) {
      if (read.error.code === PART_NOT_DRAWABLE) report('part_not_drawable', { part_sha256: row.sha256, detail: read.error.detail });
      await refuse(row, read.error);
      return;
    }
    if (!row.arriving) return;
    row.record = outcome.record;
    row.warnings = outcome.record.warnings;
    row.arriving = false;
    row.slow = false;
    persist();
    publish();
    if (LATE_STEPS.has(store.get().step)) {
      panel.notify({ kind: 'info', what: ARRIVED_LATE(row.name), todo: JOINS_LATER, key: `late:${row.key}` });
    }
  }

  const newRow = (fields) => ({
    arriving: true, slow: false, drawn: false, record: null, warnings: [], saved: true, source: 'file',
    ...fields, key: `${fields.sha256}.${fields.units}`, stop: new AbortController(),
  });

  // A part or file refused before anything was done with it: the page's own sentences, with
  // "Your other parts are fine." while the list holds parts.
  function tellRefused(failure, key) {
    panel.notify({ kind: 'error', what: failure.message, todo: [rows.length ? OTHER_PARTS_FINE : null, failure.remedy].filter(Boolean).join(' '), key });
  }

  const overSize = (label, size) => partOverSize(label, megabytes(size), size, MAX_PART_BYTES);

  async function addOne(part, label, source, gen) {
    const bytes = part.stl_bytes;
    if (!UNITS.includes(part.units)) throw new Error(`units must be "mm" or "in", not ${JSON.stringify(part.units)}`);
    if (bytes.byteLength > MAX_PART_BYTES) {
      tellRefused(overSize(label, bytes.byteLength), `size:${label}`);
      return;
    }
    const sha256 = await hash(bytes);
    if (gen !== generation) return;
    const key = `${sha256}.${part.units}`;
    const listed = rows.find((r) => r.key === key);
    if (listed) {
      listed.quantity = clampQuantity(listed.quantity + part.quantity);
      persist();
      publish();
      return;
    }
    if (rows.length >= MAX_PARTS) {
      const failure = tooManyParts(part.name, MAX_PARTS);
      panel.notify({ kind: 'error', what: failure.message, todo: failure.remedy, key: `parts-limit:${key}` });
      return;
    }
    const quantity = clampQuantity(part.quantity);
    const { saved } = await storage.addPart({ sha256, units: part.units, name: part.name, record: null, quantity }, bytes);
    if (gen !== generation) return;
    const row = newRow({ sha256, units: part.units, name: part.name, source, quantity, saved });
    rows.push(row);
    publish();
    track(bring(row, bytes));
  }

  // Runs `body` after every part set handed over before it, so that parts are taken in order.
  function inTurn(body) {
    const run = adding.then(body);
    adding = run.catch(() => {});
    return track(run);
  }

  function addPartSet(partSet) {
    const gen = generation;
    return inTurn(async () => {
      for (const part of partSet.parts) await addOne(part, part.name, partSet.source, gen);
    });
  }

  // A file's part, read in its turn: its size is checked first, by the file's own size, before
  // its bytes are read; a file the browser cannot read is refused alone, and the others go on.
  // `units` is the switch's at the moment the files were handed over.
  async function addFile(f, units, gen) {
    if (f.size > MAX_PART_BYTES) {
      tellRefused(overSize(f.name, f.size), `size:${f.name}`);
      return;
    }
    let bytes;
    try {
      bytes = await f.arrayBuffer();
    } catch (error) {
      if (gen !== generation) return;
      tellRefused(fileUnreadable(f.name, `${error?.name ?? 'Error'}: ${error?.message ?? error}`), `unreadable:${f.name}`);
      return;
    }
    if (gen !== generation) return;
    const [part] = partSetOf([{ name: f.name, bytes }], units).parts;
    await addOne(part, f.name, 'file', gen);
  }

  return {
    rows: () => rows.map(({ stop, ...row }) => ({ ...row })),
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },

    // How the next STL files are read: the user's choice, kept in the browser's storage, or the
    // configuration's upload_units until there is one.
    units,
    setUnits(value) {
      if (!UNITS.includes(value)) throw new Error(`units must be "mm" or "in", not ${JSON.stringify(value)}`);
      chosenUnits = value;
      storage.setChoice('uploadUnits', value);
      for (const listener of listeners) listener(rows);
    },

    // Files the user dropped or chose, as the browser hands them over (File: name, size,
    // arrayBuffer()): one part set, read in the switch's units at this moment, each file read in
    // its turn. Resolves when each part is added or refused, not when its upload ends.
    addFiles(files) {
      const chosen = Array.from(files);
      const readIn = units();
      const gen = generation;
      return inTurn(async () => {
        for (const f of chosen) await addFile(f, readIn, gen);
      });
    },
    addPartSet: (partSet) => addPartSet(partSet),

    setQuantity(key, n) {
      const row = rows.find((r) => r.key === key);
      if (!row) return;
      row.quantity = clampQuantity(n);
      persist();
      publish();
    },

    async remove(key) {
      const row = rows.find((r) => r.key === key);
      if (row) await drop(row);
    },

    // The wizard's red message under the list when the parts together pass MAX_INSTANCES, counting
    // the parts still arriving, which will join the plate; or null.
    instanceProblem() {
      const total = rows.reduce((n, r) => n + r.quantity, 0);
      return total > MAX_INSTANCES ? tooManyInstances(total, MAX_INSTANCES) : null;
    },

    // Empties the plate: the parts, the layout and the slice go, with a new plate_id; the
    // filament, the profile and the changes stay. The caller asks the user first.
    async newPlate() {
      generation += 1;
      for (const row of rows) { row.stop.abort(); geometry.forget(row.key); }
      rows = [];
      publish();
      await adding;
      rows = [];
      const plate = await storage.newPlate({ keepSettings: true });
      store.set({ plateId: plate.plate_id, sliced: false, layoutProblem: null });
      publish();
    },

    // Takes up the stored plate's parts when the page opens: a part with its record has arrived
    // and is read for drawing; one without is uploaded again, its bytes being kept.
    async resume() {
      const stored = await storage.choice('uploadUnits');
      chosenUnits = UNITS.includes(stored) ? stored : null;
      const gen = generation;
      for (const part of storage.plate().parts) {
        const bytes = await storage.partBytes(part.sha256, part.units);
        if (gen !== generation) return;
        if (!bytes) { await storage.removePart(part.sha256, part.units); continue; }
        const record = part.record && !recordProblem(part.record) ? part.record : null;
        const row = newRow({
          sha256: part.sha256, units: part.units, name: part.name, quantity: clampQuantity(part.quantity ?? 1),
          saved: part.saved !== false, record, arriving: !record, warnings: record ? record.warnings : [],
        });
        rows.push(row);
        track(bring(row, bytes));
      }
      publish();
    },

    // Resolves once nothing is being added, read or uploaded: for the tests, an event.
    async idle() {
      while (work.size) await Promise.allSettled([...work]);
    },
  };
}
