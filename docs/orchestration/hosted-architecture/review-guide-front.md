# Review of the front server's guide

Reviewed: [front/README.md](../../../front/README.md) (199 lines) and
[front/README-details.md](../../../front/README-details.md) (764 lines), against
[the spec](../../specs/2026-11-25-hosted-architecture-design.md),
[the decision map](decision-map.md) and [the plan](../../plans/penguin-slicer-plan.md).
Nothing of the front server is built, so both files are design throughout.

README.md is close to ready for the owner: its length is right, it says plainly that nothing
is built, and no approved decision is missing from the two files. The single most important
thing to fix is the rule for the current group: the spec says it is sent with each request and
accepted only if the cookie lists it, the details file makes that check only on configuration
and phase 5 routes while still logging a group for every slice, and README.md's route table
asks for a current group on the one route that tells the wizard which groups exist. Beyond
that, one paragraph (the print, lines 120-127) and three unexplained remarks ("until phase 4",
"the development and hosted OAuth apps", "55 seconds") would stop this reader.

Findings: Check A 11, Check B 11, Check C 1 changed row and 33 inventions.

## Check A: README.md reads well for its human reader

Read alone, top to bottom, with only the plan as background.

- front/README.md:89 — "The user and their groups; read or write a group's configuration |
  The wizard | A signed-in user and a current group the cookie lists" — the wizard asks for
  the user's groups in order to offer a current group, so this route cannot need one; the
  reader stops to work out how the first request is ever accepted — split the row: "The
  user and their groups | The wizard | A signed-in user" and "Read or write a group's
  configuration | The wizard | A signed-in user and a current group the cookie lists".
- front/README.md:120-127 — "The **relay**, printer delivery's server half, runs inside the
  front server's process; each daemon calls it with a **sync** ... An idle daemon's sync is
  held open up to 55 seconds, one thread each" — one paragraph carries four terms, a
  five-line sentence with two nested parentheses, and a held sync whose purpose is never
  given ("sync" and the held wait are not in the plan's Terms table); it must be read twice
  — rewrite as three short paragraphs: (1) "The **relay**, printer delivery's server half,
  runs inside the front server's process. The front server does three things for it: it
  tells the relay who is asking (the user and the current group); it keeps the relay's
  records in the state bucket; and it gives the relay the sliced file, kept past its two
  hours while a delivery job needs it." (2) "The records are each group's paired-printer
  record, which names its daemon, and one record for each **delivery job**, one sliced
  file on its way to a printer." (3) "A daemon reports with a **sync**, a request carrying
  the printer's status. The relay holds back its answer to an idle daemon's sync for up to
  55 seconds, so that a send reaches the daemon at once. Each held sync takes one thread:
  with 100 threads the front server has room for about fifty idle daemons beside
  everything else."
- front/README.md:70-71 — "Until phase 4, twenty people using the hosted service for two
  months spend about 80 calls." — nothing in README.md says what changes in phase 4, so
  the limit of the claim is unexplained, and the phase table (line 179) says phase 4 adds
  "Nothing new" — add a table row after line 65, "Reading parts from Onshape, from phase 4
  | Several for each part; counted in phase 4's design", and begin the sentence "Until
  phase 4 adds that,".
- front/README.md:186-187 — "whether the development and hosted OAuth apps share it" —
  README.md has spoken of one app ("the Onshape OAuth app", line 58) and said work on one
  machine uses no Onshape at all (line 73); a second, "development" app appears here
  unexplained (the same words are at README-details.md:277 and in the spec at 986-988) —
  write "whether a second OAuth app of the same account, registered for development,
  would draw on the same allowance", or drop the clause if no such app is planned.
- front/README.md:14-19 — "It is a component of its own because it holds what the rest must
  not." — the next two sentences describe the slice service and the wizard, and what the
  front server holds arrives three sentences later, so the opening claim is read twice —
  move "The front server holds the sign-in secrets and the one credential that writes to
  the buckets." to directly after that first sentence, then the slice container, then the
  wizard.
- front/README.md:54-55 — "the previous key still reads for one week and each such cookie is
  rewritten with the new one" — "each such cookie" has no clear referent, and the
  consequence for a user is missing — "the front server still reads cookies made with the
  previous key for one week, rewriting each with the new key; a user away for that whole
  week signs in again."
- front/README.md:147-149 — "about once a minute writes all of them to the log bucket as a
  new file; Railway's log view keeps them seven days" — the reader has not been told the
  lines also go to Railway's log view, so the clause reads as a contradiction of the
  ninety days in the table at line 35 — "Every line also goes to Railway's log view, which
  keeps it seven days; the log bucket keeps it ninety."
- front/README.md:109 — "(8.8 to 14.1 MB on the plates measured)" — a figure with no
  statement of what it bounds or why it matters here — either "(8.8 to 14.1 MB on the
  plates measured, small against the 100 MB Cloudflare allows a request)" or cut it; it is
  in README-details.md:437-438.
