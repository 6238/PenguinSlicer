"""The run loop, with the relay client and the printer replaced by fakes.

Every interval is on the injected monotonic clock and every sleep moves that clock instead
of waiting, so the whole file runs in milliseconds.

Ported from the original daemon's test_run_loop.py. Rewritten: the original's sleep only
recorded its argument without moving the clock, so any test that reached the start wait
without the printer reporting at once would have spun forever; here sleep moves the fake
clock. TestJobProgressIsLogged subclassed TestJobHandling and so ran every job test twice;
it is now a class of its own. The repeated make_paired/deliver helpers are one base class.
New: exchange failures, the run loop's tick while blocked, the start wait's polling, a
daemon restarted at each point of a job, and the two known faults."""
import os
import shutil
import tempfile
import unittest

import pytest

from penguin_delivery_daemon import printer as pr
from penguin_delivery_daemon import run_loop as rl
from penguin_delivery_daemon.config import DaemonConfig
from penguin_delivery_daemon.relay_client import (
    ChallengeDetected, RateLimited, RelayError, TokenRejected,
)

from daemon_fakes import (
    H2S, IDLE, JOB, SUFFIXED, FakeBambuPrinter, FakeClock, FakePrinter, FakeRelay,
    StepExecutor, running,
)


class RunLoopTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.logged = []
        self.saved_tokens = []
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.config = DaemonConfig(backend_url='https://example.test',
                                   printer_ip='10.0.0.42', printer_serial='01P00A',
                                   access_code='12345678', pairing_code='7K3MQ9XW',
                                   token='', path=os.path.join(self.tmp, 'config.toml'))
        self.relay = FakeRelay()
        self.printer = FakePrinter()

    def make(self, **overrides):
        kwargs = dict(clock=self.clock, sleep=self.clock.sleep,
                      log=lambda *a: self.logged.append(' '.join(str(x) for x in a)),
                      executor=rl.InlineExecutor(),
                      download_dir=self.tmp,
                      save_token=lambda token, path: self.saved_tokens.append((token, path)))
        kwargs.update(overrides)
        return rl.RunLoop(self.config, self.relay, self.printer, **kwargs)

    def make_paired(self, **overrides):
        self.relay.token = 'signed'
        self.config.token = 'signed'
        return self.make(**overrides)

    def deliver(self, loop, job=None):
        """Let one sync return a job."""
        self.relay.sync_job = dict(job or JOB)
        loop.tick()

    def lines(self, needle):
        return [line for line in self.logged if needle in line]


