"""Item 14 end to end: `serve` on a loopback port the system chooses, the fake Orca, and the
stop signals sent by the test to its own process, in an exact order.

`serve` runs in the test's main thread, which is where Python runs signal handlers; a driver
thread makes the HTTP requests and sends the signals. Every wait is on an event (a log line
written, a progress report, the process's own return) behind FAILSAFE_S. A driver that fails
sends two stops, so that `serve` returns and the test fails with the driver's error."""
import io
import json
import os
import queue
import signal
import threading
import urllib.error
import urllib.request

from helpers import FAILSAFE_S, box_stl, install_fake_orca, open_gate, part_entry
from penguin_slice import __main__ as cli
from penguin_slice import jobs

BOX = box_stl(20, 20, 10)
USER = {"X-Penguin-User-Key": "user-a"}


class LogWatch(io.TextIOBase):
    """serve's stderr: keeps every JSON line and lets a thread wait for one."""

    def __init__(self):
        self.lines = []
        self._changed = threading.Condition()

    def write(self, text):
        with self._changed:
            for line in text.splitlines():
                if line.startswith("{"):
                    self.lines.append(json.loads(line))
            self._changed.notify_all()
        return len(text)

    def wait_for(self, predicate):
        with self._changed:
            assert self._changed.wait_for(lambda: any(predicate(line) for line in self.lines), FAILSAFE_S), \
                "the log line never came"
            return next(line for line in self.lines if predicate(line))


def event(name, **fields):
    return lambda line: line.get("event") == name and all(line.get(k) == v for k, v in fields.items())


class Client:
    def __init__(self, port):
        self.base = f"http://127.0.0.1:{port}"

    def request(self, method, path, body=None, content_type="application/json"):
        data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={**USER, "Content-Type": content_type})
        try:
            with urllib.request.urlopen(request, timeout=FAILSAFE_S) as answer:
                return answer.status, answer.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def json(self, method, path, body=None, content_type="application/json"):
        status, raw = self.request(method, path, body, content_type)
        return status, json.loads(raw)

    def until(self, job, predicate):
        """The first progress report of the slice job's stream for which predicate holds."""
        request = urllib.request.Request(f"{self.base}/slices/{job}/events", headers=USER)
        with urllib.request.urlopen(request, timeout=FAILSAFE_S) as stream:
            for raw in stream:
                if raw.startswith(b"data: "):
                    report = json.loads(raw[len(b"data: "):])
                    if predicate(report):
                        return report
        raise AssertionError("the stream ended first")


def plate(submission):
    return {"plate_id": "plate-1", "submission_id": submission, "parts": {"box": part_entry("Box", BOX)},
            "instances": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0}]}


def serve_with(tmp_path, monkeypatch, drive, on_return=lambda: None):
    """Run serve in this thread while `drive(client, log, returned)` runs in another: (exit
    status, the log, the driver's error or None). `on_return` runs on the line straight after
    serve returns, before `returned` is set and before the driver is joined."""
    servers, returned, log, failure = queue.SimpleQueue(), threading.Event(), LogWatch(), []
    real = cli.make_server

    def capture(*args, **kwargs):
        server = real(*args, **kwargs)
        servers.put(server)
        return server
    monkeypatch.setattr(cli, "make_server", capture)

    def driver():
        try:
            drive(Client(servers.get(timeout=FAILSAFE_S).server_port), log, returned)
        except BaseException as exc:             # noqa: BLE001 - handed back to the test
            failure.append(exc)
            os.kill(os.getpid(), signal.SIGTERM)
            os.kill(os.getpid(), signal.SIGTERM)
    # A stop that arrives after serve has returned (from a driver whose serve ended too soon)
    # must not end the test's process: outside serve, SIGTERM does nothing.
    previous = signal.signal(signal.SIGTERM, lambda _signum, _frame: None)
    try:
        thread = threading.Thread(target=driver, daemon=True)
        thread.start()
        code = cli.main(["serve", "--work", str(tmp_path / "work"), "--port", "0"], stderr=log)
        on_return()
        returned.set()
        thread.join(FAILSAFE_S)
    finally:
        signal.signal(signal.SIGTERM, previous)
    return code, log, failure[0] if failure else None


def submitted(client, submission):
    assert client.request("POST", "/parts?units=mm", BOX, "application/octet-stream")[0] == 201
    status, body = client.json("POST", "/slices", plate(submission))
    assert status == 202, body
    return body["job"]


