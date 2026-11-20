"""The delivery job on the daemon, against fakes on both links and a fake clock: every
stage it reports, the waits for the printer, the retries with backoff and jitter, the start
gate, cancellation at each point before the start, restarts, the queued acknowledgement,
and the printer misbehaving in each way the daemon can see.

Each test is one deterministic scenario; nothing sleeps or opens a socket."""
import os
import shutil
import tempfile
import unittest

from penguin_delivery_daemon import printer as pr
from penguin_delivery_daemon import run_loop as rl
from penguin_delivery_daemon.config import DaemonConfig
from penguin_delivery_daemon.relay_client import DownloadCorrupt, RelayError

from daemon_fakes import (
    H2S, IDLE, JOB, SUFFIXED, FakeBambuPrinter, FakeClock, FakePrinter, FakeRelay,
    StepExecutor, running,
)

UNREACHABLE = dict(IDLE, state=pr.UNREACHABLE)


class FlowTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.logged = []
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.config = DaemonConfig(backend_url='https://example.test', pairing_code='7K3MQ9XW',
                                   token='signed', path=os.path.join(self.tmp, 'c.toml'))
        self.relay = FakeRelay(token='signed')
        self.printer = FakePrinter(starts_running=True)
        self.sleeps = []                 # hooks run on each sleep, in order

    def sleep(self, seconds):
        self.clock.sleep(seconds)
        if self.sleeps:
            hook = self.sleeps.pop(0)
            if hook is not None:
                hook()

    def make(self, **overrides):
        kwargs = dict(clock=self.clock, sleep=self.sleep,
                      log=lambda *a: self.logged.append(' '.join(str(x) for x in a)),
                      executor=rl.InlineExecutor(), download_dir=self.tmp,
                      rand=lambda: 0.0, instance='daemon-a',
                      save_token=lambda token, path: None)
        kwargs.update(overrides)
        return rl.RunLoop(self.config, self.relay, self.printer, **kwargs)

    def run_job(self, loop=None, job=None):
        loop = loop or self.make()
        self.relay.sync_job = dict(job or JOB)
        loop.tick()
        return loop

    def outcome(self):
        """(ok, reason, code) of the one acknowledgement."""
        self.assertEqual(len(self.relay.acks), 1, self.relay.acks)
        job_id, ok, reason = self.relay.acks[0]
        return ok, reason, self.relay.ack_codes[0]

    def lines(self, needle):
        return [line for line in self.logged if needle in line]


class TestStagesAndProgress(FlowTestCase):
    def test_each_stage_is_reported_to_the_relay_on_the_next_sync(self):
        executor = StepExecutor()
        loop = self.make(executor=executor)
        self.relay.sync_job = dict(JOB)
        loop.tick()
        seen = []
        original = loop._stage

        def stage(job_id, name, **fields):
            original(job_id, name, **fields)
            self.clock.advance(1)
            loop.tick()                     # the tick thread syncs while the job runs
            seen.append(self.relay.progress[-1])

        loop._stage = stage
        executor.release()
        stages = [p['stage'] for p in seen if p]
        self.assertEqual(stages[0], 'downloading')
        self.assertIn('uploading', stages)
        self.assertEqual(stages[-1], 'starting')
        uploads = [p for p in seen if p and p['stage'] == 'uploading']
        self.assertEqual((uploads[-1]['bytes_sent'], uploads[-1]['bytes_total']), (9, 9))
        self.assertTrue(all(p['id'] == 'j8f3a2c1' for p in seen if p))
        self.assertIsNone(loop.job_progress)          # cleared once the job ended

    def test_progress_is_synced_at_most_once_a_second(self):
        loop = self.make()
        loop.tick()
        loop._stage('j8f3a2c1', 'uploading', bytes_sent=1, bytes_total=9)
        loop.tick()                                    # less than a second: nothing
        self.assertEqual(len(self.relay.syncs), 1)
        self.clock.advance(1)
        loop.tick()
        self.assertEqual(len(self.relay.syncs), 2)
        self.clock.advance(1)
        loop.tick()                                    # unchanged progress: no sync
        self.assertEqual(len(self.relay.syncs), 2)


