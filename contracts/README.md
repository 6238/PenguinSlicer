# Contracts

The shapes that pass between components. A component depends on these and on nothing else
outside its own folder.

| Contract | Passes from | To | Defined in |
|---|---|---|---|
| Part set | Onshape source, or a file upload | Wizard | not written yet |
| The wizard's requests and the front server's answers | Wizard | Front server, and back | [wizard-front-server.md](wizard-front-server.md): what it must provide; its routes are not written yet |
| Plate configuration | Wizard, through the front server | Slice service | [plate-configuration.md](plate-configuration.md) |
| Sliced file | Slice service | Front server, then printer delivery | [sliced-file.md](sliced-file.md) |
| Configuration | Front server | Wizard | [configuration.md](configuration.md): what it must hold; its fields are not written yet |
| Error report | Every component | Its caller | [error-report.md](error-report.md) |
| Progress report | Every component | Its caller | [progress-report.md](progress-report.md) |

Example files for each contract are in `examples/`. A change to a contract changes its
definition, its examples and the tests of every component that uses it, in one commit.
