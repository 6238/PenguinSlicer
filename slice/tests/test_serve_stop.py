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


def serve_with(tmp_path, monkeypatch, drive):
    """Run serve in this thread while `drive(client, log, returned)` runs in another: (exit
    status, the log, the driver's error or None)."""
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
    thread = threading.Thread(target=driver, daemon=True)
    thread.start()
    code = cli.main(["serve", "--work", str(tmp_path / "work"), "--port", "0"], stderr=log)
    returned.set()
    thread.join(FAILSAFE_S)
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
    code, log, failure = serve_with(tmp_path, monkeypatch, drive)
    assert failure is None, failure
    assert code == 0
    assert seen["stopping"][0] == 503 and seen["stopping"][1]["code"] == "slice.stopping"
    assert seen["repeat"][0] == 202 and seen["repeat"][1]["job"] == seen["job"]
    assert seen["final"]["state"] == "done"
    assert (seen["file"], seen["listed"], seen["still_serving"]) == (200, True, True)
    assert seen["deleted"] == (200, {"job": seen["job"], "file": "deleted"})
    assert log.lines[-1] == {**log.lines[-1], "event": "slice_service_stopped", "how": "drained", "files_lost": []}


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
