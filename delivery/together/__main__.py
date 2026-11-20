"""Send a sample sliced file through the relay and the daemon to the stand-in printer.

    make -C delivery together              # over loopback HTTP, on an ephemeral port
    make -C delivery together ARGS=--in-process

Everything runs in this one process: the relay app (served by werkzeug on 127.0.0.1 and a
port the system picks, or called in-process), the daemon's real run loop on its own thread,
the stand-in printer, and a caller that does what a real caller's page does: poll the
status, send the job, and watch it finish. Every state change is printed. The exit status
is 0 when the stand-in printer received the very bytes of the sliced file and the relay
recorded the job as acknowledged, 1 otherwise.

The daemon's clock runs `--speed` times faster than real time, so its five-second syncs
take a quarter of a second at the default speed of twenty. Nothing is written outside a
temporary directory that is removed at the end.
"""

import argparse
import os
import secrets
import shutil
import sys
import tempfile
import threading
import time

import requests
from werkzeug.serving import WSGIRequestHandler, make_server

from penguin_delivery_daemon.config import DaemonConfig
from penguin_delivery_daemon.relay_client import RelayClient
from penguin_delivery_daemon.run_loop import RunLoop
from penguin_delivery_relay import SlicedFile, Team, create_app, error_report

from together.stand_in import StandInPrinter
from together.transport import InProcessSession

#: An obviously fake pairing code, valid in the relay's alphabet.
PAIRING_CODE = 'DEM0C0DE'
SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sample_part.gcode.3mf')
SEND_TOKEN = 'sample'


class QuietRequestHandler(WSGIRequestHandler):
    """No access log: a download path carries the job's download token, a bearer
    credential, and werkzeug would print it on every download."""

    def log_request(self, *args, **kwargs):
        pass


class Stopped(BaseException):
    """Ends the daemon's run loop. A BaseException, like KeyboardInterrupt, so neither the
    loop's nor the job's `except Exception` mistakes it for a failure."""


class Printer:
    """One printed line per event, with the seconds since the start, from any thread."""

    def __init__(self, out):
        self._out = out
        self._lock = threading.Lock()
        self._started = time.monotonic()

    def __call__(self, who, *parts):
        text = ' '.join(str(p) for p in parts)
        with self._lock:
            print(f"{time.monotonic() - self._started:6.2f}s  {who:<7} {text}",
                  file=self._out, flush=True)


class WatchedRelayClient(RelayClient):
    """The daemon's real client, printing the moment a sync hands a job out: the relay
    moves the job from pending to handed_out inside that sync, between two of the
    caller's polls, and logs nothing for it."""

    def __init__(self, *args, say, **kwargs):
        super().__init__(*args, **kwargs)
        self._say = say
        self._seen = set()

    def sync(self, snapshot, job_progress=None):
        job = super().sync(snapshot, job_progress)
        if job and job['id'] not in self._seen:
            self._seen.add(job['id'])
            self._say('daemon', f"sync handed out job {job['id']} (pending -> handed_out)")
        return job


def build_relay(sliced_path, say, clock):
    team = Team(pairing_code=PAIRING_CODE, team_number=None, user='together')
    sliced = SlicedFile(filename=os.path.basename(sliced_path), path=sliced_path)

    return create_app(
        secret_key=secrets.token_hex(16),
        clock=clock,
        identify=lambda request: team,
        find_sliced_file=lambda token, team: sliced if token == SEND_TOKEN else None,
        log=lambda *parts: say('relay', *parts),
        dev=True,                      # plain HTTP on loopback
        trusted_proxy_hops=0)


def describe(status):
    """The parts of a status answer that make a state change worth printing."""
    if 'error' in status:
        return f"status refused: {status['error']}"
    job = status.get('job')
    printer = status.get('status')
    last = status.get('last_result')
    parts = ['online' if status.get('online') else
             ('waiting for the daemon' if status.get('waiting') else 'offline')]
    if printer:
        parts.append(f"printer {printer['state']}"
                     + (f" {printer['display_name']}" if printer.get('display_name') else ''))
    parts.append(f"job {job['id']} {job['state']}" if job else 'no job')
    if last:
        parts.append('last result ok' if last['ok'] else
                     f"last result failed: {last['reason']} "
                     f"[{error_report(last['reason'])['code']}]")
    return ', '.join(parts)


