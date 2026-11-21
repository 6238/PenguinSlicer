# Fix round 1 of wizard mockup version 4

Done on Sat 2026-11-21 (Pacific) against [review 1](review-1.md): all 4 medium and all 12
low defects fixed, and the two items the review did not count as defects stated plainly
for the owner. Changed files: `js/wizard.js`, `css/panel.css`, `index.html` and
[DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) in `docs/mockups/print-wizard/`.

## The walk

Served on port 8771 (static files) and driven in one headed Chrome tab (SwiftShader WebGL
under the Xvfb display already running) at 320 and 800 px. Every state changed below was
walked, and each sentence was read back from the page after the fix. Everything inside
the panel stayed inside it, nothing scrolled sideways, and the console showed 0 errors and
0 warnings. The walk scripts are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v4-fix/`.
The browser and the server are stopped, and `.playwright-cli/` is removed.

## Defects

| # | Fixed how | Where seen after the fix |
|---|---|---|
| 1 (medium) Preview lead false after a slice ends | The lead now follows the outcome: "The slice failed, so there is nothing to preview yet. What to change is below." (empty layers, faulty mesh); "The slice was stopped at the server's time limit. Nothing to preview yet."; "The slice was cancelled, so there is nothing to preview."; "This plate was not sliced: it is too large for the server. Nothing to preview yet." It goes back to the slicing sentence on Slice again, and when the student returns to a slice that is still running. | Armed Empty layers, Cancel, Timeout and Plate too large at 320; empty layers also at 800 |
| 2 (medium) standalone page told to click in Onshape | The standalone page now says "…then upload bracket.stl again." (the student's own file). | Standalone, armed Our server cannot be reached; [320-standalone-server-down.png](screenshots/320-standalone-server-down.png) |
| 3 (medium) "Your other parts are fine" with no other parts | That clause, and "you can go on without it", appear only while the list holds other parts that have arrived. This applies to all three failure notifications. | First part of an empty list fails twice ([800-2-parts-export-failed.png](screenshots/800-2-parts-export-failed.png)); a part fails next to an arrived one (the clause is there); server down beside an arrived part ([800-2c-parts-server-unreachable-failed.png](screenshots/800-2c-parts-server-unreachable-failed.png)) |
| 4 (medium) no printer paired, yet Shop H2S named | With no printer paired, nothing names a printer or speaks of reaching one. The Send lead reads "No printer is paired with your team, so Send is off."; the summary's printer row reads "No printer paired"; the button reads "Send to printer"; the printer details drop the "Shop H2S, Bambu Lab H2S" line. The Setup printer line shows a "No printer paired" chip and "(the profiles are for a Bambu Lab H2S 0.6 nozzle)", and the Layout plate line names the model, not Shop H2S. | [320-send-no-printer-paired.png](screenshots/320-send-no-printer-paired.png), [320-setup-no-printer-paired.png](screenshots/320-setup-no-printer-paired.png); details read "No printer paired." plus the pairing note |
| 5 connection lost: two sentences disagree | "The slice keeps running on the server." is removed. Only "…the slice may still be running." remains. | [320-preview-connection-lost-cancel-off.png](screenshots/320-preview-connection-lost-cancel-off.png) |
| 6 generated file names shown | No file name reaches a student. The print card reads "Plate 1, 4 instances, on Shop H2S"; the busy card shows only "8 instances of Gusset Plate"; the Download note reads "Downloaded the sliced file of Plate 1, 4 instances (1.2 MB)." The `fileName()` helper and Alex Chen's file name are removed. | [320-5b-send-printing.png](screenshots/320-5b-send-printing.png), [320-send-busy-printer.png](screenshots/320-send-busy-printer.png), [800-5b-send-busy-printer.png](screenshots/800-5b-send-busy-printer.png) |
| 7 printer details label every job "Printing" | The first row is labelled Sending (on its way), Printing (heating, printing, waiting), Printed (finished) or Was printing (failed). | Details read in each phase, for this student's plate and for another student's; [320-printer-status-open-yours.png](screenshots/320-printer-status-open-yours.png) ("Printed") |
| 8 Send lead and button ignore the phase | The lead is "Your plate is on its way to Shop H2S." while sending, "Shop H2S is heating up to print your plate." while heating, "Your plate is printing on Shop H2S." while printing, and "Your print is waiting for a person at the printer: filament ran out." while waiting. The button reads Sending…, Heating…, Printing… or Waiting for a person…. | Every phase of one send with Filament runs out armed; [320-send-your-print-waiting-for-person.png](screenshots/320-send-your-print-waiting-for-person.png) |
| 9 "Back where you were" goes stale | The notification uses the past tense, about the moment the student left, and points below: "You had sent your plate to Shop H2S before you left; its progress is below." / "Your plate was still slicing when you left; see below." / "Your plate was sliced and ready to send when you left." | Refresh during sending, then 10 s at Fast speed until the print finished: still true ([320-resumed-send-after-refresh.png](screenshots/320-resumed-send-after-refresh.png)); refresh during a slice, which then finished ([320-resumed-preview-after-refresh-still-slicing.png](screenshots/320-resumed-preview-after-refresh-still-slicing.png), [320-resumed-preview-after-refresh-sliced.png](screenshots/320-resumed-preview-after-refresh-sliced.png)) |
| 10 identical notifications stack | Each failure notification has a key built from its kind and its part, so a repeat replaces the earlier one. A failed ↻ is keyed the same way. | HTD Pulley 24T failed twice: one notification |
| 11 advanced mode hides the printer-status icon | Advanced mode has its own top line, "PenguinSlicer", and the icon with its details moves into it while advanced mode is open and moves back on close or Reset. The icon stays live and clickable. | [320-advanced-printer-icon.png](screenshots/320-advanced-printer-icon.png), [320-advanced-printer-icon-open.png](screenshots/320-advanced-printer-icon-open.png); also at 800 |
| 12 DECISIONS.md terms table | Auto-orient and Arrange are out of the table, and a sentence below it names them as buttons that may change. Every other term is defined in place: resting position, rotation handle, resting-position strip, face markers, box tumbler, tip handle, the three mouse schemes, status line and layer preview. A note says students never read "job". | [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md), Terms |
| 13 decision 32 false | Decision 32 now names the three messages that have "For a mentor" details: empty layers, faulty mesh and the failed print. It also describes the Preview lead after a failure. | DECISIONS.md decision 32 |
| 14 "job" and "plate" | Every sentence a student reads says "print the rest on a second plate": the instance limit, both Arrange messages and Plate too large. The plate summary's accessible label is "Plate summary", where it was "Job summary". | Plate too large read back: "…print the rest on a second plate." |
| 15 armed Instances too close can show another error | The armed error picks the pair and side that break no other rule. When the pair would cross the plate's edge, both slide inward together. Because boxes 2 mm apart can leave the outlines more than 5 mm apart (the rib is slanted), the gap closes a millimetre at a time until the pair is too close. | Eight part combinations, including L Bracket with Shooter Hood Rib ("4.4 mm apart") and Gusset Plate with Shooter Hood Rib: every one reported only too-close |
| 16 names cut short at 320 px | A part name wraps to a second line (clamped at two) rather than being cut short. | [320-2-parts.png](screenshots/320-2-parts.png): "Hex Bore Spacer 1in", "HTD Pulley 24T" and "Camera Mount" in full |

Other edits to DECISIONS.md, to keep it true: decisions 9, 13, 16, 17, 37, 42, 44 and 46
describe the new behaviour; requirement 2 says the panel never shows the file name; the
fakes list no longer mentions a file name.

## The two items left for the owner

- **A finished slice dropped after two hours.** The behaviour is unchanged. The wizard now
  shows a one-line notification at Setup: "The slice of your earlier plate has expired;
  add its parts again to print it." The notification appears only when that slice was
  never sent. M18 now states the behaviour plainly and asks whether dropping it is right
  and how long to keep it. Seen in
  [320-come-back-later-slice-expired.png](screenshots/320-come-back-later-slice-expired.png).
  After sending, the notification at Setup is only "Your print finished at …"
  ([320-come-back-later-your-print-finished.png](screenshots/320-come-back-later-your-print-finished.png)).
- **The Setup step names the other student.** The behaviour is unchanged ("Shop H2S …
  Heating for Alex Chen, 2 h 29 min left" after a reopen). Decision 47 now says plainly
  that the Setup line names that student, that the brief asked only for the icon, and asks
  whether to keep it.

## Choices made

- With no printer paired, the Setup and Layout steps still name the printer **model**.
  The team's profiles and the plate's size come from it, so that is true. They no longer
  name **Shop H2S**, the paired printer.
- The plate's name in words is always "Plate 1, N instances", since the mockup has one
  plate per Part Studio.
- The waiting phase keeps the label "Printing" in the printer details, because the print
  is under way and only paused.

## Screenshots

Replaced, because they showed a fixed defect: `320-2-parts`, `800-2-parts-export-failed`,
`800-2c-parts-server-unreachable-failed`, `320-preview-connection-lost-cancel-off`,
`320-5b-send-printing`, `320-send-your-print-waiting-for-person`,
`320-printer-status-open-yours`, `320-send-busy-printer`, `800-5b-send-busy-printer`,
`320-resumed-preview-after-refresh-still-slicing`,
`320-resumed-preview-after-refresh-sliced`, `320-resumed-send-after-refresh`,
`320-come-back-later-your-print-finished`. Added: `320-standalone-server-down`,
`320-send-no-printer-paired`, `320-setup-no-printer-paired`,
`320-advanced-printer-icon`, `320-advanced-printer-icon-open`,
`320-come-back-later-slice-expired`.

## Not done

Nothing in the review is left open. One combination the scenario strip allows was not
changed: switching the Printer menu to "No printer paired" while this student's own plate
is printing keeps the print's own lead. A real printer cannot become unpaired in the
middle of a print.