class TestExchange(RunLoopTestCase):
    def test_the_first_tick_exchanges_and_saves_the_token(self):
        loop = self.make()
        loop.tick()
        self.assertEqual(self.relay.exchanges, ['7K3MQ9XW'])
        self.assertEqual(self.saved_tokens, [('signed', self.config.path)])
        self.assertEqual(self.relay.token, 'signed')
        self.assertEqual(self.config.token, 'signed')
        self.assertEqual(self.lines('paired with the backend'), ['paired with the backend'])

    def test_once_paired_the_next_tick_syncs(self):
        loop = self.make()
        loop.tick()
        loop.tick()
        self.assertEqual(len(self.relay.exchanges), 1)
        self.assertEqual(len(self.relay.syncs), 1)

    def test_a_404_retries_every_thirty_seconds_and_logs_once_a_minute(self):
        self.relay.exchange_result = None
        loop = self.make()
        for _ in range(5):
            loop.tick()
            self.clock.advance(30)
        self.assertEqual(len(self.relay.exchanges), 5)
        self.assertEqual(len(self.lines('waiting for the pairing code')), 3)  # 0, 60, 120 s
        self.assertEqual(self.saved_tokens, [])

    def test_no_exchange_before_thirty_seconds_have_passed(self):
        self.relay.exchange_result = None
        loop = self.make()
        loop.tick()
        self.clock.advance(29)
        loop.tick()
        self.assertEqual(len(self.relay.exchanges), 1)
        self.clock.advance(1)
        loop.tick()
        self.assertEqual(len(self.relay.exchanges), 2)

    def test_a_429_honours_retry_after(self):
        self.relay.exchange_error = RateLimited(90.0)
        loop = self.make()
        loop.tick()
        self.assertEqual(self.lines('rate limited'), ['pairing is rate limited; waiting 90s'])
        self.clock.advance(60)
        loop.tick()
        self.assertEqual(len(self.relay.exchanges), 1)   # still inside the 90 s window
        self.clock.advance(30)
        loop.tick()
        self.assertEqual(len(self.relay.exchanges), 2)

    def test_a_challenge_on_the_exchange_backs_off_and_names_it(self):
        self.relay.exchange_error = ChallengeDetected('got HTML')
        loop = self.make()
        loop.tick()
        self.assertEqual(loop.last_error_kind, 'challenge')
        self.assertEqual(loop.backoff_until, self.clock.now + rl.BACKOFF_START)

    def test_a_network_error_on_the_exchange_backs_off(self):
        self.relay.exchange_error = RelayError('connection refused')
        loop = self.make()
        loop.tick()
        self.assertEqual(loop.last_error_kind, 'network')
        self.assertEqual(self.lines('network:'),
                         ['network: connection refused; retrying in 5s'])
        self.clock.advance(4)
        loop.tick()                                      # blocked: nothing at all
        self.assertEqual(len(self.relay.exchanges), 1)
        self.clock.advance(30)
        loop.tick()
        self.assertEqual(self.relay.token, 'signed')
        self.assertIsNone(loop.last_error_kind)          # the success cleared it
        self.assertEqual(loop.backoff, rl.BACKOFF_START)

    def test_a_401_on_sync_blanks_the_token_and_re_exchanges(self):
        loop = self.make_paired()
        self.relay.sync_error = TokenRejected('repair')
        loop.tick()                        # the sync that gets rejected
        self.assertIsNone(self.relay.token)
        self.assertEqual(self.config.token, '')
        self.assertEqual(self.saved_tokens, [('', self.config.path)])
        loop.tick()                        # re-exchanges at once: the clock was reset
        self.assertEqual(self.relay.exchanges, ['7K3MQ9XW'])


class TestSync(RunLoopTestCase):
    def test_the_snapshot_is_posted_every_five_seconds(self):
        loop = self.make_paired()
        loop.tick()
        self.assertEqual(len(self.relay.syncs), 1)
        self.clock.advance(4)
        loop.tick()
        self.assertEqual(len(self.relay.syncs), 1)
        self.clock.advance(1)
        loop.tick()
        self.assertEqual(len(self.relay.syncs), 2)

    def test_a_state_change_syncs_at_once(self):
        loop = self.make_paired()
        loop.tick()
        self.clock.advance(1)
        self.printer.set(running(SUFFIXED))
        loop.tick()
        self.assertEqual(len(self.relay.syncs), 2)
        self.assertEqual(self.relay.syncs[-1]['state'], pr.RUNNING)

    def test_a_network_error_backs_off_doubling_to_a_cap(self):
        loop = self.make_paired()
        waits = []
        for _ in range(6):
            self.relay.sync_error = RelayError('connection refused')
            loop.tick()
            waits.append(loop.backoff_until - self.clock.now)   # the wait just applied
            self.clock.advance(waits[-1])
        self.assertEqual(waits, [5.0, 10.0, 20.0, 40.0, 60.0, 60.0])

    def test_a_successful_sync_resets_the_backoff(self):
        loop = self.make_paired()
        self.relay.sync_error = RelayError('boom')
        loop.tick()
        self.assertEqual(loop.backoff_until - self.clock.now, 5.0)
        self.clock.advance(5)
        loop.tick()
        self.assertEqual(loop.backoff, rl.BACKOFF_START)
        self.assertIsNone(loop.backoff_until)

    def test_a_cloudflare_challenge_is_named_in_the_log(self):
        loop = self.make_paired()
        self.relay.sync_error = ChallengeDetected('got HTML from the backend')
        loop.tick()
        self.assertEqual(self.lines('challenge:'),
                         ['challenge: got HTML from the backend; retrying in 5s'])
        self.assertEqual(loop.last_error_kind, 'challenge')

    def test_a_429_on_sync_waits_out_retry_after_without_growing_the_backoff(self):
        loop = self.make_paired()
        self.relay.sync_error = RateLimited(90.0)
        loop.tick()
        self.assertEqual(loop.backoff_until, self.clock.now + 90.0)
        self.assertEqual(loop.backoff, rl.BACKOFF_START)
        self.clock.advance(89)
        loop.tick()
        self.assertEqual(len(self.relay.syncs), 1)       # still inside the window
        self.clock.advance(1)
        loop.tick()
        self.assertEqual(len(self.relay.syncs), 2)


