# Review of the slice service's two guide files

[slice/README.md](../../../slice/README.md) is close to ready for the owner: it reads from
top to bottom in one pass, its length (178 lines) suits the reader, and every figure in it
but three is in [slice/README-details.md](../../../slice/README-details.md). The single
most important thing to fix is the phase of "Asked to stop, the slice service finishes the
running slice": both guide files put it in phase 2, and
[the plan](../../plans/penguin-slicer-plan.md) (line 352), the only document this reader
has read, puts "stopping gracefully" in phase 3. After that, "To be built" in the details
file states 42 routes, headers, codes, setting names and figures as decided that
[the spec](../../specs/2026-11-25-hosted-architecture-design.md) does not decide, with
nothing marking them as proposals.

Findings: Check A 17, Check B 9, Check C 6 on the decision map's rows and 42 inventions.

Line numbers are those of the files as reviewed. "README" is `slice/README.md`, "details"
is `slice/README-details.md`, "the spec" is the frozen design, "the map" is
[decision-map.md](decision-map.md).

## Check A: README.md reads well for its human reader

Read alone, as the owner, with only the plan read before it.

- README:142-143 — "Asked to stop, the slice service finishes the running slice and waits
  for its sliced file to be fetched." (under "Phase 2, one machine") — the plan, line 352,
  lists "stopping gracefully" among the slice service's work of phase 3, and its phase 2
  list (lines 308-309) does not have it, so the reader finds the guide and the plan
  disagreeing — decide the phase once. If phase 3: move this bullet under "Phase 3, hosted
  on Railway" (and details:275-287 under "Phase 3: hosted on Railway"). If phase 2: change
  the plan's line 352.
- README:112-114 — "Two rules of the code as built change in phase 2: a slice job nobody
  follows is cancelled 120 s after its last follower left, and a finished slice job's record
  and sliced file are kept for an hour." — "To be built" changes more of the code as built
  than these two (README:41-42 "SIGTERM or Ctrl-C cancels every slice job", the
  `POST /slices` row of README:66, the limits "fixed in the code"), so "Two rules" misleads
  — replace with: "Four things stated above change, as To be built says: the two rules that
  a slice job nobody follows is cancelled 120 s after its last follower left and that a
  finished slice job's record and sliced file are kept for an hour (phase 2), the request
  that carries a whole plate's files (phase 2), and the stop that cancels every slice job."
- README:133-135 — "The route that takes a whole plate's files is removed." — the only such
  route the reader has seen is `POST /slices` (README:66), so this reads as `POST /slices`
  going away, when it stays and loses its file fields — replace with: "`POST /slices` then
  takes the plate configuration alone, and a new route takes one part."
- README:94-95 — "So a host gives one slice service process 3.5 GB with the 2,000 MB
  ceiling." — the "So" does not follow from what precedes it (2,000 MB plus 502 MB is
  2,502 MB); the reader needs the details file to see where 3.5 GB comes from — replace
  with: "So a host gives one slice service process 3.5 GB with the 2,000 MB ceiling: Orca
  at about 2,500 MB, 400 MB for the slice service itself, and a fifth more for what was
  not measured."
- README:156-157 — "A route gives the front server the log lines; new lines for slices
  near a limit (80 percent), once a minute, and every exception and refusal." — must be
  read twice: "once a minute" reads as how often the near-limit lines are written, and
  "80 percent" has no statement of what it is a percentage of — replace with: "A route
  gives the front server the log lines. Three kinds of log line are new: a warning for a
  slice that passes 80 percent of the memory ceiling or of the time limit, one line a
  minute with the memory held and the slice jobs running and waiting, and one line for
  every exception and every refusal."
