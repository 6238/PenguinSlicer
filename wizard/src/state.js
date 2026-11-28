// What the panel shows, in one place: the step, the current group, the configuration's name and
// the plate summary's figures. Each change is told to every listener at once, so that every
// part of the panel is drawn from the same state. The later batches fill it from the front
// server and the browser's storage; the record of the user's work is the browser's storage, not
// this object.
//   step          'parts', 'settings', 'layout', 'preview' or 'send'
//   group         the current group's id, or null before /api/me is read
//   configName    the configuration's `name`, shown after "Config: ", or null
//   plate         {parts, instances, filament, filamentFull, profile, changes}
//   layoutProblem the Layout step's first problem, which holds Next, or null
//   sliced        whether the plate has a sliced file
export function createStore() {
  let state = {
    step: 'parts',
    group: null,
    configName: null,
    plate: { parts: 0, instances: 0, filament: null, filamentFull: null, profile: null, changes: [] },
    layoutProblem: null,
    sliced: false,
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
