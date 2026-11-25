# PenguinSlicer mockup: decisions and fakes (version 6)

The mockup is [index.html](index.html) in this folder; serve the folder with any static
file server and open it. It is a throwaway: its only product is your reactions.

It imitates PenguinCAM's wizard (`templates/wizard.html`, `static/wizard.js`,
`static/wizard.css` in PenguinCAM), and printer delivery as
[its guide](../../../delivery/README.md) describes it. Where those did not decide
something, the mockup had to; each such decision is listed below as the choice made.

This file says "user" for the person using PenguinSlicer and "administrator" for whoever
edits the configuration.

## What changed in version 6

Built from the owner's review of version 5 (Tue 2026-11-24). The Layout step was not
reviewed and changed only where the points below reach it.

- **Step 2 is the Settings step** (it was Setup): Parts, Settings, Layout, Preview, Send.
- **No role words.** No text a user sees says "student", "mentor" or "team"; where a
  permission matters, it says "administrator". "For a mentor" on a message is now
  **Details**. The configuration's name, "6238 (Popcorn Penguins)", stays.
- **Little help text, generous errors.** The line under every step title is gone, and so
  are the instructions under controls. What stays is a short line where an action has a
  consequence the user cannot see. Error messages keep what is specific to the error and
  lose generic advice ("check that this computer is online", "tell a mentor").
- **Units.** A part picked in Onshape has the units of its Part Studio or Assembly; an
  uploaded file is read in inches unless the configuration says millimetres. The plate's
  size stays in millimetres; spacing and heights are in inches when every part on the plate
  is in inches, else in millimetres; slicer settings are always in millimetres. Inches are
  decimal to three places: 2.000 × 2.000 × 0.188 in. The mock document has a Part Studio
  in inches and a metric one; the scenario strip has the configuration's option for
  uploads.
- **Arrange and the placement check** keep instances 12 mm apart with supports on and 5 mm
  with them off, from the Settings step's Supports.
