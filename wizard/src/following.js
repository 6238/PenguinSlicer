// Following a job's progress (wizard/README-details.md, "Progress streams"): one interface,
// followJob, behind which the page either reads the job's progress stream or asks for its latest
// progress report every POLL_S, and delivers the reports to the screens the same way. The stream is
// the means; asking is used when the front server refuses a fifth stream (front.too_many_streams,
// whose showing is open: until it is settled the page asks and shows nothing of the refusal), and
// would become the means should the hosts hold streams back (phase 3).
//
// A stream is opened by the module that makes every request, so its opening carries the headers of
// any request and is retried by the rules of retrying. On it:
//   - the first event is `version`, told as any answer's version is; then the latest progress
//     report at once, then each report as it happens, each `progress` event's id its sequence;
//   - a report whose sequence is not above the last one delivered is ignored;
//   - a comment line arrives at least every fifteen seconds while there is nothing to report;
//   - after a final report (done, failed, cancelled) the stream is ended;
//   - a stream that closes, or is cut off, before a final report is reopened silently, at once,
//     and then with the waits of retrying (a stream that closes having carried nothing is waited
//     for as a failed attempt is, so that a front server closing every stream at once is not
//     asked again and again with no pause);
//   - failing to reopen for STREAM_REOPEN_FAIL_S counts as a failed request (retrying's own 20 s:
//     the panel line), and so does a stream open and carrying nothing, not even a comment, for
//     STREAM_SILENT_S: it is closed and reopened, counted as failing for RETRY_QUIET_S already, so
//     that the panel line shows from that moment.
import { POLL_S, RETRY_QUIET_S, STREAM_SILENT_S } from './page-constants.js';
import { retryWaitS } from './retry.js';
import { badAnswer } from './sentences.js';

const FINAL = new Set(['done', 'failed', 'cancelled']);

// The events of a server-sent stream, from its text in pieces split anywhere: each event is
// {event, data, id}, told once its blank line arrives. Comment lines (":") carry nothing.
export function createEventParser(onEvent) {
  let buffer = '';
  let event = null;
  let data = [];
  let id = null;
  function line(text) {
    if (text === '') {
      if (data.length) onEvent({ event: event ?? 'message', data: data.join('\n'), id });
      event = null; data = []; id = null;
      return;
    }
    if (text.startsWith(':')) return;
    const colon = text.indexOf(':');
    const field = colon < 0 ? text : text.slice(0, colon);
    let value = colon < 0 ? '' : text.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
    else if (field === 'id') id = value;
  }
  return {
    push(text) {
      buffer += text;
      for (;;) {
        const at = buffer.search(/\r\n|\r|\n/);
        if (at < 0) return;
        // a lone \r at the end of a piece may be the first half of \r\n: wait for the next piece
        if (buffer[at] === '\r' && at === buffer.length - 1) return;
        const width = buffer.startsWith('\r\n', at) ? 2 : 1;
        line(buffer.slice(0, at));
        buffer = buffer.slice(at + width);
      }
    },
  };
}

const isReport = (r) => r !== null && typeof r === 'object' && typeof r.state === 'string' && Number.isInteger(r.sequence);

// followJob({api, clock, path, mode, onReport, onRefused, random}):
//   path       the job's path ('/api/slices/<slice>'); its stream is `${path}/events`
//   mode       'stream' (the default) or 'ask'
//   onReport   told each progress report, in order, each once
//   onRefused  told the error report when the job cannot be followed (front.slice_unknown, above
//              all); following then ends
// Resolves nothing; returns {stop(), mode()}: stop ends the stream or the asking at once.
export function followJob({ api, clock, path, mode = 'stream', onReport, onRefused, random = Math.random }) {
  let stopped = false;
  let current = mode;
  let last = -Infinity;
  let controller = null;
  let pause = null;

  // A report is delivered once, in order; true when it is final.
  function deliver(report) {
    if (!isReport(report) || report.sequence <= last) return false;
    last = report.sequence;
    onReport(report);
    return FINAL.has(report.state);
  }

  // Resolves after `ms` on the clock, or at once on stop().
  function wait(ms) {
    return new Promise((resolve) => {
      const timer = clock.after(ms, () => { pause = null; resolve(); });
      pause = () => { clock.cancel(timer); pause = null; resolve(); };
    });
  }

  // Reads one opened stream to its end: 'final', 'closed' (closed or cut off before a final
  // report), 'silent' (STREAM_SILENT_S with nothing) or 'stopped'; `said` is whether any event came.
  async function read(stream, own) {
    let final = false;
    let silent = false;
    let said = false;
    let timer = null;
    const arm = () => {
      if (timer !== null) clock.cancel(timer);
      timer = clock.after(STREAM_SILENT_S * 1000, () => { timer = null; silent = true; own.abort(); });
    };
    const parser = createEventParser(({ event, data }) => {
      if (final) return;
      said = true;
      let body;
      try { body = JSON.parse(data); } catch { return; }
      if (event === 'version' && body && typeof body.version === 'string') api.heard(body.version);
      else if (event === 'progress' && deliver(body)) { final = true; own.abort(); }
    });
    arm();
    try {
      await stream.chunks((text) => { if (!final && !stopped) { arm(); parser.push(text); } });
    } catch {
      // cut off, aborted at the final report, by silence or by stop(): told below
    } finally {
      if (timer !== null) clock.cancel(timer);
    }
    if (stopped) return { outcome: 'stopped', said };
    if (final) return { outcome: 'final', said };
    return { outcome: silent ? 'silent' : 'closed', said };
  }

  async function streamLoop() {
    let failingSince = null;
    let emptyCloses = 0;
    for (;;) {
      if (stopped) return;
      controller = new AbortController();
      const own = controller;
      const answer = await api.get(`${path}/events`, { expect: 'stream', signal: own.signal, failingSince });
      failingSince = null;
      if (stopped || answer.stopped) return;
      if (!answer.ok) {
        if (answer.report.code === 'front.too_many_streams') { current = 'ask'; await askLoop(); return; }
        onRefused(answer.report);
        return;
      }
      const { outcome, said } = await read(answer.stream, own);
      if (outcome === 'final' || outcome === 'stopped') return;
      if (outcome === 'silent') {
        failingSince = clock.now() - RETRY_QUIET_S * 1000;
        continue;
      }
      // closed before a final report: reopened at once, unless it carried nothing
      if (said) { emptyCloses = 0; continue; }
      await wait(retryWaitS(emptyCloses, random) * 1000);
      emptyCloses += 1;
    }
  }

  async function askLoop() {
    for (;;) {
      if (stopped) return;
      controller = new AbortController();
      const answer = await api.get(path, { signal: controller.signal });
      if (stopped || answer.stopped) return;
      if (!answer.ok) { onRefused(answer.report); return; }
      const report = answer.body && answer.body.progress;
      if (!isReport(report)) { onRefused(badAnswer(path, answer.status, JSON.stringify(answer.body))); return; }
      if (deliver(report)) return;
      await wait(POLL_S * 1000);
    }
  }

  (current === 'ask' ? askLoop() : streamLoop()).catch((err) => { if (!stopped) throw err; });

  return {
    stop() {
      if (stopped) return;
      stopped = true;
      if (controller) controller.abort();
      if (pause) pause();
    },
    mode: () => current,
  };
}