class TestJobHandling(RunLoopTestCase):
    """Download, upload, start, wait, acknowledge -- and every way that fails."""

    def setUp(self):
        super().setUp()
        self.printer.starts_running = True

    def test_a_job_is_downloaded_uploaded_started_and_acknowledged(self):
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.relay.downloads[0][0], '/printer/download/tok')
        self.assertEqual(self.printer.uploads, [(SUFFIXED, b'3mf-bytes')])
        self.assertEqual(self.printer.starts, [SUFFIXED])
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertIsNone(loop.running_job_id)
        self.assertIn('j8f3a2c1', loop.acked_job_ids)

    def test_the_downloaded_file_is_cleaned_up(self):
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(os.listdir(self.tmp), [])

    def test_a_download_failure_is_acknowledged_with_one_line(self):
        loop = self.make_paired()
        self.relay.download_error = RelayError('download answered 404')
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False, 'download answered 404')])
        self.assertEqual(self.printer.uploads, [])
        self.assertEqual(self.printer.starts, [])

    def test_an_upload_failure_is_acknowledged_and_the_file_is_still_removed(self):
        loop = self.make_paired()
        self.printer.upload_error = OSError('connection refused')
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False, 'connection refused')])
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(os.listdir(self.tmp), [])

    def test_a_start_that_returns_false_is_acknowledged_as_a_failure(self):
        loop = self.make_paired()
        self.printer.start_result = False
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False,
                                            'the printer refused the print start command')])

    def test_a_printer_that_never_reports_running_times_out_at_sixty_seconds(self):
        loop = self.make_paired()
        self.printer.starts_running = False                 # stays idle after the start
        started_at = self.clock.now
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False,
                                            'the printer did not start the file within 60s')])
        self.assertEqual(self.clock.now - started_at, rl.START_WAIT_SECONDS)
        self.assertEqual(self.clock.slept,
                         [rl.START_POLL_SECONDS] * int(rl.START_WAIT_SECONDS
                                                       / rl.START_POLL_SECONDS))

    def test_the_start_wait_acknowledges_as_soon_as_the_printer_reports(self):
        loop = self.make_paired()
        self.printer.starts_running = False
        polls = {'n': 0}

        def sleep(seconds):
            self.clock.sleep(seconds)
            polls['n'] += 1
            if polls['n'] == 3:                              # six seconds in
                self.printer.set(running(SUFFIXED))

        loop.sleep = sleep
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(polls['n'], 3)

    def test_a_printer_error_during_the_start_wait_is_acknowledged_with_its_code(self):
        loop = self.make_paired()
        self.printer.starts_running = False

        def sleep(seconds):
            self.clock.sleep(seconds)
            self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED,
                                  error='HMS_0300_0100_0001_0004'))

        loop.sleep = sleep
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False,
                                            'printer error: HMS_0300_0100_0001_0004')])

    def test_an_error_without_a_code_says_unknown(self):
        loop = self.make_paired()
        self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED))
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False, 'printer error: unknown')])

    def test_the_same_job_offered_on_every_sync_is_handled_once(self):
        """The relay re-offers a handed-out job until it is acknowledged, so the loop must
        dedupe on every sync, not only across a restart."""
        loop = self.make_paired()
        for _ in range(4):
            self.deliver(loop)
            self.clock.advance(6)
        self.assertEqual(len(self.printer.uploads), 1)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_a_job_with_no_id_is_ignored(self):
        loop = self.make_paired()
        self.deliver(loop, job=dict(JOB, id=None))
        self.assertEqual(self.relay.downloads, [])

    def test_a_404_on_the_acknowledgement_is_final_not_retried(self):
        loop = self.make_paired()
        self.relay.ack_result = False
        self.deliver(loop)
        self.assertEqual(self.lines('no longer holds'),
                         ['the backend no longer holds job j8f3a2c1 (404); treating as final'])
        self.clock.advance(6)
        self.deliver(loop)
        self.assertEqual(len(self.relay.acks), 1)     # never sent again

    def test_a_job_that_raises_before_its_first_ack_releases_the_slot(self):
        """running_job_id is cleared in a finally, so one broken job cannot wedge the
        daemon until it is restarted."""
        loop = self.make_paired()
        calls = {'n': 0}
        healthy = self.printer.snapshot

        def flaky():
            calls['n'] += 1
            if calls['n'] > 1:                  # the sync's snapshot is the first call
                raise RuntimeError('mqtt blew up')
            return healthy()

        self.printer.snapshot = flaky
        self.deliver(loop)
        self.assertIsNone(loop.running_job_id)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False, 'mqtt blew up')])
        self.assertTrue(self.lines('Traceback'))

    def test_a_malformed_job_document_is_acknowledged_and_frees_the_slot(self):
        loop = self.make_paired()
        self.deliver(loop, job={'id': 'j8f3a2c1'})          # no filename, no path
        self.assertIsNone(loop.running_job_id)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False, "'filename'")])


