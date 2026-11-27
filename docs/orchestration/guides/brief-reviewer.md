# Brief for the reviewer of a component's guide

You review `README.md` of ONE component of PenguinSlicer (/repos/popcornpenguins/penguin-slicer).
You edit nothing except the review file your task names.

Read first: /home/agent/.claude/skills/reviewing-a-document/lenses.md, then
docs/orchestration/guides/brief-writer.md (what the guide was asked to be, and why the
previous guides failed), then docs/orchestration/guides/decisions-2026-11-27.md (the owner's
latest decisions; they win over every other document), then the plan
(docs/plans/penguin-slicer-plan.md), which the guide's reader has read.

Then read the guide ALONE, from its first line to its last, as its reader: the project's
owner, acting as product manager and as engineering manager or CTO, who was not present when
it was written and will decide from it. Do not open the details file during this reading.

Report under these headings, most serious first within each.

**1. Can the reader decide from it?** For each of these, say yes or no and what is missing:
whether the component does the right things for a user; whether its division of work with
the other components is sound; whether its approaches to the hard parts are sound; whether
its limits and targets are the right ones; whether its security is adequate; whether its
behaviour on failure, cancel, restart and deploy is acceptable; what is built and what is
not; what remains undecided. A requirement area the guide leaves out, functional or
non-functional, is a finding.

**2. Written for a person.** Every code-level name that slipped in (make target, route path,
HTTP verb or status code, setting or environment-variable name, constant, error code,
function, class or file name from the code, test name), with its line and the plain words to
use. Every sentence that must be read twice, every paragraph that lists where it should
explain, every table that stands where prose was needed or before the text that explains it,
every term used before it is defined.

**3. True.** Now open the sources and check the guide against them: its own
`README-details.md`, docs/architecture.md, the frozen design
docs/specs/2026-11-25-hosted-architecture-design.md, the decisions file, and for a component
with code, the code itself where a claim about what is built looks doubtful. Report each
figure, rule or claim that differs from its source, has lost an exception that changes its
meaning, states something as built that is not (or the reverse), or contradicts the
decisions file. Report each requirement or decision present in the sources that the guide
omits and that its reader would need in order to judge the component.

**4. One name per thing, and the design as it is to be.** A thing under two names; history,
rejected options or "the owner decided" in the body; anything stated as open that the
decisions file settles, or as settled that it leaves open.

Start the review file with three sentences: is the guide ready for the owner, and the single
most important thing to fix. Each finding one bullet: the line, the quoted words, what is
wrong, and the exact fix (replacement words, or what to add where, with its source). No
stylistic preferences.

Shell rules: use the Read and Write tools for files; one plain command with absolute paths
per shell call; no `cd … && …` chains, no `rm`, no heredocs or interpreters that edit files;
no git command that changes anything.

Report back in under 150 words: the verdict, the number of findings under each heading, and
the four most serious.
