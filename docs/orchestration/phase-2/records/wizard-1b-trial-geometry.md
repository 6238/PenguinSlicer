# Phase 2, batch wizard-1b-trial-geometry: the second trial and the Layout step's geometry

The builder's record of the second half of item 1 of
[the wizard's details, "By phase"](../../../../wizard/README-details.md#phase-2-one-machine):
the second opening trial, laying on a face, auto-orient and Arrange on real exported parts,
with the geometry it tried written as the wizard's own modules. Written on Fri 2026-11-27
(Pacific time) on branch `phase-2/wizard-1b-trial-geometry`.

What was built:

- The worker, [wizard/src/geometry.worker.js](../../../../wizard/src/geometry.worker.js), and
  the geometry in `wizard/src/geometry/`: the STL reader, a quickhull, finding the faces a part
  can lie on, the turn of an instance as a quaternion and its plate-configuration fields,
  auto-orient, Arrange, the placement check and the worker's messages, all written fresh. How
  each works is in [The geometry, in a worker](../../../../wizard/README-details.md#the-geometry-in-a-worker).
- Tests on Node's runner in `wizard/tests/geometry/` (105 of them when written): every step on
  small solids made in the tests, the eight real parts and the two made parts against the
  trial's recorded answers, every shared placement plate with its expected answer, and each
  error report.
- The trial in `wizard/trials/geometry/`: its page, its script (`make -C wizard trials-geometry`),
  its results, its pictures and [its notes](../../../../wizard/trials/geometry/README.md).
- The wizard's guide and details file brought up to date: what is built, the tuned rules, the
  measured figures.

The shared plates of `contracts/plate-configuration.md` were already on `main` (batch
slice-0-shared-plates) when the branch was made; the wizard's check gives exactly the expected
answer on all thirteen.

## Decisions made

1. **The worker's modules and messages.** The details propose a module `geometry.worker` and
   are silent on its messages. I wrote `wizard/src/geometry.worker.js`, which only wires
   `wizard/src/geometry/messages.js` to the worker's messages, so that the tests run the same
   messages in their own thread; the messages are `read`, `faces`, `orient`, `arrange`, `check`
   and `forget`, each answered `{id, ok, result}` or `{id, ok: false, error}`. To overrule:
   rename the files or messages; only the trial's page and the tests use them so far.
2. **The geometry's error codes.** The details say a part the page cannot draw gets the
   wizard's own notification (that PenguinSlicer could not show the part and that it cannot
   be imported) and name no code. I made two error reports: `wizard.part_not_drawable` (a file
   the reader refuses, or a part with no hull), matching the page report's `what` of the same
   name, and `wizard.layout_failed` (a message about a part never read, an unknown message, or
   the geometry failing), matching the report's `layout_failed`. To overrule: change the codes
   and sentences in `wizard/src/geometry/errors.js` and the table in the details file.
3. **The hull's method and tolerance.** The guide says a faster hull may be needed. I wrote
   quickhull with each face keeping its outside corners and repeated corners dropped first.
   A corner within 1e-6 mm of a face counts as on it: 1e-3 mm, tried first, left a corner of
   Clamp Plate Inner 0.006 mm outside its hull, too near the 0.01 mm by which the two
   placement checks must agree. To overrule: change `HULL_EPS_MM`; the hull test on a real
   part and on random spheres says whether a value works.
4. **Thin strips of the hull are part of the flat face beside them.** The documents are
   silent. On real parts a flat face came out of the hull as a large piece and strips a
   tenth of a degree off it (a fillet's corners a thousandth of a millimetre above the
   face), which the 0.06-degree join cannot reach. A face whose corners all lie within
   0.01 mm of a larger neighbour's plane, turning from it by less than 1 degree, is merged
   into it (`FLAT_GAP_MM`, `FLAT_TURN_DEG`). To overrule: drop `mergeFlat` in
   `geometry/faces.js`; the hub then gets two stray patches on its base.
5. **A round side is judged across shallow bends, not only between neighbours.** The details
   name this as known to be needed ("treat a run joined by shallow bends as one round side").
   A face is dropped when any face it reaches through faces all within 20 degrees of it is at
   least half its size. To overrule: limit the search to direct neighbours, as first written;
   the carriage then gets five patches on fillet facets.
6. **A flat face of the part's own surface is not dropped beside a bridging hull face.** The
   documents are silent; the rule as written dropped Elevator Top Inner's four flat sides,
   each 3 degrees from a hull face of the same size bridging down to a smaller lower block.
   A face of at least 25 mm² that is mostly the part's own surface is not dropped on account
   of a neighbour that is mostly a bridge. To overrule: remove `spares` in
   `geometry/faces.js`; the bounding-box patches then cover those sides instead.
7. **The tip-over test marks patches and hides none.** The guide says Orca's tool lacks the
   test and PenguinSlicer's should have it, and is silent on what it does. Tried as a filter
   it hid Elevator Top Inner's four real flat sides and two large flat backs of the elevator
   blocks; a printer's plate holds a print's first layer whichever way its weight falls. Each
   patch carries `stable` and `height` for the Layout step to use (for instance in the
   pointer line). To overrule: drop the patches whose `stable` is false in the worker's
   `faces` answer.
8. **Auto-orient's score kept as the mockup had it.** The details say the overhang
   threshold was invented and is to be tuned on real parts. I kept 45 degrees, 0.1 mm of
   contact gap, 0.01 per millimetre of height and 100 for almost no contact, since the
   choices on the real parts look right to me except one I am unsure of (below). To overrule:
   change the four constants; the real-parts test then shows what moves.
9. **A part that lies as modelled nearly as well as its best way stays as modelled.** The
   documents are silent. The made hub was turned over for a 5% difference in how its two
   ends were cut. As modelled is kept within `AS_MODELLED_MARGIN`, 5% of the best cost. To
   overrule: set it to 0.
10. **Arrange on a map of half-millimetre squares.** The details give the packers and are
    silent on how free spots are found. Each outline, grown by half the spacing plus
    0.025 mm and held by a 32-corner outline, is marked on a map of the plate; two outlines
    sharing no square are at least the spacing apart, so an arranged plate always passes the
    placement check, at the cost of up to about a millimetre more room. 1 mm squares placed 99
    of the mix of 150, half-millimetre ones 104. To overrule: change `ARRANGE_CELL_MM`, or
    replace the map by exact distances (slower).
11. **Where an instance Arrange cannot place waits.** The guide says beside the plate. I put
    such instances in a column 20 mm to the right of the plate. To overrule: change
    `BESIDE_GAP_MM` and the placing loop in `geometry/arrange.js`.
12. **What the placement check gives the Layout step.** The guide's messages need the edge
    crossed, the distance and the size as turned. Each problem carries `edges` (`left`,
    `right`, `front` for low y, `back` for high y), `size`, `height` or `distance`, in the
    slice service's order. To overrule: rename the edges; nothing else uses them yet.
13. **Serving the wizard's modules to the trial without touching the shared server.** The
    trials' server serves only `wizard/trials/`, `wizard/vendor/` and the real parts. The
    geometry trial's script takes `serve.make_server("127.0.0.1", 0)` and swaps in a handler
    of its own that also serves `wizard/src/` at `/src/`, with the same guards. So
    `make -C wizard trials-serve` does not serve the geometry page's modules. To overrule: add
    `/src/` to the roots of `wizard/trials/serve.py`.
14. **The pictures are drawn on a 2D canvas, not with three.js.** The details ask for one
    picture of each part in its chosen orientation with its patches. I drew four views on one
    picture (as modelled from above and from below, as laid from two sides, the patch it is
    laid on edged in red) by painting triangles far to near, so that no graphics card is
    needed. To overrule: draw them with three.js under the WebGL recipe the first trial uses.
15. **What each time measures.** "Selecting" is asking a worker that has already laid the
    part down for its patches, since the faces are found when the part arrives; "arriving" is
    reading the file and auto-orient on a fresh worker. The time to find the faces from
    nothing is recorded beside them. To overrule: count the faces from nothing against
    `PATCHES_MS` (215 ms for the hub: it would miss).
16. **The mix of real parts.** The details say "a mix of the real parts" at 150 instances. The
    first mix (60 Inner Spacers, 40 pulleys and so on) put only 38 on the plate. The mix is
    140 of Pulley v3 and one or two of each other real part, nearly a full plate. To overrule:
    change `MIX` in `run.py`.
17. **The main thread is measured by a heartbeat.** The details say the page measures holds
    by the browser's long-task timing. In the trial that timing reported up to about a second
    during the hub's steps, while no answer took over 0.3 s and a 10 ms heartbeat never went
    more than 15 ms between beats; in a rerun the long task moved to another part (hub-150k
    0 ms, Elevator Block Bottom Inner 519 ms). The trial records both and counts the
    heartbeat. After review the details' "Keeping the page answering" says so: the heartbeat
    is the page's measure, and an Open line asks why Chromium reports those tasks. To
    overrule: count the long tasks, in the details and in `run.py`.
19. **After review: the placement check's footprints are kept by the part's hull corners.**
    The reviewer found that the worker kept footprints across `check` messages by the plate
    configuration's part key, so a key that came to point at another read part (the spacer
    read in inches after millimetres) answered from the old part's footprints: `[]` for a plate
    a fresh worker refuses with two `off_plate` and a `too_close`. Confirmed with a test that
    failed for that reason. The cache is now a `WeakMap` keyed by the hull's corner array of
    the part as read, then by turn and angle; a part read again gets a new array, and a
    forgotten part's footprints go with it, so `forget` no longer clears anything. Arrange's
    own cache is keyed the same way. To overrule: key by the read key instead, which must then
    also be cleared on every `read`.
