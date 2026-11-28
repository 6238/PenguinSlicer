"""The real clock, which only the running front server uses: every test passes a FakeClock."""

import threading

from penguin_front.clock import RealClock


def test_the_real_clock_gives_the_wall_time_as_seconds():
    assert RealClock().now() > 1_700_000_000


def test_the_real_clock_returns_at_once_when_already_stopped():
    stop = threading.Event()
    stop.set()
    assert RealClock().sleep(3600, stop) is True


def test_the_real_clock_sleeps_for_no_time_at_all():
    assert RealClock().sleep(0) is False
    assert RealClock().sleep(0, threading.Event()) is False
    RealClock().wake()
