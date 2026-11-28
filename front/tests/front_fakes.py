"""The fake clock and the small helpers every test of the front server shares.

Nothing here reads the real clock or sleeps. A test moves time with `FakeClock.advance`, and
waits for something to happen with `wait_for`, which returns as soon as the thing it waits
for is true and fails the test if it never becomes true: the bound is a backstop against a
hang, never a duration the test relies on.
"""

import threading

#: 2026-11-27T22:14:05Z, the moment the contracts' examples use.
START = 1_795_817_645.0

#: The longest any test waits for an event before failing. A backstop against a hang, never
#: a time a test relies on: every event a test waits for happens within milliseconds.
BACKSTOP_S = 10.0


class ClockRanAway(BaseException):
    """A fake clock passed its step limit. A BaseException, so that no `except Exception`
    in the code under test swallows it."""


class FakeClock:
    """The front server's clock (`penguin_front.clock.Clock`), moved by the test.

    `now()` is the wall time in seconds since the epoch. `sleep(seconds, stop)` blocks the
    calling thread until the test has advanced the clock past its deadline, or until `stop`
    is set and `wake()` is called; it returns whether `stop` is set. `sleepers` counts the
    threads blocked in `sleep`, so a test can wait until a background loop is parked before
    it moves time."""

    #: The most advances one clock takes in a test: far above the busiest honest test, far
    #: below a loop with no end, which then fails here instead of growing without bound.
    STEP_LIMIT = 100_000

    def __init__(self, now=START):
        self._now = float(now)
        self._steps = 0
        self._sleepers = 0
        self._cond = threading.Condition()

    def now(self):
        with self._cond:
            return self._now

    def sleep(self, seconds, stop=None):
        with self._cond:
            deadline = self._now + seconds
            self._sleepers += 1
            self._cond.notify_all()
            try:
                while self._now < deadline and not (stop is not None and stop.is_set()):
                    self._cond.wait()
            finally:
                self._sleepers -= 1
                self._cond.notify_all()
        return stop is not None and stop.is_set()

    def wake(self):
        with self._cond:
            self._cond.notify_all()

    def advance(self, seconds):
        with self._cond:
            self._steps += 1
            if self._steps > self.STEP_LIMIT:
                raise ClockRanAway(
                    f"the fake clock was advanced more than {self.STEP_LIMIT} times; a loop "
                    "that moves simulated time has no end")
            self._now += seconds
            self._cond.notify_all()

    @property
    def sleepers(self):
        with self._cond:
            return self._sleepers

    def wait_for_sleepers(self, count):
        """Block until at least `count` threads are blocked in `sleep`."""
        with self._cond:
            if not self._cond.wait_for(lambda: self._sleepers >= count, BACKSTOP_S):
                raise AssertionError(f"{count} sleeper(s) expected, {self._sleepers} found")


class LoopbackServer:
    """A WSGI application served on the loopback address at a port the system chooses.

    `stop` closes the listening socket, so every connection is refused until `start` again,
    which listens on the same port so the address a test was given stays good."""

    def __init__(self, app):
        self.app = app
        self.port = 0
        self._server = None
        self._thread = None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        from werkzeug.serving import make_server

        self._server = make_server("127.0.0.1", self.port, self.app, threaded=True)
        self.port = self._server.server_port
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        return self.url

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join()
            self._server = None


class Announcer:
    """A condition that fakes and the code under test announce changes on, so a test waits
    for a state by being told of each change, never by looking again after a pause."""

    def __init__(self):
        self._cond = threading.Condition()

    def announce(self):
        with self._cond:
            self._cond.notify_all()

    def wait_for(self, predicate, what):
        """Return once `predicate()` is true; fail the test, naming `what`, if no change
        announced within the backstop makes it true."""
        with self._cond:
            if not self._cond.wait_for(predicate, BACKSTOP_S):
                raise AssertionError(f"never happened: {what}")
