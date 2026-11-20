"""The relay's HTTP routes through Flask's test client: no socket, the fake clock, and a
fresh app per test, so nothing leaks between tests and no deadline needs real time.

Ported from the original relay's test_printer_routes.py. Rewritten: the original patched
module globals of the caller application (the session gate, the token manager, the metrics
object) and switched its shared rate limiter off and on around each test, so a test could
leak state into the next; here each test builds its own app through create_app and the
limiter runs on the fake clock in every test. Tests of the caller's own wiring (its session,
its YAML loading, its app-wide default limit) did not come across."""
import io
import threading

import pytest

from penguin_delivery_relay import SlicedFile, Team, relay_of
from penguin_delivery_relay import relay as relay_module
from penguin_delivery_relay import routes

from relay_fakes import CODE, IDLE, SECRET, make_app, running


def go_online(relay, snapshot=IDLE):
    relay.note_code(CODE)
    relay.note_daemon(CODE)
    relay.store_status(CODE, snapshot)


def send(client, token='tok'):
    return client.post('/printer/jobs', json={'token': token})


# --- GET /printer/status -------------------------------------------------------------

class TestStatusRoute:
    def test_no_identity_is_401_with_an_error_report(self, client, caller):
        caller.team = None
        resp = client.get('/printer/status')
        assert resp.status_code == 401
        body = resp.get_json()
        assert body['need_verification'] is True
        assert body['error'] == 'Session verification required.'
        assert body['error_report']['code'] == 'delivery.no_session'

    def test_unpaired_when_the_team_has_no_code(self, client, caller):
        caller.team = Team(pairing_code=None, team_number=6238)
        resp = client.get('/printer/status')
        assert resp.status_code == 200
        assert resp.get_json() == relay_module.PrinterRelay.UNPAIRED

    def test_a_malformed_code_reads_as_unpaired(self, client, caller):
        caller.team = Team(pairing_code='nope')     # ('not a code' normalises to N0TAC0DE)
        assert client.get('/printer/status').get_json()['paired'] is False

    def test_the_first_poll_presents_the_code_and_shows_waiting(self, client, relay):
        body = client.get('/printer/status').get_json()
        assert body['paired'] is True
        assert body['waiting'] is True
        assert body['code'] == '7K3M-Q9XW'
        assert relay.begin_exchange(CODE)          # the poll is what made pairing possible

    def test_the_display_form_of_a_code_works(self, client, caller):
        caller.team = Team(pairing_code='7k3m-q9xw')
        assert client.get('/printer/status').get_json()['code'] == '7K3M-Q9XW'

    def test_an_online_running_snapshot_is_served_with_its_display_name(self, client, relay):
        go_online(relay, running('sample_part-j8f3a2c1.gcode.3mf'))
        body = client.get('/printer/status').get_json()
        assert body['online'] is True
        assert body['age_seconds'] == 0
        assert body['status']['state'] == 'running'
        assert body['status']['file'] == 'sample_part-j8f3a2c1.gcode.3mf'
        assert body['status']['display_name'] == 'sample_part.gcode.3mf'

    def test_offline_after_two_minutes_of_silence(self, client, relay, clock):
        go_online(relay)
        clock.advance(420)
        body = client.get('/printer/status').get_json()
        assert body['online'] is False
        assert body['age_seconds'] == 420

    def test_an_identify_that_raises_reads_as_unpaired_and_is_logged(self, client, caller):
        caller.identify_error = RuntimeError('stale cookie')
        resp = client.get('/printer/status')
        assert resp.status_code == 200
        assert resp.get_json()['paired'] is False
        assert any('unreadable identity: RuntimeError: stale cookie' in line
                   for line in caller.logged)

    def test_identify_is_asked_on_every_poll(self, client, caller):
        client.get('/printer/status')
        client.get('/printer/status')
        assert caller.identified == ['/printer/status', '/printer/status']

    def test_a_failed_last_result_carries_an_error_report(self, client, relay):
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/d', filename='f',
                        team_number=None)
        relay.finish_job(CODE, 'j8f3a2c1', ok=False,
                         reason='the printer refused the print start command')
        last = client.get('/printer/status').get_json()['last_result']
        assert last['ok'] is False
        assert last['reason'] == 'the printer refused the print start command'
        assert last['error_report']['code'] == 'delivery.start_refused'

    def test_a_successful_last_result_carries_none(self, client, relay):
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/d', filename='f',
                        team_number=None)
        relay.finish_job(CODE, 'j8f3a2c1', ok=True, reason=None)
        last = client.get('/printer/status').get_json()['last_result']
        assert last['ok'] is True
        assert 'error_report' not in last


# --- POST /printer/jobs ---------------------------------------------------------------

