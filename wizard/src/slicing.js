// The Preview step's behaviour while a plate is submitted and sliced (wizard/README-details.md,
// "The Preview step": "Submitting a plate", "The slicing card", "While the slice service is
// stopping", "No room to wait", "When a slice fails", "Orca's own sentence under Details"), apart
// from its drawing (panel/preview-step.js) and from the result's figures, the sliced file and
// Download (result.js), which read the sliced file's details this module keeps once the plate is
// sliced.
//
// Entering the step submits the plate, unless it is already sliced, or slicing, as it stands; a
// slice goes on when the user leaves the step, and the page goes on following it. A changed plate
// starts a new slice, which replaces that plate's own earlier unfinished slice in the slice
// service. A slice cannot be cancelled by hand: nothing here asks the slice service to stop one.
//
// What the step shows is one of:
//   idle    nothing yet
//   card    the slicing card: waiting behind others, waiting while the slice service is stopping,
//           or slicing; with no news while the front server cannot be reached
//   busy    no room to wait: an amber message with Slice again
//   failed  a red message: the error report's sentences, its buttons, and folded Details on the two
//           empty-layers failures
//   done    the plate is sliced: the sliced file's details (asked for when the done report lacks
//           them), from which the result, the layer preview and the Send step are drawn; the page
//           counts the details' expires_in_s on its own clock from the moment they arrived
//   expired the sliced plate has expired: a grey message with Slice again, on the Preview and Send
//           steps, in the wizard's sentence at the moment of expiry, or in the front server's when a
//           request was refused first as expired; the page does not slice again by itself
import { followJob } from './following.js';
import { SPACING_SUPPORTS_MM } from './geometry/constants.js';
import {
  MAX_PLATE_CONFIGURATION_BYTES, PART_MISSING_TRIES, RECONNECTED_LINE_S, RETRY_TOTAL_S, SLICED_FILE_KEEP_S,
} from './page-constants.js';
import { bodyBytes, fingerprint, plateConfiguration } from './plate-configuration.js';
import { retryWaitS } from './retry.js';
import { badAnswer } from './sentences.js';
import * as T from './slicing-sentences.js';

// A slice job's stages, in order, with their words (contracts/progress-report.md, "A slice job's
// reports").
export const STAGES = [
  ['queued', 'Waiting for the slicer'],
  ['building_plate', 'Building the plate'],
  ['slicing', 'Slicing the plate'],
  ['loading', 'Loading the plate'],
  ['preparing', 'Preparing to slice'],
  ['slicing_mesh', 'Slicing the parts into layers'],
  ['generating_walls', 'Generating walls'],
  ['generating_infill', 'Generating infill'],
  ['generating_supports', 'Checking and generating supports'],
  ['optimizing_toolpath', 'Optimizing the toolpath'],
  ['generating_gcode', 'Generating G-code'],
  ['exporting', 'Writing the sliced file'],
  ['reading_result', 'Reading the sliced file'],
];
const STAGE_INDEX = new Map(STAGES.map(([stage], i) => [stage, i]));
const LATE_FACTOR = 1.3;              // the mockup's: past 1.3 times the time expected, "taking longer"
const ID = /^[A-Za-z0-9_-]{1,64}$/;
const UNITS = new Set(['mm', 'in']);

