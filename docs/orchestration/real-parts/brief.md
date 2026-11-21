# Brief: the team's real parts in the slice service's tests

- **Deliverable (REQUIRED):** the eight real parts committed-ready in the repository
  with their licence note, tests that use them, measured figures in the slice service's
  guide, and a result file at `docs/orchestration/real-parts/result.md` that lists what
  you did, every figure, every choice, and anything not done with the reason.
- **Stop condition (REQUIRED):** every part below is accepted by the slice service's
  checks and slices with the real Orca, alone and on mixed plates, the same way on every
  run; the fast suite passes 20 times in random order on 2 workers (`make -C slice
  test-flakes RUNS=20 WORKERS=2`) and stays within about a second of its present time
  (about 4 s); branch coverage stays at 100%; the real-Orca suite passes three times in a
  row.
- **Budget (REQUIRED):** 150 minutes; no cloud spend.
- **Where this fits:** a fresh reviewer who never sees your result file will check the
  work afterwards.

## Background

The owner's robotics team (FRC Team 6238) has given eight STL files of parts from its real
robot, in `/repos/popcornpenguins/PartsFRC/`. They were printed and work on the robot, so
**a refusal, a warning that is not true, a failed slice or a wrong placement of any of
them is a defect in the slice service, not in the part.** Investigate each such case at
its cause; if a part truly has a flaw (for example the mesh is not closed), say exactly
what, with evidence, and make sure the slice service's sentence about it is true and
useful, since the team printed it anyway.

| File | Size |
|---|---|
| Clamp Plate Inner.stl | 438 kB |
| Elevator Block Bottom Inner.stl | 1.95 MB |
| Elevator Block Carriage.stl | 1.18 MB |
| Elevator Block Top.stl | 1.75 MB |
| Elevator Top Inner.stl | 970 kB |
| Inner Spacer.stl | 145 kB |
| Outer Clamp.stl | 436 kB |
| Pulley v3.stl | 230 kB |

The owner: "These are from my team so we can add them with an MIT license into the source
repo." The repository has no top-level licence file; do not add one. Put the parts in one
folder of their own under `slice/` (your choice of path, for example
`slice/tests/fixtures/frc-parts/`), with a `README.md` there that says what they are, that
they are parts of FRC Team 6238's robot that were printed and used, and that they are
offered under the MIT licence, with the licence text and "Copyright (c) 2026 FRC Team
6238 Popcorn Penguins". Keep the original file names, or rename to plain lower-case names
with hyphens and list the original name of each in that README.

Keep every existing test part (the generated spacers, the hostile and broken files, the
sample part). Remove or replace one only where a real part is a clear substitute that
tests the same thing, and say so.

## What to build

1. **Read and check, in the fast suite.** Each real part is read and passes the checks of
   a plate configuration; the part information the slice service reports (size, volume,
   triangle count, resting positions if it reports them) is asserted against values you
   measure once and write into the test. Parsing about 7 MB of STL must not make the fast
   suite noticeably slower: measure it, and if it costs more than about half a second in
   all, move the heavy part to the real-Orca suite and keep only the smaller parts in the
   fast suite.
2. **Slice with the real Orca, in the real-Orca suite** (which `make upgrade-orca` also
   runs, so these become part of the check that a new Orca version still works):
   - each part alone, at the default profiles, through the HTTP interface;
   - a mixed plate of all eight parts, one instance each, arranged so they fit;
   - a plate that a team would really print: several instances of the small parts
     (spacers, clamps, pulley) together with one or two large ones.
   For each, assert the sliced file is valid, the summary's print time and filament are
   plausible and within a stated band of the values you measure, every instance lands at
   its own position, and no error report or untrue warning is given.
3. **Consistency.** The owner asked that the parts "work consistently". Slice each plate
   at least three times in separate runs and show the result is the same each time: the
   G-code identical, or, if Orca's output carries a timestamp or other varying field,
   identical apart from fields you name. If anything varies beyond that, find out why and
   report it; do not loosen a test to hide it.
4. **Measure** peak memory, slicing time and sliced-file size for each plate, one Orca at a
   time on a quiet machine where you can, and add them to the guide beside the other
   reference plates. The real team plates are the first real measurements the project
   has; say so in the guide.

## Rules

Read [the standing rules](../review-feedback/briefs/standing-rules.md) and follow them,
with these differences: your folders are `slice/` (and `contracts/` only if a real part
shows a contract is wrong); this is a different run, so your scratch folder is
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/real-parts/`.
The working branch is `tests/real-frc-parts`, already checked out. Copy the parts from
`/repos/popcornpenguins/PartsFRC/` with `cp` (literal paths); do not change or remove the
originals.
