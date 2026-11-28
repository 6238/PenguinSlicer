"""The running front server: the command, its start line, and an answer over real HTTP on a
port the system chooses."""

import io
import json
import socket
import threading

import httpx
import pytest
import waitress

from front_helpers import make_dist
from penguin_front.__main__ import main, parse_args
from penguin_front.server import build, serve, stop_server

VERSION = "20261127T221405Z-1a2b3c4"


def environ(tmp_path, **extra):
    """Fresh folders, the development identity on and no cookie key."""
    return {"PENGUIN_DEV_IDENTITY": "1", "PENGUIN_STATE_DIR": str(tmp_path / "state"),
            "PENGUIN_LOG_DIR": str(tmp_path / "log"), "PENGUIN_VERSION": VERSION,
            "PENGUIN_WIZARD_DIST": str(make_dist(tmp_path / "dist")), **extra}


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


def run_served(tmp_path, clock, environment, use, with_server=False):
    """Serve on a port the system chooses, call `use(port)` (`use(port, server)` with
    `with_server`), stop; gives the lines written on standard output and the exit status."""
    stdout = io.StringIO()
    listening = threading.Event()
    servers = []

    def ready(server):
        servers.append(server)
        listening.set()

    result = []
    thread = threading.Thread(target=lambda: result.append(serve(
        parse_args(["serve", "--port", "0"]), environ=environment, stdout=stdout,
        stderr=io.StringIO(), clock=clock, on_listening=ready)))
    thread.start()
    assert listening.wait(10)
    port = int(servers[0].effective_port)
    try:
        use(port, servers[0]) if with_server else use(port)
    finally:
        stop_server(servers[0])
        thread.join(10)
    return [json.loads(line) for line in stdout.getvalue().splitlines()], result, port


def test_the_front_server_answers_over_http_writes_its_start_line_and_stops(tmp_path, clock):
    def use(port):
        answer = httpx.get(f"http://127.0.0.1:{port}/nothing", timeout=10)
        assert answer.status_code == 404
        assert answer.json()["code"] == "front.no_such_request"
        assert answer.headers["X-PenguinSlicer-Version"] == VERSION
        assert answer.headers["Cache-Control"] == "no-store"

    # Four threads, not the hundred of the default: each thread reserves its own memory, and
    # the suite runs under a limit on its address space.
    lines, result, port = run_served(tmp_path, clock,
                                     environ(tmp_path, PENGUIN_FRONT_THREADS="4"), use)
    assert result == [0]
    start = lines[0]
    assert start["event"] == "start" and start["version"] == VERSION
    assert start["port"] == port and start["threads"] == 4
    assert lines[-1]["event"] == "stop"
    written = sorted((tmp_path / "log").rglob("*.jsonl"))
    events = [json.loads(line)["event"] for path in written
              for line in path.read_text().splitlines()]
    assert events[0] == "start" and "error" in events and events[-1] == "stop"


@pytest.mark.parametrize("threads, followed, during", [(4, 2, 2), (2, 3, 1)])
def test_each_following_of_a_slice_job_is_counted_among_the_threads(tmp_path, clock,
                                                                    monkeypatch, threads,
                                                                    followed, during):
    from front_helpers import nobody_listens

    counts, built = [], keep_built(monkeypatch)

    def use(_port, server):
        dispatcher = server.task_dispatcher
        running = lambda: len(dispatcher.threads) - dispatcher.stop_count  # noqa: E731
        follower = built[0][0].extensions["penguin_front"]["follower"]
        counts.append(running())
        for n in range(followed):  # nobody answers: each following waits and tries again
            follower.follow("dev-user", f"j{n}", "dev-group")
        counts.append(running())
        follower.stop()   # each following ends at its wait, and gives its thread back
        clock.wake()
        follower.join()
        counts.append(running())

    lines, result, _port = run_served(
        tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS=str(threads),
                                 PENGUIN_SLICE_URL=nobody_listens()), use, with_server=True)
    # At least one thread is always left to serve requests.
    assert result == [0] and counts == [threads, during, threads]
    assert lines[0]["threads"] == threads


