"""jobs.JobPool: progress reports with the count ahead, cancellation and its reason, the
replacement of a plate's earlier slice job, a repeated submission, a slice job that goes on
without a follower, expiry, shutdown and the log.

Synchronous stand-ins for the executor and an injected clock. No test sleeps or waits on a
timeout that is expected to run out: a worker that must stay running blocks on an Event
the test sets, every wait that must return early has no timeout or a fail-safe that is
reached only when the test is failing.
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from helpers import CONTRACTS, ManualTicks
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
                          "elapsed_s": 0.0, "sequence": 1, "expected_s": 12.5, "ahead": 0}
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
            context.progress("slicing_mesh", 0.07)    # a failed report keeps no stage it reached
            raise SliceError("Two instances are too close together.", "detail", -101,
                             error_code="slice.orca_too_close", reason="too close")
        pool, logs = make_pool(worker)
        job_id = pool.submit(describe={"instances": 2})
        report = pool.get(job_id)
        assert report["state"] == "failed"
        assert "stage" not in report and "stage_label" not in report and "fraction" not in report
        assert report["error"]["code"] == "slice.orca_too_close"
        assert report["error"]["detail"] == "orca code -101\ndetail"
        failed = logs[-1]
        assert (failed["state"], failed["error_code"], failed["orca_reason"], failed["instances"]) == \
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

    def test_failure_wakes_a_follower(self):
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
        # The places are the running ones and the waiting ones together: one and two.
        pool, _ = make_pool(executor=HeldExecutor(), max_queued=2)
        pool.submit()
        pool.submit()
        pool.submit()
        with pytest.raises(QueueFull):
            pool.submit()
        assert error_report(QueueFull())["code"] == "slice.busy"

    def test_a_job_being_stopped_holds_no_place(self):
        worker = Blocking(cancellable=False)
        pool, _logs, executor = threaded_pool(worker, max_queued=0)
        stopping = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        with pytest.raises(QueueFull):
            pool.submit()
        pool.cancel(stopping)
        waiting = pool.submit()
        assert pool.get(waiting)["ahead"] == 1          # the one being stopped still holds Orca
        worker.release.set()
        assert wait_final(pool, waiting)["state"] == "done"
        executor.shutdown(wait=True)

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
        assert logs[-1]["cancel_reason"] == "requested"

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


class TestFollowers:
    def test_late_follower_gets_the_latest_report_at_once(self):
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

    def test_many_followers_each_see_the_end(self):
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
        worker.release.set()
        for thread in threads:
            thread.join(FAILSAFE_S)
        executor.shutdown(wait=True)
        assert ends == ["done"] * 8

    def test_wait_returns_at_once_when_the_report_has_moved_on(self):
        pool, _ = make_pool()
        job_id = pool.submit()
        assert pool.wait(job_id, 1, timeout=None)["state"] == "done"


class TestGoesOnWithoutItsPage:
    """Item 9: once accepted, a slice job runs to its end whether or not anything follows it."""

    def test_a_job_nobody_follows_past_120_s_ends_done(self):
        clock = FakeClock()
        worker = Blocking()
        pool, logs, executor = threaded_pool(worker, clock=clock)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        clock.now += 121                          # past the old grace time, with no follower ever
        assert pool.sweep() == 0
        assert pool.get(job_id)["state"] == "running"
        worker.release.set()
        assert wait_final(pool, job_id)["state"] == "done"
        executor.shutdown(wait=True)
        assert [e["state"] for e in logs] == ["queued", "running", "done"]

    def test_a_queued_job_nobody_follows_is_not_ended(self):
        clock = FakeClock()
        pool, _ = make_pool(executor=HeldExecutor(), clock=clock)
        job_id = pool.submit()
        clock.now += 10 ** 6
        assert pool.sweep() == 0
        pool._executor.run_next()
        assert pool.get(job_id)["state"] == "done"

    def test_a_follower_that_leaves_changes_nothing(self):
        worker = Blocking(cancellable=False)
        clock = FakeClock()
        pool, _logs, executor = threaded_pool(worker, clock=clock)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        stream = pool.follow(job_id, wait_s=FAILSAFE_S)
        next(stream)
        stream.close()                            # the page went away
        clock.now += 10 ** 6
        pool.sweep()
        worker.release.set()
        assert wait_final(pool, job_id)["state"] == "done"
        executor.shutdown(wait=True)

    def test_there_is_no_grace_time_any_more(self):
        assert not hasattr(jobs, "ABANDON_GRACE_S")


class Gates:
    """A worker whose every slice job waits for its own gate: `started[n]` is set when the
    n-th job to run has started, `release(n)` lets it finish (or, once stopped, end)."""

    def __init__(self, count=4, stoppable=True):
        self.started = [threading.Event() for _ in range(count)]
        self.gates = [threading.Event() for _ in range(count)]
        self.order = []
        self.stoppable = stoppable      # False: a stop is seen only once the gate opens (an Orca still dying)
        self._lock = threading.Lock()

    def release(self, n):
        self.gates[n].set()

    def __call__(self, job_id, payload, context):
        with self._lock:
            n = len(self.order)
            self.order.append(job_id)
        if self.stoppable:
            context.stop.listen(self.gates[n].set)
        self.started[n].set()
        assert self.gates[n].wait(FAILSAFE_S)
        if context.stop.is_set():
            raise SliceCancelled("stopped")
        return {"file": f"{job_id}.gcode.3mf"}


def wait_for(pool, job_id, predicate):
    """The job's first report for which predicate(report) holds, waiting on its reports."""
    report = pool.get(job_id)
    while not predicate(report):
        assert report["state"] not in FINAL, report
        report = pool.wait(job_id, report["sequence"], timeout=FAILSAFE_S)
    return report