class TestThePrinterWhenTheJobArrives(FlowTestCase):
    def test_off_when_the_job_arrives_and_on_later_the_job_goes_through(self):
        self.printer.set(UNREACHABLE)
        self.sleeps = [None] * 10 + [lambda: self.printer.set(dict(IDLE))]
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(len(self.printer.uploads), 1)
        self.assertTrue(self.lines('waiting for the printer to answer'))

    def test_off_for_longer_than_the_wait_fails_with_the_minutes(self):
        self.printer.set(UNREACHABLE)
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.printer_unreachable_at_start'))
        self.assertEqual(self.printer.uploads, [])
        self.assertEqual(self.relay.downloads, [])
        # Waited in bounded steps, never a tight loop.
        self.assertTrue(all(s >= 1.0 for s in self.clock.slept))
        self.assertLessEqual(len(self.clock.slept), rl.PRINTER_WAIT_SECONDS)

    def test_busy_paused_error_door_filament_calibration_and_firmware(self):
        """The printer's main state decides (round 3, defect 1): a pause, a door open, the
        filament run out and a calibration are a going print; a firmware update reports a
        main state this version does not know."""
        other = {'subtask_name': 'other-j00000001'}
        cases = {
            'busy': (running('other-j00000001'), 'delivery.printer_busy_at_start'),
            'paused': (dict(IDLE, state=pr.PAUSED, file='other'),
                       'delivery.printer_busy_at_start'),
            'door open': (pr.map_status(dict(H2S['paused'], stg_cur=17, **other)),
                          'delivery.printer_busy_at_start'),
            'out of filament': (pr.map_status(dict(H2S['paused'], stg_cur=6, **other)),
                                'delivery.printer_busy_at_start'),
            'mid calibration': (pr.map_status(dict(H2S['running'], stg_cur=1, **other)),
                                'delivery.printer_busy_at_start'),
            'running, unknown stage': (pr.map_status(dict(H2S['running'], stg_cur=90,
                                                          **other)),
                                       'delivery.printer_busy_at_start'),
            'updating firmware': (pr.map_status(dict(H2S['idle'], gcode_state='UPGRADING')),
                                  'delivery.printer_state_unrecognised_at_start'),
        }
        for name, (snapshot, code) in cases.items():
            with self.subTest(name):
                self.relay = FakeRelay(token='signed')
                self.printer = FakePrinter(snapshot=snapshot)
                self.run_job()
                ok, reason, got = self.outcome()
                self.assertEqual((ok, got), (False, code))
                self.assertEqual(self.printer.uploads, [])
                self.assertEqual(self.printer.starts, [])

    def test_an_unrecognised_state_names_the_raw_value_in_the_log_and_the_detail(self):
        self.printer.set(pr.map_status(dict(H2S['idle'], gcode_state='UPGRADING')))
        self.run_job()
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_state_unrecognised_at_start'])
        self.assertIn("gcode_state 'UPGRADING'", self.relay.ack_details[0])
        self.assertTrue(self.lines("gcode_state 'UPGRADING'"))

    def test_a_printer_whose_last_print_ended_or_that_is_idle_with_any_stage_is_free(self):
        """Round 3, defects 1 and 4: an idle printer with a stage code the table does not
        know (-1, 99), or one left over from a pause (16) or a print (7), and a printer
        whose last print finished, failed or was stopped, all take the new print."""
        cases = {
            'idle, stage -1': dict(H2S['idle'], stg_cur=-1),
            'idle, stage 99': dict(H2S['idle'], stg_cur=99),
            'idle, a pause stage left over': dict(H2S['idle'], stg_cur=16),
            'idle, a print stage left over': dict(H2S['idle'], stg_cur=7),
            'finished': H2S['finished'],
            'failed': H2S['failed_with_hms'],
            'stopped': dict(H2S['failed_with_hms'], print_error=0x0300400C, hms=[]),
            'idle with an error code': dict(H2S['idle'], print_error=0x07008011),
        }
        for name, document in cases.items():
            with self.subTest(name):
                self.relay = FakeRelay(token='signed')
                document = dict(document, subtask_name='old_part-j00000001')
                self.printer = FakePrinter(snapshot=pr.map_status(document),
                                           starts_running=True)
                self.run_job()
                self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
                self.assertEqual(self.printer.starts, [SUFFIXED])

    def test_busy_names_the_other_print_and_its_progress(self):
        self.printer.set(running('other-j00000001'))
        self.run_job()
        self.assertEqual(self.outcome()[1], 'the printer is busy with other at 3 percent')


