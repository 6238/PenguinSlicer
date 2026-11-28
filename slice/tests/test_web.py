"""web.py, the HTTP interface, through Flask's test client and the fake Orca: upload a part,
submit a plate configuration, follow its progress reports, cancel it, fetch the sliced file;
the user key on every request; every error answer is an error report."""
import io
import itertools
import json
import os
import tempfile
import threading
from pathlib import Path

import pytest

from helpers import (CONTRACTS, PLATE_ID, SUBMISSION_ID, USER_KEY, box_stl, install_fake_orca, part_entry, sha256,
                     submit, upload)
from penguin_slice import limits
from penguin_slice.errors import error_report
from penguin_slice.jobs import FINAL, JobPool, RepeatedSubmission
from penguin_slice.part_store import PartStore, user_folder
from penguin_slice.web import USER_KEY_HEADER, create_app, remove_job_files, slice_worker

FAILSAFE_S = 10
BOX = box_stl(20, 20, 10)
EXAMPLES = CONTRACTS / "examples"
HEADERS = {USER_KEY_HEADER: USER_KEY}


class ImmediateExecutor:
    def submit(self, fn, *args):
        fn(*args)


class HeldExecutor:
    def __init__(self):
        self.pending = []

    def submit(self, fn, *args):
        self.pending.append((fn, args))

    def run_next(self):
        fn, args = self.pending.pop(0)
        fn(*args)


SUBMISSIONS = itertools.count(1)


def plate_configuration(**changes):
    """A plate configuration of the box on PLATE_ID, each one a new submission (its own
    submission_id) unless `changes` names one."""
    job = {"plate_id": PLATE_ID, "submission_id": f"submission-{next(SUBMISSIONS)}",
           "parts": {"box": part_entry("Box", BOX)},
           "instances": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0}],
           "local_time": "20261009-1432"}
    job.update(changes)
    return job


@pytest.fixture
def work(tmp_path):
    return tmp_path / "work"


def app_with(work, executor=None, store=None, upload_box=True, environ=None, **kwargs):
    """(client, pool, log lines), the box uploaded under USER_KEY unless `upload_box` is false."""
    logs = []
    pool = JobPool(slice_worker, executor=executor or ImmediateExecutor(), error_report=error_report,
                   cleanup=remove_job_files, log=logs.append, **kwargs)
    app = create_app(work, pool, start_sweeper=False, log=logs.append, store=store, environ=environ)
    client = app.test_client()
    if upload_box:
        assert upload(client, BOX).status_code == 201
        logs.clear()
    return client, pool, logs


class UnreadBody:
    """A request body that records every read: a test that it is never read."""

    def __init__(self):
        self.reads = []

    def read(self, *args):
        self.reads.append(args)
        return b""

    def tell(self):
        return 0

    def seek(self, *args):
        return 0


def streamed(client, path, data, content_type="application/octet-stream"):
    """A POST whose body comes without a Content-Length (Transfer-Encoding: chunked)."""
    return client.post(path, headers={**HEADERS, "Transfer-Encoding": "chunked"}, content_type=content_type,
                       environ_overrides={"wsgi.input_terminated": True}, input_stream=io.BytesIO(data))


def job_folders(work):
    """The slice jobs' folders under the work folder: every folder but the part store's."""
    return [p for p in work.iterdir() if "-parts-" not in p.name]


def assert_error_report(body, code):
    assert body["code"] == code
    assert {"code", "message", "remedy", "retryable", "detail"} <= set(body)


class TestUserKey:
    """Item 1: every request about a part or a slice job carries the user key."""

    @pytest.mark.parametrize("method, path", [("post", "/parts?units=mm"), ("post", "/slices"),
                                              ("get", "/slices/j0"), ("get", "/slices/j0/events"),
                                              ("get", "/slices/j0/file"), ("get", "/slices/j0/summary"),
                                              ("delete", "/slices/j0")])
    @pytest.mark.parametrize("key", [None, ""])
    def test_each_scoped_route_refuses_a_request_without_the_user_key(self, work, method, path, key):
        client, _pool, logs = app_with(work)
        headers = {} if key is None else {USER_KEY_HEADER: key}
        answer = getattr(client, method)(path, headers=headers, data=b"x" if method == "post" else None)
        assert answer.status_code == 400
        body = answer.get_json()
        assert_error_report(body, "slice.no_user_key")
        assert body["detail"] == f"{method.upper()} {path.split('?')[0]} " + \
            ("without X-Penguin-User-Key" if key is None else "with an empty X-Penguin-User-Key")
        assert [(e.get("error_code"), e.get("http_status")) for e in logs] == [("slice.no_user_key", 400)]

    def test_the_report_is_the_contracts_example(self, work):
        client, _pool, _logs = app_with(work)
        body = client.post("/parts?units=mm", data=BOX).get_json()
        assert body == json.loads((EXAMPLES / "slice-http" / "no-user-key.json").read_text())

    @pytest.mark.parametrize("route", ["", "/events", "/file", "/summary"])
    def test_every_route_about_a_slice_job_answers_another_user_keys_as_unknown(self, tmp_path, monkeypatch, work,
                                                                                route):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, logs = app_with(work)
        job_id = submit(client, plate_configuration()).get_json()["job"]
        logs.clear()
        theirs = client.get(f"/slices/{job_id}{route}", headers={USER_KEY_HEADER: "user-b"})
        never = client.get(f"/slices/jnever{route}", headers={USER_KEY_HEADER: "user-b"})
        assert theirs.status_code == never.status_code == 404
        assert {k: v for k, v in theirs.get_json().items() if k != "detail"} == \
            {k: v for k, v in never.get_json().items() if k != "detail"}
        assert theirs.get_json()["code"] == "slice.unknown_job"
        assert [(e["event"], e["job"], e["user_key"], e["error_code"]) for e in logs] == \
            [("slice_http_refused", job_id, "user-b", "slice.unknown_job")]
        assert client.get(f"/slices/{job_id}{route}", headers=HEADERS).status_code == 200

    def test_a_cancel_of_another_user_keys_slice_job_is_unknown_and_changes_nothing(self, work):
        client, pool, logs = app_with(work, executor=HeldExecutor())
        job_id = submit(client, plate_configuration()).get_json()["job"]
        answer = client.delete(f"/slices/{job_id}", headers={USER_KEY_HEADER: "user-b"})
        assert (answer.status_code, answer.get_json()["code"]) == (404, "slice.unknown_job")
        assert pool.get(job_id)["state"] == "queued"
        assert logs[-1]["event"] == "slice_http_refused"

    def test_a_slice_job_is_held_under_its_user_key(self, work):
        client, pool, logs = app_with(work, executor=HeldExecutor())
        job_id = submit(client, plate_configuration()).get_json()["job"]
        assert pool.owned_by(job_id, USER_KEY) and not pool.owned_by(job_id, "user-b")
        assert [e["user_key"] for e in logs] == [USER_KEY]

    def test_a_user_key_that_is_a_path_reaches_no_path(self, work):
        client, _pool, _logs = app_with(work, upload_box=False)
        assert upload(client, BOX, user_key="../../../x").status_code == 201
        store = client.application.extensions["penguin_slice_store"]
        assert (store.root / user_folder("../../../x") / f"{sha256(BOX)}-mm.stl").is_file()
        assert sorted(p.name for p in store.root.iterdir()) == [user_folder("../../../x")]