- README:109 — "The real-Orca suite slices 100 spacers" — one thing with two names: line
  51 calls these tests "the upstream check" (the plan's term) — replace with "The upstream
  check slices 100 spacers".
- README:74 and 86 — "503 when the queue is full", "Waiting (`MAX_QUEUED`) | Slice jobs
  queued behind it" against README:141 "A waiting slice job" and 147 "how many slice jobs
  wait" — one thing with two names (queued, waiting), and "the queue" is used at line 74
  before the limits table explains it — use "wait" throughout: line 74 "503 when no more
  slice jobs may wait (`slice.busy`)"; line 86 "Slice jobs waiting behind the running one;
  one more gets `slice.busy`".
- README:68 — "The progress reports as server-sent events, the latest first, ending with
  the final one" — "the latest first" reads as newest-to-oldest order, which the end of the
  sentence contradicts — replace with "starting with the latest one, then each new one,
  ending with the final one".
- README:73-74 — "Every other answer is an error report with an HTTP status: 422 for a
  plate configuration a check refused, 503 when the queue is full (`slice.busy`), 404 for
  an unknown slice job." — reads as the whole list; the details file has nine statuses —
  insert "for example" after "an HTTP status:".
- README:96-97 — "a full plate of twelve Elevator Block Bottom Inners with supports on" —
  a part's name that means something only to whoever measured it — replace with "a full
  plate of twelve of the robot's largest block (the Elevator Block Bottom Inner) with
  supports on".
- README:98-99 — "The time limit is about twenty times what 150 spacers take." — "spacers"
  are first explained ten lines later (line 109), and the time is not given — replace with
  "The time limit is about twenty-five times the 9.4 s that the largest plate of small
  spacers allowed, 150 of them, takes to slice." (see Check B for the figure). The stray
  line break after "The time limit is about twenty" goes with it.
- README:88 — "Different parts on one plate, and so the upload" — "and so the upload"
  cannot be understood without the details file — replace with "Different parts on one
  plate; with the 7.5 MB of one part this bounds one submission at 188.5 MB".
- README:151-153 and 173-175 — "and the estimates", "the expected time is only within
  about a factor of two" — neither "the estimates" nor "the expected time" is in the
  plan's Terms table or defined in the README — line 153: "and the slice service's
  estimates of a plate's memory and time"; line 174-175: "the expected time that each
  progress report carries is only within about a factor of two".
- README:154 — "A quiet progress stream sends a comment line at least every 15 s." —
  "progress stream" is not in the plan's Terms table (the plan, lines 97-99, sends the
  reader to the architecture for it) and the README defines the other hosted terms but not
  this one — replace with "The stream of progress reports (`GET /slices/<job>/events`)
  sends a comment line at least every 15 s while it has nothing to report."
- README:121 — "Two new names: the **front server** ... and the **user key**" — four names
  are introduced in bold in this section (front server, user key, slice container, part
  store), and the front server is in the plan's Terms table already — replace "Two new
  names:" with "Names used below:".
- README:21-22 — "a part Orca copes with (holes, faces wound inwards, perhaps in inches)
  only warns" — "perhaps in inches" must be read twice — replace with "(holes in its
  surface, faces wound inwards, or every side under 5 mm, which may be an inch file read
  as millimetres)".
- README:5 against README:163-170 — "Everything here outside 'To be built' is true of the
  code as built." — the first three bullets of "What is not known", which stands outside
  "To be built", are about the hosted service that is not built — move those three bullets
  (lines 165-170) to the end of "To be built" under a line "Not yet known:", and leave the
  last two bullets, which are true of the code as built, in "What is not known".

