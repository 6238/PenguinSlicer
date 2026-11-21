# Review 1: wizard mockup version 5

**Status: DONE_WITH_CONCERNS** (concerns at the end). Fri 2026-11-20, about 22:30 Pacific.
An independent reviewer reviewed version 5 and fixed what it found. The yardsticks were
[the brief](brief.md), [the standing rules](../review-feedback/briefs/standing-rules.md), the
owner's [Orca screenshot](../../reference/orca-lay-on-face/orca-lay-on-face.png) and
[its README](../../reference/orca-lay-on-face/README.md), and the later instruction to remove
the Preview step's breakdown by line type. The reviewer read the builder's
[result](result.md) only after forming its own view, and left it unchanged.

Browser walks: the folder was served on port 8771 and driven with headed Chrome under a
separate Xvfb display with SwiftShader. Every part was walked at 320 and 800 px. The server,
the display and the browser are stopped, and `.playwright-cli/` is removed.

## 1. Licence

The reviewer fetched Orca's `GLGizmoFlatten.cpp`, `GLGizmoBase.cpp` and `Selection.cpp` at
`v2.4.2` into scratch and compared them with `js/hullfaces.js` and
[the note](../../research/2026-11-21-lay-on-face-hull-faces.md).

- **Code and structure:** nothing is copied or translated line by line. The hull in
  `hullfaces.js` is the mockup's own incremental hull; Orca calls a library hull instead.
  The mockup grows a face with an angle test, where Orca compares each normal component by
  component. The patch shrinks towards the centre of area, where Orca shrinks towards the
  average of the corners. The mockup rounds the corners with quarter-point corner cutting,
  where Orca uses ten passes with moving neighbour points and an "aggressivity" weight. The
  mockup adds a neighbour graph and its own rule for round parts. The filters run in Orca's
  order, but that order is part of the method, not of the code.
- **Constant names: changed.** Orca names its constants `minimal_area`, `minimal_side` and
  `minimal_angle`. `hullfaces.js` had `MIN_AREA` and `MIN_SIDE`, the same words, and
  `MIN_CORNER_DEG` and `MAX_FACES` beside them. They are renamed `SMALLEST_FACE_MM2`,
  `SHORTEST_LONE_EDGE_MM`, `SLIVER_CORNER_DEG` and `FACES_OFFERED_CAP`.
- **Comments: one quotation removed.** The note quoted Orca's comment "because of the
  picking pass limitations" word for word. It now says, in its own words, that Orca explains
  the limit by its picking pass.
- **Citation fixed.** The note cited "blended (lines 93-109)" as if those lines were in
  `GLGizmoBase.cpp`, where lines 93-109 are grabber code. The blending is in
  `GLGizmoFlatten.cpp`, lines 93-109. The note now names that file, and it also cites the
  theme override of the patch colours (`GLGizmoBase.cpp`, lines 59-60).
- The other line citations check out against the source: lines 152-163, 166, 169-171,
  173-210, 217-222, 229-257, 260-276, 284-288, 290-327, 330-332, 338-340, 354-366, 384-405,
  `WXK_CONTROL_F` at line 57, and `Selection.cpp` lines 1435-1463. The figures are right:
  5 mm², 1 mm, 1 degree, 254, 10%, 0.1 mm, ten passes, and the colours (0.96, 0.93, 0.93, 0.5)
  and (1, 1, 1, 0.75).

## 2. Lay on face on every part, 320 and 800 px

The walk, for each part and each width: select the instance, then three rounds. A round
moves the pointer to the middle of every patch whose middle is clickable and checks for the
pointer cursor and the "Lay it on this face: N mm tall" tip. Then it clicks a patch and
checks that the instance turned and that the patches were drawn again: the face the instance
now lies on loses its patch and the earlier one gains one. The rounds that were possible all
passed on all seven parts at both widths: 34 clicks, every one of which laid the instance
down. The round parts allow one click each, because only their other end is offered.

**The handle bug: fixed.** The builder saw the spacer at 800 px put the middle of a patch
under the rotation handle. The original screenshots show the same on the L Bracket at
320 px. The handle is drawn over everything and was picked first, so a click there turned
the instance. The fix is in `js/layout3d.js`. The patches are now placed before the handle.
While patches show, `placeHandle` tests whether the handle, or a ring round it 2.2 times its
radius, would cover a patch in sight. If it would, the handle moves round the selection
45 degrees at a time to the first free side, and it is hidden if no side is free; that never
happened on these parts. The student's own handle direction is left unchanged. As a result
a click on a visible patch always lays the instance down, and the handle always turns. The
reviewer checked that a drag that starts on a patch still moves the instance and that a
drag on the handle still turns it.

