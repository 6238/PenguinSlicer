"""The relay's in-memory printer records, code handling and tokens, without any app.

Ported from the original relay's test_printer_relay.py. Changed: the module-level singleton
and its tests are gone (create_app now owns one relay per app), and the cross-process token
test is a fixed token instead of a second interpreter."""
import re
import unittest

import pytest

from penguin_delivery_relay import relay as relay_module
from penguin_delivery_relay.relay import PrinterRelay

from relay_fakes import IDLE, FakeClock, running


class TestCodeGeneration(unittest.TestCase):
    def test_code_is_eight_symbols_from_the_alphabet(self):
        for _ in range(200):
            code = relay_module.generate_code()
            self.assertEqual(len(code), relay_module.CODE_LENGTH)
            for ch in code:
                self.assertIn(ch, relay_module.ALPHABET)

    def test_alphabet_omits_the_lookalike_letters(self):
        for ch in 'ILOU':
            self.assertNotIn(ch, relay_module.ALPHABET)

    def test_code_is_never_all_digits(self):
        # An all-digit code would be loaded from YAML as an int unless the mentor quotes it.
        for _ in range(500):
            self.assertFalse(relay_module.generate_code().isdigit())

    def test_an_all_digit_draw_is_redrawn(self):
        draws = list('01234567') + list('ABCDEFGH')
        original = relay_module.secrets.choice
        relay_module.secrets.choice = lambda alphabet: draws.pop(0)
        try:
            self.assertEqual(relay_module.generate_code(), 'ABCDEFGH')
        finally:
            relay_module.secrets.choice = original
        self.assertEqual(draws, [])

    def test_format_code_groups_in_fours(self):
        self.assertEqual(relay_module.format_code('7K3MQ9XW'), '7K3M-Q9XW')


class TestNormalization(unittest.TestCase):
    def test_uppercases_and_strips_separators(self):
        self.assertEqual(relay_module.normalize_code(' 7k3m-q9xw '), '7K3MQ9XW')
        self.assertEqual(relay_module.normalize_code('7K3M Q9XW'), '7K3MQ9XW')

    def test_maps_lookalike_letters(self):
        self.assertEqual(relay_module.normalize_code('OIL23456'), '01123456')
        self.assertEqual(relay_module.normalize_code('oil23456'), '01123456')

    def test_accepts_an_integer_from_unquoted_yaml(self):
        self.assertEqual(relay_module.normalize_code(12345678), '12345678')

    def test_rejects_wrong_length_and_bad_symbols(self):
        for bad in ('7K3MQ9X', '7K3MQ9XWZ', '7K3M-Q9X!', '', None, {'a': 1}, True, 3.5):
            self.assertIsNone(relay_module.normalize_code(bad), bad)


