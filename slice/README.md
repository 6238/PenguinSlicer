# Slice service

Takes a [plate job](../contracts/plate-job.md) (the parts as STL files, where each copy
sits on the plate and how it is turned, the printer, filament and process profiles with
setting overrides), runs Orca Slicer headless, and returns a
[sliced file](../contracts/sliced-file.md) (`.gcode.3mf`) with its summary. Every failure
becomes an [error report](../contracts/error-report.md); a running slice sends
[progress reports](../contracts/progress-report.md). It knows nothing of Onshape, teams,
web sessions or printers.

## Use

```
make -C slice install        # the Python environment, and Orca Slicer into slice/tools/orca
make -C slice test           # the fast suite
```

The command line slices a plate job file and prints the summary as JSON, or prints the
error report as JSON on stderr and exits 1:

```
uv run --project slice python -m penguin_slice slice contracts/examples/plate-job.json --out /tmp/sliced
```

Ctrl-C or SIGTERM during `slice` stops Orca, removes the scratch folder and prints the
`slice.cancelled` error report (exit 1). `serve` runs the HTTP face (below) and writes one
JSON log line per job transition on stderr; stopping it with Ctrl-C or SIGTERM (what a
container host sends) cancels every job, sends each subscriber its `cancelled` report and
waits until every Orca is gone:

```
uv run --project slice python -m penguin_slice serve --work /var/tmp/penguin-slice --port 8640
```

The library:

```python
from penguin_slice import error_report, slice_plate_job

try:
    sliced = slice_plate_job("plate-job.json", "out/")     # or a JSON value, with base_dir=
    sliced.path, sliced.summary
except Exception as exc:
    report = error_report(exc)
```

`slice_plate_job` checks the plate job first (the order is in
[plate-job.md](../contracts/plate-job.md), "Checks"), then slices it in a scratch folder
inside the output folder, moves the sliced file to `<out>/<name>` and removes the scratch
folder on every way out. The move is a rename inside the output folder: it replaces a
file of the same name, and a folder of that name fails the slice with
`slice.output_unwritable`. It takes `stop` (a `slicer.Stop`, to cancel) and
`on_progress(stage, fraction, message)`.

## The HTTP face

`penguin_slice.web.create_app(work_dir)` is a Flask app factory:

| Request | Answer |
|---|---|
| `POST /slices` with form field `plate_job` (the JSON) and one file field per part, named as the part's `stl` | 202 with `job`, the first progress report and the `part_warnings` |
| `GET /slices/<job>` | The latest progress report |
| `GET /slices/<job>/events` | The progress reports as `text/event-stream`, the latest first, ending with the final one |
| `DELETE /slices/<job>` | Cancel: `{"cancel": "cancelled" \| "cancelling" \| "finished"}` |
| `GET /slices/<job>/file` | The sliced file of a done job; its summary in the `X-Slice-Summary` header |

