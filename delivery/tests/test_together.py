"""The relay and the daemon together: the daemon's real RelayClient and RunLoop talking to
the real relay app through an in-process session, the printer played by the stand-in, and
both clocks fake. No socket, no thread, no real waiting -- each step of a job is driven by
hand, so every state the caller can see is checked as it happens.

The tests marked real_time run the together run itself on real threads; `make test`
leaves them out and `make test-together` runs them."""
import io
import os

import pytest

from penguin_delivery_daemon import __main__ as daemon_main
from penguin_delivery_daemon import printer as daemon_printer
from penguin_delivery_daemon.config import DaemonConfig
from penguin_delivery_daemon.relay_client import RelayClient
from penguin_delivery_daemon.run_loop import InlineExecutor, RunLoop
from penguin_delivery_relay import relay as relay_module
from penguin_delivery_relay import relay_of

import daemon_fakes
import relay_fakes
from together import __main__ as together_main
from together.stand_in import StandInPrinter
from together.transport import InProcessResponse, InProcessSession

BASE = 'https://relay.test'
CONTENT = b'sliced bytes for the stand-in printer'


class DaemonDied(BaseException):
    """Stands in for the daemon process being killed: no `except Exception` catches it."""


class Bench:
    """One relay app, one daemon, one stand-in printer, and the two fake clocks moved
    together: the relay's wall clock and the daemon's monotonic one."""

    def __init__(self, tmp_path, printer=None, executor=None):
        self.tmp_path = tmp_path
        self.wall = relay_fakes.FakeClock()
        self.mono = daemon_fakes.FakeClock()
        self.caller = relay_fakes.Caller()
        self.sliced_path = self.caller.offer(tmp_path, content=CONTENT)
        self.app = relay_fakes.make_app(self.caller, self.wall)
        self.session = InProcessSession(self.app)
        self.pages = self.app.test_client()
        self.printer = printer or StandInPrinter()
        self.logged = []
        self.config = DaemonConfig(backend_url=BASE, pairing_code=relay_fakes.CODE,
                                   path=str(tmp_path / 'config.toml'))
        self.loop = self.new_daemon(executor)

    def advance(self, seconds):
        self.wall.advance(seconds)
        self.mono.advance(seconds)

    def new_daemon(self, executor=None):
        """A daemon process starting from the config file: only the token survives."""
        client = RelayClient(BASE, token=self.config.token or None, session=self.session)
        return RunLoop(self.config, client, self.printer, clock=self.mono,
                       sleep=self.advance, log=lambda *a: self.logged.append(
                           ' '.join(str(x) for x in a)),
                       executor=executor or InlineExecutor(),
                       download_dir=str(self.tmp_path / 'downloads'),
                       save_token=lambda token, path: None)

    def status(self):
        return self.pages.get('/printer/status', base_url=BASE).get_json()

    def send(self):
        return self.pages.post('/printer/jobs', json={'token': 'tok'}, base_url=BASE)

    def online(self):
        """Present the code, pair, and post the first snapshot."""
        assert self.status()['waiting'] is True
        self.loop.tick()                         # the exchange
        self.loop.tick()                         # the first sync
        assert self.status()['online'] is True

    def sync(self):
        self.advance(5)
        self.loop.tick()


@pytest.fixture
def bench(tmp_path):
    return Bench(tmp_path)


def test_a_job_goes_through_every_state_the_caller_can_see(tmp_path):
    executor = daemon_fakes.StepExecutor()
    b = Bench(tmp_path, executor=executor)
    b.online()
    sent = b.send()
    assert sent.status_code == 202
    job_id = sent.get_json()['job_id']
    assert b.status()['job'] == {'id': job_id, 'state': 'pending',
                                 'filename': 'sample_part.gcode.3mf',
                                 'display_name': 'sample_part.gcode.3mf'}

    b.sync()                                     # the sync hands the job out
    assert b.status()['job']['state'] == 'handed_out'
    assert b.printer.received == {}

    executor.release()                           # download, upload, start, acknowledge
    status = b.status()
    assert status['job'] is None
    assert status['last_result'] == {'ok': True, 'reason': None, 'age_seconds': 0}
    remote = f'sample_part-{job_id}.gcode.3mf'
    assert b.printer.received == {remote: CONTENT}
    assert b.printer.started == [remote]

    b.sync()                                     # the printer's report reaches the relay
    status = b.status()
    assert status['status']['state'] == 'running'
    assert status['status']['display_name'] == 'sample_part'
    # A success stays for a caller that polls slowly; only a failure the printer
    # contradicts is cleared.
    assert status['last_result']['ok'] is True
    assert (status['delivery']['state'], status['delivery']['stage']) == ('running',
                                                                          'printing')
    b.printer.finish()
    b.sync()
    assert b.status()['delivery']['state'] == 'done'


def test_the_downloaded_copy_is_gone_from_the_daemon_after_the_job(bench):
    bench.online()
    bench.send()
    bench.sync()
    assert os.listdir(bench.tmp_path / 'downloads') == []