- **Parts step:** the prompt says only "Click a part in the Part Studio" (or "in the
  assembly") and never changes; no ↻ on a row; no "Add every part in the assembly".
- **Settings step:** no printer row; the chips row as on the Layout step; each filament has
  its own profiles; a caution under the Profile menu once a setting is changed; the quick
  changes one per row below 480 px, two from 480 px; the changes box takes the Advanced
  mode button's place, with one button and each line a link into advanced mode.
- **The "+1 change" chip** opens the list of changes, joined to the chip, on every step
  where it shows.
- **Advanced mode:** no search, no Common / All switch, no "Changed only"; every setting in
  collapsed groups; an accordion of sections below 480 px, a rail from 480 px; one column,
  at most 480 px wide; an Expand all / Collapse all icon; chevrons; "Profile 0.012 mm"
  and a Reset link under a changed setting.
- **Preview step:** two colours, the parts in the filament's colour and supports in light
  grey; the key "Part · Supports" only with supports on; no hiding of line types.
- **Printer-status icon:** the details open joined to the icon, with basic information only;
  nothing says "behind its estimate" or "late", here or on the Send step.

## What changed in version 5

- **Lay on face as Orca Slicer does it:** *Faces on the hull (like Orca)*, the default
  (decision 49 and [the algorithm note](../../research/2026-11-21-lay-on-face-hull-faces.md)).
- **Round parts are offered their sensible faces only**, by one rule of the mockup's own.
- **Parts first**, then the second step (now Settings); the wizard opens on the Parts step.
- **The Preview step no longer breaks the print time down by line type.**

Version 4 brought PenguinCAM's look, the fluid width, the Send step, the printer-status
icon, coming back to running work and parts that fail to arrive as notifications.

## Terms

Each term has one meaning in the mockup and in this file.

| Term | Meaning |
|---|---|
| **user** | The person using PenguinSlicer. |
| **administrator** | Whoever edits the configuration and pairs the printer. |
| **configuration** | The settings the header names ("Config: 6238 (Popcorn Penguins)"): the printer, the filaments, each filament's profiles, and the units of uploaded files. An administrator sets it once for everyone who uses it. |
| **Parts step, Settings step, Layout step, Preview step, Send step** | The wizard's five steps, in that order (steps 1 to 5). |
| **part** | One distinct solid, from Onshape or from an uploaded file. |
| **instance** | One placement of a part on the plate, labelled `Name #n`. |
| **plate** | The printer's build plate and everything on it. |
| **plate configuration** | What is sliced: the parts, where each instance sits, the profile and the changes. |
| **profile** | A named set of slicing settings in the configuration, such as Structural. Each filament has its own. |
| **change** | One setting set differently from the profile, on the Settings step or in advanced mode. |
| **changes box** | The yellow box on the Settings step that lists the changes; it takes the Advanced mode button's place once there is a change. |
| **change details** | What a click on the "+1 change" chip opens, joined to the chip: the changes as plain text. |
| **caution** | The one line with ⚠ under the Profile menu while there are changes. |
| **advanced mode** | The view that fills the panel with every slicing setting. |
| **section** | One of advanced mode's five top divisions, as in Orca Slicer: Quality, Strength, Speed, Support, Others. |
| **group** | A collapsible set of settings inside a section, such as Precision. |
| **accordion** | Advanced mode below 480 px: the sections as headings, one open at a time. |
| **rail** | Advanced mode from 480 px: the section names in a column down the left. |
| **units of a part** | Inches or millimetres: the units of the Part Studio or Assembly it was picked in, or the configuration's units for uploads. |
| **layout units** | The units of spacing and heights on the Layout and Preview steps: inches when every part on the plate is in inches, else millimetres. |
| **slice job** | One plate configuration being sliced by the slice service. |
| **delivery job** | One sliced file's way from Send to the end of its print (printer delivery's term). |
| **printer-status icon** | The small pill at the right of the header: a printer, a dot and a word. |
| **printer details** | What a click on the printer-status icon opens, joined to it. |
| **busy printer** | The printer printing, receiving or waiting for a person on another user's delivery job. |
| **notification** | A card at the top of a step, closed with ×, that reports something not on a row: a part that did not arrive, a resumed session. It belongs to that step and goes when the user leaves it. |
| **scenario strip** | The yellow mockup controls above the page. It is not part of the product. |
| **resting position** | One way an instance can lie on the plate: one flat outside face of its part down, stable (its centre of mass above what touches the plate). |
| **rotation handle** | The round handle beside the selection on the Layout step that turns it about the vertical. |
| **resting-position strip** | A row of small pictures under the Layout step's 3D view, one per resting position of the selected part. The scenario strip calls it **Pictures under the view**. |
| **convex hull** | The closed convex shape that wraps a part as tightly as it can, as a rubber skin would; it bridges holes and hollows. |
| **hull patches** | Translucent rounded patches on the selected instance's faces that lie on its part's convex hull; a click lays it on that face. The scenario strip calls them **Faces on the hull (like Orca)**. |
| **face markers** | Small amber arrows (↓) on the selected instance's candidate faces. The scenario strip calls them **Arrows on the part's faces**. |
| **box tumbler** | A box around the selected instance whose sides are clicked (or the box dragged) to put that side down. The scenario strip calls it **Box around the part**. |
| **tip handle** | A second handle (⤵) beside the rotation handle that steps the instance to its next resting position. The scenario strip calls it **Tip handle**. |
| **Like Onshape, Like a slicer, Top-down first** | The three mouse schemes, as the scenario strip's **Mouse** menu names them. |
| **status line** | The one line just above the 3D view on the Layout step: green when every instance fits, red with the first problem when not. |
| **layer preview** | The 3D view of the sliced plate on the Preview step, with its layer bar. |

The Layout step's two buttons, **Arrange** (place every instance on the plate) and
**Auto-orient** (lay instances their best way), are named where they are described below;
they are buttons that may change, not terms.

A user never reads the word "job": what is sliced and printed is a **plate**, named in
words ("Plate 1, 16 instances"), never by the sliced file's generated name. "Slice job" and
"delivery job" are terms of this file and of the services, not of the panel.

## Please react to these

Each answerable in a sentence. The numbers are the ones you have seen before; the questions
you answered (M4, M5, M8, M9, M10, M12, M13, M14, M15, M24, the step's name, the Arrange
spacing and decision 47) are built in below and no longer listed. New questions start at M25.

