# Review of the whole set, across documents

Written Fri 2026-11-27, Pacific time. Method: the four lenses of the document review,
applied across the set, with
[the decision map](decision-map.md) as the authority on what was decided.

**Verdict.** The set is not ready to merge as it stands, and it is close: its figures
(two hours, 55 s, 10 s, 40 s, 2 minutes, thirty days, one week, 25 parts, 7.5 MB,
6,000 MB, 240 s) agree everywhere, every one of its relative links and anchors resolves,
and none of the retired names survives. What stops it is that the fifteen items awaiting
the owner are stated as settled in the plan, the architecture, the front server's guide
and printer delivery's guide (in two places with the side that is *not* recommended),
and that the plan's phase 3 list disagrees with the wizard's and the front server's
guides on which phase builds retrying, the cookie and the log. Every fix below is a
sentence or a link; none needs a document restructured.

Findings: 11 under heading 1, 5 under heading 2, 3 under heading 3, 5 under heading 4,
2 under heading 5.

The set, as reviewed: [README.md](../../../README.md), [CLAUDE.md](../../../CLAUDE.md),
[the plan](../../plans/penguin-slicer-plan.md), [the architecture](../../architecture.md),
the guides of [the slice service](../../../slice/README.md),
[printer delivery](../../../delivery/README.md), [the front server](../../../front/README.md)
and [the wizard](../../../wizard/README.md), the contracts
([README](../../../contracts/README.md),
[wizard and front server](../../../contracts/wizard-front-server.md),
[configuration](../../../contracts/configuration.md),
[plate configuration](../../../contracts/plate-configuration.md), "To be built" only), and
the four details files ([slice](../../../slice/README-details.md) and
[delivery](../../../delivery/README-details.md): opening note and "To be built" only;
[front](../../../front/README-details.md) and [wizard](../../../wizard/README-details.md):
whole).

## 1. The set disagrees with itself

Most serious first.

- **The front door and the architecture never say that fifteen items await the owner.**
  `wizard/README.md:6` — "Fifteen items await the owner's choice or yes" — against
  `docs/plans/penguin-slicer-plan.md:6-7` — "Where something is open, it says so" — and
  `docs/plans/penguin-slicer-plan.md:254-264`, which lists the thirteen rulings and the
  mockup's questions M1 to M29 and nothing else; `docs/architecture.md:546-595` ("To
  confirm before building on it") lists none of them either. The decision map's
  "Awaiting the owner" says the living documents "state the recommendation and mark it as
  not yet confirmed"; a reader of the plan and the architecture alone takes the design as
  final. Fix: the plan gains one bullet under "Where things stand" ("Fifteen items where
  the mockup and the hosted design differ await the owner; three need a choice", linking
  `wizard/README.md#where-the-mockup-and-the-design-differ`); the architecture gains one
  bullet under "To confirm before building on it" with the same sentence and link.

- **Items 1.1 and 1.4 (how long a sliced file lives) are stated as settled, with the
  design's answer and not the recommendation.** `docs/architecture.md:38-39` — "the state
  bucket keeps each sliced file for two hours after its slice"; `:206` — "A sliced file is
  kept for two hours after its slice ended"; `:363`; `:465-466`; `front/README.md:35` and
  `:96`; `front/README-details.md:498-499` — "sent again after a print, for two hours
  after its slice ended"; `delivery/README.md:150-151` — "the oldest file sent rises from
  40 minutes to two hours"; `delivery/README-details.md:353-354`. Against
  `wizard/README.md:33-34` — "(items 1.1 and 1.4 below may move either end)" — and
  `wizard/README.md:122-124` — "Recommended: keep a sliced file until two hours after its
  slice or after its last print ended, whichever is later", which
  `wizard/README-details.md:468-469` says "changes the front server's two-hour rule and
  printer delivery's limit". Only the wizard's guide and
  `contracts/wizard-front-server.md:213-217` mark it. Fix: at `docs/architecture.md:206`,
  `front/README.md:35`, `front/README-details.md:498` and `delivery/README.md:150`, add
  one parenthesis: "(not yet confirmed: items 1.1 and 1.4 of the wizard's guide; the
  recommendation extends the two hours to two hours after the last print ended)", linking
  `wizard/README.md#where-the-mockup-and-the-design-differ`.

