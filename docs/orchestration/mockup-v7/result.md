# Result: wizard mockup version 7

Built Wed 2026-11-25, 08:39 to about 09:40 PT, on branch `mockup/v7`, from
[the brief](brief.md). The mockup is in [docs/mockups/print-wizard/](../../mockups/print-wizard/index.html);
its decisions are in [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) (now version 7,
with "What changed in version 7" at the top); the lay-on-face note is
[the algorithm note](../../research/2026-11-21-lay-on-face-hull-faces.md), with a new section
on bounding-box patches. The owner's feedback file was folded into DECISIONS.md and deleted
with `git rm`; the one link to it (in the brief) now names it in words.

## Every point of the feedback, and where it is met

### Layout step

| Point | Met | Where |
|---|---|---|
| The rotation handle is bound to the instance: on a circle round the selection at the radius set when the drag starts, turning with the instance through the same angle, snaps included; no jump to another side while dragged; moves clear of hull patches only when the drag ends or patches appear | Yes | `js/layout3d.js` `placeHandle`, `applyTurn`; decision 62. Measured: the handle's position in the first selected instance's own frame moved 0.00 mm over 12 pointer steps (75°) in each of six drags (below) |
| Round parts can be laid on edge: bounding-box patches on sides with no flat face, styled like hull patches, a click lays the instance on that side; parts whose faces cover every side get none | Yes | `js/hullfaces.js` step 5, `js/layout3d.js` `showPatches`; decision 61; the note's new section. Pulley and spacer gain four each; bracket, camera mount, gusset and hex shaft none; the rib three (M29) |
| Turning is free; Shift snaps to 45°; a readout beside the handle ("↻ 37°"); the 5-degree catch and "snaps every 45 degrees" go | Yes | `applyTurn`, `turnText`; the "?" list now says "Hold Shift while turning to turn in 45° steps." |
| Drop "To print more or fewer of a part, go to the Parts step (tab 1) …" | Yes | `renderGestures` in `js/wizard.js`; decision 24 |
| No text about orientation: no "As modelled, which is already its best way.", no "… already lies that way.", no "… now lies … tall." | Yes | `renderOrientLine`, `afterLay`, `layInstances`, `autoOrient`, `tipSelected`, `enterLayoutData` in `js/wizard.js`, `layWorld` in `js/layout3d.js`; decision 59 |
| Printer and plate figures always in millimetres: the plate line, spacing in errors, the layer readout; only a part's own size follows its units; settles M27 and M28 | Yes | `syncPlateRules`, `unitsOf`, `enterLayout`, `recheck`, `setLayer`, `failSlice` in `js/wizard.js`; `check` in `js/plate.js`; decisions 54, 55, 57 |

### Send step and the printer's "finished"

| Point | Met | Where |
|---|---|---|
| The icon says "Free" as soon as the print ends, never "Finished"; its details add "Last print finished 11:25 am (Alex Chen)" | Yes | `printerStatus`, `renderPrinterPop`, `lastFinished`; decisions 43, 44 |
| The user's own last print is a one-line note, not a card; on the Send step of a new plate the card goes and the note sits above; coming back, the note shows on whichever step opens | Yes | `renderLastPrint`, `renderSend`, `reopen`; `#last-print` in `index.html`; decision 60 |
| How long: until another plate is sent or 12 hours after it finished; answers M19 | Yes | `LAST_PRINT_KEEP_MS`; the scenario strip's new **12 hours later** (`twelveHoursLater`) |
| The scenario strip's printer states match (a print that ended shows Free with the last-print line) | Yes | Printer menu: "Free, another user's print finished 25 min ago"; "Free (nothing printed lately)" |
| The time-and-filament chip goes | Yes | `updateSummary`; decision 4 |

### The top of the panel at 320 px

