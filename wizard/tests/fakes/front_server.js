// The fake front server: the transport seam's shape (src/seams/transport.js), answering in the
// contract's shapes (contracts/wizard-front-server.md), with its default answers taken whole
// from contracts/examples/. A test sets, for each request in turn, whether it is answered,
// held, dropped, or answered without the front server's version, so that it puts the events in
// an exact order. Every request is recorded with its headers.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const EXAMPLES = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'contracts', 'examples');
export const VERSION = '20261127T221405Z-0000000';

export function example(name) {
  return JSON.parse(readFileSync(join(EXAMPLES, name), 'utf8'));
}

// The front server's own error reports, with each one's status and `retryable` as the
// contract's table "The front server's error reports" gives them.
export const FRONT_CODES = {
  'front.not_signed_in': [401, false],
  'front.sign_in_refused': [401, false],
  'front.sign_in_failed': [401, false],
  'front.onshape_unreachable': [503, true],
  'front.group_not_allowed': [403, false],
  'front.not_from_wizard': [403, false],
  'front.configuration_changed': [409, false],
  'front.configuration_invalid': [422, false],
  'front.slice_unknown': [404, false],
  'front.sliced_file_not_ready': [409, false],
  'front.sliced_file_expired': [410, false],
  'front.delivery_unknown': [404, false],
  'front.slice_unreachable': [503, true],
  'front.state_bucket_unreachable': [503, true],
  'front.too_many_requests': [429, true],
  'front.too_many_streams': [429, true],
  'front.too_many_reports': [429, false],
  'front.bad_request': [400, false],
  'front.no_such_request': [404, false],
  'front.unexpected': [500, true],
};

// An error report in the contract's shape (contracts/error-report.md), with sentences the test
// makes up, so that a test can check exactly those sentences reach the user.
export function errorReport(code, fields = {}) {
  return {
    code,
    message: `The fake front server's sentence of what happened for ${code}.`,
    remedy: `The fake front server's sentence of what to do for ${code}.`,
    retryable: code in FRONT_CODES ? FRONT_CODES[code][1] : false,
    detail: `fake detail for ${code}, never shown`,
    ...fields,
  };
}

// What the contract requires of every error report: the fields, their types, nothing else.
export function errorReportProblems(report) {
  const problems = [];
  const required = { code: 'string', message: 'string', remedy: 'string', retryable: 'boolean', detail: 'string' };
  const optional = { where: 'object', action: 'string', orca_sentence: 'string' };
  for (const [field, type] of Object.entries(required)) {
    if (typeof report[field] !== type) problems.push(`${field} is not a ${type}`);
  }
  for (const [field, type] of Object.entries(optional)) {
    if (field in report && typeof report[field] !== type) problems.push(`${field} is not a ${type}`);
  }
  for (const field of Object.keys(report)) {
    if (!(field in required) && !(field in optional)) problems.push(`${field} is not a field of an error report`);
  }
  if (typeof report.code === 'string' && !/^[a-z]+\.[a-z_]+$/.test(report.code)) problems.push('code is not component.what');
  return problems;
}

function jsonAnswer(status, body, headers = {}) {
  return { kind: 'answer', status, body: body === null ? '' : JSON.stringify(body), headers: { 'Content-Type': 'application/json', ...headers } };
}

// The steps a test gives a request.
export const steps = {
  answer: (status, body, headers) => jsonAnswer(status, body, headers),
  report: (report, { status, retryAfter } = {}) => jsonAnswer(
    status ?? (FRONT_CODES[report.code] ? FRONT_CODES[report.code][0] : 422), report,
    retryAfter === undefined ? {} : { 'Retry-After': String(retryAfter) }),
  // The connection fails: refused, reset, or the network gone.
  drop: () => ({ kind: 'drop' }),
  // No answer until the test releases it (with another step) or the page aborts it.
  hold: () => ({ kind: 'hold' }),
  // An answer that is not the front server's: a proxy's error page, without the version.
  noVersion: (status = 502, text = '<html>Bad gateway</html>') => ({ kind: 'answer', status, body: text, headers: { 'Content-Type': 'text/html' }, noVersion: true }),
  // An answer of the front server whose body is not JSON.
  notJson: (status = 200) => ({ kind: 'answer', status, body: 'not json', headers: { 'Content-Type': 'text/plain' } }),
  // The front server's headers arrive and its body stalls: nothing more until the page aborts.
  stallBody: (status = 200) => ({ kind: 'answer', status, body: '', headers: { 'Content-Type': 'application/json' }, bodyFails: 'stall' }),
  // The front server's headers arrive and its body is cut off partway (a restart): reading it
  // fails as the browser's fetch fails, with a TypeError.
  cutBody: (status = 200) => ({ kind: 'answer', status, body: '{"user": {"id"', headers: { 'Content-Type': 'application/json' }, bodyFails: 'cut' }),
  // The front server's headers arrive and its body follows in parts, each when the test calls
  // `step.trickle.next()`, as a large sliced file arrives over a slow connection; between two
  // parts the body stalls.
  trickle: (status, chunks, contentType = 'application/octet-stream') => {
    const feed = {
      given: 0,
      reading: null,
      next() {
        if (!feed.reading) throw new Error('the page is not reading the body');
        const chunk = chunks[feed.given];
        feed.given += 1;
        if (feed.reading.onProgress) feed.reading.onProgress(new TextEncoder().encode(chunk).length);
        if (feed.given === chunks.length) feed.reading.resolve();
      },
    };
    return { kind: 'answer', status, body: chunks.join(''), headers: { 'Content-Type': contentType }, trickle: feed };
  },
};

