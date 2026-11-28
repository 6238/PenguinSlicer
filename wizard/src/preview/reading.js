// The preview worker's side of its one message, kept apart from the worker's own file so that the
// tests run it in their own thread (wizard/README-details.md, "The layer preview"):
//   prepare  {id, bytes, plate}   reads the sliced file's bytes (an ArrayBuffer) and prepares
//                                 what is drawn; `plate` is {instances, meshes} for the ghost, or
//                                 null for none. Posts {id, progress: {stage, fraction}} on the
//                                 way: unpacking, reading (with how far through the G-code) and
//                                 preparing, `fraction` null where it cannot be known.
// The reply is {id, ok: true, result} or {id, ok: false, error}, the error an error report; the
// result's buffers are listed in `transfer`, so they move to the page without being copied:
//   full, moving   {vertices, layerStart, count}: every segment a box (boxes.js), and the look
//                  while moving, every `decimate`-th layer of a coarser reading
//   ghost          {corners, bounds} (ghost.js)
//   layers, layerZ the number of layers and each layer's height
//   groups         the boxes of each of the four groups
//   stats          {sliced_file_bytes, sliced_file_lines, segments, instances}, for the drawing
//                  summary
import { boxVertices, decimationFor } from './boxes.js';
import { parseGcode, readZipEntry } from './gcode.js';
import { placeInstances } from './ghost.js';
import { PREVIEW_FAILED, PreviewError, errorReport } from './preview-errors.js';

const GCODE = 'Metadata/plate_1.gcode';
// The look while moving reads the G-code again with coarser arcs and merging (the trial's record,
// decision 6): within 0.1 mm and 0.05 mm.
const COARSE = { arcTolerance: 0.1, mergeTolerance: 0.05 };

// `parse` is the reading of the G-code, replaced only by a test that makes it fail.
export function createPreviewReading({ parse = parseGcode } = {}) {
  async function prepare(m, progress) {
    if (!(m.bytes instanceof ArrayBuffer)) throw new PreviewError('bytes must be an ArrayBuffer of the sliced file', PREVIEW_FAILED);
    progress('unpacking', null);
    const gcode = await readZipEntry(new Uint8Array(m.bytes), GCODE);
    const p = parse(gcode, { onProgress: (f) => progress('reading', f) });
    if (!p.layers) throw new PreviewError('The sliced file cannot be drawn: the G-code has no layers (no "; CHANGE_LAYER").');
    if (!p.count) throw new PreviewError(`The sliced file cannot be drawn: the G-code has ${p.layers} layer${p.layers === 1 ? '' : 's'} but no extrusion to draw.`);
    progress('preparing', null);
    const full = boxVertices(p);
    const coarse = parse(gcode, COARSE);
    const decimate = decimationFor(coarse);
    const moving = boxVertices(coarse, { decimate });
    const ghost = placeInstances(m.plate);
    const groups = [0, 0, 0, 0];
    for (let i = 0; i < p.count; i++) groups[p.group[i]]++;
    const result = {
      full, moving, decimate, ghost, layers: p.layers, layerZ: p.layerZ, groups,
      stats: { sliced_file_bytes: m.bytes.byteLength, sliced_file_lines: p.lines, segments: p.count, instances: m.plate ? m.plate.instances.length : 0 },
    };
    const transfer = [full.vertices.buffer, full.layerStart.buffer, moving.vertices.buffer, moving.layerStart.buffer,
      ghost.corners.buffer, ghost.bounds.buffer, p.layerZ.buffer];
    return { result, transfer };
  }

  return {
    // Answers `message`; `post(m)` sends each progress report on its way.
    async handle(message, post) {
      const progress = (stage, fraction) => post({ id: message.id, progress: { stage, fraction } });
      try {
        if (message.op !== 'prepare') throw new PreviewError(`the preview worker has no message ${JSON.stringify(message.op)}`, PREVIEW_FAILED);
        const { result, transfer } = await prepare(message, progress);
        return { reply: { id: message.id, ok: true, result }, transfer };
      } catch (err) {
        const error = err instanceof PreviewError ? err.report : errorReport(PREVIEW_FAILED, `${err.name}: ${err.message}`);
        return { reply: { id: message.id, ok: false, error }, transfer: [] };
      }
    },
  };
}
