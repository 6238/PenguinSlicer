"""Asking about a slice job, `GET /api/slices/<slice>` (README-details.md, "Asking about a
slice job"; contracts/wizard-front-server.md, "Asking about a slice job"): one test for each
row of the table, the stand-in and the folder form set up for it on a fake clock."""

import json

import pytest

from penguin_front import sliced
from sliced_helpers import (DONE, ENDED, GROUP, JOB, OTHER, SLICE_DONE, USER, Told,  # noqa: F401
                            app, at, bucket, client, context, done, get, log, queued,
                            read_state, requests_to, running, write_failed, write_stored,
                            write_submitted)


def ask(client, job=JOB, **kwargs):
    return get(client, f"/api/slices/{job}", **kwargs)


def assert_report(answer, code, status):
    assert answer.status_code == status, answer.get_data(as_text=True)
    report = answer.get_json()
    assert report["code"] == code
    assert {"message", "remedy", "retryable", "detail"} <= set(report)
    return report


# Finished.

def test_a_stored_sliced_file_is_answered_finished_exactly_as_the_contracts_example(
        client, bucket, clock, standin):
    write_stored(bucket)
    at(clock, ENDED + 6)
    answer = ask(client)
    assert answer.status_code == 200 and answer.headers["Cache-Control"] == "no-store"
    assert answer.get_json() == SLICE_DONE
    assert requests_to(standin, "GET", f"/slices/{JOB}") == []


def test_a_stored_record_answers_finished_without_the_slice_service(client, bucket, clock,
                                                                   standin):
    write_stored(bucket)
    standin.unreachable()
    at(clock, ENDED + 6)
    assert ask(client).get_json() == SLICE_DONE


# Waiting or running.

def test_a_waiting_slice_job_is_the_slice_services_report_and_is_followed(app, client,
                                                                         standin):
    standin.add_job("j1", USER, "p", "s", queued("j1", ahead=2))
    answer = ask(client, "j1")
    assert answer.status_code == 200
    assert answer.get_json() == {"progress": queued("j1", ahead=2)}
    assert "j1" in context(app)["follower"].followed()


def test_a_running_slice_job_is_its_report(client, standin):
    standin.add_job("j1", USER, "p", "s", running("j1", 5))
    assert ask(client, "j1").get_json() == {"progress": running("j1", 5)}


def test_a_slice_job_ended_whose_file_is_not_yet_stored_is_running(app, client, standin,
                                                                  bucket):
    bucket.refuse_writes = True  # the following cannot store it
    standin.add_job("j1", USER, "p", "s", done("j1", 9), file=b"sliced")
    answer = ask(client, "j1")
    progress = answer.get_json()["progress"]
    assert progress["state"] == "running" and progress["sequence"] == 8
    assert "sliced_file" not in progress
    assert "j1" in context(app)["follower"].followed()


def test_a_following_started_by_asking_carries_the_records_group(app, client, standin,
                                                                 bucket, log):
    # A front server restarted since the submission; the page now has another current group.
    write_submitted(bucket, "j1", "2026-11-27T22:14:05Z", group="earlier-group")
    standin.add_job("j1", USER, "p", "s", queued("j1"), file=b"sliced")
    assert ask(client, "j1").get_json() == {"progress": queued("j1")}
    standin.report("j1", done("j1", 2))
    standin.changes.wait_for(lambda: requests_to(standin, "DELETE", "/slices/j1/file"),
                             "the delete of j1's file")
    record = sliced.read(bucket, USER, "j1", log)
    assert record["state"] == "stored" and record["group"] == "earlier-group"


def test_a_slice_job_followed_already_is_answered_with_the_followings_latest(app, client,
                                                                            standin):
    standin.add_job("j1", USER, "p", "s", queued("j1"))
    follower = context(app)["follower"]
    follower.follow(USER, "j1", GROUP)
    told = Told()
    follower.subscribe(USER, "j1", told)
    standin.changes.wait_for(lambda: standin.open_streams("j1") == 1, "the following's stream")
    standin.report("j1", running("j1", 3))
    told.wait_for(lambda: running("j1", 3) in told.items, "the following's report 3")
    standin.answer_next("GET", "/slices/j1", 200, queued("j1"))  # an older report
    assert ask(client, "j1").get_json() == {"progress": running("j1", 3)}
    assert requests_to(standin, "GET", "/slices/j1") != []


