"""The stand-in for the slice service answers as its contract says
(contracts/slice-http-interface.md), checked against the contract's examples, lets a test put
its events in an exact order, and records every request it receives
(README-details.md, "The slice service's requests")."""

import gzip
import json
import threading

import httpx
import pytest

from front_fakes import loopback_client
from slice_standin import EXAMPLES, SliceStandIn, example

USER = "5f1e0c2a9b3d4e6f7a8b9c0d"
OTHER = "0a0b0c0d0e0f101112131415"
KEY = {"X-Penguin-User-Key": USER}
BRACKET = (EXAMPLES / "parts" / "bracket.stl").read_bytes()
SPACER = (EXAMPLES / "parts" / "spacer.stl").read_bytes()
PLATE = example("plate-configuration-phase-2.json")


@pytest.fixture
def standin(clock):
    s = SliceStandIn(clock)
    s.start()
    yield s
    s.stop()


@pytest.fixture
def http(standin):
    with loopback_client(standin.url) as client:
        yield client


def upload(http, body=BRACKET, units="mm", headers=KEY):
    return http.post(f"/parts?units={units}", content=body,
                     headers=dict(headers, **{"Content-Type": "application/octet-stream"}))


def submit(http, plate=PLATE, headers=KEY):
    return http.post("/slices", json=plate, headers=headers)


def with_both_parts(http, headers=KEY):
    assert upload(http, BRACKET, headers=headers).status_code == 201
    assert upload(http, SPACER, headers=headers).status_code == 201


# The examples, one by one.

def test_an_upload_answers_the_examples_part_record(http):
    answer = upload(http)
    assert answer.status_code == 201
    assert answer.json() == example("slice-http/part-record.json")
    assert answer.headers["Cache-Control"] == "no-store"


def test_a_repeated_upload_answers_the_same_record(http):
    assert upload(http).json() == upload(http).json()


def test_an_upload_in_inches_is_scaled(http):
    record = upload(http, units="in").json()
    assert record["units"] == "in"
    assert record["measurements"]["size_mm"] == [1016.0, 762.0, 304.8]


def test_an_upload_over_the_part_limit_answers_the_examples_refusal(http):
    answer = upload(http, body=b"\0" * 7_500_085)
    assert answer.status_code == 413
    assert answer.json() == example("error-report-part-over-size.json")


def test_an_upload_at_the_part_limit_is_read(http):
    answer = upload(http, body=b"\0" * 7_500_084)
    assert answer.status_code == 422 and answer.json()["code"] == "slice.part_unreadable"


def test_an_upload_without_units_or_with_other_units_is_refused(http):
    for query in ("", "?units=cm"):
        answer = http.post(f"/parts{query}", content=BRACKET, headers=KEY)
        assert answer.status_code == 400 and answer.json()["code"] == "slice.bad_units"


def test_an_upload_without_content_length_is_refused(http):
    answer = http.post("/parts?units=mm", content=iter([BRACKET]), headers=KEY)
    assert answer.status_code == 400 and answer.json()["code"] == "slice.bad_request"


def test_a_request_without_the_user_key_answers_the_examples_refusal(http):
    answer = upload(http, headers={})
    assert answer.status_code == 400
    assert answer.json() == example("slice-http/no-user-key.json")
    assert http.get("/slices/j1", headers={"X-Penguin-User-Key": ""}).json()["code"] \
        == "slice.no_user_key"


def test_a_submission_answers_the_examples_slice_job(standin, http):
    with_both_parts(http)
    standin.next_job_ids.append("j7c1d03ae")
    answer = submit(http)
    assert answer.status_code == 202
    assert answer.json() == example("slice-http/slice-accepted.json")


def test_a_submission_naming_parts_not_held_answers_the_examples_refusal(http):
    answer = submit(http)
    assert answer.status_code == 422
    assert answer.json() == example("error-report-parts-missing.json")


def test_another_users_parts_are_not_this_users(http):
    with_both_parts(http, headers={"X-Penguin-User-Key": OTHER})
    assert submit(http).json()["code"] == "slice.part_missing"


def test_a_submission_over_the_limit_answers_the_examples_refusal(http):
    answer = http.post("/slices", content=b" " * 1_048_577, headers=KEY)
    assert answer.status_code == 413
    assert answer.json() == example("error-report-plate-configuration-over-size.json")


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"plate_id": "p"}',
                                  b'{"plate_id": "bad id", "submission_id": "s", "parts": {}}',
                                  b'{"plate_id": "p", "submission_id": "s", "parts": []}'])
