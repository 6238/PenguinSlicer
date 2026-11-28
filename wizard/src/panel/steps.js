// The five steps, in order, and the rule for a click on a step tab (decision 3): it goes to the
// step when every step before it allows it; when one does not, the panel line names that step
// and why ("Layout first: 23 instances are closer than 12 mm with supports on."). Going back,
// or to the step the user is on, is never held.
import { STEP_FIRST } from '../sentences.js';

export const STEPS = [
  { id: 'parts', name: 'Parts' },
  { id: 'settings', name: 'Settings' },
  { id: 'layout', name: 'Layout' },
  { id: 'preview', name: 'Preview' },
  { id: 'send', name: 'Send' },
];

export const stepIndex = (id) => STEPS.findIndex((s) => s.id === id);

// The step that holds a move from `current` to `target`, as {step, text}, or null when the
// move is allowed. `why(step)` is the step's own reason it cannot be left, or null.
export function heldBy(target, current, why) {
  const from = stepIndex(current);
  const to = stepIndex(target);
  for (let i = from; i < to; i += 1) {
    const reason = why(STEPS[i].id);
    if (reason) return { step: STEPS[i].id, text: STEP_FIRST(STEPS[i].name, reason) };
  }
  return null;
}
