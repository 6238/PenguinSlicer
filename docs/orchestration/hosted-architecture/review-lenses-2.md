# Review by the four lenses: the hosted architecture design spec

Reviewed Wed 2026-11-25, Pacific time. The main document under review is
[the hosted architecture design spec](../../specs/2026-11-25-hosted-architecture-design.md),
called "the spec" below. Its declared prerequisite is
[the plan](../../plans/penguin-slicer-plan.md), which was read as the front door and not
reviewed. A change the spec declares under "What this changes in the plan" is not reported
as a disagreement. The reader is the project's owner, who knows the plan and was not
present when the design was worked out.

In each finding, `SPEC` stands for
`/repos/popcornpenguins/penguin-slicer/docs/specs/2026-11-25-hosted-architecture-design.md`
and `PLAN` for `/repos/popcornpenguins/penguin-slicer/docs/plans/penguin-slicer-plan.md`.

## Lens 1: the set agrees with itself

Checked: every term in the spec's Terms table against the plan's Terms table and against
each use in the spec, every figure that appears twice (retention times, sizes, costs,
request counts, time limits, thread and daemon counts), the scope the opening states
against what the body decides, the list under "What this changes in the plan" against
the plan, and the "By phase" list against the sections it names.

- SPEC:268 — "The hosted start command never sets that setting" — "start command" is a plan term for the message the daemon sends the printer to begin printing (PLAN:60), and here it names the command that starts the front server on Railway, so one name means two things — call it "the front server's launch command on Railway" or similar, and keep "start command" for the plan's meaning.
- SPEC:106 — "a redeploy of the slicer" — "the slicer" appears only here and could be Orca, the slice service or the slice container — write "a redeploy of the slice container".
- SPEC:123 — "one EC2 instance running both containers" — "instance" is the plan's term for one placement of a part (PLAN:41), and line 65 already says "a machine" for the same thing — write "one EC2 machine".
- SPEC:215 — "a finished slice that was not sent is gone" — "slice" as a noun means the sliced file here and at line 147 ("its slice expires") but the slice job at lines 118 and 200 ("a slice never waits", "finds a finished slice") — use "sliced file" where the file is meant and "slice job" where the work is meant.
- SPEC:222 — "the units of uploaded files and the printer's display name" — the printer's display name is also a field of the paired-printer record (line 57), so the reader cannot tell which document holds it or which wins when they differ — name one home and remove it from the other.
- SPEC:248 — "except the sign-in routes themselves and the daemon's routes, which carry the daemon's token" — pairing step 1 (lines 287 to 288) has the daemon ask the relay for a pairing code before it has any token, so one daemon route is reachable with neither a signed-in user nor a token — add the pairing-code request as a third exception and say what limits it.
- SPEC:38 — "no stored value can start a print" — the Secrets list (lines 371 to 372) holds the cookie's encryption key and the relay's secret key, stored values with which a sign-in or a daemon's token can be forged; line 295 makes the narrower, true claim about the state bucket — narrow lines 38 and 365 to "nothing in the state bucket or the configuration can start a print".
- SPEC:18 — "all of daemon telemetry (what proves a message's origin, what it may hold, its limits)" — the spec does decide part of daemon telemetry: where it is kept (line 56), for how long (line 156, ninety days), how it arrives (lines 390 to 391) and who reads it (line 400) — say that this spec fixes where daemon telemetry is kept, for how long and who reads it, and leaves the rest to phase 5.
- SPEC:15 — "of the security questions under phase 5 those about who may send to a printer, the pairing code and the relay's secret key" — the plan's sixth phase 5 question, showing who sent a print to everyone who uses the same printer (PLAN:414), is answered at lines 352 to 353 but is in neither the "answers" list nor the "leaves" list — add it to the "answers" list.
- SPEC:14 — "It answers the questions the plan lists under phase 3" — the spec also settles phase 2 matters the plan leaves to phase 2's design spec ("Coming back" and "The browser", PLAN:270 to 275) and adds phase 2 work (the part store, parts named by hash, the front server, the development identity; lines 434 to 437), and neither the opening nor "What this changes in the plan" says so — state in the opening that it decides these for phase 2, and add a bullet to "What this changes in the plan".
- SPEC:436 — "Everything in \"Parts\", \"The sliced file\" and \"Coming back\" is built here." — "The sliced file" describes Send, the relay's copy and the two-hour send limit (lines 187 to 194), and "Coming back" describes finding a delivery job (lines 201 to 202), all of which need printer delivery, which the plan and line 441 place in phase 5; the term "front server" (line 53) also puts the relay in the phase 2 process — say which parts of those sections wait for phase 5, and whether the relay runs inside the front server before phase 5.
- SPEC:186 — "The browser fetches it once, through the front server" — "Coming back" (lines 198 to 201) has a refreshed page open on the Preview step, which needs the sliced file again, and the browser's storage row (line 147) does not list the sliced file — say either that the browser stores the sliced file or that a page that has lost its state fetches it again.
- SPEC:471 — "about $40 with 5,000 slices and 1,000 daemons a month" — lines 322 to 326 give the front server room for about fifty idle daemons and defer the asynchronous server that would hold more, so the $40 case is outside what this design can serve — give the cost at about fifty daemons, or say the 1,000-daemon figure assumes the later asynchronous server.