def run(*, sliced_path=SAMPLE, in_process=False, speed=20.0, timeout=30.0, out=sys.stdout):
    say = Printer(out)
    # Both halves run on the same sped-up time, so the relay's deadlines and rate-limit
    # windows shrink with the daemon's intervals and the caller can poll often.
    app = build_relay(sliced_path, say, clock=lambda: time.time() * speed)
    server = None
    if in_process:
        base_url = 'http://relay.test'
        caller = daemon_session = InProcessSession(app)
    else:
        server = make_server('127.0.0.1', 0, app, threaded=True,
                             request_handler=QuietRequestHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base_url = f'http://127.0.0.1:{server.server_port}'
        caller, daemon_session = requests.Session(), requests.Session()
    say('relay', f'listening at {base_url}' if server else 'called in-process')

    scratch = tempfile.mkdtemp(prefix='penguin-delivery-together-')
    stop = threading.Event()

    def daemon_sleep(seconds):
        if stop.wait(seconds / speed):
            raise Stopped()

    printer = StandInPrinter(on_change=lambda text: say('printer', text))
    config = DaemonConfig(backend_url=base_url, pairing_code=PAIRING_CODE, dev=True,
                          path=os.path.join(scratch, 'config.toml'))
    loop = RunLoop(config, WatchedRelayClient(base_url, session=daemon_session, say=say),
                   printer,
                   clock=lambda: time.monotonic() * speed, sleep=daemon_sleep,
                   log=lambda *parts: say('daemon', *parts),
                   download_dir=scratch, save_token=lambda token, path: None)

    def run_daemon():
        try:
            loop.run_forever()
        except Stopped:
            pass

    def status():
        return caller.get(f'{base_url}/printer/status').json()

    deadline = time.monotonic() + timeout
    seen = [None]

    def watch(until):
        """Poll the status as a page would, print each change, until `until(status)`."""
        while time.monotonic() < deadline:
            current = status()
            text = describe(current)
            if text != seen[0]:
                say('caller', text)
                seen[0] = text
            if until(current):
                return current
            time.sleep(0.02)
        return None

    daemon_thread = threading.Thread(target=run_daemon, daemon=True)
    try:
        watch(lambda s: True)                     # the first poll presents the code
        daemon_thread.start()
        if watch(lambda s: s.get('online') and s['status']['state'] == 'idle') is None:
            say('caller', 'the daemon never came online')
            return 1
        sent = caller.post(f'{base_url}/printer/jobs', json={'token': SEND_TOKEN})
        say('caller', f'send answered {sent.status_code}: {sent.json()}')
        if sent.status_code != 202:
            return 1
        job_id = sent.json()['job_id']

        result = {}

        def finished(s):
            """The job's result is in, and for a success the printer's next report shows
            our file printing. The relay drops a successful result as soon as a sync names
            the job, so the result is remembered from the poll that first showed it."""
            if 'last_result' not in s:
                return False                      # a refused poll, e.g. rate limited
            if s['last_result'] is not None:
                result.setdefault('ok', s['last_result']['ok'])
            if 'ok' not in result:
                return False
            return (not result['ok']) or (s['status']['state'] == 'running'
                                          and job_id in s['status']['file'])

        if watch(finished) is None:
            say('caller', f'no result within {timeout:.0f}s')
            return 1
        with open(sliced_path, 'rb') as fh:
            expected = fh.read()
        printed = [name for name in printer.started if job_id in name]
        ok = (result['ok'] and len(printed) == 1
              and printer.received.get(printed[0]) == expected)
        say('caller', ('PASS: ' if ok else 'FAIL: ') +
            f'job {job_id} reached the stand-in printer as {printed} '
            f'({len(expected)} bytes, {"identical" if ok else "not as sent"})')
        return 0 if ok else 1
    finally:
        stop.set()
        if daemon_thread.is_alive():
            daemon_thread.join(timeout=5)
        loop.executor.shutdown(wait=True)
        if server is not None:
            server.shutdown()
            server.server_close()
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m together', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', default=SAMPLE,
                        help='the sliced file to send (default: the placeholder sample)')
    parser.add_argument('--in-process', action='store_true',
                        help='call the relay app directly instead of over loopback HTTP')
    parser.add_argument('--speed', type=float, default=20.0,
                        help="how many times faster than real time the daemon's clock runs")
    parser.add_argument('--timeout', type=float, default=30.0)
    args = parser.parse_args(argv)
    return run(sliced_path=os.path.abspath(args.file), in_process=args.in_process,
               speed=args.speed, timeout=args.timeout)


if __name__ == '__main__':
    sys.exit(main())
