# Slice service

The guide for a person. Everything a builder needs (every figure, rule, error code and
required test) is in [README-details.md](README-details.md). Everything here outside
"To be built" is true of the code as built.

## What it does

The slice service takes a [plate configuration](../contracts/plate-configuration.md):
the parts as binary STL files, where each **instance** (one placement of a part) sits on
the plate and how it is turned, and the printer, filament and process profiles with
setting overrides. It runs Orca Slicer 2.4.2 headless and returns a
[sliced file](../contracts/sliced-file.md) (`.gcode.3mf`) with its summary. Slicing one
plate configuration is one **slice job**. Every failure is an
[error report](../contracts/error-report.md), and a running slice job sends
[progress reports](../contracts/progress-report.md). It knows nothing of Onshape, users,
web sessions or printers.

Every part is checked before Orca runs: a part that cannot be sliced (not an STL, ASCII,
too detailed, too small, no volume, too large for the printer) refuses the plate
configuration with a report naming the part, and a part Orca copes with (holes in its
surface, faces wound inwards, or every side under 5 mm, which may be an inch file read as
millimetres) only warns. While Orca runs, the **memory watchdog**, a thread of the slice
service, reads the memory of Orca's processes every 0.25 s and stops Orca when it passes
the **memory ceiling**. Orca's own reasons for a failed slice are read from its
`result.json` and its debug log and put into the error report.

A running slice service is one **slice service process**: its slice jobs live in that
process's memory, so a client must keep talking to the process that accepted its slice
job, and several worker processes behind one address lose slice jobs.

