# Batch front-4-streams-files-two-hours: the record

The batch builds items 13 to 16 of the front server's phase 2 list
([By phase](../../../../front/README-details.md#phase-2-one-machine-no-onshape-no-printer)):
progress streams, four at most for one user; asking about a slice job; the sliced file's
details and the sliced file, with the moment it expires; and the two-hour rule, refusing,
deleting and the sweep. With them, what earlier batches left to these items:
`front.slice_unknown` and its refusal line, the refusal of an id of another form in a path,
the sweep's deletion of `submitted` records never to be stored, and the once-a-minute line
on how full the server is. Written Fri 2026-11-27, Pacific time.

## Decisions made

1. **The code for an id of another form in a path.** The details file says `404` "before it
   asks anyone" and names no code. Chosen: `front.slice_unknown`, after the sign-in and the
   current group are checked, with the same `refused` line as any unknown slice job. Reason:
   an id that cannot be a slice job is, to the page, a slice job nobody knows. To overrule:
   `asking.reckon`.
2. **The refusal line for another user's slice job.** The documents ask that the attempt be
   logged as a refusal, but the slice service answers another user's slice job and one that
   never was alike, and the records are filed under each user key. Chosen: every unknown
   slice job writes `refused` (`reason` `slice_unknown`), whose `why` says "another user's
   slice job" only when the front server follows that slice job itself for another user key
   (`Follower.whose`). Finding another user's otherwise would mean listing every user's
   records on each request. To overrule: `asking._ask_slice_service` and `_unknown`.
3. **Asking, or opening a stream, starts a following.** The documents are silent. Chosen: a
   report not yet final, of a slice job the front server does not follow, starts its
   following, with its record's group or else the current group, after the answer is
   reckoned. Reason: without it, until item 17 collects slice jobs at start, a page that
   comes back after a restart of the front server would have a stream that never moves and
   a sliced file nobody stores. To overrule: the last lines of `asking.reckon`.
4. **A stored record whose file has gone** (removed by hand, or by anything else) is treated
   as a file due: the record turns `expired` and the answer is "expired" (`why` `gone` in
   the line). The details file says such a file is answered `410`; that the record turns
   `expired` is chosen, so the answer stays "expired" for its extra day as for any other.
5. **The order of expiring.** Silent. Chosen: the file is deleted first, then the record
   turned `expired`, so a record never says `expired` beside a file still there; a delete or
   a write that fails leaves the record `stored` for the sweep, and the request is answered
   "expired" all the same (line `sliced_file_expire_failed`). Reason: the refusal must be on
   time whatever the state bucket does.
6. **The figures for keeping records.** `EXPIRED_RECORD_KEPT_S` 86,400 and
   `SUBMITTED_RECORD_KEPT_S` 14,400 (two hours plus the slice service's two hours) are the
   details file's proposals, taken as they are. Silent on `failed` records (a sliced file
   over 50 MB): chosen `FAILED_RECORD_KEPT_S`, a day and two hours from the slice's end, as
   long as a stored file and its `expired` record together. To overrule: the constants in
   `penguin_front.sliced`.
7. **A sliced file with no record.** Silent; it is left by a front server stopped between
   writing the file and its record. Chosen: the sweep deletes it two hours after it was
   stored (line `sliced_file_deleted`), unless its slice job is followed.
8. **What the sweep leaves alone:** any slice job the front server follows (its storing may
   be under way), a record it cannot read (a newer format, which a newer front server
   wrote), and any name it does not make. The sweep runs once at start, so a file that fell
   due while the front server was down goes at once, then every 600 s (the proposal). It is
   started by the running server only, so an application built for a test sweeps when the
   test asks. To overrule: `penguin_front.sweep` and `server.serve`.
9. **`/summary` and `/file` for a slice job that will never have a sliced file** (failed,
   cancelled, or a `failed` record over 50 MB). The contract gives `409` for one not
   finished or not stored and is silent on these. Chosen: `409`
   `front.sliced_file_not_ready`; the page asks for neither in honest use.
10. **The name in `Content-Disposition`.** The record's `file` when it is made of letters,
    digits, `.`, `+`, `-` and `_`, as the sliced file's name always is; otherwise
    `<slice>.gcode.3mf`, so that no name can break the header.
11. **The line for a serving** is `sliced_file_served` (`size_bytes`, `sent_bytes`, `whole`),
    written when the answer is closed, so a download cut off shows as not whole. A `HEAD`
    writes it with nothing sent.
12. **Closing a reconnecting page's old stream, at the limit only.** The details file
    proposed that "a new stream of a user on a job that user already follows closes that
    user's oldest stream on the same job", with the test "a second stream of a user on the
    same job closes the first". Built instead: only a user **at** the limit has their oldest
    stream on that job closed; below it nothing is closed. Reason: the guide's own case of
    three tabs watching one slice job would otherwise have each tab close another's stream,
    and each tab reopen it, in turn without end. The aim of the proposal, that a page
    reconnecting at once is not refused on account of its own dropped stream, holds, since
    a refusal can only happen at the limit. The details file and its test now say so. To
    overrule: `Streams.open`, and the tests
    `test_at_the_limit_a_new_stream_on_a_job_closes_the_users_oldest_on_that_job` and
    `test_below_the_limit_several_streams_on_one_job_stay_open`.
13. **A stream whose first report is final** (a slice job stored, failed, cancelled or
    expired) sends it, closes at once and is never counted against the four. Reason: it holds
    no thread, and a fifth tab on a finished slice job should see the result.
14. **The fifteen seconds of a keep-alive count from the last thing sent**, not from the last
    wake, so a wake that sends nothing (a report already sent) does not put the comment line
    off. Found by a test that failed by its own order.
15. **A `HEAD` of a progress stream** is answered `200` with the stream's headers and holds
    nothing, so it is never counted.
16. **The running server's stop ends every page's stream** (`why` `stopping`), and the
    sweep's and the line's loops. The rest of stopping (letting downloads finish, taking no
    new requests first) is phase 3's.
17. **The sentences of the four new codes.** `front.slice_unknown`: "The server knows of no
    such slice." / "Slice the plate again." `front.sliced_file_not_ready`: "This plate's
    sliced file is not ready yet." / "Wait for the slice to finish; if it happens again,
    PenguinSlicer needs fixing." `front.sliced_file_expired`: "This plate's slice has
    expired: a sliced file is kept for two hours after its slice ends." / "Slice the plate
    again." `front.too_many_streams`: "You are following more slices at once than the
    server allows: four." / "Close another tab that is slicing, or wait for one of its
    slices to finish." None carries an `action`: the contract's `slice_again` is printer
    delivery's, from phase 5, and the page offers Slice again on the code itself.
18. **The once-a-minute line.** Named `load`, written by the running server at start and
    every 60 s: `memory_bytes` (the kernel's `VmRSS`; `null` where there is no `/proc`),
    `slices_followed`, `slices_running`, `slices_waiting` (by the latest report pages see,
    `queued` being waiting), `streams_open`, `connections_open` (the streams and the
    followings' own), `threads` and `threads_in_use` (waitress's busy request threads plus
    the followings' threads, which are counted among the 100). To overrule:
    `penguin_front.load`.
19. **A loop on the front server's clock** (`penguin_front.every.Every`) runs the sweep and
    the line: a fault writes `loop_failed` and the loop goes on. It carries
    `wait_for_runs`, used only by the tests, so that a test waits on a run, never on time.
20. **The fast suite's speed.** It had grown to about 10 s on one worker (6 s on two), 776
    tests, measured Fri 2026-11-27, Pacific time. Profiling showed most of it in two places:
    each client for the slice service made its own TLS context, reading the system's
    certificates (about 8 ms, paid by every test, since every test builds the application);
    and the stand-ins' serving loop looked for a stop only every 10 ms. Chosen: one TLS
    context for every slice client (`slice_client._tls_context`), the stand-ins' loop at
    2 ms, and the tests' own loopback clients made without TLS (`loopback_client`). After:
    about 3.8 s on one worker and 2.7 s on two, for the same 776 tests; with this batch's
    tests, 884, about 3.7 to 4.3 s on two workers on a quiet machine. What remains of an
    application's cost is mostly the web framework compiling its routes, about 2.5 ms,
    which was not cheap to remove.
21. **Two tests that failed by their own order, fixed at their cause.** The load line's test
    waited for a following's first report it may have missed by subscribing late (found in
    a run of forty); and a test of the table of settings, from an earlier batch, named a
    parameter by gzip bytes carrying the time, so two workers that collected a second apart
    collected different tests (found the same way). The bytes now carry no time.

## Targets missed

- **Test first, for item 15.** The code of `/summary` and `/file` was written with item 14's
  code, before `tests/test_sliced_file.py`; items 13, 14 and 16 and the load line were
  written test first and seen to fail (every test of each file failing before its module
  existed). In place of seeing item 15's tests fail first, six checks across the batch were
  broken by hand and each was caught by the suite: the two hours (`>=` to `>`), the expired
  record's extra day (`>=` to `>`), the sweep's ages (`<` to `<=`, twice), the stream limit
  (`>=` to `>`), the stream's repeat (`<=` to `<`).
- **Another user's slice job is not told apart in the log** except when the front server
  follows it (decision 2): the line is written for every unknown slice job, so the attempt is
  logged, but its `why` says "another user's" only in that case.
- **The fast suite "finishes in seconds":** met, at about 3.8 s on one worker before this
  batch's tests and 3.7 to 4.3 s on two workers after, on a quiet machine; with four
  builders on the machine single runs took up to 10 s.

## Not done

- The test of forty progress streams and three followings with short requests still
  answered, and the test that a request waits for a free thread: item 19, as the list says.
- The tests of the two-hour rule marked phase 5 (a print moving `expires_at`, a sliced file
  kept while its delivery job has not ended, a send storing it afresh): phase 5.
- R2's three-day backstop on `sliced/`: set at R2 in phase 3.
- Letting downloads in progress finish when asked to stop: phase 3 (decision 16).
- Collecting at start the slice jobs that ended while the front server was down (item 17)
  and the log's gathering (item 18): later items. Decision 3 covers a page that comes back
  meanwhile.

## For the owner to look at

- The fast suite and its coverage: `make -C front test` and `make -C front coverage` from the
  repository's root (100% of branches).
- A progress stream as the page reads it, in
  [the contract's example](../../../../contracts/examples/wizard-front/slice-events.txt), and
  the tests that hold the front server to it: `front/tests/test_streams.py`, above all
  `test_a_stored_slice_job_streams_the_contracts_version_and_done_events_then_closes` and
  `test_at_the_limit_a_new_stream_on_a_job_closes_the_users_oldest_on_that_job`
  (decision 12).
- Not run in this batch: the three components together. With phase 2 started as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says and a slice submitted as the record of the previous batch shows, `curl -N -b jar -H
  'X-PenguinSlicer-Group: dev-group' http://127.0.0.1:8600/api/slices/<id>/events` shows the
  stream, a comment line every fifteen seconds while the slice waits, and the `done` report
  with the sliced file's details; `curl -b jar -OJ
  'http://127.0.0.1:8600/api/slices/<id>/file?group=dev-group'` downloads it under its name;
  two hours later the same request answers `410`.
