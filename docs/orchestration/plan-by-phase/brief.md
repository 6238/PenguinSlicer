# Brief: the plan by phase, and where each component stands

- **Deliverable (REQUIRED):** a new plan at `docs/plans/penguin-slicer-plan.md`; a
  "Where it stands" section in `slice/README.md` and in `delivery/README.md`; the words
  "student" and "mentor" replaced in the documents listed below; the restart plan and
  the session summary deleted with every pointer to them updated; a result file at
  `docs/orchestration/plan-by-phase/result.md` listing what you did, every choice, and
  where each section of the two old documents went (or why it was dropped).
- **Stop condition (REQUIRED):** every fact, requirement and decision still true in the
  two old documents and in the non-mockup parts of the feedback notes is in the new plan
  or a component's README, or listed in the result file as dropped with the reason; no
  link in the repository outside `docs/orchestration/` points to a deleted file; every
  Mermaid diagram you write renders.
- **Budget (REQUIRED):** 150 minutes; no cloud spend.
- **Where this fits:** the owner (asleep now) will read the new plan instead of the rest
  of the session summary. A Fable reviewer checks your work for correctness,
  over-engineering and security before the owner sees it; a fix round may follow.
  Another agent is building mockup version 6 in another checkout at the same time: do
  not touch `docs/mockups/`.

## Read first

1. [The restart plan](../../plans/2026-11-19-penguin-slicer-restart-plan.md) and
   [the session summary](../../handoffs/2026-11-20-penguin-slicer-session-summary.md).
   The owner reviewed the summary's sections 2.1, 3 and 4.1; the rest is unreviewed.
2. [The feedback notes](../../handoffs/2026-11-20-session-summary-feedback.md): every
   section. The decisions in them that are not about the mockup belong in the plan; the
   mockup ones are being folded into `docs/mockups/print-wizard/DECISIONS.md` by the
   other agent, so the plan only points there.
3. `README.md`, `CLAUDE.md`, `slice/README.md`, `delivery/README.md`, `contracts/*.md`,
   and `git log --oneline` for what has been built (pull requests 1 to 12).
4. The owner's preferences for documents: `/home/agent/.claude/CLAUDE.md` (one name per
   thing, real Markdown links, Mermaid not ASCII art, Pacific times with weekday and
   date, no time estimates, no priorities unless asked, order by risk when asked), and
   `/home/agent/.claude/projects/-repos-popcornpenguins/memory/feedback-no-decision-lists-in-documents.md`:
   a document describes the current state; decided answers are folded into the text,
   never kept as a running list of decisions.

## The plan

The owner's plan of attack for the next several days, in this order:

1. **Finish the mockup.** The owner still reviews the Layout step; then the wizard's
   spec is written as `wizard/README.md` from the mockup and its `DECISIONS.md`.
2. **The wizard outside Onshape, running locally.** The wizard's real code, opened
   directly in a browser (not inside Onshape), parts uploaded from files, talking to the
   slice service running on the same machine; the user downloads the sliced file
   (G-code). No printer.
3. **The same on AWS.** The slice service and the wizard hosted on AWS. Nothing about
   hosting has been designed: list the questions a design session must answer (which AWS
   service, memory per slice job and per slice service process — a slice peaks at 1 to
   2 GB, measured figures are in `slice/README.md` — how many at once, who may use a page
   reached from the open internet, storage and lifetime of uploaded parts and sliced
   files, logs and telemetry, cost, how a new Orca version is rolled out). Answer none of
   them.
4. **Inside Onshape.** The wizard in Onshape's right panel; the Onshape source (picking
   parts, exporting them, units from the document) and the Onshape app registration.
5. **The real printer.** Printer delivery (relay and daemon, built and tested against a
   simulated printer only) sending to the real Bambu Lab H2S; daemon telemetry (in the
   plan, not designed).

For each phase say what "done" means in a sentence a person can check, which components
it touches, and its risks (what could make it infeasible or costly). Each phase that
builds something starts with a design spec agreed with the owner; say so once, not per
phase. Do not invent decisions the owner has not made; where something is open, say it
is open. No time estimates.

Also in the plan: the terms (one table, current), the four components and `contracts/`
in a sentence each with a link to the component's README, the standing requirements
(errors, progress, cancellation, cleanup, supportable from the server, upstream code,
tests) as they stand, and known future work.

## Where each component stands

In `slice/README.md` and `delivery/README.md`, a short section "Where it stands": what
is built and tested, what is not (for delivery: never run against the real printer by
this code; telemetry not designed), and what the phases above still need from it. Keep
it short; the rest of each README already describes the component.

## Words

The person using PenguinSlicer is a **user**; whoever edits the configuration is an
**administrator**. Replace "student" and "mentor" (and "team" where it means the users,
not FRC Team 6238 as the owner of the repository) in: the new plan, both component
READMEs, `README.md`, `CLAUDE.md`, `contracts/*.md` prose, and
`docs/research/*.md`. Do **not** change any message text the slice service or printer
delivery produce, in code, tests or contract examples: that is a later change of its
own. If a contract's prose describes such a message, leave the message and change only
the prose around it, and list each such place in the result file.

## Deleting the old documents

Delete `docs/plans/2026-11-19-penguin-slicer-restart-plan.md` and
`docs/handoffs/2026-11-20-penguin-slicer-session-summary.md` with `git rm` (literal
paths). Do not delete the feedback notes; the orchestrator does that once both this work
and mockup version 6 are merged. Update every link outside `docs/orchestration/` that
pointed to a deleted file. Leave the records under `docs/orchestration/` as they are:
they are records of past runs.

## Rules

Read [the standing rules](../review-feedback/briefs/standing-rules.md) and follow them,
with these differences: your folders are `docs/plans/`, `docs/handoffs/` (deletion
only), `docs/research/`, `docs/orchestration/plan-by-phase/`, `contracts/` (prose only),
and the README and CLAUDE.md files named above; your scratch folder is
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/plan-by-phase/`.
Commit on the branch already checked out in your checkout; do not push. To render a
Mermaid diagram, see
`/home/agent/.claude/projects/-repos-popcornpenguins/memory/agent-container-webgl-acceptance.md`
(mermaid-cli core dumps there; render through the browser instead).
