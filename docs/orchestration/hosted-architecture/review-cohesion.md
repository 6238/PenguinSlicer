# Cohesion review: the hosted architecture design

Reviewed: [the hosted architecture design](../../specs/2026-11-25-hosted-architecture-design.md),
read once from the first line to the last as a reader who has read
[the plan](../../plans/penguin-slicer-plan.md) and nothing else. Line numbers are those of
the design document as it stood on Fri 2026-11-27 (Pacific).

## Verdict

The document reads as one design for most of its length: the Short answer, the Terms
table, the walk-through, "Restarts and deploys" and the state table agree on almost every
figure (two hours, thirty days, 55 seconds, 10 and 40 seconds, fifteen minutes, 25 parts,
6,000 MB, 240 seconds), and the forward and backward references all point the right way.
The patching shows in three places: the "Printers" section, where two passages sit under
headings that no longer fit them ("send" and unpairing under "Pairing", and "Progress
streams", which is about slices as much as prints); the claim "nothing in the state
bucket can start a print", which is stated three times without the qualifications that
other sections give it; and the opening paragraph, which gives the review history before
it says what the document is. None of the findings overturns the design, and the ones
under "Contradictions" and "Seams" are worth fixing before the final read, because each
would make a careful reader stop and go back.

## 1. Contradictions

- **Lines 52, 426 and 736 against 640 and 645 to 649.** "nothing in the state bucket can
  start a print" (52); "so nothing in the state bucket can be used to start a print or to
  pose as a daemon" (426); "**Nothing stored can start a print.**" (736). But line 640
  says a daemon "receives the delivery job from its record in the state bucket", and
  lines 648 to 649 say the record "holds whether that was allowed" to start. So a
  delivery-job record in the state bucket is exactly what starts a print: whoever can
  write the state bucket can plant one. The three statements are true only of what
  someone who *reads* the state bucket learns. Fix, at all three places: "nothing read
  from the state bucket lets anyone start a print or pose as a daemon". At line 736 add:
  "Someone who can write the state bucket could plant a delivery-job record, which is why
  only the front server's credential and the project's owner can write it."
- **Line 426 against lines 417 and 737.** "so nothing in the state bucket can be used ...
  to pose as a daemon" is unqualified, but step 2 (line 417) puts "a hash of the code" in
  the paired-printer record, and line 737 says so with the qualification "only until its
  daemon has its token". Fix at line 426: append "once the daemon has its token; until
  then the record holds a hash of the code (see [Security](#security))".
- **Line 73 (Terms) against lines 417 and 768.** The Terms table defines the
  paired-printer record as "the id of the group's daemon, the printer's display name, who
  paired it and when". Line 417 adds "a hash of the code" and line 768 adds "which key
  its daemon's token was last issued under". Fix at line 73: "... who paired it and when,
  which of the relay's secret keys the daemon's token was last issued under, and, until
  the daemon has its token, a hash of the pairing code."
- **Line 640 against lines 116 and 207.** "It fetches the sliced file from the state
  bucket." A daemon holds no bucket credential (line 116: "The front server holds the one
  credential"), and step 6 (line 207) says "through the front server". Fix: "It fetches
  the sliced file through the front server, which reads it from the state bucket."
- **Line 59 against lines 761, 775 to 778 and 780 to 781.** Short answer: "Every secret
  can be replaced without interrupting anyone." The Security section says only a
  *planned* replacement interrupts nobody, that a daemon switched off for the week is
  paired again, that a user away for the week signs in again, and that an emergency
  replacement makes everyone sign in or pair again. Fix at line 59: "**Every secret can
  be replaced, and a planned replacement interrupts nobody** who uses PenguinSlicer
  within a week of it."
- **Line 601 (state table) against lines 287 and 318 to 322.** Row "Parts, layout, chosen
  settings, the current group, the id of the plate's slice job and when it was
  submitted", column How long: "Until its sliced file expires". "its" has nothing to
  refer to; the current group does not expire with a sliced file; and line 287 says the
  page drops the stored parts when it is next opened, not at expiry. Fix: "Until the
  page, on opening, finds the plate's sliced file expired; the current group, until the
  user changes it".
- **Lines 274 to 275, 601 and 898 list the browser's storage three ways.** Line 274:
  "the parts, the layout, the id of the plate's slice job and the time it was submitted";
  line 601 adds "chosen settings, the current group"; line 898 has only "the parts, the
  layout and the slice job's id". Fix: use line 601's list in all three (at 274 "the
  parts, the layout, the chosen settings, the id ..."; at 898 "the parts, the layout, the
  chosen settings, the current group, and the slice job's id and time of submission").
- **Lines 765 to 770 against line 748 and line 761.** "There are six" secrets and "Every
  secret can be replaced", but the replacement table has four rows. The row "The buckets'
  credentials" covers secrets 4 and 5 yet says the new credential is "given to the front
  server", which is false of the read-only one (line 757: it "reaches a coding agent").
  Secret 6 has no row. Fix: reword the row to "... given to the front server, or for the
  read-only credential to the project owner's secrets, and the old one is then
  cancelled", and add a row "The project owner's sign-in to Cloudflare | Changed at
  Cloudflare; nothing in PenguinSlicer holds it".
- **Line 442 against line 452.** "**Everything the daemon needs is in one settings file
  on its computer**" and then "The daemon keeps a note of the print it started". The note
  is a second thing kept on the computer. Fix at line 452: "The daemon keeps a note of
  the print it started, in a file beside its settings file, so ..." (or say it is in the
  settings file, whichever is meant), and at 442 "Everything the daemon needs to
  reconnect is in one settings file".
- **Line 714 against lines 549 and 591.** "Log lines carry a part's name, size and
  measurements, never its geometry." "Measurements" appears nowhere in "Reading what
  happened", which lists "the number of parts and the bytes of each" (549) and "part
  names" (591). Fix at line 714: "Log lines carry a part's name and its size in bytes,
  never its geometry."
- **Line 499 against lines 489 and 498.** A stale delivery job may be given up, "which
  frees the printer for the next send while the print may still be running". Line 489
  says "The relay refuses a send to a printer that is printing", and a daemon silent for
  2 minutes makes Send disabled (498). The reader cannot tell what "frees" means, because
  the rule it depends on (one delivery job for a daemon at a time) is never stated. Fix:
  "... which lets the relay accept the next send once the daemon is back and the printer
  is idle; until then a daemon holds one delivery job at a time".

Checked and found consistent: every duration and size (two hours for parts, slice jobs
and sliced files; one day for delivery-job records; thirty days for the cookie; fifteen
minutes and thirty seconds for pairing; 55 seconds, 10 seconds, 40 seconds and 2 minutes
for syncs; seven and ninety days for logs; 7.5 MB, 25 parts, 6,000 MB, 8 GB, 240
seconds); the 80 calls (20 users, 2 sign-ins in two months, 2 calls each); both restart
tables against the state table and the "Coming back" table; the two lists of changes
against the body, except as reported under 3.

## 2. Order

- **Line 430, "A send is the request by which a user's page asks the relay to print a
  sliced file, which creates a delivery job."** This definition arrives after "send" has
  been used as a noun at lines 53, 80, 206, 248 and 256. Fix: move the sentence to the
  Terms table as a row "**send**", placed before "sync", and delete it at line 430.
- **Line 339, "The cookie holds the user's identity, groups and Onshape tokens".** The
  Sign-in section never says that a sign-in sets a cookie; "the cookie" has so far
  appeared only in passing at line 321. Fix: begin the paragraph "A sign-in sets one
  cookie in the browser. It holds the user's identity, ...".
- **Line 286 against lines 291 to 293.** The table row "Cancelled by a later slice of the
  same user" relies on the rule "A user has one unfinished slice job at a time", which is
  stated only after the table. Fix: move the paragraph at lines 291 to 293 to stand
  before the paragraph at line 274.
- **Lines 471 to 476 against 478 to 492.** The table of how often a daemon syncs comes
  before the two paragraphs ("The held wait", "Nothing is held during a print") that
  explain its first and third rows, so its first row has to carry the whole explanation
  in a cell. Fix: see the second finding under 3, which removes the repetition and lets
  the table stand as a summary.
- **Line 692, "Each row of the two tables above".** The tables are two subsections back,
  with "What makes a deploy cheap" and "Old and new versions together" between. Fix:
  "Each row of the two tables under [What a restart does](#what-a-restart-does)".

Checked: every "see", "below" and "above" (lines 321, 337, 341, 381, 448, 597, 711, 738,
739, 795, 797) points in the right direction. Terms the Terms table does not hold
(printer-status icon, daemon telemetry, upstream check, the slice service's estimates,
the Send, Preview and Parts steps, the standing requirement Cleanup) are in the plan.

## 3. Seams

- **Lines 430 to 435, under "### Pairing".** One paragraph defines a send, says when it
  is accepted, how long a delivery job's record is kept, and what unpairing does. None of
  it is pairing, and the reader looking for "what happens on Send" or "how do I unpair"
  will not look here. Fix: put it under a new heading "### Sending and unpairing" after
  line 428, as two paragraphs (sending and the delivery job's record; unpairing), with
  the definition of "send" moved to Terms as under 2. Also line 432, "a paired-printer
  record naming the daemon": no daemon has been named in this sentence; write "a
  paired-printer record, and the delivery job goes to the daemon it names".
- **Lines 516 to 522, "### Progress streams" under "## Printers".** The section is about
  the browser following "a slice job and a delivery job", and it is needed from phase 2,
  before any printer. Fix: move it out of "Printers" to the end of "The shape" (after
  "How many slices at once"), where the Cloudflare and Railway limits it cites are first
  introduced.
- **Lines 473 and 478 to 483: the held wait explained twice in a row,** after the Short
  answer (53 to 55) and the Terms table (80) have already given it. The table cell and
  the paragraph say the same four things, and line 482 to 483 repeats the Short answer's
  sentence. Fix: cut the cell at line 473 to "Once for each held wait: the relay answers
  when a delivery job arrives, or after 55 seconds, and the daemon syncs again at once |
  A send reaches the daemon immediately; about one request a minute", and cut the last
  sentence of the paragraph ("So an idle daemon ... never waits.").
- **Lines 245 to 246.** "... collects each finished one it has not yet stored. From then
  on the state bucket's is the copy everything uses". "From then on" used to follow "stores
  it in the state bucket"; with the restart clause patched in between it now reads as
  "from the front server's start". Fix: move "When the front server starts, it asks the
  slice service for its slice jobs and collects each finished one it has not yet stored."
  to the end of the paragraph, after line 250.
- **Lines 3 to 11, the opening paragraph.** It gives the review history first and what
  the document is second, and the join is "... nor agreed the document. It says how the
  wizard ...". Line 7, "how a secret is replaced on that day", leaves the reader asking
  which day. Fix: make "It says how the wizard, the slice service and printer delivery
  fit together ... It gives no time estimates." the first paragraph (beginning "This
  document says how"), and the history a second, shorter paragraph: "Written Wed
  2026-11-25 and revised Thu 2026-11-26 (Pacific). The project's owner has reviewed ...;
  decided, on Thu 2026-11-26, how often a daemon talks to the relay, what the log holds
  and how a secret is replaced; and has not yet read "Printers", "Reading what happened"
  or "Security" as written."
- **Line 121, "Railway's machines are believed to be x86_64."** A stray sentence between
  two about memory and about containers staying running; it answers nothing at that
  point and is repeated where it matters (line 152) and under "To confirm" (line 944).
  Fix: delete it at line 121.
- **Lines 842 to 843, "empties its folders at start, and bounds the disk the part store
  may take".** A bound on the part store's disk appears only in this list of changes; the
  body gives only 25 parts for one user key (234, 700 to 702), which bounds one user, not
  the disk. The lead (lines 16 to 17) says the body describes the whole design. Fix: add
  to "Parts", after line 236: "The part store also has a limit on the disk it may take in
  all; past it, the least recently used parts of any user key are removed. The slice
  service empties the part store when it starts."
- **Lines 620 and 651: two different lists both introduced as "Two things".** "Two things
  can take longer than the pause itself" (a cut-off slice, a pairing code) and "Two
  things are lost at a restart" (a minute of log lines, a slice whose file was not yet
  stored) sit thirty lines apart in one section, and the second list's slice is a case of
  the first list's slice. Fix at line 651: "Beyond those, a crash (not a deploy) loses
  the last minute of log lines, which stays only in Railway's log view, and a slice whose
  sliced file the front server had not yet stored, which runs again."
- **Lines 909 to 925, "## By phase".** The section assigns most of the design to a phase
  but leaves two parts unassigned: replacing secrets (two keys for the cookie, two for
  the relay) and "Old and new versions together". Line 920 also lists "the buckets, ...
  the log bucket". Fix: in Phase 3 write "the state bucket and the log bucket, Onshape
  sign-in, two keys for the cookie, the rules of
  [Old and new versions together](#old-and-new-versions-together), the command that
  reads the log bucket, ..."; in Phase 5 add "replacing the relay's secret key".

## 4. One name per thing

- **"the relay's records" names two things.** At lines 74 and 870 to 871 it is the
  relay's in-memory table of daemons (by daemon id); at lines 645, 801, 873 and 925 it is
  the delivery-job records in the state bucket. Fix: at line 74 write "in the
  paired-printer record and in the relay's memory"; at 645, 801, 873 and 925 write "the
  records of delivery jobs" (801: "Sliced files, the paired-printer records and the
  records of delivery jobs are kept in the state bucket").
- **"a send", "a print" and "a delivery job" for the same thing.** Line 54, "until it has
  a print to hand over"; line 467, "tell the daemon about a print"; line 640, "A send was
  waiting for its daemon". By line 430 a send is the request and a delivery job is what
  it creates. Fix: line 54 "until it has a delivery job to hand over"; line 467 "tell the
  daemon about a delivery job"; line 640 "A delivery job was waiting for its daemon".
- **"reports", "spoke", "heard from" for "syncs".** Line 55, "During a print the daemon
  reports every ten seconds"; line 498, "Heard from in the last 2 minutes"; line 499,
  "The daemon spoke in the last 40 seconds". Fix: "syncs every ten seconds"; "Its last
  sync was within 2 minutes"; "Its last sync was within 40 seconds".
- **"the owner of the Cloudflare account" (lines 117, 712) and "the project's owner"
  (315, 755) are one person.** A reader meets the first as if it were someone else. Fix
  at 117 and 712: "the project's owner, through Cloudflare's own console".
- **"queue" (lines 538, 702) for the slice jobs that wait.** "How many slices at once"
  never uses the word; it says "how many slice jobs may wait". Fix: line 538 "no room to
  wait for a slice"; line 702 "cannot fill the slice container's waiting places or its
  disk".
- **"the user" and "the user key" in log lines.** Line 534 "the user, the group"; line
  560 "the user and their groups"; line 576 "the user key"; line 312 "the user's name";
  line 591 "users' names". The reader cannot tell whether a line carries the Onshape id,
  the name, or both. Fix at line 576: "the group, the user key and the user's name, ...",
  and at 534 and 560 write "the user key and name".

Checked and consistent: group, current group, front server, slice container, slice
service, state bucket, log bucket, part store, daemon id, development identity, held
wait, memory ceiling, time limit, sliced file, printer-status icon, daemon's token
against Onshape tokens.

## 5. History in the body

- **Lines 396 to 398.** "The test is the setting and not the address it listens on,
  because a front server in a development container must listen on every address for a
  browser on the same computer to reach it." This answers an option (detect development
  by the listening address) that the document never raised. Fix: delete the sentence.
- **Line 925, "the chosen syncs with the held wait".** "chosen" refers to a choice among
  options the reader was not shown. Fix: "the syncs and the held wait".
- **Lines 151 to 152.** "the starting time limit, 240 seconds, is twenty times what a
  plate of 150 small spacers took" explains where the figure in the code came from, not
  why the design keeps it; see the first finding under 6 for the fix.

Checked: the remaining mentions of the present (the measurements at 144 to 152 and 252,
Chrome's storage at 296, the owner's intent at 350, "Until they exist" at 314, the later
options at 456 and 512) support a statement of the design and are not history. "As
built" appears only in the two lists of changes and "To confirm".

## 6. Weight and length

- **Lines 148 to 157, the time-limit paragraph, has to be read twice.** It gives two
  measurements (22 seconds, and a spacer plate whose time must be worked out as 12
  seconds), then "both figures", which after two times reads as those two but means the
  memory ceiling and the time limit. Fix: "What is known about time: the slowest plate of
  the Popcorn Penguins' real parts took 22 seconds, a tenth of the starting time limit of
  240 seconds. That was measured on aarch64 machines, not Railway's x86_64, and on plates
  far lighter than 6,000 MB; a plate that heavy will take longer. So the memory ceiling
  and the time limit are both settled by one set of measurements on the slice container
  ...".
- **Lines 243 to 246: how the front server learns that a slice has ended is too thin to
  decide from.** "It does this whether or not a page is open" carries the whole
  mechanism, on which the "Coming back" table and both restart tables rest. Fix: add one
  sentence saying how (for example "The front server follows every unfinished slice
  job's progress stream itself, whether or not a page is open"), whichever is intended.
- **Line 402, "Safari is not supported."** No reason is given and it is unclear whether
  it means inside Onshape's panel only or everywhere. Fix: add the scope and the one
  fact behind it in the same sentence.
- **Lines 775 to 778.** One sentence carries the daemon's limit, the consequence for the
  daemon and the consequence for a user of the cookie's key. Fix: "So a daemon switched
  off for the whole week after the relay's secret key is replaced must be paired again.
  Likewise a user who does not open PenguinSlicer in the week after the cookie's key is
  replaced signs in again."
- **Lines 676 to 678.** "Every change keeps three of them working. This is a rule for
  each change, and the one most easily broken by accident." "three of them" reads as
  three out of more. Fix: "Every change must keep three kinds of thing working; of the
  rules here it is the one most easily broken by accident."
- **Line 612, "Kept, but for the last minute before a crash, which is only in Railway's
  log view, for seven days".** "but for" is read first as "but, for". Fix: "Kept, except
  the last minute before a crash, which stays only in Railway's log view (seven days)".
- **Lines 824 to 854, the slice service's list of changes.** Thirteen bullets, three of
  which join unrelated changes (842 to 843: the Unix user, emptying folders, the disk
  bound; 846 to 848: deleting the sliced file, the part store's twenty-sixth part; 849
  to 853: the log route and four additions to log lines), and the two-hour change (854)
  is separated from the part store it belongs with. Fix: a table with columns "Area |
  As built | To be", one row per change, grouped as part store, slice jobs, limits,
  stopping and restart, logs.

Checked: no section is out of proportion otherwise. "How often a daemon talks to the
relay" is the longest subsection and is the one the owner decided on.

## 7. The four lenses

- **Lens 1 (agrees with itself):** covered under 1 and 4; nothing further.
- **Lens 2 (nothing assumed):** covered under 2. One more: line 271 and line 287 cite
  "the mockup's decision 46" and "decision 48" by number. Line 268 to 270 states what
  decision 46 says, so it passes; line 287 states what decision 48 says, so it passes.
  Line 128 to 129, "after the upstream check passes": defined in the plan (its line 74).
  Pass otherwise.
- **Lens 3 (facts that matter, in prose):** one finding. Line 827, "of up to 188.5 MB":
  a figure with no statement of what it is made of, in a list of changes where it
  supports nothing. Fix: delete "of up to 188.5 MB", or write "(25 parts of 7.5 MB and
  the plate configuration)".
- **Lens 4 (each thing explained once):** the held wait, reported under 3. The document
  is a single main document with one prerequisite and no document map; the only content
  it shares with the plan is by reference. Pass otherwise.
