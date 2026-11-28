# Record of batch wizard-2-skeleton-panel

The batch builds items 2, 3 and 4 of the wizard's phase 2 list
([By phase](../../../../wizard/README-details.md#by-phase)): the skeleton (the build of
`wizard/dist/` with the names inside assets and `wizard/vendor/`, the page, `css/panel.css`
taken over, the fake clock and the fake front server, the seams and the module that makes
every request; the seams search widened to every way of reading the time or reaching the
network), retrying with the panel line, and the panel as a whole (the widths, the header, the
step tabs, the plate summary, Back and Next, the six ways of telling, the tooltips). Pictures
of the built panel beside the mockup's are in
[look/wizard-2/](../look/wizard-2/index.html).

## Decisions made

1. **How long the panel line's passing use stays.** The details file proposed 4 s
   (`PANEL_LINE_PASSING_S`, *proposed*); the guide says "a few seconds"; the mockup's script
   used 8 s. I chose 8 s, the mockup's, since the line also goes at the user's next move, so
   the timer only matters to a user who reads without moving. To overrule: change the
   constant in `wizard/src/page-constants.js` and its two tests.
2. **The spread and the attempt times.** The details file proposed a spread of 0.1 and
   attempt times of 15 s and 60 s (upload). I settled them as proposed, the spread applied
   either way (each wait times a factor between 0.9 and 1.1). How the attempt time treats
   the body is decision 29. To overrule: the constants in `page-constants.js`.
3. **Module names that would collide in the flat `assets/`.** The details file proposed a
   module `messages` for the wizard's own sentences; `geometry/messages.js` already exists,
   and the build refuses two files of one built name. I named it `sentences.js`, and the
   page's constants `page-constants.js` (beside `geometry/constants.js`). To overrule: rename
   the geometry's modules instead.
4. **How a page module names a vendored file.** The documents say only that the build
   "builds in `wizard/vendor/`" and rewrites the bare name `three`. I made a page module name
   a vendored file by its relative path (`'../vendor/three/...'`), which resolves both in the
   built page and where `src/` and `vendor/` are served side by side as the trials serve
   them; any other bare name is refused. Only the vendored `.js` files are built in (not the
   README, `.gitignore` or `LICENSE`; the core keeps its licence line). To overrule: change
   `target()` in `wizard/build.py`.
5. **A built name carries the hash of the rewritten file.** The contract says the name
   carries "a hash of its contents". I hash each file after its names are rewritten, so a
   change to a module renames every module that imports it (otherwise a year-long cached
   importer could load a new import under an old name), and refuse modules that import each
   other in a circle, which no such name can describe. To overrule: hash the source bytes
   and accept stale caches, or allow circles with another naming scheme.
6. **What the seams search also forbids.** The details file left the other ways to the
   skeleton. Besides the six it named (`new Date()`, `performance.now`,
   `requestAnimationFrame`, `XMLHttpRequest`, `EventSource`, `WebSocket`), I forbade `Date()`
   called as a function, `requestIdleCallback` (a timer) and `sendBeacon` (the network), and
   allowed `new Date(figure)`, `Date.parse` and `Date.UTC`, which read no clock. A later item
   that needs a frame clock or a progress stream adds it to the seams. To overrule: change
   `FORBIDDEN` in `wizard/tests/forbidden_calls.js`.
7. **What an answer to another request does to the requests still failing.** The guide says
   the line "goes the moment a request is answered" and is silent on the others. I made every
   waiting request attempt again at once (its count kept, as Retry now), and every request
   past its 300 s attempt as Try again, since the server has just answered; one that fails
   again brings the line back. Without this, a request past 300 s would sit with no line and
   no Try again after another request's answer hid the red line. To overrule: change
   `answered()` in `wizard/src/retry.js`.
8. **What the line says while an attempt is being made.** The countdown would read "in 0 s"
   for up to 15 s when an attempt hangs. I wrote a sentence of the wizard's own: "The server is
   being slow. Your browser is retrying now.", and added it to the guide's table. To
   overrule: change `SERVER_SLOW` in `wizard/src/sentences.js` and the guide.
9. **Retry now and Try again act on every request concerned.** The documents speak of "the
   next attempt" of one request. Every waiting request is waiting on the same server, so Retry
   now attempts each at once (counts kept) and Try again each request past its 300 s (counts
   started afresh at its next failure). To overrule: `retryNow` and `tryAgain` in `retry.js`.
10. **A request is never dropped.** "Nothing of the user's work is dropped" and "after 300 s
    the row keeps its part": a request past 300 s stays pending, waiting for Try again or
    another request's answer, and its caller's promise does not settle until then. To
    overrule: give `request` a way to give up and a result for it.
11. **Which requests carry the current group.** The contract marks each request; I sent the
    group on every request once it is known except the three the contract marks "Group: none"
    that the page makes (`GET /api/me`, `GET /api/settings-table`, `POST /api/signout`). To
    overrule: `NO_GROUP` in `wizard/src/api.js`.
12. **An answer the page cannot read.** No document says what the page shows for a front
    server answer that is not JSON where JSON is due, or a failure whose body is not an error
    report. I made it the wizard's own error report `wizard.bad_answer` ("The server gave an
    answer this page cannot read." / "Reload the page to try again."), shown and not retried,
    with a test that produces it. Its `detail` is the path, the status and the first 200
    characters of the body as it came (`BAD_ANSWER_BODY_CHARS`, settled in the review: the
    details file says "the start of the body" with no figure). To overrule: change
    `badAnswer` in `sentences.js`.
13. **How the browser tests move time and reach the running wizard.** The documents require
    a fake clock in every test. In Chromium I used Playwright's own fake clock (`page.clock`,
    installed before the page loads and paused once it has), held the one random figure
    (`Math.random`, for the spread) at its middle with an init script, and reached the running
    wizard by importing the page's own entry module, which exports it, never through a global.
    Where a test must wait for the page to reach a state, it asks the page again, each ask a
    round trip. To overrule: add a clock seam the tests can replace in the built page.
