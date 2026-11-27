"""The daemon against the simulated printer, over real loopback sockets (`make test-sim`).

The real PrinterLink and the real pinned printer library talk MQTT over TLS and implicit
FTPS to simulator/printer.py; the relay is the daemon tests' FakeRelay and the clock is
fake. Every wait is on an event: the library's own message callback says when a status
document has arrived. This suite doubles as the upstream check of the printer library's
networking (`make test-upstream` runs it too)."""
import json
import os
import shutil
import tempfile
import threading
import time
import unittest

import pytest

from penguin_delivery_daemon import printer as pr
from penguin_delivery_daemon import run_loop as rl
from penguin_delivery_daemon.config import DaemonConfig
from penguin_delivery_relay.relay import PrinterRelay

from daemon_fakes import JOB, SUFFIXED, FakeClock, FakeRelay
from simulator.printer import SimulatedPrinter, load_scenario, read_recording, scenario_names

pytestmark = pytest.mark.simulator

CONTENT = bytes(range(256)) * 400            # 100 kB: several FTP blocks


class SimTestCase(unittest.TestCase):
    scenario = 'whole_print'
    access_code = '12345678'

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.sim = SimulatedPrinter(self.scenario).start()
        self.addCleanup(self.sim.stop)
        self.clock = FakeClock()
        self.logged = []
        self.arrived = threading.Condition()
        self.messages = 0
        self.link = self.connect(self.access_code)

    def connect(self, access_code, ports=None):
        link = pr.PrinterLink('127.0.0.1', self.sim.serial, access_code,
                              ports=ports or self.sim.ports, clock=self.clock,
                              log=self.logged.append)
        link.connect()
        self.addCleanup(link.disconnect)

        def on_message():
            with self.arrived:
                self.messages += 1
                self.arrived.notify_all()

        # PrinterLink's own hook on the library's message callback, which it uses to
        # measure the age of the printer's report.
        link.on_document = on_message
        if access_code == self.sim.access_code and ports is None:
            # The answer to the library's pushall. The predicate is checked first, so a
            # document that arrived before the callback was installed is not missed.
            self.wait_until(lambda: bool(link.raw_report()), 'the first status document')
        return link

    def wait_until(self, predicate, what, timeout=5):
        """Wait on the library's message callback until `predicate` holds.

        Only a wake from the callback counts (round 3, defect 6): a predicate that turns
        true while nothing wakes the wait -- the callback never attached, say -- fails
        here at the ceiling, never passes because it happens to hold by then. The ceiling
        is far above the milliseconds a document takes over loopback."""
        deadline = time.monotonic() + timeout
        with self.arrived:
            while not predicate():
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self.arrived.wait(remaining):
                    self.fail(f'{what} never arrived: the library\'s message callback did '
                              f'not wake the wait within {timeout} s')

    def has(self, document):
        report = self.link.raw_report()
        return all(report.get(key) == value for key, value in document.items())

    def step(self):
        """The printer's next status document, waited for until the library has merged
        it into its report."""
        if not self.sim.step():
            return False
        sent = self.sim.published[-1]
        if not self.sim.silent:
            self.wait_until(lambda: self.has(sent), f'status document {sent}')
        return True

    def run_job(self, content=CONTENT, on_sleep=None):
        """Deliver one job. `on_sleep(loop)` runs after each of the daemon's waits, once
        the printer has caught up: where a test steps the printer on."""
        holder = {}
        relay = FakeRelay(token='signed')
        relay.content = content
        relay.sync_job = dict(JOB, size=len(content))
        starts = []
        original_start = self.link.start

        def start(name):
            starts.append(name)
            return original_start(name)

        self.link.start = start

        requests = []
        original_request = self.link.request_report

        def request_report():
            printer = self.link._printer
            if printer is not None and printer.mqtt_client_connected():
                requests.append(self.sim.pushalls)      # a request that can arrive
            return original_request()

        self.link.request_report = request_report

        def sleep(seconds):
            """The daemon waits: let the printer catch up first (the start command and
            its answer travel asynchronously), then send its next status document."""
            self.clock.sleep(seconds)
            if requests:
                # The daemon asked for a whole report: let the request arrive, and the
                # answer too, when the printer gives one.
                before = requests.pop()
                requests.clear()
                self.assertTrue(self.sim.wait_for(lambda: self.sim.pushalls > before))
                if self.sim.answer_pushall and not self.sim.silent:
                    status = dict(self.sim.status)
                    self.wait_until(lambda: self.has(status), 'the answer to the request')
            if starts:
                self.assertTrue(self.sim.wait_for(lambda: len(self.sim.commands) >= len(starts)))
                if self.sim.published:
                    last = self.sim.published[-1]
                    self.wait_until(lambda: self.has(last), 'the answer to the start')
            if on_sleep is not None:
                on_sleep(holder['loop'])

        config = DaemonConfig(backend_url='https://example.test', pairing_code='7K3MQ9XW',
                              token='signed', path=os.path.join(self.tmp, 'c.toml'))
        loop = rl.RunLoop(config, relay, self.link, clock=self.clock, sleep=sleep,
                          log=self.logged.append, executor=rl.InlineExecutor(),
                          download_dir=self.tmp, rand=lambda: 0.0, instance='sim',
                          save_token=lambda *a: None)
        holder['loop'] = loop
        loop.tick()
        self.assertEqual(len(relay.acks), 1, relay.acks)
        return relay.acks[0][1:], relay.ack_codes[0]


