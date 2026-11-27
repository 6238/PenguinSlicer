# The front server: the builder's document

This is the builder's document for the front server. The guide beside it,
[README.md](README.md), is what the owner reads and decides from. Where the two differ, the
guide is right and this file is to be corrected. Nothing of the front server is built, so
every sentence here is design: it restates each requirement of the guide in the builder's
terms, with the code-level names (routes, settings, constants, error codes, records) and
the tests each requirement needs.

Names and figures marked *proposed* are this file's suggestions; no approved source fixes
them, and the builder settles them while building. A line marked **Open** names an item
the guide leaves undecided or unmeasured; build nothing past it until the item is settled.
Each links to the item in the guide and does not repeat it.

The **front server** is everything behind the one address the internet reaches. It serves
the wizard's pages, signs users in with Onshape, passes parts and plate configurations to
the slice service, stores and serves sliced files, reads and writes each group's
configuration, gathers the log, and from phase 5 hosts the relay. It is a component of its
own, in `front/`. The **wizard** is the code that runs in the browser, in `wizard/`
([the wizard's guide](../wizard/README.md)); a **page** is the wizard as loaded in one
browser tab or in Onshape's panel. Signing in is the front server's. The **Onshape
integration**, in `onshape/`, is a separate component: the Onshape app and its panel, the
exchange with Onshape's page that tells the wizard which document and element it is in and
what is selected, and the export of the selected parts and the document's units to the
wizard as a part set. It is not part of the front server, and the front server's only
share in it, from phase 4, is the calls to Onshape it may make on its behalf
([By phase](#by-phase)).

What passes between the wizard and the front server is fixed in
[the contract between the wizard and the front server](../contracts/wizard-front-server.md),
whose routes (paths, shapes, the codes of the front server's own error reports) are written
before phase 2's building starts. This file names routes by what they do; the contract
gives their paths. The phases are those of [the plan](../docs/plans/penguin-slicer-plan.md):
phase 2, one machine; phase 3, hosted on Railway; phase 4, inside Onshape; phase 5, the real
printer.

## Contents

- [Where the front server sits](#where-the-front-server-sits)
- [Serving the wizard's pages](#serving-the-wizards-pages)
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
- [Starting, and what a restart does](#starting-and-what-a-restart-does)
- [Stopping](#stopping)
- [Threads](#threads)
- [Hosting the relay, from phase 5](#hosting-the-relay-from-phase-5)
- [Secrets](#secrets)
- [Limits](#limits)
- [Security](#security)
- [Error reports](#error-reports)
- [The fast suite](#the-fast-suite)
- [By phase](#by-phase)

## Where the front server sits

One address, `https://penguinslicer.popcornpenguins.com/`, serves the wizard's pages, the
address a daemon is given for the relay, and the redirect address of the Onshape app
([the architecture](../docs/architecture.md)). The browser and the daemons talk only to the
front server. The front server calls the slice service over Railway's private network, so
the slice service's HTTP interface is not reachable from the internet, and the browser
never makes a cross-origin request.

The slice service runs in a container of its own, the **slice container**, which holds no
secret and no credential and accepts requests only from the front server. So the front
server passes every part and plate configuration through, fetches every sliced file, and
fetches the slice service's log lines from a route of the slice service
([the slice service's details](../slice/README-details.md#to-be-built)).

The domain's name service is at Cloudflare, whose proxy sits in front of the address.
Cloudflare runs none of PenguinSlicer's logic. *Proposed* (the guide marks it proposed):
every answer except the wizard's own page files carries `Cache-Control: no-store`, so that
Cloudflare's proxy never holds one user's sliced file or configuration and hands it to
another. **Open:** [smaller points](README.md#smaller-points-this-guide-proposes-or-leaves-to-a-phases-design).

**What it holds.** The front server keeps no database, no table of sessions and no
accounts. What must last across its restart is in one of two places it does not itself
contain:

- **The browser:** who is signed in is in [the cookie](#the-cookie); the user's parts,
  layout and chosen settings are in the browser's storage, which is the wizard's business.
- **Two object stores at Cloudflare R2:** the **state bucket** (each group's
  configuration, the sliced files each with its summary, and from phase 5 the relay's
  records: each group's paired-printer record and a record of each delivery job) and the
  **log bucket** (log lines and daemon telemetry, as files). On one machine, in phase 2, a
  folder stands in for each bucket, behind [the bucket interface](#the-bucket-interface).

The front server holds the one credential that writes to the buckets; beyond it only the
owner can, through Cloudflare's own console.

**What it never holds:** a user's part (it passes through, no copy kept); a session; a
password or an account; and anything that is lost by restarting it, with three
exceptions: the log lines gathered in the last minute before a crash; from phase 5 the
printers' latest status, which each daemon sends again within seconds; and from phase 5
the pairing codes daemons are offering, which each daemon offers again within half a
minute.

**One process.** *Proposed:* the front server runs as one process (one worker with 100
threads, see [Threads](#threads)), because from phase 5 the relay's memory (the printers'
status, the pairing codes on offer, the held syncs) belongs to one process, and because
the front server follows each unfinished slice job once.

**What it exchanges.**

| With | What passes | Contract |
|---|---|---|
| The wizard | Pages; parts and plate configurations going up; progress and the sliced file coming down; the group's configuration both ways; from phase 5 sends and the printer's status | [The wizard and the front server](../contracts/wizard-front-server.md); [error reports](../contracts/error-report.md); [progress reports](../contracts/progress-report.md) |
| The slice service | Parts and [plate configurations](../contracts/plate-configuration.md) in; progress, the [sliced file](../contracts/sliced-file.md) and its summary, and log lines out | The slice service's HTTP interface ([its details](../slice/README-details.md)) |
| Onshape | Who a user is and their companies and classrooms; from phase 4, on behalf of the Onshape integration, the parts a user selected | Onshape's public interface |
| The state bucket | Configurations, sliced files and summaries, from phase 5 the relay's records | [The configuration's contract](../contracts/configuration.md) |
| The relay, from phase 5 | Who is asking; a store for its records; the sliced file | [The interface the relay offers its caller](../delivery/README-details.md#the-interface-the-relay-offers-its-caller) |

**Open:** [the cost](README.md#the-cost) of the two containers and the buckets is the
architecture's figure until the first month's bill.

### Tests

- Every answer other than a page file carries `Cache-Control: no-store` (*proposed*); the
  test enumerates the routes from the application.
- The fast suite's whole run leaves no part's bytes in the state bucket or the log bucket.

## Serving the wizard's pages

The page files are built from `wizard/` and go out with the front server, so a deploy of
one is a deploy of both. *Proposed:* the front server's build copies the wizard's built
files into its own package, and a route serves them. A request for a page with no
signed-in user starts the sign-in ([Onshape sign-in](#onshape-sign-in)) and receives none
of the wizard's code; the page files are the only answers that may be cached.

Every page's answer carries `Content-Security-Policy: frame-ancestors` naming Onshape's
address alone (*proposed* header; see
[Requests from other sites](#requests-from-other-sites)).

**Browsers.** Chrome is the supported browser (the guide marks it proposed). Safari is not
supported, in Onshape's panel or outside it. *Proposed:* a request whose browser is Safari
is answered with a plain page saying that PenguinSlicer needs Chrome. **Open:**
[browsers other than Chrome](../wizard/README.md#browsers-other-than-chrome) and
[smaller points](README.md#smaller-points-this-guide-proposes-or-leaves-to-a-phases-design).

### Tests

- A request for a page with no cookie is redirected to the sign-in, and the answer holds
  no byte of the wizard's built files.
- With a cookie, the page's files are served and carry the version
  ([The version on every answer](#the-version-on-every-answer)).

## Onshape sign-in

Every user signs in with Onshape's OAuth, the same way in Onshape's panel and outside it,
through one registered Onshape app. Onshape tells the front server who the user is and
which companies and classrooms they belong to. No other sign-in is offered, so
PenguinSlicer keeps no accounts and no passwords, has no "forgot my password", and never
has to decide whether two sign-ins are the same person. In phase 3 the app asks Onshape's
permission only for the user's identity, companies and classrooms. **Open:**
[the permissions the Onshape app asks for](README.md#the-permissions-the-onshape-app-asks-for),
which phase 4 settles before any permission to read documents is added; never ask for
permission to write.

A **group** is the users who share one configuration and one printer: one Onshape company
or classroom, named by Onshape's id for it. A user who belongs to none is a group of one,
named by the user's Onshape id ([the plan](../docs/plans/penguin-slicer-plan.md)). Every
user of a group may do everything in it; there are no roles.

The sign-in, step by step:

1. A request arrives with no cookie the front server can read. The sign-in route sends the
   browser to Onshape's authorization page with a random value of its own making
   (*proposed*: OAuth's `state`, also set in a short-lived cookie of its own for the
   callback).
2. Onshape sends the browser back to the callback route at
   `https://penguinslicer.popcornpenguins.com/`. The callback checks that the returned
   value is the one it sent out and refuses the sign-in otherwise, so nobody can be signed
   in by a link someone else prepared.
3. The front server exchanges the code for tokens and makes two calls: who the user is,
   and their companies and classrooms. These are a sign-in's only two calls to Onshape
   ([Calls to Onshape](#calls-to-onshape)).
4. It sets [the cookie](#the-cookie) and writes the sign-in's log line (the user key, the
   user's name and their groups; [The log](#the-log)). It does not read the
   configuration: the page, once it opens, asks for the configuration of the current group
   ([The configuration](#the-configuration)).

**Failures at sign-in.** A sign-in that failed (the value was not the one sent out,
Onshape refused, or Onshape did not answer) lands on a plain page carrying the front
server's sentence of what is specific and one button, Sign in with Onshape. Its screen is
the wizard's ([the wizard's guide](../wizard/README.md#signing-in)); the sentence is the
front server's error report.

**Sign in again.** The group details (the small box that opens from the current group's
name in the wizard's header) hold a "sign in again" link
([the wizard's guide](../wizard/README.md#the-current-group)). It runs the sign-in afresh,
which reads the groups again for two calls; a user added to an Onshape company after
signing in sees the new group only after it. Built in phase 3. **Open:**
[sign-ins and the allowance](README.md#sign-ins-and-the-allowance) (a limit on "sign in
again", and whether it must carry the wizard's mark) and
[who may sign in](README.md#who-may-sign-in) (a list of permitted groups, checked at the
callback).

**Signing out** is not designed. **Open:** [signing out](README.md#signing-out) (one small
route that removes the cookie).

**Inside Onshape's panel** the sign-in is the same exchange and depends on Chrome sending
the cookie to a page embedded in another site. **Open:**
[the cookie inside Onshape's panel](README.md#the-cookie-inside-onshapes-panel), including
whether Onshape's approval page can appear inside the panel; its recommended first choice
(break an endless repeat of the sign-in and say so) would be built in phase 3 with the
sign-in.

**An account with no company or classroom.** The design says such a user is a group of
one, named by the user's Onshape id; the sign-in must reach that from whatever Onshape
answers. **Open:**
[what Onshape answers for such an account](README.md#what-onshape-answers-for-an-account-with-no-company-or-classroom).

### Which routes need a signed-in user

Every route of the front server refuses a request without a signed-in user, with three
exceptions:

- the sign-in routes themselves (start, callback);
- from phase 5, the daemon's routes, which carry the token the relay issued instead;
- from phase 5, the one request by which a daemon without a token offers its pairing
  code, which carries neither. It is limited to sixty a minute for the whole relay and
  also counted for each address Cloudflare reports it came from
  ([printer delivery's details](../delivery/README-details.md#pairing)).

A request for one of the wizard's pages without a signed-in user starts the sign-in. Any
other route answers `front.not_signed_in` (*proposed*). The page does not leave for
Onshape by itself on that answer: it shows the front server's sentences (the sign-in has
ended; the user's parts, layout and settings are kept in the browser) with the button Sign
in with Onshape ([the wizard's guide](../wizard/README.md#signing-in)).

### Tests

- A request with no cookie, to every route but the three exceptions, is refused; the test
  enumerates the routes from the application itself, so a new route cannot be missed. A
  page route redirects to the sign-in; every other route answers `front.not_signed_in`.
- The callback with a `state` value other than the one sent out is refused with
  `front.sign_in_failed`, lands on the plain page, and writes a refusal line.
- The callback when the stand-in for Onshape refuses the code gives `front.sign_in_failed`;
  when the stand-in does not answer, `front.onshape_unreachable`.
- A sign-in against the stand-in makes exactly two calls, sets the cookie, writes the
  sign-in line with the user key, name and groups, and does not read the state bucket.
- A user the stand-in reports with no company or classroom becomes a group of one, named
  by the user's Onshape id.
- "Sign in again" reads the groups afresh: a group added in the stand-in appears in the
  new cookie.
- A Safari user agent receives the plain page that PenguinSlicer needs Chrome
  (*proposed*).

## The cookie

A sign-in sets one cookie in the browser, **the cookie**. It holds the user's Onshape id
and name, each of their groups by id and name, and the two tokens Onshape issued (the
access token, which authorises calls for an hour, and the refresh token, which renews it).
It is encrypted and authenticated with the **cookie key**, a secret only the front server
has, so the browser can neither read it nor change it (*proposed*: an authenticated
encryption such as Fernet or AES-GCM over the JSON of its fields, with a format number
inside).

**No session on the server.** The cookie is the whole of the sign-in. Nothing about it is
kept in the front server's memory or in a bucket, and the cookie key is a setting the
front server is given when it starts, not something it makes. So a restart or a deploy
signs nobody out, and two front servers of different versions agree at once about who a
user is. A cookie set by the old front server is read by the new one.

**Thirty days from the sign-in, never extended.** The cookie lasts thirty days
(`COOKIE_LIFETIME_S`, 2,592,000 s; *proposed* name) from the sign-in. Use does not extend
it: when the front server rewrites the cookie for any reason (renewed tokens, the previous
cookie key), the end stays where it was (*proposed*: the end is a field inside the
encrypted cookie, and the cookie's own expiry matches it). So a user signs in once in
thirty days in each browser, and the groups in a cookie are never more than thirty days
old. **Open:** [choices the owner has not yet confirmed](README.md#choices-the-owner-has-not-yet-confirmed)
(thirty days from sign-in, against thirty days from last use).

**Embedded pages.** Inside Onshape's panel the cookie must be one Chrome sends to an
embedded page: `SameSite=None; Secure` (*proposed* attributes; also `HttpOnly`). A cookie
of that kind is sent with requests other sites cause too, so the cookie alone does not
prove a request came from the wizard ([Requests from other sites](#requests-from-other-sites)).

**Onshape's tokens.** The access token is renewed with the refresh token only when a call
to Onshape needs one, and the renewed tokens are written back into the cookie. Before
phase 4 nothing needs one, unless the Onshape app is public by then, when reading the
groups again does ([Groups and the current group](#groups-and-the-current-group)).
**Open:** [two requests renewing the tokens at once](README.md#two-requests-renewing-the-tokens-at-once)
(a spent refresh token must never be left in the cookie; the means is not designed) and
[whether renewing a token counts as a call](README.md#whether-renewing-a-token-counts-as-a-call).

**Size.** A browser cookie holds about 4 KB, and a cookie that is too large is dropped by
the browser without a word, so that user could never sign in. **Open:**
[whether the cookie fits](README.md#whether-the-cookie-fits), measured first in phase 3 with
a real account; until phase 4 the tokens could be left out.

### Two cookie keys, and replacing one

The front server holds two cookie keys: the current one, and the previous one for reading
only (*proposed* settings: `PENGUIN_COOKIE_KEY`, `PENGUIN_COOKIE_KEY_PREVIOUS`). A cookie
it can read only with the previous key is rewritten with the current one, keeping its end,
and each such use writes a log line.

A planned replacement: the current key becomes the previous one and a new key becomes
current, which is a change of the front server's settings and so a restart. The previous
key is removed one week after the replacement (`PREVIOUS_COOKIE_KEY_KEPT`, 7 days;
*proposed* name, and the removal is the owner's change of settings); a user who does not
open PenguinSlicer in that week signs in again, for two calls to Onshape. In an emergency,
when a key has leaked, it is replaced and not kept as the previous key, and every user
signs in again. The steps are written in the repository as a procedure
([the architecture](../docs/architecture.md#security)). The second cookie key is built in
phase 3; phase 2 has one.

### Tests

- A cookie made with the current key is read; one changed by a single byte, or made with
  an unknown key, is treated as no cookie.
- A cookie made with the previous key is accepted, rewritten with the current key with the
  same end, and the use of the previous key is logged.
- A cookie past its thirty days is treated as no cookie (fake clock, no waiting).
- A rewrite for renewed tokens and a rewrite for the previous key each leave the end where
  it was.
- The cookie carries `SameSite=None`, `Secure` and `HttpOnly` (*proposed*).
- The cookie of a user with the largest number of groups the tests choose stays under
  4 KB, or the test reports the size it reached.
- A restart of the front server with the same keys keeps every cookie readable.

## Groups and the current group

A user who belongs to several groups works in one at a time, the **current group**: the
one group, of those a user belongs to, whose configuration and printer the user is using
now. The wizard's header names it and the user changes it there; the page keeps the choice
in the browser's storage and sends it with each request (*proposed*: a request header,
`X-PenguinSlicer-Group`, named in the contract).

**The check against the cookie.** The front server accepts a current group only if the
cookie lists that group among the user's. Every request that acts for a group carries the
current group and makes this check:

- reading and writing the configuration;
- uploading a part, submitting a plate configuration, asking about, following and
  cancelling a slice job, and fetching a sliced file or its summary;
- from phase 5, everything to do with a printer: pairing, sending, following a delivery
  job and the printer's status, stop following, cancelling a delivery job, and unpairing.

A request that needs no group carries none: the wizard's pages, the sign-in routes, and
the request for the user and their groups (below). A request that needs a group and names
none, or names one the cookie does not list, is refused with `front.group_not_allowed`
(*proposed*) and a refusal line. The page then takes the first of the user's groups by
itself and says so (the wizard's business). This one check is what keeps a user out of
another group's configuration and away from another group's printer: a print is started
only by a signed-in user whose current group has a paired-printer record naming the daemon
([the architecture](../docs/architecture.md)). It also makes the group in each log line
about a slice or a send a group the user belongs to.

**The user and their groups.** The page cannot read the cookie, so a route (*proposed*)
answers the signed-in user's name and their groups, each with its id and name, from the
cookie and with no call to Onshape. The header's list of groups is drawn from it. It needs
a signed-in user and no current group. Built in phase 2.

**Reading the groups again.** How often a signed-in user's groups are read again from
Onshape is a setting (*proposed*: `PENGUIN_GROUPS_REREAD`, `never` or a duration). Until
the Onshape app is public it is `never`: the groups in the cookie stand until the cookie
ends, so a user removed from an Onshape company keeps its configuration and printer for up
to thirty days (accepted). Once the app is public it becomes one day, so a removed user
keeps access for a day; a public app's calls do not count against the allowance. Reading
the groups again needs a fresh access token, so it renews the tokens and writes them back
to the cookie (*proposed*: the time of the last read is a field in the cookie). It is in no
phase until the app is public.

### Tests

- On every route that acts for a group, one test each, a request naming a group the
  cookie lists is accepted; one naming another group, or none, is refused with
  `front.group_not_allowed` and a refusal line. The test enumerates those routes from the
  application, so a new one cannot be missed.
- The request for the user and their groups, with no current group, answers the cookie's
  user and groups, and the stand-in for Onshape receives no call.
- With the setting `never`, no request reads the groups again, however old the cookie
  (fake clock).
- With the setting one day, the first request after a day reads the groups again from the
  stand-in, renews the tokens, and a group removed in the stand-in is gone from the
  rewritten cookie, whose end has not moved.

## Calls to Onshape

Until an Onshape app is public in Onshape's App Store, every call it makes counts against
a yearly allowance of the account that owns it: 2,500 calls a year on a free or education
account (Onshape's figure). The intention is to make the app public, which lifts the
allowance; until then, all development and testing with users must fit inside it with
room to spare. **The rule is that nothing calls Onshape that can be done without it.** The
cookie's thirty days, the absence of any periodic check, the
[development identity](#the-development-identity) and the stand-in in tests all come from
this rule.

| Use | Calls to Onshape |
|---|---|
| Work on one machine, with the development identity | None |
| The automated tests, which use a stand-in for Onshape | None |
| A sign-in to the hosted service | 2, once in thirty days for each browser |
| Reading a signed-in user's groups again | None until the app is public |
| Reading parts from Onshape, from phase 4 | Several for each part; counted in phase 4's design before anything is built |

So until phase 4, twenty people using the hosted service for two months spend about 80
calls of the 2,500. Nothing makes each person sign in only once in thirty days: 1,250
sign-ins spend the whole allowance, after which nobody can sign in until Onshape's year
turns.

**Every call is counted.** Each call the front server makes to Onshape writes one log line
naming the call (*proposed* event `onshape_call`, with the endpoint and the user key), and
the command that reads the log bucket reports the year's total.

**Open:** [sign-ins and the allowance](README.md#sign-ins-and-the-allowance) (no limit is
set; the recommendation is per-user and per-day ceilings built in phase 3, *proposed*
figures there);
[which allowance the owner's account has](README.md#which-allowance-the-owners-account-has);
[whether a second Onshape app shares the allowance](README.md#whether-a-second-onshape-app-shares-the-allowance);
[whether renewing a token counts as a call](README.md#whether-renewing-a-token-counts-as-a-call).

### Tests

- The whole fast suite runs with no route to Onshape: the client for Onshape is given the
  stand-in, and a test fails if any other client is built or any real address is called
  during the suite.
- Each call to the stand-in writes exactly one log line naming the call.
- A sign-in writes two such lines, and the stand-in counts two calls.

## Requests from other sites

A browser attaches a site's cookie to requests other sites cause, and inside Onshape's
panel the cookie is of the kind attached most freely. Four defences, built in phase 3:

- **The wizard's mark and the origin.** Every route that changes something on the
  strength of the cookie requires a request header that only the wizard's own page can
  add, **the wizard's mark** (*proposed*: `X-PenguinSlicer-Wizard: 1`, which a browser
  will not let another site's page add without a preflight that is refused), and checks
  that the request comes from the front server's own address (*proposed*: the `Origin`
  header, or `Sec-Fetch-Site: same-origin`, must be the front server's own). These routes
  are: uploading a part, submitting a plate configuration, cancelling a slice job, writing
  the configuration, and from phase 5 pairing, sending, cancelling a print, stop
  following, and unpairing. A request that fails either test is refused with
  `front.not_from_wizard` (*proposed*) and a refusal line.
- **No cross-origin reads.** The front server never sends a header that lets another
  site's page read its answers (no `Access-Control-Allow-Origin`, also on a preflight).
- **The sign-in checks the random value it sent out** ([Onshape sign-in](#onshape-sign-in)).
- **Only Onshape may embed the pages.** Every page carries `Content-Security-Policy:
  frame-ancestors` naming Onshape's address alone (*proposed* value:
  `https://cad.onshape.com`), so no other site can frame the wizard.

**Open:** [sign-ins and the allowance](README.md#sign-ins-and-the-allowance) ("sign in
again" is not in the list above; whether it must carry the wizard's mark), and the
browser-failure report and sign-out routes under
[what the wizard's guide asks of the front server](README.md#what-the-wizards-guide-asks-of-the-front-server),
each of which would join the list.

### Tests

- Each changing route refuses a request with a valid cookie but without the wizard's mark,
  and one whose origin is another site, each with `front.not_from_wizard` and a refusal
  line. The test enumerates the changing routes from the application (*proposed*: every
  route whose method is not `GET` or `HEAD`), so a new one cannot be missed.
- No answer of any route carries `Access-Control-Allow-Origin`, including the answer to a
  preflight request.
- Every page's answer names only Onshape's address in `frame-ancestors`.

## The development identity

The **development identity** is a fixed made-up user in a fixed made-up group that the
front server signs in when a setting tells it to (*proposed*: `PENGUIN_DEV_IDENTITY=1`),
for work on one machine. With the setting on, the sign-in route sets the cookie for the
development identity the moment a browser arrives, with no call to Onshape. Everything
else runs as it does hosted: the cookie, the current group's check, the user key. Its
user's id is the user key of everything done under it, and its group is the only group in
its cookie. Built in phase 2.

**It can never be on in the hosted service.** Two independent things prevent it:

- the command that starts the hosted front server never sets the setting;
- the front server refuses to start with the setting on when it finds itself on Railway
  (*proposed*: any of the environment variables Railway sets in its containers, such as
  `RAILWAY_ENVIRONMENT`) or finds an Onshape app's credentials among its settings
  (`ONSHAPE_CLIENT_ID` or `ONSHAPE_CLIENT_SECRET`, *proposed* names). It writes one log line
  saying why and ends the process with a failure status. Built in phase 3.

### Tests

- With the setting on, the sign-in route sets the development identity's cookie and the
  stand-in for Onshape receives no call.
- With the setting on and a Railway variable present, the front server does not start,
  writes the one line and exits with a failure status.
- With the setting on and an Onshape client id or secret present, it does not start.
- The hosted start command, read from the repository, does not set the setting.

## The user key

The **user key** is the signed-in user's Onshape id. With every request to the slice
service the front server says whose part or slice job it is by the user key (*proposed*
header, from the slice service's details: `X-Penguin-User-Key`). The slice service only
compares user keys and never interprets them
([the slice service's details](../slice/README-details.md#to-be-built)).

The front server sets the user key from the cookie and from nowhere else. A user key in a
request from the browser, in any field or header, is never read. So a user reaches only
their own parts, slice jobs and sliced files, even among users of the same group. A
request for a slice job or a sliced file that is someone else's is answered exactly as for
one that does not exist (the slice service answers `slice.unknown_job` for a slice job;
the front server answers `front.sliced_file_unknown` for a sliced file it holds under
another user key), so nobody learns whether another user's is there, and the attempt is
logged as a refusal.

### Tests

- A request carrying another user key in its body or headers reaches the stand-in for the
  slice service with the cookie's user key.
- A request for another user's slice job, and for another user's sliced file, is answered
  as unknown and writes a refusal line.

## Parts and slice jobs, passed to the slice service

The slice service's HTTP interface is reached only from the front server. The front server
passes each request on with the user key and passes the answer back; the slice service's
error reports (`slice.*`) go to the page unchanged. *Proposed:* the front server's client
for the slice service is given the slice service's address by a setting
(`PENGUIN_SLICE_URL`, the private-network address hosted, a local address on one machine).

**A part.** The page uploads each part by itself, at the moment the user adds it, in one
request of at most 7.5 MB (7,500,084 bytes, the plate configuration's `MAX_PART_BYTES`).
The front server passes it to the slice service's part route (`POST /parts`, *proposed*
there) with the user key and the part's units, inches or millimetres, which travel beside
the file as a label (*proposed* there: a `units` query parameter or header, `mm` or `in`).
Neither the browser nor the front server ever changes a part's bytes; only the slice
service applies the scale. The slice service checks the part on arrival and keeps one that
passes in its **part store** for two hours after its last use, under the user key, the
part's SHA-256 **hash** and its units; the same file in other units is a different part.
A part that cannot be sliced is refused there, and the refusal goes back to the page as it
came; the page shows it on the Parts step as a notification and does not add the part. The
front server keeps no copy; the browser's storage is the record of a user's parts.
*Proposed* (the guide marks it proposed): the front server streams a part through in
pieces and never holds it whole in memory, so its memory does not grow with the number of
uploads under way; a body over `MAX_PART_BYTES` is refused before it is read, with the
slice service's own report for that limit. **Open:**
[Railway's limit on one request](README.md#railways-limit-on-one-request) (no fallback is
designed) and
[smaller points](README.md#smaller-points-this-guide-proposes-or-leaves-to-a-phases-design).

**A plate configuration.** On the Preview step the page sends a **plate configuration**:
the layout, the settings and each part's hash and units, with no files. The front server
passes it to the slice service (`POST /slices`, a JSON body there) with the user key, and
the slicing of it, a **slice job**, waits its turn or runs in the slice container. The
answer gives the slice job's id, which the page keeps in the browser's storage with the
time it submitted. Because a plate configuration carries no files, slicing again uploads
almost nothing. When the plate configuration names parts no longer in the part store, the
slice service answers one error report listing every missing hash (`slice.part_missing`,
action `refresh_parts`, *proposed* there) and the front server passes it back, so the page
uploads them again and submits again.

**One unfinished slice job.** A user has one unfinished slice job at a time: a submission
cancels the same user's earlier unfinished slice job (the slice service does it; its final
progress report says it was cancelled by a later slice of the same user). With the wizard
open in two tabs, the later slice job wins. The front server also passes on a user's own
cancel (`DELETE /slices/<job>` there).

**Busy, and stopping.** When no more slice jobs may wait, the slice service answers
`slice.busy` (retryable) and the front server passes it on; the user is told the slicer is
busy and to try again in a minute, and the page does not try again by itself. A slice
service that is stopping for a deploy refuses a new slice job with an answer of its own,
never `slice.busy` (its name is the slice service's to settle). The front server passes
that answer to the page as one the page retries quietly, exactly like
`front.slice_unreachable` (*proposed*: the front server answers `front.slice_unreachable`
for it). **Open:**
[a plate configuration submitted while the slice service stops](README.md#a-plate-configuration-submitted-while-the-slice-service-stops)
(recommended: the front server keeps the submission in memory and hands it to the new
slice service; phase 2 gives only the retry) and
[a plate configuration submitted twice](README.md#a-plate-configuration-submitted-twice)
(recommended: a value of the page's own making, designed with the contract's requests
before phase 2 is built).

**Rate limits.** Phase 2 builds limits on how fast one user may upload parts and submit
plate configurations, counted for the signed-in user; their figures are proposed nowhere.
**Open:** [rate limits and the sweep's interval](README.md#rate-limits-and-the-sweeps-interval).

**The list of settings and the profile catalog's names.** Advanced mode, built in
phase 2, needs every setting the slice service accepts. **Open:**
[the list of settings and the profile catalog's names](README.md#the-list-of-settings-and-the-profile-catalogs-names)
(recommended: the front server asks the slice service for both, passes the list to the
page, and checks each configuration against the catalog at start and on edit; to be
answered before phase 2 is built).

### Asking about a slice job

A page that has lost its state (a refresh, a reopened panel) still has, in the browser's
storage, the id of its plate's slice job and the time it submitted it. It asks the front
server about that slice job. The front server asks the slice service
(`GET /slices/<job>`), which remembers a slice job for two hours after it ends, and looks
in the state bucket for its sliced file. It answers one of five:

| Answer | When |
|---|---|
| Still waiting or running, with the latest progress report | The slice service says so; also when the slice has ended but its sliced file is not yet stored |
| Finished | The sliced file is in the state bucket |
| Ended in an error, with the error report | The slice service says so; also when the sliced file was stored and has since expired, in which case the report is `front.sliced_file_expired` |
| Cancelled by a later slice of the same user | The slice service says so |
| Unknown | Neither the slice service nor the state bucket knows it, or it is another user's |

What the page does with each answer is the wizard's
([the wizard's guide](../wizard/README.md#coming-back-to-running-work)). To answer
"expired" for a file already deleted, the front server keeps a small tombstone
(*proposed*: the sliced file's metadata record is kept, marked expired, until two hours
after it expired, or the sweep's index keeps the entry; either way within
[the bucket interface](#the-bucket-interface)).

A slice job the slice service cancelled while it waited, because the slice service was
asked to stop for a deploy (`"cancel_reason": "shutdown"` there), is reported to the page
as cancelled for that reason, and the page submits it again by itself. How the report
tells that cancel from the user's own and from a later slice job's is written with the
contract's requests, before phase 2 is built.

### Progress streams

A **progress stream** is the connection, of server-sent events, on which a page follows a
slice job or, from phase 5, a delivery job, through the front server. It carries
[progress reports](../contracts/progress-report.md); for a waiting slice job the report
says how many are ahead of it. Railway closes any request after fifteen minutes, and after
five minutes with no data; Cloudflare closes one after 125 seconds with no data
([the architecture](../docs/architecture.md#progress-streams)). So:

- a stream with nothing to report sends a comment line at least every fifteen seconds
  (`PROGRESS_KEEPALIVE_S`, 15; *proposed* name);
- the page reconnects whenever a stream closes, which is how it survives the
  fifteen-minute cut and every restart;
- a stream that connects late gets the latest progress report at once, so a reconnecting
  page catches up in one message;
- a slice job is reported finished on the stream only once its sliced file is in the state
  bucket, because that is where the page fetches it from.

The pages' streams are fed from the one stream the front server holds for each unfinished
slice job ([Following slice jobs](#following-slice-jobs-and-storing-sliced-files)), so
three tabs watching one slice job cost the slice service one connection.

**Open:** [whether progress arrives as it is sent](README.md#whether-progress-arrives-as-it-is-sent)
(the fallback is designed: the page asks for the latest progress report every second or
two, by the route for asking about a slice job) and
[how many users at once](README.md#how-many-users-at-once-and-what-happens-when-the-threads-run-out)
(a limit on streams for each user, *proposed* four there).

### Tests

- An uploaded part reaches the stand-in for the slice service with the cookie's user key
  and its units, byte for byte; the stand-in's refusal reaches the page unchanged.
- A part over 7.5 MB is refused before its body is read (*proposed*).
- A plate configuration reaches the stand-in with the user key; its report listing
  missing hashes, and `slice.busy`, reach the page unchanged.
- The stand-in's stopping answer reaches the page as `front.slice_unreachable`, never as
  `slice.busy`.
- Asking about a slice job gives each of the five answers, one test each, including
  "still running" for an ended slice whose sliced file is not yet stored and "ended in an
  error" with `front.sliced_file_expired` for an expired one.
- A slice job cancelled for a stop is reported with that reason.
- A progress stream with nothing to report sends a comment line within fifteen seconds of
  fake time.
- A progress stream opened after the slice job started gets the latest progress report as
  its first event.
- Three streams on one slice job make one connection to the stand-in.
- A finished slice job is reported finished on the stream only after its sliced file is in
  the state bucket.
- The slice service not answering gives the page `front.slice_unreachable`, retryable.

## Following slice jobs and storing sliced files

**The front server follows every unfinished slice job itself**, page or no page: for each
one it holds the slice service's own progress stream (`GET /slices/<job>/events`). A slice
job runs to its end through a refresh, a lost network or a closed laptop lid, and the front
server is what notices that it has ended and collects the result when no page is open.

**When a slice ends**, the front server:

1. fetches the sliced file (`GET /slices/<job>/file`) and its **summary**
   (`GET /slices/<job>/summary`: the predicted print time, the filament used, the layer
   count and the warnings; [the sliced file](../contracts/sliced-file.md#summary));
2. stores both in the state bucket under the user key and the slice job's id, with the
   time the slice ended and the group the slice job was submitted for (*proposed* names:
   `sliced/<user_key>/<job>.gcode.3mf`, and `sliced/<user_key>/<job>.json` holding the
   summary, `slice_ended_at`, the group and the record's format number);
3. tells the slice service they are stored (`DELETE /slices/<job>/file`, *proposed*
   there), and the slice container deletes its copy;
4. only then reports the slice job finished to any page that is following.

A fetch that fails partway leaves nothing half-written in the state bucket (*proposed*:
the file is written under its final name only when complete, or R2's single put of the
whole stream, and the metadata record is written last) and is tried again. If the state
bucket does not answer, the front server keeps trying; the slice container keeps its copy
until told the file is stored, and the page goes on seeing the slice job as running. If the
slice container restarts before the file is stored, that slice runs again (the page
submits again).

**Size.** A sliced file is 8.8 to 14.1 MB on the plates sliced so far, well inside the
100 MB Cloudflare allows one request. Nothing bounds its size; the log line that ends each
slice records it. *Proposed* (the guide marks it proposed): the sliced file passes through
the front server in pieces, into the state bucket and out to a browser or a daemon, and is
never held whole in memory. **Open:**
[no ceiling on a sliced file](README.md#no-ceiling-on-a-sliced-file) (recommended: measure
first in phase 3).

**The state bucket's copy is the one everything uses.** The page fetches it, and its
summary, through the front server to draw the Preview step and to offer the download; from
phase 5 the relay hands it to the daemon. The browser never stores a sliced file and the
front server has no route that takes one from a browser, so a printer only ever runs a
file the slice service made. **Open:**
[telling the page when a sliced file expires](README.md#telling-the-page-when-a-sliced-file-expires)
(recommended: the moment of expiry as a field of the summary's answer, and again when a
print of the plate ends; written into the contract before phase 2 is built) and
[the one-line description of a plate](README.md#what-the-wizards-guide-asks-of-the-front-server)
(if the front server writes it, it keeps it, or what it is made from, beside the sliced
file until the send).

**When the front server starts**, see
[Starting, and what a restart does](#starting-and-what-a-restart-does).

### Tests

- A slice job that ends with no page following it has its sliced file and summary in the
  state bucket under the user key and the slice job's id, with the time the slice ended,
  and the stand-in for the slice service was told it was stored, after both were written.
- A page following a slice job is told it is finished only after the stand-in's delete was
  sent (the stand-in orders the events).
- The stand-in failing mid-fetch leaves nothing in the state bucket, and the fetch is
  tried again until it succeeds.
- The state bucket refusing writes: the front server keeps trying (fake clock), never
  sends the delete, and the page sees the slice job as running.
- The page's fetch of a sliced file and of its summary serves the state bucket's copy,
  after the stand-in has deleted its own.
- No route accepts a sliced file from a browser (the route enumeration finds none that
  writes to `sliced/`).

## Two hours, deleting, and the backstop

**The rule.** A sliced file can be previewed, downloaded, sent to the printer, and sent
again after a print, until two hours after its slice ended or two hours after its last
print ended, whichever is later (`SLICED_FILE_KEPT_S`, 7,200 s; *proposed* name). So the
same plate can be sent again after a print of any length without slicing again. Its last
print ended when the latest delivery job that used it ended. Before phase 5 nothing is
printed, so two hours after the slice ended is the whole rule. A sliced file is **due**
once both limits have passed; a sliced file that a delivery job not yet ended uses is
never due.

The front server enforces the rule itself, in three ways:

- **It refuses a sliced file that is due** with `front.sliced_file_expired` (*proposed*)
  and deletes it. A page coming back to an expired plate is told that the earlier plate's
  sliced file has expired (the "ended in an error" answer of
  [Asking about a slice job](#asking-about-a-slice-job)); a send of one is told that it
  has expired and that the plate must be sliced again.
- **It sweeps.** At a regular interval it deletes every sliced file that is due, so that a
  file nobody asks for again is gone on time. The interval has no figure (*proposed*: ten
  minutes, `SWEEP_INTERVAL_S`); it bounds only how long past its due time an unasked-for
  file can exist, since a file somebody asks for is refused exactly on time. **Open:**
  [rate limits and the sweep's interval](README.md#rate-limits-and-the-sweeps-interval).
  The guide's four bucket operations offer no listing, so the sweep needs its own record
  of what is stored: *proposed*, an index document in the state bucket
  (`sliced/index.json`: for each stored sliced file, its name and the time it falls due if
  no print follows), updated by conditional write when a file is stored, sent or deleted,
  and read at start.
- **From phase 5, a sliced file whose print is under way is kept;** its two hours count
  from the moment that print ends.

**How the front server knows when the last print ended.** A delivery job's record names
the sliced file it used (by the user key and slice job id under which it is stored;
*proposed* form), and records when the delivery job ended. The front server finds a
sliced file's delivery jobs through those records: a file is due only when no delivery job
naming it is unended and two hours have passed since the latest one ended
([printer delivery's details](../delivery/README-details.md#the-records-of-delivery-jobs)).
A delivery job's record is kept a day after it ends, longer than the two hours the rule
needs. *Proposed:* at each delivery job's end the front server updates the sliced file's
due time in the index, so the sweep does not read every delivery job's record.

**The backstop at R2.** R2's own rule for deleting old files cannot do this alone: it
counts in whole days, not hours; Cloudflare says a file is typically removed within 24
hours after it falls due; and it counts from when a file was stored, knowing nothing of
prints. So it is used only as a backstop for a file the front server failed to delete (a
crash at the wrong moment, a fault in the sweep), set at **three days** on the sliced
files' prefix (*proposed*: an R2 lifecycle rule on `sliced/`, set by the owner at R2 in
phase 3 and written in the repository's procedure). Three, because R2 counts from when
the file was stored and the file must still be there two hours after the longest print
ends.

**A send stores the sliced file afresh.** So that a file sent late in its life is not
caught by the backstop, each send stores the sliced file again (*proposed*: a copy of the
object onto itself, which R2 counts as a new store), which restarts R2's count; the three
days therefore run from the last send. From phase 5. Consequences: a print that runs
longer than about three days from its send loses its sliced file to the backstop (the
print is not affected, since the printer has the file; sending the plate again then means
slicing it again); and a sliced file the front server failed to delete can rest at R2 for
up to about four days after it was last stored (three days, and up to a day more for
Cloudflare to remove it), in a private bucket.

**A send whose file has gone.** A send whose sliced file is no longer in the state bucket,
deleted by the rule, by the backstop or otherwise, is answered that the sliced file has
expired and that the plate must be sliced again. The relay's answer for it is
`delivery.sliced_file_too_old` with its rule changed (*proposed* in
[printer delivery's details](../delivery/README-details.md#the-sliced-file)); its sentence
is the same as `front.sliced_file_expired`'s. A preview or download of a file that has
gone answers `front.sliced_file_expired` the same way.

### Tests

All on a fake clock; none waits.

- A sliced file one second under two hours after its slice ended is served; one at two
  hours, never printed, is refused with `front.sliced_file_expired` and deleted.
- The sweep deletes a file that fell due and leaves one that has not; a restarted front
  server's sweep finds a file stored before the restart.
- Asking about a slice job whose sliced file has expired answers "ended in an error" with
  `front.sliced_file_expired`.
- A sliced file whose delivery job ended five hours after the slice is served one hour
  after that delivery job ended, and refused and deleted at two hours after it (phase 5).
- A sliced file used by a delivery job not yet ended is kept, and served to the daemon,
  past two hours after its slice (phase 5).
- A send stores the sliced file afresh: the folder form records a new store time, and the
  R2 form's suite checks the object's new upload time (phase 5).
- A send whose sliced file the state bucket no longer holds is answered as expired, with
  the plate to be sliced again (phase 5).

## The configuration

A group's **configuration** is the settings everyone in the group shares: one JSON
document for each group, in the state bucket (*proposed* name: `config/<group>.json`),
read whole and written whole. It holds:

- **The group's filaments.** Each has a **colour**, shown where the user chooses a
  filament so that two filaments of one material can be told apart. That colour is never
  used in the layer preview, which draws every plate in four fixed colours, one for each
  group of line types.
- **The profiles the wizard offers for each filament,** a list of its own for each
  filament. Each profile is one of Orca's, named by Orca's own name, with any settings that
  replace that profile's own, and beside it the group's own name and purpose for it. The
  Settings step offers profiles by the group's names and shows the purpose as a tooltip.
- **The printer's Orca profile,** from which the plate's size and height come
  (`printable_area`, `printable_height`), for the Layout step and the plate configuration's
  `printer`. Which physical printer is the group's is recorded by pairing, in the
  paired-printer record, not here; nothing checks that the two agree.
- **The units of uploaded files:** whether a part uploaded as a file, which carries no
  units, is read in inches or millimetres.
- **A format number,** like every record in the state bucket.
- **No secret:** no token, key or pairing code.

Its exact fields, with an example explaining every field, are written with phase 2's
design in [the configuration's contract](../contracts/configuration.md).

**A default.** A group with no document gets a default built into the front server, which
names the profile of the Bambu Lab H2S, the Popcorn Penguins' printer, so a new group can
slice without setting anything up.

**Reading.** The front server reads the current group's document whenever the wizard
asks: when a page opens (and so after every sign-in) and when the user presses the reload
glyph in the wizard's header. The sign-in itself does not read it.

**Writing.** An edit writes the whole document on the condition that it has not changed
since the edit started: the answer to a read carries the document's version marker
(*proposed*: the bucket's ETag, or the folder form's equivalent), a write names the marker
it was based on, and the state bucket accepts the write only if its marker still matches.
The first of two simultaneous edits is saved; the second is refused with
`front.configuration_changed` (*proposed*), telling the user it was changed by someone
else and to reload, and nothing is merged. Every edit writes a log line with the user's
name and what changed (*proposed*: the paths of the fields that changed, with old and new
values). An edit replaces the document; nothing else ever deletes it.

**A document that cannot be understood** (*proposed*: not JSON, not of a format number the
front server knows, or failing the contract's schema) is answered with
`front.configuration_unreadable` (*proposed*), and is never replaced by the default and
never written over, so a hand-written document is not lost to a typing mistake. The error
report names what is wrong, for whoever wrote it. **Open:**
[choices the owner has not yet confirmed](README.md#choices-the-owner-has-not-yet-confirmed)
(reporting a damaged document rather than falling back to the default) and the wizard's
[a configuration that cannot be read](../wizard/README.md#a-configuration-that-cannot-be-read).

**The fixed set, until the edit screens exist.** The configuration's edit screens are a
feature of their own, in no phase yet
([the plan, Known future work](../docs/plans/penguin-slicer-plan.md#known-future-work)).
Until they exist a group uses the built-in default or a document the owner writes by hand
and places in the state bucket through Cloudflare's console, following the contract's
example. No user can change one, so the front server must expect hand-written documents
and report their faults clearly. The conditional write is built in phase 2 all the same,
with nothing in the wizard using it yet: it proves the bucket's conditional write early,
on a folder and then on R2, and lets the edit screens be added without changing the front
server. **Open:** [choices the owner has not yet confirmed](README.md#choices-the-owner-has-not-yet-confirmed)
(the fixed set as default-or-hand-placed document, against a few named configurations
shipped with the front server).

### Tests

- A group with no document gets the default, which names the H2S profile.
- A read for the current group answers that group's document; a read for a group the
  cookie does not list is refused ([Groups and the current group](#groups-and-the-current-group)).
- Two edits read from the same version: the first is written, the second is refused with
  `front.configuration_changed` and the document holds the first.
- An edit writes a log line with the user's name and the change.
- A document that is not JSON, one with an unknown format number, and one that fails the
  schema each produce `front.configuration_unreadable` and are left byte for byte as they
  were.
- A hand-written document following the contract's example is read.

## The bucket interface

The front server reaches each bucket through one interface with two implementations: R2,
hosted, and a folder, on one machine. Both give the same four operations: read a file
(with its version marker), write a file, write a file only if it has not changed since it
was read, and delete a file. *Proposed:* reads and writes take and give streams, so a
sliced file is never held whole in memory, and the R2 form uses R2's S3-compatible
interface with conditional writes (`If-Match`, `If-None-Match`). Every record the front
server writes to the state bucket carries the number of its format
([the contracts](../contracts/README.md)), so a record written by the old front server is
read by the new one.

The same interface, given the state bucket, is the store the front server supplies the
relay from phase 5 ([Hosting the relay](#hosting-the-relay-from-phase-5)).

The fast suite runs against the folder form, in a fresh temporary folder for each test.
The R2 form passes the same set of tests in a suite of its own outside the fast suite,
because it needs R2.

The configurations and the paired-printer records have no second copy; if the bucket is
damaged, nothing restores them (accepted; a second copy is not designed).

### Tests

- The same set of tests runs against the folder form in the fast suite and the R2 form
  outside it: read, write, a conditional write that succeeds, one that fails because the
  file changed, a conditional create that fails because the file exists, delete, and a
  stream larger than the tests' memory chunk.
- Every record the front server writes carries a format number; a record of the previous
  format is read.

## The log

The owner runs the service alone and cannot look at a user's screen; the log must answer
what went wrong, whether the service is the right size, and who is using it
([the architecture](../docs/architecture.md#reading-what-happened)). Each log line is one
JSON object carrying the time, the component, and whichever of the group, user key, slice
job, delivery job and daemon it concerns.

**The front server's own lines:**

- each sign-in: the user key, the user's name and their groups;
- each call to Onshape;
- each edit of a configuration: the user's name and what changed;
- every error a user is shown, with its code, the user key and name, the group, and the
  slice job or delivery job it belongs to;
- every unexpected failure inside the front server, with its stack trace, including one
  no user saw because the request was retried;
- every refusal: a failed sign-in; a request for something that belongs to another user;
  a current group the cookie does not list; a changing request without the wizard's mark
  or from another address;
- what happened to each sliced file: stored (with its bytes), served, expired, deleted;
- once a minute, one line: the memory it holds, the slice jobs running and waiting, the
  connections it holds open and the threads in use;
- each start, with the version that started, and each use of the previous cookie key.

Every line about a slice or a send carries the user key and the current group. No line
holds a secret, a token, a pairing code, the cookie or a part's shape. Lines do hold
users' names and parts' names, which is why the log bucket is private.

**Gathering.** The front server is the only thing that can write to the log bucket, so it
gathers for the others. It fetches the slice service's lines from its route on the private
network (`GET /log`, *proposed* there) and adds to each the group, which it knows from the
request that submitted the slice job (*proposed*: from an in-memory map of slice job to
group, rebuilt at start from the sliced files' records and the slice service's list; a
line whose slice job it cannot place keeps no group). From phase 5 it gathers the relay's
lines and the daemons' telemetry. About once a minute (`LOG_FLUSH_S`, 60; *proposed*
name) it writes what it has gathered to the log bucket as a new file, newline-separated
JSON, named by date and component (*proposed*: `<YYYY-MM-DD>/<component>/<time>-<random>.jsonl`).
Every line also goes to standard output at once, which Railway's log view shows and keeps
seven days; the log bucket keeps them ninety days (an R2 lifecycle rule on the log bucket,
set in phase 3). A crash loses up to the last minute of lines from the log bucket; they
remain in Railway's log view. A deploy loses none, since a stopping front server writes
what it has gathered ([Stopping](#stopping)).

**Reading.** The owner and the owner's coding agents read the log bucket with a credential
that can read it and nothing else, through one command kept in the repository, built in
phase 3 (*proposed*: `make -C front log ...`). What it reports, including the year's calls
to Onshape, is in [the architecture](../docs/architecture.md#reading-it).

Accepted: users' names and parts' names stay in the log bucket ninety days, and removing
one user's lines on request is not designed. **Open:**
[failures in the browser that reach no log](README.md#what-the-wizards-guide-asks-of-the-front-server)
(recommended: one route, carrying the wizard's mark and limited, that writes one log line
for a failure that happened only in the browser, never holding a part's shape).

### Tests

- Each kind of line above is written by a test that causes it, and holds the fields
  listed.
- With a fake clock, a minute's gathered lines are written to the log bucket as one new
  file named by date and component.
- Lines fetched from the stand-in for the slice service gain the group of their slice job.
- A stop writes the gathered lines before the process ends.
- No line written during the whole fast suite contains the cookie, an Onshape token, a
  cookie key, the relay's secret key, a daemon's token or a pairing code; the test searches
  every line for the values the suite used.

## The version on every answer

Every answer of the front server, error reports and progress streams included, carries the
front server's version (*proposed*: a header, `X-PenguinSlicer-Version`, and a field on
the first event of a stream). A page that sees a newer version than its own reloads at the
next moment when nothing is in flight, which loses nothing because its state is in the
browser's storage ([the wizard's guide](../wizard/README.md#the-page-reloading-itself-for-a-new-version)).
Built in phase 2, since the wizard's reloading is built then.

**Old and new versions together.** A deploy replaces the front server and nothing else, so
for a while the new front server meets things made for the old one:

- **a page loaded before the deploy keeps working against the new front server,** at
  least until it reloads; of all the rules here this is the one most easily broken by
  accident;
- every record in the state bucket carries the number of its format, and the new front
  server reads the old formats;
- a cookie set by the old front server is read by the new one;
- from phase 5 an installed daemon keeps working
  ([the architecture](../docs/architecture.md#old-and-new-versions-together)).

*Proposed* (the guide marks it proposed, in the same words as the slice service's guide):
a change to the plate configuration's contract or to the slice service's HTTP interface is
made so that the previous front server still works against the new slice service, and the
previous slice service against the new front server. **Open:**
[smaller points](README.md#smaller-points-this-guide-proposes-or-leaves-to-a-phases-design).

### Tests

- Every route's answer carries the version, including an error report and the first event
  of a progress stream.
- The previous version's page (its built files, from the previous release) is run against
  the new front server.
- The new front server reads a record of each kind written by the previous one, and a
  cookie the previous one set.
- *Proposed:* the front server is run against the previous slice service's stand-in, and
  the new one.

## Starting, and what a restart does

PenguinSlicer is deployed continuously, so a restart of the front server is routine: it
interrupts no user and loses nothing a user did. One thing is outside the rule: from
phase 5, a pairing code typed just after a restart must be typed again.

**When it starts,** the front server asks the slice service for all its slice jobs
(`GET /slices`, *proposed* there), and asks again until the slice service answers
(*proposed*: with growing waits, on the fake clock in tests). It follows the unfinished
ones again and collects every finished one whose sliced file it has not yet stored. So a
slice that ended while the front server was down is stored a moment after it comes back.
It also reads the sweep's index ([Two hours](#two-hours-deleting-and-the-backstop)) and
writes the start line with its version.

| What the user did | Where it is | After a restart of the front server |
|---|---|---|
| Signed in | The cookie | Still signed in; the cookie key is a setting |
| Added parts, laid out a plate, chose settings | The browser's storage | Untouched |
| Submitted a slice job that is still running | The slice container | It keeps running; the front server finds it again when it starts |
| Finished a slice | The state bucket | Untouched |
| Edited the configuration | The state bucket | Untouched |
| Paired a printer; sent a print (phase 5) | The state bucket | Untouched; the print goes on, and the printer's status is not known until the daemon's next sync, within about ten seconds; the wizard shows a grey dot and "…" on the printer-status icon meanwhile |
| A daemon had gone silent just before the restart (phase 5) | Its offline time was never noted | Two minutes after the restart its printer shows Offline, silent "for at least" the time since the front server started |
| Typed a pairing code in the half minute after a restart (phase 5) | The relay's memory, which the restart emptied | Told that no daemon is showing that code; typing it again a moment later works |

The whole table, for both containers, is in
[the architecture](../docs/architecture.md#what-a-restart-does).

**Every request is safe to repeat.** The page retries every request it makes, for up to
300 seconds, so a request may arrive several times. A request sent twice because its first
answer was lost leaves the same result as one sent once: uploading the same part again
gives the same answer; a repeated send is answered with the same delivery job
([Hosting the relay](#hosting-the-relay-from-phase-5)). A repeated submission must not
leave the page following a slice job the repeat itself cancelled. **Open:**
[a plate configuration submitted twice](README.md#a-plate-configuration-submitted-twice).

What the user sees during a gap is the wizard's: nothing under 20 seconds; then a message
that the server is being slow, with a countdown to the next attempt; then, only after 300
seconds, that the server could not be reached, with an offer to try again
([the wizard's guide](../wizard/README.md#when-the-server-is-slow-or-cannot-be-reached)).

### Tests

- Each row of the table above is a test: the front server is stopped at that moment and
  started again on the same folders and the same stand-ins, and the result checked.
- A front server started while the stand-in for the slice service holds one unfinished and
  one finished, unstored slice job follows the first and stores the second.
- A finished slice job whose sliced file is already in the state bucket is not fetched
  again at start.
- A front server started while the stand-in does not answer keeps asking (fake clock) and
  follows the slice jobs once it answers.
- A plate configuration repeated with its first answer lost leaves the page following a
  live slice job (the means to be settled; see the open item).

## Stopping

Asked to stop (`SIGTERM`, as at every deploy), the front server takes no new requests,
lets uploads and downloads in progress finish, closes its progress streams, from phase 5
answers its held syncs, and writes the log lines it has gathered to the log bucket, so that
pages and daemons reconnect to its replacement and a deploy loses no log line. It has
whatever time Railway allows a stopping container (*proposed*: the front server's own
bound on its stop is a setting, defaulting below Railway's, once Railway's is known). A
stopping front server does not cancel any slice job; the slice container is not touched.
Built in phase 3.

**Open:** [what Railway does at a deploy](README.md#what-railway-does-at-a-deploy) (tried
first in phase 3: whether it deploys the front server alone, whether it overlaps old and
new, how long a stopping container gets; the design assumes a plain stop and start) and
[a deploy that fails](README.md#a-deploy-that-fails-and-learning-that-the-service-is-down)
(recommended: the check after each deploy tells the owner when it fails).

### Tests

- A stop during an upload lets the upload finish; a stop during a download lets it finish;
  a stop with a progress stream open closes it; a stop writes the gathered lines; a stop
  with a held sync open answers it (phase 5).
- A request arriving after the stop began is not accepted.

## Threads

The front server serves requests with 100 threads (*proposed*: a WSGI server in one process
with a fixed pool, such as waitress with `threads=100`, or gunicorn with one `gthread`
worker and 100 threads; `PENGUIN_FRONT_THREADS`, default 100). Threads are its scarce
resource. Each of these holds one thread for as long as it lasts:

- a page's open progress stream;
- from phase 5, an idle daemon's **held sync**: the relay holds its answer to the daemon's
  sync for up to 55 seconds (the **held wait**), so that a send reaches the daemon at once;
- the front server's own following of an unfinished slice job (*proposed*: a thread for
  each, counted among the 100); the slice service starts with one slice running and two
  allowed to wait, so following takes at most three;
- an upload or a download in progress.

So there is room for about fifty idle daemons beside the users' requests and streams, a
figure that assumes the other threads are enough for the users. When the number of daemons
calls for it, the held syncs can move to a small server of a different kind that holds
thousands of idle connections cheaply: known future work, in no phase. A request that
finds no free thread waits for one (*proposed*, as the guide recommends); the page's
retrying covers it.

**Open:**
[how many users at once, and what happens when the threads run out](README.md#how-many-users-at-once-and-what-happens-when-the-threads-run-out)
(recommended: a print and the printer's status followed by short requests every ten
seconds rather than on a progress stream, streams limited to four for each user, and a
target of fifty idle daemons and fifty open pages; until settled, build no print-following
stream), [the front server's memory](README.md#the-front-servers-memory) (never measured),
and [choices the owner has not yet confirmed](README.md#choices-the-owner-has-not-yet-confirmed)
(following counted among the 100).

### Tests

- The once-a-minute line reports the threads in use and the connections held open,
  checked with a known number of open progress streams.
- With every thread held by the tests' streams, a further request waits and is served when
  one closes (event-ordered, no sleep).

## Hosting the relay, from phase 5

The **relay** is the half of printer delivery that runs on a server; the **daemon** is the
half on the computer beside the printer, which opens no port and only calls out. From
phase 5 the relay runs inside the front server's process, and the front server is its
**caller**. The daemon reaches it at the same public address as everything else. The
relay stays a separate component with its own tests; how pairing, sending and the daemon's
requests work is printer delivery's
([its details](../delivery/README-details.md#phase-5-the-relay-inside-the-front-server)).
The relay's interface to its caller as built (`create_app(secret_key, identify,
find_sliced_file)`, with an identity keyed on a pairing code) is changed in phase 5 by
printer delivery's work to the user and current group below; the front server is built
against the changed interface
([the interface the relay offers its caller](../delivery/README-details.md#the-interface-the-relay-offers-its-caller)).

The front server:

- **Tells the relay who is asking.** The relay never looks at a cookie. For each request
  from a page, the front server gives it the signed-in user and the current group, already
  checked against the cookie. When a user types the code a daemon is showing, the relay
  links that daemon to the user's current group by writing the group's
  **paired-printer record**. A send is accepted when the current group has such a record,
  and goes to the daemon it names. The chain that protects a printer runs through the
  front server: Onshape says who the user is, the cookie carries their groups, the current
  group must be one of them, and only that group's record names the daemon.
- **Gives the relay a store for its records,** through
  [the bucket interface](#the-bucket-interface) on the state bucket (a folder on one
  machine): each group's paired-printer record, and one record for each **delivery job**
  (one sliced file on its way to one printer, from the send until the print ends), kept
  until a day after the delivery job ends. They are in the state bucket and not in memory
  because a daemon told the relay no longer knows its delivery job treats it as finished
  and drops it. A delivery job's record holds whether the daemon has been allowed to start
  the print, which keeps a print from starting twice across a restart, and names the
  sliced file it used, which is how the front server knows when that sliced file's last
  print ended ([Two hours](#two-hours-deleting-and-the-backstop)).
- **Supplies the sliced file.** The relay keeps no copy. When the daemon fetches it, the
  front server streams it from the state bucket, where it is kept under the rule above.
  Each send stores the sliced file afresh, restarting R2's three-day count; a send whose
  sliced file has gone is answered that it has expired and the plate must be sliced again.
  **Open** (printer delivery's):
  [how the daemon's fetch of the sliced file is authorised in phase 5](../delivery/README.md#how-the-daemons-fetch-of-the-sliced-file-is-authorised-in-phase-5).
- **Makes a repeated send harmless.** A send repeated by the same user with the same
  sliced file, while its delivery job is live, is answered with that same delivery job: no
  second print, and no refusal on the grounds that the printer is now busy. Printer
  delivery as built refuses the repeat with `delivery.job_in_flight`; changing that is part
  of phase 5 ([printer delivery's item](../delivery/README.md#a-send-repeated-while-its-delivery-job-is-live)).
- **Notes when a daemon goes offline.** When a daemon goes offline (no sync from it for two
  minutes), the relay writes the time of that daemon's last sync to the group's
  paired-printer record: one write at that moment, not one a minute while the daemon is
  healthy, and no further write however long it stays off. A recorded time survives a
  restart of the front server and is used as it is, so the printer details can say how long
  the printer has been silent ("Not heard from for 7 minutes"). After a restart of the
  front server, a paired daemon not heard from within two minutes, whose record holds no
  time, is shown as silent "for at least" the time since the front server started
  (*proposed*: the front server gives the relay its start time). **Open** (printer
  delivery's): [clearing the recorded time of silence](../delivery/README.md#clearing-the-recorded-time-of-silence)
  when the daemon syncs again.
- **Lets the daemon's requests in without a sign-in.** A daemon has no cookie; its requests
  carry a token the relay issued and checks, and a daemon not yet paired offers its pairing
  code with neither. These routes are excepted from the signed-in check and from the
  wizard's mark ([Which routes need a signed-in user](#which-routes-need-a-signed-in-user)).
- **Holds the relay's secret key,** which signs the daemons' tokens, as a setting
  (*proposed*: `PENGUIN_RELAY_SECRET_KEY`, with the relay's previous key beside it as the
  relay's procedure requires; [printer delivery's details](../delivery/README-details.md#replacing-the-relays-secret-key)).
- **Answers the held syncs when stopping** ([Stopping](#stopping)), and **gathers the
  relay's log lines and what the daemons report about themselves** ([The log](#the-log)).
- **Applies the limits on how fast one user or one daemon may send the relay requests,**
  counted for the signed-in user or the daemon. Printer delivery proposes carrying over
  the figures built today: 120 status requests and 10 sends a minute for each user, 120
  syncs and 60 other requests a minute for each daemon, and ten wrong pairing codes a minute
  for each user; offers of a pairing code are limited to sixty a minute for the whole relay.
  **Open:** [rate limits and the sweep's interval](README.md#rate-limits-and-the-sweeps-interval)
  and [the rate limits of phase 5](../delivery/README.md#the-rate-limits-of-phase-5).

A cancel of a print is passed to the relay. **Open:**
[the one-line description of a plate](README.md#what-the-wizards-guide-asks-of-the-front-server)
(whether the front server writes it from the plate configuration and hands it to the relay
with the send), [how many users at once](README.md#how-many-users-at-once-and-what-happens-when-the-threads-run-out)
(a page following a print by short requests rather than a progress stream), and
[a daemon through Cloudflare](README.md#a-daemon-through-cloudflare).

### Tests

- The front server's store passes the relay's own tests of a store.
- The relay is given the cookie's user and the checked current group, and never the
  cookie; a request naming a group the cookie does not list never reaches the relay.
- A send from a current group with no paired-printer record is refused; one with a record
  reaches that record's daemon.
- A send repeated by the same user with the same sliced file while its delivery job is
  live answers the same delivery job and starts no second print; a repeat after the
  delivery job ended is a new send.
- A sliced file a delivery job needs is served to the daemon after two hours after its
  slice; the daemon's fetch streams from the state bucket.
- A send stores the sliced file afresh; a send whose sliced file has gone is answered as
  expired.
- A delivery job's record names its sliced file, and its end moves that file's due time.
- On a fake clock: a daemon going offline writes the time of its last sync to its
  paired-printer record once and no more however long it stays off; a restarted front
  server reports that same time; a daemon silent from just before a restart is reported,
  two minutes after the restart, as silent "for at least" the time since the restart.
- The daemon's routes are reached without a cookie and refused without a valid token.
- Each rate limit refuses the request past its figure and admits it once the fake clock
  moves on.

## Secrets

PenguinSlicer has six secrets. The front server holds four, as settings given to it
through Railway (*proposed* names): the Onshape app's identifier and secret
(`ONSHAPE_CLIENT_ID`, `ONSHAPE_CLIENT_SECRET`), which prove to Onshape that a sign-in comes
from PenguinSlicer; the cookie key (`PENGUIN_COOKIE_KEY`, and the previous one,
`PENGUIN_COOKIE_KEY_PREVIOUS`); from phase 5 the relay's secret key
(`PENGUIN_RELAY_SECRET_KEY`); and the credential that reads and writes both buckets
(`PENGUIN_R2_ACCESS_KEY_ID`, `PENGUIN_R2_SECRET_ACCESS_KEY`, with the account's endpoint
and the buckets' names as plain settings). None is in the repository, a bucket, a log line
or a page. A missing secret stops the start with a log line naming the missing setting
(*proposed*), except where the development identity stands in on one machine.

Every one can be replaced, and a planned replacement interrupts nobody who uses
PenguinSlicer within a week of it; how each is replaced and what an emergency replacement
costs is in [the architecture](../docs/architecture.md#security), and the written
procedure for each is built in phase 3. The front server's own two points:

- **The cookie key:** two keys, the previous one kept one week
  ([Two cookie keys](#two-cookie-keys-and-replacing-one)).
- **The Onshape app's secret:** no cookie depends on it, so replacing it signs nobody out.
  **Open:** [replacing the Onshape app's secret](README.md#replacing-the-onshape-apps-secret)
  (whether sign-ins fail between Onshape issuing the new secret and the front server having
  it; whether old tokens can still be renewed from phase 4).

### Tests

- A start with a secret missing stops with a line naming the setting.
- No answer, page or log line carries any secret's value (the log search of
  [The log](#the-log) covers the lines; a search of every answer in the suite covers the
  rest).

## Limits

Every figure, what it protects and where it comes from. A figure that is a length of time
is checked by a test with a fake clock.

| Limit | Figure | Protects | From | Name (*proposed*) |
|---|---|---|---|---|
| Threads serving requests | 100 | The front server's memory; a known ceiling | The design's choice | `PENGUIN_FRONT_THREADS` |
| Idle daemons served | About fifty | Room for users' requests | 100 threads, one per idle daemon | |
| Users served at once | None set | A user's request finding a thread | Undecided | |
| One part | 7,500,084 bytes (7.5 MB) | The slice service's checks and memory | The plate configuration's contract | `MAX_PART_BYTES` |
| A sliced file | No ceiling; 8.8 to 14.1 MB so far | A fetch inside Cloudflare's 100 MB | Measured | |
| A stream with nothing to report | A comment at least every 15 s | The stream staying open | Cloudflare's 125 s and Railway's five minutes | `PROGRESS_KEEPALIVE_S` |
| Any one request | Closed by Railway after 15 minutes | Nothing of ours | Railway | |
| The cookie | Thirty days from sign-in | Onshape's allowance | The design's choice | `COOKIE_LIFETIME_S` |
| The cookie's size | About 4 KB | Being able to sign in | Browsers | |
| A sign-in | 2 calls to Onshape | The allowance of 2,500 a year | Onshape's interface | |
| Sign-ins by one user, or in one day | None set | The allowance | Undecided | |
| The previous cookie key | Kept one week | Users away briefly | The design's choice | `PREVIOUS_COOKIE_KEY_KEPT` |
| A sliced file kept | Two hours after its slice ended, or after its last print ended if later | Sending again after a print | The design's choice | `SLICED_FILE_KEPT_S` |
| R2's backstop on sliced files | Three days from last stored | A file the front server failed to delete | The design's choice | An R2 lifecycle rule |
| Log lines in the log bucket | Ninety days | A problem reported weeks later | The design's choice | An R2 lifecycle rule |
| Gathering the log | About once a minute | Lines lost in a crash | The design's choice | `LOG_FLUSH_S` |
| The sweep | No figure | How long an unasked-for file outlives its two hours | Undecided | `SWEEP_INTERVAL_S` |
| A held sync (phase 5) | Up to 55 s | A send reaching the daemon at once | Printer delivery | The relay's |
| Offline (phase 5) | No sync for two minutes | The silent-printer note | Printer delivery | The relay's |
| A delivery job's record (phase 5) | Kept a day after the delivery job ends | The daemon not dropping its job | Printer delivery | The relay's |

No target for time is set for the front server: not for how long it may take to answer,
nor for the time between a slice ending and the page being told, nor for a fetch of a
sliced file. They are measured on the first slices on the hosted service in phase 3, and
the log lines must carry what that measurement needs (*proposed*: each sliced file's
stored line carries the time from the slice's end to its storing).

## Security

**Who can reach it.** Anyone on the internet. It answers three kinds of caller: a browser
with a cookie it can read; from phase 5, a daemon with a token the relay signed; and, for
the one request of offering a pairing code, an unpaired daemon, which is rate-limited.
Everyone else gets the sign-in or a refusal. The sign-in is open to anyone with an Onshape
account; what bounds such a person is what bounds every user: one unfinished slice job at a
time, at most 25 parts in the part store for one user key, every slice bounded in memory
and time, and from phase 5 wrong pairing codes limited for each user. **Open:**
[who may sign in](README.md#who-may-sign-in).

**What it trusts:** Onshape's word on who a user is and their groups; its own secrets; the
contents of the state bucket, because only it and the owner can write there; the slice
service's results. **What it treats as hostile:** everything from a browser (the cookie
until it decrypts and is in date, the current group until the cookie confirms it, any claim
of whose a thing is, any changing request without the wizard's mark). Uploaded parts are
hostile too, but the front server never opens or parses them; it passes them to the slice
container. The slice container can call the front server over the private network and
meets the same sign-in there as anyone else (*proposed*: no route trusts the private
network).

**What a flaw in it would expose: everything.** It holds all four secrets. That is why it
is kept small, opens no uploaded file and runs no Orca.

**Accepted risks:** a removed user's thirty days; no permissions inside a group (any user
may edit the configuration, pair the printer and send a print, which starts with nobody at
the printer); users of a group see each other's names and the one-line description of the
plate printing; a flaw in the slice service itself could hand the front server any file as
a sliced file, which is not inspected; a sliced file resting at R2 until the backstop; a
leaked key costs every user a sign-in or every group a pairing; names in the log for ninety
days; no second copy of the configurations and paired-printer records.

## Error reports

Every failure a caller can see is an [error report](../contracts/error-report.md): a
sentence a user understands, what to do next, and the detail kept for the log; each has a
test that produces it on purpose. The front server passes the slice service's error reports
(`slice.*`) and, from phase 5, the relay's (`delivery.*`) to the page unchanged. Its own
codes are of the form `front.<what>`; the codes, the rows and each one's "Retryable" are
*proposed*, and are fixed when [the contract with the wizard](../contracts/wizard-front-server.md)
is written.

| Code | When | What the user sees | Retryable |
|---|---|---|---|
| `front.not_signed_in` | A route that needs a signed-in user, with no cookie, one neither cookie key reads, or one past its thirty days | That the sign-in has ended and their work is kept in the browser, with Sign in with Onshape | No |
| `front.sign_in_failed` | The callback's value is not the one sent out, or Onshape refused the sign-in | A plain page: PenguinSlicer could not sign them in with Onshape, and what is specific, with Sign in with Onshape | No |
| `front.onshape_unreachable` | Onshape did not answer, at sign-in or when reading the groups again | The same plain page, saying Onshape did not answer | Yes |
| `front.group_not_allowed` | The request names no current group, or one the cookie does not list | That they are not in that group; the page takes the first of their groups and says so | No |
| `front.not_from_wizard` | A changing route without the wizard's mark, or from another address | Nothing, in honest use | No |
| `front.configuration_changed` | The configuration was written by someone else since the edit's read | That it was changed by someone else; reload and edit again | No |
| `front.configuration_unreadable` | The group's document is not JSON, of an unknown format number, or fails the schema | That the configuration cannot be read; tell whoever wrote it | No |
| `front.sliced_file_expired` | The sliced file is due, or gone from the state bucket | That it has expired; slice the plate again | No |
| `front.sliced_file_unknown` | No sliced file of that slice job under the user's key | That it is not known; slice the plate again | No |
| `front.slice_unreachable` | The slice service did not answer, or answered that it is stopping | Nothing at first, then that the server is being slow | Yes |
| `front.state_bucket_unreachable` | Reading or writing the state bucket failed | Nothing at first, then that the server is being slow | Yes |

**Cancelling.** A user's cancel of a slice job is passed to the slice service, which stops
Orca itself; a new submission cancels the earlier slice job the same way; from phase 5 a
cancel of a print is passed to the relay. The front server has no long work of its own to
cancel. **A page that goes away** cancels nothing: the slice runs to its end, bounded by
the slice service's time limit, and the front server collects the result.

## The fast suite

The front server is its own `uv` project in `front/`, whose commands run with
`make -C front ...` (*proposed* targets, as the other components have: `install`, `test`,
`test-parallel`, `coverage`, and outside the fast suite `test-r2` and `test-hosted`, the
short scripted check run against the hosted service after each deploy).

The fast suite uses no real network, no real waiting and no fixed ports, and passes in any
order, any number of times. A test that fails once is fixed at its cause, never retried.

- **Onshape** is a stand-in that answers as Onshape's OAuth and its user and company calls
  do, and counts the calls it receives. No test calls Onshape, and a test fails if anything
  tries.
- **The slice service** is a stand-in that answers as its HTTP interface does and lets a
  test put its events in an exact order: a slice ending just before a restart, a fetch
  failing halfway, a stop beginning while a plate configuration arrives.
- **The relay** (phase 5) is the real relay with fakes for the daemons, which put syncs in
  an exact order.
- **The buckets** are the folder form, in a fresh temporary folder for each test.
- **Time** is a fake clock the test moves: thirty days, two hours, two minutes, a minute and
  fifteen seconds pass in an instant. A test waits on an event, never on a duration.
- **Servers** a test needs listen on a port the system chooses.

Rules the suite is held to:

- Every refusal, limit and change of state named in this document has a test that reaches
  it and checks what the caller sees; every error report has a test that produces it.
- The tests that every request needs a signed-in user, that every request acting for a
  group checks the group, and that every changing request needs the wizard's mark discover
  the front server's routes by themselves.
- Each row of the restart table is a test ([Starting](#starting-and-what-a-restart-does)).
- The previous version's page is run against the new front server.
- No log line of the whole run holds the cookie, a token or a key.
- The folder form and the R2 form of the buckets pass the same tests.
- From phase 5, the front server's store passes the relay's own tests of a store.

What only the real thing can prove: how Railway behaves at a deploy; that Cloudflare and
Railway pass progress on as it is sent; that a 7.5 MB upload passes Railway; what Onshape
really answers, above all for an account with no company; that Chrome keeps the cookie for
a page embedded in Onshape; and the front server's memory under load. After each deploy a
short scripted check runs against the hosted service.

## By phase

What of the front server is built in each phase, from
[the guide](README.md#what-is-built-in-which-phase).

**Phase 2, one machine, no Onshape, no printer.** The front server runs beside one slice
service process on one machine, with the development identity and a folder for each
bucket. Built here, each with its tests:

- serving the wizard's pages;
- the development identity and the cookie, with one cookie key;
- the user key, and the check of the current group against the cookie;
- the route that answers the user's name and groups, for the header;
- limits on how fast one user may upload parts and submit plate configurations (figures
  not yet proposed);
- passing parts and plate configurations to the slice service, asking about a slice job,
  and the progress streams;
- following every slice job, storing the sliced file and its summary, collecting at start;
- the two-hour rule: refusing, deleting and the sweep;
- the configuration: the default, reading, and the conditional write;
- the log, gathered once a minute into the folder that stands for the log bucket;
- the version on every answer.

To be settled before phase 2 is built: the contract's routes, including the value that
makes a repeated submission harmless, the report that tells a cancel for a stop from the
others, and the moment of expiry; and where the list of settings and the profile catalog's
names come from.

**Phase 3, hosted.** First, before anything else of this phase, what Railway does at a
deploy is tried. Then:

- the front server in its own container at `https://penguinslicer.popcornpenguins.com/`,
  calling the slice container over the private network;
- the two buckets at R2, with the three-day backstop and the ninety days for the log;
- signing in with Onshape, with every call counted, and "sign in again";
- the defences against requests from other sites;
- the second cookie key, and the written procedure for replacing each secret;
- the format number on every record in the state bucket;
- finishing work in flight when asked to stop;
- the refusal to start with the development identity on Railway;
- the command that reads the log bucket, and the check that runs after each deploy.

Recommended in the guide's open items for phase 3, not yet decided: the list of permitted
groups, the limits on sign-ins, breaking the repeated sign-in when the cookie is withheld,
signing out, and telling the owner when the check after a deploy fails.

**Phase 4, inside Onshape.** The panel uses the same sign-in and the same routes, so
nothing of the above changes. What is new is the front server's calls to Onshape for the
parts a user selected, on behalf of the Onshape integration, a separate component. Those
calls use the tokens in the cookie, which is when renewing them first matters. How that
work divides between the browser and the front server, what it costs in calls for each
part, and the permissions the app then asks for are designed in that phase before anything
is built. Its first step, as the guide recommends, is a trial in real Chrome of the cookie
inside Onshape's panel.

**Phase 5, the real printer.** The relay joins the front server's process. The front server
gives it who is asking, the store for its records and the sliced file; applies the second
half of the sliced file's rule (two hours after the last print, found from the delivery
jobs' records, and storing afresh at each send); makes a repeated send harmless; holds the
relay's secret key; lets the daemons' requests in; applies the limits on how fast one user
or one daemon may send the relay requests; answers the held syncs when stopping; and
gathers the relay's log lines and what the daemons report about themselves. It builds on
printer delivery's tests rewritten on a fake clock, which are the first piece of phase 5.

**In no phase:** the configuration's edit screens; permissions inside a group; more than
one printer for a group; the different kind of server for many daemons; and, until the
Onshape app is public, reading a signed-in user's groups again once a day with the
renewing of tokens it needs.