# Ended in an error.

def test_a_failed_slice_is_its_failed_report(client, standin):
    failed = dict(running("j1", 4), state="failed", error={
        "code": "slice.orca_failed", "message": "m", "remedy": "r", "retryable": False,
        "detail": "d"})
    standin.add_job("j1", USER, "p", "s", failed)
    assert ask(client, "j1").get_json() == {"progress": failed}


def test_a_record_of_a_file_over_50_mb_is_ended_in_an_error(client, bucket, standin):
    record = write_failed(bucket)
    answer = ask(client)
    assert answer.status_code == 200
    assert answer.get_json() == {"progress": record["report"]}
    assert requests_to(standin, "GET", f"/slices/{JOB}") == []


# Expired.

def test_a_stored_file_at_its_two_hours_is_expired_and_deleted(client, bucket, clock, log):
    write_stored(bucket)
    at(clock, ENDED + 7200)
    answer = ask(client)
    assert answer.status_code == 200
    progress = answer.get_json()["progress"]
    assert progress["state"] == "failed" and progress["sequence"] == DONE["sequence"] + 1
    assert progress["error"]["code"] == "front.sliced_file_expired"
    assert progress["error"]["retryable"] is False
    assert "sliced_file" not in progress
    assert {k: v for k, v in progress.items() if k not in ("state", "sequence", "error")} == \
        {k: v for k, v in DONE.items() if k not in ("state", "sequence")}
    assert bucket.list(sliced.file_name(USER, JOB)) == []
    assert read_state(bucket) == "expired"
    [line] = log.events("sliced_file_expired")
    assert line["user_key"] == USER and line["group"] == GROUP and line["slice"] == JOB
    assert line["by"] == "request" and line["why"] == "due"


def test_an_expired_record_answers_expired_until_its_extra_day_ends_then_unknown(
        client, bucket, clock):
    write_stored(bucket)
    at(clock, ENDED + 7200)
    expired = ask(client).get_json()
    at(clock, ENDED + 7200 + 86_399)
    assert ask(client).get_json() == expired
    at(clock, ENDED + 7200 + 86_400)
    assert_report(ask(client), "front.slice_unknown", 404)


def test_a_stored_file_removed_by_hand_is_expired(client, bucket, clock, log):
    write_stored(bucket)
    bucket.delete(sliced.file_name(USER, JOB))
    at(clock, ENDED + 6)
    progress = ask(client).get_json()["progress"]
    assert progress["error"]["code"] == "front.sliced_file_expired"
    assert read_state(bucket) == "expired"
    assert log.events("sliced_file_expired")[0]["why"] == "gone"


def test_a_due_file_whose_delete_fails_is_still_answered_expired(client, bucket, clock, log):
    write_stored(bucket)
    bucket.refuse_writes = True
    at(clock, ENDED + 7200)
    progress = ask(client).get_json()["progress"]
    assert progress["error"]["code"] == "front.sliced_file_expired"
    bucket.refuse_writes = False
    assert read_state(bucket) == "stored"  # left for the sweep
    [line] = log.events("sliced_file_expire_failed")
    assert line["slice"] == JOB and "refuses writes" in line["why"]


# Replaced, and cancelled at a stop.

@pytest.mark.parametrize("reason", ["replaced", "shutdown"])
def test_a_cancelled_slice_job_is_its_report_with_its_reason(client, standin, reason):
    cancelled = dict(queued("j1"), state="cancelled", sequence=2, cancel_reason=reason)
    standin.add_job("j1", USER, "p", "s", cancelled)
    assert ask(client, "j1").get_json() == {"progress": cancelled}


# Unknown.

