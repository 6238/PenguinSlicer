# Error report

The one shape in which every component reports a failure. A failure that reaches a caller
in any other shape (a bare exception, an exit code, a log line only) is a bug.

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `code` | string | yes | A stable name for this failure, `component.what`, for example `slice.empty_layers`. Tests and support refer to it. It never changes once released. |
| `message` | string | yes | What happened, in one sentence a student understands. No codes, no jargon. |
| `where` | object | no | What the failure is about, when known. Any of `part` (name), `copy` (name), `height_mm`, `stage`. |
| `remedy` | string | yes | What to do next, in one sentence. |
| `action` | string | no | The name of the single action that fixes it, when one exists, for example `enable_supports`. A user interface may offer it as a button. |
| `retryable` | boolean | yes | Whether the same request may succeed if sent again unchanged. |
| `detail` | string | yes | The underlying evidence for the server log: the tool's own words, the exit code, the printer's status. Never shown to a student as it is. May be empty only when there is truly none. |

## Rules

- `message` and `remedy` are complete sentences and never blame the student.
- `remedy` never proposes an action that cannot help.
- `detail` is captured before any cleanup removes its source.
- No field ever holds a secret: no token, access code or pairing code.
- Every `code` a component can produce is listed in that component's guide, and each has a
  test that produces it on purpose.

## Example

See [examples/error-report.json](examples/error-report.json).
