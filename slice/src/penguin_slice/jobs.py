"""The in-process job queue for slices, with progress reports, cancellation and cleanup.

A job table in process memory plus a thread pool. The pool size is the number of Orca
processes allowed at once (MAX_RUNNING); the queue beyond it is deliberately small,
because queued work nobody will wait for is worse than an honest refusal.

Every job's latest progress report (contracts/progress-report.md) is kept, with a
sequence number that rises by one with every report, so a subscriber can tell a missed
report from a repeated one and a late subscriber gets the latest at once. A job ends in
one of the final states done, failed or cancelled, and sends nothing after it.

Cancellation (cancel): a queued job is cancelled at once; a running one is asked to stop
(its worker's Stop), and is reported cancelled only once the worker has returned, which
for a slice means Orca and every child it started are gone (a slice still writing its
plate 3MF stops at the next object and never starts Orca). A cancel that arrives before
the final report wins over a slice that finishes at the same instant: the job is
cancelled and its sliced file discarded. Cancelling a finished job changes nothing.

Cleanup (sweep): a job nobody is following is cancelled once ABANDON_GRACE_S has passed
since its last subscriber left (or since it was submitted, if none ever came); a
subscriber that returns within the grace time keeps it. Nobody is then waiting for its
file, so an abandoned job ends exactly as a caller's cancel does: `cancelled`, a slice that
finishes at that instant discarded, its log lines carrying cancel_reason "abandoned" (and
file_discarded, the name of a finished sliced file thrown away). A final job's record, and its
sliced file through `on_discard`, go RECORD_TTL_S after its final report. shutdown()
cancels every job and waits for every worker.

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

from .slicer import SliceCancelled, Stop

MAX_RUNNING = 1          # Orca processes at once
MAX_QUEUED = 2           # jobs waiting beyond the running ones
RECORD_TTL_S = 3600      # a final record expires this long after its final report
ABANDON_GRACE_S = 120    # a job nobody follows is cancelled after this long
WAIT_S = 15.0            # a subscriber's wait when nothing changes (a keep-alive cadence)
SWEEP_INTERVAL_S = 10    # the sweeper's cadence

FINAL = ("done", "failed", "cancelled")
GENERIC_FAILURE = "The slicer failed unexpectedly."
# Every stage a slice job reports, in order, with its words for a student. Orca's own
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
    """The pool is running MAX_RUNNING jobs and MAX_QUEUED more are waiting."""


class JobFailure(Exception):
    """A worker failure with a student-facing message and log-only details."""

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
                 ttl_s=RECORD_TTL_S, abandon_grace_s=ABANDON_GRACE_S, clock=time.monotonic, log=None,
                 error_report=None, on_discard=None, cleanup=None):
        self._worker = worker
        self._executor = executor or ThreadPoolExecutor(max_workers=max_running, thread_name_prefix="slice")
        self._max_queued = max_queued
        self._ttl_s = ttl_s
        self._grace_s = abandon_grace_s
        self._clock = clock
        log = log or (lambda entry: None)
        self._log = log if isinstance(log, SafeLog) else SafeLog(log)
        self._error_report = error_report or _default_error
        self._on_discard = on_discard or (lambda result: None)
        self._cleanup_payload = cleanup or (lambda payload: None)
        self._lock = threading.Lock()
        self._changed = threading.Condition(self._lock)
        self._jobs = {}
        self._closing = threading.Event()

    # -- public ---------------------------------------------------------

    def submit(self, payload=None, *, describe=None, expected_s=None, user_key=None):
        """Queue a job; its id. `describe` (a dict) goes into every log line of the job;
        `user_key` is whose it is (owned_by)."""
        job_id = "j" + secrets.token_hex(8)
        with self._lock:
            if self._closing.is_set() or sum(1 for r in self._jobs.values() if r["state"] == "queued") >= \
                    self._max_queued:
                raise QueueFull()
            now = self._clock()
            self._jobs[job_id] = {"report": {"job": job_id, "state": "queued", "stage": "queued",
                                             "stage_label": STAGES["queued"], "elapsed_s": 0.0, "sequence": 1},
                                  "state": "queued", "submitted": now, "started": None, "finished": None,
                                  "stop": Stop(), "subscribers": 0, "alone_since": now, "result": None,
                                  "describe": describe or {}, "expected_s": expected_s, "cancel_asked": None,
                                  "payload": payload, "user_key": user_key}
            if expected_s is not None:
                self._jobs[job_id]["report"]["expected_s"] = expected_s
            self._log_transition(job_id, "queued")
        self._executor.submit(self._run, job_id, payload)
        return job_id

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

    def subscribe(self, job_id):
        with self._lock:
            record = self._jobs.get(job_id)
            if record:
                record["subscribers"] += 1
                record["alone_since"] = None
            return record is not None

    def unsubscribe(self, job_id):
        with self._lock:
            record = self._jobs.get(job_id)
            if record and record["subscribers"] > 0:
                record["subscribers"] -= 1
                if record["subscribers"] == 0:
                    record["alone_since"] = self._clock()

    def follow(self, job_id, wait_s=WAIT_S):
        """Every report of a job from the latest on, ending with its final report; while
        it runs the caller counts as a subscriber. A report repeats only when `wait_s`
        passes with no change (a keep-alive)."""
        if not self.subscribe(job_id):
            return
        try:
            report = self.get(job_id)
            while report is not None:
                yield report
                if report["state"] in FINAL:
                    return
                report = self.wait(job_id, report["sequence"], timeout=wait_s)
        finally:
            self.unsubscribe(job_id)

    def cancel(self, job_id, reason="cancel"):
        """Cancel a job. Returns "cancelled" (it was queued, and is now cancelled),
        "cancelling" (it is running; its final report will say cancelled once its work has
        stopped), "finished" (it had already ended; nothing changes) or "unknown"."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return "unknown"
            if record["state"] in FINAL:
                return "finished"
            was_queued = record["state"] == "queued"
            if was_queued:
                record["cancel_asked"] = reason
                self._finish(record, job_id, "cancelled")
            else:
                first = record["cancel_asked"] is None
                record["cancel_asked"] = record["cancel_asked"] or reason
                if first:
                    self._log_transition(job_id, "cancelling", reason=reason)
        if was_queued:
            self._cleanup(record["payload"])
            return "cancelled"
        record["stop"].set(reason)
        return "cancelling"

    def sweep(self, now=None):
        """Cancel abandoned jobs and drop expired records; (abandoned, expired) counts."""
        now = self._clock() if now is None else now
        with self._lock:
            abandoned = [job_id for job_id, r in self._jobs.items() if r["state"] not in FINAL
                         and r["alone_since"] is not None and now - r["alone_since"] >= self._grace_s]
            expired = [job_id for job_id, r in self._jobs.items() if r["state"] in FINAL
                       and now - r["finished"] >= self._ttl_s]
            discards = []
            for job_id in expired:
                record = self._jobs.pop(job_id)
                discards.append((record["result"], record["payload"]))
                self._log_transition(job_id, "expired", record=record)
            self._changed.notify_all()
        for job_id in abandoned:
            self.cancel(job_id, reason="abandoned")
        for result, payload in discards:
            if result is not None:
                self._on_discard(result)
            self._cleanup(payload)
        return len(abandoned), len(expired)

    def start_sweeper(self, interval_s=SWEEP_INTERVAL_S, also=()):
        """A daemon thread that sweeps every `interval_s` until shutdown(), calling each of
        `also` after each sweep (the part store's sweep)."""
        def loop():
            while not self._closing.wait(interval_s):
                try:
                    self.sweep()
                    for sweep in also:
                        sweep()
                except Exception:   # never let the sweeper die
                    self._log({"event": "slice_sweeper_error", "traceback": traceback.format_exc()})
        thread = threading.Thread(target=loop, name="slice-jobs-sweeper", daemon=True)
        thread.start()
        return thread

    def shutdown(self):
        """Refuse new jobs, cancel every job and wait until every worker has returned."""
        self._closing.set()
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
        record["result"] = result
        self._send(record, state=state, stage=None, stage_label=None, fraction=None, error=error)
        self._log_transition(job_id, state, exc=exc, discarded=discarded)

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

    def _run(self, job_id, payload=None):
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None or record["state"] != "queued":      # cancelled while queued
                return
            record["state"] = "running"
            record["started"] = self._clock()
            self._send(record, state="running", stage=None, stage_label=None)
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
            self._cleanup(payload)

    def _cleanup(self, payload):
        try:
            self._cleanup_payload(payload)
        except Exception:      # a cleanup that fails must not take the pool with it
            self._log({"event": "slice_cleanup_error", "traceback": traceback.format_exc()})
