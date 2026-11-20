"""The error-report adapter: one test per failure kind, each producing the failure on purpose
through the real routes and relay, then checking the report the caller receives.

The shape is checked against contracts/error-report.md: the required fields and their types,
complete sentences, and no download token in any field."""
import io

import pytest

from penguin_delivery_relay import SlicedFile, Team
from penguin_delivery_relay import errors
from penguin_delivery_relay import routes

from relay_fakes import CODE, IDLE, running

REQUIRED = {'code': str, 'message': str, 'remedy': str, 'retryable': bool, 'detail': str}
OPTIONAL = {'where': dict, 'action': str}


def assert_contract_shape(report):
    for field, kind in REQUIRED.items():
        assert isinstance(report[field], kind), field
    assert set(report) <= set(REQUIRED) | set(OPTIONAL), report
    for field, kind in OPTIONAL.items():
        if field in report:
            assert isinstance(report[field], kind), field
    assert report['code'].startswith('delivery.')
    for sentence in (report['message'], report['remedy']):
        assert sentence[0].isupper() and sentence.endswith('.'), sentence
        assert 'delivery.' not in sentence
    assert set(report.get('where', {})) <= {'part', 'copy', 'height_mm', 'stage'}


def online(relay, snapshot=IDLE):
    relay.note_code(CODE)
    relay.note_daemon(CODE)
    relay.store_status(CODE, snapshot)


def refused_send(client, caller, tmp_path):
    caller.offer(tmp_path)
    resp = client.post('/printer/jobs', json={'token': 'tok'})
    assert resp.status_code in (401, 404, 409, 429), resp.status_code
    return resp.get_json()['error_report']


def last_result_report(client):
    last = client.get('/printer/status').get_json()['last_result']
    assert last['ok'] is False
    return last['error_report']


def failed_job(relay, reason):
    """A job handed out and then acknowledged as failed with the daemon's `reason`."""
    online(relay)
    relay.claim_job(CODE, job_id='j8f3a2c1', download_path='/printer/download/t',
                    filename='f', team_number=None)
    relay.store_status(CODE, IDLE)
    relay.finish_job(CODE, 'j8f3a2c1', ok=False, reason=reason)


# --- refused sends ------------------------------------------------------------------------

def test_no_session(client, caller, tmp_path):
    caller.team = None
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.no_session'
    assert report['retryable'] is False
    assert_contract_shape(report)


def test_identity_unreadable(client, caller, tmp_path):
    caller.identify_error = RuntimeError('the cookie is from another key')
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.identity_unreadable'
    assert report['message'] == 'The printer service could not read which team sent this print.'
    assert report['detail'] == ('Could not read who is asking: '
                                'RuntimeError: the cookie is from another key')
    assert report['retryable'] is False
    assert_contract_shape(report)


def test_sliced_file_unreadable(client, caller, relay):
    online(relay)
    caller.find_error = OSError('the store is offline')
    resp = client.post('/printer/jobs', json={'token': 'tok'})
    assert resp.status_code == 500
    report = resp.get_json()['error_report']
    assert report['code'] == 'delivery.sliced_file_unreadable'
    assert report['detail'] == 'Could not read the sliced file: OSError: the store is offline'
    assert report['retryable'] is True
    assert_contract_shape(report)


def test_not_paired(client, caller, tmp_path):
    caller.team = Team(pairing_code=None)
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.not_paired'
    assert report['detail'] == 'No printer paired'
    assert_contract_shape(report)


def test_sliced_file_missing(client, relay):
    online(relay)
    report = client.post('/printer/jobs', json={'token': 'gone'}).get_json()['error_report']
    assert report['code'] == 'delivery.sliced_file_missing'
    assert report['action'] == 'slice_again'
    assert_contract_shape(report)


def test_sliced_file_too_old(client, caller, relay, clock, tmp_path):
    online(relay)
    caller.offer(tmp_path, sliced_at=clock.now - routes.SLICE_MAX_AGE_SECONDS - 60)
    report = client.post('/printer/jobs', json={'token': 'tok'}).get_json()['error_report']
    assert report['code'] == 'delivery.sliced_file_too_old'
    assert report['action'] == 'slice_again'
    assert_contract_shape(report)


def test_daemon_never_reported(client, caller, tmp_path):
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.daemon_never_reported'
    assert report['retryable'] is True
    assert_contract_shape(report)


