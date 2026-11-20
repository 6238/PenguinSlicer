# Brief: verification review of one component after the review-feedback changes

The dispatch line names the **component** (`slice` or `delivery`), the builder's brief
([slice.md](slice.md) or [delivery.md](delivery.md)), the round number and the result
path.

- **Deliverable (REQUIRED):** a review file at the result path in the dispatch line.
- **Stop condition (REQUIRED):** every numbered item of the builder's brief and every
  check below has a verdict backed by a command you ran or a line you read, and every
  defect is listed with its evidence.
- **Budget (REQUIRED):** 60 minutes; no cloud spend.
- **Where this fits:** an Opus agent changed this component from the builder's brief; you
  are the independent check before the coordinator opens a pull request. You have not
  seen that agent's result file and must not open anything under
  `docs/orchestration/review-feedback/results/` except files the dispatch line names.
  Judge the code and the tests, not anyone's claims.
- **Inputs:** [standing-rules.md](standing-rules.md) first, then the builder's brief,
  then the change itself: `git diff main -- <the component's folders>` and
  `git status --short` in `/repos/popcornpenguins/penguin-slicer` (the change is not
  committed yet), the component's guide, and `contracts/`.

You review; you do not fix. Change no file in the repository except your review file.

## Checks

1. **Each item of the builder's brief:** done as asked, with a test that fails when the
   change is undone. Undo five of the changes by hand in a scratch copy of the component
   and say which the suite did not notice.
2. **Terms.** Search the component's folders for the old terms of the standing rules, in
   prose, identifiers, file names, field names and messages. List every one left and say
   whether it is right to leave (for example "copy" meaning to duplicate a file).
3. **Flakes and speed.** Run the fast suite 20 times in random order with a different
   seed each time, on 2 workers. Report every failure with its seed, the wall time of a
   run on a quiet machine, and the ten slowest tests.
4. **Coverage.** Measure branch coverage per module yourself and compare with 100% for
   the slice service's package, or with the figures in the guide for printer delivery.
5. **The other suites** named in the guide pass (for the slice service the real-Orca
   suite, one Orca at a time; for printer delivery the simulated-printer suite, the
   upstream check and the properties target).
6. **Error reports.** Every way the changed code can fail towards its caller is an error
   report conforming to `contracts/error-report.md`, with a true sentence, a remedy that
   can help, and a test that produces it on purpose.
7. **The guide** matches the code: every route, command, make target, setting and limit
   it names exists and behaves as written. Follow the guide's own walk by hand.
8. **Hostile cases of your own** against what changed: write them as scratch tests or
   scripts, run them, and report every one that gives a traceback, a hang, a leaked
   process or file, or a wrong sentence.

For the slice service also: the HTTP interface is the only documented way in and the
`slice` command is gone; a cancel never delivers a file; the summary route cannot be made
to return a summary for a slice job that failed, was cancelled or is unfinished; the
debug-log reading never states a reason the log does not give (feed it truncated, empty,
huge and misleading logs); the 100-instance plate slices with the real Orca and the
figures in the guide are near what you measure.

For printer delivery also: the behaviour after a start command is unchanged apart from
the brief's items (compare the tests of the hold before and after); nothing of the
Raspberry Pi installer remains; a bug put into the code on purpose makes the properties
target fail within about a minute.

## The review file

Start with a verdict: `PASS`, or `FIX` with the count of defects. Then one section per
check with its evidence. Then the defects as a numbered list, most serious first, each
with: what is wrong, the evidence, and what would count as fixed. A defect is something
that can mislead a user, lose work, hang, leak, fail now and then, or hide a failure. A
style preference is not a defect. Grade each defect serious, medium or low.