class TestJobsRoute:
    @pytest.fixture(autouse=True)
    def online(self, relay):
        go_online(relay)

    def test_no_identity_is_401(self, client, caller):
        caller.team = None
        assert send(client).status_code == 401

    def test_a_team_without_a_code_is_refused(self, client, caller):
        caller.team = Team(pairing_code=None)
        resp = send(client)
        assert resp.status_code == 409
        assert resp.get_json()['error'] == 'No printer paired'
        assert resp.get_json()['error_report']['code'] == 'delivery.not_paired'

    def test_an_identify_that_raises_is_refused_as_unreadable_not_as_unpaired(
            self, client, caller):
        """The team may well be paired: what failed is reading who is asking."""
        caller.identify_error = ValueError('a list where a mapping belongs')
        resp = send(client)
        assert resp.status_code == 401
        body = resp.get_json()
        assert body['error'] == ('Could not read who is asking: '
                                 'ValueError: a list where a mapping belongs')
        report = body['error_report']
        assert report['code'] == 'delivery.identity_unreadable'
        assert report['message'] == ('The printer service could not read which team sent '
                                     'this print.')
        assert report['remedy'] == 'Sign in again, then send the print once more.'
        assert report['detail'] == body['error']
        assert 'need_verification' not in body
        assert caller.asked == []
        assert any('unreadable identity: ValueError: a list where a mapping belongs' in line
                   for line in caller.logged)

    def test_an_unknown_token_is_not_found(self, client):
        resp = send(client, token='nope')
        assert resp.status_code == 404
        assert resp.get_json()['error'] == 'File not found or expired'
        assert resp.get_json()['error_report']['code'] == 'delivery.sliced_file_missing'

    def test_a_body_without_a_token_is_not_found(self, client):
        assert client.post('/printer/jobs', json={}).status_code == 404
        assert client.post('/printer/jobs', data='not json').status_code == 404

    @pytest.mark.parametrize('body', [[1, 2], 'text', 7, None, True])
    def test_a_json_body_that_is_not_an_object_answers_as_an_empty_body(self, client,
                                                                        caller, body):
        resp = client.post('/printer/jobs', json=body)
        assert resp.status_code == 404
        assert resp.get_json()['error_report']['code'] == 'delivery.sliced_file_missing'
        assert caller.asked == []

    @pytest.mark.parametrize('token', [{'a': 1}, ['tok'], 7, True, ''])
    def test_a_token_that_is_not_a_non_empty_string_is_never_handed_to_the_caller(
            self, client, caller, tmp_path, token):
        caller.offer(tmp_path)
        resp = client.post('/printer/jobs', json={'token': token})
        assert resp.status_code == 404
        assert resp.get_json()['error_report']['code'] == 'delivery.sliced_file_missing'
        assert caller.asked == []

    def test_find_sliced_file_is_asked_with_the_token_and_the_identified_team(
            self, client, caller, tmp_path):
        caller.offer(tmp_path)
        send(client)
        assert caller.asked == [('tok', caller.team)]

    def test_a_find_sliced_file_that_raises_is_an_error_report_not_a_500_page(
            self, client, caller, app):
        caller.find_error = OSError('the store is offline')
        resp = send(client)
        assert resp.status_code == 500
        assert resp.is_json
        report = resp.get_json()['error_report']
        assert report['code'] == 'delivery.sliced_file_unreadable'
        assert report['detail'] == ('Could not read the sliced file: '
                                    'OSError: the store is offline')
        assert report['retryable'] is True
        assert any(report['detail'] in line for line in caller.logged)
        assert len(relay_of(app).files) == 0

    def test_a_stream_that_fails_while_copied_is_an_error_report_and_leaves_nothing(
            self, client, caller, relay, app, tmp_path):
        class Broken(io.RawIOBase):
            def readable(self):
                return True

            def readinto(self, buffer):
                raise OSError('disk went away')

        caller.files['tok'] = SlicedFile(filename='s.gcode.3mf', stream=Broken())
        resp = send(client)
        assert resp.status_code == 500
        report = resp.get_json()['error_report']
        assert report['code'] == 'delivery.sliced_file_unreadable'
        assert report['detail'] == 'Could not read the sliced file: OSError: disk went away'
        assert any(report['detail'] in line for line in caller.logged)
        assert len(relay_of(app).files) == 0
        assert list((tmp_path / 'spool').iterdir()) == []
        assert relay.status_for(CODE)['job'] is None

    def test_a_path_that_is_not_a_file_is_refused_at_the_send(self, client, caller, relay,
                                                              tmp_path):
        """Not accepted and failed seconds later as job_failed, whose remedy "send again"
        could not help: refused now, with "slice again"."""
        caller.files['tok'] = SlicedFile(filename='s.gcode.3mf',
                                         path=str(tmp_path / 'never-written.gcode.3mf'))
        resp = send(client)
        assert resp.status_code == 404
        report = resp.get_json()['error_report']
        assert report['code'] == 'delivery.sliced_file_missing'
        assert report['action'] == 'slice_again'
        assert relay.status_for(CODE)['job'] is None

    def test_another_request_between_holding_the_file_and_claiming_the_job_keeps_it(
            self, client, caller, relay, app):
        """Every request ends with housekeeping, which drops held files whose job the relay
        does not hold. A status poll landing after the file is held and before the job is
        claimed must not drop this send's file."""
        caller.files['tok'] = SlicedFile(filename='s.gcode.3mf', stream=io.BytesIO(b'3mf'))
        ctx = relay_of(app)
        real_claim = ctx.relay.claim_job
        polled = []

        def claim_after_another_poll(*args, **kwargs):
            polled.append(app.test_client().get('/printer/status').status_code)
            return real_claim(*args, **kwargs)

        ctx.relay.claim_job = claim_after_another_poll
        assert send(client).status_code == 202
        ctx.relay.claim_job = real_claim
        assert polled == [200]
        job = relay.store_status(CODE, IDLE)
        resp = client.get(job['download_path'])
        assert resp.status_code == 200
        assert resp.data == b'3mf'

    def test_a_claim_that_raises_leaves_no_file_behind(self, client, caller, app, tmp_path):
        caller.files['tok'] = SlicedFile(filename='s.gcode.3mf', stream=io.BytesIO(b'3mf'))
        ctx = relay_of(app)

        def broken_claim(*args, **kwargs):
            raise RuntimeError('relay state is broken')

        ctx.relay.claim_job = broken_claim
        assert send(client).status_code == 500
        assert len(ctx.files) == 0
        assert list((tmp_path / 'spool').iterdir()) == []

    def test_a_file_sliced_more_than_forty_minutes_ago_must_be_sliced_again(
            self, client, caller, clock, tmp_path):
        caller.offer(tmp_path, sliced_at=clock.now - routes.SLICE_MAX_AGE_SECONDS - 1)
        resp = send(client)
        assert resp.status_code == 409
        assert resp.get_json()['error'] == 'slice again'
        assert resp.get_json()['error_report']['code'] == 'delivery.sliced_file_too_old'

    def test_a_file_exactly_forty_minutes_old_is_still_accepted(
            self, client, caller, clock, tmp_path):
        caller.offer(tmp_path, sliced_at=clock.now - routes.SLICE_MAX_AGE_SECONDS)
        assert send(client).status_code == 202

    def test_success_stores_a_pending_job_and_answers_202(self, client, caller, relay, tmp_path):
        caller.offer(tmp_path)
        resp = send(client)
        assert resp.status_code == 202
        job_id = resp.get_json()['job_id']
        assert resp.get_json() == {'ok': True, 'job_id': job_id}
        stored = relay.status_for(CODE)['job']
        assert stored['id'] == job_id
        assert stored['state'] == 'pending'
        assert stored['filename'] == 'sample_part.gcode.3mf'

    def test_a_send_reports_an_event_and_a_log_line(self, client, caller, tmp_path):
        caller.offer(tmp_path)
        job_id = send(client).get_json()['job_id']
        assert caller.events == [('printer_send', {
            'team_number': 6238, 'user': 'student@example.com',
            'metadata': {'job_id': job_id, 'filename': 'sample_part.gcode.3mf'}})]
        assert any(job_id in line and 'queued' in line for line in caller.logged)

    def test_a_second_send_while_one_is_in_flight_is_refused(self, client, caller, app,
                                                             tmp_path):
        caller.offer(tmp_path)
        assert send(client).status_code == 202
        second = send(client)
        assert second.status_code == 409
        assert second.get_json()['error'] == 'A job is already on its way to the printer'
        assert second.get_json()['error_report']['code'] == 'delivery.job_in_flight'
        assert len(relay_of(app).files) == 1      # the refused send holds no file

    def test_a_refused_send_of_a_stream_leaves_no_copy_behind(self, client, caller, relay,
                                                              tmp_path):
        relay.store_status(CODE, running('other.gcode.3mf'))       # busy
        caller.files['tok'] = SlicedFile(filename='s.gcode.3mf', stream=io.BytesIO(b'3mf'))
        assert send(client).status_code == 409
        assert list((tmp_path / 'spool').iterdir()) == []

    def test_only_one_of_many_simultaneous_sends_wins(self, app, caller, relay, tmp_path):
        """The check-and-store is one lock acquisition, so sends racing on several threads
        produce exactly one job, and the refused sends' housekeeping does not take the
        winner's file. No thread waits on time: the barrier only lines them up, and a thread
        that fails before it breaks the barrier instead of leaving the others waiting."""
        contents = {f'tok{n}': f'sliced file {n}'.encode() for n in range(8)}
        for token, content in contents.items():
            caller.files[token] = SlicedFile(filename='s.gcode.3mf',
                                             stream=io.BytesIO(content))
        barrier = threading.Barrier(8, timeout=30)
        answers = []

        def press_send(token):
            try:
                client = app.test_client()
                barrier.wait()
                resp = send(client, token)
                answers.append((resp.status_code, resp.get_json().get('job_id'), token))
            except BaseException:
                barrier.abort()
                raise

        threads = [threading.Thread(target=press_send, args=(token,)) for token in contents]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
            assert not thread.is_alive(), 'a sending thread never finished'
        assert sorted(code for code, _, _ in answers) == [202] + [409] * 7
        _, winner, winning_token = next(a for a in answers if a[0] == 202)
        job = relay.store_status(CODE, IDLE)
        assert job['id'] == winner
        download = app.test_client().get(job['download_path'])
        assert download.status_code == 200
        assert download.data == contents[winning_token]
        assert len(relay_of(app).files) == 1
        assert len(list((tmp_path / 'spool').iterdir())) == 1


