# The seam between the front server and the slice service

The first joining of the two components, batch together-1-front-slice-seam, Fri 2026-11-27
(Pacific time). Until then the front server had been tested only against its stand-in for
the slice service (`front/tests/slice_standin.py`) and the slice service only through its
own test client. This file records where the two sides, or a side and its stand-in, read
the same words of a contract differently, which side departs from the contract, the
evidence, and what was done about it; then what the joining now exercises for real and what
only a stand-in still exercises.

The contracts read beside the code on both sides:
[the slice service's HTTP interface](../../../contracts/slice-http-interface.md),
[the plate configuration](../../../contracts/plate-configuration.md),
[the table of settings](../../../contracts/settings-table.md),
[the sliced file](../../../contracts/sliced-file.md),
[the error report](../../../contracts/error-report.md) and
[the progress report](../../../contracts/progress-report.md). The code read: the slice
service's routes (`slice/src/penguin_slice/web.py`, `jobs.py`, `service.py`,
`__main__.py`), the front server's client and every user of it
(`front/src/penguin_front/slice_client.py`, `slices.py`, `parts.py`, `asking.py`,
`following.py`, `collecting.py`, `gathering.py`, `settings_table.py`), and the stand-in.
The joined suite that ran them together is [together/](../../../together/README.md); the
batch's record is [records/together-1-front-slice-seam.md](records/together-1-front-slice-seam.md).

## Short answer

The two sides agree on every name, status, code, header and shape that passes between
them. Joined, every request of the HTTP interface the front server uses was answered as the
front server expects, through a whole walk, failures, repeats, replacement, a stop and two
kinds of restart. Eight mismatches were found. Two of them, both about stopping, could
leave a slice unfinished for the user; the rest broke no request:

| # | What | Which side departs | Done |
|---|---|---|---|
| 1 | The report in the `202` to a submission: "first" or "latest" | The contracts' words; both sides build "latest", the stand-in "first" | Contracts and the slice service's details say "latest"; the stand-in can answer a later one |
| 2 | `elapsed_s` with a fraction where the wizard's contract says whole seconds | The wizard's contract's general rule | The rule excepts progress reports, which pass unchanged |
| 3 | Parts no instance names, listed missing | The stand-in | Fixed in the stand-in |
| 4 | The repeat and the stopping answer before the plate's form | The stand-in | Fixed in the stand-in |
| 5 | The slice service's last lines before it stops never reach the log bucket | Neither contract; the architecture's promise | Not fixed: a choice for the owner, below |
| 6 | A stopping slice service exits before answering the DELETE that drained it | The slice service | Fixed in the slice service |
| 7 | A stop sent the moment the front server says it listens ends it without its stop line or its gathered log | The front server | Fixed in the front server |
| 8 | While stopping, a body that cannot be read as JSON: `400` or `503` | The stand-in; the contract's words were silent | Fixed in the stand-in; the contract's words now say it |

## Mismatches

### 1. The report in the `202` to a submission

