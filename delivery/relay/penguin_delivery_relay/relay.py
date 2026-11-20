"""In-memory relay state for the printer daemon.

Keyed by the team's eight-character pairing code, which is the ONLY identity the relay
trusts: a caller can claim any team number it likes, but the pairing code is
forty random bits that live only with the team and on the team's Pi. Nothing here is
written to disk -- a restart empties the relay, and the daemon recovers by syncing again.

Deliberately free of Flask imports, so it unit-tests without an app and a caller can drive it
directly. Everything Flask-shaped lives in routes.py.
"""

import copy
import hashlib
import re
import secrets
import threading
import time
from collections import namedtuple, deque

from itsdangerous import URLSafeSerializer

from . import deliveries as dl
from . import errors

# Crockford base32 without I, L, O and U, so no two symbols look alike when a mentor reads
# the code off a Pi's console and types it into a YAML file.
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LENGTH = 8

TOKEN_SALT = "penguincam-printer"

# A daemon counts as heard, and a snapshot as fresh, for two minutes.
DAEMON_ONLINE_SECONDS = 120
STATUS_ONLINE_SECONDS = 120
# Records and snapshots are dropped a day after anything last touched them.
RECORD_TTL_SECONDS = 24 * 60 * 60
STATUS_TTL_SECONDS = 24 * 60 * 60
# Job deadlines: pick-up and confirmation.
JOB_PENDING_TIMEOUT_SECONDS = 3 * 60
JOB_HANDED_OUT_TIMEOUT_SECONDS = 15 * 60
# How long a finished job's outcome is shown on the status line.
LAST_RESULT_TTL_SECONDS = 10 * 60
# Every record and delivery job is swept at most this often, so a record nobody reads
# again still goes when its day is up.
SWEEP_EVERY_SECONDS = 60

#: What the relay keeps of a daemon's snapshot: these fields only, each string cut to
#: MAX_SNAPSHOT_TEXT characters and each number kept only when it is a plain finite one.
#: The snapshot is stored, served in every status answer and logged, so nothing in it may
#: grow with what a daemon sends.
SNAPSHOT_TEXT = ('state', 'file', 'job_name', 'error', 'stage', 'stage_label', 'waiting_for',
                 'waiting_label', 'at_the_printer', 'unrecognised')
SNAPSHOT_NUMBERS = ('percent', 'remaining_min', 'layer', 'layers', 'stage_code',
                    'report_age_s')
SNAPSHOT_PRINTER = ('model', 'name', 'serial')
MAX_SNAPSHOT_TEXT = 200
MAX_SNAPSHOT_NUMBER = 10 ** 9
#: The daemon process's name at the start gate, as stored.
MAX_INSTANCE_CHARS = 64
#: The printer states in which a new send may go ahead: no print, or the last print ended,
#: well or badly. Every other state refuses it (see PrinterRelay._refusal).
FREE_STATES = frozenset({'idle', 'finished', 'error'})


def _bounded_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or abs(value) > MAX_SNAPSHOT_NUMBER:       # NaN, infinity, huge
        return None
    return value


def bounded_snapshot(snapshot):
    """The part of a daemon's snapshot the relay keeps (see SNAPSHOT_TEXT), or None."""
    if not isinstance(snapshot, dict):
        return None
    kept = {}
    for key in SNAPSHOT_TEXT:
        value = snapshot.get(key)
        if isinstance(value, str):
            kept[key] = value[:MAX_SNAPSHOT_TEXT]
        elif value is None and key in snapshot:
            kept[key] = None
    for key in SNAPSHOT_NUMBERS:
        if key in snapshot:
            kept[key] = _bounded_number(snapshot.get(key))
    printer = snapshot.get('printer')
    if isinstance(printer, dict):
        kept['printer'] = {key: printer[key][:MAX_SNAPSHOT_TEXT]
                           if isinstance(printer.get(key), str) else None
                           for key in SNAPSHOT_PRINTER}
    return kept


# Emitted by the relay when a job dies on a deadline; the routes drain these and log a
# printer_ack metrics event, so the metrics show every job's end, not just the acked ones.
ExpiryEvent = namedtuple('ExpiryEvent', 'code job_id team_number reason')
# Emitted on every change of a delivery job's state or stage, for the log.
Transition = namedtuple('Transition', 'code job_id team_number state stage error_code')