# --- GET /printer/download/<token> ------------------------------------------------------

class TestDownloadRoute:
    @pytest.fixture(autouse=True)
    def online(self, relay):
        go_online(relay)

    def handed_out_job(self, client, relay):
        assert send(client).status_code == 202
        return relay.store_status(CODE, IDLE)

    def test_the_job_carries_a_path_that_serves_the_sliced_file(self, client, caller, relay,
                                                                tmp_path):
        caller.offer(tmp_path, content=b'the sliced bytes')
        job = self.handed_out_job(client, relay)
        assert job['download_path'].startswith('/printer/download/')
        resp = client.get(job['download_path'])
        assert resp.status_code == 200
        assert resp.data == b'the sliced bytes'
        assert 'sample_part.gcode.3mf' in resp.headers['Content-Disposition']

    def test_a_stream_is_copied_once_and_served(self, client, caller, relay):
        caller.files['tok'] = SlicedFile(filename='s.gcode.3mf',
                                       stream=io.BytesIO(b'streamed bytes'))
        job = self.handed_out_job(client, relay)
        assert client.get(job['download_path']).data == b'streamed bytes'

    def test_after_the_ack_the_download_is_gone_and_the_copy_deleted(
            self, client, caller, relay, auth, tmp_path):
        caller.files['tok'] = SlicedFile(filename='s.gcode.3mf', stream=io.BytesIO(b'3mf'))
        job = self.handed_out_job(client, relay)
        assert len(list((tmp_path / 'spool').iterdir())) == 1
        client.post(f"/printer/daemon/jobs/{job['id']}/ack", json={'ok': True},
                    headers=auth(), base_url='https://relay.test')
        assert client.get(job['download_path']).status_code == 404
        assert list((tmp_path / 'spool').iterdir()) == []

    def test_a_file_the_caller_owns_is_never_deleted(self, client, caller, relay, auth,
                                                   tmp_path):
        path = caller.offer(tmp_path)
        job = self.handed_out_job(client, relay)
        client.post(f"/printer/daemon/jobs/{job['id']}/ack", json={'ok': True},
                    headers=auth(), base_url='https://relay.test')
        assert client.get(job['download_path']).status_code == 404
        assert open(path, 'rb').read() == b'3mf-bytes'

    def test_an_expired_job_takes_its_download_with_it(self, client, caller, relay, clock,
                                                       tmp_path):
        caller.offer(tmp_path)
        job = self.handed_out_job(client, relay)
        clock.advance(15 * 60 + 1)
        assert client.get(job['download_path']).status_code == 404

    def test_an_unknown_token_is_not_found(self, client):
        resp = client.get('/printer/download/nope')
        assert resp.status_code == 404
        assert resp.get_json() == {'error': 'File not found or expired'}

    def test_a_caller_file_that_vanished_is_not_found_not_a_500(self, client, caller, relay,
                                                              tmp_path):
        path = caller.offer(tmp_path)
        job = self.handed_out_job(client, relay)
        (tmp_path / path.rsplit('/', 1)[1]).unlink()
        assert client.get(job['download_path']).status_code == 404

    def test_the_download_needs_no_bearer_header(self, client, caller, relay, tmp_path):
        caller.offer(tmp_path)
        job = self.handed_out_job(client, relay)
        assert client.get(job['download_path']).status_code == 200


