"""The in-process job queue for slices, with progress reports, cancellation and cleanup.

A job table in process memory plus a thread pool. The pool size is the number of Orca
processes allowed at once (MAX_RUNNING); the queue beyond it is deliberately small,
because queued work nobody will wait for is worse than an honest refusal.

Every job's latest progress report (contracts/progress-report.md) is kept, with a
sequence number that rises by one with every report, so a follower can tell a missed
report from a repeated one and a late follower gets the latest at once. A job ends in
one of the final states done, failed or cancelled, and sends nothing after it.

The places: MAX_RUNNING running and MAX_QUEUED waiting, counted together over every user
key. A job being stopped (asked to end early) holds no place, though it may still hold an
Orca until that Orca is gone. A further job is refused (QueueFull).

Every queued report carries `ahead`: the jobs running (a job being stopped included, since
it still holds its Orca) and the jobs waiting before it, in the order they were accepted,
which is the order the executor runs them. Whenever that count changes a new report is
sent; no other report carries it.

A repeat (submit with the user key and submission_id of a job the pool remembers, for as
long as it remembers the job) raises RepeatedSubmission naming that job, and changes
nothing; it is looked for before anything else, so it is answered while the pool closes
and while every place is taken. remembered() looks for one without submitting.

A replacement: a job submitted with the user key and plate_id of an earlier job that is
still queued or running ends the earlier one early, with cancel_reason "replaced", and the
earlier one gives up its place before the new one is counted. A later job refused because
every place is taken replaces nothing.

Ending early (cancel, with a reason of CANCEL_REASONS): a queued job is cancelled at once;
a running one is asked to stop (its worker's Stop), and is reported cancelled only once the
worker has returned, which for a slice means Orca and every child it started are gone (a
slice still writing its plate 3MF stops at the next object and never starts Orca). A stop
that arrives before the final report wins over a slice that finishes at the same instant:
the job is cancelled and its sliced file discarded. Ending a finished job changes nothing.
Every cancelled report carries `cancel_reason`.

A job goes on whether or not anything follows it: nothing ends a job on account of its
followers. A final job's record, and its sliced file through `on_discard`, go RECORD_TTL_S
(two hours) after its final report (sweep). delete_file() gives up a done job's sliced file
once the front server has stored it: the record stays until it expires, and says the file
is no longer held (file_deleted).

Asked to stop (stop(), the first SIGTERM): every waiting job is ended early with
cancel_reason "shutdown", every new one is refused (Stopping, never QueueFull; a repeat is
still answered), and the running one runs to its end; drained() and wait_drained() say when
nothing runs and no done job still holds a sliced file. shutdown() (a second stop, and the
end of serve) cancels every job and waits for every worker.

One structured log line (a dict passed to `log`) per job transition: the job id, the
state, the plate configuration's description (profiles, overrides, parts, instances), the outcome, the
error code and Orca's reason, Orca's peak memory (with the worker's memory_note when a
delivered slice's peak passed the ceiling, and its stop_note when a stop reached Orca after
its sliced file was complete) and the wall time. The log sink is called through SafeLog:
a sink that raises is counted (log_failures) and never changes what a job does.

MAX_RUNNING stays at one until the production host is measured. The rule when
revisiting: min(vCPU count, memory / peak resident memory of one slice), never below one.
"""
import secrets
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .slicer import SliceCancelled, Stop

MAX_RUNNING = 1          # Orca processes at once
MAX_QUEUED = 2           # jobs waiting beyond the running ones
RECORD_TTL_S = 7200      # a final record expires this long after its final report: two hours
WAIT_S = 15.0            # a follower's wait when nothing changes (a keep-alive cadence)
SWEEP_INTERVAL_S = 10    # the sweeper's cadence
# Why a slice job ended early (contracts/progress-report.md, cancel_reason): the same plate's
# later slice job replaced it; the slice service was asked to stop; DELETE /slices/<job>.
CANCEL_REASONS = ("replaced", "shutdown", "requested")
REQUESTED = "requested"

