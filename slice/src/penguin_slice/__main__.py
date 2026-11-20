"""The slice service's command line.

    uv run python -m penguin_slice slice <plate-job.json> --out <dir>
    uv run python -m penguin_slice serve --work <dir> [--host 127.0.0.1] [--port 8640]

`slice` prints the sliced file's summary as JSON on stdout and exits 0, or prints the
error report as JSON on stderr and exits 1; Ctrl-C or SIGTERM stops Orca, removes the
scratch folder and ends with the slice.cancelled error report. `serve` runs the HTTP face
(web.py) until it is stopped, writing one JSON log line per job transition on stderr;
Ctrl-C and SIGTERM (what a container host sends) both end it the same way: it cancels
every job, waits until every Orca is gone, and exits 0.
"""
import argparse
import contextlib
import json
import os
import signal
import sys
import threading

from .errors import error_report
from .service import slice_plate_job
from .slicer import Stop

DEFAULT_PORT = 8640
STOP_SIGNALS = (signal.SIGINT, signal.SIGTERM)


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


@contextlib.contextmanager
def _stop_on_signals(stop):
    """SIGINT and SIGTERM set `stop` while the block runs, and can never hang the command.
    The handler runs on the main thread at whatever point it was interrupted, possibly
    holding the Stop's lock (inside set() or listen()), so it takes no lock: it only writes
    the signal's number to a pipe. A relay thread reads the pipe and calls stop.set(); it
    ends when the block ends (the pipe's write end is closed)."""
    read_fd, write_fd = os.pipe()
    os.set_blocking(write_fd, False)

    def record(signum, _frame):
        with contextlib.suppress(BlockingIOError):      # a full pipe holds stops already asked
            os.write(write_fd, bytes([signum]))

    def relay():
        while True:
            data = os.read(read_fd, 64)
            if not data:
                return
            for signum in data:
                stop.set(f"interrupted by {signal.Signals(signum).name}")

    thread = threading.Thread(target=relay, name="slice-signal-relay", daemon=True)
    thread.start()
    try:
        with _on_signals(record):
            yield
    finally:
        os.close(write_fd)
        thread.join()
        os.close(read_fd)


def serve(args, stderr):
    from .web import create_app

    def log(entry):
        print(json.dumps(entry, default=str), file=stderr, flush=True)

    app = create_app(args.work, log=log)
    try:
        with _on_signals(_interrupt):       # SIGTERM takes Ctrl-C's way out
            app.run(host=args.host, port=args.port, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        app.extensions["penguin_slice_pool"].shutdown()
    return 0


def slice_once(args, stdout, stderr):
    stop = Stop()
    try:
        with _stop_on_signals(stop):
            sliced = slice_plate_job(args.plate_job, args.out, stop=stop)
    except Exception as exc:  # every failure leaves as an error report
        print(json.dumps(error_report(exc), indent=2), file=stderr)
        return 1
    print(json.dumps(sliced.summary, indent=2), file=stdout)
    return 0


def main(argv=None, stdout=None, stderr=None):
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = argparse.ArgumentParser(prog="python -m penguin_slice", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    slice_cmd = commands.add_parser("slice", help="slice a plate job into a sliced file")
    slice_cmd.add_argument("plate_job", help="the plate job file (JSON)")
    slice_cmd.add_argument("--out", required=True, help="the directory the sliced file is written to")
    serve_cmd = commands.add_parser("serve", help="run the HTTP face")
    serve_cmd.add_argument("--work", required=True, help="the directory every job's files live in")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    if args.command == "serve":
        return serve(args, stderr)
    return slice_once(args, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
