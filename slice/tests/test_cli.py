"""The command line, `python -m penguin_slice slice <plate-job.json> --out <dir>`, run in
process against the contract's example plate job and a fake Orca."""
import io
import json
import os
import runpy
import signal
import sys
import threading

import pytest

from helpers import CONTRACTS, install_fake_orca
from penguin_slice.__main__ import main

EXAMPLE = CONTRACTS / "examples" / "plate-job.json"
FAILSAFE_S = 10


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    code = main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_slices_the_example_and_prints_the_summary(tmp_path, monkeypatch):
    install_fake_orca(tmp_path, monkeypatch, "ok")
    code, out, err = run(["slice", str(EXAMPLE), "--out", str(tmp_path / "out")])
    assert (code, err) == (0, "")
    summary = json.loads(out)
    assert summary["file"] == "Bracket_plus1-20261009-1432.gcode.3mf"
    assert summary["copies"] == 3
    assert (tmp_path / "out" / summary["file"]).is_file()


def test_failure_prints_the_error_report_and_exits_one(tmp_path):
    # The autouse placeholder Orca cannot start.
    code, out, err = run(["slice", str(EXAMPLE), "--out", str(tmp_path / "out")])
    assert (code, out) == (1, "")
    report = json.loads(err)
    assert report["code"] == "slice.orca_unstartable"
    assert report["message"] == "The slicer could not be started."


def test_refused_plate_job_exits_one(tmp_path):
    path = tmp_path / "plate-job.json"
    path.write_text("[]")
    code, out, err = run(["slice", str(path), "--out", str(tmp_path / "out")])
    assert (code, out, json.loads(err)["code"]) == (1, "", "slice.bad_plate_job")


@pytest.mark.parametrize("argv", [[], ["slice"], ["slice", "x.json"], ["cut", "x.json", "--out", "o"]])
def test_usage_errors_exit_two(argv, capsys):
    with pytest.raises(SystemExit) as caught:
        main(argv)
    assert caught.value.code == 2
    assert "usage: python -m penguin_slice" in capsys.readouterr().err


def test_module_entry_point(tmp_path, monkeypatch, capsys):
    install_fake_orca(tmp_path, monkeypatch, "ok")
    monkeypatch.setattr(sys, "argv", ["penguin_slice", "slice", str(EXAMPLE), "--out", str(tmp_path / "out")])
    monkeypatch.delitem(sys.modules, "penguin_slice.__main__", raising=False)   # run it fresh, as -m does
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("penguin_slice", run_name="__main__", alter_sys=False)
    assert caught.value.code == 0
    assert json.loads(capsys.readouterr().out)["copies"] == 3


def test_serve_runs_the_http_face_and_shuts_its_pool_down(tmp_path, monkeypatch):
    from flask import Flask
    from penguin_slice.jobs import JobPool
    ran, shut = [], []
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: ran.append(kwargs))
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: None)
    monkeypatch.setattr(JobPool, "shutdown", lambda self: shut.append(self))
    code, _out, _err = run(["serve", "--work", str(tmp_path / "work"), "--port", "0"])
    assert code == 0
    assert ran == [{"host": "127.0.0.1", "port": 0, "threaded": True}]
    assert len(shut) == 1


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
    code, _out, _err = run(["serve", "--work", str(tmp_path / "work")])
    assert code == 0 and len(shut) == 1
    assert signal.getsignal(signal.SIGTERM) is before          # the old handler is back


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_slice_interrupted_prints_the_cancelled_report(tmp_path, monkeypatch, sig):
    # Ctrl-C once printed a KeyboardInterrupt traceback.
    import penguin_slice.__main__ as cli
    install_fake_orca(tmp_path, monkeypatch, "hang")
    real = cli.slice_plate_job

    def slice_and_interrupt(*args, **kwargs):
        return real(*args, on_progress=lambda stage, *rest: stage == "slicing_mesh" and os.kill(os.getpid(), sig),
                    **kwargs)
    monkeypatch.setattr(cli, "slice_plate_job", slice_and_interrupt)
    code, out, err = run(["slice", str(EXAMPLE), "--out", str(tmp_path / "out")])
    assert (code, out) == (1, "")
    report = json.loads(err)
    assert report["code"] == "slice.cancelled"
    assert f"stopped by the slice service (interrupted by {sig.name})" in report["detail"]
    assert list((tmp_path / "out").iterdir()) == []                 # scratch removed


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_an_interrupt_while_the_stops_lock_is_held_cannot_hang(sig):
    # The handler once called Stop.set() itself on the main thread: a Ctrl-C arriving while
    # that thread held the Stop's lock (inside a first set(), or run_process's listen())
    # waited on the lock for ever. Now the handler only records the signal; a thread of the
    # command's own sets the stop once the lock is free.
    from penguin_slice.__main__ import _stop_on_signals
    from penguin_slice.slicer import Stop
    stop, stopped = Stop(), threading.Event()
    stop.listen(lambda: stop.is_set() and stopped.set())
    with _stop_on_signals(stop):
        with stop._lock:                          # the main thread inside set() or listen()
            os.kill(os.getpid(), sig)
            signal.getsignal(sig)                 # a call: the handler has run by now, and returned
            handled = True
        assert stopped.wait(FAILSAFE_S), "the stop was never set"
    assert handled and stop.reason == f"interrupted by {sig.name}"


def test_the_signal_relay_ends_with_its_block_and_restores_the_handlers():
    from penguin_slice.__main__ import _stop_on_signals
    from penguin_slice.slicer import Stop
    before = signal.getsignal(signal.SIGINT)
    threads = threading.active_count()
    with _stop_on_signals(Stop()):
        assert signal.getsignal(signal.SIGINT) is not before
    assert signal.getsignal(signal.SIGINT) is before and threading.active_count() == threads


def test_serve_logs_one_json_line_per_transition(tmp_path, monkeypatch):
    from flask import Flask
    from penguin_slice.jobs import JobPool
    from penguin_slice.web import create_app
    install_fake_orca(tmp_path, monkeypatch, "segv")
    captured = {}
    real_create = create_app

    def keep(*args, **kwargs):
        captured["log"] = kwargs["log"]
        return real_create(*args, **kwargs)
    monkeypatch.setattr("penguin_slice.web.create_app", keep)
    monkeypatch.setattr(Flask, "run", lambda self, **kwargs: None)
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: None)
    err = io.StringIO()
    main(["serve", "--work", str(tmp_path / "work")], stdout=io.StringIO(), stderr=err)
    captured["log"]({"event": "slice_job", "state": "failed", "path": tmp_path})
    assert json.loads(err.getvalue().splitlines()[-1])["state"] == "failed"
