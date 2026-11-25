# Brief: fix round 1 of the plan by phase

- **Deliverable (REQUIRED):** every finding of [review-1.md](review-1.md) fixed or
  answered, and `docs/orchestration/plan-by-phase/fix-1.md` saying for each finding what
  you did, in a line.
- **Stop condition (REQUIRED):** each finding has a line in `fix-1.md`; links checked
  again; any Mermaid you change still renders; both fast suites still pass
  (`make -C slice test`, `make -C delivery test` in this checkout).
- **Budget (REQUIRED):** 60 minutes; no cloud spend.

## Rulings on the medium findings

- **M1 (rulings made for the owner):** do not add a list of decisions to any document
  (the owner forbids running decision lists). Leave the rulings where they are. In
  `fix-1.md`, list each ruling the owner has not read, one line each with where it now
  lives, so the orchestrator can put them in front of the owner.
- **M2, M3 (security questions):** add the missing questions to phase 3's and phase 5's
  lists of open questions, one short line each. Answer none of them.
- **M4 (relay start-up advice):** make the guide true: say the local relay binds
  127.0.0.1 and signs everyone in, so it is for tests on one machine only; reaching it
  from another machine waits for phase 5's design.
- **M5 (where the configuration lives):** inside Onshape, restore the earlier answer as
  the current one (a configuration file kept in the Onshape account, and secrets never
  stored on the server, as in PenguinCAM); outside Onshape it is open. Say so where the
  plan now says "open in every phase".
- **M6 (the application that serves the wizard):** the owner's phases include "the
  client-side code and the implementation on the server". Make the wizard component own
  its server side (serving the pages, calling the slice service, later Onshape sign-in
  and calling the relay), say in which phase each part is built, and keep it in the
  wizard component, not a new one.
- **M7:** leave it; the orchestrator fixes those two files outside the repository.

Fix every low finding that is a factual error, a broken rule of the owner's, or a
broken link. For taste findings, use your judgment and say what you chose.

## Rules

Work in the checkout
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/docs-checkout`
(branch `docs/plan-by-phase`); commit there; do not push. Read
[the standing rules](../review-feedback/briefs/standing-rules.md) and the writer's
[brief](brief.md). Scratch folder:
`/tmp/claude-1000/-repos-popcornpenguins/866ece9c-6c1b-4561-aa91-d02b79810b96/scratchpad/plan-by-phase-fix/`.
Never touch `/repos/popcornpenguins/penguin-slicer`; if a browser tool writes into it,
remove only the files it wrote, by name.
