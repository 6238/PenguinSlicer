"""Submitting a plate configuration (README-details.md, "Submitting a plate configuration";
contracts/wizard-front-server.md, "`POST /api/slices`"; contracts/slice-http-interface.md,
"`POST /slices`")."""

import io
import json
from pathlib import Path

import pytest

from front_fakes import Announcer
from front_helpers import DEV_GROUP, Lines, environ, front, shut, sign_in
from penguin_front import slices, sliced
from penguin_front.app import create_app
from penguin_front.buckets import BucketUnavailable, FolderBucket
from penguin_front.records import read_record, write_record
from penguin_front.settings import Settings

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"
PLATE = json.loads((EXAMPLES / "plate-configuration-phase-2.json").read_text())
PARTS = {"bracket": (EXAMPLES / "parts" / "bracket.stl").read_bytes(),
         "spacer": (EXAMPLES / "parts" / "spacer.stl").read_bytes()}
OVER_SIZE = json.loads((EXAMPLES / "error-report-plate-configuration-over-size.json")
                       .read_text())
ACCEPTED = json.loads((EXAMPLES / "wizard-front" / "slice-accepted.json").read_text())
STOPPING = (EXAMPLES / "slice-http" / "stopping.json").read_text()


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def app(tmp_path, clock, log, standin):
    app = front(tmp_path, clock, log, PENGUIN_SLICE_URL=standin.url)
    yield app
    shut(app, standin)


@pytest.fixture
def client(app):
    client = app.test_client()
    sign_in(client)
    for body in PARTS.values():
        assert client.post("/api/parts?units=mm", data=body,
                           headers=DEV_GROUP).status_code == 201
    return client


def plate(**changes):
    return {**PLATE, **changes}


def submit(client, body=None, headers=None):
    data = body if isinstance(body, bytes) else json.dumps(body or PLATE).encode()
    return client.post("/api/slices", data=data, content_type="application/json",
                       headers={**DEV_GROUP, **(headers or {})})


def submissions(standin):
    return [r for r in standin.requests if r.method == "POST" and r.path == "/slices"]


def follower(app):
    return app.extensions["penguin_front"]["follower"]


def state_bucket(app):
    return app.extensions["penguin_front"]["state_bucket"]


def raw_submit(client, stream, length, terminated=False):
    overrides = {"wsgi.input": stream,
                 "CONTENT_LENGTH": None if length is None else str(length)}
    if terminated:
        overrides["wsgi.input_terminated"] = True
    return client.post("/api/slices", headers=DEV_GROUP, environ_overrides=overrides)


class Unreadable(io.BytesIO):
    def read(self, *_args):
        raise AssertionError("the body was read")

    readinto = readline = read1 = read


# Accepted.

def test_a_plate_configuration_reaches_the_slice_service_unchanged_with_the_user_key(
        client, standin):
    body = json.dumps(PLATE, indent=1).encode()
    answer = submit(client, body)
    assert answer.status_code == 202
    [sent] = submissions(standin)
    assert sent.body == body and sent.user_key == "dev-user"
    assert sent.headers["content-type"] == "application/json"


def test_the_answer_has_the_contracts_shape_with_the_first_progress_report(client, standin):
    standin.next_job_ids = ["3f9a1c2b"]
    answer = submit(client)
    assert answer.status_code == 202 and answer.headers["Cache-Control"] == "no-store"
    got = answer.get_json()
    assert set(got) == set(ACCEPTED) and set(got["slice"]) == set(ACCEPTED["slice"])
    job = standin.jobs["3f9a1c2b"]
    assert got["slice"] == {"id": "3f9a1c2b", "plate_id": PLATE["plate_id"],
                            "submission_id": PLATE["submission_id"],
                            "progress": job.progress}
    assert got["slice"]["progress"]["state"] == "queued"
    assert got["slice"]["progress"]["ahead"] == 0


def test_a_slice_job_that_started_before_the_answer_reaches_the_page_with_its_latest_report(
        app, client, standin):
    # The slice service answers with its latest report, already `running` when the slice
    # started at once (docs/orchestration/phase-2/seam-front-slice.md, mismatch 1): the page
    # is given that report, and the following passes on only what comes after it.
    standin.starts_at_once = True
    got = submit(client).get_json()["slice"]
    job = standin.jobs[got["id"]]
    assert got["progress"] == job.progress
    assert (got["progress"]["state"], got["progress"]["sequence"]) == ("running", 2)
    standin.changes.wait_for(lambda: standin.open_streams(got["id"]) == 1, "the following's stream")
    standin.report(got["id"], dict(job.progress, stage="slicing", sequence=3))
    asked = client.get(f"/api/slices/{got['id']}", headers=DEV_GROUP).get_json()["progress"]
    assert asked["sequence"] in (2, 3) and asked["state"] == "running"


