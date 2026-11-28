# Phase 2, batch check-last-fixes-wizard: a second look at the wizard's last fixes

The builder's record of the batch that looks again at the fixes for the wizard's third-round
blocking findings, which merged without a further review. Written on Sat 2026-11-28 (Pacific
time) on branch `phase-2/check-last-fixes-wizard`, from `origin/main` at the start of the batch.

For each finding: the fix was found on `main`, the fix was undone by hand, the suite named was run
and seen to fail, and the fix was restored (the working tree checked clean with `git status` after
each). "Fixed and tested as found" means the code was right and a test fails without it. The
browser tests were run in Chromium 159 with `wizard/tests_browser`, after `make -C wizard build`.

## The findings

### Pull request 27 (wizard-1b-trial-geometry, [its record](wizard-1b-trial-geometry.md), decisions 27 and 28)

1. **Auto-orient's stability rule was untested: fixed and tested as found.** With `c.stable &&`
   removed from the filter of counted candidates in `geometry/orient.js`, "the cheapest way to
   rest is passed over when the part would tip over from it" fails, and no other test.
2. **"The coarse outline holds the hull" was untested: fixed and tested as found.** With
   `simplified` in `geometry/outline.js` returning every fourth hull corner (the reviewer's
   mutation), "two round parts too close are found in every direction, between the coarse
   outline's corners too" and "the coarse outline holds every corner of the footprint it stands
   for" fail. Arrange marks its map from `grown(fp.coarse, …)`, so the second test holds what
   Arrange depends on too.

### Pull request 33 (wizard-2-skeleton-panel, [its record](wizard-2-skeleton-panel.md), decisions 33 and 34)

3. **No test checked that the browser's transport reports the body's progress: fixed and
   tested as found.** With `onProgress` dropped from `bytes` in `seams/transport.js`, "the
   browser's transport tells of each part of the body through text and bytes" and "the page's
   requests through the browser's transport read a slow body in one attempt" fail; with it
   dropped from `text`, the first fails.
4. **No test checked that the attempt timer starts again when the headers arrive: fixed and
   tested as found.** With the `arm()` before the body is read removed from `attemptOnce` in
   `api.js`, "the attempt's 15 s start afresh when the headers arrive: late headers, then a late
   first part, are one attempt" fails.

### Pull request 40 (oracle-offered-faces, [its record](oracle-offered-faces.md), decision 16)

