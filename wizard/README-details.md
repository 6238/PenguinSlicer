# The wizard: the builder's details

This is the builder's document for the wizard. The guide beside it,
[README.md](README.md), is what the owner reads and decides from; where the two differ,
the guide is right and this file is to be corrected. Nothing of the wizard is built, so
everything here is the design to build: every screen, state and message of the guide, in
the builder's terms, with the code-level names the guide leaves out, the figures, the
tests each one needs, and the record of where each rule came from.

The **wizard** is the code in the browser: the step-by-step user interface. It talks only
to the **front server**, a separate component in `front/`
([its guide](../front/README.md)), which serves the wizard's pages and stands between the
browser and everything else. What passes between the two is to be fixed in
[the contract between the wizard and the front server](../contracts/wizard-front-server.md),
which says what it must provide; its routes are not written yet. [D362] The phases are
those of [the plan](../docs/plans/penguin-slicer-plan.md): phase 2, one machine; phase 3,
hosted on Railway; phase 4, inside Onshape; phase 5, the real printer.

**How the sources are cited.**

- "[decision N](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)" links to the
  section of the mockup's decisions (version 8, approved Thu 2026-11-26) that holds
  numbered decision N; "M18" is a question of
  [its "Please react to these"](../docs/mockups/print-wizard/DECISIONS.md#please-react-to-these),
  and "fake N" an item of
  [its "What is fake and could mislead"](../docs/mockups/print-wizard/DECISIONS.md#what-is-fake-and-could-mislead).
  Where this file and the guide follow the mockup, the decision is cited; where they
  depart from it, the departure is listed in
  [Where this guide departs from the mockup's decisions](#where-this-guide-departs-from-the-mockups-decisions).
- The ids in brackets ("[D336]") name the decisions in
  [the map of the hosted architecture's decisions](../docs/orchestration/hosted-architecture/decision-map.md),
  whose content [the architecture](../docs/architecture.md) now holds.
- "The decisions of Fri 2026-11-27, item N" is an item of
  [that record](../docs/orchestration/guides/decisions-2026-11-27.md).
- A screen with no decision number is one the guide designed and the mockup never drew
  ([Screens the design needs that the mockup does not show](#screens-the-design-needs-that-the-mockup-does-not-show)).
- "Open:" starts a line that names an item the guide leaves undecided or unmeasured, with a
  link to it. Do not build past it: build what the line says is safe and leave the rest.
- Names and figures marked *proposed* are suggestions that no approved source fixes; the
  builder settles them while building. Every sentence in quotation marks is a sentence the
  user reads, copied from the guide.

## Contents

- [Terms used below](#terms-used-below)
- [Constants](#constants)
- [The panel as a whole](#the-panel-as-a-whole)
- [Who writes the sentences of a failure](#who-writes-the-sentences-of-a-failure)
- [Retrying every request](#retrying-every-request)
- [Signing in, and "sign in again"](#signing-in-and-sign-in-again)
- [The current group](#the-current-group)
- [The configuration](#the-configuration)
- [The Parts step](#the-parts-step)
- [Uploading each part when it is added](#uploading-each-part-when-it-is-added)
- [The Settings step](#the-settings-step)
- [The Layout step](#the-layout-step)
- [The geometry: faces, auto-orient, Arrange, the placement check](#the-geometry-faces-auto-orient-arrange-the-placement-check)
- [The Preview step](#the-preview-step)
- [Submitting a plate configuration](#submitting-a-plate-configuration)
- [One unfinished slice job at a time](#one-unfinished-slice-job-at-a-time)
- [Following progress, and reconnecting](#following-progress-and-reconnecting)
- [Errors the wizard explains](#errors-the-wizard-explains)
- [The layer preview](#the-layer-preview)
- [The sliced file](#the-sliced-file)
- [The Send step](#the-send-step)
- [Printers, from phase 5](#printers-from-phase-5)
- [What a returning page does](#what-a-returning-page-does)
- [Reloading on a newer version of the front server](#reloading-on-a-newer-version-of-the-front-server)
- [What the page keeps in the browser's storage](#what-the-page-keeps-in-the-browsers-storage)
- [Storage inside Onshape's panel, and storage in a tab](#storage-inside-onshapes-panel-and-storage-in-a-tab)
- [Browsers supported](#browsers-supported)
- [Accessibility](#accessibility)
- [Security](#security)
- [Failures only the browser sees](#failures-only-the-browser-sees)
- [What the other components must provide](#what-the-other-components-must-provide)
- [Performance targets](#performance-targets)
- [How it is tested](#how-it-is-tested)
- [By phase](#by-phase)
- [Where this guide departs from the mockup's decisions](#where-this-guide-departs-from-the-mockups-decisions)
- [Screens the design needs that the mockup does not show](#screens-the-design-needs-that-the-mockup-does-not-show)
- [Open items](#open-items)

## Terms used below

The plan's terms ([the plan](../docs/plans/penguin-slicer-plan.md#terms)), the
architecture's ([the architecture](../docs/architecture.md#terms)) and the guide's
([its terms](README.md#the-terms-this-guide-uses)) hold here. The ones this file leans on:

- The **page** is the wizard as loaded in one browser tab, or in Onshape's panel. The
  **panel** is the area the wizard draws in, whether Onshape's right panel or a tab.
- The **browser's storage** is the storage a browser gives a page that outlasts a refresh
  and a closed tab, kept for each browser and for each address the page is opened at.
- A **group** is the users who share one configuration and one printer: one Onshape
  company or classroom, or a user alone who belongs to none. The **current group** is the
  one the user is working in now. Advanced mode's collapsible sets of settings, which the
  mockup calls "groups", are **setting groups** here, so that "group" has one meaning.
- The **part store** is the slice service's folder of uploaded parts, each kept for two
  hours after it was last used. It is a cache.
- The **user key** is the signed-in user's Onshape id, which the front server takes from
  the sign-in cookie. The browser never names one.
- A **slice job** is one plate configuration being sliced; a **delivery job** is one
  sliced file on its way to one printer. The panel never says "job": it says "a slice",
  "a print", "a sliced plate" ([decision 37](../docs/mockups/print-wizard/DECISIONS.md#send-step)).
- A **progress stream** is the connection, of server-sent events, on which a page follows
  a slice job or a delivery job.
- The **state bucket** is the object store where the front server keeps each group's
  configuration and paired-printer record, the sliced files and the records of delivery
  jobs. The **paired-printer record** is the one document per group that names the
  group's daemon and the printer's display name.
- An **error report** and a **progress report** are the one shapes in which every
  component reports a failure and how far a long job has got
  ([error report](../contracts/error-report.md),
  [progress report](../contracts/progress-report.md)).
- The ways the panel says something are the guide's six: **notification**, **message**,
  **card**, **joined box**, **line** and **confirmation**
  ([How the panel tells the user something](#how-the-panel-tells-the-user-something)).
  The **panel line** is the one line under the step tabs.
- The **fake clock** is the clock every timer of the page reads, which a test moves; the
  **fake front server** is the stand-in a test drives, which answers, holds or drops each
  request and each event in the order the test sets. No test of the wizard uses the wall
  clock or a real network.

## Constants

Every figure the page's code uses, in one place. A constant marked *proposed* has a
figure no source fixes. Each is read through the fake clock where it is a time.

| Name (*proposed* names) | Figure | What it bounds | From |
|---|---|---|---|
| `PANEL_MIN_PX` | 320 | The narrowest panel, with no sideways scroll | The plan |
| `WIDTH_TABS_PX`, `WIDTH_FIGURES_PX`, `WIDTH_COLUMNS_PX` | 480, 520, 680 | The three widths at which the layout changes, each including itself | [decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| `TOOLTIP_DELAY_MS` | 150 | Rest before a tooltip shows | [decision 63](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| `TOOLTIP_EDGE_PX` | 6 | Least gap between a tooltip and the panel's edge | [decision 63](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| `DETAILS_OPEN_MS`, `DETAILS_CLOSE_MS` | 150, 300 | Printer details opening on rest, closing after the pointer leaves | [decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon) |
| `PANEL_LINE_PASSING_S` | *proposed* 4 | How long the panel line's passing use stays without a move ("a few seconds") | [decision 3](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| `ROW_SLOW_S` | 4 | A part's row says "Taking longer than usual; still trying…" | [decision 17](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| `RETRY_QUIET_S` | 20 | Failed retries before the panel line shows | The architecture; decisions of Fri 2026-11-27, item 14 |
| `RETRY_TOTAL_S` | 300 | Retrying in all, before "could not be reached" | The same |
| `RETRY_FIRST_WAIT_S`, `RETRY_MAX_WAIT_S` | *proposed* 1, 30 | Waits doubling from the first to the cap | The guide, proposed |
| `ATTEMPT_TIMEOUT_S`, `UPLOAD_ATTEMPT_TIMEOUT_S` | *proposed* 15, 60 | An attempt with no answer in this time counts as failed | This file, proposed |
| `STREAM_REOPEN_FAIL_S` | *proposed* 20 | A progress stream failing to reopen this long is treated as a failed request | Open: [A progress stream that cannot be reopened](README.md#a-progress-stream-that-cannot-be-reopened) |
| `STREAM_SILENT_S` | *proposed* 45 | An open progress stream carrying nothing this long is treated as failed | The same item's recommendation |
| `RELOAD_IDLE_S` | *proposed* 10 | Untouched time before a self-reload | The guide, proposed |
| `SLICED_FILE_KEEP_S` | 7,200 | Two hours: the page's rule for telling the two "unknown" rows apart | [D99, D106]; the front server's figure |
| `LAST_PRINT_NOTE_H` | 12 | The last-print note and "Last print finished…" go | [decision 60](../docs/mockups/print-wizard/DECISIONS.md#the-users-last-print-version-7) |
| `STALE_S`, `OFFLINE_S` | 40, 120 | A print gone quiet; a printer Offline | Printer delivery's figures [D163, D177] |
| `MAX_PART_BYTES`, `MAX_PART_TRIANGLES` | 7,500,084, 150,000 | One part | [The plate configuration](../contracts/plate-configuration.md#limits) |
| `MAX_PARTS`, `MAX_INSTANCES` | 25, 150 | Different parts, and instances, on one plate | The same; [decision 22](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| `MARGIN_MM`, `SPACING_MM`, `SPACING_SUPPORTS_MM` | 3, 5, 12 | The placement rules | The same; [decision 57](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6) |
| `POINTER_LINE_PX` | 11 | The pointer line's text, the one text under 14 px | [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms); the decisions of Fri 2026-11-27, item 16 |

## The panel as a whole

### Width, look and the three widths

- The panel is fluid, measured on the panel by container queries and not on the window,
  so dragging Onshape's panel wider changes the layout exactly as widening a window
  would ([decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)). It works
  at 320 px with no sideways scroll and nothing cut off.
- The look is PenguinCAM's light theme
  ([decision 1](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)): background
  `#f6f8fa`, cards `#ffffff`, controls `#eef1f4`, lines `#d0d7de`, text `#1f2328` and
  `#5a6570`, accent `#2f81f7`; body text 14 px, line height 1.45, PenguinCAM's font stack
  (which starts with the system's font, so the panel differs slightly by system); step
  tabs and pills 12 px; step title 18 px; buttons 8 by 14 px, radius 6 px; body padding
  14 px. Amber text is `#9a6700` (the borders keep `#d29922`), and a step tab's hover is
  light. The project documents' dark house style does not apply to the wizard.

| From | What changes | Mockup |
|---|---|---|
| 480 px | The step circles become named tabs. Settings step: Filament and Profile side by side, the quick changes two to a row. Advanced mode: the rail of section names in place of the accordion | [decision 3](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 12](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| 520 px | The Send step's print figures (percent, layer, time left) in one row. The Layout and Preview views 4:3 instead of square | [decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 25](../docs/mockups/print-wizard/DECISIONS.md#layout-step) |
| 680 px | The Parts step's list in two columns; the Send step in two columns | [decision 6](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |

Tests: each width at its own figure and one pixel under it (319 is not supported; 320,
479, 480, 519, 520, 679, 680), every step rendered and checked for no sideways scroll; a
panel resized across 480 px keeps advanced mode's open and closed sections.

### The header

The same on every step ([decision 2](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)):
line one, "PenguinSlicer" and, at its right from phase 5, the printer-status icon; line
two, "Config: 6238 (Popcorn Penguins)" (the current group's name, a button that opens the
group details) and the reload glyph; then the step tabs.

**The step tabs** ([decision 3](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)).
From 480 px: number, name, and a check mark after a finished step's name; no tooltip.
Below 480 px: five numbered circles joined by a line, a check in each finished one, the
current one filled in the accent blue with its name beside it. Every circle is clickable;
every circle but the current one has its step's name as its tooltip ("3. Layout"),
shown at once on keyboard focus; a screen reader hears "Step 3: Layout" once. A click
goes to the step when every step before it allows it.

**The panel line**, one line under the tabs, has two uses.

| Use | Shows | Goes | Mockup |
|---|---|---|---|
| Passing | The step that holds a click on a tab and why: "Layout first: 23 instances are closer than 12 mm with supports on." | At the user's next move, or after `PANEL_LINE_PASSING_S` | [decision 3](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) |
| Lasting | The retry messages ([Retrying every request](#retrying-every-request)), with their link or button | When a request is answered | None: designed in the guide |

When both apply, the lasting use is shown and the passing one is not (*proposed* in the
guide, since no source has the two meet).

**The plate summary** ([decision 4](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)).
None on the Parts step. From the Settings step on, two lines, updated at once: "1 part ·
1 instance"; then "PETG · Structural" and, while there are changes, the pill "+2 changes".
A filament or profile name too long is cut with an ellipsis, with its full name as
tooltip; the pill is never cut; the second line is as tall as the pill without it. No
plate area, print time or grams. The pill is a button that opens the **change details**,
a joined box: one plain line a change, "Quality › Resolution: 0.014 mm (profile 0.012
mm)", a quick change named in its own words, "Others › Brim: Off (profile Auto)"; closed
by a click elsewhere, Escape or the pill again. Opening the printer details closes it
([decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon)).

**Back and Next** at the bottom of every step: Next off until the step's rules pass, the
step saying why; a part still arriving never holds Next; Back off on the Parts step
([decision 5](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)).

### How the panel tells the user something

Each kind of news always uses the same way. The page's code has one component for each
(*proposed*), and every screen below names which it uses.

| Way | What it is | Used for | Mockup |
|---|---|---|---|
| Notification | A card at the top of a step, under the plate summary, closed with × | Something that happened and is on no row. It belongs to its step and goes when the user leaves the step or when it stops being true | [decision 7](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [the Terms](../docs/mockups/print-wizard/DECISIONS.md#terms) |
| Message | A block in a step's body: one sentence of what happened, one of what to do, its buttons. Red when it holds Next, amber for a caution, grey when it only informs, green when something was done | Problems on the plate, slice failures, a printer that cannot take a send, a sign-in that has ended | [decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Card | A white bordered box that holds a state for as long as it lasts | The slicing card, the print card, the busy card | [decision 30](../docs/mockups/print-wizard/DECISIONS.md#preview-step), [decision 41](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Joined box | A small box joined to the header element or icon it belongs to | The printer details, the change details, the group details, the colour key | [decision 4](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon) |
| Line | One short sentence in a fixed place | A consequence the user cannot see; the panel line | [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |
| Confirmation | *Proposed*: a small box joined to the pressed control, the question in one or two sentences, a button that goes ahead and one that keeps things; Escape or a click elsewhere keeps things | Changing the current group with something to lose, Reset all, Stop following, Unpair | None: designed in the guide |

"Details", with a capital, is only the folded part of a message, opened by the word
"Details" ([decision 58](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6)).
Exactly three messages carry it: the two empty-layers slice failures and a failed print
([decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step)).

**Tooltips** ([decision 63](../docs/mockups/print-wizard/DECISIONS.md#whole-panel)): the
panel's own white box (1 px `#d0d7de` border, radius 8 px, the printer details' shadow),
14 px, after `TOOLTIP_DELAY_MS` of rest, at once on keyboard focus of an icon or step
circle only; gone on leave, press, Escape or loss of focus; under its element, or above
where the panel ends, centred, at least `TOOLTIP_EDGE_PX` inside the panel. A tooltip says
only what is not on screen: an element whose text shows has none unless the text is cut
short. Options inside an open menu keep the browser's tooltip. Touch shows none, so
nothing a user needs is in a tooltip alone. Each element carries its tooltip text as its
accessible description, except the step circles.

### The words it uses

- **No role words:** no sentence says "student", "mentor", "team" or "administrator"
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

### Units

A part's units (inches or millimetres) are a label that travels with it: the Part
Studio's or Assembly's, or for an uploaded file the configuration's units for uploads. The
wizard never guesses units from a part's size
([decision 50](../docs/mockups/print-wizard/DECISIONS.md#units-version-6),
[decision 51](../docs/mockups/print-wizard/DECISIONS.md#units-version-6)).

| What | Shown in | Mockup |
|---|---|---|
| A part's own size, the selected instance's footprint and height, a patch's pointer line | The part's units: inches to three decimals ("2.000 × 2.000 × 0.188 in"); millimetres to 0.1 mm | [decision 52](../docs/mockups/print-wizard/DECISIONS.md#units-version-6), [decision 53](../docs/mockups/print-wizard/DECISIONS.md#units-version-6), [decision 54](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) |
| Printer and plate figures: plate size, height limit, spacing, distances between instances, a height above the plate, the layer readout | Millimetres; heights and spacing to 1 mm, distances to 0.1 mm | [decision 55](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) |
| A part's figure set against a printer's | Both in millimetres, the part's inches in brackets: "stands 352.7 mm (13.885 in) tall; the printer prints up to 340 mm" | [decision 54](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) |
| Slicing settings | Millimetres | [decision 56](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) |

A size is rounded once, from the exact millimetres, in the unit shown, by one function
(*proposed*) used on every step, so a part has one size everywhere; a size wraps and is
never cut short.

Tests: the 6.35 mm Gusset Plate reads 0.250 in on every step; a part in millimetres shows
millimetres; a too-tall instance of an inch part shows both units; the layer readout is in
millimetres on an inch plate.

## Who writes the sentences of a failure

**The component that failed writes the sentences.** Every failure arrives as an error
report; the wizard shows its `message` and `remedy` as they are, never rewords them, never
replaces them with its own made from the `code`, and never shows `detail`. What the wizard
adds is its own: where the report appears, its colour, a button for the report's `action`,
and its own buttons for moving about (Back to Layout, Back to Parts, Back to Settings).
A sentence written on a server says "your CAD program", never "Onshape"; only the Onshape
integration's sentences name Onshape.

| The failure is | Sentences by | The wizard |
|---|---|---|
| The slice service's (`slice.*`): a part refused or warned about, a plate refused, a slice that fails, runs too long or runs out of memory, no room to wait | The slice service | Shows them as they are |
| Printer delivery's (`delivery.*`), from phase 5: a send refused, a print that failed or waits for a person, a wrong pairing code | Printer delivery | Shows them as they are |
| The front server's own (*proposed* `front.<what>`): not signed in, a group the user is not in, a configuration that cannot be read, a sliced file that has expired | The front server | Shows them as they are |
| The Onshape integration's, from phase 4: a part Onshape cannot export | The Onshape integration | Shows them as they are |
| In the browser: no answer from the front server, the page's own checks before sending (a file over the size limit, a twenty-sixth part, more than 150 instances), every placement problem on the Layout step, a file the page cannot read, a lost 3D view, storage that fails | The wizard | Writes them |

States that are not failures (a slice waiting, a busy printer, a printer not heard from,
a print gone quiet, no printer paired, a sliced plate that expired with the page open) are
the wizard's to put into words, from the figures it is sent. Until the slice service's and
printer delivery's sentences drop "the print server" and old role words (known work in
those components), the wizard shows what they write.

Open: whether a user may read Orca's own sentence under Details on the two empty-layers
failures ([Orca's own sentence under Details](README.md#orcas-own-sentence-under-details)).
Under either answer the wizard never reads `detail`; if the quotation is wanted, the
slice service sends it among the fields for the user, and the wizard shows it.

Tests: for each kind of error report, the fake front server answers with sentences the
test made up, and the test checks that exactly those sentences appear, as text and not
markup, with the button the report's `action` calls for and the wizard's own buttons for
that code; a report with a `detail` never shows it; an unknown `slice.*` code is shown as
the last row of [Errors the wizard explains](#errors-the-wizard-explains).

## Retrying every request

**The page retries every request it makes,** so a request that falls in the gap of a
deploy is repeated, and a user sees nothing of a gap shorter than 20 seconds. [D338] The
project is deployed continuously, and a deploy at any moment interrupts no user
([the architecture](../docs/architecture.md#restarts-and-deploys)).

**The rule** (the decisions of Fri 2026-11-27, item 14; the guide's
[When the server is slow or cannot be reached](README.md#when-the-server-is-slow-or-cannot-be-reached)):

1. A request that fails or gets no answer is retried, quietly at first.
2. After `RETRY_QUIET_S` (20 seconds) of failed retries, counted from the first failure,
   the page shows that the server is being slow and the browser is retrying, with a
   countdown to the next attempt, as Gmail's "retrying in 28s" does. The waits between
   attempts grow, so there is something to count down and a struggling front server is
   not hammered.
3. It keeps retrying for up to `RETRY_TOTAL_S` (300 seconds) in all, counted from the
   first failure.
4. Then it stops, says the server could not be reached, and offers to try again.
5. Nothing of the user's work is dropped: the parts, the layout and the chosen settings
   stay in the browser's storage, a part whose upload stopped keeps its row, and
   everything that needs no server (laying out the plate, changing settings) goes on
   working.

The exact waits and words are the builder's; the guide proposes these, and this file
takes them:

| Time since the request first failed | What the user sees | From |
|---|---|---|
| 0 to 20 s | Nothing, except on the thing waiting: a part's row says "Taking longer than usual; still trying…" after `ROW_SLOW_S` (4 seconds) | [decision 17](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) for the row |
| 20 to 300 s | The panel line in amber: "The server is being slow. Your browser is retrying in 28 s.", the figure counting down each second to the next attempt, with a link, **Retry now** | Item 14; the words and the link are the guide's (its choice 4) |
| After 300 s | The panel line in red: "The server could not be reached.", with one button, **Try again**, which makes an attempt at once and starts the 300 seconds afresh | Item 14; the words are the guide's |

- **Waits** (*proposed*): 1, 2, 4, 8, 16, then 30 seconds between attempts, capped at
  `RETRY_MAX_WAIT_S`. So attempts fall at 1, 3, 7, 15, 31, 61, 91 … 271 seconds after the
  first failure, the message appears at 20 seconds counting down to the attempt at 31,
  and no attempt is made after 300. A small random spread on each wait (*proposed*: up to
  a tenth) keeps many pages from retrying in step after a restart.
- **Retry now** (*proposed*) makes the next attempt at once and does not restart the
  300 seconds; the countdown then resumes from the next wait.
- **An attempt that gets no answer** is one with no answer within `ATTEMPT_TIMEOUT_S`, or
  `UPLOAD_ATTEMPT_TIMEOUT_S` for uploading a part (*proposed* figures).
- **The message is the wizard's own**, since no component answered to write one; "the
  server" is the front server, the only server the browser knows. It is on the panel line
  and not a notification because it concerns the whole panel and must stay as the user
  moves between steps. It goes the moment any request of the page's is answered.
- **What is retried** (*proposed*): a request that gets no answer, whose connection
  fails, or whose answer is an error report marked `retryable` that says a service did
  not answer (the front server's "slice service did not answer" and "state bucket did
  not answer", *proposed* `front.slice_service_unavailable` and
  `front.state_bucket_unavailable`; see
  [the front server's error reports](../front/README-details.md#error-reports)).
- **`slice.busy` is not retried by itself**, though it is `retryable`: it is shown, as
  [No room to wait](#no-room-to-wait) says. So a slice service that is stopping for a
  deploy must not refuse a new slice job with `slice.busy`; it refuses with an answer the
  page retries, one that says the service did not answer
  ([the contract](../contracts/wizard-front-server.md#submitting-a-plate-configuration)).
- **Every request is safe to repeat**; the contract requires it
  ([the contract](../contracts/wizard-front-server.md#every-request-and-every-answer)).
- **Which requests** (*proposed*): every request a user waits on, adding a part,
  submitting a plate, fetching a sliced file or its summary (the preview or the
  download), sending, cancelling, pairing and unpairing; and the reads the page makes by
  itself (the configuration, the user and groups, the printer's status, asking about a
  slice job). The 300 seconds are counted for each request; the panel line shows the
  earliest-failing one's countdown.
- **While the server cannot be reached,** Cancel slice is disabled with its line
  ([decision 31](../docs/mockups/print-wizard/DECISIONS.md#preview-step); see
  [The slicing card](#the-slicing-card)).
- **A progress stream is not such a request:** it is reopened silently whenever it
  closes ([Following progress, and reconnecting](#following-progress-and-reconnecting)).
  Open: what happens when it cannot be reopened
  ([A progress stream that cannot be reopened](README.md#a-progress-stream-that-cannot-be-reopened));
  the guide recommends treating a stream that has failed to reopen for
  `STREAM_REOPEN_FAIL_S`, or carried nothing for `STREAM_SILENT_S`, as a failed request,
  with the same panel line. Build the reopening; build that rule only once it is decided.

**The one case known to show this message for minutes.** A user who submits a plate while
the slice service is finishing another user's slice before it stops for a deploy sees
"The server is being slow" until that slice ends and the replacement starts (at most the
240-second time limit plus the replacement's start), and past 300 seconds "The server
could not be reached". Open, owned by the slice service:
[What a user sees while the slice service stops](../slice/README.md#what-a-user-sees-while-the-slice-service-stops).

Open: a plate configuration submitted twice, when a retry follows a lost answer, can
cancel the slice its own first attempt made; the front server's guide recommends a value
of the page's own making on each submission
([A plate configuration submitted twice](../front/README.md#a-plate-configuration-submitted-twice)),
to be settled before phase 2 is built.

### Tests

All on the fake clock, with the fake front server dropping or holding answers:

- A request that fails once and succeeds on the attempt at 1 s shows nothing.
- At 19.9 s of failures nothing shows on the panel line; at 20 s the amber line shows,
  counting down to the attempt at 31 s; the figure falls by one each second the clock
  moves.
- The waits between attempts are 1, 2, 4, 8, 16, 30, 30 … seconds; no attempt after 300 s.
- At 300 s the red line and Try again; Try again attempts at once and restarts the count
  (a further 20 s of failures shows the amber line again).
- Retry now attempts at once and does not restart the count.
- A part's row says "Taking longer than usual; still trying…" at 4 s and not at 3.9 s;
  after 300 s the row keeps its part and Try again retries it.
- The line goes the moment any request is answered.
- `slice.busy` is not retried; an error report marked retryable that says a service did
  not answer is retried; one not marked retryable is shown at once.
- The parts, layout and settings in the browser's storage are unchanged after 300 s of
  failures, and the Layout step works throughout.
- Cancel slice is off while the front server cannot be reached and on again after.
- A repeated request (answer lost, request sent again) leaves the page in the state of
  one request: one part row, one slice followed.

## Signing in, and "sign in again"

Every user signs in with Onshape's OAuth, in Onshape's panel and outside it alike; there
are no accounts or passwords of PenguinSlicer's own. A sign-in sets one encrypted cookie
that lasts thirty days ([the front server](../front/README.md)). Every route of the front
server refuses a request without a signed-in user, except the sign-in routes and the
daemon's ([the front server](../front/README-details.md#which-routes-need-a-signed-in-user)).
On one machine (phase 2) the front server signs in a fixed made-up user and group, the
development identity, with no call to Onshape, and the wizard opens straight on its first
step. From phase 3:

| Screen or state | What the user sees | Whose sentences |
|---|---|---|
| Opening the wizard when not signed in | Nothing of PenguinSlicer's: a request for one of the wizard's pages starts the trip to Onshape (which asks the user to sign in, and the first time to allow PenguinSlicer to read who they are and their companies and classrooms) and back. A user signed in to Onshape who has allowed it before sees no screen in between | None |
| A sign-in that failed (refused, or Onshape did not answer) | A plain page with the header's first line only (no step tabs, group or printer-status icon) and one message: "PenguinSlicer could not sign you in with Onshape.", then "You did not allow PenguinSlicer to read your Onshape account. It reads only your name and the companies and classrooms you belong to." or "Onshape did not answer."; one button, **Sign in with Onshape** | The front server's (*proposed* `front.sign_in_failed`, `front.onshape_unavailable`); this page is served by the front server |
| A sign-in that has run out (thirty days, or every sign-in ended by an emergency replacement of the cookie's key) | Learnt when the front server refuses a request as not signed in (*proposed* `front.not_signed_in`). The step's content is replaced by one grey message: "Your sign-in has ended. Sign in with Onshape to go on. Your parts, layout and settings are kept in this browser.", one button, **Sign in with Onshape**. The header stays; from phase 5 the printer-status icon shows a grey dot and "…". The button takes the trip to Onshape and back, and the wizard reopens on the step the user was on, the plate as it was | The front server's |
| A browser that is not supported (Safari) | A plain page, served by the front server, saying that PenguinSlicer needs Chrome (*proposed* in [the front server's guide](../front/README.md#signing-in)) | The front server's |

**The page does not leave for Onshape by itself** when a request is refused as not
signed in: a user in the middle of dragging an instance would lose their place without
knowing why, and nothing is lost by waiting (the guide's choice 1). This replaces the
earlier proposal that the page starts the sign-in itself; the contract's line saying so
is to be corrected to match ([the contract](../contracts/wizard-front-server.md#signing-in-and-the-cookie)).
Only a request for one of the wizard's pages starts the sign-in.

**"Sign in again"** is a link inside the group details
([The current group](#the-current-group)), not on the header line, so the line stays one
row at 320 px (the guide's choice 2). It reads the user's groups afresh, for two calls to
Onshape; until the Onshape app is public, a user's groups are read only at sign-in (and
once a day after), so a user added to a company since does not see it until they use
this link. [D134, D340] It takes the trip to Onshape and back and returns to the same step
with the group details open. The front server owns the route; the page's stored work is
untouched by it. Open: nothing limits how often a user may use it
([the front server's item](../front/README.md#sign-ins-and-the-allowance)).

**Requests from other sites.** Every request of the page's that changes something carries
a header that only the wizard's own page can set (*proposed* name
`X-PenguinSlicer-Wizard`), and the front server checks the request's origin
([the front server](../front/README-details.md#requests-from-other-sites)). [D140] Inside
Onshape's panel the cookie is one that browsers send to an embedded page, so the cookie
alone does not prove a request came from the wizard.

Open: stored work is not tied to a user, so a different person signing in on the
run-out screen is shown the last user's parts
([Stored work is not tied to a user](README.md#stored-work-is-not-tied-to-a-user)).
Open: there is no sign-out ([Sign-out](README.md#sign-out)). Open: a list of permitted
groups would send a user outside it to the failed-sign-in page
([Who may sign in](../front/README.md#who-may-sign-in)).

Tests: a refused request as not signed in shows the run-out message in place of the
step and starts no navigation; the button's return lands on the stored step with the
plate unchanged; Sign in again's return opens the group details; every changing request
carries the header; the failed-sign-in page shows the fake front server's sentences.

## The current group

The header's second line names the current group, "Config: 6238 (Popcorn Penguins)", by
the Onshape company's or classroom's name, or the user's own name for a user in none. The
name is a button that opens the **group details**, a joined box
([decision 2](../docs/mockups/print-wizard/DECISIONS.md#whole-panel) for the line; the
group details are designed in the guide, and fake 25 is where the mockup's name linked
nowhere):

- the user's groups, one to a row, the current one checked; a click on another makes it
  current;
- "Signed in as Alex Chen";
- a link, **Sign in again**, with one line under it: "Reads your Onshape companies and
  classrooms again."

A click elsewhere, Escape or the name again closes it. A user in one group sees one row
and still has Sign in again. [D118] The choice is kept in the browser's storage and sent
with each request; the front server accepts it only if the sign-in cookie lists that group
([the front server](../front/README-details.md#groups-and-the-current-group)). [D119]

| Screen or state | What the page does and shows |
|---|---|
| Changing the current group, with changes or a slice to lose | A confirmation: "Change to FRC 1678? Your 2 changes and this plate's slice are cleared. Your parts and layout are kept." Going ahead: the filament and profile become the new group's first, the changes are cleared, a slice waiting or running is cancelled, the plate must be sliced again; the parts and the layout stay, and the Layout step checks them against the new printer's plate. With nothing to lose, no confirmation (the guide's choice 3) |
| A plate already sent, after the change | It goes on printing at its own printer; the printer-status icon now shows the new group's printer. Changing back shows the earlier print again in the icon and the printer details, and the last-print note when it finishes, but not the print card with Send enabled, since the sent sliced plate was cleared |
| A group the user no longer belongs to (the front server refuses the stored group, *proposed* `front.group_not_allowed`) | The page takes the first of the user's groups and says so in a notification: the front server's sentence ("You are no longer in 6238 (Popcorn Penguins).") then the wizard's own, "PenguinSlicer now uses FRC 1678's configuration and printer." The group details then offer the other groups and Sign in again. Taking the first group without asking is written as the design though no source states it |
| The reload glyph | Reads the configuration again. If the chosen filament or profile is gone, the first one takes its place and a notification says which |
| A configuration that cannot be read (*proposed* `front.configuration_unreadable`) | *Proposed*: a red message in place of every step's content, with the front server's sentence (which sends the user to whoever wrote the configuration, naming no "administrator") and the reload glyph as its one control; the header stays, so the user can change group; the stored plate is untouched |

Open: the last row is undecided
([A configuration that cannot be read](README.md#a-configuration-that-cannot-be-read));
build the red message, which the recommendation and the front server's rule both point
to, and change it if the decision differs. A damaged configuration is never replaced by
the default.

Tests: changing group with changes shows the confirmation and, confirmed, clears changes
and cancels the slice (the fake front server sees the cancel) while keeping parts and
layout; Escape keeps everything; a refused stored group falls back to the first group
with the two sentences; the reload glyph with a removed profile picks the first and says
so; an unreadable configuration shows the red message on every step.

## The configuration

A group's **configuration** holds its filaments, each with a colour and its own profiles,
the printer's Orca profile, and the units of uploaded files
([its contract](../contracts/configuration.md)). The page always uses the current
group's configuration, read whole through the front server, on opening and when the
reload glyph is pressed. An edit writes the whole document on the condition that it has
not changed since it was read; the second of two editors is told to reload
([the front server](../front/README.md)). [D115] The configuration's edit screens are a
feature of their own, in no phase yet
([the plan, Known future work](../docs/plans/penguin-slicer-plan.md#known-future-work));
until they exist there is a fixed set of configurations (the built-in default, or a
document the owner writes by hand), and the wizard only reads the configuration. A group
with no configuration document gets the built-in default, the H2S profile.

What the wizard takes from it:

- **The plate's size and height,** from the printer's Orca profile the configuration
  names (its `printable_area` and `printable_height`), the profile the slice service
  slices for and the plate configuration names as its `printer`. They feed the Layout
  step's figures line, Arrange and the placement check.
- **The printer's display name** is not the configuration's: it comes from the
  paired-printer record. Open:
  [Where the name of the printer comes from](README.md#where-the-name-of-the-printer-comes-from).
- **Profiles by the group's own names.** For each filament the profiles it lists and no
  others, under the names it gives ("Structural", "Pulley", "Camera mount"), with each
  profile's purpose as its option's tooltip
  ([decision 10](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2)).
- **The units of uploaded files,** sent beside each part uploaded from a file. The page
  never changes a part's bytes; only the slice service applies the scale
  ([the plate configuration](../contracts/plate-configuration.md#to-be-built)). Open:
  [STL files in millimetres before the edit screens exist](README.md#stl-files-in-millimetres-before-the-edit-screens-exist).
- **A colour for each filament,** shown beside the filament's name in the Filament menu,
  so two filaments of one material can be told apart. Never used in the layer preview
  ([The layer preview](#the-layer-preview)).

## The Parts step

The wizard opens here: the list of parts to print, each with a quantity.

| Screen or state | What the user sees and does | Mockup |
|---|---|---|
| Inside Onshape (phase 4) | A prompt above the list, "Click a part in the Part Studio" or "Click a part in the assembly", that never changes. A click on a part adds it with quantity 1; a click on one already listed raises its quantity by one and flashes its row. In an Assembly a click on an instance, in Onshape's list or graphics area, adds its part. No button adds every part | [decision 14](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1), [decision 21](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| Outside Onshape (phase 2) | An upload area for binary STL files, dropped or chosen, with one line under it: "STL files are read in inches." (or "in millimetres.", as the configuration says). The configuration's option is the only control; a row has no switch | [decision 51](../docs/mockups/print-wizard/DECISIONS.md#units-version-6), M25 |
| A row | The part's picture, name, size in its own units, quantity and a remove button; no refresh button (a part changed in Onshape is removed and added again) | [decision 18](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| A part arriving | Its row with a thin progress bar and "Arriving from Onshape…" or "Uploading…". The bar promises no duration | [decision 15](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) |
| A part still arriving when the user moves on | Never holds Next. It joins the plate on the Layout step, at once if the user is there, otherwise the next time that step is shown, and a notification on the current step says "Gusset Plate arrived after you left the Parts step. It joins the plate when you go back to the Layout step." | [decision 5](../docs/mockups/print-wizard/DECISIONS.md#whole-panel), [decision 23](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1), M21 |
| A part whose upload gets no answer | Its row stays, since the part is already in the browser's storage; "Taking longer than usual; still trying…" after 4 seconds; after 300 seconds the row keeps the part and shares the panel line's Try again | [decision 17](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1), departed from |
| Under the list | One line counting what the plate holds, and how many parts are still arriving | |
| Clearing the plate | The rows are removed by hand; nothing else starts a new plate | |

Open: how a second plate is started, and what the number in "Plate 1" counts
([Starting a second plate](README.md#starting-a-second-plate)). Build removing rows; do
not build a New plate action until it is decided.

### A part that cannot be used

Each part is checked by the slice service the moment it is added, so a part that cannot be
sliced is found here. [D74] A part that cannot be used is a notification naming it, and it
is not added: the list never holds a broken row. The notification's sentences are those of
the component that refused it; the wizard adds "Your other parts are fine." only while the
list holds other parts. A second failure of the same part replaces its notification
([decision 16](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1),
[decision 19](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1)). Next stays as
it was, and there is no Try again.

| What happened | Code | The notification says |
|---|---|---|
| Onshape cannot export the part (phase 4) | The Onshape integration's (named in phase 4) | "Onshape could not export Shooter Hood Rib, so it was not added.", and what to check in Onshape: one closed solid, not a surface and not several bodies; the Part Studio rebuilds with no red features |
| The file cannot be read as a part (empty, cut off, padded, not an STL) | `slice.part_unreadable` | The slice service's: that the file could not be read as a part, naming it, and to export it again |
| A text STL | `slice.part_not_binary` | The slice service's: that a binary STL is needed; export it again as binary |
| Too small or flat, nothing to print, too large for the printer | `slice.part_too_small`, `slice.part_no_volume`, `slice.part_too_large` | The slice service's. For an uploaded file refused as too large, followed by the wizard's own reminder of how STL files are read ("STL files are read in inches."), since a millimetre file read as inches is the likeliest cause; no source states this, the guide writes it as the design |
| Over the size limit | The wizard's own, see [The limits on a plate](#the-limits-on-a-plate); should the slice service refuse all the same, `slice.part_too_detailed` with its own sentence | |

A part the slice service accepts with a warning is added, and the warning stays on its
row in amber without holding Next
([decision 20](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1)):
`slice.part_not_watertight` (of the kind "Gusset Plate is not watertight: its mesh has 14
open edges in 2 places. It may still slice and print. If the slice fails, look in your CAD
program for faces that do not meet, then add the repaired part again."),
`slice.part_inside_out`, and `slice.part_maybe_inches` (every side under 5 mm).

**A part the slice service accepts and the page cannot draw** is a defect in the wizard.
*Proposed*: the part is not added; the wizard's own notification says PenguinSlicer could
not show the part and that the fault is PenguinSlicer's; the failure is reported to the
server's log. Open: there is no means yet for that report
([Failures in the browser that reach no log](README.md#failures-in-the-browser-that-reach-no-log)).
A malformed file must end in a notification, never in a frozen panel: the page's reader is
bounded by `MAX_PART_BYTES` and runs off the main thread (*proposed*).

Open: files other than binary STL (3MF, text STL) are refused
([Files other than binary STL](README.md#files-other-than-binary-stl)); build binary STL only.

### The limits on a plate

All three are the slice service's limits. The page checks each itself before sending, so
these sentences are the wizard's; should the slice service refuse all the same, its own
sentence is shown ([decision 22](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1)
for the 150).

| Limit | What the user sees | Slice service's code |
|---|---|---|
| A part is at most 7.5 MB (`MAX_PART_BYTES`, 7,500,084 bytes, 150,000 triangles) | A notification, nothing sent: "bracket.stl is 9.1 MB. PenguinSlicer takes parts up to 7.5 MB (150,000 triangles), so it was not added. Export it again from your CAD program at a coarser resolution." For a part picked in Onshape, the notification names the part and says it is too detailed to slice here | `slice.part_too_detailed` |
| At most 25 different parts (`MAX_PARTS`) | The twenty-sixth is not added: "A plate takes up to 25 different parts, so Gusset Plate was not added. Remove a part, or print it on a second plate." Raising a listed part's quantity still works | `slice.too_many_parts` |
| At most 150 instances (`MAX_INSTANCES`) | One part's quantity cannot be typed or clicked past 150. When the parts together pass it, a red message under the list, "This plate would hold 163 instances. Up to 150 instances per plate; print the rest on a second plate.", and Next off | `slice.too_many_instances` |

Open: whether the Onshape integration exports an over-size part again more coarsely by
itself is for phase 4's design.

Tests: a file of 7,500,084 bytes is uploaded and one of 7,500,085 is refused with the
sentence and no request; the twenty-sixth part is refused and the quantity of a listed one
rises; a quantity stops at 150; parts totalling 151 show the red message and Next off; each
failure row of the table, from the fake front server's error report, shows its sentences
and adds no row; "Your other parts are fine." shows only with other parts listed; a second
failure of one part replaces its notification; a warning stays on its row and Next stays
on; a part arriving after the user left joins the Layout step as described.

## Uploading each part when it is added

The wizard uploads each part by itself, at the moment the user adds it, in one request of
at most 7.5 MB (7,500,084 bytes, `MAX_PART_BYTES` in
[the plate configuration](../contracts/plate-configuration.md#limits)), far under the
100 MB Cloudflare allows a request. [D70] Railway's own limit on a request body is not
stated in its documents; one real upload of a 7.5 MB part settles it
([the architecture](../docs/architecture.md#to-confirm-before-building-on-it)).

The page keeps the part in the browser's storage first, then uploads it with its units;
the front server passes it to the slice service with the user key, and the slice service
keeps it in the part store under the user key and the SHA-256 hash of its bytes. The
answer gives the page that hash, with the part's measurements and any warnings
(*proposed*, as in [the slice service's details](../slice/README-details.md#to-be-built)),
and the page keeps the hash beside the part. The slice service runs its checks as the part
arrives, so a refused part is refused on the Parts step ([D74]; the table above).
(*Proposed*:) the slice service refuses a part larger than 7.5 MB before reading it.

A part whose upload gets no answer is not refused: the page retries it
([Retrying every request](#retrying-every-request)) and its row stays.

## The Settings step

Two menus, four quick changes and one button; the common case stays short.

| Screen or state | What the user sees | Mockup |
|---|---|---|
| Filament and Profile | The Filament menu offers the configuration's filaments, each with its colour beside its name. The Profile menu offers the chosen filament's own profiles under the group's names; a profile's purpose is its option's tooltip. Picking another filament picks its first profile. No printer row | [decision 9](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), [decision 10](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) (the colour departs) |
| The quick changes | Four menus, Infill, Walls, Supports, Brim; one to a row below 480 px, two from 480 px. They and advanced mode edit one shared set of changes | [decision 12](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| The caution | From the first change until the changes are cleared, under the Profile menu: "⚠ Changing the filament or the profile clears your 2 changes." Nothing after they are cleared | [decision 11](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Changing the filament or the profile | Clears every change, since a change is a departure from one profile | [decision 11](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| No change | The Advanced mode button stands alone under the quick changes | [decision 12](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Once a setting is changed | The **changes box** takes its place: a yellow box headed "2 settings changed from Structural", one line a change, and the Advanced mode button. Each line is a link that opens advanced mode at that setting, its section and setting group open, the setting scrolled into sight and flashed. No Reset all in the box | [decision 12](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |

### Advanced mode

Advanced mode fills the panel and offers every setting of Orca's that is a parameter with
a value (a choice from a list, a number, a piece of text): all of about 295, less the
programmatic ones (those that run a program, name a file on the slice service's machine,
or hold custom G-code), which are not shown and which the slice service refuses. [The
decisions of Fri 2026-11-27, item 5; fake 13 showed a sample of 99]

| Part | What it is | Mockup |
|---|---|---|
| Its header | "PenguinSlicer" with the printer-status icon; "Advanced mode", the profile and the changed count ("Structural, 2 changed"); **Reset all**, which asks in a confirmation before putting every setting back | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| The way out | **Back to Settings** at the bottom is the only way out; Escape does not close advanced mode | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Sections | Quality, Strength, Speed, Support, Others, each with collapsible setting groups (such as Precision). No search box, no common/all switch, no "changed only" filter | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), M26 |
| Below 480 px | An accordion of bordered cards (white, 1 px `#d0d7de`, radius 6 px): a section's heading with a chevron and its changed count ("Strength · 1 changed"), and on an open card the expand-all icon; setting groups are rows inside. Each card opens and closes by itself | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| From 480 px | A rail of section names down the left, each with a changed count, the chosen section's setting groups beside it; the rail shows the section last opened in the accordion | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Setting groups | Always one column, at most 480 px wide. A heading's chevron points right when closed and down when open; no count of its settings, only a changed count ("Precision · 1 changed"). One icon button, a double chevron, expands or collapses every setting group of a section (tooltip "Expand all" or "Collapse all") | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Open and closed | Everything starts open the first time; what the user closes is remembered in the page's memory (not the browser's storage) for as long as the page is loaded: across steps, closing and reopening advanced mode, and the panel crossing 480 px. A reload forgets it | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| A changed setting | A tinted background, a bar on its left and a dot after its name; under it "Profile 0.012 mm · Reset", the link putting the profile's value back. A value outside the setting's range is refused where it is typed | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| By keyboard | Opening puts focus on the first section's heading, or on the setting when a line of the changes box opened it; focus stays where the user acted (after Reset, on the setting's own control); what advanced mode covers cannot be reached; closing returns focus to the line or button that opened it | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) |
| Keeping the changes | Changes are part of the user's work: kept in the browser's storage, back after a refresh | [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2), departed from |

Settings are drawn from each one's kind, range and choices, not from a design made by
hand for each setting. Open: where that list, with each profile's value, comes from
([Where advanced mode's settings come from](README.md#where-advanced-modes-settings-come-from));
the recommendation is a request to the front server, which passes the slice service's
list, when advanced mode opens. Until it is settled, build the drawing from a list of that
shape and leave its source behind one interface. The slice service as built accepts four
overrides (`slice.bad_overrides` for any other); accepting every parameter setting is the
slice service's work.

Tests: changing the filament clears the changes and picks the first profile; the caution
shows from the first change and goes when cleared; a line of the changes box opens
advanced mode at its setting with its section and setting group open; Escape does nothing
in advanced mode; closed sections survive leaving and reopening and a resize across
480 px, and are all open after a reload; changes survive a reload; a value out of range is
refused; focus goes where the table says.

## The Layout step

A 3D view of the plate the user works in directly: no modes and no tools to pick up
([decision 27](../docs/mockups/print-wizard/DECISIONS.md#layout-step)). The view fills
the panel's width and grows with it, square at narrow widths and 4:3 from 520 px, with no
height cap ([decision 25](../docs/mockups/print-wizard/DECISIONS.md#layout-step)). The step
does not change the list of parts: no duplicate, delete, undo or redo, and Delete, Ctrl+D,
Ctrl+Z and Ctrl+Y do nothing; no scale, cut, mirror or per-part settings; Back goes to the
Settings step ([decision 24](../docs/mockups/print-wizard/DECISIONS.md#layout-step), M16).

### What is on the step

| Part, top to bottom | What it shows | Mockup |
|---|---|---|
| Toolbar | **Arrange**, **Auto-orient**, and at the right a "?" icon opening the list of gestures in a small panel (Escape or a click elsewhere closes it); the list says "Hold Shift while turning to turn in 45° steps." | [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6), [decision 62](../docs/mockups/print-wizard/DECISIONS.md#the-rotation-handle-version-7) |
| The status line | Green when every instance fits ("✓ All 16 instances fit the plate."); red with the first problem, with "+2 more ↓" when there are others; a click on a red line scrolls to the messages | [decision 27](../docs/mockups/print-wizard/DECISIONS.md#layout-step), M7 |
| The view | View buttons in a corner (Zoom to instances, Whole plate, Top); at the bottom left the pointer line, 11 px, saying what is under the pointer (an instance's name, "Lay it on this face: 0.250 in tall", "Drag to turn · Shift: 45° steps") | [the Terms](../docs/mockups/print-wizard/DECISIONS.md#terms), M7 |
| The selection line | Nothing selected: "90 instances on the plate, 10 beside it."; one: its name, footprint and height in its part's units; several: "5 instances move and turn together". Beside it at most one link: "Lay it the best way" when it does not lie its best way, "Put back as modelled" when laid differently from the model, nothing when it lies as modelled and that is its best way | [decision 57](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6), [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |
| The figures line | "Shop H2S: plate 340 × 320 mm, up to 340 mm tall, 12 mm apart" (5 mm with supports off), size and height from the printer's Orca profile | [decision 55](../docs/mockups/print-wizard/DECISIONS.md#units-version-6), [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |
| The messages | Anything the wizard moved; under "Fix these 2 before Next:" one red message for each problem with its button. A message about a move, and "Arranged 16 instances.", goes when the user leaves the step; a problem stays until fixed. Every sentence here is the wizard's | [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |

### Moving, turning and looking

The mouse works as in Onshape (M2): drag an instance to move it; right-drag to look
around; Shift-drag, middle-drag or Ctrl with right-drag to slide the view; scroll to zoom;
a left-drag on empty plate looks around. Shift-click or Ctrl-click adds to the selection,
and dragging one of a selection moves them all. F zooms to the instances, Ctrl+1 looks from
above, Ctrl+A selects every instance, Escape clears the selection. A touch screen works for
every click; the gestures are designed for a mouse.

**The rotation handle** ([decision 62](../docs/mockups/print-wizard/DECISIONS.md#the-rotation-handle-version-7)):
a round handle beside the selection that turns it about the vertical. A press fixes, for
the whole drag, the pivot (the middle of the selection's box), the handle's distance and
its side; while dragged the handle stays on that circle and turns through the same angle
as the instance, never hopping sides. Each instance turns rigidly about the pivot. The
mesh moves before the frame is drawn, so the handle and the dashed selection box never
lead it. Turning is free; a readout shows the first selected instance's orientation on the
plate ("↺ 37°" anticlockwise, "↻ 37°" clockwise, "0°" square, measured against the same
face-down position reached straight from the part as modelled). Holding Shift snaps that
orientation (not the angle turned) to multiples of 45°, taking effect at once when pressed
or let go mid-drag; in a selection, the first instance snaps and the others turn by the
same angle. After the drag the handle stays fixed to the first selected instance until the
selection changes or it is laid down. It is drawn over everything, and moves 45° at a time
to the first side where it covers no patch in sight, only while no drag is going on
([decision 49](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5)).

### Laying an instance on a face

Selecting one instance shows translucent blue rounded patches on the faces it could lie on
(PenguinCAM's accent `#2f81f7` at 22% opacity, 55% under the pointer); a click on a patch
lays it down on that face; a double-click on a flat face does the same. No button, no mode;
with two or more selected, no patches (M1;
[decision 49](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5)).
**Hull patches** lie on the flat faces of the part's convex hull; **bounding-box patches**
lie on a side of the part's bounding box that no hull patch points toward, drawn like the
hull patches, 10% in from the side's edges and 0.1 mm out (M29;
[decision 61](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5)).
Only patches in sight are drawn and clickable; the face it lies on has none; the pointer
line says what laying it there gives ("Lay it on this side: 1.732 in tall").

**Laying down never moves another instance**
([decision 26](../docs/mockups/print-wizard/DECISIONS.md#layout-step)):

| What follows a lay-down | Message |
|---|---|
| It still fits where it stood | None |
| It no longer fits: moved to the nearest free spot, turned if need be | Green: "L Bracket #1 no longer fitted where it stood, so it was moved to the nearest free spot." |
| No free spot: it waits beside the plate, marked off the plate, already turned to fit the plate if it is too long as it lay | Amber: "L Bracket #1 no longer fits on the plate and waits beside it. No spot on the plate is free for it lying this way. The other instances stay where you put them; press Arrange to make room." |

### Parts arrive lying their best way

A new part's instances are laid down by auto-orient, and nothing is said (M3;
[decision 27](../docs/mockups/print-wizard/DECISIONS.md#layout-step)). **Auto-orient** does
the same on request, for the selected instances or all when none is selected; if the plate
then needs rearranging, the wizard arranges it and says "Arranged the plate again to make
room." ([decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6)).

### Arrange

**Arrange** places every instance on the plate, in a compact pile about the plate's middle,
at the spacing the settings ask for, says "Arranged 16 instances.", and never turns an
instance ([decision 64](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6), M6).
Arrange and Auto-orient stay two buttons. When Arrange cannot fit everything and laying
instances their best way would fit more, its message offers that as one button: "Arrange
placed 12 of 16 instances; 4 instances do not fit and wait beside the plate. Arrange keeps
how each instance lies. With 5 instances laid the best way, everything would fit. Or lower
the quantities and print the rest on a second plate.", with **Lay them the best way: all
fit**.

The wizard turns an instance about the vertical only when it has just laid it down itself
and it is then too long for the plate, by a quarter, an eighth or three eighths of a turn,
the first that fits, at four moments
([decision 64](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6)): a
part that arrives too long as it lies, before its first Arrange; an instance Auto-orient
lays down that is then too long; an instance a lay-down leaves beside the plate; an
instance moved to the nearest free spot after a lay-down. A 353 mm rib on a 340 × 320 mm
plate fits only on the diagonal.

### The placement rules, and what each problem says

The slice service's own rules, so a plate the wizard passes is one the slice service
accepts: every instance at least `MARGIN_MM` (3 mm) inside the plate's edge, no taller than
the printer prints, and `SPACING_SUPPORTS_MM` (12 mm) from every other with supports on,
`SPACING_MM` (5 mm) off, measured between the outlines as turned. Next is off while any
rule is broken ([decision 57](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6),
[decision 64](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6)).

| Problem | The message | Its button |
|---|---|---|
| Two instances too close | "L Bracket #1 and Gusset Plate #2 are 6.2 mm apart; instances need 12 mm between them with supports on. Drag one away, or press Arrange." | Arrange |
| Many too close | One message: "23 instances are closer than 12 mm with supports on. Press Arrange, or drag them apart." Each stays marked in the view | Arrange |
| Across the plate's edge | "Gusset Plate #3 is not fully on the plate: it crosses the left edge. Drag it inward, or press Arrange." | Arrange |
| Longer or wider than the plate takes as turned | "Shooter Hood Rib #1 is 352.7 mm (13.885 in) from left to right as it is turned; the plate takes 334 mm. Turn it to fit turns it and arranges the plate again." Where it still stands on the plate, the message opens with "not fully on the plate" and goes on the same | **Turn it to fit**, in place of Arrange: turns it as on arrival and arranges again |
| A part that fits the plate at no turn | The same first sentence, then "Lay it down another way." | None |
| Too tall | "Shooter Hood Rib #1 stands 352.7 mm (13.885 in) tall; the printer prints up to 340 mm. Lay it down another way, or press Auto-orient." | Auto-orient |

An instance Arrange left beside the plate has no message of its own (Arrange's message
counts it), except one too long or wide as turned, which has its row above and is not
counted by Arrange. A click on a message selects the instances it names. **Turning
supports on after arranging moves nothing**: instances now too close get the usual message
until the user presses Arrange or drags them.

Open: the Layout step by keyboard ([The Layout step by keyboard](README.md#the-layout-step-by-keyboard));
build the buttons and the four keys; the recommendation that the status line and messages
are announced to a screen reader costs little and may be built.
Open: saying that a part will need supports
([Saying that a part will need supports](README.md#saying-that-a-part-will-need-supports));
build nothing for it.

Tests (on the fake clock where timed, and on real exported parts kept in the repository):
each problem row reached on purpose with its sentence and button; Turn it to fit turns and
arranges; Arrange keeps a 37° instance at 37°; Arrange's partial message and its button;
each of the four turning moments; a lay-down that moves to a free spot and one that waits
beside; supports turned on leaves positions unchanged and shows the too-close message;
messages about moves go on leaving the step; Delete, Ctrl+D, Ctrl+Z and Ctrl+Y do nothing;
the rotation handle stays on its circle through a drag and Shift snaps the orientation.

## The geometry: faces, auto-orient, Arrange, the placement check

All written fresh, from descriptions of the method in our own words: Orca is under the
AGPL and PenguinSlicer under MIT, so no Orca code, comment or constant name enters the
repository. The geometry runs in the browser with no server, off the main thread
(*proposed*: a worker) wherever it can freeze the panel. The page reads a part to draw,
measure and lay it out and never changes its bytes; for its own drawing and measuring it
multiplies an inch part's coordinates by 25.4 in memory only
([the slice service's guide](../slice/README.md#units)).

**Finding the faces a part can lie on**
([the note on hull faces](../docs/research/2026-11-21-lay-on-face-hull-faces.md);
[decision 49](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5),
[decision 61](../docs/mockups/print-wizard/DECISIONS.md#lay-on-face-faces-on-the-hull-version-5)):

1. The part's convex hull.
2. Hull triangles joined into flat faces, spreading to neighbours whose normal matches the
   first triangle's (not the neighbour's) within a fraction of a degree (*proposed*: the
   note's 0.06 degrees, Orca's; the mockup used 0.25 for its generated meshes; tune on
   real parts).
3. Faces dropped under 5 mm², with a corner sharper than 1 degree, and all but the 254
   largest.
4. A face dropped when a neighbouring hull face bends from it by less than 20 degrees and
   is at least half its size (round sides); a flat face beside a chamfer keeps its patch.
5. A bounding-box patch for each of the six sides of the bounding box, in the instance's
   own frame, with no kept face's outward normal within 30 degrees (plus half a degree for
   rounding); end patches included, and the 30 degrees a starting point to tune (M29).

A click turns the instance by the shortest rotation that points the face straight down,
keeping its turn about the vertical. Faces are found once a part and turn with it. Needed
on real parts and not exercised by the mockup's: unequal facets on a round side (treat a
run joined by shallow bends as one round side); round sides of fewer than 18 facets; a
part modelled at an angle to its axes; and a tip-over test on each face, using
auto-orient's stability test.

**Auto-orient.** Candidates: the faces above, and the part as modelled. A candidate
counts only if stable (the centre of mass, dropped straight down, lands inside what
touches the plate) and at least 25 mm² touches. The cost, lower being better: the area
over air divided by the area touching, plus a small charge for height, plus a large
penalty when almost nothing touches. A part with no candidate (a sphere) stays as
modelled. Runs once a part on arrival. Its overhang threshold was invented for the
mockup's parts (fake 14) and is to be tuned.

**Arrange.** Works on each instance's convex outline seen from above, as it lies and as
it is turned, grown by the spacing; never turns one. Two packers run and the better is
kept: a shelf packer (largest first, first free spot scanning from the front-left corner,
the group then slid to the middle) and a pile packer (largest first, every free spot on a
5 mm grid, scored by how small and square the pile stays and how near the middle, the best
refined at 1 mm, the pile centred). Fewer instances left beside the plate wins; the
smaller pile breaks a tie. Convex outlines mean a curved or L-shaped part takes its hollow
side too; packing true outlines is not planned.

**The placement check.** The same outlines and the three rules of the slice service. It
runs on every movement of a drag with up to 150 instances, so it must keep up with a
drag. Open: agreement with the slice service's check
([Agreement between the placement check of the wizard and of the slice service](README.md#agreement-between-the-placement-check-of-the-wizard-and-of-the-slice-service));
the proposal is shared plates, just passing and just failing, run by both suites, and the
wizard holding instances a fraction of a millimetre further apart than the rule (the
mockup's thinned outlines, fake 10, were off by about 0.2 mm).

Open, and to be tried first in phase 2: laying on a face, auto-orient and Arrange on real
exported parts ([The risks to try first in phase 2](README.md#the-risks-to-try-first-in-phase-2)):
the eight real parts the slice service is measured on, and round parts exported at
Onshape's coarse and fine settings, timed and looked at one by one.

Tests: on the fixed set of real exported parts, the expected faces, patches, orientations
and placements written down and checked, without a browser window; the placement check
against the slice service's on the shared plates; Arrange never changes an orientation.

## The Preview step

Entering the step submits the plate; when the slice is done it shows the result
([decision 28](../docs/mockups/print-wizard/DECISIONS.md#preview-step)). Coming back with a
plate already sliced shows the result without slicing again. A slice goes on without its
page: leaving the step, a refresh, a lost network or a closed lid leave it running, and
coming back with the same plate finds it going or finished; a changed plate (a part moved,
a setting changed) cancels it and starts a new one (M17;
[decision 29](../docs/mockups/print-wizard/DECISIONS.md#preview-step)).

### The slicing card

A ring gauge with the percentage, the stage in words, the time taken and "about" the time
left, a bar, the list of stages with the current one marked, **Cancel slice**, and the
line "Slicing goes on if you step back; change the plate and it starts again."
([decision 30](../docs/mockups/print-wizard/DECISIONS.md#preview-step)). Stages and
percentage are Orca's own, passed through; the time left is the slice service's estimate,
good to about a factor of two.

| State | What the user sees | Mockup |
|---|---|---|
| Waiting behind other slices | The ring empty; the stage line "Waiting for the slicer: 2 slices ahead of yours." (or "1 slice ahead of yours."), updated as the number falls; the time waited counting up; no time left; Cancel slice works | None: designed in the guide [D54] |
| Slicing | The ring, the stage and the times | [decision 30](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| The front server cannot be reached | The figures stop; the time-left line says "no news since 0:41"; Cancel slice off with the line "Cancel slice is off until the server can be reached again; the slice may still be running." | [decision 31](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Reconnected | One line on the card: "Reconnected at 1:05. The slice kept running; the progress below is up to date." | [decision 31](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| The slice service restarted | The ring and the stages back to the start; the line "The slicer restarted, so this slice began again." The page has uploaded the parts and submitted the plate again by itself. The same for a slice still waiting when the slice service was asked to stop for a deploy, which it cancels saying why | None: designed in the guide [D103, D217] |
| Cancelled by the user | A grey message: "Slice cancelled at 0:23, during “Generating walls”. Nothing was saved or sent to the printer.", with **Slice again** and Back to Layout | [decision 30](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |

Open: when "The front server cannot be reached" begins for a page only following
progress ([A progress stream that cannot be reopened](README.md#a-progress-stream-that-cannot-be-reopened)).
Until decided, the state begins when a request of the page's (a cancel, an ask about the
slice job) has failed for `RETRY_QUIET_S`.

### No room to wait

The slice service runs one slice and lets two wait (the hosted start). [D55] A fourth is
refused with `slice.busy`: an amber message in place of the slicing card, with the slice
service's sentence ("The slicer is busy, try again in a minute."), the wizard's own line
"Your plate is unchanged.", and **Slice again**. The page does not try again by itself
(the guide's choice 6): a silent queue would hide how busy the slice service is.

### Stopped by a slice from another tab

A user has one unfinished slice at a time
([One unfinished slice job at a time](#one-unfinished-slice-job-at-a-time)). The page
whose slice was cancelled by a later one shows a grey message in place of the slicing
card: "This slice was stopped because you started another one in another tab or window.
PenguinSlicer slices one plate at a time for each user.", with **Slice again** and Back to
Layout. It never slices again by itself, so two pages cannot cancel each other in turn.
Open: two tabs at the wizard's address share one stored plate
([Two tabs on one stored plate](README.md#two-tabs-on-one-stored-plate)); build nothing
that assumes either answer.

### The result

| Part | What it shows | Mockup |
|---|---|---|
| Print time and filament | Large: "3 h 12 min", "84 g PETG", Orca's figures from the sliced file's summary | [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| One quiet line | The instances, the layers and how long the slice took | [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Warnings | The summary's warnings, in amber | |
| The layer preview | A 3D view of the sliced plate with a layer bar at its right; the readout under the view, "134 / 134 · 40.2 mm", one line at 320 px; the bar moves with the arrow keys and reports its layer to a screen reader; two small buttons step one layer down or up; **Reset view**; a "?" icon: "Drag to turn, right-drag to pan, scroll to zoom; drag the bar on the right to go through the layers." | [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Next | Goes to the Send step once the plate is sliced | [decision 34](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |

The Preview step's mouse differs from the Layout step's on purpose: here a left-drag turns
the view and a right-drag slides it, since nothing can be moved.

### A sliced plate that expires

A sliced plate is kept until two hours after its slice ended or two hours after its last
print ended, whichever is later ([The sliced file](#the-sliced-file)). The page is told
the moment of expiry by the front server, as it reckons it, with the summary and again
when a print of the plate ends, and never works it out from its own clock. At that moment
(on the fake clock in tests) the page shows a grey message in place of the result on the
Preview step and in place of Send on the Send step: "This plate's slice has expired. A
sliced plate is kept for two hours after it is sliced or after its last print ends. Slice
it again to print it; your parts, layout and settings are unchanged.", with **Slice
again**, which goes to the Preview step and slices. The sentence is the wizard's. If Send
or Download is pressed first and the front server refuses with its "sliced file expired"
report (*proposed* `front.sliced_file_expired`), that sentence is shown in the same place
with the same button. A notification saying the sliced plate "is still here" goes at the
same moment. The page does not slice again by itself (the guide's choice 5). On any other
step nothing shows, and entering the Preview step afterwards slices.

Open: the moment of expiry is not in the contract yet
([Telling the page when a sliced file expires](../front/README.md#telling-the-page-when-a-sliced-file-expires)).
Build the message on that moment and, until the contract carries it, on the front server's
refusal alone. Open: a page open at the expiry keeps the plate while a returning page
drops it ([Parts dropped on return and kept while the page is open](README.md#parts-dropped-on-return-and-kept-while-the-page-is-open)).

Tests: on the fake clock, the message replaces the result at the moment the fake front
server gave, not a second before; it shows on the Send step in place of Send; on the
Layout step nothing shows and the next Preview slices; a refused Download shows the front
server's sentence; "is still here" goes.

## Submitting a plate configuration

On the Preview step the page sends the front server a **plate configuration**: the
layout, the chosen settings, and the SHA-256 hash and units of each part, with no files
([the plate configuration](../contracts/plate-configuration.md)). [D73] So slicing again
uploads nothing. [D75]

When the plate configuration names a part no longer in the part store, the answer is an
error report (*proposed*: `slice.part_missing`, action `refresh_parts`) listing every
missing hash. The page uploads those parts again from the browser's storage and submits
the same plate configuration again, and the user sees nothing of it. [D79] A part leaves
the part store two hours after its last use, when the part store's limits push it out (at
most 25 parts for one user key; a twenty-sixth pushes out the least recently used), and
whenever the slice container restarts ([the slice service](../slice/README.md)).

The page keeps the id of the slice job and the time it submitted it in the browser's
storage.

Tests: a `slice.part_missing` naming two of three parts makes the page upload exactly
those two and submit again, with nothing shown; a second `slice.part_missing` in a row is
handled the same, and a third (*proposed*) is shown as a failure rather than looped.

## One unfinished slice job at a time

A user has one unfinished slice job at a time: submitting a plate cancels the user's
earlier unfinished one ([the slice service](../slice/README.md)). With the wizard open in
two tabs, the later slice wins. [D98] The page whose slice job was cancelled this way
learns it (*proposed*: from its progress stream's final report, or when it next asks) as
"cancelled by a later slice of the same user", and shows
[Stopped by a slice from another tab](#stopped-by-a-slice-from-another-tab).

Once submitted, a slice job runs to its end whether or not anything follows it. Leaving
the Preview step leaves it running (M17); coming back with the same plate shows it going
or finished; a changed plate submits a new one, which cancels the old.

## Following progress, and reconnecting

The browser follows a slice job, and from phase 5 a delivery job, as server-sent events
through the front server ([the front server](../front/README.md)). [D58] Every progress
stream sends a comment line at least every fifteen seconds while it has nothing to report,
because Railway closes a request after fifteen minutes, or after five without data, and
Cloudflare after 125 seconds without data.

- **The page reconnects when a progress stream closes,** silently: a close is normal
  (fifteen minutes on Railway, every restart of the front server). [D61] A stream that
  connects late gets the latest progress report at once; the report's `sequence` tells a
  repeated report from a missed one.
- **A slice that waits** carries how many slices are ahead of it. [D54]
- **No room to wait** is `slice.busy`. [D55]
- **If progress streams are held.** Whether Cloudflare and Railway pass server-sent events
  on unheld is not checked; if one holds them, the page asks for the latest progress report
  every second or two instead, by a route the slice service's interface and the relay's
  both have ([the architecture](../docs/architecture.md#to-confirm-before-building-on-it)).
  [D354] (*Proposed*, as in
  [the front server's details](../front/README-details.md#parts-and-slice-jobs-passed-to-the-slice-service):)
  for a slice job, the front server's route for asking about a slice job; from phase 5,
  a route that answers a delivery job's latest progress report. Open:
  [Whether progress reaches the page unheld when hosted](README.md#whether-progress-reaches-the-page-unheld-when-hosted),
  settled by one slice on the hosted service in phase 3. Build the asking as a second way
  to receive reports behind the same interface.
- Open: the front server's guide recommends following a print and the printer's status by
  a short request every ten seconds, with progress streams for slices only and at most
  four streams for one user
  ([How many users at once](../front/README.md#how-many-users-at-once-and-what-happens-when-the-threads-run-out)).

Tests (the fake front server closing streams at chosen moments): a stream closed mid-slice
is reopened and the page shows the latest report at once; a repeated `sequence` is ignored;
a gap in `sequence` is caught up by the latest report; the stream's close is never shown.

## Errors the wizard explains

Every failure the page can see arrives as an error report whose `message` and `remedy` it
shows and whose `detail` it never shows. A failed slice is a red message in place of the
slicing card ([decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step)). The
wizard's part is the buttons: one for the report's `action`, **Slice again** when the same
plate may succeed unchanged, and Back to Layout, Back to Parts or Back to Settings,
whichever step holds the remedy. Nothing of Orca's output is shown.

| Failure | Codes | The wizard's buttons |
|---|---|---|
| The plate is not acceptable, although the Layout step passed it (a defect in one of the two placement checks) | `slice.placement_off_plate`, `slice.placement_too_tall`, `slice.placement_too_close`, `slice.crosses_edge`, `slice.nothing_on_plate`, `slice.left_off_plate`, `slice.too_many_instances`, `slice.too_many_parts`, `slice.bad_plate_configuration` | Back to Layout |
| Empty layers, supports off | `slice.empty_layers`, action `enable_supports` | **Turn on Supports and slice again**; Back to Layout. Folded Details |
| Empty layers, supports on (a fault in the mesh) | `slice.empty_layers_with_supports` | Back to Parts. Folded Details |
| A profile or setting not accepted | `slice.unknown_printer`, `slice.profiles_not_offered`, `slice.bad_overrides`, `slice.profile_unreadable` | *Proposed*: Back to Settings |
| Two instances' paths would meet | `slice.orca_too_close` | Back to Layout |
| Nothing printable | `slice.no_layers`, `slice.print_empty` | Back to Parts |
| Too slow (the time limit, 240 seconds today) | `slice.timeout` | **Slice again**; Back to Parts |
| Out of memory (2,000 MB today, 6,000 MB *proposed* hosted, the slice service's setting) | `slice.out_of_memory` | Back to Parts; no Slice again (the guide's choice 7) |
| Orca failed with only a general reason | `slice.orca_failed` | **Slice again**; Back to Layout |
| Orca crashed or was stopped, the sliced file missing or damaged, the slice service failed | `slice.orca_crashed`, `slice.orca_killed`, `slice.orca_missing`, `slice.orca_unstartable`, `slice.no_output`, `slice.unreadable_output`, `slice.no_gcode`, `slice.output_unwritable`, `slice.scratch_unwritable`, `slice.unexpected`, and any code the wizard does not know | **Slice again**; Back to Layout |

The sentences are the slice service's
([its list](../slice/README.md#when-things-go-wrong)); for example, out of memory reads
today "This plate is too large to slice: the slicer needed more than the 2,000 MB of
memory the print server allows.", with the remedy of fewer instances or a second plate, or
for a single instance to split or simplify the part. [D43, D51] The two empty-layers
failures' Details hold the slice service's sentence of where to look on the part. Open:
whether they also hold Orca's own sentence with the heights
([Orca's own sentence under Details](README.md#orcas-own-sentence-under-details)).

There is no "plate too large" error before slicing: nothing caps a plate's volume, and a
plate too heavy to slice ends as `slice.out_of_memory` or `slice.timeout` (fake 9).

**Turn on Supports and slice again** turns Supports on and runs the placement check at
12 mm first. A plate that passes is sliced. One that does not is not: the wizard goes to
the Layout step, which says "Not sliced: with Supports on, instances need 12 mm between
them." above the usual message. Nothing moves by itself
([decision 57](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6)).

Tests: each row reached on purpose from the fake front server, with the buttons listed; an
unknown code as the last row; out of memory offers no Slice again; Turn on Supports on a
plate arranged at 5 mm goes to the Layout step with the line and slices nothing, and on a
plate at 12 mm slices.

## The layer preview

**What must be achieved** (the decisions of Fri 2026-11-27, item 18; the guide's
[The layer preview, as a requirement](README.md#the-layer-preview-as-a-requirement)): Orca
makes the sliced file; the wizard shows that file's own toolpaths, and the user inspects
them layer by layer, at a stated frame rate, in a stated browser, on a stated machine, with
the appearance [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step)
requires. **The method is not fixed:** it is found while building, because the mockup's
method (every segment a flat strip) is known not to be good enough and no better one has
been tried.

**The appearance** ([decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step)):

- Four fixed colours, one for each group of line types, whatever the filament:

  | Group | Line types | Colour |
  |---|---|---|
  | Walls | Outer and inner walls | Blue `#2b5c9e` |
  | Infill | Sparse and internal solid infill | Orange `#e0912f` |
  | Top and bottom surfaces | Top and bottom surfaces | Green `#2f9e7a` |
  | Supports and brim | Supports, their interface and the brim | Violet-grey `#9a8fb8` |

  The view's background is `#f2f4f7`. The filament's colour is never used here.
- The **colour key**, a joined box from a small icon at the view's top left (its four
  stripes in the four colours): four rows, a stripe and a name each, always all four,
  closed by default; closed by a second click, a click elsewhere, Escape or leaving the
  step. No line type can be hidden.
- Each line as wide as the settings' line width at its distance from the camera, never
  under 1 pixel.
- Walls shaded by the way they face, by darkening only: `#2b5c9e` facing the Layout view's
  main light (front left, above), `#1c3d68` facing away.
- The current layer drawn over the layers below, unshaded, at least 2 pixels wide.
- Above it each instance a ghost, grey `#95a0ac` at 36% opacity, cut at the current layer;
  gone when every layer is shown.
- No combs and no show-through at any viewing angle, edge-on and zoomed in included.

**The four requirements beyond the look**
([decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step)): a frame budget on
a machine without a graphics card, met at the largest plate the wizard allows, by whatever
means keeps the look; every 3D view (the parts' pictures, the Layout view, the layer
preview) drawing again after the browser loses its 3D drawing context, without a reload;
no combs and no show-through; proof by test renders of real sliced plates (several
plates, supports on and off, several layer counts, several viewing angles including
edge-on and zoomed in), each looked at and kept as evidence.

**The measurement** (all *proposed* in the guide, to be confirmed once the first risk is
measured: [The layer preview's frame rate, browser and machine](README.md#the-layer-previews-frame-rate-browser-and-machine)):

| | Proposed |
|---|---|
| Browser | The current stable Chrome on a desktop or laptop |
| Machine with a graphics card | A school-issue laptop: graphics built into the processor, four cores, 8 GB, 1920 × 1080, on mains power, Chrome reporting it draws 3D on the hardware; make and model recorded with the first measurement and kept as the reference |
| Machine without | The same class, four cores, 8 GB, with Chrome's use of graphics hardware switched off so it draws 3D in software |
| The view | The panel at 680 px, the view at 4:3 |
| With a graphics card | At least 30 frames a second while the view is turned or the layer bar dragged, on the 14.1 MB plate and on a plate at the 150-instance limit |
| Without | At least 10 frames a second while moving, no frame longer than one second, on the same plates |
| The look while moving | May be simplified while moving, the four colours and the outlines holding, the full look within one second of rest. This departs from decision 33's "at any viewing angle", with no exception for motion, and needs the owner's yes: do not build on it until given |
| Time to the first picture | Within 5 seconds of the result appearing; print time and filament shown at once |

The sizes: the heaviest plate the Popcorn Penguins print has about a million lines of
printer instructions in an 8.8 MB sliced file; twelve of the robot's largest block give
10.8 MB, 14.1 MB with supports on; 150 instances are allowed. Known: the flat-strip method
cost about 27 millionths of a second a segment a frame in software on an aarch64 Linux
machine (4.2 s for 152,101 segments; 10 to 21 s for some 400,000), which made Chrome lose
its 3D context; on a graphics card it was fast but showed combs and show-through. Drawing
only visible segments was about three times faster and changed the look, so not
acceptable as tried. Open, and to be tried first in phase 2:
[The risks to try first in phase 2](README.md#the-risks-to-try-first-in-phase-2), with
real sliced files of 8.8 MB, 14.1 MB and the 150-instance limit, two or three candidate
methods, on the machine without a graphics card.

Tests: a lost 3D context in each view, caused on purpose, draws again without a reload,
twice in one page; the layer bar by arrow keys and its screen-reader layer; the colour key
always has four rows; the readout is in millimetres. The look and the speed are proved only
by test renders a person looks at and by timing in a real browser.

## The sliced file

The state bucket's copy of a sliced file is the one everything uses: the browser fetches
it through the front server to draw the Preview step and to offer the download, and on
Send the relay hands it to the daemon ([the front server](../front/README.md)). [D85] The
page never stores a sliced file and never uploads one, so a printer only ever receives a
file the slice service made. [D86] A sliced file can be previewed, downloaded, sent and sent
again after a print until two hours after its slice ended or two hours after its last print
ended, whichever is later; past that the front server refuses it with an error report
saying it has expired ([the front server](../front/README.md)). Its last print ended when
the latest delivery job that used it ended. So after a print of any length, finished or
failed, Send is enabled again for the same sliced plate. The two hours count from when the
slice ended, which the front server knows from the time stored with the sliced file. A
three-day rule at Cloudflare R2 backs this up, counted from the last time the file was
stored; a send stores it afresh, and a send whose file has gone is answered that the
sliced file has expired and the plate must be sliced again
([the front server](../front/README-details.md#two-hours-deleting-and-the-backstop)). A
sliced file is 8.8 to 14.1 MB on the plates measured so far.

## The Send step

One decision: send this sliced plate to the printer now, or download it.

| Part | What it shows | Mockup |
|---|---|---|
| What will be printed | A card: the printer by name, the instances by part ("16 on one plate", "8 × Gusset Plate", "4 × L Bracket"…), the print time and grams. The printer's state is not repeated here | [decision 35](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| The plate-clear line | Above the button: "⚠ Check that the plate is clear and PETG is loaded. Send starts the print at once." | [decision 35](../docs/mockups/print-wizard/DECISIONS.md#send-step), [decision 59](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) |
| The Send button | A wide blue button, "Send to Shop H2S", with a caret whose menu offers **Download the sliced file**. Choosing from the menu changes what the button does; it does not act; the menu's send item has the button's label. Send sends at once, with no confirmation. By keyboard, Enter on the caret opens the menu on its first item, arrow keys move, Escape closes. Back keeps its width | [decision 36](../docs/mockups/print-wizard/DECISIONS.md#send-step), M23 |
| Download | Saves the sliced file to the user's computer, and leaves a notification naming the plate and the file's true size | [decision 36](../docs/mockups/print-wizard/DECISIONS.md#send-step), fake 11 |
| No printer paired | Nothing names a printer: no printer's name on the card, no plate-clear line, the button **Download the sliced file** with no caret, beside the message and the pairing form ([When Send is not offered](#when-send-is-not-offered)) | [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Until phase 5 | The same step with less: the card's instances, time and grams, no printer's name; no plate-clear line or caret; one button, **Download the sliced file**; no printer-status icon, no pairing message or form. The step and tab keep the name Send from phase 2 (the guide's choice 12, which departs from the plan) | None: designed in the guide |

### After Send

The **print card** at the top: the plate in words ("Plate 1, 16 instances, on Shop H2S"),
its stage on a track (Sending, Starting, Heating, Printing, Done), percent, layer of total,
time left, expected finish and when it was sent. The button is off and follows the stage
("Sending…", "Heating…", "Printing…", "Waiting for a person…")
([decision 37](../docs/mockups/print-wizard/DECISIONS.md#send-step), M11). Under the track
the card gives the stage in the words of printer delivery's progress report
(`stage_label`). Which of printer delivery's nine stages stands under which word of the
track, *proposed*:

| Track | Printer delivery's stages |
|---|---|
| Sending | `waiting_for_daemon`, `waiting_for_printer`, `waiting_for_earlier_print`, `downloading`, `uploading` |
| Starting | `starting`, `start_not_shown` |
| Heating, Printing | `printing`, by its `printer_stage` (heating the bed and the like under Heating) |
| Printing (the track stays), the card amber | `waiting_for_person` |
| Done | The delivery job's final `done` |

([The stages](../delivery/README.md#the-stages-what-a-user-sees-and-what-can-be-cancelled),
[printer delivery's states and stages](../delivery/README-details.md#states-and-stages).)

| State | What the user sees | Mockup |
|---|---|---|
| On its way, until the relay allows the start | **Cancel sending**. Cancelling leaves a notification: "Sending cancelled. Nothing reached Shop H2S and nothing will print. Your sliced plate is still here.", which goes when the plate is sent again. From the moment the relay has allowed the start, Cancel sending is no longer offered; a cancel arriving just after is answered with printer delivery's sentence on the card (`delivery.cancel_too_late`, `delivery.start_being_sent`), and the card goes on following the plate | [decision 37](../docs/mockups/print-wizard/DECISIONS.md#send-step), M22 |
| Printing | The figures. No pause or stop: that is done at the printer's screen | [decision 38](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Waiting for a person | An amber message in printer delivery's sentences, of the kind "Filament ran out. Load new filament, then resume the print on the printer's screen." A stage, never an end | [decision 39](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Failed | The card says so in printer delivery's sentences, of the kind "The print stopped at layer 51 of 134 (38%): the printer reported a filament tangle or a clogged nozzle. Clear the plate and check the filament path at the printer, then send the plate again from here. The sliced file is still here.", with folded Details: where the printer's screen shows the fault and what to check | [decision 40](../docs/mockups/print-wizard/DECISIONS.md#send-step), [decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step) |
| Finished | No card; the last-print note at the top of the step, "Your print finished at 11:25 am." | [decision 40](../docs/mockups/print-wizard/DECISIONS.md#send-step), [decision 60](../docs/mockups/print-wizard/DECISIONS.md#the-users-last-print-version-7) |

After a print that finished or failed, Send is enabled again for the same sliced plate,
under the plate-clear line, while the sliced file is kept. Nothing says "late" or "behind
its estimate" ([decision 43](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon), M24).
What the printer really reports while waiting and on failing is unknown until recorded in
phase 5; the quoted sentences are examples.

### When Send is not offered

States, not failures, so the sentences are the wizard's, from the printer's status. A
send that printer delivery refuses all the same (the printer became busy in between,
`delivery.printer_busy`) is shown with printer delivery's sentence in the same place.

| The printer | What the step shows | Mockup |
|---|---|---|
| Busy with another user's plate | A **busy card**: "Shop H2S is busy: printing for Alex Chen.", what it is ("8 instances of Gusset Plate"), percent, layer, time left and expected finish; the line "Send comes back when the printer is free; nothing queues."; Send off; the sliced plate stays ready | [decision 41](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Busy with a print nobody sent from PenguinSlicer | The busy card: "Shop H2S is busy: printing something that was started at the printer, not from PenguinSlicer.", with percent, layer, time left and expected finish, no sender or description; the same line | None: designed in the guide |
| Offline | An amber message: "Shop H2S has not been heard from for 7 minutes, so Send waits. Your sliced plate stays ready, and Send comes back as soon as the printer answers. Or download the file.", with Download. No guess at the cause | [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step) |
| Not heard from yet | Send off, with one line: "Waiting to hear from Shop H2S." (a few seconds after the front server restarts, up to half a minute after pairing) | None: designed in the guide (choice 10) |
| No printer paired | An amber message, the pairing form below it ([Pairing a printer](#pairing-a-printer)), and Download; nothing names a printer | [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step), departed from |

**Nothing queues:** a send to a busy printer is refused rather than held, because a queued
plate would start by itself on a plate nobody has cleared.

### A print that has gone quiet, and Stop following

A print has **gone quiet** when its report is stale, no sync for more than `STALE_S`
(40 seconds) [D177]. The print card keeps its last figures, greyed, with an amber line:
"No news from Shop H2S since 11:02 am. The print may still be running; these figures are
from then.", cleared by the next report. After `OFFLINE_S` (two minutes) the icon turns
to Offline. When both hold, the print's rows win (*proposed*): the icon says Offline, and
the Send step and the printer details keep the print card or busy card, greyed, with Stop
following, not the Offline message.

Once a print that had started has gone quiet, **Stop following** appears on the print
card, on the busy card and in the printer details, for every user of the group (the
guide's choice 9). It asks in a confirmation: "Stop following this print? PenguinSlicer
will no longer show its progress and cannot say how it ended. The print itself is not
stopped; that is done at the printer's screen." with **Stop following** and Keep
following. After it the card goes, a notification says "Stopped following Plate 1 on Shop
H2S. How it ended is not known.", and Send comes back once the daemon answers and the
printer is free. If the printer reports the print again before the user confirms, the
relay refuses the stop (`delivery.still_reporting`) and the card shows the fresh figures.
A print nobody stops following is given up by the relay after 24 hours of silence
(`delivery.outcome_unknown`). A plate the relay had not yet allowed to start needs none of
this: Cancel sending is still offered.

Open: what the icon and the printer details show after a print is no longer followed
([After a print is no longer followed](README.md#after-a-print-is-no-longer-followed));
*proposed*, the icon shows what the daemon next reports and the printer details say
"Stopped following Alex Chen's print at 11:40 am. How it ended is not known." Never show
it as Failed; build the rest once decided.

Tests (fake clock, fake front server as the relay): 39.9 s without a report shows nothing,
40 s greys the card with the line; 120 s turns the icon Offline while the card stays; Stop
following appears only for a started print, for any user; confirmed, the card goes with
the notification; a report arriving first refuses the stop; Cancel sending before the
start; a cancel answered as too late shows printer delivery's sentence.

## Printers, from phase 5

The Send step and the printer-status icon show what [printer delivery](../delivery/README.md)
reports through the front server.

### The printer-status icon

On every step at the right of the header: a printer, a dot and a word
([decision 43](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon)).

| The icon says | When |
|---|---|
| Free (green) | Nothing is printing; Free as soon as a print finishes (no "Finished") |
| Sending 40% (blue, pulsing) | A plate on its way |
| Heating, or Printing 61% (blue, pulsing) | A print going on, whoever started it |
| Waiting (amber) | The print waits for a person |
| Failed (red) | A print ended on a fault someone at the printer has to see to |
| Offline (grey) | No sync for two minutes [D163] |
| No printer (grey) | The current group has no printer paired |
| A grey dot and "…" | Paired and nothing heard yet: a few seconds after the front server restarts, up to half a minute after pairing, and while the sign-in has ended (choice 10; the architecture's "blank") |

A print card that was showing keeps its last figures through the seconds after a restart;
a page first opened then shows the grey dot and "…" and the Send step's line until the
daemon's next report.

**The printer details**, a joined box that grows down from the icon
([decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon)): opens
after the pointer rests on the icon for `DETAILS_OPEN_MS`, stays open while the pointer is
over the icon or the details, closes `DETAILS_CLOSE_MS` after it leaves both; a click opens
and pins them until a click elsewhere, Escape, × or a second click on the icon; a click on
details opened by the pointer pins them; a tap or Enter is a click; opening them closes the
change details. The icon has no tooltip; a screen reader hears one sentence ("Shop H2S is
free").

| State | The details say, under the printer's name |
|---|---|
| Free | "Nothing is printing.", and after a finished print "Last print finished 11:25 am (Alex Chen)", "(you)" for the user's own; the line goes when another plate is sent or 12 hours after the print finished |
| Sending | The plate's description, who sent it, percent sent, time left, expected finish and a bar |
| Printing or heating | Who sent it ("(you)" for the user), percent, time left, expected finish. A print started at the printer: "Started at the printer, not from PenguinSlicer.", then the same figures |
| Waiting for a person | Who sent it, percent, and what to do at the printer, in amber |
| Failed | Who sent it, when it stopped and at which layer |
| A print gone quiet | The last figures, "No news since 11:02 am.", Stop following; for as long as the print is followed, also after the icon turns Offline |
| Offline, no print followed | "Not heard from for 7 minutes."; after a front server restart since it last heard, "Not heard from for at least 3 minutes." (*proposed* wording) |
| Not heard from yet | "Waiting to hear from Shop H2S." |
| No printer paired | "PenguinSlicer needs to be paired with a printer.", and the pairing form |

At the bottom, whenever a printer is paired, **Unpair this printer**
([Pairing a printer](#pairing-a-printer)). Users of one group see each other's names and a
one-line description of the plate printing; nobody outside the group sees either. [D251]

Open: an old daemon, which printer delivery recommends the printer details report
([Daemon versions](../delivery/README.md#daemon-versions)).

### Pairing a printer

Someone starts the PenguinSlicer program on the computer beside the printer, which shows a
pairing code of eight letters and digits ("B6MQ-DN77"); then any signed-in user of the
group types it into PenguinSlicer, from any computer. The code is good for fifteen minutes
and one use. [D151] The **pairing form** is in two places, the printer details and the
Send step (the guide's choice 8): one field, "Pairing code", taking capitals or small
letters with or without the hyphen; a **Pair** button; a link, "How to pair a printer", to
a documentation page written in phase 5 (fake 22). The Send step's message, the wizard's:
"No printer is paired with PenguinSlicer, so nothing can be sent. Anyone in 6238 (Popcorn
Penguins) can pair one: start the PenguinSlicer program on the computer beside the printer
and type the code it shows. Meanwhile, download the file and print it from Orca Slicer or
Bambu Studio."

| What happens | What the user sees |
|---|---|
| A daemon is showing the code | The form goes; a notification: "Paired with Shop H2S. Everyone in 6238 (Popcorn Penguins) can now send to it."; the icon shows the grey dot and "…" until the daemon first reports, within about half a minute |
| No daemon is showing that code | At once, in red under the field, printer delivery's sentence, of the kind "No computer beside a printer is showing that code right now. Check the code and try again in a moment." The one answer to every wrong code (mistyped, run out, used), and to a right code typed in the half minute after a front server restart |
| Too many wrong codes from this user (`delivery.rate_limited`) | Field and button off, with printer delivery's sentence, of the kind "Too many wrong codes. Wait a minute, then try again." |

**Unpairing.** **Unpair this printer** asks in a confirmation: "Unpair Shop H2S? Nobody in
6238 (Popcorn Penguins) can send to it until it is paired again." with **Unpair** and Keep.
While a print PenguinSlicer is following is going on, the link is off with the line "Shop
H2S is printing; unpair it when the print has ended." After unpairing the icon says No
printer. Any user of the group may pair and unpair.

Open: the limit on wrong codes, proposed by printer delivery at ten a minute for each user
([The limit on wrong pairing codes](README.md#the-limit-on-wrong-pairing-codes)); show its
sentence as it is. Open: whether the relay itself refuses an unpairing during a print
([Unpairing while a delivery job has not ended](../delivery/README.md#unpairing-while-a-delivery-job-has-not-ended)).
Open: pairing again while paired, and a pairing that never finishes
([Pairing again: three cases](../delivery/README.md#pairing-again-three-cases)). Open: what
the printer's required mode costs a group, for the how-to page
([The printer's required mode](../delivery/README.md#the-printers-required-mode)). Open:
where the printer's name comes from
([Where the name of the printer comes from](README.md#where-the-name-of-the-printer-comes-from)).

### What printer delivery reports, through the front server

- **Offline, and for how long.** The relay notes the time of the daemon's last sync in the
  paired-printer record when it goes offline, one write at that moment, and the printer's
  status returns it, so "Not heard from for 7 minutes." is true after a restart of the
  front server. A daemon silent from before such a restart, with no time noted, is
  answered as silent for at least the time since the front server started, and the page
  says "at least" ([the contract](../contracts/wizard-front-server.md#printers-from-phase-5)).
- **A printing printer.** The relay refuses a send to a printer that is printing, whoever
  started it. [D174]
- **Stale and Stop following** [D177]; **the last print**, a delivery job's record kept for
  a day after it ends [D158].
- **Who sent a print, what it is, and how the last one ended:** the sender's display name,
  a one-line description of the plate, the time the delivery job ended and, for a failure,
  its layer ([printer delivery](../delivery/README-details.md#from-the-wizards-mockup)).
  Open: who writes the one-line description
  ([Who writes the one-line description of a plate](README.md#who-writes-the-one-line-description-of-a-plate));
  *proposed*, the front server.
- **The user's own delivery job and last print,** asked of the front server by a returning
  page, since the browser's storage holds no delivery job's id
  ([the contract](../contracts/wizard-front-server.md#printers-from-phase-5); its routes
  are not written yet).
- **A send repeated** because its first answer was lost must not start a second print; the
  means is proposed on both sides
  ([the contract](../contracts/wizard-front-server.md#every-request-and-every-answer)).

## What a returning page does

A page that has lost what it had in memory (a refresh, a closed and reopened panel, a
laptop opened the next morning) reads its plate from the browser's storage, asks the front
server about the plate's slice job [D99] and, from phase 5, the user's live delivery job
and last print, and opens where the user will want to be. The rows are tried in order; the
first that applies decides.

| What the page finds | Where it opens, and what it says | Source |
|---|---|---|
| The plate has a print, running or ended (phase 5), and its sliced file is still kept | The Send step. While it runs, a notification: "Back where you were. You had sent your plate to Shop H2S before you left; its progress is below.", which goes when the print ends. After it finished: the last-print note. After it failed: the failure on the print card. Send enabled again for the same sliced plate while the file is kept | [D107]; [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), departed from |
| Parts, and no slice yet | The stored step (Parts, Settings or Layout), the plate as it was. Nothing is said | Departs from [decision 47](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work) |
| The slice is waiting or running | The Preview step with its progress; a notification: "Back where you were. Your plate was still slicing when you left; see below." | [D101]; [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work) |
| The slice finished, its sliced file in the state bucket | The Preview step with the result; a notification: "Back where you were. Your plate was sliced and ready to send when you left." | [D102]; [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work) |
| The slice ended in an error | The Preview step with the failure's message, as if the page had stayed open | [D104] |
| Cancelled by a later slice of the same user | The Preview step with [the message for a slice stopped from another tab](#stopped-by-a-slice-from-another-tab) and Slice again; it does not submit by itself | [D105] |
| Unknown to the front server, submitted less than two hours ago: the slice container restarted | The Preview step; the page uploads the parts and submits the plate again, unasked; the slicing card starts from the beginning | [D103, D337, D217] |
| The front server reports the sliced file expired, or the slice is unknown and was submitted more than two hours ago | The Parts step, empty, with one notification: "The slice of your earlier plate has expired; add its parts again to print it." The stored parts are dropped | [D106]; [decision 48](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), M18 |

- The page tells the two "unknown" rows apart by the time it kept when it submitted
  (`SLICED_FILE_KEEP_S`), not by anything the front server says. (*Proposed*:) a page
  opened more than two hours after it submitted treats an unknown slice job as expired even
  when a restart of the slice container, not age, made it unknown.
- A plate with a print is held by the first row longer than two hours from its slice, since
  a print keeps its sliced file until two hours after the print ends; the page drops such a
  plate only when the front server reports the sliced file expired.
- A page that reloads itself after a deploy is a returning page, but shows no "Back where
  you were" ([Reloading on a newer version of the front server](#reloading-on-a-newer-version-of-the-front-server)).
- A slice container that restarts while a slice waits or runs loses that slice job: an
  open page uploads its parts again and submits the same plate, unasked; a closed page does
  so when next opened within two hours of its submission
  ([the architecture](../docs/architecture.md#what-a-restart-does)). [D217]
- Work does not follow a user to another computer or browser: there the wizard opens
  empty. [D108] The same holds between Onshape's panel and a tab.

Open: why the last row drops the parts while a page open at the expiry keeps them
([Parts dropped on return and kept while the page is open](README.md#parts-dropped-on-return-and-kept-while-the-page-is-open));
build the row as written.

### The user's last print

When the user's own print finishes, the **last-print note**, "Your print finished at
11:25 am.", a line and not a card: at the top of the Send step, above the Send of the same
plate or a new one, and, when the user comes back, on whichever step opens, until the user
leaves that step. It goes, with the printer details' "Last print finished…" line, when the
user sends another plate or `LAST_PRINT_NOTE_H` (12 hours) after the print finished,
whichever is first ([decision 60](../docs/mockups/print-wizard/DECISIONS.md#the-users-last-print-version-7)).
A failed print is not a line: it is the failure on the print card on the Send step.

Tests: every row of the table reached on purpose with the fake front server, the rows'
order checked (a plate with an ended print and an unknown slice job submitted three hours
ago opens on the Send step); the "unknown" rows split at exactly two hours on the fake
clock; the last-print note goes at 12 hours and on the next send.

## Reloading on a newer version of the front server

Every answer of the front server carries its version (*proposed*: a header,
`X-PenguinSlicer-Version`; [the front server](../front/README-details.md#the-version-on-every-answer)).
**A page that sees a newer version reloads itself at the next quiet moment,** which loses
nothing because its state is in the browser's storage. [D237, D339] A quiet moment is when:

- no request of the page's is waiting for its answer (an open progress stream does not
  count: the reloaded page reconnects and gets the latest report at once);
- no pointer is down, and no menu, joined box or confirmation is open;
- no field is being typed in;
- the user has touched nothing for `RELOAD_IDLE_S` (*proposed* 10 seconds without a pointer
  movement, a key or a scroll).

Until it reloads, the older page keeps working against the newer front server
([the architecture](../docs/architecture.md#old-and-new-versions-together)).

**What the user sees:** the panel redraws once, and nothing else: no message and no "Back
where you were", because the page notes in the browser's storage (*proposed* record
`selfReload`) that the reload was its own (the guide's choice 11). The page reopens on the
step it was on, in advanced mode if advanced mode was open, with the parts, the layout,
every change, a running slice's progress and a print's progress. What starts afresh is
only what lived in memory: advanced mode's sections and setting groups all open again, the
3D views at their starting camera, the Layout step's selection cleared, the layer bar at
the top layer, open joined boxes and notifications closed
([decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2)). Keep that
list short.

Tests (fake clock, fake front server announcing a newer version): no reload while a request
waits, a pointer is down, a menu is open or a field has focus; a reload at exactly 10 s of
no input and not at 9.9 s; after it, the stored step and advanced mode reopen and no
notification shows; a page loaded from the previous version's code runs against the new
fake front server.

## What the page keeps in the browser's storage

The browser's storage is the record of a user's parts and plate; nothing on a server is.
[D336] No restart of the front server or the slice container touches it.

| What (*proposed* record names) | Kept until |
|---|---|
| `parts`: each part's file exactly as it arrived, with its name, its units and its hash | The page, on opening, finds the plate's sliced file expired |
| `layout`: where each instance sits and how it is turned | The same |
| `settings`: the filament, the profile and every change | The same |
| `slice`: the plate's slice job id, and when the page submitted it | The same |
| `step`: the step the user is on, and whether advanced mode is open | The same |
| `group`: the current group | The user changes it |
| `selfReload`: that the next load is the page's own reload | The next load |

A plate never sliced has no sliced file to expire and stays until its rows are removed.
What lives only in the page's memory starts afresh on a reload: advanced mode's open
sections, the cameras, the selection, open joined boxes and notifications.
[D203: these lifetimes are the first row of the architecture's
[table of all the state](../docs/architecture.md#all-the-state-in-one-table).]

The part store keeps a copy of each part for two hours after its last use, but it is a
cache; the page uploads again any part the part store no longer has. [D77] The page never
stores a sliced file and never uploads one. [D86]

**Size.** The parts alone can reach 25 parts of up to 7.5 MB each, about 190 MB, so the
storage must hold that much for one page. (*Proposed*: IndexedDB, since the simpler
key-value storage of a page holds only a few megabytes.) Each change is written at once
(*proposed*), so a refresh at any moment loses nothing.

Open: what the page does when the browser refuses to store a part or clears the storage
([Whether the browser's storage reliably holds a full plate](README.md#whether-the-browsers-storage-reliably-holds-a-full-plate));
*proposed*, a part the browser refuses to store is still added and sliced, with an amber
line on its row, "This part could not be saved in this browser, so a refresh will lose
it.", and the refusal reported to the log. Open: stored work is not tied to a user
([Stored work is not tied to a user](README.md#stored-work-is-not-tied-to-a-user)); the
recommendation is that the stored work carries the user it belongs to and a page signed
in as someone else clears it, so store the user beside the work from the start. Open: two
tabs on one stored plate ([Two tabs on one stored plate](README.md#two-tabs-on-one-stored-plate)).

Tests: a full plate of 25 parts of 7.5 MB stored, the page reloaded, everything back; each
record survives a reload; a refused write, caused on purpose by a fake storage, is handled
as decided.

## Storage inside Onshape's panel, and storage in a tab

Chrome keeps the storage of a page inside Onshape's panel apart from the storage of the
same page opened directly, so work begun in the panel does not appear in a tab, nor the
reverse. [D109] Each is a returning page of its own. Since a user has one unfinished slice
job at a time, slicing in one cancels an unfinished slice in the other, which then shows
[Stopped by a slice from another tab](#stopped-by-a-slice-from-another-tab).

| | In a tab | In Onshape's panel |
|---|---|---|
| Parts come from | Uploaded STL files | A click on a part, through the Onshape integration |
| A part's units | The configuration's for uploads | The Part Studio's or Assembly's |
| Where to mend a broken part | "your CAD program" | "Onshape" |
| Sign-in | A trip to Onshape and back in the tab | The same, inside the panel |
| The browser's storage | The tab's own, shared with other tabs at the address | Kept apart from the tab's |
| Width | The window's | Whatever the user drags the panel to, from 320 px |

What only real Onshape can settle, in phase 4: signing in and staying signed in as an
embedded page, storage that survives the panel being closed and reopened, the mouse beside
Onshape's own gestures, the widths the panel really allows. Open:
[What only real Onshape can settle](README.md#what-only-real-onshape-can-settle) and
[the cookie inside Onshape's panel](../front/README.md#the-cookie-inside-onshapes-panel).

## Browsers supported

Chrome is proposed as the supported browser; Safari is not supported, in Onshape's panel
or outside it, and is shown the front server's plain page. [D146] Inside the panel,
sign-in and the stored parts depend on Chrome allowing cookies and storage to an embedded
page. [D147] The wizard works from 320 px and lays out wider when it has more room. Open:
[Browsers other than Chrome](README.md#browsers-other-than-chrome); *proposed*, Chrome
supported, Edge tested, Firefox neither tested nor blocked.

## Accessibility

Required, from the accepted screens:

- Everything outside the two 3D views can be reached and worked by keyboard, focus always
  visible: the step tabs, menus, quick changes, every row and button, the joined boxes and
  the confirmations (the accepted screens state it for the step circles, advanced mode,
  the printer-status icon and the Send button's menu; for the whole panel it is proposed).
- A tooltip appears at once on keyboard focus of an icon or step circle; nothing a user
  needs is in a tooltip alone.
- The printer-status icon gives a screen reader one sentence; the layer bar moves with the
  arrow keys and reports its layer.
- The Send button's menu: Enter on the caret opens it, arrow keys move, Escape closes.
- Colour never carries a meaning alone: a message has its sentence, the icon its word, a
  changed setting its dot and bar, and the layer preview's four colours were checked for
  the three common kinds of colour blindness.
- Text at 14 px or larger, the pointer line at 11 px the one exception; amber darkened to
  `#9a6700`.

Not required: the Layout step by keyboard and what a screen reader is told of the plate
(open: [The Layout step by keyboard](README.md#the-layout-step-by-keyboard)); a screen
reader's account of the layer preview beyond the layer bar; conformance to a published
standard.

Tests: every control outside the 3D views reached by Tab in order with visible focus; the
icon's sentence and the layer bar's layer read by the accessibility tree.

## Security

- **The browser holds no secret.** No key, token or pairing code in the page's code or in
  the browser's storage; the pairing code is typed once and dead after use. The cookie,
  encrypted with a key only the front server has, lasts thirty days; the page's code
  neither reads nor writes it.
- **The page never says who the user is.** The front server takes the user from the cookie;
  the page names the current group, accepted only if the cookie lists it.
- **The mark on every changing request** ([Signing in, and "sign in again"](#signing-in-and-sign-in-again)).
  [D140]
- **What the page trusts:** only the front server, at its own address. It loads no code,
  font or picture from any other site and makes no request to one.
- **What it treats as hostile:** a part's name, another user's name, a plate's
  description, a group's, profile's or printer's name, and an error report's sentences,
  all shown as text and never as markup; an uploaded file, whose reading is bounded by
  the size limit and ends, if malformed, in a notification and never in a frozen panel.
- **What a flaw would expose:** code run in the page could read the stored parts and
  start a print on the group's printer; it could not read the cookie or any server
  secret. Stored work not tied to a user is a gap, not an accepted risk (open, above).
- **Accepted risks:** parts unencrypted in the browser's storage until the page next opens
  after the sliced file has expired (a never-sliced plate until its rows are removed);
  users of one group see each other's names and what is printing; any user of a group can
  send a print or unpair from anywhere. Open: [Sign-out](README.md#sign-out).

Tests: hostile names and sentences (markup, scripts) render as text; no request leaves for
another origin (checked by the fake front server and the page's content security policy);
nothing secret is found in the browser's storage after pairing.

## Failures only the browser sees

A part the page cannot draw, storage refused or cleared, a lost 3D context, the layout code
failing on a part, the page's own code failing, and a sentence the page wrote itself reach
no server and so no log. The plan's standing requirement is that a failure can be
diagnosed from the server's log. Open:
[Failures in the browser that reach no log](README.md#failures-in-the-browser-that-reach-no-log);
the recommendation is a report to the front server (what failed, the step, the page's
version, the browser and its version, whether 3D is drawn in software, the part's hash;
never a part's bytes or geometry or the storage's contents), at most a few a minute from
one page, dropped and never retried if it cannot be sent. Until decided, give each such
failure a stable code of the wizard's own (*proposed* `wizard.<what>`, for instance
`wizard.part_undrawable`, `wizard.storage_refused`, `wizard.context_lost`) gathered in
one place, so that the report, once decided, is one call.

**Cancelling.** A slice can be cancelled at any moment from the slicing card, which stops
Orca and leaves the plate ready to slice again; a send until the relay allows the start; a
print only at the printer.

**A restart or a deploy** costs a user a pause and, with the one exception under
[Retrying every request](#retrying-every-request), nothing else: requests are retried,
progress streams reopen, nobody is signed out; the icon shows the grey dot and "…" and a
print card keeps its last figures until the daemon reports; a lost slice starts again by
itself.

## What the other components must provide

What the wizard asks of the front server, in words, is the guide's
[What the wizard asks of the front server](README.md#what-the-wizard-asks-of-the-front-server);
the contract will hold the routes. Three rules bind every request: every failure is an
error report shown as it is; every request is safe to repeat; a page loaded before a
deploy keeps working after it until it reloads.

Not provided yet, and needed by the wizard as designed:

| Needed | From | For |
|---|---|---|
| The moment a sliced file will be refused as expired, with the summary and again when a print of the plate ends. Open, the front server's ([Telling the page when a sliced file expires](../front/README.md#telling-the-page-when-a-sliced-file-expires)) | The front server, the contract | [A sliced plate that expires](#a-sliced-plate-that-expires) |
| A request reporting a failure only the browser saw. Open | The front server, the contract | [Failures only the browser sees](#failures-only-the-browser-sees) |
| Signing out, if the proposal stands. Open | The front server, the contract | A shared computer |
| A report telling a slice cancelled because the slice service was asked to stop (*proposed*: a reason on `slice.cancelled`) from one cancelled by the user or by a later slice | The slice service, the front server, the contract | [The slicing card](#the-slicing-card) starting again by itself |
| Units for each part in the plate configuration, applied by the slice service | The slice service, the plate configuration's contract | Parts in inches |
| Every parameter setting accepted as a change; as built, four are | The slice service | Advanced mode |
| The list of those settings, with kind, range, choices and each profile's value. Open | The slice service, through the front server (recommended) | Advanced mode, the changes box |
| Orca's sentence as a quotation on the two empty-layers failures, if decided so. Open | The slice service, the error report's contract | [Errors the wizard explains](#errors-the-wizard-explains) |
| Sentences that say "your CAD program" and never a role word or "the print server" | The slice service, printer delivery | [Who writes the sentences of a failure](#who-writes-the-sentences-of-a-failure) |
| A slice that runs on without its page, one unfinished slice for each user, parts kept and named by hash, a waiting slice's place | The slice service, phase 2 | The Preview step and coming back |
| Who sent a print, a one-line description, when the last print ended and who sent it, a failure's layer | Printer delivery, phase 5 | The printer details, the busy card, the last-print note |
| The signed-in user's running print and last print | Printer delivery, phase 5 | A returning page |
| The time a daemon went silent, kept across a front server restart | Printer delivery, phase 5 | "Not heard from for 7 minutes." |
| A print started at the printer reported as a print with no sender | Printer delivery, phase 5 | The busy card |
| An ending of a print no longer followed reported apart from a failure at the printer (recommended) | Printer delivery, phase 5 | [A print that has gone quiet, and Stop following](#a-print-that-has-gone-quiet-and-stop-following) |

## Performance targets

| Requirement | Figure | Status | Checked by |
|---|---|---|---|
| Narrowest panel | 320 px, no sideways scroll, nothing cut off | The plan | Every screen at 320 px, looked at |
| Tooltip delay; printer details close | 150 ms; 300 ms | The mockup | Fake clock |
| Quiet retrying; retrying in all | 20 s; 300 s, waits doubling 1 to 30 s | The architecture; waits proposed | Fake clock |
| A part's row says it is slow | 4 s | The mockup | Fake clock |
| One part; different parts; instances | 7.5 MB (150,000 triangles); 25; 150 | Someone else's | One over each |
| Storage in the browser | 25 parts of 7.5 MB | Follows from the limits | A full plate stored and reloaded |
| Faces found | Patches within 100 ms of selecting, the panel never frozen longer | Proposed; 0.2 to 10 ms on generated parts of up to 1,744 corners | Timed on real exported parts |
| Auto-orient | Best way within 1 s of arriving | Proposed; about 0.1 s for 100,004 triangles outside a browser | The same |
| Arrange | Under 2 s for 150 instances, the panel not frozen | Proposed; 0.2 to 1.5 s for up to 25, unoptimised | The same |
| The placement check | Keeps up with a drag at 150 instances | Proposed; unmeasured | The same |
| The Layout view | At least 30 frames a second dragging or turning with a graphics card, 10 without, at 150 instances of parts up to 150,000 triangles, on the layer preview's proposed machines | Proposed, no measurement | Timed in a real browser on both machines |
| The page's memory | Under 1 GB at the largest plate with the layer preview of a 14.1 MB sliced file open | Proposed; unmeasured | Measured in a real browser |
| The layer preview | [The measurement](#the-layer-preview) | Proposed | Timing and test renders |
| Idle before a self-reload | 10 s | Proposed | Fake clock |
| A silent progress stream | A comment line at least every 15 s from the front server; reopened whenever it closes | Someone else's | Fake front server closing at chosen moments |

## How it is tested

The project's rules, applied in the browser:

- **No test waits.** Every timer reads the fake clock, which the test moves: the 150 ms of
  a tooltip, the 4, 20 and 300 seconds of retrying, the 10 seconds before a self-reload,
  the 40 seconds and two minutes of a quiet printer, the two hours of a sliced file and the
  12 hours of a last-print note are each tested in an instant. A test waits on an event,
  never on a duration.
- **The front server is the fake front server.** Everything that depends on the order of
  events over the network is put in an exact order by it: an answer lost and the request
  repeated, a progress stream closed mid-slice, a slice cancelled from another tab, a part
  the slice service has forgotten, a newer version announced while a request waits.
- **Every row is a test.** Each row of each table in this file that describes a state or a
  message has a test that reaches it on purpose and checks what the user sees.
- **Another component's sentences are shown unchanged** (see
  [Who writes the sentences of a failure](#who-writes-the-sentences-of-a-failure)).
- **The geometry is tested on real parts,** without a browser window, against written-down
  expectations, and the placement check against the slice service's.
- **The previous version's page runs against the new front server**, as the architecture
  requires of every change.
- The suites use no real front server, no fixed ports, and pass in any order, any number
  of times.

What such tests cannot prove: that the layer preview looks right (a person looks at the
test renders); that the views are fast enough (timing in Chrome on the two proposed
machines); sign-in, storage and the mouse inside Onshape's panel (real Onshape, phase 4);
what the printer reports (the real printer, phase 5); that progress passes the hosts
unheld (the hosted service, phase 3).

## By phase

The plan puts retrying and reloading in phase 2, since the restarts tested there need
them, and the mark on every changing request, checked from then on, in phase 3, as
[the front server's details](../front/README-details.md#by-phase) do for the check.

| Phase | What of the wizard is built |
|---|---|
| 2, one machine | The page opened directly in a browser, with the development identity and no sign-in. The panel, the header with the current group and the group details, and all five steps: parts from STL files and the limits; the Settings step and advanced mode; the Layout step with laying on a face, auto-orient, Arrange and the placement check; the Preview step with slicing, every slice failure, the result and the layer preview; the Send step with Download as its one button (the plan gives the Send step to phase 5 and only the download to phase 2: the guide's choice 12). The browser's storage, uploading each part once, submitting by hash and uploading missing parts again, one unfinished slice job, the returning page, progress streams and reconnecting, retrying, reloading on a newer version, reading the configuration |
| 3, hosted on Railway | Onshape sign-in, a sign-in that failed or ran out, Sign in again; the mark on every changing request, checked from here on |
| 4, inside Onshape | The page in Onshape's panel, with parts picked in Onshape and their units; its storage kept apart from a tab's |
| 5, the real printer | The printer-status icon and the printer details; pairing and unpairing; Send, the print card, the busy card, Cancel sending, Stop following; the last-print note; the returning page on the Send step |

## Where this guide departs from the mockup's decisions

Whoever builds from [the mockup's decisions](../docs/mockups/print-wizard/DECISIONS.md)
follows the guide where the two differ, in these places. Each departure is stated in the
guide and, for the points the decisions of Fri 2026-11-27 confirmed (items 15 and 16), is
confirmed there.

| The mockup's decision | What the mockup says | What the guide says |
|---|---|---|
| [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms), "configuration" | The configuration holds the printer | The paired-printer record links the group to its printer and holds its display name; the configuration names the printer's Orca profile, from which the plate's size and height come ([The configuration](#the-configuration)) |
| [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms), "group" | A collapsible set of settings in advanced mode | "Setting group"; "group" is the users who share a configuration and a printer ([Terms used below](#terms-used-below)) |
| [The Terms](../docs/mockups/print-wizard/DECISIONS.md#terms), "administrator"; [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step) | An administrator pairs the printer, once, from the computer beside it | Any signed-in user of the group types the pairing code, from any computer ([Pairing a printer](#pairing-a-printer)) |
| [decision 58](../docs/mockups/print-wizard/DECISIONS.md#words-on-the-panel-version-6) | Where a permission matters, the word is "administrator" | No sentence sends the user to an administrator; nothing distinguishes one user of a group from another ([The words it uses](#the-words-it-uses)) |
| [decision 42](../docs/mockups/print-wizard/DECISIONS.md#send-step), [decision 44](../docs/mockups/print-wizard/DECISIONS.md#the-printer-status-icon) | With no printer paired, a message and the "How to pair a printer" link | The pairing form itself, in the printer details and on the Send step, with that link ([Pairing a printer](#pairing-a-printer)) |
| [decision 13](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2) | Advanced mode's changes last for this page load | The changes are in the browser's storage and outlast a refresh; only the open and closed sections live in memory ([Advanced mode](#advanced-mode)) |
| Fake 13 ([its list](../docs/mockups/print-wizard/DECISIONS.md#what-is-fake-and-could-mislead)) | Advanced mode shows a sample of 99 settings | Every parameter setting of Orca's, less the programmatic ones ([Advanced mode](#advanced-mode)) |
| [decision 17](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) | After 20 seconds of failed retries, a notification that the part was not added, to be clicked in Onshape again (or uploaded again) | Quiet retries; after 20 seconds the panel line saying the server is slow and the browser is retrying, with a countdown and Retry now, the waits growing; up to 300 seconds, then "The server could not be reached." with Try again; nothing of the work dropped, the part keeps its row ([Retrying every request](#retrying-every-request)) |
| [decision 22](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1) | Quantities clamp at 150 | One part's quantity clamps at 150; parts that together pass 150 get a red message and Next is off ([The limits on a plate](#the-limits-on-a-plate)) |
| [decision 51](../docs/mockups/print-wizard/DECISIONS.md#units-version-6) | A 3MF file states its own units; the upload area names STL and 3MF | Binary STL only; a text STL or a 3MF is refused by the slice service (open: [Files other than binary STL](README.md#files-other-than-binary-stl)) |
| [decision 32](../docs/mockups/print-wizard/DECISIONS.md#preview-step) | A timeout suggests a profile with thicker layers; the empty-layers Details quote Orca's sentence | Every failure's sentences are the slice service's, shown as they are (for a timeout today: fewer instances or a second plate); Orca's sentence under Details is open ([Errors the wizard explains](#errors-the-wizard-explains)) |
| [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step); [Requirements on printer delivery](../docs/mockups/print-wizard/DECISIONS.md#requirements-on-printer-delivery), on the configuration | No colour for each filament | The configuration holds a colour for each filament, shown in the Filament menu and never in the layer preview ([The configuration](#the-configuration)) |
| [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step), "How the view draws" | The layer preview drawn by the mockup's method, settled by its test renders | The guide states what must be achieved, the appearance, the four requirements and a proposed measurement; the method is found while building ([The layer preview](#the-layer-preview)) |
| [decision 33](../docs/mockups/print-wizard/DECISIONS.md#preview-step), requirement 3 | No combs and no show-through at any viewing angle | *Proposed*, awaiting the owner's yes: the look may be simplified while the view moves, the full look within one second of rest ([The layer preview](#the-layer-preview)) |
| [decision 45](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), [decision 47](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work); [the requirement on the slice service](../docs/mockups/print-wizard/DECISIONS.md#requirements-on-printer-delivery) | A refresh throws the page's state away; the server finds the user's slice job and restores the parts and layout; with no slice job, an empty Parts step | The browser's storage keeps the parts, layout, settings, step and the slice job's id; a page with parts and no slice opens on the stored step; work does not follow to another browser ([What a returning page does](#what-a-returning-page-does)) |
| [decision 46](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), [decision 47](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work), [decision 48](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work) | The Send step only for a running delivery job; otherwise the Parts step; a failed print a notification on the Parts step, the parts not kept | A page whose stored plate has a delivery job, running or ended, opens on the Send step while the plate is stored; a failed print is the failure on the print card; once the plate is gone, the Parts step ([What a returning page does](#what-a-returning-page-does)) |
| [decision 48](../docs/mockups/print-wizard/DECISIONS.md#coming-back-to-running-work); M18 | A finished unsent slice is gone after two hours away | A sliced file is kept until two hours after its slice ended or after its last print ended, whichever is later ([The sliced file](#the-sliced-file)) |
| Fake 9 | A "plate too large" error against a cap on a plate's volume | No such error; a plate too heavy ends as out of memory or too slow ([Errors the wizard explains](#errors-the-wizard-explains)) |
| Fake 25 | The page outside Onshape opens the configuration from a saved link; the configuration's name links nowhere | The configuration is the signed-in user's current group's; the name opens the group details ([The current group](#the-current-group)) |

**Points that agree with the mockup.** The other recommendations the decisions of Fri
2026-11-27 confirmed (item 15) state what the mockup already decided: a part that cannot
be used is a notification and is not added
([decision 16](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1),
[decision 19](../docs/mockups/print-wizard/DECISIONS.md#parts-step-step-1)); each profile
has the group's own name and its purpose as tooltip
([decision 10](../docs/mockups/print-wizard/DECISIONS.md#settings-step-step-2)). The
mockup's questions ([Please react to these](../docs/mockups/print-wizard/DECISIONS.md#please-react-to-these);
item 16) are answered as the mockup has them: M1, faces on the hull; M2, the mouse like
Onshape; M3, parts arrive lying their best way; M6, two buttons and Arrange never turns
([decision 64](../docs/mockups/print-wizard/DECISIONS.md#arrange-spacing-version-6)); M16,
no layout tools beyond the mockup's; M17, leaving the Preview step does not stop the
slice; M29, the bounding-box rule unchanged, end patches included, the 30 degrees to tune;
M7, M11, M21, M22, M23, M25, M26 and the 11 px pointer line as the mockup has them. M18
is the departure above.

## Screens the design needs that the mockup does not show

The twelve screens the design needs and the mockup never showed (the decisions of Fri
2026-11-27, item 17) are designed in words in the guide, following the mockup's patterns,
with no mockup first. The guide adds two more written as the design and five that are only
proposed: nineteen in all, as its table
[Designed here and not in the mockup](README.md#designed-here-and-not-in-the-mockup) lists
them. The numbers 3.1 to 3.12 are those of
[the comparison of the mockup with the design](../docs/orchestration/hosted-architecture/mockup-against-design.md).
Each is specified in this file where the last column says, and each gets the tests of its
section.

| | The screen or state | The guide | This file |
|---|---|---|---|
| 3.1 | Signing in, a sign-in that failed, a sign-in that has run out | [Signing in](README.md#signing-in) | [Signing in, and "sign in again"](#signing-in-and-sign-in-again) |
| 3.2 | The group details, changing the current group, Sign in again, a group the user no longer belongs to, a filament or profile gone on reading the configuration again | [The current group](README.md#the-current-group) | [The current group](#the-current-group) |
| 3.3 | A sliced plate that expires while the page is open | [A sliced plate that expires](README.md#a-sliced-plate-that-expires) | [A sliced plate that expires](#a-sliced-plate-that-expires) |
| 3.4 | A slice waiting behind others, and no room to wait | [Slicing](README.md#slicing) | [The slicing card](#the-slicing-card), [No room to wait](#no-room-to-wait) |
| 3.5 | The pairing form, a wrong code, too many wrong codes, unpairing | [Pairing a printer](README.md#pairing-a-printer) | [Pairing a printer](#pairing-a-printer) |
| 3.6 | A print gone quiet, one gone quiet at a printer that is Offline, Stop following | [A print that has gone quiet](README.md#a-print-that-has-gone-quiet) | [A print that has gone quiet, and Stop following](#a-print-that-has-gone-quiet-and-stop-following) |
| 3.7 | The page reloading itself for a new version | [The page reloading itself](README.md#the-page-reloading-itself-for-a-new-version) | [Reloading on a newer version of the front server](#reloading-on-a-newer-version-of-the-front-server) |
| 3.8 | A slice stopped by a later one from another tab | [Slicing](README.md#slicing) | [Stopped by a slice from another tab](#stopped-by-a-slice-from-another-tab) |
| 3.9 | What a restart shows: the slicing card starting again, a printer not heard from yet | [Slicing](README.md#slicing), [The printer-status icon](README.md#the-printer-status-icon) | [The slicing card](#the-slicing-card), [The printer-status icon](#the-printer-status-icon) |
| 3.10 | A printer busy with a print nobody sent from PenguinSlicer | [When Send is not offered](README.md#when-send-is-not-offered) | [When Send is not offered](#when-send-is-not-offered) |
| 3.11 | The limits on parts: 7.5 MB, 25 different parts, 150 instances | [The limits on a plate](README.md#the-limits-on-a-plate) | [The limits on a plate](#the-limits-on-a-plate) |
| 3.12 | Running out of memory | [When a slice fails](README.md#when-a-slice-fails) | [Errors the wizard explains](#errors-the-wizard-explains) |
| | The retry message with its countdown, on the panel line | [When the server is slow](README.md#when-the-server-is-slow-or-cannot-be-reached) | [Retrying every request](#retrying-every-request) |
| | The Send step before there is a printer, Download its button | [The Send step](README.md#the-send-step) | [The Send step](#the-send-step) |
| | Proposed: a confirmation | [How the panel tells the user something](README.md#how-the-panel-tells-the-user-something) | [How the panel tells the user something](#how-the-panel-tells-the-user-something) |
| | Proposed: a configuration that cannot be read | [A configuration that cannot be read](README.md#a-configuration-that-cannot-be-read) | [The current group](#the-current-group) |
| | Proposed: a part the slice service accepts and the page cannot draw | [Failures in the browser that reach no log](README.md#failures-in-the-browser-that-reach-no-log) | [A part that cannot be used](#a-part-that-cannot-be-used) |
| | Proposed: the icon and the printer details after a print is no longer followed | [After a print is no longer followed](README.md#after-a-print-is-no-longer-followed) | [A print that has gone quiet, and Stop following](#a-print-that-has-gone-quiet-and-stop-following) |
| | Proposed: a part the browser refuses to store | [Whether the browser's storage reliably holds a full plate](README.md#whether-the-browsers-storage-reliably-holds-a-full-plate) | [What the page keeps in the browser's storage](#what-the-page-keeps-in-the-browsers-storage) |

**The guide's choices in designing them**, each written as the design, listed in
[Choices made in designing these screens](README.md#choices-made-in-designing-these-screens)
with its alternative: 1, a sign-in that has run out is a message with a button; 2, Sign in
again inside the group details; 3, changing the group clears changes and the slice and keeps
parts and layout; 4, the retry message on the panel line with Retry now; 5, an expired
sliced plate on an open page is a grey message with Slice again; 6, no room to wait is
amber with Slice again and no retry; 7, no Slice again after out of memory; 8, the pairing
form in two places; 9, Stop following and Unpair for every user, Unpair off during a
followed print; 10, the grey dot and "…" for a printer not heard from yet; 11, a silent
self-reload after ten idle seconds; 12, the Send step from phase 2. The smaller rules it
proposes, each marked *proposed* where it stands in this file: the form of a confirmation,
which use of the panel line wins, the waits between retries, a part the page cannot draw,
Back to Settings for a profile or setting not accepted, the stages under the print card's
track, a followed print's rows winning over Offline, and the ten seconds before a
self-reload; and two written as the design with no source: taking the first group when the
stored one is refused, and the reminder of how STL files are read after a too-large upload.

## Open items

Every undecided or unmeasured item of the guide that bears on building the wizard, each
named in one line where it bears in the body above as well:

- [The risks to try first in phase 2](README.md#the-risks-to-try-first-in-phase-2): the
  layer preview's speed without a graphics card; the geometry on real exported parts.
- [The layer preview's frame rate, browser and machine](README.md#the-layer-previews-frame-rate-browser-and-machine),
  with the look while moving awaiting the owner's yes.
- [Orca's own sentence under Details](README.md#orcas-own-sentence-under-details).
- [Two tabs on one stored plate](README.md#two-tabs-on-one-stored-plate).
- [Stored work is not tied to a user](README.md#stored-work-is-not-tied-to-a-user).
- [A progress stream that cannot be reopened](README.md#a-progress-stream-that-cannot-be-reopened).
- [Failures in the browser that reach no log](README.md#failures-in-the-browser-that-reach-no-log).
- [STL files in millimetres before the edit screens exist](README.md#stl-files-in-millimetres-before-the-edit-screens-exist).
- [Starting a second plate](README.md#starting-a-second-plate).
- [A configuration that cannot be read](README.md#a-configuration-that-cannot-be-read).
- [After a print is no longer followed](README.md#after-a-print-is-no-longer-followed).
- [Parts dropped on return and kept while the page is open](README.md#parts-dropped-on-return-and-kept-while-the-page-is-open).
- [The Layout step by keyboard](README.md#the-layout-step-by-keyboard).
- [Where the name of the printer comes from](README.md#where-the-name-of-the-printer-comes-from).
- [Where advanced mode's settings come from](README.md#where-advanced-modes-settings-come-from).
- [Files other than binary STL](README.md#files-other-than-binary-stl).
- [Sign-out](README.md#sign-out).
- [Agreement between the placement check of the wizard and of the slice service](README.md#agreement-between-the-placement-check-of-the-wizard-and-of-the-slice-service).
- [Saying that a part will need supports](README.md#saying-that-a-part-will-need-supports).
- [The limit on wrong pairing codes](README.md#the-limit-on-wrong-pairing-codes).
- [Who writes the one-line description of a plate](README.md#who-writes-the-one-line-description-of-a-plate).
- [Browsers other than Chrome](README.md#browsers-other-than-chrome).
- [What only real Onshape can settle](README.md#what-only-real-onshape-can-settle).
- [Whether the browser's storage reliably holds a full plate](README.md#whether-the-browsers-storage-reliably-holds-a-full-plate).
- [Whether progress reaches the page unheld when hosted](README.md#whether-progress-reaches-the-page-unheld-when-hosted).
- [Open items of the other guides that would change the panel](README.md#open-items-of-the-other-guides-that-would-change-the-panel):
  a plate configuration submitted twice, following a print without a progress stream,
  pairing again, an old daemon, the printer's required mode, who may sign in.
- The moment a sliced file expires, not yet in the contract
  ([What the wizard asks of the front server](README.md#what-the-wizard-asks-of-the-front-server)).
- Railway's limit on a request body, settled by one real upload of a 7.5 MB part
  ([the architecture](../docs/architecture.md#to-confirm-before-building-on-it)).
- What a user sees while the slice service stops for a deploy
  ([When the server is slow or cannot be reached](README.md#when-the-server-is-slow-or-cannot-be-reached)).
- How often one user may use Sign in again
  ([The current group](README.md#the-current-group)).
- Unpairing during a print: whether the relay refuses it
  ([Pairing a printer](README.md#pairing-a-printer)).
