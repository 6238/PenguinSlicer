# Review of the printer delivery guide

[README.md](../../../delivery/README.md) is close to ready for the owner: it is short, almost
every figure in it agrees with [README-details.md](../../../delivery/README-details.md), and
every decision of the spec whose Home is this guide is present in the details file's section
"To be built", none changed in meaning. It is not ready as it stands, because a reader who
knows only the plan meets several terms used without a definition (the job slot, the last
result, the token, the user key, "holds the printer", the stand-in printer) and one thing under
two names (three "parts" at line 10, then "halves" from line 32 on). The single most important
thing to fix is the section "To be built" of README-details.md, which states about twenty
specifics the spec does not decide (error codes and their new meanings, the new shape of
`identify`, the unpaired daemon's answer, a write-before-answer rule) as if they were decided;
each needs marking as a proposal.

Abbreviations in the bullets: **R** is `delivery/README.md`, **D** is
`delivery/README-details.md`, **spec** is
[the hosted architecture design](../../specs/2026-11-25-hosted-architecture-design.md), **map**
is [the decision map](decision-map.md).

## Check A: README.md reads well for its human reader

Read alone, first line to last, with only the plan's Terms table known.

- R:10 — "Printer delivery has three parts" — the plan's Terms table says "It has two halves,
  the relay and the daemon", and R itself then says "either half" (line 32) and "both halves"
  (lines 43, 49, 139) without having introduced "half"; one thing has two names and the count
  differs — replace with "Printer delivery has two halves, and a simulated printer for
  testing them:" and keep the three bullets.
- R:72 — "the job slot, the last result" — neither term is in the plan nor defined anywhere in
  R; "last result" returns at R:114 — replace the cell with "Paired or not, online or not,
  the printer's status, whether a delivery job is waiting to start, how the last delivery job
  ended (kept 10 minutes), and the latest delivery job's progress report", and at R:114 write
  "how the last delivery job ended, as the status route gives it, 10 min".
- R:30-31 — "the daemon holds the printer until the printer's own reports show what became of
  it" — "holds the printer" is not defined and reads as a physical lock; "the hold" returns at
  R:127 — replace with "the daemon sends that printer no other start command until the
  printer's own reports show what became of the first (the **hold**)".
- R:94-99 — "Only evidence ends a delivery job: … or a start gate never passed" followed by
  "the relay does so by itself after 24 hours" — the reader sees a rule and then time ending a
  job, with nothing saying it is the exception; and "a start gate never passed" does not read
  as evidence without the deadline behind it — replace the first with "…or the 15-minute
  deadline passing with the start gate never asked, after which the gate stays shut", and add
  after the 24-hour clause "This is the one place where time alone ends a delivery job."
- R:111 — "Collection deadline | 3 min to be collected, 15 min to reach the start gate | A job
  the daemon never takes up" — one row holds two figures and its "what it bounds" fits only
  the first — split into "Collection deadline | 3 min | A delivery job no daemon collects" and
  "Start-gate deadline | 15 min after collection | A collected delivery job whose daemon never
  asks the start gate; past the gate it no longer applies".
- R:116 — the rate limits row, six figures with three different keys in one cell — a pile of
  figures a person does not need, and it is the hardest sentence in the file — replace the
  value with "Per pairing code on the caller's and the daemon's routes, per address on the
  download, 60 pairing exchanges a minute for the whole relay" and leave the six figures to
  [The settings](../../../delivery/README-details.md#the-settings), which already holds them.
- R:119 — "Every time limit on the printer's side is a guess until the real H2S is timed" —
  the table does not say which rows are "on the printer's side" — replace with "The settle
  time and the wait for a free printer are guesses until the real H2S is timed."
- R:135 — "two time limits of the start rule wait on it" — "the start rule" is a new name
  (R has "start gate" and "hold"; the plan says "the timed rule after a start command") and
  the two limits are not named — replace with "the timed rule after a start command rests on
  two limits that only the H2S can settle: the settle time (5 min) and the 2 minutes before an
  end naming the file can count as this print's end".
- R:76 and R:126 — "has not passed the start gate" against "cancellation up to the start
  command" — one limit described two ways; the start gate is the limit — at R:126 write
  "cancellation up to the start gate".
- R:153 — "**Pairing with a code the daemon makes.**" — the daemon makes the code as built too
  (R:24), so the heading names what does not change — replace with "**Pairing with a code a
  user types once.**".
- R:160-161 — "A daemon that was off reconnects with no pairing again; its token has no end
  date. Most of this is built." — does not say which part is not built — replace the last
  sentence with "Built, except that the daemon's settings file gains the daemon id and loses
  the lasting pairing code."
- R:171-172 — "so the relay's secret key can be replaced without pairing again, within a week"
  — must be read twice: within a week of what — replace with "so the relay's secret key can
  be replaced without pairing again: a daemon that syncs within a week of the replacement is
  given a new token, and one switched off for that whole week must be paired again".
- R:162-164 — "An idle daemon's sync is held up to 55 s … ; each second while it takes a job;
  every 10 s during a print; at once on a change." — the subject changes silently after the
  first clause — replace with "An idle daemon's sync is held up to 55 s and answered the
  moment a send arrives (about one request a minute). A daemon syncs each second while it
  takes a job, every 10 s during a print, and at once when the printer changes state."
- R:177 — "the user key" — not in the plan's Terms table (the plan sends the reader to the
  architecture for it) and not defined in R — write "the user key (the signed-in user's
  Onshape id)".