class TestJobSlotAndAcknowledgement(RunLoopTestCase):
    """Who owns the job slot, and which ids are remembered."""

    def setUp(self):
        super().setUp()
        self.printer.starts_running = True

    def test_syncs_continue_while_a_job_runs(self):
        executor = StepExecutor()
        loop = self.make_paired(executor=executor)
        self.deliver(loop)
        self.assertEqual(len(executor.pending), 1)          # still running
        self.assertEqual(loop.running_job_id, 'j8f3a2c1')
        before = len(self.relay.syncs)
        for _ in range(3):
            self.clock.advance(6)
            loop.tick()
        self.assertEqual(len(self.relay.syncs), before + 3)
        self.assertEqual(self.relay.acks, [])
        executor.release()
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertIsNone(loop.running_job_id)

    def test_a_job_re_offered_while_it_is_still_running_is_not_started_twice(self):
        executor = StepExecutor()
        loop = self.make_paired(executor=executor)
        self.deliver(loop)
        self.clock.advance(6)
        self.deliver(loop)
        self.assertEqual(len(executor.pending), 1)
        self.assertEqual(self.lines('offered while'), [])   # the same job is not news

    def test_a_second_job_offered_while_one_runs_is_left_for_later_and_logged_once(self):
        executor = StepExecutor()
        loop = self.make_paired(executor=executor)
        self.deliver(loop)
        for _ in range(3):
            self.clock.advance(6)
            self.deliver(loop, job=dict(JOB, id='j00000002'))
        self.assertEqual(len(executor.pending), 1)
        self.assertEqual(loop.running_job_id, 'j8f3a2c1')
        self.assertEqual(len(self.lines('j00000002')), 1)
        executor.release()
        self.clock.advance(6)
        self.deliver(loop, job=dict(JOB, id='j00000002'))   # now it starts
        self.assertEqual(len(executor.pending), 1)
        self.assertEqual(loop.running_job_id, 'j00000002')

    def test_a_job_finishing_late_does_not_blank_its_successors_slot(self):
        loop = self.make_paired()
        loop.running_job_id = 'jbbbbbbb'          # B took the slot while A was finishing
        loop.handle_job(dict(JOB))                # A finishes late
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(loop.running_job_id, 'jbbbbbbb')

    def test_a_transient_acknowledgement_failure_is_retried_on_the_re_offer(self):
        """A dropped ack must not strand a print that actually ran: the id is remembered
        only on a definite answer, and the re-offer acknowledges it from the printer's own
        report without a second upload."""
        loop = self.make_paired()
        self.relay.ack_error = RelayError('connection reset by peer')
        self.deliver(loop)
        self.assertNotIn('j8f3a2c1', loop.acked_job_ids)
        self.assertIsNone(loop.running_job_id)
        self.clock.advance(6)
        self.deliver(loop)
        self.assertEqual(len(self.printer.uploads), 1)
        self.assertEqual(len(self.relay.acks), 2)
        self.assertIn('j8f3a2c1', loop.acked_job_ids)

    def test_the_remembered_acknowledgements_are_bounded(self):
        loop = self.make_paired()
        for n in range(rl.ACK_MEMORY + 5):
            loop._ack(f'j{n:08x}', True)
        loop._remember_acked(f'j{rl.ACK_MEMORY + 4:08x}')    # again: no double entry
        self.assertEqual(len(loop.acked_job_ids), rl.ACK_MEMORY)
        self.assertNotIn('j00000000', loop.acked_job_ids)
        self.assertIn(f'j{rl.ACK_MEMORY + 4:08x}', loop.acked_job_ids)


