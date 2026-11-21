# PenguinSlicer mockup: decisions and fakes (version 5)

The mockup is [index.html](index.html) in this folder; serve the folder with any static
file server and open it. It is a throwaway: its only product is your reactions.

It imitates PenguinCAM's wizard (`templates/wizard.html`, `static/wizard.js`,
`static/wizard.css` in PenguinCAM), and printer delivery as
[its guide](../../../delivery/README.md) describes it. Where those did not decide
something, the mockup had to; each such decision is listed below as the choice made.

## What changed in version 5

- **Lay on face as Orca Slicer does it.** The scenario strip's **Lay on face** menu has a
  fifth option, *Faces on the hull (like Orca)*, and it is the default. While one instance
  is selected on the Layout step, each face it can be laid on shows as a translucent patch
  in PenguinCAM's accent blue, with rounded corners, drawn on the faces of the closed convex
  shape around the part (its convex hull). The patch under the pointer turns a deeper blue
  and says how tall the instance would stand; a click lays the instance on that face, and
  the patches then show the new faces (the face it lies on has none). A drag that starts
  on a patch still moves the instance, and the rotation handle moves aside so that it never
  covers a patch. How the faces are found and filtered, and what the
  mockup adds for round parts, is in
  [the algorithm note](../../research/2026-11-21-lay-on-face-hull-faces.md).
- **Round parts are offered their sensible faces only.** Orca's own filters would offer 96
  thin patches round the HTD Pulley 24T's rim and the Hex Bore Spacer 1in's side and 40
  along the Shooter Hood Rib's curved edge. One rule of the mockup's own drops them: a face
  is left out when a neighbouring face of the hull bends away from it by less than 20
  degrees and is at least half its size. The pulley and the spacer are offered their two
  end faces; the rib its two sides, its two ends and the face across its inner curve.
- **Parts first, then Setup.** The steps are Parts, Setup, Layout, Preview, Send; the step
  keeps the name "Setup", as in PenguinCAM. The wizard opens on the Parts step (after Reset,
  after two hours away, and whenever there is no running work to go back to); Back is off
  on the Parts step; the chips row shows the parts from the Setup step on and the filament,
  profile and changes from the Layout step on. The Layout step's instruction now says to go
  to the Parts step (tab 1) to change how many of a part, since Back from Layout goes to
  Setup.
- **The Preview step no longer breaks the print time down by line type.** The list beside
  the layer preview gave each line type (outer wall, inner wall, sparse infill and so on)
  its time and share of the print, plus a row for heating and travel. It is now a plain
  legend of the layer preview's colours: each line type's colour and name, nothing else.
  A click on a name still hides that line type in the layer preview, as before.
- *Pictures under the view* is no longer marked "(recommended)" in the scenario strip,
  since it is no longer the default; nothing else about the four earlier options changed.

## What changed in version 4

- **It looks like PenguinCAM.** Light, with PenguinCAM's light-theme colours, its font
  stack at 14 px, its header (the name, then "Config: 6238 (Popcorn Penguins)"), numbered
  pill step tabs with a check mark after a finished step, the chips row, a bold 18 px step
  title with a line of instruction, light bordered cards, and Back and Next as two wide
  buttons pinned to the bottom. Every size, padding and radius is copied from PenguinCAM's
  CSS. The dark theme is gone, from the panel and from the 3D views.
- **The panel's width is fluid.** It works at 320 px and uses extra width: from 520 px the
  Setup fields sit side by side and the figures of a print in one row; from 680 px the parts
  list has two columns, the Preview legend sits beside the view and the Send step has two
  columns. The Layout view fills the width and grows with it. The scenario strip keeps its
  width menu (320, 480, 640, 800 px) and the drag handle (300 to 900 px).
- **Five steps:** Setup, Parts, Layout, Preview, **Send** (version 5 puts Parts first,
  then Setup). Back and forward always work;
  leaving the Preview step while it slices leaves the slice running.
- **The Layout step no longer changes the list of parts:** no Duplicate, Delete, Undo or
  Redo, and none of their keys. Changing quantities is done on the Parts step.
