"""The `run` command's loop.

Written as a tick() that does at most one network thing and returns, with every interval
measured on the monotonic clock through an injected `clock`, every wait through an
injected `sleep`, and every jitter drawn from an injected `rand`. That is what makes the
exchange, the sync, the start wait and the backoff testable without sleeping -- and it is
also why a computer with no network time source, or one whose clock is hours wrong, behaves
exactly like any other: the relay never sees the daemon's wall clock.

One delivery job runs at a time, on a one-worker executor, so syncs keep going during an
upload and the printer never looks offline while a file is on its way. The job thread
reports its stage through `job_progress`, which the next sync carries to the relay (at
most once a second while it moves).

A delivery job, on the daemon:

1. the printer already reports the file: acknowledge, never upload it again;
2. the relay says a start was already granted (to this daemon before a restart, or to
   another): never start it again, only wait for the printer's report;
3. wait for a free printer: a whole, fresh picture that shows no print going on, and no
   earlier start command still holding the printer (StartHold);
4. download, checked against the relay's size and checksum, retried with backoff;
5. upload, judged by the printer's own listing, retried with backoff;
6. wait for a free printer again, still cancellable, then ask the relay's start gate; on
   its yes look once more, without waiting, and send the start command only on a free
   printer. A cancel, or a relay that cannot be reached, means the file is never started;
7. hold the printer and watch for the evidence of what became of the command (seen going,
   a proven end, or START_SETTLE_SECONDS of pictures without our print), and acknowledge;
   leave the wait once the relay no longer holds the job (the hold stays).

Every acknowledgement carries the failure's code (the guide lists them; the relay turns
each into an error report), the one line of reason, and the evidence in `detail`. An acknowledgement that
cannot be delivered is queued and sent again, with backoff, until the relay answers.
"""

import os
import random
import re
import secrets
import tempfile
import threading
import time
import traceback
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from penguin_delivery_daemon import config as config_module
from penguin_delivery_daemon import printer as printer_module
from penguin_delivery_daemon.relay_client import (
    Cancelled, ChallengeDetected, DownloadCorrupt, RateLimited, RelayError, TokenRejected,
)

EXCHANGE_INTERVAL = 30.0
SYNC_INTERVAL = 5.0
PROGRESS_SYNC_SECONDS = 1.0
BACKOFF_START = 5.0
BACKOFF_CAP = 60.0
#: Every wait after a failure is shortened by up to this share, drawn from `rand`, so a
#: shop full of daemons that lost the relay at the same moment do not return in step.
JITTER = 0.25
# The settings of "How a start is decided" (the guide's section of that name). Every one
# is a guess until the real H2S is timed.
#
#: After the start command, this long without the printer showing our print and the
#: delivery job's stage becomes `start_not_shown` (non-final, with `waited_s`).
START_SLOW_SECONDS = 60.0
#: After the start command, this long of whole, fresh pictures that do not show our print
#: (idle, another file, an end that is not ours) settles it: the printer did not start the
#: file, and only then may another start command go to the printer. Only time in which the
#: printer is reachable and speaking counts: a printer that is unreachable or silent after
#: the start command may be printing, so silence is waited out (the relay shows the job as
#: stale meanwhile), never judged.
START_SETTLE_SECONDS = 5 * 60.0
#: An end naming our file, never seen going, never counts in the first this-many seconds
#: after the command: a left-over end of the previous print is seen then, and no print ends
#: that fast. After it, an end counts when the main state changed after the command; a
#: daemon that lost the printer for this long after the command (or did not send it) takes
#: such an end only once the command is START_SETTLE_SECONDS old.
LEFTOVER_END_SECONDS = 2 * 60.0
START_POLL_SECONDS = 2.0
#: A report older than this is not the printer's word.
FRESH_REPORT_SECONDS = 15.0
#: While its reports are older than that, the printer is asked for a whole report this often.
REPORT_REQUEST_SECONDS = 10.0
#: In the start wait, the relay is asked this often whether it still holds the job; once it
#: does not (the caller stopped following it), the daemon leaves the wait.
HOLD_CHECK_SECONDS = 30.0
#: The most characters of evidence an acknowledgement carries in `detail`; the relay cuts
#: to the same size. Nothing sent to the relay may grow with the size of a sliced file.
MAX_DETAIL_CHARS = 2000
#: How long a delivery job waits for an unreachable printer before it gives up.
PRINTER_WAIT_SECONDS = 10 * 60.0
PRINTER_POLL_SECONDS = 5.0
#: How long the start gate is asked for before the job is abandoned unstarted.
GATE_WAIT_SECONDS = 10 * 60.0
DOWNLOAD_ATTEMPTS = 3
UPLOAD_ATTEMPTS = 3
LOG_EVERY = 60.0
IDLE_LOG_EVERY = 10 * 60.0
TICK_SECONDS = 1.0

# How many acknowledged job ids to remember. The set only has to outlive the re-offers of a
# job the relay has not yet marked done, so a couple of hundred is generous; unbounded, it
# would be the one structure in the daemon that grows for as long as the daemon is up.
ACK_MEMORY = 200

# A download path carries a bearer token. It must not travel back to the relay in an
# acknowledgement reason, which is shown to the caller and kept in the job record.
_DOWNLOAD_PATH_RE = re.compile(r'(/download/)[^\s\'"]+')
# The files a delivery job leaves in the download directory: the job id is in the name.
_LEFTOVER_RE = re.compile(r'-j[0-9a-f]{7,8}\.gcode\.3mf(\.part)?$')

# The printer states in which a print named in the report is under way: seeing our file in
# one of them is seeing the print going.
_GOING = (printer_module.RUNNING, printer_module.PAUSED)
# The printer states that are an end of the print named in the report.
_ENDED = (printer_module.FINISHED, printer_module.ERROR)