class TestUntrustedJobFields(RunLoopTestCase):
    """The filename and the download path come from the relay, so neither may reach the
    Pi's filesystem or a status line unexamined."""

    def test_a_filename_with_a_path_cannot_escape_the_download_directory(self):
        self.printer.starts_running = True
        loop = self.make_paired()
        self.deliver(loop, job=dict(JOB, filename='../../etc/evil.gcode.3mf'))
        dest = self.relay.downloads[0][1]
        self.assertEqual(os.path.dirname(os.path.abspath(dest)), os.path.abspath(self.tmp))
        self.assertEqual(self.printer.uploads[0][0], 'evil-j8f3a2c1.gcode.3mf')

    def test_a_download_token_never_reaches_the_acknowledgement(self):
        loop = self.make_paired()
        self.relay.download_error = RelayError(
            'GET /printer/download/9f3c2b1a-very-secret failed: timed out')
        self.deliver(loop)
        reason = self.relay.acks[0][2]
        self.assertEqual(reason, 'GET /printer/download/<token> failed: timed out')

    def test_a_long_multi_line_failure_becomes_one_short_line(self):
        loop = self.make_paired()
        self.printer.upload_error = OSError('x' * 400 + '\nand a second line')
        self.deliver(loop)
        reason = self.relay.acks[0][2]
        self.assertEqual(reason, 'x' * 200)
        self.assertTrue(self.lines('Traceback'))

    def test_an_exception_with_no_text_is_named_by_its_class(self):
        loop = self.make_paired()
        self.printer.upload_error = TimeoutError()
        self.deliver(loop)
        self.assertEqual(self.relay.acks[0][2], 'TimeoutError')


class TestJobProgressIsLogged(RunLoopTestCase):
    """A mentor running the daemon by hand watches its output, so every stage of a job,
    and its outcome, has to appear there. The download path never does."""

    def test_a_successful_job_logs_each_stage_in_order_and_the_ok(self):
        self.printer.starts_running = True
        loop = self.make_paired()
        self.deliver(loop)
        stages = [line for line in self.logged if line.startswith('job j8f3a2c1')]
        self.assertEqual(stages, [
            'job j8f3a2c1: downloading the sliced file',
            f'job j8f3a2c1: uploading to the printer as {SUFFIXED}',
            'job j8f3a2c1: starting the print',
            f'job j8f3a2c1: start accepted; waiting for the printer to report {SUFFIXED}',
            'job j8f3a2c1 acknowledged: ok',
        ])
        self.assertFalse(self.lines('/printer/download/'))

    def test_a_failed_job_logs_the_reason_it_acknowledged(self):
        loop = self.make_paired()
        self.printer.start_result = False
        self.deliver(loop)
        self.assertEqual(self.lines('acknowledged'), [
            'job j8f3a2c1 acknowledged: the printer refused the print start command'])

    def test_a_failed_acknowledgement_is_logged_as_retried(self):
        self.printer.starts_running = True
        loop = self.make_paired()
        self.relay.ack_error = RelayError('reset')
        self.deliver(loop)
        self.assertEqual(self.lines('could not acknowledge'), [
            'could not acknowledge j8f3a2c1: reset; will try again on the re-offer'])


