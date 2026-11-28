# The two opening trials of phase 2

The two risks the wizard's guide names to try first
([The risks to try first in phase 2](../README.md#the-risks-to-try-first-in-phase-2)), run
as [How the trials and measurements are run](../README-details.md#how-the-trials-and-measurements-are-run)
says. Each trial lives in a folder of its own and is run by an entry point of its own, so
that the two can be built at the same time without touching the same file.

| Folder or file | What it holds | Run by |
|---|---|---|
| `preview/` | The layer preview's speed without a graphics card: the candidate methods' pages, the measuring script `preview/run.py`, `results/` and `report.html` | `make -C wizard trials-preview` |
| `geometry/` | Laying on a face, auto-orient and Arrange on real exported parts: the measuring script `geometry/run.py`, `results/` and `pictures/` | `make -C wizard trials-geometry` |
| `parts/` | The made parts, `hub-150k.stl` (a closed hub of exactly 150,000 triangles) and `hex-spacer.stl` (the slice service's reference spacer, 216 triangles), committed | `make -C wizard trials-parts` writes them again; the fast suite checks they are unchanged |
| `make_parts.py` | Writes `parts/`, deterministically | |
| `serve.py` | Serves this folder at `/`, `wizard/vendor/` at `/vendor/` and the real parts of `contracts/examples/parts/real/` at `/parts/real/`; nothing else | `make -C wizard trials-serve` (on `127.0.0.1:8610`; `HOST=0.0.0.0` to reach it from another machine) |
| `sliced/` | The preview trial's sliced files, made again by its script; not committed | `make_sliced_files.py`, with a slice service started by hand ([preview/README.md](preview/README.md)) |
| `plates/` | The preview trial's three plates, as plate configurations | `make_sliced_files.py --write-plates` writes them again; the fast suite checks they are unchanged |
| `make_sliced_files.py` | Has a slice service slice each plate of `plates/` and saves the sliced files into `sliced/` | |

`make -C wizard trials` runs both trials, the preview first. The preview trial is built
([preview/README.md](preview/README.md)); until a trial's builder replaces its `run.py`,
that entry point is a placeholder that says so and fails.

A trial's page loads three.js through an import map that names
`/vendor/three/build/three.module.min.js` for `three`, and a part as
`/parts/real/<file>.stl` or `/parts/<file>.stl`. A trial's measuring script starts the
server itself with `serve.make_server("127.0.0.1", 0)`, on a port the system chooses, and
drives Chromium with Playwright from the project's environment. Each trial says what it
found in its own folder (its results, and a `README.md` of its own if it needs one), not
in this file.