- **Send is its own step**, and the step is the confirmation: its Send button sends at
  once. After sending, the step shows the delivery and print progress. Pausing or stopping
  a print is done at the printer's screen; the panel says so and offers neither.
- **A printer-status icon** in the header on every step; a click shows the details.
- **A busy printer** (another student's print or send) disables Send and says whose, what,
  how far and when it should finish. Nothing queues.
- **Coming back to running work:** the scenario strip imitates a page refresh, closing and
  reopening the panel, and returning two hours later.
- **Parts that fail to arrive** are a notification, never a broken row: a part Onshape
  cannot export is not added; a server that cannot be reached is retried quietly first.
- **No internals in any message**: no route, status code, page id or internal name, in
  any message or its details. Where details help, they are "For a mentor" and say what is
  wrong with the part or the plate and where to look in Onshape or at the printer.
- **Answered by the owner and built in:** a repeat click raises the quantity (M14);
  changing the profile clears the changes, said beside the menu first (M13); the Send step
  is the confirmation (M10); pause and stop only at the printer's screen (M12); the Layout
  view at panel width, growing with it (M8); other instances never move when one is laid
  down (M9); Cancel slice is disabled while the server cannot be reached (M15).
- The instance limit is 150, the slice service's.

## Terms

Each term has one meaning in the mockup and in this file.

| Term | Meaning |
|---|---|
| **Parts step, Setup step, Layout step, Preview step, Send step** | The wizard's five steps, in that order (steps 1 to 5). |
| **part** | One distinct solid, from Onshape or from an uploaded file. |
| **instance** | One placement of a part on the plate, labelled `Name #n`. |
| **plate** | The printer's build plate and everything on it. |
| **plate configuration** | What is sliced: the parts, where each instance sits, the profile and the changes. |
| **profile** | A team's named set of slicing settings, such as Structural. |
| **change** | One setting set differently from the profile, on the Setup step or in advanced mode. |
| **advanced mode** | The view that fills the panel with every slicing setting. |
| **slice job** | One plate configuration being sliced by the slice service. |
| **delivery job** | One sliced file's way from Send to the end of its print (printer delivery's term). |
| **printer-status icon** | The small pill at the right of the header: a printer, a dot and a word. |
| **printer details** | What a click on the printer-status icon opens under the header. |
| **busy printer** | The printer printing, receiving or waiting for a person on another student's delivery job. |
| **notification** | A card at the top of a step, closed with ×, that reports something not on a row: a part that did not arrive, a resumed session. It belongs to that step and goes when the student leaves it. |
| **scenario strip** | The yellow mockup controls above the page. It is not part of the product. |
| **resting position** | One way an instance can lie on the plate: one flat outside face of its part down, stable (its centre of mass above what touches the plate). |
| **rotation handle** | The round handle beside the selection on the Layout step that turns it about the vertical. |
| **resting-position strip** | A row of small pictures under the Layout step's 3D view, one per resting position of the selected part. The scenario strip calls it **Pictures under the view**. |
| **convex hull** | The closed convex shape that wraps a part as tightly as it can, as a rubber skin would; it bridges holes and hollows. |
| **hull patches** | Translucent rounded patches on the selected instance's faces that lie on its part's convex hull; a click lays it on that face. The scenario strip calls them **Faces on the hull (like Orca)**. |
| **face markers** | Small amber arrows (↓) on the selected instance's candidate faces; a click lays it on that face. The scenario strip calls them **Arrows on the part's faces**. |
| **box tumbler** | A box around the selected instance whose sides are clicked (or the box dragged) to put that side down. The scenario strip calls it **Box around the part**. |
| **tip handle** | A second handle (⤵) beside the rotation handle that steps the instance to its next resting position. The scenario strip calls it **Tip handle**. |
| **Like Onshape, Like a slicer, Top-down first** | The three mouse schemes, as the scenario strip's **Mouse** menu names them. |
| **status line** | The one line just above the 3D view on the Layout step: green when every instance fits, red with the first problem when not. |
| **layer preview** | The 3D view of the sliced plate on the Preview step, with its layer bar. |

The Layout step's two buttons, **Arrange** (place every instance on the plate) and
**Auto-orient** (lay instances their best way), are named where they are described below;
they are buttons that may change, not terms.