class TestWholePrint(SimTestCase):
    def test_a_whole_print_is_delivered_started_once_and_followed_to_the_end(self):
        (ok, reason), code = self.run_job()
        self.assertEqual((ok, reason, code), (True, None, None))
        self.assertEqual(self.sim.files[SUFFIXED], CONTENT)
        self.assertEqual(self.sim.started, [SUFFIXED])
        command = self.sim.commands[0]
        self.assertEqual((command['param'], command['use_ams']), ('Metadata/plate_1.gcode',
                                                                   False))
        stages = [self.link.snapshot()['stage']]
        while self.step():
            stages.append(self.link.snapshot()['stage'])
        snapshot = self.link.snapshot()
        self.assertEqual(snapshot['state'], pr.FINISHED)
        self.assertEqual(snapshot['job_name'], SUFFIXED[:-len('.gcode.3mf')])
        self.assertIn('cleaning_nozzle', stages)
        self.assertIn('printing', stages)

    def test_the_relay_follows_the_print_to_done_from_the_daemons_snapshots(self):
        relay = PrinterRelay(clock=FakeClock())
        relay.note_code('7K3MQ9XW')
        relay.note_daemon('7K3MQ9XW')
        relay.store_status('7K3MQ9XW', self.link.snapshot())
        relay.claim_job('7K3MQ9XW', job_id='j8f3a2c1', download_path='/d',
                        filename=JOB['filename'], team_number=None)
        relay.store_status('7K3MQ9XW', self.link.snapshot())
        self.run_job()
        relay.finish_job('7K3MQ9XW', 'j8f3a2c1', ok=True, reason=None)
        while self.step():
            relay.store_status('7K3MQ9XW', self.link.snapshot())
        report = relay.delivery_report('7K3MQ9XW', 'j8f3a2c1')
        self.assertEqual((report['state'], report['percent'], report['total_layers']),
                         ('done', 100, 50))

    def test_the_printers_listing_reports_the_uploaded_size(self):
        self.run_job()
        self.assertEqual(self.link.remote_size(SUFFIXED), len(CONTENT))
        self.assertEqual(self.link.delete(SUFFIXED), (pr.REMOVED, '250 Deleted.'))
        self.assertNotIn(SUFFIXED, self.sim.files)
        self.assertEqual(self.link.delete(SUFFIXED), (pr.NOT_ON_PRINTER, '550 No such file.'))

    def test_any_certificate_is_accepted(self):
        """The daemon accepts any certificate the printer presents (the Upstream section
        of README-details.md): the library connects with verification off on both protocols. Pinned
        here so a change upstream is noticed."""
        self.assertEqual(self.link.snapshot()['state'], pr.IDLE)


class TestUploadFaults(SimTestCase):
    scenario = 'upload_426'

    def test_the_426_after_a_whole_file_is_a_success_with_no_error_in_the_log(self):
        (ok, _reason), _code = self.run_job()
        self.assertTrue(ok)
        self.assertEqual([line for line in self.logged if 'error' in line.lower()
                          or 'failed' in line.lower()], [])
        self.assertTrue(any('that is harmless' in line for line in self.logged))