// The codes the page acts on by name (contracts/error-report.md, "Codes a user interface acts
// on"), each with the wizard's buttons; every other code has those of the last row.
const ROWS = new Map([
  ...['slice.placement_off_plate', 'slice.placement_too_tall', 'slice.placement_too_close', 'slice.crosses_edge',
    'slice.nothing_on_plate', 'slice.left_off_plate', 'slice.too_many_instances', 'slice.too_many_parts',
    'slice.part_too_large', 'slice.bad_plate_configuration', 'slice.orca_too_close', 'slice.rests_on_an_edge']
    .map((code) => [code, ['layout']]),
  ['slice.empty_layers', ['supports', 'layout']],
  ['slice.empty_layers_with_supports', ['parts']],
  ...['slice.unknown_printer', 'slice.profiles_not_offered', 'slice.bad_overrides', 'slice.profile_unreadable',
    'wizard.plate_not_ready'].map((code) => [code, ['settings']]),
  ...['slice.no_layers', 'slice.print_empty', 'slice.output_too_large', 'front.sliced_file_too_large',
    'slice.out_of_memory', 'wizard.plate_configuration_over_size'].map((code) => [code, ['parts']]),
  ['slice.timeout', ['again', 'parts']],
  ['slice.orca_failed', ['again', 'layout']],
]);
const LAST_ROW = ['again', 'layout'];
// The two failures about a gap with nothing under it, the only ones with folded Details.
const GAP_CODES = new Set(['slice.empty_layers', 'slice.empty_layers_with_supports']);
const LABELS = {
  supports: T.SUPPORTS_AND_SLICE, again: T.SLICE_AGAIN,
  layout: T.BACK_TO.layout, parts: T.BACK_TO.parts, settings: T.BACK_TO.settings,
};

// The buttons of a failed slice, [{id, label}]: the one for the report's action where the action
// has one (enable_supports; slice_again), then the code's own, the first of them the primary.
export function failureButtons(report) {
  const ids = [];
  if (report.action === 'enable_supports') ids.push('supports');
  if (report.action === 'slice_again') ids.push('again');
  for (const id of ROWS.get(report.code) ?? LAST_ROW) if (!ids.includes(id)) ids.push(id);
  return ids.map((id, n) => ({ id, label: LABELS[id], primary: n === 0 }));
}

