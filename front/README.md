# The front server

Nothing of the front server is built yet: this guide describes its design, and
[README-details.md](README-details.md) holds every rule, figure and required test.

## What it is

The **front server** is the one process the internet reaches. Behind
`https://penguinslicer.popcornpenguins.com/` it serves the wizard's pages, signs users in
with Onshape, passes parts and slice jobs to the slice service, stores and serves sliced
files, reads and writes each group's configuration, gathers the log, and from phase 5
hosts the relay of [printer delivery](../delivery/README.md).

It is a component of its own because it holds what the rest must not: the sign-in secrets
and the one credential that writes to the buckets. The [slice service](../slice/README.md)
runs Orca on files strangers upload, in the **slice container**, which holds no
credentials and is reached only from the front server, over Railway's private network.
The **wizard**, the code in the browser ([its guide](../wizard/README.md)), talks only to
the front server. The whole is in [the architecture](../docs/architecture.md). The phases
are [the plan's](../docs/plans/penguin-slicer-plan.md): 2, one machine; 3, hosted; 4, inside Onshape; 5, the real printer.

More: [Where the front server sits](README-details.md#where-the-front-server-sits).

## What it holds, and what it never holds

It keeps no database and no table of sessions. It never holds a user's part (parts live in
the browser's storage and, as a cache, in the slice service) and never a session (who is
signed in lives in a cookie in the browser). What must outlast its restart is in two
object stores at Cloudflare R2, written only with its credential and by the owner; on one
machine a folder stands in for each, behind the same interface.

| Store | What the front server keeps there | For how long |
|---|---|---|
| The **state bucket** | Each group's configuration; the sliced files; from phase 5, the records printer delivery keeps (below) | A sliced file, until two hours after its slice ended or two hours after its last print ended (from phase 5), whichever is later; a configuration, until edited |
| The **log bucket** | Log lines of the front server, the slice service and, from phase 5, the relay, and daemon telemetry | Ninety days |

More: [The bucket interface](README-details.md#the-bucket-interface).

## Signing in

Every user signs in with Onshape's OAuth, in Onshape's panel and outside it alike; there are
no accounts or passwords of PenguinSlicer's own. Onshape says who the user is and which
companies and classrooms they belong to: each is a **group**, the users who share one
configuration and one printer (a user in none is a group of one). The user works in one,
the **current group**, sent with each request that acts for a group and accepted only if
the cookie lists it.

A sign-in sets one encrypted **cookie** holding the user's identity, groups and Onshape
tokens, for thirty days from the sign-in, since each sign-in costs calls to Onshape; a
restart signs nobody out. When the **cookie key**, which encrypts it, is replaced, the front
server still reads cookies made with the previous key for one week, rewriting each with the
new key; a user away for that whole week signs in again. Every route that changes something
on the strength of the cookie also requires a header only the wizard's page can set, and
checks the request's origin.

**Calls to Onshape are scarce.** Until the Onshape app is public in Onshape's App Store, its
calls count against a yearly allowance of 2,500 on a free or education account, so nothing
calls Onshape that can be done without it.

| Use | Calls to Onshape |
|---|---|
| A sign-in to the hosted service | 2, once in thirty days for each browser |
| Reading a signed-in user's groups again | None until the app is public, when they are read once a day |
| Work on one machine, and the automated tests | None |
| Reading parts from Onshape, from phase 4 | Several for each part; counted in phase 4's design |

Until the app is public, groups are read only at sign-in: a user removed from an Onshape
company keeps its configuration and printer for up to thirty days, and a user added to one
uses "sign in again" in the wizard's header. Until phase 4 adds reading parts, twenty
people using the hosted service for two months spend about 80 calls, each logged.
**On one machine** a setting signs in the **development identity**, a fixed made-up user
and group, with no call to Onshape; the front server refuses that setting on Railway or
beside Onshape credentials.

More: [Onshape sign-in](README-details.md#onshape-sign-in), [The cookie](README-details.md#the-cookie), [Calls to Onshape](README-details.md#calls-to-onshape).

## What it does for a slice

1. **A part is added.** The wizard uploads it, at most 7.5 MB, and the front server passes
   it to the slice service with the **user key**: the signed-in user's Onshape id, taken
   from the cookie and never from the browser, so a user reaches only their own parts,
   slice jobs and sliced files. The slice service checks the part and keeps it.
2. **A plate is submitted.** On the Preview step the wizard sends a plate configuration
   (layout and settings) naming each part by its hash, with no files; the front server
   passes it on with the user key. A user has one unfinished slice job at a time:
   submitting a plate cancels the user's earlier one.
3. **The slice runs.** The page follows it on a **progress stream** (server-sent events)
   through the front server, which sends a comment line at least every fifteen seconds so that
   neither Cloudflare (125 seconds without data) nor Railway (five minutes without data)
   closes it early; Railway closes any request after fifteen minutes, and the page reconnects.
4. **The slice ends.** The front server follows every unfinished slice job itself, page
   open or not, then stores the sliced file in the state bucket; the slice container
   deletes its own copy.
5. **The user previews and downloads** the state bucket's copy, through the front server,
   until two hours after the slice ended or after its last print ended, whichever is later;
   past that the front server refuses and deletes it, and a three-day rule at R2 catches any
   it missed (such a file rests up to about four days after it was stored).

More: [Parts and slice jobs](README-details.md#parts-and-slice-jobs-passed-to-the-slice-service), [Two hours](README-details.md#two-hours-deleting-and-the-backstop).

## What it does for a print, from phase 5

The **relay**, printer delivery's server half, runs inside the front server's process.
Its records are each group's paired-printer record, which names its daemon (the program
beside a printer), and one record for each **delivery job**, one sliced file on its way to
a printer. The front server does three things for the relay: it tells it who is asking
(the user and the current group); it keeps its records in the state bucket; and it gives
it the sliced file, kept until two hours after its last print ended if that is later.

A daemon reports with a **sync**, a request carrying the printer's status. The relay holds
back its answer to an idle daemon's sync for up to 55 seconds, so that a send reaches the
daemon at once. Each held sync takes one thread: with 100 threads the front server has
room for about fifty idle daemons beside everything else.

More: [Hosting the relay](README-details.md#hosting-the-relay-from-phase-5), [Threads](README-details.md#threads).

## Its interface

Routes are named by what they do; paths and shapes go in the not yet written
[contract with the wizard](../contracts/wizard-front-server.md). Every request that acts
for a group carries the current group; the first three rows below carry none.

| Route | Called by | Needs |
|---|---|---|
| The wizard's pages | The browser | A signed-in user (otherwise the sign-in starts) |
| Sign-in: start, Onshape's callback, sign in again | The browser | Nothing |
| The user and their groups (a route to be settled) | The wizard | A signed-in user; no current group |
| Read or write the configuration; upload a part; submit, ask about, follow or cancel a slice job; fetch a sliced file; from phase 5, pair, send, follow, stop following, cancel, unpair | The wizard | A signed-in user and a current group the cookie lists |
| From phase 5: the daemon's routes | A daemon | The daemon's token, except its offer of a pairing code, which is rate-limited |

More: [Which routes need a signed-in user](README-details.md#which-routes-need-a-signed-in-user), [Groups and the current group](README-details.md#groups-and-the-current-group), [Error reports](README-details.md#error-reports).

## The configuration

A group's **configuration** (its filaments, each with a colour shown where a user chooses
it and with its profiles under the group's own names; the printer's Orca profile, which
gives the plate's size; the units of uploaded files; no secret) is one JSON document in
the state bucket, read and written whole ([its contract](../contracts/configuration.md)).
A group with no document gets a built-in default, so a new group can slice at once. An
edit is written only if the document has not changed since it was read, so of two users
editing at once the second is told to reload. Every edit is logged with who and what.

More: [The configuration](README-details.md#the-configuration).

## The log

The front server writes a JSON line for each sign-in, call to Onshape and configuration
edit, every error a user is shown, every exception and refusal, and once a minute its
memory, the slices running and waiting, the connections held open and the threads in use.
It fetches the slice service's lines from a route of the slice service, adding each line's
group, and about once a minute writes all of them to the log bucket as a new file. Every
line also goes to Railway's log view, which keeps it seven days; the log bucket keeps it
ninety. No line holds a secret or a part's geometry.

More: [The log](README-details.md#the-log).

## When it restarts

The project is deployed continuously. Starting, the front server asks the slice service for
its slice jobs, follows the unfinished ones and stores each finished one's sliced file not
yet stored. Asked to stop, it finishes uploads and downloads in progress, closes its
progress streams and answers held syncs, so pages and daemons reconnect to its replacement;
the page retries, so a user sees nothing for 20 seconds, then a message that the server
is slow with a countdown, and an error only after 300 seconds.
Every answer carries its version; a page that sees a newer one reloads when nothing is in flight.

More: [Stopping](README-details.md#stopping), [The version on every answer](README-details.md#the-version-on-every-answer).

## Running and testing it

Nothing runs yet. It will be its own `uv` project, run with `make -C front ...`; its fast
suite uses a stand-in for Onshape, folders for the buckets, no real network or waiting and
no fixed ports, and every failure a caller can see gets an error report and a test.

More: [The fast suite](README-details.md#the-fast-suite).

## What is built in which phase

| Phase | What of the front server is built |
|---|---|
| 2, one machine | Serving the pages; the development identity and the cookie, with one cookie key; the user key and the current group's check; passing parts and slice jobs; following slice jobs and storing sliced files; refusing and deleting sliced files after two hours; the configuration; a folder for each bucket; the log, gathered into the folder for the log bucket; the version on every answer, for the wizard's reloading |
| 3, hosted on Railway | Its own container at the public address; the buckets at R2, the log bucket among them; Onshape sign-in; the second cookie key; the other rules for old and new versions together (a format number on each record); finishing work when asked to stop; the checks that matter only when hosted: on requests from other sites, and refusing to start with the development identity on Railway |
| 4, inside Onshape | Nothing new for sign-in or routes; reading parts from Onshape is designed in that phase |
| 5, the real printer | Hosting the relay, with its records in the state bucket |

More: [By phase](README-details.md#by-phase).

## What is not known

- **Onshape**: the owner's account's allowance, and whether a development app of the same
  account shares it; whether renewing a token counts as a call (from phase 4); what it
  answers for an account with no company or classroom; whether a replaced secret stops at once.
- **The cookie's size**: whether identity, groups and both tokens fit, encrypted, in about 4 KB.
- **Cloudflare and Railway**: whether they pass server-sent events on without holding them
  (if not, the page asks every second or two instead); whether Railway starts the new
  container before stopping the old, and how long a stopping front server has; Railway's
  limit on a request body, which a 7.5 MB part should pass.
- **The front server's memory with fifty held syncs**: never measured.

More: [the architecture](../docs/architecture.md), which lists everything not yet checked.
