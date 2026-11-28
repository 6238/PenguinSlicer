# The second trial: laying on a face, auto-orient and Arrange on real exported parts

The second opening trial of phase 2
([The risks to try first in phase 2](../../README.md#the-risks-to-try-first-in-phase-2)),
run as [How the trials and measurements are run](../../README-details.md#how-the-trials-and-measurements-are-run)
says, on the wizard's own geometry
([The geometry, in a worker](../../README-details.md#the-geometry-in-a-worker)).

`make -C wizard trials-geometry` runs [run.py](run.py), which drives [index.html](index.html)
and [trial.js](trial.js) in Playwright's Chromium against the wizard's own worker and writes:

| Folder or file | What it holds |
|---|---|
| `results/<part>.json` | For each part: its faces and patches, the way auto-orient lays it, its flat faces and whether each has a hull patch, and the times of five runs |
| `results/arrange-spacers-150.json`, `results/arrange-mix-150.json` | Arrange of 150 instances, both packers' results, and the placement check of a drag across the plate |
| `results/summary.json` | The machine, the four times against their targets, the flat faces without a hull patch, the main thread during the timed steps |
| `pictures/<part>.png` | Each part as modelled (from above, and from below and behind) and as auto-orient lays it (from two sides), its patches drawn: hull patches solid blue, bounding-box patches paler with a dashed edge, the patch it is laid on edged in red |
| `pictures/arrange-*.png` | Each arranged plate from above, with the 3 mm margin |

The pictures are drawn by [render.js](render.js) on a 2D canvas, painting triangles far to
near, so that they need no graphics card.

## What was found

Run on Fri 2026-11-27 (Pacific time) on an aarch64 Linux machine without a graphics card, 8 processors and
12 GiB of memory as its cgroup gives them, in Chromium 159 headless.

| Time | Target | Worst of five runs |
|---|---|---|
| Patches of `hub-150k.stl` after selecting it | 100 ms | 4.1 ms (its faces found when it arrived) |
| Auto-orient of `hub-150k.stl` after it arrives | 1,000 ms | 272 ms, from reading the file to its best way |
| Arrange of 150 `hex-spacer.stl` | 2,000 ms | 30 ms; all 150 placed |
| Arrange of a mix of 150 real parts | 2,000 ms | 56 ms; 104 placed, 46 beside the plate |
| Each placement check of a drag at 150 instances | 100 ms | 2.2 ms (spacers), 4.4 ms (the mix) |

Found from nothing, the faces take at most 215 ms for `hub-150k.stl` and at most 84 ms for a
real part. While each step was timed the main thread never went more than 15 ms between beats
of a 10 ms heartbeat. Chromium's long-task timing reported tasks of 0.1 to 0.9 s that
neither the heartbeat nor any answer's time shows, and on a different part from one run to
the next (on `hub-150k.stl` in one run, on Elevator Block Bottom Inner in another, with
none on the hub); the heartbeat is the figure counted.

The drag at 150 instances of the mix checks all 150, the 46 that Arrange left beside the
plate among them: the check is timed on the whole plate configuration, as a drag would
check it.

Every flat face of each real part (a hull face of at least 25 mm², at least half of it the
part's own surface) has a hull patch. That took three changes to the rules as first written,
each found on these parts and each with a test: thin strips of the hull a tenth of a degree
off a flat face are part of it; a round side is judged across all the faces it reaches by
shallow bends; and a flat face of the part's own surface is not dropped beside a hull face
that only bridges a step (Elevator Top Inner lost its four flat sides to that).

The round parts exported from Onshape at its coarse and fine settings can only come from the
owner; until they arrive the round parts are `pulley-v3.stl` and `inner-spacer.stl`, and the
Inner Spacer turns out to be a thin square plate with rounded corners, so the pulley is the
one real round side tried.

## Each part, as a person would see it

| Part | Patches | Laid | Would a person choose it? |
|---|---|---|---|
| Clamp Plate Inner | 6 hull: both faces and the four edges | On its plain back, slots up, 4.8 mm tall, no overhang | Yes |
| Elevator Block Bottom Inner | 12 hull, 9 of them on hull faces that bridge its pockets and touch it only along edges | Upside down on its top face, 82.6 mm tall, 3,685 mm² hanging over air | Not sure. The one other counted way is as modelled (more overhang); its large flat back is judged to tip over. A person might well print it as modelled or on its back. The bridging patches are Orca's too, but a person would not pick them |
| Elevator Block Carriage | 9 hull, 4 bridging | On its flat back, 31.8 mm tall | Probably: the lowest way, on its largest flat face |
| Elevator Block Top | 9 hull, 4 bridging | On its flat back, 31.8 mm tall | Probably, for the same reason |
| Elevator Top Inner | 6 hull: top, bottom and the four flat sides of its upper block | Upside down on its wider top, 57.2 mm tall | Yes: the wider block down, no lip hanging over air |
| Inner Spacer | 6 hull | Flat, 1.3 mm tall | Yes |
| Outer Clamp | 6 hull | On its plain face, slots up, 4.8 mm tall | Yes |
| Pulley v3 | 2 hull (its ends), 4 bounding-box (its rim) | On one end, 17.8 mm tall | Yes |
| Hub 150k (made) | 2 hull, 4 bounding-box | As modelled, 20 mm tall | Yes |
| Hex Spacer (made) | 2 hull, 4 bounding-box | As modelled, flat | Yes |

The arranged plates (`pictures/arrange-*.png`) pass the placement check; the instances are
packed unevenly, with gaps of up to a few millimetres more than the spacing where the shelf
packer's grid and the map's squares leave them.
