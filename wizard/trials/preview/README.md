# The layer preview's speed without a graphics card

The first trial of phase 2, run as
[How the trials and measurements are run](../../README-details.md#how-the-trials-and-measurements-are-run)
says: whether any way of drawing the layer preview reaches 10 frames a second, with the
required look, on a machine where the browser draws 3D in software. The result, the method
the Preview step is built on and every figure are in
[the trial's record](../../../docs/orchestration/phase-2/records/wizard-1a-trial-preview.md)
and in [report.html](report.html), which shows the figures and the renders side by side.

## What is here

| File | What it is |
|---|---|
| `a-every.html`, `b-moving.html`, `c-progressive.html` | The three candidate methods, a page each, on the shared viewer |
| `viewer.js` | What every method shares: the view, the plate, the ghost, the layer bar, the camera, and the measuring (`window.trial`) |
| `methods.js` | How each method draws; `methods-prepare.js`, what each prepares in the worker |
| `gcode.js` | Reading the sliced file: the archive's `Metadata/plate_1.gcode` into straight segments with their layer, line type, width and height |
| `prepare.js` | The boxes' vertices, the layers dropped while moving, the order the full look is drawn in, the ghost of each instance, and the hiding of what air cannot reach (measured, not used: see the record) |
| `worker.js` | The worker that fetches, reads and prepares, so the page's main thread only uploads |
| `run.py` | The measuring script (`make -C wizard trials-preview`) |
| `bench.html` | What software drawing costs for each kind of primitive, apart from any method |
| `results/` | One JSON file for each method and plate, `chosen.json`, and the renders, `results/<method>/<plate>/<view>.png` |
| `report.html` | The figures and renders side by side, written by `run.py` |

## The three methods

All three draw each segment of the sliced file as a box as wide as its line and as tall as
its layer, of which the top and the long side towards the camera are drawn, so that stacked
layers close into surfaces: that is how the look has no combs and no show-through. They
differ in what they draw while the view is turned or the layer bar dragged, and in how the
full look is spread over frames.

- **A** draws every box in every frame.
- **B** draws, while moving, every D-th layer with coarser arcs, each box as tall as the D
  layers it stands for, plus the layers between the last of them and the current layer, and
  the current layer; D is the smallest of 1, 2, 4, 8 and 16 that keeps it within 200,000
  boxes. At rest it draws every box in one frame.
- **C** draws as B while moving; at rest it draws the full look into an image off the screen
  150,000 boxes a frame, each piece only after the graphics side has finished the one
  before, and copies it to the screen when it is whole.

## Running it

The three sliced files are not committed (`../sliced/`). Making them needs the slice service
with the real Orca, which takes 1 to 2 GB for a slice and, for `blocks-12-supports`, a memory
ceiling of 3,000 MB and at least 4 GB free. On the agents' machine every run of the real Orca
holds the shared lock, so the slice service runs under it, and is stopped (Ctrl-C) as soon
as the script has saved the three files. The plate configurations are in `../plates/`
(`make_sliced_files.py --write-plates` writes them again).

```
make -C slice install
PENGUIN_SLICE_MAX_PEAK_MB=3000 flock /var/tmp/penguin-locks/real-orca.lock \
  slice/.venv/bin/python -m penguin_slice serve --work /var/tmp/<a folder of its own> --port <a free port>
wizard/.venv/bin/python wizard/trials/make_sliced_files.py --url http://127.0.0.1:<that port>   # in another shell
```

Then:

```
make -C wizard trials-preview          # every method on every plate: about 20 minutes
wizard/.venv/bin/python wizard/trials/preview/run.py --methods C --plates spacers-150 --steps 20
```

`run.py` exits 1 when no method reaches the builder's part of passing on all three plates,
after writing every figure, render and the report.

For the owner's timing on the Mac: `make -C wizard trials-serve`, then open
`http://127.0.0.1:8610/preview/c-progressive.html?plate=blocks-12-supports` in Chrome; the
page's `window.trial.turn(60)` and `window.trial.dragLayers(60)`, run in the console, give
the same figures as here. The sliced files must be in `wizard/trials/sliced/` on that machine.