- **Item 1.8 is stated as fact with the side that is not recommended.**
  `front/README-details.md:395-396` — "its error report reaches the page on the part's
  own row" — and `slice/README-details.md:163-164` — "refused on the wizard's Parts step,
  on its own row" — against `wizard/README.md:146` — "A part that cannot be used | A
  notification, not added | A row with its error | The mockup" — and the decision map's
  "a notification, and the part is not added … Not yet confirmed". A builder of the front
  server or the slice service is told the opposite of the recommendation. Fix: both
  details files drop "on its own row" / "on the part's own row" and say "is shown on the
  Parts step (as a row or a notification: item 1.8 of the wizard's guide, not yet
  confirmed)".

- **Item 1.9 (how long the page retries) is stated as settled, with the design's
  answer.** `docs/architecture.md:426-428` — "the user sees a pause, not an error";
  `front/README.md:163` — "the page retries, so a user sees a pause";
  `front/README-details.md:655-656`. Against `wizard/README.md:125-129` — "Recommended:
  the mockup's 20 seconds", needing the owner's choice. Fix: `docs/architecture.md:428`
  and `front/README.md:163` add "(how long before an error shows is item 1.9 of the
  wizard's guide, awaiting the owner's choice)".

- **Items 1.7, 2.1 and 2.5 (what the configuration holds) are missing from every
  statement of the configuration outside its contract.**
  `docs/plans/penguin-slicer-plan.md:59` — "the filaments with each filament's own
  profiles, and whether parts uploaded from files are read in inches or millimetres";
  `docs/architecture.md:225-227`; `front/README.md:136`; `front/README-details.md:524-526`.
  Against `contracts/configuration.md:43-65` — "Recommended, needing the owner's yes …
  the configuration names the printer's Orca profile … each profile carries the group's
  own name and its purpose". Fix: `docs/architecture.md:231` and `front/README.md:138`
  each gain one sentence: "Three additions to what it holds are recommended and not yet
  confirmed", linking `contracts/configuration.md#recommended-needing-the-owners-yes`;
  the plan's term stays as it is and is covered by the plan bullet of the first finding.

- **Which phase designs the configuration's edit screens.**
  `contracts/configuration.md:36-37` — "The configuration's edit screens are a feature of
  their own, phase 4's to design" — and `wizard/README-details.md:349-350` — "The
  configuration's edit screens are phase 4's to design" — against
  `docs/plans/penguin-slicer-plan.md:500` — "A feature of their own, in no phase yet, with
  a design spec of their own" — and the decision map's D4, "in no named phase". Fix:
  `contracts/configuration.md:37` and `wizard/README-details.md:350` change to "in no
  phase yet (the plan, Known future work)".

- **Which phase builds the wizard's retrying.**
  `docs/plans/penguin-slicer-plan.md:375-376` — phase 3: "the wizard (retrying, reloading
  on a new version)" — against `wizard/README.md:164` — phase 2: "…progress streams,
  retrying, the current group…" — and `wizard/README-details.md:415-416` — "this table
  puts retrying in phase 2". Phase 2 also tests the slice container's restarts, which
  need the page to submit again unasked. Fix: the plan changes: phase 3's wizard list
  becomes "(Onshape sign-in and 'sign in again', the header on every changing request,
  reloading on a newer version)", and phase 2's Components names the wizard's retrying
  "as its guide proposes".

- **Which phase builds the cookie, the check of the current group, and the gathering of
  the log.** `docs/plans/penguin-slicer-plan.md:373-374` — phase 3: "the front server
  (Onshape sign-in, the cookie and the two cookie keys that encrypt it, groups, the state
  bucket and the log bucket, the gathering of the log)" — against `front/README.md:180` —
  phase 2: "the development identity and the cookie; the user key and the current group's
  check; … the log (its phase to be settled)" — and `front/README-details.md:777-785`.
  The plan gives phase 3 three things the front server's guide gives phase 2, and states
  as settled one the guide marks as open. Fix: the plan changes to "(Onshape sign-in, the
  second cookie key, groups read from Onshape, the buckets at R2)" and adds "the phase of
  the log's gathering is settled in phase 2's design spec; the front server's guide
  proposes phase 2".