A student never reads the word "job": what is sliced and printed is a **plate**, named in
words ("Plate 1, 16 instances"), never by the sliced file's generated name. "Slice job" and
"delivery job" are terms of this file and of the services, not of the panel.

## Please react to these

Each answerable in a sentence. The numbers M1 to M16 are the ones you have seen before;
the questions you answered (M8, M9, M10, M12, M13, M14, M15) are built in and no longer
listed. New questions start at M17.

| # | Question |
|---|---|
| M1 | **Lay on face: which one?** *Faces on the hull (like Orca)* (the default since version 5), *Pictures under the view*, *Arrows on the part's faces*, *Box around the part*, or *Tip handle* (scenario strip, **Lay on face**)? Try each on the L Bracket, the Shooter Hood Rib and a round part such as the HTD Pulley 24T. |
| M2 | **Mouse: which one?** *Like Onshape*, *Like a slicer*, or *Top-down first* (scenario strip, **Mouse**)? |
| M3 | **Parts arrive: lying their best way, or as modelled** (scenario strip, **Parts arrive**)? |
| M4 | **Advanced mode at 320 px:** do the search box, the Common / All settings switch, the tab row and the collapsing subgroups make the settings findable? |
| M5 | **Advanced mode when the panel is wider:** a rail of tabs from 480 px, two columns from 700 px. Enough? |
| M6 | **Arrange and Auto-orient stay two buttons.** Right, or should Arrange always auto-orient first? |
| M7 | **The status line** above the Layout view: does one line say enough, with the full sentences below? |
| M11 | **Print progress on the Send step:** stages (Sending, Starting, Heating, Printing, Done), percent, layer of total, time left, expected finish and sent at. What else would a student standing at the printer want? (The layer preview no longer follows the print; it is on the Preview step.) |
| M16 | **Orca's other layout tools** (scale, cut, mirror, per-part settings): which, if any, are needed? The mockup has none. |
| M17 | **Leaving the Preview step while it slices** leaves the slice running, and coming back with the same plate finds it still going or finished; a changed plate starts a new slice. Right, or should leaving stop it (version 3)? |
| M18 | **A finished slice that was not sent is dropped after two hours away.** It survives a refresh and a reopened panel; after two hours the wizard opens at Parts with an empty plate, and one line says only "The slice of your earlier plate has expired; add its parts again to print it." Is dropping it right, and if so, how long should the server keep it for a student to come back to? |
| M19 | **When your print ended while you were away,** the wizard opens at Parts with a notification ("Your print finished at …") and your plate is not kept. Should it keep the plate so the same parts can be printed again in one go? |
| M20 | **Five step tabs at 320 px wrap to two rows,** as PenguinCAM's tabs would; at 420 px and wider they fit one row. Acceptable, or shorten the tabs at narrow widths (for example the number only, with the name on the current tab)? |
| M21 | **A part still arriving does not hold Next.** If it arrives after the student has moved on, it joins the plate on the Layout step (at once if the student is there, else next time). Right, or should Next wait for arriving parts? |
| M22 | **Cancel sending** stays on the Send step while the file is on its way, before the printer starts (printer delivery allows a cancel before its start gate). Keep it? |
| M23 | **Download moved** to the Send step, on the caret beside Send. Right place? |
| M24 | **"Behind its estimate"** shows when the printer's own finish time is 5 minutes or more later than the slicer's estimate. Is 5 minutes the right threshold, and should the printer-status icon say "late" as it does now? |

## Requirements on printer delivery

Things the mockup shows that printer delivery does not provide yet, or provides only in
part ([its guide](../../../delivery/README.md)).

1. **Who sent it.** A delivery job carries the Onshape display name of the student who
   sent it, and `GET /printer/status` returns it for the job going on, so every student's
   printer details and the busy printer can say "for Alex Chen". Not provided today.
2. **What it is.** The delivery job carries a one-line description of the plate (for
   example "8 instances of Gusset Plate"), returned with the job. Today only the file
   name, which the student did not choose; the panel never shows it.
3. **Behind its estimate.** The slicer's estimate at send (`expected_s` in the progress
   report) must be the sliced file's own estimate, kept from the send, so it can be
   compared with the printer's `remaining_min`. The guide lists `expected_s` but does not
   say where it comes from.
