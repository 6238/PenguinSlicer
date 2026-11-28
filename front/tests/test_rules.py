"""The rules for every request (README-details.md, "Rules for every request" and "The
version, and old and new versions together"; contracts/wizard-front-server.md, "Rules for
every request")."""

import json
import re
from pathlib import Path

import pytest
from flask import abort

from penguin_front.app import create_app, json_body, page_file
from penguin_front.errors import FRONT_REPORTS, FrontError, error_report
from penguin_front.settings import Settings
from penguin_front.version import VERSION_FORM

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "wizard-front-server.md"
VERSION = "20261127T221405Z-1a2b3c4"
REQUIRED = {"code": str, "message": str, "remedy": str, "retryable": bool, "detail": str}

#: The contract's requests the front server offers so far, as (method, path). Each item of
#: README-details.md's phase 2 list that builds a request adds it here; at the end of
#: phase 2 this is every phase 2 row of the contract's table.
BUILT = set()
#: The requests whose answers are page files, marked to be kept, not `no-store`.
PAGE_FILES = {("GET", "/"), ("GET", "/assets/<file>")}


class Lines:
    """A stand-in for the log: the lines written, in order."""

    def __init__(self):
        self.lines = []

    def write(self, event, **fields):
        self.lines.append({"event": event, **fields})


def contract_requests():
    """The contract's table "The requests at a glance", as {(method, path): phase}."""
    text = CONTRACT.read_text().split("## The requests at a glance", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| `([A-Z]+)` \| `([^`]+)` \| [^|]+ \| ([^|]+) \|$", text, re.M)
    return {(method, path): phase.strip() for method, path, phase in rows}


def offered(app):
    return {(method, rule.rule) for rule in app.url_map.iter_rules()
            for method in rule.methods - {"HEAD", "OPTIONS"}}


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def app(clock, log):
    settings = Settings.from_environ({"PENGUIN_DEV_IDENTITY": "1"})
    application = create_app(settings, clock=clock, log=log, version=VERSION)

    @application.post("/test/json")
    def echo():
        return {"got": json_body()}

    @application.get("/test/raise")
    def explode():
        raise RuntimeError("a fault planted by the test")

    @application.get("/test/refuse")
    def refuse():
        raise FrontError("front.bad_request", "a refusal planted by the test")

    @application.get("/test/abort/<int:status>")
    def http_failure(status):
        abort(status)

    @application.get("/test/page")
    def page():
        return page_file(application.response_class("<html></html>", mimetype="text/html"),
                         "private, no-cache")

    return application


@pytest.fixture
def client(app):
    return app.test_client()


def assert_error_report(answer, code, status):
    assert answer.status_code == status
    assert answer.headers["Content-Type"] == "application/json"
    report = answer.get_json()
    for field, kind in REQUIRED.items():
        assert isinstance(report[field], kind), field
    assert report["code"] == code
    assert report["retryable"] is FRONT_REPORTS[code]["retryable"]
    assert "Onshape" not in report["message"] + report["remedy"]
    assert not re.search(r"student|mentor|team", report["message"] + report["remedy"], re.I)
    return report


# The requests at a glance.

def test_the_contracts_table_is_read_whole():
    table = contract_requests()
    assert len(table) == 27 and table[("GET", "/api/me")] == "2"
    assert table[("GET", "/signin")] == "2 (development identity), 3"


def test_the_requests_offered_are_the_contracts_built_so_far(clock, log):
    application = create_app(Settings.from_environ({"PENGUIN_DEV_IDENTITY": "1"}),
                             clock=clock, log=log, version=VERSION)
    assert offered(application) == BUILT
    phase_2 = {request for request, phase in contract_requests().items()
               if phase.startswith("2")}
    assert BUILT <= phase_2


@pytest.mark.parametrize("method, path", [
    ("GET", "/nothing"), ("POST", "/api/nothing"), ("GET", "/api/slices/j1/cancel"),
    ("DELETE", "/api/slices/j1"), ("PUT", "/test/json"), ("GET", "/test/json"),
    ("OPTIONS", "/test/json"), ("OPTIONS", "*"), ("GET", "/test//raise"),
    ("GET", "/test/raise//"), ("GET", "/test/raise/"), ("PATCH", "/"),
])
def test_a_path_or_method_not_offered_is_front_no_such_request(client, log, method, path):
    answer = client.open(path, method=method)
    report = assert_error_report(answer, "front.no_such_request", 404)
    assert method in report["detail"]
    assert "Allow" not in answer.headers and "Location" not in answer.headers
    assert log.lines[-1]["event"] == "error" and log.lines[-1]["code"] == \
        "front.no_such_request"


@pytest.mark.parametrize("target, path_info, path", [
    ("//test/raise", "/test/raise", "//test/raise"),
    ("///test/raise", "/test/raise", "///test/raise"),
    ("http://h//test/raise?a=1", "/test/raise", "//test/raise"),
    ("test/raise", "test/raise", "test/raise"),
    ("/test/%2Fraise", "/test//raise", "/test/%2Fraise"),
])
def test_a_doubled_slash_anywhere_in_the_path_is_front_no_such_request(client, log, target,
                                                                       path_info, path):
    # The test client would read a path starting `//` as a host; the environment is set
    # directly, as waitress passes it for a request line `GET <target>`: the target whole,
    # the path with its leading slashes dropped (tests/test_server.py sends these through
    # waitress itself).
    answer = client.get("/", environ_overrides={"REQUEST_URI": target, "RAW_URI": target,
                                                "PATH_INFO": path_info})
    report = assert_error_report(answer, "front.no_such_request", 404)
    assert path in report["detail"] and "Location" not in answer.headers
    assert log.lines[-1]["path"] == path