class TestDaemonRestartsMidJob(RunLoopTestCase):
    """A daemon process that dies part-way through a job is replaced by a fresh RunLoop with
    nothing in memory. The relay keeps re-offering the handed-out job, so what the new
    process does depends only on what the printer reports."""

    def fresh_loop(self):
        """The restarted process: a new loop, the same token from the config file."""
        return self.make_paired()

    def test_died_before_the_upload_the_new_process_does_the_whole_job(self):
        self.printer.starts_running = True
        first = self.make_paired()
        self.printer.upload_error = KeyboardInterrupt      # stands in for the process dying
        with self.assertRaises(KeyboardInterrupt):
            self.deliver(first)
        self.assertEqual(self.relay.acks, [])
        self.printer.upload_error = None
        second = self.fresh_loop()
        self.clock.advance(6)
        self.deliver(second)
        self.assertEqual(self.printer.uploads, [(SUFFIXED, b'3mf-bytes')])
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_died_after_the_start_the_new_process_does_not_print_twice(self):
        """The printer reports our file, so the new process acknowledges from that report."""
        self.printer.set(running(SUFFIXED))
        loop = self.fresh_loop()
        self.deliver(loop)
        self.assertEqual(self.printer.uploads, [])
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.lines('already has'),
                         [f'the printer already has {SUFFIXED}; not uploading it again'])

    def test_died_after_the_print_finished_the_job_is_acknowledged_ok(self):
        self.printer.set(dict(IDLE, state=pr.FINISHED, file=SUFFIXED, percent=100))
        loop = self.fresh_loop()
        self.deliver(loop)
        self.assertEqual(self.printer.uploads, [])
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_a_paused_print_of_the_job_counts_as_started(self):
        self.printer.set(dict(IDLE, state=pr.PAUSED, file=SUFFIXED))
        loop = self.fresh_loop()
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_the_printer_errored_on_the_job_is_acknowledged_with_the_code_not_as_a_success(self):
        self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED,
                              error='HMS_0300_0100_0001_0004'))
        loop = self.fresh_loop()
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False,
                                            'printer error: HMS_0300_0100_0001_0004')])
        self.assertEqual(self.printer.uploads, [])
        self.assertEqual(self.lines('already has'), [])

    def test_the_previous_print_is_not_mistaken_for_this_job(self):
        """The printer still shows the LAST job's file; the job id in the name tells them
        apart, so the new job is uploaded."""
        self.printer.starts_running = True
        self.printer.set(dict(IDLE, state=pr.FINISHED, file='sample_part-j00000001.gcode.3mf'))
        loop = self.fresh_loop()
        self.deliver(loop)
        self.assertEqual(len(self.printer.uploads), 1)

    def test_a_job_finished_by_the_old_process_but_not_acknowledged_is_acknowledged_once(self):
        """The ack was lost with the old process; the new one has no memory of the job and
        acknowledges it from the printer's report, without a second upload."""
        self.printer.starts_running = True
        first = self.make_paired()
        self.relay.ack_error = RelayError('process killed mid-request')
        self.deliver(first)
        second = self.fresh_loop()
        self.clock.advance(6)
        self.deliver(second)
        self.assertEqual(len(self.printer.uploads), 1)
        self.assertEqual(self.relay.acks[-1], ('j8f3a2c1', True, None))


