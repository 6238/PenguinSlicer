"""Following every slice job and storing the sliced file and its summary, with the refusal of
one over the limit (README-details.md, "Following slice jobs and storing sliced files").

Every test puts the stand-in's events in an exact order and waits on events: a report
reaching a page, a request reaching the stand-in, the following parking on the fake clock.
None waits a number of seconds."""

import json
from pathlib import Path

import pytest

from front_fakes import BACKSTOP_S, START, Announcer, FakeClock
from front_helpers import Lines, environ, shut
from penguin_front import following, sliced
from penguin_front.app import create_app
from penguin_front.buckets import BucketUnavailable, FolderBucket, NotFound
from penguin_front.following import Follower, held_back, reports_of
from penguin_front.records import read_record, write_record
from penguin_front.settings import Settings
from penguin_front.slice_client import SliceUnreachable, json_object

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"
SUMMARY = json.loads((EXAMPLES / "sliced-file.json").read_text())
FILE = bytes(range(256)) * 40  # 10,240 bytes, larger than one piece read from the network
USER, GROUP = "dev-user", "dev-group"


def queued(job, sequence=1):
    return {"job": job, "state": "queued", "stage": "queued",
            "stage_label": "Waiting for the slicer", "elapsed_s": 0, "expected_s": 75,
            "sequence": sequence, "ahead": 0}


def running(job, sequence, stage="slicing", fraction=None):
    report = {"job": job, "state": "running", "stage": stage, "stage_label": stage,
              "elapsed_s": sequence, "expected_s": 75, "sequence": sequence}
    if fraction is not None:
        report["fraction"] = fraction
    return report


def done(job, sequence):
    return {"job": job, "state": "done", "stage": "reading_result",
            "stage_label": "Reading the sliced file", "fraction": 1.0, "elapsed_s": 52.8,
            "expected_s": 75, "sequence": sequence}


class Recording(FakeClock):
    """The fake clock, noting every wait it is asked for, so a test can wait for the
    following to park in its next wait before it moves time."""

    def __init__(self):
        super().__init__()
        self.waits = []
        self._seen = 0

    def sleep(self, seconds, stop=None):
        with self._cond:
            self.waits.append(seconds)
        return super().sleep(seconds, stop)

    def next_wait(self):
        """Block until a wait not yet seen by this call has begun; give its seconds. One
        thread's waits come one after another, so once the next has begun, the one before
        it has ended."""
        with self._cond:
            target = self._seen + 1
            if not self._cond.wait_for(
                    lambda: len(self.waits) >= target and self._sleepers >= 1, BACKSTOP_S):
                raise AssertionError(f"wait number {target} never began")
            self._seen = target
            return self.waits[target - 1]


class Watched(FolderBucket):
    """The folder form, noting each write with how many requests the stand-in had received
    by then, and refusing every write while `refuse` is set."""

    def __init__(self, root, clock, standin):
        super().__init__(root, clock)
        self.standin = standin
        self.refuse = False
        self.refused = 0
        self.writes = []

    def put(self, name, data, **condition):
        if self.refuse:
            self.refused += 1
            raise BucketUnavailable("the state bucket refuses writes, by the test")
        marker = super().put(name, data, **condition)
        self.writes.append((name, len(self.standin.requests)))
        return marker


class Page:
    """A page following a slice job: what the following delivers to it."""

    def __init__(self):
        self.reports = []
        self.closed = False
        self.told = Announcer()
        self.deletes_seen = []

    def deliver(self, report):
        if report is None:
            self.closed = True
        else:
            self.reports.append(report)
        self.told.announce()

    def wait(self, predicate, what):
        self.told.wait_for(lambda: predicate(self), what)


@pytest.fixture
def clock():
    return Recording()


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def bucket(tmp_path, clock, standin):
    return Watched(tmp_path / "state", clock, standin)