class StartHold:
    """What the daemon knows of one start command, from the moment it is sent until the
    evidence settles what became of it. While a hold is unsettled no other start command
    goes to the printer (see "How a start is decided" in the guide).

    `sent_at` is on the daemon's monotonic clock. `sent_here` is False for a hold rebuilt
    from the relay (a restarted daemon, or a start another process holds): then nothing is
    known of the printer's state before the command. `before_state` is the main state of
    the last whole, fresh picture before the command."""

    def __init__(self, job_id, remote_name, sent_at, *, sent_here, before_state=None,
                 now=None):
        self.job_id = job_id
        self.remote_name = remote_name
        self.sent_at = sent_at
        self.sent_here = sent_here
        self.last_state = before_state if sent_here else None
        self.state_changed = False
        self.unwatched = not sent_here
        self.counted = 0.0
        # A rebuilt hold counts the time since the gate as already waited: the first whole,
        # fresh picture without our print may settle it.
        age = max(0.0, (now if now is not None else sent_at) - sent_at)
        self.required = (START_SETTLE_SECONDS if sent_here
                         else max(0.0, START_SETTLE_SECONDS - age))
        self._last_at = None
        self._last_fresh_at = sent_at
        self.other = None
        #: None while unsettled; then 'going', 'ended' or 'no_print'.
        self.outcome = None
        self.evidence = None

    def _end_counts(self, now):
        """Is an end naming our file, never seen going, the end of this print? Never in the
        first LEFTOVER_END_SECONDS after the command (a left-over end is seen then, and no
        print ends that fast). After that, when the main state changed after the command.
        A daemon that could not watch continuously cannot tell a left-over from a real
        end: it takes the end once the command is START_SETTLE_SECONDS old, the same time
        after which a printer that has not shown the print is taken not to have started
        it, so a real end is found and never waited on for ever."""
        age = now - self.sent_at
        if age < LEFTOVER_END_SECONDS:
            return False
        if self.state_changed:
            return True
        return self.unwatched and age >= START_SETTLE_SECONDS

    def watch(self, snapshot, now, fresh):
        """Take one picture into account. Returns the outcome (None while unsettled); a
        settled hold is dropped by its owner, so it is never watched again."""
        dt = 0.0 if self._last_at is None else max(0.0, now - self._last_at)
        self._last_at = now
        state = snapshot.get('state')
        if not fresh or state == printer_module.UNRECOGNISED_STATE:
            if now - self._last_fresh_at >= LEFTOVER_END_SECONDS:
                self.unwatched = True
            return None
        self._last_fresh_at = now
        if self.last_state is not None and state != self.last_state:
            self.state_changed = True
        self.last_state = state
        ours = printer_module.reports_file(snapshot, self.remote_name)
        if ours and state in _GOING:
            self.outcome, self.evidence = 'going', snapshot
            return self.outcome
        if ours and state in _ENDED and self._end_counts(now):
            self.outcome, self.evidence = 'ended', snapshot
            return self.outcome
        # Not our print: idle, another file, or an end with our name that is not ours.
        self.counted += dt
        if state in _GOING and snapshot.get('file') and not ours:
            self.other = snapshot
        if self.counted >= self.required:
            self.outcome, self.evidence = 'no_print', snapshot
        return self.outcome