- R:65-66, R:79 — "a secret key that signs the daemons' tokens", "a code for a token" — the
  token is never said to be what the daemon presents on every later request — at R:79 write
  "the pairing exchange (the daemon trades its pairing code for a **token**, which it presents
  on every later request)".
- R:49 — "a stand-in printer" — a second kind of printer beside "the simulated printer", not
  defined; reads as a second name for the same thing — write "a stand-in printer (a fake
  inside the process, not the simulated printer)".
- R:77 — "a stale delivery job past the start gate" — "stale" is explained only at R:96-97,
  and the routes table comes before the section that explains queued, running, stale and stop
  following — move the section "The states of a delivery job" above "Interfaces".
- R:142 — "to change on its own" — reads as "will change by itself" — replace with "changing
  them is a separate change".
- R:138 — "signs everyone in" — unclear — replace with "treats every request as signed in".
- R:131-142 (the list "Not done") — omits what the reader would otherwise assume: a print
  already running cannot be stopped from PenguinSlicer, and the daemon accepts any certificate
  the printer presents (D:52-54) — add one bullet: "**Not handled, by design:** stopping a
  print that is already running (it is stopped at the printer), and checking the printer's
  certificate (the daemon accepts any)."
- R:147-182 — "Daemon telemetry carries the daemon's errors" (R:179) while R:139 says
  telemetry is not designed, and no item of "To be built" says who designs it — add to R:149
  "The messages of the pairing exchange and what daemon telemetry holds are left to phase 5's
  own design spec."
- R:173 — "the pairing-code offer stays 60 a minute" — as built this is called "pairing
  exchanges" (R:116); the reader cannot tell the offer replaces the exchange — write "the
  offer of a pairing code (which replaces the pairing exchange) stays 60 a minute".
