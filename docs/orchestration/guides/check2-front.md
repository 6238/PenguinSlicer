# Second check of the front server's guide

Checked Fri 2026-11-27, Pacific time: [front/README.md](../../../front/README.md), 1,491
lines as read and about 1,520 after this check's edits, against
[the first review](review-front.md), [the writer's brief](brief-writer.md) and
[the decisions of Fri 2026-11-27](decisions-2026-11-27.md).

## Verdict

The guide is ready for the owner: every finding of the first review that decides
something is now either stated as the design or written as an undecided item with what
is known, the choices, their cost and a recommendation. What remains for the owner is to
decide those items, of which the four under "Gaps in the design that need a decision"
that touch phase 3 (who may sign in, sign-ins and the allowance, users at once, the
cookie inside Onshape's panel) weigh most.

## The first review's findings

Heading 1, can the reader decide (17 findings): all fixed.

| Finding | Status |
|---|---|
| Anyone with an Onshape account can sign in | Fixed: stated under "Signing in" and "Security"; undecided item "Who may sign in" |
| Nothing limits sign-ins | Fixed: undecided item "Sign-ins and the allowance", and a row in the limits table |
| No figure for users at once, threads running out | Fixed: undecided item with three choices |
| A pairing code across a restart | Fixed: "three small exceptions", and a row in the restart table |
| The cookie inside Onshape's panel | Fixed: undecided item with three choices |
| The permissions the Onshape app asks for | Fixed: stated for phase 3, undecided item for phase 4 |
| No target for time | Fixed: one paragraph saying none is set and what would set one |
| No ceiling on a sliced file | Fixed: undecided item; the limits row says "no ceiling of its own" |
| Files in pieces or whole in memory | Fixed, as a marked proposal in two places |
| A deploy that fails; learning the service is down | Fixed: paragraph in "Restarts and deploys" and an undecided item |
| The state bucket or the slice service not answering | Fixed |
| A repeated submission | Fixed: undecided item "A plate configuration submitted twice" |
| What Cloudflare's proxy may keep | Fixed, as a marked proposal |
| Safari | Fixed: Chrome named as supported; the page shown to Safari is a marked proposal |
| Four pieces in no phase's list | Fixed: all four placed |
| Rate limits have a proposal elsewhere | Fixed in a way that created a new problem: the guide said printer delivery's guide proposes no figure for wrong pairing codes, and it proposes ten a minute for each user. Corrected in this check |
| Removal of a user's log lines; no second copy of the state bucket | Fixed: two accepted risks |

The extra question, length: fixed in the main. "Secrets", "Old and new versions together"
and "Running the relay" are cut to the front server's own part with a link; "What it
costs to run" is gone, with one item left under "About the host"; the relay's and the
wizard's rows left the limits table; each repeated fact is now told once and linked.
Not fixed: "The log" is still about 48 lines, and the limits table still has sixteen rows
of five columns. Both read well and neither was changed.

Heading 2, written for a person (9 findings): 8 fixed. The ninth, the exchange table
naming things before they are explained, was half fixed ("summaries" still appeared
undefined in the paragraph before it); corrected in this check.

Heading 3, true (9 findings): all fixed. The $40 figure left with its section.

Heading 4, one name per thing (9 findings): 8 fixed. Not fixed: "plate" and "slice" still
stood for "plate configuration" and "slice job" in about ten places, among them the
heading "A plate"; corrected in this check where the thing meant is what is sent,
submitted, followed or owned. "A slice" remains where it means the act of slicing.

Unfixed after the fixer's round: 3 (one new error, two half-fixed), all corrected here.

## What this check changed

- First diagram: the node id for Onshape changed from `on` to `os`, since an id beginning
  with "o" can be read by Mermaid as part of an arrow.
- Second diagram: the slice service's answer about a part now returns through the front
  server and not straight to the page, and the sliced file's fetch now runs page, front
  server, state bucket and back; the diagram had contradicted the text beside it.
- "plate" to "plate configuration" in four places, and the heading "A plate" to "A plate
  configuration" (no link pointed at it).
- "slice" to "slice job" in six places ("Whose it is", the development identity, the
  restart table, two lines of "The log").
- "Summaries" given a gloss at first use, in "What it holds".
- "The development identity" given a gloss at first use, one section before its own.
- Limits table: the two empty "What it protects" cells filled.
- "Choices the owner has not yet confirmed": "about fifty less up to three" reworded, and
  the cost of the other choice added to that bullet.
- "Rate limits and the sweep's interval": the proposal for wrong pairing codes corrected
  to ten a minute for each user, and the link pointed at the section that holds it.
- "Signing out": a recommendation added, and the cost of the next sign-in.
- A new last item, "Smaller points this guide proposes or leaves to a phase's design",
  gathering the four inline proposals and one deferred point so that the owner meets them
  as things to confirm.

All 67 relative links and anchors resolve, checked by script after the edits. No
code-level name, no "the owner decided" and no unmarked figure was found; every figure
checked against the architecture, the details file and printer delivery's guide matches.

## Found and not changed

- The two `mermaid` diagrams were read closely and should parse, but were not rendered in
  this check. The coordinator should render the page once.
- "Two requests renewing the tokens at once" says the fault must be prevented and that
  how is not designed, with no choices and no recommendation. It needs a design, which is
  phase 4's; the coordinator may want that said in the item.
- "The log" (about 48 lines) and the limits table (sixteen rows, five columns) are longer
  than the first review asked for. A matter of taste for the coordinator.
- The new bullet's cost, "a second set of threads to size and to watch", is this check's
  wording and has no source; the owner may strike it.
- The recommendations in the undecided items carry proposed figures (three "sign in
  again" a day, fifty sign-ins a day and ten from one address, four streams for each
  user, a status request every ten seconds, a 100 MB ceiling). Each is marked proposed;
  all are the owner's to accept or change.
- The details file does not yet hold the guide's new proposals (answers marked as not to
  be kept, files in pieces, the page for Safari). The coordinator should bring the two
  files into agreement once the owner has answered.
