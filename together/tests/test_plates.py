"""A plate's slice jobs across the seam: the same submission sent again, the same plate sliced
again, and a part the part store has forgotten."""

import pytest

from joined.page import Refused, new_id
from joined.plates import again, clamp_plate, upload_missing


def test_a_repeated_submission_is_answered_with_the_first_attempts_slice_job(page, slice_service):
    configuration = clamp_plate(page)
    first = page.submit(configuration)
    repeat = page.submit(configuration)          # its answer lost, the page sends it again
    assert repeat["id"] == first["id"]
    assert (repeat["plate_id"], repeat["submission_id"]) == (first["plate_id"], first["submission_id"])
    done = page.stream(first["id"]).wait_closed().final
    assert done["state"] == "done"
    # Sent again once it is done, still the same slice job, now done, with its sliced file.
    after = page.submit(configuration)
    assert after["id"] == first["id"]
    assert after["progress"]["state"] == "done" and after["progress"]["sliced_file"] == done["sliced_file"] | {
        "expires_in_s": after["progress"]["sliced_file"]["expires_in_s"]}
    # One slice job, and two repeats, in the slice service's own log.
    accepted = [line for line in slice_service.lines("slice_job") if line.get("state") == "queued"]
    assert [line["job"] for line in accepted] == [first["id"]]
    assert [line["job"] for line in slice_service.lines("slice_repeat")] == [first["id"]] * 2


def test_the_same_plate_sliced_again_replaces_its_unfinished_slice(page, slice_service):
    slice_service.orca_mode("gate")
    configuration = clamp_plate(page)
    earlier = page.submit(configuration)
    earlier_stream = page.stream(earlier["id"])
    earlier_stream.wait_for_stage("slicing_mesh")          # Orca holds at its gate
    slice_service.orca_mode("ok")

    later = page.submit(again(configuration))
    assert later["id"] != earlier["id"] and later["plate_id"] == earlier["plate_id"]
    ended = earlier_stream.wait_closed().final
    assert (ended["state"], ended["cancel_reason"]) == ("cancelled", "replaced")
    assert "error" not in ended
    assert page.ask(earlier["id"]) == ended
    done = page.stream(later["id"]).wait_closed().final
    assert done["state"] == "done"
    with pytest.raises(Refused) as refused:
        page.summary(earlier["id"])
    assert refused.value.report["code"] == "front.sliced_file_not_ready"


def test_another_plate_is_never_replaced(page, slice_service):
    slice_service.orca_mode("gate")
    one = page.submit(clamp_plate(page))
    one_stream = page.stream(one["id"])
    one_stream.wait_for_stage("slicing_mesh")
    slice_service.orca_mode("ok")
    other = page.submit(clamp_plate(page))
    assert other["progress"] == {**other["progress"], "state": "queued", "ahead": 1}
    slice_service.release_orca()
    assert one_stream.wait_closed().final["state"] == "done"
    assert page.stream(other["id"]).wait_closed().final["state"] == "done"


def test_a_part_the_part_store_has_forgotten_is_uploaded_again_and_the_plate_submitted_again(
        page, slice_service):
    configuration = clamp_plate(page)
    # The part store forgets every part when the slice service process ends.
    slice_service.stop()
    slice_service.wait_stopped()
    slice_service.restart()

    with pytest.raises(Refused) as refused:
        page.submit(configuration)
    report = refused.value.report
    assert refused.value.status == 422
    assert report["where"]["missing_parts"] == [
        {"key": "clamp", "sha256": configuration["parts"]["clamp"]["sha256"], "units": "mm"}]
    assert report["retryable"] is False
    # Nothing was started, so the same submission's value is sent again once the part is back.
    assert upload_missing(page, refused.value) == ["clamp"]
    accepted = page.submit(configuration)
    assert accepted["submission_id"] == configuration["submission_id"]
    assert page.stream(accepted["id"]).wait_closed().final["state"] == "done"


def test_an_instance_naming_no_part_is_the_pages_fault_with_no_parts_listed(page):
    configuration = clamp_plate(page)
    configuration["instances"].append(dict(configuration["instances"][0], ref="nothing", x=250.0))
    configuration["submission_id"] = new_id()
    with pytest.raises(Refused) as refused:
        page.submit(configuration)
    assert refused.value.report["code"] == "slice.part_missing"
    assert "missing_parts" not in refused.value.report.get("where", {})
