"""The two-hour rule: refusing, deleting and the sweep (README-details.md, "Two hours, the
sweep, and the backstop"), all on a fake clock; none waits."""

import pytest

from front_fakes import START
from front_helpers import Lines, environ, shut
from penguin_front import sliced, sweep
from penguin_front.app import create_app
from penguin_front.every import Every
from penguin_front.settings import Settings
from sliced_helpers import (ENDED, ENDED_AT, FILE, GROUP, JOB, USER, app, at,  # noqa: F401
                            bucket, client, context, get, log, queued, read_state,
                            write_failed, write_stored, write_submitted)


def sweeper(app):
    return context(app)["sweeper"]


def names(bucket):
    return [entry.name for entry in bucket.list("sliced/")]


# Refusing and deleting.

def test_a_file_one_second_under_two_hours_is_served_and_at_two_hours_refused_and_deleted(
        client, bucket, clock):
    write_stored(bucket)
    at(clock, ENDED + 7199)
    answer = get(client, f"/api/slices/{JOB}/file", buffered=True)
    assert answer.status_code == 200 and answer.get_data() == FILE
    at(clock, ENDED + 7200)
    answer = get(client, f"/api/slices/{JOB}/file", buffered=True)
    assert answer.status_code == 410
    assert answer.get_json()["code"] == "front.sliced_file_expired"
    assert names(bucket) == [sliced.record_name(USER, JOB)]
    progress = get(client, f"/api/slices/{JOB}").get_json()["progress"]
    assert progress["state"] == "failed"
    assert progress["error"]["code"] == "front.sliced_file_expired"


# The sweep.

def test_the_sweep_deletes_a_file_that_fell_due_and_leaves_one_that_has_not(app, bucket,
                                                                           clock, log):
    write_stored(bucket, "old", ended_at=ENDED_AT)
    write_stored(bucket, "new", ended_at=sliced.utc(ENDED + 60))
    at(clock, ENDED + 7200)
    assert sweeper(app).sweep() == {"checked": 2, "files_expired": 1, "records_deleted": 0,
                                    "files_deleted": 0, "failed": 0}
    assert read_state(bucket, "old") == "expired" and read_state(bucket, "new") == "stored"
    assert sliced.file_name(USER, "old") not in names(bucket)
    assert sliced.file_name(USER, "new") in names(bucket)
    [line] = log.events("sliced_file_expired")
    assert line["by"] == "sweep" and line["slice"] == "old" and line["group"] == GROUP
    [summary] = log.events("sweep")
    assert summary["files_expired"] == 1 and summary["checked"] == 2


def test_a_restarted_front_servers_sweep_finds_a_file_stored_before_the_restart(
        tmp_path, clock, standin):
    def started():
        return create_app(Settings.from_environ(environ(tmp_path,
                                                        PENGUIN_SLICE_URL=standin.url)),
                          clock=clock, log=Lines())

    first = started()
    write_stored(context(first)["state_bucket"])
    shut(first)
    second = started()
    try:
        at(clock, ENDED + 7200)
        assert sweeper(second).sweep()["files_expired"] == 1
        assert read_state(context(second)["state_bucket"]) == "expired"
    finally:
        shut(second)


def test_an_expired_record_is_deleted_once_its_extra_day_has_passed(app, bucket, clock, log):
    write_stored(bucket)
    at(clock, ENDED + 7200)
    sweeper(app).sweep()
    at(clock, ENDED + 7200 + 86_399)
    assert sweeper(app).sweep()["records_deleted"] == 0
    at(clock, ENDED + 7200 + 86_400)
    assert sweeper(app).sweep()["records_deleted"] == 1
    assert names(bucket) == []
    [line] = log.events("sliced_record_deleted")
    assert line == {"event": "sliced_record_deleted", "user_key": USER, "group": GROUP,
                    "slice": JOB, "state": "expired", "age_s": 86_400}


def test_a_submitted_record_never_to_be_stored_is_deleted_after_four_hours(app, bucket,
                                                                          clock):
    write_submitted(bucket, "j1", sliced.utc(START))
    at(clock, START + 4 * 3600 - 1)
    assert sweeper(app).sweep()["records_deleted"] == 0
    at(clock, START + 4 * 3600)
    assert sweeper(app).sweep()["records_deleted"] == 1
    assert names(bucket) == []


def test_a_sliced_file_beside_an_old_submitted_record_is_deleted_with_it(app, bucket, clock,
                                                                         log):
    # A front server stopped between storing the file and writing its `stored` record
    # leaves the file beside the `submitted` record written at submission.
    write_submitted(bucket, "j1", sliced.utc(START))
    bucket.put(sliced.file_name(USER, "j1"), FILE)
    at(clock, START + 4 * 3600 - 1)
    assert sweeper(app).sweep()["records_deleted"] == 0
    assert len(names(bucket)) == 2
    at(clock, START + 4 * 3600)
    assert sweeper(app).sweep()["records_deleted"] == 1
    assert names(bucket) == []
    [line] = log.events("sliced_record_deleted")
    assert line["state"] == "submitted" and line["slice"] == "j1"


def test_a_submitted_record_of_a_slice_job_followed_is_kept(app, bucket, clock, standin):
    standin.add_job("j1", USER, "p", "s", queued("j1"))
    context(app)["follower"].follow(USER, "j1", GROUP)
    write_submitted(bucket, "j1", sliced.utc(START))
    at(clock, START + 5 * 3600)
    assert sweeper(app).sweep()["records_deleted"] == 0
    assert read_state(bucket, "j1") == "submitted"


