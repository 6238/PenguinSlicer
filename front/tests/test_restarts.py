"""Each row of the table of what a restart of the front server does: the front server's half
(README-details.md, "Starting, and what a restart does"; docs/architecture.md, "What a
restart does", "The front server restarts").

For each row the front server is stopped at that moment and started again on the same
folders, with the same cookie key and the same stand-in for the slice service, and the
result is checked. A front server here is the application with its collection at start;
the running server's start and stop are tested in tests/test_server.py. Nothing waits a
number of seconds."""

import json
from pathlib import Path

import pytest

from front_fakes import BACKSTOP_S
from front_helpers import DEV_GROUP, Lines, environ, shut, sign_in
from penguin_front import sliced
from penguin_front.app import create_app
from penguin_front.cookie import COOKIE_NAME
from penguin_front.settings import Settings
from sliced_helpers import (FILE, SUMMARY, done, read_state, requests_to, running,
                            write_stored)
from test_streams import Reader

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"
BRACKET = (EXAMPLES / "parts" / "bracket.stl").read_bytes()
CONFIGURATION = json.loads((EXAMPLES / "wizard-front" / "configuration-write-request.json")
                           .read_text())["configuration"]
USER, GROUP = "dev-user", "dev-group"
PLATE = {"plate_id": "plate-1", "submission_id": "submission-1", "parts": {}}


class Restarts:
    """Front servers started one after another on the same folders and stand-in."""

    def __init__(self, tmp_path, clock, standin):
        self.tmp_path, self.clock, self.standin = tmp_path, clock, standin
        self.apps = []

    def start(self):
        """A front server started now: its collection at start has ended when it returns."""
        log = Lines()
        app = create_app(Settings.from_environ(environ(self.tmp_path,
                                                       PENGUIN_SLICE_URL=self.standin.url)),
                         clock=self.clock, log=log, version="20261127T221405Z-ab12cd3")
        app.penguin_log = log
        self.apps.append(app)
        collector = app.extensions["penguin_front"]["collector"]
        collector.start()
        assert collector.collected.wait(BACKSTOP_S), "the collection at start never ended"
        return app

    def stop(self, app):
        """Stop `app` as a deploy does: its pages' streams and its followings end, the slice
        jobs are left to run, and the stand-in goes on."""
        ctx = app.extensions["penguin_front"]
        ctx["collector"].stop()
        ctx["streams"].stop()
        follower = ctx["follower"]
        followed = follower.followed()
        follower.stop()
        for job in followed:  # each following ends when its stream next yields
            self.standin.close_streams(job)
        follower.join()
        self.apps.remove(app)

    def close(self):
        for app in list(self.apps):
            self.stop(app)
            shut(app)


@pytest.fixture
def restarts(tmp_path, clock, standin):
    found = Restarts(tmp_path, clock, standin)
    yield found
    found.close()


def signed_in_client(app):
    client = app.test_client()
    sign_in(client)
    return client


def client_with_cookie_of(app, earlier):
    client = app.test_client()
    client.set_cookie(COOKIE_NAME, earlier.get_cookie(COOKIE_NAME).value)
    return client


def submit(client, plate=PLATE):
    answer = client.post("/api/slices", data=json.dumps(plate), headers=DEV_GROUP)
    assert answer.status_code == 202, answer.get_data(as_text=True)
    return answer.get_json()["slice"]


def wait_for_delete(standin, job):
    standin.changes.wait_for(lambda: requests_to(standin, "DELETE", f"/slices/{job}/file"),
                             f"the delete of {job}'s file")


def state_bucket(app):
    return app.extensions["penguin_front"]["state_bucket"]


# Signed in: the cookie.

def test_a_user_signed_in_before_a_restart_is_still_signed_in(restarts):
    first = signed_in_client(restarts.start())
    assert first.get("/api/me").status_code == 200
    restarts.stop(first.application)
    second = client_with_cookie_of(restarts.start(), first)
    answer = second.get("/api/me")
    assert answer.status_code == 200 and answer.get_json()["user"]["id"] == USER


# Added parts, laid out a plate, chose settings: the browser's storage, untouched. What the
# front server owes it is that the page's repeats after the restart are answered as the
# first attempts were.

def test_a_part_and_a_plate_sent_again_after_a_restart_are_answered_as_before(restarts):
    first = signed_in_client(restarts.start())
    part = first.post("/api/parts?units=mm", data=BRACKET, headers=DEV_GROUP)
    assert part.status_code == 201
    slice_job = submit(first)
    restarts.stop(first.application)
    second = client_with_cookie_of(restarts.start(), first)
    again = second.post("/api/parts?units=mm", data=BRACKET, headers=DEV_GROUP)
    assert (again.status_code, again.get_json()) == (201, part.get_json())
    assert submit(second)["id"] == slice_job["id"]


# A slice job still running: it keeps running, and the front server finds it again.

