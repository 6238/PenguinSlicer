# Brief: the session summary and the plan, rewritten to the current state

- **Deliverable (REQUIRED):** two rewritten files,
  [the session summary](../../../handoffs/2026-11-20-penguin-slicer-session-summary.md)
  and [the plan](../../../plans/2026-11-19-penguin-slicer-restart-plan.md); the new terms
  applied to
  [the wizard research](../../../research/2026-11-19-wizard-layout-and-advanced-mode-research.md);
  and a result file at `docs/orchestration/review-feedback/results/documents.md` listing
  what changed in each section and every fact you could not confirm.
- **Stop condition (REQUIRED):** every instruction below is met; every figure and path in
  the two files was checked against the repository or a result file; no link is broken;
  the terms audit at the end is clean.
- **Budget (REQUIRED):** 90 minutes; no cloud spend.
- **Where this fits:** the owner is part-way through reading the summary and gave
  feedback on the parts read. A fresh reviewer will check your files before the owner
  sees them.
- **Inputs:** [standing-rules.md](standing-rules.md) first. Then
  [the feedback notes](../../../handoffs/2026-11-20-session-summary-feedback.md), which
  hold the owner's feedback in full; [the ledger of this run](../progress.md); the result
  and review files of this run named in the dispatch line; the two guides
  (`slice/README.md`, `delivery/README.md`), `contracts/` and the top-level `CLAUDE.md`
  as they now stand.

You edit only the three documents named above and your result file.

## The owner's rule for these documents

The owner said: once a decision is made, the documents are rewritten to state the result.
The documents the owner reviews describe the state of affairs at the time of review. They
do not carry a list of decisions with their answers, and they do not narrate how a
decision was reached. So nowhere write "the owner decided D4" or "formerly"; write what
is now true, in the section where it belongs.

## The owner must not lose their place

The owner has read the terms, section 2.1, section 3 and section 4.1 of the summary, and
has **not** yet read sections 2.2 to 2.5, 4.2 to 4.4, 5, 6 and 7.

- Keep the summary's section numbers and headings, and keep every identifier that
  survives: R1 to R18, M1 to M16, F1 to F5, P1 and P2. Never renumber. An identifier
  whose item is gone is simply absent.
- In the sections not yet read, change only: the terms; facts that are no longer true
  (paths, the repository being on GitHub, items now fixed, commands removed); and what
  follows directly from the decisions (listed below). Do not polish, reorder or shorten
  them otherwise.
- At the very top of the summary, under the title, put a short block headed "What changed
  in this revision" (at most eight lines) that says which sections changed and why, and
  that the block is to be removed when the owner's review ends. Give the time of the
  revision, read from the clock with `TZ=America/Los_Angeles date`.

## What the decisions change

Read the feedback notes for the owner's words. In outline:

- **Terms table:** "instance" replaces "copy" (row "part, instance, plate"); "plate
  configuration" replaces "plate job"; "HTTP interface" replaces "HTTP face";
  "PenguinSlicer" replaces "Penguin Slicer"; the row for Auto-orient and Arrange is
  removed (the mockup section may still name the two buttons). Define "slice job" so its
  difference from "plate configuration" is plain: the plate configuration is the
  description, the slice job is the work on it. Remove terms no longer used.
- **Section 2.1** keeps its heading and says that no decision is open, in one or two
  sentences. Each former decision's result is written where it belongs:
  - The repository is `6238/PenguinSlicer` on GitHub, public; every change reaches
    `main` through a pull request (sections 1, 3.2, 6).
  - The timed rule after a start command stays as built; the session at the real printer
    measures what the H2S does (sections 2.4 and 4.2). Cut the long comparison of the
    timed rule and the safer rule down to what a reader needs to understand P1 and P2.
    Rulings R16 and R18 are reworded to match, keeping their numbers.
  - The small open items are fixed (sections 4.1 and 4.2 state what is open now, from
    the latest review files of this run).
  - Orca's reason for a failed slice is read from its debug log, and the upgrade check
    verifies that reading; there is no patch to Orca (section 4.1; ruling R4).
  - The slice service stays on Orca 2.4.2; taking 2.5.x is known future work (sections
    4.1 and 7, and the plan).
  - Daemon telemetry is part of the initial work on printer delivery, not yet designed or
    built. State why it matters in the owner's terms: the daemon runs on many kinds of
    hardware, and the problems are hard to foresee (network misconfiguration, hardware
    capabilities, the host sleeping or overloaded, timeouts on a slow host). The protocol
    is designed to be ported when the daemon moves to Rust or Go (section 4.2, section 7,
    and the plan).
  - Specs, plans, research, the mockup and build records live in the repository's
    `docs/` (section 6).
  - The reference plates are the five of ruling R17 plus a plate of 100 instances of a
    small hex shaft spacer; the instance limit is what the slice builder set, with its
    measured figures (section 4.1).
  - The printer's certificate is not checked, by the owner's choice; it is no longer an
    open matter (sections 2.4 and 4.2).
  - The Raspberry Pi installer is removed (sections 4.2 and 5).
- **One interface.** The HTTP interface is the slice service's one interface; the `slice`
  command is gone; one interface per component is the default, not a hard rule. This
  rewrites "Run it" and "What it does" in section 4.1, ruling R3 (a cancel always
  discards the file) and ruling R13.
- **Section 4.1** is rewritten to the slice service's current state: what it does, how to
  run it, figures from this run's last review of the slice service, and what is open now.
- **Section 4.2** is updated the same way from this run's last review of printer
  delivery; its structure stays, since the owner has not read it.
- **Section 2.4:** the daemon's code now comes from GitHub (clone, then install); remove
  the certificate line and anything about the Raspberry Pi installer; keep everything
  else, including the part that says what the steps do not cover.
- **Section 6** gives the current locations, including this run's records.
- **Section 7** lists the ways forward as they now stand, riskiest first, with what makes
  each risky (feasibility, or the resources it needs). Remove what is done. Give no time
  estimates and no priorities.

## The plan

Rewrite the plan to the current state under the same rule: it says where the project is
and what is planned, not how it got there. It gains daemon telemetry as part of the
initial work on printer delivery, a short "known future work" section (Orca 2.5.x first
among it), the reference plates, the one-interface default, and the pull-request process.
It uses the new terms. It gives no time estimates and no priorities; where it orders
work, the order is by risk, riskiest first, with the reason.

## Before you finish

- Audit both files for terms: each term defined once, used with exactly that meaning, no
  synonym for variety, no one word for two things. In particular "record" must not mean
  three things, and "main state" must be defined or replaced.
- Run `python3 /tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/check_links.py /repos/popcornpenguins/penguin-slicer/docs`
  and fix every broken link in your three files.
- Diagrams are Mermaid fenced blocks, `flowchart TB`, short node text, no themes.
