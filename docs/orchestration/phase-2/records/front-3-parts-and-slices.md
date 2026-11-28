# Batch front-3-parts-and-slices: the record

The batch builds items 10 to 12 of the front server's phase 2 list
([By phase](../../../../front/README-details.md#phase-2-one-machine-no-onshape-no-printer)):
the user key and uploading a part with its limit on how fast; submitting a plate
configuration; and following every slice job and storing its sliced file and summary, with
the refusal of one over 50 MB. Written Sat 2026-11-28, Pacific time.

## Decisions made

1. **The order of an upload's checks.** Silent. Chosen: signed in, the current group,
   `Content-Length` (none, then over the limit), the limit on how fast, then the upload; the
   same for a submission. Reason: the cheap checks that need no body first, and a request
   refused by those checks never counts toward the limit. One exception: a submission sent
   without `Content-Length` and found over 1 MB only as it is read (decision 8) has already
   counted, since the body is read after the limit is taken. To overrule: `parts.upload_part`,
   `slices.submit`.
2. **How the limit on how fast counts.** The details file gives only the figures. Chosen: a
   window that slides, sixty seconds on the front server's clock, for each user key; a
   refused request does not count; `Retry-After` is the whole seconds until the oldest
   counted request leaves the window, at least 1; the counts are in memory, so a restart
   forgets them. To overrule: `penguin_front.ratelimit.RateLimit`.
3. **The figures.** The details file's proposals, taken as they are: 120 uploads and 30
   submissions a minute for each user (`PART_UPLOADS_PER_MINUTE`,
   `SUBMISSIONS_PER_MINUTE`). To overrule: the two constants.
4. **The pieces of an upload.** Proposed "in pieces"; silent on their size. Chosen: 64 KiB
   (`PIECE_BYTES`), the most the front server's code reads ahead of what the slice service
   has taken. To overrule: `parts.PIECE_BYTES`.
5. **The units label.** Passed exactly as the page sent it, and left out when the page sent
   none, so that the slice service's own `slice.bad_units` answers both. The front server
   adds no check of its own.
6. **The over-size refusals are made by the front server in the slice service's words.**
   The contract says the front server answers them "with the slice service's own report",
   without asking it. Chosen: the report written out in `parts.over_size` and
   `slices.over_size`, its `detail` giving the length sent. The examples are laid out for
   reading, so the tests compare the answer to the example field by field and in order, not
   byte for byte, as the slice service's suite does. To overrule: change both functions
   with the examples.
7. **A plate configuration's form is the slice service's to judge.** The details file's
   rules say a body that should be JSON and is not is `front.bad_request`; the contract's
   table for `POST /api/slices` gives `slice.bad_plate_configuration` for a plate refused by
   its form, and the details file says the plate configuration reaches the slice service
   unchanged. Chosen: the front server never parses it; a body that is not JSON reaches the
   slice service and is answered `slice.bad_plate_configuration`, with the slice service's
   sentence. Reason: one component owns the plate configuration's form, and the page gets a
   sentence about the plate rather than one about a broken request. To overrule: call
   `json_body()` in `slices.submit` before passing it.
8. **A submission without `Content-Length`.** Silent. Chosen: read no further than one byte
   past 1 MB, and refuse a longer one with the over-size report, its `detail` saying it was
   sent without `Content-Length`. (An upload of a part without one stays `400`
   `front.bad_request`, as the contract says.)
9. **The `202`'s slice job has no `part_warnings`.** The slice service's `202` carries them;
   the contract's slice job and its example do not. Chosen: the contract's four fields
   exactly; the warnings reach the page in the summary. To overrule: add the field (allowed,
   since it only adds).
10. **The `202`'s `progress` is what pages see.** For a repeat whose slice job has ended
    `done`, the slice service's latest report is `done`; the contract holds `done` back
    until the file is stored. Chosen: the `202` passes its report through
    `Follower.as_pages_see`, so it is the stored `done` with `sliced_file`, or the report
    before it while storing.
11. **The submitted record.** Proposed; built so: written only if the slice job has none
    (`if_absent`), so a repeat never replaces a stored file's record; a write that fails
    writes `slice_record_unwritten` and is no error for the page, the group then living in
    the following's memory only. The record also holds `submitted_at`.
12. **Each following has a thread of its own, counted among the 100.** The guide says the
    followings are counted among the 100 threads "and not apart". Waitress gives its pool to
    requests only, so chosen: a thread per following, and while n slice jobs are followed
    the running server serves with n fewer request threads (waitress's own
    `set_thread_count`), never fewer than one. Reason: the guide's one set of threads to size
    and to watch, and a following never waiting for a free request thread. To overrule:
    remove `Follower.on_count`'s use in `server.serve`, and correct the guide.
13. **When the slice ended.** The `done` report carries no time and the stream gives none.
    Chosen: `slice_ended_at` is the moment the `done` report reached the front server, to the
    second; the two hours count from it. The alternative, asking `GET /slices` for its
    `ended_at` on every `done`, adds a request and a failure to the path of every slice. To
    overrule: fetch the list's `ended_at` in `Follower._store`.
14. **What a page sees while a `done` waits, when it has seen nothing before it.** The
    contract says "the slice service's last report before `done`", which a front server that
    reopened its stream after the slice ended never received. Chosen: the `done` report as
    `running`, one `sequence` earlier (`held_back`), so that the real `done` is not dropped by
    a page as already seen.
15. **Storing is tried again from the step that failed, without end.** The details file says
    "keeps trying" and "tried again until it succeeds". Chosen: the same waits as reopening a
    stream, 1 s doubling to 30 s, from the step that failed (reading the record, the
    summary, the file, the record's write, the delete), each try writing
    `sliced_file_retry`. A file already written is not fetched again when only the record
    failed.
16. **A sliced file gone, and a delete of an unknown slice job.** Silent. Chosen: a summary
    or file answered `slice.file_gone` (the slice service's copy gone without being stored)
    ends the following with `sliced_file_lost`, as an unknown slice job ends it; a delete
    answered `slice.unknown_job` counts as done, since the slice service then holds no copy.
17. **The order for a file over the limit.** The details file lists the delete before the
    record. Built so; a record write that is tried again sends the delete again, which the
    slice service answers as the first.
18. **The record's fields.** Proposed; built with `report` (the field name the details file
    left unnamed) holding the final report without `sliced_file`, which is made afresh each
    time it is given, since `expires_in_s` counts from that moment; and `stored_at` beside
    `slice_ended_at`.
19. **A `submitted` record whose slice job never ended `done` stays.** A failed, replaced
    or forgotten slice job leaves its `submitted` record. Chosen: nothing deletes it in this
    batch; the details file now says the sweep (item 16) is to delete one once its slice job
    can no longer be known (*proposed* there: two hours after `submitted_at` plus the slice
    service's two hours). Reason: the group in it is what the log's gathering (item 18)
    adds to the slice service's lines.
20. **Stopping the following.** Chosen: `stop()` sets a flag and wakes the clock; a
    following ends at its next wait or when its stream next carries something (within the
    slice service's 15-second repeat), and touches no slice job. Closing a socket another
    thread is reading does not reliably wake it, so nothing is closed by force.
21. **A fault while following or storing** writes `following_failed` with its trace and the
    stream is opened again after a wait. A `done` whose storing failed so is handled again
    when the reopened stream gives it again (a fix found while reviewing: its sequence had
    been marked as passed).
22. **The two new codes' sentences.** `front.too_many_requests`: "This browser sent parts or
    plates faster than the server takes them." / "Your work is kept; it is sent again by
    itself in a moment." `front.sliced_file_too_large`: "This plate's sliced file is larger
    than 50 MB, too large to keep." / "Put fewer instances on the plate, or split its parts
    over two plates, and slice again." Its status in `FRONT_REPORTS` is `None`, since it is
    never an answer's status; the test that checks every code against the contract's table
    now reads "(in a report)" as that.
23. **The log lines.** Named `part_uploaded`, `slice_submitted`, `slice_record_unwritten`,
    `slice_followed`, `slice_progress` (each change of state or stage, not each report),
    `slice_stream_reopening`, `slice_ended`, `slice_unknown`, `sliced_file_retry`,
    `sliced_file_stored` (with `stored_after_s`), `sliced_file_already_stored` (decision
    28), `sliced_file_too_large`,
    `sliced_file_lost`, `following_failed`; each about a slice job carries the user key, the
    group and the slice job.
24. **Answers of the slice service of the wrong shape.** A `202` without a `job` of the id's
    form or without a `progress` object is `500` `front.unexpected`; a progress report
    without a whole-number `sequence` is a fault, logged, and the stream is opened again.
25. **Waiting on the fake clock in the following's tests.** `FakeClock.wait_for_sleepers`
    can still count a sleeper that has just been woken, so a test that waits and advances in
    a loop can run ahead. Chosen: a clock in `tests/test_following.py` that notes each wait,
    and `next_wait()`, which waits for a wait not yet seen. The details file's account of the
    fakes says so.
26. **Tests written after the code, for item 12.** `following.py` was written before
    `tests/test_following.py`; items 10 and 11 were written test first and seen to fail. In
    place of seeing item 12's tests fail first, each of these was broken by hand and caught:
    the drop of a repeated sequence (`<=` to `<`, two failures); the `done` passed to pages
    before the delete (four failures); the limit on a sliced file (`>` to `>=`, one
    failure); the rate limit's window (`<=` to `<`, four failures); the plate
    configuration's limit (`>` to `>=`, one failure); and decision 21's fix (one failure).
27. **After review: the `202` of a repeat that ended `done` is tested** (decision 10). Three
    tests in `tests/test_slices.py` give the stand-in's `202` a `done` report at sequence 9:
    with no record the page gets `running` at sequence 8 and no `sliced_file`; with a stored
    record it gets the `done` with `sliced_file`; while the slice job is followed it gets the
    following's latest report. Replacing `as_pages_see` with the `202`'s own `progress` fails
    all three. To overrule: nothing to choose here; this is a test of decision 10, which is
    overruled in its own place.
28. **After review: a record found already `stored` or `failed` still sends the delete.** The
    documents call for it (the details file's step 3, the guide, and the architecture's "the
    moments until the front server has stored it"); the code had skipped it. That path is a
    front server that wrote the record and stopped before its delete went out, so the slice
    service is told again (`DELETE /slices/<job>/file` is idempotent; `slice.unknown_job`
    counts as done) before the pages get the record's final report. A delete that fails is
    tried again after the same waits, from the delete, with the page still waiting. The line
    `sliced_file_already_stored` (`state`) is written. To overrule: drop the `_delete` call
    in the `storing.found` branch of `Follower._store_steps`.
29. **After review: `slice_ended_at` is kept across a fault while storing.** The following
    notes the moment its `done` first arrived (`_Followed.ended_at`); a `done` handled again
    after a fault (decision 21) keeps it instead of taking a later one. The documents are
    silent on which moment to keep; the first is chosen because it is the nearest to the
    slice's real end, and the two hours a sliced file is kept count from it. To overrule:
    set `followed.ended_at` afresh at each `done` in `Follower._store` (the sliced file is
    then kept up to the waits' total longer), and change the test
    `test_a_fault_while_storing_is_logged_and_the_done_report_is_handled_again`.
30. **After review: `Retry-After` rounds a part second up.** A test with 30.5 s left expects
    31; the code already did so, and `int` in place of `math.ceil` now fails it. Rounding up
    is the only choice that never tells a browser to come back before it would be taken. To
    overrule: `RateLimit.take` and its test.
31. **Declined after review: a malformed `Content-Length` (`-1`, `abc`, `1e3`).** Not changed
    in this batch. Werkzeug reads such a header as no length, so the body is read as empty and
    the slice service refuses it in its own words (`slice.part_unreadable` for a part,
    `slice.bad_plate_configuration` for a plate configuration), a report of the right form
    that tells the page the request was bad. And no such header reaches the application when
    the front server runs: Waitress, which serves it, answers `400` to any `Content-Length`
    that is not all digits before the application runs (`waitress/parser.py`,
    `ONLY_DIGIT_RE`, "Content-Length is invalid"), so all three examples reach it only
    through Flask's test client. The reviewer placed the fix with the rules for every
    request, an item of another batch, not with uploading and submitting; a check there (`400` `front.bad_request` for any
    `Content-Length` that is not a whole number) is the way to overrule.
32. **After the second review: a submission's group is tested as far as the stored record.**
    The code passed the current group to the following, but nothing checked it: replacing it
    with `"x"` passed every test. The test
    `test_the_submissions_group_reaches_the_stored_record_and_the_followings_lines` submits
    as `dev-group`, gives the stand-in's slice job a sliced file, ends it `done`, waits for
    the following's end and checks the `stored` record's `group` and the `group` of
    `slice_followed` and `sliced_file_stored`. The test of a submitted record that cannot be
    written now lets the state bucket take writes again, ends the slice job the same way and
    checks the stored record's `group`, which then came from the following's memory only
    (decision 11). Both fail under the reviewer's mutation. To overrule: nothing to choose;
    the documents require the group in the record and the lines.
33. **After the second review: what a page sees of a `done` while the following's latest is
    final.** `as_pages_see` gave the latest report only when it was not final, and otherwise
    held the `done` back; the reviewer found dropping that condition changed no test. It is
    not quite equivalent: between the final report's delivery and the following's end the
    latest is final, and when the state bucket cannot be read at that moment the condition
    turned a stored `done` with its `sliced_file` back into `running`. Chosen: the latest
    report, final or not, is what pages see while the slice job is followed; a test asks
    `as_pages_see` from inside the final report's delivery with the state bucket unreadable,
    and failed for that reason before the condition was removed. To overrule: restore the
    condition in `Follower.as_pages_see` and change the test
    `test_a_done_report_seen_as_the_final_report_is_delivered_is_that_final_report`.
34. **After the second review: three checks the mutations survived are now tested.** A
    submission refused `413` for its `Content-Length` does not count toward the limit on how
    fast (`test_a_submission_refused_for_its_size_does_not_count`, which fails when the
    limit is taken before the size check); `sliced_file_already_stored` is checked line for
    line in the test of a file already stored; and `stored_after_s` is checked as 1 after a
    fault and its one-second wait, where the test of the following's lines can only see 0.
    Each was seen to fail under the reviewer's mutation. To overrule: nothing to choose.

## Targets missed

- **"Refused before the body is read."** Waitress, the web server, receives the whole
  request before the application runs, keeping a body over 512 KB in a temporary file. So a
  part of 9 MB or a plate configuration of 2 MB crosses the network and lands on the front
  server's disk before it is refused; what holds is that the front server's code reads none
  of it and the slice service is sent nothing. Both documents now say so.
- **`slice_ended_at` is the front server's moment, not the slice service's.** It is the
  moment the `done` report arrived: within milliseconds on an open stream, but up to the
  current wait (at most 30 s) after the slice's real end when the stream had to be opened
  again. The two hours count from it (decision 13).
- **"A `Content-Length` that understates the size is caught by the count"** is tested with
  no `Content-Length` at all: the HTTP client reads no further than a length a header
  states, so a lying header cannot carry more bytes than it says.
- **The fast suite's time.** 768 tests, about 7.5 seconds on two workers and about 13 on
  one, from about 4 and 7 before the batch. After the second review's fixes, 776 tests, 6.5
  seconds on two workers and 10.8 on one, measured Sat 2026-11-28 (the reviewer measured
  6.0 to 6.5 and 11.1 for 773). The slowest test, an upload of a part of
  exactly 7.5 MB, takes about 0.5 s; where the rest goes was not measured.
- **Test first** was not met for item 12 (decision 26). The reviewer's finding on it cannot
  be fixed after the fact; the fixes of decisions 27 to 30 were each written test first and
  seen to fail for the finding's reason (decision 27's by the reviewer's mutation, since the
  code was already right).

## Not done

- Pages reach the following only through `Follower.subscribe` in the tests: the progress
  streams that give a page its reports are item 13, and asking about a slice job, the
  sliced file's details and the sliced file are items 14 and 15.
- `front.slice_unknown` for another user's slice job, and its refusal line: built with the
  requests that ask about one (items 13 to 15). Today another user key's slice job is given
  nothing by `subscribe` and `latest`.
- Deleting `submitted` records that will never be stored (decision 19) and expiring stored
  files: the sweep and the two-hour rule, item 16.
- Collecting at start the slice jobs that ended while the front server was down: item 17.
  The follower already stores a `done` slice job it is given; item 17 gives it the list.
- The log's gathering adding the group to the slice service's lines: item 18.

## For the owner to look at

- The fast suite and its coverage: `make -C front test` and `make -C front coverage` from
  the repository's root (100% of branches).
- The order of events of one slice, as the tests put it:
  `front/tests/test_following.py`, the test
  `test_a_page_gets_done_only_after_the_delete_and_it_carries_the_sliced_file`, and the
  record and file it leaves (`test_a_slice_job_ending_with_no_page_following_is_stored_then_deleted`).
- Not run in this batch: the three components together. With the slice service started as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says and the front server beside it, `curl -c jar http://127.0.0.1:8600/signin`, then
  `curl -b jar -H 'X-PenguinSlicer-Group: dev-group' --data-binary @contracts/examples/parts/bracket.stl
  'http://127.0.0.1:8600/api/parts?units=mm'` answers the part's record; a plate
  configuration naming it, posted to `/api/slices`, is sliced, and its sliced file appears
  under `/var/tmp/penguin-front/state/sliced/dev-user/` with its record beside it.
