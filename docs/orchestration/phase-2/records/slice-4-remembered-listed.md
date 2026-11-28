# Batch slice-4-remembered-listed: slice jobs remembered, listed, bounded and quoting Orca

The builder's record of items 10, 11, 12 and 13 of
[the slice service's details, Phase 2](../../../../slice/README-details.md#phase-2-one-machine):
a slice job remembered for two hours after it ends and its sliced file deleted once the
front server has stored it; the route that lists the slice jobs; a sliced file of at most
50 MB; and Orca's own sentence on the two failures about a gap. Built to
[the slice service's HTTP interface](../../../../contracts/slice-http-interface.md),
[the sliced file](../../../../contracts/sliced-file.md) and
[the error report](../../../../contracts/error-report.md). The batch also puts the
sweeper's tests on the test's clock, which
[the record of slice-1](slice-1-parts-arrive.md) left waiting on a real thread with a zero
interval. What was built is described in the details file under
[Progress, cancellation and cleanup](../../../../slice/README-details.md#progress-cancellation-and-cleanup),
[Plate limits](../../../../slice/README-details.md#plate-limits),
[Orca Slicer](../../../../slice/README-details.md#orca-slicer),
[The HTTP interface](../../../../slice/README-details.md#the-http-interface) and
[Error codes](../../../../slice/README-details.md#error-codes), and in the guide's
[Go on without the page](../../../../slice/README.md#go-on-without-the-page),
[Reading what Orca says](../../../../slice/README.md#reading-what-orca-says),
[The limits](../../../../slice/README.md#the-limits) and
[Orca's own sentence in an error report](../../../../slice/README.md#orcas-own-sentence-in-an-error-report).

## Decisions made

1. **The sweeper waits on a clock the test passes.** The documents require that no test
   waits a duration and say nothing of how the sweeper's interval is faked. Chosen:
   `JobPool.start_sweeper(wait=...)` takes the wait for one interval, the pool's closing by
   default, and ends when it returns true or the pool has closed; the tests pass
   `helpers.ManualTicks`, whose interval passes only when the test calls `tick()`. All four
   sweeper tests (three in `tests/test_jobs.py`, one in `tests/test_web.py`) use it; one of
   them moves the pool's fake clock by `RECORD_TTL_S`, ticks once and sees the record
   expire through the sweeper's own thread. A fifth test starts the default sweeper after
   the shutdown and sees it end at once. To overrule: a different fake (an injected
   `threading.Event` factory, say) changes only `start_sweeper` and those tests.
2. **The pool marks the sliced file deleted; the route removes it.** The details say the
   slice service deletes its copy at once and keep the record; they are silent on where.
   Chosen: `JobPool.delete_file` marks the record and hands back the done job's result the
   first time only, and `DELETE /slices/<job>/file` unlinks the file. The production pool has
   no `on_discard`, so routing the delete through it would have changed every pool the tests
   build. To overrule: give the web's pool an `on_discard` that removes the file and call it
   from `delete_file`.
3. **A file the disk will not remove still answers `200`.** The contract gives no answer for
   it. Chosen: the route logs `slice_file_delete_error` and answers `200`
   `{"job", "file": "deleted"}`, since the front server has the file stored and nothing it
   could do would help; the record says the file is deleted, so the file and the summary
   answer `slice.file_gone`, and the leftover goes with the slice job's folder when the
   record expires. To overrule: answer a `500` error report there, which the front server
   would then have to retry.
4. **`ended_at` comes from a wall clock of its own.** The pool's clock is monotonic and
   cannot give a time of day. Chosen: `JobPool(wall_clock=...)`, `time.time` by default,
   read when a slice job reaches its final state and written RFC 3339 in UTC to the second
   (`jobs.rfc3339`), as the contract's rules for times say. The tests pass a fake wall clock
   and move it. To overrule: derive the time from one clock, which would need a fake clock
   that gives both.
5. **`file_on_disk` is read from the record, not from the disk.** Chosen: `true` for a done
   slice job with a result whose file `DELETE /slices/<job>/file` has not deleted. A file
   that left the disk by other means still lists `true`, and its fetch answers
   `slice.file_gone`, which the front server already handles. To overrule: add a check of
   the file's existence in `JobPool.listing`, at the cost of a file system call per entry
   under the pool's lock.
6. **`slice.output_too_large` carries no action.** The contract names its stage, its
   retryable flag, its sentence's source and its remedy, and no action. Chosen: no action,
   since the wizard chooses its buttons for this code by the code itself (Back to Parts, no
   Slice again). The sentence is "The sliced file of this plate is larger than the 50 MB a
   sliced file may be.", its figure formatted from the limit when the module loads, as the
   other limits' sentences are, so a test that lowers the limit still reads "50 MB". The
   remedy is "Remove some instances, or move some of them to a new plate, and slice again.";
   on a plate of one instance it is the out-of-memory one, "Split the part in CAD into
   smaller pieces, or simplify it, and slice again.", because the contract's rule is that a
   remedy never proposes what cannot help. The *proposed* name `MAX_SLICED_FILE_BYTES` is
   kept, in `limits.py`; the check is `plate_configuration._check_size`, after the name
   guard. To overrule: add `lower_quantities` to the code's entry in `errors.CODES`, and
   the wizard's buttons would not change.
7. **Orca's sentence is the line that names the gap, and a long one is left out.** The
   details propose "the first line of its `warning_message`" and say "at most 300
   characters, and only when Orca wrote one". Chosen: the line `EMPTY_LAYER_RE` matched,
   which is the first line with the pinned Orca, stripped of the spaces around it; a line
   over 300 characters is left out rather than cut, because a cut quotation is no longer
   Orca's words. "A message without such a sentence leaves it out" is tested as a sentence
   over 300 characters and as an exception that carries none. To overrule: take the first
   line whatever it holds, or cut at 300 characters, in `slicer._gap_sentence`.
8. **The pin covers both heights Orca names.** The details name one sentence. The real Orca
   names other heights for the corpus' part with supports on ("between 9.9 and 10.62"), so
   `test_orcas_empty_layer_sentence_is_pinned` pins the sentence with supports off and on.
   The guide now says the quotation is whatever Orca said. To overrule: pin one only.
9. **A sliced plate's job gives up its hold on its parts at once.** No item of the details
   asked for it, but [the sliced file's contract](../../../../contracts/sliced-file.md)
   required it ("keeps none of them once it ends"), and the code kept the hard links for as
   long as the record, now two hours. Chosen: `web.slice_worker` removes the slice job's
   `parts/` as soon as the plate is sliced; the guide's "Go on without the page" says so. To
   overrule: remove that line, and the contract's rule "No uploads are kept with a slice
   job" with it.
10. **The sliced file's contract has no "To be built" left.** Of its four changes, the 50 MB
    limit, the copy deleted once stored and the hold given up are built here, and the part
    warnings found on upload were built by an earlier batch. Chosen: its section folded into
    the field table and the rules, and its opening saying everything is as built. To
    overrule: restore the section from the history.
11. **A deletion is a transition in the log.** Chosen: `delete_file` writes one
    `slice_job` line with the state `file_deleted`, beside `expired`, so the log shows when
    the front server collected each sliced file. To overrule: drop the line in
    `JobPool.delete_file`.
12. **The upstream check compares the gap failure with both examples.** Its comparison with
    `contracts/examples/error-report.json`, the report as built before phase 2, now leaves
    out `orca_sentence`, and a second comparison holds the report to
    `contracts/examples/error-report-orca-sentence.json`. The fast suite holds the fake
    Orca's report to the latter field for field, detail included.

## Targets missed

None. The fast suite passes with 1,521 tests and every branch of the package covered; the
upstream check passes its 60 tests in 190 seconds.

## Not done

None. Items 10 to 13 are built, and the sweeper's tests are on the test's clock. Items 14
to 18 belong to other batches.

## For the owner to look at

- The fast suite, in random order:
  `make -C slice test`, and three runs on two workers with `make -C slice test-flakes RUNS=3 WORKERS=2`.
- The upstream check, which slices with the real Orca and takes about three minutes:
  `make -C slice test-upstream`; `test_orcas_empty_layer_sentence_is_pinned` is the new test.
- By hand, with a slice service started as [Use](../../../../slice/README-details.md#use)
  says: after a slice is done, `curl -s http://127.0.0.1:8640/slices` lists it with
  `file_on_disk` true and its `ended_at`; `curl -s -X DELETE -H 'X-Penguin-User-Key: me'
  http://127.0.0.1:8640/slices/<job>/file` answers `{"file": "deleted", "job": "<job>"}`,
  after which the list shows `file_on_disk` false and the file answers `slice.file_gone`.
