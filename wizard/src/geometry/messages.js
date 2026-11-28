// The worker's side of its messages, kept apart from the worker's own file so that the tests
// run it in their own thread through the same messages. Each message is {id, op, ...}; each
// reply {id, ok: true, result} or {id, ok: false, error}, the error an error report.
//   read     {key, buffer, units}       reads a binary STL; replies its triangles, its box and
//                                       its corners for drawing (a Float32Array, transferred)
//   faces    {key}                      the patches it can be laid down by, found once
//   orient   {key}                      the way it lies best, and how the plate configuration
//                                       carries that turn
//   arrange  {plateConfiguration, geometry, printer, supports}
//   check    {plateConfiguration, geometry, printer, supports}
//   forget   {key}
// `geometry` maps each part key of the plate configuration to the key it was read under;
// `printer` is the printable area ({min, max, height}) and `supports` whether supports are on.
import { arrangePlate } from './arrange.js';
import { GeometryError, LAYOUT_FAILED, errorReport } from './errors.js';
import { autoOrient } from './orient.js';
import { analysePart } from './part.js';
import { checkPlate, plateOf } from './placement.js';
import { readBinaryStl } from './stl.js';
import { instanceTurn } from './turn.js';

class PageFault extends Error {}

const patchSummary = (p) => ({
  kind: p.kind, normal: p.normal, area: p.area, outline: p.outline,
  ...(p.kind === 'box' ? { side: p.side } : { face: p.face }),
  ...(p.stable === undefined ? {} : { stable: p.stable, height: p.height }),
});

export function createGeometry() {
  const parts = new Map();
  const footprints = new Map();

  const partOf = (key) => {
    const part = parts.get(key);
    if (!part) throw new PageFault(`no part was read under the key ${JSON.stringify(key)}`);
    return part;
  };
  const analysed = (key) => {
    const part = partOf(key);
    let computed = false;
    if (!part.analysis) {
      part.analysis = analysePart(part.mesh);
      part.choice = autoOrient(part.analysis);
      computed = true;
    }
    return [part, computed];
  };
  const pointsFor = (geometry) => Object.fromEntries(Object.entries(geometry).map(([ref, key]) => [ref, analysed(key)[0].analysis.hull.points]));
  const plateFor = (message) => plateOf(message.printer, Boolean(message.supports));

  const ops = {
    read(m) {
      const mesh = readBinaryStl(m.buffer, m.units);
      parts.set(m.key, { mesh });
      const positions = new Float32Array(mesh.positions);
      return [{ triangles: mesh.triangles, min: mesh.min, max: mesh.max, positions }, [positions.buffer]];
    },
    faces(m) {
      const [part, computed] = analysed(m.key);
      const a = part.analysis;
      const dropped = {};
      for (const f of a.faces) if (f.dropped) dropped[f.dropped] = (dropped[f.dropped] || 0) + 1;
      return [{ computed, hullTriangles: a.hullTriangles, faces: a.faces.length, dropped, patches: a.patches.map(patchSummary) }, []];
    },
    orient(m) {
      const [part, computed] = analysed(m.key);
      const { candidates, ...choice } = part.choice;
      return [{ computed, ...choice, turn: instanceTurn(choice.lay, 0) }, []];
    },
    arrange(m) {
      const result = arrangePlate(m.plateConfiguration, pointsFor(m.geometry), plateFor(m));
      return [result, []];
    },
    check(m) {
      return [{ problems: checkPlate(m.plateConfiguration, pointsFor(m.geometry), plateFor(m), footprints) }, []];
    },
    forget(m) {
      parts.delete(m.key);
      footprints.clear();
      return [{}, []];
    },
  };

  return {
    handle(message) {
      try {
        const op = Object.hasOwn(ops, message.op) ? ops[message.op] : null;
        if (!op) throw new PageFault(`the worker has no message ${JSON.stringify(message.op)}`);
        const [result, transfer] = op(message);
        return { reply: { id: message.id, ok: true, result }, transfer };
      } catch (err) {
        const error = err instanceof GeometryError ? err.report : errorReport(LAYOUT_FAILED, `${err.name}: ${err.message}`);
        return { reply: { id: message.id, ok: false, error }, transfer: [] };
      }
    },
  };
}
