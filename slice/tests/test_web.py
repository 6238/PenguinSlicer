"""web.py, the HTTP face, through Flask's test client and the fake Orca: submit a plate job,
follow its progress reports, cancel it, fetch the sliced file; every error answer is an
error report."""
import io
import json
import tempfile
import threading
from pathlib import Path

import pytest

from helpers import box_stl, install_fake_orca
from penguin_slice import error_report
from penguin_slice.jobs import FINAL, JobPool
from penguin_slice.web import create_app, remove_job_files, slice_worker

FAILSAFE_S = 10


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


def plate_job(**changes):
    job = {"parts": {"box": {"name": "Box", "stl": "box.stl"}},
           "copies": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0}],
           "local_time": "20261009-1432"}
    job.update(changes)
    return job


def form(job=None, files=None):
    data = {"plate_job": json.dumps(job or plate_job())}
    for name, content in (files if files is not None else {"box.stl": box_stl(20, 20, 10)}).items():
        data[name] = (io.BytesIO(content), name)
    return data


@pytest.fixture
def work(tmp_path):
    return tmp_path / "work"


def app_with(work, executor=None, **kwargs):
    logs = []
    pool = JobPool(slice_worker, executor=executor or ImmediateExecutor(), error_report=error_report,
                   cleanup=remove_job_files, log=logs.append, **kwargs)
    app = create_app(work, pool, start_sweeper=False, log=logs.append)
    return app.test_client(), pool, logs


def assert_error_report(body, code):
    assert body["code"] == code
    assert {"code", "message", "remedy", "retryable", "detail"} <= set(body)


