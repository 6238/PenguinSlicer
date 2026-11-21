"""slicer.run_process and slice_plate on a real child process: tests/fake_orca.py in each of
its modes, standing in for an Orca that misbehaves.

No test sleeps. A stop is triggered by the fake's first progress message (it has then
installed its signal handlers), the timeout by firing the injected timer, and the death
of a process is awaited on its pidfd with a fail-safe that is reached only when a test is
failing.
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from helpers import FAILSAFE_S, TESTS, bounded, install_fake_orca, kill_fake, make_part
from penguin_slice import slicer
from penguin_slice.errors import error_report
from penguin_slice.plate_3mf import write_plate_3mf
from penguin_slice.slicer import OrcaExit, SliceCancelled, SliceError, Stop


@pytest.fixture
def plate(tmp_path):
    stls = tmp_path / "stls"
    stls.mkdir()
    parts = {"box": make_part(stls, "Box", (20, 20, 10))}
    write_plate_3mf(tmp_path / "plate.3mf", [{"ref": "box", "orientation": "+z", "angle": 0, "x": 100.0,
                                              "y": 100.0}], parts)
    return tmp_path / "plate.3mf"


def slice_with(tmp_path, monkeypatch, plate, mode, **kwargs):
    install_fake_orca(tmp_path, monkeypatch, mode)
    return slicer.slice_plate(plate, slicer.DEFAULT_PROFILES, tmp_path / "out", **kwargs)


def failure(tmp_path, monkeypatch, plate, mode, **kwargs):
    with pytest.raises(SliceError) as caught:
        slice_with(tmp_path, monkeypatch, plate, mode, **kwargs)
    return caught.value, error_report(caught.value)


def gone(lock_path):
    """Whether the process holding `lock_path` (fake_orca.py takes it for its whole life)
    has exited: the kernel releases the lock when it does. A blocking flock in a thread,
    never a sleep; the fail-safe is reached only when the process lives on."""
    acquired = threading.Event()

    def take():
        with open(lock_path, "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            acquired.set()
            fcntl.flock(fh, fcntl.LOCK_UN)

    thread = threading.Thread(target=take, daemon=True)
    thread.start()
    return acquired.wait(FAILSAFE_S)


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill 0; it has exited all the same. The process can also exit
    # between the kill and the read: any error reading its entry means it is gone (the
    # read once raised ProcessLookupError, which is not a FileNotFoundError).
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


REAL_OOM_KILLS = slicer._oom_kills      # before the autouse fixture replaces it


def stop_on_first_progress(stop, reason="cancel", also=None):
    """Stop at the stand-in's first message (it has set up its signal handlers by then),
    not at the slice service's own "slicing", which comes before Orca says anything."""
    def on_progress(stage, fraction, message):
        if stage == "slicing":
            return
        if also:
            also()
        stop.set(reason)
    return on_progress


class TestProgress:
    def test_orca_messages_arrive_as_stages_while_it_runs(self, tmp_path, monkeypatch, plate):
        seen = []
        result = slice_with(tmp_path, monkeypatch, plate, "ok", on_progress=lambda *args: seen.append(args))
        assert [s for s, _f, _m in seen] == ["slicing", "loading", "loading", "preparing", "slicing_mesh",
                                             "slicing_mesh", "generating_walls", "generating_gcode", "exporting",
                                             "exporting"]
        assert [f for _s, f, _m in seen] == [None, 0.01, 0.02, 0.03, 0.06, 0.07, 0.16, 0.75, 0.97, 1.0]
        assert result.layer_count == 42
        assert result.peak_rss_kb > 0 and result.wall_s >= 0
        assert not (tmp_path / "out" / "orca-progress.fifo").exists()

    def test_a_run_without_a_pipe_still_works(self, tmp_path, monkeypatch, plate):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        out.mkdir()
        cmd = [c for c in slicer.build_plate_command(plate, slicer.DEFAULT_PROFILES, out)]
        i = cmd.index("--pipe")
        del cmd[i:i + 2]
        run = slicer.run_process(cmd, cwd=out, env=slicer.orca_env(out), timeout_s=60)
        assert run.returncode == 0 and run.output.endswith("fake orca: sliced 1 objects")

    def test_the_stage_is_slicing_from_the_moment_orca_starts(self, tmp_path, monkeypatch, plate):
        # An Orca whose pipe stays silent: the stage is no longer "Building the plate".
        stop, seen = Stop(), []

        def on_progress(stage, fraction, message):
            seen.append((stage, fraction, message))
            if stage == "slicing":
                stop.set("cancel")
        install_fake_orca(tmp_path, monkeypatch, "hang")
        with pytest.raises(SliceCancelled):
            slicer.slice_plate(plate, slicer.DEFAULT_PROFILES, tmp_path / "out", stop=stop, on_progress=on_progress)
        assert seen[0] == ("slicing", None, "Slicing the plate")


def oom_counts(monkeypatch, before, after):
    """The kernel's out-of-memory kill count: `before` when Orca starts, `after` when it is gone."""
    counts = iter([before, after])
    monkeypatch.setattr(slicer, "_oom_kills", lambda: next(counts))


class TestSignals:
    """A kill for memory, a crash, and a stop by someone else are three different reports;
    a stop by the slice service itself (cancel, timeout, the memory watchdog) is neither.
    A kill is for memory only when the kernel's own out-of-memory kill count rose."""

    def test_killed_by_the_kernel_for_memory(self, tmp_path, monkeypatch, plate):
        oom_counts(monkeypatch, 3, 4)
        _exc, report = failure(tmp_path, monkeypatch, plate, "sigkill")
        assert report["code"] == "slice.out_of_memory"
        assert report["message"] == "This plate is too large to slice: the slicer ran out of memory."
        assert report["remedy"] == "Remove some instances or the largest part and print them on a second plate."
        assert report["retryable"] is False and report["action"] == "lower_quantities"
        assert report["detail"].startswith("ended by signal 9 (SIGKILL), not sent by the slice service; the "
                                           "kernel's oom_kill count rose by 1")
        assert "fake orca: about to stop" in report["detail"]

    @pytest.mark.parametrize("before, after, words", [
        (3, 3, "the kernel's oom_kill count did not change"),
        (None, None, "the kernel's oom_kill count could not be read"),
        (3, None, "the kernel's oom_kill count could not be read")])
    def test_a_sigkill_from_outside_without_the_kernels_count_is_a_kill(self, tmp_path, monkeypatch, plate,
                                                                        before, after, words):
        # Once reported as out of memory whatever the evidence.
        oom_counts(monkeypatch, before, after)
        _exc, report = failure(tmp_path, monkeypatch, plate, "sigkill")
        assert report["code"] == "slice.orca_killed"
        assert report["message"] == "Something on the print server stopped the slicer before it finished."
        assert report["retryable"] is True
        assert report["detail"].startswith(f"ended by signal 9 (SIGKILL), not sent by the slice service; {words}")

    @pytest.mark.parametrize("mode, number", [("segv", 11), ("abort", 6)])
    def test_crash(self, tmp_path, monkeypatch, plate, mode, number):
        _exc, report = failure(tmp_path, monkeypatch, plate, mode)
        assert report["code"] == "slice.orca_crashed"
        assert report["message"] == "The slicer crashed while slicing this plate."
        assert report["retryable"] is False
        assert report["detail"].startswith(f"ended by signal {number} (")

    def test_stopped_by_someone_else(self, tmp_path, monkeypatch, plate):
        _exc, report = failure(tmp_path, monkeypatch, plate, "sigterm")
        assert report["code"] == "slice.orca_killed"
        assert report["message"] == "Something on the print server stopped the slicer before it finished."
        assert report["retryable"] is True

    def test_the_three_are_distinct(self, tmp_path, monkeypatch, plate):
        codes = set()
        for mode in ("sigkill", "segv", "sigterm"):
            (tmp_path / mode).mkdir()
            oom_counts(monkeypatch, 0, 1 if mode == "sigkill" else 0)
            codes.add(failure(tmp_path / mode, monkeypatch, plate, mode)[1]["code"])
        assert codes == {"slice.out_of_memory", "slice.orca_crashed", "slice.orca_killed"}

    def test_bad_alloc_is_out_of_memory(self, tmp_path, monkeypatch, plate):
        _exc, report = failure(tmp_path, monkeypatch, plate, "bad_alloc")
        assert report["code"] == "slice.out_of_memory"
        assert report["detail"].startswith("orca code -100\nexit code 156")


