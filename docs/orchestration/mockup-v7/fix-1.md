# Fix round 1 of wizard mockup version 7

Every finding of [review 1](review-1.md) is fixed or answered, as
[the fix brief](fix-1-brief.md) rules. [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md)
is updated where a fix changes what it says (decisions 3, 4, 37, 46, 54, 55, 62, the
version 7 summary, the Layout step's messages and the glossary's "notification").

## Each finding

| Finding | What was done |
|---|---|
| M1 | The too-tall error gives the instance's height in millimetres, with its own units in brackets when they are inches: "Shooter Hood Rib #1 stands 352.7 mm (13.885 in) tall; the printer prints up to 340 mm." (`js/plate.js`). It is the only message that sets a part's figure against a printer's. Decisions 54 and 55 updated. |
| M2 | Shift snaps the first selected instance's orientation on the plate to multiples of 45°; the others in the selection turn by the same angle. The orientation is the angle about the vertical between the instance and the same face-down position reached straight from the part as modelled. The readout beside the handle shows that orientation, so it reads "↺ 45°" when the instance is at 45° (`js/layout3d.js`). Decision 62 updated. |
| M3 | "Sending cancelled …" goes when the plate is sent again; "Back where you were … its progress is below" goes when this user's print ends, finished or failed (`js/wizard.js`). The other Send-step notifications were checked: none is left saying something false. |
| L1 | `applyTurn` and the move drag place the instances' meshes at once, so the handle and the dashed box never lead the instance in a drawn frame. |
| L2 | Not changed, as ruled: the Shooter Hood Rib's patches stay for the owner's open question M29. |
| L3 | Below 480 px the focus ring goes round the step circle alone (`css/panel.css`). |
| L4 | Arming "3a. Instances too close" picks a pair that is too close but not touching, weighs heavily against any overlap, and zooms to the instances afterwards. |
| L5 | The summary's second line is always as tall as the "+1 change" pill: 40.8 px with and without it. |
| L6 | The Layout step's message ("Arranged 5 instances, turning 2.") goes when the user leaves the Layout step. |

## Checked in the browser

A headed Chrome with WebGL (playwright-cli session `mockup-v7-fix`, its own Xvfb
display), the folder served on port 8774, on Wed 2026-11-25 between 10:02 and 10:16 PST.

- **M1** at 320, 480 and 800 px: the sentence in the red bar, the error and the "Layout
  first: …" line under the step tabs.
- **M2 and L1** at 320, 480 and 800 px on the 1/2in Hex Shaft and a selection of three:
  turned freely by about 15°, then with Shift: the shaft lands on 45° (footprint 5.976 ×
  5.976 in), then 135°; in a selection the first instance snaps and the others turn by the
  same angle. The handle's place in the instance's own frame, read after every frame the
  view drew, moved 0.00 mm in every drag, slow, fast and with Shift. The same reading on the
  unfixed version (commit `5e5e546`, served from a copy) found 1.7 to 27 mm, so the reading
  does catch the lag.
- **M3** at 320, 480 and 800 px: cancel then send again; close and reopen while sending,
  then a finished print and a failed one.
- **L3** at 320 px, **L4, L5, L6** at 320, 480 and 800 px.
- **The walk:** every step, advanced mode, Arrange and a send at 320, 480 and 800 px: no
  sideways scroll, no console error or warning.

One thing seen while checking, not a fault of the mockup: an element screenshot taken by
Playwright in the middle of a drag at 480 px fires a pointer event that turns the instance
again. The turn checks were rerun at 480 px without screenshots in the drag, and the
screenshots kept are of the correct state.

## Screenshots

In [screenshots/](screenshots/), named `fix-<finding>-<what>-<width>.png`: M1, M2, M3 (a
and b), L1, L4, L5 and L6 at 320, 480 and 800 px; L3 at 320 px.
