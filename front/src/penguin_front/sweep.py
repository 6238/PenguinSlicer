"""The sweep of the sliced files (README-details.md, "Two hours, the sweep, and the
backstop").

Once at start and then every `SWEEP_INTERVAL_S` on the front server's clock, the sweep lists
`sliced/` through the bucket interface, reads each record, and:

- deletes a sliced file that is due, turning its record `expired` (`sliced.expire`, the
  line `sliced_file_expired` with `by` `sweep`), so that a file nobody asks for again is
  still gone on time; a file somebody asks for is refused exactly on time by the request;
- deletes a record `expired` for longer than `EXPIRED_RECORD_KEPT_S`, a `submitted` one
  older than `SUBMITTED_RECORD_KEPT_S` (its slice job never ended `done` and can no longer
  be known), and a `failed` one older than `FAILED_RECORD_KEPT_S` from its slice's end, each
  with any sliced file beside it (a front server stopped between storing the file and
  writing its `stored` record leaves the file beside the `submitted` record), with the line
  `sliced_record_deleted` (`state`, `age_s`);
- deletes a sliced file that has no record two hours after it was stored (its `submitted`
  record was never written, or a following started by asking found none), with the line
  `sliced_file_deleted`.

A slice job the front server follows is left alone: its storing may be under way. A record
this front server cannot read (a newer format) is left alone, as is any name the front server
does not make. A failure on one file, whether the bucket refuses or the record has a field
missing or malformed, writes `sweep_item_failed` (with the record's group once the record is
read, else none: a sweep has no current group) and the sweep goes on; a malformed record and
its file are left as they are, and fail again at every sweep; a
listing that fails writes `sweep_failed`. Each sweep ends with the line `sweep` and its
counts.
"""

from . import sliced
from .buckets import BucketUnavailable
from .every import Every

#: How often the sweep runs (*proposed*): it bounds only how long past its two hours an
#: unasked-for sliced file can exist.
SWEEP_INTERVAL_S = 600

_RECORD = ".json"
_FILE = ".gcode.3mf"


class Sweeper:
    def __init__(self, *, clock, bucket, follower, log, interval_s=SWEEP_INTERVAL_S):
        self._clock = clock
        self._bucket = bucket
        self._follower = follower
        self._log = log
        self.every = Every(clock, interval_s, self.sweep, log, "sweep")

    def start(self):
        self.every.start()

    def stop(self):
        self.every.stop()

    def sweep(self):
        """One sweep; gives its counts, or None when the listing failed."""
        now = self._clock.now()
        try:
            entries = self._bucket.list(sliced.PREFIX)
        except BucketUnavailable as exc:
            self._log.write("sweep_failed", why=str(exc))
            return None
        records, files = {}, {}
        for entry in entries:
            parts = entry.name[len(sliced.PREFIX):].split("/")
            if len(parts) != 2:
                continue
            user_key, leaf = parts
            for suffix, found in ((_RECORD, records), (_FILE, files)):
                if leaf.endswith(suffix) and len(leaf) > len(suffix):
                    found[(user_key, leaf[:-len(suffix)])] = entry
        followed = self._follower.followed()
        counts = {"checked": 0, "files_expired": 0, "records_deleted": 0, "files_deleted": 0,
                  "failed": 0}
        for (user_key, job) in sorted(set(records) | set(files)):
            if job in followed:
                continue
            counts["checked"] += 1
            seen = {}  # the record's group, once the record is read
            try:
                if (user_key, job) in records:
                    outcome = self._record(user_key, job, now, seen)
                else:
                    outcome = self._lone_file(user_key, job, files[(user_key, job)], now)
            except BucketUnavailable as exc:
                counts["failed"] += 1
                self._log.write("sweep_item_failed", user_key=user_key,
                                group=seen.get("group"), slice=job, why=str(exc))
                continue
            except (KeyError, ValueError, TypeError) as exc:
                # A record of a readable format with a field missing or malformed: it is
                # left as it is, and written at every sweep until somebody looks.
                counts["failed"] += 1
                self._log.write("sweep_item_failed", user_key=user_key,
                                group=seen.get("group"), slice=job,
                                why=f"the record is malformed: {type(exc).__name__}: {exc}")
                continue
            if outcome is not None:
                counts[outcome] += 1
        self._log.write("sweep", **counts)
        return counts

    def _record(self, user_key, job, now, seen):
        record = sliced.read(self._bucket, user_key, job, self._log)
        state = record.get("state") if record is not None else None
        seen["group"] = record.get("group") if record is not None else None
        if state == "stored":
            if sliced.due(record, now):
                sliced.expire(self._bucket, user_key, record, now, self._log, by="sweep",
                              why="due")
                return "files_expired"
            return None
        since = {"expired": ("expired_at", sliced.EXPIRED_RECORD_KEPT_S),
                 "submitted": ("submitted_at", sliced.SUBMITTED_RECORD_KEPT_S),
                 "failed": ("slice_ended_at", sliced.FAILED_RECORD_KEPT_S)}.get(state)
        if since is None:
            return None
        field, kept_s = since
        age = now - sliced.moment_of(record[field])
        if age < kept_s:
            return None
        self._bucket.delete(sliced.file_name(user_key, job))
        self._bucket.delete(sliced.record_name(user_key, job))
        self._log.write("sliced_record_deleted", user_key=user_key, group=record.get("group"),
                        slice=job, state=state, age_s=int(age))
        return "records_deleted"

    def _lone_file(self, user_key, job, entry, now):
        if now - entry.stored_at < sliced.SLICED_FILE_KEPT_S:
            return None
        self._bucket.delete(entry.name)
        self._log.write("sliced_file_deleted", user_key=user_key, slice=job,
                        why="no record", size_bytes=entry.size)
        return "files_deleted"
