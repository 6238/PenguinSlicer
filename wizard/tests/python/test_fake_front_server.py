"""The browser tests' fake front server answers in the contract's shapes: its default answers are
the contract's examples, whole, with the contract's statuses and headers."""
import hashlib
import json
import urllib.error
import urllib.request

import pytest

from tests_browser.fake_front_server import EXAMPLES, FakeFrontServer, error_report, example, progress_event, stream

VERSION_META = '<meta name="penguinslicer-version" content="__PENGUINSLICER_VERSION__">'


@pytest.fixture
def server(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(f"<html>{VERSION_META}</html>")
    (tmp_path / "assets" / "main.0123456789ab.js").write_text("export {};\n")
    with FakeFrontServer(tmp_path) as running:
        yield running


def ask(server, method, path):
    request = urllib.request.Request(server.url.rstrip("/") + path, method=method, data=b"{}" if method != "GET" else None)
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            status, headers, body = answer.status, answer.headers, answer.read()
    except urllib.error.HTTPError as error:
        status, headers, body = error.code, error.headers, error.read()
    return status, headers, (json.loads(body) if body and headers.get("Content-Type") == "application/json" else body)


@pytest.mark.parametrize("method, path, status, body", [
    ("GET", "/api/me", 200, example("wizard-front/me.json")),
    ("PUT", "/api/configuration", 200, example("wizard-front/configuration-written.json")),
    ("GET", "/api/settings-table", 200, example("settings-table.json")),
    ("POST", "/api/slices", 202, example("wizard-front/slice-accepted.json")),
    ("GET", "/api/slices/3f9a1c2b", 200, example("wizard-front/slice-done.json")),
    ("GET", "/api/slices/3f9a1c2b/summary", 200, example("wizard-front/slice-summary.json")),
])
def test_the_default_answers_are_the_contract_examples(server, method, path, status, body):
    got_status, headers, got = ask(server, method, path)
    assert (got_status, got) == (status, body)
    assert headers["X-PenguinSlicer-Version"] == server.version
    assert headers["Cache-Control"] == "no-store"


def test_a_progress_stream_is_by_default_the_contracts_example_closed(server):
    status, headers, body = ask(server, "GET", "/api/slices/3f9a1c2b/events")
    assert status == 200
    assert headers["Content-Type"] == "text/event-stream"
    assert headers["X-PenguinSlicer-Version"] == server.version
    assert body.decode("utf-8") == (EXAMPLES / "wizard-front" / "slice-events.txt").read_text(encoding="utf-8")


def test_a_held_stream_is_written_at_once_and_ends_when_released(server):
    held = stream(progress_event({"job": "j", "state": "running", "sequence": 3}), hold=True)
    server.script("GET", "/api/slices/j/events", held)
    request = urllib.request.Request(server.url.rstrip("/") + "/api/slices/j/events")
    with urllib.request.urlopen(request, timeout=10) as answer:
        first = answer.readline()
        held.release()
        rest = answer.read()
    assert first == b"event: progress\n"
    assert rest.startswith(b"id: 3\n")


def test_an_upload_is_answered_with_the_record_of_the_bytes_sent(server):
    request = urllib.request.Request(server.url.rstrip("/") + "/api/parts?units=mm", method="POST", data=b"\x01\x02\x03")
    with urllib.request.urlopen(request, timeout=10) as answer:
        status, body = answer.status, json.loads(answer.read())
    assert status == 201
    assert body == {**example("wizard-front/part-record.json"), "sha256": hashlib.sha256(b"\x01\x02\x03").hexdigest(),
                    "units": "mm", "warnings": []}


def test_the_configuration_is_the_default_one_named_as_the_contract_says(server):
    _, _, body = ask(server, "GET", "/api/configuration")
    assert body == {"configuration": example("configuration-default.json"), "source": "default",
                    "name": "PenguinSlicer default", "revision": None}


def test_a_report_about_the_page_is_answered_204_with_no_body(server):
    status, headers, body = ask(server, "POST", "/api/reports/failure")
    assert (status, body) == (204, b"")


def test_the_page_and_its_assets_are_marked_as_the_contract_says(server):
    status, headers, body = ask(server, "GET", "/")
    assert headers["Cache-Control"] == "private, no-cache"
    assert "frame-ancestors 'self'" in headers["Content-Security-Policy"]
    assert server.version.encode() in body
    status, headers, _ = ask(server, "GET", "/assets/main.0123456789ab.js")
    assert (status, headers["Cache-Control"]) == (200, "private, max-age=31536000, immutable")


def test_an_unknown_request_is_the_front_servers_report(server):
    status, _, body = ask(server, "GET", "/api/nothing")
    assert (status, body["code"]) == (404, "front.no_such_request")
    assert set(body) == {"code", "message", "remedy", "retryable", "detail"}


def test_a_scripted_answer_comes_first_then_the_default(server):
    server.script("GET", "/api/me", (503, error_report("front.unexpected", retryable=True), {"Retry-After": "7"}))
    status, headers, body = ask(server, "GET", "/api/me")
    assert (status, body["code"], headers["Retry-After"]) == (503, "front.unexpected", "7")
    assert ask(server, "GET", "/api/me")[2] == example("wizard-front/me.json")