def test_the_running_server_sweeps_and_writes_how_full_it_is_once_a_minute(tmp_path, clock,
                                                                          monkeypatch):
    from front_helpers import nobody_listens

    built = keep_built(monkeypatch)

    def use(_port):
        ctx = built[0][0].extensions["penguin_front"]
        ctx["sweeper"].every.wait_for_runs(1)
        ctx["load_loop"].wait_for_runs(1)
        clock.wait_for_sleepers(3)  # the log's minute, the sweep and the line, all waiting
        clock.advance(60)
        ctx["load_loop"].wait_for_runs(2)

    lines, result, _port = run_served(
        tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS="3",
                                 PENGUIN_SLICE_URL=nobody_listens()), use)
    assert result == [0]
    loads = [line for line in lines if line["event"] == "load"]
    assert len(loads) == 2
    assert loads[0]["threads"] == 3 and loads[0]["slices_followed"] == 0
    assert loads[0]["streams_open"] == 0 and loads[0]["threads_in_use"] >= 0
    assert [line["event"] for line in lines].count("sweep") == 1
    assert lines[-1]["event"] == "stop"


class _IdleTold:
    """The web server's condition its idle request threads wait on, announcing on `idle`
    each time a thread goes idle (waitress lowers its count of busy threads just before), so
    that a test waits for a count of busy threads by being told, never by looking again."""

    def __init__(self, condition, idle):
        self._condition = condition
        self._idle = idle

    def wait(self, *args):
        self._idle.announce()
        return self._condition.wait(*args)

    def __getattr__(self, name):
        return getattr(self._condition, name)


def keep_built(monkeypatch):
    """The applications `serve` builds, in a list, as each is built."""
    from penguin_front import server as served

    built = []
    real_build = served.build

    def keep(*args, **kwargs):
        built.append(real_build(*args, **kwargs))
        return built[-1]

    monkeypatch.setattr(served, "build", keep)
    return built


def open_page_stream(port, job):
    """Sign the development identity in over HTTP and open a page's progress stream on
    `job`; gives the client and the open answer once its first two events are read."""
    from front_helpers import DEV_GROUP

    page = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10)
    assert page.get("/signin").status_code == 302
    answer = page.send(page.build_request("GET", f"/api/slices/{job}/events",
                                          headers=DEV_GROUP), stream=True)
    assert answer.status_code == 200
    text, pieces = "", answer.iter_raw()
    while text.count("\n\n") < 2:
        text += next(pieces).decode()
    return page, answer


def test_threads_in_use_counts_the_request_thread_a_progress_stream_holds(tmp_path, clock,
                                                                          standin,
                                                                          monkeypatch):
    from front_fakes import Announcer
    from sliced_helpers import running

    built = keep_built(monkeypatch)
    standin.add_job("j1", "dev-user", "p", "s", running("j1", 5), file=b"sliced")

    def use(port, server):
        dispatcher = server.task_dispatcher
        idle = Announcer()
        dispatcher.queue_cv = _IdleTold(dispatcher.queue_cv, idle)
        page, answer = open_page_stream(port, "j1")
        try:
            ctx = built[0][0].extensions["penguin_front"]
            ctx["load_loop"].wait_for_runs(1)
            # The sign-in's thread is idle again; the stream's is held for as long as the
            # stream is open.
            idle.wait_for(lambda: dispatcher.active_count == 1, "one request thread busy")
            clock.wait_for_sleepers(4)  # the log, the sweep, the line and the stream
            clock.advance(60)
            ctx["load_loop"].wait_for_runs(2)
        finally:
            answer.close()
            page.close()

    lines, result, _port = run_served(
        tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS="3",
                                 PENGUIN_SLICE_URL=standin.url), use, with_server=True)
    assert result == [0]
    load = [line for line in lines if line["event"] == "load"][1]
    assert (load["slices_followed"], load["streams_open"], load["connections_open"]) == \
        (1, 1, 2)
    # The stream's request thread, and the following's thread counted among them.
    assert (load["threads"], load["threads_in_use"]) == (3, 2)


