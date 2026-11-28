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
from .errors import error_report
from .records import UnreadableRecord, read_record, write_record

#: How long a sliced file is kept after its slice ended, before phase 5 the whole rule.
SLICED_FILE_KEPT_S = 7200
#: How long an `expired` record is kept after its file was deleted, so that asking about its
#: slice job answers "expired" rather than unknown (*proposed*).
EXPIRED_RECORD_KEPT_S = 86_400
#: How long a `submitted` record is kept after `submitted_at` (*proposed*): two hours, far
#: longer than a slice job can wait and run, plus the two hours the slice service remembers
#: a slice job after it ends; past them nobody can learn more of its slice job.
SUBMITTED_RECORD_KEPT_S = 2 * 7200
#: How long a `failed` record (a sliced file over the limit) is kept after its slice ended
#: (*proposed*): as long as a stored file and its `expired` record together.
FAILED_RECORD_KEPT_S = SLICED_FILE_KEPT_S + EXPIRED_RECORD_KEPT_S
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


def expires(record):
    """The moment a `stored` record's sliced file falls due: two hours after its slice
    ended (before phase 5, the whole rule)."""
    return moment_of(record["slice_ended_at"]) + SLICED_FILE_KEPT_S


def due(record, now):
    """Whether a `stored` record's sliced file is due at `now`: refused, and deleted."""
    return now >= expires(record)


def expired_report(record):
    """What pages see of a sliced file that has expired: the `done` report its record keeps,
    turned `failed`, with `sequence` one more and the error `front.sliced_file_expired`."""
    report = dict(record["report"], state="failed",
                  sequence=record["report"].get("sequence", 0) + 1,
                  error=error_report("front.sliced_file_expired",
                                     f"slice {record['slice']} ended at "
                                     f"{record.get('slice_ended_at')}; its sliced file was "
                                     f"kept {SLICED_FILE_KEPT_S} s"))
    report.pop("sliced_file", None)
    return report


def file_present(bucket, user_key, slice_id):
    """Whether the sliced file is in the state bucket. `BucketUnavailable` passes through."""
    name = file_name(user_key, slice_id)
    return any(entry.name == name for entry in bucket.list(name))


def expire(bucket, user_key, record, now, log, *, by, why):
    """Delete a sliced file that is due or gone, then turn its record `expired` (the file
    first, so that a record never says `expired` beside a file still there), writing the
    line `sliced_file_expired`. `BucketUnavailable` passes through, with the record as it
    was; the sweep tries again."""
    slice_id = record["slice"]
    bucket.delete(file_name(user_key, slice_id))
    write_record(bucket, record_name(user_key, slice_id), KIND,
                 dict(record, state="expired", expired_at=utc(now)))
    log.write("sliced_file_expired", user_key=user_key, group=record.get("group"),
              slice=slice_id, by=by, why=why, slice_ended_at=record.get("slice_ended_at"),
              late_s=max(0, int(now - expires(record))))


def details(record, now):
    """The sliced file's details, as the contract gives them, from a `stored` record."""
    moment = expires(record)
    return {"slice": record["slice"], "file": record["file"],
            "size_bytes": record["size_bytes"], "summary": record["summary"],
            "slice_ended_at": record["slice_ended_at"], "expires_at": utc(moment),
            "expires_in_s": max(0, int(moment - now))}


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