def test_a_user_key_in_the_body_or_headers_is_never_read(client, standin):
    answer = submit(client, plate(user_key="someone-else"),
                    headers={"X-Penguin-User-Key": "someone-else"})
    assert answer.status_code == 202
    assert [r.user_key for r in submissions(standin)] == ["dev-user"]


def test_a_submission_writes_a_line_with_the_user_key_the_group_and_the_slice_job(client,
                                                                                  log):
    job = submit(client).get_json()["slice"]["id"]
    [line] = log.events("slice_submitted")
    assert line == {"event": "slice_submitted", "user_key": "dev-user", "group": "dev-group",
                    "slice": job, "plate_id": PLATE["plate_id"],
                    "submission_id": PLATE["submission_id"], "state": "queued",
                    "repeat": False}


# The slice job's record and its group.

def test_after_acceptance_the_slice_jobs_record_holds_the_current_group(app, client, clock):
    job = submit(client).get_json()["slice"]["id"]
    record, _ = read_record(state_bucket(app), sliced.record_name("dev-user", job),
                            "sliced_file", Lines())
    assert record == {"format": 1, "slice": job, "group": "dev-group", "state": "submitted",
                      "submitted_at": sliced.utc(clock.now())}


def test_a_record_already_there_is_not_replaced(app, client, standin):
    standin.next_job_ids = ["j1"]
    name = sliced.record_name("dev-user", "j1")
    write_record(state_bucket(app), name, "sliced_file", {"slice": "j1", "state": "stored"})
    assert submit(client).status_code == 202
    record, _ = read_record(state_bucket(app), name, "sliced_file", Lines())
    assert record["state"] == "stored"


SLICED = b"a sliced file of the stand-in's"


def end_done(app, standin, job):
    """Give the stand-in's slice job a sliced file, end it `done`, and wait until its
    following has ended; gives the slice job's record."""
    standin.jobs[job].file = SLICED
    standin.jobs[job].summary = json.loads((EXAMPLES / "sliced-file.json").read_text())
    standin.changes.wait_for(lambda: standin.open_streams(job) == 1, "the following's stream")
    seen, told = [], Announcer()

    def deliver(report):
        seen.append(report)
        told.announce()

    assert follower(app).subscribe("dev-user", job, deliver) is not None
    standin.report(job, {"job": job, "state": "done", "stage": "reading_result",
                         "stage_label": "Reading the sliced file", "fraction": 1.0,
                         "elapsed_s": 52.8, "expected_s": 75, "sequence": 2})
    told.wait_for(lambda: None in seen, "the following's end")
    assert seen[-2]["state"] == "done"
    record, _ = read_record(state_bucket(app), sliced.record_name("dev-user", job),
                            "sliced_file", Lines())
    return record


def test_the_submissions_group_reaches_the_stored_record_and_the_followings_lines(
        app, client, standin, log):
    job = submit(client).get_json()["slice"]["id"]
    record = end_done(app, standin, job)
    assert record["state"] == "stored" and record["group"] == "dev-group"
    assert [line["group"] for line in log.events("slice_followed")] == ["dev-group"]
    assert {line["group"] for line in log.events("sliced_file_stored")} == {"dev-group"}


def test_a_record_that_cannot_be_written_is_no_error_for_the_page(tmp_path, clock, log,
                                                                  standin):
    class Refusing(FolderBucket):
        refuse = True

        def put(self, name, data, **condition):
            if self.refuse:
                raise BucketUnavailable("the state bucket refuses writes, by the test")
            return super().put(name, data, **condition)

    bucket = Refusing(tmp_path / "state", clock)
    app = create_app(Settings.from_environ(environ(tmp_path, PENGUIN_SLICE_URL=standin.url)),
                     clock=clock, log=log, state_bucket=bucket)
    try:
        client = app.test_client()
        sign_in(client)
        for body in PARTS.values():
            client.post("/api/parts?units=mm", data=body, headers=DEV_GROUP)
        answer = submit(client)
        assert answer.status_code == 202
        job = answer.get_json()["slice"]["id"]
        [line] = log.events("slice_record_unwritten")
        assert line["slice"] == job and line["group"] == "dev-group"
        assert "refuses writes" in line["why"]
        assert job in follower(app).followed()
        # The group lives in the following's memory only, and still reaches the record
        # written when the sliced file is stored.
        bucket.refuse = False
        record = end_done(app, standin, job)
        assert record["state"] == "stored" and record["group"] == "dev-group"
        assert [line["group"] for line in log.events("slice_followed")] == ["dev-group"]
    finally:
        shut(app, standin)


