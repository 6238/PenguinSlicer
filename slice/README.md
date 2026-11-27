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
configuration with a report naming the part, and a part Orca copes with (holes, faces
wound inwards, perhaps in inches) only warns. While Orca runs, the **memory watchdog**, a
thread of the slice service, reads the memory of Orca's processes every 0.25 s and stops
Orca when it passes the **memory ceiling**. Orca's own reasons for a failed slice are read
from its `result.json` and its debug log and put into the error report.

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

No test of the fast suite can hang: every wait gives up after 10 s, and a test still
running after 20 s fails. The upstream check runs one real Orca at a time.

More: [README-details.md, Use](README-details.md#use) and
[Tests](README-details.md#tests).

## The HTTP interface

The HTTP interface is the slice service's one way in:

| Request | Answer |
|---|---|
| `POST /slices`, the plate configuration and one file field per part | 202 with the slice job's id, its first progress report and the part warnings |
| `GET /slices/<job>` | The latest progress report |
| `GET /slices/<job>/events` | The progress reports as server-sent events, the latest first, ending with the final one |
| `DELETE /slices/<job>` | Cancel the slice job |
| `GET /slices/<job>/file` | The sliced file of a done slice job |
| `GET /slices/<job>/summary` | The sliced file's summary, as JSON |

Every other answer is an error report with an HTTP status: 422 for a plate configuration a
check refused, 503 when the queue is full (`slice.busy`), 404 for an unknown slice job.

More: [README-details.md, The HTTP interface](README-details.md#the-http-interface) and
[Error codes](README-details.md#error-codes).

## The limits that matter

| Limit | What it bounds | As built |
|---|---|---|
| Memory ceiling (`PENGUIN_SLICE_MAX_PEAK_MB`) | The memory of one Orca: the watchdog stops it past this (`slice.out_of_memory`) | 2,000 MB, a setting |
| Time limit (`PLATE_SLICE_TIMEOUT_S`) | How long one Orca may run (`slice.timeout`) | 240 s, fixed in the code |
| Running at once (`MAX_RUNNING`) | Orcas in one slice service process | 1 |
| Waiting (`MAX_QUEUED`) | Slice jobs queued behind it; one more gets `slice.busy` | 2 |
| Instances (`MAX_INSTANCES`) | Placements on one plate | 150 |
| Parts (`MAX_PARTS`) | Different parts on one plate, and so the upload | 25 |
| One part | Triangles and bytes of one STL | 150,000 triangles, 7.5 MB |
| Spacing | Least gap between two instances' footprints | 5 mm, 12 mm with supports on |

The ceiling does not bound Orca exactly: Orca can pass it by the rise between two
readings (502 MB at most, measured), and a plate that passes it in its last moments is
delivered with a note in its log line. So a host gives one slice service process 3.5 GB
with the 2,000 MB ceiling. The plates the Popcorn Penguins print peak at 1,415 MB at most,
with supports on; a full plate of twelve Elevator Block Bottom Inners with supports on, or
of about 95 pulleys or more, passes the ceiling and is stopped with a remedy of a second
plate. The time limit is about twenty
times what 150 spacers take. All of this was measured on aarch64 Linux machines.

More: [README-details.md, Plate limits](README-details.md#plate-limits).

## Where it stands

Built and tested: the HTTP interface, the checks on every part, slicing with the pinned
Orca 2.4.2, Orca's own stages and percentage as progress, cancellation and cleanup that
leave no Orca and no files, the memory watchdog, Orca's reasons from its `result.json` and
its debug log, one log line per slice job transition, and `make upgrade-orca` with the
upstream check. The fast suite covers every branch. The real-Orca suite slices 100 spacers
in a 10 by 10 grid and the eight real parts of the Popcorn Penguins' robot.

Two rules of the code as built change in phase 2: a slice job nobody follows is cancelled
120 s after its last follower left, and a finished slice job's record and sliced file are
kept for an hour.

More: [README-details.md, Where it stands](README-details.md#where-it-stands).

## To be built

What [the architecture](../docs/architecture.md) adds or changes, by the phase of
[the plan](../docs/plans/penguin-slicer-plan.md). Two new names: the **front server** is
the one process the browser talks to and the slice service's only caller, and the **user
key** is the signed-in user's Onshape id, which the front server sends with every request.
Hosted, the slice service runs alone in the **slice container** on Railway, which holds no
credentials and is reached only by the front server.

**Phase 2, one machine:**

- Every request carries the user key; a user key sees only its own parts and slice jobs.
- The **part store**: each part is uploaded once, checked on arrival and kept under the
  user key and its SHA-256 hash, for two hours after its last use, at most 25 parts per user
  key, within a disk limit, emptied at start. It is a cache; the browser keeps the parts.
- A plate configuration names parts by hash and carries no files; a missing part gets an
  error report listing the missing hashes, and the page uploads them again. The route that
  takes a whole plate's files is removed.
- One unfinished slice job per user key: a new submission cancels the earlier one.
- A slice job runs to its end whether or not anyone follows it (the 120 s rule goes).
- A slice job is remembered for two hours; its sliced file is deleted once the front server
  has stored it.
- A route lists the slice jobs, for a restarted front server.
- A waiting slice job's progress report says how many are ahead of it.
- Asked to stop, the slice service finishes the running slice and waits for its sliced file
  to be fetched.

**Phase 3, hosted on Railway:**

- The time limit, how many Orcas run at once and how many slice jobs wait become settings,
  starting at 240 s, one and two.
- The memory ceiling is set to 6,000 MB (proposed) of the slice container's 8 GB, so only
  one Orca runs at once.
- Plates of rising weight up to the ceiling are sliced and timed on the slice container,
  and set the ceiling, the time limit (a few times the slowest plate that finishes) and the
  estimates.
- A quiet progress stream sends a comment line at least every 15 s.
- Orca runs as a Unix user of its own; a new Orca version is a new image.
- A route gives the front server the log lines; new lines for slices near a limit (80
  percent), once a minute, and every exception and refusal.

Phases 4 and 5 change nothing here.

More: [README-details.md, To be built](README-details.md#to-be-built).

## What is not known

- How Orca behaves on Railway's machines, believed x86_64: every measurement is from
  aarch64 Linux and from plates under 2,600 MB.
- How many processors the slice container gets, how long real plates take there, and how
  often two users slice at the same moment.
- What the part store takes on disk, and so its disk limit, and what the slice service
  needs beside Orca hosted.
- Orca 2.5.x cannot be taken yet: it packs the Bambu Lab profiles in a file the profile
  script cannot read.
- A part whose first layer is empty gets only a general sentence, since Orca writes the
  reason nowhere; parts that intersect themselves are not detected; the expected time is
  only within about a factor of two.

More: [README-details.md, Where it stands](README-details.md#where-it-stands) and
[Taking a new upstream version](README-details.md#taking-a-new-upstream-version).