@pytest.fixture
def app(tmp_path, clock, log, standin, bucket):
    app = create_app(Settings.from_environ(environ(tmp_path, PENGUIN_SLICE_URL=standin.url)),
                     clock=clock, log=log, state_bucket=bucket)
    yield app
    shut(app, standin)


@pytest.fixture
def follower(app):
    return app.extensions["penguin_front"]["follower"]


def limited(app, limit):
    """Give `app` a following whose limit on a sliced file is `limit` bytes."""
    ctx = app.extensions["penguin_front"]
    ctx["follower"] = Follower(clock=ctx["clock"], slice_client=ctx["slice"],
                               bucket=ctx["state_bucket"], log=ctx["log"],
                               max_file_bytes=limit)
    return ctx["follower"]


def start(standin, follower, job="j1", file=FILE, user=USER):
    """A slice job waiting in the stand-in, followed, with its stream open."""
    standin.add_job(job, user, "plate-1", f"submission-{job}", queued(job), file=file,
                    summary=SUMMARY)
    follower.follow(user, job, GROUP)
    # Wait until the stream's first report, the latest at once, has been passed on, so that
    # a page subscribing after this sees only the reports the test sends.
    probe = Page()
    subscription = follower.subscribe(user, job, probe.deliver)
    if subscription.latest is None:
        probe.wait(lambda p: p.reports, f"{job}'s first report")
    subscription.cancel()
    assert standin.open_streams(job) == 1
    return Page()


def watch(follower, job, page, user=USER):
    subscription = follower.subscribe(user, job, page.deliver)
    assert subscription is not None
    return subscription


def requests_of(standin, method, path):
    return [n for n, r in enumerate(standin.requests) if r.method == method and r.path == path]


def wait_for_delete(standin, job):
    standin.changes.wait_for(lambda: requests_of(standin, "DELETE", f"/slices/{job}/file"),
                             f"the delete of {job}'s file")


def record_of(bucket, job, user=USER):
    return read_record(bucket, sliced.record_name(user, job), "sliced_file", Lines())[0]


# Storing.

def test_a_slice_job_ending_with_no_page_following_is_stored_then_deleted(standin, follower,
                                                                          bucket, clock):
    start(standin, follower)
    standin.report("j1", running("j1", 2))
    standin.report("j1", done("j1", 3))
    wait_for_delete(standin, "j1")
    assert bucket.get(sliced.file_name(USER, "j1"))[0] == FILE
    record = record_of(bucket, "j1")
    assert record == {"format": 1, "slice": "j1", "group": GROUP, "state": "stored",
                      "file": SUMMARY["file"], "size_bytes": len(FILE), "summary": SUMMARY,
                      "slice_ended_at": sliced.utc(START), "stored_at": sliced.utc(START),
                      "report": done("j1", 3)}
    [delete] = requests_of(standin, "DELETE", "/slices/j1/file")
    names = [name for name, _seen in bucket.writes]
    assert names == [sliced.file_name(USER, "j1"), sliced.record_name(USER, "j1")]
    assert all(seen <= delete for _name, seen in bucket.writes)
    assert all(standin.requests[n].user_key == USER for n in range(len(standin.requests)))


def test_a_page_gets_done_only_after_the_delete_and_it_carries_the_sliced_file(
        standin, follower):
    page = start(standin, follower)
    seen_delete = []

    def deliver(report):
        if report is not None:
            seen_delete.append(bool(requests_of(standin, "DELETE", "/slices/j1/file")))
        page.deliver(report)

    follower.subscribe(USER, "j1", deliver)
    standin.report("j1", running("j1", 2, "reading_result"))
    standin.report("j1", done("j1", 3))
    page.wait(lambda p: p.closed, "the page's following ending")
    *before, last = page.reports
    assert [r["state"] for r in before] == ["running"]
    assert last["state"] == "done" and last["sequence"] == 3
    assert last["sliced_file"] == {
        "slice": "j1", "file": SUMMARY["file"], "size_bytes": len(FILE), "summary": SUMMARY,
        "slice_ended_at": sliced.utc(START), "expires_at": sliced.utc(START + 7200),
        "expires_in_s": 7200}
    assert seen_delete[-1] is True and not any(seen_delete[:-1])