class TestDownload(FlowTestCase):
    def test_a_failed_download_is_retried_with_backoff_then_succeeds(self):
        self.relay.download_errors = [RelayError('reset'), RelayError('reset'), None]
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(len(self.relay.downloads), 3)

    def test_the_backoff_between_attempts_doubles_and_is_jittered(self):
        draws = iter([1.0, 0.5])
        self.relay.download_errors = [RelayError('a'), RelayError('b'), None]
        self.run_job(self.make(rand=lambda: next(draws)))
        waits = self.lines('the download did not work')
        self.assertEqual([w.rsplit(' ', 1)[1] for w in waits], ['4s', '9s'])  # 5*.75, 10*.875

    def test_three_failures_fail_the_job_with_download_failed(self):
        self.relay.download_errors = [RelayError('stalled')] * 3
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, reason, code), (False, 'stalled', 'delivery.download_failed'))
        self.assertEqual(self.printer.uploads, [])

    def test_wrong_content_three_times_fails_as_corrupt(self):
        self.relay.download_errors = [DownloadCorrupt('checksum')] * 3
        self.run_job()
        self.assertEqual(self.outcome()[2], 'delivery.download_corrupt')

    def test_the_job_passes_the_relays_size_and_checksum_on(self):
        calls = {}
        original = self.relay.download

        def download(path, dest, **kwargs):
            calls.update(kwargs)
            return original(path, dest, **kwargs)

        self.relay.download = download
        self.run_job(job=dict(JOB, size=9, sha256='ab' * 32))
        self.assertEqual((calls['size'], calls['sha256']), (9, 'ab' * 32))


class TestUpload(FlowTestCase):
    def test_cut_at_each_quarter_then_returns_the_upload_is_retried_and_succeeds(self):
        for quarter in (1, 2, 3, 4):
            with self.subTest(quarter=quarter):
                self.relay = FakeRelay(token='signed')
                self.printer = FakePrinter(starts_running=True)
                self.printer.upload_errors = [
                    pr.UploadFailed(f'the printer has {quarter * 25} of 100 bytes'), None]
                self.run_job()
                self.assertEqual(self.outcome(), (True, None, None))
                self.assertEqual(len(self.printer.uploads), 1)

    def test_refused_three_times_fails_and_removes_the_partial_file(self):
        self.printer.upload_errors = [pr.UploadFailed('refused', detail='550')] * 3
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.upload_failed'))
        self.assertEqual(self.printer.deleted, [SUFFIXED])
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.relay.gates, [])

    def test_the_printer_dropping_off_mid_upload_waits_for_it_to_return(self):
        self.printer.upload_errors = [OSError('connection lost'), None]
        # The pause after the failure, then the printer is unreachable for a while.
        self.sleeps = [lambda: self.printer.set(UNREACHABLE)] + [None] * 5 + \
            [lambda: self.printer.set(dict(IDLE))]
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))

    def test_the_downloaded_file_is_removed_whatever_happens(self):
        self.printer.upload_errors = [pr.UploadFailed('refused')] * 3
        self.run_job()
        self.assertEqual(os.listdir(self.tmp), [])

    def test_a_filename_windows_forbids_is_made_safe(self):
        self.run_job(job=dict(JOB, filename='CON:<part>?.gcode.3mf'))
        name = self.printer.uploads[0][0]
        self.assertEqual(name, 'CON__part__-j8f3a2c1.gcode.3mf')
        self.assertEqual(pr.safe_file_name('CON.gcode.3mf'), '_CON.gcode.3mf')
        self.assertEqual(pr.safe_file_name('...'), 'sliced_part.gcode.3mf')
        self.assertEqual(pr.safe_file_name('a. '), 'a')
        long_name = pr.safe_file_name('x' * 300 + '.gcode.3mf')
        self.assertEqual((len(long_name), long_name[-10:]), (120, '.gcode.3mf'))
        self.assertEqual(len(pr.safe_file_name('y' * 300)), 120)