- front/README.md:190-192 — "and two requests renewing the tokens at once must not leave a
  spent refresh token in it" — this is a requirement, not something unknown, and README.md
  never explains that tokens are renewed — cut the clause; README-details.md:180-181 and
  its test at 211-212 hold it.
- front/README.md:79-94 — section "Its interface" — the route table comes before the two
  sections that explain what its rows do (a slice, a print), and its phase 5 rows use
  "pair", "send", "unpair" and "the daemon's token" before the print section — move "Its
  interface" to after "What it does for a print, from phase 5". No other section needs
  moving; the length (199 lines) serves this reader.
- front/README.md:177 — "the two hours" — a label that means something only as the details
  file's heading — "refusing and deleting sliced files after two hours".

## Check B: README.md agrees with README-details.md

- front/README.md:106-107 — "sends a comment line at least every fifteen seconds so that
  neither Cloudflare (125 seconds without data) nor Railway (five minutes) closes it" —
  README-details.md:399-402 says Railway also closes any request after fifteen minutes, and
  the page reconnects; the comment line does not prevent that, so "neither closes it" is
  wrong for a long wait — "so that neither Cloudflare (125 seconds without data) nor
  Railway (five minutes without data) closes it early; Railway closes any request after
  fifteen minutes, and the page reconnects."
- front/README.md:89 — "The user and their groups" — no such route is in
  README-details.md, which has no route by which the wizard learns the user's name and
  groups (the cookie is encrypted, so the page cannot read them from it) — add the route
  to README-details.md under "Groups and the current group", marked as a proposal, with
  what it needs (a signed-in user, no current group).
- front/README.md:91 — "From phase 5: pair, send, follow, cancel, unpair | ... | A signed-in
  user and a current group the cookie lists" — README-details.md:227-228 makes the group
  check on "pairing, sending and unpairing" only, and README-details.md:297-298 names a
  fifth action, "stopping following", that README.md leaves out — make the two lists the
  same in both files: "pair, send, follow, stop following, cancel, unpair", and say in
  README-details.md:227-228 which of them make the check.
- front/README.md:125-126 — "held open up to 55 seconds" — the figure 55 is nowhere in
  README-details.md, which says only "the held wait of its sync" (line 636) — add to
  README-details.md "Threads": "the held wait, up to 55 seconds
  ([printer delivery](../delivery/README.md))".
- front/README.md:62-66 and 179 — the table of calls, and "4, inside Onshape | Nothing new"
  — README-details.md:266 has a fifth row, "Reading parts from Onshape, in phase 4 |
  Several for each part", and README-details.md:756-757 says reading parts and its cost in
  calls is designed in phase 4; README.md has lost both, which changes the meaning of
  "Calls to Onshape are scarce" — add the row (see Check A) and write line 179 as "Nothing
  new for sign-in or routes; reading parts from Onshape is designed in that phase".
- front/README.md:55-56 — "Every route that changes something also requires a header" —
  README-details.md:293 says "Every route that changes something on the strength of the
  cookie"; without the qualifier the rule covers the daemon's routes, which carry a token
  and no such header — restore "on the strength of the cookie".
- front/README.md:166 — "It will be its own `uv` project, run with `make -C front ...`" —
  not in README-details.md — add one sentence to README-details.md "Tests".
- front/README.md:104 — "A user has one unfinished slice job at a time." —
  README-details.md:378-380 adds "submitting a plate cancels the user's earlier unfinished
  slice job"; without it the reader takes a second submission to be refused — add ":
  submitting a plate cancels the user's earlier one".
- front/README.md:34 — "A sliced file, two hours after its slice ended; a configuration,
  until edited" — README-details.md:474-475 keeps a sliced file longer while a delivery job
  needs it, and "until edited" is not in README-details.md at all — "two hours after its
  slice ended (longer while a delivery job needs it, from phase 5)"; add the
  configuration's lifetime to README-details.md "The configuration".
- front/README.md:35 — "Log lines of the front server, the slice service and, from phase 5,
  the relay" — README-details.md:60 says the log bucket holds "log lines and daemon
  telemetry" — add "and daemon telemetry".
- front/README.md:37-38 — "parts live in the browser's storage and, as a cache, in the slice
  service" — README-details.md says the front server keeps no copy (line 371) and names
  the part store (368-370) but never says the browser's storage holds the parts — add to
  README-details.md:371 "the browser's storage is the record of a user's parts
  ([the wizard](../wizard/README.md))".

Checked and found in agreement: 2,500 calls; 2 calls a sign-in; thirty days from sign-in;
one week for the previous cookie key; about 80 calls; 7.5 MB; fifteen seconds; 125 seconds;
two hours; one-day deletion rule and about two days; 100 threads and about fifty daemons;
ninety days and seven days; once a minute; the development identity's refusal to start; the
three exceptions to sign-in; every item of "What is not known"; the phase 2, 3 and 5 rows.

