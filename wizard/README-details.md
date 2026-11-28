# The wizard: the builder's details

This is the builder's document for the wizard. The guide beside it,
[README.md](README.md), is what the owner reads and decides from; where the two differ, the
guide is right and this file is to be corrected. Of the wizard, only
[The project and its tools](#the-project-and-its-tools), the inputs of
[the trials](#how-the-trials-and-measurements-are-run), the second trial and the geometry it
tried ([The geometry, in a worker](#the-geometry-in-a-worker)) are built, and those sections
say what is true of them as built; everything else here is the design to build: every screen, state and message of the guide, in
the builder's terms, with the names the guide leaves out (requests, fields, error codes,
constants, stored records, tests), the figures, the tests each part needs, and an order in
which to build phase 2.

The **wizard** is the code in the browser. It talks to one thing only, the **front
server**, everything behind PenguinSlicer's one address ([its guide](../front/README.md)).
Every request and answer between the two is fixed by
[the contract between the wizard and the front server](../contracts/wizard-front-server.md),
and every shape that passes through it by the data contracts it names:
[the configuration](../contracts/configuration.md), [the part set](../contracts/part-set.md),
[the plate configuration](../contracts/plate-configuration.md),
[the table of settings](../contracts/settings-table.md),
[the error report](../contracts/error-report.md),
[the progress report](../contracts/progress-report.md) and
[the sliced file](../contracts/sliced-file.md). Where this file and a contract differ on a
name or a shape, the contract is right. From phase 4 the **Onshape integration**, the
component that makes PenguinSlicer work inside Onshape, hands the wizard the parts a user
picks there.

The phases are those of [the plan](../docs/plans/penguin-slicer-plan.md): phase 2, one
machine, parts from files, no sign-in and no printer; phase 3, hosted, with Onshape
sign-in; phase 4, inside Onshape's panel; phase 5, the real printer.

**How this file cites its sources.**

- "[decision N](../docs/mockups/print-wizard/DECISIONS.md#every-decision)" is numbered
  decision N of the mockup's decisions, version 8; "M18" is a question of
  [its "Please react to these"](../docs/mockups/print-wizard/DECISIONS.md#please-react-to-these),
  and "fake N" an item of
  [its "What is fake and could mislead"](../docs/mockups/print-wizard/DECISIONS.md#what-is-fake-and-could-mislead).
  A screen with a decision number follows that decision except where
  [Where this guide departs from the mockup's decisions](#where-this-guide-departs-from-the-mockups-decisions)
  says otherwise. A screen with no number is one the guide designed and the mockup never
  drew ([Screens designed in the guide](#screens-designed-in-the-guide)).
- A request is named by its method and path in the contract (`POST /api/slices`); an error
  code by its full name (`slice.busy`).
- "Open:" starts a line that names an item the guide or a contract leaves undecided or
  unmeasured, with a link to it. Do not build past it: build what the line says is safe and
  leave the rest.
- A name marked *proposed* (a constant, a stored record, a module, a test) is the builder's
  to choose. Names of requests, headers, fields and error codes are the contracts' and carry
  no mark. Every sentence in quotation marks is one the user reads, copied from the guide;
  a sentence another component writes is quoted as an example of its kind.

## Contents

- [Terms used below](#terms-used-below)
- [Constants](#constants)
- [The requests the wizard makes](#the-requests-the-wizard-makes)
- [The mockup: what is taken over and what is not](#the-mockup-what-is-taken-over-and-what-is-not)
- [The panel as a whole](#the-panel-as-a-whole)
- [Who writes the sentences of a failure](#who-writes-the-sentences-of-a-failure)
- [Every request: headers, answers and retrying](#every-request-headers-answers-and-retrying)
- [Progress streams](#progress-streams)
- [Signing in and signing out](#signing-in-and-signing-out)
- [The current group](#the-current-group)
- [The configuration and the table of settings](#the-configuration-and-the-table-of-settings)
- [The Parts step](#the-parts-step)
- [The Settings step](#the-settings-step)
- [The Layout step](#the-layout-step)
- [The geometry, in a worker](#the-geometry-in-a-worker)
- [The Preview step](#the-preview-step)
- [The layer preview](#the-layer-preview)
- [The Send step](#the-send-step)
- [The printer, from phase 5](#the-printer-from-phase-5)
- [When a user comes back](#when-a-user-comes-back)
- [Reloading for a new version](#reloading-for-a-new-version)
- [What the browser keeps](#what-the-browser-keeps)
- [Inside Onshape's panel and in a tab](#inside-onshapes-panel-and-in-a-tab)
- [Browsers](#browsers)
- [Accessibility](#accessibility)
- [Security](#security)
- [What the wizard reports about itself](#what-the-wizard-reports-about-itself)
- [What the other components must still provide](#what-the-other-components-must-still-provide)
- [Performance targets](#performance-targets)
- [The project and its tools](#the-project-and-its-tools)
- [How it is tested](#how-it-is-tested)
- [How the trials and measurements are run](#how-the-trials-and-measurements-are-run)
- [By phase](#by-phase)
- [Where this guide departs from the mockup's decisions](#where-this-guide-departs-from-the-mockups-decisions)
- [Screens designed in the guide](#screens-designed-in-the-guide)
- [Open items](#open-items)

## Terms used below

The plan's terms, the architecture's ([the architecture](../docs/architecture.md#terms))
and the guide's ([its terms](README.md#the-terms-this-guide-uses)) hold here. The ones this
file leans on:

- The **page** is the wizard as loaded in one browser tab or in Onshape's panel; the
  **panel** is the area it draws in.
- The **browser's storage** is the storage a browser gives a page that outlasts a refresh
  and a closed tab, kept for each browser and each address. What the wizard keeps there
  belongs to the signed-in user.
- A **plate** is the printer's bed and everything on it; each tab works with a plate of its
  own, named in the code by its **plate id** (the plate configuration's `plate_id`). A
  **stored plate** is a plate's record in the browser's storage.
- A **group** is the users who share one configuration and one printer; the **current
  group** is the one the user works in now. Advanced mode's collapsible sets of settings
  are **setting groups**, so that "group" has one meaning.
- The **user key** is the signed-in user's Onshape id, which the front server takes from
  the cookie. The page never names a user in a request.
- The **part store** is the slice service's cache of uploaded parts, each named by the user
  key, the SHA-256 hash of its bytes and its units label.
- A **slice job** is one plate configuration being sliced; a **submission** is one
  `POST /api/slices`, named by its `submission_id`. A **delivery job** is one sliced file on
  its way to one printer. The panel never says "job": it says "a slice", "a print", "a
  sliced plate".
- The **sliced file's details** are the object of that name in the contract
  ([The sliced file's details](../contracts/wizard-front-server.md#the-sliced-files-details)):
  the summary, the size, and the moment of expiry.
- A **progress stream** is one connection on which the page follows a slice job or a
  delivery job ([Progress streams](#progress-streams)).
- A **quiet retry** is a retry the user does not see for the first 20 seconds, as the
  contract defines it
  ([Retrying](../contracts/wizard-front-server.md#retrying-and-why-every-request-is-safe-to-repeat)).
- A **quiet moment** is one with no pointer down; no menu, joined box or confirmation open;
  and no field being typed in.
- The ways the panel says something are the guide's six: **notification**, **message**,
  **card**, **joined box**, **line** and **confirmation**
  ([How the panel tells the user something](#how-the-panel-tells-the-user-something)). The
  **panel line** is the one line under the step tabs.
- The **worker** is the second thread on which every heavy geometric job runs
  ([The geometry, in a worker](#the-geometry-in-a-worker)).
- The **fake clock** is the one clock every timer of the page reads, which a test moves;
  the **fake front server** is the stand-in a test drives, which answers, holds, drops or
  repeats each request and each event in the order the test sets. No test of the wizard
  uses the wall clock or a real network.

## Constants

Every figure the page's code uses, in one place, read through the fake clock where it is a
time. The names are the builder's (*proposed*) except those the plate configuration's
contract fixes (`MAX_*`, `MARGIN_MM`, `SPACING_*`).

| Name | Figure | What it bounds | From |
|---|---|---|---|
| `PANEL_MIN_PX` | 320 | The narrowest panel, with no sideways scroll | The plan |
| `WIDTH_TABS_PX`, `WIDTH_FIGURES_PX`, `WIDTH_COLUMNS_PX` | 480, 520, 680 | The three widths at which the layout changes, each including itself | [decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| `TOOLTIP_DELAY_MS` | 150 | Rest before a tooltip shows | [decision 63](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| `TOOLTIP_EDGE_PX` | 6 | Least gap between a tooltip and the panel's edge | [decision 63](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| `DETAILS_OPEN_MS`, `DETAILS_CLOSE_MS` | 150, 300 | The printer details opening on rest, closing after the pointer leaves | [decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon) |
| `PANEL_LINE_PASSING_S` | *proposed* 4 | The panel line's passing use, when the user does not move ("a few seconds") | [decision 3](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| `ROW_SLOW_S` | 4 | A part's row says "Taking longer than usual; still trying…" | [decision 17](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| `RETRY_QUIET_S` | 20 | Failed retries before the panel line shows | The guide |
| `RETRY_TOTAL_S` | 300 | Retrying in all, before "could not be reached"; also the resubmitting while the slice service stops | The guide |
| `RETRY_FIRST_WAIT_S`, `RETRY_MAX_WAIT_S` | 1, 30 | The waits between attempts, doubling from the first to the cap | The guide |
| `RETRY_SPREAD` | *proposed* 0.1 | A random spread on each wait, so that many pages do not retry in step after a restart | This file |
| `ATTEMPT_TIMEOUT_S`, `UPLOAD_ATTEMPT_TIMEOUT_S` | *proposed* 15, 60 | An attempt with no answer in this time counts as failed ("the time the builder sets" in the contract) | This file |
| `STREAM_REOPEN_FAIL_S` | 20 | A progress stream failing to reopen this long counts as a failed request | The guide |
| `STREAM_SILENT_S` | 45 | An open progress stream carrying nothing, not even a comment line, this long counts as failed | The guide; three times the front server's 15 seconds |
| `POLL_S` | *proposed* 2 | Asking for the latest progress report in place of a stream ("every second or two") | The guide |
| `PRINTER_POLL_S` | *proposed* 10 | Asking for the printer's status (phase 5), within the user's limit on status requests | The contract leaves it to the builder |
| `RELOAD_IDLE_S` | 120 | Time since the user last interacted before a reload for a new version | The guide; the contract |
| `PLATE_UNUSED_H` | 12 | A stored plate no tab holds, unused this long, is dropped; a new tab takes up only a plate used more recently | The guide |
| `SLICED_FILE_KEEP_S` | 7,200 | Two hours: the page's rule for telling the two "unknown" rows of a returning page apart | The guide |
| `LAST_PRINT_NOTE_H` | 12 | The last-print note and "Last print finished…" go | [decision 60](../docs/mockups/print-wizard/DECISIONS.md#the-users-last-print-version-7) |
| `STALE_S`, `OFFLINE_S` | 40, 120 | A print gone quiet; a printer Offline. The page shows what `GET /api/printer` and the delivery job's reports say (`stale`, `offline`) and does not time these itself | Printer delivery's figures |
| `MAX_PART_BYTES`, `MAX_PART_TRIANGLES` | 7,500,084, 150,000 | One part | [The plate configuration's limits](../contracts/plate-configuration.md#limits) |
| `MAX_PARTS`, `MAX_INSTANCES` | 25, 150 | Different parts, and instances, on one plate | The same |
| `MAX_PLATE_CONFIGURATION_BYTES` | 1,048,576 | One submission's body | [Limits in phase 2](../contracts/plate-configuration.md#limits-in-phase-2) |
| `MARGIN_MM`, `SPACING_MM`, `SPACING_SUPPORTS_MM` | 3, 5, 12 | The placement rules | [The plate configuration's limits](../contracts/plate-configuration.md#limits) |
| `MAX_SLICED_FILE_MB` | 50 | The largest sliced file kept; the page fetches nothing larger | The slice service's and the front server's figure |
| `MAIN_THREAD_HOLD_MS` | 250 | The longest the main thread may be held | The guide |
| `PATCHES_MS` | 100 | Patches appear after selecting one instance | The guide |
| `AUTO_ORIENT_MS` | 1,000 | A new part lies its best way after it arrives | The guide |
| `ARRANGE_MS` | 2,000 | Arrange at 150 instances | The guide |
| `FPS_GRAPHICS_CARD`, `FPS_SOFTWARE` | 30, 10 | The Layout view and the layer preview while moving | The guide |
| `FIRST_LAYER_S` | 5 | The first layer drawn after the Preview step opens on a sliced plate | The guide |
| `PAGE_MEMORY_MB` | 1,024 | The page at the largest plate with the layer preview of a 14.1 MB sliced file | The guide ("under 1 GB") |
| `REPORTS_PER_MIN` | *proposed* 4 | The page's reports about itself ("a few a minute") | The guide; the front server has its own limit |
| `POINTER_LINE_PX` | 11 | The pointer line's text, the one text under 14 px | [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms) |
| `HULL_EPS_MM` | 1e-6 | A corner this close to the hull is on it: far below the rounding of a single-precision STL coordinate, so that no corner of a real part is left outside its hull (1e-3 mm left corners up to 0.006 mm out) | The second trial |
| `FACE_JOIN_DEG` | 0.06 | Hull triangles joined into one flat face ("a fraction of a degree") | [The note on hull faces](../docs/research/2026-11-21-lay-on-face-hull-faces.md) |
| `FLAT_GAP_MM`, `FLAT_TURN_DEG` | 0.01, 1 | What lies on a face: a strip of the hull within this distance of a larger neighbour's plane and this angle of its direction is part of that face; a triangle of the part this near a hull face is the part's own surface there | The second trial |
| `MIN_FACE_MM2`, `MAX_FACES`, `SLIVER_DEG` | 5, 254, 1 | Faces dropped as too small, beyond the largest 254, or with a sliver corner | The guide; the sliver angle from the note |
| `ROUND_SIDE_DEG` | 20 | A facet among its like (a face it reaches through faces bending less than this is at least half its size) | The guide |
| `BBOX_COVER_DEG` | 30, plus 0.5 for rounding | A bounding-box side with no kept face within this angle gets a patch | The guide; [M29](../docs/mockups/print-wizard/DECISIONS.md#please-react-to-these) |
| `MIN_CONTACT_MM2` | 25 | A resting candidate counts for auto-orient; a flat face of the part this large is never dropped beside a hull face that bridges | The guide |
| `CONTACT_GAP_MM`, `OVERHANG_DEG` | 0.1, 45 | A triangle this close to the plate touches it; a downward triangle within this of straight down hangs over air | The mockup's score, kept |
| `HEIGHT_CHARGE_PER_MM`, `NO_CONTACT_PENALTY` | 0.01, 100 | Auto-orient's small charge for height and large penalty under `MIN_CONTACT_MM2` | The mockup's score, kept |
| `AS_MODELLED_MARGIN` | 0.05 | The part as modelled is kept when its cost is within this share of the best | The second trial |
| `PILE_GRID_MM`, `PILE_REFINE_MM` | 5, 1 | The pile packer's grid and refinement | The guide |
| `ARRANGE_CELL_MM`, `ARRANGE_SLACK_MM` | 0.5, 0.05 | Arrange's map of the plate in squares this wide; the room it leaves beyond the spacing | The second trial |

## The requests the wizard makes

Every request the page makes, in the contract's words, with the place in this file that
uses it and the phase that builds it. The page makes no other request, and never one to
another site.

| Request | For | Here | Phase |
|---|---|---|---|
| `GET /` | The page; with `in=onshape`, the Connect page from phase 4 | [Signing in](#signing-in-and-signing-out) | 2 |
| `GET /assets/<file>` | The page's code, styles and fonts, all fetched at load | [Reloading](#reloading-for-a-new-version) | 2 |
| `GET /signin?return=…` | The trip to Onshape; in phase 2 it signs in the development identity at once | [Signing in](#signing-in-and-signing-out) | 2, 3 |
| `POST /api/signout`, then `GET /signed-out` | Sign out, outside Onshape | [Sign-out](#sign-out) | 3 |
| `GET /api/me` | The user and their groups | [The current group](#the-current-group) | 2 |
| `GET /api/configuration` | The current group's configuration, with `source`, `name` and `revision` | [The configuration](#the-configuration-and-the-table-of-settings) | 2 |
| `GET /api/settings-table` | The table of settings and the profile catalog's names, with each printer's plate | [The configuration](#the-configuration-and-the-table-of-settings) | 2 |
| `POST /api/parts?units=…` | One part, checked and kept; answers its record | [Uploading a part](#uploading-a-part) | 2 |
| `POST /api/slices` | A plate configuration | [Submitting a plate](#submitting-a-plate) | 2 |
| `GET /api/slices/<slice>` | What became of a slice job; the fallback for its progress | [When a user comes back](#when-a-user-comes-back), [Progress streams](#progress-streams) | 2 |
| `GET /api/slices/<slice>/events` | A slice job's progress stream | [Progress streams](#progress-streams) | 2 |
| `GET /api/slices/<slice>/summary` | The sliced file's details | [The result](#the-result) | 2 |
| `GET /api/slices/<slice>/file` | The sliced file, for the layer preview and for Download | [The layer preview](#the-layer-preview), [The Send step](#the-send-step) | 2 |
| `POST /api/reports/failure`, `POST /api/reports/drawing` | The page's reports about itself | [What the wizard reports about itself](#what-the-wizard-reports-about-itself) | 2 |
| `GET /api/printer` | The printer's status, its current print and its last print | [The printer-status icon](#the-printer-status-icon) | 5 |
| `POST /api/printer/pairing`, `DELETE /api/printer/pairing` | Pair and unpair | [Pairing a printer](#pairing-a-printer) | 5 |
| `POST /api/printer/deliveries` | Send | [After Send](#after-send) | 5 |
| `GET /api/printer/deliveries/<delivery>`, `…/events` | A delivery job's progress | [After Send](#after-send) | 5 |
| `POST /api/printer/deliveries/<delivery>/cancel` | Cancel sending | [After Send](#after-send) | 5 |
| `POST /api/printer/deliveries/<delivery>/stop-following` | Stop following, by the sender | [A print that has gone quiet](#a-print-that-has-gone-quiet) | 5 |
| `GET /api/printer/mine` | The user's live delivery job and last print, for a returning page | [When a user comes back](#when-a-user-comes-back) | 5 |

There is no request to cancel a slice job, none to read a user's groups again, and none to
write the configuration that the wizard uses: `PUT /api/configuration` exists for the
configuration's edit screens, which are in no phase yet.

## The mockup: what is taken over and what is not

[The mockup](../docs/mockups/print-wizard/index.html), version 8, is the reference for the
look: the wizard looks the same, with the same layout, elements, order, colours, type and
wording at each width; small differences of pixels are acceptable where there is a good
reason ([The mockup, this guide and Orca](README.md#the-mockup-this-guide-and-orca)). Its
scripts were faked, so the behaviour is built from the guide and this file. For the Layout
and Preview steps, where neither says what should happen, the behaviour is Orca's; an
implementer may read Orca's source to understand a method and never copies its code
(Orca is under the AGPL and PenguinSlicer under MIT).

| File of the mockup | What it carries | Taken over |
|---|---|---|
| [index.html](../docs/mockups/print-wizard/index.html), from `#wizard` down | The markup of every screen of the panel: `#wiz-header` (with `#pstat`, `#config-info`, `#stepbar`, `#step-why`, `#pstat-pop`), `#wiz-body` (`#wiz-summary`, `#chg-pop`, `#last-print`, `#notices`), each step's body, `#wiz-nav` (`#btn-back`, `#btn-next`, `#final-action`), `#advanced` | Its structure and wording, as the template of each screen. The rest of the file (`#scenario`, `#frame`, `#standalone`) is the mockup's stand-in page and is not taken |
| [css/panel.css](../docs/mockups/print-wizard/css/panel.css) | The panel's whole look: PenguinCAM's light theme, the header and the compact stepper, the printer-status icon and its details, the body and plate summary, notifications, each step, the panel's own tooltip, the Send step's cards, Back and Next, advanced mode, the wider panel | Taken over as the wizard's style sheet, the cheap way to match. Its rules are on the panel by container queries |
| [css/frame.css](../docs/mockups/print-wizard/css/frame.css) | The page around the panel: the scenario strip and the stand-in Onshape tab | Not taken |
| [js/wizard.js](../docs/mockups/print-wizard/js/wizard.js) | How each screen is put together and changes: the steps, advanced mode, the faked export, progress, the Send step, the printer-status icon | A reference for the look and order of each screen and state; the behaviour is this file's |
| [js/layout3d.js](../docs/mockups/print-wizard/js/layout3d.js) | The Layout view: selecting, dragging, the rotation handle, the patches, the view buttons, the gestures | A reference for how the gestures feel; rewritten against real parts, in the worker's terms |
| [js/plate.js](../docs/mockups/print-wizard/js/plate.js) | The placement rules and Arrange on the mock parts | A reference; its outlines were thinned to 40 points (fake 10) and are not to be kept |
| [js/hullfaces.js](../docs/mockups/print-wizard/js/hullfaces.js) | Faces on the hull, written from the project's own note | A reference for the method of [Finding the faces](#finding-the-faces-a-part-can-lie-on) |
| [js/preview3d.js](../docs/mockups/print-wizard/js/preview3d.js) | Faked toolpaths and a layer preview drawn as flat strips | The colours and the controls only; its method of drawing is known not to be good enough |
| [js/parts.js](../docs/mockups/print-wizard/js/parts.js), [js/settings.js](../docs/mockups/print-wizard/js/settings.js), [js/frame.js](../docs/mockups/print-wizard/js/frame.js) | The mock parts, a sample of settings, the stand-in Onshape tab | Not taken |

Each screen below names the mockup's decision it follows; its markup is the matching part
of `index.html` and its style the matching section of `css/panel.css`.

## The panel as a whole

### Width, look and the three widths

- The panel is fluid, measured on the panel by container queries and never on the window,
  so dragging Onshape's panel wider changes the layout exactly as widening a window would
  ([decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)). It works at 320 px
  with no sideways scroll and nothing cut off.
- The look is PenguinCAM's light theme
  ([decision 1](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)), as `css/panel.css`
  holds it: background `#f6f8fa`, cards `#ffffff`, controls `#eef1f4`, lines `#d0d7de`, text
  `#1f2328` and `#5a6570`, accent `#2f81f7`; body text 14 px, line height 1.45, PenguinCAM's
  font stack (which starts with the system's font, so the panel differs slightly by
  system); step tabs and pills 12 px; step title 18 px; buttons 8 by 14 px, radius 6 px; body
  padding 14 px. Amber text is `#9a6700` (the borders keep `#d29922`), and a step tab's hover
  is light. The project documents' dark house style does not apply to the wizard.

| From | What changes | Mockup |
|---|---|---|
| 480 px | The step circles become named tabs. Settings step: Filament and Profile side by side, the quick changes two to a row. Advanced mode: the rail of section names in place of the accordion | [decision 3](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 12](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| 520 px | The Send step's print figures (percent, layer, time left) in one row. The Layout and Preview views 4:3 instead of square | [decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 25](../docs/mockups/print-wizard/DECISIONS.md#layout-step) |
| 680 px | The Parts step's list in two columns; the Send step in two columns | [decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |

Tests: each width at its own figure and one pixel under it (320, 479, 480, 519, 520, 679,
680), every step rendered and checked for no sideways scroll; a panel resized across 480 px
keeps advanced mode's open and closed sections.

### The header

The same on every step ([decision 2](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)):
line one, "PenguinSlicer" and, at its right from phase 5, the printer-status icon; line
two, "Config: " and the configuration's `name` from `GET /api/configuration` ("Config: 6238
(Popcorn Penguins)", or "Config: PenguinSlicer default" when its `source` is `"default"`),
with the reload glyph; then the step tabs. For a user in one group the name is plain text;
for a user in several groups outside Onshape it is a button that opens the group details
([The current group](#the-current-group)).

**The step tabs** ([decision 3](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)).
From 480 px: number, name, and a check mark after a finished step's name; no tooltip.
Below 480 px: five numbered circles joined by a line, a check in each finished one, the
current one filled in the accent blue with its name beside it. Every circle is clickable;
every circle but the current one has its step's name as its tooltip ("3. Layout"), shown at
once on keyboard focus. A click goes to the step when every step before it allows it.

**The panel line**, one line under the tabs (`#step-why` in the mockup), has two uses.

| Use | Shows | Goes | Mockup |
|---|---|---|---|
| Passing | The step that holds a click on a tab, and why: "Layout first: 23 instances are closer than 12 mm with supports on." | At the user's next move, or after `PANEL_LINE_PASSING_S` | [decision 3](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| Lasting | The retry messages ([Retrying](#retrying)), with their link or button | When a request is answered | None: designed in the guide |

When both apply, the lasting use is shown and the passing one is not.

**The plate summary** ([decision 4](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)).
None on the Parts step. From the Settings step on, two lines, updated at once: "1 part · 1
instance"; then "PETG · Structural" and, while there are changes, the pill "+2 changes". A
filament or profile name too long is cut with an ellipsis, never wrapped, its full name its
tooltip; the pill is never cut; the second line is as tall as the pill without it. No plate
area, print time or grams. The pill is a button that opens the **change details**, a
joined box: one plain line for each change, "Quality › Resolution: 0.014 mm (profile 0.012
mm)", a setting with a quick change named in the quick change's words, "Others › Brim: Off
(profile Auto)"; closed by a click elsewhere, Escape or the pill again. Opening the printer
details closes it ([decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon)).
The section and label of each line come from the table of settings; "profile" is the
profile's value as [The profile's value of a setting](#the-profiles-value-of-a-setting)
defines it.

**Back and Next** at the bottom of every step: Next off until the step's rules pass, the
step saying why; a part still arriving never holds Next; Back off on the Parts step
([decision 5](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)).

Tests: the summary updates on every change; the pill opens and closes the change details by
each of its three ways; a long profile name is cut and has its tooltip; nothing below the
summary moves when the pill comes or goes; a held tab click shows the passing line, which
goes at the next move and after `PANEL_LINE_PASSING_S` on the fake clock; with the retry
message showing, a held click shows no passing line.

### How the panel tells the user something

Each kind of news always uses the same way. The page's code has one component for each
(*proposed*), and every screen below names which it uses.

| Way | What it is | Used for | Mockup |
|---|---|---|---|
| Notification | A card at the top of a step, under the plate summary, closed with × | Something that happened and is on no row. It belongs to its step and goes when the user leaves the step or as soon as it stops being true | [decision 7](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| Message | A block in a step's body: one sentence of what happened, one of what to do, its buttons. Red when it holds Next, amber for a caution, grey when it only informs, green when something was done | A problem on the plate, a slice that failed, a printer that cannot take a send, a sign-in that could not be made | [decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Card | A white bordered box that holds a state for as long as it lasts | The slicing card, the print card, the busy card | [decision 30](../docs/mockups/print-wizard/DECISIONS.md#preview-step), [decision 41](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Joined box | A small box joined to the header element or icon it belongs to | The printer details, the change details, the colour key, and the group details | [decision 4](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon) |
| Line | One short sentence in a fixed place | A consequence the user cannot see; the panel line | [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |
| Confirmation | A small box joined to the pressed control: the question in one or two sentences, a button that goes ahead and one that keeps things; Escape or a click elsewhere keeps things | New plate and changing the current group when there is work to lose, Reset all, Stop following, Unpair | None: designed in the guide |

"Details", with a capital, is only the folded part of a message, opened by the word
"Details" ([decision 58](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6)).
Exactly three messages carry it: the two empty-layers slice failures and a failed print
([decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step)).

**Tooltips** ([decision 63](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)): the
panel's own white box (1 px `#d0d7de` border, radius 8 px, the printer details' shadow), at
14 px, after `TOOLTIP_DELAY_MS` of rest, and at once on keyboard focus of an icon or a step
circle; gone on leave, press, Escape or loss of focus; under its element, or above where the
panel ends, at least `TOOLTIP_EDGE_PX` inside the panel. A tooltip says only what is not on
screen: an element whose text shows in full has none, and one whose text is cut short shows
the whole text. Options inside an open menu keep the browser's tooltip. Touch shows none, so
nothing a user needs is in a tooltip alone.

Tests: a tooltip at 150 ms of rest and not at 149 on the fake clock; at once on keyboard
focus; at a panel edge it stays 6 px inside a 320 px panel; an element whose text shows in
full has none; each confirmation keeps things on Escape and on a click elsewhere.

### The words it uses

- **No role words:** no sentence the wizard writes says "student", "mentor", "team" or
  "administrator"
  ([decision 58](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6),
  with the departure for "administrator"). A group's name is shown as the group wrote it.
- **Little help text, generous errors**
  ([decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6)):
  no line under a step title or under a control; a line only where an action has a
  consequence the user cannot see, each named at its step. Errors say what is specific
  (which part, what about it, where to look), never generic troubleshooting or internals.
- **Nothing is said about orientation**
  ([decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6)):
  only a move the wizard made that the user did not ask for.
- **"A new plate"**, never "a second plate", wherever the remedy is another plate; no plate
  is numbered.

### Units

A part's units (`"in"` or `"mm"`) are a label that travels with it: the Part Studio's or
Assembly's from phase 4, or for an uploaded file the switch beside the upload area. The
wizard never guesses units from a part's size
([decision 50](../docs/mockups/print-wizard/DECISIONS.md#units-version-6)).

| What | Shown in | Mockup |
|---|---|---|
| A part's own size, the selected instance's footprint and height, a patch's pointer line | The part's units: inches to three decimals ("2.000 × 2.000 × 0.188 in"); millimetres to 0.1 mm | [decision 52](../docs/mockups/print-wizard/DECISIONS.md#units-version-6), [decision 53](../docs/mockups/print-wizard/DECISIONS.md#units-version-6), [decision 54](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) |
| Printer and plate figures: plate size, height limit, spacing, distances between instances, a height above the plate, the layer readout | Millimetres; heights and spacing to 1 mm, distances to 0.1 mm | [decision 55](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) |
| A part's figure set against a printer's | Both in millimetres, the part's inches in brackets: "stands 352.7 mm (13.885 in) tall; the printer prints up to 340 mm" | [decision 54](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) |
| Slicing settings, and Orca's own sentence under Details | Millimetres | [decision 56](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) |

A size is rounded once, from the exact millimetres, in the unit shown, by one function
(*proposed* `formatSize`) used on every step, so a part has one size everywhere; a size wraps
and is never cut short.

Tests: the 6.35 mm Gusset Plate reads 0.250 in on every step; a part in millimetres shows
millimetres; a too-tall instance of an inch part shows both units; the layer readout is in
millimetres on an inch plate.

## Who writes the sentences of a failure

**The component that failed writes the sentences.** Every failure arrives as an
[error report](../contracts/error-report.md). The wizard shows its `message` and `remedy` as
they are, as text: it never rewords them, never replaces them with its own made from the
`code`, and never shows `detail`. The one other field of a report a user may read is
`orca_sentence`, on the two empty-layers failures only, under their Details, marked as
Orca's ([Orca's own sentence under Details](#orcas-own-sentence-under-details)). What the
wizard adds is its own: where the report appears, its colour, a button for the report's
`action`, and its own buttons for moving about (Back to Layout, Back to Parts, Back to
Settings). The page acts on a report's `code` and `retryable`, never on the status alone.

| The failure is | Codes | Sentences by | The wizard |
|---|---|---|---|
| The slice service's: a part refused or warned about, a plate refused, a slice that fails, runs too long, runs out of memory or would give too large a file, no room to wait, the slicer stopping | `slice.*` | The slice service | Shows them as they are |
| Printer delivery's, from phase 5: a send refused, a print that failed or waits for a person, a wrong pairing code, a limit passed | `delivery.*` | Printer delivery | Shows them as they are |
| The front server's own: a sign-in that could not be made, a group the user is not in, a sliced file that has expired or would be too large | `front.*` ([its list](../contracts/wizard-front-server.md#the-front-servers-error-reports)) | The front server | Shows them as they are |
| The Onshape integration's, from phase 4: a part Onshape cannot export | Named in phase 4 | The Onshape integration | Shows them as they are |
| In the browser: no answer from the front server, the page's own checks before sending (a file over the size limit, a twenty-sixth part, a plate over 150 instances), every placement problem on the Layout step, a file the page itself cannot read, a 3D view that is lost, storage that fails | None: the wizard's own, gathered in one module (*proposed* `messages`) | The wizard | Writes them |

States that are not failures are the wizard's to put into words, from the figures it is
sent: a slice waiting behind others or waiting while the slicer restarts, a busy printer, a
printer not heard from, a print gone quiet, no printer paired, a sliced plate that expired
while the page was open. A sentence written on a server says "your CAD program", never
"Onshape"; only the Onshape integration's name Onshape. Some sentences of the slice service
and of printer delivery still say "the print server" or use old role words; the wizard shows
them as written until those components change them.

Tests: for each kind of error report, the fake front server answers with sentences the test
made up, and the test checks that exactly those sentences appear, as text and not markup,
with the button the report's `action` calls for and the wizard's own buttons for that code;
a report's `detail` never appears; an `orca_sentence` appears only on the two empty-layers
codes, under Details; a code the page does not know is shown as the last row of
[When a slice fails](#when-a-slice-fails) and not retried.

## Every request: headers, answers and retrying

### What every request carries

The contract's [Rules for every request](../contracts/wizard-front-server.md#rules-for-every-request)
hold for every request the page makes; one module (*proposed* `api`) makes every request, so
that each rule is written once.

| Header | Sent | Meaning |
|---|---|---|
| `X-PenguinSlicer-Page` | On every request | The page's own version, from the `<meta name="penguinslicer-version">` of the page it loaded |
| `X-PenguinSlicer-Group` | On every request that acts for a group | The current group's `id`, exactly as `GET /api/me` gives it. For a plain download link, the query parameter `group` instead |
| `X-PenguinSlicer-Wizard: 1` | On every `POST`, `PUT` and `DELETE`, from phase 2 | The wizard's mark. The front server checks it, and the origin, from phase 3 |
| `X-PenguinSlicer-In: onshape`, `X-PenguinSlicer-Onshape-Document`, `X-PenguinSlicer-Onshape-User` | From the page in Onshape's panel, phase 4 | See [Inside Onshape's panel](#inside-onshapes-panel-phase-4) |

The page never reads the cookie or `Set-Cookie`; the browser attaches the cookie. Every
answer of the front server carries `X-PenguinSlicer-Version`; the page compares it with its
own and acts as [Reloading for a new version](#reloading-for-a-new-version) says. A
successful answer is JSON except the sliced file and the progress streams; the page ignores
any field it does not know. A time is RFC 3339 in UTC; a length of time is whole seconds in a
field ending `_s`; where the page must act at a moment the front server reckons, it counts the
answer's seconds on its own clock from the moment the answer arrived.

### Retrying

**The page retries,** so that a request falling in the gap of a deploy is repeated and the
user sees a pause, not an error
([When the server is slow or cannot be reached](README.md#when-the-server-is-slow-or-cannot-be-reached)).

**What is a quiet retry** (the contract's list): an attempt with no answer within
`ATTEMPT_TIMEOUT_S` (`UPLOAD_ATTEMPT_TIMEOUT_S` for `POST /api/parts`) or whose connection
fails; an answer without `X-PenguinSlicer-Version`, which is not the front server's; and an
error report with code `front.slice_unreachable`, `front.state_bucket_unreachable`,
`front.onshape_unreachable` (on an `/api/` request), `front.too_many_requests` or
`front.unexpected`. An answer with `Retry-After` is not tried again before that many
seconds. Every other error report, `retryable` or not, is shown and not retried by itself:
`slice.busy` above all, and printer delivery's refusals of a send, since nothing queues.
`slice.stopping` is resubmitted by its own rule
([While the slice service is stopping](#while-the-slice-service-is-stopping)). The page's
reports about itself are never retried, and a progress stream is reopened, not retried.

| Time since the request first failed | What the user sees |
|---|---|
| Up to `RETRY_QUIET_S` (20 s) | Nothing, except on the thing that is waiting: a part's row says "Taking longer than usual; still trying…" after `ROW_SLOW_S` (4 s) |
| 20 to 300 s | The panel line, in amber: "The server is being slow. Your browser is retrying in 28 s.", the figure counting down each second to the next attempt, with a link, **Retry now** |
| After `RETRY_TOTAL_S` (300 s) | The panel line, in red: "The server could not be reached.", with one button, **Try again**, which makes an attempt at once and starts the 300 seconds afresh |

- **Waits** between attempts: 1, 2, 4, 8, 16, then 30 seconds, capped at `RETRY_MAX_WAIT_S`,
  each with a random spread of up to `RETRY_SPREAD`. So attempts fall at about 1, 3, 7, 15,
  31, 61, 91 … 271 seconds after the first failure; the message appears at 20 seconds,
  counting down to the attempt at 31; no attempt is made after 300.
- **Retry now** makes the next attempt at once and does not restart the 300 seconds; the
  countdown then runs to the following wait.
- **The 300 seconds are counted for each request;** the panel line shows the countdown of
  the request that failed earliest, and goes the moment any request of the page's is
  answered.
- The message is the wizard's own, since no component answered to write one; "the server"
  is the front server. It is on the panel line, not a notification, because it concerns the
  whole panel and must stay as the user moves between steps.
- **Nothing of the user's work is dropped:** the parts, the layout and the settings are in
  the browser's storage, a part whose upload stopped keeps its row, and everything that
  needs no server (laying out the plate, changing settings) goes on working.
- These times cover every request a user waits on (adding a part, submitting a plate,
  fetching a sliced file or its details, sending, cancelling a send, pairing, unpairing)
  and the reads the page makes by itself (`/api/me`, the configuration, the table of
  settings, a slice job's state, the printer's status).

**Every request is safe to repeat,** as the contract requires, and the page makes it so on
its side: a part is uploaded again with the same bytes and units; a submission is repeated
with the same `submission_id`; a pairing or a send repeated after a lost answer is
recovered as [Pairing a printer](#pairing-a-printer) and [After Send](#after-send) say.

Tests (fake clock; the fake front server dropping, holding or refusing answers):

- A request that fails once and succeeds on the attempt at 1 s shows nothing.
- At 19.9 s of failures the panel line is empty; at 20 s the amber line shows, counting down
  to the attempt at 31 s, the figure falling by one each second the clock moves.
- The waits are 1, 2, 4, 8, 16, 30, 30 … seconds within the spread; no attempt after 300 s.
- At 300 s the red line and Try again; Try again attempts at once and restarts the count (a
  further 20 s of failures shows the amber line again). Retry now attempts at once and does
  not restart the count.
- `Retry-After: 7` holds the next attempt for 7 s.
- An answer without `X-PenguinSlicer-Version` is retried; each quiet-retry code is retried;
  `slice.busy`, a `delivery.*` refusal and an unknown code are shown at once.
- A part's row says "Taking longer than usual; still trying…" at 4 s and not at 3.9 s; after
  300 s the row keeps its part and Try again retries it.
- The line goes the moment any request is answered.
- The stored parts, layout and settings are unchanged after 300 s of failures, and the
  Layout step works throughout.
- A repeated request (the answer lost, the request sent again) leaves the page in the state
  of one request: one part row, one slice job followed.

## Progress streams

A **progress stream** is `GET /api/slices/<slice>/events` (from phase 5 also
`GET /api/printer/deliveries/<delivery>/events`), server-sent events opened with `fetch`, so
that it carries the same headers as any request and a refusal arrives as an error report
([Progress streams](../contracts/wizard-front-server.md#progress-streams)).

- The first event is `version`, the front server's version, compared as for any answer.
  The second is the latest [progress report](../contracts/progress-report.md) at once. Each
  `progress` event's `id` is the report's `sequence`: a report whose `sequence` is not above
  the last one the page holds is ignored; a gap is harmless, since every report is whole.
- Comment lines (`:`) arrive at least every fifteen seconds while there is nothing to report.
- After a final report (`done`, `failed`, `cancelled`) the front server closes the stream.
  **A stream that closes before a final report is reopened silently,** at once and then with
  the waits of [Retrying](#retrying), since streams are closed routinely by the hosts' time
  limits and at every restart of the front server.
- **A stream counts as a failed request** once `STREAM_REOPEN_FAIL_S` (20 s) have passed since
  the first failure to reopen it, or once it has been open and carried nothing, not even a
  comment line, for `STREAM_SILENT_S` (45 s); a silent stream is then closed and reopened.
  From that moment the panel line shows as for any failed request, the page keeps reopening
  for up to 300 seconds, the slicing card says there is no news and the print card greys its
  figures.
- **Asking instead of following.** The same reports can be had by asking
  `GET /api/slices/<slice>` (from phase 5 `GET /api/printer/deliveries/<delivery>`) every
  `POLL_S`. Build both behind one interface (*proposed* `followJob`) that delivers reports to
  the screens the same way, and use the stream. Open: whether Cloudflare and Railway pass a
  stream on unheld, settled with one slice on the hosted service in phase 3
  ([Whether progress reaches the page unheld when hosted](README.md#whether-progress-reaches-the-page-unheld-when-hosted));
  if not, asking becomes the means.
- **A fifth progress stream** is refused with `429` `front.too_many_streams`, which is not a
  quiet retry. Open: what the page then shows
  ([Open items of the other guides](README.md#open-items-of-the-other-guides-that-would-change-the-panel));
  until it is settled, the page follows that job by asking every `POLL_S` and shows nothing
  of the refusal, which needs nothing new of the front server.

Tests (the fake front server closing, silencing and refusing streams at chosen moments): a
stream closed mid-slice is reopened and the page shows the latest report at once; a repeated
`sequence` is ignored; the close is never shown; failing to reopen for 19.9 s shows nothing
and 20 s shows the panel line; an open stream silent for 44.9 s shows nothing and 45 s counts
as failed; comment lines every 15 s keep it alive indefinitely; a `version` event newer than
the page's sets the reload going; `front.too_many_streams` falls back to asking.

## Signing in and signing out

What the user sees is the guide's [Signing in](README.md#signing-in); the requests are the
contract's [Signing in and signing out](../contracts/wizard-front-server.md#signing-in-and-signing-out).

**Phase 2.** The front server signs in a fixed made-up user and group, the development
identity. `GET /` without a cookie answers `302` to `/signin`, which sets the development
identity's cookie and returns at once; `GET /api/me` names that user and group. The wizard
opens straight on its first step, with no sign-in screen and no Sign out link. The page's
code for the trip is built in phase 3, but every request already goes through the module that
will handle `front.not_signed_in`.

**From phase 3, outside Onshape:**

| Case | What the page does | What the user sees |
|---|---|---|
| Opening the wizard with no sign-in | `GET /` answers `302` to `/signin?return=…`; the trip goes to Onshape and back to the same address | Nothing of PenguinSlicer's; the first time, Onshape's request to allow PenguinSlicer to read who they are, the companies and classrooms they belong to, and their documents |
| A request answered `401` `front.not_signed_in` on an open page (the sign-in ran out, or every sign-in was ended by replacing the cookie's key) | Waits for a quiet moment, notes in the browser's storage that it is making a trip (*proposed* record `signInTrip`, with the time), and goes to `/signin?return=<the page's address>`. The plate and its step are already in the browser's storage, so the page returns to the same step with the plate as it was | A moment's navigation and nothing else |
| The page comes back and its first request is again `front.not_signed_in` while `signInTrip` is set | Takes the trip as failed and does not leave again by itself, so a browser that withholds the cookie cannot repeat sign-ins without end. It replaces the step's content with a message holding that report's `message` and `remedy`, "Your parts, layout and settings are kept in this browser.", and **Sign in with Onshape**, a link to `/signin` with the same `return` | A message in place of the step; the header keeps its first line; from phase 5 the printer-status icon a grey dot and "…" |
| The trip itself fails: the user refuses Onshape's request, Onshape does not answer, or the returned value is wrong | Nothing: the front server serves the **failed sign-in page** at its callback, with `front.sign_in_refused`, `front.onshape_unreachable` or `front.sign_in_failed`, and Sign in with Onshape | The front server's sentences, of this kind: "PenguinSlicer could not sign you in with Onshape.", then what is specific, then "Your parts, layout and settings are kept in this browser." |
| A sign-in that succeeds | Clears `signInTrip`; reads `GET /api/me`; if `user.id` is not the user the stored work belongs to, clears every stored plate and the stored current group before showing anything ([What the browser keeps](#what-the-browser-keeps)) | The wizard on the step the user was on; a different user starts with an empty plate |
| Safari | Nothing: `GET /` answers a plain page saying that PenguinSlicer needs Chrome, with none of the wizard's code | That page |

A sign-in outside Onshape lasts thirty days from its last use, moved on by the front server's
`Set-Cookie`, which the page ignores.

### Sign-out

Outside Onshape, from phase 3, a quiet **Sign out** link sits at the foot of every step,
under Back and Next; inside Onshape's panel there is none. It sends `POST /api/signout` (with
the wizard's mark) and then goes to `/signed-out`, the front server's plain page with the
header's first line, "You are signed out of PenguinSlicer.", and **Sign in with Onshape**.
Nothing on that page leaves for Onshape by itself. The stored work is left where it is: it is
shown again only to the same user, dropped after `PLATE_UNUSED_H` without use like any stored
plate, and cleared when a different user signs in.

### Inside Onshape's panel (phase 4)

- `GET /?in=onshape&…` with no sign-in answers the **Connect page**, the front server's
  plain page with one button, **Connect**, which opens `/signin?window=1&return=/` in a small
  window. The window makes the trip and tells its opener `{"penguinslicer": "signed_in"}` or
  `{"penguinslicer": "sign_in_failed", "report": …}` and closes itself; the opener accepts a
  message only from the front server's own address. On `signed_in` the Connect page reloads
  itself, or an open page goes on with the request that was refused; on `sign_in_failed` the
  panel shows the report's sentences in place of the step, with Connect.
- An open page in the panel that meets `front.not_signed_in` shows Connect in place of the
  step's content, since a panel cannot leave for Onshape unseen.
- Every request from the panel carries `X-PenguinSlicer-In: onshape`, the document's id in
  `X-PenguinSlicer-Onshape-Document`, and, when Onshape tells the panel, the user in
  `X-PenguinSlicer-Onshape-User` and the company in `X-PenguinSlicer-Group`. A different
  person signed in to Onshape is answered `front.not_signed_in`; after Connect, `/api/me`
  names the new user and the page clears the previous user's stored work.
- The sign-in lasts as long as the user is signed in to Onshape; there is no Sign out link.
- Open: whether Onshape tells a panel the user and the company, and whether the trip can be
  made inside the panel without the user seeing it
  ([To be confirmed inside Onshape, in phase 4](README.md#to-be-confirmed-inside-onshape-in-phase-4)).
  Build Connect; send the user and group headers only when Onshape gives them; if the unseen
  trip works in real Chrome, Connect goes.

Tests: on the fake clock with the fake front server, a `front.not_signed_in` while a pointer
is down starts no navigation until the pointer is up and no menu, joined box, confirmation or
typed field is open; the navigation goes to `/signin` with the page's address as `return` and
sets `signInTrip`; a page loaded with `signInTrip` set whose first request is again refused
shows the message with that report's sentences and does not navigate; a successful return
clears `signInTrip` and opens the stored step with the plate unchanged; a `/api/me` naming a
different `user.id` clears every stored plate before anything is drawn; Sign out sends the
mark and goes to `/signed-out`; inside the panel a refused request shows Connect, and a
message from another origin is ignored.

## The current group

`GET /api/me` gives the user and their groups, at least one, in a fixed order; the first is
"the first of the user's groups". The current group is sent as `X-PenguinSlicer-Group` on
every request that acts for a group
([The current group](../contracts/wizard-front-server.md#the-current-group)).

- **A user in one group**, which is nearly every user, has nothing to manage: the header's
  second line names the configuration in use as plain text, with no group details, no list,
  no "Signed in as" and nothing to choose.
- **Inside Onshape** (phase 4) the current group is the group of the document the user has
  open, sent as `X-PenguinSlicer-Group` when Onshape gives the company and otherwise found by
  the front server from the document. No choice is offered, even to a user in several groups.
  The front server reads the user's groups again itself when the panel names a company the
  sign-in does not list.
- **The configuration is always usable.** The header names `GET /api/configuration`'s `name`;
  when `source` is `"default"` it says "Config: PenguinSlicer default". The wizard has no
  screen for a saved configuration that cannot be read: the front server serves the default
  in its place.
- **The reload glyph** reads `GET /api/configuration` again. If the chosen filament or profile
  is gone from it (compared by name, exactly), the first filament or the filament's first
  profile takes its place and a notification says which.

### A user in several groups, outside Onshape

| Screen or state | What the page does and shows |
|---|---|
| The header's name | A button that opens the **group details**, a joined box: the user's groups from `/api/me`, one to a row, the current one checked. A click on another makes it the current group; a click elsewhere, Escape or the name again closes the box |
| The choice | Kept in the browser's storage (*proposed* record `currentGroup`), and the group a newly opened tab starts in. The change is made in one tab; another open tab goes on with its own group and its own plate |
| Changing the current group with work to lose (parts on the plate, or a slice job) | A confirmation: "Change to FRC 1678? Your parts, layout and settings are cleared." Going ahead clears everything: the parts, the layout, the settings and the slice, and starts a new plate with a new `plate_id` ([What the browser keeps](#what-the-browser-keeps)). With nothing to lose, no confirmation. A plate already sent goes on printing at its own printer; the printer-status icon now shows the new group's printer |
| A group the user no longer belongs to: a request answered `403` `front.group_not_allowed` | The page takes the first of the user's groups from `GET /api/me`, with an empty plate as after any change of group, and says so in a notification: the front server's sentence ("You are no longer in 6238 (Popcorn Penguins).") then the wizard's own, "PenguinSlicer now uses FRC 1678's configuration and printer." |

Tests: a user with one group sees plain text and no button; a user with two sees the button,
and the group details by each of their ways; changing group with parts shows the
confirmation and, confirmed, clears parts, layout, settings and slice and makes a new
`plate_id`, while Escape keeps everything; with an empty plate no confirmation; a second tab
keeps its own group; `front.group_not_allowed` falls back to the first group with the two
sentences and an empty plate; the reload glyph with a removed profile picks the first and
says so; a configuration answered with `source` `"default"` shows "Config: PenguinSlicer
default".

## The configuration and the table of settings

The **configuration** ([its contract](../contracts/configuration.md)) is read whole with
`GET /api/configuration` when a page opens (and so after every sign-in) and when the reload
glyph is pressed. The wizard only reads it: its edit screens are a feature of their own, in
no phase yet. What the wizard takes from it:

- **`filaments`**, in order: each `name` and `colour` for the Filament menu (the colour
  beside the name, and never in the layer preview); each filament's `profiles`, in order,
  each `name` for the Profile menu and `purpose` as its option's tooltip. A new plate starts
  with the first filament and its first profile; picking a filament picks its first profile.
- **`printer`**: the Orca printer profile whose plate the Layout step draws. Its
  `printable_area` and `printable_height` come from the table of settings' `catalog.printers`
  entry of that name.
- **`upload_units`**: where the Parts step's switch starts.
- Each profile's `printer`, `filament`, `process` and `overrides`, which go into the plate
  configuration ([Submitting a plate](#submitting-a-plate)).

The **table of settings** ([its contract](../contracts/settings-table.md)) comes from
`GET /api/settings-table`, as the slice service that is running supplies it. The page asks
for it when it opens, beside `GET /api/configuration`, since the Layout step's figures line
takes the plate's size and height from it and the plate summary and the changes box take
each profile's values from it; it asks again only when a configuration read again names a
printer the table it holds lacks
([`GET /api/settings-table`](../contracts/wizard-front-server.md#get-apisettings-table)). It
keeps the table in the page's memory only. `503`
`front.slice_unreachable` is a quiet retry.

### The profile's value of a setting

The **profile's value** of a setting, shown in advanced mode's "Profile 0.012 mm · Reset" and
in the change details, is the configuration profile's own override of that setting when it
has one, and otherwise the table's `process_values` for the profile's `process`
([Process values](../contracts/settings-table.md#process-values)). A **change** is the user's
value of a setting that differs from the profile's value; a change put back to the profile's
value is no change.

Tests: the Filament menu shows each filament's colour; picking a filament picks its first
profile; a profile's purpose is its option's tooltip; the plate's size and height come from
the catalog entry the configuration names; the profile's value is the override when there is
one and the process value otherwise.

## The Parts step

The wizard opens here: the list of parts to print, each with a quantity. Its look is
`#parts-onshape`, `#parts-upload`, `#parts-messages`, `#parts-list` and `#parts-total` in the
mockup, under "Parts" in `css/panel.css`.

| Screen or state | What the user sees and does | Mockup |
|---|---|---|
| Outside Onshape (phase 2) | An upload area for STL files, dropped or chosen, binary STL only. Beside it the switch "Read STL files in: inches / millimetres", which says how the next files are read; it starts at the configuration's `upload_units`, and the user's choice is kept in the browser's storage (*proposed* record `uploadUnits`). A row has no switch of its own: a part read in the wrong units is removed and added again | [decision 51](../docs/mockups/print-wizard/DECISIONS.md#units-version-6), departed from |
| Inside Onshape (phase 4) | A prompt above the list, "Click a part in the Part Studio" or "Click a part in the assembly", that never changes. A click on a part adds it with quantity 1; a click on one already listed raises its quantity by one and flashes its row. In an Assembly a click on an instance, in Onshape's list or graphics area, adds its part. No button adds every part | [decision 14](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1), [decision 21](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| **New plate** | A button on this step that empties the plate: the parts, the layout and the slice go, with a new `plate_id`; the filament, the profile and the changes stay. When the plate holds parts it asks first, in a confirmation: "Start a new plate? The parts and layout of this one are cleared." A plate that is printing goes on printing and is then shown as a print, in the printer-status icon and the printer details, and no longer as this tab's plate. No count of plates is kept or shown | None: designed in the guide |
| A row | The part's picture, name, size in its own units, quantity and a remove button; no refresh button (a part changed in Onshape is removed and added again). The quantity cannot be typed or clicked past 150 | [decision 18](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| A part arriving | Its row with a thin progress bar and "Arriving from Onshape…" or "Uploading…". The bar promises no duration | [decision 15](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| A part still arriving when the user moves on | Never holds Next. It joins the plate on the Layout step, at once if the user is there and otherwise the next time that step is shown, and a notification on the current step says "Gusset Plate arrived after you left the Parts step. It joins the plate when you go back to the Layout step." | [decision 5](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 23](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| A part whose upload gets no answer | Its row stays, since the part is already in the browser's storage; "Taking longer than usual; still trying…" after 4 seconds; after 300 seconds the row keeps the part and shares the panel line's Try again | [decision 17](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1), departed from |
| Under the list | One line counting what the plate holds, and how many parts are still arriving | |

### Adding a part

Every way a part arrives is a [part set](../contracts/part-set.md): from an upload, the
page makes one, `source` `"file"`, one part for each file, `name` the file's name less a final
`.stl` in any case (cut to 200 characters, `part` when nothing is left), `quantity` 1, `units`
the switch's setting at that moment, `stl_bytes` the file's bytes unchanged; from phase 4 the
Onshape integration hands one over. For each part of a part set, in order:

1. **One part, one row.** The page hashes the bytes (SHA-256, by the browser's own digest,
   off the main thread). A part whose hash and units are those of a part already on the
   plate raises that part's quantity by the part set's `quantity` (to at most 150) and adds
   no row; the same bytes under the other units are another part.
2. **The page's own checks,** before anything is sent: a part over `MAX_PART_BYTES` is not
   added (notification below); a part that would be the plate's twenty-sixth is not added.
3. **Kept first:** the part is written to the stored plate (bytes, name, units, hash) and its
   row appears, arriving.
4. **Read for drawing** in the worker ([The geometry, in a worker](#the-geometry-in-a-worker)),
   at the same time as the upload.
5. **Uploaded,** as below. On `201` the row is complete; on a refusal the part and its row are
   removed and the notification shows.
6. **Laid down:** its instances are laid their best way by auto-orient and join the plate on
   the Layout step ([Parts arrive lying their best way](#parts-arrive-lying-their-best-way)).

### Uploading a part

`POST /api/parts?units=<mm|in>`, the body the part set's `stl_bytes` exactly, with
`Content-Type: application/octet-stream`, the wizard's mark and the current group. The page
never changes a byte: for an inch part it multiplies coordinates by 25.4 in memory only, for
its own drawing and measuring.

| Answer | The page |
|---|---|
| `201` with the part's record: `sha256`, `units`, `measurements` (`triangles`, `size_mm`, `volume_mm3`), `warnings` | Compares `sha256` with its own hash and uploads once more if they differ (a second difference is a `page_failed` report and the part is not added). Keeps the record beside the part. Shows each warning's `message` on the row in amber, without holding Next |
| `413` `slice.part_too_detailed` | The notification for a part over the size limit, with the slice service's sentence |
| `422` `slice.part_unreadable`, `slice.part_not_binary`, `slice.part_too_small`, `slice.part_no_volume`, `slice.part_too_large` | The notification of [A part that cannot be used](#a-part-that-cannot-be-used); the part is not added |
| `400` `slice.bad_units` or `front.bad_request` | A fault of the page: shown as a notification, reported as `page_failed` |
| `429` `front.too_many_requests`, `503` `front.slice_unreachable`, no answer | A quiet retry; the row stays |

A repeat with the same bytes and units answers the same record, so a retry after a lost
answer needs nothing more.

### A part that cannot be used

A part that cannot be used is a notification that names it, and it is not added: the list
never holds a broken row. The notification's sentences are those of the component that
refused the part; the wizard adds "Your other parts are fine." only while the list holds
other parts. A second failure of the same part replaces its notification. Next stays as it
was, and there is no Try again
([decision 16](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1),
[decision 19](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1)).

| What happened | Code | The notification says |
|---|---|---|
| Onshape cannot export the part (phase 4) | The Onshape integration's, named in phase 4 | The Onshape integration's sentences, of this kind: "Onshape could not export Shooter Hood Rib, so it was not added.", and what to check in Onshape: that it is one closed solid, not a surface and not several bodies, and that the Part Studio rebuilds with no red features |
| The file cannot be read as a part: empty, cut off or padded, or not an STL at all | `slice.part_unreadable` | The slice service's: that the file could not be read as a part, naming it, and to export it again |
| A text STL | `slice.part_not_binary` | The slice service's: that a binary STL is needed; to export it again as a binary STL |
| Too small or flat, nothing to print, too large for the printer | `slice.part_too_small`, `slice.part_no_volume`, `slice.part_too_large` | The slice service's. For an uploaded file refused as too large, followed by the wizard's own reminder of how the file was read ("STL files are being read in inches." or "…in millimetres."), since a file in millimetres read as inches is the likeliest cause |
| Over the size limit | The page's own check; `slice.part_too_detailed` should the slice service refuse all the same | See [The limits on a plate](#the-limits-on-a-plate) |

The part's record carries no `where`, so a warning's sentence from an upload does not name
the part; the row it stands on does. The warnings expected are `slice.part_not_watertight`,
`slice.part_inside_out` and `slice.part_maybe_inches` (every side under 5 mm).

**A part the slice service accepts and the page cannot draw** is a defect in the wizard. The
part is not added; the wizard's own notification says that PenguinSlicer could not show the
part and that it cannot be imported; the page sends a `POST /api/reports/failure` with `what`
`part_not_drawable` and the part's hash. A malformed file must end in a notification, never in
a frozen panel: the worker's reader is bounded by `MAX_PART_BYTES` and checks the triangle
count against the file's length before reading.

### The limits on a plate

All three are the slice service's limits. The page checks each itself before sending, so
these sentences are the wizard's; should the slice service refuse all the same, its own
sentence is shown.

| Limit | What the user sees | The slice service's code |
|---|---|---|
| A part is at most 7.5 MB (`MAX_PART_BYTES`, 7,500,084 bytes, 150,000 triangles) | A notification, nothing sent: "bracket.stl is 9.1 MB. PenguinSlicer takes parts up to 7.5 MB (150,000 triangles), so it was not added. Export it again from your CAD program at a coarser resolution." For a part picked in Onshape, the notification names the part and says it is too detailed to slice here | `slice.part_too_detailed` |
| At most 25 different parts on a plate (`MAX_PARTS`) | The twenty-sixth is not added: "A plate takes up to 25 different parts, so Gusset Plate was not added. Remove a part, or print it on a new plate." Raising a listed part's quantity still works | `slice.too_many_parts` |
| At most 150 instances on a plate (`MAX_INSTANCES`) | One part's quantity cannot be typed or clicked past 150. When the parts together pass it, a red message under the list, "This plate would hold 163 instances. Up to 150 instances per plate; print the rest on a new plate.", and Next off | `slice.too_many_instances` |

Open: whether the Onshape integration exports an over-size part again more coarsely by
itself is for phase 4's design ([The limits on a plate](README.md#the-limits-on-a-plate)).

Tests: a file of 7,500,084 bytes is uploaded and one of 7,500,085 is refused with the
sentence and no request; the twenty-sixth part is refused and the quantity of a listed one
rises; a quantity stops at 150; parts totalling 151 show the red message and Next off; the
same file added twice is one row with quantity 2, and the same file under the other units is
two rows; each failure row of the table, from the fake front server's error report, shows
its sentences and adds no row; "Your other parts are fine." shows only with other parts
listed; a second failure of one part replaces its notification; an upload refused as too
large is followed by the reminder in the switch's current units; a warning stays on its row
and Next stays on; a part the worker cannot read, accepted by the fake front server, is not
added and sends one `part_not_drawable` report; a part arriving after the user left joins
the Layout step and shows the notification; New plate with parts asks first and, confirmed,
keeps the filament, profile and changes and makes a new `plate_id`; the upload's body is
byte for byte the file.

## The Settings step

Two menus, four quick changes and one button; the common case stays short. Its look is
`#p-filament`, `#p-profile`, `#p-profile-clears`, `#p-overrides`, `#adv-entry` and
`#adv-effect` in the mockup, under "Settings" in `css/panel.css`.

| Screen or state | What the user sees | Mockup |
|---|---|---|
| Filament and Profile | The Filament menu offers the configuration's filaments, each with its colour beside its name. The Profile menu offers the chosen filament's own profiles under the group's names; a profile's purpose is its option's tooltip. Picking another filament picks its first profile. No printer row | [decision 9](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), [decision 10](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), departed from for the colour |
| The quick changes | Four menus, Infill, Walls, Supports, Brim; one to a row below 480 px, two from 480 px. They and advanced mode edit one shared set of changes. Each is a setting of the table: Infill `sparse_infill_density`, Walls `wall_loops`, Supports `enable_support` (with `support_type` `tree(auto)` when on), Brim `brim_type` ([Settings in phase 2](../contracts/plate-configuration.md#settings-in-phase-2)) | [decision 12](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| The caution | From the first change until the changes are cleared, under the Profile menu: "⚠ Changing the filament or the profile clears your 2 changes." Nothing after they are cleared | [decision 11](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Changing the filament or the profile | Clears every change, since a change is a departure from one profile | [decision 11](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| No change | The Advanced mode button stands alone under the quick changes | [decision 12](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Once a setting is changed | The **changes box** takes its place: a yellow box headed "2 settings changed from Structural", one line for each change, and the Advanced mode button. Each line is a link that opens advanced mode at that setting, its section and setting group open, the setting scrolled into sight and flashed. No Reset all in the box | [decision 12](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |

The quick changes' menus offer the mockup's values (`QUICK` in the mockup's
`js/settings.js`), each written into the changes as Orca writes it:

| Menu | Entries, in order | What each writes |
|---|---|---|
| Infill | "15 %", "25 %", "40 %", "60 %", "100 %" | `sparse_infill_density` `"15%"`, `"25%"`, `"40%"`, `"60%"`, `"100%"` |
| Walls | "2", "3", "4", "6" | `wall_loops` `"2"`, `"3"`, `"4"`, `"6"` |
| Supports | "Off", "On (tree, auto)" | Off: `enable_support` `"0"`, and nothing for `support_type`. On: `enable_support` `"1"` and `support_type` `"tree(auto)"`, whatever the profile's `support_type` |
| Brim | "Auto", "Off", "Outer only" | `brim_type` `"auto_brim"`, `"no_brim"`, `"outer_only"` |

A menu shows the value the plate will be sliced with: the user's change when there is one,
else the profile's value. Supports shows On when `enable_support` is `"1"`, whatever
`support_type` is. Choosing the profile's own value removes the change, since a change put
back to the profile's value is no change. A value off a menu's list, the profile's or one
set in advanced mode, is the open item
[A quick change whose value is not on its menu](README.md#a-quick-change-whose-value-is-not-on-its-menu);
build its recommendation: the value as one more entry at the top of the menu, written as
advanced mode writes it, and chosen.

### Advanced mode

Advanced mode fills the panel (`#advanced` in the mockup, "advanced mode" in
`css/panel.css`) and offers every entry of the table of settings, which is every setting of
Orca's that is a parameter with a value (about 295 at the pinned Orca), and no other: the
programmatic settings are not in the table, and the slice service refuses them. It shows
Orca's own `label`, `section`, `group` and `explanation` for each, in the table's order, and
draws each setting's control from its `kind`: a menu of `choices` (an on-and-off setting has
"Off" and "On"), a number field of its `number_form` within `min` and `max` with Orca's
`unit` after it, or a text field of at most `max_length`. A setting with `per_variant` takes
one value. Nothing is designed by hand for a single setting.

| Part | What it is | Mockup |
|---|---|---|
| Its header | "PenguinSlicer" with the printer-status icon; "Advanced mode", the profile and the changed count ("Structural, 2 changed"); **Reset all**, which asks in a confirmation before putting every setting back | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| The way out | **Back to Settings** at the bottom is the only way out; Escape does not close advanced mode | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Sections | The table's sections, as Orca has them (Quality, Strength, Speed, Support, Others), each with its collapsible setting groups (such as Precision). No search box, no common/all switch, no "changed only" filter | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), M26 |
| Below 480 px | An accordion of bordered cards: a section's heading with a chevron and its changed count ("Strength · 1 changed"); its setting groups are rows inside. Each card opens and closes by itself | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| From 480 px | A rail of section names down the left, each with a changed count, the chosen section's setting groups beside it | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Setting groups | Always one column, at most 480 px wide. A heading has a chevron and no count of its settings, only a changed count ("Precision · 1 changed"). One icon button, a double chevron, expands or collapses every setting group of a section | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Open and closed | Everything starts open the first time; what the user closes is remembered in the page's memory, not the browser's storage, for as long as the page is loaded: across steps, closing and reopening advanced mode, and the panel crossing 480 px. A reload forgets it | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| A changed setting | A tinted background, a bar on its left and a dot after its name; under it "Profile 0.012 mm · Reset", the link putting the profile's value back. A value outside the setting's allowed range is refused where it is typed | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| By keyboard | Opening puts focus on the first section's heading, or on the setting when a line of the changes box opened it; what advanced mode covers cannot be reached; closing returns focus to the line or button that opened it | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Keeping the changes | Changes are part of the user's work: kept in the browser's storage, back after a refresh | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), departed from |

A change is kept as Orca's `name` and its value written as Orca writes it, a string, so that
it goes into the plate configuration's `overrides` as it is.

Tests: changing the filament clears the changes and picks the first profile; the caution
shows from the first change and goes when cleared; a line of the changes box opens advanced
mode at its setting with its section and setting group open; Escape does nothing in advanced
mode; closed sections survive leaving and reopening and a resize across 480 px, and are all
open after a reload; changes survive a reload; a value out of range is refused where typed; a
control is drawn for each `kind` and `number_form` of the contract's example table; focus goes
where the table says; Reset all asks and puts every setting back.

## The Layout step

A 3D view of the plate the user works in directly: no modes and no tools to pick up
([decision 27](../docs/mockups/print-wizard/DECISIONS.md#layout-step)). The view fills the
panel's width and grows with it, square at narrow widths and 4:3 from 520 px, with no height
cap ([decision 25](../docs/mockups/print-wizard/DECISIONS.md#layout-step)). The step does not
change the list of parts: no duplicate, delete, undo or redo, and Delete, Ctrl+D, Ctrl+Z and
Ctrl+Y do nothing; no scale, cut, mirror or per-part settings
([decision 24](../docs/mockups/print-wizard/DECISIONS.md#layout-step), M16). Its look is
`#layout-toolbar` down to `#layout-info` in the mockup, under "Layout" in `css/panel.css`,
and its gestures are those of `js/layout3d.js`.

### What is on the step

| Part, top to bottom | What it shows | Mockup |
|---|---|---|
| Toolbar | **Arrange**, **Auto-orient**, and at the right a "?" icon opening the list of gestures in a small panel | [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6), [decision 62](../docs/mockups/print-wizard/DECISIONS.md#the-rotation-handle-version-7) |
| The status line | Green when every instance fits ("✓ All 16 instances fit the plate."); red with the first problem, with "+2 more ↓" when there are others; a click on a red line scrolls to the messages | [decision 27](../docs/mockups/print-wizard/DECISIONS.md#layout-step), M7 |
| The view | View buttons in a corner (Zoom to instances, Whole plate, Top); at the bottom left the pointer line, 11 px, saying what is under the pointer (an instance's name, "Lay it on this face: 0.250 in tall", "Drag to turn · Shift: 45° steps") | [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms), M7 |
| The selection line | Nothing selected: "90 instances on the plate, 10 beside it."; one: its name, footprint and height in its part's units; several: "5 instances move and turn together". Beside it at most one link: "Lay it the best way" when the selection does not lie its best way, "Put back as modelled" when laid differently from the model, nothing when it lies as modelled and that is its best way | [decision 57](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6), [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |
| The figures line | "Shop H2S: plate 340 × 320 mm, up to 340 mm tall, 12 mm apart" (5 mm with supports off), the size and height from the printer's entry in the table of settings | [decision 55](../docs/mockups/print-wizard/DECISIONS.md#units-version-6), [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |
| The messages | Anything the wizard moved; under "Fix these 2 before Next:" one red message for each problem with its button. A message about a move, and "Arranged 16 instances.", goes when the user leaves the step; a problem stays until fixed. Every sentence here is the wizard's | [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |

The figures line names the printer by the name the printer reports from phase 5; before
then, with no printer, it is *proposed* to start with the printer profile's name from the
configuration.

### Moving, turning and looking

The mouse works as in Onshape, not as in Orca (M2): drag an instance to move it; right-drag
to look around; Shift-drag, middle-drag or Ctrl with right-drag to slide the view; scroll to
zoom; a left-drag on empty plate looks around. Shift-click or Ctrl-click adds an instance to
the selection, and dragging one of a selection moves them all. F zooms to the instances,
Ctrl+1 looks from above, Ctrl+A selects every instance and Escape clears the selection; no
other key is designed for this step. A touch screen works for every click; the gestures are
designed for a mouse.

**The rotation handle** ([decision 62](../docs/mockups/print-wizard/DECISIONS.md#the-rotation-handle-version-7)):
a round handle beside the selection that turns it about the vertical. A press fixes, for the
whole drag, the pivot (the middle of the selection's box), the handle's distance and its
side; while dragged the handle stays on that circle and turns through the same angle as the
selection, never hopping sides. Each instance turns rigidly about the pivot. The mesh moves
before the frame is drawn, so the handle and the selection box never lead it. Turning is
free; a readout beside the handle shows the first selected instance's orientation on the
plate ("↺ 37°"). Holding Shift snaps that orientation to multiples of 45°, taking effect at
once when pressed or let go mid-drag; in a selection the first instance snaps and the others
turn by the same angle. The handle is drawn over everything and moves out of the way of the
face patches in sight, only while no drag is going on
([decision 49](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5)).
When a drag ends each instance's angle is kept to a whole degree, the form the plate
configuration takes, and the placement check runs on that kept angle.

### Laying an instance on a face

Selecting one instance shows translucent blue rounded patches on the faces it could lie on;
a click on a patch lays it down on that face; a double-click on a flat face does the same. No
button and no mode; with two or more selected, no patches (M1;
[decision 49](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5)).
**Hull patches** lie on the flat faces of the part's convex hull; **bounding-box patches** lie
on a side of the part's bounding box where no hull patch points that way, drawn like the hull
patches (M29;
[decision 61](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5)).
Only patches in sight are drawn and clickable; the face the instance lies on has none; a
patch brightens under the pointer, and the pointer line says what laying it there gives
("Lay it on this side: 1.732 in tall"). Patches appear within `PATCHES_MS` of selecting; until
the worker has the faces, the instance is selected with no patches.

**Laying down never moves another instance**
([decision 26](../docs/mockups/print-wizard/DECISIONS.md#layout-step)):

| What follows a lay-down | Message |
|---|---|
| It still fits where it stood | None |
| It no longer fits: moved to the nearest free spot, turned if need be | Green: "L Bracket #1 no longer fitted where it stood, so it was moved to the nearest free spot." |
| No free spot: it waits beside the plate, marked as off the plate, already turned to fit the plate if it is too long as it lay | Amber: "L Bracket #1 no longer fits on the plate and waits beside it. No spot on the plate is free for it lying this way. The other instances stay where you put them; press Arrange to make room." |

A hull face can point any way, so the page keeps each instance's turn as a full rotation and
sends it as [An instance in phase 2](../contracts/plate-configuration.md#an-instance-in-phase-2)
says: `orientation` and `angle` when the turn is one of the six axes followed by a turn about
the vertical, and otherwise `rotation`, the unit quaternion `[w, x, y, z]` of the turn out of
the part's own coordinates, with `angle` the whole degrees about the vertical after it. The
footprint, its centre and the lowest point are the contract's for that rotation, so the
page's placement check and the slice service's place the instance alike.

### Parts arrive lying their best way

A new part's instances are laid down by auto-orient, and nothing is said (M3;
[decision 27](../docs/mockups/print-wizard/DECISIONS.md#layout-step)). **Auto-orient** does the
same on request, for the selected instances or for every instance when none is selected; if
the plate then needs rearranging, the wizard arranges it and says "Arranged the plate again to
make room." ([decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6)).

### Arrange

**Arrange** places every instance on the plate, in a compact pile about the plate's middle, at
the spacing the settings ask for, says "Arranged 16 instances.", and never turns an instance
([decision 64](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6), M6), where
Orca's arranging may. Arrange and Auto-orient stay two buttons. When Arrange cannot fit
everything and laying instances their best way would fit more, its message offers that as one
button: "Arrange placed 12 of 16 instances; 4 instances do not fit and wait beside the plate.
Arrange keeps how each instance lies. With 5 instances laid the best way, everything would
fit. Or lower the quantities and print the rest on a new plate.", with **Lay them the best
way: all fit**.

The wizard turns an instance about the vertical only when it has just laid it down itself and
it is then too long for the plate, by a quarter, an eighth or three eighths of a turn, the
first that fits, at four moments
([decision 64](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6)): a part
that arrives too long as it lies, before it is first arranged; an instance Auto-orient lays
down that is then too long; an instance a lay-down leaves beside the plate, which waits turned
so that Arrange can place it; an instance moved to the nearest free spot after a lay-down. A
353 mm rib on a 340 × 320 mm plate fits only on the diagonal.

### The placement rules, and what each problem says

The slice service's own rules
([Checks](../contracts/plate-configuration.md#checks), step 5), so that a plate the wizard
passes is one the slice service accepts: every instance's footprint at least `MARGIN_MM`
(3 mm) inside the printable area, no instance taller than the printable height, and
`SPACING_SUPPORTS_MM` (12 mm) between footprints with supports on, `SPACING_MM` (5 mm) off,
measured between the outlines as they are turned. Supports are on exactly as the plate
configuration's contract says: `enable_support` `"1"` among the changes, or the profile's
value `"1"` ([decision 57](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6)).
Next is off while any rule is broken.

| Problem | The message | Its button |
|---|---|---|
| Two instances too close | "L Bracket #1 and Gusset Plate #2 are 6.2 mm apart; instances need 12 mm between them with supports on. Drag one away, or press Arrange." | Arrange |
| Many instances too close | One message for all of them: "23 instances are closer than 12 mm with supports on. Press Arrange, or drag them apart." Each stays marked in the view | Arrange |
| Across the plate's edge | "Gusset Plate #3 is not fully on the plate: it crosses the left edge. Drag it inward, or press Arrange." | Arrange |
| Longer or wider than the plate takes as it is turned | "Shooter Hood Rib #1 is 352.7 mm (13.885 in) from left to right as it is turned; the plate takes 334 mm. Turn it to fit turns it and arranges the plate again." Where it still stands on the plate, the message opens with "not fully on the plate" and goes on with the same sentences | **Turn it to fit**, in place of Arrange: turns it as on arrival and arranges again |
| A part that fits the plate at no turn | The same first sentence, then "Lay it down another way." | None |
| Too tall | "Shooter Hood Rib #1 stands 352.7 mm (13.885 in) tall; the printer prints up to 340 mm. Lay it down another way, or press Auto-orient." | Auto-orient |

An instance Arrange left beside the plate has no message of its own (Arrange's message counts
it), except one too long or too wide as turned, which has its row above and is not counted by
Arrange. A click on a message selects the instances it names. **Turning supports on after
arranging moves nothing**: instances now too close get the usual message until the user
presses Arrange or drags them.

The instance names in messages are those the slice service gives: the part's name and a count
from 1 ("L Bracket #2"), counted in the order of the plate configuration's `instances`, so that
a message of the wizard and a refusal of the slice service name the same instance alike.

Open: saying that a part will need supports
([Saying that a part will need supports](README.md#saying-that-a-part-will-need-supports));
build nothing for it.

Tests (on the fake clock where timed, and on the real exported parts kept in the repository):
each problem row reached on purpose with its sentence and button; Turn it to fit turns and
arranges; Arrange keeps a 37° instance at 37°; Arrange's partial message and its button; each
of the four turning moments; a lay-down that moves to a free spot and one that waits beside;
supports turned on leaves positions unchanged and shows the too-close message; messages about
moves go on leaving the step; Delete, Ctrl+D, Ctrl+Z and Ctrl+Y do nothing; the rotation handle
stays on its circle through a drag and Shift snaps the orientation; F, Ctrl+1, Ctrl+A and Escape
do what the table says; a lay-down answered before the worker returns the faces shows no
patches and then the patches.

## The geometry, in a worker

**Keeping the page answering.** Nothing holds the browser's main thread for more than
`MAIN_THREAD_HOLD_MS` (250 ms), on any step, with any plate up to the limits, on the machine
without a graphics card. By design the **worker** (`wizard/src/geometry.worker.js`) does
everything that reads or works with the internals of an STL file or a sliced file's paths:
reading a part for drawing; finding the faces a part can lie on; auto-orient; Arrange; the
placement check on a full plate; preparing a sliced file for the Preview step. The main thread
keeps drawing and the user's gestures. Hashing a part uses the browser's own digest, which
needs no worker. Every result arrives a moment after it was asked for, so each job has a "not
yet" state (a row without its picture, an instance selected before its patches appear); a
part's geometry is handed to the main thread as transferable buffers, so it is not copied
twice. The page measures the longest stretch the main thread was held by a heartbeat: a 10 ms
timer on the main thread, the hold being the longest gap between two beats, for its tests and
its reports ([What the wizard reports about itself](#what-the-wizard-reports-about-itself)).
The browser's long-task timing is not the measure: in the second trial Chromium reported long
tasks of 0.1 to 0.9 s during steps whose answers all came back in under 0.3 s while the
heartbeat never went more than about 15 ms between beats
([the trial's notes](trials/geometry/README.md)).
Open: why Chromium's long-task timing reports those tasks; until it is known, a long-task
figure is reported beside the heartbeat's and never counted against `MAIN_THREAD_HOLD_MS`.

All of it is written fresh: an implementer may read Orca's source to understand a method,
and no Orca code, comment or constant name enters the repository.

**Reading a part without changing it.** The worker reads a binary STL to draw, measure and lay
it out and never changes its bytes. For an inch part it multiplies the coordinates by 25.4 in
memory only; the slice service alone applies the scale to what is sliced
([Units](../slice/README.md#units)).

### Finding the faces a part can lie on

The method of [the note on hull faces](../docs/research/2026-11-21-lay-on-face-hull-faces.md),
with two rules of PenguinSlicer's own for round parts
([Finding the faces a part can lie on](README.md#finding-the-faces-a-part-can-lie-on);
[decision 49](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5),
[decision 61](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5)):

1. The part's convex hull (`geometry/hull.js`): quickhull, each face keeping the corners outside
   it, the part's repeated corners dropped first, a corner within `HULL_EPS_MM` of a face on it.
2. Hull triangles joined into flat faces, spreading to neighbours whose normal matches the
   first triangle's (not the neighbour's) within `FACE_JOIN_DEG`; then a face all of whose
   corners lie within `FLAT_GAP_MM` of a larger neighbour's plane, turning from it by less than
   `FLAT_TURN_DEG`, is made part of that neighbour (an exported flat face comes out of the hull
   as a large piece and thin strips a tenth of a degree off, where a fillet's corners sit a
   thousandth of a millimetre above it).
3. Faces dropped under `MIN_FACE_MM2` (5 mm²), with a corner sharper than `SLIVER_DEG`, and all
   but the `MAX_FACES` (254) largest.
4. A face dropped when a hull face it reaches through faces that all turn from it by less than
   `ROUND_SIDE_DEG` (20 degrees) is at least half its size: the facets of a round side, also
   when the facets are unequal or have slivers between them; a flat face beside a chamfer keeps
   its patch. Except that a face of at least `MIN_CONTACT_MM2` that is mostly the part's own
   surface (its triangles within `FLAT_GAP_MM` and `FLAT_TURN_DEG` of it cover at least half
   of it) is not dropped on account of one that mostly bridges a hollow or a step: on
   Elevator Top Inner each side's flat face sits 3 degrees from a hull face of the same size
   bridging down to a smaller lower block, and the rule as first written dropped both.
5. A bounding-box patch for each of the six sides of the part's bounding box with no kept face
   pointing within `BBOX_COVER_DEG` (30 degrees, plus half a degree for rounding) of it; end
   patches included, even where they stand the part too tall (M29).

`findFaces` in `geometry/faces.js` gives every joined face with the step that dropped it, and the
patches, each `{kind: 'hull' | 'box', normal, area, outline}` in the part's own coordinates. A
click turns the instance by the shortest rotation that points the chosen face straight down,
keeping its turn about the vertical (`layOnFace` in `geometry/turn.js`); the instance's turn is a
unit quaternion, sent as the contract's `orientation` when it is one of the six axes followed by
whole degrees about the vertical and as `rotation` otherwise (`instanceTurn`). Faces are found once
for each part and turn with it. Each patch is marked with auto-orient's test of whether the part
would stand on it without tipping (`stable`) and how tall it would stand; no patch is dropped for
tipping, because the plate holds a print's first layer whichever way its weight falls, and a
filter tried on the real parts dropped Elevator Top Inner's four flat sides. Still not handled:
a round side of fewer than 18 facets, which bend more than 20 degrees apart, and a part modelled
at an angle to its axes, whose bounding box does not meet its rim square; neither occurs among the
real parts kept in the repository.

### Auto-orient

`autoOrient` in `geometry/orient.js`. Candidates: the patches above, and the part as modelled. A
candidate counts only if it is stable (the centre of mass, dropped straight down, lands inside the
outline of the triangles that touch the plate, those within `CONTACT_GAP_MM` of it) and at least
`MIN_CONTACT_MM2` (25 mm²) touches. The cost, lower being better: the area of downward triangles
within `OVERHANG_DEG` of straight down that do not touch, divided by the area touching (at least
1 mm²), plus `HEIGHT_CHARGE_PER_MM` for each millimetre of height, plus `NO_CONTACT_PENALTY` under
`MIN_CONTACT_MM2`. The part as modelled is kept when its cost is within `AS_MODELLED_MARGIN` of the
best, so that a hub whose two ends were cut a little differently is not turned over. A part with no
candidate (a sphere) stays as modelled. It runs once for each part when the part arrives, finding
the faces on the way, so selecting an instance later only fetches the patches already found.

### Arrange and the placement check

**Arrange** (`arrangePlate` in `geometry/arrange.js`) works on each instance's convex outline seen
from above, as it lies and as it is turned (held by an outline of at most 32 corners), grown by half
the spacing and `ARRANGE_SLACK_MM` on each side; it never turns one. Whether a spot is free is read
from a map of the printable area less the margin in squares `ARRANGE_CELL_MM` across, each marked
when a grown outline touches it, so two instances whose grown outlines share no square are at least
the spacing apart and an arranged plate always passes the placement check, with up to about a
millimetre more room than the spacing. Two packers run and the better result is kept: a shelf
packer (largest first, each at the first free spot on a `PILE_GRID_MM` grid scanning from the
front-left corner, slid towards that corner a square at a time, the group then centred) and a pile
packer (largest first, every free spot on a `PILE_GRID_MM` grid near the pile, the whole plate when
none is free there, scored by the pile's area, how square it stays and how near the middle, the
best refined at `PILE_REFINE_MM`, the pile centred). Fewer instances left beside the plate wins;
the smaller pile breaks a tie. An instance left beside the plate is put to its right, clear of it.
A curved or L-shaped part takes up its hollow side too; packing true outlines is not planned. On
the second trial's two plates of 150 instances the shelf packer won both times.

**The placement check** uses the same outlines and the three rules of the slice service, with
the footprint and its centre exactly as the plate configuration's
[Coordinates](../contracts/plate-configuration.md#coordinates) define them (the convex hull of
the turned part's vertices seen from above, its centre the centre of the turned part's bounding
box), and runs on every movement of a drag with up to 150 instances. The wizard's check and the
slice service's are kept in agreement by one shared set of plates, some just passing and some
just failing, kept with the contracts and run by both components' tests
([Shared plates for the two placement checks](../slice/README.md#shared-plates-for-the-two-placement-checks)).
Their folder, the form of each plate's file with its `expected` answer, the plates each rule
needs and the agreement asked of the two checks (exactly the expected answer on every plate,
each 0.01 mm from its rule's figure except the two height plates, 0 and 1 mm from it) are fixed in
[Shared plates for the placement checks](../contracts/plate-configuration.md#shared-plates-for-the-placement-checks);
the slice service's builder wrote the set first, before anything else of its phase 2. A
plate the wizard shows green and the slice service refuses is a defect in one of them.

`checkPlate` in `geometry/placement.js` gives the problems in the slice service's order (every
instance across the margin, then every one too tall, then every pair too close, `i < j`), each
`{rule, instances}` with what the Layout step's messages need: the `edges` crossed (`left`,
`right`, `front`, `back`) and the footprint's `size` for `off_plate`, the `height` for
`too_tall`, the `distance` for `too_close`. Footprints are kept for each part and turn, keyed by
the part's hull corners as read and never by the plate configuration's part key (which means
nothing beyond one plate configuration: a key may come to point at another part read under
another key, or at a part read again in other units), so a check never answers from the
footprint of a part the key pointed at before; pairs are
compared only when their bounds come within the spacing, and two outlines are measured exactly
only when their 32-corner outlines are closer than the spacing. Instances are named as the slice
service names them (`instanceLabels`).

**The worker's messages** (`geometry/messages.js`, run by `geometry.worker.js`; the tests run the
same messages in their own thread): `read` (`key`, `buffer`, `units`; answers the triangles, the
box and the corners for drawing as a transferred `Float32Array`), `faces`, `orient` (with the
contract's fields for the turn), `arrange` and `check` (`plateConfiguration`, `geometry` mapping
each of its part keys to the key a part was read under, `printer` with `min`, `max` and `height`,
and `supports`), and `forget`. Each answer is `{id, ok: true, result}` or `{id, ok: false, error}`,
the error an error report of the wizard's own:

| Code | When | `message`; `remedy` |
|---|---|---|
| `wizard.part_not_drawable` | A file the reader cannot read (shorter than the header, cut off or padded, no triangles, over `MAX_PART_BYTES` or `MAX_PART_TRIANGLES`, a coordinate not a number), or a part with no hull (flat, a line, a point) | "PenguinSlicer could not show this part, so it cannot be imported."; "Export the part again as a binary STL and add it again." Not retryable; `detail` says what was wrong |
| `wizard.layout_failed` | A message about a part never read, a message the worker does not know, an `arrange` or `check` with an instance the slice service would refuse as `slice.bad_plate_configuration` (`x` or `y` not a finite number, `angle` not a whole number from 0 to 359, both or neither of `orientation` and `rotation`, an orientation not one of the six, a `rotation` not four finite numbers of length 1 within 1e-6, a `ref` naming no part of the plate configuration or a part missing from the message's `geometry`), or the geometry's own code failing | "PenguinSlicer could not work out the layout of this plate."; "Reload the page; your parts, layout and settings are kept in this browser." Retryable (the remedy holds once the page keeps the plate in the browser's storage, [What the browser keeps](#what-the-browser-keeps), built with the page); `detail` names the fault |

Tests (`wizard/tests/geometry/`, on Node's runner): on the eight real exported parts kept in the
repository and the two made parts, the faces, patches and the way auto-orient lays each, as the
second trial recorded them, and that every flat face of a real part (a hull face of at least
25 mm², at least half of it the part's own surface) has a hull patch; each step of finding faces
on small solids made in the tests (a box, a cylinder, a hex prism, a wedge, chamfers, a stepped
block, a round side with slivers between its facets, a strip a few thousandths of a millimetre
off a face); the hull checked against every corner of a real part and of random spheres; the
placement check against every shared plate, with the expected answer of each, and in the slice
service's order, with each of the four edges of the margin reached on purpose, two instances too
close front to back in either order, and a part key that comes to point at another part;
laying an instance on a face keeps its turn about the vertical; the sentences of each error
report are the guide's; Arrange never changes an orientation, keeps the spacing with supports on and
off, centres the pile, and leaves beside the plate what does not fit; each of the reader's
refusals and each error report through the worker's messages. To be built with the page (items 7
and 10 of [By phase](#by-phase)): a malformed STL ends in a notification the main thread shows,
with the panel never held past 250 ms.

## The Preview step

Entering the step submits the plate; when the slice is done it shows the result
([decision 28](../docs/mockups/print-wizard/DECISIONS.md#preview-step)). Coming back to a plate
already sliced as it stands shows the result without slicing again. A slice goes on without its
page: leaving the step, a refresh, a lost network or a closed lid leave it running, and coming
back with the same plate finds it going or finished (M17;
[decision 29](../docs/mockups/print-wizard/DECISIONS.md#preview-step)). A changed plate (a part
moved, a setting changed) starts a new slice, which replaces that plate's own earlier unfinished
slice. Its look is `#slice-card`, `#preview-errors` and `#preview-result` in the mockup, under
"Preview" in `css/panel.css`.

**A slice cannot be cancelled by hand.** There is no Cancel button on the slicing card, no
state "cancelled by the user", and no request to cancel a slice job. A user who no longer wants
the slice steps back and changes the plate, or leaves it to finish.

### Submitting a plate

The page makes a [plate configuration](../contracts/plate-configuration.md) in its phase 2
form, as [From a profile to a plate configuration](../contracts/plate-configuration.md#from-a-profile-to-a-plate-configuration)
says, and sends it as `POST /api/slices`:

| Field | From |
|---|---|
| `plate_id` | The stored plate's id: a random UUID made when the plate began (a new tab with an empty plate, New plate, a change of group) and kept for as long as the plate lives |
| `submission_id` | A new random UUID each time the page decides to slice: entering the Preview step with a plate not yet sliced as it stands, Slice again, Turn on Supports and slice again, and submitting again by itself after a slice job ended `cancelled` with `cancel_reason` `shutdown` or after the slice service restarted. The same value when it repeats a submission whose answer did not arrive, while the slice service is stopping, and after uploading parts the slice service said were missing |
| `parts` | Each part on the plate under a key of the page's own (*proposed*: `p1`, `p2`…), with its `name`, `sha256` and `units` |
| `instances` | The Layout step: each instance's `ref`, `orientation` or `rotation` ([Laying an instance on a face](#laying-an-instance-on-a-face)), `angle` (whole degrees), `x` and `y` (the footprint's centre on the plate, millimetres) |
| `printer`, `filament`, `process` | The chosen profile's |
| `overrides` | The chosen profile's own `overrides`, with the user's changes on top; a change put back to the profile's value is left out |
| `local_time` | The browser's clock, `YYYYMMDD-HHMM` |

The page keeps the slice job's id from the answer, the `submission_id` and the time it
submitted, in the stored plate, with a fingerprint of what it submitted (*proposed*: a hash of
the plate configuration less its two ids), by which it knows whether the plate is "already
sliced as it stands". Each submission's body is checked against `MAX_PLATE_CONFIGURATION_BYTES`
before it is sent.

| Answer | The page |
|---|---|
| `202` with `slice` (`id`, `plate_id`, `submission_id`, `progress`) | Keeps the id, shows the first report and opens the progress stream. A repeat of an accepted submission answers the same slice job |
| `422` `slice.part_missing` with `where.missing_parts` | Uploads each listed part again from the browser's storage (by its `sha256` and `units`) and submits again with the same `submission_id`, showing nothing. A second `slice.part_missing` for the same submission is handled the same; a third (*proposed*) is shown as a failure and reported as `page_failed`, so that it never loops. An instance whose `ref` names no part (`slice.part_missing` with no `missing_parts`) is a fault of the page, shown as a failure |
| `422` or `400` with a refusal of the plate | The failure, as [When a slice fails](#when-a-slice-fails) says |
| `503` `slice.busy` | [No room to wait](#no-room-to-wait) |
| `503` `slice.stopping` | [While the slice service is stopping](#while-the-slice-service-is-stopping) |
| `429` `front.too_many_requests`, `503` `front.slice_unreachable`, no answer | A quiet retry with the same `submission_id` |

### The slicing card

A ring gauge with the percentage, the stage in words (the report's `stage_label`), the time taken
and "about" the time left, a bar, the list of stages with the current one marked, and the line
"Slicing goes on if you step back; change the plate and it starts again."
([decision 30](../docs/mockups/print-wizard/DECISIONS.md#preview-step), departed from: no Cancel
slice). The stages, in order with their words, and the rule for a stage the page does not
know, are [the progress report's](../contracts/progress-report.md#a-slice-jobs-reports); the
`fraction` is Orca's own, passed through; the time left is
`expected_s` less `elapsed_s`, the slice service's estimate, good to about a factor of two.

| State | The report | What the user sees |
|---|---|---|
| Waiting behind other slices | `queued`, with `ahead` | The ring empty; the stage line "Waiting for the slicer: 2 slices ahead of yours." (or "1 slice ahead of yours."), updated as `ahead` falls; the time waited counting up; no time left |
| Waiting while the slice service is stopping | The answer `slice.stopping` | The ring empty; a stage line that the slicer is restarting (*proposed*: "The slicer is restarting; your plate will start when it is back."); the time waited counting up |
| Slicing | `running` | The ring, the stage and the times |
| The front server cannot be reached | A request of the page's has failed for `RETRY_QUIET_S`, or the progress stream counts as failed | The figures stop, and the time-left line says "no news since 0:41" |
| Reconnected | The first report after that state | One line on the card: "Reconnected at 1:05. The slice kept running; the progress below is up to date." |
| The slice service restarted | `GET /api/slices/<slice>` answers `404` `front.slice_unknown` for a slice job submitted less than `SLICED_FILE_KEEP_S` ago | The ring and the stages back to the start, and the line "The slicer restarted, so this slice began again." The page has uploaded the parts again and submitted the plate again by itself, with a new `submission_id` |
| Ended because the slice service was asked to stop | `cancelled`, `cancel_reason` `shutdown` | The same as the row above: the page submits the plate again by itself with a new `submission_id`, and the card starts again with that line |
| Replaced by the same plate's later slice | `cancelled`, `cancel_reason` `replaced` | Nothing: the page already follows the later slice job |

So a slice ends without a result, other than by failing, only by being replaced or by the slice
service being asked to stop; `cancel_reason` `requested` never reaches a page.

### While the slice service is stopping

A submission answered `503` `slice.stopping` started nothing. The slicing card shows the waiting
state above, and the page submits the same plate configuration again by itself, with the same
`submission_id`, at the waits of [Retrying](#retrying), until it is accepted or until
`RETRY_TOTAL_S` (300 s) have passed since the first such answer. This is not the message that the
server is being slow, since the front server answered, so the panel line stays empty; only past
the 300 seconds does it say "The server could not be reached.", with Try again, which resubmits
and starts the 300 seconds afresh.

### No room to wait

A submission answered `503` `slice.busy` (one slice running and two waiting): an amber message in
place of the slicing card, with the slice service's sentence ("The slicer is busy, try again in a
minute."), the wizard's own line "Your plate is unchanged.", and **Slice again**, which submits
with a new `submission_id`. The page does not try again by itself, since a silent queue outside
the slice service's own would hide how busy it is from the person waiting. The message is amber,
since nothing is wrong with the plate.

**Everyone shares the slice service's places.** There is no limit on slice jobs for each user: a
user with several tabs, each with its own plate, may have a slice of each running or waiting, and
one tab's slice job never ends another's, because a slice job is replaced only by a later one with
the same `plate_id`.

### When a slice fails

A failed slice (a refusal of the submission, or a `failed` report with its `error`) is a red
message in place of the slicing card: the report's `message` and `remedy`, with its buttons
([decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step)). The wizard's buttons: the
one for the report's `action`, for the actions that have one
([the error report's actions](../contracts/error-report.md#actions)); **Slice again** when the
row says so; and its own Back to Layout, Back to Parts or Back to Settings. The codes below,
which the page acts on by name, are fixed and never renamed
([Codes a user interface acts on](../contracts/error-report.md#codes-a-user-interface-acts-on)).

| Failure | Codes | The wizard's buttons |
|---|---|---|
| The plate is not acceptable to the slice service although the Layout step passed it (a disagreement between the two placement checks, or a fault of the page) | `slice.placement_off_plate`, `slice.placement_too_tall`, `slice.placement_too_close`, `slice.crosses_edge`, `slice.nothing_on_plate`, `slice.left_off_plate`, `slice.too_many_instances`, `slice.too_many_parts`, `slice.part_too_large`, `slice.bad_plate_configuration` | Back to Layout |
| Empty layers, supports off | `slice.empty_layers`, `action` `enable_supports` | **Turn on Supports and slice again**; Back to Layout. Folded Details |
| Empty layers, supports on (a fault in the part's mesh) | `slice.empty_layers_with_supports` | Back to Parts. Folded Details |
| A profile or setting not accepted | `slice.unknown_printer`, `slice.profiles_not_offered`, `slice.bad_overrides`, `slice.profile_unreadable` | Back to Settings |
| Two instances' paths would meet | `slice.orca_too_close` | Back to Layout |
| Nothing printable | `slice.no_layers`, `slice.print_empty` | Back to Parts |
| Too slow: past the slice service's time limit, today 240 seconds | `slice.timeout` | **Slice again**; Back to Parts |
| The sliced file would be larger than 50 MB | `slice.output_too_large`; `front.sliced_file_too_large`, in a `failed` report, should one reach the front server | Back to Parts; no Slice again, since the same plate would give the same file |
| Out of memory: past the most memory the slice service allows one plate, today 2,000 MB | `slice.out_of_memory` | Back to Parts; no Slice again, since the same plate would run out the same way |
| Orca failed with only a general reason | `slice.orca_failed` | **Slice again**; Back to Layout |
| Orca crashed or was stopped, its sliced file missing or damaged, or the slice service itself failed | `slice.orca_crashed`, `slice.orca_killed`, `slice.orca_missing`, `slice.orca_unstartable`, `slice.no_output`, `slice.unreadable_output`, `slice.no_gcode`, `slice.output_unwritable`, `slice.scratch_unwritable`, `slice.unexpected`, and any code the wizard does not know | **Slice again**; Back to Layout |

The sentences are the slice service's ([its list](../slice/README.md#when-things-go-wrong)); for
example, out of memory reads today "This plate is too large to slice: the slicer needed more than
the 2,000 MB of memory the print server allows.", with its remedy of fewer instances or a new
plate, or for a single instance to split or simplify the part. There is no "plate too large"
refusal before slicing (fake 9): a plate too heavy to slice ends as out of memory or too slow.

**Turn on Supports and slice again** sets `enable_support` to `"1"` (with `support_type`
`tree(auto)`) among the changes and runs the placement check at 12 mm first. A plate that passes
is submitted. One that does not is not: the wizard goes to the Layout step, which says "Not
sliced: with Supports on, instances need 12 mm between them." above the usual message. Nothing
moves by itself ([decision 57](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6)).

### Orca's own sentence under Details

On the two empty-layers failures, and nowhere else, the folded Details hold two things: the slice
service's sentence of where to look on the part (its `remedy` carries what to do; the place is in
its sentences), and the report's `orca_sentence`, when present, shown as text after "Orca Slicer: "
("Orca Slicer: Object can't be printed for empty layer between 9.9 and 11.34"). The wizard adds
nothing and never reads `detail`.

Tests: each row reached on purpose from the fake front server, with the buttons listed; an
unknown code as the last row; out of memory and too large a file offer no Slice again; Turn on
Supports on a plate arranged at 5 mm goes to the Layout step with the line and submits nothing,
and on a plate at 12 mm submits with `enable_support` `"1"`; `orca_sentence` shows under Details on
both empty-layers codes and is absent elsewhere even when the fake sends one.

### The result

When the progress report is `done`, it carries `sliced_file`, the sliced file's details; a page
that has the slice job's id but not that report asks `GET /api/slices/<slice>/summary`.

| Part | What it shows | Mockup |
|---|---|---|
| Print time and filament | Large: "3 h 12 min", "84 g PETG", from the summary's `print_time_s` and `filament_g`, with the filament's name; shown at once, before the layer preview | [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| One quiet line | The instances, the layers (`layer_count`) and how long the slice took | [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Warnings | The summary's `warnings` and the `part_warnings`' `message`, in amber | |
| The layer preview | A 3D view of the sliced plate with a layer bar at its right; the readout under the view, "134 / 134 · 40.2 mm", one line at 320 px; the bar moves with the arrow keys and reports its layer to a screen reader; two small buttons step one layer down or up; **Reset view**; a "?" icon: "Drag to turn, right-drag to pan, scroll to zoom; drag the bar on the right to go through the layers." | [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Next | Goes to the Send step once the plate is sliced | [decision 34](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |

A number the summary gives as `null` is left out of its line rather than shown as a failure. The
Preview step's mouse differs from the Layout step's on purpose: here a left-drag turns the view and
a right-drag slides it, since nothing can be moved.

### A sliced plate that expires

The sliced file's details carry `expires_at` and `expires_in_s`; the page counts `expires_in_s` on
its own clock from the moment the answer arrived, and never compares `expires_at` with its own
clock. Both are `null` while a delivery job that uses the sliced file has not ended; from phase 5
the new moment arrives in the delivery job's final report and in `GET /api/printer/mine`. At that
moment, on the Preview and Send steps only, the page shows a grey message in place of the result
on the Preview step and in place of Send on the Send step: "This plate's slice has expired. A
sliced plate is kept for two hours after it is sliced or after its last print ends. Slice it again
to print it; your parts, layout and settings are unchanged.", with **Slice again**, which goes to
the Preview step and submits with a new `submission_id`. The sentence is the wizard's. If a request
is refused first with `410` `front.sliced_file_expired` (the summary, the file, a send), or
`GET /api/slices/<slice>` answers `failed` with that error, the front server's sentence is shown in
the same place with the same button. A notification that says the sliced plate "is still here"
goes at the same moment. The page does not slice again by itself. On another step nothing shows,
and entering the Preview step afterwards slices, as for any plate not yet sliced.

Tests: on the fake clock, the message replaces the result at exactly `expires_in_s` after the fake
front server's answer arrived, not a second before, whatever the page's wall clock says; it shows
on the Send step in place of Send; on the Layout step nothing shows and the next Preview submits; a
refused Download shows the front server's sentence; "is still here" goes; `expires_in_s` `null`
shows no expiry until a later report gives one.

## The layer preview

**What must be achieved** ([The layer preview, as a requirement](README.md#the-layer-preview-as-a-requirement)):
the wizard shows the sliced file's own toolpaths, fetched with `GET /api/slices/<slice>/file` (with
its headers; never stored), and the user inspects them layer by layer, with the appearance below.
The worker reads `Metadata/plate_1.gcode` from the archive ([the sliced file](../contracts/sliced-file.md#contents))
and prepares what is drawn. **The method is not fixed:** it is found while building, because the
mockup's method (every segment a flat strip) is known not to be good enough and no better one has
been tried.

**The appearance** ([decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step)):

- Four fixed colours, one for each group of line types, whatever the filament:

  | Group | Line types | Colour |
  |---|---|---|
  | Walls | Outer and inner walls | Blue `#2b5c9e` |
  | Infill | Sparse and internal solid infill | Orange `#e0912f` |
  | Top and bottom surfaces | Top and bottom surfaces | Green `#2f9e7a` |
  | Supports and brim | Supports, their interface and the brim | Violet-grey `#9a8fb8` |

  The filament's colour is never used here.
- The **colour key**, a joined box from a small icon at the view's top left: four rows, a stripe
  and a name each, always all four, closed until asked for. No line type can be hidden.
- Each line as wide as the settings' line width at its distance from the camera, never under one
  pixel.
- Walls shaded by the way they face, by darkening only, from the walls' blue facing the light to a
  darker blue facing away, never toward another group's colour.
- The current layer drawn over the layers below, unshaded, at least two pixels wide.
- Above it each instance a ghost, a faint grey, mostly transparent shape cut at the current layer;
  gone when every layer is shown.
- No combs and no show-through at any viewing angle, edge-on and zoomed in included, for the view
  at rest. While the view is moving a simpler look is allowed, the four colours kept; the full look
  returns when it comes to rest.

**The four requirements beyond the look:**

1. At least `FPS_GRAPHICS_CARD` (30) frames a second in Chrome on the machine with a graphics card
   and `FPS_SOFTWARE` (10) on the one without, while the view is turned or the layer bar dragged, on
   a 14.1 MB sliced file and on a plate at the 150-instance limit.
2. Every 3D view (the parts' pictures, the Layout view, the layer preview) draws again after the
   browser loses its 3D drawing context, without a reload.
3. No combs and no show-through, at rest.
4. Proof by test renders of real sliced files (several plates, supports on and off, several layer
   counts, several viewing angles including edge-on and zoomed in), looked at one by one by a
   person when the preview is first built and whenever its drawing code changes.

The first layer is drawn within `FIRST_LAYER_S` (5 s) of opening the Preview step on a sliced
plate, with the print time and filament shown at once; the page stays under `PAGE_MEMORY_MB` with
the preview of a 14.1 MB sliced file open at the largest plate.

The sizes: the heaviest plate the Popcorn Penguins print has about a million lines of printer
instructions in an 8.8 MB sliced file; twelve of the robot's largest block give 10.8 MB, 14.1 MB
with supports on; 150 instances are allowed; a sliced file is at most 50 MB. Known: the flat-strip
method took 4 to 21 seconds a frame without a graphics card (4.2 s for 152,101 segments; 10 to 21 s
for some 400,000), which made Chrome lose every 3D view on the page; with a graphics card it was
fast but showed combs and show-through.

Open, and to be tried first in phase 2: whether any method meets 10 frames a second without a
graphics card at the largest plate with the required look
([The risks to try first in phase 2](README.md#the-risks-to-try-first-in-phase-2)); how the trial
is run is in [How the trials and measurements are run](#how-the-trials-and-measurements-are-run).
If none does, the decision comes back to the owner: a smaller largest previewable plate, the
Preview step unsupported without a graphics card, or a lower target.

Tests: a lost 3D context in each view, caused on purpose, draws again without a reload, twice in
one page; the layer bar by arrow keys and its screen-reader layer; the colour key always has four
rows; the readout is in millimetres; by Playwright in Chrome's engine on real sliced files, the
preview draws something and not a blank or an error, fills roughly the expected part of the view,
shows the four colours, changes when the layer bar or the view moves, and draws again after the
context is lost, any comparison with a kept picture with a wide tolerance; the same for the Layout
view.

## The Send step

One decision: send this sliced plate to the printer now, or download it. Its look is `#send-live`,
`#send-printer`, `#send-summary`, `#send-errors` and `#final-action` in the mockup, under "Send" in
`css/panel.css`.

**Phase 2** builds the step with less on it, under its name Send, so that the five steps never
change their names or order: the card of what will be printed with the instances by part, the
print time and the grams, and no printer's name; no plate-clear line and no caret; one button,
**Download the sliced file**; no printer-status icon and no message about pairing.

| Part | What it shows | Mockup |
|---|---|---|
| What will be printed | A card: from phase 5 the printer by name; the instances by part ("16 on one plate", then "8 × Gusset Plate", "4 × L Bracket"…), the print time and the grams. The printer's state is not repeated here | [decision 35](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| The plate-clear line (phase 5, a printer paired) | Above the button: "⚠ Check that the plate is clear and PETG is loaded. Send starts the print at once." | [decision 35](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| The Send button (phase 5) | A wide blue button, "Send to Shop H2S", with a caret whose menu offers **Download the sliced file**. Choosing from the menu changes what the button does; it does not act; the menu's send item has the button's label. Send sends at once, with no confirmation. By keyboard, Enter on the caret opens the menu on its first item, arrow keys move, Escape closes. Back keeps its width | [decision 36](../docs/mockups/print-wizard/DECISIONS.md#send-step), M23 |
| Download | Saves the sliced file to the user's computer, by a plain link to `GET /api/slices/<slice>/file?group=<id>`, so that the browser saves it without the page holding it, under the name of the details' `file`; leaves a notification naming the plate in words and the file's true size (`size_bytes`) | [decision 36](../docs/mockups/print-wizard/DECISIONS.md#send-step), fake 11 |
| No printer paired (phase 5) | Nothing names a printer: no printer's name on the card, no plate-clear line, the button Download the sliced file with no caret, beside the message of [When Send is not offered](#when-send-is-not-offered) | [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step), departed from |

A Download refused because the sliced file expired is shown as
[A sliced plate that expires](#a-sliced-plate-that-expires) says: the page asks the details first
(*proposed*), so that the refusal reaches the page rather than the browser's download.

Tests: in phase 2 the step has the card, the one button and nothing that names a printer; Download
fetches with the current group in the query and shows the notification with the true size; an
expired file shows the expired message in place of the button.

### After Send

Send is `POST /api/printer/deliveries` with `{"slice": "<id>"}` and, while who writes the one-line
description is open, its `description` ("8 instances of Gusset Plate", *proposed*: the page writes
it from the plate), which the front server ignores if it writes its own. Open:
[Who writes the one-line description of a plate](README.md#who-writes-the-one-line-description-of-a-plate).

| Answer | The page |
|---|---|
| `202` with `delivery` (`id`, `slice`, `progress`) | Keeps nothing of it in the browser's storage (a returning page asks `GET /api/printer/mine`), shows the print card and opens the delivery job's progress stream |
| `410` `front.sliced_file_expired` | The expired message, with the front server's sentence |
| `409`, `503` printer delivery's refusal (no printer paired, not heard from, unreachable, busy or paused, another delivery job on its way) | Its sentences in place of Send; never retried by itself |
| `409` `delivery.job_in_flight` to a send the page had sent before | Asks `GET /api/printer/mine` and follows the live delivery job when it uses the same slice job, as if its first answer had arrived |
| `429` `delivery.rate_limited` | Its sentence |

The **print card** at the top: the plate in words ("16 instances, on Shop H2S"), its stage on a
track (Sending, Starting, Heating, Printing, Done), and its figures: percent, layer of total, time
left, expected finish and when it was sent. The button is off and follows the stage ("Sending…",
"Heating…", "Printing…", "Waiting for a person…")
([decision 37](../docs/mockups/print-wizard/DECISIONS.md#send-step), M11). Under the track the
card gives the stage in the words of printer delivery's progress report, `stage_label`. Which of
printer delivery's nine stages stands under which word of the track
([The stages](../delivery/README.md#the-stages-what-a-user-sees-and-what-can-be-cancelled),
[its states and stages](../delivery/README-details.md#states-and-stages)):

| Track | Printer delivery's stages |
|---|---|
| Sending | The three waits (for the daemon, for the printer, for an earlier print), the fetch and the upload |
| Starting | Starting, and "start not shown yet" |
| Heating, Printing | Printing, by what the printer reports (heating under Heating) |
| Printing, the card amber | Waiting for a person |
| Done | The delivery job's final `done` |

| State | What the user sees | Mockup |
|---|---|---|
| On its way, until printer delivery allows the print to start | **Cancel sending**, which sends `POST /api/printer/deliveries/<delivery>/cancel`. Cancelled (`200`, or `202` and then the stream's `cancelled`): a notification, "Sending cancelled. Nothing reached Shop H2S and nothing will print. Your sliced plate is still here.", which goes when the plate is sent again. From the moment the relay has allowed the start, Cancel sending is no longer offered; a cancel that arrives just after is answered `409` `delivery.start_being_sent` or `delivery.cancel_too_late`, whose sentence the card shows while it goes on following the plate | [decision 37](../docs/mockups/print-wizard/DECISIONS.md#send-step), M22 |
| Printing | The figures. No pause or stop: that is done at the printer's screen | [decision 38](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Waiting for a person | An amber message in printer delivery's sentences, of the kind "Filament ran out. Load new filament, then resume the print on the printer's screen." A stage, never an end | [decision 39](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Failed | The card says so in printer delivery's sentences, of the kind "The print stopped at layer 51 of 134 (38%): the printer reported a filament tangle or a clogged nozzle. Clear the plate and check the filament path at the printer, then send the plate again from here. The sliced file is still here.", with folded Details: where the printer's screen shows the fault and what to check | [decision 40](../docs/mockups/print-wizard/DECISIONS.md#send-step), [decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Finished | No card; the last-print note at the top of the step: "Your print finished at 11:25 am." | [decision 40](../docs/mockups/print-wizard/DECISIONS.md#send-step), [decision 60](../docs/mockups/print-wizard/DECISIONS.md#the-users-last-print-version-7) |

After a print that finished or failed, Send is enabled again for the same sliced plate, under the
plate-clear line, for as long as the sliced file is kept; the final report's `sliced_file` gives
the new moment of expiry. Nothing says "late" or "behind its estimate" (M24). What the printer
really reports while waiting and on failing is unknown until recorded in phase 5; the quoted
sentences are examples.

### When Send is not offered

States, not failures, so the sentences are the wizard's, from `GET /api/printer`. A send that
printer delivery refuses all the same, because the printer became busy between the page's last
news and the press, is shown with printer delivery's sentence in the same place.

| The printer (`state`, `current`) | What the step shows | Mockup |
|---|---|---|
| Busy with another user's plate (`current.from_penguinslicer` true, not the user's) | A **busy card**: "Shop H2S is busy: printing for Alex Chen.", what it is (`description`, "8 instances of Gusset Plate"), percent, layer, time left and expected finish; the line "Send comes back when the printer is free; nothing queues."; Send off; the sliced plate stays ready | [decision 41](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Busy with a print nobody sent from PenguinSlicer (`from_penguinslicer` false) | The busy card: "Shop H2S is busy: printing something that was started at the printer, not from PenguinSlicer.", with percent, layer, time left and expected finish, no sender or description; the same line | None: designed in the guide |
| `offline`, no print followed | An amber message: "Shop H2S has not been heard from for 7 minutes, so Send waits. Your sliced plate stays ready, and Send comes back as soon as the printer answers. Or download the file.", the minutes from `silent_for_s`, with Download. No guess at the cause | [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| `not_heard_from` | Send off, with one line: "Waiting to hear from Shop H2S." (a few seconds after the front server restarts, up to half a minute after pairing) | None: designed in the guide |
| `no_printer` | An amber message: "No printer is paired with PenguinSlicer, so nothing can be sent. Anyone in 6238 (Popcorn Penguins) can pair one: start the PenguinSlicer program on the computer beside the printer and type the code it shows.", then the link **Pair a printer**, which opens the printer details, then "Meanwhile, download the file and print it from Orca Slicer or Bambu Studio.", and Download. The step has no pairing form of its own, and nothing on it names a printer | [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step), departed from |

**Nothing queues:** a send to a busy printer is refused rather than held, because a queued plate
would start by itself on a plate nobody has cleared.

### A print that has gone quiet

A print has **gone quiet** when its report is `stale` (no report for 40 seconds, as printer
delivery reckons it; `current.stale` in `GET /api/printer`). The print card keeps its last
figures, greyed, with an amber line: "No news from Shop H2S since 11:02 am. The print may still be
running; these figures are from then.", cleared by the next report. After two minutes without news
the printer's `state` is `offline` and the icon says Offline. When both hold, the print's rows
win: the icon says Offline, and the Send step and the printer details go on showing the print card
or the busy card with its greyed figures, not the Offline message.

Once a print that had started has gone quiet, **Stop following** appears for the sender of the
print only (the print's `sender.you` true, and its `delivery` id given), on the print card and in
the printer details. It asks in a confirmation: "Stop following this print? PenguinSlicer will no
longer show its progress and cannot say how it ended. The print itself is not stopped; that is done
at the printer's screen." with **Stop following** and Keep following. Going ahead sends
`POST /api/printer/deliveries/<delivery>/stop-following`:

| Answer | What the user sees |
|---|---|
| `200`, the final report `failed` with `delivery.outcome_unknown` | The card goes; a notification: "Stopped following your print on Shop H2S. How it ended is not known."; Send comes back once the daemon answers again and the printer is free |
| `409` `delivery.still_reporting`, `delivery.start_not_shown_yet` or `delivery.not_started` | Stopping is refused; the card shows the fresh figures |
| `409` `delivery.already_finished` | The card shows how it ended |

The wizard withholds the link from other users; printer delivery checks that the request comes
from the sender. If the sender is away, the print holds the printer until the daemon reports again
or the relay gives it up by its own rule after a day without word, which reaches the page as
`failed` with `delivery.outcome_unknown`. A plate the relay had not yet allowed to start needs none
of this: Cancel sending is still offered.

Open: what the printer-status icon and the printer details show after a print is no longer
followed ([After a print is no longer followed](README.md#after-a-print-is-no-longer-followed)).
Never show it as Failed; tell this ending from a fault at the printer by `delivery.outcome_unknown`;
build the rest once it is decided.

Tests (fake clock; the fake front server standing in for the relay): a report `stale` greys the
card with the line and a fresh one clears it; `state` `offline` with a stale print keeps the card
while the icon says Offline; Stop following appears only for a started print and only to the
sender; confirmed, the card goes with the notification; each refusal shows what the table says;
Cancel sending before the start; a cancel answered as too late shows printer delivery's sentence
and the card goes on.

## The printer, from phase 5

The page asks `GET /api/printer` when it opens, every `PRINTER_POLL_S` after, and after each
pairing, unpairing and send. It shows what that answer says; a delivery job of the user's own is
followed on its progress stream as well.

### The printer-status icon

On every step at the right of the header: a printer, a dot and a word
([decision 43](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon)). Its look is
`#pstat` and `#pstat-pop` in the mockup.

| The icon says | `state` |
|---|---|
| Free (green) | `free`. A printer is Free as soon as a print finishes; there is no "Finished" |
| Sending 40% (blue, pulsing) | `sending` |
| Heating, or Printing 61% (blue, pulsing) | `starting`, `heating`, `printing` |
| Waiting (amber) | `waiting_for_person` |
| Failed (red) | `failed`: a print ended on a fault someone at the printer has to see to |
| Offline (grey) | `offline` |
| No printer (grey) | `no_printer` |
| A grey dot and "…" | `not_heard_from`; also while a sign-in could not be made |

A print card that was showing keeps its last figures through the seconds after a restart; a page
first opened then shows the grey dot and "…" and the Send step's line until the daemon's next
report. The printer's name is the answer's `name`, the one the printer reports; nobody types it.

**The printer details**, a joined box that grows down from the icon
([decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon)): open after the
pointer rests on the icon for `DETAILS_OPEN_MS`, stay open while the pointer is over the icon or the
details, close `DETAILS_CLOSE_MS` after it leaves both; a click opens and pins them until a click
elsewhere, Escape, × or a second click on the icon; a click on details opened by the pointer pins
them; a tap or Enter is a click; opening them closes the change details. The icon has no tooltip; a
screen reader hears one sentence ("Shop H2S is free").

| State | The details say, under the printer's name |
|---|---|
| Free | "Nothing is printing.", and after a print that finished (`last_print`, `ended` `done`), "Last print finished 11:25 am (Alex Chen)", "(you)" for the user's own; the line goes when the user sends another plate or 12 hours after the print finished |
| Sending | The plate's description, who sent it, percent sent, time left, expected finish and a bar |
| Printing or heating | Who sent it ("(you)" for the user), percent done, time left and expected finish. A print started at the printer: "Started at the printer, not from PenguinSlicer.", then the same figures |
| Waiting for a person | Who sent it, percent done, and what to do at the printer, in amber |
| Failed | Who sent it, and when it stopped and at which layer |
| A print gone quiet | The last figures, "No news since 11:02 am.", with Stop following for the sender of the print only; for as long as the print is followed, also after the icon turns to Offline |
| Offline, no print followed | "Not heard from for 7 minutes."; with `silent_at_least` true, "Not heard from for at least 3 minutes." |
| Not heard from yet | "Waiting to hear from Shop H2S." |
| No printer paired | "PenguinSlicer needs to be paired with a printer.", and the pairing form |

At the bottom, whenever a printer is paired, **Unpair this printer**. Users of one group see each
other's names and a one-line description of the plate printing; nobody outside the group sees
either.

Open: an old daemon, which printer delivery's guide recommends the printer details report, from
the optional `daemon` field ([Daemon versions](../delivery/README.md#daemon-versions)).

Tests: each `state` gives its icon and details; the details open at 150 ms of rest and close 300 ms
after leaving, on the fake clock; a click pins them; `silent_at_least` gives "at least"; Stop
following shows only with `sender.you`; the last-print line goes on the user's next send and at 12
hours.

### Pairing a printer

Someone starts the PenguinSlicer program on the computer beside the printer, which shows a pairing
code of eight letters and digits ("B6MQ-DN77"); any signed-in user of the group types it into
PenguinSlicer, from any computer. The code is good for fifteen minutes and one use. The **pairing
form** is in the printer details only: one field, "Pairing code", taking capitals or small letters
with or without the hyphen; a **Pair** button; a link, "How to pair a printer", to a documentation
page written in phase 5 (fake 22). Pair sends `POST /api/printer/pairing` with `{"code": …}`.

| Answer | What the user sees |
|---|---|
| `201` with the printer, `state` `not_heard_from` | The form goes; a notification: "Paired with Shop H2S. Everyone in 6238 (Popcorn Penguins) can now send to it."; the icon shows the grey dot and "…" until the daemon first reports, within about half a minute |
| `404`, printer delivery's one report for every wrong code | At once, in red under the field, its sentence, of this kind: "No computer beside a printer is showing that code right now. Check the code and try again in a moment." |
| `429` `delivery.rate_limited` | The field and the button off for the wait, with printer delivery's sentence, of this kind: "Too many wrong codes. Wait a minute, then try again." |
| A wrong-code answer to a pairing the page had sent before | The page asks `GET /api/printer`; if the group now has a printer paired, it shows the success |

**Unpairing.** **Unpair this printer**, at the bottom of the printer details and nowhere else,
asks in a confirmation: "Unpair Shop H2S? Nobody in 6238 (Popcorn Penguins) can send to it until it
is paired again." with **Unpair** and Keep, and sends `DELETE /api/printer/pairing`; after it the
icon says No printer. While a print PenguinSlicer is following is going on the link is off, with the
line "Shop H2S is printing; unpair it when the print has ended." Any user of the group may pair and
unpair.

Open: the limit on wrong codes, proposed at ten a minute for each user
([The limit on wrong pairing codes](README.md#the-limit-on-wrong-pairing-codes)); show the sentence
as it is. Open: whether the relay itself refuses an unpairing during a print, and pairing again
while paired or a pairing whose daemon never finishes (`pairing` `awaiting_daemon`)
([Open items of the other guides](README.md#open-items-of-the-other-guides-that-would-change-the-panel));
show any refusal's sentence. Open: what the printer's required mode costs a group, for the how-to
page ([The printer's required mode](../delivery/README.md#the-printers-required-mode)).

Tests: each answer of the table; the field accepts "b6mq dn77" and "B6MQ-DN77"; a lost answer
followed by a wrong-code answer shows the success when the printer is paired; Unpair asks, is off
during a followed print with its line, and leaves No printer.

## When a user comes back

A page that has lost what it had in memory (a refresh, a closed and reopened panel, a laptop opened
after lunch) reads its plate from the browser's storage
([Which plate a tab shows](#which-plate-a-tab-shows)), asks `GET /api/slices/<slice>` about the
plate's slice job when it has one and, from phase 5, `GET /api/printer/mine`, and opens where the
user will want to be. The rows are tried in order; the first that applies decides.

| What the page finds | Where it opens, and what it says | Mockup |
|---|---|---|
| The plate's slice job has a delivery job in `/api/printer/mine` (`live`, or `last_print`), running or ended, and its sliced file is still kept (phase 5) | The Send step. While it runs, a notification: "Back where you were. You had sent your plate to Shop H2S before you left; its progress is below.", which goes when the print ends. After it finished: the last-print note. After it failed: the failure on the print card. Send is enabled again for the same sliced plate while its sliced file is kept | [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), departed from |
| Parts, and no slice job | The stored step (Parts, Settings or Layout), with the plate as it was. Nothing is said | [decision 47](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), departed from |
| `queued` or `running` | The Preview step with its progress; a notification: "Back where you were. Your plate was still slicing when you left; see below." | [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work) |
| `done`, with `sliced_file` | The Preview step with the result; a notification: "Back where you were. Your plate was sliced and ready to send when you left." | [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work) |
| `failed`, with an error other than `front.sliced_file_expired` | The Preview step with the failure's message, as if the page had stayed open | |
| `cancelled` `replaced` | Follows the later slice job of the same plate, whose id the stored plate already holds | |
| `cancelled` `shutdown`, or `404` `front.slice_unknown` for a slice job submitted less than `SLICED_FILE_KEEP_S` ago (the slice service restarted) | The Preview step. The page uploads the parts again and submits the plate again by itself with a new `submission_id`, and the slicing card starts from the beginning | None: designed in the guide |
| `failed` with `front.sliced_file_expired`, or `404` `front.slice_unknown` for a slice job submitted more than `SLICED_FILE_KEEP_S` ago | The stored step, with the parts, the layout and the settings as they were. If that step is the Preview or the Send step, the expired message stands in place of the result, with **Slice again**, and the page does not slice again by itself. From an earlier step, entering the Preview step slices | [decision 48](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), departed from |

- The page tells the two "unknown" rows apart by the time it kept when it submitted, not by
  anything the front server says.
- A plate with a print is held by the first row longer than two hours from its slice, since a
  print keeps its sliced file until two hours after the print ends.
- A stored plate outlives its sliced file: the sliced file lasts two hours, the stored plate 12
  hours from its last use. A returning page never empties the plate.
- A page that reloads itself for a new version is a returning page that says nothing
  ([Reloading for a new version](#reloading-for-a-new-version)).
- Work does not follow a user to another computer or browser, nor between Onshape's panel and a
  tab: there the wizard opens empty.

### The user's last print

When the user's own print finishes, the **last-print note**, "Your print finished at 11:25 am.", a
line and not a card: at the top of the Send step, above the Send of the same plate or of a new one,
and, when the user comes back, on whichever step opens, until the user leaves that step. It goes,
with the printer details' "Last print finished…" line, when the user sends another plate or
`LAST_PRINT_NOTE_H` (12 hours) after the print finished, whichever comes first
([decision 60](../docs/mockups/print-wizard/DECISIONS.md#the-users-last-print-version-7)); the
finish time is `last_print.ended_at`. A print that failed is not a line: it is the failure on the
print card, on the Send step, where the returning page opens.

Tests: every row of the table reached on purpose with the fake front server, the rows' order
checked (a plate with an ended print and an unknown slice job submitted three hours ago opens on the
Send step); the "unknown" rows split at exactly two hours on the fake clock; an expired plate on the
Preview step shows the message with Slice again and keeps parts, layout and settings; the last-print
note goes at 12 hours and on the next send.

## Reloading for a new version

Every answer carries `X-PenguinSlicer-Version`, and a progress stream its `version` event. Versions
are compared by the part before the hyphen. A page that sees a version newer than its own reloads
itself, and never refreshes under a person who is looking at it or touching it. It reloads at only
two moments:

- when the user moves between steps of the wizard, where the panel is redrawn anyway; or
- when at least `RELOAD_IDLE_S` (120 s) have passed since the user last interacted with the page (a
  pointer movement, a key or a scroll).

In either case it waits while a request of its own is pending; an open progress stream does not
count, since the reloaded page reconnects and is told the latest report at once. A page that sees an
older version does nothing. Until it reloads, the older page goes on working against the newer
front server, which the contract requires of every change; the page fetches every file of its own
code when it loads and nothing later by name.

**What the user sees:** nothing. No message and no "Back where you were", because before reloading
the page notes in the browser's storage that the reload is its own (*proposed* record `selfReload`),
and the next load clears it. The page reopens on the step it was on, in advanced mode if advanced
mode was open, with the parts, the layout, every change, a running slice's progress and a print's
progress. What starts afresh is only what lived in memory: advanced mode's sections and setting
groups all open again, the 3D views at their starting camera, the Layout step's selection cleared,
the layer bar at the top layer, open joined boxes and notifications closed. Keep that list short.

Tests (fake clock; the fake front server announcing a newer version): no reload while a request is
pending, and a reload once it is answered; with no input, a reload at exactly 120 s and not at
119.9 s; a step change reloads at once; an open progress stream does not hold the reload; an older
version does nothing; after the reload, the stored step and advanced mode reopen and no notification
shows; a page loaded from the previous release's code runs against the new fake front server.

## What the browser keeps

The browser's storage is the record of a user's parts and plate; nothing on a server is. It is
IndexedDB (*proposed*), since a page's simple key-value storage holds only a few megabytes, and every
read and write goes through one module (*proposed* `store`) so that a refusal is handled in one
place. Each change is written at once, so a refresh at any moment loses nothing.

**A plate for each tab.** Each tab works with its own stored plate, keyed by its `plate_id`; a part
added in one tab never appears in another, and one tab never writes over another's work.

| Record (*proposed* names) | What it holds | Kept until |
|---|---|---|
| `plates/<plate_id>` | The user's `user.id` and the `group` id the plate was made in; the parts (each part's bytes exactly as they arrived, its name, units, hash and part record); the layout (each instance's part, rotation and position); the settings (filament and profile by name, every change); the slice job's id, `submission_id`, fingerprint and the time submitted; the step, and whether advanced mode is open; the time last used | The plate is dropped |
| `uploadUnits` | How STL files are read | The user changes it; cleared with the user's work |
| `currentGroup` | For a user in several groups outside Onshape, the current group | The same |
| `owner` | The `user.id` the stored work belongs to | A different user signs in |
| `signInTrip`, `selfReload` | That a trip to Onshape, or a reload, is the page's own | The next load |

A refreshed tab finds its own plate through the browser's per-tab storage (*proposed*:
`sessionStorage` holding the `plate_id`), which survives a refresh and the page's own reload and
dies with the tab.

### Which plate a tab shows

A newly opened tab, or a panel opened again, takes up the user's most recently used stored plate of
its current group, if it was used less than `PLATE_UNUSED_H` (12 hours) ago and no other open tab
holds it; otherwise it starts an empty plate with a new `plate_id`. So a user who closes the panel
and opens it again finds their plate, and a second tab beside the first gets a new plate. The tabs
know which plates are held through a lock the browser releases when a tab closes or crashes
(*proposed*: the Web Locks API, one lock named by each `plate_id`), so a dead tab never holds a plate
for ever.

**When a plate is dropped.** A stored plate that no tab holds and that has not been used for 12 hours
is dropped, checked when any page opens; a plate an open tab holds is never dropped under it. A plate
is also dropped when the user presses New plate in its tab or changes the current group, and every
stored plate, with `uploadUnits` and `currentGroup`, is cleared when `/api/me` names a different user
from `owner`.

**When storage fails.** The storage must hold 25 parts of up to 7.5 MB, about 190 MB, for each tab's
plate. When the browser refuses to store a part, because the site's allowance is full, the part is
still added and can be sliced, with an amber line on its row: "This part could not be saved in this
browser, so a refresh will lose it.", and a `storage_refused` report. When the browser has cleared the
storage, the wizard opens with an empty plate and sends a `storage_cleared` report (*proposed*: known
by an `owner` record gone while `sessionStorage` still names a plate). Open: how often either happens
([Whether the browser's storage reliably holds a full plate](README.md#whether-the-browsers-storage-reliably-holds-a-full-plate));
if refusals are common, the 12 hours or the number of plates kept may come down.

The page never stores a sliced file and never sends one; it fetches the sliced file through the
front server each time it needs it. Each part is sent once, when it is added, and is named by its hash
from then on; on the Preview step the page sends only the plate configuration, so slicing again
uploads nothing. The part store's copy is a cache the page refills on `slice.part_missing`.

Tests: several pages on one fake storage: each keeps its own plate; a new tab takes up a plate only
when no other holds it and it was used less than 12 hours ago (11 h 59 min yes, 12 h no, on the fake
clock); a closed tab's lock is released and its plate can be taken up; a plate no tab holds is dropped
at 12 hours and one an open tab holds is not; a different user's sign-in clears every plate; a full
plate of 25 parts of 7.5 MB stored, the page reloaded, everything back; a refused write, caused on
purpose by a fake storage, gives the amber line and one report; a cleared storage opens empty with one
report.

## Inside Onshape's panel and in a tab

The wizard is one body of code with two homes: a page opened directly in a tab, from phase 2, and
the same page in Onshape's right panel, from phase 4, told apart by `in=onshape` on its address.

| | In a tab | In Onshape's panel |
|---|---|---|
| Parts come from | Uploaded STL files | A click on a part in Onshape, through the Onshape integration, as a part set |
| A part's units | The switch beside the upload area | The units of the Part Studio or Assembly |
| Where to mend a broken part | "your CAD program" | "Onshape" |
| Sign-in | Thirty days from its last use; the page's own trip to Onshape when it is missing; a Sign out link | Connect the first time in a browser, with a small window that closes itself; after that as long as the user is signed in to Onshape; no Sign out link |
| The group | The user's one group; a user in several chooses | The group of the document the user has open; never chosen |
| The browser's storage | Shared by every tab at the same address, each with its own plate in it | Kept apart by Chrome from the tabs', although the address is the same; each Onshape tab with its own plate in it |
| Width | Whatever the window gives | Whatever the user drags the panel to, from 320 px |

Open: what only real Onshape can settle in phase 4: whether Onshape tells a panel the user and the
company; whether the trip can be invisible inside the panel; how wide and narrow the panel can be
dragged; whether the page stays open across a document's tabs; whether full screen works from inside
it; how Onshape's trackpad gestures sit beside the Layout step's; and whether Chrome keeps allowing an
embedded page its cookie and storage
([What only real Onshape can settle](README.md#what-only-real-onshape-can-settle),
[The cookie inside Onshape's panel](../front/README.md#the-cookie-inside-onshapes-panel)).

## Browsers

Chrome, the current stable version on a desktop or laptop, is supported; every measurement is made
in it. Edge is tested, which costs a second run of the checks that need a real browser. Safari is not
supported, in the panel or outside it: the front server answers it with a plain page, and nothing of
the wizard is designed or tested for it. Any other browser is neither tested nor blocked
([Browsers other than Chrome](README.md#browsers-other-than-chrome)).

## Accessibility

The wizard's accessibility is the mockup's, and no more is a goal of this version.

- The step circles, advanced mode, the printer-status icon and the Send button's menu can be reached
  and worked by keyboard, with focus visible; focus in advanced mode as
  [Advanced mode](#advanced-mode) says.
- A tooltip appears at once on keyboard focus of an icon or a step circle; nothing a user needs is
  said by a tooltip alone.
- The printer-status icon gives a screen reader one sentence ("Shop H2S is free"); the layer bar moves
  with the arrow keys and reports its layer.
- The Send button's menu: Enter on the caret opens it, arrow keys move, Escape closes.
- Colour never carries a meaning alone: a message has its sentence, the icon its word, a changed
  setting its dot and bar; the layer preview's four colours were checked for the three common kinds
  of colour blindness.
- Text at 14 px or larger, the pointer line at 11 px the one exception; amber darkened to `#9a6700`.

Not designed: keyboard support on the Layout step beyond F, Ctrl+1, Ctrl+A and Escape (its buttons
are ordinary buttons, parts arrive laid their best way and Arrange places them, so a plate can be
taken from Parts to Send by keyboard); anything a screen reader is told of the plate or of the layer
preview beyond the layer bar; conformance to a published standard.

Tests: the step circles, advanced mode, the icon and the Send menu reached and worked by keyboard
with visible focus; the icon's sentence and the layer bar's layer in the accessibility tree; a plate
taken from Parts to Send by keyboard alone.

## Security

- **The browser holds no secret.** No key, token or pairing code in the page's code or in the
  browser's storage; the pairing code is typed once and is dead after use. The cookie is set by the
  front server, `HttpOnly`, and the page's code neither reads nor writes it.
- **The page never says who the user is.** No request names a user; the front server takes the user
  from the cookie. The page names the current group, which the front server accepts only if the cookie
  lists it.
- **The wizard's mark** on every changing request, from phase 2
  ([The wizard's mark and the origin](../contracts/wizard-front-server.md#the-wizards-mark-and-the-origin)).
- **What the page trusts:** only the front server, at its own address. It loads no code, font or
  picture from any other site and makes no request to one; its fonts and pictures are served under
  `/assets/`. The content security policy the front server sends on every page answer makes that
  a rule of the browser; its whole value, and what it allows the wizard (no inline script, no
  `style` attribute or element in markup, workers from its own files or `blob:`, no WebAssembly
  until a drawing method needs it), are in
  [The wizard's built files](../contracts/wizard-front-server.md#the-wizards-built-files).
- **What it treats as hostile:** a part's name, another user's name, a plate's description, a group's,
  profile's, filament's or printer's name, the table of settings' words, and an error report's
  sentences, all shown as text and never as markup; an uploaded file, whose reading is bounded by the
  size limit and ends, if malformed, in a notification and never in a frozen panel. A message from the
  sign-in window is accepted only from the front server's own address.
- **What a flaw would expose:** code run in the page could read the stored parts and start a print on
  the group's printer; it could not read the cookie or any server secret.
- **One user's work is never shown to another:** the stored work carries its `owner` and is cleared
  when a different user signs in; outside Onshape a user can sign out.
- **The reports about itself hold no user's work:** never a part's bytes or geometry, never a part's
  name in a drawing summary, never the storage's contents; a failure report names a part by its hash.
- **Accepted risks:** the parts sit unencrypted in the browser's storage until their plate is dropped,
  12 hours after its last use for a plate nobody opens again; users of one group see each other's
  names and what is printing; any user of a group can send a print or unpair from anywhere.

Tests: hostile names and sentences (markup, scripts) render as text; no request leaves for another
origin (the fake front server and the content security policy); nothing secret is in the browser's
storage after pairing; every `POST`, `PUT` and `DELETE` carries the mark; a reply from the sign-in
window from another origin is ignored.

## What the wizard reports about itself

The page tells the front server two kinds of thing about itself, which the front server writes to the
log ([The page's reports about itself](../contracts/wizard-front-server.md#the-pages-reports-about-itself)).
Both go through one module (*proposed* `reports`) that holds the page to `REPORTS_PER_MIN`, sends each
report once, and drops a report that cannot be sent or is refused (`429` `front.too_many_reports`),
never retrying it. Each carries `page`, a random id the page makes when it loads. A page that is not
signed in drops its reports.

**Failures in the browser,** `POST /api/reports/failure`: `what` one of `part_not_drawable`,
`storage_refused`, `storage_cleared`, `drawing_context_lost`, `layout_failed` (the layout code failing
on a part) or `page_failed` (the page's own code failing, caught by a handler for uncaught errors and
rejected promises). A `wizard.layout_failed` answer from the worker is reported as `layout_failed`
only when the geometry's code failed on a part; when the page asked for something wrong (a message
the worker does not know, a part never read, a malformed instance), it is reported as `page_failed`,
so the worker tells the two apart in its answer when the reports are built; `step` (`parts`, `settings`, `advanced`, `layout`, `preview`, `send` or `none`);
`browser`, `browser_version`; `software_3d`; `part_sha256` when a part is concerned; `detail`, the
error's message and where it arose, at most 1,000 characters, never a part's name, bytes or geometry,
or anything from the storage.

**How it draws,** `POST /api/reports/drawing`: one summary for each use of the Layout view and of the
Preview step, sent when the user leaves the view, never frame by frame: `view`; `fps_typical`,
`fps_worst`; `first_layer_ms` (preview); `longest_hold_ms`; `instances`; `sliced_file_bytes`,
`sliced_file_lines` (preview); `browser`, `browser_version`, `os`; `drawing` (`graphics_card` or
`software`) and `graphics_card` as the browser gives it; `processors`, `memory_gb` as the browser
reports them; `panel_width_px`, `pixel_ratio`; `in_onshape`. No part names and no geometry.

The figures come from the same measuring the tests use, so a test and the log speak of the same
frame rates and the same longest hold.

Tests: each `what` produced on purpose sends one report with exactly the contract's fields; a drawing
summary holds no part name; at `REPORTS_PER_MIN` the next report in that minute is dropped, on the
fake clock; a refused or failed report is not sent again.

## What the other components must still provide

The contracts now hold most of what the wizard needs: the moment of expiry, the page's reports,
signing out, the sign-in trip, the groups read again by the front server, the default served in place
of an invalid configuration, no request to cancel a slice, no limit of one slice job for each user,
`cancel_reason`, the `plate_id` and `submission_id`, `slice.stopping`, units for each part, the table
of settings with Orca's words, and `orca_sentence`. What is still to be built in the other components,
or is not yet in a contract:

| Needed | From | For |
|---|---|---|
| A general rotation for an instance, so that a part laid on any hull face can be sliced; in [the contract](../contracts/plate-configuration.md#an-instance-in-phase-2) | The slice service, phase 2 | [Laying an instance on a face](#laying-an-instance-on-a-face) |
| Every parameter setting accepted as a change, and the table of settings supplied; as built, four overrides are accepted | The slice service, phase 2 | Advanced mode |
| Parts uploaded alone and kept in the part store by user key, hash and units; plate configurations naming parts by hash; `plate_id` and `submission_id`; `slice.stopping`; `cancel_reason`; `ahead`; `orca_sentence`; a slice ended when its file would be over 50 MB; as built, a plate configuration arrives with its STL files | The slice service, phase 2 | Parts, the Preview step, coming back |
| The shared set of plates for the two placement checks, kept with the contracts | The slice service, with the wizard | [Arrange and the placement check](#arrange-and-the-placement-check) |
| Sentences that say "a new plate" and never "a second plate" | The slice service, phase 2 | [Who writes the sentences of a failure](#who-writes-the-sentences-of-a-failure) |
| Sentences that say "your CAD program" and never a role word or "the print server" | The slice service and printer delivery, as known work | The same |
| The printer's name sent by the daemon; Stop following accepted from the sender only; who sent a print, its description, the last print and its layer; the user's own live and last delivery job; the time a daemon went silent across a restart; a print started at the printer reported with no sender | Printer delivery, phase 5 | The printer-status icon, the printer details, the busy card, coming back |
| An ending of a print no longer followed told apart from a fault at the printer in the printer's `state` (open) | Printer delivery, phase 5 | [A print that has gone quiet](#a-print-that-has-gone-quiet) |
| Whether Onshape tells a panel the user and the company | The Onshape integration, phase 4 | [Inside Onshape's panel](#inside-onshapes-panel-phase-4) |

## Performance targets

| Requirement | Figure | Status | Checked by |
|---|---|---|---|
| Narrowest panel | 320 px, no sideways scroll, nothing cut off | The plan | Every screen at 320 px, looked at |
| Tooltip delay; printer details close | 150 ms; 300 ms | The mockup | Fake clock |
| Quiet retrying; retrying in all | 20 s; 300 s, waits doubling 1 to 30 s | The guide | Fake clock |
| A progress stream counted as failed | 20 s failing to reopen, 45 s open and silent | The guide | Fake clock, fake front server |
| The main thread held | Never over 250 ms, any step, any plate up to the limits, on the machine without a graphics card | Set; unmeasured | Measured by the page in tests and real use |
| A part's row says it is slow | 4 s | The mockup | Fake clock |
| One part; different parts; instances | 7.5 MB (150,000 triangles); 25; 150 | The slice service's | One over each |
| Storage in the browser | 25 parts of 7.5 MB for each tab's plate | Follows from the limits | A full plate stored and reloaded |
| A stored plate | Dropped after 12 hours unused, once no tab holds it | Set | Fake clock |
| Faces found | Patches within 100 ms of selecting | Met: at most 4.1 ms for `hub-150k.stl` in the worker in Chromium on the machine without a graphics card, the faces having been found on arrival; found from nothing, 215 ms for it and at most 84 ms for a real part | The second trial, `make -C wizard trials-geometry` |
| Auto-orient | Best way within 1 s of arriving | Met: at most 272 ms for `hub-150k.stl` from the file to its best way, faces included; at most 177 ms for a real part | The same |
| Arrange | Under 2 s for 150 instances | Met: at most 30 ms for 150 of `hex-spacer.stl` (all placed) and 56 ms for a mix of 150 real parts (104 placed, the rest beside the plate) | The same |
| The placement check | Keeps up with a drag at 150 instances | Met: at most 4.4 ms for each check of a drag at 150 instances, against one frame of 100 ms at 10 frames a second | The same |
| The Layout view | 30 frames a second with a graphics card, 10 without, while dragging or turning, at 150 instances of parts up to 150,000 triangles | Set, no measurement | Timed in Chrome on both machines; reported in real use |
| The layer preview | 30 with a graphics card, 10 without, while turning or dragging the layer bar, on a 14.1 MB sliced file and at 150 instances; a simpler look while moving | Set; the one method tried took 4 to 21 s a frame without a graphics card | Timed in Chrome on both machines; reported in real use; test renders |
| The first layer drawn | Within 5 s, print time and filament at once | Set; unmeasured | The same |
| The page's memory | Under 1 GB at the largest plate with the preview of a 14.1 MB sliced file | Set; unmeasured | Measured in Chrome at that plate |
| Before a self-reload | 120 s since the user last interacted, or a step change | Set | Fake clock |
| Reports about itself | A few a minute from one page | Set; the front server has its own limit | Fake clock |
| A sliced file | At most 50 MB; 8.8 to 14.1 MB on the plates measured | The slice service's and the front server's | A slice whose file would be larger ends with the slice service's sentence |

The **machine without a graphics card** is the container the project's agents work in, an aarch64
Linux machine on which Chrome draws 3D in software; the **machine with a graphics card** is the
owner's Mac, in Chrome.

## The project and its tools

The wizard is plain JavaScript in the browser, as [the plan](../docs/plans/penguin-slicer-plan.md#the-repository)
says: ES modules loaded by the browser as they are, with no bundler, no framework and no
package from npm at run time or in its tests. Its build and its browser tests are Python, as
the other components are: `wizard/` is a `uv` project of its own, with its own
`pyproject.toml`, holding only the tools that build and test the page.

| Folder | What it holds |
|---|---|
| `wizard/src/` | The page: `index.html`, its modules, the workers' modules, the style sheets taken over from the mockup's `css/panel.css`, fonts and pictures. As built, `index.html` and `main.js`, which reads the version from the page's `<meta>` and marks the document started; the worker `geometry.worker.js` and the geometry in `geometry/` ([The geometry, in a worker](#the-geometry-in-a-worker)) |
| `wizard/src/seams/` | The seams: the only modules that may call `setTimeout`, `setInterval`, `Date.now` or `fetch` (the clock and the transport; from the skeleton, item 2 of [By phase](#by-phase)) |
| `wizard/vendor/` | Third-party code kept as files, each with its release, licence and SHA-256 in [wizard/vendor/README.md](vendor/README.md) |
| `wizard/tests/` | The tests without a browser window on Node's runner (`*.test.js`), with their fakes in `wizard/tests/fakes/` (from the skeleton) |
| `wizard/tests/python/` | The tools' tests, on pytest: the build, Node's version check, the trials' server and made parts, the vendored files' hashes and the real parts' hashes. Not `tests/tools/`: the repository's `.gitignore` ignores every folder named `tools/` |
| `wizard/tests_browser/` | The tests that drive Chromium, with the fake front server in Python (`fake_front_server.py`) |
| `wizard/scripts/check_node.py` | Node's version check |
| `wizard/trials/` | The two opening trials of phase 2, their pages, scripts, plates and results ([wizard/trials/README.md](trials/README.md)) |
| `wizard/build.py` | The build ([The wizard's built files](../contracts/wizard-front-server.md#the-wizards-built-files)) |
| `wizard/dist/` | The built files; not committed |

**Tests without a browser window** run on Node's own test runner (`node --test`), Node 24
or later, with no npm package, in a random order (`--test-randomize`; the runner prints the
seed, and `--test-random-seed=<seed>` repeats an order), each test bounded at 60 seconds. They
cover the geometry (faces, auto-orient, Arrange, the
placement check against the shared plates), the plate configuration the page makes, the
storage, retrying, progress streams, the slicing card's states and every row of this file's
tables that needs no drawing. The page's modules reach the world through a few seams, each
replaced in these tests by a fake written in the project: the clock (every timer and every
reading of the time goes through it, and a test moves it); the front server (the module that
makes every request takes a transport, which the fake front server replaces, answering in
the contract's shapes and checked against the contract's examples); the browser's storage
(the storage module sits on a small interface over IndexedDB, which a fake in memory
implements); the browser's locks (`navigator.locks`, faked with the same interface); and the
worker (run in the same thread by the tests, through the same messages). A page module that
calls `setTimeout`, `setInterval`, `Date.now` or `fetch` directly fails the suite:
`tests/seams.test.js` searches every `.js` and `.mjs` file under `wizard/src/` outside
`wizard/src/seams/` for those names, reached directly or through the global object
(`globalThis.fetch`, `self['fetch']`, `Date['now']`), skipping comments but not strings or
regular expression literals, and names each file and line. It does not see a name built from
pieces (`'set' + 'Timeout'`, `Date[n]`), and it does not search for the other ways to reach
the time or the network (`new Date()`, `performance.now`, `requestAnimationFrame`,
`XMLHttpRequest`, `EventSource`, `WebSocket`), which the skeleton (item 2 of
[By phase](#by-phase)) decides when it builds the seams. So the suite needs no network and never waits. `tests/page.test.js` holds
`index.html` to the contract's rules: one version placeholder, no inline script, no `style`
element or attribute, nothing loaded from another site. The tools' tests in
`wizard/tests/python/` run in the same target, on pytest in a random order (pytest-randomly
prints the seed in pytest's header, `Using --randomly-seed=<seed>`, and passing that
option repeats an order; the target runs pytest without `-q`, which would
hide the header, and a test checks the seed is printed), each bounded at 120 seconds.

**Tests in a browser** use Playwright for Python in the project's `uv` environment, driving
the Chromium build Playwright installs (`playwright install chromium`), headless, with a
small fake front server in Python that serves the built files and answers in the contract's
shapes, on a port the system chooses. They cover what needs drawing or the real browser: the
3D views coarsely, as [The layer preview](#the-layer-preview) says; the widths; focus and
keyboard; the real IndexedDB and locks across several tabs; a reload. On a machine without a
graphics card Chromium draws 3D in software. Like the other suite, they wait on events, never
on a duration. As built, the fake front server serves `GET /` with the version filled in and
the contract's exact content security policy, and `GET /assets/<file>`; the tests check the
page runs with no error under that policy, that an inline script would be reported, that the
page reads its version, and that it asks only for itself and its assets. Playwright's browsers
go where `PLAYWRIGHT_BROWSERS_PATH` says, unless that folder cannot be written (the agents'
machine has a read-only `/opt/ms-playwright` holding an older revision); then into
`~/.cache/ms-playwright`, shared by every checkout.

**Third-party code.** Only code under a licence that MIT code may include (MIT, BSD or
Apache 2.0), never Orca's or any other AGPL or GPL code, kept in `wizard/vendor/` and served
from `/assets/` with the rest: nothing is loaded from another site. It is three.js 0.170.0
(release 170), taken in place of the mockup's release 128 because it is published as ES
modules with a one-file core: the core and the example files the trials are likely to need
(orbit controls, buffer utilities, convex hull, wide lines), byte for byte at the package's
own paths, as [wizard/vendor/README.md](vendor/README.md) lists with each file's SHA-256,
which the fast suite checks. The example files import the core by the bare name `three`: a
trial's page maps it with an import map; the wizard's page, which may have no inline script,
gets the name rewritten by the build (from the skeleton). A drawing method of the first trial
that needs other code is held to the same rule.

**The build, as built.** `build.py` writes `wizard/dist/index.html` and puts every other file
of `wizard/src/` flat in `wizard/dist/assets/` as
`<name>.<first 12 hexadecimal characters of its SHA-256>.<extension>`, bytes unchanged, and
rewrites each `src` and `href` of `index.html` that names one of them, its value in double
quotes, single quotes or none, to `/assets/<that name>`, keeping its quotes; a link within the
page (`href="#..."`) is left as it is. It refuses, with a sentence that says why: no
`index.html`; no version placeholder, or more than one; a reference to another site or to a
file not in `wizard/src/`; two files that would get the same built name. Only `src` and
`href` are read: an address in another attribute (`srcset`, `poster`, `data`) is neither
rewritten nor refused, and the content security policy is what stops it loading. Not yet built (the skeleton, item 2 of
[By phase](#by-phase)): rewriting the names inside an asset (a module's or a worker's
imports, a style sheet's addresses) and building in `wizard/vendor/`.

**Make targets,** each run as `make -C wizard <target>`:

| Target | What it does |
|---|---|
| `install` | The `uv` environment and Playwright's Chromium; fails naming the version when Node is older than 24 ("Node 22.3.0 is older than 24: the wizard's tests need Node 24 or later.") |
| `test` | The tests without a browser window: the fast suite (Node's check, then `test-page`, the page's tests on Node, then `test-tools`, the tools' tests on pytest) |
| `test-browser` | The tests in Chromium, after `build` |
| `build` | `wizard/dist/` from `wizard/src/` (and, from the skeleton, `wizard/vendor/`) |
| `trials` | Both opening trials' measurements, as [How the trials and measurements are run](#how-the-trials-and-measurements-are-run) says: runs `trials-preview` and `trials-geometry`, the second even when the first fails, and fails when either does |
| `trials-preview` | The first trial: `wizard/trials/preview/run.py` |
| `trials-geometry` | The second trial: `wizard/trials/geometry/run.py` |
| `trials-parts` | Writes the trials' made parts again into `wizard/trials/parts/` |
| `trials-serve` | Serves `wizard/trials/` at `/`, with `wizard/vendor/` at `/vendor/` and `contracts/examples/parts/real/` at `/parts/real/`, on `127.0.0.1:8610`, for the owner's timing on the Mac; `HOST=0.0.0.0` (or `PORT=`) to change the address |

Each trial's entry point is its own file in its own folder, so the two trials are built at
the same time without touching one file; until its builder replaces it, each is a
placeholder that says so and fails. A trial's script starts the trials' server itself with
`trials/serve.py`'s `make_server("127.0.0.1", 0)`, on a port the system chooses.

## How it is tested

- **No test waits.** Every timer reads the fake clock, which the test moves: the 150 ms of a tooltip,
  the 4, 20 and 300 seconds of retrying, the 20 and 45 seconds of a progress stream, the 120 seconds
  before a self-reload, the two hours of a sliced file and the 12 hours of a stored plate and of a
  last-print note are each tested in an instant. A test waits on an event, never on a duration.
- **The front server is the fake front server.** Everything that depends on the order of events over
  the network is put in an exact order by it: an answer lost and the request repeated, a progress
  stream closed mid-slice or open and silent, a slice job replaced by the same plate's later one or
  ended because the slice service was asked to stop, a part the part store has forgotten, a newer
  version announced while a request is pending. It answers in the contract's shapes, checked against
  the contract's examples.
- **Several tabs are several pages on one storage,** with a fake of the browser's locks.
- **Every row is a test.** Each row of each table in this file that describes a state or a message
  has a test that reaches it on purpose and checks what the user sees. Every failure the page can meet
  is an error report from the fake front server, or the page's own, produced on purpose.
- **Another component's sentences are shown unchanged**
  ([Who writes the sentences of a failure](#who-writes-the-sentences-of-a-failure)).
- **The geometry is tested on real parts,** without a browser window, against written-down
  expectations; the placement check on the shared plates.
- **The 3D views are tested coarsely,** by Playwright in Chrome's engine on real sliced files, as
  [The layer preview](#the-layer-preview) says; whether they look right is a person's judgement of the
  test renders.
- **The page measures itself in the tests as in real use.**
- **The previous release's page runs against the new fake front server.**
- The suites use no real front server, no real network and no fixed ports, and pass in any order, any
  number of times.

What such tests cannot prove: that the views look right (a person and the test renders); that they
are fast enough (timing in Chrome on the two machines, then the reports from real use); sign-in,
storage and the mouse inside Onshape's panel (real Onshape, phase 4); what the printer reports (the
real printer, phase 5); that progress passes the hosts unheld (the hosted service, phase 3).

## How the trials and measurements are run

**The inputs, kept in the repository.** The wizard reads no other component's folder, so the
eight real parts of the Popcorn Penguins' robot are copied, byte for byte, from
`slice/tests/fixtures/frc-parts/` to `contracts/examples/parts/real/` (Clamp Plate
Inner, Elevator Block Bottom Inner, Elevator Block Carriage, Elevator Block Top, Elevator Top Inner,
Inner Spacer, Outer Clamp, Pulley v3; 2,908 to 39,054 triangles, each exported once), with
[a README](../contracts/examples/parts/real/README.md) listing each file's SHA-256, which the
wizard's fast suite checks. Parts that are not real are made by `wizard/trials/make_parts.py`
(`make -C wizard trials-parts`), deterministic, into `wizard/trials/parts/`, committed, and the
fast suite checks the committed files equal its output: `hub-150k.stl`, a closed hub (a
surface of revolution, bore and all) of exactly 150,000 triangles (7,500,084 bytes, the largest
part the plate configuration allows), the shape the slice service's
measurements used (a ring 40 mm across and 20 mm tall, a 12 mm bore, 3 mm fillets on its four
edges, in near-square facets: 300 around by 250 along the cross-section, its flat base on
z = 0), written in the wizard's own code; and `hex-spacer.stl`, the slice service's
reference spacer (a spacer for a 3/8 inch hex shaft, 1/8 inch thick, round outside and 5/8 inch
across, 216 triangles: 48 sides outside, each rim segment fanned to the nearer hexagon corner),
likewise written anew. Both are closed and wound outwards, and each coordinate is rounded to a
millionth of a millimetre before it is stored, so the bytes do not hang on the last bit of a
machine's sine and cosine. The round parts exported from Onshape at its coarse
and fine settings, which the second trial would be better for, can only come from the owner; until
they are in `contracts/examples/parts/real/`, the trial's round parts are `pulley-v3.stl` and
`inner-spacer.stl`, and its result says so.

**The machines.** The **machine without a graphics card** is the one the project's agents work on,
an aarch64 Linux machine on which Chromium draws 3D in software; every figure the builder records is
taken there, in the Chromium of `make -C wizard install`, and the result names the machine's
processors and memory. The **machine with a graphics card** is the owner's Mac, in Chrome; only the
owner can take figures there.

**The layer preview's speed without a graphics card** (the first trial of phase 2). Three real sliced
files, made by `wizard/trials/make_sliced_files.py` (*proposed*), which submits each plate to a slice
service started by hand on the same machine through its HTTP interface as built today (a plate
configuration with its files) and saves the sliced file:

| Plate | What it is | Sliced file | What making it needs |
|---|---|---|---|
| `four-each-b-supports` | The plate `four-each-b` of `slice/tests/frc_parts.py`, written out as a plate configuration in `wizard/trials/plates/`: 16 instances, 2 of each real part, supports on | 8.82 MB | The default memory ceiling |
| `blocks-12-supports` | Twelve Elevator Block Bottom Inners, 3 by 4, 12.5 mm apart, supports on | 14.1 MB | The slice service started with `PENGUIN_SLICE_MAX_PEAK_MB=3000`, which this plate needs (it peaks at 2,307 MB); at least 4 GB of free memory |
| `spacers-150` | 150 of `hex-spacer.stl`, 13 by 12 less 6, 22 mm apart, supports off | 2.72 MB | The default memory ceiling |

The sliced files go to `wizard/trials/sliced/`, which is not committed (25.6 MB); the script makes
them again. Write two or three candidate methods of drawing, each as a page of its own in
`wizard/trials/preview/` that loads one sliced file and draws it with the required look. On the
machine without a graphics card, in Chromium driven by Playwright (`make -C wizard trials`), turn the
view and drag the layer bar along a fixed path, and record the frames a second (typical and worst),
the longest main-thread hold, the time to the first layer and the page's memory, by the same
measuring the wizard's reports use; and make test renders at fixed angles, edge-on and zoomed in
included. The figures (one JSON file for each method and plate) and the renders (PNG) are committed
in `wizard/trials/preview/results/`, with `wizard/trials/preview/report.html`, a page that shows them
side by side.

Passing has two parts. **The builder's part,** which lets the phase go on: a method reaches 10 frames
a second typical, and never a hold of the main thread over 250 ms, on all three plates on the
machine without a graphics card, and passes the coarse checks of the look that
[The layer preview](#the-layer-preview)'s tests name (it draws, fills roughly the expected part of
the view, shows the four colours and changes with the layer bar); the builder builds the Preview step on the fastest
such method. **The owner's part,** which the builder does not wait for: the owner opens
`report.html` to look at the renders, and runs the method's pages in Chrome on the Mac
(`make -C wizard trials-serve` serves `wizard/trials/` on `127.0.0.1:8610`) for the 30 frames a second.
If no method reaches the builder's part, the item comes back to the owner with its figures
([The risks to try first in phase 2](README.md#the-risks-to-try-first-in-phase-2)).

**Laying on a face, auto-orient and Arrange on real exported parts** (the second trial). For each of
the eight real parts and each round part: record the hull faces and patches found and the
orientation auto-orient chooses, as figures in `wizard/trials/geometry/results/` and as one picture
of the part in its chosen orientation with its patches drawn, in `wizard/trials/geometry/pictures/`;
write them down as the expected answers of the geometry's tests. Time each step in the worker, in
Chromium, on the machine without a graphics card: the patches of `hub-150k.stl` within `PATCHES_MS`
(100 ms) of selecting it, its auto-orient within `AUTO_ORIENT_MS` (1 s), Arrange of 150 instances of
`hex-spacer.stl` and of a mix of the real parts within `ARRANGE_MS` (2 s), and each placement check of
a drag at 150 instances within 100 ms, one frame of the Layout view at its 10 frames a second.

Passing: the builder's part is the four times met on that machine and every real part given hull
patches on its flat faces; the builder then goes on with the rest of the phase on the rules as
written. The owner's part is to look at the pictures and accept each part's orientation and
patches, or name the ones a person would not choose. Tuning the angles from that needs no decision;
if no rule sorts real round sides well, the Layout step offering fewer patches comes back for a
decision.

As built, `make -C wizard trials-geometry` runs `wizard/trials/geometry/run.py`, which serves
`wizard/src/` beside the trials (at `/src/`) so that `wizard/trials/geometry/index.html` drives
the wizard's own worker in Playwright's Chromium, headless, and writes one JSON file for each part
and for each arranged plate, `summary.json` (the machine's processors and memory as its cgroup gives
them, the four times against their targets, each real part's flat faces without a hull patch, and
the main thread's longest gap between beats of a 10 ms heartbeat during the timed steps), one
picture of each part (as modelled and as laid, with its patches) and one of each arranged plate.
It exits 1, naming each, when a time is missed or a flat face of a real part has no hull patch. The
mix of real parts is 140 of Pulley v3 and one or two of each other real part. The round parts
exported from Onshape at its coarse and fine settings have not arrived, so the round parts are
`pulley-v3.stl` and `inner-spacer.stl`, and the summary says so. The builder's part passed on Fri
2026-11-27: the four times met with a wide margin and every flat face of a real part given a hull
patch, after three of the rules were tuned on the real parts ([Finding the faces a part can lie
on](#finding-the-faces-a-part-can-lie-on)); what was found is in
[wizard/trials/geometry/README.md](trials/geometry/README.md).

**Whether the browser's storage holds a full plate.** In Chrome, on a tab and from phase 4 in
Onshape's panel, store a full plate of 25 parts of 7.5 MB in each of several tabs and record when the
browser refuses; after that, the `storage_refused` and `storage_cleared` reports from real use count
how often.

**Whether progress reaches the page unheld when hosted** (phase 3). With one slice on the hosted
service, compare the moment each report is sent by the front server (its log) with the moment the
page receives it; a lag of more than a second on any report means the stream is held and the page asks
instead.

## By phase

What each phase builds, in an order a builder can follow. Each item names the guide's section and the
contract's request or shape it implements, and this file's section that specifies it.

### Phase 2, one machine

The page opened directly in a browser, with the development identity and no sign-in.

1. **The two trials,** before the rest, because a failure in either trial
   changes the design. Their project and inputs are built
   ([The project and its tools](#the-project-and-its-tools), and the inputs of
   [How the trials and measurements are run](#how-the-trials-and-measurements-are-run)), and so
   is the second trial, [the geometry on real parts](README.md#the-risks-to-try-first-in-phase-2),
   with the geometry it tried ([The geometry, in a worker](#the-geometry-in-a-worker)); the first
   is to be built in place of its placeholder entry point:
   [the layer preview's speed](README.md#the-risks-to-try-first-in-phase-2)
   ([How the trials and measurements are run](#how-the-trials-and-measurements-are-run)).
2. **The skeleton:** the build of `wizard/dist/` as
   [The wizard's built files](../contracts/wizard-front-server.md#the-wizards-built-files) fixes
   it (hashed asset names, the version placeholder, nothing the content security policy
   forbids); the page served by `GET /` and `GET /assets/<file>`, its version read from its
   `<meta>`; `css/panel.css` taken over; the fake clock and the fake front server; the module that
   makes every request with `X-PenguinSlicer-Page`, `X-PenguinSlicer-Group` and the wizard's mark
   ([Every request](#every-request-headers-answers-and-retrying);
   [Rules for every request](../contracts/wizard-front-server.md#rules-for-every-request)).
3. **Retrying and the panel line**
   ([When the server is slow](README.md#when-the-server-is-slow-or-cannot-be-reached);
   [Retrying](../contracts/wizard-front-server.md#retrying-and-why-every-request-is-safe-to-repeat)).
4. **The panel as a whole:** the widths, the header, the step tabs, the plate summary, Back and Next,
   the six ways of telling, the tooltips ([The panel as a whole](README.md#the-panel-as-a-whole)).
5. **Who the user is and the configuration:** `GET /api/me`, `GET /api/configuration` with the
   header naming `name`, the reload glyph, `GET /api/settings-table` when the page opens
   ([The current group](README.md#the-current-group);
   [the configuration](../contracts/configuration.md),
   [the table of settings](../contracts/settings-table.md)).
6. **The browser's storage:** a plate for each tab, the locks, the 12 hours, `owner` stored from the
   start, refused and cleared storage
   ([What the browser keeps](README.md#what-the-browser-keeps-and-why-it-is-the-record)).
7. **The worker,** reading a binary STL and drawing a part's picture
   ([Keeping the page answering](README.md#keeping-the-page-answering)).
8. **The Parts step:** the upload area and its switch, part sets, one part one row, the page's own
   limits, `POST /api/parts` and each refusal and warning, a part the page cannot draw, New plate
   ([The Parts step](README.md#the-parts-step); [Parts](../contracts/wizard-front-server.md#parts),
   [the part set](../contracts/part-set.md)).
9. **The Settings step and advanced mode,** drawn from the table of settings, with the quick
   changes' values of [The Settings step](#the-settings-step)
   ([The Settings step](README.md#the-settings-step); [the table of settings](../contracts/settings-table.md)).
10. **The Layout step:** the view and its gestures, the rotation handle, laying on a face, auto-orient,
    Arrange, the placement check and its messages, against the shared plates (the geometry
    behind the last four is built, in the worker: [The geometry, in a worker](#the-geometry-in-a-worker);
    the step that shows them is to be built)
    ([The Layout step](README.md#the-layout-step);
    [Coordinates](../contracts/plate-configuration.md#coordinates),
    [An instance in phase 2](../contracts/plate-configuration.md#an-instance-in-phase-2),
    [Shared plates for the placement checks](../contracts/plate-configuration.md#shared-plates-for-the-placement-checks)).
11. **Submitting and following:** the plate configuration with `plate_id` and `submission_id`,
    `POST /api/slices` and each answer, parts missing, the slicing card and its states, the stopping
    answer, no room to wait, the progress streams with their 20 and 45 seconds and the asking behind
    the same interface ([Slicing](README.md#slicing);
    [Slice jobs](../contracts/wizard-front-server.md#slice-jobs),
    [the plate configuration](../contracts/plate-configuration.md#to-be-built),
    [the progress report](../contracts/progress-report.md)).
12. **Every slice failure,** with Orca's sentence under Details
    ([When a slice fails](README.md#when-a-slice-fails); [the error report](../contracts/error-report.md)).
13. **The result and the layer preview,** by the method the first trial chose
    ([The result](README.md#the-result);
    [The sliced file](../contracts/wizard-front-server.md#the-sliced-file)).
14. **A sliced plate that expires**
    ([A sliced plate that expires](README.md#a-sliced-plate-that-expires);
    [The sliced file's details](../contracts/wizard-front-server.md#the-sliced-files-details)).
15. **The Send step with Download as its one button** ([The Send step](README.md#the-send-step)).
16. **Coming back:** every row of the returning page's table that phase 2 can meet
    ([Coming back to running work](README.md#coming-back-to-running-work);
    [Asking about a slice job](../contracts/wizard-front-server.md#asking-about-a-slice-job)).
17. **Reloading for a new version**
    ([The page reloading itself](README.md#the-page-reloading-itself-for-a-new-version);
    [The version on every answer](../contracts/wizard-front-server.md#the-version-on-every-answer)).
18. **The reports about itself,** failures and drawing summaries
    ([What the wizard reports about itself](README.md#what-the-wizard-reports-about-itself);
    [The page's reports about itself](../contracts/wizard-front-server.md#the-pages-reports-about-itself)).
19. **The previous release's page against the new front server,** in the tests from the second
    release on.

### Phase 3, hosted

Signing in with Onshape by the page's own trip, and a trip that fails; Sign out and the signed-out
page; the stored work cleared for a different user; the group details for a user in several groups,
changing the current group, and a group the user no longer belongs to; the front server's check of the
mark, which the page has sent since phase 2; the measurement of progress through the hosts
([Signing in](#signing-in-and-signing-out), [The current group](#the-current-group);
[Signing in and signing out](../contracts/wizard-front-server.md#signing-in-and-signing-out)).

### Phase 4, inside Onshape

The page in Onshape's panel: parts picked in Onshape as part sets, with their units; its storage kept
apart from a tab's; Connect with its small window and the sign-in that follows Onshape's; the group
that follows the document; the panel's headers
([Inside Onshape's panel](#inside-onshapes-panel-phase-4);
[Inside Onshape's panel](../contracts/wizard-front-server.md#inside-onshapes-panel)).

### Phase 5, the real printer

The printer-status icon and the printer details; pairing and unpairing; Send, the print card, the busy
card, Cancel sending, Stop following; the last-print note; coming back to the Send step
([The printer, from phase 5](#the-printer-from-phase-5), [The Send step](#the-send-step);
[The printer, from phase 5](../contracts/wizard-front-server.md#the-printer-from-phase-5)).

## Where this guide departs from the mockup's decisions

Whoever builds from [the mockup's decisions](../docs/mockups/print-wizard/DECISIONS.md) follows the
guide where the two differ, in these places. Every other decision cited in this file is followed as
the mockup has it, and the mockup's questions are answered as it has them: M1, faces on the hull; M2,
the mouse like Onshape; M3, parts arrive lying their best way; M6, two buttons and Arrange never
turns; M16, no layout tools beyond the mockup's; M17, leaving the Preview step does not stop the
slice; M29, the bounding-box rule, end patches included, the 30 degrees to tune; M7, M11, M21, M22,
M23, M25, M26 and the 11 px pointer line as the mockup has them. M18 is a departure, below.

| The mockup's decision | What the mockup says | What the guide says |
|---|---|---|
| [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms), "configuration" | The configuration holds the printer | The paired-printer record links the group to its printer and holds the name the printer reports; the configuration names the printer's Orca profile, from which the plate's size and height come ([The configuration](#the-configuration-and-the-table-of-settings)) |
| [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms), "group" | A collapsible set of settings in advanced mode | "Setting group"; "group" is the users who share a configuration and a printer ([Terms used below](#terms-used-below)) |
| [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms), "administrator"; [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step) | An administrator pairs the printer, once, from the computer beside it | Any signed-in user of the group types the pairing code, from any computer ([Pairing a printer](#pairing-a-printer)) |
| [decision 58](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) | Where a permission matters, the word is "administrator" | No sentence sends the user to an administrator; no user of a group has rights another lacks ([The words it uses](#the-words-it-uses)) |
| [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step), [decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon) | With no printer paired, a message and the "How to pair a printer" link | The pairing form in the printer details only, with that link; the Send step's message links to the printer details by "Pair a printer" and has no form ([Pairing a printer](#pairing-a-printer), [When Send is not offered](#when-send-is-not-offered)) |
| [decision 2](../docs/mockups/print-wizard/DECISIONS.md#whole-panel); fake 25 | The header names the configuration; its name links nowhere and the reload glyph reloads nothing | The header names the configuration in use, the group's or "PenguinSlicer default"; plain text for a user in one group, a button opening the group details for a user in several outside Onshape; the reload glyph reads it again ([The current group](#the-current-group)) |
| [decision 10](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) | Filaments named, with no colour | A colour for each filament from the configuration, beside its name in the Filament menu, never in the layer preview ([The Settings step](#the-settings-step)) |
| [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) | Advanced mode's changes last for this page load | The changes are in the browser's storage and outlast a refresh; only the open and closed sections live in memory ([Advanced mode](#advanced-mode)) |
| Fake 13 | Advanced mode shows a sample of 99 settings | Every parameter setting of Orca's, from the table of settings, with Orca's own labels, groups and explanations ([Advanced mode](#advanced-mode)) |
| [decision 17](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) | After 20 seconds of failed retries, a notification that the part was not added, to be clicked or uploaded again | Quiet retries; from 20 seconds the panel line with its countdown and Retry now; up to 300 seconds, then "The server could not be reached." with Try again; nothing dropped, the part keeps its row ([Retrying](#retrying)) |
| [decision 22](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) | Quantities clamp at 150 | One part's quantity clamps at 150; parts that together pass 150 get a red message and Next is off; at most 25 different parts ([The limits on a plate](#the-limits-on-a-plate)) |
| [decision 51](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) | Uploads read in inches unless the configuration says millimetres, with a line of text and no control; a 3MF states its own units | Binary STL only; a switch beside the upload area, "Read STL files in: inches / millimetres", starting at the configuration's value and kept in the browser's storage ([The Parts step](#the-parts-step)) |
| [decision 37](../docs/mockups/print-wizard/DECISIONS.md#send-step); fake 11 | A plate is numbered ("Plate 1, 16 instances, on Shop H2S"; "Downloaded the sliced file of Plate 1") | No plate is numbered and no count of plates is kept; the plate is named by what it holds ("16 instances, on Shop H2S"); a New plate button starts afresh ([The Parts step](#the-parts-step), [After Send](#after-send)) |
| [decision 30](../docs/mockups/print-wizard/DECISIONS.md#preview-step), [decision 31](../docs/mockups/print-wizard/DECISIONS.md#preview-step) | The slicing card has Cancel slice, disabled while the server cannot be reached; a cancelled slice has its message | No Cancel slice and no "cancelled by the user"; a slice ends without a result only when the same plate's later slice replaces it or the slice service is asked to stop ([The slicing card](#the-slicing-card)) |
| [decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step) | A timeout suggests a profile with thicker layers | Every failure's sentences are the slice service's, shown as they are (for a timeout: fewer instances or a new plate); Orca's sentence under Details on the two empty-layers failures, as the mockup has it, comes from the error report's `orca_sentence` ([When a slice fails](#when-a-slice-fails)) |
| [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step), how the view draws | The layer preview drawn by the mockup's method | What must be achieved, the appearance, four requirements and stated targets; the method is found while building ([The layer preview](#the-layer-preview)) |
| [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step), no combs and no show-through | At any viewing angle, with no exception for motion | A simpler look is allowed while the view is moving, the four colours kept; the rules hold for the view at rest ([The layer preview](#the-layer-preview)) |
| [decision 45](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), [decision 47](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work); [Requirements on printer delivery](../docs/mockups/print-wizard/DECISIONS.md#requirements-on-printer-delivery), item 3 | A refresh throws the page's state away and the server finds the user's work; with no slice, an empty Parts step | The browser's storage keeps the plate, with a plate for each tab; a page with parts and no slice opens on its stored step; work does not follow to another browser ([When a user comes back](#when-a-user-comes-back)) |
| [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), [decision 48](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work) | The Send step only for a running delivery job; a failed print a notification on the Parts step, the parts not kept | A plate with a delivery job, running or ended, opens on the Send step while its sliced file is kept; a failed print is the failure on the print card ([When a user comes back](#when-a-user-comes-back)) |
| [decision 48](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work); M18 | After two hours away a finished unsent slice is gone, and the page opens on an empty Parts step | A sliced file is kept two hours after its slice or its last print ended, whichever is later; a returning page whose sliced file has expired keeps the plate and shows the expired message with Slice again ([When a user comes back](#when-a-user-comes-back)) |
| Fake 16 | Cancel sending always works at once | Cancel sending until the relay allows the start; a cancel just after is answered with printer delivery's sentence and the card goes on following ([After Send](#after-send)) |
| Fake 9 | A "plate too large" error against a cap on a plate's volume | No such error; a plate too heavy ends as out of memory or too slow ([When a slice fails](#when-a-slice-fails)) |

## Screens designed in the guide

These screens and states have never been drawn; they exist only in the guide's words, in the
mockup's look and following its patterns
([Designed here and not in the mockup](README.md#designed-here-and-not-in-the-mockup)). Each is
specified here where the last column says, and each gets the tests of its section.

| Screen or state | The guide | This file |
|---|---|---|
| A sign-in that could not be made, the page after Sign out, and Connect inside Onshape's panel | [Signing in](README.md#signing-in) | [Signing in and signing out](#signing-in-and-signing-out) |
| The header naming the default configuration, and a filament or profile gone when the configuration is read again | [The current group](README.md#the-current-group) | [The current group](#the-current-group) |
| The group details, changing the current group, and a group the user no longer belongs to | [A user in several groups](README.md#a-user-in-several-groups-outside-onshape) | [A user in several groups, outside Onshape](#a-user-in-several-groups-outside-onshape) |
| The switch that says how STL files are read, and New plate | [The Parts step](README.md#the-parts-step) | [The Parts step](#the-parts-step) |
| The slicing card without a Cancel button | [Slicing](README.md#slicing) | [The slicing card](#the-slicing-card) |
| A sliced plate that expires, with the page open or found expired on return | [A sliced plate that expires](README.md#a-sliced-plate-that-expires) | [A sliced plate that expires](#a-sliced-plate-that-expires), [When a user comes back](#when-a-user-comes-back) |
| A slice waiting behind others, waiting while the slicer restarts, and no room to wait | [Slicing](README.md#slicing) | [The slicing card](#the-slicing-card), [While the slice service is stopping](#while-the-slice-service-is-stopping), [No room to wait](#no-room-to-wait) |
| The pairing form in the printer details, the Send step's link to it, a wrong code, too many wrong codes, and unpairing | [Pairing a printer](README.md#pairing-a-printer) | [Pairing a printer](#pairing-a-printer) |
| A print gone quiet, one gone quiet at a printer that is Offline, and Stop following for the sender | [A print that has gone quiet](README.md#a-print-that-has-gone-quiet) | [A print that has gone quiet](#a-print-that-has-gone-quiet) |
| The page reloading itself for a new version | [The page reloading itself](README.md#the-page-reloading-itself-for-a-new-version) | [Reloading for a new version](#reloading-for-a-new-version) |
| What a restart shows: the slicing card starting again, and a printer not heard from yet | [Slicing](README.md#slicing), [The printer-status icon](README.md#the-printer-status-icon) | [The slicing card](#the-slicing-card), [The printer-status icon](#the-printer-status-icon) |
| A printer busy with a print nobody sent from PenguinSlicer | [When Send is not offered](README.md#when-send-is-not-offered) | [When Send is not offered](#when-send-is-not-offered) |
| The limits on parts: 7.5 MB, 25 different parts, 150 instances | [The limits on a plate](README.md#the-limits-on-a-plate) | [The limits on a plate](#the-limits-on-a-plate) |
| Running out of memory | [When a slice fails](README.md#when-a-slice-fails) | [When a slice fails](#when-a-slice-fails) |
| The retry message with its countdown, also for a lost progress stream | [When the server is slow](README.md#when-the-server-is-slow-or-cannot-be-reached) | [Retrying](#retrying), [Progress streams](#progress-streams) |
| The Send step before there is a printer | [The Send step](README.md#the-send-step) | [The Send step](#the-send-step) |
| A confirmation | [How the panel tells the user something](README.md#how-the-panel-tells-the-user-something) | [How the panel tells the user something](#how-the-panel-tells-the-user-something) |
| A part the slice service accepts and the page cannot draw | [A part that cannot be used](README.md#a-part-that-cannot-be-used) | [A part that cannot be used](#a-part-that-cannot-be-used) |
| A part the browser refuses to store | [What the browser keeps](README.md#what-the-browser-keeps-and-why-it-is-the-record) | [What the browser keeps](#what-the-browser-keeps) |
| Still open: the icon and the printer details after a print is no longer followed | [After a print is no longer followed](README.md#after-a-print-is-no-longer-followed) | [A print that has gone quiet](#a-print-that-has-gone-quiet) |

## Open items

Every undecided or unmeasured item that bears on building the wizard, each also named where it bears
above. Build what each line says is safe; do not build past it.

- **The layer preview's speed without a graphics card**, the first trial of phase 2
  ([The risks to try first in phase 2](README.md#the-risks-to-try-first-in-phase-2)). Safe: everything
  but the drawing method.
- **Laying on a face, auto-orient and Arrange on real exported parts**, the second trial
  ([The risks to try first in phase 2](README.md#the-risks-to-try-first-in-phase-2)). The builder's
  part passed; open is the owner's look at each part's pictures and the round parts exported from
  Onshape, which only the owner can supply. Safe: the rules as built, with their angles as constants.
- **A quick change whose value is not on its menu**
  ([its item](README.md#a-quick-change-whose-value-is-not-on-its-menu)). Safe: its recommendation,
  the value as one more entry at the top of the menu.
- **After a print is no longer followed**
  ([its item](README.md#after-a-print-is-no-longer-followed)). Safe: never show it as Failed.
- **Saying that a part will need supports**
  ([its item](README.md#saying-that-a-part-will-need-supports)). Build nothing.
- **Who writes the one-line description of a plate**
  ([its item](README.md#who-writes-the-one-line-description-of-a-plate)). Safe: send `description`; the
  front server may ignore it.
- **What only real Onshape can settle**, in phase 4
  ([its item](README.md#what-only-real-onshape-can-settle),
  [To be confirmed inside Onshape](README.md#to-be-confirmed-inside-onshape-in-phase-4)). Safe: Connect,
  and the panel's headers sent only when known.
- **Whether the browser's storage reliably holds a full plate**
  ([its item](README.md#whether-the-browsers-storage-reliably-holds-a-full-plate)). Safe: the amber line
  and the reports.
- **Whether progress reaches the page unheld when hosted**, phase 3
  ([its item](README.md#whether-progress-reaches-the-page-unheld-when-hosted)). Safe: streams and asking
  behind one interface.
- **A configuration that names a profile the catalog has lost**
  ([its item](README.md#a-configuration-that-names-a-profile-the-catalog-has-lost)). Nothing of the
  wizard's: such a slice fails with the slice service's sentence, Back to Settings.
- **The limit on wrong pairing codes**, phase 5
  ([its item](README.md#the-limit-on-wrong-pairing-codes)). Show printer delivery's sentence.
- **A user's fifth progress stream**
  ([Open items of the other guides](README.md#open-items-of-the-other-guides-that-would-change-the-panel)).
  Safe: ask every `POLL_S` and show nothing of the refusal.
- **A send repeated while its delivery job is live**, **unpairing while a print is followed**,
  **pairing again**, **an old daemon**, **the printer's required mode**, phase 5
  ([Open items of the other guides](README.md#open-items-of-the-other-guides-that-would-change-the-panel)).
  Safe: the recoveries in [After Send](#after-send) and [Pairing a printer](#pairing-a-printer), and
  any refusal's sentence shown as it is.
- **Left open in the contract and owned by the front server's guide**: two requests renewing Onshape's
  tokens at once (phase 4), and Railway's limit on one request, which bounds one part's upload of up to
  7.5 MB and one sliced file of up to 50 MB (phase 3)
  ([Left open by the guides](../contracts/wizard-front-server.md#left-open-by-the-guides)). Nothing for
  the wizard to build differently.
