# Brief for the fixer of a component's guide

You apply one review to `README.md` of ONE component of PenguinSlicer
(/repos/popcornpenguins/penguin-slicer). Edit only that file, with the Edit tool.

Read first: docs/orchestration/guides/brief-writer.md (what the guide must be; all its rules
hold), docs/orchestration/guides/decisions-2026-11-27.md (the owner's latest decisions; they
win over every other document), then the review named in your task, then the guide in full.

Apply every finding under the review's four headings, using its fix unless it is wrong; if
you depart from one, say so in your report.

- **A gap the review found in the design itself** (something no source decides, such as a
  missing limit or an unhandled case) is NOT settled by you. Write it into the guide's part
  on what is undecided or unmeasured, with everything needed to decide from the page: what
  it is, what is known and its figures, the options, what each costs and what a user would
  see, and a recommendation with its reason. Where the body of the guide touches the same
  subject, say there in one clause that it is undecided and link to the item.
- **A figure, method or rule that is in no source** is marked as a proposal in plain words
  ("proposed: …") or removed.
- **Sections the review says to cut or shorten** are cut or shortened: what docs/architecture.md
  owns becomes a few sentences and a link; detail only a builder needs goes (it is in the
  details file). Sections it calls too thin are filled from the sources.
- Keep the guide free of code-level names, readable top to bottom, and with every anchor that
  other documents link to (check with a search of the repository for links into this file
  before renaming or removing a heading).
- After editing, check every relative Markdown link and anchor in the file, and read each
  `mermaid` fence for syntax that would not parse.

Shell rules: use the Read and Edit tools for files; one plain command with absolute paths per
shell call; no `cd … && …` chains, no `rm`, no heredocs or interpreters that rewrite files; no
git command that changes anything.

Report back in under 150 words: findings applied per heading; any not applied and why; the
items you added as undecided, each in a line; the final line count.