class TestCancelAndTimeout:
    def test_cancel_stops_orca_and_reports_only_once_it_is_gone(self, tmp_path, monkeypatch, plate):
        stop = Stop()
        with pytest.raises(SliceCancelled) as caught:
            slice_with(tmp_path, monkeypatch, plate, "hang", stop=stop, on_progress=stop_on_first_progress(stop))
        pid = int((tmp_path / "out" / "fake-orca.pid").read_text())
        assert not alive(pid)                         # already reaped when SliceCancelled was raised
        assert "with SIGTERM after" in caught.value.details
        assert error_report(caught.value)["code"] == "slice.cancelled"

    def test_orca_that_ignores_sigterm_gets_sigkill(self, tmp_path, monkeypatch, plate):
        # Bounded: without the escalation this test fails in FAILSAFE_S instead of hanging.
        monkeypatch.setattr(slicer, "STOP_GRACE_S", 0)
        stop = Stop()
        install_fake_orca(tmp_path, monkeypatch, "hang_hard")
        try:
            _returned, raised, finished = bounded(lambda: slicer.slice_plate(
                plate, slicer.DEFAULT_PROFILES, tmp_path / "out", stop=stop, on_progress=stop_on_first_progress(stop)))
            assert finished, "Orca ignoring SIGTERM was never killed"
            assert isinstance(raised, SliceCancelled)
            assert "SIGTERM, then SIGKILL after the grace time" in raised.details
            assert not alive(int((tmp_path / "out" / "fake-orca.pid").read_text()))
        finally:
            kill_fake(tmp_path / "out")

    def test_a_stop_set_before_orca_starts_stops_it_at_once(self, tmp_path, monkeypatch, plate):
        stop = Stop()
        stop.set("cancel")
        with pytest.raises(SliceCancelled):
            slice_with(tmp_path, monkeypatch, plate, "hang", stop=stop)

    def test_timeout(self, tmp_path, monkeypatch, plate, timers):
        exc, report = failure(tmp_path, monkeypatch, plate, "hang",
                              on_progress=lambda stage, *args: stage == "slicing_mesh" and timers.made[-1].fire())
        assert timers.made[-1].interval == slicer.PLATE_SLICE_TIMEOUT_S
        assert report["code"] == "slice.timeout"
        assert report["message"] == "The slicer took too long on this plate."
        assert report["detail"].startswith("orca code timeout\nstopped by the slice service (timeout) with SIGTERM")
        assert "fake orca: slicing" in report["detail"]
        assert not alive(int((tmp_path / "out" / "fake-orca.pid").read_text()))

    def test_the_deadline_exists_before_any_message_of_orcas_is_read(self, tmp_path, monkeypatch, plate, timers):
        # Once made after the thread that reads Orca's messages had started: a message read
        # first found no timer (a test firing the timeout at it failed about once in 20 runs).
        pump_running_when_made, earlier = [], set(threading.enumerate())

        def make(interval, fn):
            pump_running_when_made.append(any(t.name == "orca-output" and t not in earlier
                                              for t in threading.enumerate()))
            return timers(interval, fn)
        monkeypatch.setattr(slicer, "TIMER", make)
        exc, report = failure(tmp_path, monkeypatch, plate, "hang",
                              on_progress=lambda stage, *args: stage == "slicing_mesh" and timers.made[-1].fire())
        assert pump_running_when_made == [False]
        assert report["code"] == "slice.timeout"

    def test_timeout_of_an_orca_that_ignores_sigterm(self, tmp_path, monkeypatch, plate, timers):
        monkeypatch.setattr(slicer, "STOP_GRACE_S", 0)
        install_fake_orca(tmp_path, monkeypatch, "hang_hard")
        try:
            _returned, raised, finished = bounded(lambda: slicer.slice_plate(
                plate, slicer.DEFAULT_PROFILES, tmp_path / "out",
                on_progress=lambda stage, *args: stage == "slicing_mesh" and timers.made[-1].fire()))
            assert finished, "Orca ignoring SIGTERM was never killed"
            report = error_report(raised)
            assert report["code"] == "slice.timeout"
            assert "SIGTERM, then SIGKILL after the grace time" in report["detail"]
        finally:
            kill_fake(tmp_path / "out")

    def test_timer_is_cancelled_when_orca_finishes(self, tmp_path, monkeypatch, plate, timers):
        slice_with(tmp_path, monkeypatch, plate, "ok")
        assert timers.made[-1].cancelled

    def test_a_child_orca_leaves_behind_is_killed(self, tmp_path, monkeypatch, plate):
        slice_with(tmp_path, monkeypatch, plate, "child")
        assert gone(tmp_path / "out" / "fake-orca-child.lock")


