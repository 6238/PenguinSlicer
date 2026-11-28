"""What the tests of asking about a slice job, its progress stream, its sliced file and the
two-hour rule share: the contract's example slice job `3f9a1c2b`, its reports, a stored
record written as the following writes one, a state bucket a test can make fail, and the
application with the stand-in for the slice service.

Nothing here reads the real clock or sleeps."""

import json
from pathlib import Path

import pytest

from front_fakes import START, Announcer
from front_helpers import DEV_GROUP, Lines, environ, shut, sign_in
from penguin_front import sliced
from penguin_front.app import create_app
from penguin_front.buckets import BucketUnavailable, FolderBucket
from penguin_front.records import write_record
from penguin_front.settings import Settings

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"
SLICE_DONE = json.loads((EXAMPLES / "wizard-front" / "slice-done.json").read_text())
SLICE_SUMMARY = json.loads((EXAMPLES / "wizard-front" / "slice-summary.json").read_text())
SLICE_EVENTS = (EXAMPLES / "wizard-front" / "slice-events.txt").read_text()
SUMMARY = json.loads((EXAMPLES / "sliced-file.json").read_text())
USER, OTHER, GROUP = "dev-user", "another-user", "dev-group"
JOB = "3f9a1c2b"
#: The example's slice job ended at 2026-11-27T22:31:47Z, 1,062 s after the clock's start.
ENDED_AT = "2026-11-27T22:31:47Z"
ENDED = START + 1062
#: The example's `done` report as the slice service gave it: without `sliced_file`.
DONE = {k: v for k, v in SLICE_DONE["progress"].items() if k != "sliced_file"}
#: A sliced file larger than one piece read from the network.
FILE = bytes(range(256)) * 40


def queued(job, sequence=1, ahead=0):
    return {"job": job, "state": "queued", "stage": "queued",
            "stage_label": "Waiting for the slicer", "elapsed_s": 0, "expected_s": 75,
            "sequence": sequence, "ahead": ahead}


def running(job, sequence, stage="slicing"):
    return {"job": job, "state": "running", "stage": stage, "stage_label": stage,
            "elapsed_s": sequence, "expected_s": 75, "sequence": sequence}


def done(job, sequence):
    return dict(DONE, job=job, sequence=sequence)


class Failing(FolderBucket):
    """The folder form, refusing reads while `refuse_reads` is set and writes while
    `refuse_writes` is set, as a state bucket that does not answer; `refuse_deletes` refuses
    deletes alone."""

    def __init__(self, root, clock):
        super().__init__(root, clock)
        self.refuse_reads = False
        self.refuse_writes = False
        self.refuse_deletes = False

    def open(self, name):
        if self.refuse_reads:
            raise BucketUnavailable("the state bucket refuses reads, by the test")
        return super().open(name)

    def list(self, prefix):
        if self.refuse_reads:
            raise BucketUnavailable("the state bucket refuses reads, by the test")
        return super().list(prefix)

    def put(self, name, data, **condition):
        if self.refuse_writes:
            raise BucketUnavailable("the state bucket refuses writes, by the test")
        return super().put(name, data, **condition)

    def delete(self, name):
        if self.refuse_writes or self.refuse_deletes:
            raise BucketUnavailable("the state bucket refuses writes, by the test")
        return super().delete(name)


def write_stored(bucket, job=JOB, *, user=USER, ended_at=ENDED_AT, report=None, file=FILE,
                 size_bytes=1843207, summary=SUMMARY):
    """A sliced file and its `stored` record, as the following writes them."""
    bucket.put(sliced.file_name(user, job), file)
    record = {"slice": job, "group": GROUP, "state": "stored", "file": summary["file"],
              "size_bytes": size_bytes, "summary": summary, "slice_ended_at": ended_at,
              "stored_at": ended_at, "report": report or done(job, 41)}
    write_record(bucket, sliced.record_name(user, job), sliced.KIND, record)
    return record


def write_failed(bucket, job=JOB, *, user=USER, ended_at=ENDED_AT):
    """The `failed` record of a sliced file over the limit, as the following writes it."""
    failed = dict(done(job, 41), state="failed", error={
        "code": "front.sliced_file_too_large", "message": "m", "remedy": "r",
        "retryable": False, "detail": "d"})
    record = {"slice": job, "group": GROUP, "state": "failed", "slice_ended_at": ended_at,
              "report": failed}
    write_record(bucket, sliced.record_name(user, job), sliced.KIND, record)
    return record


def write_submitted(bucket, job, submitted_at, *, user=USER, group=GROUP):
    record = {"slice": job, "group": group, "state": "submitted", "submitted_at": submitted_at}
    write_record(bucket, sliced.record_name(user, job), sliced.KIND, record)
    return record


def read_state(bucket, job=JOB, user=USER):
    record = sliced.read(bucket, user, job, Lines())
    return record and record["state"]


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def bucket(tmp_path, clock):
    return Failing(tmp_path / "state", clock)


@pytest.fixture
def app(tmp_path, clock, log, standin, bucket):
    app = create_app(Settings.from_environ(environ(tmp_path, PENGUIN_SLICE_URL=standin.url)),
                     clock=clock, log=log, state_bucket=bucket,
                     version="20261127T221405Z-ab12cd3")
    yield app
    shut(app, standin)


@pytest.fixture
def client(app):
    client = app.test_client()
    sign_in(client)
    return client


def context(app):
    return app.extensions["penguin_front"]


def get(client, path, **kwargs):
    headers = {**DEV_GROUP, **kwargs.pop("headers", {})}
    return client.get(path, headers=headers, **kwargs)


def at(clock, moment):
    """Move the fake clock forward to `moment`."""
    assert moment >= clock.now()
    clock.advance(moment - clock.now())


def requests_to(standin, method, path):
    return [r for r in standin.requests if r.method == method and r.path == path]


class Told(Announcer):
    """An announcer with a list: what a following gives a page, for waiting on."""

    def __init__(self):
        super().__init__()
        self.items = []

    def __call__(self, item):
        self.items.append(item)
        self.announce()