class TestAhead:
    """Item 8: every queued report says how many slice jobs are ahead, over every user key."""

    def test_the_first_report_of_a_job_says_none_are_ahead(self):
        pool, _ = make_pool(executor=HeldExecutor())
        job_id = pool.submit("p", user_key="a", plate_id="p1", submission_id="s1")
        assert pool.get(job_id)["ahead"] == 0

    def test_with_one_running_and_two_queued_they_report_1_and_2_and_then_1(self):
        gates = Gates()
        pool, _logs, executor = threaded_pool(gates)
        first = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert gates.started[0].wait(FAILSAFE_S)
        second = pool.submit(user_key="b", plate_id="p1", submission_id="s1")
        third = pool.submit(user_key="c", plate_id="p9", submission_id="s9")
        assert (pool.get(second)["ahead"], pool.get(third)["ahead"]) == (1, 2)
        assert "ahead" not in pool.get(first)
        before = pool.get(third)
        gates.release(0)
        after = wait_for(pool, third, lambda r: r["ahead"] == 1)
        assert after["sequence"] == before["sequence"] + 1 and after["state"] == "queued"
        assert gates.started[1].wait(FAILSAFE_S)
        assert wait_for(pool, second, lambda r: r["state"] == "running")
        assert pool.get(third)["ahead"] == 1          # the second running: still one ahead
        assert "ahead" not in pool.get(second)
        gates.release(1)
        assert gates.started[2].wait(FAILSAFE_S)
        gates.release(2)
        assert wait_final(pool, third)["state"] == "done"
        executor.shutdown(wait=True)
        assert all("ahead" not in pool.get(j) for j in (first, second, third))

    def test_a_queued_job_that_ends_moves_those_behind_it_up(self):
        pool, _ = make_pool(executor=HeldExecutor())
        ids = [pool.submit(user_key="a", plate_id=f"p{n}", submission_id=f"s{n}") for n in range(3)]
        assert [pool.get(j)["ahead"] for j in ids] == [0, 1, 2]
        sequence = pool.get(ids[2])["sequence"]
        assert pool.cancel(ids[0]) == "cancelled"
        assert [pool.get(j)["ahead"] for j in ids[1:]] == [0, 1]
        assert pool.get(ids[2])["sequence"] == sequence + 1
        assert "ahead" not in pool.get(ids[0])

    def test_a_job_being_stopped_still_counts_ahead_when_the_counts_are_refreshed(self):
        # User a's earlier is running; user b's waits; a replaces earlier with later (earlier
        # is being stopped, its Orca still running); then b replaces its own waiting one.
        # later's count is refreshed then, and earlier must still count: its Orca has not
        # returned.
        gates = Gates(stoppable=False)
        pool, _logs, executor = threaded_pool(gates)
        earlier = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert gates.started[0].wait(FAILSAFE_S)
        waiting = pool.submit(user_key="b", plate_id="p2", submission_id="s2")
        later = pool.submit(user_key="a", plate_id="p1", submission_id="s3")
        assert (pool.get(waiting)["ahead"], pool.get(later)["ahead"]) == (1, 2)
        before = pool.get(later)
        newer = pool.submit(user_key="b", plate_id="p2", submission_id="s4")
        assert pool.get(waiting)["cancel_reason"] == "replaced"
        assert pool.get(earlier)["state"] == "running"
        refreshed = pool.get(later)
        assert (refreshed["ahead"], refreshed["sequence"]) == (1, before["sequence"] + 1)
        assert pool.get(newer)["ahead"] == 2
        gates.release(0)
        for n in (1, 2):
            assert gates.started[n].wait(FAILSAFE_S)
            gates.release(n)
        assert [wait_final(pool, j)["state"] for j in (later, newer)] == ["done", "done"]
        executor.shutdown(wait=True)

    def test_jobs_run_in_the_order_accepted_whatever_order_the_executor_takes_them(self):
        # Two submits may reach the executor in the other order than they were accepted
        # (the executor is called outside the lock): the pool still runs the oldest waiting
        # job first, so the counts ahead stay true.
        ran = []
        pool, _ = make_pool(lambda job_id, payload, context: ran.append(job_id) or {"file": "f"},
                            executor=HeldExecutor())
        ids = [pool.submit(user_key="a", plate_id=f"p{n}", submission_id=f"s{n}") for n in range(3)]
        pool._executor.pending.reverse()
        pool._executor.run_next()
        assert ran == ids[:1]
        assert [pool.get(j)["ahead"] for j in ids[1:]] == [0, 1]
        pool._executor.run_next()
        pool._executor.run_next()
        assert ran == ids

    def test_no_new_report_when_the_count_does_not_change(self):
        pool, _ = make_pool(executor=HeldExecutor())
        first = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        sequence = pool.get(first)["sequence"]
        pool.submit(user_key="a", plate_id="p2", submission_id="s2")      # behind it: nothing changes for it
        assert pool.get(first)["sequence"] == sequence


