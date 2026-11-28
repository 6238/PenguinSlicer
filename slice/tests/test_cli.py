"""The command line, `python -m penguin_slice serve --work <dir>`, its one command: the HTTP
interface is the slice service's one interface, so there is no command that slices.

The server is replaced here by FakeServer, which a test makes stop `serve` with a signal it
sends itself; tests/test_serve_stop.py runs the real server on a loopback port the system
chooses."""
import io
import json
import os
import queue
import runpy
import signal
import sys
import threading

import pytest

from penguin_slice import __main__ as cli
from penguin_slice.__main__ import DRAINED, STOP, main, run_until_stopped

FAILSAFE_S = 10


class FakeServer:
    """What werkzeug's make_server returns, as far as `serve` uses it. serve_forever calls
    `on_serve()` (which sends the test's signal) and then waits until shutdown()."""

    made = []

    def __init__(self, host, port, app, threaded=False, on_serve=None, request_handler=None):
        self.host, self.port, self.app, self.threaded = host, port, app, threaded
        self.request_handler = request_handler
        self.server_port = port or 43210
        self.on_serve = on_serve
        self.ended = threading.Event()
        self.closed = False
        FakeServer.made.append(self)

    def serve_forever(self):
        if self.on_serve:
            self.on_serve()
        self.ended.wait(FAILSAFE_S)

    def shutdown(self):
        self.ended.set()

    def server_close(self):
        self.closed = True


def signalling(sig=signal.SIGTERM, times=1):
    """An on_serve that sends this process `sig`, `times` times."""
    def send():
        for _ in range(times):
            os.kill(os.getpid(), sig)
    return send


@pytest.fixture
def servers(monkeypatch):
    """`serve` listens on FakeServers that send one SIGTERM once listening: the servers made."""
    from penguin_slice.jobs import JobPool
    FakeServer.made = []
    monkeypatch.setattr(cli, "make_server", lambda *a, **k: FakeServer(*a, on_serve=signalling(), **k))
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a, **k: None)
    return FakeServer.made


def run(argv):
    err = io.StringIO()
    code = main(argv, stderr=err)
    return code, err.getvalue()


def lines(err):
    return [json.loads(line) for line in err.splitlines() if line.startswith("{")]


@pytest.mark.parametrize("argv", [[], ["slice", "x.json", "--out", "o"], ["serve"], ["cut", "x.json"]])
def test_usage_errors_exit_two(argv, capsys):
    # `slice` was the command line's own way to slice; it is gone, so it is a usage error.
    with pytest.raises(SystemExit) as caught:
        main(argv)
    assert caught.value.code == 2
    assert "usage: python -m penguin_slice" in capsys.readouterr().err


def test_module_entry_point_runs_serve(tmp_path, monkeypatch, servers):
    monkeypatch.setattr(sys, "argv", ["penguin_slice", "serve", "--work", str(tmp_path / "work"), "--port", "0"])
    monkeypatch.delitem(sys.modules, "penguin_slice.__main__", raising=False)   # run it fresh, as -m does
    monkeypatch.setattr("werkzeug.serving.make_server", lambda *a, **k: FakeServer(*a, on_serve=signalling(), **k))
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("penguin_slice", run_name="__main__", alter_sys=False)
    assert caught.value.code == 0
    assert [(s.host, s.port, s.threaded) for s in FakeServer.made] == [("127.0.0.1", 0, True)]


def test_serve_runs_the_http_interface_until_stopped_and_shuts_its_pool_down(tmp_path, monkeypatch, servers):
    from penguin_slice.jobs import JobPool
    shut = []
    real = JobPool.shutdown
    monkeypatch.setattr(JobPool, "shutdown", lambda self: (shut.append(self), real(self)))
    code, err = run(["serve", "--work", str(tmp_path / "work"), "--port", "0"])
    assert code == 0
    (server,) = servers
    assert (server.host, server.port, server.threaded) == ("127.0.0.1", 0, True)
    assert server.ended.is_set() and server.closed           # shut down and its socket closed
    assert len(shut) == 1
    events = [line["event"] for line in lines(err)]
    assert events == ["slice_service_started", "slice_service_stopping", "slice_service_stopped"]
    started = lines(err)[0]
    assert (started["host"], started["port"], started["pid"]) == ("127.0.0.1", 43210, os.getpid())