class TestUploadCut(SimTestCase):
    scenario = 'upload_cut'

    def test_a_cut_upload_is_retried_then_fails_and_is_never_started(self):
        (ok, reason), code = self.run_job()
        self.assertEqual((ok, code), (False, 'delivery.upload_failed'))
        self.assertEqual(self.sim.started, [])
        self.assertNotIn(SUFFIXED, self.sim.files)               # the partial file removed


class TestUploadShort(SimTestCase):
    scenario = 'upload_short'

    def test_a_226_for_a_short_file_is_caught_by_the_printers_listing(self):
        (ok, reason), code = self.run_job()
        self.assertEqual(code, 'delivery.upload_failed')
        self.assertEqual(reason, f'the printer has {len(CONTENT) - 10} of {len(CONTENT)} bytes')
        self.assertEqual(self.sim.started, [])


class TestUploadRefused(SimTestCase):
    scenario = 'upload_refused'

    def test_a_refused_upload_fails_as_an_upload_failure(self):
        (ok, reason), code = self.run_job()
        self.assertEqual((ok, code), (False, 'delivery.upload_failed'))
        self.assertEqual(self.sim.started, [])

    def test_a_file_that_never_arrived_is_said_so_from_the_printers_answer(self):
        """Review 6, defect 6, and delivery review 2, defects 1 and 2, through the real
        library: the delete is sent, the printer answers "550 No such file", the library's
        failure line for it is kept off the daemon's log, and the log says the file was not
        on the printer, not that it was removed."""
        self.run_job()
        self.assertTrue(any(f'{SUFFIXED} was not on the printer' in line
                            for line in self.logged), self.logged)
        self.assertEqual([line for line in self.logged
                          if '550' in line or f'removed {SUFFIXED}' in line
                          or 'could not confirm' in line], [])


class TestStartIgnored(SimTestCase):
    scenario = 'start_ignored'

    def test_a_start_the_printer_ignores_times_out_after_one_start(self):
        (ok, _reason), code = self.run_job()
        self.assertEqual(code, 'delivery.start_timeout')
        self.assertEqual(len(self.sim.commands), 1)


class TestOtherFile(SimTestCase):
    scenario = 'other_file'

    def test_the_printer_starting_another_file_is_reported_by_name(self):
        (ok, reason), code = self.run_job()
        self.assertEqual(code, 'delivery.start_other_file')
        self.assertEqual(reason, 'the printer started someone_elses_part instead')


class TestErrorMidPrint(SimTestCase):
    scenario = 'error_mid_print'

    def test_an_error_that_clears_then_one_that_ends_the_print(self):
        self.assertTrue(self.run_job()[0][0])
        seen = []
        while self.step():
            snapshot = self.link.snapshot()
            seen.append((snapshot['state'], snapshot['error']))
        self.assertEqual(seen[0], (pr.RUNNING, 'HMS_0300_0100_0004_0001'))   # info: runs on
        self.assertEqual(seen[1], (pr.RUNNING, None))                       # cleared
        self.assertEqual(seen[-1], (pr.ERROR, 'PRINT_ERROR_07008011'))

    def test_a_status_document_that_is_not_json_does_not_stop_the_stream(self):
        self.run_job()
        self.sim.publish(raw=b'this is not json')
        self.sim.publish({'mc_percent': 33})
        # The document after the garbage still arrives, so the library's network thread
        # survived it (a stream that stopped would time out here).
        self.wait_until(lambda: self.link.raw_report().get('mc_percent') == 33,
                        'the document after the garbage')
        self.assertEqual(self.link.snapshot()['state'], pr.RUNNING)

    def test_a_silent_stream_shows_its_age_while_the_socket_stays_open(self):
        self.run_job()
        self.sim.silent = True
        before = self.link.snapshot()['report_age_s']
        self.clock.advance(90)
        self.sim.step()                      # sent nowhere
        snapshot = self.link.snapshot()
        self.assertEqual(snapshot['report_age_s'], before + 90)
        self.assertNotEqual(snapshot['state'], pr.UNREACHABLE)


