# Fixes to the slice service after review round 1

Fri 2026-11-20, finished 10:29 PT, on the uncommitted working tree. Review:
[slice-review-1.md](slice-review-1.md). Brief: [fix.md](../briefs/fix.md). Scratch scripts
and logs: `/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/slice-fix-1/`.

## Per defect

1. **Medium, the debug log blamed a sound part: fixed.** The log cannot tell which warning,
   if any, is why a slice failed, so the sentence no longer presents one as the reason.
   `slicer.SLICE_FAILED_WARNED_MESSAGE` is now "The slicer could not slice this plate. It
   also warned, though this may not be why it failed: {warnings}", with every warning found
   (at most 5, in order, each once), never "It warned:" alone. The detail lines are
   unchanged. Choice: one wording for every plate, also for a plate of one instance; even
   there a part can warn and fail for another reason, and the reviewer's alternative
   ("the only part on the plate") would still name a guess as the reason.
   Tests: fast `test_orca_runner.py::TestOrcasDebugLog::test_a_general_failure_adds_the_logged_warning_labelled_as_maybe_unrelated`
   and `::test_every_logged_warning_is_listed_and_none_is_presented_as_the_reason` (both
   failed before the change); real Orca
   `tests_orca/test_orca.py::test_a_sound_parts_warning_is_not_given_as_the_reason_another_part_failed`
   (the reviewer's mushroom, a 20 mm cap on a 3 mm stem, beside a 0.3 x 0.3 x 300 mm needle:
   the exact labelled sentence with the mushroom's "floating cantilever" warning, the needle
   named nowhere) and the block-on-a-stem test updated to the new sentence. Guide: the
   "Orca's debug log" paragraph states the limit with the mushroom case; the
   `slice.orca_failed` row is updated; the `slicer` docstring says so too.
2. **Low, no test held the log reading to `slice.orca_failed`: fixed.**
   `TestOrcasDebugLog::test_a_failure_orca_names_by_its_return_code_ignores_the_log`, one
   case per code of `ORCA_RETURN_CODES` other than -100 (-101, -52, -50), a warning in the
   log, the code's own sentence asserted and no log line in the detail. With the guard
   replaced by `if True` all 3 cases fail; restored, they pass.
3. **Low, stray `result.json` in the root: answered.** Already removed by the coordinator
   (checked: absent). No `.gitignore` entry: no code path starts Orca there (the review
   showed it), so it recurs only from a hand run, and ignoring it would hide that sign.
   I ran Orca only through the test suites and the slice service's own code.
4. **Low, `MAX_PLATE_TRIANGLES` rests on no measurement: fixed by removal.** No
   measurement shows a value that refuses before the watchdog and never refuses a plate
   that slices (the reviewer's 100 knobs at 1.98 M triangles, about half the cap, were
   stopped by the watchdog at 922 MB; 25 hubs at 0.5 M slice at 842 MB), so the cap, its
   sentence `PLATE_TOO_DETAILED_MESSAGE`, the code `slice.plate_too_detailed`, its check in
   `service.read_plate_configuration`, its tests and its rows in the guide and in
   [plate-configuration.md](../../../../contracts/plate-configuration.md) are gone.
   `MAX_PARTS` stays at 25; the guide, the contract's limits table and the comment in
   `limits.py` say it bounds the upload (188.5 MB) and is not a measured limit.
   New test `test_service.py::TestRead::test_no_cap_on_the_triangles_of_the_whole_plate`
   (150 instances of a part at the part cap, 22.5 M triangles, are accepted by the reader);
   `test_limits.py::test_instance_and_part_caps` asserts the cap is absent.
   Measured for the guide, no Orca run (`plate3mf_worst.py` in the scratch folder): the
   largest plate the service now accepts, 150 instances of a 149,760-triangle hub, takes
   24.4 s to write as the plate 3MF, 263 MB on disk, the service's resident memory 132 MB.

## Concern, not fixed (outside the review's list)

With the cap gone, the slice service's own work before Orca starts grows from about 4 s
and 45 MB (the reviewer's 4 M triangles) to 24 s and 263 MB of scratch disk for the
largest plate accepted, which the watchdog then stops within seconds. The guide states the
figure. Whether a cancel during the writing of the plate 3MF is prompt was not checked.

## Suites

| Suite | Result |
|---|---|
| Fast suite, 20 runs, random order, 2 workers (each run under `timeout 300`, 6 GB address limit) | 20 of 20 passed, 906 tests each, 3.8 to 5.1 s (load 0.8 to 3.1) |
| Branch coverage of the package | 100 % (2,066 statements, 538 branches, none missed) |
| Real-Orca suite (`tests_orca`, one Orca at a time, `-p no:randomly`) | 35 passed in 46.7 s |

Test count: 904 before, minus 3 for the removed cap, plus 1 for defect 1 (the other
defect 1 test replaces an old one), plus 3 cases for defect 2, plus 1 for the absence of
the cap: 906.