# --- the daemon routes ------------------------------------------------------------------

class TestDaemonRoutes:
    @pytest.fixture(autouse=True)
    def presented(self, relay):
        relay.note_code(CODE)

    def test_the_exchange_answers_a_token_then_refuses_the_second_pi(self, client, https):
        first = client.post('/printer/daemon/pair', json={'code': '7k3m-q9xw'}, **https)
        assert first.status_code == 200
        assert relay_module.read_token(first.get_json()['token'], SECRET)[0] == CODE
        second = client.post('/printer/daemon/pair', json={'code': CODE}, **https)
        assert second.status_code == 404
        assert second.get_json() == {'error': 'not paired'}

    def test_the_exchange_for_an_unpresented_code_answers_the_same_404(self, client, https):
        for body in ({'code': 'ABCDEFGH'}, {'code': 'nope'}, {}):
            resp = client.post('/printer/daemon/pair', json=body, **https)
            assert resp.status_code == 404
            assert resp.get_json() == {'error': 'not paired'}

    def test_the_exchange_is_logged_without_the_token_or_the_pairing_code(
            self, client, caller, https):
        token = client.post('/printer/daemon/pair', json={'code': CODE},
                            **https).get_json()['token']
        tag = relay_module.printer_tag(CODE)
        assert f'printer-delivery request=pair printer={tag} status=200' in caller.logged
        assert not any(token in line for line in caller.logged)
        assert not any(CODE in line or '7K3M-Q9XW' in line for line in caller.logged)

    def test_sync_with_a_bad_token_says_repair(self, client, https):
        for header in ({'Authorization': 'Bearer garbage'}, {'Authorization': 'Basic x'},
                       {}):
            resp = client.post('/printer/daemon/sync', json=IDLE, headers=header, **https)
            assert resp.status_code == 401
            assert resp.get_json() == {'error': 'repair'}

    def test_a_token_signed_with_another_key_is_rejected(self, client, auth, https):
        resp = client.post('/printer/daemon/sync', json=IDLE,
                           headers=auth(key='some-other-key'), **https)
        assert resp.status_code == 401

    def test_an_unauthenticated_sync_never_touches_the_relay(self, client, relay, https):
        """The token is checked BEFORE note_daemon, so a guessed code cannot be marked
        alive -- which would otherwise block the real daemon's next exchange."""
        client.post('/printer/daemon/sync', json=IDLE,
                    headers={'Authorization': 'Bearer garbage'}, **https)
        assert relay.status_for(CODE)['waiting'] is True
        assert relay.begin_exchange(CODE)

    def test_sync_stores_the_snapshot_and_hands_out_a_job(self, client, relay, auth, https):
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/printer/download/t',
                        filename='sample_part.gcode.3mf', team_number=6238)
        body = client.post('/printer/daemon/sync', json=running('x'), headers=auth(),
                           **https).get_json()
        assert body['job']['id'] == 'j8f3a2c1'
        assert relay.status_for(CODE)['job']['state'] == 'handed_out'
        assert relay.status_for(CODE)['status']['state'] == 'running'

    def test_the_job_on_the_wire_carries_only_the_documented_fields(
            self, client, relay, auth, https, clock):
        """The relay's state -- team_number, the job state, the hand-out time, which
        daemon holds the start -- is the relay's bookkeeping and is never sent to the daemon."""
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/printer/download/t',
                        filename='sample_part.gcode.3mf', team_number=6238, size=9,
                        sha256='ab' * 32)
        job = client.post('/printer/daemon/sync', json=IDLE, headers=auth(),
                          **https).get_json()['job']
        assert job == {'id': 'j8f3a2c1', 'download_path': '/printer/download/t',
                       'filename': 'sample_part.gcode.3mf', 'created_at': clock.now,
                       'size': 9, 'sha256': 'ab' * 32, 'cancel': False,
                       'start_granted': False}

    def test_sync_answers_a_null_job_when_there_is_none(self, client, auth, https):
        assert client.post('/printer/daemon/sync', json=IDLE, headers=auth(),
                           **https).get_json() == {'job': None}

    def test_a_sync_body_that_is_not_json_stores_an_empty_snapshot(self, client, relay,
                                                                   auth, https):
        client.post('/printer/daemon/sync', data='garbage', headers=auth(), **https)
        assert relay.status_for(CODE)['online'] is True

    def test_a_token_recreates_the_record_after_a_relay_restart(self, caller, clock, auth,
                                                                https):
        """A fresh app is a restarted relay: no caller has presented the code, and the
        daemon's sync alone brings the status back."""
        fresh = make_app(caller, clock)
        client = fresh.test_client()
        assert client.post('/printer/daemon/sync', json=IDLE, headers=auth(),
                           **https).status_code == 200
        assert relay_of(fresh).relay.status_for(CODE)['online'] is True

    def test_ack_records_the_outcome_and_reports_an_event(self, client, relay, caller, auth,
                                                          https):
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/d',
                        filename='sample_part.gcode.3mf', team_number=6238)
        relay.store_status(CODE, IDLE)
        resp = client.post('/printer/daemon/jobs/j8f3a2c1/ack', json={'ok': True},
                           headers=auth(), **https)
        assert resp.status_code == 200
        assert resp.get_json() == {'ok': True}
        assert caller.events == [('printer_ack', {'team_number': 6238, 'metadata': {
            'job_id': 'j8f3a2c1', 'ok': True, 'error': None, 'code': None}})]
        assert relay.status_for(CODE)['last_result']['ok'] is True

    def test_a_failed_ack_keeps_the_daemons_reason(self, client, relay, auth, https):
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/d', filename='f',
                        team_number=None)
        client.post('/printer/daemon/jobs/j8f3a2c1/ack',
                    json={'ok': False, 'error': 'download answered 404'},
                    headers=auth(), **https)
        last = relay.status_for(CODE)['last_result']
        assert (last['ok'], last['reason']) == (False, 'download answered 404')

    @pytest.mark.parametrize('error, stored', [
        (503, '503'),
        (['download', 'failed'], '["download", "failed"]'),
        ({'stage': 'upload'}, '{"stage": "upload"}'),
        (0, None),
        ([], None),
    ])
    def test_an_ack_error_of_any_json_type_leaves_the_status_route_working(
            self, client, relay, caller, auth, https, error, stored):
        """A daemon that sends a number, a list or an object as its reason must not turn
        every status poll into a 500 for the ten minutes the result is shown."""
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/d', filename='f',
                        team_number=None)
        ack = client.post('/printer/daemon/jobs/j8f3a2c1/ack',
                          json={'ok': False, 'error': error}, headers=auth(), **https)
        assert ack.status_code == 200
        status = client.get('/printer/status')
        assert status.status_code == 200
        last = status.get_json()['last_result']
        assert last['reason'] == stored
        assert last['error_report']['code'] == 'delivery.job_failed'
        assert last['error_report']['detail'] == (stored or '')
        assert caller.events[-1][1]['metadata']['error'] == stored

    def test_the_reason_is_stored_logged_and_reported_without_the_download_token(
            self, client, relay, caller, auth, https, tmp_path):
        """The daemon redacts before it sends; the relay does not rely on that."""
        go_online(relay)
        caller.offer(tmp_path)
        job_id = send(client).get_json()['job_id']
        path = relay.store_status(CODE, IDLE)['download_path']
        token = path.rsplit('/', 1)[1]
        client.post(f'/printer/daemon/jobs/{job_id}/ack',
                    json={'ok': False, 'error': f'GET {path} failed: timed out'},
                    headers=auth(), **https)
        body = client.get('/printer/status').get_data(as_text=True)
        assert token not in body
        last = relay.status_for(CODE)['last_result']
        assert last['reason'] == 'GET /printer/download/<token> failed: timed out'
        assert not any(token in line for line in caller.logged)
        assert not any(token in str(event) for event in caller.events)

    @pytest.mark.parametrize('body', [[1], 'text', 7])
    def test_a_daemon_body_that_is_json_but_not_an_object_answers_as_an_empty_body(
            self, client, relay, auth, https, body):
        pair = client.post('/printer/daemon/pair', json=body, **https)
        assert (pair.status_code, pair.get_json()) == (404, {'error': 'not paired'})
        sync = client.post('/printer/daemon/sync', json=body, headers=auth(), **https)
        assert (sync.status_code, sync.get_json()) == (200, {'job': None})
        assert relay.status_for(CODE)['online'] is True
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/d', filename='f',
                        team_number=None)
        ack = client.post('/printer/daemon/jobs/j8f3a2c1/ack', json=body, headers=auth(),
                          **https)
        assert ack.status_code == 200
        assert relay.status_for(CODE)['last_result']['ok'] is False
        assert relay.status_for(CODE)['last_result']['reason'] is None

    def test_ack_for_an_unknown_job_is_404(self, client, auth, https):
        resp = client.post('/printer/daemon/jobs/jffffffff/ack', json={'ok': True},
                           headers=auth(), **https)
        assert resp.status_code == 404
        assert resp.get_json() == {'error': 'unknown job'}

    def test_ack_with_a_bad_token_says_repair(self, client, https):
        resp = client.post('/printer/daemon/jobs/j8f3a2c1/ack', json={'ok': True}, **https)
        assert (resp.status_code, resp.get_json()) == (401, {'error': 'repair'})

    def test_a_job_that_died_on_a_deadline_is_reported_on_the_read_that_killed_it(
            self, client, relay, caller, auth, https, clock):
        """Lazy expiry: the sync that reads the record is what kills the overdue job, so
        the route reports the expiry AFTER that read, not before."""
        go_online(relay)
        relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/d', filename='f',
                        team_number=6238)
        clock.advance(4 * 60)
        body = client.post('/printer/daemon/sync', json=IDLE, headers=auth(),
                           **https).get_json()
        assert body['job'] is None
        assert caller.events == [('printer_ack', {'team_number': 6238, 'metadata': {
            'job_id': 'j8f3a2c1', 'ok': False, 'error': 'printer did not pick up the job',
            'expired': True}})]
        assert any('expired: printer did not pick up the job' in l for l in caller.logged)

    def test_ping_reports_flags_and_stores_nothing(self, client, relay, auth, https):
        resp = client.get('/printer/daemon/ping', headers=auth(), **https)
        assert resp.get_json() == {'ok': True, 'waiting': True, 'online': False}
        assert relay.begin_exchange(CODE)

    def test_ping_with_a_bad_token_says_repair(self, client, https):
        resp = client.get('/printer/daemon/ping', **https)
        assert (resp.status_code, resp.get_json()) == (401, {'error': 'repair'})


