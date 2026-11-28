// What the page takes from the configuration and the table of settings (src/configuration.js;
// wizard/README-details.md, "The configuration and the table of settings" and "The current
// group"): the first filament and its first profile, a stored choice kept when its names are
// still there and replaced by the first when they are gone, the printer's plate from the
// table's catalog, and the shapes the page needs before it uses an answer.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { catalogPrinter, firstChoice, meProblem, configurationProblem, settleChoice, settingsTableProblem } from '../src/configuration.js';
import { example } from './fakes/front_server.js';

const DEFAULT = example('configuration-default.json');
const HAND = example('configuration-hand-written.json');
const TABLE = example('settings-table.json');

test('a new plate starts with the first filament and its first profile', () => {
  assert.deepEqual(firstChoice(DEFAULT), { filament: 'PETG', profile: 'Standard' });
  assert.deepEqual(firstChoice(HAND), { filament: 'Black PETG', profile: 'Structural' });
});

test('a choice whose names are still in the configuration is kept, compared exactly', () => {
  assert.deepEqual(settleChoice(DEFAULT, { filament: 'PLA', profile: 'Standard' }), { filament: 'PLA', profile: 'Standard', gone: null });
  assert.deepEqual(settleChoice(DEFAULT, { filament: 'PETG', profile: 'Draft' }), { filament: 'PETG', profile: 'Draft', gone: null });
});

test('no choice yet is the first filament and its first profile, and nothing is gone', () => {
  assert.deepEqual(settleChoice(DEFAULT, null), { filament: 'PETG', profile: 'Standard', gone: null });
  assert.deepEqual(settleChoice(DEFAULT, { filament: null, profile: null }), { filament: 'PETG', profile: 'Standard', gone: null });
});

test('a filament gone from the configuration gives the first filament and its first profile, and says which', () => {
  assert.deepEqual(settleChoice(DEFAULT, { filament: 'PETG-CF', profile: 'Stiff bracket' }),
    { filament: 'PETG', profile: 'Standard', gone: { filament: 'PETG-CF' } });
  // compared exactly: case counts
  assert.deepEqual(settleChoice(DEFAULT, { filament: 'petg', profile: 'Standard' }).gone, { filament: 'petg' });
});

test('a profile gone from its filament gives the filament\'s first profile, and says which', () => {
  assert.deepEqual(settleChoice(DEFAULT, { filament: 'PLA', profile: 'Structural' }),
    { filament: 'PLA', profile: 'Standard', gone: { profile: 'Structural', filament: 'PLA' } });
  assert.deepEqual(settleChoice(HAND, { filament: 'Orange PETG', profile: 'Draft' }),
    { filament: 'Orange PETG', profile: 'Structural', gone: { profile: 'Draft', filament: 'Orange PETG' } });
});

test('the plate\'s size and height come from the catalog entry the configuration names', () => {
  const printer = catalogPrinter(TABLE, DEFAULT.printer);
  assert.equal(printer.name, 'Bambu Lab H2S 0.6 nozzle');
  assert.ok(Array.isArray(printer.printable_area));
  assert.equal(typeof printer.printable_height, 'number');
  assert.equal(catalogPrinter(TABLE, 'Bambu Lab X9 0.4 nozzle'), null);
  assert.equal(catalogPrinter(null, DEFAULT.printer), null);
});

test('the contract\'s examples have the shapes the page needs', () => {
  assert.equal(meProblem(example('wizard-front/me.json')), null);
  assert.equal(configurationProblem({ configuration: DEFAULT, source: 'default', name: 'PenguinSlicer default', revision: null }), null);
  assert.equal(settingsTableProblem(TABLE), null);
});

test('an answer to /api/me the page cannot use is named', () => {
  assert.match(meProblem(null), /not an object/);
  assert.match(meProblem({ user: { name: 'A' }, groups: [{ id: 'g', name: 'G' }] }), /user\.id/);
  assert.match(meProblem({ user: { id: 'u', name: 'A' }, groups: [] }), /groups/);
  assert.match(meProblem({ user: { id: 'u', name: 'A' }, groups: [{ id: 7, name: 'G' }] }), /groups\[0\]/);
});

test('an answer to /api/configuration the page cannot use is named', () => {
  const good = { configuration: DEFAULT, source: 'default', name: 'PenguinSlicer default', revision: null };
  assert.match(configurationProblem({ ...good, name: 3 }), /name/);
  assert.match(configurationProblem({ ...good, configuration: { ...DEFAULT, filaments: [] } }), /filaments/);
  assert.match(configurationProblem({ ...good, configuration: { ...DEFAULT, filaments: [{ name: 'X', colour: '#000000', profiles: [] }] } }), /profiles/);
  assert.match(configurationProblem({ ...good, configuration: { ...DEFAULT, printer: null } }), /printer/);
});

test('an answer to /api/settings-table the page cannot use is named', () => {
  assert.match(settingsTableProblem({ ...TABLE, catalog: {} }), /catalog\.printers/);
  assert.match(settingsTableProblem({ ...TABLE, settings: 'x' }), /settings/);
  assert.match(settingsTableProblem([]), /not an object/);
});