## Lens 2: nothing is assumed beyond the declared prerequisites

Checked: every abbreviation, term and label in the spec against the spec's own Terms
table, its text up to the point of use, and the plan's Terms table. The plan's terms
(relay, daemon, caller, delivery job, slice job, plate configuration, error report,
progress report, upstream check, memory ceiling, standing requirements) pass. Railway,
Cloudflare, R2 and server-sent events are explained at first use or are common knowledge
for this reader.

- SPEC:39 — "An idle daemon waits on a held sync" — "sync" is never defined in the spec or the plan, and the Terms row for "held sync" (line 61) defines it by "sync request", so the reader has to infer it from line 308 — add a Terms row: a sync is the daemon's request to the relay that reports the printer's status and asks for work.
- SPEC:32 — "one paired-printer record in the state bucket; log lines are kept in the log bucket" — "paired-printer record", "state bucket" and "log bucket" are used in the Short answer without a gloss and defined only afterwards, in the Terms table (lines 55 to 57); the other new terms in the Short answer are glossed where they appear — add a few words at first use ("the state bucket, an object store for what must last").
- SPEC:136 — "Every held sync, every progress stream and every delivery job" — "progress stream" is used here and explained only at lines 331 to 332 — add a Terms row: a progress stream is the server-sent events connection on which a page follows a slice job or a delivery job.
- SPEC:80 — "the mockup's decision 46" — decisions 46 and 48 (lines 80, 207 and 216) are numbers from the mockup's DECISIONS.md, which the spec neither links nor lists as a prerequisite; decision 46 is paraphrased but decision 48 is cited as the authority for what the browser drops — link each number to [DECISIONS.md](../../mockups/print-wizard/DECISIONS.md) and state decision 48's content in the sentence.

## Lens 3: the facts that matter, in prose

Checked: each conclusion for the fact behind it, each figure for a statement of what it
measures, and each passage of figures or names for a sentence saying what they show. The
spec has no details file and no passage that needs moving to one.

- SPEC:463 — "its calls count against its owner's limit, 2,500 a year on a free or education account" — the facts are given without the conclusion they force: at a call or two for each sign-in and each daily reading of groups (line 465), 2,500 a year is about seven calls a day, which a handful of daily users exhausts, and that would overturn the daily reading in "Leaving a group" (lines 255 to 258) — state how many users the limit supports, what happens when it is reached, and move it out of "believed and not yet checked", since it is a known constraint and not a belief.
- SPEC:66 — "the same load costs about $7 a month while few people slice" — the choice of Railway over AWS rests on this figure, and neither here nor at lines 470 to 471 is the fact behind it given: both containers stay running (line 118), so the cost is set by the memory they hold while idle — add the idle memory assumed for each container and Railway's rate for memory.
- SPEC:116 — "The slice container is allowed 8 GB, against the 3.5 GB the slice service's guide sizes for one slice job" — no reason is given for 8 GB when 3.5 GB is the measured need, and the EC2 comparison at line 65 uses the same unexplained 8 GB; line 449 then calls it "Railway's 8 GB ... on its cheaper plan" without naming the plan — add the one fact that sets 8 GB (the plan's cap, or headroom for the part store and queued slice jobs) and name the Railway plan.
- SPEC:187 — "It is 8.8 to 14.1 MB on the plates measured so far." — the figure supports no stated conclusion — say what it shows (for example that one fetch by the browser and one copy in the relay's memory are affordable, and that it is far below Cloudflare's 100 MB request limit), or remove it.

## Lens 4: each thing explained once

Lens 4: pass. Checked whether any passage of the spec longer than about three sentences,
or any table, restates a mechanism, table or list that the plan explains. None does: the
spec's Terms table holds only new terms, facts taken from the plan (the 3.5 GB sizing,
the queue of two, the 188.5 MB request) are quoted as single figures, and the spec's list
of things to confirm is its own and not a restatement of the plan's open questions. The
missing document map in the plan is not reported, as instructed.
