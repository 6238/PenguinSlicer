"""The relay's rate limits: a fixed window per key, on the relay's own clock.

The original relay borrowed flask-limiter from the application it lived in. A standalone relay
needs only this much of it: N requests per window per key, a 429 with Retry-After, and a
clock it can be handed, so the limits are testable without waiting for a minute to pass.

A window opens at a key's first request and lasts `period` seconds, which is how
flask-limiter's fixed window counts too. Everything is in memory, like the rest of the
relay: a restart forgets every count.
"""

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    """`count` requests per `period` seconds, e.g. Limit(60, 60.0) for sixty a minute."""

    count: int
    period: float

    def __str__(self):
        if self.period == 60.0:
            return f"{self.count} per 1 minute"
        return f"{self.count} per {self.period:g} seconds"


#: Above this many tracked keys, the expired windows are dropped on the next hit, so a
#: stream of one-off keys (addresses, guessed codes) cannot grow the table without bound.
PRUNE_ABOVE = 1024


class RateLimiter:
    def __init__(self, clock):
        self._clock = clock
        self._lock = threading.Lock()
        self._windows = {}          # (name, key) -> [opened_at, period, count]

    def hit(self, name, key, limit):
        """Count one request. Returns None when it is allowed, else the seconds until the
        window closes (the Retry-After)."""
        now = self._clock()
        with self._lock:
            if len(self._windows) > PRUNE_ABOVE:
                self._prune(now)
            window = self._windows.get((name, key))
            if window is None or now - window[0] >= window[1]:
                window = [now, limit.period, 0]
                self._windows[(name, key)] = window
            if window[2] >= limit.count:
                return max(0.0, window[0] + window[1] - now)
            window[2] += 1
            return None

    def _prune(self, now):
        for k in [k for k, w in self._windows.items() if now - w[0] >= w[1]]:
            del self._windows[k]

    def reset(self):
        with self._lock:
            self._windows.clear()

    def __len__(self):
        with self._lock:
            return len(self._windows)
