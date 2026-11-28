"""The log's writer (README-details.md, "The log"; docs/architecture.md, "Reading what
happened").

Each line is one JSON object: `time` (UTC, RFC 3339, to the millisecond, as the slice
service's lines are), `component`, `event`, then whatever the line concerns. The front
server's own lines (`write`) and the lines it writes for the page's reports (`write_as`,
component `wizard`) go to standard output at once; the lines it gathers from other
components (`gather`: the slice service's, from phase 5 the relay's and the daemons') are
already in their own component's output and are not printed again.

Every line is also kept, and about once a minute (`LOG_FLUSH_S`) everything kept since the
last file is written as one new file of newline-separated JSON in the log bucket, named
`<YYYY>/<MM>/<DD>/<HHMMSS>-<8 hex digits>.jsonl` in UTC. A file is created only if its name
is free and is never written again. A failure to write the log never changes an answer: a
file that cannot be written leaves its lines kept for the next minute (at most
`MAX_PENDING_LINES`, the oldest dropped first and counted in a line of their own), and the
failure is said on standard output only.
"""

import json
import math
import secrets
import threading
from datetime import datetime, timezone

from .buckets import ConditionFailed

#: About once a minute, the gathered lines are written as one file.
LOG_FLUSH_S = 60
#: The most lines kept while the log bucket cannot be written: several hours of a busy
#: front server's lines, far below what would strain its memory.
MAX_PENDING_LINES = 100_000
#: Attempts at a free file name before a minute's file waits for the next minute.
NAME_ATTEMPTS = 5


def _file_suffix():
    """The random part of a file's name, so two files of one second never share one."""
    return secrets.token_hex(4)


def line_text(line):
    """A line as one JSON object, whatever its fields hold: a value JSON cannot hold (an
    object, `NaN` or an infinity) is written as its text, a key that is not text as its
    text, and as a note a value or key with no text (an integer too long for its digits, an
    object whose text fails), a container whose items cannot be read, a value met again
    inside itself, and one nested past `MAX_DEPTH`, so writing a line never fails."""
    return json.dumps(_jsonable(line, 0, set()), allow_nan=False)


#: How deep a value is written before the rest of it is a note.
MAX_DEPTH = 64


def _too_long(value):
    """The note for an integer past the interpreter's limit on digits (4,300 by default),
    which has no text; None for any other integer."""
    try:
        int.__repr__(value)
    except ValueError:
        return f"<int of {value.bit_length()} bits, too long to write>"
    return None


def _text(value):
    """`value` as text, or a note when it has none: an integer too long for its digits, or
    an object whose `__str__` fails."""
    if isinstance(value, int) and (note := _too_long(value)) is not None:
        return note
    try:
        return str(value)
    except Exception:  # noqa: BLE001 - writing a line never fails
        return f"<{type(value).__name__} that cannot be written as text>"


def _jsonable(value, depth, holding):
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, int):  # bool is an int
        return _too_long(value) or value
    if value is None or isinstance(value, str):
        return value
    if not isinstance(value, (dict, list, tuple)):
        return _text(value)
    if id(value) in holding:
        return f"<{type(value).__name__} holding itself>"
    if depth >= MAX_DEPTH:
        return f"<{type(value).__name__} nested past {MAX_DEPTH} levels>"
    holding.add(id(value))
    try:
        if isinstance(value, dict):
            return {k if isinstance(k, str) else _text(k): _jsonable(v, depth + 1, holding)
                    for k, v in value.items()}
        return [_jsonable(v, depth + 1, holding) for v in value]
    except Exception:  # noqa: BLE001 - a container whose items cannot be read; never fails
        return f"<{type(value).__name__} that cannot be read>"
    finally:
        holding.discard(id(value))


def utc_milliseconds(moment):
    stamp = datetime.fromtimestamp(moment, timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{stamp.microsecond // 1000:03d}Z"


class Log:
    def __init__(self, clock, stdout, bucket, *, flush_s=LOG_FLUSH_S,
                 max_pending=MAX_PENDING_LINES, on_flush=None):
        self.clock = clock
        self.stdout = stdout
        self.bucket = bucket
        self.flush_s = flush_s
        self.max_pending = max_pending
        self.on_flush = on_flush
        self._pending = []
        self._dropped = 0
        self._lock = threading.Lock()
        self._flush_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    # Writing lines.

    def write(self, event, /, **fields):
        """One line of the front server's own; gives the line as written."""
        return self.write_as("front", event, **fields)

    def write_as(self, component, event, /, **fields):
        line = {"time": utc_milliseconds(self.clock.now()), "component": component,
                "event": event}
        line.update((k, v) for k, v in fields.items() if k not in line)
        text = line_text(line)
        self._print(text)
        self._keep([text])
        return json.loads(text)

    def gather(self, lines):
        """Keep lines another component wrote (each already a dict with its component)."""
        self._keep([line_text(line) for line in lines])

    def _print(self, text):
        with self._lock:
            try:
                self.stdout.write(text + "\n")
                self.stdout.flush()
            except (OSError, ValueError):
                pass  # a closed standard output never changes an answer

    def _keep(self, texts):
        with self._lock:
            self._pending.extend(texts)
            self._trim()

    def _trim(self):
        """Drop the oldest kept lines past the bound, counting them (the lock held)."""
        over = len(self._pending) - self.max_pending
        if over > 0:
            del self._pending[:over]
            self._dropped += over

    # Writing files.

    def flush(self):
        """Write everything kept since the last file as one new file; gives its name, or
        None when there was nothing to write or the file could not be written."""
        with self._flush_lock:
            with self._lock:
                texts, self._pending = self._pending, []
                dropped, self._dropped = self._dropped, 0
            if not texts and not dropped:
                return None
            note = [json.dumps({
                "time": utc_milliseconds(self.clock.now()), "component": "front",
                "event": "log_lines_dropped", "dropped": dropped})] if dropped else []
            name = self._write_file(note + texts, kept=len(texts))
            if name is None:
                with self._lock:
                    self._pending[:0] = texts
                    self._dropped += dropped
                    self._trim()
            return name

    def _write_file(self, texts, *, kept):
        """Write `texts` as one new file; on failure say so, with `kept`, the lines kept for
        the next minute (the note of dropped lines is not one of them: it is made again)."""
        stamp = datetime.fromtimestamp(self.clock.now(), timezone.utc)
        body = ("\n".join(texts) + "\n").encode()
        failure = None
        for _attempt in range(NAME_ATTEMPTS):
            name = stamp.strftime("%Y/%m/%d/%H%M%S-") + _file_suffix() + ".jsonl"
            try:
                self.bucket.put(name, body, if_absent=True)
                return name
            except ConditionFailed as exc:
                failure = exc
            except Exception as exc:  # noqa: BLE001 - no failure of the log reaches a user
                failure = exc
                break
        self._print(json.dumps({"time": utc_milliseconds(self.clock.now()),
                                "component": "front", "event": "log_bucket_unwritable",
                                "lines_kept": kept, "detail": str(failure)}))
        return None

    # The minute's loop.

    def start(self):
        """Write a file about once a minute until `stop`."""
        self._thread = threading.Thread(target=self._run, name="log-writer", daemon=True)
        self._thread.start()

    def _run(self):
        while not self.clock.sleep(self.flush_s, self._stop):
            self.flush()
            if self.on_flush is not None:
                self.on_flush()

    def stop(self):
        """End the loop and write what has been gathered."""
        self._stop.set()
        self.clock.wake()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self.flush()
