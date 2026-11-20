# Result: the session summary, the plan and the wizard research

Status: DONE_WITH_CONCERNS. Written Fri 11-20 about 11:55 PT by the document writer, for
[the brief](../briefs/documents.md) under [the standing rules](../briefs/standing-rules.md).
Written from the second review and fix rounds of both components, while the third review
rounds run. Files changed:
[the session summary](../../../handoffs/2026-11-20-penguin-slicer-session-summary.md),
[the plan](../../../plans/2026-11-19-penguin-slicer-restart-plan.md),
[the wizard research](../../../research/2026-11-19-wizard-layout-and-advanced-mode-research.md)
and this file. Nothing else.

## The session summary, by section

- **Title and top:** "PenguinSlicer"; a seven-line block "What changed in this revision"
  (Fri 11-20 11:50 PT, read from the clock), to be removed when the owner's review ends;
  the opening paragraph names the revision and the review-feedback run.
- **1. Short answer:** rewritten to the present state: the repository on GitHub, public,
  pull requests; the slice service's one interface, 150 instances, debug-log reading; P1
  and P2 the only open items of printer delivery; daemon telemetry part of the initial
  work; the branch `work/review-feedback`.
- **Terms:** copy to instance, plate job to plate configuration, HTTP face to HTTP
  interface, PenguinSlicer; Auto-orient and Arrange row removed; slice job defined as the
  work on a plate configuration; added slice service process, reference plates, daemon
  telemetry, start note, main state, recording, upstream check, first build,
  review-feedback run. "Ledger" now "running account", so "record" survives only as the
  daemon's `record` command (and the verb).
- **2.1:** two sentences, no decision open. The table and the paragraph of decisions made
  during the session are gone; each result is in its section (Python and Rust or Go,
  no installer: 4.2; advanced mode in the panel: already in 2.3; global instructions: 6).
- **2.2:** terms in R1, R2, R7 (no "record"), R11, R15; R3 (a cancel always discards),
  R4 (no patch to Orca, the upstream check verifies the debug-log reading), R13 (the HTTP
  interface is the one interface; one interface per component is the default), R15
  (exercised through each interface), R16 (the timed rule stays; the session at the real
  printer measures), R17 (lists the five plates itself, since D8 is gone), R18 (last
  sentence about the safer rule removed).
- **2.3:** new viewer address and `open` path; copy to instance throughout; one sentence
  on Onshape's word "Instances" in the Assembly (the ledger's note); one sentence that the
  mockup clamps at 100 instances where the slice service takes 150.
- **2.4:** step 2 clones from GitHub, then `py -m pip install .\delivery\daemon`; tarball
  and "no remote" removed; "settles decision D2" now "measures what P1 and P2 depend on";
  certificate line removed; the guide's new checklist line on the H2S's answer to a
  delete added (the list is "copied from the guide"); `uv run` added to the relay command
  as the guide has it. The part on what the steps do not cover is kept.
