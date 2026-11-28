"""The running front server: the command, its start line, and an answer over real HTTP on a
port the system chooses."""

import io
import json
import socket
import threading

import httpx
import pytest
import waitress

from penguin_front.__main__ import main, parse_args
from penguin_front.server import build, serve, stop_server

VERSION = "20261127T221405Z-1a2b3c4"


def environ(tmp_path, **extra):
    return {"PENGUIN_DEV_IDENTITY": "1", "PENGUIN_STATE_DIR": str(tmp_path / "state"),
            "PENGUIN_LOG_DIR": str(tmp_path / "log"), "PENGUIN_VERSION": VERSION, **extra}


def test_a_refused_setting_stops_the_start_with_status_2_naming_it(tmp_path):
    stderr, stdout = io.StringIO(), io.StringIO()
    status = main(["serve", "--port", "0"], environ={"PENGUIN_FRONT_THREADS": "0",
                                                     "PENGUIN_DEV_IDENTITY": "1"},
                  stdout=stdout, stderr=stderr)
    assert status == 2
    assert stderr.getvalue().startswith("penguin_front serve: PENGUIN_FRONT_THREADS: ")
    [line] = [json.loads(text) for text in stdout.getvalue().splitlines()]
    assert (line["component"], line["event"], line["setting"]) == \
        ("front", "start_refused", "PENGUIN_FRONT_THREADS")
    assert line["detail"].startswith("PENGUIN_FRONT_THREADS: ") and "time" in line


def test_a_missing_cookie_key_stops_the_start_with_a_log_line_without_any_value(tmp_path):
    stderr, stdout = io.StringIO(), io.StringIO()
    assert main(["serve", "--port", "0"], environ={}, stdout=stdout, stderr=stderr) == 2
    assert "PENGUIN_COOKIE_KEY" in stderr.getvalue()
    [line] = [json.loads(text) for text in stdout.getvalue().splitlines()]
    assert line["event"] == "start_refused" and line["setting"] == "PENGUIN_COOKIE_KEY"


def test_the_built_front_server_uses_the_folders_of_its_settings(tmp_path, clock):
    from penguin_front.settings import Settings

    app, log = build(Settings.from_environ(environ(tmp_path)), clock=clock,
                     stdout=io.StringIO())
    context = app.extensions["penguin_front"]
    assert context["state_bucket"].root == tmp_path / "state"
    assert log.bucket.root == tmp_path / "log"
    assert context["version"] == VERSION


def test_the_front_server_answers_over_http_writes_its_start_line_and_stops(tmp_path, clock):
    stdout = io.StringIO()
    listening = threading.Event()
    servers = []

    def ready(server):
        servers.append(server)
        listening.set()

    result = []
    # Four threads, not the hundred of the default: each thread reserves its own memory, and
    # the suite runs under a limit on its address space.
    thread = threading.Thread(target=lambda: result.append(serve(
        parse_args(["serve", "--port", "0"]),
        environ=environ(tmp_path, PENGUIN_FRONT_THREADS="4"), stdout=stdout,
        stderr=io.StringIO(), clock=clock, on_listening=ready)))
    thread.start()
    assert listening.wait(10)
    port = int(servers[0].effective_port)
    try:
        answer = httpx.get(f"http://127.0.0.1:{port}/nothing", timeout=10)
        assert answer.status_code == 404
        assert answer.json()["code"] == "front.no_such_request"
        assert answer.headers["X-PenguinSlicer-Version"] == VERSION
        assert answer.headers["Cache-Control"] == "no-store"
    finally:
        stop_server(servers[0])
        thread.join(10)
    assert result == [0]
    lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
    start = lines[0]
    assert start["event"] == "start" and start["version"] == VERSION
    assert start["port"] == port and start["threads"] == 4
    assert lines[-1]["event"] == "stop"
    written = sorted((tmp_path / "log").rglob("*.jsonl"))
    events = [json.loads(line)["event"] for path in written
              for line in path.read_text().splitlines()]
    assert events[0] == "start" and "error" in events and events[-1] == "stop"


@pytest.fixture
def served(clock):
    """The application, with a planted `GET /t/x`, served by waitress on a port the system
    chooses; gives a function that sends one raw request line and gives (status, body)."""
    from penguin_front.app import create_app
    from penguin_front.settings import Settings

    lines = []

    class Lines:
        def write(self, event, **fields):
            lines.append({"event": event, **fields})

    app = create_app(Settings.from_environ({"PENGUIN_DEV_IDENTITY": "1"}), clock=clock,
                     log=Lines(), version=VERSION)

    @app.get("/t/x")
    def planted():
        return {"served": "/t/x"}

    server = waitress.create_server(app, host="127.0.0.1", port=0, threads=2, ident="")
    thread = threading.Thread(target=server.run)
    thread.start()
    port = int(server.effective_port)

    def send(target):
        with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
            connection.sendall(f"GET {target} HTTP/1.1\r\nHost: h\r\n"
                               "Connection: close\r\n\r\n".encode("latin-1"))
            answer = b""
            while chunk := connection.recv(65536):
                answer += chunk
        head, _, body = answer.partition(b"\r\n\r\n")
        return int(head.split()[1]), json.loads(body), lines[-1] if lines else None

    try:
        yield send
    finally:
        stop_server(server)
        thread.join(10)


@pytest.mark.parametrize("target", ["/t/x", "http://h/t/x", "/t/x?a=1"])
def test_a_path_offered_is_served_through_waitress(served, target):
    status, body, _line = served(target)
    assert (status, body) == (200, {"served": "/t/x"})


@pytest.mark.parametrize("target, path", [
    ("//t/x", "//t/x"), ("///t/x", "///t/x"), ("http://h//t/x", "//t/x"),
    ("https://h//t/x?a=1", "//t/x"), ("t/x", "t/x"), ("/t//x", "/t//x"),
    ("/t/%2Fx", "/t/%2Fx"), ("http://h", ""), ("//t/x?a=b//c", "//t/x"),
    ("/t%2Fx", "/t%2Fx"), ("/t%2fx", "/t%2fx"), ("http://h/t%2Fx?a=1", "/t%2Fx"),
])
def test_a_path_not_offered_is_404_through_waitress_as_sent(served, target, path):
    # Waitress drops a path's leading slashes before the application sees it, so the rule
    # is checked on the request's target as sent.
    status, body, line = served(target)
    assert status == 404 and body["code"] == "front.no_such_request"
    assert line["path"] == path


@pytest.mark.parametrize("target", ["/t/x?a=b//c", "http://h/t/x?next=//y"])
def test_a_doubled_slash_in_the_query_alone_is_served(served, target):
    status, body, _line = served(target)
    assert (status, body) == (200, {"served": "/t/x"})


@pytest.mark.parametrize("argv", [["serve", "--port", "x"], ["nothing"], []])
def test_the_command_refuses_arguments_it_does_not_take(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)
