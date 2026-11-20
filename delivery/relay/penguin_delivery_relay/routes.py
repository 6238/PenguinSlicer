"""The relay's HTTP routes.

Two audiences:
  * the caller, through `GET /printer/status`, `POST /printer/jobs` and the delivery job
    routes under `/printer/jobs/<id>`, identified by the caller's `identify` function;
  * the daemon, through /printer/daemon/* gated on a signed bearer token, and
    /printer/download/<token> for the sliced file.

All relay state lives in relay.py (no Flask there, no printer protocol here). Every failure
a caller can meet carries an error report: refusals beside their one line of text, a caller
function that raises or answers with the wrong type, and, as a backstop, any exception that
escapes a route (`delivery.relay_failed`, never a bare 500 page).

Every request writes one structured log line (`printer-delivery request=...`), and every
transition of a delivery job one more (`printer-delivery event=transition ...`). A pairing
code appears in no log line: the printer is named by `printer_tag`, a hash of its code.
"""

import json
import math
import numbers
import os
from dataclasses import dataclass
from typing import Callable, Optional

from flask import Response, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from . import deliveries as dl
from . import relay as relay_module
from .caller import SlicedFile, Team
from .errors import (MAX_DETAIL_CHARS, error_report, exception_text, reason_text,
                     report_for_code)
from .limits import Limit, RateLimiter
from .sliced_files import SlicedFileStore

# A sliced file older than this is refused with "slice again". In the application the relay
# was ported from, the file was deleted an hour after it was made, and forty minutes keeps
# both job deadlines (3 min to pick up, 15 to confirm) clear of that deletion. Applied only
# when the caller says when the file was made (SlicedFile.sliced_at).
SLICE_MAX_AGE_SECONDS = 40 * 60

STATUS_LIMIT = Limit(120, 60.0)        # ten open status lines per team, polling every 5 s
JOBS_LIMIT = Limit(10, 60.0)
DAEMON_LIMIT = Limit(60, 60.0)
SYNC_LIMIT = Limit(120, 60.0)          # a sync a second while an upload moves, and room
EXCHANGE_LIMIT = Limit(60, 60.0)       # service-wide; 40 bits is out of reach at that rate
DOWNLOAD_LIMIT = Limit(30, 60.0)       # what the original download route allowed

DOWNLOAD_PREFIX = '/printer/download/'
#: How long a progress stream waits for news before it says it is still there.
STREAM_HEARTBEAT_SECONDS = 15.0


@dataclass
class RelayContext:
    """Everything the routes share, kept on app.extensions['penguin_delivery_relay']."""

    relay: relay_module.PrinterRelay
    files: SlicedFileStore
    limiter: RateLimiter
    secret_key: str
    identify: Callable
    find_sliced_file: Callable
    clock: Callable
    log: Optional[Callable] = None
    on_event: Optional[Callable] = None
    dev: bool = False
    dev_pairing_code: Optional[str] = None
    # `stream_wait(code, job_id, after_sequence, timeout)` -> the latest report: how a
    # progress stream waits for news. The relay's own condition by default; tests inject a
    # scripted one so a stream runs without any waiting.
    stream_wait: Optional[Callable] = None


#: The most characters one value of a log line carries; the line names what was cut.
MAX_LOG_FIELD_CHARS = 200
#: The largest request body the relay reads. Every body it expects is a few hundred bytes
#: (a snapshot, an acknowledgement, a send's token); a larger one is refused with
#: `delivery.request_too_large` before it is read.
MAX_REQUEST_BYTES = 64 * 1024
#: The most characters of a failure code a daemon's acknowledgement may carry.
MAX_CODE_CHARS = 80


def _field(value):
    """One value of a structured log line: plain when it has no space, else JSON. Cut to
    MAX_LOG_FIELD_CHARS, so no line grows with what a daemon or a caller sent."""
    if value is None:
        return '-'
    text = str(value)
    if len(text) > MAX_LOG_FIELD_CHARS:
        text = f'{text[:MAX_LOG_FIELD_CHARS]}...[{len(text) - MAX_LOG_FIELD_CHARS} cut]'
    if text and not any(ch.isspace() or ch in '"=' for ch in text):
        return text
    return json.dumps(text)


