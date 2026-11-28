# Batch slice-5-stop-log-restarts: the stop, the sentences, the log and the restart table

The builder's record of items 14, 15, 16 and 18 of
[the slice service's details, Phase 2](../../../../slice/README-details.md#phase-2-one-machine),
of what was left of item 17, of the real-Orca finding of
[slice-1](slice-1-parts-arrive.md) (a part laid on a hull face that is no face of the part),
and of a read of items 1 to 18 against the code and the earlier records. What was built is
described in [Asked to stop](../../../../slice/README-details.md#asked-to-stop), "A new plate"
under [Error codes](../../../../slice/README-details.md#error-codes), "The log the front
server collects" under
[Progress, cancellation and cleanup](../../../../slice/README-details.md#progress-cancellation-and-cleanup),
[The slice service's half of each row of the restart table](../../../../slice/README-details.md#the-slice-services-half-of-each-row-of-the-restart-table)
and `slice.rests_on_an_edge` in [Error codes](../../../../slice/README-details.md#error-codes),
and in [the guide](../../../../slice/README.md).

## Decisions made

1. **How `serve` keeps answering while it stops.** The details file says the HTTP interface
   keeps answering until the sliced file is collected; as built, Flask's `app.run` held the
   main thread and a signal ended it. Chosen: werkzeug's own threaded server
   (`werkzeug.serving.make_server`, which `app.run` uses inside) on a thread of its own; the
   signal handler only puts a stop into a `queue.SimpleQueue` (the one queue Python makes
   safe to put into from a signal handler, so a handler can never deadlock on a lock the
   main thread holds), and `__main__.run_until_stopped` acts on it in the main thread. A
   second thread waits on the pool's drain and puts its own event in the same queue, so the
   main thread waits on one thing. `__main__.py` may now import werkzeug, as `web.py` does
   (`tests/test_independence.py`). To overrule: any server that can be shut down from
   another thread; only `serve` and `tests/test_cli.py` change.
2. **What holds the stop.** The details file says `serve` exits "once no done slice job still
   holds a sliced file". Chosen literally: every done slice job whose file the front server
   has not deleted holds the stop, the ones that finished before the stop too, until the file
   is collected or the record expires (two hours). Reason: such a file is lost with the
   process, and the front server collects every one it has not stored. Consequence by hand:
   a slice service run with no front server waits for the second Ctrl-C once it has sliced
   anything. To overrule: count only the slice job that was running at the stop, in
   `JobPool._drained`.
3. **A stopping slice service answers before the checks.** The contract says `POST /slices`
   answers `slice.stopping` "from the moment" it is asked to stop, a repeat excepted; silent on
   a plate the checks would refuse. Chosen: after the repeat, before any check, so a plate
   with a placement fault is answered `slice.stopping` too. Reason: the page submits again to
   the new slice service, which checks it; checking it twice gains nothing. A stop that
   arrives during the checks is caught under the pool's lock (`jobs.Stopping`), and one that
   meets the executor already shut down by a second stop ends that slice job with
   `shutdown` and answers `slice.stopping` (this closes the race the record of
   [slice-3](slice-3-job-life.md) left under Not done, which answered 500). To overrule:
   drop `_stopping()` from the route.
4. **The words of `slice.stopping`.** Fixed by
   [the contract's example](../../../../contracts/examples/slice-http/stopping.json), word for
   word: "The slicer is restarting.", "Your plate will be sliced as soon as the slicer is
   back.", stage `queued`, retryable, no action, and the example's detail.
5. **The log lines of the stop.** The documents ask for a line for every transition; silent on
   the stop's own. Chosen: `slice_service_started` (host, the port it listens on, which with
   `--port 0` the system chooses, and the process id), `slice_service_stopping` with `stop` 1
   (the waiting slice jobs ended, whether it was drained at once) and with `stop` 2, and
   `slice_service_stopped` (`how`, `drained` or `second_stop`, and `files_lost`, the done
   slice jobs whose sliced file goes with the process). An address `serve` cannot listen on
   exits 1 with "cannot listen on <host>:<port>: ..." (as built, Flask's own message and
   exit). The start line carries no version: the slice service has none yet.
6. **"A new plate": which sentences.** The details file names five codes. Chosen: those five
   with both their sentences (too many instances and too many parts say it in the message as
   well as the remedy) and the supports-on remedy of two instances too close, and
   `slice.output_too_large`, which already said "a new plate"; the test holds exactly these
   six codes' remedies to "a new plate" and every report to no "second plate". The upstream
   check's own expectation (`test_orca_names_the_pair_whose_supports_meet`) was found to
   still say "second plate" by the run at the end, and was corrected.
7. **The log's buffer and its names.** `LOG_BUFFER_LINES` was *proposed*; chosen: module
   `log_buffer.py`, class `LogBuffer`, `LOG_BUFFER_LINES` 10,000 and `LOG_ANSWER_LINES`
   1,000 (the contract's figures). The buffer is the sink `create_app` gives the pool and the
   routes, through `SafeLog`, and passes every line on to the sink it was made with (stderr
   under `serve`), so stderr lines now carry `n`, `time` and `component` too. `n`, `time` and
   `component` come first in each line and a caller's own field of those names is dropped.
   A value JSON cannot hold is kept as its words (as `serve`'s stderr did). The process id is
   `p` and 8 random hexadecimal characters, as the example's.
8. **`GET /log`'s `after`.** The contract says it is a whole number; silent on one left out
   or malformed. Chosen: left out is 0; anything but 1 to 18 ASCII digits (`-1`, `1.5`, `²`,
   empty) is `400` `slice.bad_request` ("The slicer was asked for its log after a line that is
   not a whole number."). The route writes no log line of its own refusal: refusals of routes
   other than the two that take a body are phase 3's (item 9 of "Phase 3").
9. **`dropped`.** "How many lines after `n` were dropped from the buffer": chosen as the lines
   numbered after `after` that the buffer no longer holds, so a front server that is
   behind by 12 lines on a buffer of 10 is told 2, and one that is not behind is told 0.
10. **The user key on every line.** Every line about a request already carried the request's
    user key (cut to 200 characters); the one line about a slice job that lacked its `job`,
    `slice_cleanup_error`, now carries it. The sweeper's and the stop's own lines concern no
    user and carry none.
11. **The restart in the tests of item 18.** The architecture's rows are about a restart of
    the container. Chosen: in `tests/test_restarts.py` the old slice service process is its
    app with its pool shut down (as the process's end does), and the new one a new app on the
    same work folder, in the same test process; the real `serve` and its signals are tested
    in `tests/test_serve_stop.py`. The table's last row (a print) has no half in the slice
    service; the test file says so. To overrule: restart a `serve` subprocess in each row.
12. **The fake Orca's new mode.** A stop while Orca runs must end that slice `done`, so the
    fake Orca must run until the test lets it finish. Chosen: mode `gate`, which makes a FIFO
    in its output folder before its first progress message and blocks on it until the test
    writes a byte (`helpers.open_gate`): a wait on an event, not a duration.
13. **`serve` tested in the test's own process.** Python runs signal handlers only in the
    main thread, so `tests/test_serve_stop.py` runs `serve` in the test's main thread on a
    loopback port the system chooses, and a driver thread makes the requests and sends the
    signals to its own process; outside `serve` the test makes SIGTERM do nothing, so a stop
    that arrives late never ends a test worker (it did once, during a mutation).
14. **The cause of the refused hull-face pose, and what the slice service does about it.**
    The guide requires an instance laid on any face of its part's hull to slice; the earlier
    record found the contract example's fourth instance refused. Found with the real Orca and
    its source: the bracket on that face touches the plate along two edges, its first layer
    is two strips about 0.2 mm wide, and the pinned Orca throws "One object has an empty first
    layer and can't be printed. Please Cut the bottom or enable supports." inside a
    `SlicingErrors` whose text, "Errors", is all it prints, so the reason reaches no file. The
    slice service is not at fault: the plate it writes puts the four lowest vertices exactly
    on the plate, and the same rotation code places a part on its own face within 0.6 mm. The
    placement check, the wizard's and the shared plates accept the pose, and changing that
    would change the contract's shared plates, which expect `rotation-pass.json` accepted.
    Chosen: keep the check, and explain Orca's failure: on a -100 failure with no reason the
    service recognises, the slice service reads each part again and, when an instance's own
    faces on the plate add up to less than 0.01 mm² (`REST_AREA_MM2`, vertices within
    0.001 mm of the lowest point), answers a new code, `slice.rests_on_an_edge`, naming the
    first such instance, listing every one in the detail, with the remedy "Lay the part on
    one of its own flat faces, or turn on supports with a raft, and slice again." ("or add a
    raft" with supports already on) and the action `choose_orientation`, which gives the
    wizard its Back to Layout. A new code, not `slice.orca_failed` with other words, so the
    log counts it apart; the error report's contract allows a new code, and a user interface
    that does not know it shows its sentences and acts on its action. The guide's rule "no
    check is added for a part whose first layer is empty" is about the part (a needle); this
    looks at the pose, and only after Orca has refused. To overrule: drop `_explain_an_edge`
    and the code; or refuse the pose before Orca, which changes the shared plates and the
    wizard's check in one commit. The rule as first built (the face area alone) blamed curved
    parts that print; decision 19 replaces it.
15. **The code is not added to the contract's table of codes a user interface acts on.** That
    table says what the wizard does; adding a row would oblige the wizard's builder and its
    tests in the same commit. The action carries the right behaviour meanwhile. To overrule:
    add `slice.rests_on_an_edge` to "Codes a user interface acts on" in
    [the error report's contract](../../../../contracts/error-report.md) with "Back to Layout".
16. **The plate configuration contract's phase 2 sections stay apart from its main text.**
    The contract says "This file holds two things, kept apart"; nothing in it, in
    [the contracts' rules](../../../../contracts/README.md) or in the plan says the two are to
    be merged in phase 2. So they are left as they are. To overrule: fold "To be built" into
    the body and retire the form before phase 2 and its example, in one commit with the
    tests that send the old example.
17. **What was left of item 17.** Checked, not built: the shared plates already go through
    `POST /parts` and `POST /slices` exactly as they are, and the rotation plates are placed
    by the slice service's own rotation (`tests/test_placement_plates.py`, since batch
    slice-1). The details file and the guide said so, except one sentence of the guide that
    still said the plates' supports setting was turned on the way in; corrected.
18. **The contract's phase 2 example.** Its fourth instance is a pose no printer could print
    as the example asks for it (supports off, no raft): the bracket's first layer would be two
    lines on the plate. It prints with supports and a raft. Left unchanged in the contract, as
    the task asked; the details file says why the upstream check slices a bracket on a face of
    its own instead.

### After the review

19. **Which instance rests on no face of its own (the review's blocking finding).** The
    review found that the area of faces lying on the plate is 0 for a tessellated ball and
    for a tube lying on a line of vertices, both of which print, so a ball beside the block on
    a stem was named in place of the block. The documents say only that the service never
    states a reason the log does not give. Chosen: an instance is named only when both hold:
    its faces on the plate add up to under 0.01 mm², and its section at the middle of the
    first layer (`mesh.first_layer_section`, at half the process's
    `initial_layer_print_height`) is empty once shrunk by half the process's
    `initial_layer_line_width`, so no line of the first layer fits in it. Both values come
    from the slice job's process with its overrides; one that is no length in millimetres (0,
    a percentage) is taken as the default process's, 0.3 mm and 0.62 mm. Measured at 0.15 mm
    (`mesh.first_layer_section`): the bracket on its hull face is at most 0.33 mm across, a
    box on an edge 0.30 mm, a ball of radius 20 mm 4.6 mm, a tube of radius 10 mm on a vertex
    line 3.3 mm. Why both conditions and not the width alone: the width alone would also name
    the block on a stem 0.4 mm across and the needle, which stand on a face, under a sentence
    ("touches the plate only along an edge or at a point") that would be false for them; the
    guide keeps those parts on the general sentence. To overrule: drop the face-area
    condition and give thin parts their own code and sentence.
20. **Orca's own warnings take precedence.** Also from the review: when Orca's debug log warns
    of instances and none of them is one the slice service would name, the report stays
    `slice.orca_failed` with Orca's warnings. The real Orca warns "floating regions" of the
    bracket on its hull face itself (with supports off), so the explanation still fires there;
    with tree supports on it warns of nothing and the explanation fires too. Cost: a plate
    where one instance rests on an edge and Orca warns only of another loses the explanation
    and gets the general sentence with Orca's warning. To overrule: drop `_logged_objects`'
    test in `_explain_an_edge`.
21. **`GET /log`'s 400 in the contract (minor finding 4).** The contract's table of codes now
    lists "an `after` on `GET /log` that is not a whole number" under `slice.bad_request`, and
    its request paragraph says so. Only the When column grew; no name or shape changed.
22. **The two surviving mutations of the log's buffer and the weak proof of the drain (minor
    findings 1 to 3).** Tests added: exactly 1,000 lines answer `more` false; a caller's own
    `n`, `time` and `component` are dropped; and the serve test of the stop now starts no
    sweeper and waits for `slice_service_stopped` after the deletion (behind `FAILSAFE_S`), so
    with `delete_file`'s `notify_all` removed it fails in 10 s instead of passing 20 s late.
    Each test was seen to fail under its mutation.
23. **Findings declined.** Minor 5 (`slice.rests_on_an_edge` not in "Codes a user interface
    acts on"): declined, decision 15 stands. The finding says the wizard loses the Slice again
    it offers for `slice.orca_failed`, but slicing the same plate again fails the same way,
    and the error report's rules say a remedy never proposes an action that cannot help; the
    report's `action`, `choose_orientation`, gives the wizard its Back to Layout. Minor 6 (the
    plate configuration contract's stale opening): declined, as decision 16 and the task say;
    not of this batch. Minor 7 (not every test seen to fail first): nothing to change; Targets
    missed 2 discloses it, and every test of the review's fixes was seen to fail first.

### After the second review

24. **A stop ends every waiting slice job (blocking finding 1).** The documents say a stop
    "ends each waiting slice job early"; no test held more than one. Added
    `test_every_waiting_slice_job_ends_with_shutdown_and_none_runs_after_the_running_one`:
    `MAX_QUEUED` (2) waiting slice jobs behind the running one, `stop()` returns both, both
    end `cancelled` with `shutdown`, and the worker is started for the running one only.
    Seen to fail under the reviewer's mutation (`[...][:1]`); the code was right, so only the
    test changed.
25. **The first-layer rule's figures (blocking finding 2).** Added to `TestRestsOnAnEdge`,
    through the fake Orca's general failure: the box on its edge with a 0.4 mm line and with
    a 0.4 mm first layer, named; a process file of the test's own, with no overrides, whose
    first layer is 0.25 mm line (not named), 0.8 mm high (not named) or 0.9 mm line under
    0.8 mm (named); the contract example's bracket on its hull face under the default
    process, named. The process file is swapped into the read plate configuration with
    `dataclasses.replace`, since the catalog holds no process whose first layer differs from
    the default this way. Each of the reviewer's three mutations, made alone, fails 4, 4 and
    2 of these tests; the code was right, so only the tests changed. The details file's
    sentence on the fast suite now lists them.
26. **Item 10's paragraph (minor finding 1).** Now says what decision 2 and "Asked to stop"
    say: the stop waits until no done slice job holds an uncollected sliced file, the running
    one's and those done before the stop alike, or until each such record expires.
27. **The `_drained` term `r["result"] is None` (minor finding 3).** Kept, and a test added
    (`test_a_done_slice_job_with_no_result_holds_no_file_and_never_holds_the_stop`), seen to
    fail with the term removed: `delete_file` answers such a job "deleted" without marking
    it, so without the term a done slice job with no result would hold the stop until its
    record expired.
28. **Finding declined: minor finding 2 (`LOGGED_OBJECT_RE` and a name holding " has ").** The
    case cannot arise. The names in Orca's warnings are the instances' labels, which
    `plate.instance_labels` builds from `plate.sanitize_part_name`: letters, digits, `-` and
    `_`, every other character `_`, then " #n". A part named "Arm has holes" is labelled
    `Arm_has_holes #1`, so the lazy match stops at the one " has " after the label. A test
    pins it (`test_orcas_debug_log_naming_an_instance_whose_name_holds_has_is_explained`,
    which names `Arm_has_holes #1`), and a comment by the expression says why it is whole.

## Targets missed

1. **"An instance laid on any face of its part's convex hull" does not always slice.** A hull
   face that bridges a hollow of the part, so that the part touches the plate only along
   edges or at points, is refused by the pinned Orca with supports off and with supports on
   (tree or normal), for an empty first layer; it slices with supports and a raft of two
   layers. Evidence, with the real Orca 2.4.2 under the lock, the contract example's bracket
   alone at (170, 160): `-100` "Failed slicing the model", stderr "Errors", the debug log's
   "It seems object Bracket #1 has floating regions" with supports off; the cross-section
   0.1 mm above the plate is two strips 12 mm long and about 0.2 mm wide (perimeter
   48.87 mm); lowering the part 0.2 or 0.6 mm into the plate changes nothing, since Orca
   puts each object's lowest point on the plate; a raft alone gives `slice.empty_layers`
   between 0.5 and 1 mm; supports with a raft slice it in 154 layers. Pinned by
   `test_a_part_resting_on_an_edge_has_no_first_layer_unless_supported_on_a_raft`. The user
   is now told which instance and what to do (`slice.rests_on_an_edge`), but the plate is
   still refused. The wizard's "lay on face" offers such hull faces
   ([the wizard's guide](../../../../wizard/README.md#laying-an-instance-on-a-face)); whether it
   should is the wizard's to decide.
2. **Not every test was seen to fail before its code was written.** The tests of item 15, of
   the pool's stop and of the HTTP interface's stop, of `GET /log`'s route and of
   `contact_area_mm2` and `slice.rests_on_an_edge` were run and seen to fail first. The tests
   of `serve` (`tests/test_cli.py`, `tests/test_serve_stop.py`) were written with the code
   and then run against the code as it was before (they fail: the first in 0.2 s), the
   buffer's own tests and the race of the executor shut down were written first but run
   only with their code, and item 18's tests pass on the code as built, since items 1 to 14
   already do what they assert. In their place, checks were broken by hand: the waiting slice
   jobs ended with `requested` instead of `shutdown` (4 tests fail, item 18's among them);
   the stopping answer before the checks removed (1 fails); the drain made to ignore an
   uncollected sliced file (6 fail).
3. **The real-Orca suite needed a second run.** Its first run at the end failed one test,
   `test_orca_names_the_pair_whose_supports_meet`, which still expected "second plate"
   (decision 6); after the fix it passed whole: 63 tests in 121 s. After the review's fixes
   and the merge of `main` it passed whole at the first run: 64 tests in 157 s.

## Not done

1. **The wizard's and the front server's halves** of the restart table, and the joined suite:
   their builders' batches, as the architecture says.
2. **The restart measured on Railway** (how long a stopping container is given, whether the
   new one starts first, how long a new slice service takes to start): phase 3, under the
   guide's Unmeasured.
3. **The plate configuration contract's two halves merged:** not asked of phase 2 (decision
   16).
4. **The older words of the slice service's sentences** ("ask a mentor", "the print
   server"): known future work, as the details file says; this batch's new sentences use
   neither.

Read against items 1 to 18 and the records of slice-0 to slice-4, nothing else of phase 2
fell between batches: slice-0's Not done (the plates through `POST /slices`, the rotation
plates by the service's own rotation) was done by slice-1; slice-1's (items 7, 5, 10, 11,
16, and the contract's halves) by slice-2 to slice-4, this batch, and decision 16; slice-3's
(items 10 and 14, and the race of a submission at the stop) by slice-4 and this batch
(decision 3).

## For the owner to look at

- The stop by hand, with Orca installed (`make -C slice install`): start
  `slice/.venv/bin/python -m penguin_slice serve --work /var/tmp/penguin-slice --port 0`,
  read the port from its first stderr line (`slice_service_started`), upload a part and
  submit a plate with the curl lines of [Use](../../../../slice/README-details.md#use), press
  Ctrl-C while it slices: it goes on, a new `POST /slices` answers `slice.stopping`, and
  `serve` waits; `curl -s -X DELETE -H 'X-Penguin-User-Key: me' .../slices/<job>/file` lets it
  exit, or a second Ctrl-C ends it at once.
- The log: `curl -s 'http://127.0.0.1:<port>/log?after=0'` on a running slice service.
- The refused hull-face pose and its explanation:
  `flock /var/tmp/penguin-locks/real-orca.lock slice/.venv/bin/python -m pytest -s -p no:randomly slice/tests_orca/test_orca.py -k resting_on_an_edge`
  prints the three error reports and the slice with supports and a raft; `-k ball_that_prints`
  prints the ball alone (done) and beside the block on a stem (`slice.orca_failed`, the
  block's warning, the ball named nowhere).
- The fast suite and its branch coverage: `make -C slice test` (1,669 tests) and
  `make -C slice coverage` (100%).
