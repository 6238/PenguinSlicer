# PenguinSlicer mockup: decisions and fakes (version 7)

The mockup is [index.html](index.html) in this folder; serve the folder with any static
file server and open it. It is a throwaway: its only product is your reactions.

It imitates PenguinCAM's wizard (`templates/wizard.html`, `static/wizard.js`,
`static/wizard.css` in PenguinCAM), and printer delivery as
[its guide](../../../delivery/README.md) describes it. Where those did not decide
something, the mockup had to; each such decision is listed below as the choice made.

This file says "user" for the person using PenguinSlicer and "administrator" for whoever
edits the configuration.

## What changed in version 7

Built from the owner's review of version 6 (Wed 2026-11-25). Nothing else changed.

- **The rotation handle is bound to the instance** (decision 62). Dragged, it sits on a
  circle round the selection at the radius it had when the drag started and turns with the
  instance through the same angle, so the two never part; it never hops to another side
  while dragged. Turning is free, with a readout beside the handle ("↺ 37°"); **Shift**
  turns in 45° steps. The tooltip says "Drag to turn · Shift: 45° steps". Version 6's
  5-degree catch round each 45° is gone.
- **Round parts can be stood on their rim** (decision 61): where no kept hull face points
  within 30° of a side of the part's bounding box, a **bounding-box patch** lies on that
  side; a click lays the instance on it. The HTD Pulley 24T and the Hex Bore Spacer 1in get
  four each; the boxy parts get none.
- **No text about orientation** on the Layout step: no line under the orientation controls,
  no "… now lies …" or "… already lies that way" after laying an instance down, nothing
  when parts arrive laid down automatically. Only a move the wizard made (an instance moved
  to a free spot, or left beside the plate) is said. The help list no longer says how to
  change a quantity.
- **Printer and plate figures are always in millimetres** (decisions 54 and 55): the line
  under the view ("Shop H2S: plate 340 × 320 mm, up to 340 mm tall, 12 mm apart"), the
  spacing in errors and the layer readout on the Preview step. Only a part's own size (and
  an instance's height) follows its part's units. This settles M27 and M28.
- **The printer is Free as soon as a print finishes**; the icon never says "Finished"
  (decision 43). The printer details add "Last print finished 11:25 am (Alex Chen)"; the
  user's own print that finished is one line, "Your print finished at 11:25 am.", not a
  card (decision 60). Both go when another plate is sent or 12 hours after the print
  finished. This answers M19. The scenario strip gains **12 hours later**.
- **The step tabs below 480 px are numbered circles** joined by a line, the current one
  with its name (decision 3). This settles M20.
- **The plate summary is two lines of text** (decision 4): parts and instances, then the
  filament and profile with the "+2 changes" pill. The plate-area and the time-and-filament
  chips are gone.
- **Advanced mode below 480 px:** each section is a bordered card (decision 13). Its
  header loses "‹ Settings", and Escape no longer closes it: "Back to Settings" at the
  bottom is the only way back.
- **No "Mockup: …" notices in the panel**, and no "Loaded from your saved configuration
  link."; what the notices said is under "What is fake and could mislead" and in the
  scenario strip.

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
  uploaded file is read in inches unless the configuration says millimetres. Slicer
  settings are always in millimetres. Inches are decimal to three places: 2.000 × 2.000 ×
  0.188 in. The mock document has a Part Studio in inches and a metric one; the scenario
  strip has the configuration's option for uploads. (Version 6 also gave spacing and
  heights in inches on an all-inch plate; version 7 replaced that rule.)
- **Arrange and the placement check** keep instances 12 mm apart with supports on and 5 mm
  with them off, from the Settings step's Supports.
