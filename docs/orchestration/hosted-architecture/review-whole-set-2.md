# Second review of the whole set, after the fixes

Written Thu 2026-11-26, 22:39 Pacific time, against commit `01cb5c1`. Method: each
finding of [the first review](review-whole-set.md) checked against the text as it now
stands; then the plan, the architecture and the four guides read front to back, with the
contracts and the details files, and [the decision map](decision-map.md) as the authority
on what was decided and on what awaits the owner.

**Verdict.** The set is ready to merge: nothing serious remains, no document states the
side that is not recommended, and the plan and the guides now agree on what each phase
builds. Nine small findings are left, each a change of one line or one sentence; the
first four are worth making before the owner's final read, and none blocks the merge.

Of the 26 first-round findings, 25 are fixed and one (the names, finding 15) is fixed
except for one occurrence. No fix put a wrong statement into the set; one edit left a
sentence dangling (new finding 4).

## (a) The 26 first-round findings

Numbered in the order of the first review.

**1. The set disagrees with itself**

1. The front door and the architecture never say fifteen items await the owner: **fixed**
   (`docs/plans/penguin-slicer-plan.md:268-271`, `docs/architecture.md:21-26`; the
   architecture carries it in its opening, not under "To confirm", which is the better
   place).
2. Items 1.1 and 1.4, how long a sliced file lives: **fixed** for item 1.1
   (`docs/architecture.md:213-215`, `front/README.md:34`, `front/README-details.md:500-502`,
   `delivery/README.md:150-151`, `delivery/README-details.md:353-355`). Item 1.4 is marked
   only in the contract; see new finding 7.
3. Item 1.8 stated with the side that is not recommended: **fixed**
   (`front/README-details.md:395-398`, `slice/README-details.md:163-166`).
4. Item 1.9 stated as settled: **fixed** (`docs/architecture.md:430-434`,
   `front/README.md:163-164`, `front/README-details.md:664-667`).
5. What the configuration holds: **fixed** (`docs/plans/penguin-slicer-plan.md:59`,
   `docs/architecture.md:243-246`, `front/README.md:139-141`,
   `front/README-details.md:530-532`). The three changes are now named alike everywhere
   (no colour, the printer's Orca profile, a profile's name and purpose).
6. Which phase designs the configuration's edit screens: **fixed**
   (`contracts/configuration.md:37-39`, `wizard/README-details.md:350-352`).
7. Which phase builds the wizard's retrying: **fixed**; the plan's phase 2 and phase 3
   lists (`docs/plans/penguin-slicer-plan.md:327-331`, `:404-405`) match
   `wizard/README.md:167-168` word for word.
8. Which phase builds the cookie, the check of the current group and the log: **fixed**;
   the plan (`:332-339`, `:398-403`) matches `front/README.md:181-182`. The front
   server's guide no longer says the log's phase is to be settled.
9. A thing to confirm that is already answered: **fixed** (the bullet is gone from the
   architecture; `delivery/README-details.md:516-522`).
10. A day or 12 hours: **fixed** (`delivery/README-details.md:491-497`, test at `:501-502`).
11. The daemon's short random wait: **fixed** (`wizard/README-details.md:785`,
    `delivery/README-details.md:341-342`).

**2. One name per thing**

12. "Configuration" meaning two things: **fixed** (`delivery/README-details.md:19-21`).
13. The details file called "printer delivery's guide": **fixed**
    (`docs/plans/penguin-slicer-plan.md:467`, `:475`).
14. "Item 2.4" and "need 2.4": **fixed**; no "need 2.x" is left.
15. "The Onshape app" and "the owner": **not fully fixed**. One occurrence is left, see
    new finding 8.
16. "FRC shops" on the front page: **fixed** (`README.md:3-4`).

**3. Each thing explained once**

17. Two lists written out in the contract: **fixed**
    (`contracts/wizard-front-server.md:82-96`).
18. Onshape's allowance explained four times: **fixed**
    (`docs/plans/penguin-slicer-plan.md:423-426`, `docs/architecture.md:256-259`, `:571-573`).
19. The architecture's "Sign-in" and "Printers" past its own rule: **fixed**
    (`docs/architecture.md:248-280`; each is three sentences and its links).

**4. Reading order and links**

20. `contracts/README.md` cited for a rule it did not hold: **fixed**
    (`contracts/README.md:16-18`).
21. `#tests` landing on the wrong section: **fixed** (`front/README-details.md:757`,
    `front/README.md:175`).
22. The contract using the architecture's terms: **fixed**
    (`contracts/wizard-front-server.md:18`, `docs/plans/penguin-slicer-plan.md:40`).