class TestTokens(unittest.TestCase):
    #: Minted once by issue_token('7K3MQ9XW', 'a-persistent-test-key', issued_at=1789300000).
    #: A token a daemon already holds must keep verifying across restarts and upgrades of
    #: the relay, as long as the key is the same; a change to the salt or the payload
    #: breaks this test before it breaks every paired Pi.
    GOLDEN = 'eyJjb2RlIjoiN0szTVE5WFciLCJpYXQiOjE3ODkzMDAwMDAuMH0.PXiJA7hePDaARh6diiELPyIB1EY'

    def test_round_trip_carries_the_code_and_issue_time(self):
        token = relay_module.issue_token('7K3MQ9XW', 'secret-one', issued_at=1234.0)
        self.assertEqual(relay_module.read_token(token, 'secret-one'), ('7K3MQ9XW', 1234.0))

    def test_a_token_minted_earlier_still_verifies_with_the_same_key(self):
        self.assertEqual(relay_module.read_token(self.GOLDEN, 'a-persistent-test-key'),
                         ('7K3MQ9XW', 1789300000.0))

    def test_the_same_inputs_mint_the_same_token(self):
        self.assertEqual(relay_module.issue_token('7K3MQ9XW', 'a-persistent-test-key',
                                                  issued_at=1789300000.0), self.GOLDEN)

    def test_token_is_rejected_under_a_different_key(self):
        self.assertIsNone(relay_module.read_token(self.GOLDEN, 'key-after-the-deploy'))

    def test_garbage_is_rejected_without_raising(self):
        for bad in ('not-a-token', '', None, 42):
            self.assertIsNone(relay_module.read_token(bad, 'secret-one'), bad)

    def test_the_salt_separates_printer_tokens_from_other_signatures(self):
        from itsdangerous import URLSafeSerializer
        forged = URLSafeSerializer('shared-key', salt='some-other-purpose').dumps(
            {'code': '7K3MQ9XW', 'iat': 0.0})
        self.assertIsNone(relay_module.read_token(forged, 'shared-key'))

    def test_a_signed_payload_that_is_not_a_code_is_rejected(self):
        from itsdangerous import URLSafeSerializer
        sign = URLSafeSerializer('k', salt=relay_module.TOKEN_SALT).dumps
        self.assertIsNone(relay_module.read_token(sign(['7K3MQ9XW']), 'k'))
        self.assertIsNone(relay_module.read_token(sign({'code': 'nope'}), 'k'))

    def test_a_bad_issue_time_reads_as_zero(self):
        from itsdangerous import URLSafeSerializer
        token = URLSafeSerializer('k', salt=relay_module.TOKEN_SALT).dumps(
            {'code': '7K3MQ9XW', 'iat': 'yesterday'})
        self.assertEqual(relay_module.read_token(token, 'k'), ('7K3MQ9XW', 0.0))


STATUS_DAY = 24 * 60 * 60


class RelayTestCase(unittest.TestCase):
    """Shared fixture: a relay on a fake clock, with one code already presented."""

    CODE = '7K3MQ9XW'

    def setUp(self):
        self.clock = FakeClock()
        self.relay = PrinterRelay(clock=self.clock)
        self.relay.note_code(self.CODE)

    def claim(self, job_id='j8f3a2c1', filename='sample_part.gcode.3mf'):
        return self.relay.claim_job(self.CODE, job_id=job_id, download_path='/download/tok',
                                    filename=filename, team_number=6238)

    def online(self, snapshot=IDLE):
        self.relay.note_daemon(self.CODE)
        self.relay.store_status(self.CODE, snapshot)

    def hand_out_a_job(self, filename='sample_part.gcode.3mf'):
        """Exchange, sync, send and hand out -- the state most job tests start from."""
        self.assertTrue(self.relay.begin_exchange(self.CODE))
        self.online()
        ok, reason, _ = self.claim(filename=filename)
        self.assertTrue(ok, reason)
        handed = self.relay.store_status(self.CODE, IDLE)
        self.assertEqual(handed['id'], 'j8f3a2c1')
        return handed


class TestNoteCodeAndExchange(RelayTestCase):
    def test_note_code_creates_a_record_and_returns_the_normal_form(self):
        fresh = PrinterRelay(clock=self.clock)
        self.assertEqual(fresh.note_code('7k3m-q9xw'), self.CODE)
        self.assertTrue(fresh.status_for(self.CODE)['paired'])

    def test_note_code_ignores_a_malformed_code(self):
        fresh = PrinterRelay(clock=self.clock)
        self.assertIsNone(fresh.note_code('nope'))
        self.assertIsNone(fresh.note_code(None))

    def test_exchange_refused_for_a_code_no_caller_has_presented(self):
        self.assertFalse(self.relay.begin_exchange('ABCDEFGH'))

    def test_exchange_refused_for_a_record_only_a_daemon_created(self):
        """A valid token recreates a record after a restart, but that is not a caller
        presenting the code, so it opens no exchange."""
        fresh = PrinterRelay(clock=self.clock)
        fresh.note_daemon(self.CODE)
        self.clock.advance(121)
        self.assertFalse(fresh.begin_exchange(self.CODE))

    def test_exchange_allowed_once_then_refused_while_the_daemon_is_heard(self):
        self.assertTrue(self.relay.begin_exchange(self.CODE))
        self.assertFalse(self.relay.begin_exchange(self.CODE))

    def test_exchange_allowed_again_after_two_minutes_of_silence(self):
        self.assertTrue(self.relay.begin_exchange(self.CODE))
        self.clock.advance(120)
        self.assertFalse(self.relay.begin_exchange(self.CODE))   # exactly two minutes: alive
        self.clock.advance(1)
        self.assertTrue(self.relay.begin_exchange(self.CODE))

    def test_seed_code_creates_a_record_like_a_caller_would(self):
        fresh = PrinterRelay(clock=self.clock)
        fresh.seed_code(self.CODE)
        self.assertTrue(fresh.begin_exchange(self.CODE))


