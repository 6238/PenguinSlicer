# Batch wizard-6-submit-follow-failures: the record

Items 11 and 12 of [the wizard's details, "By phase", phase 2](../../../../wizard/README-details.md#phase-2-one-machine):
submitting and following a plate, and every slice failure. Built on Fri 2026-11-27 (Pacific) by
one builder, with no one to ask, while the builder of the layer preview worked in another
worktree. What is built is described in the details file's sections
[Progress streams](../../../../wizard/README-details.md#progress-streams) and
[Submitting, following and failing, as built](../../../../wizard/README-details.md#submitting-following-and-failing-as-built),
and, in plain words, in the guide's [What is to be built, by phase](../../../../wizard/README.md#what-is-to-be-built-by-phase).

How it was checked beyond the fast suite and the browser tests:

- **Against the real slice service's reading.** The page's own plate configuration of each of the
  thirteen shared plates and of the contract's phase 2 example (each plate turned into the stored
  plate's form and made again by `plateConfiguration`, with the default configuration's printer,
  filament and process) was submitted to a real slice service started from `slice/` with the
  slice service's stand-in for Orca, its parts uploaded first: all fourteen answered as their
  `expected` says (nine accepted and sliced to `done`, five refused with the expected code and
  instances). No real Orca was run.
- **The whole path, once.** The built page in Chromium, against the real front server
  (development identity) and the real slice service (stand-in Orca), on ports above 20000: two
  parts uploaded, laid out, the Preview step entered; the page sent one `POST /api/slices`, opened
  one progress stream, followed the slice from "Waiting for the slicer" through "Slicing the
  plate", "Writing the sliced file" (100 %) and "Reading the sliced file" to `done`, kept the slice
  in the stored plate, and enabled Next, with no error in the console. This walk found decision 8
  below.

## Decisions made

1. **A progress stream is opened by the module that makes every request.** The details say
   streams are opened "with `fetch`, so that [they carry] the same headers as any request" and
   reopened "at once and then with the waits of Retrying"; they do not say through which code.
   Chosen: `api.get(path, {expect: 'stream'})`, which hands the stream over once its headers
   arrive (the attempt's 15 s cover only those) and whose retrying is the reopening, so the 20 s
   of failing to reopen are retrying's own `RETRY_QUIET_S`, with the same panel line, Retry now,
   300 s and Try again. Reason: one place for every rule of a request. To overrule: `attemptOnce`
   in `wizard/src/api.js` and `streamLoop` in `wizard/src/following.js`.
2. **45 s of silence counts as a request failing for 20 s already.** The guide says a silent
   stream "is treated as failed in the same way" and the details "from that moment the panel
   line shows"; neither says when its 300 s start. Chosen: the reopening request counts as
   failing since 20 s before the moment of silence, so the amber line shows at once and the red
   line comes 280 s later. To overrule: `failingSince` in `streamLoop`.
3. **A stream that closes having carried no event is reopened after the waits of retrying,** not
   at once. The documents say "at once"; a front server that closed every stream straight away
   would then be asked with no pause. A stream that carried any event is reopened at once. To
   overrule: `emptyCloses` in `streamLoop`.
4. **"No news since 0:41" names the card's time at the last report,** and while there is no news
   the time taken goes on counting (the mockup's), while the percentage, the stage, the ring and
   the bar stay as last heard, the stage line ends "(last heard)" and the ring's layers go out
   (all the mockup's). The details say "the figures stop" without naming which. To overrule:
   `cardModel` in `wizard/src/slicing.js`.
5. **The card counts as having no news while the retry board shows any line,** that is while
   any request has failed for 20 s or the stream counts as failed, as the details' table says
   literally; it has news again with the first report after the line goes. So a part's upload
   failing for 20 s also stops the card's figures. To overrule: the board's subscriber in
   `createSlicing`.
6. **"Reconnected at 1:05…" stays 5 s** (`RECONNECTED_LINE_S`), the mockup's; the documents are
   silent. The line that the slicer restarted stays while the card shows, boxed in the panel's
   grey (`.conn.restart` in `wizard/src/css/wizard.css`), since the mockup never drew it.
7. **Before the first answer to a submission, and while waiting, the card's time line reads
   "0:12 waited"** with no time left, and its first stage, "Waiting for the slicer", is current.
   The mockup draws only "elapsed"; the guide says "the time waited counts up". To overrule:
   `WAITED` in `wizard/src/slicing-sentences.js`.
8. **A running report with no `stage`** (the slice service sends one as a slice starts, before
   "Building the plate") marks no stage current and shows no stage line, rather than inventing
   one. Found by the walk with the real slice service.
9. **The fingerprint** is a 53-bit hash (cyrb53) of the plate configuration's JSON less
   `plate_id`, `submission_id` and `local_time`. The details propose "less its two ids"; the
   local time moves every minute, so leaving it in would make every plate "not sliced as it
   stands" a minute later. To overrule: `fingerprint` in `wizard/src/plate-configuration.js`.
10. **Entering the step with the plate as it stands changes nothing while its slice is slicing
    or sliced; a plate that failed or found no room to wait is submitted again** with a new
    `submission_id`. This is not the builder's choice: the guide ("Slicing": entering the step
    submits the plate, coming back to a plate already sliced shows the result),
    [the plate configuration's contract](../../../../contracts/plate-configuration.md) ("The
    submission's value") and [the wizard and front server contract](../../../../contracts/wizard-front-server.md)
    (`POST /api/slices`, "For:") all submit on entering with "a plate not yet sliced as it
    stands", and a failed or busy plate is not sliced. The first build kept the failure on the
    step and submitted nothing; the review found that against the three documents, and it was
    brought into line. So a plate that ran out of memory is sliced again, and fails again, each
    time the user enters the step. To overrule: the guide and both contracts, then the
    condition at the top of `enter` in `wizard/src/slicing.js`.
11. **A page with no slice in hand whose stored slice is of the plate as it stands follows that
    slice** and submits nothing; a stored slice of another fingerprint is never followed, and
    the plate as it stands is submitted (a test now holds that half too: removing the
    fingerprint's comparison fails it). That is the part of "coming back" (item 16) the Preview
    step needs; the rest of item 16 is not built (see Not done).
12. **A slice job unknown (`404` `front.slice_unknown`) two hours or more after it was submitted
    is not submitted again by the page itself.** The guide says "the page does not slice again
    by itself" and gives the expired message with Slice again, which is item 14, not built here.
    Until then the refusal's own sentences (the front server's) are shown as a failure with
    Slice again and Back to Layout, and entering the step again slices, as decision 10 says for
    any plate not sliced. To overrule: `onRefused` in `createSlicing`, when item 14 is built.
13. **Parts missing.** A listed part whose bytes the browser no longer holds, or one listed in a
    form the page cannot use, ends with the `slice.part_missing` report itself shown (its
    sentences "exist for … a page that cannot upload the parts again"); an upload of a missing
    part that is refused ends with that refusal shown. The third `slice.part_missing` of one
    submission (`PART_MISSING_TRIES` 2, the details' proposal) and one with no `missing_parts`
    are shown and reported as `page_failed`.
14. **Two failures of the page's own, before sending:** `wizard.plate_not_ready` when the
    configuration holds no profile of the plate's filament and profile names (Back to Settings),
    and `wizard.plate_configuration_over_size` for a body over 1,048,576 bytes (Back to Parts).
    The details say the body is checked and name no sentence or code.
15. **No room to wait reads the slice service's `message`, then its `remedy` followed by "Your
    plate is unchanged."** The details list the three without an order.
16. **Details on the two empty-layers failures holds Orca's sentence alone,** after "Orca Slicer: ",
    and no Details is drawn when the report has no `orca_sentence`. The guide also puts there "the
    slice service's sentence of where to look on the part", which no field of the error report
    carries (the slice service names the instance and heights in its `message`). See Targets
    missed.
17. **The buttons of a failure** are the action's button first (`enable_supports`,
    `slice_again`), then the code's row, the first of them primary (as the mockup draws). A
    `slice.part_missing` without a list, `wizard.bad_answer` and every code the page does not know
    have the last row's Slice again and Back to Layout.
18. **"Not sliced: with Supports on, instances need 12 mm between them."** is a grey message at
    the top of the Layout step's messages (the mockup's `msg('info', …)`), until the user leaves
    that step: a small addition to `wizard/src/layout.js` (`notSliced`), the one place the Layout
    step draws its notes. Turn on Supports sets the Supports quick change to On through the
    Settings step, so `support_type` `tree(auto)` comes with it.
19. **The plate is "sliced" only while it is the plate the sliced file was made of:** after any
    change told by the Layout step, the Settings step, the Parts step or the store, the
    fingerprint is worked out again, so that a tab click past a changed plate to the Send step is
    held. The details did not say how `sliced` follows a change.
20. **A slice goes on being followed when the user leaves the step,** so its stream stays open
    (one of the user's four) until the slice ends or the plate is submitted anew.
21. **The plate is read once the page has opened and the Layout step's work is done;** a step
    left again before then submits nothing.
22. **The ring's layers are lit by the fraction** (one more for each fifth), where the mockup
    cycles them with time; the mockup's is an animation of a fake slice.
23. **The card's markup** is the mockup's `#slice-card` without `#btn-cancel`, its time line split
    into spans so that "waited" and the separator can change; `#preview-result` is left empty in
    the markup, for the layer preview's builder, and holds one plain line once the plate is
    sliced.
24. **A running report without a number in `elapsed_s`** (the contract requires one, so only a
    hostile or broken answer lacks it) counts the card's time taken from the card's start rather
    than reading "NaN:NaN". The documents are silent. To overrule: `elapsedS` in `slicing.js`.
25. **A part uploaded again after `slice.part_missing` is checked as a first upload is:** its
    record must name the `sha256` and `units` asked for; once more when it names others, and the
    second time `wizard.bad_answer`, shown, with a `page_failed` report. The details said only
    "uploads each listed part again"; the rule is the Parts step's, so the two uploads agree.
    To overrule: `uploadOne` in `slicing.js`.

### After the review

The reviewer's findings on pull request #44, and what became of each:

- Blocking 1 (a stored slice followed without checking it is the plate as it stands): the check
  was there, but no test held it. A test now opens a page on a plate changed since its stored
  slice and requires a new submission and no stream of the old slice job; it fails when the
  comparison is removed. Decision 11.
- Blocking 2 (entering Preview with a failed or busy plate submitted nothing): fixed, decision
  10, with a test for each; the details brought back into line with the guide.
- Minor 1 (a slice unknown at two hours or more submitted again by itself): fixed, decision 12.
- Minor 2 ("NaN:NaN elapsed"): fixed, decision 24.
- Minor 3 (the job-id check held by no test): a test now feeds a report, and a `done`, naming
  another slice job; it fails when the check is removed.
- Minor 4 (`wholeAngle`'s normalising held by no test): a test now sends angles of 360, -90,
  45.6 and 719.4 and requires 0, 270, 46 and 359; it fails when the normalising is removed.
- Minor 5 (`replaced` or `requested` on the followed slice job freezes the card): declined, see
  Not done 3.
- Minor 6 (parts uploaded again not checked against what was asked): fixed, decision 25.
- Minor 7 (the details naming only `sentences.js` for the wizard's sentences): fixed; the row of
  "Who writes the sentences of a failure" names `slicing-sentences.js` for the Preview step's two
  codes.
- Minor 8 ("no news since 0:31" changing colour partway): declined, nothing to fix. The span is
  one element with one colour (`.slice-times .late`, `#slice-expected` in
  `wizard/src/panel/preview-step.js`); magnified six times, `480-no-news-wizard.png` shows the
  whole of "no news since 0:31" in the same amber. The grey look of "no" at its own size is the
  antialiasing of thin small type beside the grey separator.

## Targets missed

1. **The slicing card beside the mockup** ([the pairs](../look/wizard-6/index.html)): it lists
   the contract's 13 stages where the mockup lists its own 8 (the progress report's contract fixes
   the stages), so the card is about 100 px taller at every width; no stage is struck through
   when supports are off (the slice service reports "Checking and generating supports" either
   way); there is no Cancel slice, on purpose (the guide's departure). While there is no news the
   mockup draws, inside the card, a yellow box "Lost the connection to the server at 0:08.
   Reconnecting (try 2)…" with a sentence about Cancel slice; the built card has no such box, since
   the guide puts that news on the panel line and the card's time line only.
2. **A failure beside the mockup:** the sentences differ, the mockup's being its own and the built
   page's the slice service's (shorter, without the mockup's heights in millimetres on the
   message's first line or its "where to look" advice under Details). The look (red edge, title,
   buttons, folded Details) matches at each width.
3. **"Where to look on the part" under Details** (the guide's Details, in both empty-layers
   cases) is not shown: the slice service sends no such sentence apart from its `message`.
4. **Elsewhere on the panel, as before this batch:** the printer-status icon (phase 5) and the
   configuration's name drawn as plain text rather than the mockup's link (a departure of the
   guide).
5. **No real Orca slice** of a plate configuration the page made: the real slice service read
   all fourteen and sliced the accepted ones with its stand-in Orca.

## Not done

1. **The result and the layer preview** (item 13): a sliced plate shows one plain line in their
   place; the next batch joins the layer preview's module.
2. **A sliced plate that expires** (item 14): a slice unknown two hours after it was submitted
   shows the front server's refusal with Slice again in place of the expired message (decision
   12), and a `failed` report with `front.sliced_file_expired` is shown as a failure with Slice
   again and Back to Layout.
3. **A `cancelled` report with `cancel_reason` `replaced` or `requested` about the slice job
   being followed** stops following and leaves the card as it was. The review found that this
   freezes the card. Declined: the details say "`cancel_reason` `requested` never reaches a
   page", and a page is told `replaced` about its own slice job only after it has itself
   submitted a newer one, which it then follows (the old job's stream is closed first, so the
   report does not arrive). No document says what a page should show for a report that cannot
   arrive, and inventing a failure without an error report would break "every failure is an
   error report".
4. **Coming back** (item 16): the "Back where you were" notifications and the returning page's
   other rows; only following a stored slice of the plate as it stands is built (decision 11).
5. **The browser half of the joined suite**, which drives this page against the real components,
   is the joined suite's own batch; this batch walked the path once by hand.

## For the owner to look at

1. The pairs of pictures, mockup and built page side by side at 320, 480, 520 and 680 px:
   [docs/orchestration/phase-2/look/wizard-6/index.html](../look/wizard-6/index.html), made again
   by `make -C wizard look-preview-step`. Every pair was looked at by the builder.
2. The slicing on one machine, as [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
   says: add two parts, lay them out, open the Preview step, and watch the card go through its
   stages to the plain line of a sliced plate; then change a setting and open the step again to see
   a new slice start.
