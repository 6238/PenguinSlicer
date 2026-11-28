// The page's entry point: it reads the page's version from its <meta>, which the front server
// fills in, joins the seams to the module that makes every request, the storage module, the
// worker and the panel, marks the document as started, and opens the wizard (opening.js): who the
// user is, the tab's plate, the configuration and the table of settings, after which it marks the
// document as opened, or as failed with a page_failed report when the opening throws (endOpening). The running wizard is this module's export, so the browser tests reach it
// by importing this module, never through a global.
import { createApi } from './api.js';
import { browserEnvironment, randomId } from './environment.js';
import { createGeometryClient } from './geometry-client.js';
import { createHoldMeter } from './hold-meter.js';
import { endOpening, openWizard } from './opening.js';
import { createPanel } from './panel/panel.js';
import { createReports } from './reports.js';
import { realClock } from './seams/clock.js';
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
const reports = createReports({ api, clock: realClock, page: randomId(), step: () => store.get().step, environment: browserEnvironment() });
const storage = createStorage({
  openRecords: () => openIndexedDb(), locks: webLocks(), tab: sessionTab, clock: realClock, newId: () => randomId(),
  report: (what, fields) => reports.failure(what, fields),
});
const geometry = createGeometryClient(geometryWorker(), { report: (what, fields) => reports.failure(what, fields) });
const holdMeter = createHoldMeter(realClock);

const opening = endOpening(openWizard({ api, store, panel, storage }), {
  report: (what, fields) => reports.failure(what, fields),
  mark: (how) => { document.documentElement.dataset.opened = how; },
});

export const wizard = { version, store, api, panel, storage, reports, geometry, holdMeter, opening };

document.documentElement.dataset.version = version;
document.documentElement.dataset.started = 'true';
