# Review of the slice service after the review-feedback changes, round 1

**Verdict: FIX, 4 defects (0 serious, 1 medium, 3 low).**

Reviewed Fri 2026-11-20, about 10:05 to 11:05 PT, on the uncommitted working tree
(`git diff main -- slice contracts README.md CLAUDE.md` plus the untracked new files). The
builder's result file was not opened. Builder's brief: [slice.md](../briefs/slice.md);
review brief: [review.md](../briefs/review.md). Scratch scripts and logs are under
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/slice-review-1/`.
The container has 4 CPUs and 5 GB; the delivery reviewer was running suites in the same
checkout throughout, so "quiet" below means a load average under 1.

## Figures measured

| What | Measured | The guide says |
|---|---|---|
| Fast suite, 20 runs, random order, 2 workers | 20 of 20 passed, 904 tests each, 0 failures | passes |
| Fast suite wall time | 4.17 s at load 0.74 (quiet); 4.1 to 5.7 s at load 2 to 3; 10 s at load 4.5 | seconds |
| Branch coverage, every module of the package | 100 % (2,071 statements, 540 branches, none missed) | 100 % |
| Real-Orca suite (`tests_orca`), one Orca at a time | 34 passed in 32.8 s | passes |
| 100 spacers, peak | 504 MB (suite), 512 MB (through HTTP), 514 MB (direct, machine loaded) | 488 to 513 MB |
| 100 spacers, Orca's time | 6.1 to 6.6 s (quiet); 15.9 s while the flake runs shared the machine | 6.2 to 7.1 s |
| 100 spacers, sliced file | 1.81 MB, 13 layers, 100 objects | 1.81 to 1.82 MB |
| 100 spacers, supports on | 487 MB, 9.3 s | not stated |
| 150 spacers | 651 MB, 2.72 MB, 150 objects (16.2 s, machine loaded) | 643 to 649 MB, 2.72 MB |
| 100 knobs of 19,836 triangles, 16 mm across (1.98 M triangles, 53 % of `MAX_PLATE_TRIANGLES`) | stopped by the watchdog at 922 MB after 27.9 s, `slice.out_of_memory` | not measured |
| 100 knobs of 39,928 triangles (3.99 M, over the cap; sliced past the check) | stopped by the watchdog at 933 MB after 4.4 s; the plate 3MF took 4.0 s to write and is 45 MB | not measured |

## 1. Each item of the builder's brief

| Item | Verdict | Evidence |
|---|---|---|
| 1. Renames | Done | Old-term search below; `contracts/plate-configuration.md`, `plate_configuration.py`, `PlateConfigurationRefused`, field `instances`, `MAX_INSTANCES`, form field `plate_configuration`. A request with the old form field `plate_job` or the old field `copies` gets `slice.bad_plate_configuration` with a sentence naming the field (run against the live service). |
| 2. One interface | Done | `python -m penguin_slice` has `serve` only; `slice x.json --out o` exits 2 with usage (`test_cli.py::test_usage_errors_exit_two`). The guide's "Use" presents only the HTTP interface. The package `__init__` exports nothing. A cancel always discards (undone in the scratch copy: 2 tests fail). `CLAUDE.md` has the four additions asked for and its target table matches both Makefiles. |
| 3. Summary leaves the header | Done | `GET /slices/<job>/summary` returns the body; the file answer's largest header was 51 bytes and has no `X-Slice-Summary`. Unknown, failed, cancelled, running, and gone-from-disk all answer as the file route does (live run and `test_web.py`). |
| 4a. Damaged sliced file | Done | `slice.unreadable_output`, "The sliced file the slicer wrote is damaged.", `retryable` true; undone: 2 tests fail. |
| 4b. Old file after a stop | Done | `_run_orca` removes the sliced file, its `.tmp`, `result.json` and `orca.log` first; undone: 4 tests of `TestAReusedOutputFolder` fail. |
| 4c. Memory ceiling digits | Done | `[0-9]{1,6}`, not 0; refused at start with exit 2 and a message naming the setting. 16 hostile values tried (`٣`, `²`, `１２`, ` 900`, `900\n`, `+900`, `9e2`, `0x10`, `000000`, `1000000`): each refused or read correctly. Undone: 3 tests fail. |
| 5. Peak in the log | Done | `OrcaExit.peak_kb` is the watchdog's reading only; the guide states the limitation (a spike after the last sample). Undone (the kernel's figure mixed back in): 5 tests fail. The real-Orca suite printed the watchdog's reading reaching Orca's own `ru_maxrss`. |
| 6. One process per instance | Done | Guide "Use", `web.py` docstring, `CLAUDE.md` gotcha. |
| 7. Reason from the debug log | Done, with defect 1 | See "Item 7 with the real Orca" below. `patches/orca/README.md` is gone, the guide keeps the one sentence on patches, states the pin at 2.4.2 and what blocks 2.5.x. `upgrade_orca.py` runs `make test-upstream` and its failure message names `LOG_WARNING_RE`. |
| 8. One hundred instances | Done, with defect 4 | `MAX_INSTANCES` 150; 100 accepted and 151 refused in the fast suite; reference plate in `helpers.spacer_stl` and `spacer_grid`; upload bound `MAX_PARTS x MAX_PART_BYTES` (188.5 MB). |

**Fifteen changes undone by hand in a scratch copy** (three batches, the copy's own package
on `PYTHONPATH`, 2 workers). Noticed by the suite: the stale-file removal, the ASCII-digit
rule, the watchdog-only peak, `retryable` of `slice.unreadable_output`, a cancel keeping a
complete file, the summary's gone-from-disk answer, the upload bound, `>` to `>=` on each of
the three plate caps, the debug log's read bound, the tail of `LOG_WARNING_RE`, the
"each once" rule, and the summary's `cancelled` answer. **Not noticed (1):** with the guard
`if error_code == "slice.orca_failed"` in `slicer.orca_failure` replaced by `if True`, all
904 tests still pass (defect 2).

## 2. Terms

Searched `slice/`, `contracts/`, `README.md`, `CLAUDE.md` for `copy`, `copies`,
`plate job`, `plate_job`, `plate-job`, `HTTP face`, `Penguin Slicer`, `MAX_COPIES`,
`PER_COPY`, `X-Slice-Summary`, `slice_plate_job`.

- `copy` left, each meaning to duplicate, right to leave: `mesh.py:187` (`parent.copy()`),
  `test_service.py:2` (`import copy`), `shutil.copy` in two tests, "a staged copy" and "a
  scratch copy" in the guide and `upgrade_orca.py`, "the BBL copy" and a folder named `Copy`
  in `test_flatten_orca_profiles.py`, "its own copy of each filament" in
  `flatten_orca_profiles.py`, `install-orca.sh:218`.
- `X-Slice-Summary` left only in `test_web.py:96` (a comment on why) and
  `test_contracts.py:135` (asserts its absence): right to leave.
- No file name holds an old term. `slice/patches/orca/` is an empty folder (untracked by
  git), which the guide still refers to as the place a patch would stop the upgrade.
- Notes, not counted as defects: the class `JobPart` (`plate_configuration.py:19`) is a
  name left from "plate job"; `service.load_plate_configuration` still reads a path and
  falls back to the current directory, which only tests use now that the command is gone;
  `tests_orca/test_orca.py:616` reads "a instance".

## 3. Flakes and speed

`flakes.sh` ran pytest directly from `slice/.venv` under `timeout 300` and a 6 GB address
limit, `-n 2`, a fresh seed per run. Seeds: 2406054154, 3758219481, 3544157903, 3372874194,
1641708651, 3173965677, 2661465616, 2922742288, 526613710, 2829203405, 712242038,
2628691233, 1663138350, 1646698239, 736182212, 1258295996, 279243862, 1539470923,
3549486638, 2338597110. All passed. Ten slowest (run 1, quiet): 0.32 s
`test_a_dense_part_at_the_triangle_limit_is_read`, 0.18 s `test_a_good_file_with_bytes_changed`,
0.17 s `TestMeasurePlate::test_measure_reports_a_row_through_the_slice`, 0.17 s
`test_any_coordinates_in_one_triangle`, 0.10 s
`test_the_three_ways_orca_can_end_on_a_signal_are_distinct`, 0.09 s
`test_the_summary_answers_as_the_file_does_for_a_slice_job_without_one`, 0.08 s
`test_a_good_file_cut_or_padded`, 0.08 s (setup) `test_a_dense_part_at_the_triangle_limit_is_read`,
0.07 s `test_the_most_instances_of_spacers_are_accepted_and_one_more_refused`, 0.07 s
`test_random_bytes`.

## 4. Coverage

`coverage run` over the fast suite (data file in the scratch folder): every module 100 %
branch: `__main__` 45 statements, `errors` 33, `jobs` 270, `limits` 55, `mesh` 185, `plate`
61, `plate_3mf` 62, `plate_configuration` 69, `print_config` 108, `service` 290, `slicer`
709, `web` 184.

## 5. The other suites

`tests_orca`, run directly under `timeout 560`, `-p no:randomly`: 34 passed in 32.8 s, no
Orca process left. Slowest: the reference plate 6.6 s, its peak 6.3 s, the high-water test
4.4 s.

## 6. Error reports

Every answer of the live service that was not a success was checked for `code`, `message`,
`remedy`, `retryable`, `detail`: 18 of 18 conformed (unknown job, hostile job id, wrong
method on the summary route, old form field, old field, 151 instances, 26 parts, no body, a
JSON body, JSON nested 100,000 deep, an upload named `../x.stl`, summary and file of a
failed, a running and a cancelled slice job). The three new codes each have an entry in
`test_errors.py` and a row in the guide:

- `slice.too_many_instances`: "This plate has 151 instances; the slicer takes up to 150 on
  one plate, so print the rest in a second job." True, useful, action `lower_quantities`.
- `slice.too_many_parts`: "This plate uses 26 different parts; the slicer takes up to 25 on
  one plate, so print the rest in a second job." True and useful.
- `slice.plate_too_detailed`: "This plate is too detailed to slice: its instances have N
  triangles in all, over the 3,750,000 one plate may have." True as a rule; see defect 4.

## 7. The guide against the code

Followed "Use" by hand on port 18640 with the real Orca: the `curl` submission of
`contracts/examples/plate-configuration.json` answered 202; the event stream ended `done`;
the summary came back as JSON in the contract's field order
(`Bracket_plus1-20261009-1432.gcode.3mf`, 3 instances, 200 layers); the file was 172,933
bytes. Routes, statuses, settings and make targets named in the guide exist and behaved as
written. Not rechecked: the figures of the memory model's table, the record of the upgrade
to 2.5.1 and back, and the last paragraph's "7 tests in 54 s".

## 8. Hostile cases

- **HTTP** (`hostile_http.py`): no traceback, no hang. A cancel of a running 150-spacer
  slice job ended `cancelled` in 1.5 s; summary and file both answered `slice.cancelled`
  then and after a second cancel; no Orca was left. A cancel after `done` answered
  `finished` and changed nothing.
- **The debug log** (`hostile_log.py`, the real `orca_log_warnings` and `orca_failure`):
  missing, empty, a directory, cut mid-message, cut before `flag`, a blank message, an
  `update:` line, a `NON_CRITICAL` note, a progress callback with `warning_step=-1`, and a
  warning 5,000 characters long all leave the general sentence. A 216 MB log with the
  warning at its end is read for 0.34 s and gives no warning (the 64 MB bound); one 150 MB
  line with no newline takes 0.06 s. Seven warnings give five. No reason was ever stated
  that the log did not hold. Control characters in a logged message pass into the sentence
  unchanged; only Orca writes that file, so this is a note.
- **The stray `result.json`** in the repository root: defect 3.

### Item 7 with the real Orca

| Plate | Reason found in the debug log? | Sentence |
|---|---|---|
| (a) Block on a 0.4 mm stem ("floating regions") | Yes | "The slicer could not slice this plate. It warned: It seems object Block #1 has floating regions. Please re-orient the object or enable support generation." The advice is sound: with supports on it sliced (145 layers), and on its side it sliced. |
| (b) Needle 0.3 x 0.3 x 300 mm | No | "The slicer could not slice this plate." The log (12,634 bytes) holds only "found slicing or export error for partplate 1"; stdout holds "Errors". |
| Needle 0.5 x 0.5 x 200 mm | No | The general sentence. |
| Needle 0.2 x 0.2 x 100 mm | Not needed | `slice.print_empty`, from Orca's stdout. |
| A part that slices alone with a "floating cantilever" warning, beside the needle | A warning, about the wrong part | "The slicer could not slice this plate. It warned: It seems object Mushroom #1 has floating cantilever. ..." (defect 1) |

The guide tells the truth about (a) and (b): it names the needle as a failure whose reason
reaches no file. It does not say that a warning found in the log may belong to a part that
is not why the slice failed.

### The three limits

- **`MAX_INSTANCES` = 150:** justified by measurement, and I reproduced it (100 spacers 504
  to 514 MB, 150 spacers 651 MB against a 900 MB ceiling). It does not refuse the 100
  spacers. It is not what protects memory: 100 small detailed parts were stopped by the
  watchdog.
- **`MAX_PARTS` = 25:** not from a measurement; it bounds the upload (188.5 MB) and is what
  the old limit of 25 instances already implied, so no plate that was accepted before is
  refused. Five detailed organic parts are 5 parts and about 0.5 M triangles: neither new
  limit refuses them (the guide's own table says three such bodies already reach 825 MB, so
  the watchdog decides).
- **`MAX_PLATE_TRIANGLES` = 3,750,000:** not from a measurement (defect 4).

## Defects

1. **Medium. The debug-log reading can blame a part that is not why the slice failed.**
   `slicer.orca_failure` puts the first warning in the log into the student's sentence
   whenever Orca's failure is the general one. Evidence (`item7.py`, real Orca): a
   mushroom-shaped part slices alone, with the warning "It seems object Mushroom #1 has
   floating cantilever" in its summary; on a plate beside a 0.3 mm needle the slice fails
   because of the needle, and the sentence is "The slicer could not slice this plate. It
   warned: It seems object Mushroom #1 has floating cantilever. Please re-orient the object
   or enable support generation." The same happened with the corpus' `self_intersecting.stl`.
   The student is sent to re-orient a sound part and the needle is never named. Fixed
   means: the sentence does not present a logged warning as the explanation when it may not
   be (wording that says the warning may be unrelated, or the warning kept to the detail
   unless every part that warned is the only part on the plate), a real-Orca test with a
   warned sound part beside a failing one, and the guide's "Orca's debug log" paragraph
   stating the limit.
2. **Low. No test holds the debug-log reading to `slice.orca_failed`.** With the guard in
   `slicer.orca_failure` replaced by `if True`, the 904 tests pass; a plate Orca refuses
   with -101 or -50 would then read "The slicer could not slice this plate. It warned: ..."
   in place of its own sentence. Fixed means a fast test with a return code of
   `ORCA_RETURN_CODES` other than -100, a warning in the log, and the code's own sentence
   asserted.
3. **Low. A stray `result.json` in the repository root, untracked and not ignored.** It is
   byte for byte what the pinned Orca writes into its working folder on any run without
   `--outputdir` (`orca-slicer --help` in an empty scratch folder gave an identical file).
   Its time is Fri 2026-11-20 09:35:50 PT. Nothing in the code can write there: every
   place that starts Orca sets the working folder (`slicer.run_process` uses the slice's
   own folder, the upstream check's help test uses `tmp_path`, `install-orca.sh` changes to
   a smoke folder), and a service started with the repository root as its working folder
   ran four slice jobs without touching it. So it came from a hand run of Orca in the root.
   Fixed means it is removed before the commit.
4. **Low. `MAX_PLATE_TRIANGLES` rests on no measurement, and the guide's reason for it is
   not shown.** The guide says the cap means "many instances of a detailed part cost Orca
   no more than before". Measured: 100 instances of a 16 mm knob of 19,836 triangles, 53 %
   of the cap, pass every check, slice for 27.9 s and are then stopped at 922 MB with
   `slice.out_of_memory`; nothing between that and the cap can slice under the default
   ceiling with 100 instances, so the cap never decided anything in what I measured. It
   refused no ordinary plate. Fixed means the guide and the comment in `limits.py` say the
   cap is a bound on the service's own work (the plate 3MF: 45 MB and 4 s at 4 M
   triangles), not a measured memory limit, and that the watchdog refuses detailed
   many-instance plates first; or the cap is set from a measurement.
