"""Each row of the architecture's table "The slice container restarts" that needs no page
(docs/architecture.md, "What a restart does"), the slice service restarted at that row's
moment, and the page doing what the wizard's guide says it does; and the two rows of "The
front server restarts" that turn on the slice service's list of its slice jobs."""

import json

import pytest

from joined.page import Refused
from joined.plates import again, clamp_plate, upload_missing


def slice_again_after_a_restart(page, configuration):
    """What an open page does once the slice service has restarted: submit the plate, upload
    the parts the slice service says are missing, and submit the same submission again.
    Gives the slice job accepted."""
    with pytest.raises(Refused) as refused:
        page.submit(configuration)
    assert refused.value.status == 422
    upload_missing(page, refused.value)
    return page.submit(configuration)


def test_a_running_slice_cut_off_by_a_restart_is_submitted_again_and_slices(page, slice_service):
    """Row: a slice was waiting or running. The slice container dies; progress starts again
    once the page uploads its parts and submits the same plate."""
    slice_service.orca_mode("gate")
    configuration = clamp_plate(page)
    first = page.submit(configuration)
    stream = page.stream(first["id"])
    stream.wait_for_stage("slicing_mesh")

    slice_service.crash()
    slice_service.orca_mode("ok")
    slice_service.restart()
    # The front server's following ends when the new process does not know the slice job:
    # the page's stream closes with no final report, and asking says it is unknown.
    stream.wait_closed()
    assert stream.final is None
    with pytest.raises(Refused) as refused:
        page.ask(first["id"])
    assert (refused.value.status, refused.value.report["code"]) == (404, "front.slice_unknown")

    # Submitted less than two hours ago: the page uploads its parts and submits again.
    second = slice_again_after_a_restart(page, again(configuration))
    assert second["id"] != first["id"]
    assert page.stream(second["id"]).wait_closed().final["state"] == "done"


def test_a_stop_ends_the_waiting_slice_refuses_new_ones_and_finishes_the_running_one(
        page, slice_service):
    """Rows: a slice was waiting (ended early, `shutdown`, and submitted again by its page);
    a user submits while the slice service stops (the stopping answer, passed unchanged,
    then accepted by the new slice service); and the running slice is finished and stored
    before the slice service exits."""
    slice_service.orca_mode("gate")
    running_plate = clamp_plate(page)
    running = page.submit(running_plate)
    running_stream = page.stream(running["id"])
    running_stream.wait_for_stage("slicing_mesh")
    slice_service.orca_mode("ok")
    waiting_plate = clamp_plate(page, x=200.0)
    waiting = page.submit(waiting_plate)
    waiting_stream = page.stream(waiting["id"])
    waiting_stream.wait_for(lambda r: r["state"] == "queued" and r["ahead"] == 1, "waiting behind one")

    slice_service.stop()
    ended = waiting_stream.wait_closed().final
    assert (ended["state"], ended["cancel_reason"]) == ("cancelled", "shutdown")
    assert page.ask(waiting["id"]) == ended

    # The page submits the ended plate again by itself, with a new submission value; the
    # stopping slice service answers that it is stopping, and the front server passes that
    # answer on unchanged.
    resubmitted = again(waiting_plate)
    answer = page.submit_raw(resubmitted)
    own = slice_service.request("POST", "/slices", content=json.dumps(resubmitted).encode(),
                                headers={"Content-Type": "application/json"})
    assert (answer.status_code, own.status_code) == (503, 503)
    assert answer.content == own.content
    report = answer.json()
    assert (report["code"], report["retryable"]) == ("slice.stopping", True)

    # The running slice finishes, the front server stores it, and only then does the slice
    # service exit.
    slice_service.release_orca()
    done = running_stream.wait_closed().final
    assert done["state"] == "done"
    assert slice_service.wait_stopped() == 0
    stopped = slice_service.lines("slice_service_stopped")[-1]
    assert (stopped["how"], stopped["files_lost"]) == ("drained", [])
    assert page.download(running["id"])[0]

    # The new slice service accepts the same submission once its part is uploaded again.
    slice_service.restart()
    accepted = slice_again_after_a_restart(page, resubmitted)
    assert accepted["submission_id"] == resubmitted["submission_id"]
    assert page.stream(accepted["id"]).wait_closed().final["state"] == "done"


def test_a_finished_slice_is_still_there_after_the_slice_service_restarts(page, slice_service):
    """Row: a slice had finished. Nothing changes for the user: the sliced file is in the
    state bucket."""
    accepted = page.submit(clamp_plate(page))
    done = page.stream(accepted["id"]).wait_closed().final
    body, _headers = page.download(accepted["id"])

    slice_service.crash()
    slice_service.restart()
    assert page.ask(accepted["id"])["state"] == "done"
    assert page.summary(accepted["id"])["summary"] == done["sliced_file"]["summary"]
    assert page.download(accepted["id"])[0] == body


def test_a_slice_running_while_the_front_server_restarts_is_stored_by_the_new_one(
        page, slice_service, front_server):
    """The front server's row "a slice was running": the new front server finds the slice job
    in the slice service's list, follows it and stores its sliced file."""
    slice_service.orca_mode("gate")
    accepted = page.submit(clamp_plate(page))
    page.stream(accepted["id"]).wait_for_stage("slicing_mesh")
    front_server.stop()
    front_server.restart()
    front_server.running.wait_for_event("slices_collected", followed=1)
    slice_service.release_orca()
    # The page's stream reopens on the new front server and ends with the stored slice.
    done = page.stream(accepted["id"]).wait_closed().final
    assert done["state"] == "done" and done["sliced_file"]["slice"] == accepted["id"]


def test_a_slice_that_ended_while_the_front_server_was_down_is_collected_at_start(
        page, slice_service, front_server):
    """The slice ends with nobody to store it; the next front server collects the sliced file
    the slice service still holds, timing its two hours from when the slice ended."""
    slice_service.orca_mode("gate")
    accepted = page.submit(clamp_plate(page))
    page.stream(accepted["id"]).wait_for_stage("slicing_mesh")
    front_server.stop()
    slice_service.release_orca()
    listed = _wait_listed_done(slice_service, accepted["id"])
    assert listed["file_on_disk"] is True and listed["ended_at"]

    front_server.restart()
    front_server.running.wait_for_event("slices_collected", collecting=1)
    done = page.stream(accepted["id"]).wait_closed().final
    assert done["state"] == "done"
    assert done["sliced_file"]["slice_ended_at"] == listed["ended_at"]
    assert _listed(slice_service, accepted["id"])["file_on_disk"] is False


def _listed(slice_service, job):
    (entry,) = [e for e in slice_service.request("GET", "/slices", user_key=None).json()["slices"]
                if e["job"] == job]
    return entry


def _wait_listed_done(slice_service, job):
    """The slice service's list entry for `job` once its slice job is done, waited for on the
    slice service's own line for that transition."""
    slice_service.running.wait_for_event("slice_job", job=job, state="done")
    return _listed(slice_service, job)
