"""The sliced file's details and the sliced file, `GET /api/slices/<slice>/summary` and
`/file` (README-details.md, "The sliced file's details and the sliced file";
contracts/wizard-front-server.md, "The sliced file")."""

import pytest

from front_helpers import DEV_GROUP, Lines, environ, shut, sign_in
from penguin_front import sliced
from penguin_front.app import create_app
from penguin_front.settings import Settings
from sliced_helpers import (ENDED, ENDED_AT, FILE, GROUP, JOB, OTHER, SLICE_SUMMARY,  # noqa: F401
                            SUMMARY, USER, Failing, Told, app, at, bucket, client, context,
                            done, get, log, read_state, requests_to, running, write_failed,
                            write_stored)


def summary(client, job=JOB):
    return get(client, f"/api/slices/{job}/summary")


def file(client, job=JOB, **kwargs):
    """The file, read whole and closed, as a server closes an answer it has sent, unless
    `buffered=False`."""
    return get(client, f"/api/slices/{job}/file", **{"buffered": True, **kwargs})


def code(answer):
    return answer.status_code, answer.get_json()["code"]


# The details.

def test_the_details_of_a_stored_file_are_the_contracts_example(client, bucket, clock):
    write_stored(bucket)
    at(clock, ENDED + 793)
    answer = summary(client)
    assert answer.status_code == 200 and answer.headers["Cache-Control"] == "no-store"
    assert answer.get_json() == SLICE_SUMMARY


def test_expires_in_s_is_expires_at_less_now(client, bucket, clock):
    write_stored(bucket)
    for moment in (ENDED, ENDED + 1, ENDED + 7199):
        at(clock, moment)
        details = summary(client).get_json()["sliced_file"]
        assert details["expires_at"] == sliced.utc(ENDED + 7200)
        assert details["expires_in_s"] == ENDED + 7200 - moment
        assert set(details) == set(SLICE_SUMMARY["sliced_file"])


# The refusals of both requests.

REQUESTS = [summary, file]


@pytest.mark.parametrize("request_", REQUESTS)
def test_a_slice_job_still_running_is_not_ready(client, standin, request_):
    standin.add_job("j1", USER, "p", "s", running("j1", 3))
    assert code(request_(client, "j1")) == (409, "front.sliced_file_not_ready")


@pytest.mark.parametrize("request_", REQUESTS)
def test_a_slice_job_ended_whose_file_is_not_yet_stored_is_not_ready(client, standin,
                                                                    bucket, request_):
    bucket.refuse_writes = True
    standin.add_job("j1", USER, "p", "s", done("j1", 9), file=b"sliced")
    assert code(request_(client, "j1")) == (409, "front.sliced_file_not_ready")


@pytest.mark.parametrize("request_", REQUESTS)
def test_a_sliced_file_over_the_limit_has_no_file_and_is_not_ready(client, bucket,
                                                                  request_):
    write_failed(bucket)
    assert code(request_(client)) == (409, "front.sliced_file_not_ready")


@pytest.mark.parametrize("request_", REQUESTS)
def test_a_due_file_is_expired(client, bucket, clock, request_):
    write_stored(bucket)
    at(clock, ENDED + 7200)
    assert code(request_(client)) == (410, "front.sliced_file_expired")
    assert read_state(bucket) == "expired"
    assert code(request_(client)) == (410, "front.sliced_file_expired")


@pytest.mark.parametrize("request_", REQUESTS)
def test_a_file_removed_from_the_folder_by_hand_is_expired(client, bucket, clock, request_):
    write_stored(bucket)
    bucket.delete(sliced.file_name(USER, JOB))
    assert code(request_(client)) == (410, "front.sliced_file_expired")


@pytest.mark.parametrize("request_", REQUESTS)
def test_another_users_sliced_file_is_unknown(client, bucket, standin, request_):
    write_stored(bucket, user=OTHER)
    standin.add_job("j1", OTHER, "p", "s", done("j1", 9))
    assert code(request_(client)) == (404, "front.slice_unknown")
    assert code(request_(client, "j1")) == (404, "front.slice_unknown")


@pytest.mark.parametrize("request_", REQUESTS)
def test_a_cancelled_slice_job_has_no_sliced_file(client, standin, request_):
    standin.add_job("j1", USER, "p", "s",
                    dict(running("j1", 3), state="cancelled", cancel_reason="replaced"))
    assert code(request_(client, "j1")) == (409, "front.sliced_file_not_ready")


