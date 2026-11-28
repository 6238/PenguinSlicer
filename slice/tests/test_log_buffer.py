"""Item 16: the log the front server collects (contracts/slice-http-interface.md, GET /log).

log_buffer.LogBuffer numbers every line from 1, adds the time (from the test's clock) and
the component, keeps the most recent LOG_BUFFER_LINES, passes each line on to its sink
(stderr under serve), and answers `{process, lines, dropped, more}` with at most
LOG_ANSWER_LINES lines after the one numbered `after`. Through the HTTP interface, every
line of a request carries the user key the request carried."""
import json
import re

import pytest

from helpers import CONTRACTS, USER_KEY, box_stl, part_entry, submit, upload
from penguin_slice import log_buffer
from penguin_slice.errors import error_report
from penguin_slice.jobs import JobPool
from penguin_slice.log_buffer import LogBuffer
from penguin_slice.web import create_app, remove_job_files, slice_worker

EXAMPLE = json.loads((CONTRACTS / "examples" / "slice-http" / "log.json").read_text())
BOX = box_stl(20, 20, 10)


class Clock:
    def __init__(self, now=1795817585.412):          # 2026-11-27T22:13:05.412Z
        self.now = now

    def __call__(self):
        return self.now


def filled(count, capacity=log_buffer.LOG_BUFFER_LINES, clock=None):
    buffer = LogBuffer(capacity=capacity, clock=clock or Clock())
    for i in range(count):
        buffer({"event": "slice_job", "i": i + 1})
    return buffer


class TestTheBuffer:
    def test_each_line_is_numbered_and_carries_the_time_and_the_component(self):
        clock, sunk = Clock(), []
        buffer = LogBuffer(sink=sunk.append, clock=clock)
        buffer({"event": "slice_job", "state": "running", "job": "j1", "user_key": "u"})
        clock.now += 52.795
        buffer({"event": "slice_job", "state": "done", "job": "j1", "user_key": "u"})
        lines = buffer.read(0)["lines"]
        assert lines == [
            {"n": 1, "time": "2026-11-27T22:13:05.412Z", "component": "slice", "event": "slice_job",
             "state": "running", "job": "j1", "user_key": "u"},
            {"n": 2, "time": "2026-11-27T22:13:58.207Z", "component": "slice", "event": "slice_job",
             "state": "done", "job": "j1", "user_key": "u"}]
        assert list(lines[0])[:4] == ["n", "time", "component", "event"]
        assert sunk == lines                          # each line goes on to stderr as well

    def test_lines_come_in_order_and_only_those_after_the_number_passed(self):
        buffer = filled(5)
        answer = buffer.read(3)
        assert [line["n"] for line in answer["lines"]] == [4, 5]
        assert (answer["dropped"], answer["more"]) == (0, False)
        assert buffer.read(5)["lines"] == [] and buffer.read(99)["lines"] == []

    def test_more_than_the_answers_lines_come_over_two_answers_with_more(self):
        buffer = filled(log_buffer.LOG_ANSWER_LINES + 1)
        first = buffer.read(0)
        assert len(first["lines"]) == 1000 == log_buffer.LOG_ANSWER_LINES and first["more"] is True
        second = buffer.read(first["lines"][-1]["n"])
        assert [line["n"] for line in second["lines"]] == [1001] and second["more"] is False

    def test_exactly_an_answers_lines_come_in_one_answer_without_more(self):
        answer = filled(log_buffer.LOG_ANSWER_LINES).read(0)
        assert len(answer["lines"]) == log_buffer.LOG_ANSWER_LINES and answer["more"] is False

    def test_a_callers_own_number_time_and_component_are_dropped(self):
        buffer = LogBuffer(clock=Clock())
        buffer({"event": "slice_job", "n": 99, "time": "yesterday", "component": "front", "job": "j1"})
        assert buffer.read(0)["lines"] == [{"n": 1, "time": "2026-11-27T22:13:05.412Z", "component": "slice",
                                            "event": "slice_job", "job": "j1"}]

    def test_a_full_buffer_drops_the_oldest_and_counts_them(self):
        buffer = filled(12, capacity=10)
        answer = buffer.read(0)
        assert [line["n"] for line in answer["lines"]] == list(range(3, 13))
        assert answer["dropped"] == 2
        assert buffer.read(1)["dropped"] == 1 and buffer.read(2)["dropped"] == 0
        assert buffer.read(4)["dropped"] == 0
        assert log_buffer.LOG_BUFFER_LINES == 10_000

    def test_each_process_has_its_own_random_id(self):
        first, second = LogBuffer(), LogBuffer()
        assert re.fullmatch(r"p[0-9a-f]{8}", first.process) and first.process != second.process
        assert first.read(0)["process"] == first.process

    def test_a_line_that_is_not_json_is_kept_as_its_words(self, tmp_path):
        buffer = LogBuffer()
        buffer({"event": "slice_job", "path": tmp_path})
        assert buffer.read(0)["lines"][0]["path"] == str(tmp_path)
        json.dumps(buffer.read(0))

    def test_a_sink_that_fails_raises_and_the_line_is_kept(self):
        def broken(line):
            raise OSError("stderr closed")
        buffer = LogBuffer(sink=broken)
        with pytest.raises(OSError):
            buffer({"event": "x"})
        assert [line["event"] for line in buffer.read(0)["lines"]] == ["x"]


