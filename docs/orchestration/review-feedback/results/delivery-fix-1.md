# Fixes for review 1 of printer delivery

Written Fri 2026-11-20 10:29 PT, from
[delivery-review-1.md](delivery-review-1.md), under [fix.md](../briefs/fix.md) and
[standing-rules.md](../briefs/standing-rules.md). Only `delivery/` and this file were
changed. Nothing was committed.

Every pytest run was started directly from `delivery/.venv/bin/python` under
`timeout -k 5` and a 3 GB address-space limit on pytest itself, on at most 2 workers.
Scripts and logs: `/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/delivery-fix-1/`
(`pt.sh`, `repeat.sh`, `repeat.log`, `cov.sh`, and the scratch copy `copy/delivery/` used
for the mutations, restored afterwards).

## Per defect

**1. Medium. A listing the daemon cannot read was taken as proof that the file was not on
the printer. Fixed.** `PrinterLink._listing(whole=True)` (`printer.py`) answers None when
the listing carries no list of lines or has a line `_LIST_RE` does not read. `delete`
uses it before and after the delete: `NOT_ON_PRINTER` only on a listing read whole, the
delete is sent otherwise, and an unreadable listing after the delete answers False
(not confirmed) instead of True. `remote_size` (the upload's check) still reads the lines
it can, as before.

- Choice: an empty list of lines is an empty folder, a true listing, so `NOT_ON_PRINTER`
  stands on it. The review counted "a listing with no lines" as unreadable; the
  simulated printer's empty folder answers `[]`, and treating that as unreadable failed
  `test_a_file_that_never_arrived_is_not_deleted_and_the_log_says_so` with a real
  `550 No such file` in the log, the very line item 6 of the builder's brief removed. An
  answer with no list at all (`('226 ...', None)`, the review's `empty_reply` case) is
  unreadable.
- Tests: `test_a_listing_the_daemon_cannot_read_is_no_proof_and_the_delete_is_sent`
  (four subtests: names only, another server's format, one odd line, no list; all four
  failed before the fix), `test_an_empty_folder_is_a_listing_the_daemon_can_read`,
  `test_the_size_check_skips_a_line_it_cannot_read`, all in
  `daemon/tests/test_daemon_printer.py`. The fake's `list_lines` sets the lines.
- The guide's hardware checklist line on the `LIST` format now says what an unreadable
  line does.

**2. Medium. Nothing tested that an overtaken note keeps the printer held. Fixed.** The
review's sequence H1 is
`test_an_overtaken_note_keeps_the_printer_held_for_the_relays_last_start[damaged]` and
`[out_of_date]` in `tests/test_start_decided.py`, in the fast suite (about 0.02 s each).
Under M3 (`_note_overtaken` sets `self.hold = None`) in the scratch copy both fail with
an overlap (a second start command while the first is pending) and nothing else in the
fast suite fails.

**3. Low. A slow answer from the relay stopped the hold's count. Fixed in code, the timed
rule otherwise unchanged.** `StartHold.watch` takes `asked_s`, the time the start wait
itself spent since the last look asking the relay whether it still holds the job; that
time is left out of the `FRESH_REPORT_SECONDS` gap limit and no more. `_await_start`
measures the ask and passes it to the next look. A gap nobody watched is still dropped,
and a picture that is not whole and fresh still counts nothing.

- Tests: `test_a_slow_hold_check_does_not_stop_the_holds_count`
  (`daemon/tests/test_daemon_run_loop.py`; every hold check takes 20 s and fails; before
  the fix the start timed out 1,048 s after the command, now within
  `START_SETTLE_SECONDS + HOLD_CHECK_SECONDS`), and two more assertions in
  `test_a_hold_counts_only_the_time_between_looks_close_together` (an ask's time counts;
  it excuses no more than itself).
- The guide, "How a start is decided", now says the ask's time is watched time.

**4. Low. The guide presented the fixed sequences as copies of what the random ones
catch. Fixed in the guide** (restoring the random sequences' reach was not cheap: it
means changing their strategies, and so their run time). The section "The property tests
are not in the fast suite" now names the seven faults both catch (G2, G9, G12, G13, N1,
N3, N7) and the two only the fixed sequences catch (G4, N2). Checked: with N2 put back
in the scratch copy (no `sending` note before the command), `test-properties` passes
(3 of 3) and the fixed sequence `N2-the-note-is-written-before-the-command` fails; the
review measured G4 the same way (M10).

**5. Low. "The Pi" in comments and docstrings. Fixed.** Every mention the review listed
now says "the computer next to the printer", "the daemon's computer" or "the daemon"
(`printer.py`, `relay_client.py`, `relay.py`, `daemon_fakes.py`,
`test_daemon_run_loop.py`, `test_relay_routes.py`, `test_relay_state.py`).
`git grep -i -E '\bpi\b|\bpi'"'"'s|raspberry' -- delivery` finds nothing.

## Suites

| Suite | Result |
|---|---|
| Fast suite, random order, 2 workers, 20 runs (seeds `5200 + 7919 * run`) | 20 of 20 passed, 1,113 tests and 160 subtests each; 3.9 s to 7.4 s with another agent working (an earlier set of 20, one test fewer, at load 0.2 to 1.5: 3.5 s to 4.4 s) |
| Properties (`-m properties -n 2`) | 3 passed, 5.4 s |
| Upstream check (`-m "upstream or simulator"`) | 56 passed (the simulated printer's 37 among them), 18.3 s |
| Branch coverage, fast suite | `printer.py` 97% (was 96%); `run_loop.py` 99%, `relay_client.py` 99%, `relay.py` 99%, every other module as in the review: not fallen |