**The words.** [The slice service's HTTP interface](../../../contracts/slice-http-interface.md#post-slices--submit-a-plate-configuration)
gave `progress` as "the slice job's latest progress report: for a new slice job its first,
`queued` with `ahead`"; [the wizard's contract](../../../contracts/wizard-front-server.md#post-apislices)
said "`progress` is the slice job's first progress report"; the slice service's details
file said "the first progress report (`progress`, `queued` with `ahead`)".

**The two sides.** The slice service reads its pool's latest report after queueing
(`web._queue`: `pool.get(job_id)` after `pool.submit`). A slice job with nothing ahead of it
is started by the pool's worker thread at once, so the answer often carries the second
report, `running` at `building_plate`, with no `ahead`. The slice service's own restart
test allows it (`slice/tests/test_restarts.py`: `state in ("queued", "running")`). The front
server passes the latest report it knows (`slices.submit` through
`Follower.as_pages_see`, which prefers its following's report when that is later). The
stand-in always answered the first report, so the front server's suite never saw a
`running` `202`.

**Evidence.** The joined walk's first run: `POST /api/slices` answered `progress.state`
`running` for a plate alone on the slice service.

**Done.** The contract's own field definition says "latest", both sides build it, and the
wizard treats the report as any report, so the words were made to agree with the code, with
no name or shape changed: [the HTTP interface](../../../contracts/slice-http-interface.md#post-slices--submit-a-plate-configuration),
[the wizard's contract](../../../contracts/wizard-front-server.md#post-apislices) and
[the slice service's details](../../../slice/README-details.md#the-http-interface) now say the
latest report when the answer is made, the first unless the slice has already started. The
stand-in can now start a slice at once (`starts_at_once`), with a test of its own and a
front server test that the page is given that report.

### 2. Seconds with a fraction in a progress report

**The words.** [The wizard's contract](../../../contracts/wizard-front-server.md#answers-errors-and-times):
"A length of time is a number of whole seconds, in a field whose name ends `_s`."
[The progress report](../../../contracts/progress-report.md#fields): `elapsed_s` and
`expected_s` are numbers of seconds.

**The two sides.** The slice service writes `elapsed_s` rounded to the millisecond
(`jobs.py`: `round(…, 3)`) and `expected_s` as its estimate, a float. The front server
passes the slice service's reports to the page unchanged, as its contract requires. The
stand-in's reports carried whole numbers.

**Evidence.** The joined walk's reports carry `elapsed_s` such as `0.012`.

**Done.** The rule of whole seconds is about the front server's own fields, whose purpose
is the page counting on its own clock (`expires_in_s`); a fraction in a passed report harms
nothing. The rule now excepts a progress report's `elapsed_s` and `expected_s`, and the
progress report's contract says they may carry a fraction. The stand-in's report of a slice
started at once carries one.

### 3. Parts that no instance names

**The words.** [The plate configuration](../../../contracts/plate-configuration.md#fields-in-phase-2):
"Only parts an instance names are read."

**The two sides.** The slice service looks up only the parts its instances use
(`service.read_plate_configuration`, `if key in used`). The stand-in listed every key of
`parts` that it did not hold as missing.

**Evidence.** Reading the two; the joined test
`test_a_part_no_instance_names_is_not_read` slices a plate that lists a part never uploaded
and never placed.

**Done.** The stand-in reads only the named parts, with a test.

### 4. The repeat and the stopping answer come before the plate's form

**The words.** [Repeat and replacement](../../../contracts/slice-http-interface.md#post-slices--submit-a-plate-configuration):
a remembered submission "is answered `202` with that slice job before any check";
[While stopping](../../../contracts/slice-http-interface.md#rules-for-every-request) and the
slice service's details: the stopping answer is given after the repeat and before any check.

**The two sides.** The slice service does so (`web.submit`: `_repeat`, then `_stopping`,
then `_queue`). The stand-in read the plate's form first, so a repeat or a submission during
a stop whose body broke its form was refused `400` there and answered `202` or `503` by the
slice service.

**Evidence.** Reading the two.

**Done.** The stand-in answers a repeat and the stopping answer before it reads the form,
with a test.

### 5. The slice service's last log lines before it stops

**The words.** [The architecture](../../../docs/architecture.md#where-it-goes): the log
bucket keeps every component's lines ninety days, the front server gathering the slice
service's. [What a restart does](../../../docs/architecture.md#what-a-restart-does): "a crash
(not a deploy) loses the last minute of log lines". The slice service's
[`GET /log`](../../../contracts/slice-http-interface.md#the-log) is asked "about once a
minute".

**The two sides.** The front server gathers when it starts and then every 60 seconds
(`gathering.LOG_GATHER_S`). The slice service, asked to stop, exits once no sliced file
waits to be collected (`__main__.run_until_stopped`), without waiting for its lines to be
gathered. A new slice service process has a new `process` id and numbers its lines from 1,
so the front server starts again from 0 of the new process.

**Consequence.** At every deploy of the slice container, the slice service's lines written
since the front server's last gathering, up to a minute of them, never reach the log
bucket: the transitions of the slices of that minute, the `slice_service_stopping` and
`slice_service_stopped` lines, and any refusal. They stay in Railway's log view, which keeps
them seven days, not ninety. A deploy, unlike a crash, was meant to lose nothing.

**Evidence.** Reading the two; the joined log test shows the gathering happening only at a
front server's start, and nothing gathers between a slice service's stop and its exit.

**Done.** Not fixed: the choice is the owner's (below).

### 6. A stopping slice service exits before answering the DELETE that drained it

**The words.** [While stopping](../../../contracts/slice-http-interface.md#rules-for-every-request):
"every other request is answered as usual until the process exits"; the slice service's
[Asked to stop](../../../slice/README-details.md#asked-to-stop): it exits once no done slice
job holds a sliced file the front server has not deleted with `DELETE /slices/<job>/file`.

**The two sides.** The front server stores the sliced file, writes its record, sends the
`DELETE`, and holds the page's `done` report until that `DELETE` is answered
(`following._store_steps`). The slice service marks the file deleted inside the `DELETE`'s
handler, which wakes its stop at once; its main thread then shut the web server down and the
process exited, while the handler's thread, a daemon thread, had still to write the answer.
The front server saw the connection cut, tried the `DELETE` again after 1, 2, 4, 8, 16 and
30 seconds, and the page waited, until a new slice service answered `slice.unknown_job`
(which the front server takes as deleted). Hosted, every deploy of the slice container that
ends with a slice being collected would show that slice as running for as long as the new
slice service takes to start, plus up to 30 seconds. Neither stand-in stops, so neither
suite could see it.

**Evidence.** A joined run of
`test_a_stop_ends_the_waiting_slice_refuses_new_ones_and_finishes_the_running_one`
(`--randomly-seed=4117291481`): the slice service logged `file_deleted` and
`slice_service_stopped` in the same millisecond and exited; the front server logged
`sliced_file_retry` "telling the slice service the file is stored" six times, and the
page's stream never ended.

**Done.** The slice service waits, before it exits, for the answers it is writing, at most
10 seconds, counting them at its web server's request handler, and says in a line which
answers it cut at the bound. A test in its fast suite holds the draining `DELETE`'s answer
past the stop's last line until `serve` either starts waiting for the answers being written
or has returned, and reads on the line straight after `serve` returns whether the answer was
written. With the wait removed it fails every run (eight of eight), since the answer is then
released only after `serve` has returned; with the wait it passes every run. (Its first form
checked only after the driver thread, which itself waits for the answer, was joined, and so
could not fail; a review found that.) The same test sets the bound to 3,600 seconds, far
beyond its 10-second backstop, and lets the answer end only once `serve` waits, so the wait
must be ended by the answer's end, not by its bound: with the handler's wake-up removed it
fails, where before it passed 10 seconds slower; and it checks that no
`slice_service_answers_cut` line is written. A second test checks the cut at the bound.

### 7. A stop at the moment the front server says it listens

**The words.** [Running phase 2 on one machine](../../../front/README-details.md#running-phase-2-on-one-machine):
the front server "stops on Ctrl-C or `SIGTERM`, writing its `stop` line and what its log has
gathered". Its `start` line, with its port, is what a watcher, the joined suite or a host,
reads as the sign it listens.

**The two sides.** The front server wrote its `start` line, started its loops and only then
took the stop signals, just before serving. A `SIGTERM` in that window ended the process by
the signal's default action: no `stop` line, and the slice service's lines it had just
gathered never written to the log folder.

**Evidence.** A joined run of the log test (`--randomly-seed=4117291481`): the second front
server asked the slice service for its log and was sent `SIGTERM` as soon as the slice
service had answered, and none of the lines it gathered reached the log folder. That run's
output was not kept, so its exit status is not known; reading `server.serve` showed the
window, and the front server's own test, written first, showed the default action in place
when the `start` line was written. A second cause of a failing log test in the same seed
was the suite's own: it read the log folder's files in name order, which is not the order
of writing within one second; it now orders lines by their time and number.

**Done.** The front server takes the signals before it writes its `start` line, and a stop
that arrives before the web server runs ends it the same way. Two tests in its fast suite,
run in the main thread: the handler is in place when the `start` line is written, and a stop
raised before the serving begins still writes the `stop` line and the log. The joined suite
now fails any stop of the front server that is not clean (exit status 0 and a `stop` line).
A second test sends a second `SIGTERM` as the stop begins, before the first thing it ends,
as well as at its `stop` line, so the second stop is ignored for the whole of the stop.

### 8. While stopping, a body that cannot be read as JSON

**The words.** [While stopping](../../../contracts/slice-http-interface.md#rules-for-every-request):
"`POST /slices` answers `503` `slice.stopping` (except a repeat of a remembered
submission)", which read as every `POST /slices`, whatever its body.

**The two sides.** The slice service reads the body as JSON first, since the repeat is found
by the body's `submission_id` (`web.submit`): a multipart form, a body over the size cap
or one that is not JSON is refused `400` (or `413` for size) `slice.bad_plate_configuration`
before the repeat and the stopping answer. The stand-in answered such a body `503`
`slice.stopping` while stopping (it checked only the size first).

**Evidence.** Reading the two; a review of this batch found it. The front server always sends
a JSON body it built itself, so no page can meet it.

**Done.** The slice service's order is the one the repeat needs, so it is kept. The stand-in
now refuses a multipart form or a body that is not JSON before the repeat and the stopping
answer, with a test (`test_a_stopping_slice_service_refuses_a_body_it_cannot_read_before_it_answers_stopping`),
and the contract's words say that such a body is refused as at any other time.

## A choice for the owner: the slice service's lines at a deploy

**What it is.** Whether a deploy of the slice container may lose up to a minute of the
slice service's lines from the log bucket.

**What the code does today.** The front server asks for the slice service's lines once a
minute; the slice service exits at a stop once its sliced files are collected, which with no
slice running is at once. On one machine the joined suite's stopping slice service exited
within about a second of being asked. Every line is also on the slice service's standard
error, which Railway keeps seven days.

**The options.**

- **A. Accept it.** Nothing changes. Cost: none. What a user sees: nothing. What support
  loses: the slice service's lines of the minute before each slice container deploy, after
  seven days.
- **B. The slice service waits, at a stop, until its lines are gathered.** Once drained,
  it keeps answering until a `GET /log` has asked past its last line, bounded by a stated
  time (60 s, the gathering's interval). Cost: a change to the slice service's stop and its
  tests; every slice container deploy takes up to a minute longer, within Railway's stop
  time, which is not yet measured. What a user sees: nothing, since a stopping slice service
  answers every request but new plates, which the page submits again.
- **C. The front server gathers more often,** every 5 seconds. Cost: a figure in the front
  server, twelve times the requests on the private network (each a few hundred bytes when
  nothing is new). What a user sees: nothing. What support loses: at most 5 seconds of lines
  at a deploy.
- **D. B and C together:** C makes B's wait short.

**Recommendation.** C: the cheapest change, one figure on one side, and it shrinks the loss
for a crash as well as for a deploy. B can follow if a measured stop time leaves room for it.

**What is not known.** How long Railway allows a stopping container
([What Railway does at a deploy](../../../front/README.md#what-railway-does-at-a-deploy)),
which bounds B.

## Seen while joining, outside this seam

- **A front server's stop takes about 5 seconds while it follows a slice that is quiet.** In
  the joined suite's front restart tests, `SIGTERM` to the `stop` line took 5.1 s, while a
  slice held at Orca's gate was followed. It is the web server's wait for its threads at
  shutdown; finishing work in flight at a stop is the front server's phase 3 item
  ([Stopping](../../../front/README-details.md#stopping)). Nothing is lost: the next front
  server follows the slice again.
- **A failed slice's details answer `409` `front.sliced_file_not_ready`.** The wizard's
  contract gives that code "while the slice job has not finished, or its sliced file is not
  yet stored", which a failed or replaced slice is not. It is the seam between the wizard
  and the front server, for the wizard's builders to read; the page meets it only by asking
  for the details of a slice it already knows failed.

## What the joining exercises for real

Each of these had been exercised, on the front server's side, only against the stand-in:

- `POST /parts` with both units, the record equal to the contract's example, a refusal's
  bytes passed unchanged, and the two refusals for size the front server makes itself equal
  to the slice service's own but for `detail`.
- `POST /slices`: acceptance, a refusal of placement byte for byte, `slice.busy` byte for
  byte, `slice.stopping` byte for byte, `slice.part_missing` with `missing_parts` and the
  page's upload and submission again with the same value, a repeat before and after the
  slice ends, a replacement, another plate not replaced.
- `GET /slices/<job>/events`: the stream from its first report to its final one, each
  report once and in order, the stages in their order, `cancelled` with `replaced` and with
  `shutdown`, a failed slice's report equal to the slice service's own, and the 15-second
  repeat of a quiet stream dropped by the front server while the page gets its keep-alive.
- `GET /slices/<job>/summary`, `GET /slices/<job>/file` and `DELETE /slices/<job>/file`: the
  sliced file stored, offered under its name, and the slice service's copy deleted once.
- `GET /slices` at a front server's start: a running slice followed again, a slice that
  ended while the front server was down collected with `ended_at` as its `slice_ended_at`,
  `file_on_disk` false after. Both moments are to the second and usually fall in the same
  one, so the joined check shows `ended_at` crossing in a form the front server takes, not
  that the two hours count from the slice's end rather than from the collecting: the front
  server's fast suite checks that on its fake clock.
- `GET /settings-table`, compressed and plain, the configuration's profiles found in its
  catalog.
- `GET /log`: the lines gathered into the log folder, each once, with the group added, the
  cursor carried across a front server's restart.
- A slice service killed while it slices, and one asked to stop with one slice running and
  one waiting; a slice service restarted after a finished slice.
- With the real Orca, once: a small real plate from upload to download, the sliced file a
  real one.

## What only a stand-in still exercises

- `slice.output_too_large` and the front server's `front.sliced_file_too_large`: neither
  the stand-in Orca nor a small real plate makes a sliced file over 50 MB.
- `slice.no_user_key`: the front server always sends the user key.
- A slice job of another user key: the development identity is one user.
- `GET /log`'s `dropped` and `more`, which need more than 1,000 and 10,000 lines.
- `GET /log`'s `process` changing across a slice service restart, and the front server
  starting again from `after=0` of the new process: the joined log test restarts only the
  front server (the front server's own tests `test_a_changed_process_starts_again_from_zero`
  and `test_a_restarted_front_server_beside_a_new_slice_service_starts_from_zero`, against
  the stand-in).
- A sliced file cut partway, and a slice service that stops answering mid-request.
