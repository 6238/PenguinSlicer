# Review by the four lenses, third round: the hosted architecture design spec

Reviewed Thu 2026-11-26, Pacific time. The main document under review is
[the hosted architecture design spec](../../specs/2026-11-25-hosted-architecture-design.md),
called "the spec" below. Its declared prerequisite is
[the plan](../../plans/penguin-slicer-plan.md), which was read as the front door and not
reviewed. A change the spec declares under "What this changes in the plan" or "What
changes in each component" is not reported as a disagreement. The reader is the project's
owner, who knows the plan, reads the spec from top to bottom, was not present when it was
written, and decides from it.

Besides the four lenses, three checks the owner asked for are reported: top-to-bottom
order, the body describing the design as it is to be, and internal contradictions. The
internal contradictions are the findings of Lens 1; the other two checks have sections of
their own after Lens 4.

In each finding, `SPEC` stands for
`/repos/popcornpenguins/penguin-slicer/docs/specs/2026-11-25-hosted-architecture-design.md`
and `PLAN` for `/repos/popcornpenguins/penguin-slicer/docs/plans/penguin-slicer-plan.md`.
Where a finding says a claim was checked against the code, the source is the slice
service's guide (`slice/README.md`) or printer delivery's guide (`delivery/README.md`).

## Lens 1: the set agrees with itself (and the internal contradictions check)

Checked: every figure, duration and holder of state in the Short answer, the Terms table,
the walk-through, the table "All of it, in one table", "Restarts and deploys", "Sign-in",
"Printers", "Security", "What changes in each component", "By phase" and "To confirm
before building on it" against each other; the spec's terms against the plan's; the scope
the opening states against what the body decides; and the list "What this changes in the
plan" against the plan.