5. **The even-odd search was quadratic: fixed and tested as found; measured afresh.** With the
   ray kept along x (`alongY = false` in `firstLayerHoldsALine`), "the inside of a section of
   long finely cut strips is found with work in proportion to it" fails. Measured from the STL's
   bytes to the best way (read, `analysePart`, `autoOrient`), in two sessions of six runs for each
   strip part (eleven on Node, the first session's warm-up run left out) and one session for the
   hub, on this machine shared with other builders (8 processors), against `AUTO_ORIENT_MS`
   (1,000 ms):

   | Part | Triangles | Faces step 5 drops | Node 24 | Chromium 159, module worker |
   |---|---|---|---|---|
   | Twelve-pointed star prism (radii 50 and 30 mm, 100 mm long), sides cut into 3,000 strips | 144,048 | 12 | 290 to 494 ms | 244 to 372 ms |
   | The L of `first-layer.test.js`, 100 mm long, sides cut into 12,000 strips | 144,008 | 1 | 153 to 192 ms | 171 to 940 ms (one run of twelve; the others 171 to 229 ms) |
   | A saw bar of 20 pointed teeth, 100 mm long, sides cut into 1,700 strips | 146,282 | 1 | 252 to 333 ms | 214 to 550 ms |
   | `hub-150k.stl` (no face dropped), for comparison | 150,000 | 0 | 163 to 211 ms | 153 to 669 ms |

   Every run is within the target. The fixer's 0.2 to 0.4 s holds for the typical run; the
   slowest runs in Chromium (0.94 s once, 0.67 s on the hub, which drops nothing) are spikes of a
   shared machine, not of the search. The guide's and the details' Auto-orient rows said no
   browser had measured such a part; they now carry these figures.
6. **A triangle doubled or missing near the plate kept the bridging face: fixed and tested as
   found; compared afresh with the slice service.** With `section` returning the cuts unjoined
   (`cuts(…)` in place of `rings(cuts(…))`), "a triangle doubled or missing near the plate breaks
   a ring of the section, as the slice service takes it" fails. Compared on 57 parts written as
   binary STL files by a throwaway script outside the repository, every one read by both sides
   from the same bytes: the eight real parts; the L, inside out, twice over, with five of its
   triangles doubled and five removed; the star prism plain and cut into 3,000 strips; a sharp
   20-pointed star; the L cut into 12,000 strips; the saw plain and cut into strips; two rods, and
   twice over; ridges at 20, 30, 60 and 87 degrees; a box plain, turned 31 degrees, tilted
   0.005 mm, its corners jittered by 0.01 mm and by 1 mm, a bottom triangle wound backwards, a side
   triangle missing, a zero-area triangle added; three nested boxes; two boxes along one plane; two
   meeting at a corner; two overlapping by 0.3 mm and by 5 mm; cylinders of 48 and 7 facets; a tube
   and a tube 0.25 mm thick; a cone; a sphere; a pyramid; a wedge and a wedge 0.5 mm thin; a
   leaning post; and 200 random triangles. For each, every hull face that reaches step 5, every
   bounding-box patch and the six axis directions, laid as a click lays it
   (`instanceTurn(layFor(normal), 0)`): the wizard's `restsOnNoFace` against the slice service's
   own `contact_area_mm2 < REST_AREA_MM2 and first_layer_section(…).buffer(-line / 2).is_empty`,
   run from the slice project's environment with the default first layer. 753 poses of 56 parts:
   137 rest on no face by both, 616 stand by both, none differs. The slice service refuses the 200
   random triangles (`slice.part_no_volume`: loose triangles that enclose nothing), so their 24
   poses were not compared.
7. **The guard "inside on neither side" was untested: fixed and tested as found.** With a segment
   that is inside on neither side kept with its first normal, and kept with its other normal, "a
   segment with the section on neither side of it is no edge to lay a line against" fails each
   time.
8. **The oracle again, with the real Orca:** `slice/tests_orca/test_offered_faces.py` under the
   real-Orca lock, 57 passed in 82 s: every one of the 56 offered poses of the eight real parts
   sliced (0.5 to 1.6 s each). The committed poses file matches the code (the wizard's fast test
   `offered-faces.test.js` passes).

### Pull request 43 (wizard-5b-layout-step, [its record](wizard-5b-layout-step.md); checked by [wizard-9](wizard-9-back-reload-reports-whole.md))

9. **Arrange's message counted an instance dragged away from beside the plate: fixed and tested
   as found.** With the filter by `besideId` in `shownNote` keeping every instance, "Arrange's
   message counts only the instances still waiting beside the plate…" and "a lay-down's message
   about an instance beside the plate goes once the user drags that instance" fail.
10. **A part joining a full plate was never tested to wait beside it: fixed and tested as
    found.** With `markParked` in `join` marking nothing, "a part joining a full plate waits beside
    it and has its own message with Arrange" fails.
11. **The guide and the details disagreed about a page opened again: fixed as found.** Read side
    by side, the guide's "A page opened again cannot tell who put an instance beside the plate"
    and the details' paragraph on the Layout step's messages say the same. Wizard-9's check is
    confirmed on all three.

### Pull request 46 (wizard-8-result-expiry-send, [its record](wizard-8-result-expiry-send.md), decisions 36 and 37)

12. **A followed stored slice's plate configuration had no test: fixed and tested as found.**
    With `resume(kept)` in place of `resume(kept, built.configuration)` in `comeBack`, "a page that
    follows the plate's stored slice to done has the Send step's card, and Download saves and
    notifies once" fails.
13. **The summary asked after a bare done report was not set aside once a new slice had begun:
    fixed and tested as found.** With `mine !== run ||` removed from `askDetails`, "a summary asked
    after a bare done report and arriving after a new slice has ended is set aside…" fails. A new
    slice still running when the old summary arrives is set aside by `view.kind !== 'done'`.

### Pull request 47 (wizard-9-back-reload-reports-whole, [its record](wizard-9-back-reload-reports-whole.md))

14. **The layer preview's second use was not measured afresh: fixed and tested as found.** With
    `stats = createFrameStats();` removed from the layer preview's `beginUse`, the Chromium test
    `test_a_second_use_of_the_layer_preview_is_timed_from_its_own_opening_and_measured_afresh`
    fails (`0.7 > 0.7`); with `holds.start()` removed there, it fails (`1500 < 1500`).
15. **The Layout view's second use carried the first's longest hold: fixed and tested as
    found.** With `holds.start()` removed from the Layout view's `beginUse`,
    `test_a_second_use_of_the_layout_view_measures_its_figures_afresh` fails at the first use
    (`0 >= 1000`); with it started on the first use only, it fails at the second (`1010 < 1010`),
    which is the finding itself.
16. **Coming back to an expired slice on the Send step, nothing tested stopped a later slice by
    itself from the Preview step: fixed and tested as found.** With `|| stored === 'send'` removed
    from `expiredBack` in `comeBack`, "an expired sliced file, the page on the Send step: the
    expired message with Slice again, and nothing sliced by itself" fails.

### Carried open by the last wizard batch

17. **The selection line counted an instance dragged wholly off the plate as on it: fixed in
    this batch.** "1 instance on the plate." was said of a spacer the user had dragged to
    x = 420 mm on the 340 mm plate, and an existing test pinned it. See decision 1.

## Decisions made

1. **The selection line counts an instance the user dragged wholly off the plate in neither
   count.** The guide gave the line as "90 instances on the plate, 10 beside it." and was silent
   on an instance the user drags off; wizard-5b declined to change it, since "beside it" names
   the instances the wizard put there and a third count is a sentence neither the guide nor the
   mockup has. I chose to keep both counts and their wording, and to count such an instance in
   neither: the line then says nothing false, uses no new sentence, and the instance's own
   message ("… is not fully on the plate: it crosses the right edge.") names it in the same
   panel. Wholly off means its footprint's box lies past any edge of the plate; partly across an
   edge it is still counted on the plate. The two counts no longer always add up to the
   instances shown. Test first: the new test "the selection line counts an instance the user
   dragged wholly off the plate neither on the plate nor beside it" (all four edges) and the
   changed assertion in Arrange's message test ("1 instance on the plate, 1 beside it.") failed
   before the change; the test also fails with any one edge left out of `whollyOffPlate`. The
   guide and the details say so. To overrule: return to counting every instance not beside the
   plate as on it in `selectionLine` of `wizard/src/layout.js`, or add a third count, which needs
   a sentence in the guide.
2. **The earlier batches' records are left as written.** The oracle-offered-faces record says
   no browser measured a large part whose faces step 5 drops, and wizard-5b's and wizard-9's list
   the selection line under "Targets missed". Those records are each builder's account of their
   own batch, so this record says what is true now and the living documents (the guide's and
   the details' Auto-orient rows, the selection line's row and paragraph) were brought into
   line. To overrule: add a line to each earlier record pointing here.
3. **The comparison with the slice service and the timing ran from throwaway scripts outside the
   repository**, as the task says, and nothing of them was committed. The 57 parts are made by
   code from `wizard/tests/geometry/shapes.js`; the comparison found no difference, so there was
   no new case to pin with a test. To overrule: commit the comparison as a test of the slice
   project that reads poses the wizard writes, which would add the slice service's environment
   to a wizard check.

## Targets missed

None.

## Not done

None.

## For the owner to look at

- The selection line with an instance dragged off the plate: on the Layout step with two
  instances, drag one wholly past an edge and click the empty plate to clear the selection; the
  line under the view reads "1 instance on the plate." while that instance's red message names
  it.
- The oracle, about 80 s:
  `flock /var/tmp/penguin-locks/real-orca.lock slice/.venv/bin/python -m pytest -s -p no:randomly slice/tests_orca/test_offered_faces.py`.
