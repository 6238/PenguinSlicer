// The wizard's own sentences: the ones no other component writes, because no component
// answered (the server slow or unreachable) or because the failure is the page's own
// (wizard/README-details.md, "Who writes the sentences of a failure"). Every other failure is
// an error report whose sentences the page shows as they are. The geometry's sentences are in
// geometry/errors.js.

// The panel line's lasting use (the guide, "When the server is slow or cannot be reached").
// A no-break space joins the figure to its unit, so a narrow panel never wraps between them.
export const SERVER_SLOW = (seconds) => (seconds > 0
  ? `The server is being slow. Your browser is retrying in ${seconds} s.`
  : 'The server is being slow. Your browser is retrying now.');
export const RETRY_NOW = 'Retry now';
export const SERVER_UNREACHABLE = 'The server could not be reached.';
export const TRY_AGAIN = 'Try again';

// A part's row while its upload is retried, from ROW_SLOW_S.
export const ROW_SLOW = 'Taking longer than usual; still trying…';

// An answer of the front server that the page cannot read: a body that is not JSON where the
// contract says JSON, or a failure whose body is not an error report. A fault of the front
// server, shown as a failure and not retried. Its detail is the path, the status and the first
// BAD_ANSWER_BODY_CHARS characters of the body.
export const BAD_ANSWER_BODY_CHARS = 200;
export function badAnswer(path, status, body) {
  return {
    code: 'wizard.bad_answer',
    message: 'The server gave an answer this page cannot read.',
    remedy: 'Reload the page to try again.',
    retryable: false,
    detail: `${path} answered ${status}: ${String(body).slice(0, BAD_ANSWER_BODY_CHARS)}`,
  };
}

// The panel line's passing use: the step that holds a click on a tab, and why.
export const STEP_FIRST = (stepName, why) => `${stepName} first: ${why}`;

// The plate summary's first line.
export const PARTS_AND_INSTANCES = (parts, instances) =>
  `${parts} part${parts === 1 ? '' : 's'} · ${instances} instance${instances === 1 ? '' : 's'}`;
export const CHANGES_PILL = (count) => `+${count} change${count === 1 ? '' : 's'}`;
export const CHANGES_PILL_TIP = (profile) => `The settings changed from ${profile}`;

// The header's second line.
export const CONFIG = 'Config: ';
export const RELOAD_CONFIGURATION = 'Reload the configuration';

// The notification after the configuration is read again (the reload glyph, or a page opening on
// a stored plate) when the chosen filament or profile is gone from it: which name went, and what
// the plate uses in its place, in the plate summary's words.
export const CONFIG_FILAMENT_GONE = (filament) => `${filament} is no longer in the configuration.`;
export const CONFIG_PROFILE_GONE = (profile, filament) => `${profile} is no longer offered for ${filament}.`;
export const CONFIG_NOW_USES = (filament, profile) => `The plate now uses ${filament} · ${profile}.`;

// A part's row when the browser refused to store the part (What the browser keeps).
export const PART_NOT_SAVED = 'This part could not be saved in this browser, so a refresh will lose it.';

// ---- The Parts step (the guide, "The Parts step", "A part that cannot be used", "The limits on
// a plate"). The upload area, its switch, a row, the line under the list and New plate.
export const UPLOAD_PROMPT = 'Drop STL files here, or click to choose';
export const READ_STL_IN = 'Read STL files in:';
export const UNIT_WORDS = { in: 'inches', mm: 'millimetres' };
export const UPLOADING = 'Uploading…';
export const SIZE_TIP = (units) => `Size as modelled, in ${UNIT_WORDS[units]} (this file was read in ${UNIT_WORDS[units]})`;
export const INSTANCES_OF = (name) => `Instances of ${name}`;
export const REMOVE_PART = (name) => `Remove ${name}`;
export const NO_PARTS = 'No parts yet.';
export const PARTS_LINE = (parts, instances, arriving) =>
  `${parts} part${parts === 1 ? '' : 's'}, ${instances} instance${instances === 1 ? '' : 's'} on one plate${arriving ? `; ${arriving} more arriving.` : '.'}`;
export const NEW_PLATE = 'New plate';
export const NEW_PLATE_QUESTION = 'Start a new plate? The parts and layout of this one are cleared.';
export const KEEP_PLATE = 'Keep this plate';

// What the wizard adds to a refusal's sentences: that the other parts are fine (only while the
// list holds other parts), and, for a file refused as too large, how STL files are being read.
export const OTHER_PARTS_FINE = 'Your other parts are fine.';
export const READ_IN_REMINDER = (units) => `STL files are being read in ${UNIT_WORDS[units]}.`;
// A part's notification names it: the part's name before the sentence of the component that
// refused it, which cannot name it (an upload carries no name).
export const NAMED = (name, sentence) => `${name}: ${sentence}`;

// A part that arrived after the user left the Parts step (decision 23).
export const ARRIVED_LATE = (name) => `${name} arrived after you left the Parts step.`;
export const JOINS_LATER = 'It joins the plate when you go back to the Layout step.';

// The page's own checks before sending, each an error report of the wizard's own: the slice
// service's three limits on a plate (contracts/plate-configuration.md, "Limits").
export function partOverSize(fileName, megabytes, bytes, cap) {
  return {
    code: 'wizard.part_over_size',
    message: `${fileName} is ${megabytes} MB. PenguinSlicer takes parts up to 7.5 MB (150,000 triangles), so it was not added.`,
    remedy: 'Export it again from your CAD program at a coarser resolution.',
    retryable: false,
    detail: `${bytes} bytes, cap ${cap}`,
  };
}
export function tooManyParts(name, cap) {
  return {
    code: 'wizard.too_many_parts',
    message: `A plate takes up to ${cap} different parts, so ${name} was not added.`,
    remedy: 'Remove a part, or print it on a new plate.',
    retryable: false,
    detail: `the plate holds ${cap} different parts`,
  };
}
export function tooManyInstances(count, cap) {
  return {
    code: 'wizard.too_many_instances',
    message: `This plate would hold ${count} instances.`,
    remedy: `Up to ${cap} instances per plate; print the rest on a new plate.`,
    retryable: false,
    detail: `${count} instances, cap ${cap}`,
  };
}

// A notification's close button.
export const CLOSE_NOTIFICATION = 'Close this notification';
