# Batch wizard-5b-layout-step: the record

Item 10 of [the wizard's details, "By phase", phase 2](../../../../wizard/README-details.md#phase-2-one-machine):
the Layout step. Built on Fri 2026-11-27 and Sat 2026-11-28 (Pacific) by one builder, with no one
to ask, beside the builder of the Settings step working in another worktree. What is built is
described in the details file's section [The Layout step](../../../../wizard/README-details.md#the-layout-step)
and, in plain words, in the guide's [What is to be built, by phase](../../../../wizard/README.md#what-is-to-be-built-by-phase).

## Decisions made

1. **An instance's name in the messages is its part's own name with the slice service's
   count** ("L Bracket #2"). The guide names instances "L Bracket #2"; the details say the names
   are "those the slice service gives", which reduces the name ("L_Bracket #2"). The two differ
   for any name with a space. Chosen: the guide's form (the guide is right where the two
   differ), with the number counted exactly as the slice service counts it, so a message of the
   wizard and a refusal of the slice service name the same instance by the same number. To
   overrule: `labels` in `wizard/src/layout.js`.
2. **New instances.** The documents say a new part's instances lie their best way and join the
   plate, and are silent on where they go. Chosen, as the mockup does: the first instances of a
   plate are arranged without a message; instances that join a plate already laid out are put at
   the middle of the instances on the plate and moved to the nearest free spot, every other
   instance where it stands (Orca also places a new object in free space without moving others).
   One that finds no spot waits beside the plate. To overrule: `join` in `wizard/src/layout.js`.
3. **An instance beside the plate that no message accounts for** (a part joining a full plate,
   a page opened again after a lay-down left one beside) has a message of the wizard's own,
   which no document writes: "Gusset Plate #3 waits beside the plate: no spot on the plate is
   free for it." with "Press Arrange to make room, or lower the quantities and print the rest
   on a new plate." and Arrange. Instances beside the plate that Arrange's or a lay-down's
   message counts have none, as the guide says, and the status line then reads "2 instances do
   not fit on the plate." (the mockup's words), holding Next. To overrule: `WAITS_BESIDE` and
   `DO_NOT_FIT` in `wizard/src/layout-sentences.js`.
4. **"Many instances too close" is two pairs or more.** The guide gives the sentence for two and
   for many and no threshold. Chosen: one pair is named; two or more pairs are one message
   counting every instance in them, as the mockup does. To overrule: `problemMessages` in
   `wizard/src/layout.js`.
5. **An instance crossing several edges** names them all ("it crosses the right and back
   edges."); the guide's example has one edge. To overrule: `OFF_PLATE`.
6. **The "too long as it is turned" message** opens "Rib #1 is not fully on the plate: it is
   353 mm from left to right as it is turned; …" when the instance still stands on the plate,
   the guide's "opens with 'not fully on the plate' and goes on with the same sentences" read
   literally; "from front to back" when the depth is what is too long. To overrule: `TOO_LONG`.
7. **Auto-orient arranges the plate again whenever, once laid, the plate breaks a rule other than
   the height, for a selection as for the whole plate.** The guide says "if the plate then needs
   rearranging, the wizard arranges it"; the mockup settles a selection's instances one by one
   instead. Chosen: the guide's words for both. To overrule: `autoOrient` in
   `wizard/src/layout.js`.
8. **The message after a lay-down that moved an instance turned** keeps the guide's sentence
   ("…so it was moved to the nearest free spot."); the mockup adds "and turned". The view shows
   the turn. To overrule: `MOVED_ONE`.
9. **The messages after Turn it to fit and the offer of Arrange's message** are the mockup's
   ("Turned Rib #1 and arranged 1 instance.", "Laid 30 instances the best way and arranged
   again: every instance now fits."), and Arrange's partial message keeps the mockup's second
   button, Back to Parts, which the guide does not mention. "A second plate" became "a new
   plate", the guide's words. The offer counts every instance not lying its best way. To
   overrule: `layout-sentences.js` and `arrangeAll` in `layout.js`.
10. **The selection's link is shown only for instances of one part**, as the mockup does; with
    instances of several parts selected there is none.
11. **A double-click on a face lays the instance down only on a flat face of a hull patch**: the
    triangle under the pointer within 1 degree of a hull patch's direction. Elsewhere it does
    nothing (the mockup's hint "cannot lie on that surface" was not built; the documents do not
    ask for it).
12. **The figures line names the printer by the configuration's printer profile name** ("Bambu
    Lab H2S 0.6 nozzle: plate 340 × 320 mm, …"), the details' proposal, until phase 5 names the
    paired printer.
13. **The stored layout's shape**: the stored plate's `instances` (already an array) hold `{part,
    lay, angle, x, y}` with `part` the part's row key; a stored instance the page cannot use is
    dropped and the part's quantity made up. No other field of the stored plate changed, and its
    `format` stays 1. To overrule: `stored` and `usableStored` in `layout.js`.
14. **The Layout view draws coarse copies of the parts while it moves, and at rest on a heavy
    plate.** Without a graphics card Chromium drew about three million triangles a second: 150
    instances of the robot's real parts (803,000 triangles) dragged at 3 to 4 frames a second
    and 150 of the largest part (22.5 million) at 0.6, against a target of 10. The guide allows
    a simpler look while moving only for the layer preview; the same was taken here: while the
    view moves on a plate of more than 250,000 triangles, and at rest on one of more than
    500,000, each instance draws its part's coarse copy (the worker's own vertex clustering, a
    grid over the part's box), the selected instances whole at rest. To overrule:
    `MOVING_TRIANGLES` and `REST_TRIANGLES` in `wizard/src/panel/layout-view.js` (set them very
    high to draw every part whole always); a better coarse copy is a change to
    `wizard/src/geometry/coarse.js` alone.
15. **Without a graphics card the view has no antialiasing**, and it never keeps its drawing
    buffer; both cost a software renderer a share of each frame. To overrule: the `software`
    option of `createLayoutView`.
16. **A part's bytes are sent as a Blob.** Sent as an `ArrayBuffer`, a 7.5 MB upload held
    Chromium's main thread 350 to 560 ms in the browser tests (about 11 ms as a Blob); the
    malformed file's notification within 250 ms could not be met without it. The bytes are
    unchanged (the upload test still compares them byte for byte). It changes the shared
    transport seam, `bodyOf` in `wizard/src/seams/transport.js`. Not known: whether Chrome
    without the DevTools protocol watching holds as long; the Blob costs nothing either way.
17. **The 3D view's tests run on the real clock**, since the view draws on animation frames,
    which Playwright's paused fake clock never runs; they wait on events (the page asked
    again), never a duration. The frame seam (`wizard/src/seams/frames.js`) is the one place
    the page asks for a frame.
18. **The step's sentences live in their own module**, `wizard/src/layout-sentences.js`, not in
    `wizard/src/sentences.js`, so that this batch and the Settings step's touch different
    files.
19. **Gestures not in the documents, taken from the mockup:** the handle's place outside the
    selection's box at 28 px, its radius 7 px, a press moving under 4 px being a click, the
    wheel zooming towards the pointer, and the camera's three views (Zoom to instances, Whole
    plate, Top) fitted as the mockup fits them.