def test_a_running_slice_job_is_found_again_and_its_page_follows_it(restarts, standin):
    first = signed_in_client(restarts.start())
    job = submit(first)["id"]
    standin.jobs[job].file, standin.jobs[job].summary = FILE, SUMMARY
    standin.report(job, running(job, 2))
    restarts.stop(first.application)
    standin.report(job, running(job, 3))
    app = restarts.start()
    assert job in app.extensions["penguin_front"]["follower"].followed()
    second = client_with_cookie_of(app, first)
    asked = second.get(f"/api/slices/{job}", headers=DEV_GROUP)
    assert asked.status_code == 200 and asked.get_json()["progress"]["sequence"] == 3
    # The page's stream, opened again, follows it to its end.
    reader = Reader(second.get(f"/api/slices/{job}/events", headers=DEV_GROUP,
                               buffered=False))
    reader.wait(lambda r: [p["sequence"] for p in r.progress()] == [3], "the latest report")
    standin.changes.wait_for(lambda: standin.open_streams(job) == 1, "the following's stream")
    standin.report(job, done(job, 4))
    reader.wait_for_end()
    final = reader.progress()[-1]
    assert final["state"] == "done"
    assert final["sliced_file"]["slice"] == job
    record = sliced.read(state_bucket(app), USER, job, Lines())
    assert record["state"] == "stored" and record["group"] == GROUP


def test_a_slice_that_ended_while_the_front_server_was_down_is_stored_when_it_returns(
        restarts, standin, clock):
    first = signed_in_client(restarts.start())
    job = submit(first)["id"]
    restarts.stop(first.application)
    standin.jobs[job].file, standin.jobs[job].summary = FILE, SUMMARY
    clock.advance(30)
    standin.report(job, done(job, 9))
    ended_at = standin.jobs[job].ended_at
    clock.advance(30)
    app = restarts.start()
    wait_for_delete(standin, job)
    record = sliced.read(state_bucket(app), USER, job, Lines())
    assert (record["state"], record["group"], record["slice_ended_at"]) == \
        ("stored", GROUP, ended_at)
    second = client_with_cookie_of(app, first)
    summary = second.get(f"/api/slices/{job}/summary", headers=DEV_GROUP)
    assert summary.status_code == 200
    assert summary.get_json()["sliced_file"]["expires_in_s"] == 7200 - 30


# A finished slice: the state bucket, untouched.

def test_a_finished_slice_is_served_after_a_restart_and_not_fetched_again(restarts, standin,
                                                                          clock):
    first = signed_in_client(restarts.start())
    write_stored(state_bucket(first.application), "jdone",
                 ended_at=sliced.utc(clock.now()))
    standin.add_job("jdone", USER, "plate-9", "submission-9", done("jdone", 41), file=FILE,
                    summary=SUMMARY, ended_at=sliced.utc(clock.now()))
    before = requests_to(standin, "GET", "/slices/jdone/file")
    restarts.stop(first.application)
    second = client_with_cookie_of(restarts.start(), first)
    assert second.get("/api/slices/jdone/summary", headers=DEV_GROUP).status_code == 200
    answer = second.get("/api/slices/jdone/file", headers=DEV_GROUP)
    assert answer.status_code == 200 and answer.get_data() == FILE
    assert requests_to(standin, "GET", "/slices/jdone/file") == before == []
    assert read_state(state_bucket(second.application), "jdone") == "stored"


# Edited the configuration: the state bucket, untouched.

def test_an_edited_configuration_is_read_after_a_restart(restarts):
    first = signed_in_client(restarts.start())
    written = first.put("/api/configuration", headers=DEV_GROUP,
                        data=json.dumps({"based_on": None, "configuration": CONFIGURATION}))
    assert written.status_code == 200
    restarts.stop(first.application)
    second = client_with_cookie_of(restarts.start(), first)
    read = second.get("/api/configuration", headers=DEV_GROUP).get_json()
    assert read["configuration"] == CONFIGURATION
    assert read["revision"] == written.get_json()["revision"]


# Any page was open: its progress stream ends, and opened again on the new front server it
# carries on.

def test_an_open_progress_stream_is_closed_at_the_stop_and_carries_on_when_opened_again(
        restarts, standin):
    first = signed_in_client(restarts.start())
    job = submit(first)["id"]
    reader = Reader(first.get(f"/api/slices/{job}/events", headers=DEV_GROUP,
                              buffered=False))
    reader.wait(lambda r: r.progress(), "the first report")
    restarts.stop(first.application)
    reader.wait_for_end()
    assert first.application.penguin_log.events("stream_closed")[-1]["why"] == "stopping"
    second = client_with_cookie_of(restarts.start(), first)
    again = Reader(second.get(f"/api/slices/{job}/events", headers=DEV_GROUP,
                              buffered=False))
    again.wait(lambda r: r.progress(), "the latest report on the new front server")
    assert again.events()[0][0] == "version"
    standin.changes.wait_for(lambda: standin.open_streams(job) == 1, "the following's stream")
    standin.report(job, running(job, 2))
    again.wait(lambda r: [p["sequence"] for p in r.progress()] == [1, 2], "the next report")
    restarts.stop(second.application)
    again.wait_for_end()
