# Batch together-1-front-slice-seam: the record

The batch joins the front server and the slice service for the first time, without the
wizard: a review of the seam between them, written up in
[the record of the seam](../seam-front-slice.md); the joined suite's project, `together/`
([its README](../../../../together/README.md)), with the two servers run together and driven
over HTTP as the wizard drives them; one walk with the real Orca; and the fixes the joining
called for. It builds the first half of item 20 of the front server's phase 2 list
([By phase](../../../../front/README-details.md#phase-2-one-machine-no-onshape-no-printer)).
Written Fri 2026-11-27, Pacific time.

## Decisions made

1. **One walk with the real Orca, as a target of its own.** The details file puts nothing
   with the real Orca in the joined suite; the owner agreed to this addition. Chosen:
   `make -C together test-orca`, outside `make -C together test`, which installs the pinned
   Orca and runs `together/tests_orca/` under `flock /var/tmp/penguin-locks/real-orca.lock`
   inside the target itself, so it cannot be run without the lock. Its plate is the clamp
   plate laid flat, the smallest real plate that is a real part; it slices in about a
   second. To overrule: the target `test-orca` in `together/Makefile`.
2. **The start commands are run from each component's environment, not through `uv run`.**
   The details file gives `uv run --project slice python -m penguin_slice serve`. Chosen:
   `slice/.venv/bin/python -m penguin_slice serve …` and the same for the front server.
   Reason: a stop is a `SIGTERM` to the server, and the slice service reads a second one as
   a second stop; a wrapper that passes signals on, or a signal sent to the whole group,
   would turn one stop into two. CLAUDE.md's gotcha on bounding the right process says the
   same of timeouts. To overrule: `argv` in `SliceService.start` and `FrontServer.start`.
3. **A restarted slice service listens on the port its first process was given.** The
   details file says each listens on a port the system chooses and is silent on a restart.
   Chosen: the first start takes `--port 0` and reads the port from the
   `slice_service_started` line; a restart asks for the same port. Reason: the front server
   was given one address at its start, as hosted it is given one private address. To
   overrule: `SliceService.start`.
4. **The front server's page files are a one-line page the suite writes.** The front
   server will not start without `index.html` holding the version's placeholder, and the
   wizard's build is another batch's. Chosen: a folder per test holding only that page. The
   browser half replaces it with `wizard/dist/`. To overrule: `page_files` in
   `joined/servers.py`.
5. **The front server is given a cookie key.** As the details file says of a test of the
   restart table; it lets a front server's restart keep the page signed in. To overrule:
   `FrontServer.cookie_key`.
6. **The stand-in Orca's mode is read from a file at each slice.** The details file names
   one wrapper running `fake_orca.py`. Chosen: the wrapper reads the mode from a file beside
   it, so a test chooses how the next slice goes (`ok`, `empty_layers`, `gate`) with no
   restart of the slice service. A slice is held running by the mode `gate`, and released by
   writing one byte into the FIFO Orca made, whose opening waits for Orca to read it: an
   event, behind the backstop. To overrule: `write_fake_orca` and `release_orca`.
7. **How a test knows the front server has gathered the slice service's lines.** The front
   server gathers at its start and then once a minute, and writes no line of its own for an
   ordinary gathering. Chosen: the test starts a front server again and waits for the slice
   service's own request line on its standard error (`"GET /log?after=`), then stops the
   front server, whose stop writes what it gathered. Reason: an event, where waiting for
   the next minute would be a wait of a duration. Should the slice service's web server stop
   writing request lines, the test fails at its backstop, naming the line. To overrule:
   `test_the_gathered_log_holds_the_slice_services_lines_in_their_group`.
8. **A part the part store has forgotten is reached by restarting the slice service.** The
   part store also forgets a part two hours unused and the least recently used past its
   limit, whose least is 8 MB; the eight real parts make 7.1 MB, and two hours cannot be
   waited for. Chosen: the restart, one of the four causes the contract lists; the other two
   are the slice service's own suite's. To overrule: a test that uploads generated parts past
   8 MB with `PENGUIN_SLICE_PART_STORE_MAX_MB=8` (the fixture takes `slice_env`).
9. **Mismatch 1, the report in the `202`: "latest".** The contracts said "first"; both
   sides build "latest". Chosen: the contracts' and the slice service's details' words made
   to say "the latest report when the answer is made: the first unless the slice has
   already started", no name or shape changed; the stand-in can start a slice at once.
   Reason: the contract's own field says latest, it is truer to the page, and changing the
   slice service would change several of its tests that read a later report from the `202`
   (`slice/tests/test_web.py`, the stops during the write and the repeats). To overrule: snapshot the
   first report in `JobPool.submit` and answer it from `web._queue`, and put the contracts'
   words back.
10. **Mismatch 2, seconds with a fraction.** The wizard's contract's rule of whole seconds
    now excepts a progress report's `elapsed_s` and `expected_s`, passed unchanged. Reason:
    the rule serves the page's counting of `expires_in_s`, and rounding a passed report would
    break "unchanged". To overrule: round in the slice service's `_snapshot` and drop the
    exception.
11. **Mismatches 3 and 4 are fixed in the stand-in only.** The slice service follows the
    contract; the stand-in did not. Each fix has a stand-in test seen to fail first.
12. **Mismatch 6: the slice service waits for the answers it is writing before it exits,
    at most 10 seconds (`STOP_ANSWERS_S`, *proposed*), counted at its web server's request
    handler.** The documents are silent on how. Counting at the WSGI app's `close` was tried
    first and missed answers whose client had gone, which the development server never
    closes; the request handler's `handle` ends every time. Ten seconds: every answer after
    the drain is short, since every slice job has ended, and a deploy's stop time is not yet
    known. Answers still being written at the bound are cut and named in a line
    `slice_service_answers_cut`. To overrule: `InFlight` and `STOP_ANSWERS_S` in
    `slice/src/penguin_slice/__main__.py`.
13. **Mismatch 7: the front server takes the stop signals before it writes its `start`
    line.** The documents say a stop writes the `stop` line and the gathered log, and are
    silent on a stop during the start. To overrule: `server.serve`.
14. **Mismatch 5 is left for the owner,** with its options and a recommendation in
    [the record of the seam](../seam-front-slice.md#a-choice-for-the-owner-the-slice-services-lines-at-a-deploy).
    Reason: either fix moves a figure or a stop rule another builder relies on, and costs
    deploy time not yet measured.
15. **Two servers of its own for each test.** Chosen over servers shared by the session, so
    that each test starts from empty folders and the suite passes in any order; each test
    costs about half a second to start them.
16. **The backstops.** 60 seconds for each event (`joined/waits.py`); 180 seconds for one
    test (pytest-timeout); 900 seconds and 4 GB of address space for the run, on pytest's
    own process, which the servers inherit. The real-Orca walk keeps the time limit and
    drops the address-space one, since the slice service sets Orca's own ceiling.
17. **The suite runs one test at a time.** Each test starts two servers; the machine's
    rule allows two workers, and the run takes 37 to 42 seconds serially.
18. **A test of the front server's fast suite that failed about one run in eight was fixed
    at its cause.** `test_a_finished_slice_job_followed_already_is_counted_in_no_kind[stored]`
    in `front/tests/test_collecting.py` began its following on a slice job already done with
    its record stored, which can end before the collection asks to follow it, so that the
    collection began one of its own and counted it. It now begins the following on a running
    slice job and makes it done once the collection has run; thirty runs in a row passed.
    Not this batch's code, but its fast suite had to pass twice.
19. **Two rows of "The front server restarts" are in the suite too.** Not asked for; they
    are the only way to exercise `GET /slices`, its `file_on_disk` and its `ended_at` across
    the seam.

## Mismatches between the two sides

Each in full, with its evidence, in [the record of the seam](../seam-front-slice.md#mismatches).

1. **The report in the `202` to a submission.** The contracts and the slice service's
   details said the first report, `queued` with `ahead`; the slice service answers its
   latest, `running` when the slice started at once, and the front server passes the latest
   it knows; the stand-in answered only the first. Fixed in the contracts' words and the
   slice service's details; the stand-in can answer a later one.
2. **Seconds with a fraction.** The wizard's contract said every `_s` field is whole
   seconds; the slice service's reports carry `elapsed_s` to the millisecond, passed
   unchanged. Fixed in the contracts' words.
3. **Parts no instance names.** The stand-in listed them as missing; the slice service, as
   the contract says, reads only the parts an instance names. Fixed in the stand-in.
4. **The repeat and the stopping answer before the form.** The stand-in read the plate's
   form first; the slice service answers both before any check, as the contract says. Fixed
   in the stand-in.
5. **The slice service's last lines before it stops never reach the log bucket.** The front
   server gathers once a minute and the slice service exits without waiting to be gathered,
   so a deploy of the slice container loses up to a minute of its lines from the bucket.
   Not fixed: the owner's choice.
6. **A stopping slice service exited before answering the DELETE that drained it.** The
   contract says every request is answered until the process exits; the slice service's stop
   woke inside that `DELETE`'s handler and the process exited before the answer was written,
   so the front server held the page's `done` and asked again until a new slice service
   answered. Fixed in the slice service: it waits, at most 10 s, for the answers it is
   writing.
7. **A stop at the moment the front server said it listened ended it without its stop line
   or its gathered log.** The front server wrote its `start` line before taking the stop
   signals. Fixed in the front server: the signals are taken first.

## Targets missed

1. **A deploy of the slice container loses up to 60 seconds of the slice service's lines
   from the log bucket** (mismatch 5), where the architecture loses lines only at a crash.
2. **A front server's stop takes 5.1 seconds while it follows a quiet slice.** No phase 2
   figure is set for it; phase 3's stopping item will set one against Railway's stop time.

## Not done

1. **The browser half of the joined suite:** driving the wizard in Chromium over the same
   two servers, through the phase's "Done when" and the restart rows that need a page. The
   wizard's steps are still being built; it is a later batch's.
2. **`slice.output_too_large` and `front.sliced_file_too_large` across the seam.** Neither
   the stand-in Orca nor a small real plate makes a sliced file over 50 MB; each side's own
   suite covers its half.
3. **The least-recently-used and two-hour forgetting of a part, joined** (decision 8).
4. **The fix of mismatch 5,** left for the owner.

## For the owner to look at

- `make -C together install`, then `make -C together test`: the joined suite, 37 to 42
  seconds on an aarch64 Linux machine. Each server's output is kept in `slice.log` and
  `front.log` in the test's temporary folder.
- `make -C together test-orca`: the walk with the real Orca, under the real-Orca lock.
- [The record of the seam](../seam-front-slice.md), and in it
  [the choice about the slice service's lines at a deploy](../seam-front-slice.md#a-choice-for-the-owner-the-slice-services-lines-at-a-deploy).