class TestCancelReason:
    """Item 8: every cancelled report carries why the slice job ended early."""

    def test_a_requested_cancel_of_a_queued_job(self):
        pool, logs = make_pool(executor=HeldExecutor())
        job_id = pool.submit()
        pool.cancel(job_id)
        assert pool.get(job_id)["cancel_reason"] == "requested"
        assert (logs[-1]["state"], logs[-1]["cancel_reason"]) == ("cancelled", "requested")

    def test_a_requested_cancel_of_a_running_job(self):
        worker = Blocking()
        pool, logs, executor = threaded_pool(worker)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        pool.cancel(job_id)
        final = wait_final(pool, job_id)
        executor.shutdown(wait=True)
        assert (final["state"], final["cancel_reason"]) == ("cancelled", "requested")
        assert [(e["state"], e.get("cancel_reason")) for e in logs][-2:] == \
            [("cancelling", "requested"), ("cancelled", "requested")]

    def test_a_shutdown(self):
        worker = Blocking()
        pool, logs, _executor = threaded_pool(worker)
        running, queued = pool.submit(), pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        pool.shutdown()
        assert [pool.get(j)["cancel_reason"] for j in (running, queued)] == ["shutdown", "shutdown"]
        assert {e["cancel_reason"] for e in logs if e["state"] == "cancelled"} == {"shutdown"}

    def test_a_replacement(self):
        pool, logs = make_pool(executor=HeldExecutor())
        earlier = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        pool.submit(user_key="a", plate_id="p1", submission_id="s2")
        assert pool.get(earlier)["cancel_reason"] == "replaced"
        cancelled = [e for e in logs if e["state"] == "cancelled"]
        assert [(e["job"], e["cancel_reason"]) for e in cancelled] == [(earlier, "replaced")]

    def test_a_job_that_ends_cancelled_by_itself_still_says_why(self):
        # A worker that raises SliceCancelled with no stop asked of it: the pool never asked,
        # so the reason is the one left, requested.
        def worker(job_id, payload, context):
            raise SliceCancelled("stopped")
        pool, _ = make_pool(worker)
        assert pool.get(pool.submit())["cancel_reason"] == "requested"

    def test_a_replaced_report_has_the_fields_of_its_contract_example(self):
        example = json.loads((CONTRACTS / "examples" / "progress-report-replaced.json").read_text())

        def worker(job_id, payload, context):
            context.progress("generating_supports", 0.4)
            assert gate.wait(FAILSAFE_S)
            raise SliceCancelled("stopped")
        gate = threading.Event()
        pool, _logs, executor = threaded_pool(worker)
        earlier = pool.submit(expected_s=75, user_key="a", plate_id="p1", submission_id="s1")
        wait_for(pool, earlier, lambda r: r.get("stage") == "generating_supports")
        pool.submit(expected_s=75, user_key="a", plate_id="p1", submission_id="s2")
        gate.set()
        final = wait_final(pool, earlier)
        executor.shutdown(wait=True)
        assert set(final) == set(example)
        assert (final["stage"], final["stage_label"]) == (example["stage"], example["stage_label"])
        assert final["cancel_reason"] == example["cancel_reason"]

    def test_a_waiting_report_has_the_fields_of_its_contract_example(self):
        example = json.loads((CONTRACTS / "examples" / "progress-report-waiting.json").read_text())
        pool, _ = make_pool(executor=HeldExecutor())
        pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        pool.submit(user_key="b", plate_id="p1", submission_id="s1")
        report = pool.get(pool.submit(user_key="c", plate_id="p1", submission_id="s1"))
        assert set(report) == set(example)
        assert (report["stage"], report["stage_label"], report["ahead"]) == \
            (example["stage"], example["stage_label"], example["ahead"])

    def test_no_other_report_carries_a_reason(self):
        pool, _ = make_pool()
        failing, _ = make_pool(lambda *a: (_ for _ in ()).throw(ValueError("x")))
        assert "cancel_reason" not in pool.get(pool.submit())
        assert "cancel_reason" not in failing.get(failing.submit())


