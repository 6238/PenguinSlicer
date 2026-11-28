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
   on". Chosen: every row keeps the stored step when the reload is the page's own, the slice
   followed, shown or found expired there. To overrule: `toPreview` in `comeBack`.
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
