# Review 1 of the plan by phase

Written Tue 2026-11-24 23:04 PT by a reviewer who did not write the change, following
[the review brief](review-brief.md). It reviews `git diff 3bc0998..HEAD` on the branch
`docs/plan-by-phase`: [the plan](../../plans/penguin-slicer-plan.md), the "Where it
stands" sections of [the slice service's guide](../../../slice/README.md) and
[printer delivery's guide](../../../delivery/README.md), the change of words, and the two
deleted documents. Nothing was fixed; this file only reports.

## Short answer

- **No serious finding, 7 medium, 15 low, 3 of taste.**
- The plan is accurate about what is built: every statement about the code that was checked
  against `slice/`, `delivery/` and `contracts/` holds, apart from the low findings below.
  It adds no phase or mechanism the owner did not ask for, and it invents no decision.
- The medium findings are of two kinds. Three are things lost or un-decided on the way
  from the deleted documents (M1, M5, M7). Four are about security and the pieces the
  phases need that no component owns (M2, M3, M4, M6).
- No secret is committed. Both Mermaid diagrams the change wrote or touched render. No
  link outside `docs/orchestration/` points to a deleted file inside the repository; one
  pointer outside the repository does (M7).

Severity as used here: **serious** would make the owner decide on a false statement, or
states something insecure as the way to do it; **medium** misleads or leaves out something
a later phase depends on until someone notices; **low** is a small inaccuracy or a breach of
a document rule; **taste** is marked as such.

## Medium

### M1. The rulings made on the owner's behalf are no longer asked about anywhere

- **Where:** the deleted session summary, section 2.2 ("Rulings made on your behalf:
  confirm or reverse each", R1 to R18); nothing in
  [the plan](../../plans/penguin-slicer-plan.md) or the two guides replaces it
  (outside `docs/orchestration/` and `docs/handoffs/`, `git grep -i ruling` finds the word
  only in comments of two of printer delivery's test files).
- **What is wrong:** section 2.2 listed eighteen choices the coordinator made where the
  owner had not decided, and asked the owner to confirm or reverse each. The owner never
  read that section (the summary's own header lists 2.2 among the sections not read, and
  [the writer's brief](brief.md) says the owner reviewed only 2.1, 3 and 4.1). The owner
  has since answered some in other words: R4 (no patch to Orca), R13 (one interface), R15
  (no "local mode"; file upload instead), R16 (the timed rule stays until the H2S is
  measured), R17 (the reference plates). The others are now described in the guides as
  plain facts of the design, with no sign that the owner has not ruled on them:
  R2 (a slice whose memory passed the memory ceiling may still be delivered), R3 (a cancel
  discards even a finished sliced file), R5 and R6 (what ends a delivery job, and that the
  printer's main state decides), R7 and R11 (outcome unknown, and both 24-hour limits),
  R8 (a printer whose last print ended is free), R9 and R10 (the start on a whole, fresh
  picture, and the hold), R12 (a relay restart resumes no delivery job), R18 (an end
  counts only as this print's end).
- **Why it matters:** the plan is what the owner reads instead of the rest of the session
  summary. With the summary deleted, the request to confirm or reverse is gone, and the
  plan reads as if every design choice in the guides were the owner's. The brief's first
  check is that open questions are marked open. The writer dropped the list on purpose
  ([result.md](result.md), the row for section 2.2: "None kept as a list, by the owner's
  rule"). That rule is about decisions the owner has made; these are choices the owner has
  not yet been asked about.
- **Smallest fix:** one short paragraph under "Where things stand" saying that these
  choices in the two guides were made by the coordinator during the unattended builds and
  the owner has not confirmed them, naming each in a clause with a link to the guide
  section that states it. That is an open list, which the owner's rule on decision lists
  allows while it is open; each clause is dropped when the owner answers.

### M2. Phase 3 does not name the security questions of a page on the open internet

- **Where:** [the plan](../../plans/penguin-slicer-plan.md), lines 282 to 299 (the
  questions the design session must answer).
- **What is wrong:** the list has one security question ("Who may use a page reached from
  the open internet, and how they sign in") and the single word "Cost". It leaves out
  what the review brief names, and each has a fact in the code behind it:
  1. **Who may call the slice service itself.** Its HTTP interface has no sign-in of any
     kind (`slice/src/penguin_slice/web.py`); today it is private only because `serve`
     listens on 127.0.0.1 by default (`__main__.py`, `--host`). The question is whether the
     slice service is reachable from the internet at all, or only from whatever serves
     the wizard.
  2. **Whose slice job it is.** A sliced file and its summary are fetched with the slice
     job's id alone. The need "coming back" (line 256) and any sign-in both require
     something to know which user a slice job belongs to, and the slice service knows
     nothing of users.
  3. **Abuse and cost limits.** One request may upload 188.5 MB and hold the one Orca for
     up to 240 s at up to about 2,500 MB; the queue is two more, with no limit per client,
     so one client can keep everyone else at `slice.busy`; each finished slice job keeps
     its uploads for an hour. "Cost" does not say this.
  4. **Uploaded files as hostile input.** The slice service's own STL reader is hardened
     and fuzzed, but the same bytes then go to Orca, which runs with an allowlisted
     environment and its own home folder and otherwise with the slice service's rights,
     beside other users' uploads and sliced files in the same work folder, and on a
     hosted machine usually within reach of that machine's own credentials. What confines
     Orca is a design question.
  5. **Secrets.** Where the configuration lives (it holds the pairing code), the hosting
     credentials, and that none reaches the repository, a log line or the page.
  6. **What the log lines hold about users** once they leave the machine (part names and
     the names of uploaded files are in the slice service's log lines).
- **Why it matters:** the plan's stated job for this phase is to name what the design must
  settle. A question left off the list is the one a design session skips.
- **Smallest fix:** add those six as questions under line 293, each one line, answered
  nowhere.

### M3. Phase 5 names no security question for the relay, the daemon or daemon telemetry

- **Where:** [the plan](../../plans/penguin-slicer-plan.md), lines 325 to 363.
- **What is wrong:** phase 5 puts a relay where a daemon on another network reaches it and
  adds a new channel (daemon telemetry) from a computer nobody controls. Its risks are all
  about the H2S's behaviour. Missing, as questions for the phase's spec:
  1. Who may send to the printer: the caller's sign-in is the only thing between the
     internet and a print on the H2S, and the caller must refuse a sliced file that is not
     the request's own (printer delivery's guide, "The caller's duty").
  2. The pairing code as a secret: where it is kept, who can read it, how it is replaced.
  3. The relay's secret key, which signs the daemon's token: where it lives on the host.
  4. What the daemon stores on the daemon's computer (the printer's access code and the
     token, with no protection by the operating system: the guide, "Running the daemon").
  5. Daemon telemetry: what proves a message comes from a paired daemon, what a message
     may never hold (the access code, the pairing code, the token), its size and rate
     limits, how long it is kept and who reads it.
  6. Showing "who sent it" (a user's Onshape name) to everyone who uses the same printer.
  The printer's certificate is not such a question: the owner decided it (the guide says
  the daemon accepts any), and the plan could say so in a clause.
- **Why it matters:** the same as M2; and daemon telemetry "gets its own design" with no
  hint that the design has a security half.
- **Smallest fix:** a "Security" bullet in phase 5 listing those six as open.

### M4. The relay for the session at the real printer: the text points at a relay that listens on 127.0.0.1 only and signs everyone in

- **Where:** [printer delivery's guide](../../../delivery/README.md), lines 1190 to 1201
  (new in this change, carried over from the session summary); the plan, lines 341 to 342
  and 362.
- **What is wrong:** the guide says "a relay must be started somewhere the daemon can
  reach (`uv run python -m together.relay_server`, as in Try it on one machine) and its
  address given to `pair`". `together/relay_server.py` binds `127.0.0.1` and has no option
  to bind anything else (line 55), runs in development mode over plain HTTP, and signs
  every request in with the pairing code (lines 29 to 39; its own docstring says "Never
  use it for a real shop"). So the daemon can reach it only when it runs on the daemon's
  computer itself, which the text does not say and which means installing `uv` and the
  relay on a Windows computer where nothing here has run. Read as written ("somewhere the
  daemon can reach"), the natural next step is to make it listen on a network address,
  and then anyone who can reach that address can start a print on the real H2S.
- **Why it matters:** it is wrong about what the command can do, and the obvious way round
  is unsafe on the one occasion a real printer is attached.
- **Smallest fix:** in the guide, say that this relay listens on 127.0.0.1 only and so
  runs on the daemon's computer for the session, that it must not be given a network
  address, and that a relay on another machine needs a real caller with a sign-in (not
  built). In the plan's phase 5 risks, replace "a relay the daemon can reach" with the
  same fact.

### M5. Where the configuration is kept is declared open, and the standing answer and its rule are dropped

- **Where:** [the plan](../../plans/penguin-slicer-plan.md), line 36 (the term
  **configuration**: "Where it is kept is open in every phase").
- **What is wrong:** the deleted restart plan defined "team configuration" as "the
  settings file each team keeps in its Onshape account, which PenguinCAM reads at
  sign-in". Dropping the word "team" follows the owner's rule; dropping where it lives
  un-decides something. The code still assumes that file: the daemon's `pair` command
  prints "for a team configuration file, these two lines"
  (`delivery/daemon/penguin_delivery_daemon/__main__.py`, lines 222 to 223). The owner's
  rule for PenguinCAM, in the agent's memory note `project-penguincam-secrets-rule.md`
  (dated 2026-09-13), was that such secrets (the pairing code is one) live only in that
  file in Onshape and are never stored on the server.
  Whether that rule carries over to PenguinSlicer outside Onshape (phases 2 and 3) is a
  fair open question; "open in every phase", phase 4 inside Onshape included, is more than
  the owner has said. Also, "everyone who uses one PenguinSlicer" does not say what one
  PenguinSlicer is (an installation, an Onshape company, the users of one pairing code),
  which is the question of whose configuration it is.
- **Why it matters:** the pairing code is the secret that decides who may print on a
  printer, and phase 3 puts the product on the open internet. A reader of the plan cannot
  tell that a rule about where such secrets may live already exists.
- **Smallest fix:** in the term's row, say that the first attempt kept it in a file in the
  Onshape account, read at sign-in; that the owner's rule there was that its secrets are
  never stored on the server; and that where it is kept outside Onshape, and whose it is,
  are open. I could not confirm that the owner means the PenguinCAM rule to bind
  PenguinSlicer: state it as the earlier rule, not as a decision.

### M6. The application that serves the wizard and is the relay's caller exists nowhere and belongs to no phase

- **Where:** [the plan](../../plans/penguin-slicer-plan.md), lines 56 (the term
  **caller**), 107 to 108 ("the wizard stands for the application around it"), 259 to 261,
  284 and 335 ("the application that is the relay's caller").
- **What is wrong:** from phase 2 on, something must serve the wizard's page and stand
  between it and the slice service; by phase 3 it signs users in and holds the
  configuration; by phase 5 it is the relay's caller, holds the sliced file between the
  slice and the send, and passes the user's name. It is none of the four components, no
  line of it exists (printer delivery has only the stand-in of
  `together/relay_server.py`), the plan gives it three different descriptions and no
  name, and no phase lists building it or its risks. "Joining the components, and
  returning to PenguinCAM" is under known future work, outside the phases, yet phases 2,
  3 and 5 each need part of exactly that. The session summary's risk for it ("no two
  components have yet run joined ... a mismatch between them would show first here") is
  not in the plan.
- **Why it matters:** it is where every security answer of M2 and M3 will land, and it is
  work the plan's count of components hides.
- **Smallest fix:** one sentence in "The repository" saying this application does not
  exist, is not one of the four components and has no design; add it to the components of
  phases 2, 3 and 5 as "to be settled by the phase's spec"; add the summary's risk to
  phase 2 (the first time two components run joined).

### M7. Outside the repository, the workspace notes still send agents to the deleted plan

- **Where:** `/repos/popcornpenguins/CLAUDE.md`, line 105 ("The plan is
  `penguin-slicer/docs/plans/2026-11-19-penguin-slicer-restart-plan.md`. Start from the
  plan."), and the memory file
  `/home/agent/.claude/projects/-repos-popcornpenguins/memory/penguin-slicer-restart.md`,
  lines 46 to 47.
- **What is wrong:** both name the two files this change deletes. Neither is in the
  repository, so the brief's link check passes and the writer was right not to touch
  them (the writer reports the same in [result.md](result.md), "For the owner"), but
  every new session in the workspace is told to start from a file that will not exist
  once this branch merges.
- **Smallest fix:** for the orchestrator, when the branch merges: point both at
  `penguin-slicer/docs/plans/penguin-slicer-plan.md`.

## Low

Each is one or two sentences to change.

| # | Where | What is wrong | Smallest fix |
|---|---|---|---|
| L1 | Plan, line 189 | "pull request 12 (Sat 2026-11-21)": the merge was at 2026-11-21 06:29 UTC, which is Fri 2026-11-20 22:29 PT. The plan says its times are Pacific. | "Fri 2026-11-20". |
| L2 | Plan, line 15 | "the slice service (complete for one machine)" beside six things phase 2 still needs from it (lines 244 to 261). | "built and tested for one slice service process". |
| L3 | Plan, lines 253 to 255 | "the heaviest real plate measured has about a million lines of G-code (an 8.8 MB sliced file)". That is the heaviest of the Popcorn Penguins' target plates. Heavier real plates were measured: twelve Bottom Inners give a 10.8 MB sliced file under the memory ceiling, and 14.1 MB with supports on at a 3,000 MB ceiling ([the slice service's guide](../../../slice/README.md), lines 429 to 430); their lines were not counted. | "the heaviest target plate"; add the 10.8 MB plate. |
| L4 | Plan, line 285 | "A slice peaks at 1 to 2 GB". The measured single parts peak at 97 to 218 MB and the target plates at 863 to 1,415 MB; only a full plate of the large parts nears or passes the 2,000 MB memory ceiling. | "A full plate can reach the memory ceiling; the target plates peak at 0.9 GB, and 1.4 GB with supports on". |
| L5 | Plan, lines 352 to 355; printer delivery's guide, lines 53 to 56 | "none is provided today" / "does not give today". [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) (lines 165 to 170) says two of the three are provided in part: `delivery` in `GET /printer/status` is the pairing code's most recent delivery job, and `last_result.age_seconds` gives the last print's end for ten minutes. | "not provided, or only in part". |
| L6 | Plan, lines 333 to 334 | "the simulated printer replaced by recordings". The simulated printer stays; its invented status sequences are replaced by recordings. | "the simulated printer's invented sequences replaced by recordings". |
| L7 | Plan, lines 328 to 332 | Daemon telemetry "is part of this phase", yet "Done when" does not mention it, so the phase can be done without it. | Add it to "Done when", or say its own spec defines its done. |
| L8 | Plan, lines 211 to 212 | "the one step not reviewed in the round of Tue 2026-11-24". The feedback notes say only that the Layout step was not reviewed; they record nothing on the Send step either, so "the one" is more than the record shows. | "which was not reviewed in the round of". |
| L9 | Plan, line 64 | "320 px, the width of Onshape's right panel". The wizard research calls 320 px a guess and [the visual reference](../../reference/penguincam-in-onshape/README.md) shows the panel far wider. | "320 px, the narrowest width it must work at". |
| L10 | Plan, line 289 | The link "Sizing the host" goes to the top of a 1,008-line guide. | Link `../../slice/README.md#plate-limits`, as the guide itself does. |
| L11 | Printer delivery's guide, lines 948 to 949 | "a team number and a user name passed through to the log and events". Only the team number reaches the log (`team=`); the user name goes to events only (`caller.py`, line 38; `routes.py`, line 386). | "a team number, passed through to the log and events, and a user name, passed through to events". |
| L12 | The slice service's guide, lines 38 to 39 | "Every measurement is from one aarch64 Linux machine". The memory model's fit also takes nine plates "measured on another aarch64 machine" (line 708). | "from aarch64 Linux machines with 4 CPUs". |
| L13 | Plan, line 371; both guides' "Where it stands" | The words still to change are listed as error and progress reports and the `Team` type. Also there: what the daemon's `pair` command prints ("your team's print server", "a team configuration file") and the log field `team=`. No progress report sentence with an old word was found in either component. | Name the daemon's printed text and the log field; drop "progress reports" unless one is found. |
| L14 | One name per thing, across the plan and the guides | (a) "spec": the wizard's spec is `wizard/README.md`, which the terms call its guide, and each phase also "starts with a design spec"; lines 223 to 225 and 244 leave unclear whether phase 2's spec is that file or another. (b) "the session at the real printer" (plan), "the session at the H2S", "a hardware session", "the first session" (printer delivery's guide). (c) "a person" in the done sentences of phases 2 and 3, "a user" in phases 4 and 5. (d) "sliced result" beside "sliced file". (e) "profile catalog", "advanced mode" and "printer-status icon" are used and not in the terms table. (f) [docs/reference/orca-lay-on-face/README.md](../../reference/orca-lay-on-face/README.md), line 14, still says "student" (outside the writer's list, inside the owner's rule). | Pick one name for each; add the three terms; change the one word. |
| L15 | The slice service's guide, "What happened when the command was run to other versions and back" and the memory model's table; [result.md](result.md), the row for section 5 | The session summary's section 5 said which claims no independent review had checked. The Windows checklist kept that caveat. Two lost it: the upgrade commands were run by the builders only (the reviewers read them and did not run them), and the memory figures of the eight synthetic plates are the builder's. The result file says the unchecked claims "are kept in the delivery guide", which is true of one of the three. | A clause in each of the two places in the slice service's guide. |

## Taste

- **T1.** Plan, line 132 with lines 147 to 150: "Words" sits under "A component is not
  done until each is shown by a test", so it now asks for a test that no sentence says the
  old words, and makes both built components "not done" on paper. The owner asked for the
  words, not for a test. A clause exempting it, or moving "Words" out of the tested list,
  would say what was meant.
- **T2.** Plan, lines 330 to 332: phase 5 is done only when "every line of the hardware
  checklist" is answered (23 lines, among them unplugging the network and switching the
  printer off mid-print). The deleted plan said "One confirmation on the real H2S closes
  this work". The stricter sentence is defensible, since the recordings answer most lines,
  but it is the writer's bar, not the owner's.
- **T3.** [README.md](../../../README.md), lines 3 to 4, still opens "3D printing for FRC
  shops ... the shop's printer", which sits oddly beside "used by people who are not FRC
  teams". "Shop" is not one of the three words, so this is the owner's call.

## The writer's result file, checked after the findings above were written

[result.md](result.md) was read only after the sections above existed. Its claims:

| Claim | Checked | Holds |
|---|---|---|
| No broken relative link or anchor outside `docs/orchestration/` | My own run of a link check over every Markdown file, and the anchors by hand | Yes |
| Both diagrams render | Rendered again, independently | Yes |
| `README.md` had none of the three words | `git grep` | Yes (T3 is the writer's choice 8) |
| The memory ceiling (2,000 MB) and the host sizing (3.5 GB) corrected from the guide | `limits.py`; the guide's "Sizing the host" | Yes |
| The code facts of choice 6 (no cross-origin header, `MAX_RUNNING` 1, `MAX_QUEUED` 2, four overrides, the daemon's default relay address) | The code | Yes |
| "The tests that read the guides and contracts parse the error-code tables, the printer-values table and contract field rows, none of which I changed" | The diff | **No, but harmless.** The change did edit rows of those tables: the `message`, `detail`, `stage_label` and `part_warnings` rows of three contracts, and the `delivery.not_paired` and `delivery.job_unknown` rows of printer delivery's error table. Only the prose cells changed, and both fast suites are reported passing on this branch (slice 972, delivery 1,123). |
| Rulings R1 to R18 dropped as a list "by the owner's rule" | See M1 | The fact holds; the reason does not cover choices the owner has not seen |
| Section 5's unchecked claims "are kept in the delivery guide" | See L15 | One of three |
| Every risk of section 7 is in its phase or in known future work | The plan | All but one: "no two components have yet run joined" (see M6) |
| The workspace notes still name the deleted plan | The two files | Yes (M7) |

Not listed in the result file as dropped, and dropped: the last review round's figure for
the first of the two limits that wait for the real printer (109 of 4,300 random sequences
ended with a wrong final answer on a simulated printer that kept the previous end under
the new name; none sent a start command twice). It is history of a review round, and the
guide states the limit itself, so this is a note, not a finding.

## What was checked, and how

- **Read in full:** the plan; both guides; `README.md`; `CLAUDE.md`; the four contract
  files' changed lines and `contracts/plate-configuration.md` to line 105; both research
  files; the feedback notes; both deleted documents (from `git show 3bc0998:`); the
  writer's brief, the standing rules and the brief for mockup version 6 (in the diff, not
  part of the writer's change).
- **Against the code:** the memory ceiling's default (2,000 MB), `MAX_RUNNING` 1,
  `MAX_QUEUED` 2, `RECORD_TTL_S` an hour, `MAX_INSTANCES` 150, `MAX_PARTS` 25 (`limits.py`,
  `jobs.py`); no cross-origin header and no sign-in in `web.py`; `serve` on 127.0.0.1 by
  default; slice job ids from `secrets.token_hex(8)`; the profile catalog accepted for any
  printer in it (`print_config.py`); STL files in millimetres and the four overrides
  (`contracts/plate-configuration.md`); the three platforms of `install-orca.sh` and the
  pin at 2.4.2; `make coverage` failing under 100%; the real-Orca suite's plates
  (`tests_orca/test_frc_parts.py`, `test_orca.py`); the reference plates of
  `scripts/measure_plate.py`; the `Team` type and what the relay does with its fields;
  `together/relay_server.py`; the old words still in both components' sentences.
- **Against git:** the merge time of pull request 12; that printer delivery's code last
  changed in pull request 5; that the change touches no code, test or contract example.
- **Links:** every relative link in every Markdown file checked for its target file
  (twelve broken, all under `docs/orchestration/`, which the brief allows); every anchor
  in the plan and in the two "Where it stands" sections checked against the headings. The
  three links to the notes repository were checked against the local checkout of that
  repository, not fetched from GitHub.
- **Mermaid:** the plan's flowchart and the sequence diagram the change edited in printer
  delivery's guide were rendered in Chrome with the viewer's Mermaid, dark theme, strict:
  two `svg` elements, no syntax error, the page's `scrollWidth` equal to its
  `clientWidth`, the diagrams 429 and 736 px wide.
- **The owner's rules:** no time estimate and no priority found; times are Pacific with
  weekday and date except L1; cross-references are real links; no decision list; no
  ASCII art. "student", "mentor" and "team" remain only where the brief allows (code
  names, the components' own messages, FRC Team 6238) and at L14 (f).
- **Not done:** the fast suites were not run again (the change is documents only, and both
  were reported passing on this branch); no real Orca was run; nothing was tried in a real
  Onshape panel or on a printer.

One side effect to report: the browser command used for the Mermaid check wrote two
snapshot files into `/repos/popcornpenguins/penguin-slicer/.playwright-cli/` (a folder
git ignores), because the session's working directory is that checkout. Both were removed
by their literal names; nothing else there was touched.
