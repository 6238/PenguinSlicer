// The Layout step's sentences (wizard/README.md, "The Layout step"; wizard/README-details.md,
// "The Layout step"): every sentence on this step is the wizard's own, since everything here
// happens in the browser. Kept apart from sentences.js so that the step's words are in one
// place. Instances are named as the guide names them: the part's name and a number, counted as
// the slice service counts them ("L Bracket #2").
import { formatSize } from './units.js';

const MM_PER_INCH = 25.4;
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const joinWords = (words) => (words.length <= 1 ? words.join('') : `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`);

// A printer or plate figure: millimetres to the whole millimetre ("340 mm"), or to 0.1 mm for a
// distance between instances ("6.2 mm"); never in inches (decision 55).
export const mm = (v) => `${Math.round(v)} mm`;
export const mmTenth = (v) => `${Number(v.toFixed(1))} mm`;
// A part's figure set against a printer's: both in millimetres, the part's inches in brackets
// when the part is in inches (decision 54): "352.7 mm (13.885 in)".
export const against = (v, units) => (units === 'in' ? `${mmTenth(v)} (${(v / MM_PER_INCH).toFixed(3)} in)` : mmTenth(v));
// A length in the part's own units (decision 52): "0.250 in", "6.4 mm".
export const ownLength = (v, units) => formatSize([v], units);

// ---- the toolbar and its help
export const ARRANGE = 'Arrange';
export const ARRANGE_TIP = 'Place every instance on the plate automatically';
export const AUTO_ORIENT = 'Auto-orient';
export const AUTO_ORIENT_TIP = 'Lay the selected instances, or every instance when none is selected, the best way';
export const HELP = 'How to move instances and the view';
export const GESTURES = 'Drag an instance to move it, its round handle to turn it. Right-drag to look around, Shift-drag to slide, scroll to zoom. '
  + 'Select an instance: its faces show as pale blue patches; click one to lay it on that face.';
export const MORE_GESTURES = [
  'Left-drag on empty plate also looks around; middle-drag, Ctrl + right-drag or Shift-drag slides the view.',
  'Shift- or Ctrl-click adds an instance to the selection; drag one to move them all.',
  'Hold Shift while turning to turn in 45° steps.',
  'Double-click a flat face to lay the instance down on it.',
  'F zooms to the instances; Ctrl+1 looks from above; Ctrl+A selects every instance; Escape clears the selection.',
];

// ---- the view's buttons and the pointer line
export const VIEW_FIT = 'Zoom to instances';
export const VIEW_FIT_TIP = 'Zoom to the instances (F)';
export const VIEW_PLATE = 'Whole plate';
export const VIEW_PLATE_TIP = 'Show the whole plate';
export const VIEW_TOP = 'Top';
export const VIEW_TOP_TIP = 'Look straight down (Ctrl+1)';
export const POINTER_HANDLE = 'Drag to turn · Shift: 45° steps';
export const POINTER_PATCH = (kind, height, units) => `Lay it on this ${kind === 'box' ? 'side' : 'face'}: ${ownLength(height, units)} tall`;
// The readout beside the rotation handle: the first selected instance's orientation on the
// plate, ↺ anticlockwise and ↻ clockwise seen from above.
export function turnReadout(deg) {
  let d = Math.round(deg) % 360;
  if (d > 180) d -= 360;
  if (d <= -180) d += 360;
  if (d === 0) return '0°';
  return `${d > 0 ? '↺' : '↻'} ${Math.abs(d)}°`;
}

// ---- the status line
export const ALL_FIT = (n, onlyName) => (n === 1 ? `✓ ${onlyName} fits the plate.` : `✓ All ${n} instances fit the plate.`);
export const NO_INSTANCES = 'No instances yet: add parts on the Parts step.';
export const MORE = (n) => `+${n} more ↓`;
export const FIX = 'Fix ↓';
export const DO_NOT_FIT = (n) => `${plural(n, 'instance does', 'instances do')} not fit on the plate.`;

// ---- the selection line, its link and the figures line
export const ON_PLATE = (onPlate, beside) => `${plural(onPlate, 'instance', 'instances')} on the plate${beside ? `, ${beside} beside it.` : '.'}`;
export const FOOTPRINT = (size, height, units) => ` ${formatSize(size, units)}, ${ownLength(height, units)} tall`;
export const TOGETHER = (n) => `${n} instances`;
export const TOGETHER_REST = ' move and turn together';
export const LAY_BEST = 'Lay it the best way';
export const PUT_BACK = 'Put back as modelled';
export const FIGURES = (printer, width, depth, height, spacing) => `${printer}: plate ${Math.round(width)} × ${Math.round(depth)} mm, up to ${mm(height)} tall, ${mm(spacing)} apart`;