class TestReplacement:
    """Item 7: a plate's later slice job ends its earlier one, of the same user key only."""

    def test_a_queued_one_is_ended_at_once(self):
        cleaned = []
        pool, _ = make_pool(executor=HeldExecutor(), cleanup=cleaned.append)
        earlier = pool.submit("earlier", user_key="a", plate_id="p1", submission_id="s1")
        later = pool.submit("later", user_key="a", plate_id="p1", submission_id="s2")
        assert pool.get(earlier)["state"] == "cancelled" and cleaned == ["earlier"]
        assert pool.get(later)["state"] == "queued" and pool.get(later)["ahead"] == 0
        pool._executor.run_next()                     # the earlier's task: it runs the later one
        pool._executor.run_next()                     # the later's task: nothing is left to run
        assert pool.get(later)["state"] == "done"

    def test_a_running_one_is_reported_replaced_only_once_its_work_has_stopped(self):
        gates = Gates(stoppable=False)
        pool, logs, executor = threaded_pool(gates)
        earlier = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert gates.started[0].wait(FAILSAFE_S)
        later = pool.submit(user_key="a", plate_id="p1", submission_id="s2")
        # Its stop is set, but its work has not returned: it is not yet reported ended.
        assert pool.get(earlier)["state"] == "running"
        assert [(e["job"], e["state"], e.get("cancel_reason")) for e in logs][-2:] == \
            [(earlier, "cancelling", "replaced"), (later, "queued", None)]
        assert pool.get(later)["ahead"] == 1            # the earlier still holds the one Orca
        gates.release(0)
        final = wait_final(pool, earlier)
        assert (final["state"], final["cancel_reason"]) == ("cancelled", "replaced")
        assert gates.started[1].wait(FAILSAFE_S)
        gates.release(1)
        assert wait_final(pool, later)["state"] == "done"
        executor.shutdown(wait=True)

    def test_a_running_one_that_finishes_as_it_is_replaced_discards_its_file(self):
        discarded = []
        worker = Blocking(cancellable=False, result={"file": "late.gcode.3mf"})
        pool, _logs, executor = threaded_pool(worker, on_discard=discarded.append)
        earlier = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert worker.started.wait(FAILSAFE_S)
        later = pool.submit(user_key="a", plate_id="p1", submission_id="s2")
        worker.release.set()                           # it returns its file all the same
        assert wait_final(pool, earlier)["cancel_reason"] == "replaced"
        assert wait_final(pool, later)["state"] == "done"
        executor.shutdown(wait=True)
        assert discarded == [{"file": "late.gcode.3mf"}] and pool.result(earlier) is None

    def test_another_plate_and_another_user_key_are_untouched(self):
        pool, _ = make_pool(executor=HeldExecutor(), max_queued=5)
        mine = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        other_plate = pool.submit(user_key="a", plate_id="p2", submission_id="s2")
        other_user = pool.submit(user_key="b", plate_id="p1", submission_id="s3")
        pool.submit(user_key="a", plate_id="p1", submission_id="s4")
        assert [pool.get(j)["state"] for j in (mine, other_plate, other_user)] == ["cancelled", "queued", "queued"]

    def test_a_finished_one_is_not_touched(self):
        pool, logs = make_pool()
        earlier = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        before = pool.get(earlier)
        lines_before = [e for e in logs if e["job"] == earlier]
        pool.submit(user_key="a", plate_id="p1", submission_id="s2")
        assert pool.get(earlier) == before and before["state"] == "done"
        # The replacement writes no line for it, and its later lines name no cancel reason.
        assert [e for e in logs if e["job"] == earlier] == lines_before
        pool.sweep(now=pool._clock() + 10 ** 9)
        earlier_lines = [e for e in logs if e["job"] == earlier]
        assert [e["state"] for e in earlier_lines] == ["queued", "running", "done", "expired"]
        assert all("cancel_reason" not in e for e in earlier_lines)

    def test_with_every_place_taken_by_one_user_key_a_changed_plate_is_accepted_and_another_refused(self):
        gates = Gates(stoppable=False)
        pool, _logs, executor = threaded_pool(gates)
        running = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert gates.started[0].wait(FAILSAFE_S)
        waiting = [pool.submit(user_key="a", plate_id=f"p{n}", submission_id=f"s{n}") for n in (2, 3)]
        with pytest.raises(QueueFull):
            pool.submit(user_key="a", plate_id="p4", submission_id="s4")
        with pytest.raises(QueueFull):
            pool.submit(user_key="b", plate_id="p1", submission_id="s5")
        changed_waiting = pool.submit(user_key="a", plate_id="p3", submission_id="s6")
        assert pool.get(waiting[1])["cancel_reason"] == "replaced"
        changed_running = pool.submit(user_key="a", plate_id="p1", submission_id="s7")
        with pytest.raises(QueueFull):
            pool.submit(user_key="a", plate_id="p4", submission_id="s8")
        gates.release(0)
        assert wait_final(pool, running)["cancel_reason"] == "replaced"
        for n in (1, 2, 3):
            assert gates.started[n].wait(FAILSAFE_S)
            gates.release(n)
        for job_id in (waiting[0], changed_waiting, changed_running):
            assert wait_final(pool, job_id)["state"] == "done"
        executor.shutdown(wait=True)
        assert gates.order == [running, waiting[0], changed_waiting, changed_running]

    def test_a_later_one_refused_as_busy_leaves_the_earlier_as_it_was(self):
        # The earlier one is already being stopped (a requested cancel), so it holds no place
        # to give up: the later one finds every place taken and replaces nothing.
        gates = Gates(stoppable=False)
        pool, logs, executor = threaded_pool(gates, max_queued=1)
        earlier = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert gates.started[0].wait(FAILSAFE_S)
        assert pool.cancel(earlier) == "cancelling"
        others = [pool.submit(user_key="b", plate_id=f"p{n}", submission_id=f"s{n}") for n in (8, 9)]
        with pytest.raises(QueueFull):
            pool.submit(user_key="a", plate_id="p1", submission_id="s2")
        assert pool.remembered("a", "s2") is None
        gates.release(0)
        assert wait_final(pool, earlier)["cancel_reason"] == "requested"
        assert [e["state"] for e in logs if e["job"] == earlier].count("cancelling") == 1
        for n in (1, 2):
            assert gates.started[n].wait(FAILSAFE_S)
            gates.release(n)
        assert [wait_final(pool, j)["state"] for j in others] == ["done", "done"]
        executor.shutdown(wait=True)

    def test_while_closing_nothing_is_replaced(self):
        pool, _ = make_pool(executor=HeldExecutor())
        earlier = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        pool._closing.set()
        with pytest.raises(jobs.Stopping):
            pool.submit(user_key="a", plate_id="p1", submission_id="s2")
        assert pool.get(earlier)["state"] == "queued"

    def test_while_stopping_nothing_is_replaced_but_the_waiting_one_has_ended(self):
        pool, _ = make_pool(executor=HeldExecutor())
        earlier = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        pool._executor.run_next()            # done before the stop
        pool.stop()
        with pytest.raises(jobs.Stopping):
            pool.submit(user_key="a", plate_id="p1", submission_id="s2")
        assert pool.get(earlier)["state"] == "done"

    def test_jobs_without_a_plate_or_a_user_key_replace_nothing(self):
        pool, _ = make_pool(executor=HeldExecutor())
        first, second = pool.submit(), pool.submit()
        assert [pool.get(j)["state"] for j in (first, second)] == ["queued", "queued"]


