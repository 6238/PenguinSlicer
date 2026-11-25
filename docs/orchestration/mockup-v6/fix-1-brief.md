# Brief: fix round 1 of mockup version 6

- **Deliverable (REQUIRED):** every finding of [review-1.md](review-1.md) fixed or
  answered, `DECISIONS.md` kept true, and `docs/orchestration/mockup-v6/fix-1.md` saying
  for each finding what you did, in a line.
- **Stop condition (REQUIRED):** each fix checked in the browser at the width and state
  the review names, plus a walk of every step at 320, 480 and 800 px with no console
  error; screenshots of the fixed states saved as `screenshots/fix-*.png`.
- **Budget (REQUIRED):** 90 minutes; no cloud spend.

## Rulings

- **F1:** after "Turn on Supports", run the placement check at 12 mm before slicing. If
  any instances are now too close, do not slice: take the user to Layout, where the usual
  message shows, and nothing moves on its own (the owner's rule: other instances never
  move by themselves; Arrange is the user's choice).
- **F2:** the switches happen at 480 px inclusive, so the strip's 480 px shows the wide
  layout. Check every width breakpoint the same way.
- **F3, F4:** fix as the review proposes: sizes never cut (wrap or shorten the line,
  never ellipsis), and inches converted from the unrounded millimetres, so one part has
  one size everywhere.
- **F5:** the owner's rule is little help text on working screens, and the Layout step
  has not been reviewed yet. Move the gestures paragraph behind a small help icon with a
  tooltip or a popover, keep "More ways to move and look" only if it is a control rather
  than text, and drop the plate line if the printer-status icon or the chips already say
  it. Record what you did in `DECISIONS.md` for the owner's Layout review.
- **F6:** one error for all instances that are too close: how many, and one Arrange
  button. Instances stay marked in the view.
- **F7:** a click on a step that Layout blocks says why, in one line, where the user
  looks.
- **F8:** keep focus where the user acted in advanced mode; covered controls are not
  reachable (use `inert` or equivalent).
- **F9:** on the standalone page, no mention of Onshape or a Part Studio; say what to
  check in the user's CAD program in general words.
- **Low findings:** fix every factual error, accessibility fault or inconsistency. For
  taste, use your judgment, staying inside the owner's preferences, and say what you
  chose.

Do not change anything the review did not raise.

## Walk and rules

As in [the builder's brief](brief.md): serve the folder on a free port other than 6238
and 6249, `playwright-cli`, the WebGL note, stop everything you start, remove
`.playwright-cli/`. Read [the standing rules](../review-feedback/briefs/standing-rules.md).
Commit on `mockup/v6`; do not push. Scratch folder:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v6-fix/`.