class TestReconnect(SimTestCase):
    def test_a_reconnect_with_no_new_document_keeps_the_old_age(self):
        """Defect 4: the printer drops the MQTT connection mid-print for five minutes and
        comes back saying nothing. The library keeps its last document; the snapshot shows
        it with its true age, never as fresh."""
        self.run_job()
        self.step()                                       # a document mid-print
        before = self.link.snapshot()
        self.assertEqual((before['state'], before['report_age_s']), (pr.RUNNING, 0))
        logins = len(self.sim.logins)
        pushalls = self.sim.pushalls
        self.sim.answer_pushall = False
        self.sim.drop_mqtt()
        self.clock.advance(300)
        # paho reconnects on its own after its one-second delay; the printer hears the
        # library's pushall and answers nothing.
        self.assertTrue(self.sim.wait_for(lambda: len(self.sim.logins) > logins
                                          and self.sim.pushalls > pushalls))
        self.assertTrue(self.link._printer.mqtt_client_connected()
                        or self.sim.wait_for(self.link._printer.mqtt_client_connected, 2))
        after = self.link.snapshot()
        self.assertEqual(after['state'], pr.RUNNING)
        self.assertEqual(after['percent'], before['percent'])     # the old figure ...
        self.assertGreaterEqual(after['report_age_s'], 300)       # ... with its old age


class TestTls12(SimTestCase):
    scenario = 'tls12'

    def test_a_whole_job_is_delivered_over_tls_1_2(self):
        content = os.urandom(1024 * 1024)
        (ok, _reason), code = self.run_job(content)
        self.assertEqual((ok, code), (True, None))
        self.assertEqual(self.sim.files[SUFFIXED], content)
        self.assertEqual(self.sim.started, [SUFFIXED])


class TestTls13(SimTestCase):
    scenario = 'tls13'

    def test_a_whole_job_is_delivered_over_tls_1_3(self):
        """Defect 5: under TLS 1.3 the library once lost the end of an upload. With its
        `unwrap` option the whole file arrives; the size check stays the guard."""
        for _ in range(4):
            content = os.urandom(1024 * 1024)
            self.sim.files.clear()
            self.sim.started.clear()
            (ok, _reason), code = self.run_job(content)
            self.assertEqual((ok, code), (True, None))
            self.assertEqual(self.sim.files[SUFFIXED], content)
            self.assertEqual(self.sim.started, [SUFFIXED])
            # Whole the first time: no upload was retried after a short listing.
            self.assertEqual([line for line in self.logged if 'did not work' in line], [])
            self.sim.status = dict(self.sim.scenario['idle'])
            self.sim.publish(dict(self.sim.scenario['idle']))
            self.wait_until(lambda: self.link.snapshot()['state'] == pr.IDLE, 'idle again')


class TestIdleWithAStageCodeLeftOrUnknown(SimTestCase):
    """Round 3, defect 1: IDLE is no print whatever the stage code says."""
    scenario = 'idle_stage_minus_one'

    def test_an_idle_printer_reporting_stage_minus_one_takes_the_print(self):
        before = self.link.snapshot()
        self.assertEqual((before['state'], before['unrecognised']), (pr.IDLE, "stg_cur '-1'"))
        (ok, reason), code = self.run_job()
        self.assertEqual((ok, reason, code), (True, None, None))
        self.assertEqual(self.sim.started, [SUFFIXED])


class TestIdleWithAStageLeftOver(SimTestCase):
    scenario = 'idle_stage_left_over'

    def test_an_idle_printer_still_showing_a_pause_stage_takes_the_print(self):
        self.assertEqual(self.link.snapshot()['state'], pr.IDLE)
        (ok, reason), code = self.run_job()
        self.assertEqual((ok, reason, code), (True, None, None))
        self.assertEqual(self.sim.started, [SUFFIXED])

    def test_an_idle_printer_with_a_stage_no_table_knows_takes_the_print(self):
        self.sim.publish({'stg_cur': 99})
        self.wait_until(lambda: self.link.raw_report().get('stg_cur') == 99, 'stage 99')
        self.assertEqual(self.link.snapshot()['state'], pr.IDLE)
        (ok, reason), code = self.run_job()
        self.assertEqual((ok, reason, code), (True, None, None))