def test_a_failed_record_is_deleted_a_day_and_two_hours_after_its_slice_ended(app, bucket,
                                                                             clock):
    write_failed(bucket)
    at(clock, ENDED + 7200 + 86_399)
    assert sweeper(app).sweep()["records_deleted"] == 0
    at(clock, ENDED + 7200 + 86_400)
    assert sweeper(app).sweep()["records_deleted"] == 1


def test_a_file_with_no_record_is_deleted_two_hours_after_it_was_stored(app, bucket, clock):
    bucket.put(sliced.file_name(USER, "j1"), FILE)
    at(clock, START + 7199)
    assert sweeper(app).sweep()["files_deleted"] == 0
    at(clock, START + 7200)
    assert sweeper(app).sweep()["files_deleted"] == 1
    assert names(bucket) == []


def test_a_file_with_no_record_whose_slice_job_is_followed_is_kept(app, bucket, clock,
                                                                  standin):
    standin.add_job("j1", USER, "p", "s", queued("j1"))
    context(app)["follower"].follow(USER, "j1", GROUP)
    bucket.put(sliced.file_name(USER, "j1"), FILE)
    at(clock, START + 3 * 3600)
    assert sweeper(app).sweep()["files_deleted"] == 0


def test_a_record_of_a_newer_format_is_left_alone(app, bucket, clock, log):
    write_stored(bucket)
    name = sliced.record_name(USER, JOB)
    bucket.put(name, b'{"format": 99, "kind": "sliced_file", "state": "stored"}')
    at(clock, ENDED + 3 * 86_400)
    assert sweeper(app).sweep()["checked"] == 1
    assert name in names(bucket) and sliced.file_name(USER, JOB) in names(bucket)


def test_names_the_sweep_does_not_make_are_left_alone(app, bucket, clock):
    for name in ("sliced/x", "sliced/u/notes.txt", "sliced/u/v/w.json"):
        bucket.put(name, b"{}")
    at(clock, START + 3 * 86_400)
    assert sweeper(app).sweep()["checked"] == 0
    assert len(names(bucket)) == 3


def test_a_state_bucket_that_cannot_be_listed_fails_the_sweep_with_a_line(app, bucket, log):
    bucket.refuse_reads = True
    assert sweeper(app).sweep() is None
    [line] = log.events("sweep_failed")
    assert "refuses reads" in line["why"]


def test_a_file_that_cannot_be_deleted_is_counted_failed_and_tried_at_the_next_sweep(
        app, bucket, clock, log):
    write_stored(bucket)
    at(clock, ENDED + 7200)
    bucket.refuse_writes = True
    assert sweeper(app).sweep()["failed"] == 1
    [line] = log.events("sweep_item_failed")
    assert line["slice"] == JOB and line["user_key"] == USER and "refuses" in line["why"]
    bucket.refuse_writes = False
    assert sweeper(app).sweep()["files_expired"] == 1


def test_a_record_is_never_expired_beside_a_file_still_there(app, bucket, clock):
    # The file is deleted first, then the record turned `expired`: a delete that fails
    # leaves the record `stored`, for the next sweep.
    write_stored(bucket)
    at(clock, ENDED + 7200)
    bucket.refuse_deletes = True
    assert sweeper(app).sweep()["failed"] == 1
    assert read_state(bucket) == "stored"
    assert sliced.file_name(USER, JOB) in names(bucket)


# The sweep's loop.

def test_the_sweep_runs_at_start_and_every_ten_minutes_on_the_clock(app, bucket, clock):
    write_stored(bucket)
    loop = sweeper(app).every
    assert loop.seconds == sweep.SWEEP_INTERVAL_S == 600
    sweeper(app).start()
    try:
        loop.wait_for_runs(1)
        assert read_state(bucket) == "stored"
        clock.wait_for_sleepers(1)
        at(clock, ENDED + 7200)  # far past the ten minutes of the loop's wait
        loop.wait_for_runs(2)
        assert read_state(bucket) == "expired"
    finally:
        sweeper(app).stop()
    assert loop.wait_for_runs(2) is None


def test_a_failure_inside_a_loop_is_logged_and_the_loop_goes_on(clock):
    log = Lines()
    calls = []

    def action():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("by the test")

    loop = Every(clock, 60, action, log, "test_loop")
    loop.start()
    try:
        loop.wait_for_runs(1)
        clock.wait_for_sleepers(1)
        clock.advance(60)
        loop.wait_for_runs(2)
    finally:
        loop.stop()
    [line] = log.events("loop_failed")
    assert line["loop"] == "test_loop" and "RuntimeError: by the test" in line["trace"]


def test_a_loop_stopped_before_it_starts_never_runs(clock):
    calls = []
    loop = Every(clock, 60, lambda: calls.append(1), Lines(), "test_loop")
    loop.stop()  # nothing started: nothing to wait for
    loop.start()
    loop.stop()
    assert calls == []


def test_a_loop_that_never_ran_is_reported_so(clock):
    loop = Every(clock, 60, lambda: None, Lines(), "test_loop")
    with pytest.raises(AssertionError):
        loop.wait_for_runs(1, backstop_s=0)
