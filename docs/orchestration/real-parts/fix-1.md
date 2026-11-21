# Fix 1: the review's defects in the real parts' work

Run of Fri 2026-11-20, 18:15 to 19:05 PT, against [review 1](review-1.md), [the
brief](brief.md) and [the standing rules](../review-feedback/briefs/standing-rules.md),
with the coordinator's rulings. Branch `tests/real-frc-parts`; nothing committed. Folders
touched: `slice/` and `contracts/` only. Scratch scripts and logs:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/real-parts-fix-1/`
(`measure.py` slices a pair of real parts with the placement check left out, `sweep2.sh`
runs a list of pairs, `trace.py` slices a plate and records every reading of the memory
watchdog, `gcode_diff.py` compares two sliced files apart from the named fields). One real
Orca at a time throughout; Orca always ran in its own scratch folder.

## Defect 1 (serious): the flaky one-CPU byte-identity test. Fixed.

- **Removed** `test_the_mixed_plate_slices_to_the_same_gcode_every_time` and its helpers
  (`VARYING_LINES`, `VARYING_ENTRIES`, `FIRST_LAYER_TIME`, `without_varying_fields`) from
  `slice/tests_orca/test_frc_parts.py`.
- **Kept** what is stable, pinned on every run of the upstream check for every plate it
  slices, now in both supports settings for the target plates:
  `test_the_real_parts_slice_through_the_http_interface` (layers exact, print time and
  filament within 2 %, warnings exactly the true ones, every instance's first layer within
  1 mm of its outline).
- **The slice service's own determinism moved to the fast suite:**
  `tests/test_frc_parts.py::test_the_slice_service_hands_orca_the_same_plate_every_time`
  writes one plate configuration's plate 3MF twice and compares every entry byte for byte
  (0.04 s: the pulleys and spacers of plate four-each-a).
- **Guide corrected** (`slice/README.md`, "The same plate, sliced again"): Orca's G-code is
  not byte-identical between slices of the same plate on any number of CPUs; the fields
  that vary (time stamp, object ids, `.md5`, `first_layer_time`, `prediction`, sometimes
  the object order of `model_settings.config`); the extrusion order from Orca's threads,
  with measured sizes (6,254 to 13,236 of four-each-a's 1,063,416 lines with supports on,
  2,931 to 8,965 of them extruding moves; other plates listed there); that one CPU does
  not remove it (the review's 1 failure in 3); that summaries, warnings and placements are
  stable and tested.

## Defect 2 (serious): supports on, closeness. Fixed.

**Measured gaps** (pairs of real parts side by side or one behind the other, the
placement check left out, one slice each, Fri 2026-11-20 18:26 to 18:35 PT; 81 slices):

| Pair | Supports off | Supports on: refused at | Supports on: sliced at |
|---|---|---|---|
| two Elevator Block Tops, one behind the other | 1 mm slices | 5, 7, 7.5 mm | 8, 8.5, 9, 11 mm |
| a Top with a Carriage behind it | 1 mm slices | 5, 7, 7.5 mm | 8, 8.5, 9 mm |
| two Elevator Top Inners side by side | 1 mm slices | 5, 7, 7.5, 8 mm | 8.5 (twice), 9 mm |
| two Elevator Top Inners one behind the other | | 5, 7 mm | 8, 8.5, 9, 10 mm |
| Tops side by side; Tops turned 90°; Bottom Inners and Carriages both ways; Top before a Bottom Inner; Top Inner beside a Top or Carriage; pulleys; clamps; spacer before a Top | 1 mm slices (those tried) | none | 5 mm and up |

Every refusal was -101 with the debug log line `gcode path conflicts found between X and
Y`. So with supports off 1 mm sliced every pair tried (9 pairs, incl. turned 90°), and with
supports on 8.5 mm sliced every pair tried.

- **(a) The spacing depends on supports.** `plate.SPACING_SUPPORTS_MM` = 12 mm (8.5 mm
  measured plus 3.5 mm, about 40 %); `SPACING_MM` stays 5 mm (1 mm measured plus 4 mm).
  `plate.plate_from_printer(printer, supports)` picks the spacing; `service.read_plate_configuration`
  works out supports before the plate. The refusal is `slice.placement_too_close` at the
  checking stage, before Orca: "Box #1 and Box #2 are closer than 12 mm, the room supports
  need between instances.", `where` naming both (`instance`, new `other_instance`), remedy
  "Spread the instances out (or press Arrange), turn supports off, or move some instances
  to a second plate, and slice again." Contracts: `SPACING_SUPPORTS_MM` in
  [plate-configuration.md](../../../contracts/plate-configuration.md)'s limits and checks
  (`test_contracts.py` holds it), `other_instance` in
  [error-report.md](../../../contracts/error-report.md). Tests:
  `test_plate.py::test_the_spacing_depends_on_supports`,
  `test_with_supports_the_plate_asks_for_the_larger_spacing`,
  `test_errors.py::test_with_supports_on_the_placement_check_asks_for_the_supports_spacing`;
  real Orca: `tests_orca/test_frc_parts.py::test_the_placement_checks_spacing_is_enough_for_orca`
  (the tightest pairs exactly 12 mm apart with supports on, 5 mm with them off: both slice).
- **(b) When Orca still refuses.** `slicer.orca_log_conflicts` reads the pair from the
  debug log (`LOG_CONFLICT_RE`, through the one log reader `_log_lines`); `slicer._too_close`
  makes the sentence "Elevator_Block_Top #1 and Elevator_Block_Top #2 are too close
  together: the slicer found that their paths would meet, most likely their supports,
  which need more room between instances." (the supports clause only when they are on),
  `where` `instance` and `other_instance`, up to 5 pairs in the detail, remedy with "turn
  supports off" when supports are on, else "Spread the instances out (or press Arrange), or
  move some instances to a second plate, and slice again." No pair in the log: "Two
  instances are too close together: ...". Tests: fake Orca's new mode `refuse_logged`
  (`test_errors.py::test_orcas_too_close_names_the_pair_from_its_debug_log`, 3 cases),
  `test_slicer.py::test_the_pairs_orca_found_too_close_are_read_in_one_order_and_bounded`;
  real Orca: `test_orca_names_the_pair_whose_supports_meet` (two Tops 5 mm apart, supports
  on, the check's spacing lowered) and `test_orca.py::test_overlapping_instances_are_refused_by_orca`
  (pins the log line and `fake_orca.CONFLICT` against it).
- **(c) The examples leave the larger gap, and the target plates slice with supports on.**
  The old four-each-a (12 blocks) cannot take 12 mm: two Tops and two Bottom Inners in a column
  are 292.1 mm of footprints plus three 12 mm gaps, 328.1 mm, over the 314 mm the margins
  leave. Re-split, still 4 of each part on 2 plates: each plate holds 2 of every part
  (blocks in two columns Top, Bottom Inner, Carriage with a pulley above each; small parts
  in two columns beside), four-each-b is four-each-a mirrored; every gap 13 to 14.2 mm. The team plate
  was re-spaced (Carriage and pulleys moved; every gap 14.2 mm or more). Every example plate
  passes the placement check with supports on (`test_frc_parts.py`, parametrized over
  supports). Both target plates slice with supports off and on through the HTTP interface
  (`test_the_real_parts_slice_through_the_http_interface[four-each-a/b-on/off]`): with
  supports on no warning, 1,368 to 1,415 MB.
- **Not in my folders:** the wizard mockup's Arrange (`docs/mockups/print-wizard/js/plate.js`,
  `settings.js`: `spacing: 5`) leaves 5 mm whatever the supports. The contract now says a
  user interface that arranges must leave `SPACING_SUPPORTS_MM` with supports on; the
  mockup needs that change (another agent's folder).

## Defect 3 (medium): host sizing. Fixed (guide, "Sizing the host").

Measured with `trace.py` (every watchdog reading), MB of 1,024 kB:
- Stopped at the default ceiling (2,048,000 kB): twelve Bottom Inners 12.5 mm apart with
  supports on, readings 2,144,504 and 2,226,800 kB at the stop (94 and 175 MB over). The
  same plate at a 3,000 MB ceiling: 2,307 MB peak, 34.3 s.
- Largest rise between two consecutive readings over all plates measured: 514,268 kB
  (502 MB in 0.26 s, on that plate); on the target plates up to 308 MB.
- Worst case: ceiling + one rise, about 2,500 MB of Orca, plus 400 MB of service = 2,900 MB.
  Host: 3.5 GB (3,584 MB) for the slice service, about a fifth of headroom.
- Ceiling kept at 2,000 MB: the target plates need at most 1,415 MB with supports on. The
  only supports-on plates that need more are full plates of one block (twelve Bottom
  Inners: refused with `slice.out_of_memory`, remedy a second plate). Raising the ceiling
  for them would put Orca's worst case past the 2.5 GB this 5 GB container allows; not done.
  Note that even at 2,000 MB the measured worst case (about 2.5 GB) is at that limit; the
  suites' plates peak at 1.45 GB at most.

## Defect 4 (low): figures disagree. Fixed.

Each figure is now given once, with its plate: the guide's table in "The team's real
parts" (new slices: three or four of each plate, both supports settings, Fri 2026-11-20
18:36 to 18:47 PT), the `limits.py` comment points there and quotes only the 1,415 MB of the
target and the 1,410 MB of a full block plate, both from that table. The parsing time is
0.17 to 0.19 s (three runs) in both `tests/test_frc_parts.py`'s docstring and the guide's
Tests section. The real-Orca suite's `MEASURED_SLICES` and `MEASURED_SLICES_SUPPORTS` are
the same slices' figures.

## Defect 5 (low): warnings' edge cases. Fixed, each with a test (`test_slicer.py::TestReadSummary`).

- One normaliser for both sources (`slicer._warning_text`: strip, cut to 300):
  `test_a_long_warning_in_both_sources_is_listed_once`.
- The sort key never converts digits (length without leading zeros, then digits) and
  breaks ties on the text: `test_a_run_of_thousands_of_digits_neither_fails_nor_misorders`,
  `test_warnings_that_differ_only_in_leading_zeros_come_in_one_order` (also asserts a
  strict order of the keys).
- The whole log is read (up to 64 MB) and the first of the order kept, bounded while
  reading (`slicer._first_in_order` holds at most 600):
  `test_past_the_bound_the_warnings_kept_are_the_first_in_order_not_the_first_logged`.
- Hand mutations, each reverted after: no tie-break (4 tests fail), `int()` in the key (1),
  no normaliser on `result.json` (2), stop reading at the bound (2), the spacing not
  following supports in the service (1), the supports clause inverted (4).

## Defect 6: not a defect (coordinator). README wording left as it is.

## Suites

- Fast suite: 972 tests. 20 runs in random order on 2 workers, pytest bounded directly
  (`timeout 300 prlimit --as=8 GB`, the same command as `make test-flakes`): 20 of 20
  passed, 4.56 to 5.63 s a run (load 1 to 3); after the last test change, 20 more runs:
  20 of 20, 4.37 to 5.14 s. About 4.4 to 5 s against the brief's 4 s: the new fast tests
  cost about 0.25 s (the eight parts' reading 0.17 to 0.19 s once per worker, the plate 3MF
  test 0.04 s).
- Branch coverage of `penguin_slice` under the fast suite: 100 % (2,139 statements, 558
  branches, none missed).
- Real-Orca suite (`tests_orca/`, pytest bounded directly, one Orca at a time): three runs
  in a row, 53 passed each, in 144.3 s, 147.7 s and 150.8 s; the real parts' tests about
  110 s of that. Worst first-layer placement error 0.4692 mm on every plate, both supports
  settings.

## Choices

- `SPACING_SUPPORTS_MM` 12 mm: the measured 8.5 mm plus about 40 %, since tree supports
  depend on the part's overhangs and only eight parts were measured.
- The target split: 2 of every part on each plate (two plates alike, mirrored), which also
  lowers the heavier plate's peak (869 to 911 MB with supports off, against the old
  four-each-a's 1,388 to 1,393 MB in the review; 1,415 MB with supports on).
- `other_instance` added to `where` rather than a list, so `instance` keeps its meaning.
- The -101 pair is put in natural order within the pair (Orca writes the second first).
