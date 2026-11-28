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

// A notification's close button.
export const CLOSE_NOTIFICATION = 'Close this notification';
