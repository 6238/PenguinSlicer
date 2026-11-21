# Review 1: the real parts in the slice service's tests

**Verdict: FIX (2 serious, 1 medium, 3 low).**

Reviewed Fri 11-20 around 18:00 PT, on the uncommitted working tree of branch
`tests/real-frc-parts` (`git diff main -- slice contracts`, plus the untracked
`slice/tests/fixtures/frc-parts/`, `slice/tests/frc_parts.py`, `slice/tests/test_frc_parts.py`
and `slice/tests_orca/test_frc_parts.py`). The builder's result file was not read. Every figure
below comes from a command run for this review, one real Orca at a time, on the container's
4 CPUs and 5 GB (load 1.8 to 4.9 from other agents). Scratch scripts and logs are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/real-parts-review-1/`
(`slice_one.py` slices one plate of `tests/frc_parts.py` through
`service.slice_plate_configuration`, `hostile_logs.py` feeds hostile debug logs to
`slicer.plate_warnings`, `compare_sliced.py` compares sliced files apart from the named
varying fields).

## Check 1: the parts' folder and README: PASS, with one low defect

- `sha256sum` of the eight files in `/repos/popcornpenguins/PartsFRC/` and of the eight in
  `slice/tests/fixtures/frc-parts/` gives identical checksums pair by pair (for example
  `19e59b00…2827b` for Clamp Plate Inner, `db902cd5…6144a` for Elevator Block Bottom
  Inner). The sizes match too. The renames are lower case with hyphens.
- The README says the parts belong to "the Popcorn Penguins (FRC Team 6238)". It says the
  team printed every part and uses them on the robot. It lists every original file name
  and carries the standard MIT text with "Copyright (c) 2026 Popcorn Penguins, Inc.".
  `test_every_part_is_in_the_folder_with_its_licence_note` asserts the copyright line and
  every original name.
- Defect 6: the README calls MIT "the licence of this repository". The repository has no
  licence, and `git grep -i licen` finds none.

## Check 2: the mentor's target: PASS (supports off)

Run with the real Orca at the default ceiling (`PENGUIN_SLICE_MAX_PEAK_MB` unset; `env`
holds no `PENGUIN_` variable).

| Plate | Through | Result | Peak (MB) | Orca (s) | Warnings |
|---|---|---|---|---|---|
| four-each-a (16) | HTTP interface, real-Orca suite | done, worst first-layer error 0.4692 mm over 16 instances | | | 16 |
| four-each-a, 3 separate slices | `slice_one.py` | done, no `memory_note`, no `stop_note` | 1,388 to 1,393 | 18.9 to 19.2 | 16, the same list each time |
| four-each-b (16) | HTTP interface, real-Orca suite | done, worst first-layer error 0.4600 mm over 16 instances | | | 4 |
| four-each-b, 3 separate slices | `slice_one.py` | done | 401 to 408 | 11.0 to 11.2 | 4, the same list each time |

Both plates hold 4 instances of every part, each in its printing orientation and none
turned (`test_the_two_plates_hold_four_instances_of_every_part`). The placement check
passes both plates. No slice was refused, and the watchdog stopped none.

The warnings are true. Orca warns "floating cantilever" for the three Elevator Blocks and
the Elevator Top Inner, and "floating regions" for the pulley. Orca warns of nothing for
the two clamps and the spacer. In each part's printing orientation, `overhangs.py` finds
2,080 to 3,582 mm² of faces looking down (within 45°) above the plate on the blocks and
the Elevator Top Inner, starting 0.3 mm up. It finds 187 mm² on the pulley, starting
4.76 mm up, and none on the clamps or the spacer. That is the geometry each warning
describes.

## Check 3: supports on: FAIL (defect 2, serious; memory part acceptable)

Each plate the real-Orca suite slices, run again with `"supports": "on"`:

| Plate | Result |
|---|---|
| alone, each of the 8 parts | done (peaks 97 to 321 MB), no warnings |
| mixed | done, 756 MB |
| team | done, 600 MB |
| four-each-b | done, 670 MB |
| **four-each-a** | **refused after 16.4 s: `slice.orca_too_close`** (ran twice, the same both times) |
| two Elevator Block Tops, one behind the other, gap 5 mm and 7.45 mm | **refused: `slice.orca_too_close`** |
| the same pair at 8.5, 10, 12, 15 and 20 mm | done |
| the same pair at 5 and 7.45 mm, supports off | done |
| full Elevator Block Bottom Inner, 3 x 4, gaps 10 mm | **stopped: `slice.out_of_memory`** at a reading of 2,140,316 kB, ceiling 2,048,000 kB, after 25.9 s |

So the failure is not limited to the full target plate. **Any two Elevator Block Tops
closer than somewhere between 7.45 and 8.5 mm are refused once supports are on.** The
placement check passes such a plate, because its `SPACING_MM` is 5 mm whatever the
supports.

What the student is told for the too-close refusal:

```
"message": "Parts are too close together; spread them out."
"remedy": "Move the instances further apart, or press Arrange, and slice again."
"where": {"stage": "slicing"}
```

The sentence is true but not useful:

- It names no instance, although Orca's debug log does:
  `gcode path conflicts found between Elevator_Block_Top #2 and Elevator_Block_Top #1`.
  `result.json`'s `error_string` only says "G-code conflicts detected after slicing ...
  try moving the wipe tower", and the slice service reads only that.