// The default answer to each request of the contract that phase 2 makes, from its examples.
function defaultStep(method, path) {
  const route = path.split('?')[0];
  if (method === 'GET' && route === '/api/me') return steps.answer(200, example('wizard-front/me.json'));
  if (method === 'GET' && route === '/api/configuration') {
    return steps.answer(200, { configuration: example('configuration-default.json'), source: 'default', name: 'PenguinSlicer default', revision: null });
  }
  if (method === 'PUT' && route === '/api/configuration') return steps.answer(200, example('wizard-front/configuration-written.json'));
  if (method === 'GET' && route === '/api/settings-table') return steps.answer(200, example('settings-table.json'));
  if (method === 'POST' && route === '/api/parts') return steps.answer(201, example('wizard-front/part-record.json'));
  if (method === 'POST' && route === '/api/slices') return steps.answer(202, example('wizard-front/slice-accepted.json'));
  if (method === 'GET' && /^\/api\/slices\/[\w-]+\/summary$/.test(route)) return steps.answer(200, example('wizard-front/slice-summary.json'));
  if (method === 'GET' && /^\/api\/slices\/[\w-]+$/.test(route)) return steps.answer(200, example('wizard-front/slice-done.json'));
  if (method === 'POST' && /^\/api\/reports\/(failure|drawing)$/.test(route)) return { kind: 'answer', status: 204, body: '', headers: {} };
  return steps.report(errorReport('front.no_such_request'));
}

export class FakeFrontServer {
  constructor({ version = VERSION } = {}) {
    this.version = version;
    this.requests = [];
    this.scripts = [];            // [{method, path, steps: []}]
    this.waiters = [];
    this.transport = { send: (request) => this.receive(request) };
  }

  // The next requests matching `method` and `path` (a string, or a regular expression) meet
  // these steps, one each, in order; after them, the default answer.
  script(method, path, ...list) {
    this.scripts.push({ method, path, steps: list });
    return this;
  }

  // Resolves with the request once `count` requests in all have arrived: an event, not a wait.
  arrived(count) {
    if (this.requests.length >= count) return Promise.resolve(this.requests[count - 1]);
    return new Promise((resolve) => this.waiters.push({ count, resolve }));
  }

  // The requests that matched `method` and `path`.
  made(method, path) {
    return this.requests.filter((r) => r.method === method && matches(path, r.path));
  }

  stepFor(method, path) {
    for (const script of this.scripts) {
      if (script.method === method && matches(script.path, path) && script.steps.length) return script.steps.shift();
    }
    return defaultStep(method, path);
  }

  receive({ method, path, headers = {}, body, signal }) {
    const lower = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
    const record = { method, path, headers: lower, body, at: this.requests.length + 1, held: null };
    this.requests.push(record);
    this.waiters = this.waiters.filter((w) => (this.requests.length >= w.count ? (w.resolve(this.requests[w.count - 1]), false) : true));
    return this.play(this.stepFor(method, path), record, signal);
  }

  play(step, record, signal) {
    if (signal && signal.aborted) return Promise.reject(abortError());
    if (step.kind === 'drop') return Promise.reject(new TypeError('Failed to fetch'));
    if (step.kind === 'hold') {
      return new Promise((resolve, reject) => {
        record.held = { release: (next) => resolve(this.play(next ?? defaultStep(record.method, record.path), record, signal)) };
        if (signal) signal.addEventListener('abort', () => reject(abortError()), { once: true });
      });
    }
    const headers = { ...step.headers };
    if (!step.noVersion) headers['X-PenguinSlicer-Version'] = this.version;
    headers['Cache-Control'] = 'no-store';
    const lower = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
    const read = (parse, onProgress) => {
      if (step.bodyFails === 'cut') return Promise.reject(new TypeError('network error'));
      if (step.trickle) {
        return new Promise((resolve, reject) => {
          if (signal && signal.aborted) { reject(abortError()); return; }
          step.trickle.reading = { onProgress, resolve: () => resolve(parse(step.body)) };
          if (signal) {
            signal.addEventListener('abort', () => { step.trickle.reading = null; reject(abortError()); }, { once: true });
          }
        });
      }
      if (step.bodyFails === 'stall') {
        return new Promise((resolve, reject) => {
          if (!signal) return;
          if (signal.aborted) { reject(abortError()); return; }
          signal.addEventListener('abort', () => reject(abortError()), { once: true });
        });
      }
      return Promise.resolve().then(() => parse(step.body));
    };
    return Promise.resolve({
      status: step.status,
      header: (name) => lower[name.toLowerCase()] ?? null,
      json: () => read((body) => JSON.parse(body)),
      text: (onProgress) => read((body) => body, onProgress),
      bytes: (onProgress) => read((body) => new TextEncoder().encode(body).buffer, onProgress),
    });
  }
}

function matches(pattern, path) {
  return typeof pattern === 'string' ? pattern === path.split('?')[0] : pattern.test(path);
}

function abortError() {
  const error = new Error('The operation was aborted.');
  error.name = 'AbortError';
  return error;
}
