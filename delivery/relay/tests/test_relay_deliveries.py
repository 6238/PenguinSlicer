"""Delivery jobs through the relay's routes: progress reports from the send to the end of
the print, the stream, staleness, the start gate, cancellation, the outcomes of a print,
a relay restart, the sweep of expired records and the spool, the log lines, and caller
functions that answer with the wrong type.

The daemon is played by plain requests to its routes; the clock is a FakeClock."""
import io
import json
import os

import pytest

from penguin_delivery_relay import SlicedFile, Team, relay_of
from penguin_delivery_relay import deliveries as dl
from penguin_delivery_relay import relay as relay_module
from penguin_delivery_relay import routes

from daemon_fakes import SimulatedTimeExceeded
from relay_fakes import CODE, IDLE, Caller, FakeClock, make_app, running

HTTPS = {'base_url': 'https://relay.test'}
#: How long the guide says a final delivery job's report is kept (round 3, defect 5).
A_DAY = 24 * 60 * 60
JOB_FILE = 'sample_part.gcode.3mf'


def assert_progress_shape(report):
    """contracts/progress-report.md: the required fields, a contract state, a known stage."""
    for field, kind in (('job', str), ('state', str), ('elapsed_s', (int, float)),
                        ('sequence', int)):
        assert isinstance(report[field], kind), field
    assert report['state'] in {'queued', 'running', 'done', 'failed', 'cancelled'}
    assert report['stage'] in dl.STAGE_LABELS
    if 'fraction' in report:
        assert 0.0 <= report['fraction'] <= 1.0
    assert ('error' in report) == (report['state'] == 'failed')


def bounded_stream(wait, calls=100):
    """A progress stream's wait that fails the test after `calls` waits: a stream that never
    reaches a final state ends the test with a message instead of running for ever."""
    count = [0]

    def call(code, job_id, after_sequence, timeout):
        count[0] += 1
        if count[0] > calls:
            raise SimulatedTimeExceeded(f'the progress stream waited {calls} times and its '
                                        'delivery job never reached a final state')
        return wait(code, job_id, after_sequence, timeout)
    return call


class Shop:
    """A relay with a paired daemon and a caller, driven through the routes. A progress
    stream's wait never waits: it reads the latest report, at most 100 times."""

    def __init__(self, tmp_path, **app_overrides):
        self.tmp_path = tmp_path
        self.clock = FakeClock()
        self.caller = Caller()
        app_overrides['stream_wait'] = bounded_stream(app_overrides.get('stream_wait') or (
            lambda code, job_id, after, timeout: self.relay.delivery_report(code, job_id)))
        self.app = make_app(self.caller, self.clock, spool_dir=str(tmp_path / 'spool'),
                            **app_overrides)
        self.relay = relay_of(self.app).relay
        self.client = self.app.test_client()
        self.headers = {'Authorization':
                        f"Bearer {relay_module.issue_token(CODE, 'test-secret-key')}"}
        self.relay.note_code(CODE)
        self.sync(IDLE)

    # the daemon's side
    def sync(self, snapshot, progress=None):
        body = dict(snapshot)
        if progress is not None:
            body['job_progress'] = progress
        resp = self.client.post('/printer/daemon/sync', json=body, headers=self.headers,
                                **HTTPS)
        assert resp.status_code == 200
        return resp.get_json()['job']

    def ack(self, job_id, ok, **fields):
        return self.client.post(f'/printer/daemon/jobs/{job_id}/ack',
                                json={'ok': ok, **fields}, headers=self.headers, **HTTPS)

    def start(self, job_id, instance='daemon-1'):
        return self.client.post(f'/printer/daemon/jobs/{job_id}/start',
                                json={'instance': instance}, headers=self.headers, **HTTPS)

    # the caller's side
    def send(self, content=b'3mf-bytes'):
        self.caller.offer(self.tmp_path, content=content)
        resp = self.client.post('/printer/jobs', json={'token': 'tok'})
        assert resp.status_code == 202, resp.get_json()
        return resp.get_json()['job_id']

    def report(self, job_id):
        resp = self.client.get(f'/printer/jobs/{job_id}')
        assert resp.status_code == 200, resp.get_json()
        report = resp.get_json()
        assert_progress_shape(report)
        return report

    def cancel(self, job_id):
        return self.client.post(f'/printer/jobs/{job_id}/cancel')

    def printing(self, job_id, **fields):
        """The H2S's snapshot of our job, as the daemon maps it."""
        snapshot = running(f'sample_part-{job_id}', percent=fields.pop('percent', 42))
        snapshot.update(job_name=f'sample_part-{job_id}', stage='printing',
                        stage_label='Printing', stage_code=0)
        snapshot.update(fields)
        return snapshot

    def through_to_printing(self):
        job_id = self.send()
        self.sync(IDLE)
        self.sync(IDLE, {'id': job_id, 'stage': 'downloading'})
        self.sync(IDLE, {'id': job_id, 'stage': 'uploading', 'bytes_sent': 50,
                         'bytes_total': 100})
        assert self.start(job_id).get_json() == {'start': True, 'outcome': 'start'}
        assert self.ack(job_id, True).status_code == 200
        return job_id


@pytest.fixture
def shop(tmp_path):
    return Shop(tmp_path)


# --- progress through a whole delivery job ----------------------------------------------

