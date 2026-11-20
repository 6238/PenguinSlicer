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
from hypothesis import HealthCheck, Phase, settings

from penguin_delivery_daemon.config import DaemonConfig
from penguin_delivery_daemon.relay_client import RelayClient
from penguin_delivery_daemon.run_loop import InlineExecutor, RunLoop
from penguin_delivery_relay import relay_of

import daemon_fakes
import relay_fakes
from together.stand_in import StandInPrinter
from together.transport import InProcessResponse

BASE = 'https://relay.test'

#: The settings of the random sequences (`make test-properties`, marker `properties`).
#: The same examples every run (`derandomize`, no example database). No shrinking: a
#: failing example is reported as it was found, at once. Hypothesis takes pytest-timeout's
#: failure for a failing example too, so with shrinking on, one slow failing example could
#: be shrunk for five minutes past the per-test limit; without it a test ends within that
#: limit (30 s, pyproject.toml) plus one more run of the example that failed.
PROPERTY_SETTINGS = settings(
    deadline=None, derandomize=True, database=None, report_multiple_bugs=False,
    phases=(Phase.explicit, Phase.generate),
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
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
        #: Called with the path of every ask of the start gate, before anything else, and
        #: once the relay has handled it.
        self.on_start_ask = None
        self.on_start_answered = None

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
        if name == 'start' and self.on_start_ask is not None:
            self.on_start_ask(path)
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
        if name == 'start' and self.on_start_answered is not None:
            self.on_start_answered(path)
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
        #: Every start command the daemon tried to send, whether or not it reached the
        #: printer, in order; `started` (the stand-in's) is those the printer accepted.
        self.commanded = []
        #: A one-shot fault of the next start command: 'before' (the connection drops
        #: before the command reaches the printer) or 'after' (it reaches the printer, and
        #: the connection drops before the answer). Either way the call raises.
        self.start_raises = None
        #: Every picture the daemon read: (shop time, picture).
        self.reads = []
        #: Start commands that reached the printer while it was printing (its own truth).
        self.busy_starts = []

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
        self.reads.append((self.clock(), self.last_read))
        return dict(self.last_read)

    def truth(self):
        """What the printer is doing, whether or not anyone can hear it."""
        if (self.started_at is not None and self._snapshot['state'] == 'running'
                and self.clock() - self.started_at >= self.print_seconds):
            self.finish()
        return StandInPrinter.snapshot(self)

    def someone_prints(self, shop, at, seconds, name='someone_elses_print',
                       pending=lambda: False):
        """Someone starts a print at the printer's own screen `at` seconds from now, while
        the printer is off the network (so nobody hears it start); it runs for `seconds`,
        then finishes. Nothing happens if the printer is busy, holds a start it has not
        begun (`pending`), or is not off just then."""
        def begin():
            truth = self.truth()
            if not self.off or truth['state'] in ('running', 'paused') or pending():
                return
            self._snapshot = dict(self._idle(), state='running', file=name, job_name=name,
                                  percent=10, remaining_min=5, layers=10, stage_code=0,
                                  stage='printing', stage_label='Printing')
            shop.at(seconds, end)

        def end():
            if self._snapshot.get('file') == name and self._snapshot['state'] == 'running':
                self._snapshot = dict(self._snapshot, state='finished', percent=100)

        shop.at(at, begin)

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
        self.commanded.append(remote_name)
        self.start_evidence.append(self.last_read)
        if not self.off and self.truth()['state'] in ('running', 'paused'):
            # The printer's own truth: a print is going on as this command arrives.
            self.busy_starts.append((remote_name, self.truth()))
        fault, self.start_raises = self.start_raises, None
        if fault == 'before':
            raise OSError('the connection dropped before the command reached the printer')
        if self.off:
            raise OSError('the printer is off')
        accepted = super().start(remote_name)
        if accepted:
            self.started_at = self.clock()
        if self.after_start is not None:
            hook, self.after_start = self.after_start, None
            hook()
        if fault == 'after':
            raise OSError('the connection dropped after the command reached the printer')
        return accepted


#: How each snapshot `state` of the stand-in reads as the H2S's own `gcode_state`.
_GCODE_STATE = {'idle': 'IDLE', 'running': 'RUNNING', 'paused': 'PAUSE',
                'finished': 'FINISH', 'error': 'FAILED'}
#: The fields of a partial status document: figures, never the main state.
_PARTIAL_FIELDS = ('mc_percent', 'mc_remaining_time', 'layer_num')


def h2s_document(snapshot):
    """The H2S status document that map_status reads back as this stand-in snapshot."""
    error = snapshot.get('error')
    code = (int(error[len('PRINT_ERROR_'):], 16)
            if isinstance(error, str) and error.startswith('PRINT_ERROR_') else 0)
    stage = snapshot.get('stage_code')
    state = _GCODE_STATE.get(snapshot.get('state'), 'IDLE')
    if snapshot.get('state') == 'error' and stage == 255:
        state = 'IDLE'                                  # idle with an error code set
    return {'gcode_state': state, 'subtask_name': snapshot.get('job_name') or '',
            'mc_percent': snapshot.get('percent') or 0,
            'mc_remaining_time': snapshot.get('remaining_min') or 0,
            'layer_num': snapshot.get('layer') or 0,
            'total_layer_num': snapshot.get('layers') or 0,
            'stg_cur': 255 if stage is None else stage, 'print_error': code, 'hms': []}


class _Message:
    def __init__(self, document):
        self.payload = json_module.dumps(document).encode()


class _ShopMqtt:
    """bambulabs_api's MQTT client as far as PrinterLink uses it: the two hooks, pushall,
    and the paho client's disconnect."""

    def __init__(self):
        self.on_message_handler = None
        self.on_connect_handler = None
        self._client = self
        self.pushalls = 0

    def pushall(self):
        self.pushalls += 1

    def disconnect(self):
        pass


class ShopLibrary:
    """bambulabs_api.Printer as the daemon's PrinterLink meets it, over the stand-in's
    truth: it merges every status document into the last, keeps the last connection's
    picture across a reconnect, and calls the connect hook on each (re)connect. On a
    connection the printer's whole document arrives only `whole_after` seconds later
    (the library asked for it; the printer is slow to answer); until then only partial
    documents, which never carry the main state. One document a second while the printer
    speaks; none while its stream is quiet; disconnected while it is off."""

    def __init__(self, shop, truth_printer, whole_after=0):
        self.shop = shop
        self.inner = truth_printer
        self.whole_after = whole_after
        self.mqtt_client = _ShopMqtt()
        self.merged = {}
        self.connected = False
        self.whole_due = None
        self.last_document_at = None
        self._once = None

    def mqtt_start(self):
        pass

    def mqtt_stop(self):
        pass

    def reconnect(self, whole_after=None):
        """The connection drops and comes straight back (a Wi-Fi blip); on this one
        connection the whole document comes `whole_after` seconds late."""
        self.connected = False
        self._once = whole_after

    def mqtt_client_connected(self):
        self.hear()
        return self.connected

    def mqtt_dump(self):
        return {'print': dict(self.merged)}

    def hear(self):
        now = self.shop()
        if self.inner.off:
            self.connected = False
            return
        if not self.connected:
            self.connected = True
            once, self._once = self._once, None
            self.whole_due = now + (self.whole_after if once is None else once)
            if self.mqtt_client.on_connect_handler is not None:
                self.mqtt_client.on_connect_handler(None, None, None, 0)
        if self.inner.quiet_spells:
            return
        if self.last_document_at is not None and now - self.last_document_at < 1:
            return
        self.last_document_at = now
        document = h2s_document(self.inner.truth())
        if self.whole_due is not None:
            if now >= self.whole_due:
                self.whole_due = None
            else:
                document = {key: document[key] for key in _PARTIAL_FIELDS}
        self.merged.update(document)
        if self.mqtt_client.on_message_handler is not None:
            self.mqtt_client.on_message_handler(None, None, _Message({'print': document}))


class LinkedPrinter:
    """The stand-in printer as the daemon hears it through the real PrinterLink over
    ShopLibrary: what the daemon reads is what PrinterLink makes of the documents. The
    upload, the delete and the start go to the stand-in directly. One per daemon process:
    a restarted daemon connects anew."""

    def __init__(self, shop, inner, whole_after=0):
        from penguin_delivery_daemon.printer import PrinterLink
        self.inner = inner
        self.library = ShopLibrary(shop, inner, whole_after)
        self.link = PrinterLink('127.0.0.1', 'STANDIN0001', 'not-a-code',
                                printer_factory=lambda *args: self.library,
                                clock=shop.mono)
        self.link.connect()

    def snapshot(self):
        picture = self.link.snapshot()
        self.inner.last_read = picture
        self.inner.reads.append((self.inner.clock(), picture))
        return dict(picture)

    def request_report(self):
        self.link.request_report()

    def upload(self, *args, **kwargs):
        return self.inner.upload(*args, **kwargs)

    def delete(self, remote_name):
        return self.inner.delete(remote_name)

    def start(self, remote_name):
        return self.inner.start(remote_name)


class Shop:
    """`linked`: the daemon hears the printer through the real PrinterLink over
    ShopLibrary (merged documents, reconnects, partial documents for `whole_after` seconds
    of each connection), instead of reading the stand-in's snapshot directly."""

    def __init__(self, tmp_path, *, daemon_clock_offset=0.0, rand=lambda: 0.5,
                 linked=False, whole_after=0):
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
        self.linked = linked
        self.whole_after = whole_after
        self.heard = None
        #: Every ask of the start gate: {'at', 'job', 'picture'} (the daemon's last read).
        self.start_asks = []
        #: When each job's start was granted, by the relay that granted it.
        self.gate_at = {}
        self.relay_restarts = []
        self.link.on_start_ask = self._start_asked
        self.link.on_start_answered = self._start_answered
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
        self.relay_restarts.append(self())
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
        heard = self.printer
        if self.linked:
            self.heard = heard = LinkedPrinter(self, self.printer, self.whole_after)
        return RunLoop(self.config, client, heard, clock=self.mono,
                       sleep=sleep, rand=self.rand,
                       log=lambda *a: self.logged.append(' '.join(str(x) for x in a)),
                       executor=InlineExecutor(), instance=instance,
                       download_dir=str(self.tmp_path / 'downloads'), save_token=save_token,
                       start_record_path=self.start_record_path)

    @property
    def start_record_path(self):
        """The note of a start command, in the daemon's home: it outlives every process."""
        return str(self.tmp_path / 'start.json')

    def restart_daemon(self):
        self.loops = [self.new_daemon()]

    def _start_asked(self, path):
        job = path.rstrip('/').split('/')[-2]
        self.start_asks.append({'at': self(), 'job': job, 'picture': self.printer.last_read,
                                'granted_before': self.relay_granted(job),
                                'commanded': list(self.printer.commanded)})

    def _start_answered(self, path):
        job = path.rstrip('/').split('/')[-2]
        if job not in self.gate_at and self.relay_granted(job):
            self.gate_at[job] = self()

    def relay_granted(self, job_id):
        """Has the relay granted this job's start (as far as this relay process knows)?"""
        record = self.relay._get(relay_fakes.CODE)
        job = record.job if record is not None else None
        return bool(job and job['id'] == job_id and job.get('start_granted_to'))

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
        if self.linked:
            # Until the printer's whole document arrives, the relay rightly refuses a send.
            assert self.drive(seconds, lambda: (self.status().get('status') or {}).get(
                'state') not in (None, 'unrecognised')), 'no whole picture'

    def observe(self, job_ids):
        """Note each job's state and stage as the relay reports it now (the property
        tests' record of what a caller saw, and when)."""
        for job_id in job_ids:
            report = self.relay.delivery_report(relay_fakes.CODE, job_id)
            if report is not None:
                self.observed.append((self(), job_id, report['state'], report.get('stage'),
                                      (report.get('error') or {}).get('code')))

    @property
    def observed(self):
        if not hasattr(self, '_observed'):
            self._observed = []
        return self._observed

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


# --- the invariants of the start path, for the property tests ------------------------------

#: The codes whose sentence says the print was not started.
NOT_STARTED = frozenset({
    'delivery.cancelled', 'delivery.printer_unreachable_at_start',
    'delivery.printer_busy_at_start', 'delivery.printer_state_unrecognised_at_start',
    'delivery.earlier_start_unsettled', 'delivery.start_not_recorded',
    'delivery.job_not_confirmed', 'delivery.job_not_picked_up'})
_FREE = ('idle', 'finished', 'error')


def file_of(job_id):
    return f'sample_part-{job_id}.gcode.3mf'


def _whole_and_fresh(picture):
    from penguin_delivery_daemon import run_loop as rl
    return (picture is not None and picture.get('whole') is not False
            and picture.get('state') not in ('unreachable', 'unrecognised')
            and isinstance(picture.get('report_age_s'), (int, float))
            and picture['report_age_s'] <= rl.FRESH_REPORT_SECONDS)


def _going(picture, job_id):
    stem = file_of(job_id)[:-len('.gcode.3mf')]
    return picture.get('state') in ('running', 'paused') and stem in (
        picture.get('job_name'), picture.get('file'))


def check_start_path(shop, jobs, *, shown, cancels=(), exempt_done=False, exempt_end=False,
                     slow=False, allow_overlap=False, longer_hold=False):
    """The start path's invariants, from what the printer was sent and what everyone was
    told. `shown`: the files the printer showed as printing (its own truth). `cancels`:
    (job, error code or None, shop time, the files commanded by then) of each cancel and
    its answer. `exempt_done` and `exempt_end`: a printer so slow, or a daemon so blind,
    that the guide's two stated limits allow a done, or an end, without the print shown;
    `slow` the same for "did not start", and `allow_overlap` for a start command while
    the printer prints. `longer_hold`: a damaged note, which holds the printer for longer
    on purpose. Returns nothing; raises AssertionError naming the broken invariant."""
    from penguin_delivery_daemon import run_loop as rl
    printer = shop.printer
    # 1. One start command per file, counting the ones that never reached the printer;
    #    none while the printer was printing (its own truth).
    assert len(printer.commanded) == len(set(printer.commanded)), \
        ('a file was sent two start commands', printer.commanded)
    if not allow_overlap:
        assert printer.busy_starts == [], ('a start command while the printer printed',
                                           printer.busy_starts)
    # 2. A start command only on a whole, fresh picture of a free printer.
    for evidence in printer.start_evidence:
        assert _whole_and_fresh(evidence) and evidence['state'] in _FREE, \
            ('a start command on a picture that is not whole, fresh and free', evidence)
    # 3. The gate is asked, before it grants, only on such a picture: every wait comes
    #    before the gate, where a cancel still ends the job.
    for ask in shop.start_asks:
        if (ask['granted_before'] or file_of(ask['job']) in ask['commanded']
                or shop.gate_at.get(ask['job'], ask['at']) < ask['at']):
            continue                    # a hold's check that the relay still holds it
        picture = ask['picture']
        assert _whole_and_fresh(picture) and picture['state'] in _FREE, \
            ('the start gate asked while the printer was not free on whole, fresh word', ask)
    # 4. No final state without evidence, and no sentence claiming a start that did not
    #    happen (or denying one that did).
    for job_id in jobs:
        report = shop.report(job_id)
        name = file_of(job_id)
        seen = [entry for entry in shop.observed if entry[1] == job_id]
        if any(stage == 'printing' for _at, _job, _state, stage, _code in seen):
            assert name in printer.commanded, ('printing, but no start command', job_id)
        if report is None:
            continue
        code = (report.get('error') or {}).get('code')
        if code in NOT_STARTED:
            assert name not in printer.commanded, ('"not started", but it was', report)
        if code == 'delivery.start_refused':
            assert name not in printer.started, ('"refused", but the printer took it', report)
        if report['state'] == 'done':
            assert name in shown or exempt_done, ('done, never shown', report)
        if code in ('delivery.printer_error_at_start', 'delivery.print_failed',
                    'delivery.print_stopped'):
            assert exempt_end, ('a printer error that never happened', report)
        if code in ('delivery.start_timeout', 'delivery.start_other_file'):
            assert name not in shown or slow, ('"did not start", but it printed', report)
    for job_id, code, at, commanded in cancels:
        if code == 'delivery.cancel_too_late':
            assert file_of(job_id) in commanded, \
                ('"the start command has already been sent", none was', job_id, at)
    # 5. A hold never holds the printer past START_SETTLE_SECONDS of whole, fresh pictures
    #    after the gate, nor once the held print has been seen going. (Only while the
    #    relay that granted the gate runs: after a relay restart the daemon's note holds
    #    the printer, its time counted from after the restart, which is the safe side.) The
    #    slack: the daemon looks every PRINTER_POLL_SECONDS, and its word reaches the
    #    relay at the next sync.
    slack = rl.PRINTER_POLL_SECONDS + 3
    for at, job_id, _state, stage, _code in shop.observed:
        if stage != 'waiting_for_earlier_print' or longer_hold:
            continue
        earlier = [(gate, other) for other, gate in shop.gate_at.items()
                   if other != job_id and gate < at]
        if not earlier:
            continue
        gate, other = max(earlier)
        if any(gate <= restart <= at for restart in shop.relay_restarts):
            continue
        fresh = 0.0
        previous = None
        for read_at, picture in printer.reads:
            if read_at < gate or read_at > at - slack:
                continue
            ok = _whole_and_fresh(picture)
            assert not (ok and _going(picture, other)), \
                ('still held after the held print was seen going', job_id, other, read_at)
            if previous is not None and ok and previous[1]:
                fresh += read_at - previous[0]
            previous = (read_at, ok)
        assert fresh <= rl.START_SETTLE_SECONDS, \
            ('held past the settle time of whole, fresh pictures', job_id, other, fresh)