class TestTheStartGate(FlowTestCase):
    def test_the_file_is_started_only_after_the_gate_says_yes(self):
        order = []
        original_gate, original_start = self.relay.start_gate, self.printer.start
        self.relay.start_gate = lambda *a: order.append('gate') or original_gate(*a)
        self.printer.start = lambda name: order.append('start') or original_start(name)
        self.run_job()
        self.assertEqual(order, ['gate', 'start'])
        self.assertEqual(self.relay.gates, [('j8f3a2c1', 'daemon-a')])

    def test_a_relay_unreachable_at_the_gate_is_asked_again_until_it_answers(self):
        self.relay.gate_outcomes = [RelayError('down'), RelayError('down'), 'start']
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(len(self.relay.gates), 3)

    def test_a_relay_unreachable_for_the_whole_gate_wait_never_starts_the_file(self):
        self.relay.gate_outcomes = [RelayError('down')] * 1000
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.job_failed'))
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.printer.deleted, [SUFFIXED])
        self.assertLess(len(self.relay.gates), 40)     # backoff, not a tight loop

    def test_a_cancel_at_the_gate_removes_the_file_and_never_starts_it(self):
        self.relay.gate_outcomes = ['cancelled']
        self.run_job()
        self.assertEqual(self.outcome(), (False, 'cancelled', 'delivery.cancelled'))
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.printer.deleted, [SUFFIXED])

    def test_a_job_the_relay_no_longer_holds_is_not_started_and_not_acknowledged(self):
        self.relay.gate_outcomes = ['unknown']
        self.run_job()
        self.assertEqual(self.relay.acks, [])
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.printer.deleted, [SUFFIXED])

    def test_a_start_another_daemon_holds_is_never_made_here(self):
        """Two daemons claim the same pairing: only one starts the file."""
        self.relay.gate_outcomes = ['refused']
        self.printer.starts_running = False
        self.sleeps = [lambda: self.printer.set(running(SUFFIXED))]
        self.run_job()
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.outcome(), (True, None, None))


class TestTheStart(FlowTestCase):
    def test_accepted_and_nothing_happens_times_out_without_a_second_start(self):
        self.printer.starts_running = False
        self.run_job()
        self.assertEqual(self.outcome()[2], 'delivery.start_timeout')
        self.assertEqual(len(self.printer.starts), 1)

    def test_refused_is_start_refused(self):
        self.printer.start_result = False
        self.run_job()
        self.assertEqual(self.outcome()[2], 'delivery.start_refused')

    def test_the_printer_starts_a_different_file(self):
        self.printer.starts_running = False
        self.sleeps = [lambda: self.printer.set(running('someone_else-j00000009'))]
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.start_other_file'))
        self.assertEqual(reason, 'the printer started someone_else instead')

    def test_someone_starts_another_print_between_upload_and_start(self):
        original = self.relay.start_gate

        def gate(job_id, instance):
            self.printer.set(running('walk_up_print'))
            return original(job_id, instance)

        self.relay.start_gate = gate
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.printer_busy_at_start'))
        self.assertEqual(self.printer.starts, [])
        self.assertIn('someone started walk_up_print', reason)

    def test_the_printer_dropping_off_mid_start_is_never_sent_a_second_start(self):
        self.printer.starts_running = False
        self.printer.start_error = OSError('mqtt connection lost')
        self.sleeps = [lambda: self.printer.set(UNREACHABLE), None,
                       lambda: self.printer.set(running(SUFFIXED))]
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(len(self.printer.starts), 1)
        self.assertTrue(self.lines('may not have reached the printer'))

    def test_an_error_on_our_file_at_the_start_is_reported_with_its_code(self):
        self.printer.starts_running = False
        self.sleeps = [lambda: self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED[:-10],
                                                     job_name=SUFFIXED[:-10],
                                                     error='HMS_0300_0D00_0001_0003'))]
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.printer_error_at_start'))
        self.assertIn('HMS_0300_0D00_0001_0003', reason)


