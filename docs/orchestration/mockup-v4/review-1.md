# Review 1 of wizard mockup version 4

**Verdict: FIX: 0 serious, 4 medium, 12 low.**

The round meets the owner's feedback in substance. The panel measures the same as
PenguinCAM's, it is light everywhere, it has five steps with a Send step that is its own
confirmation, a printer-status icon, a busy-printer block, resume after a refresh, and
failure handling for parts that do not arrive. All four medium defects are sentences that
are false for the state on screen (check d). Each takes a few lines to fix. Nothing here
would make the owner reject the round.

Reviewed on Sat 2026-11-21 from the working tree of `docs/mockups/print-wizard/`. The
mockup was served as static files on port 8741 and driven in one headed Chrome tab
(SwiftShader WebGL under Xvfb) at panel widths 320, 480, 640 and 800 px. Screenshots and
scripts are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v4-review/`.
The builder's result file was not read.

## (a) The brief's checklist and the owner's later answers

| Point | Status | Where seen |
|---|---|---|
| Light mode; dark theme gone | Met | Every step, advanced mode, both 3D views (scene background `#f2f4f7`); see (c) |
| PenguinCAM's font, sizes, spacing, measured from its CSS | Met | See (b): no difference over 1 px on tabs, chips, title, select box, Back and Next |
| Header with name and config line; "PenguinSlicer"; "6238 (Popcorn Penguins)" | Met | Header, every step |
| Numbered pill tabs with check marks; chips row; bold title with short instruction; light cards; Back and Next wide at the bottom | Met | Every step |
| Panel width fluid, works at 320, uses width to about 800; width control kept | Met | Two-column parts list, legend beside the view and two-column Send from 680 px; strip keeps the width menu and the drag grip |
| Scenario strip does not hide the panel | Met | The strip sits above the page; Fewer controls and Hide strip are present |
| Keep: quantity per row, 3D picture per part, slicing progress on Preview, advanced mode in the panel, the three strip options | Met | Parts, Preview, Setup → Advanced mode, strip row 3 |
| Five steps; back and forward always work | Met | Tabs and Back/Next at all four widths (overflow script clicked every tab at every width) |
| Layout: no duplicate, delete, undo, redo | Met | Toolbar has only Arrange and Auto-orient; keys disabled (`layout3d.js:591`). Unused undo-stack code remains in `wizard.js` and is not visible |
| Send step: printer, instances, time, filament, clear-plate reminder, sends at once, no dialog | Met | Send at 320 (`08-send-320.png`) |
| After sending: stages, percent, layer, time left, expected finish; pause and stop only at the printer's screen (M12) | Met | `11-sending-320.png`, `14-print-waiting-320.png` |
| Repeat click raises the quantity and flashes the row (M14) | Met | Row got class `flash`, quantity 1 → 2, "Added one more: Hex Bore Spacer 1in: 2 instances." |
| Profile change clears changes, said beside the menu first (M13) | Met | "Picking another profile clears your change and uses that profile's own settings." under Profile |
| Instance limit 150 | Met | "(up to 150)", quantity clamps |
| Printer-status icon in the header with every state; click opens the details | Met; low defects 7 and 11 | All nine strip states walked, see (e) |
| Busy printer names the student, blocks Send, plate stays ready, nothing queues | Met | `09-send-busy-320.png` |
| Come back: refresh, reopen, two hours later; own slice or send resumes on its step with the plate restored | Met | Refresh and reopen during a slice → Preview, same parts and same instance positions; refresh during a send → Send |
| Other student's work: wizard at Setup, icon shows it | Met | Reopen with another student printing → Setup, icon "Printing 62%" |
| Export failure: notification, not added, Next stays enabled, no Try again, names the part and what a mentor checks, no internals | Met; medium defect 3 | `03-export-fail-320.png` |
| Server unreachable: quiet retry, progress, "taking longer than usual", notification only after the retries fail, no broken row | Met; medium defect 2 | `04-server-slow-320.png`, `05-server-down-320.png` |
| Every other error card free of internals | Met, with low defect 6 (file names) | See (d) |
| DECISIONS.md rewritten | Met, with low defects 12 and 13 | See (h) |
| M8 Layout view at panel width, growing | Met | View is square, then 4:3 from 520 px with no height cap (756 × 567 at 800 px) |
| M9 other instances never move | Met as documented (decision 26); not tested by dragging | |
| M15 Cancel slice disabled while the server cannot be reached | Met | Armed "Connection lost": `#btn-cancel` disabled with an explanatory line |
| M16 stays open | Met | DECISIONS.md M16 |

