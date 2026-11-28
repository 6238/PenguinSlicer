"""Following every slice job, and storing its sliced file and summary (README-details.md,
"Following slice jobs and storing sliced files"; the guide's "The front server follows every
slice job itself").

The front server follows every unfinished slice job itself, page or no page: for each it
holds the slice service's progress stream (`GET /slices/<job>/events`, with the slice job's
user key), on a thread of its own. Every page following that slice job is fed from that one
stream (`subscribe`), so three pages on one slice job cost the slice service one connection.

- **Each report once.** A report whose `sequence` has already been passed on is dropped (the
  slice service repeats its latest report every 15 seconds on a quiet stream).
- **A stream that closes** before a final report, or a slice service that does not answer,
  is tried again after a wait that doubles from `FIRST_WAIT_S` to `LONGEST_WAIT_S`, on the
  front server's clock. A slice service that answers the slice job unknown ends the
  following: the pages' streams are closed with no final report.
- **When a slice ends `done`**, that report is held back from every page while the front
  server fetches the summary and the sliced file, writes the file and then its record in the
  state bucket, and tells the slice service they are stored (`DELETE /slices/<job>/file`);
  only then does every page get the `done` report, carrying `sliced_file`. A step that fails
  (the slice service not answering, the file cut partway, the state bucket not answering) is
  tried again after the same growing waits, from that step: no record is written before its
  file, and the slice service is never told before the record is written.
- **Over `max_file_bytes`** (`Content-Length`, or the bytes counted as they pass, in case it
  lies) the sliced file is not stored: the slice service is still told to delete its copy,
  the record is written `failed`, and pages get the `done` report as `failed`, with the same
  `sequence` and the error `front.sliced_file_too_large`.

Each change of a slice job's state or stage, each wait, each storing and each end writes one
log line, with the user key, the current group and the slice job.
"""

import json
import threading
import traceback
from dataclasses import dataclass, field

import httpx

from . import sliced
from .buckets import CHUNK_BYTES, BucketUnavailable
from .errors import error_report
from .records import write_record
from .slice_client import SliceUnreachable, json_object, slice_report, user_key_header

FINAL_STATES = ("done", "failed", "cancelled")
#: The first wait before a stream is opened again or a step of storing is tried again
#: (*proposed*); each further wait doubles, up to `LONGEST_WAIT_S`.
FIRST_WAIT_S = 1
LONGEST_WAIT_S = 30


class _Waits:
    def __init__(self):
        self._next = FIRST_WAIT_S

    def take(self):
        wait, self._next = self._next, min(self._next * 2, LONGEST_WAIT_S)
        return wait

    def reset(self):
        self._next = FIRST_WAIT_S


class _Ended(Exception):
    """The following of a slice job ends here, with no final report for the pages."""


class _Again(Exception):
    """A step of storing failed and is tried again after a wait."""

    def __init__(self, step, why):
        super().__init__(f"{step}: {why}")
        self.step = step
        self.why = why


class _TooLarge(Exception):
    def __init__(self, count):
        super().__init__(count)
        self.count = count


@dataclass
class _Followed:
    user_key: str
    job: str
    group: str | None
    #: The highest `sequence` of the slice service's reports passed on.
    last_sequence: int = 0
    #: The latest report as pages see it.
    latest: dict | None = None
    subscribers: list = field(default_factory=list)
    closed: bool = False


@dataclass
class _Storing:
    """How far the storing of one slice job's sliced file has got."""

    done: dict
    ended_at: str
    checked: bool = False
    summary: dict | None = None
    file_stored: bool = False
    size_bytes: int | None = None
    too_large: int | None = None
    #: The record once written, False before.
    recorded: dict | bool = False


class Subscription:
    """A page's place on a followed slice job: `latest`, the latest report as pages see it
    when the page subscribed (None before the first), and `cancel()`."""

    def __init__(self, latest, cancel):
        self.latest = latest
        self.cancel = cancel