- SPEC:372 — "The paired-printer record is already in the state bucket, and the daemon gets its token when it next offers its code" — after a restart the relay's memory of who offered which code is gone (SPEC:344), so the token is issued on the strength of the record plus a daemon id that the record itself holds, which contradicts "nothing in the state bucket can be used to start a print or to pose as a daemon" (SPEC:520, and SPEC:47, SPEC:714): whoever reads the record can offer that daemon id and be given a token — say what the daemon must present besides its daemon id to be given the token after a restart (for example the code, checked against a hash kept in the record until the token is issued), or have the user type the code again and change the row.
- SPEC:324 — "a document the project's owner writes into the state bucket by hand" — SPEC:137 says "Only the front server holds a credential that writes to them", SPEC:690 says "the only credential that reads it is the front server's", and the list of secrets (SPEC:727 to 731) has no credential for the owner — say with which credential the owner writes the document and add it to the list of secrets, or give the owner a command that goes through the front server.
- SPEC:683 — "Every limit on the rate of requests is counted for the signed-in user or the daemon" — SPEC:437 limits the pairing offer to "sixty a minute for the whole relay", which is counted for neither (the same limit is in the code today, `EXCHANGE_LIMIT`), and one stranger posting offers without a token can use it up and stop every pairing — name the offer's limit as the exception in "Security" and in SPEC:811, and say what keeps a stranger from exhausting it.
- SPEC:352 — "Nothing a user did has to be done again" — the restart table at SPEC:373 has a user who typed a pairing code "told ... to try again in a moment", and SPEC:360 restarts a slice from the beginning, which costs the user up to the 240-second time limit again — state the two exceptions in the rule, or change the rows.
- SPEC:351 — "A user may see a pause of a few seconds" — the same figure is in the Short answer (SPEC:38, "connections drop for a few seconds"), but SPEC:371 leaves the printer-status icon and the Send step blank "until the daemon's next sync", which is up to 30 or 60 seconds under two of the choices of SPEC:636 to 640, SPEC:373 gives half a minute for pairing, and SPEC:857 to 861 says how long Railway takes to stop and start a container is not known — give the pause as what it depends on (Railway's restart time and the idle sync interval), not as "a few seconds".
- SPEC:381 — "if both containers restart in the seconds between a slice ending and the front server storing its sliced file, that slice runs again" — the slice container alone crashing in those seconds loses the sliced file, since it empties its folders at start (SPEC:788), and the front server alone restarting loses nothing, since it lists the slice jobs it must still collect (SPEC:778) — write "if the slice container crashes in the seconds between".
- SPEC:395 — "closes its progress streams and held waits" — the held wait is "One of the choices not yet made" (SPEC:73) and SPEC:550 says the section "decides nothing", yet here, at SPEC:813 and at SPEC:888 ("fifty held waits") it is written as part of the design — write "and its held waits, if that choice is made" in each place.
- SPEC:335 — "Until the plate is sent or its sliced file expires" — SPEC:269 lets a sliced file be "sent, and sent again after a print", and SPEC:298 opens a page whose plate has a delivery job on the Send step, both of which need the browser's stored plate after it was sent — drop "the plate is sent or" or say what is kept after a send.
- SPEC:682 — "the part store holds at most 25 parts for one user key" — SPEC:247 says a part stays "for two hours after it was last used", so a user who builds a second plate from different parts within two hours passes 25, and the spec does not say which rule gives way — say that the least recently used part is removed (the page uploads it again if a plate names it), or that the upload is refused and with what error.
- SPEC:687 — "A part exists on the server only in the slice container" and SPEC:688 "A sliced file is in the state bucket" — the slice container also holds each sliced file it made, and nothing says for how long after the front server fetched it; checked against the code, the slice service keeps a finished slice job's sliced file for an hour (`RECORD_TTL_S`), and "What changes in each component" does not change that; the table at SPEC:333 to 345 has no row for it — say when the slice container deletes its copy, add the row, and add the change to the slice service's list.
- SPEC:344 — "While the daemon keeps offering" — SPEC:517 says "A code is good for fifteen minutes; a daemon still unpaired then makes a new one" — write "Fifteen minutes at most, while the daemon keeps offering".
- SPEC:339 — "Two hours after the slice ended" — SPEC:271 to 272 keeps a sliced file a delivery job needs "until the daemon has fetched it", and SPEC:276 to 277 lets one rest at R2 for about two days; the Short answer (SPEC:33) also says only "for two hours", and for a part that is "two hours after last use" (SPEC:247) — add "or until the daemon has fetched it" to the row, and write the Short answer as "for two hours after its last use".
- SPEC:45 — "no others until the app is public" — the table at SPEC:458 has reading parts in phase 4 cost "several for each part", SPEC:460 says "until phase 4", and SPEC:472 to 473 has "sign in again" cost two calls — write "no others until phase 4".
- SPEC:783 — "The rule that cancels a slice job nobody has followed for 120 seconds is removed." — this overturns the plan's standing requirement Cleanup ("When a client goes away without cancelling, the component notices, waits a stated time ... then stops the work", PLAN:169 to 170), and "What this changes in the plan" (SPEC:75 to 101) does not list it, although SPEC:12 to 14 promises every difference from the plan is stated there — add a bullet: a slice job goes on without its page, bounded by the time limit, and the Cleanup requirement is amended for slice jobs.
- SPEC:18 — "of the security questions under phase 5 those about who may send to a printer, the pairing code, the relay's secret key and showing who sent a print" — the spec also answers the plan's question of what the daemon stores on the daemon's computer (PLAN:410 to 411) at SPEC:533 to 535, and it is in neither the "answers" list nor the "leaves" list — add it to the "answers" list.
- SPEC:176 — "plates of the Popcorn Penguins' real parts took 3 to 11 seconds" — checked against the slice service's guide, whose table of the Popcorn Penguins' real parts gives 0.1 to 21.7 seconds of Orca's time (`slice/README.md`, lines 390 to 405); 3 to 11 matches no row range there — give the range the guide gives, or name the plates the figure is for.
- SPEC:4 — "revised Fri 2026-11-27 after the owner's review" — this review was written Thu 2026-11-26 at 16:41 Pacific time, so the date is a day ahead; it is the UTC date — write "Thu 2026-11-26".
- SPEC:404 — "A deploy replaces the server and nothing else" — "the server" names no one thing in a design with two containers: it is the front server here and at SPEC:46 and SPEC:463, both containers at SPEC:32 ("The server keeps a copy of each part and each sliced file") and SPEC:208, and "the slicer" at SPEC:683 is a fourth name for the slice container — write "front server", "slice container" or "the two containers" in each place.
- SPEC:140 — "Railway's Hobby plan" — SPEC:870 calls the same thing "its cheaper plan", and "plan" otherwise means the project's plan — write "Railway's Hobby plan" in both places.
- SPEC:524 — "A send is allowed when" — "a send" (also SPEC:370, SPEC:590, SPEC:595) is not a term of the spec or the plan, and the reader cannot tell whether it is the delivery job or the request that creates one — define it in one sentence at first use, or write "a delivery job is accepted when".
- SPEC:296 — "the earlier plate's slice has expired" — everywhere else "slice" is the work and "sliced file" is what expires — write "the earlier plate's sliced file has expired", unless these are the words the user reads, in which case put them in quotation marks.

## Lens 2: nothing is assumed beyond the declared prerequisites

Checked: every abbreviation, term and label in the spec against the spec's Terms table,
its text up to the point of use, and the plan's Terms table. The plan's terms pass.
Railway, Cloudflare, R2, the Hobby plan and server-sent events are explained at first use
or are common knowledge for this reader. The mockup's decisions 46 and 48 are now linked
and paraphrased. Terms used before their explanation are reported under "Top-to-bottom
order" below.

- SPEC:377 — "whether the daemon was already allowed to start the print" — that the daemon asks the relay's leave before it sends the start command is not explained in the spec or the plan (printer delivery's guide calls it the start gate), so the reader cannot see why a record of it prevents a second start — add one sentence: before sending the start command the daemon asks the relay, which grants it once for each delivery job.
- SPEC:870 — "and x86_64 machines" — the body never says that Railway's machines are x86_64 or that the design depends on it; SPEC:178 says only "a different kind of machine from Railway's" — say at SPEC:178 that Railway's machines are believed to be x86_64 and every measurement is from aarch64.
- SPEC:300 — "A user has one unfinished slice job at a time" — the table of answers at SPEC:291 to 296 has no row for a slice job that ended in an error or was cancelled by the user's later slice in another tab or in Onshape's panel, so the reader cannot tell what a returning page shows, or whether two pages resubmit against each other without end — add the two rows.

