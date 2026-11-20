# Fixes for review 2 of printer delivery

Written Fri 2026-11-20 11:00 PT, from [delivery-review-2.md](delivery-review-2.md) and the
coordinator's rulings on its four defects. Only `delivery/` was changed, and nothing was
committed. The behaviour after a start command is unchanged.

Scratch files are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/delivery-fix-2/`:
`pt.sh` (pytest from `delivery/.venv` under `timeout -k 5 300` and a 3 GB address-space
limit), `repeat.sh` with `repeat-1.log` to `repeat-20.log`, and `walk.sh` with the walk's
logs in `walk/`.

## Defects 1 and 2: deleting a cancelled file

**Fixed.** Defects 1 and 2 were fixed together, as the ruling asked.

- `PrinterLink.delete` (`daemon/penguin_delivery_daemon/printer.py`) no longer asks for a
  listing. It always sends the delete for the name it was given, as `main` did, and
  returns `(outcome, the printer's answer)`. The outcome is one of:
  - `REMOVED`: the library returned the server's reply, and that reply is 250 or 200 (what
    ftplib takes as success).
  - `NOT_ON_PRINTER`: the printer answered a 550 that says there is no such file ("no
    such file", "not found", "does not exist").
  - `UNCONFIRMED`: every other answer. That covers a 550 that says something else (for
    example `550 Delete operation failed.`, which is what vsftpd answers for a missing
    file), a 4xx, an unexpected reply, no answer at all, a refused connection (`no
    connection: ...`), and no printer.
- The library swallows a failed delete and logs it as `Failed to execute function: <reply>`
  at ERROR. While the delete runs, that log is captured, the way the upload's already was.
  It becomes the answer and never reaches the daemon's log as `printer library said:`.
- The listing check of the last round (`_listing(whole=...)`) is removed. `remote_size` is
  back to the code `main` has.
- `RunLoop._remove_from_printer` writes its log line from the outcome:
  - `removed <name> from the printer` for `REMOVED`;
  - `<name> was not on the printer` for `NOT_ON_PRINTER`. The line has no warning, no
    error and no 550 in it;
  - `warning: could not confirm that <name> was removed from the printer (it answered:
    <answer>); it is harmless there, but can be deleted on its screen` for
    `UNCONFIRMED`, with no traceback.
- Choice: the daemon's log has no levels, so "warning level" means a `warning:` prefix, in
  the same way the log already uses `error:` and `WARNING:`.
- Tests:
  - In `test_daemon_printer.py`:
    - `test_a_delete_the_printer_confirms_is_removed`
    - `test_a_file_the_printer_does_not_have_is_said_so_from_its_answer` (the delete is
      sent and nothing is forwarded to the log)
    - `test_the_answer_decides_and_no_listing_is_asked`: defect 1. The name is listed in
      upper case, or the listing is empty, missing or failing, and the delete is still
      sent and answers `REMOVED`.
    - `test_a_file_never_there_is_not_said_removed_whatever_the_listing`: defect 2.
    - `test_any_other_answer_is_a_delete_that_could_not_be_confirmed` (six answers)
    - `test_a_200_is_a_confirmed_delete_as_ftplib_takes_it`
    - `test_delete_never_raises`
    - `test_a_delete_with_no_printer_never_raises`
  - In `test_daemon_job_flow.py`, one test for each of the three log lines. Each asserts
    that the delete was sent and that the log has no `Traceback`.
  - In `test_upstream_printer_library.py`,
    `test_a_delete_returns_the_reply_or_logs_and_swallows_the_printers_answer` runs four
    answers through ftplib's own `delete` and the library's `delete_file`.
  - In `test_simulated_printer.py`, the real library against the simulated printer: `250
    Deleted.` gives `REMOVED`, a second delete gives `NOT_ON_PRINTER`, and in the
    `upload_refused` scenario the log says the file was not on the printer and has no
    `550` in it.
  - In `test_together.py`, one test for the stand-in's answers.
- Every fake was moved to the new return shape: `daemon_fakes.FakePrinter`,
  `FakeBambuPrinter.delete_file` (which now behaves like the library) and
  `together/stand_in.py`.
- Two mutants, each tried and then undone. Putting a listing check back before the delete
  fails 9 tests. Taking any 5xx as "no such file" fails 3.
- The guide changed in three places:
  - the walk's step 7 names the new line;
  - pipeline step 5 says how the line about a removal is worded;
  - the hardware checklist line about a 550 for a file that never arrived is replaced by
    an open line: the H2S's answer to a delete for a file it does not have.
- The walk's step 7 was run against the code (`walk.sh`), and the daemon's log said
  `sample_part-jf52df952.gcode.3mf was not on the printer`.

## Defect 3: one name for the daemon's computer

**Fixed.** Each file now uses "the computer next to the printer" at its first mention and
"the daemon's computer" after that. The changes:

- `README.md`: line 8 (was "a computer in the shop"), line 45, "the computer's clock", and
  both mentions of "the shop computer";
- `daemon/pyproject.toml` lines 7 and 11;
- `scripts/upgrade_printer_library.py`;
- `tests/test_link_faults.py`, both lines;
- `tests/test_upgrade_script.py`, the test's name and its docstring.

Same-kind names found next to the listed ones, also fixed: "a computer on the shop's
network" (`__init__.py`), "this computer" (`relay_client.py` message, `run_loop.py`,
`start_record.py`), "that computer", "a computer" and "the same computer" (`config.py`),
"the computer" (`__main__.py`), "a small computer" (`daemon_fakes.py`, `printer.py`).
Left as they are: "on one computer" in the guide's "Try it on one machine" (any computer,
not the daemon's computer); the relay's student messages, each of which opens with "The
computer next to the printer"; and the test helper `Shop` in `test_link_faults.py`, which
stands for the whole shop rather than the daemon's computer.

