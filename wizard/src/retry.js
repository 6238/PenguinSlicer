// Retrying (wizard/README-details.md, "Retrying"): which answers are retried quietly, the waits
// between attempts, and the board that knows every request still failing and tells the panel
// line what to show. The page retries so that a request falling in the gap of a deploy is
// repeated and the user sees a pause, not an error.
import {
  RETRY_FIRST_WAIT_S, RETRY_MAX_WAIT_S, RETRY_QUIET_S, RETRY_SPREAD, RETRY_TOTAL_S,
} from './page-constants.js';

const QUIET_CODES = new Set([
  'front.slice_unreachable', 'front.state_bucket_unreachable', 'front.too_many_requests', 'front.unexpected',
]);

// Whether an error report is one the page retries by itself, quietly (the contract's list).
// front.onshape_unreachable is a quiet retry on an /api/ request only.
export function isQuietRetry(report, path) {
  if (report.code === 'front.onshape_unreachable') return path.startsWith('/api/');
  return QUIET_CODES.has(report.code);
}

// The wait after the attempt numbered `index` (from 0) failed, in seconds: 1, 2, 4, 8, 16, then
// 30, each spread by up to a tenth either way so that many pages do not retry in step.
export function retryWaitS(index, random) {
  const plain = Math.min(RETRY_FIRST_WAIT_S * 2 ** index, RETRY_MAX_WAIT_S);
  return Math.round(plain * (1 + RETRY_SPREAD * (2 * random() - 1)) * 1e6) / 1e6;
}

const same = (a, b) => a.kind === b.kind && a.seconds === b.seconds;

// The board of failing requests. Each request that fails is an entry, from its first failure
// until it is answered; the panel line follows the entry that failed earliest:
//   {kind: 'none'}               nothing, up to RETRY_QUIET_S after its first failure
//   {kind: 'slow', seconds}      amber, counting down to its next attempt (0 while one is made)
//   {kind: 'unreachable'}        red, from RETRY_TOTAL_S, with Try again; and from RETRY_QUIET_S
//                                when a Retry-After leaves no attempt within RETRY_TOTAL_S
// The last attempt is at RETRY_TOTAL_S itself (api.js shortens the last wait), so the amber
// line always counts down to an attempt that will be made.
// The line goes the moment any request of the page's is answered; since the server has then
// answered, every request still waiting is sent again at once.
export function createRetryBoard(clock) {
  const entries = new Set();
  const listeners = new Set();
  let hidden = false;
  let shownState = { kind: 'none' };
  let timer = null;

  function earliest() {
    let first = null;
    for (const entry of entries) if (!first || entry.firstFailedAt < first.firstFailedAt) first = entry;
    return first;
  }

  function state() {
    const entry = earliest();
    if (!entry || hidden) return { kind: 'none' };
    const elapsed = clock.now() - entry.firstFailedAt;
    if (elapsed >= RETRY_TOTAL_S * 1000) return { kind: 'unreachable' };
    if (elapsed < RETRY_QUIET_S * 1000) return { kind: 'none' };
    // parked before its 300 s (a Retry-After past them): no attempt is left to count down to
    if (entry.parked) return { kind: 'unreachable' };
    const seconds = entry.nextAttemptAt === null ? 0 : Math.max(0, Math.ceil((entry.nextAttemptAt - clock.now()) / 1000));
    return { kind: 'slow', seconds };
  }

  // The next moment the shown state can change by the clock alone.
  function nextChange() {
    const entry = earliest();
    if (!entry || hidden) return null;
    const now = clock.now();
    const moments = [entry.firstFailedAt + RETRY_QUIET_S * 1000, entry.firstFailedAt + RETRY_TOTAL_S * 1000];
    if (entry.nextAttemptAt !== null && entry.nextAttemptAt > now) {
      const seconds = Math.ceil((entry.nextAttemptAt - now) / 1000);
      moments.push(entry.nextAttemptAt - (seconds - 1) * 1000);
    }
    const later = moments.filter((m) => m > now);
    return later.length ? Math.min(...later) : null;
  }

  function changed() {
    if (timer !== null) { clock.cancel(timer); timer = null; }
    const now = state();
    if (!same(now, shownState)) {
      shownState = now;
      for (const listener of listeners) listener(now);
    }
    const at = nextChange();
    if (at !== null) timer = clock.after(at - clock.now(), changed);
  }

  function wake(entry) {
    if (entry.timer !== null) { clock.cancel(entry.timer); entry.timer = null; }
    const resume = entry.resume;
    entry.resume = null;
    if (resume) resume();
  }

  return {
    state,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },

    // A request's attempt failed: its entry, made at its first failure, or at `since` (a moment in
    // the clock's milliseconds) for a request that counts as failing from then.
    failed(entry, since = null) {
      hidden = false;
      const made = entry ?? { firstFailedAt: since ?? clock.now(), nextAttemptAt: null, timer: null, resume: null, parked: false, again: false };
      entries.add(made);
      changed();
      return made;
    },

    // An attempt of the entry's request is being made.
    attempting(entry) {
      entry.nextAttemptAt = null;
      changed();
    },

    // Resolves at `at`, or sooner on Retry now or another request's answer: 'attempt'.
    waitUntil(entry, at) {
      entry.nextAttemptAt = at;
      entry.parked = false;
      return new Promise((resolve) => {
        entry.resume = () => resolve('attempt');
        entry.timer = clock.after(at - clock.now(), () => { entry.timer = null; wake(entry); });
        changed();
      });
    },

    // No attempt is left within RETRY_TOTAL_S: resolves on Try again or another request's
    // answer, and the request starts its count afresh.
    park(entry) {
      entry.nextAttemptAt = null;
      if (entry.again) {                         // Try again was pressed during the last attempt
        entry.again = false;
        entries.delete(entry);
        changed();
        return Promise.resolve('again');
      }
      entry.parked = true;
      return new Promise((resolve) => {
        entry.resume = () => { entries.delete(entry); resolve('again'); };
        changed();
      });
    },

    // The entry's request was answered.
    done(entry) {
      if (entry) { wake(entry); entries.delete(entry); }
    },

    // The entry's request was stopped by its caller: it wakes, leaves the board, and the line
    // follows the requests still failing.
    stop(entry) {
      if (!entry) return;
      wake(entry);
      entries.delete(entry);
      changed();
    },

    // Any request of the page's was answered.
    answered() {
      hidden = true;
      for (const entry of [...entries]) wake(entry);
      changed();
    },

    // Retry now: the next attempt of every waiting request, at once; the counts go on.
    retryNow() {
      for (const entry of [...entries]) if (!entry.parked) wake(entry);
      changed();
    },

    // Try again: an attempt at once of every request past its RETRY_TOTAL_S, each starting
    // its count afresh. One whose last attempt is still being made is sent again as soon as
    // that attempt fails.
    tryAgain() {
      const now = clock.now();
      for (const entry of [...entries]) {
        if (entry.parked) wake(entry);
        else if (now - entry.firstFailedAt >= RETRY_TOTAL_S * 1000) entry.again = true;
      }
      changed();
    },
  };
}
