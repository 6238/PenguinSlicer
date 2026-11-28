# The seam between the wizard and the front server

The first joining of the wizard and the front server, batch
together-2-browser-and-wizard-seam, Sat 2026-11-28 (Pacific time). Until then the wizard had
run only against fake front servers (`wizard/tests/fakes/front_server.js` on Node, and
`wizard/tests_browser/fake_front_server.py` in Chromium), and the front server had never served
the real wizard. This file records where the two sides, or a side and its fake, read the same
words of a contract differently, which side departs from the contract, the evidence, and what
was done; then what the joined suite now exercises for real, which scenarios it adds and why,
and what only a fake still exercises.

The contracts read beside the code on both sides:
[the wizard and the front server](../../../contracts/wizard-front-server.md),
[the part set](../../../contracts/part-set.md),
[the configuration](../../../contracts/configuration.md),
[the table of settings](../../../contracts/settings-table.md),
[the plate configuration](../../../contracts/plate-configuration.md),
[the error report](../../../contracts/error-report.md),
[the progress report](../../../contracts/progress-report.md) and
[the sliced file](../../../contracts/sliced-file.md). The code read: on the wizard's side the
module that makes every request (`wizard/src/api.js`) and each module that reads an answer
(`opening.js`, `configuration.js`, `parts.js`, `settings.js`, `slicing.js`, `following.js`,
`result.js`, `reloading.js`, `reports.js`, the preview's reader `preview/gcode.js`); on the
front server's side its routes (`front/src/penguin_front/app.py`, `pages.py`, `identity.py`,
`parts.py`, `slices.py`, `asking.py`, `streams.py`, `reports.py`, `errors.py`); and the two
fakes beside the real front server. The joined suite that ran them together is
[together/](../../../together/README.md); the batch's record is
[records/together-2-browser-and-wizard-seam.md](records/together-2-browser-and-wizard-seam.md).
The seam on the other side of the front server is
[the record of the front server and the slice service](seam-front-slice.md).

## Short answer

The two sides agree on every request, header, status, code, field and shape that passes
between them in phase 2. Joined, the real wizard in Chromium walked phase 2's "Done when"
against the real front server and the real slice service, with the stand-in Orca and with the
real Orca, and each row of the slice container's restart table that needs a page. Every
setting of the real table of settings, at its bounds and just past them, is accepted by the
slice service exactly when the wizard lets a user set it. The front server's codes have the
statuses and `retryable` the wizard's fake gives them.

Two mismatches stopped something a user does, and both are fixed:

1. **An open page whose sign-in was lost showed the refusal instead of making the trip.**
   The wizard departed from the contract. Fixed in the wizard, and its browser fake now keeps
   a sign-in it can lose.
2. **The stand-in Orca's sliced file could not be drawn by the layer preview.** The stand-in
   departed from the sliced file's contract. Fixed in the stand-in.

Two more are differences no reader acts on today, recorded and left: the hand-written
examples give a `done` report a stage the real one never has, and the slice service's first
running report has no stage, which the slicing card shows as a blank stage line for a moment.

## Mismatches

### 1. An open page answered "not signed in" did not make the trip

**The words.** The contract, "Signed in": an `/api/` request without a readable cookie is
answered `401` `front.not_signed_in`, and "that answer is what tells an open page to make the
trip". `GET /signin` is built in phase 2 for the development identity. The front server's
details, "The cookie key on one machine": with the development identity on and no cookie key
given, a restart makes every cookie unreadable; "the page's next request is answered
`front.not_signed_in`, it makes the trip, and `/signin` signs the development identity in
again at once, so nothing is lost". The architecture's table "The front server restarts" says
the same of one machine.

**The departure.** The wizard. Its details file built the trip in phase 3: "The page's code for
the trip is built in phase 3", and the module that makes every request passed
`front.not_signed_in` to its caller like any refusal.

