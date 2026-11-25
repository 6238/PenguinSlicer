# Brief: wizard mockup version 6

- **Deliverable (REQUIRED):** mockup version 6 in `docs/mockups/print-wizard/`, its
  `DECISIONS.md` updated to version 6, and a result file at
  `docs/orchestration/mockup-v6/result.md` that lists every point of the owner's
  feedback with where it is met, every choice you made, and what you could not do.
- **Stop condition (REQUIRED):** every point of the feedback below is met or answered in
  the result file; the mockup has been walked in a browser at 320, 480 and 800 px panel
  widths through every step and every scenario-strip control, with no console error;
  screenshots saved to `docs/orchestration/mockup-v6/screenshots/`.
- **Budget (REQUIRED):** 180 minutes; no cloud spend.
- **Where this fits:** the owner reviewed version 5 a step at a time (Parts, the
  printer-status icon, Settings with advanced mode, Preview) and is asleep. A fresh
  reviewer walks your version afterwards; a fix round may follow. The mockup is a
  click-through imitation; the repository's test-suite bar does not apply, but a clean
  console and a careful walk do.

## Read first

1. **The feedback:** [the feedback notes](../../handoffs/2026-11-20-session-summary-feedback.md),
   the whole section "Mockup version 5 feedback of Tue 2026-11-24". Every bullet there
   is a requirement. Read the earlier sections too for the rulings still in force.
2. The mockup as it is, `docs/mockups/print-wizard/`, and its `DECISIONS.md`.
3. [The visual reference](../../reference/penguincam-in-onshape/README.md): the wizard
   still looks like PenguinCAM (light, PenguinCAM's sizes, works at 320 px, uses width
   up to about 800 px).

## The points that reach across the whole mockup

- **No role words.** No text a user sees says "student", "mentor" or "team" (the
  header's configuration name "6238 (Popcorn Penguins)" is a name and stays). Where a
  permission difference must be named, say "administrator". Check every string in the
  JavaScript and HTML, including error and notice text, tooltips and the scenario
  strip's labels that describe what the user sees.
- **Little help text on the working screens, generous error text.** Remove the
  instructions under step titles and controls on every step, not only the sentences the
  owner named; keep a short line only where an action has a consequence the user cannot
  see or a control does not explain itself. Errors keep and may gain information that is
  specific to that error and helps fix it; no generic troubleshooting, no internals. List
  every sentence you removed or kept, by step, in the result file.
- **Step 2 is renamed "Settings"** everywhere: tabs, chips, text, `DECISIONS.md`.
- **Units.** Implement the units rules in the feedback. Give the mockup's Onshape parts
  their document's units (make most of them inches and at least one Part Studio metric,
  and show both cases), uploaded files in inches by default, and add to the scenario
  strip a switch for the configuration option that makes millimetres the default for
  uploaded files. Plate size in millimetres; spacing and heights in inches when every
  part on the plate is in inches, otherwise millimetres; slicer settings always in
  millimetres. Show inches the way a US machinist reads them (decimal inches, for
  example 2.000 × 2.000 × 0.188 in); say in the result file what you chose.
- **Arrange and the placement check** use 12 mm between instances with supports on and
  5 mm with them off, from the Settings step's supports setting. Turning supports on
  after arranging moves nothing; instances now too close get the usual message until
  the user presses Arrange or drags them.
- **Per-filament profiles:** each filament has its own list of profiles in the mockup's
  configuration, with different names.

## `DECISIONS.md`

- Add "What changed in version 6" at the top. Fold each answer into the design under
  "Every decision"; questions the owner answered stop being questions: M5 (always one
  column, accordion below 480 px), M24 (no "behind its estimate"; drop the late label),
  the step name, the Arrange spacing, and decision 47 if the new wording settles it.
  Keep the numbers of the questions still open.
- Use "user" for the person using PenguinSlicer and "administrator" for whoever edits
  the configuration, throughout the document, and check the terms table.
- Requirements on printer delivery: drop any that the owner's cuts made unnecessary
  (for example where `expected_s` comes from, if nothing shows "behind" any more), and
  say which you dropped.

## Do not

- Do not change the Layout step beyond what the points above require (units, spacing,
  role words, help text); the owner has not reviewed it yet.
- Do not change anything in `slice/`, `delivery/`, `contracts/` or the plan.

## Walk and rules

Serve the folder on a free port other than 6238 and 6249 and drive a browser with
`playwright-cli` (session name in `$PLAYWRIGHT_CLI_SESSION`); for WebGL read
`/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`.
Save screenshots of: each step at 320 and 800 px; the Settings step at 480 px; advanced
mode at 320 px (accordion, one section open, a changed setting) and at 800 px (rail, one
column); the yellow box of changed settings; the "+1 change" chip opened; the
printer-status details open in each state; the Preview step with supports on; parts in
inches and in millimetres. Stop every server and browser you start and remove any
`.playwright-cli/` folder you leave in the repository.

Read [the standing rules](../review-feedback/briefs/standing-rules.md) and follow them,
with these differences: your folders are `docs/mockups/print-wizard/` and
`docs/orchestration/mockup-v6/`; your scratch folder is
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v6/`.
The working branch `mockup/v6` is checked out; commit your work on it, do not push.
