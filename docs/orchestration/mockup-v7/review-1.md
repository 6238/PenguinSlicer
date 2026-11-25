# Review 1 of wizard mockup version 7

Reviewed: the mockup in `docs/mockups/print-wizard/` at commit `5e5e546` on branch
`mockup/v7`, against [the review brief](review-brief.md), the owner's feedback on version 6
(the handoff note of Wed 2026-11-25, read from `git show 5e5e546~1`) and
[the builder's brief](brief.md). Walked on Wed 2026-11-25, 09:20 to 09:54 PST, by a
reviewer who did not build it. Nothing in the mockup was changed. The server and the
browser used for the walk are stopped, and no `.playwright-cli/` folder is left in the
repository or in the scratch folder.

**9 findings: 0 serious, 3 medium, 6 low** (one of the low ones is taste). Every point of
the owner's feedback is built. No console error or warning in any walk. No text a user
sees says "student", "mentor" or "team", and none starts "Mockup:". Nothing overflows the
panel or scrolls sideways at 320, 480 or 800 px in any state walked (about 300 layout
audits).

Severity as used here: **serious** is a point of the owner's feedback that is not met, or
a rule of the owner's that the mockup breaks; **medium** is a false or confusing statement
a user would notice, or a usability fault; **low** is polish. A finding that is a matter
of taste, or that needs the owner's word, says so.

## What was walked

A headed Chrome with WebGL, driven by `playwright-cli`, the folder served on port 8773, at
panel widths 320, 480 and 800 px:

- **Every step** on the plain path, with a plate that mixes inch and metric parts.
- **Context:** Part Studio in inches, Part Studio in millimetres, Assembly, Standalone;
  **Configuration: uploads in** inches and millimetres.
- **Arm error:** every one of the 15 (1a to 10b); the two that run on the real clock for
  20 and 40 seconds (1c, 6) at 320 px only.
- **Printer:** all 8 states with the printer details open in each; this user's own print
  while sending, waiting for a person, printing, finished and failed.
- **Come back:** Refresh page while slicing, Close and reopen while sending, Come back 2 h
  later after a finished and after a failed print, and **12 hours later** after another
  user's and after this user's finished print.
- **Layout step, options to compare:** all 5 ways to lay on a face, all 3 mouse schemes,
  both ways parts arrive.
- **The rotation handle:** dragged on a long part (1/2in Hex Shaft), a round part (HTD
  Pulley 24T), an L Bracket and a selection of three, free, with Shift and fast, at each
  width; its place in the instance's own frame was read at every drawn frame (see L1).
  Also after a turn: zooming, laying the instance another way, adding an instance to the
  selection.
- **Lay on face:** every mock part selected at each width; a bounding-box patch clicked on
  the pulley and the spacer, and a face patch clicked to lay each flat again.
- **Advanced mode** as cards (320 px) and as the rail (480 and 800 px): every section
  expanded, a changed setting, an invalid value, Reset all, the printer details, opened
  from the button and from a line of the changes box, Escape.
- **By keyboard:** the step circles and pills, the "+2 changes" pill, the printer-status
  icon and its details, the accordion, its chevrons and the Expand all icon, the layer
  slider.

Every string in `index.html`, `js/wizard.js`, `js/settings.js`, `js/frame.js` and the
sentences built in `js/plate.js` and `js/layout3d.js` was read in the source; the text and
the tooltips of every state above were also read from the page at 320 px.

## The owner's feedback, point by point

| Point of the feedback | Met | Where checked, and what remains |
|---|---|---|
| The rotation handle is bound to the instance | Yes | At 320, 480 and 800 px, on a long part, a round part, an L Bracket and three instances: the radius is fixed for the drag, the handle never changes side while dragged, and once the picture settles the handle sits exactly where it was in the instance's frame (0.00 mm off). In the frames drawn while the pointer moves it leads by one update: L1. |
| Round parts can be laid on edge | Yes | HTD Pulley 24T and Hex Bore Spacer 1in gain four bounding-box patches each; two can be clicked from the opening view at every width; a click stands the part on its rim, and a face patch lays it flat again. L Bracket, Camera Mount, Gusset Plate and 1/2in Hex Shaft gain none. The Shooter Hood Rib gains three: L2. |
| Turning is free, Shift snaps to 45°, a readout | Yes | Readout "↺ 37°" beside the handle, never clipped by the view in the walks; tooltip "Drag to turn · Shift: 45° steps"; no text says "snaps". What Shift snaps is the turn, not the instance: M2. |
| Drop "To print more or fewer of a part…" | Yes | Not in the "?" list or anywhere else. |
| No text about orientation | Yes | No line under the controls, no message after laying an instance another way or when parts arrive laid down. "Put back as modelled" and "Lay it the best way" remain as links. |
| Printer and plate figures always in millimetres | Yes | "Shop H2S: plate 340 × 320 mm, up to 340 mm tall, 12 mm apart" with an all-inch plate; spacing in errors; "134 / 134 · 40.2 mm" on Preview. The too-tall sentence now holds both units: M1. |
| The icon says "Free", never "Finished"; "Last print finished … (Alex Chen)" | Yes | Every printer state and this user's own print, all three widths. |
| "Your print finished at 11:25 am." is a note, not a card | Yes | On the Send step of the same plate and of a new plate; on the Parts step after coming back. Two notifications beside it are left saying things no longer true: M3. |
| The note and the line go at the next send or after 12 hours | Yes | **12 hours later** removes both; a new send removes both. |
| The time-and-filament chip and the plate-area chip go | Yes | No chip but "+2 changes". |
| Steps below 480 px are numbered circles | Yes | Five 22 px circles, a check in each done step, the current one filled with its name; each has its step's name as tooltip and works by click, Enter and Space. The header is 98 px tall at every width. Pills from 480 px. L3 is about the focus ring. |
| The plate summary is two lines of text | Yes | "6 parts · 7 instances" and "PETG · Structural" with the pill. The longest filament and profile in the mock data ("PETG-CF · Light and stiff", 135 px) fits at 320 px, so the ellipsis never shows in a walk; the rule is in the style sheet. L5 is about a 4 px jump. |
| No "Mockup: …" notices in the panel | Yes | None in the source or in any state. |
| Advanced mode's sections are cards below 480 px | Yes | Bordered cards, a closed section slim, the Expand all icon in the open card's title; the rail unchanged from 480 px. |
| Advanced mode's header loses "‹ Settings"; Escape does not close it | Yes | Escape closes only the printer details when they are open. |
| "Loaded from your saved configuration link." goes | Yes | Gone. "A link that fails still shows an error" cannot be checked: the scenario strip has no failing link. |

## Medium

### M1. The too-tall error compares inches with millimetres

- **Where:** Layout step, every width, an inch part standing taller than the printer
  prints (armed "3c. Instance too tall", or "Put back as modelled" on a Shooter Hood Rib).
  The sentence is in the error, in the red bar above the view and in the "Layout first: …"
  line under the step tabs.
  [Screenshot](screenshots/review-1-too-tall-inches-against-mm.png).
- **What:** "Shooter Hood Rib #1 stands 13.885 in tall; the printer prints up to 340 mm."
  At 320 px the red bar cuts it to "Shooter Hood Rib #1 stands 13.885 in tall; …".
- **Why:** the sentence exists to compare two heights, and gives them in different units,
  so the reader cannot see that 13.885 is more than 340, or by how much. `DECISIONS.md`
  decision 54 chose this ("an instance's height in a too-tall error" follows its part's
  units), reading the feedback's "only a part's own size follows its units" to the letter.
  How tall an instance stands on the plate, set against the printer's limit, is as much a
  plate figure as the spacing between two instances, which the same feedback puts in
  millimetres. With a metric part the sentence reads well: "stands 353 mm tall; the
  printer prints up to 340 mm."
- **Smallest fix:** in this one sentence give the instance's height in millimetres, as the
  limit is. The selection line and the patch tooltips keep the part's units. This changes
  a decision the builder recorded, so it needs the owner's word.

### M2. Shift snaps the turn, not the instance, so a freely turned instance cannot be squared again

- **Where:** Layout step, every width, the rotation handle with Shift held.
  [Screenshot](screenshots/review-2-shift-after-free-turn.png).
- **What:** Shift turns in 45° steps counted from where the drag started. A 1/2in Hex
  Shaft turned freely by 18° and then turned with Shift ends at 63° (its footprint reads
  4.043 × 7.298 in, where square to the plate it is 7.874 × 0.577 in). The readout shows
  the turn of this drag ("↺ 45°"), never the angle the instance lies at.
- **Why:** turning is free now, so instances end up at odd angles easily, by a slip as
  much as on purpose. Nothing then brings one instance back square to the plate:
  Auto-orient and "Put back as modelled" do not look at the turn on the plate, and Arrange
  squares it only by moving every instance. The feedback's "snaps to multiples of 45°" can
  be read either way; `DECISIONS.md` decision 62 records the reading built ("in steps of
  45° from where the drag started"), and the builder's result lists it as a choice made
  while the owner was away. Programs differ on this; snapping the object's own angle is
  the reading that lets a user straighten something.
- **Smallest fix:** with Shift, snap the instance's angle on the plate, counted from how it
  lay when it was last arranged or laid down, to multiples of 45°, and show that angle in
  the readout. Needs the owner's word, since it is a choice between two readings.

### M3. Two notifications on the Send step stay after they stop being true

- **Where:** Send step, every width.
  [The "Sending cancelled" notification](screenshots/review-3a-cancelled-notice-after-the-print.png),
  [the "Back where you were" notification](screenshots/review-3b-progress-is-below-nothing.png).
- **What:**
  1. Cancel a send, then send the plate again. "Sending cancelled. Nothing reached Shop
     H2S and nothing will print. Your sliced plate is still here." stays at the top while
     the plate is sent, prints and finishes, and then sits directly under "Your print
     finished at 6:39 am."
  2. Close and reopen the panel while a plate is on its way. "Back where you were. You had
     sent your plate to Shop H2S before you left; its progress is below." stays after the
     print finishes. Version 7 removes the finished print's card, so nothing is below it
     but the reminder for a new send, and the notification sits under "Your print finished at
     10:08 pm."
- **Why:** each says something false in the state it is left in ("nothing will print"
  beside a print; "its progress is below" above no progress). The second became false
  with version 7's change from a card to the last-print note. Both go only when the user
  presses × or leaves the step.
- **Smallest fix:** drop the "Sending cancelled" notification when a send starts, and the
  "Back where you were" notification when this user's print ends (`sendToPrinter` and the place where
  the print card is removed, in `js/wizard.js`).

## Low

### L1. While the pointer moves, the handle is drawn one update ahead of the instance

- **Where:** Layout step, every width, dragging the rotation handle; plainest with Shift.
  [A drawn frame](screenshots/review-4-handle-ahead-of-instance.png): the handle and the
  dashed selection box have snapped 45°, the shaft has not yet.
- **What:** the handle's place in the first selected instance's own frame was recorded at
  every frame the view drew. Settled, it is exact (0.00 mm at every width, on every part
  and on three instances). In frames drawn while the pointer moves, the handle and the
  dashed box are at the newest angle and the instance is still at the one before. In a
  slow free turn (pointer steps of half a degree) that is under a millimetre; in a fast
  one (steps of 5°) 2 to 11 mm of plate, a few pixels; at each Shift snap one frame shows
  the handle a full 45° from the instance (13 to 47 mm of plate, measured at 320, 480 and
  800 px).
- **Why:** the feedback asks that "the instance and the handle never part". They part for
  one frame per update, which the eye catches as a flicker at a Shift snap. The cause is
  the order of work in a frame: `applyTurn` in `js/layout3d.js` changes the instance, the
  view draws (placing the handle from the new angle), and only then does the wizard move
  the instance's mesh (`editor.sync` in a later animation frame).
- **Smallest fix:** in `applyTurn`, call `placeMesh` for each turned instance, so the mesh
  has moved before the frame is drawn. The same one-frame lag is in a move drag (the dashed
  box leads the instance).

### L2. The Shooter Hood Rib's bounding-box patches: two can only fail, and none can be reached from the opening view

- **Where:** Layout step, a Shooter Hood Rib selected, every width.
  [Screenshot](screenshots/review-5-rib-box-patches.png).
- **What:** the rib gains three bounding-box patches (its outer curve and its two ends), as
  `DECISIONS.md` decision 61 says and asks about (M29). Laid on either end it stands
  13.885 in (353 mm) tall, above the printer's 340 mm, so those two patches can only end
  in the too-tall error. And with the rib lying flat all three are strips 8 mm high on
  its edges: from the opening view at 320 and at 800 px no point of the view presses any
  of them.
- **Why:** a patch offers a way to lay the part; one that always fails, or that cannot be
  pressed without first turning the view, is clutter on a part that already has five
  face patches.
- **Smallest fix:** draw no patch, on the box or on the hull, for a side on which the part
  would stand taller than the printer prints. Whether an arc's outer curve should get a
  patch at all is the owner's question M29.

### L3. The focus ring of a step circle takes in the line beside it

- **Where:** header below 480 px, a step circle focused by keyboard.
  [Screenshot](screenshots/review-6-step-focus-ring.png).
- **What:** the ring is drawn round the list item, which holds the circle and the line to
  the next circle, so it is a lopsided pill 44 to 48 px wide with the circle at its left
  end. On the last step it is a neat ring.
- **Why:** it reads as a ring round two things. Keyboard use itself works (Tab, Enter,
  Space).
- **Smallest fix:** put the outline on the circle (the item's `::before`) below 480 px.

### L4. Armed "3a. Instances too close" can show an overlap, out of sight

- **Where:** Layout step, scenario strip, with two Gusset Plates, an HTD Pulley 24T and a
  Hex Bore Spacer 1in on the plate.
  [Screenshot](screenshots/review-7-too-close-is-overlap.png).
- **What:** the armed error put the spacer inside a gusset's outline: "Gusset Plate #2 and
  Hex Bore Spacer 1in #1 overlap." The sentence the option is there to show (in
  `js/plate.js`: "… are … mm apart; instances need 5 mm between them with supports off")
  did not appear, and the red gusset was half outside the view, which is not zoomed again
  after arming.
- **Why:** the scenario strip is how the owner sees each error's wording; with these parts
  it shows another one. It is the mockup's fidelity, not the wizard's design.
- **Smallest fix:** when arming, skip a pair whose outlines already touch, and zoom to the
  instances afterwards.

### L5. The summary's second line grows 4 px when the pill appears

- **Where:** Settings step, every width, the first change made or the last one cleared.
- **What:** the plate summary is 36.8 px tall without the "+1 change" pill and 40.8 px
  with it, so everything under it, the menu just used included, moves down 4 px at the
  first change and back up when the changes are cleared.
- **Why:** a control that moves as it is used. Small, but it is new with the two-line
  summary.
- **Smallest fix:** give the second line the pill's height always (`min-height: 21px` on
  `.sum-set`).

