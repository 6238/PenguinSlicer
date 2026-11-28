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
   log (a `404` from a slice service of an older release without the route, a `5xx`, a
   body that is not the log's form). Silent. Chosen: one line `slice_log_unavailable`,
   then silence until an answer that was the log, so such a slice service does not write a
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
    Preview summary without them is refused. A number is a JSON number a float can hold:
    `json_body` refuses `NaN`, `Infinity` and a fraction such as `1e999`, but JSON's whole
    numbers have no bound, so one past a float's range (`10**400`) is of the wrong kind
    (decision 26). A `page` that is empty or only spaces is refused like a missing one,
    since a report without a page id cannot be held to its limit. `front.too_many_reports` is retryable false: the page
    drops a refused report and never sends it again.
13. **The report's lines** are `failure_report` and `drawing_report`, component `wizard`,
    with `user_key`, `group` (only when the cookie lists it) and `page_version` (only of the
    version's form) before the contract's fields. A group the cookie does not list writes
    no `refused` line, since the report is not refused.
14. **`page`'s length** is 64 characters (`PAGE_CHARS`, *proposed*); the contract gives
    none.
15. **A report's size.** The documents give none. Chosen: 16,384 bytes
    (`MAX_REPORT_BYTES`, *proposed*), refused `400` `front.bad_request` before the front
    server's code reads it: a `Content-Length` over the limit is refused with nothing taken
    from the body, and a body without `Content-Length` is read no further than one byte past
    it. Waitress has by then received the whole body, as for every request (keeping one over
    512 KB in a temporary file). Reason: a report is under 2 KB, and without a bound a
    hostile page could have the front server's code take any body whole into its memory.
    `json_body` now takes bytes already read.
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
26. **A whole number too large for a float in a report** (second review, blocking 1). It
    reached `math.isfinite`, which raised `OverflowError`, and answered `500`
    `front.unexpected`. Chosen: of the wrong kind, as the rule of decision 12 has it,
    so `400` `front.bad_request` in a required field and dropped in an optional one.
    Reason: no honest figure of a drawing summary is past 1.8 × 10^308, and refusing
    rather than writing the number keeps the log's readers from meeting a number they
    cannot read as a float. To overrule: `_number` in `penguin_front.reports`.
27. **An answer of `GET /log` saying `more` whose lines are all unreadable** (second review,
    minor 3). Chosen: it ends the gathering, as one with no lines does, since `after` has
    not moved and the slice service would answer the same; the rest waits for the next
    minute, with one `slice_log_lines_unreadable` line a minute rather than up to 100.
    To overrule: the `not kept` test in `Gatherer._gather`.
28. **What `slices_collected` counts for a slice job followed already** (second review,
    minor 4). Chosen: `followed`, `collecting` and `already_stored` count the followings
    the start began, so a slice job a page had followed first is counted in none of them
    (it is still in `listed`). Reason: one meaning for the three. To overrule: the
    `if not started` line in `Collector._collect_once`.
29. **A `page` of only spaces** (second review, minor 6): refused as an empty one is.
30. **A `page` holding a character that is not printable** (third review, minor 2:
    `"\u0000\u0000"` and `"​"` were taken as page ids). Chosen: a `page` is refused
    `400` `front.bad_request` unless every character is printable (Python's
    `str.isprintable`: no control, format, invisible or lone surrogate character) and one
    is not a space. Reason: the page's id is a random UUID, so an honest page never sends
    such a character, and an id made of invisible characters cannot be told apart in the
    log. To overrule: `_page` in `penguin_front.reports`.
31. **A lone surrogate in a report's other strings** (third review, minor 3). Chosen: left
    as it is, written escaped. The log's JSON is ASCII-escaped, so the line stays valid
    JSON and readable; refusing it would refuse a report for a browser's text the page
    passed on (a `detail` is the browser's own message). A `page` with one is refused, by
    decision 30.

### The review's findings declined

- **Minor 6, a per-user ceiling on reports beside the per-page limit.** Declined. The
  contract and the details file fix the limit as counted per user and `page`; a hostile
  signed-in page that changes `page` each time writes at most one line a request, each
  through the rules every request meets, and costs no more than any other short request.
  A second ceiling is a change to the contract's rule, the owner's to make. To add it: a
  second `RateLimit` keyed on the user alone in `penguin_front.reports._report`, with its
  figure in the contract.
- **Second review, minor 2: an absurd `dropped` in a gathered answer raises `highest`.**
  Declined. `dropped` is the count of lines the slice service gave up since the `after`
  asked; it has no bound in the contract and can honestly be large (a front server down
  for days beside a busy slice service), so any ceiling the front server set would be a
  figure the documents do not give and could drop honest lines. It comes from the slice
  service alone, a component on the private network, never from a browser; `highest`
  guards against one line's absurd `n`, not against a slice service that lies about its
  whole answer. To add a ceiling: a bound on `dropped` in `Gatherer._ask`, with its
  figure in the slice service's HTTP interface contract.
- **Second review, minor 5: the search for secrets skips streamed answers.** Declined for
  this batch. The details file says so; the streamed answers are the progress streams,
  whose events are the slice service's progress reports passed on field by field, and the
  sliced file, whose bytes are the slice service's output. Neither is built from the
  cookie key, a sealed cookie or an Onshape token. Searching them needs the search to wrap
  each stream's generator, which the web framework consumes after the answer handler the
  search patches; it is left as a gap, written here and in the details file.

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

From the second review, each test seen to fail first, for the finding's reason:

- **Blocking 1:** a drawing summary with `fps_worst` of `10**400` or `-10**400` is refused
  `400` naming the field, and an optional `processors` of `10**400` is dropped
  (`tests/test_reports.py`); both answered `500` before the fix (decision 26). The details
  file and decision 12 no longer say every JSON number is finite.
- **Blocking 2:** the test of an expired record at start no longer waits for the absence of
  a request. It records every `follow` the collection asks for, which happens on the
  collection's own thread before `collected` is set, and asserts that none was asked, that
  nothing is followed, and that `slices_collected` counts the slice job `left` with
  `collecting` and `already_stored` 0. Against `found in (None, "submitted", "expired")`
  it fails on every run.
- **Blocking 3:** a report whose `Content-Length` is over the limit is refused with nothing
  taken from the counted input; a body of exactly `MAX_REPORT_BYTES` is written and one byte
  more is refused with nothing taken, with and without `Content-Length`. Against
  `length > limit * 2` the first fails, and against `length > limit + 1` the boundary test
  fails.
- **Minor 1:** the details file's reports section and decision 15 say "before the front
  server's code reads it", with waitress's whole receipt of the body stated.
- **Minors 3, 4 and 6:** decisions 27, 28 and 29, each with a test.

From the third review:

- **Blocking 1:** `main` (with batch slice-5's `GET /log`) is merged into the branch, and
  decision 8, "Not done" and the owner's step no longer say the route is unbuilt.
- **Minor 1:** "Targets missed" gives the suite's count and times as measured after the
  merge.
- **Minor 2:** decision 30, with the test `test_a_failure_field_off_its_list_or_of_a_bad_form_is_refused`
  given `"\u0000\u0000"`, `"​"`, a page id with a control character inside it and a
  lone surrogate; the four answered `204` before the fix.

### Checked against the real slice service

On Fri 11-27 at 21:12 Pacific, the slice service from the merged tree (no Orca, no slice asked for) and the front server
ran side by side on two ports above 20000 with the folder buckets in a scratch folder.
Within the minute the slice service's `slice_service_started` line, `n` 1, was in the log
bucket's minute file with component `slice` and no group, and the cursor read
`{"format": 1, "process": "p6b04013b", "after": 1}`. After the slice service was stopped
and started again, the front server wrote `slice_log_process_changed` (`previous`
`p6b04013b`, `process` `pdd0b8fef`) and the cursor moved to the new process. The
reviewer's own run of the same check, with a slice job, saw that job's lines carry its
group. This is a check by hand, not a test: the front server's suite depends only on the
contracts, never on the slice service's code, and the joined suite (item 20) is where the
two run together.

### The third review's findings declined

- **Minor 3, a lone surrogate in a report's `detail`.** Declined, as decision 31 says: it
  is written escaped and the line stays valid JSON.
- **Minor 4, the first `load` line's `threads_in_use` of 65.** Declined for this batch: it
  is batch front-4's `Load`, which this batch does not change. Left for whoever next
  changes the load line.
- **Minor 5, a wrong method answering `404` `front.no_such_request`.** Declined: the app
  answers every wrong method this way, as the reviewer says, and a `405` would be a new
  error report for every route, beyond this batch.

## Targets missed

- The fast suite now takes 7 to 8 s on one worker and 4.6 s on two (1,047 tests after the
  third review's fixes and the merge of `main`, on a machine shared with three other
  builds), against the 3.8 s and 2.7 s measured on 776 tests before this batch. It still "finishes in seconds"; the search for secrets after
  each test and the running-server tests account for the rise. Not measured apart.
- The third review's fixes (decisions 30 and 31, the record's account of the slice
  service's `GET /log`, the merge of `main`) were merged without a further review: that
  was the last review round.

## Not done

- **The previous release's page and the previous slice service's stand-in against the new
  front server** (item 19): they apply from the second release on. No release has been
  made, so there is no previous page or stand-in to keep.
- **Item 20, the joined suite:** a later batch, once the wizard's steps exist.
- **The restart table's three rows of phase 5** (a print, a silent daemon, a pairing code):
  with the relay.

The gathering was checked by hand against the real slice service once batch slice-5 built
its `GET /log` (merged into this branch from `main`; no Orca was needed, since no slice
was asked for): see "Checked against the real slice service" below.

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
- A gathered line: with the slice service and the front server started as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says, within a minute the minute's file under
  `/var/tmp/penguin-front/log/<year>/<month>/<day>/` holds the slice service's lines,
  component `slice`, those of a slice job with its `group`, and
  `/var/tmp/penguin-front/state/log-cursor/slice.json` says where the gathering stopped
  (`process` and `after`). Restarting the slice service writes one
  `slice_log_process_changed` line and the cursor moves to the new process.
- A report: `curl -c jar http://127.0.0.1:8600/signin`, then
  `curl -b jar -H 'X-PenguinSlicer-Group: dev-group' --data-binary @contracts/examples/wizard-front/report-failure-request.json http://127.0.0.1:8600/api/reports/failure`
  answers `204`, and standard output shows a `failure_report` line, component `wizard`.
