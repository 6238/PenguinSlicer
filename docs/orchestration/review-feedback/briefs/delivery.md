# Brief: the owner's feedback applied to printer delivery

- **Deliverable (REQUIRED):** the changes below, in `delivery/` only, and a result file
  at `docs/orchestration/review-feedback/results/delivery.md` that lists, per numbered
  item below: what was done, the test that proves it, any choice you made, and anything
  not done with the reason.
- **Stop condition (REQUIRED):** every item is done or answered; the fast suite passes 20
  times in random order with 2 workers and takes about 4 seconds on a quiet machine; the
  simulated-printer suite and the upstream check pass; coverage has not fallen.
- **Budget (REQUIRED):** 120 minutes; no cloud spend.
- **Where this fits:** a fresh reviewer who never sees your result file will check the
  work, rerun the suites and break the code on purpose.
- **Inputs:** [standing-rules.md](standing-rules.md) first. Then `delivery/README.md` and
  the last review of printer delivery,
  [delivery-hardening-review-6.md](../../penguin-slicer/results/delivery-hardening-review-6.md),
  whose "Defects" and "Open" sections describe items 1 to 6 below and give the reviewer's
  sequence for item 1.

Do not touch `slice/`, `contracts/` or `docs/` (except your result file).

**Out of scope, on the owner's word:** the timed rule after a start command and the two
open limits that wait for the real printer (a daemon that could not watch, and a printer
slower than `START_SETTLE_SECONDS`). Leave that behaviour exactly as it is. Daemon
telemetry is also not part of this brief.

## 1. The missing test for the hold's timing

One fix of the last round (the hold counted some time twice after a restart) has no test
that fails when the fix is undone. Write that test from the reviewer's sequence. Undo the
fix in a scratch copy to see the test fail.

## 2. The fast suite returns to about 4 seconds

Three property tests take about 3.3 of the fast suite's 7 seconds. Move those three to
their own make target (`make -C delivery test-properties`), to be run before a commit and
by reviewers. In the fast suite keep fixed sequences written out by hand, one for each
fault the random sequences are known to catch (the review lists them; about eight).
Running fewer random sequences is not the remedy: it loses two of the faults.

## 3. A real bug must fail fast

When a real bug is introduced, a failing property test can spend minutes reducing its
example, and the 30-second limit on each test does not stop it. Bound the reduction so
that the properties target fails within about a minute for any bug, and say in the guide
what the bound is.

## 4. A damaged or out-of-date record of a start command

After the daemon restarts and finds such a record, the next print waits 5 minutes with a
message about an earlier print where there may be none. Fix it as the review describes,
without ever freeing a printer that a valid record says is held.

## 5. Silent time and the hold

The guide says time when the printer is silent never counts towards releasing the hold;
in one corner it does (nobody following the first delivery job, and the printer off the
network). Make the code match the guide if that is a few lines and does not change the
timed rule otherwise; if it is not, correct the guide's sentence. Say which you did.

## 6. Two log lines

- The daemon's log has a line that looks like an error, and says a file was removed, when
  a cancelled file was never on the printer. Reword it to say what happened.
- Several Ctrl-C at once can end the daemon's log with a Python error trace. Make the
  daemon stop quietly however many interrupts arrive.

## 7. Remove the Raspberry Pi installer

The owner's ruling: it was never tested and will not be needed. Remove
`delivery/daemon/install.sh`, its service unit, `test_daemon_install.py` and every
mention in the guide and the Makefile. The daemon remains a plain Python program started
by hand on Windows, macOS or Linux.

## 8. The printer's certificate

The owner's ruling: do not pin or check the printer's certificate. The guide keeps one
sentence saying the daemon accepts any certificate the printer presents. Remove any text
that presents this as an open decision.

## 9. Terms

Apply the renames of the standing rules to `delivery/`: prose, code and messages. Most
uses of "copy" here mean duplicating a file and stay.
