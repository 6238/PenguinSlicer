"""A limit on how fast one user may do something: at most a number of times in any minute
(README-details.md, "Parts" and "Submitting a plate configuration").

The window slides: each use is remembered for sixty seconds on the front server's clock, and
a use is refused while the user already has the limit's number of uses within the last
sixty seconds. A refused use is not counted. The answer to a refusal is the whole seconds
until the oldest counted use leaves the window, at least 1, for the `Retry-After` header.
The uses are held in memory only, so a restart of the front server forgets them; the limit
protects the slice service from one user, and a restart is rare beside a minute.
"""

import math
import threading
from collections import deque

WINDOW_S = 60


class RateLimit:
    def __init__(self, clock, per_minute):
        self._clock = clock
        self._per_minute = per_minute
        self._uses = {}
        self._lock = threading.Lock()

    def take(self, user_key):
        """Count one use by `user_key` and give None; or, past the limit, count nothing and
        give the whole seconds until a use is allowed again."""
        now = self._clock.now()
        with self._lock:
            self._forget(now)
            uses = self._uses.setdefault(user_key, deque())
            if len(uses) >= self._per_minute:
                return max(1, math.ceil(uses[0] + WINDOW_S - now))
            uses.append(now)
            return None

    def _forget(self, now):
        for user_key in list(self._uses):
            uses = self._uses[user_key]
            while uses and uses[0] + WINDOW_S <= now:
                uses.popleft()
            if not uses:
                del self._uses[user_key]

    def users(self):
        """How many users have a use counted within the window (for the tests)."""
        with self._lock:
            return len(self._uses)
