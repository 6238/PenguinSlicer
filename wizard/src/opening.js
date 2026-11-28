// The page opening, and the reload glyph (wizard/README-details.md, "The current group", "The
// configuration and the table of settings", "What the browser keeps"):
//   1. GET /api/settings-table and GET /api/me, at once: the table acts for no group, and the
//      Layout step's plate, the plate summary and the change details are drawn from it;
//   2. the tab's plate from the browser's storage, for the user /api/me names (the storage module
//      stores `owner` from the start and clears every plate for a different user) and its current
//      group: the tab's own plate's group while the user has it, otherwise the stored current
//      group, otherwise the first of the user's groups;
//   3. GET /api/configuration, with X-PenguinSlicer-Group naming that group; the header names its
//      `name`, and the plate's filament and profile are kept by name, or replaced by the first
//      and said in a notification when they are gone.
// The reload glyph reads the configuration again in the same way, and the table of settings
// again only when the configuration names a printer the table lacks. Every failure on the way
// is an error report shown as a notification: the report of the component that wrote it, or the
// wizard's own wizard.bad_answer for an answer the page cannot use. A quiet failure is retried by
// the module that makes every request, and is no failure here.
//
// From then on the stored plate follows the store: a change of step, filament or profile is
// written at once.
import { catalogPrinter, configurationProblem, meProblem, settleChoice, settingsTableProblem } from './configuration.js';
import { CONFIG_FILAMENT_GONE, CONFIG_NOW_USES, CONFIG_PROFILE_GONE, badAnswer } from './sentences.js';

// An answer, or the wizard's own report when its body is not of the shape the page needs.
function usable(answer, path, problem) {
  if (!answer.ok) return answer;
  const fault = problem(answer.body);
  if (fault === null) return answer;
  return { ok: false, status: answer.status, report: { ...badAnswer(path, answer.status, JSON.stringify(answer.body)), detail: `${path}: ${fault}` } };
}

// openWizard({api, store, panel, storage}) resolves to {opened}, false when /api/me could not
// be used (its report is shown, and nothing is asked or stored for a group).
export async function openWizard({ api, store, panel, storage }) {
  const tell = (report, key) => panel.notify({ kind: 'error', what: report.message, todo: report.remedy, key });

  async function readTable() {
    const answer = usable(await api.get('/api/settings-table'), '/api/settings-table', settingsTableProblem);
    if (!answer.ok) { tell(answer.report, 'settings-table'); return false; }
    const state = store.get();
    store.set({ settingsTable: answer.body, printer: state.configuration ? catalogPrinter(answer.body, state.configuration.printer) : null });
    return true;
  }

  async function readConfiguration() {
    const answer = usable(await api.get('/api/configuration'), '/api/configuration', configurationProblem);
    if (!answer.ok) { tell(answer.report, 'configuration'); return false; }
    const { configuration, source, name } = answer.body;
    const { plate } = store.get();
    const choice = settleChoice(configuration, { filament: plate.filament, profile: plate.profile });
    store.set({
      configuration, configSource: source, configName: name,
      printer: catalogPrinter(store.get().settingsTable, configuration.printer),
      plate: { filament: choice.filament, filamentFull: choice.filament, profile: choice.profile },
    });
    if (choice.gone) {
      const what = choice.gone.filament !== undefined && choice.gone.profile === undefined
        ? CONFIG_FILAMENT_GONE(choice.gone.filament)
        : CONFIG_PROFILE_GONE(choice.gone.profile, choice.gone.filament);
      panel.notify({ kind: 'warn', what, todo: CONFIG_NOW_USES(choice.filament, choice.profile), key: 'configuration-choice' });
    }
    return true;
  }

  let reading = null;
  function reloadConfiguration() {
    if (reading) return reading;
    reading = (async () => {
      if (!(await readConfiguration())) return;
      const { settingsTable, configuration } = store.get();
      if (settingsTable && !catalogPrinter(settingsTable, configuration.printer)) await readTable();
    })().finally(() => { reading = null; });
    return reading;
  }

  const table = readTable();
  const me = usable(await api.get('/api/me'), '/api/me', meProblem);
  if (!me.ok) {
    tell(me.report, 'me');
    await table;
    return { opened: false };
  }
  const { user, groups } = me.body;
  const { plate, group } = await storage.begin({ user: user.id, groups });
  store.set({
    user, groups, group, plateId: plate.plate_id, step: plate.step,
    plate: {
      parts: plate.parts.length, instances: plate.instances.length,
      filament: plate.settings.filament, filamentFull: plate.settings.filament, profile: plate.settings.profile,
    },
  });

  // The stored plate follows the store from here on.
  store.subscribe((state, before) => {
    const patch = {};
    if (state.step !== before.step) patch.step = state.step;
    if (state.plate.filament !== before.plate.filament || state.plate.profile !== before.plate.profile) {
      patch.settings = { ...storage.plate().settings, filament: state.plate.filament, profile: state.plate.profile };
    }
    if (Object.keys(patch).length) storage.update(patch);
  });
  panel.onReloadConfiguration(reloadConfiguration);

  await readConfiguration();
  await table;
  return { opened: true };
}