def test_without_the_target_as_sent_the_servers_path_is_checked(client, log):
    answer = client.get("/", environ_overrides={"REQUEST_URI": None, "RAW_URI": None,
                                                "PATH_INFO": "/test//raise"})
    assert_error_report(answer, "front.no_such_request", 404)
    assert log.lines[-1]["path"] == "/test//raise"


# Answers.

@pytest.mark.parametrize("body", [b"", b"not json", b"{", b'{"a": NaN}', b"[1, Infinity]",
                                  b'{"a": 1e999}', b"[-1e400]",
                                  b'{"a": 1} trailing', b"\xff\xfe{}", b'"\xed\xa0\x80"',
                                  b"[" * 100_000, b"[" * 50_000 + b"]" * 50_000,
                                  b'{"a":' * 50_000 + b"1" + b"}" * 50_000])
def test_a_body_that_is_not_json_is_front_bad_request(client, log, body):
    answer = client.post("/test/json", data=body, content_type="application/json")
    report = assert_error_report(answer, "front.bad_request", 400)
    assert "JSON" in report["detail"]
    assert log.lines[-1]["code"] == "front.bad_request"


def test_a_json_body_is_read_whatever_its_content_type_says(client):
    for content_type in ("application/json", "text/plain", None):
        answer = client.post("/test/json", data=b'{"a": [1, 2.5, null]}',
                             content_type=content_type)
        assert answer.status_code == 200 and answer.get_json() == {"got": {"a": [1, 2.5, None]}}


def test_an_exception_inside_is_front_unexpected_and_its_trace_goes_to_the_log(client, log):
    answer = client.get("/test/raise")
    report = assert_error_report(answer, "front.unexpected", 500)
    line = log.lines[-1]
    assert line["event"] == "error" and line["code"] == "front.unexpected"
    assert "detail" not in line  # the report's detail says nothing the line needs
    assert "RuntimeError: a fault planted by the test" in line["trace"]
    assert "explode" in line["trace"]
    assert line["incident"] in report["detail"]
    assert "a fault planted" not in report["detail"] and "Traceback" not in report["detail"]


@pytest.mark.parametrize("status", [400, 411, 413, 431])
def test_a_request_the_web_framework_refuses_is_front_bad_request(client, status):
    report = assert_error_report(client.get(f"/test/abort/{status}"), "front.bad_request", 400)
    assert report["detail"].startswith(str(status))


@pytest.mark.parametrize("status", [500, 503])
def test_a_server_failure_of_the_web_framework_is_front_unexpected(client, status):
    assert_error_report(client.get(f"/test/abort/{status}"), "front.unexpected", 500)


def test_each_unexpected_failure_has_its_own_incident(client, log):
    client.get("/test/raise")
    client.get("/test/raise")
    assert log.lines[-1]["incident"] != log.lines[-2]["incident"]


def test_a_front_error_raised_by_a_handler_is_answered_as_its_report(client, log):
    report = assert_error_report(client.get("/test/refuse"), "front.bad_request", 400)
    assert report["detail"] == "a refusal planted by the test"
    assert log.lines[-1] == {"event": "error", "code": "front.bad_request", "status": 400,
                             "method": "GET", "path": "/test/refuse",
                             "detail": "a refusal planted by the test"}