- **Parts step:** the prompt says only "Click a part in the Part Studio" (or "in the
  assembly") and never changes; no ↻ on a row; no "Add every part in the assembly".
- **Settings step:** no printer row; the plate summary as on the Layout step; each filament has
  its own profiles; a caution under the Profile menu once a setting is changed; the quick
  changes one per row below 480 px, two from 480 px; the changes box takes the Advanced
  mode button's place, with one button and each line a link into advanced mode.
- **The "+1 change" pill** opens the list of changes, joined to the pill, on every step
  where it shows.
- **Advanced mode:** no search, no Common / All switch, no "Changed only"; every setting in
  collapsed groups; an accordion of sections below 480 px, a rail from 480 px; one column,
  at most 480 px wide; an Expand all / Collapse all icon; chevrons; "Profile 0.012 mm"
  and a Reset link under a changed setting.
- **Preview step:** two colours, the parts in the filament's colour and supports in light
  grey; the key "Part · Supports" only with supports on; no hiding of line types.
- **Printer-status icon:** the details open joined to the icon, with basic information only;
  nothing says "behind its estimate" or "late", here or on the Send step.

A review of version 6 led to one round of fixes ([review](../../orchestration/mockup-v6/review-1.md),
[fixes](../../orchestration/mockup-v6/fix-1.md)). The ones you will notice:

- **"Turn on Supports and slice again"** runs the placement check at 12 mm first; a plate
  that fails it is not sliced and the wizard goes to the Layout step (decision 57).
- **Instances too close are one error,** with how many and one Arrange button (decision 57).
- **A click on a step tab that an earlier step holds back** says why, in one line under
  the tabs (decision 3).
- **The Layout step's gestures** moved behind a "?" icon (decisions 24 and 59).
- **"480 px" in the scenario strip is now 480 px of panel,** so both "from 480 px" layouts
  show there (decision 6).

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
| **plate summary** | The two lines of text at the top of every step from the Settings step on: parts and instances; then filament and profile, and the "+1 change" pill. |
| **"+1 change" pill** | The one pill of the plate summary, shown while there are changes ("+2 changes"); a button. |
| **change details** | What a click on the "+1 change" pill opens, joined to the pill: the changes as plain text. |
| **caution** | The one line with ⚠ under the Profile menu while there are changes. |
| **advanced mode** | The view that fills the panel with every slicing setting. |
| **section** | One of advanced mode's five top divisions, as in Orca Slicer: Quality, Strength, Speed, Support, Others. Below 480 px each is a card. |
| **group** | A collapsible set of settings inside a section, such as Precision. |
| **accordion** | Advanced mode below 480 px: the sections as headings, one open at a time. |
| **rail** | Advanced mode from 480 px: the section names in a column down the left. |
| **units of a part** | Inches or millimetres: the units of the Part Studio or Assembly it was picked in, or the configuration's units for uploads. |
| **printer and plate figures** | The plate's size, the height limit, the spacing between instances, distances between instances and heights above the plate (a layer's, a slicing error's): always in millimetres. |
| **slice job** | One plate configuration being sliced by the slice service. |
| **delivery job** | One sliced file's way from Send to the end of its print (printer delivery's term). |
| **printer-status icon** | The small pill at the right of the header: a printer, a dot and a word. |
| **printer details** | What a click on the printer-status icon opens, joined to it. |
| **last-print note** | The one line "Your print finished at 11:25 am." for the user whose print finished (decision 60). |
| **busy printer** | The printer printing, receiving or waiting for a person on another user's delivery job. |
| **notification** | A card at the top of a step, closed with ×, that reports something not on a row: a part that did not arrive, a resumed session. It belongs to that step and goes when the user leaves it. |
| **scenario strip** | The yellow mockup controls above the page. It is not part of the product. |
| **resting position** | One way an instance can lie on the plate: one flat outside face of its part down, stable (its centre of mass above what touches the plate). |
| **rotation handle** | The round handle beside the selection on the Layout step that turns it about the vertical. |
| **resting-position strip** | A row of small pictures under the Layout step's 3D view, one per resting position of the selected part. The scenario strip calls it **Pictures under the view**. |
| **convex hull** | The closed convex shape that wraps a part as tightly as it can, as a rubber skin would; it bridges holes and hollows. |
| **hull patches** | Translucent rounded patches on the selected instance's faces that lie on its part's convex hull; a click lays it on that face. The scenario strip calls them, with the bounding-box patches, **Faces on the hull (like Orca)**. |
| **bounding-box patches** | Patches like the hull patches, lying on a side of the selected instance's bounding box that no hull patch covers (a pulley's rim); a click lays it on that side (decision 61). |
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
you answered (M4, M5, M8, M9, M10, M12, M13, M14, M15, M19, M20, M24, M27, M28, the step's
name, the Arrange spacing and decision 47) are built in below and no longer listed.

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
| M21 | **A part still arriving does not hold Next.** If it arrives after the user has moved on, it joins the plate on the Layout step. Right, or should Next wait for arriving parts? |
| M22 | **Cancel sending** stays on the Send step while the file is on its way, before the printer starts. Keep it? |
| M23 | **Download moved** to the Send step, on the caret beside Send. Right place? |
| M25 | **An uploaded file in the other units.** STL carries no units, so a metric file uploaded where the configuration says inches arrives 25.4 times too large (it then fails the height or plate checks). Is the configuration's one option enough, or should each uploaded row get an inches / millimetres switch? |
| M26 | **"Changed only" in advanced mode** went with the search box and the Common / All switch, since the changes box, the change details and the changed counts on sections and groups already find a changed setting. Right, or bring it back? |
| M29 | **Bounding-box patches on the Shooter Hood Rib** (version 7): the rule gives the rib three, on its outer curve and on its two ends (its end faces are 36° off the box's sides, more than the 30° that counts as covering). Standing it on an end makes it too tall for the printer, which the usual error then says. Keep the rule as it is, or widen the angle so that a part's slanted end faces count? |

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
4. **The end time and the sender of the last print that finished**, for "Last print
   finished 11:25 am (Alex Chen)" in every user's printer details and "Your print finished
   at 11:25 am." for its sender (version 7): kept until another plate is sent or for 12
   hours after the print finished. Today `last_result.age_seconds` lasts ten minutes only
   (`LAST_RESULT_TTL_SECONDS`); printer delivery keeps its final report 24 hours (R11),
   which is long enough if the report carries the end time and the sender.

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
   and the pill 12 px with PenguinCAM's paddings; step title 18 px; buttons 8 px by 14 px,
   radius 6 px; body padding 14 px. Two departures: amber text is `#9a6700` (PenguinCAM's
   `#d29922` is hard to read on white; the borders keep `#d29922`), and a step tab's hover
   is light.
2. The header: "PenguinSlicer", the printer-status icon at the right of the same line,
   "Config: 6238 (Popcorn Penguins)" with the reload glyph, then the step tabs.
3. The step tabs are PenguinCAM's from 480 px: number, name, and a check mark after the
   name of a finished step. **Below 480 px they are numbered circles** (version 7, M20), as
   in Material's compact stepper: five small circles joined by a line, a check in each done
   step, the current one filled in the accent blue with its name beside it, so the header
   stays one row and the content the user works with stays high in the panel. Every circle
   stays clickable and has its step's name as its tooltip ("3. Layout"). A click on a tab
   goes there when every step before it allows. When one does not, one line under the tabs
   names the step and why ("Layout first: 23 instances are closer than 12 mm with supports
   on."); it goes at the next move, or after a few seconds.
4. **The plate summary** (version 7, replacing version 6's chips row): none on the Parts
   step; from the Settings step on, two lines of text, the same on every step and updated
   at once as the filament, profile or a setting changes. The first line gives parts and
   instances ("1 part · 1 instance"); the second the filament and profile ("PETG ·
   Structural"), then the "+2 changes" pill. The filament and profile are cut with an
   ellipsis when too long, never wrapped (their full names are the tooltip); the pill stays
   whole. There is no plate area and no print time and grams (the Send step states those).
   **The "+1 change" pill is a button** on every step where it shows. A click opens the
   change details joined to the pill, as the printer details are joined to their icon: one
   plain-text line per change in the changes box's wording ("Quality › Resolution: 0.014
   mm (profile 0.012 mm)"), no links. A setting that has a quick change is named in the
   quick change's words ("Others › Brim: Off (profile Auto)"), so the menu and the line
   agree. A click elsewhere, Escape or the pill again closes them.
5. Next is disabled until the step's rules pass, and the step says why. A part still
   arriving never holds Next (M21).
6. The panel's width is fluid, by container queries on the panel, so dragging it wider
   changes the layout exactly as the window would. From 480 px the Settings step puts the
   filament and profile side by side and the quick changes two per row; from 520 px the
   figures of a print sit in one row; from 680 px the parts list has two columns and the
   Send step two columns. Advanced mode has its own rule (decision 13). Each "from" width
   includes itself, and the stand-in panel's border is outside its width, so the scenario
   strip's 480 px shows the 480 px layouts.
7. Notifications sit at the top of a step, under the plate summary, until closed with × or
   until the user leaves the step.
8. The scenario strip sits above the page, never over it: three short rows, a **Fewer
   controls** button that leaves one row, and **Hide strip** that leaves a small tab. Its
   **Context** menu offers the Part Studio in inches, the Part Studio in millimetres, the
   Assembly (in inches) and the standalone page; **Configuration: uploads in** sets the
   configuration's units for uploaded files. What the mockup fakes is said there (an armed
   error's option says what it does to the plate, and "How to use this mockup") and below,
   never in the panel (version 7).

### Words on the panel (version 6)

58. **No role words** (version 6). No text a user sees says "student", "mentor" or "team".
    Where a permission matters, the word is "administrator" ("An administrator pairs the
    printer once, from the computer beside it"). Folded details on a message are labelled
    **Details**.
59. **Help text and error text get opposite treatment** (version 6). No line under a step
    title and no instruction under a control. A short line stays only where an action has a
    consequence the user cannot see: the caution under the Profile menu, "STL files are read
    in inches." under the upload area, "Slicing goes on if you step back; change the plate
    and it starts again." on the slicing card, "Check that the plate is clear and PETG is
    loaded. Send starts the print at once." on the Send step, "Send comes back when the
    printer is free; nothing queues." on a busy printer, and on the Layout step the line
    under the view, "Shop H2S: plate 340 × 320 mm, up to 340 mm tall, 5 mm apart" (the
    owner's wording, version 7: printer and plate figures in millimetres whatever the
    parts' units; it no longer says whether supports are on, which the errors still say),
    kept because neither the printer-status icon nor the plate summary gives the plate's
    size, the height limit or the spacing. The Layout step's
    gestures (how to move, turn, look and lay an instance down, and the other ways that
    were under "More ways to move and look") are behind a "?" icon at the right of its
    toolbar, which opens them in a small panel; Escape or a click elsewhere closes it. This
    is for the owner's review of the Layout step. Tooltips carry the rest. Errors say
    what went wrong and what is specific to it (which part, what about it, where to look),
    never generic troubleshooting or internals. **No text about orientation** (version 7):
    the controls under the selection ("Put back as modelled", "Lay it the best way") stand
    alone, with no sentence beside them and nothing at all when the instance lies as
    modelled and that is its best way; laying an instance down, auto-orient and arrival
    laid down automatically say nothing of how it lies now (the view shows it). What is
    said is a move the wizard made that the user did not ask for: "L Bracket #1 no longer
    fitted where it stood, so it was moved to the nearest free spot.", an instance left
    beside the plate, or "Arranged the plate again to make room." after Auto-orient.

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
51. **An uploaded STL file is read in inches** unless the configuration makes millimetres
    the default. One line under the upload area says which ("STL files are read in
    inches."). A 3MF file states its own units. (The mockup reads no file, so an uploaded
    3MF row shows the configuration's units too.)
52. **The Parts step shows each part's size in its own units:** "2.362 × 1.181 × 1.575 in"
    or "70 × 40 × 50 mm". A size is rounded once, from the exact millimetres, in the unit
    shown, so a part has one size on every step (the 6.35 mm Gusset Plate is 0.250 in
    thick everywhere). A size never gets cut short: in a narrow panel it wraps.
53. **Inches are decimal, to three places,** as a US machinist reads a drawing: "2.000 ×
    2.000 × 0.188 in". Millimetres keep the precision version 5 had (sizes to 0.1 mm,
    heights and spacing to 1 mm, distances to 0.1 mm).
54. **A part's own size follows its units** (version 7, replacing version 6's layout
    units): the selected instance's footprint and height on the Layout step, the hull
    patches' and bounding-box patches' tooltips ("Lay it on this side: 1.732 in tall"), the
    resting-position strip, and an instance's height in a too-tall error are in the units
    of its part.
55. **Printer and plate figures are always in millimetres** (version 7, the owner; settles
    M27 and M28), as Bambu Lab gives them: the line under the Layout view ("Shop H2S: plate
    340 × 320 mm, up to 340 mm tall, 12 mm apart"), the spacing and distances in errors
    ("… are 3.2 mm apart; instances need 12 mm between them with supports on."), the
    printer's limit in a too-tall error ("… stands 13.885 in tall; the printer prints up to
    340 mm."), a height above the plate in a slicing error, and the layer readout on the
    Preview step ("134 / 134 · 40.2 mm").
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
    holding a change starts open). **Below 480 px, an accordion of cards** (cards since
    version 7): each section is a bordered card like PenguinCAM's cards (white, a 1 px
    `#d0d7de` border, radius 6 px), whose title is the section's bold heading with a
    chevron, its changed count ("Strength · 1 changed") and, on the open section, the
    Expand all / Collapse all icon at its right; the section's groups are rows inside the
    card, with the same chevrons but lighter type; a closed section is a slim card; one
    section is open at a time. **From 480 px, a rail** (no card there: it would make the
    settings more cramped) of section names down the left, with a changed count on each, and the
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
    **The header** (version 7) says "Advanced mode", the profile and changed count
    ("Structural, 2 changed") and "Reset all"; it has no "‹ Settings" button. **"Back to
    Settings" at the bottom is the only way back**; Escape does not close advanced mode.
    **By keyboard,** opening advanced mode puts focus on the first section's heading (or the
    line's setting, when a line of the changes box opened it), focus stays where the user
    acted (a heading, a name in the rail, a setting; after a Reset link, the setting's own
    control), what advanced mode covers cannot be reached, and closing it returns focus to
    the line or the button that opened it.

### Layout step

24. The Layout step does not change the list of parts: no Duplicate, Delete, Undo or Redo,
    and Delete, Ctrl+D, Ctrl+Z and Ctrl+Y do nothing. Back from the Layout step goes to the
    Settings step. Since version 6 there is no line under the title; since version 7 nothing
    says how to change how many of a part (the owner dropped the line).
25. **The 3D view fills the panel's width and grows as the panel is widened** (M8): square
    at narrow widths, 4:3 from 520 px, with no height cap.
26. **Laying an instance down never moves another instance** (M9). An instance that no
    longer fits where it stood moves to the nearest free spot, turned if need be; if there
    is none, it waits beside the plate, marked off the plate, and the message says to press
    Arrange to make room.
27. Everything else is as version 3: no modes; the mouse schemes (M2); the ways to lay an
    instance on a face (M1; see decision 49); auto-orient on arrival (M3); Arrange with its
    two packers and its offer to lay instances their best way when that fits more (M6); the
    status line (M7); the rotation handle drawn over everything (bound to the instance since
    version 7, decision 62); the placement rules of the
    slice service (decision 57, 3 mm inside the edge, 340 mm tall).

### Arrange spacing (version 6)

57. **Arrange and the placement check follow the Settings step** (version 6): instances are
    kept 12 mm apart with supports on and 5 mm with them off, the slice service's spacing
    for that setting. Turning supports on after arranging moves nothing; instances now too
    close get the usual message until the user presses Arrange or drags them. **Every
    instance that is too close is in one error:** a single pair is named ("… are 6.2 mm
    apart; instances need 12 mm between them with supports on."), more are counted ("23
    instances are closer than 12 mm with supports on. Press Arrange, or drag them
    apart."), with one Arrange button; each of them stays marked in the view. An instance
    Arrange left beside the plate gets no error of its own: Arrange's message already
    counts them, and the line under the view says "90 instances on the plate, 10 beside
    it." The line under the view says the spacing (since version 7 not whether supports
    are on; the errors say it).
    **"Turn on Supports and slice again"** (the empty-layers error) turns Supports on and
    runs the placement check at 12 mm before slicing. A plate that passes is sliced; one
    that does not is not sliced, and the wizard goes to the Layout step, which says "Not
    sliced: with Supports on, instances need 0.472 in between them." above the usual
    message ("Not sliced: with Supports on, instances need 12 mm between them." since
    version 7). Nothing moves by itself; Arrange is the user's choice.

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
    sentence with the heights, and where to look on the part: in Onshape, or on the
    standalone page in "your CAD program", with no word of Onshape or a Part Studio), and
    the failed print on the Send step (where the printer's screen shows the fault, and what to check in the
    filament path and the nozzle). A timeout suggests a profile with thicker layers (the
    filament's profiles differ, so it no longer names Draft).
33. **The result:** print time and grams, a quiet line of instances, layers and slice time,
    and the layer preview with its layer bar, read out under it as "134 / 134 · 40.2 mm"
    (always millimetres since version 7; one line at 320 px); the bar reports its layer to a screen reader and moves with the
    arrow keys. **Two colours** (version 6): every line of the
    parts (walls, infill, surfaces, brim) in the filament's colour, and supports with their
    interface in light grey. The key, "Part · Supports", shows under the view only when
    supports are on. No line type can be hidden. How to turn, pan and zoom the view is its
    tooltip.
34. Next goes to the Send step once the plate is sliced.

### Send step

35. The step shows what will be printed (the printer by name, its state left to the
    printer-status icon and the card or message beside it; the instances by part,
    print time, grams of filament) and one line: "Check that the plate is clear and PETG is
    loaded. Send starts the print at once." There is no line under the step title
    (version 6).
36. **The Send button sends at once** (M10). It is PenguinCAM's final action: a wide blue
    button with a caret, whose menu offers Download instead (M23). Choosing from the menu
    changes the button; it does not act. The menu's send item has the button's label ("Send
    to Shop H2S"). By keyboard, Enter on the caret opens the menu on its first item, the
    arrow keys move, Escape closes it. On this step Back keeps its own width, so it does
    not jump as the button's label changes.
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
40. A failed print says so on the card. A print that finished leaves no card (version 7):
    the last-print note takes its place at the top of the step (decision 60). Either way
    Send is enabled again for the same sliced plate, under the plate-clear reminder.
41. **A busy printer** (another user's print or send): a card says whose, what, how far
    (percent, layer), the time left and the expected finish; Send is disabled; the sliced
    plate stays ready; nothing queues, and one line says "Send comes back when the printer
    is free; nothing queues."
42. An offline printer and no printer paired each disable Send with a message and
    Download. With no printer paired, nothing on the step names a printer: "No printer is
    paired with PenguinSlicer, so nothing can be sent. An administrator pairs the printer
    once, from the computer beside it.", with the printer details' "How to pair a printer"
    link. Offline says how long since the printer was last heard from and that Send comes
    back when it answers, with no guess at the cause, as the printer details do.

### The printer-status icon

43. On every step, the right of the header: a printer, a dot and a word. Free (green),
    Sending 40% (blue, pulsing), Heating or Printing 61% (blue, pulsing), Waiting (amber),
    Failed (red), Offline and No printer (grey). Nothing says "late" (M24). **There is no
    "Finished"** (version 7): the printer reports that a print ended but cannot tell
    whether a person has cleared the plate, so once a print finishes the printer is Free
    (ruling R8), and the plate being clear is the user's check (the Send step's reminder).
    A print that failed still shows Failed: it ended on a fault someone at the printer has
    to see to.
44. **A click opens the printer details as part of the icon** (version 6): a tab that
    expands from it, the icon turning white and joining the panel below it. Basic
    information only, under the printer's name:
    - Free: "Nothing is printing.", and after a print that finished (version 7) a second
      line, "Last print finished 11:25 am (Alex Chen)", "(you)" for this user's own; the
      line goes when another plate is sent or 12 hours after the print finished.
    - Another user sending: as version 5 (the plate's description, sent by, sending
      percent, time left, expected finish and a bar), less the estimate row and the note.
    - Printing or heating: sent by (the Onshape name, with "(you)" for this user), percent
      done, time left and expected finish; nothing more.
    - Waiting for a person: sent by, percent done, and what to do at the printer, in amber.
    - Failed: sent by, and when it stopped and at which layer.
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
    notification on the Parts step says the slice of the earlier plate has expired. A print
    of this user's that failed meanwhile is reported in a notification on the Parts step,
    which adds that the parts were not kept. A print of this user's that finished is the
    last-print note on whichever step opens (decision 60; M19, version 7).

### The user's last print (version 7)

60. **The last-print note.** When this user's print finishes, one line says so, "Your
    print finished at 11:25 am.", not a card. It shows on the Send step (of the same plate
    or a new one, above the new plate's Send), and, when the user comes back to the wizard
    (a refresh, a reopened panel, hours later), on whichever step opens, until the user
    leaves that step. It goes, with the printer details' "Last print finished …" line, when
    the user sends another plate or 12 hours after the print finished, whichever comes
    first (the owner's answer to M19). Printer delivery keeps its final report 24 hours
    (R11) regardless. The scenario strip's **12 hours later** moves the clock on with the
    panel left open, to show both go.

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
      degrees at a time, to the first side where it covers no patch in sight, but only
      while no drag is going on (version 7, decision 62).
    - No test of whether the instance would tip over on a face, as in Orca. The real wizard
      should test it (the auto-orient code already does).
61. **Bounding-box patches** (version 7, the owner): the round-part rule leaves a pulley only
    its two end faces, so it could not be stood on its rim. Now each of the six sides of the
    part's bounding box, in the instance's own frame, is checked: a side is uncovered when
    no kept hull face's outward normal is within 30° of it (half a degree more for
    rounding, so the 1/2in Hex Shaft's flats, exactly 30° off, count as covering). Each
    uncovered side gets a patch styled like the hull patches (same blue, same opacity, the
    same rounded shape drawn 10% in) lying on the box's side, 0.1 mm out; its tooltip is
    "Lay it on this side: 1.732 in tall"; a click lays the instance on that side, so a
    pulley rests on its rim. A part whose hull faces cover every side gets none. In the
    mock document: the HTD Pulley 24T and the Hex Bore Spacer 1in get four each (their
    rims); the L Bracket, Camera Mount, Gusset Plate and 1/2in Hex Shaft none; the Shooter
    Hood Rib three, on its outer curve and on its two ends (M29). The rule and what the real
    wizard would need beyond it are in [the algorithm note](../../research/2026-11-21-lay-on-face-hull-faces.md).

### The rotation handle (version 7)

62. **The rotation handle is bound to the instance** (the owner). A press on it fixes, for
    the whole drag, the middle of the selection's box (the pivot), the handle's distance
    from it and its side. While dragged, the handle sits on that circle and turns with the
    instance through the same angle (snaps included), so the two never part, and it never
    hops to another side. Each instance turns rigidly about the pivot. After the drag the
    handle stays where the turn left it, fixed to the first selected instance (it follows
    a move too), until the selection changes or the instance is laid down; it moves clear
    of hull patches only when no drag is going on (when the drag ends, or when patches
    appear). **Turning is free;** a small readout beside the handle shows the turn while
    dragging, "↺ 37°" anticlockwise and "↻ 37°" clockwise as seen from above. **Holding
    Shift** (the usual modifier for constraining angles in CAD and drawing programs) turns
    in steps of 45° from where the drag started; pressing or letting go of Shift mid-drag
    takes effect at once. The handle's tooltip is "Drag to turn · Shift: 45° steps"; the
    Layout step's "?" list says "Hold Shift while turning to turn in 45° steps."

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
   plate (its option in the scenario strip says so; until version 6 a note in the panel
   did).
10. Hulls are thinned to 40 points; placement distances can be off by about 0.2 mm.
11. Download saves nothing, though the panel says "Downloaded the sliced file of Plate 1, …".
12. The page around the panel is not Onshape.
13. Advanced mode shows a sample of Orca's settings (99 of about 295).
14. Auto-orient scores flat outside faces of the mock parts only; "overhangs" uses an
    invented threshold.
15. *Top-down first* uses a perspective camera, not an orthographic one.
16. Cancel sending always works at once; a real cancel may arrive after the printer has
    started.
17. The panel's drag limits (300 to 900 px) are the mockup's, not Onshape's.
18. Fonts: PenguinCAM's stack starts with the system font, so screenshots taken on Linux
    show Liberation Sans or DejaVu Sans, not San Francisco.
19. The hull patches and the bounding-box patches are worked out from the mock parts'
    generated meshes, in the browser.
20. **The mock parts were drawn in millimetres,** so the "inch" parts have sizes that are
    not round in inches (the L Bracket is 2.362 × 1.181 × 1.575 in). A part drawn in inches
    would show 2.000 × 1.000 × 1.500 in.
21. The second filaments' profiles, their values and the filament colours are invented.
22. The "How to pair a printer" link goes nowhere; the page is still to be written.
23. Each file uploaded on the standalone page becomes one of the mock parts, whatever its
    name; the file itself is not read; the units it is read in are the configuration's
    option at the moment of upload. (Until version 6 a note in the panel said so.)
24. Armed "Instance too tall" stands a Shooter Hood Rib up as modelled, adding one from
    the same Part Studio as the first part if the plate has none; its option in the
    scenario strip says so. (Until version 6 a note in the panel did.)
25. The configuration's name links nowhere, and "↻" reloads nothing. The standalone page
    imitates opening the configuration from a saved link; the panel no longer says so
    (version 7).
26. **12 hours later** (scenario strip) moves the page's clock on by 12 hours, and further
    if a print's own clock ran ahead at Fast speed, so that a finished print is more than
    12 hours old; a print still running ends.