| # | Question |
|---|---|
| M1 | **Lay on face: which one?** *Faces on the hull (like Orca)* (the default since version 5), *Pictures under the view*, *Arrows on the part's faces*, *Box around the part*, or *Tip handle* (scenario strip, **Lay on face**)? Try each on the L Bracket, the Shooter Hood Rib and a round part such as the HTD Pulley 24T. |
| M2 | **Mouse: which one?** *Like Onshape*, *Like a slicer*, or *Top-down first* (scenario strip, **Mouse**)? |
| M3 | **Parts arrive: lying their best way, or as modelled** (scenario strip, **Parts arrive**)? |
| M6 | **Arrange and Auto-orient stay two buttons.** Right, or should Arrange always auto-orient first? |
| M7 | **The status line** above the Layout view: does one line say enough, with the full sentences below? |
| M11 | **Print progress on the Send step:** stages (Sending, Starting, Heating, Printing, Done), percent, layer of total, time left, expected finish and sent at. What else would a user standing at the printer want, or what can go? |
| M16 | **Orca's other layout tools** (scale, cut, mirror, per-part settings): which, if any, are needed? The mockup has none. |
| M17 | **Leaving the Preview step while it slices** leaves the slice running, and coming back with the same plate finds it still going or finished; a changed plate starts a new slice. Right, or should leaving stop it? |
| M18 | **A finished slice that was not sent is dropped after two hours away.** It survives a refresh and a reopened panel; after two hours the wizard opens at Parts with an empty plate and one line: "The slice of your earlier plate has expired; add its parts again to print it." Is dropping it right, and if so, how long should the server keep it? |
| M19 | **When your print ended while you were away,** the wizard opens at Parts with a notification ("Your print finished at …") and your plate is not kept. Should it keep the plate so the same parts can be printed again in one go? |
| M20 | **Five step tabs at 320 px wrap to two rows,** as PenguinCAM's tabs would. Acceptable, or shorten the tabs at narrow widths (for example the number only, with the name on the current tab)? |
| M21 | **A part still arriving does not hold Next.** If it arrives after the user has moved on, it joins the plate on the Layout step. Right, or should Next wait for arriving parts? |
| M22 | **Cancel sending** stays on the Send step while the file is on its way, before the printer starts. Keep it? |
| M23 | **Download moved** to the Send step, on the caret beside Send. Right place? |
| M25 | **An uploaded file in the other units.** STL carries no units, so a metric file uploaded where the configuration says inches arrives 25.4 times too large (it then fails the height or plate checks). Is the configuration's one option enough, or should each uploaded row get an inches / millimetres switch? |
| M26 | **"Changed only" in advanced mode** went with the search box and the Common / All switch, since the changes box, the change details and the changed counts on sections and groups already find a changed setting. Right, or bring it back? |
| M27 | **Spacing in inches reads oddly:** 5 mm is "0.197 in" and 12 mm "0.472 in" on an all-inch plate. Keep the exact conversion, or show the slice service's spacing in millimetres always, as the plate's size is? |

## Requirements on printer delivery

Things the mockup shows that printer delivery does not provide yet, or provides only in
part ([its guide](../../../delivery/README.md)).

1. **Who sent it.** A delivery job carries the Onshape display name of the user who sent
   it, and `GET /printer/status` returns it for the job going on, so every user's printer
   details and the busy printer can say "Sent by Alex Chen". Not provided today.
2. **What it is.** The delivery job carries a one-line description of the plate (for
   example "8 instances of Gusset Plate"), returned with the job, for the printer details
   while a plate is on its way and for the busy printer on the Send step. Today only the
   file name, which the user did not choose; the panel never shows it.
3. **Finding my own work after a refresh.** A page that has lost its state finds this
   user's live delivery job (today: `delivery` in `GET /printer/status` is the most recent
   job; with requirement 1 the page can tell whether it is this user's).
4. **The end time of the last print**, for "Finished 3:12 pm" (today
   `last_result.age_seconds`, ten minutes only, `LAST_RESULT_TTL_SECONDS`). How long to
   keep it is a decision for printer delivery.

**Dropped in version 6:** version 5's requirement 3, that the slicer's estimate at send
(`expected_s`) be the sliced file's own estimate kept from the send so it could be compared
with the printer's time left. Nothing shows "behind its estimate" or "late" any more.

Already provided and used as is: paired or not (`paired`), offline (`online`,
`age_seconds`, `delivery.daemon_silent`), sending (`uploading`, with a fraction),
starting, printing with percent, layer, total layers and time left, waiting for a person
with what to do at the printer (`waiting_for_person`, `waiting_label`, `at_the_printer`),
finished, failed, the job slot (one job; nothing queues; `delivery.printer_busy` refuses a
send to a busy printer), and cancel before the start gate.

