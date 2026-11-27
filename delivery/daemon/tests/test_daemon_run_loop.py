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
                      download_dir=self.tmp, rand=lambda: 0.0, instance='daemon-test',
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
        self.assertEqual(self.lines('paired with the relay'), ['paired with the relay'])

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

    def test_a_printer_that_never_reports_running_settles_after_five_minutes(self):
        """Review 4, defect 4: the final "did not start" needs START_SETTLE_SECONDS of whole,
        fresh pictures without the print after the command, not sixty seconds."""
        loop = self.make_paired()
        self.printer.starts_running = False                 # stays idle after the start
        started_at = self.clock.now
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False,
                                            'the printer did not start the file within 300s')])
        self.assertEqual(self.clock.now - started_at, rl.START_SETTLE_SECONDS)
        self.assertEqual(self.clock.slept,
                         [rl.START_POLL_SECONDS] * int(rl.START_SETTLE_SECONDS
                                                       / rl.START_POLL_SECONDS))
        self.assertIsNone(loop.hold)                        # settled: the printer is free

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
        self.printer.starts_running = False

        def sleep(seconds):
            self.clock.sleep(seconds)
            self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED))

        loop.sleep = sleep
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
                         ['the relay no longer holds job j8f3a2c1; treating it as finished'])
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
    daemon's filesystem or a status line unexamined."""

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
        # An expected failure is a plain line, not a traceback that looks like a crash.
        self.assertFalse(self.lines('Traceback'))

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
            'job j8f3a2c1: uploaded; the printer has all 9 bytes',
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
            'could not acknowledge j8f3a2c1: reset; will try again in 5s'])


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
        """The relay says the gate was passed ten minutes ago: an end naming our file that
        long after the start is this print's end, found at once, not waited on for ever."""
        self.printer.set(dict(IDLE, state=pr.FINISHED, file=SUFFIXED, percent=100))
        loop = self.fresh_loop()
        self.deliver(loop, dict(JOB, start_granted=True, start_granted_age_s=600))
        self.assertEqual(self.printer.uploads, [])
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.clock.slept, [])

    def test_a_restart_just_after_the_start_does_not_take_a_left_over_end_for_ours(self):
        """Review 4, defect 2, for a restarted daemon: the gate passed 5 s ago and the
        printer names our file under the previous print's FINISH. Not our end yet: the
        print shows going a little later and the job is acknowledged as started, never as
        finished in its first seconds."""
        self.printer.set(dict(IDLE, state=pr.FINISHED, file=SUFFIXED, percent=100))
        loop = self.fresh_loop()
        polls = {'n': 0}

        def sleep(seconds):
            self.clock.sleep(seconds)
            polls['n'] += 1
            if polls['n'] == 5:
                self.printer.set(running(SUFFIXED))

        loop.sleep = sleep
        self.deliver(loop, dict(JOB, start_granted=True, start_granted_age_s=5))
        self.assertEqual(polls['n'], 5)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.printer.starts, [])

    def test_a_restarted_daemon_finds_a_real_end_once_the_start_is_old_enough(self):
        """The same left-over-looking FINISH that stays: a restarted daemon cannot tell it
        from a real end, so once the gate is START_SETTLE_SECONDS old it counts as this
        print's end, and the job ends done, bounded, never waited on for ever."""
        self.printer.set(dict(IDLE, state=pr.FINISHED, file=SUFFIXED, percent=100))
        loop = self.fresh_loop()
        started = self.clock.now
        self.deliver(loop, dict(JOB, start_granted=True, start_granted_age_s=5))
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertGreaterEqual(self.clock.now - started, rl.START_SETTLE_SECONDS - 5)
        self.assertLess(self.clock.now - started,
                        rl.START_SETTLE_SECONDS - 5 + 2 * rl.START_POLL_SECONDS)

    def test_a_paused_print_of_the_job_counts_as_started(self):
        self.printer.set(dict(IDLE, state=pr.PAUSED, file=SUFFIXED))
        loop = self.fresh_loop()
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_the_printer_errored_on_the_job_is_acknowledged_with_the_code_not_as_a_success(self):
        self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED,
                              error='HMS_0300_0100_0001_0004'))
        loop = self.fresh_loop()
        self.deliver(loop, dict(JOB, start_granted=True, start_granted_age_s=600))
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

    def test_the_start_check_matches_the_h2s_report(self):
        """Known fault 1, fixed: the uploaded name without .gcode.3mf is matched against
        the H2S's `subtask_name`, so the print that started is acknowledged at once."""
        self.bambu.report_after_start = self.as_the_h2s_reports
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.bambu.started['filename'], SUFFIXED)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.clock.slept, [])                 # no waiting at all

    def test_a_restarted_daemon_recognises_its_running_job_and_uploads_nothing(self):
        """Known fault 1, fixed: a restarted daemon never prints the part twice."""
        self.bambu.report = self.as_the_h2s_reports(SUFFIXED)
        loop = self.make_paired()
        self.deliver(loop)
        self.assertIsNone(self.bambu.uploaded)
        self.assertIsNone(self.bambu.started)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_a_failed_upload_is_never_started_and_says_upload_failed(self):
        """Known fault 2, fixed: the library's swallowed failure is caught by the printer's
        own listing, the upload is tried again, and the job fails as an upload failure
        without a start."""
        self.bambu.upload_returns_none = True
        loop = self.make_paired()
        self.deliver(loop)
        self.assertIsNone(self.bambu.uploaded)
        self.assertIsNone(self.bambu.started)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', False,
                                            'the printer did not confirm that the file arrived')])
        self.assertEqual(self.relay.ack_codes, ['delivery.upload_failed'])

    def test_the_426_after_a_whole_file_goes_on_to_start_and_logs_no_error(self):
        """The hardware test's case: the reply was 426, the file arrived whole."""
        self.bambu.arrives_but_426 = True
        self.bambu.report_after_start = self.as_the_h2s_reports
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertFalse([line for line in self.logged
                          if 'Failed to execute' in line or 'error' in line.lower()])


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


