"""jobs.JobPool: progress reports, cancellation, abandonment, expiry, shutdown and the log.

Synchronous stand-ins for the executor and an injected clock. No test sleeps or waits on a
timeout that is expected to run out: a worker that must stay running blocks on an Event
the test sets, every wait that must return early has no timeout or a fail-safe that is
reached only when the test is failing.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from penguin_slice import jobs
from penguin_slice.errors import error_report
from penguin_slice.jobs import FINAL, STAGES, JobFailure, JobPool, QueueFull
from penguin_slice.slicer import ORCA_STAGES, SliceCancelled, SliceError

FAILSAFE_S = 10      # only reached when a test is about to fail


class ImmediateExecutor:
    """Runs the submitted function on the calling thread, like a pool with a free worker."""
    def submit(self, fn, *args):
        fn(*args)


class HeldExecutor:
    """Accepts work and runs it only when told to: every job stays queued until then."""
    def __init__(self):
        self.pending = []

    def submit(self, fn, *args):
        self.pending.append((fn, args))

    def run_next(self):
        fn, args = self.pending.pop(0)
        fn(*args)


class FakeClock:
    """Stands still until moved."""
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


def good_worker(job_id, payload, context):
    context.progress("building_plate")
    context.progress("slicing_mesh", 0.07)
    context.progress("slicing_mesh", 0.07)            # a repeat sends nothing
    context.progress("generating_gcode", 0.75)
    return {"file": "Box-20261009-1432.gcode.3mf", "summary": {"layer_count": 3}, "peak_rss_kb": 2048,
            "orca_wall_s": 1.5}


class Blocking:
    """A worker that reports one stage, then waits until released or stopped."""
    def __init__(self, cancellable=True, result=None):
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancellable = cancellable
        self.result = result or {"file": "x.gcode.3mf"}

    def __call__(self, job_id, payload, context):
        context.progress("slicing_mesh", 0.07)
        self.started.set()
        if self.cancellable:
            context.stop.listen(self.release.set)
        assert self.release.wait(FAILSAFE_S)
        if self.cancellable and context.stop.is_set():
            raise SliceCancelled("stopped")
        return self.result


def make_pool(worker=good_worker, **kwargs):
    logs = []
    kwargs.setdefault("executor", ImmediateExecutor())
    kwargs.setdefault("clock", FakeClock())
    pool = JobPool(worker, log=logs.append, error_report=error_report, **kwargs)
    return pool, logs


def threaded_pool(worker, **kwargs):
    executor = ThreadPoolExecutor(max_workers=1)
    pool, logs = make_pool(worker, executor=executor, **kwargs)
    return pool, logs, executor


def wait_final(pool, job_id):
    report = pool.get(job_id)
    while report["state"] not in FINAL:
        report = pool.wait(job_id, report["sequence"], timeout=FAILSAFE_S)
    return report


class TestReports:
    def test_a_job_reports_queued_running_its_stages_and_done(self):
        seen = []
        pool, _logs = make_pool(executor=HeldExecutor())
        job_id = pool.submit("payload", expected_s=12.5)
        queued = pool.get(job_id)
        assert queued == {"job": job_id, "state": "queued", "stage": "queued", "stage_label": "Waiting for the slicer",
                          "elapsed_s": 0.0, "sequence": 1, "expected_s": 12.5}
        original = pool._progress

        def spy(*args):
            original(*args)
            seen.append(pool.get(job_id))
        pool._progress = spy
        pool._executor.run_next()
        final = pool.get(job_id)
        assert [r["stage"] for r in seen] == ["building_plate", "slicing_mesh", "slicing_mesh", "generating_gcode"]
        assert [r["sequence"] for r in seen] == [3, 4, 4, 5]
        assert seen[1]["fraction"] == 0.07 and seen[1]["stage_label"] == "Slicing the parts into layers"
        assert "fraction" not in seen[0]
        assert final["state"] == "done" and final["sequence"] == 6
        assert "stage" not in final and "fraction" not in final and "error" not in final
        assert final["expected_s"] == 12.5
        assert pool.result(job_id)["summary"] == {"layer_count": 3}

    def test_ids_are_unguessable_and_distinct(self):
        pool, _ = make_pool()
        ids = {pool.submit() for _ in range(20)}
        assert len(ids) == 20 and all(len(i) == 17 and i.startswith("j") for i in ids)

    def test_elapsed_counts_from_the_start_of_running(self):
        clock = FakeClock()
        worker = Blocking()
        pool, _logs, executor = threaded_pool(worker, clock=clock)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        clock.now += 7.25
        assert pool.get(job_id)["elapsed_s"] == 7.25
        worker.release.set()
        executor.shutdown(wait=True)
        assert pool.get(job_id)["elapsed_s"] == 7.25

    def test_unknown_stage_keeps_the_current_one(self):
        def worker(job_id, payload, context):
            context.progress("slicing_mesh", 0.1)
            context.progress(None, 0.2)          # an Orca message the service does not know
            return {}
        pool, _ = make_pool(worker)
        job_id = pool.submit()
        assert pool.get(job_id)["state"] == "done"

    def test_every_orca_stage_is_a_job_stage(self):
        assert set(ORCA_STAGES.values()) <= set(STAGES)

    def test_unknown_job(self):
        pool, _ = make_pool()
        assert pool.get("nope") is None and pool.result("nope") is None
        assert pool.wait("nope", 0, timeout=None) is None
        assert list(pool.follow("nope")) == []

    def test_result_only_for_done_jobs(self):
        pool, _ = make_pool(executor=HeldExecutor())
        job_id = pool.submit()
        assert pool.result(job_id) is None


class TestFailure:
    def test_a_failure_carries_its_error_report(self):
        def worker(job_id, payload, context):
            raise SliceError("Parts are too close together; spread them out.", "detail", -101,
                             error_code="slice.orca_too_close", reason="too close")
        pool, logs = make_pool(worker)
        job_id = pool.submit(describe={"copies": 2})
        report = pool.get(job_id)
        assert report["state"] == "failed"
        assert report["error"]["code"] == "slice.orca_too_close"
        assert report["error"]["detail"] == "orca code -101\ndetail"
        failed = logs[-1]
        assert (failed["state"], failed["error_code"], failed["orca_reason"], failed["copies"]) == \
            ("failed", "slice.orca_too_close", "too close", 2)

    def test_a_bug_in_the_worker_keeps_its_traceback_for_the_log(self):
        def worker(job_id, payload, context):
            raise KeyError("plate")
        pool, _ = make_pool(worker)
        error = pool.get(pool.submit())["error"]
        assert error["code"] == "slice.unexpected"
        assert error["detail"].startswith("KeyError: 'plate'\nTraceback")

    def test_job_failure_keeps_its_words(self):
        def worker(job_id, payload, context):
            raise JobFailure("The worker gave up.", "worker said no")
        pool, _ = make_pool(worker)
        error = pool.get(pool.submit())["error"]
        assert error["detail"] == "JobFailure: The worker gave up.\nworker said no"

    def test_an_error_report_that_fails_falls_back(self):
        def worker(job_id, payload, context):
            raise ValueError("x")

        def broken(exc):
            raise RuntimeError("adapter")
        pool = JobPool(worker, executor=ImmediateExecutor(), error_report=broken)
        error = pool.get(pool.submit())["error"]
        assert error["code"] == "slice.unexpected" and error["detail"].startswith("ValueError: x")

    def test_default_error_report(self):
        def worker(job_id, payload, context):
            raise ValueError("x")
        pool = JobPool(worker, executor=ImmediateExecutor())
        assert pool.get(pool.submit())["error"]["code"] == "slice.unexpected"

    def test_failure_wakes_a_subscriber(self):
        worker = Blocking(cancellable=False)
        original = worker.__call__

        def failing(job_id, payload, context):
            original(job_id, payload, context)
            raise ValueError("boom")
        pool, _logs, executor = threaded_pool(failing)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        report = pool.get(job_id)
        worker.release.set()
        assert wait_final(pool, job_id)["state"] == "failed"
        executor.shutdown(wait=True)
        assert report["state"] == "running"


class TestQueue:
    def test_queue_full(self):
        pool, _ = make_pool(executor=HeldExecutor(), max_queued=2)
        pool.submit()
        pool.submit()
        with pytest.raises(QueueFull):
            pool.submit()
        assert error_report(QueueFull())["code"] == "slice.busy"

    def test_two_jobs_at_once_with_one_slot_run_one_after_the_other(self):
        worker = Blocking(cancellable=False)
        pool, _logs, executor = threaded_pool(worker)
        first, second = pool.submit(), pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        assert (pool.get(first)["state"], pool.get(second)["state"]) == ("running", "queued")
        worker.release.set()
        assert wait_final(pool, first)["state"] == "done"
        assert wait_final(pool, second)["state"] == "done"
        executor.shutdown(wait=True)

    def test_running_jobs_do_not_count_as_queued(self):
        worker = Blocking(cancellable=False)
        pool, _logs, executor = threaded_pool(worker, max_queued=1)
        pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        pool.submit()                       # queued: the one waiting place
        with pytest.raises(QueueFull):
            pool.submit()
        worker.release.set()
        executor.shutdown(wait=True)
        assert pool.counts() == {"queued": 0, "running": 0, "done": 2, "failed": 0, "cancelled": 0}

    def test_default_executor_runs_on_its_own_thread(self):
        names = []

        def worker(job_id, payload, context):
            names.append(threading.current_thread().name)
            return {}
        pool = JobPool(worker)
        job_id = pool.submit()
        wait_final(pool, job_id)
        pool.shutdown()
        assert names[0].startswith("slice")


class TestCancel:
    def test_cancel_a_queued_job(self):
        pool, logs = make_pool(executor=HeldExecutor())
        job_id = pool.submit()
        assert pool.cancel(job_id) == "cancelled"
        assert pool.get(job_id)["state"] == "cancelled"
        pool._executor.run_next()          # the worker never runs
        assert pool.get(job_id)["state"] == "cancelled"
        assert [entry["state"] for entry in logs] == ["queued", "cancelled"]

    def test_cancel_a_running_job_reports_cancelled_only_after_the_worker_returned(self):
        worker = Blocking()
        pool, logs, executor = threaded_pool(worker)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        assert pool.cancel(job_id) == "cancelling"
        final = wait_final(pool, job_id)
        executor.shutdown(wait=True)
        assert final["state"] == "cancelled" and "error" not in final
        assert [e["state"] for e in logs] == ["queued", "running", "cancelling", "cancelled"]
        assert logs[-1]["cancel_reason"] == "cancel"

    def test_cancel_twice(self):
        worker = Blocking(cancellable=False)
        pool, logs, executor = threaded_pool(worker)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        assert pool.cancel(job_id) == "cancelling"
        assert pool.cancel(job_id) == "cancelling"
        assert [e["state"] for e in logs].count("cancelling") == 1
        worker.release.set()
        executor.shutdown(wait=True)

    def test_cancel_at_the_instant_the_job_finishes_wins_and_discards_the_file(self):
        discarded = []
        worker = Blocking(cancellable=False, result={"file": "late.gcode.3mf"})
        pool, _logs, executor = threaded_pool(worker, on_discard=discarded.append)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        pool.cancel(job_id)                 # the worker then returns a result anyway
        worker.release.set()
        assert wait_final(pool, job_id)["state"] == "cancelled"
        executor.shutdown(wait=True)
        assert discarded == [{"file": "late.gcode.3mf"}]
        assert pool.result(job_id) is None

    def test_cancel_a_finished_job_changes_nothing(self):
        pool, _ = make_pool()
        job_id = pool.submit()
        before = pool.get(job_id)
        assert pool.cancel(job_id) == "finished"
        assert pool.get(job_id) == before

    def test_cancel_an_unknown_job(self):
        pool, _ = make_pool()
        assert pool.cancel("nope") == "unknown"


class TestSubscribers:
    def test_late_subscriber_gets_the_latest_report_at_once(self):
        pool, _ = make_pool()
        job_id = pool.submit()
        assert [r["state"] for r in pool.follow(job_id)] == ["done"]

    def test_follow_sees_each_report_in_order_and_ends_on_the_final_one(self):
        worker = Blocking(cancellable=False)
        pool, _logs, executor = threaded_pool(worker)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        stream = pool.follow(job_id, wait_s=FAILSAFE_S)
        first = next(stream)
        assert first["state"] == "running" and first["stage"] == "slicing_mesh"
        worker.release.set()
        rest = list(stream)
        executor.shutdown(wait=True)
        assert [r["state"] for r in rest] == ["done"]
        assert rest[0]["sequence"] > first["sequence"]

    def test_follow_repeats_on_its_cadence_when_nothing_changes(self):
        pool, _ = make_pool(executor=HeldExecutor())
        job_id = pool.submit()
        stream = pool.follow(job_id, wait_s=0)
        assert next(stream)["sequence"] == next(stream)["sequence"] == 1
        stream.close()
        assert pool._jobs[job_id]["subscribers"] == 0

    def test_many_subscribers_each_see_the_end(self):
        worker = Blocking(cancellable=False)
        pool, _logs, executor = threaded_pool(worker)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        ends, ready = [], threading.Barrier(9)

        def follow():
            stream = pool.follow(job_id, wait_s=FAILSAFE_S)
            next(stream)
            ready.wait(FAILSAFE_S)
            ends.append(list(stream)[-1]["state"])
        threads = [threading.Thread(target=follow) for _ in range(8)]
        for thread in threads:
            thread.start()
        ready.wait(FAILSAFE_S)
        assert pool._jobs[job_id]["subscribers"] == 8
        worker.release.set()
        for thread in threads:
            thread.join(FAILSAFE_S)
        executor.shutdown(wait=True)
        assert ends == ["done"] * 8

    def test_wait_returns_at_once_when_the_report_has_moved_on(self):
        pool, _ = make_pool()
        job_id = pool.submit()
        assert pool.wait(job_id, 1, timeout=None)["state"] == "done"


class TestAbandoned:
    def test_a_job_nobody_follows_is_cancelled_after_the_grace_time(self):
        clock = FakeClock()
        worker = Blocking()
        pool, logs, executor = threaded_pool(worker, clock=clock, abandon_grace_s=60)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        clock.now += 59
        assert pool.sweep() == (0, 0)
        clock.now += 1
        assert pool.sweep() == (1, 0)
        assert wait_final(pool, job_id)["state"] == "cancelled"
        executor.shutdown(wait=True)
        assert logs[-1]["cancel_reason"] == "abandoned"

    def test_a_subscriber_that_returns_resets_the_grace_time(self):
        clock = FakeClock()
        pool, _ = make_pool(executor=HeldExecutor(), clock=clock, abandon_grace_s=60)
        job_id = pool.submit()
        pool.subscribe(job_id)
        clock.now += 100
        assert pool.sweep() == (0, 0)             # followed: never abandoned
        pool.unsubscribe(job_id)
        clock.now += 30
        pool.subscribe(job_id)                    # back within the grace time
        pool.unsubscribe(job_id)
        clock.now += 59
        assert pool.sweep() == (0, 0)
        clock.now += 1
        assert pool.sweep() == (1, 0)
        assert pool.get(job_id)["state"] == "cancelled"

    def test_an_abandoned_job_that_finishes_as_it_is_cancelled_ends_cancelled_like_a_callers_cancel(self):
        # Nobody is waiting for its file: it ends cancelled, the file discarded, and its log
        # lines say it was abandoned and which file was thrown away.
        discarded = []

        def worker(job_id, payload, context):
            pool.sweep()                               # the grace time has passed; it finishes anyway
            return {"file": "late.gcode.3mf"}
        clock = FakeClock()
        pool, logs = make_pool(worker, clock=clock, abandon_grace_s=0, on_discard=discarded.append)
        job_id = pool.submit()
        assert pool.get(job_id)["state"] == "cancelled" and pool.result(job_id) is None
        assert discarded == [{"file": "late.gcode.3mf"}]
        assert [(e["state"], e.get("cancel_reason")) for e in logs] == \
            [("queued", None), ("running", None), ("cancelling", "abandoned"), ("cancelled", "abandoned")]
        assert logs[-1]["file_discarded"] == "late.gcode.3mf" and "file" not in logs[-1]

    def test_unsubscribe_of_an_unknown_job_or_below_zero_is_harmless(self):
        pool, _ = make_pool(executor=HeldExecutor())
        pool.unsubscribe("nope")
        job_id = pool.submit()
        pool.unsubscribe(job_id)
        assert pool._jobs[job_id]["subscribers"] == 0
        assert pool.subscribe("nope") is False


class TestExpiry:
    def test_a_final_record_expires_after_its_ttl_and_its_file_is_discarded(self):
        clock = FakeClock()
        discarded = []
        pool, logs = make_pool(clock=clock, ttl_s=3600, on_discard=discarded.append)
        job_id = pool.submit()
        clock.now += 3599
        assert pool.sweep() == (0, 0)
        clock.now += 1
        assert pool.sweep() == (0, 1)
        assert pool.get(job_id) is None
        assert [d["file"] for d in discarded] == ["Box-20261009-1432.gcode.3mf"]
        assert logs[-1]["state"] == "expired"

    def test_a_running_job_never_expires_and_finishes_normally(self):
        clock = FakeClock()
        worker = Blocking(cancellable=False)
        pool, _logs, executor = threaded_pool(worker, clock=clock, ttl_s=10, abandon_grace_s=10 ** 9)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        clock.now += 10 ** 6
        assert pool.sweep() == (0, 0)
        worker.release.set()
        assert wait_final(pool, job_id)["state"] == "done"
        executor.shutdown(wait=True)

    def test_a_job_whose_record_is_gone_when_it_finishes_discards_its_file(self):
        discarded = []
        worker = Blocking(cancellable=False, result={"file": "orphan"})
        pool, _logs, executor = threaded_pool(worker, on_discard=discarded.append)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        with pool._lock:
            del pool._jobs[job_id]
        worker.release.set()
        executor.shutdown(wait=True)
        assert discarded == [{"file": "orphan"}]

    def test_expiry_wakes_a_waiter(self):
        clock = FakeClock()
        pool, _ = make_pool(clock=clock, ttl_s=1)
        job_id = pool.submit()
        clock.now += 1
        pool.sweep()
        assert pool.wait(job_id, 99, timeout=None) is None


class TestSweeperAndShutdown:
    def test_sweeper_runs_until_shutdown(self):
        swept = threading.Event()
        pool, _ = make_pool()
        pool.sweep = lambda: swept.set()
        thread = pool.start_sweeper(interval_s=0)
        assert swept.wait(FAILSAFE_S)
        pool.shutdown()
        thread.join(FAILSAFE_S)
        assert not thread.is_alive()

    def test_sweeper_survives_a_failing_sweep(self):
        calls = []
        pool, logs = make_pool()

        def sweep():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("disk")
            pool._closing.set()
        pool.sweep = sweep
        thread = pool.start_sweeper(interval_s=0)
        thread.join(FAILSAFE_S)
        assert len(calls) == 2 and logs[-1]["event"] == "slice_sweeper_error"

    def test_shutdown_cancels_every_job_and_waits_for_the_workers(self):
        worker = Blocking()
        pool, logs, _executor = threaded_pool(worker)
        running, queued = pool.submit(), pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        pool.shutdown()
        assert (pool.get(running)["state"], pool.get(queued)["state"]) == ("cancelled", "cancelled")
        assert {e["cancel_reason"] for e in logs if e["state"] == "cancelled"} == {"shutdown"}
        with pytest.raises(QueueFull):
            pool.submit()


class TestLog:
    def test_one_line_per_transition_with_what_support_needs(self):
        clock = FakeClock()
        pool, logs = make_pool(clock=clock)
        describe = {"printer": None, "overrides": {"enable_support": "1"}, "parts": {"box": {"triangles": 12}},
                    "copies": [{"name": "Box #1", "x": 50.0}]}
        job_id = pool.submit(describe=describe)
        assert [e["state"] for e in logs] == ["queued", "running", "done"]
        done = logs[-1]
        assert done["event"] == "slice_job" and done["job"] == job_id
        assert done["overrides"] == {"enable_support": "1"} and done["copies"][0]["name"] == "Box #1"
        assert (done["peak_rss_kb"], done["orca_wall_s"], done["wall_s"]) == (2048, 1.5, 0.0)

    def test_the_log_never_carries_the_payload(self):
        pool, logs = make_pool()
        pool.submit({"secret": "s3cr3t-value"})
        assert "s3cr3t-value" not in repr(logs)

    def test_a_stop_note_travels_in_the_done_line(self):
        def worker(job_id, payload, context):
            return {"file": "x.gcode.3mf", "stop_note": "stopped by the slice service (timeout) ..."}
        pool, logs = make_pool(worker)
        pool.submit()
        assert logs[-1]["stop_note"] == "stopped by the slice service (timeout) ..."


class BrokenLog:
    """A log sink that raises (a closed or broken stderr) on the calls it is told to."""

    def __init__(self, failing=lambda n, entry: True):
        self.calls, self.failing = [], failing

    def __call__(self, entry):
        self.calls.append(entry)
        if self.failing(len(self.calls), entry):
            raise BrokenPipeError(32, "Broken pipe")


class TestALogThatFails:
    """A log sink that raises never changes what the pool does; the failures are swallowed
    in one place (jobs.SafeLog) and counted. One that raised on arrival once left a queued
    record nothing would run, so the queue filled for ever."""

    def test_jobs_still_queue_run_and_finish(self):
        log = BrokenLog()
        pool = JobPool(good_worker, executor=ImmediateExecutor(), log=log, max_queued=2, clock=FakeClock())
        ids = [pool.submit() for _ in range(5)]
        assert [pool.get(job_id)["state"] for job_id in ids] == ["done"] * 5
        assert pool.counts()["queued"] == 0
        assert pool.log_failures() == len(log.calls) == 15          # queued, running, done, five times

    def test_a_failed_job_is_still_cleaned_up(self):
        cleaned = []

        def worker(job_id, payload, context):
            raise ValueError("x")
        pool = JobPool(worker, executor=ImmediateExecutor(), log=BrokenLog(), cleanup=cleaned.append)
        job_id = pool.submit("files")
        assert pool.get(job_id)["state"] == "failed" and cleaned == ["files"]

    def test_a_cancel_and_a_sweep_still_work(self):
        clock = FakeClock()
        pool = JobPool(good_worker, executor=HeldExecutor(), log=BrokenLog(), clock=clock, ttl_s=1,
                       abandon_grace_s=1)
        queued, abandoned = pool.submit(), pool.submit()
        assert pool.cancel(queued) == "cancelled"
        clock.now += 1
        assert pool.sweep() == (1, 1)
        assert pool.get(abandoned)["state"] == "cancelled" and pool.get(queued) is None

    def test_the_sweeper_survives_a_log_that_fails_while_it_reports_a_failing_sweep(self):
        calls = []
        pool = JobPool(good_worker, executor=ImmediateExecutor(), log=BrokenLog())

        def sweep():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("disk")
            pool._closing.set()
        pool.sweep = sweep
        pool.start_sweeper(interval_s=0).join(FAILSAFE_S)
        assert len(calls) == 2 and pool.log_failures() == 1

    def test_a_healthy_log_counts_nothing(self):
        pool, logs = make_pool()
        pool.submit()
        assert pool.log_failures() == 0 and len(logs) == 3

    def test_a_safe_log_is_not_wrapped_twice(self):
        log = jobs.SafeLog(BrokenLog())
        pool = JobPool(good_worker, executor=ImmediateExecutor(), log=log)
        pool.submit()
        assert pool.log_failures() == log.failures == 3


class TestEdges:
    def test_follow_ends_when_the_record_goes_while_it_waits(self):
        pool, _ = make_pool(executor=HeldExecutor())
        job_id = pool.submit()
        stream = pool.follow(job_id, wait_s=0)
        next(stream)
        with pool._lock:
            del pool._jobs[job_id]
        assert list(stream) == []

    def test_a_failed_job_that_expires_is_cleaned_up_without_a_result(self):
        clock = FakeClock()
        cleaned, discarded = [], []

        def worker(job_id, payload, context):
            raise ValueError("x")
        pool, _ = make_pool(worker, clock=clock, ttl_s=1, cleanup=cleaned.append, on_discard=discarded.append)
        pool.submit("files")
        assert cleaned == ["files"]           # at once, on failure
        clock.now += 1
        pool.sweep()
        assert cleaned == ["files", "files"] and discarded == []

    def test_progress_after_the_end_changes_nothing(self):
        pool, _ = make_pool()
        job_id = pool.submit()
        before = pool.get(job_id)
        pool._progress(job_id, "slicing_mesh", 0.5)
        pool._progress("nope", "slicing_mesh", 0.5)
        assert pool.get(job_id) == before

    def test_a_cleanup_that_fails_is_logged_not_raised(self):
        def worker(job_id, payload, context):
            raise ValueError("x")

        def cleanup(payload):
            raise OSError("busy")
        pool, logs = make_pool(worker, cleanup=cleanup)
        pool.submit()
        assert logs[-1]["event"] == "slice_cleanup_error" and "OSError: busy" in logs[-1]["traceback"]


def test_constants_are_the_documented_defaults():
    assert (jobs.MAX_RUNNING, jobs.MAX_QUEUED, jobs.RECORD_TTL_S, jobs.ABANDON_GRACE_S) == (1, 2, 3600, 120)