class TestProgress:
    def test_a_whole_delivery_job_reports_every_stage_in_order(self, shop):
        job_id = shop.send()
        seen = [shop.report(job_id)]
        assert (seen[0]['state'], seen[0]['stage']) == ('queued', 'waiting_for_daemon')
        shop.clock.advance(2)
        shop.sync(IDLE)
        shop.sync(IDLE, {'id': job_id, 'stage': 'downloading'})
        seen.append(shop.report(job_id))
        shop.sync(IDLE, {'id': job_id, 'stage': 'uploading', 'bytes_sent': 25,
                         'bytes_total': 100})
        seen.append(shop.report(job_id))
        shop.start(job_id)
        seen.append(shop.report(job_id))
        shop.ack(job_id, True)
        shop.sync(shop.printing(job_id, percent=0, stage='heating_bed',
                                stage_label='Heating the bed', layer=0, layers=50,
                                remaining_min=17))
        seen.append(shop.report(job_id))
        shop.sync(shop.printing(job_id, percent=60, layer=30, layers=50, remaining_min=7))
        seen.append(shop.report(job_id))
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        seen.append(shop.report(job_id))
        assert [(r['state'], r['stage']) for r in seen] == [
            ('queued', 'waiting_for_daemon'), ('running', 'downloading'),
            ('running', 'uploading'), ('running', 'starting'), ('running', 'printing'),
            ('running', 'printing'), ('done', 'printing')]
        assert seen[2]['bytes_sent'] == 25 and seen[2]['bytes_total'] == 100
        assert seen[2]['fraction'] == pytest.approx(0.035)
        assert seen[4]['printer_stage'] == 'heating_bed'
        assert seen[4]['printer_stage_label'] == 'Heating the bed'
        assert (seen[5]['percent'], seen[5]['layer'], seen[5]['total_layers'],
                seen[5]['remaining_min']) == (60, 30, 50, 7)
        assert seen[5]['fraction'] == pytest.approx(0.64)
        assert seen[5]['expected_s'] == pytest.approx(seen[5]['elapsed_s'] + 420)
        assert seen[6]['fraction'] == 1.0
        sequences = [r['sequence'] for r in seen]
        assert sequences == sorted(set(sequences))
        assert seen[1]['elapsed_s'] == 0.0      # running starts at the hand-out

    def test_a_repeated_identical_sync_is_not_a_new_report(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id))
        first = shop.report(job_id)['sequence']
        shop.sync(shop.printing(job_id))
        assert shop.report(job_id)['sequence'] == first

    def test_the_status_route_carries_the_latest_report(self, shop):
        job_id = shop.send()
        body = shop.client.get('/printer/status').get_json()
        assert body['delivery']['job'] == job_id
        assert body['delivery']['state'] == 'queued'

    def test_a_late_caller_gets_the_latest_report_at_once_from_the_stream(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(dict(shop.printing(job_id), state='finished'))
        resp = shop.client.get(f'/printer/jobs/{job_id}/events')
        assert resp.mimetype == 'text/event-stream'
        frames = resp.get_data(as_text=True).split('\n\n')
        data = json.loads(frames[0].split('data: ', 1)[1])
        assert data['state'] == 'done'
        assert frames[0].startswith(f"id: {data['sequence']}\nevent: progress\n")
        assert frames[1:] == ['']               # a final state ends the stream

    def test_the_stream_sends_each_new_report_and_ends_after_the_final_one(self, tmp_path):
        """The stream's wait is scripted: each call moves the delivery job on one step, so
        the stream runs with no waiting at all."""
        steps = []

        def scripted_wait(code, job_id, after_sequence, timeout):
            assert timeout == routes.STREAM_HEARTBEAT_SECONDS
            if steps:
                steps.pop(0)()
            return shop.relay.delivery_report(code, job_id)

        shop = Shop(tmp_path, stream_wait=scripted_wait)
        job_id = shop.send()
        steps.extend([
            lambda: shop.sync(IDLE),
            lambda: None,                               # nothing new: a heartbeat
            lambda: shop.sync(IDLE, {'id': job_id, 'stage': 'downloading'}),
            lambda: shop.cancel(job_id),
            lambda: shop.ack(job_id, False, code='delivery.cancelled', error='cancelled'),
        ])
        text = shop.client.get(f'/printer/jobs/{job_id}/events').get_data(as_text=True)
        frames = [f for f in text.split('\n\n') if f]
        kinds = [('beat' if f.startswith(':') else json.loads(f.split('data: ', 1)[1])['state'])
                 for f in frames]
        # queued, running (hand-out), beat, downloading, cancel requested, cancelled
        assert kinds == ['queued', 'running', 'beat', 'running', 'running', 'cancelled']
        assert json.loads(frames[4].split('data: ', 1)[1])['cancel_requested'] is True

    def test_a_stream_whose_delivery_job_is_dropped_ends_with_an_error_report(self, tmp_path):
        def dropped(code, job_id, after_sequence, timeout):
            return None

        shop = Shop(tmp_path, stream_wait=dropped)
        job_id = shop.send()
        frames = [f for f in shop.client.get(f'/printer/jobs/{job_id}/events')
                  .get_data(as_text=True).split('\n\n') if f]
        assert frames[-1].startswith('event: error\n')
        assert json.loads(frames[-1].split('data: ', 1)[1])['code'] == 'delivery.job_unknown'

    def test_the_relays_own_wait_wakes_on_a_change(self, shop):
        """The default wait is the relay's condition: real threads, no sleeping."""
        import threading
        job_id = shop.send()
        seq = shop.report(job_id)['sequence']
        got = {}
        ready = threading.Event()

        def waiter():
            ready.set()
            # Far longer than the join below: only a wake ends this wait in time, so a
            # change that wakes nothing fails the test instead of timing out into a pass.
            got['report'] = shop.relay.wait_for_report(CODE, job_id, seq, timeout=3600)

        thread = threading.Thread(target=waiter, daemon=True)
        thread.start()
        assert ready.wait(10), 'the waiting thread never started'
        # The waiter may not be waiting yet; any change after it starts wakes it, and a
        # change before it waits is seen by its first check.
        shop.sync(IDLE)
        thread.join(timeout=5)
        assert not thread.is_alive(), 'the change did not wake the waiting stream'
        assert got['report']['sequence'] > seq
        # A final job never waits.
        shop.cancel(job_id)
        shop.ack(job_id, False, code='delivery.cancelled')
        assert shop.relay.wait_for_report(CODE, job_id, 0, timeout=30)['state'] == 'cancelled'

    def test_the_relays_own_wait_times_out_with_the_unchanged_report(self, shop):
        """Nothing changes: the wait ends at its timeout (zero here, so no real waiting)
        and answers the same report."""
        job_id = shop.send()
        before = shop.report(job_id)
        after = shop.relay.wait_for_report(CODE, job_id, before['sequence'], timeout=0)
        assert after['sequence'] == before['sequence']

    def test_a_delivery_job_of_another_team_is_unknown(self, shop, tmp_path):
        job_id = shop.send()
        shop.caller.team = Team(pairing_code='ABCD2345', team_number=1)
        resp = shop.client.get(f'/printer/jobs/{job_id}')
        assert resp.status_code == 404
        assert resp.get_json()['error_report']['code'] == 'delivery.job_unknown'
        assert shop.client.post(f'/printer/jobs/{job_id}/cancel').status_code == 404
        assert shop.client.get(f'/printer/jobs/{job_id}/events').status_code == 404

    def test_the_delivery_routes_need_an_identity(self, shop):
        job_id = shop.send()
        shop.caller.team = None
        for resp in (shop.client.get(f'/printer/jobs/{job_id}'),
                     shop.client.get(f'/printer/jobs/{job_id}/events'),
                     shop.client.post(f'/printer/jobs/{job_id}/cancel')):
            assert resp.status_code == 401
            assert resp.get_json()['error_report']['code'] == 'delivery.no_session'

    def test_the_delivery_routes_are_rate_limited_with_an_error_report(self, shop):
        job_id = shop.send()
        for _ in range(routes.STATUS_LIMIT.count):
            shop.client.get(f'/printer/jobs/{job_id}')
        resp = shop.client.get(f'/printer/jobs/{job_id}')
        assert resp.status_code == 429
        assert resp.get_json()['error_report']['code'] == 'delivery.rate_limited'

    def test_a_daemon_progress_report_for_an_unknown_stage_or_job_is_ignored(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        before = shop.report(job_id)
        shop.sync(IDLE, {'id': job_id, 'stage': 'printing'})    # the relay's to decide
        shop.sync(IDLE, {'id': job_id, 'stage': 'melting'})
        shop.sync(IDLE, {'id': 'jffffffff', 'stage': 'downloading'})
        shop.sync(IDLE, {'id': job_id, 'stage': 'uploading', 'bytes_sent': 'x',
                         'bytes_total': 0})
        after = shop.report(job_id)
        assert after['stage'] == 'uploading' and 'fraction' not in after
        assert before['stage'] == 'waiting_for_daemon'


class TestStaleness:
    def test_a_quiet_daemon_marks_the_report_stale_with_its_age_and_clears_on_return(
            self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=10))
        fresh = shop.report(job_id)
        assert 'stale' not in fresh
        shop.clock.advance(dl.STALE_AFTER_SECONDS + 5)
        stale = shop.report(job_id)
        assert stale['stale'] is True and stale['stale_age_s'] == dl.STALE_AFTER_SECONDS + 5
        assert stale['sequence'] == fresh['sequence'] + 1     # a new report says so
        assert stale['percent'] == 10                         # the old figure, marked old
        shop.clock.advance(10)
        assert shop.report(job_id)['stale_age_s'] == dl.STALE_AFTER_SECONDS + 15
        shop.sync(shop.printing(job_id, percent=11))
        back = shop.report(job_id)
        assert 'stale' not in back and back['percent'] == 11

    def test_a_printer_whose_report_stopped_changing_marks_the_print_stale(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, report_age_s=dl.PRINTER_QUIET_SECONDS + 1))
        report = shop.report(job_id)
        assert report['stale'] is True
        assert report['stale_age_s'] == dl.PRINTER_QUIET_SECONDS + 1

    def test_an_unreachable_printer_during_a_print_does_not_fail_it(self, shop):
        """Seems down, then recovers: the print goes on."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30))
        for _ in range(10):
            shop.clock.advance(60)
            shop.sync(dict(IDLE, state='unreachable'))
        assert shop.report(job_id)['state'] == 'running'
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        assert shop.report(job_id)['state'] == 'done'

    def test_a_print_nothing_is_heard_about_stays_running_and_stale_for_a_day(self, shop):
        """Silence is not an end: for a day with no word the job is running and stale,
        then the printer's report of the finished print makes it done."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30))
        for _ in range(23):
            shop.clock.advance(3600)
            shop.relay.note_code(CODE)                # the caller still presents the code
            report = shop.report(job_id)
            assert (report['state'], report['stale']) == ('running', True)
        assert report['stale_age_s'] == 23 * 3600
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        assert shop.report(job_id)['state'] == 'done'

    def test_a_day_with_no_fresh_word_past_the_gate_ends_with_the_outcome_unknown(
            self, shop):
        """Defect 3: a caller that keeps polling never let the record go; now a day of
        continuous staleness past the start gate ends the job, saying the outcome is not
        known, never that the print failed. The job slot is free afterwards."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30))
        shop.clock.advance(dl.OUTCOME_UNKNOWN_AFTER_SECONDS - 1)
        shop.relay.note_code(CODE)
        assert shop.report(job_id)['state'] == 'running'
        shop.clock.advance(1)
        report = shop.report(job_id)
        assert report['state'] == 'failed'
        error = report['error']
        assert error['code'] == 'delivery.outcome_unknown'
        assert error['message'] == (
            'Contact with the printer was lost after this print was handed over to be '
            'started, so the printer service cannot tell whether it is printing, has '
            'finished or never started.')
        assert 'fail' not in error['message']
        assert error['retryable'] is False
        assert 'the relay stopped following it after 24 h' in error['detail']
        # The finished print reported later changes nothing: no report after a final one.
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        assert shop.report(job_id) == report

    @pytest.mark.parametrize('every', [1, 5, 7, 15, 30, 60, 600, 3600])
    @pytest.mark.parametrize('silent_from', ['after_the_gate', 'mid_print'])
    def test_polling_only_the_job_route_across_the_day_sees_the_outcome_unknown(
            self, tmp_path, every, silent_from):
        """Round 3, defect 5: nobody presents the pairing code, so the printer's record
        expires around the same moment as the 24-hour rule; whichever comes first, a
        caller polling only GET /printer/jobs/<id>, at any interval, sees the delivery job
        end with `delivery.outcome_unknown`, and goes on seeing it for a day."""
        shop = Shop(tmp_path)
        if silent_from == 'after_the_gate':
            job_id = shop.send()
            shop.sync(IDLE)
            assert shop.start(job_id).get_json()['outcome'] == 'start'
        else:
            job_id = shop.through_to_printing()
            shop.sync(shop.printing(job_id, percent=30))
        # Polls long before the mark change nothing (the record is not touched, the job is
        # stale and not yet a day old): jump to a window before it, then poll at `every`.
        window = max(600, 2 * every)
        shop.clock.advance(dl.OUTCOME_UNKNOWN_AFTER_SECONDS - window)
        assert shop.client.get(f'/printer/jobs/{job_id}').get_json()['state'] == 'running'
        seen = []
        for _ in range(int((window + 3 * relay_module.SWEEP_EVERY_SECONDS) // every) + 2):
            shop.clock.advance(every)
            resp = shop.client.get(f'/printer/jobs/{job_id}')
            assert resp.status_code == 200, (shop.clock.now, resp.get_json())
            seen.append(resp.get_json()['state'])
            if seen[-1] != 'running':
                break
        report = shop.report(job_id)
        assert (report['state'], report['error']['code']) == ('failed',
                                                              'delivery.outcome_unknown')
        # The stated time, a day, not whatever the constant says.
        shop.clock.advance(A_DAY - relay_module.SWEEP_EVERY_SECONDS)
        shop.relay.sweep()
        assert shop.report(job_id) == report                  # kept for a day ...
        shop.clock.advance(2 * relay_module.SWEEP_EVERY_SECONDS)
        shop.relay.sweep()
        assert shop.client.get(f'/printer/jobs/{job_id}').status_code == 404   # ... then gone

    def test_every_final_state_is_kept_a_day_for_a_slow_poller(self, shop):
        """Round 3, defect 5, for every other final state."""
        done = shop.through_to_printing()
        shop.sync(dict(shop.printing(done, percent=100), state='finished'))
        cancelled = shop.send()
        assert shop.cancel(cancelled).status_code == 200
        failed = shop.send()
        shop.clock.advance(relay_module.JOB_PENDING_TIMEOUT_SECONDS + 1)
        shop.relay.note_code(CODE)
        expected = {done: 'done', cancelled: 'cancelled', failed: 'failed'}
        assert {job: shop.report(job)['state'] for job in expected} == expected
        shop.clock.advance(A_DAY - relay_module.JOB_PENDING_TIMEOUT_SECONDS
                           - 2 * relay_module.SWEEP_EVERY_SECONDS)
        shop.relay.sweep()
        assert {job: shop.report(job)['state'] for job in expected} == expected

    def test_a_followed_print_under_an_unrecognised_state_is_stale_and_can_be_given_up(
            self, shop):
        """Round 3, defect 1: a main state the daemon does not know never ends or vanishes
        a print, and counts as stale so the caller is never locked in."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30))
        unknown = dict(IDLE, state='unrecognised', unrecognised="gcode_state 'SLICING'",
                       report_age_s=0)
        for _ in range(5):
            shop.clock.advance(60)
            shop.sync(unknown)
        report = shop.report(job_id)
        assert (report['state'], report['stage'], report['stale']) == ('running', 'printing',
                                                                       True)
        assert report['percent'] == 30                        # the last figures, kept
        assert report['unrecognised'] == "gcode_state 'SLICING'"
        resp = shop.client.post(f'/printer/jobs/{job_id}/stop-following')
        assert resp.status_code == 200
        assert resp.get_json()['progress']['error']['code'] == 'delivery.outcome_unknown'

    def test_a_followed_print_whose_printer_goes_idle_with_an_odd_stage_vanishes(self, shop):
        """Round 3, defect 1: IDLE with stage -1 and our file still named is no print, so
        the delivery job does not stay `printing` for ever."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30))
        idle = dict(IDLE, file=f'sample_part-{job_id}', job_name=f'sample_part-{job_id}',
                    stage_code=-1, stage='stage_-1', unrecognised="stg_cur '-1'",
                    report_age_s=0)
        for _ in range(int(dl.PRINT_VANISH_SECONDS // 5) + 2):
            shop.clock.advance(5)
            shop.sync(idle)
        assert shop.report(job_id)['error']['code'] == 'delivery.print_vanished'

    def test_the_day_counts_only_continuous_staleness(self, shop):
        """Fresh word in between starts the day again."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30))
        shop.clock.advance(dl.OUTCOME_UNKNOWN_AFTER_SECONDS - 60)
        shop.sync(shop.printing(job_id, percent=31))           # word again
        shop.report(job_id)
        shop.clock.advance(dl.OUTCOME_UNKNOWN_AFTER_SECONDS - 60)
        shop.relay.note_code(CODE)
        report = shop.report(job_id)
        assert (report['state'], report['stale']) == ('running', True)

    def test_a_day_of_staleness_ends_the_job_even_when_nobody_asks(self, shop):
        """The sweep applies the day to a job nobody reads: the next request of any kind
        (here another team's status poll, which sweeps) ends it before its record goes,
        and a late caller still gets the report for an hour."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30))
        shop.clock.advance(dl.OUTCOME_UNKNOWN_AFTER_SECONDS + 3600)
        shop.relay.sweep()
        assert shop.relay.counts()['records'] == 0          # the record went too
        report = shop.report(job_id)
        assert (report['state'], report['error']['code']) == ('failed',
                                                              'delivery.outcome_unknown')

    def test_before_the_gate_a_day_of_staleness_is_left_to_the_job_slot_deadlines(
            self, shop):
        job_id = shop.send()
        shop.sync(IDLE)                                     # handed out, never asked to start
        shop.clock.advance(relay_module.JOB_HANDED_OUT_TIMEOUT_SECONDS + 1)
        assert shop.report(job_id)['error']['code'] == 'delivery.job_not_confirmed'

    def test_an_unreachable_printer_during_a_print_is_stale_at_once_with_its_true_age(
            self, shop):
        """Old figures are never shown as fresh: the first sync that finds the printer
        unreachable marks the report stale, aged from the printer's last document."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30, remaining_min=17))
        shop.clock.advance(5)
        shop.sync(dict(IDLE, state='unreachable', report_age_s=5))
        report = shop.report(job_id)
        assert report['stale'] is True and report['stale_age_s'] == 5
        assert (report['state'], report['percent']) == ('running', 30)
        shop.sync(shop.printing(job_id, percent=31, report_age_s=0))
        assert 'stale' not in shop.report(job_id)

    def test_a_printer_that_cannot_be_reached_after_the_start_marks_the_start_stale(
            self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        shop.sync(dict(IDLE, state='unreachable', report_age_s=12),
                  {'id': job_id, 'stage': 'starting'})
        report = shop.report(job_id)
        assert (report['stage'], report['stale'], report['stale_age_s']) == \
            ('starting', True, 12)

    def test_the_daemons_word_without_the_printers_keeps_the_marker_steady(self, shop):
        """Each sync from a daemon that cannot reach the printer is not a new report."""
        job_id = shop.through_to_printing()
        shop.sync(dict(IDLE, state='unreachable'))
        first = shop.report(job_id)
        for _ in range(5):
            shop.clock.advance(5)
            shop.sync(dict(IDLE, state='unreachable'))
        assert shop.report(job_id)['sequence'] == first['sequence']


class TestPrintOutcomes:
    def test_an_error_code_that_ends_the_print_fails_it_with_the_meaning(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, state='error', error='PRINT_ERROR_07008011',
                                percent=40))
        report = shop.report(job_id)
        assert report['state'] == 'failed'
        assert report['error']['code'] == 'delivery.print_failed'
        assert report['error']['message'] == (
            'The print failed partway through: the filament ran out.')
        assert 'PRINT_ERROR_07008011' in report['error']['detail']

    def test_an_unknown_error_code_is_still_a_truthful_report_with_the_code_kept(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, state='error', error='HMS_9999_0000_0001_0001'))
        error = shop.report(job_id)['error']
        assert error['message'] == 'The print failed partway through.'
        assert 'HMS_9999_0000_0001_0001' in error['detail']

    def test_a_stop_at_the_printer_is_reported_as_stopped(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, state='error', error='PRINT_ERROR_0300400C'))
        error = shop.report(job_id)['error']
        assert error['code'] == 'delivery.print_stopped'

    def test_an_error_that_clears_is_not_a_failure_until_it_ends_the_print(self, shop):
        """An HMS entry that does not stop the print leaves the state running."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, error='HMS_0300_0100_0004_0001', percent=20))
        shop.sync(shop.printing(job_id, error=None, percent=21))
        assert shop.report(job_id)['state'] == 'running'

    def test_a_pause_and_resume_at_the_printer_keeps_the_job_running(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, state='paused', stage='paused_by_user',
                                stage_label='Paused at the printer'))
        paused = shop.report(job_id)
        assert (paused['state'], paused['printer_stage']) == ('running', 'paused_by_user')
        shop.sync(shop.printing(job_id))
        assert shop.report(job_id)['printer_stage'] == 'printing'

    def test_percent_going_backwards_is_reported_as_the_printer_said(self, shop):
        """Never invented: a backwards or jumping figure is passed on, not smoothed."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=50))
        shop.sync(shop.printing(job_id, percent=20))
        assert shop.report(job_id)['percent'] == 20
        shop.sync(shop.printing(job_id, percent=95))
        assert shop.report(job_id)['percent'] == 95

    def test_fields_missing_from_the_snapshot_are_left_out_not_invented(self, shop):
        job_id = shop.through_to_printing()
        shop.sync({'state': 'running', 'job_name': f'sample_part-{job_id}'})
        report = shop.report(job_id)
        assert report['state'] == 'running'
        for field in ('percent', 'layer', 'total_layers', 'remaining_min', 'fraction'):
            assert field not in report

    def test_a_print_the_printer_stops_naming_vanishes_after_the_grace(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id))
        shop.sync(IDLE)                                        # a flicker: not yet
        shop.clock.advance(dl.PRINT_VANISH_SECONDS - 1)
        shop.sync(IDLE)
        assert shop.report(job_id)['state'] == 'running'
        shop.clock.advance(1)
        shop.sync(IDLE)
        report = shop.report(job_id)
        assert report['state'] == 'failed'
        assert report['error']['code'] == 'delivery.print_vanished'

    def test_a_flicker_shorter_than_the_grace_keeps_the_print(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(IDLE)
        shop.clock.advance(dl.PRINT_VANISH_SECONDS - 1)
        shop.sync(shop.printing(job_id))
        shop.clock.advance(dl.PRINT_VANISH_SECONDS)
        shop.sync(shop.printing(job_id))
        assert shop.report(job_id)['state'] == 'running'

    def test_no_report_after_a_final_state(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(dict(shop.printing(job_id), state='finished'))
        done = shop.report(job_id)
        shop.sync(shop.printing(job_id, state='error', error='PRINT_ERROR_07008011'))
        shop.clock.advance(6 * 3600)
        assert shop.report(job_id) == done

    def test_a_printer_idle_but_still_naming_the_file_ends_the_job_as_vanished(self, shop):
        """The printer went back to idle without a finish or an error: after the grace,
        the job ends with an error report instead of showing the print forever."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=40))
        idle_naming_ours = dict(shop.printing(job_id, percent=40), state='idle')
        shop.sync(idle_naming_ours)
        shop.clock.advance(dl.PRINT_VANISH_SECONDS)
        shop.sync(idle_naming_ours)
        report = shop.report(job_id)
        assert report['state'] == 'failed'
        assert report['error']['code'] == 'delivery.print_vanished'
        assert report['error']['message'] == (
            'The printer stopped reporting this print without saying it finished.')
        assert "'idle'" in report['error']['detail']

    def test_a_huge_detail_from_the_daemon_is_cut_everywhere_it_travels(self, shop):
        """Nothing proportional to a sliced file's size reaches a report, a status answer
        or a log line, whatever the daemon sends."""
        job_id = shop.send()
        shop.sync(IDLE)
        huge = 'x' * 15_000              # three of them stay under the body limit
        assert shop.ack(job_id, False, code='delivery.upload_failed', error=huge,
                        detail=huge, fields={'name': huge, 'seconds': 60, 'junk': huge}
                        ).status_code == 200
        report = shop.report(job_id)
        assert len(report['error']['detail']) <= 2000
        assert report['error']['detail'].endswith('more characters cut]')
        status = shop.client.get('/printer/status').get_json()
        assert len(json.dumps(status)) < 10_000
        assert len(json.dumps(report)) < 10_000
        assert max(len(line) for line in shop.caller.logged) < 10_000
        assert max(len(json.dumps(fields, default=str))
                   for _kind, fields in shop.caller.events) < 10_000

    def test_a_daemon_failure_code_becomes_the_error_report(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        shop.ack(job_id, False, code='delivery.upload_failed',
                 error='the printer has 10 of 99 bytes', detail='426 Failure reading')
        report = shop.report(job_id)
        assert report['state'] == 'failed'
        assert report['error']['code'] == 'delivery.upload_failed'
        assert report['error']['detail'] == '426 Failure reading'
        last = shop.client.get('/printer/status').get_json()['last_result']
        assert last['error_report'] == report['error']


# --- the start gate and cancellation -------------------------------------------------------

class TestStartGateAndCancel:
    def test_the_start_is_granted_to_one_daemon_process_only(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        assert shop.start(job_id, 'daemon-1').get_json()['outcome'] == 'start'
        assert shop.start(job_id, 'daemon-1').get_json()['outcome'] == 'start'  # repeated
        assert shop.start(job_id, 'daemon-2').get_json() == {'start': False,
                                                             'outcome': 'refused'}
        assert shop.sync(IDLE)['start_granted'] is True

    def test_the_gate_for_a_job_the_relay_does_not_hold_is_404(self, shop):
        assert shop.start('jffffffff').status_code == 404

    @pytest.mark.parametrize('body', [{}, {'instance': ''}, {'instance': '   '},
                                      {'instance': None}, {'instance': 7}])
    def test_a_start_that_names_no_daemon_process_is_refused_and_grants_nothing(
            self, shop, body):
        """Round 3, defect 7: a start nobody could hold to the at-most-once rule."""
        job_id = shop.send()
        shop.sync(IDLE)
        for _ in range(2):
            resp = shop.client.post(f'/printer/daemon/jobs/{job_id}/start', json=body,
                                    headers=shop.headers, **HTTPS)
            assert resp.status_code == 400
            report = resp.get_json()['error_report']
            assert report['code'] == 'delivery.start_without_instance'
            assert report['retryable'] is False
        assert shop.sync(IDLE)['start_granted'] is False
        # A daemon that names itself is granted the start, once.
        assert shop.start(job_id, 'daemon-1').get_json()['outcome'] == 'start'
        assert shop.start(job_id, 'daemon-2').get_json()['outcome'] == 'refused'

    def test_a_job_past_the_gate_whose_printer_record_went_ends_with_the_outcome_unknown(
            self, shop):
        """Round 3, defect 5. In practice the 24-hour rule ends such a job first (fresh
        word touches the record); should the record go anyway, the job still ends."""
        job_id = shop.send()
        shop.sync(IDLE)
        assert shop.start(job_id).get_json()['outcome'] == 'start'
        del shop.relay._records[CODE]                       # the record went, by any route
        shop.clock.advance(relay_module.SWEEP_EVERY_SECONDS + 1)
        shop.relay.sweep()
        report = shop.report(job_id)
        assert (report['state'], report['error']['code']) == ('failed',
                                                              'delivery.outcome_unknown')
        assert 'record expired' in report['error']['detail']

    def test_a_job_whose_starts_named_no_process_ends_at_the_deadline_as_never_started(
            self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        assert shop.relay.grant_start(CODE, job_id, '') == 'no_instance'
        shop.clock.advance(relay_module.JOB_HANDED_OUT_TIMEOUT_SECONDS + 1)
        report = shop.report(job_id)
        assert report['error']['code'] == 'delivery.job_not_confirmed'
        assert report['error']['retryable'] is True

    def test_a_queued_job_is_cancelled_at_once_and_never_handed_out(self, shop):
        job_id = shop.send()
        resp = shop.cancel(job_id)
        assert resp.status_code == 200
        assert resp.get_json()['outcome'] == 'cancelled'
        assert resp.get_json()['progress']['state'] == 'cancelled'
        assert shop.sync(IDLE) is None
        assert len(relay_of(shop.app).files) == 0
        assert shop.client.get('/printer/status').get_json()['last_result']['cancelled']

    def test_a_handed_out_job_is_cancelled_on_the_daemons_next_sync(self, shop):
        job_id = shop.send()
        shop.sync(IDLE, None)
        shop.sync(IDLE, {'id': job_id, 'stage': 'uploading', 'bytes_sent': 1,
                         'bytes_total': 9})
        resp = shop.cancel(job_id)
        assert resp.status_code == 202 and resp.get_json()['outcome'] == 'cancelling'
        report = shop.report(job_id)
        assert report['state'] == 'running' and report['cancel_requested'] is True
        assert shop.sync(IDLE)['cancel'] is True
        assert shop.start(job_id).get_json() == {'start': False, 'outcome': 'cancelled'}
        shop.ack(job_id, False, code='delivery.cancelled', error='cancelled')
        assert shop.report(job_id)['state'] == 'cancelled'
        assert 'error' not in shop.report(job_id)

    def test_cancel_after_the_start_was_granted_is_refused_with_an_error_report(self, shop):
        """Review 4, defect 3: between the gate and the daemon's word that the command went,
        the refusal says the start is being sent, never that the print started."""
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        resp = shop.cancel(job_id)
        assert resp.status_code == 409
        report = resp.get_json()['error_report']
        assert report['code'] == 'delivery.start_being_sent'
        assert 'started' not in report['message']
        assert 'printer' in report['remedy']
        shop.sync(IDLE, {'id': job_id, 'stage': 'starting', 'start_sent': True})
        report = shop.cancel(job_id).get_json()['error_report']
        assert report['code'] == 'delivery.cancel_too_late'
        assert 'start command' in report['message'] and 'sent' in report['message']
        shop.ack(job_id, True)
        assert shop.cancel(job_id).get_json()['error_report']['code'] == \
            'delivery.cancel_too_late'

    def test_a_restarted_daemon_is_told_the_gates_age_and_the_previous_start(self, shop):
        """Review 4, defects 2 and 4: the relay knows when the start gate was passed. A
        re-offered job carries its gate's age; the next job names the printer's last start
        granted, so a restarted daemon can hold the printer until it settles."""
        first = shop.send()
        shop.sync(IDLE)
        shop.start(first)
        shop.clock.advance(42)
        job = shop.sync(IDLE, {'id': first, 'stage': 'start_not_shown', 'waited_s': 42,
                               'start_sent': True})
        assert (job['id'], job['start_granted'], job['start_granted_age_s']) == \
            (first, True, 42)
        assert 'previous_start' not in job
        shop.ack(first, True)
        shop.sync(shop.printing(first, state='finished', percent=100))
        second = shop.send()
        job = shop.sync(IDLE)
        assert job['id'] == second and not job['start_granted']
        assert 'start_granted_age_s' not in job
        assert job['previous_start'] == {'id': first, 'filename': 'sample_part.gcode.3mf',
                                         'age_s': 42}

    def test_an_end_reported_with_our_name_before_the_print_shows_is_left_to_the_daemon(
            self, shop):
        """The relay does not move a job past the gate to `printing` on an end naming its
        file: only a going state does (the daemon tells a left-over end from ours)."""
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        shop.sync(shop.printing(job_id, state='finished', percent=100))
        assert shop.report(job_id)['stage'] == 'starting'
        shop.sync(shop.printing(job_id, state='paused'))
        assert shop.report(job_id)['stage'] == 'waiting_for_person'

    def test_stop_following_while_the_printer_has_not_shown_the_print_says_so(self, shop):
        """Review 4, defect 3: fresh word past the gate, the print not shown yet. The refusal
        is `delivery.start_not_shown_yet`, never "still reporting, so it is running"."""
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        shop.sync(IDLE, {'id': job_id, 'stage': 'start_not_shown', 'start_sent': True,
                         'waited_s': 75})
        report = shop.report(job_id)
        assert (report['stage'], report['waited_s']) == ('start_not_shown', 75)
        assert report['stage_label'] == \
            'The printer has the file and has not shown the print yet'
        resp = shop.client.post(f'/printer/jobs/{job_id}/stop-following')
        assert resp.status_code == 409
        report = resp.get_json()['error_report']
        assert report['code'] == 'delivery.start_not_shown_yet'
        assert 'running' not in report['message']

    def test_cancel_of_a_finished_job_says_so(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(dict(shop.printing(job_id), state='finished'))
        resp = shop.cancel(job_id)
        assert resp.status_code == 409
        assert resp.get_json()['error_report']['code'] == 'delivery.already_finished'

    def test_a_cancel_the_daemon_never_answers_ends_cancelled_at_the_deadline(self, shop):
        """The daemon is unreachable: it can never pass the gate, so the file was never
        started, and the job ends as cancelled rather than as unconfirmed."""
        job_id = shop.send()
        shop.sync(IDLE)
        shop.cancel(job_id)
        shop.clock.advance(relay_module.JOB_HANDED_OUT_TIMEOUT_SECONDS + 1)
        assert shop.report(job_id)['state'] == 'cancelled'

    def test_an_unconfirmed_job_fails_at_the_deadline_and_can_never_start(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        shop.clock.advance(relay_module.JOB_HANDED_OUT_TIMEOUT_SECONDS + 1)
        report = shop.report(job_id)
        assert report['error']['code'] == 'delivery.job_not_confirmed'
        assert report['error']['message'] == (
            'The computer next to the printer collected the print and was then not heard '
            'from for 15 minutes, so the print was given up before it started.')
        assert shop.start(job_id).status_code == 404          # the gate is shut for good

    def test_a_job_past_the_gate_is_never_ended_by_the_deadline(self, shop):
        """Defect 1, route B: the start was granted, then the link was down for 17
        minutes. The job stays in progress (stale), follows the print from the first
        snapshot that names its file, and the daemon's late acknowledgement is taken."""
        job_id = shop.send()
        shop.sync(IDLE)
        assert shop.start(job_id).get_json()['outcome'] == 'start'
        shop.clock.advance(17 * 60)
        report = shop.report(job_id)
        assert (report['state'], report['stage'], report['stale']) == \
            ('running', 'starting', True)
        shop.sync(shop.printing(job_id, percent=12))          # the link is back
        report = shop.report(job_id)
        assert (report['state'], report['stage'], report['percent']) == \
            ('running', 'printing', 12)
        assert 'stale' not in report
        assert shop.ack(job_id, True).status_code == 200      # the queued "ok" lands
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        assert shop.report(job_id)['state'] == 'done'

    def test_a_start_failure_after_the_printer_named_the_file_does_not_end_the_print(
            self, shop):
        """The printer's own report outranks a start-stage failure from the daemon."""
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        shop.sync(shop.printing(job_id, percent=3))
        shop.ack(job_id, False, code='delivery.start_timeout',
                 error='the printer did not start the file within 60s')
        assert shop.report(job_id)['state'] == 'running'
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        assert shop.report(job_id)['state'] == 'done'

    def test_a_silent_job_past_the_gate_ends_unknown_before_its_record_goes(self, shop):
        job_id = shop.through_to_printing()
        shop.clock.advance(relay_module.RECORD_TTL_SECONDS + relay_module.SWEEP_EVERY_SECONDS
                           + 1)
        shop.relay.sweep()
        report = shop.report(job_id)
        assert report['error']['code'] == 'delivery.outcome_unknown'

    def test_a_job_whose_printer_record_went_ends_and_keeps_its_final_report(self, shop):
        """Round 3, defect 5: nobody read anything for a day, so the job slot's deadlines
        never ran; the record goes, and the delivery job ends with a report a slow poller
        can still read, instead of vanishing."""
        cases = (('handed out', lambda: shop.sync(IDLE), 'delivery.job_not_confirmed'),
                 ('never collected', lambda: None, 'delivery.job_not_picked_up'))
        for _name, step, code in cases:
            job_id = shop.send()
            step()
            shop.clock.advance(relay_module.RECORD_TTL_SECONDS
                               + relay_module.SWEEP_EVERY_SECONDS + 1)
            shop.relay.sweep()
            shop.clock.advance(A_DAY - 60)
            report = shop.report(job_id)
            assert (report['state'], report['error']['code']) == ('failed', code)
            assert report['error']['retryable'] is True
            shop.relay.note_code(CODE)
            shop.sync(IDLE)

    def test_a_job_never_picked_up_fails_at_the_deadline(self, shop):
        job_id = shop.send()
        shop.clock.advance(relay_module.JOB_PENDING_TIMEOUT_SECONDS + 1)
        assert shop.report(job_id)['error']['code'] == 'delivery.job_not_picked_up'


# --- restarts, sweeps and the spool ---------------------------------------------------------

class TestRestartsAndCleanup:
    def test_after_a_relay_restart_the_caller_gets_an_error_report_not_silence(self, shop,
                                                                             tmp_path):
        job_id = shop.send()
        shop.sync(IDLE)
        restarted = make_app(shop.caller, shop.clock, spool_dir=str(tmp_path / 'spool'))
        client = restarted.test_client()
        resp = client.get(f'/printer/jobs/{job_id}')
        assert resp.status_code == 404
        assert resp.get_json()['error_report']['code'] == 'delivery.job_unknown'
        # The daemon learns too: the gate and the ack both say the job is unknown.
        assert client.post(f'/printer/daemon/jobs/{job_id}/start', json={},
                           headers=shop.headers, **HTTPS).status_code == 404
        assert client.post(f'/printer/daemon/jobs/{job_id}/ack', json={'ok': True},
                           headers=shop.headers, **HTTPS).status_code == 404

    def test_a_restarted_relay_sweeps_the_orphans_of_the_last_process(self, tmp_path):
        spool = tmp_path / 'spool'
        spool.mkdir()
        orphans = ['j8f3a2c1-abc_123.gcode.3mf', 'j0000001-x.gcode.3mf']
        keep = ['notes.txt', 'jzzzz-x.gcode.3mf', 'caller-file.gcode.3mf']
        for name in orphans + keep:
            (spool / name).write_bytes(b'x')
        caller = Caller()
        make_app(caller, FakeClock(), spool_dir=str(spool))
        assert sorted(os.listdir(spool)) == sorted(keep)
        assert 'printer-delivery event=spool_swept removed=2' in caller.logged

    def test_a_stream_copy_held_by_this_process_is_never_swept(self, tmp_path):
        shop = Shop(tmp_path)
        shop.caller.files['tok'] = SlicedFile(filename=JOB_FILE, stream=io.BytesIO(b'abc'))
        assert shop.client.post('/printer/jobs', json={'token': 'tok'}).status_code == 202
        files = relay_of(shop.app).files
        assert files.sweep() == []
        assert len(os.listdir(tmp_path / 'spool')) == 1

    def test_expired_records_nobody_reads_again_are_swept(self, shop):
        shop.relay.note_code('ABCD2345')
        assert shop.relay.counts()['records'] == 2
        shop.clock.advance(relay_module.RECORD_TTL_SECONDS + 1)
        shop.relay.note_code(CODE)                  # only our own record is read again
        shop.client.get('/printer/status')
        assert shop.relay.counts()['records'] == 1

    def test_final_delivery_jobs_are_dropped_after_their_keeping_time(self, shop):
        job_id = shop.send()
        shop.cancel(job_id)
        shop.clock.advance(dl.FINAL_TTL_SECONDS + relay_module.SWEEP_EVERY_SECONDS + 1)
        shop.client.get('/printer/status')
        assert shop.relay.counts()['deliveries'] == 0
        assert shop.client.get(f'/printer/jobs/{job_id}').status_code == 404

    def test_the_sweep_runs_at_most_once_a_minute(self, shop):
        assert shop.relay.sweep() == 0
        shop.clock.advance(1)
        shop.relay.note_code('ABCD2345')
        shop.clock.advance(relay_module.RECORD_TTL_SECONDS)
        assert shop.relay.sweep() == 1


# --- supportable from the server --------------------------------------------------------------

class TestLogLines:
    def test_every_transition_and_every_exchange_writes_one_structured_line(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(dict(shop.printing(job_id), state='finished'))
        logged = shop.caller.logged
        tag = relay_module.printer_tag(CODE)
        transitions = [line for line in logged if 'event=transition' in line]
        assert [line.split(' state=')[1].split(' code=')[0] for line in transitions] == [
            'queued stage=waiting_for_daemon', 'running stage=waiting_for_daemon',
            'running stage=downloading', 'running stage=uploading', 'running stage=starting',
            'running stage=printing', 'done stage=printing']
        assert all(f'job={job_id}' in line and f'printer={tag}' in line
                   for line in transitions)
        for name in ('send', 'sync', 'start', 'ack'):
            assert any(line.startswith(f'printer-delivery request={name} ') for line in logged)

    def test_a_status_poll_is_logged_so_support_can_see_it_was_asked(self, shop):
        shop.client.get('/printer/status')
        assert any(line.startswith('printer-delivery request=status ')
                   and 'status=200' in line for line in shop.caller.logged)

    def test_no_log_line_holds_a_pairing_code_token_or_download_token(self, shop):
        job_id = shop.through_to_printing()
        download_path = None
        for line in shop.caller.logged:
            assert CODE not in line and '7K3M-Q9XW' not in line
            assert shop.headers['Authorization'].split()[1] not in line
            assert '/printer/download/' not in line
        assert job_id

    def test_a_failure_transition_names_its_code(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        shop.ack(job_id, False, code='delivery.download_failed', error='reset')
        assert any('state=failed' in line and 'code=delivery.download_failed' in line
                   for line in shop.caller.logged)


# --- caller functions that answer with the wrong type ------------------------------------------

class TestWrongTypes:
    @pytest.mark.parametrize('answer', ['7K3MQ9XW', {'pairing_code': CODE}, 6238, ['x']])
    def test_an_identify_that_returns_the_wrong_type_is_an_error_report(self, shop, answer):
        shop.caller.team = answer
        status = shop.client.get('/printer/status')
        assert status.status_code == 200 and status.get_json()['paired'] is False
        send = shop.client.post('/printer/jobs', json={'token': 'tok'})
        assert send.status_code == 401
        report = send.get_json()['error_report']
        assert report['code'] == 'delivery.identity_unreadable'
        assert 'not a Team' in report['detail']

    @pytest.mark.parametrize('answer, named', [
        ('/tmp/x.gcode.3mf', 'returned str'), ({'filename': 'x'}, 'returned dict'),
        (7, 'returned int'),
        (SlicedFile(filename='x.gcode.3mf', stream=io.BytesIO(b'x'), sliced_at='today'),
         'sliced_at is str'),
        (SlicedFile(filename='', stream=io.BytesIO(b'x')), 'no filename'),
        (SlicedFile(filename='x.gcode.3mf', stream=io.BytesIO(b'x'), sliced_at=True),
         'sliced_at is bool'),
        (SlicedFile(filename='x.gcode.3mf', path=42), 'path is int'),
    ])
    def test_a_find_sliced_file_that_returns_the_wrong_type_is_an_error_report(
            self, shop, answer, named):
        shop.caller.files['tok'] = answer
        resp = shop.client.post('/printer/jobs', json={'token': 'tok'})
        assert resp.status_code == 500
        assert resp.mimetype == 'application/json'
        report = resp.get_json()['error_report']
        assert report['code'] == 'delivery.sliced_file_unreadable'
        assert named in report['detail']
        assert len(relay_of(shop.app).files) == 0

    def test_a_stream_that_yields_text_is_an_error_report(self, shop):
        shop.caller.files['tok'] = SlicedFile(filename=JOB_FILE, stream=io.StringIO('text'))
        resp = shop.client.post('/printer/jobs', json={'token': 'tok'})
        assert resp.status_code == 500
        assert resp.get_json()['error_report']['code'] == 'delivery.sliced_file_unreadable'
        assert os.listdir(shop.tmp_path / 'spool') == []

    def test_anything_that_escapes_a_route_is_an_error_report_not_a_bare_500(self, shop,
                                                                           monkeypatch):
        def broken(code):
            raise RuntimeError('relay state broke /printer/download/s3cret')

        monkeypatch.setattr(shop.relay, 'status_for', broken)
        resp = shop.client.get('/printer/status')
        assert resp.status_code == 500 and resp.mimetype == 'application/json'
        report = resp.get_json()['error_report']
        assert report['code'] == 'delivery.relay_failed'
        assert 's3cret' not in json.dumps(resp.get_json())
        assert any('event=unexpected' in line for line in shop.caller.logged)

    def test_an_unknown_route_is_still_a_plain_404(self, shop):
        assert shop.client.get('/printer/nothing-here').status_code == 404


# --- the printer waiting for a person (defect 1, round 2) -----------------------------------

def waiting(shop, job_id, **fields):
    """The daemon's snapshot of our print while the printer waits for a person."""
    snapshot = shop.printing(job_id, state='paused', stage='paused_filament_runout',
                             stage_label='Paused: the filament ran out', stage_code=6,
                             error='PRINT_ERROR_07008011', waiting_for='paused_filament_runout',
                             waiting_label='Paused: the filament ran out',
                             at_the_printer="Load new filament, then resume the print on "
                                            "the printer's screen.")
    snapshot.update(fields)
    return snapshot


class TestWaitingForAPerson:
    def test_a_fault_cleared_at_the_printer_is_a_wait_never_an_end(self, shop):
        """The reviewer's probe H: filament out, the printer waits, someone loads filament,
        the print resumes and finishes. The job is done, not failed."""
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=30))
        shop.sync(waiting(shop, job_id, percent=30))
        report = shop.report(job_id)
        assert (report['state'], report['stage']) == ('running', 'waiting_for_person')
        assert report['stage_label'] == 'The printer is waiting for someone'
        assert report['waiting_for'] == 'paused_filament_runout'
        assert report['printer_error'] == 'PRINT_ERROR_07008011'
        assert report['printer_error_meaning'] == 'the filament ran out'
        assert report['at_the_printer'].startswith('Load new filament')
        assert report['percent'] == 30 and 'error' not in report
        shop.clock.advance(40 * 60)                 # nobody comes for forty minutes
        shop.sync(waiting(shop, job_id, percent=30))
        assert shop.report(job_id)['stage'] == 'waiting_for_person'
        shop.sync(shop.printing(job_id, percent=31))
        back = shop.report(job_id)
        assert (back['stage'], back['percent']) == ('printing', 31)
        for gone in ('waiting_for', 'printer_error', 'at_the_printer', 'printer_error_meaning'):
            assert gone not in back
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        assert shop.report(job_id)['state'] == 'done'

    def test_a_wait_with_no_remedy_from_the_daemon_still_says_what_to_do(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, state='paused', stage='paused_by_user',
                                stage_label='Paused at the printer'))
        report = shop.report(job_id)
        assert report['stage'] == 'waiting_for_person'
        assert report['waiting_for'] == 'paused'
        assert report['waiting_label'] == 'Paused at the printer'
        assert report['at_the_printer'] == dl.AT_THE_PRINTER
        assert 'printer_error' not in report

    def test_an_unknown_error_code_while_waiting_is_shown_without_a_meaning(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(waiting(shop, job_id, error='PRINT_ERROR_0BADC0DE'))
        report = shop.report(job_id)
        assert report['printer_error'] == 'PRINT_ERROR_0BADC0DE'
        assert 'printer_error_meaning' not in report

    def test_an_unrecognised_value_is_shown_and_the_print_goes_on(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, unrecognised="gcode_state 'SOMETHING_NEW'"))
        report = shop.report(job_id)
        assert (report['state'], report['stage']) == ('running', 'printing')
        assert report['unrecognised'] == "gcode_state 'SOMETHING_NEW'"

    def test_a_wait_counts_as_the_printer_reporting_for_stop_following(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(waiting(shop, job_id))
        resp = shop.client.post(f'/printer/jobs/{job_id}/stop-following')
        assert resp.status_code == 409
        assert resp.get_json()['error_report']['code'] == 'delivery.still_reporting'


# --- stop following (defect 3, round 2) -------------------------------------------------------

class TestStopFollowing:
    def stop(self, shop, job_id):
        return shop.client.post(f'/printer/jobs/{job_id}/stop-following')

    def test_a_stale_job_past_the_gate_can_be_given_up_and_the_queue_is_freed(self, shop):
        """The printer was switched off mid-print: the caller stops following, the job
        ends saying the outcome is unknown, the slot is free, and the next send is guarded
        only by the printer's own report."""
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)                            # granted; the ack never arrives
        shop.sync(shop.printing(job_id, percent=20))
        shop.sync(dict(IDLE, state='unreachable', report_age_s=0))
        shop.clock.advance(30)
        shop.sync(dict(IDLE, state='unreachable', report_age_s=30))
        resp = self.stop(shop, job_id)
        assert resp.status_code == 200, resp.get_json()
        body = resp.get_json()
        assert body['outcome'] == 'stopped'
        progress = body['progress']
        assert (progress['state'], progress['error']['code']) == ('failed',
                                                                  'delivery.outcome_unknown')
        assert 'the caller stopped following it' in progress['error']['detail']
        status = shop.client.get('/printer/status').get_json()
        assert status['job'] is None                  # the job slot is free
        assert status['last_result']['error_report']['code'] == 'delivery.outcome_unknown'
        assert shop.start(job_id).status_code == 404  # the gate stays shut
        assert shop.ack(job_id, True).status_code == 404      # a late ack is final
        # A send while the printer cannot be heard is refused by the printer's report ...
        shop.caller.offer(shop.tmp_path, content=b'next')
        refused = shop.client.post('/printer/jobs', json={'token': 'tok'})
        assert refused.status_code == 409
        assert refused.get_json()['error_report']['code'] == 'delivery.printer_unreachable'
        # ... and goes ahead once the printer reports idle again.
        shop.sync(IDLE)
        assert shop.client.post('/printer/jobs', json={'token': 'tok'}).status_code == 202

    def test_a_job_whose_daemon_went_silent_can_be_given_up(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=20))
        shop.clock.advance(dl.STALE_AFTER_SECONDS)
        assert self.stop(shop, job_id).get_json()['outcome'] == 'stopped'

    def test_a_starting_job_that_went_stale_can_be_given_up(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        shop.clock.advance(dl.STALE_AFTER_SECONDS)
        assert self.stop(shop, job_id).get_json()['outcome'] == 'stopped'
        assert shop.client.get('/printer/status').get_json()['job'] is None

    def test_a_fresh_print_is_refused_because_it_is_running(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(shop.printing(job_id, percent=20))
        resp = self.stop(shop, job_id)
        assert resp.status_code == 409
        report = resp.get_json()['error_report']
        assert report['code'] == 'delivery.still_reporting'
        assert report['message'] == ('The printer is still reporting this print, so it is '
                                     'running and can only be stopped at the printer.')
        assert shop.report(job_id)['state'] == 'running'

    def test_before_the_gate_it_says_to_cancel_instead(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        shop.clock.advance(dl.STALE_AFTER_SECONDS)
        resp = self.stop(shop, job_id)
        assert resp.status_code == 409
        report = resp.get_json()['error_report']
        assert (report['code'], report['action']) == ('delivery.not_started', 'cancel')

    def test_a_finished_or_unknown_job(self, shop):
        job_id = shop.through_to_printing()
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        resp = self.stop(shop, job_id)
        assert (resp.status_code, resp.get_json()['error_report']['code']) == \
            (409, 'delivery.already_finished')
        resp = self.stop(shop, 'jdeadbeef')
        assert (resp.status_code, resp.get_json()['error_report']['code']) == \
            (404, 'delivery.job_unknown')

    def test_without_a_session_it_is_refused_before_anything_changes(self, shop):
        job_id = shop.through_to_printing()
        shop.clock.advance(dl.STALE_AFTER_SECONDS)
        shop.caller.team = None
        resp = self.stop(shop, job_id)
        assert resp.status_code == 401
        assert resp.get_json()['need_verification'] is True
        assert shop.relay.delivery_report(CODE, job_id)['state'] == 'running'

    def test_it_is_logged(self, shop):
        job_id = shop.through_to_printing()
        shop.clock.advance(dl.STALE_AFTER_SECONDS)
        self.stop(shop, job_id)
        assert any('request=stop_following' in line and 'status=stopped' in line
                   for line in shop.caller.logged)


# --- the job slot is freed by any end (defect 2, round 2) -----------------------------------

class TestTheSlotIsFreedByAnyEnd:
    def test_a_print_that_ends_before_the_ack_frees_the_slot(self, shop):
        """The daemon's ok acknowledgement never reached the relay (a proxy's 404 page
        answered it): the printer's own report of the finished print frees the slot, and
        the next send is accepted."""
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        shop.sync(shop.printing(job_id, percent=50))
        shop.sync(dict(shop.printing(job_id, percent=100), state='finished'))
        assert shop.report(job_id)['state'] == 'done'
        status = shop.client.get('/printer/status').get_json()
        assert status['job'] is None
        assert status['last_result']['ok'] is True
        assert shop.ack(job_id, True).status_code == 404      # final for the daemon
        shop.sync(IDLE)
        assert shop.client.post('/printer/jobs', json={'token': 'tok'}).status_code == 202

    def test_a_print_that_fails_before_the_ack_frees_the_slot_with_its_report(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        shop.sync(shop.printing(job_id))
        shop.sync(shop.printing(job_id, state='error', error='PRINT_ERROR_07008011'))
        last = shop.client.get('/printer/status').get_json()['last_result']
        assert last['ok'] is False
        assert last['error_report']['code'] == 'delivery.print_failed'

    @pytest.mark.parametrize('state', ['finished', 'error'])
    def test_an_end_naming_the_file_before_it_was_seen_going_is_not_taken(self, shop,
                                                                        state):
        """Review 4, defect 2, the relay's half: our name under the previous print's end
        (`FINISH`, `FAILED`, idle with an error code) in the first seconds after the gate is
        not the end of this print. The relay waits for the daemon, which can tell."""
        job_id = shop.send()
        shop.sync(IDLE)
        shop.start(job_id)
        shop.sync(shop.printing(job_id, state=state, percent=100,
                                error='PRINT_ERROR_0300400C' if state == 'error' else None))
        report = shop.report(job_id)
        assert (report['state'], report['stage']) == ('running', 'starting')
        shop.sync(shop.printing(job_id, percent=1))
        assert shop.report(job_id)['stage'] == 'printing'


# --- what the relay keeps of what a daemon sends (defect 5, round 2) ------------------------

class TestSizeLimits:
    BIG = 'x' * 30_000

    def test_a_body_over_the_limit_is_refused_before_it_is_read(self, shop):
        body = {'state': 'idle', 'junk': 'x' * (routes.MAX_REQUEST_BYTES + 1)}
        resp = shop.client.post('/printer/daemon/sync', json=body, headers=shop.headers,
                                **HTTPS)
        assert resp.status_code == 413
        assert resp.get_json()['error_report']['code'] == 'delivery.request_too_large'
        assert shop.relay.status_for(CODE)['status']['state'] == 'idle'   # the old one
        assert any('request=too_large' in line for line in shop.caller.logged)

    def test_a_send_over_the_limit_is_refused_too(self, shop):
        resp = shop.client.post('/printer/jobs',
                                json={'token': 'x' * (routes.MAX_REQUEST_BYTES + 1)})
        assert resp.status_code == 413
        assert resp.get_json()['error_report']['code'] == 'delivery.request_too_large'

    def test_the_snapshot_is_cut_where_it_is_stored_served_and_logged(self, shop):
        """The reviewer's probe I: one sync with oversized strings, numbers and unknown
        fields. The status answer and every log line stay small."""
        job_id = shop.send()
        big = self.BIG[:5_000]                      # nine of them stay under the limit
        snapshot = dict(shop.printing(job_id), file=big, job_name=big, stage_label=big,
                        error=big, junk=big, percent=10 ** 400, layer=float('inf'),
                        printer={'model': big, 'name': None, 'serial': 7, 'extra': big})
        resp = shop.client.post('/printer/daemon/sync', headers=shop.headers, **HTTPS,
                                data=json.dumps(dict(snapshot, job_progress={
                                    'id': job_id, 'stage': big, 'junk': big})),
                                content_type='application/json')
        assert resp.status_code == 200
        status = shop.client.get('/printer/status').get_json()
        assert len(json.dumps(status)) < 3_000
        kept = status['status']
        assert 'junk' not in kept
        assert len(kept['file']) == relay_module.MAX_SNAPSHOT_TEXT
        assert kept['percent'] is None and kept['layer'] is None
        assert kept['printer'] == {'model': 'x' * relay_module.MAX_SNAPSHOT_TEXT,
                                   'name': None, 'serial': None}
        assert len(json.dumps(shop.report(job_id))) < 3_000
        assert max(len(line) for line in shop.caller.logged) < 2_000

    def test_the_start_gate_keeps_a_short_instance_and_logs_a_short_job_id(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        assert shop.start(job_id, instance=self.BIG).get_json()['outcome'] == 'start'
        assert shop.start(job_id, instance=self.BIG[:relay_module.MAX_INSTANCE_CHARS]
                          ).get_json()['outcome'] == 'start'
        held = shop.relay._records[CODE].job['start_granted_to']
        assert len(held) == relay_module.MAX_INSTANCE_CHARS
        shop.client.post(f"/printer/daemon/jobs/j{'f' * 5000}/ack", json={'ok': True},
                         headers=shop.headers, **HTTPS)
        assert max(len(line) for line in shop.caller.logged) < 2_000

    def test_an_acknowledgements_code_is_cut(self, shop):
        job_id = shop.send()
        shop.sync(IDLE)
        shop.ack(job_id, False, code='delivery.' + self.BIG, error='x')
        report = shop.report(job_id)
        assert len(json.dumps(report)) < 3_000
        assert max(len(line) for line in shop.caller.logged) < 2_000
        assert max(len(json.dumps(fields, default=str))
                   for _kind, fields in shop.caller.events) < 2_000