- **2.5:** F5 "instances".
- **3:** terms (3.2 diagram label, 3.3 and 3.5 "copied" to "brought over" and "taken
  over"); 3.1's last sentence says the plan is kept to the present state; 3.2 names the
  GitHub repository and the pull-request rule. **3.6 is new:** the review-feedback run,
  with pull request times from GitHub and a table of its four review rounds.
- **4.1:** rewritten: what it does, how to run it (`serve` and the guide's `curl` lines),
  the reference plates and plate limits with the builder's spacer figures, the second
  review round's figures, the second fix round's figures marked "measured by the
  builder", the debug-log reading, the older memory figures kept as the builder's, and
  what is open now: S7 and S9 only (S9 states as a fact that the needle's reason is lost
  inside Orca and only a patch would surface it).
- **4.2:** structure kept. "What it does" gains the Python and Rust or Go fact, no
  installer, the certificate; "Run it" gains `test-properties`; new paragraphs "The timed
  rule after a start command" (the long comparison cut to what P1 and P2 need, keeping
  the 109 of 4,300 figure) and "Daemon telemetry" (why it matters, in the owner's terms);
  "Outcome of the last round" describes this run's fixes without the gone identifiers;
  figures from delivery review 2, then fix 2's marked "measured by the builder"; the
  paragraph on why the fast suite got slower removed (no longer true); open table P1 and
  P2 only, with the fixes pointing at section 2.4.
- **5:** P3 reference reworded; the Raspberry Pi installer line removed; "memory
  measurements of section 4.1" narrowed to the eight synthetic plates.
- **6:** rewritten: GitHub, `main` with pull requests 1 to 3, the branch
  `work/review-feedback`, this run's ledger, briefs and latest result files, the first
  build's files, the mockup's viewer address, the guides as real links; the notes
  repository no longer holds PenguinSlicer's documents.
- **7:** done items removed (the GitHub repository, the small open items); daemon
  telemetry moved up with its feasibility and resource risks; Orca 2.5.x as S7; moving the
  daemon to Rust or Go added; hosting mentions the 280 MB and one slice service process.

## The plan

Rewritten to the present state, no narrative of how decisions were reached, no open
decisions section. Gains: the terms of the run (plus plate 3MF, memory watchdog, upstream
check, ledger); section 4's `docs/` row, the one-interface default and "How changes reach
`main`"; 5.6 states there is no patch; a new 5.7 Tests (the quality bar); section 6 the
slice service's state and the reference plates; section 7 split into state, the session at
the real printer and daemon telemetry (part of the initial work, own design first);
section 9 the remaining initial work by risk with reasons; section 10 known future work,
Orca 2.5.x first. No time estimates or priorities. Removed terms no longer used: local
mode, validation run, printer stand-in, plate triangle cap, plate file.

## The wizard research

Every "copy" meaning a placement is "instance" (terms table, short answer, sections B to
D, "Zoom to instances"); one definition sentence added under the terms line. Kept:
"Porting either copies GPL or AGPL code" (duplicating code). "not copied" (imitating
Orca's Ctrl+D) became "not imitated".

## Checks

- Links: `check_links.py` on `docs/` reports one broken link, in
  `orchestration/penguin-slicer/results/slice-hardening-review-4.md` (an old record, not
  mine, pointing at the removed `slice/patches/orca/README.md`). My three files: none.
- Terms audit of the summary and the plan: no "copy" for a placement, no "plate job",
  "HTTP face", "Penguin Slicer", "D1" to "D11", "formerly" or "safer rule"; "instance"
  only for a placement; "record" only as the `record` command and as a verb; "main state"
  defined; "job" alone only in "a long job" of the progress report's definition.
- The two Mermaid diagrams changed one edge label each ("plate configuration"); not
  rendered here.

## Facts I could not confirm, and concerns

- **Figures not yet from a review:** everything after the second fix rounds (919 slice
  tests, a cancel during the plate write in 0.05 to 0.17 s, about 200 MB for the largest
  plate, the delete's log lines, 1,119 delivery tests) is marked "measured by the
  builder". The coordinator updates them after the third reviews.
- **The ledger's times disagree with GitHub and the builders.** GitHub gives pull
  request 2 merged at 09:31 PT (ledger: 09:15) and pull request 3 at 09:44 PT; the slice
  builder says it worked from 09:05 PT and the delivery builder from 09:00 PT, while the
  ledger has the builders dispatched at 09:32. Section 3.6 uses GitHub's times and "from
  about 09:00 PT" for the builders.
- **The workspace `/repos/popcornpenguins/CLAUDE.md` is stale:** it names the plan and the
  first build's ledger at their old `PenguinCAM-notes/` paths and says the repository is
  local only. Section 6 says so as a fact; the coordinator may want to fix that file
  instead.
- **The printer delivery guide still says P1 and P2 are "left as they are until the owner
  decides"** and keeps the long "alternative" paragraph naming it "the owner's choice"
  (`delivery/README.md`, "Two limits that wait for the real printer"). Not my file.
- **The 100 mm cube:** ruling R1 and section 4.1 keep 276 MB (the hardening's figure); the
  slice guide's memory model now says 269 MB. Left as it was in the unread section 2.2.
- **The mockup clamps quantities at 100 instances; the slice service's `MAX_INSTANCES` is
  150.** Stated in section 2.3 as a fact; the mockup was not changed.
- **Not verified by me:** that `git clone` and `pip install .\delivery\daemon` work on
  Windows (nobody has done it, the summary says so); that `main` on GitHub has the
  daemon as section 2.4 describes before `work/review-feedback` is merged (the installer
  is still on `main` until then).
- Orca's reason for the thin, tall needle is not in its debug log, as the coordinator
  ruled; section 4.1 (S9) and the plan state it as a fact for the owner.