**The evidence.** The front server started by hand as
[Running phase 2 on one machine](../../../front/README-details.md#running-phase-2-on-one-machine)
says, with no cookie key, is restarted after each `make -C wizard build`. A joined test that
restarts the front server with a new key while a page is open on the Layout step and then
enters the Preview step found the page on the Preview step showing "You are not signed in to
PenguinSlicer in this browser." with **Slice again** and **Back to Layout**, two buttons that
cannot help; the answers it had were `POST /api/slices` `401` and no trip. The page recovered
only if the user reloaded it.

**What hid it.** Neither fake keeps a sign-in: the browser fake answered `/` and every `/api/`
request whatever cookie came, so no test of the wizard's could meet `front.not_signed_in` from
a page that was signed in a moment before.

**What was done.** Fixed in the wizard, test first: `wizard/src/signing-in.js` and a hook in
`api.js`. A request answered `front.not_signed_in` notes the trip in the tab, goes to
`/signin?return=<the page's address>` at the next quiet moment (no pointer down, no field being
typed in), and is left unanswered, so nothing is shown; the page comes back on its stored step
with the plate as it was. Any other answer clears the note; a refusal while the note stands is
a trip that failed, shown as the refusal and not made again. The Node suite's
`tests/signing-in.test.js` and three tests in `tests/api.test.js` failed first. The browser
fake gained the sign-in (`new_cookie_key()`: every cookie set before becomes unreadable, `/`
sends a browser without one on the trip, `/signin` sets it), and
`test_a_request_answered_not_signed_in_makes_the_trip_and_comes_back_to_the_plate` in
`wizard/tests_browser/test_coming_back.py` fails without the fix and passes with it. The
joined test is `together/tests/test_browser_sign_in.py`. The wizard's details file and guide
now say the trip is built in its phase 2 form; the contract's words needed no change.

### 2. The stand-in Orca's sliced file had no layers a page could draw

**The words.** The sliced file's contract: the file "is what Orca Slicer exports for a sliced
plate"; `Metadata/plate_1.gcode` is "the G-code of the plate", its header carrying
`; total layer number: <n>`. The wizard's layer preview reads Orca's own markers in it
(`; CHANGE_LAYER`, `; Z_HEIGHT:`, `; LAYER_HEIGHT:`, `; FEATURE:`).

**The departure.** The slice service's stand-in Orca (`slice/tests/fake_orca.py`), on which the
joined suite runs. Its G-code was the header saying 42 layers and 2,000 moves with no layer
marker, so the preview found no layer and showed "PenguinSlicer could not read this plate's
sliced file to draw its preview." in place of the view.

**What hid it.** The wizard's fakes serve a sliced file the real Orca made
(`wizard/tests/sliced/spacer-1.gcode.3mf`), and nothing of the slice service's reads the
G-code beyond its header.

**What was done.** Fixed in the stand-in, test first in the slice service's suite
(`test_the_stand_ins_g_code_has_its_layers_in_the_pinned_orcas_markers` in
`slice/tests/test_orca_runner.py`, which failed on the old G-code): the same header and the
same 2,000 moves, now in 42 layers, each opened by the pinned Orca's markers, with relative
extrusion as Orca's `M83`. The slice service's whole fast suite passes with it.

### 3. The hand-written `done` report carries a stage the real one never has

**The words.** The progress report's contract makes `stage`, `stage_label` and `fraction`
optional and is silent on a final report. The hand-written examples
(`contracts/examples/wizard-front/slice-done.json`, `slice-events.txt`) give the `done` report
`stage` `reading_result`, its label and `fraction` 1.0. The slice service's real `done` and
`failed` reports carry none of the three (a `cancelled` one keeps the stage it ended at), and
the front server passes them unchanged.

**The departure.** The examples, written by hand before either side existed. No reader acts on
a final report's stage: the wizard's `slicing.js` reads only its `state`, `error`,
`cancel_reason` and `sliced_file`.

**What was done.** Left; the examples' README now says so, so that a later reader does not
take the example's stage as a rule. Changing the examples would move the fakes' default
answers under a dozen tests of the wizard's and the front server's for no reader's sake.

### 4. The slice service's first running report has no stage

**The words.** The progress report's contract: a job reports on every change of `state` or
`stage`; its table of a slice job's stages begins with `queued` and then `building_plate`; "a
stage a page does not know is shown by its `stage_label` alone". It is silent on a `running`
report with neither.

**What happens.** The slice service sends one `running` report with no `stage` at the moment the
slice starts, then `building_plate` (the `202` to a submission often carries it: seen here as
`{"state": "running", "sequence": 2, "elapsed_s": 0.0, "expected_s": 1.4}`). The wizard reads
it as an unknown stage, so for that moment the slicing card's stage line is blank and its list
marks only the first stage. With the stand-in it lasts milliseconds; with the real Orca the
plate is built before Orca starts, a fraction of a second on a small plate.

**The departure.** Neither side breaks a written rule; the contract does not say what such a
report means. Left, as a reading for the owner: the guides support either the slice service
sending `building_plate` from the first running report, or the wizard keeping the last stage
it showed until a report names one.

## What was checked and found to agree

- **Every request's headers.** `X-PenguinSlicer-Page` on every request,
  `X-PenguinSlicer-Group` on every request that acts for a group (none on `/api/me`,
  `/api/settings-table`), the wizard's mark on every changing request; the front server reads
  them as the contract says. The plain link of Download names the group in its query, and the
  real front server serves the file to it.
- **The version on every answer and on the stream.** Every answer of the real front server,
  redirects and refusals included, carries `X-PenguinSlicer-Version`; a stream's first event is
  `version`, then the latest report. Each start on one machine is a newer version.
- **The front server's codes.** Every code of phase 2 has the same status and `retryable` in
  the front server (`errors.FRONT_REPORTS`) and in the wizard's Node fake (`FRONT_CODES`).
- **The shapes of the answers.** The real `GET /api/me`, the part's record and the sliced
  file's details have exactly the keys of the examples the fakes answer with; the
  configuration answer has its four fields; the real reports differ from the examples only as
  mismatches 3 and 4 say, and in carrying fractions of a second, which the contract allows.
- **The table of settings.** The real table of 338 settings, passed by the front server
  unchanged, opens advanced mode; for every setting, every choice, both bounds and the value
  just past each, a text at its longest and one longer, and a value of the wrong form, the
  wizard's check of what a user types and the slice service's check of an override give the
  same verdict (1,299 values; `together/tests/test_browser_settings.py`). Settings changed
  in advanced mode reach the slice service in Orca's form (`0.20` as `0.2`, `35` as `35%`), and
  with the real Orca the sliced file carries them.
- **Failures.** The slice service's error report reaches the page's red message with its
  `message` and `remedy` as written, without its `detail`, with the wizard's buttons for its
  code, and its action slices again with the setting the action names.
- **Replacing, restarting and coming back.** A plate changed while it slices replaces its
  slice job (`cancelled`, `replaced`); one changed after is sliced afresh; the page shows the
  newest result and downloads its file. The slice container's restart rows behave as the
  architecture's table says.
- **A report the page makes about itself** is taken (`204`) and written as one line with the
  page's version.

## Which scenarios the joined suite adds

Beside the phase's "Done when" and the restart rows, the owner asked for two or three scenarios
of common use, chosen from what is least covered across both seams. Chosen:

1. **A slice that fails**, the slice service's report reaching the user's eyes unchanged with
   the right buttons, and its action slicing again. Each half had covered its own side only:
   the HTTP half that the report crosses the front server byte for byte, the wizard's suite that
   a hand-made report is drawn.
2. **A plate changed while it slices and after it is sliced**, the later slice replacing the
   earlier and the page showing the newest result and its download. Replacement had been
   shown only over HTTP, and the wizard's resubmitting only against a fake that answers every
   submission with the same example.
3. **Settings changed in advanced mode, and every setting at its bounds.** The review found
   this the least covered of all: the wizard's tests read a hand-written table of nine
   settings, the HTTP half sends only a configuration's own overrides, and the two checks of a
   value (the wizard's and the slice service's) were written separately against the contract's
   words.
4. **A page reloaded while its slice runs**, the third the owner named: it comes back to the
   Preview step following the same slice job, submits nothing again, and shows that slice
   job's result. The restart rows cover a closed page opened again only after the slice job
   was lost; none had shown a page keeping a slice job that still runs across a refresh.

The sign-in scenario of mismatch 1 is a fifth, added because the review found it.

## What only a fake still exercises

- **Expiry at two hours.** No joined test waits two hours; the front server's suite moves its
  clock, the wizard's its page's clock.
- **A refused progress stream** (`front.too_many_streams`, a fifth stream for one user) and the
  page's fall-back to asking.
- **The front server's limits on how fast** (`front.too_many_requests` with `Retry-After`)
  and the page's quiet retry after it.
- **A drawing summary** of a view: the page sends one only for a use whose frames were measured,
  which needs the user to move the view; the joined walk does not, and the wizard's own browser
  suite drives the views.
- **The previous release's page against the new front server**, which needs a second release.
- **The front server's restart rows that need a page** other than the sign-in: a page whose
  front server restarts with the same key sees a newer version and reloads at its next move
  between steps, which the wizard's suite shows against its fake.
