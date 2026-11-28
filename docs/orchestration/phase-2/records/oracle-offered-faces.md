# Phase 2, batch oracle-offered-faces: the real Orca as the oracle of the faces offered

The builder's record of the batch that uses the real Orca, in a test and never in the product,
to check the faces the wizard offers to lay a part on. Written on Sat 2026-11-28 (Pacific time)
on branch `phase-2/oracle-offered-faces`.

What was built, by the task's items:

1. `make -C wizard offered-faces` ([wizard/scripts/offered-faces.js](../../../../wizard/scripts/offered-faces.js))
   writes [contracts/examples/placement/offered-faces/real-parts.json](../../../../contracts/examples/placement/offered-faces/real-parts.json):
   one pose for each patch the wizard offers on each of the eight real parts, the instance as
   the plate configuration's phase 2 instance carries it. The wizard's fast test
   `tests/geometry/offered-faces.test.js` fails when the committed file differs from the code's.
2. `slice/tests_orca/test_offered_faces.py` slices every pose through the HTTP interface, one
   instance alone over the default set with supports off, and requires each to slice. All poses
   are sliced: 60 in 74 s before item 3, 56 in about 72 s after, under the real-Orca lock. No
   sample was needed.
3. What the oracle showed: one pose of 60 refused (`slice.rests_on_an_edge`). The wizard now
   drops a hull face on which the part would rest on no face of its own, by the slice service's
   rule and figures ([wizard/src/geometry/first-layer.js](../../../../wizard/src/geometry/first-layer.js),
   step 5 of [Finding the faces a part can lie on](../../../../wizard/README-details.md#finding-the-faces-a-part-can-lie-on)).
   A slice fast test (`slice/tests/test_offered_faces.py`) checks the slice service's own rule
   on every pose without Orca. The second trial was run again for its pictures and figures.
4. `slice.rests_on_an_edge` is in [the error report's codes a user interface acts on](../../../../contracts/error-report.md#codes-a-user-interface-acts-on),
   with [an example](../../../../contracts/examples/error-report-rests-on-an-edge.json) the real Orca
   produces, asserted by the slice service's real-Orca suite and, field by field, by its fast
   suite.

## Decisions made

1. **Where the poses live.** The task names `contracts/examples/placement/`; the contract says
   that folder holds one JSON file for each shared plate, and both components' tests list it
   (the slice service's required exactly the 13 plates in it). I put the poses in a folder of
   their own, `contracts/examples/placement/offered-faces/real-parts.json`, and changed the slice
   service's test to require exactly the 13 plates as files and exactly that one folder beside
   them; the wizard's test lists only `.json` files and needed no change. To overrule: move the
   file and change `OFFERED_FACES_FILE` in the script and the paths in the two slice tests.
2. **The pose file's shape.** The documents fix only that each pose carries the part, the patch
   and the rotation as the phase 2 instance carries it. I chose `parts` keyed by the real part's
   file name, each `{name, sha256, units}` exactly as a plate configuration names a part, and
   `poses`, each `{id, patch: {index, kind, side?, normal, area_mm2}, area_rank, orient_rank,
   chosen, instance}`, the instance laid from as modelled as a click lays it
   (`instanceTurn(layFor(normal), 0)`), `angle` 0, at the H2S plate's middle (170, 160). Ranks
   were added for the sample the task allows; none was needed. To overrule: change
   `offeredFaces` in the script and the two slice tests that read it.
3. **No sample: every pose is sliced every time.** The task allows a sample above about 15
   minutes; the whole run took 74 s for 60 poses (about 1.2 s each, each part small). To
   overrule: filter `POSES` in `tests_orca/test_offered_faces.py` by `area_rank` and
   `orient_rank` (the first draft did, with an environment variable to run all).
4. **The wizard's rule is the slice service's whole rule, not the face area alone (this narrows
   the guide's "any face of its hull").** The task suggested, as the simplest rule, not offering
   a hull face on which the part's own surface is too small to be a first layer. Measured on
   the 60 poses: 21 hull faces of the three elevator blocks have none of the part's own surface
   on the plate (under 0.01 mm²), and Orca slices 20 of them: they rest on the rounded rims of
   pockets, millimetres wide half a layer up. The face area alone would have taken 20 sliceable
   faces from the user. I chose the slice service's two conditions together, with its figures
   (`REST_AREA_MM2` 0.01 mm² of faces within `ON_THE_PLATE_MM` 0.001 mm, and no disc of
   `FIRST_LINE_MM` 0.62 mm in the section at half of `FIRST_LAYER_MM` 0.3 mm), so that the
   wizard offers no pose the slice service would name and the two agree exactly: on the 60
   poses both name the same four (the slice service measured with its own code, the wizard's
   test pins the four normals). It drops the one Orca refuses and three Orca slices, whose first
   layer is under a line across (606 mm² faces of normal (0, 0.71, 0.71); shrunk by 0.2 mm 0.47
   mm² is left, by 0.31 mm nothing). The guide's step list, its paragraph on hull patches and
   the details say so. To overrule: drop step 5 in `geometry/faces.js` (the poses file then
   changes and the oracle refuses one pose again); or use the face area alone (21 faces dropped,
   20 of which slice); or give the wizard a first layer of its own, looser than the slice
   service's, and accept that the slice service may name a pose the wizard offered.
5. **How the wizard measures the section.** The slice service uses shapely's buffer on the
   section polygon. The wizard has no polygon library, so it cuts the section's segments from
   the part's triangles and tries discs of the line's width touching the section's edge from
   inside, every 0.02 mm along it, the inside found by the even-odd rule as the slice service
   finds it (amended by the first review's fixer: see "Fixes after the first review"); a
   disc that fits anywhere can be moved until it touches the edge, so that search finds it up to
   the sampling. Near the threshold the two may differ by a few hundredths of a millimetre; on
   the eight real parts and the made shapes they agree. To overrule: replace
   `firstLayerHoldsALine` by a polygon offset.
6. **The default process's first layer.** The slice service reads the slice job's process; the
   wizard finds faces once for each part, before and whatever the settings. I used the default
   process's 0.3 mm and 0.62 mm. A user who sets a thinner first line could slice a face the
   wizard no longer offers, and one who sets a wider one could be refused on a face it offers
   (the slice service then answers `slice.rests_on_an_edge`). To overrule: make the faces depend
   on the settings, which means finding them again when the first layer changes.
7. **The rule applies to hull faces, not to bounding-box patches, and a dropped face covers no
   side.** The task speaks of hull faces. Applied to bounding-box patches too, it removed the
   patches of two existing tests (a box modelled turned 31 degrees, a wedge), which rest on an
   edge, and those tests pin `BBOX_COVER_DEG`; on the real parts the only bounding-box patches,
   the pulley's rim, slice. A face step 5 drops does not count as covering its side, so a side
   left empty gets a bounding-box patch as before; on the real parts none appeared. To overrule:
   test each bounding-box patch with `restsOnNoFace` in step 6 and change those two tests.
8. **`planeBasis` moved into the new module.** The build refuses modules that import each other
   in a circle, and the new module needed `planeBasis` from `geometry/faces.js`, which needs the
   new module. It now lives in `geometry/first-layer.js` and `geometry/faces.js` gives it out
   under the same name, so `geometry/orient.js` and the next builder see no change. To
   overrule: move it to a module of its own.
9. **The second trial run again.** The task asks for the trial's recorded expectations and
   pictures to follow the rule. `make -C wizard trials-geometry` rewrote every result and the
   three blocks' pictures, with figures of a machine shared with other builders (every target
   still met; the faces from nothing now at most 241 ms for the hub and 92 ms for a real part,
   215 ms and 84 ms before). The trial's notes, the details' performance rows and the guide's
   figure were brought into line with the new run. To overrule: restore the first run's results
   and keep only the three pictures.
10. **The contract's row for `slice.rests_on_an_edge`.** The slice service's last record
    declined it (its decisions 15 and 23) because a row binds the wizard; the task asks for it.
    The row says Back to Layout, as `choose_orientation` asks, and no Slice again, since the same
    plate fails the same way, and that the code comes from a plate laid out by another page
    version. The wizard's details and guide gained the same row in "When a slice fails". To
    overrule: remove the three rows; the action alone still gives Back to Layout.
11. **The example of the report.** I took it from the real Orca's report for the bracket on its
    hull face with supports off (the upstream check's existing case), detail included. The
    real-Orca test asserts every field but the detail equal to the file, and the detail's first
    three lines; the fast test, with the fake Orca and a box on its edge, asserts code, remedy,
    action, retryable, the field order, and message and `where` with the instance renamed. To
    overrule: hold the detail whole, which ties the example to Orca's wording of its log.
12. **The first review's finding that the documents promised too much: the documents
    corrected, the code kept.** The contract's row, the details' and the guide's rows in "When
    a slice fails" said the wizard never offers a face on which a part rests on no face of its
    own, and the guide added "a slicer that judges a first layer more strictly". Both were
    false. Decisions 5, 6 and 7 leave four ways for a plate this wizard laid out to get
    `slice.rests_on_an_edge`: a bounding-box patch (step 5 does not test them), a first layer
    set wider or lower than the default's (the slice service reads the job's process and
    overrides), a face within hundredths of a millimetre of the threshold (disc sampling
    against shapely), and another page version. A stricter slicer cannot give the code:
    `_explain_an_edge` in `slice/src/penguin_slice/plate_configuration.py` gives it only when
    the slice service's own rule names an instance, otherwise `slice.orca_failed`. The three
    rows, the guide's step 5, the details' step 6 and "Still not handled", the constants'
    comment and the guide's cases not handled now say this. I did not apply `restsOnNoFace` to
    bounding-box patches: it removes the patches two existing tests pin `BBOX_COVER_DEG` with
    (decision 7), and on a part like the reviewer's 20-spike urchin it would leave nothing at
    all to offer on a side, a change of the guide's step 6 the owner has not asked for; a
    bounding-box patch that rests on edges is answered by the slice service with its remedy
    (lay it on its own face, or supports with a raft). To overrule: test each bounding-box
    patch with `restsOnNoFace` in step 6 of `geometry/faces.js`, change the two tests of
    decision 7 and the star prism's test in `tests/geometry/first-layer.test.js`, and take the
    bounding-box case out of the three rows.
13. **The review's minor findings declined.** Minor 2 (no test that the four dropped faces are
    those the slice service names): `tests/geometry/real-parts.test.js` pins the four dropped
    normals exactly, so dropping one more on a real part fails it; that those four are the
    slice service's was measured once with its code (decision 4), and checking it in a test
    would add the dropped faces to the shared poses file, a change of its shape for a check
    that the slice service's fast test already makes in the other direction (no offered pose is
    one it names). Minor 4 (`time.monotonic()` in `slice/tests_orca/test_offered_faces.py`):
    it only measures each pose's time for the printed record, and no assertion or wait depends
    on it, which the quality bar allows. Minor 5 (instance labels with underscores in the
    message): there before the batch, the slice service's own labelling, outside this batch.
    The review's other findings were fixed with tests seen to fail first: the star prism's test
    fails under the reviewer's mutation of step 6 (a face dropped at step 5 counted as covering
    a side), and a threshold test of ridges and a ring 0.60 and 0.64 mm across half a layer up
    fails under each of the reviewer's looser disc tests (a slack of 0.05 mm; discs tried 1.2
    half-lines in, caught only by the ring, since a straight ridge's ends still hold such a
    disc).
14. **Second review, blocking finding: the section's inside found by the even-odd rule, not
    from the winding.** The reviewer showed that `firstLayerHoldsALine` took each segment's
    inside from its triangle's outward winding, while the slice service's
    `first_layer_section` uses the even-odd rule and slices an inside-out part with only
    `slice.part_inside_out`: the L wound inside out kept its face across the open corner, and
    with one of its 20 triangles turned it kept it in 12 of 20 cases. The documents were
    silent on winding; the reviewer offered (a) a winding-free search or (b) documenting the
    case. I chose (a): the documents' list of cases where the code can still come stays
    complete, and the wizard and the slice service measure the same section. Each segment's
    inside is now the side on which a point 0.00001 mm (`SIDE_MM`) off its middle is inside
    the section by counting crossings of a ray towards +x (segments bucketed by rows of one
    line's width); a segment inside on neither side is skipped. A disc that touches a segment
    on its inside and crosses no segment lies wholly inside, so the search's meaning is
    unchanged for a part wound outwards: the committed poses file, the trial's results and the
    real parts' tests are unchanged. The new test turns the L inside out and turns each of its
    20 triangles in turn (each drops the face), and checks that the rods and the 20-degree
    ridges still hold a line inside out; it failed before the fix (`true !== false` on the
    inside-out L). Cost, on Node, from the file to the part's best way: `hub-150k.stl` 217 to
    266 ms against 245 to 435 ms before (a shared machine; no difference to see), a
    144,000-triangle twelve-pointed star prism 106 to 197 ms against 125 to 186 ms. The details'
    step 5 and the guide's step 5 say so; `slice/README-details.md` no longer claims the fast
    test is the whole agreement and points to the contract's list. To overrule: go back to
    the winding and add wrong winding to the contract's row, the "When a slice fails" rows of
    both wizard documents and the guide's step 5.
15. **Second review, minor findings.** Fixed, each with a test seen to catch the mutation
    the reviewer named: `ON_THE_PLATE_MM` (a 20 mm box with its bottom tilted 0.005 mm has no
    face on the plate, tilted 0.0008 mm its 400 mm²; fails at 0.01 mm and would at 0.0005 mm);
    `SAMPLE_MM` (a prism whose section is a flat triangle 10 mm across and 0.624 mm tall, where
    a line fits only within 0.013 mm of the long side's middle; fails with the step at 1e9 and
    at 0.1 mm, though a step of 0.03 or 0.05 mm can still land in the window by the
    alignment, so the test pins the step to under about 0.03 mm, not to 0.02 mm exactly);
    `orient_rank` backwards (a new test checks that poses sorted by `orient_rank` run by
    auto-orient's cost, cheapest first, and by `area_rank` largest first; it fails under the
    reversed rank, not only through the committed file); `REST_AREA_MM2` at its exact value
    (two flats 2^-10 mm wide and 5.12 mm long add up to exactly 0.01 mm² in floating point,
    and the part stands, as the slice service's strict `<` has it; fails with `<=`). The
    guide's performance rows now agree with the details' figures (about a millisecond and
    0.24 s for the faces, 0.24 s and 0.17 s for auto-orient) and say that a part as large on
    which step 5 drops faces costs more, with the reviewer's 660 ms on Node; I could not
    reproduce the 660 ms with a star prism of my own make (above), so the figure is the
    reviewer's. `slice/README-details.md` no longer names this machine's lock path. Declined:
    none. A checked test that the wizard's chosen pose has `orient_rank` 1 was tried and is
    wrong: auto-orient keeps a part as modelled within 5% of the best cost, so the chosen
    patch can rank 2 (one real part does).
16. **Third review, blocking findings 1 to 3: the section joined into rings as the slice
    service joins it, and the even-odd ray cast across each segment.** The reviewer showed that
    the even-odd search of decision 14 was quadratic on a section of long finely cut strips
    (its ray ran along the strips through every segment of their row): auto-orient took 29.5 s
    on a 144,048-triangle star prism cut into 3,000 strips and 19.8 s on the L cut into 12,000,
    so decision 14's "no difference to see" and the 1 s target claimed met were false for such
    parts, as were the guide's and details' Auto-orient rows. The reviewer also showed that the
    wizard counted every cut while the slice service's `first_layer_section` keeps only closed
    rings from `linemerge` and takes their symmetric difference, so with one of the L's 20
    triangles doubled (4 cases) or removed (6 cases) the wizard kept the face across its open
    corner and the slice service named it; and that the guard "inside on neither side" had no
    test. The documents were silent on how the wizard joins the cuts; the reviewer offered (a)
    building rings as the slice service does or (b) adding "triangles doubled or missing near
    the plate" to every list of cases. I chose (a), so that the lists of cases where the code
    can still come stay complete without a new case: the cuts are chained through every point
    where exactly two meet (an edge two triangles share is cut from the same end, by the
    corners' coordinates in order, so both give the same point to the last bit, which is the
    order of the slice service's vertex indices too), and only chains that close with three
    segments or more are kept, which is what shapely's `linemerge` and `is_ring` give (checked
    with the slice service's environment: a square with a side doubled gives three open lines,
    a figure of eight two rings, a cut of no length nothing). For speed the even-odd ray runs
    along whichever plate direction is nearer the segment's normal, in rows and columns as wide
    as a segment is long on average (at least 0.0001 mm, `RAY_CELL_MM`), and the disc test
    compares squared distances. Measured on Node, from the mesh to the best way, five runs each
    on the shared machine: the 3,000-strip star 311 to 390 ms (0.77 s at 299c49c), the
    600-strip star 59 to 113 ms, the 12,000-strip L 204 to 299 ms (0.58 s at 299c49c),
    `hub-150k.stl` 248 to 330 ms. The reviewer's 40 STL files of the doubled and removed L,
    and seven more shapes (nested boxes, two boxes along one plane, boxes meeting at a corner,
    boxes overlapping by 5 mm and by 0.3 mm, a rod, a rod doubled), give the same verdict in
    the wizard and in the slice service's own code. New tests, each seen to fail: the L doubled
    and with each triangle doubled or removed (failed before the fix);
    the L cut into 600 strips bounding the segments the rays look at to under 100 for each
    segment (failed with the counter absent, and at 8,664,016 with the ray kept along x); two
    boxes along one plane, whose shared sides have the section on neither side (fails when the
    guard keeps the first normal); three nested boxes with a 0.15 mm gap and a 0.4 mm wall
    (fails with `SIDE_MM` at 0.2 and at 0.5 mm, minor finding 1). The test's ring standing on a
    circular ridge was not closed (its last step's sine is not 0), which the rings now see as
    a broken file, as the slice service would; the test now closes it. The committed poses
    file, the trial's results and the real parts' tests are unchanged. Minor finding 2 (open
    chains counted by the wizard and not by the slice service) is gone with the rings, and the
    details say how the section is joined. Minor finding 3 (`time.monotonic()` in
    `tests_orca/test_offered_faces.py`) is declined again as in decision 13: it only prints
    each pose's time. To overrule: go back to counting every cut and add "triangles doubled or
    missing near the plate" to the contract's row, both wizard documents' "When a slice fails"
    rows and the guide's step 5.

## Targets missed

- Not every test was seen to fail before its code. The example test of item 4 in the fast suite
  and the real-Orca assertion of the example were written after the example file, so they
  passed at once; the tests of items 1 to 3 (the poses file, the first-layer rule, the four
  dropped faces, the slice service's agreement test) were each seen to fail first, and three
  mutations of the rule (the section at a whole layer, half the area, a third of the line) each
  failed a test.
- The rule drops three faces that the real Orca slices (decision 4): Elevator Block Bottom
  Inner, Elevator Block Carriage and Elevator Block Top each on a 606 mm² hull face of normal
  (0, 0.71, 0.71), whose first layer is under one line across.
- Finding the faces costs more: on Node, Elevator Block Carriage from 72 ms to 89 ms; in
  Chromium the trial's worst for a real part from 84 ms to 92 ms and for the hub from 215 ms to
  241 ms (shared machine). Every target of the trial is still met.
- Step 5 can swap bad hull faces for bad bounding-box patches (decision 12). A 12-pointed star
  prism (radii 50 and 30 mm, 100 mm long) loses its 12 side hull faces at step 5 and is offered
  four bounding-box patches (`+x`, `-x`, `+y`, `-y`) that rest on tips too; before step 5 its
  sides were offered as hull faces 15 degrees from those, which rested on tips as well. So the
  wizard still offers a pose the slice service refuses on such a part; none of the real parts
  is one. A sharp 20-spike urchin is offered only bounding-box patches, all resting on tips.
  `tests/geometry/first-layer.test.js` pins the star's case.
- Step 5's cost on a part whose faces it drops: each face dropped reads the whole part for its
  section. On Node (decision 16) a 144,048-triangle star prism cut into 3,000 strips takes 311
  to 390 ms from the mesh to its best way and the 12,000-strip L 204 to 299 ms, within the
  auto-orient target of 1 s; in Chromium neither was measured. Until decision 16 the even-odd
  search was quadratic on such parts (29.5 s and 19.8 s), and decision 14's figures did not
  show it.
- The fixes of the third review (decision 16) were merged without a further review.

## Not done

- The wizard's handling of `slice.rests_on_an_edge` (its Back to Layout and no Slice again):
  built by the batch that builds every slice failure on the Preview step; this batch only adds
  the rows to the contract, the details and the guide.
- Bounding-box patches are not tested for a first layer (decisions 7 and 12); a part modelled
  at an angle to its axes, or one whose hull faces on a side all rest on edges (the star prism),
  can still be offered a bounding-box patch on which it rests on an edge, items the details
  list as not handled.
- Step 5 in Chromium on a large part whose faces it drops (the star prism above): not
  measured.
- The oracle is run with the default profiles and supports off only; other profiles' first
  layers are not tried (decision 6).

## For the owner to look at

- What the oracle cannot show is whether the wizard offers every face a person would want: the
  second trial's pictures are for that, with the table "Each part, as a person would see it" in
  [the trial's notes](../../../../wizard/trials/geometry/README.md). The three that changed:
  [Elevator Block Bottom Inner](../../../../wizard/trials/geometry/pictures/elevator-block-bottom-inner.png),
  [Elevator Block Carriage](../../../../wizard/trials/geometry/pictures/elevator-block-carriage.png)
  and [Elevator Block Top](../../../../wizard/trials/geometry/pictures/elevator-block-top.png).
  The blocks still offer 17 hull faces across their pockets that rest on rounded rims; Orca
  slices them, though a person would rarely choose them.
- The oracle, about 75 s:
  `flock /var/tmp/penguin-locks/real-orca.lock slice/.venv/bin/python -m pytest -s -p no:randomly slice/tests_orca/test_offered_faces.py`
  (each pose prints its outcome and time).
- The poses again after a change to the rules: `make -C wizard offered-faces`.
