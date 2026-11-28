"""Failures across the seam: the slice service's error report reaches the page unchanged,
whether it refuses a plate at once or a slice fails while it runs."""

import json

import pytest

from joined.page import Refused
from joined.plates import clamp_plate


def test_a_slice_that_fails_reaches_the_page_with_the_slice_services_own_report(page, slice_service):
    slice_service.orca_mode("empty_layers")
    accepted = page.submit(clamp_plate(page))
    stream = page.stream(accepted["id"]).wait_closed()
    failed = stream.final
    assert failed["state"] == "failed"
    error = failed["error"]
    assert error["code"] == "slice.empty_layers" and error["action"] == "enable_supports"
    assert error["orca_sentence"] == "Object can't be printed for empty layer between 9.9 and 11.34."
    # Byte for byte what the slice service reports of its slice job.
    own = slice_service.request("GET", f"/slices/{accepted['id']}").json()
    assert own["state"] == "failed"
    assert error == own["error"]
    assert failed == own
    # Asked about afterwards, the same failure.
    assert page.ask(accepted["id"]) == own
    # A failed slice has no sliced file.
    with pytest.raises(Refused) as refused:
        page.summary(accepted["id"])
    assert refused.value.report["code"] == "front.sliced_file_not_ready"


def test_a_plate_refused_at_once_is_answered_with_the_slice_services_own_bytes(page, slice_service):
    off_the_plate = clamp_plate(page, x=2000.0)
    answer = page.submit_raw(off_the_plate)
    own = slice_service.request("POST", "/slices", content=json.dumps(off_the_plate).encode(),
                                headers={"Content-Type": "application/json"})
    assert (answer.status_code, own.status_code) == (422, 422)
    assert answer.json()["code"] == "slice.placement_off_plate"
    assert answer.content == own.content


def test_with_one_slice_running_and_two_waiting_the_busy_answer_reaches_the_page_unchanged(
        page, slice_service):
    slice_service.orca_mode("gate")
    running = page.submit(clamp_plate(page))
    running_stream = page.stream(running["id"])
    running_stream.wait_for_stage("slicing_mesh")
    slice_service.orca_mode("ok")
    waiting = [page.submit(clamp_plate(page)) for _ in range(2)]
    assert [w["progress"]["ahead"] for w in waiting] == [1, 2]

    refused_plate = clamp_plate(page)
    answer = page.submit_raw(refused_plate)
    own = slice_service.request("POST", "/slices", content=json.dumps(refused_plate).encode(),
                                headers={"Content-Type": "application/json"})
    assert (answer.status_code, own.status_code) == (503, 503)
    assert answer.content == own.content
    assert (answer.json()["code"], answer.json()["retryable"]) == ("slice.busy", True)

    slice_service.release_orca()
    assert running_stream.wait_closed().final["state"] == "done"
    for accepted in waiting:
        assert page.stream(accepted["id"]).wait_closed().final["state"] == "done"


def test_a_part_the_slice_service_refuses_is_answered_with_its_own_bytes(page, slice_service):
    text_stl = b"solid box\nendsolid box\n"          # too short to be a binary STL
    answer = page.client.post("/api/parts", params={"units": "mm"}, content=text_stl, headers={
        **page._headers(changing=True), "Content-Type": "application/octet-stream"})
    own = slice_service.request("POST", "/parts", params={"units": "mm"}, content=text_stl,
                                headers={"Content-Type": "application/octet-stream"})
    assert (answer.status_code, own.status_code) == (422, 422)
    assert answer.content == own.content
    assert answer.json()["code"] == "slice.part_unreadable"


def test_a_part_without_its_units_is_refused_by_the_slice_service_not_the_front_server(page, slice_service):
    body = b"\0" * 84
    answer = page.client.post("/api/parts", content=body, headers={
        **page._headers(changing=True), "Content-Type": "application/octet-stream"})
    own = slice_service.request("POST", "/parts", content=body,
                                headers={"Content-Type": "application/octet-stream"})
    assert (answer.status_code, answer.json()["code"]) == (400, "slice.bad_units")
    assert answer.content == own.content
