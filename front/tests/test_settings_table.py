"""The table of settings, passed from the slice service (README-details.md, "The table of
settings"; contracts/wizard-front-server.md, "`GET /api/settings-table`"; contracts/
slice-http-interface.md, "`GET /settings-table`")."""

import gzip
import json
from pathlib import Path

import pytest

from front_helpers import Lines, front, sign_in
from penguin_front.settings_table import accepts_gzip
from slice_standin import SliceStandIn

TABLE = (Path(__file__).resolve().parents[2] / "contracts" / "examples" /
         "settings-table.json").read_bytes()


@pytest.fixture
def standin(clock):
    standin = SliceStandIn(clock)
    standin.start()
    yield standin
    standin.stop()


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def app(tmp_path, clock, log, standin):
    app = front(tmp_path, clock, log, PENGUIN_SLICE_URL=standin.url)
    yield app
    app.extensions["penguin_front"]["slice"].close()


@pytest.fixture
def client(app):
    client = app.test_client()
    sign_in(client)
    return client


def table_requests(standin):
    return [r for r in standin.requests if r.path == "/settings-table"]


def test_the_answer_is_the_slice_services_table_whole_and_unchanged(client, standin):
    answer = client.get("/api/settings-table")
    assert answer.status_code == 200 and answer.mimetype == "application/json"
    assert answer.data == TABLE == standin.settings_table
    assert "Content-Encoding" not in answer.headers
    assert answer.headers["Cache-Control"] == "no-store"
    assert answer.headers["Vary"] == "Accept-Encoding"
    [asked] = table_requests(standin)
    assert asked.method == "GET" and asked.headers["accept-encoding"] == "identity"


def test_a_proxy_named_in_the_environment_is_not_used_for_the_slice_service(
        tmp_path, clock, standin, monkeypatch):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")      # nothing listens there
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    app = front(tmp_path, clock, Lines(), PENGUIN_SLICE_URL=standin.url)
    try:
        client = app.test_client()
        sign_in(client)
        assert client.get("/api/settings-table").status_code == 200
    finally:
        app.extensions["penguin_front"]["slice"].close()


def test_the_answer_is_compressed_when_the_browser_accepts_it(client, standin):
    answer = client.get("/api/settings-table", headers={"Accept-Encoding": "gzip, deflate, br"})
    assert answer.status_code == 200 and answer.headers["Content-Encoding"] == "gzip"
    assert gzip.decompress(answer.data) == TABLE
    assert len(answer.data) < len(TABLE)
    assert table_requests(standin)[0].headers["accept-encoding"] == "gzip"


@pytest.mark.parametrize("header, accepted", [
    ("gzip", True), ("GZIP", True), ("deflate, gzip;q=0.5", True), ("gzip; q=1.0", True),
    ("*", True), ("gzip;q=0", False), ("gzip;q=0.000", False), ("deflate, br", False),
    ("", False), ("x-gzip", False), ("gzip;q=abc", False), ("identity", False),
    ("gzip;q=1.2.3", False), (",,gzip", True),
])
def test_a_browser_accepts_gzip_by_its_accept_encoding(header, accepted):
    assert accepts_gzip(header) is accepted


def test_a_changed_table_is_answered_at_the_next_request_with_no_restart(client, standin):
    client.get("/api/settings-table")
    standin.settings_table = json.dumps({"format": 2, "changed": True}).encode()
    assert client.get("/api/settings-table").data == standin.settings_table
    assert len(table_requests(standin)) == 2


def test_the_slice_service_not_answering_is_front_slice_unreachable(client, standin, log):
    client.get("/api/settings-table")  # a connection the client may keep open
    standin.unreachable()
    answer = client.get("/api/settings-table")
    assert answer.status_code == 503
    report = answer.get_json()
    assert report["code"] == "front.slice_unreachable" and report["retryable"] is True
    assert log.events("error")[-1]["code"] == "front.slice_unreachable"
    standin.reachable()
    assert client.get("/api/settings-table").status_code == 200


def test_a_slice_service_that_was_never_there_is_front_slice_unreachable(tmp_path, clock):
    app = front(tmp_path, clock)
    client = app.test_client()
    sign_in(client)
    assert client.get("/api/settings-table").get_json()["code"] == "front.slice_unreachable"


def test_without_a_sign_in_it_is_refused_and_the_slice_service_is_not_asked(app, standin):
    answer = app.test_client().get("/api/settings-table")
    assert answer.status_code == 401 and answer.get_json()["code"] == "front.not_signed_in"
    assert table_requests(standin) == []


def test_it_acts_for_no_group(client):
    answer = client.get("/api/settings-table",
                        headers={"X-PenguinSlicer-Group": "a-group-of-nobody"})
    assert answer.status_code == 200


def test_the_slice_services_error_report_is_passed_byte_for_byte_with_its_status(client,
                                                                               standin):
    report = {"code": "slice.profile_unreadable", "message": "m", "remedy": "r",
              "retryable": False, "detail": "d"}
    standin.answer_next("GET", "/settings-table", 500, report)
    answer = client.get("/api/settings-table")
    assert answer.status_code == 500 and answer.data == json.dumps(report).encode()
    assert answer.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("body", [[1, 2], {"code": "front.unexpected"}, {"message": "x"},
                                  {"code": 5}])
def test_an_answer_of_the_slice_service_that_is_neither_table_nor_its_report_is_unexpected(
        client, standin, log, body):
    standin.answer_next("GET", "/settings-table", 502, body)
    answer = client.get("/api/settings-table")
    assert answer.status_code == 500 and answer.get_json()["code"] == "front.unexpected"
    assert "502" in log.events("error")[-1]["trace"]


@pytest.mark.parametrize("body, headers", [
    (gzip.compress(b'{"code": "slice.x"}'), {"Content-Encoding": "gzip"}),
    (b"<html>a proxy's page</html>", {}),
])
def test_a_failure_answered_compressed_or_not_as_json_is_unexpected(client, standin, body,
                                                                    headers):
    @standin.app.before_request
    def failure():
        from flask import Response

        return Response(body, 500, headers=headers)

    answer = client.get("/api/settings-table", headers={"Accept-Encoding": "gzip"})
    assert answer.status_code == 500 and answer.get_json()["code"] == "front.unexpected"


def test_no_user_key_is_sent_for_the_whole_slice_services_table(client, standin):
    client.get("/api/settings-table")
    assert table_requests(standin)[0].user_key is None
