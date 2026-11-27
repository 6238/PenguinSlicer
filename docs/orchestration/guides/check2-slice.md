# Second check of the slice service's guide

Checked Fri 2026-11-27, Pacific time: [slice/README.md](../../../slice/README.md), read from
its first line to its last, against [the first review](review-slice.md),
[the decisions](decisions-2026-11-27.md) and [the writer's brief](brief-writer.md).

## Verdict

The guide is ready for the owner. Every finding of the first review is fixed, the seams
the fixes left were matters of wording and are now repaired, and what remains open is
written as undecided items with backing and a recommendation.

## Status of the first review's findings

| Findings | Status |
|---|---|
| 1.1 to 1.9 | Fixed. 1.1 and 1.2 became the undecided items "Where the wizard gets the list of settings and the profile catalog's names" and "What a user sees while the slice service stops", each with options, costs and a recommendation |
| The seven cuts under heading 1 (the log, the restart, "Where it stands", the tests, running Orca, reading Orca, the row of 196 spacers) | Fixed |
| The seven sentences to be read twice, the three tables and the five terms used early (heading 2) | Fixed |
| 3.1 to 3.5 (the writer's own claims) | Fixed: the security reasoning is now marked as the guide's own reading, under "How the list of accepted settings is made"; the 7,404 MB sum, the generated list and the check of each value are marked as proposed or unverified |
| 3.6 to 3.17 | Fixed |
| 4.1 | Fixed with a seam: the upstream check was defined twice and one table row still said "the real Orca slices". Repaired in this check |
| 4.2 to 4.8, 4.11 to 4.13 | Fixed |
| 4.9 | Fixed for "the operator". "The owner" still stands in three places; see the last section |
| 4.10 | Fixed with a seam: two places still used the wrong one of "scratch folder" and "the slice job's folder". Repaired in this check |

Findings not fixed: none.

Every relative link and anchor resolves (the plan, the details file, the four contracts,
the architecture's "The shape", "What a restart does" and "Reading what happened", and the
ten anchors inside the guide). The one `mermaid` fence is a plain `flowchart TB` with
quoted labels and parses. The only code-formatted text is the file format `.gcode.3mf`.

## What this check changed in the guide

1. Opening: "Every section below opens with a line that says which" was untrue of four
   sections; now says the sections about what the slice service does open with such a line
   and elsewhere the sentence says it.
2. "The pinned Orca" was used throughout and never introduced; it is now named where the
   version 2.4.2 is first given.
3. "Why it is a component of its own": the user key was stated as if built; it now says
   "from phase 2" and that today no request carries one. The paragraph was rewrapped.
4. The fit test on arrival: "the profile catalog" was used before its section; a clause
   now says what it is.
5. "What a restart does": the folder removed at start is the slice job's folder of a dead
   process, as in the code, not "the scratch folder".
6. "When asked to stop": "up to four minutes" contradicted the table row above it (240
   seconds plus the replacement's start); now says both. The same words in the options
   table of "What a user sees while the slice service stops" are changed to match.
7. "Taking a new Orca version": the second, bold definition of the upstream check is
   removed.
8. The rule on patching Orca: its link now goes to "A part whose first layer is empty",
   not to the top of the whole last part.
9. The limits table, row "Margin, spacing, least size": "The real Orca slices" is now "The
   upstream check slices".
10. "Disk", under Unmeasured: "the folder of one slice job" is now "one slice job's
    folder".
11. "The longest text a text setting may hold" was a one-line question; it now says what
    the limit bounds, what already bounds it, and a recommendation marked as the guide's.
12. "A part whose first layer is empty" listed three options and no recommendation; a
    recommendation marked as the guide's is added (leave it until a real part shows the
    need).

## Found and not changed

- **"The owner" beside "whoever runs the service".** The guide says "the owner's decision"
  (patching Orca), "a configuration the owner places in the state bucket by hand" and
  "Proposed, and the owner's to change", and elsewhere "whoever runs the service". These
  may be two roles of one person; the coordinator should choose whether the guides use one
  name, since the other guides face the same choice.
- **The two recommendations added in changes 11 and 12 are this check's own.** No source
  holds them. They are marked as the guide's recommendation; the owner may strike either.
- **The rule for old and new versions of the two containers** is proposed in the guide
  ("When asked to stop") because the architecture's "Old and new versions together" has no
  rule for this pair. If it is accepted it belongs in the architecture as well, which this
  check may not edit.
- **Three recommendations change the front server, not only the slice service:** that the
  slice service supplies the list of settings and the catalog's names, that the front
  server keeps a submission made during a stop, and that the front server checks a
  configuration against the catalog. The front server's guide should carry the same items
  in the same words; this check did not read it.
- **The details file's two loosenesses reported by the first review** (the 502 MB rise
  beside endpoints that differ by 514, and 188.5 MB against 187.5 MB) are corrected in the
  guide only. The details file still has them.
- **Some lines of the guide run past the wrap width** where a fix inserted words (the
  spacing paragraph, the default set, the measurements' opening, the security section).
  They render the same; rewrapping is cosmetic and was left.
