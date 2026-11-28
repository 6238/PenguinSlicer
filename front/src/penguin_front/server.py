"""Starting and running the front server: the settings, the two buckets, the log and the
application, served by waitress in one process with a fixed pool of threads
(README-details.md, "Threads").

A start writes the `start` line with the version; a stop (Ctrl-C, or `SIGTERM` as at every
deploy) ends the serving, writes the `stop` line, and writes what the log has gathered.
Finishing work in flight when asked to stop is phase 3's (README-details.md, "Stopping").
"""

import signal
import threading

import waitress
from waitress import wasyncore

from .app import EXTENSION, create_app
from .buckets import FolderBucket
from .clock import RealClock
from .log import Log
from .settings import Settings, SettingError
from .version import version_at


def build(settings, *, clock, stdout):
    """The application and its log, on the folders that stand for the two buckets."""
    log = Log(clock, stdout, FolderBucket(settings.log_dir, clock))
    version = settings.version or version_at(clock.now())
    app = create_app(settings, clock=clock, log=log, version=version)
    app.extensions[EXTENSION]["state_bucket"] = FolderBucket(settings.state_dir, clock)
    return app, log


def serve(args, *, environ=None, stdout, stderr, clock=None, on_listening=None):
    """Serve until stopped; 0 on a stop, 2 when a setting is refused."""
    try:
        settings = Settings.from_environ(environ)
    except SettingError as exc:
        print(f"penguin_front serve: {exc}", file=stderr, flush=True)
        return 2
    clock = clock or RealClock()
    app, log = build(settings, clock=clock, stdout=stdout)
    server = waitress.create_server(app, host=args.host, port=args.port,
                                    threads=settings.threads, ident="")
    log.write("start", version=app.extensions[EXTENSION]["version"], host=args.host,
              port=int(server.effective_port), threads=settings.threads,
              dev_identity=settings.dev_identity)
    log.start()
    (on_listening or _nothing)(server)
    try:
        with _stop_on_signals():
            server.run()
    finally:
        server.task_dispatcher.shutdown()
        log.write("stop")
        log.stop()
    return 0


def _nothing(_server):
    """No one to tell that the server listens."""


def stop_server(server):
    """End `server.run()` from any thread, as a signal does."""
    server.trigger.pull_trigger(lambda: wasyncore.close_all(server._map))


class _stop_on_signals:
    """`SIGINT` and `SIGTERM` end the serving while the block runs (main thread only)."""

    SIGNALS = (signal.SIGINT, signal.SIGTERM)

    def __enter__(self):
        self._previous = {}
        if threading.current_thread() is threading.main_thread():  # pragma: no cover
            for sig in self.SIGNALS:
                self._previous[sig] = signal.signal(sig, _interrupt)

    def __exit__(self, *_exc):
        for sig, old in self._previous.items():  # pragma: no cover - the main thread only
            signal.signal(sig, old)


def _interrupt(_signum, _frame):  # pragma: no cover - a signal at the command line
    raise KeyboardInterrupt
