# The front server: the design in full

Nothing of the front server is built. This whole document is the design, written for
whoever builds it. The guide for a human reader is [README.md](README.md); each section
here goes deeper into the section of the same subject there.

Names and figures marked *proposed* below are this guide's suggestions; the design
approved by the owner does not fix them, and the phase's design spec settles them.

The **front server** is the one process the internet reaches. It serves the wizard's
pages, signs users in with Onshape, passes parts and slice jobs to the slice service,
stores and serves sliced files, reads and writes each group's configuration, gathers the
log, and from phase 5 hosts the relay. It is a component of its own, in `front/`; the
**wizard** is the code that runs in the browser, in `wizard/`
([the wizard's guide](../wizard/README.md)). What passes between the two is to be fixed in
[the contract between the wizard and the front server](../contracts/wizard-front-server.md),
which is not written yet; this document names routes by what they do, and the contract
gives their paths and shapes. The phases are those of
[the plan](../docs/plans/penguin-slicer-plan.md): phase 2, one machine; phase 3, hosted on
Railway; phase 4, inside Onshape; phase 5, the real printer.

## Contents

- [Where the front server sits](#where-the-front-server-sits)
- [Onshape sign-in](#onshape-sign-in)
- [The cookie](#the-cookie)
- [Groups and the current group](#groups-and-the-current-group)
- [Calls to Onshape](#calls-to-onshape)
- [Requests from other sites](#requests-from-other-sites)
- [The development identity](#the-development-identity)
- [The user key](#the-user-key)
- [Parts and slice jobs, passed to the slice service](#parts-and-slice-jobs-passed-to-the-slice-service)
- [Following slice jobs and storing sliced files](#following-slice-jobs-and-storing-sliced-files)
- [Two hours, deleting, and the backstop](#two-hours-deleting-and-the-backstop)
- [The configuration](#the-configuration)
- [The bucket interface](#the-bucket-interface)
- [The log](#the-log)
- [The version on every answer](#the-version-on-every-answer)
- [Stopping](#stopping)
- [Threads](#threads)
- [Hosting the relay, from phase 5](#hosting-the-relay-from-phase-5)
- [Error reports](#error-reports)
- [The fast suite](#the-fast-suite)
- [By phase](#by-phase)

## Where the front server sits

One address, `https://penguinslicer.popcornpenguins.com/`, serves the wizard's pages, the
address a daemon is given for the relay, and the redirect address of the Onshape app ([the architecture](../docs/architecture.md)). The browser and the daemons talk only
to the front server, and the front server calls the slice service over Railway's private
network, so the slice service's HTTP interface is not reachable from the internet and the
browser never makes a cross-origin request ([the architecture](../docs/architecture.md),
[the slice service](../slice/README.md)).

Because the slice service runs in a container of its own, the **slice container**, which
holds no credentials, the front server must pass parts and slice jobs through, fetch each
sliced file, and fetch the slice service's log lines from a route of the slice service
([the architecture](../docs/architecture.md)).

What must last is in two object stores at Cloudflare R2: the **state bucket** (each
group's configuration and paired-printer record, the sliced files, a record of each
delivery job) and the **log bucket** (log lines and daemon telemetry, as files). The front
server holds the one credential that writes to the buckets; beyond it, only the
owner can write, through Cloudflare's own console
([the architecture](../docs/architecture.md)).

The front server keeps no database and no table of sessions. Everything it must remember
across a restart is in the state bucket or in the browser.

**Secrets.** Four of PenguinSlicer's six secrets are environment variables of the front
server, set in Railway: the Onshape app's client id and secret, the cookie key (which
encrypts the cookie, below), the
relay's secret key, and the credential with which it reads and writes both buckets. None
is in the repository, a bucket, a log line or a page
([the architecture](../docs/architecture.md)). Replacing any of them changes a setting of
the front server, which restarts as at any deploy. The Onshape app's secret is replaced by
a new secret for the same app from Onshape's developer portal; no cookie depends on it, so
nobody is signed out. Whether the old secret stops working the moment it is replaced,
which would fail sign-ins until the front server has the new one, and whether, from
phase 4, tokens issued under the old secret can still be renewed, were not checked
([the architecture](../docs/architecture.md)).

## Onshape sign-in

Every user signs in with Onshape's OAuth, the same way in Onshape's panel and outside it,
through one Onshape app. Onshape tells the front server who the user is and which
companies and classrooms they belong to; those are the user's groups, or the user alone
when there are none. No other sign-in is offered, so PenguinSlicer keeps no accounts and
no passwords and never has to decide whether two sign-ins are the same person.

A **group** is the users who share one configuration and one printer: one Onshape company
or classroom, named by Onshape's id for it; a user who belongs to none is a group of one,
named by the user's Onshape id ([the plan](../docs/plans/penguin-slicer-plan.md)).

The sign-in, step by step:

1. A request arrives with no cookie that the front server can read. The sign-in route
   sends the browser to Onshape's authorization page with a value of its own making
   (*proposed*: OAuth's `state`, which it also remembers in the browser for the
   callback).
2. Onshape sends the browser back to the callback route at
   `https://penguinslicer.popcornpenguins.com/`. The callback checks that the value
   Onshape returns is the one it sent out, and refuses the sign-in otherwise.
3. The front server reads who the user is and their companies and classrooms. A sign-in
   makes 2 calls to Onshape in all (see [Calls to Onshape](#calls-to-onshape)).
4. It sets [the cookie](#the-cookie), reads the configuration of the user's groups
   (see [The configuration](#the-configuration)), and writes the sign-in's log line (see
   [The log](#the-log)).

**Groups are read at sign-in.** A person the front server has not seen has no cookie,
signs in, and their groups are read then. How often a signed-in user's groups are read
again is a setting (see [Groups and the current group](#groups-and-the-current-group)).

**Sign in again.** The wizard's header has a "sign in again" action beside the current
group's name. It runs the sign-in afresh, which reads the groups again for two calls; a
user added to an Onshape company after signing in sees the new group only after it
([the wizard](../wizard/README.md)).

**Inside Onshape's panel**, sign-in and the stored parts depend on Chrome allowing cookies
and storage to an embedded page ([the wizard](../wizard/README.md)). Safari is not
supported.

**What Onshape answers for an account with no company or classroom** was not checked
([the architecture](../docs/architecture.md)). The design says such a user is a group of
one, named by the user's Onshape id; the sign-in must reach that result from whatever
Onshape does answer, and the first such account tried settles it.

### Which routes need a signed-in user

Every route of the front server refuses a request without a signed-in user, with three
exceptions:

- the sign-in routes themselves (start, callback);
- from phase 5, the daemon's routes, which carry the daemon's token instead;
- from phase 5, the one request by which a daemon without a token offers its pairing
  code. It is limited to sixty a minute for the whole relay and also counted for each
  address Cloudflare reports it came from ([printer delivery](../delivery/README.md)).

A request for one of the wizard's pages without a signed-in user starts the sign-in; any
other route answers with an [error report](#error-reports).

### Tests

- A request with no cookie, to every route but the three exceptions, is refused; the test
  enumerates the routes from the application itself, so a new route cannot be missed.
- The callback with a `state` value other than the one sent out is refused, and
  (*proposed*) the refusal is logged as a failed sign-in.
- The callback when the stand-in for Onshape refuses the code, and when it does not
  answer, each produce their error report.
- A sign-in against the stand-in for Onshape makes exactly two calls, sets the cookie, and
  writes the sign-in line.
- A user the stand-in reports with no company or classroom becomes a group of one, named
  by the user's Onshape id.
- "Sign in again" reads the groups afresh: a group added in the stand-in appears in the
  new cookie.

## The cookie

A sign-in sets one cookie in the browser, **the cookie**. It holds the user's identity
(the user's Onshape id and name), their groups (each group's id and name) and their
Onshape tokens (the access token and the refresh token). It is encrypted, so the browser
can neither read nor change it.

**Thirty days.** The cookie lasts thirty days, long enough that signing in, which costs
calls to Onshape, is rare. *Proposed*: the thirty days count from the sign-in, and
rewriting the cookie (for renewed tokens or a new cookie key, below) keeps its end. This is what makes the
groups in a cookie stand for at most thirty days, which
[Groups and the current group](#groups-and-the-current-group) relies on.

**No session on the server.** Nothing about a session is kept on the front server; the
cookie is the whole of it, and the cookie key is a setting of the front server, not
something in its memory. So a restart signs nobody out.

**Embedded pages.** Inside Onshape's panel the page is embedded in another site, so the
cookie must be one that browsers send to an embedded page: in Chrome, a cookie marked
(*proposed*) `SameSite=None` and `Secure`. That is why the cookie alone does not prove a request came
from the wizard (see [Requests from other sites](#requests-from-other-sites)).

**Onshape's tokens.** Onshape's access token lasts an hour. It is renewed with its
refresh token only when a call to Onshape needs one, and the renewed tokens are written
back to the cookie. Before phase 4 nothing needs one, unless the Onshape app is public by
then, when reading the groups again does (see
[Groups and the current group](#groups-and-the-current-group)). Two requests renewing the
tokens at once must not leave a spent refresh token in the cookie.

**Size.** A browser cookie holds about 4 KB, and the cookie must carry the identity, the
groups and both Onshape tokens, encrypted. That it fits was not checked
([the architecture](../docs/architecture.md)); a user with many groups is the case to
measure.

### Two cookie keys, and replacing one

The **cookie key** is the secret that encrypts the cookie. The front server holds two: the
current one, and the previous one for reading only. A cookie read with the previous key is
written back with the current one, keeping its end (*proposed*, as above). The front server writes a log line
each time the previous key is used.

A planned replacement: the current key becomes the previous one and a new key becomes
current, which is a change of the front server's settings and so a restart. The previous
key is removed after one week, so a user who does not open PenguinSlicer in the week after
the cookie key is replaced signs in again; with no replacement under way that limit does
not apply. In an emergency, when the key has leaked, it is replaced and not kept as the
previous key, and every user signs in again. The steps are written down in the repository
as a procedure ([the architecture](../docs/architecture.md)).

### Tests

- A cookie made with the current key is read; one changed by a single byte, or made with
  an unknown key, is treated as no cookie (*proposed*).
- A cookie made with the previous key is accepted, written back with the current key with
  the same end, and the use of the previous key is logged.
- A cookie past its thirty days is treated as no cookie (fake clock, no real waiting).
- A rewrite does not move the cookie's end.
- Two requests that renew the tokens at once, against the stand-in for Onshape, leave a
  cookie holding a refresh token the stand-in still accepts.
- The cookie of a user with the largest number of groups the tests choose stays under
  4 KB, or the test reports the size it reached.
- A restart of the front server with the same keys keeps every cookie readable.

## Groups and the current group

A user who belongs to several groups uses one at a time, the **current group**: the one
group, of those a user belongs to, whose configuration and printer the user is using now.
The wizard's header names it and the user changes it there; the choice is kept in the
browser and sent with each request ([the wizard](../wizard/README.md)).

**The check against the cookie.** The front server accepts a current group only if the
cookie lists that group among the user's. Every request that acts for a group carries the
current group and makes this check:

- reading and writing the configuration;
- uploading a part, submitting a plate configuration, asking about, following or
  cancelling a slice job, and fetching a sliced file;
- from phase 5, pairing, sending, following a delivery job and the printer's status,
  stopping following, cancelling a delivery job, and unpairing.

A request that needs no group carries none: the wizard's pages, the sign-in routes, and
the request for the user and their groups (below). A request that needs a group and names none, or names one
the cookie does not list, is refused with an error report and (*proposed*) logged as a
refusal. The check is what keeps a user from another group's configuration and printer: a
print is started only by a signed-in user whose current group has a paired-printer record
naming the daemon ([the architecture](../docs/architecture.md)). It is also what makes the
group in each log line about a slice or a send a group the user belongs to (see
[The log](#the-log)).

**The user and their groups.** The cookie is encrypted, so the page cannot read from it
who the user is or which groups they belong to. A route (*proposed*) answers the
signed-in user's name and their groups, each with its id and name, from the cookie, so
the wizard can offer a current group. It needs a signed-in user and no current group, and
makes no call to Onshape.

**Reading the groups again.** How often a signed-in user's groups are read again from
Onshape is a setting. Until the Onshape app is public it is "never": the groups in the
cookie stand until the cookie ends. Once the app is public the setting becomes one day.
So a user removed from an Onshape company keeps its configuration and its printer for up
to thirty days while the setting is "never", and loses both within a day once it is one
day; both are accepted. Reading the groups again needs a fresh access token, so it renews
the tokens and writes them back to the cookie.

### Tests

- On every route that acts for a group, one test each, a request naming a group the
  cookie lists is accepted; one naming another group, or none, is refused with its error
  report and a refusal line. The test enumerates those routes from the application, so a
  new one cannot be missed.
- The request for the user and their groups, with no current group, answers the cookie's
  user and groups.
- With the setting "never", no request reads the groups again, however old the cookie
  (fake clock).
- With the setting one day, the first request after a day reads the groups again from
  the stand-in, renews the tokens, and a group removed in the stand-in is gone from the
  rewritten cookie.

## Calls to Onshape

Until an Onshape app is public in Onshape's App Store, its calls count against a yearly
allowance of the account that owns it: 2,500 a year on a free or education account. The
owner intends to make the app public; until then, development and testing with
users must fit inside that allowance with room to spare
([the plan](../docs/plans/penguin-slicer-plan.md)). **The rule is that nothing calls
Onshape that can be done without it.**

| Use | Calls to Onshape |
|---|---|
| Work on one machine, with the development identity | None |
| The automated tests, which use a stand-in for Onshape | None |
| A sign-in to the hosted service | 2, once in thirty days for each browser |
| Reading a user's groups again | None until the app is public |
| Reading parts from Onshape, in phase 4 | Several for each part; counted in phase 4's design before it is built ([the plan](../docs/plans/penguin-slicer-plan.md)) |

So until phase 4, twenty people using the hosted service for two months spend about 80
calls. Once the app is public, reading the groups again once a day, and renewing the
tokens to do it, also make calls, but a public app's calls do not count against the
allowance ([the architecture](../docs/architecture.md)).

**Every call is counted.** The front server writes a log line for each call it makes to
Onshape, and the command that reads the log bucket reports the year's total.

**Not known** ([the architecture](../docs/architecture.md)): what allowance the
owner's account has; whether a second Onshape app of the same account, registered for
development, would draw on the same allowance as the hosted one; and whether renewing a token counts as a
call, which matters from phase 4.

### Tests

- The whole fast suite runs with no route to Onshape at all: the client for Onshape is
  given the stand-in, and (*proposed*) a test fails if any other client is built during
  the suite.
- Each call to the stand-in writes exactly one log line naming the call.
- A sign-in writes two such lines.

## Requests from other sites

Inside Onshape's panel the cookie is one that browsers send to an embedded page, so the
cookie alone does not prove a request came from the wizard. So:

- **Every route that changes something on the strength of the cookie** also requires a
  header that only the wizard's own page can set, and checks the request's origin
  (*proposed*: the `Origin` header must be the front server's own address). These routes
  are (*proposed* list) uploading a part, submitting a plate configuration, cancelling a
  slice job, writing the configuration, and from phase 5 pairing, sending, stopping
  following, cancelling a delivery job and unpairing.
- **No route allows cross-origin requests**: the front server (*proposed*) sends no header
  that would let another site's page read its answers.
- **The sign-in callback checks the value it sent out** (see
  [Onshape sign-in](#onshape-sign-in)).
- **The pages may be embedded by Onshape only**: every page carries (*proposed*) a
  `Content-Security-Policy` whose `frame-ancestors` names Onshape's address alone.

### Tests

- Each changing route refuses a request with a valid cookie but no header, and one whose
  origin is another site, each with its error report and a refusal line.
- No answer of any route carries an `Access-Control-Allow-Origin` header, including the
  answer to a preflight request.
- Every page's answer names only Onshape's address in `frame-ancestors`.

## The development identity

The **development identity** is a fixed made-up user and group that the front server signs
in when a setting tells it to, for work on one machine
([the plan](../docs/plans/penguin-slicer-plan.md)). On one machine there is no Onshape app
to redirect to, so with the setting on, the sign-in route sets the cookie for the
development identity at once, with no call to Onshape. Its user's Onshape id is the user
key of everything done under it, and its group is the only group in its cookie.

**It can never be on in the hosted service.** The command that launches the hosted front
server never sets the setting, and the front server refuses to start with it on when it
finds itself on Railway (*proposed*: by the environment variables Railway sets in its
containers) or finds Onshape credentials in its environment. A refusal to start
(*proposed*) writes one log line saying why and ends the process with a failure status.

### Tests

- With the setting on, the sign-in route sets the development identity's cookie and the
  stand-in for Onshape receives no call.
- With the setting on and a Railway variable present, the front server does not start.
- With the setting on and an Onshape client id or secret present, it does not start.
- The hosted launch command, read from the repository, does not set the setting.

## The user key

The **user key** is the signed-in user's Onshape id, which the front server passes to the
slice service with every request to say whose part or slice job it is; the slice service
compares user keys and never interprets them
([the plan](../docs/plans/penguin-slicer-plan.md), [the slice service](../slice/README.md)).

The front server sets the user key from the cookie, and only from the cookie. The browser
cannot name one: a user key in a request from the browser, in any field or header, is
never read. So a user reaches only their own parts, slice jobs and sliced files. A request
for a slice job or a sliced file that is not the user's is (*proposed*) answered as for
one that does not exist, so nobody learns whether another user's id exists; when the slice service
reports that the slice job belongs to another user key, the front server logs it as a
refusal of a request for something that belongs to another user.

### Tests

- A request carrying another user key in its body or headers reaches the stand-in for the
  slice service with the cookie's user key.
- A request for another user's slice job, and for another user's sliced file, is answered
  as unknown and writes a refusal line.

## Parts and slice jobs, passed to the slice service

The slice service's HTTP interface is reached only from the front server
([the slice service](../slice/README.md)). The front server passes each request on with
the user key and passes the answer back, error reports included (*proposed*: unchanged).

**Parts.** The wizard uploads each part by itself at the moment the user adds it, in one
request of at most 7.5 MB, the plate configuration's limit for one part
([the wizard](../wizard/README.md)). The front server passes the part to the slice service
with the user key. The slice service checks it as it arrives and keeps it in its **part
store** (its folder of uploaded parts, each kept for two hours after it was last used)
under the user key and the SHA-256 hash of its bytes; a part that cannot be sliced is
refused there, and its error report reaches the page, which shows it on the Parts step
as a notification and does not add the part
([the wizard's guide](../wizard/README-details.md#uploading-each-part-when-it-is-added)). The front
server keeps no copy of a part; the browser's storage is the record of a user's parts
([the wizard](../wizard/README.md)). Cloudflare allows a request 100 MB; Railway's limit on a
request body is not stated in its documents, and one real upload of a 7.5 MB part settles
it ([the architecture](../docs/architecture.md)).

**Slice jobs.** On the Preview step the page sends a **plate configuration** (the layout,
the settings, and the hash of each part, with no files). The front server passes it on
with the user key, and the slice job waits or runs in the slice container. A user has one
unfinished slice job at a time: submitting a plate cancels the user's earlier unfinished
slice job ([the slice service](../slice/README.md)). When the plate names a part no longer
in the part store, the slice service's error report lists the missing hashes and the front
server passes it back, so the page uploads them again and submits again. When no more
slice jobs may wait, the slice service's "busy" error report is passed back likewise. The
front server also passes on a cancel of a slice job.

**Asking about a slice job.** A page that has lost its state asks the front server about
the slice job whose id it kept ([the wizard](../wizard/README.md)). The front server asks
the slice service, which remembers a slice job for two hours after it ends
([the slice service](../slice/README.md)), and looks for the sliced file in the state
bucket. It answers one of: still waiting or running; finished, with its sliced file in the
state bucket; ended in an error, with the error report; cancelled by a later slice of the
same user; or unknown. The page decides from the time it kept what an unknown slice job
means.

**Progress streams.** A **progress stream** is the connection, of server-sent events, on
which a page follows a slice job or (from phase 5) a delivery job. The browser follows
both through the front server. Its stream carries the slice service's progress reports
([the progress report](../contracts/progress-report.md)): for a waiting slice job, how many
are ahead of it. Railway closes a request after fifteen minutes, or after five without
data, and Cloudflare after 125 seconds without data, so every progress stream sends a
comment line at least every fifteen seconds while it has nothing to report
([the slice service](../slice/README.md)), and the page reconnects when one closes. A
progress stream that connects late gets the latest progress report at once. The front
server (*proposed*) reports a slice job finished on the stream only once the sliced file
is in the state bucket, because that is where the page fetches it from.

Whether Cloudflare and Railway pass server-sent events on without holding them back was
not checked. If one does hold them, the page asks for the latest progress report every
second or two instead, by a route both interfaces have
([the architecture](../docs/architecture.md)); (*proposed*) the front server's route for
asking about a slice job is that route.

### Tests

- An uploaded part reaches the stand-in for the slice service with the cookie's user key,
  and the stand-in's refusal reaches the page unchanged.
- A plate configuration reaches the stand-in with the user key; its error report listing
  missing hashes, and its "busy" error report, reach the page unchanged.
- Asking about a slice job gives each of the five answers, one test each.
- A progress stream with nothing to report sends a comment line within fifteen seconds of
  fake time.
- A progress stream opened after the slice job started gets the latest progress report as
  its first event.
- A finished slice job is reported finished on the stream only after the sliced file is
  in the state bucket.
- The slice service not answering gives the page a retryable error report.

## Following slice jobs and storing sliced files

**The front server follows every unfinished slice job itself**, whether or not a page is
open: for each one it holds the slice service's own progress stream. That is how it learns
that a slice has ended; (*proposed*) the pages' progress streams are served from what it
follows.

**When a slice ends**, the front server fetches the sliced file from the slice container
and stores it in the state bucket under the user key and the slice job's id, with
(*proposed*) the time the slice ended. It then (*proposed*) tells the slice service it has
stored the file, and the slice container deletes its own copy ([the slice service](../slice/README.md)). A sliced file is
8.8 to 14.1 MB on the plates measured so far. The front server stores the sliced file's
summary ([the sliced file](../contracts/sliced-file.md#summary)) beside it in the state
bucket, fetched with the file before the slice service is told, and serves both (added
after the approved design: the Preview step needs the summary after the slice container
has deleted its copy).

**The state bucket's copy is the one everything uses.** The browser fetches it through the
front server to draw the Preview step and to offer the download, and from phase 5 the
relay hands it to the daemon. The browser does not store the sliced file and never uploads
one, so (*proposed*) the front server has no route that takes a sliced file from a browser, and a
printer only ever receives a file the slice service made
([the wizard](../wizard/README.md)).

**When the front server starts**, it asks the slice service for its slice jobs, by the
route that lists them ([the slice service](../slice/README.md)). It follows the unfinished
ones and collects each finished one whose sliced file it has not yet stored. So a slice
that was running across a restart of the front server is stored when it ends.

### Tests

- A slice job that ends with no page following it has its sliced file in the state bucket
  under the user key and the slice job's id, and the stand-in for the slice service was
  told it was stored.
- A front server started while the stand-in holds one unfinished and one finished,
  unstored slice job follows the first and stores the second.
- A finished slice job whose sliced file is already in the state bucket is not fetched
  again at start.
- (*proposed*) The slice service failing mid-fetch leaves nothing half-written in the
  state bucket, and the fetch is tried again.
- The page's fetch of a sliced file serves the state bucket's copy.

## Two hours, deleting, and the backstop

A sliced file can be previewed, downloaded, sent, and sent again after a print, until two
hours after its slice ended or two hours after its last print ended, whichever is later.
Its last print ended when the latest delivery job that used it ended (from phase 5;
before phase 5 nothing is printed, so the two hours after the slice ended are the whole
rule). A sliced file is **due** once both of those two hours have passed. The front server
enforces this:

- it refuses a sliced file that is due, with an error report (*proposed*: saying it has
  expired), and deletes it;
- it deletes each sliced file when it falls due, in (*proposed*) a regular sweep, so that
  a file nobody asks for again is gone on time too;
- from phase 5, a sliced file that a running delivery job uses is never due, since that
  delivery job has not ended; when it ends, the file is kept two hours more.

R2's own rule for deleting old files cannot do this alone: it counts in whole days, and
Cloudflare says a file is typically removed within 24 hours after it falls due. So a
three-day R2 deletion rule on the sliced files is set as well, to catch any file the front
server failed to delete. The rule counts from when a file was stored, so it is set at three
days to outlast the longest print and the two hours after it; a print that runs longer
than that loses its sliced file to the rule, and the user slices the plate again to send
it again. Such a file can rest at R2 for up to about four days after it was stored ([the architecture](../docs/architecture.md)).

### Tests

- With a fake clock, a sliced file one second under two hours after its slice ended is
  served, and one at two hours, never printed, is refused with its error report and
  deleted.
- The sweep deletes a file that fell due and leaves one that has not.
- A sliced file whose delivery job ended five hours after the slice is served one hour
  after that delivery job ended, and refused and deleted at two hours after it (phase 5).
- A sliced file used by a running delivery job is kept and served to the daemon past two
  hours after its slice (phase 5).

## The configuration

A group's **configuration** is one JSON document in the state bucket, read whole and
written whole; it holds the group's filaments (each with a colour, which the wizard shows
where the user chooses a filament and never uses in the layer preview, and with its
profiles, each under the group's own name and purpose), the printer's Orca profile (from
which the plate's size and height come) and the units of uploaded files, and no secret.
Its shape, with an annotated example, is in
[the configuration's contract](../contracts/configuration.md). A group's document is kept
until edited: an edit replaces it, and nothing else deletes it.

- **A default.** A group with no document gets a built-in default configuration, so a new
  group can slice without setting anything up.
- **Reading.** The front server reads the document when a user signs in and again when
  the wizard asks.
- **Writing.** An edit writes the whole document on the condition that it has not changed
  since it was read, so two users editing at once cannot silently overwrite each other;
  the second gets an error report telling them to reload. The front server reads the
  document's (*proposed*) version marker with the document and writes only if the state bucket's
  marker still matches.
- **The log.** Every edit writes a log line with the user's name and what changed.
- **A document that cannot be read** (*proposed*: not JSON, or not of a format number
  the front server knows) is answered with an error report, and (*proposed*) its contents
  are never written over by the default.

The configuration's edit screens are a feature of their own, in no phase yet, with a
design spec of their own
([the plan, Known future work](../docs/plans/penguin-slicer-plan.md#known-future-work)).
Until they exist, a group uses the default or a document the owner puts into the state
bucket through Cloudflare's console, following the annotated example. So the front server
must expect a document written by hand.

### Tests

- A group with no document gets the default.
- Two edits read from the same version: the first is written, the second is refused with
  its error report and the document holds the first.
- An edit writes a log line with the user's name and the change.
- A document that is not JSON, and one with an unknown format number, each produce their
  error report and are left as they are.

## The bucket interface

The front server reaches each bucket through one interface with two implementations: R2,
hosted, and a folder, on one machine. Both give (*proposed*) the same four things: read a file with its
version marker, write a file, write a file only if its version marker has not changed,
and delete a file. Each record the front server writes to the state bucket carries the
number of its format ([the contracts](../contracts/README.md)).

The fast suite runs against the folder implementation, in a temporary folder made for
each test. The R2 implementation is tested against R2's interface (*proposed*) in a suite
of its own, outside the fast suite.

### Tests

- The same set of tests runs against the folder implementation in the fast suite and the
  R2 implementation outside it: read, write, a conditional write that succeeds, one that
  fails because the file changed, delete.

## The log

The log must answer, without seeing a user's screen or computer, what went wrong, whether
the service is the right size, and who is using it
([the architecture](../docs/architecture.md)). Each log line is one JSON object carrying
the time, the component, and whichever of the group, user key, slice job, delivery job and
daemon it concerns.

**The front server's own lines:**

- each sign-in: the user key, the user's name and their groups;
- each call to Onshape;
- each edit of the configuration: the user's name and what changed;
- each use of the previous cookie key;
- every error a user is shown, with its code, the user key and name, the group and the job
  it belongs to ([the architecture](../docs/architecture.md));
- every exception, with its stack trace, including one that no user saw because the
  request was tried again;
- every refusal: a failed sign-in, a request for something that belongs to another user,
  and (*proposed*) a current group the cookie does not list and a request without the
  wizard's header or from another origin;
- every transition of a job it sees (*proposed* list: a sliced file stored, served,
  expired, deleted);
- once a minute, one line: the memory it holds, the slices running and waiting, the
  connections held open and the threads in use
  ([the architecture](../docs/architecture.md));
- its start, with the version that started.

Every line about a slice or a send carries the user key and the current group.

**Gathering.** The front server gathers its own lines and, from phase 5, the relay's. It
fetches the slice service's from a route on the private network, since the slice
container has no credential to write them itself ([the slice service](../slice/README.md)),
and adds the group to each, since the slice service knows only the user key: the front
server knows each slice job's group from the request that submitted it. About once a
minute it writes what it has gathered to the log bucket as a new file, newline-separated
JSON, files named by date and component. Every line also goes to the front server's
standard output, which Railway's log view shows as it is written and keeps seven days; the
log bucket keeps them ninety days. A crash loses the last minute of lines from the log
bucket, which stays only in Railway's log view.

No log line holds a secret, a token, a pairing code or a part's geometry.

### Tests

- Each kind of line above is written by a test that causes it, and holds the fields
  listed.
- With a fake clock, a minute's gathered lines are written to the log bucket as one new
  file named by date and component.
- Lines fetched from the stand-in for the slice service gain the group of their slice job.
- No line written during the whole fast suite contains the cookie, an Onshape token or a
  cookie key; the test searches every line for the values the suite used.

## The version on every answer

Every answer of the front server carries the front server's version (*proposed*: in a
header, errors and progress streams included). A page that sees a newer version reloads itself at the next
moment when nothing is in flight ([the wizard](../wizard/README.md)). A page loaded before
a deploy keeps working against the new front server, and a record in the state bucket
written by the old front server is read by the new one
([the architecture](../docs/architecture.md)).

### Tests

- Every route's answer carries the version, including an error report and the first event
  of a progress stream.
- Tests run the previous version's page against the new front server
  ([the architecture](../docs/architecture.md)).

## Stopping

Asked to stop (as at every deploy), the front server (*proposed*) stops accepting new
requests, finishes the uploads and downloads in progress, closes its progress streams,
from phase 5 answers its held syncs, and (*proposed*) writes the log lines it has gathered
to the log bucket, so
that pages and daemons reconnect to its replacement and only a crash loses log lines. It
has the time Railway allows a stopping container. How long that is, whether Railway starts
the new container before stopping the old, and whether it deploys the front server alone
when only its folders changed are not yet known; until tried, the design assumes a plain
stop and start ([the architecture](../docs/architecture.md)). The page retries every request it makes, so
a request that falls in the gap is repeated: a user sees nothing if the gap is under 20
seconds, a message that the server is being slow, with a countdown to the next attempt,
if it is longer, and an error only after 300 seconds
([the wizard's guide](../wizard/README-details.md#retrying-every-request)).

### Tests

- Each row of the table of what a restart of the front server does
  ([the architecture](../docs/architecture.md)) is a test that runs with the rest of the
  suite: the front server is stopped at that moment and started again, and the result
  checked.
- A stop during an upload lets the upload finish; a stop with a progress stream open
  closes it; a stop writes the gathered lines.

## Threads

The front server's server runs with 100 threads. From phase 5 it spends one thread on
every idle daemon, for the held wait of its sync, up to 55 seconds
([printer delivery](../delivery/README.md)), so it has room for about fifty idle daemons
beside the users' requests and progress streams (*proposed*: including the progress
streams it holds itself to follow slice jobs, which the approved design does not count). A small asynchronous server may take over the held
wait's route later and hold thousands of daemons; that is decided when the number of
daemons calls for it ([the plan](../docs/plans/penguin-slicer-plan.md)). What the front
server's memory is with fifty held syncs was never measured
([the architecture](../docs/architecture.md)).

### Tests

- The line written once a minute reports the threads in use and the connections held
  open, checked with a known number of open progress streams.

## Hosting the relay, from phase 5

The **relay** is the half of printer delivery that runs on the server; from phase 5 it
runs inside the front server's process, and the front server is its **caller**, the
application that runs it ([printer delivery](../delivery/README.md)). Hosting it means the
front server:

- **supplies its store.** The records of delivery jobs are kept in a store the relay's
  caller supplies: the state bucket hosted, a folder on one machine
  ([printer delivery](../delivery/README.md)).
- **supplies the sliced file from that store.** The relay takes the sliced file from the
  state bucket when the daemon fetches it, and keeps no copy of its own; the front server
  keeps a sliced file until two hours after its last print ended, if that is later than
  two hours after its slice ended
  ([Two hours, deleting, and the backstop](#two-hours-deleting-and-the-backstop)).
- **tells it who is asking:** the signed-in user and the current group, checked against
  the cookie. When a signed-in user types a code that a daemon is offering, the relay
  writes the paired-printer record for the user's current group; a send is accepted when
  the current group has a paired-printer record, and its delivery job goes to the daemon
  that record names ([printer delivery](../delivery/README.md)). When the group's daemon
  goes offline, the relay writes the time to the paired-printer record, once, so the
  printer's status can say how long the printer has been silent across a restart of the
  front server. *Proposed:* a send
  repeated with the same sliced file by the same user while its delivery job is live
  answers with that delivery job, where the code as built answers
  `delivery.job_in_flight`.
- **holds the relay's secret key**, with which the relay signs the daemons' tokens, as an
  environment variable; replacing it is the relay's procedure
  ([printer delivery](../delivery/README.md)).
- **answers the relay's held syncs when stopping** (see [Stopping](#stopping)) and gathers
  the relay's log lines (see [The log](#the-log)).

Limits on the rate of requests are counted for the signed-in user or the daemon
([printer delivery](../delivery/README.md)).

### Tests

- The front server's store implementation passes the relay's own tests of a store.
- A send from a current group with no paired-printer record is refused; one with a record
  reaches that record's daemon.
- A sliced file a delivery job needs is served to the daemon after two hours.
- A daemon going offline writes the time to its paired-printer record once; a restarted
  front server reports the same time for it.

## Error reports

Every failure a caller can see is an [error report](../contracts/error-report.md), with a
test that produces it on purpose. The front server passes the slice service's error
reports (`slice.*`) and, from phase 5, the relay's (`delivery.*`) to the page unchanged.
Its own failures are below. Each gets a stable code (*proposed*: of the form
`front.<what>`); the codes are named when
[the contract with the wizard](../contracts/wizard-front-server.md) is written, and listed
here then. The table's rows and each one's "Retryable" are *proposed*.

| Failure | When | Retryable |
|---|---|---|
| Not signed in | A route that needs a signed-in user, with no cookie, one that neither cookie key reads, or one past its thirty days | No |
| Sign-in failed | The callback's value is not the one sent out, or Onshape refused the sign-in | No |
| Onshape did not answer | At sign-in, or when reading the groups again | Yes |
| Group not allowed | The request names no current group, or one the cookie does not list | No |
| Not from the wizard's page | A changing route without the wizard's header, or from another origin | No |
| Configuration changed | The configuration was written by someone else since it was read; reload | No |
| Configuration unreadable | The group's document is not JSON or not of a known format number | No |
| Sliced file expired | Past two hours after its slice ended and two hours after its last print ended | No |
| Sliced file unknown | No sliced file of that slice job under the user's key | No |
| Slice service did not answer | The private network or the slice service is down | Yes |
| State bucket did not answer | Reading or writing the state bucket failed | Yes |

## The fast suite

The front server will be its own `uv` project, in `front/`, whose commands run with
`make -C front ...`, as every component's do.

Each section above lists the tests its subject needs. All of them follow the project's
rule for the fast suite: no real network, no real waiting and no fixed ports, passing in
any order and any number of times. So:

- **Onshape** is a stand-in that answers as Onshape's OAuth and its user and company
  calls do, and counts the calls it receives; no test calls Onshape.
- **The slice service** is a stand-in that answers as its HTTP interface does.
- **The buckets** are the folder implementation, in a temporary folder for each test.
- **Time** is a fake clock: thirty days, two hours, a minute and fifteen seconds pass at
  once.
- **Servers** that a test needs listen on a port the system chooses.

Every refusal, limit and state transition named in this document has a test that reaches
it and asserts what the caller sees.

## By phase

What of the front server is built in each phase, from
[the plan](../docs/plans/penguin-slicer-plan.md). The approved design does not place
every item: those marked *proposed* below are placed by this guide.

**Phase 2, one machine.** The front server, without the relay, runs beside one slice
service process on one machine, with the development identity. A folder stands in for
each bucket, behind the same interface. Built here:

- serving the wizard's pages;
- the development identity and the cookie it sets, with (*proposed*) one cookie key;
- the user key, and the check of the current group against the cookie;
- passing parts and slice jobs to the slice service, asking about a slice job, and the
  progress streams;
- following every unfinished slice job, storing its sliced file, collecting at start;
- the two-hour rule and deleting;
- reading and writing the configuration, with the default and the conditional write;
- (*proposed*) the log lines, gathered once a minute into the folder that stands in for
  the log bucket;
- (*proposed*) the version on every answer, which the wizard's reloading, built in this
  phase, needs.

**Phase 3, hosted.** The first thing tried is what Railway does at a deploy, since the
rest of restarts and deploys rests on it. Then:

- the front server in a container of its own on Railway, at
  `https://penguinslicer.popcornpenguins.com/`, calling the slice container over the
  private network;
- the state bucket and the log bucket at R2, with the three-day backstop rule;
- Onshape sign-in, with the stand-in for Onshape in the tests, counting every call;
- (*proposed*) the checks on requests from other sites;
- the second cookie key and the procedure for replacing one;
- the other rules for old and new versions together (a format number on each record in
  the state bucket);
- (*proposed*) finishing work in flight when asked to stop;
- (*proposed*) the refusal to start with the development identity on Railway.

**Phase 4, inside Onshape.** The panel uses the same sign-in and the same routes. Reading
parts from Onshape, and what that costs in calls to Onshape, is designed in phase 4.

**Phase 5, the real printer.** The relay joins the front server: pairing, the syncs and
the held wait, the records of delivery jobs in the state bucket, replacing the relay's
secret key, and daemon telemetry ([printer delivery](../delivery/README.md)). The front
server supplies the relay its store and the sliced files, answers held syncs when
stopping, gathers the relay's lines, and spends one of its 100 threads on each idle
daemon.