## Check C: nothing of the approved design was lost or changed

Rows whose Home is `front/README.md`: D58, D62, D71, D84, D85, D87, D88, D91, D92, D93,
D113, D114, D115, D116, D119 to D123, D125 to D128, D130 to D133, D135, D136, D138 to D145,
D179, D192, D196, D199, D231, D236, D249, D268, D327 to D335 (50 rows). Each was looked for
through the whole of README-details.md.

**Missing:** none.

**Changed in meaning:**

- D119 — spec 341-343: "The choice is kept in the browser and sent with each request; the
  front server accepts it only if the user's sign-in cookie ... lists that group among the
  user's." — README-details.md:227-228: "Every route that reads or writes a configuration,
  and from phase 5 every route of pairing, sending and unpairing, makes this check." — the
  check is narrowed to some routes, and README.md:90 accordingly asks only "A signed-in
  user" for parts and slice jobs. Yet README-details.md:571 says "Every line about a slice
  or a send carries the user key and the current group" and 576-577 says the front server
  "knows each slice job's group from the request that submitted it". So a slice's group
  comes from the browser unchecked and goes into the log, where "slices and prints for
  each group" are counted — fix: either check the current group on every request that
  carries one, the slice routes included (the spec's words), and change README.md:90 to
  match; or keep the narrowing and mark it in README-details.md:227 as a proposal that
  changes D119.

**Weakened:** none. The other 49 rows are stated in the spec's words or closer.

**The writer's inventions** (stated as decided, not decided by the spec; all in
README-details.md; mark each as a proposal):

- 95-97 — the sign-in's value is OAuth's `state`, and is remembered "in the browser".
- 143-144 — a callback with a wrong `state` "is logged as a failed sign-in".
- 162-163, 192 — the thirty days "count from the sign-in"; a rewrite "keeps its end".
- 173 — the cookie is marked `SameSite=None` and `Secure`.
- 205-206, 209 — an unreadable or expired cookie "is treated as no cookie".
- 225-227 — a request naming no group, or an unlisted one, is "logged as a refusal" (not
  in the spec's list of refusals at 555-556).
- 227-228 — which routes make the group check (see D119 above).
- 284 — "a test fails if any other client is built during the suite".
- 294-295 — "the `Origin` header must be the front server's own address".
- 295-298 — the list of changing routes, "stopping following" included.
- 299-300, 310 — "sends no header that would let another site's page read its answers";
  no `Access-Control-Allow-Origin`, preflight included.
- 303-304 — a `Content-Security-Policy` whose `frame-ancestors` names Onshape's address.
- 325 — Railway is recognised "by the environment variables Railway sets".
- 326-327 — a refusal to start "writes one log line saying why and ends the process with a
  failure status".
- 347-350 — another user's slice job or sliced file "is answered as for one that does not
  exist", and logged as a refusal.
- 362-363 — the slice service's answers are passed back "unchanged".
- 403-405 — a slice job is reported finished on the stream "only once the sliced file is
  in the state bucket".
- 410-411 — "the front server's route for asking about a slice job is that route" (the
  fallback when server-sent events are held).
- 431-432 — "the pages' progress streams are served from what it follows".
- 435-436 — the sliced file is stored "with the time the slice ended".
- 436-437 — the front server "tells the slice service it has stored the file".
- 443 — "the front server has no route that takes a sliced file from a browser".
- 461-462 — a failed fetch "leaves nothing half-written ... and the fetch is tried again".
- 470-475 — the refusal is an error report "saying it has expired"; "a regular sweep"; a
  kept file is "deleted then if it is older than two hours".
- 504-506 — the "version marker" read with the document.
- 508-510 — an unreadable document gets an error report and "its contents are never
  written over by the default"; "format number" as the test of readability.
- 528-536 — the bucket interface's "four things"; the R2 implementation tested "in a suite
  of its own, outside the fast suite".
- 557, 562-565 — log lines for a refused current group, a request without the wizard's
  header or from another origin, and the transitions "stored, served, expired, deleted".
- 598-599 — the version is carried "in a header, errors and progress streams included".
- 614-617 — stopping also "stops accepting new requests" and "writes the log lines it has
  gathered to the log bucket".
- 637-638 — the fifty daemons are beside "the progress streams it holds itself to follow
  slice jobs" (the spec, 535-537, does not count those).
- 689-704 — the code form `front.<what>`, the ten failures of the table and each one's
  "Retryable"; line 702 gives "Sliced file expired" for a file "unknown under the user's
  key", which makes one report of two different failures.
- 728-754 — the split of the front server's work between phases 2 and 3 where the spec
  (949-961) does not assign it: "one cookie key" and the log lines in phase 2; the checks
  on requests from other sites, finishing work when asked to stop, and the refusal to
  start with the development identity on Railway in phase 3.
