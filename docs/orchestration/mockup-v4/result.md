# Result: wizard mockup version 4

Built on Sat 2026-11-21 (Pacific). The mockup is
[docs/mockups/print-wizard/index.html](../../mockups/print-wizard/index.html); its
decisions, open questions and fakes are in
[DECISIONS.md](../../mockups/print-wizard/DECISIONS.md), rewritten to version 4.
Screenshots are in [screenshots/](screenshots/).

## Sources

The brief's links to `docs/reference/` point to files that are not in this checkout. The
coordinator had fetched them from the branch `visual-reference/penguincam` into the
scratch folder (`scratchpad/ref/`); I read the owner's notes there (the sections
"Feedback of Sat 2026-11-21" and "Mockup feedback of Sat 2026-11-21", which the checkout's
copy of the feedback notes does not have yet), the visual reference README, and decoded
and looked at the three PenguinCAM screenshots and `export-failed.png`. PenguinCAM's
wizard HTML is at `templates/wizard.html`, not `static/wizard.html`.

## What changed

| File | Change |
|---|---|
| `css/panel.css` | Rewritten: PenguinCAM's light theme and measurements; printer-status icon and details; notifications; Send step; arrival progress; container queries at 520 and 680 px. |
| `css/frame.css` | The scenario strip in three short rows that can drop to one or hide behind a tab; the standalone page light. |
| `index.html` | Five step tabs; the header's printer-status icon and details; notifications area; instruction lines under each title; the Send step; Duplicate, Delete, Undo, Redo removed; the final split button moved to the Send step; the strip's new controls (Printer, Refresh page, Close and reopen, Come back 2 h later, new armed errors). |
| `js/wizard.js` | Five steps; the printer model shared by the icon, Setup and Send; the Send step; repeat click raises the quantity; arrival with progress and the two failure notifications; profile change clears changes; slices that survive leaving the step; coming back; every message cleaned of internals; limit 150; the owner's M8, M9 and M15 answers (sent mid-run by the coordinator). |
| `js/frame.js` | The strip's new controls; drag limits 300 to 900 px. |
| `js/layout3d.js`, `js/preview3d.js` | Light scene colours; Delete, Ctrl+D, Ctrl+Z, Ctrl+Y no longer handled. |
| `DECISIONS.md` | Rewritten to version 4. |

## The owner's points, and where each is met

| Point | Where |
|---|---|
| Light mode, dark theme gone | panel.css `#wizard` tokens; 3D scenes light. DECISIONS 1. |
| PenguinCAM's font, sizes, controls, spacing, from its CSS | panel.css copies `static/wizard.css` values (14 px/1.45, pills 12 px 3×10, chips 3×9, h2 18 px, buttons 8×14 r6, body 14 px, nav 10×14 gap 10, part rows 8 px gap 10 with 44 px pictures). DECISIONS 1. |
| Header with name and config line; "PenguinSlicer"; "6238 (Popcorn Penguins)" | index.html header. Screenshot `320-1-setup.png`. |
| Numbered pill tabs with check marks, chips row, bold title with instructions, light cards, wide Back and Next | Every step screenshot. |
| Fluid width, 320 to about 800, width control kept | Container queries; `800-*` screenshots; width menu 320/480/640/800 and the drag handle. Checked: no horizontal overflow at 320 on every step. |
| Scenario strip must not hide the panel | It sits above the page; Fewer controls and Hide strip. |
| Keep quantity, 3D picture, slicing progress, advanced mode, the three switchable options | Kept; `320-2-parts.png`, `320-4a-preview-slicing.png`. |
| Five steps; back and forward always work | DECISIONS 3, 29. Back from a slicing Preview leaves it running; tested Back then Next returns to the live card. |
| Layout: no duplicate, delete, undo, redo | Removed with their keys. DECISIONS 24. |
| Send step: printer, instances, time, filament, clear-plate reminder; sends at once; then progress; pause/stop at the printer only | `320-5a-send-ready.png`, `320-5b-send-printing.png`, `320-send-your-print-waiting-for-person.png`. DECISIONS 35 to 40. |
| Repeat click raises quantity and flashes the row | DECISIONS 14; `320-2-parts.png` (pulley clicked three times). |
| Profile change clears changes, said beside the menu first | `800-1b-setup-profile-clears-changes.png`. DECISIONS 11. |
| Instance limit 150 | `MAX_INSTANCES = 150`, as `slice/src/penguin_slice/limits.py`. |
| Printer-status icon on every step, its states, details on a click | `printer-icon-closed-*.png`, `320-printer-status-open-yours.png`, `320-printer-status-open-other-student.png`, `800-printer-status-open-other-student-behind.png`. DECISIONS 43, 44. |
| Busy printer on Send: whose, what, how far, when; Send disabled; file stays ready; nothing queues | `320-send-busy-printer.png`, `800-5b-send-busy-printer.png`. DECISIONS 41. |
| Coming back: refresh, close and reopen, return later; resume on Preview or Send; another's work starts at Setup | `320-resumed-preview-after-refresh-still-slicing.png`, `320-resumed-preview-after-refresh-sliced.png`, `320-resumed-send-after-refresh.png`, `320-reopen-other-student-sending-starts-at-setup.png`, `320-come-back-later-your-print-finished.png`. DECISIONS 45 to 48. |
| Export failure: notification, not added, Next enabled, no Try again, mentor wording, no internals | `800-2-parts-export-failed.png`. DECISIONS 16. |
| Server unreachable: quiet retries, progress, "taking longer", failure only after retries, no broken entry | `800-2b-parts-server-slow-taking-longer.png`, `800-2c-parts-server-unreachable-failed.png`. DECISIONS 17. |
| Every other error card cleaned of internals | Removed: page id, HTTP method and status, route, `plate_volume_cm3`, Orca's return code and `result.json`, relay and daemon wording, printer serial, `print_error` code, printer state names. Kept for a mentor: Orca Slicer's own sentence with heights, and where to look. DECISIONS 32. |
| DECISIONS.md to version 4: answered questions built in, M1 to M9, M11, M15, M16 kept, new from M17, "What changed" at the top | Done. M8, M9 and M15 were then answered mid-run and are built in too (DECISIONS 25, 26, 31); open now: M1 to M7, M11, M16, and new M17 to M24. |
| Printer states as delivery reports them; requirements where it does not | DECISIONS "Requirements on printer delivery": who sent it, a plate description, where `expected_s` comes from, finding one's own job after a refresh, how long the last print's end is kept; and one on the slice service (finding one's own slice job after a refresh). |

## Choices I made (the brief left them open)

1. Five tabs at 320 px wrap to two rows, as PenguinCAM's would; I kept PenguinCAM's tab
   exactly rather than invent a narrower one (M20).
2. Leaving the Preview step while slicing leaves the slice running; a changed plate
   restarts it (M17).
3. A part still arriving never holds Next; a late part joins the plate on the Layout step
   (M21).
4. Notifications belong to the step they were given on and go when the student leaves it.
5. Cancel sending kept, since printer delivery allows a cancel before its start gate
   (M22). Download moved to the Send step's caret menu (M23).
6. "Behind its estimate" from 5 minutes, with "· late" on the icon (M24).
7. A finished unsent slice survives a refresh and a reopen but not two hours (M18); after
   two hours an ended print of this student's is a notification at Setup and the plate is
   not kept (M19).
8. The layer preview no longer follows the running print (it is on the Preview step, the
   progress on the Send step). M11 says so.
9. Two departures from PenguinCAM's CSS: amber text `#9a6700` instead of `#d29922` (too
   faint on white), and a light hover on step tabs (PenguinCAM's light theme keeps a dark
   hover colour).