@pytest.mark.parametrize("request_", REQUESTS)
def test_a_state_bucket_that_does_not_answer_is_unreachable(client, bucket, request_):
    write_stored(bucket)
    bucket.refuse_reads = True
    assert code(request_(client)) == (503, "front.state_bucket_unreachable")


# The file.

def test_the_file_is_the_state_buckets_copy_after_the_stand_in_deleted_its_own(
        app, client, standin, clock, log):
    standin.add_job("j1", USER, "p", "s", running("j1", 2), file=FILE, summary=SUMMARY)
    follower = context(app)["follower"]
    told = Told()
    follower.follow(USER, "j1", GROUP)
    follower.subscribe(USER, "j1", told)
    standin.changes.wait_for(lambda: standin.open_streams("j1") == 1, "the following's stream")
    standin.report("j1", done("j1", 3))
    told.wait_for(lambda: None in told.items, "the following's end")
    assert standin.jobs["j1"].file is None  # the stand-in deleted its copy
    answer = file(client, "j1")
    assert answer.status_code == 200
    assert answer.get_data() == FILE
    assert answer.headers["Content-Type"] == "application/octet-stream"
    assert answer.headers["Content-Length"] == str(len(FILE))
    assert answer.headers["Content-Disposition"] == \
        f'attachment; filename="{SUMMARY["file"]}"'
    assert answer.headers["Cache-Control"] == "no-store"
    assert requests_to(standin, "GET", "/slices/j1/file")  # fetched once, by the following
    [line] = log.events("sliced_file_served")
    assert line == {"event": "sliced_file_served", "user_key": USER, "group": GROUP,
                    "slice": "j1", "size_bytes": len(FILE), "sent_bytes": len(FILE),
                    "whole": True}


def test_with_the_group_in_the_query_alone_the_file_is_served(client, bucket):
    write_stored(bucket)
    answer = client.get(f"/api/slices/{JOB}/file?group={GROUP}", buffered=True)
    assert answer.status_code == 200 and answer.get_data() == FILE


def test_a_file_name_of_another_form_is_offered_under_the_slice_jobs_id(client, bucket):
    write_stored(bucket, summary=dict(SUMMARY, file='a"; b.gcode.3mf'))
    answer = file(client)
    assert answer.headers["Content-Disposition"] == f'attachment; filename="{JOB}.gcode.3mf"'


def test_a_fetch_cut_off_is_logged_as_not_whole(client, bucket, log):
    bucket.chunk_bytes = 1024
    write_stored(bucket)
    answer = file(client, buffered=False)
    next(iter(answer.response))
    answer.close()
    [line] = log.events("sliced_file_served")
    assert line["whole"] is False and line["sent_bytes"] < len(FILE)


def test_a_file_gone_between_the_check_and_the_read_is_expired(client, bucket, monkeypatch):
    write_stored(bucket)
    monkeypatch.setattr(sliced, "file_present", lambda *_args: True)
    bucket.delete(sliced.file_name(USER, JOB))
    assert code(file(client)) == (410, "front.sliced_file_expired")
    assert read_state(bucket) == "expired"


def test_a_file_that_cannot_be_read_is_unreachable(client, bucket, monkeypatch):
    write_stored(bucket)
    real_open = bucket.open

    def failing(name):
        if name.endswith(".gcode.3mf"):
            bucket.refuse_reads = True
        return real_open(name)

    monkeypatch.setattr(bucket, "open", failing)
    assert code(file(client)) == (503, "front.state_bucket_unreachable")


def test_a_file_larger_than_the_memory_chunk_passes_through_in_pieces(tmp_path, clock,
                                                                     standin):
    small = Failing(tmp_path / "state", clock)
    small.chunk_bytes = 1024
    app = create_app(Settings.from_environ(environ(tmp_path, PENGUIN_SLICE_URL=standin.url)),
                     clock=clock, log=Lines(), state_bucket=small)
    try:
        client = app.test_client()
        sign_in(client)
        write_stored(small)
        answer = client.get(f"/api/slices/{JOB}/file", headers=DEV_GROUP, buffered=False)
        pieces = list(answer.response)
        answer.close()
        assert b"".join(pieces) == FILE
        assert len(pieces) == len(FILE) // 1024 and max(map(len, pieces)) == 1024
    finally:
        shut(app, standin)


def test_a_head_of_the_file_gives_its_headers_and_closes_it(client, bucket, log):
    write_stored(bucket)
    answer = client.head(f"/api/slices/{JOB}/file", headers=DEV_GROUP, buffered=True)
    assert answer.status_code == 200 and answer.get_data() == b""
    assert answer.headers["Content-Length"] == str(len(FILE))
    assert log.events("sliced_file_served")[0]["sent_bytes"] == 0
