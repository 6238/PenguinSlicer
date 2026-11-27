# Review of the front server's guide

Reviewed Fri 2026-11-27, Pacific time: [front/README.md](../../../front/README.md), 1,112
lines, against [the writer's brief](brief-writer.md),
[the decisions of Fri 2026-11-27](decisions-2026-11-27.md),
[the plan](../../plans/penguin-slicer-plan.md), [the architecture](../../architecture.md),
[the contract between the wizard and the front server](../../../contracts/wizard-front-server.md),
[the configuration's contract](../../../contracts/configuration.md) and
[its details file](../../../front/README-details.md).

The guide is close to ready for the owner: it is prose a person can read from top to
bottom, it carries no code-level name, and almost every figure matches its source. It is
not ready yet, because three things an owner would decide on are missing: who can sign in
at all and what one such person can spend or exhaust, how many users the 100 threads
serve and what a user sees when they run out, and what a restart of the front server
does to a pairing code that is being typed. The single most important fix is the first:
say that anyone with an Onshape account can sign in, and bound the calls to Onshape that
one person can spend by signing in repeatedly.

Line numbers are those of the guide as read. "Add" names where the new text goes and its
source; where no source exists the finding says so, and the item belongs under "What is
undecided or unmeasured".

## 1. Can the reader decide from it?

| Question | Answer | What is missing |
|---|---|---|
| Does it do the right things for a user? | Yes, with gaps | Who may use it; signing in inside Onshape's panel when the browser withholds the cookie; what a Safari user sees |
| Is the division of work with the other components sound? | Yes | Nothing. The three "Apart from" paragraphs and the exchange table answer it |
| Are the approaches to the hard parts sound? | Mostly | Whether files pass through in pieces or whole in memory; how a repeated submission is made safe; what happens when threads run out |
| Are the limits and targets the right ones? | No | No figure for users at once, no time target of any kind, no ceiling on a sliced file, no limit on sign-ins |
| Is the security adequate? | Cannot be judged | Open sign-up, the allowance as a target, the permissions asked of Onshape, what Cloudflare may keep |
| Is behaviour on failure, cancel, restart and deploy acceptable? | Mostly | A pairing code across a restart; a deploy that is itself faulty; the slice service or the state bucket unreachable at the moment a slice ends or the front server starts |
| What is built and what is not? | Yes | Four pieces are in no phase's list |
| What remains undecided? | Mostly | The embedded cookie in Chrome is listed only under testing; the rate limits have a proposal in printer delivery's guide that is not given here |

### Findings, most serious first

- Lines 821-825 and 844-859 — "Anyone on the internet can send it a request ... Everyone
  else gets the sign-in or a refusal." — The guide never says that anyone can make a free
  Onshape account and so sign in, slice and store sliced files; the reader would assume
  from "group" and "Onshape company" that use is limited to known people. — Add to
  "Who can reach it": "Anyone with an Onshape account, which is free to make, can sign
  in and slice. There is no list of permitted users or groups." Then add, in "What is
  accepted as a risk", either that this is accepted, with what bounds a stranger (one
  unfinished slice job for each user, at most 25 parts in the part store for one user
  key, each slice bounded in memory and time: the architecture, Security, "Who may use
  it"), or list a permitted-groups setting under "What is undecided" with its cost. No
  source decides it.
- Lines 223-250 and 205-210 — "A sign-in to the hosted service | 2" and "The header has a
  'sign in again' action ... It costs two calls." — Nothing limits how often one person
  signs in, so one signed-in user pressing "sign in again", or clearing the cookie, 1,250
  times spends the whole 2,500 calls and after that nobody can sign in until the year
  turns. The guide calls the allowance the reason for half its design and does not
  defend it. — Add to "Onshape's yearly allowance of calls" a limit on sign-ins for each
  user and for the whole service in a day, with what a user sees at the limit, and add
  the row to "The limits that matter"; or list it under "What is undecided" with that
  consequence. No source has a figure.
- Lines 788-796 — "The figure of about fifty daemons assumes the other fifty threads are
  enough for the users." — The guide gives no figure for how many users or open pages the
  front server must serve at once, and does not say what happens when all 100 threads are
  held. From phase 5 a page following a print holds a thread for the whole print, hours
  long, so fifty open pages watching prints use every thread left. — Add after line 796:
  the number of pages following a slice or a print at once that the design is meant to
  serve; what a user sees when no thread is free (their request waits, and the page's
  retrying covers it, or it is refused); and whether the printer's status is followed on
  an open connection by every open page or only on the Send step. No source states these;
  if undecided, list under "About the design itself".
- Lines 604-647 — "the rule is that it interrupts no user and loses nothing a user did"
  and the table's last row. — The table omits the one thing a restart of the front server
  does cost a user: a pairing code typed in the half minute after a restart is answered
  as a wrong code and must be typed again, because the codes daemons are offering are in
  the relay's memory (the architecture, "What a restart does", last row of the second
  table, and "All the state", the row "Pairing codes that daemons are offering"). Line
  111 also says there are "two small exceptions" to nothing being lost; this is a third. —
  Add a row: "Typed a pairing code in the half minute after a restart (phase 5) | The
  relay's memory | Told that no daemon is showing that code; typing it again a moment
  later works". Change line 111 to "with three small exceptions" and add "and the pairing
  codes daemons are offering, which each daemon offers again within half a minute".
- Lines 933-937 and 211-214 — "that Chrome keeps the cookie for a page embedded in
  Onshape" — This is listed only as something the real thing must prove. If Chrome
  withholds the cookie from a page embedded in another site (a private window, a user's
  setting, a future default), a user in Onshape's panel can never sign in, and no
  fallback is designed. It is a feasibility risk of phase 4 and is absent from "What is
  undecided or unmeasured". — Add under "About the design itself": what is known
  (PenguinCAM's panel works this way in production today), what the user sees if the
  cookie is withheld (the sign-in repeats without end), and that no alternative is
  designed.
- Lines 837-842 — "call Onshape with the tokens of whichever users' requests pass through
  it" — The guide does not say what the Onshape app asks permission for, so the reader
  cannot tell what a stolen token, or a stolen cookie key, opens: a user's name and
  companies only, or every document they can read or write. — Add to "Onshape is the only
  sign-in" (after line 137) one sentence naming the permissions the app requests in
  phases 3 and 4, and repeat the consequence at line 840. No source states them; if
  undecided, list it under "About Onshape".
- Lines 757-784 — the table "The limits that matter". — No row is a target for time: how
  long the front server may take to answer, how long between a slice ending and the page
  being told it is finished, how long a preview's or a daemon's fetch of 14.1 MB may
  take. Line 1083 says only "the moment it takes". The brief asks for performance
  requirements. — Add the targets, or one sentence after line 762 saying that no time
  target is set for the front server and which measurement in phase 3 would set one.
- Lines 770-771 — "Any one request through Cloudflare | 100 MB | ... | Not needed: the
  largest thing sent is a sliced file" and "A sliced file | 8.8 to 14.1 MB" — The second
  row is a measurement on a few plates, not a limit, and nothing in the guide bounds a
  sliced file below Cloudflare's 100 MB; a full plate at a fine layer height is not among
  the plates measured. — Change the sliced file's "Limit" cell to say "no ceiling of its
  own" and add what happens to a sliced file over 100 MB (it cannot be fetched by a
  browser or a daemon), or add a ceiling the front server enforces when it collects the
  file, with what the user sees.
- Lines 326-345 and 392-411 — "The front server passes it to the slice service" and
  "fetches the sliced file ... stores both" — The guide does not say whether a part and a
  sliced file pass through the front server in pieces or are held whole in its memory.
  With several 14 MB fetches at once that decides its memory, which line 1017 says was
  never measured. — Add one sentence to "A part" and one to "The front server follows
  every slice job itself" stating the approach. No source states it; the builder's
  choice should at least be named as bounded.
- Lines 629-633 and 995-1002 — "When it is asked to stop ..." — The guide covers a deploy
  that works. It does not say what happens when the new front server fails to start or
  fails the check that runs after each deploy (line 937): who learns of it, whether the
  previous version comes back, and what users see meanwhile. Nor does it say how the
  owner learns that the service is down at any other time; the log is read on demand. —
  Add a paragraph to "Restarts and deploys", or an item under "About the host", saying
  what is designed (nothing, by the sources) and what a user sees: the page's retrying
  for 300 seconds and then the error.
- Lines 392-405 and 624-627 — "A fetch that fails partway leaves nothing half-written in
  the state bucket and is tried again." — Two failures are not followed to their end:
  the state bucket not answering for a long time when a slice ends (how long the slice
  container keeps the uncollected sliced file, and what the user sees meanwhile), and the
  slice service not answering when the front server starts and asks for its slice jobs. —
  Add to "The front server follows every slice job itself": the slice container keeps the
  file until told it is stored (the slice service's guide, line 722), the page goes on
  showing the slice as running, and the front server keeps trying; and to line 624 that
  the front server asks again until the slice service answers.
- Lines 635-639 — "a repeated submission must not leave the page following a slice that
  the repeat itself cancelled" — This states the requirement and not the approach, and it
  is the hard one of the three, since a submission cancels the user's earlier unfinished
  slice job. — Add how it is met (for example, the page marks each submission and a
  repeat with the same mark is answered with the first one's slice job), or list it
  under "About the design itself" as not designed. The contract marks the requirement
  proposed and gives no means.
- Lines 71-73 — "Cloudflare runs no logic of PenguinSlicer's." — The guide does not say
  whether Cloudflare's proxy may keep copies of what passes: a sliced file or a
  configuration answered to one user and kept by the proxy would be a leak. — Add: "The
  front server marks every answer except the wizard's own page files as not to be kept
  by any proxy or browser." No source states it; without one, list it as a requirement
  to confirm.
- Line 160 — "Safari is not supported, in Onshape's panel or outside it." — It does not
  say what a Safari user sees, or which browsers are supported. — Add one sentence: the
  supported browser (Chrome, by lines 935-936) and what the front server or the page
  shows in another.
- Lines 939-989 — the phase lists. — Four pieces described in the body are in no phase's
  list: the request that gives the page the user's name and groups (lines 178-180; the
  header needs it in phase 2); "sign in again" (phase 3 by the plan's list for the
  wizard); the limits on the rate of requests (line 802; line 1111 says "phase 2's and
  phase 5's designs"); and reading groups again once a day, with the token renewal it
  needs (lines 244-247, when the app is public). — Add each to its phase, and the last
  to the "In no phase" sentence at line 988 with "until the Onshape app is public".
- Lines 802-803 and 1111-1112 — "their figures are not settled" — Printer delivery's
  guide proposes the figures for phase 5 (120 status requests and 10 sends a minute for
  each user; 120 syncs and 60 other requests a minute for each daemon:
  [delivery/README.md](../../../delivery/README.md), "The rate limits of phase 5"). The
  reader is given a one-line open question where a proposal exists. — Replace line
  1111-1112 with the proposal and a link, and say that nothing is proposed for phase 2's
  requests (uploads and submissions for each user).
- Lines 698-755 — "The log". — Users' and parts' names are kept ninety days; the guide
  says so (line 724) but not whether a user's lines can be removed on request, nor that
  the configuration documents and paired-printer records in the state bucket have no
  second copy if the bucket is damaged or a hand-written document is overwritten. — Add
  one sentence each, under "What is accepted as a risk": that neither is designed.

### The extra question: is every part earning its place at 1,112 lines?

Most of the length is earned. The sections on signing in, the part and the slice, the
sliced file's life and the configuration are the body the owner asked for and should stay
as they are. About 150 lines can go without loss, from three causes.

**Sections that explain at length what the architecture owns.** The guide is read after
the plan only, so a gist and a link are right; these go beyond a gist.

- "Secrets", lines 668-696 (29 lines). The table and the two paragraphs after it restate
  the architecture's "Replacing a secret" almost sentence for sentence, including the
  relay's secret, which is printer delivery's, and the buckets' credential. Keep: the
  four secrets it holds, the cookie key's two-key replacement (the front server's own
  mechanism) and the Onshape secret's unconfirmed gap. Cut to about 12 lines with a link
  to [the architecture's Security](../../architecture.md#security).
- "The log", lines 698-755 (58 lines). "Where it goes" and "Who reads it" are the
  architecture's "Reading what happened" restated. Keep "What the front server writes"
  and the paragraph on gathering for the others (lines 738-746). Cut the rest to a
  three-sentence gist and a link: about 30 lines.
- "Old and new versions together", lines 649-666. The architecture owns it under the
  same heading. Keep the first rule, which is the front server's (the version on every
  answer); give the other two a sentence and the link.
- "What it costs to run", lines 805-817. The cost is of both containers and the buckets,
  not of the front server, and the plan (phase 3) and the architecture ("To confirm")
  both state it. Cut the section; keep the one sentence at lines 1021-1022 with the $7
  and a link.
- "Why it is the one thing the internet reaches", lines 57-84. The diagram is the
  architecture's "The shape" diagram less two nodes. Keep the three consequences; the
  diagram can stay only because this reader has not been sent to the architecture
  first, so this one is a judgment call and not a cut.

**Detail that belongs to another component's guide.**

- "Running the relay", lines 583-602: the 55 seconds, the sixty offers a minute and the
  noting of when a daemon went silent are the relay's mechanisms, in printer delivery's
  guide. Keep the first four bold paragraphs (who is asking, the place for records, the
  sliced file, the repeated send) and the thread cost in one sentence; move the rest to
  a link. The rows "An idle daemon's open request", "A pairing offer without a token"
  and "The page's patience" of the limits table (lines 768, 783, 784) likewise belong
  to the relay's and the wizard's guides.
- The limits table's rows "Any one request through Cloudflare" and "Log lines in
  Railway's view" protect "Nothing of ours" by their own words and need no check; fold
  them into the sentences that already state them (lines 371-373, 732).

**The same fact told several times.** This is the largest saving and the reader's main
cost: each of these is explained in full in more than one place.

| Fact | Lines where it is told |
|---|---|
| A removed user keeps access for thirty days | 205-207, 244-247, 846-847, 1079-1081 |
| A sliced file can rest at R2 about four days | 479-481, 779, 857-858 |
| Silent for 20 seconds, an error after 300 | 641-644, 784, 999-1000 |
| The cookie may not fit in 4 KB | 775, 1060-1067 |
| Two requests renewing the tokens at once | 216-221, 1069-1074 |
| No permissions inside a group | 165-166, 848-851, 988 |
| A repeated send answers with the first delivery job | 578-581, 638-639, 1087-1088 |
| Railway's behaviour at a deploy is unknown | 633, 959-960, 995-1002 |

Tell each once, in its own section, and let the limits table, "Security" and "What is
undecided" name it in a clause with a link to that section.

**Detail only a builder needs.** Little remains. Lines 97-99 (the four operations on a
bucket) and lines 729-730 ("one small structured record") could each lose a sentence;
neither is worth a round of edits by itself.

**Sections that are too thin.**

- "Security", "Who can reach it" (lines 821-825): see the first two findings above.
- "The limits that matter": no figure for users at once and no time target.
- Serving the wizard's pages: one bullet (line 947) and nothing else. What is served,
  whether a signed-out browser receives any of the wizard's code, and what a proxy may
  keep are not said.
- Signing in inside Onshape's panel: one sentence (line 135) and one accepted
  consequence (lines 211-214). What the user sees there the first time (Onshape's
  approval page inside the panel, or in a window of its own) is not said.
- Phase 4 (lines 973-979) is thin on purpose and says so; that is right.
- A deploy that goes wrong, and how the owner learns the service is down: absent.

## 2. Written for a person

No code-level name was found: no route path, verb, status code, setting name, error code,
file or test name. The one identifier is the public address (line 12), which a person
deals with. The findings are of reading.

- Lines 59-61 — "One address serves the wizard's pages, the address a daemon is given,
  and the address Onshape sends a user back to after signing in." — "One address serves
  ... the address" must be read twice. — "The wizard's pages, the address a daemon is
  given and the address Onshape sends a user back to after signing in are all at one
  address."
- Lines 467-470 — "Three, because the rule counts from storing and must not remove a
  file that a long print still gives a right to: it has to outlast the longest print and
  the two hours after it." — "still gives a right to" must be read twice. — "Three,
  because R2 counts from when the file was stored, and the file must still be there two
  hours after the longest print ends."
- Lines 451-452 — "a sliced file whose print is under way has not passed its limits,
  since that print has not ended. When it ends, the two hours start again." — "start
  again" suggests they had run once before. — "a sliced file whose print is under way is
  kept; its two hours are counted from the moment that print ends."
- Lines 75-84 — the diagram uses "state bucket" and "log bucket" before lines 94-96
  define them. — Move the diagram below "What it holds, and what it never holds", or add
  to line 71-73: "It keeps what must last in two stores, the state bucket and the log
  bucket, explained below."
- Lines 146-158 and throughout — "the page" is used from line 146 on and never defined;
  "the browser" (line 169), "the wizard" (line 328) and "the page" (line 348) each name
  the sender of a request. — Add at line 28-29: "A **page** is the wizard as loaded in
  one browser tab or in Onshape's panel" (the contract's definition), and use "the page"
  for whatever sends a request.
- Lines 117-123 — the exchange table names "plate configurations", "summary", "the
  relay's records" and "the number of its format" before the text that explains them
  (lines 348, 394, 566, 660). — Move the table to the end of "What it does for a part and
  for a slice", or keep it and cut each row to what the reader already knows at that
  point.
- Lines 764-784 — a table of nineteen rows and five columns, whose cells are whole
  clauses, stands where the brief asked for "a table with a sentence of explanation for
  each row". Six of its rows are other components' or "Nothing of ours" (see heading 1).
  — Cut those rows and drop the "How it is checked" column into the sentence at lines
  759-762 where the check is "a test with a moved clock", keeping the cell only where
  the check is something else.
- Lines 1076-1092 — "Things this design fixes that the approved design left open." — A
  list of seven where each needs its consequence to be judged; five have one and two do
  not (line 1084, "answered as unknown, not as forbidden": what the user sees is the
  same; line 1089-1090 gives a reason but no cost). — Give each the same two parts, what
  the user sees and what the other choice would cost, or drop the two that have no
  consequence for a user.
- Line 517 — "which names the H2S's profile" — H2S is the plan's term, but this is its
  only appearance in the guide. — "which names the profile of the Bambu Lab H2S, the
  Popcorn Penguins' printer".

## 3. True

Checked against the details file, the architecture, the two contracts, the decisions
file, and by search the frozen design and printer delivery's and the slice service's
guides. Figures checked and found to match: 7.5 MB, two hours (part, slice job, sliced
file), three days and about four, thirty days, 2 calls, 2,500 a year, about 80 calls,
fifteen minutes, five minutes, 125 seconds, fifteen seconds, 55 seconds, 100 threads,
about fifty daemons, sixty offers a minute, one week, seven days, ninety days, once a
minute, 20 and 300 seconds, 8.8 to 14.1 MB, 100 MB, $7, $10 and $40, one running and two
waiting, a day after a delivery job ends, ten seconds, two minutes.

- Lines 111-113 and 615-622 — "with two small exceptions" — Differs from the
  architecture, which lists a third thing the relay's memory loses at a restart, the
  pairing codes daemons are offering, with a consequence a user sees. — The fix is under
  heading 1, fourth finding.
- Lines 599-600 — "When a daemon goes silent the relay writes the time into the
  paired-printer record, once" — Omits which time, which decision 19 settles (proposed):
  "the time noted is that of the daemon's last sync". — "the relay writes the time of
  that daemon's last request into the paired-printer record, once".
- Lines 348-349 — "the layout, the settings and each part's fingerprint, with no files
  in it" — Decision 6: the plate configuration gains units for each part, and lines
  335-336 of the guide itself make the units part of what names a part. — "each part's
  fingerprint and units".
- Line 783 — "A pairing offer without a token | Sixty a minute for the whole relay | ...
  | Printer delivery, as built" — As built, the limit of 60 a minute is on the trade of
  a pairing code, counted with no user or daemon to count for; the offer by a daemon
  without a token, also counted for each address, is the design to be built in phase 5
  ([delivery/README.md](../../../delivery/README.md), "Limits on the rate of requests").
  — "Printer delivery's design; the figure is the one built today".
- Lines 359-363 — "in that case the front server answers that the service did not
  answer" — The contract puts the duty on the slice service ("a slice service that is
  stopping for a deploy must refuse a new slice job with an answer the page retries
  silently"). The guide makes it the front server's translation. Both can be true, but
  the guide states as settled which component does it. — "in that case the page must be
  answered that the service did not answer, which it retries silently; whether the slice
  service says so itself or the front server turns its refusal into that answer is
  settled with phase 2's design."
- Lines 153-154 — "It sets the cookie, reads the configuration of the user's groups" —
  True to the details file, but with lines 515-516 ("always for the current group") the
  reader cannot tell whether a sign-in reads every group's document or one. — "reads the
  configuration of each of the user's groups" if that is meant, with its cost for a user
  in many groups; otherwise "of the current group".
- Lines 807-811 — "About $40 a month is the figure for 5,000 slices and 1,000 daemons" —
  Copied exactly from the architecture, which also gives no period for the 5,000 slices.
  A figure without what it measures. — "5,000 slices a month", if that is what the
  frozen design's figure means; otherwise cut the sentence with the section (heading 1).
- Lines 819-862 — "Security" omits two statements of the architecture's Security that
  bear on the front server: that the slice container can call the front server over the
  private network, where it meets the same sign-in as anyone else; and that wrong
  pairing codes are limited for each signed-in user. — Add the first to "What it treats
  as hostile" and the second to "Who can reach it".
- Lines 1060-1067 — "nothing needs the tokens before phase 4, unless the app is public
  by then" presented as "One fact leaves room". — It is true, but the room it leaves is
  not stated: leaving the tokens out of the cookie until phase 4. — Say so: "so until
  then the cookie could be set without the tokens, which removes most of its size".

Omissions the reader needs, already listed under heading 1 and not repeated here: the 25
parts for each user key and one unfinished slice job as the bounds on a signed-in
stranger (the architecture, Security).

## 4. One name per thing, and the design as it is to be

- Lines 51, 113, 409 — "a computer beside the printer", "each printer's computer", "the
  printer's computer" — The plan's term is "the daemon's computer". — Use it at lines
  113 and 409, and define it at line 51: "a program on **the daemon's computer**, the
  computer beside the printer".
- Lines 599-602 — "goes silent", "has been silent", "shown as silent" — The architecture
  and the contract say a daemon "goes offline" and the printer-status icon shows
  "Offline" after 2 minutes without a request; "silent" is the wizard's sentence to the
  user. Two names for one state. — "When a daemon goes offline (no request from it for
  two minutes) ..."; keep "silent" only inside the quoted words the user sees.