class TestSilenceNeverEndsTheStart(RunLoopTestCase):
    """Defect 1, route A: the start wait counts only the printer's fresh reports. A
    printer that is unreachable or quiet after an accepted start may be printing."""

    class Requesting(FakePrinter):
        def __init__(self):
            super().__init__()
            self.requests = []

        def request_report(self):
            self.requests.append(True)

    def run_start(self, script):
        """Deliver a job whose start is accepted; `script(seconds_since_start)` sets what
        the printer reports at each poll of the start wait."""
        loop = self.make_paired()
        self.printer.starts_running = False
        begun = {}

        def sleep(seconds):
            self.clock.sleep(seconds)
            if self.printer.starts:
                begun.setdefault('at', self.clock.now - seconds)
                script(self.clock.now - begun['at'])

        loop.sleep = sleep
        self.deliver(loop)
        return loop

    def test_an_unreachable_spell_of_ninety_seconds_then_our_file_is_a_success(self):
        def script(t):
            if t < 90:
                self.printer.set(dict(IDLE, state=pr.UNREACHABLE))
            else:
                self.printer.set(running(SUFFIXED))

        self.run_start(script)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.printer.starts, [SUFFIXED])

    def test_an_unreachable_printer_is_waited_for_with_no_end_and_never_judged(self):
        """An hour of a printer that cannot be reached: still waiting, nothing acked."""
        class Done(BaseException):          # not caught by the job's own backstop
            pass

        def script(t):
            self.printer.set(dict(IDLE, state=pr.UNREACHABLE))
            if t >= 3600:
                raise Done()

        with self.assertRaises(Done):
            self.run_start(script)
        self.assertEqual(self.relay.acks, [])
        self.assertTrue(self.lines('it is not answering just now, so the wait is not counted'))

    def test_a_silent_stream_is_not_counted_and_the_printer_is_asked_for_a_report(self):
        self.printer = self.Requesting()

        def script(t):
            if t < 600:
                self.printer.set(dict(IDLE, report_age_s=int(t) + 30))
            else:
                self.printer.set(dict(running(SUFFIXED), report_age_s=0))

        self.run_start(script)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        # Asked once just before the start gate, then every REPORT_REQUEST_SECONDS while
        # quiet, not every poll.
        self.assertEqual(len(self.printer.requests),
                         1 + int(600 / rl.REPORT_REQUEST_SECONDS))

    def test_only_fresh_reports_count_towards_the_start_timeout(self):
        def script(t):
            reachable = int(t) % 40 < 20                  # 20 s answering, 20 s not
            self.printer.set(dict(IDLE) if reachable else dict(IDLE, state=pr.UNREACHABLE))

        started = self.clock.now
        self.run_start(script)
        self.assertEqual(self.relay.ack_codes, ['delivery.start_timeout'])
        self.assertGreaterEqual(self.clock.now - started, 2 * rl.START_SETTLE_SECONDS - 20)
        self.assertEqual(self.relay.ack_fields, [{'seconds': 300}])


