# Contracts

The shapes that pass between components. A component depends on these and on nothing else
outside its own folder.

| Contract | Passes from | To | Defined in |
|---|---|---|---|
| Part set | The Onshape integration, or a file upload | Wizard | [part-set.md](part-set.md) |
| The wizard's requests and the front server's answers | Wizard | Front server, and back | [wizard-front-server.md](wizard-front-server.md) |
| Configuration | Front server | Wizard | [configuration.md](configuration.md) |
| Table of settings | Slice service, through the front server | Wizard | [settings-table.md](settings-table.md) |
| Plate configuration | Wizard, through the front server | Slice service | [plate-configuration.md](plate-configuration.md) |
| Sliced file | Slice service | Front server, then printer delivery | [sliced-file.md](sliced-file.md) |
| The slice service's HTTP interface: the front server's requests and the slice service's answers | Front server | Slice service, and back | [slice-http-interface.md](slice-http-interface.md) |
| Error report | Every component | Its caller | [error-report.md](error-report.md) |
| Progress report | Every component | Its caller | [progress-report.md](progress-report.md) |

A contract describes the code as built unless it says otherwise; what phase 2 builds is
marked in each contract as to be built, with the phase. Each name and shape here is fixed
for the builders of both sides: no contract leaves a name for one builder to settle alone.

## Rules

- **Each record kept in the state bucket carries the number of its format,** in a field
  named `format`, an integer counting from 1: the group's configuration document, and every
  record the front server or the relay writes there. A component reads every format up to
  its own and refuses one it does not know, saying so in the log, so that a record written
  by an older front server is read by a newer one and a record written by a newer one is
  never misread by an older one
  ([the architecture](../docs/architecture.md#old-and-new-versions-together)). A change
  that a reader of the previous version could not read takes a new number; a field added
  with a meaning when it is left out does not. The part set and the table of settings
  carry a format number by the same rule, though neither is kept in the state bucket.
- **One name for one thing.** A field that means the same thing in two contracts has the
  same name in both: `printer`, `filament` and `process` for Orca's profile names,
  `overrides` for settings that replace values of the process profile, `units` (`"mm"` or
  `"in"`) for a part's units label, `sha256` for the hash of a part's bytes.
- **A change in one commit.** Example files for each contract are in `examples/`. A change
  to a contract changes its definition, its examples and the tests of every component that
  uses it, in one commit.