def test_a_stop_while_orca_runs_finishes_the_slice_and_exits_once_its_file_is_deleted(tmp_path, monkeypatch):
    install_fake_orca(tmp_path, monkeypatch, "gate")
    seen = {}

    def drive(client, log, returned):
        job = submitted(client, "s1")
        client.until(job, lambda r: r.get("stage") == "slicing_mesh")        # Orca is running
        os.kill(os.getpid(), signal.SIGTERM)
        log.wait_for(event("slice_service_stopping", stop=1))
        seen["stopping"] = client.json("POST", "/slices", plate("s2"))
        seen["repeat"] = client.json("POST", "/slices", plate("s1"))
        open_gate(tmp_path / "work")
        seen["final"] = client.until(job, lambda r: r["state"] in ("done", "failed", "cancelled"))
        seen["file"] = client.request("GET", f"/slices/{job}/file")[0]
        seen["listed"] = client.json("GET", "/slices")[1]["slices"][0]["file_on_disk"]
        seen["still_serving"] = not returned.is_set()
        seen["deleted"] = client.json("DELETE", f"/slices/{job}/file")
        seen["job"] = job
        # The deletion itself ends the drain (the sweeper, which would also wake the wait,
        # is not started in this test).
        log.wait_for(event("slice_service_stopped", how="drained"))
    monkeypatch.setattr(jobs.JobPool, "start_sweeper", lambda self, *args, **kwargs: None)
    code, log, failure = serve_with(tmp_path, monkeypatch, drive)
    assert failure is None, failure
    assert code == 0
    assert seen["stopping"][0] == 503 and seen["stopping"][1]["code"] == "slice.stopping"
    assert seen["repeat"][0] == 202 and seen["repeat"][1]["job"] == seen["job"]
    assert seen["final"]["state"] == "done"
    assert (seen["file"], seen["listed"], seen["still_serving"]) == (200, True, True)
    assert seen["deleted"] == (200, {"job": seen["job"], "file": "deleted"})
    assert log.lines[-1] == {**log.lines[-1], "event": "slice_service_stopped", "how": "drained", "files_lost": []}


def test_the_answer_to_the_delete_that_ends_the_drain_is_written_before_serve_returns(tmp_path, monkeypatch):
    # Found by the joined suite: the front server's DELETE of the last sliced file drained
    # the slice service, which exited before that DELETE's answer was written, so the front
    # server never heard its file was stored. Here that answer is held past the drain's last
    # line until serve either starts waiting for the answers being written or has returned,
    # whichever comes first. A serve that waits writes it first; a serve that does not returns
    # with it unwritten, which `on_return` sees on the line straight after serve returns.
    install_fake_orca(tmp_path, monkeypatch, "ok")
    written, release, watch, at_return = threading.Event(), threading.Event(), [], []
    real, real_wait_idle = cli.make_server, cli.InFlight.wait_idle

    def holding(host, port, app, **kwargs):
        def held(environ, start_response):
            body = app(environ, start_response)
            if environ["REQUEST_METHOD"] == "DELETE" and environ["PATH_INFO"].endswith("/file"):
                watch[0].wait_for(event("slice_service_stopped"))
                assert release.wait(FAILSAFE_S), "serve neither waited for the answer nor returned"
                return _Closing(body, written)
            return body
        return real(host, port, held, **kwargs)
    monkeypatch.setattr(cli, "make_server", holding)

    def waiting(self, seconds):
        release.set()
        return real_wait_idle(self, seconds)
    monkeypatch.setattr(cli.InFlight, "wait_idle", waiting)

    def on_return():
        at_return.append(written.is_set())
        release.set()

    def drive(client, log, returned):
        watch.append(log)
        job = submitted(client, "s1")
        client.until(job, lambda r: r["state"] == "done")
        os.kill(os.getpid(), signal.SIGTERM)
        log.wait_for(event("slice_service_stopping", stop=1))
        assert client.json("DELETE", f"/slices/{job}/file") == (200, {"job": job, "file": "deleted"})
    monkeypatch.setattr(jobs.JobPool, "start_sweeper", lambda self, *args, **kwargs: None)
    code, log, failure = serve_with(tmp_path, monkeypatch, drive, on_return)
    assert at_return == [True], "serve returned before the answer that drained it was written"
    assert failure is None, failure
    assert code == 0


