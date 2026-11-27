# Printer delivery

Printer delivery takes a sliced file (the `.gcode.3mf` file the slice service makes) and
gets it printed on a Bambu Lab printer, reporting how the print goes. Everything here is
true of the code as built except the section [To be built](#to-be-built). The detailed
guide, for someone changing printer delivery, is [README-details.md](README-details.md).

## What it does

Printer delivery has two halves, and a simulated printer for testing them:

- **The relay** runs on the server. It pairs with a daemon, holds each printer's
  delivery jobs and last status, and answers the caller.
- **The daemon** runs on **the daemon's computer**: the computer next to the printer, on
  the printer's network. It connects outward to the relay, downloads the sliced file,
  uploads it to the printer and starts it. It opens no port, so nothing on the internet
  can call that computer. It is a plain Python program for Windows, macOS or Linux.
- **The simulated printer** plays a Bambu H2S to the daemon over real sockets, for tests.

The **caller** is the application that runs the relay and asks it to deliver sliced
files: it signs users in and holds the sliced file; in PenguinSlicer it will be the front
server, from phase 5 of [the plan](../docs/plans/penguin-slicer-plan.md). A **delivery
job** is one sliced file's way from the caller's send to the end of its print. The
**pairing code** is eight symbols the daemon's `pair` command shows; as built it is a
lasting secret the caller presents for its users, telling the relay which daemon to use.

The daemon starts a print only after asking the relay's **start gate**, which says yes
once per delivery job and never to a cancelled one. After the **start command** (the
message that tells the printer to begin) the daemon sends that printer no other start
command until the printer's own reports show what became of the first (the **hold**), so
no file is started twice, across restarts of either half.

Deeper: [Printer delivery](README-details.md#printer-delivery), [Layout](README-details.md#layout).

## The states of a delivery job

A delivery job is `queued` until a sync hands it to the daemon, then `running` through
its stages (among them waiting for the printer, downloading, uploading, starting,
printing, waiting for a person), and ends `done`, `failed` or `cancelled`. Only evidence
ends a delivery job: the printer's own report, the daemon's acknowledgement, or the
15-minute deadline passing with the start gate never asked, after which the gate stays
shut. A printer paused or waiting for someone is a stage, never an end. A report whose
daemon or printer has gone quiet is marked **stale**, not ended; past the start gate, the
caller may **stop following** it, and the relay does so by itself after 24 hours of
continuous staleness, saying the outcome is unknown. This is the one place where time
alone ends a delivery job.

Deeper: [Delivery jobs](README-details.md#delivery-jobs) and
[How a start is decided](README-details.md#how-a-start-is-decided).

## Interfaces

The caller builds the relay with `create_app`, giving it a secret key that signs the
daemons' tokens, a function that says who is asking and which pairing code they may use,
and one that finds the sliced file for a send. The routes for the caller's pages:

| Route | What it does |
|---|---|
| `GET /printer/status` | Paired or not, online or not, the printer's status, whether a delivery job is waiting to start, how the last delivery job ended (kept 10 minutes), and the latest delivery job's progress report |
| `POST /printer/jobs` | A send: creates a delivery job, or refuses with an error report |
| `GET /printer/jobs/<id>` | The delivery job's latest progress report |
| `GET /printer/jobs/<id>/events` | The progress reports as a server-sent event stream |
| `POST /printer/jobs/<id>/cancel` | Cancels a delivery job that has not passed the start gate |
| `POST /printer/jobs/<id>/stop-following` | Gives up a stale delivery job past the start gate, whose outcome cannot be known |

The daemon's routes: the pairing exchange (the daemon trades its pairing code for a
**token**, which it presents on every later request), the **sync** (the daemon posts the
printer's status and its delivery job's progress; the answer carries a job, a cancel or
nothing), the start gate, the acknowledgement (the daemon's word that the print was seen
going, or that the delivery job failed or was cancelled before it started), a read-only
ping, and the download of the sliced file. Every failure a caller can meet is an
[error report](../contracts/error-report.md); progress reports follow
[the progress report contract](../contracts/progress-report.md).

Deeper: [The caller's routes](README-details.md#the-callers-routes),
[The interface the relay offers its caller](README-details.md#the-interface-the-relay-offers-its-caller)
and [Error reports](README-details.md#error-reports).

## The figures that matter, as built

| Figure | Value | What it bounds |
|---|---|---|
| Sync interval | 5 s; at most once a second while a job's progress moves; at once on a change of the printer's state | How old the relay's picture of the printer is |
| Stale limit | 20 s without the daemon; past the start gate also 60 s without the printer, or at once when the printer is unreachable | When a running delivery job's report is marked stale |
| Online limit | 2 min | When a daemon counts as silent and a send is refused |
| Collection deadline | 3 min | A delivery job no daemon collects |
| Start-gate deadline | 15 min after collection | A collected delivery job whose daemon never asks the start gate; past the gate it no longer applies |
| Settle time | 5 min of fresh reports without the print | When a start command counts as not taken, and the printer as free again |
| Wait for a free printer | 10 min | How long the daemon waits, before the gate, before the job ends unstarted |
| Records kept | final report 24 h; how the last delivery job ended, as the status route gives it, 10 min; a printer's record a day after last touched | What a slow caller can still read |
| Oldest sliced file sent | 40 min after its slice | A send of an older file is refused |
| Rate limits | Per pairing code on the caller's and the daemon's routes, per address on the download, 60 pairing exchanges a minute for the whole relay | One page or daemon flooding the relay |
| Request size | 64 kB | Any request body the relay reads |

The settle time and the wait for a free printer are guesses until the real H2S is timed.

Deeper: [The settings](README-details.md#the-settings).

## Where it stands

Built and tested: the relay and the daemon, their pairing, delivery jobs with progress
reports through the whole delivery and the print, cancellation up to the start gate, the
start gate and the hold, restarts of either half, and the log lines; tested by the fast
suite, by random fault sequences on both links, and against the simulated printer.

Not done:

- **Never run against the real printer.** Every printer sequence the simulated printer
  plays is invented from one recorded status document. A session at the H2S must record
  real prints and time the start: the timed rule after a start command rests on two
  limits that only the H2S can settle, the settle time (5 min) and the 2 minutes before
  an end naming the file can count as this print's end.
- **Never run on Windows.** Tests fake each platform-dependent choice.
- **No relay reachable from another machine.** The only one that can be started binds
  127.0.0.1 and treats every request as signed in; no real caller with a sign-in is built.
- **Daemon telemetry is not designed.** Both halves write log lines only.
- **One relay process.** Every record lives in that process's memory and is lost when it
  restarts.
- **Not handled, by design:** stopping a print that is already running (it is stopped at
  the printer), and checking the printer's certificate (the daemon accepts any).
- Some text keeps old words for users (`Team`, `team=`); changing them is a separate change.

Deeper: [Where it stands](README-details.md#where-it-stands) and
[Before trusting it at the H2S](README-details.md#before-trusting-it-at-the-h2s-what-the-session-at-the-h2s-must-confirm).

## To be built

Phases 2 to 4 need nothing of printer delivery. In phase 5 (the real printer) the relay
runs inside the front server, and a **group** (the users who share one configuration and
one printer) is paired with one daemon. Everything below is phase 5; the messages of the
pairing exchange and what daemon telemetry holds are left to phase 5's own design spec.

- **Pairing with a code a user types once.** The daemon makes a code and a **daemon id**
  (a random id it keeps), and offers both every 30 s; a user types the code, the relay
  writes a **paired-printer record** (one per group, in the state bucket, the store that
  outlasts a restart), and the daemon's next offer gets its token. The code is good for
  15 minutes and used once. This replaces the lasting code the caller presents.
- **Sending and unpairing.** A send goes to the daemon the user's group's record names.
  Unpairing removes the record; the daemon then says it is unpaired and waits.
- **A daemon that was off** reconnects with no pairing again; its token has no end date.
  Built, except that the daemon's settings file gains the daemon id and loses the
  lasting pairing code.
- **How often a daemon talks to the relay.** An idle daemon's sync is held up to 55 s and
  answered the moment a send arrives (about one request a minute). A daemon syncs each
  second while it takes a job, every 10 s during a print, and at once when the printer
  changes state. A daemon is offline after 2 minutes, as now, and a report stale after
  40 seconds, replacing 20 s.
- **Records of delivery jobs in a store the caller supplies**, kept a day after the job
  ends, holding whether the start was allowed: a front server restart loses no job.
- **The sliced file taken from that store**, with no copy of the relay's own; the oldest
  file sent rises from 40 minutes to two hours.
- **Two secret keys and a new token**, so the relay's secret key can be replaced without
  pairing again: a daemon that syncs within a week of the replacement is given a new
  token, and one switched off for that whole week must be paired again.
- **Rate limits counted per user and per daemon**, with figures still to be settled; the
  offer of a pairing code (which replaces the pairing exchange) stays 60 a minute for the
  whole relay and is also counted per address.
- **Closing held syncs and progress streams when asked to stop**, so pages and daemons reconnect.
- **Log lines in JSON** with the time, the group and the user key (the signed-in user's
  Onshape id); the line ending a delivery job gives how long the file took to reach the
  printer, how long the print ran, and how it ended. Daemon telemetry carries the
  daemon's errors.
- **What the wizard's mockup needs**: who sent a delivery job, a one-line description of
  the plate, when it ended and, for a failure, the layer it stopped at; and a way for a
  page that lost its state to find its user's live delivery job and last print. How the
  relay gives these is to be settled in phase 5's design spec.

Deeper: [To be built](README-details.md#to-be-built).

## What is not known

- How the real H2S behaves (the session at the H2S settles it): what it reports while
  paused or after a stop, how long it takes to show a print after the start command,
  whether it keeps the previous print's end under the new file's name, its TLS version
  and its error codes.
- Whether the daemon works on Windows, the likely daemon's computer at the printer.
- Whether Cloudflare's protection against automated clients ever challenges a daemon.

Deeper: [Two limits that wait for the real printer](README-details.md#two-limits-that-wait-for-the-real-printer)
and [To confirm](README-details.md#to-confirm).

## How to run and test it

All targets run from the repository root with `make -C delivery <target>`:

| Target | What it does |
|---|---|
| `install` | Installs both halves and the test tools (`uv sync`) |
| `test` | The fast suite: no socket, no real waiting, any order |
| `test-properties` | Random sequences of faults on both links, run before a commit and by reviewers |
| `test-sim` | The daemon against the simulated printer |
| `test-upstream` | Checks the pinned printer library's behaviour, then `test-sim` |
| `together` | Both halves and a stand-in printer (a fake inside the process, not the simulated printer) in one process |
| `hardware-smoke` | Starts a real print on a real printer; never part of a suite |

By hand, the whole chain runs on one computer: the simulated printer, a local relay,
`curl` as the caller, and the daemon (`python -m penguin_delivery_daemon pair`, then `run`).

Deeper: [Tests](README-details.md#tests) (the other targets), [Running the daemon](README-details.md#running-the-daemon),
[Try it on one machine](README-details.md#try-it-on-one-machine).
