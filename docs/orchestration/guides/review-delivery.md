# Review of printer delivery's guide

The guide ([delivery/README.md](../../../delivery/README.md), 1,114 lines) is close but not
ready for the owner: its prose, its figures and its split between "as built" and "in phase 5"
hold up against the sources, and almost no code-level name slipped in. The single most
important thing to fix is that it never says what an administrator must do to the printer
and to the daemon's computer: the code requires the printer in LAN-only mode with Developer
Mode on, and the daemon needs Python installed and commands typed in a terminal, and both
are product decisions the reader cannot see. Second is a gap in the rule for "how long a
printer has been silent" (finding 1.2), which as written gives a wrong time after a restart.

Sources checked: the guide's own [details file](../../../delivery/README-details.md), [the
architecture](../../architecture.md), [the frozen design](../../specs/2026-11-25-hosted-architecture-design.md),
[the decisions file](decisions-2026-11-27.md), [the plan](../../plans/penguin-slicer-plan.md),
[the wizard's guide](../../../wizard/README.md), [the front server's guide](../../../front/README.md),
and the code under `delivery/` where a claim looked doubtful. The two `mermaid` diagrams
were read, not rendered.

## 1. Can the reader decide from it?

| Question | Answer | What is missing |
|---|---|---|
| Does it do the right things for a user? | Mostly yes | What the administrator does to install and pair (1.1); unpairing and pairing again (1.3); the printed file left on the printer (1.5) |
| Is the division of work with the other components sound? | Yes, with one omission | The caller's duty to refuse a sliced file the user may not use (1.4) |
| Are the approaches to the hard parts sound? | Yes for the start, the held wait and the records | The silent-time rule has a hole (1.2); the deadlines across a restart are not stated (1.6) |
| Are the limits and targets the right ones? | Yes, each has a figure and an origin | Two of the three tables have no "how it is checked" (1.9) |
| Is security adequate? | Yes, and the accepted risks are plain | Finding 1.4; the printer's mode (1.1) |
| Failure, cancel, restart and deploy? | Yes, the strongest part | Finding 1.6; a page that goes away (1.7) |
| What is built and what is not? | Yes | Nothing |
| What remains undecided? | Mostly | Findings 1.2, 1.3, 1.6, 1.8 belong in that section |

Findings, most serious first.