class TestRepeat:
    """Item 7: a submission the pool remembers, under the same user key, starts nothing."""

    def test_a_repeat_is_the_first_attempts_job(self):
        pool, logs = make_pool(executor=HeldExecutor())
        first = pool.submit("p", user_key="a", plate_id="p1", submission_id="s1")
        assert pool.remembered("a", "s1") == first
        with pytest.raises(jobs.RepeatedSubmission) as caught:
            pool.submit("p", user_key="a", plate_id="p1", submission_id="s1")
        assert caught.value.job_id == first
        assert pool.get(first)["state"] == "queued" and pool.get(first)["sequence"] == 1
        assert [e["state"] for e in logs] == ["queued"]
        assert pool.counts()["queued"] == 1

    def test_one_value_under_two_user_keys_is_two_submissions(self):
        pool, _ = make_pool(executor=HeldExecutor())
        first = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert pool.remembered("b", "s1") is None
        second = pool.submit(user_key="b", plate_id="p1", submission_id="s1")
        assert second != first and pool.get(first)["state"] == "queued"

    def test_a_repeat_is_answered_even_when_every_place_is_taken_or_the_pool_closes(self):
        pool, _ = make_pool(executor=HeldExecutor(), max_queued=0)
        first = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        with pytest.raises(jobs.RepeatedSubmission):
            pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        pool._closing.set()
        with pytest.raises(jobs.RepeatedSubmission):
            pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert pool.get(first)["state"] == "queued"

    def test_a_repeat_of_an_ended_job_is_that_job(self):
        pool, _ = make_pool()
        first = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert pool.remembered("a", "s1") == first and pool.get(first)["state"] == "done"

    def test_an_expired_job_is_no_longer_remembered(self):
        clock = FakeClock()
        pool, _ = make_pool(clock=clock, ttl_s=10)
        pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        clock.now += 10
        pool.sweep()
        assert pool.remembered("a", "s1") is None

    def test_nothing_is_remembered_without_a_user_key_or_a_value(self):
        pool, _ = make_pool(executor=HeldExecutor())
        pool.submit()
        assert pool.remembered(None, None) is None
        assert pool.remembered("a", None) is None

    def test_a_refused_submission_is_not_remembered(self):
        pool, _ = make_pool(executor=HeldExecutor(), max_running=1, max_queued=0)
        pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        with pytest.raises(QueueFull):
            pool.submit(user_key="a", plate_id="p2", submission_id="s2")
        assert pool.remembered("a", "s2") is None

    def test_the_payload_of_a_job(self):
        pool, _ = make_pool(executor=HeldExecutor())
        job_id = pool.submit("the payload")
        assert pool.payload(job_id) == "the payload" and pool.payload("nope") is None


class TestExpiry:
    def test_a_final_record_expires_after_its_ttl_and_its_file_is_discarded(self):
        clock = FakeClock()
        discarded = []
        pool, logs = make_pool(clock=clock, ttl_s=3600, on_discard=discarded.append)
        job_id = pool.submit()
        clock.now += 3599
        assert pool.sweep() == 0
        clock.now += 1
        assert pool.sweep() == 1
        assert pool.get(job_id) is None
        assert [d["file"] for d in discarded] == ["Box-20261009-1432.gcode.3mf"]
        assert logs[-1]["state"] == "expired"

    def test_a_running_job_never_expires_and_finishes_normally(self):
        clock = FakeClock()
        worker = Blocking(cancellable=False)
        pool, _logs, executor = threaded_pool(worker, clock=clock, ttl_s=10)
        job_id = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        clock.now += 10 ** 6
        assert pool.sweep() == 0
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