class InlineExecutor:
    """Runs the job on the calling thread. Used by the tests, so no thread is involved."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)

    def shutdown(self, wait=True):
        pass


class _JobEnded(Exception):
    """Internal: the delivery job has been acknowledged (or abandoned); stop here."""


class _Stopped(_JobEnded):
    """Internal: the daemon is stopping. The job ends here unacknowledged and its file is
    never started by this process; the relay offers the job to the next one."""


def _capped(text, limit=MAX_DETAIL_CHARS):
    if not isinstance(text, str) or len(text) <= limit:
        return text
    note = f' ... [{len(text) - limit} more characters cut]'
    return text[:limit - len(note)] + note


class RunLoop:
    """One printer, one relay, one delivery job at a time."""

    def __init__(self, config, relay, printer, *, clock=time.monotonic, sleep=None,
                 log=print, executor=None, download_dir=None,
                 save_token=config_module.save_token, rand=random.random, instance=None):
        self.config = config
        self.relay = relay
        self.printer = printer
        self.clock = clock
        # Set by stop(). The default sleep is a wait on it, so stopping ends every wait of
        # the tick loop and of the job thread at once.
        self.stopping = threading.Event()
        self.sleep = sleep if sleep is not None else self.stopping.wait
        self.log = log
        self.rand = rand
        # Names this process to the relay's start gate, so a second daemon with a copied
        # configuration, or this one after a restart, can never start the file again.
        self.instance = instance or secrets.token_hex(8)
        self.executor = executor if executor is not None else ThreadPoolExecutor(max_workers=1)
        self.download_dir = download_dir or tempfile.gettempdir()
        self.save_token = save_token

        self.backoff = BACKOFF_START
        self.backoff_until = None
        self.last_error_kind = None
        self.last_exchange_at = None
        self.last_exchange_log_at = None
        self.next_exchange_at = None
        self.last_sync_at = None
        self.last_state = None
        self.last_idle_log_at = None
        self.running_job_id = None
        self.acked_job_ids = set()
        self._acked_order = deque()
        self._deferred_logged = set()
        self._lock = threading.Lock()
        self.job_progress = None
        self._sent_progress = None
        self.cancel_requested = set()
        self.pending_acks = {}          # job id -> dict(ok, reason, code, detail, due, wait)
        #: The last start command's StartHold while it is unsettled, else None.
        self.hold = None
        self.clean_download_dir()

    # -- helpers -----------------------------------------------------------------------

    def _due(self, last, interval):
        return last is None or self.clock() - last >= interval

    def _blocked(self):
        return self.backoff_until is not None and self.clock() < self.backoff_until

    def _jittered(self, seconds):
        return seconds * (1.0 - JITTER * max(0.0, min(1.0, self.rand())))

    def _fail(self, kind, message):
        """Log, name the failure, and back off, doubling to a cap, with jitter."""
        self.last_error_kind = kind
        wait = self._jittered(self.backoff)
        self.log(f"{kind}: {message}; retrying in {wait:.0f}s")
        self.backoff_until = self.clock() + wait
        self.backoff = min(self.backoff * 2, BACKOFF_CAP)

    def _succeeded(self):
        if self.last_error_kind is not None:
            self.log("the relay is answering again")
        self.backoff = BACKOFF_START
        self.backoff_until = None
        self.last_error_kind = None

    def clean_download_dir(self):
        """Remove what a delivery job of an earlier process left behind: a daemon that died
        mid-job leaves its download. Only names a delivery job writes are touched."""
        try:
            names = os.listdir(self.download_dir)
        except OSError:
            return []
        removed = []
        for name in names:
            if _LEFTOVER_RE.search(name):
                self._discard(os.path.join(self.download_dir, name))
                removed.append(name)
        if removed:
            self.log(f"removed {len(removed)} file(s) an earlier run left in "
                     f"{self.download_dir}")
        return removed

    # -- the parts of a tick -------------------------------------------------------------

    def _exchange(self):
        """Trade the pairing code for a token. Runs until there is one, then never again
        unless a sync answers 401."""
        if self.next_exchange_at is not None and self.clock() < self.next_exchange_at:
            return
        if not self._due(self.last_exchange_at, EXCHANGE_INTERVAL):
            return
        self.last_exchange_at = self.clock()
        try:
            token = self.relay.exchange(self.config.pairing_code)
        except RateLimited as e:
            self.next_exchange_at = self.clock() + e.retry_after
            self.log(f"pairing is rate limited; waiting {e.retry_after:.0f}s")
            return
        except ChallengeDetected as e:
            self._fail('challenge', str(e))
            return
        except RelayError as e:
            self._fail('network', str(e))
            return
        self.next_exchange_at = None
        if not token:
            # Once a minute, not every thirty seconds: this is the normal state between
            # running `pair` and the pairing code reaching the caller.
            if self._due(self.last_exchange_log_at, LOG_EVERY):
                self.last_exchange_log_at = self.clock()
                self.log("waiting for the pairing code to be entered on the server")
            return
        self.save_token(token, self.config.path)
        self.config.token = token
        self._succeeded()
        self.log("paired with the relay")

    def _progress_due(self):
        with self._lock:
            progress = self.job_progress
        return (progress is not None and progress != self._sent_progress
                and self._due(self.last_sync_at, PROGRESS_SYNC_SECONDS))

    def _sync(self):
        """Post the snapshot and the job's progress; hand any returned job on."""
        snapshot = self.printer.snapshot()
        state_changed = snapshot.get('state') != self.last_state
        if (not state_changed and not self._due(self.last_sync_at, SYNC_INTERVAL)
                and not self._progress_due()):
            return
        self.last_sync_at = self.clock()
        self.last_state = snapshot.get('state')
        with self._lock:
            progress = dict(self.job_progress) if self.job_progress else None
        try:
            job = self.relay.sync(snapshot, progress)
        except TokenRejected:
            self.log("the relay rejected our token; pairing again")
            self.relay.token = None
            self.config.token = ''
            self.save_token('', self.config.path)
            self.last_exchange_at = None
            return
        except RateLimited as e:
            self.log(f"the relay is rate limiting us; waiting {e.retry_after:.0f}s")
            self.backoff_until = self.clock() + e.retry_after
            return
        except ChallengeDetected as e:
            self._fail('challenge', str(e))
            return
        except RelayError as e:
            self._fail('network', str(e))
            return
        self._sent_progress = progress
        self._succeeded()
        if job:
            self._maybe_start_job(job)
        elif self.running_job_id is None and self._due(self.last_idle_log_at,
                                                       IDLE_LOG_EVERY):
            self.last_idle_log_at = self.clock()
            self.log(f"idle: the printer is {snapshot.get('state')}, the relay is "
                     "answering; waiting for a print")

    def _send_due_ack(self):
        """Send one queued acknowledgement whose wait is over. True when one was tried."""
        now = self.clock()
        with self._lock:
            due = [(entry['due'], job_id) for job_id, entry in self.pending_acks.items()
                   if entry['due'] <= now]
        if not due:
            return False
        _due, job_id = min(due)
        with self._lock:
            entry = self.pending_acks.pop(job_id)
        self._ack(job_id, entry['ok'], entry['reason'], code=entry['code'],
                  detail=entry['detail'], fields=entry.get('fields'), wait=entry['wait'])
        return True

    def tick(self):
        """One pass. Does at most one network thing, then returns."""
        if self._blocked():
            return
        if not self.relay.token:
            self._exchange()
            return
        if self._send_due_ack():
            return
        self._sync()

    def preflight(self):
        """Refuse a relay URL the daemon must not talk to, and name a development one.

        load_config and save_config deliberately do not enforce this -- a config file the
        daemon cannot use must still be readable by `status` -- so the check belongs here,
        once, before the first request."""
        config_module.check_backend_url(self.config.backend_url, dev=self.config.dev)
        if self.config.dev:
            self.log(f"WARNING: development mode, talking to {self.config.backend_url} "
                     "over an unverified connection")

    def stop(self):
        """Stop the loop and the job thread's waits. A job in flight ends at its next wait,
        unacknowledged, and is never started by this process (see _Stopped)."""
        self.stopping.set()

    def _check_stop(self):
        if self.stopping.is_set():
            raise _Stopped()

    def run_forever(self):
        """Never exits on a single failure; returns once stop() has been called."""
        self.preflight()
        while not self.stopping.is_set():
            try:
                self.tick()
            except Exception as e:                  # nothing may kill the loop
                self._fail('unexpected', repr(e))
                self.log(traceback.format_exc())     # the whole of it, for the log
            self.sleep(TICK_SECONDS)

    # -- handing a job on --------------------------------------------------------------

    def _maybe_start_job(self, job):
        """Hand a job to the job thread, unless this process has already dealt with it.

        The relay re-offers a handed-out job on every sync until it is acknowledged, so the
        guard runs on every sync and not only after a restart: the set of acknowledged ids
        covers a job already finished, a queued acknowledgement one whose answer is on its
        way, and running_job_id the one in flight. A re-offer carrying `cancel` reaches the
        running job as a cancel request."""
        job_id = job.get('id')
        if not job_id or job_id in self.acked_job_ids:
            return
        with self._lock:
            if job_id in self.pending_acks:
                return
        if job.get('cancel'):
            if job_id == self.running_job_id:
                if job_id not in self.cancel_requested:
                    self.log(f"job {job_id}: cancel requested; stopping before the print "
                             "starts")
                self.cancel_requested.add(job_id)
                return
            if self.running_job_id is None and not job.get('start_granted'):
                self.log(f"job {job_id}: cancelled before it was started here")
                self._ack(job_id, False, 'cancelled', code='delivery.cancelled')
                return
        if self.running_job_id is not None:
            # Once per deferred job, not once per sync: the relay re-offers it every five
            # seconds, and a log full of the same line hides everything else.
            if job_id != self.running_job_id and job_id not in self._deferred_logged:
                self._deferred_logged.add(job_id)
                self.log(f"job {job_id} offered while {self.running_job_id} is still "
                         "running; leaving it for the next sync")
            return
        self._deferred_logged.discard(job_id)
        self.running_job_id = job_id
        self.executor.submit(self.handle_job, job)

    def _ack(self, job_id, ok, reason=None, *, code=None, detail=None, fields=None,
             wait=None):
        """Acknowledge, and remember the job only when the answer was definite.

        A False answer means the relay no longer holds the job (404), which the daemon
        treats as final rather than retrying. A RelayError is transient: the
        acknowledgement is queued and sent again after a backoff, and the id is NOT
        remembered, so the job is not lost if this process dies before it is delivered
        (the relay re-offers it, and a new process acknowledges from the printer's own
        report without uploading a second time).

        `detail` is cut to MAX_DETAIL_CHARS here, where every acknowledgement is built;
        `fields` are the figures the relay fills the failure's sentence with."""
        detail = _capped(detail)
        try:
            held = self.relay.ack(job_id, ok, reason, code=code, detail=detail,
                                  fields=fields)
        except RelayError as e:
            wait = min((wait or BACKOFF_START / 2) * 2, BACKOFF_CAP)
            jittered = self._jittered(wait)
            with self._lock:
                self.pending_acks[job_id] = {'ok': ok, 'reason': reason, 'code': code,
                                             'detail': detail, 'fields': fields,
                                             'wait': wait,
                                             'due': self.clock() + jittered}
            self.log(f"could not acknowledge {job_id}: {e}; will try again in "
                     f"{jittered:.0f}s")
            return
        self._remember_acked(job_id)
        self.log(f"job {job_id} acknowledged: {'ok' if ok else reason}")
        if not held:
            self.log(f"the relay no longer holds job {job_id}; treating it as finished")

    def _remember_acked(self, job_id):
        """Add an id to the bounded set of jobs this process has finished with."""
        if job_id in self.acked_job_ids:
            return
        if len(self._acked_order) >= ACK_MEMORY:
            self.acked_job_ids.discard(self._acked_order.popleft())
        self._acked_order.append(job_id)
        self.acked_job_ids.add(job_id)

    def handle_job(self, job):
        """Run one delivery job, and free the slot however it ends.

        The slot is cleared in a finally: a job that raises before its first acknowledgement
        -- a malformed job document, a printer link that throws -- must not leave the daemon
        refusing every later job until someone restarts it. It is cleared only while this
        job still owns it, so a job finishing late cannot blank the slot of the one that
        has since taken it."""
        job_id = job.get('id')
        try:
            self._run_job(job)
        except _Stopped:
            self.log(f"job {job_id}: the daemon is stopping; the next run takes the job up "
                     "where the relay and the printer say it is")
        except _JobEnded:
            pass
        except Exception as e:
            self.log(f"job {job_id} failed unexpectedly: {e!r}")
            self.log(traceback.format_exc())          # the whole of it, for the log
            if job_id and job_id not in self.acked_job_ids:
                self._ack(job_id, False, self._one_line(e), code='delivery.job_failed',
                          detail=self._one_line(repr(e)))
        finally:
            with self._lock:
                if self.job_progress and self.job_progress.get('id') == job_id:
                    self.job_progress = None
            self.cancel_requested.discard(job_id)
            if self.running_job_id == job_id:
                self.running_job_id = None

    # -- one delivery job ----------------------------------------------------------------

    def _stage(self, job_id, stage, **fields):
        with self._lock:
            self.job_progress = {'id': job_id, 'stage': stage, **fields}

    def _end(self, job_id, ok, reason=None, *, code=None, detail=None, fields=None):
        """Acknowledge and stop the job here."""
        self._ack(job_id, ok, reason, code=code, detail=detail, fields=fields)
        raise _JobEnded()

    def _cancelled(self, job_id):
        return job_id in self.cancel_requested

    def _interrupted(self, job_id):
        """Should a transfer stop now: the job cancelled, or the daemon stopping."""
        return self._cancelled(job_id) or self.stopping.is_set()

    def _end_cancelled(self, job_id, remote_name=None):
        if remote_name is not None:
            self._remove_from_printer(job_id, remote_name)
        self.log(f"job {job_id}: cancelled; it was never started on the printer")
        self._end(job_id, False, 'cancelled', code='delivery.cancelled')

    def _remove_from_printer(self, job_id, remote_name):
        delete = getattr(self.printer, 'delete', None)
        if delete is None:
            return
        if delete(remote_name):
            self.log(f"job {job_id}: removed {remote_name} from the printer")
        else:
            self.log(f"job {job_id}: could not confirm {remote_name} was removed from the "
                     "printer; it is harmless there, but can be deleted on its screen")

    def _wait(self, job_id, seconds):
        """Wait in the job thread, a second at a time, ending early on a cancel."""
        end = self.clock() + seconds
        while self.clock() < end:
            self._check_stop()
            if self._cancelled(job_id):
                return True
            self.sleep(min(TICK_SECONDS, end - self.clock()))
        self._check_stop()
        return self._cancelled(job_id)

    def _run_job(self, job):
        job_id = job['id']
        # The filename comes from the relay: it is made a plain file name, safe on every
        # operating system, before it becomes the name on the printer or on disk.
        remote_name = printer_module.suffixed_name(
            printer_module.safe_file_name(job['filename']), job_id)

        self._adopt_previous_start(job)
        # 1. The printer is already printing this job: a daemon that died after the start
        #    command must not print the part a second time.
        if self._acknowledge_if_going(
                job_id, remote_name,
                note=f"the printer already has {remote_name}; not uploading it again"):
            return
        # 2. A start was granted before (to an earlier run of this daemon, or to another
        #    daemon with the same pairing): whatever happened, never start it again. The
        #    hold is rebuilt from the gate's age, as the relay measured it.
        if job.get('start_granted'):
            self.log(f"job {job_id}: the start was already granted, so it is never started "
                     "again from here; waiting for the printer to report it")
            self._stage(job_id, 'starting')
            self._await_start(job_id, remote_name,
                              self._rebuilt_hold(job_id, remote_name,
                                                 job.get('start_granted_age_s')))
            return
        if job.get('cancel'):
            self._end_cancelled(job_id)

        self._await_free_printer(job_id)                                 # 3
        dest = os.path.join(self.download_dir, remote_name)
        try:
            self._download(job_id, job, dest)                            # 4
            self._upload(job_id, dest, remote_name)                      # 5
        finally:
            self._discard(dest)
        self._gate(job_id, remote_name)                                  # 6
        self._start(job_id, remote_name)                                 # 7

    def _rebuilt_hold(self, job_id, remote_name, age_s):
        """A StartHold for a start this process did not send, `age_s` after the gate."""
        now = self.clock()
        age = float(age_s) if (isinstance(age_s, (int, float))
                               and not isinstance(age_s, bool) and age_s >= 0) else 0.0
        return StartHold(job_id, remote_name, now - age, sent_here=False, now=now)

    def _adopt_previous_start(self, job):
        """A restarted daemon has no hold in memory: the relay names the printer's last
        start granted (`previous_start`), and an earlier job this process has not settled
        holds the printer until the evidence settles it."""
        previous = job.get('previous_start')
        if not isinstance(previous, dict) or self.hold is not None:
            return
        previous_id = previous.get('id')
        if (not isinstance(previous_id, str) or previous_id == job.get('id')
                or previous_id in self.acked_job_ids
                or not isinstance(previous.get('filename'), str)):
            return
        name = printer_module.suffixed_name(
            printer_module.safe_file_name(previous['filename']), previous_id)
        self.hold = self._rebuilt_hold(previous_id, name, previous.get('age_s'))
        self.log(f"job {job.get('id')}: the printer was sent {name} (job {previous_id}) "
                 "before this process started; no other print starts until the printer "
                 "shows what became of it")

    def _watch_foreign_hold(self, job_id, snapshot):
        """Feed a picture to a hold left by another delivery job. True while it holds."""
        hold = self.hold
        if hold is None or hold.job_id == job_id:
            return False
        outcome = hold.watch(snapshot, self.clock(), self._fresh(snapshot))
        if outcome is None:
            return True
        self.hold = None
        self.log(f"the earlier start of {hold.remote_name} (job {hold.job_id}) is settled: "
                 + {'going': 'the printer is printing it',
                    'ended': 'the printer reports it ended',
                    'no_print': 'the printer did not start it'}[outcome])
        return False

    def _await_free_printer(self, job_id, remote_name=None):
        """Wait for a free printer: a whole, fresh picture (younger than
        FRESH_REPORT_SECONDS) that shows no print going on (idle, or its last print ended,
        well or badly), with no earlier start command still holding the printer. Called
        when the job arrives, between upload attempts, and after the upload, before the
        start gate is asked -- so every wait comes before the gate, where a cancel still
        ends the job, and two different files can never overlap on a printer that went
        quiet or was slow to show the last print.

        Without a whole, fresh picture (the printer unreachable, its status stream quiet,
        or only partial documents since the daemon connected) the printer is asked for a
        whole report every REPORT_REQUEST_SECONDS, and the job waits in the stage
        `waiting_for_printer`; held by an earlier start, in `waiting_for_earlier_print`.
        After PRINTER_WAIT_SECONDS of that the job ends unstarted. A fresh report of a print
        going on, or of a state this version does not know, ends it unstarted at once. With
        `remote_name`, the uploaded file is removed from the printer whenever it ends."""
        waited_from = self.clock()
        last_log = None
        last_request = None
        while True:
            if self._cancelled(job_id):
                self._end_cancelled(job_id, remote_name)
            snapshot = self.printer.snapshot()
            state = snapshot.get('state')
            held = self._watch_foreign_hold(job_id, snapshot)
            if self._fresh(snapshot):
                self._refuse_if_not_free(job_id, snapshot, remote_name)
                if not held:
                    return snapshot
            now = self.clock()
            waited = now - waited_from
            if waited >= PRINTER_WAIT_SECONDS:
                minutes = int(PRINTER_WAIT_SECONDS // 60)
                if remote_name is not None:
                    self._remove_from_printer(job_id, remote_name)
                if held and self._fresh(snapshot):
                    # The printer answers, but has not shown what became of the earlier
                    # start. (A printer that does not answer is the plainer reason below.)
                    hold = self.hold
                    self._end(job_id, False,
                              f'the printer did not show within {minutes} min what became of '
                              f'the print sent before this one ({hold.remote_name})',
                              code='delivery.earlier_start_unsettled',
                              detail=f'job {hold.job_id} was sent a start command; '
                                     f'{int(hold.counted)} s of fresh reports since, none '
                                     f'naming it; the last: {self._snapshot_detail(snapshot)}',
                              fields={'minutes': minutes})
                self._end(job_id, False, f'the printer did not answer for {minutes} min',
                          code='delivery.printer_unreachable_at_start',
                          detail=f'no whole, fresh report from the printer for {int(waited)} '
                                 f's; the last: {self._snapshot_detail(snapshot)}, '
                                 f"{snapshot.get('report_age_s')!r} s old",
                          fields={'minutes': minutes})
            if held and self._fresh(snapshot):
                self._stage(job_id, 'waiting_for_earlier_print')
                if last_log is None or now - last_log >= LOG_EVERY:
                    last_log = now
                    self.log(f"job {job_id}: waiting for the printer to show what became of "
                             f"{self.hold.remote_name}, sent before this one ({int(waited)}s "
                             "so far)")
                self._wait(job_id, PRINTER_POLL_SECONDS)
                continue
            self._stage(job_id, 'waiting_for_printer')
            if last_request is None or now - last_request >= REPORT_REQUEST_SECONDS:
                last_request = now
                request = getattr(self.printer, 'request_report', None)
                if request is not None:
                    request()
            if last_log is None or now - last_log >= LOG_EVERY:
                last_log = now
                if state == printer_module.UNREACHABLE:
                    self.log(f"job {job_id}: waiting for the printer to answer "
                             f"({int(waited)}s so far)")
                else:
                    self.log(f"job {job_id}: waiting for a fresh report from the printer "
                             f"(its last is {snapshot.get('report_age_s')} s old) before "
                             f"going on ({int(waited)}s so far)")
            self._wait(job_id, PRINTER_POLL_SECONDS)

    def _refuse_if_not_free(self, job_id, snapshot, remote_name):
        """End the job unstarted when a fresh picture shows a print going on, or a main
        state this version does not know (a picture with no main state is never fresh, so
        it never reaches here). With `remote_name`, the uploaded file is removed."""
        state = snapshot.get('state')
        if remote_name is not None and self._acknowledge_if_going(job_id, remote_name,
                                                                   snapshot):
            raise _JobEnded()
        if state in _GOING:
            fields = self._busy_fields(snapshot)
            if remote_name is not None:
                self._remove_from_printer(job_id, remote_name)
                reason = f"someone started {fields['name']} at the printer before this print"
            else:
                reason = f"the printer is busy with {fields['name']}"
                if 'percent' in fields:
                    reason += f" at {fields['percent']} percent"
            self._end(job_id, False, reason, code='delivery.printer_busy_at_start',
                      detail=self._snapshot_detail(snapshot), fields=fields)
        if state == printer_module.UNRECOGNISED_STATE:
            value = snapshot.get('unrecognised') or f'state {state!r}'
            if remote_name is not None:
                self._remove_from_printer(job_id, remote_name)
            self.log(f"job {job_id}: the printer reports something this version does "
                     f"not know ({value}); the print is not started")
            self._end(job_id, False,
                      f'the printer reported something this version does not know: '
                      f'{value}', code='delivery.printer_state_unrecognised_at_start',
                      detail=f'{value}; {self._snapshot_detail(snapshot)}')

    def _download(self, job_id, job, dest):
        self._stage(job_id, 'downloading')
        self.log(f"job {job_id}: downloading the sliced file")
        size = job.get('size') if isinstance(job.get('size'), int) else None

        def progress(received, total):
            self._stage(job_id, 'downloading', bytes_sent=received, bytes_total=total)

        wait = BACKOFF_START
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            try:
                self.relay.download(job['download_path'], dest, size=size,
                                    sha256=job.get('sha256'), progress=progress,
                                    cancelled=lambda: self._interrupted(job_id))
                return
            except Cancelled:
                self._check_stop()
                self._end_cancelled(job_id)
            except RelayError as e:
                corrupt = isinstance(e, DownloadCorrupt)
                if attempt == DOWNLOAD_ATTEMPTS:
                    self._end(job_id, False, self._one_line(e),
                              code='delivery.download_corrupt' if corrupt
                              else 'delivery.download_failed',
                              detail=f'{DOWNLOAD_ATTEMPTS} attempts; last: {self._one_line(e)}')
                pause = self._jittered(wait)
                self.log(f"job {job_id}: the download did not work ({self._one_line(e)}); "
                         f"trying again in {pause:.0f}s")
                if self._wait(job_id, pause):
                    self._end_cancelled(job_id)
                wait = min(wait * 2, BACKOFF_CAP)

    def _upload(self, job_id, dest, remote_name):
        self.log(f"job {job_id}: uploading to the printer as {remote_name}")

        def progress(sent, total):
            self._stage(job_id, 'uploading', bytes_sent=sent, bytes_total=total)

        self._stage(job_id, 'uploading', bytes_sent=0, bytes_total=os.path.getsize(dest))
        wait = BACKOFF_START
        for attempt in range(1, UPLOAD_ATTEMPTS + 1):
            try:
                note = self.printer.upload(dest, remote_name, progress=progress,
                                           cancelled=lambda: self._interrupted(job_id))
                self.log(f"job {job_id}: uploaded; {note}")
                return
            except printer_module.UploadCancelled:
                if self.stopping.is_set():
                    self._remove_from_printer(job_id, remote_name)
                    raise _Stopped()
                self._end_cancelled(job_id, remote_name)
            except (printer_module.UploadFailed, OSError) as e:
                detail = getattr(e, 'detail', '') or self._one_line(repr(e))
                if attempt == UPLOAD_ATTEMPTS:
                    self._remove_from_printer(job_id, remote_name)
                    self._end(job_id, False, self._one_line(e), code='delivery.upload_failed',
                              detail=f'{UPLOAD_ATTEMPTS} attempts; last: {detail}')
                pause = self._jittered(wait)
                self.log(f"job {job_id}: the upload did not work ({self._one_line(e)}); "
                         f"trying again in {pause:.0f}s")
                if self._wait(job_id, pause):
                    self._end_cancelled(job_id, remote_name)
                self._await_free_printer(job_id, remote_name)
                self._stage(job_id, 'uploading', bytes_sent=0,
                            bytes_total=os.path.getsize(dest))
                wait = min(wait * 2, BACKOFF_CAP)

    def _gate(self, job_id, remote_name):
        """Ask the relay's start gate until it answers. A file is started only on its yes:
        a cancel, an unknown job, or a relay that cannot be reached for GATE_WAIT_SECONDS
        each mean it is never started.

        Before each ask the printer must be free on a whole, fresh picture (a wait for one
        is cancellable, and the gate is not asked meanwhile), and is asked for a whole
        report, so its answer arrives while the gate's answer travels: the one look after
        the gate then finds a fresh picture whenever the printer is answering."""
        started = self.clock()
        wait = BACKOFF_START
        while True:
            self._check_stop()
            self._await_free_printer(job_id, remote_name)
            request = getattr(self.printer, 'request_report', None)
            if request is not None:
                request()
            self._stage(job_id, 'starting')
            try:
                outcome = self.relay.start_gate(job_id, self.instance)
            except RelayError as e:
                if self.clock() - started >= GATE_WAIT_SECONDS:
                    self._remove_from_printer(job_id, remote_name)
                    self._end(job_id, False, 'the relay could not be reached to start the print',
                              code='delivery.job_failed', detail=self._one_line(e))
                pause = self._jittered(wait)
                self.log(f"job {job_id}: waiting for the relay before starting the print "
                         f"({self._one_line(e)}); asking again in {pause:.0f}s")
                self._wait(job_id, pause)
                wait = min(wait * 2, BACKOFF_CAP)
                continue
            if outcome == 'start':
                return
            if outcome == 'cancelled':
                self._end_cancelled(job_id, remote_name)
            if outcome == 'unknown':
                self._remove_from_printer(job_id, remote_name)
                self.log(f"job {job_id}: the relay no longer holds this job, so it is not "
                         "started")
                raise _JobEnded()
            # refused: another daemon process holds the start.
            self.log(f"job {job_id}: another daemon holds the start of this job; not starting "
                     "it here")
            self._await_start(job_id, remote_name)
            return

    def _start(self, job_id, remote_name):
        """Past the gate: one look, no wait, then the start command or none at all.

        Every wait came before the gate, where a cancel still ends the job. Here the
        printer's picture is read once: on a free printer the command goes; otherwise it
        does not, the file is removed, and the failure is acknowledged with a code that
        says the print was not started -- which is true."""
        snapshot = self.printer.snapshot()
        # Started already (by another daemon with the same pairing, say): never again.
        if self._acknowledge_if_going(
                job_id, remote_name, snapshot,
                note=f"the printer is already printing {remote_name}; not starting it again"):
            raise _JobEnded()
        held = self._watch_foreign_hold(job_id, snapshot)
        if not self._fresh(snapshot):
            self._remove_from_printer(job_id, remote_name)
            self._end(job_id, False, 'the printer stopped answering just before the start',
                      code='delivery.printer_unreachable_at_start',
                      detail=f'past the start gate, no whole, fresh report: '
                             f'{self._snapshot_detail(snapshot)}, '
                             f"{snapshot.get('report_age_s')!r} s old; not started")
        self._refuse_if_not_free(job_id, snapshot, remote_name)
        if held:
            self._remove_from_printer(job_id, remote_name)
            self._end(job_id, False, 'an earlier start still holds the printer',
                      code='delivery.earlier_start_unsettled',
                      detail=f'job {self.hold.job_id} was sent a start command and the '
                             'printer has not shown what became of it; not started')
        self._stage(job_id, 'starting')
        # The last moment a stop can come in before the command: after it, never.
        self._check_stop()
        self.log(f"job {job_id}: starting the print")
        before_state = snapshot.get('state')
        try:
            accepted = self.printer.start(remote_name)
        except Exception as e:
            # The command may or may not have reached the printer: never send it twice.
            # The printer's own report decides.
            self.log(f"job {job_id}: the start command may not have reached the printer "
                     f"({self._one_line(e)}); waiting for the printer to report it")
            accepted = True
        if not accepted:
            self._end(job_id, False, 'the printer refused the print start command',
                      code='delivery.start_refused')
        hold = StartHold(job_id, remote_name, self.clock(), sent_here=True,
                         before_state=before_state)
        self.hold = hold
        self._stage(job_id, 'starting', start_sent=True)
        self.log(f"job {job_id}: start accepted; waiting for the printer to report "
                 f"{remote_name}")
        self._await_start(job_id, remote_name, hold)

    def _await_start(self, job_id, remote_name, hold=None):
        """Hold the printer and wait for the evidence of what became of the start command
        (see "How a start is decided" in the guide): the print seen going, a proven end of
        ours, or START_SETTLE_SECONDS of whole, fresh pictures that do not show our print.
        A start that silently did nothing is reported, never shown as a success, and an end
        left over from the previous print is never taken for ours.

        While the printer is unreachable or its picture is old or not whole, nothing is
        counted -- it may be printing our file -- and it is asked for a whole report every
        REPORT_REQUEST_SECONDS. A wait with no end is honest here: the relay marks the job
        stale, and the job goes on the moment the printer speaks. After START_SLOW_SECONDS
        the stage says the printer has the file and has not shown the print yet."""
        if hold is None:
            hold = StartHold(job_id, remote_name, self.clock(), sent_here=False,
                             now=self.clock())
        if self.hold is None or self.hold.job_id == job_id:
            self.hold = hold
        last_request = None
        last_log = None
        last_slow_log = None
        last_hold_check = self.clock()
        while True:
            self._check_stop()
            snapshot = self.printer.snapshot()
            now = self.clock()
            fresh = self._fresh(snapshot)
            outcome = hold.watch(snapshot, now, fresh)
            if outcome is not None:
                if self.hold is hold:
                    self.hold = None
                self._settled(job_id, remote_name, hold)
            if now - last_hold_check >= HOLD_CHECK_SECONDS:
                last_hold_check = now
                if not self._relay_still_holds(job_id):
                    # The caller stopped following it, or the relay dropped it: nobody
                    # waits for this answer any more. The file is left where it is (it may
                    # be printing). The hold stays: the next delivery job waits for it to
                    # settle before its own start command can go.
                    self.log(f"job {job_id}: the relay no longer holds this job; no longer "
                             "waiting for the printer to report it (the printer stays held "
                             "until it shows what became of the start)")
                    raise _JobEnded()
            if not fresh:
                if last_request is None or now - last_request >= REPORT_REQUEST_SECONDS:
                    last_request = now
                    request = getattr(self.printer, 'request_report', None)
                    if request is not None:
                        request()
                if last_log is None or now - last_log >= LOG_EVERY:
                    last_log = now
                    self.log(f"job {job_id}: waiting for the printer to report the print; "
                             "it is not answering just now, so the wait is not counted")
            waited = now - hold.sent_at
            if waited >= START_SLOW_SECONDS:
                self._stage(job_id, 'start_not_shown', start_sent=True,
                            waited_s=int(waited))
                if last_slow_log is None or now - last_slow_log >= LOG_EVERY:
                    last_slow_log = now
                    self.log(f"job {job_id}: the printer has {remote_name} and has not shown "
                             f"the print yet ({int(waited)}s since the start command, "
                             f"{int(hold.counted)}s of fresh reports without it)")
            self.sleep(START_POLL_SECONDS)

    def _settled(self, job_id, remote_name, hold):
        """Acknowledge what the evidence says became of the start command."""
        snapshot = hold.evidence
        if hold.outcome == 'going':
            self._ack(job_id, True)
            raise _JobEnded()
        if hold.outcome == 'ended':
            if snapshot.get('state') == printer_module.FINISHED:
                self._ack(job_id, True)
                raise _JobEnded()
            self._end(job_id, False, f"printer error: {snapshot.get('error') or 'unknown'}",
                      code='delivery.printer_error_at_start',
                      detail=self._snapshot_detail(snapshot),
                      fields={'error': snapshot.get('error')})
        seconds = int(START_SETTLE_SECONDS)
        if hold.other is not None:
            name = printer_module.strip_job_suffix(hold.other.get('file') or '')
            self._end(job_id, False, f'the printer started {name} instead',
                      code='delivery.start_other_file',
                      detail=self._snapshot_detail(hold.other), fields={'name': name})
        self._end(job_id, False, f'the printer did not start the file within {seconds}s',
                  code='delivery.start_timeout',
                  detail=f'{int(hold.counted)} s of whole, fresh reports from the printer '
                         f'after the start command never showed {remote_name}; the last: '
                         f'{self._snapshot_detail(snapshot)}',
                  fields={'seconds': seconds})

    def _relay_still_holds(self, job_id):
        """Does the relay still hold this job? Asked through the start gate, which answers
        'unknown' once the relay no longer holds it. Any other answer, or no answer, is
        taken as yes: only the relay's own word ends the wait."""
        try:
            return self.relay.start_gate(job_id, self.instance) != 'unknown'
        except RelayError:
            return True

    @staticmethod
    def _fresh(snapshot):
        """Is this snapshot a whole, fresh picture: the printer's own recent word, with its
        main state reported since the daemon connected?"""
        if snapshot.get('state') == printer_module.UNREACHABLE:
            return False
        if snapshot.get('whole') is False:
            return False
        age = snapshot.get('report_age_s')
        return not isinstance(age, (int, float)) or age <= FRESH_REPORT_SECONDS

    @staticmethod
    def _busy_fields(snapshot):
        fields = {'name': printer_module.strip_job_suffix(snapshot.get('file') or '')
                  or 'a file'}
        if isinstance(snapshot.get('percent'), int):
            fields['percent'] = snapshot['percent']
        return fields

    def _acknowledge_if_going(self, job_id, remote_name, snapshot=None, *, note=None):
        """Acknowledge when a whole, fresh picture shows our file going (or waiting for a
        person). `note` is logged when it does. An end naming our file is not enough here:
        only StartHold can tell this print's end from one left over before its start.

        The file name carries the job id, so this cannot mistake the previous print for
        ours -- which is what lets a restarted daemon recognise a job it already started."""
        if snapshot is None:
            snapshot = self.printer.snapshot()
        if not (self._fresh(snapshot) and snapshot.get('state') in _GOING
                and printer_module.reports_file(snapshot, remote_name)):
            return False
        if note:
            self.log(note)
        if self.hold is not None and self.hold.job_id == job_id:
            self.hold = None
        self._ack(job_id, True)
        return True

    @staticmethod
    def _snapshot_detail(snapshot):
        return (f"state {snapshot.get('state')}, file {snapshot.get('file')!r}, "
                f"error {snapshot.get('error')!r}, stage {snapshot.get('stage_code')!r}, "
                f"{snapshot.get('percent')!r} percent")

    @staticmethod
    def _discard(path):
        """The sliced file is the relay's copy, not this computer's: it goes as soon as the
        printer has it, so a small disk cannot fill up with old prints."""
        try:
            os.unlink(path)
        except OSError:
            pass

    @staticmethod
    def _one_line(error):
        """One line for the status line; the traceback belongs in the log only.

        A download path is a bearer token, and this string goes back to the relay and to
        the caller, so any that survived into the message is redacted first."""
        text = str(error) or error.__class__.__name__
        text = _DOWNLOAD_PATH_RE.sub(r'\1<token>', text)
        return text.splitlines()[0][:200]
