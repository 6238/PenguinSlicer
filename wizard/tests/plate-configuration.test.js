// The plate configuration the page makes (src/plate-configuration.js; wizard/README-details.md,
// "Submitting a plate"; contracts/plate-configuration.md, "To be built"): built from the stored
// plate, the Settings step's changes and the Layout step's instances, exactly in the contract's
// phase 2 form, checked against the contract's example and the thirteen shared plates.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { MAX_PLATE_CONFIGURATION_BYTES } from '../src/page-constants.js';
import { bodyBytes, fingerprint, localTime, plateConfiguration } from '../src/plate-configuration.js';
import { ORIENTATION_MATRICES, matrixOfQuaternion } from '../src/geometry/turn.js';
import { EXAMPLES, example } from './fakes/front_server.js';

const BRACKET = 'f41155dd67adfc26a035de3b56c4997cae15252645388c8f583a1c74ec85f893';
const SPACER = 'fb78e3c785af625f95c6c8d63c60354f5bcea552bc5bdf670a0f006ab8608f0d';
const PLATE_ID = '3f0c8f2e-6a1b-4d5e-9c27-8b14d0e6a5f1';
const SUBMISSION = 'b71e2a94-0d3c-4f8a-a6e5-2c9d17f04b38';

// The unit quaternion [w, x, y, z] of a rotation matrix (one of the six orientations).
function quaternionOf(m) {
  const w = Math.sqrt(Math.max(0, 1 + m[0][0] + m[1][1] + m[2][2])) / 2;
  if (w > 1e-6) return [w, (m[2][1] - m[1][2]) / (4 * w), (m[0][2] - m[2][0]) / (4 * w), (m[1][0] - m[0][1]) / (4 * w)];
  const x = Math.sqrt(Math.max(0, 1 + m[0][0] - m[1][1] - m[2][2])) / 2;
  if (x > 1e-6) return [(m[2][1] - m[1][2]) / (4 * x), x, (m[0][1] + m[1][0]) / (4 * x), (m[0][2] + m[2][0]) / (4 * x)];
  const y = Math.sqrt(Math.max(0, 1 - m[0][0] + m[1][1] - m[2][2])) / 2;
  return [(m[0][2] - m[2][0]) / (4 * y), (m[0][1] + m[1][0]) / (4 * y), y, (m[1][2] + m[2][1]) / (4 * y)];
}

// The stored plate's form of a plate configuration's instances and parts (layout.js keeps an
// instance as {part, lay, angle, x, y}; storage.js a part as {sha256, units, name, quantity}).
function storedFrom(config) {
  const keyOf = (ref) => `${config.parts[ref].sha256}.${config.parts[ref].units}`;
  const parts = Object.values(config.parts).map((p) => ({ sha256: p.sha256, units: p.units, name: p.name, quantity: 1, record: null, saved: true }));
  const instances = config.instances.map((i) => ({
    part: keyOf(i.ref),
    lay: i.rotation ?? quaternionOf(ORIENTATION_MATRICES[i.orientation]),
    angle: i.angle, x: i.x, y: i.y,
  }));
  return { plate_id: config.plate_id, parts, instances };
}

function configurationWith(profile) {
  return { format: 1, printer: profile.printer, upload_units: 'mm', filaments: [{ name: 'PLA', colour: '#e0e0e0', profiles: [{ name: 'Standard', purpose: 'everyday parts', ...profile }] }] };
}

const EXAMPLE = example('plate-configuration-phase-2.json');
const EXAMPLE_CONFIGURATION = configurationWith({
  printer: EXAMPLE.printer, filament: EXAMPLE.filament, process: EXAMPLE.process,
  overrides: { sparse_infill_density: '20%', wall_loops: '3' },
});
const EXAMPLE_PLATE = {
  ...storedFrom(EXAMPLE),
  settings: { filament: 'PLA', profile: 'Standard', changes: { enable_support: '0', brim_type: 'auto_brim' } },
};
const AT = new Date(2026, 9, 9, 14, 32, 5).getTime();        // the browser's local time

// The page's keys renamed to the example's, so that the two can be compared whole.
function renamed(config, names) {
  const parts = {};
  for (const [key, part] of Object.entries(config.parts)) parts[names[key]] = part;
  return { ...config, parts, instances: config.instances.map((i) => ({ ...i, ref: names[i.ref] })) };
}

