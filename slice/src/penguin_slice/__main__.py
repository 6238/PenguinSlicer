"""The slice service's one command: run its HTTP interface.

    uv run python -m penguin_slice serve --work <dir> [--host 127.0.0.1] [--port 8640]

`serve` runs the HTTP interface (web.py) on a threaded server, writing one JSON log line for
each slice job transition and each of its own on stderr, until it is asked to stop. Ctrl-C
and SIGTERM (what a container host sends) are the same request to stop
(slice/README-details.md, "Asked to stop"):

1. The first ends every waiting slice job early (cancel_reason "shutdown"), answers every new
   plate configuration slice.stopping, lets the running slice job run to its end, and keeps
   answering every request until no done slice job still holds a sliced file the front
   server has not collected (DELETE /slices/<job>/file); then it exits 0.
2. A second also ends the running slice job early ("shutdown") and exits 0 once Orca is gone,
   without waiting for any sliced file to be collected; such a file is lost with the process.

A setting it refuses (limits.SettingError) stops it at start, before it listens, with a
message naming the setting on stderr and exit status 2; an address it cannot listen on, with
exit status 1.
"""
import argparse
import contextlib
import ctypes
import json
import os
import queue
import signal
import sys
import threading

from werkzeug.serving import make_server

from .limits import SettingError

DEFAULT_PORT = 8640
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)
M_ARENA_MAX = -8          # glibc's mallopt parameter for the most malloc arenas
MALLOC_ARENAS = 2         # the request threads' and the slice jobs' threads share these
STOP, DRAINED = "stop", "drained"     # what run_until_stopped waits for, in its queue


def cap_malloc_arenas(libc=None):
    """Cap glibc's malloc arenas at MALLOC_ARENAS (as MALLOC_ARENA_MAX would); True when set.

    Each thread that allocates gets an arena of its own, up to 8 per CPU, and an arena keeps
    what it freed: with a new thread per request and per slice job, a slice service process
    that had served 16 of the largest plates in a row peaked at 365 MB, against 178 MB on its
    first; with the cap, 261 MB (see slice/README-details.md, "The cost of the largest plate"). A C library
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


def run_until_stopped(pool, events, log):
    """Wait for the first STOP in `events` (a queue.SimpleQueue, which a signal handler may
    put into), then stop as the module says: "drained" once the pool is drained, or
    "second_stop" at a second STOP. Either way the pool is shut down when it returns."""
    while events.get() != STOP:
        pass
    ended = pool.stop()
    drained = pool.drained()
    log({"event": "slice_service_stopping", "stop": 1, "waiting_ended": ended, "drained": drained})
    how = "drained"
    if not drained:
        def tell_when_drained():
            pool.wait_drained()
            events.put(DRAINED)
        threading.Thread(target=tell_when_drained, name="slice-stop-drain", daemon=True).start()
        if events.get() == STOP:
            how = "second_stop"
            log({"event": "slice_service_stopping", "stop": 2})
    pool.shutdown()          # at a second stop, ends the running slice job early and waits until Orca is gone
    lost = [entry["job"] for entry in pool.listing() if entry["file_on_disk"]]
    log({"event": "slice_service_stopped", "how": how, "files_lost": lost})
    return how


def serve(args, stderr):
    from .web import create_app

    def write(entry):
        print(json.dumps(entry, default=str), file=stderr, flush=True)

    cap_malloc_arenas()
    try:
        app = create_app(args.work, log=write)
    except SettingError as exc:
        print(f"penguin_slice serve: {exc}", file=stderr, flush=True)
        return 2
    pool, log = app.extensions["penguin_slice_pool"], app.extensions["penguin_slice_log"]
    events = queue.SimpleQueue()          # put() is safe in a signal handler
    with _on_signals(lambda _signum, _frame: events.put(STOP)):
        try:
            server = make_server(args.host, args.port, app, threaded=True)
        except OSError as exc:
            print(f"penguin_slice serve: cannot listen on {args.host}:{args.port}: {exc}", file=stderr, flush=True)
            pool.shutdown()
            return 1
        listening = threading.Thread(target=server.serve_forever, name="slice-http", daemon=True)
        listening.start()
        log({"event": "slice_service_started", "host": args.host, "port": server.server_port, "pid": os.getpid()})
        try:
            run_until_stopped(pool, events, log)
        finally:
            server.shutdown()
            server.server_close()
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