10. Drag limits 300 to 900 px (300 is PenguinCAM's `min-width`).
11. Another student's print runs 30 times faster at Fast speed (yours 900), so the busy
    printer can be watched freeing up.
12. A person "resumes at the printer" 10 mock minutes after a print starts waiting.

## The walk

Served on port 8765 (not 6238), Chrome under the existing Xvfb with SwiftShader, one tab.
Walked at 320 and 800 px through every step, and at 480 and 640 px for the Layout
parking case and the standalone page; every scenario-strip control used at least once:
width menu, Context (all three), Speed (both), Printer (another student sending,
printing, printing behind, door open; offline; not paired), Refresh page, Close and
reopen, Come back 2 h later, Parts arrive (as modelled, for the parking case), and armed
errors 1a, 1b, 1c, 3a, 3b, 3c, 4, 7, 9, 10a, 10b (with the assembly button's own failure).
A second pass covered the rest: Reset, Fewer controls, Hide strip and its tab, the
Printer menu's Free, Last print finished and Last print failed, armed 2 (not watertight),
5 (faulty mesh), 6 (timeout) and 8 (auto-cancel), and every Lay on face and Mouse option
(switched on the Layout step; not dragged by hand, since that code is version 3's,
changed only in colour). The console showed no error or warning at each check. Browser and server
stopped; `.playwright-cli/` removed.

## What still differs from PenguinCAM (side by side with its screenshots)

- **Parts:** PenguinCAM's row is a 44 px blue outline, the name, the size and a red ×.
  Ours adds a 3D picture, ↻ and a quantity box (the owner keeps both), so long names are
  cut short at 320 px. PenguinCAM's select prompt reads "Select a face in Onshape…"; ours
  "Click a part in Onshape…".
- **Layout:** PenguinCAM has a machine card ("Avid CNC Pro2424 · Bed · Tool") above a
  2D canvas with Flip over and zoom − +. Ours has Arrange and Auto-orient, a one-line status,
  and a 3D view; the printer's plate size is a quiet line at the bottom, not a card.
- **Preview:** PenguinCAM's is "Preview & Save": one line of stats, a light 3D toolpath
  view, then a move scrubber with play, restart, speed and Reset view, and the final split
  button on this step. Ours shows two stat tiles, a vertical layer bar inside the view and
  a legend; its final action is on the Send step.
- **Steps:** five tabs instead of four; at 320 px they wrap to two rows.
- **Header:** ours has the printer-status icon; PenguinCAM has nothing there.
- **New idioms PenguinCAM lacks:** notifications, the printer details, the Send step's
  cards.
- **Fonts:** the same stack; the screenshots were taken on Linux and render in its
  fallback sans, not the Mac's system font, so they are not a pixel comparison.

## What I could not do

- The brief's reference paths do not exist in the checkout (see Sources).
- No pixel-level comparison at equal panel widths: PenguinCAM was not run (its server and
  port 6238 are out of bounds), so the sizes are matched from its CSS, not measured side
  by side.