class TestCancellation(FlowTestCase):
    def cancel_on_sync(self, loop):
        """The relay's next sync carries the cancel for the running job."""
        loop._maybe_start_job(dict(JOB, cancel=True))

    def test_cancel_while_waiting_for_the_printer(self):
        self.printer.set(UNREACHABLE)
        loop = self.make()
        self.sleeps = [lambda: self.cancel_on_sync(loop)]
        self.run_job(loop)
        self.assertEqual(self.outcome(), (False, 'cancelled', 'delivery.cancelled'))
        self.assertEqual(self.relay.downloads, [])

    def test_cancel_during_the_download(self):
        loop = self.make()

        def download(path, dest, *, cancelled=None, **kwargs):
            self.cancel_on_sync(loop)
            from penguin_delivery_daemon.relay_client import Cancelled
            if cancelled():
                raise Cancelled('cancelled')

        self.relay.download = download
        self.run_job(loop)
        self.assertEqual(self.outcome()[2], 'delivery.cancelled')
        self.assertEqual(self.printer.uploads, [])

    def test_cancel_during_the_upload_removes_the_partial_file(self):
        loop = self.make()
        original = self.printer.upload

        def upload(local, remote, *, cancelled=None, progress=None):
            self.cancel_on_sync(loop)
            return original(local, remote, cancelled=cancelled, progress=progress)

        self.printer.upload = upload
        self.run_job(loop)
        self.assertEqual(self.outcome()[2], 'delivery.cancelled')
        self.assertEqual(self.printer.deleted, [SUFFIXED])
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.relay.gates, [])

    def test_cancel_in_the_pause_between_upload_attempts(self):
        loop = self.make()
        self.printer.upload_errors = [pr.UploadFailed('cut')]
        self.sleeps = [lambda: self.cancel_on_sync(loop)]
        self.run_job(loop)
        self.assertEqual(self.outcome()[2], 'delivery.cancelled')
        self.assertEqual(self.printer.deleted, [SUFFIXED])

    def test_a_cancelled_job_offered_to_a_fresh_daemon_is_acknowledged_cancelled_at_once(self):
        """Cancel while the daemon was unreachable takes effect when it returns."""
        self.run_job(job=dict(JOB, cancel=True))
        self.assertEqual(self.outcome()[2], 'delivery.cancelled')
        self.assertEqual(self.relay.downloads, [])

    def test_a_cancel_logged_once_however_many_syncs_repeat_it(self):
        executor = StepExecutor()
        loop = self.make(executor=executor)
        self.run_job(loop)
        for _ in range(3):
            loop._maybe_start_job(dict(JOB, cancel=True))
        self.assertEqual(len(self.lines('cancel requested')), 1)


class TestRestarts(FlowTestCase):
    def test_a_start_granted_before_a_restart_is_never_made_again(self):
        self.printer.starts_running = False
        self.sleeps = [lambda: self.printer.set(running(SUFFIXED))]
        self.run_job(job=dict(JOB, start_granted=True))
        self.assertEqual(self.printer.uploads, [])
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.outcome(), (True, None, None))

    def test_a_start_granted_whose_print_never_appears_times_out_without_starting(self):
        self.printer.starts_running = False
        self.run_job(job=dict(JOB, start_granted=True))
        self.assertEqual(self.outcome()[2], 'delivery.start_timeout')
        self.assertEqual(self.printer.starts, [])

    def test_leftovers_of_an_earlier_run_are_removed_at_start(self):
        for name in ('p-j8f3a2c1.gcode.3mf', 'p-j8f3a2c1.gcode.3mf.part', 'keep.txt'):
            with open(os.path.join(self.tmp, name), 'wb') as fh:
                fh.write(b'x')
        self.make()
        self.assertEqual(os.listdir(self.tmp), ['keep.txt'])
        self.assertTrue(self.lines('removed 2 file(s) an earlier run left'))

    def test_a_missing_download_directory_is_not_an_error(self):
        rl.RunLoop(self.config, self.relay, self.printer, download_dir='/nonexistent/x',
                   executor=rl.InlineExecutor(), log=self.logged.append)


class TestQueuedAcknowledgements(FlowTestCase):
    def test_a_lost_acknowledgement_is_sent_again_with_backoff_until_it_lands(self):
        loop = self.make()
        self.relay.ack_error = RelayError('reset')
        self.run_job(loop)
        self.assertIn('j8f3a2c1', loop.pending_acks)
        loop.tick()                                   # not due yet: a sync instead
        self.assertEqual(len(self.relay.acks), 1)
        self.clock.advance(5)
        loop.tick()
        self.assertEqual(len(self.relay.acks), 2)
        self.assertEqual(loop.pending_acks, {})
        self.assertIn('j8f3a2c1', loop.acked_job_ids)

    def test_repeated_failures_double_the_wait_to_the_cap(self):
        loop = self.make()
        self.relay.ack_error = RelayError('down')
        self.run_job(loop)
        waits = []
        for _ in range(6):
            entry = loop.pending_acks['j8f3a2c1']
            waits.append(entry['due'] - self.clock.now)
            self.clock.advance(waits[-1])
            self.relay.ack_error = RelayError('down')
            loop.tick()
        self.assertEqual(waits, [5.0, 10.0, 20.0, 40.0, 60.0, 60.0])

    def test_a_re_offer_while_the_acknowledgement_is_queued_starts_nothing(self):
        loop = self.make()
        self.relay.ack_error = RelayError('reset')
        self.run_job(loop)
        loop._maybe_start_job(dict(JOB))
        self.assertEqual(len(self.printer.uploads), 1)


