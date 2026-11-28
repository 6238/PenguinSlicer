# The slice service's HTTP interface

The requests the front server makes of the slice service, and every answer. The front server
is the slice service's only caller: hosted, over Railway's private network; on one machine,
over the loopback address ([the architecture](../docs/architecture.md#the-shape)). The
shapes that travel in these requests are the data contracts:
[the plate configuration](plate-configuration.md), [the sliced file](sliced-file.md),
[the table of settings](settings-table.md), [the error report](error-report.md) and
[the progress report](progress-report.md).

*Partly built in phase 2.* This contract is the interface of phase 2. Built in the slice
service: the user key on every request marked "yes", `POST /parts`, `POST /slices` with the
plate configuration in its phase 2 form, with the repeat and the replacement of
[Repeat and replacement](#post-slices--submit-a-plate-configuration), `ahead` in a waiting
slice job's report, `GET`, `events`, `file`, `summary` and `DELETE` of one slice job, and
`GET /settings-table`. To be built: `GET /slices`, `DELETE /slices/<job>/file`, `GET /log`
and `slice.stopping`
([The HTTP interface](../slice/README-details.md#the-http-interface) in the slice
service's details file says what is built). The slice service's builder and the front
server's builder both build to this file; neither settles a name or a shape of it alone. A
change to it changes this file, its examples in [examples/slice-http/](examples/slice-http/)
and both components' tests in one commit ([the contracts' rules](README.md#rules)).

## Contents

- [The requests at a glance](#the-requests-at-a-glance)
- [Rules for every request](#rules-for-every-request)
- [Parts](#parts)
- [Slice jobs](#slice-jobs)
- [The sliced file](#the-sliced-file)
- [The table of settings](#the-table-of-settings)
- [The log](#the-log)
- [Error codes](#error-codes)
- [Examples](#examples)

## The requests at a glance

| Method | Path | For | User key |
|---|---|---|---|
| `POST` | `/parts?units=mm` or `?units=in` | Upload one part, to be checked and kept in the part store | yes |
| `POST` | `/slices` | Submit a plate configuration | yes |
| `GET` | `/slices` | Every slice job the slice service process knows, for a front server that has just started | no |
| `GET` | `/slices/<job>` | A slice job's latest progress report | yes |
| `GET` | `/slices/<job>/events` | A slice job's progress stream | yes |
| `GET` | `/slices/<job>/file` | The sliced file of a done slice job | yes |
| `GET` | `/slices/<job>/summary` | The sliced file's summary | yes |
| `DELETE` | `/slices/<job>/file` | The front server has stored the sliced file; the slice service deletes its own copy | yes |
| `DELETE` | `/slices/<job>` | Cancel a slice job: kept as built, and sent by no component of PenguinSlicer | yes |
| `GET` | `/settings-table` | The table of settings, with the profile catalog's names | no |
| `GET` | `/log?after=<n>` | The log lines written after line `n` | no |

Any other path answers `404` `slice.bad_request`, and a method a path does not take `405`
`slice.bad_request`, as built.

## Rules for every request

**The user key.** A request marked "yes" above carries the header `X-Penguin-User-Key`: the
signed-in user's Onshape id, which the front server takes from the cookie and from nowhere
else. The slice service compares user keys and never interprets them. A part is kept, and a
slice job held, under the user key that sent it. A request marked "yes" without the header, or
with an empty one, is answered `400` `slice.no_user_key`, which is a fault of the front
server's. A request about a slice job of another user key is answered exactly as one about an
unknown slice job, `404` `slice.unknown_job`, and logged as a refusal, so that nobody learns
that the slice job exists. The three requests marked "no" answer for the whole slice service
and ignore the header.

**Answers.** A successful answer is a JSON object (`Content-Type: application/json`), except
the sliced file, the progress stream and a compressed table of settings. Every failure is an
[error report](error-report.md) as the whole JSON body, with the status the tables below give.
Every answer carries `Cache-Control: no-store`.

**Times and ids.** A time is a string in UTC, RFC 3339, to the second
(`2026-11-27T22:14:05Z`), except the `time` of a log line, which is to the millisecond
([The log](#the-log)). A slice job's id (`job`) is the slice service's, an opaque string of
1 to 64 letters, digits, `-` and `_`, made at random (as built, `j` and 16 hexadecimal
characters), so that a restarted process never gives an id an earlier process gave: the front
server keeps a sliced file under its slice job's id after the process that made it has gone.

**One process.** A slice service process holds its slice jobs in its memory. A restarted
process knows none of the slice jobs of the process before it, and answers them
`slice.unknown_job`.

**While stopping.** From the moment the slice service is asked to stop, `POST /slices`
answers `503` `slice.stopping` (except a repeat of a remembered submission, which is answered
with its slice job); every other request is answered as usual until the process exits
([the slice service's details, item 14](../slice/README-details.md#phase-2-one-machine)).

**Old and new versions together.** From phase 3 the front server and the slice service are
deployed apart, so a change to this contract may only add: a new request, a new optional query
parameter or header with a meaning when it is left out, a new field of an answer, a new error
code. Removing or renaming a request, a field or a code, or changing a meaning, is forbidden
while a previous front server or slice service may meet it
([Old and new versions together](../docs/architecture.md#old-and-new-versions-together)).

## Parts

### `POST /parts?units=` — upload one part

**Request.** The query parameter `units`, `mm` or `in`: the part's units label. The body is
the part's binary STL, exactly as the browser read it, with `Content-Type:
application/octet-stream` and a `Content-Length`. The front server passes the page's upload
through in pieces with the user key ([`POST /api/parts`](wizard-front-server.md#post-apiparts--upload-one-part)).

**Answers.**

| Status | When | Body |
|---|---|---|
| `201` | The part passes the checks and is kept in the part store | The part's record |
| `413` | A `Content-Length` over 7,500,084 bytes, refused before the body is read; or more than 150,000 triangles | `slice.part_too_detailed`, exactly [examples/error-report-part-over-size.json](examples/error-report-part-over-size.json) for the first case |
| `422` | A check refuses the part | `slice.part_unreadable`, `slice.part_not_binary`, `slice.part_too_small`, `slice.part_no_volume`, `slice.part_too_large` (against the largest printer of the profile catalog) |
| `400` | No units label, or one that is neither `mm` nor `in` | `slice.bad_units` |
| `400` | No `Content-Length` | `slice.bad_request` |
| `400` | No user key | `slice.no_user_key` |
| `500` | The part store cannot be written (a full disk, for one) | `slice.scratch_unwritable` |

**The part's record** is the object of [`POST /api/parts`](wizard-front-server.md#post-apiparts--upload-one-part),
which the front server passes to the page unchanged: `sha256` (64 lowercase hexadecimal
characters), `units` (the label it was kept under), `measurements` (`triangles`; `size_mm`,
the bounding box in millimetres after the scale; `volume_mm3`, or `null` for a surface that is
not closed) and `warnings`, each in the shape of the sliced file's `part_warnings` without
`where`. See [examples/slice-http/part-record.json](examples/slice-http/part-record.json).

**Repeat.** The same bytes under the same user key and units answer the same record and count
as a use of the part.

## Slice jobs

### `POST /slices` — submit a plate configuration

**Request.** The body is a [plate configuration](plate-configuration.md#to-be-built) in its
phase 2 form, `Content-Type: application/json`, at most 1,048,576 bytes, with no files. See
[examples/plate-configuration-phase-2.json](examples/plate-configuration-phase-2.json).

**Answers.**

| Status | When | Body |
|---|---|---|
| `202` | Accepted; or a repeat of a submission the slice service remembers, which starts nothing | The slice job, below |
| `413` | A body over 1,048,576 bytes, refused before it is read | `slice.bad_plate_configuration`, exactly [examples/error-report-plate-configuration-over-size.json](examples/error-report-plate-configuration-over-size.json) |
| `400` | Not JSON, a multipart body, or a field missing, unknown or of a bad form | `slice.bad_plate_configuration` |
| `422` | Parts the part store does not hold under this user key | `slice.part_missing`, with `where.missing_parts` ([Parts missing from the part store](plate-configuration.md#parts-missing-from-the-part-store)) |
| `422` | Another check refuses it | `slice.too_many_instances`, `slice.too_many_parts`, `slice.unknown_printer`, `slice.profiles_not_offered`, `slice.bad_overrides`, `slice.profile_unreadable`, `slice.part_missing` (an instance naming no key of `parts`), `slice.part_too_large` (against the plate's own printer), `slice.placement_off_plate`, `slice.placement_too_tall`, `slice.placement_too_close` |
| `503` | One slice running and two waiting: no more may wait | `slice.busy`, `retryable` true |
| `503` | The slice service has been asked to stop | `slice.stopping`, `retryable` true |
| `400` | No user key | `slice.no_user_key` |
| `500` | The slice job's folder cannot be made, or a bug | `slice.scratch_unwritable`, `slice.unexpected` |

**The slice job,** in the `202` answer:

| Field | Type | Meaning |
|---|---|---|
| `job` | string | The slice job's id |
| `plate_id` | string | The plate configuration's `plate_id`, as sent |
| `submission_id` | string | The plate configuration's `submission_id`, as sent |
| `progress` | object | The slice job's latest [progress report](progress-report.md): for a new slice job its first, `queued` with `ahead`; for a repeat, whatever is latest |
| `part_warnings` | array | The warnings found on the plate's parts when each was uploaded, in the shape of the sliced file's `part_warnings` (with `where` naming the part) |

See [examples/slice-http/slice-accepted.json](examples/slice-http/slice-accepted.json).

**Repeat and replacement.** A plate configuration whose user key and `submission_id` are those
of a slice job the slice service remembers is answered `202` with that slice job before any
check. A plate configuration that passes its checks ends early the earlier waiting or running
slice job of the same user key and `plate_id`, whose last report is `cancelled` with
`cancel_reason` `replaced` ([The plate and the submission](plate-configuration.md#the-plate-and-the-submission)).

### `GET /slices` — every slice job

**For:** a front server that has just started, to find the slice jobs it must follow again and
the sliced files it must still collect ([the front server's details](../front/README-details.md#starting-and-what-a-restart-does)).

**Answer.** `200` `{"slices": [<entry>, …]}`, every slice job the slice service process
remembers, waiting, running or ended, of every user key, in the order they were accepted. An
empty list from a newly started process. Each entry:

| Field | Type | Meaning |
|---|---|---|
| `job` | string | The slice job's id |
| `user_key` | string | The user key it was submitted under |
| `plate_id` | string | Its plate's id |
| `submission_id` | string | Its submission's value |
| `progress` | object | Its latest progress report |
| `file_on_disk` | boolean | `true` while a done slice job's sliced file is still held by the slice service; `false` before it is done, after `DELETE /slices/<job>/file`, and for a slice job that did not end `done` |
| `ended_at` | string or null | When it reached its final state, RFC 3339; `null` while it waits or runs. The front server writes this as the sliced file's `slice_ended_at` when it collects the file at start |

See [examples/slice-http/slices-list.json](examples/slice-http/slices-list.json).

### `GET /slices/<job>` — the latest progress report

**Answer.** `200` with the slice job's latest [progress report](progress-report.md) as the
whole body. `404` `slice.unknown_job` for a slice job unknown, expired, of another process or of
another user key.

### `GET /slices/<job>/events` — the progress stream

**Answer.** `200`, `Content-Type: text/event-stream`. The first event is the latest report at
once; then one event for each new report, ending with the final one, after which the stream
closes. Each event is:

```
id: <the report's sequence>
event: progress
data: <the progress report as JSON, on one line>
```

While nothing changes, the latest report is sent again every 15 seconds with the same `id` and
`sequence`, so that a quiet stream is never silent for longer; the follower drops a report
whose `sequence` it has already passed. From phase 3 a comment line (`:`) every 15 seconds
replaces the repeat. `404` `slice.unknown_job` before the stream starts, as for
`GET /slices/<job>`. See [examples/slice-http/events.txt](examples/slice-http/events.txt).

### `DELETE /slices/<job>` — cancel

Kept as built (`{"job", "cancel": "cancelled" | "cancelling" | "finished", "progress"}`), now
with the user key. A slice cannot be cancelled by hand, and no component of PenguinSlicer sends
it; its `cancelled` report carries `cancel_reason` `requested`.

## The sliced file

### `GET /slices/<job>/file` — the sliced file

**Answer.** `200`, `Content-Type: application/octet-stream`, `Content-Length`, and
`Content-Disposition: attachment; filename="<file>"`, the [sliced file](sliced-file.md),
at most 50 MB.

| Status | When | Body |
|---|---|---|
| `409` | The slice job has not finished | `slice.not_ready` |
| `409` | The slice job failed, or was cancelled | Its own error report, or `slice.cancelled` |
| `410` | The sliced file has been deleted by `DELETE /slices/<job>/file`, or is gone from the disk | `slice.file_gone` |
| `404` | Unknown, or another user key's | `slice.unknown_job` |

### `GET /slices/<job>/summary` — its summary

**Answer.** `200` with the [sliced file's summary](sliced-file.md#summary) as the whole JSON
body, its fields in the contract's order. The same refusals as `/file`, `slice.file_gone`
included once the sliced file is deleted. See [examples/sliced-file.json](examples/sliced-file.json).

### `DELETE /slices/<job>/file` — stored, delete your copy

**For:** the front server, once it has written the sliced file and its record in the state
bucket. The slice service deletes its copy at once and keeps the slice job's record until it
expires, two hours after the slice job ended.

| Status | When | Body |
|---|---|---|
| `200` | Deleted, or already deleted (a repeat answers as the first) | `{"job": "<job>", "file": "deleted"}` |
| `409` | The slice job has not finished | `slice.not_ready` |
| `404` | Unknown, or another user key's | `slice.unknown_job` |

A slice job that did not end `done` has no sliced file; the request answers `200` as for one
already deleted. See [examples/slice-http/file-deleted.json](examples/slice-http/file-deleted.json).

## The table of settings

### `GET /settings-table`

**Answer.** `200` with the [table of settings](settings-table.md) whole, for the Orca version
this slice service runs, `gzip`-encoded (`Content-Encoding: gzip`) when the request's
`Accept-Encoding` allows it. The front server passes it to the page as it is, compressed or not
([`GET /api/settings-table`](wizard-front-server.md#get-apisettings-table)). See
[examples/settings-table.json](examples/settings-table.json).

## The log

### `GET /log?after=<n>`

**For:** the front server, which gathers the slice service's log lines about once a minute
and writes them with every other component's into the log
([the front server's details](../front/README-details.md#the-log)). The slice service holds no
credential to store anything itself.

**Request.** `after`, a whole number: the `n` of the last line the front server received from
this process, `0` for none.

**Answer.** `200`:

| Field | Type | Meaning |
|---|---|---|
| `process` | string | A random id the slice service process makes when it starts. When it differs from the one of the previous answer, the process restarted, its numbering began again at 1, and the front server asks again with `after` `0` |
| `lines` | array | The lines after `n`, oldest first, at most 1,000 in one answer; each is one log line as written, with the field `n` added |
| `dropped` | integer | How many lines after `n` were dropped from the buffer before they were asked for; 0 when none. They are still in the process's standard error |
| `more` | boolean | `true` when lines remain after the last one in `lines`; the front server asks again at once |

`n` counts the lines of the process from 1. The slice service keeps the most recent 10,000
lines in memory; an older one is dropped and counted. Every line carries `n`, `time` (UTC,
RFC 3339, to the millisecond), `component` (`"slice"`) and `event`, and whichever of
`user_key` and `job` it concerns; the group is added by the front server
([Reading what happened](../docs/architecture.md#reading-what-happened)). A line never holds a
part's bytes, a payload, a path of the caller's or an environment variable. A failing buffer
never changes any other answer. See [examples/slice-http/log.json](examples/slice-http/log.json).

## Error codes

The codes of this interface, with the status each is answered with. The others, those of the
checks and of a slice, are listed in the slice service's details file
([Error codes](../slice/README-details.md#error-codes)). A code never changes once released.

| Code | Status | When |
|---|---|---|
| `slice.no_user_key` | `400` | A request that needs the user key arrived without it, or with an empty one. A fault of the front server's; the front server answers its page `500` `front.unexpected` |
| `slice.bad_request` | `400`, `404`, `405` | No `Content-Length` on an upload; a path the interface does not offer; a method a path does not take |
| `slice.bad_units` | `400` | An upload whose units label is missing or is neither `mm` nor `in` |
| `slice.bad_plate_configuration` | `400`, `413` | A plate configuration that is not JSON, is multipart, breaks its form, or is over 1,048,576 bytes (`413`) |
| `slice.stopping` | `503` | A new plate configuration while the slice service has been asked to stop; `retryable` true. Never `slice.busy` |
| `slice.output_too_large` | in a `failed` report | The sliced file would be over 50 MB; stage `saving`, `retryable` false; its sentence is the slice service's own, and its remedy fewer instances or a new plate |
| `slice.file_gone` | `410` | The sliced file or its summary after the sliced file was deleted, or a sliced file gone from the disk |
| `slice.not_ready` | `409` | The sliced file, its summary or its deletion asked of a slice job that has not finished |
| `slice.unknown_job` | `404` | A slice job never known, expired, of another process, or of another user key |

## Examples

In [examples/slice-http/](examples/slice-http/):

| File | What it is |
|---|---|
| [part-record.json](examples/slice-http/part-record.json) | The `201` answer to `POST /parts?units=mm` for [examples/parts/bracket.stl](examples/parts/bracket.stl) |
| [slice-accepted.json](examples/slice-http/slice-accepted.json) | The `202` answer to `POST /slices` for [examples/plate-configuration-phase-2.json](examples/plate-configuration-phase-2.json) |
| [slices-list.json](examples/slice-http/slices-list.json) | The answer to `GET /slices` holding one running and one done slice job |
| [events.txt](examples/slice-http/events.txt) | A progress stream from its first event to its final one |
| [file-deleted.json](examples/slice-http/file-deleted.json) | The answer to `DELETE /slices/<job>/file` |
| [log.json](examples/slice-http/log.json) | The answer to `GET /log?after=41` |
| [no-user-key.json](examples/slice-http/no-user-key.json) | The error report for a request without the user key |
| [stopping.json](examples/slice-http/stopping.json) | The error report answered to a submission while the slice service stops |

The answers that carry a data contract whole have their examples beside that contract: the
summary is [examples/sliced-file.json](examples/sliced-file.json), the table of settings
[examples/settings-table.json](examples/settings-table.json), the parts missing
[examples/error-report-parts-missing.json](examples/error-report-parts-missing.json), and the
two over-size refusals
[examples/error-report-part-over-size.json](examples/error-report-part-over-size.json) and
[examples/error-report-plate-configuration-over-size.json](examples/error-report-plate-configuration-over-size.json).
Each component's tests assert their answers against these files.
