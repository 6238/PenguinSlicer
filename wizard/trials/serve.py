#!/usr/bin/env python3
"""Serve the trials' pages: wizard/trials/ at /, wizard/vendor/ at /vendor/, and the real
parts (contracts/examples/parts/real/) at /parts/real/.

`make -C wizard trials-serve` runs it on 127.0.0.1:8610 for the owner's timing in Chrome on
the Mac (HOST=0.0.0.0 to reach it from another machine). A trial's measuring script calls
make_server(host, 0) for a port the system chooses. Nothing outside the three folders is
served, every answer says not to cache it, and only GET and HEAD are answered.
"""
import argparse
import posixpath
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

WIZARD = Path(__file__).resolve().parent.parent
TRIALS = WIZARD / "trials"
ROOTS = [                                     # (prefix, folder), the longest prefix first
    ("/parts/real/", WIZARD.parent / "contracts" / "examples" / "parts" / "real"),
    ("/vendor/", WIZARD / "vendor"),
    ("/", TRIALS),
]
NOWHERE = None                                # what translate_path gives for a path not served


class TrialsHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
                      ".stl": "model/stl", ".3mf": "model/3mf", ".gcode": "text/plain",
                      ".wasm": "application/wasm"}

    def translate_path(self, path):
        path = unquote(urlsplit(path).path)
        if "\0" in path or any(part == ".." for part in path.split("/")):
            return NOWHERE
        path = posixpath.normpath(path) + ("/" if path.endswith("/") and path != "/" else "")
        for prefix, folder in ROOTS:
            if path == prefix.rstrip("/") or path.startswith(prefix):
                target = (folder / path[len(prefix):]).resolve()
                if target != folder.resolve() and not target.is_relative_to(folder.resolve()):
                    return NOWHERE
                return str(target)
        return NOWHERE

    def send_head(self):
        if self.translate_path(self.path) is NOWHERE:
            self.send_error(404, "File not found")
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, "File not found")
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def make_server(host, port):
    """A server on (host, port), already bound; port 0 lets the system choose."""
    return ThreadingHTTPServer((host, port), partial(TrialsHandler, directory=str(TRIALS)))


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8610)
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    httpd = make_server(args.host, args.port)
    host, port = httpd.server_address[:2]
    print(f"Serving wizard/trials/ on http://{host}:{port}/ (Ctrl-C stops it)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
