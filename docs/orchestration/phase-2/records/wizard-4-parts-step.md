# Batch wizard-4-parts-step: the record

Item 8 of [the wizard's details, "By phase", phase 2](../../../../wizard/README-details.md#phase-2-one-machine):
the Parts step. Built on Sat 2026-11-28 by one builder, with no one to ask. What is built is
described in the details file's section [The Parts step](../../../../wizard/README-details.md#the-parts-step)
and, in plain words, in the guide's [What is to be built, by phase](../../../../wizard/README.md#what-is-to-be-built-by-phase).

## Decisions made

1. **A refused part's notification names it by putting its name before the refusal's
   sentence** ("Shooter Hood Rib: This part …"). To decide: the guide says the notification
   "names it" and that its sentences are those of the component that refused the part; an
   upload carries no name, so the slice service's sentences cannot name it. Chosen: the part's
   name, a colon, then the refusal's `message` unchanged; the second line is the `remedy`.
   Reason: with several files dropped at once, the user must know which one failed, and no
   word of the refusal is changed. To overrule: change `NAMED` in `wizard/src/sentences.js`,
   or have the front server pass the name to the slice service.
2. **The order of a part's checks: its size, then its hash, then the number of parts.** The
   details listed the hash first. Chosen: the size first, so a file of any size (a 100 MB
   file chosen by mistake) is refused before it is hashed. Nothing a user sees changes. To
   overrule: move the size check after the hash in `addOne` of `wizard/src/parts.js`.
3. **A file's size in the over-size notification is in megabytes of a million bytes,
   rounded up to 0.1.** The guide's example says "9.1 MB" and "up to 7.5 MB" for 7,500,084
   bytes, and is silent on rounding. Chosen: rounded up, so 7,500,085 bytes reads "7.6 MB"
   and a refused file never reads as the limit. To overrule: change `megabytes` in
   `wizard/src/units.js`.
4. **"Your other parts are fine." comes first on the notification's second line, before the
   remedy**, as the mockup puts it, and on the over-size notification too, which the guide's
   table "A part that cannot be used" includes; not on the twenty-sixth part's, whose sentence
   is about the other parts. The reminder of how STL files are read comes last. The guide is
   silent on the order. To overrule: change `tellNotAdded` in `wizard/src/parts.js`.
5. **A part still arriving never holds Next, even as the plate's only part**, as the guide
   says ("A part still arriving never holds Next"); the mockup turns Next off until a part has
   arrived. The plate summary counts only the parts that have arrived; the 150-instance limit
   and its red message count the parts still arriving too ("This plate would hold …"). The
   store carries `arriving` and `arrivingInstances` beside `parts` and `instances`. To
   overrule: `whyNotLeave` in `wizard/src/panel/panel.js`.
6. **The notification of a part that arrives late is shown on the Settings, Preview and Send
   steps**, not on the Layout step, where the part joins at once. The guide says "a
   notification on the step the user is on"; the mockup shows it only after the Layout step.
   The guide is right. To overrule: change `LATE_STEPS` in `wizard/src/parts.js`.
7. **New plate is shown only while the plate holds parts, and so always asks first.** The
   guide said "When the plate holds parts it asks first", which implies a button on an empty
   plate that does nothing visible. Chosen: hidden on an empty plate; the guide and the
   details now say so. To overrule: show it always and let it act at once on an empty plate.
8. **The switch is two radio buttons in the mockup's line under the upload area**, "Read STL
   files in: (o) inches / ( ) millimetres", in the line's 12 px grey, the radios in the accent
   blue. The guide gives its words, not its form. To overrule: draw it as two chips in
   `wizard/src/panel/parts-step.js` and `wizard/src/css/wizard.css`.
9. **A switch never chosen follows the configuration's `upload_units` as it is read, and is
   inches when there is no configuration.** The guide says it "starts at the configuration's
   value". Inches is the default configuration's value. To overrule: `units` in
   `wizard/src/parts.js`.
10. **A warning on a row is drawn as the mockup's amber message: its first sentence bold, the
    rest beneath**, the slice service's words unchanged, split at the first full stop, question
    or exclamation mark followed by a space and a capital letter (since the review: "e.g. on"
    and "i.e. 0.2 in" no longer end the first line). The contract gives a warning one
    `message`; the mockup draws two lines. To overrule: `firstSentence` in
    `wizard/src/panel/parts-step.js`.
11. **A row's size is the record's `size_mm`, the slice service's measure, in the part's own
    units**, with the tooltip "Size as modelled, in inches (this file was read in inches)". The
    mockup's tooltip said "STL files are read in inches", which the switch can make untrue for
    an older row. To overrule: `SIZE_TIP` in `wizard/src/sentences.js`.
12. **A record naming another hash, or other units, is uploaded once more; a second difference
    is shown as `wizard.bad_answer`** and reported as `page_failed`, the part not added. The
    details give no sentence for it. A record the page cannot use (eight ways, each tested) is
    `wizard.bad_answer` too.
13. **Any other refusal of an upload** (a front server code the details' table does not list,
    such as `front.group_not_allowed`) is shown as it is and the part is not added. The details
    are silent. To overrule: give such codes their own handling in `upload`.
14. **A part removed, or a plate emptied by New plate, has its upload stopped.** The documents
    say a long job is stopped by the component that runs it, and nothing of how. Built: an
    AbortSignal option `signal` on `api.request`, which aborts the attempt being made, makes no
    other, takes the request off the panel line (`board.stop` in `wizard/src/retry.js`) and
    resolves to `{ok: false, stopped: true}`. Reason: otherwise a removed part's upload would go
    on retrying, and could hold the red panel line, for ever.
15. **The fake front servers (JavaScript and Python) answer an upload with the record of the
    bytes sent**: the example's record with the body's hash, the query's units and no warning.
    Reason: the page compares the record's hash with its own, so the example's fixed hash would
    make every upload in every test a mismatch. Their own tests check the new default.
16. **A page opening again takes up its stored parts before it marks itself opened**: a part
    with its record arrives at once and is read for drawing; one without is uploaded again (its
    bytes are kept); one whose bytes are gone is dropped. The opening waits only for the
    storage, never for an upload. The full-plate storage test in Chromium now stores real STL
    files with their records, since the page reads every stored part on opening (1.76 s and
    1.86 s for the test in two runs after the review, on an aarch64 Linux machine of 8
    processors shared with other work; 3.4 s once while it was busier; 1.35 s before this
    batch).
17. **A stored part carries its `quantity`**, beside `sha256`, `units`, `name`, `record` and
    `saved`; the record is null until the upload is answered. The details listed the fields
    without a quantity.
18. **The page's own checks are error reports with codes of the wizard's own**:
    `wizard.part_over_size`, `wizard.too_many_parts`, `wizard.too_many_instances`, made in
    `wizard/src/sentences.js`. The details named only the slice service's codes for the same
    limits. Reason: every failure a user sees is an error report.
19. **A confirmation near the panel's foot opens above its control.** Looking at the pictures
    showed New plate's question under a long list running past the panel and scrolling the page.
    The details said "under its control"; now "or above it where the panel ends below", in
    `confirmation` of `wizard/src/panel/telling.js`, with a test in Chromium.
20. **An arriving row's bar moves to and fro**, since it "promises no duration" and the page
    knows no progress of an upload; its picture is faded and its quantity cannot yet be changed,
    as in the mockup.
21. **A worker that has failed as a whole** refuses every new part with its own
    `wizard.layout_failed` sentences, and the part is not reported as `part_not_drawable` (the
    worker's client already sent one `layout_failed`). The documents are silent.
22. **The over-size notification names the file as chosen ("bracket.stl"), every other
    notification the part's name ("Gusset Plate")**, as the guide's examples do.
23. **Rows are updated in place, keyed by hash and units**, so that a quantity being typed
    keeps its focus when another part arrives; the typed figure is held at 150 as it is typed,
    and taken on its change; a figure under 1 or not a number becomes 1, a fraction is rounded.
24. **The Parts step's section stays before the Settings step's in `index.html`**, where the
    mockup has the Settings section first. The step test checks that the ids the page shares
    with the mockup come in the mockup's order; the Settings step's ids, when they are added
    to its section, will come after the Parts step's and fail that check. The builder of the
    Settings step moves the Parts section after the Settings section, or the check is changed.
    Left so here because the Settings step is being built at the same time, and moving the
    sections now would collide with it.
25. **The pictures for the look are of the whole panel**, with the mockup's words and sizes
    given to the fake front server, in seven states the mockup shows and four it never drew;
    the parts are boxes, not the mockup's generated parts.

### Decided while fixing the review's findings

26. **A file the browser cannot read is refused alone, with a notification of the wizard's
    own, `wizard.file_unreadable`**: "gone.stl could not be read, so it was not added." and
    "Check that the file is still there, then add it again.", with "Your other parts are fine."
    before it while the list holds parts; the browser's reason (`NotReadableError: …`) in its
    `detail`; no report sent, since the fault is the file's, not the page's. The guide listed
    "a file the page itself cannot read" among the wizard's own failures and gave no sentence
    or code. Each file is now read in its turn (`addFiles` in `wizard/src/parts.js` takes the
    browser's File objects), after its size is checked by `File.size`, so a file over the
    limit is never read into memory and only one file's bytes are being read at a time. The
    guide and the details now say so. To overrule: `fileUnreadable` in
    `wizard/src/sentences.js` and `addFile` in `wizard/src/parts.js`.
27. **The reminder after a part refused as too large names the units the file was read in**,
    not the switch's setting at the moment of the refusal; the two differ only when the switch
    is turned during an upload. The guide says "how the file was read"; the details' test
    sentence said "the switch's current units" and now says the former. To overrule:
    `tellNotAdded` in `wizard/src/parts.js`.
28. **The figure measured for the full-plate storage test** replaces the one written while the
    machine was busy (decision 16).

The review's findings declined:

- **Minor finding 4, decision 7 (New plate hidden on an empty plate), is kept, not reverted.**
  The reviewer is right that it overrules the guide's sentence ("When the plate holds parts
  it asks first") rather than settling something the guide left open. It is kept because
  reverting would put back a button that, on an empty plate, does nothing a user can see, and
  the guide now says what is built; it is listed under "For the owner to look at" so that the
  owner decides.

## Targets missed

Differences between the mockup's Parts step and the built one, seen in the pairs of
[docs/orchestration/phase-2/look/wizard-4/](../../look/wizard-4/index.html), that were not removed:

- **A refused part's notification starts with the part's name** ("bracket: Could not read
  bracket.stl …"), decision 1. The mockup's sentence is the wizard's own and names the file in
  it; here the sentence is the slice service's.
- **The line under the upload area is the switch** ("Read STL files in: inches / millimetres",
  two radio buttons) where the mockup has "STL files are read in inches."; the guide departs
  from the mockup here (decision 51 departed from).
- **The upload area says "Drop STL files here, or click to choose"**, where the mockup says "STL
  or 3MF files": binary STL only, by the guide. At 320 px it is one line shorter.
- **New plate** is a button the mockup never drew, under the line counting the plate.
- **Next is on while the only part is still arriving** (decision 5), where the mockup's is off.
- **The arriving bar** moves to and fro rather than filling, since the page knows no progress.
- **The parts' pictures** are of the test boxes, drawn by the page's worker, not the mockup's
  generated parts; the look of a picture is the one batch wizard-3 settled.
- **The header**, as batch wizard-2 left it: no printer-status icon (phase 5), the configuration's
  name in plain text, the header 2 px shorter without the icon, so everything below sits 2 px
  higher; the built panel is 760 px tall in the pictures and the mockup's 750 px.

- **A warning's first line can still end early** at an abbreviation followed by a capital
  letter ("e.g. PLA"): the split (decision 10) knows no list of abbreviations. None of the
  slice service's warning sentences has one today.

No target figure of the documents was measured in this batch. The one figure measured is the
time of the full-plate storage test (decision 16), which has no target.

## Not done

- **A part's instances laid down by auto-orient and joining the plate on the Layout step**,
  step 7 of "Adding a part": the Layout step is item 10. The notification of a part that arrives
  late is built; its joining is not.
- **The Onshape prompt above the list** (`#parts-onshape`) and part sets from the Onshape
  integration: phase 4. `addPartSet` takes any part set now.
- **A late part's notification in Chromium**: it is tested in the fast suite only; the Python
  fake front server cannot hold an answer until the user has moved on.
- **The drop area's look while a file is dragged over it** (the mockup's `drag` class) is built
  and not tested.
- **The second run of the browser tests in Edge.**

## For the owner to look at

- **Decision 7 overrules the guide.** The guide said New plate "asks first when the plate holds
  parts", which implies a button also on an empty plate; the batch hides it there and changed
  the guide's sentence to match. If the button should show on an empty plate too, it acts
  there at once, without asking (`.new-plate` in `wizard/src/panel/parts-step.js`).

- The pairs, mockup beside the built page, at 320, 480, 520 and 680 px, in each state of the
  Parts step the mockup shows and in New plate's confirmation, a part over the size limit, the
  twenty-sixth part and a part the page cannot draw:
  [docs/orchestration/phase-2/look/wizard-4/index.html](../../look/wizard-4/index.html), made
  again with `make -C wizard look-parts-step`.
- `make -C wizard test` and `make -C wizard test-browser`; the new tests are
  `wizard/tests/parts.test.js`, `wizard/tests/parts-step.test.js`, `wizard/tests/units.test.js`, the stopped requests in
  `wizard/tests/retry.test.js` and `wizard/tests_browser/test_parts_step.py`.
- With the three components started as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says: drop the real parts of `contracts/examples/parts/real/` on the upload area with the
  switch at millimetres; drop one again (its quantity rises); switch to inches and drop a large
  part (the slice service refuses it as too large, with the reminder); refresh the tab (the rows
  come back); press New plate.