class TestMemoryWatchdog:
    """The slice service's guard on memory: the watchdog samples Orca's process group, its
    resident memory and the kernel's high-water mark of it, and stops Orca once the peak
    passes the ceiling. The reader is injected: its first sample waits for the stand-in's
    first message (an event, no clock), the next come at once (MEMORY_SAMPLE_S 0). Every
    test that waits on a stand-in that only a stop can end is bounded: with the watchdog's
    stop removed, or the ceiling setting ignored, it fails in FAILSAFE_S and kills its
    stand-in (it once hung the suite)."""

    def readings(self, monkeypatch, values):
        seen, ready, values = [], threading.Event(), list(values)

        def reader(pgid):
            if not seen:
                ready.wait(FAILSAFE_S)
            seen.append(pgid)
            return values.pop(0) if len(values) > 1 else values[0]
        monkeypatch.setattr(slicer, "MEMORY_READER", reader)
        monkeypatch.setattr(slicer, "MEMORY_SAMPLE_S", 0)
        return seen, (lambda stage, *args: stage == "slicing_mesh" and ready.set())

    def stopped_failure(self, tmp_path, monkeypatch, plate, **kwargs):
        """The SliceError of a "hang" stand-in that only the watchdog can stop, bounded."""
        install_fake_orca(tmp_path, monkeypatch, "hang")
        try:
            _returned, raised, finished = bounded(lambda: slicer.slice_plate(
                plate, slicer.DEFAULT_PROFILES, tmp_path / "out", **kwargs))
            assert finished, f"the watchdog never stopped Orca within {FAILSAFE_S} s"
            assert isinstance(raised, SliceError), f"the slice ended with {raised!r}, not a SliceError"
            return raised, error_report(raised)
        finally:
            kill_fake(tmp_path / "out")

    def test_orca_past_the_ceiling_is_stopped_and_reported_out_of_memory(self, tmp_path, monkeypatch, plate):
        seen, on_progress = self.readings(monkeypatch, [(100_000, 100_000), (400_000, 400_000), (900_000, 950_000)])
        exc, report = self.stopped_failure(tmp_path, monkeypatch, plate, memory_ceiling_mb=900,
                                           on_progress=on_progress)
        assert report["code"] == "slice.out_of_memory"
        assert report["message"] == ("This plate is too large to slice: the slicer needed more than the 900 MB of "
                                     "memory the print server allows.")
        assert report["retryable"] is False and report["action"] == "lower_quantities"
        assert report["detail"].startswith("stopped by the slice service (memory) with SIGTERM after ")
        assert ("Orca's processes reached a peak of 950,000 kB (the watchdog's high-water reading of Orca's "
                "processes), over") in report["detail"]
        assert "ru_maxrss" not in report["detail"]
        assert "over the ceiling of 921,600 kB (PENGUIN_SLICE_MAX_PEAK_MB=900)" in report["detail"]
        assert len(seen) == 3 and len(set(seen)) == 1               # three samples of one process group
        assert exc.peak_rss_kb == 950_000 and exc.reason == "stopped at the memory ceiling"
        assert not alive(int((tmp_path / "out" / "fake-orca.pid").read_text()))

    def test_a_spike_between_samples_is_seen_through_the_high_water_mark(self, tmp_path, monkeypatch, plate):
        # Resident memory back under the ceiling at the sample, its high-water mark over it:
        # the watchdog once read only the resident figure and missed the real Orca's spikes.
        _seen, on_progress = self.readings(monkeypatch, [(100_000, 100_000), (600_000, 930_000)])
        _exc, report = self.stopped_failure(tmp_path, monkeypatch, plate, memory_ceiling_mb=900,
                                            on_progress=on_progress)
        assert report["code"] == "slice.out_of_memory"
        assert "a peak of 930,000 kB" in report["detail"]

    def test_the_ceiling_is_the_setting(self, tmp_path, monkeypatch, plate):
        monkeypatch.setenv("PENGUIN_SLICE_MAX_PEAK_MB", "50")
        _seen, on_progress = self.readings(monkeypatch, [(60_000, 60_000)])
        _exc, report = self.stopped_failure(tmp_path, monkeypatch, plate, on_progress=on_progress)
        assert report["code"] == "slice.out_of_memory" and "the 50 MB of memory" in report["message"]
        assert "over the ceiling of 51,200 kB" in report["detail"]

    def test_orca_under_the_ceiling_slices_and_its_peak_is_kept(self, tmp_path, monkeypatch, plate):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        monkeypatch.setattr(slicer, "MEMORY_READER", lambda pgid: (3000, 4096))
        out = tmp_path / "out"
        out.mkdir()
        cmd = slicer.build_plate_command(plate, slicer.DEFAULT_PROFILES, out)
        run = slicer.run_process(cmd, cwd=out, env=slicer.orca_env(out), timeout_s=60, memory_ceiling_kb=8192)
        assert (run.returncode, run.stopped, run.memory_peak_kb, run.memory_ceiling_kb) == (0, None, 4096, 8192)

    def test_a_peak_over_the_ceiling_read_as_orca_exits_is_delivered_with_a_note(self, tmp_path, monkeypatch,
                                                                                  plate):
        # The watchdog's one sample returns only once the stand-in has exited, with a peak
        # over the 1 MB ceiling: Orca finished before the stop could be sent, so the sliced
        # file is delivered and the result says the peak passed the ceiling.
        monkeypatch.setattr(slicer, "MEMORY_READER", lambda pgid: (
            os.waitid(os.P_PID, pgid, os.WEXITED | os.WNOWAIT), (0, 2048))[1])
        result = slice_with(tmp_path, monkeypatch, plate, "ok", memory_ceiling_mb=1)
        assert result.output_path.is_file() and result.layer_count == 42
        assert result.peak_rss_kb == 2048
        assert result.memory_note == ("Orca's processes reached a peak of 2,048 kB (the watchdog's high-water "
                                      "reading of Orca's processes), over the ceiling of 1,024 kB "
                                      "(PENGUIN_SLICE_MAX_PEAK_MB=1), and Orca finished before the watchdog stopped "
                                      "it: the sliced file is delivered")

    def test_a_slice_under_the_ceiling_has_no_note(self, tmp_path, monkeypatch, plate):
        assert slice_with(tmp_path, monkeypatch, plate, "ok", memory_ceiling_mb=100_000).memory_note is None

    @pytest.mark.parametrize("rss, watchdog, peak", [(500, 400, 400), (400, 500, 500), (None, 300, 300),
                                                     (300, None, None), (None, None, None)])
    def test_the_peak_reported_is_the_watchdogs_reading_of_orca_alone(self, rss, watchdog, peak):
        # ru_maxrss counts the slice service's own memory at the fork (it survives exec): run
        # from a service holding 400 MB, /bin/true once reported a peak of 440,216 kB.
        assert OrcaExit(0, "", peak_rss_kb=rss, memory_peak_kb=watchdog).peak_kb == peak

    def test_the_kernels_figure_never_reaches_the_peak_of_a_real_child(self, tmp_path, monkeypatch, plate):
        # This process holds 64 MB more than the stand-in ever does: the kernel's ru_maxrss
        # of the child counts it, the reported peak does not.
        ballast = bytearray(64 * 1024 * 1024)
        ballast[::4096] = b"x" * len(ballast[::4096])                      # resident, not just reserved
        monkeypatch.setattr(slicer, "MEMORY_READER", lambda pgid: (1000, 1500))
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        out.mkdir()
        cmd = slicer.build_plate_command(plate, slicer.DEFAULT_PROFILES, out)
        run = slicer.run_process(cmd, cwd=out, env=slicer.orca_env(out), timeout_s=60, memory_ceiling_kb=1 << 30)
        assert run.peak_rss_kb > 64 * 1024 and run.peak_kb == 1500
        del ballast

    def test_the_watchdog_samples_after_orcas_last_message(self, tmp_path, monkeypatch, plate):
        # Orca's peak comes as it writes the sliced file, just before "All done, Success": a
        # sample follows that message, whatever the cadence (here longer than any test).
        # The stand-in writes its file, says "All done, Success" and waits: the reading after
        # that message passes the ceiling and the watchdog stops it, the file delivered.
        done = threading.Event()
        monkeypatch.setattr(slicer, "MEMORY_READER", lambda pgid: (0, 5000 if done.is_set() else 10))
        monkeypatch.setattr(slicer, "MEMORY_SAMPLE_S", 10 * FAILSAFE_S)
        install_fake_orca(tmp_path, monkeypatch, "written_then_hang")
        try:
            result, raised, finished = bounded(lambda: slicer.slice_plate(
                plate, slicer.DEFAULT_PROFILES, tmp_path / "out", memory_ceiling_mb=1,
                on_progress=lambda stage, fraction, message: message == "All done, Success" and done.set()))
        finally:
            kill_fake(tmp_path / "out")
        assert finished and raised is None, raised
        assert result.peak_rss_kb == 5000 and result.stop_note.startswith("stopped by the slice service (memory)")
        assert result.memory_note.endswith("the watchdog stopped Orca only after it had written the complete "
                                           "sliced file: the sliced file is delivered")

    def test_without_a_process_table_the_watchdog_reads_nothing_and_stops_nothing(self, tmp_path, monkeypatch,
                                                                                   plate):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        out.mkdir()
        cmd = slicer.build_plate_command(plate, slicer.DEFAULT_PROFILES, out)
        run = slicer.run_process(cmd, cwd=out, env=slicer.orca_env(out), timeout_s=60, memory_ceiling_kb=1,
                                 memory_reader=lambda pgid: None)
        assert (run.returncode, run.stopped, run.memory_peak_kb) == (0, None, None)

    def test_the_reader_sums_orcas_process_group(self, tmp_path):
        def process(pid, pgrp, status=None):
            fields = ["S", "1", str(pgrp)] + ["0"] * 20
            (tmp_path / str(pid)).mkdir()
            (tmp_path / str(pid) / "stat").write_text(f"{pid} (orca slicer) " + " ".join(fields) + "\n")
            if status is not None:
                (tmp_path / str(pid) / "status").write_text(f"Name:\torca-slicer\n{status}Threads:\t9\n")
        process(12, 777, "VmPeak:\t 999999 kB\nVmHWM:\t    900 kB\nVmRSS:\t    250 kB\n")
        process(13, 777, "VmHWM:\t    70 kB\nVmRSS:\t    50 kB\n")
        process(17, 777, "VmRSS:\t    5 kB\n")                     # no high-water line: its resident figure
        process(18, 777)                                          # gone between its stat and its status
        process(14, 888, "VmHWM:\t 99999 kB\nVmRSS:\t 9999 kB\n")  # another group
        (tmp_path / "15").mkdir()                                # gone while the table is read: no stat
        (tmp_path / "16").mkdir()
        (tmp_path / "16" / "stat").write_text("16 (cut off) S 1\n")
        (tmp_path / "self").mkdir()
        assert slicer.group_memory_kb(777, proc=str(tmp_path)) == (305, 975)

    def test_the_reader_without_a_process_table(self, tmp_path):
        assert slicer.group_memory_kb(1, proc=str(tmp_path / "no-proc")) is None

    @pytest.mark.skipif(not Path("/proc/self/status").exists(), reason="reads /proc")
    def test_the_reader_reads_this_machines_process_table(self):
        rss, hwm = slicer.group_memory_kb(os.getpgrp())
        assert 0 < rss <= hwm


class TestASlowNoteOfTheExit:
    """A stop asked just after Orca ended by itself, before the slice service has noted the
    exit, is never sent and never reported: how Orca really ended is. The waiter's note is
    held back until the slice service has signalled Orca's group (a stop sent, or the
    final SIGKILL of anything left), so the window is open for as long as it matters.
    Orca's ending once lost to the stop: a finished sliced file was thrown away as a timeout."""

    def hold_back_the_note(self, monkeypatch, stop, reason):
        real_wait, real_signal, signalled = slicer._wait_for_exit, slicer._signal_group, threading.Event()

        def late_note(pid):
            real_wait(pid)
            stop.set(reason)                        # Orca has ended; the exit is not noted yet
            signalled.wait(FAILSAFE_S)

        def signal_group(pgid, sig):
            real_signal(pgid, sig)
            signalled.set()
        monkeypatch.setattr(slicer, "_wait_for_exit", late_note)
        monkeypatch.setattr(slicer, "_signal_group", signal_group)

    @pytest.mark.parametrize("reason", ["timeout", "memory", "cancel"])
    @pytest.mark.parametrize("mode, code", [("segv", "slice.orca_crashed"), ("sigterm", "slice.orca_killed"),
                                            ("refuse", "slice.orca_too_close"), ("ok", None)])
    def test_orcas_own_ending_wins(self, tmp_path, monkeypatch, plate, mode, code, reason):
        stop = Stop()
        self.hold_back_the_note(monkeypatch, stop, reason)
        install_fake_orca(tmp_path, monkeypatch, mode)
        returned, raised, finished = bounded(lambda: slicer.slice_plate(plate, slicer.DEFAULT_PROFILES,
                                                                        tmp_path / "out", stop=stop))
        assert finished and stop.reason == reason
        if code is None:
            assert raised is None and returned.output_path.is_file()      # the finished sliced file is kept
        else:
            assert isinstance(raised, SliceError) and error_report(raised)["code"] == code
            assert "stopped by the slice service" not in raised.details