## (b) Side by side with PenguinCAM

PenguinCAM's page needs its server, which this review did not start. Its
`templates/wizard.html` was rendered without a server: Jinja with `theme="light"`,
`source="onshape"` and the 6238 config, with `url_for` pointed at a symlink to its
`static/`. The page was served as plain files on port 8742 and rendered normally. A chip row
and one part card were injected with the markup that PenguinCAM's `wizard.js` itself
builds (`renderParts`, `chip`). The browser's computed styles were compared at viewport
widths 320 and 800 against the mockup's panel at 320 and 800.

Identical within 1 px at both widths: body font (same stack, 14 px, line height 20.3 px),
config line, step tab and active step tab (12 px, padding 3/10, radius 999), chip font and
padding (12 px, 3/9), step title (18 px), select-status box, hint text (12 px), part name
and size lines, the bottom bar, Back and Next (padding 8/14, radius 6, same height).

Differences over 1 px or of font:

| Element | PenguinCAM | Mockup | Deliberate and justified? |
|---|---|---|---|
| Header height | 96.1 px (800) | 97.8 px | Yes: the printer-status pill (22 px) shares the name's line |
| Part card padding | 8 px on the `li` | 0 on the `li`, 8 px on an inner row | Yes: the same 8 px, moved to make room for the warning area under the row; it looks the same |
| Remove × button | Browser default font (Arial), 23 px tall | Inherits the panel font, 26 px tall | Incidental: PenguinCAM's button does not set `font`. Not visible; not a defect |
| Panel width | 320 | 319 | Yes: the stand-in Onshape frame's 1 px border |
| Chip and part widths | Text-dependent | Text-dependent | Content, not style |

Against the screenshots: Parts, Layout and Preview read as PenguinCAM's (compare
`02-parts-800.png` with images/4.png and `07-preview-800.png` with images/5.png). The
remaining differences are content the owner asked to keep (quantity box and ↻ on each part
row, the 3D thumbnails) or step content that differs by nature. At 320 px the five tabs wrap
to two rows, as PenguinCAM's four tabs also do at 320 (`pcam-parts-320.png`). DECISIONS.md
asks about this as M20.

## (c) Light mode everywhere

A script listed every visible element in the panel whose background luminance is below
0.5. It ran on Setup, advanced mode and the Send step with a print card. It found only the
accent blue (active tab, Next, Send, the advanced tab) and the green status dot. The scene
backgrounds of the Layout and Preview views are `#f2f4f7`. Notifications, error cards
(`.msg.error` with `#ffcecb` edges), the amber waiting card, the busy card, the clear-plate
card, the printer details popover, the connection-lost band (`#fff8c5`) and advanced mode
(`13-advanced-320.png`) are all light. Nothing dark is left over.

## (d) Sentences a student can see

There are no HTTP methods, status codes, routes, page ids or job ids, and no "relay" or
"daemon". The "For a mentor" details quote Orca Slicer's own sentence and say where to look
in Onshape. The export failure has no retry button. Its closing "Then click it again." is
conditional on the mentor's fix, which is acceptable. Sentences that are false for the
state shown:

- Preview after a failed, cancelled, timed-out or too-large slice: "Slicing the plate on
  the server. You can step back meanwhile; it goes on." (defect 1)
- Standalone page, server unreachable: "…then click Camera_Mount in Onshape again."
  (defect 2)
- First part fails with an empty list: "Your other parts are fine, and you can go on
  without it." / "Your other parts are fine." (defect 3)
- No printer paired: "Send waits until Shop H2S can be reached." (defect 4)
- Connection lost: "The slice keeps running on the server." next to "the slice may still
  be running." (defect 5)
- Generated file names shown to students: "(Drivetrain_gussets_plate_1.gcode.3mf)",
  "Intake_v3_plate_1.gcode.3mf on Shop H2S" (defect 6)
- Printer details while sending, finished or failed list the job under the label
  "Printing" (defect 7). The Send step lead reads "Your plate is on its way." while the
  plate is printing or waiting for a person (defect 8).

