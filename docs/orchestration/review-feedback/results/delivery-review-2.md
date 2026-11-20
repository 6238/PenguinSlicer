# Review 2 of printer delivery after the review-feedback changes

Written Fri 2026-11-20 10:50 PT. Reviewed: the uncommitted changes under `delivery/` in
`/repos/popcornpenguins/penguin-slicer` (`git diff main -- delivery`, 33 changed paths and
2 new test files) after the fix round that followed
[review 1](delivery-review-1.md), judged against [review.md](../briefs/review.md),
[standing-rules.md](../briefs/standing-rules.md) and the builder's brief
[delivery.md](../briefs/delivery.md). Neither builder's result file was opened. No tracked
file was changed except this one: `git status --short -- delivery` lists the same paths
before and after.

## Verdict

**FIX, 4 defects: 4 low.**

All five defects of review 1 are fixed at their cause, each with a test that fails when
the fix is undone. Every suite and every make target passes through `make` itself, the
fast suite passed 20 of 20 random-order runs, and the hold behaves the same as `main`
after a start command under every slow or failing relay tried. The four defects left are
two corners of the log lines about removing a file, one name, and one sentence of the
guide's walk that `main` already had. None lets a second start command reach a held
printer.

Scratch files are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/delivery-review-2/`:
`pt.sh`, `repeat.sh`, `mut.sh`, `mk.sh`, `all.sh`, `walk2.sh`, `hold_probe.py`, the logs
beside them, the scratch copy `copy/delivery/` (with my tests
`daemon/tests/test_r2_delete.py` and the mutation switches) and `main/delivery/` (the
same folder as of `main`, from `git archive`).

Every pytest run of mine was started from `delivery/.venv/bin/python` under `timeout -k 5`
and an address-space limit on pytest itself, on at most 2 workers. The make targets were
run through `make` under `timeout` and an address-space limit of 4 GB on the whole tree.
Another agent was using the machine; each timing says the load it was taken under.

## What was not checked

- The Ctrl-C handling (item 6) and the "never frees a printer" claim beyond what review 1
  tried: review 1 covered both and the code there is unchanged in kind.
- `make hardware-smoke` and `make upgrade-printer-library` (a real printer, the network).
- Real firmware: whether the H2S lists a partial file, and how it spells a name in its
  listing. Defect 1 below rests on fakes.
- The first `make` run rebuilt the daemon package in `delivery/.venv` (uv saw the changed
  `pyproject.toml`). `make daemon-tarball` left an empty `delivery/dist/`, which I removed.

## 1. Review 1's five defects, and the builder's brief

| Review 1's defect | Verdict | The test that fails when the fix is undone |
|---|---|---|
| 1. An unreadable listing taken as proof of absence | Fixed: `_listing(whole=True)` answers None for no list of lines or a line the pattern does not read, and `delete` then sends the delete | MA (an unreadable line is skipped): 3 subtests of `test_a_listing_the_daemon_cannot_read_is_no_proof_and_the_delete_is_sent` fail. MG (no list of lines counts as empty): 1 fails. MH (the listing after the delete is not read whole): 4 fail |
| 2. Nothing tested that an overtaken note keeps the printer held | Fixed | MB (`_note_overtaken` drops the hold): both cases of `test_an_overtaken_note_keeps_the_printer_held_for_the_relays_last_start` fail, nothing else |
| 3. A slow relay stopped the hold's count | Fixed: the time of the ask is passed to `StartHold.watch` as `asked_s` | MC (`asked_s` not passed): `test_a_slow_hold_check_does_not_stop_the_holds_count` fails, nothing else |
| 4. The guide did not say which faults only the fixed sequences catch | Fixed: the guide names G4 and N2 | Measured: with N2 put back the properties target passes and the fast suite fails 13 |
| 5. "The Pi" in comments | Fixed | `git grep -w` for `Pi`, `Pi's`, `Raspberry`: no match under `delivery/` |

The nine items of the builder's brief stand as review 1 found them. Two more mutations
of items 1 and 5: ME (`take_age` counts the watched time twice) fails 1 test; MD (a long
gap between looks is counted) fails 2.

**The fixed-sequence faults review 1 did not put back**, each alone, fast suite on 2
workers and then the properties target:

