// The module that makes every request of the page's (wizard/README-details.md, "Every request:
// headers, answers and retrying"), so that each rule of the contract's "Rules for every
// request" is written once:
// - X-PenguinSlicer-Page, the page's own version, on every request;
// - X-PenguinSlicer-Group, the current group, on every request that acts for a group;
// - X-PenguinSlicer-Wizard: 1, the wizard's mark, on every POST, PUT and DELETE;
// - every answer's X-PenguinSlicer-Version told to whoever listens (reloading for a new version);
// - retrying, quietly and then on the panel line, through the retry board (retry.js).
// The page never reads the cookie; the browser attaches it. It reaches the network only through
// the transport seam and the time only through the clock seam.
import { ATTEMPT_TIMEOUT_S, RETRY_TOTAL_S, ROW_SLOW_S, UPLOAD_ATTEMPT_TIMEOUT_S } from './page-constants.js';
import { createRetryBoard, isQuietRetry, retryWaitS } from './retry.js';
import { badAnswer } from './sentences.js';

// The requests that act for no group (the contract's "Group: none").
const NO_GROUP = new Set(['/api/me', '/api/settings-table', '/api/signout']);
const CHANGING = new Set(['POST', 'PUT', 'DELETE']);

function isErrorReport(body) {
  return body !== null && typeof body === 'object' && typeof body.code === 'string'
    && typeof body.message === 'string' && typeof body.remedy === 'string';
}

// What one attempt gave: {answer: result} when the front server answered for good, or
// {retry: true, retryAfterS} when the attempt counts as failed and is made again.
async function attemptOnce({ transport, clock, method, path, headers, body, timeoutS, expect, tellVersion }) {
  const controller = new AbortController();
  const timer = clock.after(timeoutS * 1000, () => controller.abort());
  try {
    let answer;
    try {
      answer = await transport.send({ method, path, headers, body, signal: controller.signal });
    } catch {
      return { retry: true };                       // no answer: the connection failed or timed out
    }
    const version = answer.header('X-PenguinSlicer-Version');
    if (!version) return { retry: true };           // not the front server's answer
    tellVersion(version);
    const success = answer.status >= 200 && answer.status < 300;
    let content = null;
    if (answer.status !== 204) {
      try {
        content = success && expect === 'bytes' ? await answer.bytes() : await answer.json();
      } catch (error) {
        if (error && error.name === 'SyntaxError') {
          return { answer: { ok: false, status: answer.status, report: badAnswer(path, answer.status, error.message) } };
        }
        return { retry: true };                     // the body was cut off
      }
    }
    if (success) return { answer: { ok: true, status: answer.status, body: content } };
    if (!isErrorReport(content)) {
      return { answer: { ok: false, status: answer.status, report: badAnswer(path, answer.status, JSON.stringify(content)) } };
    }
    if (isQuietRetry(content, path)) {
      const after = Number.parseFloat(answer.header('Retry-After') ?? '');
      return { retry: true, retryAfterS: Number.isFinite(after) && after > 0 ? after : 0 };
    }
    return { answer: { ok: false, status: answer.status, report: content } };
  } finally {
    clock.cancel(timer);
  }
}

// createApi({transport, clock, version, currentGroup, random}):
//   request(method, path, options) resolves to {ok: true, status, body} or
//     {ok: false, status, report}, the report an error report shown as it is. It retries every
//     quiet failure until it is answered, never giving up: after RETRY_TOTAL_S it waits for Try
//     again (or for another request's answer). Options: json (a body sent as JSON), bytes (a
//     body sent as it is), upload (the longer attempt time), expect ('json' or 'bytes'),
//     onSlow (called once, ROW_SLOW_S after the first failure), once (the page's reports about
//     itself: one attempt, and {ok: false, dropped: true} on any failure).
//   get, post, put: request with that method.
//   link(path): a plain link's address, naming the current group in its query.
//   pending(): the requests sent and not yet answered.
//   waiting(): of those, the ones waiting between attempts or for Try again.
//   onVersion(listener): told every answer's X-PenguinSlicer-Version.
//   board: the retry board, for the panel line.
export function createApi({ transport, clock, version, currentGroup = () => null, random = Math.random }) {
  const board = createRetryBoard(clock);
  const versionListeners = new Set();
  let pending = 0;
  let waiting = 0;

  function headersFor(method, path, options) {
    const headers = { 'X-PenguinSlicer-Page': version };
    const group = currentGroup();
    if (group && !NO_GROUP.has(path.split('?')[0])) headers['X-PenguinSlicer-Group'] = group;
    if (CHANGING.has(method)) headers['X-PenguinSlicer-Wizard'] = '1';
    if (options.json !== undefined) headers['Content-Type'] = 'application/json';
    else if (options.bytes !== undefined) headers['Content-Type'] = 'application/octet-stream';
    return headers;
  }

  async function request(method, path, options = {}) {
    const { json, bytes, upload = false, expect = 'json', onSlow = null, once = false } = options;
    const attempt = () => attemptOnce({
      transport, clock, method, path,
      headers: headersFor(method, path, options),
      body: json !== undefined ? JSON.stringify(json) : bytes,
      timeoutS: upload ? UPLOAD_ATTEMPT_TIMEOUT_S : ATTEMPT_TIMEOUT_S,
      expect,
      tellVersion: (v) => { for (const listener of versionListeners) listener(v); },
    });

    pending += 1;
    try {
      if (once) {
        const outcome = await attempt();
        if (outcome.answer) board.answered();
        return outcome.answer && outcome.answer.ok ? outcome.answer : { ok: false, dropped: true };
      }
      let entry = null;
      let index = 0;
      let slowTimer = null;
      try {
        for (;;) {
          if (entry) board.attempting(entry);
          const outcome = await attempt();
          if (outcome.answer) {
            board.done(entry);
            board.answered();
            return outcome.answer;
          }
          const now = clock.now();
          if (!entry && onSlow && slowTimer === null) slowTimer = clock.after(ROW_SLOW_S * 1000, onSlow);
          entry = board.failed(entry);
          const wait = Math.max(retryWaitS(index, random), outcome.retryAfterS ?? 0) * 1000;
          index += 1;
          waiting += 1;
          try {
            if (now + wait > entry.firstFailedAt + RETRY_TOTAL_S * 1000) {
              await board.park(entry);
              entry = null;
              index = 0;
            } else {
              await board.waitUntil(entry, now + wait);
            }
          } finally {
            waiting -= 1;
          }
        }
      } finally {
        if (slowTimer !== null) clock.cancel(slowTimer);
      }
    } finally {
      pending -= 1;
    }
  }

  return {
    request,
    get: (path, options) => request('GET', path, options),
    post: (path, options) => request('POST', path, options),
    put: (path, options) => request('PUT', path, options),
    link(path) {
      const group = currentGroup();
      if (!group) return path;
      return `${path}${path.includes('?') ? '&' : '?'}group=${encodeURIComponent(group)}`;
    },
    pending: () => pending,
    waiting: () => waiting,
    onVersion(listener) { versionListeners.add(listener); return () => versionListeners.delete(listener); },
    board,
  };
}