class TestStatusShape(RelayTestCase):
    def test_unpaired_when_there_is_no_code(self):
        payload = self.relay.status_for(None)
        self.assertEqual(payload, PrinterRelay.UNPAIRED)
        payload['paired'] = True                       # a copy, not the class constant
        self.assertFalse(PrinterRelay.UNPAIRED['paired'])

    def test_unpaired_for_a_code_the_relay_never_heard_of(self):
        self.assertFalse(self.relay.status_for('ABCDEFGH')['paired'])

    def test_waiting_before_any_daemon_is_heard(self):
        payload = self.relay.status_for(self.CODE)
        self.assertTrue(payload['paired'])
        self.assertTrue(payload['waiting'])
        self.assertFalse(payload['online'])
        self.assertEqual(payload['code'], '7K3M-Q9XW')

    def test_heard_but_no_snapshot_is_neither_waiting_nor_online(self):
        self.relay.note_daemon(self.CODE)
        payload = self.relay.status_for(self.CODE)
        self.assertFalse(payload['waiting'])
        self.assertFalse(payload['online'])
        self.assertIsNone(payload['status'])

    def test_online_and_age_come_from_the_relay_clock_not_the_snapshot(self):
        self.online()
        self.clock.advance(7)
        payload = self.relay.status_for(self.CODE)
        self.assertTrue(payload['online'])
        self.assertEqual(payload['age_seconds'], 7)
        self.assertEqual(payload['status']['state'], 'idle')

    def test_offline_once_the_snapshot_is_older_than_two_minutes(self):
        self.online()
        self.clock.advance(121)
        payload = self.relay.status_for(self.CODE)
        self.assertFalse(payload['online'])
        self.assertEqual(payload['age_seconds'], 121)

    def test_a_snapshot_that_is_not_a_mapping_is_stored_as_none(self):
        self.relay.note_daemon(self.CODE)
        self.relay.store_status(self.CODE, ['not', 'a', 'snapshot'])
        payload = self.relay.status_for(self.CODE)
        self.assertIsNone(payload['status'])
        self.assertTrue(payload['online'])            # it still arrived

    def test_status_dropped_after_twenty_four_hours(self):
        """Only a daemon sync refreshes the snapshot, so a record a caller keeps alive
        still loses its day-old status. The two TTLs are equal, so the touch has to fall
        between them for this to exercise the status branch rather than the record one."""
        self.online()
        self.clock.advance(12 * 60 * 60)
        self.relay.note_code(self.CODE)      # a caller keeps the record alive
        self.clock.advance(13 * 60 * 60)     # the snapshot is now 25 hours old
        payload = self.relay.status_for(self.CODE)
        self.assertTrue(payload['paired'])
        self.assertIsNone(payload['status'])
        self.assertIsNone(payload['age_seconds'])
        self.assertFalse(payload['online'])

    def test_record_dropped_when_nothing_touches_it_for_a_day(self):
        self.clock.advance(STATUS_DAY + 1)
        self.assertFalse(self.relay.status_for(self.CODE)['paired'])

    def test_a_dropped_record_takes_its_job_with_it_without_an_expiry_event(self):
        """A record untouched for a day is deleted whole; the job inside it never reaches
        a deadline, so no expiry event is raised for it."""
        self.online()
        self.claim()
        self.clock.advance(STATUS_DAY + 1)
        self.assertIsNone(self.relay.status_for(self.CODE)['job'])
        self.assertEqual(self.relay.drain_expiry_events(), [])