14. **"Grey when it only informs."** The guide calls the informing message grey; the mockup's
    style sheet has `.msg.info`, a grey box with a blue left edge, and no plain grey kind. I
    used the mockup's `info`, since the look is the mockup's. To overrule: add a plain grey
    kind to `css/wizard.css` and use it.
15. **The configuration's name in the header.** The mockup draws it as a blue link that goes
    nowhere; the guide (its departure from decision 2) makes it plain text for a user in one
    group. I drew it in the line's own grey, and the reload glyph as the mockup's `<a>` with the
    role of a button. To overrule: one rule in `css/wizard.css`.
16. **Why a step holds a click, before the steps exist.** The steps' own rules come with the
    steps. Until then the panel uses the mockup's own reasons: for the Parts step "add a
    part." and "a plate holds up to 150 instances."; for the Layout step "there are no
    instances.", then the layout's first problem when one is set; for the Preview step "the
    plate is not sliced yet.". Next follows the same rules. To overrule: each step
    brings its rules in `whyNotLeave` in `wizard/src/panel/panel.js`.
17. **The user's "next move".** The passing line goes at the next pointer press or key in the
    panel, or at a move to another step; a pointer merely moving does not end it. To overrule:
    the listeners in `panel.js`.
18. **The confirmation's look.** The mockup never drew one. I gave it the look of the panel's
    other joined boxes (white, 1 px border, radius 8 px, the shared shadow), under its control
    and 6 px inside the panel, with Keep first and focused so Enter never drops work. To
    overrule: `.confirm-pop` in `css/wizard.css` and `confirmation` in `panel/telling.js`.
19. **The style sheets.** `css/panel.css` is the mockup's byte for byte (a test checks it) and
    is never edited; what the mockup never drew is in `css/wizard.css`. To overrule: merge
    the two, giving up the check.
20. **The Send step's one button.** Phase 2 has "Download the sliced file" as the Send step's
    one button; the mockup's split button with its caret and menu is phase 5's. I kept the
    mockup's markup without the caret, with both corners rounded. To overrule: build the
    caret and menu in phase 5.
21. **The widths of the pictures.** The task names "the three widths the details file names
    (320 px included)"; the details file names 480, 520 and 680, the three where the layout
    changes. I took all four, 320, 480, 520 and 680 px. The pictures are made by a new target,
    `make -C wizard look`, so they can be made again after any change.
22. **A favicon.** The mockup's `data:,` favicon is refused by the build (another scheme), and
    without one Chromium asks for `/favicon.ico`, which the contract does not serve. I added a
    small `favicon.svg`, served from `/assets/` like every file. To overrule: delete it and the
    `<link>`.

Decided while fixing the review's findings:

23. **The last attempt is at 300 s.** The guide says the amber line counts down to the next
    attempt and that no attempt is made after 300 s; with the waits as they fall, the last
    attempt is at about 271 s and the next would be at 301 s, so from 271 s to 300 s there was
    no attempt to count down to (the line said "retrying now" and Retry now did nothing). The
    documents are silent on that gap. I shortened the wait that would pass the 300 s so that
    it ends at them: the line counts down to an attempt at 300 s, and Retry now makes it at
    once. The waits' list in the details file and the guide's table now say so. To overrule:
    the `deadline` in `request` in `wizard/src/api.js`, and show something else in the gap.