Length and order. 178 lines is right. The order serves the reader except that "Where it
stands" (12 lines) comes after two reference tables; a reader who wants the state of the
component first would be served by moving it to follow "What it does". What I would cut,
because a person does not need it and the details file has it: README:54-55 ("No test of
the fast suite can hang: every wait gives up after 10 s, and a test still running after
20 s fails. The upstream check runs one real Orca at a time.", the second sentence of
which repeats the table's row); and the code constants in the first column of the limits
table (`PLATE_SLICE_TIMEOUT_S`, `MAX_RUNNING`, `MAX_QUEUED`, `MAX_INSTANCES`, `MAX_PARTS`),
keeping `PENGUIN_SLICE_MAX_PEAK_MB`, the one name a person sets.

## Check B: README.md agrees with README-details.md

Checked: every figure, name, rule and claim of built or to be built on README lines 9-175
against the details file. Everything not listed below was found and agrees.

- README:89 — "150,000 triangles, 7.5 MB" — the details file never states
  `MAX_PART_TRIANGLES` as 150,000 (it follows only from details:873-874, "150 instances ...
  22.5 million triangles in all"), and states `MAX_PART_BYTES` (7,500,084 bytes) only
  inside "To be built" (details:167). The code agrees with the README (`limits.py` lines
  13-14) — add to details:685-686, after "the triangles and bytes of one part":
  "(`MAX_PART_TRIANGLES`, 150,000; `MAX_PART_BYTES`, 7,500,084 bytes, 7.5 MB)".
- README:142-143 against the plan:352 — the phase of the graceful stop; README and
  details agree with each other (details:275) and both differ from the plan. See Check A.
- README:98-99 — "about twenty times what 150 spacers take" — details:725 says "twenty
  times" and details:700 gives 9.4 s for 150 spacers; 240 s over 9.4 s is 25.5. The two
  files agree in words and the details file disagrees with its own table — README: "about
  twenty-five times"; details:725: "about twenty-five times what 150 spacers take (9.4 s)".
  This sentence of the details file is as-built text, so the correction is the owner's to
  allow.
- README:169-170 — "and what the slice service needs beside Orca hosted" — not in the
  details file as an unknown; details:319-321 uses a known figure for it ("a host is sized
  for 400 MB of the slice service beside Orca, so 6,000 MB plus both is 6,902 MB") — either
  delete the clause from the README, or add to details:321 after "under the 8 GB": "The
  400 MB was measured without the part store and without the checks of parts on arrival,
  so it is confirmed with the measurements below."
- README:138 — "A slice job is remembered for two hours" — details:242-243 says "for two
  hours (7,200 s) after it ends"; without "after it ends" the two hours could run from
  submission — add "after it ends".
- README:73-74 — three HTTP statuses given as the list; details:457-465 has 400, 404, 405,
  409, 410, 413, 422, 500 and 503 — "for example", as under Check A.
- README:112-113 — "cancelled 120 s after its last follower left" — details:1130-1131 adds
  "or after it was submitted if none ever came", and calls the follower a "subscriber"
  throughout (details:432, 1084, 1131-1134) — README: "120 s after its last follower left,
  or after it was submitted if none ever came". The name: the spec says "follows", so keep
  "follower" in the README and note in the details file's "To be built" that the code's
  "subscriber" is the same thing.
- README:23 — "reads the memory of Orca's processes every 0.25 s" — details:910-912 adds
  two readings the README drops: at once when Orca starts, and at once after each of
  Orca's progress messages. This does not change the README's conclusion (README:92-93)
  — no change needed; listed because it is a lost exception.
- README:163-175 — the README's "What is not known" leaves out three unknowns that
  details:41-44 lists as not measured: the disk held by finished slice jobs, CPU time, and
  how many slices a host can run at once — add one bullet: "Not measured: the disk held by
  finished slice jobs, Orca's CPU time, and how many slices one host can run at once."

## Check C: nothing of the approved design was lost or changed

Checked: the 53 rows of the map whose Home is `slice/README.md` (D42 to D56, D60, D72,
D74, D76 to D78, D80 to D83, D90, D95 to D98, D100, D188, D190, D230, D253, D291, D292,
D294 to D309). Each is stated in "To be built" of the details file. 45 agree with the
spec's words; the eight rows in the six findings below do not.

### Rows changed, weakened or incomplete

- D49 (changed) — spec:158-159: "the slowest plate of the Popcorn Penguins' real parts
  took 22 seconds, a tenth of the starting time limit of 240 seconds" — details:331-334:
  "The plates the Popcorn Penguins print took at most 22.5 s of Orca's time (four-each-b
  with supports on), and the slowest plate of their parts measured, twelve Elevator Block
  Bottom Inners with supports on at a 3,000 MB ceiling, 34.3 s." — the guide corrects the
  spec's figure from the measurements (details:757 and 781): the slowest plate of the real
  parts took 34.3 s, a seventh of the limit, not 22 s, a tenth. The correction is right
  and is not marked as one — add to details:334, after "34.3 s": "(the approved design
  says 22 seconds, a tenth of the time limit; 34.3 s is a seventh)", and name D49 in the
  pull request's description as the repository's rule for a changed decision asks.
- D308 (changed) — spec:887-889: "it gains the bytes of each part and of the sliced file,
  the wait and the memory ceiling" — details:383-387: "which already carries ... the memory
  ceiling (`memory_ceiling_mb`) ... gains the bytes of each part, the bytes of the sliced
  file and how long the slice job waited before it ran" — the guide says the memory
  ceiling is already on the line, where the spec says it is gained. The code agrees with
  the guide (`plate_configuration.py` line 63) — add to details:385, after
  "(`memory_ceiling_mb`)": ", which the approved design lists as still to add", and name
  D308 in the pull request's description.
- D188 (weakened) — spec:566: "The number of parts, ... the number of instances, how long
  it waited, how long Orca ran" — details:383-387 names neither "the number of parts" nor
  "the number of instances"; the line as built lists every part and every instance
  (details:1148-1149) and carries no count — add to details:387, before "[D188, D308]":
  "It also carries the number of parts and the number of instances as figures of their
  own."
- D95 (incomplete) — spec:291-292: "This is the mockup's decision 46." — details:232-234
  states the rule and drops the reference, which the map's row keeps — add to details:234,
  after "a closed lid": " (the mockup's
  [decision 46](../docs/mockups/print-wizard/DECISIONS.md))".
