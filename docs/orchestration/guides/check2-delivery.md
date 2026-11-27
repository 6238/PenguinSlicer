# Second check of printer delivery's guide

The guide ([delivery/README.md](../../../delivery/README.md), 1,503 lines after this check)
is ready for the owner: every finding of [the first review](review-delivery.md) is fixed,
and what the fixes left behind was wording, which is now corrected in the guide. Its
twelve undecided items and eight unmeasured ones each carry their backing and a
recommendation or proposal, except daemon telemetry and the messages of the pairing
exchange, which the guide hands whole to phase 5's design.

Checked: the guide read from first line to last; every relative link (the files exist) and
every anchor (each matches a heading of the guide or of
[the architecture](../../architecture.md)); the two `mermaid` fences, read and not rendered;
the figures of the new section on setting up, against the daemon's code (five seconds of
listening, twenty seconds for the first status document, the idle line every ten minutes,
the version sent with every request, the model learned when pairing).

## Status of the first review's findings

| Finding | Status |
|---|---|
| 1.1 What the administrator does | Fixed: a section "What the administrator does, once", with the daemon's screen, and two new items for the session at the H2S |
| 1.2 The silent-time rule | Fixed: a rule in four parts and an undecided item. The fix stated the clearing (part 2) as the design although no source has it; now marked as this guide's proposal |
| 1.3 Unpairing and pairing again | Fixed: two undecided items, each with options and a recommendation |
| 1.4 The caller's duty over sliced files | Fixed |
| 1.5 Printed files left on the printer | Fixed |
| 1.6 Deadlines across a restart | Fixed: proposed in the record's list, undecided item with a recommendation |
| 1.7 A page that goes away | Fixed |
| 1.8 Three missing undecided items | Fixed: progress streams, daemon versions, which printers |
| 1.9 "How it is checked" | Fixed: a sentence above each of the two tables |
| 1.10 The fetch's authority | Fixed: the proposal is stated |
| The five passages to shorten | Fixed, all five |
| Section 2: one code-level name, eight terms, six sentences, two tables | Fixed, all |
| 3.1 to 3.9 | Fixed, all |
| Section 4: names and history | Fixed, all. "The computer beside the printer" stays once, at line 25, before the term is defined, as the review allowed |

No finding remains unfixed. One fix created a new problem (1.2, above), now corrected.

## The two diagrams

Neither would fail to parse. The `flowchart TB` has six short nodes, one quoted subgraph
title, quoted edge labels and a cylinder written `[("state bucket")]`. The
`sequenceDiagram` has four participants with aliases and twelve messages; no message holds
a semicolon, HTML or a colon beyond the one that starts it. Neither has an init directive.
They were not rendered here, so the width check (no horizontal scroll) is still to do.

## What I changed in the guide

- Opening: the parenthesis about which printers are supported, which read as a broken
  sentence, is now a sentence of its own.
- Pairing, step 3: "the relay's secret key" was used 700 lines before its explanation; a
  gloss and a link to Security added.
- "A daemon that was switched off": a line left overlong by the first fix re-wrapped.
- "How a start is decided": "All of it is built" contradicted the phase 5 sentence about
  the start gate's answer two paragraphs on; now says so.
- "As built: everything in memory": "the job" is now "that delivery job".
- The delivery job's record: "serve the wizard's guide" is now "serve the wizard, whose
  guide requires them".
- The paired-printer record: "which of the relay's secret keys" now says there are two and
  links to where that is explained.
- The silent-time rule: says which parts are the design and that part 2 is this guide's
  proposal, and that whether to clear is itself undecided (the undecided item already
  said so; the body did not).
- Rate limits: the link for "not decided" now goes to the item, not to the top of the
  section.
- Daemon telemetry: a sentence with a dangling "where" split in two; its link now goes to
  the item.
- The session at the H2S: "the two limits above" (500 lines above) is now a link.
- "Which printers are supported": "The guide" is now "This guide".
- "Whether Cloudflare challenges a daemon", "Windows" and "Capacity" had no statement of
  how each is settled; one sentence added to each, the first marked as a recommendation.

## Found and not changed

- **For the coordinator: render the two diagrams** and check their width. Reading the
  source finds no fault, which is not the same as a rendered `svg`.
- **For the coordinator: the architecture's term for one field differs.** The architecture
  calls it "the time of the daemon's last sync before it last went offline" and keeps it
  until the next outage; the guide proposes clearing it when the daemon returns. If the
  owner accepts the clearing, the architecture's two rows need the same words.
- **For the owner: daemon telemetry** is listed as not designed, with what is fixed about
  it and what is not, and no options. It cannot be decided from the page; the guide says
  it gets its own design in phase 5. The same holds for "The messages of the pairing
  exchange".
- **For the owner: what LAN-only mode and Developer Mode cost a group** is stated as
  unknown. The guide says how to settle it (Bambu's documentation, then the session at
  the H2S) and does not guess.
- **For the coordinator: the send refused because "the sliced file is gone"** says what
  the user is told in phase 5 only. As built the refusal is for a sliced file more than
  40 minutes old (stated under "The sliced file"); the as-built sentence the user reads
  is not in the guide.
- **For the coordinator: a user-facing phrase.** The recommendation for a record whose
  daemon never collects its token has the wizard say "the printer's computer has not
  finished pairing"; the term everywhere else is "the daemon's computer". The words a
  user reads are the wizard's guide's to fix.
