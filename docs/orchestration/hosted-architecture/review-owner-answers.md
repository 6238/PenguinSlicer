# Review of the owner's answers as applied (pull request 20, merge commit 5221890)

Reviewed Fri 2026-11-27 against `git diff 7c8c308 5221890`, by reading the wizard's two
files, both contracts and the changed parts of every other file, and by searching the
whole set for each old rule and figure.

**Verdict.** The four answers are stated the same way in every guide and contract, no
mark survives outside the expected one, and every link and anchor in the wizard's two
files resolves. What remains is one sentence of the old retry rule in the wizard's
detailed guide, a self-contradiction in the decision map, and six consequences the change
did not follow through, the most serious being that the three-day rule at R2 can delete
a sliced file the front server still offers for Send.

Terms used here: **the change** is the merge commit; **the departures table** is the
table "Where this guide departs from the mockup's decisions" in
[the wizard's detailed guide](../../../wizard/README-details.md); **the comparison** is
[mockup-against-design.md](mockup-against-design.md).

## (e) Consequences the change did not follow through

- **The three-day rule at R2 against "a print of any length" and repeated sends.**
  [front/README-details.md](../../../front/README-details.md) lines 516-519: "it is set
  at three days to outlast the longest print and the two hours after it; a print that
  runs longer than that loses its sliced file to the rule". The rule counts from when the
  file was stored, and each print of the same sliced plate moves the front server's due
  time to two hours after that print ended. A plate sent again and again (each send
  within two hours of the last print's end) is still kept by the front server's rule on
  day four, and R2 has deleted it: Send is enabled for a file that is gone, which is the
  failure answer 1 was meant to remove. No document says what the front server answers
  then. The wizard's files say "after a print of any length" without the limit
  ([wizard/README.md](../../../wizard/README.md) line 33,
  [wizard/README-details.md](../../../wizard/README-details.md) line 422,
  [docs/architecture.md](../../architecture.md) line 210). Replace the sentence at
  front/README-details.md 516-519 with: "The rule counts from when a file was stored, so
  it is set at three days to outlast the longest print and the two hours after it. A
  sliced file is therefore never kept past three days after it was stored, whatever its
  prints: a print that runs longer, or a plate sent again and again for longer, loses its
  sliced file to the rule, and (*proposed*) the front server answers a request for such a
  file with the error report saying it has expired, so the user slices the plate again."
  In [the contract](../../../contracts/wizard-front-server.md) line 197, after "whichever
  is later", add ", and never past three days after it was stored". This is a design
  point the owner has not ruled on; the words above are a proposal.
- **Which time the relay writes when a daemon goes offline.** A daemon is offline once
  its last sync is 2 minutes old, so "the time a daemon went offline" is 2 minutes after
  the last sync. [contracts/wizard-front-server.md](../../../contracts/wizard-front-server.md)
  lines 227-231: "it carries the time its daemon went offline ... so the page can say how
  long the printer has been silent (\"Not heard from for 7 minutes.\")". A page that
  counts from the written time understates the silence by 2 minutes. The same words are
  in [delivery/README-details.md](../../../delivery/README-details.md) lines 511-513,
  [docs/architecture.md](../../architecture.md) lines 79, 271 and 366,
  [delivery/README.md](../../../delivery/README.md) line 165,
  [front/README-details.md](../../../front/README-details.md) line 722 and
  [wizard/README-details.md](../../../wizard/README-details.md) line 445. Replace at
  delivery/README-details.md 511-512 "the relay writes the time to the group's
  paired-printer record" with "the relay writes the time of the daemon's last sync to the
  group's paired-printer record", and in the other six places "the time the daemon
  (last) went offline" with "the time of the daemon's last sync before it went offline".
- **A daemon that goes silent just before a restart of the front server.** The relay's
  memory of the last sync is lost at a restart
  ([docs/architecture.md](../../architecture.md) line 368), so a daemon whose last sync
  was under 2 minutes before the restart, and that never syncs again, has no offline time
  written and none to write. The tests at delivery/README-details.md 519-521 cover only a
  time already written. Add to that paragraph: "(*Proposed*:) a relay that starts and
  hears nothing within 2 minutes from the daemon a paired-printer record names, when the
  record holds no offline time later than the daemon's pairing, writes its own start time
  as that time." and to the tests: "a daemon silent from just before a restart of the
  front server has an offline time written 2 minutes after the restart".
- **Nothing says how the front server learns that a sliced file's last print ended.**
  [front/README-details.md](../../../front/README-details.md) lines 501-511 make a file
  due by "the latest delivery job that used it", and a regular sweep deletes due files,
  but the fields of a delivery job's record
  ([delivery/README-details.md](../../../delivery/README-details.md) lines 498-500: "the
  sender's display name, the plate's one-line description, the time the delivery job
  ended and, for a failure, the layer") do not name the sliced file. Add at
  delivery/README-details.md 498, after "a delivery job's record carries": "the slice job
  whose sliced file it sends,"; and at front/README-details.md 511, after "the file is
  kept two hours more": "The front server finds a sliced file's delivery jobs by the
  slice job each delivery job's record names."
- **The plan's phase 5 list of what the wizard needs is the old one.**
  [docs/plans/penguin-slicer-plan.md](../../plans/penguin-slicer-plan.md) lines 494-497:
  "who sent the print going on (the user's Onshape name), the end time of the last print,
  and a way for a page that has lost its state to find its user's delivery job;
  DECISIONS.md lists them". It omits the offline time (answer 3), the one-line
  description, the failure's layer and the last print, all of which
  [delivery/README.md](../../../delivery/README.md) lines 163-166 now lists. Replace
  with: "who sent a delivery job, a one-line description of the plate, when it ended
  and, for a failure, its layer; a page's way to find its user's live delivery job and
  last print; and the time of a daemon's last sync before it went offline, written once
  to the paired-printer record ([printer delivery's guide](../../delivery/README.md)
  lists them under \"To be built\"); each is not provided, or only in part."
- **The decision map's rows for the spec still state the rules the owner changed, with
  nothing pointing to the change.** [decision-map.md](decision-map.md) lines 35 (D7),
  164-167 (D91 to D94), 194 (D111), 404 (D234) and 432 (D247) give "for two hours after
  its slice", "one-day R2 deletion rule ... about two days", "the colour for the layer
  preview" and "a pause, not an error", and the wizard's detailed guide cites [D91]
  (line 421) and [D234] (line 288) beside the new rules. Add under the heading "Decided
  by the owner on Fri 2026-11-27", after its first paragraph: "These decisions replace
  what the rows above record of the spec: 1.1 and the last row replace D7, D91, D92,
  D93, D94 and D247; 1.9 replaces D234; 1.5 replaces D111."
- **The front server's phase 5 does not list the longer lifetime.**
  [front/README.md](../../../front/README.md) line 184: "Hosting the relay, with its
  records in the state bucket"; [front/README-details.md](../../../front/README-details.md)
  lines 831-834 likewise. Phase 2 builds "refusing and deleting sliced files after two
  hours" (correct, since nothing is printed before phase 5), so the half of answer 1
  that waits for phase 5 is in no phase. Replace front/README.md 184 with "Hosting the
  relay, with its records in the state bucket; keeping a sliced file until two hours
  after its last print ended", and add the same clause to the details' phase 5
  paragraph after "supplies the relay its store and the sliced files".
- **"Where things stand" is dated before the answers.**
  [docs/plans/penguin-slicer-plan.md](../../plans/penguin-slicer-plan.md) line 248: "As
  of Thu 2026-11-26:". Replace with "As of Fri 2026-11-27:".
- **The contract says what the page shows between 20 and 300 seconds, less two things.**
  [contracts/wizard-front-server.md](../../../contracts/wizard-front-server.md) lines
  34-36: "then shows that the server is being slow, with a countdown to the next attempt,
  and stops with an error, offering to try again, only after 300 seconds". It leaves out
  that the message says the browser is retrying and that nothing of the user's work is
  dropped. Replace with: "then shows that the server is being slow and the browser is
  retrying, with a countdown to the next attempt, and stops with an error, offering to
  try again, only after 300 seconds; nothing of the user's work is dropped".

Checked and sound: printer delivery's "To be built" gives the relay no two-hour limit
(delivery/README-details.md 351-356 and 366-368 hand the age limit to the front server's
rule, and its tests at 377-383 follow the new lifetime; the 40 minutes at
delivery/README.md 91 and delivery/README-details.md 1171, 1369 and 1452 describe the
code as built). The architecture's table of all the state gives the new lifetime
(line 364) and the offline time in the paired-printer record (line 366).

## (a) Each answer applied everywhere, the same way

- **Answer 2, a survivor of the old rule.**
  [wizard/README-details.md](../../../wizard/README-details.md) lines 287-288: "so a
  request that falls in the gap of a deploy is repeated and the user sees a pause, not an
  error." The same section, 20 lines on, gives the message after 20 seconds and the
  error after 300. Replace with: "so a request that falls in the gap of a deploy is
  repeated, and a user sees nothing of a gap shorter than 20 seconds."
- **Answer 1, two statements that differ.** [decision-map.md](decision-map.md) line 607:
  "the one-day rule at R2 stays as the backstop"; line 624 of the same table: "The
  backstop rule at R2 for sliced files is three days, not one". Replace the clause at 607
  with "a three-day rule at R2 is the backstop (last row)". The two rows also give
  different homes for one rule (607 links the front server's details, 624 names
  `front/README.md`): at 624 replace `front/README.md` with
  `[The front server's details](../../../front/README-details.md#two-hours-deleting-and-the-backstop)`.
- **Answer 2, a softer survivor.** [docs/architecture.md](../../architecture.md) lines
  376-378: "A user may see a pause while the container comes back and its clients
  reconnect. No work of a user's is lost". Replace the first sentence with: "A user may
  see a pause while the container comes back and its clients reconnect, and after 20
  seconds a message that the server is being slow."

Searched and clean: no statement of "two hours after its slice ended" standing alone
survives except where the slice's end is the whole rule (phase 2 at
docs/plans/penguin-slicer-plan.md 332, front/README.md 181 and front/README-details.md
806, which front/README-details.md 501-503 explains). "One-day" and "about two days"
survive only in the decision map's rows for the spec (see (e)). "20 seconds" with "not
added" survives only in the departures table's column for what the mockup says. No
"60 seconds" belongs to retrying. Answer 4 reads the same in all eight places it is
stated. Answer 6 is in README.md lines 3-5.

## (d) The wizard's two files after the rewrite

- **A paragraph cut loose by the rewrite.**
  [wizard/README-details.md](../../../wizard/README-details.md) line 405 begins with a
  space and no subject, after the list that ends at 403: " An edit writes the whole
  document on the condition that it has not changed since it was read". Its lead-in
  (line 383, "The front server reads it when a user signs in and again when the wizard
  asks.") is now separated from it by "What the wizard takes from it:" and three
  bullets. Move lines 405-411 to follow line 383, before "What the wizard takes from
  it:", and remove the leading space.
- **A sentence left in the wrong section.** [wizard/README.md](../../../wizard/README.md)
  lines 132-133, under "The configuration and printers": "There is no \"plate too
  large\" error; a plate too big to slice ends in the out-of-memory error." It concerns
  neither, and a reader of this file alone has met no such error. Delete both lines; the
  rule is in the details ("Errors the wizard explains", lines 282-283) and in the
  departures table, which line 141 already links.
- **Terms used in wizard/README.md and never explained there.** The file is to be
  readable without the details. Line 28 "slice job", line 38 "the slice service", line
  72 "a delivery job", line 126 "the daemon", line 128 "the relay", line 5 "the mockup".
  Replacements: line 5, "from the mockup" becomes "from the wizard's approved mockup
  ([its decisions](../docs/mockups/print-wizard/DECISIONS.md))"; line 28, "the id of the
  plate's slice job" becomes "the id of the plate's slice job (one plate being sliced by
  the slice service, which runs Orca behind the front server)"; line 72, "has a delivery
  job, running or ended" becomes "has a delivery job (one sliced file on its way to the
  printer), running or ended"; lines 125-126, "by typing the code the daemon shows"
  becomes "by typing the code shown by the daemon (the program on a computer beside the
  printer)"; line 128, "because the relay notes" becomes "because the relay (the part of
  the front server that talks to daemons) notes".
- **The inserted paragraph on the sliced file speaks of prints with no phase.**
  [wizard/README.md](../../../wizard/README.md) lines 32-34 sit in "What the page keeps,
  and why", which is otherwise phase 2, and the line break at 34-35 shows the join.
  Replace lines 32-36 (to "sliced file expired;") with: "The stored work stays until the
  page, on opening, finds the plate's sliced file expired. A sliced file is kept until
  two hours after its slice ended or, from phase 5, two hours after its last print
  ended, whichever is later, so after a print, finished or failed, Send is enabled again
  for the same sliced plate. The current group stays until the user changes it."
- **The departures table against the eleven disagreements of the comparison.** Nine of
  the eleven need a row or need none: 1.1 and 1.8 need none, since this guide now says
  what the mockup says; 1.2, 1.3, 1.4, 1.5, 1.7, 1.9, 1.10 and 1.11 each have a row.
  Two rows are incomplete. Line 520, for 1.6, cites "Terms, \"administrator\"; 42", and
  the comparison (line 90) says the same words are in decision 58: replace with "Terms,
  \"administrator\"; 42, 58". Line 525, for decision 47, covers only a plate with a
  delivery job; decision 47's other case (a refresh on the Settings or the Layout step
  opens an empty Parts step, comparison lines 40-43) is the heart of 1.2: at line 524
  replace "45, 46; the requirement on the slice service" with "45, 46, 47; the
  requirement on the slice service" and "A refresh throws the page's state away;" with
  "A refresh throws the page's state away and, with no slice job, opens an empty Parts
  step;".

Checked and sound: every relative link and anchor in both files resolves (17 anchors
from wizard/README.md into the details; from the details, the anchors into the
architecture, the plan, the two contracts, the front server's two files, the slice
service's details and printer delivery's details, and the files DECISIONS.md,
decision-map.md and mockup-against-design.md). No section is left empty by the removal
of the open-items sections; "Still to be written" reads whole in both files. Links to
the removed anchors (`#11-...` to `#19-...`, `#where-the-mockup-and-the-design-differ`,
`#recommended-needing-the-owners-yes`) survive only in the older review records in this
folder, which quote the documents as they were.

## (c) History crept in

No sentence outside the decision map says the owner decided, chose or confirmed one of
these answers, and no item is named by its former number. Five sentences argue against
the side that lost or tell what a document used to say:

- [wizard/README-details.md](../../../wizard/README-details.md) lines 424-426: "The two
  hours count from when the slice ended, which the front server knows from the time
  stored with the sliced file, not from when the user left the page." Delete ", not from
  when the user left the page"; the departures table's row "48; M18" carries the
  difference.
- [wizard/README.md](../../../wizard/README.md) lines 117-118: "read through the front
  server after sign-in, never one opened from a link." and
  [wizard/README-details.md](../../../wizard/README-details.md) lines 381-382: "never
  one opened from a link: a link would bypass the check of the current group against the
  sign-in cookie." No link exists in this design; the departures table's row "What is
  fake, 25" carries it. Replace in README.md with "read through the front server after
  sign-in." and in the details with "read through the front server, which checks the
  current group against the sign-in cookie."
- [contracts/configuration.md](../../../contracts/configuration.md) lines 26-27, written
  by the change: "Orca's own profile names are not names a group would choose, and say
  nothing of a profile's purpose." Delete the clause and end the sentence at "as its
  option's tooltip."
- [contracts/configuration.md](../../../contracts/configuration.md) lines 37-39: "the
  pairing code is typed into PenguinSlicer once and is then dead, and is no longer kept
  in the configuration"; the same at
  [delivery/README-details.md](../../../delivery/README-details.md) lines 141-142.
  Replace "and is no longer kept in the configuration" and "it is no longer kept in the
  configuration" with "and is never kept in the configuration" and "it is never kept in
  the configuration".
- [contracts/wizard-front-server.md](../../../contracts/wizard-front-server.md) lines
  191-193: "(added after the approved design: the Preview step needs the summary after
  the slice container has deleted its copy;"; the same at
  [front/README-details.md](../../../front/README-details.md) lines 468-470. Replace
  "added after the approved design: the Preview step" with "the Preview step" in both.
  These two may predate the change; they break the same rule.

## (b) No mark survives

No finding. The one mark left is the expected one,
[docs/plans/penguin-slicer-plan.md](../../plans/penguin-slicer-plan.md) lines 257-258,
"Thirteen design rulings in those two guides ... are not yet confirmed by the owner".
Marks of *proposed* remain, as answer 2 allows. One thing does still wait for the owner
and is correctly stated as such, not as a mark on a decided item: the mockup's open
questions M1 to M29 (the plan, lines 295-298; wizard/README.md lines 159-160;
wizard/README-details.md lines 559-562).