class TestSendRefusals(RelayTestCase):
    """Every refusal claim_job can give, word for word: these are the texts a caller shows."""

    def test_refused_for_a_code_the_relay_does_not_hold(self):
        self.assertEqual(self.relay.claim_job('ABCDEFGH', job_id='j1', download_path='/d',
                                              filename='f', team_number=None),
                         (False, 'No printer paired', None))

    def test_refused_when_no_daemon_has_ever_been_heard(self):
        self.assertEqual(self.claim(), (False, 'The Pi has not reported since the service '
                                               'started; check the setup guide.', None))

    def test_refused_when_heard_but_no_snapshot_yet(self):
        self.relay.note_daemon(self.CODE)
        self.assertEqual(self.claim()[1], 'No printer reporting yet; try again in a moment.')

    def test_refused_when_the_daemon_has_gone_quiet(self):
        self.online()
        self.clock.advance(7 * 60)
        self.assertEqual(self.claim()[1], 'Printer offline, last seen 7 min ago')

    def test_refused_while_the_printer_is_running(self):
        self.online(running('other-jdeadbeef.gcode.3mf'))
        self.assertEqual(self.claim()[1], 'Printer busy, printing other.gcode.3mf at 42 percent')

    def test_running_with_no_file_name_says_a_file(self):
        self.online(running(''))
        self.assertEqual(self.claim()[1], 'Printer busy, printing a file at 42 percent')

    def test_refused_while_paused_unreachable_or_unrecognised(self):
        for state, unrecognised, expected in (
                ('paused', None, 'Paused, a file'),
                ('unreachable', None, 'Printer unreachable from the Pi'),
                ('unrecognised', "gcode_state 'SLICING'",
                 "Printer state not recognised: gcode_state 'SLICING'"),
                ('busy', None, "Printer state not recognised: state 'busy'"),
                (None, None, 'Printer state not recognised: state None'),
                # A state that is not text is not kept, which reads as none at all.
                (42, None, 'Printer state not recognised: state None')):
            with self.subTest(state=state):
                self.online(dict(IDLE, state=state, unrecognised=unrecognised))
                ok, reason, job = self.claim()
                self.assertEqual((ok, reason, job), (False, expected, None))

    def test_a_printer_whose_last_print_ended_badly_is_free(self):
        """Round 3, defect 4: a stopped or failed print leaves the printer free; the
        daemon starts the next one only on a fresh report of a free printer."""
        for error in ('PRINT_ERROR_0300400C', 'HMS_0300_0100_0001_0004', None):
            with self.subTest(error=error):
                self.setUp()
                self.online(dict(IDLE, state='error', error=error))
                self.assertEqual(self.claim()[:2], (True, None))

    def test_busy_without_a_percent_never_says_none(self):
        self.online(dict(IDLE, state='running', file='other.gcode.3mf', percent=None))
        self.assertEqual(self.claim()[1], 'Printer busy, printing other.gcode.3mf')

    def test_refused_when_a_job_is_already_in_flight(self):
        self.hand_out_a_job()
        self.assertEqual(self.claim(job_id='jaaaaaaaa')[1],
                         'A job is already on its way to the printer')

    def test_finished_counts_as_free(self):
        self.online(dict(IDLE, state='finished', file='old-j8f3a2c1.gcode.3mf'))
        self.assertTrue(self.claim()[0])

    def test_accepted_when_idle_and_online(self):
        self.online()
        ok, reason, job = self.claim()
        self.assertTrue(ok, reason)
        self.assertEqual(job['state'], 'pending')
        self.assertEqual(job['download_path'], '/download/tok')
        self.assertEqual(self.relay.status_for(self.CODE)['job']['state'], 'pending')