- **1.1** Lines 80 to 82 and 115 to 117 — "It is a plain program for Windows, macOS or Linux." and "The daemon finds the printer, asks for its access code" — the guide leaves out the whole requirement area of installing and setting up. The code's pair command tells the user "Check that it is in LAN-only mode with Developer Mode ON ... Developer Mode is required: Bambu firmware rejects print starts from third-party software in any other mode" (`delivery/daemon/penguin_delivery_daemon/__main__.py`, lines 199 to 202), and the details file's "Running the daemon" requires Python 3.11 or newer, an install from a terminal, and three typed commands (pair, run, status). A product manager must be able to object to each. Fix: add a section "What the administrator does, once" after "Two halves": (a) at the printer: LAN-only mode and Developer Mode on, the access code read from its screen, and what the printer loses in that mode (to be stated from Bambu's documentation, not assumed); (b) at the daemon's computer: install Python 3.11 or newer, install the daemon, run pair, then run and leave it running in a terminal window; the daemon finds the printer by listening on the local network and falls back to a typed address; (c) that all of this is built and none of it tried on Windows. Add "the printer's required mode" to "What only the session at the real printer can settle".
- **1.2** Lines 637 to 645 — "one write at that moment ... and no further write however long it stays off. The daemon's next sync puts the printer back online. One case is left: a daemon that was healthy when the front server restarted, and never syncs again, has no time written." — false whenever that daemon had been offline before: the record still holds the time of the earlier outage, since nothing says the return online clears it, so after a restart the wizard would say "Not heard from for 3 weeks" of a daemon heard a minute before the restart. Fix: state one of two rules and list the choice under "What is undecided or unmeasured" with its cost: either the daemon's first sync after an outage clears the time (a second write for each outage), or the relay ignores a recorded time unless it wrote it since it started and otherwise says "for at least". The decisions file (item 19) settles neither.
- **1.3** Lines 143 to 145 — "**Unpairing** removes the paired-printer record." — the guide does not say who may unpair, what happens to a delivery job in progress, or what pairing again does. The wizard's guide (lines 874 to 880) says any user of the group may unpair and that unpairing "is off while a print that PenguinSlicer is following is going on"; the delivery guide must say whether the relay itself refuses that or only the wizard hides it. Also unstated: a group that already has a paired-printer record and types a new code (replace, or refuse?); a daemon already paired whose pair command is run again; a record whose daemon never collected its token (the group shows a printer nobody hears, and the hash stays). Fix: add after line 145 "Any user of the group may unpair. The relay refuses to unpair while a delivery job of that group has not ended" (if that is the design; the wizard's guide implies it), and list the three pairing-again cases under "What is undecided or unmeasured", each with a proposal.
- **1.4** Lines 751 to 756 ("Who can reach it") — omits a security duty that the details file states in bold: "The caller's duty: `find_sliced_file` must return `None` for a token that the request's identity may not use ... The relay cannot know who owns a send token." Without it the reader cannot judge the division of work: it is the front server, not the relay, that keeps one user from sending another user's or another group's sliced file. Fix: add to "Who can reach it": "The relay cannot tell whose a sliced file is. Its caller must refuse a send that names a sliced file the signed-in user may not use; in phase 5 that check is the front server's, by user key."
- **1.5** Lines 668 to 673 — "It uploads the file to the printer under its own name with the delivery job's id added" — nothing says what becomes of that file after a print. The code removes a file from the printer only when the print was not started or the upload failed; neither the guide nor the details file says a printed file is ever removed, so files gather on the printer's storage, against the plan's standing requirement "Cleanup" ("nothing accumulates on disk"). Fix: add one sentence stating what is built ("A file that was printed stays on the printer; nothing removes it") and list under "What is undecided or unmeasured" whether the daemon should remove it when the print ends, and what a full printer does to an upload.
- **1.6** Lines 612 to 623 (the delivery job's record) — the record's list has no times, yet three deadlines run on a delivery job: 3 minutes to be collected, 15 minutes from collection to the start gate (which is also when an unanswered cancel takes effect), and 24 hours of staleness. The project deploys continuously, so the reader must know whether a restart of the front server restarts those clocks. Fix: add to the list "when it was sent and when it was collected, so that the 3-minute and 15-minute limits run on across a restart", or say they start again, and say which for the 24 hours; add the choice to the item "What of a delivery job is written to its record" at line 1081.
- **1.7** Section "When the daemon, the relay or the printer goes away" (lines 537 to 564) — no row for the user's page going away, which the plan's standing requirement "Cleanup" asks every component to state. Fix: add a sentence before the table: "A delivery job does not depend on any page: if the user closes the page, the delivery job and the print go on, and any user of the group sees it on the printer-status icon." (true of the code as built: the relay holds the delivery job whether or not a page follows it). Add also the plan's rule that a page connecting late gets the latest progress report at once, which the guide never states for delivery jobs (details file, "Already built, kept as they are").
- **1.8** "What is undecided or unmeasured" (lines 1042 to 1114) omits three items the sources list: (a) the architecture's "Progress streams through Cloudflare and Railway" (if either holds events back, the page asks for the latest progress report every second or two instead, which changes the status-request allowance discussed at line 1060); (b) how an installed daemon is brought to a new version and whether the relay can tell which version a daemon runs, a requirement area the guide leaves out entirely although line 559 says a daemon "may be much older than the relay"; (c) which printers are supported: line 3 says "a Bambu Lab printer" while everything known is the H2S. Fix: add the three items, (c) as one sentence near line 3: "Only the H2S is known to it today."
- **1.9** Lines 720 to 747 — the tables "A delivery job" and "What is kept, and how big" have no column for how each figure is checked, which the first table has. Fix: add the column, or one sentence above each: "Each built figure here has a test on a fake clock that reaches it; none is checked against the real printer."
- **1.10** Line 1073 to 1079 — "does not say whether the fetch should require the daemon's token. Requiring it is stricter ... keeping the unguessable address is simpler" — an undecided item with two options and no proposal. Fix: add "The proposal is to keep the unguessable address and the count for each network address" (the details file's proposal, "The sliced file").

### Is every part earning its place at 1,114 lines?

Yes for most of it. The guide does not re-explain what the architecture owns except where
noted below, since the architecture now gives printers one paragraph and names this guide as
the owner of pairing, the syncs and the limits.

Shorten or cut:

- **Lines 786 to 800, "Replacing the relay's secret key".** The architecture owns this under "Replacing a secret" (the table, the week, the log line, the command, the emergency). Keep three sentences (two keys, a daemon off for the whole week pairs again, an emergency pairs every printer again), the link, and the as-built paragraph at 802 to 804. About 10 lines go.
- **Lines 675 to 697, "What the wizard needs that the relay does not give yet".** Its four items repeat the delivery job's record at 612 to 623 and quote screen text the wizard's guide owns. Fold "as built" for each of the four into the record's list and delete the section. About 18 lines go.
- **Lines 906 to 920, "Random sequences" and "No test can hang".** The counts (260 sequences, 5 seconds, nine faults, two the random sequences no longer reach, 30 seconds, a million steps) are a builder's. Keep the invariants checked (lines 909 to 913) and one sentence that no test can hang. About 8 lines go.
- **Lines 868 to 874, the phase 5 log.** The architecture's "What is written" owns it; keep the three figures on the line that ends a delivery job and the link.
- **Lines 478 to 494, the start note and the relay's memory of the last start.** Sound, and an engineering manager wants the approach, but "Each write is made whole and forced to the disk before it replaces the old note" and the daemon "restarted with no note" are builder's depth; two sentences each would do.

Too thin: installing and setting up (1.1); unpairing and pairing again (1.3); what the user of the daemon's computer sees on its screen while it runs (one paragraph: idle line, waiting lines, what an error looks like); daemon versions (1.8 b).

## 2. Written for a person

Code-level names: one.

- Line 947 — "the together run speeds up a real clock and polls" — "together" is the name of a make target and a folder. Fix: "that run speeds up a real clock and polls".

Terms used before they are defined (the guide promises at lines 8 to 11 to say each term again where first used):

- Line 62 (diagram) and line 124 — "state bucket" — in the diagram 60 lines before its definition. Fix: add after the diagram "The state bucket is the object store in which the relay's records outlast a restart of the front server (phase 5)."
- Lines 63 and 181 — "sync", "The daemon's first sync" — the architecture's term, defined only at line 213. Fix at 181: "The daemon's first sync (its regular request to the relay, described below)".
- Lines 201 and 547 — "The start note" — a table row at 201, defined in bold at 479; line 185 calls the same thing "a note of the print it started". Fix: at 185 write "keeps a **start note** on its own disk, a record of the print it is about to start or has started".
- Line 269 — "progress streams" — defined at 556. Fix: move the definition "(the connections on which pages follow a delivery job)" to 269.
- Lines 637 and 680 — "The printer details", "the busy-printer card" — never defined. Fix: "the printer details (the small box that opens from the printer-status icon)" and "the card the Send step shows when the printer is busy"; the wizard's guide calls it "the busy card".
- Line 753 — "a current group that the cookie lists" — "current group" never defined. Fix: "(the one group, of those the user belongs to, whose printer the user is using now)".
- Line 874 — "the log bucket" — never defined. Fix: "the log bucket (the object store that keeps log lines for ninety days)".
- Line 344 — "a start command sent for an earlier delivery job has not yet shown what became of it" — relies on the hold, explained at 461. Fix: add "(see [How a start is decided](#how-a-start-is-decided-so-that-a-print-is-never-started-twice))".

Sentences to be read twice:

- Lines 158 to 161 — "the relay grants the trade only for a code the caller has presented since the relay started, and only while no daemon with that code has been heard for two minutes, so a second daemon with a copied settings file is refused while the first is alive" — three conditions and a consequence. Fix: split: "The relay grants the trade on two conditions. The caller must have presented that code since the relay started. And no daemon with that code may have been heard in the last two minutes, which refuses a second daemon with a copied settings file while the first is alive."
- Lines 420 to 421 — "or on the relay's permission to start never having been given" — Fix: "or because the relay never gave permission to start before its deadline".
- Line 438 — "It is given to one running daemon" — Fix: "The yes goes to one running copy of the daemon and to no other".
- Lines 583 to 585 — "The daemon's hold on the printer is not lifted by it. A daemon still waiting ... learns within 30 seconds that the relay has let go and becomes free for the next delivery job, which then waits for the earlier start to settle like any other." — says the daemon is free and the printer is held in one breath. Fix: "It does not lift the daemon's hold on the printer. Within 30 seconds the daemon learns that the relay has let go and will take the next delivery job, but that delivery job still waits, cancellable, until the evidence settles the earlier start."
- Lines 663 to 665 — "either a file on disk or a stream, which the relay copies once into a folder of its own" — unclear which is copied; see 3.3.
- Line 1003 — "the rule for whose end an end is" — Fix: "the rule that an end counts only if it is the end of this print".

Tables that stand where prose was needed:

- Lines 340 to 350, the stages — a nine-row table before any text explains the rows, with cells of forty words that carry limits (3 minutes, 10 minutes, three attempts). Fix: two sentences before it naming the three groups (waiting, taking the file, the print), and move the limits to the text or leave them to "How well it must do it", which repeats them.
- Lines 543 to 549, what went away — the last two rows are paragraphs inside cells. Fix: keep the first three rows; write "The relay, as built" and "The front server, in phase 5" as two short paragraphs below the table.

## 3. True

Checked against the details file outside "To be built", the architecture, the frozen design,
the decisions file and the code. Every figure I compared agrees with its source except as
listed: the pairing figures, the four rhythms, the two limits from silence, the deadlines of
3, 10, 15 minutes and 24 hours, the picture's 15 and 10 seconds, the hold's 1, 2 and 5
minutes, the retry waits, the size limits, the rate limits as built (confirmed in
`delivery/relay/penguin_delivery_relay/routes.py`), the test counts, and the sliced file's
sizes.

The three figures of the writer's own making:

- **3.1** Line 844 — "(room for thirty unpaired daemons offering at once)" — stated as fact, in the body, unmarked. It is the writer's arithmetic (sixty offers a minute, one offer for each daemon every thirty seconds) and appears in no source. Fix: "(which, at one offer every thirty seconds, is thirty unpaired daemons offering at once: this guide's arithmetic, not a figure of the design)", or remove it.
- **3.2** Line 1086 — "at about five writes for each delivery job" — marked: it sits inside the sentence "... is the proposal", under "What is undecided or unmeasured". It is the count of the five changes listed just before it; a delivery job that is never cancelled makes four. Fix: "at four or five writes for each delivery job (this guide's count of the changes just listed)".
- **3.3a** Lines 1061 to 1064 — "even a generous limit such as ten a minute for each user leaves guessing hopeless" — marked as an illustration ("such as"), in a paragraph that begins "For wrong pairing codes nothing is proposed". The arithmetic holds (150 guesses in a code's fifteen minutes against forty random bits). But the item then leaves the reader a decision with no proposal, and the wizard's guide already promises "Too many wrong codes. Wait a few minutes, then try again." Fix: make it a proposal, marked as one: "The proposal, this guide's, is ten a minute for each user".

The two diagrams:

- Lines 53 to 65 (`flowchart TB`) and lines 295 to 313 (`sequenceDiagram`): no semicolon inside any message, no HTML in a label, no init directive, all labels quoted where they hold spaces, the cylinder written as `[("state bucket")]`, the subgraph titled in quotes. I see nothing that would fail to parse. `participant U as User's page` holds an apostrophe, which Mermaid 11 accepts in an alias. Neither was rendered; the rendering check for width still has to be done.

Other differences from the sources:

- **3.3** Lines 598 to 599 and 663 to 665 — "a copy of each sliced file being delivered, on its own disk" and "either a file on disk or a stream, which the relay copies once" — as built only a stream is copied; a file on disk stays the caller's, which must keep it for up to eighteen minutes (details file, "The interface the relay offers its caller"). Fix at 663: "As built the caller hands the relay either a file on disk, which the caller keeps until the delivery job no longer needs it, or a stream, which the relay copies once into a folder of its own".
- **3.4** Lines 94 to 95 — "with three small libraries and nothing of the server's" — the daemon names three libraries, and the printer library brings two more that are pinned with it, one of them an image library (details file, "Upstream": `paho-mqtt`, Pillow), and all of it needs Python 3.11. Fix: "with Python and a handful of libraries (three of its own choosing and two the printer library needs)".
- **3.5** Line 81 — "It is a plain program for Windows, macOS or Linux." — unmarked, though it has never run on Windows (said only at line 992 and 1031). Fix: add "It has never yet been run on Windows, the likely system."
- **3.6** Lines 139 to 141 — "in the state bucket only as a hash for the seconds between steps 2 and 3" — the hash stays until the daemon's next offer, up to half a minute, and for as long as the daemon stays away after the code was typed (architecture: "until the daemon has its token"). Fix: "only as a hash, from the moment the code is typed until the daemon collects its token, normally under half a minute".
- **3.7** Lines 631 to 635 — "the time the daemon was last heard" — the architecture's and the details file's term for this field is "the time the daemon last went offline"; the decisions file (item 19, proposed) says the time noted is that of the daemon's last sync. The guide follows the decisions file, which is right, but "last heard" in a list of the record's fields reads as a field kept current. Fix: "the time of the daemon's last sync, written once when the daemon goes offline".
- **3.8** Lines 352 to 353 — "The Send step shows these on its track (Sending, Starting, Heating, Printing, Done)" — true of the wizard's guide (line 756), but nine stages are mapped onto five with no rule, and three of them (waiting for the printer, waiting for an earlier print, start not shown yet) have no place on that track. Fix: add "Which stage shows under which word, and how the three waits are shown, is the wizard's guide's to say", or give the mapping.
- **3.9** Omitted and needed: the caller's duty over sliced files (1.4); the printer's required mode (1.1); the page that goes away and the late-connecting page (1.7); the architecture's fallback for progress streams (1.8 a).

Not findings: the guide's phase 5 text differs from the details file's "To be built" in
places (the JSON log lines of the daemon, the time noted for an offline daemon); the
decisions file wins and that section is being rewritten.

## 4. One name per thing, and the design as it is to be

- Lines 35, 349, 395, 419, 459 — "the printer's own reports", "What the printer's reports mean", "the printer's reports decide" — these are status documents, the plan's term, which the guide defines at line 397 and then uses beside "reports"; "report" is also the progress report and the error report. Fix: "status documents" throughout; retitle the section "What the printer's status documents mean".
- Lines 531, 703, 958, 968, 1051 — "the session at the real printer", "the session at the H2S", "the session" — the plan's name is "the session at the H2S". Fix: use it everywhere, and rename the heading at 958 and the two links to it.
- Lines 833 to 834 — "**The development relay signs everyone in.** The stand-in caller used to try the chain on one machine" — one thing under two names, and line 76 calls it "stand-ins". Fix: "**The stand-in caller signs everyone in.**"
- Lines 23, 85 to 86, 859 — "the computer beside the printer" for "the daemon's computer", the plan's term, defined at line 80. Fix: use "the daemon's computer" after line 80; line 23 may keep the plain words since the term is not yet defined.
- Lines 436 and after — "the start gate" and "the gate" alternate (lines 451, 454, 492, 549, 568). Acceptable as a short form once line 436 says so. Fix: add "(below, the gate)" at line 436.
- Lines 677 and 695 — "The wizard's mockup shows four things", "The mockup shows the last print for 12 hours" — the design as it is to be lives in the wizard's guide; the mockup is thrown away once that guide is complete (the plan, phase 1), and the decisions file (items 15 to 17) makes the wizard's guide the statement of the design. Fix: "The wizard's guide requires four things" and "The wizard shows the last print for 12 hours", each linked to [the wizard's guide](../../../wizard/README.md).
- Lines 914 to 916 and 934 to 937 — "Nine faults found in review are also kept as hand-written sequences", "It has found two faults that way" — history. Fix: keep what the tests guard, drop how the faults were found: "Nine known faults each have a hand-written sequence in the fast suite"; "Only this suite can show a deadlock in the daemon's handling of the library's log, or an upload that loses its end under the newer version of TLS; both are covered."
- Line 154 — "an older scheme that phase 5 replaces" — acceptable: it describes the code as built, not how a decision was reached.
- Nothing is stated as open that the decisions file settles. The thirteen rulings that stand (item 7) are stated as the design, and "The two timed limits on a start" is correctly an unmeasured item with its proposal, not a reopened ruling. Items 10 to 13, 19 and 20 are all in the guide as the design.
- Stated as settled but left open by the sources: the silent-time rule after a restart (1.2), and the thirty daemons (3.1).