class TestFailureFigures(RunLoopTestCase):
    """Defect 3: every daemon failure whose sentence has a figure sends it in `fields`."""

    def test_the_start_timeout_names_its_seconds(self):
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.relay.ack_fields, [{'seconds': 300}])

    def test_an_unreachable_printer_at_the_start_names_its_minutes(self):
        loop = self.make_paired()
        self.printer.set(dict(IDLE, state=pr.UNREACHABLE))
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_unreachable_at_start'])
        self.assertEqual(self.relay.ack_fields, [{'minutes': 10}])

    def test_a_busy_printer_names_its_print_and_percent(self):
        loop = self.make_paired()
        self.printer.set(running('other_part-j0000abc.gcode.3mf'))
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_busy_at_start'])
        self.assertEqual(self.relay.ack_fields,
                         [{'name': 'other_part.gcode.3mf', 'percent': 3}])

    def test_a_printer_error_at_the_start_names_its_code(self):
        """Our file named by a printer whose print ended badly at once."""
        loop = self.make_paired()
        self.printer.starts_running = False

        def sleep(seconds):
            self.clock.sleep(seconds)
            if self.printer.starts:
                self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED,
                                      error='PRINT_ERROR_07008011'))

        loop.sleep = sleep
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_error_at_start'])
        self.assertEqual(self.relay.ack_fields, [{'error': 'PRINT_ERROR_07008011'}])

    def test_a_printer_left_in_its_failed_state_takes_the_next_print(self):
        """Round 3, defect 4: the error left over from the last print does not refuse."""
        loop = self.make_paired()
        self.printer.starts_running = True
        self.printer.set(dict(IDLE, state=pr.ERROR, error='PRINT_ERROR_0300400C'))
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.printer.starts, [SUFFIXED])

    def test_another_file_started_is_named(self):
        loop = self.make_paired()
        self.printer.starts_running = False

        def sleep(seconds):
            self.clock.sleep(seconds)
            if self.printer.starts:
                self.printer.set(running('someone_elses_part.gcode.3mf'))

        loop.sleep = sleep
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.start_other_file'])
        self.assertEqual(self.relay.ack_fields, [{'name': 'someone_elses_part.gcode.3mf'}])

    def test_a_huge_detail_is_cut_before_it_is_sent_or_queued(self):
        loop = self.make_paired()
        self.relay.ack_error = RelayError('down')
        loop._ack('j8f3a2c1', False, 'x', code='delivery.upload_failed', detail='y' * 5_000_000)
        self.assertLessEqual(len(self.relay.ack_details[0]), rl.MAX_DETAIL_CHARS)
        self.assertLessEqual(len(loop.pending_acks['j8f3a2c1']['detail']),
                             rl.MAX_DETAIL_CHARS)