FINAL = ("done", "failed", "cancelled")
GENERIC_FAILURE = "The slicer failed unexpectedly."
# Every stage a slice job reports, in order, with its words for a user. Orca's own
# stages are slicer.ORCA_STAGES' values.
STAGES = {
    "queued": "Waiting for the slicer",
    "building_plate": "Building the plate",
    "slicing": "Slicing the plate",          # Orca has started; its own messages refine this
    "loading": "Loading the plate",
    "preparing": "Preparing to slice",
    "slicing_mesh": "Slicing the parts into layers",
    "generating_walls": "Generating walls",
    "generating_infill": "Generating infill",
    "generating_supports": "Checking and generating supports",
    "optimizing_toolpath": "Optimizing the toolpath",
    "generating_gcode": "Generating G-code",
    "exporting": "Writing the sliced file",
    "reading_result": "Reading the sliced file",
}


class QueueFull(Exception):
    """Every place is taken: MAX_RUNNING running and MAX_QUEUED waiting."""


STOPPING_DETAIL = "asked to stop; finishing the running slice job before exiting"


class Stopping(Exception):
    """The slice service has been asked to stop: no new slice job is accepted (slice.stopping,
    never slice.busy)."""

    def __init__(self, detail=STOPPING_DETAIL):
        super().__init__(detail)
        self.detail = detail


class RepeatedSubmission(Exception):
    """A submission the pool remembers: `job_id` is the job its first attempt started."""

    def __init__(self, job_id):
        super().__init__(job_id)
        self.job_id = job_id


class JobFailure(Exception):
    """A worker failure with a message a user reads and details for the log only."""

    def __init__(self, message, details=""):
        super().__init__(message)
        self.message = message
        self.details = details


class SafeLog:
    """The one place a log sink's failure is swallowed: calls `sink(entry)`, and when the
    sink raises (a closed or broken stderr), counts the failure in `failures` and goes on.
    A log that fails never changes what a job does."""

    def __init__(self, sink):
        self._sink = sink
        self.failures = 0

    def __call__(self, entry):
        try:
            self._sink(entry)
        except Exception:      # noqa: BLE001 - whatever the sink raises, the job goes on
            self.failures += 1


class JobContext:
    """What a worker gets: `stop`, set when the job is cancelled, and `progress(stage,
    fraction, message)`, which sends a progress report."""

    def __init__(self, pool, job_id, stop):
        self._pool, self.job_id, self.stop = pool, job_id, stop

    def progress(self, stage, fraction=None, message=None):
        self._pool._progress(self.job_id, stage, fraction)


UNEXPECTED_DETAIL_CHARS = 2000     # a bug's own words, at most: they may carry what a caller sent


def exception_text(exc):
    """`<type>: <message>` of an exception, cut at UNEXPECTED_DETAIL_CHARS."""
    text = f"{type(exc).__name__}: {exc}"
    return text if len(text) <= UNEXPECTED_DETAIL_CHARS else text[:UNEXPECTED_DETAIL_CHARS] + " [cut]"


def rfc3339(seconds):
    """A moment of the wall clock as the HTTP interface writes a time: UTC, to the second."""
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_error(exc):
    return {"code": "slice.unexpected", "message": GENERIC_FAILURE, "remedy": "Slice again.", "retryable": False,
            "detail": exception_text(exc)}