More: [README-details.md, Checks on every part](README-details.md#checks-on-every-part)
and [Orca Slicer](README-details.md#orca-slicer).

## Run and test it

```
make -C slice install        # the Python environment, and Orca Slicer into slice/tools/orca
uv run --project slice python -m penguin_slice serve --work /var/tmp/penguin-slice --port 8640
```

`serve` writes one JSON log line per slice job transition on stderr. SIGTERM or Ctrl-C
cancels every slice job and waits until every Orca is gone. A bad setting stops it before
it listens, with exit status 2.

| Target | What it runs |
|---|---|
| `make -C slice test` | The fast suite, in random order: no Orca, no network, no real waiting |
| `make -C slice test-parallel` | The fast suite on `WORKERS` worker processes (default 2) |
| `make -C slice test-flakes` | The fast suite `RUNS` times (default 10), each in a new random order |
| `make -C slice coverage` | Branch coverage under the fast suite; fails under 100% |
| `make -C slice test-upstream` | The upstream check: the tests that run the real Orca, one at a time (`test-orca` is the same) |
| `make -C slice upgrade-orca VERSION=x.y.z` | Moves the Orca pin, regenerates the profiles, runs the upstream check |

More: [README-details.md, Use](README-details.md#use) and
[Tests](README-details.md#tests).

## The HTTP interface

The HTTP interface is the slice service's one way in:

| Request | Answer |
|---|---|
| `POST /slices`, the plate configuration and one file field per part | 202 with the slice job's id, its first progress report and the part warnings |
| `GET /slices/<job>` | The latest progress report |
| `GET /slices/<job>/events` | The progress reports as server-sent events, starting with the latest one, then each new one, ending with the final one |
| `DELETE /slices/<job>` | Cancel the slice job |
| `GET /slices/<job>/file` | The sliced file of a done slice job |
| `GET /slices/<job>/summary` | The sliced file's summary, as JSON |

Every other answer is an error report with an HTTP status, for example: 422 for a plate
configuration a check refused, 503 when no more slice jobs may wait (`slice.busy`), 404
for an unknown slice job.

More: [README-details.md, The HTTP interface](README-details.md#the-http-interface) and
[Error codes](README-details.md#error-codes).

## The limits that matter

| Limit | What it bounds | As built |
|---|---|---|
| Memory ceiling (`PENGUIN_SLICE_MAX_PEAK_MB`) | The memory of one Orca: the watchdog stops it past this (`slice.out_of_memory`) | 2,000 MB, a setting |
| Time limit | How long one Orca may run (`slice.timeout`) | 240 s, fixed in the code |
| Running at once | Orcas in one slice service process | 1, fixed in the code |
| Waiting | Slice jobs waiting behind the running one; one more gets `slice.busy` | 2, fixed in the code |
| Instances | Placements on one plate | 150 |
| Parts | Different parts on one plate; with the 7.5 MB of one part this bounds one submission at 188.5 MB | 25 |
| One part | Triangles and bytes of one STL | 150,000 triangles, 7.5 MB |
| Spacing | Least gap between two instances' footprints | 5 mm, 12 mm with supports on |

The ceiling does not bound Orca exactly: Orca can pass it by the rise between two
readings (502 MB at most, measured), and a plate that passes it in its last moments is
delivered with a note in its log line. So a host gives one slice service process 3.5 GB
with the 2,000 MB ceiling: Orca at about 2,500 MB, 400 MB for the slice service itself,
and a fifth more for what was not measured. The plates the Popcorn Penguins print peak at
1,415 MB at most, with supports on; a full plate of twelve of the robot's largest block
(the Elevator Block Bottom Inner) with supports on, or of about 95 pulleys or more, passes
the ceiling and is stopped with a remedy of a second plate. The time limit, 240 s, is
about twenty-five times the 9.4 s that the largest plate of small spacers allowed, 150 of
them, takes to slice. All of this was measured on aarch64 Linux machines.

More: [README-details.md, Plate limits](README-details.md#plate-limits).

## Where it stands

Built and tested: the HTTP interface, the checks on every part, slicing with the pinned
Orca 2.4.2, Orca's own stages and percentage as progress, cancellation and cleanup that
leave no Orca and no files, the memory watchdog, Orca's reasons from its `result.json` and
its debug log, one log line per slice job transition, and `make upgrade-orca` with the
upstream check. The fast suite covers every branch. The upstream check slices 100 spacers
in a 10 by 10 grid and the eight real parts of the Popcorn Penguins' robot.

Several things stated above change, as To be built says: in phase 2, the rule that a slice
job nobody follows is cancelled 120 s after its last follower left, or after it was
submitted if none ever came; the rule that a finished slice job's record and sliced file
are kept for an hour; the request that carries a whole plate's files; and the stop that
cancels every slice job. In phase 3, the time limit and the counts fixed in the code
become settings.

More: [README-details.md, Where it stands](README-details.md#where-it-stands).

## To be built

What [the architecture](../docs/architecture.md) adds or changes, by the phase of
[the plan](../docs/plans/penguin-slicer-plan.md). Names used below: the **front server**
is the one process the browser talks to and the slice service's only caller, and the
**user key** is the signed-in user's Onshape id, which the front server sends with every
request. Hosted, the slice service runs alone in the **slice container** on Railway, which
holds no credentials and is reached only by the front server.

**Phase 2, one machine:**

- Every request carries the user key; a user key sees only its own parts and slice jobs.
- The **part store**: each part is uploaded once, checked on arrival and kept under the
  user key and its SHA-256 hash, for two hours after its last use, at most 25 parts per user
  key, within a disk limit, emptied at start. It is a cache; the browser keeps the parts.
- A plate configuration names parts by hash and carries no files; a missing part gets an
  error report listing the missing hashes, and the page uploads them again. `POST /slices`
  then takes the plate configuration alone, and a new route takes one part.
- One unfinished slice job per user key: a new submission cancels the earlier one.
- A slice job runs to its end whether or not anyone follows it (the 120 s rule goes).
- A slice job is remembered for two hours after it ends; its sliced file is deleted once
  the front server has stored it.
- A route lists the slice jobs, for a restarted front server.
- A waiting slice job's progress report says how many are ahead of it.
- Asked to stop, the slice service finishes the running slice and waits for its sliced file
  to be fetched.

**Phase 3, hosted on Railway:**

- The time limit, how many Orcas run at once and how many slice jobs wait become settings,
  starting at 240 s, one and two.
- The memory ceiling is set to 6,000 MB of the slice container's 8 GB, a figure the
  approved design proposes, so only one Orca runs at once.
- Plates of rising weight up to the ceiling are sliced and timed on the slice container,
  and set the ceiling, the time limit (a few times the slowest plate that finishes) and the
  slice service's estimates of a plate's memory and time.
- The stream of progress reports (`GET /slices/<job>/events`) sends a comment line at least
  every 15 s while it has nothing to report.
- Orca runs as a Unix user of its own; a new Orca version is a new image.
- A route gives the front server the log lines. Three kinds of log line are new: a warning
  for a slice that passes 80 percent of the memory ceiling or of the time limit, one line a
  minute with the memory held and the slice jobs running and waiting, and one line for
  every exception and every refusal.

Phases 4 and 5 change nothing here.

Not yet known:

- How Orca behaves on Railway's machines, believed x86_64: every measurement is from
  aarch64 Linux and from plates under 2,600 MB.
- How many processors the slice container gets, how long real plates take there, and how
  often two users slice at the same moment.
- What the part store takes on disk, and so its disk limit, and what the slice service
  needs beside Orca hosted.

More: [README-details.md, To be built](README-details.md#to-be-built).

## What is not known

- Orca 2.5.x cannot be taken yet: it packs the Bambu Lab profiles in a file the profile
  script cannot read.
- A part whose first layer is empty gets only a general sentence, since Orca writes the
  reason nowhere; parts that intersect themselves are not detected; the expected time that
  each progress report carries is only within about a factor of two.
- Not measured: the disk held by finished slice jobs, Orca's CPU time, and how many slices
  one host can run at once.

More: [README-details.md, Where it stands](README-details.md#where-it-stands) and
[Taking a new upstream version](README-details.md#taking-a-new-upstream-version).
