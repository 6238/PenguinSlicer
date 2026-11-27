# Brief: wizard mockup version 7

- **Deliverable (REQUIRED):** mockup version 7 in `docs/mockups/print-wizard/`, its
  `DECISIONS.md` updated to version 7, the lay-on-face note
  `docs/research/2026-11-21-lay-on-face-hull-faces.md` updated for the bounding-box
  patches, and a result file at `docs/orchestration/mockup-v7/result.md` listing every
  point of the owner's feedback with where it is met, every choice you made, and what
  you could not do.
- **Stop condition (REQUIRED):** every point of the feedback is met or answered in the
  result file; the mockup walked in a browser at 320, 480 and 800 px through every step
  and scenario-strip control with no console error; the rotation handle dragged on at
  least three parts (one long, one round, one multi-selection), with and without Shift;
  every part tried with lay on face; screenshots saved to
  `docs/orchestration/mockup-v7/screenshots/`.
- **Budget (REQUIRED):** 180 minutes; no cloud spend.
- **Where this fits:** the owner reviewed version 6 and is working on documents in
  another session. A fresh Fable reviewer walks your version afterwards; a fix round may
  follow.

## Read first

1. **The feedback:** the owner's feedback on version 6, a handoff note of Wed 2026-11-25
   (deleted once built: its points are in [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md),
   "What changed in version 7", and listed one by one in [the result](result.md)).
   Every bullet is a requirement.
2. The mockup and its `DECISIONS.md`; the version 6 records in
   [mockup-v6](../mockup-v6/) (brief, review, fix) for what was just done.
3. The owner's interface preferences:
   `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-penguinslicer-wizard-looks-like-penguincam.md`
   and `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-penguinslicer-not-only-frc.md`:
   light, like PenguinCAM; works at 320 px, uses width up to about 800 px; little help
   text on working screens, generous error text; no role words; basic features only.

## Notes on the harder points

- **The rotation handle** (the owner found dragging it broken): bind it to the
  instance as the feedback says. Read `js/layout3d.js` (`placeHandle`, the `rotate`
  drag): today the handle follows the pointer while the instance snaps, its distance is
  recomputed from the turning bounding box, and it can hop sides to avoid patches
  mid-drag. Fix all three. Free turning with an angle readout; Shift snaps to 45°; say
  so in the handle's tooltip ("Drag to turn · Shift: 45° steps").
- **Bounding-box patches for round parts:** a direction of the part's bounding box (six
  sides, in the instance's own frame) is "uncovered" when no kept hull face's outward
  normal is within about 30° of it; draw a patch on each uncovered side, styled like the
  hull patches, and a click lays the instance on that side. Check the pulley and the
  spacer (they must gain rim patches) and the boxy parts (they must gain none). Update
  the research note: what the rule is, and what the real wizard would need beyond it.
- **Printer "finished" versus "free":** the icon never shows a "Finished" state; the
  scenario strip's printer states change to match (a print that ended shows Free, with
  the last-print line). Keep the 12-hour window and "until the next send" in the
  imitation, with a scenario-strip control to imitate "12 hours later".
- **Units:** printer and plate figures always in millimetres (plate line, spacing in
  errors, Preview's layer readout); part sizes follow the part's units.
- **Mockup notices:** remove every "Mockup: …" notice from the panel; move what they
  said into `DECISIONS.md`'s "What is fake and could mislead" or the scenario strip.

## `DECISIONS.md`

Add "What changed in version 7" at the top. Fold the owner's answers into the design;
questions answered stop being questions: M19, M20, M27, M28. Keep the numbers of the
questions still open. When everything in the feedback file is in `DECISIONS.md`,
delete the feedback file with `git rm` (literal path) and fix any link to it.

## Do not

Change anything the feedback does not ask for. Do not touch `slice/`, `delivery/`,
`contracts/`, `docs/plans/` or the component READMEs: another session is editing
documents.

## Walk and rules

Serve the folder on a free port other than 6238 and 6249 and drive a browser with
`playwright-cli` (session name in `$PLAYWRIGHT_CLI_SESSION`); for WebGL read
`/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`.
Stop every server and browser you start and remove any `.playwright-cli/` folder you
leave in the repository. Read [the standing rules](../review-feedback/briefs/standing-rules.md)
and follow them, with these differences: your folders are `docs/mockups/print-wizard/`,
`docs/orchestration/mockup-v7/`, the lay-on-face research note and the feedback file;
your scratch folder is
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v7/`.
The branch `mockup/v7` is checked out; commit on it; do not push.