## (e) Steps and state

- Five steps; Back and the tabs went everywhere allowed at every width. Next is gated
  only by the next step's needs; a part still arriving does not hold it.
- The Send step is the confirmation. Send went straight to "Sending to Shop H2S 37%" with
  no dialog; the button became "Sending…" and was disabled.
- Busy printer: for another student sending, printing, printing late and waiting for a
  person, the card names Alex Chen, what is printing, percent, layer, time left and
  finish (with "22 min behind"). Send is disabled and the caret's Download stays
  available. Finished and failed leave Send enabled. Offline and not paired disable it.
- Refresh and Close-and-reopen during this student's slice reopened on Preview at 69–70%,
  with the same parts and instance positions and a "Back where you were" notification.
  Refresh during this student's send reopened on Send. At Fast speed the print ended
  within a second, so the notification said "printing" over a finished card (defect 9).
- Come back 2 h later during a slice reopened at Setup with an empty plate and no word
  about the finished slice. This matches decision 48 and is asked as M18, so it is not
  counted as a defect.
- Another student's print after a reopen shows in the icon. It also shows in the Setup
  step's printer line ("for Alex Chen, 54 min left"). Decision 47 says so deliberately,
  and it does not contradict the brief.

## (f) Widths

At 320, 480, 640 and 800 px a script visited all five steps and checked every visible
element in the panel. None extended beyond the panel's edges, and no element scrolled
sideways. The screenshots show no overlap. At 320 a part name next to ↻, the quantity box
and × truncates early ("Hex Bore Spa…"; defect 16).

## (g) Console

`playwright-cli console` reported 0 errors and 0 warnings after the whole walk: every
step, every armed error except "faulty mesh" and "instance too tall" (their messages were
read in the code), every printer state, refresh, reopen, two hours later, advanced mode,
the standalone context and all four widths.

## (h) DECISIONS.md

It has been rewritten to version 4 with a "What changed in version 4" section at the top.
The answered questions (M8, M9, M10, M12, M13, M14, M15) are built into the design and no
longer listed. The open questions are M1–M7, M11 and M16, and the new ones run M17–M24.
Each can be answered in a sentence; M11 is the most open-ended. The section "Requirements
on printer delivery" is useful. Stale or wrong statements are listed in defects 12 and 13.

## Defects

1. **Medium: the Preview lead is false after a slice ends without a result.**
   Where: Preview step, `#preview-lead`, set in `startSlice` (`wizard.js:1205`) and never
   reset by `failSlice`, `cancelSlice` or the plate-too-large branch.
   Evidence: armed Empty layers, Cancel, Timeout and Plate too large. Each showed "Slicing
   the plate on the server. You can step back meanwhile; it goes on." above the failure
   card; for Plate too large no slice ever started.
   Fixed when: the lead states the actual outcome (failed, cancelled, stopped, not
   started) in each of those four states.

2. **Medium: the standalone page tells the student to click in Onshape.**
   Where: `failNotice(part, 'server')`, `wizard.js:561`, which does not check `S.ctx`.
   Evidence: Context Standalone, armed Our server cannot be reached, uploaded a file:
   "…Check that this computer is online, then click Camera_Mount in Onshape again."
   (`16-standalone-server-down-320.png`).
   Fixed when: the standalone wording says to upload the file again.

3. **Medium: "Your other parts are fine" when there are no other parts.**
   Where: `failNotice`, `wizard.js:555–562` (all three branches).
   Evidence: the first part of an empty list fails to export: "Your other parts are fine,
   and you can go on without it." The list shows "No parts yet." and Next is disabled
   (`03-export-fail-320.png`). The server-down branch is the same.
   Fixed when: those clauses appear only while the list holds other parts.

4. **Medium: no printer paired, yet the page speaks of reaching Shop H2S.**
   Where: Send step lead (`wizard.js:1653`); printer details (`renderPrinterPop`); Send
   summary row "Printer: Shop H2S · No printer".
   Evidence: Printer = No printer paired. The lead says "Send waits until Shop H2S can be
   reached." The details read "No printer paired." over "Shop H2S, Bambu Lab H2S 0.6
   nozzle".
   Fixed when: with no printer paired, no sentence names a printer or speaks of reaching
   one, and the lead says no printer is paired.

