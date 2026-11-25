# Review 1 of wizard mockup version 6

Reviewed: the mockup in `docs/mockups/print-wizard/` at commit `184ba8f` on branch
`mockup/v6`, against [the review brief](review-brief.md), the section "Mockup version 5
feedback of Tue 2026-11-24" of
[the feedback notes](../../handoffs/2026-11-20-session-summary-feedback.md) and
[the builder's brief](brief.md). Walked on Tue 2026-11-24, 23:11 to 23:50 PST, by a
reviewer who did not build it. Nothing in the mockup was changed. The server and the
browser used for the walk are stopped, and no `.playwright-cli/` folder is left.

**19 findings: 2 serious, 7 medium, 10 low.** No console error or warning in any walk. No
text a user sees says "student", "mentor" or "team". Nothing overflows the panel or
scrolls sideways at any width walked.

Severity as used here: **serious** is a rule of the owner's that the mockup breaks or
hides; **medium** is a requirement partly unmet, a false or inconsistent statement a user
would notice, or a usability fault; **low** is polish. A finding that is a matter of
taste says so.

## What was walked

A headed Chrome with WebGL, driven by `playwright-cli`, the folder served on port 8765.
At panel widths 320, 480 and 800 px (and 300 px, the panel's own minimum, for the Parts
and Settings steps and advanced mode):

- **Context:** Part Studio in inches, Part Studio in millimetres, Assembly, Standalone;
  **Configuration: uploads in** inches and millimetres.
- **Arm error:** every one of the 15 (1a to 10b).
- **Printer:** all 8 states, the printer details open in each, plus this user's own print
  while sending, heating, printing, waiting for a person, finished and failed.
- **Come back:** Refresh page, Close and reopen and Come back 2 h later, while slicing,
  with a finished slice, while printing, after a finished print, and with only another
  user's print.
- **Layout step, options to compare:** all 5 ways to lay on a face, all 3 mouse schemes,
  both ways parts arrive.
- Advanced mode as the accordion and as the rail, a changed setting, an invalid value,
  Reset, Reset all, opened from the Advanced mode button and from a line of the changes
  box.
- By keyboard: the step tabs, the "+1 change" chip, the printer-status icon, the
  accordion and its chevrons, the Send button's menu, the layer slider.

Every string in `index.html` and `js/wizard.js`, `js/settings.js`, `js/frame.js`, and the
sentences built in `js/plate.js`, `js/layout3d.js` and `js/parts.js`, was read in the
source; the text of every state above was also read from the page.

## Serious

### F1. "Turn on Supports and slice again" slices a plate arranged for supports off

- **Where:** Preview step, the "empty layers" error (Arm error 4), every width; then the
  Send step.
- **What:** with supports off, Arrange leaves 5 mm between instances (measured smallest
  gap 5.54 mm). The error's main button turns supports on and slices at once. The slice
  succeeds, Next is enabled, and Send is enabled. Going back to the Layout step, the same
  plate now shows two problems ("closer than 0.472 in … with supports on") and Next is
  disabled there.
- **Why it matters:** the rule of version 6 is that the placement check uses 12 mm with
  supports on, because the slice service requires it. Here the mockup slices and offers to
  send a plate the slice service would refuse, and the route to it is the remedy button
  of the most likely slicing error. The mockup has to show what the wizard does at this
  moment.
- **Smallest fix:** the button turns supports on and runs the placement check. If the
  plate passes, it slices. If not, it goes to the Layout step, where the usual sentence
  and Arrange are (nothing moves by itself, as the owner ruled).
- **Screenshots:** [sliced and ready to send](screenshots/review-01-remedy-sliced-at-5mm-supports-on.png),
  [the same plate back on the Layout step](screenshots/review-02-remedy-layout-afterwards.png).

### F2. At the scenario strip's 480 px, neither "from 480 px" layout appears

- **Where:** Settings step and advanced mode, Panel width 480 px. The builder's own
  `screenshots/480-2-settings.png` shows it too.
- **What:** at the 480 px choice the wizard is 479 px wide, because the stand-in panel's
  1 px left border is inside the 480. The quick changes (Infill, Walls, Supports, Brim)
  are one per row, Filament and Profile are stacked, and advanced mode is the accordion.
  Measured at panel widths 479, 480, 481, 482: one column and accordion at 479 and 480,
  two columns and rail at 481 and 482.
- **Why it matters:** the owner asked for two per row from 480 px and for the rail from
  480 px. Checking that at the width the scenario strip calls 480 px shows both as
  unmet.
- **Smallest fix:** keep the border outside the panel's width
  (`#os-right { box-sizing: content-box; }` in `css/frame.css`, and the same for
  `#sa-slot`), then retake the 480 px screenshots.
- **Screenshots:** [Settings step](screenshots/review-03-480-settings-one-per-row.png),
  [advanced mode](screenshots/review-04-480-advanced-accordion.png).

## Medium

### F3. Sizes in inches are cut off on the Parts step in a narrow panel

- **Where:** Parts step. At 320 px whenever the body shows a scrollbar (six parts, or
  fewer with a notification) on a system that draws scrollbars; at 300 px always.
- **What:** "0.866 × 0.866 × 1.0…", "4.724 × 3.937 × 0.2…". The line needs 130 to
  137 px; it has 136 px at 320 px, 121 px beside a scrollbar and 117 px at 300 px. So a
  size with a figure of 10 in or more ("0.315 × 3.213 × 13.886 in") is cut even with no
  scrollbar. The third number, usually the thickness, is the one lost. The tooltip gives
  the units, not the size.
- **Why it matters:** units are the headline of version 6, and name, size, quantity and
  remove are all a row keeps.
- **Smallest fix:** let the line wrap, as PenguinCAM's own `.part-item .dims` does:
  remove `white-space: nowrap; overflow: hidden; text-overflow: ellipsis` from it in
  `css/panel.css`.
- **Screenshots:** [320 px](screenshots/review-05-320-inch-sizes-cut.png),
  [300 px](screenshots/review-06-300-inch-sizes-cut.png).

### F4. A quarter-inch plate reads 0.248 in on the Parts step and 0.250 in on the Layout step

- **Where:** Parts step against Layout step, every width, parts in inches.
- **What:** the Parts step rounds each size to 0.1 mm and then converts to inches. Gusset
  Plate is 6.35 mm thick: the Parts step says "4.724 × 3.937 × 0.248 in", the Layout step
  says "0.250 in tall". Also Shooter Hood Rib 3.213 and 13.886 against 3.211 and 13.885,
  and 1/2in Hex Shaft 0.579 against 0.577.
- **Why it matters:** the brief asks for inches as a US machinist reads them, and the
  third decimal is exactly where a machinist looks. The wizard also gives two numbers
  for one thickness.
- **Smallest fix:** in `js/parts.js` keep the unrounded size and round once, in the unit
  shown (`MockUnits.size`).

### F5. The Layout step still carries a paragraph of instructions

- **Where:** Layout step, every width and state.
- **What:** under the view, always shown: a 40-word paragraph ("Drag an instance to move
  it, its round handle to turn it. Right-drag to look around, … click one to lay it on
  that face."), then "More ways to move and look" (six more lines when opened), then
  "Shop H2S: plate 340 × 320 mm, instances up to 13.386 in tall and 0.197 in apart
  (supports off)."
- **Why it matters:** the builder's brief says to remove instructions under controls on
  every step, allows "a short line" where a control does not explain itself, and names
  help text among the things the Layout step may change for. The builder kept all three
  on purpose and says so in the result file ("the view does not explain itself"). But 40
  words are not a short line, and `DECISIONS.md` decision 59 lists the five lines that
  stay without any of these three, so the document and the mockup disagree. Part of this
  is judgement: the owner has not reviewed the Layout step.
- **Smallest fix:** move the paragraph into "More ways to move and look", which stays
  closed. Keep the last line only if the owner wants the spacing said there (see F10 for
  its wording).
- **Screenshot:** [the text under the view](screenshots/review-07-layout-help-text.png).

### F6. Turning supports on with many instances gives one error card per instance

- **Where:** Layout step after supports are turned on, with the owner's reference plate
  of 100 Hex Bore Spacers (measured at 320 px).
- **What:** 82 error messages, each with its own Arrange button; the list is 14,285 px
  tall. After Arrange, 90 fit and the other 10 each get a card "… is off the plate" with
  its own Back to Parts button, under a message that already says "10 instances do not
  fit".
- **Why it matters:** version 6 makes this an ordinary path: supports are turned on
  after the plate was arranged. Generous error text is for what is specific to an error;
  this is one cause said 82 times.
- **Smallest fix:** when more than about three problems have the same rule, one message
  and one button: "82 instances are closer than 0.472 in with supports on. Press
  Arrange." Drop the per-instance cards for instances Arrange left beside the plate.
- **Screenshot:** [the top of the list](screenshots/review-08-100-spacers-82-errors.png).

### F7. A click on a later step tab does nothing, and says nothing, when the Layout step blocks

- **Where:** any step before Layout, a click on the Preview or Send tab, every width.
  The natural way in: slice, go back to the Settings step, turn Supports on, click the
  Preview tab.
- **What:** the wizard stays on the Settings step. No message, no movement. (Next does
  work: it goes to the Layout step, where the message is.)
- **Why it matters:** the owner called moving between steps an important capability, and
  the spacing rule of version 6 makes this dead click easy to reach.
- **Smallest fix:** go as far as allowed: land on the first step that blocks (the Layout
  step), where its own message explains.
- **Screenshot:** [after the click](screenshots/review-09-dead-step-tab-click.png).

### F8. Advanced mode loses the keyboard at every action

- **Where:** advanced mode, as the accordion (320 px) and as the rail (800 px).
- **What:** (1) Enter or Space on a section heading, a name in the rail, a group
  heading, the Expand all icon or a "Reset" link does its job, and then focus falls to
  the page: the next Tab starts again from the top. The same after ticking a checkbox,
  and after typing a value and pressing Tab. Every action redraws all of advanced mode,
  and the control that had focus is gone. (2) Shift+Tab from "‹ Settings" reaches the
  printer-status icon, then the covered Next and Back buttons and the covered Settings
  controls. Enter on the covered Next moves the wizard to the Layout step while advanced
  mode still fills the panel, and Escape then does nothing because focus is outside
  advanced mode. (3) Closing advanced mode, by Escape or either button, drops focus to
  the page instead of returning it to what opened it.
- **Why it matters:** the review brief asks for keyboard use of the accordion and the
  chevrons. A mouse user sees none of this; a keyboard user cannot change two settings in
  a row. Elsewhere the keyboard holds: the step tabs, the "+1 change" chip and the
  printer-status icon work with Enter or Space and keep focus, Escape closes the change
  details and the printer details, and every control but the Layout view (F14) shows a
  focus ring.
- **Smallest fix:** after a redraw, put focus back on the control with the same id
  (give headings an id). Set `inert` on the header, body and footer while advanced mode
  is open. On close, focus the Advanced mode button, or the line of the changes box that
  opened it.
- **Screenshot:** [advanced mode over the Layout step](screenshots/review-10-advanced-over-layout.png).

### F9. On the standalone page, the faulty-mesh error's details send the user to Onshape

- **Where:** Preview step, Arm error 5, Context Standalone, every width.
- **What:** the details say "In Onshape, check that bracket_v2 is one closed solid … and
  that its Part Studio rebuilds with no errors." The sentence above them correctly says
  "your CAD program".
- **Why it matters:** it is false in this state, in the text the owner most wants to be
  right.
- **Smallest fix:** give the details the same switch the sentence has (`js/wizard.js`,
  the `faulty` branch of `failSlice`).
- **Screenshot:** [the error with its details open](screenshots/review-11-standalone-faulty-mesh-says-onshape.png).

## Low

### F10. The line under the Layout view reads as a largest spacing

- **Where:** Layout step, every width: "instances up to 13.386 in tall and 0.197 in
  apart (supports off)".
- **What and why:** "up to" governs both figures, so the sentence says instances may be
  at most 0.197 in apart. It is a least distance.
- **Smallest fix:** "…up to 13.386 in tall, at least 0.197 in apart (supports off)."

### F11. "Files are read in inches." is not true of a 3MF file

- **Where:** Parts step, Context Standalone.
- **What and why:** the upload area takes STL and 3MF. A 3MF file states its units; only
  an STL carries none, which is what the owner's rule is about.
- **Smallest fix:** "STL files are read in inches."

### F12. Inches and millimetres side by side where the units rules leave room (the owner's call)

- **Where:** the chips from the Preview step on, and the Preview step, when every part
  is in inches.
- **What:** the plate-area chip says "5.983 × 5.865 in of plate" while the plate itself is
  "340 × 320 mm", so the two cannot be compared. On the Preview step "134 layers of
  0.3 mm" sits above "134 of 134 · 1.583 in high" (layer 1 is "0.012 in high"), and the
  empty-layers error says "0.976 in above the plate" over Orca Slicer's "between 24.8 and
  25.52 mm".
- **Why:** all of it follows decision 54 of `DECISIONS.md` as the builder wrote it, and
  none of it breaks the owner's four rules. It is here because the owner has not ruled on
  whether the plate area is a plate measure (millimetres) and whether a layer's height is
  a height (inches) or a slicer quantity (millimetres). The builder's open question M27
  asks the same of the spacing. Taste.
- **Smallest fix, if wanted:** the plate-area chip and the layer readout in millimetres.
- **Screenshot:** [Preview step at 320 px](screenshots/review-14-preview-units-320.png).

### F13. The "Downloaded…" line outlives the plate it describes

- **Where:** Send step, after Download the sliced file.
- **What:** change a quantity, slice again and return: the line still says "Downloaded
  the sliced file of Plate 1, 2 instances" on a plate of 4. It also survives the scenario
  strip's Reset.
- **Smallest fix:** hide `#send-toast` when the Send step is drawn for a different slice,
  and in `reset`.
- **Screenshot:** [a plate of 2 under a line about 3](screenshots/review-12-stale-download-toast.png).

### F14. The Send button's menu and the layer slider are not finished for the keyboard

- **Where:** Send step; Preview step.
- **What:** Enter on the caret opens the menu, but its two items cannot take focus, so
  Download cannot be chosen by keyboard; Escape does not close it; the caret has no
  `aria-expanded`. The layer slider answers the arrow keys but has no `aria-valuenow`,
  `aria-valuemin` or `aria-valuemax`. The Layout view takes focus with no visible ring.
- **Smallest fix:** make the menu items buttons, close on Escape, set the three slider
  attributes in `setLayer`.

### F15. One thing under two names

- **Where:** Send step; Settings step.
- **What:** the Send button says "Send to Shop H2S" and its menu says "Send to printer".
  The Brim menu says "Off" and the changes box beside it says "Brim type: No-brim"; the
  Supports menu says "On (tree, auto)" and the box says "Enable support: On".
- **Why:** one name per thing. The second pair is Orca Slicer's wording against the quick
  change's, so it needs a choice, not only an edit.
- **Smallest fix:** the menu item takes the button's label. For a setting that has a
  quick change, the changes box and the change details use the quick change's words.
- **Screenshots:** [the menu](screenshots/review-13-send-menu-names.png),
  [the Brim menu and the changes box](screenshots/review-03-480-settings-one-per-row.png).

### F16. Two things that jump

- **Where:** Send step footer; Preview step at 320 px.
- **What:** the Back button changes width with the Send button's label: 94 px beside
  "Send to Shop H2S", 149 px beside "Printing…" at 320 px. With parts in inches the layer
  readout ("134 of 134 · 1.583 in high") wraps to two lines at 320 px, and its row grows.
- **Smallest fix:** `flex: 1 1 0; min-width: 0` on both halves of the footer; a shorter
  readout ("134 / 134 · 1.583 in").

### F17. "100 instances on the plate." while 10 wait beside it

- **Where:** Layout step, when Arrange could not place every instance.
- **Smallest fix:** "90 instances on the plate, 10 beside it."

### F18. The Send step says the printer's status three times (taste)

- **Where:** Send step with a busy printer.
- **What:** the printer-status icon, the busy card and the summary card's "Printer: Shop
  H2S [Printing 61%]" all say it. The owner removed the Settings step's printer row for
  repeating the icon. Two sentences here also differ from the printer details the owner
  cut down: the offline message keeps "may be off or off the network", and the no-printer
  message has no "How to pair a printer" link.
- **Smallest fix:** drop the status from the summary card's Printer row; bring the two
  sentences in line with the printer details.
- **Screenshot:** [icon, busy card and summary card](screenshots/review-15-send-status-three-places.png).

### F19. Some click targets are small

- **Where:** every step.
- **What:** a row's remove × is 19 × 26 px; the × of a notification and of the printer
  details 15 × 18 px; "Reset" under a changed setting 29 × 16 px; the view buttons 20 px
  tall; the lines of the changes box 17 px tall and 3 px apart.
- **Smallest fix:** pad each × to 24 × 24 px.

## The owner's feedback, point by point

| Point | Result |
|---|---|
| **Parts.** Units of a part picked in Onshape: its Assembly's or Part Studio's | Met. Part Studio 1 and the Assembly in inches, "Camera Mount (mm)" in millimetres; a plate can mix them |
| Uploaded file: inches by default, a configuration option for millimetres | Met; the scenario strip's **Configuration: uploads in** switches it. See F11 |
| The plate's size in millimetres | Met ("plate 340 × 320 mm") |
| Spacing and heights in inches when every part is in inches, else millimetres | Met on the Layout and Preview steps and in every sentence read. See F4, F10, F12 |
| No "Add every part in the assembly", its sentence or its notice | Met |
| A click on an instance is enough; the prompt says only "Click a part in the assembly" / "…in the Part Studio" | Met; no help text beneath |
| The prompt does not change when a part is added | Met; the row flashes and its quantity rises |
| No refresh button on a row; name, size, quantity, remove stay | Met. See F3 for the size |
| **Step 2 is "Settings"** | Met: the step tab, the step's title, "‹ Settings" and "Back to Settings" in advanced mode and on the timeout error |
| **Settings.** The same chips as the Layout step, updating at once | Met |
| The "+1 change" chip opens the changes, joined to the chip, plain text, on every step | Met on the Settings, Layout, Preview and Send steps at all three widths |
| No printer row | Met |
| Each filament has its own profiles | Met: 5, 3, 3 and 2 profiles, all named differently |
| No help text under the profile control; the caution with its icon while changes exist | Met: "⚠ Changing the filament or the profile clears your 3 changes." At 800 px it sits under both menus, not only Profile |
| Quick changes one per row below 480 px, two from 480 px | **Not at the scenario strip's 480 px: F2** |
| The four sentences to remove | Met; none remains |
| The changes box takes the Advanced mode button's place; one button; each line a link to that setting; no "Reset all" | Met |
| **Advanced mode.** No search box; no Common / All switch | Met |
| Accordion below 480 px: bold heading, chevron, changed count, groups one level in, one open at a time, the icon at the right of the open heading | Met |
| Rail from 480 px | **Not at the scenario strip's 480 px: F2.** Met at 800 px |
| Groups always one column, about 480 px at most | Met (480 px) |
| Expand all / Collapse all: one double-chevron icon with a tooltip; at the top right of the groups beside the rail | Met |
| A group's heading: chevron right when closed, down when open; no count; "Precision · 1 changed" | Met |
| A changed setting: tint, bar, dot, "Profile 0.012 mm" and a "Reset" link; no revert arrow; the box uses the same word | Met |
| Slicer settings always in millimetres | Met |
| **Preview.** Two colours; the key "Part · Supports" only with supports on; no hiding; no help text | Met |
| **Arrange follows the Settings step:** 12 mm with supports on, 5 mm off; the placement check the same | Met: smallest gaps measured 5.06 mm and 12.01 mm; turning supports on moves nothing and gives the usual sentence. **One way round it: F1.** See F6, F7 |
| **No "mentor", "team" or "student";** "administrator" where a permission is named | Met in every string read |
| **Little help text, generous errors** | Met on the Parts, Settings, Preview and Send steps. **Layout: F5.** Errors: F9 |
| **Printer-status icon.** The details open joined to the icon | Met at all three widths and inside advanced mode |
| Free: "Nothing is printing." | Met |
| Another user sending: as it was | Met, less the estimate row |
| Printing: who sent it, percent, time left, finish time; nothing more | Met |
| Finished: no reminder | Met |
| Offline: how long since last heard; no advice | Met ("Not heard from for 7 minutes.") |
| No printer paired: one sentence and a link | Met |

## The builder's result file, checked

Read only after the findings above were written: [result.md](result.md).

- **Row 17** (quick changes two per row from 480 px) cites `480-2-settings.png`, which
  shows them one per row. **Row 23** (the rail from 480 px) cites only an 800 px
  screenshot. Both are F2.
- **Row 32** (the placement check uses the same spacing) holds on every route but F1's.
- **Help text, Layout step:** the result file says the gestures line, "More ways to move
  and look" and the plate line were kept on purpose. That is F5; decision 59 of
  `DECISIONS.md` does not list them.
- **Help text, Send step:** the result file says the offline advice "became specific".
  F18 notes that the owner cut the same advice from the printer details.
- **"What I could not do":** the mock parts were drawn in millimetres, so the inch parts
  have sizes such as 2.362 × 1.181 × 1.575 in (fake 20). Confirmed, and not a finding
  here. F4 is a different thing: a part that is a round inch size (the 6.35 mm Gusset
  Plate) shown wrongly.
- **Row 21** says 95 sample settings; the mockup has 99.
- **Checks:** every control of the scenario strip at 320, 480 and 800 px with a clean
  console: agreed, the same was found here.
- **Role words, the removed sentences, the printer details in each state, the two-colour
  Preview:** as the result file says.
- **Concerns:** the step tabs on two rows at 320 px (M20) and the spacing in inches
  (M27) are the builder's open questions and are not repeated as findings.

## Not checked

- The mockup inside Onshape, and in any browser other than Chrome.
- Dragging instances and turning them by the handle in the Layout view; instances were
  selected by a click and changed through the buttons.
- A screen reader.