- It does not say the cause is the supports. The same plate slices with supports off.
- On plate A, "Move the instances further apart" cannot be done: the columns already
  fill 313 mm of the 314 the margins leave. "Press Arrange" helps only if the arranger
  spaces wider than the check's 5 mm.

The student also waits 16 s for a refusal that the checks could have given before Orca
ran.

**The right fix** has two parts:

1. **A spacing check with supports on.** Add a supports spacing to the contract (for
   example `SPACING_SUPPORTS_MM`, measured; 10 mm passes the Tops pair above), used by
   the placement check whenever supports are on. The refusal is then an ordinary
   `slice.placement_too_close` at the checking stage, naming the pair and saying "with
   supports on", before any Orca runs.
2. **A true report for what still reaches Orca.** For return code -101, read the
   `gcode path conflicts found between A and B` line from the debug log (the one place
   the log is read, `orca_log_warnings`'s reader). Put the two instances in `where`, and
   say in the sentence that their paths (supports or brims) meet. When supports are on,
   the remedy should offer turning supports off or moving one instance to a second plate.

The memory side is acceptable. The full plate with supports on is stopped with a true
sentence ("the slicer needed more than the 2,000 MB of memory the print server allows")
and a useful remedy (remove some instances, or use a second plate). The estimate in the
log already predicted it (2,399 MB). Raising the ceiling to let it through is not
allowed: with the service's 400 MB it would pass the owner's 2.5 GB (see check 5). The
guide reports both supports facts honestly. The too-close part is still a defect,
because the brief counts a refusal of a plate of real parts as a defect in the slice
service, and the slice service's own check passed this plate.

## Check 4: the warnings fix: PASS for real Orca output, with one low defect

- **The real parts:** the mixed plate gives 5 warnings, four-each-a 16 (12 blocks and
  4 pulleys) and four-each-b 4. In three separate slices of each plate, and in the
  suite's run, every list was identical (`uniq -c` counts 3 for each). Each list has
  each instance once, in natural order (`#2` before `#10`). With supports on, no plate
  warns.
- **Mutations by hand** (in a copy of the source, run with `PYTHONPATH` pointing at it):
  - Dropping `result.json`'s warnings from `plate_warnings` fails
    `test_warnings_come_from_result_json`.
  - Sorting without `_natural` fails
    `test_every_warning_in_the_debug_log_is_kept_once_in_one_order`.
- **Hostile debug logs and `result.json` (`hostile_logs.py`), where the code holds:**
  - Duplicates in log and `result.json`, and 10,000 copies of one warning: each comes
    once.
  - Whitespace around a warning in `result.json`: merged with the log's copy.
  - Invalid UTF-8 and a NUL: kept, replaced, no crash.
  - A line longer than `MAX_LINE_BYTES` with a forged warning in its tail: not taken.
  - A message that contains `, message_type=2, flag=32`: handled.
  - Empty messages: dropped.
  - A `result.json` that is a list: no warnings.
  - Superscript digits (`²`): no crash, because `\d` does not split them.
  - 400 distinct warnings: bounded to 300.
- **Where the code does not hold** (defect 5, low): the two sources are not cut and keyed
  alike.
  - A warning over 300 characters appears **twice**: once full from `result.json`, once
    cut to 300 from the log.
  - A run of 5,000 digits in `result.json` makes `_natural` raise `ValueError` (Python's
    4,300-digit limit), so `read_summary` fails on a good slice.
  - Two warnings that differ only in leading zeros (`Block 007`, `Block 7`, `Block 07`)
    come in an order that changes with `PYTHONHASHSEED`. Seed 1 gave
    `007, 07, 7`; the default seed gave `007, 7, 07`.
  - Past 300 distinct warnings, the 300 kept are the first found in the log, so which
    300 depends on the order of Orca's threads. The contract promises "the same list
    every time".

  None of these is reachable with today's instance labels (ASCII, at most 40
  characters, `#n` without leading zeros) and at most 2 warnings an instance. Only a
  changed or hostile Orca reaches them.

