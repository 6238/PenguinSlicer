"""The once-a-minute line on how full the front server is (README-details.md, "The log" and
"Threads"): the memory it holds, the slice jobs running and waiting, the connections it
holds open and the threads in use."""

from pathlib import Path

from penguin_front import load as loading
from penguin_front.load import Load
from sliced_helpers import (GROUP, USER, Told, app, bucket, client, context, log,  # noqa: F401
                            queued, running)


def test_the_line_counts_the_followings_and_streams_held_and_the_threads_in_use(
        app, standin, log):
    ctx = context(app)
    follower = ctx["follower"]
    standin.add_job("j1", USER, "p", "s", queued("j1"))
    standin.add_job("j2", USER, "p", "s", running("j2", 3))
    told = Told()
    for job in ("j1", "j2"):
        follower.follow(USER, job, GROUP)
        follower.subscribe(USER, job, told)
    told.wait_for(lambda: len(told.items) == 2, "both followings' first reports")
    streams = [ctx["streams"].open(USER, "j1") for _ in range(3)]
    assert None not in streams
    line = Load(follower=follower, streams=ctx["streams"], threads=100, busy=lambda: 4,
                log=log)
    line.write()
    [written] = log.events("load")
    assert {k: v for k, v in written.items() if k != "memory_bytes"} == {
        "event": "load", "slices_followed": 2, "slices_running": 1, "slices_waiting": 1,
        "streams_open": 3, "connections_open": 5, "threads": 100, "threads_in_use": 6}
    assert isinstance(written["memory_bytes"], int) and written["memory_bytes"] > 0


def test_the_memory_is_the_processs_resident_size(tmp_path):
    status = tmp_path / "status"
    status.write_text("Name:\tpython\nVmHWM:\t  9000 kB\nVmRSS:\t  1234 kB\n")
    assert loading.memory_bytes(status) == 1234 * 1024


def test_a_memory_that_cannot_be_read_is_none(tmp_path):
    assert loading.memory_bytes(tmp_path / "none") is None
    (tmp_path / "status").write_text("Name:\tpython\n")
    assert loading.memory_bytes(tmp_path / "status") is None


def test_the_line_is_written_once_a_minute():
    assert loading.LOAD_LINE_S == 60
    assert Path("/proc/self/status") == loading.STATUS
