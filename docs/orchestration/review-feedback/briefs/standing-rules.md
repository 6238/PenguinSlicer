# Standing rules for the review-feedback run

Read this before your own brief. This run applies the owner's feedback of Fri 2026-11-20
on the session summary. The repository is `/repos/popcornpenguins/penguin-slicer`
(GitHub: `6238/PenguinSlicer`). The owner is away; nobody answers questions. Where your
brief leaves a choice open, choose, and record the choice in your result file.

## Terms, changed by the owner on Fri 2026-11-20

| Old term | New term | Meaning |
|---|---|---|
| copy | **instance** | One placement of a part on the plate. A part printed once has one instance. |
| plate job | **plate configuration** | What to slice: the parts, where each instance sits on the plate, and the chosen profiles and settings. It is a description, not work. |
| HTTP face | **HTTP interface** | The slice service's web routes. |
| Penguin Slicer | **PenguinSlicer** | The repository and the product. |

Unchanged: **slice job** (one plate configuration being sliced by the slice service, from
arrival to its end), slice service, printer delivery, relay, daemon, sliced file,
delivery job, part, plate, profile, error report, progress report, guide (a component's
`README.md`). One name per thing in everything you write. The word "copy" stays where it
means duplicating bytes or a file (`shutil.copy`, "copy the tarball").

The old records under `docs/orchestration/penguin-slicer/` keep the old terms. Do not
edit them.

## The owner's quality bar

The owner has said: "Slow flaky tests are the bane of making good progress."

- **Fast suite** (`make test` in the component's folder): no real Orca, no real printer,
  no network beyond loopback, no real sleeping or waiting on the wall clock, no fixed
  ports, no shared temporary paths, no dependence on test order, the current directory,
  the home directory or the user. It finishes in seconds.
- **No flakes:** a test that fails once in any number of runs, in any order, is a defect
  and is fixed at its cause. Never retried, skipped or given a longer timeout.
- **Coverage that means something:** every refusal, limit, timeout and state transition
  has a test that reaches it and asserts what the caller sees. Branch coverage does not
  fall.
- **Every failure is an error report** (`contracts/error-report.md`) with a stable code,
  a sentence a student understands, a remedy that can help, and the detail kept for the
  log. Each code is listed in the guide and has a test that produces it on purpose.
- Write each test first, see it fail, then make the change.

## Machine limits

This container has 4 CPUs and 5 GB of memory, shared with other agents working at the
same time. One Orca slice can use 1 to 2 GB. Never run more than one real Orca process at
a time, never run the real-Orca suite in parallel workers, and keep parallel test workers
to 2. Bound anything that might hang, and bound the right process: run pytest directly
from the project's environment under a time limit and a memory limit. A timeout on a
wrapper such as `uv run` kills the wrapper and leaves pytest running.

## Rules of work

- Stay inside the folders your brief names. Other agents are working in the other
  folders of the same checkout at the same time.
- No git command that writes (add, commit, switch, checkout, stash, reset, mv, rm) in any
  repository: the coordinator commits. Rename a file by writing the new file and removing
  the old one with a literal path. `git diff`, `git status`, `git grep` and `git log` are
  fine.
- Shell: one plain command per call, absolute paths, no `cd ... && ...` chains (use
  `make -C <path>` or `uv run --project <path>`), no `rm` on a path built from a
  variable, no `eval`, no `sh -c` with built strings, no indirect expansion, no loops
  that build command names. Files are created and edited with the Write and Edit tools
  only, never through `sed -i`, a heredoc or an interpreter.
- Never print or write a secret from the environment. Test values for codes and tokens
  are obviously fake. Do not touch port 6238.
- Scratch files go under your own folder in
  `/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/`.
- You have no sub-agents.
- Markdown you write links other Markdown files as real links, never as code spans.
  Times are Pacific, with weekday and date.
- The deliverable named in your brief is a file. Your reply is one status line (`DONE`,
  `DONE_WITH_CONCERNS`, `BLOCKED`) and at most 14 more lines.
