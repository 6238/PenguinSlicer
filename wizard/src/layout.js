// The Layout step's behaviour (wizard/README-details.md, "The Layout step"), apart from its
// drawing (panel/layout-step.js, panel/layout-view.js): the plate's instances, the selection,
// moving and turning, laying an instance on a face, auto-orient, Arrange, the placement check
// and every message of the step. Every heavy job is a question to the worker
// (geometry/messages.js), so each has a "not yet" state; the answers are taken in the order the
// changes were made.
//
// An instance here is {id, part, lay, angle, x, y}: `part` is the key of its part's row
// ("<sha256>.<units>", the key the worker read it under), `lay` how it lies (a unit quaternion
// [w, x, y, z] out of the part's own coordinates), `angle` the degrees it is then turned about
// the vertical (a fraction only during a turn; whole when the turn ends) and `x`, `y` the centre
// of its footprint on the plate, in millimetres: the plate configuration's transform,
// p_plate = Rz(angle) M p_part + t (contracts/plate-configuration.md, "An instance in phase 2").
// The plate's instances are kept in the stored plate's `instances`, in that form.
//
// The instances follow the Parts step's quantities: they join the plate when the user is on the
// Layout step, at once, and otherwise the next time that step is shown. A new part's instances lie
// their best way (auto-orient) and say nothing; the first instances of a plate are arranged, and
// those that join a plate already laid out each take the free spot nearest the others' middle.
import { MAX_INSTANCES } from './geometry/constants.js';
import { instanceLabels, supportsOn } from './geometry/placement.js';
import { instanceTurn, layOnFace, rotateVector } from './geometry/turn.js';
import * as W from './layout-sentences.js';

const DOWN = [0, 0, -1];
const SAME_FACE = 1 - 1e-6;
const MODELLED = [1, 0, 0, 0];

const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const wholeAngle = (deg) => ((Math.round(deg) % 360) + 360) % 360;
const isQuaternion = (q) => Array.isArray(q) && q.length === 4 && q.every(finite) && Math.abs(Math.hypot(...q) - 1) < 1e-6;

// The direction, in the part's own coordinates, that points down when the part lies by `lay`.
export function downOf(lay) {
  const [w, x, y, z] = lay;
  return rotateVector([w, -x, -y, -z], DOWN);
}
const sameFace = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2] > SAME_FACE;

// An instance's orientation on the plate, in degrees: the turn about the vertical between how it
// lies and the same face put down straight from the part as modelled, plus its angle. Shift
// snaps this to multiples of 45 degrees.
export function plateAngle(instance) {
  const d = downOf(instance.lay);
  // the lay that puts the same face down straight from the part as modelled
  const straight = layOnFace(MODELLED, d);
  // r = lay * straight^-1, a turn about the vertical only
  const [aw, ax, ay, az] = instance.lay;
  const [bw, bx, by, bz] = [straight[0], -straight[1], -straight[2], -straight[3]];
  const rw = aw * bw - ax * bx - ay * by - az * bz;
  const rz = aw * bz + ax * by - ay * bx + az * bw;
  return (2 * Math.atan2(rz, rw) * 180) / Math.PI + instance.angle;
}

// What the stored plate keeps of an instance, and whether a stored one can be used.
const stored = ({ part, lay, angle, x, y }) => ({ part, lay, angle, x, y });
function usableStored(i) {
  return i && typeof i.part === 'string' && isQuaternion(i.lay) && Number.isInteger(i.angle) && i.angle >= 0 && i.angle < 360 && finite(i.x) && finite(i.y);
}

// Whether supports are on, as the plate configuration's contract decides it: the user's change
// of enable_support, else the chosen profile's own override, else the table's value for the
// profile's process (wizard/README-details.md, "The profile's value of a setting").
export function supportsFor(state, changes = {}) {
  if ('enable_support' in changes) return changes.enable_support === '1';
  const filament = state.configuration?.filaments?.find((f) => f.name === state.plate.filament);
  const profile = filament?.profiles?.find((p) => p.name === state.plate.profile);
  if (!profile) return false;
  const value = profile.overrides && 'enable_support' in profile.overrides
    ? profile.overrides.enable_support
    : state.settingsTable?.process_values?.[profile.process]?.enable_support;
  return supportsOn({ overrides: {} }, value);
}