Every other answer is an error report: 400 for a request that is not a plate job, 404 for
an unknown job (`slice.unknown_job`) or a path the face does not offer
(`slice.bad_request`, also 405 for a method a path does not take), 409 for a file that is
not there (the job's own error report, `slice.cancelled` or `slice.not_ready`), 410 for a
sliced file gone from the disk (`slice.file_gone`), 413 for an upload over
`MAX_COPIES x MAX_PART_BYTES`, 422 for a plate job a check refused, 500 for the server's
own failure (`slice.scratch_unwritable` when the work folder cannot be written or an
upload cannot be saved in it, a full disk for one,
`slice.unexpected` for a bug, logged with its traceback), 503 when the queue is full. A plate job is read and checked when it arrives, before it is queued, so a refusal
comes back at once; its STL paths must name files sent with it. Each job's files live in
`<work>/slice-<pid>-<start>-<random>/`; they are removed when the job ends failed or
cancelled, or when its record expires (`RECORD_TTL_S`, an hour after its final report).

## Orca Slicer

The slice service runs the Orca wrapper named by the environment variable
`PENGUIN_SLICE_ORCA`, or else `slice/tools/orca/orca-slicer`. It looks when a slice starts,
so the fast suite runs without Orca. `scripts/install-orca.sh` installs the pinned release
there (`PENGUIN_SLICE_ORCA_DEST` installs elsewhere, `PENGUIN_SLICE_ORCA_CACHE` keeps and
reuses each verified download). Its `ORCA_VERSION` line, with the three checksums below
it, is the only place the Orca version is stated; the tests read it from there.
Idempotent, the script exits at once when `tools/orca/VERSION` already records this
version for this platform. Linux x86_64, Linux aarch64 and macOS arm64 only.

On Linux the AppImage is extracted (no FUSE needed) and the wrapper runs the binary
directly with its own library path. When the host lacks Orca's runtime libraries and the
script is not running as root, it unpacks the missing Ubuntu 24.04 packages into
`tools/orca/hostlibs/`, verified against the archive's SHA-256 index. As root it stops
instead; install the distribution's packages:

```
libopengl0 libegl1 libgl1 libglx0 libglu1-mesa libgtk-3-0t64 libgdk-pixbuf-2.0-0
libatk1.0-0t64 libcairo2 libcairo-gobject2 libpango-1.0-0 libpangocairo-1.0-0
libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 libglib2.0-0t64 libdbus-1-3
libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libwebkit2gtk-4.1-0
libjavascriptcoregtk-4.1-0 libsoup-3.0-0 libsecret-1-0 libwayland-client0 libwayland-egl1
libwayland-server0 libxkbcommon0 libx11-6 libxext6 libsm6 libice6 libstdc++6 libexpat1
liblzma5 libmspack0t64 zlib1g
```

`slicer.py` is the one module that runs Orca and reads what Orca writes: the command
lines, the environment, Orca's return codes (`ORCA_RETURN_CODES`, the only table of them),
its reasons in `result.json`, its progress messages (`ORCA_STAGES`), and the sliced file's
entries. A change in a new Orca is absorbed there.

**How Orca is run.** With an allowlisted environment (`PATH`, `TMPDIR`, `LANG`, `USER`,
`LOGNAME`) and its own `HOME`, `XDG_CONFIG_HOME`, `XDG_RUNTIME_DIR` and `--datadir` in the
slice's scratch folder, so secrets never reach it and two slices never share state; in a
session of its own, so Orca and every child it starts form one process group; on Linux
with `PR_SET_PDEATHSIG`, so Orca dies with the thread that started it even when the
service is killed outright; with stdout and stderr read as they arrive into a tail of the
last 200 lines (a line is cut at 4 KB), so megabytes of output neither block Orca nor sit
in memory. A plate is sliced with `--arrange 0 --orient 0`: Orca keeps every copy where
the plate job put it.

**Stopping Orca.** A cancel or the timeout sends SIGTERM to the process group, waits
`STOP_GRACE_S` (5 s) for Orca to go, then sends SIGKILL. Whatever is left of the group is
killed once Orca has exited, and only then is Orca reaped, so the group's id cannot be
reused under the service. A cancel is reported only after all of this.

**What Orca reports while slicing.** Found by experiment with the pinned 2.4.2, headless on
aarch64 Linux: stdout carries almost nothing (one line on failure, `run found error,
return -100, exit...`, and at most a harmless Wayland socket warning); `--debug 3` and up
write a debug log to a file, not to stdout. `--pipe <path>` is the progress channel: Orca
opens the path (a FIFO the service makes) and writes one JSON object per line,
`{"message", "plate_count", "plate_index", "plate_percent", "total_percent"}`, at each of
its stages: "Start to load files" (1%), "Loading files finished" (2), "Prepare slicing"
(3), "Slicing begins" (6), "Slicing mesh" (7), "Generating walls" (16), "Generating infill
regions" (25), "Generating infill toolpath" (34), "Checking support necessity" (48),
"Detect overhangs for auto-lift" (66), "Optimizing toolpath" (70), "Generating G-code"
(75), "Slicing finished" (93), "Generate thumbnails" (94), "Exporting 3mf" (97), "All done,
Success" (100). The slice service maps each message to a stage (`slicer.ORCA_STAGES`) and
reports Orca's own `total_percent` as the fraction; it invents none between messages. On
a small plate the first messages can arrive together. Generating G-code takes most of the
time on a large plate, so the fraction sits at 0.75 longest. `--debug` changes nothing
the service reads.

**What Orca says when it fails.** Its return code is in `result.json` (`return_code`)
and in the exit status as a byte (-100 is exit 156). Its general reason is
`error_string`; the specific one, when it gives one, is `sliced_plates[].warning_message`,
for example "Object can't be printed for empty layer between 9.9 and 11.34.\nObject: Tower
#1\nMaybe parts of the object at these height are too thin, or the object has faulty
mesh". Both are read before the scratch folder is removed and kept in the detail. For a
plate with nothing to slice Orca returns -100 with only the general `error_string`, and
says why on stdout: "No layers were detected. You might want to repair your STL file(s) or
check their size or thickness and retry." (an open 100 mm box, a box with half its
triangles, a tilted flat sheet) or "The print is empty. The model is not printable with
current print settings." (a 0.15 mm cube, a 0.15 mm needle); the service reads those lines
(`ORCA_OUTPUT_REASONS`) into `slice.no_layers` and `slice.print_empty`, and into the log's
Orca reason. An Orca that cannot load a shared library exits 127 with the loader's words
and no `result.json` (`slice.orca_unstartable`). A
critical warning such as "floating regions" reaches only the debug log; see
[patches/orca/README.md](patches/orca/README.md). Under an address-space limit Orca prints
`std::bad_alloc` and returns -100 (1 GB), or aborts with SIGABRT after "terminate called
recursively" (500 MB, reported as a crash: the words do not say memory).

## Profiles

`src/penguin_slice/profiles/` holds the default set, three self-contained Orca profiles
flattened from the BBL vendor tree inside the installed Orca:

| File | Source profile |
|---|---|
| `printer.json` | `machine/Bambu Lab H2S 0.6 nozzle` |
| `filament.json` | `filament/Generic PETG @BBL H2S` |
| `process.json` | `process/0.24mm Balanced Quality @BBL H2S 0.6 nozzle` |

A Bambu Lab H2S with the 0.6 mm High Flow hardened steel nozzle, Generic PETG and the
Textured PEI Plate. The nozzle variant and the plate are in no vendor profile, so the
flattening script writes `nozzle_volume_type` and `curr_bed_type` into every printer
profile itself; without them Orca's command line falls back to the Standard nozzle and
the smooth plate, silently.

