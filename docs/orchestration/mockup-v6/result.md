# Result: wizard mockup version 6

**Status: DONE_WITH_CONCERNS.** Tue 2026-11-24 23:30 Pacific. Brief: [brief.md](brief.md).
Feedback: [the owner's notes](../../handoffs/2026-11-20-session-summary-feedback.md),
section "Mockup version 5 feedback of Tue 2026-11-24". The design is written up in
[DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) ("What changed in version 6" and
the decisions it names).

## Every point of the feedback, and where it is met

| # | Point | Where it is met |
|---|---|---|
| 1 | Parts: keep the 3D picture and the list's size | Unchanged (`js/wizard.js` `renderParts`). |
| 2 | Uploading files works; keep | Unchanged; uploads now carry units (below). |
| 3 | Units, picked in Onshape: the Part Studio's or Assembly's units | `js/parts.js` `PART_STUDIOS`, `ASSEMBLY.units`; `js/frame.js` passes them with each click (`docUnits`); decision 50. Part Studio 1 in inches, "Camera Mount (mm)" metric, Assembly in inches. |
| 4 | Units, uploaded: inches by default, a configuration option for millimetres | `Config.uploadUnits` in `js/wizard.js`; scenario strip **Configuration: uploads in**; line "Files are read in inches." under the upload area; decision 51. |
| 5 | Plate size in millimetres | "plate 340 × 320 mm" on the Layout step, always; decision 55. |
| 6 | Spacing and heights in inches when every part is in inches, else millimetres | `MockUnits` in `js/settings.js`, `syncPlateRules` in `js/wizard.js`; used by `js/plate.js` (problem sentences), `js/layout3d.js` (tooltips), the selection line, resting-position strip, plate-area chip, layer readout, slicing errors; decision 54. |
| 7 | Assembly: drop "Add every part in the assembly", its sentence and its notice | Removed (`index.html`, `importAssembly` deleted); decision 21. |
| 8 | Clicking an instance is enough; prompt "Click a part in the assembly", no help text; same in a Part Studio | `renderParts`: "Click a part in the assembly" / "Click a part in the Part Studio"; the hint under it is gone; decision 14. |
| 9 | The prompt does not change when a part is added | `lastAdded` and the busy text removed; decision 14. |
| 10 | No refresh button on a row | ↻ and its code removed; the not-watertight and faulty-mesh messages now say to remove the row and add the part again; decision 18. |
| 11 | Step 2 is "Settings" | Step tab, advanced mode's back button ("‹ Settings", "Back to Settings"), "Back to Settings" on the timeout message, tooltips, `DECISIONS.md`. The internal step id stays `setup`. |
| 12 | Settings: the chips row as on Layout, updating at once | `updateSummary`: from step 2 on, parts and instances, filament, profile, "+N changes"; called on every change; decision 4. |
| 13 | "+1 change" chip clickable on every step, opens joined to the chip, the yellow box's wording, plain text | `toggleChangesPop`, `renderChangesPop`, `#chg-pop`; CSS `.chg-chip.open`, `.chg-pop`; decision 4. Screenshot `320-change-chip-open.png`. |
| 14 | No printer row on Settings | Removed (`renderPrinterLine` deleted); decision 9. |
| 15 | Each filament has its own profiles, different names | `FILAMENTS[].profiles` and nine new profiles in `js/settings.js`; decision 10. |
| 16 | No help text under Profile, except the caution once a setting is changed, until cleared; changing the filament clears too | `#p-profile-clears` with ⚠: "Changing the filament or the profile clears your 2 changes."; the filament's change handler clears changes; decision 11. |
| 17 | Setting controls one per row below 480 px, two from 480 px | `.print-overrides` grid, container query at 480 px; decision 12. Screenshots `320-2-settings.png`, `480-2-settings.png`. |
| 18 | Remove the four named sentences | All four removed (list below). |
| 19 | Changed settings replace the Advanced mode button; one button "Advanced mode"; lines are links into advanced mode at that setting; no Reset all in the box; advanced mode keeps its Reset all | `renderSetup` (`#adv-entry` hidden while there are changes), `openAdvanced(key)`; decision 12. Screenshot `320-changes-box.png`. |
| 20 | Advanced: no search box | Removed. |
| 21 | Advanced: no Common / All; every setting, collapsed groups | Removed; all 95 sample settings shown; groups start closed unless they hold a change; decision 13. |
| 22 | Below 480 px an accordion: bold section headings, chevron, changed count, groups one level in, one open at a time, Expand/Collapse icon at the right of the open heading | `renderAdvanced` (accordion branch); decision 13. Screenshot `320-advanced-accordion.png`. |
| 23 | From 480 px the rail with the groups beside it | `renderAdvanced` (rail branch); screenshot `800-advanced-rail.png`. |
| 24 | Groups always one column, about 480 px max | `.adv-col { max-width: 480px }`; the two-column rule is gone; settles M5. |
| 25 | Expand all / Collapse all: one icon (double chevron), tooltip, no line of its own | `expandButton`: Material "unfold more / unfold less" glyphs, tooltip "Expand all" / "Collapse all"; at the right of the open section's heading (accordion) or the top right of the groups (rail). |
| 26 | Group heading chevron right / down instead of the triangle | `chevron()`, `.chev.open` rotates 90°. |
| 27 | No count of settings on a group heading; changed count only | "Precision · 1 changed". |
| 28 | Changed setting: tint, bar, dot; "Profile 0.012 mm" then a "Reset" link; no revert arrow | `advRow`. |
| 29 | Yellow box lines "(profile 0.012 mm)" | `changeLine`, shared by the box and the change details. |
| 30 | Slicer settings always in millimetres | Unchanged; layer height in the Preview line stays mm; decision 56. |
| 31 | Preview: two colours, parts in the filament's colour, supports light grey; key "Part · Supports" only with supports on; no hiding; no help text | `js/preview3d.js` `show(res, instances, partColor)`, `SUPPORT_COLOR`; `renderLegend`; filament colours in `js/settings.js`; decision 33. Screenshots `320-4b-preview-supports-on.png`, `800-4b-preview-supports-on.png`. |
| 32 | Arrange follows Settings: 12 mm with supports on, 5 mm off; placement check the same | `syncPlateRules` sets `PLATE.spacing` before each check; decision 57. Screenshots `*-3b-layout-supports-on-too-close.png`, `*-3c-layout-supports-on-arranged.png`. |
| 33 | No "mentor", "team" or "student" in anything a user sees; "administrator" for a permission | All strings checked (below); decision 58. |
| 34 | Documents say "user" and "administrator" | `DECISIONS.md` throughout, with both in the terms table. |
| 35 | Little help text on working screens; generous, specific error text | Decision 59; the full list by step is below. |
| 36 | Printer details open as part of the icon, joined | `placePrinterPop` and `.pstat[aria-expanded="true"]`; decision 44. Screenshots `*-printer-details-*.png`. |
| 37 | Free: "Nothing is printing." and nothing more | Done. |
| 38 | Another user sending: good as it is | Kept, less the estimate row and the closing note (dropped everywhere). |
| 39 | Printing: who, percent, time left, finish time; no "last reported", no pause/stop sentence, no "behind" | Done; settles M24. |
| 40 | Finished: no reminder to take the plate off | Done (also dropped from the Send step's finished message and the "come back later" notification). |
| 41 | Offline: how long since heard from, no advice | "Not heard from for 7 minutes." |
| 42 | No printer paired: needs pairing, a link to a documentation page | "PenguinSlicer needs to be paired with a printer." and "How to pair a printer" (goes nowhere; fake 22). |

## Help text: every sentence removed or kept, by step

**Header.** Removed: "Your team's configuration lists these printers, filaments and
profiles; a mentor changes them there." Kept: "Loaded from your saved configuration link."
(standalone only; says where the configuration came from, a consequence not seen
otherwise), with "team" removed. Tooltips reworded: "Open the configuration", "Reload the
configuration from Onshape".

**Parts step.** Removed: "Click a part in the Parts list or the graphics area; it comes in
automatically. Click it again for one more, or set the quantity on its row."; the assembly
version of it; "Add every part in the assembly" and "Brings each distinct part with its
count. Then remove what you do not print."; the notice "Added the 7 parts of …"; "Added one
more: …"; "Bringing parts in from Onshape… keep clicking to add more."; "(up to 150)" and
"Next does not wait for it." in the total line. Kept: the prompt; "Drop STL or 3MF files
here, or click to choose" (the control's label); the total line "3 parts, 4 instances on
one plate." Added: "Files are read in inches." (STL has no units: a consequence the user
cannot see). Errors: "a mechanical mentor can check" became "Check in Onshape that …";
"Check that this computer is online … If it keeps happening, tell a mentor." became "Click
… in Onshape again to try once more." (no generic advice); the unreadable-file message
gained "The file may be cut short or saved in another format under that name." and no
longer says "as STL in millimetres"; the not-watertight warning says to remove the row and
add the repaired part. "It is in the list of parts, and" dropped from the late-arrival
notification.

**Settings step.** Removed: "Pick the filament and the profile; change a setting only if
this print needs it."; the printer row; "(most prints)" after PETG; the profile's purpose
line ("For strong brackets and plates. 0.3 mm layers.", now the option's tooltip);
"Picking another profile clears your … and uses that profile's own settings." (replaced by
the caution); "Cleared your 2 changes: this print uses … as it is."; the legend "Change for
this print" (kept as the group's accessible name); "Every slicing setting, grouped as in
Orca Slicer."; "Your team's configuration lists …"; "for this print:" in the box's heading;
"Review in advanced mode" and "Reset all" in the box. Kept: the caution (consequence not
visible); "2 settings changed from Structural".

**Advanced mode.** Removed: "Your changes stay for this print."; the search box and its
placeholder; "Common shows the … settings teams change most …" (the mockup note now only
says the sample size). Kept: "Structural, 2 changed" under the title; the range-check error.

**Layout step** (changed only for help text, units and spacing). Removed: "↔ Widen the
panel for more room. Drag to move, drag the round handle to turn. To change how many of a
part, go to the Parts step (tab 1)."; "Click one to select it."; "Chosen by how much touches
the plate, how much hangs over air and how tall it stands. Select an instance to see the
other ways it can lie, or to put it back as modelled."; "(click one to select its
instances)". Kept: the gestures line under the view (the view does not explain itself); the
folded "More ways to move and look"; the plate line ("Shop H2S: plate 340 × 320 mm,
instances up to … tall and … apart (supports off)."), now with the supports state; the
resting-position strip's heading (it is one of the M1 options under review); "Laid down
automatically: …" (a consequence not seen otherwise).

**Preview step.** Removed: every line under the title ("The plate is sliced as soon as you
get here …", "Slicing the plate on the server …", "Sliced. Check the layers, then Next …",
"The slice failed …", "… stopped at the server's time limit …", "The slice was cancelled
…", "This plate was not sliced …"); "Click a line type to hide it. Drag the bar … scroll to
zoom." (now the view's tooltip); "Change the plate or the settings with Back, or slice
again." on the cancelled message. Kept: "Slicing goes on if you step back; change the plate
and it starts again." (consequence not seen); the connection lines; the reconnected toast.
Errors: "pick the Draft profile" became "pick a profile with thicker layers" (profiles now
differ per filament); "press ↻ on its row" became "remove its row and click the repaired
part again"; "on a shop computer" became "on your own computer".

**Send step.** Removed: every line under the title ("Check the plate on the printer, then
send …", "Your plate is on its way … Pausing or stopping a print is done at the printer's
screen.", the heating, printing, waiting, finished, busy, offline and unpaired versions);
"nobody is asked again"; "Nothing prints until the whole file has arrived."; "From the
printer's own report, a few seconds behind. To pause or stop the print, use the printer's
screen; this panel cannot."; "Take the plate off once the bed has cooled; PETG lets go
more easily when cool."; "send it again when you are ready"; the busy card's "Send waits
until the printer is free; your sliced plate stays ready here. Nothing queues: come back,
or keep this panel open, and send when it is free." Kept: "Check that the plate is clear
and PETG is loaded. Send starts the print at once."; "Send comes back when the printer is
free; nothing queues."; the waiting reason and what to do at the printer; the failed print
with its Details. Offline and unpaired messages: "Your team has no printer paired …" became
"No printer is paired with PenguinSlicer, so nothing can be sent." and "A mentor pairs …"
became "An administrator pairs the printer once, from the computer beside it."; offline
advice became specific ("The printer, or the computer beside it that connects it to
PenguinSlicer, may be off or off the network.").

**Printer details.** Removed: "… is free for the next plate."; the printer's model line;
"The printer's own report, a few seconds behind. To pause or stop a print, use the
printer's screen."; "Take the plate off before the next print."; "Clear the plate at the
printer before the next print."; the offline advice; "Your team has not paired a printer …
A mentor pairs it once …"; the "Estimate" row and "· late".

**Coming back.** Removed: "Your parts and layout are as you left them."; "Take it off the
plate if nobody has yet. Start a new plate here." Kept: "Your parts were not kept; add them
again to print again." (consequence not seen).

## Role words

Every string in `index.html` and `js/*.js` was searched for "student", "mentor" and "team"
(case-insensitive): none remains in anything a user sees, nor in the scenario strip
("Another user sending", "User cancels", "Imitate the user …"), nor in code comments.
"For a mentor" is now "Details". "6238 (Popcorn Penguins)" stays as the configuration's
name; "Shop H2S" stays as the printer's name.

## Choices made

- **Inches:** decimal to three places everywhere (sizes, heights, distances, spacing:
  "0.197 in", "0.472 in"); millimetres keep version 5's precision. A too-tall sentence in
  inches also gives the limit in millimetres ("13.386 in (340 mm)"). The height limit in
  the plate line follows the layout units; the plate's width and depth stay in mm. Contact
  areas in the strip's tooltips follow too (in² to two places).
- **Mixing units:** the document has two Part Studio tabs; moving between them keeps the
  wizard's plate (as switching Onshape tabs with the panel open), so a plate can hold inch
  and metric parts. The scenario strip's **Context** offers both Part Studios. A part added
  by the armed "too tall" error takes the first part's units.
- **The changes box's link colour** is a darker blue (`#0b5cd5`) for contrast on yellow.
- **Change details** close on a click elsewhere, Escape, or the chip; they and the printer
  details close each other.
- **Advanced mode:** "Changed only" removed with the search and the Common / All switch
  (asked as M26); groups start closed unless they hold a change; a line of the changes box
  opens its section and group, scrolls the setting into the middle and flashes it; the
  section name heads the groups in the rail layout so the icon has a row to sit on.
- **Printer details:** "Sent by" in every state (version 5 said "For"); "Expected finish" as
  on the Send step; the bar kept only while sending (the owner said sending was good as it
  was, and printing "nothing more"); waiting shows sent by, percent and what to do.
- **"Behind" dropped everywhere,** on the Send step's print card and busy card too, and the
  scenario strip's "Another student printing, behind" option with it.
- **Filament colours** (invented): PETG HF orange, PETG-CF dark grey, PLA green, TPU pink;
  supports `#b4bac2`.
- **Per-filament profiles:** PETG-CF Stiff bracket, Light and stiff, CF draft; PLA Fit check,
  Jig, Display; TPU Bumper, Grip pad (PETG keeps version 5's five).
- **Decision numbers** are kept; new decisions are 50 to 59. `DECISIONS.md`'s version 4
  history is cut to one line; version 5's is kept short.
- **Questions:** M4, M5, M24, decision 47, the step's name and the Arrange spacing are
  settled and folded in; M25 (per-file units), M26 ("Changed only") and M27 (spacing shown
  in inches) are new.
- **Requirements:** version 5's requirement 3 (`expected_s` kept from the send) is dropped;
  new short requirements on the configuration and the Onshape source are added.

## What I could not do

- **Inch parts with round inch sizes.** The mock parts were drawn in millimetres, so the L
  Bracket reads 2.362 × 1.181 × 1.575 in rather than a drawing's 2.000-style numbers.
  Redrawing them in inches would change every part's hull faces, which version 5's lay-on-face
  work measured; left as fake 20.
- **The real panel staying open across Onshape tabs** is unverified (open facts).

## Checks

Served `docs/mockups/print-wizard/` on port 8836 (Python's static server), headed Chrome
under its own Xvfb display (:97) with SwiftShader; both stopped afterwards and
`.playwright-cli/` removed.

- **Every step at 320 and 800 px** (inch plate at 320, mixed inch and metric plate at 800),
  then supports turned on after arranging (too-close sentences, then Arrange), then Preview
  with supports on.
- **Settings at 480 px;** advanced mode at 320 (accordion) and 800 (rail).
- **Printer details in each of the eight states** at 320 and 800 px.
- **Every scenario-strip control at 320, 480 and 800 px** (one script, run three times):
  panel width menu, Fewer/More controls, Hide/Show strip, the how-to fold, both speeds,
  the four contexts, the uploads units option both ways, Reset, every armed error (four on
  Parts, three on Layout, six on Preview, two on Send), every Printer state, Refresh page,
  Close and reopen, Come back 2 h later, the five Lay on face options, the three Mouse
  schemes, both Parts arrive options, Download, Cancel sending.
- **Console:** no errors and no warnings after each walk.

## Screenshots

In [screenshots/](screenshots/):

- Steps: `320-1-parts-inches.png`, `320-2-settings.png`, `320-3-layout-inches.png`,
  `320-4-preview.png`, `320-5-send.png`; `800-1-parts-mixed-inches-and-mm.png`,
  `800-2-settings.png`, `800-3-layout-mm.png`, `800-4-preview.png`, `800-5-send.png`;
  `480-2-settings.png`.
- Settings changes: `320-2b-settings-changes-box.png`, `480-2b-settings-changes-box.png`,
  `320-changes-box.png`, `320-change-chip-open.png`, `800-change-chip-open.png` (on the
  Layout step, after picking PLA, whose profiles are Fit check, Jig, Display).
- Advanced mode: `320-advanced-accordion.png`, `320-advanced-accordion-expand-all.png`,
  `800-advanced-rail.png`.
- Printer details: `320-printer-details-<state>.png` and `800-printer-details-<state>.png`
  for idle, other_sending, other_printing, other_waiting, finished, failed, offline,
  unpaired; `sweep-320-5-printer-details-your-print-waiting.png`.
- Supports and spacing: `320-3b-layout-supports-on-too-close.png`,
  `320-3c-layout-supports-on-arranged.png`, `800-3b-…`, `800-3c-…`,
  `320-4b-preview-supports-on.png`, `800-4b-preview-supports-on.png`.
- Units: `320-1-parts-inches.png`, `sweep-320-1e-parts-metric-studio.png`,
  `sweep-320-1f-standalone-uploads-inches-and-mm.png`, `800-1-parts-mixed-inches-and-mm.png`.
- The 320 px sweep of the scenario strip's errors: `sweep-320-*.png`.

## Concerns

- At 320 px the five step tabs still wrap to two rows ("Settings" is longer than "Setup");
  M20 stays open.
- The spacing in inches (0.197 in, 0.472 in) follows the rule but reads oddly; asked as M27.