# --- HTTPS, development mode, proxies -----------------------------------------------------

DAEMON_ROUTES = (('/printer/daemon/pair', 'post'), ('/printer/daemon/sync', 'post'),
                 ('/printer/daemon/jobs/j8f3a2c1/ack', 'post'), ('/printer/daemon/ping', 'get'))


class TestHttpsAndDevMode:
    def test_daemon_routes_refuse_plain_http_outside_development_mode(self, client, auth):
        for path, method in DAEMON_ROUTES:
            resp = getattr(client, method)(path, json={'code': CODE}, headers=auth())
            assert resp.status_code == 403, path
            assert resp.get_json() == {'error': 'HTTPS required'}

    def test_development_mode_allows_plain_http(self, caller, clock):
        client = make_app(caller, clock, dev=True).test_client()
        client.get('/printer/status')
        assert client.post('/printer/daemon/pair', json={'code': CODE}).status_code == 200

    def test_the_dev_pairing_code_opens_the_exchange_in_development_mode(self, caller, clock):
        client = make_app(caller, clock, dev=True, dev_pairing_code='abcd-efgh').test_client()
        assert client.post('/printer/daemon/pair',
                           json={'code': 'ABCDEFGH'}).status_code == 200

    def test_the_dev_pairing_code_is_ignored_outside_development_mode(self, caller, clock,
                                                                      https):
        client = make_app(caller, clock, dev_pairing_code='ABCDEFGH').test_client()
        assert client.post('/printer/daemon/pair', json={'code': 'ABCDEFGH'},
                           **https).status_code == 404

    def test_a_forwarded_https_request_passes_the_gate(self, client, auth):
        """Behind a proxy that terminates TLS, X-Forwarded-Proto: https is what opens the
        gate; ProxyFix trusts one hop by default."""
        resp = client.post('/printer/daemon/sync', json=IDLE,
                           headers=dict(auth(), **{'X-Forwarded-Proto': 'https'}))
        assert resp.status_code == 200

    def test_with_no_trusted_proxy_the_forwarded_header_is_ignored(self, caller, clock, auth):
        client = make_app(caller, clock, trusted_proxy_hops=0).test_client()
        resp = client.post('/printer/daemon/sync', json=IDLE,
                           headers=dict(auth(), **{'X-Forwarded-Proto': 'https'}))
        assert resp.status_code == 403



