# Result: the owner's feedback applied to the slice service

Builder's record for [briefs/slice.md](../briefs/slice.md), under
[briefs/standing-rules.md](../briefs/standing-rules.md). Work done Fri 2026-11-20, 09:05 to
10:30 PT, in `slice/`, `contracts/`, the top-level [README.md](../../../../README.md) and
[CLAUDE.md](../../../../CLAUDE.md). Nothing was committed (the coordinator commits).

## Figures at the end

| Check | Result |
|---|---|
| Fast suite | 904 tests (858 before), 8.3 s on one process |
| `make -C slice test-flakes RUNS=20 WORKERS=2` | 20 of 20 passed, a new random seed each, 4.1 to 6.0 s a run |
| Branch coverage of the package (fast suite) | 100 %: 2,071 statements, 540 branches, 0 missed |
| Real-Orca suite (`tests_orca/`, one process, one Orca at a time) | 34 of 34 passed in 38.4 s (final run); an earlier run failed only on the summary's field order, fixed (the summary route no longer sorts its keys) |
| Search of my folders for the old terms | Only the deliberate ones listed under item 1 |

## 1. The renames

**Done.** Everywhere in `slice/` and `contracts/`, plus the two top-level files:

- Files: `contracts/plate-job.md` is now [contracts/plate-configuration.md](../../../../contracts/plate-configuration.md),
  `contracts/examples/plate-job.json` is `plate-configuration.json`,
  `slice/src/penguin_slice/plate_job.py` is `plate_configuration.py`,
  `slice/tests/test_plate_job.py` is `test_plate_configuration.py` (old files removed by
  literal path).
- Code: `PlateJob` to `PlateConfiguration`, `PlateJobRefused` to
  `PlateConfigurationRefused`, `read_plate_job`, `load_plate_job`, `slice_plate_job`,
  `run_plate_job` to `..._plate_configuration`, the keyword `job=` of
  `slice_plate_configuration` to `configuration=`, `PLATE_JOB_FIELDS`,
  `COPY_FIELDS` to `INSTANCE_FIELDS`, `MAX_COPIES` to `MAX_INSTANCES`,
  `MEMORY_PER_COPY_MB` and `TIME_PER_COPY_S` to `..._PER_INSTANCE_...`, `copy_matrix`,
  `copy_hull`, `copy_labels` to `instance_...`, `BAD_JOB_MESSAGE` to
  `BAD_CONFIGURATION_MESSAGE`, `ONE_COPY_MEMORY_REMEDY` to `ONE_INSTANCE_MEMORY_REMEDY`.
- Wire: JSON field `copies` to `instances` (the plate configuration and the summary),
  `where.copy` to `where.instance` in error reports (and in
  [contracts/error-report.md](../../../../contracts/error-report.md)), the placement
  problems' key `copies` to `instances` (also in `tests/fixtures/plate_cases.json`, which a
  user interface's twin reads), form field `plate_job` to `plate_configuration`, the log's
  `copies` to `instances`, error codes `slice.bad_plate_job` to
  `slice.bad_plate_configuration` and `slice.too_many_copies` to
  `slice.too_many_instances`.
- Prose: "HTTP face" to "HTTP interface", "Penguin Slicer" to "PenguinSlicer", "plate job"
  to "plate configuration" (and "slice job" where the work was meant).
- Student sentences, each read for a part with one instance: "An instance on the plate
  names a part this plate configuration does not include.", "This plate configuration
  could not be read: it has no instances.", remedies "Move the instance fully onto the
  plate, ...", "Move the instances further apart, ...". The timeout's remedy "Try again,
  or slice fewer instances at once." made no sense for one instance, so a plate of one
  instance now gets "Try again; if it is too slow again, simplify the part or split it in
  CAD." with no action, as out of memory already did.