### L6. "Arranged 5 instances, turning 5." is still there on coming back to the Layout step (taste)

- **Where:** Layout step, every width: press Arrange, go to Settings, turn Supports on,
  come back. [Screenshot](screenshots/review-8-stale-arranged-note.png).
- **What:** the green message of the earlier Arrange is shown above "5 instances are
  closer than 12 mm with supports on."
- **Why:** an old success above a new error reads as a contradiction. The message also
  goes against the feedback's wish for a quieter Layout step, though the feedback did not
  name it. Not new in version 7.
- **Smallest fix:** clear the message when the user leaves the Layout step.

## Checked and found right

- **Units:** the plate line, spacing in errors ("… are 6 mm apart; instances need 12 mm
  between them with supports on."), "Not sliced: with Supports on, instances need 12 mm
  between them.", heights above the plate in slicing errors, the layer readout and its
  spoken text are in millimetres with inch parts; a part's size, the selection line and
  the patch tooltips are in the part's units.
- **The printer:** Free after another user's and after this user's print; Failed after a
  failed one; the details' line "(you)" for this user's own; Send offered again at once
  with the plate-clear reminder.
- **The handle after a turn:** it stays with the instance through a move, a zoom and
  **Whole plate**, and when a second instance is added to the selection; it moves clear
  of patches when the drag ends and when the instance is laid another way.
- **Back and Next,** the step circles (by click, Enter and Space) and pills, and the "X
  first: …" line under them, in every state walked.
- **Text:** role words none; help text on the working screens is one line under the upload
  area and the "?" list; error texts are specific to their error.

## The builder's result, checked

[The result](result.md) was read after the findings above were written.

- **Every "Yes" in its tables holds** in the walks above. Its counts of bounding-box patches
  (pulley and spacer four each, rib three, the others none) are the ones found here.
- **"The handle's position in the instance's own frame moved 0.00 mm"** is true as
  measured: its walk waited 40 ms after each pointer step and then read the position. Read
  at the frames the view draws, the handle leads by one update (L1). The result says
  itself that the walk cannot judge how the drag feels.
- **Choice 1, Shift counts from where the drag started,** is M2: recorded as a choice, and
  worth the owner's answer because of what it leaves no way to do.
- **Choice 5, the rib's three bounding-box patches,** is L2 and the open question M29; its note
  that the two end patches could not be pressed in its walk matches what was found here.
- **Decision 54, an instance's height in its part's units in the too-tall error,** is M1.
- **Choice 14:** the builder did not use the session named in `$PLAYWRIGHT_CLI_SESSION`
  because another session might be using it. This review used that name, as its brief
  says; the browser was closed once from outside between two walks, was reopened, and the
  interrupted walk was run again from its start. No result is affected.
- `DECISIONS.md` has "What changed in version 7" at the top; M19, M20, M27 and M28 are
  folded into the decisions and listed as answered; M29 is the one new question. The
  lay-on-face note has its section on bounding-box patches, with the rule and what the
  real wizard would need beyond it. The feedback file is deleted and no link to it is
  left.
