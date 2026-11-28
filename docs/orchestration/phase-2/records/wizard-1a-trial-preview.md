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
the builder's part of passing on all three plates: 10 frames a second typical (10 to 20
measured) while turning the view and dragging the layer bar, no hold of the main thread over
250 ms (113 to 198 ms), and the coarse checks of the look, read from what C itself put on the
screen at rest, the ghost included. Method C draws every line of the
sliced file as a box as wide as the line and as tall as its layer, of which the top and the
long side towards the camera are drawn, so that stacked layers close into surfaces with no
combs and no show-through. While the view moves (turning, or the layer bar dragged) it draws
every D-th layer of a coarser reading of the file, each box D layers tall (D = 4 or 8 on these
plates), and no ghost. At rest it draws the full look into an image off the screen at most
100,000 boxes a frame, each piece only once a fence shows the one before is drawn, then the
ghost as a piece of its own, and copies it to the screen when whole, about 0.4 to 1.8 s after
the view stops. Uploads to the graphics side go 8 MB a frame behind the same kind of fence.

On the shared machine the margin is thin, on more than the heaviest plate (below, "Targets
missed"): the last run of C on `blocks-12-supports` turned at exactly 10.0 frames a second,
an earlier one missed, and one of the reviewer's two runs on `spacers-150` missed on its hold.

The figures and renders below were all taken again on Sat 2026-11-28, after the review's
fixes (below, "The first review"), from sliced files made again through the slice service's
phase 2 HTTP interface.

### The machine

The agents' container: aarch64 Linux, **8 processors and 12 GB of memory as its cgroup gives
them** (`cpu.max` 800000 100000, `memory.max` 12,884,901,888 bytes), shared with three other
builders while the figures were taken (load average 3.0 to 7.2 at the start of each
measurement; recorded in each JSON file). Chromium 159.0.8154.6, headless, from
`make -C wizard install`, drawing WebGL 2 in software: ANGLE on Vulkan 1.3.0 over SwiftShader
(LLVM 10.0.0). The view is 640 by 480 pixels at a pixel ratio of 1.

### The figures

Frames a second are typical / worst over a 60-frame path; the hold is the longest the main
thread was held while loading, moving or coming to rest; "first / full" is seconds from the
page starting to fetch the sliced file to the first frame that drew toolpaths (for B and C
the look while moving; for A, which draws nothing until every box is uploaded, the full look)
and to the full look on the screen; "rest" is milliseconds from the end of the turn until the
full look is on the screen; memory is the peak resident memory of the page's renderer and
graphics processes together; "ghost" is the share of the view the ghost changes at the middle
layer, the same after the lost drawing context.

| Method, plate | Turning | Layer bar | Hold (ms) | First / full (s) | Rest (ms) | Memory (MB) | D | Load | Ghost | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| A four-each-b-supports | 2.7 / 1.9 | 2.7 / 1.9 | 2,964 | 4.5 / 4.9 | 374 | 1,172 | 1 | 3.0 | 2.4 % | misses |
| A blocks-12-supports | 1.4 / 1.1 | 1.7 / 1.2 | 6,893 | 9.6 / 10.3 | 741 | 2,025 | 1 | 6.4 | 16.3 % | misses |
| A spacers-150 | 6.0 / 4.6 | 10.0 / 4.3 | 914 | 1.9 / 2.1 | 196 | 493 | 1 | 7.2 | 12.7 % | misses |
| B four-each-b-supports | 15.0 / 8.6 | 20.0 / 10.0 | 2,563 | 1.6 / 4.7 | 432 | 1,227 | 4 | 6.8 | 2.4 % | misses |
| B blocks-12-supports | 15.0 / 10.0 | 20.0 / 10.0 | 5,111 | 2.5 / 8.7 | 860 | 2,082 | 8 | 6.7 | 16.3 % | misses |
| B spacers-150 | 20.0 / 6.7 | 20.0 / 10.0 | 707 | 1.6 / 2.4 | 218 | 535 | 4 | 6.7 | 12.7 % | misses |
| **C four-each-b-supports** | 15.0 / 12.0 | 20.0 / 10.0 | 113 | 1.5 / 3.3 | 622 | 615 | 4 | 6.0 | 2.4 % | passes |
| **C blocks-12-supports** | 10.0 / 5.0 | 12.0 / 7.5 | 198 | 2.7 / 8.5 | 1,787 | 839 | 8 | 6.0 | 16.3 % | passes |
| **C spacers-150** | 20.0 / 12.0 | 12.0 / 5.0 | 193 | 1.7 / 2.4 | 441 | 423 | 4 | 6.5 | 12.7 % | passes |

The sliced files: `four-each-b-supports` 8,826,407 bytes, 1,063,371 lines of G-code, 998,281
segments, 344 layers; `blocks-12-supports` 14,129,734 bytes, 2,189,011 lines, 1,910,234
segments, 344 layers; `spacers-150` 2,729,074 bytes, 874,281 lines, 459,900 segments, 13
layers. Made again on Sat 2026-11-28 through the phase 2 HTTP interface, slicing them took
Orca 14.9, 37.3 and 11.2 s and peaked at 1,406, 2,314 and 652 MB (the slice service's
`peak_rss_kb`); the files made on Fri 2026-11-27 through the earlier interface differed by a
few thousand bytes and, on the first plate, 25 lines.

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
   reason: the three sliced files then match the details file's sizes (8.83, 14.13 and
   2.73 MB). To overrule: change `plate_configurations()` in `make_sliced_files.py` and write
   the committed `wizard/trials/plates/` again with `--write-plates`.
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
    the sliced file to the first frame that drew toolpaths (a frame of the plate alone, while
    the boxes upload, or C's first frame of one box, does not count); memory is the peak resident memory
    (`VmHWM`) of the renderer and graphics processes. The wizard's reports should take these
    same definitions. To overrule: `runPath` in `viewer.js` and `measure` in `run.py`.
12. **The coarse checks of the look.** Chosen: every check reads what the method itself put on
    the screen at rest, on the frame that finished the full look (`look` in `viewer.js`,
    `look.js`). At the top layer the view is at least 5 % covered; every group with segments in
    the file shows on at least 0.05 % of the view at the top layer or the middle layer (so
    `spacers-150`, which has no supports, needs three; the middle layer's colours are sorted on
    the method's drawing with the ghost left out, since the ghost lies between the camera and the
    cut and tints every colour under it); moving the bar from the top to the middle changes at
    least 1 % of the view; the ghost changes at least 0.2 % of the view at the middle layer (the
    method's drawing with the ghost against the same without it; measured 2.4 to 16.3 %); and
    after a lost drawing context, caused on purpose, the middle layer again covers 5 % and its
    ghost again changes 0.2 %. To overrule: the constants at the top of `run.py`.
13. **Renders.** Chosen: every view (default, top, edge-on from the front and the side, zoomed
    in, zoomed edge-on, zoomed from above, the middle layer at the default and zoomed view, and
    the look while moving) for C; the default view, the middle layer and the look while moving
    for A and B, which draw the full look with the same code. To overrule: `--all-views`.
14. **`run.py` exits 1 when no method passes on all three plates,** after writing every figure,
    render and the report, so `make -C wizard trials` fails as the Makefile's comment says a
    trial does. When none passes it names the fastest of the methods with the required look on
    every plate, as the owner's direction says, and no method at all when none has the look.
    It writes the committed `report.html` only with the figures in the committed `results/`;
    with `--out` elsewhere the report goes beside those figures.
15. **Hiding what air cannot reach was built and left unused.** A worker step that floods each
    layer's empty space from outside and hides the segments no air touches (`cull` in
    `prepare.js`, with its tests) hides 75 % of `spacers-150` but only 25 % of the robot
    plates (sparse infill is reached through the cavities' open channels), and took 10 to 14 s
    in the worker on the heavy plates. Not worth its time against a 5 s first layer; kept for
    the Preview step's builder with its figures.
16. **Making the sliced files.** The slice service was started from this worktree on a random
    port above 20000 with its own work folder under `/var/tmp`, under the shared real-Orca lock
    for the whole session, with `PENGUIN_SLICE_MAX_PEAK_MB=3000` for all three plates, and
    stopped as soon as the three were saved (memory before: 1.37 GB anonymous of the 12 GB, the
    rest page cache).
17. **The client speaks the slice service's phase 2 HTTP interface.** After the merge of
    `origin/main` the slice service refuses a multipart plate configuration and needs a user
    key, so `make_sliced_files.py` was ported rather than pinned to an earlier commit of the
    slice service: a pinned commit would leave the trial on an interface nothing else uses.
    Chosen: each part uploaded by itself (`POST /parts?units=mm`) and its record's `sha256` and
    `units` checked against the plate configuration's; then the plate configuration as JSON
    (`POST /slices`); every request under the user key `wizard-trials` (`--user-key`). The
    contract is silent on what a script's ids should be. Chosen: each plate's `plate_id` and
    committed `submission_id` are fixed UUIDs (version 5, from the plate's name), so the
    committed plates are what the script writes; each slice sends a new `submission_id`
    (version 4), as the contract says the page does each time it decides to slice, so a second
    run within the two hours the slice service remembers a submission slices again instead of
    being answered with the first run's slice job. A part's key is its file's name without
    `.stl`, which the trial's page uses to fetch the part for the ghost. To overrule:
    `configuration()` and `slice_plate()` in `make_sliced_files.py`.
18. **A box is at most 5.1 mm tall.** Its height is one byte of fiftieths of a millimetre. Chosen:
    the look while moving never takes a D whose boxes of D layers would be taller (D falls back
    to the largest that fits), and a box that would still be taller is refused with an error
    that names the layer, never clipped. At 0.2 mm layers D = 16 is 3.2 mm, so nothing changes
    on these plates. To overrule: `MAX_BOX_MM` in `prepare.js` and `decimationFor` in
    `methods-prepare.js`.

## Targets missed

- **Method C misses now and then on the shared machine, on more than the heaviest plate.** On
  `blocks-12-supports`: of three measurements on Fri 2026-11-27, two passed (15 and 12 frames a
  second turning, holds 116 and 123 ms) and one missed (8.6 frames a second typical on both
  paths, a 302 ms hold, load average 6.4); the committed run of Sat 2026-11-28 passed at exactly
  10.0 frames a second turning, a 198 ms hold, load average 6.0. On `spacers-150`: one of the
  reviewer's two runs missed on its hold (303 and 355 ms, load average 4.8); the committed run
  passed with a 193 ms hold and 12 frames a second on the layer bar. The machine was shared with
  three other builders; the target is for a machine without a graphics card, not for one under
  that load. A lower `MOVING_BUDGET` (D = 16 on the blocks) and a smaller `PIECE` would give more
  margin at a coarser look while moving and a slower return of the full look.
- **The worst frame rate** is under 10 on every plate for every method (C: 5.0 to 12). The
  builder's part asks for 10 typical; the worst is recorded.
- **The full look at rest** takes up to 8.5 s from opening on the heaviest plate (1.8 s after a
  turn ends). No target names it; the first layer, which the target names, is on the screen
  within 2.7 s.
- **The look while moving** shows infill on the sides of round parts and steps on sloped ones,
  where every D-th layer stands for the D around it; the full look does not.
- **Methods A and B** miss on every plate: A at 1.4 to 10 frames a second, B with holds of 0.7
  to 5.1 s when it draws the full look in one frame.
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
- **The middle layer** (`default-layer-*.png`, `zoom-layer-*.png`), looked at again on Sat
  2026-11-28 after the fix of the ghost: the cut shows orange infill, green surfaces and blue
  walls, unshaded, under the faint grey ghost of what is still to print: the upper halves of the
  twelve blocks, the tops of the carriages and pulleys of `four-each-b-supports`, and on
  `spacers-150` a grey ring over each spacer, plain in `zoom-layer-6.png` and faint at the
  default distance. `zoom-layer-172.png` of `four-each-b-supports` shows a part wholly below
  the cut, so no ghost, and the ghost of the parts behind it at the top right. The renders
  committed on Fri 2026-11-27 had no ghost: every render is made after the deliberate loss of
  the drawing context, and the ghost was never sent to the graphics side again after it (the
  first review, finding 1). This section said otherwise then; it was wrong.
- **At a distance** the round sides of the blocks show a fine stipple of lighter and darker
  pixels: each layer's box is under a pixel tall there and its shade is sampled, not averaged.
  Not a comb or show-through, but the owner should judge whether it looks right.
- **The look while moving** (`default-moving.png`) keeps the four colours and the shape; it
  shows orange infill on the sides of the round bases of the blocks, which the full look does
  not.

## The first review

Pull request #29 was reviewed by someone who did not write it. Every finding was checked
against the code and found real; each was fixed with a test that failed for its reason first.
None was declined.

1. **C drew no ghost at rest.** Cause: after a lost drawing context the page builds the scene
   again, but its flag that the ghost had arrived stayed set, so the new scene's ghost was
   never uploaded and every later frame left it out; `run.py` makes every render after the
   deliberate loss. A's committed renders had a ghost only because they dated from before the
   ghost's upload was split. Fixed: the flag is cleared with the scene. Shown by the new check
   of the ghost after a lost context: with the fix taken out, C on `four-each-b-supports` gave
   `ghost_after_context_lost` 0 and missed the look; with it, 0.024.
2. **The coarse checks drew every box in one frame, not the method's drawing.** Fixed: they
   read the method's own pixels at rest, ghost included (decision 12); the drawing of every box
   in one frame is no longer part of a method. The reviewer's mutation (C's copy to the screen
   replaced by a clear) now gives coverage 0, no colours and no ghost, and misses the look.
3. **The sliced files could not be made from the branch.** Fixed by porting the client
   (decision 17); the three sliced files were made again with it from this branch's slice
   service and every figure above was taken from them.
4. **Figures in the documents disagreed with the committed ones, and the first layer was timed
   to C's frame of the plate alone.** Fixed: the first layer is timed to the first frame that
   drew toolpaths (decision 11); C's first frame of one box counts as none; every figure in
   [wizard/README-details.md](../../../../wizard/README-details.md),
   [wizard/README.md](../../../../wizard/README.md) and the trial's README was taken again from
   the committed JSON files; the trial's README said 150,000 boxes a piece where the code says
   100,000.
5. **Failures no test reached, and surviving mutations.** Tests added: the client's refusal of
   a sliced file that is not there (the reviewer's `if False:` mutation of `fetch` now fails
   it), a part refused or kept under another hash, `make_sliced_files.py` without `--url`
   (exit 2), `run.py` with a sliced file missing (exit 2), and a diagonal segment's box (the
   reviewer's mutation of the far end now fails it).

The minor findings, all fixed: `choose` falls back to the fastest method with the required look
(decision 14); tests at exactly 10 frames a second and exactly 250 ms; the unused constants
`FIRST_LAYER_S` and `PAGE_MEMORY_MB` removed from `run.py` (the trial's verdict is the
builder's part, which names neither); the committed report is no longer replaced by a run
written elsewhere; the thin margin on `spacers-150` is in "Targets missed"; each reading of the
G-code keeps its own list of line types; a box too tall for its height byte is refused, and D
is held below it (decision 18).

## For the owner to look at

1. [wizard/trials/preview/report.html](../../../../wizard/trials/preview/report.html), opened in
   a browser from the checkout: the figures and every render side by side.
2. The renders of C on the heaviest plate:
   `wizard/trials/preview/results/C/blocks-12-supports/` (`zoom.png`, `zoom-edge-on.png`,
   `zoom-layer-172.png`, `default-moving.png`), and the stipple on the round sides in
   `default.png`.
3. The frame rate on the Mac, in Chrome: the sliced files must first be made on the Mac
   ([wizard/trials/preview/README.md](../../../../wizard/trials/preview/README.md), "Running it",
   with this repository's slice service, whose phase 2 interface the script now speaks), then
   `make -C wizard trials-serve` and
   `http://127.0.0.1:8610/preview/c-progressive.html?plate=blocks-12-supports`; in the console,
   `await trial.turn(60)` and `await trial.dragLayers(60)` give the same figures as here.
4. Whether dragging the layer bar may use the coarser look (decision 8) and the budget of the
   look while moving (decision 7).
