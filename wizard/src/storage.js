// The storage module: every read and write of the browser's storage goes through it, so that a
// refusal is handled in one place (wizard/README-details.md, "What the browser keeps" and "Which
// plate a tab shows"). The browser's storage is the record of a user's parts and plate; nothing on
// a server is. Each change is written at once, so a refresh at any moment loses nothing.
//
// The records, each under its key in the storage seam (src/seams/browser-storage.js):
//   owner                                  the user.id the stored work belongs to
//   uploadUnits, currentGroup              the user's two small choices
//   plates/<plate_id>                      a plate: its user and group, its parts (each part's
//                                          sha256, units, name, record and whether its bytes are
//                                          saved), its instances, its settings (filament and
//                                          profile by name, every change), its slice, its step,
//                                          whether advanced mode is open, and the time last used
//   part-bytes/<plate_id>/<sha256>.<units> one part's bytes, exactly as they arrived
// A part's bytes are a record of their own, so that a change to the layout or the settings
// rewrites a few kilobytes and never the plate's parts, which may reach 190 MB.
//
// Each tab works with its own plate. The tab names its plate in its sessionStorage (the tab seam),
// which survives a refresh and the page's own reload and dies with the tab, and holds the plate's
// lock (the locks seam, the browser's Web Locks), which the browser releases when the tab closes
// or crashes. A newly opened tab takes up the most recently used stored plate of its current
// group that no tab holds and that was used less than PLATE_UNUSED_H ago; otherwise it begins an
// empty plate. A stored plate that no tab holds and that has not been used for PLATE_UNUSED_H is
// dropped, checked when any page opens.

export const PLATE_UNUSED_H = 12;
// The format of a stored plate. A page leaves alone a plate of a format it does not know, which a
// later release's page wrote.
export const PLATE_FORMAT = 1;

const TAB_PLATE = 'penguinslicer.plate_id';
const PLATES = 'plates/';
const BYTES = 'part-bytes/';
const CHOICES = ['uploadUnits', 'currentGroup'];

export const plateLock = (plateId) => `penguinslicer-plate/${plateId}`;
const plateKey = (plateId) => `${PLATES}${plateId}`;
const bytesKey = (plateId, sha256, units) => `${BYTES}${plateId}/${sha256}.${units}`;
const partKey = (sha256, units) => `${sha256}.${units}`;

function emptyPlate(plateId, user, group, now, settings = null) {
  return {
    format: PLATE_FORMAT, plate_id: plateId, user, group, parts: [], instances: [],
    settings: settings ?? { filament: null, profile: null, changes: {} },
    slice: null, step: 'parts', advanced: false, last_used_ms: now,
  };
}

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

// Whether a stored plate of PLATE_FORMAT, under the key of `plateId`, has the shape the page
// takes up and opens: anything else would throw while the page opens.
function readable(p, plateId) {
  return p.plate_id === plateId && typeof p.user === 'string' && typeof p.group === 'string'
    && Array.isArray(p.parts) && p.parts.every((part) => isObject(part) && typeof part.sha256 === 'string' && typeof part.units === 'string')
    && Array.isArray(p.instances)
    && isObject(p.settings) && isObject(p.settings.changes)
    && typeof p.step === 'string' && Number.isFinite(p.last_used_ms);
}

const failure = (err) => `${err && err.name ? err.name : 'Error'}: ${err && err.message ? err.message : String(err)}`;