class TestJobLifecycle(RelayTestCase):
    """Every transition of a job: pending -> handed_out -> finished (ok or failed), and the
    two deadline expiries."""

    def test_sync_hands_out_a_pending_job_once_then_repeats_it(self):
        self.online()
        self.claim()
        self.clock.advance(4)
        first = self.relay.store_status(self.CODE, IDLE)
        self.assertEqual(first['state'], 'handed_out')
        self.assertEqual(first['handed_out_at'], self.clock.now)
        self.clock.advance(5)
        again = self.relay.store_status(self.CODE, IDLE)
        self.assertEqual(again['id'], 'j8f3a2c1')     # a restarted daemon sees it again
        self.assertEqual(again['handed_out_at'], first['handed_out_at'])   # not re-stamped

    def test_sync_hands_out_nothing_when_there_is_no_job(self):
        self.relay.note_daemon(self.CODE)
        self.assertIsNone(self.relay.store_status(self.CODE, IDLE))

    def test_ack_records_the_outcome_and_clears_the_job(self):
        self.hand_out_a_job()
        self.assertEqual(self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=True, reason=None),
                         (True, 6238))
        payload = self.relay.status_for(self.CODE)
        self.assertIsNone(payload['job'])
        self.assertEqual(payload['last_result'], {'ok': True, 'reason': None,
                                                  'age_seconds': 0})
        self.assertIsNone(self.relay.held_job_id(self.CODE))

    def test_an_ack_before_the_hand_out_still_finishes_the_job(self):
        self.online()
        self.claim()
        self.assertEqual(self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=False,
                                               reason='x'), (True, 6238))
        self.assertIsNone(self.relay.status_for(self.CODE)['job'])

    def test_ack_for_an_unknown_job_is_not_found_and_changes_nothing(self):
        self.hand_out_a_job()
        self.assertEqual(self.relay.finish_job(self.CODE, 'jffffffff', ok=True, reason=None),
                         (False, None))
        self.assertEqual(self.relay.held_job_id(self.CODE), 'j8f3a2c1')

    def test_ack_with_no_job_held_is_not_found(self):
        self.online()
        self.assertEqual(self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=True, reason=None),
                         (False, None))

    def test_failed_ack_keeps_the_reason_for_ten_minutes(self):
        self.hand_out_a_job()
        self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=False,
                              reason='Upload to printer failed: connection refused')
        self.clock.advance(600)
        last = self.relay.status_for(self.CODE)['last_result']
        self.assertEqual(last['reason'], 'Upload to printer failed: connection refused')
        self.assertEqual(last['age_seconds'], 600)
        self.clock.advance(1)
        self.assertIsNone(self.relay.status_for(self.CODE)['last_result'])

    def test_pending_job_expires_after_three_minutes(self):
        self.online()
        self.claim()
        self.clock.advance(180)
        self.assertEqual(self.relay.held_job_id(self.CODE), 'j8f3a2c1')   # not yet
        self.clock.advance(1)
        payload = self.relay.status_for(self.CODE)
        self.assertIsNone(payload['job'])
        self.assertEqual(payload['last_result']['reason'], 'printer did not pick up the job')
        self.assertFalse(payload['last_result']['ok'])
        events = self.relay.drain_expiry_events()
        self.assertEqual(events, [relay_module.ExpiryEvent(
            self.CODE, 'j8f3a2c1', 6238, 'printer did not pick up the job')])
        self.assertEqual(self.relay.drain_expiry_events(), [])

    def test_handed_out_job_expires_fifteen_minutes_after_the_hand_out(self):
        self.online()
        self.claim()
        self.clock.advance(170)                 # picked up late, just inside three minutes
        self.relay.store_status(self.CODE, IDLE)
        self.clock.advance(900)                 # fifteen minutes after the hand-out
        self.assertEqual(self.relay.held_job_id(self.CODE), 'j8f3a2c1')
        self.clock.advance(1)
        payload = self.relay.status_for(self.CODE)
        self.assertIsNone(payload['job'])
        self.assertEqual([e.reason for e in self.relay.drain_expiry_events()],
                         ['printer did not confirm the job'])

    def test_an_ack_after_the_expiry_is_not_found(self):
        self.hand_out_a_job()
        self.clock.advance(901)
        self.assertEqual(self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=True, reason=None),
                         (False, None))

    def test_a_new_send_is_accepted_once_the_last_job_finished(self):
        self.hand_out_a_job()
        self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=True, reason=None)
        ok, reason, _ = self.claim(job_id='jbbbbbbbb')
        self.assertTrue(ok, reason)

    def test_snapshot_naming_the_job_clears_a_failed_last_result(self):
        """The printer has the job whatever the acknowledgement said."""
        self.hand_out_a_job()
        self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=False, reason='timed out waiting')
        self.relay.store_status(self.CODE, running('sample_part-j8f3a2c1.gcode.3mf'))
        self.assertIsNone(self.relay.status_for(self.CODE)['last_result'])

    def test_snapshot_naming_another_file_leaves_last_result_alone(self):
        self.hand_out_a_job()
        self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=False, reason='timed out waiting')
        self.relay.store_status(self.CODE, running('someone-else.gcode.3mf'))
        self.assertIsNotNone(self.relay.status_for(self.CODE)['last_result'])

    @pytest.mark.known_fault
    def test_known_fault_a_real_h2s_snapshot_never_clears_a_failed_last_result(self):
        """KNOWN FAULT, to be fixed in hardening. The daemon fills `file` from the H2S's
        `gcode_file`, which is the G-code path inside the archive and never carries the job
        id, so the relay cannot see that the printer has the job. On 2026-10-09 the part
        printed while the status line kept saying the job failed. Hardening flips this to
        assertIsNone."""
        self.hand_out_a_job()
        self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=False,
                              reason='the printer did not start the file within 60s')
        self.relay.store_status(self.CODE, running('/data/Metadata/plate_1.gcode'))
        self.assertIsNotNone(self.relay.status_for(self.CODE)['last_result'])


