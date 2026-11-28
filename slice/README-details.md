# Slice service

**This is the builder's document for the slice service.** The guide beside it,
[README.md](README.md), is what the owner reads and decides from. This file holds what a
builder needs that the guide leaves out: the code-level names (routes, settings, error
codes, constants and tests), every measurement in full, and what is to be built, in order.
Where the two differ, the guide is right and this file is to be corrected. The names and
shapes that pass between components are fixed by [the contracts](../contracts/README.md),
which win over this file for those. Everything in this file outside the section
[To be built](#to-be-built) is true of the code as built; a difference there between this
file and the guide is reported to the owner, not corrected in either file.

Takes a [plate configuration](../contracts/plate-configuration.md) (the parts as STL files,
where each instance of a part sits on the plate and how it is turned, the printer, filament
and process profiles with setting overrides), runs Orca Slicer headless, and returns a
[sliced file](../contracts/sliced-file.md) (`.gcode.3mf`) with its summary. Slicing one
plate configuration is one slice job. Every failure becomes an
[error report](../contracts/error-report.md); a running slice job sends
[progress reports](../contracts/progress-report.md). It knows nothing of Onshape, users,
web sessions or printers.

## Where it stands

The phases named here are those of [the plan](../docs/plans/penguin-slicer-plan.md).

**Built and tested** (on `main` after pull request 12): the HTTP interface, the checks on
every part before Orca runs, slicing with the pinned Orca 2.4.2, Orca's own stages and
percentage as progress, ending a slice job early and cleanup that leave no Orca and no
files, the memory watchdog at a 2,000 MB memory ceiling, Orca's reasons read from its
`result.json` and its debug log, one log line per slice job transition, and
`make upgrade-orca` with the upstream check. The fast suite covers every branch of the
package. The real-Orca suite slices 100 spacers in a 10 by 10 grid and the eight real
parts of the Popcorn Penguins' robot, alone and on mixed plates. The other reference
plates (a plate of several different functional parts, a full plate of small instances,
one, two and three large organic parts, and those with supports on) were measured with
`scripts/measure_plate.py` (see [Plate limits](#plate-limits)). Of phase 2, the shared set of
plates for the two placement checks is built (see
[Shared plates for the placement checks](#shared-plates-for-the-placement-checks)), and so
are items 1 to 4: the user key on every request, one part uploaded by itself into the part
store, its units beside it, and the plate configuration in its phase 2 form, parts named by
hash and an instance turned by a rotation (see
[The user key, the part store, units and the plate configuration](#the-user-key-the-part-store-units-and-the-plate-configuration));
the shared plates now go through `POST /slices` after their parts are uploaded. Items 5 and
6 are built too: the table of settings, generated from Orca 2.4.2's source with every
process setting classified and served by `GET /settings-table`, and every setting of it
accepted in `overrides` under Orca's own name (see
[The table of settings](#the-table-of-settings)). Items 7 to 9 are built as well: a plate's
later slice job replaces its earlier one and a repeated submission is answered with its
first attempt's slice job (see
[A plate's slice jobs: repeats, replacement and the places](#a-plates-slice-jobs-repeats-replacement-and-the-places)),
every waiting slice job's report says how many are ahead and every slice job ended early
says why, and a slice job goes on without its page (see
[Progress, cancellation and cleanup](#progress-cancellation-and-cleanup)). Items 10 to 13
are built: a slice job remembered for two hours and its sliced file deleted once the front
server has stored it, and the route that lists the slice jobs (both under
[Progress, cancellation and cleanup](#progress-cancellation-and-cleanup)); a sliced file of
at most 50 MB (see [Plate limits](#plate-limits)); and Orca's own sentence on the two
failures about a gap (see [Orca Slicer](#orca-slicer)). Items 14 to 18 finish phase 2: a
stop that finishes the running slice (see [Asked to stop](#asked-to-stop)), "a new plate" in
the sentences (see [Error codes](#error-codes)), the log the front server collects (under
[Progress, cancellation and cleanup](#progress-cancellation-and-cleanup)), the shared plates
through the HTTP interface (item 17), and the slice service's half of each row of the restart
table (see
[The slice service's half of each row of the restart table](#the-slice-services-half-of-each-row-of-the-restart-table)).
Everything phase 2 asks of the slice service is built; a part laid on a face of its convex
hull that bridges a hollow, so that it touches the plate only along edges, is refused by the
pinned Orca unless supports and a raft are on, and the slice service says so
(`slice.rests_on_an_edge`).

**Not built or not known:**

- Orca 2.5.x cannot be taken yet (see
  [Taking a new upstream version](#taking-a-new-upstream-version)).
- A part whose first layer is empty gets only the general sentence, since the pinned Orca
  writes its reason to no file; only a patch to Orca could surface it, and there is none.
- Parts that intersect themselves are not detected before slicing; the expected time is
  only within about a factor of two; the peak in the log can be under Orca's true peak for
  an Orca that fails between two of the watchdog's samples.
- Not measured: the disk held by the part store and by finished slice jobs, which keep
  their sliced file until the front server has stored it, or for two hours when nothing
  collects it; CPU time; how many slices a host can run at once. Every measurement is
  from aarch64 Linux machines: almost all from one with 4 CPUs, and nine plates of the
  memory model's fit from another.

**What the phases still need from it** is in [To be built](#to-be-built), by phase.
Some sentences of its error reports and some code comments
still name the user with the old words; changing them is a change of its own, with its
tests.

## To be built

This section holds what [the guide](README.md) requires of the slice service that the code
as built does not yet do, by the phase of [the plan](../docs/plans/penguin-slicer-plan.md)
that builds it: phase 2 runs everything on one machine, phase 3 hosts it on Railway.
Phases 4 (inside Onshape) and 5 (the real printer) change nothing here: parts from Onshape
arrive as any part does, and printing does not pass through the slice service. Each item
links the guide's section and the contract's request or shape it implements, and says what
it builds, its names and figures, what it replaces in the code as built, the error reports
it produces and the tests it needs. When an item is built, its text moves into the body of
this file and out of this section, and [README.md](README.md) is updated to match. The ids
in brackets name decisions in
[the map of the hosted architecture's decisions](../docs/orchestration/hosted-architecture/decision-map.md).

**Names.** A name a contract fixes is written here as the contract writes it, with no
mark: the fields of [the plate configuration](../contracts/plate-configuration.md#to-be-built),
[the table of settings](../contracts/settings-table.md#fields),
[the error report](../contracts/error-report.md#fields) and
[the progress report](../contracts/progress-report.md#fields); the constant
`MAX_PLATE_CONFIGURATION_BYTES`; the shape of an uploaded part's record; and the codes
`slice.part_missing` with `missing_parts`, `slice.bad_units` and `slice.stopping`, which
[the contract between the wizard and the front server](../contracts/wizard-front-server.md)
names; and everything of the slice service's own HTTP interface in phase 2, which
[its contract](../contracts/slice-http-interface.md) fixes for this builder and the front
server's alike: every route, the header `X-Penguin-User-Key`, every answer's shape and status,
the list of slice jobs, the log's route, and the codes `slice.no_user_key`,
`slice.bad_request`, `slice.bad_units`, `slice.stopping`, `slice.output_too_large`,
`slice.file_gone`, `slice.not_ready` and `slice.unknown_job`. Only the slice service's own
settings, constants, file names and test names are marked *proposed*; the builder settles
those while building.

**Tests.** Every failure a caller can see is an error report with a test in the fast suite
that produces it on purpose, through the code that really raises it, and states its
sentence, remedy, action, retryable flag and evidence (`tests/test_errors.py`). No test
sleeps or waits a number of seconds: time passes through a fake clock the test moves, the
time limit's timer is `slicer.TIMER` replaced, Orca is `tests/fake_orca.py`, and where
events race or cross a connection (a stream and a stop, a replacement and a running Orca,
a restart and a fetch) fakes put them in an exact order and the test waits on an event,
never on a duration, behind `helpers.FAILSAFE_S`.

**Open items.** Each item the guide still lists as undecided or unmeasured is named below
where it bears on the work, in one line with a link to it in the guide. Nothing is built
past such an item; where the work cannot wait, the line says which reading to build.

### Terms used below

- The **front server** is everything behind the address the browser talks to (in
  `front/`, see [its guide](../front/README.md)). It is the only caller of the slice
  service: it passes parts and plate configurations through with the user key, follows
  every unfinished slice job, fetches and stores each sliced file and collects the slice
  service's log lines. The **wizard** is the code in the browser; "the page" is the wizard
  open in one browser tab. In phase 2 the front server is a process on the one machine;
  hosted, it has a container of its own.
- The **slice container** is the container on Railway that runs one slice service process
  and nothing else.
- The **user key** is the signed-in user's Onshape id, which the front server passes with
  every request about a part or a slice job to say whose it is. The slice service compares
  user keys and never interprets them.
- The **part store** is the slice service's folder of uploaded parts, each kept under its
  user key, the SHA-256 hash of its bytes and its units label, for two hours after it was
  last used. It is a cache: the browser's storage is the record of a user's parts.
- The **plate's id** (`plate_id`) and the **submission's value** (`submission_id`) are the
  two values the page makes and every plate configuration carries
  ([The plate and the submission](../contracts/plate-configuration.md#the-plate-and-the-submission)).
- A slice job **ended early** is one whose final progress report has the state
  `cancelled` and a `cancel_reason`; the code calls ending it early cancelling it.
- A **follower** of a slice job is a connection that follows its progress stream.
- A **progress stream** is the connection of server-sent events on which a slice job is
  followed: as built, `GET /slices/<job>/events`.
- The **table of settings** describes every setting a plate configuration may replace,
  with the profile catalog's names ([its contract](../contracts/settings-table.md)).
- The **state bucket** is the store where the front server keeps what must outlast a
  restart, the sliced files among it; the **log bucket** holds the log as files. The slice
  service holds no credential for either.

### What the other documents decide

These are decided and explained elsewhere; the slice service is built to fit them.

- **Who reaches the slice service.** The browser talks only to the front server, which
  calls the slice service over Railway's private network, so the HTTP interface is not
  reachable from the internet and the browser never makes a cross-origin request.
  See [the architecture, The shape](../docs/architecture.md#the-shape). [D33]
- **Why a container of its own.** Orca reads files strangers upload, so the slice
  container holds no credentials: a flaw in Orca reaches no sign-in secret and no bucket.
  The split makes the front server pass parts and plate configurations through, fetch each
  sliced file and fetch the slice service's log lines from a route of the slice service.
  See [the architecture, The shape](../docs/architecture.md#the-shape). [D34, D36]
- **The slice container's size.** It is allowed 8 GB, the most one container gets on
  Railway's Hobby plan. See [the architecture, The shape](../docs/architecture.md#the-shape). [D39]
- **Only the front server calls it, with the user key.** The front server sets the user
  key from the sign-in cookie (the browser cannot name one) and passes it with each part
  and each plate configuration, so a user reaches only their own parts, slice jobs and
  sliced files. See [the guide, Security](README.md#security). [D26, D71, D249, D252]
- **Parts named by hash, with their units.** A plate configuration names each part by the
  SHA-256 hash of its bytes and its units label and carries no files; an error report lists
  the parts missing from the part store.
  See [the plate configuration contract](../contracts/plate-configuration.md#to-be-built). [D25, D73, D293]
- **The front server follows and collects.** It follows every unfinished slice job's
  progress stream itself, whether or not a page is open; when it starts it asks the slice
  service for its slice jobs, follows the unfinished ones and collects each finished one it
  has not yet stored. See
  [the front server's guide](../front/README.md#the-front-server-follows-every-slice-job-itself). [D62, D88]
- **Everyone shares the places.** Nothing limits the slice jobs or the parts of one user
  key. A user with a plate in each of several tabs may have a slice of each running or
  waiting, and one user can hold every place, which is accepted. The part store's limit on
  disk bounds all users' parts together. The front server limits how fast one user may
  upload parts and submit plate configurations (`front.too_many_requests`). See
  [the guide, Security](README.md#security).
- **The plan's standing requirements change.** The requirement Cleanup is amended for
  slice jobs: a slice job goes on when its page goes away, bounded by the time limit. How
  many slices run at once and how many may wait become settings in phase 3, starting at
  one and two. See [the plan](../docs/plans/penguin-slicer-plan.md#standing-requirements). [D282, D290]
- **What every component logs.** Every error a user is shown, with its code, the user key
  and the job; every exception with its stack trace; every refusal; and once a minute a
  line with the memory held and the slices running and waiting. The front server fetches
  the slice service's lines and writes them, with every other component's, into one file
  each minute, adding the group; every line carries the component that wrote it. See
  [the architecture, Reading what happened](../docs/architecture.md#reading-what-happened)
  and [the front server's guide](../front/README.md#the-log). [D182, D183, D184, D191, D196]
- **Measured before users rely on it.** Every measurement so far is from aarch64 Linux
  and from plates under 2,600 MB. Plates of rising weight up to the hosted ceiling's
  starting figure of 6,000 MB are sliced on the slice container before users rely on it,
  and set the memory ceiling, the time limit and the estimates. See
  [the architecture, To confirm before building on it](../docs/architecture.md#to-confirm-before-building-on-it). [D350]

### Phase 2: one machine

The front server and one slice service process run on the one machine
([Running phase 2 on one machine](../front/README-details.md#running-phase-2-on-one-machine)).
The items are in the order to build them; each rests on those before it, except item 17,
the shared plates, which was written first of all, before item 1, since the wizard's builder
runs it from the start and it needs only the placement check as built; it is built. Items 1
to 4, which replace the way parts arrive, are built too, and so are 5 and 6, which replace
the settings; 7 to 13 replace the life of a slice job, and are built; 14 to 18 finish the
phase, and are built.

**1 to 4. The user key, the part store, units and the plate configuration.** Built: see
[The user key, the part store, units and the plate configuration](#the-user-key-the-part-store-units-and-the-plate-configuration).
What they leave to later items: the three
routes that answer for the whole slice service and are not scoped to a user key (the table
of settings, item 5, built; the list of slice jobs, item 11, built; the log, item 16, built)
ignore the header. A plate's id and a submission's value are compared among the slice jobs of one user
key (item 7) and the first progress report carries `ahead` (item 8), both built.

**5 and 6. The table of settings, and every setting that is a parameter.** Built: see
[The table of settings](#the-table-of-settings). What they leave to later items: nothing.

**7. A plate's later slice replaces its earlier one, and a repeat is recognised**
([Run one slice at a time, and let a few wait](README.md#run-one-slice-at-a-time-and-let-a-few-wait),
[A plate configuration submitted twice](README.md#a-plate-configuration-submitted-twice);
[The plate and the submission](../contracts/plate-configuration.md#the-plate-and-the-submission)).
Built: see
[A plate's slice jobs: repeats, replacement and the places](#a-plates-slice-jobs-repeats-replacement-and-the-places).
What it leaves to later items: a repeat is recognised for as long as the slice job's record
lasts, two hours after it ends (item 10, built); a stopping slice service answers
`slice.stopping` (item 14, built), the repeat being looked for first. [D97, D98, D295]

**8. Progress reports say how many are ahead, and why a slice job ended early**
([Report progress](README.md#report-progress), [End a slice job early](README.md#end-a-slice-job-early);
[A slice job's reports](../contracts/progress-report.md#a-slice-jobs-reports)). Built: see
"How many are ahead" and "Ending a slice job early" under
[Progress, cancellation and cleanup](#progress-cancellation-and-cleanup) (tests:
`tests/test_jobs.py` `TestAhead`, `TestCancelReason`). What it leaves to later items:
nothing; the `shutdown` reason is given to the waiting slice jobs at a stop and to the running
one at a second stop (item 14, built).

**9. A slice job goes on without its page** ([Go on without the page](README.md#go-on-without-the-page)).
Built: see "Going on without its page" under
[Progress, cancellation and cleanup](#progress-cancellation-and-cleanup) (tests:
`tests/test_jobs.py` `TestGoesOnWithoutItsPage`, `tests/test_web.py`
`TestGoesOnWithoutItsPage`). What it leaves to later items: nothing. [D95, D96, D297]

**10. Slice jobs remembered for two hours; the sliced file deleted once stored.** Built:
see "Remembered for two hours; the sliced file deleted once stored" under
[Progress, cancellation and cleanup](#progress-cancellation-and-cleanup). What it leaves to
later items: nothing; the stop of item 14 (built) waits until no done slice job holds a
sliced file the front server has not collected, the running one's and those done before
the stop alike, or until each such file's record expires. [D90, D100, D298, D299]

**11. A route lists the slice jobs.** Built: see "The list of slice jobs" under
[Progress, cancellation and cleanup](#progress-cancellation-and-cleanup). What it leaves to
later items: nothing. [D296]

**12. A sliced file is at most 50 MB.** Built: see "A sliced file is at most 50 MB" under
[Plate limits](#plate-limits). What it leaves to later items: nothing.

**13. Orca's own sentence on the two failures about a gap.** Built: see "Orca's own
sentence in an error report" under [Orca Slicer](#orca-slicer). What it leaves to later
items: nothing.

**14. Asked to stop, it finishes the running slice**
([What a user sees while the slice service stops](README.md#what-a-user-sees-while-the-slice-service-stops);
the stopping answer of [Submitting a plate configuration](../contracts/wizard-front-server.md#submitting-a-plate-configuration)).
Built: see [Asked to stop](#asked-to-stop). What it leaves to later items: nothing. [D230, D306]

**15. "A new plate" in the sentences.** Built: see "A new plate" under
[Error codes](#error-codes). What it leaves to later items: nothing.

**16. The log collected by the front server.** Built: see "The log the front server
collects" under [Progress, cancellation and cleanup](#progress-cancellation-and-cleanup).
What it leaves to later items: nothing.

**17. One shared set of plates for the two placement checks.** Built: see
[Shared plates for the placement checks](#shared-plates-for-the-placement-checks), each
plate now through `POST /slices` after its parts are uploaded, exactly as it is, its
`enable_support` under Orca's own name.

**18. The slice service's half of each row of the restart table.** Built: see
[The slice service's half of each row of the restart table](#the-slice-services-half-of-each-row-of-the-restart-table).
What it leaves to later items: nothing.

### Phase 3: hosted on Railway

The slice service runs alone in the slice container, and the front server in a container
of its own. The guide lists what this phase adds under
[What is built and what is not](README.md#what-is-built-and-what-is-not).

**1. The limits become settings**
([Run one slice at a time, and let a few wait](README.md#run-one-slice-at-a-time-and-let-a-few-wait),
[The limits](README.md#the-limits)). The slice service stops an Orca that passes the memory
ceiling or the time limit and reports each as an error the wizard explains: passing the
memory ceiling is `slice.out_of_memory`, passing the time limit is `slice.timeout`, both as
built. Both limits, and how many Orcas run at once and how many slice jobs may wait behind
them, are settings of the slice service, each refused at start with a message that names it
and exit status 2 (*proposed*), as `PENGUIN_SLICE_MAX_PEAK_MB` is as built. The settings'
names are *proposed*:

| Setting | Default | Replaces |
|---|---|---|
| `PENGUIN_SLICE_TIME_LIMIT_S` | 240 | `limits.PLATE_SLICE_TIMEOUT_S` (240 s) |
| `PENGUIN_SLICE_MAX_RUNNING` | 1 | `jobs.MAX_RUNNING` (1) |
| `PENGUIN_SLICE_MAX_WAITING` | 2 | `jobs.MAX_QUEUED` (2) |

The hosted service starts with one running and two waiting, changed from what is seen in
use. These stay settings because how many processors Railway gives the slice container,
how long real plates take there and how often two users slice at the same moment are not
yet known ([Unmeasured](README.md#unmeasured)). Tests: each setting's refusal of a bad value; a time limit set by the test
fires `slice.timeout` through the replaced `slicer.TIMER`; with two running, two fake
Orcas run at once. [D43, D51, D52, D56, D301, D304]

**2. The memory ceiling at the hosted figure**
([Bounding Orca's memory](README.md#bounding-orcas-memory), [The limits](README.md#the-limits)).
The slice container sets `PENGUIN_SLICE_MAX_PEAK_MB` to 6,000 MB, the figure to start from
on the hosted service, chosen without a measurement there and the owner's to change; the
default in the code stays 2,000 MB. 6,000 MB leaves 2 GB of the slice container's 8 GB for
the slice service process, its checks on uploaded parts and the operating system. The
margin matters because Railway stops a container that passes its 8 GB, which would take
the waiting slice jobs with it, where the ceiling ends only the one slice. A high ceiling
costs money only while a heavy plate is slicing, since Railway bills the memory a
container holds at each moment. By the figures of "Sizing the host" under
[Plate limits](#plate-limits), Orca can pass the ceiling by the rise between two of the
watchdog's readings (502 MB, the largest measured) and a host is sized for 400 MB of the
slice service beside Orca, so 6,000 MB plus both is 6,902 MB, under the 8 GB (a
calculation, not a measurement). The 400 MB was measured without the part store and
without the checks of parts on arrival; open: what the slice service needs beside Orca
([Unmeasured](README.md#unmeasured)), and if the true figure is much larger, the ceiling
comes down. The slice container never runs more Orcas than fit in its memory
with each at the memory ceiling: with 6,000 MB that is one, and two at once would need a
ceiling of about 3,000 MB each, and so smaller plates. Orca uses several processors by
itself, so a second Orca would share them, not use idle ones. Replaces: the 2,000 MB the
service runs at as built, and the rule in the docstring of `jobs.py` (min of the CPUs and
memory over one slice's peak; *proposed*). Error report: `slice.out_of_memory`, as built. Tests: none
new in the fast suite (the setting's tests exist); the measurements below. [D44, D45, D53,
D303]

**3. Measurements on the slice container set the two limits**
([Unmeasured](README.md#unmeasured), its items on Orca on the hosted machines, how often
two users slice at once and Orca's processor time). The heaviest plate ever
measured peaked at 2,569 MB (six Stanford bunnies with supports on). The plates the Popcorn
Penguins print took at most 22.5 s of Orca's time (four-each-b with supports on), and the
slowest plate of their parts measured, twelve Elevator Block Bottom Inners with supports on
at a 3,000 MB ceiling, 34.3 s, about a seventh of the time limit of 240 s. All of it was
measured on aarch64 machines, where Railway's
are believed to be x86_64, and on plates far lighter than 6,000 MB; a plate that heavy will
take longer. The time limit must be long enough that every plate which would finish does
finish, and no longer, because a slice that hangs holds up everyone waiting behind it. So
both are settled by one set of measurements on the slice container: plates of rising
weight up to the memory ceiling, each timed, with Orca's processor time beside its elapsed
time. The time limit and the time a new slice service takes to start must together stay
under the wizard's 300 seconds of submitting again
([How long a new slice service takes to start](README.md#unmeasured)). The time limit is then set at a few times the
slowest plate that finishes; until then it starts at 240 seconds. For plates heavier than
any measured, the slice service's estimates of memory and time are extended beyond what
was measured: the memory and time models (`limits.estimate_peak_mb`,
`limits.estimate_seconds`) are linear in the instances and the volume, and are refitted on
these runs (`scripts/measure_plate.py --fit`; *proposed*). Replaces: `limits.MEASURE_STOP_MB`
(3,072 MB), the ceiling `scripts/measure_plate.py` slices under, which stops a measurement
below the hosted ceiling and must rise above it (*proposed*); the time limit a measurement runs under
(`slicer.slice_plate`'s default, `PLATE_SLICE_TIMEOUT_S`, 240 s; `limits.MEASURE_MAX_SECONDS`,
180, is defined and used nowhere); and the models' constants (`MEMORY_*`, `TIME_*`).
Tests: the fast suite's tests of the models follow their new constants. [D46, D47, D48,
D49, D50]

**4. A comment line on a quiet progress stream**
([Report progress](README.md#report-progress)). Railway closes a request after fifteen
minutes, or after five without data, and Cloudflare after 125 seconds without data. So the
progress stream sends a comment line (`: keep-alive`, *proposed*) at least every fifteen seconds while
it has nothing to report, as the relay's does. Replaces (*proposed*): `JobPool.follow` repeating the
latest progress report, with its same `sequence`, every `jobs.WAIT_S` (15 s) when nothing
changes. Error report: none. Tests: with the wait injected, a quiet stream sends a comment
line and no repeated report; a new report follows the comment line. [D60, D300]

**5. Orca as a Unix user of its own** ([Security](README.md#security)). Orca runs as a
Unix user of its own that can write
only the scratch folder of its slice job, so a flaw in Orca cannot alter the slice service
or reach another slice job's files. The slice container's image makes the user, and the
slice service starts Orca as it (*proposed*). Replaces: Orca run as the slice service's own user (with
its allowlisted environment and its `HOME` in the scratch folder, which stay). Error report:
an Orca that cannot be started as that user is `slice.orca_unstartable` (*proposed*). Tests: in the fast
suite, the command the slice service builds names the user; in the slice container's
image, a fake Orca that tries to write outside its scratch folder is refused. [D253, D305]

**6. A new Orca version is a new image**
([Taking a new Orca version](README.md#taking-a-new-orca-version)). A new Orca version is
rolled out as a new image of
the slice container, built with the version pinned in `scripts/install-orca.sh` after
`make upgrade-orca` (*proposed*) and the upstream check pass, and deployed like any other change. The
image installs the distribution's packages listed under [Orca Slicer](#orca-slicer)
(*proposed*), since the install script stops instead when it runs as root. Replaces:
nothing; as built Orca is installed into `tools/orca` on the machine that runs the
service. Tests: the image's build runs `make test-upstream` (*proposed*). [D42]

**7. Reached only over the private network** ([Security](README.md#security)). Hosted, the
slice service listens on Railway's
private network and has no address on the internet; on one machine it listens on the
loopback address, as `serve --host 127.0.0.1` does by default as built. The slice
container's start command passes the private network's address (*proposed*: `--host ::`,
since Railway's private network is reached over IPv6). Nothing in a request proves that it
comes from the front server: the private network, or the loopback address, is the only
guard, which is accepted. Replaces: nothing. Tests: none in the fast suite; the slice
container's image is checked to answer on the private network and not on a public address
(*proposed*).

**8. Two versions side by side at a deploy**
([What a user sees while the slice service stops](README.md#what-a-user-sees-while-the-slice-service-stops),
[the plate configuration contract](../contracts/plate-configuration.md#old-and-new-versions-together)).
A deploy replaces one container and not the
other, so a new front server meets the previous slice service and the reverse. A change to
[the plate configuration contract](../contracts/plate-configuration.md) or to the HTTP
interface is made so that the previous front server still works against the new slice
service, and the previous slice service against the new front server: a field added to
the plate configuration after phase 2 is optional, with a meaning when it is left out, and
no field is removed or given a new meaning while a previous front server may still send
it. Replaces: nothing. Tests (*proposed*): the fast suite keeps
the previous release's example requests and answers and checks that the new slice service
still answers those requests as the previous front server expects.

**9. The log's new lines** ([The log](README.md#the-log)). The route by which the front
server collects the lines is built in phase 2 (item 16 there); from phase 3 the front
server writes the files into the log bucket. The time and the user key on every line are
built in phase 2 too (item 16 there). [D307] Phase 3 adds:

- The line that ends a slice job, which already carries Orca's peak memory
  (`peak_rss_kb`), the estimates (`estimated_peak_mb`, `expected_s`), the memory ceiling
  (`memory_ceiling_mb`), its times (`orca_wall_s`, `wall_s`) and each part's measurements,
  gains the bytes of each part, the bytes of the sliced file and how long the slice job
  waited before it ran. It also carries the number of parts and the number of instances
  as figures of their own. [D188, D308]
- A slice that passes 80 percent of the memory ceiling or of the time limit also writes a
  line marked as a warning, so that near misses can be found without reading every slice:
  with 6,000 MB and 240 s, a peak over 4,800 MB or Orca running over 192 s (the derived
  figures *proposed*). [D190]
- Once a minute a line gives the memory the slice service process and its Orcas hold
  together (*proposed*), and the slices running and waiting (`JobPool.counts`). [D309]
- A line for every exception and every refusal, whichever route it comes from. As built
  only the refusals of `POST /slices` (`"state": "refused"`) and the exceptions of the
  routes (`slice_http_error`), the sweeper and the cleanup are logged; the refusal of
  another user key's slice job (phase 2) is logged too; every refusal of `POST /parts`
  joins them. [D309]

Replaces: lines with no time and no user key. Error report: none; a log that fails never
changes an answer, as built (`jobs.SafeLog`). Tests: each kind of line produced on purpose
(a fake Orca reporting a peak over 80 percent of a ceiling the test sets, a fake clock past
80 percent of the time limit, the once-a-minute line on a fake clock, a refusal at every
route); every line carries the time and the user key where the request had one.

## Use

The HTTP interface is the slice service's one way in. Nobody slices by hand: to try
something, start the service and write a throwaway script against its routes.

```
make -C slice install        # the Python environment, and Orca Slicer into slice/tools/orca
make -C slice test           # the fast suite
```

Start the service, then upload the example's two parts and submit a plate configuration
that names them with `curl`, follow its progress reports, and fetch the sliced file and its
summary. Every request but the three for the whole slice service carries the user key; any
string will do by hand:

```
uv run --project slice python -m penguin_slice serve --work /var/tmp/penguin-slice --port 8640

K='X-Penguin-User-Key: me'
curl -s -H "$K" --data-binary @contracts/examples/parts/bracket.stl \
     -H 'Content-Type: application/octet-stream' 'http://127.0.0.1:8640/parts?units=mm'    # 201: the record
curl -s -H "$K" --data-binary @contracts/examples/parts/spacer.stl \
     -H 'Content-Type: application/octet-stream' 'http://127.0.0.1:8640/parts?units=mm'
curl -s -H "$K" -H 'Content-Type: application/json' --data-binary @plate.json \
     http://127.0.0.1:8640/slices                                 # 202: {"job": "j...", "progress": ...}
curl -sN -H "$K" http://127.0.0.1:8640/slices/<job>/events         # progress reports until the final one
curl -s  -H "$K" http://127.0.0.1:8640/slices/<job>/summary        # the sliced file's summary, as JSON
curl -s -OJ -H "$K" http://127.0.0.1:8640/slices/<job>/file        # the sliced file itself
```

`plate.json` is [the phase 2 example](../contracts/examples/plate-configuration-phase-2.json)
without its fourth instance. That instance lays the
bracket by a `rotation` on a face of its convex hull that is no face of the part, so the
bracket touches the plate along two edges only: the checks accept it, and the pinned Orca
fails the slice for its empty first layer (`slice.rests_on_an_edge`, see
[Error codes](#error-codes)) unless supports and a raft are on. With the first three
instances the plate slices.

`serve` writes one JSON log line per slice job transition, and one for each of its own
(`slice_service_started` with the host, the port it listens on, which with `--port 0` the
system chooses, and its process id; `slice_service_stopping`; `slice_service_stopped`), on
stderr. Ctrl-C and SIGTERM (what a container host sends) ask it to stop, as
[Asked to stop](#asked-to-stop) says: the first lets the running slice job finish and waits
for its sliced file to be collected, the second ends it too. By hand, with no front server
to collect a sliced file, a slice service that has sliced anything waits for the second
Ctrl-C. A setting it refuses (see Settings) stops it before it listens, with a message
naming the setting and exit status 2; an address it cannot listen on (one already taken),
with "cannot listen on <host>:<port>: ..." and exit status 1.

**One slice service process holds its slice jobs.** A running slice service is a slice
service process: one process, whose slice jobs live in its memory (`jobs.JobPool`).
Several slice service processes may run, on one machine or several; a client must keep
talking to the slice service process that accepted its slice job, because no other
process knows it. A server that starts several worker processes behind one address
(several Gunicorn workers, for example) loses slice jobs: a request that reaches another
worker gets `slice.unknown_job`. `serve` runs werkzeug's threaded server
(`werkzeug.serving.make_server`, Flask's own) in one process, on a thread of its own, so
that the main thread is free to take the stop signals.

### Asked to stop

Item 14 of [Phase 2](#phase-2-one-machine), built
([What a user sees while the slice service stops](README.md#what-a-user-sees-while-the-slice-service-stops);
the stopping answer of [Submitting a plate configuration](../contracts/wizard-front-server.md#submitting-a-plate-configuration)).
[D230, D306] When `serve` receives SIGTERM or Ctrl-C (its handler only puts a stop into a
`queue.SimpleQueue`, the one queue safe to put into from a signal handler, and
`__main__.run_until_stopped` acts on it in the main thread):

1. **The first stop** (`JobPool.stop`) ends each waiting slice job early with `cancel_reason`
   `shutdown`, so that its page submits the plate again by itself, and lets the running slice
   job run to its end, bounded by the time limit. The HTTP interface keeps answering every
   request. `serve` exits 0 once the pool is drained (`JobPool.drained`,
   `JobPool.wait_drained`): nothing waits or runs and no done slice job still holds a sliced
   file the front server has not deleted with `DELETE /slices/<job>/file`. A running slice
   that fails ends as any failure and holds nothing. A done slice job from before the stop
   holds the stop as the running one does, until its file is collected or its record expires
   (two hours). On one machine with no front server running nothing collects a sliced file,
   and `serve` waits for it until a second stop.
2. **While stopping,** each new plate configuration is answered `503` `slice.stopping`
   (retryable, exactly [the contract's example](../contracts/examples/slice-http/stopping.json)),
   never `slice.busy`, which a user is shown. `POST /slices` looks for a repeat first, so a
   repeat of a remembered submission is still answered `202` with its slice job; the stop is
   then answered before any check (a plate that the checks would refuse is answered
   `slice.stopping` too, since the page will submit it again to the new slice service, which
   checks it). A stop that arrives while a plate configuration is being checked is caught
   under the pool's lock (`jobs.Stopping`), and its folder is removed; one whose slice job
   meets the executor already shut down by a second stop (the executor is called outside the
   lock) is ended early with `shutdown` and answered `slice.stopping` too, never a 500. An upload of a part,
   and every request about a slice job, the list, the table of settings and the log, are
   answered as usual.
3. **A second stop** shuts the pool down (`JobPool.shutdown`): the running slice job is ended
   early with `cancel_reason` `shutdown`, reported only once Orca and every child are gone,
   and `serve` exits 0 at once after, without waiting for any done slice job's sliced file to
   be collected; such a file is lost with the process (`files_lost` in the last log line), and
   its slice runs again when its page submits again. A third stop changes nothing.

The log lines: `slice_service_stopping` with `stop` 1, the ids of the waiting slice jobs it
ended (`waiting_ended`) and whether the pool was drained at once; `slice_service_stopping`
with `stop` 2 at a second stop; and `slice_service_stopped` with `how` (`drained` or
`second_stop`) and `files_lost`. Past the time Railway gives a stopping container, Railway
kills the process and Orca dies with it (`PR_SET_PDEATHSIG`). Open: how long Railway gives a
stopping container, whether it starts the new one first, and how long a new slice service
takes to start ([Unmeasured](README.md#unmeasured)). Tests: `tests/test_jobs.py`
`TestAskedToStop` (the pool, with a worker the test releases), `tests/test_web.py`
`TestWhileStopping` (the HTTP interface), `tests/test_cli.py` `TestRunUntilStopped` (the
order of the stops and the drain, with a fake pool) and `tests/test_serve_stop.py`, which runs
`serve` itself on a loopback port the system chooses with the fake Orca in its mode `gate`
(it waits until the test writes into its FIFO, `helpers.open_gate`) and sends the stops to
its own process: a stop while Orca runs ends that slice job `done`, `serve` keeps answering
and exits only after its sliced file is deleted; a waiting slice job ends `cancelled` with
`shutdown`; a submission after the stop gets `slice.stopping`; a repeat gets its slice job; a
second stop ends the running slice job with `shutdown` once Orca is gone; a second stop while
a done slice job's sliced file is uncollected makes `serve` exit at once.

### The slice service's half of each row of the restart table

Item 18 of [Phase 2](#phase-2-one-machine), built
([What a restart does](README.md#what-a-restart-does),
[the architecture](../docs/architecture.md#keeping-it-true)). `tests/test_restarts.py` holds a
test for each row of the table "The slice container restarts" of
[the architecture](../docs/architecture.md#what-a-restart-does), of what the slice service
itself does in it, through its HTTP interface, with the fake Orca (mode `gate` for a slice
that must still be running at the restart) and a clock of the test's. A restart there is the
old slice service process ended (its pool shut down, which ends its slice jobs and its Orca)
and a new one started on the same work folder, with its own pool, part store and log:

| Row | What the slice service does, as the test asserts it |
|---|---|
| A slice was waiting or running | The new process answers the earlier slice job `404` `slice.unknown_job` at `GET /slices/<job>` and its progress stream, lists no slice job, holds no part, and answers the page's new submission of the same plate `422` `slice.part_missing` listing every part (`refresh_parts`); once the parts are uploaded again it accepts the plate and its progress starts again, to `done`. A slice still waiting when the old process is asked to stop ends `cancelled` with `cancel_reason` `shutdown`, with no error report, while the running one goes on to `done` |
| A user submits a plate while the slice service is stopping | `503` `slice.stopping`, retryable, at every attempt; nothing is started or remembered, so the new process takes the same `submission_id`, lists the missing parts and accepts the plate once they are back |
| A slice had finished | Once the front server has fetched the sliced file and deleted the slice service's copy, a stop finds nothing to wait for, and the new process knows nothing of the slice job; its log answers a new `process`, so the front server starts again from 0 |
| A print was being sent or was printing | Nothing of the slice service's: printer delivery does not pass through it |

What the front server and the page do in each row is asserted in their own suites against
their stand-ins, and the whole row, all three together, in the joined suite.

## The HTTP interface

`penguin_slice.web.create_app(work_dir)` is a Flask app factory, built to
[the contract](../contracts/slice-http-interface.md), every route of which it answers:

| Request | Answer |
|---|---|
| `POST /parts?units=mm` or `?units=in`, one binary STL as the body | 201 with the part's record (see [The part store](#the-part-store)) |
| `POST /slices`, a phase 2 plate configuration as a JSON body | 202 with `job`, `plate_id`, `submission_id`, the first progress report (`progress`, `queued` with `ahead`) and the `part_warnings`, each naming its part; for a repeat, the same with the latest report (see [A plate's slice jobs: repeats, replacement and the places](#a-plates-slice-jobs-repeats-replacement-and-the-places)) |
| `GET /slices` | `{"slices": [...]}`, every slice job this slice service process remembers, of every user key, in the order accepted; the user key is not looked at (see "The list of slice jobs" under [Progress, cancellation and cleanup](#progress-cancellation-and-cleanup)) |
| `GET /slices/<job>` | The latest progress report |
| `GET /slices/<job>/events` | The progress reports as `text/event-stream`, the latest first, ending with the final one |
| `DELETE /slices/<job>` | Cancel: `{"cancel": "cancelled" \| "cancelling" \| "finished"}`, its `cancelled` report with `cancel_reason` `requested`; kept as built and sent by no component of PenguinSlicer |
| `GET /slices/<job>/file` | The sliced file of a done slice job, and nothing else |
| `GET /slices/<job>/summary` | The sliced file's summary ([sliced-file.md](../contracts/sliced-file.md), "Summary") as a JSON body |
| `DELETE /slices/<job>/file` | The front server has stored the sliced file: `{"job", "file": "deleted"}`, the slice service's copy deleted at once and the record kept until it expires (see "Remembered for two hours" under [Progress, cancellation and cleanup](#progress-cancellation-and-cleanup)) |
| `GET /settings-table` | The table of settings whole, `gzip`-encoded when the request accepts it; the user key is not looked at (see [The table of settings](#the-table-of-settings)) |
| `GET /log?after=<n>` | `{process, lines, dropped, more}`, the log lines after the line numbered `n`; the user key is not looked at (see "The log the front server collects" under [Progress, cancellation and cleanup](#progress-cancellation-and-cleanup)) |

**The user key.** Every one of these requests but `GET /slices`, `GET /settings-table` and `GET /log` carries the user key in the header
`X-Penguin-User-Key` (`web.USER_KEY_HEADER`). One without it, or with an empty one, is
refused with `slice.no_user_key` (HTTP 400; [the contract's example](../contracts/examples/slice-http/no-user-key.json)),
whose detail names the method, the path and whether the header was missing or empty. The
slice service compares user keys and never interprets them. A part is kept, and a slice job
held (`JobPool.submit(user_key=...)`, `JobPool.owned_by`), under the user key that sent it.
A request about another user key's slice job is answered exactly as one about an unknown
slice job (`slice.unknown_job`, HTTP 404) and logged as a refusal, so nobody learns that the
slice job exists. A path the interface does not offer, or a method a path does not take,
answers `slice.bad_request` before the user key is looked at.

Every answer carries `Cache-Control: no-store`. Every other answer is an error report: 400
for a request without the user key, an upload without its units (`slice.bad_units`) or
without a Content-Length (`slice.bad_request`), or a body that is not a plate configuration;
404 for an unknown slice job (`slice.unknown_job`) or a path the interface does not offer
(`slice.bad_request`, also 405 for a method a path does not take); 409 for a sliced file or
summary that is not there (the slice job's own error report, `slice.cancelled` or
`slice.not_ready`), and for a delete of the sliced file of a slice job not ended
(`slice.not_ready`); 410 for a sliced file gone from the disk or deleted once stored
(`slice.file_gone`, for the summary too); 413 for an upload over `MAX_PART_BYTES` or a plate configuration over
`MAX_PLATE_CONFIGURATION_BYTES`, each refused from its Content-Length before its body is
read, and for an upload over `MAX_PART_TRIANGLES`; 422 for a part or plate configuration a
check refused, and for parts missing from the part store; 500 for the server's own failure
(`slice.scratch_unwritable` when the work folder or the part store cannot be written, a full
disk for one, `slice.unexpected` for a bug, logged with its traceback); 503 when the queue is
full (`slice.busy`) or the slice service has been asked to stop (`slice.stopping`); 400 for a
`GET /log` whose `after` is not a whole number (`slice.bad_request`); and a `failed` report's `slice.output_too_large` for a sliced file over 50 MB
(see [Plate limits](#plate-limits)). The file and summary routes answer alike for a slice job that is unknown, failed,
cancelled or not finished. A part is checked when it is uploaded and a plate configuration
when it arrives, before a slice job is queued for it, so a refusal comes back at once.

Flask reads no body past `web.MAX_BODY_BYTES` (`MAX_PART_BYTES`): a plate configuration
sent without a Content-Length is read that far and refused for its size. Each slice job's
files live in `<work>/slice-<pid>-<start>-<random>/`: its hold on each of its parts
(`parts/<sha256>-<units>.stl`, a hard link into the part store, or a copy where hard links
fail), given up as soon as the plate is sliced, its scratch, and its sliced file, deleted
once the front server has stored it; the folder is removed when the slice job ends failed
or cancelled, or when its record expires (`RECORD_TTL_S`, two hours after its final report).
Instances of one part share that part's one file. The part store is its own folder,
`<work>/slice-<pid>-<start>-parts-<random>/`, new in each process, so the scratch of a
process that is gone and its part store are removed alike at the next start.

### The user key, the part store, units and the plate configuration

Items 1 to 4 of [Phase 2](#phase-2-one-machine), built: what follows is the code. [D72,
D73, D74, D76, D77, D78, D80, D81, D82, D83, D291, D292, D293, D294, D295]

#### The part store

([Check a part when it arrives](README.md#check-a-part-when-it-arrives),
[Keep each part once: the part store](README.md#keep-each-part-once-the-part-store);
the front server's [upload of one part](../contracts/wizard-front-server.md#parts), which
passes this route's answer to the page unchanged.)
[`POST /parts?units=mm` or `?units=in`](../contracts/slice-http-interface.md#post-partsunits--upload-one-part)
takes one part, its binary STL as the body exactly as the browser read it, with
`Content-Length`. It runs the checks of [Checks on every part](#checks-on-every-part) at
once, on the part scaled to its units, so a part that cannot be sliced is refused on the
wizard's Parts step as a notification and is not added
([the wizard's guide](../wizard/README.md#a-part-that-cannot-be-used)). The fit test
(`slice.part_too_large`) runs here against the largest printer of the profile catalog
(`service.largest_plate`: the widest, deepest and tallest of the default printer and every
printer of the catalog, 340 x 320 x 340 mm today), and again against the plate's own
printer when a plate configuration names the part. Answers, in the order they are tested:

| Status | When | Body |
|---|---|---|
| 400 | No user key | `slice.no_user_key` |
| 400 | No units label, or one that is neither `mm` nor `in` | `slice.bad_units` |
| 400 | No `Content-Length` | `slice.bad_request` |
| 413 | A `Content-Length` over `MAX_PART_BYTES` (7,500,084 bytes), refused before the body is read, exactly [examples/error-report-part-over-size.json](../contracts/examples/error-report-part-over-size.json); or over `MAX_PART_TRIANGLES` (150,000) | `slice.part_too_detailed` |
| 422 | A check refuses the part | `slice.part_unreadable`, `slice.part_not_binary`, `slice.part_too_small`, `slice.part_no_volume`, `slice.part_too_large` |
| 500 | The part store cannot be written (a full disk, for one) | `slice.scratch_unwritable` |
| 201 | The part passes and is kept in the part store | The part's record |

Open: Railway's limit on the body of a request is not known
([Railway's limit on the body of a request](README.md#unmeasured), the front server's
item); the 7.5 MB limit is what is built.

An upload carries no part name, so the sentences of its refusals and warnings say "This
part" (`service.UPLOAD_NAME`, capitalised where it starts a sentence), and a refusal's
`where` names no part. The part's record is the contract's: `sha256` (64 lowercase
hexadecimal characters), `units` (the label it was kept under), `measurements`
(`triangles`; `size_mm`, the bounding box in millimetres after the scale; `volume_mm3`, or
`null` for a surface that is not closed) and `warnings`, in the shape of the sliced file's
`part_warnings` without `where` (`slice.part_not_watertight`, `slice.part_inside_out`,
`slice.part_maybe_inches`). The same bytes sent again by the same user key under the same
units answer the same record, are not checked again, and count as a use.

The part store's rules (`part_store.PartStore`):

- **Where.** One folder per user key, named `part_store.user_folder(user_key)`: the SHA-256
  hash of all the user key's UTF-8 bytes, 64 lowercase hexadecimal characters. A user key is an
  arbitrary string from outside, so it never names a path itself: a hash holds no `/` or
  `..`, is never empty or too long, two different user keys never share a folder (that would
  take a collision of SHA-256), and the same user key gets the same folder in every process
  with no table to lose at a restart. Each part is `<sha256>-<units>.stl` in its user key's
  folder, its bytes exactly as they arrived, written under a temporary name and renamed so a
  part's file is always whole. The whole user key is hashed, however long (a lone surrogate
  as `surrogatepass` writes it). Two first uploads of the same bytes under one user key at
  once both run the checks; the second finds the first's entry and keeps it, as a use, so a
  slice job that found the first can still hold it.
- **Found only under all three.** A part is found only under its user key, its hash and its
  units together, so two users who upload the same file each have their own entry, nobody
  can learn whether someone else uploaded a given file, and one file under `mm` and `in` is
  two entries with different records.
- **Two hours.** A part stays 7,200 s (`part_store.PART_STORE_TTL_S`) after it was last
  used; its upload is a use, and so is each slice job that names it, when it is accepted.
  The job pool's sweeper (`SWEEP_INTERVAL_S`, 10 s) sweeps the part store too
  (`JobPool.start_sweeper(also=...)`).
- **No count of parts for one user key.** `MAX_PARTS` (25) stays what it is in
  [the contract](../contracts/plate-configuration.md#limits-in-phase-2): the different
  parts one plate may use, not a bound on the part store.
- **A limit on disk.** The parts of every user key together take at most the setting
  `PENGUIN_SLICE_PART_STORE_MAX_MB` (see [Settings](#settings); 1,024 MB by default, the
  starting figure for one machine). Past it, the least recently used parts of any user key
  are removed, never the part just added, and those users' pages upload them again without
  their being told. Open: the disk was never measured ([Disk](README.md#unmeasured)); the
  slice container's figure is set from that measurement before phase 3.
- **Empty at start.** The part store's folder is new in each slice service process, and
  `service.clean_stale_scratch` removes the folder of a process no longer running, so the
  slice service starts with an empty part store.
- **A slice job's own hold.** When a slice job is accepted it takes its own hold on each
  part's file (`PartStore.hold`: a hard link into its folder, a copy where the file system
  has none), under the part store's lock, so removing a part never touches a slice job
  already accepted. A part removed between the checks and the hold makes it missing
  (`slice.part_missing` with `missing_parts`), and nothing is held.

#### Units

([Units](README.md#units); [A part in phase 2](../contracts/plate-configuration.md#a-part-in-phase-2).)
The units label travels with the upload (`units`) and in each part of the plate
configuration (`units`, `"mm"` or `"in"`). Only the slice service applies the scale
(`part_store.UNITS`): a part in inches is multiplied by 25.4 about the STL's own origin,
before anything else (`mesh.read_binary_stl(scale=...)`), in the mesh the checks measure
and in the model written for Orca (`plate_3mf.write_plate_3mf`, each part's `scale`); an
instance's `x` and `y` stay millimetres on the plate whatever the part's units. The checks on
arrival run on the scaled mesh: `MIN_PART_EXTENT_MM`, the fit on the largest printer, and
`slice.part_maybe_inches` (`MAYBE_INCHES_MM`, 5 mm), which is not raised for a part labelled
`in`. The slice service never guesses units: an upload without a label, or with another
value, is `slice.bad_units` (HTTP 400); a part of a plate configuration without `units`, or
with another value, is `slice.bad_plate_configuration`. A plate configuration that names a
hash under units it was not uploaded with gets `slice.part_missing`.

#### The plate configuration in its phase 2 form

([Check a plate before it is sliced](README.md#check-a-plate-before-it-is-sliced);
[Fields in phase 2](../contracts/plate-configuration.md#fields-in-phase-2),
[Checks in phase 2](../contracts/plate-configuration.md#checks-in-phase-2),
[Parts missing from the part store](../contracts/plate-configuration.md#parts-missing-from-the-part-store),
[Limits in phase 2](../contracts/plate-configuration.md#limits-in-phase-2).)
[`POST /slices`](../contracts/slice-http-interface.md#post-slices--submit-a-plate-configuration)
takes the plate configuration as a JSON body with the fields `plate_id`, `submission_id`,
`parts` (each `name`, `sha256`, `units`), `instances` (each with `orientation` or
`rotation`), `printer`, `filament`, `process`, `overrides` and `local_time`, and no files
(`service.PLATE_CONFIGURATION_FIELDS`, `PART_FIELDS`, `INSTANCE_FIELDS`). Slicing again
uploads nothing.

- A body whose Content-Length is over `MAX_PLATE_CONFIGURATION_BYTES` (1,048,576 bytes; the
  guide's figure, chosen without a measurement) is refused with
  `slice.bad_plate_configuration` (HTTP 413) before it is read, with the report of
  [examples/error-report-plate-configuration-over-size.json](../contracts/examples/error-report-plate-configuration-over-size.json);
  one sent without a Content-Length is refused the same way once it is read past the
  limit. A multipart body is refused with the same code (HTTP 400), and so is a body that
  is not JSON.
- **An instance's rotation**
  ([An instance in phase 2](../contracts/plate-configuration.md#an-instance-in-phase-2)).
  An instance carries exactly one of `orientation` and `rotation`, a unit quaternion
  `[w, x, y, z]` of 4 finite numbers within 1e-6 (`service.ROTATION_TOLERANCE`) of length 1,
  divided by its length before use. Step 1 refuses both, neither, or a bad quaternion with
  `slice.bad_plate_configuration`. `plate.quaternion_matrix` is the contract's matrix;
  `plate.turn_of(instance)` is an instance's turn (its orientation's name, or its rotation as
  a tuple), under which its part's footprint is kept (`mesh.turned_footprint` for a
  rotation, the part's file read once in its units), so the footprint, its centre, the
  lowest point and the placement check use the rotation's matrix in place of
  `ORIENTATION_MATRICES[orientation]`; `plate_3mf.py` writes the same transform into the
  plate it gives Orca; the log line records the rotation beside the orientation.
- Step 1 also refuses a plate configuration without `plate_id` or `submission_id` (each 1
  to 64 letters, digits, `-` or `_`), or a part without `sha256` (64 lowercase hexadecimal
  characters) or `units`.
- Step 4 finds every part an instance names in the part store under the request's user
  key, its `sha256` and its `units`. When any is missing it answers one report, starting
  nothing (`service.parts_missing`): `slice.part_missing`, HTTP 422, `where` with `stage`
  `checking` and `missing_parts`, one object (`key`, `sha256`, `units`) for each missing
  part in the order of `parts`; the message "The slicer no longer has 2 of this plate's
  parts." ("one of this plate's parts" for one); `action` `refresh_parts`; `retryable`
  false; `detail` the hashes and units
  ([the contract's example](../contracts/examples/error-report-parts-missing.json)). The
  page uploads them again and submits again with the same `submission_id`; the user sees
  nothing. An instance whose `ref` names no key of `parts` keeps `slice.part_missing` with
  no `missing_parts`, tested first. Each found part is then tested against the plate's own
  printer (`slice.part_too_large`, naming the part); the other checks on a part are not
  repeated, since what they found is kept with the part in the part store.
- The answer is 202, `{job, plate_id, submission_id, progress, part_warnings}`
  ([the contract's slice job](../contracts/slice-http-interface.md#post-slices--submit-a-plate-configuration),
  [its example](../contracts/examples/slice-http/slice-accepted.json)), the warnings now
  naming their part; the front server makes its own answer from it
  ([Submitting a plate configuration](../contracts/wizard-front-server.md#submitting-a-plate-configuration)).
  Its progress report is the slice job's first, `queued` with `ahead`; a repeat and a
  replacement are under [A plate's slice jobs: repeats, replacement and the places](#a-plates-slice-jobs-repeats-replacement-and-the-places).

The `overrides` are checked against the table of settings in step 3
([Settings a plate configuration may replace](#settings-a-plate-configuration-may-replace)),
so the contract's phase 2 example is accepted as it is.

**Found with the real Orca.** The contract example's `rotation` lays the bracket on the face
of its convex hull across the L's open corner, which is no face of the part: the bracket then
touches the plate along two edges, its first layer (sliced at 0.1 mm) is two strips about
0.2 mm wide, narrower than a line Orca lays down, and the pinned Orca fails the slice with
-100. Its reason, read in its source (`GCode::collect_layers_to_print`), is "One object has an
empty first layer and can't be printed. Please Cut the bottom or enable supports.", thrown
inside a `SlicingErrors` whose own text, "Errors", is all it prints, and written to no file;
its debug log adds "It seems object Bracket #1 has floating regions" with supports off. It
fails so with supports off and with tree or normal supports on, and slices with supports and
a raft of two layers (a raft alone gives `slice.empty_layers`). Lowering the part into the
plate changes nothing, since Orca puts every object's lowest point on the plate. The placement
check accepts such a plate, since its footprint is sound, and the wizard's agrees; the slice
service explains Orca's failure instead (`slice.rests_on_an_edge`: on a -100 failure with no
reason it recognises, `plate_configuration.resting_on_no_face` reads each part again and
names the instances that meet two conditions. Their own faces on the plate,
`mesh.contact_area_mm2` within `mesh.ON_THE_PLATE_MM` (0.001 mm) of the lowest point, add
up to less than `plate_configuration.REST_AREA_MM2`, 0.01 mm². And their section at the
middle of the first layer, `mesh.first_layer_section` at half the process's
`initial_layer_print_height`, is empty once shrunk by half its `initial_layer_line_width`,
so no line of the first layer fits anywhere in it; both values are read from the slice
job's process with its overrides, and one that is missing or no length in millimetres (0,
a percentage) is the default process's, `FIRST_LAYER_MM` 0.3 and `FIRST_LINE_MM` 0.62. The
second condition keeps curved parts out: a ball of radius 20 mm on its pole and a tube of
radius 10 mm lying on a line of its vertices have no face on the plate, but at 0.15 mm up
they are 4.6 mm and 3.3 mm across and print, while the bracket on its hull face is 0.33 mm
across there and a box on an edge 0.30 mm. A part that cannot be read again leaves
`slice.orca_failed`, and so does a debug log whose warnings
(`plate_configuration.LOGGED_OBJECT_RE` over the detail's "orca debug log warning" lines)
name instances none of which is so named: Orca's evidence then points elsewhere, and the
general sentence keeps its warnings. The fast suite holds both conditions
(`tests/test_errors.py`, `TestRestsOnAnEdge`; `tests/test_mesh.py`,
`TestFirstLayerSection`), and the rule's figures with cases near its threshold through the
fake Orca's general failure: the box on its edge is named under a 0.4 mm line and under a
0.4 mm first layer and not under a 0.25 mm line; a process file of its own, with no
overrides, decides by its own first layer (0.25 mm line or 0.8 mm first layer: not named;
0.9 mm line under 0.8 mm: named); and the contract example's bracket on its hull face is
named under the default process. The face-area condition has its own case: the block on a
stem (`helpers.block_on_a_stem_stl`, a stem 0.4 mm across standing on its own 0.16 mm²
face) keeps `slice.orca_failed` alone, and beside the box on its edge only the box is
named. The upstream check pins it
(`test_a_part_resting_on_an_edge_has_no_first_layer_unless_supported_on_a_raft`). The
upstream check slices a bracket laid by a `rotation` on a face of the part itself
(`test_a_rotation_and_a_part_in_inches_slice_where_the_checks_place_them`): Orca's first
layer of it is within 0.6 mm of the slice service's footprint, and that of a 1 x 1 x 0.5 inch
block within 0.4 mm.

**Tests.** `tests/test_part_store.py` (the user keys' folders, finding, the two hours, the
limit on disk, the hold, writing), `tests/test_web.py` (`TestUserKey`, `TestUpload`,
`TestSubmit`, `TestRefusals`: every route, answer and code through the HTTP interface, with
the contract's examples), `tests/test_service.py` (`TestRead`, `TestCheckPart`: the phase 2
fields, rotations, missing parts, units), `tests/test_mesh.py`, `tests/test_plate.py` and
`tests/test_plate_3mf.py` (the scale, the rotation's matrix and its transform in the plate
written for Orca), `tests/test_errors.py` (`slice.no_user_key` and `slice.bad_units`
produced on purpose), and in the upstream check the test above.

Underneath, the interface calls `service.slice_plate_configuration`, and that calls
`slicer.slice_plate`; they are code the HTTP interface and the tests call, not ways in.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `PENGUIN_SLICE_MAX_PEAK_MB` | 2000 | The memory ceiling (see "Plate limits"). Unset or empty: the default. Otherwise 1 to 6 plain digits `0` to `9`, not 0; anything else (`²`, `٣`, `1e3`, a space, 30 digits) is refused at start with a message that names the setting. |
| `PENGUIN_SLICE_PART_STORE_MAX_MB` | 1024 | The limit on the disk the part store may take in all, in MB (see [The part store](#the-part-store)): the starting figure for one machine, since the disk was never measured. Unset or empty: the default. Otherwise 1 to 7 plain digits `0` to `9`, at least 8 (room for the largest part); anything else is refused at start with a message that names the setting. |
| `PENGUIN_SLICE_ORCA` | `slice/tools/orca/orca-slicer` | The Orca wrapper the service runs. |
| `PENGUIN_SLICE_ORCA_DEST`, `PENGUIN_SLICE_ORCA_CACHE` | | For `scripts/install-orca.sh` only (see below). |

## Orca Slicer

The slice service runs the Orca wrapper named by the environment variable
`PENGUIN_SLICE_ORCA`, or else `slice/tools/orca/orca-slicer`. It looks when a slice starts,
so the fast suite runs without Orca. `scripts/install-orca.sh` installs the pinned release
there (`PENGUIN_SLICE_ORCA_DEST` installs elsewhere, `PENGUIN_SLICE_ORCA_CACHE` keeps and
reuses each verified download). Its `ORCA_VERSION` line, with the three checksums below
it, is the only place the Orca version is stated; the tests read it from there.
Idempotent, the script exits at once when `tools/orca/VERSION` already records this
version for this platform. Linux x86_64, Linux aarch64 and macOS arm64 only.

On Linux the AppImage is extracted (no FUSE needed) and the wrapper runs the binary
directly with its own library path. When the host lacks Orca's runtime libraries and the
script is not running as root, it unpacks the missing Ubuntu 24.04 packages into
`tools/orca/hostlibs/`, verified against the archive's SHA-256 index. As root it stops
instead; install the distribution's packages:

```
libopengl0 libegl1 libgl1 libglx0 libglu1-mesa libgtk-3-0t64 libgdk-pixbuf-2.0-0
libatk1.0-0t64 libcairo2 libcairo-gobject2 libpango-1.0-0 libpangocairo-1.0-0
libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 libglib2.0-0t64 libdbus-1-3
libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libwebkit2gtk-4.1-0
libjavascriptcoregtk-4.1-0 libsoup-3.0-0 libsecret-1-0 libwayland-client0 libwayland-egl1
libwayland-server0 libxkbcommon0 libx11-6 libxext6 libsm6 libice6 libstdc++6 libexpat1
liblzma5 libmspack0t64 zlib1g
```

`slicer.py` is the one module that runs Orca and reads what Orca writes: the command
lines, the environment, Orca's return codes (`ORCA_RETURN_CODES`, the only table of them),
its reasons in `result.json`, its debug log (`orca_log_warnings`, `orca_log_conflicts`), its progress messages
(`ORCA_STAGES`), and the sliced file's entries. A change in a new Orca is absorbed there.

**How Orca is run.** With an allowlisted environment (`PATH`, `TMPDIR`, `LANG`, `USER`,
`LOGNAME`) and its own `HOME`, `XDG_CONFIG_HOME`, `XDG_RUNTIME_DIR` and `--datadir` in the
slice's scratch folder, so secrets never reach it and two slices never share state; in a
session of its own, so Orca and every child it starts form one process group; on Linux
with `PR_SET_PDEATHSIG`, so Orca dies with the thread that started it even when the
service is killed outright; with stdout and stderr read as they arrive into a tail of the
last 200 lines (a line is cut at 4 KB), so megabytes of output neither block Orca nor sit
in memory; with `--debug 3 --logfile <scratch>/orca.log`, its debug log (about 12 kB for a
small plate, removed with the scratch folder). A plate is sliced with
`--arrange 0 --orient 0`: Orca keeps every instance where the plate configuration put it.
The plate 3MF lists its objects grouped by part and its build items in instance order, so
the right placement rests on Orca pairing each build item with its object by `objectid`;
the real-Orca suite slices nine interleaved instances of three parts and holds each named
object's first layer to its own instance within 0.25 mm
(`test_interleaved_parts_each_land_where_their_own_instance_is_placed`). Before Orca starts, whatever an earlier run left in its folder that the service reads (the
sliced file and its temporary name, `result.json`, the debug log) is removed, so a stop
before Orca writes anything is never handed an old file.

**Stopping Orca.** A cancel or the timeout sends SIGTERM to the process group, waits
`STOP_GRACE_S` (5 s) for Orca to go, then sends SIGKILL. Whatever is left of the group is
killed once Orca has exited, and only then is Orca reaped, so the group's id cannot be
reused under the service. A cancel is reported only after all of this, and a cancel always
discards the sliced file.

**What Orca reports while slicing.** Found by experiment with the pinned 2.4.2, headless on
aarch64 Linux: stdout carries almost nothing (one line on failure, `run found error,
return -100, exit...`, and at most a harmless Wayland socket warning). `--pipe <path>` is
the progress channel: Orca opens the path (a FIFO the service makes) and writes one JSON
object per line, `{"message", "plate_count", "plate_index", "plate_percent",
"total_percent"}`, at each of its stages: "Start to load files" (1%), "Loading files
finished" (2), "Prepare slicing" (3), "Slicing begins" (6), "Slicing mesh" (7),
"Generating walls" (16), "Generating infill regions" (25), "Generating infill toolpath"
(34), "Checking support necessity" (48), "Detect overhangs for auto-lift" (66),
"Optimizing toolpath" (70), "Generating G-code" (75), "Slicing finished" (93), "Generate
thumbnails" (94), "Exporting 3mf" (97), "All done, Success" (100). The slice service maps
each message to a stage (`slicer.ORCA_STAGES`) and reports Orca's own `total_percent` as
the fraction; it invents none between messages. On a small plate the first messages can
arrive together. Generating G-code takes most of the time on a large plate, so the
fraction sits at 0.75 longest. Orca's command line starts its warning reports only when
`--pipe` is given.

**What Orca says when it fails.** Its return code is in `result.json` (`return_code`)
and in the exit status as a byte (-100 is exit 156). Its general reason is
`error_string`; the specific one, when it gives one, is `sliced_plates[].warning_message`,
for example "Object can't be printed for empty layer between 9.9 and 11.34.\nObject: Tower
#1\nMaybe parts of the object at these height are too thin, or the object has faulty
mesh". Both are read before the scratch folder is removed and kept in the detail.

**Orca's own sentence in an error report.** Item 13 of [Phase 2](#phase-2-one-machine),
built ([Orca's own sentence in an error report](README.md#orcas-own-sentence-in-an-error-report);
[the error report's `orca_sentence`](../contracts/error-report.md#fields)). The reports of
`slice.empty_layers` and `slice.empty_layers_with_supports` (`errors.ORCA_SENTENCE_CODES`)
carry `orca_sentence`: the line of Orca's `warning_message` that names the empty layer
(`slicer._gap_sentence`, the line `EMPTY_LAYER_RE` matched, which is its first line with
the pinned Orca), exactly as Orca wrote it but for the spaces around it, such as "Object
can't be printed for empty layer between 9.9 and 11.34.". A line over 300 characters
(`slicer.ORCA_SENTENCE_MAX_CHARS`) is left out rather than cut, since a cut quotation would
no longer be Orca's words; so is a sentence Orca did not write. `errors.error_report` adds
the field on those two codes only, so no other code's report ever carries it, whatever its
exception holds. With supports on the pinned Orca names other heights for the same part
(9.9 and 10.62 for the corpus' `slivers_and_lattice` part). Tests: `tests/test_slicer.py`
(the sentence kept, the line found wherever it is in the warning, 300 characters kept and
301 left out, no other failure keeping one), `tests/test_errors.py` (each of the two codes
carries it from the fake Orca's message, every other code's report has none, a gap failure
without one leaves it out, and
[the error report's example](../contracts/examples/error-report-orca-sentence.json) equals
what the code produces), and the upstream check `test_orcas_empty_layer_sentence_is_pinned`,
which pins the wording with supports off and on.

For a
plate with nothing to slice Orca returns -100 with only the general `error_string`, and
says why on stdout: "No layers were detected. You might want to repair your STL file(s) or
check their size or thickness and retry." (an open 100 mm box, a box with half its
triangles, a tilted flat sheet) or "The print is empty. The model is not printable with
current print settings." (a 0.15 mm cube, a 0.15 mm needle); the service reads those lines
(`ORCA_OUTPUT_REASONS`) into `slice.no_layers` and `slice.print_empty`, and into the log's
Orca reason. An Orca that cannot load a shared library exits 127 with the loader's words
and no `result.json` (`slice.orca_unstartable`). Under an address-space limit Orca prints
`std::bad_alloc` and returns -100 (1 GB), or aborts with SIGABRT after "terminate called
recursively" (500 MB, reported as a crash: the words do not say memory).

**Orca's debug log.** Every warning Orca reported while slicing is in its debug log; its
`result.json` holds at most one of them, and on a plate of several warned instances which
one changes from run to run (the Popcorn Penguins' mixed plate warned of four blocks and the pulley,
and `result.json` named the Elevator Block Top in one slice and the Elevator Block Carriage
in the next). The service reads the log in one place, `slicer._log_lines` (each line read as
at most 4 KB, at most 64 MB of the log), for two things. `slicer.orca_log_warnings` takes
the lines matching `LOG_WARNING_RE`, `cli_status_callback: percent=-1, warning_step=7,
message=..., message_type=2, flag=32`. `slicer.orca_log_conflicts` takes the line Orca
writes when it refuses a plate with -101, `gcode path conflicts found between
Elevator_Block_Top #2 and Elevator_Block_Top #1` (`LOG_CONFLICT_RE`), the one place that
names the two instances (`result.json` says only "G-code conflicts detected after slicing
... try moving the wipe tower"). A warning from either source goes through one normaliser
(stripped, cut to 300 characters), so the same warning in `result.json` and the log is one
warning. Warnings and pairs are kept each once and sorted with the runs of digits in them
read as numbers, `#2` before `#10`, without converting them (a run of 5,000 digits is
fine), ties broken on the text itself (`007` before `07` before `7`), so the order never
depends on Orca's threads; the whole log is read and the first of that order kept, so a
plate with more warnings than are kept keeps the same ones every time. After a good slice
the sliced file's summary carries every warning with `result.json`'s, the first 300
(`slicer.plate_warnings`).
When Orca fails with only its general reason (`slice.orca_failed`), the first 5 go into
the sentence. The log cannot say which warning, if any, is why the slice failed:
a part that slices soundly warns too, so on a plate where another part fails its warning
is beside the point. So the sentence keeps the general failure and adds every warning
found, labelled as possibly unrelated: "The slicer could not slice this plate. It also
warned, though this may not be why it failed: It seems object Block #1 has floating
regions. Please re-orient the object or enable support generation." (a 20 x 20 x 5 mm
block on a stem 0.4 mm across: re-oriented, it prints). The limit, measured: a mushroom (a
20 mm cap on a 3 mm stem) slices alone with the warning "It seems object Mushroom #1 has
floating cantilever"; beside a needle that fails, the slice fails because of the needle,
the needle is named nowhere, and the mushroom's warning is the only one the sentence can
add (the real-Orca suite holds both plates). A log that is missing, unreadable or holds no
such line leaves the general sentence, "The slicer could not slice this plate.": the
service never states a reason of Orca's the log does not give. Some reasons reach no file at all. A part
whose first layer is empty (a needle 0.3 mm across and 300 mm tall, thinner than the
nozzle prints) fails as an error that the pinned Orca collects and loses (it prints
`Errors` on stderr): neither `result.json` nor the debug log, even at `--debug 5`, holds
the reason, so that part gets the general sentence. The one exception is the slice
service's own finding, `slice.rests_on_an_edge`: an instance resting on no face of its own,
measured from the part itself and never from a reason Orca did not give
([The plate configuration in its phase 2 form](#the-plate-configuration-in-its-phase-2-form)
has its rule; a needle stands on a face
and keeps the general sentence). The debug log's format is Orca's and
can change at an upgrade: the upstream check slices the block on a stem and fails when the
reason is no longer found (see "Taking a new upstream version").

## Profiles

`src/penguin_slice/profiles/` holds the default set, three self-contained Orca profiles
flattened from the BBL vendor tree inside the installed Orca:

| File | Source profile |
|---|---|
| `printer.json` | `machine/Bambu Lab H2S 0.6 nozzle` |
| `filament.json` | `filament/Generic PETG @BBL H2S` |
| `process.json` | `process/0.24mm Balanced Quality @BBL H2S 0.6 nozzle` |

A Bambu Lab H2S with the 0.6 mm High Flow hardened steel nozzle, Generic PETG and the
Textured PEI Plate. The nozzle variant and the plate are in no vendor profile, so the
flattening script writes `nozzle_volume_type` and `curr_bed_type` into every printer
profile itself; without them Orca's command line falls back to the Standard nozzle and
the smooth plate, silently.

`profiles/catalog/` holds every Bambu Lab H2S printer and every filament and process that
names one, flattened the same way, with `index.json` listing which printers each fits.
These are the names a plate configuration may use. Orca's command line does not resolve
`inherits` and the desktop app exports only differences, so both are regenerated after an
Orca upgrade (`make upgrade-orca` does it):

```
uv run --project slice python slice/scripts/flatten_orca_profiles.py
uv run --project slice python slice/scripts/flatten_orca_profiles.py --audit-only   # resolved values and their sources
```

## The table of settings

Items 5 and 6 of [Phase 2](#phase-2-one-machine), built
([How the list of accepted settings is made](README.md#how-the-list-of-accepted-settings-is-made),
[Where the wizard gets the list of settings and the profile catalog's names](README.md#where-the-wizard-gets-the-list-of-settings-and-the-profile-catalogs-names),
[Accept settings](README.md#accept-settings),
[Taking a new Orca version](README.md#taking-a-new-orca-version);
[the table of settings](../contracts/settings-table.md),
[Settings in phase 2](../contracts/plate-configuration.md#settings-in-phase-2), passed on by
the front server's [request for it](../contracts/wizard-front-server.md#the-table-of-settings)).
The table, `src/penguin_slice/settings/table.json`, is generated, never written by hand, and
checked in: `format` 1, `orca_version` `2.4.2`, 338 settings, the values of the 16 process
profiles of the catalog and the catalog's names (4 printers, 136 filaments, 16 processes);
378,740 bytes, 34,716 compressed.

**The source.** `SHA_SOURCE` in `scripts/install-orca.sh`, beside `ORCA_VERSION`, pins the
SHA-256 of GitHub's archive of the version's tag
(`https://github.com/OrcaSlicer/OrcaSlicer/archive/refs/tags/v<version>.tar.gz`, 131 MB for
2.4.2); `install-orca.sh` itself does not download it. `scripts/fetch_orca_source.py`
(`make orca-source`) downloads the archive, verifies it, and keeps only the three files the
generator reads (`make_settings_table.SOURCE_FILES`: `src/libslic3r/Preset.cpp`,
`src/libslic3r/PrintConfig.cpp`, `src/slic3r/GUI/Tab.cpp`, 1.2 MB) in `tools/orca-source/`
with a `VERSION` stamp of the version and the checksum. It is idempotent: a stamp that
records the pin, its version and its checksum both, downloads nothing; a stamp of the same
version with another checksum is fetched and verified again. A wrong checksum, an archive
that is not a `.tar.gz` or that lacks one of the three files keeps nothing new and leaves an
earlier source as it was; the earlier source is moved aside and removed only once the new
one is in place, so a failed move leaves it as it was too;
the members are read by name and written by the script, never extracted, so no path in the
archive is followed. `PENGUIN_SLICE_ORCA_CACHE` keeps each verified archive as
`OrcaSlicer-<version>.tar.gz` and reuses it, verified against the pin like a download: a
cached archive that has changed is refused by name, nothing is kept, and it stays in the
cache until removed (`test_a_changed_archive_in_the_cache_is_refused_and_named`); an
archive that fails its checksum is never cached. `make test-upstream` runs `make orca-source`
first. GitHub publishes no checksum of a tag's archive, so `make upgrade-orca` fetches the
new version's archive trusting the download and pins the checksum of what it received
([Taking a new upstream version](#taking-a-new-upstream-version)); every later fetch is
verified against that pin.

**The generator.** `scripts/make_settings_table.py` (`make settings-table`; `--check`
compares with the checked-in table instead of writing it, and exits 1 when they differ)
reads Orca's source as data, with regular expressions over the C++ text with its comments
removed; no code of Orca's is copied into PenguinSlicer (Orca is AGPL, PenguinSlicer MIT).
From `Preset.cpp` it takes the process settings, in Orca's order, from
`s_Preset_print_options` (355 at 2.4.2). From `PrintConfig.cpp` it takes each setting's
definition, the lines from its `def = this->add("<name>", <type>)` to the next assignment
of `def`: `label` (or `full_label` when there is no `label`), `tooltip` (the
`explanation`), `sidetext` (the `unit`), `min` and `max` (a literal or a named constant of
the file, `max_temp`), the `enum_values` and `enum_labels` of a choice (pushed one by one,
given as a braced list, or taken over from another definition through its variable,
`def_top_fill_pattern->enum_values`), and the default given to `set_default_value`, an
enum's default turned into its key through the file's `s_keys_map_<Type>` tables. A
setting without a `min` or `max` line has no bound in the table. Which settings Orca
keeps for each extruder variant comes from `print_options_with_variant`. From `Tab.cpp`
it takes the page (`section`) and setting group of each setting from `TabPrint::build`, in
the order Orca shows them, which is the table's order. Orca's type gives the kind:
`coFloat` a number in `decimal` form, `coInt` `integer`, `coPercent` `percent`,
`coFloatOrPercent` `decimal_or_percent`, `coBool` a choice of `"0"` and `"1"` labelled
"Off" and "On", `coEnum` a choice, `coString` a text; a list type is the same kind for a
setting kept for each variant and is refused otherwise. `process_values` holds, for each
process profile of the catalog, each setting's own value in the profile, or Orca's default
written as Orca writes it (a number as an ostream writes it, six significant digits; a
percentage with its `%`; on and off as `"0"` and `"1"`) when the profile holds none. A
profile's list for a setting Orca keeps once gives its first value: Orca reads only that
(see "Found with the real Orca" below). For a `per_variant` setting it would give the value
of the profile's printer's variant (`extruder_type` and `nozzle_volume_type`, "Direct Drive
High Flow", found in the profile's `print_extruder_variant`). A text setting's
`max_length` is the length of its longest value among the process values, and never less
than 1. `catalog` is `profiles/catalog/index.json`'s three lists in its order, each
printer with its `printable_area` (its corners, from the profile's `"<x>x<y>"` strings) and
`printable_height`. The generator stops with a message naming the setting or the file
(`TableError`) when the source is missing, when a process setting is classified nowhere,
classified twice, or classified but not one of this Orca's, when a programmatic or not
offered setting has no reason, and when a parameter has no definition, is on no page, has
choices whose labels do not pair up, a default or a line it cannot read, or a type the
table cannot hold. A line it cannot read in a definition no parameter needs is no error.

**The classification.** `src/penguin_slice/settings/classification.json` classifies every
process setting of the pinned Orca by hand, in one of three lists: `parameters` (338, the
table's settings), `programmatic` (3) and `not_offered` (14), each of the last two with its
reason, written to complete the sentence "The setting `<name>` cannot be changed: ...",
which the refusal shows. Programmatic: `post_process` (runs a program), `filename_format`
(names a file on the server: the sliced file's name, which the slice service sets) and
`process_change_extrusion_role_gcode` (custom G-code). The other custom G-code
(`machine_start_gcode`, `before_layer_change_gcode` and the rest) and every other setting
of the filament and printer profiles are no process setting, so they are in no list and
refused as such. Not offered: the 13 process settings Orca shows on no page of its process
settings (`travel_speed_z`, `enforce_support_layers`, `raft_expansion`,
`support_interface_loop_pattern`, `prime_tower_flat_ironing`, `wiping_volumes_extruders`,
`calib_flowrate_topinfill_special_order`, `ironing_expansion`, and the profile's own
bookkeeping: `print_extruder_id`, `print_extruder_variant`, `compatible_printers`,
`compatible_printers_condition`, `inherits`), which have no page or group to be shown
under, and `small_area_infill_flow_compensation_model`, a list of figures no kind of entry
can describe. The agent taking a new Orca version classifies every new setting before the
work is finished.

**The route.** [`GET /settings-table`](../contracts/slice-http-interface.md#get-settings-table)
answers the checked-in file's bytes whole as `application/json`, with `Content-Encoding:
gzip` (compressed once per process, `settings_table.Table.gzipped`) when the request's
`Accept-Encoding` allows `gzip` with a quality above 0 (or `*`), and `Vary:
Accept-Encoding`. It answers for the whole slice service, so the user key is not looked at.
The table is read once per process (`settings_table.load`); one that is missing or not a
table answers 500 with `slice.profile_unreadable` ("The slicer could not read its table of
settings."), logged. The front server passes it to the wizard unchanged and keeps no copy
from one start to the next.

### Settings a plate configuration may replace

`overrides` holds settings under Orca's own names, each value a string as Orca writes it,
and every setting of the table may appear (`settings_table.validate_overrides`, step 3 of
the checks). Each value is checked against its entry before Orca runs:

- a value that is not a string is refused;
- a choice must be one of its `choices`' values (`"0"` or `"1"` for an on-and-off setting);
- a number must be of its `number_form`, written as Orca writes it, in the digits 0 to 9
  only (another script's digits are refused): `integer` `-?[0-9]+`, and within a C++ int;
  `decimal` `-?[0-9]+(\.[0-9]+)?`, no sign `+`, no space, no exponent, no `nan`, no `.5`;
  `percent` a decimal with `%`; `decimal_or_percent` either; at most 40 characters
  (`MAX_NUMBER_CHARS`); then
  within `min` and `max` where the entry has them, a percentage's figure in percent;
- a text must be no longer than its `max_length`, hold no control character (`\x00` to
  `\x1f`, `\x7f`) and no lone surrogate (U+D800 to U+DFFF, which a JSON `\ud800` escape
  can carry and UTF-8 cannot write): "Insert solid layers (Strength, Advanced) cannot hold
  a character that is not valid text."

Every process profile's own value of every setting passes these checks. A setting the
table does not hold, or a value that does not fit, refuses the plate configuration with
`slice.bad_overrides` (HTTP 422, action `choose_profiles`), whose sentence names the
first problem and whose `detail` lists every one (at most 20, `DETAIL_PROBLEMS`, then how
many more); a value shown is cut to 120 characters (`SHOWN_CHARS`). The setting is named
by its label, page and group, "Wall loops (Strength, Walls) must be at most 1000, not
1001."; one the table does not hold by its name: "The setting post_process cannot be
changed: it runs a program (the post-processing scripts Orca runs on the finished file).",
"The setting nozzle_temperature belongs to the filament or printer profile, which a plate
cannot change." (the names of the default set's filament and printer profiles), "The
setting wall_lops is not a print setting the slicer knows."; a name longer than 120
characters, or holding a character that does not print (a line break, `\x85`, ` `),
is shown as its quoted, escaped form. The remedy: "Change that
setting to a value it takes, or back to the profile's, and slice again."

The checks hold a value to the bounds Orca's definitions give and no further. Orca checks
some values against others only while it slices, so a value inside the table's bounds can
still fail there: with the pinned Orca, `layer_height` `"50"` ends as `slice.orca_failed`,
with Orca's own reason in the `detail`. Repeating Orca's checks of one setting against
another is not part of the table.

Only the process profile's values are replaced
(`print_config.write_process_with_overrides`): each value is written as it was sent, and a
`per_variant` setting's one value once for each variant of the profile's
`print_extruder_variant` (once when it lists none). No setting of the pinned Orca is
`per_variant`. Supports are on when `overrides` sets `enable_support` to `"1"`, or does not
set it and the process profile's own value is `"1"`: that one question decides
`SPACING_SUPPORTS_MM` and the supports factor of both estimates. Other settings that make an
instance need more room (a wide brim, a raft, printing one object at a time) are not known
to the placement check, and Orca refuses such a plate with `slice.orca_too_close`. The four
quick changes of the wizard's Settings step are ordinary settings (`sparse_infill_density`,
`wall_loops`, `enable_support` with `support_type` `tree(auto)`, `brim_type`).

**Found with the real Orca.** Bambu Lab's process profiles hold some speeds as a list of
two values, one for each extruder variant (the 0.30 mm Standard profile for the 0.6 mm
nozzle has `outer_wall_speed` `["120", "500"]`), but Orca 2.4.2 keeps those settings once
(`coFloat`) and reads the first value of the list, the standard nozzle's: sliced on the
default printer, whose nozzle is the High Flow one, that profile prints its outer wall at
120 mm/s, not 500. The table gives 120, what Orca slices with. Five of the 16 process
profiles hold such lists with different values (the five "Standard" profiles of 0.16, 0.20,
0.24, 0.30 and 0.40 mm). The upstream check slices two profiles
and finds every one of the 338 process values, and ten overrides of every kind, in the
settings Orca writes into the sliced file (`Metadata/project_settings.config`).

**Tests.** `tests/test_make_settings_table.py` runs the generator on
`tests/fixtures/orca_source/` (three short files written by hand in the form of Orca's,
with a classification) and `tests/fixtures/settings_catalog/`: every reader, every kind and
form, the order, the process values (own, default, a list's first, a variant's), the
catalog, and each refusal named. `tests/test_fetch_orca_source.py` fetches a made-up
archive: verified, idempotent, a stamp with another checksum fetched again, cached, a wrong
checksum, a missing file or a failed move keeping nothing new, no member outside its folder
written. `tests/test_settings_table.py` holds the checked-in
table to its contract (each entry's fields for its kind, every process profile in
`process_values` with every setting, each profile's own value accepted, nothing
programmatic and no filament or printer setting, the catalog's names, the contract's
example of the same shape) and produces every acceptance and refusal, with `per_variant`
on a table that says a setting is. `tests/test_web.py` (`TestSettingsTable`: whole, gzip
or not by `Accept-Encoding`, no user key needed, what it answers is what is accepted),
`tests/test_plate_configuration.py` (one setting of each kind and form reaching the
process file Orca is given), `tests/test_service.py` (supports through the overrides and
through the process profile), `tests/test_errors.py` (`slice.bad_overrides`, the table
unreadable, a wide brim 5 mm apart ending `slice.orca_too_close` with the fake Orca), and
`tests/test_contracts.py` (the contract's settings example accepted). In the upstream check,
`tests_orca/test_settings_table.py`: the source is the pinned version's;
`test_every_setting_of_the_pinned_orca_is_classified` fails naming each process setting
classified nowhere; `test_the_checked_in_table_is_what_the_generator_makes` fails when the
table differs from what the generator makes; and Orca slices with the table's values and
the overrides as above.

## Sample part

`src/penguin_slice/sample_part.stl`, an L bracket 40 x 30 x 12 mm (binary STL, 20
triangles), written by `scripts/make_sample_part.py`; the fast suite checks that the two
agree byte for byte. `slicer.slice_stl` slices it alone with the default set and
`--arrange 1` (the upstream check uses it).

## Shared plates for the placement checks

([Shared plates for the two placement checks](README.md#shared-plates-for-the-two-placement-checks);
[the wizard's placement rules](../wizard/README.md#the-placement-rules-and-what-each-problem-says).)
The set's folder, file form, plates, parts and agreement are fixed in
[Shared plates for the placement checks](../contracts/plate-configuration.md#shared-plates-for-the-placement-checks).
`contracts/examples/placement/` holds 13 plates, one JSON file each with `description`,
`plate_configuration` and `expected`:

| Rule | Passes | Fails |
|---|---|---|
| The 3 mm margin | `margin-pass.json` (3.01 mm inside the left edge) | `margin-fail.json` (2.99 mm) |
| The printable height | `height-pass.json` (`post-340.stl` standing, exactly 340 mm); `height-laid-down-pass.json` (`post-341.stl` on its side, `orientation` `+x`, `angle` 30) | `height-fail.json` (`post-341.stl` standing) |
| 5 mm apart, supports off | `spacing-pass.json` (5.01 mm) | `spacing-fail.json` (4.99 mm) |
| 12 mm apart, supports on | `spacing-supports-pass.json` (12.01 mm) | `spacing-supports-fail.json` (11.99 mm) |
| A turned instance | `angle-pass.json` (a bracket at `angle` 37, 5.01 mm from one at 0) | `angle-fail.json` (4.99 mm) |
| A rotation | `rotation-pass.json` (the bracket laid by `rotation` on its hull face across the L's open corner, at `angle` 15, 5.01 mm from a spacer) | `rotation-fail.json` (4.99 mm) |

Every plate is a whole phase 2 plate configuration over the default set (no `printer`,
`filament` or `process`), with `plate_id` and `submission_id` made by `uuid.uuid5` from the
file's name so that they never change, and `overrides` holding only `enable_support`
(`"0"` or `"1"`), so that whether supports are on never depends on the process profile. Its
parts are named by the SHA-256 hashes of `contracts/examples/parts/bracket.stl`,
`spacer.stl` (a 40 x 30 x 10 mm box), `post-340.stl` and `post-341.stl`, all in `"mm"`; the
posts' parts are named `Post-340` and `Post-341`, so the too-tall instance is
`Post-341 #1`.

`scripts/make_placement_parts.py` writes the two posts (10 x 10 x 340 and 10 x 10 x 341 mm
boxes on the origin, 12 triangles each) and every plate. It computes each position with
geometry of its own from the contract's Coordinates and rotation matrix (its own convex hull,
polygon distance and a bisection along x, positions kept to 6 decimals, so each distance is
within 1e-6 mm of the figure plus or minus 0.01 mm), never with `plate.py`, so the placement
check is tested against an independent computation. It also asserts that every distance a
plate does not try is more than 1 mm clear of its rule. The rotation plates' `rotation` is
`LAID_BRACKET_TURNED`: the contract example's `LAID_BRACKET` followed by 30 degrees about the
vertical, at `angle` 15. `LAID_BRACKET` alone is a quarter turn about a horizontal axis, and
on the bracket it and its inverse give the same footprint, so plates made with it would pass
a check that turns by the transposed matrix; under `LAID_BRACKET_TURNED` the turned
bracket's bounding box is 50.59 x 15.19 mm, and under its inverse 41.48 x 33.20 mm. After a
change to a rule or a figure:

```
uv run --project slice python slice/scripts/make_placement_parts.py
```

and change both components' tests in the same commit
([the contracts' rules](../contracts/README.md#rules)).

`tests/test_placement_plates.py` holds the set to the script's output byte for byte (the
plates and the posts), each plate's `expected` to the contract's table, each file to the
contract's form (the phase 2 fields only, with the types the contract fixes: each part's
`sha256` naming a file of `contracts/examples/parts/`, a `rotation` of 4 numbers and length 1
or one of the six orientations, `angle` an integer from 0 to 359, `x` and `y` finite numbers),
and runs every plate through the slice service's front door: it uploads every part of
`contracts/examples/parts/` with `POST /parts` and submits the plate with `POST /slices`,
comparing the error report's `code`, `instance` and `other_instance` with `expected`; an
instance with a `rotation` goes through the code's own placement of a rotation, and the
code's `plate.quaternion_matrix` is held to the test's own copy of the contract's matrix.
Each plate is sent as it is, its `enable_support` under Orca's own name. It also
measures, from the footprints the code makes, that each plate's
deciding distance is its figure plus or minus 0.01 mm. The footprints keep their points to
0.001 mm (`mesh._footprint`), so the slice service's own distances are within about
0.0007 mm of the script's; the 0.01 mm step covers that. It runs the two rotation plates
again with the rotation's inverse (the conjugate quaternion), and again with the angle
applied before the rotation, and requires a different answer on at least one of them each
time. With the check's tolerance
`plate.EPS_MM` made 0.02 mm, the five failing plates of the spacings and the margin fail
their test; made -0.02 mm, the six passing ones do. Beside the 13 plates the folder holds one
folder, `offered-faces/`, the wizard's (below), and nothing else.

### The faces the wizard offers

`contracts/examples/placement/offered-faces/real-parts.json` is written by the wizard
(`make -C wizard offered-faces`, [its details](../wizard/README-details.md#the-faces-offered-against-the-real-orca)):
the eight real parts of `contracts/examples/parts/real/`, named as a plate configuration names
a part, and one pose for each face the wizard offers to lay each on, its instance exactly as a
phase 2 plate configuration carries it (`orientation` or `rotation`, `angle` 0, at the plate's
middle), with the patch it lays on, its rank by area and by auto-orient's cost. Two suites
read it:

- `tests/test_offered_faces.py`, in the fast suite: no pose is one on which an instance rests
  on no face of its own, by `resting_on_no_face`'s two conditions with the default process's
  first layer (`plate_configuration.REST_AREA_MM2`, `FIRST_LAYER_MM`, `FIRST_LINE_MM`). The
  wizard applies the same rule with the same figures, finding the section's inside by the
  same even-odd rule, so this checks that the two agree on the real parts; where they can
  still differ is listed in the row for `slice.rests_on_an_edge` of
  [the error report's contract](../contracts/error-report.md).
- `tests_orca/test_offered_faces.py`, in the upstream check: every pose is sliced through the
  HTTP interface as a plate of that one instance over the default set with supports off, and
  every one must slice. All 56 poses are sliced, in about 75 s on an aarch64 Linux machine
  with 8 CPUs; no sample is needed. Run alone, under whatever lock keeps one real Orca at a
  time on the machine, with
  `slice/.venv/bin/python -m pytest -s -p no:randomly slice/tests_orca/test_offered_faces.py`.

Measured with the pinned Orca 2.4.2 before the wizard had the rule: of the 60 poses it then
offered, 59 sliced and one was refused (`slice.rests_on_an_edge`, Elevator Block Bottom Inner
on a hull face of 2,999 mm² across a pocket, normal (0, -0.87, -0.49)). Twenty-one of the 60
were hull faces of the three blocks with no face of the part on the plate at all, the blocks
resting on the rims of their pockets (and four more the pulley's bounding-box patches, on its
rim); 17 of the 21 are millimetres across half a layer up and slice. Four meet both of the
slice service's conditions: the refused one, and three that Orca slices though its first
layer there is under a line across (the slanting hull faces of normal (0, 0.71, 0.71) of the
three blocks, 606 mm², shrunk by 0.2 mm leaving 0.47 mm² and by 0.31 mm nothing). The wizard
now offers none of the four.

## Checks on every part

Every part is read and examined when it is uploaded, by itself, in its units
(`service.check_part`: `mesh.read_binary_stl` and `mesh.analyse`), and what the checks
found is kept with it in the part store. A finding that makes a slice impossible or
pointless refuses the upload with an error report about "this part"; a finding Orca copes
with only warns, and the warning travels in the part's record, then, naming the part, in the
HTTP interface's answer to a submission that names it and in the sliced file's summary
(`part_warnings`). When a plate configuration names the part, only the fit is tested again,
against the plate's own printer.

| Finding | Refuse or warn | Code |
|---|---|---|
| The file is empty, too short, not an STL (an image such as a PNG or JPEG, a PDF, a zip or 3MF, a gzip, UTF-16 text, text of any length such as an HTML or JSON error page, or any file whose header gives a triangle count larger than any part the service takes), cut off, padded, has 0 triangles, or a coordinate that is not a finite number | Refuse | `slice.part_unreadable` |
| An ASCII STL, in any case and with or without a byte-order mark | Refuse | `slice.part_not_binary` |
| Over `MAX_PART_TRIANGLES` or `MAX_PART_BYTES` | Refuse | `slice.part_too_detailed` |
| 0.1 mm or less in every direction, or in one (flat) | Refuse | `slice.part_too_small` |
| Every triangle a line or a point; or no triangle shares an edge with another; or a closed surface in one plane or enclosing no volume (faces laid on top of each other) | Refuse | `slice.part_no_volume` |
| Fits the largest printer of the profile catalog in no orientation at any angle (on arrival), or the plate's own printer (when a plate configuration names it) | Refuse | `slice.part_too_large` |
| Open edges (holes, slivers, a thin open lattice): "has holes in its surface"; or, with no open edge, edges shared by more than two faces (faces doubled, a part laid over its mirror image): "has faces laid on top of each other" | Warn | `slice.part_not_watertight` |
| Closed, with its faces wound inwards | Warn | `slice.part_inside_out` |
| Every side under 5 mm (an inch file read as millimetres?) | Warn | `slice.part_maybe_inches` |

Why these: the pinned Orca slices an open box, an inside-out box, two shells, a
self-intersecting pair of boxes and a 2 x 1 x 0.5 mm block (the real-Orca suite proves
it), so refusing them would refuse good prints; a part with holes is the one that later
fails with empty layers, so its warning names it before the slice. Self-intersection is
not looked for. The fit test is a necessary condition (least width against the plate's
short side, diameter against its diagonal, height), so a part it refuses truly fits
nowhere; a long part that fits only turned towards the diagonal passes and the placement
decides.

## Plate limits

The limits that refuse a plate configuration before slicing are the instances
(`MAX_INSTANCES`, 150), the different parts they use (`MAX_PARTS`, 25), the triangles and
bytes of one part (`MAX_PART_TRIANGLES`, 150,000; `MAX_PART_BYTES`, 7,500,084 bytes,
7.5 MB), and each part's size against the plate and the printer. Memory refuses
nothing before slicing, and neither do the triangles of the whole plate: the memory
watchdog, not the instance count, is what protects the machine.

**A sliced file is at most 50 MB.** Item 12 of [Phase 2](#phase-2-one-machine), built
([Reading what Orca says](README.md#reading-what-orca-says), [The limits](README.md#the-limits)).
After the two guards of a good slice (every instance in the sliced file's list of objects,
every entry passing its checksum), `plate_configuration._check_size` fails a sliced file
larger than `limits.MAX_SLICED_FILE_BYTES` (50 MB, 52,428,800 bytes) with
`slice.output_too_large` (stage `saving`, retryable false, no action): the slice service's
own sentence ("The sliced file of this plate is larger than the 50 MB a sliced file may
be."), the remedy "Remove some instances, or move some of them to a new plate, and slice
again." (on a plate of one instance, "Split the part in CAD into smaller pieces, or
simplify it, and slice again.", since removing instances cannot help), and the file's size
and the limit in the detail. The file is removed with the scratch folder. The front server
refuses a larger one too, as `front.sliced_file_too_large`. The largest measured is 14.1 MB
(twelve Elevator Block Bottom Inner with supports on, below). Tests: `tests/test_service.py`
lowers the limit to the fake Orca's own file, which is delivered at the limit and refused
one byte over; `tests/test_errors.py` produces the code.

**The instances.** A user may print as many as 100 small spacers in a 10 by 10 grid. The
reference plate is that: 100 instances of one hex shaft spacer (for a 3/8 inch hex shaft,
1/8 inch thick, round outside and 5/8 inch across; 216 triangles, `helpers.spacer_stl`),
22 mm apart, measured with the pinned Orca and the default set, one slice at a time, on an
aarch64 Linux machine with 4 CPUs (peak: the watchdog's reading of Orca's processes; on
these plates the kernel's `ru_maxrss` of Orca read the same):

| Spacers | Slices | Peak (MB) | Orca's time (s) | Sliced file (MB) | Layers |
|---|---|---|---|---|---|
| 100 (10 x 10) | 6 | 488 to 513 | 6.2 to 7.1 | 1.81 to 1.82 | 13 |
| 150 (13 x 12) | 2 | 643 to 649 | 9.4 | 2.72 | 13 |
| 196 (14 x 14) | 2 | 815 to 829 | 12.5 to 12.6 | 3.55 | 13 |

`MAX_INSTANCES` is 150: it was set when the ceiling was 900 MB, which the plate a user
needs (100) peaked near half of, 150 left more than a quarter of free, and 196 came within
8 % of. Under the 2,000 MB ceiling (see "The Popcorn Penguins' real parts" below) 150
spacers use a third of it. Instances of larger parts reach the ceiling sooner: the Popcorn
Penguins' pulley (19 mm,
4,608 triangles) costs about 20 MB an instance, so 50 pulleys peak at 1,074 MB and 150
passed 2,500 MB and were stopped there; the watchdog stops such a slice with
`slice.out_of_memory` and its remedy asks for fewer instances. The instance limit is still
right as it is: no real plate came near it, and it bounds the placement check and the
plate write, not memory, which the watchdog guards. The limits derived from the
instance count were checked with it: the upload is bounded by the parts sent
(`MAX_PARTS x MAX_PART_BYTES`, 188.5 MB), not by the instances, since instances of one
part share one file. `MAX_PARTS` is that bound on the upload, and what the old limit of 25
instances already implied; it is not a measured limit. There is no limit on the triangles
of the whole plate. One was tried (3,750,000) and removed: it rested on no measurement and
never decided anything measured. 100 instances of a 16 mm knob of 19,836 triangles (1.98
million, about half that limit) passed every check, sliced for 27.9 s and were stopped by
the watchdog at 922 MB with `slice.out_of_memory`. No measurement shows a value that would
refuse such a plate before the watchdog stops it and never refuse a plate that slices (25
hubs of 20,000 triangles, 0.5 million, slice at 842 MB), so the watchdog decides. The
placement check compares every pair (11,175 for 150 instances on one spot, a few
hundredths of a second) and its refusal's detail lists at most 20 of the problems; the
time limit (`PLATE_SLICE_TIMEOUT_S`, 240 s) is about twenty-five times what 150 spacers
take (9.4 s).

**The Popcorn Penguins' real parts.** These are the project's first measurements of real
parts: the eight parts of the robot of the Popcorn Penguins (FRC Team 6238) in
`tests/fixtures/frc-parts/` (printed and in use; 2,908 to 39,054 triangles, all
watertight, one shell each), on the plates of `tests/frc_parts.py`, each instance in the
orientation the Popcorn Penguins print it in. Measured with the pinned Orca 2.4.2
and the default set (H2S, 0.6 mm nozzle, PETG), supports off unless the table says on, one
slice at a time through `service.slice_plate_configuration`, on an aarch64 Linux machine
with 4 CPUs (peak: the watchdog's reading of Orca's processes, in MB of 1,024 kB as the
kernel counts and as the ceiling is set; time: Orca's own run; sliced file in millions of
bytes). The parts alone: three slices each on Fri 2026-11-20 between 17:12 and 18:01 PT at a
load under 1. The other plates: three slices each (four for the plates with supports on and
for the Popcorn Penguins' target) on Fri 2026-11-20 between 18:36 and 18:47 PT at a load of 1 to 3:

| Plate | Instances | Supports | Peak (MB) | Orca's time (s) | Sliced file (MB) | Print time, filament |
|---|---|---|---|---|---|---|
| Clamp Plate Inner alone | 1 | off | 117 to 118 | 1.0 to 1.3 | 0.16 | 18 min, 7.8 g |
| Elevator Block Bottom Inner alone | 1 | off | 216 to 218 | 1.4 to 1.5 | 1.10 | 1 h 56 min, 64.0 g |
| Elevator Block Carriage alone | 1 | off | 181 to 182 | 1.1 to 1.4 | 0.64 | 1 h 7 min, 39.7 g |
| Elevator Block Top alone | 1 | off | 210 to 212 | 1.3 to 1.4 | 0.91 | 1 h 22 min, 50.2 g |
| Elevator Top Inner alone | 1 | off | 128 to 129 | 0.6 to 0.7 | 0.41 | 45 min, 26.6 g |
| Inner Spacer alone | 1 | off | 97 | 0.1 | 0.08 | 11 min, 3.8 g |
| Outer Clamp alone | 1 | off | 120 to 121 | 0.9 to 1.1 | 0.17 | 18 min, 8.2 g |
| Pulley v3 alone | 1 | off | 116 to 117 | 0.5 to 0.6 | 0.11 | 18 min, 2.2 g |
| mixed: one instance of each part | 8 | off | 504 to 513 | 7.4 to 7.7 | 3.70 | 5 h 21 min, 202 g |
| mixed | 8 | on | 753 to 761 | 9.4 to 12.8 | 4.69 | 6 h 25 min, 216 g |
| `team` (its name in `tests/frc_parts.py`): 2 blocks, 4 spacers, 3 outer clamps, 3 clamp plates, 4 pulleys | 16 | off | 503 to 510 | 11.0 to 12.3 | 2.91 | 4 h 11 min, 161 g |
| `team` | 16 | on | 609 to 613 | 12.0 to 15.2 | 3.34 | 4 h 38 min, 166 g |
| four-each-a: 2 of each part | 16 | off | 869 to 911 | 13.4 to 17.4 | 6.85 | 10 h 8 min, 403 g |
| four-each-a | 16 | on | 1,391 to 1,415 | 20.2 to 21.7 | 8.77 | 12 h 18 min, 431 g |
| four-each-b: four-each-a mirrored | 16 | off | 863 to 915 | 15.4 to 17.7 | 6.87 | 10 h 8 min, 403 g |
| four-each-b | 16 | on | 1,368 to 1,409 | 20.0 to 22.5 | 8.82 | 12 h 18 min, 431 g |

four-each-a and four-each-b are the Popcorn Penguins' target, 4 instances of every part
(32) on two H2S plates, every instance in its printing orientation and none turned; both
plates slice with supports off and with supports on. Each plate holds 2 instances of every
part, so the large blocks, which cost the memory, are shared out. On four-each-a two
columns of an Elevator Block Top, a Bottom Inner and a Carriage (231 mm deep of the 314 mm
the margins leave) stand with a pulley above each, and beside them two columns of an
Elevator Top Inner, a Clamp Plate Inner, an Outer Clamp and an Inner Spacer; four-each-b is
four-each-a mirrored left to right. Every gap is 13 to 14.2 mm, more than the 12 mm
supports need (see "Spacing" below). The first split put the twelve blocks on one plate,
6.5 to 10 mm apart in
columns 313 mm deep; Orca refused it with supports on, and the supports' spacing cannot fit
there (two Tops and two Bottom Inners in a column are 292 mm of footprints, plus three gaps
of 12 mm is 328 mm, over the 314 mm), so the split changed, not the target. The heaviest
target plate peaks at 1,415 MB with supports on, 585 MB under the default ceiling of
2,000 MB. Full plates of one part, supports off, one slice each on Fri 2026-11-20 between
17:12 and 18:01 PT, and the heaviest of them spaced for supports, measured with them on
(the full plates' gaps of 6 to 10 mm are refused with supports on, see "Spacing"):

| Plate | Instances | Supports | Peak (MB) | Orca's time (s) | Sliced file (MB) |
|---|---|---|---|---|---|
| Elevator Block Top, 3 x 3 | 9 | off | 1,015 | 12.8 | 7.19 |
| Elevator Block Bottom Inner, 3 x 4 | 12 | off | 1,410 | 19.1 | 10.8 |
| Elevator Block Bottom Inner, 3 x 4, 12.5 mm apart, at a 3,000 MB ceiling | 12 | on | 2,307 | 34.3 | 14.1 |
| Elevator Block Carriage, 3 x 5 | 15 | off | 1,333 | 17.7 | 8.04 |
| Elevator Top Inner, 5 x 5 | 25 | off | 895 | 13.9 | 8.28 |
| clamp plates, outer clamps and spacers, 6 x 5 | 30 | off | 502 | 19.9 | 3.19 |
| Pulley v3 | 25 | off | 583 | 13.7 | 1.89 |
| Pulley v3 | 50 | off | 1,074 | 27.3 | 3.68 |
| Pulley v3, 13 x 12 less 6 | 150 | off | over 2,500 (stopped) | | |

So twelve Bottom Inners with supports on and more than about 95 pulleys pass the 2,000 MB
ceiling: at the default ceiling the twelve Bottom Inners with supports on were stopped with
`slice.out_of_memory` in each of two slices (after 25.4 and 28.1 s), whose remedy is a
second plate. The ceiling was not raised for them (see "Sizing the host" below). Every check and
every slice above accepted every part, and every instance landed where it was placed: its
first-layer extrusions in the G-code lie within 0.47 mm of the part's own outline on the
plate (`tests_orca/test_frc_parts.py`; Orca's `bbox_objects` includes the auto brim, up to
15 mm wide at the blocks).

**Spacing.** Two instances' footprints must be `SPACING_MM` (5 mm) apart with supports
off and `SPACING_SUPPORTS_MM` (12 mm) with supports on; a plate closer than that is
refused before Orca runs (`slice.placement_too_close`, naming both instances; with
supports on the sentence says supports need the room). Measured with the pinned Orca and
the default set on Fri 2026-11-20 between 18:26 and 18:35 PT, pairs of the real parts side
by side or one behind the other, the placement check left out, one slice each:

- Supports off: every pair tried slices 1 mm apart (two Tops one behind the other, side by
  side, and turned 90°; two Bottom Inners; two Elevator Top Inners, also turned 90°; a Top
  with a Carriage behind it; two pulleys; a Clamp Plate Inner beside an Outer Clamp). 5 mm
  keeps 4 mm to spare.
- Supports on: Orca refuses some pairs with -101, its debug log saying "gcode path
  conflicts found between Elevator_Block_Top #2 and Elevator_Block_Top #1": their tree
  supports' paths meet. Two Tops one behind the other are refused at 5, 7 and 7.5 mm and
  slice at 8, 8.5, 9 and 11 mm; a Top with a Carriage behind it is refused at 5 to 7.5 mm
  and slices from 8 mm; two Elevator Top Inners side by side are refused at 5 to 8 mm and
  slice at 8.5 and 9 mm, one behind the other refused at 5 and 7 mm and slice from 8 mm.
  Every other pair tried slices 5 mm apart (Tops side by side, and turned 90°; Bottom
  Inners and Carriages both ways; a Top in front of a Bottom Inner; an Elevator Top Inner
  beside a Top; pulleys; clamps; a spacer). So 8.5 mm sliced every pair tried, and
  `SPACING_SUPPORTS_MM` is 12 mm, 3.5 mm more.

The upstream check slices the tightest pairs exactly the spacing apart, 12 mm with supports
on and 5 mm with them off (`test_the_placement_checks_spacing_is_enough_for_orca`), and
pins Orca's refusal of two Tops 5 mm apart with supports on and the log line that names
them (`test_orca_names_the_pair_whose_supports_meet`). The spacing was measured on these
parts at the default profiles; another part or setting may need more. When Orca still
refuses a plate for closeness (`slice.orca_too_close`), the report names the pair from
Orca's debug log, says the supports are the likely cause when they are on, and offers
spreading the instances out (or Arrange), turning supports off, or a second plate. A user
interface that arranges the plate must leave `SPACING_SUPPORTS_MM` when supports are on
([plate-configuration.md](../contracts/plate-configuration.md)).

The warnings Orca gives for these parts are true, and none of the slice service's part
warnings is. Every block and the Elevator Top Inner warn "has floating cantilever": in the
printing orientation each has 2,200 to 3,700 mm2 of faces looking down over pockets and
holes, 1,425 to 1,440 mm2 of it one ceiling 1.7 mm above the plate, printed as bridges;
with supports on Orca no longer warns. The pulley warns "has floating regions": inside its
bore (radius 6.35 mm) a hub ring (radius 3.45 to 4.76 mm) starts 4.76 mm above the plate
with nothing under it, and joins the rest of the pulley only 0.8 mm higher, through a 45°
chamfer, so its first layers start in mid-air; the pulley is the same from either flange,
and on its rim it would need supports all round. The Popcorn Penguins printed all of them
as they are.

**The same plate, sliced again.** Orca's G-code is not byte-identical between slices of
the same plate, on any number of CPUs. What varies:

- Fields that change in every slice: the time stamp in the G-code's second line, the
  object ids in its `; printing object ... id:` comments (a memory address), the G-code's
  checksum (`Metadata/plate_1.gcode.md5`), and in `Metadata/slice_info.config` the
  `first_layer_time` (uninitialised memory: 0.000000 in one slice,
  307348170571033591697770805198848.000000 in the next) and the `prediction` (by a second
  or so). In some slices the order of the objects in `Metadata/model_settings.config`.
- The extrusions themselves: Orca's threads order and split them differently from slice
  to slice. Between two separate slices, apart from the fields above, 6,254 to 13,236 of
  four-each-a's 1,063,416 G-code lines changed with supports on (2,931 to 8,965 of them
  extruding moves), 7,907 to 8,872 of its 755,749 with supports off, 4,273 to 4,922 of
  four-each-b's 755,607 with supports off, 1,600 to 7,059 of the mixed plate's 384,804 with
  supports off and 1,154 to 5,861 of its 537,216 with supports on (two pairs of slices
  each, Fri 2026-11-20).
- Pinning Orca to one CPU (`taskset`) does not remove it: of three runs of a test that
  compared two such slices of the mixed plate on one CPU, one found 1,085 lines different
  (the print time by 1 s), so that test was removed.

The slice service hands Orca the same plate 3MF every time: the fast suite writes one plate
configuration twice and compares the entries byte for byte
(`test_the_slice_service_hands_orca_the_same_plate_every_time`), so the variation is
Orca's. What is stable, and tested on every run of the upstream check for every plate it
slices (`test_the_real_parts_slice_through_the_http_interface`): the summary (the layers
exactly; the print time and the filament within 2 % of the measured values, which they
kept to within 5 s and 0.01 g in every slice measured), the warnings (exactly the true
ones, the same list every time) and the placements (every instance's first layer within
1 mm of its outline, 0.47 mm measured). The prints are the same; the bytes are not.

**The cost of the largest plate to the slice service.** The largest plate configuration
every check accepts has `MAX_INSTANCES` (150) instances of parts at `MAX_PART_TRIANGLES`
(22.5 million triangles in all). The slice service writes its plate 3MF before Orca
starts, part by part, holding one part's mesh text at a time, so the write and Orca never
run at the same time and the number of different parts adds disk, not memory. Measured
through the HTTP interface with a stand-in for Orca (no Orca run), on an aarch64 Linux
machine with 4 CPUs at a load of about 1, each figure from a freshly started service
(resident peak: its `VmHWM`, the checks of the upload included; the first and third rows
were measured before `serve` capped its malloc arenas):

| Plate configuration | `POST` | Plate write | Slice job's folder | Service's resident peak |
|---|---|---|---|---|
| 150 instances of one 149,760-triangle hub | 1.8 s | 24 s | 269 MB (7.5 MB upload, 261 MB plate 3MF) | 207 MB |
| 150 instances over 25 different such hubs, 6 instances each | 5.8 s | 28 s | 448 MB (187 MB uploads, 261 MB plate 3MF) | 178 to 233 MB over the fresh processes measured; 183 and 199 MB with the arena cap below |
| three of the 25-hub plate configurations, sent at the same moment | 9 to 12 s | 28 s (one at a time) | 823 MB in all (the first's plate 3MF beside three sets of uploads) | 276 MB |

The service's resident memory stays near its peak while Orca runs (Python keeps what it
has used), and its peak creeps upwards as one slice service process serves plate after
plate. Measured with the same stand-in, the 25-hub plate sent 16 times in a row to one
`serve` process, each slice job cancelled once the stand-in had started (aarch64 Linux,
4 CPUs, load about 1):

| `serve` process | Peak on its first plate | Peak after 13 plates | Peak after 16 plates |
|---|---|---|---|
| glibc's malloc arenas capped at 2 (what `serve` does) | 199 MB | 251 MB | 261 MB |
| no cap (glibc's default, up to 8 arenas per CPU) | 178 MB | 360 MB | 365 MB |

Each thread that allocates gets a malloc arena of its own, and an arena keeps what the
plate write freed; a new thread serves every request and every slice job, so the uncapped
process filled one arena after another. `serve` calls `mallopt(M_ARENA_MAX, 2)` before it
listens (`__main__.cap_malloc_arenas`; on a C library without `mallopt`, such as macOS's,
it does nothing). With the cap the peak still rises, by about 4 MB a plate from the 8th
plate to the 16th; the cause of that rest was not found. The table's 261 MB is the largest
measured; the host is sized for 400 MB of the service (see "Sizing the host" below). Before
the write held only one part's mesh text, the 25-hub plate peaked at 438 MB on a fresh
process.

**The memory watchdog** is the guard on memory. While Orca runs, a thread of the slice
service samples Orca's whole process group (`slicer.group_memory_kb`, from
`/proc/<pid>/stat` and `/proc/<pid>/status`) at once, then every `MEMORY_SAMPLE_S`
(0.25 s), and at once after each progress message of Orca's. Each sample reads every
process's current resident memory (`VmRSS`) and the kernel's high-water mark of it
(`VmHWM`, its peak since the process started), summed over the group. The pinned Orca's
memory peaks in spikes shorter than 0.1 s near the end of a slice, while it writes the
sliced file, which a reading of the current figure misses most of the time; the high-water
mark keeps the spike, and the sample after "All done, Success" (sent once the file is
written, about 30 ms before Orca exits) reads it. When a sample's peak passes the memory
ceiling, the setting `PENGUIN_SLICE_MAX_PEAK_MB` (2,000 MB by default), the watchdog stops
Orca as a cancel does (SIGTERM to the group, SIGKILL after the grace time) and the slice
fails with `slice.out_of_memory`: "This plate is too large to slice: the slicer needed
more than the 2,000 MB of memory the print server allows.", with the peak, where it was read
and the ceiling in the detail. A slice is reported out of memory only on that stop, on a
kill with the kernel's `oom_kill` count (cgroup `memory.events`) risen, or when Orca
prints `bad_alloc`; a kill with neither is `slice.orca_killed`.

**The peak in the log** (`peak_rss_kb` in the log, the detail, the note) is the watchdog's
highest reading of Orca's processes alone. The kernel's `ru_maxrss` of Orca at exit is not
used: it survives `fork` and `exec`, so it starts at the slice service's own resident
memory at the moment it starts Orca (a service holding 400 MB once reported a peak of
440,216 kB for `/bin/true`). The limitation: a spike that comes after the last sample, in
an Orca that ends by itself between two samples with no progress message after the spike
(a failure, typically), is not seen, so the peak logged for such a slice can be under
Orca's true peak. The real-Orca suite checks that on a good slice the watchdog's reading
reaches Orca's own `ru_maxrss`.

**What the ceiling guarantees.** The ceiling protects the server from a slice that keeps
growing; it is not a promise that no delivered slice ever touched it. A plate whose peak is
over the ceiling may be stopped with `slice.out_of_memory`, or may finish and be delivered
with a note, depending on timing: the same plate configuration sent twice can get the two
answers. It is never silent. A complete sliced file is never discarded by the watchdog: if
Orca has written it before the watchdog's sample stops Orca (Orca exits by itself, or the
watchdog's SIGTERM ends Orca after the file is complete; see "How a slice ends"), the
sliced file is delivered even though the peak is over the ceiling. The slice job's result
and its `done` log line then carry `memory_note` ("Orca's processes reached a peak of ...
kB (the watchdog's high-water reading of Orca's processes), over the ceiling of ... kB
(PENGUIN_SLICE_MAX_PEAK_MB=...), and Orca finished before the watchdog stopped it: the
sliced file is delivered", or "... and the watchdog stopped Orca only after it had written
the complete sliced file: ..."), so support can see it. Where the kernel's own limit is
lower than the ceiling the kernel acts first.

**Sizing the host.** So the ceiling does not bound Orca's memory: the watchdog reads it
every 0.25 s, Orca can pass the ceiling by as much as it grows between two readings before
it is stopped, and a plate that passes it in its last moments is delivered above it.
Measured with the pinned Orca on Fri 2026-11-20 between 18:36 and 18:47 PT, in MB of
1,024 kB (the ceiling's 2,000 MB is 2,048,000 kB):

- At the default ceiling the twelve Bottom Inners with supports on (see "The Popcorn
  Penguins' real parts") were stopped at readings of 2,144,504 and 2,226,800 kB, 94 and 175 MB over the
  ceiling (a review's slice of a like plate stopped at 2,140,316 kB).
- The largest rise of Orca's memory between two consecutive readings, over every plate of
  "The Popcorn Penguins' real parts" in both supports settings, was 514,268 kB (502 MB:
  1,347 to 1,861 MB in 0.26 s, on that plate); the target plates rose by up to 308 MB.
- So the worst measured is the ceiling plus one such rise: Orca at about 2,500 MB, beside
  the service's 400 MB, 2,900 MB.

A host gives the slice service 3.5 GB (3,584 MB) with the default ceiling, a fifth above
that worst case for what was not measured, and more for anything else on it (it was
1.3 GB with the 900 MB ceiling before Fri 2026-11-20). The ceiling stays at 2,000 MB:
every measured plate of the Popcorn Penguins' parts that they print, their target with
supports on included (1,415 MB at most), peaks well under it. The plates over it (twelve Bottom Inners with
supports, about 95 pulleys or more) are stopped with a remedy of a second plate; raising
the ceiling for them would let Orca's worst case pass the 2.5 GB the 5 GB test machine
allows one Orca.

Measured on an aarch64 Linux machine with the pinned Orca, one slice at a time, before
the sample after each progress message existed (the peaks were then the higher of the
watchdog's reading and `ru_maxrss`):

- 12 hubs of 20,000 triangles (peak 442 to 459 MB): six slices at a ceiling of 426 MB, 5 %
  under the peak, were all stopped with `slice.out_of_memory`, each reporting a high-water
  reading equal to Orca's `ru_maxrss`, while the highest current figure the same samples
  read was 362 to 380 MB.
- 6 hubs of 20,000 triangles (four free slices peaked at 265,540 to 269,336 kB): at
  ceilings 10 %, 3 % and 0.5 % under the lowest peak, 9 of 12 slices were stopped and 3
  delivered with the note; at ceilings 0.5 %, 3 % and 10 % over the highest peak, 12 of 12
  were delivered with no note. This plate's memory rises from about 210 MB to about 270 MB
  in its last 150 ms, while Orca writes the sliced file, so whether a 0.25 s sample lands
  before Orca exits is chance.

The real-Orca suite runs a real slice with a ceiling of 100 MB to show the stop, and a
slice at a ceiling 5 % under the plate's own peak to show the high-water reading (stopped,
or delivered with the note).

**How a slice ends** is decided in one place, `slicer.settle`, in this order:

1. A complete sliced file is never discarded by a stop the slice service decides on
   itself. When Orca exited 0, or was stopped for a timeout or by the watchdog, and its
   sliced file is complete, the slice succeeds. Complete means, for a normal success and
   after a stop alike: the file is there under its final name (Orca writes
   `plate.gcode.3mf.tmp` and renames it once written); it opens as a zip, which needs the
   end-of-central-directory record and the central directory, the last bytes written, so
   a file cut anywhere fails; the G-code header reads; it has `Metadata/plate_1.gcode`
   and, for a plate, `Metadata/plate_1.json`; and every entry decompresses and matches
   its CRC-32. Then the name guard checks every instance is in it, as for any slice. A
   stop that reached Orca is recorded in the slice job's result and its `done` log line as
   `stop_note` ("stopped by the slice service (timeout) with SIGTERM after 2.36 s, after
   Orca had written the complete sliced file (...): the sliced file is delivered", and
   "Orca had not written result.json, so its warnings are only those its debug log held by then" when that
   is so). With the real Orca the moment between writing the file and exiting is about
   30 ms; the real-Orca suite holds Orca there and asks a timeout and a watchdog stop.
2. A stop the slice service sent and that ended Orca: `slice.timeout`,
   `slice.out_of_memory`, or `cancelled`. A cancel (a replacement, a shutdown, a
   requested cancel) discards even a complete file. A stop is sent only while Orca is
   still running (checked with `waitid`, without reaping Orca, before the SIGTERM, so a
   stop asked after Orca ended by itself is never sent or reported); of two, the first
   reason asked is the one reported.
3. Orca's own ending: its error report. A stop that was sent but is not what ended Orca
   is reported this way too, and named only in the detail: when the slice service sent
   only SIGTERM and Orca ended on another signal (someone else's SIGKILL, a crash: "the
   slice service had asked it to stop (timeout) and sent SIGTERM, which is not what ended
   it"), or when Orca was already ending as the stop was asked (`slicer.orca_dying`, read
   from `/proc/<pid>/status` and `stat` just before the SIGTERM: a zombie, in exit, writing
   a core file, or with a signal pending that will end it: "it was already ending when the
   slice service asked it to stop (timeout)"). So someone else's kill is
   `slice.orca_killed` (or `slice.out_of_memory` on the kernel's count) and a crash
   `slice.orca_crashed`, never `slice.timeout`. A stop the slice service escalated to
   SIGKILL is the stop.

A cancel is applied by the job pool as well, so a cancel that reaches Orca just after it
exited by itself still ends `cancelled`, its file discarded: see "Cancelling" below.

**The memory model** in [plate-configuration.md](../contracts/plate-configuration.md),
"Memory", estimates Orca's peak from the parts' volume and the instances, with a factor for
supports. It is rough, so it only goes into the log lines of each slice job
(`estimated_peak_mb`, beside `memory_ceiling_mb`). It is wrong both ways on plates unlike
those it was fitted to: one 100 mm solid cube is estimated at 1,158 MB and slices at
269 MB (it would have been refused); the corpus' tower stand-in scaled 6 times (120 mm,
not watertight, so its bounding box of 1,746 cm3 stands in for its volume) is estimated at
1,893 MB; and 25 hubs of 20,000 triangles are estimated at 792 MB and peak at 842 MB,
because the model ignores triangles. The 100 spacers are estimated at 507 MB, close to
their measured peak. Refitting it belongs with the choice of hosting, on that host's
measurements. It was fitted as the upper envelope of these measurements
(`scripts/measure_plate.py --fit` reprints it), peak resident memory of Orca from `wait4`,
one slice at a time on an aarch64 Linux machine with 4 CPUs, pinned Orca 2.4.2, the
default set (the figures of these eight plates are the builder's; no review measured them
again):

| Plate | Instances | Volume (cm3) | Supports | Peak (MB) | Estimate (MB) | Seconds | Sliced file (MB) |
|---|---|---|---|---|---|---|---|
| mechanism (2 hubs, 4 tubes, 2 gussets, a block) | 9 | 268.5 | off | 312 | 461 | 2.6 | 1.1 |
| mechanism, supports | 9 | 268.5 | on | 309 | 646 | 2.8 | 1.1 |
| full-small (25 hubs of 12,000 triangles) | 25 | 554.6 | off | 781 | 791 | 9.9 | 5.4 |
| organic-1 (a lumpy body 110 x 90 x 100 mm) | 1 | 466.1 | off | 345 | 632 | 3.0 | 3.9 |
| organic-1, supports | 1 | 466.1 | on | 381 | 885 | 3.3 | 4.2 |
| organic-2 | 2 | 932.2 | off | 591 | 1,094 | 5.4 | 6.7 |
| organic-3 | 3 | 1,398.2 | off | 825 | 1,556 | 8.1 | 9.4 |
| organic-3, supports | 3 | 1,398.2 | on | 915 | 2,179 | 10.7 | 10.1 |

The fit also takes nine plates measured on another aarch64 machine in an earlier
investigation of plate limits (1, 2, 4 and 6 Stanford bunnies of 112,402 triangles and
279.6 cm3 each, with supports off: 367, 711, 1,281 and 1,739 MB; 2, 4 and 6 with supports
on: 1,012, 1,752 and 2,569 MB; 25 hubs: 786 MB; 2 hubs of 150,000 triangles: 218 MB).
They bind the envelope: the bunny costs about 1 MB per cm3, the smooth organic body about
0.5. The time model (`limits.estimate_seconds`, for `expected_s`) has the same shape and
is within about a factor of two of every plate above; it over-estimates the 100 spacers
five times (36 s for 7 s), since their cost per instance is small. The least-squares fit
(`MEMORY_BASE_MB` 73, `MEMORY_PER_INSTANCE_MB` 11.4, `MEMORY_PER_CM3_MB` 0.79, supports
1.29) under-estimates the bunny by up to 24%. To refit after more measurements:

```
uv run --project slice python slice/scripts/measure_plate.py --list
uv run --project slice python slice/scripts/measure_plate.py --plate organic-3 --out results.jsonl
uv run --project slice python slice/scripts/measure_plate.py --fit results.jsonl
```

The script slices under the memory watchdog with a ceiling of 3 GB (`MEASURE_STOP_MB`)
and records a plate stopped there as `over`.

## Progress, cancellation and cleanup

`jobs.JobPool` runs slice jobs one at a time (`MAX_RUNNING`), with at most `MAX_QUEUED`
waiting; a further one is refused with `slice.busy` (see
[A plate's slice jobs: repeats, replacement and the places](#a-plates-slice-jobs-repeats-replacement-and-the-places)).
Each slice job's latest progress report is kept with a `sequence` that rises by one with
every report; a follower that connects late gets it at once. The stages, in order:

| Stage | Words | Fraction |
|---|---|---|
| `queued` | Waiting for the slicer | none |
| `building_plate` | Building the plate | none |
| `slicing` | Slicing the plate | none |
| `loading` | Loading the plate | Orca's |
| `preparing` | Preparing to slice | Orca's |
| `slicing_mesh` | Slicing the parts into layers | Orca's |
| `generating_walls` | Generating walls | Orca's |
| `generating_infill` | Generating infill | Orca's |
| `generating_supports` | Checking and generating supports | Orca's |
| `optimizing_toolpath` | Optimizing the toolpath | Orca's |
| `generating_gcode` | Generating G-code | Orca's |
| `exporting` | Writing the sliced file | Orca's |
| `reading_result` | Reading the sliced file | none |

`slicing` is the slice service's own: it is sent the moment Orca has started, before Orca
says anything, so an Orca whose pipe stays silent (one stalled while loading, or a new
release that changes `--pipe`) is not shown as still building the plate. Orca's own
messages then refine it. Checking the parts happens before a slice job exists, when the
plate configuration arrives. Every report carries `elapsed_s` and `expected_s`, the time
model's estimate from the plate's volume, instances and supports
(`limits.estimate_seconds`). The final states are `done`, `failed` (with the error report)
and `cancelled` (ended early, with `cancel_reason`). A `cancelled` report keeps the `stage`
and `stage_label` it was ended at, as
[the contract's example](../contracts/examples/progress-report-replaced.json) does; a
`done` or `failed` one carries no stage.

**How many are ahead.** Every `queued` report carries `ahead`
([the contract](../contracts/progress-report.md#fields)): the slice jobs running and those
waiting before it, over every user key, in the order they were accepted, which is the order
they run: each `JobPool.submit` gives the executor one task, `JobPool._run_next`, which
starts the oldest waiting slice job rather than its own, so two submits that reach the
executor in the other order (it is called outside the pool's lock) still run in the order
accepted, and starting a slice job changes no count ahead. A task whose own slice job was
ended while waiting runs the next one, or nothing. A running slice job that is being
stopped counts as running, since it still holds the one Orca until Orca is gone. Whenever a
slice job ends, whether it ran or waited, the pool works out `ahead` again for every waiting one
(`JobPool._refresh_ahead`) and sends a new report (`sequence` plus one) to each whose count
changed, and to no other. No report but a `queued` one carries `ahead`. With one running and
two waiting, the waiting ones report 1 and 2; when the running one ends the first reports
0 and the last 1, and when the first starts the last stays at 1. The stage words stay
("Waiting for the slicer").

**Ending a slice job early.** `JobPool.cancel(job, reason)` ends a slice job early with one
of `jobs.CANCEL_REASONS`, which its `cancelled` report carries as `cancel_reason` and its
`cancelling` and `cancelled` log lines as `cancel_reason` too: `replaced` (the same plate's
later slice job, see below), `shutdown` (a waiting one at `JobPool.stop`, the running one at
`JobPool.shutdown`) or `requested`
(`DELETE /slices/<job>`, kept as built, which no component of PenguinSlicer sends). A slice
job keeps the first reason it was given. A worker that ends with `SliceCancelled` without
the pool having asked (which nothing does) is reported with `requested`, so a `cancelled`
report never lacks its reason; no other report carries one. A queued slice job is ended at
once. A running one that is still
writing its plate 3MF (`building_plate`) stops at the next object it writes: the write
looks at the stop before each part's mesh and each instance's object, and once it is set
ends with `cancelled`, never starts Orca, and its files are removed; the same holds for a
replacement and a shutdown during the write. On the largest plate (150 instances of a hub
at `MAX_PART_TRIANGLES`, one part or 25), `cancelled` came 0.05 to 0.17 s after the
`DELETE`, at any moment of the 24 to 28 s write. Orca is also never started for a slice job
whose stop is already set (`slicer._run_orca` looks first). A running one whose Orca has
started is reported
`cancelled` only after its Orca and every child are gone, or `failed` when it had already
failed (a watchdog stop or a timeout asked first is the one reported, and so is a crash or
someone else's kill that ended Orca before the cancel's SIGTERM could). Ending a slice job
early before its final report always discards the sliced file, even one Orca finished at
the same instant (a replaced slice is of a plate that has since changed; the `cancelled`
log line names the file in `file_discarded`); ending a finished slice job changes nothing
and answers `finished`; an unknown slice job answers `unknown`; ending one twice answers
`cancelling` twice and is logged once.

**Going on without its page.** Once accepted, a slice job runs to its end whether or not
anything follows its progress stream: following one, or ceasing to, changes nothing about
it (`JobPool.follow` counts no followers), and the sweep only drops expired records. A slice
whose user never returns holds the one Orca until it ends, which the time limit bounds; the
front server follows every unfinished slice job itself and collects its sliced file.

**Cleanup.** Scratch folders are removed on every way out (success,
failure, timeout, cancel); at start the HTTP interface removes the scratch of any process
that is no longer running (`service.clean_stale_scratch`: the folder name carries the
process id and its start time, so a reused process id is not mistaken for the living one).
A running slice job's record never expires.

**Remembered for two hours; the sliced file deleted once stored.** Item 10 of
[Phase 2](#phase-2-one-machine), built ([Go on without the page](README.md#go-on-without-the-page)).
A final slice job's record, with its `plate_id` and `submission_id`, is kept for two hours
(`jobs.RECORD_TTL_S`, 7,200 s) after its final report, with the moment it ended on the wall
clock (`ended_at`, see "The list of slice jobs" below); the sweeper
(`JobPool.start_sweeper`, every `SWEEP_INTERVAL_S`, 10 s) drops it at 7,200 s with its
folder, and a repeat of its submission is recognised for as long. A sliced plate's job gives
up its hold on its parts as soon as the plate is sliced (`web.slice_worker` removes its
`parts/`), so only its sliced file stays. Once the front server has stored the sliced file it
says so with
[`DELETE /slices/<job>/file`](../contracts/slice-http-interface.md#delete-slicesjobfile--stored-delete-your-copy):
`JobPool.delete_file` marks the record and the route deletes the slice service's copy at
once, answering `200` `{"job", "file": "deleted"}`
([the contract's example](../contracts/examples/slice-http/file-deleted.json)); the record
stays until it expires, its progress report is still served, and the file and the summary
answer `slice.file_gone` (HTTP 410). A second delete answers as the first, as does a delete
on a slice job that ended without a sliced file; a delete on a slice job waiting or running
is `slice.not_ready` (HTTP 409); on an unknown slice job or another user key's,
`slice.unknown_job`. A file the disk refuses to remove is logged
(`slice_file_delete_error`) and goes with the folder when the record expires; the delete
still answers `200`. A sliced file never collected goes with its record. The fake clock of
the tests moves both the pool's clock and the sweeper's intervals (`helpers.ManualTicks`),
so no test waits a duration (tests: `tests/test_jobs.py` `TestRememberedForTwoHours`,
`TestSweeperAndShutdown`; `tests/test_web.py` `TestTheSlicedFileOnceStored`).

A stop (`JobPool.stop`) ends every waiting slice job and refuses new ones; shutdown
(`JobPool.shutdown`, a second stop and the end of `serve`) cancels every slice job and waits
for every worker (see [Asked to stop](#asked-to-stop)).

**The list of slice jobs.** Item 11 of [Phase 2](#phase-2-one-machine), built ([Go on without the page](README.md#go-on-without-the-page)).
[`GET /slices`](../contracts/slice-http-interface.md#get-slices--every-slice-job) answers
`200` `{"slices": [...]}` (`JobPool.listing`): every slice job the slice service process
remembers, waiting, running or ended, of every user key, in the order accepted, each entry
`job`, `user_key` (as the request carried it), `plate_id`, `submission_id`, `progress` (its
latest report), `file_on_disk` (`true` while a done slice job's sliced file has not been
deleted by `DELETE /slices/<job>/file`; `false` before it is done and for one that did not
end `done`) and `ended_at` (the wall clock's moment of its final report, RFC 3339 in UTC to
the second, `null` while it waits or runs; the pool's `wall_clock`, `time.time` unless a
test gives its own). It answers for the whole slice service, so the user key is not looked
at, and a newly started process answers an empty list. A restarted front server uses it to
find the slices it must still follow or collect, and takes `ended_at` as the sliced file's
`slice_ended_at`. Tests: `tests/test_jobs.py` `TestTheList` (a queued, a running, a done, a
failed and a cancelled slice job, the three ended with the fake clock's moments; an empty
pool; a deleted file not on disk; an expired slice job gone) and `tests/test_web.py`
`TestTheListOfSliceJobs` (the shape of
[the contract's example](../contracts/examples/slice-http/slices-list.json), a new process's
empty list).

**The log.** One JSON line per slice job transition (`queued`, `running`, `cancelling`,
`done`, `failed`, `cancelled`, `file_deleted`, `expired`), `{"event": "slice_job", ...}`, carrying the job
id, the user key (cut to 200 characters), the `plate_id` and `submission_id`, the printer,
filament, process, overrides and whether supports are on, the memory and time estimates,
every part with its hash, units, triangles, size, volume, watertightness, shells, open
edges and warnings, every instance with its name, orientation or rotation, angle and position, and on
a final state the error code, the error report's detail, Orca's reason, Orca's peak memory
(and `memory_note` when a delivered slice's peak passed the ceiling, `stop_note` when a
stop reached Orca after its sliced file was complete, `cancel_reason`, and
`file_discarded` when a cancel threw away a finished sliced file), Orca's wall time and
the slice job's wall time. The log sink is called through `jobs.SafeLog`, the one place a
failing sink (a closed or broken stderr under `serve`) is caught: the failure is counted
(`JobPool.log_failures()`; the HTTP interface has no health answer to show it in) and
never changes what a slice job or an answer does. A plate configuration refused before
any slice job exists for it leaves one line too, with `"state": "refused"`: every answer of `POST /slices` that
is not 202 (no user key, a check that refused it, parts missing from the part store, a body
that is not JSON, is multipart or is too large, a full queue, a full disk while its parts
are held, a work folder that cannot be written, a bug) carries `user_key`, `http_status`,
`error_code`, `error_detail`, `parts` (each part's key, name, `sha256` and `units`, as the
plate configuration named them, when it could be read) and `bytes` (its Content-Length).
Every upload of a part leaves one line, `{"event": "part_upload", ...}`, with `state`
`stored`, `stored_again` (the same bytes again) or `refused`, the `user_key`, `units`,
`bytes`, `http_status`, and the `sha256`, triangles, size and warning codes of a part kept
or the `error_code` and `error_detail` of a refusal. A request without the user key, and a
request about another user key's slice job, leave a line `{"event": "slice_http_refused",
...}` with the path, the job, the user key, the status and the code. A repeated submission
leaves one line `{"event": "slice_repeat", ...}` with the `job` it was answered with, the
`user_key`, `plate_id`, `submission_id`, `http_status` 202 and that slice job's `state`. No
payload, path of the caller or environment variable is logged.

**The log the front server collects.** Item 16 of [Phase 2](#phase-2-one-machine), built
([The log](README.md#the-log)). The slice service holds no credential to store its log, so
every line goes into a buffer in memory (`log_buffer.LogBuffer`, the log sink `create_app`
gives the pool and the routes, through `jobs.SafeLog`) from which the front server fetches
it with [`GET /log?after=<n>`](../contracts/slice-http-interface.md#get-logaftern). The buffer
numbers each line from 1 (`n`), stamps it with `time` (the wall clock, UTC, RFC 3339 to the
millisecond, `2026-11-27T22:13:05.412Z`) and `"component": "slice"`, puts those three first,
keeps a value JSON cannot hold as its words, keeps the most recent 10,000 lines
(`log_buffer.LOG_BUFFER_LINES`, *proposed* and settled at that figure), and passes each line
on to its sink: under `serve`, one JSON line on stderr, so a line dropped from a full buffer is
still in the process's output. The answer is `200` `{process, lines, dropped, more}`: the
lines numbered after `after`, oldest first, at most 1,000 (`log_buffer.LOG_ANSWER_LINES`);
`process`, `p` and 8 random hexadecimal characters made when the process starts, so that a
restarted process, which numbers from 1 again, is told apart; `dropped`, how many lines after
`after` the buffer no longer holds; and `more`, whether lines remain after the last one in
`lines`. `after` left out is 0; any run of ASCII digits is a whole number, leading zeros
dropped, and one of more than 18 digits (`web.AFTER_DIGITS`), past any line a process
writes, is read as eighteen nines; one that is not ASCII digits (`-1`, `+1`, `1.5`, `²`, empty)
is refused `400` `slice.bad_request` ("The slicer was asked for its log after a line that is
not a whole number."). The route answers for the whole slice service and does not look at the
user key. Every line about a request carries the user key the request carried (`user_key`,
cut to 200 characters, `null` on a request without one), and every line about a slice job its
`job`, a failed cleanup's (`slice_cleanup_error`) among them. A buffer or a sink that fails is
counted by `SafeLog` and never changes an answer; a buffer that cannot be read answers `500`
`slice.unexpected`. The front server adds the group as it gathers. Tests
(`tests/test_log_buffer.py`): lines in order and only those after the number passed; 1,001
lines over two answers with `more`; a full buffer that drops the oldest and counts them; the
time from the fake clock, the component and the user key of each request's line, over
uploads, submissions, a repeat, refusals and a slice job's transitions; a new process's new
`process` and numbering; a failing buffer that changes no answer; the shape of
[the contract's example](../contracts/examples/slice-http/log.json).

### A plate's slice jobs: repeats, replacement and the places

Item 7 of [Phase 2](#phase-2-one-machine), built ([Run one slice at a time, and let a few wait](README.md#run-one-slice-at-a-time-and-let-a-few-wait),
[A plate configuration submitted twice](README.md#a-plate-configuration-submitted-twice);
[The plate and the submission](../contracts/plate-configuration.md#the-plate-and-the-submission)).
[D97, D98, D295]

**The places.** One slice job running and two waiting (`jobs.MAX_RUNNING`, `jobs.MAX_QUEUED`)
are the slice service's three places, counted together over every user key: nothing limits
the slice jobs of one user key. A slice job holds a place from its acceptance until it ends
or is asked to end early; one being stopped holds none, though its Orca may run on for the
moment it takes to stop (it still counts in `ahead`). A plate configuration that finds every
place taken is refused `slice.busy` (HTTP 503, retryable, "The slicer is busy, try again in a
minute.").

**The order.** `POST /slices` handles a plate configuration in this order:

1. **A repeat.** When the body is a JSON object whose `submission_id` is a string, and the
   user key and that `submission_id` are those of a slice job the slice service remembers
   (`JobPool.remembered`, for as long as the record lasts), the answer is 202 with that slice
   job, `{job, plate_id, submission_id, progress, part_warnings}` exactly as when it was
   accepted but with its latest progress report, before any check: it starts nothing,
   replaces nothing, takes no place and adds no report to the slice job. A refused submission
   started no slice job, so its value is not remembered and is checked afresh when it comes
   again. One `submission_id` under two user keys is two submissions.
2. **A stopping slice service** answers `503` `slice.stopping` before any check (see
   [Asked to stop](#asked-to-stop)).
3. **The checks**, as in [The plate configuration in its phase 2 form](#the-plate-configuration-in-its-phase-2-form).
4. **The parts held** in a new folder for the slice job (`slice.scratch_unwritable`,
   `slice.part_missing` as there).
5. **The pool decides, under its lock** (`JobPool.submit(..., plate_id, submission_id)`):
   first the repeat again, since two attempts of one submission can pass the first look
   together (`jobs.RepeatedSubmission`: the second's folder is removed and it is answered as
   a repeat); then a stopping pool (`jobs.Stopping`, `slice.stopping`, see
   [Asked to stop](#asked-to-stop)); then the places, counting
   as given up the place of every earlier slice job of the same user key and `plate_id` that
   is still waiting or running; then **the replacement**: each such earlier slice job is
   ended early with `cancel_reason` `replaced` (a waiting one at once, its files removed; a
   running one through its stop, reported only once its work has stopped, its sliced file
   discarded), and the new slice job is queued behind every other. So a user who slices a
   changed plate while every place is taken is accepted, and a plate configuration refused
   at any step, `slice.busy` included, ends nothing. A slice job is never ended early on
   account of another plate's or another user key's.

Tests (`tests/test_jobs.py` `TestReplacement`, `TestRepeat`; `tests/test_web.py`
`TestReplacementAndRepeat`, `TestStopDuringThePlateWrite`): a later plate configuration of
the same plate ends the earlier one while queued, while building its plate and while a
hanging fake Orca runs, each with `cancel_reason` `replaced` only once the work has stopped
(the fake Orca's process gone); another plate of the same user key and another user key's
same `plate_id` are untouched; with every place taken by one user key's slice jobs a changed
plate is accepted and another plate refused `slice.busy`; a repeat answers the first
attempt's slice job and leaves its sequence of reports unbroken, before any check and with
every place taken; a repeat after the first was refused is checked afresh; one
`submission_id` under two user keys is two submissions; a refused change leaves the earlier
slice job as it was; the race of two attempts at once.

## Modules

| Module | What it holds |
|---|---|
| `web.py` | The HTTP interface, the one way in, and the user key on every request |
| `service.py` | Checking a part on arrival; reading and checking a plate configuration, slicing it, the sliced file, scratch folders |
| `part_store.py` | The part store: the user keys' folders, the two hours, the limit on disk, a slice job's hold on a part, the units' scales |
| `errors.py` | The adapter from every exception to an error report, and every code |
| `plate.py` | Orientations, instance placement and the rules a placement must pass |
| `mesh.py` | Reading a binary STL, the checks on its surface, the warnings, and a part's footprints |
| `plate_3mf.py` | The plate written as a 3MF for Orca, the sliced file's name, the name guard |
| `plate_configuration.py` | One checked plate configuration and its description for the log; the slice job's work on it (the plate 3MF, the Orca run, the name guard) |
| `print_config.py` | The profile catalog, the profile choice, the overrides written over the process profile and whether supports are on |
| `settings_table.py` | The table of settings (`settings/table.json`, with `settings/classification.json`) and the check of the overrides against it |
| `slicer.py` | Everything that runs Orca or reads what it writes |
| `jobs.py` | The job queue: the places, progress reports with the count ahead, ending early and its reason, the replacement and the repeat, expiry, the stop, the log lines of the slice jobs |
| `log_buffer.py` | The log lines kept for the front server to collect, numbered, with their time and component |
| `__main__.py` | `serve`: the server on a thread of its own, the stop signals and the order of the stop |
| `limits.py` | Every cap, the memory and time models, the memory ceiling setting, and the sentences that refuse them |

## Error codes

Every code the slice service produces, in the order of the checks. `tests/test_errors.py`
produces each one on purpose, through the code that really raises it, and states the
sentence, remedy, action, retryable flag and evidence its report must carry.

| Code | Stage | When |
|---|---|---|
| `slice.no_user_key` | checking | A request about a part or a slice job without `X-Penguin-User-Key`, or with an empty one (HTTP 400): a fault of the front server's. |
| `slice.bad_plate_configuration` | checking | The plate configuration is not JSON (or nested too deeply to read), is a multipart body, has a field that is not listed, or a part or instance lacks a field or has a bad value (no `plate_id` or `submission_id` of 1 to 64 letters, digits, `-` or `_`; a part without a `sha256` of 64 lowercase hexadecimal characters or without `units` `"mm"` or `"in"`; an instance with both or neither of `orientation` and `rotation`, or a `rotation` that is not 4 finite numbers of length 1 within 1e-6; a part `name` over 200 characters; a `printer`, `filament` or `process` name over 200 characters) (HTTP 400); or the body is over `MAX_PLATE_CONFIGURATION_BYTES` (HTTP 413, refused before it is read). No sentence, detail or log line grows with what a caller sends: a value it shows is cut to 120 characters, and a bug's own words to 2,000. |
| `slice.too_many_instances` | checking | More than `MAX_INSTANCES` instances. |
| `slice.too_many_parts` | checking | The instances use more than `MAX_PARTS` different parts. |
| `slice.unknown_printer` | checking | The printer is not in the catalog. |
| `slice.profiles_not_offered` | checking | The filament or process is not in the catalog, does not fit the printer, or is not the default set's. |
| `slice.bad_overrides` | checking | `overrides` is not an object, or names a setting the table of settings does not hold (programmatic, not offered, a filament or printer setting, a misspelling), or gives a value that does not fit its entry (see [Settings a plate configuration may replace](#settings-a-plate-configuration-may-replace)); the sentence names the first, the detail every one. |
| `slice.profile_unreadable` | checking | A profile file of the server's own (the catalog, a printer or process profile) is missing or not a profile; or its table of settings is ("The slicer could not read its table of settings.", HTTP 500 at `GET /settings-table`). |
| `slice.part_missing` | checking | Parts the plate configuration names are not in the part store under the request's user key, their `sha256` and their `units` (HTTP 422): one report lists every one in `where.missing_parts` (`key`, `sha256`, `units`, in the order of `parts`), with `action` `refresh_parts`, the remedy "Add the parts again and slice again." and the hashes and units in the detail. Also, without `missing_parts`: an instance names a part the plate configuration does not list; or a part's file goes away after the checks, before the plate is written. |
| `slice.bad_units` | checking | An upload whose `units` is missing or is neither `mm` nor `in` (HTTP 400). |
| `slice.part_unreadable` | checking | An uploaded part is empty, is not an STL (an image, a zip or 3MF, a gzip, text such as an HTML or JSON error page), is cut off or padded, has no triangles, or has coordinates that are not finite (HTTP 422). |
| `slice.part_not_binary` | checking | An uploaded part is an ASCII STL. |
| `slice.part_too_detailed` | checking | An upload whose Content-Length is over `MAX_PART_BYTES`, refused before its body is read, or whose STL is over `MAX_PART_TRIANGLES` (HTTP 413). |
| `slice.part_too_small` | checking | An uploaded part, in its units, is 0.1 mm or less in every direction, or flat in one. |
| `slice.part_no_volume` | checking | An uploaded part's triangles have no area, or none shares an edge with another, or its closed surface lies in one plane or encloses no volume (faces laid on top of each other). |
| `slice.part_too_large` | checking | An uploaded part, in its units, fits the largest printer of the profile catalog in no orientation; or, when a plate configuration names it, it fits that plate's printer in no orientation (`where.part` names it). |
| `slice.placement_off_plate` | checking | A footprint leaves the printable area less the margin. |
| `slice.placement_too_tall` | checking | An instance is taller than the printable height. |
| `slice.placement_too_close` | checking | Two footprints are closer than `SPACING_MM` (5 mm), or `SPACING_SUPPORTS_MM` (12 mm) with supports on (see "Spacing"). The report names both instances (`where`: `instance`, `other_instance`); with supports on the sentence says supports need the room, and the remedy also offers turning supports off. The detail lists at most 20 such problems. |
| `slice.busy` | queued | The job queue is full. |
| `slice.stopping` | queued | A new plate configuration after the slice service was asked to stop (HTTP 503, retryable): "The slicer is restarting.", the remedy "Your plate will be sliced as soon as the slicer is back.", exactly [the contract's example](../contracts/examples/slice-http/stopping.json). Never `slice.busy`. |
| `slice.scratch_unwritable` | building | The plate 3MF, the process file or Orca's folders cannot be written (a full disk, a folder where an earlier run's sliced file was), or the HTTP interface cannot make a slice job's folder in its work folder or hold its parts there, or the part store cannot keep an uploaded part (HTTP 500). The upload's report has its own sentence (`web.PART_STORE_UNWRITABLE_MESSAGE`) and remedy (add the part again in a few minutes, or the server needs more free disk space). |
| `slice.orca_missing` | slicing | No Orca at `PENGUIN_SLICE_ORCA` or `tools/orca`. |
| `slice.orca_unstartable` | slicing | Orca is there but will not start (not executable, another architecture), or exits 126 or 127 with no `result.json` (the loader could not load a library it needs). |
| `slice.timeout` | slicing | Orca took longer than `PLATE_SLICE_TIMEOUT_S`; the service stopped it, and the stop is what ended Orca, before its sliced file was complete. On a plate of one instance the remedy is to simplify or split the part, with no action. |
| `slice.cancelled` | slicing | The slice job was ended early (replaced, at shutdown, or by a requested cancel) and Orca is gone: the answer of its file and summary (HTTP 409). Its `cancelled` report itself carries no error report, only `cancel_reason`. |
| `slice.out_of_memory` | slicing | The memory watchdog stopped Orca at the memory ceiling before its sliced file was complete (the detail holds the measured peak); or Orca was killed and the cgroup's `oom_kill` count rose (the kernel's out-of-memory killer); or Orca printed `bad_alloc`. On a plate of one instance the remedy is to split or simplify the part, with no action. |
| `slice.orca_crashed` | slicing | Orca died on a signal that means it failed (SIGSEGV, SIGABRT, SIGBUS, SIGFPE, SIGILL, SIGTRAP, SIGSYS), also when a stop of the service's was asked at the same moment (the detail says so). |
| `slice.orca_killed` | slicing | Something else stopped Orca with a signal the service did not send (SIGKILL with the `oom_kill` count unchanged or unreadable, SIGTERM, SIGINT and the rest), also when a stop of the service's was asked at the same moment or Orca ignored the service's SIGTERM (the detail says so). |
| `slice.orca_too_close` | slicing | Orca's return code -101: Orca found that two instances' paths would meet, on a plate the placement check passed. The report names the pair from Orca's debug log when it is there (`where`: `instance`, `other_instance`; the detail lists up to 5 pairs); with supports on the sentence names the supports as the likely cause and the remedy offers turning supports off. The remedy always offers spreading the instances (or Arrange) and a new plate. |
| `slice.crosses_edge` | slicing | Orca's return code -52: an instance partly off the plate beside others on it. |
| `slice.empty_layers` | slicing | Orca refused empty layers with supports off: the report names the instance and the height, and offers `enable_supports`. |
| `slice.empty_layers_with_supports` | slicing | The same with supports on: the part must be repaired, no action. |
| `slice.no_layers` | slicing | Orca printed "No layers were detected." (an open or broken surface, a part too thin): repair in CAD. Names the part when the plate has one. |
| `slice.print_empty` | slicing | Orca printed "The print is empty." (a part thinner than the nozzle prints): check size and thickness. Names the part when the plate has one. |
| `slice.nothing_on_plate` | slicing | Orca's return code -50: no instance fully on the plate. |
| `slice.orca_failed` | slicing | Any other non-zero exit, -100 without a reason the service recognises, or a code it does not know; Orca's words are in the detail. When Orca's debug log holds warnings it reported while slicing, the sentence adds them, labelled as possibly unrelated ("It also warned, though this may not be why it failed: ..."). |
| `slice.rests_on_an_edge` | slicing | Orca's return code -100 with no reason the service recognises, on a plate where an instance touches the plate only along an edge or at a point (its part's own faces on the plate under 0.01 mm², and its section at the middle of the first layer nowhere as wide as one line of that layer), unless Orca's debug log warns of other instances only: the pinned Orca's reason, an empty first layer, reaches no file. The report names the first such instance (`where.instance`), the detail every one ("resting on no face of its own: ...") before Orca's words; the remedy lays the part on one of its own flat faces or turns on supports with a raft (with supports on, adds a raft); `action` `choose_orientation`. |
| `slice.no_output` | slicing | Orca exited 0 without writing the sliced file. |
| `slice.unreadable_output` | slicing | The sliced file is not a zip (also a directory entry asking for a zip version the reader does not know), an entry fails its checksum, a plate's sliced file has no `Metadata/plate_1.json`, or that entry has no list of objects. Worth retrying. |
| `slice.no_gcode` | slicing | The sliced file has no `Metadata/plate_1.gcode`. |
| `slice.left_off_plate` | slicing | Orca left an instance out of the sliced file. |
| `slice.output_unwritable` | saving | The slice job's folder for its sliced file (`out/` in its folder under the work folder) cannot be made or written, or a folder there already has the sliced file's name. |
| `slice.output_too_large` | saving | The sliced file is over `limits.MAX_SLICED_FILE_BYTES` (50 MB, 52,428,800 bytes), the third guard after a good slice: a `failed` report, retryable false, no action, the slice service's own sentence ("The sliced file of this plate is larger than the 50 MB a sliced file may be."), the remedy fewer instances or a new plate (on a plate of one instance, to split or simplify the part); the detail holds the file's size and the limit. |
| `slice.unknown_job` | fetching | The HTTP interface does not know the slice job (never, or expired, or accepted by another slice service process), or it is another user key's (answered exactly alike, and logged as a refusal). |
| `slice.not_ready` | fetching | The sliced file or summary of a slice job that has not finished, or `DELETE /slices/<job>/file` on one (HTTP 409). |
| `slice.file_gone` | fetching | The sliced file of a done slice job is no longer on the disk, or was deleted by `DELETE /slices/<job>/file` once the front server stored it (HTTP 410), for the file and the summary alike. |
| `slice.bad_request` | fetching | The HTTP interface does not offer that path (404) or that method on it (405), or an upload has no Content-Length (400), or an upload's body ends before its Content-Length (400, "This part did not arrive whole."). The upload's report has its own sentence (`web.NO_LENGTH_MESSAGE`) and remedy (add the part again, or the server needs fixing), a fault of the front server's. |
| `slice.unexpected` | slicing | Anything else: a bug in the slice service; the detail keeps the traceback. |

**A new plate.** Item 15 of [Phase 2](#phase-2-one-machine), built
([When things go wrong](README.md#when-things-go-wrong)). Every sentence whose remedy is
another plate says "a new plate", the words of the wizard's panel, never "a second plate":
the sentences and remedies of `slice.too_many_instances` and `slice.too_many_parts`
(`limits.TOO_MANY_INSTANCES_MESSAGE`, `limits.TOO_MANY_PARTS_MESSAGE`, `errors.CODES`), the
remedy of `slice.out_of_memory`, those of `slice.placement_too_close` and
`slice.orca_too_close` with supports off and on (`plate.TOO_CLOSE_REMEDY`,
`plate.TOO_CLOSE_SUPPORTS_REMEDY`), and that of `slice.output_too_large`. The old words for
people and "the print server" in other sentences stay: changing them is known future work
([Known future work](README.md#known-future-work)). Tests: no report of
`tests/test_errors.py` says "second plate", and exactly those six codes' remedies say "a new
plate" (`test_no_report_says_a_second_plate_and_another_plate_is_a_new_plate`).

**The remedies of an upload.** A part refused when it arrives (`POST /parts`) was never
added, and its report reaches the wizard's Parts step: its remedy is about adding the part
(export it again, simplify it, check its units, as the guide's "When things go wrong" says),
never about a slice, a mentor or the print server, and it carries no `action`. Every code
`POST /parts` can answer has its remedy in `service.UPLOAD_REMEDIES`: `service.check_part`
sets it on the part checks' `MeshError` and on a `ProfileError` of the server's own
profiles (whose upload sentence is `service.UPLOAD_PROFILE_UNREADABLE_MESSAGE`, "The slicer
could not read its printer settings, so it could not check this part."), and `web._for_upload`
sets it on every other answer of the route (no user key, no units, no Content-Length, a
Content-Length over the cap, a part store that cannot be written, a bug, and a body that
ends before its Content-Length, which Flask answers as a 400 and whose sentence is
`web.UPLOAD_NOT_WHOLE_MESSAGE`, "This part did not arrive whole.", under
`slice.bad_request`). `errors.CODES`
keeps the slice's remedies for the same codes, for a part read again for a plate.
`tests/test_errors.py` produces every one through the HTTP interface and asserts its remedy,
that it has no action, and that no remedy says mentor, print server or slice.

For a failure Orca reports, the detail holds Orca's code, the exit status, Orca's own
reasons (`error_string` and every `warning_message` from its `result.json`, the warnings
of its debug log) and the last lines Orca printed. For a signal it holds the signal and who
sent it, and a stop of the service's that was asked but did not end Orca.

## Taking a new upstream version

The slice service rests on Orca Slicer (the program and its profiles). The pin stays at
Orca 2.4.2. Taking 2.5.x is known future work: Orca 2.5.1 ships the Bambu Lab vendor
profiles packed in one opaque file, `BBL.opc`, which `scripts/flatten_orca_profiles.py`
cannot read yet, so the profiles cannot be regenerated from it (see the record below). A
patch to Orca is the owner's decision; `make upgrade-orca` stops when `patches/orca/`
holds one, because patching Orca means building it from source. To move to another
release:

```
make -C slice upgrade-orca VERSION=2.5.1
```

It reads the release from GitHub, takes GitHub's SHA-256 digest of each of the three
assets, and stops if `patches/orca/` holds a patch. It then fetches the release's source
into `tools/orca-source.next` (`scripts/fetch_orca_source.py`, trusting the download, whose
checksum becomes the new `SHA_SOURCE`: GitHub publishes none for a tag's archive) and
installs the release beside the installed one, in `tools/orca.next` (a staged copy of
`scripts/install-orca.sh` holding the new pin verifies the download), so a failed download
or checksum changes nothing. Only then does it rewrite the pin in `scripts/install-orca.sh`
(`ORCA_VERSION` and the four `SHA_` lines), move `tools/orca` to `tools/orca.previous` and
the new release into `tools/orca`, and the new source into `tools/orca-source`, regenerate
`profiles/` and `profiles/catalog/` from the new Orca's own profiles and the table of
settings from its source (`scripts/make_settings_table.py`, which stops naming every new
process setting nobody has classified: classify each in
`src/penguin_slice/settings/classification.json` and run `make settings-table`), and run the
upstream check, `make test-upstream` (`tests_orca/`: every test's docstring starts with
"Protects:" and names the behaviour it pins). When the check passes, `tools/orca.previous`
is removed. When it fails, the command stops with a message that says to read the failing
test's "Protects:" line and message for what to fix, and how to go back. Nothing is
committed.

Then look at:

- `git diff -- slice/src/penguin_slice/settings/`: settings that appeared in or left the
  table, and changed labels, ranges, choices and process values. A setting a new Orca adds
  is classified by the agent taking the version before the work is finished.
- `git diff -- slice/src/penguin_slice/profiles/`: values that changed in the default set
  (temperatures, speeds, `nozzle_volume`), profiles that appeared or went from the
  catalog, and `index.json`'s `skipped` list. A changed default set changes every slice.
- The upstream check's output. A failing test names the assumption that broke: a command
  line option, a return code or the wording `slicer.py` reads (`ORCA_RETURN_CODES`,
  `EMPTY_LAYER_RE`, `OBJECT_RE`, `OUT_OF_MEMORY_RE`, `ORCA_OUTPUT_REASONS`), a progress
  message `ORCA_STAGES` does not know, the sliced file's metadata, the placement, the
  catalog, or Orca's debug log: `test_orcas_reason_for_a_general_failure_is_read_from_its_debug_log`
  slices a part known to fail with only Orca's general reason and fails, saying "the debug
  log's format changed: fix slicer.LOG_WARNING_RE and tests/fake_orca.py's LOG_WARNING",
  when the warning is no longer found. Its output prints the error report; the new Orca's
  `orca.log` for that plate shows the new format. The log's line naming two instances too
  close together (`slicer.LOG_CONFLICT_RE`, `fake_orca.CONFLICT`) is pinned by
  `test_overlapping_instances_are_refused_by_orca` and
  `test_orca_names_the_pair_whose_supports_meet`, and the placement check's two spacings by
  `test_the_placement_checks_spacing_is_enough_for_orca`.

When a test fails, fix `slicer.py` (or the flattening script for the catalog) and its
fast-suite stand-in `tests/fake_orca.py` together, and record what changed in the test.

**Going back.** When the regeneration or the upstream check fails, the new release is
installed and pinned and the old one is still in `tools/orca.previous`; the message names
both. Run the command again with the old version (`make -C slice upgrade-orca
VERSION=2.4.2`): it downloads, verifies and installs the old release the same way and
regenerates the profiles from it (`PENGUIN_SLICE_ORCA_CACHE` keeps each verified download,
so going back is quick). `git diff -- slice/` then shows nothing but what you meant to
keep.

**What happened when the command was run to other versions and back** (on an aarch64
Linux machine, with 2.4.2 pinned, Thu 2026-11-19; the commands were run by the builders
only, and the reviewers read them without running them):

- **Up to 2.5.1** (released Sat 2026-11-14), `make -C slice upgrade-orca VERSION=2.5.1`:
  GitHub's digests read, the release downloaded, verified and installed, the pin moved.
  The regeneration of the profiles then stopped with "machine profile 'Bambu Lab H2S 0.6
  nozzle' not found": 2.5.1 ships the Bambu Lab vendor profiles packed in `BBL.opc` (not a
  zip), and leaves only `filament/` and `cli_config.json` loose, so
  `scripts/flatten_orca_profiles.py` finds no printer to flatten. Taking 2.5.x needs the
  flattening script to read that format (or Orca's own export of it).
- **Down to 2.4.1**, `make -C slice upgrade-orca VERSION=2.4.1`: downloaded, verified,
  installed into `tools/orca.next`, the pin moved, `tools/orca` swapped, the profiles
  regenerated (only `catalog/index.json` changed: its `skipped` list is empty for
  2.4.1). The upstream check ran: 26 passed, 1 failed,
  `test_checked_in_profiles_and_catalog_match_the_installed_orca`, on that empty
  `skipped` list, and the command stopped, naming both versions and how to go back. That
  is the check doing its job: the test that assumes the catalog skips some profiles names
  the assumption that changed.
- **Back to 2.4.2** after each, `make -C slice upgrade-orca VERSION=2.4.2`: installed,
  regenerated and the upstream check passed (the return from 2.4.1 took 50 s). The
  pin's lines in `scripts/install-orca.sh` were byte for byte what they were, `git diff`
  showed no change under `src/penguin_slice/profiles/`, `tools/` held only `orca`
  (2.4.2), and no staged script was left in `scripts/`. Coming back restored the pin with
  no changes.

## Tests

| Target | What it runs |
|---|---|
| `make test` | The fast suite, in random order: no Orca, no network, no waiting, each test in its own temporary folder. |
| `make test-parallel` | The fast suite on `WORKERS` worker processes (default 2). |
| `make test-flakes` | The fast suite `RUNS` times (default 10) on `WORKERS` workers, each run with a new random seed, which it prints first. |
| `make coverage` | Branch coverage of the package under the fast suite; fails under 100%. |
| `make test-upstream` | The upstream check: the tests that run the real Orca (`tests_orca/`), one at a time, with each test's time, after `make orca-source`. `make test-orca` is the same. |
| `make orca-source` | Fetches and verifies the pinned Orca's source into `tools/orca-source/` (see [The table of settings](#the-table-of-settings)). |
| `make settings-table` | Regenerates `src/penguin_slice/settings/table.json` from that source and the profile catalog. |

In the fast suite `PENGUIN_SLICE_ORCA` always points at a placeholder that cannot run, so
no test can start the real Orca by accident, and no real timer runs (`slicer.TIMER` is
replaced; a test fires a timeout itself). Tests that need Orca's behaviour use
`tests/fake_orca.py` through `helpers.install_fake_orca`, a real child process with a mode
for each way Orca misbehaves (killed, crashing, hanging, ignoring SIGTERM, leaving a child,
flooding its output, writing a damaged file, waiting after writing its sliced file whole,
half, or under its temporary name, failing with a warning in its debug log); the upstream
check pins the fake's progress lines and its debug log line to the real ones.
`tests/fixtures/bad_stls/` is the corpus of bad part files, written by
`tests/fixtures/make_bad_stls.py` (the suite checks the two agree); Hypothesis throws
random and damaged files at the reader, derandomized so every run sees the same examples.
`helpers.spacer_stl` and `helpers.spacer_grid` write the reference plate of spacers.
`tests/fixtures/frc-parts/` holds eight real, printed parts of the Popcorn Penguins' robot (MIT, see
[its README](tests/fixtures/frc-parts/README.md)) and `tests/frc_parts.py` their measured
figures and plates: the fast suite reads and checks all eight (`tests/test_frc_parts.py`;
reading the 7 MB took 0.17 to 0.19 s in three runs on Fri 2026-11-20, once per worker), and
the upstream check slices them (`tests_orca/test_frc_parts.py`, about 110 s of the upstream
check's 144 s on Fri 2026-11-20). To rerun one random order, pass the seed:
`--randomly-seed=<seed>`.

No test can hang. Every wait on a process, a thread or an event gives up after
`helpers.FAILSAFE_S` (10 s) with a message naming what never happened, and a test that
runs a stand-in only a stop can end runs it through `helpers.bounded` and kills it
(`helpers.kill_fake`) if it is still there. Behind that, `conftest.no_test_can_hang` fails
any test still running after 20 s (a SIGALRM in the test's process, whose exception
`slicer.run_process`'s cleanup survives, killing the stand-in's group), and the stand-in
and any child it starts end themselves after 25 s (`fake_orca.LIMIT_S`). With the
watchdog's stop removed from a scratch copy, the suite fails 7 tests in 54 s on 2 workers
and leaves no process; with the ceiling setting ignored, 5 tests in 13 s.
