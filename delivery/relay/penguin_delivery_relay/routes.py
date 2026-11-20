"""The relay's HTTP routes.

Three audiences:
  * the caller, through `GET /printer/status` and `POST /printer/jobs`, identified by the
    caller's `identify` function;
  * the daemon, through /printer/daemon/* gated on a signed bearer token, and
    /printer/download/<token> for the sliced file;
  * the installer fetch, /install-printer.sh, when the caller gives an installer path.

All relay state lives in relay.py (no Flask there, no printer protocol here). Every
response body and status code is the original relay's, except for these additions:
`error_report` beside every failure the caller can see; the download route, which the
application the relay was ported from used to provide; and refusals, each with its error
report, where the original answered a bare 500 or accepted a send that could only fail
(the caller's `identify` or `find_sliced_file` raising, a stream that fails while copied,
a `path` that is not a file, a JSON body that is not an object).
"""

import math
import os
from dataclasses import dataclass
from typing import Callable, Optional

from flask import jsonify, request, send_file

from . import relay as relay_module
from .errors import error_report, exception_text, reason_text
from .caller import Team
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
EXCHANGE_LIMIT = Limit(60, 60.0)       # service-wide; 40 bits is out of reach at that rate
INSTALLER_LIMIT = Limit(30, 60.0)
DOWNLOAD_LIMIT = Limit(30, 60.0)       # what the original download route allowed

DOWNLOAD_PREFIX = '/printer/download/'


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
    installer_path: Optional[str] = None


