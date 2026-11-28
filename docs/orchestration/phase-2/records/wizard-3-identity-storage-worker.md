# Batch wizard-3-identity-storage-worker: the record

Items 5, 6 and 7 of [the wizard's details, "By phase", phase 2](../../../../wizard/README-details.md#phase-2-one-machine):
who the user is and the configuration, the browser's storage, and the worker reading a binary STL
and drawing a part's picture. Built on Sat 2026-11-28 by one builder, with no one to ask. What is
built is described in the details file's sections
[The current group](../../../../wizard/README-details.md#the-current-group),
[The configuration and the table of settings](../../../../wizard/README-details.md#the-configuration-and-the-table-of-settings),
[What the browser keeps](../../../../wizard/README-details.md#what-the-browser-keeps),
[The geometry, in a worker](../../../../wizard/README-details.md#the-geometry-in-a-worker) and
[What the wizard reports about itself](../../../../wizard/README-details.md#what-the-wizard-reports-about-itself).

## Decisions made

1. **The configuration's name is plain text for every user in phase 2.** To decide: what the
   header shows for a user in several groups, which the development identity's `/api/me` example
   is. The documents put the group details and choosing a group in phase 3 and say nothing of phase
   2's header for such a user. Chosen: plain text, the current group being the first of the user's
   groups. Reason: the button would open group details that phase 3 builds. To overrule: build the
   group details in phase 2.
2. **Which group a tab works in.** To decide: the order among the tab's own plate's group, the
   stored `currentGroup` and the first group. The documents say a refreshed tab "goes on with its
   own group" and a new tab starts in the stored choice; they give no order. Chosen: the tab's own
   plate's group while `/api/me` lists it, then the stored `currentGroup` while listed, then the
   first. Reason: a refresh must not move a tab to another group's plate. To overrule: change
   `begin` in `wizard/src/storage.js`.
3. **A part's bytes are a record of their own.** To decide: how the *proposed* record
   `plates/<plate_id>` holds the parts' bytes. The details put the bytes inside the plate's record.
   Chosen: `part-bytes/<plate_id>/<sha256>.<units>`, one record a part, beside the plate's record.
   Reason: every change of layout or settings is written at once, and rewriting up to 190 MB of
   bytes each time would be slow and wasteful. To overrule: fold the bytes back into the plate's
   record in `wizard/src/storage.js`.
4. **The storage's names, settled.** The details marked them *proposed*. Chosen: IndexedDB database
   `penguinslicer`, object store `records`; keys `owner`, `uploadUnits`, `currentGroup`,
   `plates/<plate_id>`, `part-bytes/…`; the tab's `sessionStorage` key `penguinslicer.plate_id`; the
   lock `penguinslicer-plate/<plate_id>`. A plate record carries `format` 1 and `last_used_ms`.
   Reason: short, and nothing else on the address uses them. To overrule: rename in
   `wizard/src/storage.js` before any real user stores a plate.
5. **The storage module is `storage.js` (`createStorage`), not `store`.** The details proposed
   `store`. Reason: `wizard/src/state.js` already has `createStore`, the panel's store, and one name
   must mean one thing. The seam is `wizard/src/seams/browser-storage.js`, since the build puts
   every file flat and two `storage.js` would collide. To overrule: rename both.
6. **A plate of an unknown `format` is left alone.** The documents are silent on a stored plate a
   later release wrote. Chosen: never taken up and never dropped by a page that cannot read it.
   Reason: an older page must not destroy a newer page's work. To overrule: drop such plates.
7. **A part whose bytes were refused is gone after a refresh.** The guide says "a refresh will lose
   it" and no more. Chosen: the plate keeps the part's entry marked `saved: false` while the page
   lives, and a page taking up the plate drops entries without bytes. To overrule: keep the entry
   and ask the user to add the file again.
8. **A browser that will not open its storage.** The documents speak of a refused write, not of a
   storage that will not open. Chosen: the page works from its memory, with one `storage_refused`
   report, and every later write is silently not made. Reason: the page stays usable. To
   overrule: show a message.
9. **A refused write of the plate itself** gives one `storage_refused` report for the page,
   however many writes fail; a refused part gives one report for that part. The documents speak
   only of a refused part. Reason: the log should not fill from one full disk.
10. **No Web Locks.** A page served over plain HTTP from another machine has no `navigator.locks`;
    the documents are silent. Chosen: the tab keeps its own plate through a refresh and never
    takes up another, and plates are dropped after 12 hours with no way to see they are held.
    Reason: two tabs must never share a plate. To overrule: serve the page only over HTTPS or
    localhost.
11. **A duplicated tab begins a plate of its own.** Chrome copies `sessionStorage` when it
    duplicates a tab; the documents are silent. Chosen: the copy finds the plate's lock held by
    the original and begins a new plate. Reason: "one tab never writes over another's work".
12. **Taking up a plate counts as using it.** The documents speak of "the time last used". Chosen:
    `last_used_ms` moves on when a tab takes the plate up and at each change. Known gap: during a
    refresh the browser releases the tab's lock for a moment; a second tab opening in exactly that
    moment could take the plate up, and the refreshed tab would then begin a new one. Reason: the
    window is a fraction of a second and the cure (a lock held across navigations) does not exist.
13. **The words of a choice gone from the configuration.** The guide says "a notification says
    which" and gives no sentence. Chosen, in amber: "PETG-CF is no longer in the configuration." or
    "Fine is no longer offered for PETG.", then "The plate now uses PETG · Standard." The same
    notification shows when a page opens on a stored plate whose choice has gone. The user's
    changes are kept. To overrule: change the three sentences in `wizard/src/sentences.js`.
14. **A failure on opening is a notification.** The documents say how phase 3 handles
    `front.not_signed_in`, not how phase 2 shows a failure of `/api/me`, the configuration or the
    table. Chosen: the report's sentences as a red notification on the Parts step; an answer of a
    shape the page cannot use is `wizard.bad_answer` with the fault in `detail`; when `/api/me`
    fails nothing is stored and nothing is asked for a group. To overrule: show a message in place
    of the step, as phase 3 does for a failed sign-in.
15. **The table of settings is asked before `/api/me`, at once.** The contract says "when the page
    opens, beside the configuration". Chosen: the table first, `/api/me` straight after, the
    configuration once the group is known. Reason: the table acts for no group and is the
    largest answer.
16. **The failure reports are built now, ahead of item 18.** The storage's two failures need them.
    Chosen: `wizard/src/reports.js` with the failure reports only, `REPORTS_PER_MIN` settled at 4 in
    any 60 seconds (the details' proposal), `software_3d` known by whether a WebGL context asked to
    fail on a major performance caveat is refused, `browser` from the brands or the user agent. The
    drawing summaries are left to item 18. To overrule: change the figure in `reports.js`.
17. **A part's picture is drawn in the worker, in software.** The documents say the worker reads a
    part for drawing and the row shows its picture; the mockup draws pictures with WebGL on the main
    thread. Chosen: a small rasteriser in `wizard/src/geometry/picture.js`, the mockup's camera,
    lights and colours, a fixed exposure of 0.72 so a lit face is near the part's colour rather
    than white, 2 by 2 samples a pixel, a transparent ground. Reason: a browser gives a page only
    a few WebGL contexts, and drawing 150,000 triangles on the main thread could hold it; this takes
    18 ms in the worker. To overrule: draw with three.js in an `OffscreenCanvas` in the worker.
18. **The picture shows the part as modelled,** not as auto-orient lays it. The documents are
    silent. Reason: the row names the file the user added; how it lies is the Layout step's. To
    overrule: pass the turn to the `picture` message.
19. **A part's colour is the mockup's palette by its place on the plate,** in turn (`PART_COLOURS`).
    The documents are silent. To overrule: change the palette.
20. **A part's bytes are copied to the worker, never transferred.** The page keeps them for the
    storage and the upload. Cost: one copy of up to 7.5 MB for each part read.
21. **A worker that fails as a whole** answers every question waiting, and every later one, with
    `wizard.layout_failed`. The documents are silent. Reason: no question may wait for ever.
22. **The page is marked `data-opened`** once the opening ends, and the browser tests and the
    `look` script wait for it; the requests the opening made are counted apart. Reason: the opening
    sets the store, and a test that set it first would race with it.

## Targets missed

None.

## Not done

- The amber line on a part's row when its bytes could not be saved: the rows are item 8. The
  storage module gives the row its `saved` flag and the sentence `PART_NOT_SAVED`.
- The notification of a part the page cannot draw, and its `part_not_drawable` report: item 8. The
  worker's report and the main thread's never being held while it arrives are built and tested.
- Choosing a group, the group details and the fall-back on `front.group_not_allowed`: phase 3.
- The records `signInTrip` and `selfReload`: phase 3 and item 17.
- The drawing summaries of the page's reports: item 18.
- How often a browser refuses or clears the storage with several tabs' full plates, in Chrome on the
  Mac and in real use: only one tab's full plate was stored, in headless Chromium.
- The second run of the browser tests in Edge.

## For the owner to look at

- The pictures of each kept part as its row will show it, at 88 pixels (44 at twice the density):
  [docs/orchestration/phase-2/look/wizard-3/](../../look/wizard-3/).
- `make -C wizard test` and `make -C wizard test-browser`; the new tests are
  `wizard/tests/storage.test.js`, `wizard/tests/opening.test.js`, `wizard/tests/reports.test.js`,
  `wizard/tests/geometry/picture.test.js`, `wizard/tests/geometry-client.test.js`,
  `wizard/tests_browser/test_storage.py` and `wizard/tests_browser/test_worker.py`.
- With the three components started as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says: the header reads "Config: PenguinSlicer default"; a second tab gets its own plate; a
  refreshed tab keeps its step; a closed tab's plate is taken up by the next tab opened.
