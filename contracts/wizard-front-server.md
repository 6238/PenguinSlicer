# The wizard and the front server

What the contract between the wizard and the front server must provide. **Its routes are
not written yet:** their paths, the shapes of their requests and answers, and the codes of
the front server's own error reports are written before phase 2's building starts. Until
then this file collects every requirement that binds them, so that nothing is lost when
they are written.

The **wizard** is the code in the browser ([its guide](../wizard/README.md)); the **front
server** is the one process the internet reaches, which serves the wizard's pages and
stands between the browser and the slice service, the buckets, Onshape and, from phase 5,
the relay ([its guide](../front/README.md)). The browser talks only to the front server,
at one address, and never makes a cross-origin request. A **page** is the wizard as loaded
in one browser tab or in Onshape's panel. The phases are those of
[the plan](../docs/plans/penguin-slicer-plan.md): phase 2, one machine; phase 3, hosted on
Railway; phase 4, inside Onshape; phase 5, the real printer.

**Read after:** [the architecture](../docs/architecture.md#terms), whose terms it uses.

Each requirement below links to the guide that owns its full explanation. Where a
requirement rests on an item that is still undecided, it says so and links to the item
in the guide that owns it; the requests are written to the item's answer. Names and
figures marked *proposed* are this file's suggestions; the design approved by the owner
does not fix them, and the builder settles them while building.

What the wizard needs of the front server, in its own words, is in
[What the wizard asks of the front server](../wizard/README.md#what-the-wizard-asks-of-the-front-server).

## Every request and every answer

- **Errors and progress have one shape each.** Every failure the front server answers is
  an [error report](error-report.md), and every report of how far a job has got is a
  [progress report](progress-report.md).
- **Each component writes the sentences of its own failures.** The front server passes
  the slice service's error reports (`slice.*`) and, from phase 5, the relay's
  (`delivery.*`) to the page unchanged, and writes its own (*proposed*: codes of the form
  `front.<what>`) for its own failures: not signed in, a group the user is not in, a
  configuration that cannot be read, a sliced file that has expired. The wizard shows the
  sentences for the user as they are and never shows the detail kept for the log
  ([Who writes the sentences of a failure](../wizard/README.md#who-writes-the-sentences-of-a-failure)).
  A sentence written on a server cannot know whether the page is inside Onshape, so it
  says "your CAD program" and never "Onshape". Whether the slice service's report on two
  failures of a slice also carries Orca's own sentence as a quotation for the user is
  undecided
  ([Orca's own sentence under Details](../wizard/README.md#orcas-own-sentence-under-details));
  if it does, the quotation travels inside the report the front server passes unchanged.
- **Every request is safe to repeat.** The page retries every request it makes, so a
  request that falls in the gap of a deploy is repeated. It retries quietly for 20
  seconds; then it says on the panel line that the server is being slow and the browser
  is retrying, with a countdown to the next attempt, the waits between attempts growing
  (*proposed* in the wizard's guide: doubling from one second to thirty); after 300
  seconds in all it says the server could not be reached and offers Try again, which
  starts the 300 seconds afresh. Nothing of the user's work is dropped
  ([When the server is slow or cannot be reached](../wizard/README.md#when-the-server-is-slow-or-cannot-be-reached)).
  So a request may arrive several times over five minutes, and a request sent twice
  because its first answer was lost must leave the same result as one sent once:
  - uploading the same part again answers the same;
  - a repeated submission must not leave the page following a slice job the repeat
    cancelled. The means is undecided; recommended, a value the page makes for each
    submission, which the slice service remembers beside the slice job, so that a repeat
    carrying the same value is answered with the first attempt's slice job. It is settled
    with these requests before phase 2
    ([A plate configuration submitted twice](../front/README.md#a-plate-configuration-submitted-twice));
  - a repeated send must not start a second delivery job, and must not be refused because
    the first one made the printer busy. Printer delivery as built refuses the second
    send (`delivery.job_in_flight`). Proposed in both guides: a send repeated with the
    same sliced file by the same user while its delivery job is live answers with that
    delivery job
    ([Running the relay](../front/README.md#running-the-relay-from-phase-5),
    [A send repeated while its delivery job is live](../delivery/README.md#a-send-repeated-while-its-delivery-job-is-live)).
- **One answer is not retried: the slicer is busy** (see
  [Submitting a plate configuration](#submitting-a-plate-configuration)). The page shows
  it and leaves the next attempt to the user.
- **Every answer carries the front server's version** (*proposed*: in a header), error
  reports and the first event of a progress stream included. A page that sees a newer
  version than its own reloads itself at the next quiet moment: no request of its own
  waiting, nothing being dragged or typed, no menu or box open, and (*proposed* in the
  wizard's guide) ten seconds in which the user has touched nothing. An open progress
  stream does not count as a request waiting
  ([The page reloading itself for a new version](../wizard/README.md#the-page-reloading-itself-for-a-new-version)).
- **A page from before a deploy keeps working after it.** Every change to these routes
  must keep a page loaded before the deploy working against the new front server, at least
  until it reloads; this is the rule most easily broken by accident
  ([Old and new versions together](../front/README.md#old-and-new-versions-together)).

## Signing in, and the cookie

- **Every route refuses a request without a signed-in user,** except the sign-in routes
  and, from phase 5, the daemon's routes and the daemon's offer of a pairing code. Every
  user signs in with Onshape's OAuth, in Onshape's panel and outside it alike
  ([Onshape is the only sign-in](../front/README.md#onshape-is-the-only-sign-in-and-there-are-no-accounts)).
- **A request for one of the wizard's pages with no signed-in user starts the sign-in.**
  The front server sends the browser to Onshape and, when Onshape sends it back, the
  wizard opens. A user already signed in to Onshape who has allowed PenguinSlicer before
  sees no screen between.
- **Any other request with no signed-in user** is answered with the front server's error
  report that the user is not signed in: the sign-in has ended, and the user's parts,
  layout and settings are kept in this browser. The page does not leave for Onshape by
  itself on that answer. It shows those sentences with one button, **Sign in with
  Onshape**, which takes the same trip to Onshape and back and reopens the wizard on the
  step the user was on ([Signing in](../wizard/README.md#signing-in)). So the contract
  provides a way for the page to start a sign-in that comes back to the wizard.
- **A sign-in that failed** (the user refused Onshape's request, or Onshape did not
  answer) lands on a plain page with the front server's sentence of what failed and the
  same button.
- **In phase 2 there is no sign-in to see.** The front server signs in the development
  identity, a fixed made-up user and group, without contacting Onshape, and everything
  else runs as it does hosted: the cookie, the check of the current group and the user
  key ([The development identity](../front/README.md#the-development-identity)).
- **One encrypted cookie** holds the user's Onshape id and name, each of their groups by
  id and name, and the Onshape tokens. It lasts thirty days from the sign-in and is not
  extended by use (a choice the owner has not yet confirmed:
  [Choices the owner has not yet confirmed](../front/README.md#choices-the-owner-has-not-yet-confirmed)).
  Nothing about a session is kept on the server, so a restart signs nobody out
  ([The cookie](../front/README.md#the-cookie-and-why-there-are-no-sessions)).
- **The user key comes from the cookie only.** The front server sets the user key, the
  signed-in user's Onshape id, from the cookie; nothing the page sends can name one, and
  an attempt to is ignored. So a user reaches only their own parts, slice jobs and sliced
  files, even within a group. A slice job or sliced file of another user is answered
  exactly as if it did not exist, and the attempt is logged as a refusal
  ([Whose it is](../front/README.md#whose-it-is)).
- **The user and their groups.** The page asks for the signed-in user's name and the
  names of their groups, which the front server answers from the cookie without calling
  Onshape; the group details are drawn from it
  ([Groups and the current group](../front/README.md#groups-and-the-current-group)).
- **"Sign in again"** (phase 3) is started from a link inside the group details, the box
  that opens from the current group's name, not from the header line itself. It takes the
  trip to Onshape and back, reads the user's groups afresh for two calls, and returns to
  the same step with the group details open, so a user added to an Onshape company after
  signing in sees the new group ([The current group](../wizard/README.md#the-current-group)).
  Nothing yet limits how often one user may use it; that is undecided
  ([Sign-ins and the allowance](../front/README.md#sign-ins-and-the-allowance)).
- **Signing out** is undecided
  ([Sign-out](../wizard/README.md#sign-out)). If the proposal stands, the contract gains
  one small request that removes the cookie, costing no call to Onshape, from a link in
  the group details; the page clears the work stored in the browser. Both guides
  recommend it for phase 3, with "sign in again"
  ([Signing out](../front/README.md#signing-out)).
- **A browser that is not supported.** Chrome is proposed as the supported browser, and
  Safari is not supported. What a user of Safari is shown is the front server's to serve,
  since the wizard's code cannot be relied on there; *proposed*: a plain page saying that
  PenguinSlicer needs Chrome
  ([Browsers other than Chrome](../wizard/README.md#browsers-other-than-chrome)).

## The mark and the origin check

From phase 3, every request that changes something on the strength of the cookie also
carries a mark that only the wizard's own page can add, and comes from the front
server's own address; a request that fails either test is refused with an error report
and logged, and no route allows cross-origin requests. Those requests are: uploading a
part, submitting a plate configuration, cancelling a slice job, writing the
configuration, and from phase 5 pairing, sending, cancelling a send, stop following and
unpairing; and, if they are added, signing out and the report of a failure in the browser
([Requests from other sites](../front/README.md#requests-from-other-sites)).

## The current group

The page keeps the current group in the browser's storage and sends it with every request
that acts for a group: reading and writing the configuration; uploading a part;
submitting a plate configuration; asking about, following and cancelling a slice job;
fetching a sliced file; and from phase 5 everything to do with a printer. The front
server accepts it only if the cookie lists that group among the user's. A request that
names no group, or one the cookie does not list, is refused with the front server's error
report that the user is not in that group, whose remedy is Sign in again, and the
refusal is logged
([Groups and the current group](../front/README.md#groups-and-the-current-group)). On
that refusal the page takes the first of the user's groups and says so
([The current group](../wizard/README.md#the-current-group)).

## Uploading one part

- **One part a request, at the moment the user adds it,** at most 7.5 MB (7,500,084 bytes,
  [the plate configuration's](plate-configuration.md#limits) `MAX_PART_BYTES`), which the
  page checks before sending anything. A plate uses at most 25 different parts, the most
  the slice service keeps for one user key
  ([The limits on a plate](../wizard/README.md#the-limits-on-a-plate)).
- **Its units travel beside it.** Each upload carries the part's units, inches or
  millimetres, as a label: for a file, how the configuration says uploads are read; from
  phase 4, the units of the Onshape document. Neither the browser nor the front server
  ever changes a part's bytes, and only the slice service applies the scale. The slice
  service keeps a part under the user key, its hash and its units together, so the same
  file under other units is another part; it refuses a part without a units label
  (*proposed* in its guide) ([Units](../slice/README.md#units)). Whether the page may
  offer its own switch between inches and millimetres until the configuration's edit
  screens exist is undecided
  ([STL files in millimetres before the edit screens exist](../wizard/README.md#stl-files-in-millimetres-before-the-edit-screens-exist)),
  so the requests must not assume that the label always equals the configuration's value.
- **Checked on arrival.** The slice service runs its checks as the part arrives, judging
  size on the part's true size in its units, and keeps a part that passes in the part
  store under the SHA-256 hash of its bytes. The answer gives that hash, with the part's
  measurements and any warnings, which the page shows on the part's row
  ([Check a part when it arrives](../slice/README.md#check-a-part-when-it-arrives)).
- **A part that cannot be used** is answered with the slice service's error report, which
  the page shows on the Parts step as a notification; the part is not added
  ([A part that cannot be used](../wizard/README.md#a-part-that-cannot-be-used)).
- **It passes through in pieces** (*proposed*): the front server never holds a part whole
  in its memory, and keeps no copy ([A part](../front/README.md#a-part)).

## Submitting a plate configuration

- **Parts by hash and units, no files.** The page sends a
  [plate configuration](plate-configuration.md) naming each part by its SHA-256 hash, with
  its units, and carrying no files, so slicing again uploads nothing. The plate
  configuration's contract gains the units of each part in phase 2. The plate
  configuration names its three profiles by Orca's names, with the user's changes. Which
  side turns the group's profile (its Orca profile and the settings the configuration
  adds) into those three names and settings is stated in no guide; presumably the wizard,
  which holds the whole configuration. It is settled before phase 2.
- **The answer that lists missing parts.** When the plate configuration names parts no
  longer in the part store, the answer is one error report listing every missing hash
  (*proposed*: `slice.part_missing`, action `refresh_parts`), passed back unchanged. The
  page uploads those parts again from the browser's storage and submits again, and the
  user sees nothing of it
  ([Keep each part once: the part store](../slice/README.md#keep-each-part-once-the-part-store)).
- **Which settings are accepted.** Every setting Orca allows that is a parameter with a
  value (a choice from a list, a number, a piece of text) is accepted as a change and
  offered in advanced mode. Settings that run a program, name a file on the server or
  carry custom G-code are refused. As built, four are accepted. A profile or setting that
  is not accepted is refused with the slice service's sentence asking the user to choose
  from the lists; *proposed*: each value is checked against what its setting allows, and
  a refusal names the setting. Which profiles a setting may replace values of is
  undecided, recommended the process profile only
  ([Accept settings](../slice/README.md#accept-settings),
  [How the list of accepted settings is made](../slice/README.md#how-the-list-of-accepted-settings-is-made)).
- **One unfinished slice job.** A user has one unfinished slice job at a time: a
  submission cancels the same user's earlier slice job if it is still waiting or running,
  whose final progress report says it was cancelled by a later slice of the same user.
  With the wizard open in two tabs the later slice wins, and the page whose slice was
  cancelled does not slice again by itself
  ([Run one slice at a time](../slice/README.md#run-one-slice-at-a-time-and-let-a-few-wait),
  [Slicing](../wizard/README.md#slicing)).
- **The answer gives the slice job's id,** which the page keeps in the browser's storage
  with the time it submitted.
- **The busy answer.** One slice runs and two may wait. When no more may wait, the answer
  is the slice service's error report `slice.busy`, passed unchanged, whose sentence is
  "The slicer is busy, try again in a minute." The page shows it as an amber message with
  Slice again and does not try again by itself, since a silent queue in the browser would
  hide how busy the slice service is ([Slicing](../wizard/README.md#slicing)).
- **A stopping slice service is not busy.** A slice service asked to stop for a deploy
  finishes its running slice and meanwhile refuses a new slice job with an answer of its
  own, different from busy; the front server passes it to the page as an answer the page
  retries quietly, like a service that did not answer, so the user sees the panel line
  after 20 seconds and never `slice.busy`
  ([A plate configuration](../front/README.md#a-plate-configuration)). Whether the front
  server should instead keep such a submission, hand it to the replacement and report it
  as a slice job waiting while the slicer restarts is undecided, recommended in both
  guides; until it is built, phase 2 retries
  ([What a user sees while the slice service stops](../slice/README.md#what-a-user-sees-while-the-slice-service-stops)).
- **Cancelling a slice job** is a request of its own, passed on to the slice service. It
  is the user's Cancel slice on the Preview step, and the page's own when the user
  changes the current group with a slice still waiting or running.

## Asking about a slice job

A page that has lost its state asks about the slice job whose id it kept. The front
server asks the slice service, which remembers a slice job for two hours after it ends,
and looks in the state bucket. The answer is one of these, and the page acts on each as
[Coming back to running work](../wizard/README.md#coming-back-to-running-work) says:

| Answer | When | Carries |
|---|---|---|
| Still waiting or running | The slice service says so; also when the slice has ended but its sliced file is not yet stored | Its latest progress report, which for a waiting slice job says how many slice jobs are ahead of it |
| Finished | The sliced file is in the state bucket | That the sliced file is ready, with what the page needs of [The sliced file](#the-sliced-file) |
| Ended in an error | The slice service says so; also when the sliced file was stored and has since expired | The error report; for an expired sliced file, the front server's report that it has expired |
| Cancelled by a later slice of the same user | The slice service says so | That reason |
| Cancelled because the slice service was asked to stop | The slice job was still waiting when a deploy stopped the slice service | That reason, so that the page submits the plate again by itself and does not take the cancel for the user's own or a later slice's |
| Unknown | Neither the slice service nor the state bucket knows it, or it is another user's | Nothing more: the page decides from the time it kept whether the slice service restarted (submit again) or the sliced file has expired |

How a report tells a cancel at a stop from the user's own cancel and from a later slice
job's is written with these requests, before phase 2 is built
([A page that comes back](../front/README.md#a-page-that-comes-back)).

## The progress stream

- **Server-sent events, through the front server,** for a slice job
  ([Progress](../front/README.md#progress)). Whether a page follows a delivery job on a
  stream too, or by short requests, is undecided
  ([Printers, from phase 5](#printers-from-phase-5)).
- **The front server follows every slice job itself,** holding the slice service's own
  progress stream whether or not a page is open, and feeds the streams it serves to pages
  from that one, so three tabs watching one slice job cost the slice service one
  connection
  ([The front server follows every slice job itself](../front/README.md#the-front-server-follows-every-slice-job-itself)).
- **What a report holds.** The stage and the percentage are Orca's own, passed through,
  with the time taken and the slice service's estimate of the time left; nothing is
  invented. A waiting slice job's report says how many slice jobs are ahead of it (those
  running and those waiting before it), and a new report is sent when that number
  changes ([Report progress](../slice/README.md#report-progress)).
- **A comment line at least every fifteen seconds** while there is nothing to report,
  because Railway closes a request after fifteen minutes, or after five without data, and
  Cloudflare after 125 seconds without data
  ([Progress streams](../docs/architecture.md#progress-streams)).
- **The latest progress report at once** to a stream that connects late, so a page that
  reconnects catches up in one event.
- **How it ends:** finished; an error report; cancelled by the user; cancelled by a later
  slice of the same user; or cancelled because the slice service was asked to stop.
- **Finished only once stored.** The front server reports a slice job finished only once
  its sliced file is in the state bucket, since that is where the page fetches it from (a
  choice the owner has not yet confirmed:
  [Choices the owner has not yet confirmed](../front/README.md#choices-the-owner-has-not-yet-confirmed)).
- **Reconnecting.** The page reopens a stream silently whenever it closes, including at
  every restart of the front server. What it does when a stream cannot be reopened is
  undecided; recommended, a stream that has failed to reopen for 20 seconds, or that is
  open and has carried nothing for 45 seconds, is treated as a failed request, which
  rests on the comment line above
  ([A progress stream that cannot be reopened](../wizard/README.md#a-progress-stream-that-cannot-be-reopened)).
- **The fallback.** If Cloudflare or Railway turns out to hold server-sent events back,
  the page asks for the latest progress report every second or two instead
  ([Whether progress arrives as it is sent](../front/README.md#whether-progress-arrives-as-it-is-sent)):
  (*proposed*) by the request for asking about a slice job, and from phase 5 by one that
  answers a delivery job's latest progress report.

## The sliced file

- **Fetched through the front server,** from the state bucket's copy, the one everything
  uses: for the Preview step and for the download. The browser never stores a sliced file
  and no request takes one from a browser. *Proposed*: it passes through the front server
  in pieces and is never held whole in its memory
  ([The front server follows every slice job itself](../front/README.md#the-front-server-follows-every-slice-job-itself)).
- **Its summary,** which the slice service gives beside the file (the predicted print
  time, the filament used, the layer count and the warnings;
  [the sliced file](sliced-file.md#summary)), is kept by the front server beside the file
  in the state bucket, for as long as the file, and served with it, since the Preview
  step needs it after the slice container has deleted its copy. The Preview step shows
  the print time and the filament from it, and its warnings in amber
  ([The result](../wizard/README.md#the-result)).
- **How long it is kept.** A sliced file can be previewed, downloaded, sent and sent again
  after a print until two hours after its slice ended or two hours after its last print
  ended (the end of the latest delivery job that used it), whichever is later; before
  phase 5 nothing is printed, so two hours after the slice ended is the whole rule. Past
  that it is answered with the front server's error report saying it has expired, and
  deleted; the front server also sweeps at intervals for files nobody asks for
  ([How long a sliced file lives](../front/README.md#how-long-a-sliced-file-lives)).
- **The moment it expires.** The page must know the moment at which the front server will
  refuse the sliced file, as the front server reckons it, so that it can show at that
  moment that the plate's slice has expired; it must not work it out from its own clock,
  which may be wrong
  ([A sliced plate that expires](../wizard/README.md#a-sliced-plate-that-expires)). How
  the page learns it is undecided; recommended, the front server sends the moment with
  the sliced file's summary and again when a print of the plate ends, written into these
  requests before phase 2
  ([Telling the page when a sliced file expires](../front/README.md#telling-the-page-when-a-sliced-file-expires)).
- **The backstop.** A three-day rule at Cloudflare R2 deletes any sliced file the front
  server failed to delete. Sending a sliced file stores it afresh, which restarts the
  rule's count, so the backstop runs from the last send. A send, a preview or a download
  whose sliced file has gone is answered with the error report saying the sliced file has
  expired and the plate must be sliced again
  ([Why R2's own rule cannot do this alone](../front/README.md#why-r2s-own-rule-cannot-do-this-alone)).

## The configuration

- **Read whole whenever the wizard asks,** always for the current group: when a page
  opens, and so after every sign-in, and when the user presses the reload glyph beside the
  current group's name. A group with no document gets the built-in default
  ([Reading it and writing it](../front/README.md#reading-it-and-writing-it)).
- **Written whole, on the condition that it has not changed** since it was read. A write
  that fails the condition is refused with an error report saying the configuration was
  changed by someone else and to reload; nothing is merged. So (*proposed*) the answer to a
  read carries a marker of the document's version, and a write names the marker it was
  based on. The write is built in phase 2, though nothing in the wizard uses it until the
  edit screens exist.
- **A document that cannot be understood** (damaged, or of a format the front server does
  not know) is answered with the front server's error report and is never replaced by
  the default, so the group cannot slice until the document is mended (a choice the owner
  has not yet confirmed). What the wizard shows then is undecided
  ([A configuration that cannot be read](../wizard/README.md#a-configuration-that-cannot-be-read)).
- **Its shape** is [the configuration's contract](configuration.md). The Layout step
  reads from it the plate's size and height, from the printer's Orca profile it names;
  the Settings step, each filament's colour, its profiles under the group's own names,
  and each profile's purpose ([The Settings step](../wizard/README.md#the-settings-step)).
- **The list of settings for advanced mode.** Advanced mode needs every setting the slice
  service accepts, with its section and setting group, its kind, its range or choices,
  and the chosen profile's own value. Where the list comes from is undecided, and is to
  be answered before phase 2. Recommended: the slice service supplies it and the front
  server passes it to the wizard, on a request made when advanced mode opens, keeping no
  copy from one start to the next, so that the list always matches the slice service
  that is running. The same answer gives the front server the profile catalog's names,
  against which it checks the configuration when it starts and when a configuration is
  edited
  ([The list of settings and the profile catalog's names](../front/README.md#the-list-of-settings-and-the-profile-catalogs-names),
  [the slice service's item](../slice/README.md#where-the-wizard-gets-the-list-of-settings-and-the-profile-catalogs-names)).

## Reporting a failure in the browser

Failures that happen only in the browser reach no server: a part the slice service
accepted and the page cannot draw, storage refused, full or cleared, a lost 3D drawing
context, the page's own code failing. Whether the page reports them is undecided
([Failures in the browser that reach no log](../wizard/README.md#failures-in-the-browser-that-reach-no-log)).
Recommended in both guides: one request by which the page reports such a failure, saying
what failed, on which step, the page's version, the browser's name and version, whether 3D
is drawn in software, and the hash of the part concerned, never a part's bytes or
geometry or the contents of the storage. It carries the wizard's mark like any request
that changes something; the front server writes one log line for each and limits how
many one page may send, and a report that cannot be sent is dropped, never retried into a
loop ([What the wizard's guide asks of the front server](../front/README.md#what-the-wizards-guide-asks-of-the-front-server)).

## Printers, from phase 5

All of these pass through the front server to the relay of
[printer delivery](../delivery/README.md), with the signed-in user and the current group,
already checked against the cookie
([Running the relay](../front/README.md#running-the-relay-from-phase-5)).

- **The printer's status,** for the printer-status icon, the printer details and the Send
  step: free (no print, or its last print ended), sending, starting, heating or printing
  with percent, layer of total and time left, waiting for a person, failed, offline (no
  sync within 2 minutes), not heard from yet (paired, and nothing heard since the front
  server started or since pairing, which the page shows as a grey dot and "…"), or no
  printer paired. A running delivery job's report is marked stale when the daemon's last
  sync was more than 40 seconds ago
  ([The printer-status icon](../wizard/README.md#the-printer-status-icon),
  [The stages](../delivery/README.md#the-stages-what-a-user-sees-and-what-can-be-cancelled)).
  It also carries:
  - the printer's display name from the paired-printer record; where that name comes from
    is undecided
    ([Where the name of the printer comes from](../wizard/README.md#where-the-name-of-the-printer-comes-from));
  - who sent the print going on, a one-line description of its plate, and how the last
    print ended (its sender, its end time and, for a failure, its layer)
    ([In phase 5: records in a store](../delivery/README.md#in-phase-5-records-in-a-store-the-front-server-supplies)).
    Who writes the description is undecided; proposed, the front server, from the plate
    configuration, keeping it beside the sliced file until the send
    ([Who writes the one-line description of a plate](../wizard/README.md#who-writes-the-one-line-description-of-a-plate));
  - a print started at the printer's own screen, as a print with no sender and no
    description, with what the printer reports of it;
  - for an offline printer, how long it has been silent. The relay writes the time of the
    daemon's last sync to the paired-printer record once, when the daemon goes offline,
    so the page can say "Not heard from for 7 minutes." even after a restart of the front
    server. After a restart, a paired daemon not heard from within two minutes of the
    front server starting, for which the record holds no time, is answered as silent for
    at least the time since the front server started, and the page says "at least".
    Whether the relay clears the recorded time when the daemon syncs again is undecided
    ([Clearing the recorded time of silence](../delivery/README.md#clearing-the-recorded-time-of-silence)).
- **Following a print.** A page follows its user's delivery job on a progress stream or
  by short requests; which is undecided, and the front server's guide recommends short
  requests for a print
  ([How many users at once](../front/README.md#how-many-users-at-once-and-what-happens-when-the-threads-run-out)).
- **Sending.** A send is accepted when the current group has a paired-printer record and
  the printer could start now, and its delivery job goes to the daemon that record names.
  Nothing queues: a send to a printer that is printing, or while another delivery job is
  on its way, is refused, whoever started the print. Each refusal is printer delivery's
  error report, with its sentence of what is in the way
  ([When a send is accepted](../delivery/README.md#when-a-send-is-accepted)). The
  delivery job's record names the sliced file it used, which is how the front server
  knows when a sliced file's last print ended; and the send stores the sliced file
  afresh (see [The sliced file](#the-sliced-file)).
- **Cancelling a send** is allowed until the relay allows the print to start. From that
  moment a cancel is refused with printer delivery's sentence: that the start command
  may already have been sent, or has been sent, so the plate can no longer be cancelled
  from here; neither says that the print started
  ([Cancelling](../delivery/README.md#cancelling)).
- **"Stop following"** a delivery job past the start whose report is stale, open to every
  user of the group. It ends the delivery job with the sentence that contact was lost and
  how the print ended is not known, and lets the relay accept the next send once the
  daemon is back and the printer is free. It is refused while the printer reports the
  print again ([Stop following](../delivery/README.md#stop-following)).
- **The user's live delivery job and last print** (the request *proposed*). A page that
  has lost its state asks for the signed-in user's live delivery job and that user's last
  print, since the browser's storage holds no delivery job's id. The page opens on the
  Send step while its plate is stored and has a delivery job, running or ended
  ([Coming back to running work](../wizard/README.md#coming-back-to-running-work)).
- **Typing a pairing code.** Any signed-in user of the group may type it, from any
  computer. When a daemon is offering the typed code, the relay writes the paired-printer
  record for the user's current group. When none is, the answer, at once, is printer
  delivery's sentence that no daemon is showing that code and to try again in a moment;
  every wrong code gets that one answer, whatever was wrong with it, and so does a right
  code typed in the half minute after the front server restarts. Wrong attempts are
  limited for each user, and too many are refused with printer delivery's sentence naming
  the wait (*proposed*: ten wrong codes a minute;
  [The rate limits of phase 5](../delivery/README.md#the-rate-limits-of-phase-5))
  ([Pairing in phase 5](../delivery/README.md#pairing-in-phase-5),
  [Pairing a printer](../wizard/README.md#pairing-a-printer)). What happens when a group
  that already has a paired-printer record types a second code is undecided; recommended,
  it is refused with a sentence telling the user to unpair first
  ([Pairing again: three cases](../delivery/README.md#pairing-again-three-cases)).
- **Unpairing** removes the current group's paired-printer record; any user of the group
  may do it. The wizard does not offer it while a print that PenguinSlicer is following is
  going on. Whether the relay itself refuses it then is undecided; recommended, it
  refuses while a delivery job of that group has not ended
  ([Unpairing while a delivery job has not ended](../delivery/README.md#unpairing-while-a-delivery-job-has-not-ended)).