# --- rate limits -----------------------------------------------------------------------

class TestRateLimits:
    def test_120_syncs_a_minute_then_429_with_retry_after(self, client, relay, auth,
                                                          https, clock):
        """A sync a second while an upload moves is sixty a minute: the limit leaves room."""
        relay.note_code(CODE)
        codes = [client.post('/printer/daemon/sync', json=IDLE, headers=auth(),
                             **https).status_code for _ in range(120)]
        assert set(codes) == {200}
        clock.advance(20)
        refused = client.post('/printer/daemon/sync', json=IDLE, headers=auth(), **https)
        assert refused.status_code == 429
        assert refused.headers['Retry-After'] == '40'
        assert refused.get_json() == {'error': 'Too Many Requests: 120 per 1 minute'}
        clock.advance(40)
        assert client.post('/printer/daemon/sync', json=IDLE, headers=auth(),
                           **https).status_code == 200

    def test_each_code_has_its_own_daemon_budget(self, client, auth, https):
        for _ in range(60):
            client.post('/printer/daemon/sync', json=IDLE, headers=auth(), **https)
        assert client.post('/printer/daemon/sync', json=IDLE, headers=auth('ABCDEFGH'),
                           **https).status_code == 200

    def test_a_garbage_token_is_limited_by_address_and_still_says_repair(self, client,
                                                                         https):
        resp = client.post('/printer/daemon/sync', json=IDLE,
                           headers={'Authorization': 'Bearer !!! not a token'}, **https)
        assert (resp.status_code, resp.get_json()) == (401, {'error': 'repair'})

    def test_the_exchange_limit_is_shared_by_every_address(self, client, https):
        """Keying the exchange on the address would let a guesser spread the attempts over a
        botnet, so its budget is service-wide: a second address finds it already spent."""
        codes = {client.post('/printer/daemon/pair', json={'code': 'ABCDEFGH'},
                             headers={'X-Forwarded-For': '203.0.113.7'}, **https).status_code
                 for _ in range(60)}
        assert codes == {404}
        other = client.post('/printer/daemon/pair', json={'code': 'ABCDEFGH'},
                            headers={'X-Forwarded-For': '198.51.100.4'}, **https)
        assert other.status_code == 429

    def test_the_status_limit_is_per_team_and_carries_an_error_report(self, client, caller):
        for _ in range(120):
            assert client.get('/printer/status').status_code == 200
        refused = client.get('/printer/status')
        assert refused.status_code == 429
        assert refused.get_json()['error_report']['code'] == 'delivery.rate_limited'
        caller.team = Team(pairing_code='ABCDEFGH')
        assert client.get('/printer/status').status_code == 200

    def test_ten_sends_a_minute(self, client, relay):
        go_online(relay)
        codes = [send(client, token='none').status_code for _ in range(10)]
        assert set(codes) == {404}
        assert send(client).status_code == 429

    def test_a_forwarded_address_is_the_key_for_the_download_limit(self, client):
        """ProxyFix turns X-Forwarded-For into the request address, which is what the
        address-keyed limits count."""
        for _ in range(30):
            client.get('/printer/download/nope', headers={'X-Forwarded-For': '203.0.113.7'})
        assert client.get('/printer/download/nope', headers={
            'X-Forwarded-For': '203.0.113.7'}).status_code == 429
        assert client.get('/printer/download/nope', headers={
            'X-Forwarded-For': '198.51.100.4'}).status_code == 404

    def test_ping_and_ack_each_have_sixty_a_minute(self, client, auth, https):
        for _ in range(60):
            client.get('/printer/daemon/ping', headers=auth(), **https)
            client.post('/printer/daemon/jobs/j1/ack', json={'ok': True}, headers=auth(),
                        **https)
        assert client.get('/printer/daemon/ping', headers=auth(),
                          **https).status_code == 429
        assert client.post('/printer/daemon/jobs/j1/ack', json={'ok': True}, headers=auth(),
                           **https).status_code == 429

    def test_ping_and_ack_share_no_budget_with_sync(self, client, auth, https):
        for _ in range(60):
            client.post('/printer/daemon/sync', json=IDLE, headers=auth(), **https)
        assert client.get('/printer/daemon/ping', headers=auth(), **https).status_code == 200
        assert client.post('/printer/daemon/jobs/j1/ack', json={'ok': True}, headers=auth(),
                           **https).status_code == 404


