# Fix round 1 of wizard mockup version 6

Fixes to the findings of [review 1](review-1.md), following [the fix brief](fix-1-brief.md),
on branch `mockup/v6`, from Tue 2026-11-24 23:50 to Wed 2026-11-25 00:10 PT. Every
change is in `docs/mockups/print-wizard/`; [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md)
is updated to match (a "fix round" paragraph under "What changed in version 6", decisions
3, 4, 6, 12, 13, 24, 32, 33, 35, 36, 42, 51, 52, 57 and 59, fake 13, and the new question
M28).

## Each finding

| # | What I did |
|---|---|
| F1 | "Turn on Supports and slice again" turns Supports on and runs the placement check at 12 mm. A plate that passes is sliced; one that fails is not, and the wizard goes to the Layout step with "Not sliced: with Supports on, instances need 0.472 in between them." above the usual message. Nothing moves. [Screenshot](screenshots/fix-06-320-supports-remedy-goes-to-layout.png). |
| F2 | `#os-right` and `#sa-slot` are `content-box`, so the border is outside the width; the drag handle measures the panel without it. At the scenario strip's 480 px the wizard is 480 px wide, with two quick changes per row and the rail. 520 and 680 checked the same way (on at 520 and 680, off at 519 and 679). [Settings](screenshots/fix-01-480-settings-two-per-row.png), [advanced mode](screenshots/fix-02-480-advanced-rail.png). |
| F3 | The size line wraps; no `nowrap` or ellipsis. Checked at 300 px with seven parts and a scrollbar: every size whole. [Screenshot](screenshots/fix-08-300-inch-sizes-wrap.png). |
| F4 | Part sizes are kept unrounded and rounded once, in the unit shown. Gusset Plate reads 0.250 in on the Parts step and the Layout step; Hood Rib 3.211 and 13.885; Hex Shaft 0.577. |
| F5 | The gestures paragraph and the "More ways to move and look" lines moved behind a "?" icon at the right of the Layout toolbar, which opens them in a small panel (Escape or a click elsewhere closes it). "More ways" was text, not a control, so it is no longer a separate fold. The plate line stays: neither the icon nor the chips give the plate's size, height limit or spacing. Recorded in decision 59 for the owner's Layout review. [Screenshot](screenshots/fix-07-320-layout-help-open.png). |
| F6 | All too-close instances are one error: one pair is named, more are counted ("100 instances are closer than 0.472 in with supports on. Press Arrange, or drag them apart."), with one Arrange button; all stay red in the view. Instances Arrange left beside the plate get no card of their own. [One error](screenshots/fix-04-320-100-spacers-one-error.png), [after Arrange](screenshots/fix-05-320-arranged-90-beside-10.png). |
| F7 | A click on a later tab that an earlier step holds back shows one line under the tabs: "Layout first: 23 instances are closer than 0.472 in with supports on." It goes at the next move or after 8 seconds. The same applies to the Parts and Preview steps. [Screenshot](screenshots/fix-03-480-step-tab-says-why.png). |
| F8 | Every control in advanced mode has a stable id, and a redraw puts focus back on it (after Reset, on the setting's control; a typed value redraws after Tab has moved). The header, body and footer are `inert` while advanced mode is open. Closing returns focus to the changes-box line that opened it, or to the Advanced mode button. Checked by keyboard as the rail at 480 px and the accordion at 320 px. [Screenshot](screenshots/fix-13-320-advanced-accordion-keyboard.png). |
| F9 | On the standalone page, the faulty-mesh details say "In your CAD program, check that … and that the model rebuilds with no errors before you export it again." The configuration's reload tooltip there drops "from Onshape" too. [Screenshot](screenshots/fix-12-320-standalone-faulty-mesh-cad.png). |
| F10 | "…instances up to 13.386 in tall, at least 0.197 in apart (supports off)." |
| F11 | "STL files are read in inches." A 3MF row's tooltip says it has the units the file states. |
| F12 | Taste, the owner's call: left as decision 54 has it, and asked as M28 in `DECISIONS.md`. |
| F13 | The download line is hidden when the Send step is drawn for another slice, and on Reset. |
| F14 | The menu items are buttons; Enter on the caret opens the menu on its first item, the arrow keys move, Escape closes it and returns to the caret; the caret has `aria-expanded`. The layer slider has `aria-valuemin`, `aria-valuemax`, `aria-valuenow` and `aria-valuetext`. The Layout view shows a focus ring. |
| F15 | The menu's send item takes the button's label ("Send to Shop H2S"). A setting that has a quick change is named in the quick change's words in the changes box and the change details ("Others › Brim: Off (profile Auto)", "Support › Supports: On (tree, auto) (profile Off)"). Advanced mode keeps Orca Slicer's words. [Screenshot](screenshots/fix-09-320-send-menu-one-name.png). |
| F16 | Not the review's fix: equal halves would cut "Download the sliced file" at 320 px. On the Send step Back keeps its own width (61 px at 320 px) whatever the label. The layer readout is "134 / 134 · 1.583 in", one line at 320 px. |
| F17 | "90 instances on the plate, 10 beside it." |
| F18 | The summary card's Printer row gives the name only. The offline message drops "may be off or off the network"; the no-printer message gains the "How to pair a printer" link. [No printer](screenshots/fix-10-320-send-no-printer-link.png), [busy printer](screenshots/fix-11-320-send-busy-status-once.png). |
| F19 | Every × (row, notification, printer details) is a 24 × 24 px target, and a setting's Reset link has 4 px more on each side without changing the line. The view buttons and the changes-box lines are unchanged (taste). |

Also from the review's check of the result file: fake 13 in `DECISIONS.md` now says 99
sample settings, not 95.

## Checks

- Each fix checked in a headed Chrome with WebGL at the width and state the review names,
  served on port 8771.
- A walk of every step (Parts, Settings, advanced mode, Layout, Preview, Send) at 320, 480
  and 800 px: no console message, nothing wider than the panel.
- The server and the browser are stopped. The `.playwright-cli/` files this round made, in
  the workspace folder above the repository, are removed; none was in the repository.
