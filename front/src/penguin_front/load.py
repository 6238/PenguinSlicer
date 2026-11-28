"""The once-a-minute line on how full the front server is (README-details.md, "The log" and
"Threads"), event `load`:

- `memory_bytes`: the process's resident memory, from the kernel (`VmRSS`), or None where
  the kernel does not say;
- `slices_followed`, and of them `slices_running` and `slices_waiting`, by the latest report
  pages see of each (`queued` is waiting; anything else, a slice whose sliced file is being
  stored among them, is running);
- `streams_open`, the pages' progress streams, and `connections_open`, those and the
  followings' own streams to the slice service together;
- `threads`, the threads of the process that serve (`PENGUIN_FRONT_THREADS`), and
  `threads_in_use`, the request threads busy (a progress stream holds one for as long as it
  is open) and the followings' threads, which are counted among them.
"""

from pathlib import Path

#: How often the line is written.
LOAD_LINE_S = 60
STATUS = Path("/proc/self/status")


def memory_bytes(status=STATUS):
    """The process's resident memory in bytes, or None when the kernel's account of the
    process cannot be read (a system without `/proc`)."""
    try:
        text = status.read_text()
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return None


class Load:
    def __init__(self, *, follower, streams, threads, busy, log):
        self._follower = follower
        self._streams = streams
        self._threads = threads
        self._busy = busy
        self._log = log

    def fields(self):
        states = self._follower.states()
        waiting = states.count("queued")
        streams = self._streams.count()
        return {"memory_bytes": memory_bytes(), "slices_followed": len(states),
                "slices_running": len(states) - waiting, "slices_waiting": waiting,
                "streams_open": streams, "connections_open": streams + len(states),
                "threads": self._threads, "threads_in_use": self._busy() + len(states)}

    def write(self):
        self._log.write("load", **self.fields())