# --- review 4, defect 6: every refused request leaves its line ------------------------------

JOB_ROUTES = [('GET', '/printer/jobs/j8f3a2c1', 'job'),
              ('GET', '/printer/jobs/j8f3a2c1/events', 'events'),
              ('POST', '/printer/jobs/j8f3a2c1/cancel', 'cancel'),
              ('POST', '/printer/jobs/j8f3a2c1/stop-following', 'stop_following')]


def refusal_lines(caller, name):
    return [line for line in caller.logged if f'printer-delivery request={name} ' in line]


@pytest.mark.parametrize('method,path,name', JOB_ROUTES)
def test_a_signed_out_request_on_a_job_route_is_logged(client, caller, method, path, name):
    """The reviewer's sequence: nobody signed in, each delivery job route answered 401 with
    an error report and logged nothing. Now each logs the route, the refusal and the
    job, with no secret in it."""
    caller.team = None
    resp = client.open(path, method=method)
    assert resp.status_code == 401
    assert resp.get_json()['error_report']
    lines = refusal_lines(caller, name)
    assert len(lines) == 1, caller.logged
    assert 'status=401' in lines[0] and 'error=not_signed_in' in lines[0]
    assert 'job=j8f3a2c1' in lines[0]
    assert CODE not in lines[0]


