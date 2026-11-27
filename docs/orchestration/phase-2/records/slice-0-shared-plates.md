# Batch slice-0-shared-plates: the shared set of plates for the two placement checks

The builder's record of item 17 of
[the slice service's details, Phase 2](../../../../slice/README-details.md#phase-2-one-machine):
one shared set of plates for the placement checks, as fixed in
[the plate configuration contract](../../../../contracts/plate-configuration.md#shared-plates-for-the-placement-checks).
What was built is described in
[Shared plates for the placement checks](../../../../slice/README-details.md#shared-plates-for-the-placement-checks).

## Decisions made

1. **The plates' profiles.** The contract says each plate is "over the default set of
   profiles" and "every field", which pull opposite ways for `printer`, `filament` and
   `process`. Chosen: they are left out, which is what the default set means in the
   contract's Profiles. Reason: naming the H2S 0.6 nozzle profiles explicitly is a different
   path through the code (a catalog choice, not the default set). To overrule: add the three
   names in `scripts/make_placement_parts.py`, regenerate, and both suites follow.
2. **Supports stated on every plate.** The documents are silent on whether a supports-off
   plate sets `enable_support`. Chosen: every plate's `overrides` holds exactly
   `enable_support`, `"0"` or `"1"`. Reason: whether supports are on must not depend on the
   default process profile's own value, which the wizard's builder would otherwise have to
   look up. To overrule: drop the `"0"` from the supports-off plates in the script.
3. **No `local_time`.** The contract is silent. Chosen: left out; it bears on no placement
   rule. To overrule: add it in the script.
4. **The plates are written by the script too, not only the posts.** The details file names
   a script for the posts; it is silent on how the plates are written. Chosen:
   `scripts/make_placement_parts.py` writes the posts and all thirteen plates, and the test
   compares both byte for byte. Reason: the positions of the turned and rotated plates are
   irrational and must be computed; computing them with geometry of the script's own (its
   own hull, polygon distance and bisection), never `plate.py`, tests the slice service's
   check against an independent answer. To overrule: hand-edit the JSON and drop
   `test_the_set_is_what_the_script_writes`.
5. **The file names.** The contract gives `margin-pass.json` and `margin-fail.json` and
   "so on". Chosen: `margin-`, `height-`, `spacing-`, `spacing-supports-`, `angle-` and
   `rotation-` with `pass`/`fail`, and `height-laid-down-pass.json` for the third height
   plate. To overrule: rename in the script and in `EXPECTED` of the test; the wizard's
   tests read the same names.
6. **The posts' part names.** Silent. Chosen: `Post-340` and `Post-341`, so the too-tall
   instance is `Post-341 #1`. Reason: the file names, in the instance-name character set.
7. **The laid-down post.** The contract says the 341 mm post "laid down passes" but not how.
   Chosen: `orientation` `+x` at `angle` 30 at the plate's centre. Reason: 341 mm is longer
   than the 334 mm between the margins along x, so it fits only turned towards the
   diagonal. To overrule: change the angle in the script; it asserts the post stays more
   than 1 mm inside the margin.
8. **Fixed ids.** `plate_id` and `submission_id` are UUIDs the script makes with
   `uuid.uuid5` from each file's name, so they never change and differ on every plate.
9. **Where each plate sits.** Silent. Chosen: the fixed instance at (100, 160), the moved
   one along x at y = 160; the margin plates against the left edge; the height plates at
   the centre (170, 160). The script asserts every distance a plate does not try is more
   than 1 mm clear of its rule, so each plate fails for one reason only.
10. **The rotation plates now, before item 4.** The details file said the plates with a
    `rotation` wait for item 4. Chosen: they are run now, by turning a copy of the bracket by
    the contract's rotation matrix in the test and placing it `+z`, which the contract's
    one transform places exactly where the rotation does. Reason: the wizard's builder gets a
    checked answer for those plates from the start. When item 4 exists, its builder runs them
    through its own `rotation` (written into the details file's item 17). As first written
    the plates used `LAID_BRACKET` itself, a quarter turn about a horizontal axis, under which
    the bracket's footprint is the same as under the inverse turn, so they passed a check
    with the transposed matrix; the review found it, and decision 14 replaces that rotation.
11. **The tolerance of the "a hundredth from its figure" test.** The built footprints keep
    their points to 0.001 mm (`mesh._footprint`), so the distance the code measures differs
    from the script's by up to 0.00043 mm on the rotation plates. Chosen: that test allows
    0.001 mm. The set's 0.01 mm step covers it.
12. **Item 17's place in "To be built".** CLAUDE.md says a built item's text moves into the
    body. Chosen: its text moved to a new body section, and item 17 keeps its number with a
    two-line pointer saying what remains for items 1 to 4 (running the plates through
    `POST /slices`), so items 1 to 18 keep their numbers.
13. **The `plate.py` docstring.** It pointed a user interface at
    `tests/fixtures/plate_cases.json` and said "student". Changed to point the wizard at the
    shared set and to say "user". `plate_cases.json` stays, as `tests/test_plate.py`'s own
    cases. `tests/test_plate.py`'s own docstring, which still called those cases the ones a
    user interface's twin is tested against, was brought into line after the review.
14. **The rotation plates' turn.** The contract asked only for "the bracket laid on its hull
    face by `rotation`". Chosen: `LAID_BRACKET_TURNED`, the contract example's rotation
    followed by 30 degrees about the vertical (`[0.683012702, -0.669818101, 0.226591507,
    0.183012702]`), at `angle` 15. Reason: a plate must tell the contract's turn from its two
    usual mistakes. Under this rotation the turned bracket's box is 50.59 x 15.19 mm, under
    its inverse 41.48 x 33.20 mm; the nonzero angle makes "angle after the rotation"
    (`Rz(angle) M`) differ from "angle first" (`M Rz(angle)`). The test
    `test_the_rotation_plates_tell_the_contracts_turn_from_a_wrong_one` runs both mistakes and
    requires another answer on one of the two plates; with `w = -w` in the test's matrix, or
    in the script's, the suite now fails. The contract's example plate keeps `LAID_BRACKET`.
    To overrule: change the two constants in the script and regenerate; the test says
    whether the new turn still tells the mistakes apart.
15. **Declined from the review: margin plates on the other three edges** (minor finding 1).
    The margin plates try only the left edge, so a check without the upper bound in x or
    either bound in y passes the set. Not changed: one failing plate can catch the loss of
    only one of the four bounds, so the fix is three more plates, which changes the contract's
    table of one passing and one failing plate per rule and its list of thirteen files, read
    by the wizard's builder now; this batch was asked to stay small. The slice service's own
    cases (`tests/fixtures/plate_cases.json`, with plates crossing the left and the top
    margin) catch a check without its upper bound, as the review found; the wizard's own
    tests must cover the other edges until the set does. To overrule: add `margin-right-fail.json`,
    `margin-bottom-fail.json` and `margin-top-fail.json` to the contract and the script.
16. **Declined from the review: a height plate closer than 1 mm** (minor finding 2). The
    contract's table fixes the two posts at 340 and 341 mm, so a height tolerance under 1 mm
    is not caught by the set; it stays under Targets missed. To overrule: change the
    contract's posts (for example to 340.01 mm) and regenerate.

## Targets missed

1. The contract asks for every plate 0.01 mm from its rule's figure; the height plates are
   0 mm (`post-340.stl`, exactly 340 mm tall) and 1 mm (`post-341.stl`) from the 340 mm
   figure, because the contract's own table fixes those two posts. The contract now says so.
   So the set does not catch a height check with a tolerance anywhere below 1 mm.
3. The margin plates try only the left edge of the printable area (decision 15): the set
   does not catch a check that loses the right, front or back bound.
2. The slice service's check agrees with the script's exact distances only to about
   0.0007 mm (its footprints are rounded to 0.001 mm), not to the 1e-6 mm tolerance it
   decides each rule with; on the set that is 0.00043 mm at most, inside the 0.01 mm step.

## Not done

1. Running the plates through `POST /slices` after uploading their parts: it needs items 1
   to 4 (the user key, the part store, parts named by hash); it is left in item 17 of "To be
   built" for their builder.
2. Placing the rotation plates through the slice service's own `rotation`: it needs item 4.
3. The wizard's side of the agreement: the wizard's builder's batch.

## For the owner to look at

- The plates: [contracts/examples/placement/](../../../../contracts/examples/placement/).
- Rewrite the set and see that nothing changes:
  `uv run --project slice python slice/scripts/make_placement_parts.py` then `git status`.
- Run the set's tests: `make -C slice test` (or only
  `slice/.venv/bin/pytest slice/tests/test_placement_plates.py`).