class TestQuietWhileBusy(SimTestCase):
    """Round 3, defect 3: the daemon holds an old idle document while someone prints at
    the printer. It asks for a whole report before going on, and the answer refuses."""
    scenario = 'quiet_while_busy'

    def test_a_stale_idle_document_is_never_trusted_for_the_start(self):
        self.sim.silent = True
        self.sim.publish(dict(self.sim.scenario['walk_up']))        # heard by nobody
        self.clock.advance(rl.FRESH_REPORT_SECONDS + 45)
        stale = self.link.snapshot()
        self.assertEqual(stale['state'], pr.IDLE)
        self.assertGreater(stale['report_age_s'], rl.FRESH_REPORT_SECONDS)
        self.sim.silent = False                    # it answers a request, nothing more
        (ok, reason), code = self.run_job()
        self.assertEqual((ok, code), (False, 'delivery.printer_busy_at_start'))
        self.assertIn('walk_up_part', reason)
        self.assertEqual((self.sim.started, self.sim.files), ([], {}))
        self.assertGreaterEqual(self.sim.pushalls, 2)               # connect, and the ask

    def test_a_printer_that_answers_nothing_is_never_started(self):
        self.sim.silent = True
        self.clock.advance(rl.FRESH_REPORT_SECONDS + 45)
        (ok, reason), code = self.run_job()
        self.assertEqual((ok, code), (False, 'delivery.printer_unreachable_at_start'))
        self.assertEqual(self.sim.started, [])


class TestNoMainState(SimTestCase):
    """Review 4, defect 1: documents with figures and a name but no main state, even the
    answer to a request for a whole report, during someone else's print."""
    scenario = 'no_main_state'

    def test_a_picture_with_no_main_state_is_never_free(self):
        snapshot = self.link.snapshot()
        self.assertEqual((snapshot['state'], snapshot['whole']),
                         (pr.UNRECOGNISED_STATE, False))
        (ok, _reason), code = self.run_job()
        self.assertEqual((ok, code), (False, 'delivery.printer_unreachable_at_start'))
        self.assertEqual((self.sim.started, self.sim.files), ([], {}))
        self.assertGreaterEqual(self.sim.pushalls, 2)               # connect, and the asks


class TestLeftOverFinish(SimTestCase):
    """Review 4, defect 2: our name under the previous print's FINISH just after the start
    command is not the end of this print."""
    scenario = 'left_over_finish'

    def test_a_left_over_finish_with_our_name_waits_for_the_print(self):
        stepped = []

        def on_sleep(loop):
            if self.sim.started and len(stepped) < 5:
                stepped.append(loop.job_progress)
                if len(stepped) == 5:
                    self.step()                                     # PREPARE, ours

        (ok, reason), code = self.run_job(on_sleep=on_sleep)
        self.assertEqual((ok, reason, code), (True, None, None))
        self.assertEqual(len(stepped), 5)       # it waited through the left-over FINISH
        self.assertEqual(self.link.snapshot()['state'], pr.RUNNING)
        self.assertEqual(self.sim.started, [SUFFIXED])

    def test_a_left_over_finish_that_stays_is_a_start_not_shown_never_done(self):
        (ok, _reason), code = self.run_job()
        self.assertEqual((ok, code), (False, 'delivery.start_timeout'))
        self.assertEqual(len(self.sim.commands), 1)


class TestSlowStart(SimTestCase):
    """Review 4, defect 4: a printer that shows the print 90 s after accepting it."""
    scenario = 'slow_start'

    def test_a_slow_printer_gets_a_non_final_stage_then_the_print_is_followed(self):
        seen = []

        def on_sleep(loop):
            if not self.sim.started or shown:
                return
            seen.append((loop.job_progress or {}).get('stage'))
            if self.clock.now - started[0] >= 90:
                shown.append(self.step())                           # PREPARE, ours

        started = [self.clock.now]
        shown = []
        (ok, reason), code = self.run_job(on_sleep=on_sleep)
        self.assertEqual((ok, reason, code), (True, None, None))
        self.assertIn('start_not_shown', seen)
        self.assertEqual(seen[0], 'starting')
        self.assertEqual(len(self.sim.commands), 1)