def test_an_answer_still_being_written_past_the_bound_is_cut_and_logged(tmp_path, monkeypatch):
    install_fake_orca(tmp_path, monkeypatch, "ok")
    monkeypatch.setattr(cli, "STOP_ANSWERS_S", 0)
    held, releases = threading.Event(), []
    real = cli.make_server

    def holding(host, port, app, **kwargs):
        def slow(environ, start_response):
            if environ["PATH_INFO"] == "/settings-table":
                held.set()
                releases[0].wait(FAILSAFE_S)        # until serve has returned
            return app(environ, start_response)
        return real(host, port, slow, **kwargs)
    monkeypatch.setattr(cli, "make_server", holding)

    def drive(client, log, returned):
        releases.append(returned)
        threading.Thread(target=client.request, args=("GET", "/settings-table"), daemon=True).start()
        assert held.wait(FAILSAFE_S)
        os.kill(os.getpid(), signal.SIGTERM)
    code, log, failure = serve_with(tmp_path, monkeypatch, drive)
    assert failure is None, failure
    assert code == 0
    cut = log.wait_for(event("slice_service_answers_cut"))
    assert (cut["answering"], cut["waited_s"]) == (["GET /settings-table"], 0)


class _Closing:
    """An answer's body that, once written and closed, sets `written`, then closes the body."""

    def __init__(self, body, written):
        self._body, self._written = body, written

    def __iter__(self):
        return iter(self._body)

    def close(self):
        self._written.set()
        getattr(self._body, "close", lambda: None)()


def test_a_waiting_slice_job_ends_with_shutdown_at_the_stop(tmp_path, monkeypatch):
    install_fake_orca(tmp_path, monkeypatch, "gate")
    seen = {}

    def drive(client, log, returned):
        running = submitted(client, "s1")
        client.until(running, lambda r: r.get("stage") == "slicing_mesh")
        waiting = client.json("POST", "/slices", dict(plate("s2"), plate_id="plate-2"))[1]["job"]
        os.kill(os.getpid(), signal.SIGTERM)
        log.wait_for(event("slice_service_stopping", stop=1))
        seen["waiting"] = client.json("GET", f"/slices/{waiting}")[1]
        open_gate(tmp_path / "work")
        client.until(running, lambda r: r["state"] == "done")
        client.request("DELETE", f"/slices/{running}/file")
    code, log, failure = serve_with(tmp_path, monkeypatch, drive)
    assert failure is None, failure
    assert code == 0
    assert (seen["waiting"]["state"], seen["waiting"]["cancel_reason"]) == ("cancelled", "shutdown")


def test_a_second_stop_ends_the_running_slice_with_shutdown_once_orca_is_gone(tmp_path, monkeypatch):
    install_fake_orca(tmp_path, monkeypatch, "gate")
    seen = {}

    def drive(client, log, returned):
        job = submitted(client, "s1")
        client.until(job, lambda r: r.get("stage") == "slicing_mesh")
        seen["pid"] = int(next((tmp_path / "work").rglob("fake-orca.pid")).read_text())
        os.kill(os.getpid(), signal.SIGTERM)
        log.wait_for(event("slice_service_stopping", stop=1))
        os.kill(os.getpid(), signal.SIGTERM)
        seen["job"] = job
    code, log, failure = serve_with(tmp_path, monkeypatch, drive)
    assert failure is None, failure
    assert code == 0
    cancelled = [line for line in log.lines if line.get("job") == seen["job"] and line.get("state") == "cancelled"]
    assert [line["cancel_reason"] for line in cancelled] == ["shutdown"]
    try:
        os.kill(seen["pid"], 0)
        alive = True
    except ProcessLookupError:
        alive = False
    assert not alive                              # Orca was gone before serve returned
    assert log.lines[-1]["how"] == "second_stop" and log.lines[-1]["files_lost"] == []


def test_a_second_stop_while_a_sliced_file_is_uncollected_exits_at_once(tmp_path, monkeypatch):
    install_fake_orca(tmp_path, monkeypatch, "ok")
    seen = {}

    def drive(client, log, returned):
        job = submitted(client, "s1")
        client.until(job, lambda r: r["state"] == "done")
        os.kill(os.getpid(), signal.SIGTERM)
        log.wait_for(event("slice_service_stopping", stop=1))
        seen["still_serving"] = client.json("GET", f"/slices/{job}")[1]["state"] == "done" and not returned.is_set()
        os.kill(os.getpid(), signal.SIGTERM)
        seen["job"] = job
    code, log, failure = serve_with(tmp_path, monkeypatch, drive)
    assert failure is None, failure
    assert code == 0 and seen["still_serving"]
    assert log.lines[-1]["how"] == "second_stop" and log.lines[-1]["files_lost"] == [seen["job"]]