## Targets missed

- **The main thread held over 250 ms during a drag at 150 instances**: 0.42 to 0.49 s on the
  real mix and 0.22 to 0.26 s on 150 spacers (`make -C wizard measure-layout`, four runs on an
  aarch64 Linux machine of 8 processors shared with three other builders; 0.10 to 0.13 s on 150
  of `hub-150k.stl`). A CPU profile shows over 95 % of the main thread's time outside the page's
  JavaScript, in Chromium's own work (drawing, most likely); which frame holds it was not found.
- **The look, against the mockup** (pairs in [look/wizard-5b](../look/wizard-5b/index.html)):
  - the plate and its grid are a little darker and bluer than the mockup's, and the parts'
    shading differs: three.js release 170's lights are not release 128's, and the view uses
    flat Lambert shading rather than the mockup's standard material;
  - a selected instance's tint is paler than the mockup's, and its patches are its hull faces'
    outlines, a little paler and with sharp corners where the mockup's are rounded;
  - the camera after a move does not follow an instance dragged off to an edge (the mockup's
    view, made by its scenario strip, shows the instance in sight);
  - the rotation handle starts above the selection where the mockup's sits at its left (both
    move clear of the patches; the mockup's had been pushed aside);
  - with no graphics card the edges of parts are not smoothed (no antialiasing, decision 15);
  - differences the pairs show that are not this batch's: the printer-status icon (phase 5),
    the configuration's name not a link (batch wizard-2), the printer named by its profile
    ("Bambu Lab H2S 0.6 nozzle" against "Shop H2S", decision 12), the profile "Standard"
    against "Structural", the parts (the contract's bracket and a box against the mockup's own
    parts, in millimetres against inches).
- **The frame rate with a graphics card** (30 frames a second) is unmeasured: only the owner's
  Mac can take it.

## Not done

- **The details' test of a lay-down answered before the worker returns the faces, in
  Chromium**: the page's patches come from one question to the worker, and the test without a
  browser window shows them found once; holding the worker's answer in Chromium needs a hook the
  page does not have.
- **The Layout view's drawing summaries in the page's reports about itself** (frames a second
  for each use of the view): item 18 of "By phase", not this batch.
- **The submission's own plate configuration** (`description`, `local_time`, the profiles):
  item 11; the Layout step builds the instances' part of it only for the worker.
- **The owner's part of the second trial** (looking at each real part's chosen orientation) is
  the owner's.

## For the owner to look at

- The pairs of pictures, mockup and built, at 320, 480, 520 and 680 px in six states:
  [docs/orchestration/phase-2/look/wizard-5b/index.html](../look/wizard-5b/index.html), made
  again with `make -C wizard look-layout-step`.
- The frame rate at 150 instances on the machine without a graphics card:
  [frame-rate.json](../look/wizard-5b/frame-rate.json), made again with
  `make -C wizard measure-layout`. On the Mac: start phase 2 on one machine, add the eight real
  parts with quantities making 150 instances, and drag one on the Layout step in Chrome.
- Dragging, turning with Shift, laying on a patch and Arrange by hand, in Chrome on the Mac:
  that the coarse copies while moving look acceptable (decision 14), and that the gestures feel
  like Onshape's.