4. **Finding my own work after a refresh.** A page that has lost its state finds this
   student's live delivery job (today: `delivery` in `GET /printer/status` is the team's
   most recent job; with requirement 1 the page can tell whether it is this student's).
5. **The end time of the last print**, for "Finished at 3:12 pm" (today
   `last_result.age_seconds`, ten minutes only, `LAST_RESULT_TTL_SECONDS`). The mockup
   shows the last print's end for longer; how long is a decision for printer delivery.

Already provided and used as is: paired or not (`paired`), offline (`online`,
`age_seconds`, `delivery.daemon_silent`), sending (`uploading`, with a fraction),
starting, printing with percent, layer, total layers and time left, waiting for a person
with what to do at the printer (`waiting_for_person`, `waiting_label`, `at_the_printer`),
finished, failed, the job slot (one job; nothing queues; `delivery.printer_busy` refuses a
send to a busy printer), and cancel before the start gate.

**On the slice service** (not printer delivery): a page that has lost its state finds this
student's running or finished slice job and its plate configuration, to resume on the
Preview step. Not provided today.

## Open facts, not decisions

- **How wide the real panel can be dragged.** The owner widens PenguinCAM's panel by
  dragging; Onshape publishes no limits. The mockup allows 300 to 900 px.
- **Full screen inside Onshape**, **an element tab beside the panel**, **Onshape's trackpad
  gestures** and **Onshape's default mouse**: as in version 3, unverified.
- **Speed in Onshape** of auto-orient and Arrange on real team parts: unmeasured.

## Every decision

### Whole panel