test('the page makes the contract\'s phase 2 example from the same plate, field for field', () => {
  const { configuration, problem } = plateConfiguration({
    plate: EXAMPLE_PLATE, configuration: EXAMPLE_CONFIGURATION, plateId: PLATE_ID, submissionId: SUBMISSION, now: AT,
  });
  assert.equal(problem, null);
  assert.deepEqual(Object.keys(configuration.parts), ['p1', 'p2']);
  assert.deepEqual(renamed(configuration, { p1: 'bracket', p2: 'spacer' }), EXAMPLE);
  // the fields in the contract's order, as the example has them
  assert.deepEqual(Object.keys(configuration), Object.keys(EXAMPLE));
});

test('only the parts an instance names are sent, keyed p1, p2… in the plate\'s order', () => {
  const plate = { ...EXAMPLE_PLATE, parts: [{ sha256: 'a'.repeat(64), units: 'in', name: 'Unplaced' }, ...EXAMPLE_PLATE.parts], instances: EXAMPLE_PLATE.instances.filter((i) => i.part.startsWith(SPACER)) };
  const { configuration } = plateConfiguration({ plate, configuration: EXAMPLE_CONFIGURATION, plateId: PLATE_ID, submissionId: SUBMISSION, now: AT });
  assert.deepEqual(configuration.parts, { p1: { name: 'Spacer', sha256: SPACER, units: 'mm' } });
  assert.deepEqual(configuration.instances.map((i) => i.ref), ['p1']);
});

test('an instance whose part is no longer on the plate is left out', () => {
  const plate = { ...EXAMPLE_PLATE, parts: EXAMPLE_PLATE.parts.filter((p) => p.sha256 === BRACKET) };
  const { configuration } = plateConfiguration({ plate, configuration: EXAMPLE_CONFIGURATION, plateId: PLATE_ID, submissionId: SUBMISSION, now: AT });
  assert.equal(configuration.instances.length, 3);
  assert.deepEqual(Object.keys(configuration.parts), ['p1']);
});

test('the overrides are the profile\'s own, with the user\'s changes on top', () => {
  const plate = { ...EXAMPLE_PLATE, settings: { ...EXAMPLE_PLATE.settings, changes: { wall_loops: '5', layer_height: '0.16' } } };
  const { configuration } = plateConfiguration({ plate, configuration: EXAMPLE_CONFIGURATION, plateId: PLATE_ID, submissionId: SUBMISSION, now: AT });
  assert.deepEqual(configuration.overrides, { sparse_infill_density: '20%', wall_loops: '5', layer_height: '0.16' });
});

test('a profile with no overrides and no change sends empty overrides', () => {
  const plate = { ...EXAMPLE_PLATE, settings: { filament: 'PETG', profile: 'Standard', changes: {} } };
  const { configuration } = plateConfiguration({ plate, configuration: example('configuration-default.json'), plateId: PLATE_ID, submissionId: SUBMISSION, now: AT });
  assert.deepEqual(configuration.overrides, {});
  assert.equal(configuration.printer, 'Bambu Lab H2S 0.6 nozzle');
  assert.equal(configuration.filament, 'Generic PETG @BBL H2S');
  assert.equal(configuration.process, '0.24mm Balanced Quality @BBL H2S 0.6 nozzle');
});

test('a plate whose filament or profile the configuration does not hold makes no plate configuration', () => {
  for (const settings of [{ filament: 'Nylon', profile: 'Standard', changes: {} }, { filament: 'PLA', profile: 'Fast', changes: {} }, { filament: null, profile: null, changes: {} }]) {
    const { configuration, problem } = plateConfiguration({ plate: { ...EXAMPLE_PLATE, settings }, configuration: EXAMPLE_CONFIGURATION, plateId: PLATE_ID, submissionId: SUBMISSION, now: AT });
    assert.equal(configuration, null);
    assert.match(problem, /profile/);
  }
  assert.match(plateConfiguration({ plate: EXAMPLE_PLATE, configuration: null, plateId: PLATE_ID, submissionId: SUBMISSION, now: AT }).problem, /configuration/);
});

test('the local time is the browser\'s clock as YYYYMMDD-HHMM', () => {
  assert.equal(localTime(new Date(2026, 0, 2, 3, 4, 59).getTime()), '20260102-0304');
  assert.equal(localTime(AT), '20261009-1432');
});