`profiles/catalog/` holds every Bambu Lab H2S printer and every filament and process that
names one, flattened the same way, with `index.json` listing which printers each fits.
These are the names a plate job may use. Orca's command line does not resolve `inherits`
and the desktop app exports only differences, so both are regenerated after an Orca
upgrade (`make upgrade-orca` does it):

```
uv run --project slice python slice/scripts/flatten_orca_profiles.py
uv run --project slice python slice/scripts/flatten_orca_profiles.py --audit-only   # resolved values and their sources
```

## Sample part

`src/penguin_slice/sample_part.stl`, an L bracket 40 x 30 x 12 mm (binary STL, 20
triangles), written by `scripts/make_sample_part.py`; the fast suite checks that the two
agree byte for byte. `slicer.slice_stl` slices it alone with the default set and
`--arrange 1`.

## Checks on every part

Every part a copy uses is read and examined when the plate job arrives, before any slice
starts (`mesh.read_binary_stl` and `mesh.analyse`). A finding that makes a slice
impossible or pointless refuses the plate job with an error report naming the part; a
finding Orca copes with only warns, and the warning travels in the sliced file's summary
(`part_warnings`) and in the HTTP face's answer to the submission.

| Finding | Refuse or warn | Code |
|---|---|---|
| The file is empty, too short, not an STL (an image such as a PNG or JPEG, a PDF, a zip or 3MF, a gzip, UTF-16 text, text of any length such as an HTML or JSON error page, or any file whose header gives a triangle count larger than any part the service takes), cut off, padded, has 0 triangles, or a coordinate that is not a finite number | Refuse | `slice.part_unreadable` |
| An ASCII STL, in any case and with or without a byte-order mark | Refuse | `slice.part_not_binary` |
| Over `MAX_PART_TRIANGLES` or `MAX_PART_BYTES` | Refuse | `slice.part_too_detailed` |
| 0.1 mm or less in every direction, or in one (flat) | Refuse | `slice.part_too_small` |
| Every triangle a line or a point; or no triangle shares an edge with another; or a closed surface in one plane or enclosing no volume (faces laid on top of each other) | Refuse | `slice.part_no_volume` |
| Fits the printer in no orientation at any angle | Refuse | `slice.part_too_large` |
| Open edges (holes, slivers, a thin open lattice): "has holes in its surface"; or, with no open edge, edges shared by more than two faces (faces doubled, a part laid over its mirror image): "has faces laid on top of each other" | Warn | `slice.part_not_watertight` |
| Closed, with its faces wound inwards | Warn | `slice.part_inside_out` |
| Every side under 5 mm (an inch file read as millimetres?) | Warn | `slice.part_maybe_inches` |

Why these: the pinned Orca slices an open box, an inside-out box, two shells, a
self-intersecting pair of boxes and a 2 x 1 x 0.5 mm block (the real-Orca suite proves
it), so refusing them would refuse good prints; a part with holes is the one that later
fails with empty layers, so its warning names it before the slice. Self-intersection is
not looked for. The fit test is a necessary condition (least width against the plate's
short side, diameter against its diagonal, height), so a part it refuses truly fits
nowhere; a long part that fits only turned towards the diagonal passes and the placement
decides.

## Plate limits

The plate triangle cap is gone: triangles cost Orca time, not memory. The plate limits
that refuse a plate job before slicing are the copies (`MAX_COPIES`), the triangles and
bytes of one part, and each part's size against the plate and the printer. Memory refuses
nothing before slicing.

**The memory watchdog** is the guard on memory. While Orca runs, a thread of the slice
service samples Orca's whole process group (`slicer.group_memory_kb`, from
`/proc/<pid>/stat` and `/proc/<pid>/status`) at once and then every `MEMORY_SAMPLE_S`
(0.25 s). Each sample reads every process's current resident memory (`VmRSS`) and the
kernel's high-water mark of it (`VmHWM`, its peak since the process started), summed over
the group. The pinned Orca's memory peaks in spikes shorter than 0.1 s near the end of a
slice, which a reading of the current figure misses most of the time; the high-water mark
keeps the spike, so the next sample sees it. When a sample's peak passes the memory
ceiling, the setting `PENGUIN_SLICE_MAX_PEAK_MB` (900 MB by default), the watchdog stops
Orca as a cancel does (SIGTERM to the group, SIGKILL after the grace time) and the slice
fails with `slice.out_of_memory`: "This plate is too large to slice: the slicer needed
more than the 900 MB of memory the print server allows.", with the peak, where it was
read and the ceiling in the detail. A slice is reported out of memory only on that stop,
on a kill with the kernel's `oom_kill` count (cgroup `memory.events`) risen, or when Orca
prints `bad_alloc`; a kill with neither is `slice.orca_killed`.