class TestRememberedForTwoHours:
    """Item 10: a slice job's record is kept for two hours after it ends, and its sliced file
    is given up as soon as the front server says it has stored it."""

    def test_a_record_is_there_at_7199_s_and_gone_at_7200_s(self):
        clock = FakeClock()
        pool, logs = make_pool(clock=clock)
        job_id = pool.submit()
        clock.now += 7199
        assert pool.sweep() == 0 and pool.get(job_id)["state"] == "done"
        assert pool.remembered(None, None) is None
        clock.now += 1
        assert pool.sweep() == 1 and pool.get(job_id) is None
        assert logs[-1]["state"] == "expired"

    def test_a_repeat_is_recognised_for_the_two_hours(self):
        clock = FakeClock()
        pool, _ = make_pool(clock=clock)
        job_id = pool.submit(user_key="u", submission_id="s")
        clock.now += 7199
        pool.sweep()
        assert pool.remembered("u", "s") == job_id
        clock.now += 1
        pool.sweep()
        assert pool.remembered("u", "s") is None

    def test_deleting_a_done_jobs_file_hands_over_its_result_once(self):
        pool, logs = make_pool()
        job_id = pool.submit()
        assert pool.file_deleted(job_id) is False
        answer, result = pool.delete_file(job_id)
        assert answer == "deleted" and result["file"] == "Box-20261009-1432.gcode.3mf"
        assert pool.file_deleted(job_id) is True
        assert logs[-1]["state"] == "file_deleted" and logs[-1]["job"] == job_id
        assert pool.delete_file(job_id) == ("deleted", None)            # a repeat answers as the first
        assert len([e for e in logs if e["state"] == "file_deleted"]) == 1
        assert pool.get(job_id)["state"] == "done"                      # the record stays

    def test_a_deleted_file_is_not_discarded_again_when_the_record_expires(self):
        clock, discarded, cleaned = FakeClock(), [], []
        pool, _ = make_pool(clock=clock, on_discard=discarded.append, cleanup=cleaned.append)
        job_id = pool.submit("files")
        pool.delete_file(job_id)
        clock.now += jobs.RECORD_TTL_S
        assert pool.sweep() == 1
        assert discarded == [] and cleaned == ["files"]

    def test_a_job_that_ended_without_a_file_answers_deleted(self):
        def worker(job_id, payload, context):
            raise ValueError("x")
        pool, _ = make_pool(worker)
        failed = pool.submit()
        held, _ = make_pool(executor=HeldExecutor())
        cancelled = held.submit()
        held.cancel(cancelled)
        assert pool.delete_file(failed) == ("deleted", None)
        assert held.delete_file(cancelled) == ("deleted", None)

    def test_a_job_not_ended_is_not_ready_and_an_unknown_one_is_unknown(self):
        worker = Blocking(cancellable=False)
        pool, _logs, executor = threaded_pool(worker)
        running, queued = pool.submit(), pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        assert pool.delete_file(running) == ("not_ready", None)
        assert pool.delete_file(queued) == ("not_ready", None)
        assert pool.delete_file("jnope") == ("unknown", None)
        assert pool.file_deleted("jnope") is False
        worker.release.set()
        executor.shutdown(wait=True)


END = 1795817638.0            # 2026-11-27T22:13:58Z, on the wall clock


class TestTheList:
    """Item 11: every slice job the pool knows, in the order accepted, with when it ended."""

    def test_the_list_holds_every_state_with_when_each_ended(self):
        clock, wall = FakeClock(), FakeClock(END)
        release = threading.Event()

        def worker(job_id, payload, context):
            if payload == "fail":
                raise ValueError("x")
            if payload == "block":
                context.progress("slicing_mesh", 0.5)
                assert release.wait(FAILSAFE_S)
            return {"file": f"{payload}.gcode.3mf"}
        executor = HeldExecutor()
        pool, _ = make_pool(worker, executor=executor, clock=clock, wall_clock=wall)
        done = pool.submit("ok", user_key="u", plate_id="p1", submission_id="s1")
        executor.run_next()
        wall.now += 1
        failed = pool.submit("fail", user_key="u", plate_id="p2", submission_id="s2")
        executor.run_next()
        wall.now += 1
        cancelled = pool.submit("x", user_key="v", plate_id="p3", submission_id="s3")
        pool.cancel(cancelled)
        executor.pending.pop(0)
        wall.now += 1
        running = pool.submit("block", user_key="v", plate_id="p4", submission_id="s4")
        queued = pool.submit("ok", user_key="v", plate_id="p5", submission_id="s5")
        thread = threading.Thread(target=executor.run_next)
        thread.start()
        while pool.get(running)["state"] != "running":
            pool.wait(running, pool.get(running)["sequence"], timeout=FAILSAFE_S)
        listed = pool.listing()
        assert [e["job"] for e in listed] == [done, failed, cancelled, running, queued]
        assert [e["progress"]["state"] for e in listed] == ["done", "failed", "cancelled", "running", "queued"]
        assert [e["ended_at"] for e in listed] == ["2026-11-27T22:13:58Z", "2026-11-27T22:13:59Z",
                                                   "2026-11-27T22:14:00Z", None, None]
        assert [e["file_on_disk"] for e in listed] == [True, False, False, False, False]
        assert [(e["user_key"], e["plate_id"], e["submission_id"]) for e in listed][0] == ("u", "p1", "s1")
        assert listed[3]["progress"] == pool.get(running)
        assert set(listed[0]) == {"job", "user_key", "plate_id", "submission_id", "progress", "file_on_disk",
                                  "ended_at"}
        release.set()
        thread.join(FAILSAFE_S)

    def test_a_new_pool_lists_nothing(self):
        pool, _ = make_pool()
        assert pool.listing() == []

    def test_a_done_job_whose_file_was_deleted_is_not_on_disk(self):
        pool, _ = make_pool()
        job_id = pool.submit()
        assert pool.listing()[0]["file_on_disk"] is True
        pool.delete_file(job_id)
        assert pool.listing()[0]["file_on_disk"] is False

    def test_an_expired_job_leaves_the_list(self):
        clock = FakeClock()
        pool, _ = make_pool(clock=clock)
        pool.submit()
        clock.now += jobs.RECORD_TTL_S
        pool.sweep()
        assert pool.listing() == []

    def test_the_wall_clock_is_the_systems_by_default(self, monkeypatch):
        monkeypatch.setattr(jobs.time, "time", lambda: END)
        pool = JobPool(good_worker, executor=ImmediateExecutor())
        pool.submit()
        assert pool.listing()[0]["ended_at"] == "2026-11-27T22:13:58Z"