## Lens 3: the facts that matter, in prose

Checked: each conclusion for the fact behind it, each figure for a statement of what it
measures, and each passage of figures or names for a sentence saying what they show. The
spec has no details file and no passage that needs moving to one.

- SPEC:524 — "A send is allowed when the signed-in user's current group has a paired-printer record naming the daemon." — the current group is "kept in the browser" (SPEC:329), and nothing says the front server checks it against the groups in the cookie, so the conclusion "nobody outside a group can reach its printer" (SPEC:707) and the same for a group's configuration have no fact behind them; SPEC:692 gives that fact for the user key only — add: the front server accepts a current group only if the cookie lists it.
- SPEC:460 — "twenty people using the hosted service for two months spend about 80 calls" — the figure assumes renewing a token is not a call, which SPEC:874 lists as unchecked, while SPEC:441 renews the access token each hour; if a renewal counts, one user with a page open spends up to 24 calls a day and 2,500 a year is gone in weeks — say that tokens are renewed only when a call to Onshape needs one (none does before phase 4), or give the figure for the case where a renewal counts.
- SPEC:342 — "Until a day after the delivery job ends" — the figure appears only in this row; no text says what it is for or what reads a delivery job's record after the job ends — add one sentence in "Printers" (what the Send step and the printer-status icon show from the record after a print ends) or remove the figure.
- SPEC:267 — "A sliced file is 8.8 to 14.1 MB on the plates measured so far." — the figure supports no stated conclusion (also reported in the second round) — say what it shows (for example that a fetch by the browser and by the daemon are each small against Cloudflare's 100 MB), or remove it.
- SPEC:336 — "Thirty days" and SPEC:345 "Ninety days" — neither duration has a reason, and the thirty days decides both how many calls to Onshape a user costs (SPEC:456) and how long a removed user keeps a printer (SPEC:468 to 469) — give one sentence for each on why that figure.
- SPEC:585 — "Each limit is a few times the interval it watches." — the online limit is 2 minutes against a 5-second interval, twenty-four times (checked against the code: `STATUS_ONLINE_SECONDS` 2 min, `SYNC_INTERVAL` 5 s), which is why SPEC:642 can allow a 60-second idle sync without raising it — write "the stale limit is four times its interval and the online limit twenty-four times".

## Lens 4: each thing explained once

Lens 4: pass. Checked whether any passage of the spec longer than about three sentences,
or any table, restates a mechanism, table or list that the plan explains. None does: the
Terms table holds only new terms, and facts taken from the plan are quoted as single
figures. Within the spec, the page uploading its parts again and submitting the plate
again is told four times (SPEC:249 to 252, SPEC:295, SPEC:337 to 338, SPEC:360), each in
one sentence, and "Security" restates the two-hour rule and the pairing code's limits as
a gist with a link; neither is long enough to report. The missing document map in the
plan is not reported, as in the second round.

## Top-to-bottom order

Checked: each table and summary against the position of the text that explains its rows,
and each term against its first explanation, other than the terms of the Terms table.

- SPEC:333 — "All of it, in one table" — SPEC:208 to 210 promises that the section "takes each kind of state in turn, and ends with a table of all of it", but six rows are explained only later: the cookie and its thirty days (SPEC:336, explained at SPEC:439), the paired-printer record and "until unpaired" (SPEC:341, explained at SPEC:505 to 526), delivery jobs (SPEC:342, explained nowhere), printer status (SPEC:343), offered pairing codes and "back within half a minute, as each daemon offers again" (SPEC:344, explained at SPEC:507 to 510), and the log lines with "the last minute before a crash" and "seven days" (SPEC:345, explained at SPEC:742 to 747) — move the table to the end of the design, after "Reading what happened", or move "Sign-in", "Printers" and "Reading what happened" before it.
- SPEC:366 — the table "The front server restarts" — its rows rest on mechanisms not yet explained: "the cookie's key" (SPEC:368, the cookie is explained at SPEC:439), "its token still verifies" (SPEC:370, explained at SPEC:519), and "when it next offers its code" (SPEC:372 and SPEC:373, offering is explained at SPEC:507 to 510) — move "Restarts and deploys" after "Printers", or move "Sign-in" and "Printers" before it.
- SPEC:75 — "What this changes in the plan" — the section is a summary placed before the design it summarises: "parts named by hash in the plate configuration" (SPEC:88), "typed into PenguinSlicer once and is then dead" (SPEC:93) and "This is what lets a container restart without a user losing work" (SPEC:86) can only be followed after "Parts", "Pairing" and "Restarts and deploys" — move the section to stand directly before "What changes in each component".
- SPEC:156 — the table of limits on one slice — the rows "6,000 MB, proposed" and "240 seconds, until measured on Railway" come before the paragraphs that explain them (SPEC:163 to 183) — move the table below those paragraphs.
- SPEC:452 — the table of calls to Onshape — the row "Reading a user's groups again | None until the app is public" comes before "Groups are read at sign-in" (SPEC:463 to 473), which explains it — move the table and the sentence at SPEC:460 below that paragraph and its two bullets.
- SPEC:596 — "A held wait | No wait | About 1 a minute for the wait ... | New code on both halves, described below" — the row precedes the paragraphs that explain the held wait and its cost (SPEC:602 to 622) — move the table of setting 1 below them.

## The body describes the design as it is to be

Checked: every sentence outside "What this changes in the plan", "What changes in each
component" and "How often a daemon talks to the relay" for a statement of how the code
works today, how something used to work, or an option that was rejected. Measurements of
Orca (SPEC:170 to 178) are facts behind a figure and are not reported.

- SPEC:674 — "(the relay's does; the slice service's must be added)" — a statement of the code as built, in "Progress streams"; SPEC:790 already carries the change (checked against the code: the relay sends a comment line every 15 s, `STREAM_HEARTBEAT_SECONDS`) — delete the parenthesis.
- SPEC:676 — "A stream that connects late already gets the latest progress report at once." — "already" describes the code as built — write "A stream that connects late gets the latest progress report at once."
- SPEC:134 — "R2 can issue a credential that only reads one bucket ... Railway's buckets promise none of the three." — a rejected option (Railway's buckets) argued in the body — keep the three things the design needs of its object store, and move the comparison with Railway's buckets to a bullet of "What this changes in the plan".
- SPEC:130 — "Railway bills by use, so two containers cost what one would." — together with SPEC:126 to 129 this argues against the rejected option of one container (the plan allows the components to "run inside one server", PLAN:127) — keep what the split gives; move the comparison with one container to "What this changes in the plan".
- SPEC:877 — "which both interfaces already answer" and SPEC:886 "Whether the daemon as built fetches a sliced file again ... was not read from its code" — statements about the code as built, in "To confirm before building on it", which is not one of the two allowed sections — either name "To confirm before building on it" as a third allowed section at SPEC:12 to 15, which fits what the section is for, or reword both.
