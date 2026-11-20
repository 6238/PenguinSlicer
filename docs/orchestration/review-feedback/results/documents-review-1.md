# Review 1 of the session summary and the plan

Written Fri 2026-11-20 12:20 PT. Reviewed and corrected:
[the session summary](../../../handoffs/2026-11-20-penguin-slicer-session-summary.md) and
[the plan](../../../plans/2026-11-19-penguin-slicer-restart-plan.md), against
[the feedback notes](../../../handoffs/2026-11-20-session-summary-feedback.md),
[the writer's brief](../briefs/documents.md), [the ledger](../progress.md), the guides,
`contracts/`, `CLAUDE.md`, the result files of this run up to
[slice-review-3.md](slice-review-3.md) and [delivery-fix-3.md](delivery-fix-3.md), and
`git show main:` of the summary. The writer's own result file was not opened. Only the two
documents and this file were changed.

## Verdicts

| Check | Verdict |
|---|---|
| (a) Feedback applied, present state, 2.1 says nothing is open | Pass after small fixes |
| (b) Place kept; unread sections changed only as allowed | Pass |
| (c) Revision block | Pass after update |
| (d) Facts | Fixed: several statements overtaken by the third review rounds, one wrong time |
| (e) Terms | Fixed: "the Windows computer", "host" for the daemon's computer, "record" in a third sense |
| (f) Readability | Pass; 4.1 and 4.2 figure passages rewritten for the newer figures |
| (g) Mermaid | Pass: one block in each document, `flowchart TB`, renders an svg, no syntax error, `scrollWidth` = `clientWidth` (1280) on both pages |
| (h) Links | Pass: the one broken link reported is in an old record (`orchestration/penguin-slicer/results/slice-hardening-review-4.md`), not in these documents |
| (i) Estimates, priorities, order, times | Fixed in the plan: section 10's "Orca 2.5.x first" was an order without a risk reason |

## (a) Feedback applied

Every item of the feedback notes is written as the present state where it belongs: D1 in
sections 1, 3.2 and 6; D2 as "The timed rule after a start command" in 4.2 and R16; D3 in
4.1 and 4.2; D4 in 4.1 and R4; D5 in 4.1, S7 and 7; D6 in 4.2 and 7; D7 in 6; D8 in 4.1
and R17; D9 in 4.2; D10 in 4.2 and 5; D11 in 6; the four terms; one interface in 4.1, R3,
R13. Section 2.1 says no decision is open. No "formerly" or "the owner decided" remains.

Changed: the telemetry paragraph of 4.2 left out the owner's "issues with the UI"; added.
Section 6's "nothing in it is generated from elsewhere" stated as certain what the owner
said only "as far as the owner knows"; softened to his words.

## (b) Place kept

All of R1 to R18, M1 to M16, F1 to F5, P1 and P2 are present, unrenumbered; S7 and S9
keep their numbers. Section by section against `main`, the unread sections changed only
in terms, facts no longer true and results of decisions: R3, R4, R13, R15 to R18 (the
decisions), R7 and R11 ("record" replaced by delivery job), the viewer address in 2.3,
the "Instances" sentence in 2.3 (follows from the term, supported by
[mockup.md](mockup.md)), step 2 and the certificate line in 2.4, the `uv run` before
`together.relay_server` (the guide's command), the new delete line of the H2S checklist
(copied from the guide), 4.2 per the brief, the P3 sentence and the installer line in 5.
Nothing reverted.

## (c) Revision block

Eight lines. Updated: the time (12:20 PT), "the daemon's computer" among the defined
terms, the third review rounds' figures, sections 3.1 and 3.2 named as changed, R7 and
R11 added to the reworded rulings. The plan's revision time updated to match.

## (d) Facts corrected

- Section 1, 3.6, 4.1, 4.2, 6: "a third review round is running" was overtaken. Now: both
  third review rounds judged their change fit to merge with two low defects each;
  printer delivery's third fix round reports both fixed ([delivery-fix-3.md](delivery-fix-3.md));
  the slice service's is running; after it the change merges by pull request on the
  suites' evidence, with no fourth review round (ledger, about 12:00 PT).
- Section 3.6: the builders started at 09:32 PT (ledger), not "about 09:00". Third review
  rows added to its table.
- Section 4.1: the figures table now comes from [slice-review-3.md](slice-review-3.md)
  (919 tests, 4.1 to 4.8 s quiet, real-Orca 35 in 33.1 s, 100 spacers 509 MB in 6.2 s,
  interleaved plate within 0.054 mm, cancel during the write 0.03 to 0.20 s). The
  builder's 200 MB figure replaced by the reviewer's 216 to 233 MB; the 280 MB sizing now
  carries the reviewer's 343 MB for a long-running slice service process (also in 7 and
  the plan's section 10). "Open now" names the two low defects of the third round.
- Section 4.2: the bullet saying the daemon's computer "has one name, 'the computer next
  to the printer', then 'the daemon's computer'" was false (two names, review 3 defect 2);
  replaced by the third fix round's state. The figures table now comes from
  [delivery-review-3.md](delivery-review-3.md) (1,120 tests and 168 subtests, 57 upstream
  checks, 5 of 5 mutations, 16 cancel cases identical to `main`); the second round's
  quiet timing and `make test-repeat` kept and labelled as such; the builder's figures
  are now the third fix round's.
- Sections 1 and 6: `work/review-feedback` exists only locally (`git ls-remote` shows no
  such branch on GitHub); "not yet pushed" added.
- Section 6: the latest result files now link review 3 and delivery fix 3.
- Plan: section 6's and section 9's "review rounds" rows brought to the same state; the
  section 9 row now says what makes it low risk.

Checked and true: GitHub `6238/PenguinSlicer` public, pull requests 1 to 3 merged at
09:13, 09:31 and 09:44 PT on Fri 11-20; every make target named exists in the two
Makefiles; the `serve` and `curl` commands, routes and `contracts/examples/` files match
`slice/README.md`; `MAX_INSTANCES` 150, `MAX_PARTS` 25, 900 MB ceiling, 188.5 MB upload
bound in `limits.py` and the guide; the spacer table matches [slice.md](slice.md); the
delivery settings and their values in 2.4 match the guide; the install step and
`together.relay_server` match the delivery guide; the workspace `CLAUDE.md` matches
section 6; the notes repository no longer holds the plan or the orchestration records.

## (e) Terms

- **The daemon's computer** had no definition in either document, and "the Windows
  computer" stood for it in 2.4, 5 and 7 of the summary and 7.1, 7.2 and 9 of the plan.
  Added a terms row in each ("the computer next to the printer, on the printer's network,
  that runs the daemon"), the daemon row now points at it, and every "Windows computer"
  became "the daemon's computer" (the summary says once that it is the owner's Windows
  computer).
- **"host"** meant both the slice service's server and the daemon's computer (4.2 and 7
  of the summary, 7.3 of the plan). The daemon's sense now says "the daemon's computer";
  "host" keeps only the server sense.
- **"record"**: "the restart notes ... recorded the first attempt" and "the container
  recorded two out-of-memory kills" were a third and fourth sense beside the `record`
  command and recordings; now "described" and "logged".
- **Plan, "fresh, whole report"** for the printer's status: "report" is the progress or
  error report elsewhere; now "whole, fresh status documents".
- instance, plate configuration, slice job, slice service process, HTTP interface,
  delivery job, start command, hold: no slip found.

## (f) Readability

The 4.1 and 4.2 passages about figures were rewritten in place for the newer figures; the
"Outcome of the last round" bullets were regrouped so that the second round's delete fix
sits under "confirmed by a review round" and the third fix round has its own bullet.

## (i) Order and times

The plan's section 10 put Orca 2.5.x "first" in a list it calls unordered; now "not in any
order", and section 1 says "taking Orca 2.5.x among it". Section 7 of the summary and
section 9 of the plan are by risk with reasons. Times are Pacific with weekday and date.

## Not settled

- The slice service's third fix round had not returned when this was written; the
  documents say it is running. When it returns, sections 1, 3.6, 4.1 and 6 of the
  summary and sections 6 and 9 of the plan need one sentence each.
- The local `main` is behind GitHub (pull request 3 not fetched). Not a statement in the
  documents; noted only.
- The figures marked "measured by the builder" (delivery's third fix round) are not
  confirmed by a reviewer, by the ledger's ruling.
