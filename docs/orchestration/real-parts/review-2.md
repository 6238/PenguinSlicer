# Review 2: the real parts in the slice service's tests

**Verdict: FIX (0 serious, 1 medium, 1 low).**

The slice service side is fit to merge: every defect from round 1 is fixed at its cause, and
each fix has a test that fails when the fix is undone. The one defect that blocks the merge
is outside `slice/`. The new `other_instance` key in
[the error report contract](../../../contracts/error-report.md) makes the delivery
component's fast suite fail. A one-line test change fixes it.

Reviewed Fri 11-20 between 19:06 and 19:21 PT, on the uncommitted working tree of branch
`tests/real-frc-parts-2` (`git diff main -- slice contracts`, plus the untracked
`slice/tests/fixtures/frc-parts/`, `slice/tests/frc_parts.py`, `slice/tests/test_frc_parts.py`
and `slice/tests_orca/test_frc_parts.py`). The builders' result and fix files were not read.
Every figure below comes from a command run for this review:

- one real Orca at a time, at most 2 test workers;
- on the container's 4 CPUs and 5 GB (cgroup), at a load of 0.4 to 2.2;
- no `PENGUIN_` variable in the environment, so every slice ran at the default 2,000 MB
  ceiling.

Scratch scripts and logs are in
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/real-parts-review-2/`:

- `pair.py` slices two instances of a real or generated part a given gap apart, with the
  placement check's spacings set to 0 so the plate reaches Orca;
- `tight.py` does the same for the upstream check's six-instance `tight_plate`;
- `rises.py` logs every watchdog reading of one slice;
- `mut.sh` runs the fast suite against the mutated copy in `mut/`;
- `flakes.sh` runs the fast suite 20 times.

## Check 1: round 1's six defects: all fixed at their cause

| Round-1 defect | What changed | Mutation in a scratch copy, and what failed |
|---|---|---|
| 1, the flaky one-CPU byte test | The test is gone. `test_the_slice_service_hands_orca_the_same_plate_every_time` (fast suite) compares two plate 3MF writes byte for byte. Each run of the upstream check pins the summary (in the band), the warnings (exactly) and the placements. The guide gives the size of Orca's variation, and says one CPU does not remove it. | (none needed: the test is gone, and the upstream check passed twice, see check 5) |
| 2, the supports spacing (check before Orca) | `plate_from_printer(printer, supports)` uses `SPACING_SUPPORTS_MM` = 12 mm. `read_plate_configuration` passes `supports`. The refusal names both instances (`other_instance`). With supports on, the sentence and the remedy say so. | `plate_from_printer` always 5 mm: 3 tests failed (`test_with_supports_on_the_placement_check_asks_for_the_supports_spacing`, `test_with_supports_the_plate_asks_for_the_larger_spacing`, `test_the_spacing_depends_on_supports[True-5.0…]`). `service` not passing `supports`: 1 failed. `other_instance` set to the wrong instance and the supports remedy dropped: 3 failed. |
| 2, the pair named from Orca's log (-101) | `orca_log_conflicts` reads `gcode path conflicts found between A and B` (`LOG_CONFLICT_RE`). `_too_close` puts the pair in the sentence, in `where` and in the detail. With supports on, it adds the supports clause and remedy. | Log pair ignored: 2 failed (`test_orcas_too_close_names_the_pair_from_its_debug_log[refuse_logged-…]`). Pair left in the log's order: 3 failed. Supports clause dropped: 2 failed. With the real Orca, `test_orca_names_the_pair_whose_supports_meet` and `test_overlapping_instances_are_refused_by_orca` pin the log line. |
| 3, the host sizing | A new section, "Sizing the host" (see check 4). | (not a mutation) |
| 4, figures that disagree | The parse time is 0.17 to 0.19 s in both the docstring and the guide. The figures for plate four-each-a are given once, with their plate (the plates changed, see check 3). | (not a mutation) |
| 5, the warnings edges | One normaliser for both sources (`_warning_text`). `_natural` compares digit runs by length and digits, never through `int()`, and breaks ties on the text. `_first_in_order` reads the whole log and keeps the first in order. | result.json not cut to 300 characters: 2 failed (the long-warning test and the 5,000-digit test). `int()` in `_natural`: 1 failed. No tie-break on the text: 4 failed (the leading-zeros tests). Keeping the first logged, not the first in order: 2 failed. |
| 6, "the licence of this repository" | The README still says it. It is now true: `main` has a top-level `LICENSE` (commit `78605c9`, "MIT licence for the repository"), MIT, "Copyright (c) 2026 Popcorn Penguins, Inc.", the same text and holder as the parts' README. | (not a mutation) |

After each mutation the scratch copy was put back. `diff -r` shows it identical to the
working tree, and its unmutated run passes all 972 tests.

## Check 2: supports spacing: 12 mm is enough and not needlessly large

**The refusal before Orca.** `test_with_supports_on_the_placement_check_asks_for_the_supports_spacing`
asserts the report for two instances 10 mm apart with supports on:

- code `slice.placement_too_close`, at the checking stage, before any Orca runs;
- message "Box #1 and Box #2 are closer than 12 mm, the room supports need between
  instances.";
- `where` = `part`, `instance`, `other_instance`, `stage`;
- remedy "Spread the instances out (or press Arrange), turn supports off, or move some
  instances to a second plate, and slice again.", with the action `arrange`.

The sentence names both instances. Each remedy is something a student can do in the
wizard. The plates the target needs fit at 12 mm.

**With the real Orca, one slice at a time, supports on, the placement check left out:**

| Pair | 5 mm | 8 mm | 8.5 mm | 9 mm | 12 mm |
|---|---|---|---|---|---|
| two Elevator Block Tops, one behind the other | refused -101, pair named | | | slices | slices |
| two Elevator Top Inners, side by side | refused -101, pair named | | | slices | slices |
| two Elevator Top Inners, one behind the other | refused -101, pair named | | | slices | slices |
| `tight_plate` (2 Tops and a Carriage in a column, 3 Top Inners) | | refused -101 (Top Inners #1 and #2) | slices | slices | slices (upstream check) |
| generated T-beam 30 mm high, flanges facing | slices (also at 3 mm) | | | slices | slices |
| generated T-beam 100 mm high, side by side and one behind the other | slices (also at 3 mm) | | | slices | slices |
| generated gallows (post and arm) 30 and 100 mm high, arms facing | slices (also at 3 mm) | | | slices | slices |

The generated parts carried 790 lines of support features in their G-code, so they did
have supports, and their supports never met even 3 mm apart. Only the real parts' tree
supports (inside pockets and bores near the footprint's edge) need the room. Every -101
report named the right pair. With supports on it said the supports were the likely cause.

**Is 12 mm needlessly large?** No. The edge measured is 8 to 8.5 mm (8 mm refused, 8.5 mm
sliced), on the builder's pairs and on mine. 9 mm would leave 0.5 to 1 mm over a refusal
the reviewers saw twice. Those figures come from a few pairs at the default profiles, and
Orca's tree supports vary from slice to slice (see the guide's "The same plate, sliced
again"). 12 mm costs the students little:

- the mentor's target fits with 13 to 14.2 mm gaps;
- a full plate of 3 x 4 Bottom Inners fits at 12.5 mm.

**Graded finding:** none. 9 mm would be the measured edge plus a hair, not a safe spacing.

## Check 3: the two target plates: PASS

Through the HTTP interface, in the real-Orca suite (two runs) and in `rises.py`, at the
default ceiling:

| Plate | Supports | Result | Print time, filament | Worst first-layer error | Peak |
|---|---|---|---|---|---|
| four-each-a (2 of every part) | off | done, twice | 36,451 s, 403.18 g | 0.4692 mm over 16 | |
| four-each-b | off | done, twice | 36,464 s, 403.18 g | 0.4692 mm over 16 | |
| four-each-a | on | done, three times | 44,304 s, 430.64 g | 0.4692 mm over 16 | 1,394,292 kB (1,362 MB) |
| four-each-b | on | done, three times | 44,306 s, 430.65 g | 0.4692 mm over 16 | 1,439,800 kB (1,406 MB) |

- Together the two plates hold 4 instances of every part (32), each in its printing
  orientation and none turned (`test_the_two_plates_hold_four_instances_of_every_part`).
- Every instance landed at its own place (tolerance 1 mm).
- With supports off the 10 warnings were the true ones. With supports on there were none.
- Plate four-each-a's 1,362 MB with supports on is 29 MB below the guide's band of 1,391
  to 1,415 MB. That is ordinary run-to-run spread and is not graded.

## Check 4: host sizing: follows from the figures

The guide's argument:

- worst case = ceiling + largest rise between two readings = 2,000 + 502 = about 2,500 MB;
- add the service's 400 MB: 2,900 MB;
- add a fifth: 3,480 MB, rounded to 3.5 GB (3,584 MB);
- all in MB of 1,024 kB, said once, with the ceiling given as 2,048,000 kB.

That arithmetic is right. My readings fit it:

- **Twelve Bottom Inners, 12.5 mm apart, supports on, default ceiling:** stopped with
  `slice.out_of_memory` after 24.0 s, at 2,104,996 kB. That is 56 MB over, inside the
  guide's 94 and 175 MB. The largest rise was 497,356 kB (486 MB) in 0.26 s, against the
  guide's 502 MB on that plate.
- **The target plates:** the largest rise was 318,600 kB (311 MB) on four-each-b with
  supports on, against the guide's "up to 308 MB". That is within the spread, and the
  guide's bound uses the 502 MB figure anyway.

The guide says what the 3.5 GB means for the owner's limit:

- the ceiling stays at 2,000 MB;
- Orca's measured worst at that ceiling is about 2,500 MB, the 2.5 GB the owner allows;
- raising the ceiling would pass that limit.

Each figure is given with its plate. In
[the guide](../../../slice/README.md), `limits.py` and the test comments, the four-each-a
figures and the 1,410 MB of the full Bottom Inner plate agree. Defect 2 is one figure stated
two ways in another place.

## Check 5: suites: PASS

- **Fast suite:** 20 runs in random order on 2 workers, pytest bounded directly (`timeout
  300`, `prlimit --as=8 GB`). Result: 20 of 20, 972 tests each, 4.38 to 4.83 s a run.
  Alternated with `main` on the same machine: `main` 4.19 to 4.49 s, branch 4.42 to
  4.80 s. That is within the brief's second.
- **Branch coverage:** 100 %, with 2,139 statements and 558 branches, none missed.
- **Real-Orca suite, twice:** 53 passed in 141.8 s, and 53 passed in 141.0 s. The real-part
  tests take about 110 s of that, as the guide says. The heaviest are four-each-a and
  four-each-b with supports on, 19.0 and 18.8 s each.

## Check 6: error reports and contracts: conform; one other component not updated

- **`slice.placement_too_close`:** `where` = `part`, `instance`, `other_instance`,
  `stage`. It has its own remedy when supports are on, and the action `arrange`.
- **`slice.orca_too_close`:** `where` = `instance`, `other_instance`, `stage` when Orca's log
  names the pair, and `stage` alone when it does not. The detail lists the pairs. The
  remedy depends on the supports.
- **Shape:** both reports pass the suite's `assert_report_shape`, whose `WHERE_KEYS` now
  holds `other_instance`.
- **Contracts:** [contracts/error-report.md](../../../contracts/error-report.md) defines
  `other_instance`.
  [contracts/plate-configuration.md](../../../contracts/plate-configuration.md) gives
  `SPACING_SUPPORTS_MM` = 12, with what an arranging user interface must do, and says the
  too-close report names both instances. The guide's error table describes both codes.
- **Defect 1:** the delivery component reads the same contract and pins its list of
  `where` keys, so its fast suite now fails.

## Defects

### 1. Medium: the contract change makes the delivery component's fast suite fail

- **Evidence:** I ran
  `delivery/.venv/bin/python -m pytest delivery/tests/test_contracts.py` on the working tree:

  ```
  FAILED delivery/tests/test_contracts.py::test_the_contract_lists_the_fields_this_test_expects
  E   Extra items in the left set:
  E   'other_instance'
  ```

  The test reads the `where` row of `contracts/error-report.md` and asserts it is exactly
  `{'part', 'instance', 'height_mm', 'stage'}` (line 67). Merging this change makes
  `make -C delivery test` fail on `main`. `delivery/relay/tests/test_relay_errors.py`
  line 31 pins the same four keys as the relay's own allowed set. It does not fail today,
  since the relay reports no pair.
- **Fixed when:** `delivery/tests/test_contracts.py` expects `other_instance` too, and the
  relay test's allowed set is either taken from the contract or says why it is narrower.
  `make -C delivery test` must pass on the branch. That folder was outside the builder's,
  so the coordinator has to allow the change or make it.

### 2. Low: the comment on the example plates is untrue for the full plates

- **Evidence:** `slice/tests/frc_parts.py` says "Every plate below leaves at least 12.5 mm
  between footprints … so each slices with supports off and on". The full plates defined
  below it are 5.8 to 10 mm apart and are refused with supports on, as their own comment
  says. The guide calls the same gaps "6 to 10 mm".
- **Fixed when:** the comment covers only the alone, mixed, team and target plates, and the
  guide and `frc_parts.py` give the full plates' gaps as one figure.