**On the slice service** (not printer delivery): a page that has lost its state finds this
user's running or finished slice job and its plate configuration, to resume on the Preview
step. Not provided today. The slice service's spacing between instances is 12 mm with
supports on and 5 mm with them off, as the mockup uses it.

**On the configuration and the Onshape source:** the configuration lists the profiles of
each filament (not one list for all), a colour for each filament for the layer preview, and
the option that makes millimetres the units of uploaded files. The Onshape source gives
each part the units of its Part Studio or Assembly, failing that the part's own units or
Onshape's default units, whichever the API gives.

## Open facts, not decisions

- **How wide the real panel can be dragged.** Onshape publishes no limits. The mockup allows
  300 to 900 px.
- **Whether the panel stays open across Onshape tabs.** The mockup keeps the wizard's plate
  when the user moves between the document's two Part Studio tabs; Onshape's behaviour is
  unverified.
- **Full screen inside Onshape**, **an element tab beside the panel**, **Onshape's trackpad
  gestures** and **Onshape's default mouse**: unverified.
- **Speed in Onshape** of auto-orient and Arrange on real parts: unmeasured.

## Every decision

### Whole panel

1. The look is PenguinCAM's light theme, copied from its CSS: background `#f6f8fa`, cards
   `#ffffff`, controls `#eef1f4`, lines `#d0d7de`, text `#1f2328` and `#5a6570`, accent
   `#2f81f7`; body text 14 px with line height 1.45 in PenguinCAM's font stack; step tabs
   and chips 12 px with PenguinCAM's paddings; step title 18 px; buttons 8 px by 14 px,
   radius 6 px; body padding 14 px. Two departures: amber text is `#9a6700` (PenguinCAM's
   `#d29922` is hard to read on white; the borders keep `#d29922`), and a step tab's hover
   is light.
2. The header: "PenguinSlicer", the printer-status icon at the right of the same line,
   "Config: 6238 (Popcorn Penguins)" with the reload glyph, then the step tabs.
3. The step tabs are PenguinCAM's: number, name, and a check mark after the name of a
   finished step. A click on a tab goes there when every step before it allows. At 320 px
   the five tabs wrap to two rows (M20).
4. **The chips row** (version 6): none on the Parts step; from the Settings step on, parts
   and instances, filament, profile and "+N changes", the same on the Settings and Layout
   steps and updated at once as the filament, profile or a setting changes; the plate area
   from the Preview step on; print time and grams on the Send step. The plate area is in
   the layout units. **The "+1 change" chip is a button** on every step where it shows. A
   click opens the change details joined to the chip, as the printer details are joined to
   their icon: one plain-text line per change in the changes box's wording ("Quality ›
   Resolution: 0.014 mm (profile 0.012 mm)"), no links. A click elsewhere, Escape or the
   chip again closes them.
5. Next is disabled until the step's rules pass, and the step says why. A part still
   arriving never holds Next (M21).
6. The panel's width is fluid, by container queries on the panel, so dragging it wider
   changes the layout exactly as the window would. From 480 px the Settings step puts the
   filament and profile side by side and the quick changes two per row; from 520 px the
   figures of a print sit in one row; from 680 px the parts list has two columns and the
   Send step two columns. Advanced mode has its own rule (decision 13).
7. Notifications sit at the top of a step, under the chips, until closed with × or until
   the user leaves the step.
8. The scenario strip sits above the page, never over it: three short rows, a **Fewer
   controls** button that leaves one row, and **Hide strip** that leaves a small tab. Its
   **Context** menu offers the Part Studio in inches, the Part Studio in millimetres, the
   Assembly (in inches) and the standalone page; **Configuration: uploads in** sets the
   configuration's units for uploaded files.

### Words on the panel (version 6)

