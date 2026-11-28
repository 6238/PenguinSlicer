# Batch wizard-1a-trial-preview: the layer preview's speed without a graphics card

The first trial of phase 2, run as
[How the trials and measurements are run](../../../../wizard/README-details.md#how-the-trials-and-measurements-are-run)
says, for the risk named in
[The risks to try first in phase 2](../../../../wizard/README.md#the-risks-to-try-first-in-phase-2).
Built and measured on Fri 2026-11-27 (Pacific time), on branch
`phase-2/wizard-1a-trial-preview`. The trial's own guide is
[wizard/trials/preview/README.md](../../../../wizard/trials/preview/README.md); the figures and
renders side by side are in [report.html](../../../../wizard/trials/preview/report.html).

## The answer

**The Preview step is to be built on method C.** It is the only one of the three that reaches
the builder's part of passing on all three plates: 10 frames a second typical (15 to 20
measured) while turning the view and dragging the layer bar, no hold of the main thread over
250 ms (116 to 159 ms), and the coarse checks of the look. Method C draws every line of the
sliced file as a box as wide as the line and as tall as its layer, of which the top and the
long side towards the camera are drawn, so that stacked layers close into surfaces with no
combs and no show-through. While the view moves (turning, or the layer bar dragged) it draws
every D-th layer of a coarser reading of the file, each box D layers tall (D = 4 or 8 on these
plates), and no ghost. At rest it draws the full look into an image off the screen 100,000
boxes a frame, each piece only once a fence shows the one before is drawn, and copies it to
the screen when whole, about 0.35 to 1.2 s after the view stops. Uploads to the graphics side
go 8 MB a frame behind the same kind of fence.

On the shared machine the heaviest plate has little margin: of three runs of C on
`blocks-12-supports` after its last change, two passed and one missed (below, "Targets
missed").

### The machine

The agents' container: aarch64 Linux, **8 processors and 12 GB of memory as its cgroup gives
them** (`cpu.max` 800000 100000, `memory.max` 12,884,901,888 bytes), shared with three other
builders while the figures were taken (load average 3 to 7.5 at the start of each
measurement; recorded in each JSON file). Chromium 159.0.8154.6, headless, from
`make -C wizard install`, drawing WebGL 2 in software: ANGLE on Vulkan 1.3.0 over SwiftShader
(LLVM 10.0.0). The view is 640 by 480 pixels at a pixel ratio of 1.

### The figures

Frames a second are typical / worst over a 60-frame path; the hold is the longest the main
thread was held while loading, moving or coming to rest; "first / full" is seconds from the
page starting to fetch the sliced file to the first frame on the screen and to the full look;
"rest" is milliseconds from the end of the turn until the full look is on the screen; memory
is the peak resident memory of the page's renderer and graphics processes together.

| Method, plate | Turning | Layer bar | Hold (ms) | First / full (s) | Rest (ms) | Memory (MB) | D | Load | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| A four-each-b-supports | 2.5 / 2.0 | 2.5 / 1.8 | 2,550 | 0.8 / 3.5 | 429 | 1,172 | 1 | 3.6 | misses |
| A blocks-12-supports | 1.3 / 0.9 | 1.4 / 1.0 | 5,303 | 1.5 / 7.1 | 790 | 2,033 | 1 | 5.2 | misses |
| A spacers-150 | 5.5 / 5.0 | 10.0 / 4.3 | 666 | 1.2 / 1.9 | 200 | 493 | 1 | 7.1 | misses |
| B four-each-b-supports | 15.0 / 7.5 | 15.0 / 12.0 | 2,924 | 1.3 / 4.9 | 440 | 1,227 | 4 | 7.5 | misses |
| B blocks-12-supports | 12.0 / 8.6 | 10.0 / 7.5 | 6,266 | 2.4 / 10.2 | 798 | 2,073 | 8 | 7.4 | misses |
| B spacers-150 | 20.0 / 12.0 | 15.0 / 10.0 | 691 | 1.2 / 2.1 | 226 | 534 | 4 | 7.1 | misses |
| **C four-each-b-supports** | 15.0 / 7.5 | 15.0 / 8.6 | 159 | 1.4 / 3.5 | 706 | 619 | 4 | 3.2 | passes |
| **C blocks-12-supports** | 15.0 / 10.0 | 20.0 / 8.6 | 116 | 1.7 / 7.0 | 1,207 | 904 | 8 | 4.6 | passes |
| **C spacers-150** | 20.0 / 12.0 | 20.0 / 8.6 | 129 | 1.4 / 2.2 | 350 | 418 | 4 | 5.8 | passes |

The sliced files: `four-each-b-supports` 8,830,158 bytes, 1,063,346 lines of G-code, 998,280
segments, 344 layers; `blocks-12-supports` 14,136,085 bytes, 2,189,011 lines, 1,910,234
segments, 344 layers; `spacers-150` 2,727,571 bytes, 874,281 lines, 459,900 segments, 13
layers. Slicing them took Orca 19.5, 35.1 and 10.3 s and peaked at 1,370, 2,325 and 652 MB.

What software drawing costs here (`bench.html`, 640 by 480, load average 5.5): plain triangles
106 ns each and one-pixel lines 100 ns each (500,000 of either); an instanced quad or box
15,365 ns each (20,000), whatever its number of triangles, so instanced drawing is about 150
times slower than the same triangles drawn plainly. That is why the mockup's method took
27 µs a segment, and why every method here gives each box six vertices of its own.

## Decisions made

1. **The three plates' exact layout.** The details file names them; it is silent on the
   spacers' orientation, whether "22 mm apart" is pitch or gap, and how supports are asked
   for. Chosen: the spacer flat on its base (`+z`), 22 mm centre to centre (the slice
   service's `spacer_grid`, which the measured 2.72 MB came from), 13 to a row, 150 in all;
   supports through the built `supports` override (`"on"` or `"off"`); `four-each-b` copied
   from `slice/tests/frc_parts.py`, since the wizard reads no other component's folder. The
   reason: the three sliced files then match the details file's sizes (8.83, 14.14 and
   2.73 MB). To overrule: change `plate_configurations()` in `make_sliced_files.py` and the
   committed `wizard/trials/plates/`.
2. **Which of Orca's line types fall in which group.** The guide names eight; Orca 2.4.2 writes
   more. Chosen: Overhang wall with walls; Gap infill and Internal Bridge with infill; Bridge
   and Ironing with top and bottom surfaces; Support interface, Support transition, Skirt,
   Prime tower and Custom with supports and brim; a type Orca adds later, with walls. The
   reason: each sits with the group a user would expect from where it lies in the part. To
   overrule: `FEATURE_GROUP` in `gcode.js`.
3. **How a line is drawn: a box, top and near side.** The guide asks for the look, not the
   method. Chosen: each segment a box as wide as its line (never under 1 pixel, 2 for the
   current layer) and as tall as its layer (4 % taller, to close cracks), ends pushed out by
   half the width, its top and the long side towards the camera drawn, the walls' sides
   darkened by the way they face the mockup's light. End faces are not drawn: the pushed-out
   ends overlap the next box. The reason: a stack of boxes is a closed surface, which is what
   "no combs, no show-through" asks; a flat strip, the mockup's, is not. To overrule: the
   vertex shader in `methods.js`.
4. **Where lines of one layer overlap, the walls win.** Silent. Orca lays infill and surfaces
   a little over the walls' edge, and two tops at one height speckle in the depth buffer.
   Chosen: the walls' tops sit 0.01 mm higher. Lifting the other lines instead was tried and
   showed every top-surface line's end as a sawtooth along the walls. To overrule: `lift` in
   the shader.
5. **WebGL 2 directly, three.js only for the camera and its controls.** Silent. The reason: the
   methods need byte-packed vertices, batches with moving attribute offsets, fences and an
   off-screen image, which three.js hides. Nothing new is vendored.
6. **Arcs and merging.** Orca writes arcs (G2, G3) in these files. Chosen: arcs cut into chords
   within 0.02 mm, and straight runs of one type merged while no point strays over 0.01 mm,
   for the full look; 0.1 and 0.05 mm for the look while moving. The reason: below a tenth of
   a pixel at the closest view, and the merge saves 1 to 2 % on these files.
7. **The look while moving.** The details file allows "a simpler look, the four colours kept".
   Chosen: every D-th layer of the coarser reading, each box D layers tall, the layers between
   the last of them and the current layer from the full set, the current layer, no ghost; D the
   smallest of 1, 2, 4, 8 and 16 that keeps it within 200,000 boxes. The reason: it keeps the
   plate's shape and all four colours at a cost fixed by the budget; 300,000 left too little
   margin on a busy machine. To overrule: `MOVING_BUDGET` in `methods-prepare.js`.
8. **Dragging the layer bar counts as moving.** The guide's requirement 1 names both turning
   and dragging; the simpler look is allowed "while the view is moving". Chosen: both use the
   look while moving; the full look follows when the bar stops. The reason: at the bar's
   frame rate, drawing every box is several times too slow. To overrule: the bar's handlers in
   `viewer.js`; the figures for drawing every box are method A's.
9. **The full look at rest, a piece a frame.** Silent. Chosen: pieces of at most 100,000 boxes,
   the current layer first and then from the top down, each started only after a fence shows
   the last finished; the uploads 8 MB a frame the same way; the ghost last, as a piece of its
   own; a first frame of one box that builds the pipelines. The reason: the browser queues
   drawing without waiting, so without fences the pieces pile up and the copy to the screen
   held the page 800 ms. To overrule: `PIECE` and `UPLOAD_BYTES` in `methods.js`.
10. **The ghost is the instances' own meshes.** The details file says "a faint grey, mostly
    transparent shape cut at the current layer". Chosen: each instance's STL placed as the
    plate configuration's contract places it, the mockup's grey `#95a0ac` at 36 %, faces a
    little darker as they turn from the light, back faces culled, cut in the fragment shader.
    The reason: the wizard has the parts, and the sliced file has no mesh. To overrule: `scenery`
    in `viewer.js`.
11. **How the measuring is done.** The details file says "by the same measuring the wizard's
    reports use", which is not built yet. Chosen: frame times are the intervals between
    animation frames that drew (checked once against frames that waited for their drawing to
    finish: the same 20 and 15 frames a second); typical is 1000 over the median interval,
    worst 1000 over the longest; the hold is the longest task the browser's Long Tasks API
    reports, or the longest frame script, over loading, both paths and coming to rest; the
    paths are 60 frames each, a full turn tilting by up to 0.35 rad, and the bar from the top
    layer to the first and back; the time to the first layer runs from the start of fetching
    the sliced file to the first frame on the screen; memory is the peak resident memory
    (`VmHWM`) of the renderer and graphics processes. The wizard's reports should take these
    same definitions. To overrule: `runPath` in `viewer.js` and `measure` in `run.py`.
12. **The coarse checks of the look.** Chosen: the full look, without the ghost, covers at least
    5 % of the view; every group with segments in the file shows on at least 0.05 % of the view
    at the top layer or the middle layer (so `spacers-150`, which has no supports, needs three);
    moving the bar from the top to the middle changes at least 1 % of the pixels; after a lost
    drawing context, caused on purpose, the view draws again. To overrule: the constants at the
    top of `run.py`.
13. **Renders.** Chosen: every view (default, top, edge-on from the front and the side, zoomed
    in, zoomed edge-on, zoomed from above, the middle layer at the default and zoomed view, and
    the look while moving) for C; the default view, the middle layer and the look while moving
    for A and B, which draw the full look with the same code. To overrule: `--all-views`.
14. **`run.py` exits 1 when no method passes on all three plates,** after writing every figure,
    render and the report, so `make -C wizard trials` fails as the Makefile's comment says a
    trial does.
15. **Hiding what air cannot reach was built and left unused.** A worker step that floods each
    layer's empty space from outside and hides the segments no air touches (`cull` in
    `prepare.js`, with its tests) hides 75 % of `spacers-150` but only 25 % of the robot
    plates (sparse infill is reached through the cavities' open channels), and took 10 to 14 s
    in the worker on the heavy plates. Not worth its time against a 5 s first layer; kept for
    the Preview step's builder with its figures.
16. **Making the sliced files.** The slice service was started from this worktree on a random
    port above 20000 with its own work folder under `/var/tmp`, under the shared real-Orca lock
    for the whole session, with `PENGUIN_SLICE_MAX_PEAK_MB=3000` for all three plates, and
    stopped as soon as the three were saved (memory before: 1.35 GB anonymous of the 12 GB).

## Targets missed

- **Method C on `blocks-12-supports` misses now and then on the shared machine.** Of three
  measurements after its last change, two passed (15 and 12 frames a second turning, holds
  116 and 123 ms) and one missed: 8.6 frames a second typical on both paths and a 302 ms hold
  at a load average of 6.4 on the 8 processors. The machine was shared with three other
  builders; the target is for a machine without a graphics card, not for one under that load.
  A lower `MOVING_BUDGET` (D = 16 on this plate) would give more margin at a coarser look.
- **The worst frame rate** is under 10 on every plate for every method (C: 7.5 to 12). The
  builder's part asks for 10 typical; the worst is recorded.
- **The look while moving** shows infill on the sides of round parts and steps on sloped ones,
  where every D-th layer stands for the D around it; the full look does not.
- **Methods A and B** miss on every plate: A at 1.3 to 10 frames a second, B with holds of 0.7
  to 6.3 s when it draws the full look in one frame. Both measured before the ghost's upload was
  split, which changes only their loading holds, which they miss by far anyway.
- **The machine with a graphics card** is not measured: the 30 frames a second on the Mac is the
  owner's.

## Not done

- **The owner's part of passing:** the renders looked at by the owner, and the 30 frames a
  second in Chrome on the Mac. The builder does not wait for it.
- **The wizard's Preview step itself** (item 13 of By phase) is a later batch, to be built on
  method C.
- **Requirement 2 for every 3D view** is shown only for the trial's page (a lost context,
  caused on purpose, draws again); the parts' pictures and the Layout view are not built.
- **The colour key, the readout's buttons and the "?"** are not on the trial's pages: they cost
  nothing to draw and are the Preview step's.

## What I saw in the renders

Every render of C was looked at, one by one, in
`wizard/trials/preview/results/C/<plate>/`:

- **No combs.** Walls, hole edges and the round bosses read as solid surfaces at every angle,
  edge-on from the front and the side and zoomed in (`zoom-edge-on.png` on all three plates is
  a flat blue face). The round sides show faint horizontal layer lines from the walls'
  shading, as a print does.
- **No show-through** of one colour through another at rest after the walls were lifted: top
  surfaces are flat green with clean blue edges (`zoom-top.png`, `zoom.png`). Before that change
  the walls speckled through the green; with the opposite change the surface lines' ends made a
  sawtooth along every wall. Both were seen and fixed.
- **Supports** (violet) read as solid trees and pads; between support lines the plate shows
  through where Orca leaves gaps, which is the real gap.
- **The middle layer** (`default-layer-*.png`, `zoom-layer-*.png`): the cut shows orange infill,
  green surfaces and blue walls, unshaded, under the faint grey ghost of what is still to print.
- **At a distance** the round sides of the blocks show a fine stipple of lighter and darker
  pixels: each layer's box is under a pixel tall there and its shade is sampled, not averaged.
  Not a comb or show-through, but the owner should judge whether it looks right.
- **The look while moving** (`default-moving.png`) keeps the four colours and the shape; it
  shows orange infill on the sides of the round bases of the blocks, which the full look does
  not.

## For the owner to look at

1. [wizard/trials/preview/report.html](../../../../wizard/trials/preview/report.html), opened in
   a browser from the checkout: the figures and every render side by side.
2. The renders of C on the heaviest plate:
   `wizard/trials/preview/results/C/blocks-12-supports/` (`zoom.png`, `zoom-edge-on.png`,
   `zoom-layer-172.png`, `default-moving.png`), and the stipple on the round sides in
   `default.png`.
3. The frame rate on the Mac, in Chrome: the sliced files must first be made on the Mac
   (wizard/trials/preview/README.md, "Running it"), then `make -C wizard trials-serve` and
   `http://127.0.0.1:8610/preview/c-progressive.html?plate=blocks-12-supports`; in the console,
   `await trial.turn(60)` and `await trial.dragLayers(60)` give the same figures as here.
4. Whether dragging the layer bar may use the coarser look (decision 8) and the budget of the
   look while moving (decision 7).