// m:ss, whole seconds, the minutes unbounded (the mockup's clock).
export function clockText(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

const isErrorReport = (r) => r !== null && typeof r === 'object' && typeof r.code === 'string'
  && typeof r.message === 'string' && typeof r.remedy === 'string';

// The sliced file's details (contracts/wizard-front-server.md, "The sliced file's details"), as
// far as the page relies on them: the name a download is offered under, and the summary.
export const isDetails = (d) => d !== null && typeof d === 'object' && typeof d.file === 'string'
  && d.summary !== null && typeof d.summary === 'object';

// The front server's refusal of a sliced file that has expired or gone.
export const EXPIRED_CODE = 'front.sliced_file_expired';
// The key of a notification that says the sliced plate "is still here", which goes at the moment
// the sliced plate expires, since it has stopped being true.
export const STILL_HERE_NOTICE = 'sliced-plate-still-here';

// createSlicing({api, clock, storage, store, settings, layout, panel, report, newId, random, mode, follow}):
//   storage   the storage module: the tab's plate, its parts' bytes, and the slice it keeps
//   store     the panel's store: the step, the configuration, and `sliced`
//   settings  {setQuick}: Turn on Supports and slice again sets the Supports quick change
//   layout    {idle, notSliced}: the placement check run (idle resolves once it is), and the line
//             the Layout step shows above its usual message when supports need more room
//   panel     {goTo, dropNotice}: the wizard's own Back to Layout, Back to Parts and Back to
//             Settings, and the notification that goes when the sliced plate expires
//   report(what, {detail})  a failure report about the page itself
//   newId()   a new random UUID, for each submission
//   mode      'stream' (the default) or 'ask': how a slice job is followed
//   ready()   resolves once the plate can be read as it stands (the page opened, the Layout step's
//             work done); by default layout.idle()
export function createSlicing({
  api, clock, storage, store, settings, layout, panel, report, newId, random = Math.random, mode = 'stream', follow = followJob,
  ready = () => layout.idle(),
}) {
  let run = 0;                  // moves on each time the page decides to slice; older work stops
  let current = null;           // {id, submissionId, fingerprint, submittedMs, body}
  let expiry = null;            // the timer of the sliced plate's expiry
  let view = { kind: 'idle' };
  let card = null;
  let follower = null;
  let lastSequence = -Infinity;
  const pauses = new Set();
  let parked = null;
  let checking = false;
  const listeners = new Set();

  const tell = () => { for (const listener of listeners) listener(); };

  // ---- the plate configuration of the plate as it stands
  function make(submissionId) {
    const plate = storage.plate();
    return plateConfiguration({ plate, configuration: store.get().configuration, plateId: plate.plate_id, submissionId, now: clock.now() });
  }

  function setSliced(value) {
    if (store.get().sliced !== value) store.set({ sliced: value });
  }

  // ---- ending work that a newer decision replaces
  function stopFollowing() {
    if (follower) { follower.stop(); follower = null; }
  }
  function endWaits() {
    for (const pause of [...pauses]) pause();
    if (parked) { api.board.stop(parked); parked = null; }
  }
  function wait(ms) {
    return new Promise((resolve) => {
      const timer = clock.after(ms, () => { pauses.delete(end); resolve(); });
      const end = () => { clock.cancel(timer); pauses.delete(end); resolve(); };
      pauses.add(end);
    });
  }

  // ---- what the step shows
  function show(next) {
    view = next;
    if (next.kind !== 'card') card = null;
    if (next.kind !== 'done') endExpiry();
    const expired = next.kind === 'expired';
    if (Boolean(store.get().expired) !== expired) store.set({ expired });
    tell();
  }
  function fail(errorReport) {
    stopFollowing();
    setSliced(false);
    show({ kind: 'failed', report: errorReport });
  }

  // ---- a sliced plate and its expiry
  function endExpiry() {
    if (expiry !== null) { clock.cancel(expiry); expiry = null; }
  }
  // The sliced file's details, from the done report, the summary or a later answer: the moment of
  // expiry counted on the page's own clock from now, never from expires_at; none while it is null.
  function takeDetails(details) {
    if (view.kind !== 'done' || !isDetails(details)) return;
    view = { ...view, details };
    endExpiry();
    const s = details.expires_in_s;
    if (typeof s === 'number' && Number.isFinite(s)) {
      expiry = clock.after(Math.max(0, s) * 1000, () => { expiry = null; expire(null); });
    }
    tell();
  }
  // The sliced plate has expired: the wizard's sentence at the moment of expiry (report null), or
  // the front server's refusal's when a request was refused first. Nothing is sliced by itself.
  function expire(report) {
    if (!current) return;
    stopFollowing();
    endWaits();
    setSliced(false);
    show({
      kind: 'expired', report,
      what: report ? report.message : T.EXPIRED_WHAT,
      todo: report ? report.remedy : T.EXPIRED_TODO,
    });
    if (panel.dropNotice) panel.dropNotice(STILL_HERE_NOTICE);
  }
  async function askDetails(mine) {
    const path = `/api/slices/${encodeURIComponent(current.id)}/summary`;
    const answer = await api.get(path);
    if (mine !== run || view.kind !== 'done') return;
    if (answer.ok && answer.body && isDetails(answer.body.sliced_file)) takeDetails(answer.body.sliced_file);
    else if (answer.ok) fail(badAnswer(path, answer.status, JSON.stringify(answer.body)));
    else if (answer.report.code === EXPIRED_CODE) expire(answer.report);
    else fail(answer.report);
  }

  function newCard({ since, restarted }) {
    card = {
      phase: 'queued', report: null, since, arrivedAt: since, fraction: null, lastKnown: 0, unknown: false,
      restarted, lost: api.board.state().kind !== 'none', lastNewsS: 0, reportSinceLost: false, reconnected: null,
    };
    lastSequence = -Infinity;
  }

  function elapsedS(now) {
    if (!card) return 0;
    // a report's own elapsed_s when it carries a number (the contract requires one); otherwise
    // the time since the card began
    if (card.phase === 'running' && card.report && Number.isFinite(card.report.elapsed_s)) {
      return card.report.elapsed_s + (now - card.arrivedAt) / 1000;
    }
    return (now - card.since) / 1000;
  }

  function reconnect() {
    card.lost = false;
    card.reportSinceLost = false;
    const now = clock.now();
    card.reconnected = { text: T.RECONNECTED(clockText(elapsedS(now))), until: now + RECONNECTED_LINE_S * 1000 };
  }

  // The front server cannot be reached while any request has failed for RETRY_QUIET_S, or the
  // progress stream counts as failed: the panel line shows. The first report after says so.
  api.board.subscribe((state) => {
    if (!card) return;
    if (state.kind !== 'none') {
      if (!card.lost) { card.lost = true; card.reportSinceLost = false; card.reconnected = null; tell(); }
    } else if (card.lost && card.reportSinceLost) {
      reconnect();
      tell();
    }
  });

  function updateCard(r) {
    const now = clock.now();
    if (r.state === 'queued') {
      card.phase = 'queued';
      card.report = r;
    } else {
      card.phase = 'running';
      card.report = r;
      card.arrivedAt = now;
      if (typeof r.fraction === 'number' && Number.isFinite(r.fraction)) card.fraction = Math.min(1, Math.max(0, r.fraction));
      if (STAGE_INDEX.has(r.stage)) { card.lastKnown = STAGE_INDEX.get(r.stage); card.unknown = false; } else card.unknown = true;
    }
    card.lastNewsS = elapsedS(now);
    if (card.lost) {
      card.reportSinceLost = true;
      if (api.board.state().kind === 'none') reconnect();
    }
  }

  // ---- following a slice job
  function onReport(mine, r) {
    if (mine !== run || !current) return;
    if (typeof r.job === 'string' && current.id && r.job !== current.id) return;
    if (Number.isInteger(r.sequence)) {
      if (r.sequence <= lastSequence) return;
      lastSequence = r.sequence;
    }
    if (r.state === 'queued' || r.state === 'running') {
      if (!card) newCard({ since: clock.now(), restarted: false });
      updateCard(r);
      if (view.kind !== 'card') view = { kind: 'card' };
      tell();
    } else if (r.state === 'done') {
      stopFollowing();
      setSliced(true);
      show({ kind: 'done', report: r, details: null, slice: current.id, body: current.body });
      if (isDetails(r.sliced_file)) takeDetails(r.sliced_file);
      else askDetails(mine);
    } else if (r.state === 'failed') {
      // the sliced file stored and since expired is the done report turned failed
      if (isErrorReport(r.error) && r.error.code === EXPIRED_CODE) expire(r.error);
      else fail(isErrorReport(r.error) ? r.error : badAnswer(`/api/slices/${current.id}`, 200, JSON.stringify(r)));
    } else if (r.state === 'cancelled') {
      stopFollowing();
      // asked to stop before it ran: the page submits the plate again by itself; replaced by the
      // same plate's later slice: that one is already followed
      if (r.cancel_reason === 'shutdown') slice({ restarted: true });
    }
  }

  function onRefused(mine, r) {
    if (mine !== run || !current) return;
    follower = null;
    if (r.code === 'front.slice_unknown') {
      // neither the slice service nor the state bucket knows it: a slice service that restarted,
      // when it was submitted less than two hours ago, by the page's own clock, and the page
      // submits again by itself; two hours or more, it has expired, and the page does not slice
      // again by itself: the expired message, in the wizard's sentence, and entering the step
      // again slices
      if (clock.now() - current.submittedMs < SLICED_FILE_KEEP_S * 1000) slice({ restarted: true });
      else expire(null);
      return;
    }
    if (r.code === EXPIRED_CODE) { expire(r); return; }
    fail(r);
  }

  function startFollowing(mine) {
    stopFollowing();
    follower = follow({
      api, clock, random, mode, path: `/api/slices/${encodeURIComponent(current.id)}`,
      onReport: (r) => onReport(mine, r), onRefused: (r) => onRefused(mine, r),
    });
  }

  // ---- submitting
  async function uploadAgain(missing, refusal) {
    for (const part of missing) {
      if (!part || typeof part.sha256 !== 'string' || !UNITS.has(part.units)) return refusal;
      const bytes = await storage.partBytes(part.sha256, part.units);
      if (!bytes) return refusal;
      const refused = await uploadOne(part, bytes);
      if (refused) return refused;
    }
    return null;
  }

  // One part uploaded again; its record must name the hash and units asked for, as for a first
  // upload (parts.js): once more when it names others, and the second time a fault, shown and
  // reported.
  async function uploadOne(part, bytes) {
    const path = `/api/parts?units=${part.units}`;
    let answer;
    for (let tries = 0; tries < 2; tries += 1) {
      answer = await api.post(path, { bytes, upload: true });
      if (!answer.ok) return answer.report;
      const record = answer.body;
      if (record && record.sha256 === part.sha256 && record.units === part.units) return null;
    }
    const detail = `POST ${path}: the record named another part twice; the page asked for ${part.sha256}.${part.units}`;
    report('page_failed', { part_sha256: part.sha256, detail });
    return { ...badAnswer(path, answer.status, JSON.stringify(answer.body)), detail };
  }

  function accept(mine, body) {
    const slice = body && body.slice;
    if (!slice || typeof slice.id !== 'string' || !ID.test(slice.id)) {
      fail(badAnswer('/api/slices', 202, JSON.stringify(body)));
      return;
    }
    current.id = slice.id;
    storage.update({ slice: { id: slice.id, submission_id: current.submissionId, fingerprint: current.fingerprint, submitted_ms: current.submittedMs } });
    const first = slice.progress;
    if (first && typeof first === 'object') onReport(mine, { ...first, job: first.job ?? slice.id });
    if (mine === run && view.kind === 'card') startFollowing(mine);
  }

  async function submit(mine, body) {
    let missingRounds = 0;
    let stoppingSince = null;
    let index = 0;
    for (;;) {
      if (mine !== run) return;
      const answer = await api.post('/api/slices', { json: body });
      if (mine !== run) return;
      if (answer.ok) { accept(mine, answer.body); return; }
      const r = answer.report;
      if (r.code === 'slice.part_missing') {
        const missing = r.where && Array.isArray(r.where.missing_parts) ? r.where.missing_parts : null;
        if (!missing || !missing.length) {
          report('page_failed', { detail: `POST /api/slices answered slice.part_missing naming no part: ${r.detail ?? ''}`.slice(0, 1000) });
          fail(r);
          return;
        }
        missingRounds += 1;
        if (missingRounds > PART_MISSING_TRIES) {
          report('page_failed', { detail: `POST /api/slices answered slice.part_missing ${missingRounds} times for submission ${current.submissionId}: ${r.detail ?? ''}`.slice(0, 1000) });
          fail(r);
          return;
        }
        const refused = await uploadAgain(missing, r);
        if (mine !== run) return;
        if (refused) { fail(refused); return; }
        continue;
      }
      if (r.code === 'slice.stopping') {
        // the slice service takes no new slice while it stops: the card waits, and the same
        // plate configuration is sent again at the waits of retrying, for up to RETRY_TOTAL_S;
        // the panel line stays empty until then, since the front server answered
        const now = clock.now();
        if (stoppingSince === null) stoppingSince = now;
        if (card) { card.phase = 'stopping'; card.report = null; }
        tell();
        const deadline = stoppingSince + RETRY_TOTAL_S * 1000;
        if (now >= deadline) {
          parked = api.board.failed(null, stoppingSince);
          await api.board.park(parked);
          parked = null;
          if (mine !== run) return;
          stoppingSince = clock.now();
          index = 0;
          continue;
        }
        const at = Math.min(now + retryWaitS(index, random) * 1000, deadline);
        index += 1;
        await wait(at - now);
        continue;
      }
      if (r.code === 'slice.busy') {
        setSliced(false);
        show({ kind: 'busy', report: r });
        return;
      }
      fail(r);
      return;
    }
  }

  // The page decides to slice: a new submission value, the card from its start.
  async function slice({ restarted = false } = {}) {
    run += 1;
    const mine = run;
    stopFollowing();
    endWaits();
    const submissionId = newId();
    const built = make(submissionId);
    if (!built.configuration) {
      current = null;
      fail(T.plateNotReady(built.problem));
      return;
    }
    const body = built.configuration;
    current = { id: null, submissionId, fingerprint: fingerprint(body), submittedMs: clock.now(), body };
    setSliced(false);
    const bytes = bodyBytes(body);
    if (bytes > MAX_PLATE_CONFIGURATION_BYTES) {
      fail(T.plateConfigurationOverSize(bytes, MAX_PLATE_CONFIGURATION_BYTES));
      return;
    }
    newCard({ since: clock.now(), restarted });
    show({ kind: 'card' });
    await submit(mine, body);
  }

  // Turn on Supports and slice again: supports need 12 mm between instances, so the placement
  // check runs first; a plate that does not pass goes to the Layout step, and nothing moves.
  async function supportsAndSlice() {
    settings.setQuick('supports', '1');
    await layout.idle();
    if (store.get().layoutProblem) {
      layout.notSliced(T.NOT_SLICED_SUPPORTS(SPACING_SUPPORTS_MM));
      panel.goTo('layout');
      return;
    }
    await slice();
  }

  // A slice kept in the stored plate, of the plate as it stands: followed, not submitted again.
  function resume(kept, body) {
    run += 1;
    const mine = run;
    stopFollowing();
    endWaits();
    current = { id: kept.id, submissionId: kept.submission_id, fingerprint: kept.fingerprint, submittedMs: kept.submitted_ms, body };
    newCard({ since: clock.now(), restarted: false });
    show({ kind: 'card' });
    startFollowing(mine);
  }

  async function enter() {
    await ready();
    if (store.get().step !== 'preview') return;        // left again before the plate could be read
    const built = make('probe');
    if (!built.configuration) {
      run += 1;
      stopFollowing();
      endWaits();
      current = null;
      fail(T.plateNotReady(built.problem));
      return;
    }
    const fp = fingerprint(built.configuration);
    // slicing or sliced as it stands: nothing changes; a failed plate, or one that found no room to
    // wait, is not sliced, so it is submitted again (wizard/README.md, "Slicing")
    if (current && current.fingerprint === fp && (view.kind === 'card' || view.kind === 'done')) return;
    const kept = storage.plate().slice;
    if (!current && kept && typeof kept.id === 'string' && kept.fingerprint === fp && Number.isFinite(kept.submitted_ms)) {
      resume(kept, built.configuration);
      return;
    }
    await slice();
  }

  store.subscribe((state, before) => {
    if (state.step === 'preview' && before.step !== 'preview') enter();
  });

  function cardModel(now) {
    const c = card;
    const stalled = c.lost;
    const elapsed = elapsedS(now);
    const r = c.report;
    let stage;
    let left = '';
    let late = false;
    if (c.phase === 'stopping') stage = T.RESTARTING;
    else if (c.phase === 'queued') stage = r && Number.isInteger(r.ahead) && r.ahead > 0 ? T.WAITING_AHEAD(r.ahead) : (r?.stage_label || T.WAITING);
    else {
      stage = r.stage_label || (STAGE_INDEX.has(r.stage) ? STAGES[STAGE_INDEX.get(r.stage)][1] : '');
      if (typeof r.expected_s === 'number' && r.expected_s > 0) {
        late = elapsed > r.expected_s * LATE_FACTOR;
        const remaining = r.expected_s - elapsed;
        left = late ? T.LONGER_THAN(clockText(r.expected_s)) : remaining > 1 ? T.ABOUT_LEFT(clockText(remaining)) : T.FINISHING;
      }
    }
    if (stalled) {
      left = T.NO_NEWS_SINCE(clockText(c.lastNewsS));
      if (c.phase === 'running') stage = T.LAST_HEARD(stage);
    }
    const running = c.phase === 'running';
    const fraction = running && c.fraction !== null ? c.fraction : 0;
    const current = running ? c.lastKnown : 0;
    const stages = STAGES.map(([, label], i) => {
      if (running && c.unknown) return { label, state: i <= current ? 'done' : '' };
      return { label, state: i < current ? 'done' : i === current ? 'now' : '' };
    });
    let conn = null;
    if (c.reconnected && now < c.reconnected.until) conn = { kind: 'back', text: c.reconnected.text };
    else if (c.restarted) conn = { kind: 'restart', text: T.SLICER_RESTARTED };
    return {
      pct: running && c.fraction !== null ? `${Math.floor(c.fraction * 100)}%` : '',
      fraction,
      litLayers: stalled ? 0 : Math.min(4, Math.floor(fraction * 5)),     // none while there is no news, as the mockup's
      stage,
      elapsed: clockText(elapsed),
      elapsedWord: running ? T.ELAPSED : T.WAITED,
      left,
      late,
      stalled: stalled || late,
      stages,
      line: T.SLICING_GOES_ON,
      conn,
    };
  }

  // Slice again from the expired message: on the Preview step it submits; on the Send step it goes
  // to the Preview step, whose entering submits the plate, which is not sliced.
  function sliceExpired() {
    if (store.get().step === 'preview') return slice();
    panel.goTo('preview');
    return Promise.resolve();
  }

  const act = (id) => {
    if (id === 'again') return () => slice();
    if (id === 'supports') return () => supportsAndSlice();
    return () => panel.goTo(id);
  };

  return {
    // What the step shows, worked out at this moment.
    model() {
      const now = clock.now();
      if (view.kind === 'card' && card) return { kind: 'card', card: cardModel(now) };
      if (view.kind === 'busy') {
        return {
          kind: 'busy', report: view.report, what: view.report.message, todo: `${view.report.remedy} ${T.PLATE_UNCHANGED}`,
          actions: [{ id: 'again', label: T.SLICE_AGAIN, primary: true, run: act('again') }],
        };
      }
      if (view.kind === 'failed') {
        const r = view.report;
        const details = GAP_CODES.has(r.code) && typeof r.orca_sentence === 'string' && r.orca_sentence ? T.ORCA_SAYS(r.orca_sentence) : null;
        return {
          kind: 'failed', report: r, what: r.message, todo: r.remedy, details,
          actions: failureButtons(r).map((b) => ({ ...b, run: act(b.id) })),
        };
      }
      if (view.kind === 'done') return { kind: 'done', report: view.report, details: view.details, slice: view.slice, body: view.body };
      if (view.kind === 'expired') {
        return {
          kind: 'expired', report: view.report, what: view.what, todo: view.todo,
          actions: [{ id: 'again', label: T.SLICE_AGAIN, primary: true, run: sliceExpired }],
        };
      }
      return { kind: 'idle' };
    },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    // The plate may have changed (a part, an instance, a setting): it is sliced only while it is the
    // plate the sliced file was made of. Worked out after the change has been told to everyone, so
    // that a store listener is never handed an older state after a newer one.
    plateChanged() {
      if (view.kind !== 'done' || !current || checking) return;
      checking = true;
      queueMicrotask(() => {
        checking = false;
        if (view.kind !== 'done' || !current) return;
        const built = make('probe');
        setSliced(Boolean(built.configuration) && fingerprint(built.configuration) === current.fingerprint);
      });
    },
    enter,
    sliceAgain: () => slice(),
    // The sliced file's details answered later (Download asks them first): the moment of expiry
    // counted afresh from their arrival.
    takeDetails,
    // A request about the sliced plate `slice` refused as expired (the file, the summary): the
    // expired message with the front server's sentence.
    expire(report, slice) {
      if (view.kind === 'done' && view.slice === slice) expire(report);
    },
  };
}
