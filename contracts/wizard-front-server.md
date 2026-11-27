# The wizard and the front server

What the contract between the wizard and the front server must provide. **Its routes are
not written yet:** their paths, the shapes of their requests and answers, and the codes of
the front server's own error reports are written with phase 2's design. Until then this
file collects every decision that binds them, so that nothing is lost when they are
written.

The **wizard** is the code in the browser ([its guide](../wizard/README.md)); the **front
server** is the one process the internet reaches, which serves the wizard's pages and
stands between the browser and the slice service, the buckets, Onshape and, from phase 5,
the relay ([its guide](../front/README.md)). The browser talks only to the front server,
at one address, and never makes a cross-origin request. A **page** is the wizard as loaded
in one browser tab or in Onshape's panel. The phases are those of
[the plan](../docs/plans/penguin-slicer-plan.md): phase 2, one machine; phase 3, hosted on
Railway; phase 4, inside Onshape; phase 5, the real printer.

Each requirement below links to the guide that owns its full explanation. Some depend on
an item still awaiting the owner; those say so and link
[the wizard's list of them](../wizard/README-details.md#where-the-mockup-and-the-design-differ).

## Every request and every answer

- **Errors and progress have one shape each.** Every failure the front server answers is
  an [error report](error-report.md), and every report of how far a job has got is a
  [progress report](progress-report.md). The front server passes the slice service's
  error reports (`slice.*`) and, from phase 5, the relay's (`delivery.*`) to the page
  unchanged; its own get codes of the form `front.<what>`
  ([the front server](../front/README-details.md#error-reports)).
- **Every request is safe to repeat.** The page retries every request it makes, so a
  request that falls in the gap of a deploy is repeated and the user sees a pause, not an
  error ([the wizard](../wizard/README-details.md#retrying-every-request)). A request sent
  twice because its first answer was lost must leave the same result as one sent once:
  uploading the same part again answers the same; a repeated submission must not leave the
  page following a slice job the repeat cancelled; a repeated send must not start a second
  delivery job or answer the first with a refusal. How long the page retries before it
  shows an error depends on
  [item 1.9](../wizard/README-details.md#19-retrying-then-an-error-after-20-seconds),
  awaiting the owner's choice.
- **Every answer carries the front server's version,** in a header, error reports and the
  first event of a progress stream included
  ([the front server](../front/README-details.md#the-version-on-every-answer)). A page that
  sees a newer version reloads itself at the next moment when nothing is in flight
  ([the wizard](../wizard/README-details.md#reloading-on-a-newer-version-of-the-front-server)).
- **A page from before a deploy keeps working after it.** Every change to these routes
  must keep a page loaded before the deploy working against the new front server, at least
  until it reloads; this is the rule most easily broken by accident
  ([the architecture](../docs/architecture.md#old-and-new-versions-together)).

## Signing in, and the cookie

- **Every route refuses a request without a signed-in user,** except the sign-in routes
  and the daemon's routes, with a "not signed in" error report on which the page starts
  the sign-in. Every user signs in with Onshape's OAuth, in Onshape's panel and outside it
  alike ([the front server](../front/README-details.md#which-routes-need-a-signed-in-user)).
- **One encrypted cookie** holds the user's identity, groups and Onshape tokens for thirty
  days; nothing about a session is kept on the server, so a restart signs nobody out
  ([the front server](../front/README-details.md#the-cookie)).
- **The user key comes from the cookie only.** The front server sets the user key, the
  signed-in user's Onshape id, from the cookie, and no request of the page's can name one,
  so a user reaches only their own parts, slice jobs and sliced files
  ([the front server](../front/README-details.md#the-user-key)).
- **"Sign in again"** is a route the header's action starts. It reads the user's groups
  afresh from Onshape, for two calls, so a user added to an Onshape company after signing
  in sees the new group ([the wizard](../wizard/README-details.md#signing-in-and-sign-in-again)).
- **The user and their groups** are a route the page reads, to name the current group and
  offer the others ([the front server](../front/README.md#its-interface)).

## The header and origin check

Every route that changes something on the strength of the cookie also requires a header
that only the wizard's own page can set, and checks that the request's origin is the
front server's own address. These are uploading a part, submitting a plate configuration,
cancelling a slice job, writing the configuration, and from phase 5 pairing, sending,
stopping following, cancelling a delivery job and unpairing. A request that fails either
check is refused with an error report. No route allows cross-origin requests
([the front server](../front/README-details.md#requests-from-other-sites)).

## The current group

The page keeps the current group in the browser's storage and sends it with each request.
The front server accepts it only if the cookie lists that group among the user's, and
refuses with an error report a request that needs a group and names none or one the cookie
does not list. Every route that reads or writes a configuration, and from phase 5 every
route of pairing, sending and unpairing, makes the check
([the front server](../front/README-details.md#groups-and-the-current-group)).

## Uploading one part

- **One part a request, at the moment the user adds it,** at most 7.5 MB (7,500,084 bytes,
  [the plate configuration's](plate-configuration.md#limits) `MAX_PART_BYTES`)
  ([the wizard](../wizard/README-details.md#uploading-each-part-when-it-is-added)).
- **Checked on arrival.** The slice service runs its checks as the part arrives; the answer
  for a part that passes gives the SHA-256 hash of its bytes, under which the part store
  keeps it, with its measurements and warnings
  ([the slice service](../slice/README-details.md#to-be-built)).
- **A part that cannot be used** is answered with an error report the page shows on the
  Parts step. Whether as a row or as a notification, with the part not added, is
  [item 1.8](../wizard/README-details.md#18-a-part-that-cannot-be-used), not yet confirmed
  by the owner.

## Submitting a plate configuration

- **Parts by hash, no files.** The page sends a [plate configuration](plate-configuration.md)
  naming each part by its SHA-256 hash and carrying no files, so slicing again uploads
  nothing ([the wizard](../wizard/README-details.md#submitting-a-plate-configuration)).
- **The answer that lists missing parts.** When the plate configuration names parts no
  longer in the part store, the answer is one error report listing every missing hash
  (`slice.part_missing`, action `refresh_parts`), passed back unchanged. The page uploads
  those parts again from the browser's storage and submits again, and the user sees
  nothing of it ([the slice service](../slice/README-details.md#to-be-built)).
- **One unfinished slice job.** A user has one unfinished slice job at a time: a
  submission cancels the same user's earlier unfinished slice job, whose final progress
  report says it was cancelled by a later slice of the same user
  ([the slice service](../slice/README-details.md#to-be-built)).
- **The answer gives the slice job's id,** which the page keeps in the browser's storage
  with the time it submitted.
- **The busy answer.** When no more slice jobs may wait, the answer is `slice.busy`
  (retryable), telling the user the slice service is busy and to try again shortly
  ([the slice service](../slice/README.md)).
- **Cancelling a slice job** is a route of its own, passed on to the slice service.

## Asking about a slice job

A page that has lost its state asks about the slice job whose id it kept. The answer is
one of these, and the page acts on each as
[the wizard's table](../wizard/README-details.md#what-a-returning-page-does) says:

| Answer | Carries |
|---|---|
| Waiting | How many slice jobs are ahead of it |
| Running | Its latest progress report |
| Finished | That its sliced file is in the state bucket |
| Ended in an error | The error report |
| Cancelled by a later slice of the same user | That reason |
| Unknown | Nothing more: the page decides from the time it kept whether the slice container restarted (submit again) or the sliced file has expired |

The slice service remembers a slice job for two hours after it ends, and the front server
also looks for its sliced file in the state bucket
([the front server](../front/README-details.md#parts-and-slice-jobs-passed-to-the-slice-service)).
A slice job of another user answers as unknown.

## The progress stream

- **Server-sent events, through the front server,** for a slice job and, from phase 5, a
  delivery job ([the front server](../front/README-details.md#parts-and-slice-jobs-passed-to-the-slice-service)).
- **A comment line at least every fifteen seconds** while there is nothing to report,
  because Railway closes a request after fifteen minutes, or after five without data, and
  Cloudflare after 125 seconds without data.
- **The latest progress report at once** to a stream that connects late, so a page that
  reconnects catches up in one event.
- **A waiting slice job's report says how many are ahead of it,** and a new report is sent
  when that number changes ([the slice service](../slice/README-details.md#to-be-built)).
- **Finished only once stored.** The front server reports a slice job finished on the
  stream only once its sliced file is in the state bucket.
- **Reconnecting.** The page reconnects whenever a stream closes, including at every
  restart of the front server ([the wizard](../wizard/README-details.md#following-progress-and-reconnecting)).
- **The fallback.** If Cloudflare or Railway turns out to hold server-sent events back,
  the page asks for the latest progress report every second or two instead, by the route
  for asking about a slice job, which both interfaces must therefore have
  ([the architecture](../docs/architecture.md#to-confirm-before-building-on-it)).

## The sliced file

- **Fetched through the front server,** from the state bucket's copy, the one everything
  uses: for the Preview step and for the download. The browser never stores a sliced file
  and no route takes one from a browser
  ([the front server](../front/README-details.md#following-slice-jobs-and-storing-sliced-files)).
- **Its summary,** the JSON object the slice service gives beside the file (the predicted
  print time, the filament used, the layer count and the warnings;
  [the sliced file](sliced-file.md#summary)),
  is fetched through the front server too, for as long as the file itself, so the front
  server keeps it beside the file in the state bucket.
- **Two hours.** A sliced file can be previewed, downloaded, sent and sent again after a
  print for two hours after its slice ended; an older one is answered with an error report
  saying it has expired, and deleted
  ([the front server](../front/README-details.md#two-hours-deleting-and-the-backstop)).
  When the two hours start, and whether a print extends them, depend on
  [item 1.4](../wizard/README-details.md#14-when-the-two-hours-start) (not yet confirmed
  by the owner) and
  [item 1.1](../wizard/README-details.md#11-sending-the-same-plate-again-after-a-long-print)
  (awaiting the owner's choice).

## The configuration

- **Read whole** when a user signs in and again when the wizard asks, for the current
  group; a group with no document gets the built-in default
  ([the front server](../front/README-details.md#the-configuration)).
- **Written whole, on the condition that it has not changed** since it was read; a write
  that fails the condition is refused with an error report telling the user to reload, so
  two users editing at once cannot silently overwrite each other. So the answer to a read
  carries a marker of the document's version, and a write names the marker it was based
  on.
- **Its shape** is [the configuration's contract](configuration.md). What the Layout step
  needs from it (the plate's size and height, from the printer's Orca profile) and what
  the Settings step needs (each profile's name and purpose) depend on
  [item 1.7](../wizard/README-details.md#17-whether-the-printer-is-in-the-configuration)
  and [need 2.5](../wizard/README-details.md#25-a-profiles-name-and-purpose), not yet
  confirmed by the owner.

## Printers, from phase 5

All of these pass through the front server to the relay of
[printer delivery](../delivery/README.md), with the signed-in user and the current group.

- **The printer's status,** for the printer-status icon and the Send step: free, sending,
  starting, printing with percent, layer and time left, waiting for a person, failed,
  offline (no sync within 2 minutes), or no printer paired; a running delivery job's
  report marked stale when the daemon's last sync was more than 40 seconds ago. It also
  carries who sent the print going on, a one-line description of its plate, and how the
  last print ended (its sender, its end time and, for a failure, its layer)
  ([printer delivery](../delivery/README-details.md#from-the-wizards-mockup)). How long an
  offline daemon has been silent ("Not heard from for 7 minutes") depends on
  [need 2.4](../wizard/README-details.md#24-not-heard-from-for-7-minutes), awaiting the
  owner's choice.
- **Sending.** A send is accepted when the current group has a paired-printer record, and
  its delivery job goes to the daemon that record names; a send to a printer that is
  printing is refused, whoever started the print
  ([printer delivery](../delivery/README-details.md#sending-and-unpairing)).
- **Cancelling** a delivery job, and **"stop following"** a stale delivery job whose print
  was started, which lets the relay accept the next send once the daemon is back and the
  printer is idle ([printer delivery](../delivery/README-details.md#how-often-a-daemon-talks-to-the-relay)).
- **The user's live delivery job and last print.** A page that has lost its state asks for
  the signed-in user's live delivery job and that user's last print, since the browser's
  storage holds no delivery job's id
  ([printer delivery](../delivery/README-details.md#from-the-wizards-mockup)). Which step
  a returning page then opens on is
  [item 1.10](../wizard/README-details.md#110-where-a-returning-page-opens-after-its-print-ended).
- **Typing a pairing code.** When a daemon is offering the typed code, the relay writes the
  paired-printer record for the user's current group. When none is, the answer, at once,
  is that no daemon is showing that code and to try again in a moment; every wrong code
  gets that one answer, whatever was wrong with it, and wrong attempts are limited for each
  user ([printer delivery](../delivery/README-details.md#pairing)). Who may type it is
  [item 1.6](../wizard/README-details.md#16-who-pairs-the-printer-and-where).
- **Unpairing** removes the current group's paired-printer record
  ([printer delivery](../delivery/README-details.md#sending-and-unpairing)).