# Followed.

def test_an_accepted_slice_job_is_followed(app, client, standin):
    job = submit(client).get_json()["slice"]["id"]
    assert job in follower(app).followed()
    standin.changes.wait_for(lambda: standin.open_streams(job) == 1, "the following's stream")


def test_two_plates_of_one_user_give_two_slice_jobs_both_followed(app, client, standin):
    first = submit(client).get_json()["slice"]["id"]
    second = submit(client, plate(plate_id="another-plate",
                                  submission_id="another-submission")).get_json()["slice"]["id"]
    assert first != second
    assert {first, second} <= follower(app).followed()
    assert not standin.jobs[first].ended


def test_a_later_submission_of_the_same_plate_leaves_the_earlier_followed_to_its_end(
        app, client, standin):
    first = submit(client).get_json()["slice"]["id"]
    seen, told = [], Announcer()

    def deliver(report):
        seen.append(report)
        told.announce()

    standin.changes.wait_for(lambda: standin.open_streams(first) == 1, "the first stream")
    follower(app).subscribe("dev-user", first, deliver)
    second = submit(client, plate(submission_id="a-new-submission")).get_json()["slice"]["id"]
    told.wait_for(lambda: None in seen, "the first slice job's following ending")
    assert seen[-2]["state"] == "cancelled" and seen[-2]["cancel_reason"] == "replaced"
    assert first not in follower(app).followed() and second in follower(app).followed()


def test_a_repeat_answers_the_first_attempts_slice_job_and_one_is_followed(app, client,
                                                                           standin, log):
    first = submit(client).get_json()
    again = submit(client)
    assert again.status_code == 202 and again.get_json()["slice"]["id"] == first["slice"]["id"]
    assert follower(app).followed() == {first["slice"]["id"]}
    assert len(standin.jobs) == 1
    assert [line["repeat"] for line in log.events("slice_submitted")] == [False, True]
    assert len(log.events("slice_followed")) == 1


# A repeat of a slice job that ended done: the 202 carries the slice service's done report,
# which the page sees as the front server's pages see it (contracts/wizard-front-server.md,
# "The reports the front server passes").

def done_report(job, sequence):
    return {"job": job, "state": "done", "stage": "reading_result",
            "stage_label": "Reading the sliced file", "fraction": 1.0, "elapsed_s": 52.8,
            "expected_s": 75, "sequence": sequence}


def accepted_done(job, sequence):
    return {"job": job, "plate_id": PLATE["plate_id"], "submission_id": PLATE["submission_id"],
            "progress": done_report(job, sequence), "part_warnings": []}


def test_a_repeat_answered_done_with_no_stored_file_is_held_back(client, standin):
    # The slice job is one the stand-in does not know, so its following ends at once and
    # nothing is stored while the answer is made.
    standin.answer_next("POST", "/slices", 202, accepted_done("jdone1", 9))
    answer = submit(client)
    assert answer.status_code == 202
    progress = answer.get_json()["slice"]["progress"]
    assert progress["state"] == "running" and progress["sequence"] == 8
    assert "sliced_file" not in progress


def test_a_repeat_answered_done_with_a_stored_file_is_done_with_the_sliced_file(app, client,
                                                                                 standin,
                                                                                 clock):
    write_record(state_bucket(app), sliced.record_name("dev-user", "jdone2"), "sliced_file", {
        "slice": "jdone2", "group": "dev-group", "state": "stored", "file": "x.gcode.3mf",
        "size_bytes": 3, "summary": {"file": "x.gcode.3mf"},
        "slice_ended_at": sliced.utc(clock.now()), "report": done_report("jdone2", 9)})
    standin.answer_next("POST", "/slices", 202, accepted_done("jdone2", 9))
    progress = submit(client).get_json()["slice"]["progress"]
    assert progress["state"] == "done" and progress["sequence"] == 9
    assert progress["sliced_file"]["slice"] == "jdone2"
    assert progress["sliced_file"]["expires_in_s"] == 7200


