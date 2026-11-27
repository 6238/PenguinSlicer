# Brief: fix round 1 of mockup version 7

- **Deliverable (REQUIRED):** every finding of [review-1.md](review-1.md) fixed or
  answered, `DECISIONS.md` kept true, and `docs/orchestration/mockup-v7/fix-1.md` saying
  for each finding what you did, in a line.
- **Stop condition (REQUIRED):** each fix checked in the browser at the width and state
  the review names, plus a walk of every step at 320, 480 and 800 px with no console
  error; screenshots of the fixed states saved as `screenshots/fix-*.png`.
- **Budget (REQUIRED):** 60 minutes; no cloud spend.

## Rulings

- **M1 (too tall, inches beside millimetres):** the owner's rule is that printer and
  plate figures are always in millimetres. A comparison is made in one unit: say the
  instance's height in millimetres, with its own units in brackets when they are inches
  ("stands 352.7 mm (13.885 in) tall; the printer prints up to 340 mm"). Apply the same
  to any other message that compares a part figure with a printer figure. Update
  decision 54.
- **M2 (Shift snaps the turn):** Shift snaps the instance's orientation on the plate to
  multiples of 45° (0, 45, 90…), as CAD programs do, not the angle turned since the drag
  began. For a multi-selection, snap the first-selected instance's orientation and turn
  the others by the same angle. Update the decision that records it.
- **M3:** a notification that stops being true goes away: remove each when its state
  ends, and check every other notification on the Send step the same way.
- **Low findings:** fix them all, including L1 with the review's fix. The Shooter Hood
  Rib's patches (M29) stay as they are: that question is open for the owner.

Do not change anything the review did not raise.

## Walk and rules

As in [the builder's brief](brief.md). Work only in this checkout
(`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-checkout`),
never in `/repos/popcornpenguins/penguin-slicer`. Commit on `mockup/v7`; do not push.
Scratch folder:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v7-fix/`.
