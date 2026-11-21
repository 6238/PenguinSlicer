# Result: the team's real parts in the slice service's tests

Run of Fri 2026-11-20, 17:12 to 18:01 PT, against [the brief](brief.md) and
[the standing rules](../review-feedback/briefs/standing-rules.md), with the coordinator's
two later additions (several instances of every part, then the mechanical mentor's target
of 4 instances of each part on two H2S plates; the copyright holder "Popcorn Penguins,
Inc."). Branch `tests/real-frc-parts`; nothing committed (the coordinator commits).

## What was done

- **The parts.** The eight STL files copied byte for byte with `cp` into
  `slice/tests/fixtures/frc-parts/`, renamed to lower case with hyphens; the originals are
  untouched. Its `README.md` names each original file, says they are parts of the robot of
  the Popcorn Penguins (FRC Team 6238) that were printed and are in use, and carries the MIT
  licence text with "Copyright (c) 2026 Popcorn Penguins, Inc.", described as the
  repository's licence. No top-level licence file was added. No existing test part was
  removed or replaced: none tests the same thing as a real part.
- **`slice/tests/frc_parts.py`**: each part's file, name and printing orientation, the
  figures measured once with the slice service's own code (triangles, size, volume,
  footprint), and the plates: each part alone, `mixed` (one of each), `team` (2 blocks with
  4 spacers, 3 outer clamps, 3 clamp plates, 4 pulleys), `four-each-a` and `four-each-b`
  (the mentor's target), and `FULL` (full plates, measured for the guide, not sliced by the
  suite).
- **Fast suite, `slice/tests/test_frc_parts.py`** (23 tests): every part read once through
  `service.read_plate_configuration` (the mixed plate, all eight parts); triangles, size,
  volume, watertight, one shell, no open or overused edge, not inside out, no part warning;
  every resting position's height and the printing orientation's footprint; the four sliced
  plates pass the placement check; the two target plates hold exactly 4 of each part, none
  turned; the folder holds the parts and the README with its licence line and every
  original name.
- **Real-Orca suite, `slice/tests_orca/test_frc_parts.py`** (13 tests, part of
  `make test-upstream`, so of `make upgrade-orca`): each of the 12 plates through the HTTP
  interface at the default profiles: state `done` (no error report), a sliced file whose zip
  reads back and whose G-code has its six block markers in order, every instance's object
  in it, layers exactly as measured, print time and filament within 2 % of the measured
  values, no part warning, Orca's warnings exactly the true ones (listed per instance), and
  every instance's first-layer extrusions within 1 mm of the part's outline placed by that
  instance (measured 0.47 mm at worst). One more test slices the mixed plate twice with Orca
  pinned to one CPU and requires the plate file's entries and the sliced file to be the
  same apart from named fields.
- **Defect fixed: Orca's warnings in the summary were incomplete and changed from run to
  run.** The pinned Orca's `result.json` holds one warning per plate, a different one each
  slice (mixed plate: "Elevator_Block_Top #1" in one slice, "Elevator_Block_Carriage #1" in
  the next, while the debug log held five). `slicer.read_summary` now gives every warning
  of `result.json` and the debug log, each once, in natural order, at most 300
  (`slicer.plate_warnings`, `MAX_PLATE_WARNINGS`); `orca_log_warnings` sorts too, so a
  failure's sentence no longer depends on Orca's thread order. Tests first
  (`test_slicer.py::TestReadSummary`, two new), seen failing, then the change; one existing
  test's expected order was updated. The stop note now says "its warnings are only those
  its debug log held by then". Contract `contracts/sliced-file.md` (`warnings`) updated.
- **Defect fixed: the default memory ceiling stopped real team plates.** Plate four-each-a
  peaks at 1,343 to 1,377 MB, full plates of one block at up to 1,410 MB, all over 900 MB.
  `DEFAULT_MAX_PEAK_MB` is now 2,000 (1.4 times the highest supports-off plate), with the
  tests that pinned 900 updated, `contracts/plate-configuration.md`'s limits table, and the
  guide's settings, watchdog text and host sizing (400 MB of service beside the ceiling:
  2.4 GB).