def test_no_printer_status(client, caller, relay, tmp_path):
    relay.note_code(CODE)
    relay.note_daemon(CODE)
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.no_printer_status'
    assert_contract_shape(report)


def test_printer_offline_names_the_minutes(client, caller, relay, clock, tmp_path):
    online(relay)
    clock.advance(7 * 60)
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.printer_offline'
    assert report['message'] == 'The printer was last heard from 7 minutes ago.'
    assert report['detail'] == 'Printer offline, last seen 7 min ago'
    assert_contract_shape(report)


def test_printer_busy(client, caller, relay, tmp_path):
    online(relay, running('other-jdeadbeef.gcode.3mf'))
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.printer_busy'
    assert report['detail'] == 'Printer busy, printing other.gcode.3mf at 42 percent'
    assert_contract_shape(report)


def test_printer_paused(client, caller, relay, tmp_path):
    online(relay, dict(IDLE, state='paused', file='other.gcode.3mf'))
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.printer_paused'
    assert_contract_shape(report)


def test_printer_unreachable(client, caller, relay, tmp_path):
    online(relay, dict(IDLE, state='unreachable'))
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.printer_unreachable'
    assert_contract_shape(report)


def test_printer_error_keeps_the_printer_code_in_the_detail_only(client, caller, relay,
                                                                tmp_path):
    online(relay, dict(IDLE, state='error', error='HMS_0300_0100_0001_0004'))
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.printer_error'
    assert 'HMS_' not in report['message'] + report['remedy']
    assert report['detail'] == 'Printer error: HMS_0300_0100_0001_0004'
    assert_contract_shape(report)


def test_job_in_flight(client, caller, relay, tmp_path):
    online(relay)
    caller.offer(tmp_path)
    assert client.post('/printer/jobs', json={'token': 'tok'}).status_code == 202
    report = refused_send(client, caller, tmp_path)
    assert report['code'] == 'delivery.job_in_flight'
    assert_contract_shape(report)


def test_rate_limited(client):
    for _ in range(routes.STATUS_LIMIT.count):
        client.get('/printer/status')
    report = client.get('/printer/status').get_json()['error_report']
    assert report['code'] == 'delivery.rate_limited'
    assert report['retryable'] is True
    assert_contract_shape(report)


# --- jobs that ended without a print ------------------------------------------------------

def test_job_not_picked_up(client, caller, relay, clock, tmp_path):
    online(relay)
    caller.offer(tmp_path)
    client.post('/printer/jobs', json={'token': 'tok'})
    clock.advance(3 * 60 + 1)
    report = last_result_report(client)
    assert report['code'] == 'delivery.job_not_picked_up'
    assert report['where'] == {'stage': 'pick_up'}
    assert_contract_shape(report)


def test_job_not_confirmed_is_not_retryable(client, caller, relay, clock, tmp_path):
    """The part may be printing already; sending again unchanged could print it twice."""
    online(relay)
    caller.offer(tmp_path)
    client.post('/printer/jobs', json={'token': 'tok'})
    relay.store_status(CODE, IDLE)
    clock.advance(15 * 60 + 1)
    report = last_result_report(client)
    assert report['code'] == 'delivery.job_not_confirmed'
    assert report['retryable'] is False
    assert_contract_shape(report)


def test_start_refused(client, relay):
    failed_job(relay, 'the printer refused the print start command')
    report = last_result_report(client)
    assert report['code'] == 'delivery.start_refused'
    assert_contract_shape(report)


def test_start_timeout(client, relay):
    failed_job(relay, 'the printer did not start the file within 60s')
    report = last_result_report(client)
    assert report['code'] == 'delivery.start_timeout'
    assert report['message'] == 'The printer did not show the print as started within 60 seconds.'
    assert report['retryable'] is False
    assert_contract_shape(report)


def test_printer_error_at_start(client, relay):
    failed_job(relay, 'printer error: HMS_0300_0100_0001_0004')
    report = last_result_report(client)
    assert report['code'] == 'delivery.printer_error_at_start'
    assert_contract_shape(report)


@pytest.mark.parametrize('reason', [
    'download answered 404',
    'GET /printer/download/<token> failed: timed out',
    "OSError('connection refused')",
    None,
])
def test_job_failed_for_any_other_reason(client, relay, reason):
    failed_job(relay, reason)
    report = last_result_report(client)
    assert report['code'] == 'delivery.job_failed'
    assert report['detail'] == (reason or '')
    assert_contract_shape(report)