def test_the_running_servers_stop_ends_each_pages_progress_stream_before_its_stop_line(
        tmp_path, clock, standin):
    from sliced_helpers import running

    standin.add_job("j1", "dev-user", "p", "s", running("j1", 5), file=b"sliced")
    opened = []

    def use(port):
        opened.extend(open_page_stream(port, "j1"))

    try:
        lines, result, _port = run_served(
            tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS="3",
                                     PENGUIN_SLICE_URL=standin.url), use)
    finally:
        for each in reversed(opened):
            each.close()
    assert result == [0]
    events = [line["event"] for line in lines]
    [closed] = [line for line in lines if line["event"] == "stream_closed"]
    assert closed["why"] == "stopping" and closed["slice"] == "j1"
    assert events.index("stream_closed") < events.index("stop") == len(events) - 1


def test_the_running_server_collects_at_start_and_gathers_the_slice_services_lines(
        tmp_path, clock, standin, monkeypatch):
    from front_fakes import BACKSTOP_S
    from penguin_front.buckets import FolderBucket
    from sliced_helpers import FILE, SUMMARY, done, requests_to, write_submitted

    built = keep_built(monkeypatch)
    write_submitted(FolderBucket(tmp_path / "state", clock), "jdone", "2026-11-27T22:00:00Z",
                    group="dev-group")
    standin.add_job("jdone", "dev-user", "p", "s", done("jdone", 9), file=FILE,
                    summary=SUMMARY, ended_at="2026-11-27T22:13:58Z")
    standin.log_line("slice_job", state="done", job="jdone", user_key="dev-user")

    def use(_port):
        ctx = built[0][0].extensions["penguin_front"]
        assert ctx["collector"].collected.wait(BACKSTOP_S)
        standin.changes.wait_for(lambda: requests_to(standin, "DELETE", "/slices/jdone/file"),
                                 "the collected file's delete")
        ctx["gatherer"].loop.wait_for_runs(1)

    lines, result, _port = run_served(
        tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS="3",
                                 PENGUIN_SLICE_URL=standin.url), use)
    assert result == [0]
    assert "slices_collected" in [line["event"] for line in lines]
    written = [json.loads(line) for path in sorted((tmp_path / "log").rglob("*.jsonl"))
               for line in path.read_text().splitlines()]
    [gathered] = [line for line in written if line["component"] == "slice"]
    assert (gathered["event"], gathered["group"], gathered["n"]) == ("slice_job", "dev-group", 1)
    # The slice service's line is in its own output, not printed again by the front server.
    assert all(line["component"] == "front" for line in lines)


def test_a_start_without_a_cookie_key_makes_one_and_says_so_after_the_start_line(tmp_path,
                                                                                 clock):
    lines, result, _port = run_served(
        tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS="2"), lambda port: None)
    assert result == [0]
    assert [line["event"] for line in lines[:2]] == ["start", "cookie_key_made"]
    assert "memory" in lines[1]["detail"]


def test_a_start_with_a_cookie_key_makes_none(tmp_path, clock):
    lines, _result, _port = run_served(
        tmp_path, clock, environ(tmp_path, PENGUIN_FRONT_THREADS="2",
                                 PENGUIN_COOKIE_KEY="a-cookie-key-only-the-tests-use-7f3a"),
        lambda port: None)
    assert "cookie_key_made" not in [line["event"] for line in lines]


@pytest.fixture
def served(tmp_path, clock):
    """The application, with a planted `GET /t/x`, served by waitress on a port the system
    chooses; gives a function that sends one raw request line and gives (status, body)."""
    from penguin_front.app import create_app
    from penguin_front.settings import Settings

    lines = []

    class Lines:
        def write(self, event, **fields):
            lines.append({"event": event, **fields})

    app = create_app(Settings.from_environ(environ(tmp_path)), clock=clock,
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
