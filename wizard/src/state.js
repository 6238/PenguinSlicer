// What the panel shows, in one place: the step, who the user is and the current group, the
// configuration and its name, the table of settings, the plate summary's figures. Each change is
// told to every listener at once, so that every part of the panel is drawn from the same state.
// It lives in the page's memory only: the record of the user's work is the browser's storage
// (storage.js), which opening.js keeps in step with it.
//   step          'parts', 'settings', 'layout', 'preview' or 'send'
//   user          {id, name} from /api/me, or null before it is read
//   groups        the user's groups from /api/me, [] before it is read
//   group         the current group's id, or null before /api/me is read
//   plateId       the tab's plate's plate_id, or null before the storage is opened
//   configuration the configuration document from /api/configuration, or null
//   configSource  its `source`, 'group' or 'default', or null
//   configName    the configuration's `name`, shown after "Config: ", or null
//   settingsTable the table of settings from /api/settings-table, or null
//   printer       the table's catalog entry of the configuration's printer (its printable area
//                 and height), or null
//   plate         {parts, instances, arriving, arrivingInstances, filament, filamentFull, profile,
//                 changes}: parts and instances count the parts that have arrived, arriving and
//                 arrivingInstances those still arriving (parts.js)
//                 changes, the change details' lines (settings.js)
//   advanced      whether advanced mode is open, over the Settings step (settings.js)
//   layoutProblem the Layout step's first problem, which holds Next, or null
//   sliced        whether the plate has a sliced file
//   expired       whether the plate's sliced file has expired, the expired message shown in place of
//                 the result and of Send (slicing.js)
export function createStore() {
  let state = {
    step: 'parts',
    user: null,
    groups: [],
    group: null,
    plateId: null,
    configuration: null,
    configSource: null,
    configName: null,
    settingsTable: null,
    printer: null,
    plate: { parts: 0, instances: 0, arriving: 0, arrivingInstances: 0, filament: null, filamentFull: null, profile: null, changes: [] },
    advanced: false,
    layoutProblem: null,
    sliced: false,
    expired: false,
  };
  const listeners = new Set();
  return {
    get: () => state,
    set(patch) {
      const before = state;
      state = { ...state, ...patch, plate: { ...state.plate, ...(patch.plate ?? {}) } };
      for (const listener of listeners) listener(state, before);
    },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
  };
}