@pytest.mark.parametrize("raw", ["²", "٣", "0", "lots", "9" * 30])
def test_serve_refuses_a_bad_memory_ceiling_at_start(tmp_path, monkeypatch, raw, servers):
    # "²" once made every slice fail with slice.unexpected; "٣" was read as 3 MB.
    monkeypatch.setenv("PENGUIN_SLICE_MAX_PEAK_MB", raw)
    code, err = run(["serve", "--work", str(tmp_path / "work")])
    assert (code, servers) == (2, [])                             # it never listens
    assert err.startswith("penguin_slice serve: The setting PENGUIN_SLICE_MAX_PEAK_MB is ")
    assert not (tmp_path / "work").exists()                       # refused before anything else


def test_serve_refuses_a_bad_part_store_limit_at_start(tmp_path, monkeypatch, servers):
    monkeypatch.setenv("PENGUIN_SLICE_PART_STORE_MAX_MB", "4")
    code, err = run(["serve", "--work", str(tmp_path / "work")])
    assert (code, servers) == (2, [])
    assert err.startswith("penguin_slice serve: The setting PENGUIN_SLICE_PART_STORE_MAX_MB is '4'")
    assert not (tmp_path / "work").exists()


def test_serve_that_cannot_listen_says_so_and_exits_one(tmp_path, monkeypatch):
    from penguin_slice.jobs import JobPool
    shut = []

    def taken(*args, **kwargs):
        raise OSError(98, "Address already in use")
    monkeypatch.setattr(cli, "make_server", taken)
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a, **k: None)
    monkeypatch.setattr(JobPool, "shutdown", lambda self: shut.append(self))
    code, err = run(["serve", "--work", str(tmp_path / "work"), "--port", "20555"])
    assert code == 1 and len(shut) == 1
    assert "penguin_slice serve: cannot listen on 127.0.0.1:20555: [Errno 98] Address already in use" in err


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_serve_stopped_by_a_signal_shuts_its_pool_down_and_puts_the_handlers_back(tmp_path, monkeypatch, sig):
    # SIGTERM, what a container host sends, once ended serve at once with no shutdown.
    from penguin_slice.jobs import JobPool
    monkeypatch.setattr(cli, "make_server", lambda *a, **k: FakeServer(*a, on_serve=signalling(sig), **k))
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a, **k: None)
    shut = []
    monkeypatch.setattr(JobPool, "shutdown", lambda self: shut.append(self))
    before = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
    code, _err = run(["serve", "--work", str(tmp_path / "work")])
    assert code == 0 and len(shut) == 1
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)) == before


class FakeLibc:
    """A C library whose mallopt records its calls and answers `answer` (glibc: 1 for done)."""

    def __init__(self, answer=1):
        self.calls, self.answer = [], answer

    def mallopt(self, param, value):
        self.calls.append((param, value))
        return self.answer


class TestMallocArenas:
    """Each thread that allocates gets one of glibc's malloc arenas (up to 8 per CPU), and an
    arena keeps what the plate write freed. A slice service process that had served 16 of the
    largest plates in a row peaked at 365 MB (178 MB on the first); with two arenas, at 261 MB.
    `serve` caps them at start."""

    def test_the_cap_is_set_through_mallopt(self):
        from penguin_slice.__main__ import M_ARENA_MAX, MALLOC_ARENAS, cap_malloc_arenas
        libc = FakeLibc()
        assert cap_malloc_arenas(libc) is True
        assert libc.calls == [(M_ARENA_MAX, MALLOC_ARENAS)] == [(-8, 2)]

    def test_a_c_library_without_mallopt_or_that_refuses_is_left_alone(self):
        from penguin_slice.__main__ import cap_malloc_arenas
        assert cap_malloc_arenas(object()) is False         # not glibc (macOS, musl)
        refusing = FakeLibc(answer=0)
        assert cap_malloc_arenas(refusing) is False and len(refusing.calls) == 1

    def test_this_process_c_library_takes_the_cap_when_it_is_glibc(self):
        import ctypes
        from penguin_slice.__main__ import cap_malloc_arenas
        assert cap_malloc_arenas() is hasattr(ctypes.CDLL(None), "mallopt")

    def test_serve_caps_the_arenas_before_it_listens(self, tmp_path, monkeypatch, servers):
        order = []
        monkeypatch.setattr(cli, "cap_malloc_arenas", lambda: order.append("cap"))
        real = cli.make_server
        monkeypatch.setattr(cli, "make_server", lambda *a, **k: (order.append("listen"), real(*a, **k))[1])
        assert run(["serve", "--work", str(tmp_path / "work"), "--port", "0"])[0] == 0
        assert order == ["cap", "listen"]


