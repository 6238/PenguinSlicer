// The page's reports about itself (wizard/README-details.md, "What the wizard reports about
// itself"; contracts/wizard-front-server.md, "The page's reports about itself"): one module that
// holds the page to REPORTS_PER_MIN, sends each report once, and drops a report that cannot be
// sent or is refused (front.too_many_reports), never retrying it, so a report can never loop.
// Built so far: the failure reports, POST /api/reports/failure. The drawing summaries,
// POST /api/reports/drawing, come with item 18 of "By phase".
export const REPORTS_PER_MIN = 4;

// The failures the contract lists.
const WHAT = new Set(['part_not_drawable', 'storage_refused', 'storage_cleared', 'drawing_context_lost', 'layout_failed', 'page_failed']);
const BROWSER_CHARS = 40;
const DETAIL_CHARS = 1000;

// createReports({api, clock, page, step, environment}):
//   page         the page's random id, made when it loads
//   step()       the step the user is on, in the contract's words (parts, settings, advanced,
//                layout, preview, send or none)
//   environment  {browser, browser_version, software_3d()} as the browser gives them
//   failure(what, {part_sha256, detail}) resolves to true when the report was taken, false
//     when it was dropped (over the limit, refused or not sent). A report never holds a part's
//     name, bytes or geometry, or anything from the storage: its caller names a part by its hash.
export function createReports({ api, clock, page, step, environment }) {
  const sentAt = [];

  return {
    async failure(what, { part_sha256: sha256, detail } = {}) {
      if (!WHAT.has(what)) throw new Error(`${JSON.stringify(what)} is not a failure the contract lists`);
      const now = clock.now();
      while (sentAt.length && now - sentAt[0] >= 60_000) sentAt.shift();
      if (sentAt.length >= REPORTS_PER_MIN) return false;
      sentAt.push(now);
      const body = {
        page, what, step: step(),
        browser: String(environment.browser).slice(0, BROWSER_CHARS),
        browser_version: String(environment.browser_version).slice(0, BROWSER_CHARS),
        software_3d: Boolean(environment.software_3d()),
      };
      if (sha256) body.part_sha256 = sha256;
      if (detail !== undefined) body.detail = String(detail).slice(0, DETAIL_CHARS);
      const answer = await api.post('/api/reports/failure', { json: body, once: true });
      return answer.ok === true;
    },
  };
}