def printer_tag(code):
    """A short stable name for a pairing code in logs: never the code itself, which is a
    credential. Eight hex digits of its SHA-256."""
    if not code:
        return '-'
    return hashlib.sha256(f'penguin-delivery:{code}'.encode()).hexdigest()[:8]


def generate_code():
    """A fresh pairing code: eight symbols, forty bits, never all digits.

    An all-digit code would be read out of an unquoted YAML value as an int, so it is
    redrawn -- that way the mentor can quote it or not and the file still works."""
    while True:
        code = ''.join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if not code.isdigit():
            return code


def normalize_code(value):
    """The canonical form of a pairing code, or None when it is not one.

    Accepts what a mentor might actually type or what YAML might hand us: lower case, a
    dash or spaces, an int from an unquoted all-digit value. O becomes 0; I and L become 1.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        return None
    cleaned = value.strip().upper().replace('-', '').replace(' ', '')
    cleaned = cleaned.replace('O', '0').replace('I', '1').replace('L', '1')
    if len(cleaned) != CODE_LENGTH:
        return None
    if any(ch not in ALPHABET for ch in cleaned):
        return None
    return cleaned


def format_code(code):
    """Display form: two groups of four separated by a dash."""
    return f"{code[:4]}-{code[4:]}"


# The job id the daemon bakes into the uploaded file name, e.g. the '-j8f3a2c1' in
# 'sample_part-j8f3a2c1.gcode.3mf'. Anchored on the extension so only a real suffix matches.
# new_job_id() draws eight hex digits; a seven-digit id such as 'j8f3a2c1' is
# accepted too, so a name written by hand from the documentation still reads back cleanly.
# The H2S reports the name without its extension (`subtask_name`), so a suffix at the very
# end is a suffix too.
_JOB_SUFFIX_RE = re.compile(r'-j[0-9a-fA-F]{7,8}(?=(\.gcode\.3mf)?$)')


def strip_job_suffix(name):
    """The printer's reported file name with the job id taken back out.

    The daemon uploads 'sample_part-j8f3a2c1.gcode.3mf' so the printer's own display names
    the job; a student reading PenguinCAM should see 'sample_part.gcode.3mf'. Any other
    name -- one printed from an SD card, say -- is left exactly as the printer reported it."""
    if not isinstance(name, str):
        return name
    return _JOB_SUFFIX_RE.sub('', name)


def new_job_id():
    """A short opaque job id, e.g. 'j8f3a2c1'. It is also baked into the file name the
    daemon uploads, so the printer's reported name identifies the job."""
    return 'j' + secrets.token_hex(4)


def _serializer(secret_key):
    return URLSafeSerializer(secret_key, salt=TOKEN_SALT)


def issue_token(code, secret_key, *, issued_at=None):
    """Sign a daemon credential carrying the code and the issue time.

    No expiry: retiring a Pi means the caller no longer presents its code, after which no
    fresh send names it. The issue time is for logging only and is never compared with
    any clock."""
    payload = {'code': code, 'iat': float(issued_at if issued_at is not None else time.time())}
    return _serializer(secret_key).dumps(payload)


def read_token(token, secret_key):
    """(code, issued_at) for a correctly signed token, else None. Never raises."""
    if not token or not isinstance(token, str):
        return None
    try:
        payload = _serializer(secret_key).loads(token)
    except Exception:  # a bad signature, a bad payload -- any decode failure is just "no"
        return None
    if not isinstance(payload, dict):
        return None
    code = normalize_code(payload.get('code'))
    if code is None:
        return None
    try:
        issued_at = float(payload.get('iat', 0.0))
    except (TypeError, ValueError):
        issued_at = 0.0
    return code, issued_at


class _Record:
    """One printer, keyed by its normalised pairing code. Plain attributes; every access
    happens under PrinterRelay's single lock."""

    __slots__ = ('session_seen_at', 'daemon_seen_at', 'status', 'status_received_at',
                 'job', 'last_result', 'last_result_at', 'touched_at', 'latest_delivery',
                 'last_grant')

    def __init__(self, now):
        self.session_seen_at = None
        self.daemon_seen_at = None
        self.status = None
        self.status_received_at = None
        self.job = None                 # {'id','download_path','filename','created_at',
                                        #  'state','team_number','handed_out_at'}
        self.last_result = None         # {'ok': bool, 'reason': str | None,
                                        #  'job_id': str, 'team_number': int | None}
        self.last_result_at = None
        self.touched_at = now
        self.latest_delivery = None     # the id of this printer's most recent delivery job
        self.last_grant = None          # {'id', 'filename', 'at'}: the last start granted


