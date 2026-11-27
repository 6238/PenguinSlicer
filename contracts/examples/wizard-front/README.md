# Examples: the wizard and the front server

Each file here is one example request or answer of
[the contract between the wizard and the front server](../../wizard-front-server.md), written
out whole from the example that stands inline in the contract, where a link to the file
stands beside it. A file holds exactly what its inline example holds; where the inline example
is shortened (an ellipsis, a placeholder in angle brackets), the file completes it with values
taken from the other contracts' examples, so that every file is a complete, valid request or
answer. The contract wins over a file wherever the two differ.

The front server's builder and the wizard's builder each check their stand-ins against these
files.

| File | What it is | Phase |
|---|---|---|
| [me.json](me.json) | The `200` answer to `GET /api/me`: the signed-in user and their two groups | 2 |
| [configuration-write-request.json](configuration-write-request.json) | The body of `PUT /api/configuration`: `based_on` and the whole document, here [the hand-written configuration](../configuration-hand-written.json) | 2 |
| [configuration-written.json](configuration-written.json) | The `200` answer to that `PUT`: the new `revision`, `source` `"group"` and the group's name | 2 |
| [part-record.json](part-record.json) | The `201` answer to `POST /api/parts?units=in`: the part's record, with one `slice.part_not_watertight` warning | 2 |
| [slice-accepted.json](slice-accepted.json) | The `202` answer to `POST /api/slices` for [the phase 2 plate configuration](../plate-configuration-phase-2.json): the slice job, waiting behind two others | 2 |
| [slice-done.json](slice-done.json) | The `200` answer to `GET /api/slices/<slice>` for a finished slice job: its `done` report, carrying the sliced file's details | 2 |
| [slice-events.txt](slice-events.txt) | `GET /api/slices/<slice>/events`: the `version` event, a running report, a comment line and the final `done` report | 2 |
| [slice-summary.json](slice-summary.json) | The `200` answer to `GET /api/slices/<slice>/summary`: the sliced file's details, later than the `done` report and so with fewer seconds to expiry | 2 |
| [report-failure-request.json](report-failure-request.json) | The body of `POST /api/reports/failure`: a part the page cannot draw | 2 |
| [signout.json](signout.json) | The `200` answer to `POST /api/signout` | 3 |
| [signin-window-signed-in.json](signin-window-signed-in.json) | The message the callback's small window sends its opener after a sign-in | 4 |
| [printer-pairing-request.json](printer-pairing-request.json) | The body of `POST /api/printer/pairing` | 5 |
| [printer-send-request.json](printer-send-request.json) | The body of `POST /api/printer/deliveries` | 5 |
| [printer-mine.json](printer-mine.json) | The `200` answer to `GET /api/printer/mine`: a live delivery job printing and the last print, done | 5 |

The error reports the front server passes on from the slice service have their examples
beside [the error report](../../error-report.md) and in [slice-http/](../slice-http/); the
configuration and the table of settings that `GET /api/configuration` and
`GET /api/settings-table` carry have theirs beside [the configuration](../../configuration.md)
and [the table of settings](../../settings-table.md).