def test_the_page_version_is_written_in_the_line_when_it_has_the_versions_form(client, log):
    client.get("/nothing", headers={"X-PenguinSlicer-Page": VERSION})
    assert log.lines[-1]["page_version"] == VERSION
    client.get("/nothing", headers={"X-PenguinSlicer-Page": "x" * 500})
    assert "page_version" not in log.lines[-1]


@pytest.mark.parametrize("code", sorted(FRONT_REPORTS))
def test_every_report_of_the_front_server_has_its_fields_and_its_contract_status(code):
    report = error_report(code, "a detail")
    assert set(report) >= set(REQUIRED) and report["detail"] == "a detail"
    contract = CONTRACT.read_text().split("## The front server's error reports", 1)[1]
    row = re.search(rf"^\| `{re.escape(code)}` \| `(\d+)` \| [^|]+ \| (true|false) \|",
                    contract, re.M)
    assert row, f"{code} is not in the contract"
    assert FRONT_REPORTS[code]["status"] == int(row[1])
    assert report["retryable"] is (row[2] == "true")


def test_an_error_report_can_say_where():
    report = error_report("front.bad_request", "d", where={"stage": "checking"})
    assert report["where"] == {"stage": "checking"} and "action" not in report


def test_an_error_report_can_name_its_action():
    assert error_report("front.bad_request", "d", action="slice_again")["action"] == \
        "slice_again"


# Not kept by any proxy or browser, and the version on every answer.

@pytest.mark.parametrize("method, path", [
    ("GET", "/nothing"), ("POST", "/test/json"), ("GET", "/test/raise"),
    ("GET", "/test/refuse"), ("HEAD", "/test/refuse"), ("OPTIONS", "/test/json"),
])
def test_every_answer_carries_the_version_and_no_store(client, method, path):
    answer = client.open(path, method=method, data=b"{}")
    assert answer.headers["X-PenguinSlicer-Version"] == VERSION
    assert answer.headers["Cache-Control"] == "no-store"


def test_a_successful_answer_carries_the_version_and_no_store(client):
    answer = client.post("/test/json", data=b"{}")
    assert answer.status_code == 200
    assert answer.headers["X-PenguinSlicer-Version"] == VERSION
    assert answer.headers["Cache-Control"] == "no-store"


def test_a_page_file_keeps_its_own_cache_control_and_still_carries_the_version(client):
    answer = client.get("/test/page")
    assert answer.headers["Cache-Control"] == "private, no-cache"
    assert answer.headers["X-PenguinSlicer-Version"] == VERSION


def test_every_request_the_application_offers_carries_the_version_and_its_marking(app):
    client = app.test_client()
    for method, rule in offered(app):
        path = re.sub(r"<[^>]+>", "x", rule)
        answer = client.open(path, method=method, data=b"{}")
        assert answer.headers["X-PenguinSlicer-Version"] == VERSION, (method, rule)
        if (method, rule) in PAGE_FILES or rule == "/test/page":
            assert answer.headers["Cache-Control"] != "no-store", (method, rule)
        else:
            assert answer.headers["Cache-Control"] == "no-store", (method, rule)


def test_no_answer_lets_another_site_read_it(client):
    for path in ("/nothing", "/test/refuse", "/test/page"):
        answer = client.get(path, headers={"Origin": "https://other.example"})
        assert not [h for h in answer.headers.keys() if h.lower().startswith("access-control")]


def test_a_version_made_at_start_has_the_versions_form(clock, log):
    application = create_app(Settings.from_environ({"PENGUIN_DEV_IDENTITY": "1"}),
                             clock=clock, log=log)
    version = application.test_client().get("/x").headers["X-PenguinSlicer-Version"]
    assert VERSION_FORM.fullmatch(version) and version == "20261127T221405Z-0000000"


def test_the_versions_setting_is_used_when_set(clock, log):
    settings = Settings.from_environ({"PENGUIN_DEV_IDENTITY": "1",
                                      "PENGUIN_VERSION": "20270101T000000Z-abcdef0"})
    application = create_app(settings, clock=clock, log=log)
    assert application.test_client().get("/x").headers["X-PenguinSlicer-Version"] == \
        "20270101T000000Z-abcdef0"


def test_the_error_body_is_the_whole_report_as_json(client):
    answer = client.get("/nothing")
    assert json.loads(answer.data) == answer.get_json()
    assert set(answer.get_json()) <= set(REQUIRED) | {"where", "action"}