class TestStoppingWithAJobInFlight(RunLoopTestCase):
    """Defect 7: stop() ends the job thread's waits at once, on a real thread, and the
    file is never started afterwards."""

    def test_stop_ends_a_job_waiting_for_the_printer_promptly_and_never_starts_it(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        waiting = threading.Event()

        class Unreachable(FakePrinter):
            def snapshot(self):
                waiting.set()
                return dict(IDLE, state=pr.UNREACHABLE)

        self.printer = Unreachable()
        executor = ThreadPoolExecutor(max_workers=1)
        loop = self.make_paired(executor=executor, sleep=None, clock=__import__('time').monotonic)
        self.deliver(loop)
        self.assertTrue(waiting.wait(10))              # the job thread is in its wait
        loop.stop()
        finished = threading.Event()
        threading.Thread(target=lambda: (executor.shutdown(wait=True), finished.set()),
                         daemon=True).start()
        self.assertTrue(finished.wait(10), 'the job thread did not stop')
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.printer.uploads, [])
        self.assertEqual(self.relay.acks, [])          # left for the next run
        self.assertIsNone(loop.running_job_id)
        self.assertTrue(self.lines('the daemon is stopping'))

    def test_stop_ends_the_start_wait_promptly_with_the_printer_unreachable(self):
        """Round 3, defect 6: Ctrl-C while the daemon waits for the printer to report the
        file it started, the printer unreachable since the command: on a real thread, the
        job thread ends at once and nothing is sent twice."""
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor
        in_start_wait = threading.Event()

        class GoneAfterTheStart(FakePrinter):
            def snapshot(self):
                if self.starts:
                    in_start_wait.set()
                    return dict(IDLE, state=pr.UNREACHABLE)
                return super().snapshot()

        self.printer = GoneAfterTheStart()
        executor = ThreadPoolExecutor(max_workers=1)
        loop = self.make_paired(executor=executor, sleep=None, clock=time.monotonic)
        self.deliver(loop)
        self.assertTrue(in_start_wait.wait(10), 'the job never reached the start wait')
        loop.stop()
        finished = threading.Event()
        threading.Thread(target=lambda: (executor.shutdown(wait=True), finished.set()),
                         daemon=True).start()
        self.assertTrue(finished.wait(5), 'the start wait did not end on stop()')
        self.assertEqual(self.printer.starts, [SUFFIXED])
        self.assertEqual(self.relay.acks, [])          # left for the next run
        self.assertIsNone(loop.running_job_id)
        self.assertTrue(self.lines('the daemon is stopping'))

    def test_a_stop_before_the_start_command_means_it_is_never_sent(self):
        loop = self.make_paired()
        original = self.relay.start_gate

        def gate(job_id, instance):
            loop.stop()                                # Ctrl-C arrives at the gate
            return original(job_id, instance)

        self.relay.start_gate = gate
        self.deliver(loop)
        self.assertEqual(self.printer.starts, [])
        self.assertEqual(self.relay.acks, [])

    def test_a_stop_during_the_upload_removes_the_partial_file(self):
        loop = self.make_paired()

        class Stopping(FakePrinter):
            def upload(self, local_path, remote_name, *, progress=None, cancelled=None):
                loop.stop()
                return super().upload(local_path, remote_name, progress=progress,
                                      cancelled=cancelled)

        self.printer = Stopping()
        loop.printer = self.printer
        self.deliver(loop)
        self.assertEqual(self.printer.deleted, [SUFFIXED])
        self.assertEqual(self.printer.starts, [])

    def test_run_forever_returns_once_stopped(self):
        loop = self.make_paired()

        def sleep(seconds):
            self.clock.sleep(seconds)
            loop.stop()

        loop.sleep = sleep
        loop.run_forever()
        self.assertEqual(self.clock.slept, [rl.TICK_SECONDS])


