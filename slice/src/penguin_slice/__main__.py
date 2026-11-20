"""The slice service's one command: run its HTTP interface.

    uv run python -m penguin_slice serve --work <dir> [--host 127.0.0.1] [--port 8640]

`serve` runs the HTTP interface (web.py) until it is stopped, writing one JSON log line per
slice job transition on stderr; Ctrl-C and SIGTERM (what a container host sends) both end
it the same way: it cancels every slice job, waits until every Orca is gone, and exits 0. A
setting it refuses (limits.SettingError) stops it at start, before it listens, with a
message naming the setting on stderr and exit status 2.
"""
import argparse
import contextlib
import ctypes
import json
import signal
import sys

from .limits import SettingError

DEFAULT_PORT = 8640
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)
M_ARENA_MAX = -8          # glibc's mallopt parameter for the most malloc arenas
MALLOC_ARENAS = 2         # the request threads' and the slice jobs' threads share these


def cap_malloc_arenas(libc=None):
    """Cap glibc's malloc arenas at MALLOC_ARENAS (as MALLOC_ARENA_MAX would); True when set.

    Each thread that allocates gets an arena of its own, up to 8 per CPU, and an arena keeps
    what it freed: with a new thread per request and per slice job, a slice service process
    that had served 16 of the largest plates in a row peaked at 365 MB, against 178 MB on its
    first; with the cap, 261 MB (see the guide's "The cost of the largest plate"). A C library
    without mallopt (macOS) is left alone."""
    libc = ctypes.CDLL(None) if libc is None else libc
    mallopt = getattr(libc, "mallopt", None)
    return mallopt is not None and mallopt(M_ARENA_MAX, MALLOC_ARENAS) == 1


@contextlib.contextmanager
def _on_signals(handler):
    """`handler(signum, frame)` for SIGINT and SIGTERM while the block runs, then the old ones."""
    previous = {sig: signal.signal(sig, handler) for sig in STOP_SIGNALS}
    try:
        yield
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)


def _interrupt(_signum, _frame):
    raise KeyboardInterrupt


def serve(args, stderr):
    from .web import create_app

    def log(entry):
        print(json.dumps(entry, default=str), file=stderr, flush=True)

    cap_malloc_arenas()
    try:
        app = create_app(args.work, log=log)
    except SettingError as exc:
        print(f"penguin_slice serve: {exc}", file=stderr, flush=True)
        return 2
    try:
        with _on_signals(_interrupt):       # SIGTERM takes Ctrl-C's way out
            app.run(host=args.host, port=args.port, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        app.extensions["penguin_slice_pool"].shutdown()
    return 0


def main(argv=None, stderr=None):
    stderr = stderr or sys.stderr
    parser = argparse.ArgumentParser(prog="python -m penguin_slice", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    serve_cmd = commands.add_parser("serve", help="run the HTTP interface")
    serve_cmd.add_argument("--work", required=True, help="the directory every slice job's files live in")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    return serve(args, stderr)


if __name__ == "__main__":
    sys.exit(main())