def app_with_buffer(work, clock=None, executor=None):
    buffer = LogBuffer(clock=clock or Clock())
    pool = JobPool(slice_worker, executor=executor or Held(), error_report=error_report, cleanup=remove_job_files,
                   log=buffer)
    app = create_app(work, pool, start_sweeper=False, log=buffer)
    return app.test_client(), pool, buffer


class Held:
    def submit(self, fn, *args):
        pass


class TestTheRoute:
    def test_the_answer_has_the_contracts_shape(self, tmp_path):
        client, _pool, buffer = app_with_buffer(tmp_path / "work")
        for n in range(43):
            buffer({"event": "slice_job", "state": "running", "job": "j7c1d03ae", "user_key": "u", "i": n})
        answer = client.get("/log?after=41")
        assert answer.status_code == 200 and answer.headers["Cache-Control"] == "no-store"
        body = answer.get_json()
        assert set(body) == set(EXAMPLE) and [type(body[k]) for k in EXAMPLE] == [type(v) for v in EXAMPLE.values()]
        assert [set(line) >= {"n", "time", "component", "event", "job", "user_key"} for line in body["lines"]] == \
            [True, True]
        assert [line["n"] for line in body["lines"]] == [42, 43] and body["process"] == buffer.process
        assert all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", line["time"]) for line in body["lines"])

    def test_without_after_it_answers_from_the_first_line(self, tmp_path):
        client, _pool, buffer = app_with_buffer(tmp_path / "work")
        buffer({"event": "x"})
        assert [line["n"] for line in client.get("/log").get_json()["lines"]] == [1]

    def test_no_user_key_is_needed(self, tmp_path):
        client, _pool, _buffer = app_with_buffer(tmp_path / "work")
        assert client.get("/log?after=0", headers={"X-Penguin-User-Key": ""}).status_code == 200

    @pytest.mark.parametrize("after", ["-1", "x", "1.5", "²", "1e3", "9" * 19, ""])
    def test_an_after_that_is_not_a_whole_number_is_refused(self, tmp_path, after):
        client, _pool, _buffer = app_with_buffer(tmp_path / "work")
        answer = client.get("/log", query_string={"after": after})
        body = answer.get_json()
        assert (answer.status_code, body["code"]) == (400, "slice.bad_request")
        assert body["message"] == "The slicer was asked for its log after a line that is not a whole number."

    def test_a_new_process_answers_a_new_process_id_and_numbers_from_one(self, tmp_path):
        first, _pool, _buffer = app_with_buffer(tmp_path / "work")
        assert upload(first, BOX).status_code == 201
        before = first.get("/log?after=0").get_json()
        second, _pool2, _buffer2 = app_with_buffer(tmp_path / "work")
        after = second.get(f"/log?after={before['lines'][-1]['n']}").get_json()
        assert after["process"] != before["process"]
        assert second.get("/log?after=0").get_json()["lines"] == []

    def test_an_app_made_without_a_buffer_makes_its_own_and_passes_each_line_on(self, tmp_path):
        sunk = []
        app = create_app(tmp_path / "work", start_sweeper=False, log=sunk.append)
        client = app.test_client()
        assert upload(client, BOX).status_code == 201
        lines = client.get("/log?after=0").get_json()["lines"]
        assert [line["event"] for line in lines] == ["part_upload"] and sunk == lines
        app.extensions["penguin_slice_pool"].shutdown()

    def test_a_failing_buffer_never_changes_an_answer(self, tmp_path, monkeypatch):
        client, pool, buffer = app_with_buffer(tmp_path / "work")

        def broken(entry):
            raise MemoryError("the buffer is broken")
        monkeypatch.setattr(LogBuffer, "__call__", lambda self, entry: broken(entry))
        assert upload(client, BOX).status_code == 201
        data = {"plate_id": "p", "submission_id": "s", "parts": {"box": part_entry("Box", BOX)},
                "instances": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0}]}
        assert submit(client, data).status_code == 202
        assert client.get("/slices/nope", headers={"X-Penguin-User-Key": USER_KEY}).status_code == 404
        assert pool.log_failures() >= 1

    def test_a_buffer_that_cannot_be_read_is_an_error_report(self, tmp_path, monkeypatch):
        client, _pool, _buffer = app_with_buffer(tmp_path / "work")
        monkeypatch.setattr(LogBuffer, "read", lambda self, after: 1 / 0)
        answer = client.get("/log?after=0")
        assert (answer.status_code, answer.get_json()["code"]) == (500, "slice.unexpected")