def test_a_repeat_answered_done_while_followed_is_the_followings_latest_report(app, client,
                                                                               standin):
    running = {"job": "jdone3", "state": "running", "stage": "slicing",
               "stage_label": "Slicing", "elapsed_s": 5, "expected_s": 75, "sequence": 5}
    standin.add_job("jdone3", "dev-user", PLATE["plate_id"], PLATE["submission_id"], running)
    follower(app).follow("dev-user", "jdone3", "dev-group")
    told = Announcer()
    subscription = follower(app).subscribe("dev-user", "jdone3", lambda _r: told.announce())
    told.wait_for(lambda: follower(app).latest("dev-user", "jdone3") is not None,
                  "the following's first report")
    subscription.cancel()
    standin.answer_next("POST", "/slices", 202, accepted_done("jdone3", 9))
    progress = submit(client).get_json()["slice"]["progress"]
    assert progress == running


def test_no_submission_reaches_the_slice_services_cancel(client, standin):
    submit(client)
    submit(client, plate(submission_id="a-new-submission"))
    submit(client, plate(plate_id="p2", submission_id="s2"))
    assert standin.cancels() == []


# Refusals of the slice service, passed unchanged.

def test_parts_missing_from_the_part_store_reach_the_page_with_where_missing_parts(app,
                                                                                   standin):
    client = app.test_client()
    sign_in(client)
    answer = submit(client)
    assert answer.status_code == 422
    report = answer.get_json()
    assert report["code"] == "slice.part_missing"
    assert {p["key"] for p in report["where"]["missing_parts"]} == {"bracket", "spacer"}


@pytest.mark.parametrize("code, status", [
    ("slice.bad_plate_configuration", 400), ("slice.too_many_instances", 422),
    ("slice.too_many_parts", 422), ("slice.unknown_printer", 422),
    ("slice.profiles_not_offered", 422), ("slice.bad_overrides", 422),
    ("slice.part_too_large", 422), ("slice.placement_off_plate", 422),
    ("slice.placement_too_tall", 422), ("slice.placement_too_close", 422),
    ("slice.profile_unreadable", 422), ("slice.scratch_unwritable", 500),
    ("slice.unexpected", 500),
])
def test_each_refusal_of_the_plate_reaches_the_page_unchanged(app, client, standin, log,
                                                              code, status):
    report = {"code": code, "message": "m", "where": {"stage": "checking"}, "remedy": "r",
              "retryable": False, "detail": "d"}
    standin.answer_next("POST", "/slices", status, report)
    answer = submit(client)
    assert answer.status_code == status and answer.data == json.dumps(report).encode()
    assert log.events("error")[-1]["code"] == code
    assert follower(app).followed() == set()


def test_the_busy_answer_reaches_the_page_unchanged(app, client, standin):
    for n in range(3):
        assert submit(client, plate(plate_id=f"p{n}", submission_id=f"s{n}")).status_code == 202
    answer = submit(client, plate(plate_id="p3", submission_id="s3"))
    assert answer.status_code == 503
    report = answer.get_json()
    assert report["code"] == "slice.busy" and report["retryable"] is True


def test_the_stopping_answer_is_passed_unchanged_never_busy_or_unreachable(client, standin):
    standin.stopping = True
    answer = submit(client)
    assert answer.status_code == 503
    assert answer.get_json() == json.loads(STOPPING)
    assert answer.get_json()["code"] == "slice.stopping"
    assert answer.headers.get("Retry-After") is None


def test_a_repeat_while_stopping_is_answered_with_its_slice_job(client, standin):
    first = submit(client).get_json()["slice"]["id"]
    standin.stopping = True
    again = submit(client)
    assert again.status_code == 202 and again.get_json()["slice"]["id"] == first


def test_the_slice_services_no_user_key_is_the_front_servers_fault(client, standin):
    no_key = json.loads((EXAMPLES / "slice-http" / "no-user-key.json").read_text())
    standin.answer_next("POST", "/slices", 400, no_key)
    answer = submit(client)
    assert answer.status_code == 500 and answer.get_json()["code"] == "front.unexpected"


@pytest.mark.parametrize("accepted", [
    {"plate_id": "p", "submission_id": "s", "progress": {}},
    {"job": "not an id!", "plate_id": "p", "submission_id": "s", "progress": {}},
    {"job": "j1", "plate_id": "p", "submission_id": "s", "progress": []},
    ["a list"],
])
def test_an_acceptance_of_the_wrong_shape_is_unexpected(app, client, standin, accepted):
    standin.answer_next("POST", "/slices", 202, accepted)
    answer = submit(client)
    assert answer.status_code == 500 and answer.get_json()["code"] == "front.unexpected"
    assert follower(app).followed() == set()