def test_serve_logs_one_json_line_per_transition(tmp_path, monkeypatch, servers):
    from penguin_slice.web import create_app
    captured = {}
    real_create = create_app

    def keep(*args, **kwargs):
        captured["log"] = kwargs["log"]
        return real_create(*args, **kwargs)
    monkeypatch.setattr("penguin_slice.web.create_app", keep)
    err = io.StringIO()
    main(["serve", "--work", str(tmp_path / "work")], stderr=err)
    captured["log"]({"event": "slice_job", "state": "failed", "path": tmp_path})
    assert json.loads(err.getvalue().splitlines()[-1])["state"] == "failed"


class FakePool:
    """The pool as run_until_stopped sees it, its drain and its shutdown moved by the test."""

    def __init__(self, drained=False, waiting=(), files=()):
        self.calls, self._drained, self.waiting, self.files = [], drained, list(waiting), list(files)
        self.drain = threading.Event()
        self.shut = threading.Event()

    def stop(self):
        self.calls.append("stop")
        return self.waiting

    def drained(self):
        return self._drained

    def wait_drained(self, timeout=None):
        self.drain.wait(FAILSAFE_S)
        return True

    def listing(self):
        return [{"job": job, "file_on_disk": True} for job in self.files]

    def shutdown(self):
        self.calls.append("shutdown")
        self.shut.set()
        self.drain.set()


class TestRunUntilStopped:
    """Item 14's order, with the stops and the drain put in an exact order by the test."""

    def run_in_thread(self, pool, events):
        logs, outcome = [], []
        thread = threading.Thread(target=lambda: outcome.append(run_until_stopped(pool, events, logs.append)),
                                  daemon=True)
        thread.start()
        return thread, logs, outcome

    def test_the_first_stop_waits_for_the_drain(self):
        pool, events = FakePool(waiting=["j2"]), queue.SimpleQueue()
        thread, logs, outcome = self.run_in_thread(pool, events)
        events.put(STOP)
        pool.drain.set()                         # the running slice ended and its file was collected
        thread.join(FAILSAFE_S)
        assert outcome == ["drained"] and pool.calls == ["stop", "shutdown"]
        assert logs[0] == {"event": "slice_service_stopping", "stop": 1, "waiting_ended": ["j2"], "drained": False}
        assert logs[-1] == {"event": "slice_service_stopped", "how": "drained", "files_lost": []}

    def test_nothing_happens_before_the_first_stop(self):
        pool, events = FakePool(), queue.SimpleQueue()
        thread, _logs, outcome = self.run_in_thread(pool, events)
        events.put(DRAINED)                      # a drain is no stop
        events.put(STOP)
        pool.drain.set()
        thread.join(FAILSAFE_S)
        assert outcome == ["drained"] and pool.calls == ["stop", "shutdown"]

    def test_a_second_stop_shuts_the_pool_down_without_waiting_for_the_drain(self):
        pool, events = FakePool(files=["j1"]), queue.SimpleQueue()
        thread, logs, outcome = self.run_in_thread(pool, events)
        events.put(STOP)
        events.put(STOP)
        thread.join(FAILSAFE_S)
        assert outcome == ["second_stop"] and pool.calls == ["stop", "shutdown"]
        assert logs[1] == {"event": "slice_service_stopping", "stop": 2}
        assert logs[-1] == {"event": "slice_service_stopped", "how": "second_stop", "files_lost": ["j1"]}

    def test_a_drained_pool_ends_at_the_first_stop(self):
        pool, events = FakePool(drained=True), queue.SimpleQueue()
        thread, logs, outcome = self.run_in_thread(pool, events)
        events.put(STOP)
        thread.join(FAILSAFE_S)
        assert outcome == ["drained"] and logs[0]["drained"] is True
