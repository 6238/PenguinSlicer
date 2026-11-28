# Batch wizard-9-back-reload-reports-whole: the record

This batch builds items 16, 17 and 18 of
[the wizard's details, "By phase", phase 2](../../../../wizard/README-details.md#phase-2-one-machine),
and checks the wizard's phase 2 as a whole:

- 16, coming back: every row of the returning page's table that phase 2 can meet;
- 17, reloading for a new version;
- 18, the reports about itself: every failure, the handler for uncaught errors and rejected
  promises, and the drawing summaries of the Layout view and the layer preview.

It was built on Sat 2026-11-28 (Pacific) by one builder, with nobody to ask. What is built is
described under "As built" in four sections of the details file:
[When a user comes back](../../../../wizard/README-details.md#when-a-user-comes-back),
[Reloading for a new version](../../../../wizard/README-details.md#reloading-for-a-new-version),
[What the wizard reports about itself](../../../../wizard/README-details.md#what-the-wizard-reports-about-itself)
and [The Layout step](../../../../wizard/README-details.md#the-layout-step) (the view's lost
context and its measuring). The guide's
[What is to be built, by phase](../../../../wizard/README.md#what-is-to-be-built-by-phase)
describes the same in plain words.

**Phase 2 as a whole.** Items 1 to 18 were read against the code and against every record of the
wizard's batches (wizard-0 to wizard-8) and
[the record of the offered faces](oracle-offered-faces.md). Each "Not done" that named a later
item was checked:

| Left by | What | Where it stands |
|---|---|---|
| wizard-3 | `selfReload` (item 17) | Built, kept in the tab (decision 8) |
| wizard-3 | The handler for every uncaught error and rejected promise, and the drawing summaries (item 18) | Built |
| wizard-3 | A worker's `wizard.layout_failed` answer reported, told apart from the page asking wrongly | Built: the worker's answer carries `fault` (decision 16) |
| wizard-3 | A notification for a page whose opening throws | Not built: no sentence exists ("Not done") |
| wizard-4 | A part's instances joining the plate on the Layout step | Built by wizard-5b |
| wizard-5b | The Layout view's drawing summaries (item 18) | Built |
| wizard-6, wizard-8 | Coming back (item 16) | Built |
| wizard-7, wizard-8 | Sending the drawing summary (item 18) | Built |
| wizard-1a | Requirement 2, a view that draws again after a lost context, for the Layout view | Built in this batch, with a test that loses the context twice |
| oracle-offered-faces | `slice.rests_on_an_edge` with Back to Layout and no Slice again | Built by wizard-6, tested |

The three findings of the Layout step's last review that were fixed without a further look were
each checked by breaking the fix by hand: Arrange's message counting an instance dragged away
from beside the plate (the filter by `besideId` replaced by one that keeps every instance: two
tests fail); a part joining a full plate waiting beside it (`markParked` in `join` made to mark
nothing: its test fails); the guide and the details on a page opened again (read side by side:
they now say the same). The test of a lay-down answered before the worker returns the faces is
there and fails when the patches are answered without waiting for the faces (checked by hand).
All three fixes stand.

One gap between batches was found and closed: a page loaded before a deploy started the layer
preview's worker by its file name only when a sliced plate was shown, and the new front server
answers `404` for an old name, so the first preview after a deploy failed. The worker is now
started when the page loads (decision 18), with a browser test that takes the files away from the
server after the page has loaded.

## Decisions made

1. **A returning page told `cancelled` `replaced`.** The table says the page follows the later
   slice job "whose id the stored plate already holds"; but the stored plate holds only the latest
   id the page knows, so this answer reaches a returning page only when the acceptance of a later
   slice job was lost to the refresh. Silent on what to do then. Chosen: the plate as it stands is
   submitted again, with a new `submission_id` and no line about a restart. Reason: it is the only
   way to a slice of the plate as it stands; following an unknown job is impossible. To overrule:
   the `cancelled` branch of `comeBack` in `wizard/src/slicing.js`.
2. **"The page uploads the parts again" when the slice service restarted.** Chosen: the plate is
   submitted again, and the parts are uploaded only when the slice service answers
   `slice.part_missing`, as for any submission. Reason: the outcome is the same, and a slice
   service that kept its part store is sent nothing twice (up to 190 MB). To overrule: upload each
   part before `slice({restarted: true})` in `comeBack`.
3. **A plate stored on the Send step with no slice of the plate as it stands.** The table is
   silent. Chosen: the Preview step opens, which slices the plate. Reason: the Send step has
   nothing to send. To overrule: the first branch of `comeBack`.
4. **Which stored slice counts.** Chosen: only one whose fingerprint is the plate's as it stands
   now; any other counts as "no slice job" (the table's second row) and nothing is asked. Reason:
   the Preview step already works this way, and a slice of an older plate is not the user's
   current work. To overrule: `usable` in `comeBack`.
5. **A returning page on the Send step with a finished slice.** The table says the Preview step
   with "ready to send"; chosen as written, though it moves a user who refreshed on the Send step
   back a step. To overrule: the `done` branch of `comeBack`.
6. **The page's own reload, whatever the row.** The details say it reopens "on the step it was
   on". Chosen: every row of a slice job keeps the stored step when the reload is the page's own,
   the slice followed, shown or found expired there. The one exception, settled at the review: a
   plate stored on the Send step with no slice of the plate as it stands opens the Preview step
   even after the page's own reload (decision 3), since the Send step has nothing to send; the
   guide and the details now say so. To overrule: `toPreview` and the first branch of `comeBack`.
7. **Any other refusal of the asking** (a `403`, an unknown code) or an answer that is not a
   progress report of this slice job. Silent. Chosen: the Preview step with that error report,
   or the wizard's `wizard.bad_answer`, with the failure's buttons. Reason: every failure a caller
   can see is an error report, and the Preview step is where a slice's failures show.
8. **Where the mark of the page's own reload is kept.** The details proposed a record
   `selfReload` in the browser's storage. Chosen: `penguinslicer.self_reload` in the tab's
   `sessionStorage`. Reason: the browser's storage is shared by every tab, so a tab opening at the
   moment another reloads could take the mark as its own; the tab's storage survives a reload, dies
   with the tab, and works when the browser refuses its storage. To overrule: `markSelfReload` and
   `begin` in `wizard/src/storage.js`.
9. **Which versions are compared.** Chosen: only versions of the contract's form
   (`YYYYMMDDTHHMMSSZ-<commit>`); one of any other form is never newer, and a page that does not
   know its own version (no `<meta>`) never reloads. Reason: without it a page served without its
   version would reload at every step. To overrule: `isNewer` in `wizard/src/reloading.js`.
10. **A move between steps made while a request is pending.** Chosen: the reload is made when the
    last request ends, unless the user has interacted since the move; then the next moment (120 s
    without input, or the next move) does. Reason: the reload must not come under a user who is at
    work on the new step. To overrule: `onSettled` in `createReloader`.
11. **What counts as interacting.** Chosen: pointer movements and presses, keys, the wheel and
    scrolls, on the window, in the capture phase. To overrule: `onInput` in `main.js`.
12. **A use of a view with no frame drawn while it moved, or no first layer drawn.** The
    contract's fields are required numbers and the front server refuses `null`. Chosen: no summary
    is sent for such a use. Reason: the contract has no way to say "not measured", and inventing a
    figure is forbidden. To overrule: a contract change making those fields optional.
13. **When a drawing summary is sent.** Chosen: when the user leaves the step; none when the tab
    closes. Reason: the contract says "sent when the user leaves the view", and a report on closing
    would need `sendBeacon` or `keepalive`, outside the module that makes every request.
14. **A second use of the layer preview already drawn.** Chosen: coming back to the Preview step
    on the same sliced plate begins a new use: its figures are measured afresh, and its first layer
    is timed from that opening to the next frame that draws toolpaths. To overrule: `beginUse` in
    `wizard/src/panel/layer-preview.js`.
15. **"A page that is not signed in drops its reports."** The module takes `signedIn()`, tested;
    `main.js` leaves it at its default in phase 2, since the development identity is always
    signed in and a report sent without a sign-in is refused `401` and dropped. Reason: the
    opening's own reports come before the store knows the user, and would be lost. To overrule:
    join it to the sign-in in phase 3.
16. **How the worker tells its own failure from the page's.** Chosen: its failed answer carries
    `fault` (`part`, `page` or `layout`) beside the error report, not in it, since the error
    report's shape is the contract's; the worker's client reports `page_failed` or
    `layout_failed` once for each such answer, with the part's hash when the question named a part.
17. **The Layout view at rest.** The details said coarse copies at rest from 500,000 triangles.
    Chosen: from 250,000, as while moving. Reason: the main thread's hold at the start of a drag
    (measured under "Targets missed"): a press draws two frames at rest back to back, and at
    500,000 the real mix drew about 300,000 triangles in each. The cost: a plate between 250,000 and
    500,000 triangles is drawn coarsely at rest, the selected instances whole. Tried and dropped: a
    smaller figure while moving (100,000) raised the frame rate but not the hold, and compiling the
    shaders ahead changed nothing measurable. To overrule: `REST_TRIANGLES` in
    `wizard/src/panel/layout-view.js`.
18. **The preview's worker started when the page loads.** Chosen: one worker is started with the
    page and kept idle; each one taken starts the next, whose files the browser has in its cache
    under the same names. Reason: the contract requires that the page fetch nothing later by name,
    and the worker was fetched only when a sliced plate was shown. The cost: one idle worker always
    alive (its code only). To overrule: `wizard/src/seams/preview-worker.js`.
19. **The Layout view after a lost context.** Chosen: three.js's renderer keeps the context
    restorable; the view reports `drawing_context_lost` and draws again when the context comes back.
20. **The detail of an uncaught error.** Chosen: `uncaught: <name>: <message> at <path>:<line>:<column>`,
    the path without the front server's address; for a rejection, `unhandled rejection:` with the
    error's name, message and the first three lines of its stack. Never a part's name: the page's
    own code names parts by hash in its errors.
21. **The "Back where you were" notifications.** Chosen: kind `info` (the mockup's), one key for
    both, and they stay until the user closes them or leaves the step, like any notification; the
    guide says only the print's notification goes when the print ends.

22. **The page's own reload when it would lose work** (settled at the review, finding 1). A part
    whose bytes the browser refused lives only in the page's memory, and with the storage refused
    the whole plate does; the next load drops them. The guide says the reload reopens "with the
    parts, the layout, every change" and the plan's standing requirement says a deploy interrupts
    no user; no document decides this case. Chosen: no reload while a reload would lose work
    (`reloadKeepsWork()` in `wizard/src/storage.js`: the storage open, the plate's last write
    stored, no part kept only in memory). `markSelfReload` reads it after every write asked for is
    done and resolves to `false` without setting the mark; the reloader then makes no reload and
    asks again at the next moment (the next move between steps, or 120 s after the next input).
    Nothing is said, since the part's amber line already says a refresh will lose it. Reason: a
    reload the user did not ask for must never lose work; the cost is an older page staying open
    against a newer front server for as long as the work is unsaved, which the contract already
    requires to work. To overrule: `markSelfReload` and `reloadKeepsWork` in `wizard/src/storage.js`
    and `go` in `wizard/src/reloading.js`.
23. **What counts as a progress report when coming back** (review, minor finding 3). Chosen: the
    contract's required `job`, `state`, `elapsed_s` and `sequence`, and `job` equal to the stored
    slice's id; anything else is `wizard.bad_answer`. Before the review a report with no `job`
    passed. To overrule: `isProgress` in `comeBack`.
24. **Coming back when the opening throws** (review, minor finding 2). Chosen: coming back catches
    the rejection of the opening (and of the Layout step's readiness) and does nothing, so the
    opening's failure is reported once, by `endOpening`, and never a second time as an unhandled
    rejection. A failure of coming back's own code still rejects, and is reported as `page_failed`.
    To overrule: `cameBack` in `wizard/src/slicing.js`.
25. **The Layout view's lost context reported each time** (review, minor finding 7): the view
    reports `drawing_context_lost` at every loss, held only by `REPORTS_PER_MIN` (4 in any 60 s
    for all of a page's reports together); the browser test loses the context twice and sees two
    reports.

### The review's findings (pull request #47)

Every finding was checked against the code before anything changed.

- Blocking 1, the reload losing unsaved work: real; decision 22, tested in `tests/storage.test.js`
  and `tests/reloading.test.js` on the fake clock.
- Blocking 2, `markSelfReload`'s wait untested: real. The fake records can now hold every write
  (`holdPuts` in `tests/fakes/storage.js`); a test holds the step's write open and sees the mark
  unresolved until it is released. Removing `await writing` fails it (checked by hand).
- Blocking 3, one drawing summary for each use untested: real. `tests/drawing-summaries.test.js`
  builds the Layout step and the Preview step on a small fake document (`tests/fakes/dom.js`) with
  a fake view and a spy on `reportDrawing`, two uses each. Deleting the Preview step's `beginUse`
  line, or the Layout step's `view?.beginUse()` on entering the step, fails them (checked by hand).
- Blocking 4, the check that the answer is about this slice job untested: real; a test in
  `tests/coming-back.test.js` answers with another job's `done` report and fails under the
  reviewer's mutation (checked by hand).
- Minor 1, the future tense at the worker's `fault`: fixed.
- Minor 2, a second `page_failed` when the opening throws: real; decision 24, with a test that
  listens for unhandled rejections.
- Minor 3, `isProgress` not requiring `job` or `elapsed_s`: fixed, decision 23, tested.
- Minor 4, decision 6 and the Send step: the code is right (the Send step has nothing to send) and
  the decision's words were wrong; decision 6, the guide and the details now state the exception,
  with a test of the page's own reload on the Send step with no slice.
- Minor 5, advanced mode after a quiet reload: half right. Advanced mode does reopen after any load
  of a plate stored on the Settings step with it open, the page's own reload included
  (`settings.resume`, tested in `tests/settings.test.js`, "the changes survive a reload ... and
  advanced mode reopens when it was open"), so no code changed; the details credited the wrong file,
  and now name `tests/settings.test.js` and `tests/coming-back.test.js`.
- Minor 6, polling loops in `tests_browser/test_coming_back.py`: the two loops that ran
  `return true;` until a report arrived now wait on the front server's answer to the report
  (`expect_response`). Kept: the loop in the Preview step's summary test, which moves Playwright's
  fake clock by 50 ms until the page's own event (`window.__driven`) has happened; it waits on that
  event and is bounded, as the quality bar allows.
- Minor 7: decision 25.

Declined: none.

### The second review's findings (pull request #47)

Each was checked against the code first; each blocking test was seen to fail under the reviewer's
mutation and pass without it.

- Blocking 1, the views' own new use untested: real. Two Chromium tests in
  `tests_browser/test_coming_back.py` drive the real views. The layer preview: drawn and driven,
  left, a minute (60 000 ms) moved on the fake clock, the Preview step opened again, driven again
  and left; the second summary's `first_layer_ms` is under the minute. With `since = opened;`
  deleted it was 60 608. The Layout view: a first drag held still halfway for 120 animation frames
  (an event counted, not a duration waited), a second use with a drag and no pause; the second
  summary's `fps_worst` exceeds the first's. With `stats = createFrameStats();` deleted both were
  0.5. A use with no frame drawn while moving sends no summary (`reports.js`), so the second use
  must move too: that is why the Layout test compares worst frame rates instead of expecting none.
  The details' Tests line no longer credits `tests/drawing-summaries.test.js` with the real view's
  timing, and names the two new tests.
- Blocking 2, coming back to a report of this slice job in a state the contract does not name:
  real; a test in `tests/coming-back.test.js` answers `paused` and expects the Preview step with
  `wizard.bad_answer`, nothing said and nothing submitted. The details now state the case.
- Blocking 3, New plate letting the reload happen again untested: real; a test in
  `tests/storage.test.js` refuses a part's bytes, presses New plate, and sees `reloadKeepsWork()`
  true and `markSelfReload()` resolve to true.
- Minor 1: the Preview step's summary test now waits on the report's answer (`expect_response`),
  through a helper `drive_layers` shared with the new test.
- Minor 2 and minor 3: the guide's paragraph on a held reload now names the plate's refused last
  write, and says that a page left untouched after its work is stored again waits for the user's
  next move (a move between steps, or 120 seconds after the next input) before it reloads.
- Minor 4: a confirmation, nothing to do.

Declined: none.

## Targets missed

- **The main thread held over 250 ms at the start of a drag at 150 instances** of the real mix:
  0.28 to 0.29 s (three runs of `make -C wizard measure-layout` on Sat 2026-11-28, load average 1.5
  to 4.4), down from 0.39 to 0.47 s in this batch's first runs. It is the two frames at rest a
  press draws back to back (the selection, then its patches): 150 and 133 ms. On 150 spacers 0.21
  to 0.23 s, on 150 of `hub-150k.stl` 0.07 to 0.09 s, both met. Frame rates: 19 to 20 frames a
  second dragging the real mix, 41 to 42 on the hub, 46 to 47 on the spacers (target 10).
- **Carried, not changed by this batch:** the layer preview's hold on `blocks-12-supports`, 0.25
  and 0.34 s in two runs of five (wizard-7's record); the page's memory 992 to 1,016 MiB against
  1,024 (wizard-7); the selection line counting an instance dragged off the plate as on it
  (wizard-5b, declined there).

## Not done

- **Item 19, the previous release's page against the new front server:** it applies from the
  second release on, and there is no previous release yet. Until then a browser test takes this
  release's files away after the page loads and checks that the layer preview still draws.
- **The printer's row of the returning page's table, the last-print note and coming back to the
  Send step's print:** phase 5.
- **A notification for a page whose opening throws** (wizard-3's decision 26): no sentence for it
  exists in the guide; the page is marked failed and reported.
- **`signedIn` joined to the sign-in:** phase 3 (decision 15).
- **A drawing summary when the tab closes** (decision 13).
- **The second run of the browser tests in Edge** (left by wizard-3 and wizard-4): no Edge on this
  machine.
- **A late part's notification in Chromium** (wizard-4): still tested in the fast suite only.
- **The layer preview at the 150-instance limit of large parts** (wizard-7): not measured.
- **A round side of fewer than 18 facets, and a part modelled at an angle to its axes**
  (wizard-1b, oracle-offered-faces): no part kept in the repository has either.
- **The owner's parts:** the renders and the frame rate on the Mac, and a look at each real part's
  chosen orientation.

## For the owner to look at

- `make -C wizard test-browser`: `tests_browser/test_coming_back.py` refreshes a sliced tab (the
  Preview step with "Back where you were. Your plate was sliced and ready to send when you
  left."), reloads the page for a newer version at a move between steps with nothing said, draws
  the layer preview after the page's files are gone from the server, loses the Layout view's
  drawing context twice, and sends an uncaught error and the two drawing summaries.
- `make -C wizard measure-layout`: the figures above, with the triangles of a frame while moving
  and the first frames of a drag, written to
  [frame-rate.json](../look/wizard-5b/frame-rate.json).
- By hand, with the three components started as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says: slice a plate, go back to the Layout step and refresh the tab (the Preview step with "Back
  where you were"); refresh while it slices (the slicing card and "Back where you were. Your plate
  was still slicing when you left; see below."); restart the front server while the page is open,
  then move between steps (the page reloads on the step moved to, with nothing said, since each
  start on one machine is a newer version).
- At rest, a plate between 250,000 and 500,000 triangles is now drawn coarsely but for the
  selected instances (decision 17): whether that looks acceptable is the owner's judgement.