def register_routes(app, ctx):
    """Add the relay's routes to `app`."""

    def log(*args):
        if ctx.log:
            ctx.log(*args)

    def log_line(kind, name, **fields):
        """One structured line: `printer-delivery <kind>=<name> key=value ...`."""
        parts = [f'printer-delivery {kind}={_field(name)}']
        parts += [f'{key}={_field(value)}' for key, value in fields.items()]
        log(' '.join(parts))

    def event(kind, **fields):
        if ctx.on_event:
            ctx.on_event(kind, **fields)

    # --- helpers ---------------------------------------------------------------------

    def require_https():
        """403 unless the request arrived over HTTPS, judged after ProxyFix, or the relay
        runs in development mode."""
        if request.is_secure or ctx.dev:
            return None
        return jsonify({'error': 'HTTPS required'}), 403

    def maybe_seed_dev_code():
        if ctx.dev and ctx.dev_pairing_code:
            ctx.relay.seed_code(ctx.dev_pairing_code)

    def caller_failure(text, status, **fields):
        return jsonify({'error': text, 'error_report': error_report(text), **fields}), status

    def coded_failure(code, status, *, text, detail='', **fields):
        report = report_for_code(code, detail=detail, **fields)
        return jsonify({'error': text, 'error_report': report}), status

    def unreadable_sliced_file(error):
        """The caller's find_sliced_file raised or answered with the wrong type, or its
        stream failed while copied: a JSON error report, never a bare 500 page."""
        text = f'Could not read the sliced file: {exception_text(error)}'
        log(f"⚠️  Printer: {text}")
        return caller_failure(text, 500)

    def unauthorized_session():
        body = {'error': 'Session verification required.', 'need_verification': True,
                'error_report': error_report('Session verification required.')}
        return jsonify(body), 401

    def limited(name, key, limit, *, caller=False):
        """A 429 when this request is over its limit, else None."""
        retry_after = ctx.limiter.hit(name, key, limit)
        if retry_after is None:
            return None
        text = f'Too Many Requests: {limit}'
        body = {'error': text}
        if caller:
            body['error_report'] = error_report(text)
        response = jsonify(body)
        response.status_code = 429
        response.headers['Retry-After'] = str(max(1, math.ceil(retry_after)))
        return response

    def address_key():
        return request.remote_addr or 'unknown'

    def identify():
        """(team or None, the caller function's failure or None). A caller function that
        raises, or answers with something that is not a Team, reads as a team with no
        code, and the failure is handed back so a send can say what really happened."""
        try:
            team = ctx.identify(request)
        except Exception as e:      # a stale cookie must not turn a poll into a 500
            log(f"⚠️  Printer: unreadable identity: {exception_text(e)}")
            return Team(pairing_code=None), e
        if team is not None and not isinstance(team, Team):
            error = TypeError(f'identify returned {type(team).__name__}, not a Team')
            log(f"⚠️  Printer: unreadable identity: {exception_text(error)}")
            return Team(pairing_code=None), error
        return team, None

    def checked_sliced_file(value):
        """The caller's answer, or a TypeError naming what is wrong with it."""
        if value is None:
            return None
        if not isinstance(value, SlicedFile):
            raise TypeError(f'find_sliced_file returned {type(value).__name__}, '
                            'not a SlicedFile')
        if not isinstance(value.filename, str) or not value.filename:
            raise TypeError('find_sliced_file returned a SlicedFile with no filename')
        if value.path is not None and not isinstance(value.path, (str, os.PathLike)):
            raise TypeError(f'SlicedFile.path is {type(value.path).__name__}')
        if value.sliced_at is not None and (isinstance(value.sliced_at, bool)
                                            or not isinstance(value.sliced_at, numbers.Real)):
            raise TypeError(f'SlicedFile.sliced_at is {type(value.sliced_at).__name__}, '
                            'not a number')
        return value

    def json_object():
        """The request's JSON body when it is an object, else {} -- so a list, a string or a
        number answers exactly as an empty body does."""
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    def team_code(team):
        if team is None:
            return None
        return relay_module.normalize_code(team.pairing_code)

    def code_key(code):
        return f'printer-code:{code}' if code else address_key()

    def bearer_token():
        header = request.headers.get('Authorization', '')
        if header.startswith('Bearer '):
            return header[len('Bearer '):].strip()
        return None

    def authenticated_code():
        """The pairing code carried by a correctly signed bearer token, or None. Verified by
        signature alone: the relay may not have seen the code since it started."""
        payload = relay_module.read_token(bearer_token(), ctx.secret_key)
        return payload[0] if payload else None

    def wire_job(job):
        """The job as the daemon receives it."""
        if not job:
            return None
        wired = {'id': job['id'], 'download_path': job['download_path'],
                 'filename': job['filename'], 'created_at': job['created_at'],
                 'size': job.get('size'), 'sha256': job.get('sha256'),
                 'cancel': bool(job.get('cancel_requested')),
                 'start_granted': job.get('start_granted_to') is not None}
        # For a restarted daemon's hold on the printer (see "How a start is decided").
        for key in ('start_granted_age_s', 'previous_start'):
            if job.get(key) is not None:
                wired[key] = job[key]
        return wired

    def housekeeping():
        """After every relay read: sweep expired records, drop the sliced files of jobs the
        relay no longer holds, then report every job that died on a deadline and every
        transition. Always AFTER the read, because the lazy deadlines are applied in it."""
        ctx.relay.sweep()
        ctx.files.prune(lambda code, job_id: ctx.relay.held_job_id(code) == job_id)
        for expired in ctx.relay.drain_expiry_events():
            log(f"🖨️  Printer job {expired.job_id} expired: {expired.reason}")
            event('printer_ack', team_number=expired.team_number,
                  metadata={'job_id': expired.job_id, 'ok': False,
                            'error': expired.reason, 'expired': True})
        for step in ctx.relay.drain_transitions():
            log_line('event', 'transition', job=step.job_id,
                     printer=relay_module.printer_tag(step.code), team=step.team_number,
                     state=step.state, stage=step.stage, code=step.error_code)

    def with_error_reports(payload):
        last = payload.get('last_result')
        if last is not None and not last['ok'] and 'error_report' not in last:
            last['error_report'] = error_report(last['reason'])
        return payload

    def request_line(name, status, code=None, **fields):
        log_line('request', name, printer=relay_module.printer_tag(code), status=status,
                 **fields)

    # --- the backstop ----------------------------------------------------------------

    app.config['MAX_CONTENT_LENGTH'] = MAX_REQUEST_BYTES

    @app.errorhandler(413)
    def too_large(_error):
        """A body over MAX_REQUEST_BYTES: refused before it is read, with an error report."""
        request_line('too_large', 413, None, path=request.path,
                     bytes=request.content_length)
        report = report_for_code('delivery.request_too_large',
                                 detail=f'{request.content_length} bytes; at most '
                                        f'{MAX_REQUEST_BYTES} are read')
        return jsonify({'error': 'request too large', 'error_report': report}), 413

    @app.errorhandler(Exception)
    def unexpected(error):
        """Anything that escapes a route is an error report, never a bare 500 page."""
        if isinstance(error, HTTPException):
            return error
        text = f'The printer service failed: {exception_text(error)}'
        log_line('event', 'unexpected', path=request.path, error=exception_text(error))
        return jsonify({'error': text, 'error_report': error_report(text)}), 500

    # --- caller routes ---------------------------------------------------------------

    @app.route('/printer/status')
    def printer_status():
        team, _unreadable = identify()
        code = team_code(team)
        refusal = limited('status', code_key(code), STATUS_LIMIT, caller=True)
        if refusal is not None:
            request_line('status', 429, code, team=getattr(team, 'team_number', None),
                         error='rate_limited')
            return refusal
        if team is None:
            request_line('status', 401, code, error='not_signed_in')
            return unauthorized_session()
        maybe_seed_dev_code()
        if code:
            ctx.relay.note_code(code)
        payload = ctx.relay.status_for(code)
        housekeeping()
        request_line('status', 200, code, team=team.team_number,
                     state=(payload.get('status') or {}).get('state'),
                     job=(payload.get('job') or {}).get('id'))
        return jsonify(with_error_reports(payload))

    @app.route('/printer/jobs', methods=['POST'])
    def printer_jobs():
        team, unreadable = identify()
        code = team_code(team)
        refusal = limited('jobs', code_key(code), JOBS_LIMIT, caller=True)
        if refusal is not None:
            request_line('send', 429, code, team=getattr(team, 'team_number', None),
                         error='rate_limited')
            return refusal
        if team is None:
            request_line('send', 401, code, error='not_signed_in')
            return unauthorized_session()
        if unreadable is not None:
            request_line('send', 401, code, error='identity_unreadable')
            return caller_failure(
                f'Could not read who is asking: {exception_text(unreadable)}', 401)
        if not code:
            request_line('send', 409, code, team=team.team_number, error='not_paired')
            return caller_failure('No printer paired', 409)
        ctx.relay.note_code(code)

        # A token that is not a non-empty string names nothing: the caller's function is
        # never asked about it, and it answers as an empty body does.
        token = json_object().get('token')
        sliced = None
        if isinstance(token, str) and token:
            try:
                sliced = checked_sliced_file(ctx.find_sliced_file(token, team))
            except Exception as e:
                request_line('send', 500, code, team=team.team_number,
                             error='sliced_file_unreadable')
                return unreadable_sliced_file(e)
        if not sliced:
            request_line('send', 404, code, team=team.team_number, error='sliced_file_missing')
            return caller_failure('File not found or expired', 404)
        # A path that is not a file now will not be one when the daemon downloads it:
        # refuse here, where "slice again" can still help, not seconds later as a failed job.
        if sliced.path is not None and not os.path.isfile(sliced.path):
            request_line('send', 404, code, team=team.team_number, error='sliced_file_missing')
            return caller_failure('File not found or expired', 404)
        if (sliced.sliced_at is not None
                and ctx.clock() - sliced.sliced_at > SLICE_MAX_AGE_SECONDS):
            request_line('send', 409, code, team=team.team_number, error='sliced_file_too_old')
            return caller_failure('slice again', 409)

        job_id = relay_module.new_job_id()
        try:
            download_token = ctx.files.add(code, job_id, sliced)
        except Exception as e:      # the caller's stream failed while it was copied
            request_line('send', 500, code, team=team.team_number,
                         error='sliced_file_unreadable')
            return unreadable_sliced_file(e)
        held = ctx.files.get(download_token)
        ok = False
        try:
            ok, reason, _job = ctx.relay.claim_job(
                code, job_id=job_id, download_path=f'{DOWNLOAD_PREFIX}{download_token}',
                filename=sliced.filename, team_number=team.team_number,
                size=held.size, sha256=held.sha256)
        finally:
            # Until here the file waited for its claim, out of every other request's
            # housekeeping (see sliced_files.py); now the wait ends either way.
            if ok:
                ctx.files.confirm(download_token)
            else:
                ctx.files.discard(download_token)
        housekeeping()
        if not ok:
            request_line('send', 409, code, team=team.team_number,
                         error=error_report(reason)['code'])
            return caller_failure(reason, 409)

        log(f"🖨️  Printer job {job_id} queued: {sliced.filename}")
        request_line('send', 202, code, team=team.team_number, job=job_id,
                     file=sliced.filename, bytes=held.size)
        event('printer_send', team_number=team.team_number, user=team.user,
              metadata={'job_id': job_id, 'filename': sliced.filename})
        return jsonify({'ok': True, 'job_id': job_id}), 202

    def caller_team(name, limit):
        """(code, refusal): the identified team's code for a delivery job route. Every
        refusal leaves its line: the route, the refusal, the team when known."""
        team, unreadable = identify()
        code = team_code(team)
        team_number = getattr(team, 'team_number', None)
        job = (request.view_args or {}).get('job_id')
        refusal = limited(name, code_key(code), limit, caller=True)
        if refusal is not None:
            request_line(name, 429, code, team=team_number, job=job, error='rate_limited')
            return code, refusal
        if team is None or unreadable is not None:
            request_line(name, 401, code, team=team_number, job=job,
                         error='identity_unreadable' if unreadable is not None
                         else 'not_signed_in')
            return code, unauthorized_session()
        return code, None

    def unknown_job(name, code, job_id):
        request_line(name, 404, code, job=job_id, error='job_unknown')
        return coded_failure('delivery.job_unknown', 404, text='unknown job',
                             detail=f'no delivery job {job_id} for this printer')

    @app.route('/printer/jobs/<job_id>')
    def printer_job(job_id):
        """The latest progress report of one delivery job: what a late caller gets at once."""
        code, refusal = caller_team('job', STATUS_LIMIT)
        if refusal is not None:
            return refusal
        report = ctx.relay.delivery_report(code, job_id)
        housekeeping()
        if report is None:
            return unknown_job('job', code, job_id)
        request_line('job', 200, code, job=job_id, state=report['state'],
                     stage=report['stage'], sequence=report['sequence'])
        return jsonify(report)

    @app.route('/printer/jobs/<job_id>/events')
    def printer_job_events(job_id):
        """The delivery job's progress reports as a server-sent event stream: the latest at
        once, then each new one, until a final state. A comment line every
        STREAM_HEARTBEAT_SECONDS of quiet keeps proxies from closing it."""
        code, refusal = caller_team('events', STATUS_LIMIT)
        if refusal is not None:
            return refusal
        first = ctx.relay.delivery_report(code, job_id)
        if first is None:
            return unknown_job('events', code, job_id)
        request_line('events', 200, code, job=job_id, sequence=first['sequence'])
        wait = ctx.stream_wait or ctx.relay.wait_for_report

        def frames():
            report, last = first, None
            while True:
                if report is None:
                    gone = report_for_code('delivery.job_unknown',
                                           detail=f'delivery job {job_id} was dropped')
                    yield f"event: error\ndata: {json.dumps(gone)}\n\n"
                    return
                if (last is None or report['sequence'] != last['sequence']
                        or report.get('stale_age_s') != last.get('stale_age_s')):
                    yield (f"id: {report['sequence']}\nevent: progress\n"
                           f"data: {json.dumps(report, sort_keys=True)}\n\n")
                else:
                    yield ': still here\n\n'
                last = report
                if report['state'] in dl.FINAL:
                    return
                report = wait(code, job_id, report['sequence'], STREAM_HEARTBEAT_SECONDS)

        return Response(frames(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @app.route('/printer/jobs/<job_id>/cancel', methods=['POST'])
    def printer_job_cancel(job_id):
        code, refusal = caller_team('cancel', JOBS_LIMIT)
        if refusal is not None:
            return refusal
        outcome = ctx.relay.cancel(code, job_id)
        housekeeping()
        request_line('cancel', outcome, code, job=job_id)
        if outcome == 'unknown':
            return unknown_job('cancel', code, job_id)
        if outcome == 'too_late':
            return coded_failure('delivery.cancel_too_late', 409, text='too late to cancel',
                                 detail=f'the start command of delivery job {job_id} was '
                                        'sent to the printer')
        if outcome == 'being_sent':
            return coded_failure('delivery.start_being_sent', 409, text='too late to cancel',
                                 detail=f'delivery job {job_id} passed the start gate; the '
                                        'daemon has not yet said the command went')
        if outcome == 'final':
            return coded_failure('delivery.already_finished', 409, text='already finished',
                                 detail=f'delivery job {job_id} has ended')
        report = ctx.relay.delivery_report(code, job_id)
        return jsonify({'ok': True, 'outcome': outcome, 'progress': report}), \
            (200 if outcome == 'cancelled' else 202)

    @app.route('/printer/jobs/<job_id>/stop-following', methods=['POST'])
    def printer_job_stop_following(job_id):
        """The caller gives up a delivery job past the start gate whose report is stale:
        it ends `failed`, `delivery.outcome_unknown`. Refused while the printer still
        reports it (`delivery.still_reporting`), and before the gate (`delivery.not_started`:
        cancel it instead)."""
        code, refusal = caller_team('stop_following', JOBS_LIMIT)
        if refusal is not None:
            return refusal
        outcome = ctx.relay.stop_following(code, job_id)
        housekeeping()
        request_line('stop_following', outcome, code, job=job_id)
        if outcome == 'unknown':
            return unknown_job('stop_following', code, job_id)
        if outcome == 'final':
            return coded_failure('delivery.already_finished', 409, text='already finished',
                                 detail=f'delivery job {job_id} has ended')
        if outcome == 'fresh':
            return coded_failure('delivery.still_reporting', 409, text='still reporting',
                                 detail=f'delivery job {job_id} has fresh word from the '
                                        'printer')
        if outcome == 'not_shown':
            return coded_failure('delivery.start_not_shown_yet', 409, text='not shown yet',
                                 detail=f'delivery job {job_id} has fresh word from the '
                                        'printer, which has not shown the print yet')
        if outcome == 'not_started':
            return coded_failure('delivery.not_started', 409, text='not started',
                                 detail=f'delivery job {job_id} has not passed the start '
                                        'gate')
        report = ctx.relay.delivery_report(code, job_id)
        return jsonify({'ok': True, 'outcome': outcome, 'progress': report}), 200

    # --- daemon routes ---------------------------------------------------------------
    # All require HTTPS outside development mode. All but the exchange carry
    # Authorization: Bearer <token>, and every one of them validates the token BEFORE it
    # touches the relay, so an unverified code never reaches relay state.

    @app.route('/printer/daemon/pair', methods=['POST'])
    def printer_daemon_pair():
        refusal = limited('pair', 'printer-exchange', EXCHANGE_LIMIT)
        if refusal is not None:
            request_line('pair', 429, error='rate_limited')
            return refusal
        refusal = require_https()
        if refusal:
            request_line('pair', 403, error='https_required')
            return refusal
        maybe_seed_dev_code()
        code = relay_module.normalize_code(json_object().get('code'))
        if code and ctx.relay.begin_exchange(code):
            token = relay_module.issue_token(code, ctx.secret_key)
            request_line('pair', 200, code)
            return jsonify({'token': token})
        # The SAME body for an unknown code, a code no caller has presented yet, and a
        # code whose daemon is already alive -- so a guesser learns nothing from the reply.
        request_line('pair', 404, code, error='not_paired')
        return jsonify({'error': 'not paired'}), 404

    def daemon_gate(name, limit):
        """(code, refusal) for a daemon route: the limit, HTTPS and the token."""
        code = authenticated_code()
        refusal = limited(name, code_key(code), limit)
        if refusal is not None:
            request_line(name, 429, code, error='rate_limited')
            return code, refusal
        refusal = require_https()
        if refusal:
            request_line(name, 403, code, error='https_required')
            return code, refusal
        if not code:
            request_line(name, 401, error='token_invalid')
            return code, (jsonify({'error': 'repair'}), 401)
        return code, None

    @app.route('/printer/daemon/sync', methods=['POST'])
    def printer_daemon_sync():
        code, refusal = daemon_gate('sync', SYNC_LIMIT)
        if refusal is not None:
            return refusal
        ctx.relay.note_daemon(code)
        body = dict(json_object())
        progress = body.pop('job_progress', None)
        progress = progress if isinstance(progress, dict) else None
        job = ctx.relay.store_status(code, body, progress)
        housekeeping()
        kept = relay_module.bounded_snapshot(body) or {}
        request_line('sync', 200, code, state=kept.get('state'),
                     printer_job=kept.get('job_name') or kept.get('file'),
                     job=(job or {}).get('id'),
                     stage=(progress or {}).get('stage'))
        return jsonify({'job': wire_job(job)})

    @app.route('/printer/daemon/jobs/<job_id>/ack', methods=['POST'])
    def printer_daemon_ack(job_id):
        code, refusal = daemon_gate('ack', DAEMON_LIMIT)
        if refusal is not None:
            return refusal
        ctx.relay.note_daemon(code)
        body = json_object()
        ok = bool(body.get('ok'))
        # Stored, logged and reported as one string with no download token in it: the
        # status line builds an error report from it and shows it beside that report.
        reason = reason_text(body.get('error'))
        error_code = (body.get('code')[:MAX_CODE_CHARS] if isinstance(body.get('code'), str)
                      else None)
        detail = reason_text(body.get('detail'), MAX_DETAIL_CHARS)
        found, team_number = ctx.relay.finish_job(code, job_id, ok=ok, reason=reason,
                                                  error_code=error_code, detail=detail,
                                                  fields=body.get('fields'))
        housekeeping()
        if not found:
            # The daemon treats this as final: the relay no longer holds that job.
            request_line('ack', 404, code, job=job_id, ok=ok, code_reported=error_code)
            return jsonify({'error': 'unknown job'}), 404
        log(f"🖨️  Printer job {_field(job_id)} acknowledged: {'ok' if ok else reason}")
        request_line('ack', 200, code, job=job_id, ok=ok, code_reported=error_code,
                     reason=reason)
        event('printer_ack', team_number=team_number,
              metadata={'job_id': job_id, 'ok': ok, 'error': reason, 'code': error_code})
        return jsonify({'ok': True})

    @app.route('/printer/daemon/jobs/<job_id>/start', methods=['POST'])
    def printer_daemon_start(job_id):
        """The start gate: the daemon asks, and starts the file only on {"start": true}."""
        code, refusal = daemon_gate('start', DAEMON_LIMIT)
        if refusal is not None:
            return refusal
        ctx.relay.note_daemon(code)
        instance = json_object().get('instance')
        outcome = ctx.relay.grant_start(code, job_id,
                                        instance if isinstance(instance, str) else '')
        housekeeping()
        status = {'unknown': 404, 'no_instance': 400}.get(outcome, 200)
        request_line('start', status, code, job=job_id, outcome=outcome)
        if outcome == 'unknown':
            return jsonify({'error': 'unknown job'}), 404
        if outcome == 'no_instance':
            # A start nobody can hold to the at-most-once rule: refused, with an error
            # report, since only a daemon not of this version can reach it.
            return coded_failure('delivery.start_without_instance', 400,
                                 text='the start gate needs the daemon process to name '
                                      'itself',
                                 detail=f'instance {instance!r:.80}')
        return jsonify({'start': outcome == 'start', 'outcome': outcome})

    @app.route('/printer/daemon/ping')
    def printer_daemon_ping():
        code, refusal = daemon_gate('ping', DAEMON_LIMIT)
        if refusal is not None:
            return refusal
        # Read-only on purpose: `status` must not be able to disturb the running daemon,
        # so this does NOT record daemon_seen_at and hands out no job.
        request_line('ping', 200, code)
        return jsonify(ctx.relay.ping(code))

    @app.route(f'{DOWNLOAD_PREFIX}<token>')
    def printer_download(token):
        """The sliced file of a job the relay still holds. No bearer header: the token in
        the path is the whole authority, as it was on the original download route. The
        token is never logged."""
        refusal = limited('download', address_key(), DOWNLOAD_LIMIT)
        if refusal is not None:
            request_line('download', 429, error='rate_limited')
            return refusal
        housekeeping()
        held = ctx.files.get(token)
        if held is None or not os.path.isfile(held.path):
            request_line('download', 404, error='file_unknown')
            return jsonify({'error': 'File not found or expired'}), 404
        request_line('download', 200, held.code, job=held.job_id, bytes=held.size)
        return send_file(held.path, mimetype='application/octet-stream',
                         as_attachment=True, download_name=held.filename)