class Interrupted(Exception):
    pass


def test_an_interrupt_while_orca_runs_kills_it_and_returns(tmp_path, monkeypatch, plate):
    # A KeyboardInterrupt or the suite's own hang bound in the wait for Orca: the cleanup
    # once reaped Orca before the waiter thread had noted its exit, so the watchdog waited
    # for that note for ever. Now Orca is killed, noted, reaped, and the interrupt goes on.
    def interrupt(signum, frame):
        raise Interrupted()
    previous = signal.signal(signal.SIGUSR1, interrupt)
    try:
        install_fake_orca(tmp_path, monkeypatch, "hang_hard")
        with pytest.raises(Interrupted):
            slicer.slice_plate(plate, slicer.DEFAULT_PROFILES, tmp_path / "out",
                               on_progress=lambda stage, *args: stage == "slicing_mesh"
                               and os.kill(os.getpid(), signal.SIGUSR1))
    finally:
        signal.signal(signal.SIGUSR1, previous)
        kill_fake(tmp_path / "out")
    assert gone(tmp_path / "out" / "fake-orca.lock")


def test_a_wait_for_orcas_exit_that_fails_still_ends_the_run(tmp_path, monkeypatch, plate):
    # The waiter thread's note is set whatever its wait does, so neither the stop nor the
    # watchdog can wait for it for ever.
    real_wait, raised = slicer._wait_for_exit, []

    def failing_wait(pid):
        real_wait(pid)
        raise ChildProcessError(10, "No child processes")
    monkeypatch.setattr(slicer, "_wait_for_exit", failing_wait)
    monkeypatch.setattr(threading, "excepthook", lambda args: raised.append(args.exc_type))
    install_fake_orca(tmp_path, monkeypatch, "ok")
    returned, error, finished = bounded(lambda: slicer.slice_plate(plate, slicer.DEFAULT_PROFILES, tmp_path / "out"))
    assert finished, f"the run waited on the waiter's note for {FAILSAFE_S} s"
    assert error is None and returned.output_path.is_file() and raised == [ChildProcessError]


class TestWhichStopIsReported:
    def test_the_first_reason_is_kept(self):
        stop, woken = Stop(), []
        stop.listen(lambda: woken.append(stop.reason))
        stop.set("memory")
        stop.set("cancel")
        assert (stop.reason, woken) == ("memory", ["memory", "memory"])

    def test_a_cancel_after_a_watchdog_stop_reports_the_watchdog(self, tmp_path, monkeypatch, plate):
        stop = Stop()
        stop.set("memory")
        stop.set("cancel")
        _exc, report = failure(tmp_path, monkeypatch, plate, "hang", stop=stop)
        assert report["code"] == "slice.out_of_memory"
        assert report["detail"].startswith("stopped by the slice service (memory) with SIGTERM")

    def test_a_timeout_after_a_cancel_reports_the_cancel(self, tmp_path, monkeypatch, plate):
        stop = Stop()
        stop.set("cancel")
        stop.set("timeout")
        with pytest.raises(SliceCancelled):
            slice_with(tmp_path, monkeypatch, plate, "hang", stop=stop)


