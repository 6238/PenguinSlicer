// The plate configuration the page submits (wizard/README-details.md, "Submitting a plate";
// contracts/plate-configuration.md, "Fields in phase 2" and "From a profile to a plate
// configuration"), made from the tab's stored plate:
//   plate_id        the stored plate's id
//   submission_id   the submission's value, made by the caller each time the page decides to slice
//   parts           each part an instance names, under the page's own key (p1, p2… in the order of
//                   the plate's parts), with its name, sha256 and units
//   instances       the Layout step's instances, each with its ref, orientation or rotation, angle
//                   and the centre of its footprint (the stored plate keeps them in the form
//                   p_plate = Rz(angle) M p_part + t, which instanceTurn writes as the contract asks)
//   printer, filament, process   the chosen profile's
//   overrides       the chosen profile's own overrides, with the user's changes on top (the
//                   Settings step leaves out a change put back to the profile's value)
//   local_time      the browser's clock, YYYYMMDD-HHMM
// The fingerprint, by which the page knows whether the plate is already sliced as it stands, is a
// hash of the plate configuration less its two ids and its local time (which moves every minute).
import { instanceTurn } from './geometry/turn.js';

const NAME_CHARS = 200;
const wholeAngle = (deg) => ((Math.round(deg) % 360) + 360) % 360;
const two = (n) => String(n).padStart(2, '0');

// The browser's own clock, as YYYYMMDD-HHMM in the browser's time zone.
export function localTime(ms) {
  const d = new Date(ms);
  return `${d.getFullYear()}${two(d.getMonth() + 1)}${two(d.getDate())}-${two(d.getHours())}${two(d.getMinutes())}`;
}

// The chosen profile of the configuration, by the stored plate's filament and profile names.
function chosenProfile(configuration, settings) {
  if (!configuration || !Array.isArray(configuration.filaments) || !settings) return null;
  const filament = configuration.filaments.find((f) => f.name === settings.filament);
  return filament && Array.isArray(filament.profiles) ? filament.profiles.find((p) => p.name === settings.profile) ?? null : null;
}

// plateConfiguration({plate, configuration, plateId, submissionId, now}) is {configuration,
// problem}: the plate configuration, or null with what stops the page making one.
export function plateConfiguration({ plate, configuration, plateId, submissionId, now }) {
  if (!configuration) return { configuration: null, problem: 'the configuration is not read yet' };
  const settings = plate.settings ?? {};
  const profile = chosenProfile(configuration, settings);
  if (!profile) return { configuration: null, problem: `the configuration has no profile ${settings.profile} of ${settings.filament}` };

  const byKey = new Map(plate.parts.map((p) => [`${p.sha256}.${p.units}`, p]));
  const placed = (plate.instances ?? []).filter((i) => byKey.has(i.part));
  const named = new Set(placed.map((i) => i.part));
  const refs = new Map();
  const parts = {};
  for (const part of plate.parts) {
    const key = `${part.sha256}.${part.units}`;
    if (!named.has(key) || refs.has(key)) continue;
    const ref = `p${refs.size + 1}`;
    refs.set(key, ref);
    parts[ref] = { name: String(part.name ?? 'part').slice(0, NAME_CHARS) || 'part', sha256: part.sha256, units: part.units };
  }
  const instances = placed.map((i) => ({ ref: refs.get(i.part), ...instanceTurn(i.lay, wholeAngle(i.angle)), x: i.x, y: i.y }));
  return {
    configuration: {
      plate_id: plateId,
      submission_id: submissionId,
      parts,
      instances,
      printer: profile.printer,
      filament: profile.filament,
      process: profile.process,
      overrides: { ...(profile.overrides ?? {}), ...(settings.changes ?? {}) },
      local_time: localTime(now),
    },
    problem: null,
  };
}

// The body's size as sent, in bytes of UTF-8.
export function bodyBytes(configuration) {
  return new TextEncoder().encode(JSON.stringify(configuration)).length;
}

// A hash of the plate configuration less its plate_id, submission_id and local_time: 53 bits of
// cyrb53 over its JSON, written in hexadecimal. It tells one plate from a changed one, nothing more.
export function fingerprint(configuration) {
  const { plate_id: _p, submission_id: _s, local_time: _t, ...rest } = configuration;
  const text = JSON.stringify(rest);
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16);
}
