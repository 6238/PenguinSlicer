# Cross-check of the four guides

Checked Fri 2026-11-27, Pacific time: [the slice service's guide](../../../slice/README.md),
[printer delivery's guide](../../../delivery/README.md),
[the front server's guide](../../../front/README.md) and
[the wizard's guide](../../../wizard/README.md), read against each other, against
[the decisions of Fri 2026-11-27](decisions-2026-11-27.md),
[the architecture](../../architecture.md) and [the plan](../../plans/penguin-slicer-plan.md).

## Verdict

The four guides are ready for the owner: after the corrections below, every exchange
between two components is described the same way from both sides, and each open question
is one item in one guide with a pointer from the others. The owner should read first the
24 items in the table at the end that must be answered before phase 2 can be built,
starting with [Orca's own sentence under Details](../../../wizard/README.md#orcas-own-sentence-under-details),
which only the owner may settle, and then the wizard's
[Where to look first](../../../wizard/README.md#where-to-look-first). Two contracts and two
details files still say what the guides said before these corrections; they are listed
under "Other documents now out of line".

Every relative link and anchor in the four guides resolves (372 links, checked by script
after the last edit). The `mermaid` diagrams were not changed and were not rendered in
this check.

## Corrections made

### The wizard's guide (30)

1. "Profile" is defined in the plan's words (one of Orca's named bundles, offered under
   the group's own name), not as "a named set in the configuration".
2. The terms name the plan's "the daemon's computer" beside the panel's words for it.
3. "Where to look first" counts twelve gaps and twelve smaller items.
4. "Who writes the sentences of a failure" no longer states Orca's sentence under
   Details as the design; it says the matter is undecided and links to the item (two
   passages).
5. The units table marks Orca's sentence as shown only if the undecided item is answered
   that way.
6. "When the server is slow" gives the slice service's recommendation for a submission
   made during a stop, and what a user would then see.
7. "The owner of the service" is "the owner", as in the other guides (three places).
8. The cancelled-slice example names the slice service's stage, "Generating walls"; it
   said "Generating perimeters", which is no stage of the slice service's.
9. The slicing card's row for a restarted slice service also covers a slice that was
   waiting when the slice service was asked to stop, which the page submits again.
10. "When a slice fails" says in its text and its table that the quotation of Orca's
    sentence is undecided.
11. A row is added for the slice service's failure "a profile or setting is not
    accepted", which the table lacked; its button, Back to Settings, is marked proposed.
12. "After Send" says that the stage in words is printer delivery's, and proposes which
    of printer delivery's nine stages stands under which word of the track; printer
    delivery's guide said the wizard's guide gives this, and it did not.
13. Cancelling a send follows printer delivery's rule: refused from the moment the relay
    allows the start, with printer delivery's two sentences. The guide had "the card says
    the print has started", which printer delivery never claims (three passages).
14. "Gone quiet" is tied to printer delivery's word "stale"; a printer that can take a
    send is "free", not "idle".
15. The example for too many wrong pairing codes says "Wait a minute", which is what
    printer delivery's proposed limit of ten a minute gives; it said "a few minutes".
16. A part's "fingerprint" is its "hash", the architecture's term (eight places).
17. "Reading a part without changing it" keeps two sentences of the reason and links to
    the slice service's "Units", which owns the rule.
18. The table of asks: the expiry moment links to the front server's new item; the list
    of settings names the slice service's item and recommendation; Orca's sentence is
    conditional on the owner's answer; a row is added for the report that tells a cancel
    at a stop from the other two.
19. "Progress connection" is "progress stream".
20. Choices 1 and 2 no longer say that the front server's guide disagrees, since it now
    agrees; the contract and the details file still do.
21. The list of smaller proposed rules has eight, with the two added in 11 and 12.
22. New gap, in full: "Orca's own sentence under Details", with both sides, what a user
    sees under each, what each risks and a recommendation.
23. "Where advanced mode's settings come from" recommended a list made when the slice
    service's image is built, which the slice service's guide rejects. It is now a
    pointer to the slice service's item, with that item's recommendation.
24. "Sign-out" is the one item for signing out, with the other choice stated.
25. "The limit on wrong pairing codes" agrees with the corrected example.
26. "Who writes the one-line description of a plate" says how the description reaches
    the relay and that the other two guides note it.
27. "What only real Onshape can settle" links to the front server's item on the cookie
    inside Onshape's panel.
28. "Whether progress reaches the page unheld" is a pointer to the front server's item,
    with the same words for what a user sees (up to two seconds late).
29. New item: "Open items of the other guides that would change the panel" (six
    pointers).
30. Three items (a print no longer followed, the printer's name, the two placement
    checks) link to the matching note in the guide of the component that would do the
    work.

### The slice service's guide (13)

1. "When things go wrong" says that one exception to "never shown as it is" is
   undecided, and links to the item.
2. "Whoever runs the service" is "the owner" (two places).
3. "When asked to stop": a waiting slice job is cancelled with a report that says the
   slice service is stopping, so that the page submits it again and does not take the
   cancel for the user's own.
4. "Report progress" links to the architecture's "Progress streams" for the hosts'
   limits.
5. "Go on without the page" links to the front server's section on following slice jobs.
6. "How long a stopping container is given" points to the front server's item on what
   Railway does at a deploy, which owns the question for both containers.
7. "Railway's limit on the body of a request" is a pointer to the front server's item.
8. The item on the list of settings says it is needed before phase 2 and that the front
   server's guide carries it.
9. The item on what a user sees during a stop says that the front server's guide
   carries it.
10. The item on a configuration that names a lost profile states its recommendation and
    links to the front server's side.
11. New short item: "Orca's own sentence in an error report", linking to the wizard's.
12. New short item: "A plate configuration submitted twice", for the front server's
    recommendation, which asks the slice service to remember a value.
13. New short item: "Shared plates for the two placement checks", for the wizard's
    proposal.

### The front server's guide (25)

1. The table of exchanges says "configuration", not "the group's settings" (two rows).
2. A sign-in sets the cookie and writes its log line; the configuration is read when the
   page opens. The guide had the sign-in read "the current group's" configuration,
   which the front server cannot know then, since the browser keeps that choice.
3. A request refused as not signed in is shown by the page as a message with a button;
   the page does not leave for Onshape by itself (the wizard's choice 1).
4. Chrome is "proposed as the supported browser", with the wizard's item; the guide had
   stated it as decided.
5. "Sign in again" is in the group details, not beside the current group's name (the
   wizard's choice 2; three places).
6. The busy answer says "try again in a minute", the slice service's sentence, and that
   the page does not try again by itself; it said "shortly".
7. A stopping slice service refuses with an answer of its own, as the slice service's
   guide says; the guide had left open which component does this.
8. A quiet progress stream sends "a comment line", the architecture's term, not "an
   empty line" (two places), with a link to the architecture.
9. "A page that comes back" adds the report for a slice job cancelled at a stop.
10. The configuration is read whenever the wizard asks, on opening and at the reload
    glyph.
11. "Running the relay" uses "sync", "held wait" and "held sync" for what it called an
    open request (nine places).
12. "Running the relay" notes the two open proposals about a send.
13. The restart table says the printer's status is not known, shown by the wizard as a
    grey dot, not "blank".
14. The retrying paragraph uses the wizard's words and links to it.
15. "Old and new versions together" carries the rule the slice service's guide proposes
    for the two containers.
16. Four rows of the table of failures follow the wizard's screens (a sign-in run out, a
    sign-in refused, Onshape not answering, a group the user is not in).
17. New item: "A plate configuration submitted while the slice service stops", the
    slice service's recommendation from the front server's side.
18. New item: "The list of settings and the profile catalog's names", likewise, with the
    check of a configuration against the catalog.
19. New item, owned here: "Telling the page when a sliced file expires".
20. New item: "What the wizard's guide asks of the front server" (a report of a failure
    in the browser, signing out, the plate's description).
21. "A plate configuration submitted twice" says which guides point to it.
22. "Signing out" is a pointer to the wizard's item, with the front server's part.
23. The smaller points list the versions rule in place of the bullet settled by 7.
24. "A daemon through Cloudflare" is a pointer to printer delivery's item.
25. "Whether progress arrives as it is sent" is the one item for all four guides.

### Printer delivery's guide (7)

1. With no printer paired, the Send step is described as the wizard has it: no Send, the
   pairing form, the link and the download.
2. A print started at the printer's own screen: the guide says what the wizard shows and
   that the printer's status already gives it.
3. "The printer's computer has not finished pairing" uses the term "the daemon", in the
   wizard's words for it.
4. The sentence for too many wrong codes is printer delivery's and names the wait the
   limit gives; the guide had said the wizard's guide "already promises" a sentence with
   another wait.
5. New item: "What the wizard's guide asks of printer delivery" (the printer's name, a
   print no longer followed, the plate's description, following a print without a
   progress stream).
6. "Progress streams through Cloudflare and Railway" points to the front server's item
   and keeps only printer delivery's part; it said phase 5 where the front server's
   guide says phase 3.
7. "Capacity" links to the front server's item on its memory.

## Disagreements with the architecture or the plan, not fixed

| Where | What disagrees |
|---|---|
| [The plan](../../plans/penguin-slicer-plan.md), lines 326 to 329 and 472 to 474 | The plan gives the Send step to phase 5 and "the download" to phase 2. The wizard's guide (line 1052, and choice 12) has a Send step from phase 2 with Download as its button |
| [The architecture](../../architecture.md), line 405 | The icon and the Send step are "blank" after a restart of the front server. The wizard's guide (line 1161, and choice 10) and now the front server's guide show a grey dot and "…" |
| The architecture, lines 80, 274 to 279 and 372 | The paired-printer record keeps "the time of the daemon's last sync before it last went offline". Printer delivery's guide (line 802) proposes clearing that time when the daemon syncs again |
| The architecture, lines 444 to 458 | "Old and new versions together" has no rule for the front server and the slice service. Both guides propose one (slice, line 904; front, line 770) |
| The plan, lines 188 to 193 | The standing requirement "Errors" keeps Orca's own words for the server log. The wizard's guide shows Orca's sentence under Details on two failures, as the accepted mockup does. Now one undecided item |
| The architecture, lines 82 and 155 to 159 | A page follows a delivery job on a progress stream. The front server's guide recommends short requests for a print instead. Undecided, so not yet a disagreement |
| The architecture, lines 144 to 146 | A slice stopped at a limit is "an error the wizard explains". In the guides the slice service writes the sentences and the wizard shows them as they are |
| The architecture, lines 365 and 394 | The stored plate is kept "until the page, on opening, finds the plate's sliced file expired". The wizard's guide recommends keeping it (its item "Parts dropped on return"). Undecided |

### Other documents now out of line

- [The contract between the wizard and the front server](../../../contracts/wizard-front-server.md),
  lines 66 to 67 (the page starts a run-out sign-in itself) and line 76 ("sign in again"
  is "the header's action"), against the wizard's choices 1 and 2. It also lacks the
  expiry moment, the report of a failure in the browser, signing out, the list of
  settings and the report of a cancel at a stop.
- [The error report's contract](../../../contracts/error-report.md), line 16 ("Never shown
  to a user as it is"), against the wizard's Details, until the owner answers.
- [The wizard's details file](../../../wizard/README-details.md) and
  [the front server's details file](../../../front/README-details.md), as the second
  checks reported; neither was read here.

### Found and not changed

- No guide says which component turns the group's profile (its Orca profile and the
  settings the configuration adds) into the three profile names and settings of a plate
  configuration. The wizard holds the whole configuration, so it is presumably the
  wizard. It needs one sentence before phase 2.
- The printer-status icon reads "Sending 40%". Printer delivery gives the stages before
  the print the first tenth of a delivery job's fraction, so the 40 cannot be that
  fraction. Which figure the icon shows is not stated.
- The notification of a returning page, "The slice of your earlier plate has expired…",
  is worded by the wizard's guide, though an expired sliced file is listed there as the
  front server's failure and so the front server's sentence.
- The wizard's guide says the daemon "reports"; the term is "syncs". Left, since the
  wizard never talks to the daemon and its reader need not learn the word.
- The mockup's remedy for a slice that ran out of time (a profile with thicker layers)
  is not in either guide; both give the slice service's remedy.
- "The log" in the front server's guide (about 48 lines) repeats part of the
  architecture's "Reading what happened". It reads well and was left.

## Every undecided or unmeasured item

One row for each question, under the guide that owns it. "Before phase 2" means the
answer changes what phase 2 builds or what the contracts' requests must hold. "First in
phase 2" is a trial the phase starts with. A pointer to an item owned elsewhere is not
counted again.

| # | Item | Owner | Recommendation | When |
|---|---|---|---|---|
| 1 | Whether a user may read Orca's own sentence under Details | Wizard | Quote it, on two failures only | Before phase 2 |
| 2 | Where the list of settings and the catalog's names come from | Slice | The slice service supplies them through the front server | Before phase 2 |
| 3 | How the list of accepted settings is made | Slice | A generated list of what is accepted; unknown settings refused | Before phase 2 |
| 4 | Which profiles a setting may replace values of | Slice | The process profile only | Before phase 2 |
| 5 | The longest text a text setting may hold | Slice | Set when the check is built, from the catalog | Before phase 2 |
| 6 | The slice service's smaller proposed rules: the fit test on arrival, refusing a part with no units, no "under 5 mm" warning for inches, checking each value, 1 MB for a plate configuration | Slice | As written | Before phase 2 |
| 7 | How a cancel at a stop is told from the user's own and a later slice job's | Slice | A reason in the report, written with the contract | Before phase 2 |
| 8 | A plate configuration submitted twice | Front | A value the page makes for each submission | Before phase 2 |
| 9 | Telling the page when a sliced file expires | Front | The front server sends the moment | Before phase 2 |
| 10 | The front server's six unconfirmed choices (cookie counted from sign-in, finished only once stored, a damaged configuration reported, log in phase 2, threads, the fixed set) | Front | As written | Before phase 2 |
| 11 | The front server's smaller proposals (answers not kept by a proxy, files in pieces) | Front | As written | Before phase 2 |
| 12 | Rate limits for uploads and submissions, and the sweep's interval | Front | The builder proposes figures with phase 2's design | Before phase 2 |
| 13 | Two tabs on one stored plate | Wizard | One tab owns the plate | Before phase 2 |
| 14 | A progress stream that cannot be reopened | Wizard | Failed after 20 seconds; also after 45 silent | Before phase 2 |
| 15 | Failures in the browser that reach no log | Wizard | The page reports them; one log line each | Before phase 2 |
| 16 | STL files in millimetres before the edit screens exist | Wizard | A switch beside the upload area | Before phase 2 |
| 17 | Starting a second plate | Wizard | A New plate action | Before phase 2 |
| 18 | A configuration that cannot be read | Wizard | A red message in place of the step | Before phase 2 |
| 19 | Parts dropped on return, kept while the page is open | Wizard | Keep the plate on return too | Before phase 2 |
| 20 | The Layout step by keyboard | Wizard | Leave it; announce the status line | Before phase 2 |
| 21 | Agreement between the two placement checks | Wizard | Shared plates in both suites; a small margin | Before phase 2 |
| 22 | Browsers other than Chrome | Wizard | Chrome supported, Edge tested | Before phase 2 |
| 23 | Files other than binary STL | Wizard | Binary STL only | Before phase 2 |
| 24 | The wizard's twelve choices and eight smaller proposed rules, those of phase 2 (choice 12 departs from the plan) | Wizard | As written | Before phase 2 |
| 25 | The layer preview's speed without a graphics card | Wizard | Try two or three methods on real sliced files | First in phase 2 |
| 26 | Lay on face, auto-orient and Arrange on real exported parts | Wizard | Try on the eight real parts and round exports | First in phase 2 |
| 27 | The layer preview's frame rate, browser and machine, and a simpler look while moving | Wizard | 30 and 10 frames a second; the look relaxed in motion | First in phase 2 |
| 28 | The wizard's proposed targets for speed and memory | Wizard | As in its table; timed on real parts | First in phase 2 |
| 29 | Whether the browser's storage holds a full plate | Wizard | An amber line on a part that was not stored | First in phase 2 |
| 30 | Saying that a part will need supports | Wizard | Leave it | Later, on real parts |
| 31 | What a user sees while the slice service stops | Slice | The front server keeps the submission | Later: phase 3 |
| 32 | Who notices a configuration that names a lost profile | Slice | The front server checks against the catalog | Later: phase 3 |
| 33 | The rule for old and new versions of the two containers | Slice | Each previous version works against the other's new one | Later: phase 3 |
| 34 | The hosted memory ceiling | Slice | One Orca at 6,000 MB | Later: phase 3 |
| 35 | Orca on the hosted machines, up to the ceiling | Slice | Measure plates of rising weight | Later: phase 3 |
| 36 | What the slice service needs beside Orca | Slice | Measure | Later: phase 3 |
| 37 | Disk, and the part store's overall limit | Slice | Measure; choose a figure before phase 3 | Later: phase 3 |
| 38 | How long a stopping container is given, as it bears on a running slice | Slice | With item 49 | Later: phase 3 |
| 39 | How long the replacement takes to start | Slice | Measure | Later: phase 3 |
| 40 | How often two users slice at once | Slice | Read it from the log | Later: in use |
| 41 | Orca's processor time | Slice | Only if a second Orca is considered | Later |
| 42 | A part whose first layer is empty | Slice | Leave it | Later |
| 43 | Parts that pass through themselves | Slice | Not proposed | Later |
| 44 | Who may sign in | Front | A list of permitted groups; empty means anyone | Later: phase 3 |
| 45 | Sign-ins and the allowance | Front | Limit "sign in again" and all sign-ins in a day | Later: phase 3 |
| 46 | No ceiling on a sliced file | Front | Measure first | Later: phase 3 |
| 47 | Whether the cookie fits | Front | Measure with a real account | Later: phase 3 |
| 48 | No target for the front server's time | Front | Measure the first hosted slices | Later: phase 3 |
| 49 | What Railway does at a deploy | Front | Try it first in phase 3 | Later: phase 3 |
| 50 | A deploy that fails, and learning that the service is down | Front | The check after a deploy tells the owner | Later: phase 3 |
| 51 | Whether progress arrives as it is sent | Front | One hosted slice settles it | Later: phase 3 |
| 52 | Railway's limit on one request | Front | One real upload settles it | Later: phase 3 |
| 53 | The front server's memory | Front | Read it from the log | Later: phase 3 |
| 54 | The cost | Front | The first month's bill | Later: phase 3 |
| 55 | The page shown to Safari | Front | A plain page that names Chrome | Later: phase 3 |
| 56 | Which allowance the owner's account has | Front | Confirm | Later: phase 3 |
| 57 | Whether a second Onshape app shares the allowance | Front | Confirm | Later: phase 3 |
| 58 | An account with no company or classroom | Front | The first such account settles it | Later: phase 3 |
| 59 | Replacing the Onshape app's secret | Front | Check | Later: phase 3 |
| 60 | Sign-out | Wizard | A link in the group details; clears stored work | Later: phase 3 |
| 61 | Stored work is not tied to a user | Wizard | Clear it when another user signs in | Later: phase 3 |
| 62 | The wizard's choices 1 and 2, on signing in | Wizard | As written | Later: phase 3 |
| 63 | The cookie inside Onshape's panel | Front | Break the repeat in phase 3; try partitioned cookies first in phase 4 | Later: phases 3 and 4 |
| 64 | The permissions the Onshape app asks for | Front | Identity in phase 3; documents in phase 4 | Later: phase 4 |
| 65 | Whether renewing a token counts as a call | Front | Count it in phase 4's design | Later: phase 4 |
| 66 | Two requests renewing the tokens at once | Front | Not designed | Later: phase 4 |
| 67 | What only real Onshape can settle | Wizard | Try in real Onshape | Later: phase 4 |
| 68 | How many users at once; following a print without a progress stream | Front | Short requests for a print; four streams a user | Later: phase 5 |
| 69 | After a print is no longer followed | Wizard | A state of its own; never "failed" | Later: phase 5 |
| 70 | Where the name of the printer comes from | Wizard | The daemon sends the printer's own name | Later: phase 5 |
| 71 | Who writes the one-line description of a plate | Wizard | The front server | Later: phase 5 |
| 72 | The wizard's choices 8, 9 and 10, on the printer | Wizard | As written | Later: phase 5 |
| 73 | Clearing the recorded time of silence | Delivery | Clear on return; try a failed clearing again | Later: phase 5 |
| 74 | Unpairing while a delivery job has not ended | Delivery | The relay refuses | Later: phase 5 |
| 75 | Pairing again: three cases | Delivery | Refuse a second code; pair says it is paired; drop an uncollected record | Later: phase 5 |
| 76 | Printed files left on the printer | Delivery | Remove at the print's end, after the session | Later: phase 5 |
| 77 | Daemon versions | Delivery | Record and show the version | Later: phase 5 |
| 78 | Which printers are supported | Delivery | The H2S only, for now | Later: phase 5 |
| 79 | The rate limits of phase 5, wrong pairing codes among them | Delivery | Carry over the built figures; ten wrong codes a minute | Later: phase 5 |
| 80 | A send repeated while its delivery job is live | Delivery | Answer with the same delivery job | Later: phase 5 |
| 81 | How the daemon's fetch is authorised | Delivery | Keep the unguessable address | Later: phase 5 |
| 82 | What is written to a delivery job's record, and deadlines across a restart | Delivery | Five writes; 3 and 15 minutes run on | Later: phase 5 |
| 83 | Daemon telemetry | Delivery | Its own design | Later: phase 5 |
| 84 | The messages of the pairing exchange | Delivery | Phase 5's design spec | Later: phase 5 |
| 85 | The two timed limits on a start | Delivery | Keep the timed rule and measure | Later: phase 5 |
| 86 | The printer's required mode | Delivery | Keep it; state its cost once known | Later: phase 5 |
| 87 | Polling counted against the status allowance | Delivery | Count it apart, if polling is needed | Later: phase 5 |
| 88 | Every timing that concerns the printer | Delivery | The session at the H2S sets them | Later: phase 5 |
| 89 | Whether Cloudflare challenges a daemon | Delivery | Check with a daemon on another machine | Later: phase 5 |
| 90 | Recording and running at once | Delivery | Find out at the session | Later: phase 5 |
| 91 | Windows | Delivery | Try at the session | Later: phase 5 |
| 92 | How long a fetch and an upload take | Delivery | Measure at the session | Later: phase 5 |

92 items in all: 24 before phase 2, 5 first in phase 2, and 63 for a later phase.