**What the ceiling guarantees.** The ceiling protects the server from a slice that keeps
growing; it is not a promise that no delivered slice ever touched it. A plate whose peak is
over the ceiling may be stopped with `slice.out_of_memory`, or may finish and be delivered
with a note, depending on timing: the same plate job sent twice can get the two answers.
It is never silent, and the peak reported is the true peak. A complete sliced file is
never discarded by the watchdog: if Orca has written it before the watchdog's sample
stops Orca (Orca exits by itself, or the watchdog's SIGTERM ends Orca after the file is
complete; see "How a slice ends"), the sliced file is delivered even though the peak is
over the ceiling. The job's result and its `done` log line then carry `memory_note`
("Orca's processes reached a peak of ... kB (...), over the ceiling of ... kB
(PENGUIN_SLICE_MAX_PEAK_MB=...), and Orca finished before the watchdog stopped it: the
sliced file is delivered", or "... and the watchdog stopped Orca only after it had
written the complete sliced file: ..."), so support can see it. The peak reported
everywhere (`peak_rss_kb` in the log, the detail, the note) is the higher of the
watchdog's last high-water reading and the kernel's `ru_maxrss` of Orca at exit, so it is
never under Orca's own peak. Where the kernel's own limit is lower than the ceiling the
kernel acts first.

Measured on an aarch64 Linux machine with the pinned Orca, one slice at a time:

- 12 hubs of 20,000 triangles (peak 442 to 459 MB): six slices at a ceiling of 426 MB, 5 %
  under the peak, were all stopped with `slice.out_of_memory`, each reporting a high-water
  reading equal to Orca's `ru_maxrss`, while the highest current figure the same samples
  read was 362 to 380 MB.
- 6 hubs of 20,000 triangles (four free slices peaked at 265,540 to 269,336 kB): at
  ceilings 10 %, 3 % and 0.5 % under the lowest peak, 9 of 12 slices were stopped and 3
  delivered with the note; at ceilings 0.5 %, 3 % and 10 % over the highest peak, 12 of 12
  were delivered with no note. This plate's memory rises from about 210 MB to about 270 MB
  in its last 150 ms, while Orca writes the sliced file, so whether a 0.25 s sample lands
  before Orca exits is chance. Every stopped slice reported a peak of 264,048 to
  273,188 kB (the watchdog's high-water reading equal to `ru_maxrss`), every delivered
  one 270,332 to 274,620 kB: none under the free slices' peaks.

The real-Orca suite runs a real slice with a ceiling of 100 MB to show the stop, and a
slice at a ceiling 5 % under the plate's own peak to show the high-water reading (stopped,
or delivered with the note).

**How a slice ends** is decided in one place, `slicer.settle`, in this order:

1. A complete sliced file is never discarded by a stop the slice service decides on
   itself. When Orca exited 0, or was stopped for a timeout or by the watchdog, and its
   sliced file is complete, the slice succeeds. Complete means, for a normal success and
   after a stop alike: the file is there under its final name (Orca writes
   `plate.gcode.3mf.tmp` and renames it once written); it opens as a zip, which needs the
   end-of-central-directory record and the central directory, the last bytes written, so
   a file cut anywhere fails; the G-code header reads; it has `Metadata/plate_1.gcode`
   and, for a plate, `Metadata/plate_1.json`; and every entry decompresses and matches
   its CRC-32. Then the name guard checks every copy is in it, as for any slice. A stop
   that reached Orca is recorded in the job's result and its `done` log line as
   `stop_note` ("stopped by the slice service (timeout) with SIGTERM after 2.36 s, after
   Orca had written the complete sliced file (...): the sliced file is delivered", and
   "Orca had not written result.json, so any warnings of its own are not known" when that
   is so). With the real Orca the moment between writing the file and exiting is about
   30 ms; the real-Orca suite holds Orca there and asks a timeout and a watchdog stop.
2. A stop the slice service sent and that ended Orca: `slice.timeout`,
   `slice.out_of_memory`, or `cancelled`. A cancel (the student's, an abandoned job's, a
   shutdown's) discards even a complete file. A stop is sent only while Orca is still
   running (checked with `waitid`, without reaping Orca, before the SIGTERM, so a stop
   asked after Orca ended by itself is never sent or reported); of two, the first reason
   asked is the one reported.
3. Orca's own ending: its error report. A stop that was sent but is not what ended Orca
   is reported this way too, and named only in the detail: when the slice service sent
   only SIGTERM and Orca ended on another signal (someone else's SIGKILL, a crash: "the
   slice service had asked it to stop (timeout) and sent SIGTERM, which is not what ended
   it"), or when Orca was already ending as the stop was asked (`slicer.orca_dying`, read
   from `/proc/<pid>/status` and `stat` just before the SIGTERM: a zombie, in exit, writing
   a core file, or with a signal pending that will end it: "it was already ending when the
   slice service asked it to stop (timeout)"). So someone else's kill is
   `slice.orca_killed` (or `slice.out_of_memory` on the kernel's count) and a crash
   `slice.orca_crashed`, never `slice.timeout`. A stop the slice service escalated to
   SIGKILL is the stop.

A cancel of the student's is still applied by the job pool afterwards: see "Cancelling"
below.

**The memory model** in [plate-job.md](../contracts/plate-job.md), "Memory", estimates
Orca's peak from the parts' volume and the copies, with a factor for supports. It is
rough, so it only goes into the log line of each plate job (`estimated_peak_mb`, beside
`memory_ceiling_mb`). It is wrong both ways on plates unlike those it was fitted to: one
100 mm solid cube is estimated at 1,158 MB and slices at 269 MB (it would have been
refused); the corpus' tower stand-in scaled 6 times (120 mm, not watertight, so its
bounding box of 1,746 cm3 stands in for its volume) is estimated at 1,893 MB; and 25 hubs
of 20,000 triangles are estimated at 792 MB and peak at 842 MB, because the model ignores
triangles. Refitting it belongs with the choice of hosting, on that host's measurements.
It was fitted as the upper envelope of these measurements (`scripts/measure_plate.py
--fit` reprints it), peak resident memory of Orca from `wait4`, one slice at a time on an
aarch64 Linux machine with 4 CPUs, pinned Orca 2.4.2, the default set:

| Plate | Copies | Volume (cm3) | Supports | Peak (MB) | Estimate (MB) | Seconds | Sliced file (MB) |
|---|---|---|---|---|---|---|---|
| mechanism (2 hubs, 4 tubes, 2 gussets, a block) | 9 | 268.5 | off | 312 | 461 | 2.6 | 1.1 |
| mechanism, supports | 9 | 268.5 | on | 309 | 646 | 2.8 | 1.1 |
| full-small (25 hubs of 12,000 triangles) | 25 | 554.6 | off | 781 | 791 | 9.9 | 5.4 |
| organic-1 (a lumpy body 110 x 90 x 100 mm) | 1 | 466.1 | off | 345 | 632 | 3.0 | 3.9 |
| organic-1, supports | 1 | 466.1 | on | 381 | 885 | 3.3 | 4.2 |
| organic-2 | 2 | 932.2 | off | 591 | 1,094 | 5.4 | 6.7 |
| organic-3 | 3 | 1,398.2 | off | 825 | 1,556 | 8.1 | 9.4 |
| organic-3, supports | 3 | 1,398.2 | on | 915 | 2,179 | 10.7 | 10.1 |

The fit also takes nine plates measured on another aarch64 machine in an earlier
investigation of plate limits (1, 2, 4 and 6 Stanford bunnies of 112,402 triangles and
279.6 cm3 each, with supports off: 367, 711, 1,281 and 1,739 MB; 2, 4 and 6 with supports
on: 1,012, 1,752 and 2,569 MB; 25 hubs: 786 MB; 2 hubs of 150,000 triangles: 218 MB).
They bind the envelope: the bunny costs about 1 MB per cm3, the smooth organic body about
0.5. The time model (`limits.estimate_seconds`, for `expected_s`) has the same shape and
is within about a factor of two of every plate. The least-squares fit
(`MEMORY_BASE_MB` 73, `MEMORY_PER_COPY_MB` 11.4, `MEMORY_PER_CM3_MB` 0.79, supports 1.29)
under-estimates the bunny by up to 24%. To refit after more measurements:

```
uv run --project slice python slice/scripts/measure_plate.py --list
uv run --project slice python slice/scripts/measure_plate.py --plate organic-3 --out results.jsonl
uv run --project slice python slice/scripts/measure_plate.py --fit results.jsonl
```

The script slices under the memory watchdog with a ceiling of 3 GB (`MEASURE_STOP_MB`)
and records a plate stopped there as `over`.

## Progress, cancellation and cleanup

`jobs.JobPool` runs slices one at a time (`MAX_RUNNING`), with at most `MAX_QUEUED`
waiting; a further one is refused with `slice.busy`. Each job's latest progress report is
kept with a `sequence` that rises by one with every report; a subscriber that connects
late gets it at once. The stages, in order:

| Stage | Words | Fraction |
|---|---|---|
| `queued` | Waiting for the slicer | none |
| `building_plate` | Building the plate | none |
| `slicing` | Slicing the plate | none |
| `loading` | Loading the plate | Orca's |
| `preparing` | Preparing to slice | Orca's |
| `slicing_mesh` | Slicing the parts into layers | Orca's |
| `generating_walls` | Generating walls | Orca's |
| `generating_infill` | Generating infill | Orca's |
| `generating_supports` | Checking and generating supports | Orca's |
| `optimizing_toolpath` | Optimizing the toolpath | Orca's |
| `generating_gcode` | Generating G-code | Orca's |
| `exporting` | Writing the sliced file | Orca's |
| `reading_result` | Reading the sliced file | none |

`slicing` is the slice service's own: it is sent the moment Orca has started, before Orca
says anything, so an Orca whose pipe stays silent (one stalled while loading, or a new
release that changes `--pipe`) is not shown as still building the plate. Orca's own
messages then refine it. Checking the parts happens before a job exists, when the plate
job arrives. Every report
carries `elapsed_s` and `expected_s`, the time model's estimate from the plate's volume,
copies and supports (`limits.estimate_seconds`). The final states are `done`, `failed`
(with the error report) and `cancelled`.

**Cancelling.** A queued job is cancelled at once; a running one is reported `cancelled`
only after its Orca and every child are gone, or `failed` when it had already failed (a
watchdog stop or a timeout asked first is the one reported, and so is a crash or someone
else's kill that ended Orca before the cancel's SIGTERM could). A cancel the student asked
for before the final report wins over a slice finishing at the same instant (its sliced
file is discarded: the student asked not to have it; the `cancelled` log line names it in
`file_discarded`);
cancelling a finished job changes nothing and answers `finished`; an unknown job answers
`unknown`; cancelling twice answers `cancelling` twice and is logged once.

**Cleanup.** A job nobody follows is cancelled `ABANDON_GRACE_S` (120 s) after its last
subscriber left, or after it was submitted if none ever came; a subscriber that returns in
time keeps it. When every subscriber has gone and the grace time has passed, nobody is
waiting for the file, and the job ends `cancelled` like a student's cancel: a slice that
finishes at that instant is discarded too, and a subscriber who comes back later finds
`cancelled`. Its `cancelling` and `cancelled` log lines carry `"cancel_reason":
"abandoned"`, and the `cancelled` line `file_discarded` when a finished sliced file was
thrown away. Scratch folders are removed on every way out (success, failure, timeout,
cancel); at start the HTTP face removes the scratch of any process that is no longer
running (`service.clean_stale_scratch`: the folder name carries the process id and its
start time, so a reused process id is not mistaken for the living one). A running job's
record never expires; a final one goes an hour after its final report, with its files.
Shutdown (`JobPool.shutdown`, the end of `serve`) cancels every job and waits for every
worker.

**The log.** One JSON line per job transition (`queued`, `running`, `cancelling`, `done`,
`failed`, `cancelled`, `expired`), `{"event": "slice_job", ...}`, carrying the job id, the
printer, filament, process, overrides and whether supports are on, the memory and time
estimates, every part with its triangles, size, volume, watertightness, shells, open edges
and warnings, every copy with its name, orientation, angle and position, and on a final
state the error code, the error report's detail, Orca's reason, Orca's peak memory (and
`memory_note` when a delivered slice's peak passed the ceiling, `stop_note` when a stop
reached Orca after its sliced file was complete, `cancel_reason`, and `file_discarded`
when a cancel threw away a finished sliced file), Orca's wall time and the job's wall
time. The log sink is called through `jobs.SafeLog`, the one place a failing sink (a
closed or broken stderr under `serve`) is caught: the failure is counted
(`JobPool.log_failures()`; the HTTP face has no health answer to show it in) and never
changes what a job or an answer does. A plate job that is never queued leaves one line too, with `"state":
"refused"`: every answer of `POST /slices` that is not 202 (a part a check refused, a
plate job that is not JSON or has no `plate_job` field, an upload too large, a full queue,
a full disk while an upload is saved, a work folder that cannot be written, a bug)
carries `http_status`, `error_code`, `error_detail`, `parts` (each part's key, name and
`stl`, as the plate job named them, when it could be read) and `uploads` (each uploaded
file's field name and size in bytes, when the body could be read). No payload, path of
the caller or environment variable is logged.

## Modules

| Module | What it holds |
|---|---|
| `service.py` | The entry point: reading and checking a plate job, slicing it, the sliced file, scratch folders |
| `errors.py` | The adapter from every exception to an error report, and every code |
| `plate.py` | Orientations, copy placement and the rules a placement must pass |
| `mesh.py` | Reading a binary STL, the checks on its surface, the warnings, and a part's footprints |
| `plate_3mf.py` | The plate written as a 3MF for Orca, the sliced file's name, the name guard |
| `plate_job.py` | One plate job, its description for the log, and running its slice |
| `print_config.py` | The profile catalog, the profile choice, the overrides and whether supports are on |
| `slicer.py` | Everything that runs Orca or reads what it writes |
| `jobs.py` | The job queue: progress reports, cancellation, abandonment, expiry, the log |
| `web.py` | The HTTP face |
| `limits.py` | Every cap, the memory and time models, and the sentences that refuse them |

## Error codes

Every code the slice service produces, in the order of the checks. `tests/test_errors.py`
produces each one on purpose, through the code that really raises it, and states the
sentence, remedy, action, retryable flag and evidence its report must carry.

| Code | Stage | When |
|---|---|---|
| `slice.bad_plate_job` | checking | The plate job is not JSON (or nested too deeply to read), has a field that is not listed, or a part or copy lacks a field or has a bad value (an `stl` with a NUL character, over 1,024 characters, or a piece over 255 bytes; a part `name` over 200 characters; a `printer`, `filament` or `process` name over 200 characters). No sentence, detail or log line grows with what a caller sends: a value it shows is cut to 120 characters, and a bug's own words to 2,000. |
| `slice.too_many_copies` | checking | More than `MAX_COPIES` copies. |
| `slice.unknown_printer` | checking | The printer is not in the catalog. |
| `slice.profiles_not_offered` | checking | The filament or process is not in the catalog, does not fit the printer, or is not the default set's. |
| `slice.bad_overrides` | checking | An override is not one of the four, or its value is not listed. |
| `slice.profile_unreadable` | checking | A profile file of the server's own (the catalog, a printer or process profile) is missing or not a profile. |
| `slice.part_missing` | checking | A copy names a part the plate job does not list, or the part's STL file is missing (also when it goes away after the checks), or lies outside the files sent with the plate job. |
| `slice.part_unreadable` | checking | A part's file cannot be opened, is empty, is not an STL (an image, a zip or 3MF, a gzip, text such as an HTML or JSON error page), is cut off or padded, has no triangles, or has coordinates that are not finite. |
| `slice.part_not_binary` | checking | A part's file is an ASCII STL. |
| `slice.part_too_detailed` | checking | A part's STL is over `MAX_PART_BYTES` or `MAX_PART_TRIANGLES`. |
| `slice.part_too_small` | checking | A part is 0.1 mm or less in every direction, or flat in one. |
| `slice.part_no_volume` | checking | A part's triangles have no area, or none shares an edge with another, or its closed surface lies in one plane or encloses no volume (faces laid on top of each other). |
| `slice.part_too_large` | checking | A part fits the printer in no orientation. |
| `slice.placement_off_plate` | checking | A footprint leaves the printable area less the margin. |
| `slice.placement_too_tall` | checking | A copy is taller than the printable height. |
| `slice.placement_too_close` | checking | Two footprints are closer than `SPACING_MM`. |
| `slice.busy` | queued | The job queue is full. |
| `slice.scratch_unwritable` | building | The plate 3MF, the process file or Orca's folders cannot be written (a full disk), or the HTTP face cannot make a job's folder in its work folder (HTTP 500). |
| `slice.orca_missing` | slicing | No Orca at `PENGUIN_SLICE_ORCA` or `tools/orca`. |
| `slice.orca_unstartable` | slicing | Orca is there but will not start (not executable, another architecture), or exits 126 or 127 with no `result.json` (the loader could not load a library it needs). |
| `slice.timeout` | slicing | Orca took longer than `PLATE_SLICE_TIMEOUT_S`; the service stopped it, and the stop is what ended Orca, before its sliced file was complete. |
| `slice.cancelled` | slicing | The slice was cancelled (by a client, as abandoned, or at shutdown) and Orca is gone. |
| `slice.out_of_memory` | slicing | The memory watchdog stopped Orca at the memory ceiling before its sliced file was complete (the detail holds the measured peak); or Orca was killed and the cgroup's `oom_kill` count rose (the kernel's out-of-memory killer); or Orca printed `bad_alloc`. On a plate of one copy the remedy is to split or simplify the part, with no action. |
| `slice.orca_crashed` | slicing | Orca died on a signal that means it failed (SIGSEGV, SIGABRT, SIGBUS, SIGFPE, SIGILL, SIGTRAP, SIGSYS), also when a stop of the service's was asked at the same moment (the detail says so). |
| `slice.orca_killed` | slicing | Something else stopped Orca with a signal the service did not send (SIGKILL with the `oom_kill` count unchanged or unreadable, SIGTERM, SIGINT and the rest), also when a stop of the service's was asked at the same moment or Orca ignored the service's SIGTERM (the detail says so). |
| `slice.orca_too_close` | slicing | Orca's return code -101. |
| `slice.crosses_edge` | slicing | Orca's return code -52: a copy partly off the plate beside others on it. |
| `slice.empty_layers` | slicing | Orca refused empty layers with supports off: the report names the copy and the height, and offers `enable_supports`. |
| `slice.empty_layers_with_supports` | slicing | The same with supports on: the part must be repaired, no action. |
| `slice.no_layers` | slicing | Orca printed "No layers were detected." (an open or broken surface, a part too thin): repair in CAD. Names the part when the plate has one. |
| `slice.print_empty` | slicing | Orca printed "The print is empty." (a part thinner than the nozzle prints): check size and thickness. Names the part when the plate has one. |
| `slice.nothing_on_plate` | slicing | Orca's return code -50: no copy fully on the plate. |
| `slice.orca_failed` | slicing | Any other non-zero exit, -100 without a reason the service recognises, or a code it does not know; Orca's words are in the detail. |
| `slice.no_output` | slicing | Orca exited 0 without writing the sliced file. |
| `slice.unreadable_output` | slicing | The sliced file is not a zip, an entry fails its checksum, a plate's sliced file has no `Metadata/plate_1.json`, or that entry has no list of objects. |
| `slice.no_gcode` | slicing | The sliced file has no `Metadata/plate_1.gcode`. |
| `slice.left_off_plate` | slicing | Orca left a copy out of the sliced file. |
| `slice.output_unwritable` | saving | The output folder cannot be made or written, or a folder already has the sliced file's name. |
| `slice.unknown_job` | fetching | The HTTP face does not know the job (never, or expired). |
| `slice.not_ready` | fetching | The sliced file of a job that has not finished. |
| `slice.file_gone` | fetching | The sliced file of a done job is no longer on the disk (HTTP 410). |
| `slice.bad_request` | fetching | The HTTP face does not offer that path (404) or that method on it (405). |
| `slice.unexpected` | slicing | Anything else: a bug in the slice service; the detail keeps the traceback. |

For a failure Orca reports, the detail holds Orca's code, the exit status, Orca's own
reasons (`error_string` and every `warning_message` from its `result.json`) and the last
lines Orca printed. For a signal it holds the signal and who sent it, and a stop of the
service's that was asked but did not end Orca.

## Taking a new upstream version

The slice service rests on Orca Slicer (the program and its profiles). To move to another
release:

```
make -C slice upgrade-orca VERSION=2.5.1
```

It reads the release from GitHub, takes GitHub's SHA-256 digest of each of the three
assets, and stops if `patches/orca/` holds a patch: patching Orca needs a source build,
which the command does not do ([patches/orca/README.md](patches/orca/README.md)); this
deviates from applying patches, for the owner to accept. It then installs the release
beside the installed one, in `tools/orca.next` (a staged copy of `scripts/install-orca.sh`
holding the new pin verifies the download), so a failed download or checksum changes
nothing. Only then does it rewrite the pin in `scripts/install-orca.sh`, move
`tools/orca` to `tools/orca.previous` and the new release into `tools/orca`, regenerate
`profiles/` and `profiles/catalog/` from the new Orca's own profiles, and run the upstream
check, `make test-upstream` (`tests_orca/`: every test's docstring starts with
"Protects:" and names the behaviour it pins). When the check passes,
`tools/orca.previous` is removed. Nothing is committed.

Then look at:

- `git diff -- slice/src/penguin_slice/profiles/`: values that changed in the default set
  (temperatures, speeds, `nozzle_volume`), profiles that appeared or went from the
  catalog, and `index.json`'s `skipped` list. A changed default set changes every slice.
- The upstream check's output. A failing test names the assumption that broke: a command
  line option, a return code or the wording `slicer.py` reads (`ORCA_RETURN_CODES`,
  `EMPTY_LAYER_RE`, `OBJECT_RE`, `OUT_OF_MEMORY_RE`), a progress message `ORCA_STAGES`
  does not know, the sliced file's metadata, the placement, or the catalog.

When a test fails, fix `slicer.py` (or the flattening script for the catalog) and its
fast-suite stand-in `tests/fake_orca.py` together, and record what changed in the test.
When the fix cannot be made from outside Orca, write a patch note in
[patches/orca/README.md](patches/orca/README.md) for the owner to decide.

**Going back.** When the regeneration or the upstream check fails, the new release is
installed and pinned and the old one is still in `tools/orca.previous`; the message names
both. Run the command again with the old version (`make -C slice upgrade-orca
VERSION=2.4.2`): it downloads, verifies and installs the old release the same way and
regenerates the profiles from it (`PENGUIN_SLICE_ORCA_CACHE` keeps each verified download,
so going back is quick). `git diff -- slice/` then shows nothing but what you meant to
keep.

**What happened when the command was run to other versions and back** (on an aarch64
Linux machine, with 2.4.2 pinned):

- **Up to 2.5.1** (released Sat 2026-11-14), `make -C slice upgrade-orca VERSION=2.5.1`:
  GitHub's digests read, the release downloaded, verified and installed, the pin moved.
  The regeneration of the profiles then stopped with "machine profile 'Bambu Lab H2S 0.6
  nozzle' not found": 2.5.1 ships the Bambu Lab vendor profiles packed in one opaque file,
  `BBL.opc` (not a zip), and leaves only `filament/` and `cli_config.json` loose, so
  `scripts/flatten_orca_profiles.py` finds no printer to flatten. Taking 2.5.x needs the
  flattening script to read that format (or Orca's own export of it).
- **Down to 2.4.1**, `make -C slice upgrade-orca VERSION=2.4.1`: downloaded, verified,
  installed into `tools/orca.next`, the pin moved, `tools/orca` swapped, the profiles
  regenerated (only `catalog/index.json` changed: its `skipped` list is empty for
  2.4.1). The upstream check ran: 26 passed, 1 failed,
  `test_checked_in_profiles_and_catalog_match_the_installed_orca`, on that empty
  `skipped` list, and the command stopped with "upstream check failed (exit 2). Orca
  2.4.1 is installed and pinned; 2.4.2 is kept at .../tools/orca.previous. To go back:
  make upgrade-orca VERSION=2.4.2". That is the check doing its job: the test that
  assumes the catalog skips some profiles names the assumption that changed.
- **Back to 2.4.2** after each, `make -C slice upgrade-orca VERSION=2.4.2`: installed,
  regenerated and the upstream check passed (the return from 2.4.1 took 50 s). The
  pin's lines in `scripts/install-orca.sh` were byte for byte what they were, `git diff`
  showed no change under `src/penguin_slice/profiles/`, `tools/` held only `orca`
  (2.4.2), and no staged script was left in `scripts/`. Coming back restored the pin with
  no changes.

## Tests

| Target | What it runs |
|---|---|
| `make test` | The fast suite, in random order: no Orca, no network, no waiting, each test in its own temporary folder. |
| `make test-parallel` | The fast suite on `WORKERS` worker processes (default 2). |
| `make test-flakes` | The fast suite `RUNS` times (default 10) on `WORKERS` workers, each run with a new random seed, which it prints first. |
| `make coverage` | Branch coverage of the package under the fast suite; fails under 100%. |
| `make test-upstream` | The upstream check: the tests that run the real Orca (`tests_orca/`), one at a time, with each test's time. `make test-orca` is the same. |

In the fast suite `PENGUIN_SLICE_ORCA` always points at a placeholder that cannot run, so
no test can start the real Orca by accident, and no real timer runs (`slicer.TIMER` is
replaced; a test fires a timeout itself). Tests that need Orca's behaviour use
`tests/fake_orca.py` through `helpers.install_fake_orca`, a real child process with a mode
for each way Orca misbehaves (killed, crashing, hanging, ignoring SIGTERM, leaving a child,
flooding its output, writing a damaged file, waiting after writing its sliced file whole,
half, or under its temporary name); the upstream check pins the fake's progress
lines to the real ones. `tests/fixtures/bad_stls/` is the corpus of bad part files, written
by `tests/fixtures/make_bad_stls.py` (the suite checks the two agree); Hypothesis throws
random and damaged files at the reader, derandomized so every run sees the same examples.
To rerun one random order, pass the seed: `--randomly-seed=<seed>`.

No test can hang. Every wait on a process, a thread or an event gives up after
`helpers.FAILSAFE_S` (10 s) with a message naming what never happened, and a test that
runs a stand-in only a stop can end runs it through `helpers.bounded` and kills it
(`helpers.kill_fake`) if it is still there. Behind that, `conftest.no_test_can_hang` fails
any test still running after 20 s (a SIGALRM in the test's process, whose exception
`slicer.run_process`'s cleanup survives, killing the stand-in's group), and the stand-in
and any child it starts end themselves after 25 s (`fake_orca.LIMIT_S`). With the
watchdog's stop removed from a scratch copy, the suite fails 7 tests in 54 s on 2 workers
and leaves no process; with the ceiling setting ignored, 5 tests in 13 s.
