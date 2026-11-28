"""The records the front server keeps in the state bucket, each with its format number.

Every record carries `format`, a whole number counting from 1 (contracts/README.md,
"Rules"). `write_record` is the one way the front server writes a record, and it always
writes the front server's own format for that kind of record. `read_record` reads every
format up to the front server's own and refuses any other (one newer than it knows, a
missing or malformed number, a file that is not a JSON object) with `UnreadableRecord`,
writing one log line that says so, so that a record written by a newer front server is never
misread by an older one.
"""

import json

#: The front server's format of each kind of record it writes. A change that a front server
#: of the previous version could not read raises a number; a field added with a meaning
#: when it is left out does not.
FORMATS = {
    # A group's configuration document (contracts/configuration.md).
    "configuration": 1,
    # A sliced file's record, beside the sliced file (README-details.md, "The records of a
    # sliced file").
    "sliced_file": 1,
    # Where the gathering of the slice service's log lines stopped (README-details.md, "The
    # log"): the slice service process and the last line's number.
    "log_cursor": 1,
}


class UnreadableRecord(Exception):
    """A record whose format this front server does not read."""


def record_bytes(kind, record):
    """The bytes `write_record` writes for `record`: its JSON, with the front server's format
    for `kind` first. One record always gives the same bytes, so a write repeated with the
    same record can be told by comparing them."""
    stored = {"format": FORMATS[kind], **{k: v for k, v in record.items() if k != "format"}}
    return json.dumps(stored).encode()


def write_record(bucket, name, kind, record, **condition):
    """Write `record` (a dict) as JSON under `name` with the front server's format for
    `kind`; `condition` is `if_marker=` or `if_absent=`, passed to the bucket. Gives the
    record's new marker."""
    return bucket.put(name, record_bytes(kind, record), **condition)


def read_record(bucket, name, kind, log):
    """The record under `name` and its marker, if its format is one this front server
    reads; otherwise `UnreadableRecord`, with a `record_unreadable` line in `log`. The
    bucket's `NotFound` and `BucketUnavailable` pass through to the caller."""
    body, marker = bucket.get(name)
    newest = FORMATS[kind]
    found, why = None, None
    try:
        record = json.loads(body)
    except ValueError as exc:
        record, why = None, f"not JSON: {exc}"
    except RecursionError:  # Python's reader raises it, not ValueError, past its depth
        record, why = None, "not JSON: nested deeper than the reader goes"
    if why is None and not isinstance(record, dict):
        why = "not a JSON object"
    if why is None:
        found = record.get("format")
        if not isinstance(found, int) or isinstance(found, bool) or found < 1:
            why = "no format number"
        elif found > newest:
            why = "a format newer than this front server reads"
    if why is not None:
        log.write("record_unreadable", record=name, kind=kind, format=found,
                  reads_up_to=newest, why=why)
        raise UnreadableRecord(f"{name}: {why}")
    return record, marker
