# PenguinSlicer: notes for agents

Read [README.md](README.md) first: five components, each its own project, depending only
on [contracts/](contracts/README.md).

## Working here

- The repository is `6238/PenguinSlicer` on GitHub. Every change reaches `main` through a
  pull request from a branch; never commit or push to `main` directly.
- Start from [the plan](docs/plans/penguin-slicer-plan.md): the terms, the standing
  requirements, where each component stands and the phases of work. Then
  [the architecture](docs/architecture.md): what runs where when hosted, where state
  lives, restarts and deploys, security and the log.
- **Before changing a component, read its `README-details.md`.** A component's `README.md`
  is its guide for a person and is kept short; `README-details.md` beside it holds every
  figure, rule, error code and required test. In a component that has code, everything
  in the details file outside the section "To be built" is true of the code as built;
  when you build an item of "To be built", move its text into the body and update the
  `README.md` to match. Never let the two files disagree.
- The project is deployed continuously: a deploy at any moment must interrupt no user.
  Treat a restart at any moment as normal in every design and change (the plan's
  standing requirement "Deploys").
- [docs/specs/2026-11-25-hosted-architecture-design.md](docs/specs/2026-11-25-hosted-architecture-design.md)
  is the record of the design the owner approved on Thu 2026-11-26. It is not edited. A
  change to something decided there is made in the living documents, in a pull request
  whose description names the decision it changes;
  [the map of its decisions](docs/orchestration/hosted-architecture/decision-map.md)
  says where each one lives.
- Specs, plans, research, the mockup and the build records live under `docs/`
  (`docs/plans/`, `docs/research/`, `docs/mockups/`, `docs/handoffs/`,
  `docs/orchestration/`).
- Each component is its own `uv` project. Run its commands with `make -C <component> ...`.

| Component | Fast suite | Other targets |
|---|---|---|
| `slice/` | `make -C slice test` | `install`, `test-parallel`, `test-flakes RUNS=20 WORKERS=2`, `coverage`, `test-upstream` (real Orca Slicer; `test-orca` is the same), `upgrade-orca VERSION=x.y.z` |
| `delivery/` | `make -C delivery test` | `install`, `test-parallel`, `test-repeat`, `slowest`, `coverage`, `test-properties`, `test-sim` (simulated printer), `test-upstream`, `upgrade-printer-library`, `test-together`, `together`, `daemon-tarball`, `hardware-smoke` |

## Terms

One name per thing, in code, documents and the sentences users read: the **user** is the
person using PenguinSlicer, and an **administrator** is whoever edits the configuration
(never "student", "mentor" or "team" for either; FRC Team 6238, the Popcorn Penguins, is
named as such); an **instance** is
one placement of a part on the plate (a part printed once has one instance); a **plate
configuration** is what to slice (the parts, where each instance sits, the profiles and
settings), a description, not work; a **slice job** is one plate configuration being
sliced by the slice service; the **wizard** is the code in the browser and the **front server** is everything
behind its address (never "the wizard's server side"); a **slice service process** is one running slice service,
holding its slice jobs in its memory (never called an "instance"); the **HTTP interface**
is the slice service's web routes;
**PenguinSlicer** is the repository and the product. "Copy" means duplicating bytes or a
file, nothing else.

## The quality bar

- The fast suites use no real Orca, no real printer, no real waiting and no fixed ports,
  and must pass in any order, any number of times. A test that fails once is fixed at its
  cause, never retried or skipped.
- Every failure a caller can see is an error report
  ([contracts/error-report.md](contracts/error-report.md)) with a test that produces it on
  purpose. Every long job sends progress reports and can be cancelled.
- A change to a component is checked by someone who did not write it: rerun the suites in
  random order, mutate the changed checks by hand, and try hostile inputs.
- One interface per component is the default, not a hard rule. The slice service has one,
  its HTTP interface. The wizard may exist both inside Onshape and as a page reached
  directly from a browser, and the Onshape source may likewise have two homes.

## Gotchas learned the hard way

- **One real Orca at a time.** A slice can take 1 to 2 GB; never run the real-Orca suite
  in parallel workers.
- **Bound anything that might hang, and bound the right process.** Run pytest directly
  from the project's environment under a time limit and a memory limit. A timeout placed
  on a wrapper such as `uv run` kills the wrapper and leaves pytest running; a test that
  loops on a fake clock can then grow to gigabytes.
- **Orca reports progress through its `--pipe` option**, one message per stage with a
  percentage. Its real reason for a failed slice is in `result.json` (`error_string`,
  `warning_message`), which must be read before the scratch folder is removed; the
  warnings it reported while slicing are only in its debug log (`--debug 3 --logfile`),
  and some reasons reach no file at all.
- **Orca's peak memory is a spike shorter than a tenth of a second.** Sampling current
  memory misses it; the kernel's high-water mark (`VmHWM`) does not. The kernel's
  `ru_maxrss` of a child counts the parent's memory at the fork, so it is not Orca's own.
- **Orca 2.5.x packs the Bambu profiles in `BBL.opc`,** which the profile catalog script
  cannot read yet. The pin stays at 2.4.2 until it can.
- **A running slice service is one slice service process.** Its slice jobs live in that
  process's memory; a client keeps talking to the process that accepted its slice job,
  and a server with several worker processes behind one address loses slice jobs.
- **The printer status sequences in the simulated printer are invented** from one recorded
  status document. `python -m penguin_delivery_daemon record` saves real ones; replace the
  scenarios when recordings exist.