class TestEveryLineCarriesItsUserKey:
    """Every line a request leads to carries the time from the test's clock, the component,
    and the user key the request carried."""

    def test_the_lines_of_uploads_submissions_refusals_and_slice_jobs(self, tmp_path):
        clock = Clock()
        client, pool, buffer = app_with_buffer(tmp_path / "work", clock=clock)
        headers_b = {"X-Penguin-User-Key": "user-b"}
        upload(client, BOX)                                                  # part_upload, stored
        upload(client, b"not an stl", user_key="user-b")                     # part_upload, refused
        data = {"plate_id": "p", "submission_id": "s", "parts": {"box": part_entry("Box", BOX)},
                "instances": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0}]}
        job = submit(client, data).get_json()["job"]                         # slice_job, queued
        submit(client, data)                                                 # slice_repeat
        submit(client, dict(data, submission_id="t", instances=[]))          # slice_job, refused
        client.get(f"/slices/{job}", headers=headers_b)                      # slice_http_refused (another's)
        client.get(f"/slices/{job}")                                         # slice_http_refused (no key)
        pool.cancel(job)                                                     # slice_job, cancelled
        lines = buffer.read(0)["lines"]
        assert [line["n"] for line in lines] == list(range(1, len(lines) + 1))
        assert all(line["time"] == "2026-11-27T22:13:05.412Z" and line["component"] == "slice" for line in lines)
        keys = [(line["event"], line.get("state"), line["user_key"]) for line in lines]
        assert keys == [("part_upload", "stored", USER_KEY), ("part_upload", "refused", "user-b"),
                        ("slice_job", "queued", USER_KEY), ("slice_repeat", "queued", USER_KEY),
                        ("slice_job", "refused", USER_KEY), ("slice_http_refused", None, "user-b"),
                        ("slice_http_refused", None, None), ("slice_job", "cancelled", USER_KEY)]
        assert all(line["job"] == job for line in lines if line["event"] in ("slice_job", "slice_repeat")
                   and line.get("state") != "refused")
