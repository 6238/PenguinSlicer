"""Item 18: the slice service's half of each row of the table "The slice container restarts"
(docs/architecture.md, "What a restart does"), through its HTTP interface.

A restart is the old slice service process stopped (its pool shut down, as the process's end
does) and a new one started on the same work folder: a new app with a new pool, a new part
store and a new log. The fake Orca of mode `gate` keeps a slice running until the test lets
it go on, and the pools run on the test's clock, so the restart and the requests come in
the exact order each test gives them; every wait is on an event behind FAILSAFE_S.

What the front server and the page do in each row is asserted in their own suites, and the
whole row in the joined suite. The table's last row (a print being sent or printing) has no
half here: printer delivery does not pass through the slice service."""
from helpers import FAILSAFE_S, USER_KEY, box_stl, install_fake_orca, open_gate, part_entry, submit, upload
from penguin_slice.errors import error_report
from penguin_slice.jobs import FINAL, JobPool
from penguin_slice.log_buffer import LogBuffer
from penguin_slice.web import create_app, remove_job_files, slice_worker

HEADERS = {"X-Penguin-User-Key": USER_KEY}
BRACKET, BLOCK = box_stl(40, 30, 12), box_stl(20, 20, 10)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Process:
    """One slice service process on `work`: its client, its pool and its log."""

    def __init__(self, work):
        self.clock = Clock()
        self.log = LogBuffer(clock=lambda: 1795817585.0 + self.clock.now)
        self.pool = JobPool(slice_worker, error_report=error_report, cleanup=remove_job_files, log=self.log,
                            clock=self.clock)
        self.app = create_app(work, self.pool, start_sweeper=False, log=self.log)
        self.client = self.app.test_client()

    def upload_parts(self):
        for data in (BRACKET, BLOCK):
            assert upload(self.client, data).status_code == 201

    def report(self, job):
        return self.client.get(f"/slices/{job}", headers=HEADERS)

    def until(self, job, predicate):
        report = self.pool.get(job)
        while not predicate(report):
            assert report["state"] not in FINAL, report
            report = self.pool.wait(job, report["sequence"], timeout=FAILSAFE_S)
        return report

    def end(self):
        """The process ends: every slice job of it is gone with it (its Orca too)."""
        self.pool.shutdown()


def plate(submission, plate_id="plate-1"):
    return {"plate_id": plate_id, "submission_id": submission,
            "parts": {"bracket": part_entry("Bracket", BRACKET), "block": part_entry("Block", BLOCK)},
            "instances": [{"ref": "bracket", "orientation": "+z", "angle": 0, "x": 60.0, "y": 60.0},
                          {"ref": "block", "orientation": "+z", "angle": 0, "x": 150.0, "y": 60.0}]}


MISSING = [{"key": "bracket", "sha256": part_entry("", BRACKET)["sha256"], "units": "mm"},
           {"key": "block", "sha256": part_entry("", BLOCK)["sha256"], "units": "mm"}]


def assert_new_process_knows_nothing_of(new, job):
    answer = new.report(job)
    assert (answer.status_code, answer.get_json()["code"]) == (404, "slice.unknown_job")
    events = new.client.get(f"/slices/{job}/events", headers=HEADERS)
    assert (events.status_code, events.get_json()["code"]) == (404, "slice.unknown_job")
    assert new.client.get("/slices").get_json() == {"slices": []}
    assert len(new.app.extensions["penguin_slice_store"]) == 0


def assert_submitted_again_after_the_parts(new, submission):
    """The page's way back: the plate names parts the new part store lacks, every one is
    listed, the page uploads them again and submits again with the same value."""
    missing = submit(new.client, plate(submission))
    body = missing.get_json()
    assert (missing.status_code, body["code"], body["action"]) == (422, "slice.part_missing", "refresh_parts")
    assert body["where"]["missing_parts"] == MISSING
    new.upload_parts()
    accepted = submit(new.client, plate(submission))
    assert accepted.status_code == 202 and accepted.get_json()["progress"]["state"] in ("queued", "running")
    return accepted.get_json()["job"]