20. **After review: the remedy of `wizard.layout_failed`.** The details quoted two sentences
    of each geometry error report that the guide did not have, and the remedy "Reload the page;
    your parts and settings are kept." left out the layout. The guide now carries all four
    sentences (under its part that cannot be used, and under "Keeping the page answering"), the
    remedy reads "Reload the page; your parts, layout and settings are kept in this browser.",
    the wording the guide already uses for what the browser keeps, and a test checks that each
    sentence of each report is quoted in both files. The promise holds only once the page keeps
    the plate in the browser's storage, which is built with the page; no user sees the
    sentence before then. To overrule: change the sentences in the guide, the details and
    `geometry/errors.js` together.
21. **After review: declined, the hull's "could not be closed" refusal has no test that
    produces it.** It guards an inconsistency of the horizon that only corners closer than the
    hull's tolerance could cause, and no input I could construct reaches it (the hull is
    checked on random spheres and every real part without meeting it). A test would have to
    reach into the hull's internals. The two other refusals the reviewer named ("no size",
    "one line") now have a test each that tells them from the flat refusal. To overrule: find
    an input that reaches it and add it as a test.
18. **When the trial fails.** The details give its passing conditions. `run.py` exits 1 when a
    time is missed or a real part's flat face has no hull patch, naming each, after writing the
    results. A flat face is a hull face of at least 25 mm² of which at least half is the part's
    own surface.