- **A thing to confirm that is already answered.** `docs/architecture.md:585-586` — "The
  daemon after a cut-off fetch. Whether the daemon fetches a sliced file again when the
  connection drops mid-way was not read from its code" — against
  `delivery/README-details.md:515-518` — "the code as built does, up to three attempts" —
  and the decision map's D366, "this leaves the list of things to confirm". Fix: the
  architecture deletes that bullet; `delivery/README-details.md:515-518` then drops its
  sentence about the architecture's list.

- **How long a user's last print can be found: a day or 12 hours.**
  `delivery/README-details.md:180-181` — "A delivery job's record is kept for a day after
  the delivery job ends, so the Send step and the printer-status icon can show how the
  last print ended" — and `wizard/README-details.md:386-388`, the same — against
  `delivery/README-details.md:496-497` — "that user's last print is found for 12 hours
  after it finished" (the mockup's figure, marked proposed at `:489`). The difference is
  not among the fifteen items. Fix: `delivery/README-details.md:489-497` says which holds
  (the record is kept a day; whether the last-print note shows for 12 hours of it is
  written with the wizard's steps) and the test follows.

- **How soon a print's status is back after a front server restart.**
  `docs/architecture.md:398` — "within ten seconds, plus the daemon's short random wait,
  of the front server answering again" — against `wizard/README-details.md:782` (screen
  3.9) — "within ten seconds of the front server answering again" — and
  `delivery/README-details.md:341-342`, the same without the wait. The decision map lists
  this as a disagreement of the spec that the architecture corrected. Fix: both details
  files add "plus the daemon's short random wait".

## 2. One name per thing

Checked and clean: no "the wizard's server side" outside the rule that forbids it
(`CLAUDE.md:49`); no "four components"; "AWS" appears once, as the place to go when
leaving Railway (`docs/architecture.md:134`), never as the host; "student", "mentor" and
"team" appear only in the rules about them and in the as-built identifiers `Team` and
`team=`.

- **"Configuration" means two things.** `delivery/README-details.md:20-21` (the opening
  note) — "the configuration (the settings an administrator keeps for everyone who uses
  PenguinSlicer, the pairing code among them)" — against
  `docs/plans/penguin-slicer-plan.md:59` — "one document for each group … holds no
  secret" — and `contracts/configuration.md:22-24` — "the pairing code … is no longer
  kept in the configuration". Fix: `delivery/README-details.md:19-21` changes to "or of
  where the caller keeps the pairing code it presents (as built; phase 5 replaces this,
  see To be built)".

- **The details file is called "printer delivery's guide".**
  `docs/plans/penguin-slicer-plan.md:435` — "every line of the hardware checklist in
  printer delivery's guide" — and `:443-444` — "Its checklist is in printer delivery's
  guide, [Before trusting it at the H2S](…/delivery/README-details.md#…)" — against the
  plan's own term (`:61`): the guide is `README.md`, and `:484` — "printer delivery's
  detailed guide". The checklist is not in `delivery/README.md`. Fix: the plan says
  "printer delivery's detailed guide" at `:435` and `:443`.

- **"Item 2.4" and "need 2.4".** `wizard/README.md:6` and `:138` count and head all
  fifteen as "items"; `wizard/README-details.md:442`,
  `contracts/wizard-front-server.md:233` and `:249`, and `contracts/configuration.md:59`
  and `:65` call 2.1, 2.4 and 2.5 "need 2.x". Fix: the three files that say "need 2.x"
  say "item 2.x".

- **"The Onshape app", "the OAuth app", "the Onshape OAuth app"; "the owner", "the
  project's owner".** The plan and the architecture say "the Onshape app" and "the owner"
  throughout (`docs/plans/penguin-slicer-plan.md:388`, `docs/architecture.md:246`);
  `front/README.md:57` and `:189` say "the OAuth app", `front/README-details.md:49` and
  `wizard/README-details.md:319` "the Onshape OAuth app"; `front/README.md:30-31`,
  `contracts/configuration.md:38` and `front/README-details.md:64-65` say "the project's
  owner". Fix: the front server's guide and details, the wizard's details and the
  configuration's contract use "the Onshape app" and "the owner".

- **"FRC shops" on the front page.** `README.md:3-4` — "3D printing for FRC shops … send
  the result to the shop's printer" — against `docs/plans/penguin-slicer-plan.md:194-195`
  — "PenguinSlicer is used by people who are not FRC teams". Fix: `README.md:3-4` takes
  the plan's sentence (`docs/plans/penguin-slicer-plan.md:11-13`): "takes parts, lays
  them out on a printer's plate, slices them with Orca on a server and sends the sliced
  file to the printer".

## 3. Each thing explained once

- **Two lists of the front server's are written out in full in the contract.**
  `contracts/wizard-front-server.md:91-106` (which requests carry the current group) is
  `front/README-details.md:228-240` almost word for word, and
  `contracts/wizard-front-server.md:82-89` (which routes need the header and the origin
  check) is `front/README-details.md:318-323`. The decision map's Home for both (D119,
  D140) is the front server's guide. Fix: the contract keeps, for each, the rule in one
  or two sentences and its link to
  `front/README-details.md#groups-and-the-current-group` and
  `#requests-from-other-sites`; the lists stay in the front server's details.

