# Progress report

The one shape in which every component reports how far a long job has got. A job is
anything that can take more than a few seconds: a slice, a delivery, a print.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `job` | string | yes | The job's id. |
| `state` | string | yes | One of `queued`, `running`, `done`, `failed`, `cancelled`. The last three are final. |
| `stage` | string | no | What the job is doing now, as a stable name, for example `generating_supports` or `uploading`. Each component's guide lists its stages in order. |
| `stage_label` | string | no | The stage in words a user understands. |
| `fraction` | number | no | How far through the whole job, from 0 to 1. Left out when it cannot be known; never invented. |
| `elapsed_s` | number | yes | Seconds since the job started running; it may carry a fraction (a slice job's is to the millisecond). |
| `expected_s` | number | no | The expected total running time in seconds, when an estimate exists; it may carry a fraction. |
| `sequence` | integer | yes | Increases by one with every report of a job, so a client can tell a missed report from a repeated one. |
| `error` | object | when `state` is `failed` | The [error report](error-report.md). |
| `ahead` | integer | when a slice job's `state` is `queued` | From phase 2: how many slice jobs are ahead of this one, those running and those waiting before it, counted over every user. 0 or more. |
| `cancel_reason` | string | when a slice job's `state` is `cancelled` | From phase 2: why the slice job ended early. One of `replaced` (the same plate's later slice replaced it), `shutdown` (the slice service was asked to stop) or `requested` (the slice service's own cancel request, which no component of PenguinSlicer sends). |

A component may add fields of its own beside these, for example `layer` and `total_layers`
for a print. It never changes the meaning of the fields above.

## A slice job's reports

*From phase 2.* What a page can meet while it follows a slice job, and what each means:

| The report | Means | What the wizard does |
|---|---|---|
| `queued`, with `ahead` | The slice job is waiting for the slicer, behind `ahead` others | Shows the slice as waiting, with how many are ahead ("2 slices ahead of yours.") |
| `running` | Orca, or the slice service around it, is working | Shows the stage, the fraction and the times |
| `done` | The sliced file is stored and can be fetched | Shows the result |
| `failed`, with `error` | The slice failed; the error report says why | Shows the error report's sentences |
| `cancelled`, `cancel_reason` `replaced` | A later slice job of the same plate replaced it | Nothing: it already follows the later one |
| `cancelled`, `cancel_reason` `shutdown` | The slice service was asked to stop before this slice job ran, or was asked a second time while it ran | Submits the plate again by itself, with a new submission value |

A slice cannot be cancelled by hand, so no page meets `requested`. A `cancelled` slice job
has no sliced file and no error report.

**A slice job's stages,** in the order they come, each with its `stage_label` and whether
Orca's own `fraction` moves through it. A page that lists the stages (the wizard's slicing
card) shows these, marking the current one by its `stage`:

| Order | `stage` | `stage_label` | `fraction` |
|---|---|---|---|
| 1 | `queued` | Waiting for the slicer | none |
| 2 | `building_plate` | Building the plate | none |
| 3 | `slicing` | Slicing the plate | none |
| 4 | `loading` | Loading the plate | Orca's |
| 5 | `preparing` | Preparing to slice | Orca's |
| 6 | `slicing_mesh` | Slicing the parts into layers | Orca's |
| 7 | `generating_walls` | Generating walls | Orca's |
| 8 | `generating_infill` | Generating infill | Orca's |
| 9 | `generating_supports` | Checking and generating supports | Orca's |
| 10 | `optimizing_toolpath` | Optimizing the toolpath | Orca's |
| 11 | `generating_gcode` | Generating G-code | Orca's |
| 12 | `exporting` | Writing the sliced file | Orca's |
| 13 | `reading_result` | Reading the sliced file | none |

A slice job may skip a stage that Orca does not report for a plate, but never goes back to an earlier one. A `stage` a page does not know (a new Orca version may
add one) is shown by its `stage_label` alone, as the current stage after the last known stage
it has seen, and the list is not redrawn; a page never fails on an unknown stage. A stage is
never renamed once released; a new one is added to this table in the commit that makes the
slice service send it.

## Rules

- A job sends a report on every change of `state` or `stage`, and at least every second
  while `fraction` is moving. A waiting slice job also sends one whenever `ahead` changes.
- A client that connects late receives the latest report at once.
- After a final state no further report is sent for that job.
- `cancelled` is reported only after the work itself has stopped.
- A slice job's `cancelled` report always carries `cancel_reason`; a job of another
  component never does.

## Examples

See [examples/progress-report.json](examples/progress-report.json), a slice job running;
[examples/progress-report-waiting.json](examples/progress-report-waiting.json), a slice job
waiting behind two others; and
[examples/progress-report-replaced.json](examples/progress-report-replaced.json), a slice
job ended because the same plate's later slice replaced it.