# --- the adapter itself -------------------------------------------------------------------

def test_a_download_token_never_reaches_any_field():
    report = errors.error_report('GET /printer/download/s3cr3t-t0ken failed: reset')
    assert 's3cr3t' not in str(report)
    assert report['detail'] == 'GET /printer/download/<token> failed: reset'


def test_every_rule_is_reachable_and_produces_the_contract_shape():
    """Each rule's own example text must land on that rule, not on an earlier one."""
    examples = {
        'delivery.no_session': 'Session verification required.',
        'delivery.identity_unreadable': 'Could not read who is asking: ValueError: x',
        'delivery.sliced_file_unreadable': 'Could not read the sliced file: OSError: x',
        'delivery.not_paired': 'No printer paired',
        'delivery.sliced_file_missing': 'File not found or expired',
        'delivery.sliced_file_too_old': 'slice again',
        'delivery.daemon_never_reported': ('The Pi has not reported since the service '
                                           'started; check the setup guide.'),
        'delivery.no_printer_status': 'No printer reporting yet; try again in a moment.',
        'delivery.printer_offline': 'Printer offline, last seen 0 min ago',
        'delivery.printer_busy': 'Printer busy, printing a file at None percent',
        'delivery.printer_paused': 'Paused, a file',
        'delivery.printer_unreachable': 'Printer unreachable from the Pi',
        'delivery.printer_error': 'Printer error: unknown',
        'delivery.job_in_flight': 'A job is already on its way to the printer',
        'delivery.rate_limited': 'Too Many Requests: 10 per 1 minute',
        'delivery.job_not_picked_up': 'printer did not pick up the job',
        'delivery.job_not_confirmed': 'printer did not confirm the job',
        'delivery.start_refused': 'the printer refused the print start command',
        'delivery.start_timeout': 'the printer did not start the file within 60s',
        'delivery.printer_error_at_start': 'printer error: unknown',
    }
    assert set(examples) == {rule.code for rule in errors.RULES}
    for code, text in examples.items():
        report = errors.error_report(text)
        assert report['code'] == code, text
        assert_contract_shape(report)


@pytest.mark.parametrize('value, text', [
    (None, None), ('', None), (0, None), ([], None), ({}, None), (False, None),
    ('download answered 404', 'download answered 404'),
    (503, '503'), (True, 'true'), (['a', 1], '["a", 1]'), ({'b': 2, 'a': 1}, '{"a": 1, "b": 2}'),
    ('GET /printer/download/s3cr3t failed', 'GET /printer/download/<token> failed'),
    ({'url': '/printer/download/s3cr3t'}, '{"url": "/printer/download/<token>"}'),
])
def test_an_acknowledgement_reason_becomes_one_string_without_a_token(value, text):
    assert errors.reason_text(value) == text


@pytest.mark.parametrize('value', [503, ['a'], {'a': 1}, None])
def test_error_report_accepts_a_reason_that_is_not_a_string(value):
    report = errors.error_report(value)
    assert report['code'] == 'delivery.job_failed'
    assert report['detail'] == (errors.reason_text(value) or '')
    assert_contract_shape(report)


def test_an_exception_becomes_one_line_naming_its_class_without_a_token():
    assert errors.exception_text(OSError('first\nsecond')) == 'OSError: first'
    assert errors.exception_text(KeyError()) == 'KeyError'
    assert errors.exception_text(ValueError('/printer/download/s3cr3t')) == \
        'ValueError: /printer/download/<token>'
    assert len(errors.exception_text(ValueError('x' * 500))) == 200


def test_codes_are_unique():
    codes = [rule.code for rule in errors.RULES] + [errors.FALLBACK.code]
    assert len(codes) == len(set(codes))


def test_a_stream_send_refused_for_a_busy_printer_reports_busy(client, caller, relay):
    """The report does not depend on where the sliced file came from."""
    online(relay, running('x.gcode.3mf'))
    caller.files['tok'] = SlicedFile(filename='s.gcode.3mf', stream=io.BytesIO(b'3mf'))
    report = client.post('/printer/jobs', json={'token': 'tok'}).get_json()['error_report']
    assert report['code'] == 'delivery.printer_busy'
