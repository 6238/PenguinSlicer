# Batch wizard-8-result-expiry-send: the record

This batch builds items 13 (the rest of it), 14 and 15 of
[the wizard's details, "By phase", phase 2](../../../../wizard/README-details.md#phase-2-one-machine):

- the result around the layer preview;
- a sliced plate that expires;
- the Send step, with "Download the sliced file" as its one button.

It was built on Sat 2026-11-28 (Pacific) by one builder, with nobody to ask. What is built is
described in three sections of the details file, each under "As built":
[The result](../../../../wizard/README-details.md#the-result),
[A sliced plate that expires](../../../../wizard/README-details.md#a-sliced-plate-that-expires)
and [The Send step](../../../../wizard/README-details.md#the-send-step). The guide's
[What is to be built, by phase](../../../../wizard/README.md#what-is-to-be-built-by-phase)
describes the same in plain words.

The layer preview's view came from batch wizard-7, and its interface is in
[its record](wizard-7-layer-preview-view.md). The slicing card and the failures came from batch
wizard-6, recorded in [its record](wizard-6-submit-follow-failures.md).

**The whole path.** In Chromium, against the Python fake front server, on the page's own clock,
a user does each step of phase 2:

1. adds two parts;
2. goes through the Settings step;
3. lays the parts out;
4. slices them;
5. sees the layer preview drawn from a real sliced file;
6. goes to the Send step and downloads the file.

This walk is now a test: `test_the_whole_path_on_the_real_clock_parts_layout_slice_preview_and_download`
in `wizard/tests_browser/test_result_send.py`. Building and walking it broke nothing between the
steps. One of its checks found the readout wrapping at 320 px (decision 12).

## Decisions made

1. **How the wizard's expired sentence is cut.** The guide gives one sentence, and a message holds
   two: what happened and what to do. The documents are silent on where to cut. Chosen:
   - what happened: "This plate's slice has expired.";
   - what to do: the rest of the guide's sentence.

   To overrule it, change `EXPIRED_WHAT` and `EXPIRED_TODO` in `slicing-sentences.js`.
2. **Which sentence an unknown slice job shows.** The case is a slice job that the front server
   no longer knows two hours or more after it was submitted. The details said only that the
   expired message replaces the refusal. Chosen: the wizard's sentence, not the front server's
   `front.slice_unknown` sentence. The page itself decides that this case is an expiry, and
   nothing refused the sliced file as expired. To overrule it, change `onRefused` in `slicing.js`.
3. **How the panel hides Send.** The store has a new field, `expired`, and the panel hides
   `#final-action` while it holds. The documents say "in place of Send" and are silent on how. To
   overrule it, change `drawSteps` in `panel.js`.
4. **What Slice again does on the Send step.** It goes to the Preview step, and entering that step
   submits the plate, because the plate is not sliced. So Slice again submits once, with a new
   `submission_id`, from either step. The documents are silent on how this joins the rule
   "entering the step slices". To overrule it, change `sliceExpired` in `slicing.js`.
5. **What follows a refusal of the summary.** The summary is asked when a done report lacks
   the sliced file's details. If it is refused with anything other than "expired", the refusal is
   shown as a failure, with the buttons of the failures' table's last row. The details only say
   to ask. To overrule it, change `askDetails` in `slicing.js`.
6. **When the layer preview is made and kept.** It is made only while the Preview step is in
   sight with a sliced plate. It is kept while the plate stays sliced, so coming back to the step
   neither fetches the file again nor reads it again. It is destroyed by a new slice, by a
   failure, or by the expiry. The documents are silent. The reason: the 5 s target for the first
   layer, and the guide's rule "never stored". The cost: the view's memory stays held while the
   user is on another step. To overrule it, change `drawResult` and `dropView` in
   `panel/preview-step.js`.
7. **A ghost with a part's corners missing.** If the corners of any part are not at hand, the
   preview draws with no ghost at all. The other choice was `wizard.preview_failed`, which the
   view gives for an instance with no corners. A missing ghost is a smaller loss than a missing
   preview. To overrule it, change `ghost()` in `result.js`.
8. **How a failure of the preview is shown.** The documents are silent. Chosen: an amber message
   in place of the view and its row. It is not red, because the plate is sliced and Next stays on.
   It offers Slice again only for `wizard.preview_unreadable`, the one failure that a new slice can
   mend. The print time, the filament and the quiet line stay on the step. To overrule it, change
   `viewFailed` in `panel/preview-step.js`.
9. **Progress while the file is read.** The readout's place says "Reading the sliced file", and
   adds the worker's percentage while it reads the G-code. The standing requirement "Progress"
   asks for this; the documents name no words or place. To overrule it, change `READING` in
   `result-sentences.js`.
10. **The quiet line has no layer height.** The mockup writes "134 layers of 0.3 mm". No field
    that the page is given holds the layer height, and the guide lists only the instances, the
    layers and how long the slice took.
11. **Where the warnings go.** They are an amber list under the quiet line, each sentence as
    text. The mockup drew no warnings. To overrule it, change `.result-warnings` in
    `css/wizard.css`.
12. **How the readout stays on one line at 320 px.** The guide requires one line; the mockup's
    readout wraps at 320 px. Below 480 px of panel, three things change:
    - the row's gaps go from 6 px to 4 px;
    - the spacer gives way to Reset view's own margin;
    - the two small buttons go from 28 px to 24 px wide.

    With these, "4250 / 4250 · 339.9 mm" fits. A browser test holds this. To overrule it, change
    `css/wizard.css`.
13. **The colour key opens and closes as the mockup's does.** It opens from its icon and closes on
    the icon, on a click elsewhere, or on Escape. The CSS places it under the icon. It is not built
    with the panel's `joinedBox`, which would place it by its own rules and differ from the
    mockup's look.
14. **Download asks for the details first.** This settles a detail the documents mark as
    proposed. If the front server refuses with anything other than "expired", a red message with
    its own sentences goes in `#send-errors`, and the button stays. To overrule it, change
    `download()` in `result.js`.
15. **Where Download's notification goes.** It is the panel's notification, at the top of the
    step and closed with ×, as the guide's "How the panel tells the user something" asks. The
    mockup shows a grey box under the card instead. Its text: "Downloaded the sliced file of 2
    instances (1.8 MB)." It names the plate by its instances, with no "Plate 1", as the guide
    departs from the mockup on fake 11.
16. **What a megabyte is.** It is 1,048,576 bytes, as the contracts count the 50 MB cap
    (52,428,800 bytes). Sizes show one decimal from a megabyte up, whole kilobytes under a
    megabyte, and bytes under a kilobyte. The documents are silent. To overrule it, change
    `sizeText` in `result.js`.
17. **Rounding the print time.** It is written in whole minutes, as the mockup's `hm` writes it,
    and any time above none shows at least 1 minute.
18. **Where the counts come from.** The Send card's instance count and Download's notification
    count the plate configuration that was submitted. The quiet line uses the summary's
    `instances`. The two agree for a real slice; the fake front server's example does not agree
    with its own plate.
19. **The Send card stays under the expired message.** The guide says the message replaces Send,
    not the card.
20. **A key for the "is still here" notification.** A notification keyed
    `STILL_HERE_NOTICE` (`sliced-plate-still-here`) is dropped at the moment of expiry. Phase 2
    makes no such notification; phase 5's notifications that say "is still here" are to use this
    key.
21. **A new seam for Download.** `seams/download.js` (`saveLink`) holds the plain link, so that a
    test can replace it.
22. **The fake front servers.** The Python fake front server now answers `GET
    /api/slices/<slice>/file` with the committed real `spacer-1.gcode.3mf`, and can send scripted
    answers of bytes. The Node tests' helper for the Preview step moved to
    `tests/fakes/preview-page.js`, so that two test files share it.
23. **No new ids on the page.** The page's test allows only the mockup's ids, so the result's
    three new places are classes: `.result-warnings`, `.preview-view-message` and
    `.preview-view-box`.
24. **What the look pictures draw.** The built page draws the committed `pair-supports` sliced
    file of the same two real parts it uploads. The mockup draws its own fake slice. The Send
    step is shown beside the mockup's twice: once with a printer paired and once with none, since
    phase 2's Send step lies between the two.

## Targets missed

1. **Download's notification is not where the mockup puts it.** The mockup draws a grey box
   under the card; the built page shows a notification card at the top of the step, as the guide
   requires (decision 15).
2. **The quiet line has no layer height.** The mockup's line ends "of 0.3 mm"; the built line has
   no layer height (decision 10).
3. **The row under the view is tighter than the mockup's below 480 px:** 4 px gaps and 24 px small
   buttons, against the mockup's 6 px and 28 px. The mockup's readout wraps at 320 px and the
   built one does not (decision 12).
4. **The two pages show different plates.** The toolpaths and the figures in each pair differ,
   because the mockup's slice is fake. The layout, the elements, their order, colours, type and
   wording match at all four widths.
5. **The layer preview was not measured again in the Preview step.**
   - `measure-preview` was not run again.
   - The first layer is now timed from the moment the step opened, a fetch included. That
     figure, and the frame rates and memory with the result around the view, are not measured
     against `FIRST_LAYER_S` (5 s) and `PAGE_MEMORY_MB`.
6. **Elsewhere on the panel, as before this batch:**
   - there is no printer-status icon (it comes in phase 5);
   - the configuration's name is plain text, a departure of the guide.

## Not done

1. **Coming back, item 16.** A returning page whose stored slice is of the plate as it stands
   follows that slice. If the front server answers that the slice has expired, the expired message
   shows, through what this batch built. The "Back where you were" notifications and the rest of
   the returning page's table are not built.
2. **Sending the drawing summary, item 18.** It is not built.
3. **The whole path against the real front server and slice service.** This batch walked it only
   against the Python fake front server. The joined suite's browser half does the real walk.
4. **The Mac's frame rate and the renders.** These are the owner's part, as in the record of
   wizard-7.

## For the owner to look at

1. The pairs of pictures, the mockup and the built page side by side at 320, 480, 520 and
   680 px: [docs/orchestration/phase-2/look/wizard-8/index.html](../look/wizard-8/index.html).
   Run `make -C wizard look-result-send` to make them again. The builder looked at every pair.
2. On one machine, as
   [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
   says:
   1. Add two parts and lay them out.
   2. Open the Preview step and watch the result and the layer preview appear.
   3. Open the colour key and the "?".
   4. Go to the Send step and press Download the sliced file. The browser should save the file
      under the name the slice service gave it, and the notification should give its size.
