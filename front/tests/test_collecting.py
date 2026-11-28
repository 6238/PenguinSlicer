"""Collecting at start: the slice jobs the slice service holds, followed again or collected
(README-details.md, "Starting, and what a restart does").

Every test puts the stand-in's slice jobs in place before the collection runs, and waits on
events: the collection ending, a request reaching the stand-in, the collection parking on
the fake clock. None waits a number of seconds."""

import pytest

from front_fakes import BACKSTOP_S
from front_helpers import DEV_GROUP
from penguin_front import sliced
from penguin_front.collecting import Collector
from test_following import Recording
from sliced_helpers import (FILE, GROUP, SUMMARY, USER, app, bucket, client, context,  # noqa: F401
                            done, log, queued, read_state, requests_to, running,
                            write_stored, write_submitted)

#: When the slice service says the finished slice job ended: before the clock's start.
LISTED_END = "2026-11-27T22:13:58Z"


def collector(app):
    return context(app)["collector"]


def collect(app):
    """Run the collection on its own thread and wait for it to end."""
    found = collector(app)
    found.start()
    assert found.collected.wait(BACKSTOP_S), "the collection never ended"
    return found


def wait_for_delete(standin, job):
    standin.changes.wait_for(lambda: requests_to(standin, "DELETE", f"/slices/{job}/file"),
                             f"the delete of {job}'s file")


def add_done(standin, job, *, user=USER, file=FILE, ended_at=LISTED_END, state="done"):
    report = dict(done(job, 9), state=state) if state != "done" else done(job, 9)
    return standin.add_job(job, user, f"plate-{job}", f"submission-{job}", report,
                           file=file, summary=SUMMARY, ended_at=ended_at)


def test_the_unfinished_is_followed_and_the_finished_unstored_stored_with_its_records_group(
        app, standin, bucket, log):
    standin.add_job("jrun", USER, "plate-run", "submission-run", running("jrun", 4))
    add_done(standin, "jdone")
    write_submitted(bucket, "jrun", "2026-11-27T22:00:00Z", group="group-of-run")
    write_submitted(bucket, "jdone", "2026-11-27T22:00:00Z", group="group-of-done")
    collect(app)
    wait_for_delete(standin, "jdone")
    record = sliced.read(bucket, USER, "jdone", log)
    assert record["state"] == "stored" and record["group"] == "group-of-done"
    # The two hours count from when the slice service says the slice ended.
    assert record["slice_ended_at"] == LISTED_END
    assert bucket.get(sliced.file_name(USER, "jdone"))[0] == FILE
    follower = context(app)["follower"]
    assert "jrun" in follower.followed()
    [followed] = [line for line in log.events("slice_followed") if line["slice"] == "jrun"]
    assert followed["group"] == "group-of-run" and followed["user_key"] == USER
    [line] = log.events("slices_collected")
    assert (line["listed"], line["followed"], line["collecting"]) == (2, 1, 1)


def test_a_slice_job_with_no_record_is_followed_without_a_group(app, standin, bucket, log):
    add_done(standin, "jdone")
    collect(app)
    wait_for_delete(standin, "jdone")
    assert sliced.read(bucket, USER, "jdone", log)["group"] is None


def test_a_finished_slice_job_already_stored_is_not_fetched_again(app, standin, bucket, log):
    write_stored(bucket, "jkept")
    add_done(standin, "jkept")
    # Stored, and the slice service has deleted its copy: nothing is asked about it.
    write_stored(bucket, "jgone")
    add_done(standin, "jgone", file=None)
    collect(app)
    # The slice service still holds a copy of the first: it is told to delete it, and the
    # file is fetched no more.
    wait_for_delete(standin, "jkept")
    for job in ("jkept", "jgone"):
        assert not requests_to(standin, "GET", f"/slices/{job}/file")
        assert not requests_to(standin, "GET", f"/slices/{job}/summary")
    assert not [r for r in standin.requests if "jgone" in r.path]
    assert read_state(bucket, "jkept") == "stored"
    [line] = log.events("slices_collected")
    assert (line["already_stored"], line["left"]) == (1, 1)


@pytest.mark.parametrize("state", ["failed", "cancelled"])
def test_a_slice_job_that_did_not_end_done_is_left_alone(app, standin, state, log):
    add_done(standin, "jend", file=None, state=state)
    collect(app)
    assert not [r for r in standin.requests if "jend" in r.path]
    assert log.events("slices_collected")[0]["left"] == 1


def test_a_finished_slice_job_whose_record_has_expired_is_not_stored_again(app, standin,
                                                                             bucket, log):
    from penguin_front.records import write_record

    record = write_stored(bucket, "jold")
    write_record(bucket, sliced.record_name(USER, "jold"), sliced.KIND,
                 dict(record, state="expired", expired_at=LISTED_END))
    bucket.delete(sliced.file_name(USER, "jold"))
    add_done(standin, "jold")
    collect(app)
    assert not [r for r in standin.requests if "jold" in r.path]
    assert read_state(bucket, "jold") == "expired"


def test_a_slice_job_followed_already_is_not_followed_twice(app, standin, log):
    standin.add_job("jrun", USER, "plate-run", "submission-run", queued("jrun"))
    context(app)["follower"].follow(USER, "jrun", GROUP)
    collect(app)
    assert len([line for line in log.events("slice_followed")
                if line["slice"] == "jrun"]) == 1
    assert log.events("slices_collected")[0]["followed"] == 0


