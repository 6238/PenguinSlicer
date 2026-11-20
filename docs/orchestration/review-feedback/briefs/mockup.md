# Brief: new terms in the wizard mockup

- **Deliverable (REQUIRED):** the renames below in `docs/mockups/print-wizard/` only, and
  a result file at `docs/orchestration/review-feedback/results/mockup.md` listing what
  changed, every sentence you reworded beyond a plain word swap, and what you walked.
- **Stop condition (REQUIRED):** no visible text, code identifier or sentence of
  `DECISIONS.md` uses "copy" for one placement of a part; the mockup has been walked in
  a browser through all four steps, advanced mode, and every option of the three
  scenario-strip menus (Lay on face, Mouse, Parts arrive) with no console error.
- **Budget (REQUIRED):** 60 minutes; no cloud spend.
- **Inputs:** [standing-rules.md](standing-rules.md) first, then
  `docs/mockups/print-wizard/DECISIONS.md` and the mockup's files. For a browser with
  WebGL in this container, read
  `/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`.
  Drive the browser with `playwright-cli`; serve the folder on a free port other than
  6238.

The owner has not finished reviewing the mockup. **Change nothing but the terms:** no
behaviour, no layout, no option, no question in `DECISIONS.md` added, removed or
renumbered.

## The renames

- "copy" and "copies", where they mean one placement of a part, become "instance" and
  "instances": in the text a student sees, in the scenario strip, in comments and code
  identifiers, and in `DECISIONS.md`. The owner's objection was that "copy" reads wrongly
  for a part that is on the plate once, so read every changed sentence with one instance
  and with several, and reword any that reads oddly. A quantity field may stay
  "Quantity".
- `MAX_COPIES` becomes `MAX_INSTANCES`, and its value becomes 100: the owner wants to
  print as many as 100 small spacers on one plate.
- "Penguin Slicer" becomes "PenguinSlicer"; "plate job" becomes "plate configuration";
  "HTTP face" becomes "HTTP interface", wherever they appear.
- The word "face" for a face of a part ("Lay on face") stays.
