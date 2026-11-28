// The trial's worker: fetches the sliced file, reads its G-code into segments, has the method
// prepare its buffers, and places the ghost of each instance from the plate configuration and
// its parts. The page's main thread only uploads what comes back.
import { readZipEntry, parseGcode } from './gcode.js';
import { readStl, ghostOf } from './prepare.js';
import * as methods from './methods-prepare.js';

const PART_URL = (stl) => (stl === 'hex-spacer.stl' ? `/parts/${stl}` : `/parts/real/${stl}`);

async function bytesOf(url) {
  const answer = await fetch(url);
  if (!answer.ok) throw new Error(`${url} answered HTTP ${answer.status}.`);
  return answer.arrayBuffer();
}

self.onmessage = async ({ data }) => {
  const { plate, method, options } = data;
  try {
    const t0 = performance.now();
    const archive = new Uint8Array(await bytesOf(`/sliced/${plate}.gcode.3mf`));
    const tFetched = performance.now();
    const gcode = await readZipEntry(archive, 'Metadata/plate_1.gcode');
    const tUnzipped = performance.now();
    const p = parseGcode(gcode, options.parse || {});
    const tParsed = performance.now();
    const prepared = methods[method](p, options, () => parseGcode(gcode, { arcTolerance: 0.1, mergeTolerance: 0.05 }));
    const tPrepared = performance.now();
    const plateConfiguration = JSON.parse(new TextDecoder().decode(await bytesOf(`/plates/${plate}.json`)));
    const corners = {};
    for (const part of Object.values(plateConfiguration.parts)) corners[part.stl] = readStl(await bytesOf(PART_URL(part.stl)));
    const ghost = ghostOf(plateConfiguration, corners);
    const tGhost = performance.now();
    const transfer = [ghost.corners.buffer, ...prepared.transfer];
    self.postMessage({
      ok: true, prepared: prepared.data, ghost: ghost.corners, bounds: ghost.bounds,
      layers: p.layers, layerZ: p.layerZ, layerHeight: p.layerHeight, layerStart: p.layerStart,
      stats: { sliced_file_bytes: archive.byteLength, sliced_file_lines: p.lines, moves: p.moves, segments: p.count,
        instances: plateConfiguration.instances.length,
        worker_ms: { fetch: tFetched - t0, unzip: tUnzipped - tFetched, parse: tParsed - tUnzipped,
          prepare: tPrepared - tParsed, ghost: tGhost - tPrepared } },
    }, transfer);
  } catch (error) {
    self.postMessage({ ok: false, error: String(error && error.message || error) });
  }
};
