# Fix round 1 of wizard mockup version 8

Against [review 1](review-1.md), following [the fix brief](fix-1-brief.md). Done Thu
2026-11-26, 11:15 to 11:50 PST. Every finding is fixed or answered;
[DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) says the result (decisions 3, 13,
26, 33, 57, 63, 64, the Terms and "What changed in version 8").

| Finding | What was done |
|---|---|
| S1 | An instance a lay-down leaves beside the plate now waits turned as `fitTurn` turns it, so "press Arrange to make room" is true. An instance longer or wider than the plate takes as it is turned gets "Shooter Hood Rib #1 is 352.7 mm (13.885 in) from left to right as it is turned; the plate takes 334 mm." and one button, **Turn it to fit** (turns it, arranges again); the "not fully on the plate" error offers it in place of Arrange; Arrange's own message no longer counts such an instance. Arrange still never turns. |
| M1 (a) | Decision 33 records the review's measurements, this round's, and the two requirements: a frame budget on software WebGL at the largest plate, and views that draw again after a lost WebGL context. |
| M1 (b) | The cull was tried and **not kept**: the renders differ (see below). |
| M2 | Walls are shaded by darkening only, `#2b5c9e` facing the light to `#1c3d68` facing away; least CIEDE2000 difference over the range 20.3 in all four kinds of vision (recomputed with the review's script), contrast at least 6.1:1. |
| M3 | Lines take the width of the sliced settings' `line_width` (0.62 mm); decision 33 says so. |
| M4 | Three rules in `showTip`: a tooltip repeating the element's visible text shows only when that text is cut short; a step pill or circle whose name shows has none; showing at once on focus only for elements with no visible text, so menus and fields show it on hover only. |
| L1 | The Preview view's `title` is gone; the sentence is behind a "?" icon beside Reset view; "What changed in version 8" corrected. |
| L2 | The Layout view's line is the **pointer line** in the Terms, used in decisions 54, 61, 62 and the version 7 notes; its look is unchanged. Whether it should be larger is the owner's to say. |
| L3 | Only opening a section in the accordion makes it the rail's section. |
| L4 | `aria-describedby` is set only where `adoptTitle` gave a description; the key's list is named "Colour key". |
| L5 | `wizard.js` header says version 8; `bestArrange` no longer counts `turned`. |

## Checked in the browser

Headed Chrome on software WebGL (SwiftShader) via `playwright-cli`, the folder served on a
scratch port.

- **S1, each way pressed through to the end at 320, 480 and 800 px.** Way 1 (armed "Instance
  too tall", its Auto-orient): the rib waits beside the plate at 45°; the error's Arrange
  then places all 3 instances, Next on. Way 2 (parts arrive as modelled, rib among them):
  the same. Way 3 (rib squared with Shift and the rotation handle): the error says 352.7 mm
  from front to back, the plate takes 314 mm, button Turn it to fit; pressed, the rib turns
  and "All 2 instances fit the plate", Next on. At 800 px the scripted Shift drag did not
  square the rib (the drag's angle), so the squared rib was also set by code and the
  toolbar's Arrange pressed: it waits beside the plate with its own card and Turn it to fit,
  which puts it on the plate, at every width.
- **M4** at each width: the current step and the pills from 480 px show no tooltip; a
  circle below 480 px does, on hover and at once on Tab, with no `aria-describedby`; a part
  name, no tooltip; Tab onto and arrow keys on a quick-change menu, no tooltip; hover on
  it, the tooltip; the status line's tooltip at 320 px (cut short), none at 480 and 800.
- **L1:** no `title` left in the panel but menu options; the "?" opens above the row, inside
  the panel at each width, and closes on Escape (focus back on it), a click elsewhere and
  leaving the step. **L3:** Strength closed at 320 px, widened: the rail shows Quality;
  opened, widened: Strength.
- **Walk of every step** at 320, 480 and 800 px (four instances): nothing scrolls sideways.
  Two runs out of three logged Chrome's WebGL warnings of a lost context (the M1 limit:
  frames of 10 to 18 s); the third run had no console error or warning. The same walk on
  the unchanged commit `b20c4af`, once, had none; its frames measure the same (about 10 s,
  some 16 to 18 s), so the loss is the same edge, not new. No JavaScript error in any run.

## M1 (b): the cull, what I saw

Renders without and with the cull (inner walls and infill drawn only for the current
layer and the 16 under it) of a Gusset Plate with an L Bracket, 134 layers, at layers 1, 4,
68, 131 and 134, 800 px
([sheet: left without, right with](screenshots/fix-m1-cull-tried-800-gusset-and-bracket.png)).
Layers 1 and 4: identical (0 pixels differ). Layers 68, 131 and 134: 4.4% of the pixels
differ; the holes read smaller, the walls round them thinner, and the background shows
through in white slivers along the front edges, where the inner walls fill in behind the
one-line outer wall. Frame time with the cull: 1.4 to 2.7 s against about 5.6 s without.
Since one plate already did not look the same, the second plate was not rendered, and the
cull was taken out.

## Screenshots

In [screenshots/](screenshots/), named `fix-…`: S1 at each step of ways 1 and 3 and the
card beside the plate at 320 and 800 px, M2's walls beside supports, M3's top surface close
up, M4's focused menu with the label below it uncovered, L1's "?" at 320 and 800 px, L3's
rail at 480 px, and the M1 sheet.

## Left

- The layer preview's cost on software WebGL (M1) is recorded, not reduced; the owner's Mac
  was not measured.
- L2: whether the pointer line should be larger needs the owner's word.
- The reading of "each setting" as each group (decision 13) still needs the owner's nod,
  as the review said.