- D230 and D306 (phase) — spec:681-682 and 881-882 give no phase; the plan:352 gives
  phase 3; details:275 and README:142 give phase 2. See Check A, first finding.
- D54 and D302 (extended) — spec:184-185: "how many slices are ahead of it" —
  details:266-268: "the number of slice jobs ahead of it (those running and those queued
  before it), and a new report (`sequence` plus one) is sent whenever that number changes"
  — not a loss; the counting rule and the new report are the writer's, listed below.

### What the guide states as decided that the spec does not decide

None of these is marked as a proposal; only "6,000 MB (proposed)" is. All are in the
details file. The README states none of them.

The user key (details:142-153):

- details:143 — the header's name, `X-Penguin-User-Key`.
- details:144-146 — a request about another user key's slice job answers
  `slice.unknown_job`, HTTP 404.
- details:146-147 — the list of slice jobs is the one route not scoped to a user key.
- details:148-150 — a request without the header is `slice.no_user_key`, HTTP 400, a new
  error code.

The part store (details:155-198):

- details:155-156 — the route's path, `POST /parts`, and the part as the request body.
- details:158-160 — the fit test runs on arrival against the largest printer of the
  catalog, and again against the plate configuration's printer.
- details:161-164 — the answer: HTTP 201 with the hash in hexadecimal, the part's
  measurements and its warnings.
- details:164-165 — the same bytes sent again answer the same and count as a use.
- details:167-169 — a body over `MAX_PART_BYTES` is `slice.part_too_detailed`, HTTP 413,
  refused before it is read (the 7.5 MB is the spec's).
- details:170-172 — a part's upload counts as a use (the spec counts each slice that names
  it), and the job pool's sweeper removes expired parts every 10 s.
- details:176-178 — the disk limit is a setting of the slice service, with no default.
- details:184-185 — a slice job takes its own link to each part's file when accepted.
- details:188-190 — the checks' refusals through `POST /parts` are HTTP 422; a part store
  that cannot be written is `slice.scratch_unwritable`, HTTP 500.

A plate configuration names parts by hash (details:200-216):

- details:200-203 — `POST /slices` takes a JSON body of at most 1 MB.
- details:207-209 — the error's code `slice.part_missing`, stage `checking`, HTTP 422,
  action `refresh_parts`, its detail and `where` listing the hashes.
- details:215 — a multipart body is refused.