**Look:** the patches are translucent, rounded, and appear on the hull faces the student can
see, including the faces that bridge a hollow, such as the L Bracket's diagonal face and the
face across the Shooter Hood Rib's inner curve. This matches the owner's screenshot. The
patch under the pointer is a deeper blue. The builder's choice of PenguinCAM's accent blue in
place of Orca's near-white is reasonable. The owner's screenshot is Orca on a dark
background, near-white would vanish on the mockup's pale parts, and decision 49 records the
choice.

Middles that failed the hover check were all outside the visible part of the view, under
the Next button or the header. Those patches are not visible there, so this is not a defect.

## 3. Round parts

The reviewer recounted in the browser: hull faces 7, 98, 7, 98, 7, 45 and 8; offered 7, 2,
7, 2, 7, 5 and 8. On the pulley and the spacer the 96 dropped facets measure 25.9 mm² and
18.3 mm², bend 3.75 degrees, and leave the two end faces. The rib keeps its two sides, its
two ends and its inner-curve face, and loses its 40 outer-edge facets (1.8 degrees apart).
No sliver is offered. The note's figures for the failed rules (1.1%, 4.8% and 9.5%; widths
of 8 mm against 4 mm) match the measured faces.

The rule (a neighbour bending less than 20 degrees that is at least half the size) is
simple and fits the brief. The note describes it truthfully, with one exception, now fixed.
It said a chamfer beside a flat face loses its patch, but a 45-degree chamfer bends too far
to be caught. The note now says that only a shallow facet, under 20 degrees, loses its
patch, and that a 45-degree chamfer keeps its own, as in Orca. The note's list of what the
real wizard needs (runs of facets, coarse round sides, a stability test, several bodies) is
fair.

## 4. The step swap

The reviewer checked the following in the browser at 320 px. The wizard opens on Parts with
Back off and no chips. Setup shows "2 parts · 2 instances". Layout adds PETG and Structural.
Preview adds the area of plate. Send adds the time and the grams. Back from Setup goes to
Parts, and Back from Layout goes to Setup. Refresh page with a finished slice reopens on
Preview with "Back where you were". After Come back 2 h later the wizard opens on Parts with
the notification that the slice expired. With another student printing, Close and reopen
shows "Printing 62%" in the printer-status icon on the Parts step.

Every sentence that names a step agrees with the new order: in `index.html` (the step tabs,
the Layout instruction, the scenario strip's Arm error groups, the how-to), in `wizard.js`
(comments, notifications, Back to Parts / Setup / Layout buttons, Layout's "more ways"
list) and in `DECISIONS.md`. The scenario strip names no step number. "Tab 1" in the Layout
instruction uses the mockup's own term "step tab" (decision 3) and is kept. No change was
needed.

## 5. The Preview breakdown

Gone. The legend lists only the line types' colours and names (Outer wall to Bottom
surface), with no times or shares. The "Heating, travel, layer changes" row is gone, and the
legend's label is now "Line types". A click on a row still hides that line type. The CSS
removed only the legend's unused rules.

## 6. Scope, console, overflow

The diff against `main` touches only the three changes, plus "(recommended)" dropped from
*Pictures under the view*, since that option is no longer the default (recorded in
DECISIONS). The console showed no errors and no warnings across all the walks. At 320 px
neither the panel nor its body overflows on any step (scroll width equals client width). At
800 px the stand-in Onshape page is 16 px wider than the 1050 px window, the same in
version 4, and not part of the panel.

## 7. DECISIONS.md

The "What changed in version 5" section is at the top and is true. M1 lists the five
options, and M18, M19 and decisions 4, 24, 33, 47 and 48 are updated. One sentence went
stale with the fix: decision 49 said "The rotation handle stays on top of a patch". It now
describes the handle keeping clear of the patches, and the version 5 summary says the handle
moves aside. The note's "What the mockup does" section says the same.

## Files changed by this review

- `docs/mockups/print-wizard/js/layout3d.js`: the handle keeps clear of the patches
  (`patchUnderHandle`, `placeHandle`), and the patches are placed before the handle in
  `placeOverlays`.
- `docs/mockups/print-wizard/js/hullfaces.js`: four constants renamed.
- `docs/mockups/print-wizard/DECISIONS.md`: decision 49's handle bullet and the version 5
  summary.
- [The note](../../research/2026-11-21-lay-on-face-hull-faces.md): the quotation removed,
  the blending citation corrected, the chamfer sentence corrected, and the handle added to
  "What the mockup does".
- `screenshots/hull-*.png`: all 42 replaced, because the handle now sits elsewhere. The
  `-b-hover` shots show the whole browser window, because a screenshot clipped to the panel
  made Chrome send a pointer-leave event and lost the hover.

## Concerns

- The builder's [result](result.md) still says the spacer at 800 px was left to the
  handle ("the handle wins"); this review supersedes that line.
- If no side is free, the handle is hidden while patches show. That never happened on the
  mock parts, but a crowded view of real parts could hide it; a student would then deselect
  to turn the part.