class TestSubmit:
    def test_a_plate_job_is_sliced_and_its_file_fetched(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, logs = app_with(work)
        answer = client.post("/slices", data=form())
        assert answer.status_code == 202
        body = answer.get_json()
        assert body["part_warnings"] == [] and body["progress"]["state"] == "done"
        fetched = client.get(f"/slices/{body['job']}/file")
        assert fetched.status_code == 200
        assert fetched.data[:2] == b"PK"
        assert "Box-20261009-1432.gcode.3mf" in fetched.headers["Content-Disposition"]
        assert json.loads(fetched.headers["X-Slice-Summary"])["layer_count"] == 42
        fetched.close()
        assert [e["state"] for e in logs] == ["queued", "running", "done"]
        assert logs[-1]["parts"]["box"]["triangles"] == 12

    def test_progress_and_events(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = client.post("/slices", data=form()).get_json()["job"]
        assert client.get(f"/slices/{job_id}").get_json()["state"] == "queued"
        pool._executor.run_next()
        stream = client.get(f"/slices/{job_id}/events")
        assert stream.mimetype == "text/event-stream"
        events = [json.loads(line[6:]) for line in stream.get_data(as_text=True).splitlines()
                  if line.startswith("data: ")]
        assert [e["state"] for e in events] == ["done"]          # a late subscriber: the latest at once

    def test_the_stream_follows_a_running_job_to_its_end(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "hang")
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = client.post("/slices", data=form()).get_json()["job"]
        runner = threading.Thread(target=pool._executor.run_next)
        runner.start()
        stream = client.get(f"/slices/{job_id}/events", buffered=False)
        reports = []
        for chunk in stream.response:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            report = json.loads(text.split("data: ", 1)[1])
            reports.append(report)
            if report.get("stage") == "slicing_mesh":
                assert client.delete(f"/slices/{job_id}").get_json()["cancel"] == "cancelling"
            if report["state"] in FINAL:
                break
        stream.close()
        runner.join(FAILSAFE_S)
        assert reports[-1]["state"] == "cancelled"
        sequences = [r["sequence"] for r in reports]
        assert sequences == sorted(sequences) and len(set(sequences)) == len(sequences)
        assert list(work.iterdir()) == []             # uploads and scratch removed

    def test_a_failed_job_leaves_no_files(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "segv")
        client, _pool, _logs = app_with(work)
        job_id = client.post("/slices", data=form()).get_json()["job"]
        assert client.get(f"/slices/{job_id}").get_json()["error"]["code"] == "slice.orca_crashed"
        assert list(work.iterdir()) == []

    def test_part_warnings_come_back_at_once(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, _pool, _logs = app_with(work)
        body = client.post("/slices", data=form(files={"box.stl": box_stl(2, 1, 0.5)})).get_json()
        assert [w["code"] for w in body["part_warnings"]] == ["slice.part_maybe_inches"]


class TestRefusals:
    def test_no_plate_job_field(self, work):
        client, _pool, _logs = app_with(work)
        answer = client.post("/slices", data={})
        assert answer.status_code == 400
        assert_error_report(answer.get_json(), "slice.bad_plate_job")

    @pytest.mark.parametrize("raw", ["{not json", "[" * 100_000])
    def test_plate_job_that_is_not_json(self, work, raw):
        client, _pool, _logs = app_with(work)
        answer = client.post("/slices", data={"plate_job": raw})
        assert answer.status_code == 400
        assert answer.get_json()["message"] == "This plate job could not be read: its plate_job field is not JSON."

    def test_a_refused_plate_job_is_422_and_leaves_nothing(self, work):
        client, _pool, _logs = app_with(work)
        answer = client.post("/slices", data=form(files={"box.stl": b""}))
        assert answer.status_code == 422
        assert_error_report(answer.get_json(), "slice.part_unreadable")
        assert list(work.iterdir()) == []

    def test_a_part_file_not_sent(self, work):
        client, _pool, _logs = app_with(work)
        answer = client.post("/slices", data=form(files={}))
        assert answer.status_code == 422
        assert answer.get_json()["code"] == "slice.part_missing"

    def test_an_stl_path_outside_the_upload_is_refused(self, tmp_path, work):
        (tmp_path / "secret.stl").write_bytes(box_stl())
        client, _pool, _logs = app_with(work)
        for stl in ("../../secret.stl", str(tmp_path / "secret.stl")):
            job = plate_job(parts={"box": {"name": "Box", "stl": stl}})
            body = client.post("/slices", data=form(job)).get_json()
            assert body["code"] == "slice.part_missing"
            assert body["message"] == "The file for Box is not one of the files sent with this plate job."

    def test_an_upload_name_that_is_a_path_is_refused(self, work):
        client, _pool, _logs = app_with(work)
        answer = client.post("/slices", data=form(files={"../x.stl": box_stl()}))
        assert answer.status_code == 400
        assert "not a plain file name" in answer.get_json()["detail"]

    def test_queue_full_is_503(self, work):
        client, _pool, _logs = app_with(work, executor=HeldExecutor(), max_queued=1)
        assert client.post("/slices", data=form()).status_code == 202
        answer = client.post("/slices", data=form())
        assert answer.status_code == 503
        assert_error_report(answer.get_json(), "slice.busy")

    def test_an_upload_too_large(self, work):
        client, _pool, _logs = app_with(work)
        client.application.config["MAX_CONTENT_LENGTH"] = 1000
        answer = client.post("/slices", data=form(files={"box.stl": box_stl() * 3}))
        assert answer.status_code == 413
        assert answer.get_json()["message"] == "This plate job is too large to receive."


def full_disk(storage, destination, *args, **kwargs):
    raise OSError(28, "No space left on device")


class TestEveryPlateJobIsLogged:
    """Every plate job that reaches POST /slices leaves one log line with its outcome: the
    queued ones through the pool, every other one as a refusal with its error code, its
    detail, the parts it named and the sizes of the files it sent. Refusals were once
    answered and never logged."""

    def refusal(self, work, monkeypatch, data, status, code, *, setup=None, **app_kwargs):
        client, _pool, logs = app_with(work, **app_kwargs)
        if setup:
            setup(client, monkeypatch)
        answer = client.post("/slices", data=data)
        assert answer.status_code == status
        body = answer.get_json()
        assert body["code"] == code
        refused = [e for e in logs if e.get("state") == "refused"]
        assert len(refused) == 1, logs
        line = refused[0]
        assert (line["event"], line["error_code"], line["error_detail"], line["http_status"]) == \
            ("slice_job", code, body["detail"], status)
        return line

    def test_a_bad_stl_refused_on_arrival(self, work, monkeypatch):
        page = b"<!DOCTYPE html>\n<html><body><h1>502 Bad Gateway</h1>" + b" " * 100 + b"</body></html>\n"
        line = self.refusal(work, monkeypatch, form(files={"box.stl": page}), 422, "slice.part_unreadable")
        assert line["parts"] == {"box": {"name": "Box", "stl": "box.stl"}}
        assert line["uploads"] == {"box.stl": len(page)}

    def test_an_empty_stl(self, work, monkeypatch):
        line = self.refusal(work, monkeypatch, form(files={"box.stl": b""}), 422, "slice.part_unreadable")
        assert line["uploads"] == {"box.stl": 0}

    def test_a_plate_job_that_is_not_json(self, work, monkeypatch):
        line = self.refusal(work, monkeypatch, {"plate_job": "{not json", "box.stl": (io.BytesIO(b"x" * 7), "box.stl")},
                            400, "slice.bad_plate_job")
        assert line["parts"] is None and line["uploads"] == {"box.stl": 7}

    def test_no_plate_job_field(self, work, monkeypatch):
        self.refusal(work, monkeypatch, {}, 400, "slice.bad_plate_job")

    def test_an_upload_name_that_is_a_path(self, work, monkeypatch):
        self.refusal(work, monkeypatch, form(files={"../x.stl": box_stl()}), 400, "slice.bad_plate_job")

    def test_the_queue_full(self, work, monkeypatch):
        client, _pool, logs = app_with(work, executor=HeldExecutor(), max_queued=1)
        assert client.post("/slices", data=form()).status_code == 202
        assert client.post("/slices", data=form()).status_code == 503
        assert [e["state"] for e in logs] == ["queued", "refused"]
        assert logs[-1]["error_code"] == "slice.busy"

    def test_an_upload_too_large(self, work, monkeypatch):
        def small(client, _monkeypatch):
            client.application.config["MAX_CONTENT_LENGTH"] = 1000
        line = self.refusal(work, monkeypatch, form(files={"box.stl": box_stl() * 3}), 413, "slice.bad_plate_job",
                            setup=small)
        assert line["uploads"] is None                 # the body was never read

    def test_a_body_that_is_not_a_form(self, work):
        client, _pool, logs = app_with(work)
        answer = client.post("/slices", data=b"--x\r\nnot a form", content_type="multipart/form-data")
        assert answer.status_code == 400
        assert [e["state"] for e in logs] == ["refused"]

    def test_a_work_folder_that_cannot_be_written(self, work, monkeypatch):
        def refuse(client, monkeypatch):
            monkeypatch.setattr("penguin_slice.web.make_scratch",
                                lambda root: (_ for _ in ()).throw(PermissionError(13, "Permission denied")))
        self.refusal(work, monkeypatch, form(), 500, "slice.scratch_unwritable", setup=refuse)

    def test_a_full_disk_while_an_upload_is_saved(self, work, monkeypatch):
        # Once "The slicer failed unexpectedly." (slice.unexpected), and no log line.
        def disk(client, monkeypatch):
            monkeypatch.setattr("werkzeug.datastructures.FileStorage.save", full_disk)
        line = self.refusal(work, monkeypatch, form(), 500, "slice.scratch_unwritable", setup=disk)
        assert "No space left on device" in line["error_detail"] and "box.stl" in line["error_detail"]
        assert list(work.iterdir()) == []

    def test_a_bug_while_a_plate_job_arrives(self, work, monkeypatch):
        def bug(client, monkeypatch):
            monkeypatch.setattr("penguin_slice.web.read_plate_job", lambda *a, **k: 1 / 0)
        self.refusal(work, monkeypatch, form(), 500, "slice.unexpected", setup=bug)

    def test_a_bug_outside_the_plate_job_code_is_logged_too(self, work, monkeypatch):
        client, _pool, logs = app_with(work)
        monkeypatch.setattr("penguin_slice.web.json.loads", lambda raw: 1 / 0)    # not caught by submit
        assert client.post("/slices", data=form()).status_code == 500
        assert [(e["state"], e["error_code"]) for e in logs] == [("refused", "slice.unexpected")]
        assert "ZeroDivisionError" in logs[0]["traceback"]

    def test_an_http_error_while_a_plate_job_arrives_is_logged_too(self, work, monkeypatch):
        from werkzeug.exceptions import BadRequest
        client, _pool, logs = app_with(work)

        def bad_request(raw):
            raise BadRequest()
        monkeypatch.setattr("penguin_slice.web.json.loads", bad_request)
        assert client.post("/slices", data=form()).status_code == 400
        assert [(e["state"], e["error_code"], e["http_status"]) for e in logs] == \
            [("refused", "slice.bad_request", 400)]

    def test_a_delivered_slice_over_the_ceiling_is_noted_in_its_result_and_log(self, tmp_path, monkeypatch, work):
        # The stand-in's own ru_maxrss passes a 1 MB ceiling after the watchdog's last sample.
        install_fake_orca(tmp_path, monkeypatch, "ok")
        logs = []
        pool = JobPool(slice_worker, executor=ImmediateExecutor(), error_report=error_report,
                       cleanup=remove_job_files, log=logs.append)
        client = create_app(work, pool, start_sweeper=False, log=logs.append,
                            environ={"PENGUIN_SLICE_MAX_PEAK_MB": "1"}).test_client()
        job_id = client.post("/slices", data=form()).get_json()["job"]
        assert client.get(f"/slices/{job_id}").get_json()["state"] == "done"
        note = pool.result(job_id)["memory_note"]
        assert "over the ceiling of 1,024 kB" in note and note.endswith("the sliced file is delivered")
        assert (logs[-1]["state"], logs[-1]["memory_note"]) == ("done", note)
        assert logs[-1]["peak_rss_kb"] > 1024

    def test_a_log_that_fails_changes_no_answer_and_no_job(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")

        def broken(entry):
            raise BrokenPipeError(32, "Broken pipe")
        app = create_app(work, start_sweeper=False, log=broken)
        app.extensions["penguin_slice_pool"]._executor = ImmediateExecutor()
        client = app.test_client()
        refused = client.post("/slices", data={"plate_job": "not json"})
        assert refused.status_code == 400 and refused.get_json()["code"] == "slice.bad_plate_job"
        job_id = client.post("/slices", data=form()).get_json()["job"]
        assert client.get(f"/slices/{job_id}").get_json()["state"] == "done"
        assert client.get(f"/slices/{job_id}/file").status_code == 200
        assert app.extensions["penguin_slice_pool"].log_failures() == 4    # refused, queued, running, done

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
        job_id = client.post("/slices", data=form()).get_json()["job"]
        assert client.get(f"/slices/{job_id}").get_json()["state"] == "done"
        note = pool.result(job_id)["stop_note"]
        assert note.startswith("stopped by the slice service (timeout) with SIGTERM after ")
        assert (logs[-1]["state"], logs[-1]["stop_note"]) == ("done", note)
        assert client.get(f"/slices/{job_id}/file").status_code == 200

    def test_parts_that_are_not_objects_are_named_as_such(self):
        from penguin_slice.web import _parts_named
        assert _parts_named({"parts": {"a": "x"}}) == {"a": {"name": None, "stl": None}}


class TestJobs:
    def test_unknown_job_everywhere(self, work):
        client, _pool, _logs = app_with(work)
        for method, path in (("get", "/slices/jnope"), ("get", "/slices/jnope/events"),
                             ("delete", "/slices/jnope"), ("get", "/slices/jnope/file")):
            answer = getattr(client, method)(path)
            assert answer.status_code == 404, path
            assert_error_report(answer.get_json(), "slice.unknown_job")

    def test_file_of_a_failed_job_is_its_error_report(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "refuse")
        client, _pool, _logs = app_with(work)
        job_id = client.post("/slices", data=form()).get_json()["job"]
        answer = client.get(f"/slices/{job_id}/file")
        assert answer.status_code == 409
        assert_error_report(answer.get_json(), "slice.orca_too_close")

    def test_file_of_a_queued_job_is_not_ready(self, work):
        client, _pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = client.post("/slices", data=form()).get_json()["job"]
        answer = client.get(f"/slices/{job_id}/file")
        assert answer.status_code == 409
        assert_error_report(answer.get_json(), "slice.not_ready")

    def test_cancel_a_queued_job_removes_its_files(self, work):
        client, pool, _logs = app_with(work, executor=HeldExecutor())
        job_id = client.post("/slices", data=form()).get_json()["job"]
        assert len(list(work.iterdir())) == 1
        body = client.delete(f"/slices/{job_id}").get_json()
        assert (body["cancel"], body["progress"]["state"]) == ("cancelled", "cancelled")
        answer = client.get(f"/slices/{job_id}/file")
        assert answer.status_code == 409
        assert_error_report(answer.get_json(), "slice.cancelled")
        assert client.delete(f"/slices/{job_id}").get_json()["cancel"] == "finished"

    def test_a_done_job_expires_with_its_files(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        clock = [1000.0]
        client, pool, _logs = app_with(work, clock=lambda: clock[0], ttl_s=60)
        job_id = client.post("/slices", data=form()).get_json()["job"]
        assert len(list(work.iterdir())) == 1
        clock[0] += 60
        pool.sweep()
        assert list(work.iterdir()) == []
        assert client.get(f"/slices/{job_id}").status_code == 404


class TestEveryAnswerIsAnErrorReport:
    """Every status of 400 or more the app gives is an error report, never Flask's HTML."""

    @pytest.mark.parametrize("method, path, status", [("get", "/nothing", 404), ("put", "/slices", 405),
                                                      ("get", "/slices", 405), ("post", "/slices/jx", 405)])
    def test_a_path_or_method_not_offered(self, work, method, path, status):
        client, _pool, _logs = app_with(work)
        answer = getattr(client, method)(path)
        assert answer.status_code == status and answer.is_json
        body = answer.get_json()
        assert_error_report(body, "slice.bad_request")
        assert body["message"] == f"The print server does not offer {method.upper()} {path}."

    def test_a_sliced_file_gone_from_the_disk(self, tmp_path, monkeypatch, work):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        client, pool, _logs = app_with(work)
        job_id = client.post("/slices", data=form()).get_json()["job"]
        Path(pool.result(job_id)["path"]).unlink()
        answer = client.get(f"/slices/{job_id}/file")
        assert answer.status_code == 410
        assert_error_report(answer.get_json(), "slice.file_gone")

    def test_a_work_folder_that_cannot_be_written(self, work, monkeypatch):
        client, _pool, _logs = app_with(work)

        def refuse(root):
            raise PermissionError(13, "Permission denied", str(root))
        monkeypatch.setattr("penguin_slice.web.make_scratch", refuse)
        answer = client.post("/slices", data=form())
        assert answer.status_code == 500
        body = answer.get_json()
        assert_error_report(body, "slice.scratch_unwritable")
        assert "PermissionError" in body["detail"]

    def test_a_bug_in_a_route_is_an_error_report_and_a_log_line(self, work, monkeypatch):
        client, pool, logs = app_with(work)
        monkeypatch.setattr(pool, "get", lambda job_id: 1 / 0)
        answer = client.get("/slices/jx")
        assert answer.status_code == 500
        assert_error_report(answer.get_json(), "slice.unexpected")
        assert logs[-1]["event"] == "slice_http_error" and "ZeroDivisionError" in logs[-1]["traceback"]


def test_start_removes_scratch_of_a_dead_process_and_starts_the_sweeper(work, monkeypatch):
    (work / "slice-999999999-1-abc").mkdir(parents=True)
    started = []
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: started.append(self))
    app = create_app(work)
    assert not (work / "slice-999999999-1-abc").exists()
    assert started == [app.extensions["penguin_slice_pool"]]
    app.extensions["penguin_slice_pool"].shutdown()


def test_default_work_dir_is_a_new_folder(monkeypatch, tmp_path):
    (tmp_path / "temp").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "temp"))
    monkeypatch.setattr(JobPool, "start_sweeper", lambda self, *a: None)
    app = create_app()
    app.extensions["penguin_slice_pool"].shutdown()
    assert [p.name[:14] for p in (tmp_path / "temp").iterdir()] == ["penguin-slice-"]


def test_remove_job_files_without_a_folder():
    remove_job_files(None)
