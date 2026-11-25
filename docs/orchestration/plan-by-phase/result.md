# Result: the plan by phase

Written Tue 2026-11-24, about 23:00 PT. Status: DONE_WITH_CONCERNS (see "For the owner").

## What was done

- **New plan:** [docs/plans/penguin-slicer-plan.md](../../plans/penguin-slicer-plan.md):
  short answer, one current terms table, the repository (`contracts/` and the four
  components, a sentence each with a link), the standing requirements, where things stand,
  the five phases in the owner's order (each with what "done" means, the components it
  touches and its risks; phase 3 lists the hosting questions and answers none), and known
  future work. One Mermaid diagram.
- **"Where it stands"** added near the top of [slice/README.md](../../../slice/README.md)
  and [delivery/README.md](../../../delivery/README.md).
- **Words:** "student", "mentor" and "team" (where it meant the users) replaced in the
  plan, both guides, [CLAUDE.md](../../../CLAUDE.md), `contracts/*.md` prose and
  `docs/research/*.md`. [README.md](../../../README.md) had none; it and
  [CLAUDE.md](../../../CLAUDE.md) now point at the plan.
- **Deleted** with `git rm`: `docs/plans/2026-11-19-penguin-slicer-restart-plan.md` and
  `docs/handoffs/2026-11-20-penguin-slicer-session-summary.md`.
- **Links:** the only link to a deleted file outside `docs/orchestration/` was line 4 of
  [the feedback notes](../../handoffs/2026-11-20-session-summary-feedback.md); it now
  says the summary was deleted and links the plan. A script
  (`scratchpad/plan-by-phase/check_links.py`) found 0 broken relative links or anchors in
  every `.md` outside `docs/orchestration/`.
- **Mermaid:** the plan's flowchart and the delivery guide's pairing sequence diagram (one
  label changed) rendered to SVG with Mermaid from the container's viewer in the browser,
  no syntax error, no horizontal scroll.

## Choices

1. **The relay's "team".** The relay keys everything on the pairing code, and its caller
   interface has a type named `Team` (pairing code, team number, user). In prose I wrote
   "pairing code" ("each pairing code's delivery jobs", "per pairing code" for rate
   limits), "the request's identity", and defined `Team` once as the code's name for a
   request's identity, still to be renamed. Code identifiers (`Team`, `team_number`,
   `team=` in log lines, `find_sliced_file(token, team)`) are left as they are.