// The printable area of the configuration's printer, from the table of settings' catalog entry:
// {min, max, height, name}, or null before both are read.
export function printerOf(state) {
  const p = state.printer;
  if (!p || !Array.isArray(p.printable_area) || !finite(p.printable_height)) return null;
  const xs = p.printable_area.map((c) => c[0]);
  const ys = p.printable_area.map((c) => c[1]);
  return { min: [Math.min(...xs), Math.min(...ys)], max: [Math.max(...xs), Math.max(...ys)], height: p.printable_height, name: state.configuration?.printer ?? p.name };
}

// createLayout({geometry, storage, store, parts, panel}):
//   geometry  the worker's client (geometry-client.js)
//   storage   the storage module, holding the tab's plate and its instances
//   store     the panel's store: the step, the configuration, the table, `layoutProblem`
//   parts     the Parts step's behaviour (parts.js): rows() and subscribe()
//   panel     {notify}: a question the worker could not answer is its error report, shown as a
//             notification (wizard.layout_failed, reported once by the worker's client when the
//             worker failed as a whole)
export function createLayout({ geometry, storage, store, parts, panel }) {
  let instances = [];
  let selected = [];
  let nextId = 1;
  const info = new Map();          // part key -> {best: {lay, normal}, patches, height}
  let checked = { problems: [], bounds: [], heights: [], fits: new Map(), at: -1 };
  let notes = { lay: null, arrange: null };
  let version = 0;                 // moves on with every change of the instances
  let checking = null;             // the check in flight
  let queue = Promise.resolve();
  const work = new Set();
  const listeners = new Set();
  let loaded = false;

  const on = () => store.get().step === 'layout';
  const rows = () => parts.rows().filter((r) => !r.arriving);
  const rowOf = (key) => rows().find((r) => r.key === key) || null;
  const byId = (id) => instances.find((i) => i.id === id) || null;
  const printer = () => printerOf(store.get());
  const supports = () => supportsFor(store.get(), storage.plate().settings?.changes || {});
  const spacingNow = () => (supports() ? 12 : 5);

  function failed(err) {
    const report = err && err.report;
    if (!report) throw err;
    panel.notify({ kind: 'error', what: report.message, todo: report.remedy, key: `layout:${report.code}` });
  }
  function track(promise) {
    const handled = promise.catch(failed);
    work.add(handled);
    handled.finally(() => work.delete(handled)).catch(() => {});
    return handled;
  }
  // Runs `body` after every change asked for before it, so that the worker's answers are taken in
  // the order the changes were made.
  function inTurn(body) {
    const run = queue.then(body);
    queue = run.catch(() => {});
    return track(run);
  }

  function tell() { for (const l of listeners) l(); }

  // ---- the plate configuration the worker is asked about
  function plateMessage(list = instances) {
    const keys = [...new Set(list.map((i) => i.part))];
    const refs = new Map(keys.map((k, n) => [k, `p${n + 1}`]));
    const partsField = {};
    const geometryField = {};
    for (const key of keys) {
      const row = rowOf(key);
      partsField[refs.get(key)] = { name: row ? row.name : 'part', sha256: key.split('.')[0], units: key.split('.')[1] };
      geometryField[refs.get(key)] = key;
    }
    const p = printer();
    return {
      plateConfiguration: {
        parts: partsField,
        instances: list.map((i) => ({ ref: refs.get(i.part), ...instanceTurn(i.lay, wholeAngle(i.angle)), x: i.x, y: i.y })),
        overrides: { enable_support: supports() ? '1' : '0' },
      },
      geometry: geometryField,
      printer: p ? { min: p.min, max: p.max, height: p.height } : null,
      supports: supports(),
    };
  }

  // The instance moved and turned as the worker's answer says. The answer carries the contract's
  // fields, whose `angle` may hold a quarter turn the lay was made of (an orientation followed by
  // whole degrees), so only the change from the angle sent is taken.
  function fromAnswer(instance, answer, sent) {
    return { ...instance, angle: wholeAngle(instance.angle + (answer.angle - sent.angle)), x: answer.x, y: answer.y };
  }
  // The angle a `fit` answer asks for, in the instance's own terms.
  const fitAngle = (instance, fit, sent) => wholeAngle(instance.angle + (fit.angle - sent.angle));

  // The names the messages use: the part's own name and a number counted as the slice service
  // counts its instances.
  function labels(list = instances) {
    const message = plateMessage(list);
    const counted = instanceLabels(message.plateConfiguration);
    return list.map((i, n) => `${rowOf(i.part)?.name ?? 'part'} #${counted[n].split(' #').pop()}`);
  }

  async function ask(question) {
    const answer = await question;
    if (!answer.ok) throw Object.assign(new Error(answer.error.detail), { report: answer.error });
    return answer.result;
  }

  // ---- the part's best way and its patches, found once for each part
  async function partInfo(key) {
    if (!info.has(key)) {
      const orient = await ask(geometry.orient(key));
      info.set(key, { best: { lay: orient.lay, normal: orient.normal }, patches: null });
    }
    return info.get(key);
  }

  async function patchesOf(key) {
    const known = await partInfo(key);
    if (!known.patches) known.patches = (await ask(geometry.faces(key))).patches;
    return known.patches;
  }

  // ---- the placement check, after every change; during a drag, the latest positions only
  function recheck() {
    version += 1;
    if (!checking) checking = track(runCheck().finally(() => { checking = null; }));
    return checking;
  }

  async function runCheck() {
    for (;;) {
      const at = version;
      const message = plateMessage();
      if (!message.printer || instances.length === 0) {
        checked = { problems: [], bounds: [], heights: [], fits: new Map(), at };
      } else {
        const result = await ask(geometry.check(message));
        // what each instance too long for the plate as it is turned would need
        const fits = new Map();
        for (const problem of result.problems) {
          if (problem.rule !== 'off_plate') continue;
          const i = problem.instances[0];
          if (!tooLong(problem.size, message.printer)) continue;
          const fit = await ask(geometry.fit(message, i));
          fits.set(i, { turns: fit.fits && fit.angle !== message.plateConfiguration.instances[i].angle });
        }
        checked = { ...result, fits, at };
      }
      if (version === at) break;
    }
    publish();
  }

  const frameOf = (p) => [p.max[0] - p.min[0] - 6, p.max[1] - p.min[1] - 6];
  function tooLong(size, p) {
    const [w, d] = frameOf(p);
    return size[0] > w + 1e-6 || size[1] > d + 1e-6;
  }
  const besideIndex = (n) => checked.bounds[n] && printer() && checked.bounds[n][0] > printer().max[0];

  // ---- the messages, from the check and the notes
  function problemMessages() {
    const p = printer();
    const list = labels();
    const out = [];
    if (!p || checked.at < 0) return out;
    const sup = supports();
    const spacing = spacingNow();
    const coveredBeside = Boolean(notes.arrange) || Boolean(notes.lay && notes.lay.beside);
    for (const problem of checked.problems) {
      const [n] = problem.instances;
      const instance = instances[n];
      if (!instance) continue;
      const units = instance.part.split('.')[1];
      if (problem.rule === 'off_plate') {
        if (tooLong(problem.size, p)) {
          const [w, d] = frameOf(p);
          const way = problem.size[0] > w + 1e-6 ? 'x' : 'y';
          const turns = Boolean(checked.fits.get(n)?.turns);
          const words = W.TOO_LONG(list[n], way, way === 'x' ? problem.size[0] : problem.size[1], units, way === 'x' ? w : d, !besideIndex(n), turns);
          out.push({ kind: 'error', ...words, instances: [instance.id], action: turns ? { label: W.TURN_TO_FIT, run: () => turnToFit([instance.id]) } : null });
        } else if (besideIndex(n)) {
          if (coveredBeside) continue;
          out.push({ kind: 'error', ...W.WAITS_BESIDE(list[n]), instances: [instance.id], action: { label: W.ARRANGE, run: () => arrange() } });
        } else {
          out.push({ kind: 'error', ...W.OFF_PLATE(list[n], problem.edges), instances: [instance.id], action: { label: W.ARRANGE, run: () => arrange() } });
        }
      } else if (problem.rule === 'too_tall') {
        out.push({ kind: 'error', ...W.TOO_TALL(list[n], problem.height, units, p.height), instances: [instance.id], action: { label: W.AUTO_ORIENT, run: () => autoOrient([instance.id]) } });
      }
    }
    const close = checked.problems.filter((q) => q.rule === 'too_close' && !besideIndex(q.instances[0]) && !besideIndex(q.instances[1]));
    if (close.length === 1) {
      const [a, b] = close[0].instances;
      out.push({ kind: 'error', ...W.TOO_CLOSE_TWO(list[a], list[b], close[0].distance, spacing, sup), instances: [instances[a].id, instances[b].id], action: { label: W.ARRANGE, run: () => arrange() } });
    } else if (close.length > 1) {
      const ids = [...new Set(close.flatMap((q) => q.instances))].sort((x, y) => x - y).map((n) => instances[n].id);
      out.push({ kind: 'error', ...W.TOO_CLOSE_MANY(ids.length, spacing, sup), instances: ids, action: { label: W.ARRANGE, run: () => arrange() } });
    }
    return out;
  }

  function besideCount() {
    return instances.filter((_, n) => besideIndex(n)).length;
  }

  // Everything the step draws, from one state.
  function model() {
    const p = printer();
    const problems = problemMessages();
    const beside = besideCount();
    if (notes.arrange && beside === 0) notes.arrange = null;
    const shownNotes = [notes.lay, notes.arrange].filter(Boolean);
    // An instance beside the plate that only a note accounts for still holds Next.
    const holdsByNote = beside > 0 && problems.every((m) => !m.instances.some((id) => besideIndex(instances.findIndex((i) => i.id === id))));
    const lines = problems.length + (holdsByNote && shownNotes.some((n) => n.beside) ? 1 : 0);
    let status;
    if (problems.length) {
      status = { ok: false, first: problems[0].what, more: lines > 1 ? W.MORE(lines - 1) : W.FIX };
    } else if (holdsByNote) {
      status = { ok: false, first: W.DO_NOT_FIT(beside), more: W.FIX };
    } else if (instances.length) {
      status = { ok: true, first: W.ALL_FIT(instances.length, labels()[0]) };
    } else {
      status = { ok: true, first: W.NO_INSTANCES };
    }
    const marked = new Set(problems.flatMap((m) => m.instances));
    for (let n = 0; n < instances.length; n++) if (besideIndex(n)) marked.add(instances[n].id);
    const names = labels();
    return {
      ready: Boolean(p) && loaded,
      instances: instances.map((i, n) => ({ ...i, label: names[n], beside: Boolean(besideIndex(n)), bounds: checked.bounds[n] || null, height: checked.heights[n] ?? null })),
      selected: selected.slice(),
      marked,
      status,
      notes: shownNotes,
      problems,
      selection: selectionLine(),
      link: selectionLink(),
      figures: p ? W.FIGURES(p.name, p.max[0] - p.min[0], p.max[1] - p.min[1], p.height, spacingNow()) : '',
      printer: p,
      holds: problems.length ? problems[0].what : (holdsByNote ? W.DO_NOT_FIT(beside) : null),
    };
  }

  function selectionLine() {
    const list = labels();
    const sel = selected.map(byId).filter(Boolean);
    if (sel.length === 0) {
      const beside = besideCount();
      return { text: W.ON_PLATE(instances.length - beside, beside) };
    }
    if (sel.length === 1) {
      const n = instances.indexOf(sel[0]);
      const b = checked.bounds[n];
      const h = checked.heights[n];
      const units = sel[0].part.split('.')[1];
      return { strong: list[n], text: b && h !== undefined ? W.FOOTPRINT([b[2] - b[0], b[3] - b[1]], h, units) : '' };
    }
    return { strong: W.TOGETHER(sel.length), text: W.TOGETHER_REST };
  }

  // "Put back as modelled" when laid differently from the model; "Lay it the best way" when it
  // lies as modelled and that is not its best way; nothing when it lies as modelled and that is
  // its best way. Only for instances of one part.
  function selectionLink() {
    const sel = selected.map(byId).filter(Boolean);
    if (!sel.length || sel.some((i) => i.part !== sel[0].part)) return null;
    const best = info.get(sel[0].part)?.best;
    const modelled = sel.every((i) => sameFace(downOf(i.lay), DOWN));
    if (!modelled) return { label: W.PUT_BACK, run: () => layAs(sel.map((i) => i.id), () => DOWN) };
    if (best && !sameFace(best.normal, DOWN)) return { label: W.LAY_BEST, run: () => layAs(sel.map((i) => i.id), (i) => info.get(i.part).best.normal) };
    return null;
  }

  function publish() {
    const m = model();
    store.set({ layoutProblem: on() || instances.length ? m.holds : store.get().layoutProblem });
    tell();
  }

  function persist() {
    return storage.update({ instances: instances.map(stored) });
  }

  // ---- the instances follow the parts
  function newInstance(key, best) {
    return { id: nextId++, part: key, lay: best.lay.slice(), angle: 0, x: 0, y: 0 };
  }

  async function join() {
    const present = rows();
    const keys = new Set(present.map((r) => r.key));
    let changed = false;
    const before = instances.filter((i) => keys.has(i.part));
    if (before.length !== instances.length) changed = true;
    instances = before;
    const fresh = [];
    for (const row of present) {
      const have = instances.filter((i) => i.part === row.key);
      const want = Math.min(row.quantity, MAX_INSTANCES);
      for (let k = have.length - 1; k >= want; k--) { instances.splice(instances.indexOf(have[k]), 1); changed = true; }
      if (have.length < want) {
        const { best } = await partInfo(row.key);
        for (let k = have.length; k < want; k++) fresh.push(newInstance(row.key, best));
      }
    }
    selected = selected.filter((id) => byId(id));
    if (fresh.length === 0) {
      if (changed) { await persist(); await recheck(); }
      return;
    }
    const laidOut = instances.length > 0;
    // a part that arrives too long for the plate as it lies is turned to fit before it is first
    // arranged; one turn for each part, all its instances lying alike
    const turnFor = new Map();
    for (const instance of fresh) {
      if (!turnFor.has(instance.part)) {
        const message = plateMessage([instance]);
        const sent = message.plateConfiguration.instances[0];
        turnFor.set(instance.part, message.printer ? fitAngle(instance, await ask(geometry.fit(message, 0)), sent) : 0);
      }
      instance.angle = turnFor.get(instance.part);
    }
    if (!laidOut) {
      instances = fresh;
      await arrangeAll({ say: false });
    } else {
      await recheck();
      const middle = middleOfPlaced();
      for (const instance of fresh) {
        instances.push({ ...instance, x: middle[0], y: middle[1] });
        const last = instances.length - 1;
        const message = plateMessage();
        const outcome = await ask(geometry.settle(message, last));
        instances[last] = fromAnswer(instances[last], outcome.instance, message.plateConfiguration.instances[last]);
      }
      await recheck();
    }
    await persist();
  }

  function middleOfPlaced() {
    const p = printer();
    const boxes = checked.bounds.filter((b, n) => b && !besideIndex(n));
    if (!boxes.length) return p ? [(p.min[0] + p.max[0]) / 2, (p.min[1] + p.max[1]) / 2] : [170, 160];
    const x0 = Math.min(...boxes.map((b) => b[0])), x1 = Math.max(...boxes.map((b) => b[2]));
    const y0 = Math.min(...boxes.map((b) => b[1])), y1 = Math.max(...boxes.map((b) => b[3]));
    return [(x0 + x1) / 2, (y0 + y1) / 2];
  }

  // ---- Arrange and what offers it
  async function arrangeAll({ say = true } = {}) {
    if (!printer() || instances.length === 0) return null;
    const message = plateMessage();
    const result = await ask(geometry.arrange(message));
    instances = instances.map((i, n) => fromAnswer(i, result.plateConfiguration.instances[n], message.plateConfiguration.instances[n]));
    await recheck();
    // Those left beside the plate, less any too long for it as it is turned, which have their
    // own message: Arrange's message counts the others.
    const left = result.placed.map((ok, n) => (ok ? -1 : n)).filter((n) => n >= 0);
    const long = left.filter((n) => checked.fits.has(n));
    const parked = left.length - long.length;
    const placed = result.placed.filter(Boolean).length;
    if (parked > 0) {
      const offer = await bestWayOffer(parked);
      notes.arrange = {
        kind: 'error', beside: true, what: W.ARRANGE_PARTIAL(placed, parked),
        todo: offer ? W.ARRANGE_PARTIAL_OFFER(offer.changed, offer.parked === 0) : W.ARRANGE_PARTIAL_TODO,
        actions: [
          ...(offer ? [{ label: W.LAY_THEM_BEST(offer.parked === 0, parked - offer.parked), run: () => layAllBestWay() }] : []),
          { label: W.BACK_TO_PARTS, run: () => store.set({ step: 'parts' }) },
        ],
        instances: left.map((n) => instances[n].id),
      };
    } else {
      notes.arrange = null;
    }
    return { placed, parked };
  }

  // Whether laying every instance that does not lie its best way the best way (turned to fit
  // if need be) would leave fewer beside the plate: {changed, parked}, or null.
  async function bestWayOffer(parked) {
    const notBest = instances.filter((i) => !sameFace(downOf(i.lay), info.get(i.part).best.normal));
    if (!notBest.length) return null;
    const trial = await bestLaid(instances, new Set(notBest.map((i) => i.id)));
    const result = await ask(geometry.arrange(plateMessage(trial)));
    const left = result.placed.filter((ok) => !ok).length;
    return left < parked ? { changed: notBest.length, parked: left } : null;
  }

  // The instances with those in `ids` laid their best way, keeping their turn about the
  // vertical, then turned to fit the plate when that leaves them too long for it.
  async function bestLaid(list, ids) {
    const out = list.map((i) => (ids.has(i.id) ? { ...i, lay: layOnFace(i.lay, info.get(i.part).best.normal) } : { ...i }));
    for (let n = 0; n < out.length; n++) {
      if (!ids.has(out[n].id)) continue;
      const message = plateMessage(out);
      out[n].angle = fitAngle(out[n], await ask(geometry.fit(message, n)), message.plateConfiguration.instances[n]);
    }
    return out;
  }

  // ---- laying instances another way, and what follows
  // Lays each of `ids` with the face `normalOf(instance)` (in its part's coordinates) down,
  // keeping its turn about the vertical, then finds each a free spot if it needs one. Laying
  // down never moves another instance.
  function layAs(ids, normalOf) {
    return inTurn(async () => {
      const list = ids.map(byId).filter(Boolean);
      const changed = [];
      for (const instance of list) {
        const normal = normalOf(instance);
        if (sameFace(downOf(instance.lay), normal)) continue;
        instance.lay = layOnFace(instance.lay, normal);
        changed.push(instance);
      }
      if (!changed.length) { notes.lay = null; publish(); return; }
      await afterLay(changed);
    });
  }

  async function afterLay(changed) {
    const outcomes = [];
    for (const instance of changed) {
      const n = instances.indexOf(instance);
      const message = plateMessage();
      const outcome = await ask(geometry.settle(message, n));
      instances[n] = fromAnswer(instance, outcome.instance, message.plateConfiguration.instances[n]);
      outcomes.push(outcome.how);
    }
    const label = labels()[instances.findIndex((i) => i.id === changed[0].id)];
    const parked = outcomes.filter((h) => h === 'beside').length;
    const moved = outcomes.filter((h) => h === 'moved' || h === 'turned').length;
    if (parked) {
      notes.lay = { kind: 'warn', beside: true, what: changed.length === 1 ? W.BESIDE_ONE(label) : W.BESIDE_MANY(parked), todo: W.BESIDE_TODO(parked), actions: [], instances: changed.map((i) => i.id) };
    } else if (moved) {
      notes.lay = { kind: 'ok', what: changed.length === 1 ? W.MOVED_ONE(label) : W.MOVED_MANY(moved), actions: [], instances: changed.map((i) => i.id) };
    } else {
      notes.lay = null;
    }
    await persist();
    await recheck();
  }

  // Auto-orient: the selected instances, or every instance when none is selected, laid their
  // best way; one then too long for the plate is turned to fit; when the plate then breaks a
  // rule other than the height, it is arranged again and says so.
  function autoOrient(ids = selected) {
    return inTurn(async () => {
      const chosen = new Set((ids.length ? ids : instances.map((i) => i.id)).filter((id) => byId(id)));
      const changing = new Set(instances.filter((i) => chosen.has(i.id) && !sameFace(downOf(i.lay), info.get(i.part).best.normal)).map((i) => i.id));
      if (!changing.size) { notes.lay = null; publish(); return; }
      instances = await bestLaid(instances, changing);
      await recheck();
      const crowded = checked.problems.some((p) => p.rule !== 'too_tall');
      notes.lay = null;
      if (crowded) {
        await arrangeAll();
        notes.lay = { kind: 'ok', what: W.ARRANGED_AGAIN, actions: [], instances: [] };
      }
      await persist();
      await recheck();
    });
  }

  function arrange() {
    return inTurn(async () => {
      const result = await arrangeAll();
      if (!result) return;
      notes.lay = result.parked === 0 ? { kind: 'ok', what: W.ARRANGED(result.placed), actions: [], instances: [] } : null;
      await persist();
      publish();
    });
  }

  // Turn it to fit: each instance turned as on arrival, then the plate arranged again.
  function turnToFit(ids) {
    return inTurn(async () => {
      const list = ids.map(byId).filter(Boolean);
      for (const instance of list) {
        const n = instances.indexOf(instance);
        const message = plateMessage();
        instance.angle = fitAngle(instance, await ask(geometry.fit(message, n)), message.plateConfiguration.instances[n]);
      }
      const result = await arrangeAll();
      const label = labels()[instances.findIndex((i) => i.id === list[0].id)];
      notes.lay = result && result.parked === 0
        ? { kind: 'ok', what: W.TURNED_AND_ARRANGED(list.length === 1 ? label : W.INSTANCES(list.length), result.placed), actions: [], instances: [] } : null;
      await persist();
      publish();
    });
  }

  // "Lay them the best way: all fit": done afresh on the plate as it is now.
  function layAllBestWay() {
    return inTurn(async () => {
      const notBest = new Set(instances.filter((i) => !sameFace(downOf(i.lay), info.get(i.part).best.normal)).map((i) => i.id));
      instances = await bestLaid(instances, notBest);
      const result = await arrangeAll();
      if (result) notes.lay = { kind: 'ok', what: W.LAID_BEST_AND_ARRANGED(notBest.size, result.placed, result.parked === 0), actions: [], instances: [] };
      await persist();
      publish();
    });
  }

  // ---- the selection
  function select(id, how = 'only') {
    if (how === 'none') selected = [];
    else if (how === 'all') selected = instances.map((i) => i.id);
    else if (how === 'toggle') selected = selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id];
    else if (how === 'set') selected = id.filter((s) => byId(s));
    else selected = byId(id) ? [id] : [];
    tell();
  }

  // ---- moving and turning, live during a drag; the end of a drag keeps it and checks it
  // `moves` is [{id, x, y}]: where each instance's footprint centre is now.
  function place(moves) {
    for (const m of moves) {
      const instance = byId(m.id);
      if (!instance) continue;
      instance.x = m.x;
      instance.y = m.y;
      if (m.angle !== undefined) instance.angle = m.angle;
    }
    recheck();
    tell();
  }

  // The end of a drag: each angle kept to a whole degree, the form the plate configuration
  // takes, the placement check run on that kept angle, and the instances stored.
  function endDrag() {
    return inTurn(async () => {
      for (const instance of instances) instance.angle = wholeAngle(instance.angle);
      await persist();
      await recheck();
    });
  }

  // A lay-down on a patch or a flat face: `normal` in the part's own coordinates.
  function layOnNormal(id, normal) {
    selected = [id];
    return layAs([id], () => normal);
  }

  // ---- the step entered and left
  store.subscribe((state, before) => {
    if (state.step === 'layout' && before.step !== 'layout') track(inTurn(join));
    if (before.step === 'layout' && state.step !== 'layout') {
      // a message about a move, and "Arranged 16 instances.", goes when the user leaves the step
      notes.lay = null;
      tell();
    }
    if (state.plate.filament !== before.plate.filament || state.plate.profile !== before.plate.profile
      || state.configuration !== before.configuration || state.settingsTable !== before.settingsTable || state.printer !== before.printer) {
      if (instances.length) recheck();
    }
  });
  parts.subscribe(() => { if (on() && loaded) track(inTurn(join)); });

  return {
    model,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    // Takes up the stored plate's instances when the page opens, before the parts have arrived;
    // they are matched to the parts when the Layout step is shown.
    resume() {
      const kept = (storage.plate().instances || []).filter(usableStored);
      instances = kept.map((i) => ({ id: nextId++, ...stored(i) }));
      loaded = true;
      if (on()) track(inTurn(join));
    },
    // The settings changed (supports on or off): the spacing follows, and nothing moves.
    settingsChanged() { if (instances.length) recheck(); },
    select,
    selectAll: () => select(null, 'all'),
    clearSelection: () => select(null, 'none'),
    place,
    endDrag,
    layOnNormal,
    autoOrient: (ids) => autoOrient(ids ?? selected),
    arrange,
    turnToFit,
    layAllBestWay,
    patches: (id) => { const i = byId(id); return i ? patchesOf(i.part) : Promise.resolve([]); },
    plateAngle: (id) => { const i = byId(id); return i ? plateAngle(i) : 0; },
    // Resolves once nothing is being joined, checked, laid or arranged: for the tests, an event.
    async idle() { while (work.size) await Promise.allSettled([...work]); },
  };
}
