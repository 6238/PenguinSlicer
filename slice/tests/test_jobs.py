"""jobs.JobPool, with synchronous stand-ins for the executor and an injected clock.

No test sleeps or waits on a timeout that is expected to run out: a wait that must
return early is given no timeout at all, so only a notification can end it, and every
thread join has a generous fail-safe that is never reached when the code is right.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from penguin_slice import jobs
from penguin_slice.jobs import JobFailure, JobPool, QueueFull

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


class TickingClock:
    """One second later on every reading, so every update is later than the one before."""
    def __init__(self, start=1000.0):
        self.now = start
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            self.now += 1.0
            return self.now


def good_worker(job_id, payload):
    return {"token": "tok-" + job_id[:4], "summary": {"layer_count": 3}, "part": {"name": "sample_part"}}


class TestSubmitAndRun:
    def test_submit_returns_long_id_and_runs_worker_to_done(self):
        pool = JobPool(good_worker, executor=ImmediateExecutor())
        job_id = pool.submit()
        assert len(job_id) >= 32
        rec = pool.get(job_id)
        assert rec["state"] == "done"
        assert rec["token"] == "tok-" + job_id[:4]
        assert rec["summary"] == {"layer_count": 3}
        assert rec["part"] == {"name": "sample_part"}
        assert rec["error"] is None

    def test_payload_reaches_worker(self):
        seen = []

        def worker(job_id, payload):
            seen.append(payload)
            return good_worker(job_id, payload)

        pool = JobPool(worker, executor=ImmediateExecutor())
        plate = object()
        assert pool.get(pool.submit(payload=plate))["state"] == "done"
        pool.submit()
        assert seen[0] is plate
        assert seen[1] is None

    def test_states_go_queued_running_done_in_order(self):
        seen = []
        holder = {}

        def worker(job_id, payload):
            seen.append(holder["pool"].get(job_id)["state"])
            return good_worker(job_id, payload)

        executor = HeldExecutor()
        pool = JobPool(worker, executor=executor)
        holder["pool"] = pool
        job_id = pool.submit()
        seen.append(pool.get(job_id)["state"])
        executor.run_next()
        seen.append(pool.get(job_id)["state"])
        assert seen == ["queued", "running", "done"]

    def test_unknown_id_is_none(self):
        pool = JobPool(good_worker, executor=ImmediateExecutor())
        assert pool.get("nope") is None
        assert pool.wait("nope", 0, timeout=None) is None      # returns at once, never waits

    def test_get_returns_a_copy_with_elapsed(self):
        clock = FakeClock()
        pool = JobPool(good_worker, executor=HeldExecutor(), clock=clock)
        job_id = pool.submit()
        clock.now += 12.5
        rec = pool.get(job_id)
        assert rec["elapsed_s"] == 12.5
        assert (rec["created"], rec["updated"]) == (1000.0, 1000.0)
        rec["state"] = "hacked"
        assert pool.get(job_id)["state"] == "queued"

    def test_counts(self):
        executor = HeldExecutor()
        pool = JobPool(good_worker, executor=executor, max_queued=5)
        pool.submit()
        pool.submit()
        fn, args = executor.pending.pop(0)
        pool._update(args[0], state="running")
        assert pool.counts() == {"queued": 1, "running": 1}


class TestFailure:
    def test_job_failure_ends_failed_with_message_only_and_logs_details(self):
        logged = []

        def worker(job_id, payload):
            raise JobFailure("The slicer could not process this part.", "exit code 255\nsecret details")

        pool = JobPool(worker, executor=ImmediateExecutor(), log=logged.append)
        job_id = pool.submit()
        rec = pool.get(job_id)
        assert (rec["state"], rec["error"]) == ("failed", "The slicer could not process this part.")
        assert "secret details" not in str(rec)
        assert logged == [f"slice job {job_id[:8]} failed: The slicer could not process this part.\n"
                          "exit code 255\nsecret details"]

    def test_unexpected_exception_ends_failed_with_generic_message_and_logs_traceback(self):
        logged = []

        def worker(job_id, payload):
            raise RuntimeError("boom with a path /tmp/x")

        pool = JobPool(worker, executor=ImmediateExecutor(), log=logged.append)
        rec = pool.get(pool.submit())
        assert (rec["state"], rec["error"]) == ("failed", "The slicer failed unexpectedly.")
        assert "/tmp/x" not in str(rec)
        assert "crashed:" in logged[0] and "RuntimeError: boom with a path /tmp/x" in logged[0]

    def test_worker_returning_a_non_dict_ends_failed_without_raising(self):
        pool = JobPool(lambda job_id, payload: None, executor=ImmediateExecutor())
        job_id = pool.submit()          # a synchronous executor must not raise out of submit
        assert pool.get(job_id)["error"] == "The slicer failed unexpectedly."

    @pytest.mark.parametrize("failure", [JobFailure("The slicer could not process this part.", "x"),
                                         RuntimeError("boom")])
    def test_failure_wakes_a_subscriber_waiting_without_a_timeout(self, failure):
        # The subscriber is inside cond.wait (no timeout: only a notification ends it) before
        # the worker fails, so a failure that stamps nothing or notifies nobody leaves it
        # hanging and the join's fail-safe runs out.
        executor = HeldExecutor()
        started, release = threading.Event(), threading.Event()

        def worker(job_id, payload):
            started.set()
            assert release.wait(FAILSAFE_S)
            raise failure

        pool = JobPool(worker, executor=executor, clock=TickingClock())
        job_id = pool.submit()
        runner = threading.Thread(target=executor.run_next, daemon=True)
        runner.start()
        assert started.wait(FAILSAFE_S)
        running = pool.get(job_id)
        assert running["state"] == "running"

        waiting = threading.Event()

        class SignallingCondition(threading.Condition):
            def wait(self, timeout=None):
                waiting.set()           # still holding the lock: the worker cannot update yet
                return super().wait(timeout)

        pool._conds[job_id] = SignallingCondition(pool._lock)
        answers = []
        waiter = threading.Thread(target=lambda: answers.append(pool.wait(job_id, running["updated"], timeout=None)),
                                  daemon=True)
        waiter.start()
        assert waiting.wait(FAILSAFE_S)
        release.set()
        waiter.join(FAILSAFE_S)
        runner.join(FAILSAFE_S)
        assert not waiter.is_alive(), "a failed job did not wake its subscriber"
        assert answers[0]["state"] == "failed"
        assert answers[0]["updated"] > running["updated"]

    def test_default_log_swallows(self):
        pool = JobPool(lambda job_id, payload: 1 / 0, executor=ImmediateExecutor())
        assert pool.get(pool.submit())["state"] == "failed"


class TestQueueCap:
    def test_third_waiting_job_is_refused(self):
        executor = HeldExecutor()
        pool = JobPool(good_worker, executor=executor, max_queued=2)
        pool.submit()
        pool.submit()
        assert pool.counts() == {"queued": 2, "running": 0}
        with pytest.raises(QueueFull):
            pool.submit()
        assert len(executor.pending) == 2            # the refused job reached no executor
        executor.run_next()
        pool.submit()   # room again after one finished

    def test_running_jobs_do_not_count_as_queued_on_a_real_thread_pool(self):
        started = threading.Event()
        release = threading.Event()

        def slow_worker(job_id, payload):
            started.set()
            assert release.wait(FAILSAFE_S)
            return good_worker(job_id, payload)

        executor = ThreadPoolExecutor(max_workers=1)
        pool = JobPool(slow_worker, executor=executor, max_queued=1)
        try:
            first = pool.submit()
            assert started.wait(FAILSAFE_S)
            assert pool.get(first)["state"] == "running"
            second = pool.submit()   # one queued behind the running one
            with pytest.raises(QueueFull):
                pool.submit()
        finally:
            release.set()            # never leave a worker parked, even on a failed assert
            executor.shutdown(wait=True)
        assert pool.counts() == {"queued": 0, "running": 0}
        assert pool.get(first)["state"] == pool.get(second)["state"] == "done"

    def test_default_executor_runs_jobs_on_its_own_thread(self):
        names = []
        done = threading.Event()

        def worker(job_id, payload):
            names.append(threading.current_thread().name)
            done.set()
            return good_worker(job_id, payload)

        pool = JobPool(worker)
        try:
            pool.submit()
            assert done.wait(FAILSAFE_S)
        finally:
            pool._executor.shutdown(wait=True)
        assert names[0].startswith("slice")


class TestSubscribers:
    def test_wait_returns_on_state_change_without_a_timeout(self):
        executor = HeldExecutor()
        pool = JobPool(good_worker, executor=executor, clock=TickingClock())
        job_id = pool.submit()
        since = pool.get(job_id)["updated"]
        answers = []
        waiter = threading.Thread(target=lambda: answers.append(pool.wait(job_id, since, timeout=None)),
                                  daemon=True)
        waiter.start()
        executor.run_next()          # the change: running, then done, each notifying
        waiter.join(FAILSAFE_S)
        assert not waiter.is_alive(), "wait() missed the notification"
        assert answers[0]["state"] in ("running", "done")
        assert answers[0]["updated"] > since

    def test_wait_returns_at_once_when_the_record_has_moved_on(self):
        pool = JobPool(good_worker, executor=ImmediateExecutor(), clock=TickingClock())
        job_id = pool.submit()
        assert pool.wait(job_id, 0, timeout=None)["state"] == "done"

    def test_wait_with_no_change_returns_the_same_state_when_its_timeout_ends(self):
        pool = JobPool(good_worker, executor=HeldExecutor())
        job_id = pool.submit()
        rec = pool.wait(job_id, pool.get(job_id)["updated"], timeout=0)
        assert rec["state"] == "queued"

    def test_follow_yields_state_then_terminal(self):
        pool = JobPool(good_worker, executor=ImmediateExecutor())
        job_id = pool.submit()
        events = list(pool.follow(job_id, wait_s=0))
        assert [e for e, _ in events] == ["state", "done"]
        assert events[-1][1]["token"] == "tok-" + job_id[:4]

    def test_follow_repeats_state_on_cadence_until_change(self):
        executor = HeldExecutor()
        pool = JobPool(good_worker, executor=executor, clock=TickingClock())
        gen = pool.follow(pool.submit(), wait_s=0)
        first, second, third = next(gen), next(gen), next(gen)
        assert [(e, r["state"]) for e, r in (first, second, third)] == [("state", "queued")] * 3
        executor.run_next()
        rest = list(gen)
        assert rest[-1][0] == "done"
        assert all(e == "state" for e, _ in rest[:-1])

    def test_follow_failed_job_ends_with_failed(self):
        def worker(job_id, payload):
            raise JobFailure("The slicer could not process this part.", "x")

        pool = JobPool(worker, executor=ImmediateExecutor())
        events = list(pool.follow(pool.submit(), wait_s=0))
        assert [e for e, _ in events] == ["state", "failed"]
        assert events[-1][1]["error"] == "The slicer could not process this part."

    def test_follow_unknown_id_yields_nothing(self):
        pool = JobPool(good_worker, executor=ImmediateExecutor())
        assert list(pool.follow("nope", wait_s=0)) == []


class TestExpiry:
    def test_records_expire_one_hour_after_last_update_even_if_unread(self):
        clock = FakeClock()
        pool = JobPool(good_worker, executor=ImmediateExecutor(), clock=clock, ttl_s=3600)
        old = pool.submit()
        clock.now += 1800
        young = pool.submit()
        clock.now += 1801
        assert pool.expire() == 1
        assert pool.get(old) is None
        assert pool.get(young) is not None
        assert pool.expire(now=clock.now + 3600) == 1
        assert pool.get(young) is None

    def test_follow_stops_when_record_expires(self):
        clock = FakeClock()
        pool = JobPool(good_worker, executor=HeldExecutor(), clock=clock, ttl_s=10)
        gen = pool.follow(pool.submit(), wait_s=0)
        next(gen)
        clock.now += 11
        pool.expire()
        assert list(gen) == []

    def test_expire_wakes_a_waiter(self):
        clock = FakeClock()
        pool = JobPool(good_worker, executor=HeldExecutor(), clock=clock, ttl_s=10)
        job_id = pool.submit()
        answers = []
        entered = threading.Event()

        def wait():
            entered.set()
            answers.append(pool.wait(job_id, clock.now, timeout=None))

        waiter = threading.Thread(target=wait, daemon=True)
        waiter.start()
        assert entered.wait(FAILSAFE_S)
        # The waiter may not be inside cond.wait yet; if it is not, wait() finds the record
        # gone and returns None at once. Either way the answer is None.
        clock.now += 11
        pool.expire()
        waiter.join(FAILSAFE_S)
        assert not waiter.is_alive(), "expire() did not wake the waiter"
        assert answers == [None]

    def test_job_that_expired_while_running_finishes_quietly(self):
        clock = FakeClock()
        executor = HeldExecutor()
        pool = JobPool(good_worker, executor=executor, clock=clock, ttl_s=10)
        job_id = pool.submit()
        clock.now += 11
        pool.expire()
        executor.run_next()
        assert pool.get(job_id) is None


class StopSweeper(BaseException):
    """Raised by a fake sleep to end the sweeper's endless loop; the thread then ends with it,
    which pytest reports as an unhandled thread exception, so the two tests ignore that."""


SWEEPER_ENDS = pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")


class TestSweeper:
    @SWEEPER_ENDS
    def test_sweeper_expires_on_its_cadence(self):
        clock = FakeClock()
        pool = JobPool(good_worker, executor=ImmediateExecutor(), clock=clock, ttl_s=10)
        old = pool.submit()
        clock.now += 11
        intervals, swept, stop = [], threading.Event(), threading.Event()

        def fake_sleep(seconds):
            intervals.append(seconds)
            if len(intervals) == 2:          # the first sweep has run
                swept.set()
                stop.wait(FAILSAFE_S)
                raise StopSweeper

        thread = pool.start_sweeper(interval_s=600, sleep=fake_sleep)
        try:
            assert swept.wait(FAILSAFE_S)
            assert pool.get(old) is None
            assert thread.daemon and thread.name == "slice-jobs-sweeper"
        finally:
            stop.set()
            thread.join(FAILSAFE_S)
        assert intervals == [600, 600]

    @SWEEPER_ENDS
    def test_sweeper_survives_a_failing_expire(self, monkeypatch):
        logged = []
        pool = JobPool(good_worker, executor=ImmediateExecutor(), log=logged.append)
        calls = []

        def flaky_expire(now=None):
            calls.append(now)
            if len(calls) == 1:
                raise OSError("disk went away")
            return 0

        monkeypatch.setattr(pool, "expire", flaky_expire)
        slept, swept, stop = [], threading.Event(), threading.Event()

        def fake_sleep(seconds):
            slept.append(seconds)
            if len(slept) == 3:              # two sweeps have run, the first one failed
                swept.set()
                stop.wait(FAILSAFE_S)
                raise StopSweeper

        thread = pool.start_sweeper(sleep=fake_sleep)
        try:
            assert swept.wait(FAILSAFE_S)
        finally:
            stop.set()
            thread.join(FAILSAFE_S)
        assert len(calls) == 2
        assert "OSError: disk went away" in logged[0]
        assert slept == [jobs.SWEEP_INTERVAL_S] * 3


def test_constants_are_the_documented_defaults():
    assert jobs.MAX_RUNNING == 1
    assert jobs.MAX_QUEUED == 2
    assert jobs.RECORD_TTL_S == 3600
    assert jobs.WAIT_S == 5.0
    assert jobs.SWEEP_INTERVAL_S == 600
    assert jobs.TERMINAL == ("done", "failed")
