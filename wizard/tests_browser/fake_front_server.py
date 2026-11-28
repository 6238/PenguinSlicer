"""A small fake front server for the browser tests: it serves the built page from wizard/dist/
as the contract says the front server does (`GET /` with the version filled in and the
content security policy, `GET /assets/<file>` as found), and answers the contract's requests in
the contract's shapes, its default answers taken whole from contracts/examples/ (but for an
upload, answered with the record of the bytes sent), on a port the system chooses. Every answer carries `X-PenguinSlicer-Version`; every answer but the page
files carries `Cache-Control: no-store`.

A test sets what the next requests to a path meet with `script(method, path, *answers)`: each
answer is `(status, body)` or `(status, body, headers)`, the body a dict sent as JSON, bytes sent
as they are (a sliced file; the default answer of `GET /api/slices/<slice>/file` is a real one), or a
progress stream, `stream(text, ...)`: server-sent events written at once, then the stream closed,
or with `hold=True` left open until the test calls `release()` or the server stops (the default
answer of `GET /api/slices/<slice>/events` is the contract's example of a stream, closed). The
requests are recorded with their headers and their bodies. `files` maps a path to bytes that a
test's own code fetches (a part's STL file, which in use comes from the user's disk).
"""
import hashlib
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PLACEHOLDER = "__PENGUINSLICER_VERSION__"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
    "font-src 'self'; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
