"""Progress streams, `GET /api/slices/<slice>/events` (README-details.md, "Progress streams";
contracts/wizard-front-server.md, "Progress streams").

A progress stream is one answer of server-sent events: first `version`, then the latest
report at once (from `asking.reckon`, or the following's own latest when newer), then each
new report the following of the slice job gives (`Follower.subscribe`), each once, by its
`sequence`, and a comment line every `PROGRESS_KEEPALIVE_S` while there is nothing to report.
After a final report the stream closes; it closes too when the following ends without one
(the slice service no longer knows the slice job), when it is replaced, and when the front
server stops.

- **Four at most for one user** (`MAX_STREAMS_PER_USER`), counted in memory for each user
  key, from the moment the stream is accepted to the moment its answer is closed: by its
  end, or by the web server when a write to a page that has gone fails. A stream whose first
  report is already final (a slice job finished or ended) is sent at once, closed, and never
  counted. Past the four, `429` `front.too_many_streams`, before the stream starts.
- **A page reconnecting at once** must not be refused on account of its own dropped stream,
  which the front server notices only at its next write. So a user at the limit who opens a
  stream on a slice job they already follow has their oldest stream on that slice job closed
  first, and the new one counted in its place. Below the limit nothing is closed, so several
  tabs can follow one slice job.

Each stream writes `stream_opened` (`streams_held`) and `stream_closed` (`why`: `final`,
`following_ended`, `replaced`, `stopping` or `page_gone`; `open_s`).
"""

import json
import threading
from collections import deque

from flask import Response, request

from .asking import reckon
from .context import context
from .errors import FrontError
from .following import FINAL_STATES
from .identity import acts_for_group

#: The longest a stream with nothing to report goes without sending (*proposed* name):
#: Cloudflare closes a request after 125 seconds without data, and the page treats a stream
#: silent for 45 seconds as failed.
PROGRESS_KEEPALIVE_S = 15
#: The most progress streams one user may hold at once (*proposed* name; the guide's
#: proposal), on slice jobs and, from phase 5, delivery jobs together.
MAX_STREAMS_PER_USER = 4
KEEPALIVE = b": keep-alive\n\n"


def register(app):
    app.add_url_rule("/api/slices/<slice>/events", "slice_events", events, methods=["GET"])


def event(kind, data, event_id=None):
    """One server-sent event, as the contract writes it."""
    head = f"event: {kind}\n" + (f"id: {event_id}\n" if event_id is not None else "")
    return (head + f"data: {json.dumps(data)}\n\n").encode()


class Stream:
    """One page's stream: the reports given to it, and why it was ended, if it was."""

    def __init__(self, user_key, job, clock):
        self.user_key = user_key
        self.job = job
        self._clock = clock
        self._lock = threading.Lock()
        self._reports = deque()
        self.wakeup = threading.Event()
        #: Why the stream was ended from outside (`replaced`, `stopping`), else None.
        self.ended = None
        self.opened_at = clock.now()

    def deliver(self, report):
        """A report of the following (None when it ends), on the following's thread."""
        with self._lock:
            self._reports.append(report)
        self._wake()

    def take(self):
        with self._lock:
            reports, self._reports = list(self._reports), deque()
        return reports

    def end(self, why):
        self.ended = why
        self._wake()

    def _wake(self):
        self.wakeup.set()
        self._clock.wake()


class Streams:
    """The progress streams held open, for each user key."""

    def __init__(self, clock, limit=MAX_STREAMS_PER_USER):
        self._clock = clock
        self._limit = limit
        self._lock = threading.Lock()
        self._held = {}
        self._stopping = False

    def open(self, user_key, job):
        """A new stream of `user_key` on `job`, counted; None past the limit, or once
        stopping. At the limit, the user's oldest stream on `job` is ended first."""
        with self._lock:
            if self._stopping:
                return None
            held = self._held.setdefault(user_key, [])
            if len(held) >= self._limit:
                same = [stream for stream in held if stream.job == job]
                if not same:
                    return None
                held.remove(same[0])
                same[0].end("replaced")
            stream = Stream(user_key, job, self._clock)
            held.append(stream)
            return stream

    def close(self, stream):
        with self._lock:
            held = self._held.get(stream.user_key, [])
            if stream in held:
                held.remove(stream)
            if not held:
                self._held.pop(stream.user_key, None)

    def held(self, user_key):
        with self._lock:
            return len(self._held.get(user_key, []))

    def count(self):
        with self._lock:
            return sum(len(held) for held in self._held.values())

    def stop(self):
        """End every stream, and open no more."""
        with self._lock:
            self._stopping = True
            every = [stream for held in self._held.values() for stream in held]
        for stream in every:
            stream.end("stopping")


@acts_for_group
def events(slice):  # noqa: A002 - the contract's name for the path's part
    ctx = context()
    reckoned = reckon(slice)
    if request.method == "HEAD":
        return Response(b"", 200, content_type="text/event-stream")
    first = reckoned.report
    stream = subscription = None
    if first.get("state") not in FINAL_STATES:
        stream = ctx["streams"].open(reckoned.user_key, reckoned.job)
        if stream is None:
            raise FrontError("front.too_many_streams",
                             f"{ctx['streams'].held(reckoned.user_key)} progress streams "
                             f"held, the most one user may hold")
        subscription = ctx["follower"].subscribe(reckoned.user_key, reckoned.job,
                                                 stream.deliver)
        latest = subscription.latest if subscription is not None else None
        if latest is not None and latest.get("sequence", 0) > first.get("sequence", 0):
            first = latest
    lines = {"user_key": reckoned.user_key, "group": reckoned.group, "slice": reckoned.job}
    log, clock = ctx["log"], ctx["clock"]
    closing = {"why": "page_gone", "done": False}
    if stream is not None:
        log.write("stream_opened", **lines, streams_held=ctx["streams"].held(stream.user_key))
        if subscription is None:  # the following ended in between: the page asks again
            closing["why"] = "following_ended"

    def body():
        yield event("version", {"version": ctx["version"]})
        yield event("progress", first, first.get("sequence"))
        if stream is None or subscription is None:
            return
        last = first.get("sequence", 0)
        if first.get("state") in FINAL_STATES:
            closing["why"] = "final"
            return
        while True:
            stream.wakeup.clear()
            for report in stream.take():
                if report is None:
                    closing["why"] = "following_ended"
                    return
                if report.get("sequence", 0) <= last:
                    continue
                last = report.get("sequence", 0)
                yield event("progress", report, last)
                if report.get("state") in FINAL_STATES:
                    closing["why"] = "final"
                    return
            if stream.ended is not None:
                closing["why"] = stream.ended
                return
            if not clock.sleep(PROGRESS_KEEPALIVE_S, stream.wakeup):
                yield KEEPALIVE

    def closed():
        if stream is None or closing["done"]:
            return
        closing["done"] = True
        if subscription is not None:
            subscription.cancel()
        ctx["streams"].close(stream)
        log.write("stream_closed", **lines, why=closing["why"],
                  open_s=int(clock.now() - stream.opened_at))

    response = Response(body(), 200, content_type="text/event-stream")
    response.call_on_close(closed)
    return response
