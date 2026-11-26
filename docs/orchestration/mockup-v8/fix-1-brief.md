# Brief: fix round 1 of mockup version 8

- **Deliverable (REQUIRED):** every finding of [review-1.md](review-1.md) fixed or
  answered, `DECISIONS.md` kept true, and `docs/orchestration/mockup-v8/fix-1.md` saying
  for each finding what you did, in a line.
- **Stop condition (REQUIRED):** each fix checked in the browser at the width and state
  the review names, plus a walk of every step at 320, 480 and 800 px with no console
  error; S1's three ways in each pressed through to the end (the remedy buttons pressed,
  not only the error shown); screenshots of the fixed states saved as
  `screenshots/fix-*.png`.
- **Budget (REQUIRED):** 90 minutes; no cloud spend.

## Rulings

- **S1:** fix as the review proposes, both parts: an instance parked beside the plate
  stays turned as `fitTurn` would turn it; an instance longer or wider than the plate
  takes as it is turned gets a message with both figures in millimetres (the part's own
  units in brackets when they are inches, as decision 54 says) and one button, **Turn it
  to fit**, which turns it and arranges again; the "not fully on the plate" error offers
  that button in place of Arrange for such an instance. Arrange itself still never turns.
- **M1:** two parts. (a) Record in decision 33 what the review measured, and two
  requirements for the implementation: a frame budget for the layer preview on a machine
  without a graphics card, and a view that draws again after a lost WebGL context.
  (b) Try the review's cull (below the current layer, draw only what can be seen; keep
  inner walls and infill for the current layer and a few under it). Keep it only if
  renders before and after, at the review's five layer counts on its two plates, look
  the same to you; say what you saw and the new frame times.
- **M2, M3, M4:** fix as the review proposes. For M3 the line width comes from the
  sliced settings.
- **Low findings:** fix them all as the review proposes. L2: name the Layout view's line
  in the glossary (a status line of the view, not a tooltip) and leave its look alone;
  the owner will be asked whether it should be larger.

Do not change anything the review did not raise.

## Walk and rules

As in [the builder's brief](brief.md). Work only in this checkout
(`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-checkout`),
never in `/repos/popcornpenguins/penguin-slicer`. Commit on `mockup/v8`; do not push.
Scratch folder:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v8-fix/`.
No `rm` on paths built from variables, no `cd … &&` chains, no `eval` or `sh -c`; edit
files with the Edit and Write tools only.
