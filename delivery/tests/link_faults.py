"""A fault-injecting link between the daemon and the relay, and a shop to drive through it.

`FaultyLink` is a `requests`-shaped session (like together/transport.py's) that hands each
request to the relay app in the same process, unless a scripted fault says otherwise:

| Fault | What the daemon sees |
|---|---|
| `timeout` | the request times out; the relay never saw it |
| `late` | the relay handled it, but the answer came after the timeout |
| `reset_before` / `reset_after` | the connection is reset before / after the relay handled it |
| `dns` / `tls` | the name does not resolve / the secure connection fails |
| `500`, `502`, `503` | the relay or its proxy fails (502 and 503 as an HTML page) |
| `429` / `429_hint` | rate limited without / with a Retry-After of 7 s |
| `html` | a captive portal's page with status 200 |
| `truncated` | JSON cut off partway |
| `wrong_shape` | JSON, but a list |
| `duplicate` | the request reaches the relay twice |
| `slow` | the answer takes 15 s (inside the timeout) |
| `stop_partway`, `stall`, `wrong_length`, `wrong_content` | the download breaks, stalls, or delivers the wrong bytes |

The link can also be down until a time on the shared clock, or flap. Faults are queued per
exchange (`pair`, `sync`, `ack`, `start`, `download`) and each is used once.

`Shop` puts a relay, one or more daemons (the real RunLoop and RelayClient), the stand-in
printer and a caller on two fake clocks that move together, and `drive` runs them second by
second with no real waiting.
"""

import json as json_module
from urllib.parse import urlsplit

import requests

from penguin_delivery_daemon.config import DaemonConfig
from penguin_delivery_daemon.relay_client import RelayClient
from penguin_delivery_daemon.run_loop import InlineExecutor, RunLoop
from penguin_delivery_relay import relay_of

import daemon_fakes
import relay_fakes
from together.stand_in import StandInPrinter
from together.transport import InProcessResponse

BASE = 'https://relay.test'
CONTENT = b'sliced bytes for the stand-in printer' * 10

FAULTS = ('timeout', 'late', 'reset_before', 'reset_after', 'dns', 'tls', '500', '502',
          '503', '429', '429_hint', 'html', 'truncated', 'wrong_shape', 'duplicate', 'slow')
DOWNLOAD_FAULTS = ('stop_partway', 'stall', 'wrong_length', 'wrong_content')
EXCHANGES = ('pair', 'sync', 'ack', 'start', 'download')
#: The most simulated seconds one daemon's job thread may sleep in a Shop test.
JOB_SLEEP_LIMIT_SECONDS = 12 * 3600


def exchange_of(path):
    if path.startswith('/printer/download/'):
        return 'download'
    if path.endswith('/ack'):
        return 'ack'
    if path.endswith('/start'):
        return 'start'
    return path.rsplit('/', 1)[-1]


class DaemonDied(BaseException):
    """Raised from a hook to stand in for the daemon process being killed at that point:
    no `except Exception` in the daemon catches it, and the Shop starts a new process."""


def die():
    raise DaemonDied()