class PrinterRelay:
    """Every printer record the process knows about, behind one lock.

    Expiry is lazy: there is no thread. Each read applies the job deadlines, drops a
    day-old snapshot and deletes a record nothing has touched for a day, all against the
    injected clock -- which is what makes the deadlines testable without sleeping.
    """

    def __init__(self, clock=time.time):
        self._clock = clock
        self._lock = threading.RLock()
        # Signalled on every change of any delivery job, under the same lock, so a progress
        # stream waits on an event rather than polling.
        self._changed = threading.Condition(self._lock)
        self._records = {}
        self._expiry_events = deque()
        self._deliveries = {}           # job id -> Delivery
        self._transitions = deque()
        self._last_sweep = None

    # -- housekeeping -----------------------------------------------------------------

    def _touch(self, record):
        record.touched_at = self._clock()

    def _is_fresh(self, record, now):
        """Is this record's snapshot inside the two-minute window? Caller holds the lock.

        The single definition of "online": status_for, ping and _refusal all read it, so the
        status line and a send refusal can never disagree about the same instant. The
        comparison is on the raw float -- truncating the age to whole seconds first would
        call a 120.5 second old snapshot fresh in one place and stale in another."""
        if record.status_received_at is None:
            return False
        return now - record.status_received_at <= STATUS_ONLINE_SECONDS

    def _expire(self, code, record):
        """Apply every lazy deadline to one record. Caller holds the lock.

        Returns False when the record itself has expired and should be dropped."""
        now = self._clock()
        if now - record.touched_at > RECORD_TTL_SECONDS:
            return False
        if record.status_received_at is not None and now - record.status_received_at > STATUS_TTL_SECONDS:
            record.status = None
            record.status_received_at = None
        job = record.job
        if job is not None:
            if job['state'] == 'pending' and now - job['created_at'] > JOB_PENDING_TIMEOUT_SECONDS:
                self._finish(code, record, job, ok=False,
                             reason='printer did not pick up the job', record_event=True,
                             error_code='delivery.job_not_picked_up')
            elif (job['state'] == 'handed_out' and not job.get('start_granted_to')
                  and now - job['handed_out_at'] > JOB_HANDED_OUT_TIMEOUT_SECONDS):
                # Only a job whose start was never granted ends on this deadline: from
                # here the start gate answers 'unknown', so the file can never be started,
                # and the evidence for the ending is the gate itself. A job past the gate
                # is never ended by a timer: the print may be running while the link is
                # down, so it stays in progress (marked stale) until the daemon or the
                # printer's own report says how it went.
                self._finish(code, record, job, ok=False,
                             reason='printer did not confirm the job', record_event=True,
                             error_code=('delivery.cancelled' if job.get('cancel_requested')
                                         else 'delivery.job_not_confirmed'),
                             detail=f'no start asked for within '
                                    f'{JOB_HANDED_OUT_TIMEOUT_SECONDS} s of the hand-out',
                             fields={'minutes': JOB_HANDED_OUT_TIMEOUT_SECONDS // 60})
        if (record.last_result_at is not None
                and now - record.last_result_at > LAST_RESULT_TTL_SECONDS):
            record.last_result = None
            record.last_result_at = None
        return True

    def _finish(self, code, record, job, *, ok, reason, record_event=False, error_code=None,
                detail=None, fields=None):
        """Record a job's outcome and clear the job slot. Caller holds the lock.

        `record_event` is set only by the lazy deadlines: a job that dies on a deadline is
        never acknowledged, so the relay raises the metrics event itself. A real
        acknowledgement is logged by the ack route instead, so setting it here too would
        double-count.

        The delivery job lives on: an ok start moves it to `printing`, a cancel to
        `cancelled`, anything else to `failed` with its error report."""
        now = self._clock()
        record.job = None
        report = None if ok else errors.error_report(reason, code=error_code, detail=detail,
                                                     fields=fields)
        if error_code == 'delivery.cancelled':
            report = None
        record.last_result = {'ok': ok, 'reason': reason, 'job_id': job['id'],
                              'team_number': job.get('team_number'),
                              'error_report': report,
                              'cancelled': error_code == 'delivery.cancelled'}
        record.last_result_at = now
        if record_event:
            self._expiry_events.append(
                ExpiryEvent(code, job['id'], job.get('team_number'), reason))
        delivery = self._deliveries.get(job['id'])
        if delivery is not None:
            if ok:
                delivery.started(now)
            elif delivery.stage in dl.FOLLOWING and not delivery.final:
                # The printer's own report already named this job's file as its print:
                # that outranks a failure the daemon reported about the start, so the
                # delivery job goes on following the print.
                pass
            elif error_code == 'delivery.cancelled':
                delivery.cancel(now)
            else:
                delivery.fail(now, report)
            self._note(delivery)

    def _note(self, delivery):
        """Queue the delivery job's new transitions for the log and wake every stream.
        Caller holds the lock.

        A delivery job that has ended, by whatever route (the printer's report, the
        caller's stop-following, the day without word), frees its job slot here, so the
        printer's queue never waits on an acknowledgement that may never come."""
        if delivery.final:
            record = self._records.get(delivery.code)
            if (record is not None and record.job is not None
                    and record.job['id'] == delivery.job_id):
                job = record.job
                record.job = None
                record.last_result = {
                    'ok': delivery.state == dl.DONE,
                    'reason': None if delivery.error is None else delivery.error['message'],
                    'job_id': job['id'], 'team_number': job.get('team_number'),
                    'error_report': copy.deepcopy(delivery.error),
                    'cancelled': delivery.state == dl.CANCELLED}
                record.last_result_at = self._clock()
        for state, stage in delivery.transitions:
            error_code = (delivery.error or {}).get('code') if state == dl.FAILED else None
            self._transitions.append(Transition(delivery.code, delivery.job_id,
                                                delivery.team_number, state, stage,
                                                error_code))
        delivery.transitions.clear()
        self._changed.notify_all()

    def drain_transitions(self):
        """Take and clear the delivery jobs' transitions since the last call."""
        with self._lock:
            items = list(self._transitions)
            self._transitions.clear()
        return items

    def _get(self, code, create=False):
        """The live record for a code, expiring it first. Caller holds the lock."""
        if code is None:
            return None
        record = self._records.get(code)
        if record is not None and not self._expire(code, record):
            del self._records[code]
            record = None
        if record is None and create:
            record = _Record(self._clock())
            self._records[code] = record
        return record

    def drain_expiry_events(self):
        """Take and clear the expiry events recorded since the last call. The routes log a
        printer_ack metrics event for each, so a job that died on a deadline still shows up
        in the metrics."""
        with self._lock:
            events = list(self._expiry_events)
            self._expiry_events.clear()
        return events

    # -- how a code becomes known ------------------------------------------------------

    def note_code(self, code):
        """The caller has presented this pairing code for a team it vouches for. The only way
        a code becomes known to the relay (besides seed_code in development). Returns the
        normalised code, or None if it was not one."""
        code = normalize_code(code)
        if code is None:
            return None
        with self._lock:
            record = self._get(code, create=True)
            record.session_seen_at = self._clock()
            self._touch(record)
        return code

    def seed_code(self, code):
        """Development only: pretend the caller presented this code, so a daemon can pair
        against a relay no team has used yet. Wired to create_app's dev_pairing_code, which
        the routes honour ONLY in development mode."""
        return self.note_code(code)

    def note_daemon(self, code):
        """A request carrying a valid token for this code arrived. Creates the record if
        the relay restarted since the session last presented the code.

        Returns the normalised code, or None if it was not one -- a malformed code makes no
        record and raises nothing."""
        code = normalize_code(code)
        if code is None:
            return None
        with self._lock:
            record = self._get(code, create=True)
            record.daemon_seen_at = self._clock()
            self._touch(record)
        return code

    def begin_exchange(self, code):
        """The pairing exchange, atomically: True (and the caller mints a token) only when
        a session has presented this code and no daemon has been heard for two minutes.

        Marking daemon_seen_at here is what refuses a SECOND Pi carrying a copied config
        file while the first one is alive."""
        code = normalize_code(code)
        if code is None:
            return False
        with self._lock:
            record = self._get(code)
            if record is None or record.session_seen_at is None:
                return False
            now = self._clock()
            if (record.daemon_seen_at is not None
                    and now - record.daemon_seen_at <= DAEMON_ONLINE_SECONDS):
                return False
            record.daemon_seen_at = now
            self._touch(record)
            return True

    # -- reads -------------------------------------------------------------------------

    UNPAIRED = {'paired': False, 'waiting': False, 'online': False, 'age_seconds': None,
                'status': None, 'job': None, 'last_result': None, 'delivery': None,
                'code': None}

    def status_for(self, code):
        """Everything a caller's status line needs, computed from the relay's own clock.

        The snapshot carries no timestamp: `age_seconds` is measured from when the sync
        arrived here, so a Pi with a wrong clock changes nothing."""
        code = normalize_code(code)
        if code is None:
            return dict(self.UNPAIRED)
        with self._lock:
            record = self._get(code)
            if record is None:
                return dict(self.UNPAIRED)
            now = self._clock()
            age = None if record.status_received_at is None else int(now - record.status_received_at)
            last_result = None
            if record.last_result is not None:
                last_result = {'ok': record.last_result['ok'],
                               'reason': record.last_result['reason'],
                               'age_seconds': int(now - record.last_result_at)}
                if record.last_result.get('error_report') is not None:
                    last_result['error_report'] = copy.deepcopy(
                        record.last_result['error_report'])
                if record.last_result.get('cancelled'):
                    last_result['cancelled'] = True
            job = None
            if record.job is not None:
                job = {'id': record.job['id'], 'state': record.job['state'],
                       'filename': record.job['filename'],
                       'display_name': strip_job_suffix(record.job['filename'])}
            # The raw name stays, so a caller can still match the job id in it; display_name
            # is what a caller shows.
            status = copy.deepcopy(record.status) if record.status else None
            if status is not None:
                status['display_name'] = strip_job_suffix(status.get('file') or '')
            delivery = self._deliveries.get(record.latest_delivery or '')
            report = None
            if delivery is not None:
                if delivery.refresh(now):
                    self._note(delivery)
                report = copy.deepcopy(delivery.report)
            return {
                'paired': True,
                'waiting': record.daemon_seen_at is None,
                'online': self._is_fresh(record, now),
                'age_seconds': age,
                'status': status,
                'job': job,
                'last_result': last_result,
                'delivery': report,
                'code': format_code(code),
            }

    # -- writes ------------------------------------------------------------------------

    def _refusal(self, record):
        """Why a send cannot go ahead right now, or None. Caller holds the lock.

        The text is what a caller shows, so it reads as a sentence to a student."""
        now = self._clock()
        if record.daemon_seen_at is None:
            return ('The Pi has not reported since the service started; '
                    'check the setup guide.')
        if record.status_received_at is None:
            return 'No printer reporting yet; try again in a moment.'
        if not self._is_fresh(record, now):
            age = now - record.status_received_at
            return f'Printer offline, last seen {int(age // 60)} min ago'
        status = record.status or {}
        state = status.get('state')
        if state == 'running':
            percent = status.get('percent')
            name = strip_job_suffix(status.get('file')) or 'a file'
            if isinstance(percent, int) and not isinstance(percent, bool):
                return f'Printer busy, printing {name} at {percent} percent'
            return f'Printer busy, printing {name}'
        if state == 'paused':
            paused_name = strip_job_suffix(status.get('file')) or 'a file'
            return f'Paused, {paused_name}'
        if state == 'unreachable':
            return 'Printer unreachable from the Pi'
        if state not in FREE_STATES:
            # The daemon's own word that it cannot read the printer (`unrecognised`), or a
            # state this relay does not know: nobody can tell whether a print is going on.
            raw = status.get('unrecognised') or f'state {state!r}'
            return f'Printer state not recognised: {raw}'
        # Idle, or its last print ended (well or badly): the printer is free. The daemon
        # still starts the file only on a fresh report that shows no print going on.
        if record.job is not None:
            return 'A job is already on its way to the printer'
        return None

    def claim_job(self, code, *, job_id, download_path, filename, team_number, size=None,
                  sha256=None):
        """Store a pending job, or refuse with a reason.

        The whole check-and-store is one lock acquisition, so two callers pressing Send at
        the same instant cannot both win. Returns (ok, reason, job). `size` and `sha256`
        travel to the daemon, which checks the download against them."""
        code = normalize_code(code)
        with self._lock:
            record = self._get(code)
            if record is None:
                return False, 'No printer paired', None
            refusal = self._refusal(record)
            if refusal is not None:
                return False, refusal, None
            now = self._clock()
            job = {'id': job_id, 'download_path': download_path, 'filename': filename,
                   'created_at': now, 'state': 'pending',
                   'team_number': team_number, 'handed_out_at': None, 'size': size,
                   'sha256': sha256, 'cancel_requested': False, 'start_granted_to': None}
            record.job = job
            record.latest_delivery = job_id
            delivery = dl.Delivery(job_id, code, filename=filename, team_number=team_number,
                                   now=now)
            self._deliveries[job_id] = delivery
            self._note(delivery)
            self._touch(record)
            return True, None, dict(job)

    def store_status(self, code, snapshot, progress=None):
        """Store a sync's snapshot and hand out the job, if any.

        `progress` is the daemon's word on the job it holds: {id, stage, bytes_sent,
        bytes_total}. Returns the job the daemon should act on -- a pending job promoted to
        handed_out, or the handed_out job again for a daemon that restarted mid-job -- else
        None."""
        code = normalize_code(code)
        if code is None:
            return None
        with self._lock:
            record = self._get(code, create=True)
            now = self._clock()
            record.status = bounded_snapshot(snapshot)
            record.status_received_at = now
            self._touch(record)
            status = record.status or {}
            # A FAILED result whose job the printer is now reporting: the printer has the
            # job whatever the acknowledgement said. A success is left for the caller to
            # see; it expires on its own.
            names = f"{status.get('job_name') or ''} {status.get('file') or ''}"
            if (record.last_result is not None
                    and not record.last_result['ok']
                    and record.last_result.get('job_id')
                    and record.last_result['job_id'] in names):
                record.last_result = None
                record.last_result_at = None
            self._follow_prints(code, status, progress, now)
            job = record.job
            if job is None:
                return None
            if job['state'] == 'pending':
                job['state'] = 'handed_out'
                job['handed_out_at'] = now
                delivery = self._deliveries.get(job['id'])
                if delivery is not None:
                    delivery.handed_out(now)
                    self._note(delivery)
            offered = dict(job)
            # What a restarted daemon needs to rebuild its hold on the printer: the gate's
            # age for this job, and the printer's last start granted to an earlier one.
            if job.get('start_granted_at') is not None:
                offered['start_granted_age_s'] = int(now - job['start_granted_at'])
            last = record.last_grant
            if last is not None and last['id'] != job['id']:
                offered['previous_start'] = {'id': last['id'], 'filename': last['filename'],
                                             'age_s': int(now - last['at'])}
            return offered

    def _follow_prints(self, code, status, progress, now):
        """Every live delivery job of this printer hears the sync. Caller holds the lock."""
        for delivery in list(self._deliveries.values()):
            if delivery.code != code or delivery.final:
                continue
            delivery.heard(now)
            delivery.printer_word(status)
            if (isinstance(progress, dict) and progress.get('id') == delivery.job_id):
                delivery.daemon_progress(progress, now)
            if delivery.stage in dl.STARTING and delivery.printer_shows_it_going(status):
                # The printer shows this job's file going before the daemon's
                # acknowledgement arrived (it may be on its way through a link that is
                # down): the printer's own report is the evidence that it started. An end
                # naming the file is not: it may be the previous print's, left over, and
                # only the daemon can tell (see "How a start is decided").
                delivery.started(now)
            delivery.print_report(status, now)
            delivery.refresh(now)
            self._note(delivery)

    def finish_job(self, code, job_id, *, ok, reason, error_code=None, detail=None,
                   fields=None):
        """Record an acknowledgement. Returns (found, team_number); found False means the
        daemon acked a job this relay no longer holds, which the daemon treats as final.

        `error_code` is the daemon's code for the failure, `detail` its evidence, `fields`
        the figures that fill its sentence (errors.daemon_fields keeps the known ones)."""
        code = normalize_code(code)
        if code is None:
            return False, None
        with self._lock:
            record = self._get(code)
            if record is None or record.job is None or record.job['id'] != job_id:
                return False, None
            job = record.job
            team_number = job.get('team_number')
            if not isinstance(error_code, str) or not error_code:
                error_code = None
            # The caller cancelled and the job stopped before the start, whatever stopped
            # it: the caller asked for a cancel, and a cancel is what happened.
            if not ok and job['cancel_requested'] and job['start_granted_to'] is None:
                error_code = 'delivery.cancelled'
            self._finish(code, record, job, ok=bool(ok), reason=reason,
                         error_code=None if ok else error_code, detail=detail,
                         fields=fields)
            self._touch(record)
            return True, team_number

    # -- the start gate and cancellation -------------------------------------------------

    def grant_start(self, code, job_id, instance):
        """May the daemon start this job's file on the printer now? One of:

        - 'start': yes. Granted once, to one daemon process (`instance`); the same process
          asking again (a repeated request) is answered 'start' again;
        - 'cancelled': the caller cancelled it, never start it;
        - 'refused': another daemon process holds the grant: never start it a second time;
        - 'unknown': the relay holds no such job (finished, expired, or the relay restarted);
        - 'no_instance': the request named no daemon process, so no grant could keep the
          start to one process: refused, and nothing is granted.

        From the grant on, a cancel is refused: the file may be printing."""
        code = normalize_code(code)
        with self._lock:
            record = self._get(code)
            if record is None or record.job is None or record.job['id'] != job_id:
                return 'unknown'
            if not isinstance(instance, str) or not instance.strip():
                return 'no_instance'
            job = record.job
            if job['cancel_requested']:
                return 'cancelled'
            instance = instance[:MAX_INSTANCE_CHARS]
            if job['start_granted_to'] is None:
                job['start_granted_to'] = instance
                job['start_granted_at'] = self._clock()
                record.last_grant = {'id': job_id, 'filename': job['filename'],
                                     'at': job['start_granted_at']}
                delivery = self._deliveries.get(job_id)
                if delivery is not None:
                    delivery.gate_passed = True
                    delivery.daemon_progress({'stage': 'starting'}, self._clock())
                    self._note(delivery)
                self._touch(record)
                return 'start'
            return 'start' if job['start_granted_to'] == instance else 'refused'

    def stop_following(self, code, job_id):
        """The caller stops following a delivery job past the start gate whose report is
        stale. One of 'stopped' (it ends `failed`, `delivery.outcome_unknown`, and its job
        slot is freed), 'fresh' (the printer is still reporting it: refused, the print can
        only be stopped at the printer), 'not_shown' (past the gate, fresh word, and the
        printer has not shown the print yet: refused, the daemon is still watching),
        'not_started' (before the gate: cancel it instead), 'final', 'unknown'.

        A later send is still guarded by the printer's own report: a printer that is busy,
        or that cannot be heard, refuses it."""
        code = normalize_code(code)
        with self._lock:
            delivery = self._deliveries.get(job_id)
            if delivery is None or delivery.code != code:
                return 'unknown'
            self._get(code)                  # applies the job slot's lazy deadlines
            now = self._clock()
            if not delivery.final and delivery.refresh(now):
                self._note(delivery)
            if delivery.final:
                return 'final'
            if not delivery.gate_passed:
                return 'not_started'
            if delivery.stale_age is None:
                # Fresh word: following the print, the printer reports it; before that, the
                # printer has not shown it yet, and nobody may be told it is running.
                return 'fresh' if delivery.stage in dl.FOLLOWING else 'not_shown'
            delivery.outcome_unknown(now, 'the caller stopped following it')
            self._note(delivery)
            return 'stopped'

    def cancel(self, code, job_id):
        """The caller cancels a delivery job. Returns one of 'cancelled' (it was still
        waiting for the daemon: done at once), 'cancelling' (the daemon holds it: it stops
        on its next sync, and the job ends as cancelled once it has), 'being_sent' (the start
        was granted and the daemon has not yet said the command went: it may be going now),
        'too_late' (the start command was sent, or the printer showed the print), 'final'
        (already over), 'unknown'."""
        code = normalize_code(code)
        with self._lock:
            delivery = self._deliveries.get(job_id)
            if delivery is None or delivery.code != code:
                return 'unknown'
            record = self._get(code)
            job = record.job if record is not None else None
            if job is None or job['id'] != job_id:
                if delivery.final:
                    return 'final'
                return 'too_late' if delivery.start_sent else 'being_sent'
            if job['start_granted_to'] is not None:
                return 'too_late' if delivery.start_sent else 'being_sent'
            if job['state'] == 'pending':
                self._finish(code, record, job, ok=False, reason='cancelled',
                             error_code='delivery.cancelled')
                self._touch(record)
                return 'cancelled'
            job['cancel_requested'] = True
            delivery.cancel_requested = True
            delivery._emit(self._clock())
            self._note(delivery)
            self._touch(record)
            return 'cancelling'

    # -- delivery reports ---------------------------------------------------------------

    def delivery_report(self, code, job_id):
        """The latest progress report of one of this printer's delivery jobs, or None."""
        code = normalize_code(code)
        with self._lock:
            self._get(code)                  # applies the job slot's lazy deadlines
            delivery = self._deliveries.get(job_id)
            if delivery is None or delivery.code != code:
                return None
            if delivery.refresh(self._clock()):
                self._note(delivery)
            return copy.deepcopy(delivery.report)

    def wait_for_report(self, code, job_id, after_sequence, timeout):
        """Block until the delivery job has a report newer than `after_sequence`, or for
        `timeout` seconds, then return its latest report (None when unknown). The wait is
        on the relay's condition, so it ends the moment anything changes."""
        with self._lock:
            delivery = self._deliveries.get(job_id)
            if (delivery is not None and delivery.sequence <= after_sequence
                    and not delivery.final):
                self._changed.wait(timeout)
        return self.delivery_report(code, job_id)

    def sweep(self):
        """Drop every expired record and every final delivery job past its keeping time,
        at most once a minute on the relay's clock. Returns how many went."""
        with self._lock:
            now = self._clock()
            if self._last_sweep is not None and now - self._last_sweep < SWEEP_EVERY_SECONDS:
                return 0
            self._last_sweep = now
            removed = 0
            # Delivery jobs first: one past the gate with a day of no fresh word ends as
            # `delivery.outcome_unknown` here, before its printer's record can go.
            for delivery in list(self._deliveries.values()):
                if delivery.refresh(now):
                    self._note(delivery)
            for code in list(self._records):
                if self._get(code) is None:
                    removed += 1
            for job_id, delivery in list(self._deliveries.items()):
                if delivery.final and now - delivery.finished_at > dl.FINAL_TTL_SECONDS:
                    del self._deliveries[job_id]
                    removed += 1
                elif not delivery.final and delivery.code not in self._records:
                    # Its printer's record went after a day with nothing from anyone. The
                    # delivery job is not dropped: it ends here and keeps its final report
                    # for FINAL_TTL_SECONDS, so a caller polling only the job route learns
                    # how it ended instead of being told there is no record.
                    self._end_orphan(delivery, now)
            return removed

    def _end_orphan(self, delivery, now):
        """End a live delivery job whose printer's record expired. Caller holds the lock.

        Past the start gate the print may have run: `delivery.outcome_unknown`. Before it,
        the file was never started, and the job slot's own deadlines say why."""
        if delivery.gate_passed:
            delivery.outcome_unknown(now, 'the printer\'s record expired after a day '
                                          'without word')
        elif delivery.state == dl.QUEUED:
            delivery.fail(now, errors.report_for_code(
                'delivery.job_not_picked_up',
                detail='the printer\'s record expired before the job was collected'))
        else:
            delivery.fail(now, errors.report_for_code(
                'delivery.job_not_confirmed',
                detail='the printer\'s record expired before a start was asked for',
                minutes=JOB_HANDED_OUT_TIMEOUT_SECONDS // 60))
        self._note(delivery)

    def counts(self):
        """How many records and delivery jobs the relay holds, for tests and support."""
        with self._lock:
            return {'records': len(self._records), 'deliveries': len(self._deliveries)}

    def ping(self, code):
        """Read-only health answer for `penguincam-printer status`.

        Stores nothing -- deliberately NOT recording daemon_seen_at, so a mentor running
        status while the service is down cannot block the service's next exchange."""
        code = normalize_code(code)
        with self._lock:
            record = self._get(code)
            if record is None:
                return {'ok': True, 'waiting': True, 'online': False}
            return {'ok': True,
                    'waiting': record.daemon_seen_at is None,
                    'online': self._is_fresh(record, self._clock())}

    def held_job_id(self, code):
        """The id of the job the relay holds for this code, or None. Applies the lazy
        deadlines like every other read. The routes use it to drop a sliced file once its
        job is no longer held."""
        code = normalize_code(code)
        with self._lock:
            record = self._get(code)
            if record is None or record.job is None:
                return None
            return record.job['id']