class TestDaemonSurvivesARelayRestart(RelayTestCase):
    def test_a_valid_token_recreates_the_record_after_a_restart(self):
        """A restart empties the relay. The daemon's next sync must work, so status is
        back before any caller opens a page."""
        fresh = PrinterRelay(clock=self.clock)          # stands in for the new process
        self.assertIsNone(fresh.status_for(self.CODE)['status'])
        fresh.note_daemon(self.CODE)                    # what a valid bearer token does
        fresh.store_status(self.CODE, running('sample_part-j8f3a2c1.gcode.3mf'))
        payload = fresh.status_for(self.CODE)
        self.assertTrue(payload['paired'])
        self.assertTrue(payload['online'])
        self.assertEqual(payload['status']['state'], 'running')

    def test_a_job_in_flight_is_lost_with_the_restart(self):
        """Nothing is on disk, so a restart forgets the job; the daemon's ack for it then
        answers not found, which the daemon treats as final."""
        self.hand_out_a_job()
        fresh = PrinterRelay(clock=self.clock)
        fresh.note_daemon(self.CODE)
        self.assertIsNone(fresh.store_status(self.CODE, IDLE))
        self.assertEqual(fresh.finish_job(self.CODE, 'j8f3a2c1', ok=True, reason=None),
                         (False, None))


class TestPing(RelayTestCase):
    def test_ping_reports_flags_and_stores_nothing(self):
        """`penguincam-printer status` must not be able to disturb the running service, so
        ping does NOT record daemon_seen_at -- otherwise a mentor running status could
        block the real daemon's re-exchange for two minutes."""
        self.assertEqual(self.relay.ping(self.CODE),
                         {'ok': True, 'waiting': True, 'online': False})
        self.assertTrue(self.relay.begin_exchange(self.CODE))

    def test_ping_for_an_unknown_code(self):
        self.assertEqual(self.relay.ping('ABCDEFGH'),
                         {'ok': True, 'waiting': True, 'online': False})

    def test_ping_once_online(self):
        self.online()
        self.assertEqual(self.relay.ping(self.CODE),
                         {'ok': True, 'waiting': False, 'online': True})


