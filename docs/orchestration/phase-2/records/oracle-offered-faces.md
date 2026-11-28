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
   inside, every 0.02 mm along it, the inside known from each triangle's outward winding; a
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

## Not done

- The wizard's handling of `slice.rests_on_an_edge` (its Back to Layout and no Slice again):
  built by the batch that builds every slice failure on the Preview step; this batch only adds
  the rows to the contract, the details and the guide.
- Bounding-box patches are not tested for a first layer (decision 7); a part modelled at an
  angle to its axes could still be offered a bounding-box patch on which it rests on an edge, an
  item the details already list as not handled.
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
