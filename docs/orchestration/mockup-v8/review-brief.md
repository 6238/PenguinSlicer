# Brief: review of wizard mockup version 8

- **Deliverable (REQUIRED):** `docs/orchestration/mockup-v8/review-1.md`: every finding
  with its severity (serious, medium, low), where it is (step, width, state), what is
  wrong, why, and the smallest fix; screenshots that show the findings in
  `docs/orchestration/mockup-v8/screenshots/review-*.png`.
- **Stop condition (REQUIRED):** every step walked at 320, 480 and 800 px panel widths
  in every state the scenario strip offers; every point of the owner's feedback checked;
  every user-visible string that changed in version 8 read; the preview rendered and
  looked at with supports on and off at no fewer than five layer counts.
- **Budget (REQUIRED):** 120 minutes; no cloud spend.
- **Where this fits:** you did not build this. The builder's brief is
  [brief.md](brief.md); do not read the builder's `result.md` until your own findings
  are written, then check its claims. A fix round follows your review. The owner
  expects this to be the last round on the mockup before implementation, so anything
  that would mislead the implementation matters.

## What to check

1. **The owner's feedback is met.** The feedback file was folded into `DECISIONS.md`
   and deleted; read it as it was with
   `git log --diff-filter=D --oneline -- docs/handoffs/` and `git show <commit>~1:docs/handoffs/2026-11-26-mockup-v7-feedback.md`.
   Check it point by point, and the brief's notes. Especially:
   - the step-circle tooltips: delay, size, look, keyboard and screen-reader access,
     never clipped at 320 px;
   - advanced mode's open state: sections open by default, remembered across steps,
     reopening advanced mode and the 480 px switch, the expand/collapse-all icon;
   - printer details on hover: no flicker moving from icon to details, click pins,
     Escape, keyboard, touch;
   - Arrange keeps every instance's orientation and still spaces 5 or 12 mm correctly
     with the oriented footprint;
   - the preview's four colours: distinct (also for colour blindness), legible on the
     light background, calm beside the wizard; the key behind an icon; the preview
     reads well at every layer count.
2. **The owner's interface preferences** (read all three, they are the bar):
   - `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-penguinslicer-wizard-looks-like-penguincam.md`
   - `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-penguinslicer-not-only-frc.md`
   - [the visual reference](../../reference/penguincam-in-onshape/README.md) and
     PenguinCAM's own `/repos/popcornpenguins/PenguinCAM/static/wizard.css` (read only).
   In short: light, like PenguinCAM and Onshape; works at 320 px and uses width up to
   about 800 px; little help text on working screens, generous error text specific to
   the error; no "student", "mentor" or "team" in text a user sees; basic features
   only, no over-engineering; one name per thing.
3. **Interface best practice at each width:** no sideways overflow; controls not
   cramped and aligned; sane target sizes; readable contrast; focus order and visible
   focus; things that jump when state changes; consistency of the same element across
   steps.
4. **Correctness of the imitation:** wrong or inconsistent numbers, sentences false in
   some state, broken Back and Next, console errors, and regressions of what version 7
   fixed (the rotation handle bound to the instance, Shift snapping to 45°, lay on face).

Do not fix anything; report only. Prefer fewer, well-argued findings over a long list of
taste; mark taste as such.

## Walk and rules

Work only in the checkout
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-checkout`,
never in `/repos/popcornpenguins/penguin-slicer`. Serve the folder on a free port other
than 6238 and 6249 and drive a browser with `playwright-cli` (session name in
`$PLAYWRIGHT_CLI_SESSION`); for WebGL read
`/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`.
Stop every server and browser you start and remove any `.playwright-cli/` folder you
create. Read [the standing rules](../review-feedback/briefs/standing-rules.md). Commit
your review on `mockup/v8`; do not push. Scratch folder:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v8-review/`.
No `rm` on paths built from variables, no `cd … &&` chains, no `eval` or `sh -c`; write
files with the Write tool only.
