// The page's entry point: it reads the page's version from its <meta>, which the front server
// fills in, joins the seams to the module that makes every request, the storage module, the
// worker, the panel, the Parts step, the Layout step, the Settings step and the Preview step's
// submitting, following and failures, marks the document as started, and
// opens the wizard (opening.js): who the user is, the tab's plate, the configuration and the table
// of settings, then the stored plate's changes (settings.js) and parts (parts.js), after which it marks the
// document as opened, or as failed with a page_failed report when the opening throws (endOpening). The running wizard is this module's export, so the browser tests reach it
// by importing this module, never through a global.
import { createApi } from './api.js';
import { browserEnvironment, randomId, softwareDrawing } from './environment.js';
import { createGeometryClient } from './geometry-client.js';
import { createHoldMeter } from './hold-meter.js';
import { createLayout, printerOf } from './layout.js';
import { createLayerPreview } from './panel/layer-preview.js';
import { createLayoutStep } from './panel/layout-step.js';
import { createSendStep } from './panel/send-step.js';
import { createResult } from './result.js';
import { saveLink } from './seams/download.js';
import { startPreviewWorker } from './seams/preview-worker.js';
import { createLayoutView } from './panel/layout-view.js';
import { realFrames } from './seams/frames.js';
import { endOpening, openWizard } from './opening.js';
import { createPanel } from './panel/panel.js';
import { createPartsStep } from './panel/parts-step.js';
import { createPreviewStep } from './panel/preview-step.js';
import { createSlicing } from './slicing.js';
import { createSettingsStep } from './panel/settings-step.js';
import { createParts } from './parts.js';
import { createSettings } from './settings.js';
import { createReports, watchUncaught } from './reports.js';
import { createReloader } from './reloading.js';
import { realClock } from './seams/clock.js';
import { reloadPage } from './seams/location.js';
import { webLocks } from './seams/locks.js';
import { openIndexedDb, sessionTab } from './seams/browser-storage.js';
import { fetchTransport } from './seams/transport.js';
import { geometryWorker } from './seams/worker.js';
import { createStore } from './state.js';
import { createStorage } from './storage.js';

const meta = document.querySelector('meta[name="penguinslicer-version"]');
const version = meta ? meta.content : '';

const store = createStore();
const api = createApi({ transport: fetchTransport, clock: realClock, version, currentGroup: () => store.get().group });
const panel = createPanel(document.getElementById('wizard'), { api, clock: realClock, store });
const reports = createReports({
  api, clock: realClock, page: randomId(), environment: browserEnvironment(),
  step: () => (store.get().advanced ? 'advanced' : store.get().step),
});
// Every error the page's code did not catch and every rejected promise nobody handled.
watchUncaught(window, reports);
const reportDrawing = (summary) => { reports.drawing(summary).catch(() => {}); };
const storage = createStorage({
  openRecords: () => openIndexedDb(), locks: webLocks(), tab: sessionTab, clock: realClock, newId: () => randomId(),
  report: (what, fields) => reports.failure(what, fields),
});
const geometry = createGeometryClient(geometryWorker(), { report: (what, fields) => reports.failure(what, fields) });
const holdMeter = createHoldMeter(realClock);

const parts = createParts({ api, storage, geometry, store, panel, report: (what, fields) => reports.failure(what, fields) });
const partsStep = createPartsStep(document.querySelector('section.step[data-step="parts"]'), { parts, geometry, panel, window });
const layout = createLayout({ geometry, storage, store, parts, panel });
const layoutStep = createLayoutStep(document.querySelector('section.step[data-step="layout"]'), {
  layout, parts, geometry, frames: realFrames, store, reportDrawing,
  createView: (container, options) => createLayoutView(container, { ...options, software: softwareDrawing(), clock: realClock }),
});
const settings = createSettings({ store, storage });
const settingsStep = createSettingsStep({ root: document.getElementById('wizard'), settings, store, window });
// the changes may turn supports on or off: the Layout step's spacing follows, and nothing moves
settings.subscribe(() => layout.settingsChanged());

// The opening, then the stored plate's changes and parts taken up: advanced mode again when it
// was open, the parts' rows, and an upload again for each part whose upload had not been
// answered; then the stored layout, which joins the parts on the Layout step.
const opened = openWizard({ api, store, panel, storage }).then(async (outcome) => {
  if (outcome.opened) {
    await settings.resume();
    await parts.resume();
    layout.resume();
  }
  return outcome;
});
// The Preview step: submitting and following a plate, and every slice failure; the plate is
// read as it stands once the page has opened and the Layout step's work is done.
// Coming back: once opened on a stored plate, the page asks about its slice job and opens where the
// user will want to be, saying nothing after its own reload for a new version.
const slicing = createSlicing({
  api, clock: realClock, storage, store, settings, layout, panel, newId: () => randomId(),
  report: (what, fields) => reports.failure(what, fields),
  ready: () => opened.then(() => layout.idle()),
  back: () => opened.then((outcome) => (outcome.opened ? { quiet: Boolean(outcome.selfReload) } : null)),
});
// The result around the layer preview, and the Send step with Download as its one button.
const result = createResult({ api, slicing, store, panel, geometry, save: saveLink });
const previewStep = createPreviewStep(document.querySelector('section.step[data-step="preview"]'), {
  slicing, store, clock: realClock, result, frames: realFrames, reportDrawing,
  createView: (container, options) => createLayerPreview(container, {
    ...options, frames: realFrames, clock: realClock, startWorker: startPreviewWorker, software: softwareDrawing(),
    printer: printerOf(store.get()) ?? undefined,
    report: (what, fields) => reports.failure(what, fields),
  }),
});
const sendStep = createSendStep(document.querySelector('section.step[data-step="send"]'), { slicing, result, store, root: document.getElementById('wizard') });
// a change to the plate makes a sliced plate unsliced, until it is the sliced plate again
for (const source of [layout, settings, parts, store]) source.subscribe(() => slicing.plateChanged());

// Reloading for a new version: at a move between steps, or after RELOAD_IDLE_S without input, once
// no request is pending; the reload is noted as the page's own first.
const reloader = createReloader({
  api, clock: realClock, store, version,
  onInput: (listener) => {
    for (const type of ['pointermove', 'pointerdown', 'keydown', 'wheel', 'scroll']) {
      window.addEventListener(type, listener, { capture: true, passive: true });
    }
  },
  beforeReload: () => storage.markSelfReload(),
  reload: () => reloadPage(),
});

const opening = endOpening(opened, {
  report: (what, fields) => reports.failure(what, fields),
  mark: (how) => { document.documentElement.dataset.opened = how; },
});

export const wizard = { version, store, api, panel, storage, reports, geometry, holdMeter, parts, partsStep, layout, layoutStep, settings, settingsStep, slicing, result, previewStep, sendStep, opening, reloader };

document.documentElement.dataset.version = version;
document.documentElement.dataset.started = 'true';
