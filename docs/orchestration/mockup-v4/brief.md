# Brief: wizard mockup version 4

- **Deliverable (REQUIRED):** mockup version 4 in `docs/mockups/print-wizard/`, its
  `DECISIONS.md` rewritten to version 4, and a result file at
  `docs/orchestration/mockup-v4/result.md` listing every change, every choice you made,
  every point of the owner's feedback with where it is met, and what you could not do.
- **Stop condition (REQUIRED):** every point under "What the owner asked for" is met or
  answered in the result file; the mockup has been walked in a browser at panel widths
  320, 480 and 800 px through every step, every scenario-strip control and every new
  state, with no console error; screenshots of the walk are saved (see "Walk").
- **Budget (REQUIRED):** 150 minutes; no cloud spend.
- **Where this fits:** the owner is away for a few hours and will review version 4 on
  return. A fresh reviewer walks it before then and a fix round may follow. The mockup is
  a click-through imitation with nothing real behind it; it is not product code, so the
  repository's test-suite quality bar does not apply, but a clean console and a careful
  walk do.

## Read first

1. [The owner's feedback notes](../../handoffs/2026-11-20-session-summary-feedback.md):
   everything under "Feedback of Sat 2026-11-21" and "Mockup feedback of Sat 2026-11-21".
2. [The visual reference](../../reference/penguincam-in-onshape/README.md) and its three
   screenshots (open the PNG files and look at them), plus
   [the export-failed screenshot](../../reference/mockup-v3-feedback/export-failed.png)
   of version 3's error card that the owner disliked.
3. PenguinCAM's own wizard, which version 4 should look like: read
   `/repos/popcornpenguins/PenguinCAM/static/wizard.css`, `static/wizard.html` and
   `static/wizard.js` (read only; never change anything in PenguinCAM). Take its fonts,
   font sizes, colours, spacing, border radii, step tabs, chips, cards and bottom
   buttons from that code, not by eye from the screenshots.
4. The mockup as it is: `docs/mockups/print-wizard/` and its `DECISIONS.md`.
5. For the printer states: `delivery/README.md` (the relay's routes, the job slot, the
   error codes such as `delivery.printer_busy_at_start`), so the mockup shows what printer
   delivery really reports. Where the mockup needs something printer delivery does not
   provide yet, show it anyway and list it in `DECISIONS.md` as a requirement on printer
   delivery.

## What the owner asked for

**Look like PenguinCAM.**

- Light mode, as PenguinCAM and Onshape; the dark theme goes.
- PenguinCAM's font, font sizes, control sizes, spacing and alignment, measured from its
  CSS. At the same panel width, a line of body text, a step tab, a chip and the Next
  button should be the same size as in PenguinCAM.
- PenguinCAM's idioms: the header with the application name and the config line, the
  numbered pill step tabs with check marks, the chips row, a bold step title with short
  instructions, light bordered cards, Back and Next as wide buttons pinned to the bottom.
  The name in the header is "PenguinSlicer"; the team is "6238 (Popcorn Penguins)".
- **Panel width is fluid.** Onshape's panel is widened by dragging. The wizard works at
  320 px and uses extra width well up to about 800 px. Keep the scenario strip's width
  control.
- The scenario strip is not part of the product and may stay as it is in style, but it
  must not hide the panel.

**Keep:** the quantity on each row of the parts list, the 3D picture of each part, the
slicing progress on the Preview step, advanced mode inside the panel, and the three
switchable options of version 3 (Lay on face, Mouse, Parts arrive) in the scenario strip.

**The steps.**

- Five steps: Setup, Parts, Layout, Preview, Send. Back and forward between steps always
  work.
- Layout does not change the list of parts: remove its duplicate and delete buttons and
  its undo and redo. Changing quantities means going back to Parts.
- **Send** is its own step after Preview. It shows the printer, the instances, the print
  time and filament, and a reminder to check that the plate is clear; its Send button
  sends at once. The step itself is the confirmation: no extra dialog. After sending, the
  same step shows the delivery and print progress (stages, percent, layer, time left,
  expected finish). Pausing or stopping a print is done at the printer's screen; the step
  says so, and the panel offers neither.
- **Repeat click:** clicking a part in Onshape that is already in the list raises its
  quantity by one and flashes the row.
- **Changing the profile clears changed settings:** picking another profile resets every
  setting to that profile's values. Say so before it happens, in a sentence next to the
  profile control, not a dialog.
- Instance limit 150 on a plate (the slice service's limit), up from 100.

**Printer status, always visible.** A small printer-status icon in the panel's header,
on every step. Its states: no printer paired, printer offline or not heard from, idle and
free, sending, printing (with percent), waiting for a person (paused, door open, filament
out), finished, failed. A click expands it to the details: what is printing, for whom
(the Onshape name of the student who sent it), percent, time left, expected finish, and
whether it is behind its estimate.

**Busy printer.** On the Send step, when the printer is busy with another student's
print or send: say whose, what, how far and when it should finish; Send is disabled
until the printer is free; the sliced file stays ready. Nothing queues.

**Coming back to running work.** Add scenario-strip controls to imitate: a page refresh,
closing and reopening the wizard, and returning later. When this student's slice or send
is still running, the wizard resumes where they were: it reopens on that step (Preview or
Send) with live progress, the parts and layout restored. When another student's work is
running, the wizard starts at Setup and the printer-status icon shows it.

**Parts that fail to arrive.**

- **Onshape cannot export a part** (a broken part): a notification, the part is not
  added to the list, Next stays enabled, no "Try again". The wording names the part and
  what a mechanical mentor can check in Onshape (for example that it is one closed solid,
  or that the Part Studio rebuilds without errors). No HTTP method, status code, route,
  page id or any other internal of PenguinSlicer anywhere, including in any details.
- **Our server cannot be reached:** retry quietly; show the part as arriving with
  progress, then "taking longer than usual" after a few seconds; report failure as a
  notification only after the retries have failed. The list never holds a broken entry
  that disables Next.
- Apply the same rule to every other error card in the mockup: read every message a
  student can see and remove anything internal.

**Questions.** Rewrite `DECISIONS.md` to version 4. Questions the owner has answered are
not listed as questions any more; write the answer into the design. The owner answered:
M10 (the Send step is the confirmation), M12 (printer's screen only), M13 (clear
changes), M14 (raise the quantity). Keep the numbers of the questions that remain open
(M1 to M9, M11, M15, M16) and add new ones numbered from M17, each answerable in a
sentence. Add a short "What changed in version 4" section at its top.

## Walk

Serve the folder on a free port other than 6238 and drive a browser with `playwright-cli`
(session name in `$PLAYWRIGHT_CLI_SESSION`); for WebGL in this container read
`/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`.
Save screenshots of each step at 320 and 800 px, of the printer-status icon closed and
open, of the busy-printer Send step, of a resumed Send step after a refresh, and of both
part-arrival failures, to `docs/orchestration/mockup-v4/screenshots/`, as PNG files
named for what they show. Compare the Parts, Layout and Preview steps side by side with
the PenguinCAM screenshots and say in the result file what still differs. Stop the server
and the browser when done, and remove any `.playwright-cli/` folder you leave in the
repository.

## Rules

Read [the standing rules](../review-feedback/briefs/standing-rules.md) and follow them,
with these differences: your folders are `docs/mockups/print-wizard/` and
`docs/orchestration/mockup-v4/`; your scratch folder is
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v4/`.
Another agent is working in `slice/` of the same checkout and may be running a real Orca
slice: keep your browser to one tab and close it when done.