def test_the_simulated_printer_runs_on_its_own_and_plays_a_print(tmp_path):
    """`python -m simulator` (review 4, defect 5): it says where it listens and what to
    give `pair`, a hand-run daemon's PrinterLink reaches it, and a start command plays
    the scenario's print one document per step."""
    import io
    from simulator import __main__ as sim_main

    out = io.StringIO()
    stop = threading.Event()
    ready = threading.Event()
    holder = {}

    def on_ready(printer):
        holder['printer'] = printer
        ready.set()

    thread = threading.Thread(target=sim_main.run, args=('whole_print',),
                              kwargs={'mqtt_port': 0, 'ftps_port': 0, 'step_seconds': 0.05,
                                      'out': out, 'stop': stop, 'ready': on_ready},
                              daemon=True)
    thread.start()
    try:
        assert ready.wait(30)
        sim = holder['printer']
        link = pr.PrinterLink('127.0.0.1', sim.serial, sim.access_code, ports=sim.ports)
        arrived = threading.Condition()

        def on_document():
            with arrived:
                arrived.notify_all()

        link.on_document = on_document
        link.connect()
        try:
            assert sim.wait_for(lambda: bool(sim.logins))
            path = tmp_path / SUFFIXED
            path.write_bytes(CONTENT)
            link.upload(str(path), SUFFIXED)
            assert link.start(SUFFIXED)
            with arrived:      # woken by each status document the steps send
                assert arrived.wait_for(
                    lambda: link.raw_report().get('gcode_state') == 'FINISH', 30)
        finally:
            link.disconnect()
    finally:
        stop.set()
        thread.join(10)
    text = out.getvalue()
    assert f'MQTT {sim.mqtt_port}, FTPS {sim.ftps_port}' in text
    assert '--printer-ports' in text and 'access code 12345678' in text
    assert f'received {SUFFIXED}' in text and "'gcode_state': 'FINISH'" in text
    assert text.rstrip().endswith('stopped')


class TestStoppedAtPrinter(SimTestCase):
    scenario = 'stopped_at_printer'

    def test_a_pause_a_resume_and_a_stop_at_the_printer(self):
        self.run_job()
        states = []
        while self.step():
            states.append(self.link.snapshot())
        self.assertEqual([s['state'] for s in states], [pr.PAUSED, pr.RUNNING, pr.ERROR])
        self.assertEqual(states[0]['stage'], 'paused_by_user')
        self.assertEqual(states[-1]['error'], 'PRINT_ERROR_0300400C')


class FollowedByTheRelay(SimTestCase):
    """Round 2, defect 1: the daemon's snapshots of a print, one per status document, fed
    to the relay. A wait for a person is never an end."""

    def follow(self):
        relay = PrinterRelay(clock=FakeClock())
        code = '7K3MQ9XW'
        relay.note_code(code)
        relay.note_daemon(code)
        relay.store_status(code, self.link.snapshot())
        relay.claim_job(code, job_id='j8f3a2c1', download_path='/d',
                        filename=JOB['filename'], team_number=None)
        relay.store_status(code, self.link.snapshot())
        (ok, _reason), _code = self.run_job()
        self.assertTrue(ok)
        relay.finish_job(code, 'j8f3a2c1', ok=True, reason=None)
        reports = []
        while self.step():
            relay.store_status(code, self.link.snapshot())
            reports.append(relay.delivery_report(code, 'j8f3a2c1'))
        return reports

    def assert_waits_then_finishes(self, waiting_for, error=None):
        reports = self.follow()
        stages = [(r['state'], r['stage']) for r in reports]
        self.assertIn(('running', 'waiting_for_person'), stages)
        waits = [r for r in reports if r['stage'] == 'waiting_for_person']
        self.assertEqual({r['waiting_for'] for r in waits}, set(waiting_for))
        self.assertTrue(all(r['at_the_printer'] for r in waits))
        if error is not None:
            self.assertIn(error, {r.get('printer_error') for r in waits})
        after = stages[stages.index(('running', 'waiting_for_person')):]
        self.assertIn(('running', 'printing'), after)       # it resumed
        self.assertEqual(reports[-1]['state'], 'done')
        return waits


class TestPauseAndResume(FollowedByTheRelay):
    scenario = 'pause_resume'

    def test_a_pause_at_the_printer_is_a_wait_and_the_print_ends_done(self):
        self.assert_waits_then_finishes(['paused_by_user'])