- Test: the fast suite as a whole (every old name is gone, so any leftover fails to
  import); `tests/test_contracts.py` (document tables against the code, the README's
  contract row); `tests/test_plate_configuration.py::test_a_plate_of_one_instance_is_never_told_to_slice_fewer`.
- Choice: the example plate configuration's `stl` values became plain file names
  (`bracket.stl`), because the HTTP interface, now the only way in, takes only plain
  upload names; the files stay in `contracts/examples/parts/`.
- Deliberate old words left (the search's only hits): "copy" for duplicating bytes or a
  file (`shutil.copy`, `parent.copy()`, "a staged copy of install-orca.sh", "a scratch
  copy", "the BBL copy", `import copy as copying`, a test folder named `Copy`), and
  `X-Slice-Summary` in two tests that assert it is gone. The records under
  `docs/orchestration/penguin-slicer/` keep the old terms, as the rules say.
- **For the coordinator:** `delivery/tests/test_contracts.py` (line 67) and
  `delivery/relay/tests/test_relay_errors.py` (line 31) assert the error report's `where`
  keys are `{'part', 'copy', 'height_mm', 'stage'}`, read from
  `contracts/error-report.md`; the contract now says `instance`. Those two tests are in
  `delivery/`, which I may not touch; they fail until the delivery builder renames them.

## 2. One interface

**Done.**

- `python -m penguin_slice slice` is gone, with everything that existed only for it: the
  signal relay `_stop_on_signals`, `slice_once`, Ctrl-C handling during a slice and the
  stop notes on the command line (review defect 1 and open item 10 are moot). `serve` is
  the one command. A cancel always discards the file (through the job pool, as before).
- The package docstring, `service.py`'s and `web.py`'s docstrings and the guide present
  the HTTP interface as the only way in; `slice_plate_configuration` and
  `slicer.slice_plate` are described as code the interface and the tests call. The guide's
  "Use" shows `serve` and the example submitted with `curl`, then `events`, `summary`,
  `file`. `penguin_slice/__init__.py` no longer re-exports functions.
- Top-level [CLAUDE.md](../../../../CLAUDE.md): the quality bar says one interface per
  component is the default, not a hard rule, with the wizard and Onshape source cases;
  the file now names `6238/PenguinSlicer`, says every change reaches `main` through a pull
  request, says where specs, plans, research, the mockup and build records live
  (`docs/`), lists the make targets of both Makefiles as they stand, and states the terms.
  The top-level [README.md](../../../../README.md) rule "exercised from the command line"
  now reads "through its interface", pointing at the `curl` example.
- Tests: `tests/test_cli.py::test_usage_errors_exit_two` (`slice` is now a usage error),
  `test_module_entry_point_runs_serve`, the `serve` tests; the real-Orca suite's
  `test_the_http_interface_slices_the_contract_example` replaces the command-line slice.
- The guide's `curl` lines were run against `serve` on a spare port (8641) with the real
  Orca: 202, the event stream to `done`, the summary (3 instances, 200 layers), the file
  (172,936 bytes). That run found that the form field `plate_configuration=<file` must be
  quoted (the shell reads `<` as a redirect); the guide quotes it.

## 3. The summary leaves the header

**Done.** `GET /slices/<job>/summary` returns the summary as a JSON body, fields in the
contract's order. It shares one function (`finished`) with the file route, so both answer
404 `slice.unknown_job`, 409 with the slice job's own error report, 409
`slice.cancelled`, 409 `slice.not_ready` alike; and 410 `slice.file_gone` when the sliced
file has left the disk (choice: a summary of a file that is gone is not served). The file
route returns only the file; `X-Slice-Summary` is removed. Guide route table and
[contracts/sliced-file.md](../../../../contracts/sliced-file.md) updated.

Tests: `tests/test_web.py::TestSubmit::test_a_plate_configuration_is_sliced_and_its_file_fetched`
(no `X-Slice-*` header, the summary body and its field order),
`test_the_summary_of_25_warned_parts_is_a_body_not_a_header` (25 parts with
170-character names, each warned: headers under 1 kB),
`test_the_summary_answers_as_the_file_does_for_a_slice_job_without_one`,
`test_the_summary_of_a_sliced_file_gone_from_the_disk_is_gone_too`;
`tests/test_contracts.py::TestSlicedFile::test_the_summary_travels_in_no_header`.

## 4. Three small defects from the last review

- **Damage reported as "The slicer failed unexpectedly."** `read_summary`'s first open of
  the archive now catches `_ZIP_READ_ERRORS` (which include `NotImplementedError`), so a
  directory entry asking for zip version 23.5 is `slice.unreadable_output`, "The sliced
  file the slicer wrote is damaged.", retryable. Test:
  `tests/test_slicer.py::TestReadSummary::test_a_directory_entry_asking_for_an_unknown_zip_version_is_damage_worth_retrying`
  (it builds such a file by setting the entry's version byte).
- **A reused output folder handing back an old file.** `slicer._run_orca` removes the
  sliced file, its `.tmp` name, `result.json` and the debug log before starting Orca
  (`slice_plate` and `slice_stl` both pass their archive). A folder where the file was is
  `slice.scratch_unwritable` (choice). Tests: `tests/test_orca_runner.py::TestAReusedOutputFolder`
  (a timeout before Orca writes is `slice.timeout`, the old file and result gone; an old
  debug log is not read; `slice_stl` clears its archive; a folder in its place).
- **A memory ceiling with a digit that is not 0 to 9.** `limits.max_peak_mb` accepts unset
  or empty (the default) or 1 to 6 ASCII digits, not 0, and raises `limits.SettingError`
  naming `PENGUIN_SLICE_MAX_PEAK_MB` for anything else. `web.create_app` reads it first,
  so `serve` stops before it listens or makes its work folder, printing the message and
  exiting 2. Choice: a refusal at start, not a fall-back to the default (the brief says
  refuse); "0" and over six digits are refused too. Tests:
  `tests/test_limits.py::TestMemoryModel::test_ceiling_refuses_anything_but_plain_digits_and_names_the_setting`
  ("²", "٣", "１２", "1e3", " 900", "900\n", 30 digits and others),
  `tests/test_cli.py::test_serve_refuses_a_bad_memory_ceiling_at_start`,
  `tests/test_web.py::...::test_a_bad_memory_ceiling_stops_the_app_at_start`.

## 5. The peak memory in the log

**Done.** `OrcaExit.peak_kb` is now the watchdog's highest reading of Orca's process group
alone; `ru_maxrss` is kept on `OrcaExit.peak_rss_kb` but no longer reported (detail,
note, log, `SliceResult.peak_rss_kb`). Without more, the watchdog's 0.25 s cadence would
miss the pinned Orca's peak, which comes while it writes the sliced file in its last
150 ms; so the watchdog now also samples at once after every progress message (the
`--pipe` reader pokes the one sampling thread), and "All done, Success" arrives after the
file is written and about 30 ms before Orca exits. Measured: on the 6-hub plate the
watchdog's reading equalled Orca's `ru_maxrss` (266,400 kB both), and on the 100-spacer
plates both read the same. Limitation, stated in the guide ("The peak in the log"): a
spike after the last sample, in an Orca that ends by itself with no progress message
after it (a failure, typically), is not seen, so such a peak can be under Orca's true
peak. Tests: `tests/test_orca_runner.py::TestMemoryWatchdog::test_the_peak_reported_is_the_watchdogs_reading_of_orca_alone`,
`test_the_kernels_figure_never_reaches_the_peak_of_a_real_child` (64 MB held by the test
process: `ru_maxrss` counts it, the peak does not), `test_the_watchdog_samples_after_orcas_last_message`
(a cadence longer than any test: only the sample after "All done, Success" can see the
peak), `test_a_peak_over_the_ceiling_read_as_orca_exits_is_delivered_with_a_note`; real
Orca: `test_the_watchdog_sees_a_real_orcas_peak_through_its_high_water_mark` asserts the
reported peak is the watchdog's and reaches 98 % of Orca's `ru_maxrss`.

## 6. One process per instance

**Done.** The guide's "Use" says one instance of the slice service is one process, its
slice jobs live in that process's memory, several instances may run on one machine or
several, a client must keep talking to the instance that accepted its slice job, and a
server with several worker processes for one instance loses slice jobs (they answer
`slice.unknown_job`, which the error table now mentions). `web.py`'s docstring says the
same, and the top-level [CLAUDE.md](../../../../CLAUDE.md) has it as a gotcha. No test:
prose only.

## 7. Orca's reason for a failed slice, from its debug log

**Done, with a finding the brief did not expect.**

- Orca now runs with `--debug 3 --logfile <scratch>/orca.log` (level 3 is the lowest at
  which the pinned Orca logs `cli_status_callback` warnings; read in its source,
  `src/OrcaSlicer.cpp` of v2.4.2). One function at the seam, `slicer.orca_log_warnings`,
  reads the lines matching `LOG_WARNING_RE`, each once, at most 5, each cut to 300
  characters, at most 64 MB of log. `orca_failure` uses them only for `slice.orca_failed`:
  "The slicer could not slice this plate. It warned: <Orca's warning>", the warnings in
  the detail and the log's reason. A missing, unreadable or warning-less log keeps the
  general sentence. Fast tests: `tests/test_orca_runner.py::TestOrcasDebugLog` (the
  stand-in's new mode `general_warned`; missing, directory, empty, garbage and empty
  message logs; the bounds; a reason from `result.json` or stdout still wins).
- **Finding:** the thin, tall needle of the review (0.3 x 0.3 x 300 mm) does not log
  "floating regions" or any reason, even at `--debug 5`. Read in Orca's source: its real
  reason, "One object has an empty first layer and can't be printed", is thrown in
  `GCode.cpp`, collected into `SlicingErrors` whose text is "Errors", printed as `Errors`
  on stderr and lost; no file holds it. That part keeps the general sentence (truthful,
  as the brief requires); the guide says so. Patching Orca would be the only way to get
  it, and that is the owner's decision.
- The real-Orca test uses a part that does fail this way with its reason in the log: a
  20 x 20 x 5 mm block on a stem 0.4 mm across and 30 mm tall. Orca fails it with -100 and
  only its general `error_string`, and logs "It seems object Block #1 has floating regions.
  Please re-orient the object or enable support generation." (re-oriented, the block
  prints). `tests_orca/test_orca.py::test_orcas_reason_for_a_general_failure_is_read_from_its_debug_log`
  asserts the sentence, and its failure message says what to fix (`LOG_WARNING_RE` and the
  stand-in's `LOG_WARNING`); it also checks the stand-in's line against the regex.
- `make upgrade-orca` runs the upstream check: `scripts/upgrade_orca.py` step "upstream
  check" runs `make -C slice test-upstream` (pinned by
  `tests/test_upgrade_orca.py::test_upgrade_installs_beside_then_pins_regenerates_and_checks`,
  whose steps list ends with "upstream check"). Its failure message now says that each failing test's
  "Protects:" line and message name what to fix, naming the debug log's two places
  (`tests/test_upgrade_orca.py::test_a_failed_check_after_the_swap_says_how_to_go_back`).
  The guide's "Taking a new upstream version" says so.
- `slice/patches/orca/README.md` is removed, and every text proposing the patch is gone.
  The rule is one sentence in the guide: "A patch to Orca is the owner's decision". The
  upgrade command still stops when `patches/orca/` holds a `*.patch` file (its message no
  longer points at the removed note); the folder is now empty.
- The guide states the pin stays at 2.4.2, taking 2.5.x is known future work, blocked by
  the packed profile file `BBL.opc` the flattening script cannot read.
- Cost: a small plate's log is about 12 kB; the 100-spacer plate sliced in 6.2 s with it,
  inside the 6.4 to 7.1 s measured without it.

## 8. One hundred small instances

**Done. `MAX_INSTANCES` = 150.**

- The reference plate: `tests/helpers.py` `spacer_stl()` (a closed 216-triangle STL: round
  outside 5/8 inch across, hex hole for a 3/8 inch hex shaft, 1/8 inch thick; outside shape
  the coordinator's assumption) and `spacer_grid(100)` (10 by 10, 22 mm apart, centred).
  Nothing binary committed.
- Measured with the real Orca, one slice at a time, aarch64 Linux, 4 CPUs, default set
  (peak: the watchdog's reading; `ru_maxrss` read the same):

  | Spacers | Slices | Peak (MB) | Orca's time (s) | Sliced file (MB) |
  |---|---|---|---|---|
  | 100 | 6 | 488 to 513 | 6.2 to 7.1 | 1.81 to 1.82 |
  | 150 | 2 | 643 to 649 | 9.4 | 2.72 |
  | 196 | 2 | 815 to 829 | 12.5 to 12.6 | 3.55 |

  Choice: 150, more than a quarter of the 900 MB ceiling free; 196 came within 8 % of it.
  Figures in the guide's "Plate limits", next to the other limits.
- Limits derived from the instance count, each checked: the upload bound is now
  `MAX_PARTS x MAX_PART_BYTES` + 1 MiB (188,550,676 bytes, as before), with a new `MAX_PARTS` = 25
  different parts (`slice.too_many_parts`), since instances of one part share one file; a
  new `MAX_PLATE_TRIANGLES` = 3,750,000 (`slice.plate_too_detailed`), the most the old
  cap of 25 instances allowed, because one `<object>` per instance repeats the mesh and
  150 instances of a 150,000-triangle part would otherwise be a 1 GB plate file; the
  placement check (11,175 pairs for 150 instances on one spot, about 0.03 s) now lists at
  most 20 problems in the detail ("; and 11,155 more"), where the old code would have
  logged about 1.2 MB; the timeout (240 s) is twenty times the 150-spacer slice; the
  memory model estimates the 100 spacers at 507 MB (close), the time model at 36 s (five
  times too high; noted in the guide, not refitted: it only feeds `expected_s`).
  `scripts/measure_plate.py`'s full-small plate keeps its 25 hubs as `FULL_SMALL_HUBS`.
- Tests: `tests/test_service.py::TestRead::test_the_reference_plate_of_100_spacers_is_accepted`,
  `test_the_most_instances_of_spacers_are_accepted_and_one_more_refused` (150 accepted,
  151 refused with "This plate has 151 instances; the slicer takes up to 150 on one plate,
  so print the rest in a second job."), `test_too_many_different_parts`,
  `test_a_plate_with_too_many_triangles_in_all_is_refused`,
  `test_instances_piled_on_one_spot_give_a_bounded_detail`;
  `tests/test_web.py::...::test_the_reference_plate_of_100_spacers_is_accepted` (through
  `POST /slices`), `test_the_upload_bound_follows_the_parts_not_the_instances`;
  `tests/test_errors.py` produces both new codes; real Orca:
  `test_the_reference_plate_of_100_spacers` (through the HTTP interface, 100 objects) and
  `test_the_peak_of_the_reference_plate` (peak under 800 MB, no note).

## Other changes a reviewer should know

- New error codes `slice.too_many_parts` and `slice.plate_too_detailed`, listed in the
  guide and produced in `tests/test_errors.py`.
- The guide has a "Settings" table (the review's gap) and its "Modules" table lists
  `web.py` first as the way in.
- The fake Orca accepts and, in one mode, writes `--logfile`.
