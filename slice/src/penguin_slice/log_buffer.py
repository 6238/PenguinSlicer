"""The slice service's log lines, kept for the front server to collect
(contracts/slice-http-interface.md, GET /log?after=<n>).

The slice service holds no credential to store its own log, so the front server fetches its
new lines about once a minute and writes them with every other component's. A LogBuffer is
the log sink of one slice service process: every line it is given is numbered from 1
(`n`), stamped with the wall clock's time (UTC, RFC 3339, to the millisecond) and the
component (`"slice"`), made JSON-safe (a value JSON cannot hold is kept as its words), kept
among the most recent LOG_BUFFER_LINES, and passed on to its sink (stderr under serve), so a
line dropped from a full buffer is still in the process's output. `process` is a random id
made at start: a new process numbers from 1 again under a new id.

The buffer is called through jobs.SafeLog, so a buffer or a sink that fails never changes an
answer or a slice job.
"""
import collections
import itertools
import json
import secrets
import threading
import time
from datetime import datetime, timezone

COMPONENT = "slice"
LOG_BUFFER_LINES = 10_000     # the most recent lines kept in memory (proposed)
LOG_ANSWER_LINES = 1_000      # lines in one answer of GET /log, at most (the contract's)
_STAMPS = ("n", "time", "component")
# A line made JSON-safe: a value JSON cannot hold becomes its words. Bound once, so that the
# buffer depends on nothing a caller may replace.
_ENCODE = json.JSONEncoder(default=str).encode
_DECODE = json.JSONDecoder().decode


def rfc3339_ms(seconds):
    """A moment of the wall clock as a log line carries it: UTC, to the millisecond."""
    moment = datetime.fromtimestamp(round(seconds, 3), timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


class LogBuffer:
    """`buffer(entry)` keeps one log line; `buffer.read(after)` answers GET /log."""

    def __init__(self, sink=None, capacity=LOG_BUFFER_LINES, clock=time.time, process=None):
        self._sink = sink or (lambda line: None)
        self._clock = clock
        self._lines = collections.deque(maxlen=capacity)
        self._last = 0
        self._lock = threading.Lock()
        self.process = process or "p" + secrets.token_hex(4)

    def __call__(self, entry):
        with self._lock:
            self._last += 1
            line = {"n": self._last, "time": rfc3339_ms(self._clock()), "component": COMPONENT}
            line.update((key, value) for key, value in entry.items() if key not in _STAMPS)
            line = _DECODE(_ENCODE(line))
            self._lines.append(line)
            self._sink(line)          # in the lock, so stderr has the lines in their order

    def read(self, after, limit=LOG_ANSWER_LINES):
        """{process, lines, dropped, more}: the lines numbered after `after`, oldest first, at
        most `limit`; how many of those were dropped from the buffer; whether more remain."""
        with self._lock:
            oldest = self._lines[0]["n"] if self._lines else self._last + 1
            dropped = max(0, oldest - 1 - after)          # lines after `after` no longer kept
            skip = max(after + 1, oldest) - oldest
            lines = list(itertools.islice(self._lines, skip, skip + limit))
            more = bool(lines) and lines[-1]["n"] < self._last
            return {"process": self.process, "lines": lines, "dropped": dropped, "more": more}
