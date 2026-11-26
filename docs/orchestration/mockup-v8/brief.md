# Brief: wizard mockup version 8

- **Deliverable (REQUIRED):** mockup version 8 in `docs/mockups/print-wizard/`, its
  `DECISIONS.md` updated to version 8, and a result file at
  `docs/orchestration/mockup-v8/result.md` listing every point of the owner's feedback
  with where it is met, every choice you made (the four preview colours with their hex
  values and why), and what you could not do.
- **Stop condition (REQUIRED):** every point of the feedback is met or answered in the
  result file; the mockup walked in a browser at 320, 480 and 800 px through every step
  and scenario-strip control with no console error; the preview rendered and looked at
  with supports on and off at no fewer than five layer counts (first layer, a few layers,
  about half, nearly all, all) on at least two plates; screenshots saved to
  `docs/orchestration/mockup-v8/screenshots/`.
- **Budget (REQUIRED):** 180 minutes; no cloud spend.
- **Where this fits:** the owner reviewed version 7 and expects this to be the last round
  on the mockup before implementation. A fresh Fable reviewer walks your version
  afterwards; a fix round may follow.

## Read first

1. **The feedback:** the owner's feedback on version 7, given Thu 2026-11-26 in
   `docs/handoffs/2026-11-26-mockup-v7-feedback.md` (now folded into
   [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) and deleted; every point is
   listed in [the result](result.md)). Every bullet is a requirement.
2. The mockup and its `DECISIONS.md`; the version 7 records in
   [mockup-v7](../mockup-v7/) (brief, review, fix) for what was just done.
3. The owner's interface preferences:
   `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-penguinslicer-wizard-looks-like-penguincam.md`
   and `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-penguinslicer-not-only-frc.md`:
   light, like PenguinCAM; works at 320 px, uses width up to about 800 px; little help
   text on working screens, generous error text; no role words; basic features only.

## Notes on the harder points

- **Step-circle tooltips:** a custom tooltip, not the `title` attribute: shown after a
  short delay (about 150 ms) on hover and at once on keyboard focus, hidden on Escape,
  pointer leave and blur; PenguinSlicer's font, at least the body text size; styled like
  the wizard's other floating surfaces (the printer details, the chip popover); kept
  inside the panel at 320 px; reachable by screen readers (`aria-describedby` or an
  accessible name). If the wizard already has other `title` tooltips on working
  controls, give them the same tooltip only if it is simple to do; say what you did.
- **Advanced mode open state:** sections open by default; a setting's open state is its
  changed-setting detail or whatever opens on it today. Keep the state in memory in the
  page (no `localStorage`); it survives switching steps, closing and reopening advanced
  mode, and widths crossing 480 px (accordion and rail). The expand/collapse-all icon
  still works and updates the remembered state.
- **Printer details on hover:** open on pointer enter of the icon, stay open while the
  pointer is over the icon or the details, close after a short grace delay on leave;
  a click still opens (and pins it open until a click elsewhere or Escape); keyboard and
  touch behave as today. No flicker when moving from the icon to the details.
- **Arrange:** find where Arrange resets orientation and make it keep each instance's
  orientation; spacing (5 or 12 mm) and the placement check use the oriented footprint.
- **Preview colours:** four fixed colours, chosen on reasoning you write down (hue
  spacing, lightness contrast against the background `#f2f4f7` and against each other,
  checked for deuteranopia, protanopia and tritanopia with a simulation, not by eye).
  The key opens from a small icon in the preview, closed by default, four rows.
- **Test renders:** script the renders with `playwright-cli` and look at every image
  yourself. Tune what the images show needs tuning: line weight or width, the ghost of
  the part, the current layer's emphasis, lighting, camera. Keep the before and after
  images and say in the result what each change fixed.

## `DECISIONS.md`

Add "What changed in version 8" at the top. Fold the feedback into the design; keep the
numbers of the questions still open. When everything in the feedback file is in
`DECISIONS.md`, delete the feedback file with `git rm` (literal path) and fix any link to
it.

## Do not

Change anything the feedback does not ask for. Do not touch `slice/`, `delivery/`,
`contracts/`, `docs/plans/` or the component READMEs: another session is editing
documents.

## Walk and rules

Work only in the checkout
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-checkout`,
never in `/repos/popcornpenguins/penguin-slicer`. Serve the folder on a free port other
than 6238 and 6249 and drive a browser with `playwright-cli` (session name in
`$PLAYWRIGHT_CLI_SESSION`); for WebGL read
`/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`.
Stop every server and browser you start and remove any `.playwright-cli/` folder you
leave. Read [the standing rules](../review-feedback/briefs/standing-rules.md) and follow
them, with these differences: your folders are `docs/mockups/print-wizard/`,
`docs/orchestration/mockup-v8/` and the feedback file; your scratch folder is
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v8/`.
The branch `mockup/v8` is checked out; commit on it; do not push. No `rm` on paths built
from variables, no `cd … &&` chains, no `eval` or `sh -c`; edit files with the Edit and
Write tools only.