def test_an_acceptance_that_is_not_json_is_unexpected(app, standin):
    @standin.app.before_request
    def odd():
        from flask import Response

        return Response(b"<html>", 202)

    client = app.test_client()
    sign_in(client)
    assert submit(client).get_json()["code"] == "front.unexpected"


def test_the_slice_service_not_answering_is_front_slice_unreachable(client, standin):
    standin.unreachable()
    answer = submit(client)
    assert answer.status_code == 503
    assert answer.get_json()["code"] == "front.slice_unreachable"


# The size.

def test_a_body_over_one_megabyte_is_refused_before_it_is_read(client, standin):
    answer = raw_submit(client, Unreadable(), 1_048_577)
    assert answer.status_code == 413
    assert list(answer.get_json().items()) == list(OVER_SIZE.items())
    assert submissions(standin) == []


def test_a_body_of_exactly_one_megabyte_passes(client, standin):
    body = json.dumps(PLATE).encode()
    body += b" " * (slices.MAX_PLATE_CONFIGURATION_BYTES - len(body))
    assert len(body) == 1_048_576
    assert submit(client, body).status_code == 202
    assert submissions(standin)[0].body == body


def test_a_body_without_content_length_is_read_only_to_the_limit(client, standin):
    answer = raw_submit(client, io.BytesIO(b" " * 1_048_577), None, terminated=True)
    assert answer.status_code == 413
    report = answer.get_json()
    assert report["code"] == "slice.bad_plate_configuration"
    assert report["message"] == OVER_SIZE["message"]
    assert "without Content-Length" in report["detail"]
    assert submissions(standin) == []


def test_a_body_without_content_length_under_the_limit_passes(client, standin):
    body = json.dumps(PLATE).encode()
    answer = raw_submit(client, io.BytesIO(body), None, terminated=True)
    assert answer.status_code == 202 and submissions(standin)[0].body == body


def test_a_body_that_is_not_json_is_the_slice_services_to_refuse(client, standin):
    answer = submit(client, b"not json")
    assert answer.status_code == 400
    assert answer.get_json()["code"] == "slice.bad_plate_configuration"


# Signed in, and the group.

def test_a_submission_without_a_sign_in_is_refused_and_nothing_is_sent(app, standin):
    answer = app.test_client().post("/api/slices", json=PLATE, headers=DEV_GROUP)
    assert answer.status_code == 401 and submissions(standin) == []


def test_a_submission_for_a_group_not_the_users_is_refused_and_nothing_is_sent(client,
                                                                              standin):
    answer = submit(client, headers={"X-PenguinSlicer-Group": "a-group-of-nobody"})
    assert answer.status_code == 403 and submissions(standin) == []


# How fast.

def test_the_limit_is_30_submissions_a_minute_for_each_user():
    assert slices.SUBMISSIONS_PER_MINUTE == 30


def test_past_the_limit_a_submission_is_too_many_requests_with_retry_after(
        tmp_path, clock, log, standin, monkeypatch):
    monkeypatch.setattr(slices, "SUBMISSIONS_PER_MINUTE", 2)
    app = front(tmp_path, clock, log, PENGUIN_SLICE_URL=standin.url)
    try:
        client = app.test_client()
        sign_in(client)
        for body in PARTS.values():
            client.post("/api/parts?units=mm", data=body, headers=DEV_GROUP)
        assert submit(client).status_code == 202
        clock.advance(20)
        assert submit(client).status_code == 202
        refused = submit(client)
        assert refused.status_code == 429
        assert refused.get_json()["code"] == "front.too_many_requests"
        assert refused.headers["Retry-After"] == "40"
        assert len(submissions(standin)) == 2
        clock.advance(40)
        assert submit(client).status_code == 202
    finally:
        shut(app, standin)


def test_a_submission_refused_for_its_size_does_not_count(tmp_path, clock, log, standin,
                                                          monkeypatch):
    monkeypatch.setattr(slices, "SUBMISSIONS_PER_MINUTE", 2)
    app = front(tmp_path, clock, log, PENGUIN_SLICE_URL=standin.url)
    try:
        client = app.test_client()
        sign_in(client)
        for body in PARTS.values():
            client.post("/api/parts?units=mm", data=body, headers=DEV_GROUP)
        for _ in range(3):
            assert raw_submit(client, Unreadable(), 1_048_577).status_code == 413
        assert submit(client).status_code == 202
        assert submit(client, plate(plate_id="p2", submission_id="s2")).status_code == 202
        assert submit(client, plate(plate_id="p3", submission_id="s3")).status_code == 429
    finally:
        shut(app, standin)
