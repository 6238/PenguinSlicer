# Review 3 of printer delivery after the review-feedback changes

Written Fri 2026-11-20 11:52 PT. Reviewed: the uncommitted changes under `delivery/` in
`/repos/popcornpenguins/penguin-slicer` (`git diff main -- delivery`, 39 changed paths and
2 new test files) after the fix round that followed [review 2](delivery-review-2.md),
judged against [review.md](../briefs/review.md),
[standing-rules.md](../briefs/standing-rules.md) and the builder's brief
[delivery.md](../briefs/delivery.md). No builder's result file was opened. No tracked file
was changed except this one: `git status --short -- delivery` lists the same paths before
and after.

## Verdict

**FIX, 2 defects: 2 low.**

Round 2's defects 1, 2 and 4 are fixed at their cause, each with a test that fails when
the fix is undone. Defect 3 is half fixed: "the shop computer" is gone, but the same
computer still has two names. The new delete is sound: it is always sent, the log line is
taken from the printer's answer, nothing the library reports as an error is lost, and no
delete is ever sent after a start command, exactly as on `main`. What is left is one
wording corner of the warning line and the two names. **I judge the change fit to merge
with the two defects below listed as known open items.**

Scratch files are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/delivery-review-3/`.
The previous reviewer of this round left scripts there (`pt.sh`, `pm.sh`, `hp.sh`,
`mk.sh`, `repeat.sh`, `cancel_probe.py`) and two scratch copies, `copy/delivery/` and
`main/delivery/`. I checked that `copy/delivery/` matches the working tree
(`diff -rq`, no difference), read each script before running it, and reran everything
myself; none of its logs is used here. Mine are `delete_probe.py`, `mut3.sh`, the
mutation copy `mut3/delivery/`, `hold_probe.py` (copied from review 2's folder) and the
`probe-*.out`, `m3-*.log`, `repeat-*.log` and `make-*.log` files.

Every pytest run was started from `delivery/.venv/bin/python` under `timeout -k 5` and an
address-space limit on pytest itself, on at most 2 workers; the make targets ran through
`make` under `timeout` and a 4 GB address-space limit. The slice reviewer was running
tests on the same machine throughout, so **no timing here was taken on a quiet machine**;
each says its load.

## What was not checked

- The Ctrl-C handling, the removal of the installer, the certificate sentence and the
  routes' limits: unchanged since review 2, which checked them.
- That a bug put in on purpose fails the properties target within about a minute: review 2
  measured 3.6 s to 8.1 s and the property code is unchanged since; not rerun.
- `make hardware-smoke` and `make upgrade-printer-library` (a real printer, the network).
- Real firmware: how the H2S words its answer to a `DELE`. Everything below rests on
  ftplib's own `delete` with the socket replaced, and on the fakes.

## (a) Round 2's four defects

| Round 2's defect | Verdict | Undone in `mut3/`: what the suite says |
|---|---|---|
| 1. A listing taken as proof of absence, so no delete sent | Fixed: `PrinterLink.delete` never lists; it always sends the delete | Mutation A (a listing that lacks the name answers `NOT_ON_PRINTER` with no delete): 7 fail, among them `test_a_file_the_printer_does_not_have_is_said_so_from_its_answer`, `test_a_200_is_a_confirmed_delete_as_ftplib_takes_it` and the upstream check's `test_a_delete_returns_the_reply_or_logs_and_swallows_the_printers_answer` |
| 2. "removed X" for a file never there | Fixed: `REMOVED` only on a `250` or `200` | Mutation B (`NOT_ON_PRINTER` logged as "removed"): 1 fails, `test_a_file_that_never_reached_the_printer_is_not_said_to_be_removed`. Mutation D (any `550` is "no such file"): 3 fail. Mutation E (the match case-sensitive): 4 fail |
| 3. One computer, three names | Half fixed: "shop computer" has no match under `delivery/`; two names remain | Defect 2 below |
| 4. Step 5 of the walk names stages the stream does not show | Fixed: README lines 123 to 132 say the stream goes `waiting_for_daemon`, `starting`, `printing` and why the stages between are not seen, which is what review 2 saw | (prose) |

Mutation C (the library's log not captured during the delete, so its `550` line reaches
the daemon's log): 7 fail, among them the upstream check. Each of the five mutations was
noticed by the fast suite; B is the only one the upstream check does not notice, and it
needs not to (it is in the run loop).

## (b) The delete, attacked

`delete_probe.py` drives `PrinterLink.delete` through the real `bambulabs_api`
`PrinterFTPClient.delete_file` and ftplib's `delete`, with only the socket replaced, and
renders the run loop's log line for each answer.

| Answer to `DELE` | Outcome | Log line | True? |
|---|---|---|---|
| `250 …`, `200 OK` | `removed` | "removed X from the printer" | Yes |
| `550 no such file or directory`, `550 NO SUCH FILE`, `550 File not found`, `550-No such file` (multi-line) | `not_on_printer` | "X was not on the printer" | Yes |
| `550 Could not delete file.`, `550 Datei nicht gefunden`, `550 文件不存在`, `553`, `450`, `421`, `226`, `150`, `hello` | `unconfirmed` | "warning: could not confirm that X was removed from the printer (it answered: …)" with the reply | Yes |
| A socket timeout, a reset, an SSL error | `unconfirmed` | "… (it answered: timed out)", "(it answered: [Errno 104] Connection reset by peer)" | The printer did not answer: defect 1 |
| A dropped connection (`EOFError`) | `unconfirmed` | "… (it answered: )" | Empty: defect 1 |
| A refused connection, a `530` login | `unconfirmed` | "… (it answered: no connection: …)" | As above, defect 1 |
| An empty reply | `unconfirmed` | "(it answered: )" | Not reachable through ftplib (an empty line raises) |

No case raised and none printed a traceback; nothing was forwarded to the daemon's log as
"printer library said". The answer in another language is a warning, never "not on the
printer", which is the safe side. One contrived reply, `550 Permission denied: user not
found`, is read as "no such file" because the pattern accepts its words anywhere after
`550`; no printer is known to answer so, and the delete was sent anyway, so I do not grade
it.

**Does the suppressed line hide a real error?** No. During a delete the whole of the
library's log on that thread is captured: its four INFO lines (dropped before this change
too, being below WARNING) and the one `Failed to execute function: <e>` line, which comes
back as the answer in the warning. The probe shows a library error on the same thread
after the delete is forwarded again, and one from another thread (the MQTT thread) during
the delete is forwarded at once. A delete inside an upload's capture would drop that
capture, but `upload` stops its capture in a `finally` before any delete can run.

**A cancel at each moment** (`cancel_probe.py`, the real `RunLoop` on a fake clock), run on
the change and on `main`'s copy: **the 16 outputs are the same, word for word**. Before
the upload, the delete is not sent; mid-upload, after the upload, a gate answering
`cancelled` or `unknown`: the delete is sent and the job ends `delivery.cancelled` (or
unacknowledged on `unknown`). After the start command, under eight shapes (the printer
printing, idle, unreachable; the relay answering `cancelled` or `unknown`; the command
raising; the command refused): **no delete is ever sent**. The thirteen call sites of
`_remove_from_printer` are the thirteen of `main`, all before `printer.start` in
`_start`; `_await_start` and `_settled` have none.

## (c) Behaviour after a start command

Review 2's `hold_probe.py` (35 cases of a slow, failing or vanishing relay and of an
ignored, silent or late start) gives the same output on the change and on `main`'s copy
(`diff`, no difference). In `git diff main` no removed line of
`test_start_decided.py`, `test_daemon_run_loop.py`, `test_link_faults.py` or
`test_simulated_printer.py` is an assertion about the hold; the one assertion removed is
`assertTrue(link.delete(...))`, replaced by the outcome and the answer.

## (d) Suites, flakes, speed, coverage

- **Fast suite, 20 runs**, random order, 2 workers, seeds `31337 + 7919 * run`: **20 of
  20 passed**, 1,120 tests and 168 subtests each. pytest's own time 4.42 s to 9.52 s at a
  load of 1.9 to 3.2 (the slice reviewer's tests and my mutation runs alongside).
- `make test-parallel`: 1,120 passed, pytest 4.49 s, load 1.3. `make slowest` (one
  worker): 5.91 s, load 1.3; the slowest test 0.34 s, the ten 0.34, 0.21, 0.15, 0.11, 0.10,
  then 0.06 s each, the first five in `tests/test_link_faults.py`.
- `make test-properties`: 3 passed, 5.68 s, load 1.6. `make test-sim`: 37 passed, 18 s,
  load 1.4. `make test-upstream`: 57 passed (one more than round 2: the new delete
  check), 17 s, load 1.3.
- `make coverage`, branch coverage per module, against review 2:

| Module | Now | Review 2 |
|---|---|---|
| `run_loop.py` | 99% | 99% |
| `printer.py` | 97% | 97% |
| `start_record.py` | 96% | 96% |
| `__main__.py` | 98% | 98% |
| `config.py` | 97% | 97% |
| `relay_client.py`, `relay.py`, `routes.py` | 99% | 99% |
| `deliveries.py` | 98% | 98% |
| `paths.py`, `app.py`, `caller.py`, `errors.py`, `limits.py`, `sliced_files.py` | 100% | 100% |

No line of the new `delete` is missed. Coverage has not fallen.

## (e) The guide read as a newcomer

- **delivery job**: defined at README line 212 and used as that throughout; the many bare
  "job" are the same thing in context and in code names (`job_id`).
- **start command**, **hold**: one name each in the guide. One older slip, already on
  `main`: the `delivery.start_refused` reason says "the print start command"
  (`errors.py` line 257, `run_loop.py` line 1158). Not graded.
- **The computer the daemon runs on**: "the computer next to the printer" (README line 8,
  every student sentence in `errors.py` and `deliveries.py`) and "the daemon's computer"
  (README lines 45, 528, 1199, 1204, and comments in `config.py`, `printer.py`,
  `relay_client.py`, `relay.py`, `run_loop.py`, `start_record.py`, `daemon/pyproject.toml`
  line 11, `daemon_fakes.py`, `tests/test_link_faults.py` lines 733 and 737). The guide
  never says these are one thing: defect 2.
- The guide's delete sentences (step 5 of "The daemon's side of a delivery job", lines 430
  to 434, the walk's step 7, and the hardware checklist at line 1146) match the code.

## Defects

1. **Low. The warning for an unconfirmed delete says "it answered" when the printer gave
   no answer, and shows nothing for a dropped connection.** Evidence (`delete_probe.py`):
   a socket timeout logs "(it answered: timed out)", a refused connection "(it answered:
   no connection: [Errno 111] Connection refused)", and a connection dropped during the
   `DELE` (ftplib's `EOFError`, whose text is empty) "(it answered: )". The outcome is
   right in each (a warning, nothing hidden); only the sentence is untrue. Fixed when the
   line says "it answered: <reply>" only for a reply from the printer and otherwise names
   what happened ("no answer: timed out", "the connection dropped"), with a test of the
   dropped connection.

2. **Low. One computer still has two names.** "The computer next to the printer" and
   "the daemon's computer" name the computer the daemon runs on (places listed under (e)).
   Round 2's defect 3 asked for one; the fix removed the third. Nothing a student reads
   uses the second name. Fixed when one name is used in `delivery/` (the student sentences
   already use "the computer next to the printer").
