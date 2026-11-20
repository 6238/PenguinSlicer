# Penguin Slicer

3D printing for FRC shops: take parts, lay them out on a plate, slice them with Orca Slicer
on a server, and send the result to the shop's printer.

The repository holds four components. Each is developed as its own project: it has its own
folder, its own tests and its own guide, and it runs without the other three.

| Folder | Component | What it does |
|---|---|---|
| [slice/](slice/README.md) | Slice service | Takes a plate job, runs Orca Slicer, returns a sliced file |
| [delivery/](delivery/README.md) | Printer delivery | Sends a sliced file to a printer and reports how the print goes |
| `wizard/` | Wizard | The step-by-step user interface (not started) |
| `onshape/` | Onshape source | Turns a selection in Onshape into a part set (not started) |

## Rules that keep the components separate

- A component depends only on [contracts/](contracts/README.md), never on another
  component's code.
- Every component can be exercised from the command line with the example files in
  `contracts/examples/`.
- Every component reports failures as an
  [error report](contracts/error-report.md) and long jobs as
  [progress reports](contracts/progress-report.md).
- Each component is its own `uv` project with its own `pyproject.toml`, and its own
  `make test`, which is fast and never flaky: no network, no real waiting, no dependence
  on test order. Tests that need the real Orca Slicer or a real printer are separate
  targets.