One unfinished slice job per user key (details:218-230):

- details:221-224 — the earlier slice job's final report is `cancelled` and says it was
  replaced; `"cancel_reason": "replaced"` in its log lines.
- details:224-226 and 229 — the earlier slice job gives up its place before the new one
  is counted, so a user key that resubmits while no more may wait is not refused.

Remembering and deleting (details:242-254):

- details:244-246 — the front server says it has stored the sliced file with
  `DELETE /slices/<job>/file`; the record stays until it expires.
- details:246-247 — a sliced file never collected goes with its record.
- details:248-254 — `slice.file_gone` (HTTP 410) after the delete; the delete on a slice
  job not done is `slice.not_ready` (HTTP 409); a second delete answers as the first.

The list of slice jobs (details:256-262):

- details:256-258 — the route's path, `GET /slices`, and what each entry holds (id, user
  key, latest progress report, whether the sliced file is on the disk).

How many are ahead (details:264-273):

- details:266-268 — the number counts those running and those queued before it, and a new
  progress report is sent whenever it changes.

Stopping (details:275-287):

- details:275-280 — after the stop the slice service refuses new slice jobs with
  `slice.busy`, cancels the queued ones with `"cancel_reason": "shutdown"`, keeps the HTTP
  interface answering until the sliced file is fetched and deleted, and exits 0.
- details:280 — a second SIGTERM or Ctrl-C cancels the running slice job.
- details:137-140 and 275 — that this, the list of slice jobs, the two hours and the count
  of those ahead are built in phase 2 (the spec gives no phases; the plan names four items
  for phase 2 and puts the stop in phase 3).

The limits as settings (details:291-309):

- details:300-302 — the settings' names, `PENGUIN_SLICE_TIME_LIMIT_S`,
  `PENGUIN_SLICE_MAX_RUNNING`, `PENGUIN_SLICE_MAX_WAITING`.
- details:295-296 — a bad value is refused at start with exit status 2.

The memory ceiling (details:311-328):

- details:318-321 — the sum 6,000 MB plus 502 MB plus 400 MB is 6,902 MB, under the 8 GB.
  The spec gives only "leaves 2 GB".
- details:324-326 — the rule in the docstring of `jobs.py` is replaced.

The measurements (details:330-350):

- details:342-344 — the models are refitted on these runs with
  `scripts/measure_plate.py --fit`.
- details:344-348 — `limits.MEASURE_STOP_MB` (3,072 MB) must rise above the hosted
  ceiling, and the models' constants are replaced.

The comment line (details:352-358):

- details:354 — the comment line's text, `: keep-alive`.
- details:355-357 — it replaces the repeat of the latest progress report every 15 s.

Orca's Unix user and the image (details:360-375):

- details:362-363 — the slice container's image makes the user and the slice service
  starts Orca as it.
- details:364-365 — an Orca that cannot be started as that user is
  `slice.orca_unstartable`.
- details:370-371 — the image is built after `make upgrade-orca` passes (the spec names
  only the upstream check).
- details:372-375 — the image installs the distribution's packages, and its build runs
  `make test-upstream`.

The log (details:377-403):

- details:379-382 — the route's path, `GET /log`; the sequence number the front server
  passes back; the bounded buffer in memory; each line also on stderr.
- details:390 — "a peak over 4,800 MB or Orca running over 192 s" (derived from the
  spec's 80 percent, 6,000 MB and 240 s).
- details:391-392 — the once-a-minute line counts the memory of the slice service process
  and its Orcas together.
- details:403 — a full buffer drops the oldest line and counts it.

The fix for all of them is one sentence at details:63, after the sentence about the ids
in brackets: "Where an item names a route's path, a header, a setting, an error code, an
HTTP status or a figure that the approved design does not give, that name or figure is
this guide's proposal, and the phase's own design spec may change it." The two changes of
substance among them, which deserve the owner's eye apart from that sentence, are that a
part's upload counts as a use (details:170-171) and that a user key which resubmits is
never refused for lack of room (details:224-226, 229).