| Point | Met | Where |
|---|---|---|
| Steps below 480 px: numbered circles joined by a line, a check in each done step, the current one filled with its name; every circle clickable with a tooltip; pills from 480 px; settles M20 | Yes | `css/panel.css` container query `max-width: 479.98px`; `index.html` step tabs; decision 3 |
| The plate summary is two lines of text: parts and instances; then filament and profile, cut with an ellipsis, and the "+2 changes" pill, kept whole; the plate-area chip goes | Yes | `updateSummary`, `#wiz-summary` CSS; decision 4 |
| No "Mockup: …" notices in the panel; what they said goes to "What is fake and could mislead" or the scenario strip | Yes | Removed: the upload note, the too-tall note (two forms), the plate-too-large note, "Mockup: no file is saved.", advanced mode's sample note, and the "(mockup: …)" in two tooltips. Fakes 9, 11, 23, 24, 25 and the strip's option labels and "How to use this mockup" say it now |
| Advanced mode's sections are cards below 480 px (title with chevron, changed count and Expand / Collapse icon; groups as rows; a closed section a slim card); the rail from 480 px unchanged | Yes | `.adv-sec` CSS; decision 13 |
| Advanced mode's header loses "‹ Settings"; "Back to Settings" is the only way back; Escape no longer closes it | Yes | `index.html`, `bindAdvanced`; decision 13. Walk: Escape left advanced mode open at 320, 480 and 800 px |
| "Loaded from your saved configuration link." goes; a failing link still shows an error | Yes (the line); see below | `renderConfig`; fake 25 |

## Choices made (the owner was away)

1. **Shift's 45° steps count from where the drag started** (the turn is a multiple of
   45°), not from the instance's absolute heading. Every instance arrives square, so the
   two agree until the user turns one freely.
2. **The readout's arrow shows the direction:** "↺ 37°" anticlockwise, "↻ 37°" clockwise,
   seen from above. The owner's example used ↻ only.
3. **After a drag the handle stays bound** to the first selected instance (it follows a move
   too), until the selection changes or the instance is laid down; then it goes back above
   the selection. Each instance turns rigidly about the pivot (version 6 kept each
   instance's box middle on the turned point, which slid asymmetric parts against the
   handle).
4. **The bounding-box test uses 30° plus half a degree,** so the hex shaft's flats, exactly
   30° from its box's sides, cover them. Box patches are offered only with *Faces on the
   hull (like Orca)*, the way the hull patches are.
5. **The Shooter Hood Rib gets three box patches** (outer curve and both ends); standing it
   on an end is too tall and the usual error says so. Asked as M29 rather than tuned.
6. **"No text about orientation" was read widely:** besides the three sentences named, the
   "Laid down automatically" chip, "Laid down by you." and "As modelled." beside the
   orientation links, the note when parts arrive laid down automatically, auto-orient's
   "laid N instances their best way", and the tip handle's "has only one way to lie flat"
   are gone. Kept: the two links themselves ("Put back as modelled", "Lay it the best
   way"), and sentences about a move the wizard made that the user did not ask for (moved
   to a free spot, left beside the plate, "Arranged the plate again to make room.").
7. **The plate line follows the owner's wording exactly:** "Shop H2S: plate 340 × 320 mm,
   up to 340 mm tall, 12 mm apart", without "(supports on)" and without a full stop. The
   spacing errors still say "with supports on" or "off".
8. **A failed print keeps its card and the icon's "Failed"**; only a print that finished
   becomes Free with a one-line note. A failed print when coming back keeps its
   notification on the Parts step.
9. **The last-print note on other steps** shows only on the step that opens when the user
   comes back, and goes when the user leaves it (as notifications do); on the Send step it
   shows whenever it is valid. Coming back no longer adds "Your parts were not kept; add
   them again to print again." for a finished print (the empty Parts step shows it).
10. **"(you)"** replaces the name in the details' line for the user's own print: "Last
    print finished 7:31 pm (you)".
11. **12 hours later** moves the clock with the panel left open (no curtain), and further if
    a print's own clock ran ahead at Fast speed.
12. **Opening advanced mode puts focus on the first section's heading,** since its old
    target, "‹ Settings", is gone.