2. **"team" meaning FRC Team 6238** became "the Popcorn Penguins" (the owner's wording);
   the slice guide's heading "The team's real parts" became "The Popcorn Penguins' real
   parts", with its four mentions. "The mechanical mentor's target" became "the Popcorn
   Penguins' target". The plate named `team` in `tests/frc_parts.py` keeps its name, now
   in code type.
3. **New term "configuration"** in the plan for the settings an administrator keeps
   (printers, filaments with their profiles, pairing code, units of uploaded parts); the
   old "team configuration" is gone. Where it is kept is stated as open.
4. **The feedback notes** sit in `docs/handoffs/` (deletion only for me), but the stop
   condition forbids a link to a deleted file, so I changed only that one link.
5. **The Windows checklist and the session preparation facts** (summary 2.4, not in any
   guide) went into the delivery guide's "Before trusting it at the H2S" section, not the
   plan.
6. **What the phases need from each component** is written as open needs that follow
   from the mockup (settings beyond four overrides, profiles per filament, where inches
   are scaled, a preview form, finding a job after a refresh, cross-origin access); how to
   meet each is left open. Facts checked in code: no CORS in `web.py`, `MAX_RUNNING = 1`,
   `MAX_QUEUED = 2`, four overrides in the contract, `DEFAULT_BACKEND_URL`.
7. **Facts the old documents had wrong are corrected from the guide:** the memory ceiling is
   2,000 MB (not 900 MB), and the host sizing is 3.5 GB (not 1.3 GB), after pull request 11.
8. **README.md's "3D printing for FRC shops"** is left as it is; it says "FRC" but none of
   the three words. The owner may want it changed, since PenguinSlicer is not only for FRC.

## Messages left as they are (in code, for the later change)

No contract prose or guide quotes a message that uses the old words, so nothing in prose
was left around such a message. The old words are still in code: the slice service
(`errors.py`, `limits.py`, `service.py`, `mesh.py`, `plate.py`, `print_config.py`,
`jobs.py`, `slicer.py`), the relay (`errors.py`, `relay.py`, `routes.py`, `caller.py`,
`app.py`, `__init__.py`) and the daemon (`__main__.py`, `config.py`, `printer.py`,
`relay_client.py`), and in `slice/tests/frc_parts.py` comments. Listed as known future
work in the plan. The fast suites were not run (no environment in this checkout); the
tests that read the guides and contracts parse the error-code tables, the printer-values
table and contract field rows, none of which I changed.

## Where each section of the old documents went

**Restart plan:**

| Section | Went to |
|---|---|
| Header (what it replaced) | Plan, closing paragraph (the notes-repository links) |
| 1 Short answer | Plan, Short answer, updated |
| 2 Terms | Plan, Terms. Dropped: plate 3MF, plate limits, reference plates, status of team configuration, port, hardening, review round, ledger (not used in the plan; the guides define their own); "team configuration" replaced by "configuration" |
| 3 Approach | Premise 1 in the plan's rules; premise 2 (Onshape solved) in phase 4's risks; premise 3 in phase 1. The print branch's size (412 files) dropped as history |
| 4 Repository | Plan, The repository (diagram, rules, how changes reach `main`, stack) |
| 5 Standing requirements | Plan, Standing requirements, with "user" and the owner's error-text rule |
| 6 Slice service | Slice guide (already) and its Where it stands; reference plates there |
| 7.1 Delivery state | Delivery guide and its Where it stands; Python now, Rust or Go later in the plan's future work |
| 7.2 Session at the printer | Plan, phase 5; checklist in the delivery guide |
| 7.3 Telemetry | Plan, phase 5; delivery Where it stands |
| 8 Mockup | Plan, phase 1 (the owner's direction, thrown away afterwards); details point to DECISIONS.md |
| 9 By risk | Each risk in its phase. The row "last fix round and PR of Fri 11-20" dropped: done (PRs 4, 5) |
| 10 Future work | Plan, Known future work and the phases (building the wizard and the Onshape source, use without Onshape, hosting, the Onshape test bed now in phases 2 to 4) |

**Session summary:**

| Section | Went to |
|---|---|
| Revision note, 1 Short answer | Dropped: superseded by the plan's short answer |
| Terms | Plan's terms where used; process terms (builder, fix round, defect, coordinator, ruling, brief, phase as port/hardening) dropped: they describe past runs, kept in `docs/orchestration/` |
| 2.1 Decisions | Nothing open; dropped |
| 2.2 Rulings R1 to R18 | Each is already the state written in the guides (R1 to R4, R13 in the slice guide; R5 to R12, R14, R16, R18 in the delivery guide); R15 in the plan (use without Onshape is phase 2); R17 in the slice guide's Where it stands. None kept as a list, by the owner's rule |
| 2.3 Mockup | Superseded by DECISIONS.md (mockup versions 4 and 5); dropped |
| 2.4 Session at the printer | Delivery guide: H2S checklist (already), Windows checklist and the session's needs (added) |
| 2.5 Facts F1 to F5 | Plan, phase 4 risks (F1 to F4, F5 in Onshape) and phase 1 (F5 on generated parts) |
| 3 What was done | Dropped as history (git log, `docs/orchestration/`); Orca AGPL versus MIT kept in phase 1 |
| 4.1 Slice service | Slice guide (already) and its Where it stands; 900 MB figures superseded |
| 4.2 Printer delivery | Delivery guide (already: P1, P2 as "Two limits that wait for the real printer"; not handled by design) and its Where it stands |
| 4.3, 4.4 Wizard, Onshape source | Plan, Where things stand |
| 5 What went wrong | Dropped: records of past runs; the lessons are already in CLAUDE.md's gotchas. The unchecked claims (Windows, the builder's checklist) are kept in the delivery guide |
| 6 Where everything is | Dropped: the plan links each place; commit ids are in git log |
| 7 Ways forward | Each risk in its phase or in known future work |

**Feedback notes, non-mockup parts:** terms (plan's terms); D1, D7 (the repository); D2,
D6 (phase 5); D3, D10, D11 and the answers to the four questions (done, dropped); D4, D5
(standing requirement on upstream, future work); D8 (slice guide); D9 (delivery guide);
S2, S4 and one interface per component (plan's rules, slice guide); the real parts and the
MIT licence (slice guide, plan); the words rule and help versus error text (plan's
standing requirements); units (plan, phases 2 and 4). The mockup parts are DECISIONS.md's.

## For the owner

- **The workspace file `/repos/popcornpenguins/CLAUDE.md` still names the deleted restart
  plan** as the place to start, and the memory note `penguin-slicer-restart.md` does too.
  Neither is in this repository, so I did not change them; they should point at
  `docs/plans/penguin-slicer-plan.md`.
- **A slip, fixed:** the browser tool wrote two log files into a git-ignored
  `.playwright-cli/` folder in `/repos/popcornpenguins/penguin-slicer` (its working
  directory). I removed the two files and the empty folder at once; nothing tracked was
  touched.
- Open, for the phases' specs: everything the plan marks open (where the configuration
  lives, the six needs from the slice service in phase 2, every hosting question, sign-in
  outside Onshape, where the relay runs).
