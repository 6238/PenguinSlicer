# Review 1 of printer delivery after the review-feedback changes

Written Fri 2026-11-20 10:20 PT. Reviewed: the uncommitted changes under `delivery/` in
`/repos/popcornpenguins/penguin-slicer` (`git diff main -- delivery`, 31 changed paths and
2 new test files), judged against [review.md](../briefs/review.md),
[standing-rules.md](../briefs/standing-rules.md) and the builder's brief
[delivery.md](../briefs/delivery.md). The builder's result file was not opened. No file
in the repository was changed except this one (`git status --short -- delivery` lists
the same 33 paths before and after).

## Verdict

**FIX, 5 defects: 2 medium, 3 low.**

All nine items of the builder's brief are done, every suite passes, and the fast suite is
back to about 4 s with no failure in 20 random-order runs. The two medium defects are a
new untrue log line with a delete that is never sent (item 6 of the brief), and a safety
property of item 4 that no test protects. Nothing found lets a second start command reach
a held printer in the code as it stands.

Scratch files are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/delivery-review-1/`:
`repeat.sh`, `fast-quiet.log`, `fast-rest.log`, `pt.sh`, `mut.sh`, `others.sh`, `walk.sh`,
`walk/`, `sigint.sh`, `sigint/`, and the scratch copy `copy/delivery/` with my tests in
`copy/delivery/tests/test_r1_hostile.py`.

Every pytest run was started directly from `delivery/.venv/bin/python` under `timeout -k 5`
and a 3 GB address-space limit on pytest itself, on at most 2 workers. Another agent was
using the machine throughout; each timing below says the load it was taken under.

## What was not checked

- Steps 5, 6 and 8 of the guide's walk (a whole print, a cancel at once, a cancel too
  late). Steps 1 to 4 and 7 were walked.
- `make test-together`, `make together`, `make daemon-tarball`, `make test-repeat`,
  `make slowest` were not run. The `make` targets `test`, `test-properties`, `test-sim`,
  `test-upstream` and `coverage` were dry-run (`make -n`) and their pytest commands run
  directly from the environment, not through `uv run`.
- Of the nine faults the fixed sequences name, three were put back (G2 and G13 through
  one mutation, G4). G9, G12, N1, N2, N3 and N7 were not put back.
- The "never frees a printer" claim of item 4 was tested on two sequences of my own, not
  by a campaign.

## 1. Each item of the builder's brief

| Item | Verdict | Evidence |
|---|---|---|
| 1. Test for the hold's timing | Done | Mutation M1 (below) fails `test_a_hold_from_the_note_counts_the_watched_time_once_when_it_takes_the_gates_age` and nothing else |
| 2. Fast suite about 4 s | Done | 3.67 s on a quiet machine (section 3); three property tests carry the marker `properties`; `tests/test_fixed_sequences.py` has 8 sequences naming 9 faults |
| 3. A real bug fails fast | Done | Properties target under M7: fails in 6.1 s; under M9 (a hold that never settles): fails in 12.9 s. Shrinking is off (`PROPERTY_SETTINGS`, `tests/link_faults.py`); the guide states the bound (30 s per test plus one run) |
| 4. Damaged or out-of-date note | Done, half tested | The delay is gone (the two new tests assert `elapsed_s < 120`). The code keeps the printer held (my H1 passes), but no test fails when it stops doing so: defect 2 |
| 5. Silent time and the hold | Done in code | `StartHold.watch` drops a gap over `FRESH_REPORT_SECONDS`; the guide says so. It changes the timed rule in one more corner: defect 3 |
| 6. Two log lines | Done, with a new fault | Walk step 7: the log says "the printer does not have ..., so there was nothing to remove", no `550` line. Three interrupts at once: the log ends `stopping`, no trace. The new listing check is defect 1 |
| 7. Installer removed | Done | `install.sh` and `test_daemon_install.py` deleted; no `install.sh`, `install-printer`, `systemd`, `systemctl`, `is_service_install`, `Raspberry` left under `delivery/`; the relay's route, limit and `installer_path` are gone |
| 8. The certificate | Done | Guide, Upstream: "The daemon accepts any certificate the printer presents, on MQTT and on FTPS alike"; the checklist line is removed; the simulated-printer test is renamed |
| 9. Terms | Done | Section 2 |

**Mutations, each alone in the scratch copy** (fast suite on 2 workers, then the
properties target where noted):

| | Mutation | Fast suite | Properties target |
|---|---|---|---|
| M1 | `take_age` counts the watched time twice (item 1) | 1 fails | 3 pass (9.0 s) |
| M2 | A gap up to 300 s between looks is counted (item 5) | 1 fails (the unit test; the sequence test passes) | not run |
| M3 | An overtaken note frees the printer instead of holding it for the relay's last start (item 4) | **0 fail: escaped** | **3 pass: escaped** |
| M4 | `delete` never answers `NOT_ON_PRINTER` (item 6) | 1 fails | not run |
| M5 | Every interrupt raises, not only the first (item 6) | 1 fails; the run is then aborted (exit 2, 558 of 1,107 tests run) | not run |
| M7 | A picture not whole counts as fresh (G2, G13) | 8 fail, 3 of them fixed sequences | 2 fail in 6.1 s |
| M8 | A daemon that could not watch never takes an end (G7) | 4 fail | 3 pass |
| M9 | A hold never settles as "no print" | many fail, each at the simulated-time bound | 3 fail in 12.9 s |
| M10 | No wait for a free printer before the gate (G4) | 8 fail, 1 a fixed sequence | **3 pass** (defect 4) |

M4 and M5 were applied together and told apart by the test that failed. The suite did
not notice one of nine: M3.

## 2. Terms

`git grep -n -i` over `delivery/` (lock file left out) for `plate job`, `plate_job`,
`http face`, `penguin slicer`: no match. `copy`/`copies`: 24 matches, every one about
duplicating a file, a value or a literal (`copy.deepcopy`, "the relay's copy of a sliced
file", "copy the tarball"), right to leave. The `where` key of an error report is
`instance` in `relay/tests/test_relay_errors.py` and `tests/test_contracts.py`, and the
contract tests pass against `contracts/`.

"The Pi" for the computer next to the printer remains in comments and docstrings
(defect 5). `penguincam-printer` remains as the command, the User-Agent, the token salt
and the tarball's name, which the package's docstring states is kept on purpose.

## 3. Flakes and speed

Fast suite, random order, 2 workers, seeds `4100 + 7919 * run` for runs 1 to 20: **20 of
20 passed**, 1,107 tests and 156 subtests each, no failure.

| Runs | Load at the start | pytest's own time |
|---|---|---|
| 1 (the only run on a quiet machine) | 0.82 | 3.67 s |
| 2 to 18 (another agent working) | 0.91 to 3.17 | 5.08 s to 6.48 s |
| 19, 20 | 3.08, 3.16 (the one-minute average, which lags; the times suggest the other work had just ended) | 4.17 s, 3.90 s |

So one timing was taken on a quiet machine, 3.67 s, and it agrees with the brief's
"about 4 seconds".

The ten slowest tests (one worker, load about 2): 0.39 s, 0.38 s, 0.17 s, 0.10 s, 0.10 s,
0.09 s, 0.09 s, 0.08 s, 0.08 s, 0.07 s; the first three are in `tests/test_link_faults.py`.
No property test is among them.

## 4. Coverage

Branch coverage per module under the fast suite, measured with the data file in the
scratch folder. The guide states no figures, so the comparison is with
[review 6](../../penguin-slicer/results/delivery-hardening-review-6.md):

| Module | Now | Review 6 |
|---|---|---|
| `run_loop.py` | 99% | 99% |
| `start_record.py` | 96% | 96% |
| `printer.py` | 96% | 96% |
| `__main__.py` | 98% | 97% |
| `config.py` | 97% | 97% |
| `relay_client.py` | 99% | 99% |
| `deliveries.py` | 98% | 98% |
| `relay.py`, `routes.py` | 99%, 99% | 99%, 99% |
| `paths.py`, `app.py`, `caller.py`, `errors.py`, `limits.py`, `sliced_files.py` | 100% | 100% |

Coverage has not fallen.

## 5. The other suites

| Suite | Result | Time (load about 2) |
|---|---|---|
| Simulated printer (`-m simulator`) | 37 passed | 18.3 s |
| Upstream check (`-m "upstream or simulator"`) | 56 passed | 18.6 s |
| Properties (`-m properties -n 2`) | 3 passed | 5.3 s (load 2.8) |

## 6. Error reports

No code was added or removed. The two sentences that named "the Pi" now say "the computer
next to the printer", in `relay.py`, in the rules of `errors.py` and in the tests that
pin them. The stage sentence of `waiting_for_earlier_print` is now "Waiting for the
printer to show that no earlier print is about to start", the same in `deliveries.py`
and the guide, and true of a hold from an unreadable note. From the walk's relay: an
unknown job answers `404 delivery.job_unknown` on the job route and on the cancel route,
each a whole error report with message, remedy and detail.

## 7. The guide

Walked as written with the simulated printer (`walk.sh`): steps 1 to 4, then step 7.
`pair` printed the pairing code and the `run` command with `--home`; the daemon said
`paired with the relay`, then idle; the cancel answered `202` with
`"outcome":"cancelling"`; ten seconds later the report said `cancelled`; the daemon's log
said the printer does not have the file, so there was nothing to remove, and that it was
never started. The home held `config.toml` and an empty `downloads/` afterwards, and
nothing was left running.

The guide's figures for the properties target ("260 random sequences in about 5 s",
"within about a minute" for a real bug) match what I measured (5.3 s; 6.1 s and 12.9 s).
The sentence that the fixed sequences cover "each fault the random sequences are known
to catch" leaves out that two of them are no longer caught by the random sequences
(defect 4).

## 8. Hostile cases of my own

`copy/delivery/tests/test_r1_hostile.py`, on the code as it stands:

| Case | Result |
|---|---|
| H1: the first start pending (shows at 250 s), its caller stops following at 90 s, the daemon restarts at 100 s with a damaged note, or with a whole note naming an older job, resend at 115 s | Passes, both: one start command, the second job ends `delivery.printer_busy_at_start`. With M3 both fail: a second start command while the first is pending |
| H2: the file is on the printer and the listing comes in a format the daemon's pattern does not match (three formats), or with no lines | **Fails, all four**: `delete` answers `not_on_printer` and sends no delete (defect 1) |
| H3: looks every 2 s, and every 30 s a relay call that takes the client's 20 s timeout | **A start the printer ignored settles at 1,048 s, not 300 s** (defect 3) |
| Interrupts (`sigint.sh`): five at once while waiting for a configuration; three at once with a printer address that answers nothing and a relay refusing connections; three 0.15 s after launch | Each log ends `stopping`, exit 0, gone within 2 s, no trace |

For printer delivery also:

- **The hold's tests before and after.** In `tests/test_start_decided.py`,
  `daemon/tests/test_daemon_run_loop.py` and `tests/test_link_faults.py` the diff adds
  tests and moves the bodies of the three property tests into `starts_case`,
  `resend_case` and `faults_case`; no existing assertion about the hold is changed or
  removed. The behaviour after a start command differs in items 4 and 5 and in the
  corner of defect 3.
- **Nothing of the Raspberry Pi installer remains** under `delivery/`.
- **A bug put in on purpose** fails the properties target in 6.1 s (M7) and 12.9 s (M9).

## Defects

1. **Medium. A listing the daemon cannot read is taken as proof that the file is not on
   the printer.** `PrinterLink.delete` (`printer.py`, lines 813 to 827) answers
   `NOT_ON_PRINTER` whenever the name is not among the lines its pattern matched. A
   listing in another format, or one with no lines, gives an empty set, so no delete is
   sent and the log says "the printer does not have ..., so there was nothing to remove"
   while the file is there. Before this change the delete was always sent. The format of
   the printer's `LIST` lines is an open line of the guide's own hardware checklist.
   Evidence: H2, four of four. Fixed when `NOT_ON_PRINTER` is answered only for a listing
   the daemon understood (every line matched, say), the delete is sent otherwise, and a
   test with an unreadable listing is in the fast suite.

2. **Medium. Nothing tests that an overtaken note keeps the printer held.** Item 4 lets
   a damaged or out-of-date note give way to the relay's last start; the brief requires
   that this never frees a held printer. With M3 (`_note_overtaken` drops the hold
   instead of replacing it) all 1,107 fast tests and the three property tests pass, and
   H1 shows a second start command sent while the first is pending. The code as it
   stands is right. Fixed when a sequence like H1 (the first job no longer followed, the
   daemon restarted on a bad note, a resend while the first start is pending) is in the
   fast suite and fails under M3.

3. **Low. A slow answer from the relay now stops the hold's count.** In `_await_start`
   the relay is asked every `HOLD_CHECK_SECONDS` (30 s) on the same thread as the looks;
   the client's timeout is 20 s (`relay_client.py`, line 83), over
   `FRESH_REPORT_SECONDS` (15 s), so the look after a timed-out ask counts nothing. With
   the relay timing out, 8 s of each 30 s count, and a start the printer ignored is
   reported, and the printer freed, after about 17 minutes instead of 5 (H3: 1,048 s).
   Before this change that time counted. It errs towards holding, but it is a change to
   the timed rule outside the corner item 5 names, with no test and no word in the
   guide. Fixed when a slow hold check does not break the count (a look just before and
   just after the ask, for instance), or the guide states it and a test pins it.

4. **Low. The random sequences no longer catch two faults that review 6 measured them
   catching, and the guide does not say so.** Under M10 (G4) the properties target
   passes; the docstring of `tests/test_fixed_sequences.py` says the same of N2. Both
   are caught by fixed sequences, so the fast suite has not lost them, but the guide
   presents the fixed sequences as copies of what the random ones catch. Fixed when the
   random sequences reach G4 and N2 again, or the guide says which faults only the fixed
   sequences catch.

5. **Low. "The Pi" still names the computer next to the printer in comments and
   docstrings**, where a reader may take a Raspberry Pi to be required:
   `printer.py` lines 412 and 666; `relay_client.py` lines 2, 36, 79, 81 and 180;
   `relay.py` lines 5, 26, 180, 440 and 467; `daemon/tests/daemon_fakes.py` line 312;
   `daemon/tests/test_daemon_run_loop.py` line 452; `relay/tests/test_relay_routes.py`
   lines 471 and 490; `relay/tests/test_relay_state.py` line 69. None reaches a user.
   Fixed when they say "the computer next to the printer" or "the daemon's computer".
