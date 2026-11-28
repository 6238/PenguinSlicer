"""A server run as a process of its own, its every output line kept and announced.

A test waits for a line, or for the process to end, by being told: each line read wakes
every waiter, and a waiter that is not satisfied within its backstop fails the test with
what it waited for and the last lines it saw. Nothing here waits a number of seconds to see
whether something has happened.
"""

import json
import os
import signal
import subprocess
import threading

from .waits import BACKSTOP_S, Backstop

#: The setting, in this process's environment, of the bytes of address space each server may
#: take; unset, no limit of the suite's own.
SERVER_AS_BYTES = "JOINED_SERVER_AS_BYTES"


class Line:
    """One line of a process's output: the stream (`out` or `err`), its text, and the JSON
    object it holds when it is one (else None)."""

    def __init__(self, stream, text):
        self.stream = stream
        self.text = text
        try:
            value = json.loads(text)
        except ValueError:
            value = None
        self.json = value if isinstance(value, dict) else None

    def __repr__(self):
        return f"<{self.stream}: {self.text[:160]}>"


class Running:
    def __init__(self, name, argv, *, env, cwd, log_path):
        self.name = name
        self.lines = []
        self.returncode = None
        self._changed = threading.Condition()
        self._log = open(log_path, "a", encoding="utf-8")
        self._log.write(f"# {name}: {' '.join(str(a) for a in argv)}\n")
        self._log.flush()
        # The limit on each server's address space, when the run gives one (together/Makefile,
        # `test`): `prlimit` sets it and runs the server in its own place, so the pid is the
        # server's. Given to each server rather than to pytest, whose Chromium cannot start
        # under it; the real-Orca run gives none, since the slice service sets Orca's own.
        limit = os.environ.get(SERVER_AS_BYTES)
        if limit:
            argv = ["prlimit", f"--as={limit}", "--", *argv]
        # A session of its own, so that a kill reaches every process it started (Orca).
        self.process = subprocess.Popen([str(a) for a in argv], env=env, cwd=cwd,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, start_new_session=True)
        self._readers = [threading.Thread(target=self._read, args=(stream, label), daemon=True,
                                          name=f"{name}-{label}")
                         for stream, label in ((self.process.stdout, "out"),
                                               (self.process.stderr, "err"))]
        for reader in self._readers:
            reader.start()
        threading.Thread(target=self._reap, daemon=True, name=f"{name}-reap").start()

    @property
    def pid(self):
        return self.process.pid

    def _read(self, stream, label):
        for raw in stream:
            text = raw.decode("utf-8", "replace").rstrip("\n")
            with self._changed:
                self.lines.append(Line(label, text))
                self._log.write(f"{label}: {text}\n")
                self._log.flush()
                self._changed.notify_all()

    def _reap(self):
        code = self.process.wait()
        for reader in self._readers:
            reader.join()
        with self._changed:
            self.returncode = code
            self._log.write(f"# {self.name} exited {code}\n")
            self._log.flush()
            self._changed.notify_all()

    # Waiting.

    def mark(self):
        """A place in the output: a later `wait_for_line(since=…)` looks only after it."""
        with self._changed:
            return len(self.lines)

    def wait_for_line(self, test, what, *, since=0, backstop_s=BACKSTOP_S):
        """The first line from `since` on for which `test(line)` is true. Fails when the
        process ends first, or at the backstop."""
        stop = Backstop(backstop_s, f"{self.name}: {what}")
        with self._changed:
            seen = since
            while True:
                for line in self.lines[seen:]:
                    seen += 1
                    if test(line):
                        return line
                if self.returncode is not None:
                    stop.fail(f"it exited {self.returncode} first", self.lines[-20:])
                if not self._changed.wait(stop.left()):
                    stop.fail("not seen", self.lines[-20:])

    def wait_for_event(self, event, *, since=0, backstop_s=BACKSTOP_S, **fields):
        """The first JSON line from `since` on with this `event` and these fields."""
        def test(line):
            return line.json is not None and line.json.get("event") == event and all(
                line.json.get(k) == v for k, v in fields.items())
        described = ", ".join(f"{k}={v!r}" for k, v in fields.items())
        return self.wait_for_line(test, f"a line {event!r} {described}", since=since,
                                  backstop_s=backstop_s).json

    def events(self, event=None):
        """Every JSON line so far, or those of one `event`."""
        with self._changed:
            return [line.json for line in self.lines
                    if line.json is not None and (event is None or line.json.get("event") == event)]

    def wait_for_exit(self, backstop_s=BACKSTOP_S):
        stop = Backstop(backstop_s, f"{self.name}: its end")
        with self._changed:
            while self.returncode is None:
                if not self._changed.wait(stop.left()):
                    stop.fail("it did not exit", self.lines[-20:])
            return self.returncode

    # Ending it.

    def signal(self, signum):
        """`signum` to the server itself (not its children: the server decides what becomes
        of them), as a container host's stop does."""
        if self.returncode is None:
            try:
                os.kill(self.process.pid, signum)
            except ProcessLookupError:
                pass

    def kill(self):
        """End the server and every process it started at once, as a crash does."""
        if self.returncode is None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return self.wait_for_exit()

    def close(self):
        """What a test's end does: anything still running is killed with its children."""
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        self.wait_for_exit()
        self._log.close()
