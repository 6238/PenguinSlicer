// The faces the wizard offers to lay each real part on, written as poses for the slice
// service's real-Orca suite, which slices each one as the oracle of the faces offered
// (wizard/README-details.md, "The faces offered, against the real Orca"). Run by
// `make -C wizard offered-faces`, which writes contracts/examples/placement/offered-faces/
// real-parts.json; the wizard's fast suite fails when the committed file differs from what
// this writes.
//
// One pose for each patch of each part, in the order the worker gives the patches: the part
// laid on that patch from as modelled, as a click on the patch lays it, with `angle` 0, carried
// as the plate configuration's phase 2 instance carries it, at the plate's middle.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { autoOrient } from '../src/geometry/orient.js';
import { analysePart } from '../src/geometry/part.js';
import { readBinaryStl } from '../src/geometry/stl.js';
import { instanceTurn, layFor } from '../src/geometry/turn.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTRACTS = join(HERE, '..', '..', 'contracts');
const REAL_PARTS = join(CONTRACTS, 'examples', 'parts', 'real');
export const OFFERED_FACES_FILE = join(CONTRACTS, 'examples', 'placement', 'offered-faces', 'real-parts.json');

// The eight real parts, by the file name under contracts/examples/parts/real/ and the name
// they were exported under (that folder's README.md).
export const REAL = [
  ['clamp-plate-inner', 'Clamp Plate Inner'],
  ['elevator-block-bottom-inner', 'Elevator Block Bottom Inner'],
  ['elevator-block-carriage', 'Elevator Block Carriage'],
  ['elevator-block-top', 'Elevator Block Top'],
  ['elevator-top-inner', 'Elevator Top Inner'],
  ['inner-spacer', 'Inner Spacer'],
  ['outer-clamp', 'Outer Clamp'],
  ['pulley-v3', 'Pulley v3'],
];

// The middle of the default set's printer, the H2S (x 0 to 340 mm, y 0 to 320 mm).
const PLATE_MIDDLE = [170, 160];

const round = (v, places) => {
  const r = Math.round(v * 10 ** places) / 10 ** places;
  return Object.is(r, -0) ? 0 : r;
};

// Ranks from 1 by `value`, larger first when `descending`; a tie goes to the earlier patch.
function ranks(values, descending) {
  const order = values.map((v, i) => i).sort((a, b) => (descending ? values[b] - values[a] : values[a] - values[b]) || a - b);
  const out = new Array(values.length);
  order.forEach((i, r) => { out[i] = r + 1; });
  return out;
}

export function offeredFaces() {
  const parts = {};
  const poses = [];
  for (const [key, name] of REAL) {
    const bytes = readFileSync(join(REAL_PARTS, `${key}.stl`));
    parts[key] = { name, sha256: createHash('sha256').update(bytes).digest('hex'), units: 'mm' };
    const part = analysePart(readBinaryStl(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), 'mm'));
    const choice = autoOrient(part);
    const costs = new Map(choice.candidates.filter((c) => c.patch >= 0).map((c) => [c.patch, c.cost]));
    const byCost = ranks(part.patches.map((_, i) => costs.get(i)), false);
    const byArea = ranks(part.patches.map((p) => p.area), true);
    part.patches.forEach((patch, index) => {
      const turn = instanceTurn(layFor(patch.normal), 0);
      poses.push({
        id: `${key}-${index}`,
        patch: {
          index, kind: patch.kind,
          ...(patch.kind === 'box' ? { side: patch.side } : {}),
          normal: patch.normal.map((v) => round(v, 6)),
          area_mm2: round(patch.area, 2),
        },
        area_rank: byArea[index],
        orient_rank: byCost[index],
        chosen: choice.patch === index,
        instance: { ref: key, ...turn, x: PLATE_MIDDLE[0], y: PLATE_MIDDLE[1] },
      });
    });
  }
  return {
    description: 'Every face the wizard offers to lay each real part on, as one pose each: the part '
      + 'laid on the patch from as modelled, as the plate configuration carries the turn, at the '
      + "plate's middle. Written by make -C wizard offered-faces; sliced one by one by the slice "
      + "service's real-Orca suite, each must slice.",
    parts,
    poses,
  };
}

// The file's text: two spaces of indent, each pose's short arrays kept on one line.
export function offeredFacesText(data = offeredFaces()) {
  return `${JSON.stringify(data, (k, v) => v, 2).replace(/\[\s+([-\d.,\s]+?)\s+\]/g, (_, inner) => `[${inner.split(/,\s*/).join(', ')}]`)}\n`;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const data = offeredFaces();
  writeFileSync(OFFERED_FACES_FILE, offeredFacesText(data));
  console.log(`${data.poses.length} poses of ${Object.keys(data.parts).length} parts written to ${OFFERED_FACES_FILE}`);
}
