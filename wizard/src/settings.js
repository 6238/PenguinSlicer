// The Settings step's behaviour and advanced mode's (wizard/README-details.md, "The Settings step",
// "Advanced mode", "The profile's value of a setting"), apart from their drawing
// (panel/settings-step.js): the Filament and Profile menus, the four quick changes, and the one
// shared set of changes that they and advanced mode edit.
//
// A change is the user's value of a setting that differs from the profile's value, kept as Orca's
// `name` and its value written as Orca writes it, a string, so that it goes into the plate
// configuration's `overrides` as it is; a change put back to the profile's value is no change. The
// profile's value is the configuration profile's own override of the setting when it has one, and
// otherwise the table of settings' `process_values` for the profile's `process`. Changing the
// filament or the profile clears every change, since a change is a departure from one profile.
//
// The changes are part of the user's work: kept in the stored plate's `settings.changes`, in the
// order they were made, and written at once. Whether advanced mode is open is kept as the stored
// plate's `advanced`, so a refresh on the Settings step reopens it. The store holds the change
// details' lines (`plate.changes`), from which the plate summary draws its pill, and `advanced`.
import {
  CHANGES_BOX_TITLE, IN_ADVANCED_MODE, PROFILE_CLEARS, settingRefused,
} from './sentences.js';

// The quick changes, with the mockup's values (QUICK in the mockup's js/settings.js), each written
// into the changes as Orca writes it. Supports On also writes support_type tree(auto).
export const QUICK = [
  { id: 'infill', label: 'Infill', name: 'sparse_infill_density',
    entries: ['15', '25', '40', '60', '100'].map((n) => ({ value: `${n}%`, text: `${n} %` })) },
  { id: 'walls', label: 'Walls', name: 'wall_loops',
    entries: ['2', '3', '4', '6'].map((n) => ({ value: n, text: n })) },
  { id: 'supports', label: 'Supports', name: 'enable_support',
    entries: [{ value: '0', text: 'Off' }, { value: '1', text: 'On (tree, auto)' }] },
  { id: 'brim', label: 'Brim', name: 'brim_type',
    entries: [{ value: 'auto_brim', text: 'Auto' }, { value: 'no_brim', text: 'Off' }, { value: 'outer_only', text: 'Outer only' }] },
];
const SUPPORTS_ON = { name: 'support_type', value: 'tree(auto)' };

