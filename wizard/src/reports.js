// The page's reports about itself (wizard/README-details.md, "What the wizard reports about
// itself"; contracts/wizard-front-server.md, "The page's reports about itself"): one module that
// holds the page to REPORTS_PER_MIN, sends each report once, and drops a report that cannot be
// sent or is refused (front.too_many_reports), never retrying it, so a report can never loop.
// Two kinds: the failures in the browser, POST /api/reports/failure, and the drawing summaries,
// POST /api/reports/drawing, one for each use of the Layout view and of the Preview step; and the
// handler that reports every uncaught error and rejected promise as page_failed (watchUncaught).
export const REPORTS_PER_MIN = 4;

// The failures the contract lists.
const WHAT = new Set(['part_not_drawable', 'storage_refused', 'storage_cleared', 'drawing_context_lost', 'layout_failed', 'page_failed']);
const BROWSER_CHARS = 40;
const CARD_CHARS = 120;
const DETAIL_CHARS = 1000;

const text = (v, n) => String(v).slice(0, n);
const finite = (v) => typeof v === 'number' && Number.isFinite(v);
const tenth = (v) => Math.round(v * 10) / 10;

// createReports({api, clock, page, step, environment, signedIn}):
//   page         the page's random id, made when it loads
//   step()       the step the user is on, in the contract's words (parts, settings, advanced,
//                layout, preview, send or none)
//   environment  what the browser gives (environment.js, browserEnvironment): browser,
//                browser_version, software_3d(); for the drawing summaries also os,
//                graphics_card(), processors, memory_gb, pixel_ratio(), panel_width_px(), in_onshape
//   signedIn()   whether the page is signed in; a page that is not drops its reports
//   failure(what, {part_sha256, detail}) resolves to true when the report was taken, false
//     when it was dropped (over the limit, refused or not sent). A report never holds a part's
//     name, bytes or geometry, or anything from the storage: its caller names a part by its hash.
//   drawing(summary) sends one drawing summary: `summary` is the view's own figures ({view,
//     fps_typical, fps_worst, longest_hold_ms, instances}, and for the Preview step first_layer_ms,
//     sliced_file_bytes, sliced_file_lines), to which the machine's are added; only the contract's
//     fields are sent, so no part name ever is. A use of the view without a figure the contract
//     requires (no frame drawn while moving, no first layer drawn) is not sent: false.
export function createReports({ api, clock, page, step, environment, signedIn = () => true }) {
  const sentAt = [];

  // Whether the limit lets one more report go now; it is then counted.
  function take() {
    const now = clock.now();
    while (sentAt.length && now - sentAt[0] >= 60_000) sentAt.shift();
    if (sentAt.length >= REPORTS_PER_MIN) return false;
    sentAt.push(now);
    return true;
  }

  async function send(path, body) {
    const answer = await api.post(path, { json: body, once: true });
    return answer.ok === true;
  }

  return {
    async failure(what, { part_sha256: sha256, detail } = {}) {
      if (!WHAT.has(what)) throw new Error(`${JSON.stringify(what)} is not a failure the contract lists`);
      if (!signedIn() || !take()) return false;
      const body = {
        page, what, step: step(),
        browser: text(environment.browser, BROWSER_CHARS),
        browser_version: text(environment.browser_version, BROWSER_CHARS),
        software_3d: Boolean(environment.software_3d()),
      };
      if (sha256) body.part_sha256 = sha256;
      if (detail !== undefined) body.detail = text(detail, DETAIL_CHARS);
      return send('/api/reports/failure', body);
    },

    async drawing(summary) {
      const preview = summary.view === 'preview';
      if (summary.view !== 'layout' && !preview) throw new Error(`${JSON.stringify(summary.view)} is not a view the contract lists`);
      const figures = ['fps_typical', 'fps_worst', 'longest_hold_ms', 'instances', ...(preview ? ['first_layer_ms', 'sliced_file_bytes', 'sliced_file_lines'] : [])];
      if (!figures.every((name) => finite(summary[name])) || !signedIn()) return false;
      if (!take()) return false;
      const body = {
        page, view: summary.view, fps_typical: tenth(summary.fps_typical), fps_worst: tenth(summary.fps_worst),
      };
      if (preview) body.first_layer_ms = Math.round(summary.first_layer_ms);
      body.longest_hold_ms = Math.round(summary.longest_hold_ms);
      body.instances = summary.instances;
      if (preview) { body.sliced_file_bytes = summary.sliced_file_bytes; body.sliced_file_lines = summary.sliced_file_lines; }
      body.browser = text(environment.browser, BROWSER_CHARS);
      body.browser_version = text(environment.browser_version, BROWSER_CHARS);
      body.os = text(environment.os, BROWSER_CHARS);
      body.drawing = environment.software_3d() ? 'software' : 'graphics_card';
      const card = environment.graphics_card();
      if (typeof card === 'string' && card) body.graphics_card = text(card, CARD_CHARS);
      if (finite(environment.processors)) body.processors = environment.processors;
      if (finite(environment.memory_gb)) body.memory_gb = environment.memory_gb;
      body.panel_width_px = Math.round(environment.panel_width_px());
      body.pixel_ratio = environment.pixel_ratio();
      body.in_onshape = Boolean(environment.in_onshape);
      return send('/api/reports/drawing', body);
    },
  };
}

// Where an error arose, as the page's own files name it: the path of its file, without the
// address of the front server, which every line of the log already knows.
function where(filename, line, column) {
  if (!filename) return '';
  let path = String(filename);
  try { path = new URL(path).pathname; } catch { /* not an address: kept as it is */ }
  return ` at ${path}${line ? `:${line}` : ''}${column ? `:${column}` : ''}`;
}

function described(value) {
  if (value && typeof value === 'object' && typeof value.message === 'string') {
    const name = typeof value.name === 'string' && value.name ? value.name : 'Error';
    const stack = typeof value.stack === 'string' ? `\n${value.stack.split('\n').slice(1, 4).join('\n')}` : '';
    return `${name}: ${value.message}${stack}`;
  }
  return String(value);
}

// watchUncaught(target, reports): every error the page's code did not catch and every rejected
// promise nobody handled, on `target` (the window), reported as page_failed: the error's message
// and where in the page's code it arose. The limit of the reports module holds a storm of them to
// a few a minute, and a report that fails is never itself reported.
export function watchUncaught(target, reports) {
  const tell = (detail) => { reports.failure('page_failed', { detail }).catch(() => {}); };
  target.addEventListener('error', (event) => {
    const error = event && event.error;
    const head = error && typeof error.message === 'string'
      ? `${error.name || 'Error'}: ${error.message}` : String(event && event.message);
    tell(`uncaught: ${head}${where(event && event.filename, event && event.lineno, event && event.colno)}`);
  });
  target.addEventListener('unhandledrejection', (event) => {
    tell(`unhandled rejection: ${described(event && event.reason)}`);
  });
}
