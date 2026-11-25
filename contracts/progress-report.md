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
| `elapsed_s` | number | yes | Seconds since the job started running. |
| `expected_s` | number | no | The expected total running time in seconds, when an estimate exists. |
| `sequence` | integer | yes | Increases by one with every report of a job, so a client can tell a missed report from a repeated one. |
| `error` | object | when `state` is `failed` | The [error report](error-report.md). |

A component may add fields of its own beside these, for example `layer` and `total_layers`
for a print. It never changes the meaning of the fields above.

## Rules

- A job sends a report on every change of `state` or `stage`, and at least every second
  while `fraction` is moving.
- A client that connects late receives the latest report at once.
- After a final state no further report is sent for that job.
- `cancelled` is reported only after the work itself has stopped.

## Example

See [examples/progress-report.json](examples/progress-report.json).