class TestSweeperAndShutdown:
    """The sweeper on its own thread, its intervals passed by the test (ManualTicks): it
    waits on events, never on a duration."""

    def test_the_sweeper_expires_records_on_the_fake_clock_once_per_interval_until_shutdown(self):
        clock, ticks = FakeClock(), ManualTicks()
        pool, logs = make_pool(clock=clock)
        job_id = pool.submit()
        expired = threading.Event()
        pool._log = lambda entry: entry.get("state") == "expired" and expired.set()
        thread = pool.start_sweeper(wait=ticks)
        clock.now += jobs.RECORD_TTL_S
        ticks.tick()
        assert expired.wait(FAILSAFE_S)
        assert pool.get(job_id) is None
        assert ticks.intervals[0] == jobs.SWEEP_INTERVAL_S == 10
        pool.shutdown()
        ticks.tick()                     # an interval passes after the shutdown: the sweeper ends
        thread.join(FAILSAFE_S)
        assert not thread.is_alive()

    def test_without_a_test_clock_the_sweeper_waits_on_the_pools_closing(self):
        pool, _ = make_pool()
        pool.sweep = lambda: pytest.fail("swept after the shutdown")
        pool.shutdown()
        thread = pool.start_sweeper()              # the closing is set: its wait returns at once
        thread.join(FAILSAFE_S)
        assert not thread.is_alive()

    def test_sweeper_survives_a_failing_sweep(self):
        calls, ticks, second = [], ManualTicks(), threading.Event()
        pool, logs = make_pool()

        def sweep():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("disk")
            second.set()
        pool.sweep = sweep
        thread = pool.start_sweeper(wait=ticks)
        ticks.tick()
        ticks.tick()
        assert second.wait(FAILSAFE_S)
        ticks.stop()
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
        with pytest.raises(jobs.Stopping):          # never slice.busy, which a user is shown
            pool.submit()


class TestLog:
    def test_one_line_per_transition_with_what_support_needs(self):
        clock = FakeClock()
        pool, logs = make_pool(clock=clock)
        describe = {"printer": None, "overrides": {"enable_support": "1"}, "parts": {"box": {"triangles": 12}},
                    "instances": [{"name": "Box #1", "x": 50.0}]}
        job_id = pool.submit(describe=describe)
        assert [e["state"] for e in logs] == ["queued", "running", "done"]
        done = logs[-1]
        assert done["event"] == "slice_job" and done["job"] == job_id
        assert done["overrides"] == {"enable_support": "1"} and done["instances"][0]["name"] == "Box #1"
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
        pool = JobPool(good_worker, executor=HeldExecutor(), log=BrokenLog(), clock=clock, ttl_s=1)
        queued, unfollowed = pool.submit(), pool.submit()
        assert pool.cancel(queued) == "cancelled"
        clock.now += 1
        assert pool.sweep() == 1
        assert pool.get(unfollowed)["state"] == "queued" and pool.get(queued) is None

    def test_the_sweeper_survives_a_log_that_fails_while_it_reports_a_failing_sweep(self):
        calls, ticks, second = [], ManualTicks(), threading.Event()
        pool = JobPool(good_worker, executor=ImmediateExecutor(), log=BrokenLog())

        def sweep():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("disk")
            second.set()
        pool.sweep = sweep
        thread = pool.start_sweeper(wait=ticks)
        ticks.tick()
        ticks.tick()
        assert second.wait(FAILSAFE_S)
        ticks.stop()
        thread.join(FAILSAFE_S)
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
        job_id = pool.submit()
        assert logs[-1]["event"] == "slice_cleanup_error" and "OSError: busy" in logs[-1]["traceback"]
        assert logs[-1]["job"] == job_id                # the line names the slice job it concerns


