# Final read: the hosted architecture design

Reviewed: [the hosted architecture design](../../specs/2026-11-25-hosted-architecture-design.md),
read once from its first line to its last on Fri 2026-11-27 (Pacific), after the findings
of [the cohesion review](review-cohesion.md) were applied. Line numbers are those of the
design document as it stood at this read.

## Verdict

The document is ready for the owner's final read: nothing serious remains, and it reads
as one design with every figure agreeing from the Short answer to the last list. The
eleven new findings below are small; the first four are leftovers of the patching and
are worth applying first, because each would make a careful reader stop or be misled.

## The cohesion review's findings: fixed or not

All twenty findings under "1. Contradictions" and "3. Seams" are fixed.

### 1. Contradictions

1. "Nothing in the state bucket can start a print" against the delivery-job record: fixed (lines 54, 442, 750 to 755).
2. "Pose as a daemon" unqualified: fixed (line 443, "once the daemon has its token").
3. The Terms row for the paired-printer record: fixed (line 77).
4. The daemon fetching "from the state bucket": fixed (line 655).
5. The Short answer on replacing secrets: fixed (lines 62 to 63).
6. The state table's "Until its sliced file expires": fixed (line 616).
7. Three lists of the browser's storage: fixed (lines 295 to 297, 616, 931 to 932).
8. Six secrets against four rows: fixed (lines 785 and 787).
9. "Everything the daemon needs" against the note of the print: fixed (lines 463 and 473).
10. "Measurements" in log lines: fixed, by adding the measurements to the slice job's line (line 562) and keeping them at line 728.
11. "Frees the printer": fixed (lines 450 and 520).

### 3. Seams

1. A send and unpairing under "Pairing": fixed (heading at line 447; "send" is in the Terms table).
2. "Progress streams" under "Printers": fixed (moved to line 189), but the move left the status paragraph wrong; see the first new finding.
3. The held wait explained twice: fixed (the cell at line 495 is cut and the paragraph's last sentence is gone).
4. "From then on" after the restart clause: fixed (lines 257 to 267).
5. The opening paragraph: fixed (lines 3 to 13).
6. The stray x86_64 sentence under "Size": fixed (deleted).
7. The part store's disk limit only in the list of changes: fixed (lines 248 to 250).
8. Two lists both called "Two things": fixed, but the new opening "Beyond those" has lost its antecedent; see the fourth new finding.
9. "By phase" leaving parts unassigned: fixed (lines 953 to 960).

## New findings

Most serious first. None is serious.

- **Line 9, "The owner has reviewed "The shape","**, against line 12, "has not yet read
  "Printers"". "Progress streams" was under "Printers" and now sits in "The shape"
  (line 189), so the status paragraph tells the owner that a subsection they have not
  read is one they have reviewed. Replace `The owner has reviewed "The shape", "Where
  each piece of state` with `The owner has reviewed "The shape" (except its last
  subsection, "Progress streams", which was moved there since), "Where each piece of
  state`.
- **Line 797, "In an emergency, when a key has leaked, its previous key is removed at
  once."** The key that leaked is the current one; "its previous key" reads as a
  different, older key, so the sentence seems to remove the wrong key. Replace with: "In
  an emergency, when a key has leaked, it is replaced and is not kept as the previous
  key."
- **Line 660, "The records of delivery jobs are in the state bucket, not its memory,"**
  A leftover: the sentence once began "The relay's records", and "its" now has nothing to
  refer to. Replace with: "The records of delivery jobs are in the state bucket, not the
  relay's memory,".
- **Line 666, "Beyond those, a crash (not a deploy) loses"**. "Those" pointed at the two
  things named at lines 635 to 637; thirty lines, two tables and a paragraph about
  records now stand between. Replace "Beyond those," with "Beyond what the two tables
  show,".
- **Lines 750 to 751, "Nothing read from storage can start a print. Neither the state
  bucket nor the configuration holds anything that, once read, does:"** Two faults.
  "Storage" everywhere else is the browser's storage. And the configuration is a document
  in the state bucket (line 319), so "neither ... nor" names one thing twice, a leftover
  of the plan's configuration file in the Onshape account. Replace with: "**Nothing read
  from the state bucket can start a print.** Nothing it holds, the configuration
  included, does once read:".
- **Lines 433 to 434 and 444 against line 658.** Line 444: "A wrong code gets the same
  answer whatever was wrong with it"; line 434 gives that answer as "no daemon is showing
  that code"; line 658 gives a different one, "no daemon is showing that code yet and to
  try again in a moment". After a restart the relay cannot tell a wrong code from one not
  yet offered again, so there is one answer. Replace at lines 433 to 434: "If none is,
  the user is told at once that no daemon is showing that code and to try again in a
  moment." Replace at line 658: "They are told, as for any wrong code, that no daemon is
  showing that code and to try again in a moment".
- **Lines 403 to 405, "Every route that changes something therefore also requires a
  header that only the wizard's own page can set and checks the request's origin"**. The
  daemon's routes change things (a sync, an offer of a pairing code) and cannot carry
  that header; line 351 has just said they carry the daemon's token instead. Replace
  "Every route that changes something therefore" with "Every route that changes something
  on the strength of the cookie therefore".
- **Lines 778 to 779, "Replacing one changes a setting of the front server, which
  restarts as at any deploy."** Untrue of the fifth and sixth secrets, which the front
  server does not hold (lines 773 to 775, and the table's last row says so). Replace
  with: "Replacing any of the first four changes a setting of the front server, which
  restarts as at any deploy."
- **Lines 210 and 224, "the name of each part" and "referred to by name"**, against line
  229, "names each part by that hash", and line 606, "part names". "Name" is the part's
  hash in the first two places and the user's file name in the logs and at line 728.
  Replace at line 210: "the layout, the settings, and the hash of each part". Replace at
  line 224: "A part is uploaded once and then referred to by its hash."
- **Lines 859 to 861, "deletes its copy of a sliced file once the front server has
  fetched it"**, against line 271, "Once the front server has stored a sliced file, the
  slice container deletes its own copy", and line 620, "until the front server has stored
  it". Fetched and stored are different moments, and a builder will take the list of
  changes as the instruction. Replace at line 860: "deletes its copy of a sliced file
  once the front server has stored it".
- **Lines 359 to 361, "only when a call to Onshape needs one, which nothing does before
  phase 4"**, against lines 377 to 378, "Once the app is public, the setting becomes one
  day". Reading the groups again a day after sign-in needs a renewed token, and the app
  may become public before phase 4. Replace "which nothing does before phase 4" with
  "which nothing does before phase 4 unless the app is public by then, when reading the
  groups again does".

Checked and clean: no statement of how the code works today outside the three sections
allowed to make one; no term used before the Terms table or the plan explains it; every
duration, size and count agrees across the Short answer, the body, the state table, both
restart tables and the two lists of changes; "Progress streams" reads correctly in its
new place and the later references to it (lines 502 to 503, 862 to 863, 984 to 987)
still hold.