| Fault | Fast suite | Its fixed sequence | Properties target |
|---|---|---|---|
| G9 | 8 fail | fails | 1 fails, 5.4 s |
| G12 | 2 fail | fails | 2 fail, 3.6 s |
| N1 | 5 fail | fails | 1 fails, 3.6 s |
| N2 | 13 fail | fails | 3 pass (as the guide says) |
| N3 | 5 fail | fails | 1 fails, 8.1 s |
| N7 | 6 fail | fails | 1 fails, 7.9 s |

MB, MC and MD pass the properties target; the fast suite catches each. No mutation
escaped the fast suite: 13 of 13 noticed.

## 2. Terms

`plate job`, `plate_job`, `http face`, `penguin slicer`: no match under `delivery/`.
The computer the daemon runs on has three names: "the computer next to the printer",
"the daemon's computer", and "the shop computer" (defect 3).

## 3. Flakes and speed

Fast suite, random order, 2 workers, seeds `9001 + 6151 * run` for runs 1 to 20: **20 of
20 passed**, 1,113 tests and 160 subtests each (plus one test of mine that checks the
copy is the code under test).

| Runs | Load at the start | pytest's own time |
|---|---|---|
| 1 to 3 (quiet machine) | 0.55 to 0.93 | 3.72 s, 3.58 s, 3.72 s |
| 4 to 12 | 1.02 to 1.49 | 3.56 s to 4.15 s |
| 13 to 20 | 1.77 to 2.30 | 3.90 s to 4.25 s |

The load in the later runs is partly these runs themselves. On one worker, as `make test`
runs it, the suite took 6.0 s to 6.2 s at a load of 1.2 to 1.9; no one-worker timing was
taken on a quiet machine.

The ten slowest tests (`make slowest`, one worker, load 1.9): 0.32 s, 0.21 s, 0.17 s,
0.10 s, 0.08 s, 0.07 s, 0.06 s, 0.06 s, 0.06 s, 0.06 s; the first three are in
`tests/test_link_faults.py`. No property test is among them.

## 4. Coverage

`make coverage`, branch coverage per module, against review 1's figures:

| Module | Now | Review 1 |
|---|---|---|
| `run_loop.py` | 99% | 99% |
| `printer.py` | 97% | 96% |
| `start_record.py` | 96% | 96% |
| `__main__.py` | 98% | 98% |
| `config.py` | 97% | 97% |
| `relay_client.py` | 99% | 99% |
| `deliveries.py` | 98% | 98% |
| `relay.py`, `routes.py` | 99%, 99% | 99%, 99% |
| `paths.py`, `app.py`, `caller.py`, `errors.py`, `limits.py`, `sliced_files.py` | 100% | 100% |

Coverage has not fallen.

## 5. The other suites, and every make target through `make`

| Target | Result | Wall time | Load |
|---|---|---|---|
| `make test` | 1,113 passed | 9 s (with the rebuild of the daemon package) | 1.4 |
| `make slowest` | 1,113 passed | 7 s | 1.9 |
| `make test-parallel` | 1,113 passed | 4 s (pytest 4.07 s) | 1.5 |
| `make test-properties` | 3 passed | 6 s (pytest 5.44 s) | 1.6 |
| `make test-sim` | 37 passed | 18 s | 1.7 |
| `make test-upstream` | 56 passed | 18 s | 1.5 |
| `make test-together` | 2 passed | 2 s | 1.4 |
| `make together` | exit 0, the job acknowledged and the printer running | 1 s | 1.2 |
| `make coverage` | 1,113 passed | 13 s | 1.2 |
| `make test-repeat` | 10 of 10 runs passed | 63 s | 1.2 |
| `make daemon-tarball` | the eight modules and `pyproject.toml`; no installer, no service unit | under 1 s | |

## 6. Error reports

No code was added or removed by the fix round. In the walk, a cancel too late answers
`409` with a whole error report: `delivery.cancel_too_late`, the guide's sentence word
for word, the remedy "Stop the print on the printer's own screen if it should not go
on.", `retryable: false`, and the detail naming the job.

## 7. The guide's walk, steps 5, 6 and 8

Walked as written against the code as it stands (`walk2.sh`), with steps 1 to 4 as set-up.

