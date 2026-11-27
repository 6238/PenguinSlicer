# Brief: review of wizard mockup version 7

- **Deliverable (REQUIRED):** `docs/orchestration/mockup-v7/review-1.md`: every finding
  with its severity (serious, medium, low), where it is (step, width, state), what is
  wrong, why, and the smallest fix; screenshots that show the findings in
  `docs/orchestration/mockup-v7/screenshots/review-*.png`.
- **Stop condition (REQUIRED):** every step walked at 320, 480 and 800 px panel widths
  in every state the scenario strip offers; every point of the owner's feedback checked;
  every user-visible string read.
- **Budget (REQUIRED):** 120 minutes; no cloud spend.
- **Where this fits:** you did not build this. The builder's brief is
  [brief.md](brief.md); do not read the builder's `result.md` until your own findings
  are written, then check its claims. A fix round follows your review.

## What to check

1. **The owner's feedback is met.** The feedback file was folded into `DECISIONS.md`
   and deleted; read it as it was with
   `git -C <checkout> show HEAD~1:docs/handoffs/2026-11-25-mockup-v6-feedback.md` (or
   find the commit that deleted it with `git log --diff-filter=D --oneline -- docs/handoffs/`),
   and check it point by point, and the brief's notes. Check especially that the
   rotation handle stays bound to the instance while dragging, at every width.
2. **The owner's interface preferences** (read all three, they are the bar):
   - `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-penguinslicer-wizard-looks-like-penguincam.md`
   - `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-penguinslicer-not-only-frc.md`
   - [the visual reference](../../reference/penguincam-in-onshape/README.md) and
     PenguinCAM's own `/repos/popcornpenguins/PenguinCAM/static/wizard.css` (read only).
   In short: light, like PenguinCAM and Onshape; works at 320 px and uses width up to
   about 800 px; little help text on working screens, generous error text specific to
   the error; no "student", "mentor" or "team" in text a user sees; basic features
   only, no over-engineering; one name per thing.
3. **Interface best practice at each width:** layout that never overflows or scrolls
   sideways; controls that are not cramped and line up; touch and click targets of a
   sane size; readable contrast in the light theme; focus order and visible focus;
   keyboard use of the accordion, chevrons, chips and the printer-status details;
   things that move or jump when state changes; truncated or wrapped labels; consistency
   of the same element across steps (chips, cards, buttons, chevrons).
4. **Correctness of the imitation:** wrong or inconsistent numbers (units, spacing 5 or
   12 mm, sizes), sentences that are false in some state, broken Back and Next, console
   errors.

Do not fix anything; report only. Prefer fewer, well-argued findings over a long list of
taste; mark taste as such.

## Walk and rules

Serve the folder on a free port other than 6238 and 6249 and drive a browser with
`playwright-cli` (session name in `$PLAYWRIGHT_CLI_SESSION`); for WebGL read
`/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`.
Stop every server and browser you start and remove any `.playwright-cli/` folder. Read
[the standing rules](../review-feedback/briefs/standing-rules.md). Commit your review on
`mockup/v7`; do not push. Scratch folder:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/mockup-v7-review/`.
