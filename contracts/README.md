# Contracts

The shapes that pass between components. A component depends on these and on nothing else
outside its own folder.

| Contract | Passes from | To | Defined in |
|---|---|---|---|
| Part set | Onshape source, or a file upload | Wizard | not written yet |
| Plate job | Wizard | Slice service | [plate-job.md](plate-job.md) |
| Sliced file | Slice service | Printer delivery | [sliced-file.md](sliced-file.md) |
| Error report | Every component | Its caller | [error-report.md](error-report.md) |
| Progress report | Every component | Its caller | [progress-report.md](progress-report.md) |

Example files for each contract are in `examples/`. A change to a contract changes its
definition, its examples and the tests of every component that uses it, in one commit.
