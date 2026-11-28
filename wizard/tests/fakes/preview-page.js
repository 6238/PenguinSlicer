// A page on the Preview step's behaviour, for the tests of slicing.js and result.js: the real
// module that makes every request over the fake front server, the real storage module over the
// fakes of the browser's storage, on the fake clock, with a plate of three instances of two parts
// laid out; the Settings and Layout steps, the panel and the geometry stood in for by what the
// Preview and Send steps ask of them.
import { createHash } from 'node:crypto';

import { createApi } from '../../src/api.js';
import { createResult } from '../../src/result.js';
import { createSlicing } from '../../src/slicing.js';
import { createStore } from '../../src/state.js';
import { createStorage } from '../../src/storage.js';
import { FakeClock } from './clock.js';
import { FakeFrontServer, events, example, steps } from './front_server.js';
import { boxFile } from './stl.js';
import { FakeLocks, FakeRecords, FakeTab } from './storage.js';

export const S = 1000;
export const ME = example('wizard-front/me.json');
export const JOB = '3f9a1c2b';
export const EVENTS = /^\/api\/slices\/[\w-]+\/events$/;
export const hex = (bytes) => createHash('sha256').update(new Uint8Array(bytes)).digest('hex');
export const A = boxFile('bracket');
export const B = boxFile('spacer', [40, 30, 10]);
export const CONFIGURATION = example('configuration-default.json');

export const progress = (fields) => ({ job: JOB, state: 'running', stage: 'generating_infill', stage_label: 'Generating infill', fraction: 0.42, elapsed_s: 31.5, expected_s: 75, sequence: 17, ...fields });
export const accepted = (fields = {}) => ({ slice: { id: JOB, plate_id: 'x', submission_id: 'y', progress: progress({ state: 'queued', stage: 'queued', stage_label: 'Waiting for the slicer', ahead: 2, elapsed_s: 0, sequence: 1, fraction: undefined, ...fields }) } });
export const doneReport = (sequence = 41, details = {}) => {
  const report = example('wizard-front/slice-done.json').progress;
  return { ...report, sequence, sliced_file: { ...report.sliced_file, ...details } };
};
export const failedReport = (error, sequence = 30) => progress({ state: 'failed', error, sequence });

export async function openPage({ step = 'layout', changes = {} } = {}) {
  const clock = new FakeClock();
  const server = new FakeFrontServer();
  const records = new FakeRecords();
  const store = createStore();
  let ids = 0;
  const newId = () => `id-${(ids += 1)}`;
  const api = createApi({ transport: server.transport, clock, version: 'v', currentGroup: () => store.get().group, random: () => 0.5 });
  const reports = [];
  const report = (what, fields = {}) => { reports.push({ what, ...fields }); };
  const storage = createStorage({ openRecords: () => records.open(), locks: new FakeLocks().forTab('A'), tab: new FakeTab(), clock, newId: () => 'plate-1', report });
  const { plate, group } = await storage.begin({ user: ME.user.id, groups: ME.groups });
  await storage.addPart({ sha256: hex(A), units: 'mm', name: 'Bracket', quantity: 2, record: null }, A);
  await storage.addPart({ sha256: hex(B), units: 'in', name: 'Spacer', quantity: 1, record: null }, B);
  await storage.update({
    settings: { filament: 'PETG', profile: 'Structural', changes },
    instances: [
      { part: `${hex(A)}.mm`, lay: [1, 0, 0, 0], angle: 0, x: 80, y: 80 },
      { part: `${hex(A)}.mm`, lay: [1, 0, 0, 0], angle: 90, x: 150, y: 80 },
      { part: `${hex(B)}.in`, lay: [1, 0, 0, 0], angle: 0, x: 240, y: 200 },
    ],
  });
  store.set({ user: ME.user, groups: ME.groups, group, plateId: plate.plate_id, step, configuration: CONFIGURATION, plate: { filament: 'PETG', profile: 'Structural' } });
  const layout = {
    problem: null, notes: [],
    async idle() { store.set({ layoutProblem: layout.problem }); },
    notSliced(text) { layout.notes.push(text); },
  };
  const settings = {
    setQuick(id, v) {
      const plateNow = storage.plate();
      storage.update({ settings: { ...plateNow.settings, changes: { ...plateNow.settings.changes, enable_support: v, support_type: 'tree(auto)' } } });
    },
  };
  const notices = [];
  const panel = {
    goTo: (s) => store.set({ step: s }),
    notify: (n) => { const at = notices.findIndex((x) => x.key === n.key); if (at >= 0) notices.splice(at, 1); notices.push(n); },
    dropNotice: (key) => { const at = notices.findIndex((x) => x.key === key); if (at >= 0) notices.splice(at, 1); },
  };
  const slicing = createSlicing({ api, clock, storage, store, settings, layout, panel, report, newId, random: () => 0.5 });
  const saved = [];
  const meshes = new Map();
  const geometry = { mesh: (key) => meshes.get(key) ?? null };
  const result = createResult({ api, slicing, store, panel, geometry, save: (href, name) => saved.push({ href, name }) });
  const page = { clock, server, store, api, storage, slicing, result, reports, layout, records, notices, saved, meshes };
  page.enter = async () => { store.set({ step: 'preview' }); await clock.advance(0); };
  page.leave = async (to = 'layout') => { store.set({ step: to }); await clock.advance(0); };
  page.view = () => slicing.model();
  page.card = () => slicing.model().card;
  page.submissions = () => server.made('POST', '/api/slices').map((r) => JSON.parse(r.body));
  return page;
}

// A stream the test feeds, for the next progress stream the page opens.
export function feedStream(page, ...chunks) {
  const stream = steps.stream([events.version(), ...chunks]);
  page.server.script('GET', EVENTS, stream);
  return stream.feed;
}