class TestSettle:
    """settle(), the one place a run's ending is decided: a finished sliced file is never
    discarded, then a stop the slice service sent, then Orca's own failure."""

    def archive(self, tmp_path):
        from helpers import make_archive
        out = tmp_path / "out"
        out.mkdir()
        make_archive(out / slicer.PLATE_ARCHIVE)
        with zipfile.ZipFile(out / slicer.PLATE_ARCHIVE, "a") as zf:
            zf.writestr(slicer.PLATE_JSON_ENTRY, '{"bbox_objects": [{"name": "Box"}]}')
        return out / slicer.PLATE_ARCHIVE, out

    @pytest.mark.parametrize("stopped", ["timeout", "memory", "cancel"])
    def test_orca_that_finished_after_a_stop_was_sent_delivers_its_file(self, tmp_path, stopped):
        archive, out = self.archive(tmp_path)
        result = slicer.settle(OrcaExit(0, "", stopped=stopped, memory_ceiling_kb=1024, memory_peak_kb=10),
                               archive, out)
        assert result.output_path == archive and result.memory_note is None

    @pytest.mark.parametrize("stopped, raised", [("timeout", SliceError), ("memory", SliceError),
                                                 ("cancel", SliceCancelled)])
    def test_a_stop_with_no_finished_file_is_the_stop(self, tmp_path, stopped, raised):
        with pytest.raises(raised) as caught:
            slicer.settle(OrcaExit(0, "", stopped=stopped, memory_ceiling_kb=1024, memory_peak_kb=10),
                          tmp_path / "none.gcode.3mf", tmp_path)
        assert "stopped by the slice service" in caught.value.details

    def test_no_stop_and_no_file_is_orcas_fault(self, tmp_path):
        with pytest.raises(SliceError) as caught:
            slicer.settle(OrcaExit(0, ""), tmp_path / "none.gcode.3mf", tmp_path)
        assert caught.value.error_code == "slice.no_output"

    # A stop the slice service decides on (a timeout, the watchdog) that kills Orca after it
    # wrote a complete sliced file: the file is delivered, with the stop recorded. A complete
    # file once failed as slice.timeout or slice.out_of_memory.

    @pytest.mark.parametrize("stopped", ["timeout", "memory"])
    def test_a_complete_file_survives_a_stop_that_killed_orca(self, tmp_path, stopped):
        archive, out = self.archive(tmp_path)
        result = slicer.settle(OrcaExit(-15, "", stopped=stopped, wall_s=2.2), archive, out,
                               entries=slicer.PLATE_ENTRIES)
        assert result.output_path == archive
        assert result.stop_note == (f"stopped by the slice service ({stopped}) with SIGTERM after 2.2 s, after Orca "
                                    f"had written the complete sliced file (it opens, its directory is intact, it "
                                    f"has Metadata/plate_1.gcode and Metadata/plate_1.json, and every entry reads "
                                    f"back with its checksum): the sliced file is delivered; Orca had not written "
                                    f"result.json, so its warnings are only those its debug log held by then")

    def test_the_note_on_a_stop_after_the_file_does_not_mention_result_json_when_orca_wrote_it(self, tmp_path):
        archive, out = self.archive(tmp_path)
        (out / slicer.RESULT_JSON).write_text('{"return_code": 0}')
        result = slicer.settle(OrcaExit(-15, "", stopped="timeout", wall_s=1.0), archive, out)
        assert result.stop_note.endswith("it has Metadata/plate_1.gcode, and every entry reads back with its "
                                         "checksum): the sliced file is delivered")

    def test_a_watchdog_stop_after_the_file_says_so_in_the_memory_note(self, tmp_path):
        archive, out = self.archive(tmp_path)
        result = slicer.settle(OrcaExit(-15, "", stopped="memory", memory_ceiling_kb=1024, memory_peak_kb=2048,
                                        wall_s=1.0), archive, out)
        assert result.memory_note.endswith("over the ceiling of 1,024 kB (PENGUIN_SLICE_MAX_PEAK_MB=1), and the "
                                           "watchdog stopped Orca only after it had written the complete sliced "
                                           "file: the sliced file is delivered")

    @pytest.mark.parametrize("stopped, code", [("timeout", "slice.timeout"), ("memory", "slice.out_of_memory")])
    @pytest.mark.parametrize("damage", ["half", "no plate_1.json", "bad checksum", "absent"])
    def test_an_incomplete_file_after_a_stop_is_the_stop(self, tmp_path, stopped, code, damage):
        from helpers import corrupt_entry, make_archive
        out = tmp_path / "out"
        out.mkdir()
        archive = out / slicer.PLATE_ARCHIVE
        if damage == "half":
            make_archive(archive)
            archive.write_bytes(archive.read_bytes()[:archive.stat().st_size // 2])
        elif damage == "no plate_1.json":
            make_archive(archive)                    # G-code and slice_info.config, no plate_1.json
        elif damage == "bad checksum":
            corrupt_entry(archive, slicer.GCODE_ENTRY, "; total layer number: 3\n" * 50,
                          others=((slicer.PLATE_JSON_ENTRY, '{"bbox_objects": []}'),))
        with pytest.raises(SliceError) as caught:
            slicer.settle(OrcaExit(-15, "", stopped=stopped, memory_ceiling_kb=1024, memory_peak_kb=10), archive, out,
                          entries=slicer.PLATE_ENTRIES)
        assert caught.value.error_code == code
        assert caught.value.details.startswith(f"stopped by the slice service ({stopped}) with SIGTERM")

    def test_a_cancel_discards_even_a_complete_file(self, tmp_path):
        archive, out = self.archive(tmp_path)
        with pytest.raises(SliceCancelled):
            slicer.settle(OrcaExit(-15, "", stopped="cancel"), archive, out)

    def test_a_success_must_have_every_entry_it_needs(self, tmp_path):
        # Without a stop the missing entry is the sliced file's own fault.
        from helpers import make_archive
        out = tmp_path / "out"
        out.mkdir()
        archive = out / slicer.PLATE_ARCHIVE
        make_archive(archive)                        # no Metadata/plate_1.json
        with pytest.raises(SliceError) as caught:
            slicer.settle(OrcaExit(0, ""), archive, out, entries=slicer.PLATE_ENTRIES)
        assert caught.value.error_code == "slice.unreadable_output"
        assert "has no entry Metadata/plate_1.json" in caught.value.details


class TestAStopAfterTheSlicedFileIsWritten:
    """The stand-in at each point a timeout or a watchdog stop can meet the sliced file:
    not yet under its final name, half written under it, complete under it. Only a complete
    one is delivered; a cancel discards even that."""

    def stop_at_the_end(self, tmp_path, monkeypatch, plate, mode, reason):
        install_fake_orca(tmp_path, monkeypatch, mode)
        stop = Stop()
        try:
            returned, raised, finished = bounded(lambda: slicer.slice_plate(
                plate, slicer.DEFAULT_PROFILES, tmp_path / "out", stop=stop,
                on_progress=lambda stage, fraction, message: message == "All done, Success" and stop.set(reason)))
        finally:
            kill_fake(tmp_path / "out")
        assert finished, f"the stand-in was never stopped within {FAILSAFE_S} s"
        assert not alive(int((tmp_path / "out" / "fake-orca.pid").read_text()))
        return returned, raised

    @pytest.mark.parametrize("reason", ["timeout", "memory"])
    def test_a_complete_file_is_delivered_with_the_stop_recorded(self, tmp_path, monkeypatch, plate, reason):
        returned, raised = self.stop_at_the_end(tmp_path, monkeypatch, plate, "written_then_hang", reason)
        assert raised is None, raised
        assert returned.output_path.is_file() and returned.layer_count == 42
        assert returned.stop_note.startswith(f"stopped by the slice service ({reason}) with SIGTERM after ")
        assert "the sliced file is delivered; Orca had not written result.json" in returned.stop_note

    @pytest.mark.parametrize("reason, code", [("timeout", "slice.timeout"), ("memory", "slice.out_of_memory")])
    @pytest.mark.parametrize("mode", ["tmp_then_hang", "half_then_hang"])
    def test_an_unfinished_file_fails_as_the_stop(self, tmp_path, monkeypatch, plate, mode, reason, code):
        returned, raised = self.stop_at_the_end(tmp_path, monkeypatch, plate, mode, reason)
        assert isinstance(raised, SliceError), (returned, raised)
        assert error_report(raised)["code"] == code
        assert raised.details.startswith(f"stopped by the slice service ({reason}) with SIGTERM")

    def test_a_cancel_discards_a_complete_file(self, tmp_path, monkeypatch, plate):
        _returned, raised = self.stop_at_the_end(tmp_path, monkeypatch, plate, "written_then_hang", "cancel")
        assert isinstance(raised, SliceCancelled)


class TestAnOutsideSignalThenAStop:
    """A run the slice service sent only SIGTERM, but which ended on another signal or was
    already ending when the stop was asked, is reported as what really ended it, the stop
    mentioned only in the detail. Such a run was once reported as the stop: "the slicer
    took too long" for an Orca someone else had killed."""

    def outcome(self, tmp_path, monkeypatch, plate, on_progress, stop, mode="hang_hard"):
        monkeypatch.setattr(slicer, "STOP_GRACE_S", FAILSAFE_S)       # no escalation in these tests
        install_fake_orca(tmp_path, monkeypatch, mode)
        try:
            returned, raised, finished = bounded(lambda: slicer.slice_plate(
                plate, slicer.DEFAULT_PROFILES, tmp_path / "out", stop=stop, on_progress=on_progress))
        finally:
            kill_fake(tmp_path / "out")
        assert finished
        assert isinstance(raised, SliceError), (returned, raised)
        return raised, error_report(raised)

    def pid(self, tmp_path):
        return int((tmp_path / "out" / "fake-orca.pid").read_text())

    def in_the_moment_before_it_is_gone(self, monkeypatch):
        """Hold the run in the moment after the outside signal, before the kernel has torn
        Orca down: the slice service still finds it running, and the waiter's note of the
        exit is held back until the stop's SIGTERM has gone out. Without this, a fast death
        would let the slice service see the exit first, and never send its stop."""
        real_wait, real_signal, signalled = slicer._wait_for_exit, slicer._signal_group, threading.Event()

        def late_note(pid):
            real_wait(pid)
            signalled.wait(FAILSAFE_S)

        def signal_group(pgid, sig):
            real_signal(pgid, sig)
            signalled.set()
        monkeypatch.setattr(slicer, "_wait_for_exit", late_note)
        monkeypatch.setattr(slicer, "_signal_group", signal_group)
        monkeypatch.setattr(slicer, "_still_running", lambda pid: True)

    @pytest.mark.parametrize("reason", ["timeout", "memory", "cancel"])
    @pytest.mark.parametrize("sig, code", [(signal.SIGKILL, "slice.orca_killed"), (signal.SIGSEGV, "slice.orca_crashed")])
    def test_a_signal_just_before_the_stop_is_what_is_reported(self, tmp_path, monkeypatch, plate, sig, code, reason):
        # Whether the probe still sees the signal pending is a matter of microseconds; the
        # signal Orca ended on decides alone here.
        monkeypatch.setattr(slicer, "DYING_PROBE", lambda pid: False)
        self.in_the_moment_before_it_is_gone(monkeypatch)
        stop = Stop()

        def on_progress(stage, fraction, message):
            if stage == "slicing_mesh":
                os.kill(self.pid(tmp_path), sig)
                stop.set(reason)
        exc, report = self.outcome(tmp_path, monkeypatch, plate, on_progress, stop)
        assert report["code"] == code
        assert report["detail"].startswith(f"ended by signal {int(sig)} ({sig.name}), not sent by the slice service")
        assert f"the slice service had asked it to stop ({reason}) and sent SIGTERM, which is not what ended it" \
            in report["detail"]

    @pytest.mark.parametrize("sig, code", [(signal.SIGKILL, "slice.orca_killed"), (signal.SIGSEGV, "slice.orca_crashed")])
    def test_with_the_real_probe_the_report_is_the_same(self, tmp_path, monkeypatch, plate, sig, code):
        # Whichever of the two ways notices it, the error report is the same.
        stop = Stop()

        def on_progress(stage, fraction, message):
            if stage == "slicing_mesh":
                os.kill(self.pid(tmp_path), sig)
                stop.set("timeout")
        _exc, report = self.outcome(tmp_path, monkeypatch, plate, on_progress, stop)
        assert report["code"] == code
        assert "stopped by the slice service" not in report["detail"]

    @pytest.mark.parametrize("reason", ["timeout", "memory", "cancel"])
    def test_a_kill_from_outside_in_the_grace_time_is_what_is_reported(self, tmp_path, monkeypatch, plate, reason):
        # The stand-in ignores the slice service's SIGTERM; someone else's SIGKILL ends it.
        monkeypatch.setattr(slicer, "DYING_PROBE", lambda pid: False)
        stop = Stop()
        real = slicer._signal_group

        def signal_group(pgid, sig):
            real(pgid, sig)
            if sig == signal.SIGTERM:
                os.kill(pgid, signal.SIGKILL)
        monkeypatch.setattr(slicer, "_signal_group", signal_group)
        _exc, report = self.outcome(tmp_path, monkeypatch, plate,
                                    lambda stage, *a: stage == "slicing_mesh" and stop.set(reason), stop)
        assert report["code"] == "slice.orca_killed"
        assert "had asked it to stop" in report["detail"]

    @pytest.mark.parametrize("reason", ["timeout", "memory", "cancel"])
    def test_an_orca_already_ending_when_the_stop_is_asked_is_what_is_reported(self, tmp_path, monkeypatch, plate,
                                                                               reason):
        # Someone else's SIGTERM ends Orca on the same signal the slice service sends: only
        # Orca's state when the stop was asked tells them apart. The probe of that state is
        # injected here (TestOrcaDying tests the probe itself on a process table).
        stop, probed = Stop(), []
        monkeypatch.setattr(slicer, "DYING_PROBE", lambda pid: probed.append(pid) or True)
        self.in_the_moment_before_it_is_gone(monkeypatch)

        def on_progress(stage, fraction, message):
            if stage == "slicing_mesh":
                os.kill(self.pid(tmp_path), signal.SIGTERM)
                stop.set(reason)
        _exc, report = self.outcome(tmp_path, monkeypatch, plate, on_progress, stop, mode="hang")
        assert report["code"] == "slice.orca_killed"
        assert report["detail"].startswith("ended by signal 15 (SIGTERM), not sent by the slice service")
        assert f"it was already ending when the slice service asked it to stop ({reason})" in report["detail"]
        assert probed == [self.pid(tmp_path)]

    @pytest.mark.parametrize("mode, code", [("refuse", "slice.orca_too_close"), ("ok", None)])
    def test_an_orca_already_exiting_by_itself_keeps_its_own_ending(self, tmp_path, monkeypatch, plate, mode, code):
        # Orca was exiting by itself (not on a signal) when the stop was asked, and the
        # slice service still found it running: its own ending is reported, or its file kept.
        stop = Stop()
        real_wait, real_signal, signalled = slicer._wait_for_exit, slicer._signal_group, threading.Event()

        def late_note(pid):
            real_wait(pid)
            stop.set("timeout")                        # Orca has ended; the exit is not noted yet
            signalled.wait(FAILSAFE_S)

        def signal_group(pgid, sig):
            real_signal(pgid, sig)
            signalled.set()
        monkeypatch.setattr(slicer, "_wait_for_exit", late_note)
        monkeypatch.setattr(slicer, "_signal_group", signal_group)
        monkeypatch.setattr(slicer, "_still_running", lambda pid: True)     # the moment before it ended
        monkeypatch.setattr(slicer, "DYING_PROBE", lambda pid: True)
        install_fake_orca(tmp_path, monkeypatch, mode)
        returned, raised, finished = bounded(lambda: slicer.slice_plate(plate, slicer.DEFAULT_PROFILES,
                                                                        tmp_path / "out", stop=stop))
        assert finished
        if code is None:
            assert raised is None and returned.output_path.is_file() and returned.stop_note is None
        else:
            assert error_report(raised)["code"] == code
            assert "it was already ending when the slice service asked it to stop (timeout)" in raised.details

    def test_a_stop_the_service_escalated_is_still_the_stop(self, tmp_path, monkeypatch, plate):
        # The slice service's own SIGKILL: the stop is what ended Orca.
        monkeypatch.setattr(slicer, "STOP_GRACE_S", 0)
        install_fake_orca(tmp_path, monkeypatch, "hang_hard")
        stop = Stop()
        try:
            _returned, raised, finished = bounded(lambda: slicer.slice_plate(
                plate, slicer.DEFAULT_PROFILES, tmp_path / "out", stop=stop,
                on_progress=stop_on_first_progress(stop, "timeout")))
        finally:
            kill_fake(tmp_path / "out")
        assert finished and error_report(raised)["code"] == "slice.timeout"


def proc_entry(root, pid, state="S", flags=0x400100, status=None):
    """A process table entry under `root`: /proc/<pid>/stat and /proc/<pid>/status."""
    (root / str(pid)).mkdir(parents=True)
    fields = [state, "1", str(pid), str(pid), "0", "-1", str(flags)] + ["0"] * 20
    (root / str(pid) / "stat").write_text(f"{pid} (orca slicer) " + " ".join(fields) + "\n")
    lines = {"State": f"{state} (sleeping)", "SigPnd": "0000000000000000", "ShdPnd": "0000000000000000",
             "SigBlk": "0000000000000000", "SigIgn": "0000000000001000", "SigCgt": "0000000180000002",
             "CoreDumping": "0"}
    lines.update(status or {})
    (root / str(pid) / "status").write_text("".join(f"{k}:\t{v}\n" for k, v in lines.items()))


def bit(*signals):
    return f"{sum(1 << (int(s) - 1) for s in signals):016x}"


class TestOrcaDying:
    """slicer.orca_dying: whether Orca was already ending when a stop was asked, read from
    its process table entry."""

    @pytest.mark.parametrize("label, state, flags, status, dying", [
        ("healthy", "S", 0x400100, {}, False),
        ("a zombie", "Z", 0x400100, {}, True),
        ("exiting (PF_EXITING)", "R", 0x400104, {}, True),
        ("writing a core file", "D", 0x400100, {"CoreDumping": "1"}, True),
        ("SIGKILL pending", "R", 0x400100, {"SigPnd": bit(signal.SIGKILL)}, True),
        ("an unhandled SIGTERM pending for the group", "R", 0x400100, {"ShdPnd": bit(signal.SIGTERM)}, True),
        ("an unhandled SIGSEGV pending", "R", 0x400100, {"ShdPnd": bit(signal.SIGSEGV)}, True),
        ("a SIGTERM it handles", "R", 0x400100, {"ShdPnd": bit(signal.SIGTERM), "SigCgt": bit(signal.SIGTERM)},
         False),
        ("a SIGTERM it ignores", "R", 0x400100, {"ShdPnd": bit(signal.SIGTERM), "SigIgn": bit(signal.SIGTERM)},
         False),
        ("a SIGTERM it blocks", "R", 0x400100, {"SigPnd": bit(signal.SIGTERM), "SigBlk": bit(signal.SIGTERM)},
         False),
        ("a SIGCHLD pending", "R", 0x400100, {"SigPnd": bit(signal.SIGCHLD)}, False),
    ])
    def test_the_states_of_a_process(self, tmp_path, label, state, flags, status, dying):
        proc_entry(tmp_path, 77, state, flags, status)
        assert slicer.orca_dying(77, proc=str(tmp_path)) is dying, label

    def test_no_entry_or_an_unreadable_one_is_not_dying(self, tmp_path):
        assert slicer.orca_dying(78, proc=str(tmp_path)) is False
        (tmp_path / "79").mkdir()
        (tmp_path / "79" / "stat").write_text("79 (cut off) S\n")
        (tmp_path / "79" / "status").write_text("State:\tS\n")
        assert slicer.orca_dying(79, proc=str(tmp_path)) is False

    @pytest.mark.skipif(not Path("/proc/self/status").exists(), reason="reads /proc")
    def test_this_process_is_not_dying(self):
        assert slicer.orca_dying(os.getpid()) is False


class TestOutput:
    def test_megabytes_of_output_neither_block_nor_stay_in_memory(self, tmp_path, monkeypatch, plate):
        install_fake_orca(tmp_path, monkeypatch, "flood")
        out = tmp_path / "out"
        out.mkdir()
        os.mkfifo(out / slicer.PROGRESS_FIFO)
        cmd = slicer.build_plate_command(plate, slicer.DEFAULT_PROFILES, out)
        run = slicer.run_process(cmd, cwd=out, env=slicer.orca_env(out), timeout_s=60,
                                 progress_fifo=out / slicer.PROGRESS_FIFO)
        lines = run.output.splitlines()
        assert run.returncode == 0
        assert len(lines) == slicer.TAIL_LINES
        assert lines[-1] == "fake orca: sliced 1 objects"
        assert len(run.output) < 300_000

    def test_a_very_long_line_is_cut(self):
        seen = []
        reader = slicer._LineReader(seen.append)
        reader.feed(b"a" * (slicer.MAX_LINE_BYTES + 10))
        reader.feed(b"b" * 50 + b"\nnext\npartial")
        reader.close()
        assert seen == ["a" * slicer.MAX_LINE_BYTES + " [line cut]", "next", "partial"]

    def test_invalid_utf8_is_replaced_not_fatal(self, tmp_path, monkeypatch, plate):
        _exc, report = failure(tmp_path, monkeypatch, plate, "garbled")
        assert report["code"] == "slice.orca_too_close"
        assert "Br�cket is too close" in report["detail"]


class TestOrcaExits:
    @pytest.mark.parametrize("mode, code, piece", [
        ("exit_bare", "slice.orca_failed", "fake orca: giving up"),
        ("exit_137", "slice.orca_killed", "ended by signal 9 (SIGKILL)"),
        ("exit_127", "slice.orca_unstartable", "exit code 127: Orca did not start"),
        ("no_layers", "slice.no_layers", "orca said: No layers were detected."),
        ("print_empty", "slice.print_empty", "orca said: The print is empty."),
        ("bad_result", "slice.orca_failed", "orca code -100\nexit code 156"),
        ("no_output", "slice.no_output", ""),
        ("truncated", "slice.unreadable_output", "plate.gcode.3mf"),
        ("corrupt", "slice.unreadable_output", "plate.gcode.3mf"),
        ("unknown_code", "slice.orca_failed", "orca error_string: Something Orca has never said before."),
        ("general", "slice.orca_failed", "orca error_string: Failed slicing the model."),
        ("empty_layers", "slice.empty_layers", "orca warning_message: Object can't be printed for empty layer"),
    ])
    def test_each_exit_is_a_truthful_report(self, tmp_path, monkeypatch, plate, mode, code, piece):
        _exc, report = failure(tmp_path, monkeypatch, plate, mode)
        assert report["code"] == code
        assert piece in report["detail"]

    def test_empty_layers_with_supports_off_offer_supports(self, tmp_path, monkeypatch, plate):
        _exc, report = failure(tmp_path, monkeypatch, plate, "empty_layers")
        assert report["message"] == ("Box #1 has nothing to print between 9.9 and 11.34 mm high, so the layers "
                                     "above would start in mid-air.")
        assert report["where"] == {"instance": "Box #1", "height_mm": 9.9, "stage": "slicing"}
        assert report["action"] == "enable_supports"

    @pytest.mark.parametrize("mode, message, reason", [
        ("no_layers", "The slicer found no layers to print: a part's surface may have holes, or a part may be too "
                      "thin to slice.", "No layers were detected. You might want to repair your STL file(s) or "
                                        "check their size or thickness and retry."),
        ("print_empty", "The slicer found nothing it can print with these settings: a part may be thinner than the "
                        "nozzle can print.", "The print is empty. The model is not printable with current print "
                                             "settings.")])
    def test_orcas_words_for_nothing_to_slice_get_their_own_report(self, tmp_path, monkeypatch, plate, mode,
                                                                   message, reason):
        # Once the generic "could not slice this plate" with a remedy that could not help.
        exc, report = failure(tmp_path, monkeypatch, plate, mode)
        assert report["message"] == message
        assert "orientation" not in report["remedy"] and "action" not in report
        assert exc.reason.splitlines()[0] == reason            # reaches the log's orca_reason

    def test_an_orca_that_cannot_load_is_not_the_plates_fault(self, tmp_path, monkeypatch, plate):
        _exc, report = failure(tmp_path, monkeypatch, plate, "exit_127")
        assert report["message"] == "The slicer could not be started."
        assert report["remedy"] == "Ask a mentor to check the print server; the slicer will not start on it."
        assert "error while loading shared libraries" in report["detail"]

    def test_general_failure_no_longer_claims_a_missing_flat_face(self, tmp_path, monkeypatch, plate):
        _exc, report = failure(tmp_path, monkeypatch, plate, "general")
        assert report["message"] == "The slicer could not slice this plate."
        assert "flat" not in report["message"] and "action" not in report
        assert "debug log" not in report["detail"]                # the stand-in wrote no log: nothing said


class TestOrcasDebugLog:
    """Orca's reason for a general failure, from its debug log (--debug 3 --logfile): the
    warnings it reported while slicing reach that log only. The stand-in writes the real
    log's line (tests_orca pins it to the pinned Orca's)."""

    WARNING = "It seems object Box #1 has floating regions. Please re-orient the object or enable support generation."

    def test_a_general_failure_adds_the_logged_warning_labelled_as_maybe_unrelated(self, tmp_path, monkeypatch,
                                                                                    plate):
        # The log cannot tell which warning, if any, made the slice fail: a sound part beside a
        # failing one warns too (real Orca: a mushroom's "floating cantilever" beside a needle).
        exc, report = failure(tmp_path, monkeypatch, plate, "general_warned")
        assert report["code"] == "slice.orca_failed"
        assert report["message"] == ("The slicer could not slice this plate. It also warned, though this may not be "
                                     f"why it failed: {self.WARNING}")
        assert report["remedy"] == "Try another orientation or other print settings, and slice again."
        lines = report["detail"].splitlines()
        assert lines[:3] == ["orca code -100", "exit code 156", f"orca debug log warning: {self.WARNING}"]
        assert report["detail"].count("orca debug log warning") == 1                  # each warning once
        assert self.WARNING in exc.reason

    def test_every_logged_warning_is_listed_and_none_is_presented_as_the_reason(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        line = "cli_status_callback: percent=-1, warning_step=7, message={}, message_type=2, flag=32\n"
        mushroom = ("It seems object Mushroom #1 has floating cantilever. Please re-orient the object or enable "
                    "support generation.")
        (out / slicer.ORCA_LOG).write_text(line.format(mushroom) + line.format(self.WARNING) + line.format(mushroom))
        exc = slicer.orca_failure(OrcaExit(156, "run found error, return -100, exit..."), out)
        assert exc.error_code == "slice.orca_failed"
        # Sorted, not in the log's order, which Orca's threads change from run to run.
        assert exc.message == ("The slicer could not slice this plate. It also warned, though this may not be why it "
                               f"failed: {self.WARNING} {mushroom}")
        assert "It warned:" not in exc.message

    @pytest.mark.parametrize("code", sorted(c for c in slicer.ORCA_RETURN_CODES if c != -100))
    def test_a_failure_orca_names_by_its_return_code_ignores_the_log(self, tmp_path, code):
        # Only the general failure (-100) reads the log; -101, -52 and -50 keep their own sentence.
        out = tmp_path / "out"
        out.mkdir()
        (out / slicer.ORCA_LOG).write_text(fake_orca_log_line())
        exc = slicer.orca_failure(OrcaExit(256 + code, f"run found error, return {code}, exit..."), out)
        assert (exc.error_code, exc.message) == slicer.ORCA_RETURN_CODES[code]
        assert "debug log" not in exc.details and "floating" not in exc.reason

    def test_orca_is_asked_for_its_log_in_the_slices_own_folder(self, tmp_path, monkeypatch, plate):
        slice_with(tmp_path, monkeypatch, plate, "ok")
        argv = json.loads((tmp_path / "out" / "fake-orca-argv.json").read_text())
        assert argv[argv.index("--debug") + 1] == "3"
        assert argv[argv.index("--logfile") + 1] == str((tmp_path / "out" / "orca.log").resolve())

    @pytest.mark.parametrize("log", [None, "dir", b"", b"no warning here\nfound slicing or export error\n",
                                     b"cli_status_callback: percent=-1, warning_step=7, message=, message_type=2, "
                                     b"flag=32\n", b"\xff\xfe garbage \x00\n" * 50])
    def test_a_log_missing_unreadable_or_without_a_warning_keeps_the_general_sentence(self, tmp_path, log):
        out = tmp_path / "out"
        out.mkdir()
        if log == "dir":
            (out / slicer.ORCA_LOG).mkdir()
        elif log is not None:
            (out / slicer.ORCA_LOG).write_bytes(log)
        assert slicer.orca_log_warnings(out) == []
        exc = slicer.orca_failure(OrcaExit(156, "run found error, return -100, exit..."), out)
        assert (exc.error_code, exc.message) == ("slice.orca_failed", "The slicer could not slice this plate.")

    def test_the_log_is_read_within_bounds(self, tmp_path, monkeypatch):
        out = tmp_path / "out"
        out.mkdir()
        line = "cli_status_callback: percent=-1, warning_step=7, message={}, message_type=2, flag=32\n"
        text = "".join(line.format(f"warning {i} " + "w" * 400) for i in range(8))
        (out / slicer.ORCA_LOG).write_text("x" * 10_000 + "\n" + text)
        found = slicer.orca_log_warnings(out)
        assert len(found) == slicer.MAX_LOG_WARNINGS == 5
        assert all(len(w) == slicer.MAX_WARNING_CHARS for w in found) and found[0].startswith("warning 0 ")
        monkeypatch.setattr(slicer, "MAX_LOG_BYTES", 10_000)          # the warnings lie past the bound
        assert slicer.orca_log_warnings(out) == []

    def test_a_reason_orca_gives_elsewhere_wins_over_the_log(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        (out / slicer.ORCA_LOG).write_text(fake_orca_log_line())
        exc = slicer.orca_failure(OrcaExit(156, "No layers were detected. You might want to repair your STL."), out)
        assert exc.error_code == "slice.no_layers"
        (out / slicer.RESULT_JSON).write_text(json.dumps({"return_code": -101, "error_string": "too close"}))
        assert slicer.orca_failure(OrcaExit(155, ""), out).error_code == "slice.orca_too_close"


def fake_orca_log_line():
    import fake_orca
    return fake_orca.LOG_WARNING.format(name="Box #1") + "\n"


class TestAReusedOutputFolder:
    """slicer.slice_plate and slice_stl remove what an earlier run left in their output
    folder before Orca starts: a run stopped before Orca writes anything was once handed the
    old sliced file, with a stop_note."""

    def old_run(self, out):
        from helpers import write_names_archive
        out.mkdir(parents=True)
        write_names_archive(out / slicer.PLATE_ARCHIVE, ["Box #1"])
        with zipfile.ZipFile(out / slicer.PLATE_ARCHIVE, "a") as zf:
            zf.writestr(slicer.GCODE_ENTRY, "; total layer number: 7\n")
        (out / (slicer.PLATE_ARCHIVE + ".tmp")).write_bytes(b"old")
        (out / slicer.RESULT_JSON).write_text('{"return_code": 0}')
        (out / slicer.ORCA_LOG).write_text(fake_orca_log_line())

    def test_a_timeout_before_orca_writes_is_the_timeout_not_the_old_file(self, tmp_path, monkeypatch, plate):
        out = tmp_path / "out"
        self.old_run(out)
        timers = slicer.TIMER
        install_fake_orca(tmp_path, monkeypatch, "hang")
        try:
            _r, raised, finished = bounded(lambda: slicer.slice_plate(
                plate, slicer.DEFAULT_PROFILES, out,
                on_progress=lambda stage, *a: stage == "slicing_mesh" and timers.made[-1].fire()))
        finally:
            kill_fake(out)
        assert finished and isinstance(raised, SliceError) and raised.error_code == "slice.timeout"
        assert not (out / slicer.PLATE_ARCHIVE).exists() and not (out / slicer.RESULT_JSON).exists()

    def test_a_general_failure_does_not_read_an_old_log(self, tmp_path, monkeypatch, plate):
        out = tmp_path / "out"
        self.old_run(out)
        install_fake_orca(tmp_path, monkeypatch, "general")
        with pytest.raises(SliceError) as caught:
            slicer.slice_plate(plate, slicer.DEFAULT_PROFILES, out)
        assert caught.value.message == "The slicer could not slice this plate."

    def test_slice_stl_clears_its_own_archive_too(self, tmp_path, monkeypatch):
        out = tmp_path / "out"
        out.mkdir()
        (out / "sample_part.gcode.3mf").write_bytes(b"an old sliced file")
        monkeypatch.setenv(slicer.ORCA_ENV, str(slicer.SAMPLE_STL))                  # a file that exists
        seen = []

        def orca_writes_nothing(cmd, **kwargs):
            seen.append((out / "sample_part.gcode.3mf").exists())
            return OrcaExit(0, "")
        monkeypatch.setattr(slicer, "run_process", orca_writes_nothing)
        with pytest.raises(SliceError) as caught:
            slicer.slice_stl(slicer.SAMPLE_STL, out)
        assert seen == [False] and caught.value.error_code == "slice.no_output"

    def test_a_folder_where_the_old_file_was_is_the_scratch_folders_fault(self, tmp_path, monkeypatch, plate):
        out = tmp_path / "out"
        (out / slicer.PLATE_ARCHIVE).mkdir(parents=True)
        install_fake_orca(tmp_path, monkeypatch, "ok")
        with pytest.raises(SliceError) as caught:
            slicer.slice_plate(plate, slicer.DEFAULT_PROFILES, out)
        assert caught.value.error_code == "slice.scratch_unwritable"


class TestOrcaThatWillNotStart:
    def test_missing_binary(self, tmp_path, monkeypatch, plate):
        monkeypatch.setenv(slicer.ORCA_ENV, str(tmp_path / "nowhere"))
        with pytest.raises(RuntimeError):
            slicer.slice_plate(plate, slicer.DEFAULT_PROFILES, tmp_path / "out")

    def test_not_executable(self, tmp_path, plate):
        _exc, report = failure_direct(plate, tmp_path)
        assert report["code"] == "slice.orca_unstartable" and "Permission denied" in report["detail"]

    def test_wrong_architecture(self, tmp_path, monkeypatch, plate):
        binary = tmp_path / "orca-other-arch"
        binary.write_bytes(b"\x7fELF\x02\x01\x01" + b"\x00" * 9 + b"\x02\x00\x08\x00" + b"\x00" * 100)
        binary.chmod(0o755)
        monkeypatch.setenv(slicer.ORCA_ENV, str(binary))
        _exc, report = failure_direct(plate, tmp_path)
        assert report["code"] == "slice.orca_unstartable" and "Exec format error" in report["detail"]


class TestPlumbing:
    def test_drain_reads_what_is_left_and_stops_at_the_end_or_when_nothing_waits(self):
        seen = []
        reader = slicer._LineReader(seen.append)
        read_end, write_end = os.pipe()
        os.write(write_end, b"one\ntwo")
        slicer._drain(read_end, reader)             # the writer still open: stops when nothing waits
        assert seen == ["one"]
        os.write(write_end, b"\nthree\n")
        os.close(write_end)
        slicer._drain(read_end, reader)             # the writer closed: stops at the end of file
        os.close(read_end)
        assert seen == ["one", "two", "three"]

    def test_signal_to_a_group_that_is_gone_is_harmless(self):
        slicer._signal_group(2 ** 22 + 12345, signal.SIGTERM)

    def test_oom_kills_unknown_without_the_cgroup_file(self, monkeypatch):
        monkeypatch.setattr(slicer.Path, "read_text", lambda self, *a, **k: (_ for _ in ()).throw(OSError("no")))
        assert REAL_OOM_KILLS() is None

    def test_oom_kills_unknown_when_the_file_has_no_count(self, monkeypatch):
        monkeypatch.setattr(slicer.Path, "read_text", lambda self, *a, **k: "low 0\n")
        assert REAL_OOM_KILLS() is None

    def test_oom_kills_read_from_the_cgroup_file(self, monkeypatch):
        monkeypatch.setattr(slicer.Path, "read_text", lambda self, *a, **k: "oom 1\noom_kill 7\n")
        assert REAL_OOM_KILLS() == 7

    def test_an_unstartable_orca_without_a_pipe_leaves_nothing(self, tmp_path):
        with pytest.raises(OSError):
            slicer.run_process([str(tmp_path / "nothing")], cwd=tmp_path, env={}, timeout_s=1)


def failure_direct(plate, tmp_path):
    with pytest.raises(SliceError) as caught:
        slicer.slice_plate(plate, slicer.DEFAULT_PROFILES, tmp_path / "out")
    return caught.value, error_report(caught.value)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="PR_SET_PDEATHSIG is Linux only")
def test_orca_does_not_outlive_a_service_that_is_killed(tmp_path, monkeypatch, plate):
    install_fake_orca(tmp_path, monkeypatch, "hang")
    service = subprocess.Popen([sys.executable, str(TESTS / "service_until_killed.py"), str(plate),
                                str(tmp_path / "out")], stdout=subprocess.PIPE, text=True,
                               env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path)))
    orca = None
    try:
        line = service.stdout.readline()                # blocks until Orca has reported progress
        assert line.startswith("orca "), line
        orca = int(line.split()[1])
        assert alive(orca)
        service.kill()
        service.wait()
        assert gone(tmp_path / "out" / "fake-orca.lock")
    finally:
        kill_fake(tmp_path / "out")      # once `alive(orca) and os.kill(...)`: it can exit in between
        service.kill()
        service.wait()
        service.stdout.close()