- R:41-53 — the table of thirteen make targets — more than a person needs in the second
  section — keep `install`, `test`, `test-properties`, `test-sim`, `test-upstream`,
  `together` and `hardware-smoke`; move the rest to
  [Tests](../../../delivery/README-details.md#tests).

Length and order. 196 lines is right. The order does not serve this reader: the make targets
come second, before the reader knows the interfaces or the state of the work. Suggested order:
What it does; The states of a delivery job; Interfaces; The figures that matter; Where it
stands; To be built; What is not known; How to run and test it (last).

## Check B: README.md agrees with README-details.md

Checked: every figure of R:104-117 against D's two settings tables and the routes table; the
make targets against D:1473-1483 and the Makefile; the routes against D:836-845 and
D:1410-1417; the lists "Built and tested" and "Not done" against D:28-66; every item of R's
"To be built" against D:68-496. All figures agree (5 s, 1 s, 20 s, 2 min, 3 min, 15 min,
5 min, 10 min, 24 h, 10 min, 40 min, 64 kB, the six rate limits, 30 s, 15 min, 55 s, 10 s,
40 s, two hours, one week). Differences:

- R:10 against D:8 — "three parts" against "It has two halves" — the count and the noun differ
  — fix as in Check A.
- R:109 — "Stale limit | 20 s without the daemon" — D:738-741 gives three more causes from
  the start gate on: the printer unreachable (at once), a main state this version does not
  know (at once), no status document for 60 s (`PRINTER_QUIET_SECONDS`); R:96-97 says "daemon
  or printer has gone quiet" but the table gives no figure for the printer — write "20 s
  without the daemon; past the start gate also 60 s without the printer, or at once when the
  printer is unreachable".
- R:81 — "the acknowledgement of a job's end" — in D the acknowledgement is the daemon's word
  on what became of the start: the print seen going, or the delivery job failed or cancelled
  before it started (D:812, D:924-927, D:1415); a delivery job ends later, at the end of the
  print (R:23) — replace with "the acknowledgement (the daemon's word that the print was seen
  going, or that the delivery job failed or was cancelled before it started)".
- R:92-94 — "its stages (waiting for the printer, downloading, uploading, starting, printing,
  waiting for a person)" — D:702-712 has nine; R drops `waiting_for_daemon`,
  `waiting_for_earlier_print` and `start_not_shown` while presenting the list as whole — write
  "its stages (among them waiting for the printer, …)".
- R:50 — "`slowest`" — the target exists in the Makefile (line 40) but D never mentions it —
  add `make -C delivery slowest` to D:1473-1483, or drop it from R.
- R:131-142 against D:39-54 — the two lists "Not done" differ: R adds "No relay reachable from
  another machine" and "One relay process" (both true, from D:1635-1641 and D:822-825), and
  omits D:52-54 "Not handled, by design" — add the bullet given in Check A; no change to D
  needed.
- R:149 — "Phases 2 to 4 need nothing of printer delivery" — D:56 says "Phases 1 to 4", D:70
  "Phases 2, 3 and 4"; not a contradiction, but two wordings in D — no change to R.
- R:160 — "its token has no end date" — D:216-219 carries the exception (a replacement of the
  relay's secret key while the daemon was off for more than a week); R states the exception
  only obliquely at R:171-172 — fixed by the replacement words for R:171-172 in Check A.

## Check C: nothing of the approved design was lost or changed

Rows of the map whose Home is `delivery/README.md`, 60 in all: D124, D148 to D165, D167 to
D178, D186, D189, D226, D227, D233, D245, D246, D257, D269, D275, D310 to D325. Each was
found in D's section "To be built" (D:68-496).

**Missing:** none.

**Changed in meaning:** none.

**Weakened:**

- D175 — spec:526-527 "A healthy idle daemon is never silent for much more than a minute, so
  two minutes means it has missed two rounds." — D:269-270 "A daemon is online if its last
  sync was within 2 minutes; past that the printer-status icon shows Offline and Send is
  disabled." — the reason for the figure is gone, while the matching reason for 40 seconds is
  kept (D:273) — add after D:270 "(a healthy idle daemon is never silent for much more than a
  minute, so two minutes is two missed rounds)".
- D178 — spec:531 "every held sync closes at the same moment" — D:277 "every held sync closes
  at once" — "at once" says soon, the spec says together, which is the reason for the random
  wait — write "closes at the same moment".
- D257 — spec:748 "Pairing needs the code on the daemon's screen." — D:110-137 gives the
  figures (forty bits, fifteen minutes, once, attempts limited) but never the claim itself —
  add to D:110 "Pairing needs the code on the daemon's screen."

**Stated as decided, not decided by the spec** (each to be marked as a proposal):

- D:153-155 — "a new error report (retryable) … one code serves every wrong case" — the spec
  decides the sentence the user is told and that the answer is the same, not an error report,
  its retryable flag or one code.
- D:155-156 — "Over the limit for the user it is `delivery.rate_limited`, as built" — the spec
  names no code for wrong attempts past the limit.
- D:150-151 — "The same answer for every refusal is kept: as built every refused exchange is
  `404 {"error": "not paired"}`" — reads as fixing the status and body of the refusal.