class Follower:
    def __init__(self, *, clock, slice_client, bucket, log,
                 max_file_bytes=sliced.MAX_SLICED_FILE_BYTES):
        self._clock = clock
        self._slice = slice_client
        self._bucket = bucket
        self._log = log
        self._max_file_bytes = max_file_bytes
        self._lock = threading.Lock()
        self._jobs = {}
        self._threads = []
        self._stopping = threading.Event()

    # What the rest of the front server asks of it.

    def follow(self, user_key, job, group):
        """Follow `job` of `user_key`, noting `group` beside it, unless it is followed
        already. Gives whether a following started now."""
        with self._lock:
            if job in self._jobs or self._stopping.is_set():
                return False
            followed = _Followed(user_key, job, group)
            self._jobs[job] = followed
            thread = threading.Thread(target=self._run, args=(followed,),
                                      name=f"follow-{job}", daemon=True)
            self._threads.append(thread)
        thread.start()
        return True

    def followed(self):
        """The slice jobs followed now, by id."""
        with self._lock:
            return set(self._jobs)

    def subscribe(self, user_key, job, deliver):
        """Give every report pages are to see of `job` to `deliver(report)`, then
        `deliver(None)` when the following ends; None when `job` is not followed for
        `user_key`. `deliver` is called on the following's thread and must not block."""
        with self._lock:
            followed = self._jobs.get(job)
            if followed is None or followed.user_key != user_key:
                return None
            followed.subscribers.append(deliver)

            def cancel():
                with self._lock:
                    if deliver in followed.subscribers:
                        followed.subscribers.remove(deliver)

            return Subscription(followed.latest, cancel)

    def latest(self, user_key, job):
        """The latest report pages are to see of `job`, while it is followed for
        `user_key`; otherwise None."""
        with self._lock:
            followed = self._jobs.get(job)
            if followed is None or followed.user_key != user_key:
                return None
            return followed.latest

    def as_pages_see(self, user_key, job, report):
        """`report`, a report of the slice service's about `job`, as pages are to see it: a
        `done` report is held back until its sliced file is stored, and is then the stored
        `done` report with `sliced_file`; until then it is the latest report before it."""
        latest = self.latest(user_key, job)
        if report.get("state") != "done":
            if latest is not None and latest.get("sequence", 0) > report.get("sequence", 0):
                return latest
            return report
        try:
            record = sliced.read(self._bucket, user_key, job, self._log)
        except BucketUnavailable:
            record = None
        if record is not None and record.get("state") in ("stored", "failed"):
            return sliced.final_report(record, self._clock.now())
        if latest is not None and latest.get("state") not in FINAL_STATES:
            return latest
        return held_back(report)

    def stop(self):
        """Follow nothing more: every following ends at its next wait or when its stream
        next closes. A slice job is never touched; a front server started later follows it
        again."""
        self._stopping.set()
        self._clock.wake()

    def join(self):
        """Wait for every following's thread to end (after `stop`)."""
        with self._lock:
            threads = list(self._threads)
        for thread in threads:
            thread.join()

    # Following one slice job.

    def _run(self, followed):
        self._line("slice_followed", followed)
        waits = _Waits()
        try:
            while True:
                try:
                    if self._read_stream(followed, waits):
                        return
                    why = "the stream closed before a final report"
                except _Ended:
                    return
                except _Again as exc:
                    why = str(exc)
                except (SliceUnreachable, httpx.TransportError) as exc:
                    why = f"{type(exc).__name__}: {exc}"
                except Exception as exc:  # a fault of the front server's: logged, tried again
                    why = f"{type(exc).__name__}: {exc}"
                    self._line("following_failed", followed,
                               trace="".join(traceback.format_exception(exc)))
                if self._stopping.is_set():
                    return
                wait = waits.take()
                self._line("slice_stream_reopening", followed, why=why, wait_s=wait)
                if self._sleep(wait):
                    return
        finally:
            self._close(followed)

    def _read_stream(self, followed, waits):
        """Read the slice job's progress stream once; True when the following has ended."""
        with self._slice.stream(f"/slices/{followed.job}/events",
                                user_key_header(followed.user_key)) as answer:
            if answer.status_code != 200:
                self._refused(followed, answer.status_code, answer.read(), "the stream")
            waits.reset()
            for report in reports_of(answer.iter_lines()):
                if self._stopping.is_set():
                    return True
                sequence = report.get("sequence")
                if not isinstance(sequence, int) or isinstance(sequence, bool):
                    raise ValueError(f"a progress report without a sequence: {report!r:.200}")
                if sequence <= followed.last_sequence:
                    continue
                followed.last_sequence = sequence
                if report.get("state") == "done":
                    self._store(followed, report)
                    return True
                self._publish(followed, report)
                if report.get("state") in FINAL_STATES:
                    error = report.get("error")
                    self._line("slice_ended", followed, state=report["state"],
                               cancel_reason=report.get("cancel_reason"),
                               code=error.get("code") if isinstance(error, dict) else None)
                    return True
        return False

    def _refused(self, followed, status, body, what):
        """A failure answer of the slice service's about the slice job: unknown or its file
        gone ends the following; any other is tried again."""
        report = slice_report(body)
        code = report["code"] if report is not None else None
        if code == "slice.unknown_job":
            self._line("slice_unknown", followed, detail=f"{what}: answered {status} {code}")
            raise _Ended()
        if code == "slice.file_gone":
            self._line("sliced_file_lost", followed, detail=f"{what}: answered {status} {code}")
            raise _Ended()
        raise _Again(what, f"answered {status} {code or 'with no report of the slice service'}")

    # Storing the sliced file and its summary.

    def _store(self, followed, done):
        storing = _Storing(done, sliced.utc(self._clock.now()))
        waits = _Waits()
        while True:
            try:
                self._store_steps(followed, storing)
                return
            except _Again as again:
                wait = waits.take()
                self._line("sliced_file_retry", followed, step=again.step, why=again.why,
                           wait_s=wait)
                if self._sleep(wait):
                    return

    def _store_steps(self, followed, storing):
        """Each step not yet done, in order; `_Again` from the step that failed."""
        job, user_key = followed.job, followed.user_key
        if not storing.checked:
            try:
                record = sliced.read(self._bucket, user_key, job, self._log)
            except BucketUnavailable as exc:
                raise _Again("reading the record", str(exc)) from None
            storing.checked = True
            if record is not None and record.get("state") in ("stored", "failed"):
                # Stored already, by this front server before a restart or an earlier one.
                self._publish(followed, sliced.final_report(record, self._clock.now()))
                return
        if storing.summary is None:
            storing.summary = self._summary(followed)
        if not storing.file_stored and storing.too_large is None:
            self._fetch_file(followed, storing)
        if storing.too_large is not None:
            self._refuse_too_large(followed, storing)
            return
        if storing.recorded is False:
            storing.recorded = self._write(followed, "stored", {
                "file": storing.summary.get("file") or f"{job}.gcode.3mf",
                "size_bytes": storing.size_bytes, "summary": storing.summary,
                "slice_ended_at": storing.ended_at,
                "stored_at": sliced.utc(self._clock.now()), "report": storing.done})
        self._delete(followed)
        self._line("sliced_file_stored", followed, size_bytes=storing.size_bytes,
                   stored_after_s=int(self._clock.now() - sliced.moment_of(storing.ended_at)))
        self._publish(followed, sliced.final_report(storing.recorded, self._clock.now()))

    def _summary(self, followed):
        path = f"/slices/{followed.job}/summary"
        try:
            raw = self._slice.send("GET", path, headers=user_key_header(followed.user_key))
        except SliceUnreachable as exc:
            raise _Again("fetching the summary", str(exc)) from None
        if raw.status != 200:
            self._refused(followed, raw.status, raw.body, "fetching the summary")
        summary = json_object(raw.body)
        if summary is None:
            raise _Again("fetching the summary", "the summary is not a JSON object")
        return summary

    def _fetch_file(self, followed, storing):
        path = f"/slices/{followed.job}/file"
        try:
            with self._slice.stream(path, user_key_header(followed.user_key)) as answer:
                if answer.status_code != 200:
                    self._refused(followed, answer.status_code, answer.read(),
                                  "fetching the sliced file")
                stated = answer.headers.get("Content-Length", "")
                if stated.isdigit() and int(stated) > self._max_file_bytes:
                    storing.too_large = int(stated)
                    return
                counted = _Counted(answer.iter_raw(CHUNK_BYTES), self._max_file_bytes)
                self._bucket.put(sliced.file_name(followed.user_key, followed.job), counted)
        except _TooLarge as exc:
            storing.too_large = exc.count
            return
        except (SliceUnreachable, httpx.TransportError) as exc:
            raise _Again("fetching the sliced file", f"{type(exc).__name__}: {exc}") from None
        except BucketUnavailable as exc:
            raise _Again("storing the sliced file", str(exc)) from None
        storing.size_bytes = counted.count
        storing.file_stored = True

    def _refuse_too_large(self, followed, storing):
        """Tell the slice service to delete its copy, then write the record `failed`; a step
        tried again repeats the delete, which the slice service answers as the first."""
        self._delete(followed)
        limit = self._max_file_bytes
        failed = dict(storing.done, state="failed", error=error_report(
            "front.sliced_file_too_large",
            f"the sliced file is at least {storing.too_large:,} bytes, over the limit of "
            f"{limit:,}"))
        self._write(followed, "failed", {"slice_ended_at": storing.ended_at, "report": failed})
        self._line("sliced_file_too_large", followed, size_bytes=storing.too_large,
                   limit_bytes=limit)
        self._publish(followed, failed)

    def _write(self, followed, state, fields):
        """Write the slice job's record in `state`; gives the record written."""
        record = {"slice": followed.job, "group": followed.group, "state": state, **fields}
        try:
            write_record(self._bucket, sliced.record_name(followed.user_key, followed.job),
                         sliced.KIND, record)
        except BucketUnavailable as exc:
            raise _Again("writing the record", str(exc)) from None
        return record

    def _delete(self, followed):
        path = f"/slices/{followed.job}/file"
        try:
            raw = self._slice.send("DELETE", path, headers=user_key_header(followed.user_key))
        except SliceUnreachable as exc:
            raise _Again("telling the slice service the file is stored", str(exc)) from None
        report = slice_report(raw.body) if raw.status != 200 else None
        if raw.status == 200 or (report is not None and report["code"] == "slice.unknown_job"):
            return  # deleted; or the slice service no longer knows it, and holds no copy
        raise _Again("telling the slice service the file is stored",
                     f"answered {raw.status} {report['code'] if report else 'with no report'}")

    # Passing reports to pages.

    def _publish(self, followed, report):
        with self._lock:
            previous = followed.latest
            followed.latest = report
            subscribers = list(followed.subscribers)
        if previous is None or (previous.get("state"), previous.get("stage")) != \
                (report.get("state"), report.get("stage")):
            self._line("slice_progress", followed, state=report.get("state"),
                       stage=report.get("stage"), sequence=report.get("sequence"))
        for deliver in subscribers:
            deliver(report)
        if report.get("state") in FINAL_STATES:
            self._close(followed)

    def _close(self, followed):
        with self._lock:
            if followed.closed:
                return
            followed.closed = True
            subscribers, followed.subscribers = followed.subscribers, []
            del self._jobs[followed.job]
        for deliver in subscribers:
            deliver(None)

    def _sleep(self, seconds):
        return self._clock.sleep(seconds, self._stopping)

    def _line(self, event, followed, **fields):
        self._log.write(event, user_key=followed.user_key, group=followed.group,
                        slice=followed.job, **fields)


class _Counted:
    """The pieces of a sliced file, counted as they pass; past `limit`, `_TooLarge`."""

    def __init__(self, pieces, limit):
        self._pieces = pieces
        self._limit = limit
        self.count = 0

    def __iter__(self):
        for piece in self._pieces:
            self.count += len(piece)
            if self.count > self._limit:
                raise _TooLarge(self.count)
            yield piece


def held_back(done):
    """What pages see of a `done` report while its sliced file is not yet stored: the slice
    service's last report before it, `running` at the same stage, one `sequence` earlier."""
    report = dict(done, state="running", sequence=done.get("sequence", 1) - 1)
    report.pop("sliced_file", None)
    return report


def reports_of(lines):
    """The progress reports of a stream of server-sent events (`event: progress`, its
    `data` one JSON object); comments and other events are passed over."""
    kind, data = "message", []
    for line in lines:
        if line == "":
            if kind == "progress" and data:
                report = json.loads("\n".join(data))
                if not isinstance(report, dict):
                    raise ValueError(f"a progress report that is not an object: {report!r:.200}")
                yield report
            kind, data = "message", []
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if name == "event":
            kind = value
        elif name == "data":
            data.append(value)
