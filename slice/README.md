# Slice service

Takes a [plate job](../contracts/plate-job.md) (the parts as STL files, where each copy
sits on the plate and how it is turned, the printer, filament and process profiles with
setting overrides), runs Orca Slicer headless, and returns a
[sliced file](../contracts/sliced-file.md) (`.gcode.3mf`) with its summary. Every failure
becomes an [error report](../contracts/error-report.md). It knows nothing of Onshape,
teams, web sessions or printers.

This is a port of the print path of an earlier application. Its behaviour is kept as it
was, except where the port's review found a failure reported as the wrong thing or
sentences that named the earlier application (Onshape, teams); the faults still kept are
pinned by tests marked `known_fault` (see Tests) for a later hardening pass.

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

The library has one entry point:

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
folder whether the slice succeeds or fails. The move is a rename inside the output folder:
it replaces a file of the same name, and a folder of that name fails the slice with
`slice.output_unwritable`, so `sliced.path` is always the sliced file. It blocks until
Orca is done. There is no HTTP server and no progress report yet; `jobs.py` holds the job
queue a server will use.

## Orca Slicer

The slice service runs the Orca wrapper named by the environment variable
`PENGUIN_SLICE_ORCA`, or else `slice/tools/orca/orca-slicer`. It looks when a slice starts,
so the fast suite runs without Orca. `scripts/install-orca.sh` installs the pinned release
there. Its `ORCA_VERSION` line, with the three checksums below it, is the only place the
Orca version is stated; the tests read it from there. Idempotent, the script exits at once
when `tools/orca/VERSION` already records this version for this platform. Linux x86_64,
Linux aarch64 and macOS arm64 only.

`slicer.py` is the one module that runs Orca and reads what Orca writes: the command
lines, the environment, Orca's return codes (`ORCA_RETURN_CODES`, the only table of them),
`result.json`, and the sliced file's entries. A change in a new Orca is absorbed there.

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

Orca runs with an allowlisted environment (`PATH`, `HOME`, `TMPDIR`, `LANG`, `USER`,
`LOGNAME`) plus private `XDG_CONFIG_HOME`, `XDG_RUNTIME_DIR` and `--datadir` folders in the
slice's own scratch folder, so secrets never reach it and two slices never share state.
A plate is sliced with `--arrange 0 --orient 0`: Orca keeps every copy where the plate job
put it.

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
and the desktop app exports only differences, so regenerate both after an Orca upgrade:

```
uv run --project slice python slice/scripts/flatten_orca_profiles.py
uv run --project slice python slice/scripts/flatten_orca_profiles.py --audit-only   # resolved values and their sources
```

`make test-orca` fails when the checked-in files differ from what the script produces.

## Sample part

`src/penguin_slice/sample_part.stl`, an L bracket 40 x 30 x 12 mm (binary STL, 20
triangles), written by `scripts/make_sample_part.py`; the fast suite checks that the two
agree byte for byte. `slicer.slice_stl` slices it alone with the default set and
`--arrange 1`, as the earlier application's upload mode did.

## Modules

| Module | What it holds |
|---|---|
| `service.py` | The entry point: reading and checking a plate job, slicing it, the sliced file |
| `errors.py` | The adapter from every exception to an error report, and every code |
| `plate.py` | Orientations, copy placement and the rules a placement must pass |
| `mesh.py` | Reading a binary STL, and a part's footprint in each orientation |
| `plate_3mf.py` | The plate written as a 3MF for Orca, the sliced file's name, the name guard |
| `plate_job.py` | One plate job and running its slice |
| `print_config.py` | The profile catalog, the profile choice and the overrides |
| `slicer.py` | Everything that runs Orca or reads what it writes: its command line, its environment, its return codes, `result.json`, the summary and the sliced objects' names |
| `jobs.py` | The in-process job queue (not used by the command line) |
| `limits.py` | Every cap and the sentence that refuses it |

## Error codes

Every code the slice service produces, in the order of the checks. `tests/test_errors.py`
produces each one on purpose, through the code that really raises it, and states the
sentence, remedy, action, retryable flag and evidence its report must carry.