- **Onshape's yearly allowance is explained four times.**
  `docs/plans/penguin-slicer-plan.md:388-394` (six sentences),
  `docs/architecture.md:246-251`, `docs/architecture.md:565-569` and
  `front/README.md:57-71` with its table. The decision map's Home is the front server's
  guide (D128, D130, D136, D138); the plan owns only the owner's intent to make the app
  public (D129). Fix: the plan's paragraph keeps "the owner intends to make the app
  public; until then development and testing must fit inside the allowance" and links
  `front/README.md#signing-in` for the figures; `docs/architecture.md:246-251` shrinks
  to one sentence with the same link; the bullet at `:565-569` keeps only what is
  unchecked.

- **The architecture's "Sign-in" and "Printers" go past its own rule.**
  `docs/architecture.md:10-12` — "this document gives a few sentences and a link wherever
  a guide holds the full explanation" — against `docs/architecture.md:235-244` (nine
  sentences on the cookie, groups and the current group, all owned by
  `front/README.md:40-76`; D120 to D133) and `docs/architecture.md:259-272` (nine
  sentences on pairing and the syncs, owned by `delivery/README.md:133-147`; D148
  onward). A reader following the plan's order reads each twice. Fix: the architecture
  cuts each section to three sentences (what crosses components: one cookie and no
  session on the server; a pairing code used once and the held wait) and keeps its
  closing links.

## 4. Reading order and links

Every relative Markdown link in the sixteen files was checked by script against the
target file and its headings: no file and no anchor is missing. The findings below are
links that resolve to the wrong place, or to a place that does not hold what the sentence
promises, and terms a document's declared prerequisites do not give.

