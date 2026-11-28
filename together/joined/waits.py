"""The backstop behind every wait of the joined suite.

A test waits on an event (a line a server writes, a report on a progress stream, a process
ending); the backstop is only what fails the test when the event never comes, so that a
hang is a failure that names what was awaited, never a run that stands still. It is never
a duration a test waits for to see whether something has happened.
"""

import time

#: The longest any one event is awaited. The slowest honest event in the suite, a stopping
#: slice service draining after its slice, takes about a second on an aarch64 Linux machine.
BACKSTOP_S = 60.0


class Backstop:
    def __init__(self, seconds, what):
        self.what = what
        self._end = time.monotonic() + seconds

    def left(self):
        return max(0.0, self._end - time.monotonic())

    def fail(self, why, seen=()):
        seen = "\n".join(f"  {item!r}" for item in seen)
        raise AssertionError(f"waiting for {self.what}: {why}" + (f"\nlast seen:\n{seen}" if seen else ""))