TYPES = {".js": "text/javascript", ".css": "text/css", ".html": "text/html; charset=utf-8",
         ".woff2": "font/woff2", ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json"}
EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"
# The sliced file answered by default for `GET /api/slices/<slice>/file`: a real one, made by Orca
# through the slice service (wizard/tests/sliced/README.md), under the example details' name.
SLICED = Path(__file__).resolve().parents[1] / "tests" / "sliced" / "spacer-1.gcode.3mf"


def example(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


class stream:
    """A progress stream's answer: `chunks` (texts of server-sent events) written at once; then the
    stream is closed, or with `hold` left open until `release()` or the server's stop."""

    def __init__(self, *chunks, hold=False):
        self.chunks = chunks
        self.hold = hold
        self.released = threading.Event()

    def release(self):
        self.released.set()


def progress_event(report):
    return f"event: progress\nid: {report['sequence']}\ndata: {json.dumps(report)}\n\n"


def version_event(version):
    return f"event: version\ndata: {json.dumps({'version': version})}\n\n"


EXAMPLE_EVENTS = (EXAMPLES / "wizard-front" / "slice-events.txt").read_text(encoding="utf-8")


def error_report(code, **fields):
    """An error report in the contract's shape, with sentences the test makes up."""
    return {"code": code, "message": f"The fake front server's sentence of what happened for {code}.",
            "remedy": f"The fake front server's sentence of what to do for {code}.",
            "retryable": False, "detail": f"fake detail for {code}, never shown", **fields}


def part_record_of(path, body):
    """The part's record a front server answers for an upload: the example's, with the hash of the
    bytes sent and the units label of the query, and no warning; a test that wants a warning or a
    refusal scripts it."""
    units = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query).get("units", [None])[0]
    return {**example("wizard-front/part-record.json"), "sha256": hashlib.sha256(body).hexdigest(),
            "units": units, "warnings": []}


def default_answer(method, path, body=b""):
    route = path.split("?")[0]
    if method == "GET" and route == "/api/me":
        return 200, example("wizard-front/me.json")
    if method == "GET" and route == "/api/configuration":
        return 200, {"configuration": example("configuration-default.json"), "source": "default",
                     "name": "PenguinSlicer default", "revision": None}
    if method == "PUT" and route == "/api/configuration":
        return 200, example("wizard-front/configuration-written.json")
    if method == "GET" and route == "/api/settings-table":
        return 200, example("settings-table.json")
    if method == "POST" and route == "/api/parts":
        return 201, part_record_of(path, body)
    if method == "POST" and route == "/api/slices":
        return 202, example("wizard-front/slice-accepted.json")
    if method == "GET" and route.startswith("/api/slices/") and route.endswith("/summary"):
        return 200, example("wizard-front/slice-summary.json")
    if method == "GET" and route.startswith("/api/slices/") and route.endswith("/file"):
        name = example("wizard-front/slice-summary.json")["sliced_file"]["file"]
        return 200, SLICED.read_bytes(), {"Content-Disposition": f'attachment; filename="{name}"'}
    if method == "GET" and route.startswith("/api/slices/") and route.count("/") == 3:
        return 200, example("wizard-front/slice-done.json")
    if method == "POST" and route in ("/api/reports/failure", "/api/reports/drawing"):
        return 204, None
    return 404, error_report("front.no_such_request")


class FakeFrontServer:
    def __init__(self, dist, version="20261127T221405Z-0000000"):
        self.dist = Path(dist)
        self.version = version
        self.page = (self.dist / "index.html").read_text(encoding="utf-8").replace(PLACEHOLDER, version)
        self.requests = []
        self.request_headers = []
        self.bodies = []                # (method, path, the request's body as bytes)
        self.files = {}                 # path: bytes, served to a test's own fetch (a part's STL file)
        self.scripts = {}
        self.lock = threading.Lock()
        self.stopping = threading.Event()        # set at the stop, which ends every stream held open
        self.held = []
        # True once a deploy has replaced the page files: this release's assets are answered 404,
        # as the new front server answers a name it does not have
        self.assets_gone = False
        server = self

        class Handler(BaseHTTPRequestHandler):
            def handle_any(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                with server.lock:
                    server.requests.append(self.path)
                    server.request_headers.append((method, self.path, {k.lower(): v for k, v in self.headers.items()}))
                    server.bodies.append((method, self.path, body))
                    queue = server.scripts.get((method, self.path.split("?")[0]))
                    scripted = queue.pop(0) if queue else None
                    test_file = server.files.get(self.path) if method == "GET" else None
                if test_file is not None:
                    self.answer(200, "application/octet-stream", test_file)
                    return
                if method == "GET" and self.path == "/":
                    self.answer(200, TYPES[".html"], server.page.encode("utf-8"), page=True)
                    return
                if method == "GET" and self.path.startswith("/assets/"):
                    name = self.path.removeprefix("/assets/")
                    asset = server.dist / "assets" / name
                    if "/" not in name and asset.is_file() and not server.assets_gone:
                        self.answer(200, TYPES.get(asset.suffix, "application/octet-stream"), asset.read_bytes(),
                                    cache="private, max-age=31536000, immutable")
                    else:
                        self.json(404, error_report("front.no_such_request"))
                    return
                route = self.path.split("?")[0]
                if scripted is None and method == "GET" and route.startswith("/api/slices/") and route.endswith("/events"):
                    scripted = stream(EXAMPLE_EVENTS)
                if isinstance(scripted, stream):
                    self.stream(scripted)
                    return
                answer = scripted if scripted is not None else default_answer(method, self.path, body)
                status, content, *rest = answer
                if isinstance(content, bytes):
                    self.answer(status, "application/octet-stream", content, headers=rest[0] if rest else {})
                else:
                    self.json(status, content, rest[0] if rest else {})

            def stream(self, answer):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("X-PenguinSlicer-Version", server.version)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    for chunk in answer.chunks:
                        self.wfile.write(chunk.encode("utf-8"))
                        self.wfile.flush()
                    if answer.hold:
                        with server.lock:
                            server.held.append(answer)
                            if server.stopping.is_set():
                                answer.release()
                        answer.released.wait()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                self.close_connection = True

            def do_GET(self):
                self.handle_any("GET")

            def do_POST(self):
                self.handle_any("POST")

            def do_PUT(self):
                self.handle_any("PUT")

            def do_DELETE(self):
                self.handle_any("DELETE")

            def json(self, status, body, headers=None):
                data = b"" if body is None else json.dumps(body).encode("utf-8")
                self.answer(status, "application/json", data, headers=headers or {})

            def answer(self, status, content_type, body, page=False, cache="no-store", headers=None):
                self.send_response(status)
                if body or status != 204:
                    self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-PenguinSlicer-Version", server.version)
                self.send_header("Cache-Control", "private, no-cache" if page else cache)
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                if page:
                    self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        # A short poll, so that shutting the server down at the end of a test is quick.
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)

    def script(self, method, path, *answers):
        with self.lock:
            self.scripts.setdefault((method, path), []).extend(answers)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        with self.lock:
            self.stopping.set()
            for answer in self.held:
                answer.release()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()
