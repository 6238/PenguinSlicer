# Printer delivery

Printer delivery takes a sliced file (the `.gcode.3mf` file the slice service makes) and
gets it printed on a Bambu Lab printer, reporting how the print goes. Everything here is
true of the code as built except the section [To be built](#to-be-built). The detailed
guide, for someone changing printer delivery, is [README-details.md](README-details.md).

## What it does

Printer delivery has three parts:

- **The relay** runs on the server. It pairs with a daemon, holds each printer's
  delivery jobs and last status, and answers the caller.
- **The daemon** runs on **the daemon's computer**: the computer next to the printer, on
  the printer's network. It connects outward to the relay, downloads the sliced file,
  uploads it to the printer and starts it. It opens no port, so nothing on the internet
  can call that computer. It is a plain Python program for Windows, macOS or Linux.
- **The simulated printer** plays a Bambu H2S to the daemon over real sockets, for tests.

The **caller** is the application that runs the relay and asks it to deliver sliced
files: it signs users in and holds the sliced file. In PenguinSlicer the caller will be
the front server, from phase 5 of [the plan](../docs/plans/penguin-slicer-plan.md). A
**delivery job** is one sliced file's way from the caller's send to the end of its print.
The **pairing code** is eight symbols the daemon's `pair` command shows; as built it is a
lasting secret the caller presents for its users, and it tells the relay which daemon a
request may use.

The daemon starts a print only after asking the relay's **start gate**, which says yes
once per delivery job and never to a cancelled one. After the **start command** (the
message that tells the printer to begin) the daemon holds the printer until the
printer's own reports show what became of it, so no file is started twice, across
restarts of either half.

Deeper: [Printer delivery](README-details.md#printer-delivery) and
[Layout](README-details.md#layout).

## How to run and test it

All targets run from the repository root with `make -C delivery <target>`:

| Target | What it does |
|---|---|
| `install` | Installs both halves and the test tools (`uv sync`) |
| `test` | The fast suite: no socket, no real waiting, any order |
| `test-parallel`, `test-repeat` | The fast suite on two workers; ten runs in new random orders |
| `test-properties` | Random sequences of faults on both links, run before a commit and by reviewers |
| `test-sim` | The daemon against the simulated printer |
| `test-upstream` | Checks the pinned printer library's behaviour, then `test-sim` |
| `test-together`, `together` | Both halves and a stand-in printer in one process |
| `coverage`, `slowest` | Branch coverage; the slowest tests |
| `upgrade-printer-library VERSION=x.y.z` | Moves the printer library's pin and runs the upstream check |
| `daemon-tarball` | Packs the daemon to copy to its computer |
| `hardware-smoke` | Starts a real print on a real printer; never part of a suite |

The whole chain can be run by hand on one computer with the simulated printer, a local
relay and `curl` as the caller. The daemon is run with
`python -m penguin_delivery_daemon pair`, then `run`.

Deeper: [Running the daemon](README-details.md#running-the-daemon),
[Try it on one machine](README-details.md#try-it-on-one-machine) and
[Tests](README-details.md#tests).

## Interfaces

The caller builds the relay with `create_app`, giving it a secret key that signs the
daemons' tokens, a function that says who is asking and which pairing code they may use,
and a function that finds the sliced file for a send. The relay's routes for the
caller's pages:

| Route | What it does |
|---|---|
| `GET /printer/status` | Paired or not, online or not, the printer's status, the job slot, the last result, the latest delivery job's progress report |
| `POST /printer/jobs` | A send: creates a delivery job, or refuses with an error report |
| `GET /printer/jobs/<id>` | The delivery job's latest progress report |
| `GET /printer/jobs/<id>/events` | The progress reports as a server-sent event stream |
| `POST /printer/jobs/<id>/cancel` | Cancels a delivery job that has not passed the start gate |
| `POST /printer/jobs/<id>/stop-following` | Gives up a stale delivery job past the start gate, whose outcome cannot be known |

The daemon's routes: the pairing exchange (a code for a token), the **sync** (the daemon
posts the printer's status and its delivery job's progress; the answer carries a job, a
cancel or nothing), the start gate, the acknowledgement of a job's end, a read-only ping,
and the download of the sliced file. Every failure a caller can meet is an
[error report](../contracts/error-report.md); progress reports follow
[the progress report contract](../contracts/progress-report.md).

Deeper: [The caller's routes](README-details.md#the-callers-routes),
[The interface the relay offers its caller](README-details.md#the-interface-the-relay-offers-its-caller)
and [Error reports](README-details.md#error-reports).

## The states of a delivery job

A delivery job is `queued` until a sync hands it to the daemon, then `running` through
its stages (waiting for the printer, downloading, uploading, starting, printing, waiting
for a person), and ends `done`, `failed` or `cancelled`. Only evidence ends a delivery
job: the printer's own report, the daemon's acknowledgement, or a start gate never
passed. A printer paused or waiting for someone is a stage, never an end. A report whose
daemon or printer has gone quiet is marked stale, not ended; past the start gate, the
caller may stop following it, and the relay does so by itself after 24 hours of
continuous staleness, saying the outcome is unknown.

Deeper: [Delivery jobs](README-details.md#delivery-jobs) and
[How a start is decided](README-details.md#how-a-start-is-decided).

## The figures that matter, as built

| Figure | Value | What it bounds |
|---|---|---|
| Sync interval | 5 s; at most once a second while a job's progress moves; at once on a change of the printer's state | How old the relay's picture of the printer is |
| Stale limit | 20 s without the daemon | When a running delivery job's report is marked stale |
| Online limit | 2 min | When a daemon counts as silent and a send is refused |
| Collection deadline | 3 min to be collected, 15 min to reach the start gate | A job the daemon never takes up; past the gate this deadline no longer applies |
| Settle time | 5 min of fresh reports without the print | When a start command counts as not taken, and the printer as free again |
| Wait for a free printer | 10 min | How long the daemon waits, before the gate, before the job ends unstarted |
| Records kept | final report 24 h; last result 10 min; a printer's record a day after last touched | What a slow caller can still read |
| Oldest sliced file sent | 40 min after its slice | A send of an older file is refused |
| Rate limits | 120 status reads and 10 sends a minute per pairing code; 120 syncs and 60 other daemon requests a minute per pairing code in the daemon's token; 60 pairing exchanges a minute for the whole relay; 30 downloads a minute per address | One page or daemon flooding the relay |
| Request size | 64 kB | Any request body the relay reads |

Every time limit on the printer's side is a guess until the real H2S is timed.

Deeper: [The settings](README-details.md#the-settings).

## Where it stands

Built and tested: the relay and the daemon, their pairing, delivery jobs with progress
reports through the whole delivery and the print, cancellation up to the start command,
the start gate and the hold after a start command, restarts of either half, and the
log lines. They are tested by the fast suite, by random fault sequences on both links,
and against the simulated printer over real sockets.

Not done:

- **Never run against the real printer.** Every printer sequence the simulated printer
  plays is invented from one recorded status document. A session at the H2S must record
  real prints and time the start; two time limits of the start rule wait on it.
- **Never run on Windows.** Tests fake each platform-dependent choice.
- **No relay reachable from another machine.** The only one that can be started binds
  127.0.0.1 and signs everyone in; a real caller with a sign-in is not built.
- **Daemon telemetry is not designed.** Both halves write log lines only.
- **One relay process.** Every record lives in that process's memory and is lost when it
  restarts.
- Some text still uses old words for users (`Team`, `team=`), to change on its own.

Deeper: [Where it stands](README-details.md#where-it-stands) and
[Before trusting it at the H2S](README-details.md#before-trusting-it-at-the-h2s-what-the-session-at-the-h2s-must-confirm).

## To be built

Phases 2 to 4 need nothing of printer delivery. In phase 5 (the real printer) the relay
runs inside the front server, and a **group** (the users who share one configuration and
one printer) is paired with one daemon. Everything below is phase 5:

- **Pairing with a code the daemon makes.** The daemon makes a code and a **daemon id**
  (a random id it keeps), and offers both every 30 s; a user types the code, the relay
  writes a **paired-printer record** (one per group, in the state bucket, the store that
  outlasts a restart), and the daemon's next offer gets its token. The code is good for
  15 minutes and used once. This replaces the lasting code the caller presents.
- **Sending and unpairing.** A send goes to the daemon the user's group's record names.
  Unpairing removes the record; the daemon then says it is unpaired and waits.
- **A daemon that was off** reconnects with no pairing again; its token has no end date.
  Most of this is built.
- **How often a daemon talks to the relay.** An idle daemon's sync is held up to 55 s
  and answered the moment a send arrives (about one request a minute); each second while
  it takes a job; every 10 s during a print; at once on a change. A daemon is offline
  after 2 minutes, as now, and a report stale after 40 seconds, replacing 20 s.
- **Records of delivery jobs in a store the caller supplies**, kept a day after the job
  ends, holding whether the start was allowed, so a restart of the front server loses
  no delivery job.
- **The sliced file taken from that store**, with no copy of the relay's own; the oldest
  file sent rises from 40 minutes to two hours.
- **Two secret keys and a new token**, so the relay's secret key can be replaced without
  pairing again, within a week.
- **Rate limits counted per user and per daemon**; the pairing-code offer stays 60 a
  minute for the whole relay and is also counted per address.
- **Closing held syncs and progress streams when asked to stop**, so pages and daemons
  reconnect to the replacement.
- **Log lines in JSON** with the time, the group and the user key; the line ending a
  delivery job gives how long the file took to reach the printer, how long the print
  ran, and how it ended. Daemon telemetry carries the daemon's errors.
- **What the wizard's mockup needs**: who sent a delivery job, a one-line description of
  the plate, when it ended and, for a failure, the layer it stopped at; and a way for a
  page that lost its state to find its user's live delivery job and last print.

Deeper: [To be built](README-details.md#to-be-built).

## What is not known

- How the real H2S behaves: what it reports while paused or after a stop, how long it
  takes to show a print after the start command, whether it keeps the previous print's
  end under the new file's name, its TLS version, and its error codes. The session at
  the H2S settles these.
- Whether the daemon works on Windows, the likely daemon's computer at the printer.
- Whether Cloudflare's protection against automated clients ever challenges a daemon.

Deeper: [Two limits that wait for the real printer](README-details.md#two-limits-that-wait-for-the-real-printer)
and [To confirm](README-details.md#to-confirm).