def test_a_submission_of_the_wrong_form_is_refused(http, body):
    answer = http.post("/slices", content=body, headers=KEY)
    assert answer.status_code == 400
    assert answer.json()["code"] == "slice.bad_plate_configuration"


def test_a_repeated_submission_answers_its_first_slice_job_and_starts_nothing(standin, http):
    with_both_parts(http)
    first = submit(http).json()
    standin.report(first["job"], dict(first["progress"], state="running", stage="slicing",
                                      sequence=2))
    again = submit(http).json()
    assert again["job"] == first["job"] and again["progress"]["sequence"] == 2
    assert len(standin.jobs) == 1


def test_a_plates_later_slice_replaces_its_earlier_one(standin, http):
    with_both_parts(http)
    first = submit(http).json()["job"]
    second = submit(http, dict(PLATE, submission_id="second")).json()
    assert second["job"] != first and second["progress"]["ahead"] == 0
    replaced = http.get(f"/slices/{first}", headers=KEY).json()
    assert replaced["state"] == "cancelled" and replaced["cancel_reason"] == "replaced"


def test_one_running_and_two_waiting_leave_no_room(standin, http):
    with_both_parts(http)
    for n in range(3):
        accepted = submit(http, dict(PLATE, plate_id=f"plate{n}", submission_id=f"s{n}"))
        assert accepted.json()["progress"]["ahead"] == n
    answer = submit(http, dict(PLATE, plate_id="plate3", submission_id="s3"))
    assert answer.status_code == 503
    assert answer.json()["code"] == "slice.busy" and answer.json()["retryable"] is True


def test_every_place_taken_a_changed_plate_of_the_same_user_key_is_accepted(standin, http):
    # slice/README-details.md: the slice job it replaces gives up its place.
    with_both_parts(http)
    first = [submit(http, dict(PLATE, plate_id=f"plate{n}", submission_id=f"s{n}")).json()
             for n in range(3)]
    answer = submit(http, dict(PLATE, plate_id="plate2", submission_id="changed"))
    assert answer.status_code == 202 and answer.json()["job"] != first[2]["job"]
    replaced = http.get(f"/slices/{first[2]['job']}", headers=KEY).json()
    assert replaced["state"] == "cancelled" and replaced["cancel_reason"] == "replaced"


def test_a_stopping_slice_service_answers_the_examples_refusal_but_repeats_a_submission(
        standin, http):
    with_both_parts(http)
    first = submit(http).json()
    standin.stopping = True
    answer = submit(http, dict(PLATE, submission_id="new"))
    assert answer.status_code == 503
    assert answer.json() == example("slice-http/stopping.json")
    assert submit(http).json()["job"] == first["job"]


def test_the_list_of_slice_jobs_answers_the_example(standin, http):
    listed = example("slice-http/slices-list.json")["slices"]
    for entry in listed:
        standin.add_job(entry["job"], entry["user_key"], entry["plate_id"],
                        entry["submission_id"], entry["progress"],
                        file=b"sliced" if entry["file_on_disk"] else None,
                        ended_at=entry["ended_at"])
    answer = http.get("/slices")
    assert answer.status_code == 200
    assert answer.json() == {"slices": listed}


def test_a_newly_started_process_lists_no_slice_jobs(standin, http):
    with_both_parts(http)
    submit(http)
    standin.restart()
    assert http.get("/slices").json() == {"slices": []}


def test_the_progress_stream_answers_the_example(standin, http):
    reports = [json.loads(line[len("data: "):])
               for line in (EXAMPLES / "slice-http" / "events.txt").read_text().splitlines()
               if line.startswith("data: ")]
    standin.add_job("j7c1d03ae", USER, "p", "s", reports[0])
    received = []
    with http.stream("GET", "/slices/j7c1d03ae/events", headers=KEY) as stream:
        assert stream.headers["Content-Type"].startswith("text/event-stream")
        chunks = stream.iter_text()
        received.append(next(chunks))
        for report in reports[1:4]:
            standin.report("j7c1d03ae", report)
        standin.repeat("j7c1d03ae")
        standin.report("j7c1d03ae", reports[5])
        received.extend(chunks)
    assert "".join(received) == (EXAMPLES / "slice-http" / "events.txt").read_text()


def test_a_stream_closed_before_its_final_report_ends_without_it(standin, http):
    standin.add_job("j1", USER, "p", "s", {"job": "j1", "state": "running", "sequence": 4})
    with http.stream("GET", "/slices/j1/events", headers=KEY) as stream:
        chunks = stream.iter_text()
        first = next(chunks)
        standin.close_streams("j1")
        rest = "".join(chunks)
    assert first.startswith("id: 4\n") and rest == ""


