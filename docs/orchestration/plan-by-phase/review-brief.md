# Brief: review of the plan by phase

- **Deliverable (REQUIRED):** `docs/orchestration/plan-by-phase/review-1.md`: every
  finding with its severity (serious, medium, low), the file and line, what is wrong,
  why, and the smallest fix.
- **Stop condition (REQUIRED):** every changed or new file read in full; every claim
  about what is built checked against the code, tests or git history; every link
  followed.
- **Budget (REQUIRED):** 90 minutes; no cloud spend.
- **Where this fits:** you did not write this. The writer's brief is [brief.md](brief.md);
  read `git diff 3bc0998..HEAD` for the change. Do not read the writer's `result.md`
  until your own findings are written, then check its claims. The owner reads the plan
  when they wake up; a fix round follows your review.

## What to check

1. **Correctness.** Every statement about what exists, what is tested and what is
   measured is true of the code and tests in the repository (`slice/`, `delivery/`,
   `contracts/`). Nothing true and still needed in the two deleted documents
   (`git show 3bc0998:docs/plans/2026-11-19-penguin-slicer-restart-plan.md`, and
   `git show 3bc0998:docs/handoffs/2026-11-20-penguin-slicer-session-summary.md`) or in
   [the feedback notes](../../handoffs/2026-11-20-session-summary-feedback.md) was lost.
   No decision is invented that the owner did not make; open questions are marked open.
2. **Over-engineering.** Phases, requirements or mechanisms that go beyond what the
   owner asked for; requirements that would make a phase much costlier for little gain.
   The owner dislikes features and machinery added "to be safe".
3. **Security.** Phases 3 (on AWS, a page reachable from the open internet) and 5 (a
   relay and a daemon reaching a printer): does the plan name the security questions a
   design must answer (who may slice, abuse and cost limits, uploaded files as hostile
   input, secrets, the pairing between relay and daemon)? Does any document state or
   imply something insecure, or commit a secret?
4. **The owner's document rules** in `/home/agent/.claude/CLAUDE.md`: one name per
   thing across all the documents (and "user", "administrator" for people; no
   "student" or "mentor" outside quoted service messages); real Markdown links; Mermaid
   that renders, not ASCII art; Pacific times with weekday and date; no time estimates;
   no priorities. And
   `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-no-decision-lists-in-documents.md`.
5. **Links.** No link outside `docs/orchestration/` points to a deleted file.

Do not fix anything; report only. Prefer fewer, well-argued findings over a long list
of taste; mark taste as such.

## Rules

Work in the checkout
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/docs-checkout`
(branch `docs/plan-by-phase`); commit your review there; do not push. Read
[the standing rules](../review-feedback/briefs/standing-rules.md). Scratch folder:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/plan-by-phase-review/`.