def test_a_slice_job_nobody_knows_is_unknown_and_logged_as_a_refusal(client, log):
    report = assert_report(ask(client, "j1"), "front.slice_unknown", 404)
    assert report["retryable"] is False
    [line] = log.events("refused")
    assert line["reason"] == "slice_unknown" and line["user_key"] == USER
    assert line["group"] == GROUP and line["slice"] == "j1"
    assert log.events("error")[-1]["code"] == "front.slice_unknown"


def test_another_users_slice_job_is_unknown(client, standin, bucket, log):
    standin.add_job("j1", OTHER, "p", "s", running("j1", 2))
    write_stored(bucket, "j2", user=OTHER)
    assert_report(ask(client, "j1"), "front.slice_unknown", 404)
    assert_report(ask(client, "j2"), "front.slice_unknown", 404)
    assert [r.user_key for r in requests_to(standin, "GET", "/slices/j1")] == [USER]
    assert [(line["reason"], line["slice"], line["user_key"])
            for line in log.events("refused")] == [("slice_unknown", "j1", USER),
                                                   ("slice_unknown", "j2", USER)]


def test_another_users_slice_job_followed_here_is_logged_as_another_users(app, client,
                                                                          standin, log):
    standin.add_job("j1", OTHER, "p", "s", running("j1", 2))
    context(app)["follower"].follow(OTHER, "j1", GROUP)
    assert_report(ask(client, "j1"), "front.slice_unknown", 404)
    [line] = log.events("refused")
    assert line["why"] == "another user's slice job"


def test_a_submitted_record_whose_slice_job_the_slice_service_forgot_is_unknown(
        client, bucket):
    write_submitted(bucket, "j1", "2026-11-27T22:14:05Z")
    assert_report(ask(client, "j1"), "front.slice_unknown", 404)


@pytest.mark.parametrize("job", ["a" * 65, "bad.id", "bad%20id", "bad~", "%C3%A9"])
def test_an_id_of_another_form_is_unknown_before_anyone_is_asked(client, standin, job, log):
    assert_report(ask(client, job), "front.slice_unknown", 404)
    assert [r for r in standin.requests if r.path.startswith("/slices")] == []
    [line] = log.events("refused")
    assert line["reason"] == "slice_unknown" and line["why"] == "an id of another form"
    assert line["user_key"] == USER and line["group"] == GROUP


def test_an_id_of_64_characters_is_asked_about(client, standin):
    assert_report(ask(client, "a" * 64), "front.slice_unknown", 404)
    assert len(requests_to(standin, "GET", "/slices/" + "a" * 64)) == 1


# The state bucket and the slice service not answering.

def test_a_state_bucket_that_does_not_answer_is_state_bucket_unreachable(client, bucket,
                                                                         standin):
    write_stored(bucket)
    bucket.refuse_reads = True
    report = assert_report(ask(client), "front.state_bucket_unreachable", 503)
    assert report["retryable"] is True


def test_a_slice_service_that_does_not_answer_with_no_record_is_slice_unreachable(
        client, standin):
    standin.unreachable()
    report = assert_report(ask(client, "j1"), "front.slice_unreachable", 503)
    assert report["retryable"] is True


def test_another_refusal_of_the_slice_service_is_passed_unchanged(client, standin):
    body = {"code": "slice.bad_request", "message": "m", "remedy": "r", "retryable": False,
            "detail": "d"}
    standin.answer_next("GET", "/slices/j1", 400, body)
    answer = ask(client, "j1")
    assert answer.status_code == 400 and json.loads(answer.get_data()) == body


@pytest.mark.parametrize("body", [[1], {"state": 3}, {"job": "j1"}])
def test_an_answer_of_the_slice_service_that_is_not_a_report_is_unexpected(client, standin,
                                                                           body):
    standin.answer_next("GET", "/slices/j1", 200, body)
    assert_report(ask(client, "j1"), "front.unexpected", 500)


def test_asking_needs_a_sign_in_and_the_current_group(app, standin):
    client = app.test_client()
    assert_report(client.get(f"/api/slices/{JOB}"), "front.not_signed_in", 401)
    client.get("/signin")
    assert_report(client.get(f"/api/slices/{JOB}"), "front.group_not_allowed", 403)
    assert standin.requests == []
