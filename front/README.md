# The front server

Nothing of the front server is built yet: this guide describes its design. Every rule,
figure and required test is in [README-details.md](README-details.md).

## What it is

The **front server** is the one process the internet reaches. Behind
`https://penguinslicer.popcornpenguins.com/` it serves the wizard's pages, signs users in
with Onshape, passes parts and slice jobs to the slice service, stores and serves sliced
files, reads and writes each group's configuration, gathers the log, and from phase 5
hosts the relay of [printer delivery](../delivery/README.md).

It is a component of its own because it holds what the rest must not. The
[slice service](../slice/README.md) runs Orca on files strangers upload, so it runs in the
**slice container**, which holds no credentials and is reached only from the front
server, over Railway's private network. The **wizard**, the code in the browser
([its guide](../wizard/README.md)), talks only to the front server. The front server holds
the sign-in secrets and the one credential that writes to the buckets. The whole is in
[the architecture](../docs/architecture.md). The phases are
[the plan's](../docs/plans/penguin-slicer-plan.md): 2, one machine; 3, hosted on Railway;
4, inside Onshape; 5, the real printer.

More: [Where the front server sits](README-details.md#where-the-front-server-sits).

## What it holds, and what it never holds

It keeps no database and no table of sessions. What must outlast its restart is in two
object stores at Cloudflare R2, written only with its credential and by the project's
owner; on one machine a folder stands in for each, behind the same interface.

| Store | What the front server keeps there | For how long |
|---|---|---|
| The **state bucket** | Each group's configuration; the sliced files; from phase 5, the records printer delivery keeps (below) | A sliced file, two hours after its slice ended; a configuration, until edited |
| The **log bucket** | Log lines of the front server, the slice service and, from phase 5, the relay | Ninety days |

It never holds a user's part (parts live in the browser's storage and, as a cache, in the
slice service) and never a session (who is signed in lives in a cookie in the browser).

More: [The bucket interface](README-details.md#the-bucket-interface).

## Signing in

Every user signs in with Onshape's OAuth, in Onshape's panel and outside it alike; there
are no accounts or passwords of PenguinSlicer's own. Onshape says who the user is and
which companies and classrooms they belong to: each is a **group**, the users who share
one configuration and one printer (a user in none is a group of one). The user works in
one, the **current group**, which the browser sends with each request and the front
server accepts only if the cookie lists it.

A sign-in sets one encrypted **cookie** holding the user's identity, groups and Onshape
tokens, for thirty days from the sign-in, since each sign-in costs calls to Onshape.
Nothing about a session is kept on the server, so a restart signs nobody out. When the
**cookie key**, which encrypts it, is replaced, the previous key still reads for one week and
each such cookie is rewritten with the new one. Every route that changes something also
requires a header only the wizard's page can set, and checks the request's origin.

**Calls to Onshape are scarce.** Until the Onshape OAuth app is public in Onshape's App
Store, its calls count against a yearly allowance of 2,500 on a free or education
account, so nothing calls Onshape that can be done without it.

| Use | Calls to Onshape |
|---|---|
| A sign-in to the hosted service | 2, once in thirty days for each browser |
| Reading a signed-in user's groups again | None until the app is public, when they are read once a day |
| Work on one machine, and the automated tests | None |

Until the app is public, groups are read only at sign-in: a user removed from an Onshape
company keeps its configuration and printer for up to thirty days, and a user added to
one uses "sign in again" in the wizard's header. Until phase 4, twenty people using the
hosted service for two months spend about 80 calls. Every call writes a log line.

**On one machine** a setting signs in the **development identity**, a fixed made-up user
and group, with no call to Onshape; the front server refuses to start with that setting on
Railway or beside Onshape credentials.

More: [Onshape sign-in](README-details.md#onshape-sign-in), [The cookie](README-details.md#the-cookie), [Calls to Onshape](README-details.md#calls-to-onshape).

## Its interface

Routes are named by what they do; paths and shapes go in
[the contract with the wizard](../contracts/wizard-front-server.md), not yet written.
Behind them the front server calls the slice service, the two buckets and Onshape.

| Route | Called by | Needs |
|---|---|---|
| The wizard's pages | The browser | A signed-in user (otherwise the sign-in starts) |
| Sign-in: start, Onshape's callback, sign in again | The browser | Nothing |
| The user and their groups; read or write a group's configuration | The wizard | A signed-in user and a current group the cookie lists |
| Upload a part; submit, ask about, follow or cancel a slice job; fetch a sliced file | The wizard | A signed-in user |
| From phase 5: pair, send, follow, cancel, unpair | The wizard | A signed-in user and a current group the cookie lists |
| From phase 5: the daemon's routes | A daemon (the program beside a printer) | The daemon's token, except its offer of a pairing code, which is rate-limited |

More: [Which routes need a signed-in user](README-details.md#which-routes-need-a-signed-in-user), [Error reports](README-details.md#error-reports).

## What it does for a slice

1. **A part is added.** The wizard uploads it, at most 7.5 MB, and the front server passes
   it to the slice service with the **user key**: the signed-in user's Onshape id, taken
   from the cookie and never from the browser, so a user reaches only their own parts,
   slice jobs and sliced files. The slice service checks the part and keeps it.
2. **A plate is submitted.** On the Preview step the wizard sends a plate configuration
   (layout and settings) naming each part by its hash, with no files; the front server passes it on with the
   user key. A user has one unfinished slice job at a time.
3. **The slice runs.** The page follows it on a **progress stream** (server-sent events)
   through the front server, which sends a comment line at least every fifteen seconds so
   that neither Cloudflare (125 seconds without data) nor Railway (five minutes) closes it.
4. **The slice ends.** The front server follows every unfinished slice job itself, page
   open or not. It fetches the sliced file (8.8 to 14.1 MB on the plates measured) and
   stores it in the state bucket; the slice container then deletes its own copy.
5. **The user previews and downloads** the state bucket's copy, through the front server,
   for two hours after the slice ended. Past that the front server refuses the sliced file
   and deletes it. A one-day deletion rule at R2 catches any file it failed to delete, so
   such a file may rest there up to about two days.

More: [Parts and slice jobs](README-details.md#parts-and-slice-jobs-passed-to-the-slice-service), [Two hours](README-details.md#two-hours-deleting-and-the-backstop).

## What it does for a print, from phase 5

The **relay**, printer delivery's server half, runs inside the front server's process;
each daemon calls it with a **sync** carrying the printer's status. The front server tells
the relay who is asking (the user and the current group), keeps its records in the state
bucket (each group's paired-printer record, naming its daemon, and the record of each
**delivery job**, one sliced file on its way to a printer), and gives it the sliced file,
kept past its two hours while a delivery job needs it. An idle daemon's sync is held open
up to 55 seconds, one thread each: with 100 threads the front server has room for about
fifty idle daemons beside everything else.

More: [Hosting the relay](README-details.md#hosting-the-relay-from-phase-5), [Threads](README-details.md#threads).

## The configuration

A group's **configuration** (its filaments and the units of uploaded files, no secret) is
one JSON document in the state bucket, read whole and written whole, in the shape of
[its contract](../contracts/configuration.md). A group with no document gets a built-in
default, so a new group can slice at once. An edit is written only if the document has
not changed since it was read, so of two users editing at once the second is told to
reload. Every edit writes a log line with the user's name and what changed.

More: [The configuration](README-details.md#the-configuration).

## The log

The front server writes a JSON line for each sign-in, call to Onshape and configuration
edit, every error a user is shown, every exception and refusal, and once a minute its
memory, the slices running and waiting, the connections held open and the threads in
use. It fetches the slice service's lines from a route of the slice service, adding each
line's group, and about once a minute writes all of them to the log bucket as a new file;
Railway's log view keeps them seven days. No line holds a secret or a part's geometry.

More: [The log](README-details.md#the-log).

## When it restarts

The project is deployed continuously. Starting, the front server asks the slice service
for its slice jobs, follows the unfinished ones and stores each finished one's sliced file
not yet stored. Asked to stop, it finishes uploads and downloads in progress, closes its
progress streams and answers held syncs, so pages and daemons reconnect to its
replacement; the page retries, so a user sees a pause. Every answer carries the front
server's version; a page that sees a newer one reloads itself when nothing is in flight.

More: [Stopping](README-details.md#stopping), [The version on every answer](README-details.md#the-version-on-every-answer).

## Running and testing it

Nothing runs yet. It will be its own `uv` project, run with `make -C front ...`. Its fast
suite will use a stand-in for Onshape, folders for the buckets, no real network, no real
waiting and no fixed ports; every failure a caller can see will be an error report with a
test that produces it on purpose.

More: [Tests](README-details.md#tests).

## What is built in which phase

| Phase | What of the front server is built |
|---|---|
| 2, one machine | Serving the pages; the development identity and the cookie; the user key and the current group's check; passing parts and slice jobs; following slice jobs and storing sliced files; the two hours; the configuration; the log; a folder for each bucket |
| 3, hosted on Railway | Its own container at the public address; the buckets at R2; Onshape sign-in; the checks on requests from other sites; two cookie keys; the version on every answer; finishing work when asked to stop |
| 4, inside Onshape | Nothing new: the panel uses the same sign-in and the same routes |
| 5, the real printer | Hosting the relay, with its records in the state bucket |

More: [By phase](README-details.md#by-phase).

## What is not known

- **Onshape**: the owner's account's allowance, whether the development and hosted OAuth
  apps share it, whether renewing a token counts as a call (from phase 4), what Onshape
  answers for an account with no company or classroom, and whether an old app secret
  stops working the moment it is replaced.
- **The cookie's size**: whether identity, groups and both Onshape tokens fit, encrypted,
  in the about 4 KB a cookie holds; and two requests renewing the tokens at once must not
  leave a spent refresh token in it.
- **Cloudflare and Railway**: whether they pass server-sent events on without holding
  them (if not, the page asks every second or two instead); whether Railway starts the
  new container before stopping the old, and how long a stopping front server has; and
  Railway's limit on a request body, which a 7.5 MB part should pass.
- **The front server's memory with fifty held syncs**: never measured.

More: [the architecture](../docs/architecture.md), which lists everything not yet checked.