// The forms of a number, as the slice service checks them: ASCII digits only.
const DECIMAL = '-?[0-9]+(?:\\.[0-9]+)?';
const FORMS = {
  integer: new RegExp('^-?[0-9]+$'),
  decimal: new RegExp(`^${DECIMAL}$`),
  percent: new RegExp(`^${DECIMAL}%$`),
  decimal_or_percent: new RegExp(`^${DECIMAL}%?$`),
};
const FORM_WORDS = {
  integer: 'a whole number', decimal: 'a number', percent: 'a percentage such as 40%',
  decimal_or_percent: 'a number or a percentage',
};
const MAX_NUMBER_CHARS = 40;                 // the slice service's: no number Orca writes is longer
const INT_RANGE = [-(2 ** 31), 2 ** 31 - 1]; // Orca holds a whole-number setting in a C++ int
const CONTROL = /[\u0000-\u001f\u007f]/;
const LONE_SURROGATE = /[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/;

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

// The unit shown after a plain number: Orca's unit, less its " or %" where the setting takes either.
function plainUnit(entry) {
  const unit = entry.unit ?? '';
  const either = /^(.*) or %$/.exec(unit);
  return either ? either[1] : unit;
}

// A value as advanced mode, the changes box and the change details show it: a number with Orca's
// unit after it ("0.24 mm", "40 %"), a choice by Orca's label for it ("Gyroid"), a text as it is.
export function formatValue(entry, value) {
  if (value === undefined || value === null) return '';
  const v = String(value);
  if (!entry) return v;
  if (entry.kind === 'choice') {
    const choice = (entry.choices ?? []).find((c) => c.value === v);
    return choice ? choice.label : v;
  }
  if (entry.kind === 'number') {
    if (v.endsWith('%')) return `${v.slice(0, -1)} %`;
    const unit = plainUnit(entry);
    return unit ? `${v} ${unit}` : v;
  }
  return v;
}

// A number written the shortest way Orca writes it: "0.20" is "0.2", "05" is "5".
function shortest(figure) {
  const n = Number(figure);
  const text = Object.is(n, -0) ? '0' : String(n);
  return /e/i.test(text) ? figure : text;
}

const bound = (entry, n) => (entry.number_form === 'percent' ? `${n} %` : (plainUnit(entry) ? `${n} ${plainUnit(entry)}` : String(n)));

// readInput(entry, text, current) reads what the user typed or picked for a setting:
// {ok: true, value} with the value written as Orca writes it, or {ok: false, report} with the
// wizard's own error report, wizard.setting_refused, when it does not fit the setting's entry as
// the slice service would refuse it. A percentage typed without its sign gets it. `current` is the
// value the setting keeps, for the report's remedy.
export function readInput(entry, text, current) {
  const kept = current === undefined || current === null ? null : formatValue(entry, current);
  const refuse = (why, detail) => ({ ok: false, report: settingRefused(entry.label, why, kept, `${entry.name}: ${detail}`) });
  const raw = String(text ?? '');
  if (entry.kind === 'choice') {
    const values = (entry.choices ?? []).map((c) => c.value);
    return values.includes(raw) ? { ok: true, value: raw } : refuse('cannot be that value: choose one of the values Orca offers for it', `${JSON.stringify(raw.slice(0, 120))} is not a choice`);
  }
  if (entry.kind === 'text') {
    if (raw.length > entry.max_length) return refuse(`can be at most ${entry.max_length} characters long`, `${raw.length} characters, max_length ${entry.max_length}`);
    if (CONTROL.test(raw)) return refuse('cannot hold a line break or other control character', 'a control character');
    if (LONE_SURROGATE.test(raw)) return refuse('cannot hold a character that is not valid text', 'a lone surrogate');
    return { ok: true, value: raw };
  }
  const form = entry.number_form;
  let t = raw.trim();
  if (form === 'percent' && new RegExp(`^${DECIMAL}$`).test(t)) t = `${t}%`;
  const notForm = () => refuse(`must be ${FORM_WORDS[form]}`, `${JSON.stringify(t.slice(0, 120))} is not of the form ${form}`);
  if (t.length > MAX_NUMBER_CHARS || !FORMS[form] || !FORMS[form].test(t)) return notForm();
  const percent = t.endsWith('%');
  const figure = percent ? t.slice(0, -1) : t;
  if (form === 'integer' && (Number(figure) < INT_RANGE[0] || Number(figure) > INT_RANGE[1])) return notForm();
  const n = Number(figure);
  const below = 'min' in entry && n < entry.min;
  const above = 'max' in entry && n > entry.max;
  if (below || above) {
    const detail = `${t} outside ${entry.min ?? '-'}..${entry.max ?? '-'}`;
    // the unit once, after the second figure, as the mockup has it ("between 0.08 and 0.42 mm")
    if ('min' in entry && 'max' in entry) return refuse(`must be between ${entry.min} and ${bound(entry, entry.max)}`, detail);
    return below ? refuse(`must be at least ${bound(entry, entry.min)}`, detail) : refuse(`must be at most ${bound(entry, entry.max)}`, detail);
  }
  return { ok: true, value: `${shortest(figure)}${percent ? '%' : ''}` };
}

// Whether two values of a setting are the same value: numbers compared as numbers, a percentage
// never the same as a plain number; anything else compared exactly.
export function sameValue(entry, a, b) {
  if (a === undefined || a === null || b === undefined || b === null) return a === b;
  if (entry && entry.kind === 'number') {
    const pa = String(a).endsWith('%');
    const pb = String(b).endsWith('%');
    if (pa !== pb) return false;
    const fa = Number(pa ? String(a).slice(0, -1) : a);
    const fb = Number(pb ? String(b).slice(0, -1) : b);
    if (Number.isFinite(fa) && Number.isFinite(fb)) return fa === fb;
  }
  return String(a) === String(b);
}

// What a quick change's menu offers and shows: its entries, and the one chosen, the value the
// plate will be sliced with. A value off the list, the profile's or the user's, is one more entry
// at the top of the menu, written as advanced mode writes it; the profile's stays while it is the
// profile's value (the guide's recommendation for "A quick change whose value is not on its menu").
export function quickMenu(quick, entry, profileValue, value) {
  const listed = (v) => quick.entries.find((e) => sameValue(entry, e.value, v));
  const extra = [];
  for (const v of [profileValue, value]) {
    if (v === undefined || v === null || listed(v) || extra.some((e) => sameValue(entry, e.value, v))) continue;
    extra.push({ value: v, text: formatValue(entry, v) });
  }
  const on = value === undefined || value === null ? null : (listed(value) ?? extra.find((e) => sameValue(entry, e.value, value)));
  return { entries: [...extra, ...quick.entries], chosen: on ? on.value : null };
}

// Every setting's value in a configuration profile: the table's process values for its process,
// with the profile's own overrides over them.
export function profileValues(table, profile) {
  const processValues = table && isObject(table.process_values) && profile ? table.process_values[profile.process] : null;
  return { ...(isObject(processValues) ? processValues : {}), ...(profile && isObject(profile.overrides) ? profile.overrides : {}) };
}

// The table's sections, each with its setting groups, each with its settings, in the table's order.
export function sectionsOf(table) {
  if (!table || !Array.isArray(table.settings)) return [];
  const sections = new Map();
  for (const entry of table.settings) {
    if (!sections.has(entry.section)) sections.set(entry.section, { section: entry.section, groups: new Map() });
    const groups = sections.get(entry.section).groups;
    if (!groups.has(entry.group)) groups.set(entry.group, { group: entry.group, settings: [] });
    groups.get(entry.group).settings.push(entry);
  }
  return [...sections.values()].map((s) => ({ section: s.section, groups: [...s.groups.values()] }));
}

// createSettings({store, storage}):
//   store    the panel's store: the configuration, the table, the chosen filament and profile
//   storage  the storage module, holding the tab's plate
export function createSettings({ store, storage }) {
  let changes = {};              // name: value, in the order made
  let resumed = false;
  let pending = false;
  const listeners = new Set();
  let byName = { table: null, map: new Map() };

  const table = () => store.get().settingsTable;
  function entryOf(name) {
    const t = table();
    if (byName.table !== t) byName = { table: t, map: new Map((t && Array.isArray(t.settings) ? t.settings : []).map((s) => [s.name, s])) };
    return byName.map.get(name) ?? null;
  }
  function chosenFilament() {
    const { configuration, plate } = store.get();
    return configuration ? configuration.filaments.find((f) => f.name === plate.filament) ?? null : null;
  }
  function configProfile() {
    const filament = chosenFilament();
    return filament ? filament.profiles.find((p) => p.name === store.get().plate.profile) ?? null : null;
  }
  const profileValue = (name) => profileValues(table(), configProfile())[name];
  const value = (name) => (Object.hasOwn(changes, name) ? changes[name] : profileValue(name));
  const quickOf = (name) => QUICK.find((q) => q.name === name) ?? null;

  // A value in a quick change's words where it has them ("Off" for no_brim), else advanced mode's.
  function words(name, v) {
    const quick = quickOf(name);
    const entry = entryOf(name);
    const listed = quick ? quick.entries.find((e) => sameValue(entry, e.value, v)) : null;
    return listed ? listed.text : formatValue(entry, v);
  }

  // The change details' lines: "Quality › Layer height: 0.2 mm (profile 0.24 mm)", a setting with
  // a quick change named in its words ("Others › Brim: Off (profile Auto)").
  function lines() {
    return Object.keys(changes).map((name) => {
      const entry = entryOf(name);
      const quick = quickOf(name);
      return {
        name,
        section: entry ? entry.section : '',
        label: quick ? quick.label : (entry ? entry.label : name),
        value: words(name, changes[name]),
        profile: words(name, profileValue(name)),
      };
    });
  }

  let published = '[]';
  function tell() { for (const listener of listeners) listener(); }
  function publish() {
    const now = lines();
    published = JSON.stringify(now);
    store.set({ plate: { changes: now } });
    tell();
  }
  // A store change heard while the store tells its listeners is published after they are told, so
  // that no listener is handed an older state after a newer one; and only when the lines differ
  // from those last published.
  function publishSoon() {
    if (pending) return;
    pending = true;
    queueMicrotask(() => {
      pending = false;
      if (JSON.stringify(lines()) !== published) publish();
    });
  }
  // Writes the changes into the stored plate, with the chosen filament and profile when given.
  function write(chosen = {}) {
    if (!store.get().plateId) return;
    storage.update({ settings: { ...storage.plate().settings, ...chosen, changes: { ...changes } } });
  }
  function commit() { write(); publish(); }

  function setChange(name, v) {
    if (sameValue(entryOf(name), v, profileValue(name))) delete changes[name];
    else changes[name] = v;
  }

  // Drops each change the table no longer holds, whose value no longer fits, or that is the
  // profile's value: what the slice service would refuse, or no change at all. Waits for the
  // table and the configuration's profile.
  function settle() {
    if (!resumed || !table() || !configProfile()) return false;
    let dropped = false;
    for (const [name, v] of Object.entries(changes)) {
      const entry = entryOf(name);
      if (!entry || !readInput(entry, v).ok || sameValue(entry, v, profileValue(name))) {
        delete changes[name];
        dropped = true;
      }
    }
    if (dropped) write();
    return dropped;
  }

  const storedChanges = () => {
    const plate = store.get().plateId ? storage.plate() : null;
    return plate && isObject(plate.settings) && isObject(plate.settings.changes) ? plate.settings.changes : {};
  };

  store.subscribe((state, before) => {
    const now = state.plate;
    const was = before.plate;
    const moved = now.filament !== was.filament || now.profile !== was.profile;
    // the filament or the profile changed from one the plate had: every change goes
    if (moved && was.filament !== null && state.plateId
        && (Object.keys(changes).length || Object.keys(storedChanges()).length)) {
      changes = {};
      write();
      publishSoon();
    }
    if (moved || state.settingsTable !== before.settingsTable || state.configuration !== before.configuration) {
      settle();
      publishSoon();
    }
    if (state.advanced !== before.advanced && state.plateId) storage.update({ advanced: state.advanced });
    // advanced mode belongs to the Settings step
    if (state.advanced && state.step !== 'settings') queueMicrotask(() => { if (store.get().advanced && store.get().step !== 'settings') store.set({ advanced: false }); });
  });

  return {
    QUICK,
    entry: entryOf,
    value,
    profileValue,
    isChanged: (name) => Object.hasOwn(changes, name),
    // The changes, in the order made: [{name, value}].
    changes: () => Object.entries(changes).map(([name, v]) => ({ name, value: v })),
    // The number of changes among the table's settings that `test(entry)` accepts.
    changedIn: (test) => Object.keys(changes).filter((name) => { const e = entryOf(name); return e && test(e); }).length,
    sections: () => sectionsOf(table()),

    // The Filament menu: each filament's name and colour; the Profile menu: the chosen filament's
    // profiles, each with its purpose.
    filaments: () => (store.get().configuration ? store.get().configuration.filaments.map((f) => ({ name: f.name, colour: f.colour })) : []),
    profiles: () => (chosenFilament() ? chosenFilament().profiles.map((p) => ({ name: p.name, purpose: p.purpose })) : []),
    chooseFilament(name) {
      const { configuration, plate } = store.get();
      const filament = configuration && configuration.filaments.find((f) => f.name === name);
      if (!filament || name === plate.filament) return;
      changes = {};
      write({ filament: filament.name, profile: filament.profiles[0].name });
      store.set({ plate: { filament: filament.name, filamentFull: filament.name, profile: filament.profiles[0].name, changes: [] } });
      tell();
    },
    chooseProfile(name) {
      const filament = chosenFilament();
      if (!filament || !filament.profiles.some((p) => p.name === name) || name === store.get().plate.profile) return;
      changes = {};
      write({ filament: filament.name, profile: name });
      store.set({ plate: { profile: name, changes: [] } });
      tell();
    },

    // The caution under the Profile menu, or null with no change.
    caution: () => (Object.keys(changes).length ? PROFILE_CLEARS(Object.keys(changes).length) : null),
    // The changes box's heading.
    boxTitle: () => CHANGES_BOX_TITLE(Object.keys(changes).length, store.get().plate.profile),

    // The quick changes as their menus show them: [{id, label, name, entries, chosen, changed, title}].
    quick: () => QUICK.map((q) => {
      const entry = entryOf(q.name);
      const menu = quickMenu(q, entry, profileValue(q.name), value(q.name));
      return { id: q.id, label: q.label, name: q.name, entries: menu.entries, chosen: menu.chosen,
        changed: Object.hasOwn(changes, q.name), title: IN_ADVANCED_MODE(entry ? entry.label : q.label) };
    }),
    // A quick change's menu set to `v`: the profile's own value removes the change. Supports On
    // also writes support_type tree(auto); Off writes nothing for support_type.
    setQuick(id, v) {
      const quick = QUICK.find((q) => q.id === id);
      if (!quick) return;
      setChange(quick.name, v);
      if (quick.id === 'supports' && v === '1') setChange(SUPPORTS_ON.name, SUPPORTS_ON.value);
      commit();
    },
    // A setting set in advanced mode from what was typed or picked: {ok} or {ok: false, report}.
    set(name, text) {
      const entry = entryOf(name);
      if (!entry) return { ok: false, report: settingRefused(name, 'is not a setting PenguinSlicer can change', null, `${name} is not in the table of settings`) };
      const read = readInput(entry, text, value(name));
      if (read.ok) { setChange(name, read.value); commit(); }
      return read;
    },
    reset(name) { delete changes[name]; commit(); },
    resetAll() { changes = {}; commit(); },

    openAdvanced() { store.set({ advanced: true }); },
    closeAdvanced() { store.set({ advanced: false }); },

    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },

    // Takes up the stored plate's changes when the page opens, and advanced mode when it was open
    // on the Settings step.
    async resume() {
      const stored = storedChanges();
      changes = {};
      for (const [name, v] of Object.entries(stored)) if (typeof v === 'string') changes[name] = v;
      resumed = true;
      settle();
      publish();
      const plate = storage.plate();
      if (plate.advanced === true && store.get().step === 'settings') store.set({ advanced: true });
      else if (plate.advanced === true) storage.update({ advanced: false });
    },
  };
}