def test_three_streams_on_one_slice_job_are_three_connections(standin, http):
    standin.add_job("j1", USER, "p", "s", {"job": "j1", "state": "running", "sequence": 1})
    opened = threading.Barrier(4)
    texts = []

    def follow():
        with loopback_client(standin.url) as client:
            with client.stream("GET", "/slices/j1/events", headers=KEY) as stream:
                chunks = stream.iter_text()
                text = next(chunks)
                opened.wait()
                texts.append(text + "".join(chunks))

    threads = [threading.Thread(target=follow) for _ in range(3)]
    for t in threads:
        t.start()
    opened.wait()
    assert standin.open_streams("j1") == 3
    standin.report("j1", {"job": "j1", "state": "done", "sequence": 2})
    for t in threads:
        t.join()
    assert len(texts) == 3 and all(t.count("event: progress") == 2 for t in texts)


def test_the_sliced_file_its_summary_and_the_delete(standin, http):
    summary = example("sliced-file.json")
    standin.add_job("j1", USER, "p", "s", {"job": "j1", "state": "done", "sequence": 9},
                    file=b"G-code bytes", summary=summary, ended_at="2026-11-27T22:13:58Z")
    answer = http.get("/slices/j1/file", headers=KEY)
    assert answer.status_code == 200 and answer.content == b"G-code bytes"
    assert answer.headers["Content-Length"] == "12"
    assert answer.headers["Content-Disposition"] == \
        'attachment; filename="Bracket_plus1-20261009-1432.gcode.3mf"'
    assert http.get("/slices/j1/summary", headers=KEY).json() == summary
    deleted = http.delete("/slices/j1/file", headers=KEY)
    assert deleted.json() == {"job": "j1", "file": "deleted"}
    assert http.delete("/slices/j1/file", headers=KEY).json() == {"job": "j1", "file": "deleted"}
    for path in ("/slices/j1/file", "/slices/j1/summary"):
        gone = http.get(path, headers=KEY)
        assert gone.status_code == 410 and gone.json()["code"] == "slice.file_gone"
    assert http.get("/slices").json()["slices"][0]["file_on_disk"] is False


def test_the_file_deleted_answer_is_the_examples(standin, http):
    standin.add_job("j7c1d03ae", USER, "p", "s", {"job": "j7c1d03ae", "state": "done",
                                                  "sequence": 38}, file=b"x")
    assert http.delete("/slices/j7c1d03ae/file", headers=KEY).json() == \
        example("slice-http/file-deleted.json")


def test_an_unfinished_slice_job_has_no_file_yet(standin, http):
    standin.add_job("j1", USER, "p", "s", {"job": "j1", "state": "running", "sequence": 3})
    for method, path in (("GET", "/slices/j1/file"), ("GET", "/slices/j1/summary"),
                         ("DELETE", "/slices/j1/file")):
        answer = http.request(method, path, headers=KEY)
        assert answer.status_code == 409 and answer.json()["code"] == "slice.not_ready"


def test_a_failed_slice_job_answers_its_own_report_and_a_cancelled_one_slice_cancelled(
        standin, http):
    failure = example("error-report.json")
    standin.add_job("j1", USER, "p", "s", {"job": "j1", "state": "failed", "sequence": 5,
                                           "error": failure})
    standin.add_job("j2", USER, "p2", "s2", {"job": "j2", "state": "cancelled", "sequence": 5,
                                             "cancel_reason": "replaced"})
    assert http.get("/slices/j1/file", headers=KEY).json() == failure
    cancelled = http.get("/slices/j2/file", headers=KEY)
    assert cancelled.status_code == 409 and cancelled.json()["code"] == "slice.cancelled"
    assert http.delete("/slices/j1/file", headers=KEY).json() == {"job": "j1", "file": "deleted"}


def test_another_users_slice_job_is_answered_as_unknown_and_counted_as_a_refusal(
        standin, http):
    standin.add_job("j1", USER, "p", "s", {"job": "j1", "state": "running", "sequence": 3})
    other = {"X-Penguin-User-Key": OTHER}
    for method, path in (("GET", "/slices/j1"), ("GET", "/slices/j1/events"),
                         ("GET", "/slices/j1/file"), ("GET", "/slices/j1/summary"),
                         ("DELETE", "/slices/j1/file"), ("DELETE", "/slices/j1")):
        theirs = http.request(method, path, headers=other)
        never = http.request(method, path.replace("j1", "j9"), headers=other)
        assert theirs.status_code == never.status_code == 404
        assert theirs.json() == {**never.json(), "detail": theirs.json()["detail"]}
        assert theirs.json()["code"] == "slice.unknown_job"
    assert standin.refusals == 6


