// What the page takes from the configuration and the table of settings
// (wizard/README-details.md, "The configuration and the table of settings"; contracts/
// configuration.md and contracts/settings-table.md), and the shapes it needs of the answers
// that carry them and of GET /api/me before it uses one. An answer of another shape is the
// wizard's own report wizard.bad_answer, shown and not retried, like any answer the page
// cannot read.

// The first filament and its first profile: what a new plate starts with.
export function firstChoice(configuration) {
  const filament = configuration.filaments[0];
  return { filament: filament.name, profile: filament.profiles[0].name };
}

// The chosen filament and profile, by name, against a configuration: kept when both names are
// still in it (compared exactly, case and spaces included), otherwise the first filament or the
// filament's first profile in its place. `gone` says which name went: {filament} or
// {profile, filament}, or null.
export function settleChoice(configuration, chosen) {
  const first = firstChoice(configuration);
  if (!chosen || chosen.filament === null || chosen.filament === undefined) return { ...first, gone: null };
  const filament = configuration.filaments.find((f) => f.name === chosen.filament);
  if (!filament) return { ...first, gone: { filament: chosen.filament } };
  if (filament.profiles.some((p) => p.name === chosen.profile)) {
    return { filament: filament.name, profile: chosen.profile, gone: null };
  }
  const gone = chosen.profile === null || chosen.profile === undefined ? null : { profile: chosen.profile, filament: filament.name };
  return { filament: filament.name, profile: filament.profiles[0].name, gone };
}

// The table's catalog entry of the printer the configuration names, with its printable area
// and height, or null when the table does not hold it.
export function catalogPrinter(table, name) {
  if (!table || !table.catalog || !Array.isArray(table.catalog.printers)) return null;
  return table.catalog.printers.find((p) => p.name === name) ?? null;
}

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const isText = (v) => typeof v === 'string' && v.length > 0;

// What is wrong with an answer to GET /api/me for the page's use, or null.
export function meProblem(body) {
  if (!isObject(body)) return 'the answer is not an object';
  if (!isObject(body.user) || !isText(body.user.id)) return 'user.id is not a string';
  if (!Array.isArray(body.groups) || body.groups.length === 0) return 'groups is not a list of at least one group';
  for (const [i, group] of body.groups.entries()) {
    if (!isObject(group) || !isText(group.id) || typeof group.name !== 'string') return `groups[${i}] has no string id and name`;
  }
  return null;
}

// What is wrong with an answer to GET /api/configuration for the page's use, or null. The front
// server never serves an invalid configuration, so this checks only what the page leans on.
export function configurationProblem(body) {
  if (!isObject(body)) return 'the answer is not an object';
  if (typeof body.name !== 'string') return 'name is not a string';
  const c = body.configuration;
  if (!isObject(c)) return 'configuration is not an object';
  if (!isText(c.printer)) return 'configuration.printer is not a string';
  if (!Array.isArray(c.filaments) || c.filaments.length === 0) return 'configuration.filaments is not a list of at least one filament';
  for (const [i, f] of c.filaments.entries()) {
    if (!isObject(f) || typeof f.name !== 'string') return `configuration.filaments[${i}] has no name`;
    if (!Array.isArray(f.profiles) || f.profiles.length === 0) return `configuration.filaments[${i}].profiles is not a list of at least one profile`;
    for (const [j, p] of f.profiles.entries()) {
      if (!isObject(p) || typeof p.name !== 'string') return `configuration.filaments[${i}].profiles[${j}] has no name`;
    }
  }
  return null;
}

// What is wrong with an answer to GET /api/settings-table for the page's use, or null.
export function settingsTableProblem(body) {
  if (!isObject(body)) return 'the answer is not an object';
  if (!Array.isArray(body.settings)) return 'settings is not a list';
  if (!isObject(body.process_values)) return 'process_values is not an object';
  if (!isObject(body.catalog) || !Array.isArray(body.catalog.printers)) return 'catalog.printers is not a list';
  return null;
}
