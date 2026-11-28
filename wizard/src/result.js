// A sliced plate's result and the Send step in phase 2 (wizard/README-details.md, "The result",
// "The layer preview", "The Send step"), apart from their drawing (panel/preview-step.js,
// panel/send-step.js): the figures of the result and of the Send step's card, worked out from the
// sliced file's details that slicing.js holds; the sliced file fetched for the layer preview, with
// the ghost of the plate's instances; and Download, which asks the details first, so that a
// sliced file that has expired is told to the page rather than to the browser's download, and then
// saves the file by a plain link naming the current group, so that the page never holds it.
// A sliced file refused as expired, here or anywhere, becomes slicing.js's expired message.
import { EXPIRED_CODE, STILL_HERE_NOTICE, clockText, isDetails } from './slicing.js';
import * as R from './result-sentences.js';
import { badAnswer } from './sentences.js';

export { STILL_HERE_NOTICE };

const MB = 1_048_576;           // the contracts' megabyte: the 50 MB cap is 52,428,800 bytes
const KB = 1024;
const isNumber = (n) => typeof n === 'number' && Number.isFinite(n);

// A print time as the mockup writes it: "3 h 12 min", "36 min"; any time above none is at least
// a minute.
export function hoursMinutes(seconds) {
  const minutes = seconds > 0 ? Math.max(1, Math.round(seconds / 60)) : 0;
  const h = Math.floor(minutes / 60);
  return h ? `${h} h ${minutes % 60} min` : `${minutes} min`;
}

// A file's size: megabytes to one decimal from a megabyte up, whole kilobytes from a kilobyte up,
// else bytes.
export function sizeText(bytes) {
  if (bytes >= MB) return `${(bytes / MB).toFixed(1)} MB`;
  if (bytes >= KB) return `${Math.round(bytes / KB)} KB`;
  return `${bytes} byte${bytes === 1 ? '' : 's'}`;
}