def test_a_cancel_is_answered_as_built_and_recorded(standin, http):
    standin.add_job("j1", USER, "p", "s", {"job": "j1", "state": "running", "sequence": 3})
    answer = http.delete("/slices/j1", headers=KEY).json()
    assert answer["job"] == "j1" and answer["cancel"] == "cancelled"
    assert answer["progress"]["cancel_reason"] == "requested"
    assert standin.cancels() == ["j1"]


def test_the_table_of_settings_is_the_example_compressed_when_allowed(http):
    table = (EXAMPLES / "settings-table.json").read_bytes()
    plain = http.get("/settings-table", headers={"Accept-Encoding": "identity"})
    assert plain.content == table and "Content-Encoding" not in plain.headers
    with http.stream("GET", "/settings-table", headers={"Accept-Encoding": "gzip"}) as raw:
        assert raw.headers["Content-Encoding"] == "gzip"
        assert gzip.decompress(b"".join(raw.iter_raw())) == table


def test_the_log_answers_the_example(standin, http):
    expected = example("slice-http/log.json")
    standin.process = expected["process"]
    for n in range(1, 42):
        standin.log_line("filler")
    for line in expected["lines"]:
        standin.log_line(**{k: v for k, v in line.items() if k not in ("n", "component")})
    assert http.get("/log?after=41").json() == expected


def test_the_log_pages_drops_and_restarts(standin, http):
    standin.log_page = 2
    standin.log_capacity = 3
    for n in range(5):
        standin.log_line("e", job=f"j{n}")
    first = http.get("/log?after=0").json()
    assert [line["n"] for line in first["lines"]] == [3, 4] and first["dropped"] == 2
    assert first["more"] is True
    second = http.get("/log?after=4").json()
    assert [line["n"] for line in second["lines"]] == [5] and second["more"] is False
    assert second["dropped"] == 0
    process = first["process"]
    standin.restart()
    restarted = http.get("/log?after=5").json()
    assert restarted["process"] != process and restarted["lines"] == []


@pytest.mark.parametrize("after", ["", "x", "-1"])
def test_the_log_refuses_an_after_that_is_not_a_whole_number(http, after):
    answer = http.get(f"/log?after={after}")
    assert answer.status_code == 400 and answer.json()["code"] == "slice.bad_request"


def test_a_path_not_offered_and_a_method_not_taken(http):
    missing = http.get("/nothing")
    assert missing.status_code == 404 and missing.json()["code"] == "slice.bad_request"
    wrong = http.put("/slices", headers=KEY)
    assert wrong.status_code == 405 and wrong.json()["code"] == "slice.bad_request"


def test_every_request_is_recorded(standin, http):
    upload(http)
    http.get("/slices")
    recorded = [(r.method, r.path, r.query, r.user_key) for r in standin.requests]
    assert recorded == [("POST", "/parts", "units=mm", USER), ("GET", "/slices", "", None)]
    assert standin.requests[0].body == BRACKET


def test_a_next_answer_set_by_the_test_is_given_once(standin, http):
    standin.answer_next("POST", "/parts", 500, example("error-report.json"))
    assert upload(http).status_code == 500
    assert upload(http).status_code == 201


def test_a_fetch_cut_halfway_and_a_file_sent_without_its_length(standin, http):
    standin.add_job("j1", USER, "p", "s", {"job": "j1", "state": "done", "sequence": 9},
                    file=b"0123456789")
    standin.cut_file("j1", after=4)
    with pytest.raises(httpx.HTTPError):
        http.get("/slices/j1/file", headers=KEY)
    standin.cut_file("j1", after=None)
    standin.jobs["j1"].send_length = False
    whole = http.get("/slices/j1/file", headers=KEY)
    assert whole.content == b"0123456789" and "Content-Length" not in whole.headers


def test_an_unreachable_stand_in_refuses_connections_and_comes_back(standin, http):
    standin.unreachable()
    with pytest.raises(httpx.ConnectError):
        http.get("/slices")
    standin.reachable()
    assert http.get("/slices").status_code == 200


def test_a_final_report_records_when_the_slice_job_ended(standin, clock, http):
    with_both_parts(http)
    job = submit(http).json()["job"]
    clock.advance(53)
    standin.report(job, {"job": job, "state": "done", "sequence": 2})
    entry = http.get("/slices").json()["slices"][0]
    assert entry["ended_at"] == "2026-11-27T22:14:58Z"
    assert http.get(f"/slices/{job}", headers=KEY).json()["state"] == "done"
