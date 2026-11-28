// The page's entry point: it reads the page's version from its <meta>, which the front server
// fills in, joins the seams to the module that makes every request and to the panel, and marks
// the document as started. The running wizard is this module's export, so the browser tests
// reach it by importing this module, never through a global.
import { createApi } from './api.js';
import { createPanel } from './panel/panel.js';
import { realClock } from './seams/clock.js';
import { fetchTransport } from './seams/transport.js';
import { createStore } from './state.js';

const meta = document.querySelector('meta[name="penguinslicer-version"]');
const version = meta ? meta.content : '';

const store = createStore();
const api = createApi({ transport: fetchTransport, clock: realClock, version, currentGroup: () => store.get().group });
const panel = createPanel(document.getElementById('wizard'), { api, clock: realClock, store });

export const wizard = { version, store, api, panel };

document.documentElement.dataset.version = version;
document.documentElement.dataset.started = 'true';