class TestAnErrorThatClears(FollowedByTheRelay):
    scenario = 'error_clears'

    def test_an_error_code_and_a_serious_entry_that_clear_end_done(self):
        waits = self.assert_waits_then_finishes(['printer_error'], 'PRINT_ERROR_07008011')
        self.assertIn('HMS_0700_8000_0002_0001', {w.get('printer_error') for w in waits})


class TestFilamentRunout(FollowedByTheRelay):
    scenario = 'filament_runout'

    def test_out_of_filament_is_a_wait_with_its_meaning_and_the_print_ends_done(self):
        waits = self.assert_waits_then_finishes(['paused_filament_runout'],
                                                'PRINT_ERROR_07008011')
        self.assertEqual(waits[0]['printer_error_meaning'], 'the filament ran out')


class TestCoverOpen(FollowedByTheRelay):
    scenario = 'cover_open'

    def test_an_open_cover_is_a_wait_and_the_print_ends_done(self):
        waits = self.assert_waits_then_finishes(['paused_cover_open'], 'PRINT_ERROR_0500400E')
        self.assertTrue(waits[0]['at_the_printer'].startswith('Close the front cover'))


class TestAnErrorThatEndsThePrint(FollowedByTheRelay):
    scenario = 'error_mid_print'

    def test_the_printers_failed_state_ends_the_job_failed_with_its_code(self):
        reports = self.follow()
        self.assertEqual(reports[-1]['state'], 'failed')
        self.assertEqual(reports[-1]['error']['code'], 'delivery.print_failed')
        self.assertIn('PRINT_ERROR_07008011', reports[-1]['error']['detail'])
        # The informational entry before it never made the printer wait.
        self.assertNotIn('waiting_for_person', [r['stage'] for r in reports])


class TestAccessAndAddress(SimTestCase):
    def test_the_wrong_access_code_reads_as_unreachable_and_the_job_says_so(self):
        self.link.disconnect()
        link = self.connect('00000000')
        self.link = link
        self.assertTrue(self.sim.wait_for(lambda: ('mqtt', False) in self.sim.logins))
        self.assertEqual(link.snapshot()['state'], pr.UNREACHABLE)
        (ok, reason), code = self.run_job()
        self.assertEqual(code, 'delivery.printer_unreachable_at_start')
        self.assertEqual(self.sim.files, {})

    def test_a_printer_at_a_new_address_reads_as_unreachable(self):
        closed = SimulatedPrinter('whole_print').start()
        ports = closed.ports
        closed.stop()
        link = self.connect(self.access_code, ports=ports)
        self.assertEqual(link.snapshot()['state'], pr.UNREACHABLE)


class TestRecording(SimTestCase):
    def test_a_recording_of_the_simulated_print_plays_back_as_a_scenario(self):
        from penguin_delivery_daemon import __main__ as main_mod
        from penguin_delivery_daemon import config as cfg
        home = os.path.join(self.tmp, 'home')
        cfg.save_config(cfg.DaemonConfig(printer_ip='127.0.0.1', printer_serial=self.sim.serial,
                                         access_code=self.access_code,
                                         pairing_code='7K3MQ9XW'),
                        path=os.path.join(home, 'config.toml'))
        self.run_job()
        out = os.path.join(self.tmp, 'rec.jsonl')
        args = main_mod.build_parser().parse_args(['record', '--home', home, '--out', out,
                                                   '--seconds', '20'])

        def sleep(seconds):
            self.clock.sleep(seconds)
            self.step()

        class AlreadyConnected:
            """The test's own link, so its message callback keeps reporting arrivals."""
            raw_report = self.link.raw_report

            def connect(self):
                pass

            def disconnect(self):
                pass

        assert main_mod.cmd_record(args, clock=self.clock, sleep=sleep,
                                   link=AlreadyConnected()) == 0
        documents = read_recording(out)
        self.assertEqual(documents[-1]['gcode_state'], 'FINISH')
        self.assertGreaterEqual(len(documents), 4)
        replay = SimulatedPrinter({**load_scenario('whole_print'), 'print': documents})
        self.assertEqual(replay.scenario['print'][-1]['mc_percent'], 100)
        with open(out, encoding='utf-8') as fh:
            self.assertNotIn(self.access_code, fh.read())


def test_every_scenario_loads_and_says_what_is_invented():
    for name in scenario_names():
        scenario = load_scenario(name)
        assert 'idle' in scenario and 'print' in scenario, name
        assert scenario['description'], name
