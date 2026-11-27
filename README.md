# PenguinSlicer

3D printing for FRC shops: take parts, lay them out on a plate, slice them with Orca Slicer
on a server, and send the result to the shop's printer.

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
| `onshape/` | Onshape source | Turns a selection in Onshape into a part set (not started) |

## Rules that keep the components separate

- A component depends only on [contracts/](contracts/README.md), never on another
  component's code.
- Every component can be exercised through its interface with the example files in
  `contracts/examples/`; for the slice service that is its HTTP interface, with `curl`
  ([the slice service's detailed guide](slice/README-details.md), "Use").
- Every component reports failures as an
  [error report](contracts/error-report.md) and long jobs as
  [progress reports](contracts/progress-report.md).
- Each component is its own `uv` project with its own `pyproject.toml`, and its own
  `make test`, which is fast and never flaky: no network, no real waiting, no dependence
  on test order. Tests that need the real Orca Slicer or a real printer are separate
  targets.