5. **Low: connection lost: two sentences disagree.**
   Where: `tickSlice`, `wizard.js:1275–1277`.
   Evidence: "…Reconnecting (try 2)… The slice keeps running on the server." directly over
   "Cancel slice is off until the server can be reached again; the slice may still be
   running."
   Fixed when: only the hedged statement remains.

6. **Low: generated file names shown to students.**
   Where: busy card (`busyCard`, `wizard.js:1688`) and print card (`.pc-file`,
   `wizard.js:1748`).
   Evidence: "8 instances of Gusset Plate (Drivetrain_gussets_plate_1.gcode.3mf)";
   "Intake_v3_plate_1.gcode.3mf on Shop H2S". DECISIONS.md requirement 2 itself calls
   this a name "the student did not choose".
   Fixed when: neither card shows a file name, or the file name is reachable only on
   Download.

7. **Low: the printer details label every job "Printing".**
   Where: `renderPrinterPop`, `wizard.js:1599`.
   Evidence: while another student's plate is being sent, and under "The last print
   finished." or "…failed", the first row reads "Printing: 8 instances of Gusset Plate".
   Fixed when: the label suits the state (for example "Print", or "Sending" and "Printed").

8. **Low: the Send step's lead and button do not follow the print's phase.**
   Where: `renderSend` (`wizard.js:1650`) and `updateNext` (`wizard.js:230`).
   Evidence: while this student's print is printing or waiting for a person (filament
   out), the lead says "Your plate is on its way." and the button says "Printing…"
   (`14-print-waiting-320.png`).
   Fixed when: the lead says printing or waiting for a person in those phases.

9. **Low: the "Back where you were" notification goes stale.**
   Where: `reopen`, `wizard.js:1844`.
   Evidence: refresh during sending at Fast speed. The notification says "your plate is
   printing on Shop H2S" while the card below says "Print finished 100%"
   (`12-resumed-send-320.png`).
   Fixed when: the notification avoids naming a phase, or updates with it.

10. **Low: the same export failure stacks two identical notifications.**
    Where: `failNotice` passes no key to `notify`.
    Evidence: HTD Pulley 24T failed twice and two identical cards were shown.
    Fixed when: a repeat for the same part replaces the earlier notification.

11. **Low: advanced mode hides the printer-status icon.**
    Where: `.advanced` covers the whole panel, header included.
    Evidence: `13-advanced-320.png`, where no icon is visible.
    Fixed when: the icon stays visible in advanced mode, or DECISIONS.md states the
    exception.

12. **Low: the DECISIONS.md terms table.**
    Where: Terms, last row.
    Evidence: it still lists "auto-orient" and "Arrange" as terms, which the owner's
    notes ask to remove from the terms table ("buttons that may change"). It defines nine
    terms only as "As in version 3", which the owner can no longer open.
    Fixed when: auto-orient and Arrange are out of the table, and the other terms are
    defined in this file.

13. **Low: DECISIONS.md decision 32 is false.**
    Where: decision 32, "No other message has details."
    Evidence: the failed-print card has "For a mentor" (`wizard.js:1773`).
    Fixed when: decision 32 names every message with details.

14. **Low: "job" and "plate" used for the same thing.**
    Where: `TOO_MANY_INSTANCES_MESSAGE` and plate-too-large ("print the rest in a second
    job") against the timeout message ("print the rest on a second plate").
    Fixed when: one word is used, and it is "plate", since "slice job" is the slice
    service's term.

15. **Low: armed "Instances too close" can show a different error.**
    Where: the strip's arm with L Bracket and Shooter Hood Rib.
    Evidence: it reported "Shooter Hood Rib #1 is not fully on the plate: it crosses the
    right and front edges." With L Bracket and Hex Bore Spacer it correctly reported
    "2.0 mm apart".
    Fixed when: the armed error always produces the too-close message.

16. **Low: part names truncate early at 320 px.**
    Where: Parts step row (`02-parts-320.png`).
    Evidence: "Hex Bore Spa…" beside ↻, the quantity box and ×. PenguinCAM's cards show
    the whole name at this width.
    Fixed when: names of about 20 characters show in full at 320 px, for example by
    letting the name wrap to two lines.