| Code | Stage | When |
|---|---|---|
| `slice.bad_plate_job` | checking | The plate job is not JSON, or a part or copy lacks a field or has a bad value (a number no float can hold included). |
| `slice.too_many_copies` | checking | More than `MAX_COPIES` copies. |
| `slice.part_missing` | checking | A copy names a part the plate job does not list, or the part's STL file is missing, also when it goes away after the checks. |
| `slice.part_unreadable` | checking | A part's STL cannot be opened, is not binary, is truncated, or has coordinates that are not finite. |
| `slice.part_too_detailed` | checking | A part's STL is over `MAX_PART_BYTES` or `MAX_PART_TRIANGLES`. |
| `slice.part_too_small` | checking | A part is 0.1 mm or less in some direction. |
| `slice.job_too_detailed` | checking | The copies hold more than `MAX_JOB_TRIANGLES` triangles. |
| `slice.unknown_printer` | checking | The printer is not in the catalog. |
| `slice.profiles_not_offered` | checking | The filament or process is not in the catalog, does not fit the printer, or is not the default set's. |
| `slice.bad_overrides` | checking | An override is not one of the four, or its value is not listed. |
| `slice.placement_off_plate` | checking | A footprint leaves the printable area less the margin. |
| `slice.placement_too_tall` | checking | A copy is taller than the printable height. |
| `slice.placement_too_close` | checking | Two footprints are closer than `SPACING_MM`. |
| `slice.busy` | queued | The job queue is full. |
| `slice.orca_missing` | slicing | No Orca at `PENGUIN_SLICE_ORCA` or `tools/orca`. |
| `slice.orca_unstartable` | slicing | Orca is there but will not start. |
| `slice.timeout` | slicing | Orca took longer than `PLATE_SLICE_TIMEOUT_S`. |
| `slice.orca_killed` | slicing | The operating system stopped Orca with a signal (for example the out-of-memory killer). |
| `slice.orca_too_close` | slicing | Orca's return code -101. |
| `slice.crosses_edge` | slicing | Orca's return code -52. |
| `slice.empty_layers` | slicing | Orca's return code -100, its general slicing failure (see below). |
| `slice.nothing_on_plate` | slicing | Orca's return code -50. |
| `slice.orca_failed` | slicing | Any other non-zero exit. |
| `slice.no_output` | slicing | Orca exited 0 without writing the sliced file. |
| `slice.unreadable_output` | slicing | The sliced file is not a zip, an entry the slice service reads is damaged, or `Metadata/plate_1.json` has no list of objects. |
| `slice.no_gcode` | slicing | The sliced file has no `Metadata/plate_1.gcode`. |
| `slice.left_off_plate` | slicing | Orca left a copy out of the sliced file. |
| `slice.output_unwritable` | saving | The output folder cannot be made or written, or a folder already has the sliced file's name. |
| `slice.unexpected` | slicing | Anything else: a bug in the slice service. |

For a failure Orca reports, the detail holds Orca's code, the exit status, Orca's own
reason (`error_string` from its `result.json`, read before the scratch folder is removed)
and the last lines Orca printed.

Known fault, kept for hardening: Orca's -100 is its general "Failed slicing the model"
failure, not only an empty layer, but its report says "A part has no flat face on the
plate; choose another Lay flat." whatever the cause. The real Orca gives -100 for a part
with a gap between two layers, which has a flat face on the plate. The remedy and the
absence of an action are honest for any cause; the sentence is pinned by tests marked
`known_fault`.

## Tests

| Target | What it runs |
|---|---|
| `make test` | The fast suite, in random order: no Orca, no network, no waiting, each test in its own temporary folder. |
| `make test-parallel` | The fast suite on `WORKERS` worker processes (default 2). |
| `make test-flakes` | The fast suite `RUNS` times (default 10) on `WORKERS` workers, each run with a new random seed, which it prints first. |
| `make coverage` | Branch coverage of the package under the fast suite. |
| `make test-orca` | The tests that run the real Orca (`tests_orca/`), one at a time, with each test's time. |

In the fast suite `PENGUIN_SLICE_ORCA` always points at a placeholder that cannot run, so
no test can start the real Orca by accident. Tests that need Orca's behaviour use
`tests/fake_orca.py`, which writes the files the pinned Orca writes, in the shape the slice
service reads. To rerun one random order, pass the seed: `--randomly-seed=<seed>`.

A test marked `known_fault` pins a known fault's current wrong behaviour. It passes today;
the hardening pass that fixes the fault flips its assertion.

Measurements of time and memory at the limits are recorded in `jobs.py`;
`scripts/measure_plate.py` repeats them.