- D:187-188 — "`identify` instead answers the user key, the user's display name and the
  current group" — a new shape for the caller's interface.
- D:192-195 — "a token that verifies but names a daemon no paired-printer record names is
  refused with an answer of its own, and the daemon stops syncing, says it has been unpaired
  and how to pair again" — the spec says only that the next request is refused and the daemon
  says it has been unpaired and waits; "an answer of its own" and "how to pair again" are new.
- D:197-199 — "`delivery.not_paired`, whose meaning changes from … to 'the current group has
  no paired-printer record'" — a code and its new meaning.
- D:199-200 — "The unpaired daemon's answer is not an error report to a user: it is the
  daemon's log line."
- D:203-204 — "a second send while the daemon holds a delivery job is refused as built
  (`delivery.job_in_flight`)" — the spec says only that a daemon holds one delivery job at a
  time.
- D:284-285 — "a sync each second while it takes a delivery job" listed among what the daemon
  gains — spec:899-901 lists three gains (the thread, the 10-second rhythm, the random wait);
  this fourth follows from spec:500 but is the writer's addition to the list.
- D:320-321 — "The grant must be written to the store before the gate answers yes." — a rule
  the spec does not state (spec:666-668 says only that the record holds whether it was
  allowed).
- D:321-323 — "`delivery.job_unknown` then means only an id the relay never had or whose
  record has gone, and `delivery.daemon_never_reported` … means no daemon heard since the
  printer was paired" — two codes given new meanings.
- D:346-347 — the download stays `GET /printer/download/<token>` "with the token in the path
  as its whole authority" is described as built, and D:387-399 does not say whether, under
  the design, the download is counted for the daemon or still for the address — state it as
  open or as a proposal.
- D:353-355 — "`delivery.sliced_file_too_old`, with its figure changed; … `delivery.download_failed`,
  as built" — codes assigned to the design's rules.
- D:389-393 with D:395-399 — the design gives no figure for the limits counted per user and
  per daemon, nor for wrong pairing codes per user, and D does not say whether 120, 10, 120
  and 60 a minute carry over — say that the figures are not decided.
- D:401-402 — "`delivery.rate_limited` on a caller's route, as built; a daemon's route answers
  `429` with `Retry-After`, as built" — keeps two built answers by decision of the writer.
- D:411-412 with D:420-421 — "answers every held sync at once" when asked to stop is the
  spec's; what the answer carries (no job, as at 55 s) is not said — state it.
- D:444-475 (the section "From the wizard's mockup") — none of it is in the spec; it comes
  from the mockup's DECISIONS.md, which D cites. D:468-470 "So a delivery job's record carries
  the sender's display name, the plate's one-line description, the time the delivery job ended
  and, for a failure, the layer at which it stopped; and a page that has lost its state can
  ask for its user's live delivery job and that user's last print" is the writer's design from
  those requirements, and "12 hours" (D:460, D:475) is the mockup's figure, not the spec's —
  mark the paragraph as a proposal answering the mockup.
- D:158-167, 202-206, 239-242, 295-302, 325-331, 357-360, 382-385, 404-407, 420-422, 440-442,
  472-475 (every paragraph "*Tests:*") — the spec requires tests only for the rows of its
  restart tables (spec:710-713) and for the key replacement (spec:805-806); the other tests
  and their figures ("sixteen minutes old", "a simulated week", "41 s", "1 h 59 min", "2 h
  1 min") are derived by the writer — one sentence at D:72-75 saying that the tests listed are
  the writer's proposal, derived from the design, is enough.

Spot-checked against the code, all true: `STALE_AFTER_SECONDS = 20` (`deliveries.py:75`),
`SLICE_MAX_AGE_SECONDS = 40 * 60` (`routes.py:41`), `EXCHANGE_LIMIT` 60 and `DOWNLOAD_LIMIT` 30
a minute (`routes.py:47-48`), `EXCHANGE_INTERVAL = 30.0` (`run_loop.py:56`), `issue_token`
signing `{'code', 'iat'}` (`relay.py:184`), `begin_exchange` (`relay.py:437`),
`RECORD_TTL_SECONDS` 24 h (`relay.py:37`).
