# Review of the slice service after the review-feedback changes, round 2

**Verdict: FIX, 3 defects (0 serious, 1 medium, 2 low).**

Reviewed Fri 2026-11-20, about 10:27 to 10:45 PT, on the uncommitted working tree
(`git diff main -- slice contracts README.md CLAUDE.md` plus the untracked new files). The
builders' result files were not opened. Builder's brief: [slice.md](../briefs/slice.md);
review brief: [review.md](../briefs/review.md); round 1:
[slice-review-1.md](slice-review-1.md). Scratch scripts and logs are under
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/slice-review-2/`
(`probe.py`, `serve_probe.py`, `gen.py`, `flakes.sh`, `mut.sh`, `cov.sh`, `orca.sh`,
`flakes.log`, `serve.log`, `serve2.log`). The container has 4 CPUs and 5 GB; another
agent ran suites in the same checkout throughout. No timing here was taken on a truly
quiet machine: the load average is given with each figure.

Round 2 spent its time on the fixes of round 1, the plate write that the removal of the
triangle cap now allows, the debug-log sentence and the terms. Checks 2, 6 and 7 of the
review brief were covered in round 1 and were only spot-checked here.

## Figures measured

| What | Measured | The guide says |
|---|---|---|
| Fast suite, 20 runs, random order, 2 workers | 20 of 20 passed, 906 tests each | passes |
| Fast suite wall time | 4.2 to 5.2 s at load 2.1 to 4.2 (no quiet run) | seconds |
| Branch coverage, every module of the package | 100 % (2,066 statements, 538 branches, none missed) | 100 % |
| Real-Orca suite, one Orca at a time (load 1.7) | 35 passed in 34.9 s, no Orca left, nothing written to the working folder | passes |
| 100 spacers, peak | 526 MB | 488 to 513 MB |
| 100 spacers, Orca's time and file | 6.7 s, 1.81 MB, 13 layers | 6.2 to 7.1 s, 1.81 to 1.82 MB |
| 150 instances of one 149,760-triangle part: plate write, through HTTP (load 1.4) | 26.0 s; job folder 267 MB (7.5 MB upload, 259 MB plate 3MF); service resident peak 183 MB | 24 s, 263 MB, 132 MB |
| 150 instances over 25 different parts at the triangle limit (load about 2) | write 28.0 s; job folder 448 MB (187 MB uploads, 261 MB plate 3MF); service resident peak 438 MB; the `POST` took 5.9 s | not stated |
| A cancel during that write | reported `cancelled` 21.7 s after the `DELETE` | "a running one is reported `cancelled` only after its Orca and every child are gone" |
| A cancel once Orca (a stand-in) runs | 0.10 s | prompt |
| Five largest plates submitted one after another | the first three accepted (1 running, 2 waiting), the fourth and fifth refused with `slice.busy` (503) in 1.7 s each; work folder peak 267 MB; resident peak 212 MB | 1 running and 2 waiting, then `slice.busy` |
| Three 25-part plates submitted at the same moment | all accepted in 10 to 14 s; work folder peak 563 MB; resident peak 582 MB | not stated |
| A client that vanishes (abandon grace set to 2 s for the probe) | noticed at the next keep-alive: `cancelled` 17.8 s later with Orca running, 25.8 s later during the write | 120 s grace |

The largest plates were measured with a stand-in for Orca that notes its start and waits
to be stopped, so no real Orca ran in those probes.

## Round 1's four defects

| Round 1 defect | Verdict | Evidence |
|---|---|---|
| 1. The debug-log reading can blame a sound part | Fixed at its cause | `SLICE_FAILED_WARNED_MESSAGE`: "The slicer could not slice this plate. It also warned, though this may not be why it failed: ...", every warning listed, none first. Fast tests assert the exact sentence (`TestOrcasDebugLog`, two tests); the real-Orca test `test_a_sound_parts_warning_is_not_given_as_the_reason_another_part_failed` slices the mushroom beside the needle and passed; the guide's "Orca's debug log" paragraph states the limit. Undone in the scratch copy (first warning only): 1 test fails. |
| 2. No test holds the reading to `slice.orca_failed` | Fixed | `test_a_failure_orca_names_by_its_return_code_ignores_the_log`, one case per code of `ORCA_RETURN_CODES` other than -100. With the guard replaced by `if True` in the scratch copy, 3 tests fail. |
| 3. A stray `result.json` in the repository root | Fixed | `git status --short` shows no untracked file outside the change; the real-Orca suite run from a scratch working folder left that folder empty. |
| 4. `MAX_PLATE_TRIANGLES` rests on no measurement | Fixed as asked, and it opened defect 1 below | No `MAX_PLATE_TRIANGLES`, `plate_too_detailed` or "plate is too detailed" in `slice/`, `contracts/`, `README.md` or `CLAUDE.md`, except two tests that assert the absence (`test_limits.py:22`, `test_service.py:301`). The guide and `limits.py` say the watchdog decides and give the measurement. Left over, a note: `PlateConfiguration.triangles()` is now called only by tests. |

## 1. Each item of the builder's brief

Round 1 found every item done; nothing in the change since contradicts that. Seven more
changes were undone by hand in a scratch copy (the copy's own package on `PYTHONPATH`, 2
workers), and the suite noticed all seven: the guard on `slice.orca_failed` (3 tests
fail), a cancel that no longer wins over a finished slice (2), the removal of a refused
plate configuration's folder (2), the one-instance remedy applied to two instances (2 of
`test_plate_configuration.py`, 2 of `test_errors.py`), only the first logged warning in
the sentence (1), the `building_plate` report removed (1), and the summary through
`jsonify` in place of the contract's field order (1).

## 2. Terms

No old term is left that should not be: `copy` only where bytes or a file are duplicated,
`X-Slice-Summary` only in the two tests that record its removal. The class `JobPart`
(`plate_configuration.py:19`) is still named after "plate job". The confusions a newcomer
meets are listed under defect 3.

## 3. Flakes and speed

`flakes.sh` ran pytest directly from `slice/.venv` under `timeout 300` and a 6 GB address
limit, `-n 2`, a fresh seed per run. Seeds: 2241065503, 2095177507, 487451501, 2998979258,
3521832074, 2037685317, 1861896674, 4194881809, 1519064521, 670615271, 1778101173,
3709517178, 2206679071, 1612219936, 3126932469, 3145366854, 1720884855, 1984922130,
3099367493, 3088580309. All passed, 906 tests each. The slowest test in any run was 0.25 s
(`test_the_three_ways_orca_can_end_on_a_signal_are_distinct`); the others named were 0.06
to 0.11 s (`test_a_failed_job_leaves_no_files`,
`test_the_most_instances_of_spacers_are_accepted_and_one_more_refused`,
`TestSignals::test_the_three_are_distinct`, `test_measure_reports_orca_refusal_as_failed`).

## 4. Coverage

`coverage run` over the fast suite, data file in the scratch folder: every module 100 %
branch (`__main__` 45 statements, `errors` 33, `jobs` 270, `limits` 53, `mesh` 185, `plate`
61, `plate_3mf` 62, `plate_configuration` 69, `print_config` 108, `service` 287, `slicer`
709, `web` 184).

## 5. The other suites

`tests_orca`, run directly under `timeout 560` from a scratch working folder,
`-p no:randomly`: 35 passed in 34.9 s. The block on a stem and the mushroom beside a
needle both gave the hedged sentence. The reference plate peaked at 526 MB, 13 MB over the
top of the guide's range of 488 to 513 MB (a note, not a defect: the test passed and the
conclusion drawn from the range holds).

## 6. Error reports

Every refusal met in the probes conformed to the contract: `slice.busy` ("The slicer is
busy, try again in a minute.", retryable), `slice.not_ready` on the file route of a slice
job being cancelled, `slice.cancelled` afterwards.

**The sentence for a failed slice whose debug log holds only warnings.** "The slicer could
not slice this plate. It also warned, though this may not be why it failed: It seems
object Mushroom #1 has floating cantilever. Please re-orient the object or enable support
generation."

- True: Orca did fail, did warn, and the service does not know whether the two are
  linked; the sentence says exactly that.
- Useful: for the block on a stem the warning is the reason and its advice works; for the
  mushroom beside the needle the student is told the warning may be unrelated, which is
  the most the log supports. The remedy ("Try another orientation or other print
  settings, and slice again.") can help in the first case and does no harm in the second.
- It names a part (Orca's words do) but never as the cause: the hedge precedes every
  warning, all warnings are listed in the log's order, `where` names no part or instance,
  and the reading happens only for `slice.orca_failed`. Notes: five warnings of 300
  characters make a message of about 1,600 characters, and a warning cut at 300 characters
  ends mid-word with no mark.

## 7. The guide against the code

The route table, the settings and the make targets were used as written in the probes
(`serve`, `POST /slices`, `GET /slices/<job>`, `/events`, `/file`, `DELETE`). The guide's
figures for the largest plate (24 s, 263 MB, 132 MB) are near what was measured for the
configuration it names (26.0 s, 259 MB plate 3MF, 183 MB); they are not the largest cost
(defect 2). The walk with the real Orca and `curl` was done in round 1 and not repeated.

## 8. The largest plate now accepted

`probe.py` against `python -m penguin_slice serve` with the stand-in Orca.

| Question | Answer | Evidence |
|---|---|---|
| Is a cancel during the write prompt? | **No** (defect 1) | `DELETE` 3.0 s into the write answered `cancelling`; the work folder went on growing (44, 55, 65 MB in the next three seconds); the stand-in Orca was then started and stopped; `cancelled` came 21.7 s after the `DELETE`. |
| Does a vanished client free the slot? | Yes, late | The stream's end is noticed at the next keep-alive (15 s), then the grace time, then the sweep; during the write the slot is freed only when the write ends (the same cause as defect 1). |
| Is every file removed afterwards? | Yes | After every probe (cancel in the write, cancel in Orca, queued cancels, abandonment, three at once) the work folder was empty: 0 files. |
| Does a progress report say something true during the write? | Yes | One report, `building_plate`, "Building the plate", no fraction, `elapsed_s` rising. `expected_s` (55.2 s) is the time model's estimate for Orca alone, 26 s of which had passed before Orca started: rough, as the guide says of it. |
| Can several queued together exhaust the disk or memory? | No | One write at a time: the work folder peaked at 267 MB with three queued, 563 MB with three 25-part plates (their uploads), and the service's resident memory at 582 MB at most. A refused fourth costs its upload and its checks (1.7 s) and leaves nothing. Not probed: done slice jobs keep their uploads and sliced file for an hour (`RECORD_TTL_S`), which was so before this change. |

## Defects

1. **Medium. A cancel during the plate write is not acted on until the write ends, and
   Orca is then started only to be stopped.** `run_plate_configuration` passes `stop` to
   `slice_plate` but `write_plate_3mf` never looks at it. With the triangle cap gone the
   write of an accepted plate takes 26 to 28 s (round 1 measured 4.0 s at the cap). Evidence
   (`probe.py cancel`): `DELETE` at 3.0 s answered `cancelling`; the service wrote a
   further 200 MB; the stand-in Orca's start log gained a line after the cancel;
   `cancelled` was reported 21.7 s after the `DELETE`, against 0.10 s once Orca runs. The
   same wait applies to an abandoned slice job (25.8 s measured) and to a shutdown, which
   waits for every worker; a student who cancels and submits again waits behind a slice
   job nobody wants. No test cancels during the write (no test name or body mentions it).
   Fixed means: the write checks `stop` between instances (or the mesh is written in
   bounded pieces) and raises `SliceCancelled` without starting Orca; a fast test sets the
   stop during the write and asserts `cancelled`, no Orca started and an empty folder; the
   guide's "Cancelling" paragraph covers the write.
2. **Low. The guide's cost of the largest plate to the service is not the largest.**
   "Plate limits" gives 24 s, 263 MB of disk and 132 MB resident for 150 instances of one
   part and calls the cost bounded by `MAX_INSTANCES` x `MAX_PART_TRIANGLES`. With the same
   150 instances over 25 different parts at the limit (accepted by every check) the
   service's resident memory peaked at 438 MB, because the write keeps every part's mesh
   text until the end, and the slice job's folder at 448 MB; three such plates at once
   reached 582 MB resident. A host sized from the guide's 132 MB beside a 900 MB Orca
   ceiling is short by about 300 MB. Fixed means the guide states the figures for 25
   parts at the limit (or the write stops holding all 25 meshes) and says that the write
   and Orca do not overlap.
3. **Low. Terms: "instance" names two things, and a few places blur plate configuration,
   slice job and "job".** Listed as a newcomer meets them:
   - "instance" of a part and "instance of the slice service":
     `slice/README.md:43-49` ("One process per instance of the service"), `:599`
     ("accepted by another instance of the service"), `web.py:28-30`, `CLAUDE.md:62`,
     three paragraphs from text where an instance is a placement on the plate. The second
     use is the wording of the builder's brief (item 6), so the choice of another word
     ("one running slice service", "service process") is the owner's.
   - A plate configuration said to be queued or logged, which is what a slice job is:
     `slice/README.md:74-75` ("A plate configuration is read and checked when it arrives,
     before it is queued"), `:413` ("the log line of each plate configuration"), `:526`
     ("A plate configuration that is never queued"), `web.py:21` and `:140`,
     `limits.py:35`. The modules table gives `plate_configuration.py` "running its slice".
   - "job" for a print, in four sentences a student reads ("print the rest in a second
     job": `limits.py:63` and `:65`, `errors.py:28`, `:30`, `:74`), beside slice job and
     delivery job.
   - `contracts/sliced-file.md:5`: "its HTTP interface" follows "what Orca Slicer exports",
     so "its" reads as Orca's; lines 26, 47 and 70 speak of "the output directory", which a
     caller of the HTTP interface never sees now that the command is gone.
   - `contracts/plate-configuration.md` and `contracts/error-report.md`: no confusion
     found.

   Fixed means each place uses the one term, or the owner rules that "instance of the
   service" stays.
