# PenguinSlicer

PenguinSlicer is 3D printing from Onshape: it takes parts, lays them out on a printer's
plate, slices them with Orca on a server and sends the sliced file to the printer. Its
first users are FRC teams, and it is not limited to them.

Where the work stands and what comes next is in [the plan](docs/plans/penguin-slicer-plan.md).
How the components fit together when hosted is in [the architecture](docs/architecture.md).

The repository holds five components. Each is developed as its own project: it has its own
folder, its own tests and its own guide, and it runs without the other four. A component's
guide is the `README.md` in its folder, written for a person; `README-details.md` beside it
holds everything someone changing the component needs.

| Folder | Component | What it does |
|---|---|---|
| [slice/](slice/README.md) | Slice service | Takes a plate configuration, runs Orca Slicer, returns a sliced file, through its HTTP interface |
| [delivery/](delivery/README.md) | Printer delivery | Sends a sliced file to a printer and reports how the print goes |
| [wizard/](wizard/README.md) | Wizard | The step-by-step user interface: the code in the browser (not started) |
| [front/](front/README.md) | Front server | Serves the wizard's pages, signs users in, calls the slice service, keeps sliced files and configurations, runs the relay (not started) |
| `onshape/` | Onshape integration | Makes PenguinSlicer work inside Onshape: the Onshape app and its panel, what is selected, and the export of the selected parts with the document's units to the wizard (not started) |

The shapes that pass between the components are the [contracts](contracts/README.md):
[the part set](contracts/part-set.md),
[the wizard and the front server](contracts/wizard-front-server.md),
[the configuration](contracts/configuration.md),
[the table of settings](contracts/settings-table.md),
[the plate configuration](contracts/plate-configuration.md),
[the sliced file](contracts/sliced-file.md),
[the slice service's HTTP interface](contracts/slice-http-interface.md),
[the error report](contracts/error-report.md) and
[the progress report](contracts/progress-report.md).

The wizard looks the same as [the mockup](docs/mockups/print-wizard/index.html), which is
kept in the repository as the reference for the look; what the wizard does is in
[its guide](wizard/README.md).

Orca Slicer is licensed under the AGPL and PenguinSlicer under the MIT licence. Anyone
working on PenguinSlicer may read Orca's source to understand its algorithms and
methods, and never copies its code.

## Rules that keep the components separate

- A component depends only on [contracts/](contracts/README.md), never on another
  component's code.
- Every component can be exercised through its interface with the example files in
  `contracts/examples/`; for the slice service that is its HTTP interface, with `curl`
  ([the slice service's details file](slice/README-details.md), "Use").
- Every component reports failures as an
  [error report](contracts/error-report.md) and long jobs as
  [progress reports](contracts/progress-report.md).
- Each component is its own `uv` project with its own `pyproject.toml`, and its own
  `make test`, which is fast and never flaky: no network, no real waiting, no dependence
  on test order. Tests that need the real Orca Slicer or a real printer are separate
  targets. The wizard is plain JavaScript in the browser: its `uv` project holds only its
  build and its browser tests, and its `make test` runs its tests without a browser on
  Node's own test runner, with no npm package
  ([its details file](wizard/README-details.md#the-project-and-its-tools)).
- The components are run together in one place only: the joined suite in `together/`,
  which starts the front server and the slice service and drives the wizard through their
  interfaces alone
  ([the front server's details file](front/README-details.md#running-phase-2-on-one-machine)).
