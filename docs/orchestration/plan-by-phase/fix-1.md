# Fix round 1 of the plan by phase

Written Wed 2026-11-25, Pacific time, following [the fix brief](fix-1-brief.md), for the
findings of [review 1](review-1.md). The plan is [penguin-slicer-plan.md](../../plans/penguin-slicer-plan.md).

## Medium

- **M1.** No list added to any document, as the brief rules. The rulings the owner has not
  read are listed below for the orchestrator.
- **M2.** Six questions added to phase 3's list of open questions, one line each, none
  answered: who may call the slice service, whose slice job it is, abuse and cost limits,
  uploaded files as hostile input, secrets, what the log lines hold about users.
- **M3.** A list of six open security questions added to phase 5 (who may send, the
  pairing code, the relay's secret key, what the daemon stores, daemon telemetry, showing
  who sent a print), with a clause that the printer's certificate is not one ("by design",
  as the guide says; I did not call it the owner's decision, which I could not confirm).
- **M4.** [Printer delivery's guide](../../../delivery/README.md), "What the session needs
  beyond `record`", now says the local relay binds 127.0.0.1 and signs every request in,
  so it is for tests on one machine only, must never get a network address, and a relay
  reached from another machine waits for phase 5's design. Its "Where it stands" and the
  plan's phase 5 (the session at the H2S, and the risks) say the same.
- **M5.** The term **configuration** now says: inside Onshape (phase 4) a configuration
  file in the Onshape account, read at sign-in, with its secrets never stored on the
  server, as in PenguinCAM; outside Onshape, where it is kept and whose it is are open.
- **M6.** The wizard owns its server side. New term **the wizard's server side** (serves
  the pages and calls the slice service in phase 2, Onshape sign-in in phase 4, calls the
  relay as the caller in phase 5); the terms **wizard** and **caller**, "The repository",
  the note under the diagram, "Where things stand", and the components of phases 2 to 5
  say so; phase 2's risks add "the first time two components run joined". The future-work
  row became "Running the components inside one server, and returning to PenguinCAM".
  The delivery guide's definition of the caller names it too.
- **M7.** Left, as the brief rules.

## Low

- **L1.** "Sat 2026-11-21" changed to "Fri 2026-11-20".
- **L2.** "complete for one machine" changed to "built and tested for one slice service
  process".
- **L3.** "the heaviest target plate of the Popcorn Penguins", and the 10.8 MB plate of
  twelve Elevator Block Bottom Inners (14.1 MB with supports on) added.
- **L4.** "A slice peaks at 1 to 2 GB" replaced by the reviewer's sentence.
- **L5.** Plan and delivery guide: "not provided, or only in part".
- **L6.** "the simulated printer's invented sequences replaced by recordings".
- **L7.** Phase 5's "Done when" adds "daemon telemetry does what its own design says".
- **L8.** "which was not reviewed in the round of".
- **L9.** "from 320 px, the narrowest width it must work at".
- **L10.** The link now goes to `slice/README.md#plate-limits`.
- **L11.** The delivery guide now says the team number goes to the log and events, the user
  name to events only.
- **L12.** The slice guide now says the measurements are from aarch64 Linux machines,
  almost all from one with 4 CPUs and nine plates of the memory model's fit from another.
- **L13.** The plan's future-work row and the delivery guide name the daemon's `pair`
  text and the log field `team=`, and drop "progress reports".
- **L14.** (a) Phase 1 writes the wizard's **guide**, which is the wizard's part of phase
  2's design spec; "spec" elsewhere in the plan and the slice guide became "design spec".
  (b) "the session at the H2S" everywhere; the delivery guide's heading is now "Before
  trusting it at the H2S: what the session at the H2S must confirm", with every link to it
  updated. (c) "a user" in phases 2 and 3. (d) "sliced result" became "sliced file" in the
  plan and the slice guide. (e) **profile catalog**, **advanced mode** and
  **printer-status icon** added to the terms. (f) "student" became "user" in
  [the Lay on face reference](../../reference/orca-lay-on-face/README.md).
