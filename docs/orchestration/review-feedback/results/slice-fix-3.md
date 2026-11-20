# Fixes to the slice service after review round 3

Fri 2026-11-20, finished about 12:37 PT, on the uncommitted working tree. Review:
[slice-review-3.md](slice-review-3.md). Folders touched: `slice/` only (`contracts/`
needed no change). Scratch scripts and logs:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/slice-fix-3/`
(`orca.sh`, `mut.sh`, `plates.py`, `serve.sh`, `serve-arena.sh`, `flakes.sh`, `cov.sh`, and
the scratch copy in `copy/`).

## Defect 1: no real-Orca test of an interleaved plate. Fixed

New real-Orca test `test_interleaved_parts_each_land_where_their_own_instance_is_placed`
(`slice/tests_orca/test_orca.py`, in the suite `make -C slice test-orca` runs, which
`make upgrade-orca` runs as its upstream check). It writes nine instances of three parts
(an uncentred bar, the sheared L, a slab) in the order Ell, Bar, Ell, Slab, Bar, Ell, Slab,
Ell, Bar, at orientations `+z`, `+x`, `+y`, `-z` and angles 0 to 275, slices them with the
real Orca, and holds each named object's first-layer bbox (Orca's `plate_1.json`) to the
bed-touching vertices of its own instance under `instance_matrix`, within
`INTERLEAVED_TOLERANCE_MM` = 0.25 mm. Today's worst error: 0.054 mm.

Shown to fail in the scratch copy, with two mutants of the writer's build items:

- every build item takes the object at the same position in the resource order (pairing by
  position): the test fails, Orca refusing the plate ("Ell #2 has floating regions");
- every build item takes another object of its own part (same part, wrong instance): the
  test fails at the bbox assertion, 8 of 9 instances off by 70 to 149 mm.

The guide's paragraph on `--arrange 0 --orient 0` now says the placement rests on Orca's
pairing by `objectid` and names this test.

## Defect 2: the guide's memory figures. Fixed in part (a cause found and capped; some growth remains)

Measured with the real `serve` command and a stand-in for Orca, the 25-hub plate
(150 instances over 25 hubs of 149,760 triangles) sent 16 times in a row to one process,
each slice job cancelled once the stand-in had started, `VmHWM` read then (load 0.7 to 1.4):

| `serve` process | First plate | After 13 | After 16 |
|---|---|---|---|
| before the fix (glibc's default arenas) | 178 MB | 360 MB | 365 MB |
| `MALLOC_ARENA_MAX=2` in the environment | 183 MB | 252 MB | (13 sent) |
| after the fix (`serve` caps the arenas) | 199 MB | 251 MB | 261 MB |

Cause found: glibc gives each allocating thread a malloc arena of its own (up to 8 per
CPU), and an arena keeps what the plate write freed; the slice service runs every request
and every slice job on a new thread, so the process filled one arena after another. Nothing
is kept per slice job after it ends: a finished record holds the plate configuration, about
21 kB of footprints per hub. Fix: `serve` calls `mallopt(M_ARENA_MAX, 2)` before it
listens (`penguin_slice.__main__.cap_malloc_arenas`; on a C library without `mallopt`,
such as macOS's, it does nothing). Tests, written first and seen to fail
(`slice/tests/test_cli.py::TestMallocArenas`): the cap goes through `mallopt` with
(-8, 2); a library without `mallopt` or one that refuses is left alone; this process's C
library takes it when it is glibc; `serve` caps before it listens.

Not fixed: with the cap the peak still rises, about 4 MB a plate from the 8th plate to the
16th. I did not hunt its cause further, as the ruling said. The guide's "The cost of the
largest plate" now gives the table above (with the cap and without), says the growth goes
on, and sizes a host for 400 MB of the service beside Orca's ceiling (1.3 GB with the
default 900 MB ceiling) over the measured worst case of 261 MB. Its 25-hub row of the
fresh-process table now reads "178 to 233 MB over the fresh processes measured" (the
builder's, the reviewer's and mine), and the guide says that the 1-hub and three-at-once
rows were measured before the cap.

## The gap: nothing held the one-mesh-at-a-time write. Fixed

New fast test `test_each_parts_mesh_text_is_released_before_the_next_is_built`
(`slice/tests/test_plate_3mf.py`). It wraps `_mesh_xml` through `monkeypatch` to return
each part's mesh text as a `memoryview` (which takes a weak reference) and checks that every
earlier part's mesh text is dead when the next is built, and that none outlives the write.
It does not depend on timing: CPython frees on the last reference. In the scratch copy it
fails on both mutants: the `del mesh` removed (`[[], [True], [False, True]]`) and a
module-level cache of meshes (`[[], [True], [True, True]]`).

## A defect of the same kind found beside: a flake in the fast suite. Fixed

The first 20-run flake check found one failure (seed 2783857003, reproduced on a rerun):
`test_orca_runner.py::TestCancelAndTimeout::test_timeout_of_an_orca_that_ignores_sigterm`.
`slicer.run_process` started the thread that reads Orca's messages before it made the
deadline timer, so a message read first found no timer (`timers.made[-1]`: IndexError in
the pump thread), and the timeout never fired. The fault was in the code's order, not only
in the test. Fix: the deadline is made before the pump starts and started where it was.
The new test `test_the_deadline_exists_before_any_message_of_orcas_is_read` checks that
the pump thread of this call is not yet running when the deadline is made. It failed before
the change (`[True]`) and passes after. The failing seed now passes.

## Suites

- Fast suite, 20 runs, each in a new random order, 2 workers, after every change: 20 of 20
  passed, 925 tests each, 3.8 to 4.1 s at load 0.8 to 2.1. Seeds: 2756264783, 3655303094,
  1475996979, 3200828263, 3381684507, 1970108023, 382604573, 3778042789, 2034852850,
  3534434402, 2230182243, 114032016, 1217009858, 52570646, 2085251444, 2135983018,
  1940071744, 562184822, 3092828759, 1170201873.
- Branch coverage: 100 % (2,083 statements, 544 branches, none missed).
- Real-Orca suite, one Orca at a time, from a scratch working folder, after every change:
  36 passed in 32.7 s at load 2.2; no Orca left, nothing written to the working folder.
