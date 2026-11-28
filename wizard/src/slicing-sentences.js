// The Preview step's own sentences while a plate is submitted and sliced (wizard/README-details.md,
// "The slicing card", "No room to wait", "When a slice fails"): the states that are not failures,
// which the wizard puts into words from the figures it is sent, its buttons, and the page's own
// failures there. Every other failure is an error report whose sentences are shown as they are.

// The slicing card.
export const SLICING_GOES_ON = 'Slicing goes on if you step back; change the plate and it starts again.';
export const WAITING_AHEAD = (ahead) => `Waiting for the slicer: ${ahead} slice${ahead === 1 ? '' : 's'} ahead of yours.`;
export const WAITING = 'Waiting for the slicer';
// proposed in the details: the slice service is stopping, as at a deploy
export const RESTARTING = 'The slicer is restarting; your plate will start when it is back.';
export const ELAPSED = 'elapsed';
export const WAITED = 'waited';
export const ABOUT_LEFT = (time) => `about ${time} left`;
export const FINISHING = 'finishing';
export const LONGER_THAN = (time) => `taking longer than the expected ${time}`;
export const NO_NEWS_SINCE = (time) => `no news since ${time}`;
export const LAST_HEARD = (stage) => `${stage} (last heard)`;
export const RECONNECTED = (time) => `Reconnected at ${time}. The slice kept running; the progress below is up to date.`;
export const SLICER_RESTARTED = 'The slicer restarted, so this slice began again.';

// No room to wait: the wizard's own line beside the slice service's sentences.
export const PLATE_UNCHANGED = 'Your plate is unchanged.';

// The buttons of a failed slice.
export const SUPPORTS_AND_SLICE = 'Turn on Supports and slice again';
export const SLICE_AGAIN = 'Slice again';
export const BACK_TO = { layout: 'Back to Layout', parts: 'Back to Parts', settings: 'Back to Settings' };
export const ORCA_SAYS = (sentence) => `Orca Slicer: ${sentence}`;

// On the Layout step, above its usual message, when Turn on Supports and slice again finds the
// plate too close together for supports.
export const NOT_SLICED_SUPPORTS = (mm) => `Not sliced: with Supports on, instances need ${mm} mm between them.`;

// The placeholder where the result and the layer preview will be, until they are built.
export const SLICED_PLACEHOLDER = 'The plate is sliced. Its print time, filament and layer preview will show here.';

// The page's own failures on the Preview step.
export function plateConfigurationOverSize(bytes, cap) {
  return {
    code: 'wizard.plate_configuration_over_size',
    message: `This plate's description is ${bytes.toLocaleString('en-US')} bytes, more than the ${cap.toLocaleString('en-US')} bytes one slice may send.`,
    remedy: 'Remove some instances, or move some of them to a new plate, and slice again.',
    retryable: false,
    detail: `plate configuration ${bytes} bytes, cap ${cap}`,
  };
}

export function plateNotReady(detail) {
  return {
    code: 'wizard.plate_not_ready',
    message: 'This plate cannot be sliced: its filament or profile is not one the configuration offers.',
    remedy: 'Choose the filament and the profile on the Settings step, and slice again.',
    retryable: false,
    detail,
  };
}
