// The worker's side of its messages, kept apart from the worker's own file so that the tests
// run it in their own thread through the same messages. Each message is {id, op, ...}; each
// reply {id, ok: true, result} or {id, ok: false, error}, the error an error report.
//   read     {key, buffer, units}       reads a binary STL; replies its triangles, its box and
//                                       its corners for drawing (a Float32Array, transferred)
//   faces    {key}                      the patches it can be laid down by, found once
//   orient   {key}                      the way it lies best, and how the plate configuration
//                                       carries that turn
//   arrange  {plateConfiguration, geometry, printer, supports}
//   check    {plateConfiguration, geometry, printer, supports}  the problems, in the slice
//                                       service's order, and each instance's footprint
//                                       `bounds` ([x0, y0, x1, y1] on the plate) and `heights`
//   settle   {plateConfiguration, geometry, printer, supports, index}  after a lay-down: where
//                                       instance `index` goes, the others where they stand
//                                       ({how, instance}, arrange.js settleInstance)
//   fit      {plateConfiguration, geometry, printer, supports, index}  the turn that makes it
//                                       fit the plate ({fits, angle}, arrange.js turnToFit)
//   picture  {key, px, colour}          the part's picture for its row, px by px RGBA pixels
//                                       (a Uint8ClampedArray, transferred), drawn as modelled
//   forget   {key}
// `geometry` maps each part key of the plate configuration to the key it was read under;
// `printer` is the printable area ({min, max, height}) and `supports` whether supports are on.
import { arrangePlate, settleInstance, turnToFit } from './arrange.js';
import { GeometryError, LAYOUT_FAILED, errorReport } from './errors.js';
import { autoOrient } from './orient.js';
import { analysePart } from './part.js';
import { checkPlate, placedOutlines, plateOf } from './placement.js';
import { MAX_PICTURE_PX, MIN_PICTURE_PX, drawPicture } from './picture.js';
import { readBinaryStl } from './stl.js';
import { ORIENTATION_MATRICES, instanceTurn } from './turn.js';

class PageFault extends Error {}

const finite = (v) => typeof v === 'number' && Number.isFinite(v);

// What is wrong with an instance's form, as the slice service judges it
// (contracts/plate-configuration.md, "An instance in phase 2": slice.bad_plate_configuration),
// or null. The page builds every instance, so such an instance is the page's own fault; checking
// it here keeps the placement check from showing green a plate the slice service refuses.
function instanceFault(instance) {
  if (!finite(instance.x) || !finite(instance.y)) return 'x and y must be finite numbers';
  if (!Number.isInteger(instance.angle) || instance.angle < 0 || instance.angle > 359) return 'angle must be a whole number of degrees, 0 to 359';
  const hasOrientation = 'orientation' in instance;
  const hasRotation = 'rotation' in instance;
  if (hasOrientation === hasRotation) return 'it must have exactly one of orientation and rotation';
  if (hasOrientation) {
    return Object.hasOwn(ORIENTATION_MATRICES, instance.orientation) ? null : `orientation ${JSON.stringify(instance.orientation)} is not one of the six`;
  }
  const q = instance.rotation;
  if (!Array.isArray(q) || q.length !== 4 || !q.every(finite)) return 'rotation must be four finite numbers';
  if (Math.abs(Math.hypot(...q) - 1) > 1e-6) return 'rotation must be a unit quaternion';
  return null;
}

// An instance whose ref names no part of the plate configuration, or a part the worker was not
// told where to find, is the page's fault too.
function refFault(instance, plateConfiguration, geometry) {
  const { ref } = instance;
  if (typeof ref !== 'string' || !Object.hasOwn(plateConfiguration.parts || {}, ref)) return `ref ${JSON.stringify(ref)} names no part of the plate configuration`;
  if (!Object.hasOwn(geometry || {}, ref)) return `ref ${JSON.stringify(ref)} names a part the worker was not given`;
  return null;
}

function checkInstances(plateConfiguration, geometry) {
  plateConfiguration.instances.forEach((instance, i) => {
    const fault = instanceFault(instance) || refFault(instance, plateConfiguration, geometry);
    if (fault) throw new PageFault(`instance ${i}: ${fault}`);
  });
}

// `index` names one instance of the message's plate configuration.
function checkIndex(m) {
  if (!Number.isInteger(m.index) || m.index < 0 || m.index >= m.plateConfiguration.instances.length) {
    throw new PageFault(`index ${JSON.stringify(m.index)} names no instance of the plate configuration`);
  }
}

const patchSummary = (p) => ({
  kind: p.kind, normal: p.normal, area: p.area, outline: p.outline,
  ...(p.kind === 'box' ? { side: p.side } : { face: p.face }),
  ...(p.stable === undefined ? {} : { stable: p.stable, height: p.height }),
});

export function createGeometry() {
  const parts = new Map();
  // Footprints by each read part's hull corners (placement.js, turnedFootprint): a part read
  // again or forgotten leaves none of its old footprints behind.
  const footprints = new WeakMap();

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
      checkInstances(m.plateConfiguration, m.geometry);
      const result = arrangePlate(m.plateConfiguration, pointsFor(m.geometry), plateFor(m));
      return [result, []];
    },
    check(m) {
      checkInstances(m.plateConfiguration, m.geometry);
      const points = pointsFor(m.geometry);
      const placed = placedOutlines(m.plateConfiguration, points, footprints);
      return [{
        problems: checkPlate(m.plateConfiguration, points, plateFor(m), footprints),
        bounds: placed.map((p) => p.bounds), heights: placed.map((p) => p.height),
      }, []];
    },
    settle(m) {
      checkInstances(m.plateConfiguration, m.geometry);
      checkIndex(m);
      return [settleInstance(m.plateConfiguration, pointsFor(m.geometry), plateFor(m), m.index, footprints), []];
    },
    fit(m) {
      checkInstances(m.plateConfiguration, m.geometry);
      checkIndex(m);
      return [turnToFit(m.plateConfiguration.instances[m.index], pointsFor(m.geometry), plateFor(m), footprints), []];
    },
    picture(m) {
      const part = partOf(m.key);
      if (!Number.isInteger(m.px) || m.px < MIN_PICTURE_PX || m.px > MAX_PICTURE_PX) {
        throw new PageFault(`px must be a whole number from ${MIN_PICTURE_PX} to ${MAX_PICTURE_PX}, not ${JSON.stringify(m.px)}`);
      }
      if (!Number.isInteger(m.colour) || m.colour < 0 || m.colour > 0xffffff) {
        throw new PageFault(`colour must be a whole number from 0 to 0xffffff, not ${JSON.stringify(m.colour)}`);
      }
      const picture = drawPicture(part.mesh, { px: m.px, colour: m.colour });
      return [picture, [picture.pixels.buffer]];
    },
    forget(m) {
      parts.delete(m.key);
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
