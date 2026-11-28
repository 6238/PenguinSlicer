# Batch front-5-start-log-whole: the record

The batch builds items 17 to 19 of the front server's phase 2 list
([By phase](../../../../front/README-details.md#phase-2-one-machine-no-onshape-no-printer)):
collecting at start; the log's gathering of the slice service's lines, with the group
added, and the page's reports about itself; and the tests across the whole (each row of
the restart table, the front server's half; forty progress streams with short requests
still answered; no secret in any log line or answer). Item 20, the joined suite, is a later
batch's. Written Fri 2026-11-27, Pacific time.

## Decisions made

1. **A finished slice job already stored, whose sliced file the slice service still
   holds.** The details file says to collect a finished one when `file_on_disk` is true
   and the state bucket has no stored record, and is silent on one that has both. Chosen:
   it is followed all the same; the following finds the `stored` (or `failed`) record,
   fetches nothing, and tells the slice service to delete its copy. Reason: this is a front
   server stopped between writing the record and telling the slice service, and the slice
   service's copy would otherwise wait two hours. To overrule: `Collector._kind` in
   `penguin_front.collecting`, returning `left` for those.
2. **A finished slice job whose record is `expired`.** Silent. Chosen: left alone, never
   stored again, so a sliced file past its two hours cannot come back. To overrule: the
   same function.
3. **A state bucket that does not answer while the records are read at start.** Silent.
   Chosen: the whole pass waits and is asked again, with the same growing waits as a slice
   service that does not answer. Reason: following a slice job without its record's group
   would store its sliced file with no group. To overrule: `_Again` in `Collector._kind`.
4. **An answer of `GET /slices` other than a `200` list, and an entry of another form.**
   Silent. Chosen: an answer that is not the list is asked again after a wait; an entry of
   another form (not an object, a `job` not of the id's form, a `user_key` that cannot name
   a folder, a `progress` without a `state`) is skipped with a line
   `slices_entry_unreadable`, the rest collected. To overrule: `_readable`.
5. **An `ended_at` of another form.** Silent. Chosen: the two hours count from when the
   following hears the slice is done, as for any followed slice job. To overrule:
   `_ended_at`.
6. **How the collection reaches the following.** `Follower.follow` takes `ended_at`, and
   a collected slice job is followed like any other: its stream's first event is its
   `done` report, and storing is the following's. Reason: one way of storing, already
   tested step by step, rather than a second.
7. **Where the gathering stopped is kept in the state bucket** (`log-cursor/slice.json`,
   kind `log_cursor`, format 1). The documents say only that the front server passes back
   the last `n` and starts from `0` when the process changes; a restarted front server
   would otherwise ask from `0` and gather again up to 10,000 lines already written.
   Chosen: the cursor is written after each gathering that moved it, before the lines reach
   the log bucket at the next minute's file, so a crash between the two loses that minute's
   slice lines (still in the slice service's own output) rather than doubling them; a
   deploy loses none, since the stop writes the file. A cursor that cannot be read skips
   that minute. To overrule: `penguin_front.gathering`; with no cursor, `_read_cursor`
   returns at once and every start asks from `0`.
8. **A slice service that does not answer `GET /log`,** or answers with what is not the
   log. The slice service's `GET /log` is still to be built (its contract says so), so
   today every answer is `404`. Chosen: one line `slice_log_unavailable`, then silence
   until an answer that was the log, so a slice service without the route does not write a
   line a minute. To overrule: `_unavailable` in `Gatherer._gather`.
9. **A gathered line of the wrong shape** (the record of batch front-1 left this to item
   18): a line that is not an object, or whose `n` is not a whole number past the last one,
   is dropped and counted in one line `slice_log_lines_unreadable`. A `group` a slice line
   carries is removed, since the slice service never knows the group and "a line it cannot
   place keeps no group".
10. **Placing a line's group.** The following's group while the slice job is followed,
    else the record's, remembered for the last 10,000 slice jobs (`GROUPS_KEPT`,
    *proposed*); a slice job with no record is looked for once a gathering.
11. **The bound on one gathering:** `MAX_ASKS`, 100 answers (100,000 lines), *proposed*,
    so that a slice service that always says `more` cannot hold the loop; an answer saying
    `more` with no lines ends the gathering.
12. **The page's reports: what is refused and what is dropped.** The details file
    proposes refusing an enumerated value off its list. Chosen as a rule for every field: a
    required field missing, of the wrong kind or off its list is refused `400`
    `front.bad_request` and nothing is written; an optional field of the wrong kind is
    dropped. A `part_sha256` that is not 64 lowercase hexadecimal characters is dropped, so
    the field cannot carry a part's name. A Layout summary drops the Preview's fields; a
    Preview summary without them is refused. Numbers are any JSON number, which is always
    finite, since `json_body` refuses `NaN`, `Infinity` and `1e999` (the details file's
    wording). An empty `page` is refused like a missing one, since a report without a page
    id cannot be held to its limit. `front.too_many_reports` is retryable false: the page
    drops a refused report and never sends it again.
13. **The report's lines** are `failure_report` and `drawing_report`, component `wizard`,
    with `user_key`, `group` (only when the cookie lists it) and `page_version` (only of the
    version's form) before the contract's fields. A group the cookie does not list writes
    no `refused` line, since the report is not refused.
14. **`page`'s length** is 64 characters (`PAGE_CHARS`, *proposed*); the contract gives
    none.
15. **A report's size.** The documents give none. Chosen: 16,384 bytes
    (`MAX_REPORT_BYTES`, *proposed*), refused `400` `front.bad_request` before it is read,
    and a body without `Content-Length` read no further than one byte past it. Reason: a
    report is under 2 KB, and without a bound a hostile page could have any body read
    whole. `json_body` now takes bytes already read.
16. **`front.too_many_reports`' sentences** are new: "This page sent more reports about
    itself than the server takes in a minute." and "Nothing needs doing: the page goes on
    without sending this one." No user sees them; the page drops the report.
17. **Forty streams need ten users.** The details file asks for forty progress streams and
    three followings. One user may hold four streams, and a stream is on that user's own
    slice job, so forty streams are ten users' four each and ten followings. Chosen: ten
    followings, threads 40 + 10 + 7 = 57, twenty short requests answered. The test is
    stricter than asked (seven more followings); with three, the forty streams cannot
    exist in phase 2. To overrule: `tests/test_users_at_once.py`.
18. **The restart table's browser-storage row.** Nothing of it is the front server's, so
    its test is what the front server owes it: a part and a plate the page sends again
    after the restart are answered as the first attempts were.
19. **The search for secrets runs after every test** of the fast suite, not as one test:
    `tests/conftest.py` patches the cookie key, sealing, the log's printing and gathering,
    and the web framework's handling of each answer of the front server, and
    `tests/secret_watch.py` searches. `Set-Cookie` is left out, since it carries the
    cookie by design. Searched for: every cookie key given or made (with the made key's
    hexadecimal and base64 forms), every cookie sealed, every Onshape token the stand-in
    issued; values shorter than eight characters are not searched for. The local stand-ins
    for the log in `tests/test_rules.py`, `tests/test_records.py` and `tests/test_server.py`
    are now `front_helpers.Lines`, so every line any test's log is given is searched.
20. **`MALLOC_ARENA_MAX=2` in the make targets.** The forty-streams test holds about
    seventy threads; glibc reserves 64 MB of address space per thread arena, and under the
    suite's 4G address-space limit the run failed to start threads (`can't start new
    thread`, `MemoryError`) and once hung until its time limit. Bounding the arenas leaves
    the memory used unchanged. A run of pytest by hand outside the make targets lacks it.
    To overrule: the `BOUNDED` line of `front/Makefile`, and then the forty-streams test
    needs its own process.
21. **A listed slice job in a state off the contract's list that is not final.** Silent.
    Chosen: followed, as a waiting or running one is; its following reads the slice job's
    own reports and ends on its final one. Reason: leaving it alone would leave a slice
    job of a newer slice service unstored. To overrule: `Collector._kind`, returning `left`
    for a state outside `queued`, `running` and the final ones.
22. **A gathered line whose `n` is past what its answer can hold** (from the review). The
    contract numbers a process's lines from 1, with none skipped but the dropped, so no line
    of one answer can carry a number past the `after` asked plus `dropped` plus the lines in
    the answer. Chosen: such a line is dropped and counted as unreadable, so that one line
    with an `n` of 10^30 cannot move the cursor past every line still to come. To overrule:
    `highest` in `Gatherer._gather`.
23. **A gathered line naming a component other than `slice`** (from the review). The
    contract says every slice line carries `component` `"slice"`. Chosen: the gathering
    writes `slice` over whatever the line names, rather than dropping the line, so that a
    slice service line never passes for the front server's or the wizard's and is still
    kept. To overrule: `Gatherer._placed`.
24. **The guide's thread budget beside decision 17** (from the review). The guide's sum of
    100 counts three followings, the most the slice service as configured gives at once
    (one running, two waiting); the forty-streams test needs ten, as decision 17 says.
    Chosen: the sum stands, and the guide now says in a paragraph of its own that the test
    holds forty streams and ten followings on 57 threads; the details file's test line
    says "their followings (ten...)" instead of "three followings".
25. **A drawing summary's example file** (from the review: front-0's record left
    `POST /api/reports/drawing` without one). Chosen:
    `contracts/examples/wizard-front/report-drawing-request.json`, a Preview summary with
    every field, listed in the examples' README and named under the route in the contract;
    `tests/test_reports.py` reads it rather than holding its own copy. It adds no field and
    changes no shape, so no wizard test changes with it.

### The review's findings declined

- **Minor 6, a per-user ceiling on reports beside the per-page limit.** Declined. The
  contract and the details file fix the limit as counted per user and `page`; a hostile
  signed-in page that changes `page` each time writes at most one line a request, each
  through the rules every request meets, and costs no more than any other short request.
  A second ceiling is a change to the contract's rule, the owner's to make. To add it: a
  second `RateLimit` keyed on the user alone in `penguin_front.reports._report`, with its
  figure in the contract.

### The review's findings fixed

Each with a test seen to fail against the code mutated as the finding describes, then to
pass against the code as built: a finished slice job whose record is `failed` is not
fetched and its copy is deleted (`tests/test_collecting.py`); a report without
`Content-Length` takes at most `MAX_REPORT_BYTES + 1` bytes from a body sixty-four times the
limit, counted on the request's input (`tests/test_reports.py`); the running server's stop
ends the gathering (`tests/test_server.py`); an unreadable entry's line is cut to 300
characters (`tests/test_collecting.py`); a gathering broken off still saves its cursor
(`tests/test_gathering.py`). Decisions 22 to 25 above fix minors 4, 5 and 9; minors 7 and 8
are folded into decisions 12 and 21 and into the details file.

## Targets missed

- The fast suite now takes 7 to 12 s on one worker and 5 to 6 s on two (1,033 tests after
  the review's fixes, on a machine shared with three other builds), against the 3.8 s and 2.7 s measured on 776
  tests before this batch. It still "finishes in seconds"; the search for secrets after
  each test and the running-server tests account for the rise. Not measured apart.

## Not done

- **The previous release's page and the previous slice service's stand-in against the new
  front server** (item 19): they apply from the second release on. No release has been
  made, so there is no previous page or stand-in to keep.
- **Item 20, the joined suite:** a later batch, once the wizard's steps exist.
- **The real slice service's `GET /log`** is still to be built by the slice service's
  builder; the front server is tested against the stand-in, which answers as the contract
  says. Until it exists, a real run writes one `slice_log_unavailable` line and gathers
  nothing.
- **The restart table's three rows of phase 5** (a print, a silent daemon, a pairing code):
  with the relay.

Read against the phase 2 list from item 1 to item 19 and the records of batches front-0 to
front-4, nothing else of phase 2 fell between batches: what those records left to items 17
to 19 is built here, and what they left to phases 3 to 5 stays there.

## For the owner to look at

- The fast suite and its coverage: `make -C front test` and `make -C front coverage` from
  the repository's root (100% of branches).
- The restart table, row by row: `front/tests/test_restarts.py`.
- Collecting at start, with the slice service starting late: start the front server as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says before the slice service; its standard output shows `slices_list_retry` lines with
  waits of 1, 2, 4… seconds, then `slices_collected` once the slice service answers.
- A gathered line: once the slice service has `GET /log`, the minute's file under
  `/var/tmp/penguin-front/log/<year>/<month>/<day>/` holds the slice service's lines with a
  `group`, and `/var/tmp/penguin-front/state/log-cursor/slice.json` where the gathering
  stopped. Until then, one `slice_log_unavailable` line on standard output.
- A report: `curl -c jar http://127.0.0.1:8600/signin`, then
  `curl -b jar -H 'X-PenguinSlicer-Group: dev-group' --data-binary @contracts/examples/wizard-front/report-failure-request.json http://127.0.0.1:8600/api/reports/failure`
  answers `204`, and standard output shows a `failure_report` line, component `wizard`.
