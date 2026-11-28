"""Users at once, on the running server (README-details.md, "Threads"; the guide's "How many
users at once, and what happens when the threads run out").

The target is forty pages following a slice job at once, with short requests still
answered. Every stream is opened over HTTP on the running server, on a port the system
chooses, and each test waits on events, never on a duration."""

import threading

import httpx

from front_fakes import BACKSTOP_S, Announcer
from front_helpers import DEV_GROUP, KEY
from penguin_front.cookie import COOKIE_NAME, CookieKey, Identity
from sliced_helpers import running
from test_server import environ, keep_built, run_served

#: The target's forty progress streams. The four streams one user may hold make them the
#: streams of ten users, each on a slice job of their own, so ten followings beside them.
STREAMS, PER_USER = 40, 4
USERS = STREAMS // PER_USER
#: The short requests the test sends while the streams are open, and the threads left for
#: them (as the target's seven for uploads, downloads and short requests).
SHORT, SPARE = 20, 7


def cookie(clock, user):
    return CookieKey(KEY).seal(Identity(user, f"User {user}",
                                        (("dev-group", "Development Group"),), None,
                                        int(clock.now())))


def open_stream(port, clock, user, job):
    """A page's progress stream on `job`, open once its first two events are read."""
    page = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=BACKSTOP_S,
                        cookies={COOKIE_NAME: cookie(clock, user)})
    answer = page.send(page.build_request("GET", f"/api/slices/{job}/events",
                                          headers=DEV_GROUP), stream=True)
    assert answer.status_code == 200, answer.read()
    text, pieces = "", answer.iter_raw()
    while text.count("\n\n") < 2:
        text += next(pieces).decode()
    return page, answer


def test_forty_progress_streams_held_open_leave_short_requests_answered(tmp_path, clock,
                                                                        standin,
                                                                        monkeypatch):
    built = keep_built(monkeypatch)
    users = [f"user-{n}" for n in range(USERS)]
    for user in users:
        standin.add_job(f"j{user[-1]}", user, "p", "s", running(f"j{user[-1]}", 5),
                        file=b"sliced")
    threads = STREAMS + USERS + SPARE
    opened, answers = [], []

    def use(port):
        ctx = built[0][0].extensions["penguin_front"]
        try:
            for user in users:
                for _ in range(PER_USER):
                    opened.append(open_stream(port, clock, user, f"j{user[-1]}"))
            assert len(ctx["follower"].followed()) == USERS
            assert ctx["streams"].count() == STREAMS
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=BACKSTOP_S,
                              cookies={COOKIE_NAME: cookie(clock, users[0])}) as short:
                for n in range(SHORT):
                    path = "/api/me" if n % 2 else "/api/configuration"
                    answers.append(short.get(path, headers=DEV_GROUP).status_code)
        finally:
            for page, answer in opened:
                answer.close()
                page.close()

    lines, result, _port = run_served(
        tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS=str(threads),
                                 PENGUIN_COOKIE_KEY=KEY, PENGUIN_SLICE_URL=standin.url), use)
    assert result == [0]
    assert answers == [200] * SHORT
    assert len([line for line in lines if line["event"] == "stream_opened"]) == STREAMS


class _QueueTold:
    """The web server's condition for its queue of requests, announcing on `queued` each
    time a request is put in the queue, so that a test waits for a waiting request by being
    told."""

    def __init__(self, condition, queued):
        self._condition = condition
        self._queued = queued

    def notify(self, *args):
        self._condition.notify(*args)
        self._queued.announce()

    def __getattr__(self, name):
        return getattr(self._condition, name)


def test_with_every_thread_held_a_request_waits_and_is_served_when_a_stream_closes(
        tmp_path, clock, standin, monkeypatch):
    built = keep_built(monkeypatch)
    standin.add_job("j1", "dev-user", "p", "s", running("j1", 5), file=b"sliced")
    opened, answered = [], []

    def use(port, server):
        ctx = built[0][0].extensions["penguin_front"]
        dispatcher = server.task_dispatcher
        queued = Announcer()
        dispatcher.queue_cv = _QueueTold(dispatcher.queue_cv, queued)
        try:
            # Three threads, one of them the following's: the two streams hold the others.
            for _ in range(2):
                opened.append(open_stream(port, clock, "dev-user", "j1"))
            assert len(ctx["follower"].followed()) == 1
            waiting = threading.Thread(target=lambda: answered.append(httpx.get(
                f"http://127.0.0.1:{port}/api/me", timeout=BACKSTOP_S,
                cookies={COOKIE_NAME: cookie(clock, "dev-user")}).status_code))
            waiting.start()
            queued.wait_for(lambda: len(dispatcher.queue) == 1, "the request waiting")
            assert answered == []
            # The slice job's final report ends both streams, freeing their threads.
            standin.changes.wait_for(lambda: standin.open_streams("j1") == 1,
                                     "the following's stream")
            standin.report("j1", dict(running("j1", 6), state="failed", error={
                "code": "slice.orca_failed", "message": "m", "remedy": "r",
                "retryable": False, "detail": "d"}))
            waiting.join(BACKSTOP_S)
            assert answered == [200]
        finally:
            for page, answer in opened:
                answer.close()
                page.close()

    _lines, result, _port = run_served(
        tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS="3", PENGUIN_COOKIE_KEY=KEY,
                                 PENGUIN_SLICE_URL=standin.url), use, with_server=True)
    assert result == [0]