## Check 5: the 2,000 MB ceiling: the value is supported; the host sizing is not (defect 3, medium)

- **Supported.** The target plate A peaks at 1,388 to 1,393 MB in my slices. That is over
  the old 900 MB and leaves 600 MB free under 2,000, so the mentor's target needs a
  ceiling of about 1,400 or more. The full plates without supports peak at up to 1,410 MB
  (the builder's figure, not rerun). Pulleys pass 2,000 only beyond about 95 instances,
  which no team plate needs. 2,000 MB plus the service's 400 MB is 2.4 GB, inside the
  owner's 2.5 GB.
- **The sizing is not truthful.** The guide sizes the host "for 400 MB of the service
  beside Orca's ceiling: 2.4 GB". Orca's memory is not bounded by the ceiling:
  - The watchdog samples every 0.25 s. My stop of the full Bottom Inner plate with
    supports read 2,140,316 kB, which is 92 MB (decimal) over the 2,048,000 kB ceiling.
  - The guide's own section "What the ceiling guarantees" says a plate whose spike comes
    at the end is **delivered** over the ceiling, and Orca's own peak for that plate is
    2,319 MB (the guide's table).
  - So Orca's real worst on a 2,000 MB ceiling is about 2.1 to 2.3 GB, and the host needs
    about 2.5 to 2.7 GB, not 2.4. That is at or past what the owner allowed.
  - "2,000 MB" is also 2,000 MiB in the code (2,048,000 kB), while the guide's "2.4 GB"
    reads as decimal.

## Check 6: consistency: the variation is confirmed; the test meant to pin what is stable is flaky (defect 1, serious)

- **Confirmed: Orca's G-code varies on several CPUs.** Three separate slices each of
  mixed, four-each-a and four-each-b, compared with the varying fields of
  `tests_orca/test_frc_parts.py` removed:
  - Every pair differs in `Metadata/plate_1.gcode`.
  - four-each-a: 21,437 changed lines of 1,204,922, of which 16,190 are extrusions other
    than `M73`. four-each-b: 1,876. mixed: 1,338.
  - `slice_info.config` differs only in `prediction` (by 1 s) and in `first_layer_time`
    (`0.000000` against `16532829680798007296.000000`).

  The builder's cause, Orca's threads, fits. The guide's description, "a handful of
  segments" in 12 layers of the Carriage, understates the plates: 0.7 % of plate A's
  extrusion lines move.
- **What is pinned, and holds:**
  - The summaries: layers exact; print time and filament within `BAND` = 2 %. My print
    times moved by 5 s in 55,950 s, and `filament_m` by 0.01.
  - The warnings: exact, and stable in every run.
  - The placements: within 1.0 mm, with a measured worst of 0.4692 mm.

  None of these was flaky in my runs.
- **What is pinned, and does not hold:** `test_the_mixed_plate_slices_to_the_same_gcode_every_time`
  asserts the mixed plate's sliced file is byte-identical, apart from the named fields,
  on one CPU. It passed in the suite's run and in one more run, then **failed on the
  third**:

  ```
  [orca] mixed plate on one CPU: 19 entries, differing ['Metadata/plate_1.gcode', 'Metadata/slice_info.config']
  FAILED slice/tests_orca/test_frc_parts.py::test_the_mixed_plate_slices_to_the_same_gcode_every_time
  ```

  The two G-code files differed in 1,085 lines, starting with the model print time,
  5h 15m 13s against 5h 15m 12s. One failure in three runs of a test inside the
  upstream check is a flake by the standing rules. It also disproves the guide's and
  the docstring's claim that this plate came out the same on one CPU "in every pair
  measured". `taskset` does not make Orca deterministic.
- The part of that test worth keeping is the slice service's own determinism: the plate
  3MF is the same for two writes. That needs no Orca and belongs in the fast suite.

## Check 7: suites: the fast suite PASSES; real-Orca PASSED once (but see defect 1)

- **Fast suite:** `make -C slice test-flakes RUNS=20 WORKERS=2` passed 20 of 20, 950
  tests each, at 5.00 to 9.74 s a run (147.8 s wall). The machine was shared at load 2 to
  5, so I compared against `main` (exported with `git archive` and run with the same
  environment), alternating runs:
  - `main`: 4.96 to 6.27 s.
  - Branch: 5.35 to 6.06 s.
  - The new fast tests: 0.48 s alone, of which 0.25 s is the module fixture that reads
    all eight parts.

  So the change adds no measurable time. The "about 4 s" baseline is not reachable on
  this loaded machine for `main` either. (The flakes run was bounded through `make`, not
  on pytest directly; every other pytest here was bounded directly with `timeout` and
  `prlimit`.)
- **Branch coverage:** `coverage run ... -m pytest -p no:randomly` followed by
  `coverage report --fail-under=100` gives 100 %: 2,089 statements and 544 branches, none
  missed.
- **Real-Orca suite, once:** 49 passed in 134.4 s.
  - The real-part tests take about 95 s of it: the one-CPU test 33.6 s, four-each-a
    20.0 s, team 13.0 s, four-each-b 10.3 s, mixed 9.0 s, and the eight parts alone
    10 s.
  - **Judgement:** about 2 minutes is acceptable for `make upgrade-orca`. It runs rarely,
    and the mentor's target plates are exactly what a new Orca must still slice, so they
    should stay in that check rather than move to a separate target. The full plates
    already stay out, which is right.
  - The one change needed is defect 1's: removing the flaky one-CPU byte test takes 34 s
    off and brings the suite to about 100 s. A separate target for the heaviest plates
    is not needed at that cost.

## Defects

### 1. Serious: the one-CPU consistency test is flaky, and the guide's claim behind it is false

- **Evidence:** check 6. `test_the_mixed_plate_slices_to_the_same_gcode_every_time`
  failed in 1 of 3 runs, with 1,085 differing G-code lines. It is part of
  `make test-upstream`, so of `make upgrade-orca`. The guide ("The same plate, sliced
  again") and the test's docstring say the mixed, team and four-each-b plates came out
  the same on one CPU.
- **Fixed when:**
  - The real-Orca suite no longer asserts byte identity of Orca's output.
  - The check that the slice service hands Orca the same plate 3MF every time is a
    fast-suite test.
  - Consistency is pinned by slicing the same plate twice and comparing the summaries
    (in the band), the warnings (exactly) and the placements.
  - The guide describes the variation with its measured size (for example 16,190
    extrusion lines of 1.2 million on plate A), and says that one CPU does not remove
    it.
  - The real-Orca suite passes three times in a row, as the brief's stop condition asks.

### 2. Serious: with supports on, the placement check passes plates Orca refuses, and the refusal names neither the instances nor the cause

- **Evidence:** check 3.
  - Two Elevator Block Tops 5 or 7.45 mm apart with supports on are refused by Orca with
    `slice.orca_too_close`. They slice at 8.5 mm, and with supports off.
  - The mentor's plate A with supports on is refused after 16.4 s.
  - The sentence "Parts are too close together; spread them out." has `where` holding
    only `stage`, although Orca's debug log names the pair. The remedy offers moves
    that do not fit plate A.
- **Fixed when:**
  - A measured spacing with supports on is in the contract and in the placement check,
    so these plates are refused at the checking stage with `slice.placement_too_close`
    naming the pair. There is a fast test of it and a real-Orca test that the measured
    spacing slices.
  - A -101 that still reaches Orca carries the two instances from the log's
    `gcode path conflicts found between` line in `where` and in the sentence. There is
    a fake-Orca test producing it on purpose, and a real-Orca test pinning the log
    line's format.
  - With supports on, the remedy offers turning supports off or a second plate.
  - The guide's error table lists the new detail.

### 3. Medium: the guide's host sizing leaves out what Orca uses past the ceiling

- **Evidence:** check 5. The watchdog stopped Orca at a reading of 2,140,316 kB against
  a 2,048,000 kB ceiling. The guide itself says a plate can be delivered over the
  ceiling, and one such plate peaks at 2,319 MB. "2.4 GB" for the host is therefore not
  a bound.
- **Fixed when:** the guide sizes the host from measured worst cases (the ceiling, plus
  the largest overshoot measured at a stop, plus a delivered spike, plus the service's
  400 MB), in one unit, and says whether that fits the 2.5 GB allowed. If it does not,
  the default ceiling comes down until it does, and the four-each-a plate (about
  1,390 MB) still slices.

### 4. Low: the plate A figures disagree with each other

- **Evidence:**
  - Plate A's peak is "1,343 to 1,372 MB" in the comment in `limits.py`, "1,343 to
    1,377" in the guide's table, and 1,388 to 1,393 MB in my three slices.
  - Parsing the eight parts takes "about 0.3 s" in the docstring of
    `tests/test_frc_parts.py`, and "about 0.2 s" in the guide.
- **Fixed when:** one set of figures, measured once, appears in both places, with the
  band seen between runs.

### 5. Low: warnings from `result.json` and from the debug log are not cut and keyed alike

- **Evidence:** check 4.
  - A warning over 300 characters is listed twice.
  - A 5,000-digit run raises `ValueError` in `_natural`.
  - Leading-zero ties come in an order set by `PYTHONHASHSEED`.
  - Past 300 distinct warnings, which 300 are kept depends on the order of Orca's
    threads.

  None of these is reachable with today's labels.
- **Fixed when:**
  - Both sources go through one normaliser (strip, cut to `MAX_WARNING_CHARS`).
  - The sort key breaks ties on the text itself and cannot raise. For example, compare
    digit runs by (length without leading zeros, digits) instead of `int()`.
  - The log is read whole, up to `MAX_LOG_BYTES`, and sorted before the cut to 300.
  - There is a fast test for each of the four cases.

### 6. Low: the parts' README calls MIT the repository's licence

- **Evidence:** check 1. "offered under the MIT licence, the licence of this
  repository". The repository has no licence file, and the brief says not to add one.
- **Fixed when:** the README says only that these parts are offered under the MIT
  licence below.
