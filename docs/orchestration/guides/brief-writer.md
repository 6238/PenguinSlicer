# Brief for the writer of a component's guide

You write `README.md` for ONE component of PenguinSlicer (the repository at
/repos/popcornpenguins/penguin-slicer, on the branch `docs/guides-for-deciders`). Run no git
command that changes anything; the coordinator commits. Edit only the file or files your task
names.

## Who reads it, and why the last attempt failed

The reader is the project's owner, acting as product manager and as engineering manager or
CTO at once. They were present for none of the writing. They read the guide from its first
line to its last and then decide: is this component being built correctly, and what should
change.

The guides that exist now were written to a 200-line limit and came out as lists of make
targets, routes and limits. The owner's verdict on the slice service's: "it is in fact pretty
bad. I don't care about the Makefile targets since the agents are running the Makefiles ... I
care about how this thing works and what its requirements are ... What I really want to see
is good human prose about the things we've been talking about, and so I can react to the
requirements." And: "a lot of times Claude tends to write a lot of very code-specific jargon
... It just needs to be written for a human and not be so tightly tied to jargon." There is
no line limit. Write at the length a person needs to understand the component fully. Expect
several hundred lines.

What the reader wants from the guide, in their words: "everything a human needs to make the
class of decisions that we've done during this session and other sessions": "architectural
decisions, user interface decisions, and requirements (both functional and nonfunctional)".
As engineering manager they look for: the algorithms, as approaches and not as code; the
performance requirements; the security requirements; and whether the software is well
composed into components.

## What to read first

1. /home/agent/.claude/skills/reviewing-a-document/lenses.md : the definition of a finished
   document.
2. docs/orchestration/guides/decisions-2026-11-27.md : what the owner decided most recently.
   Where it differs from any other document, it wins. Items marked "proposed" are stated in
   the guide as the design, since the owner did not object.
3. docs/plans/penguin-slicer-plan.md : the plan, which your reader has read. Use its terms.
4. docs/architecture.md : what spans components. Your guide does not repeat its mechanisms
   at length; where the architecture owns an explanation, give the few sentences your reader
   needs and link to it.
5. Your component's `README-details.md` : the builder's document. It holds the facts, with
   code-level names you must translate into plain words. In a component that has code,
   everything in it outside its section "To be built" is true of the code as built.
6. docs/specs/2026-11-25-hosted-architecture-design.md : the design the owner approved, kept
   as a frozen record. READ IT AS YOUR MODEL OF PROSE: the owner read it closely over several
   rounds and approved it. Sections such as "Parts", "The sliced file", "Coming back", "What
   a restart does", "How often a daemon talks to the relay" and "Replacing a secret" show the
   register wanted: a statement of what happens, the reason in a clause, the figure with what
   it protects, a small table where there are cases, and what is not known said plainly. Do
   not copy its change lists or its review status.
7. The other sources your task names.

## What the guide contains

Use these as the parts of the guide, in an order that reads top to bottom. Rename and merge
them to suit the component; do not leave one empty.

1. **What it is for.** What the component does for a user, in a paragraph. Then why it is a
   component of its own: what it owns, what it must never know or hold, what it exchanges
   with the other components and under which contract, in words and, where it helps, one
   `mermaid` diagram.
2. **What it must do.** Subject by subject, each requirement in plain words with its reason
   and with what a user sees. This is the body of the guide. A reader must be able to say
   "no, that is wrong" to any requirement from the page alone.
3. **How it does the hard parts.** The approach for anything an engineering manager would
   ask about, without code: for example how memory is bounded, how a server reaches a client
   that opens no port, how the faces a part can lie on are found. State the approach, why it
   was chosen, and what it costs.
4. **How well it must do it.** Every limit and target that matters: memory, time, how many
   at once, sizes, durations, frame rate. For each: the figure, what it protects, where the
   figure comes from (a measurement, a proposal, a limit of someone else's), and how it will
   be checked. A table with a sentence of explanation for each row works well.
5. **Security.** Who can reach it, what it trusts and what it treats as hostile, what a flaw
   in it would expose, and what is accepted as a risk and why.
6. **When things go wrong.** Each kind of failure a user can meet, in the user's terms: what
   happened, what they see, what they can do. Cancelling. What a restart or a deploy does.
7. **How it is tested,** at the level of rules a manager cares about: what is proved by
   tests, with fakes that move the clock and order the network's events, and what only a
   real printer, a real Orca or the real host can prove.
8. **What is built and what is not.** Plainly, by phase: what exists and works today, what
   each coming phase adds. A reader must never have to guess whether a sentence elsewhere in
   the guide describes code that exists; say it in the sentence ("today", "to be built in
   phase 2") or keep built and unbuilt in separate passages.
9. **What is undecided or unmeasured.** Each item with everything needed to decide from the
   page: what it is, what is known, the options or the proposal, what each costs and what a
   user would see. Never a one-line question.

## Rules

- **No code-level names.** No make targets, route paths, HTTP verbs or status codes, setting
  or environment-variable names, constant names, error codes, function, class or file names
  from the code, or test names. Say the thing: not "`slice.busy` (503)" but "the user is told
  the slicer is busy and to try again shortly". Names of things a person deals with are fine:
  Orca, Railway, Cloudflare R2, Onshape, the names of the wizard's steps, a file format.
- **Technical content is wanted; code is not.** An approach, a protocol, a data flow, a
  limit, a trade-off, a threat: yes. An identifier: no.
- **Every figure says what it bounds** and whether it is measured, proposed or someone
  else's limit.
- **The design as it is to be.** No history of how a decision was reached, no options that
  lost, no "the owner decided". A reason is welcome when short.
- **One name per thing,** the plan's and the architecture's terms, each defined in a sentence
  at first use. The person using PenguinSlicer is "the user"; never "student", "mentor" or
  "team" for a person or a group. The wizard is the code in the browser; the front server is
  everything behind its address; the component for working inside Onshape is "the Onshape
  integration".
- **Readable top to bottom:** nothing used before it is explained; no table before the text
  that explains its rows.
- **The guide stands alone.** It may rely on the plan, and on the architecture where it
  links to it, never on its own details file. Put one sentence near the top saying that
  `README-details.md` holds what a builder needs.
- Markdown links for any reference to another Markdown file. Diagrams are `mermaid` fences
  (`flowchart TB` or `sequenceDiagram`, short node text, no HTML, no init directives; in a
  sequence diagram no semicolon inside a message). Dates as "Fri 2026-11-27". No time
  estimates, schedules or priorities. No secret values.
- Copy every figure exactly from its source. If two sources disagree and the decisions file
  does not settle it, do not choose: use the figure of the code or of the approved design,
  and list the disagreement in your report.

## Shell rules

Use the Read, Edit and Write tools for files. One plain command with absolute paths per shell
call. No `cd … && …` chains, no `rm`, no heredocs or interpreters that rewrite files.

## Your report

Under 150 words: the file written and its line count; the parts it has; anything you could
not find a source for; disagreements between sources; and decisions you had to make that the
sources did not make (each in a line).
