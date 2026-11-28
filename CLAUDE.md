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
  is its guide, written for the person who decides: a product manager and an engineering
  manager at once, who must be able to tell from it whether the component is being built
  correctly. It holds the architectural decisions, the user-interface decisions and the
  requirements, functional and non-functional, with the approach to each hard part, the
  performance and security requirements and each key limit in plain words with its
  figure. It is prose, in plain words, with no line limit, and free of code-level names:
  no make targets, route paths, setting or constant names, error codes, function or class
  names, file paths inside the code or test names. `README-details.md` beside it is the
  builder's document and holds those names, with every figure, rule, error code and
  required test; a detail marked *proposed* there is the builder's to settle while
  building, and is never a name or a shape that passes between components, which the
  contracts fix. In a component that has code, everything
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
- **The contracts** are in [contracts/](contracts/README.md), one file each, with
  examples in `contracts/examples/`:
  [the part set](contracts/part-set.md),
  [the wizard and the front server](contracts/wizard-front-server.md),
  [the configuration](contracts/configuration.md),
  [the table of settings](contracts/settings-table.md),
  [the plate configuration](contracts/plate-configuration.md),
  [the sliced file](contracts/sliced-file.md),
  [the slice service's HTTP interface](contracts/slice-http-interface.md),
  [the error report](contracts/error-report.md) and
  [the progress report](contracts/progress-report.md). What phase 2 builds is marked in
  each as to be built.
- **The wizard looks like the mockup.**
  [docs/mockups/print-wizard](docs/mockups/print-wizard/index.html), at version 8, is the
  reference for the look and is kept; it is never edited and never thrown away. The
  wizard matches its layout, elements, order, colours, type and wording at each width,
  taking over its style sheets where that is the cheap way. Its scripts were faked, so
  the wizard's behaviour is built from [its guide](wizard/README.md); for the Layout and
  Preview steps, where the guide and the mockup are silent, Orca's behaviour is the
  model.
- **Reading Orca's source.** An implementer may read Orca's source to understand its
  algorithms and methods, and never copies its code: Orca is AGPL and PenguinSlicer is
  MIT, and the licence covers the code as written, not the idea behind it. The table of
  settings is taken from Orca's source each time an Orca version is integrated, so taking
  a new Orca version needs that version's source as well as its release.
- Each component is its own `uv` project. Run its commands with `make -C <component> ...`.
  The wizard is plain JavaScript: its `uv` project holds its build and its browser tests,
  and its fast suite runs on Node's own test runner, with no npm package
  ([The project and its tools](wizard/README-details.md#the-project-and-its-tools)). How
  the three phase 2 components are started together on one machine is
  [Running phase 2 on one machine](front/README-details.md#running-phase-2-on-one-machine).

| Component | Fast suite | Other targets |
|---|---|---|
| `slice/` | `make -C slice test` | `install`, `test-parallel`, `test-flakes RUNS=20 WORKERS=2`, `coverage`, `test-upstream` (real Orca Slicer; `test-orca` is the same), `upgrade-orca VERSION=x.y.z`, `orca-source` (the pinned Orca's source, for the table of settings), `settings-table` |
| `delivery/` | `make -C delivery test` | `install`, `test-parallel`, `test-repeat`, `slowest`, `coverage`, `test-properties`, `test-sim` (simulated printer), `test-upstream`, `upgrade-printer-library`, `test-together`, `together`, `daemon-tarball`, `hardware-smoke` |
| `wizard/` (phase 2, being built: its project, build, trials, geometry, retrying, the panel as a whole, who the user is and the configuration, the browser's storage, the worker's part pictures, the Parts step, and the Settings step with advanced mode; the other steps' contents to be built) | `make -C wizard test` | `install`, `test-browser`, `build` (writes `wizard/dist/`), `look` (the panel's pictures beside the mockup's), `look-parts` (the kept parts' pictures), `look-parts-step` (the Parts step's pictures beside the mockup's), `look-settings-step` (the Settings step's and advanced mode's pictures beside the mockup's), `offered-faces` (the poses the slice service's real-Orca suite slices), `trials` (runs `trials-preview` and `trials-geometry`), `trials-parts`, `trials-serve` |
| `front/` (phase 2, being built: the project, the buckets' folder form, the rules for every request, the log's writer, the development identity and the cookie, the pages, the current group's check, the configuration, the table of settings, the user key, uploading a part, submitting a plate configuration, following every slice job to its stored sliced file, asking about a slice job, progress streams, the sliced file and its details, the two-hour rule with its sweep, collecting at start, the log's gathering of the slice service's lines, the page's reports about itself and the tests across the whole exist; the joined suite is to be built) | `make -C front test` | `install`, `test-parallel`, `coverage`; outside the fast suite `test-r2` and `test-hosted` (phase 3, to be built) |
| `together/` (phase 2, to be built) | none: it is the joined suite, `make -C together test` | |

## Terms

One name per thing, in code, documents and the sentences users read: the **user** is the
person using PenguinSlicer, and an **administrator** is whoever edits the configuration and pairs the printer, which is
every user of a group
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

- A test never sleeps and never waits a number of seconds to see whether something has
  happened: time passes through a fake clock that the test moves, and a test waits on an
  event, never on a duration.
- Code that talks over a network or depends on the order of events is tested with fakes
  that let the test put the events in an exact order.
- The fast suites use no real Orca, no real printer and no fixed ports, and must pass in
  any order, any number of times. A test that fails once is fixed at its cause, never
  retried or skipped.
- Every failure a caller can see is an error report
  ([contracts/error-report.md](contracts/error-report.md)) with a test that produces it on
  purpose. Every long job sends progress reports and can be stopped by the component
  that runs it; a slice job is never cancelled by hand (the plan's standing requirement
  "Cancellation").
- A change to a component is checked by someone who did not write it: rerun the suites in
  random order, mutate the changed checks by hand, and try hostile inputs.
- One interface per component is the default, not a hard rule. The slice service has one,
  its HTTP interface. The wizard may exist both inside Onshape and as a page reached
  directly from a browser, and the Onshape integration (the component that makes
  PenguinSlicer work inside Onshape) may likewise have two homes.

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
