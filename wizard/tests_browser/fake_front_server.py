"""A small fake front server for the browser tests: it serves the built page from wizard/dist/
as the contract says the front server does (`GET /` with the version filled in and the
content security policy, `GET /assets/<file>` as found), on a port the system chooses.

The skeleton batch grows it to answer the contract's requests in the contract's shapes.
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PLACEHOLDER = "__PENGUINSLICER_VERSION__"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
    "font-src 'self'; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
TYPES = {".js": "text/javascript", ".css": "text/css", ".html": "text/html; charset=utf-8",
         ".woff2": "font/woff2", ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json"}


class FakeFrontServer:
    def __init__(self, dist, version="20261127T221405Z-0000000"):
        self.dist = Path(dist)
        self.version = version
        self.page = (self.dist / "index.html").read_text(encoding="utf-8").replace(PLACEHOLDER, version)
        self.requests = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server.requests.append(self.path)
                if self.path == "/":
                    self.answer(200, TYPES[".html"], server.page.encode("utf-8"), page=True)
                    return
                name = self.path.removeprefix("/assets/")
                asset = server.dist / "assets" / name
                if self.path.startswith("/assets/") and "/" not in name and asset.is_file():
                    self.answer(200, TYPES.get(asset.suffix, "application/octet-stream"), asset.read_bytes())
                else:
                    self.answer(404, "text/plain", b"not found")

            def answer(self, status, content_type, body, page=False):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-PenguinSlicer-Version", server.version)
                if page:
                    self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()