- **Three documents cite `contracts/README.md` for a rule it does not hold.**
  `contracts/configuration.md:33-35` — "the document carries the number of its format …
  ([the contracts](README.md))"; `front/README-details.md:563-564`;
  `delivery/README-details.md:325-326`. `contracts/README.md` (17 lines) says nothing of
  a format number, though the decision map makes it the Home of D343. Fix:
  `contracts/README.md` gains one sentence after its table: "Each record kept in the
  state bucket carries the number of its format, so a record written by an older front
  server is read by a newer one ([the architecture](../docs/architecture.md#old-and-new-versions-together))."

- **`#tests` lands on the wrong section.** `front/README.md:174` — "More:
  [Tests](README-details.md#tests)" — and `front/README-details.md:43` (Contents).
  `front/README-details.md` has eighteen headings named "Tests"; `#tests` is the first,
  the tests of Onshape sign-in at `:143`, not the section at `:746` the sentence means.
  Fix: `front/README-details.md:746` is renamed "## The fast suite" and both links
  become `#the-fast-suite`.

- **The contract between the wizard and the front server uses the architecture's terms,
  and the plan says to read contracts after the plan alone.**
  `docs/plans/penguin-slicer-plan.md:40` — "contracts/ | This plan" — against
  `contracts/wizard-front-server.md:93` ("the current group"), `:114` ("the part
  store"), `:159` ("the state bucket"), `:162` ("the slice container") and `:251`
  ("paired-printer record"), none defined there or in the plan's Terms
  (`docs/plans/penguin-slicer-plan.md:103-105` only names them). Fix:
  `contracts/wizard-front-server.md` gains, after its second paragraph, "Read after:
  [the architecture](../docs/architecture.md#terms), whose terms it uses", and the
  plan's table row for `contracts/` says "This plan; for the contract between the wizard
  and the front server, the architecture".

- **The wizard's guide uses two things its reader has not been given.**
  `wizard/README.md:63` — "the slice container restarted" — is the first and only use of
  "slice container" in the guide, which is read after the plan, where the term is not
  defined; `wizard/README.md:113` — "The numbers are those of the comparison the items
  come from" — names a comparison the guide never identifies (it is
  `docs/orchestration/hosted-architecture/mockup-against-design.md`, named only at
  `wizard/README-details.md:429`). Fix: `wizard/README.md:63` says "the slice service
  restarted"; `:113` links the comparison.

- **The wizard's details cite printer delivery's guide for rules only its details
  hold.** `wizard/README-details.md:372-374` — "every wrong code gets that one answer
  ([printer delivery](../delivery/README.md))" — and `:378-380` — "refuses a send to a
  printer that is printing, whether PenguinSlicer sent the print or someone started it
  at the printer's own screen ([printer delivery](../delivery/README.md))". Neither is in
  `delivery/README.md`; they are at `delivery/README-details.md:136-138` and `:276-278`.
  Fix: the two links point to `../delivery/README-details.md#pairing` and
  `#how-often-a-daemon-talks-to-the-relay`.

No human guide needs its details file to be understood, with one deliberate exception:
`wizard/README.md:114-115` sends the owner to the details to decide the fifteen items
("decided there, not from this page").

## 5. Built against to be built

The four guides are clear: the slice service's and printer delivery's say everything
outside "To be built" is true of the code, and the front server's and the wizard's say
nothing is built. The two findings are in the plan.

- **The Cleanup requirement states the phase 2 behaviour as present.**
  `docs/plans/penguin-slicer-plan.md:211-213` — "A slice job is the exception: it goes on
  when its page goes away, bounded by the slice service's time limit" — against
  `slice/README.md:113-115` — "in phase 2, the rule that a slice job nobody follows is
  cancelled 120 s after its last follower left" changes. Today the code does the opposite
  of the plan's sentence. Fix: the plan adds "from phase 2; as built, a slice job nobody
  follows is cancelled after 120 s".

- **"Brought up to the standing requirements" now includes two requirements neither
  component meets.** `docs/plans/penguin-slicer-plan.md:249-253` — "The slice service is
  ported from the print branch, brought up to the standing requirements … Printer
  delivery is ported and brought up to the standing requirements" — against the standing
  requirement Deploys (`:215-219`), added after both were built, and
  `delivery/README.md:117-118` — "Every record lives in that process's memory and is
  lost when it restarts" — and `slice/README.md:42-43` — "SIGTERM or Ctrl-C cancels
  every slice job". Fix: the plan's two bullets say "brought up to the standing
  requirements except Deploys, which its guide lists under To be built".

## 6. For the owner's final read

Read the plan first (512 lines; its Terms and phases are what every other document is
checked against), then the wizard's guide (181 lines), because it holds the fifteen items
only the owner can settle and its answers change sentences in three other documents;
then the architecture (595 lines), the front server's guide (200 lines), the slice
service's guide (190 lines) and printer delivery's guide (200 lines), reading only "To be
built" and "What is not known" in the last two, since the rest describes code already
reviewed; then the configuration's contract (65 lines) and the contract between the
wizard and the front server (272 lines); the front page (35 lines), the notes for agents
(92 lines) and the contracts' index (17 lines) need a glance only. The weakest single
document is the plan: it is the front door, and five findings change it (it does not
mention the fifteen items, its phase 3 list disagrees with two guides, it states one
requirement as built that is not, it calls two components up to requirements they do not
all meet, and it carries the Onshape allowance in full). The architecture is second: it
states three open items as settled, keeps one answered question as open, and runs past
its own "a few sentences and a link" rule in two sections.
