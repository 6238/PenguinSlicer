# Batch slice-3-job-life: a plate's later slice, the places, and a slice job without its page

The builder's record of items 7, 8 and 9 of
[the slice service's details, Phase 2](../../../../slice/README-details.md#phase-2-one-machine):
a plate's later slice job replaces its earlier one and a repeated submission is answered
with its first attempt's slice job; every waiting slice job's progress report says how many
are ahead and every slice job ended early says why; and a slice job goes on without its
page. Built to [the plate and the submission](../../../../contracts/plate-configuration.md#the-plate-and-the-submission),
[the progress report](../../../../contracts/progress-report.md) and
[`POST /slices`](../../../../contracts/slice-http-interface.md#post-slices--submit-a-plate-configuration).
What was built is described in
[A plate's slice jobs: repeats, replacement and the places](../../../../slice/README-details.md#a-plates-slice-jobs-repeats-replacement-and-the-places)
and [Progress, cancellation and cleanup](../../../../slice/README-details.md#progress-cancellation-and-cleanup)
in the details file, and in the guide's
[Run one slice at a time, and let a few wait](../../../../slice/README.md#run-one-slice-at-a-time-and-let-a-few-wait),
[End a slice job early](../../../../slice/README.md#end-a-slice-job-early) and
[Go on without the page](../../../../slice/README.md#go-on-without-the-page).

## Decisions made

1. **The places are counted together, running and waiting.** The guide calls the one
   running slot and the two waiting slots "the slice service's places"; the code as built
   refused a submission when two slice jobs were in the state `queued`, whatever was
   running. That rule cannot accept a changed plate whose earlier slice job is running
   while two others wait, which item 7 requires: the replaced one is still running until
   its Orca is gone, and two are still queued. Chosen: a slice job holds a place from its
   acceptance until it ends or is asked to end early, and a submission is refused when the
   places held reach `MAX_RUNNING + MAX_QUEUED` (three). A slice job being stopped holds
   none, so for the moment its Orca takes to stop three may wait behind it. The visible
   difference from before is only with an executor that has not yet started a free slot's
   job (the tests' held executor): three are accepted where two were. Two tests that leaned
   on the old count were changed (`test_queue_full`, and the `slice.busy` producer in
   `tests/test_errors.py`). To overrule: count `queued` jobs again in `JobPool.submit` and
   add the replaced running job's slot back by hand; the test of every place taken would
   then have to change.
2. **A slice job being stopped counts in `ahead`.** The contract counts "those running and
   those waiting before it". A replaced or requested slice job whose Orca is still dying is
   running in fact and holds the one Orca, so it is counted; a new slice job behind it
   reports one more ahead until that Orca is gone, then a new report. To overrule: count
   only running jobs with no stop asked in `JobPool._refresh_ahead` and
   `_ahead_of_a_new_job`.
3. **A waiting slice job may report `ahead` 0 for a moment.** When the running slice job
   ends, the next one is queued with nobody ahead until the executor starts it, and the
   pool sends that truthful report (`queued`, `ahead` 0) before `running`. The documents are
   silent on this gap. To overrule: skip the refresh for the oldest waiting job when a
   running one ends, since that is the one the next task starts (decision 13).
4. **The repeat is looked for twice: before the checks, and again under the pool's lock.**
   The details file says the repeat is answered "before step 1 of the checks". Two attempts
   of one submission can both pass that first look while the first is being checked, and
   the second would then replace the first. Chosen: `JobPool.submit` looks again under its
   lock and raises `jobs.RepeatedSubmission`; the HTTP interface removes the second
   attempt's folder and answers it with the first's slice job. Only a JSON object whose
   `submission_id` is a string is looked up; anything else goes on to the checks, which
   refuse it. To overrule: drop the second look, and accept that a simultaneous repeat
   ends its own first attempt.
5. **A repeat is answered even while the pool closes and with every place taken.** The
   contract says a repeat "takes no place" and, for a stopping slice service, that a repeat
   is still answered (item 14). The repeat is therefore looked for before the closing pool
   and the places. To overrule: move the look after the closing check in `JobPool.submit`.
6. **A repeat's answer is the first attempt's answer with the latest progress report.** The
   contract says "as if just accepted" and "for a repeat, whatever is latest". The
   `part_warnings` are recomputed from the first attempt's checked plate configuration,
   which the pool keeps with the record (`JobPool.payload`), so they are exactly the first
   answer's. To overrule: store the first answer itself in the record.
7. **A repeat leaves a log line of its own, `slice_repeat`.** The documents list what is
   logged and say nothing of a repeat, which is neither a transition nor a refusal. A
   support question ("why did my second try start nothing?") needs it, so it is logged with
   the job, the user key, `plate_id`, `submission_id`, status 202 and the slice job's state.
   To overrule: remove the `log(...)` call in `web._answer_repeat`.
8. **A worker that ends with `SliceCancelled` unasked is reported `requested`.** The
   contract requires `cancel_reason` on every `cancelled` report. Nothing in the slice
   service raises `SliceCancelled` without the pool's stop, but a report without a reason
   would break the contract, so the pool fills in `requested`. To overrule: change the
   fallback in `JobPool._finish`.
9. **`DELETE /slices/<job>` gives `requested`, and `JobPool.cancel`'s default reason is
   `requested`.** As built the default was `"cancel"` and only reached the log. The
   contract's three reasons are the only ones now (`jobs.CANCEL_REASONS`). `slicer.Stop`'s
   own default `"cancel"` is untouched, since only the pool sets a stop with a reason.
10. **Followers are no longer counted.** With abandonment gone, `JobPool.subscribe`,
    `unsubscribe` and the per-job counts served no purpose, so they are removed, and
    `JobPool.sweep` now returns the number of records expired instead of a pair. The details
    file says "the tests of abandonment are removed"; the tests that counted subscribers
    were changed too. To overrule: nothing depends on the counts any more; adding them
    back is self-contained.
11. **The first progress report is built with its `ahead` and is still sequence 1.** The
    contract's example of the 202 answer has `"sequence": 1, "ahead": 0`; the first report
    is made with `ahead` in it rather than sent as a second report.
12. **The old words in two code comments of `jobs.py` were changed** ("words for a
    student", "student-facing") since the file was being rewritten there; the error
    reports' sentences with the old words are left to their own change, as the details
    file says.

Decisions of the fixes made after the review of pull request #32:

13. **The executor's task runs the oldest waiting slice job, not its own.** The details
    file said the order accepted "is the order the pool's executor runs them", but
    `JobPool.submit` calls the executor outside the pool's lock, so two submits racing can
    reach it in the other order, and the later one would run first. Chosen: each submit
    gives the executor one task, `JobPool._run_next`, which starts the oldest `queued` slice
    job. Every submit adds one task and one waiting job, every task starts at most one, so
    no waiting job is left without a task. Starting the oldest changes no other job's count
    ahead, so the refresh of the counts at the start (whose removal survived the review's
    mutation) is gone. Calling the executor under the lock was not chosen: the tests'
    immediate executor runs the job on the calling thread, and the job takes the same lock.
    Tested with an executor that runs the tasks in the reverse order. To overrule: give
    each task its own job id again and serialise the submits with a lock of their own.
14. **A `cancelled` report keeps the stage it was ended at.** The contract makes `stage` and
    `stage_label` optional, and its example of a replaced slice job keeps them; the code as
    built dropped them. Chosen: keep them on `cancelled` (so a page can say where the slice
    stopped), drop them on `done` and `failed` as before. Two tests now compare the
    replaced and the waiting reports' fields with their contract examples. One web test
    that cancelled on the first report at `slicing_mesh` now also checks it is `running`,
    since the final report carries that stage too. To overrule: pass `stage=None,
    stage_label=None` for every final state in `JobPool._finish` and drop the stage from
    the contract's example.
15. **A web test's fixed `submission_id` was made a fresh one.**
    `TestSubmit::test_slicing_again_uploads_nothing` named its second submission
    `submission-2`, which the helper's counter also hands out, so in some orders the second
    was a repeat of the first and the test failed. It now takes a new one from the helper.

Findings of the review declined: none. Every finding was checked against the code and the
documents and found real: the plate configuration contract's status paragraph, the guide's
"where today they would find it gone", the mutation of a stopping slice job in the
refreshed count (a new test,
`TestAhead::test_a_job_being_stopped_still_counts_ahead_when_the_counts_are_refreshed`,
fails under it with `ahead` 0 where 1 is right), the race of two submits (decision 13), the
reports against their examples (decision 14), and the tests named after subscribers, now
followers.

Fixes made after the second review of pull request #32:

16. **The test of a finished slice job under a replacement now reads the log.**
    `TestReplacement::test_a_finished_one_is_not_touched` compared only the progress
    report, which a wrongly replaced done slice job does not change, so dropping the
    condition `r["state"] not in FINAL` from `JobPool.submit` survived. The test now also
    requires that the replacement writes no log line for the earlier slice job and that,
    once swept, its lines are `queued, running, done, expired` with no `cancel_reason`.
    Seen to fail under the mutation (an extra `cancelling` line), and pass without it. No
    code changed: the code was right.
17. **A failed report is tested to carry no stage.** The worker of
    `TestFailure::test_a_failure_carries_its_error_report` now reports `slicing_mesh` before
    it fails, and the test requires no `stage`, `stage_label` or `fraction` in the failed
    report. Without the stage reported first, keeping the stage on `failed` in
    `JobPool._finish` changed nothing visible; the test now fails under that mutation.

Findings of the second review declined:

- **The race of `shutdown()` between the pool's lock and `self._executor.submit` in
  `JobPool.submit`** is real and predates this batch: the slice job is accepted, then
  ended with `shutdown` by the stop, and the executor's `RuntimeError` makes `POST /slices`
  answer 500. Not fixed here, as the reviewer suggests: item 14 decides what a stopping
  slice service answers (`slice.stopping`) and rewrites `JobPool.shutdown`, so the fix
  belongs with it; fixing it now would settle an answer item 14 has to change. Listed under
  "Not done".

## Targets missed

None.

## Not done

- The record of a slice job still lasts one hour after it ends (`RECORD_TTL_S` 3,600 s), so a
  repeat is recognised for an hour, not two: item 10 changes that and is not in this batch.
- A stopping slice service still answers a new submission `slice.busy`, and its stop still
  ends the running slice job with `shutdown`: item 14 is not in this batch. The repeat is
  already looked for before the stop, as item 14 needs. With it stays a race: a submission
  that passes the closing check just before the stop begins reaches an executor already
  shut down, and `POST /slices` answers 500 instead of an error report
  that says the service is stopping.
- The real-Orca suite was not run: nothing in this batch changes how Orca is run, and the
  batch names no other suite.

## For the owner to look at

- `make -C slice test` and `make -C slice coverage` (100% of branches).
- The new tests: `tests/test_jobs.py` classes `TestAhead`, `TestCancelReason`,
  `TestReplacement`, `TestRepeat` and `TestGoesOnWithoutItsPage`, and `tests/test_web.py`
  classes `TestReplacementAndRepeat`, `TestGoesOnWithoutItsPage` and
  `TestStopDuringThePlateWrite::test_a_replacement_during_the_write`.