## Targets missed

None.

## Not done

- The round parts exported from Onshape at its coarse and fine settings: only the owner can
  supply them. The trial used `pulley-v3.stl` and `inner-spacer.stl`, as the details say, and
  its summary says so; Inner Spacer is a square plate with rounded corners, so the pulley is
  the only real round side tried.
- A round side of fewer than 18 facets, and a part modelled at an angle to its axes: the
  details list both as needed on real parts; no part kept in the repository has either, so
  neither has a rule or a test.
- The malformed STL ending in a notification on the main thread, with the panel never held
  past 250 ms: it needs the page (items 7 and 10 of "By phase"); the worker's error report for
  it is built and tested.
- The Layout step itself (the view, the gestures, the messages): item 10, a later batch.
- After review, the trial was not run again: the fixes change the worker's cache (which only
  makes a fresh footprint where a stale one was used) and the trial page's constants (the same
  values by name), not what the trial measures. `summary.json`'s note was brought into line by
  hand with the note `run.py` now writes, its figures left as recorded.

## For the owner to look at

- Each part's picture, in `wizard/trials/geometry/pictures/`, with the table "Each part, as a
  person would see it" in [the trial's notes](../../../../wizard/trials/geometry/README.md).
  Look first at [Elevator Block Bottom Inner](../../../../wizard/trials/geometry/pictures/elevator-block-bottom-inner.png):
  auto-orient turns it upside down, 82.6 mm tall, and I am not sure a person would; it also
  has nine patches on hull faces that bridge its pockets, which Orca offers too.
- The two arranged plates, [the spacers](../../../../wizard/trials/geometry/pictures/arrange-spacers-150.png)
  and [the mix](../../../../wizard/trials/geometry/pictures/arrange-mix-150.png): they pass, but
  the packing is uneven.
- `make -C wizard trials-geometry` runs the trial again (about a minute); the figures land in
  `wizard/trials/geometry/results/summary.json`.