## Defect 4: the stages in the walk's step 5

**Fixed in the guide. No code change, because no stage is skipped by a bug.**

- What the code does:
  - The daemon sends its stage on a sync at most once a second (`PROGRESS_SYNC_SECONDS`,
    `RunLoop._progress_due`). Only the latest stage goes, so a stage that lasts less than
    a second can be overwritten before it is sent.
  - The relay sets `starting` itself when the daemon asks its start gate (`relay.py` line
    714).
  - `waiting_for_printer` is set only while the daemon has no fresh report and waits for
    one (`run_loop.py` line 901). With a simulated printer that answers, it never waits
    there.
- What the walk showed: step 5 was run three times, and each time the stream showed
  `waiting_for_daemon`, `starting` and `printing`, then `done`, after 21 s to 22 s. The
  stage became `starting` 0.2 s after the job was taken. Step 7 showed
  `waiting_for_printer`.
- The guide's step 5 now names the three stages that are seen. It says why `downloading`
  and `uploading` are not seen: the sample's 323 bytes take less than the second between
  two syncs. It also says when `waiting_for_printer` does show, and points to step 7.
  Step 7 now says the report's stage is `waiting_for_printer` or `uploading`.

## The suites

| Suite | Result |
|---|---|
| Fast suite, random order, 2 workers, 20 runs (seeds `7001 + 4099 * run`) | 20 of 20 passed, 1,119 tests and 168 subtests each. pytest's own time was 3.88 s to 7.21 s at loads of 1.2 to 2.7, with the other agent's work running |
| `make test` (one worker) | 1,120 passed in 5.82 s (the stand-in test added after the repeat runs) |
| `make test-parallel` | 1,120 passed in 3.51 s, load 0.8 |
| `make test-properties` | 3 passed in 5.06 s |
| `make test-sim` | 37 passed in 18.28 s |
| `make test-upstream` | 57 passed in 16.29 s (one new upstream test) |
| `make test-together` | 2 passed in 1.61 s |
| `make coverage` | The same figure as review 2 for every daemon and relay module: `printer.py` 97%, `run_loop.py` 99%, `start_record.py` 96%, `__main__.py` 98%, `config.py` 97%, `relay_client.py` 99%, the rest unchanged. `together/stand_in.py` is at 92%, and its delete is fully covered |

Every make target was run through `make` under `timeout` and a 4 GB address-space limit.