- **Guide** (`slice/README.md`): "The team's real parts" in "Plate limits" (the first real
  measurements, said so), the full plates, the true warnings with their evidence, the
  consistency findings; `MAX_INSTANCES` rationale; the debug-log paragraph; the Tests
  section.

## Figures

Pinned Orca 2.4.2, default set, aarch64 Linux, 4 CPUs (cgroup quota 4, 5 GB), load under
1, one Orca at a time, three slices per plate (peak MB / Orca s / sliced MB):

| Plate | Instances | Peak (MB) | Orca (s) | File (MB) |
|---|---|---|---|---|
| clamp-plate-inner alone | 1 | 117 to 118 | 1.0 to 1.3 | 0.16 |
| elevator-block-bottom-inner alone | 1 | 216 to 218 | 1.4 to 1.5 | 1.10 |
| elevator-block-carriage alone | 1 | 181 to 182 | 1.1 to 1.4 | 0.64 |
| elevator-block-top alone | 1 | 210 to 212 | 1.3 to 1.4 | 0.91 |
| elevator-top-inner alone | 1 | 128 to 129 | 0.6 to 0.7 | 0.41 |
| inner-spacer alone | 1 | 97 | 0.1 | 0.08 |
| outer-clamp alone | 1 | 120 to 121 | 0.9 to 1.1 | 0.17 |
| pulley-v3 alone | 1 | 116 to 117 | 0.5 to 0.6 | 0.11 |
| mixed | 8 | 504 to 510 | 6.7 to 7.6 | 3.70 |
| team | 16 | 507 to 516 | 9.9 to 12.0 | 2.88 |
| four-each-a | 16 | 1,343 to 1,377 | 17.3 to 18.2 | 9.36 |
| four-each-b | 16 | 406 to 409 | 9.6 to 9.7 | 2.78 |

One slice each: Elevator Block Top 3 x 3, 1,015 MB, 12.8 s; Bottom Inner 3 x 4, 1,410 MB,
19.1 s (supports on: 2,319 MB, 31.0 s); Carriage 3 x 5, 1,333 MB, 17.7 s; Top Inner 5 x 5,
895 MB, 13.9 s; 30 clamps and spacers, 502 MB, 19.9 s; 25 pulleys 583 MB, 50 pulleys
1,074 MB; 150 pulleys passed 2,500 MB and were stopped (about 20 MB a pulley instance).
On one CPU: mixed 451 MB, 15.4 to 15.7 s; team 445 to 447 MB, 24.0 to 24.9 s; four-each-a
1,287 to 1,288 MB, 39.3 to 40.0 s; four-each-b 349 to 350 MB, 22.4 to 24.1 s.

Suites, all run on this machine while other agents shared it (load 0.2 to 2.7):

- Fast suite: 950 tests (23 new in `test_frc_parts.py`, 2 new in `test_slicer.py`).
  `make -C slice test-flakes RUNS=20 WORKERS=2`: 20 of 20 passed, 4.5 to 7.1 s a run (most
  4.7 to 5.4). Side by side on 2 workers: 4.70 s without `test_frc_parts.py` and 4.75 s
  with it at a load near 0.2; reading the eight parts costs 0.18 s, once per worker.
- Branch coverage of `penguin_slice` under the fast suite: 100 % (2,089 statements, 544
  branches).
- Real-Orca suite (`tests_orca/`, pytest run directly under `timeout` and `prlimit`, one
  Orca at a time): 49 passed three times in a row, in 121 s, 135 s and 149 s; worst
  first-layer placement error 0.47 mm on every run, and the one-CPU mixed plate identical
  apart from the named fields on every run.

## What was refused, warned or failed at first, and why

- **Nothing was refused** by the slice service's checks, and no part warning was given:
  every part is watertight, one shell, wound outwards.
