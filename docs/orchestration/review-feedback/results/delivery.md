# Result: the owner's feedback applied to printer delivery

Written Fri 2026-11-20 10:00 PT by the delivery builder, for the brief
[delivery.md](../briefs/delivery.md) under the [standing rules](../briefs/standing-rules.md).
All changes are in `delivery/`; nothing is committed (the coordinator commits). Review 6,
which items 1 to 6 come from, is
[delivery-hardening-review-6.md](../../penguin-slicer/results/delivery-hardening-review-6.md);
its regression names (G2, N4 and so on) are used below. Scratch files are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/delivery-builder/`:
`pt.sh` (pytest bounded in time and memory), `mutate.py` (puts one regression back in a
scratch copy of `delivery/` and runs pytest there), `repeat.sh`, `cov.sh`, and the logs in
`logs/`.

## Figures

Every run was pytest started directly from `delivery/.venv/bin/python` under
`timeout -k 5` and a 3 GB address-space limit on pytest itself (`pt.sh`), Fri 2026-11-20
between 09:00 and 10:05 PT, with other agents sharing the 4 CPUs.

| Suite | Runs | Failures | Time per run (pytest's own figure) |
|---|---|---|---|
| Fast suite (`-m "not real_time and not simulator and not properties"`), random order, 2 workers, seeds `4100 + 7919 * run` | 20 + 20 + 5 | 0 | Last 20 runs: 3.53 s to 7.68 s; runs 1 to 9 before the machine got busy, 3.53 s to 4.33 s, median 3.65 s. Before this round: 7.0 s |
| Properties target (`-m properties -n 2`) | 3 | 0 | 5.1 s to 5.3 s |
| Simulated-printer suite (`-m simulator`) | 1 | 0 | 18.1 s, 37 tests (one new) |
| Upstream check (`-m "upstream or simulator"`) | 2 | 0 | 17.8 s and 18.8 s, 56 tests |
| Together run (`-m real_time`) | 1 | 0 | 1.8 s |

The fast suite is 1,107 tests and 156 subtests (1,125 before: the 3 property tests, the
21 tests of `install.sh` and 14 tests of the relay's installer route and the daemon's
hand-over to an installed machine left; 20 new tests came).

**Coverage** (branch, the fast suite, `cov.sh`), before and after: `run_loop.py` 99% both
(7 partial branches before, 6 now), `__main__.py` 97% to 98%, `config.py` 97%,
`printer.py` 96%, `start_record.py` 96%, `relay_client.py` 99%, `deliveries.py` 98%,
`relay.py` 99%, `routes.py` 99%, the other relay modules 100%; in all, 555 missed
statements and 34 partial branches before, 553 and 32 now. The "before" figure included
the three property tests; the "after" does not.

## 1. The missing test for the hold's timing

**Done.** `tests/test_start_decided.py::test_a_hold_from_the_note_counts_the_watched_time_once_when_it_takes_the_gates_age`
is the reviewer's sequence (`r6_n4.py`): the daemon restarts 10 s after the start command,
watches about 100 s, the printer is quiet for 75 s, the caller stops following at 180 s and
sends again at 188 s, the printer shows the first print at 250 s. It asserts no overlap,
one start command, and the second job refused `delivery.printer_busy_at_start`.

**Proof.** With N4 put back in a scratch copy (`mutate.py N4`), the test fails: the second
start command reaches the printer while the first is pending (`model.overlaps` has it).
Without N4 it passes. Under N4 the whole fast suite now fails 3 tests (review 6: none).

## 2. The fast suite returns to about 4 seconds

**Done.** The three property tests carry the new marker `properties` (declared in
`pyproject.toml`), the fast suite's marker expression leaves them out, and
`make -C delivery test-properties` runs them (two workers, fixed order). Their bodies moved
into plain functions (`starts_case`, `resend_case` in `test_start_decided.py`,
`faults_case` in `test_link_faults.py`), which the property tests and the fixed sequences
both call, so both are held to the same invariants.

`tests/test_fixed_sequences.py` holds eight sequences written out by hand, one for each
fault review 6 lists as caught by the random sequences (G2, G4, G9, G12, G13, N1, N2, N7)
and N3 besides. Six were taken from the failing example the property tests printed with
the fault put back; G4 and N2 the property tests no longer reach at all (G4 passed them in
5 s, N2 too, after this round's changes), so those two sequences were written to reach the
fault (G4: the stream quiet from the download with three gate timeouts; N2: a daemon that
dies before marking the note `sent`, then both halves restarting before the resend).

**Proof.** Each of the nine faults, put back alone, fails its sequence in under 0.5 s
(`fixed_under_mutations.sh`), and fails the whole fast suite in about 4 s
(`fast_under_mutations.sh`: from 3 failing tests for G11 and N4 to 15 for N2). Review 6's
other five (G7, G11, N4, N5, N6) and this round's three (D4, D5, D6, below) each fail the
fast suite too: all 17 regressions tried are caught by it.

**Choice.** The fsync suggestion of review 6 (a note writer without `fsync` for the
harness) was not taken: the fast suite is at its target without it.

## 3. A real bug must fail fast

**Done.** `PROPERTY_SETTINGS` in `tests/link_faults.py` turns shrinking off
(`phases=(explicit, generate)`, `report_multiple_bugs=False`); all three property tests use
it. The cause, read from the runs: pytest-timeout raises its failure inside the test, and
Hypothesis takes that for a failing example and shrinks it, past the limit. Without
shrinking, a failing test ends within the 30 s per-test limit plus one more run of the
sequence that failed. The guide's Tests section says so, and that the target, three tests
on two workers, therefore ends within about a minute.

**Proof.** With a regression that makes every sequence slow (`mutate.py CPU`, a busy loop
in `RunLoop._fresh`), `make test-properties`'s command failed two tests on
`Timeout (>30.0s)` and ended in 63 s. With G2, it fails in under 5 s, printing the
sequence as found.

## 4. A damaged or out-of-date record of a start command

**Done, as the review describes.** `RunLoop._note_overtaken` (in `run_loop.py`): when the
relay names the printer's last start granted (`previous_start`, or the job itself offered
again with `start_granted` and no `previous_start`), a hold made from a note that is
damaged, or that names another job, becomes a hold for the start the relay names, rebuilt
from the gate's age and marked as the note's, so that start's own evidence settles it and
removes the note. The reasoning, in the code and the guide: a note is written only after
its own grant, so the relay's last grant is the note's start or a later one, and a later
one was granted only once the note's had settled. The printer is never left without a hold
by this: the replacement is made in the same step. A whole note naming the relay's last
start keeps its hold (it takes the gate's age, as before); with both halves restarted the
relay names nothing and the note decides alone, as before.

The stage sentence of `waiting_for_earlier_print` (`deliveries.py`) is now "Waiting for
the printer to show that no earlier print is about to start", which is true of a start
known to have gone, one that may have gone, and the start an unreadable note stood for.
The daemon's waiting log line no longer prints `None` for an unreadable note.

**Tests.** `test_a_damaged_note_is_settled_by_the_relays_word_on_the_start_it_stood_for`
(daemon restarts 10 s after the command with its note damaged; the print shows at 30 s; a
resend at 150 s prints at once, under 120 s including its 60 s print; the note is gone) and
`test_an_out_of_date_note_gives_way_to_the_relays_last_start` (a whole note naming an
older job is found by a restarted daemon; the next print starts at once). Before the change
both waited the full five minutes (elapsed 390 s and 360 s). With the change undone
(`mutate.py D5`) 4 tests of the fast suite fail. The safety side is held by the existing
restart tests and the property tests (none fails), and by item 1's test, whose note is
whole and names the relay's last start.

## 5. Silent time and the hold

**The code was made to match the guide** (three lines). `StartHold.watch` counts the time
since its last look only when that look is at most `FRESH_REPORT_SECONDS` (15 s) old. While
a delivery job watches a hold it looks every 2 s or 5 s, so the timed rule is unchanged
there; the gap between one job that stopped waiting and the next (nobody looking) is no
longer counted. The guide's sentence in "How a start is decided" now says both.

**Tests.** `test_time_nobody_watched_the_hold_is_not_counted` is review 6's sequence
(`r6_cancel.py`, last test: the relay restarts 20 s after the command, the printer is off
the network from 5 s to 400 s, a resend at 402 s, the print shows at 420 s): before the
change a second start command went at 402 s; now the second job is refused busy. A unit
test, `test_a_hold_counts_only_the_time_between_looks_close_together`, pins the bound.
With it undone (`mutate.py D4`) 4 tests fail.

## 6. Two log lines

**Done.**

- `PrinterLink.delete` asks the printer's listing first: a file it does not list is not
  deleted at all (so the FTP server's "550 No such file", which the library logs as a
  failure, never happens) and the answer is `NOT_ON_PRINTER`; the run loop then logs
  "the printer does not have NAME, so there was nothing to remove". It also no longer
  says "removed" when the listing cannot be read after a delete (it says it could not
  confirm). Tests: `test_a_file_the_printer_does_not_list_is_not_deleted_and_says_so`,
  `test_a_listing_that_fails_still_tries_the_delete` (`test_daemon_printer.py`),
  `test_a_file_that_never_reached_the_printer_is_not_said_to_be_removed`
  (`test_daemon_job_flow.py`), and in the simulated printer's suite, the refused upload
  logs that line and no `550`
  (`TestUploadRefused::test_a_file_that_never_arrived_is_not_deleted_and_the_log_says_so`,
  through the real library). With the log change undone (`mutate.py D6`) 3 fast tests and
  that simulated-printer test fail.
- `cmd_run` installs a SIGINT handler (`_InterruptOnce`) for as long as it runs: the first
  interrupt raises KeyboardInterrupt as before, every later one is ignored, and after a
  real interrupt SIGINT stays ignored until the process exits. Test:
  `test_several_interrupts_at_once_stop_it_quietly` (`test_daemon_cli.py`) sends real
  SIGINTs, one from the loop and three more during the shutdown; before the change the
  third escaped as a KeyboardInterrupt (it stopped the pytest run), now `run` returns 0 and
  the log ends with `stopping`. The guide's "Stopping" paragraph says so.

## 7. Remove the Raspberry Pi installer

**Done.** Removed `delivery/daemon/install.sh` (the service unit was written by it, inside
the script; there was no separate unit file) and `test_daemon_install.py`. Its package
checks (the one pin, the versions, the imports, the seam) are not about the installer and
moved, unchanged, to `daemon/tests/test_daemon_package.py`. The Makefile had no mention.

**Choice: everything that existed only for an install it made went too**, because the
ruling is that the daemon is a plain program started by hand and no machine has such an
install: the relay's `/install-printer.sh` route (`installer_path`, `INSTALLER_LIMIT`, the
plain-text refusal, four tests), and the daemon's hand-over to an install at
`/etc/penguincam-printer/config.toml` (`hand_to_service_user`, `restart_service`,
`paths.is_service_install`, the `/var/tmp/penguincam-printer` download folder, their
tests). `config.DEFAULT_CONFIG_PATH` is now `config.toml` in the default home. The guide
lost the installer paragraph, the route row and the limit; the docstrings of `config.py`,
`__init__.py`, `__main__.py` and their tests that spoke of a Pi, sudo, systemd or the
installer were rewritten. Two sentences a caller sees named the Pi and now name "the
computer next to the printer" (`relay.py`, the matching rules in `errors.py`, three tests):
`delivery.daemon_never_reported` and `delivery.printer_unreachable`. A search of
`delivery/` for `installer`, `install.sh`, `systemd` and `Raspberry` finds nothing outside
`uv.lock`.

**Not done, with the reason:** about fifteen code comments and test docstrings in
`relay_client.py`, `printer.py`, `relay.py`, `daemon_fakes.py` and three relay and daemon
test files still call the shop computer "the Pi" (for example "a small Pi" as the reason
the camera is never started). They are not about the installer and change no behaviour;
renaming them is a later sweep, left so as not to widen this change further.

## 8. The printer's certificate

**Done.** The hardware checklist's line "decide whether to pin it" is gone, and the
Upstream section's "a policy question" sentence is now the one sentence: "The daemon
accepts any certificate the printer presents, on MQTT and on FTPS alike." The simulated
printer's test of it no longer calls it an open point.

## 9. Terms

**Done.** `delivery/` had no "plate job", "HTTP face" or "Penguin Slicer". Every "copy"
left means duplicating bytes or a file (the relay's copy of a sliced file, copying the
tarball across, a copied configuration, a scratch copy). The one "copy" that meant an
instance was the `where` key of the error-report contract, which `contracts/` now names
`instance`; the two tests that pin that key (`tests/test_contracts.py`,
`relay/tests/test_relay_errors.py`) were changed to match.

## Not done

Nothing in the brief, but for the comments named under item 7. Out of scope as the brief says: the timed rule after a start command
and its two open limits, and daemon telemetry, are untouched.