test('a part\'s name over 200 characters is cut to 200, as the contract allows', () => {
  const plate = { ...EXAMPLE_PLATE, parts: EXAMPLE_PLATE.parts.map((p) => ({ ...p, name: 'x'.repeat(250) })) };
  const { configuration } = plateConfiguration({ plate, configuration: EXAMPLE_CONFIGURATION, plateId: PLATE_ID, submissionId: SUBMISSION, now: AT });
  assert.equal(configuration.parts.p1.name.length, 200);
});

test('the fingerprint is the same plate\'s whatever its two ids and its time, and changes with the plate', () => {
  const make = (plate, submissionId = SUBMISSION, now = AT) => plateConfiguration({ plate, configuration: EXAMPLE_CONFIGURATION, plateId: PLATE_ID, submissionId, now }).configuration;
  const base = fingerprint(make(EXAMPLE_PLATE));
  assert.equal(typeof base, 'string');
  assert.equal(fingerprint(make(EXAMPLE_PLATE, 'another', AT + 3_600_000)), base);
  const moved = { ...EXAMPLE_PLATE, instances: EXAMPLE_PLATE.instances.map((i, n) => (n === 0 ? { ...i, x: i.x + 0.1 } : i)) };
  assert.notEqual(fingerprint(make(moved)), base);
  const turned = { ...EXAMPLE_PLATE, instances: EXAMPLE_PLATE.instances.map((i, n) => (n === 0 ? { ...i, angle: 1 } : i)) };
  assert.notEqual(fingerprint(make(turned)), base);
  const changed = { ...EXAMPLE_PLATE, settings: { ...EXAMPLE_PLATE.settings, changes: { enable_support: '1', support_type: 'tree(auto)', brim_type: 'auto_brim' } } };
  assert.notEqual(fingerprint(make(changed)), base);
});

test('the body\'s size is counted in bytes of UTF-8, against the 1 MB of one submission', () => {
  const { configuration } = plateConfiguration({ plate: EXAMPLE_PLATE, configuration: EXAMPLE_CONFIGURATION, plateId: PLATE_ID, submissionId: SUBMISSION, now: AT });
  assert.equal(bodyBytes(configuration), new TextEncoder().encode(JSON.stringify(configuration)).length);
  const named = { ...configuration, parts: { p1: { ...configuration.parts.p1, name: 'é'.repeat(10) } } };
  assert.equal(bodyBytes(named), new TextEncoder().encode(JSON.stringify(named)).length);
  assert.equal(MAX_PLATE_CONFIGURATION_BYTES, 1_048_576);
});

// The thirteen shared plates: each plate's instances, kept in the stored plate's form, come back
// from the page as the plate gives them: the same orientation or rotation, angle and position.
const PLACEMENT = join(EXAMPLES, 'placement');
const SHARED = readdirSync(PLACEMENT).filter((f) => f.endsWith('.json'));

test('there are thirteen shared plates', () => {
  assert.equal(SHARED.length, 13);
});

for (const name of SHARED) {
  test(`the page gives back the instances of the shared plate ${name}`, () => {
    const plate = JSON.parse(readFileSync(join(PLACEMENT, name), 'utf8')).plate_configuration;
    const stored = { ...storedFrom(plate), settings: { filament: 'PETG', profile: 'Standard', changes: plate.overrides } };
    const { configuration } = plateConfiguration({ plate: stored, configuration: example('configuration-default.json'), plateId: plate.plate_id, submissionId: plate.submission_id, now: AT });
    assert.equal(configuration.instances.length, plate.instances.length);
    configuration.instances.forEach((mine, n) => {
      const theirs = plate.instances[n];
      assert.equal(configuration.parts[mine.ref].sha256, plate.parts[theirs.ref].sha256);
      assert.equal(configuration.parts[mine.ref].name, plate.parts[theirs.ref].name);
      assert.equal(mine.x, theirs.x);
      assert.equal(mine.y, theirs.y);
      assert.equal(mine.angle, theirs.angle);
      if (theirs.orientation) {
        assert.equal(mine.orientation, theirs.orientation);
        assert.equal(mine.rotation, undefined);
      } else {
        const a = matrixOfQuaternion(mine.rotation);
        const b = matrixOfQuaternion(theirs.rotation);
        for (let i = 0; i < 3; i += 1) for (let j = 0; j < 3; j += 1) assert.ok(Math.abs(a[i][j] - b[i][j]) < 1e-8);
        assert.ok(Math.abs(Math.hypot(...mine.rotation) - 1) <= 1e-6);
      }
    });
    assert.deepEqual(configuration.overrides, plate.overrides);
  });
}