class TestUpload:
    """Items 2 and 3: POST /parts?units= takes one part into the part store."""

    def test_the_bracket_answers_the_contracts_record(self, work):
        client, _pool, logs = app_with(work, upload_box=False)
        answer = upload(client, (EXAMPLES / "parts" / "bracket.stl").read_bytes())
        assert answer.status_code == 201 and answer.headers["Cache-Control"] == "no-store"
        assert answer.get_json() == json.loads((EXAMPLES / "slice-http" / "part-record.json").read_text())
        assert [(e["event"], e["state"], e["user_key"], e["sha256"]) for e in logs] == \
            [("part_upload", "stored", USER_KEY, answer.get_json()["sha256"])]

    def test_a_repeated_upload_answers_the_same_record(self, work):
        client, _pool, logs = app_with(work)
        again = upload(client, BOX)
        assert again.status_code == 201 and again.get_json()["sha256"] == sha256(BOX)
        assert logs[-1]["state"] == "stored_again"

    def test_one_file_under_mm_and_under_in_is_two_entries(self, work):
        client, _pool, _logs = app_with(work, upload_box=False)
        small = box_stl(2, 1, 0.5)
        mm, inches = upload(client, small).get_json(), upload(client, small, units="in").get_json()
        assert (mm["units"], inches["units"]) == ("mm", "in") and mm["sha256"] == inches["sha256"]
        assert mm["measurements"]["size_mm"] == [2.0, 1.0, 0.5]
        assert inches["measurements"]["size_mm"] == [50.8, 25.4, 12.7]
        assert [w["code"] for w in mm["warnings"]] == ["slice.part_maybe_inches"] and inches["warnings"] == []
        assert len(client.application.extensions["penguin_slice_store"]) == 2

    @pytest.mark.parametrize("units, detail", [(None, "no units label"), ("cm", "units 'cm', not 'mm' or 'in'"),
                                               ("", "units '', not 'mm' or 'in'"), ("MM", "units 'MM', not 'mm' or 'in'")])
    def test_an_upload_without_mm_or_in_is_refused(self, work, units, detail):
        client, _pool, logs = app_with(work, upload_box=False)
        answer = upload(client, BOX, units=units)
        assert answer.status_code == 400
        body = answer.get_json()
        assert_error_report(body, "slice.bad_units")
        assert (body["message"], body["detail"]) == (
            "The slicer was not told whether this part is in millimetres or inches.", detail)
        assert logs[-1]["state"] == "refused" and logs[-1]["error_code"] == "slice.bad_units"

    @pytest.mark.parametrize("data, code, status", [
        (b"", "slice.part_unreadable", 422),
        (b"solid x\n facet normal 0 0 1\n" + b" " * 100, "slice.part_not_binary", 422),
        (box_stl(0.05, 0.05, 0.05), "slice.part_too_small", 422),
        (box_stl(500, 500, 500), "slice.part_too_large", 422),
    ])
    def test_each_refusal_comes_through_the_route(self, work, data, code, status):
        client, _pool, logs = app_with(work, upload_box=False)
        answer = upload(client, data)
        assert answer.status_code == status
        assert_error_report(answer.get_json(), code)
        assert answer.get_json()["where"] == {"stage": "checking"}
        assert len(client.application.extensions["penguin_slice_store"]) == 0
        assert (logs[-1]["event"], logs[-1]["error_code"], logs[-1]["http_status"]) == ("part_upload", code, status)

    def test_loose_triangles_are_refused_as_nothing_to_print(self, work):
        from helpers import FIXTURES
        client, _pool, _logs = app_with(work, upload_box=False)
        answer = upload(client, (FIXTURES / "bad_stls" / "single_triangle.stl").read_bytes())
        assert (answer.status_code, answer.get_json()["code"]) == (422, "slice.part_no_volume")

    def test_over_the_triangle_cap_is_too_detailed(self, work, monkeypatch):
        monkeypatch.setattr(limits, "MAX_PART_TRIANGLES", 11)
        client, _pool, _logs = app_with(work, upload_box=False)
        answer = upload(client, BOX)                 # 12 triangles
        assert (answer.status_code, answer.get_json()["code"]) == (413, "slice.part_too_detailed")

    def test_a_content_length_over_the_cap_is_refused_before_the_body_is_read(self, work):
        client, _pool, logs = app_with(work, upload_box=False)
        body = UnreadBody()
        answer = client.post("/parts?units=mm", headers=HEADERS, input_stream=body,
                             environ_overrides={"CONTENT_LENGTH": str(limits.MAX_PART_BYTES + 1)},
                             content_type="application/octet-stream")
        assert answer.status_code == 413 and body.reads == []
        assert answer.get_json() == json.loads((EXAMPLES / "error-report-part-over-size.json").read_text())
        assert logs[-1]["error_code"] == "slice.part_too_detailed"

    def test_a_part_at_the_byte_cap_is_read(self, work, monkeypatch):
        client, _pool, _logs = app_with(work, upload_box=False)
        data = BOX + b"\0" * (limits.MAX_PART_BYTES - len(BOX))
        answer = upload(client, data)
        assert answer.get_json()["code"] == "slice.part_unreadable"          # read, and found padded

    def test_an_upload_without_a_content_length_is_refused(self, work):
        client, _pool, _logs = app_with(work, upload_box=False)
        answer = streamed(client, "/parts?units=mm", BOX)
        assert answer.status_code == 400
        assert_error_report(answer.get_json(), "slice.bad_request")

    def test_a_part_store_that_cannot_be_written(self, work, monkeypatch):
        client, _pool, logs = app_with(work, upload_box=False)
        monkeypatch.setattr("penguin_slice.part_store.os.fdopen",
                            lambda *a, **k: (_ for _ in ()).throw(OSError(28, "No space left on device")))
        answer = upload(client, BOX)
        assert answer.status_code == 500
        body = answer.get_json()
        assert_error_report(body, "slice.scratch_unwritable")
        assert "No space left on device" in body["detail"] and logs[-1]["http_status"] == 500

    def test_a_catalog_that_cannot_be_read_on_upload(self, work, monkeypatch):
        from penguin_slice import service
        from penguin_slice.print_config import ProfileError
        client, _pool, _logs = app_with(work, upload_box=False)

        def broken():
            raise ProfileError("The print server's settings for this printer could not be read.", "x",
                               error_code="slice.profile_unreadable")
        monkeypatch.setattr(service, "largest_plate", broken)
        answer = upload(client, BOX)
        assert (answer.status_code, answer.get_json()["code"]) == (422, "slice.profile_unreadable")

    def test_a_bug_while_a_part_arrives_is_an_error_report_and_a_log_line(self, work, monkeypatch):
        client, _pool, logs = app_with(work, upload_box=False)
        monkeypatch.setattr("penguin_slice.web.upload_part", lambda *a: 1 / 0)
        answer = upload(client, BOX)
        assert (answer.status_code, answer.get_json()["code"]) == (500, "slice.unexpected")
        assert logs[-1]["event"] == "part_upload" and "ZeroDivisionError" in logs[-1]["traceback"]

    def test_a_method_parts_does_not_take_is_no_upload(self, work):
        client, _pool, logs = app_with(work, upload_box=False)
        assert client.get("/parts").status_code == 405
        assert logs == []


