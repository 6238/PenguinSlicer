"""The project itself: its make targets, its fakes and the guards of the fast suite."""

import re
import socket
import threading
import time
from pathlib import Path

import pytest

from conftest import RealNetworkUsed
from front_fakes import ClockRanAway, FakeClock, START

FRONT = Path(__file__).resolve().parents[1]
PACKAGE = FRONT / "src" / "penguin_front"


def test_the_make_targets_of_the_details_file_exist():
    targets = set(re.findall(r"^([a-z][a-z-]*):", (FRONT / "Makefile").read_text(), re.M))
    assert {"install", "test", "test-parallel", "coverage"} <= targets


def test_no_code_of_the_front_server_reads_the_real_clock_or_sleeps_but_the_clock():
    forbidden = re.compile(r"\btime\.(time|sleep|monotonic|perf_counter)\(|"
                           r"\bdatetime\.(now|utcnow|today)\(|\bdate\.today\(")
    offenders = [f"{path.name}:{n}" for path in PACKAGE.rglob("*.py") if path.name != "clock.py"
                 for n, line in enumerate(path.read_text().splitlines(), 1)
                 if forbidden.search(line)]
    assert offenders == []


def test_a_connection_beyond_loopback_fails_the_test():
    with pytest.raises(RealNetworkUsed, match="cad.onshape.com"):
        socket.getaddrinfo("cad.onshape.com", 443)
    sock = socket.socket()
    try:
        with pytest.raises(RealNetworkUsed, match="192.0.2.1"):
            sock.connect(("192.0.2.1", 443))
        with pytest.raises(RealNetworkUsed, match="192.0.2.1"):
            sock.connect_ex(("192.0.2.1", 443))
    finally:
        sock.close()


def test_loopback_is_allowed():
    assert socket.getaddrinfo("127.0.0.1", 80)
    assert socket.getaddrinfo("localhost", 80)
    assert socket.getaddrinfo(b"::1", 80)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    client, second = socket.socket(), socket.socket()
    try:
        client.connect(server.getsockname())
        assert second.connect_ex(server.getsockname()) == 0
    finally:
        client.close()
        second.close()
        server.close()


def test_sleeping_fails_the_test():
    with pytest.raises(AssertionError, match="no test sleeps"):
        time.sleep(0)


def test_the_fake_clock_starts_at_the_examples_moment_and_moves_only_when_told():
    clock = FakeClock()
    assert clock.now() == START
    clock.advance(60)
    assert clock.now() == START + 60


def test_a_sleeper_wakes_when_the_clock_passes_its_deadline():
    clock = FakeClock()
    woke = threading.Event()

    def sleeper():
        assert clock.sleep(60) is False
        woke.set()

    thread = threading.Thread(target=sleeper)
    thread.start()
    clock.wait_for_sleepers(1)
    clock.advance(59)
    assert clock.sleepers == 1 and not woke.is_set()
    clock.advance(1)
    thread.join()
    assert woke.is_set() and clock.sleepers == 0


def test_a_sleeper_wakes_when_stopped():
    clock = FakeClock()
    stop = threading.Event()
    result = []
    thread = threading.Thread(target=lambda: result.append(clock.sleep(3600, stop)))
    thread.start()
    clock.wait_for_sleepers(1)
    stop.set()
    clock.wake()
    thread.join()
    assert result == [True]


def test_waiting_for_sleepers_that_never_come_fails():
    clock = FakeClock()
    clock_backstop = pytest.MonkeyPatch()
    clock_backstop.setattr("front_fakes.BACKSTOP_S", 0)
    try:
        with pytest.raises(AssertionError, match="1 sleeper"):
            clock.wait_for_sleepers(1)
    finally:
        clock_backstop.undo()


def test_a_clock_moved_without_end_fails():
    clock = FakeClock()
    clock.STEP_LIMIT = 3
    for _ in range(3):
        clock.advance(1)
    with pytest.raises(ClockRanAway):
        clock.advance(1)