24. **A `Retry-After` past the 300 s.** The details file says an answer with `Retry-After` is
    not tried again before that many seconds; it is silent when that reaches past the 300 s.
    No attempt is then left to count down to, so the request waits for Try again at once and
    the board shows it as the red line from 20 s (`front.too_many_requests` with
    `Retry-After: 400`: nothing until 20 s, then "The server could not be reached." with Try
    again). Try again then goes against the server's request, but only when the user asks.
    To overrule: `state()` in `wizard/src/retry.js` (the `parked` case).
25. **Try again during the last attempt.** From 300 s the line is red while the attempt made at
    300 s may still be under way (up to 15 s). Try again pressed then marks the request, and
    the moment that attempt fails it is sent again with its count started afresh, instead of
    the press doing nothing. To overrule: `tryAgain()` and `park()` in `retry.js`.
26. **A `Retry-After` as an HTTP date.** HTTP allows a date as well as seconds; the details
    file does not say which the front server sends. The page reads both, a date reckoned on its
    own clock from the moment the answer arrived, and ignores a value it cannot read (the plain
    wait then holds). Before the review a date was read as 0. To overrule: `retryAfterS` in
    `wizard/src/api.js`.
27. **The body is read as text and parsed by the page.** So that `wizard.bad_answer` can carry
    the start of the body, and so that a body that fails while it is being read (silent past
    the attempt time, decision 29, or cut off by a restart) is told apart from a whole body that is not
    JSON: the first is a quiet retry, the second the wizard's report. The fake front server
    has two steps for it, `stallBody` and `cutBody`. To overrule: `attemptOnce` in `api.js`.
28. **The build and two kinds of name it could not handle.** A name inside a style sheet's
    comment (`/* url(gone.png) */`) is now left alone, as in a module; a dynamic import whose
    name is not one quoted string (a template literal, an expression) is refused with a
    sentence naming the line, since the build cannot rewrite it and the page would fail only
    when it runs. To overrule: `css_code_only` and `DYNAMIC_IMPORT` in `wizard/build.py`.

Decided while fixing the second review's findings:

29. **The attempt time limits the body's silence, not its length** (blocking finding 1).
    The contract leaves the attempt time to the builder; the details file said it covered
    the whole body, which made a sliced file of up to 50 MB (14.1 MB the largest measured)
    need about 27 Mbit/s (7.5 Mbit/s for 14.1 MB) to load at all: below that each attempt was
    aborted at 15 s, retried for ever, and the panel line blamed the server. Now the 15 s
    (60 s for an upload) run from sending until the headers arrive and then start afresh
    each time bytes of the body arrive: the transport seam's `text(onProgress)` and
    `bytes(onProgress)` read the body through its stream and tell `attemptOnce` of each part.
    A body silent for 15 s is still a quiet retry, so the restart case the old rule served is
    kept. I chose this over a longer time for the sliced file alone because any fixed time
    sets a slowest connection, and this rule sets none. The fake front server has a step
    `trickle` whose body arrives in parts the test releases; four tests cover a stalled
    sliced file, one arriving a part every 14 s for 168 s, one that stops after its first
    part (failed 15 s after it) and a JSON body arriving in parts. To overrule: `arm` in
    `attemptOnce` in `wizard/src/api.js`.
30. **The figure and its unit on the amber line are joined by a no-break space** (minor
    finding 2), so at 320 px the line no longer wraps between "11" and "s.". The guide's
    sentence reads the same. To overrule: `SERVER_SLOW` in `wizard/src/sentences.js`.
31. **A dynamic import with a second argument is refused, and the documents say so** (minor
    finding 5): the details file's and `build.py`'s lists of refusals name it, and a test
    produces it. The page has no use for import attributes. To overrule:
    `QUOTED_DYNAMIC_IMPORT` in `wizard/build.py`.
32. **Try again leaves alone a request still within its 300 s** (minor finding 1): the rule
    was built and untested; a test now presses Try again at 100 s and checks the request
    still makes its last attempt at 300 s and then shows the red line, not a silent restart.

Findings of the review declined, with the reason:

- **A report about the page itself answered with a quiet-retry code does not clear the panel
  line** (minor finding 5). Declined: for every request, an answer whose error report is a
  quiet-retry code (`front.slice_unreachable`, `front.unexpected`, …) counts as a failed
  attempt, not as an answer, and does not clear the line; the page's reports about itself
  follow the same rule. Such an answer says the front server is up but something behind it
  is not, so sending every waiting request again at once, which an answer does, would only
  hammer it. An answer of any other kind to such a report does clear the line, as for every
  request.