class TestAskedToStop:
    """Item 14: asked to stop once (stop), the pool ends every waiting slice job early with
    `shutdown`, lets the running one run to its end and refuses new ones with Stopping; it
    is drained once nothing runs and no done slice job still holds a sliced file. A second
    stop is shutdown(), which ends the running one early too."""

    def test_the_running_slice_job_runs_to_its_end_and_the_waiting_ones_end_with_shutdown(self):
        worker = Blocking(cancellable=True)
        pool, logs, executor = threaded_pool(worker)
        running, waiting = pool.submit(user_key="a"), pool.submit(user_key="b")
        assert worker.started.wait(FAILSAFE_S)
        assert pool.stop() == [waiting]
        assert pool.stopping()
        report = pool.get(waiting)
        assert (report["state"], report["cancel_reason"]) == ("cancelled", "shutdown")
        assert pool.get(running)["state"] == "running" and not pool.drained()
        worker.release.set()
        assert wait_final(pool, running)["state"] == "done"       # its stop was never set
        assert not pool.drained()                                 # its sliced file is not yet collected
        assert pool.delete_file(running)[0] == "deleted"
        assert pool.drained()
        assert [e["state"] for e in logs if e["job"] == running] == ["queued", "running", "done", "file_deleted"]
        executor.shutdown(wait=True)

    def test_a_submission_after_the_stop_is_refused_stopping_and_a_repeat_is_answered(self):
        pool, _logs = make_pool(executor=HeldExecutor())
        first = pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        pool._executor.run_next()
        pool.stop()
        with pytest.raises(jobs.Stopping):
            pool.submit(user_key="a", plate_id="p2", submission_id="s2")
        with pytest.raises(jobs.RepeatedSubmission) as caught:
            pool.submit(user_key="a", plate_id="p1", submission_id="s1")
        assert caught.value.job_id == first
        assert pool.remembered("a", "s2") is None

    def test_a_stopping_pool_never_answers_busy(self):
        pool, _logs = make_pool(executor=HeldExecutor(), max_running=1, max_queued=0)
        pool.submit()
        pool.stop()
        with pytest.raises(jobs.Stopping):
            pool.submit()
        assert error_report(jobs.Stopping())["code"] == "slice.stopping"

    def test_a_shut_down_pool_answers_stopping_too(self):
        pool, _logs = make_pool()
        pool.shutdown()
        with pytest.raises(jobs.Stopping):
            pool.submit()

    def test_the_contracts_example_is_the_report_of_a_stopping_pool(self):
        example = json.loads((CONTRACTS / "examples" / "slice-http" / "stopping.json").read_text())
        assert error_report(jobs.Stopping()) == example

    def test_a_running_slice_that_fails_drains_the_pool_with_no_file(self):
        release = threading.Event()

        def worker(job_id, payload, context):
            assert release.wait(FAILSAFE_S)
            raise JobFailure("Orca failed", "detail")
        pool, _logs, executor = threaded_pool(worker)
        job_id = pool.submit()
        pool.stop()
        assert not pool.drained()
        release.set()
        assert wait_final(pool, job_id)["state"] == "failed"
        assert pool.drained()
        executor.shutdown(wait=True)

    def test_a_done_slice_job_from_before_the_stop_holds_the_stop_until_its_file_is_collected(self):
        clock = FakeClock()
        pool, _logs = make_pool(clock=clock)
        job_id = pool.submit()
        assert pool.get(job_id)["state"] == "done"
        assert pool.stop() == []
        assert not pool.drained()
        clock.now += jobs.RECORD_TTL_S
        pool.sweep()                     # nothing collected it: it goes with its record
        assert pool.drained()

    def test_an_empty_pool_is_drained_at_once(self):
        pool, _logs = make_pool()
        assert pool.stop() == [] and pool.drained() and pool.wait_drained(timeout=FAILSAFE_S)

    def test_the_wait_for_the_drain_ends_on_the_collection_of_the_file(self):
        pool, _logs = make_pool()
        job_id = pool.submit()
        pool.stop()
        drained = []
        waiter = threading.Thread(target=lambda: drained.append(pool.wait_drained(timeout=FAILSAFE_S)))
        waiter.start()
        pool.delete_file(job_id)
        waiter.join(FAILSAFE_S)
        assert drained == [True]

    def test_the_wait_for_the_drain_ends_on_a_shutdown(self):
        worker = Blocking(cancellable=True)
        pool, _logs, executor = threaded_pool(worker)
        running = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        pool.stop()
        ended = []
        waiter = threading.Thread(target=lambda: ended.append(pool.wait_drained(timeout=FAILSAFE_S)))
        waiter.start()
        pool.shutdown()                  # the second stop: the running slice job is ended early too
        waiter.join(FAILSAFE_S)
        assert ended == [True]
        report = pool.get(running)
        assert (report["state"], report["cancel_reason"]) == ("cancelled", "shutdown")
        executor.shutdown(wait=True)

    def test_a_second_stop_ends_the_running_slice_job_with_shutdown_once_its_work_has_stopped(self):
        worker = Blocking(cancellable=True)
        pool, logs, _executor = threaded_pool(worker)
        running = pool.submit()
        assert worker.started.wait(FAILSAFE_S)
        pool.stop()
        pool.shutdown()                                           # returns once the worker has returned
        report = pool.get(running)
        assert (report["state"], report["cancel_reason"]) == ("cancelled", "shutdown")
        assert [e["state"] for e in logs if e["job"] == running][-2:] == ["cancelling", "cancelled"]

    def test_a_second_stop_with_an_uncollected_file_does_not_wait_for_it(self):
        pool, _logs = make_pool()
        job_id = pool.submit()
        pool.stop()
        pool.shutdown()                                           # nothing to wait for: it returns
        assert pool.get(job_id)["state"] == "done" and pool.listing()[0]["file_on_disk"]

    def test_a_submission_that_meets_an_executor_shut_down_meanwhile_is_answered_stopping(self):
        # A second stop between the pool's look and the executor's submit (the executor is
        # called outside the lock) once made POST /slices answer 500.
        class ShutDown:
            def submit(self, fn, *args):
                raise RuntimeError("cannot schedule new futures after shutdown")
        cleaned = []
        pool, logs = make_pool(executor=ShutDown(), cleanup=cleaned.append)
        with pytest.raises(jobs.Stopping):
            pool.submit("files")
        (entry,) = pool.listing()
        assert (entry["progress"]["state"], entry["progress"]["cancel_reason"]) == ("cancelled", "shutdown")
        assert cleaned == ["files"]

    def test_stopping_twice_ends_nothing_more(self):
        pool, _logs = make_pool(executor=HeldExecutor())
        pool.submit()
        pool._executor.run_next()
        pool.submit()
        assert len(pool.stop()) == 1 and pool.stop() == []


def test_constants_are_the_documented_defaults():
    assert (jobs.MAX_RUNNING, jobs.MAX_QUEUED, jobs.RECORD_TTL_S) == (1, 2, 7200)
    assert jobs.CANCEL_REASONS == ("replaced", "shutdown", "requested")
