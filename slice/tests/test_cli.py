"""The command line, `python -m penguin_slice serve --work <dir>`, its one command: the HTTP
interface is the slice service's one interface, so there is no command that slices."""
import io
import json
import os
import runpy
import signal
import sys
import threading

import pytest

from penguin_slice.__main__ import main

FAILSAFE_S = 10


def run(argv):
    err = io.StringIO()
    code = main(argv, stderr=err)
    return code, err.getvalue()


@pytest.mark.parametrize("argv", [[], ["slice", "x.json", "--out", "o"], ["serve"], ["cut", "x.json"]])
def test_usage_errors_exit_two(argv, capsys):
    # `slice` was the command line's own way to slice; it is gone, so it is a usage error.
    with pytest.raises(SystemExit) as caught:
        main(argv)
    assert caught.value.code == 2
    assert "usage: python -m penguin_slice" in capsys.readouterr().err


def test_module_entry_point_runs_serve(tmp_path, monkeypatch):
    from flask import Flask
    from penguin_slice.jobs import JobPool
    ran = []
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: ran.append(kwargs))
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: None)
    monkeypatch.setattr(sys, "argv", ["penguin_slice", "serve", "--work", str(tmp_path / "work"), "--port", "0"])
    monkeypatch.delitem(sys.modules, "penguin_slice.__main__", raising=False)   # run it fresh, as -m does
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("penguin_slice", run_name="__main__", alter_sys=False)
    assert caught.value.code == 0 and ran == [{"host": "127.0.0.1", "port": 0, "threaded": True}]


def test_serve_runs_the_http_interface_and_shuts_its_pool_down(tmp_path, monkeypatch):
    from flask import Flask
    from penguin_slice.jobs import JobPool
    ran, shut = [], []
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: ran.append(kwargs))
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: None)
    monkeypatch.setattr(JobPool, "shutdown", lambda self: shut.append(self))
    code, _err = run(["serve", "--work", str(tmp_path / "work"), "--port", "0"])
    assert code == 0
    assert ran == [{"host": "127.0.0.1", "port": 0, "threaded": True}]
    assert len(shut) == 1


@pytest.mark.parametrize("raw", ["²", "٣", "0", "lots", "9" * 30])
def test_serve_refuses_a_bad_memory_ceiling_at_start(tmp_path, monkeypatch, raw):
    # "²" once made every slice fail with slice.unexpected; "٣" was read as 3 MB.
    from flask import Flask
    ran = []
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: ran.append(kwargs))
    monkeypatch.setenv("PENGUIN_SLICE_MAX_PEAK_MB", raw)
    code, err = run(["serve", "--work", str(tmp_path / "work")])
    assert (code, ran) == (2, [])                                 # it never listens
    assert err.startswith("penguin_slice serve: The setting PENGUIN_SLICE_MAX_PEAK_MB is ")
    assert not (tmp_path / "work").exists()                       # refused before anything else


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
def test_serve_stopped_by_a_signal_shuts_its_pool_down(tmp_path, monkeypatch, sig):
    # SIGTERM, what a container host sends, once ended serve at once with no shutdown.
    from flask import Flask
    from penguin_slice.jobs import JobPool
    shut = []

    def run_until_signalled(self, **kwargs):
        os.kill(os.getpid(), sig)
        threading.Event().wait(FAILSAFE_S)         # the signal ends this wait at once
        raise AssertionError(f"{sig.name} did not stop the server")
    monkeypatch.setattr(Flask, "run", run_until_signalled)
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: None)
    monkeypatch.setattr(JobPool, "shutdown", lambda self: shut.append(self))
    before = signal.getsignal(signal.SIGTERM)
    code, _err = run(["serve", "--work", str(tmp_path / "work")])
    assert code == 0 and len(shut) == 1
    assert signal.getsignal(signal.SIGTERM) is before          # the old handler is back


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

    def test_serve_caps_the_arenas_before_it_listens(self, tmp_path, monkeypatch):
        from flask import Flask
        from penguin_slice import __main__ as cli
        from penguin_slice.jobs import JobPool
        order = []
        monkeypatch.setattr(cli, "cap_malloc_arenas", lambda: order.append("cap"))
        monkeypatch.setattr(Flask, "run", lambda self, **kwargs: order.append("listen"))
        monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: None)
        assert run(["serve", "--work", str(tmp_path / "work"), "--port", "0"])[0] == 0
        assert order == ["cap", "listen"]


def test_serve_logs_one_json_line_per_transition(tmp_path, monkeypatch):
    from flask import Flask
    from penguin_slice.jobs import JobPool
    from penguin_slice.web import create_app
    captured = {}
    real_create = create_app

    def keep(*args, **kwargs):
        captured["log"] = kwargs["log"]
        return real_create(*args, **kwargs)
    monkeypatch.setattr("penguin_slice.web.create_app", keep)
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: None)
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: None)
    err = io.StringIO()
    main(["serve", "--work", str(tmp_path / "work")], stderr=err)
    captured["log"]({"event": "slice_job", "state": "failed", "path": tmp_path})
    assert json.loads(err.getvalue().splitlines()[-1])["state"] == "failed"