- Lines 336, 349 — "fingerprint" — The plan, the architecture and the contracts say
  "hash". Line 336 defines fingerprint as a SHA-256 hash, so the reader is not lost, but
  the set has two names. — Use "hash", defined once at line 335-336 as "a hash of the
  file's bytes, a short value that changes if any byte does".
- Lines 15, 174, 277-279, 354-357 and others — "plates" and "a slice" for what the plan
  calls a plate configuration and a slice job ("takes the user's parts and plates to the
  slice service", "submitting a plate", "the later slice wins", "cancelling a slice"). In
  the plan a plate is the bed and what is on it. — Use "plate configuration" for what is
  sent and "slice job" for what is submitted, followed and cancelled; "the slice" may
  stay where it means the act of slicing ("when a slice ends").
- Lines 596, 683, 688 — "the relay's secret" — The architecture and the plan say "the
  relay's secret key". — Use that.
- Lines 1076-1092 — "Things this design fixes that the approved design left open", and
  line 1091-1092 "the approved design's 'about fifty daemons' did not count it" —
  History of how the design was reached, which the brief excludes from the body. The
  content is wanted, since each is a choice the owner has not seen. — Retitle "Choices
  the owner has not yet confirmed", drop "the approved design" from the lead sentence
  and from the last bullet ("Following slice jobs is counted among the 100 threads, so
  the room for daemons is about fifty less up to three").
- Lines 783 and 1087-1088 — "Printer delivery, as built" and "Printer delivery as built
  refuses it instead" — These state what exists today, which the brief allows when said
  in the sentence; the second is correct and useful. No change beyond the fix to line
  783 under heading 3.
- Lines 1099-1103 — "What the fixed set of configurations is." — Stated as open. Decision
  8 says only "there is a fixed set of configurations"; the plan and the configuration's
  contract say a group uses the built-in default or a document the owner places by hand.
  The living documents therefore settle it the way the guide assumes. — Either cut the
  item, or keep it and say that the plan and the contract already state the first
  reading, so that the owner is asked only to confirm it.
- Lines 1094-1097 — "The configuration's write, with nothing using it." — The plan's
  phase 2 list for the front server says "the configuration" and the details file places
  the conditional write in phase 2; the guide states it as the design at lines 546-547
  and as open here. — Keep one: state it at 546-547 with its reason and cut the item, or
  move the whole of it here.
- No finding: "the Onshape integration" is used and defined at lines 975-976 as decision
  21 requires; no sentence says "student", "mentor" or "team"; "administrator" is not
  needed and not used.
