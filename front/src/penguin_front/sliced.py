"""The sliced files in the state bucket: their names, their records, and the sliced file's
details as pages are given them (README-details.md, "The records of a sliced file" and "The
sliced file's details and the sliced file"; contracts/wizard-front-server.md, "The sliced
file's details").

Under `sliced/<user_key>/`, for each slice job:

- `<slice>.gcode.3mf`, the sliced file, byte for byte as the slice service gave it;
- `<slice>.json`, its record (kind `sliced_file`): `format`, `slice`, `group`, `state`, and
  as the state gives them `file`, `size_bytes`, `summary`, `slice_ended_at`, `stored_at` and
  `report`, the final report as passed to pages, without `sliced_file`, which is made afresh
  from the record whenever it is given (its `expires_in_s` counts from that moment).

`state` is `submitted` (the slice job was accepted; the record holds the current group),
`stored` (the file and its summary are stored), `failed` (the sliced file was over the limit
and was not stored) or, from the two-hour rule, `expired`. The file is always written before
the record that names it, so a `stored` record always names a whole file.
"""

from datetime import datetime, timezone

from .buckets import BucketUnavailable, ConditionFailed, NotFound
from .records import UnreadableRecord, read_record, write_record

#: How long a sliced file is kept after its slice ended, before phase 5 the whole rule.
SLICED_FILE_KEPT_S = 7200
#: The largest sliced file the front server stores (*proposed*: the slice service's name and
#: figure): 50 MB.
MAX_SLICED_FILE_BYTES = 50_000_000
KIND = "sliced_file"
PREFIX = "sliced/"


def file_name(user_key, slice_id):
    return f"{PREFIX}{user_key}/{slice_id}.gcode.3mf"


def record_name(user_key, slice_id):
    return f"{PREFIX}{user_key}/{slice_id}.json"


def utc(moment):
    """A moment as RFC 3339 in UTC, to the second."""
    return datetime.fromtimestamp(int(moment), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def moment_of(text):
    """The seconds since the epoch of an RFC 3339 time in UTC to the second."""
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc).timestamp()


def details(record, now):
    """The sliced file's details, as the contract gives them, from a `stored` record."""
    expires = moment_of(record["slice_ended_at"]) + SLICED_FILE_KEPT_S
    return {"slice": record["slice"], "file": record["file"],
            "size_bytes": record["size_bytes"], "summary": record["summary"],
            "slice_ended_at": record["slice_ended_at"], "expires_at": utc(expires),
            "expires_in_s": max(0, int(expires - now))}


def final_report(record, now):
    """The final report a record keeps, as pages are given it: a `stored` record's `done`
    report carrying the sliced file's details; a `failed` record's `failed` report."""
    report = dict(record["report"])
    if record["state"] == "stored":
        report["sliced_file"] = details(record, now)
    return report


def read(bucket, user_key, slice_id, log):
    """The slice job's record, or None when there is none or this front server cannot read
    it. `BucketUnavailable` passes through."""
    try:
        record, _marker = read_record(bucket, record_name(user_key, slice_id), KIND, log)
    except (NotFound, UnreadableRecord):
        return None
    return record


def note_submitted(bucket, user_key, slice_id, group, now):
    """Write the record of a slice job just accepted, holding its group, unless the slice job
    already has a record (a repeat; a stored file's record is never replaced by this). Gives
    None, or the reason the record could not be written."""
    record = {"slice": slice_id, "group": group, "state": "submitted",
              "submitted_at": utc(now)}
    try:
        write_record(bucket, record_name(user_key, slice_id), KIND, record, if_absent=True)
    except ConditionFailed:
        return None
    except BucketUnavailable as exc:
        return str(exc)
    return None
