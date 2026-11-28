"""The one place the front server reads the time or waits.

Every part of the front server is given a clock and reads the time only through it:
`now()`, the wall time in seconds since the epoch, and `sleep(seconds, stop)`, which waits
until the time has passed or `stop` (a `threading.Event`) is set, and returns whether it is
set. Whoever sets `stop` then calls `wake()`, which the real clock does not need and a fake
clock uses to let its sleepers see the event. The tests pass a fake clock they move
(tests/front_fakes.py), so thirty days, two hours or a minute pass in an instant; a check of
the fast suite fails if any other module reads the real clock or sleeps.
"""

import threading
import time


class RealClock:
    def now(self):
        return time.time()

    def sleep(self, seconds, stop=None):
        stop = stop if stop is not None else threading.Event()
        return stop.wait(seconds)

    def wake(self):
        """Nothing to do: a real sleep sees its `stop` event at once."""