// createStorage({openRecords, locks, tab, clock, newId, report}):
//   openRecords()  the storage seam's opening: resolves to {get, put, delete, keys}, or rejects
//                  when the browser will not give the page its storage
//   locks          the locks seam ({tryHold(name), held()}), or null where the browser has none
//                  (a page not served over HTTPS or from localhost): then a tab keeps its own
//                  plate through a refresh and never takes up another
//   tab            the tab seam ({get(name), set(name, value)}), the tab's sessionStorage
//   newId()        a new plate_id, a random UUID
//   report(what, {part_sha256, detail})  a failure report about the page itself
export function createStorage({ openRecords, locks, tab, clock, newId, report }) {
  let records = null;          // null when the browser will not give the page its storage
  let plate = null;
  let release = null;
  let writing = Promise.resolve();
  let plateRefusalReported = false;
  const unsaved = new Map();   // the bytes of parts the browser refused to store, by sha256.units

  // Writes in the order asked, each after the one before it, so the last change is the one kept.
  // A write the browser refuses resolves to false.
  function queue(work) {
    const done = writing.then(() => (records ? work(records) : false)).then((r) => r !== false, (err) => err);
    writing = done.then(() => undefined);
    return done;
  }

  async function writePlate() {
    const copy = structuredClone(plate);
    const outcome = await queue((r) => r.put(plateKey(copy.plate_id), copy));
    if (outcome !== true && outcome !== false && !plateRefusalReported) {
      plateRefusalReported = true;
      report('storage_refused', { detail: `writing the plate: ${failure(outcome)}` });
    }
    return outcome === true;
  }

  async function dropPlate(plateId) {
    await queue(async (r) => {
      const keys = await r.keys();
      for (const key of keys) {
        if (key === plateKey(plateId) || key.startsWith(`${BYTES}${plateId}/`)) await r.delete(key);
      }
    });
  }

  async function hold(plateId) {
    if (!locks) return () => {};
    return locks.tryHold(plateLock(plateId));
  }

  // The stored plates of this page's format, {plates, unreadable}: `unreadable` names, by the
  // plate_id in their key, the plates of this format whose shape the page cannot use. A plate of
  // another format is in neither: a later release's page wrote it.
  async function readPlates() {
    const keys = await records.keys();
    const plates = [];
    const unreadable = [];
    for (const key of keys) {
      if (!key.startsWith(PLATES)) continue;
      const value = await records.get(key);
      if (!value || value.format !== PLATE_FORMAT) continue;
      if (readable(value, key.slice(PLATES.length))) plates.push(value);
      else unreadable.push(key.slice(PLATES.length));
    }
    return { plates, unreadable };
  }

  // Takes a stored plate into this tab: its parts whose bytes were never saved are gone with the
  // page that held them in memory.
  function takeUp(stored) {
    return { ...stored, parts: stored.parts.filter((p) => p.saved !== false) };
  }

  return {
    // Opens the storage for `user` and gives the tab its plate and its current group:
    //   {plate, group}
    // `groups` is /api/me's list: the tab's own plate keeps its group while the user has it, a new
    // tab starts in the stored current group when the user has it, and otherwise in the first.
    async begin({ user, groups }) {
      const has = (id) => groups.some((g) => g.id === id);
      const now = clock.now();
      try {
        records = await openRecords();
      } catch (err) {
        records = null;
        report('storage_refused', { detail: `opening the browser's storage: ${failure(err)}` });
      }
      const named = tab.get(TAB_PLATE);
      let own = null;
      let candidates = [];
      let group = groups[0].id;
      if (records) {
        try {
          const owner = await records.get('owner');
          if (owner === undefined && named) {
            report('storage_cleared', { detail: 'the owner record is gone while the tab still names its plate' });
          }
          if (owner !== undefined && owner !== user) {
            for (const key of await records.keys()) {
              if (key.startsWith(PLATES) || key.startsWith(BYTES) || CHOICES.includes(key)) await records.delete(key);
            }
          }
          if (owner !== user) await records.put('owner', user);
          const stored = await records.get('currentGroup');
          if (typeof stored === 'string' && has(stored)) group = stored;
          // Drop every plate no tab holds and unused for PLATE_UNUSED_H.
          const held = locks ? await locks.held() : new Set();
          const fresh = [];
          const { plates, unreadable } = await readPlates();
          // A plate of this format the page cannot read is dropped unless a tab holds it.
          const dropped = unreadable.filter((id) => !held.has(plateLock(id)));
          for (const id of dropped) await dropPlate(id);
          if (dropped.length) {
            report('page_failed', { detail: `${dropped.length} stored plate${dropped.length === 1 ? '' : 's'} of format ${PLATE_FORMAT} the page could not read, dropped` });
          }
          for (const p of plates) {
            const unused = now - p.last_used_ms >= PLATE_UNUSED_H * 3600 * 1000;
            if (unused && !held.has(plateLock(p.plate_id))) await dropPlate(p.plate_id);
            else fresh.push(p);
          }
          own = named ? fresh.find((p) => p.plate_id === named && p.user === user) ?? null : null;
          if (own && has(own.group)) group = own.group;
          else own = null;
          candidates = fresh
            .filter((p) => p.user === user && p.group === group && p.plate_id !== named && !held.has(plateLock(p.plate_id)))
            .sort((a, b) => b.last_used_ms - a.last_used_ms);
        } catch (err) {
          report('storage_refused', { detail: `reading the browser's storage: ${failure(err)}` });
          own = null;
          candidates = [];
        }
      }
      // The tab's own plate first (unless a duplicated tab's original holds it), then the most
      // recently used plate no tab holds, then an empty plate.
      const tries = [...(own ? [own] : []), ...(locks ? candidates : [])];
      for (const candidate of tries) {
        const releaseIt = await hold(candidate.plate_id);
        if (releaseIt) {
          release = releaseIt;
          plate = { ...takeUp(candidate), last_used_ms: now };
          break;
        }
      }
      if (!plate) {
        const plateId = newId();
        release = await hold(plateId);
        plate = emptyPlate(plateId, user, group, now);
      }
      tab.set(TAB_PLATE, plate.plate_id);
      await writePlate();
      return { plate: structuredClone(plate), group };
    },

    // The tab's plate as it stands, in memory.
    plate: () => structuredClone(plate),

    // Changes the plate and writes it at once; the time last used moves on.
    async update(patch) {
      plate = { ...plate, ...structuredClone(patch), last_used_ms: clock.now() };
      return writePlate();
    },

    // Adds a part to the plate: its bytes first, then the plate. A part whose bytes the browser
    // refuses is still added, marked unsaved and kept in memory, with one storage_refused report.
    // Resolves to {saved}.
    async addPart(part, bytes) {
      const key = partKey(part.sha256, part.units);
      let saved = false;
      if (records) {
        const outcome = await queue((r) => r.put(bytesKey(plate.plate_id, part.sha256, part.units), bytes));
        saved = outcome === true;
        if (!saved && outcome !== false) {
          report('storage_refused', { part_sha256: part.sha256, detail: `writing a part's bytes: ${failure(outcome)}` });
        }
      }
      if (!saved) unsaved.set(key, bytes);
      plate = { ...plate, parts: [...plate.parts, { ...part, saved }], last_used_ms: clock.now() };
      await writePlate();
      return { saved };
    },

    async removePart(sha256, units) {
      const plateId = plate.plate_id;
      unsaved.delete(partKey(sha256, units));
      plate = { ...plate, parts: plate.parts.filter((p) => !(p.sha256 === sha256 && p.units === units)), last_used_ms: clock.now() };
      await queue((r) => r.delete(bytesKey(plateId, sha256, units)));
      return writePlate();
    },

    // A part's bytes, exactly as they arrived, or null when the plate has no such part.
    async partBytes(sha256, units) {
      const key = partKey(sha256, units);
      if (unsaved.has(key)) return unsaved.get(key);
      if (!records) return null;
      await writing;
      try {
        return (await records.get(bytesKey(plate.plate_id, sha256, units))) ?? null;
      } catch {
        return null;
      }
    },

    // Drops this tab's plate and begins an empty one with a new plate_id, in `group` (by default
    // the plate's own), keeping the filament, the profile and the changes when `keepSettings`.
    // The old plate is dropped while this tab still holds its lock, and only then let go, so no
    // tab opening meanwhile can take up a plate whose records are being deleted.
    async newPlate({ group = plate.group, keepSettings = false } = {}) {
      const old = plate;
      unsaved.clear();
      await dropPlate(old.plate_id);
      if (release) release();
      release = null;
      const plateId = newId();
      release = await hold(plateId);
      plate = emptyPlate(plateId, old.user, group, clock.now(), keepSettings ? structuredClone(old.settings) : null);
      tab.set(TAB_PLATE, plateId);
      await writePlate();
      return structuredClone(plate);
    },

    // The user's small choices: 'uploadUnits' and 'currentGroup'.
    async choice(name) {
      if (!records) return null;
      await writing;
      try { return (await records.get(name)) ?? null; } catch { return null; }
    },
    async setChoice(name, value) {
      return queue((r) => r.put(name, value));
    },

    // Resolves once every write asked for so far is done.
    written: () => writing,
  };
}
