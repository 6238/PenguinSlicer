"""Something the front server does at a regular interval, on its clock: the sweep of the
sliced files, and the once-a-minute line on how full the server is.

`Every(clock, seconds, action, log, name)` runs `action` once at `start`, then each time
`seconds` have passed, on a daemon thread of its own, until `stop`. A failure of `action`
writes `loop_failed` (`loop`, `trace`) and the loop goes on. `wait_for_runs(n)` is for the
tests: it returns once `action` has run `n` times.
"""

import threading
import traceback

#: The longest `wait_for_runs` waits: a backstop against a hang in a test.
BACKSTOP_S = 10.0


class Every:
    def __init__(self, clock, seconds, action, log, name):
        self.seconds = seconds
        self._clock = clock
        self._action = action
        self._log = log
        self._name = name
        self._stop = threading.Event()
        self._thread = None
        self._ran = threading.Condition()
        self.runs = 0

    def start(self):
        self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                self._action()
            except Exception as exc:  # a fault of the front server's: logged, tried again
                self._log.write("loop_failed", loop=self._name,
                                trace="".join(traceback.format_exception(exc)))
            with self._ran:
                self.runs += 1
                self._ran.notify_all()
            if self._clock.sleep(self.seconds, self._stop):
                return

    def stop(self):
        """End the loop at its next wait, and wait for it."""
        self._stop.set()
        self._clock.wake()
        if self._thread is not None:
            self._thread.join()

    def wait_for_runs(self, count, backstop_s=BACKSTOP_S):
        with self._ran:
            if not self._ran.wait_for(lambda: self.runs >= count, backstop_s):
                raise AssertionError(f"{self._name} ran {self.runs} times, not {count}")