class Canned:
    """A response made up by the link, read the way RelayClient reads one."""

    def __init__(self, status, text, content_type, headers=None, chunks=None):
        self.status_code = status
        self.text = text
        self.headers = {'Content-Type': content_type, **(headers or {})}
        self._chunks = chunks

    def json(self):
        return json_module.loads(self.text)

    def iter_content(self, chunk_size=8192):
        for chunk in self._chunks or [self.text.encode()]:
            if isinstance(chunk, BaseException):
                raise chunk
            yield chunk

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FaultyLink:
    def __init__(self, app, clock):
        self.app = app
        self.client = app.test_client()
        self.clock = clock
        self.plan = {name: [] for name in EXCHANGES}
        self.before = {}                # exchange -> a one-shot callback run before it
        self.down_until = None
        self.flap_period = None
        self.calls = []
        self.delivered = []

    def use_app(self, app):
        """The relay restarted: the same address now answers from a new process."""
        self.app = app
        self.client = app.test_client()

    def inject(self, exchange, *faults):
        self.plan[exchange].extend(faults)

    def is_down(self):
        now = self.clock()
        if self.down_until is not None and now < self.down_until:
            return True
        return bool(self.flap_period) and int(now // self.flap_period) % 2 == 1

    def _deliver(self, method, path, headers, json, base):
        self.delivered.append((method, path))
        return self.client.open(path, method=method, headers=headers or {}, json=json,
                                base_url=base)

    def _send(self, method, url, headers=None, json=None, timeout=None, **_ignored):
        parts = urlsplit(url)
        path = parts.path
        base = f'{parts.scheme}://{parts.netloc}'
        name = exchange_of(path)
        self.calls.append((self.clock(), name))
        if name in self.before:
            self.before.pop(name)()
        if self.is_down():
            raise requests.ConnectionError('[Errno 111] Connection refused')
        fault = self.plan.get(name, []).pop(0) if self.plan.get(name) else None
        if fault == 'timeout':
            raise requests.exceptions.ReadTimeout('read timed out')
        if fault == 'reset_before':
            raise requests.ConnectionError('Connection reset by peer')
        if fault == 'dns':
            raise requests.ConnectionError('Failed to resolve relay.test (NameResolutionError)')
        if fault == 'tls':
            raise requests.exceptions.SSLError('certificate verify failed')
        if fault in ('500', '502', '503'):
            if fault == '500':
                return Canned(500, '{"error": "internal"}', 'application/json')
            return Canned(int(fault), f'<html><body>{fault} Bad Gateway</body></html>',
                          'text/html')
        if fault == '429':
            return Canned(429, '{"error": "Too Many Requests"}', 'application/json')
        if fault == '429_hint':
            return Canned(429, '{"error": "Too Many Requests"}', 'application/json',
                          {'Retry-After': '7'})
        if fault == 'html':
            return Canned(200, '<html>Sign in to the school Wi-Fi</html>', 'text/html')
        if fault == 'truncated':
            return Canned(200, '{"job": {"id": "j1', 'application/json')
        if fault == 'wrong_shape':
            return Canned(200, '[1, 2, 3]', 'application/json')
        if fault == 'slow':
            self.clock.advance(15)
        response = self._deliver(method, path, headers, json, base)
        if fault == 'duplicate':
            response = self._deliver(method, path, headers, json, base)
        if fault == 'late':
            raise requests.exceptions.ReadTimeout('read timed out')
        if fault == 'reset_after':
            raise requests.ConnectionError("('Connection aborted.', RemoteDisconnected())")
        answer = InProcessResponse(response)
        if fault in DOWNLOAD_FAULTS and answer.status_code == 200:
            data = answer._data
            chunks = {
                'stop_partway': [data[:len(data) // 2],
                                 requests.ConnectionError('Connection reset by peer')],
                'stall': [data[:len(data) // 3],
                          requests.exceptions.ConnectionError('Read timed out.')],
                'wrong_length': [data, b'extra'],
                'wrong_content': [bytes([data[0] ^ 0xFF]) + data[1:]],
            }[fault]
            return Canned(200, '', 'application/octet-stream', chunks=chunks)
        return answer

    def post(self, url, **kwargs):
        return self._send('POST', url, **kwargs)

    def get(self, url, **kwargs):
        return self._send('GET', url, **kwargs)


class CountingPrinter(StandInPrinter):
    """The stand-in printer, which also finishes a print a set time after it started, can
    be switched off, and reports the age of its last word (`report_age_s`) the way
    PrinterLink does: zero while it reports, and growing from its last report while it is
    off. `outages` counts the outages in force, so overlapping ones end in order."""

    def __init__(self, clock, print_seconds=120):
        super().__init__()
        self.clock = clock
        self.print_seconds = print_seconds
        self.started_at = None
        self.outages = 0
        self.spoke_at = clock()
        self.before_upload = None       # one-shot hooks
        self.after_start = None
        # A quiet status stream: the socket stays open, the daemon keeps the last document,
        # and its age grows, while the printer goes on doing what it does.
        self.quiet_spells = 0
        self.frozen = None
        self.quiet_since = None
        #: The snapshot the daemon last read, and, for each start command, the one it had
        #: read just before: the evidence it started on.
        self.last_read = None
        self.start_evidence = []

    @property
    def off(self):
        return self.outages > 0

    @off.setter
    def off(self, value):
        self.outages = 1 if value else 0

    def outage(self, shop, at, seconds):
        """Switch the printer off `at` seconds from now for `seconds`, on the shop's timers,
        so it happens wherever the daemon is: in a sync or inside its job's waits."""
        def down():
            self.outages += 1

        def up():
            self.outages = max(0, self.outages - 1)

        if at <= 0:
            down()
        else:
            shop.at(at, down)
        shop.at(max(at, 0) + seconds, up)

    @property
    def finished_ours(self):
        """Did the print run to its end (whether or not anyone could see it finish)?"""
        return (self.started_at is not None
                and self.clock() - self.started_at >= self.print_seconds)

    def quiet(self, shop, at, seconds):
        """The status stream goes silent `at` seconds from now for `seconds`, on the shop's
        timers; spells that overlap end in order."""
        def down():
            if self.quiet_spells == 0:
                self.frozen = dict(super(CountingPrinter, self).snapshot())
                self.quiet_since = self.clock()
            self.quiet_spells += 1

        def up():
            self.quiet_spells = max(0, self.quiet_spells - 1)

        if at <= 0:
            down()
        else:
            shop.at(at, down)
        shop.at(max(at, 0) + seconds, up)

    def snapshot(self):
        self.last_read = self._read()
        return dict(self.last_read)

    def _read(self):
        if self.off:
            return dict(self._idle(), state='unreachable', stage_code=None, stage=None,
                        stage_label=None, report_age_s=int(self.clock() - self.spoke_at))
        if (self.started_at is not None and self._snapshot['state'] == 'running'
                and self.clock() - self.started_at >= self.print_seconds):
            self.finish()
        if self.quiet_spells:
            return dict(self.frozen, report_age_s=int(self.clock() - self.quiet_since))
        self.spoke_at = self.clock()
        return dict(super().snapshot(), report_age_s=0)

    def upload(self, local_path, remote_name, **kwargs):
        if self.before_upload is not None:
            hook, self.before_upload = self.before_upload, None
            hook()
        if self.off:
            from penguin_delivery_daemon.printer import UploadFailed
            raise UploadFailed('the printer is off')
        return super().upload(local_path, remote_name, **kwargs)

    def start(self, remote_name):
        self.start_evidence.append(self.last_read)
        if self.off:
            raise OSError('the printer is off')
        accepted = super().start(remote_name)
        if accepted:
            self.started_at = self.clock()
        if self.after_start is not None:
            hook, self.after_start = self.after_start, None
            hook()
        return accepted


class Shop:
    def __init__(self, tmp_path, *, daemon_clock_offset=0.0, rand=lambda: 0.5):
        self.tmp_path = tmp_path
        self.wall = relay_fakes.FakeClock()
        self.mono = daemon_fakes.FakeClock(now=1000.0 + daemon_clock_offset)
        self.timers = []
        self.caller = relay_fakes.Caller()
        self.caller.offer(tmp_path, content=CONTENT)
        self.app = self.new_relay()
        self.link = FaultyLink(self.app, self)
        self.pages = self.app.test_client()
        self.printer = CountingPrinter(self)
        self.config = DaemonConfig(backend_url=BASE, pairing_code=relay_fakes.CODE,
                                   path=str(tmp_path / 'config.toml'))
        self.rand = rand
        self._depth = 0
        self.logged = []
        self.errors = []
        self.loops = [self.new_daemon()]
        self.reports = []
        self._last_seen = {}

    # the clocks
    def __call__(self):
        return self.wall()

    def advance(self, seconds):
        self.wall.advance(seconds)
        self.mono.advance(seconds)
        due = [entry for entry in self.timers if entry[0] <= self.wall()]
        for entry in due:
            self.timers.remove(entry)
            entry[1]()

    def at(self, seconds_from_now, action):
        """Run `action` once the shared clock has moved on this far, wherever the daemon
        is at that moment (in a sync, or in its job's wait)."""
        self.timers.append((self.wall() + seconds_from_now, action))

    # the parts
    def new_relay(self):
        return relay_fakes.make_app(self.caller, self.wall,
                                    spool_dir=str(self.tmp_path / 'spool'))

    def restart_relay(self):
        self.app = self.new_relay()
        self.link.use_app(self.app)
        self.pages = self.app.test_client()

    def job_sleep(self, seconds):
        """The job thread sleeps; meanwhile the daemon's tick thread goes on syncing. With
        one thread, that is: move the clocks a second at a time and tick every daemon,
        which is the same interleaving two threads would have at the job's wait points."""
        whole = int(seconds)
        for _ in range(whole):
            self.advance(1)
            if self._depth < 3:
                self._depth += 1
                try:
                    self.tick()
                finally:
                    self._depth -= 1
        if seconds - whole:
            self.advance(seconds - whole)

    def new_daemon(self, instance=None):
        client = RelayClient(BASE, token=self.config.token or None, session=self.link)

        def save_token(token, path):
            self.config.token = token

        # The job thread's waits, bounded tighter than the suite's default: each simulated
        # second here also ticks every daemon, so a wait with no end must fail early.
        sleep = daemon_fakes.SleepBound(self.job_sleep, 'the shop daemon',
                                        seconds=JOB_SLEEP_LIMIT_SECONDS)
        return RunLoop(self.config, client, self.printer, clock=self.mono,
                       sleep=sleep, rand=self.rand,
                       log=lambda *a: self.logged.append(' '.join(str(x) for x in a)),
                       executor=InlineExecutor(), instance=instance,
                       download_dir=str(self.tmp_path / 'downloads'), save_token=save_token)

    def restart_daemon(self):
        self.loops = [self.new_daemon()]

    @property
    def relay(self):
        return relay_of(self.app).relay

    # the caller
    def status(self):
        return self.pages.get('/printer/status', base_url=BASE).get_json()

    def send(self):
        resp = self.pages.post('/printer/jobs', json={'token': 'tok'}, base_url=BASE)
        assert resp.status_code == 202, resp.get_json()
        return resp.get_json()['job_id']

    def report(self, job_id):
        resp = self.pages.get(f'/printer/jobs/{job_id}', base_url=BASE)
        if resp.status_code == 404:
            return None
        report = resp.get_json()
        self.reports.append(report)
        return report

    # driving
    def tick(self):
        for loop in list(self.loops):
            if loop not in self.loops:
                continue
            try:
                loop.tick()
            except DaemonDied:
                if self._depth:
                    raise                       # unwind the dying process to the top
                self.restart_daemon()           # a new process starts from the config
            except BaseException as e:          # a crash: recorded, never expected
                self.errors.append(e)
                raise

    def drive(self, seconds, until=None, step=1):
        """Run every part for `seconds` of simulated time, a tick each `step` seconds. A
        `step` above one is for hours of simulated time: the daemon then syncs once a step
        instead of every five seconds."""
        for _ in range(int(seconds // step)):
            if until is not None and until():
                return True
            self.advance(step)
            self.tick()
        return until() if until is not None else None

    def online(self, seconds=120):
        self.status()                               # the caller presents the code
        assert self.drive(seconds, lambda: self.relay.status_for(relay_fakes.CODE)['online']), \
            'never came online'
        assert self.status()['online']

    def final(self, job_id):
        """Is the delivery job over? Asked every simulated second, so it reads the relay in
        the same process, and fetches the caller's report through the route (recording it
        for assert_truthful) only when that report has changed: the same reports a caller
        polling every second would see, without an HTTP request per second."""
        seen = self.relay.delivery_report(relay_fakes.CODE, job_id)
        if seen is None or seen != self._last_seen.get(job_id):
            self._last_seen[job_id] = seen
            report = self.report(job_id)
        else:
            report = seen
        return report is not None and report['state'] in ('done', 'failed', 'cancelled')