class TestASliceWasWaitingOrRunning:
    """Row 1: progress starts again; the page uploads its parts again and submits again."""

    def test_a_running_slice_is_unknown_to_the_new_process_and_its_parts_are_missing(self, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "gate")
        work = tmp_path / "work"
        old = Process(work)
        old.upload_parts()
        job = submit(old.client, plate("s1")).get_json()["job"]
        old.until(job, lambda r: r.get("stage") == "slicing_mesh")         # Orca is running
        old.end()                                                          # the restart cuts it off
        assert old.pool.get(job)["state"] == "cancelled"
        new = Process(work)
        assert_new_process_knows_nothing_of(new, job)
        again = assert_submitted_again_after_the_parts(new, "s2")
        assert again != job
        new.until(again, lambda r: r.get("stage") == "slicing_mesh")      # progress starts again
        open_gate(work)                                                    # the old Orca's gate went with its folder
        assert new.until(again, lambda r: r["state"] in FINAL)["state"] == "done"
        new.end()

    def test_a_waiting_slice_at_a_stop_ends_with_shutdown_and_is_submitted_again(self, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "gate")
        work = tmp_path / "work"
        old = Process(work)
        old.upload_parts()
        running = submit(old.client, plate("s1")).get_json()["job"]
        old.until(running, lambda r: r.get("stage") == "slicing_mesh")
        waiting = submit(old.client, plate("s2", plate_id="plate-2")).get_json()["job"]
        old.pool.stop()                                                    # the deploy asks it to stop
        report = old.report(waiting).get_json()
        assert (report["state"], report["cancel_reason"]) == ("cancelled", "shutdown")
        assert "error" not in report                                       # no failure: nothing to show a user
        assert old.report(running).get_json()["state"] == "running"        # the running one goes on
        open_gate(work)
        assert old.until(running, lambda r: r["state"] in FINAL)["state"] == "done"
        old.client.delete(f"/slices/{running}/file", headers=HEADERS)
        assert old.pool.drained()
        old.end()
        new = Process(work)
        assert_new_process_knows_nothing_of(new, waiting)
        assert_submitted_again_after_the_parts(new, "s3")
        new.end()


class TestASubmissionWhileStopping:
    """Row 2: the slice is shown as waiting and the page submits again until the new slice
    service accepts."""

    def test_stopping_then_accepted_by_the_new_process_once_the_parts_are_back(self, tmp_path):
        work = tmp_path / "work"
        old = Process(work)
        old.upload_parts()
        old.pool.stop()
        answer = submit(old.client, plate("s1"))
        body = answer.get_json()
        assert (answer.status_code, body["code"], body["retryable"]) == (503, "slice.stopping", True)
        assert submit(old.client, plate("s1")).get_json()["code"] == "slice.stopping"   # submitted again
        assert old.client.get("/slices").get_json() == {"slices": []}     # nothing started, nothing remembered
        old.end()
        new = Process(work)
        assert_submitted_again_after_the_parts(new, "s1")                  # the refused value may come again
        new.end()


class TestASliceHadFinished:
    """Row 3: nothing; the sliced file is in the state bucket, and the slice service has no
    more to do with that slice once its copy was deleted."""

    def test_a_finished_and_collected_slice_is_no_concern_of_the_new_process(self, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        work = tmp_path / "work"
        old = Process(work)
        old.upload_parts()
        job = submit(old.client, plate("s1")).get_json()["job"]
        assert old.until(job, lambda r: r["state"] in FINAL)["state"] == "done"
        assert old.client.get(f"/slices/{job}/file", headers=HEADERS).status_code == 200      # the front server stores it
        assert old.client.delete(f"/slices/{job}/file", headers=HEADERS).status_code == 200
        old.pool.stop()
        assert old.pool.drained()                                          # a stop finds nothing to wait for
        old.end()
        new = Process(work)
        assert_new_process_knows_nothing_of(new, job)
        old_log, new_log = (p.client.get("/log?after=0").get_json() for p in (old, new))
        assert new_log["process"] != old_log["process"]                    # the front server starts again from 0
        new.end()
