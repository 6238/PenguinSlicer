// A part's picture on its row of the Parts step (decision 18), drawn by the worker
// (geometry/picture.js) and put on the page as a canvas, which the mockup's style sheet sizes to
// PICTURE_CSS_PX as `.part-item .thumb`. The picture is drawn at the screen's density, so it is
// sharp on a dense screen, up to three times, beyond which a 44 px picture gains nothing.
import { PART_COLOURS, PICTURE_CSS_PX } from './page-constants.js';

const MAX_DENSITY = 3;

export function picturePx(pixelRatio) {
  const ratio = Number.isFinite(pixelRatio) ? Math.min(MAX_DENSITY, Math.max(1, pixelRatio)) : 1;
  return Math.round(PICTURE_CSS_PX * ratio);
}

// The colour of the part in place `index` of the plate, the mockup's colours in turn.
export const partColour = (index) => PART_COLOURS[index % PART_COLOURS.length];

// partPicture({geometry, key, colour, pixelRatio, document}) resolves to {ok: true, canvas} with
// the picture of the part read under `key`, or to {ok: false, error}, the worker's error report.
export async function partPicture({ geometry, key, colour, pixelRatio, document }) {
  const answer = await geometry.picture(key, picturePx(pixelRatio), colour);
  if (!answer.ok) return answer;
  const { width, height, pixels } = answer.result;
  const canvas = document.createElement('canvas');
  canvas.className = 'thumb';
  canvas.width = width;
  canvas.height = height;
  canvas.setAttribute('aria-hidden', 'true');
  canvas.getContext('2d').putImageData(new ImageData(pixels, width, height), 0, 0);
  return { ok: true, canvas };
}