58. **No role words** (version 6). No text a user sees says "student", "mentor" or "team".
    Where a permission matters, the word is "administrator" ("An administrator pairs the
    printer once, from the computer beside it"). Folded details on a message are labelled
    **Details**.
59. **Help text and error text get opposite treatment** (version 6). No line under a step
    title and no instruction under a control. A short line stays only where an action has a
    consequence the user cannot see: the caution under the Profile menu, "Files are read in
    inches." under the upload area, "Slicing goes on if you step back; change the plate and
    it starts again." on the slicing card, "Check that the plate is clear and PETG is
    loaded. Send starts the print at once." on the Send step, and "Send comes back when the
    printer is free; nothing queues." on a busy printer. Tooltips carry the rest. Errors say
    what went wrong and what is specific to it (which part, what about it, where to look),
    never generic troubleshooting or internals.

### Parts step (step 1)

The wizard opens on this step. Back is off here.

14. A click on a part in Onshape adds it with quantity 1. **A click on a part already in
    the list raises its quantity by one and flashes its row** (M14). **The prompt above the
    list says only "Click a part in the Part Studio" or "Click a part in the assembly" and
    never changes**; only the list updates (version 6).
15. A part arriving shows on its row with a thin progress bar ("Arriving from Onshape…").
16. **Onshape cannot export a part** (a broken part): a notification names the part and
    says what to check in Onshape (one closed solid, not a surface, not several bodies; the
    Part Studio rebuilds with no red features). The part is not added, Next stays enabled,
    and there is no Try again. "Your other parts are fine" is said only while the list holds
    other parts. A second failure of the same part replaces its notification.
17. **Our server cannot be reached:** the page retries quietly; the row shows the part
    arriving with progress, then "Taking longer than usual; still trying…" after 4
    seconds; after 20 seconds of failed retries a notification says the part was not added
    and to click it in Onshape again (on the standalone page: upload the file again). The
    list never holds a broken row.
18. **No refresh button on a row** (version 6). A part changed in Onshape is removed and
    added again. A row keeps its picture, name, size, quantity and remove button.
19. A file that cannot be read on the standalone page is a notification and is not added.
20. The not-watertight warning stays on its row, in amber, and does not block.
21. **In an Assembly, a click on an instance adds its part,** in the list of instances or in
    the graphics area; there is no button that adds every part (version 6).
22. A plate holds up to 150 instances, the slice service's limit; quantities clamp there.
23. A part that arrives after the user left the Parts step joins the plate on the Layout
    step: at once if the user is there, else the next time it is shown (M21).

### Units (version 6)

50. **A part picked in Onshape has the units of its Part Studio or Assembly.** In the mock
    document, Part Studio 1 is in inches (L Bracket, HTD Pulley 24T, Hex Bore Spacer 1in,
    Gusset Plate, Shooter Hood Rib, 1/2in Hex Shaft) and the Part Studio "Camera Mount (mm)"
    is metric (the Camera Mount). The Assembly is in inches, so every part picked there,
    the Camera Mount too, is in inches. The wizard never guesses units from a part's size.
51. **An uploaded file is read in inches** unless the configuration makes millimetres the
    default. One line under the upload area says which ("Files are read in inches.").
52. **The Parts step shows each part's size in its own units:** "2.362 × 1.181 × 1.575 in"
    or "70 × 40 × 50 mm".
53. **Inches are decimal, to three places,** as a US machinist reads a drawing: "2.000 ×
    2.000 × 0.188 in", "0.472 in apart". Millimetres keep the precision version 5 had
    (sizes to 0.1 mm, heights and spacing to 1 mm, distances to 0.1 mm).
54. **The layout units:** spacing and heights on the Layout and Preview steps (the selected
    instance's size and height, the status line and its sentences, the hull patches'
    tooltips, the resting-position strip, the plate-area chip, the layer readout, the height
    in a slicing error) are in inches when every part on the plate is in inches, otherwise
    in millimetres.
55. **The plate's size stays in millimetres,** as Bambu Lab gives it ("plate 340 × 320
    mm"). The printer's height limit is part of the line "instances up to 13.386 in tall"
    in the layout units, and a too-tall sentence gives it in both: "the printer prints up to
    13.386 in (340 mm)".
56. **Slicer settings are always in millimetres** (layer height, line width, hole
    compensation and the rest), as in Orca Slicer and the profiles, whatever the parts'
    units; so is Orca Slicer's own sentence quoted in a slicing error's details.

### Settings step (step 2)

Called Setup until version 5; the decisions keep their numbers.

9. **No printer row** (version 6): the printer-status icon already says it. Who is
   printing is said only in the printer details (this settles decision 47's question).
10. **Four filaments, each with its own profiles** from the configuration (version 6):
    Bambu PETG HF (Structural, Pulley, Camera mount, Draft, Fine), Bambu PETG-CF (Stiff
    bracket, Light and stiff, CF draft), Bambu PLA Basic (Fit check, Jig, Display) and
    Generic TPU 95A (Bumper, Grip pad). The Profile menu offers the chosen filament's
    profiles; picking another filament picks its first profile. A profile's purpose is its
    option's tooltip, not a line under the menu.
11. **Changing the filament or the profile clears every change** (M13, refined in version 6:
    changing the filament changes the profile). From the first change until the changes
    are cleared, the caution under the Profile menu says so: "⚠ Changing the filament or the
    profile clears your 2 changes." Nothing is said after they are cleared.
12. **The quick changes** (Infill, Walls, Supports, Brim) are one per row, full width, below
    480 px and two per row from 480 px. They and advanced mode edit one shared set of
    changes. **Once a setting is changed, the changes box takes the Advanced mode button's
    place:** "2 settings changed from Structural", one line per change, each line a link
    that opens advanced mode at that setting (its section and group open, the setting
    scrolled into sight and flashed), and one button, "Advanced mode". No "Reset all" in the
    box. With no change, the Advanced mode button stands alone.
13. **Advanced mode** (version 6) fills the panel, its top line repeating "PenguinSlicer"
    with the printer-status icon. No search box, no Common / All switch, no "Changed only"
    (M26): every setting of the sample is shown, in groups that start closed (a group
    holding a change starts open). **Below 480 px, an accordion:** each section a bold
    heading with a chevron and its changed count ("Strength · 1 changed"); opening one shows
    its groups, one level in, with the same chevrons; one section is open at a time; the
    Expand all / Collapse all icon sits at the right of the open section's heading. **From
    480 px, a rail** of section names down the left, with a changed count on each, and the
    open section's groups beside it; the icon sits at the top right of the groups. **The
    groups are always one column,** at most 480 px wide, so each value stays near its name
    (this settles M5). **Expand all / Collapse all** is one icon button, a double chevron
    (unfold more, unfold less), with the tooltip "Expand all" or "Collapse all". **A
    group's heading** starts with a chevron pointing right when closed and down when open,
    and shows no count of its settings, only a changed count when it has changes
    ("Precision · 1 changed"). **A changed setting** keeps its tinted background, the bar
    on its left and the dot after its name; the line under it says "Profile 0.012 mm" and
    then a "Reset" link that puts the profile's value back. Advanced mode keeps its own
    "Reset all", which asks once more. Range checks stay. Changes last for this page load.

### Layout step

24. The Layout step does not change the list of parts: no Duplicate, Delete, Undo or Redo,
    and Delete, Ctrl+D, Ctrl+Z and Ctrl+Y do nothing. Back from the Layout step goes to the
    Settings step. Since version 6 there is no line under the title; "go to the Parts step
    to change how many of a part" is in the folded "More ways to move and look".
25. **The 3D view fills the panel's width and grows as the panel is widened** (M8): square
    at narrow widths, 4:3 from 520 px, with no height cap.
26. **Laying an instance down never moves another instance** (M9). An instance that no
    longer fits where it stood moves to the nearest free spot, turned if need be; if there
    is none, it waits beside the plate, marked off the plate, and the message says to press
    Arrange to make room.
27. Everything else is as version 3: no modes; the mouse schemes (M2); the ways to lay an
    instance on a face (M1; see decision 49); auto-orient on arrival (M3); Arrange with its
    two packers and its offer to lay instances their best way when that fits more (M6); the
    status line (M7); the rotation handle drawn over everything; the placement rules of the
    slice service (decision 57, 3 mm inside the edge, 340 mm tall).

### Arrange spacing (version 6)

57. **Arrange and the placement check follow the Settings step** (version 6): instances are
    kept 12 mm apart with supports on and 5 mm with them off, the slice service's spacing
    for that setting. Turning supports on after arranging moves nothing; instances now too
    close get the usual sentence ("… are 0.245 in apart; instances need 0.472 in between
    them with supports on.") until the user presses Arrange or drags them. The line under
    the view says the spacing and whether supports are on.

### Preview step

28. Entering the Preview step starts the slice; coming back with the same plate shows the
    result without slicing again.
29. **Leaving the Preview step while it slices leaves the slice running** on the server
    (M17); coming back with the same plate shows its progress, and a changed plate cancels
    it and starts a new one.
30. Slicing progress is version 3's card: ring gauge, percent and stage, elapsed and time
    left, bar, list of stages, Cancel slice, and the one line "Slicing goes on if you step
    back; change the plate and it starts again."
31. **While the server cannot be reached, Cancel slice is disabled** (M15), with one line
    saying the server cannot be reached and the slice may still be running.
32. Each slicing failure is one sentence of what happened and one of what to do, with its
    buttons; there is no line under the step title (version 6). Exactly three messages have
    folded **Details**: the empty-layers and faulty-mesh slice failures (Orca Slicer's own
    sentence with the heights, and where to look on the part), and the failed print on the
    Send step (where the printer's screen shows the fault, and what to check in the
    filament path and the nozzle). A timeout suggests a profile with thicker layers (the
    filament's profiles differ, so it no longer names Draft).
33. **The result:** print time and grams, a quiet line of instances, layers and slice time,
    and the layer preview with its layer bar. **Two colours** (version 6): every line of the
    parts (walls, infill, surfaces, brim) in the filament's colour, and supports with their
    interface in light grey. The key, "Part · Supports", shows under the view only when
    supports are on. No line type can be hidden. How to turn, pan and zoom the view is its
    tooltip.
34. Next goes to the Send step once the plate is sliced.

### Send step

35. The step shows what will be printed (printer with its state, the instances by part,
    print time, grams of filament) and one line: "Check that the plate is clear and PETG is
    loaded. Send starts the print at once." There is no line under the step title
    (version 6).
36. **The Send button sends at once** (M10). It is PenguinCAM's final action: a wide blue
    button with a caret, whose menu offers Download instead (M23). Choosing from the menu
    changes the button; it does not act.
37. After sending, the step shows the delivery and print progress at the top: the stage on
    a track (Sending, Starting, Heating, Printing, Done), percent, layer of total, time
    left, expected finish and sent at. The card names the plate in words ("Plate 1, 16
    instances, on Shop H2S"), never by the sliced file's name. The disabled button follows
    the phase ("Sending…", "Heating…", "Printing…", "Waiting for a person…"). While the
    plate is on its way, **Cancel sending** is offered (M22).
38. **Pausing or stopping a print is done at the printer's screen** (M12); the panel offers
    neither. Since version 6 the card no longer says so.
39. A print that waits for a person (filament ran out, door open) shows what to do at the
    printer, in amber; it is never an end.
40. A finished or failed print says so on the card; Send is enabled again for the same
    sliced plate.
41. **A busy printer** (another user's print or send): a card says whose, what, how far
    (percent, layer), the time left and the expected finish; Send is disabled; the sliced
    plate stays ready; nothing queues, and one line says "Send comes back when the printer
    is free; nothing queues."
42. An offline printer and no printer paired each disable Send with a message and
    Download. With no printer paired, nothing on the step names a printer: "No printer is
    paired with PenguinSlicer, so nothing can be sent. An administrator pairs the printer
    once, from the computer beside it."

### The printer-status icon

43. On every step, the right of the header: a printer, a dot and a word. Free (green),
    Sending 40% (blue, pulsing), Heating or Printing 61% (blue, pulsing), Waiting (amber),
    Finished (green), Failed (red), Offline and No printer (grey). Nothing says "late"
    (M24).
44. **A click opens the printer details as part of the icon** (version 6): a tab that
    expands from it, the icon turning white and joining the panel below it. Basic
    information only, under the printer's name:
    - Free: "Nothing is printing."
    - Another user sending: as version 5 (the plate's description, sent by, sending
      percent, time left, expected finish and a bar), less the estimate row and the note.
    - Printing or heating: sent by (the Onshape name, with "(you)" for this user), percent
      done, time left and expected finish; nothing more.
    - Waiting for a person: sent by, percent done, and what to do at the printer, in amber.
    - Finished or failed: sent by, and when it finished or stopped (and at which layer).
    - Offline: "Not heard from for 7 minutes."
    - No printer paired: "PenguinSlicer needs to be paired with a printer." and a link,
      "How to pair a printer", to a documentation page still to be written.
    A click elsewhere, Escape or × closes it.

### Coming back to running work

45. The scenario strip's **Refresh page**, **Close and reopen** and **Come back 2 h later**
    throw away the page's state; what the server holds stays: this user's slice job and
    plate configuration, and the printer.
46. When this user's slice is running, or finished and not sent, the wizard reopens on the
    Preview step with the parts and layout restored; when this user's delivery job is
    running, it reopens on the Send step with live progress. A notification says "Back
    where you were" and, in the past tense, what the plate was doing when the user left.
47. Otherwise it starts at the Parts step. Another user's work shows in the printer-status
    icon, which is on every step and so is the first thing seen; their name is in the
    printer details only.
48. After two hours away, a finished unsent slice is gone (M18), and a one-line
    notification on the Parts step says the slice of the earlier plate has expired; a print
    of this user's that ended meanwhile is reported in a notification on the Parts step
    (M19), which adds that the parts were not kept.

### Lay on face: faces on the hull (version 5)

49. *Faces on the hull (like Orca)*, the default way to lay an instance on a face, follows
    Orca Slicer's Lay on face tool as [the algorithm note](../../research/2026-11-21-lay-on-face-hull-faces.md)
    describes it: the faces of the part's convex hull, with Orca's filters (at least 5 mm²,
    no sliver corners, the 254 largest), plus one rule of the mockup's own for round parts
    (a face is left out when a neighbouring hull face bends away from it by less than 20
    degrees and is at least half its size). Choices made:
    - **Opening it is selecting one instance**: no button and no mode. With two or more
      instances selected, no patches show, as Orca shows them for one instance only.
    - **Colours:** PenguinCAM's accent blue `#2f81f7` at 22% opacity, 55% under the pointer.
    - **Only the patches in sight are drawn and clickable.**
    - **The face the instance lies on has no patch.**
    - **The rotation handle keeps clear of the patches:** it moves round the selection, 45
      degrees at a time, to the first side where it covers no patch in sight.
    - No test of whether the instance would tip over on a face, as in Orca. The real wizard
      should test it (the auto-orient code already does).

## What is fake and could mislead

1. Toolpaths are generated shapes, not Orca's output; print time and grams are estimates
   from them.
2. Slicing time, stage durations and percentages are invented formulas.
3. Nothing is exported from Onshape; an export takes about a second; the server outages
   last 9 seconds (slow) or 20 (down) on the real clock; an uploaded file is never read.
4. The printer, Alex Chen, his gusset plate, the waiting reasons, the failure reason and
   every time are invented. A person "resumes at the printer" after 10 mock minutes.
5. Times of day are this computer's clock plus mock time; at Fast speed a print runs 900
   times faster and another user's 30 times, so the clock jumps ahead.
6. The Printer menu in the scenario strip sets the printer outright.
7. "Come back 2 h later" moves the page's clock and the printer forward two hours at once.
8. The notification after a refresh, and what is restored, imitate requirements on printer
   delivery and the slice service that do not exist yet.
9. The plate-volume cap (600 cm³) is invented; armed "plate too large" lowers it for one
   plate and says so in a mockup note.
10. Hulls are thinned to 40 points; placement distances can be off by about 0.2 mm.
11. Download saves nothing.
12. The page around the panel is not Onshape.
13. Advanced mode shows a sample of Orca's settings (95 of about 295).
14. Auto-orient scores flat outside faces of the mock parts only; "overhangs" uses an
    invented threshold.
15. *Top-down first* uses a perspective camera, not an orthographic one.
16. Cancel sending always works at once; a real cancel may arrive after the printer has
    started.
17. The panel's drag limits (300 to 900 px) are the mockup's, not Onshape's.
18. Fonts: PenguinCAM's stack starts with the system font, so screenshots taken on Linux
    show Liberation Sans or DejaVu Sans, not San Francisco.
19. The hull patches are worked out from the mock parts' generated meshes, in the browser.
20. **The mock parts were drawn in millimetres,** so the "inch" parts have sizes that are
    not round in inches (the L Bracket is 2.362 × 1.181 × 1.575 in). A part drawn in inches
    would show 2.000 × 1.000 × 1.500 in.
21. The second filaments' profiles, their values and the filament colours are invented.
22. The "How to pair a printer" link goes nowhere; the page is still to be written.
23. Each file uploaded on the standalone page becomes one of the mock parts, whatever its
    name; the units it is read in are the configuration's option at the moment of upload.