def test_a_sliced_file_that_vanished_before_the_download_reaches_the_caller(bench):
    bench.online()
    bench.send()
    os.unlink(bench.sliced_path)                 # the caller deleted it too early
    bench.sync()
    last = bench.status()['last_result']
    assert (last['ok'], last['reason']) == (False, 'download answered 404')
    assert last['error_report']['code'] == 'delivery.download_failed'
    assert last['error_report']['detail'] == '3 attempts; last: download answered 404'
    assert bench.printer.received == {}


def test_a_printer_that_refuses_the_start_reaches_the_caller(tmp_path):
    class Refusing(StandInPrinter):
        def start(self, remote_name):
            return False

    b = Bench(tmp_path, printer=Refusing())
    b.online()
    b.send()
    b.sync()
    report = b.status()['last_result']['error_report']
    assert report['code'] == 'delivery.start_refused'


def test_a_job_no_daemon_collects_expires_and_reaches_the_caller(bench):
    bench.online()
    bench.send()
    bench.advance(3 * 60 + 1)                    # the daemon is silent all this time
    report = bench.status()['last_result']['error_report']
    assert report['code'] == 'delivery.job_not_picked_up'
    assert bench.caller.events[-1][1]['metadata']['expired'] is True


def test_a_daemon_that_died_before_the_upload_is_replaced_and_finishes_the_job(tmp_path):
    executor = daemon_fakes.StepExecutor()
    b = Bench(tmp_path, executor=executor)
    b.online()
    job_id = b.send().get_json()['job_id']
    b.sync()                                     # handed out to the first process ...
    executor.pending.clear()                     # ... which dies before doing anything
    b.loop = b.new_daemon()
    b.sync()                                     # the relay offers the job again
    assert b.printer.started == [f'sample_part-{job_id}.gcode.3mf']
    assert b.status()['last_result']['ok'] is True


def test_a_daemon_that_died_after_the_start_does_not_print_twice(tmp_path):
    class DiesAfterStart(StandInPrinter):
        armed = True

        def start(self, remote_name):
            accepted = super().start(remote_name)
            if self.armed:
                self.armed = False
                raise DaemonDied()
            return accepted

    b = Bench(tmp_path, printer=DiesAfterStart())
    b.online()
    b.send()
    with pytest.raises(DaemonDied):
        b.sync()
    assert b.status()['job']['state'] == 'handed_out'     # no acknowledgement yet
    b.loop = b.new_daemon()
    b.sync()
    assert len(b.printer.started) == 1
    assert b.status()['last_result']['ok'] is True
    assert any('already has' in line for line in b.logged)


def test_a_relay_restart_mid_job_loses_the_job_and_the_caller_learns_nothing(tmp_path):
    executor = daemon_fakes.StepExecutor()
    b = Bench(tmp_path, executor=executor)
    b.online()
    b.send()
    b.sync()
    restarted = relay_fakes.make_app(b.caller, b.wall)          # same key, empty memory
    b.session._client = restarted.test_client()
    b.pages = restarted.test_client()
    executor.release()                           # the download now answers 404 ...
    assert any('no longer holds job' in line for line in b.logged)   # ... and so does ack
    status = b.status()
    assert (status['job'], status['last_result']) == (None, None)
    assert b.printer.received == {}


def test_a_relay_restarted_with_a_new_key_makes_the_daemon_pair_again(bench):
    bench.online()
    restarted = relay_fakes.make_app(bench.caller, bench.wall, secret_key='a-new-key')
    bench.session._client = restarted.test_client()
    bench.pages = restarted.test_client()
    bench.sync()                                 # 401: the token is blanked
    assert bench.loop.relay.token is None
    bench.loop.tick()                            # the exchange: no caller presented the code
    assert bench.loop.relay.token is None
    assert bench.status()['waiting'] is True     # a caller's poll presents it
    bench.advance(30)
    bench.loop.tick()
    assert bench.loop.relay.token is not None
    bench.loop.tick()
    assert bench.status()['online'] is True


def test_a_second_daemon_with_a_copied_config_is_refused_while_the_first_is_alive(bench):
    bench.online()
    second = RelayClient(BASE, session=bench.session)
    assert second.exchange(relay_fakes.CODE) is None


def test_a_real_h2s_report_is_recognised_as_our_running_print(tmp_path):
    """Known fault 1, fixed: the whole path with the real PrinterLink and the report the
    H2S really sends (`subtask_name` without the extension, `gcode_file` the path inside
    the archive). The part prints and the caller is told so."""
    holder = {}

    def factory(ip, access_code, serial):
        holder['bambu'] = daemon_fakes.FakeBambuPrinter(ip, access_code, serial)
        holder['bambu'].report = dict(daemon_fakes.H2S['idle'])

        def as_the_h2s_reports(remote_name):
            return dict(daemon_fakes.H2S['running_as_reported_by_h2s'],
                        subtask_name=remote_name[:-len('.gcode.3mf')])

        holder['bambu'].report_after_start = as_the_h2s_reports
        return holder['bambu']

    link = daemon_printer.PrinterLink('10.0.0.42', '01P00A', 'not-a-real-code',
                                      printer_factory=factory)
    link.connect()
    b = Bench(tmp_path, printer=link)
    b.online()
    b.send()
    b.sync()
    b.sync()
    status = b.status()
    assert status['status']['state'] == 'running'
    assert status['last_result']['ok'] is True
    assert status['delivery']['stage'] == 'printing'
    assert status['delivery']['printer_stage'] == 'cleaning_nozzle'     # stg_cur 14
    assert status['delivery']['total_layers'] == 50
    assert holder['bambu'].started['filename'] == holder['bambu'].uploaded[0]


