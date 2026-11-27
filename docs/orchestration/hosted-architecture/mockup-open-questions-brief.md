# Has the owner already answered eight open mockup questions (M6, M7, M11, M21, M22, M23, M25, M26, pointer line)?

Paths are relative to `/repos/popcornpenguins/penguin-slicer/` unless marked `git:`. The owner's
feedback files were deleted from the tree after each build; I read them from git history. A
`git:<commit>:<path>:<line>` locator is read with `git show <commit>:<path>`. Times are
Pacific. D = `docs/mockups/print-wizard/DECISIONS.md`.

## Short answer

Only the "Arrange never turns" half of M6 and the configuration option behind M25 trace to
the owner's own words. The rest are agent choices the owner never reacted to, so the only
evidence for them is the acceptance of version 8 (plan, line 261).

| Question | Status | Answer, in a few words | Source |
|---|---|---|---|
| M6 two buttons; Arrange does not turn | partly | Owner (Thu 11-26): Arrange never turns an instance; recorded as decision 64. "Stay two buttons": no owner word found, an agent's choice | `git:9d7de52:docs/handoffs/2026-11-26-mockup-v7-feedback.md:27`; D:33, D:590 |
| M7 status line, one line enough | no answer found | Never mentioned by the owner; acceptance only | D:229 |
| M11 progress on the Send step | partly | Owner asked for progress with stages, percent, layer, time left, finish (agent's paraphrase); "sent at" and "what else / what can go" never answered | `docs/orchestration/mockup-v4/brief.md:68-70`; D:230 |
| M21 arriving part does not hold Next | partly | Owner: a failed part never disables Next. A part still arriving: agent's choice | `git:da9c6c2:docs/handoffs/2026-11-20-session-summary-feedback.md:154,158-159`; `mockup-v4/result.md:63` |
| M22 Cancel sending stays | decided by an agent, not by the owner | Agent kept it; owner's M12 says the panel offers neither pause nor stop | `mockup-v4/result.md:66`; D:749 |
| M23 Download on the Send step's caret | decided by an agent, not by the owner | Agent placed it; owner only said Send sends at once | `mockup-v4/result.md:67`; D:734 |
| M25 uploaded file in other units | partly | Owner decided the configuration option (inches by default, option for millimetres). Whether it is enough versus a switch per row: never asked of the owner after M25 was raised | `git:da9c6c2:...feedback.md:177-179`; D:237 |
| M26 "Changed only" removed | decided by an agent, not by the owner | Owner removed the search box and the Common / All switch; "Changed only" was the agent's added removal | `git:da9c6c2:...feedback.md:235-236`; `mockup-v6/result.md:165-166` |
| Pointer line larger than 11 px | no answer found | Still the owner's to say; the owner's "larger text" was about tooltips | `mockup-v8/fix-1.md:17,74` |

Acceptance of version 8 is the only evidence for M7, M22, M23, M26 and the pointer line.
For M6, M11, M21 and M25 there is also an earlier owner statement, but it settles only the
part named in the table.

The one decision number you asked for: decision 64 in D ("Arrange never turns an instance",
D:590), summarised in "What changed in version 8" (D:33-37). It came from feedback on
version 7 (given Thu 11-26 09:28 PT, built as version 8), not on version 8.

## Findings

### M6: Arrange and Auto-orient stay two buttons; Arrange does not turn

- The owner's feedback on version 7 says Arrange keeps each instance's orientation — `git:9d7de52:docs/handoffs/2026-11-26-mockup-v7-feedback.md:27` — "Arrange never turns an instance back to its original orientation: every instance keeps the orientation it was given (by lay on face, by the rotation handle, or by the wizard)." — stated (owner's own words; the file's header says "Given Thu 2026-11-26, Pacific time, on mockup version 7")
- Built in as decision 64, marked as the owner's — D:590 — "Arrange never turns an instance (version 8, the owner). Every instance keeps the orientation it was given: by lay on face, by the rotation handle, or by the wizard." — stated
- Same in the version 8 summary — D:33 — "Arrange never turns an instance (decision 64). Every instance keeps the orientation it was given" — stated
- The version 8 result lists it as a point of the owner's feedback, met — `docs/orchestration/mockup-v8/result.md:20` — "Arrange never turns an instance back to its original orientation; every instance keeps its orientation" — stated
- The reviewer confirmed the build — `docs/orchestration/mockup-v8/review-1.md:107` (table row) — "Arrange never turns an instance" — stated
- That statement does not say Arrange and Auto-orient stay two buttons. I found no owner sentence in any record that does. It follows only by inference that Arrange no longer auto-orients first, because it turns nothing — D:590 — "Arrange (both packers, and every Arrange the wizard runs itself, after Auto-orient or "Lay them the best way") only moves instances." — inferred
- M6 is still listed as open — D:228 — "Arrange and Auto-orient stay two buttons. Right, or should Arrange always auto-orient first?" — stated
- Decision 27 still attaches M6 to Arrange's offer — D:564-565 — "Arrange with its two packers (which turn nothing since version 8, decision 64) and its offer to lay instances their best way when that fits more (M6)" — stated
- The "two buttons" arrangement is an agent's choice from the first mockup round (a Fable review, Fri 11-20 00:34 PT) — `docs/orchestration/penguin-slicer/progress.md:457` — "kept Arrange and Auto-orient as two buttons (Arrange offers "lay them the best way" only when it has checked more would fit)" — stated (agent)
- The owner's only remark on the two buttons is about the terms table — `git:da9c6c2:docs/handoffs/2026-11-20-session-summary-feedback.md:20` — "Auto-orient, Arrange are buttons that may change; remove them from the terms table." — stated. D:209-211 now says "they are buttons that may change, not terms."
- Acceptance of version 8 is not the only evidence for the "does not turn" half, which has the owner's own sentence above. For "two buttons", acceptance is the only evidence.

### M7: the status line above the Layout view

- No record has the owner reacting to the status line. D:229 asks — "The status line above the Layout view: does one line say enough, with the full sentences below?" — stated
- Nearest owner words are about other lines: the plate line under the view (owner's wording, D:394-395) and "No text about orientation" (`git:c634a8d:docs/handoffs/2026-11-25-mockup-v6-feedback.md:29-32`, "The view shows the result; the text only makes the screen busier."). Neither names the status line — inferred
- Status: no answer found. Acceptance only (plan, line 261-262; line 283).

### M11: print progress on the Send step

- The progress stages are in the version 4 brief's list "What the owner asked for", which is the coordinator's paraphrase — `docs/orchestration/mockup-v4/brief.md:68-70` — "After sending, the same step shows the delivery and print progress (stages, percent, layer, time left, expected finish)." — stated (agent paraphrasing the owner; the original wording is in no record I found)
- The version 4 review checked it as met — `docs/orchestration/mockup-v4/review-1.md:33` — "After sending: stages, percent, layer, time left, expected finish; pause and stop only at the printer's screen (M12)" — stated
- M11 as it stands adds "sent at" — D:230 — "stages (Sending, Starting, Heating, Printing, Done), percent, layer of total, time left, expected finish and sent at. What else would a user standing at the printer want, or what can go?" — stated. No record shows the owner asking for "sent at".
- Owner rules on the printer details (not the Send step) point the same way — `git:da9c6c2:docs/handoffs/2026-11-20-session-summary-feedback.md:308-309` — "Printing: show who sent it (their Onshape name), percent done, time left and the finish time; nothing more." — stated (owner). Also `git:c634a8d` has none on the Send step's progress; its Send section (lines 40-56) is about "Free" and the last-print note only — inferred
- The version 6 result says the owner called the sending card "good as it was" — `docs/orchestration/mockup-v6/result.md:170-171` — "the bar kept only while sending (the owner said sending was good as it was, and printing "nothing more")" — stated (agent, about the printer details)
- Status: partly. The owner set what progress to show; the question of what else or what can go was never answered. Acceptance covers the rest.

### M21: a part still arriving does not hold Next

- Owner rule on a failed part — `git:da9c6c2:docs/handoffs/2026-11-20-session-summary-feedback.md:153-154` — "Export failed (the part or its STL is broken): show a notification, do not add the part to the list, and do not disable Next." — stated (owner)
- Owner rule on both failure kinds — same file, lines 158-159 — "In either case: a notification, the list of parts unchanged, and never a broken entry in the list that disables Next." — stated (owner)
- The version 4 builder applied it to a part still arriving, as its own choice — `docs/orchestration/mockup-v4/result.md:63` — "A part still arriving never holds Next; a late part joins the plate on the Layout step (M21)." — stated (agent, under "Choices I made (the brief left them open)")
- Open question — D:234 — "A part still arriving does not hold Next. If it arrives after the user has moved on, it joins the plate on the Layout step. Right, or should Next wait for arriving parts?" — stated
- Status: partly. The owner's rule is about broken or failed parts, not a part that is arriving and may succeed. The late-joining behaviour (decision 23, D:440) is an agent's choice.

### M22: Cancel sending stays on the Send step

- Agent's own choice, with its reason — `docs/orchestration/mockup-v4/result.md:66` — "Cancel sending kept, since printer delivery allows a cancel before its start gate (M22)." — stated (agent)
- The owner's ruling M12, as the version 4 brief records it, points the other way — `docs/orchestration/mockup-v4/brief.md:70-71` — "Pausing or stopping a print is done at the printer's screen; the step says so, and the panel offers neither." — stated (agent paraphrasing the owner's M12 answer). D:749 repeats it — "the panel offers neither"
- Open question — D:235 — "Cancel sending stays on the Send step while the file is on its way, before the printer starts. Keep it?" — stated
- Status: decided by an agent, not by the owner. See the conflict below. Acceptance only.

### M23: Download on the caret beside Send

- Agent's own choice — `docs/orchestration/mockup-v4/result.md:67` — "Download moved to the Send step's caret menu (M23)." — stated (agent)
- What the owner decided is that Send sends at once — D:734 — "The Send button sends at once (M10)." — stated. The caret menu is the agent's design.
- Open question — D:236 — "Download moved to the Send step, on the caret beside Send. Right place?" — stated
- A version 6 review finding touched the caret menu, never the place of Download — `docs/orchestration/mockup-v6/review-1.md:252` — "Download cannot be chosen by keyboard" — stated (reviewer agent). The fix is in `mockup-v6/fix-1.md:26`. Not an owner reaction.
- Status: decided by an agent, not by the owner. Acceptance only.

### M25: an uploaded file in the other units

- The owner decided the configuration option — `git:da9c6c2:docs/handoffs/2026-11-20-session-summary-feedback.md:177-179` — "Uploaded from a file (the wizard outside Onshape): inches by default. An option in the configuration (the one the header names, set once by an administrator for everyone who uses it) makes millimetres the default." — stated (owner, Tue 2026-11-24)
- Built that way — D:450-451 — "An uploaded STL file is read in inches unless the configuration makes millimetres the default." — stated
- The agent raised M25 as a new question in version 6 — `docs/orchestration/mockup-v6/result.md:181` — "M25 (per-file units), M26 ("Changed only") and M27 (spacing shown in inches) are new." — stated (agent). The version 7 feedback settled M27 and M28 (D:78) but not M25.
- The version 6 review marked the owner's units rule met without touching per-row switches — `docs/orchestration/mockup-v6/review-1.md:310` — "Uploaded file: inches by default, a configuration option for millimetres | Met" — stated (reviewer agent)
- Status: partly. The owner chose the configuration option as the design, which is what M25 asks about as "the configuration's one option", but never said it was enough over a switch per row. Acceptance is the only evidence for "enough".

### M26: "Changed only" in advanced mode

- Owner removed two things — `git:da9c6c2:docs/handoffs/2026-11-20-session-summary-feedback.md:235-236` — "No search box for the settings. No Common / All switch: every setting is shown, in collapsed groups as in Orca Slicer." — stated (owner, Tue 11-24)
- "Changed only" is in neither owner sentence. The agent removed it too and asked M26 — `docs/orchestration/mockup-v6/result.md:165-166` — ""Changed only" removed with the search and the Common / All switch (asked as M26)" — stated (agent)
- Open question — D:238 — "went with the search box and the Common / All switch, since the changes box, the change details and the changed counts on sections and groups already find a changed setting. Right, or bring it back?" — stated
- Status: decided by an agent, not by the owner. Version 8's advanced-mode feedback (open by default, remembered) never mentions it (`git:9d7de52:...v7-feedback.md:14-18`). Acceptance only.

### The pointer line: larger than 11 px?

- The glossary names the line and its size — D:190 — "A line of the view, 11 px, fixed in its corner: not a tooltip, and not the status line." — stated
- The version 8 reviewer asked for the owner's word — `docs/orchestration/mockup-v8/review-1.md:352` — "the feedback's "larger text" may or may not be meant for this line. That part needs the owner's word." — stated (reviewer agent)
- The owner's "larger text" was about the step circles' tooltips — `git:9d7de52:docs/handoffs/2026-11-26-mockup-v7-feedback.md:10-12` — "appear faster, look like the rest of the PenguinSlicer interface rather than the browser's default tooltip, and have larger text." — stated (owner)
- Fix round 1 left it open — `docs/orchestration/mockup-v8/fix-1.md:17` — "Whether it should be larger is the owner's to say." — stated; also `fix-1.md:74`, and `fix-1-brief.md:32` ("the owner will be asked whether it should be larger")
- The plan lists it as open after acceptance — `docs/plans/penguin-slicer-plan.md:265-266` — "plus whether the Layout view's pointer line should be larger than 11 px" — stated
- Status: no answer found.

## Conflicts and open questions

- Acceptance. The plan says (line 261-262) "the owner accepted it as the last version on Thu 2026-11-26, every step reviewed", and in the same sentence lists M1 to M29 and the pointer line as still open. I read acceptance as not answering them. If the owner means it did, no record says which answer was given, so the answer cannot be stated.
- M22 against M12. The owner's M12 ruling is that the panel offers neither pause nor stop (D:749). Cancel sending is a stop before the printer starts. Whether that fits is for the owner.
- M6 has two parts. "Arrange does not turn" is answered by the owner and built (decision 64). "Two buttons" is not, and D:228 and D:564-565 still treat M6 as open. After decision 64 the second half of M6 ("should Arrange always auto-orient first?") has in effect been answered no, but that is my inference. D:228 should change either way.
- The original owner feedback behind the version 4 brief (Sat 2026-11-21 and later) is not in any record. The brief's "What the owner asked for" is the coordinator's paraphrase, so M11, M22 and M23 may rest on conversation the records do not hold.
- Chat is not a record I could read. The owner may have answered in a session whose text is not kept in these files.
- The version 8 feedback file is in git, not the tree. Its text is at `git:9d7de52:docs/handoffs/2026-11-26-mockup-v7-feedback.md` (42 lines; deleted in `git:c464a61`). The version 6 feedback is at `git:c634a8d:docs/handoffs/2026-11-25-mockup-v6-feedback.md` (90 lines). The version 5 feedback is in `git:da9c6c2:docs/handoffs/2026-11-20-session-summary-feedback.md` (section "Mockup version 5 feedback of Tue 2026-11-24", from line 161).
- Not owner-confirmed either way: "each setting" read as each group (`mockup-v8/fix-1.md:76`, "still needs the owner's nod"). Outside the eight questions.

## Not read

- `mockup-v4`, `mockup-v5`, `mockup-v6`, `mockup-v7`, `mockup-v8` `review-1.md` and `review-brief.md` files: searched with grep for the eight questions and the owner's name, and read in part (v6 lines 205-236 and 305-312; v7 lines 57-125; v8 lines 97-150 and 296-360). I did not read them end to end.
- `mockup-v5` `brief.md`, `result.md`, `review-1.md`; `mockup-v4` `result.md`, `fix-1.md`, `review-1.md`: grep and the parts quoted above. The v5 brief is about Lay on face and step order; none of the eight questions appears in v5.
- `mockup-v6/fix-1.md`, `fix-1-brief.md`, `review-brief.md`, `mockup-v7/review-brief.md`, `fix-1.md`, `mockup-v7/fix-1-brief.md`: grep only; no owner statement on the eight questions.
- `review-feedback/` (`progress.md` read in full; `briefs/mockup.md` read in full; `results/mockup.md` grepped; the slice, delivery and documents results and reviews not read: they concern other components). `review-feedback/progress.md` and `briefs/mockup.md` hold nothing on these questions.
- DECISIONS.md lines 330-941 were read only where grep pointed (decisions 5, 13, 23, 26, 27, 36-38, 51, 57, 62-64). I did not read the rest.
- Not in scope but checked: `wizard/README-details.md:559-562` and `wizard/README.md:159-160` list M6, M7, M11, M21, M22, M23, M25, M26 as "answered by the owner or carried here as an open choice", with no answers given. `docs/orchestration/penguin-slicer/progress.md:457` was read for M6 only.