class TestJobIds(unittest.TestCase):
    def test_job_id_is_j_plus_eight_hex_digits(self):
        for _ in range(200):
            self.assertRegex(relay_module.new_job_id(), r'^j[0-9a-f]{8}$')

    def test_job_ids_do_not_repeat(self):
        self.assertEqual(len({relay_module.new_job_id() for _ in range(500)}), 500)


class TestEveryEntryPointNormalizes(RelayTestCase):
    """Everywhere a code is read, it is normalised before use: the display form works
    wherever the canonical one does, and a malformed one is refused rather than raising or
    keying a ghost record."""

    TYPED = '7k3m-q9xw'

    def test_begin_exchange_accepts_the_display_form(self):
        self.assertTrue(self.relay.begin_exchange(self.TYPED))

    def test_note_daemon_accepts_the_display_form_without_a_ghost_record(self):
        self.assertEqual(self.relay.note_daemon(self.TYPED), self.CODE)
        self.assertFalse(self.relay.status_for(self.CODE)['waiting'])
        self.assertFalse(self.relay.status_for(self.TYPED)['waiting'])

    def test_store_status_finish_job_and_held_job_id_accept_the_display_form(self):
        self.hand_out_a_job()
        self.relay.store_status(self.TYPED, IDLE)
        self.assertEqual(self.relay.held_job_id(self.TYPED), 'j8f3a2c1')
        self.assertEqual(self.relay.finish_job(self.TYPED, 'j8f3a2c1', ok=True, reason=None),
                         (True, 6238))

    def test_ping_accepts_the_display_form(self):
        self.relay.note_daemon(self.CODE)
        self.assertFalse(self.relay.ping(self.TYPED)['waiting'])

    def test_a_malformed_code_is_refused_everywhere_and_never_raises(self):
        for bad in (None, '', 'nope', 'OIL!', {'a': 1}):
            self.assertIsNone(self.relay.note_daemon(bad), bad)
            self.assertFalse(self.relay.begin_exchange(bad), bad)
            self.assertIsNone(self.relay.store_status(bad, IDLE), bad)
            self.assertIsNone(self.relay.held_job_id(bad), bad)
            self.assertEqual(self.relay.finish_job(bad, 'j8f3a2c1', ok=True, reason=None),
                             (False, None))
            ok, _, job = self.relay.claim_job(bad, job_id='jaaaaaaaa',
                                              download_path='/download/tok',
                                              filename='sample_part.gcode.3mf',
                                              team_number=6238)
            self.assertFalse(ok, bad)
            self.assertIsNone(job, bad)
            self.assertFalse(self.relay.ping(bad)['online'], bad)
        self.assertTrue(self.relay.begin_exchange(self.CODE))   # no ghost record blocked it


class TestFreshnessIsOneRule(RelayTestCase):
    def test_status_and_send_agree_on_a_fractional_boundary(self):
        """At 120.5 seconds the status line once said online while a send refused as
        offline, because one comparison truncated the age to whole seconds first."""
        self.online()
        self.clock.advance(120.5)
        self.assertFalse(self.relay.status_for(self.CODE)['online'])
        self.assertFalse(self.relay.ping(self.CODE)['online'])
        ok, reason, _ = self.claim()
        self.assertFalse(ok)
        self.assertIn('offline', reason)

    def test_exactly_two_minutes_is_still_fresh_everywhere(self):
        self.online()
        self.clock.advance(120)
        self.assertTrue(self.relay.status_for(self.CODE)['online'])
        self.assertTrue(self.relay.ping(self.CODE)['online'])
        ok, reason, _ = self.claim()
        self.assertTrue(ok, reason)


