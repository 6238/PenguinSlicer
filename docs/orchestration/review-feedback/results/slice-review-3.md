# Review of the slice service after the review-feedback changes, round 3

**Verdict: FIX, 2 defects (0 serious, 0 medium, 2 low). Fit to merge with both as known
open items.**

Reviewed Fri 2026-11-20, about 11:20 to 12:00 PT, on the uncommitted working tree
(`git diff main -- slice contracts README.md CLAUDE.md` plus the untracked new files). The
builders' result files were not opened. Builder's brief: [slice.md](../briefs/slice.md);
review brief: [review.md](../briefs/review.md); earlier rounds:
[slice-review-1.md](slice-review-1.md), [slice-review-2.md](slice-review-2.md).

Scratch scripts and logs are under
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/slice-review-3/`.
The previous reviewer of this round left `flakes.sh`, `mut.sh`, `probe.py`,
`serve_probe.py`, `interleaved.py` and a scratch copy there; I reran them myself and
trust only those runs. My own scripts are in its `mine/` folder (`interleaved3.py`,
`peak.py`, `serve.sh`, `realserve.sh`, `cov.sh`, `orca.sh`). The container has 4 CPUs and
5 GB, shared with another agent reviewing `delivery/`. Only the first twelve runs of the
fast suite count as quiet (load 0.2 to 1.0). The load is given with every other timing.

## Figures measured

| What | Measured | The guide says |
|---|---|---|
| Fast suite, 20 runs, random order, 2 workers | 20 of 20 passed, 919 tests each | passes |
| Fast suite wall time | 4.1 to 4.8 s at load 0.2 to 1.7 (quiet); 6.0 to 7.9 s at load 1.9 to 3.1 | seconds |
| Branch coverage, every module | 100 % (2,075 statements, 544 branches, none missed) | 100 % |
| Real-Orca suite, one Orca at a time (load 1.0) | 35 passed in 33.1 s, no Orca left, nothing written to the working folder | passes |
| 100 spacers | peak 509 MB, Orca 6.2 s; 1.81 MB, 13 layers | 488 to 513 MB, 6.2 to 7.1 s, 1.81 to 1.82 MB |
| Interleaved plate of three parts, real Orca | 9 instances, names in instance order, worst position error 0.054 mm | every instance where placed |
| Cancel during the write of the largest plate (1 part / 25 parts) | `cancelled` 0.03 to 0.20 s after the `DELETE`, at 0 to 26 s into the write; Orca never started; folder empty; next slice job reaches `slicing` in 0.02 to 0.08 s | 0.05 to 0.17 s |
| Abandonment during the write (grace set to 2 s) | `cancelled` 15.8 s after the client vanished (15 s keep-alive, then the grace); Orca never started; folder empty; slot free | keep-alive, then `ABANDON_GRACE_S` |
| Shutdown (SIGTERM to `serve`) 5 s into the write, 25 parts | process gone in 0.08 s; Orca never started; folder empty | cancels every slice job |
| Plate write, fresh slice service process, load about 1.2 | 1 part: `POST` 1.8 s, write 23.8 s, resident peak 212 MB. 25 parts: `POST` 5.9 to 6.5 s, write 27.5 to 30.0 s, resident peak 216 to 233 MB | 24 s / 207 MB; 28 s / 197 MB |

The plate-write and stop probes used a stand-in for Orca that notes its start and waits to
be stopped. Only the interleaved plate and the real-Orca suite ran the real Orca.

## (a) Round 2's three defects

| Round 2 defect | Verdict | Evidence |
|---|---|---|
| 1. A cancel during the plate write waits for the write to end | Fixed at its cause | `plate_3mf.write_plate_3mf` calls `_check_stop` before each part's mesh and each object. `slicer._run_orca` still checks first, so a stop after the last object never starts Orca. Undone in the scratch copy: without the per-object check, 4 tests fail (`TestStopDuringTheWrite`). Without both checks, 9 fail, including the three HTTP tests of `TestStopDuringThePlateWrite` (cancel, abandonment, shutdown). The probes in (c) confirm it over HTTP. |
| 2. The guide's cost of the largest plate is not the largest | Fixed | The write now holds one part's mesh text at a time. "The cost of the largest plate" gives figures for 1 part, 25 parts and three at once, and says the write and Orca never overlap. My figures are near the guide's (see the table). Note: a change that keeps every mesh alive (a module-level cache) passes the whole suite. No test holds the one-mesh-at-a-time property, but `test_a_stop_set_after_the_first_parts_mesh_ends_the_write` does catch building every mesh up front. |
| 3. Terms | Fixed | See (e). |

## (b) Objects grouped by part

- **Placement, orientation and name, real Orca.** `mine/interleaved3.py` sliced 9
  instances of three parts in the order Ell, Bar, Ell, Slab, Bar, Ell, Slab, Ell, Bar,
  with orientations `+z`, `+x`, `+y` and `-z` and angles from 0 to 275, through the HTTP
  interface. Orca's `plate_1.json` lists the objects in instance order. Each name's
  first-layer bbox matches the bed-touching vertices of its own instance under
  `instance_matrix` to within 0.054 mm (the sheared L shows any wrong turn or face). The
  `-z` Ell rests on its sheared top as asked. The first script's "WRONG" lines came from
  comparing with the hull of the whole part, not of its first layer: a measuring error,
  not a fault.
- **What reads the order downstream.** `check_plate_names` compares sorted lists. Its
  `where` names the first missing name in sorted order, which does not depend on the
  write's order. The summary counts `len(configuration.instances)`. `part_warnings` and
  placement refusals come from the plate configuration, not from the file. The
  empty-layer report names the object as Orca names it. Nothing depends on the old
  order.
- **A file left behind at each check.** `test_a_stop_set_between_two_objects_of_one_part_ends_the_write`
  sets the stop at every look, including the last (looks 1 to 4 for one mesh and three
  objects). A stop after the last look reaches `_run_orca`'s check, and that path is
  tested (`test_slicer.py:418`). `slice_plate_configuration` removes the scratch folder in
  a `finally`. Over HTTP every probe left the slice service process's work folder empty.
  After a SIGTERM to a bare `app.run` (no handler), the next `serve` start removed the
  dead process's folder (`clean_stale_scratch`).

## (c) Stops during the write, through the HTTP interface

See the table. A cancel came 0.03 to 0.20 s after the `DELETE` at every point of the
write, for both plates, including 26 s into the 28 s write with 424 MB already on disk.
No stop ever started the stand-in Orca, every one left the folder empty, and the next
slice job started at once. One caution for anyone reusing `probe.py`: with a 2 s
abandonment grace and no follower, the job is abandoned before the cancel arrives.

## (d) Suites

The 20 seeds were 2323517612, 3512557065, 1978929077, 2446583587, 3072522364, 2403698631,
1885340111, 998351571, 523001093, 793945979, 69721121, 429648331, 2318383422, 2974308563,
2265383569, 4201092354, 515603754, 2510278069, 2392855575 and 2617877641: no failure. The
ten slowest tests of the last run took 0.12 to 0.48 s, the slowest being
`test_a_dense_part_at_the_triangle_limit_is_read` (0.48 s) and
`test_any_coordinates_in_one_triangle` (0.42 s). Coverage and the real-Orca suite are in
the table. The real-Orca suite ran from a scratch working folder under `timeout 560`, with
`-p no:randomly`.

## (e) Terms, read as a newcomer

I read the guide, the top-level `README.md` and `CLAUDE.md`, and
`contracts/plate-configuration.md`, `contracts/sliced-file.md` and
`contracts/error-report.md`.

- **instance:** used only for a placement of a part.
- **slice service process:** defined in `CLAUDE.md:26` and used in `slice/README.md:43-49`
  and `:623`, and in `web.py:29-31`. "Instance of the service" is gone everywhere.
- **plate configuration:** never said to be queued, logged or running. `web.py:21` now
  reads "before a slice job is…".
- **slice job:** used for the work. "Print the rest on a second plate" replaces "second
  job" in the student sentences.
- **HTTP interface:** `contracts/sliced-file.md:5` now reads "The slice service's HTTP
  interface", and "output directory" is gone.

Left in place, and right to leave: "job" in `jobs.py` (the generic job pool) and in "the
job queue" of the `slice.busy` row; "job" in `contracts/progress-report.md`, which covers
every component; `<job>` in route paths. No slip found.

## Defects

1. **Low. No real-Orca test holds an interleaved plate of several parts to its
   placements.** The objects are now written grouped by part, so resource order and build
   order differ. Placement is right only because Orca pairs each build item with its
   object by `objectid`. The only real-Orca placement test,
   `test_rotated_instance_lands_where_the_placement_check_sees_it`, has one instance, and
   the name guard compares sorted names, not positions. A later Orca that paired items
   with objects by position would put the instances in the wrong places, and `make
   upgrade-orca` would still pass. Evidence: `tests_orca/test_orca.py:172-184`. My probe
   passes today (0.054 mm). **Fixed means:** a real-Orca test slices an interleaved plate
   of two or three different parts at distinct orientations and asserts each named
   object's first-layer bbox against its instance, as `mine/interleaved3.py` does.
2. **Low. The guide's host sizing undercounts a slice service process that has served
   many plates.** "The cost of the largest plate" says the slice service needs about
   280 MB beside Orca's ceiling, and gives 197 MB for the 25-part plate. A fresh process
   peaked at 233 MB on that plate. A process that had served thirteen plates in a row
   (five of one hub, five small, three of 25 hubs, all cancelled) reached `VmHWM`
   343 MB, against a resident 311 MB. Three 25-part plates in a row on a fresh process
   gave 212, 216 and 223 MB, so the peak creeps upwards with use. The cause (heap growth
   or fragmentation) was not found. **Fixed means:** the guide gives the peak of a
   long-running process after a sequence of the largest plates, or the figure is
   otherwise bounded.