class TestHowAStartIsDecided(RunLoopTestCase):
    """Review 4, the four rulings on the moment a print starts ("How a start is decided"
    in README-details.md), one test per case, on the fake clock."""

    def setUp(self):
        super().setUp()
        self.printer.starts_running = False

    def at_sleep(self, loop, schedule):
        """Run `schedule[n]` after the n-th sleep of the job thread (1-based)."""
        count = {'n': 0}

        def sleep(seconds):
            self.clock.sleep(seconds)
            count['n'] += 1
            action = schedule.get(count['n'])
            if action is not None:
                action()

        loop.sleep = sleep
        return count

    # -- ruling 1: only a whole picture that positively says no print is free ----------

    def test_a_picture_with_no_main_state_is_never_free_and_starts_nothing(self):
        self.printer.set(dict(IDLE, state=pr.UNRECOGNISED_STATE, whole=False,
                              unrecognised=pr.NO_MAIN_STATE, percent=43,
                              file='someone_elses_print'))
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_unreachable_at_start'])
        self.assertEqual(self.printer.starts, [])
        self.assertTrue(self.lines('waiting for a fresh report'))

    def test_a_picture_not_whole_waits_and_a_whole_one_decides(self):
        self.printer.starts_running = True
        self.printer.set(dict(IDLE, whole=False))
        loop = self.make_paired()
        self.at_sleep(loop, {3: lambda: self.printer.set(dict(IDLE))})
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.printer.starts, [SUFFIXED])

    def test_the_last_document_of_a_whole_picture_is_what_counts(self):
        self.assertFalse(rl.RunLoop._fresh(dict(IDLE, whole=False, report_age_s=0)))
        self.assertTrue(rl.RunLoop._fresh(dict(IDLE, whole=True, report_age_s=0)))
        self.assertTrue(rl.RunLoop._fresh(dict(IDLE, report_age_s=0)))     # a stand-in

    # -- ruling 2: an end counts only if it is the end of this print -------------------

    def test_a_left_over_finish_naming_our_file_is_not_our_end(self):
        """The previous print's FINISH, with our name put on it in the first seconds."""
        self.printer.set(dict(IDLE, state=pr.FINISHED, file='other_part-j00000001'))
        loop = self.make_paired()
        original_start = self.printer.start

        def start(name):
            accepted = original_start(name)
            self.printer.set(dict(IDLE, state=pr.FINISHED, file=SUFFIXED, percent=100))
            return accepted

        self.printer.start = start
        self.at_sleep(loop, {5: lambda: self.printer.set(running(SUFFIXED))})
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.clock.slept, [rl.START_POLL_SECONDS] * 5)

    def test_a_left_over_failed_naming_our_file_is_not_a_failure(self):
        self.printer.set(dict(IDLE, state=pr.ERROR, file='other_part-j00000001',
                              error='PRINT_ERROR_0300400C'))
        loop = self.make_paired()
        original_start = self.printer.start

        def start(name):
            accepted = original_start(name)
            self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED,
                                  error='PRINT_ERROR_0300400C'))
            return accepted

        self.printer.start = start
        self.at_sleep(loop, {5: lambda: self.printer.set(running(SUFFIXED))})
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_a_left_over_end_that_never_changes_settles_as_not_started(self):
        """The same state from before the command, never seen going: after
        START_SETTLE_SECONDS the printer is taken not to have started the file."""
        self.printer.set(dict(IDLE, state=pr.FINISHED, file='other_part-j00000001'))
        loop = self.make_paired()
        original_start = self.printer.start

        def start(name):
            accepted = original_start(name)
            self.printer.set(dict(IDLE, state=pr.FINISHED, file=SUFFIXED))
            return accepted

        self.printer.start = start
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.start_timeout'])
        self.assertEqual(self.relay.ack_fields, [{'seconds': int(rl.START_SETTLE_SECONDS)}])

    def test_an_end_that_follows_a_change_after_the_command_is_ours(self):
        """IDLE before the command, then FAILED with our name: the state changed after the
        start, so once the command is LEFTOVER_END_SECONDS old it is this print's end."""
        loop = self.make_paired()
        original_start = self.printer.start

        def start(name):
            accepted = original_start(name)
            self.printer.set(dict(IDLE, state=pr.ERROR, file=SUFFIXED,
                                  error='PRINT_ERROR_07008011'))
            return accepted

        self.printer.start = start
        started = self.clock.now
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_error_at_start'])
        self.assertGreaterEqual(self.clock.now - started, rl.LEFTOVER_END_SECONDS)

    def test_a_restarted_daemon_takes_an_end_naming_the_file_after_the_settle_time(self):
        """The relay says the gate passed long ago: the end is found at once."""
        self.printer.set(dict(IDLE, state=pr.FINISHED, file=SUFFIXED, percent=100))
        loop = self.make_paired()
        self.deliver(loop, dict(JOB, start_granted=True,
                                start_granted_age_s=int(rl.START_SETTLE_SECONDS) + 60))
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.clock.slept, [])

    # -- ruling 3: every wait before the gate, no untrue sentence ----------------------

    def test_past_the_gate_there_is_one_look_and_no_wait(self):
        original_gate = self.relay.start_gate

        def gate(job_id, instance):
            self.printer.set(dict(IDLE, report_age_s=int(rl.FRESH_REPORT_SECONDS) + 5))
            return original_gate(job_id, instance)

        self.relay.start_gate = gate
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_unreachable_at_start'])
        self.assertEqual((self.printer.starts, self.printer.deleted), ([], [SUFFIXED]))
        self.assertEqual(self.clock.slept, [])
        self.assertIn('not started', self.relay.ack_details[0])

    def test_a_quiet_printer_after_the_upload_is_waited_for_before_the_gate(self):
        original_upload = self.printer.upload

        def upload(*args, **kwargs):
            note = original_upload(*args, **kwargs)
            self.printer.set(dict(IDLE, report_age_s=int(rl.FRESH_REPORT_SECONDS) + 5))
            return note

        self.printer.upload = upload
        self.printer.starts_running = True
        loop = self.make_paired()
        stages = []
        self.at_sleep(loop, {
            1: lambda: stages.append(loop.job_progress['stage']),
            2: lambda: (self.assertEqual(self.relay.gates, []),
                        self.printer.set(dict(IDLE)))})
        self.deliver(loop)
        self.assertEqual(stages, ['waiting_for_printer'])
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(len(self.relay.gates), 1)

    def test_our_file_seen_going_before_the_gate_is_acknowledged_never_started(self):
        """Another process with this pairing started it (the gate keeps that to one): the
        pre-gate wait sees our file going and acknowledges it, with no start command."""
        original_upload = self.printer.upload

        def upload(*args, **kwargs):
            note = original_upload(*args, **kwargs)
            self.printer.set(running(SUFFIXED))
            return note

        self.printer.upload = upload
        loop = self.make_paired()
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual((self.printer.starts, self.relay.gates), ([], []))

    def test_the_look_after_the_gate_refuses_a_start_while_an_earlier_one_holds(self):
        """The one look past the gate checks the hold too (it cannot have appeared since
        the wait before the gate in one job thread, but the look does not rely on that)."""
        loop = self.make_paired()
        loop.hold = rl.StartHold('j00000001', 'other-j00000001.gcode.3mf', self.clock.now,
                                 sent_here=True, before_state=pr.IDLE)
        with self.assertRaises(rl._JobEnded):
            loop._start('j8f3a2c1', SUFFIXED)
        self.assertEqual(self.relay.ack_codes, ['delivery.earlier_start_unsettled'])
        self.assertEqual((self.printer.starts, self.printer.deleted), ([], [SUFFIXED]))

    def test_a_rebuilt_hold_with_no_usable_age_counts_from_now(self):
        loop = self.make_paired()
        for age in (None, 'x', True, -5):
            hold = loop._rebuilt_hold('j8f3a2c1', SUFFIXED, age)
            self.assertEqual((hold.sent_at, hold.required, hold.sent_here),
                             (self.clock.now, rl.START_SETTLE_SECONDS, False))

    def test_the_wait_for_a_start_keeps_a_hold_another_job_left(self):
        """A job waiting for its own start never takes the place of a hold an earlier job
        left: settling its own start leaves the other hold in place."""
        loop = self.make_paired()
        other = rl.StartHold('j00000001', 'other-j00000001.gcode.3mf', self.clock.now,
                             sent_here=False, now=self.clock.now)
        loop.hold = other
        self.printer.set(running(SUFFIXED))
        with self.assertRaises(rl._JobEnded):
            loop._await_start('j8f3a2c1', SUFFIXED)
        self.assertIs(loop.hold, other)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_a_hold_counts_only_the_time_between_looks_close_together(self):
        """Time since the last look counts while the looks come within
        FRESH_REPORT_SECONDS of one another; a longer gap is time nobody watched (between
        two delivery jobs), so it is not counted, whatever the next picture says."""
        hold = rl.StartHold('j00000001', 'other-j00000001.gcode.3mf', 0.0, sent_here=True,
                            before_state=pr.IDLE)
        idle = dict(IDLE)
        hold.watch(idle, 0.0, True)
        hold.watch(idle, rl.FRESH_REPORT_SECONDS, True)
        self.assertEqual(hold.counted, rl.FRESH_REPORT_SECONDS)
        hold.watch(idle, rl.FRESH_REPORT_SECONDS + 200.0, True)
        self.assertEqual(hold.counted, rl.FRESH_REPORT_SECONDS)
        self.assertIsNone(hold.outcome)
        hold.watch(idle, rl.FRESH_REPORT_SECONDS + 205.0, True)
        self.assertEqual(hold.counted, rl.FRESH_REPORT_SECONDS + 5.0)
        # The start wait's own ask of the relay (20 s here) is watched time ...
        hold.watch(idle, rl.FRESH_REPORT_SECONDS + 227.0, True, asked_s=20.0)
        self.assertEqual(hold.counted, rl.FRESH_REPORT_SECONDS + 27.0)
        # ... but it excuses no more than itself.
        hold.watch(idle, 2 * rl.FRESH_REPORT_SECONDS + 249.0, True, asked_s=20.0)
        self.assertEqual(hold.counted, rl.FRESH_REPORT_SECONDS + 27.0)

    def test_a_slow_hold_check_does_not_stop_the_holds_count(self):
        """Delivery review 1, defect 3: every HOLD_CHECK_SECONDS the start wait asks the
        relay whether it still holds the job, and that ask may take the client's whole
        timeout (20 s, over FRESH_REPORT_SECONDS). The daemon's own wait was watching all
        through it, so the time counts: a start the printer ignored on a fresh, idle
        printer ends delivery.start_timeout after START_SETTLE_SECONDS of the hold's count,
        not after about 17 minutes. Time nobody watched is still not counted
        (test_a_hold_counts_only_the_time_between_looks_close_together)."""
        original_gate = self.relay.start_gate
        asks = {'n': 0}

        def gate(job_id, instance):
            asks['n'] += 1
            if asks['n'] > 1:                     # the hold checks, after the gate itself
                self.clock.advance(20.0)
                raise RelayError('timed out')
            return original_gate(job_id, instance)

        self.relay.start_gate = gate
        loop = self.make_paired()
        started = []
        original_start = self.printer.start

        def start(name):
            started.append(self.clock.now)
            return original_start(name)

        self.printer.start = start
        self.deliver(loop)
        self.assertEqual(self.relay.ack_codes, ['delivery.start_timeout'])
        self.assertGreater(asks['n'], 2)
        self.assertLessEqual(self.clock.now - started[0],
                             rl.START_SETTLE_SECONDS + rl.HOLD_CHECK_SECONDS)

    def test_the_wait_is_made_again_before_a_second_ask_of_the_gate(self):
        """The gate does not answer; while the daemon waits to ask again the printer goes
        quiet; the next ask waits for a fresh report first, still cancellable."""
        self.relay.gate_outcomes = [RelayError('reset'), 'start']
        self.printer.starts_running = True
        loop = self.make_paired()
        self.at_sleep(loop, {1: lambda: self.printer.set(dict(IDLE, report_age_s=60)),
                             8: lambda: self.printer.set(dict(IDLE))})
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertTrue(self.lines('waiting for a fresh report'))

    def test_the_daemon_says_when_the_start_command_went(self):
        loop = self.make_paired()
        sent = []
        original_start = self.printer.start

        def start(name):
            sent.append(dict(loop.job_progress))
            accepted = original_start(name)
            sent.append(dict(loop.job_progress))
            return accepted

        self.printer.start = start
        self.at_sleep(loop, {1: lambda: self.printer.set(running(SUFFIXED))})
        self.deliver(loop)
        self.assertNotIn('start_sent', sent[0])
        self.assertEqual(loop.relay.acks, [('j8f3a2c1', True, None)])

    # -- ruling 4: after a start command the printer is held ---------------------------

    def test_a_slow_printer_gets_a_non_final_stage_then_success(self):
        loop = self.make_paired()
        stages = []
        show_at = int(90 / rl.START_POLL_SECONDS)
        schedule = {n: (lambda: stages.append(dict(loop.job_progress)))
                    for n in range(1, show_at)}
        schedule[show_at] = lambda: self.printer.set(running(SUFFIXED))
        self.at_sleep(loop, schedule)
        self.deliver(loop)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        names = [s['stage'] for s in stages]
        self.assertEqual(names[0], 'starting')
        self.assertIn('start_not_shown', names)
        late = [s for s in stages if s['stage'] == 'start_not_shown']
        self.assertGreaterEqual(late[0]['waited_s'], rl.START_SLOW_SECONDS)
        self.assertTrue(all(s.get('start_sent') for s in stages))

    def test_a_second_job_waits_while_the_first_start_holds_the_printer(self):
        """The first job leaves its wait (the relay no longer holds it) with its start
        unsettled. The second job is not started while the printer is fresh and idle
        until START_SETTLE_SECONDS of that settle the first."""
        self.relay.gate_outcomes = ['start', 'unknown']
        loop = self.make_paired()
        self.deliver(loop)
        self.assertIsNotNone(loop.hold)
        self.assertEqual(loop.hold.job_id, 'j8f3a2c1')
        self.assertEqual(self.printer.starts, [SUFFIXED])
        before = self.clock.now
        self.relay.gate_outcomes = []
        self.printer.starts_running = True
        self.deliver(loop, dict(JOB, id='j0000abcd'))
        self.assertEqual(self.relay.acks[-1], ('j0000abcd', True, None))
        self.assertGreaterEqual(self.clock.now - before,
                                rl.START_SETTLE_SECONDS - rl.HOLD_CHECK_SECONDS)
        self.assertEqual(len(self.printer.starts), 2)
        self.assertTrue(self.lines('the earlier start of'))

    def test_a_second_job_is_refused_when_the_held_print_shows(self):
        self.relay.gate_outcomes = ['start', 'unknown']
        loop = self.make_paired()
        self.deliver(loop)
        self.relay.gate_outcomes = []
        self.at_sleep(loop, {3: lambda: self.printer.set(running(SUFFIXED))})
        self.deliver(loop, dict(JOB, id='j0000abcd'))
        self.assertEqual(self.relay.ack_codes[-1], 'delivery.printer_busy_at_start')
        self.assertEqual(self.printer.starts, [SUFFIXED])
        self.assertIsNone(loop.hold)

    def test_a_hold_unsettled_at_the_ten_minute_wait_ends_the_second_job_unstarted(self):
        self.relay.gate_outcomes = ['start', 'unknown']
        loop = self.make_paired()
        self.deliver(loop)
        self.relay.gate_outcomes = []
        self.printer.set(dict(IDLE, report_age_s=60))            # quiet, nothing counted
        near_end = int(rl.PRINTER_WAIT_SECONDS - 3)          # the wait sleeps a second a time
        self.at_sleep(loop, {near_end: lambda: self.printer.set(dict(IDLE))})
        self.deliver(loop, dict(JOB, id='j0000abcd'))
        self.assertEqual(self.relay.ack_codes[-1], 'delivery.earlier_start_unsettled')
        self.assertEqual(self.relay.ack_fields[-1], {'minutes': 10})
        self.assertEqual(self.printer.starts, [SUFFIXED])

    def test_a_restarted_daemon_rebuilds_the_hold_from_the_relays_previous_start(self):
        loop = self.make_paired()
        previous = {'id': 'j00000001', 'filename': 'other_part.gcode.3mf', 'age_s': 10}
        self.at_sleep(loop, {3: lambda: self.printer.set(running('other_part-j00000001'))})
        self.deliver(loop, dict(JOB, previous_start=previous))
        self.assertEqual(self.relay.ack_codes, ['delivery.printer_busy_at_start'])
        self.assertEqual(self.printer.starts, [])

    def test_an_old_previous_start_settles_on_the_first_free_picture(self):
        self.printer.starts_running = True
        loop = self.make_paired()
        previous = {'id': 'j00000001', 'filename': 'other_part.gcode.3mf',
                    'age_s': int(rl.START_SETTLE_SECONDS) + 1}
        self.deliver(loop, dict(JOB, previous_start=previous))
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])
        self.assertEqual(self.clock.slept[:1], [])

    def test_a_previous_start_this_process_acknowledged_is_not_rebuilt(self):
        self.printer.starts_running = True
        loop = self.make_paired()
        loop._remember_acked('j00000001')
        previous = {'id': 'j00000001', 'filename': 'other_part.gcode.3mf', 'age_s': 5}
        self.deliver(loop, dict(JOB, previous_start=previous))
        self.assertIsNone(loop.hold)
        self.assertEqual(self.relay.acks, [('j8f3a2c1', True, None)])

    def test_a_malformed_previous_start_is_ignored(self):
        self.printer.starts_running = True
        loop = self.make_paired()
        for previous in ('x', {'id': 5}, {'id': 'j00000001'}, {'filename': 'a.3mf'}):
            loop.hold = None
            self.deliver(loop, dict(JOB, id=f'j{len(self.relay.acks):08x}',
                                    previous_start=previous))
        self.assertIsNone(loop.hold)