| Step | Seen | Matches the guide |
|---|---|---|
| 5. A whole print | The stream ended by itself after 23 s at `done`; printer stages heating the bed, levelling it, 25 and 75 percent, 100 | Yes for the end and the time. The stages on the stream were `waiting_for_daemon`, `starting`, `printing` only (defect 4) |
| 6. A cancel at once | `200`, `"outcome":"cancelled"`; the report says `cancelled`, stage `waiting_for_daemon` | Yes |
| 8. Too late to cancel | After ten seconds the report says `printing`; the cancel answers `409`, `delivery.cancel_too_late`, the guide's sentence; the print goes on to `done` | Yes |

The daemon's log through all three: two jobs downloaded, uploaded ("the printer has all
323 bytes"), started and acknowledged, the cancelled one never reached it, then
`stopping` on one interrupt. The home held `config.toml` and an empty `downloads/`
afterwards and nothing was left running.

The guide's figures hold: 260 random sequences in "about 5 s" (5.4 s to 5.8 s measured),
a real bug failing the properties target "within about a minute" (3.6 s to 8.1 s for the
five faults it catches).

## 8. The probes of this round

### Deleting a cancelled file from the printer

`copy/delivery/daemon/tests/test_r2_delete.py`: the file is on the printer, and the
listing is answered in 18 shapes.

| The listing | `delete` answers | Delete sent |
|---|---|---|
| Blank lines around the file's line; a trailing carriage return | False (the fake's fixed listing still shows the file afterwards) | Yes |
| A `total 4` header line; a truncated line cut inside the date; a year in place of the time; an ISO date in two fields | False | Yes |
| The listing fails, or carries no list of lines | False | Yes |
| **Only blank lines** | `not_on_printer` | **No** |
| **Every line read, the file's name spelled otherwise** (upper case, `./` or `/` before it) | `not_on_printer` | **No** |
| **The last line cut inside the name**, or the listing cut before the file's line | `not_on_printer` | **No** |
| **Partial lines beside a `426` reply** | `not_on_printer` | **No** |

The rule the fix round chose holds as written: a blank line is ignored, a line the
pattern does not read sends the delete, and an empty folder sends none. With the pinned
library three of the four bold rows cannot come from a transfer that failed: the library
swallows the failure and answers None, so the delete is sent (read in
`bambulabs_api/ftp_client.py`). What remains is a listing the printer answers whole, with
`226`, that does not show the name as the daemon sent it. In that case a file is left on
the printer while the log says it is not there: defect 1.

Each log line, against what happened:

| Line | True? |
|---|---|
| "the printer does not have X, so there was nothing to remove" | True whenever the listing shows names as the daemon sent them. Untrue in defect 1 |
| "removed X from the printer" | True when the file was listed, deleted and no longer listed. Untrue when the first listing failed and the second did not: defect 2 |
| "could not confirm X was removed from the printer; it is harmless there, but can be deleted on its screen" | True in every case tried |

A listing after a reconnect: the library opens a new FTPS connection for every listing,
and a link that is not connected raises, which `_listing` takes as "cannot be asked", so
the delete is tried and the line is "could not confirm". Nothing stale is read.

### The hold's count and the time spent asking the relay

`hold_probe.py` drives one delivery job through the real `RunLoop` on a fake clock, with
the relay's hold check taking a chosen time, and prints the second the job ended. It was
run on the changed code and on `main`'s; **the two outputs are the same in all 35
cases**.

| Case | Seconds from the start command to the end (both) |
|---|---|
| The printer ignores the start, fresh idle pictures; the relay answers at once, fails at once, or takes 14 s, 16 s or 20 s then answers or fails | 300, `delivery.start_timeout` (301 with a 5 s ask) |
| The same, the ask takes 40 s, 100 s, 400 s, 1,000 s | 324, 336, 432, 1,032: the settle time or one ask past it, never earlier than 300 |
| The printer silent, or unreachable, throughout; four kinds of relay | No end in 6,000 s and the hold counted 0.0 s: silence is never counted, whatever the relay does |
| The print shows at 250 s; the relay at once, or 20 s then failing | 250 and 262, acknowledged ok |
| Silent from 40 s to 400 s, idle otherwise; three kinds of relay | 660 |
| The relay drops the job at the second hold check; a second job at 70 s | The first job leaves the wait unacknowledged with the printer held; the second starts only once the hold has counted 300 s, or is refused `delivery.printer_busy_at_start` at 250 s when the first print shows |