class TestSubmit:
    def test_a_plate_configuration_is_sliced_and_its_file_fetched(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, logs = app_with(work)
        answer = submit(client, plate_configuration(submission_id=SUBMISSION_ID))
        assert answer.status_code == 202 and answer.headers["Cache-Control"] == "no-store"
        body = answer.get_json()
        assert (body["plate_id"], body["submission_id"]) == (PLATE_ID, SUBMISSION_ID)
        assert body["part_warnings"] == [] and body["progress"]["state"] == "done"
        fetched = client.get(f"/slices/{body['job']}/file", headers=HEADERS)
        assert fetched.status_code == 200
        assert fetched.data[:2] == b"PK"
        assert "Box-20261009-1432.gcode.3mf" in fetched.headers["Content-Disposition"]
        assert not [h for h in fetched.headers.keys() if h.lower().startswith("x-slice")]   # the file, and only it
        fetched.close()
        summary = client.get(f"/slices/{body['job']}/summary", headers=HEADERS)
        assert summary.status_code == 200 and summary.mimetype == "application/json"
        assert summary.get_json() == {"file": "Box-20261009-1432.gcode.3mf", "instances": 1, "print_time_s": 600.0,
                                      "filament_m": 1.5, "filament_g": 4.5, "layer_count": 42, "warnings": [],
                                      "part_warnings": []}
        from penguin_slice.service import SUMMARY_FIELDS
        assert list(json.loads(summary.data)) == list(SUMMARY_FIELDS)              # the contract's order
        assert [e["state"] for e in logs] == ["queued", "running", "done"]
        assert logs[-1]["parts"]["box"]["triangles"] == 12 and logs[-1]["parts"]["box"]["sha256"] == sha256(BOX)
        assert (logs[-1]["user_key"], logs[-1]["plate_id"], logs[-1]["submission_id"]) == \
            (USER_KEY, PLATE_ID, SUBMISSION_ID)

    def test_the_contracts_phase_2_example_is_accepted_after_its_two_parts_are_uploaded(self, work):
        client, _pool, _logs = app_with(work, executor=HeldExecutor(), upload_box=False)
        example = json.loads((EXAMPLES / "plate-configuration-phase-2.json").read_text())      # sent as it is
        refused = submit(client, example)
        assert refused.status_code == 422
        assert refused.get_json() == json.loads((EXAMPLES / "error-report-parts-missing.json").read_text())
        for name in ("bracket.stl", "spacer.stl"):
            assert upload(client, (EXAMPLES / "parts" / name).read_bytes()).status_code == 201
        answer = submit(client, example)                     # the same submission_id, again
        assert answer.status_code == 202, answer.get_json()
        body = answer.get_json()
        expected = json.loads((EXAMPLES / "slice-http" / "slice-accepted.json").read_text())
        assert set(body) == set(expected)
        assert {k: body[k] for k in ("plate_id", "submission_id", "part_warnings")} == \
            {k: expected[k] for k in ("plate_id", "submission_id", "part_warnings")}
        assert (body["progress"]["state"], body["progress"]["sequence"], body["progress"]["ahead"]) == ("queued", 1, 0)
        assert set(body["progress"]) == set(expected["progress"])

    def test_slicing_again_uploads_nothing(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, _logs = app_with(work)
        first = submit(client, plate_configuration()).get_json()
        second = submit(client, plate_configuration(submission_id="submission-2")).get_json()
        assert first["progress"]["state"] == second["progress"]["state"] == "done" and first["job"] != second["job"]

    def test_a_slice_job_holds_its_parts_so_their_removal_does_not_touch_it(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        store = PartStore(work / "store", 1024 * 1024)
        client, pool, _logs = app_with(work, executor=HeldExecutor(), store=store)
        job_id = submit(client, plate_configuration()).get_json()["job"]
        store._ttl_s = 0
        assert store.sweep() == 1 and len(store) == 0             # the part is gone from the part store
        pool._executor.run_next()
        assert pool.get(job_id)["state"] == "done"

    def test_a_submission_counts_as_a_use_of_each_part(self, work):
        clock = [100.0]
        store = PartStore(work / "store", 1024 * 1024, clock=lambda: clock[0])
        client, _pool, _logs = app_with(work, executor=HeldExecutor(), store=store)
        clock[0] += 7000
        assert submit(client, plate_configuration()).status_code == 202
        clock[0] += 7000
        assert store.sweep() == 0 and len(store) == 1
        clock[0] += 200
        assert store.sweep() == 1

    def test_a_part_removed_between_the_check_and_the_hold_is_missing(self, work, monkeypatch):
        from penguin_slice import service
        client, _pool, logs = app_with(work, executor=HeldExecutor())
        store = client.application.extensions["penguin_slice_store"]
        real = service.read_plate_configuration

        def read_then_lose(*args, **kwargs):
            configuration = real(*args, **kwargs)
            store._remove(store.get(USER_KEY, sha256(BOX), "mm"))
            return configuration
        monkeypatch.setattr("penguin_slice.web.read_plate_configuration", read_then_lose)
        answer = submit(client, plate_configuration())
        assert answer.status_code == 422
        assert answer.get_json()["where"]["missing_parts"] == [{"key": "box", "sha256": sha256(BOX), "units": "mm"}]
        assert job_folders(work) == [] and logs[-1]["state"] == "refused"

    def test_the_summary_of_25_warned_parts_is_a_body_not_a_header(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, _logs = app_with(work)
        stls = [box_stl(2, 1, 0.5 + i / 100) for i in range(25)]          # each warns: inches?
        for data in stls:
            assert upload(client, data).status_code == 201
        parts = {f"p{i}": part_entry(f"Inch-drawn spacer number {i:02d} " + "x" * 150, data)
                 for i, data in enumerate(stls)}
        instances = [{"ref": f"p{i}", "orientation": "+z", "angle": 0, "x": 20.0 + 30 * (i % 10),
                      "y": 20.0 + 30 * (i // 10)} for i in range(25)]
        job_id = submit(client, plate_configuration(parts=parts, instances=instances)).get_json()["job"]
        fetched = client.get(f"/slices/{job_id}/file", headers=HEADERS)
        assert fetched.status_code == 200 and sum(len(k) + len(v) for k, v in fetched.headers.items()) < 1000
        fetched.close()
        summary = client.get(f"/slices/{job_id}/summary", headers=HEADERS).get_json()
        assert len(summary["part_warnings"]) == 25 and summary["instances"] == 25

    def test_the_summary_answers_as_the_file_does_for_a_slice_job_without_one(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "segv")
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        unknown = [client.get(f"/slices/j0000/{route}", headers=HEADERS) for route in ("file", "summary")]
        assert [(a.status_code, a.get_json()["code"]) for a in unknown] == [(404, "slice.unknown_job")] * 2
        job_id = submit(client, plate_configuration()).get_json()["job"]
        queued = [client.get(f"/slices/{job_id}/{route}", headers=HEADERS) for route in ("file", "summary")]
        assert [(a.status_code, a.get_json()["code"]) for a in queued] == [(409, "slice.not_ready")] * 2
        pool._executor.run_next()
        failed = [client.get(f"/slices/{job_id}/{route}", headers=HEADERS) for route in ("file", "summary")]
        assert [(a.status_code, a.get_json()["code"]) for a in failed] == [(409, "slice.orca_crashed")] * 2
        assert failed[0].get_json() == failed[1].get_json()
        cancelled_id = submit(client, plate_configuration()).get_json()["job"]
        client.delete(f"/slices/{cancelled_id}", headers=HEADERS)
        cancelled = [client.get(f"/slices/{cancelled_id}/{route}", headers=HEADERS) for route in ("file", "summary")]
        assert [(a.status_code, a.get_json()["code"]) for a in cancelled] == [(409, "slice.cancelled")] * 2

    def test_the_summary_of_a_sliced_file_gone_from_the_disk_is_gone_too(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, pool, _logs = app_with(work)
        job_id = submit(client, plate_configuration()).get_json()["job"]
        Path(pool.result(job_id)["path"]).unlink()
        gone = [client.get(f"/slices/{job_id}/{route}", headers=HEADERS) for route in ("file", "summary")]
        assert [(a.status_code, a.get_json()["code"]) for a in gone] == [(410, "slice.file_gone")] * 2

    def test_the_reference_plate_of_100_spacers_is_accepted(self, tmp_path, monkeypatch, work):
        # 100 instances of one part: one part uploaded, and the slice job is queued.
        from helpers import spacer_grid, spacer_stl
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, _logs = app_with(work, executor=HeldExecutor())
        assert upload(client, spacer_stl()).status_code == 201
        job = plate_configuration(parts={"spacer": part_entry("Spacer", spacer_stl())}, instances=spacer_grid(100))
        answer = submit(client, job)
        assert answer.status_code == 202, answer.get_json()

    def test_a_bad_setting_stops_the_app_at_start(self, work):
        from penguin_slice.limits import SettingError
        for environ, name in (({"PENGUIN_SLICE_MAX_PEAK_MB": "²"}, "PENGUIN_SLICE_MAX_PEAK_MB"),
                              ({"PENGUIN_SLICE_PART_STORE_MAX_MB": "1"}, "PENGUIN_SLICE_PART_STORE_MAX_MB")):
            with pytest.raises(SettingError, match=name):
                create_app(work, start_sweeper=False, environ=environ)
            assert not work.exists()

    def test_progress_and_events(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = submit(client, plate_configuration()).get_json()["job"]
        assert client.get(f"/slices/{job_id}", headers=HEADERS).get_json()["state"] == "queued"
        pool._executor.run_next()
        stream = client.get(f"/slices/{job_id}/events", headers=HEADERS)
        assert stream.mimetype == "text/event-stream" and stream.headers["Cache-Control"] == "no-store"
        events = [json.loads(line[6:]) for line in stream.get_data(as_text=True).splitlines()
                  if line.startswith("data: ")]
        assert [e["state"] for e in events] == ["done"]          # a late subscriber: the latest at once

    def test_the_stream_follows_a_running_job_to_its_end(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "hang")
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = submit(client, plate_configuration()).get_json()["job"]
        runner = threading.Thread(target=pool._executor.run_next)
        runner.start()
        stream = client.get(f"/slices/{job_id}/events", headers=HEADERS, buffered=False)
        reports = []
        for chunk in stream.response:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            report = json.loads(text.split("data: ", 1)[1])
            reports.append(report)
            if report.get("stage") == "slicing_mesh":
                assert client.delete(f"/slices/{job_id}", headers=HEADERS).get_json()["cancel"] == "cancelling"
            if report["state"] in FINAL:
                break
        stream.close()
        runner.join(FAILSAFE_S)
        assert reports[-1]["state"] == "cancelled"
        sequences = [r["sequence"] for r in reports]
        assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences)
        assert job_folders(work) == []             # its hold on the parts and its scratch removed

    def test_a_failed_job_leaves_no_files(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "segv")
        client, _pool, _logs = app_with(work)
        job_id = submit(client, plate_configuration()).get_json()["job"]
        assert client.get(f"/slices/{job_id}", headers=HEADERS).get_json()["error"]["code"] == "slice.orca_crashed"
        assert job_folders(work) == []
        assert len(client.application.extensions["penguin_slice_store"]) == 1      # the part stays in the store

    def test_part_warnings_come_back_at_once_naming_the_part(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, _logs = app_with(work)
        small = box_stl(2, 1, 0.5)
        upload(client, small)
        body = submit(client, plate_configuration(parts={"box": part_entry("Box", small)})).get_json()
        assert [(w["code"], w["where"]) for w in body["part_warnings"]] == [("slice.part_maybe_inches", {"part": "Box"})]
        assert body["part_warnings"][0]["message"].startswith("Box is only 2.0 x 1.0 x 0.5 mm")

    def test_a_part_in_inches_is_sliced_at_its_size_in_millimetres(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, _logs = app_with(work, executor=HeldExecutor())
        small = box_stl(2, 1, 0.5)
        upload(client, small, units="in")
        inches = plate_configuration(parts={"box": part_entry("Box", small, "in")})
        assert submit(client, inches).status_code == 202
        inches["instances"][0]["x"] = 26.0                          # 50.8 mm wide: its edge at 0.6 mm
        inches["submission_id"] = "submission-moved"                # a new submission, not a repeat
        assert submit(client, inches).get_json()["code"] == "slice.placement_off_plate"
        millimetres = plate_configuration(parts={"box": part_entry("Box", small, "mm")})
        assert submit(client, millimetres).get_json()["code"] == "slice.part_missing"   # uploaded under in only


class TestRefusals:
    def test_a_multipart_body_is_refused(self, work):
        import io
        client, _pool, logs = app_with(work)
        answer = client.post("/slices", headers=HEADERS,
                             data={"plate_configuration": json.dumps(plate_configuration()),
                                   "box.stl": (io.BytesIO(BOX), "box.stl")})
        assert answer.status_code == 400
        body = answer.get_json()
        assert_error_report(body, "slice.bad_plate_configuration")
        assert body["detail"] == "it is a multipart form, not a JSON body"
        assert logs[-1]["state"] == "refused"

    @pytest.mark.parametrize("raw", [b"{not json", b"[" * 100_000, b"", b"\xff\xfe"])
    def test_a_body_that_is_not_json(self, work, raw):
        client, _pool, _logs = app_with(work)
        answer = client.post("/slices", data=raw, headers=HEADERS, content_type="application/json")
        assert answer.status_code == 400
        assert answer.get_json()["message"] == "This plate configuration could not be read: it is not JSON."

    def test_a_refused_plate_configuration_leaves_nothing(self, work):
        client, _pool, _logs = app_with(work)
        answer = submit(client, plate_configuration(instances=[]))
        assert answer.status_code == 400
        assert_error_report(answer.get_json(), "slice.bad_plate_configuration")
        assert job_folders(work) == []

    def test_a_placement_refusal_is_422(self, work):
        client, _pool, _logs = app_with(work)
        answer = submit(client, plate_configuration(instances=[{"ref": "box", "orientation": "+z", "angle": 0,
                                                                "x": 1.0, "y": 50.0}]))
        assert (answer.status_code, answer.get_json()["code"]) == (422, "slice.placement_off_plate")

    def test_parts_never_uploaded_are_listed(self, work):
        client, _pool, _logs = app_with(work, upload_box=False)
        answer = submit(client, plate_configuration())
        assert answer.status_code == 422
        assert answer.get_json()["where"]["missing_parts"] == [{"key": "box", "sha256": sha256(BOX), "units": "mm"}]

    def test_a_part_of_user_key_a_is_missing_for_user_key_b(self, work):
        client, _pool, _logs = app_with(work)
        answer = submit(client, plate_configuration(), user_key="user-b")
        assert answer.status_code == 422 and answer.get_json()["code"] == "slice.part_missing"
        assert submit(client, plate_configuration()).status_code == 202

    def test_an_instance_naming_no_part_keeps_part_missing_without_a_list(self, work):
        client, _pool, _logs = app_with(work)
        answer = submit(client, plate_configuration(parts={}))
        assert answer.status_code == 422
        assert answer.get_json()["code"] == "slice.part_missing" and "missing_parts" not in answer.get_json()["where"]

    def test_queue_full_is_503(self, work):
        client, _pool, _logs = app_with(work, executor=HeldExecutor(), max_queued=1)
        for plate in ("plate-1", "plate-2"):            # the two places: one to run, one to wait
            assert submit(client, plate_configuration(plate_id=plate)).status_code == 202
        answer = submit(client, plate_configuration(plate_id="plate-3"))
        assert answer.status_code == 503
        assert_error_report(answer.get_json(), "slice.busy")
        assert len(job_folders(work)) == 2

    def test_the_most_bytes_are_accepted_and_one_more_refused_before_it_is_read(self, work):
        client, _pool, _logs = app_with(work, executor=HeldExecutor())
        body = json.dumps(plate_configuration())
        padded = body[:-1] + " " * (limits.MAX_PLATE_CONFIGURATION_BYTES - len(body)) + "}"
        assert len(padded.encode()) == limits.MAX_PLATE_CONFIGURATION_BYTES
        accepted = client.post("/slices", data=padded, headers=HEADERS, content_type="application/json")
        assert accepted.status_code == 202, accepted.get_json()
        body = UnreadBody()
        refused = client.post("/slices", input_stream=body, content_type="application/json", headers=HEADERS,
                              environ_overrides={"CONTENT_LENGTH": str(limits.MAX_PLATE_CONFIGURATION_BYTES + 1)})
        assert refused.status_code == 413 and body.reads == []
        assert refused.get_json() == json.loads(
            (EXAMPLES / "error-report-plate-configuration-over-size.json").read_text())

    def test_a_body_without_a_length_over_the_limit_is_refused(self, work):
        client, _pool, _logs = app_with(work)
        answer = streamed(client, "/slices", b" " * (limits.MAX_PLATE_CONFIGURATION_BYTES + 1), "application/json")
        assert answer.status_code == 413
        assert answer.get_json()["detail"] == "plate configuration of 1,048,577 bytes, cap 1,048,576"

    def test_a_body_without_a_length_within_the_limit_is_read(self, work):
        client, _pool, _logs = app_with(work, executor=HeldExecutor())
        answer = streamed(client, "/slices", json.dumps(plate_configuration()).encode(), "application/json")
        assert answer.status_code == 202

    def test_a_body_without_a_length_is_read_no_further_than_the_largest_body(self, work):
        from penguin_slice.web import MAX_BODY_BYTES
        client, _pool, logs = app_with(work)
        answer = streamed(client, "/slices", b" " * (MAX_BODY_BYTES + 1000), "application/json")
        assert answer.status_code == 413
        assert answer.get_json()["detail"] == f"plate configuration of {MAX_BODY_BYTES:,} bytes, cap 1,048,576"
        assert logs[-1]["state"] == "refused"


class TestEveryPlateConfigurationIsLogged:
    """Every plate configuration that reaches POST /slices leaves one log line with its
    outcome: the queued ones through the pool, every other one as a refusal with its error
    code, its detail, its user key, the parts it named and its size in bytes."""

    def refusal(self, work, monkeypatch, data, status, code, *, setup=None, raw=None, **app_kwargs):
        client, _pool, logs = app_with(work, **app_kwargs)
        if setup:
            setup(client, monkeypatch)
        if raw is None:
            answer = submit(client, data)
        else:
            answer = client.post("/slices", data=raw, headers=HEADERS, content_type="application/json")
        assert answer.status_code == status
        body = answer.get_json()
        assert body["code"] == code
        refused = [e for e in logs if e.get("state") == "refused"]
        assert len(refused) == 1, logs
        line = refused[0]
        assert (line["event"], line["error_code"], line["error_detail"], line["http_status"], line["user_key"]) == \
            ("slice_job", code, body["detail"], status, USER_KEY)
        return line

    def test_a_placement_refused(self, work, monkeypatch):
        data = plate_configuration(instances=[{"ref": "box", "orientation": "+z", "angle": 0, "x": 1.0, "y": 50.0}])
        line = self.refusal(work, monkeypatch, data, 422, "slice.placement_off_plate")
        assert line["parts"] == {"box": {"name": "Box", "sha256": sha256(BOX), "units": "mm"}}
        assert line["bytes"] == len(json.dumps(data))

    def test_a_plate_configuration_that_is_not_json(self, work, monkeypatch):
        line = self.refusal(work, monkeypatch, None, 400, "slice.bad_plate_configuration", raw="{not json")
        assert line["parts"] is None and line["bytes"] == 9

    def test_the_queue_full(self, work, monkeypatch):
        client, _pool, logs = app_with(work, executor=HeldExecutor(), max_queued=0)
        assert submit(client, plate_configuration(plate_id="plate-1")).status_code == 202
        assert submit(client, plate_configuration(plate_id="plate-2")).status_code == 503
        assert [e["state"] for e in logs] == ["queued", "refused"]
        assert logs[-1]["error_code"] == "slice.busy"

    def test_a_work_folder_that_cannot_be_written(self, work, monkeypatch):
        def refuse(client, monkeypatch):
            monkeypatch.setattr("penguin_slice.web.make_scratch",
                                lambda root: (_ for _ in ()).throw(PermissionError(13, "Permission denied")))
        line = self.refusal(work, monkeypatch, plate_configuration(), 500, "slice.scratch_unwritable", setup=refuse)
        assert "PermissionError" in line["error_detail"]

    def test_a_full_disk_while_the_parts_are_held(self, work, monkeypatch):
        def full(client, monkeypatch):
            monkeypatch.setattr("penguin_slice.part_store.os.link",
                                lambda *a: (_ for _ in ()).throw(OSError(28, "No space left on device")))
            monkeypatch.setattr("penguin_slice.part_store.shutil.copyfile",
                                lambda *a: (_ for _ in ()).throw(OSError(28, "No space left on device")))
        line = self.refusal(work, monkeypatch, plate_configuration(), 500, "slice.scratch_unwritable", setup=full)
        assert "No space left on device" in line["error_detail"] and "holding the parts" in line["error_detail"]
        assert job_folders(work) == []

    def test_a_bug_while_a_plate_configuration_arrives(self, work, monkeypatch):
        def bug(client, monkeypatch):
            monkeypatch.setattr("penguin_slice.web.read_plate_configuration", lambda *a, **k: 1 / 0)
        line = self.refusal(work, monkeypatch, plate_configuration(), 500, "slice.unexpected", setup=bug)
        assert "ZeroDivisionError" in line["traceback"]

    def test_a_bug_while_the_slice_job_is_queued_leaves_no_folder(self, work, monkeypatch):
        def bug(client, monkeypatch):
            pool = client.application.extensions["penguin_slice_pool"]
            monkeypatch.setattr(pool, "submit", lambda *a, **k: 1 / 0)
        self.refusal(work, monkeypatch, plate_configuration(), 500, "slice.unexpected", setup=bug)
        assert job_folders(work) == []

    def test_an_http_error_while_a_plate_configuration_arrives_is_logged_too(self, work, monkeypatch):
        from werkzeug.exceptions import BadRequest
        client, _pool, logs = app_with(work)

        def bad_request(raw):
            raise BadRequest()
        monkeypatch.setattr("penguin_slice.web.json.loads", bad_request)
        assert submit(client, plate_configuration()).status_code == 400
        assert [(e["state"], e["error_code"], e["http_status"]) for e in logs] == \
            [("refused", "slice.bad_request", 400)]

    def test_a_delivered_slice_over_the_ceiling_is_noted_in_its_result_and_log(self, tmp_path, monkeypatch, work):
        # The watchdog's one reading, taken as the stand-in exits, passes a 1 MB ceiling.
        from penguin_slice import slicer
        monkeypatch.setattr(slicer, "MEMORY_READER", lambda pgid: (
            os.waitid(os.P_PID, pgid, os.WEXITED | os.WNOWAIT), (0, 2048))[1])
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, pool, logs = app_with(work, environ={"PENGUIN_SLICE_MAX_PEAK_MB": "1"})
        job_id = submit(client, plate_configuration()).get_json()["job"]
        assert client.get(f"/slices/{job_id}", headers=HEADERS).get_json()["state"] == "done"
        note = pool.result(job_id)["memory_note"]
        assert "over the ceiling of 1,024 kB" in note and note.endswith("the sliced file is delivered")
        assert (logs[-1]["state"], logs[-1]["memory_note"]) == ("done", note)
        assert logs[-1]["peak_rss_kb"] == 2048

    def test_a_log_that_fails_changes_no_answer_and_no_job(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")

        def broken(entry):
            raise BrokenPipeError(32, "Broken pipe")
        app = create_app(work, start_sweeper=False, log=broken)
        app.extensions["penguin_slice_pool"]._executor = ImmediateExecutor()
        client = app.test_client()
        assert upload(client, BOX).status_code == 201
        refused = client.post("/slices", data="not json", headers=HEADERS, content_type="application/json")
        assert refused.status_code == 400 and refused.get_json()["code"] == "slice.bad_plate_configuration"
        job_id = submit(client, plate_configuration()).get_json()["job"]
        assert client.get(f"/slices/{job_id}", headers=HEADERS).get_json()["state"] == "done"
        assert client.get(f"/slices/{job_id}/file", headers=HEADERS).status_code == 200
        assert app.extensions["penguin_slice_pool"].log_failures() == 5    # upload, refused, queued, running, done

    def test_a_stop_after_the_file_is_complete_delivers_it_with_the_stop_in_the_log(self, tmp_path, monkeypatch,
                                                                                     work, timers):
        # The timeout fires in the moment between Orca writing its sliced file and exiting.
        install_fake_orca(tmp_path, monkeypatch, "written_then_hang")
        client, pool, logs = app_with(work)
        real = pool._progress

        def progress(job_id, stage, fraction):
            real(job_id, stage, fraction)
            if fraction == 1.0:                       # "All done, Success"
                timers.made[-1].fire()
        pool._progress = progress
        job_id = submit(client, plate_configuration()).get_json()["job"]
        assert client.get(f"/slices/{job_id}", headers=HEADERS).get_json()["state"] == "done"
        note = pool.result(job_id)["stop_note"]
        assert note.startswith("stopped by the slice service (timeout) with SIGTERM after ")
        assert (logs[-1]["state"], logs[-1]["stop_note"]) == ("done", note)
        assert client.get(f"/slices/{job_id}/file", headers=HEADERS).status_code == 200

    def test_parts_that_are_not_objects_are_named_as_such(self):
        from penguin_slice.web import _parts_named
        assert _parts_named({"parts": {"a": "x"}}) == {"a": {"name": None, "sha256": None, "units": None}}


class TestJobs:
    def test_unknown_job_everywhere(self, work):
        client, _pool, _logs = app_with(work)
        for method, path in (("get", "/slices/jnope"), ("get", "/slices/jnope/events"),
                             ("delete", "/slices/jnope"), ("get", "/slices/jnope/file")):
            answer = getattr(client, method)(path, headers=HEADERS)
            assert answer.status_code == 404, path
            assert_error_report(answer.get_json(), "slice.unknown_job")

    def test_file_of_a_failed_job_is_its_error_report(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "refuse")
        client, _pool, _logs = app_with(work)
        job_id = submit(client, plate_configuration()).get_json()["job"]
        answer = client.get(f"/slices/{job_id}/file", headers=HEADERS)
        assert answer.status_code == 409
        assert_error_report(answer.get_json(), "slice.orca_too_close")

    def test_file_of_a_queued_job_is_not_ready(self, work):
        client, _pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = submit(client, plate_configuration()).get_json()["job"]
        answer = client.get(f"/slices/{job_id}/file", headers=HEADERS)
        assert answer.status_code == 409
        assert_error_report(answer.get_json(), "slice.not_ready")

    def test_cancel_a_queued_job_removes_its_files(self, work):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = submit(client, plate_configuration()).get_json()["job"]
        assert len(job_folders(work)) == 1
        body = client.delete(f"/slices/{job_id}", headers=HEADERS).get_json()
        assert (body["cancel"], body["progress"]["state"]) == ("cancelled", "cancelled")
        answer = client.get(f"/slices/{job_id}/file", headers=HEADERS)
        assert answer.status_code == 409
        assert_error_report(answer.get_json(), "slice.cancelled")
        assert client.delete(f"/slices/{job_id}", headers=HEADERS).get_json()["cancel"] == "finished"
        assert job_folders(work) == []

    def test_a_cancel_of_a_job_gone_between_two_looks_is_unknown(self, work, monkeypatch):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = submit(client, plate_configuration()).get_json()["job"]
        monkeypatch.setattr(pool, "cancel", lambda job_id: "unknown")
        assert client.delete(f"/slices/{job_id}", headers=HEADERS).status_code == 404

    @pytest.mark.parametrize("route", ["", "/file", "/summary"])
    def test_a_slice_job_gone_between_two_looks_is_unknown(self, work, monkeypatch, route):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = submit(client, plate_configuration()).get_json()["job"]
        monkeypatch.setattr(pool, "get", lambda job_id: None)        # it expired after the user key's check
        answer = client.get(f"/slices/{job_id}{route}", headers=HEADERS)
        assert (answer.status_code, answer.get_json()["code"]) == (404, "slice.unknown_job")

    def test_a_done_job_expires_with_its_files(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        clock = [1000.0]
        client, pool, _logs = app_with(work, clock=lambda: clock[0], ttl_s=60)
        job_id = submit(client, plate_configuration()).get_json()["job"]
        assert len(job_folders(work)) == 1
        clock[0] += 60
        pool.sweep()
        assert job_folders(work) == []
        assert client.get(f"/slices/{job_id}", headers=HEADERS).status_code == 404


class FirstAtOnce:
    """Runs the first slice job submitted at once, on the calling thread, and holds the rest."""

    def __init__(self):
        self.held = []

    def submit(self, fn, *args):
        if self.held is None or self.held:
            self.held.append((fn, args))
        else:
            self.held.append(None)            # the first: run now, and hold every later one
            fn(*args)


class TestStopDuringThePlateWrite:
    """A cancel, a replacement and a shutdown that come while the plate is being written:
    the write ends at the next object, Orca is never started, every file is removed. The
    stop is set from inside the write, after the first part's mesh, so nothing waits."""

    def run(self, tmp_path, monkeypatch, work, stop_with):
        """Submit three parts, interleaved; `stop_with(pool, job_id, clock)` runs during the
        write (self.client is the app's client by then). (the POST's answer, the meshes
        built, the Orca runs, the log lines)"""
        from penguin_slice import plate_3mf, slicer
        install_fake_orca(tmp_path, monkeypatch, "ok")
        clock, seen, built, orca_runs, logs = [1000.0], [], [], [], []
        real_mesh_xml = plate_3mf._mesh_xml

        def worker(job_id, configuration, context):
            seen.append(job_id)
            return slice_worker(job_id, configuration, context)

        def mesh_xml(stl_path, name, scale):
            built.append(name)
            if len(built) == 1:
                stop_with(pool, seen[0], clock)
            return real_mesh_xml(stl_path, name, scale)

        monkeypatch.setattr(plate_3mf, "_mesh_xml", mesh_xml)
        monkeypatch.setattr(slicer, "run_process", lambda *args, **kwargs: orca_runs.append(args))
        pool = JobPool(worker, executor=FirstAtOnce(), error_report=error_report, cleanup=remove_job_files,
                       log=logs.append, clock=lambda: clock[0])
        client = self.client = create_app(work, pool, start_sweeper=False, log=logs.append).test_client()
        stls = {ref: box_stl(10, 10, 5 + n) for n, ref in enumerate("abc")}
        for data in stls.values():
            upload(client, data)
        parts = {ref: part_entry(name, stls[ref]) for ref, name in (("a", "Arm"), ("b", "Bolt"), ("c", "Cap"))}
        instances = [{"ref": ref, "orientation": "+z", "angle": 0, "x": 30.0 + 30 * n, "y": 50.0}
                     for n, ref in enumerate("abcabc")]
        self.later = plate_configuration(parts=parts, instances=instances)
        answer = submit(client, plate_configuration(parts=parts, instances=instances))
        return client, answer, built, orca_runs, logs

    def assert_stopped_in_the_write(self, client, answer, built, orca_runs, logs, work, reason, folders=0):
        assert answer.status_code == 202
        job_id = answer.get_json()["job"]
        assert answer.get_json()["progress"]["state"] == "cancelled"
        assert answer.get_json()["progress"]["cancel_reason"] == reason
        assert built == ["Arm"]                      # the write ended before the next part's mesh
        assert orca_runs == []                       # Orca was never started
        assert len(job_folders(work)) == folders     # every file of the stopped one removed
        last = [e for e in logs if e.get("job") == job_id][-1]
        assert (last["state"], last["cancel_reason"]) == ("cancelled", reason)
        assert_error_report(client.get(f"/slices/{job_id}/file", headers=HEADERS).get_json(), "slice.cancelled")

    def test_a_cancel_during_the_write(self, tmp_path, monkeypatch, work):
        answers = []
        outcome = self.run(tmp_path, monkeypatch, work,
                           lambda pool, job_id, clock: answers.append(pool.cancel(job_id)))
        assert answers == ["cancelling"]
        self.assert_stopped_in_the_write(*outcome, work, "requested")

    def test_a_replacement_during_the_write(self, tmp_path, monkeypatch, work):
        later = []

        def replace(pool, job_id, clock):
            later.append(submit(self.client, self.later))
        outcome = self.run(tmp_path, monkeypatch, work, replace)
        self.assert_stopped_in_the_write(*outcome, work, "replaced", folders=1)    # the later one's
        assert later[0].status_code == 202
        assert later[0].get_json()["progress"] == {**later[0].get_json()["progress"], "state": "queued", "ahead": 1}

    def test_a_shutdown_during_the_write(self, tmp_path, monkeypatch, work):
        outcome = self.run(tmp_path, monkeypatch, work, lambda pool, job_id, clock: pool.shutdown())
        self.assert_stopped_in_the_write(*outcome, work, "shutdown")


def wait_for_report(pool, job_id, predicate):
    """The slice job's first report for which predicate(report) holds, waiting on its reports."""
    report = pool.get(job_id)
    while not predicate(report):
        assert report["state"] not in FINAL, report
        report = pool.wait(job_id, report["sequence"], timeout=FAILSAFE_S)
    return report


class TestReplacementAndRepeat:
    """Item 7 through the HTTP interface: a plate's later slice replaces its earlier one, and
    a repeated submission is answered with its first attempt's slice job."""

    def test_a_later_plate_configuration_ends_the_earlier_one_while_it_waits(self, work):
        client, pool, logs = app_with(work, executor=HeldExecutor())
        earlier = submit(client, plate_configuration()).get_json()["job"]
        later = submit(client, plate_configuration())
        assert later.status_code == 202 and later.get_json()["job"] != earlier
        report = client.get(f"/slices/{earlier}", headers=HEADERS).get_json()
        assert (report["state"], report["cancel_reason"]) == ("cancelled", "replaced")
        assert later.get_json()["progress"]["ahead"] == 0
        assert len(job_folders(work)) == 1                         # the earlier one's files are gone
        assert [(e["job"] == earlier, e["state"]) for e in logs] == \
            [(True, "queued"), (True, "cancelled"), (False, "queued")]

    def test_a_later_plate_configuration_ends_the_earlier_one_while_a_hanging_orca_runs(self, tmp_path,
                                                                                       monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "hang")
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        earlier = submit(client, plate_configuration()).get_json()["job"]
        runner = threading.Thread(target=pool._executor.run_next)
        runner.start()
        wait_for_report(pool, earlier, lambda r: r.get("stage") == "slicing_mesh")     # Orca has spoken
        pids = [int(p.read_text()) for p in work.rglob("fake-orca.pid")]
        assert len(pids) == 1
        later = submit(client, plate_configuration()).get_json()
        assert later["progress"]["ahead"] == 1                     # the earlier one still holds Orca
        final = wait_for_report(pool, earlier, lambda r: r["state"] in FINAL)
        runner.join(FAILSAFE_S)
        assert (final["state"], final["cancel_reason"]) == ("cancelled", "replaced")
        with pytest.raises(ProcessLookupError):                    # Orca was gone before the report
            os.kill(pids[0], 0)
        assert pool.get(later["job"])["ahead"] == 0
        assert len(job_folders(work)) == 1

    def test_another_plate_and_another_user_keys_same_plate_are_untouched(self, work):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        assert upload(client, BOX, user_key="user-b").status_code == 201
        mine = submit(client, plate_configuration()).get_json()["job"]
        other_plate = submit(client, plate_configuration(plate_id="plate-2")).get_json()["job"]
        theirs = submit(client, plate_configuration(), user_key="user-b").get_json()["job"]
        assert [pool.get(j)["state"] for j in (mine, other_plate, theirs)] == ["queued"] * 3

    def test_with_every_place_taken_by_one_user_key_a_changed_plate_is_accepted_and_another_refused(self, work):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        jobs = [submit(client, plate_configuration(plate_id=f"plate-{n}")).get_json()["job"] for n in (1, 2, 3)]
        refused = submit(client, plate_configuration(plate_id="plate-4"))
        assert (refused.status_code, refused.get_json()["code"]) == (503, "slice.busy")
        changed = submit(client, plate_configuration(plate_id="plate-2"))
        assert changed.status_code == 202
        assert pool.get(jobs[1])["cancel_reason"] == "replaced"
        assert [pool.get(j)["state"] for j in (jobs[0], jobs[2])] == ["queued", "queued"]
        assert changed.get_json()["progress"]["ahead"] == 2

    def test_a_refused_change_leaves_the_earlier_slice_job_as_it_was(self, work):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        earlier = submit(client, plate_configuration()).get_json()["job"]
        off_plate = plate_configuration(instances=[{"ref": "box", "orientation": "+z", "angle": 0, "x": 1.0,
                                                    "y": 50.0}])
        assert submit(client, off_plate).status_code == 422
        assert submit(client, plate_configuration(parts={})).status_code == 422
        assert pool.get(earlier)["state"] == "queued" and pool.get(earlier)["sequence"] == 1

    def test_a_repeat_answers_the_first_attempts_slice_job(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, pool, logs = app_with(work, executor=HeldExecutor())
        small = box_stl(2, 1, 0.5)
        upload(client, small)
        data = plate_configuration(parts={"box": part_entry("Box", small)})
        first = submit(client, data).get_json()
        logs.clear()
        again = submit(client, data)
        assert again.status_code == 202 and again.get_json() == first
        assert len(job_folders(work)) == 1 and pool.counts()["queued"] == 1
        assert [(e["event"], e["job"], e["submission_id"]) for e in logs] == \
            [("slice_repeat", first["job"], data["submission_id"])]
        pool._executor.run_next()
        later = submit(client, data).get_json()                    # after it ended: still that slice job
        assert later["job"] == first["job"] and later["progress"]["state"] == "done"
        assert later["part_warnings"] == first["part_warnings"] != []
        stream = client.get(f"/slices/{first['job']}/events", headers=HEADERS).get_data(as_text=True)
        reports = [json.loads(line[6:]) for line in stream.splitlines() if line.startswith("data: ")]
        assert reports[-1]["sequence"] == later["progress"]["sequence"]       # the sequence unbroken
        assert client.get(f"/slices/{first['job']}/file", headers=HEADERS).status_code == 200

    def test_a_repeat_is_answered_before_any_check(self, work):
        client, pool, _logs = app_with(work, executor=HeldExecutor(), max_queued=0)
        data = plate_configuration()
        first = submit(client, data).get_json()
        for changed in ({**data, "instances": []}, {**data, "unknown": 1}, {**data, "parts": {}}):
            answer = submit(client, changed)
            assert (answer.status_code, answer.get_json()["job"]) == (202, first["job"])
        assert pool.counts()["queued"] == 1                         # every place taken, and still answered

    def test_a_repeat_after_the_first_was_refused_is_checked_afresh(self, work):
        client, pool, _logs = app_with(work, executor=HeldExecutor(), upload_box=False)
        data = plate_configuration()
        refused = submit(client, data)
        assert refused.get_json()["code"] == "slice.part_missing"
        assert upload(client, BOX).status_code == 201
        accepted = submit(client, data)                             # the same submission_id, again
        assert accepted.status_code == 202 and pool.get(accepted.get_json()["job"])["state"] == "queued"

    def test_one_submission_value_under_two_user_keys_is_two_submissions(self, work):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        assert upload(client, BOX, user_key="user-b").status_code == 201
        data = plate_configuration()
        mine = submit(client, data).get_json()["job"]
        theirs = submit(client, data, user_key="user-b").get_json()["job"]
        assert mine != theirs and [pool.get(j)["state"] for j in (mine, theirs)] == ["queued", "queued"]

    def test_a_repeat_that_arrives_while_the_first_is_being_checked(self, work, monkeypatch):
        # Both attempts pass the first look; the pool, which decides under its lock, answers
        # the second with the first's slice job, and the second's folder is removed.
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        data = plate_configuration()
        first = submit(client, data).get_json()
        monkeypatch.setattr(pool, "remembered", lambda user_key, submission_id: None)
        again = submit(client, data)
        assert (again.status_code, again.get_json()) == (202, first)
        assert len(job_folders(work)) == 1 and pool.counts()["queued"] == 1

    def test_a_repeat_whose_slice_job_expires_as_it_is_looked_up_is_checked_afresh(self, work, monkeypatch):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        data = plate_configuration()
        first = submit(client, data).get_json()["job"]
        real = pool.payload
        gone = iter([True])
        # Its record is dropped between the look for it and the answer: a new submission after all.
        monkeypatch.setattr(pool, "payload", lambda job_id: None if next(gone, False) else real(job_id))
        monkeypatch.setattr(pool, "remembered", lambda user_key, submission_id: first)
        answer = submit(client, data)
        assert answer.status_code == 202, answer.get_json()

    def test_a_repeat_found_by_the_pool_whose_job_then_expires_is_tried_again(self, work, monkeypatch):
        # The pool refuses a repeat whose job is gone before its answer is made: the plate
        # configuration goes through again, and the pool's own look decides once more.
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        data = plate_configuration()
        first = submit(client, data).get_json()["job"]
        real_submit, real_payload = pool.submit, pool.payload
        calls = []

        def submit_once_as_repeat(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RepeatedSubmission(first)
            return real_submit(*args, **kwargs)
        monkeypatch.setattr(pool, "remembered", lambda user_key, submission_id: None)
        monkeypatch.setattr(pool, "submit", submit_once_as_repeat)
        monkeypatch.setattr(pool, "payload", lambda job_id: None if len(calls) == 1 else real_payload(job_id))
        answer = submit(client, data)
        assert (answer.status_code, answer.get_json()["job"], len(calls)) == (202, first, 2)
        assert len(job_folders(work)) == 1

    def test_a_repeat_of_a_body_that_is_not_an_object_is_no_repeat(self, work):
        client, _pool, _logs = app_with(work)
        for raw in ("[]", '{"submission_id": 7}'):
            answer = client.post("/slices", data=raw, headers=HEADERS, content_type="application/json")
            assert answer.get_json()["code"] == "slice.bad_plate_configuration"


class TestGoesOnWithoutItsPage:
    """Item 9 through the HTTP interface: nothing follows the slice job, and it ends done."""

    def test_a_slice_job_nobody_follows_past_120_s_ends_done_and_its_file_is_there(self, tmp_path, monkeypatch,
                                                                                  work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        clock = [1000.0]
        client, pool, _logs = app_with(work, executor=HeldExecutor(), clock=lambda: clock[0])
        job_id = submit(client, plate_configuration()).get_json()["job"]
        clock[0] += 121
        pool.sweep()
        pool._executor.run_next()
        clock[0] += 121
        pool.sweep()
        assert client.get(f"/slices/{job_id}", headers=HEADERS).get_json()["state"] == "done"
        assert client.get(f"/slices/{job_id}/file", headers=HEADERS).status_code == 200


class TestEveryAnswerIsAnErrorReport:
    """Every status of 400 or more the app gives is an error report, never Flask's HTML."""

    @pytest.mark.parametrize("method, path, status", [("get", "/nothing", 404), ("put", "/slices", 405),
                                                      ("get", "/slices", 405), ("post", "/slices/jx", 405),
                                                      ("put", "/parts", 405)])
    def test_a_path_or_method_not_offered(self, work, method, path, status):
        client, _pool, _logs = app_with(work)
        answer = getattr(client, method)(path, headers=HEADERS)
        assert answer.status_code == status and answer.is_json
        assert answer.headers["Cache-Control"] == "no-store"
        body = answer.get_json()
        assert_error_report(body, "slice.bad_request")
        assert body["message"] == f"The print server does not offer {method.upper()} {path}."

    def test_a_sliced_file_gone_from_the_disk(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, pool, _logs = app_with(work)
        job_id = submit(client, plate_configuration()).get_json()["job"]
        Path(pool.result(job_id)["path"]).unlink()
        answer = client.get(f"/slices/{job_id}/file", headers=HEADERS)
        assert answer.status_code == 410
        assert_error_report(answer.get_json(), "slice.file_gone")

    def test_a_work_folder_that_cannot_be_written(self, work, monkeypatch):
        client, _pool, _logs = app_with(work)

        def refuse(root):
            raise PermissionError(13, "Permission denied", str(root))
        monkeypatch.setattr("penguin_slice.web.make_scratch", refuse)
        answer = submit(client, plate_configuration())
        assert answer.status_code == 500
        body = answer.get_json()
        assert_error_report(body, "slice.scratch_unwritable")
        assert "PermissionError" in body["detail"]

    def test_a_bug_in_a_route_is_an_error_report_and_a_log_line(self, work, monkeypatch):
        client, pool, logs = app_with(work)
        monkeypatch.setattr(pool, "owned_by", lambda job_id, key: 1 / 0)
        answer = client.get("/slices/jx", headers=HEADERS)
        assert answer.status_code == 500
        assert_error_report(answer.get_json(), "slice.unexpected")
        assert logs[-1]["event"] == "slice_http_error" and "ZeroDivisionError" in logs[-1]["traceback"]
        assert logs[-1]["user_key"] == USER_KEY


def test_start_removes_scratch_of_a_dead_process_and_starts_the_sweeper(work, monkeypatch):
    (work / "slice-999999999-1-abc").mkdir(parents=True)
    (work / "slice-999999999-1-parts-abc").mkdir(parents=True)
    started = []
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a, **k: started.append((self, k)))
    app = create_app(work)
    assert not (work / "slice-999999999-1-abc").exists()
    assert not (work / "slice-999999999-1-parts-abc").exists()        # the earlier process's part store
    assert [pool for pool, _k in started] == [app.extensions["penguin_slice_pool"]]
    assert started[0][1]["also"] == (app.extensions["penguin_slice_store"].sweep,)
    app.extensions["penguin_slice_pool"].shutdown()


def test_a_start_empties_the_part_store(work):
    first = create_app(work, start_sweeper=False)
    client = first.test_client()
    assert upload(client, BOX).status_code == 201
    second = create_app(work, start_sweeper=False)
    assert len(second.extensions["penguin_slice_store"]) == 0
    assert second.extensions["penguin_slice_store"].root != first.extensions["penguin_slice_store"].root
    answer = submit(second.test_client(), plate_configuration())
    assert answer.get_json()["where"]["missing_parts"] == [{"key": "box", "sha256": sha256(BOX), "units": "mm"}]


def test_the_sweeper_sweeps_the_part_store(work, monkeypatch):
    from penguin_slice import jobs
    swept = threading.Event()
    store = PartStore(work / "store", 1024)
    monkeypatch.setattr(store, "sweep", swept.set)
    pool = JobPool(slice_worker)
    pool.start_sweeper(interval_s=0, also=(store.sweep,))           # no real interval: it waits on the event
    assert swept.wait(FAILSAFE_S)
    pool.shutdown()
    assert jobs.SWEEP_INTERVAL_S == 10


def test_default_work_dir_is_a_new_folder(monkeypatch, tmp_path):
    (tmp_path / "temp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a, **k: None)
    app = create_app()
    app.extensions["penguin_slice_pool"].shutdown()
    assert [p.name[:14] for p in (tmp_path / "temp").iterdir()] == ["penguin-slice-"]


def test_remove_job_files_without_a_folder():
    remove_job_files(None)


class TestSettingsTable:
    """Item 5: GET /settings-table answers the table whole, compressed when asked, for any
    caller: it answers for the whole slice service, so the user key is not looked at."""

    def test_the_table_whole_without_a_user_key(self, work):
        from penguin_slice.settings_table import TABLE_PATH
        client, _pool, _logs = app_with(work, upload_box=False)
        answer = client.get("/settings-table")
        assert answer.status_code == 200
        assert answer.mimetype == "application/json" and "Content-Encoding" not in answer.headers
        assert answer.data == TABLE_PATH.read_bytes()
        assert answer.headers["Cache-Control"] == "no-store" and answer.headers["Vary"] == "Accept-Encoding"
        assert client.get("/settings-table", headers=HEADERS).data == TABLE_PATH.read_bytes()   # a key changes nothing

    @pytest.mark.parametrize("accept", ["gzip", "gzip, deflate, br", "br;q=1.0, gzip;q=0.8", "*"])
    def test_compressed_when_the_request_accepts_it(self, work, accept):
        import gzip
        from penguin_slice.settings_table import TABLE_PATH
        client, _pool, _logs = app_with(work, upload_box=False)
        answer = client.get("/settings-table", headers={"Accept-Encoding": accept})
        assert answer.status_code == 200 and answer.headers["Content-Encoding"] == "gzip"
        assert int(answer.headers["Content-Length"]) == len(answer.data) < len(TABLE_PATH.read_bytes()) // 5
        assert gzip.decompress(answer.data) == TABLE_PATH.read_bytes()

    @pytest.mark.parametrize("accept", ["identity", "gzip;q=0", "deflate", "br"])
    def test_plain_when_the_request_does_not_accept_gzip(self, work, accept):
        from penguin_slice.settings_table import TABLE_PATH
        client, _pool, _logs = app_with(work, upload_box=False)
        answer = client.get("/settings-table", headers={"Accept-Encoding": accept})
        assert "Content-Encoding" not in answer.headers and answer.data == TABLE_PATH.read_bytes()

    def test_another_method_is_not_offered(self, work):
        client, _pool, _logs = app_with(work, upload_box=False)
        answer = client.post("/settings-table", data=b"{}")
        assert answer.status_code == 405
        assert_error_report(answer.get_json(), "slice.bad_request")

    def test_what_it_answers_is_what_the_service_accepts(self, work):
        """A setting of the answered table, set to a process profile's value, is accepted; one
        the table leaves out is refused."""
        client, _pool, _logs = app_with(work, upload_box=True)
        table = json.loads(client.get("/settings-table").data)
        name = table["settings"][0]["name"]
        value = table["process_values"]["0.24mm Balanced Quality @BBL H2S 0.6 nozzle"][name]
        assert submit(client, plate_configuration(overrides={name: value})).status_code == 202
        refused = submit(client, plate_configuration(overrides={"post_process": "true"}))
        assert refused.status_code == 422 and refused.get_json()["code"] == "slice.bad_overrides"