class TestReadsDoNotLeakTheStoredRecord(RelayTestCase):
    def test_mutating_the_returned_status_does_not_change_the_record(self):
        self.online()
        payload = self.relay.status_for(self.CODE)
        payload['status']['state'] = 'running'
        payload['status']['printer']['name'] = 'somewhere else'
        again = self.relay.status_for(self.CODE)
        self.assertEqual(again['status']['state'], 'idle')
        self.assertEqual(again['status']['printer']['name'], 'Shop H2S')

    def test_mutating_a_returned_job_does_not_change_the_record(self):
        self.online()
        _, _, job = self.claim()
        job['state'] = 'handed_out'
        self.assertEqual(self.relay.status_for(self.CODE)['job']['state'], 'pending')


class TestNoFlaskImport(unittest.TestCase):
    def test_the_relay_state_never_imports_flask(self):
        """relay.py stays importable and testable without an app."""
        with open(relay_module.__file__, encoding='utf-8') as handle:
            source = handle.read()
        for line in source.splitlines():
            self.assertIsNone(re.match(r'\s*(import|from)\s+flask\b', line, re.IGNORECASE),
                              line)


class TestStripJobSuffix(unittest.TestCase):
    """The daemon uploads 'sample_part-<job id>.gcode.3mf' so the printer's own display
    names the job; a caller shows the name without that suffix."""

    def test_strips_the_job_id_the_daemon_added(self):
        self.assertEqual(relay_module.strip_job_suffix('sample_part-j8f3a2c1.gcode.3mf'),
                         'sample_part.gcode.3mf')

    def test_strips_a_real_new_job_id(self):
        job_id = relay_module.new_job_id()
        self.assertEqual(relay_module.strip_job_suffix(f'sample_part-{job_id}.gcode.3mf'),
                         'sample_part.gcode.3mf')

    def test_leaves_any_other_name_alone(self):
        for name in ('sample_part.gcode.3mf',          # no suffix at all
                     'sample_part-j8f3a2.gcode.3mf',   # too short to be a job id
                     'sample_part-jzzzzzzz.gcode.3mf',  # not hex
                     'sample_part-j8f3a2c1.3mf',       # a different extension
                     'sample_part-j8f3a2c1.gcode.3mf.bak',  # not at the end
                     'holder v2.gcode.3mf',
                     ''):
            self.assertEqual(relay_module.strip_job_suffix(name), name)

    def test_a_non_string_passes_through(self):
        self.assertIsNone(relay_module.strip_job_suffix(None))


class TestDisplayNames(RelayTestCase):
    JOB_FILE = 'sample_part-j8f3a2c1.gcode.3mf'

    def test_status_carries_both_the_reported_and_the_display_name(self):
        self.online(running(self.JOB_FILE))
        status = self.relay.status_for(self.CODE)['status']
        self.assertEqual(status['file'], self.JOB_FILE)
        self.assertEqual(status['display_name'], 'sample_part.gcode.3mf')

    def test_job_carries_both_names(self):
        self.hand_out_a_job(filename=self.JOB_FILE)
        job = self.relay.status_for(self.CODE)['job']
        self.assertEqual(job['filename'], self.JOB_FILE)
        self.assertEqual(job['display_name'], 'sample_part.gcode.3mf')

    def test_the_paused_refusal_shows_the_name_without_the_job_id(self):
        self.online(dict(running(self.JOB_FILE), state='paused'))
        self.assertEqual(self.claim(job_id='jaaaaaaaa')[1], 'Paused, sample_part.gcode.3mf')

    def test_display_name_is_not_written_back_into_the_stored_snapshot(self):
        """status_for adds display_name to its own copy; the record keeps what the daemon
        sent, which is what the job-id match in store_status reads."""
        self.hand_out_a_job(filename=self.JOB_FILE)
        self.relay.finish_job(self.CODE, 'j8f3a2c1', ok=False, reason='timed out waiting')
        self.relay.status_for(self.CODE)
        self.relay.store_status(self.CODE, running(self.JOB_FILE))
        self.assertIsNone(self.relay.status_for(self.CODE)['last_result'])
