"""Shared set-up for the fast suite.

Every test runs with PENGUIN_SLICE_ORCA pointing at a placeholder file in its own
temporary directory: a test that forgets to replace subprocess.run can never start the
real Orca (the placeholder is not executable, so the slice fails at once with
"The slicer could not be started."), and no test depends on whether Orca is installed.
"""
import signal
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "scripts"
for _path in (TESTS, SCRIPTS):          # helpers.py and the scripts, for every worker and import mode
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


HANG_S = 20     # no test of this suite runs a second; one still running after this is hung


class Hung(BaseException):
    """Not an Exception: no `except Exception` in the code under test can swallow it."""


@pytest.fixture(autouse=True)
def no_test_can_hang():
    """A test still running after HANG_S fails with a message saying it hung, instead of
    hanging the suite. A SIGALRM in this process (tests run in the main thread, also under
    xdist) raises in whatever the test waits on; slicer.run_process's own cleanup then kills
    the stand-in's group, and the stand-in ends itself in any case (fake_orca.LIMIT_S).
    The tests that wait on a stand-in only a stop can end are bounded themselves, in
    FAILSAFE_S (helpers.bounded), with a message naming what never happened."""
    def hung(signum, frame):
        raise Hung(f"this test was still running after {HANG_S} s: it waits on a process, a thread or an event "
                   f"that never came")
    previous = signal.signal(signal.SIGALRM, hung)
    signal.setitimer(signal.ITIMER_REAL, HANG_S)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@pytest.fixture(autouse=True)
def timers(monkeypatch):
    """No real timer ever runs in the fast suite: a timeout fires when a test fires it."""
    from helpers import ManualTimers
    from penguin_slice import slicer
    made = ManualTimers()
    monkeypatch.setattr(slicer, "TIMER", made)
    return made


@pytest.fixture(autouse=True)
def machine(monkeypatch):
    """No test reads this machine's state while the stand-in Orca runs: the kernel's
    out-of-memory kill count (other processes on the machine move it) is a steady 0, and
    the memory watchdog reads a steady 1 MB. A test that needs either sets its own."""
    from penguin_slice import slicer
    monkeypatch.setattr(slicer, "_oom_kills", lambda: 0)
    monkeypatch.setattr(slicer, "MEMORY_READER", lambda pgid: (1024, 1024))


@pytest.fixture(autouse=True)
def placeholder_orca(tmp_path, monkeypatch):
    path = tmp_path / "orca-placeholder" / "orca-slicer"
    path.parent.mkdir()
    path.write_text("not a program\n")
    monkeypatch.setenv("PENGUIN_SLICE_ORCA", str(path))
    return path