class TestTheRealLinkAgainstTheLibraryFake(FlowTestCase):
    """The run loop with the real PrinterLink, its library replaced by FakeBambuPrinter."""

    def setUp(self):
        super().setUp()
        self.bambu = None

        def factory(ip, access_code, serial):
            self.bambu = FakeBambuPrinter(ip, access_code, serial)
            return self.bambu

        self.printer = pr.PrinterLink('10.0.0.42', '01P00A', 'not-a-code',
                                      printer_factory=factory, clock=self.clock,
                                      log=self.logged.append)
        self.printer.connect()
        self.bambu.report = dict(H2S['idle'])

    def h2s_running(self, name):
        return dict(H2S['running_as_reported_by_h2s'], subtask_name=name[:-len('.gcode.3mf')])

    def test_a_short_file_with_a_226_is_caught_and_never_started(self):
        self.bambu.short_by = 3
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.upload_failed'))
        self.assertEqual(reason, 'the printer has 6 of 9 bytes')
        self.assertIsNone(self.bambu.started)
        self.assertIn(SUFFIXED, self.bambu.deleted)

    def test_a_status_document_that_is_not_json_reads_as_unreachable(self):
        self.bambu.report = 'not json'
        self.assertEqual(self.printer.snapshot()['state'], pr.UNREACHABLE)

    def test_a_silent_status_stream_shows_its_age(self):
        self.bambu.report = self.h2s_running(SUFFIXED)
        self.printer.snapshot()
        self.clock.advance(120)
        self.assertEqual(self.printer.snapshot()['report_age_s'], 120)

    def test_reconnecting_with_stale_status_of_our_own_print_is_still_recognised(self):
        """The printer comes back and repeats its last report: our job is ours."""
        self.bambu.report = self.h2s_running(SUFFIXED)
        self.bambu.connected = False
        self.assertEqual(self.printer.snapshot()['state'], pr.UNREACHABLE)
        self.bambu.connected = True
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertIsNone(self.bambu.uploaded)


