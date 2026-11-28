"""The log's gathering of the slice service's lines (README-details.md, "The log";
contracts/slice-http-interface.md, "`GET /log?after=<n>`").

The front server is the only thing that writes to the log bucket, so it gathers the slice
service's lines for it: about once a minute (`LOG_GATHER_S`) it asks `GET /log?after=<n>`,
passing back the last `n` it received, and asks again at once while the answer says `more`.
The lines it receives are kept by the log (`Log.gather`) for the minute's file, each with the
group added: the group noted beside its slice job, by the following while the slice job is
followed, or else in the slice job's record in the state bucket. A line whose slice job
cannot be placed keeps no group.

- **A changed `process`** (the slice service restarted, its numbering begun again at 1):
  asked again at once from `0`, with a line `slice_log_process_changed`.
- **`dropped` not 0:** a line of the front server's own, `slice_log_lines_dropped`.
- **Where it stopped** (the process and the last `n`) is kept in the state bucket
  (`CURSOR`), so that a front server started later goes on from there and gathers no line
  twice. It is written after each gathering that moved it; the lines gathered are written
  to the log bucket within the minute, so a crash between the two loses at most that
  minute's lines, which stay in the slice service's own output.
- **A slice service that does not answer**, or answers with what is not the log, is said
  once (`slice_log_unavailable`) until it answers again; nothing is gathered meanwhile, and
  the slice service keeps its lines until they are asked for or dropped.
"""

import re
import threading
from collections import OrderedDict

from . import sliced
from .buckets import BadName, BucketUnavailable, NotFound
from .every import Every
from .records import UnreadableRecord, read_record, write_record
from .slice_client import SliceUnreachable, json_object

#: About once a minute the slice service's lines are gathered.
LOG_GATHER_S = 60
#: Where the gathering stopped, in the state bucket.
CURSOR = "log-cursor/slice.json"
CURSOR_KIND = "log_cursor"
#: The most answers one gathering asks for (*proposed*): at 1,000 lines an answer, ten times
#: the 10,000 lines the slice service keeps. The rest waits for the next minute.
MAX_ASKS = 100
#: The groups remembered by slice job, so that a record is read once (*proposed*).
GROUPS_KEPT = 10_000
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class _NotTheLog(Exception):
    """The slice service did not answer with its log."""


class Gatherer:
    def __init__(self, *, clock, slice_client, bucket, follower, log):
        self._slice = slice_client
        self._bucket = bucket
        self._follower = follower
        self._log = log
        self._lock = threading.Lock()
        self._process = None
        self._after = 0
        self._cursor_read = False
        self._saved = None
        self._unavailable = False
        self._groups = OrderedDict()
        self.loop = Every(clock, LOG_GATHER_S, self.gather_once, log, "gather")

    def start(self):
        self.loop.start()

    def stop(self):
        self.loop.stop()

    def gather_once(self):
        """Gather every line the slice service holds after the last one received."""
        with self._lock:
            if not self._read_cursor():
                return
            try:
                self._gather()
            finally:
                self._save_cursor()

    def _gather(self):
        lookups = {}
        for _ask in range(MAX_ASKS):
            try:
                process, lines, dropped, more = self._ask(self._after)
            except _NotTheLog as exc:
                if not self._unavailable:
                    self._log.write("slice_log_unavailable", why=str(exc), after=self._after)
                self._unavailable = True
                return
            self._unavailable = False
            if process != self._process:
                previous, self._process = self._process, process
                if previous is not None:
                    self._log.write("slice_log_process_changed", previous=previous,
                                    process=process, after=self._after)
                    if self._after != 0:
                        self._after = 0
                        continue
            if dropped:
                self._log.write("slice_log_lines_dropped", process=process,
                                after=self._after, dropped=dropped)
            # Lines are numbered from 1 with none skipped but the dropped, so no line of this
            # answer can carry a number past `highest`.
            kept, unreadable = [], 0
            highest = self._after + dropped + len(lines)
            for line in lines:
                n = line.get("n") if isinstance(line, dict) else None
                if not isinstance(n, int) or isinstance(n, bool) or n <= self._after \
                        or n > highest:
                    unreadable += 1
                    continue
                kept.append(self._placed(line, lookups))
                self._after = n
            if unreadable:
                self._log.write("slice_log_lines_unreadable", process=process,
                                count=unreadable)
            self._log.gather(kept)
            if not more or not lines:
                return

    def _ask(self, after):
        try:
            raw = self._slice.send("GET", "/log", params={"after": str(after)})
        except SliceUnreachable as exc:
            raise _NotTheLog(str(exc)) from None
        if raw.status != 200:
            raise _NotTheLog(f"GET /log answered {raw.status}")
        answer = json_object(raw.body)
        if answer is None:
            raise _NotTheLog("GET /log answered with what is not the log")
        process, lines = answer.get("process"), answer.get("lines")
        dropped, more = answer.get("dropped"), answer.get("more")
        if not isinstance(process, str) or not process or not isinstance(lines, list) \
                or not isinstance(dropped, int) or isinstance(dropped, bool) or dropped < 0 \
                or not isinstance(more, bool):
            raise _NotTheLog("GET /log answered with what is not the log: "
                             f"{raw.body[:200]!r}")
        return process, lines, dropped, more

    # Placing a line in its group.

    def _placed(self, line, lookups):
        line = dict(line)
        line.pop("group", None)
        # Every gathered line is the slice service's, whatever component it names.
        line["component"] = "slice"
        group = self._group(line.get("user_key"), line.get("job"), lookups)
        if group is not None:
            line["group"] = group
        return line

    def _group(self, user_key, job, lookups):
        if not isinstance(job, str) or not _ID.fullmatch(job) or not isinstance(user_key, str):
            return None
        key = (user_key, job)
        followed, group = self._follower.group_of(user_key, job)
        if followed:
            return group
        if key in self._groups:
            return self._groups[key]
        if key not in lookups:
            lookups[key] = self._recorded_group(user_key, job)
            if lookups[key] is not None:
                self._groups[key] = lookups[key]
                while len(self._groups) > GROUPS_KEPT:
                    self._groups.popitem(last=False)
        return lookups[key]

    def _recorded_group(self, user_key, job):
        try:
            sliced.check_user_key(user_key)
            record = sliced.read(self._bucket, user_key, job, self._log)
        except (BadName, BucketUnavailable):
            return None
        group = record.get("group") if record is not None else None
        return group if isinstance(group, str) else None

    # Where the gathering stopped.

    def _read_cursor(self):
        """Read where an earlier front server stopped, once; False when the state bucket
        does not answer, so that this minute gathers nothing rather than lines again."""
        if self._cursor_read:
            return True
        try:
            record, _marker = read_record(self._bucket, CURSOR, CURSOR_KIND, self._log)
        except (NotFound, UnreadableRecord):
            record = None
        except BucketUnavailable as exc:
            self._log.write("slice_log_cursor_unreadable", detail=str(exc))
            return False
        self._cursor_read = True
        if record is not None:
            process, after = record.get("process"), record.get("after")
            if isinstance(process, str) and isinstance(after, int) \
                    and not isinstance(after, bool) and after >= 0:
                self._process, self._after = process, after
                self._saved = (process, after)
        return True

    def _save_cursor(self):
        now = (self._process, self._after)
        if self._process is None or now == self._saved:
            return
        try:
            write_record(self._bucket, CURSOR, CURSOR_KIND,
                         {"process": self._process, "after": self._after})
        except BucketUnavailable as exc:
            self._log.write("slice_log_cursor_unwritten", process=self._process,
                            after=self._after, detail=str(exc))
            return
        self._saved = now