- **L15.** The slice guide now says the upgrade commands were run by the builders only and
  the eight plates' memory figures are the builder's, unmeasured by a review.
- **Found while fixing:** the plan's term **wizard** named a "Settings" step; the step is
  Setup ([DECISIONS.md](../../mockups/print-wizard/DECISIONS.md)). Corrected.
  Reverted by the orchestrator: the owner renamed step 2 "Settings" on Tue 2026-11-24,
  and mockup version 6 makes the change in `DECISIONS.md`.

## Taste

- **T1.** Fixed: "A component is not done until each, apart from Words, is shown by a
  test."
- **T2.** Left as written: phase 5's bar ("every line of the hardware checklist") is the
  writer's, stricter than the deleted plan's "one confirmation on the real H2S". The owner
  should choose.
- **T3.** Left: "shop" in [README.md](../../../README.md) is not one of the three words;
  the owner's call.

## Rulings the owner has not read (for the orchestrator)

Made by the coordinator in the session summary's section 2.2, which the owner never read,
and not since answered in other words (R4, R13, R15, R16 and R17 were). Each now stands in
a guide as a plain fact of the design:

- **R1** a memory watchdog stops Orca at the memory ceiling, instead of refusing plates on
  the memory estimate: [slice guide, Plate limits](../../../slice/README.md#plate-limits).
- **R2** a complete sliced file is delivered, with a note, even when a timeout or a
  watchdog stop landed as Orca finished: [slice guide, Plate limits](../../../slice/README.md#plate-limits).
- **R3** a cancel always discards the sliced file, even one Orca finished:
  [slice guide, Progress, cancellation and cleanup](../../../slice/README.md#progress-cancellation-and-cleanup).
- **R5** only evidence that the print ended ends a delivery job, and a paused printer is
  "waiting for a person": [delivery guide, States and stages](../../../delivery/README.md#states-and-stages).
- **R6** the printer's main state decides whether a print is going on, and an unknown one
  refuses a send: [delivery guide, What the printer's report means](../../../delivery/README.md#what-the-printers-report-means).
- **R7** "outcome unknown" after a stale delivery job, by the caller or after 24 hours:
  [delivery guide, States and stages](../../../delivery/README.md#states-and-stages).
- **R8** a printer whose last print ended is free for a new send:
  [delivery guide, How a start is decided](../../../delivery/README.md#how-a-start-is-decided).
- **R9** a start command only on a whole, fresh picture that shows the printer free:
  [delivery guide, How a start is decided](../../../delivery/README.md#how-a-start-is-decided).
- **R10** the daemon holds the printer after a start command, with guessed time limits:
  [delivery guide, How a start is decided](../../../delivery/README.md#how-a-start-is-decided) and [The settings](../../../delivery/README.md#the-settings).
- **R11** every final progress report kept 24 hours:
  [delivery guide, Restarts and cleanup](../../../delivery/README.md#restarts-and-cleanup).
- **R12** a relay restart keeps only its secret key and resumes no delivery job:
  [delivery guide, Restarts and cleanup](../../../delivery/README.md#restarts-and-cleanup).
- **R14** the simulated printer's sequences are invented from one status document:
  [delivery guide, The simulated printer](../../../delivery/README.md#the-simulated-printer).
- **R18** an end counts only as the end of this print:
  [delivery guide, How a start is decided](../../../delivery/README.md#how-a-start-is-decided).

The review named all of these except R1 and R14; I added those two because the feedback
notes answer neither.

## Checks

- Links: every relative link and anchor in every Markdown file outside
  `docs/orchestration/` checked by a script: none broken.
- Mermaid: no diagram changed.
- Fast suites on this branch: `make -C slice test` 972 passed; `make -C delivery test`
  1,123 passed.
