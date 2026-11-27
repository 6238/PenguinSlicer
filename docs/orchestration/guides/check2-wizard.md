# Second check of the wizard's guide

The guide is ready for the owner. Every finding of the first review that concerned the
guide is fixed, the three places a reader must find from "Where to look first" exist, are
linked and are now complete, and one departure of the fixer's (Orca's own sentence taken
out of a failed slice's Details) is put back, which leaves a disagreement with the slice
service's guide for the coordinator.

Checked Fri 2026-11-27: [the guide](../../../wizard/README.md), 2,299 lines after this
check (2,262 before it), read from its first line to its last, against
[the first review](review-wizard.md), [the decisions of Fri 2026-11-27](decisions-2026-11-27.md),
[the mockup's decisions](../../mockups/print-wizard/DECISIONS.md),
[the plan](../../plans/penguin-slicer-plan.md),
[the slice service's guide](../../../slice/README.md),
[the front server's guide](../../../front/README.md) and
[printer delivery's guide](../../../delivery/README.md).

## The first review's findings

The first review has 71 findings under its four headings and 5 cuts under "Length".

| Group | Findings | Fixed | Not fixed | Fixed with a new problem |
|---|---|---|---|---|
| 1. Can the reader decide from it | 23 | 22 | 0 | 1 |
| Length | 5 | 5 | 0 | 0 |
| 2. Written for a person | 13 | 13 | 0 | 0 |
| 3. True | 27 | 25 | 2, both outside the guide | 0 |
| 4. One name per thing | 8 | 8 | 0 | 0 |

- **Fixed with a new problem (1).** "Who writes each sentence of a failure" is now a
  section with a table, and it is right. In writing it the fixer removed Orca's own
  sentence from the Details of the two slice failures and wrote "never Orca's raw
  output". The mockup's accepted decisions show that sentence to the user (see
  [Orca's sentence](#orcas-sentence-under-details)). Put back in this check.
- **Not fixed, outside the guide (2).** Both concern
  [the wizard's details file](../../../wizard/README-details.md), which a second check
  does not edit: the small rules of the mockup's decisions 13, 33, 36 and 44 are still in
  neither file; and the details file still says it is "begun, not complete", gives the
  Send step to phase 5, puts "sign in again" beside the current group's name and has the
  page start a run-out sign-in by itself.
- Everything else is fixed as the first review asked: the contents list and "Where to
  look first"; the table of choices; the eleven gaps written as undecided items with
  options and a recommendation; the cut of "What the mockup faked" with its four live
  requirements moved to their places; the terms (panel, joined box, setting group, gone
  quiet); the mockup's decisions 3, 4, 26, 42, 53, 57, 59, 61 and 64 carried in full.

## The three places a reader must find

| Place | Exists and is linked | Complete before this check | Now |
|---|---|---|---|
| The screens designed here and not in the mockup | Yes | No. Five proposed screens were missing (a confirmation, a configuration that cannot be read, a part the page cannot draw, the icon and details after a print is no longer followed, a part the browser refuses to store), and three states were in no row (a group the user no longer belongs to, a filament or profile gone at a reload of the configuration, a print gone quiet at a printer that is Offline) | Nineteen rows' worth: fourteen written as the design, five marked proposed and linked to their undecided item |
| The table of choices | Yes, twelve rows, each with reason and alternative | Nearly. Two proposed rules were missing from the list under the table (the waits between retries, a part the page cannot draw), and two rules written as the design have no source and were not shown as choices (the page takes the first group by itself when the stored group is refused; the reminder of how STL files are read after a "too large" refusal) | All four added to the list under the table, with a pointer to the proposed targets for speed and memory |
| What is undecided or unmeasured | Yes | Yes for the eleven gaps (each has what it is, what is known, options with cost and what a user sees, a recommendation). One smaller item, the limit on wrong pairing codes, was a one-line question | That item now carries printer delivery's proposal and a link to its reasoning. "Where to look first" names all eleven gaps and links the eleven smaller items |

## Orca's sentence under Details

Restored. The sources:

- The mockup's decision 32: "Exactly three messages have folded Details: the empty-layers
  and faulty-mesh slice failures (Orca Slicer's own sentence with the heights, and where
  to look on the part ...), and the failed print on the Send step".
- The mockup's decision 56: slicer settings are always in millimetres; "so is Orca
  Slicer's own sentence quoted in a slicing error's details".
- The decisions of Fri 2026-11-27, items 15 and 16, confirm the mockup's decisions where
  nothing else is said.
- The plan's standing requirement "Errors" says the underlying detail (Orca's own words)
  is "kept for the server log and never thrown away". It does not say that none of it may
  be shown.

**The difference, for the coordinator.** The slice service's guide says the underlying
evidence, Orca's own words among it, "goes to the log and is never shown as it is"
(its section "When things go wrong"), and
[the error report's contract](../../../contracts/error-report.md) says of the detail
"Never shown to a user as it is". The wizard's guide now states the mockup's design: the
slice service quotes Orca's sentence, marked as Orca's, in the part of the error report
that is for the user, on those two failures only, and the wizard never reads the detail
kept for the log. It is listed as an ask in the wizard's table "What the other components
do not provide yet". One of the two sides has to change: either the slice service's guide
and the contract gain a quotation for the user on these two failures, or the owner drops
decision 32's quotation.

## What this check changed in the guide

1. Orca's own sentence restored under Details on the two slice failures: in "Who writes
   the sentences of a failure", the units table, "When a slice fails" and its table, and
   as an ask on the slice service.
2. "Where to look first": the count of screens corrected to nineteen, the list of smaller
   proposed rules mentioned, and all eleven gaps named with a link to the smaller items.
3. "Everything else in the guide follows the mockup's accepted decisions" was not true of
   the proposed targets; the sentence now says so and links the table.
4. "The relay" was used three times and never defined; defined in the terms, in the
   plan's words.
5. The table of screens: three states added to existing rows and five proposed screens
   added as rows.
6. The list under the table of choices: two proposed rules and two unstated choices
   added.
7. Repetition: the reason for dropping parts on return was told in "Coming back to
   running work" and again in its undecided item; the body keeps two sentences and a
   link.
8. Repetition: the deploy that shows the retry message for minutes was told in full in
   "When the server is slow" and again in "When things go wrong"; the second is one
   sentence and a link.
9. Repetition: the reason for Chrome was given in "Browsers" and again in the layer
   preview's proposal table; the table links to the first.
10. Repetition: where focus goes in advanced mode was told under "Advanced mode" and
    again under "Accessibility"; the second links to the first.
11. Repetition: the fingerprint was explained as a hash twice within thirty lines; once
    now.
12. One paragraph (the last-print note) had a line left unwrapped by an insertion;
    rewrapped.
13. "The limit on wrong pairing codes" given its backing and a link to printer delivery's
    proposal.

Checked and found sound: every relative link and anchor resolves (checked by script, no
failure before or after the edits); the one `mermaid` fence is a plain `flowchart TB`
with quoted labels; no route, setting name, error code, make target or file name from
the code appears (the four colour codes in the table of line types stay, as the first
review asked); "the owner decided" and the history of the mockup are gone from the body;
every figure with no source is marked "proposed".

## Found and not changed

For the owner:

- The twelve choices in the guide's table, and sign-out, are the owner's to confirm.
  Choice 12 (a Send step from phase 2) departs from the plan; if it stands, the plan's
  phases 2 and 5 change.
- The proposal that the layer preview's look may be simplified while the view moves
  departs from the mockup's decision 33 and is marked as needing the owner's yes.
- The mockup's decision 32 has a slice that ran out of time suggest "a profile with
  thicker layers". The guide follows the slice service's sentence, which offers fewer
  instances or a second plate. Nothing in the guide says the mockup's remedy was dropped.

For the coordinator:

- Orca's sentence, as set out above: the slice service's guide and the error report's
  contract against the mockup's decisions 32 and 56.
- Choice 1 (a run-out sign-in waits for a button) disagrees with three texts marked
  proposed: the contract between the wizard and the front server, the front server's
  guide ("the page starts the sign-in itself") and the wizard's details file. Choice 2
  (Sign in again inside the group details) disagrees in the letter with the front
  server's guide ("beside the current group's name").
- The wizard's details file is out of line with the guide, as listed under "Not fixed"
  above.
- The contract between the wizard and the front server lacks four things the guide asks
  for: the moment a sliced file expires, a report of a failure in the browser, signing
  out, and the list of advanced mode's settings.
- The slice service's guide has a failure the wizard's table of slice failures has no row
  for: "A profile or setting is not accepted", whose remedy is on the Settings step. As
  written the wizard would treat it as an unknown failure and offer Slice again and Back
  to Layout. Adding a row means choosing its button, so it was left.
- The guide's example for too many wrong pairing codes says "Wait a few minutes";
  printer delivery proposes ten wrong codes a minute, so the true wait would be under a
  minute. The sentence is printer delivery's to write.
- When the stored group is refused, the guide has the page take the first of the user's
  groups; the front server's guide tells the user to choose another group. Both can be
  true, but the two guides should say the same thing.