# --- the two halves agree where they cannot import each other --------------------------

def test_the_pairing_code_alphabet_is_the_same_on_both_sides():
    assert daemon_main.ALPHABET == relay_module.ALPHABET
    assert daemon_main.CODE_LENGTH == relay_module.CODE_LENGTH


def test_a_code_the_daemon_mints_is_one_the_relay_accepts_unchanged():
    for _ in range(200):
        code = daemon_main.generate_pairing_code()
        assert relay_module.normalize_code(code) == code
        assert relay_module.normalize_code(daemon_main.format_pairing_code(code)) == code


def test_a_job_id_the_relay_mints_is_one_the_daemon_strips_again():
    for _ in range(200):
        job_id = relay_module.new_job_id()
        name = daemon_printer.suffixed_name('sample_part.gcode.3mf', job_id)
        assert daemon_printer.strip_job_suffix(name) == 'sample_part.gcode.3mf'
        assert relay_module.strip_job_suffix(name) == 'sample_part.gcode.3mf'


def test_the_daemons_snapshot_is_what_the_relay_reads():
    snapshot = daemon_printer.map_status(daemon_fakes.H2S['paused'])
    relay = relay_module.PrinterRelay(clock=relay_fakes.FakeClock())
    relay.note_code(relay_fakes.CODE)
    relay.note_daemon(relay_fakes.CODE)
    relay.store_status(relay_fakes.CODE, snapshot)
    ok, reason, _ = relay.claim_job(relay_fakes.CODE, job_id='j1', download_path='/d',
                                    filename='f', team_number=None)
    # The H2S reports the subtask name, without the extension.
    assert (ok, reason) == (False, 'Paused, sample_part')


# --- the pieces of the together run ------------------------------------------------------

def test_the_in_process_response_reads_like_a_requests_response(tmp_path, bench):
    response = bench.session.get(f'{BASE}/printer/status?x=1', headers={})
    assert bench.session.calls[-1] == ('GET', '/printer/status?x=1')
    assert response.json()['paired'] is True
    with response as same:
        assert same is response
    assert response.closed is True


def test_the_in_process_response_chunks_and_refuses_non_json(tmp_path):
    class Raw:
        status_code = 200
        headers = {}

        def get_data(self):
            return b'abcde'

        def close(self):
            pass

    response = InProcessResponse(Raw())
    assert list(response.iter_content(chunk_size=2)) == [b'ab', b'cd', b'e']
    with pytest.raises(ValueError):
        response.json()


def test_the_stand_in_refuses_to_start_a_file_it_was_not_sent():
    printer = StandInPrinter()
    assert printer.start('missing.gcode.3mf') is False
    assert printer.snapshot()['state'] == 'idle'


def test_the_stand_in_answers_a_delete_with_the_daemons_outcomes():
    printer = StandInPrinter()
    assert printer.delete('missing.gcode.3mf') == (daemon_printer.NOT_ON_PRINTER,
                                                   '550 No such file.')
    printer.received['p.gcode.3mf'] = b'x'
    assert printer.delete('p.gcode.3mf') == (daemon_printer.REMOVED, '250 Deleted.')
    assert printer.deleted == ['missing.gcode.3mf', 'p.gcode.3mf']


def test_describe_names_each_part_of_a_status():
    describe = together_main.describe
    assert describe({'error': 'Too Many Requests: 120 per 1 minute'}) == \
        'status refused: Too Many Requests: 120 per 1 minute'
    assert describe({'waiting': True}) == 'waiting for the daemon, no job'
    assert describe({'online': True, 'status': {'state': 'running',
                                                'display_name': 'p.gcode.3mf'},
                     'job': {'id': 'j1', 'state': 'pending'},
                     'last_result': {'ok': False, 'reason': 'download answered 404'}}) == (
        'online, printer running p.gcode.3mf, job j1 pending, '
        'last result failed: download answered 404 [delivery.job_failed]')


@pytest.mark.real_time
def test_the_together_run_in_process():
    out = io.StringIO()
    assert together_main.run(in_process=True, out=out) == 0, out.getvalue()
    assert 'PASS' in out.getvalue()


@pytest.mark.real_time
def test_the_together_run_over_loopback_on_an_ephemeral_port():
    out = io.StringIO()
    assert together_main.run(in_process=False, out=out) == 0, out.getvalue()
    text = out.getvalue()
    assert 'listening at http://127.0.0.1:' in text
    assert '/printer/download/' not in text      # no download token in the output