// ---- the messages
export const FIX_THESE = (n) => (n === 1 ? 'Fix this before Next:' : `Fix these ${n} before Next:`);
const supportsWord = (on) => `with supports ${on ? 'on' : 'off'}`;

export const TOO_CLOSE_TWO = (a, b, distance, spacing, supports) => ({
  what: `${a} and ${b} are ${mmTenth(distance)} apart; instances need ${mm(spacing)} between them ${supportsWord(supports)}.`,
  todo: 'Drag one away, or press Arrange.',
});
export const TOO_CLOSE_MANY = (n, spacing, supports) => ({
  what: `${n} instances are closer than ${mm(spacing)} ${supportsWord(supports)}.`,
  todo: 'Press Arrange, or drag them apart.',
});
export const OFF_PLATE = (name, edges) => ({
  what: `${name} is not fully on the plate: it crosses the ${joinWords(edges)} edge${edges.length === 1 ? '' : 's'}.`,
  todo: 'Drag it inward, or press Arrange.',
});
// An instance longer or wider than the plate takes as it is turned. `onPlate`: it still
// stands on the plate. `turns`: some turn makes it fit.
export function TOO_LONG(name, way, length, units, takes, onPlate, turns) {
  const across = way === 'x' ? 'from left to right' : 'from front to back';
  const first = onPlate
    ? `${name} is not fully on the plate: it is ${against(length, units)} ${across} as it is turned; the plate takes ${mm(takes)}.`
    : `${name} is ${against(length, units)} ${across} as it is turned; the plate takes ${mm(takes)}.`;
  return { what: first, todo: turns ? 'Turn it to fit turns it and arranges the plate again.' : 'Lay it down another way.' };
}
export const TOO_TALL = (name, height, units, limit) => ({
  what: `${name} stands ${against(height, units)} tall; the printer prints up to ${mm(limit)}.`,
  todo: 'Lay it down another way, or press Auto-orient.',
});
// An instance beside the plate that no message of a move or of Arrange accounts for (a part that
// joined a full plate, or a page opened again): the wizard's own words.
export const WAITS_BESIDE = (name) => ({
  what: `${name} waits beside the plate: no spot on the plate is free for it.`,
  todo: 'Press Arrange to make room, or lower the quantities and print the rest on a new plate.',
});
export const TURN_TO_FIT = 'Turn it to fit';

// After a lay-down (decision 26).
export const MOVED_ONE = (name) => `${name} no longer fitted where it stood, so it was moved to the nearest free spot.`;
export const MOVED_MANY = (n) => `${n} instances no longer fitted where they stood and moved to the nearest free spots.`;
export const BESIDE_ONE = (name) => `${name} no longer fits on the plate and waits beside it.`;
export const BESIDE_MANY = (n) => `${n} instances no longer fit on the plate and wait beside it.`;
export const BESIDE_TODO = (n) => `No spot on the plate is free for ${n === 1 ? 'it' : 'them'} lying this way. The other instances stay where you put them; press Arrange to make room.`;

// Arrange and Auto-orient (decisions 59 and 64).
export const ARRANGED = (n) => `Arranged ${plural(n, 'instance', 'instances')}.`;
export const ARRANGED_AGAIN = 'Arranged the plate again to make room.';
export const ARRANGE_PARTIAL = (placed, parked) => `Arrange placed ${placed} of ${placed + parked} instances; ${plural(parked, 'instance does', 'instances do')} not fit and ${parked === 1 ? 'waits' : 'wait'} beside the plate.`;
export const ARRANGE_PARTIAL_OFFER = (changed, allFit) => `Arrange keeps how each instance lies. With ${plural(changed, 'instance', 'instances')} laid the best way, ${allFit ? 'everything would fit' : 'more would fit'}. Or lower the quantities and print the rest on a new plate.`;
export const ARRANGE_PARTIAL_TODO = 'Lower the quantities and print the rest on a new plate, or turn or lay instances another way to make room.';
export const LAY_THEM_BEST = (allFit, more) => `Lay them the best way: ${allFit ? 'all fit' : `${more} more fit`}`;
export const BACK_TO_PARTS = 'Back to Parts';
export const LAID_BEST_AND_ARRANGED = (n, placed, all) => `Laid ${plural(n, 'instance', 'instances')} the best way and arranged again: ${all ? 'every instance now fits.' : `${plural(placed, 'instance fits', 'instances fit')} now.`}`;
export const TURNED_AND_ARRANGED = (what, placed) => `Turned ${what} and arranged ${plural(placed, 'instance', 'instances')}.`;
export const INSTANCES = (n) => plural(n, 'instance', 'instances');
