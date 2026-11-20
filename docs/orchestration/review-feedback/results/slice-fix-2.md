# Fixes for the slice service's review, round 2

Fri 2026-11-20, finished about 10:58 PT, on the uncommitted working tree. Review:
[slice-review-2.md](slice-review-2.md); brief: [fix.md](../briefs/fix.md). Scratch scripts
and logs are under
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/slice-fix-2/`
(`probe.py`, `flakes.sh`, `cov.sh`, `orca.sh`, `interleaved.py`, `flakes.log`). Probes ran
against `python -m penguin_slice serve` with a stand-in for Orca that notes its start and
waits to be stopped, on an aarch64 Linux machine with 4 CPUs at a load of about 1.

## Defect 1 (medium): a stop during the plate write: fixed

- `plate_3mf.write_plate_3mf` takes `stop` and looks at it before each part's mesh and
  before each instance's object; once set it raises `SliceCancelled` ("stopped by the slice
  service (<reason>) while the plate was being written, before Orca was started").
  `plate_configuration.run_plate_configuration` passes the slice job's stop to it.
- `slicer._run_orca` raises `SliceCancelled` without starting Orca when the stop is already
  set by a cancel, an abandonment or a shutdown. A preset timeout or watchdog stop is left
  as it was (only the run itself sets those; `TestWhichStopIsReported` uses a preset one
  to drive the reporting). Choice: the check sits in `_run_orca`, the one place that starts
  Orca, so every caller gets it. A stop set between that check and the `Popen` still
  starts Orca and stops it at once, as before.
- Files: the pool's cleanup removes the slice job's folder, as on every cancel.
- Tests, each seen failing first: `test_web.py::TestStopDuringThePlateWrite` (a cancel, an
  abandonment through `pool.sweep` with a fake clock, a shutdown; each set from inside the
  write after the first of three parts' mesh; asserts `cancelled`, the cancel reason in the
  log, the next mesh never built, `run_process` never called, the work folder empty);
  `test_plate_3mf.py::TestStopDuringTheWrite` (a stop at each of the first four looks ends
  the write there; the writer looks once per part and once per object);
  `test_slicer.py::TestPlateSlice::test_a_stop_set_before_orca_starts_never_starts_it`
  (cancel, abandoned, shutdown).
- Measured, `DELETE` at 0.5, 3, 8 and 15 s into the write of the largest plate (150
  instances of the review's 149,760-triangle hub): `cancelled` 0.06 to 0.17 s later with
  one part, 0.05 to 0.17 s with 25 parts; no Orca start; the work folder empty. Before:
  21.7 s.
- The guide's "Cancelling" paragraph covers the write, an abandonment and a shutdown.

## Defect 2 (low): the cost of the largest plate: fixed, memory reduced

- The write now goes part by part: all instances of one part are written after its mesh
  text is built, and the text is freed before the next part's is built, so one part's mesh
  text is held at a time. Object ids and build items keep the instances' order; the
  `<object>` elements are grouped by part, so Orca lists them grouped (the name guard
  compares in any order). Test: `TestStopDuringTheWrite::test_one_parts_mesh_text_at_a_time_objects_grouped_by_part`.
  A real-Orca slice of an interleaved plate (bracket, spacer, bracket; `interleaved.py`)
  passed the name guard with all three names.
- Measured, each from a freshly started service (`VmHWM`, the upload's checks included):
  150 instances of one hub: `POST` 1.8 s, write 24 s, folder 269 MB, resident 207 MB.
  150 instances over 25 hubs: `POST` 5.8 s, write 28 s, folder 448 MB, resident 197 MB
  (438 MB before the change). Three 25-hub plates at once: resident 276 MB, folders 823
  MB in all.
- The guide's "Plate limits" has a new paragraph and table, "The cost of the largest plate
  to the slice service", with these figures, which plate each is for, that the write and
  Orca never run at the same time, and that the service's memory stays near its peak while
  Orca runs (size a host for about 280 MB beside Orca's ceiling).

## Defect 3 (low): terms: fixed

- A running slice service is a **slice service process**: the guide's paragraph (now "One
  slice service process holds its slice jobs"), the `slice.unknown_job` row, `web.py`'s
  docstring, the top-level `CLAUDE.md` gotcha, and a definition added to its Terms. "One
  instance" for a server's worker processes became "behind one address".
- Plate configuration said to be queued or logged: `web.py` (module docstring,
  `log_refusal`, `_queue`), the guide (the HTTP interface, the memory model's log line, the
  refusal log line, the modules table), `limits.py:35`, `plate_configuration.py`'s
  docstring. Found beside it and fixed: the class `JobPart` is now `CheckedPart`.
- The five student sentences say "on a second plate": `limits.py` (two refusals: "so print
  the rest on a second plate."), `errors.py` remedies "Lower the quantities and print the
  rest on a second plate.", "Use fewer different parts on this plate and print the rest on
  a second plate." and "Remove some instances or the largest part and print them on a
  second plate." (choice: "them", since "the rest" would read as the parts kept). The
  tests that state each sentence were changed first.
- `contracts/sliced-file.md`: the HTTP interface is named as the slice service's, the
  guide links say "the slice service's guide", and "the output directory" is gone (the name
  is the one `GET /slices/<job>/file` offers; a done slice job keeps only its sliced file and
  uploads until its record expires). Found beside it: the guide's `slice.output_unwritable`
  row no longer says "the output folder".

## Suites

- Fast suite: 919 tests; 20 of 20 runs passed in random order on 2 workers, 3.96 to 5.34 s
  each, slowest test 0.54 s (seeds in `flakes.log`).
- Branch coverage: 100 % of every module (2,075 statements, 544 branches).
- Real-Orca suite, one Orca at a time from a scratch working folder: 35 passed in 41.8 s
  (load 2.3), no Orca left, nothing written to the working folder.
