# Slice service

**The detailed guide, for someone changing the slice service.** A shorter guide for a
person is [README.md](README.md). Everything in this file outside the section
[To be built](#to-be-built) is true of the code as built.

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
percentage as progress, cancellation, abandonment and cleanup that leave no Orca and no
files, the memory watchdog at a 2,000 MB memory ceiling, Orca's reasons read from its
`result.json` and its debug log, one log line per slice job transition, and
`make upgrade-orca` with the upstream check. The fast suite covers every branch of the
package. The real-Orca suite slices 100 spacers in a 10 by 10 grid and the eight real
parts of the Popcorn Penguins' robot, alone and on mixed plates. The other reference
plates (a plate of several different functional parts, a full plate of small instances,
one, two and three large organic parts, and those with supports on) were measured with
`scripts/measure_plate.py` (see [Plate limits](#plate-limits)).

**Not built or not known:**

- Orca 2.5.x cannot be taken yet (see
  [Taking a new upstream version](#taking-a-new-upstream-version)).
- A part whose first layer is empty gets only the general sentence, since the pinned Orca
  writes its reason to no file; only a patch to Orca could surface it, and there is none.
- Parts that intersect themselves are not detected before slicing; the expected time is
  only within about a factor of two; the peak in the log can be under Orca's true peak for
  an Orca that fails between two of the watchdog's samples.
- Not measured: the disk held by finished slice jobs, which keep their uploads and sliced
  file for an hour; CPU time; how many slices a host can run at once. Every measurement is
  from aarch64 Linux machines: almost all from one with 4 CPUs, and nine plates of the
  memory model's fit from another.

**What the phases still need from it** is in [To be built](#to-be-built), by phase.
Some sentences of its error reports and some code comments
still name the user with the old words; changing them is a change of its own, with its
tests.

## To be built

This section holds what [the architecture](../docs/architecture.md) adds to the slice
service or changes in it, grouped by the phase of [the plan](../docs/plans/penguin-slicer-plan.md)
that builds it: phase 2 runs everything on one machine, phase 3 hosts it on Railway.
Phases 4 (inside Onshape) and 5 (the real printer) change nothing here: printer delivery
does not pass through the slice service. Each item says what it does, its figures, what it
replaces in the code as built, the error report it produces and the tests it needs. Every
failure a caller can see gets a test in the fast suite that produces it on purpose, with no
real Orca and no real waiting (a fake clock, `tests/fake_orca.py`, `slicer.TIMER` replaced).
When an item is built, its text moves into the body of this file and out of this section,
and [README.md](README.md) is updated to match. The ids in brackets name the decisions in
[the map of the hosted architecture's decisions](../docs/orchestration/hosted-architecture/decision-map.md).

### Terms used below

- The **front server** is the one process the browser talks to (in `front/`, see
  [its guide](../front/README.md)). It is the only caller of the slice service: it passes
  parts and slice jobs through, fetches each sliced file and gathers the slice service's
  log lines. In phase 2 it is a process on the one machine; hosted, it has a container of
  its own.
- The **slice container** is the container on Railway that runs one slice service process
  and nothing else.
- The **user key** is the signed-in user's Onshape id, which the front server passes with
  every request to say whose part or slice job it is. The slice service compares user
  keys and never interprets them.
- The **part store** is the slice service's folder of uploaded parts, each kept for two
  hours after it was last used. It is a cache: the browser's storage is the record of a
  user's parts.
- The **state bucket** is the object store where the front server keeps what must outlast
  a restart, the sliced files among it; the **log bucket** is the object store that holds
  log lines as files. The slice service holds no credential for either.
- A **progress stream** is the connection of server-sent events on which a slice job is
  followed: as built, `GET /slices/<job>/events`.

### What the other documents decide

These are decided and explained elsewhere; the slice service is built to fit them.

- **Who reaches the slice service.** The browser talks only to the front server, which
  calls the slice service over Railway's private network, so the HTTP interface is not
  reachable from the internet and the browser never makes a cross-origin request. This
  settles the as-built need for a way for the page to reach the HTTP interface.
  See [the architecture, The shape](../docs/architecture.md#the-shape). [D33]
- **Why a container of its own.** Orca reads files strangers upload, so the slice
  container holds no credentials: a flaw in Orca reaches no sign-in secret and no bucket.
  The split makes the front server pass parts and slice jobs through, fetch each sliced
  file and fetch the slice service's log lines from a route of the slice service.
  See [the architecture, The shape](../docs/architecture.md#the-shape). [D34, D36]
- **The slice container's size.** It is allowed 8 GB, the most one container gets on
  Railway's Hobby plan. See [the architecture, The shape](../docs/architecture.md#the-shape). [D39]
- **Only the front server calls it, with the user key.** Orca and the checks run in the
  slice container, which accepts requests only from the front server. The front server
  passes each uploaded part with the user key, sets the user key from the sign-in cookie
  (the browser cannot name one), so a user reaches only their own parts, slice jobs and
  sliced files. See [the architecture, Security](../docs/architecture.md#security) and
  [the front server's guide](../front/README.md). [D26, D71, D249, D252]
- **Parts named by hash.** A plate configuration names each part by the SHA-256 hash of its
  bytes and carries no files; an error report lists the parts missing from the part store.
  See [the plate configuration contract](../contracts/plate-configuration.md). [D25, D73, D293]
- **The front server follows and collects.** It follows every unfinished slice job's
  progress stream itself, and when it starts it asks the slice service for its slice jobs,
  follows the unfinished ones and collects each finished one it has not yet stored. A
  progress stream that connects late gets the latest progress report at once, which the
  slice service already does. See [the front server's guide](../front/README.md). [D62, D88]
- **One user cannot take the service.** One unfinished slice job per user, bounded memory
  and time, and at most 25 parts per user key together keep one user from taking every
  place a slice job may wait in or filling the slice container's disk.
  See [the architecture, Security](../docs/architecture.md#security). [D244]
- **The plan's standing requirements change.** The requirement Cleanup is amended for
  slice jobs: a slice job goes on when its page goes away, bounded by the time limit. How
  many slices run at once and how many may wait are settings, where the plan states one
  and two. See [the plan](../docs/plans/penguin-slicer-plan.md#standing-requirements). [D282, D290]
- **What every component logs.** Every error a user is shown, with its code, the user key
  and the job; every exception with its stack trace; every refusal; and once a minute a
  line with the memory held and the slices running and waiting. The front server fetches
  the slice service's lines from a route on the private network and writes them to the
  log bucket about once a minute, adding the group.
  See [the architecture, Reading what happened](../docs/architecture.md#reading-what-happened)
  and [the front server's guide](../front/README.md). [D182, D183, D184, D191, D196]
- **Measured before users rely on it.** Every measurement so far is from aarch64 Linux
  and from plates under 2,600 MB. Plates of rising weight up to the proposed 6,000 MB are
  sliced on the slice container before users rely on it, and set the memory ceiling, the
  time limit and the estimates. See
  [the architecture, To confirm before building on it](../docs/architecture.md#to-confirm-before-building-on-it). [D350]

### Phase 2: one machine

The front server and one slice service process run on the one machine. Everything below
is built in phase 2, with its tests.

**The user key on every request.** Every request to the HTTP interface carries the user
key in the header `X-Penguin-User-Key`. A part is stored, and a slice job is held, under the
user key that sent it. A request about a slice job of another user key answers exactly as
for an unknown slice job (`slice.unknown_job`, HTTP 404), so nobody learns that the slice
job exists, and is logged as a refusal. The one route that is not scoped to a user key is
the list of slice jobs (below), which only the front server calls. Replaces: nothing; as
built the slice service knows no user. Error report: a request without the header, or with
an empty one, is refused with `slice.no_user_key` (HTTP 400), a new code added to
`errors.CODES` and to [Error codes](#error-codes). Tests: each route refuses a request
without the user key; every route about a slice job (`GET`, `events`, `DELETE`, `file`,
`summary`) answers `slice.unknown_job` for another user key's slice job and logs the
refusal. [D295]

**The part store.** A route, `POST /parts`, takes one part (a binary STL as the request
body) and checks it on arrival, so a part that cannot be sliced is refused on the wizard's
Parts step, on its own row, before the user has laid anything out. The checks are those of
[Checks on every part](#checks-on-every-part); the fit test (`slice.part_too_large`) runs
on arrival against the largest printer of the catalog and again, as built, against the
plate configuration's printer when a plate configuration names the part. A part that passes
is kept in the part store under the user key and the SHA-256 hash of its bytes, and the
answer (HTTP 201) carries that hash (hexadecimal), the part's measurements (triangles,
size, volume) and its warnings (`slice.part_not_watertight`, `slice.part_inside_out`,
`slice.part_maybe_inches`). The same bytes sent again by the same user key answer the same
and count as a use. The figures and rules:

- A request body over `MAX_PART_BYTES` (7,500,084 bytes, 7.5 MB, the plate
  configuration's limit for one part) is refused with `slice.part_too_detailed`
  (HTTP 413) before it is read.
- A part stays in the part store for two hours (7,200 s) after it was last used; its upload
  and each slice that names it count as a use. The job pool's sweeper (`SWEEP_INTERVAL_S`,
  10 s) removes expired parts.
- The part store holds at most 25 parts for one user key (`MAX_PARTS`, the most a plate
  can use). When a twenty-sixth arrives, that user key's least recently used part is
  removed; the page uploads it again if a plate ever names it.
- The part store has a limit on the disk it may take in all, a setting of the slice
  service. Past it, the least recently used parts of any user key are removed. Its
  default is not set: the part store's disk use was never measured.
- A part is found only under its user key, so two users who upload the same file each have
  their own entry, and nobody can learn whether someone else uploaded a given file.
- The slice service empties the part store when it starts. This adds to
  `service.clean_stale_scratch`, which removes only the scratch of processes no longer
  running.
- A slice job takes its own link to each part's file when it is accepted, so removing a
  part from the part store never touches a slice job already accepted.

Replaces: the parts sent as file fields of `POST /slices`, saved into each slice job's own
`parts/` folder (`web.UPLOADS`). Error reports: each check's code as listed in
[Checks on every part](#checks-on-every-part), now answered by `POST /parts` (HTTP 422);
a part store that cannot be written is `slice.scratch_unwritable` (HTTP 500). Tests:
a good part answers its SHA-256; each refusal code of the checks produced through
`POST /parts`; a body over `MAX_PART_BYTES` refused before it is read; the twenty-sixth
part of one user key removes that user key's least recently used part and no other user
key's; past a small disk limit set by the test, the least recently used part of any user
key goes; on a fake clock a part unused for 7,200 s is gone and one named by a slice in
between is kept; a start empties the part store; a part of user key A is missing for user
key B; removing a part does not touch a slice job that names it. [D72, D74, D76, D77, D80,
D81, D82, D83, D291, D294]

**A plate configuration names parts by hash.** `POST /slices` takes the plate
configuration as a JSON body, its parts naming the hashes of parts in the part store, and
carries no files ([the plate configuration contract](../contracts/plate-configuration.md)
defines the field). Slicing again uploads nothing. The body is at most 1 MB, the allowance
the form has as built. Replaces: the route that takes a whole plate's files in one request,
with `web.FORM_FIELD`, `web.UPLOAD_NAME_RE` and `web.MAX_UPLOAD_BYTES`
(`MAX_PARTS x MAX_PART_BYTES` plus a megabyte); the route is removed. Error report: a plate
configuration that names parts no longer in the part store is answered with one error
report listing every missing hash, `slice.part_missing` (stage `checking`, HTTP 422, action
`refresh_parts`, its detail and `where` listing the hashes). The page then uploads those
parts again from the browser's storage and submits again, and the user sees nothing of it.
Replaces in `slice.part_missing`: the meanings "the part's STL file is missing" and "lies
outside the files sent"; an instance naming a part the plate configuration does not list
keeps the code. Tests: a plate configuration naming two missing hashes gets one report
listing both; after both are uploaded the same plate configuration is accepted;
`tests/test_errors.py` produces the new meaning on purpose; a multipart body is refused.
[D78, D292]

**One unfinished slice job per user key.** Submitting a plate configuration cancels the
same user key's earlier unfinished slice job (queued or running), which is what the
Preview step does when a plate changes; with the wizard open in two tabs, the later slice
wins. The cancel is a cancel as built (a queued slice job at once, a running one once Orca
and every child are gone), and its final report is `cancelled`, saying it was replaced by a
later slice of the same user key ([the progress report contract](../contracts/progress-report.md)
names the field), with `"cancel_reason": "replaced"` in its log lines. The earlier slice job
gives up its place in the queue before the new one is counted, so a user key holds at most
one place. Replaces: nothing; as built any number of slice jobs may come from one caller.
Error report: none new. Tests: a second submission cancels the first while queued and while
running (a hanging fake Orca); the first's final report says replaced; another user key's
slice job is untouched; a user key that resubmits while the queue is full is not refused.
[D97, D98, D295]

**A slice job goes on without its page.** Once submitted, a slice job runs to its end
whether or not anything follows it: through a refresh, a dropped connection or a closed
lid. A slice whose user never returns holds an Orca until it ends, which the time limit
bounds (accepted). Replaces: `jobs.ABANDON_GRACE_S` (120 s), the sweep's cancel of a slice
job nobody follows, `"cancel_reason": "abandoned"` and the paragraph "Cleanup" under
[Progress, cancellation and cleanup](#progress-cancellation-and-cleanup) as far as it
concerns abandonment. Error report: none. Tests: on a fake clock, a slice job with no
subscriber for longer than 120 s ends `done`; the tests of abandonment are removed. [D95,
D96, D297]

**Slice jobs remembered for two hours; the sliced file deleted once stored.** The slice
service remembers a slice job for two hours (7,200 s) after it ends; a finished one is also
known by its sliced file in the state bucket. Once the front server has stored the sliced
file, it says so with `DELETE /slices/<job>/file`, and the slice service deletes its own
copy at once; the record stays until it expires. A sliced file never collected goes with
its record. Replaces: `jobs.RECORD_TTL_S` (3,600 s), and the sliced file kept beside its
record for that hour. Error reports: the file or summary of a slice job whose file was
deleted is `slice.file_gone` (HTTP 410), as built; `DELETE /slices/<job>/file` on a slice
job not done is `slice.not_ready` (HTTP 409); on an unknown slice job,
`slice.unknown_job`. Tests: on a fake clock the record is there at 7,199 s and gone at
7,200 s; after the delete, the file and the summary answer `slice.file_gone` and the
progress report is still served; a second delete answers the same as the first; a delete
before the slice ends is refused. [D90, D100, D298, D299]

**A route lists the slice jobs.** `GET /slices` answers every slice job the slice service
process knows: for each, its id, its user key, its latest progress report and whether its
sliced file is still on the disk. A restarted front server uses it to find the slices it
must still follow or collect. Replaces: nothing. Error report: none beyond those of every
route. Tests: the list holds a queued, a running, a done, a failed and a cancelled slice
job with their states; it is empty in a newly started process; a done slice job whose file
was deleted shows the file gone. [D296]

**A waiting slice job says how many are ahead.** A slice that cannot start yet waits, and
its user is shown that it is waiting and how many slices are ahead of it. A queued slice
job's progress report carries the number of slice jobs ahead of it (those running and those
queued before it), and a new report (`sequence` plus one) is sent whenever that number
changes ([the progress report contract](../contracts/progress-report.md) names the field).
When no more slice jobs may wait, the user is told the slice service is busy and to try
again shortly: that is `slice.busy` (HTTP 503, retryable, "The slicer is busy, try again in
a minute."), as built. Replaces: the queued report, which says only "Waiting for the
slicer". Tests: with one running and two queued, the queued ones report 1 and 2 ahead; when
the running one ends, the last reports 1. [D54, D55, D302]

**Asked to stop, it finishes the running slice.** When `serve` receives SIGTERM (what a
container host sends) or Ctrl-C, it refuses new slice jobs (`slice.busy`), cancels the
queued ones (`"cancel_reason": "shutdown"`; their pages submit them again), lets the
running slice job run to its end, bounded by the time limit, keeps the HTTP interface
answering until the front server has fetched and deleted that slice job's sliced file,
and then exits 0. A second SIGTERM or Ctrl-C cancels the running slice job as built.
Railway gives a stopping container a time of its own, not yet known; past it Railway kills
the process, and Orca dies with it (`PR_SET_PDEATHSIG`). Replaces: `JobPool.shutdown`,
which cancels every slice job, and the end of `serve`, which waits only until every Orca is
gone. Error report: none new. Tests: a stop while a fake Orca runs ends that slice job
`done` and `serve` exits only after the sliced file is deleted; a queued slice job ends
`cancelled` with the reason shutdown; a submission after the stop is refused with
`slice.busy`; a second stop cancels the running slice job. [D230, D306]

### Phase 3: hosted on Railway

**The limits become settings.** The slice service stops an Orca that passes the memory
ceiling or the time limit and reports each as an error the wizard explains: passing the
memory ceiling is `slice.out_of_memory`, passing the time limit is `slice.timeout`, both as
built. Both limits, and how many Orcas run at once and how many slice jobs may wait behind
them, are settings of the slice service, each refused at start with a message that names it
and exit status 2, as `PENGUIN_SLICE_MAX_PEAK_MB` is as built:

| Setting | Default | Replaces |
|---|---|---|
| `PENGUIN_SLICE_TIME_LIMIT_S` | 240 | `limits.PLATE_SLICE_TIMEOUT_S` (240 s) |
| `PENGUIN_SLICE_MAX_RUNNING` | 1 | `jobs.MAX_RUNNING` (1) |
| `PENGUIN_SLICE_MAX_WAITING` | 2 | `jobs.MAX_QUEUED` (2) |

The hosted service starts with one running and two waiting, changed from what is seen in
use. These stay settings because how many processors Railway gives the slice container,
how long real plates take there and how often two users slice at the same moment are not
yet known. Tests: each setting's refusal of a bad value; a time limit set by the test
fires `slice.timeout` through the replaced `slicer.TIMER`; with two running, two fake
Orcas run at once. [D43, D51, D52, D56, D301, D304]

**The memory ceiling at the hosted figure.** The slice container sets
`PENGUIN_SLICE_MAX_PEAK_MB` to 6,000 MB (proposed); the default in the code stays 2,000 MB.
6,000 MB leaves 2 GB of the slice container's 8 GB for the slice service process, its
checks on uploaded parts and the operating system. The margin matters because Railway
stops a container that passes its 8 GB, which would take the waiting slice jobs with it,
where the ceiling ends only the one slice. The figure is the project owner's to change; a
high ceiling costs money only while a heavy plate is slicing, since Railway bills the
memory a container holds at each moment. By the figures of "Sizing the host" under
[Plate limits](#plate-limits), Orca can pass the ceiling by the rise between two of the
watchdog's readings (502 MB, the largest measured) and a host is sized for 400 MB of the
slice service beside Orca, so 6,000 MB plus both is 6,902 MB, under the 8 GB. The slice container never runs more Orcas than fit in its memory
with each at the memory ceiling: with 6,000 MB that is one, and two at once would need a
ceiling of about 3,000 MB each, and so smaller plates. Orca uses several processors by
itself, so a second Orca would share them, not use idle ones. Replaces: the 2,000 MB the
service runs at as built, and the rule in the docstring of `jobs.py` (min of the CPUs and
memory over one slice's peak). Error report: `slice.out_of_memory`, as built. Tests: none
new in the fast suite (the setting's tests exist); the measurements below. [D44, D45, D53,
D303]

**Measurements on the slice container set the two limits.** The heaviest plate ever
measured peaked at 2,569 MB (six Stanford bunnies with supports on). The plates the Popcorn
Penguins print took at most 22.5 s of Orca's time (four-each-b with supports on), and the
slowest plate of their parts measured, twelve Elevator Block Bottom Inners with supports on
at a 3,000 MB ceiling, 34.3 s. All of it was measured on aarch64 machines, where Railway's
are believed to be x86_64, and on plates far lighter than 6,000 MB; a plate that heavy will
take longer. The time limit must be long enough that every plate which would finish does
finish, and no longer, because a slice that hangs holds up everyone waiting behind it. So
both are settled by one set of measurements on the slice container: plates of rising
weight up to the memory ceiling, each timed. The time limit is then set at a few times the
slowest plate that finishes; until then it starts at 240 seconds. For plates heavier than
any measured, the slice service's estimates of memory and time are extended beyond what
was measured: the memory and time models (`limits.estimate_peak_mb`,
`limits.estimate_seconds`) are linear in the instances and the volume, and are refitted on
these runs (`scripts/measure_plate.py --fit`). Replaces: `limits.MEASURE_STOP_MB`
(3,072 MB), the ceiling `scripts/measure_plate.py` slices under, which stops a measurement
below the hosted ceiling and must rise above it; the time limit a measurement runs under
(`slicer.slice_plate`'s default, `PLATE_SLICE_TIMEOUT_S`, 240 s; `limits.MEASURE_MAX_SECONDS`,
180, is defined and used nowhere); and the models' constants (`MEMORY_*`, `TIME_*`).
Tests: the fast suite's tests of the models follow their new constants. [D46, D47, D48,
D49, D50]

**A comment line on a quiet progress stream.** Railway closes a request after fifteen
minutes, or after five without data, and Cloudflare after 125 seconds without data. So the
progress stream sends a comment line (`: keep-alive`) at least every fifteen seconds while
it has nothing to report, as the relay's does. Replaces: `JobPool.follow` repeating the
latest progress report, with its same `sequence`, every `jobs.WAIT_S` (15 s) when nothing
changes. Error report: none. Tests: with the wait injected, a quiet stream sends a comment
line and no repeated report; a new report follows the comment line. [D60, D300]

**Orca as a Unix user of its own.** Orca runs as a Unix user of its own that can write
only the scratch folder of its slice job, so a flaw in Orca cannot alter the slice service
or reach another slice job's files. The slice container's image makes the user, and the
slice service starts Orca as it. Replaces: Orca run as the slice service's own user (with
its allowlisted environment and its `HOME` in the scratch folder, which stay). Error report:
an Orca that cannot be started as that user is `slice.orca_unstartable`. Tests: in the fast
suite, the command the slice service builds names the user; in the slice container's
image, a fake Orca that tries to write outside its scratch folder is refused. [D253, D305]

**A new Orca version is a new image.** A new Orca version is rolled out as a new image of
the slice container, built with the version pinned in `scripts/install-orca.sh` after
`make upgrade-orca` and the upstream check pass, and deployed like any other change. The
image installs the distribution's packages listed under [Orca Slicer](#orca-slicer), since
the install script stops instead when it runs as root. Replaces: nothing; as built Orca is
installed into `tools/orca` on the machine that runs the service. Tests: the image's build
runs `make test-upstream`. [D42]

**The log.** The slice service's log lines reach the log bucket through the front server:

- A route, `GET /log`, gives the front server the lines written since the last it fetched
  (by a sequence number it passes back). The lines wait in a bounded buffer in memory; each
  line also goes to stderr, so one dropped from a full buffer is still in Railway's log
  view. Every line gains the time and the user key. [D307]
- The line that ends a slice job, which already carries Orca's peak memory
  (`peak_rss_kb`), the estimates (`estimated_peak_mb`, `expected_s`), the memory ceiling
  (`memory_ceiling_mb`), its times (`orca_wall_s`, `wall_s`) and each part's measurements,
  gains the bytes of each part, the bytes of the sliced file and how long the slice job
  waited before it ran. [D188, D308]
- A slice that passes 80 percent of the memory ceiling or of the time limit also writes a
  line marked as a warning, so that near misses can be found without reading every slice:
  with 6,000 MB and 240 s, a peak over 4,800 MB or Orca running over 192 s. [D190]
- Once a minute a line gives the memory the slice service process and its Orcas hold, and
  the slices running and waiting (`JobPool.counts`). [D309]
- A line for every exception and every refusal, whichever route it comes from. As built
  only the refusals of `POST /slices` (`"state": "refused"`) and the exceptions of the
  routes (`slice_http_error`), the sweeper and the cleanup are logged; the refusal of
  another user key's slice job and every refusal of `POST /parts` join them. [D309]

Replaces: the log lines written only to stderr, with no time and no user key. Error report:
none; a log that fails never changes an answer, as built (`jobs.SafeLog`). Tests: each kind
of line produced on purpose (a fake Orca reporting a peak over 80 percent of a ceiling the
test sets, a fake clock past 80 percent of the time limit, the once-a-minute line on a fake
clock, a refusal at every route); `GET /log` gives lines in order and only those after the
number passed; a full buffer drops the oldest and counts it.

## Use

The HTTP interface is the slice service's one way in. Nobody slices by hand: to try
something, start the service and write a throwaway script against its routes.

```
make -C slice install        # the Python environment, and Orca Slicer into slice/tools/orca
make -C slice test           # the fast suite
```

Start the service, then submit the example plate configuration with `curl`, follow its
progress reports, and fetch the sliced file and its summary:

```
uv run --project slice python -m penguin_slice serve --work /var/tmp/penguin-slice --port 8640

curl -s -F 'plate_configuration=<contracts/examples/plate-configuration.json' \
     -F bracket.stl=@contracts/examples/parts/bracket.stl \
     -F spacer.stl=@contracts/examples/parts/spacer.stl \
     http://127.0.0.1:8640/slices                                 # 202: {"job": "j...", "progress": ...}
curl -sN http://127.0.0.1:8640/slices/<job>/events                 # progress reports until the final one
curl -s  http://127.0.0.1:8640/slices/<job>/summary                # the sliced file's summary, as JSON
curl -s -OJ http://127.0.0.1:8640/slices/<job>/file                # the sliced file itself
```

`serve` writes one JSON log line per slice job transition on stderr; stopping it with
Ctrl-C or SIGTERM (what a container host sends) cancels every slice job, sends each
subscriber its `cancelled` report and waits until every Orca is gone. A setting it refuses
(see Settings) stops it before it listens, with a message naming the setting and exit
status 2.

**One slice service process holds its slice jobs.** A running slice service is a slice
service process: one process, whose slice jobs live in its memory (`jobs.JobPool`).
Several slice service processes may run, on one machine or several; a client must keep
talking to the slice service process that accepted its slice job, because no other
process knows it. A server that starts several worker processes behind one address
(several Gunicorn workers, for example) loses slice jobs: a request that reaches another
worker gets `slice.unknown_job`. `serve` runs Flask's own threaded server in one process.

## The HTTP interface

`penguin_slice.web.create_app(work_dir)` is a Flask app factory:

| Request | Answer |
|---|---|
| `POST /slices` with form field `plate_configuration` (the JSON) and one file field per part, named as the part's `stl` | 202 with `job`, the first progress report and the `part_warnings` |
| `GET /slices/<job>` | The latest progress report |
| `GET /slices/<job>/events` | The progress reports as `text/event-stream`, the latest first, ending with the final one |
| `DELETE /slices/<job>` | Cancel: `{"cancel": "cancelled" \| "cancelling" \| "finished"}` |
| `GET /slices/<job>/file` | The sliced file of a done slice job, and nothing else |
| `GET /slices/<job>/summary` | The sliced file's summary ([sliced-file.md](../contracts/sliced-file.md), "Summary") as a JSON body |

Every other answer is an error report: 400 for a request that is not a plate configuration,
404 for an unknown slice job (`slice.unknown_job`) or a path the interface does not offer
(`slice.bad_request`, also 405 for a method a path does not take), 409 for a sliced file or
summary that is not there (the slice job's own error report, `slice.cancelled` or
`slice.not_ready`), 410 for a sliced file gone from the disk (`slice.file_gone`, for the
summary too), 413 for an upload over `MAX_UPLOAD_BYTES`, 422 for a plate configuration a
check refused, 500 for the server's own failure (`slice.scratch_unwritable` when the work
folder cannot be written or an upload cannot be saved in it, a full disk for one,
`slice.unexpected` for a bug, logged with its traceback), 503 when the queue is full. The
file and summary routes answer alike for a slice job that is unknown, failed, cancelled or
not finished. A plate configuration is read and checked when it arrives, before a slice
job is queued for it, so a refusal comes back at once; its STL paths must name files sent with it.
Instances of one part share that part's one file. Each slice job's files live in
`<work>/slice-<pid>-<start>-<random>/`; they are removed when the slice job ends failed or
cancelled, or when its record expires (`RECORD_TTL_S`, an hour after its final report).

`MAX_UPLOAD_BYTES` is `MAX_PARTS x MAX_PART_BYTES` plus a megabyte for the form: one STL
per part used, whatever the number of instances.

Underneath, the interface calls `service.slice_plate_configuration`, and that calls
`slicer.slice_plate`; they are code the HTTP interface and the tests call, not ways in.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `PENGUIN_SLICE_MAX_PEAK_MB` | 2000 | The memory ceiling (see "Plate limits"). Unset or empty: the default. Otherwise 1 to 6 plain digits `0` to `9`, not 0; anything else (`²`, `٣`, `1e3`, a space, 30 digits) is refused at start with a message that names the setting. |
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
mesh". Both are read before the scratch folder is removed and kept in the detail. For a
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
service never states a reason the log does not give. Some reasons reach no file at all. A part
whose first layer is empty (a needle 0.3 mm across and 300 mm tall, thinner than the
nozzle prints) fails as an error that the pinned Orca collects and loses (it prints
`Errors` on stderr): neither `result.json` nor the debug log, even at `--debug 5`, holds
the reason, so that part gets the general sentence. The debug log's format is Orca's and
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

## Sample part

`src/penguin_slice/sample_part.stl`, an L bracket 40 x 30 x 12 mm (binary STL, 20
triangles), written by `scripts/make_sample_part.py`; the fast suite checks that the two
agree byte for byte. `slicer.slice_stl` slices it alone with the default set and
`--arrange 1` (the upstream check uses it).

## Checks on every part

Every part an instance uses is read and examined when the plate configuration arrives,
before any slice starts (`mesh.read_binary_stl` and `mesh.analyse`). A finding that makes a
slice impossible or pointless refuses the plate configuration with an error report naming
the part; a finding Orca copes with only warns, and the warning travels in the sliced
file's summary (`part_warnings`) and in the HTTP interface's answer to the submission.

| Finding | Refuse or warn | Code |
|---|---|---|
| The file is empty, too short, not an STL (an image such as a PNG or JPEG, a PDF, a zip or 3MF, a gzip, UTF-16 text, text of any length such as an HTML or JSON error page, or any file whose header gives a triangle count larger than any part the service takes), cut off, padded, has 0 triangles, or a coordinate that is not a finite number | Refuse | `slice.part_unreadable` |
| An ASCII STL, in any case and with or without a byte-order mark | Refuse | `slice.part_not_binary` |
| Over `MAX_PART_TRIANGLES` or `MAX_PART_BYTES` | Refuse | `slice.part_too_detailed` |
| 0.1 mm or less in every direction, or in one (flat) | Refuse | `slice.part_too_small` |
| Every triangle a line or a point; or no triangle shares an edge with another; or a closed surface in one plane or enclosing no volume (faces laid on top of each other) | Refuse | `slice.part_no_volume` |
| Fits the printer in no orientation at any angle | Refuse | `slice.part_too_large` |
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
bytes of one part, and each part's size against the plate and the printer. Memory refuses
nothing before slicing, and neither do the triangles of the whole plate: the memory
watchdog, not the instance count, is what protects the machine.

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
time limit (`PLATE_SLICE_TIMEOUT_S`, 240 s) is twenty times what 150 spacers take.

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
   `slice.out_of_memory`, or `cancelled`. A cancel (the user's, an abandoned slice
   job's, a shutdown's) discards even a complete file. A stop is sent only while Orca is
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
waiting; a further one is refused with `slice.busy`. Each slice job's latest progress
report is kept with a `sequence` that rises by one with every report; a subscriber that
connects late gets it at once. The stages, in order:

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
and `cancelled`.

**Cancelling.** A queued slice job is cancelled at once. A running one that is still
writing its plate 3MF (`building_plate`) stops at the next object it writes: the write
looks at the stop before each part's mesh and each instance's object, and once it is set
ends with `cancelled`, never starts Orca, and its files are removed; the same holds for an
abandonment and a shutdown during the write. On the largest plate (150 instances of a hub
at `MAX_PART_TRIANGLES`, one part or 25), `cancelled` came 0.05 to 0.17 s after the
`DELETE`, at any moment of the 24 to 28 s write. Orca is also never started for a slice job
whose stop is already set (`slicer._run_orca` looks first). A running one whose Orca has
started is reported
`cancelled` only after its Orca and every child are gone, or `failed` when it had already
failed (a watchdog stop or a timeout asked first is the one reported, and so is a crash or
someone else's kill that ended Orca before the cancel's SIGTERM could). A cancel the
user asked for before the final report always discards the sliced file, even one Orca
finished at the same instant (the user asked not to have it; the `cancelled` log line
names it in `file_discarded`); cancelling a finished slice job changes nothing and answers
`finished`; an unknown slice job answers `unknown`; cancelling twice answers `cancelling`
twice and is logged once.

**Cleanup.** A slice job nobody follows is cancelled `ABANDON_GRACE_S` (120 s) after its
last subscriber left, or after it was submitted if none ever came; a subscriber that
returns in time keeps it. When every subscriber has gone and the grace time has passed,
nobody is waiting for the file, and the slice job ends `cancelled` like a user's
cancel: a slice that finishes at that instant is discarded too, and a subscriber who comes
back later finds `cancelled`. Its `cancelling` and `cancelled` log lines carry
`"cancel_reason": "abandoned"`, and the `cancelled` line `file_discarded` when a finished
sliced file was thrown away. Scratch folders are removed on every way out (success,
failure, timeout, cancel); at start the HTTP interface removes the scratch of any process
that is no longer running (`service.clean_stale_scratch`: the folder name carries the
process id and its start time, so a reused process id is not mistaken for the living one).
A running slice job's record never expires; a final one goes an hour after its final
report, with its files. Shutdown (`JobPool.shutdown`, the end of `serve`) cancels every
slice job and waits for every worker.

**The log.** One JSON line per slice job transition (`queued`, `running`, `cancelling`,
`done`, `failed`, `cancelled`, `expired`), `{"event": "slice_job", ...}`, carrying the job
id, the printer, filament, process, overrides and whether supports are on, the memory and
time estimates, every part with its triangles, size, volume, watertightness, shells, open
edges and warnings, every instance with its name, orientation, angle and position, and on
a final state the error code, the error report's detail, Orca's reason, Orca's peak memory
(and `memory_note` when a delivered slice's peak passed the ceiling, `stop_note` when a
stop reached Orca after its sliced file was complete, `cancel_reason`, and
`file_discarded` when a cancel threw away a finished sliced file), Orca's wall time and
the slice job's wall time. The log sink is called through `jobs.SafeLog`, the one place a
failing sink (a closed or broken stderr under `serve`) is caught: the failure is counted
(`JobPool.log_failures()`; the HTTP interface has no health answer to show it in) and
never changes what a slice job or an answer does. A plate configuration refused before
any slice job exists for it leaves one line too, with `"state": "refused"`: every answer of `POST /slices` that
is not 202 (a part a check refused, a plate configuration that is not JSON or has no
`plate_configuration` field, an upload too large, a full queue, a full disk while an upload
is saved, a work folder that cannot be written, a bug) carries `http_status`,
`error_code`, `error_detail`, `parts` (each part's key, name and `stl`, as the plate
configuration named them, when it could be read) and `uploads` (each uploaded file's field
name and size in bytes, when the body could be read). No payload, path of the caller or
environment variable is logged.

## Modules

| Module | What it holds |
|---|---|
| `web.py` | The HTTP interface, the one way in |
| `service.py` | Reading and checking a plate configuration, slicing it, the sliced file, scratch folders |
| `errors.py` | The adapter from every exception to an error report, and every code |
| `plate.py` | Orientations, instance placement and the rules a placement must pass |
| `mesh.py` | Reading a binary STL, the checks on its surface, the warnings, and a part's footprints |
| `plate_3mf.py` | The plate written as a 3MF for Orca, the sliced file's name, the name guard |
| `plate_configuration.py` | One checked plate configuration and its description for the log; the slice job's work on it (the plate 3MF, the Orca run, the name guard) |
| `print_config.py` | The profile catalog, the profile choice, the overrides and whether supports are on |
| `slicer.py` | Everything that runs Orca or reads what it writes |
| `jobs.py` | The job queue: progress reports, cancellation, abandonment, expiry, the log |
| `limits.py` | Every cap, the memory and time models, the memory ceiling setting, and the sentences that refuse them |

## Error codes

Every code the slice service produces, in the order of the checks. `tests/test_errors.py`
produces each one on purpose, through the code that really raises it, and states the
sentence, remedy, action, retryable flag and evidence its report must carry.

| Code | Stage | When |
|---|---|---|
| `slice.bad_plate_configuration` | checking | The plate configuration is not JSON (or nested too deeply to read), has a field that is not listed, or a part or instance lacks a field or has a bad value (an `stl` with a NUL character, over 1,024 characters, or a piece over 255 bytes; a part `name` over 200 characters; a `printer`, `filament` or `process` name over 200 characters); or the upload is over `MAX_UPLOAD_BYTES` (HTTP 413). No sentence, detail or log line grows with what a caller sends: a value it shows is cut to 120 characters, and a bug's own words to 2,000. |
| `slice.too_many_instances` | checking | More than `MAX_INSTANCES` instances. |
| `slice.too_many_parts` | checking | The instances use more than `MAX_PARTS` different parts. |
| `slice.unknown_printer` | checking | The printer is not in the catalog. |
| `slice.profiles_not_offered` | checking | The filament or process is not in the catalog, does not fit the printer, or is not the default set's. |
| `slice.bad_overrides` | checking | An override is not one of the four, or its value is not listed. |
| `slice.profile_unreadable` | checking | A profile file of the server's own (the catalog, a printer or process profile) is missing or not a profile. |
| `slice.part_missing` | checking | An instance names a part the plate configuration does not list, or the part's STL file is missing (also when it goes away after the checks), or lies outside the files sent with the plate configuration. |
| `slice.part_unreadable` | checking | A part's file cannot be opened, is empty, is not an STL (an image, a zip or 3MF, a gzip, text such as an HTML or JSON error page), is cut off or padded, has no triangles, or has coordinates that are not finite. |
| `slice.part_not_binary` | checking | A part's file is an ASCII STL. |
| `slice.part_too_detailed` | checking | A part's STL is over `MAX_PART_BYTES` or `MAX_PART_TRIANGLES`. |
| `slice.part_too_small` | checking | A part is 0.1 mm or less in every direction, or flat in one. |
| `slice.part_no_volume` | checking | A part's triangles have no area, or none shares an edge with another, or its closed surface lies in one plane or encloses no volume (faces laid on top of each other). |
| `slice.part_too_large` | checking | A part fits the printer in no orientation. |
| `slice.placement_off_plate` | checking | A footprint leaves the printable area less the margin. |
| `slice.placement_too_tall` | checking | An instance is taller than the printable height. |
| `slice.placement_too_close` | checking | Two footprints are closer than `SPACING_MM` (5 mm), or `SPACING_SUPPORTS_MM` (12 mm) with supports on (see "Spacing"). The report names both instances (`where`: `instance`, `other_instance`); with supports on the sentence says supports need the room, and the remedy also offers turning supports off. The detail lists at most 20 such problems. |
| `slice.busy` | queued | The job queue is full. |
| `slice.scratch_unwritable` | building | The plate 3MF, the process file or Orca's folders cannot be written (a full disk, a folder where an earlier run's sliced file was), or the HTTP interface cannot make a slice job's folder in its work folder (HTTP 500). |
| `slice.orca_missing` | slicing | No Orca at `PENGUIN_SLICE_ORCA` or `tools/orca`. |
| `slice.orca_unstartable` | slicing | Orca is there but will not start (not executable, another architecture), or exits 126 or 127 with no `result.json` (the loader could not load a library it needs). |
| `slice.timeout` | slicing | Orca took longer than `PLATE_SLICE_TIMEOUT_S`; the service stopped it, and the stop is what ended Orca, before its sliced file was complete. On a plate of one instance the remedy is to simplify or split the part, with no action. |
| `slice.cancelled` | slicing | The slice was cancelled (by a client, as abandoned, or at shutdown) and Orca is gone. |
| `slice.out_of_memory` | slicing | The memory watchdog stopped Orca at the memory ceiling before its sliced file was complete (the detail holds the measured peak); or Orca was killed and the cgroup's `oom_kill` count rose (the kernel's out-of-memory killer); or Orca printed `bad_alloc`. On a plate of one instance the remedy is to split or simplify the part, with no action. |
| `slice.orca_crashed` | slicing | Orca died on a signal that means it failed (SIGSEGV, SIGABRT, SIGBUS, SIGFPE, SIGILL, SIGTRAP, SIGSYS), also when a stop of the service's was asked at the same moment (the detail says so). |
| `slice.orca_killed` | slicing | Something else stopped Orca with a signal the service did not send (SIGKILL with the `oom_kill` count unchanged or unreadable, SIGTERM, SIGINT and the rest), also when a stop of the service's was asked at the same moment or Orca ignored the service's SIGTERM (the detail says so). |
| `slice.orca_too_close` | slicing | Orca's return code -101: Orca found that two instances' paths would meet, on a plate the placement check passed. The report names the pair from Orca's debug log when it is there (`where`: `instance`, `other_instance`; the detail lists up to 5 pairs); with supports on the sentence names the supports as the likely cause and the remedy offers turning supports off. The remedy always offers spreading the instances (or Arrange) and a second plate. |
| `slice.crosses_edge` | slicing | Orca's return code -52: an instance partly off the plate beside others on it. |
| `slice.empty_layers` | slicing | Orca refused empty layers with supports off: the report names the instance and the height, and offers `enable_supports`. |
| `slice.empty_layers_with_supports` | slicing | The same with supports on: the part must be repaired, no action. |
| `slice.no_layers` | slicing | Orca printed "No layers were detected." (an open or broken surface, a part too thin): repair in CAD. Names the part when the plate has one. |
| `slice.print_empty` | slicing | Orca printed "The print is empty." (a part thinner than the nozzle prints): check size and thickness. Names the part when the plate has one. |
| `slice.nothing_on_plate` | slicing | Orca's return code -50: no instance fully on the plate. |
| `slice.orca_failed` | slicing | Any other non-zero exit, -100 without a reason the service recognises, or a code it does not know; Orca's words are in the detail. When Orca's debug log holds warnings it reported while slicing, the sentence adds them, labelled as possibly unrelated ("It also warned, though this may not be why it failed: ..."). |
| `slice.no_output` | slicing | Orca exited 0 without writing the sliced file. |
| `slice.unreadable_output` | slicing | The sliced file is not a zip (also a directory entry asking for a zip version the reader does not know), an entry fails its checksum, a plate's sliced file has no `Metadata/plate_1.json`, or that entry has no list of objects. Worth retrying. |
| `slice.no_gcode` | slicing | The sliced file has no `Metadata/plate_1.gcode`. |
| `slice.left_off_plate` | slicing | Orca left an instance out of the sliced file. |
| `slice.output_unwritable` | saving | The slice job's folder for its sliced file (`out/` in its folder under the work folder) cannot be made or written, or a folder there already has the sliced file's name. |
| `slice.unknown_job` | fetching | The HTTP interface does not know the slice job (never, or expired, or accepted by another slice service process). |
| `slice.not_ready` | fetching | The sliced file or summary of a slice job that has not finished. |
| `slice.file_gone` | fetching | The sliced file of a done slice job is no longer on the disk (HTTP 410), for the file and the summary alike. |
| `slice.bad_request` | fetching | The HTTP interface does not offer that path (404) or that method on it (405). |
| `slice.unexpected` | slicing | Anything else: a bug in the slice service; the detail keeps the traceback. |

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
assets, and stops if `patches/orca/` holds a patch. It then installs the release beside
the installed one, in `tools/orca.next` (a staged copy of `scripts/install-orca.sh`
holding the new pin verifies the download), so a failed download or checksum changes
nothing. Only then does it rewrite the pin in `scripts/install-orca.sh`, move `tools/orca`
to `tools/orca.previous` and the new release into `tools/orca`, regenerate `profiles/`
and `profiles/catalog/` from the new Orca's own profiles, and run the upstream check,
`make test-upstream` (`tests_orca/`: every test's docstring starts with "Protects:" and
names the behaviour it pins). When the check passes, `tools/orca.previous` is removed.
When it fails, the command stops with a message that says to read the failing test's
"Protects:" line and message for what to fix, and how to go back. Nothing is committed.

Then look at:

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
| `make test-upstream` | The upstream check: the tests that run the real Orca (`tests_orca/`), one at a time, with each test's time. `make test-orca` is the same. |

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