class KnownFaultsWithTheRealPrinterReport(RunLoopTestCase):
    """The run loop against the real PrinterLink, its library replaced by FakeBambuPrinter
    reporting what the H2S actually reported on 2026-10-09 (fixtures/h2s_status.json,
    `running_as_reported_by_h2s`)."""

    def setUp(self):
        super().setUp()
        self.bambu = None

        def factory(ip, access_code, serial):
            self.bambu = FakeBambuPrinter(ip, access_code, serial)
            return self.bambu

        self.printer = pr.PrinterLink('10.0.0.42', '01P00A', '12345678',
                                      printer_factory=factory)
        self.printer.connect()
        self.bambu.report = dict(H2S['idle'])

    @staticmethod
    def as_the_h2s_reports(remote_name):
        report = dict(H2S['running_as_reported_by_h2s'])
        report['subtask_name'] = remote_name[:-len('.gcode.3mf')]
        return report

    @pytest.mark.known_fault
    def test_known_fault_the_start_check_never_matches_the_h2s_report(self):
        """KNOWN FAULT, to be fixed in hardening. The start check compares the uploaded name
        with `file`, which map_status fills from `gcode_file` (the G-code path inside the
        archive) before `subtask_name` (our name without .gcode.3mf). So a print that
        started is acknowledged as failed after sixty seconds. Hardening flips this to
        expect ('j8f3a2c1', True, None) with no waiting."""
        self.bambu.report_after_start = self.as_the_h2s_reports
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.bambu.started['filename'], SUFFIXED)
        self.assertEqual(self.printer.snapshot()['state'], pr.RUNNING)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False,
                                            'the printer did not start the file within 60s')])

    @pytest.mark.known_fault
    def test_known_fault_a_restarted_daemon_uploads_a_running_job_again(self):
        """KNOWN FAULT, to be fixed in hardening. Same cause: the restarted daemon cannot
        recognise its own job in the H2S report, so it uploads and starts the part a second
        time while the first copy prints. Hardening flips this to expect no upload."""
        self.bambu.report = self.as_the_h2s_reports(SUFFIXED)
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.bambu.uploaded, (SUFFIXED, b'3mf-bytes'))
        self.assertEqual(self.bambu.started['filename'], SUFFIXED)

    @pytest.mark.known_fault
    def test_known_fault_a_failed_upload_goes_on_to_start_a_missing_file(self):
        """KNOWN FAULT, to be fixed in hardening. bambulabs_api catches a failure during the
        transfer itself, logs it and returns None (a refused connection or login raises,
        and that is reported); PrinterLink.upload returns the None and the run loop never
        looks at it. So the daemon starts a file the printer does not have, and the caller
        learns only of a start timeout a minute later. Hardening flips this to expect no
        start and an upload failure in the acknowledgement."""
        self.bambu.upload_returns_none = True
        loop = self.make_paired()
        self.deliver(loop)
        self.assertIsNone(self.bambu.uploaded)                 # nothing reached the printer
        self.assertEqual(self.bambu.started['filename'], SUFFIXED)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False,
                                            'the printer did not start the file within 60s')])


class TestPreflightAndRunForever(RunLoopTestCase):
    def test_a_plain_http_backend_url_is_refused(self):
        self.config.backend_url = 'http://example.test'
        with self.assertRaises(ValueError):
            self.make().preflight()

    def test_a_dev_backend_url_is_warned_about_by_name(self):
        self.config.backend_url = 'http://10.0.0.5:6238'
        self.config.dev = True
        self.make().preflight()
        self.assertEqual(self.lines('WARNING'), [
            'WARNING: development mode, talking to http://10.0.0.5:6238 over an unverified '
            'connection'])

    def test_an_https_backend_url_warns_about_nothing(self):
        self.make().preflight()
        self.assertEqual(self.lines('WARNING'), [])

    def test_run_forever_keeps_going_after_an_unexpected_error(self):
        loop = self.make()

        def sleep(seconds):
            self.clock.sleep(seconds)
            if len(self.clock.slept) >= 3:
                raise KeyboardInterrupt      # the only way out of a forever loop

        def boom():
            raise RuntimeError('kaboom')

        loop.sleep = sleep
        loop.tick = boom
        with self.assertRaises(KeyboardInterrupt):
            loop.run_forever()
        self.assertEqual(self.clock.slept, [rl.TICK_SECONDS] * 3)
        self.assertEqual(len(self.lines("unexpected: RuntimeError('kaboom')")), 3)
        self.assertTrue(self.lines('Traceback'))

    def test_run_forever_refuses_a_bad_backend_before_any_tick(self):
        self.config.backend_url = 'ftp://example.test'
        loop = self.make()
        with self.assertRaises(ValueError):
            loop.run_forever()
        self.assertEqual(self.relay.exchanges, [])

    def test_the_default_executor_is_one_worker_thread_and_downloads_go_to_tmp(self):
        loop = rl.RunLoop(self.config, self.relay, self.printer)
        try:
            self.assertEqual(loop.executor._max_workers, 1)
            self.assertEqual(loop.download_dir, tempfile.gettempdir())
        finally:
            loop.executor.shutdown(wait=True)