@pytest.mark.parametrize('method,path,name', JOB_ROUTES)
def test_an_unreadable_identity_on_a_job_route_is_logged(client, caller, method, path,
                                                         name):
    caller.identify_error = RuntimeError('stale cookie')
    assert client.open(path, method=method).status_code == 401
    lines = refusal_lines(caller, name)
    assert len(lines) == 1 and 'error=identity_unreadable' in lines[0], caller.logged


@pytest.mark.parametrize('method,path,name', JOB_ROUTES)
def test_a_rate_limited_request_on_a_job_route_is_logged_with_its_team(
        client, caller, method, path, name):
    limit = routes.STATUS_LIMIT if method == 'GET' else routes.JOBS_LIMIT
    for _ in range(limit.count + 1):
        resp = client.open(path, method=method)
    assert resp.status_code == 429
    lines = [line for line in refusal_lines(caller, name) if 'status=429' in line]
    assert len(lines) == 1, caller.logged
    assert 'error=rate_limited' in lines[0] and 'team=6238' in lines[0]
    assert relay_module.printer_tag(CODE) in lines[0] and CODE not in lines[0]


def test_every_other_refusal_names_itself_in_its_line(client, caller, https, auth):
    """The caller routes and the daemon routes: each refused request's line says which
    refusal it was."""
    caller.team = None
    client.get('/printer/status')
    client.post('/printer/jobs', json={'token': 'tok'})
    client.post('/printer/daemon/sync', json=IDLE)                      # no token, HTTP
    client.post('/printer/daemon/sync', json=IDLE, **https)             # no token
    client.post('/printer/daemon/pair', json={'code': CODE}, **https)   # not presented
    client.get('/printer/download/nothing-here')
    logged = '\n'.join(caller.logged)
    for expected in ('request=status printer=- status=401 error=not_signed_in',
                     'request=send printer=- status=401 error=not_signed_in',
                     'request=sync printer=- status=403 error=https_required',
                     'request=sync printer=- status=401 error=token_invalid',
                     'status=404 error=not_paired',
                     'request=download printer=- status=404 error=file_unknown'):
        assert expected in logged, (expected, caller.logged)
    assert CODE not in logged and 'nothing-here' not in logged