def register_routes(app, ctx):
    """Add the relay's routes to `app`."""

    def log(*args):
        if ctx.log:
            ctx.log(*args)

    def event(kind, **fields):
        if ctx.on_event:
            ctx.on_event(kind, **fields)

    # --- helpers ---------------------------------------------------------------------

    def require_https(*, plain_text=False):
        """403 unless the request arrived over HTTPS, judged after ProxyFix, or the relay
        runs in development mode. `plain_text` is for the installer, whose caller is
        `curl ... | bash`: a comment line is inert in a shell, JSON is noise."""
        if request.is_secure or ctx.dev:
            return None
        if plain_text:
            return '# HTTPS required\n', 403, {'Content-Type': 'text/plain; charset=utf-8'}
        return jsonify({'error': 'HTTPS required'}), 403

    def maybe_seed_dev_code():
        if ctx.dev and ctx.dev_pairing_code:
            ctx.relay.seed_code(ctx.dev_pairing_code)

    def caller_failure(text, status):
        return jsonify({'error': text, 'error_report': error_report(text)}), status

    def unreadable_sliced_file(error):
        """The caller's find_sliced_file raised, or its stream failed while copied: a JSON
        error report, never a bare 500 page. The same line goes to the log."""
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
        """(team or None, the caller function's exception or None). A caller function that
        raises reads as a team with no code, and the exception is handed back so a send can
        say what really happened."""
        try:
            team = ctx.identify(request)
        except Exception as e:      # a stale cookie must not turn a poll into a 500
            log(f"⚠️  Printer: unreadable identity: {e}")
            return Team(pairing_code=None), e
        return team, None

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
        """The job as the daemon receives it: the four fields of the wire shape."""
        if not job:
            return None
        return {'id': job['id'], 'download_path': job['download_path'],
                'filename': job['filename'], 'created_at': job['created_at']}

    def housekeeping():
        """After every relay read: drop the sliced files of jobs the relay no longer holds,
        then report every job that died on a deadline. Always AFTER the read, because the
        lazy deadlines are applied inside it."""
        ctx.files.prune(lambda code, job_id: ctx.relay.held_job_id(code) == job_id)
        for expired in ctx.relay.drain_expiry_events():
            log(f"🖨️  Printer job {expired.job_id} expired: {expired.reason}")
            event('printer_ack', team_number=expired.team_number,
                  metadata={'job_id': expired.job_id, 'ok': False,
                            'error': expired.reason, 'expired': True})

    def with_error_reports(payload):
        last = payload.get('last_result')
        if last is not None and not last['ok']:
            last['error_report'] = error_report(last['reason'])
        return payload

    # --- caller routes ---------------------------------------------------------------

    @app.route('/printer/status')
    def printer_status():
        team, _unreadable = identify()
        code = team_code(team)
        refusal = limited('status', code_key(code), STATUS_LIMIT, caller=True)
        if refusal is not None:
            return refusal
        if team is None:
            return unauthorized_session()
        maybe_seed_dev_code()
        if code:
            ctx.relay.note_code(code)
        payload = ctx.relay.status_for(code)
        housekeeping()
        return jsonify(with_error_reports(payload))

    @app.route('/printer/jobs', methods=['POST'])
    def printer_jobs():
        team, unreadable = identify()
        code = team_code(team)
        refusal = limited('jobs', code_key(code), JOBS_LIMIT, caller=True)
        if refusal is not None:
            return refusal
        if team is None:
            return unauthorized_session()
        if unreadable is not None:
            return caller_failure(
                f'Could not read who is asking: {exception_text(unreadable)}', 401)
        if not code:
            return caller_failure('No printer paired', 409)
        ctx.relay.note_code(code)

        # A token that is not a non-empty string names nothing: the caller's function is
        # never asked about it, and it answers as an empty body does.
        token = json_object().get('token')
        sliced = None
        if isinstance(token, str) and token:
            try:
                sliced = ctx.find_sliced_file(token, team)
            except Exception as e:
                return unreadable_sliced_file(e)
        if not sliced:
            return caller_failure('File not found or expired', 404)
        # A path that is not a file now will not be one when the daemon downloads it:
        # refuse here, where "slice again" can still help, not seconds later as a failed job.
        if sliced.path is not None and not os.path.isfile(sliced.path):
            return caller_failure('File not found or expired', 404)
        if (sliced.sliced_at is not None
                and ctx.clock() - sliced.sliced_at > SLICE_MAX_AGE_SECONDS):
            return caller_failure('slice again', 409)

        job_id = relay_module.new_job_id()
        try:
            download_token = ctx.files.add(code, job_id, sliced)
        except Exception as e:      # the caller's stream failed while it was copied
            return unreadable_sliced_file(e)
        ok = False
        try:
            ok, reason, _job = ctx.relay.claim_job(
                code, job_id=job_id, download_path=f'{DOWNLOAD_PREFIX}{download_token}',
                filename=sliced.filename, team_number=team.team_number)
        finally:
            # Until here the file waited for its claim, out of every other request's
            # housekeeping (see sliced_files.py); now the wait ends either way.
            if ok:
                ctx.files.confirm(download_token)
            else:
                ctx.files.discard(download_token)
        housekeeping()
        if not ok:
            return caller_failure(reason, 409)

        log(f"🖨️  Printer job {job_id} queued: {sliced.filename}")
        event('printer_send', team_number=team.team_number, user=team.user,
              metadata={'job_id': job_id, 'filename': sliced.filename})
        return jsonify({'ok': True, 'job_id': job_id}), 202

    # --- daemon routes ---------------------------------------------------------------
    # All require HTTPS outside development mode. All but the exchange carry
    # Authorization: Bearer <token>, and every one of them validates the token BEFORE it
    # touches the relay, so an unverified code never reaches relay state.

    @app.route('/printer/daemon/pair', methods=['POST'])
    def printer_daemon_pair():
        refusal = limited('pair', 'printer-exchange', EXCHANGE_LIMIT)
        if refusal is not None:
            return refusal
        refusal = require_https()
        if refusal:
            return refusal
        maybe_seed_dev_code()
        code = relay_module.normalize_code(json_object().get('code'))
        if code and ctx.relay.begin_exchange(code):
            token = relay_module.issue_token(code, ctx.secret_key)
            log(f"🖨️  Printer daemon paired for code {relay_module.format_code(code)}")
            return jsonify({'token': token})
        # The SAME body for an unknown code, a code no caller has presented yet, and a
        # code whose daemon is already alive -- so a guesser learns nothing from the reply.
        return jsonify({'error': 'not paired'}), 404

    @app.route('/printer/daemon/sync', methods=['POST'])
    def printer_daemon_sync():
        code = authenticated_code()
        refusal = limited('sync', code_key(code), DAEMON_LIMIT)
        if refusal is not None:
            return refusal
        refusal = require_https()
        if refusal:
            return refusal
        if not code:
            return jsonify({'error': 'repair'}), 401
        ctx.relay.note_daemon(code)
        job = ctx.relay.store_status(code, json_object())
        housekeeping()
        return jsonify({'job': wire_job(job)})

    @app.route('/printer/daemon/jobs/<job_id>/ack', methods=['POST'])
    def printer_daemon_ack(job_id):
        code = authenticated_code()
        refusal = limited('ack', code_key(code), DAEMON_LIMIT)
        if refusal is not None:
            return refusal
        refusal = require_https()
        if refusal:
            return refusal
        if not code:
            return jsonify({'error': 'repair'}), 401
        ctx.relay.note_daemon(code)
        body = json_object()
        ok = bool(body.get('ok'))
        # Stored, logged and reported as one string with no download token in it: the
        # status line builds an error report from it and shows it beside that report.
        reason = reason_text(body.get('error'))
        found, team_number = ctx.relay.finish_job(code, job_id, ok=ok, reason=reason)
        housekeeping()
        if not found:
            # The daemon treats this as final: the relay no longer holds that job.
            return jsonify({'error': 'unknown job'}), 404
        log(f"🖨️  Printer job {job_id} acknowledged: {'ok' if ok else reason}")
        event('printer_ack', team_number=team_number,
              metadata={'job_id': job_id, 'ok': ok, 'error': reason})
        return jsonify({'ok': True})

    @app.route('/printer/daemon/ping')
    def printer_daemon_ping():
        code = authenticated_code()
        refusal = limited('ping', code_key(code), DAEMON_LIMIT)
        if refusal is not None:
            return refusal
        refusal = require_https()
        if refusal:
            return refusal
        if not code:
            return jsonify({'error': 'repair'}), 401
        # Read-only on purpose: `penguincam-printer status` must not be able to disturb the
        # running service, so this does NOT record daemon_seen_at and hands out no job.
        return jsonify(ctx.relay.ping(code))

    @app.route(f'{DOWNLOAD_PREFIX}<token>')
    def printer_download(token):
        """The sliced file of a job the relay still holds. No bearer header: the token in
        the path is the whole authority, as it was on the original download route."""
        refusal = limited('download', address_key(), DOWNLOAD_LIMIT)
        if refusal is not None:
            return refusal
        housekeeping()
        held = ctx.files.get(token)
        if held is None or not os.path.isfile(held.path):
            return jsonify({'error': 'File not found or expired'}), 404
        return send_file(held.path, mimetype='application/octet-stream',
                         as_attachment=True, download_name=held.filename)

    # --- the installer ---------------------------------------------------------------

    if ctx.installer_path:
        installer_dir, installer_name = os.path.split(os.path.abspath(ctx.installer_path))

        @app.route('/install-printer.sh')
        def install_printer_sh():
            """A convenience alias for the installer. The documented command fetches the
            script from GitHub pinned to a commit instead, because a challenge page piped
            into bash fails confusingly."""
            refusal = limited('installer', address_key(), INSTALLER_LIMIT)
            if refusal is not None:
                return refusal
            refusal = require_https(plain_text=True)
            if refusal:
                return refusal
            return send_file(os.path.join(installer_dir, installer_name),
                             mimetype='text/x-shellscript')