class JobPool:
    """`worker(job_id, payload, context)` returns a dict (the job's result); an exception
    fails the job with `error_report(exc)` as its error, SliceCancelled cancels it.
    `on_discard(result)` removes what a result left behind (its sliced file) when the result
    is thrown away; `cleanup(payload)` removes what a job's payload holds (its uploaded
    files) once the job ends failed or cancelled, or its record expires."""

    def __init__(self, worker, *, executor=None, max_running=MAX_RUNNING, max_queued=MAX_QUEUED,
                 ttl_s=RECORD_TTL_S, clock=time.monotonic, log=None, error_report=None, on_discard=None,
                 cleanup=None, wall_clock=None):
        self._worker = worker
        self._wall_clock = wall_clock or time.time      # the moment a job ended (ended_at), in UTC
        self._executor = executor or ThreadPoolExecutor(max_workers=max_running, thread_name_prefix="slice")
        self._places = max_running + max_queued
        self._ttl_s = ttl_s
        self._clock = clock
        log = log or (lambda entry: None)
        self._log = log if isinstance(log, SafeLog) else SafeLog(log)
        self._error_report = error_report or _default_error
        self._on_discard = on_discard or (lambda result: None)
        self._cleanup_payload = cleanup or (lambda payload: None)
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._jobs = {}
        self._stopping = threading.Event()    # asked to stop once: stop()
        self._closing = threading.Event()     # shutdown(): the second stop, or the end of serve

    # -- public ---------------------------------------------------------

    def submit(self, payload=None, *, describe=None, expected_s=None, user_key=None, plate_id=None,
               submission_id=None):
        """Queue a job; its id. `describe` (a dict) goes into every log line of the job;
        `user_key` is whose it is (owned_by); `plate_id` names its plate, whose earlier
        unfinished job of the same user key it replaces; `submission_id` names this
        submission. Raises RepeatedSubmission for a submission the pool remembers, and
        QueueFull when every place is taken or the pool closes."""
        job_id = "j" + secrets.token_hex(8)
        with self._lock:
            repeat = self._remembered(user_key, submission_id)
            if repeat is not None:
                raise RepeatedSubmission(repeat)
            if self._stopping.is_set() or self._closing.is_set():
                raise Stopping()
            earlier = [(other, r) for other, r in self._jobs.items() if r["state"] not in FINAL
                       and plate_id is not None and user_key is not None
                       and (r["user_key"], r["plate_id"]) == (user_key, plate_id)]
            taken = sum(1 for r in self._jobs.values() if self._holds_a_place(r))
            if taken - sum(1 for _other, r in earlier if self._holds_a_place(r)) >= self._places:
                raise QueueFull()
            for other, record in earlier:
                self._end_early(other, record, "replaced")
            ahead = self._ahead_of_a_new_job()
            self._jobs[job_id] = {"report": {"job": job_id, "state": "queued", "stage": "queued",
                                             "stage_label": STAGES["queued"], "elapsed_s": 0.0, "sequence": 1},
                                  "state": "queued", "submitted": self._clock(), "started": None, "finished": None,
                                  "stop": Stop(), "result": None, "describe": describe or {},
                                  "expected_s": expected_s, "cancel_asked": None, "payload": payload,
                                  "file_deleted": False, "ended_at": None,
                                  "user_key": user_key, "plate_id": plate_id, "submission_id": submission_id}
            if expected_s is not None:
                self._jobs[job_id]["report"]["expected_s"] = expected_s
            self._jobs[job_id]["report"]["ahead"] = ahead
            self._log_transition(job_id, "queued")
        self._after_ending_early(earlier, "replaced")
        try:
            self._executor.submit(self._run_next)
        except RuntimeError:
            # The executor was shut down between the look above and here (a second stop):
            # the job ends with it, and the submission is answered as one while stopping.
            self.cancel(job_id, reason="shutdown")
            raise Stopping() from None
        return job_id

    def remembered(self, user_key, submission_id):
        """The id of the job the pool remembers under this user key and submission_id, or None."""
        with self._lock:
            return self._remembered(user_key, submission_id)

    def payload(self, job_id):
        """The payload a job was submitted with, or None for an unknown job."""
        with self._lock:
            record = self._jobs.get(job_id)
            return record["payload"] if record else None

    def get(self, job_id):
        """The job's latest progress report, or None for an unknown job."""
        with self._lock:
            record = self._jobs.get(job_id)
            return self._snapshot(record) if record else None

    def owned_by(self, job_id, user_key):
        """Whether the job is known and was submitted under `user_key`."""
        with self._lock:
            record = self._jobs.get(job_id)
            return record is not None and record["user_key"] == user_key

    def result(self, job_id):
        """The worker's result of a done job, else None."""
        with self._lock:
            record = self._jobs.get(job_id)
            return record["result"] if record and record["state"] == "done" else None

    def delete_file(self, job_id):
        """The front server has stored the job's sliced file: (answer, result). The answer is
        "deleted" for a job that has ended (done, failed or cancelled, the first time and
        every time after), "not_ready" for one waiting or running, "unknown" for one the pool
        does not know. `result` is the done job's result the first time only, whose sliced
        file the caller removes; None otherwise. The record stays until it expires."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return "unknown", None
            if record["state"] not in FINAL:
                return "not_ready", None
            if record["file_deleted"] or record["result"] is None:
                return "deleted", None
            record["file_deleted"] = True
            self._log_transition(job_id, "file_deleted")
            self._changed.notify_all()            # a stopping slice service may now be drained
            return "deleted", record["result"]

    def listing(self):
        """Every job the pool remembers, waiting, running or ended, of every user key, in the
        order accepted (contracts/slice-http-interface.md, GET /slices): job, user_key,
        plate_id, submission_id, progress (its latest report), file_on_disk (a done job's
        sliced file not yet given up by delete_file) and ended_at (RFC 3339 in UTC, None
        while it waits or runs)."""
        with self._lock:
            return [{"job": job_id, "user_key": r["user_key"], "plate_id": r["plate_id"],
                     "submission_id": r["submission_id"], "progress": self._snapshot(r),
                     "file_on_disk": r["state"] == "done" and r["result"] is not None and not r["file_deleted"],
                     "ended_at": r["ended_at"]} for job_id, r in self._jobs.items()]

    def file_deleted(self, job_id):
        """Whether delete_file() gave up the job's sliced file."""
        with self._lock:
            record = self._jobs.get(job_id)
            return record is not None and record["file_deleted"]

    def wait(self, job_id, after_sequence, timeout=WAIT_S):
        """The latest report once its sequence is past `after_sequence`, or the latest when
        `timeout` runs out; None for an unknown job (or one that expired)."""
        with self._lock:
            def ready():
                record = self._jobs.get(job_id)
                return record is None or record["report"]["sequence"] > after_sequence
            self._changed.wait_for(ready, timeout)
            record = self._jobs.get(job_id)
            return self._snapshot(record) if record else None

    def follow(self, job_id, wait_s=WAIT_S):
        """Every report of a job from the latest on, ending with its final report. A report
        repeats only when `wait_s` passes with no change (a keep-alive). Following a job, or
        ceasing to, changes nothing about the job."""
        report = self.get(job_id)
        while report is not None:
            yield report
            if report["state"] in FINAL:
                return
            report = self.wait(job_id, report["sequence"], timeout=wait_s)

    def cancel(self, job_id, reason=REQUESTED):
        """End a job early, with `reason` (one of CANCEL_REASONS) as its cancel_reason.
        Returns "cancelled" (it was queued, and is now cancelled), "cancelling" (it is
        running; its final report will say cancelled once its work has stopped), "finished"
        (it had already ended; nothing changes) or "unknown". A job already being stopped
        keeps its first reason."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return "unknown"
            if record["state"] in FINAL:
                return "finished"
            was_queued = record["state"] == "queued"
            self._end_early(job_id, record, reason)
        self._after_ending_early([(job_id, record)], reason)
        return "cancelled" if was_queued else "cancelling"

    def sweep(self, now=None):
        """Drop the records that expired, with their files; how many."""
        now = self._clock() if now is None else now
        with self._lock:
            expired = [job_id for job_id, r in self._jobs.items() if r["state"] in FINAL
                       and now - r["finished"] >= self._ttl_s]
            discards = []
            for job_id in expired:
                record = self._jobs.pop(job_id)
                discards.append((job_id, None if record["file_deleted"] else record["result"], record["payload"]))
                self._log_transition(job_id, "expired", record=record)
            self._changed.notify_all()
        for job_id, result, payload in discards:
            if result is not None:
                self._on_discard(result)
            self._cleanup(payload, job_id)
        return len(expired)

    def start_sweeper(self, interval_s=SWEEP_INTERVAL_S, also=(), wait=None):
        """A daemon thread that sweeps every `interval_s` until shutdown(), calling each of
        `also` after each sweep (the part store's sweep). `wait(interval_s)` lets one interval
        pass and returns True to end the sweeper: the pool's closing by default, a test's
        clock in the fast suite; the sweeper also ends once the pool closes."""
        wait = wait or self._closing.wait

        def loop():
            while not wait(interval_s) and not self._closing.is_set():
                try:
                    self.sweep()
                    for sweep in also:
                        sweep()
                except Exception:   # never let the sweeper die
                    self._log({"event": "slice_sweeper_error", "traceback": traceback.format_exc()})
        thread = threading.Thread(target=loop, name="slice-jobs-sweeper", daemon=True)
        thread.start()
        return thread

    def stop(self):
        """Asked to stop (the first SIGTERM or Ctrl-C): refuse every new job (Stopping, a
        repeat still answered), end every waiting job early with cancel_reason "shutdown",
        and let the running one run to its end. The ids of the jobs it ended; asked again,
        it ends nothing more."""
        with self._lock:
            self._stopping.set()
            waiting = [(job_id, r) for job_id, r in self._jobs.items() if r["state"] == "queued"]
            for job_id, record in waiting:
                self._end_early(job_id, record, "shutdown")
        self._after_ending_early(waiting, "shutdown")
        return [job_id for job_id, _record in waiting]

    def stopping(self):
        """Whether the pool has been asked to stop (stop() or shutdown())."""
        return self._stopping.is_set() or self._closing.is_set()

    def drained(self):
        """Whether nothing is waiting or running and no done job still holds a sliced file
        the front server has not collected (delete_file): a stopping slice service may exit."""
        with self._lock:
            return self._drained()

    def wait_drained(self, timeout=None):
        """Wait until the pool is drained or shut down; whether it is drained or shut down."""
        with self._lock:
            return self._changed.wait_for(lambda: self._drained() or self._closing.is_set(), timeout)

    def shutdown(self):
        """Refuse new jobs, cancel every job and wait until every worker has returned: the
        second stop, and the end of serve."""
        self._closing.set()
        with self._lock:
            self._changed.notify_all()            # a wait for the drain ends
        with self._lock:
            ids = [job_id for job_id, r in self._jobs.items() if r["state"] not in FINAL]
        for job_id in ids:
            self.cancel(job_id, reason="shutdown")
        shutdown = getattr(self._executor, "shutdown", None)
        if shutdown:
            shutdown(wait=True)

    def log_failures(self):
        """How many log lines the log sink failed to take (SafeLog) since the pool started."""
        return self._log.failures

    def counts(self):
        with self._lock:
            states = [r["state"] for r in self._jobs.values()]
        return {state: states.count(state) for state in ("queued", "running", "done", "failed", "cancelled")}

    # -- internals ------------------------------------------------------

    def _remembered(self, user_key, submission_id):
        """Under the lock: the job remembered under this user key and submission_id, or None."""
        if user_key is None or submission_id is None:
            return None
        for job_id, record in self._jobs.items():
            if (record["user_key"], record["submission_id"]) == (user_key, submission_id):
                return job_id
        return None

    def _drained(self):
        """Under the lock: see drained()."""
        return all(r["state"] in FINAL and (r["state"] != "done" or r["result"] is None or r["file_deleted"])
                   for r in self._jobs.values())

    @staticmethod
    def _holds_a_place(record):
        return record["state"] not in FINAL and record["cancel_asked"] is None

    def _ahead_of_a_new_job(self):
        """Under the lock, before a new job is added: every job running or queued is ahead of it."""
        return sum(1 for r in self._jobs.values() if r["state"] in ("running", "queued"))

    def _refresh_ahead(self):
        """Under the lock: a new report for every queued job whose count ahead changed."""
        ahead = sum(1 for r in self._jobs.values() if r["state"] == "running")
        for record in self._jobs.values():
            if record["state"] == "queued":
                if record["report"].get("ahead") != ahead:
                    self._send(record, ahead=ahead)
                ahead += 1

    def _end_early(self, job_id, record, reason):
        """Under the lock, for a job that has not ended: end it at once if it is queued, or
        ask it to stop if it is running. A job keeps the first reason it was given."""
        if record["state"] == "queued":
            record["cancel_asked"] = reason
            self._finish(record, job_id, "cancelled")
        elif record["cancel_asked"] is None:
            record["cancel_asked"] = reason
            self._log_transition(job_id, "cancelling", reason=reason)

    def _after_ending_early(self, ended, reason):
        """Outside the lock, for each (job_id, record) _end_early ended or asked: a job that
        never started has its files removed; a started one has its stop set (which changes
        nothing once its worker has returned)."""
        for job_id, record in ended:
            if record["started"] is None:
                self._cleanup(record["payload"], job_id)
            else:
                record["stop"].set(reason)

    def _snapshot(self, record):
        report = dict(record["report"])
        if record["state"] == "running":
            report["elapsed_s"] = round(self._clock() - record["started"], 3)
        return report

    def _send(self, record, **fields):
        """A new report for the job (under the lock): the fields changed, sequence + 1."""
        report = dict(record["report"])
        for key, value in fields.items():
            if value is None:
                report.pop(key, None)
            else:
                report[key] = value
        report["elapsed_s"] = round(self._clock() - record["started"], 3) if record["started"] is not None else 0.0
        report["sequence"] = record["report"]["sequence"] + 1
        record["report"] = report
        self._changed.notify_all()

    def _progress(self, job_id, stage, fraction):
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None or record["state"] != "running":
                return
            stage = stage if stage in STAGES else record["report"].get("stage")
            if stage == record["report"].get("stage") and fraction == record["report"].get("fraction"):
                return
            self._send(record, stage=stage, stage_label=STAGES.get(stage), fraction=fraction)

    def _finish(self, record, job_id, state, error=None, result=None, exc=None, discarded=None):
        record["state"] = state
        record["finished"] = self._clock()
        record["ended_at"] = rfc3339(self._wall_clock())
        record["result"] = result
        if state == "cancelled":       # always with its reason; a stop the pool never asked counts as requested
            record["cancel_asked"] = record["cancel_asked"] or REQUESTED
        # A cancelled report keeps the stage it was ended at, as the contract's example of a
        # replaced slice job does; a done or failed one has no stage left.
        kept = {} if state == "cancelled" else {"stage": None, "stage_label": None}
        self._send(record, state=state, fraction=None, error=error, ahead=None,
                   cancel_reason=record["cancel_asked"] if state == "cancelled" else None, **kept)
        self._log_transition(job_id, state, exc=exc, discarded=discarded)
        self._refresh_ahead()

    def _log_transition(self, job_id, state, exc=None, reason=None, record=None, discarded=None):
        record = record or self._jobs[job_id]
        entry = {"event": "slice_job", "job": job_id, "state": state, **record["describe"]}
        report = record["report"]
        if record["started"] is not None:
            entry["wall_s"] = round((record["finished"] or self._clock()) - record["started"], 3)
        result = record["result"] or {}
        for key in ("peak_rss_kb", "orca_wall_s", "file", "memory_note", "stop_note"):
            if key in result:
                entry[key] = result[key]
        if discarded is not None:
            entry["file_discarded"] = discarded.get("file")      # a finished slice nobody will now fetch
        if report.get("error"):
            entry["error_code"] = report["error"]["code"]
            entry["error_detail"] = report["error"]["detail"]
        if exc is not None:
            for name in ("reason", "peak_rss_kb"):
                if getattr(exc, name, None):
                    entry["orca_reason" if name == "reason" else name] = getattr(exc, name)
        if record["cancel_asked"]:
            entry["cancel_reason"] = record["cancel_asked"]
        if reason:
            entry["cancel_reason"] = reason
        self._log(entry)

    def _run_next(self):
        """One task of the executor: run the oldest waiting job, if any. Every submit gives
        the executor one task and every task starts at most one job, so no waiting job is
        left without a task; a task whose own job was ended while waiting runs the next one,
        or nothing. Taking the oldest, not the task's own, keeps the order of acceptance
        even when two submits reach the executor in the other order (it is called outside
        the lock), and with it every count ahead: starting the oldest changes none."""
        with self._lock:
            job_id = next((j for j, r in self._jobs.items() if r["state"] == "queued"), None)
            if job_id is None:
                return
            record = self._jobs[job_id]
            payload = record["payload"]
            record["state"] = "running"
            record["started"] = self._clock()
            self._send(record, state="running", stage=None, stage_label=None, ahead=None)
            self._log_transition(job_id, "running")
            stop = record["stop"]
        context = JobContext(self, job_id, stop)
        result, error, state, exc = None, None, "done", None
        try:
            result = self._worker(job_id, payload, context)
        except SliceCancelled as caught:
            state, exc = "cancelled", caught
        except Exception as caught:
            state, exc = "failed", caught
            try:
                error = self._error_report(caught)
            except Exception:
                error = _default_error(caught)
            if not isinstance(caught, JobFailure) and error.get("code") == "slice.unexpected":
                error = dict(error, detail=error["detail"] + "\n" + traceback.format_exc()[-2000:])
        discard = None
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                discard, state = result, "gone"
            else:
                if state == "done" and record["cancel_asked"]:
                    state, discard = "cancelled", result      # the cancel came first
                    result = None
                self._finish(record, job_id, state, error=error, result=result, exc=exc, discarded=discard)
        if discard is not None:
            self._on_discard(discard)
        if state != "done":
            self._cleanup(payload, job_id)

    def _cleanup(self, payload, job_id):
        try:
            self._cleanup_payload(payload)
        except Exception:      # a cleanup that fails must not take the pool with it
            self._log({"event": "slice_cleanup_error", "job": job_id, "traceback": traceback.format_exc()})