1. The look is PenguinCAM's light theme, copied from its CSS: background `#f6f8fa`, cards
   `#ffffff`, controls `#eef1f4`, lines `#d0d7de`, text `#1f2328` and `#5a6570`, accent
   `#2f81f7`; body text 14 px with line height 1.45 in PenguinCAM's font stack; step tabs
   and chips 12 px with PenguinCAM's paddings; step title 18 px; buttons 8 px by 14 px,
   radius 6 px; body padding 14 px. Two departures: amber text is `#9a6700` (PenguinCAM's
   `#d29922` is hard to read on white; the borders keep `#d29922`), and a step tab's hover
   is light (PenguinCAM's hover is a dark colour in its light theme too).
2. The header: "PenguinSlicer", the printer-status icon at the right of the same line,
   "Config: 6238 (Popcorn Penguins)" with the reload glyph, then the step tabs.
3. The step tabs are PenguinCAM's: number, name, and a check mark after the name of a
   finished step. A click on a tab goes there when every step before it allows. At 320 px
   the five tabs wrap to two rows (M20).
4. A row of chips grows as the student advances, each chip saying what an earlier step
   decided: none on the Parts step; parts and instances from the Setup step on; filament,
   profile and changes from the Layout step on; plate area from the Preview step on; print
   time and grams on the Send step.
5. Next is disabled until the step's rules pass, and the step says why. A part still
   arriving never holds Next (M21).
6. The panel's width is fluid; the extra width is used from 520 px and 680 px by
   container queries on the panel, so dragging the panel wider changes the layout exactly
   as the window would. Advanced mode keeps its own rail and two columns (M5).
7. Notifications sit at the top of a step, under the chips, until closed with × or until
   the student leaves the step.
8. The scenario strip sits above the page, never over it: three short rows, a **Fewer
   controls** button that leaves one row, and **Hide strip** that leaves a small tab. The
   how-to note is folded.

### Setup step (step 2)

The Setup step comes after the Parts step since version 5; the decisions keep their numbers.

9. The printer line names the printer with a state chip (Free, Sending 40%, Printing 61%,
   Waiting, Finished, Failed, Offline) and, while a print runs, for whom and how long is
   left. With no printer paired it names no printer: a "No printer paired" chip and the
   model the team's profiles are for. The Layout step's plate line then names the model,
   not the printer.
10. Four filaments, PETG first and marked "(most prints)"; five team profiles, each with a
    one-line purpose.
11. **Picking another profile clears every change** and uses that profile's own values
    (M13). While there are changes, a sentence under the Profile menu says so before it
    happens: "Picking another profile clears your 2 changes and uses that profile's own
    settings." After the change, one line says what was cleared.
12. The four quick changes (Infill, Walls, Supports, Brim) and advanced mode edit one
    shared set of changes, listed under "N settings changed from Structural" with Review
    in advanced mode and Reset all.
13. Advanced mode is unchanged from version 3 apart from its colours: inside the panel,
    filling it; search first; Common / All settings; tabs; collapsing subgroups; undo
    arrow per change; range checks; Reset all asks once more; changes last for this page
    load. It covers the panel's header, so its top line repeats "PenguinSlicer" with the
    printer-status icon, which keeps working there.

### Parts step (step 1)

The wizard opens on this step: it is step 1 since version 5. Back is off here.

14. A click on a part in Onshape adds it with quantity 1. **A click on a part already in
    the list raises its quantity by one and flashes its row** (M14); the line at the top
    says "Added one more: HTD Pulley 24T: 3 instances." A ↻ on each row brings in a new
    version of a part changed in Onshape.
15. A part arriving shows on its row with a thin progress bar ("Arriving from Onshape…").
16. **Onshape cannot export a part** (a broken part): a notification names the part and
    says what a mechanical mentor can check in Onshape (one closed solid, not a surface,
    not several bodies; the Part Studio rebuilds with no red features). The part is not
    added, Next stays enabled, and there is no Try again. "Your other parts are fine" is
    said only while the list holds other parts. A second failure of the same part replaces
    its notification rather than adding another.
17. **Our server cannot be reached:** the page retries quietly; the row shows the part
    arriving with progress, then "Taking longer than usual; still trying…" after 4
    seconds; after 20 seconds of failed retries a notification says the part was not added
    and to check that the computer is online, then click it again in Onshape (on the
    standalone page: upload the file again). The list never holds a broken row.
18. A ↻ that fails keeps the version already in the list and says so in a notification.
19. A file that cannot be read on the standalone page is a notification and is not added.
20. The not-watertight warning stays on its row, in amber, and does not block.
21. In an Assembly, one button adds every distinct part with its count; standard content
    is left out with a sentence naming it.
22. A plate holds up to 150 instances, the slice service's limit; quantities clamp there.
23. A part that arrives after the student left the Parts step joins the plate on the
    Layout step: at once if the student is there, else the next time it is shown (M21).

### Layout step

24. The Layout step does not change the list of parts: no Duplicate, Delete, Undo or Redo,
    and Delete, Ctrl+D, Ctrl+Z and Ctrl+Y do nothing. The instruction line says to go to the
    Parts step (tab 1) to change how many of a part; Back from the Layout step goes to the
    Setup step.
25. **The 3D view fills the panel's width and grows as the panel is widened** (M8): square
    at narrow widths, 4:3 from 520 px, with no height cap. The instruction line starts
    "↔ Widen the panel for more room", as PenguinCAM's Layout step does.
26. **Laying an instance down never moves another instance** (M9). An instance that no
    longer fits where it stood moves to the nearest free spot, turned if need be; if there
    is none, it waits beside the plate, marked off the plate, and the message says to press
    Arrange to make room.
27. Everything else is as version 3: no modes; the mouse schemes (M2); the ways to lay an
    instance on a face (M1; five since version 5, see decision 49); auto-orient on arrival (M3); Arrange with its two packers
    and its offer to lay instances their best way when that fits more (M6); the status
    line (M7); the rotation handle drawn over everything; the placement rules of the slice
    service (5 mm apart, 3 mm inside the edge, 340 mm tall).

### Preview step

28. Entering the Preview step starts the slice; coming back with the same plate shows the
    result without slicing again.
29. **Leaving the Preview step while it slices leaves the slice running** on the server
    (M17); coming back with the same plate shows its progress, and a changed plate cancels
    it and starts a new one.
30. Slicing progress is version 3's card: ring gauge, percent and stage, elapsed and time
    left, bar, list of stages, Cancel slice.
31. **While the server cannot be reached, Cancel slice is disabled** (M15), with one line
    saying the server cannot be reached and the slice may still be running.
32. Each slicing failure is one sentence of what happened and one of what to do, with its
    buttons, and the Preview step's lead says the slice failed, was stopped at the time
    limit, was cancelled, or (for a plate too large) was never started. Exactly three
    messages have "For a mentor" details: the empty-layers and faulty-mesh slice failures
    (Orca Slicer's own sentence with the heights, and where to look on the part), and the
    failed print on the Send step (where the printer's screen shows the fault, and what to
    check in the filament path and the nozzle). No other message has details.
33. The result: print time and grams, a quiet line of instances, layers and slice time,
    the 3D layer preview with its layer bar, and a legend of the layer preview's colours
    (each line type's colour and name only; a click on one hides that line type), beside
    the view from 680 px.
34. Next goes to the Send step once the plate is sliced.

### Send step

35. The step shows what will be printed (printer with its state, the instances by part,
    print time, grams of filament) and a reminder: "Check that the plate is clear and PETG
    is loaded. Send starts the print at once; nobody is asked again."
36. **The Send button sends at once** (M10). It is PenguinCAM's final action: a wide blue
    button with a caret, whose menu offers Download instead (M23). Choosing from the menu
    changes the button; it does not act.
37. After sending, the step shows the delivery and print progress at the top: the stage on
    a track (Sending, Starting, Heating, Printing, Done), percent, layer of total, time
    left, expected finish (with "N min behind" when late) and sent at. The card names the
    plate in words ("Plate 1, 16 instances, on Shop H2S"), never by the sliced file's name.
    The step's lead and the disabled button follow the phase: on its way ("Sending…"),
    heating ("Heating…"), printing ("Printing…"), waiting for a person ("Waiting for a
    person…"). While the plate is on its way, **Cancel sending** is offered (M22).
38. **Pausing or stopping a print is done at the printer's screen** (M12); the card says
    so, and the panel offers neither.
39. A print that waits for a person (filament ran out, door open) shows what to do at the
    printer, in amber; it is never an end.
40. A finished or failed print says so on the card; Send is enabled again for the same
    sliced plate.
41. **A busy printer** (another student's print or send): a card says whose, what, how far
    (percent, layer), the time left and when it should finish, with "N min behind" when
    late; Send is disabled; the sliced plate stays ready; nothing queues. Send comes back
    by itself when the printer is free.
42. An offline printer and a team with no printer paired each disable Send with one
    sentence and Download. With no printer paired, nothing on the step names a printer or
    speaks of reaching one: the lead says no printer is paired, the summary's printer row
    says "No printer paired", and the button reads "Send to printer".

### The printer-status icon

43. On every step, the right of the header: a printer, a dot and a word. Free (green),
    Sending 40% (blue, pulsing), Heating or Printing 61% (blue, pulsing), Waiting (amber),
    Finished (green), Failed (red), Offline and No printer (grey). "· late" follows when a
    print is 5 minutes or more behind its estimate (M24).
44. A click opens the printer details under the header: what is printing (the row is
    labelled Sending, Printing, Printed or Was printing, as the phase is), for whom (the
    Onshape name, with "(you)" for this student), percent and layer, time left, expected
    finish, whether it is behind its estimate, and a bar; what to do at the printer while
    it waits for a person; that pausing or stopping is done at the printer. A click
    elsewhere, Escape or × closes it.

### Coming back to running work

45. The scenario strip's **Refresh page**, **Close and reopen** and **Come back 2 h later**
    throw away the page's state; what the server holds stays: this student's slice job and
    plate configuration, and the printer.
46. When this student's slice is running, or finished and not sent, the wizard reopens on
    the Preview step with the parts and layout restored; when this student's delivery job
    is running, it reopens on the Send step with live progress. A notification says
    "Back where you were" and, in the past tense, what the plate was doing when the
    student left ("You had sent your plate to Shop H2S before you left; its progress is
    below."), so it stays true while the card under it moves on.
47. Otherwise it starts at the Parts step, step 1. Another student's work shows in the
    printer-status icon, which is on every step and so is the first thing seen, and also on
    the Setup step (step 2), whose printer line **names that student**: "Shop H2S
    Printing 54% for Alex Chen, 54 min left". The brief asked only for the icon; the name on
    the Setup step is a choice of this mockup. Keep it, or show the name only in the
    printer details?
48. After two hours away, a finished unsent slice is gone (M18), and a one-line
    notification on the Parts step says the slice of the earlier plate has expired; a print
    of this student's that ended meanwhile is reported in a notification on the Parts step
    (M19).

### Lay on face: faces on the hull (version 5)

49. *Faces on the hull (like Orca)*, the default way to lay an instance on a face, follows
    Orca Slicer's Lay on face tool as [the algorithm note](../../research/2026-11-21-lay-on-face-hull-faces.md)
    describes it: the faces of the part's convex hull, with Orca's filters (at least 5 mm²,
    no sliver corners, the 254 largest), plus one rule of the mockup's own for round parts
    (a face is left out when a neighbouring hull face bends away from it by less than 20
    degrees and is at least half its size). Choices the brief left open:
    - **Opening it is selecting one instance**, as with the arrows and the box: no button
      and no mode (decision 27 keeps the Layout step free of modes). With two or more
      instances selected, no patches show, as Orca shows them for one instance only.
    - **Colours:** PenguinCAM's accent blue `#2f81f7` at 22% opacity, 55% under the pointer.
      Orca's near-white patches would not show on the light theme's pale parts.
    - **Only the patches in sight are drawn and clickable:** a patch behind the part, or
      behind another instance, is hidden by it. Orca draws every patch over the part.
    - **The face the instance lies on has no patch.**
    - **The rotation handle keeps clear of the patches:** while patches show, the handle
      moves round the selection, 45 degrees at a time, to the first side where it covers
      no patch in sight (and is hidden if no side is free), so a click on a patch always
      lays the instance down and a click on the handle always turns it.
    - No test of whether the instance would tip over on a face, as in Orca. So a face the
      part would fall off is offered too: by hand arithmetic, the end of the L Bracket's base
      (5 mm tall) with the bracket's centre of mass about 10 mm up. The real wizard should
      test it (the auto-orient code already does).

## What is fake and could mislead

1. Toolpaths are generated shapes, not Orca's output; print time and grams are estimates
   from them.
2. Slicing time, stage durations and percentages are invented formulas.
3. Nothing is exported from Onshape; an export takes about a second; the server outages
   last 9 seconds (slow) or 20 (down) on the real clock; an uploaded file is never read.
4. The printer, Alex Chen, his gusset plate, the waiting reasons, the
   failure reason and every time are invented. The heating, starting and waiting lengths
   are invented; a person "resumes at the printer" after 10 mock minutes.
5. Times of day are this computer's clock plus mock time; at Fast speed a print runs 900
   times faster and another student's 30 times, so the clock jumps ahead.
6. The Printer menu in the scenario strip sets the printer outright; a real printer gets
   there by itself.
7. "Come back 2 h later" moves the page's clock and the printer forward two hours at once.
8. The notification after a refresh, and what is restored, imitate requirements on printer
   delivery and the slice service that do not exist yet.
9. The plate-volume cap (600 cm³) is invented; armed "plate too large" lowers it for one
   plate and says so in a mockup note.
10. Hulls are thinned to 40 points; placement distances can be off by about 0.2 mm.
11. Download saves nothing.
12. The page around the panel is not Onshape.
13. Advanced mode shows a sample of Orca's settings (about 50 Common, 95 All).
14. Auto-orient scores flat outside faces of the mock parts only; "overhangs" uses an
    invented threshold.
15. *Top-down first* uses a perspective camera, not an orthographic one.
16. Cancel sending always works at once; a real cancel may arrive after the printer has
    started.
17. The panel's drag limits (300 to 900 px) are the mockup's, not Onshape's.
18. Fonts: PenguinCAM's stack starts with the system font, so the mockup renders in each
    computer's own system font, as PenguinCAM does; screenshots taken on Linux show
    Liberation Sans or DejaVu Sans, not San Francisco.
19. The hull patches are worked out from the mock parts' generated meshes, in the browser,
    the first time a part is selected; real exported meshes are finer and less regular, and
    the round-part rule has been tried on these seven parts only.