- **Running `make -C wizard look` again changes some committed pictures by bytes** (minor
  finding 8). Declined: the pictures are for a person to look at and no test compares them;
  the changes are anti-aliasing and the hover state, invisible in the pairs. Making Chromium's
  rendering byte-stable (fonts, hinting, the cursor) costs more than it is worth. The
  pictures in this pull request are the ones made after the fixes.

## Targets missed

1. **The printer-status icon is not in the header** (phase 5), so the header's first line is
   about 2 px shorter than the mockup's at every width and has nothing at its right
   ([320 px](../look/wizard-2/320-tabs-wizard.png) beside
   [the mockup](../look/wizard-2/320-tabs-mockup.png)).
2. **The configuration's name is grey, not the mockup's blue**, by the guide's departure from
   decision 2 (decision 15 above), at every width.
3. **The Send step's button has no caret and menu** (phase 5; decision 20 above).
4. **Two pictures differ by their surroundings, not by the element:** the mockup's message
   sits inside a part's row, so it is narrower than the wizard's, which has no row yet; and at
   680 px the mockup's card sits in one of the Send step's two columns, which come with the
   Send step, so the wizard's card spans the panel
   ([680 px card](../look/wizard-2/680-card-wizard.png)). The elements themselves match.
5. **The confirmation shows the browser's own focus ring** on its Keep button when it opens,
   since it takes focus; the mockup has no confirmation to compare it with.
6. **The steps' contents are not built**, so "every step rendered and checked for no sideways
   scroll" covers each step's panel as a whole (header, summary, title, Back and Next) and not
   what each step will hold.
7. **Three tests of the details file's Retrying list are not written**, since they need what
   later items build: the part's row saying "Taking longer than usual; still trying…" (the
   Parts step; the moment, 4 s and not 3.9 s, is tested on the request), the stored parts,
   layout and settings unchanged after 300 s (the browser's storage), and a repeated request
   leaving one part row and one slice job followed.
8. **"A panel resized across 480 px keeps advanced mode's open and closed sections"** is not
   tested: advanced mode is item 9.
9. **Sending a part needs about 1 Mbit/s of upload speed for the largest part.** The 60 s of
   an upload attempt cover sending the whole part, because the browser's `fetch` tells the
   page nothing of a request body's progress, so the rule of decision 29 cannot apply to
   it. A part of 7.5 MB in 60 s needs 7.5 × 8 / 60 = 1.0 Mbit/s; a 2 MB part about
   0.27 Mbit/s. Below that speed each attempt of such a part is aborted at 60 s and retried,
   and the part's row stays "Taking longer than usual; still trying…". The guide's limits
   table and its section on a slow server now state the figure. Meeting it on any
   connection would need a request whose sending can be followed (`XMLHttpRequest`'s upload
   progress, through the transport seam) or a longer time; that is for the Parts step
   (item 7) to decide with its row.

## Not done

1. **The header's content from the front server** (`GET /api/me`, `GET /api/configuration`,
   the reload glyph's request): item 5. The header draws whatever name the store holds and
   hides the line until it has one; the reload glyph tells a listener that item 5 sets.
2. **The steps' bodies, advanced mode, the printer-status icon and its details:** items 8 to
   15 and phase 5. The panel's markup holds each step's title only.
3. **The progress streams' seam:** item 11 adds the stream (an `EventSource` or a reading of
   `fetch`'s body) to the seams when it builds the streams; the search already forbids it
   elsewhere.

## For the owner to look at

- [docs/orchestration/phase-2/look/wizard-2/index.html](../look/wizard-2/index.html): each
  pair, the mockup on the left and the built panel on the right, at 320, 480, 520 and 680 px,
  for the header and step tabs with the panel line, a tooltip, the plate summary, the change
  details, a notification, a message, a card, a line, and the wizard's alone: the
  confirmation and the panel line's amber and red retry messages
  ([320 px amber](../look/wizard-2/320-retry-amber-wizard.png),
  [320 px red](../look/wizard-2/320-retry-red-wizard.png)). In the tooltip pair both pages
  keep the passing line of the held click. `make -C wizard look` makes them again.
- The panel itself: `make -C wizard build`, then start the front server as
  [Running phase 2 on one machine](../../../../front/README-details.md#running-phase-2-on-one-machine)
  says and open its address; the panel shows the Parts step with Next off, and a click on a
  later tab says "Parts first: add a part." under the tabs.
- The retry line: `make -C wizard test-browser` runs `test_the_retry_messages_on_the_panel_line`,
  which drives the line from 20 s (amber, counting down, Retry now) through the countdown to
  the last attempt at 300 s, to the red line with Try again, on the page's fake clock.