- **Orca's warnings** "floating cantilever" (the four blocks, the Elevator Top Inner) and
  "floating regions" (the pulley) are true: see the guide. The blocks have 2,200 to
  3,700 mm2 of downward faces over pockets in their printing orientation (1,425 to 1,440 mm2
  of it a ceiling 1.7 mm up); with supports on, the warning goes. The pulley's hub ring
  starts 4.76 mm up inside a 6.35 mm bore with nothing under it, joined 0.8 mm higher by a
  45° chamfer (shown with cross-sections of the mesh). No slice service sentence speaks
  about either, so none needed correcting; Orca's own remedy ("re-orient ... or enable
  support generation") is right about supports.
- **Defect: warnings incomplete and varying** (above), fixed.
- **Defect: 900 MB ceiling** (above), fixed.
- **First test failures that were my test, not the service:** the placement check first
  compared Orca's `bbox_objects`, which includes the auto brim (up to 15 mm at the blocks),
  then missed the G2/G3 arcs of the pulley's first layer; both fixed in the test.
- **Not fixed, reported:** with supports on, four-each-a is refused by Orca as
  `slice.orca_too_close` (supports and brims of blocks 6.5 to 8.1 mm apart conflict); the
  placement check's 5 mm spacing does not foresee supports. The target is at the default
  profiles (supports off), where it slices.

## Consistency

Three separate slices of every plate (and four of each larger plate on one CPU). The
summary was the same apart from print time (up to 8 s in 15.5 h) and filament (0.01 g).
The sliced files differ in fields named in `tests_orca/test_frc_parts.py`
(`VARYING_LINES`, `VARYING_ENTRIES`, `FIRST_LAYER_TIME`): the G-code time stamp, the object
ids in `; printing object ... id:` comments (memory addresses), the G-code's `.md5`, and
`slice_info.config`'s `first_layer_time` (uninitialised memory in Orca). Beyond those, on 4
CPUs Orca's threads order and split a few extrusions differently each slice (Elevator Block
Carriage: 12 of 133 layers, a handful of segments each). Pinned to one CPU with `taskset`,
mixed, team and four-each-b were identical apart from the named fields in three separate
slices; four-each-a was not (one slice of three added a path of 14 short segments in layer
104 and moved print time by 1 s). The plate 3MF the slice service writes has the same
entries every time (its zip time stamps differ). So the remaining variation is Orca's, not
the slice service's; the test was not loosened: it holds the strict check on one CPU for
the mixed plate and states what it does not hold.

## Choices

- Printing orientation of each part: its largest face flat on the plate (contact areas
  measured per orientation), as a team prints it; no instance is turned.
- The target split: plate A the 12 Elevator Blocks and the 4 pulleys, plate B the other 16
  parts (4 x 4 grid). It fits only with every block in its printing orientation in two
  columns of Tops over Bottom Inners, 313 of 314 mm deep.
- All eight parts stay in the fast suite: reading and checking them costs about 0.18 s.
- Ceiling 2,000 MB, not higher: covers every supports-off plate with 40 % headroom; the
  only plate measured above it (12 Bottom Inners with supports, 2,319 MB) would leave
  under 10 % at 2.5 GB, the most this machine allows.
- Slice service keeps running Orca on every CPU: one CPU makes Orca 2.2 to 2.5 times slower
  and is still not fully deterministic (four-each-a). Left for the owner.
- Warnings sorted in natural order (numbers as numbers) rather than instance order: it
  needs nothing but the text and is the same every run.

## Not done

- The real-Orca suite's existing tests were not changed.
- The placement check was not taught about supports (see above): a design question.
- Orca's own nondeterminism was not worked around in production (see Choices).
- Rule slip: one measurement call chained three scratch-script runs with `;` (still one
  Orca at a time). The measurement scripts are scratch files, not committed; the plates
  they sliced are `tests/frc_parts.py`'s.