13. **Tooltip text was cleaned too:** "Open the configuration (mockup: does nothing)" and
    "Documentation (mockup: the page is still to be written)" lost their mockup part.
14. **The browser session was named `mockup-v7`,** not the one in `$PLAYWRIGHT_CLI_SESSION`,
    which another session of the owner's may be using; it ran on its own Xvfb display
    (`:117`), with the folder served on port 8731.

## What I could not do, or did not

- **"A link that fails still shows an error":** the mockup has no failing-configuration-link
  path to show; nothing was added (the brief forbids features not asked for).
- **The real proof of the handle is the owner's hand:** the walk drives the mouse
  through playwright, at 6° a step; it cannot judge how the drag feels.
- The sweep's slicing part arms errors in a fixed order inherited from version 6, so some
  of its lines report the previous armed error's message; that is the script, not the
  mockup (version 6's sweep did the same).

## The walk

Served `docs/mockups/print-wizard/` on port 8731; Chrome under Xvfb with SwiftShader WebGL,
driven by `playwright-cli`. Screenshots are in [screenshots/](screenshots/).

- **Every step at 320, 480 and 800 px** (Parts, Settings with two changes, the change
  details, advanced mode, Layout, Preview, Send): `320-*.png`, `480-*.png`, `800-*.png`.
- **Every scenario-strip control at 320, 480 and 800 px** (one script, run three times;
  screenshots at 320, `sweep-320-*.png`): widths, Fewer controls, Hide strip, How to use,
  speed, every context, uploads in both units, all armed errors, every Printer state
  including the new "finished", Refresh, Close and reopen, Come back 2 h later and the new
  12 hours later. Console: no errors and no warnings after each run.
- **The rotation handle** on a long part (1/2in Hex Shaft), a round part (HTD Pulley 24T)
  and a multi-selection of three, each with and without Shift (`handle-*.png`):

  | Drag | Handle drift in the instance's frame | Readout / turn (every other step) | Bound after |
  |---|---|---|---|
  | Shaft, free | 0.00 mm at every step | ↺ 10°, 20°, 31°, 42°, 54°, 67° | yes |
  | Shaft, Shift | 0.00 mm | ↻ 0°, 0°, ↺ 45°, 45°, 45°, 90° | yes |
  | Pulley, free | 0.00 mm | ↺ 7°, 21°, 36°, 51°, 65°, 79° | yes |
  | Pulley, Shift | 0.00 mm | 0°, 0°, 45°, 45°, 45°, 90° | yes |
  | Three instances, free | 0.00 mm | ↺ 4°, 12°, 20°, 30°, 41°, 55° | yes |
  | Three instances, Shift | 0.00 mm | 0°, 0°, 45°, 45°, 45°, 90° | yes |

  The handle's tooltip read "Drag to turn · Shift: 45° steps".
- **Lay on face, every part** (all seven, on one plate at 640 px): each patch a press
  would take was clicked in turn; after each click the patch's direction pointed straight
  down. 41 lays, all right, including the four box patches of the pulley and of the spacer
  (the pulley then rests on its rim: `box-patches-pulley-laid-on-its-rim.png`). The boxy
  parts showed no box patch (`box-patches-bracket.png`). On the rib, after three lays (it
  then waited beside the plate), a click on its middle selected the instance in front of
  it, and the script stopped there. A run with the rib alone laid it on five patches in
  turn, all right, including the box patch of its outer curve; its two end box patches
  were drawn but a press at their middles never reached them from the walk's views (they
  stand edge-on to the camera at the rib's ends), so they were not clicked (M29 asks
  whether they should exist at all).
- **The plate summary at 320 px** with Bambu PETG-CF, "Light and stiff" and three changes:
  "PETG-CF · Light and stiff" (135 px) and "+3 changes" fit on one line without the
  ellipsis; no mock filament and profile pair is long enough to show it, so the ellipsis
  is set in CSS (`.sum-text`) but was not seen cut. A first run counted two patches as pickable that another instance covered at
  their middle; the walk's own check (`__patches`) was corrected to test the press the
  way `onDown` does.