@pytest.mark.parametrize("ended_at", ["yesterday", "2026-13-40T25:00:00Z", None])
def test_an_end_time_of_another_form_counts_the_two_hours_from_when_it_is_heard(
        app, standin, bucket, clock, log, ended_at):
    add_done(standin, "jdone", ended_at=ended_at)
    collect(app)
    wait_for_delete(standin, "jdone")
    assert sliced.read(bucket, USER, "jdone", log)["slice_ended_at"] == sliced.utc(clock.now())


@pytest.mark.parametrize("entry", [
    "not an object", {"job": "j/../x", "user_key": USER, "progress": {"state": "done"}},
    {"job": "jx", "user_key": "", "progress": {"state": "done"}},
    {"job": "jx", "user_key": USER, "progress": "done"},
    {"job": "jx", "user_key": USER, "progress": {"state": 3}},
    {"job": "jx", "user_key": "a/b", "progress": {"state": "running"}},
])
def test_an_entry_the_front_server_cannot_read_is_skipped_with_a_line(app, standin, log,
                                                                      entry):
    standin.answer_next("GET", "/slices", 200, {"slices": [entry]})
    collect(app)
    [line] = log.events("slices_entry_unreadable")
    assert "entry" in line
    assert log.events("slices_collected")[0]["unreadable"] == 1
    assert context(app)["follower"].followed() == set()


@pytest.fixture
def clock():
    return Recording()


def wait_for_retry(clock, log, count):
    """Wait until the collection's next wait has begun, its retry line written before it;
    there are then `count` retry lines."""
    clock.next_wait()
    assert len(log.events("slices_list_retry")) == count


def test_a_start_while_the_slice_service_does_not_answer_keeps_asking_and_serves_meanwhile(
        app, client, standin, clock, log):
    standin.add_job("jrun", USER, "plate-run", "submission-run", running("jrun", 4))
    standin.unreachable()
    found = collector(app)
    found.start()
    wait_for_retry(clock, log, 1)
    # Other requests are answered while it waits.
    assert client.get("/api/me").status_code == 200
    answer = client.get("/api/settings-table", headers=DEV_GROUP)
    assert answer.get_json()["code"] == "front.slice_unreachable"
    clock.advance(1)
    wait_for_retry(clock, log, 2)
    assert [line["wait_s"] for line in log.events("slices_list_retry")] == [1, 2]
    assert not found.collected.is_set()
    standin.reachable()
    clock.advance(2)
    assert found.collected.wait(BACKSTOP_S)
    assert "jrun" in context(app)["follower"].followed()


def test_the_waits_between_askings_grow_to_thirty_seconds(app, standin, clock, log):
    standin.unreachable()
    collector(app).start()
    for n, wait in enumerate([1, 2, 4, 8, 16, 30, 30], start=1):
        wait_for_retry(clock, log, n)
        assert log.events("slices_list_retry")[-1]["wait_s"] == wait
        clock.advance(wait)
    standin.reachable()


@pytest.mark.parametrize("status, body, why", [
    (500, {"code": "slice.unexpected"}, "answered 500"),
    (200, {"slices": "none"}, "not a list"),
    (200, ["no object"], "not a list"),
])
def test_an_answer_that_is_not_the_list_is_asked_again(app, standin, clock, log, status,
                                                        body, why):
    standin.add_job("jrun", USER, "plate-run", "submission-run", running("jrun", 4))
    standin.answer_next("GET", "/slices", status, body)
    found = collector(app)
    found.start()
    wait_for_retry(clock, log, 1)
    assert why in log.events("slices_list_retry")[0]["why"]
    clock.advance(1)
    assert found.collected.wait(BACKSTOP_S)
    assert "jrun" in context(app)["follower"].followed()


def test_a_state_bucket_that_does_not_answer_is_asked_again(app, standin, bucket, clock, log):
    add_done(standin, "jdone")
    write_submitted(bucket, "jdone", "2026-11-27T22:00:00Z", group="group-of-done")
    bucket.refuse_reads = True
    found = collector(app)
    found.start()
    wait_for_retry(clock, log, 1)
    assert "refuses reads" in log.events("slices_list_retry")[0]["why"]
    assert context(app)["follower"].followed() == set()
    bucket.refuse_reads = False
    clock.advance(1)
    assert found.collected.wait(BACKSTOP_S)
    wait_for_delete(standin, "jdone")
    assert sliced.read(bucket, USER, "jdone", log)["group"] == "group-of-done"


def test_a_stop_while_it_waits_ends_the_collection(app, standin, clock, log):
    standin.unreachable()
    found = collector(app)
    found.start()
    wait_for_retry(clock, log, 1)
    found.stop()
    assert not found.collected.is_set()
    assert len(log.events("slices_list_retry")) == 1


def test_a_stop_before_the_start_collects_nothing(app, standin):
    found = collector(app)
    found.stop()
    found.start()
    found.stop()
    assert not requests_to(standin, "GET", "/slices")


def test_a_collector_never_started_stops_at_once(clock, log):
    Collector(clock=clock, slice_client=None, bucket=None, follower=None, log=log).stop()
