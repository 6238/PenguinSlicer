# The wizard: the design, begun

Nothing of the wizard is built. This document is its design, written for whoever builds
it, and it is begun, not complete. What is here: everything
[the architecture](../docs/architecture.md) asks of the code in the browser; where this
guide departs from the wizard's approved mockup; and the screens the design needs that
the mockup does not show. What is still to be written: the steps a user
sees (every screen, message and decision of the Parts, Settings, Layout, Preview and Send
steps and of the printer-status icon), from
[the mockup's decisions](../docs/mockups/print-wizard/DECISIONS.md); see
[Still to be written](#still-to-be-written). The guide for a human reader is
[README.md](README.md).

The **wizard** is the code in the browser: the step-by-step user interface. It talks only
to the **front server**, a separate component in `front/`
([its guide](../front/README.md)), which serves the wizard's pages and stands between the
browser and everything else. What passes between the two is to be fixed in
[the contract between the wizard and the front server](../contracts/wizard-front-server.md),
which says what it must provide; its routes are not written yet. [D362] The phases are
those of [the plan](../docs/plans/penguin-slicer-plan.md): phase 2, one machine; phase 3,
hosted on Railway; phase 4, inside Onshape; phase 5, the real printer.

The ids in brackets name the decisions in
[the map of the hosted architecture's decisions](../docs/orchestration/hosted-architecture/decision-map.md);
the numbered decisions ("decision 17") and questions ("M18") are those of the mockup's
decisions, version 8, which the owner approved on Thu 2026-11-26. "The design" below is
the hosted architecture design the owner approved on Thu 2026-11-26, whose content
[the architecture](../docs/architecture.md) now holds.

Names and figures marked *proposed* below are this guide's suggestions; the design
approved by the owner does not fix them, and the phase's design spec settles them.

## Contents

- [Terms used below](#terms-used-below)
- [What the page keeps in the browser's storage](#what-the-page-keeps-in-the-browsers-storage)
- [Uploading each part when it is added](#uploading-each-part-when-it-is-added)
- [Submitting a plate configuration](#submitting-a-plate-configuration)
- [One unfinished slice job at a time](#one-unfinished-slice-job-at-a-time)
- [What a returning page does](#what-a-returning-page-does)
- [Following progress, and reconnecting](#following-progress-and-reconnecting)
- [Errors the wizard explains](#errors-the-wizard-explains)
- [Retrying every request](#retrying-every-request)
- [Reloading on a newer version of the front server](#reloading-on-a-newer-version-of-the-front-server)
- [Signing in, and "sign in again"](#signing-in-and-sign-in-again)
- [The current group](#the-current-group)
- [The configuration](#the-configuration)
- [The sliced file](#the-sliced-file)
- [Printers, from phase 5](#printers-from-phase-5)
- [Storage inside Onshape's panel, and storage in a tab](#storage-inside-onshapes-panel-and-storage-in-a-tab)
- [Browsers supported](#browsers-supported)
- [By phase](#by-phase)
- [Where this guide departs from the mockup's decisions](#where-this-guide-departs-from-the-mockups-decisions)
- [Screens the design needs that the mockup does not show](#screens-the-design-needs-that-the-mockup-does-not-show)
- [Still to be written](#still-to-be-written)

## Terms used below

The plan's terms ([the plan](../docs/plans/penguin-slicer-plan.md#terms)) and the
architecture's ([the architecture](../docs/architecture.md#terms)) hold here. The ones this
document leans on:

- The **page** is the wizard as loaded in one browser tab, or in Onshape's panel.
- The **browser's storage** is the storage a browser gives a page that outlasts a refresh
  and a closed tab. It is kept for each browser, and for each address the page is opened
  at.
- A **group** is the users who share one configuration and one printer: one Onshape
  company or classroom, or a user alone who belongs to none. The **current group** is the
  one group, of those a user belongs to, whose configuration and printer the user is
  using now.
- The **part store** is the slice service's folder of uploaded parts, each kept for two
  hours after it was last used. It is a cache.
- The **user key** is the signed-in user's Onshape id, which the front server takes from
  the sign-in cookie and passes to the slice service. The browser never names one.
- A **slice job** is one plate configuration being sliced by the slice service; a
  **delivery job** is one sliced file on its way to one printer.
- A **progress stream** is the connection, of server-sent events, on which a page follows
  a slice job or a delivery job.
- The **state bucket** is the object store where the front server keeps what must outlast
  its restart: each group's configuration and paired-printer record, the sliced files and
  the records of delivery jobs. The **paired-printer record** is the one document per
  group that names the group's daemon.
- An **error report** and a **progress report** are the one shapes in which every
  component reports a failure and how far a long job has got
  ([error report](../contracts/error-report.md),
  [progress report](../contracts/progress-report.md)).

## What the page keeps in the browser's storage

The browser's storage is the record of a user's parts and plate; nothing on the server is.
The page keeps there:

| What | Kept until |
|---|---|
| The parts (each part's file, as added) | The page, on opening, finds the plate's sliced file expired |
| The layout (where each instance sits and how it is turned) | The same |
| The chosen settings (filament, profile and every change) | The same |
| The id of the plate's slice job, and the time the page submitted it | The same |
| The current group | The user changes it |

[D336] No restart of the front server or the slice container touches any of it. So a
refresh, a closed and reopened panel or a reload brings back the parts, the layout and
the chosen settings, with every change made on the Settings step or in advanced mode; a
reload that dropped them would lose work at every deploy, since the page reloads itself
after each one. What lives only in the page's memory, such as which of advanced mode's
sections are open, starts afresh.
[D203: these lifetimes are the first row of the architecture's
[table of all the state](../docs/architecture.md#all-the-state-in-one-table).]

The part store keeps a copy of each part for two hours after its last use, but it is a
cache: the browser's storage is the record of a user's parts, and the page uploads any
part again that the part store no longer has
([the slice service](../slice/README.md)). [D77]

The page never stores a sliced file and never uploads one. It fetches the sliced file
through the front server each time it needs it, so a printer only ever receives a file the
slice service made. [D86]

The parts alone can reach 25 parts of up to 7.5 MB each, the most a plate can use, so
(*proposed*) the storage the builder chooses must hold that much for one page.

## Uploading each part when it is added

The wizard uploads each part by itself, at the moment the user adds it, in one request of
at most 7.5 MB (7,500,084 bytes, the plate configuration's limit for one part,
`MAX_PART_BYTES` in [the plate configuration](../contracts/plate-configuration.md#limits)).
That is far under the 100 MB that Cloudflare allows a request. [D70] Railway's own limit
on a request body is not stated in its documents; one real upload of a 7.5 MB part settles
it ([the architecture](../docs/architecture.md#to-confirm-before-building-on-it)).

The page keeps the part in the browser's storage and uploads it; the front server passes it
to the slice service with the user key, and the slice service keeps it in the part store
under the user key and the SHA-256 hash of its bytes. (*Proposed*, as in
[the slice service's guide](../slice/README-details.md#to-be-built):) the answer gives the
page that hash, which the page keeps beside the part.

The slice service runs its checks on the part as it arrives, so a part that cannot be
sliced is refused on the Parts step, before the user has laid anything out
([the slice service](../slice/README.md)). [D74] The page shows the refusal as a
notification naming the part and does not add the part, as it does for a part Onshape
cannot export and for a file that cannot be read, so the list holds only usable parts.
(*Proposed*:) a part larger than 7.5 MB is refused by the slice service before it is read.

A part whose upload gets no answer is not refused: the page retries it
([Retrying every request](#retrying-every-request)), and its row stays in the list, since
the part is in the browser's storage from the moment it is added.

## Submitting a plate configuration

On the Preview step the page sends the front server a **plate configuration**: the layout,
the chosen settings and the SHA-256 hash of each part, with no files, because the parts are
already in the part store ([the plate configuration](../contracts/plate-configuration.md)).
[D73] So slicing again uploads nothing: a user who looks at the preview, changes a setting
or moves a part, and slices again sends only a small plate configuration each time. [D75]

When the plate configuration names a part no longer in the part store, the answer is an
error report (*proposed*: `slice.part_missing`, action `refresh_parts`) listing every
missing hash.
The page then uploads those parts again from the browser's storage and submits the same
plate configuration again, and the user sees nothing of it. [D79] A part leaves the part
store two hours after its last use, when the part store's limits push it out (at most 25
parts for one user key; when a twenty-sixth arrives, the least recently used one goes), and
whenever the slice container restarts, since the slice service empties the part store when
it starts ([the slice service](../slice/README.md)).

The page keeps the id of the slice job the answer gives, and the time it submitted it, in
the browser's storage.

## One unfinished slice job at a time

A user has one unfinished slice job at a time: submitting a plate cancels the user's
earlier unfinished slice job, which is what the Preview step does when a plate changes
([the slice service](../slice/README.md)). With the wizard open in two tabs, the later
slice wins ([the slice service](../slice/README.md)). [D98] The page whose slice job was
cancelled this way learns it (*proposed*: from its progress stream's final report, or when
it next asks) as "cancelled by a later slice of the same user"; it shows the plate on the Preview step and offers to
slice it, and does not submit by itself, so two pages cannot cancel each other in turn
([What a returning page does](#what-a-returning-page-does)).

Once submitted, a slice job runs to its end whether or not anything follows it: through a
refresh, a dropped connection or a closed lid. So leaving the Preview step while it slices
leaves the slice running, and coming back with the same plate shows it still going or
finished; a changed plate submits a new one, which cancels the old.

## What a returning page does

A page that has lost its state (a refresh, a closed and reopened panel, a reload) reads the
parts, the layout, the chosen settings, the id of the plate's slice job and the time it was
submitted from the browser's storage, and asks the front server about that slice job.
[D99] The slice service remembers a slice job for two hours after it ends, and a finished
one is also known by its sliced file in the state bucket
([the slice service](../slice/README.md)).

| The front server answers | The page |
|---|---|
| Still waiting or running | Shows its progress on the Preview step [D101] |
| Finished, and its sliced file is in the state bucket | Opens on the Preview step with the result [D102] |
| Unknown, and the page submitted it less than two hours ago: the slice container restarted | Uploads the parts and submits the plate again, unasked [D103, D337] |
| Ended in an error | Shows the error on the Preview step, as when the page was open [D104] |
| Cancelled by a later slice of the same user | Shows the plate on the Preview step and offers to slice it; it does not submit by itself, so two pages cannot cancel each other in turn [D105] |
| Unknown, and the page submitted it more than two hours ago: its sliced file has expired | Opens on the Parts step with one line saying the earlier plate's sliced file has expired (the mockup's decision 48), and drops the stored parts [D106] |

The page tells the two "unknown" rows apart by the time it kept, not by anything the
front server says. *Proposed*, since the approved design states both this rule and the
restart rule below and does not say which wins: a page opened more than two hours after
it submitted treats an unknown slice job as expired even when a restart of the slice container, not
age, made it unknown.

From phase 5, a returning page whose plate has a delivery job, running or ended, opens on
the Send step, for as long as its plate is still in the browser's storage. [D107] For a
print that finished it shows the last-print note there ("Your print finished at
11:25 am."); for one that failed, the failure on the card; and Send is enabled again for
the same sliced plate while its sliced file is kept ([The sliced file](#the-sliced-file)).
A page that reloads itself after a deploy is a returning page, so this keeps a user on
the step they were on. The page finds its user's delivery job and last print by asking
the front server ([Printers, from phase 5](#printers-from-phase-5)), since the browser's
storage holds no delivery job's id. (*Proposed*:) this comes before the table's last row: a page whose
plate has a delivery job does not treat its slice job as expired by the time it kept,
since a print keeps the sliced file two hours past the print's end; it drops the plate
only once the front server reports the sliced file expired. Once the plate is gone from
the browser's storage, the page opens on the Parts step.

A slice container that restarts while a slice waits or runs loses that slice job: an open
page uploads its parts again from the browser's storage and submits the same plate,
unasked, and a closed page does so when it is next opened, if that is within two hours of
its submission; later, the page treats the plate as expired (above)
([the architecture](../docs/architecture.md#what-a-restart-does)). [D217]

Work does not follow a user to another computer or browser: there the wizard opens empty.
[D108] The parts and the layout live only in one browser's storage, so another browser
could not show or change the plate's layout, and the front server needs no lookup of a
slice job by user. The same holds between Onshape's panel and a tab
([Storage inside Onshape's panel, and storage in a tab](#storage-inside-onshapes-panel-and-storage-in-a-tab)).

Which step a page with stored parts and no slice job opens on (a refresh on the Settings
or the Layout step) is written with the steps.

## Following progress, and reconnecting

The browser follows a slice job, and from phase 5 a delivery job, as server-sent events,
through the front server ([the front server](../front/README.md)). [D58] Every progress
stream sends a comment line at least every fifteen seconds while it has nothing to report,
because Railway closes a request after fifteen minutes, or after five without data, and
Cloudflare after 125 seconds without data.

**The page reconnects when a progress stream closes.** [D61] A stream closes on its own
after at most fifteen minutes on Railway, and at every restart of the front server, so a
close is normal and never shown as an error. A stream that connects late gets the latest
progress report at once, so a reconnected page catches up in one event. The progress
report's `sequence` lets the page tell a repeated report from a missed one.

**A slice that waits.** A slice that cannot start yet waits, and its user is shown that it
is waiting and how many slices are ahead of it; its progress report carries that number
([the slice service](../slice/README.md)). [D54]

**No room to wait.** When no more slice jobs may wait, the user is told the slice service
is busy and to try again shortly (`slice.busy`; [the slice service](../slice/README.md)).
[D55] The hosted service starts with one slice running and two waiting.

**If progress streams are held.** Whether Cloudflare and Railway pass server-sent events
on without holding them back is not checked. If one does hold them, the page asks for the
latest progress report every second or two instead, by a route that both the slice
service's interface and the relay's have
([the architecture](../docs/architecture.md#to-confirm-before-building-on-it)). [D354]
(*Proposed*, as in [the front server's guide](../front/README-details.md#parts-and-slice-jobs-passed-to-the-slice-service):)
for a slice job that route is the front server's route for asking about a slice job, and
from phase 5, for a delivery job, a route that answers a delivery job's latest progress
report.

## Errors the wizard explains

Every failure the page can see arrives as an error report, whose `message` and `remedy`
are sentences for the user and whose `detail` is never shown. The slice service stops an
Orca that passes the memory ceiling or the time limit, and reports each as an error the
wizard explains: `slice.out_of_memory` and `slice.timeout`
([the slice service](../slice/README.md)). [D43, D51] The hosted memory ceiling is 6,000 MB
(proposed) and the time limit starts at 240 seconds, both settings of the slice service.
The mockup shows the timeout and no out-of-memory message
([screen 3.12](#screens-the-design-needs-that-the-mockup-does-not-show)). How each error
reads is written with the steps.

There is no "plate too large" error: no limit caps a plate's volume. A plate too big to
slice ends in `slice.out_of_memory`.

## Retrying every request

**The page retries every request it makes,** so a request that falls in the gap of a
deploy is repeated and the user sees a pause, not an error. [D234, D338] The project is
deployed continuously, and a deploy at any moment interrupts no user
([the architecture](../docs/architecture.md#restarts-and-deploys)). (*Proposed*:) a
request is retried when it gets no answer, when its connection fails, and when its answer
is an error report marked `retryable` that says a service did not answer. (*Proposed*:)
`slice.busy` is not retried silently: it is shown, as
[Following progress](#following-progress-and-reconnecting) says. So a slice service that
is stopping for a deploy must not refuse a new slice job with `slice.busy`, which the user
would see as an error; it refuses with an answer the page retries, one that says the
service did not answer ([the contract](../contracts/wizard-front-server.md#submitting-a-plate-configuration)).
(*Proposed*:) every request is safe to repeat; the contract requires it
([the contract](../contracts/wizard-front-server.md#every-request-and-every-answer)).

**How long the page retries, and what it shows.**

- The page retries a request that fails or gets no answer, quietly at first.
- After 20 seconds of failed retries it shows a message saying the server is being slow
  and the browser is retrying, with a countdown to the next attempt (as Gmail's
  "retrying in 28s" does). So the waits between attempts grow, to leave something to
  count down. (*Proposed*:) the waits double from one second up to thirty seconds, and the
  message reads "The server is being slow. Your browser is retrying in 28 s."
- It keeps retrying for up to 300 seconds in all.
- After 300 seconds it stops, tells the user the server could not be reached, and offers
  to try again. (*Proposed*:) the message reads "The server could not be reached.", and
  the action is named Try again. Nothing of the user's work is dropped: the parts, the
  layout and the chosen settings stay in the browser's storage, and a part whose upload
  stopped keeps its row, with Try again.

(*Proposed*:) these times cover every request a user waits on: adding a part, submitting a
plate, fetching a sliced file (the preview or the download), sending, cancelling. A
progress stream is not one: its reconnecting is never shown. While the server cannot be
reached, Cancel slice is disabled, with one line saying the slice may still be running
(the mockup's decision 31).

## Reloading on a newer version of the front server

Every answer of the front server carries the front server's version
([the front server](../front/README.md)). **A page that sees a newer version reloads
itself at the next moment when nothing is in flight,** which loses nothing because its
state is in the browser's storage. [D237, D339] (*Proposed*:) nothing is in flight when
no request of the page's is waiting for its answer; an open progress stream does not
count, since the
reloaded page reconnects and gets the latest report at once. A page loaded before a deploy
keeps working against the new front server until it reloads
([the architecture](../docs/architecture.md#old-and-new-versions-together)).

What the reload resets that the browser's storage does not hold (advanced mode's open and
closed sections, decision 13, which live in the page's memory) is
[screen 3.7](#screens-the-design-needs-that-the-mockup-does-not-show).

## Signing in, and "sign in again"

Every user signs in with Onshape's OAuth, in Onshape's panel and outside it alike; there
are no accounts or passwords of PenguinSlicer's own. A sign-in sets one encrypted cookie
that lasts thirty days ([the front server](../front/README.md)). Every route of the front
server refuses a request without a signed-in user, except the sign-in routes and the
daemon's. A request for one of the wizard's pages without a signed-in user starts the
sign-in; any other route answers with an error report, and (*proposed*: as the front
server's guide proposes it, "not signed in") the page then starts the sign-in
([the front server](../front/README-details.md#which-routes-need-a-signed-in-user)). On
one machine the front server signs in a fixed made-up user and group, the
development identity, with no call to Onshape.

**"Sign in again".** The wizard's header has a "sign in again" action beside the current
group's name. It reads the user's groups afresh, for two calls to Onshape. Until the
Onshape app is public, a signed-in user's groups are read only at sign-in, so a user
added to an Onshape company after signing in does not see the new group until they use
this action. [D134, D340] The front server owns the route
([the front server](../front/README.md#signing-in)); (*proposed*) the page's stored work
is untouched by it.

**Requests from other sites.** Every request of the page's that changes something carries
a header that only the wizard's own page can set, and the front server checks the
request's origin ([the front server](../front/README.md)). [D140] Inside Onshape's panel
the cookie is one that browsers send to an embedded page, so the cookie alone does not
prove a request came from the wizard.

## The current group

The wizard's header names the current group, as the mockup's "Config:" line does, and the
user changes it there. [D118] The choice is kept in the browser's storage and sent with
each request; the front server accepts it only if the sign-in cookie lists that group
among the user's ([the front server](../front/README.md)). [D119] A user in one group has
nothing to choose; a user in none is a group of one.

What the header looks like with a choice of groups, and with "sign in again" beside it, is
[screen 3.2](#screens-the-design-needs-that-the-mockup-does-not-show).

## The configuration

A group's **configuration** holds its filaments, each with a colour and its own profiles,
the printer's Orca profile, and the units of uploaded files
([its contract](../contracts/configuration.md)). The page always uses the current
group's configuration, read through the front server, never one opened from a link: a
link would bypass the check of the current group against the sign-in cookie. The front
server reads it when a user signs in and again when the wizard asks.

What the wizard takes from it:

- **The plate's size and height.** The Layout step's line "Shop H2S: plate 340 × 320 mm,
  up to 340 mm tall, 12 mm apart", Arrange and the placement check (3 mm inside the edge,
  within the height) use the plate's size and height from the printer's Orca profile (its
  `printable_area` and `printable_height`), the same profile the slice service slices
  for, which the plate configuration names as its `printer`. The printer's display name
  comes from the paired-printer record. A group with no configuration document gets the
  built-in default, the H2S profile. The spacing, 12 mm with supports on and 5 mm off, is
  the plate configuration's ([its limits](../contracts/plate-configuration.md#limits)).
- **Profiles by the group's own names.** The Settings step offers each filament's
  profiles by the names the configuration gives them ("Structural, Pulley, Camera
  mount") and shows each profile's purpose as its option's tooltip.
- **A colour for each filament,** shown where the user chooses a filament, so that two
  filaments of one material (a red PLA and a green PLA) can be told apart. The layer
  preview never uses it: it draws every plate in four fixed colours, one for each set of
  line types, whatever the filament (walls blue `#2b5c9e`, infill orange `#e0912f`, top
  and bottom surfaces green `#2f9e7a`, supports and brim violet-grey `#9a8fb8`), chosen
  to stay apart in every common kind of colour blindness.

 An edit writes the whole document
on the condition that it has not changed since it was read, so two users editing at once
cannot silently overwrite each other; the second is told to reload
([the front server](../front/README.md)). [D115] The configuration's edit screens are a
feature of their own, in no phase yet, with a design spec of their own
([the plan, Known future work](../docs/plans/penguin-slicer-plan.md#known-future-work));
(*proposed*) until they exist the wizard only reads the configuration.

## The sliced file

The state bucket's copy of a sliced file is the one everything uses: the browser fetches
it through the front server to draw the Preview step and to offer the download, and on Send
the relay hands it to the daemon ([the front server](../front/README.md)). [D85] A sliced
file can be previewed, downloaded, sent, and sent again after a print, until two hours
after its slice ended or two hours after its last print ended, whichever is later; past
that the front server refuses it with an error report saying it has expired
([the front server](../front/README.md)). [D91] Its last print ended when the latest
delivery job that used it ended. So after a print of any length, whether it finished or
failed, Send is enabled again for the same sliced plate, and a user whose long print
failed at the last layer can send it again at once. The two hours count from when the
slice ended, which the front server knows from the time stored with the sliced file, not
from when the user left the page. A sliced file is 8.8 to 14.1 MB on the plates measured
so far.

## Printers, from phase 5

The Send step and the printer-status icon show what [printer delivery](../delivery/README.md)
reports through the front server. What the design fixes:

- **Pairing.** Someone runs the daemon's `pair` command on the daemon's computer; then
  any signed-in user of the group types the code it shows into PenguinSlicer, from any
  computer. With no printer paired, the Send step offers the field for the code, and its
  message says that any user of the group can pair the printer, since nothing
  distinguishes one user of a group from another. When no daemon is offering the typed code, the user is told at once that no daemon is
  showing that code and to try again in a moment; every wrong code gets that one answer
  ([printer delivery](../delivery/README-details.md#pairing)). [D151]
- **Offline.** While the daemon is silent (no sync within 2 minutes) the printer-status
  icon shows Offline and Send is disabled; the daemon's first sync puts both back
  ([printer delivery](../delivery/README.md)). [D163] An offline printer's details say
  how long it has been silent ("Not heard from for 7 minutes."), and so does the Send
  step. The relay notes the time in the paired-printer record when a daemon goes offline,
  one write at that moment, and the printer's status returns it, so the duration is true
  even after a restart of the front server.
- **A printing printer.** The relay refuses a send to a printer that is printing, whether
  PenguinSlicer sent the print or someone started it at the printer's own screen
  ([printer delivery](../delivery/README-details.md#how-often-a-daemon-talks-to-the-relay)). [D174]
- **Stale and "stop following".** A running delivery job's report is stale when the
  daemon's last sync was more than 40 seconds ago. A stale delivery job whose print was
  started may be given up by the user ("stop following"), which lets the relay accept the
  next send once the daemon is back and the printer is idle
  ([printer delivery](../delivery/README.md)). [D177]
- **The last print.** A delivery job's record is kept for a day after it ends, so the Send
  step and the printer-status icon can show how the last print ended
  ([printer delivery](../delivery/README.md)). [D158]
- **Names.** Users of one group see each other's names and a one-line description of a
  plate that is printing, on the printer-status icon
  ([the architecture](../docs/architecture.md#security)). [D251]
- **Who sent a print, what it is, and how the last one ended.** The printer details and
  the busy printer's card say who sent the print ("Sent by Alex Chen") and what it is
  ("8 instances of Gusset Plate"); the printer details say "Last print finished 11:25 am
  (Alex Chen)" and, for a failure, when it stopped and at which layer. So a delivery
  job's record carries the sender's display name, a one-line description of the plate,
  the time the delivery job ended and, for a failure, its layer, and the printer's status
  returns them, from the relay through the front server
  ([printer delivery](../delivery/README-details.md#from-the-wizards-mockup)). Who writes the one-line
  description (the page with its send, or the front server from the plate configuration)
  is settled when the contract's routes are written.
- **The user's own delivery job and last print.** A returning page reopens the Send step
  with live progress, reports a failed print and shows the last-print note
  ([What a returning page does](#what-a-returning-page-does)). The browser's storage holds
  a slice job's id and no delivery job's, so the page asks the front server for the
  signed-in user's live delivery job and that user's last print, which the relay keeps
  ([the contract](../contracts/wizard-front-server.md#printers-from-phase-5); its routes
  are not written yet).

## Storage inside Onshape's panel, and storage in a tab

Chrome keeps the storage of a page inside Onshape's panel apart from the storage of the
same page opened directly, so work begun in the panel does not appear at the address
opened in a tab of its own, nor the reverse. [D109] Each is a returning page of its own,
with its own stored parts, layout and slice job. Since a user has one unfinished slice job
at a time, slicing in one cancels an unfinished slice in the other, which that page then
shows as "cancelled by a later slice of the same user".

## Browsers supported

Safari is not supported, in Onshape's panel or outside it: nothing is designed or tested
for it. [D146] Inside Onshape's panel, sign-in and the stored parts depend on Chrome
allowing cookies and storage to an embedded page. [D147] The wizard works from 320 px,
the narrowest width it must work at, and lays out wider when it has more room
([the plan](../docs/plans/penguin-slicer-plan.md#terms)).

## By phase

The design's own list by phase does not place retrying, reloading or the header on every
changing request. [The plan](../docs/plans/penguin-slicer-plan.md#the-phases) puts
retrying and reloading in phase 2, since the restarts tested there need them, and the
header, checked from then on, in phase 3, as
[the front server's guide](../front/README-details.md#by-phase) does for the check.

| Phase | What of the wizard is built |
|---|---|
| 2, one machine | The wizard opened directly in a browser, with parts from files and the development identity: the browser's storage; uploading each part; submitting by hash and uploading missing parts again; one unfinished slice job; the returning page; progress streams and reconnecting; retrying; reloading on a newer version of the front server; the current group in the header; reading the configuration; the preview and the download |
| 3, hosted on Railway | Onshape sign-in and "sign in again"; the header on every changing request, checked from here on |
| 4, inside Onshape | The wizard in Onshape's panel, with parts read from Onshape; its storage kept apart from a tab's |
| 5, the real printer | The Send step and the printer-status icon: pairing, sending, cancelling, "stop following", unpairing, and the returning page on the Send step |

## Where this guide departs from the mockup's decisions

Whoever writes the steps from [the mockup's decisions](../docs/mockups/print-wizard/DECISIONS.md)
follows this guide where the two differ, in these places:

| The mockup's decision | What the mockup says | What this guide says |
|---|---|---|
| Terms, "configuration" | The configuration holds the printer | The paired-printer record links the group to its printer; the configuration names the printer's Orca profile ([The configuration](#the-configuration)) |
| Terms, "administrator"; 42 | An administrator pairs the printer, from the computer beside it | Any signed-in user of the group types the pairing code, from any computer ([Printers](#printers-from-phase-5)) |
| 13 | Advanced mode's changes last for this page load | The changes are in the browser's storage and outlast a refresh ([What the page keeps](#what-the-page-keeps-in-the-browsers-storage)) |
| 17 | After 20 seconds of failed retries, a notification that the part was not added, to be clicked in Onshape again | After 20 seconds, a message that the server is being slow, with a countdown; retrying for up to 300 seconds, then an error with Try again; the part keeps its row ([Retrying](#retrying-every-request)) |
| 33; the requirement on the configuration | No colour for each filament | The configuration holds a colour for each filament, shown where the user chooses one and never in the layer preview ([The configuration](#the-configuration)) |
| 45, 46; the requirement on the slice service | A refresh throws the page's state away; the server finds the user's slice job and restores the parts and layout | The browser's storage keeps the work and the slice job's id; work does not follow to another browser ([What a returning page does](#what-a-returning-page-does)) |
| 47, 48 | Otherwise the Parts step; a failed print is a notification on the Parts step, the parts not kept | A page whose stored plate has a delivery job, running or ended, opens on the Send step ([What a returning page does](#what-a-returning-page-does)) |
| 48; M18 | A finished unsent slice is gone after two hours away | A sliced file is kept until two hours after its slice ended or its last print ended, whichever is later ([The sliced file](#the-sliced-file)) |
| What is fake, 9 | A "plate too large" error against a cap on a plate's volume | No such error; a plate too big to slice ends in `slice.out_of_memory` ([Errors](#errors-the-wizard-explains)) |
| What is fake, 25 | The page outside Onshape opens the configuration from a saved link | The configuration is the signed-in user's current group's ([The configuration](#the-configuration)) |

## Screens the design needs that the mockup does not show

Twelve screens or states the design requires that no step of the mockup shows. Each is
designed when the steps are written. The numbers are those of
[the comparison of the mockup with the design](../docs/orchestration/hosted-architecture/mockup-against-design.md).

| | The screen or state | What the design says | Where it would appear |
|---|---|---|---|
| 3.1 | Signing in, signed out, a sign-in that has ended | Every user signs in with Onshape; every route refuses a request without a signed-in user; the cookie lasts thirty days, and after an emergency replacement of its key every user signs in again | Before any step, in the panel and outside it |
| 3.2 | Choosing the current group, and "sign in again" | The header names the current group and the user changes it there; "sign in again" beside it reads the groups afresh for two calls to Onshape | The header |
| 3.3 | A sliced file that expires while the page is open | The front server refuses a sliced file once it is past two hours after its slice ended and two hours after its last print ended, whether or not the page is open, including after "Sending cancelled … Your sliced plate is still here." (decision 37) | The Preview step and the Send step: the preview, Download and Send |
| 3.4 | A slice that waits, and no room to wait | A waiting slice shows how many slices are ahead of it; with no room (one running and two waiting, to start with) the user is told the slice service is busy and to try again shortly | The Preview step's slicing card |
| 3.5 | Typing a pairing code, a wrong code, unpairing | Any signed-in user types the code; a code is good for fifteen minutes; every wrong code gets one answer, at once, and wrong attempts are limited for each user; unpairing removes the paired-printer record | The Send step with no printer paired, and the printer details |
| 3.6 | A stale delivery job, and "stop following" | A running delivery job's report is stale after 40 seconds without a sync; the user may then stop following a print that was started | The Send step and the printer details |
| 3.7 | The page reloading itself on a newer version | A page that sees a newer front server version reloads at the next moment when nothing is in flight; what the browser's storage does not hold (advanced mode's open sections, decision 13) starts afresh | The whole panel, at any step |
| 3.8 | A slice cancelled by a later one in another tab | The page shows the plate on the Preview step and offers to slice it, and does not submit by itself | The Preview step |
| 3.9 | What a restart shows | A slice container restart sends a slice's progress back to its start; a front server restart leaves the printer-status icon and the Send step blank until the daemon's next sync, within ten seconds, plus the daemon's short random wait, of the front server answering again | The Preview step's slicing card; the printer-status icon and the Send step |
| 3.10 | A printer busy with a print nobody sent from PenguinSlicer | The daemon syncs every 10 seconds whoever started the print, and the relay refuses a send to a printing printer, so a print with no sender and no description is busy too | The Send step's busy card and the printer details |
| 3.11 | Limits on parts | A part is uploaded in one request of at most 7.5 MB; a plate uses at most 25 different parts (and at most 150 instances, decision 22) | The Parts step |
| 3.12 | Running out of memory | The memory ceiling (6,000 MB proposed, hosted) ends a slice with `slice.out_of_memory`, an error the wizard explains | The Preview step's slicing failures |

## Still to be written

- **The steps,** from [the mockup's decisions](../docs/mockups/print-wizard/DECISIONS.md):
  every screen, message and decision of the Parts, Settings, Layout, Preview and Send
  steps and of the printer-status icon, with the twelve screens above, and this guide in
  place of the mockup wherever
  [Where this guide departs from the mockup's decisions](#where-this-guide-departs-from-the-mockups-decisions)
  says so.
- **The mockup's open questions,** "Please react to these" (M1, M2, M3, M6, M7, M11, M16,
  M17, M21, M22, M23, M25, M26, M29; M18 is answered by
  [The sliced file](#the-sliced-file)): each is either answered by the owner
  or carried into this guide as an open choice with its backing.
- **The mockup is thrown away** once this guide is complete and the owner has agreed it
  ([the plan](../docs/plans/penguin-slicer-plan.md#phase-1-the-wizards-guide)).