def test_each_report_reaches_a_page_once(standin, follower):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.report("j1", running("j1", 2))
    standin.repeat("j1")
    standin.report("j1", running("j1", 3, "generating_walls", 0.2))
    page.wait(lambda p: len(p.reports) == 2, "two reports")
    assert [r["sequence"] for r in page.reports] == [2, 3]


def test_a_stream_closed_before_a_final_report_is_opened_again(standin, follower, clock, log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.close_streams("j1")
    clock.next_wait()
    assert log.events("slice_stream_reopening")[-1]["wait_s"] == 1
    clock.advance(1)
    standin.changes.wait_for(lambda: len(requests_of(standin, "GET", "/slices/j1/events")) == 2,
                             "the stream opened again")
    standin.changes.wait_for(lambda: standin.open_streams("j1") == 1, "the stream open")
    standin.report("j1", running("j1", 2))
    page.wait(lambda p: [r["sequence"] for r in p.reports] == [2], "the next report")


def test_a_slice_job_unknown_on_reopening_ends_the_following_and_closes_the_pages(
        standin, follower, clock, log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.restart()  # a restarted slice service process knows none of the earlier jobs
    clock.next_wait()
    clock.advance(1)
    page.wait(lambda p: p.closed, "the following ending")
    assert page.reports == [] and "j1" not in follower.followed()
    assert log.events("slice_unknown")[-1]["slice"] == "j1"


def test_waits_before_opening_again_double_from_one_second_to_thirty(standin, follower,
                                                                     clock):
    start(standin, follower)
    standin.unreachable()
    expected = [1, 2, 4, 8, 16, 30, 30]
    for wait in expected:
        clock.next_wait()
        clock.advance(wait)
    clock.next_wait()
    assert clock.waits[:len(expected)] == expected
    standin.reachable()
    clock.advance(30)
    standin.changes.wait_for(lambda: standin.open_streams("j1") == 1, "the stream again")
    standin.report("j1", running("j1", 2))
    standin.report("j1", running("j1", 3))
    standin.close_streams("j1")
    clock.next_wait()
    assert clock.waits[-1] == 1  # a stream that opened starts the waits afresh


def test_the_file_cut_mid_fetch_leaves_no_record_and_is_fetched_again(standin, follower,
                                                                      bucket, clock, log):
    start(standin, follower)
    standin.cut_file("j1", 1000)
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    with pytest.raises(NotFound):
        bucket.get(sliced.record_name(USER, "j1"))
    with pytest.raises(NotFound):
        bucket.get(sliced.file_name(USER, "j1"))
    assert requests_of(standin, "DELETE", "/slices/j1/file") == []
    assert log.events("sliced_file_retry")[-1]["step"] == "fetching the sliced file"
    standin.cut_file("j1", None)
    clock.advance(1)
    wait_for_delete(standin, "j1")
    assert bucket.get(sliced.file_name(USER, "j1"))[0] == FILE
    assert len(requests_of(standin, "GET", "/slices/j1/file")) == 2
    assert len(requests_of(standin, "GET", "/slices/j1/summary")) == 1


def test_the_state_bucket_refusing_writes_is_tried_again_and_the_slice_seems_running(
        standin, follower, bucket, clock, log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    bucket.refuse = True
    standin.report("j1", running("j1", 2, "exporting"))
    standin.report("j1", done("j1", 3))
    for wait in (1, 2, 4):
        clock.next_wait()
        assert requests_of(standin, "DELETE", "/slices/j1/file") == []
        assert follower.latest(USER, "j1")["state"] == "running"
        clock.advance(wait)
    clock.next_wait()
    assert bucket.refused == 4 and clock.waits[-4:] == [1, 2, 4, 8]
    assert {line["step"] for line in log.events("sliced_file_retry")} == \
        {"storing the sliced file"}
    assert [r["state"] for r in page.reports] == ["running"]
    bucket.refuse = False
    clock.advance(8)
    page.wait(lambda p: p.closed, "the following ending")
    assert page.reports[-1]["state"] == "done"
    assert record_of(bucket, "j1")["slice_ended_at"] == sliced.utc(START)


def test_a_record_that_fails_to_be_written_is_written_again_without_the_file(
        standin, follower, bucket, clock):
    start(standin, follower)
    original = bucket.put

    def file_then_refuse(name, data, **condition):
        marker = original(name, data, **condition)
        if name.endswith(".gcode.3mf"):
            bucket.refuse = True
        return marker

    bucket.put = file_then_refuse
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    assert requests_of(standin, "DELETE", "/slices/j1/file") == []
    bucket.refuse = False
    clock.advance(1)
    wait_for_delete(standin, "j1")
    assert [name for name, _ in bucket.writes] == [sliced.file_name(USER, "j1"),
                                                   sliced.record_name(USER, "j1")]
    assert len(requests_of(standin, "GET", "/slices/j1/file")) == 1


def test_a_delete_that_fails_is_sent_again_and_the_page_waits_for_it(standin, follower,
                                                                     clock, log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.answer_next("DELETE", "/slices/j1/file", 409,
                        {"code": "slice.not_ready", "message": "m", "remedy": "r",
                         "retryable": False, "detail": "d"})
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    assert page.reports == [] and log.events("sliced_file_retry")[-1]["step"] == \
        "telling the slice service the file is stored"
    clock.advance(1)
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["state"] == "done"
    assert len(requests_of(standin, "DELETE", "/slices/j1/file")) == 2


def test_a_delete_answered_unknown_counts_as_done(standin, follower):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.answer_next("DELETE", "/slices/j1/file", 404,
                        {"code": "slice.unknown_job", "message": "m", "remedy": "r",
                         "retryable": False, "detail": "d"})
    standin.report("j1", done("j1", 2))
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["state"] == "done"


def test_a_delete_the_slice_service_does_not_answer_is_sent_again(standin, follower, clock,
                                                                  bucket):
    page = start(standin, follower)
    watch(follower, "j1", page)
    original = bucket.put

    def then_stop(name, data, **condition):
        marker = original(name, data, **condition)
        if name.endswith(".json"):
            standin.unreachable()
        return marker

    bucket.put = then_stop
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    assert page.reports == []
    standin.reachable()
    clock.advance(1)
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["state"] == "done"


def test_the_summary_not_answered_or_not_json_is_fetched_again(standin, follower, clock,
                                                               log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.answer_next("GET", "/slices/j1/summary", 200, ["not", "an", "object"])
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    assert log.events("sliced_file_retry")[-1]["why"] == "the summary is not a JSON object"
    standin.answer_next("GET", "/slices/j1/summary", 500,
                        {"code": "slice.unexpected", "message": "m", "remedy": "r",
                         "retryable": True, "detail": "d"})
    clock.advance(1)
    clock.next_wait()
    assert "slice.unexpected" in log.events("sliced_file_retry")[-1]["why"]
    clock.advance(2)
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["sliced_file"]["summary"] == SUMMARY


def test_a_sliced_file_gone_from_the_slice_service_ends_the_following(standin, follower,
                                                                      log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.answer_next("GET", "/slices/j1/summary", 410,
                        {"code": "slice.file_gone", "message": "m", "remedy": "r",
                         "retryable": False, "detail": "d"})
    standin.report("j1", done("j1", 2))
    page.wait(lambda p: p.closed, "the following ending")
    assert page.reports == [] and log.events("sliced_file_lost")[-1]["slice"] == "j1"


def test_a_slice_job_unknown_when_its_file_is_fetched_ends_the_following(standin, follower,
                                                                        log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.answer_next("GET", "/slices/j1/file", 404,
                        {"code": "slice.unknown_job", "message": "m", "remedy": "r",
                         "retryable": False, "detail": "d"})
    standin.report("j1", done("j1", 2))
    page.wait(lambda p: p.closed, "the following ending")
    assert page.reports == [] and log.events("slice_unknown")


def test_a_file_already_stored_is_not_fetched_again_and_its_delete_is_sent(standin, follower,
                                                                           bucket):
    # A front server that wrote the record and stopped before its delete went out: the
    # slice service is still told, before the page gets done.
    write_record(bucket, sliced.record_name(USER, "j1"), "sliced_file", {
        "slice": "j1", "group": GROUP, "state": "stored", "file": "x.gcode.3mf",
        "size_bytes": 3, "summary": SUMMARY, "slice_ended_at": sliced.utc(START - 60),
        "report": done("j1", 2)})
    page = start(standin, follower)
    seen_delete = []

    def deliver(report):
        if report is not None:
            seen_delete.append(bool(requests_of(standin, "DELETE", "/slices/j1/file")))
        page.deliver(report)

    follower.subscribe(USER, "j1", deliver)
    standin.report("j1", done("j1", 2))
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["sliced_file"]["expires_in_s"] == 7140
    assert requests_of(standin, "GET", "/slices/j1/file") == []
    assert len(requests_of(standin, "DELETE", "/slices/j1/file")) == 1
    assert seen_delete == [True]
    assert standin.jobs["j1"].file is None


def test_a_delete_after_a_stored_record_that_fails_is_sent_again(standin, follower, bucket,
                                                                  clock, log):
    write_record(bucket, sliced.record_name(USER, "j1"), "sliced_file", {
        "slice": "j1", "group": GROUP, "state": "stored", "file": "x.gcode.3mf",
        "size_bytes": 3, "summary": SUMMARY, "slice_ended_at": sliced.utc(START),
        "report": done("j1", 2)})
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.answer_next("DELETE", "/slices/j1/file", 500,
                        {"code": "slice.unexpected", "message": "m", "remedy": "r",
                         "retryable": True, "detail": "d"})
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    assert page.reports == []
    assert log.events("sliced_file_retry")[-1]["step"] == \
        "telling the slice service the file is stored"
    clock.advance(1)
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["state"] == "done"
    assert len(requests_of(standin, "DELETE", "/slices/j1/file")) == 2


def test_the_state_bucket_not_read_before_storing_is_read_again(standin, follower, bucket,
                                                                clock, log):
    original = bucket.get

    def unreadable(name):
        raise BucketUnavailable("the state bucket cannot be read, by the test")

    page = start(standin, follower)
    watch(follower, "j1", page)
    bucket.get = unreadable
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    assert log.events("sliced_file_retry")[-1]["step"] == "reading the record"
    bucket.get = original
    clock.advance(1)
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["state"] == "done"


# Over the limit.

def test_the_limit_is_50_megabytes():
    assert sliced.MAX_SLICED_FILE_BYTES == 50_000_000


@pytest.mark.parametrize("send_length", [True, False])
def test_a_sliced_file_over_the_limit_is_not_stored_and_reaches_the_page_failed(
        app, standin, bucket, log, send_length):
    follower = limited(app, len(FILE) - 1)
    page = start(standin, follower)
    standin.jobs["j1"].send_length = send_length
    watch(follower, "j1", page)
    standin.report("j1", done("j1", 7))
    page.wait(lambda p: p.closed, "the following ending")
    failed = page.reports[-1]
    assert failed["state"] == "failed" and failed["sequence"] == 7
    assert "sliced_file" not in failed
    assert failed["error"]["code"] == "front.sliced_file_too_large"
    assert failed["error"]["retryable"] is False
    with pytest.raises(NotFound):
        bucket.get(sliced.file_name(USER, "j1"))
    assert requests_of(standin, "DELETE", "/slices/j1/file")
    record = record_of(bucket, "j1")
    assert record["state"] == "failed" and record["report"] == failed
    assert record["group"] == GROUP
    [line] = log.events("sliced_file_too_large")
    assert line["limit_bytes"] == len(FILE) - 1
    if send_length:
        assert line["size_bytes"] == len(FILE)
    else:
        assert len(FILE) - 1 < line["size_bytes"] <= len(FILE)


def test_a_sliced_file_at_the_limit_is_stored(app, standin, bucket):
    follower = limited(app, len(FILE))
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.report("j1", done("j1", 2))
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["state"] == "done"
    assert bucket.get(sliced.file_name(USER, "j1"))[0] == FILE


def test_a_too_large_files_record_that_fails_is_written_again(app, standin, bucket, clock):
    follower = limited(app, 10)
    page = start(standin, follower)
    watch(follower, "j1", page)
    bucket.refuse = True
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    bucket.refuse = False
    clock.advance(1)
    page.wait(lambda p: p.closed, "the following ending")
    assert page.reports[-1]["state"] == "failed"
    # The delete comes before the record, and is sent again with it.
    assert len(requests_of(standin, "DELETE", "/slices/j1/file")) == 2
    assert record_of(bucket, "j1")["state"] == "failed"


def test_a_too_large_files_record_already_written_is_its_final_report(standin, follower,
                                                                      bucket):
    failed = {**done("j1", 2), "state": "failed", "error": {"code": "front.sliced_file_too_large"}}
    write_record(bucket, sliced.record_name(USER, "j1"), "sliced_file", {
        "slice": "j1", "group": GROUP, "state": "failed",
        "slice_ended_at": sliced.utc(START), "report": failed})
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.report("j1", done("j1", 2))
    page.wait(lambda p: p.closed, "the end")
    assert page.reports == [failed]
    assert requests_of(standin, "GET", "/slices/j1/file") == []
    assert len(requests_of(standin, "DELETE", "/slices/j1/file")) == 1


def test_the_summary_of_a_slice_service_not_answering_is_fetched_again(standin, follower,
                                                                       clock, log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    client = follower._slice
    send = client.send
    failures = []

    def once_unreachable(method, path, **extra):
        if path.endswith("/summary") and not failures:
            failures.append(path)
            raise SliceUnreachable("the slice service does not answer, by the test")
        return send(method, path, **extra)

    client.send = once_unreachable
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    assert "does not answer" in log.events("sliced_file_retry")[-1]["why"]
    clock.advance(1)
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["state"] == "done"


def test_a_body_that_is_not_one_json_object_is_none():
    assert json_object(b"not json") is None and json_object(b"[1]") is None
    assert json_object(b'{"a": 1}') == {"a": 1}


# Pages.

def test_three_pages_on_one_slice_job_make_one_connection(standin, follower):
    pages = [Page() for _ in range(3)]
    start(standin, follower)
    for page in pages:
        watch(follower, "j1", page)
    standin.report("j1", running("j1", 2))
    standin.report("j1", done("j1", 3))
    for page in pages:
        page.wait(lambda p: p.closed, "done")
        assert [r["state"] for r in page.reports] == ["running", "done"]
    assert len(requests_of(standin, "GET", "/slices/j1/events")) == 1


def test_a_page_subscribing_late_is_given_the_latest_report(standin, follower):
    first = start(standin, follower)
    watch(follower, "j1", first)
    standin.report("j1", running("j1", 2))
    first.wait(lambda p: len(p.reports) == 1, "the report")
    assert follower.subscribe(USER, "j1", Page().deliver).latest == running("j1", 2)


def test_a_page_that_cancels_gets_nothing_more(standin, follower):
    page = start(standin, follower)
    other = Page()
    subscription = watch(follower, "j1", page)
    watch(follower, "j1", other)
    subscription.cancel()
    subscription.cancel()
    standin.report("j1", running("j1", 2))
    other.wait(lambda p: p.reports, "the other page's report")
    assert page.reports == []


def test_another_users_slice_job_cannot_be_subscribed_to_or_read(standin, follower):
    start(standin, follower)
    assert follower.subscribe("someone-else", "j1", Page().deliver) is None
    assert follower.latest("someone-else", "j1") is None
    assert follower.subscribe(USER, "never", Page().deliver) is None


@pytest.mark.parametrize("final", [
    {"state": "failed", "error": {"code": "slice.orca_failed", "message": "m"}},
    {"state": "cancelled", "cancel_reason": "shutdown"},
])
def test_a_slice_ending_otherwise_reaches_the_pages_as_it_is(standin, follower, log, final):
    page = start(standin, follower)
    watch(follower, "j1", page)
    report = {**running("j1", 2), **final}
    standin.report("j1", report)
    page.wait(lambda p: p.closed, "the end")
    assert page.reports == [report] and "j1" not in follower.followed()
    [line] = log.events("slice_ended")
    assert line["state"] == final["state"]
    assert line["code"] == final.get("error", {}).get("code")
    assert line["cancel_reason"] == final.get("cancel_reason")
    assert requests_of(standin, "GET", "/slices/j1/file") == []


# The log.

def test_the_lines_of_a_following(standin, follower, log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.report("j1", running("j1", 2, "slicing"))
    standin.report("j1", running("j1", 3, "slicing", 0.1))
    standin.report("j1", running("j1", 4, "exporting", 0.9))
    standin.report("j1", done("j1", 5))
    page.wait(lambda p: p.closed, "done")
    who = {"user_key": USER, "group": GROUP, "slice": "j1"}
    assert log.events("slice_followed") == [{"event": "slice_followed", **who}]
    assert [(line["state"], line["stage"]) for line in log.events("slice_progress")] == [
        ("queued", "queued"), ("running", "slicing"), ("running", "exporting"),
        ("done", "reading_result")]
    [stored] = log.events("sliced_file_stored")
    assert stored == {"event": "sliced_file_stored", **who, "size_bytes": len(FILE),
                      "stored_after_s": 0}


def test_a_report_without_a_sequence_is_a_fault_logged_and_the_stream_opened_again(
        standin, follower, clock, log):
    start(standin, follower)
    standin.report("j1", {"job": "j1", "state": "running", "sequence": "2"})
    clock.next_wait()
    [line] = log.events("following_failed")
    assert "without a sequence" in line["trace"] and line["slice"] == "j1"


def test_a_fault_while_storing_is_logged_and_the_done_report_is_handled_again(
        standin, follower, bucket, clock, log):
    page = start(standin, follower)
    watch(follower, "j1", page)
    original = bucket.put
    faults = []

    def fault_once(name, data, **condition):
        if not faults:
            faults.append(name)
            raise RuntimeError("a fault planted by the test")
        return original(name, data, **condition)

    bucket.put = fault_once
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    assert "a fault planted" in log.events("following_failed")[-1]["trace"]
    clock.advance(1)
    page.wait(lambda p: p.closed, "done")
    assert page.reports[-1]["state"] == "done" and page.reports[-1]["sequence"] == 2
    assert bucket.get(sliced.file_name(USER, "j1"))[0] == FILE
    # When the slice ended is when the done report first arrived, not after the wait.
    assert record_of(bucket, "j1")["slice_ended_at"] == sliced.utc(START)
    assert page.reports[-1]["sliced_file"]["expires_in_s"] == 7199


def test_a_stream_refused_otherwise_is_opened_again(standin, follower, clock, log):
    standin.add_job("j1", USER, "p", "s", queued("j1"), file=FILE, summary=SUMMARY)
    standin.answer_next("GET", "/slices/j1/events", 500,
                        {"code": "slice.unexpected", "message": "m", "remedy": "r",
                         "retryable": True, "detail": "d"})
    follower.follow(USER, "j1", GROUP)
    clock.next_wait()
    assert "slice.unexpected" in log.events("slice_stream_reopening")[-1]["why"]
    clock.advance(1)
    standin.changes.wait_for(lambda: standin.open_streams("j1") == 1, "the stream")


# Stopping.

def test_a_stopped_following_ends_at_its_wait_and_follows_nothing_new(standin, follower,
                                                                      clock):
    start(standin, follower)
    standin.unreachable()
    clock.next_wait()
    follower.stop()
    follower.join()
    assert follower.followed() == set()
    assert follower.follow(USER, "j2", GROUP) is False


def test_a_following_stopped_while_storing_ends_at_its_wait(standin, follower, bucket,
                                                            clock):
    start(standin, follower)
    bucket.refuse = True
    standin.report("j1", done("j1", 2))
    clock.next_wait()
    follower.stop()
    follower.join()
    assert follower.followed() == set()


def test_a_following_stopped_while_a_stream_is_open_ends_with_the_next_report(standin,
                                                                             follower):
    start(standin, follower)
    follower.stop()
    standin.report("j1", running("j1", 2))
    follower.join()
    assert follower.followed() == set()


# What pages see of a report the slice service gives elsewhere.

def test_a_report_older_than_the_followings_latest_is_seen_as_the_latest(standin, follower):
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.report("j1", running("j1", 2))
    page.wait(lambda p: p.reports, "the report")
    assert follower.as_pages_see(USER, "j1", queued("j1")) == running("j1", 2)
    assert follower.as_pages_see(USER, "j1", running("j1", 9)) == running("j1", 9)


def test_a_done_report_is_seen_held_back_until_stored(standin, follower, bucket):
    assert follower.as_pages_see(USER, "j9", done("j9", 5)) == held_back(done("j9", 5))
    page = start(standin, follower)
    watch(follower, "j1", page)
    standin.report("j1", running("j1", 2))
    page.wait(lambda p: p.reports, "the report")
    assert follower.as_pages_see(USER, "j1", done("j1", 3)) == running("j1", 2)


def test_a_done_report_of_a_stored_file_is_seen_as_its_stored_report(follower, bucket,
                                                                     clock):
    write_record(bucket, sliced.record_name(USER, "j1"), "sliced_file", {
        "slice": "j1", "group": GROUP, "state": "stored", "file": "x.gcode.3mf",
        "size_bytes": 3, "summary": SUMMARY, "slice_ended_at": sliced.utc(START),
        "report": done("j1", 3)})
    seen = follower.as_pages_see(USER, "j1", done("j1", 3))
    assert seen["state"] == "done" and seen["sliced_file"]["expires_in_s"] == 7200


def test_a_done_report_is_held_back_when_the_state_bucket_cannot_be_read(follower, bucket):
    def unreadable(name):
        raise BucketUnavailable("by the test")

    bucket.get = unreadable
    assert follower.as_pages_see(USER, "j1", done("j1", 3))["state"] == "running"


def test_held_back_is_the_done_report_running_one_sequence_earlier():
    report = held_back({**done("j1", 41), "sliced_file": {"slice": "j1"}})
    assert report == {**done("j1", 41), "state": "running", "sequence": 40}


# The stream's events.

def test_the_reports_of_a_stream_are_its_progress_events():
    lines = ["event: version", 'data: {"version": "v"}', "", ": keep-alive", "",
             "id: 2", "event: progress", 'data: {"sequence": 2,', 'data: "state": "running"}',
             "", "event: progress", "", "id: 3", "event: progress",
             'data:{"sequence": 3}', ""]
    assert list(reports_of(lines)) == [{"sequence": 2, "state": "running"}, {"sequence": 3}]


def test_a_progress_event_that_is_not_an_object_is_a_fault():
    with pytest.raises(ValueError):
        list(reports_of(["event: progress", "data: [1]", ""]))


def test_the_slice_services_own_example_stream_gives_its_reports():
    lines = (EXAMPLES / "slice-http" / "events.txt").read_text().splitlines() + [""]
    sequences = [r["sequence"] for r in reports_of(lines)]
    assert sequences == [1, 2, 3, 17, 17, 38]


def test_the_waits_figures():
    assert following.FIRST_WAIT_S == 1 and following.LONGEST_WAIT_S == 30