class AskablePrinter(FakePrinter):
    """A FakePrinter that counts the daemon's requests for a whole report, and records the
    snapshot the daemon read last before each start command."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requests = 0
        self.last_read = None
        self.start_evidence = []

    def request_report(self):
        self.requests += 1

    def snapshot(self):
        self.last_read = super().snapshot()
        return dict(self.last_read)

    def start(self, remote_name):
        self.start_evidence.append(self.last_read)
        return super().start(remote_name)


STALE_IDLE = dict(IDLE, report_age_s=int(rl.FRESH_REPORT_SECONDS) + 25)
FRESH_IDLE = dict(IDLE, report_age_s=0)


class TestFreshWordBeforeTheStart(FlowTestCase):
    """Round 3, defect 3: a start command is sent only on a report younger than
    FRESH_REPORT_SECONDS that shows no print going on. Without one, the daemon asks the
    printer for a report and waits in `waiting_for_printer`, where a cancel still ends it."""

    def setUp(self):
        super().setUp()
        self.printer = AskablePrinter(snapshot=dict(FRESH_IDLE), starts_running=True)
        self.stages = []

    def watch_stage(self, loop):
        """Each sleep records the stage the next sync would carry."""
        def hook():
            self.stages.append((loop.job_progress or {}).get('stage'))
        return hook

    def assert_started_on_fresh_word_only(self):
        for evidence in self.printer.start_evidence:
            self.assertIn(evidence['state'], (pr.IDLE, pr.FINISHED, pr.ERROR))
            self.assertLessEqual(evidence['report_age_s'], rl.FRESH_REPORT_SECONDS)

    def test_a_quiet_printer_at_arrival_is_asked_and_the_job_waits_then_goes_on(self):
        self.printer.set(dict(STALE_IDLE))
        loop = self.make()
        watch = self.watch_stage(loop)
        self.sleeps = [watch, watch, watch, lambda: self.printer.set(dict(FRESH_IDLE))]
        self.run_job(loop)
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(self.stages, ['waiting_for_printer'] * 3)
        self.assertGreaterEqual(self.printer.requests, 1)
        self.assertEqual(self.printer.starts, [SUFFIXED])
        self.assertTrue(self.lines('waiting for a fresh report from the printer'))
        self.assert_started_on_fresh_word_only()

    def test_a_printer_quiet_for_the_whole_wait_ends_the_job_unstarted(self):
        self.printer.set(dict(STALE_IDLE))
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.printer_unreachable_at_start'))
        self.assertIn('no fresh report', self.relay.ack_details[0])
        self.assertEqual((self.relay.downloads, self.printer.uploads, self.printer.starts),
                         ([], [], []))
        # Asked again every REPORT_REQUEST_SECONDS, never in a tight loop.
        self.assertEqual(self.printer.requests,
                         int(rl.PRINTER_WAIT_SECONDS / rl.REPORT_REQUEST_SECONDS))

    def test_a_stale_report_of_a_busy_printer_is_waited_out_not_believed(self):
        """A quiet printer whose last word was a print: wait for fresh word, then judge."""
        self.printer.set(dict(running('other-j00000001'), report_age_s=300))
        self.sleeps = [None, lambda: self.printer.set(dict(FRESH_IDLE))]
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))

    def test_a_cancel_while_waiting_for_fresh_word_ends_it_unstarted(self):
        self.printer.set(dict(STALE_IDLE))
        loop = self.make()
        self.sleeps = [None, lambda: loop._maybe_start_job(dict(JOB, cancel=True))]
        self.run_job(loop)
        self.assertEqual(self.outcome(), (False, 'cancelled', 'delivery.cancelled'))
        self.assertEqual((self.relay.downloads, self.printer.starts), ([], []))

    def test_after_the_gate_a_quiet_printer_is_asked_before_the_start_command(self):
        original = self.relay.start_gate

        def gate(job_id, instance):
            self.printer.set(dict(STALE_IDLE))           # quiet from the gate on
            return original(job_id, instance)

        self.relay.start_gate = gate
        loop = self.make()
        watch = self.watch_stage(loop)
        self.sleeps = [watch, watch, lambda: self.printer.set(dict(FRESH_IDLE))]
        self.run_job(loop)
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(self.stages, ['waiting_for_printer'] * 2)
        self.assertEqual(self.printer.starts, [SUFFIXED])
        self.assert_started_on_fresh_word_only()

    def test_after_the_gate_a_printer_quiet_for_the_whole_wait_means_no_start(self):
        original = self.relay.start_gate

        def gate(job_id, instance):
            self.printer.set(dict(STALE_IDLE))
            return original(job_id, instance)

        self.relay.start_gate = gate
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.printer_unreachable_at_start'))
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.printer.deleted, [SUFFIXED])

    def test_after_the_gate_fresh_word_of_another_print_means_no_start(self):
        original = self.relay.start_gate

        def gate(job_id, instance):
            self.printer.set(dict(STALE_IDLE))
            return original(job_id, instance)

        self.relay.start_gate = gate
        self.sleeps = [None, lambda: self.printer.set(dict(running('walk_up_print'),
                                                           report_age_s=0))]
        self.run_job()
        ok, reason, code = self.outcome()
        self.assertEqual((ok, code), (False, 'delivery.printer_busy_at_start'))
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.printer.deleted, [SUFFIXED])

    def test_an_unrecognised_state_just_before_the_start_means_no_start(self):
        original = self.relay.start_gate

        def gate(job_id, instance):
            self.printer.set(pr.map_status(dict(H2S['idle'], gcode_state='UPGRADING')))
            return original(job_id, instance)

        self.relay.start_gate = gate
        self.run_job()
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_state_unrecognised_at_start'])
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.printer.deleted, [SUFFIXED])


class TestLeavingTheStartWait(FlowTestCase):
    """Round 3, defect 3: a daemon in the start wait of a job the relay no longer holds
    (the caller stopped following it) leaves the wait, so the next job is taken up."""

    def setUp(self):
        super().setUp()
        self.printer.starts_running = False

    def test_the_daemon_leaves_the_start_wait_once_the_relay_says_unknown(self):
        # The gate grants, then answers 'unknown' at the first hold check; the printer has
        # gone unreachable since the start command, so the wait would otherwise never end.
        self.relay.gate_outcomes = ['start', 'unknown']
        original = self.printer.start

        def start(remote_name):
            accepted = original(remote_name)
            self.printer.set(UNREACHABLE)
            return accepted

        self.printer.start = start
        loop = self.run_job()
        self.assertEqual(self.relay.acks, [])                   # nobody waits for one
        self.assertEqual(self.printer.starts, [SUFFIXED])
        self.assertEqual(self.printer.deleted, [])               # it may be printing
        self.assertIsNone(loop.running_job_id)
        self.assertTrue(self.lines('the relay no longer holds this job'))
        waited = sum(self.clock.slept)
        self.assertGreaterEqual(waited, rl.HOLD_CHECK_SECONDS)
        self.assertLess(waited, rl.HOLD_CHECK_SECONDS + 2 * rl.START_POLL_SECONDS)
        # The next delivery job is taken up at once.
        self.printer.start = original
        self.printer.set(dict(IDLE))
        self.printer.starts_running = True
        self.run_job(loop, job=dict(JOB, id='j0000abcd'))
        self.assertEqual(self.relay.acks, [('j0000abcd', True, None)])

    def test_a_hold_check_that_gets_no_answer_keeps_waiting(self):
        self.relay.gate_outcomes = ['start', RelayError('reset'), 'refused']
        polls = {'n': 0}
        original = self.printer.start

        def start(remote_name):
            accepted = original(remote_name)
            self.printer.set(UNREACHABLE)
            return accepted

        def sleep_hook():
            polls['n'] += 1
            if polls['n'] == 40:                                 # 80 s on
                self.printer.set(running(SUFFIXED))

        self.printer.start = start
        self.sleeps = [sleep_hook] * 40
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(len(self.relay.gates), 3)               # the gate, two checks


class TestTheRemainingFailurePaths(FlowTestCase):
    """Round 3, defect 8: the five failure paths of the second review, each asserting what
    the relay is told and that nothing is started twice."""

    def test_a_file_that_could_not_be_removed_from_the_printer_is_said_so(self):
        loop = self.make()
        self.printer.delete = lambda remote_name: False
        original = self.printer.upload

        def upload(local, remote, *, cancelled=None, progress=None):
            loop._maybe_start_job(dict(JOB, cancel=True))
            return original(local, remote, cancelled=cancelled, progress=progress)

        self.printer.upload = upload
        self.run_job(loop)
        self.assertEqual(self.outcome(), (False, 'cancelled', 'delivery.cancelled'))
        self.assertTrue(self.lines(f'could not confirm {SUFFIXED} was removed'))
        self.assertEqual(self.printer.starts, [])

    def test_a_job_that_arrives_already_cancelled_is_acknowledged_without_a_download(self):
        loop = self.make()
        loop.handle_job(dict(JOB, cancel=True))
        self.assertEqual(self.outcome(), (False, 'cancelled', 'delivery.cancelled'))
        self.assertEqual((self.relay.downloads, self.printer.starts), ([], []))
        self.assertIsNone(loop.running_job_id)

    def test_a_cancel_in_the_pause_between_download_attempts(self):
        loop = self.make()
        self.relay.download_errors = [RelayError('reset')]
        self.sleeps = [lambda: loop._maybe_start_job(dict(JOB, cancel=True))]
        self.run_job(loop)
        self.assertEqual(self.outcome(), (False, 'cancelled', 'delivery.cancelled'))
        self.assertEqual(len(self.relay.downloads), 1)
        self.assertEqual((self.printer.uploads, self.printer.starts), ([], []))

    def test_the_printer_already_printing_our_file_when_the_start_is_due(self):
        original = self.relay.start_gate

        def gate(job_id, instance):
            self.printer.set(running(SUFFIXED))   # another daemon of the pairing started it
            return original(job_id, instance)

        self.relay.start_gate = gate
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(self.printer.starts, [])
        self.assertTrue(self.lines('not starting it again'))

    def test_our_file_named_by_an_idle_printer_is_not_taken_as_printing(self):
        """An idle printer that still names our file has not printed it (no start was
        granted): the job goes on, and the file is started once."""
        self.printer.set(dict(IDLE, file=SUFFIXED[:-len('.gcode.3mf')],
                              job_name=SUFFIXED[:-len('.gcode.3mf')]))
        self.run_job()
        self.assertEqual(self.outcome(), (True, None, None))
        self.assertEqual(len(self.printer.uploads), 1)
        self.assertEqual(self.printer.starts, [SUFFIXED])