23. The wizard's guide using two things its reader has not been given: **fixed**
    (`wizard/README.md:64`, `:114-116`).
24. The wizard's details citing printer delivery's guide for rules only its details hold:
    **fixed** (`wizard/README-details.md:376`, `:382`).

**5. Built against to be built**

25. The Cleanup requirement stating phase 2's behaviour as present: **fixed**
    (`docs/plans/penguin-slicer-plan.md:211-214`).
26. "Brought up to the standing requirements": **fixed**
    (`docs/plans/penguin-slicer-plan.md:250-256`).

The links the fixes added were checked by hand against their targets' headings: every
one resolves, and each target holds what its sentence promises.

## (b) New findings, most serious first

### 1. The decision map and the set disagree on which items await the owner

`docs/orchestration/hosted-architecture/decision-map.md:617` — "What a delivery job's
record carries; a returning page finding its delivery job and last print; a profile's own
name and purpose; the plate's size on the Layout step | Added to the living documents as
the mockup requires | Not yet confirmed" — against `wizard/README.md:154` — "2.6 | A
'plate too large' error? | Yes, invented | No volume cap | Left out" — and
`wizard/README.md:156-159` — "The other needs from the server (who sent a print, the
user's own delivery job) … are listed in the details".

The decision map's table holds sixteen items: it counts 2.2 and 2.3 and leaves out 2.6.
The set says fifteen in four places (`docs/plans/penguin-slicer-plan.md:268-269`,
`docs/architecture.md:21-22`, `wizard/README.md:6`, `wizard/README-details.md:440-447`),
counts 2.6, and treats 2.2 and 2.3 as proposals with no status
(`wizard/README-details.md:710-711`, `:722-723`: "*proposed*; not decided by the owner").
An owner who checks the fifteen against the authority finds a different list.

The sixteen files agree with each other, so the smaller change is in the decision map.
Replace the row at `decision-map.md:617` with these two rows:

> | A profile's own name and purpose; the plate's size on the Layout step | Added to the living documents as the mockup requires | Not yet confirmed |
> | The "plate too large" error | The steps leave it out | Not yet confirmed |

and add after the table:

> What a delivery job's record carries, and how a returning page finds its delivery job
> and last print (2.2 and 2.3 of the comparison), are not among the fifteen: the living
> documents carry them as proposals, settled in phase 5's design spec.

### 2. The plan says "already settled" of things that await the owner

`docs/plans/penguin-slicer-plan.md:350-352` — "**Already settled by the architecture:**
how parts reach the slice service, where the sliced file is kept, how a page that has
lost its state comes back to its work" — against `docs/architecture.md:230-233` — "That a
refresh keeps the work and that it stays in one browser are not yet confirmed by the
owner" — and `:213-215` — "This may change: an item awaits the owner's choice".

`docs/plans/penguin-slicer-plan.md:481` — "**Already settled by the architecture:**
pairing with a code used once" — against `docs/architecture.md:268-269` — "(not yet
confirmed by the owner: item 1.6)".

The plan states as settled what the document it cites marks as open. Replacement, at
`:350`:

> - **Settled by [the architecture](../architecture.md#where-each-piece-of-state-lives), apart from the items awaiting the owner ([Where things stand](#where-things-stand)):** how parts

and at `:481`:

> - **Settled by the architecture, apart from the items awaiting the owner ([Where things stand](#where-things-stand)):** pairing with a code used once and how often a

### 3. Phase 3 of the plan builds a rule for daemons that no guide places before phase 5

`docs/plans/penguin-slicer-plan.md:410-413` — "The rules of Old and new versions
together that phase 2 does not build: a format number on each record in the state bucket,
and an installed daemon kept working" — against `front/README.md:182` — "the other rules
for old and new versions together (a format number on each record)" — and
`delivery/README.md:128` — "Phases 2 to 4 need nothing of printer delivery".

No daemon talks to the hosted front server before phase 5. Replacement for
`:410-413`:

> - The rule of
>   [Old and new versions together](../architecture.md#old-and-new-versions-together)
>   that phase 2 does not build: a format number on each record in the state bucket.
>   (Its rule for an installed daemon applies from phase 5.)

### 4. A sentence left dangling in the contract

`contracts/wizard-front-server.md:48-50` — "This may change: an item awaits the owner's
choice (item 1.9, how long the page retries before it shows an error)." It stands after
"a send repeated with the same sliced file by the same user while its delivery job is
live answers with that delivery job", so "This" reads as the repeated send. It belongs
to "the user sees a pause, not an error" at `:36-37`.

Replacement: delete the sentence at `:48-50` and put it at `:37`, straight after
"([the wizard](../wizard/README-details.md#retrying-every-request)).":

> This may change: an item awaits the owner's choice
> ([item 1.9](../wizard/README-details.md#19-retrying-then-an-error-after-20-seconds),
> how long the page retries before it shows an error).

### 5. Pairing in printer delivery's guide carries no mark (the known gap)

`delivery/README.md:134` — "a user types the code" — against
`docs/architecture.md:267-269` — "any signed-in user of the group types the pairing code
… (not yet confirmed by the owner: item 1.6)" — and
`contracts/wizard-front-server.md:257-259`, which marks it too. See (c) for the judgment
and the line.

### 6. Item 2.4 leaves no trace in printer delivery's two files

`wizard/README.md:135-137` — "Recommended: the relay notes the time in the paired-printer
record … when a daemon goes offline" — is a change to the relay and to the record that
`delivery/README-details.md:89-93` defines, and neither `delivery/README.md:163-166`
("What the wizard's mockup needs") nor `delivery/README-details.md:467-497` ("From the
wizard's mockup") mentions it. The architecture and the front server's guide do not
either; only the wizard's files and `contracts/wizard-front-server.md:235-238` do. A
builder of phase 5 who reads printer delivery's files does not learn of it. The details
file has no line limit. Add at `delivery/README-details.md:497`, after "that user's last
print.":

> How long an offline daemon has been silent is not kept across a restart of the front
> server. This may change: an item awaits the owner's choice
> ([item 2.4 of the wizard's guide](../wizard/README-details.md#24-not-heard-from-for-7-minutes)).

### 7. Item 1.4 is marked in the contract only

`docs/architecture.md:213` — "A sliced file is kept for two hours after its slice ended"
— and `front/README-details.md:500-501`, both marked for item 1.1 alone, against
`contracts/wizard-front-server.md:202-203` — "The two hours start when the slice ended
(not yet confirmed by the owner: item 1.4)". The rule is applied in one of three places.
The recommendation is the design's, so no reader is misled; for evenness, at
`docs/architecture.md:215` and `front/README-details.md:502`, add after the link to
item 1.1:

> That the two hours start when the slice ended is not yet confirmed by the owner
> ([item 1.4](../wizard/README-details.md#14-when-the-two-hours-start)).

(In the front server's details the link text is "item 1.4 of the wizard's guide".)

### 8. Two names from the first round's finding 15 are left

`front/README-details.md:49-50` — "the redirect address of the Onshape OAuth app" (the
term is split across two lines, which is why a search for it finds nothing). Replacement:
"the redirect address of the Onshape app".

`slice/README-details.md:334` (inside "To be built") — "The figure is the project owner's
to change". Replacement: "The figure is the owner's to change".

### 9. "A shop's printer" in the opening of printer delivery's details

`delivery/README-details.md:7-8` — "gets it printed on a shop's Bambu Lab printer" —
against `README.md:3-4` and `delivery/README.md:3-4`, which the first round brought to
"a Bambu Lab printer". Replacement: "gets it printed on a Bambu Lab printer".

### Checked and clean

- Phase assignments: the plan's lists for phases 2, 3 and 5 match the tables of
  `wizard/README.md:165-170`, `front/README.md:179-184` and the lists of
  `slice/README.md:131-166`, apart from new finding 3.
- No item awaiting the owner is stated with the side that is not recommended.
- The three items needing a choice (1.1, 1.9, 2.4) are stated as the approved design with
  "This may change" wherever a document outside the wizard's guide states them, apart
  from new finding 6. The wizard's guide, which is the items' home, words them its own
  way ("item 1.2 below", "needs the owner's choice (item 1.9 below)"), which reads
  correctly there.
- The figures (two hours, 55 s, 10 s, 40 s, 2 minutes, thirty days, one week, 25 parts,
  7.5 MB, 6,000 MB, 240 s) still agree.

## (c) The known gap: pairing in printer delivery's guide

It should change, and it can without adding a line. The text matches the approved
design, so nobody is misled; but the architecture and the contract mark the same
statement as not yet confirmed, and the owner reading the architecture and then this
guide meets the rule applied in one and not the other. `delivery/README.md:151` already
carries its mark on one long line, so the same form keeps the file at 200 lines.

Replace line 134:

> `  (a random id it keeps), and offers both every 30 s; a user types the code, the relay`

with:

> `  (a random id it keeps), and offers both every 30 s; a user of the group types the code (which user, and from where, is not yet confirmed by the owner: [1.6](../wizard/README-details.md#16-who-pairs-the-printer-and-where)), the relay`