So a slow or failing relay neither frees a held printer before `START_SETTLE_SECONDS` of
whole, fresh pictures nor holds one for ever, and the count is back to what `main` did.
A slow ask can hold the printer longer by at most the length of that one ask, as on
`main`. The excuse covers the ask and nothing else: `asked_s` is measured around the one
call and set back to zero after the next look, and
`test_a_hold_counts_only_the_time_between_looks_close_together` pins that it "excuses no
more than itself".

The tests of the hold in `git diff main -- delivery`: tests are added, and the bodies of
the three property tests move into `starts_case`, `resend_case` and `faults_case`. No
assertion about the hold that `main` had is changed or removed.

### The removal of the Raspberry Pi installer

`git grep` under `delivery/` for `install.sh`, `install-printer`, `installer`,
`INSTALLER_LIMIT`, `installer_path`, `is_service_install`, `LEGACY_CONFIG_PATH`,
`systemd`, `systemctl`, `journal`, `chown`, `plain_text`, `penguincam user`, `Raspberry`:
no match. `sudo` appears only in three assertions that a message does not say it.

Every route of `main` except `/install-printer.sh` keeps the limit it had, read side by
side in `routes.py`:

| Route | Limit on `main` | Limit now |
|---|---|---|
| `GET /printer/status` | `STATUS_LIMIT` | the same |
| `POST /printer/jobs` | `JOBS_LIMIT` | the same |
| `GET /printer/jobs/<id>`, `.../events` | `STATUS_LIMIT` | the same |
| `POST .../cancel`, `.../stop-following` | `JOBS_LIMIT` | the same |
| `POST /printer/daemon/pair` | `EXCHANGE_LIMIT` | the same |
| `POST /printer/daemon/sync` | `SYNC_LIMIT` | the same |
| `POST .../ack`, `.../start`, `GET /printer/daemon/ping` | `DAEMON_LIMIT` | the same |
| `GET /printer/download/<token>` | `DOWNLOAD_LIMIT` | the same |

The six limits keep their values, the HTTPS refusal of the daemon's routes is unchanged,
and `routes.py` still uses the `os` import the installer route shared.

## Defects

1. **Low. A file the daemon itself uploaded can be left on the printer while the log
   says the printer does not have it.** `PrinterLink.delete` answers `NOT_ON_PRINTER`
   whenever a listing read whole lacks the exact name, with no regard to what the daemon
   knows of the upload. Evidence (`test_upload_226_but_listed_under_another_spelling_then_delete`
   in my scratch tests): the upload is answered `226`, the listing shows the name in
   upper case, the upload's note is "sent 9 bytes; the printer did not list its files to
   confirm", and the removal that follows answers `not_on_printer`, sends no delete and
   leaves the file. On `main` the delete was always sent. It needs a printer that spells
   a name otherwise in its listing (or lists late), which nothing shows the H2S does;
   the format of its `LIST` lines is an open line of the guide's hardware checklist.
   Fixed when the delete is sent whenever this delivery job's upload may have put bytes
   on the printer (it reached the transfer), and `NOT_ON_PRINTER` is kept for an upload
   that never did, with a test of an upload answered `226` whose name the listing does
   not show.

2. **Low. "removed X from the printer" is still logged for a file that was never
   there, when the first listing fails and the second does not.** Evidence
   (`test_first_listing_fails_then_works_file_never_there`): the file is not on the
   printer, the first listing answers None, the delete is sent (the printer would answer
   `550`), the second listing lacks the name, and `delete` answers True. This is item 6
   of the builder's brief in a narrower corner. Fixed when True is answered only if the
   file was seen listed before the delete, and the line otherwise says the printer does
   not list it.

3. **Low. One thing has three names.** The computer the daemon runs on is "the computer
   next to the printer", "the daemon's computer" and "the shop computer":
   `README.md` line 1188, `daemon/pyproject.toml` lines 7 and 11 (line 7 written in this
   change), `scripts/upgrade_printer_library.py` line 112, `tests/test_link_faults.py`
   lines 733 and 737, `tests/test_upgrade_script.py` line 34. None reaches a student.
   Fixed when one name is used.

4. **Low, and already so on `main`. Step 5 of the guide's walk names stages the stream
   does not show.** The guide says the reports go through `waiting_for_printer` and
   `uploading` and that only `downloading` is seldom seen; in the walk the stream showed
   `waiting_for_daemon`, `starting` and `printing`. One run. Fixed when the sentence
   says that on one machine the stages before `starting` pass too quickly to be seen.
