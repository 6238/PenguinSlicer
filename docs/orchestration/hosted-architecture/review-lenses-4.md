# Review by the four lenses, fourth and last round: the hosted architecture design spec

Reviewed Fri 2026-11-27, Pacific time. The document under review is
[the hosted architecture design spec](../../specs/2026-11-25-hosted-architecture-design.md),
called "the spec" below. Its declared prerequisite,
[the plan](../../plans/penguin-slicer-plan.md), was not reviewed. The previous round is
[the third round's review](review-lenses-3.md). The reader is the project's owner, who
knows the plan, reads the spec from top to bottom, was not present when it was written,
and decides from it.

`SPEC` stands for
`/repos/popcornpenguins/penguin-slicer/docs/specs/2026-11-25-hosted-architecture-design.md`.
Line numbers are those of the spec as it stands in this round.

## Status of the third round's findings

Each finding is named by the line it had in the third round and its quoted words.

### Lens 1

- SPEC:372, "the daemon gets its token when it next offers its code": fixed. The paired-printer record holds a hash of the code until the token is issued (SPEC:404 to 410, SPEC:652).
- SPEC:324, "writes into the state bucket by hand": fixed. The owner writes through Cloudflare's console, and that sign-in is the sixth secret (SPEC:306, SPEC:765).
- SPEC:683, "Every limit on the rate of requests": fixed. The pairing offer is named as the exception and counted for each address (SPEC:713 to 716, SPEC:855).
- SPEC:352, "Nothing a user did has to be done again": fixed. The two exceptions are in the rule (SPEC:630 to 632).
- SPEC:351, "a pause of a few seconds": fixed. No figure is given (SPEC:39, SPEC:628).
- SPEC:381, "if both containers restart": fixed (SPEC:662).
- SPEC:395, "closes its progress streams and held waits": fixed in all three places (SPEC:676, SPEC:857, SPEC:934).
- SPEC:335, "Until the plate is sent or its sliced file expires": fixed (SPEC:612).
- SPEC:682, "at most 25 parts for one user key": fixed. The least recently used part is removed (SPEC:228 to 230).
- SPEC:687, the slice container's own copy of a sliced file: fixed in the text and in the slice service's list (SPEC:246, SPEC:831). The row asked for in the table of all the state was not added; see the new finding at SPEC:607.
- SPEC:344, "While the daemon keeps offering": fixed (SPEC:621).
- SPEC:339, "Two hours after the slice ended": fixed in the row and in the Short answer (SPEC:616, SPEC:32 to 34).
- SPEC:45, "no others until the app is public": fixed (SPEC:46).
- SPEC:783, the Cleanup standing requirement: fixed (SPEC:783 to 785).
- SPEC:18, what the daemon keeps on its computer: fixed (SPEC:20).
- SPEC:176, "3 to 11 seconds": fixed. The figure is now the slowest plate, 22 seconds (SPEC:144).
- SPEC:4, the revision date: fixed (SPEC:4).
- SPEC:404, "the server": not fixed in three places. SPEC:48 "the server holds a record linking a group to its daemon" (the record is in the state bucket, which the same sentence then says can start no print); SPEC:718 "A part exists on the server only in the slice container"; SPEC:872 "the server's version" where SPEC:691 says "the front server's version". The fix is to write "the state bucket holds" at SPEC:48, "Of the hosted service, only the slice container holds a part" at SPEC:718, and "the front server's version" at SPEC:872.
- SPEC:140, "Railway's Hobby plan": fixed (SPEC:916).
- SPEC:524, "A send is allowed when": fixed. A send is defined at SPEC:419.
- SPEC:296, "the earlier plate's slice has expired": fixed (SPEC:278).

### Lens 2

- SPEC:377, the daemon asking the relay before it starts a print: fixed (SPEC:656 to 659).
- SPEC:870, "and x86_64 machines": fixed (SPEC:115, SPEC:146).
- SPEC:300, rows for a slice job that ended in an error or was cancelled: fixed (SPEC:276 to 277).

### Lens 3

- SPEC:524, the current group checked against the cookie: fixed (SPEC:311 to 312, SPEC:744 to 745).
- SPEC:460, "about 80 calls" and the renewal of tokens: fixed (SPEC:331 to 333).
- SPEC:342, "Until a day after the delivery job ends": fixed (SPEC:421 to 423).
- SPEC:267, "8.8 to 14.1 MB": fixed (SPEC:245 to 246).
- SPEC:336 and SPEC:345, "Thirty days" and "Ninety days": fixed (SPEC:329, SPEC:583).
- SPEC:585, "a few times the interval it watches": fixed (SPEC:483).

### Top-to-bottom order

- SPEC:333, "All of it, in one table": fixed. The table follows "Reading what happened" (SPEC:605).
- SPEC:366, the table "The front server restarts": fixed. "Restarts and deploys" follows "Sign-in" and "Printers".
- SPEC:75, "What this changes in the plan": fixed. It stands directly before "What changes in each component".
- SPEC:156, the table of limits on one slice: fixed. It follows its explanation (SPEC:153).
- SPEC:452, the table of calls to Onshape: fixed (SPEC:357).
- SPEC:596, the table of Setting 1 above the explanation of the held wait: deliberately left.

### The body describes the design as it is to be

- SPEC:674, "(the relay's does; the slice service's must be added)": fixed.
- SPEC:676, "already gets the latest progress report": fixed (SPEC:573).
- SPEC:134, the comparison with Railway's buckets: fixed. It moved to "What this changes in the plan" (SPEC:779).
- SPEC:130, "Railway bills by use, so two containers cost what one would.": not fixed (SPEC:103). It is one sentence of reasons for the split and states nothing about the code; it can stand if the owner accepts it.
- SPEC:877 and SPEC:886, statements about the code in "To confirm before building on it": not fixed. SPEC:923 still says "by a route both interfaces have" and SPEC:932 "was not read from its code", and SPEC:12 to 15 still does not name that section as a place for such statements; see the new finding at SPEC:14.

Not fixed: three (the remaining uses of "the server", the sentence at SPEC:103, and the
statements about the code in "To confirm before building on it"). Deliberately left: one.
All others are fixed.

## New findings

Found in one reading from top to bottom after the changes and the reordering. All
cross-reference links were checked: every anchor in the spec names a heading that exists,
and the linked file of the mockup's decisions exists.

- SPEC:4 — "revised Thu 2026-11-26 after the owner's review of the sections up to and including "Sign-in". The owner has not yet reviewed "Printers" or "Reading what happened"" — the sections were reordered after that review, so "up to and including Sign-in" now leaves out "Restarts and deploys" and "What this changes in the plan", which stood before "Sign-in" when the owner reviewed them, and the list of two unreviewed sections leaves "Security", "All the state, in one table" and everything after it unaccounted for — name the reviewed sections and the unreviewed sections one by one.
- SPEC:14 — "or [What changes in each component](#what-changes-in-each-component), and nowhere else; every other section describes the design as it is to be" — the spec itself contradicts this: "How often a daemon talks to the relay" has "What the daemon does today" and "What the relay concludes from silence today" (SPEC:462, SPEC:476) and decides nothing, and "To confirm before building on it" speaks of the code (SPEC:923, SPEC:932) — name both sections here as the two further exceptions and say why (one sets out a choice against what exists, the other lists what was not checked).
- SPEC:312 — "only if the cookie lists that group among the user's" — "the cookie" is used here for the first time and is not in the Terms table; what it is and what it holds is explained only at SPEC:328 under "Sign-in" — write "only if the user's sign-in cookie (see [Sign-in](#sign-in)) lists that group", or add "cookie" to the Terms table.
- SPEC:423 — "Unpairing removes the record; the daemon's next request is refused" — the sentence added before it is about "A delivery job's record", so "the record" now reads as the delivery job's record, when the paired-printer record is meant — write "Unpairing removes the paired-printer record".
- SPEC:278 — "Its sliced file has expired" (and SPEC:276 "Ended in an error", SPEC:277 "Cancelled by a later slice of the same user") — these three answers need the hosted service to remember a slice job after it has ended, yet the table of all the state keeps slice jobs only "Until the slice ends" (SPEC:615) and the front server deletes an expired sliced file (SPEC:250), so nothing says how the front server tells "expired" from "Unknown, because the slice container restarted" (SPEC:275), for which the page does the opposite thing and submits the plate again — say what records an ended slice job, where and for how long (for example the slice service's memory for two hours, or the time the slice ended kept in the browser's storage beside the slice job's id), and add the row to the table at SPEC:615.
- SPEC:607 — "Every kind of state the design keeps" — the table omits four kinds the text describes: the slice container's copy of a sliced file until the front server has fetched it (SPEC:246), the daemon's settings file and its note of the print it started (SPEC:431 to 440), the user's choice of current group kept in the browser (SPEC:311), and the record of an ended slice job (the finding above) — add the rows, or write "Every kind of state the hosted service and the browser keep" and add only those that then belong.
- SPEC:834 — "A route gives the front server its log lines, which gain the time, the user key and the group." — the slice service is never given the group: the front server passes it only the user key, which it "never interprets" (SPEC:71, SPEC:209), so it cannot write the group on its log lines — either say that each request to the slice service carries the group as well, in "Parts" and in the Terms table, or drop "and the group" here and say in "Reading what happened" that the front server adds the group to the slice service's lines when it gathers them.
- SPEC:649 — "the front server stores the sliced file when the slice ends" — how a restarted front server learns which slices it must still collect is told only in the list of changes (SPEC:817, "A route lists its slice jobs, by which a restarted front server finds the slices it must still collect"), so the row, and "It does this whether or not a page is open" at SPEC:239, rest on a mechanism the design never explains — add one sentence to "The sliced file": at start the front server asks the slice service for its slice jobs and collects each finished one.
- SPEC:145 — "and 240 seconds is twenty times what a plate of 150 small spacers took" — since the table of limits moved below this paragraph, nothing before this point says what 240 seconds is — write "and the starting time limit, 240 seconds, is twenty times what a plate of 150 small spacers took".
- SPEC:939 — "About $40 a month is the figure for 5,000 slices and 1,000 daemons, which also needs the asynchronous server mentioned under" — the asynchronous server is needed only if the held wait is chosen, which the spec says is undecided, and every other mention of the held wait outside its section now carries "if that choice is made" — write "which, if the held wait is chosen, also needs the asynchronous server".
- SPEC:325 — "which is limited to sixty a minute for the whole relay" — SPEC:713 to 716 and SPEC:855 to 856 now say the offer is also counted for each address, and this sentence gives only half the limit — add "and also counted for each address (see [Security](#security))".