// createResult({api, slicing, store, panel, geometry, save}):
//   save(href, name)  the download seam (seams/download.js): the browser saves `href` as `name`
export function createResult({ api, slicing, store, panel, geometry, save }) {
  const done = () => {
    const m = slicing.model();
    return m.kind === 'done' ? m : null;
  };
  const filament = () => store.get().plate.filament ?? '';
  const path = (slice, what) => `/api/slices/${encodeURIComponent(slice)}/${what}`;

  // The instances of each part, in the order of the plate configuration's parts.
  function byPart(body) {
    const counts = new Map(Object.keys(body.parts).map((ref) => [ref, 0]));
    for (const i of body.instances) counts.set(i.ref, (counts.get(i.ref) ?? 0) + 1);
    return [...counts].filter(([, n]) => n > 0).map(([ref, n]) => R.OF_PART(n, body.parts[ref].name));
  }

  return {
    // The result on the Preview step: {stats: [{label, value}], line, warnings}, or null while
    // the plate is not sliced or its details have not arrived. A figure given as null is left out.
    preview() {
      const m = done();
      if (!m || !m.details) return null;
      const s = m.details.summary;
      const stats = [];
      if (isNumber(s.print_time_s)) stats.push({ label: R.PRINT_TIME, value: hoursMinutes(s.print_time_s) });
      if (isNumber(s.filament_g)) stats.push({ label: R.FILAMENT, value: R.GRAMS_OF(s.filament_g, filament()) });
      const line = [];
      if (Number.isInteger(s.instances)) line.push(R.INSTANCES(s.instances));
      if (Number.isInteger(s.layer_count)) line.push(R.LAYERS(s.layer_count));
      if (isNumber(m.report.elapsed_s)) line.push(R.SLICED_IN(clockText(m.report.elapsed_s)));
      const warnings = [
        ...(Array.isArray(s.warnings) ? s.warnings.filter((w) => typeof w === 'string') : []),
        ...(Array.isArray(s.part_warnings) ? s.part_warnings.filter((w) => w && typeof w.message === 'string').map((w) => w.message) : []),
      ];
      return { stats, line: line.join(R.QUIET_SEPARATOR), warnings };
    },

    // The Send step's card: {count, parts, printTime, grams, filament}, or null with no sliced plate.
    send() {
      const m = done();
      if (!m || !m.details || !m.body) return null;
      const s = m.details.summary;
      return {
        count: R.ON_ONE_PLATE(m.body.instances.length),
        parts: byPart(m.body),
        printTime: isNumber(s.print_time_s) ? hoursMinutes(s.print_time_s) : null,
        grams: isNumber(s.filament_g) ? R.GRAMS(s.filament_g) : null,
        filament: R.OF_FILAMENT(filament()),
      };
    },

    // The sliced plate's id, or null.
    slice: () => (done() ? done().slice : null),

    // The ghost of the plate for the layer preview: the sliced plate configuration's instances and
    // each part's corners under the key its instances name; null when a part's corners are not at
    // hand, so that the preview draws without a ghost rather than failing.
    ghost() {
      const m = done();
      if (!m || !m.body) return null;
      const meshes = {};
      for (const [ref, part] of Object.entries(m.body.parts)) {
        const mesh = geometry.mesh(`${part.sha256}.${part.units}`);
        if (!mesh || !mesh.positions) return null;
        meshes[ref] = mesh.positions;
      }
      return { instances: m.body.instances, meshes };
    },

    // The sliced file for the layer preview, fetched with the page's headers and never stored:
    // {ok: true, bytes, slice}, {ok: false, expired: true} once the expired message has taken the
    // result's place, {ok: false, report} for any other refusal, or {ok: false, stopped: true}
    // when the plate is no longer this sliced plate.
    async file() {
      const m = done();
      if (!m) return { ok: false, stopped: true };
      const answer = await api.get(path(m.slice, 'file'), { expect: 'bytes' });
      if (slicing.model().kind !== 'done' || slicing.model().slice !== m.slice) return { ok: false, stopped: true };
      if (answer.ok) return { ok: true, bytes: answer.body, slice: m.slice };
      if (answer.report.code === EXPIRED_CODE) {
        slicing.expire(answer.report, m.slice);
        return { ok: false, expired: true };
      }
      return { ok: false, report: answer.report };
    },

    // Download: the details asked first (their expiry counted afresh), then the file saved by a
    // plain link, and a notification of the plate and the file's true size. {ok: true}, {ok:
    // false, expired: true} (the expired message in place of Send), {ok: false, report} (shown by
    // the Send step), or {ok: false} with no sliced plate.
    async download() {
      const m = done();
      if (!m) return { ok: false };
      const summary = path(m.slice, 'summary');
      const answer = await api.get(summary);
      // details that arrive after the plate expired or was sliced again are another plate's: nothing
      // is saved and nothing is taken
      if (slicing.model().kind !== 'done' || slicing.model().slice !== m.slice) return { ok: false };
      if (!answer.ok) {
        if (answer.report.code === EXPIRED_CODE) {
          slicing.expire(answer.report, m.slice);
          return { ok: false, expired: true };
        }
        return { ok: false, report: answer.report };
      }
      const details = answer.body && answer.body.sliced_file;
      if (!isDetails(details)) return { ok: false, report: badAnswer(summary, answer.status, JSON.stringify(answer.body)) };
      slicing.takeDetails(details);
      save(api.link(path(m.slice, 'file')), details.file);
      // the plate in words by what it holds, as the Send step's card counts it
      const instances = m.body.instances.length;
      const what = isNumber(details.size_bytes) && details.size_bytes >= 0 ? R.DOWNLOADED(instances, sizeText(details.size_bytes)) : R.DOWNLOADED_NO_SIZE(instances);
      panel.notify({ kind: 'info', what, key: 'downloaded' });
      return { ok: true };
    },
  };
}
