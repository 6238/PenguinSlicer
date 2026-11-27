# Brief for the second check of a component's guide

Second and last round. You edit ONLY the guide named in your task (with the Edit tool) and
write one short review file. Read first: docs/orchestration/guides/brief-writer.md (what the
guide must be), docs/orchestration/guides/decisions-2026-11-27.md (the owner's latest
decisions; they win), and the first review named in your task.

1. Read the guide from its first line to its last, as its reader: the project's owner, as
   product manager and as engineering manager, who was not present and will decide from it.
2. For each finding of the first review, note in your review file: fixed, not fixed, or
   fixed in a way that created a new problem.
3. While reading, find what the fixes broke or left: a contradiction inside the guide; a
   sentence left dangling by a cut; something used before it is explained; a code-level name
   (route path, setting name, error code, constant, function or file name from the code,
   make target); a figure in no source that is not marked as a proposal; history or "the
   owner decided" in the body; a statement that does not say whether it is built or to be
   built; an undecided item that cannot be decided from the page; a broken link or anchor
   (check every relative link and anchor in the file); a `mermaid` fence that would not
   parse.
4. FIX what you find, directly in the guide, when the fix is a matter of wording, order, a
   mark or a link. Do not settle a design question: if something is undecided, make sure it
   is written as an undecided item with its backing and a recommendation.
5. Write the review file: a two-sentence verdict (is it ready for the owner); the status of
   the first review's findings; what you changed, each in a line; and anything you found and
   did NOT change because it needs the owner or the coordinator, each in a line.

Shell rules: use the Read, Edit and Write tools for files; one plain command with absolute
paths per shell call; no `cd … && …` chains, no `rm`, no heredocs or interpreters that
rewrite files; no git command that changes anything.

Report back in under 120 words: the verdict, how many first-round findings remained unfixed,
how many things you changed, and what you left for the owner or the coordinator.
