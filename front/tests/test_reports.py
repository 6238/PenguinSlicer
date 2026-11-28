"""The page's reports about itself (README-details.md, "The page's reports about itself";
contracts/wizard-front-server.md, "The page's reports about itself")."""

import io
import json
from pathlib import Path

import pytest

from front_helpers import DEV_GROUP, KEY, Lines, front, sign_in
from penguin_front import reports
from penguin_front.cookie import COOKIE_NAME, CookieKey, Identity

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "wizard-front"
EXAMPLE = json.loads((EXAMPLES / "report-failure-request.json").read_text())
PAGE_VERSION = "20261127T221405Z-1a2b3c4"
DRAWING = json.loads((EXAMPLES / "report-drawing-request.json").read_text())
LAYOUT = {k: v for k, v in DRAWING.items()
          if k not in ("first_layer_ms", "sliced_file_bytes", "sliced_file_lines")} | \
    {"view": "layout"}


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def client(tmp_path, clock, log):
    client = front(tmp_path, clock, log).test_client()
    sign_in(client)
    return client


def send(client, kind, body, headers=None):
    return client.post(f"/api/reports/{kind}", data=json.dumps(body),
                       headers={**DEV_GROUP, "X-PenguinSlicer-Page": PAGE_VERSION,
                                **(headers or {})})


def written(log, event):
    return [line for line in log.lines if line["event"] == event]


def test_a_failure_report_is_one_line_with_exactly_the_contracts_fields(client, log):
    answer = send(client, "failure", EXAMPLE)
    assert answer.status_code == 204 and answer.get_data() == b""
    [line] = written(log, "failure_report")
    assert line == {"event": "failure_report", "component": "wizard", "user_key": "dev-user",
                    "group": "dev-group", "page_version": PAGE_VERSION, **EXAMPLE}


def test_the_line_is_written_as_the_wizards_on_the_log_as_built(tmp_path, clock):
    import io

    from penguin_front.buckets import FolderBucket
    from penguin_front.log import Log

    out = io.StringIO()
    log = Log(clock, out, FolderBucket(tmp_path / "log", clock))
    client = front(tmp_path, clock, log).test_client()
    sign_in(client)
    assert send(client, "failure", EXAMPLE).status_code == 204
    [line] = [json.loads(text) for text in out.getvalue().splitlines()
              if json.loads(text)["event"] == "failure_report"]
    assert line["component"] == "wizard" and line["what"] == "part_not_drawable"


@pytest.mark.parametrize("body", [DRAWING, LAYOUT])
def test_a_drawing_summary_is_one_line_with_exactly_the_contracts_fields(client, log, body):
    assert send(client, "drawing", body).status_code == 204
    [line] = written(log, "drawing_report")
    assert {k: v for k, v in line.items()
            if k not in ("event", "component", "user_key", "group", "page_version")} == body
    assert line["component"] == "wizard"


def test_a_field_not_listed_is_dropped(client, log):
    send(client, "failure", EXAMPLE | {"storage": {"plate": "everything"}, "name": "bracket"})
    send(client, "drawing", DRAWING | {"part_name": "bracket.stl", "frames": [1, 2, 3]})
    for line in log.lines:
        assert not {"storage", "name", "part_name", "frames"} & set(line)


def test_the_preview_fields_of_a_layout_summary_are_dropped(client, log):
    send(client, "drawing", LAYOUT | {"first_layer_ms": 3, "sliced_file_bytes": 4})
    [line] = written(log, "drawing_report")
    assert "first_layer_ms" not in line and "sliced_file_bytes" not in line


@pytest.mark.parametrize("field, length", [
    ("browser", 40), ("browser_version", 40), ("detail", 1000), ("page", 64)])
def test_a_string_over_its_length_is_cut(client, log, field, length):
    send(client, "failure", EXAMPLE | {field: "x" * (length + 50)})
    [line] = written(log, "failure_report")
    assert line[field] == "x" * length


@pytest.mark.parametrize("field, length", [("os", 40), ("graphics_card", 120)])
def test_a_drawing_string_over_its_length_is_cut(client, log, field, length):
    send(client, "drawing", DRAWING | {field: "y" * 500})
    [line] = written(log, "drawing_report")
    assert line[field] == "y" * length


def bad_request(answer, log, field):
    assert answer.status_code == 400
    report = answer.get_json()
    assert report["code"] == "front.bad_request" and field in report["detail"]
    assert not written(log, "failure_report") and not written(log, "drawing_report")


@pytest.mark.parametrize("field, value", [
    ("what", "everything_failed"), ("step", "checkout"), ("what", 3), ("browser", 7),
    ("software_3d", "yes"), ("page", ""), ("page", None), ("page", "   "), ("page", "\t\n"),
    ("page", "\u0000\u0000"), ("page", "​"), ("page", "page-\u0007id"),
    ("page", "\ud800"),
])
def test_a_failure_field_off_its_list_or_of_a_bad_form_is_refused(client, log, field, value):
    bad_request(send(client, "failure", EXAMPLE | {field: value}), log, field)


@pytest.mark.parametrize("field", ["page", "what", "step", "browser", "browser_version",
                                   "software_3d"])
def test_a_failure_report_without_a_required_field_is_refused(client, log, field):
    body = {k: v for k, v in EXAMPLE.items() if k != field}
    bad_request(send(client, "failure", body), log, field)


@pytest.mark.parametrize("field, value", [
    ("view", "sideways"), ("drawing", "crayon"), ("fps_typical", "fast"),
    ("fps_worst", True), ("instances", None), ("in_onshape", 0),
])
def test_a_drawing_field_off_its_list_or_of_a_bad_form_is_refused(client, log, field, value):
    bad_request(send(client, "drawing", DRAWING | {field: value}), log, field)


@pytest.mark.parametrize("field", ["first_layer_ms", "sliced_file_bytes",
                                   "sliced_file_lines"])
def test_a_preview_summary_without_its_preview_fields_is_refused(client, log, field):
    body = {k: v for k, v in DRAWING.items() if k != field}
    bad_request(send(client, "drawing", body), log, field)


@pytest.mark.parametrize("field, value", [
    ("part_sha256", "bracket.stl"), ("part_sha256", "9F" * 32), ("detail", 12),
])
def test_an_optional_failure_field_of_a_bad_form_is_dropped(client, log, field, value):
    assert send(client, "failure", EXAMPLE | {field: value}).status_code == 204
    [line] = written(log, "failure_report")
    assert field not in line


@pytest.mark.parametrize("field, value", [
    ("graphics_card", 5), ("processors", "eight"), ("memory_gb", False)])
def test_an_optional_drawing_field_of_a_bad_form_is_dropped(client, log, field, value):
    assert send(client, "drawing", DRAWING | {field: value}).status_code == 204
    [line] = written(log, "drawing_report")
    assert field not in line


@pytest.mark.parametrize("body", [b"[1, 2]", b"\"text\"", b"not json"])
def test_a_body_that_is_not_an_object_is_refused(client, log, body):
    answer = client.post("/api/reports/failure", data=body, headers=DEV_GROUP)
    assert answer.status_code == 400 and answer.get_json()["code"] == "front.bad_request"


def test_a_report_over_its_size_is_refused_before_it_is_read(client, log):
    body = EXAMPLE | {"detail": "x" * reports.MAX_REPORT_BYTES}
    answer = send(client, "failure", body)
    assert answer.status_code == 400 and answer.get_json()["code"] == "front.bad_request"
    assert str(reports.MAX_REPORT_BYTES) in answer.get_json()["detail"].replace(",", "")
    assert not written(log, "failure_report")


@pytest.mark.parametrize("value", [10 ** 400, -(10 ** 400)], ids=["huge", "huge-negative"])
def test_a_required_whole_number_too_large_for_a_float_is_refused(client, log, value):
    # JSON's whole numbers have no bound: one too large for a float is no honest figure.
    body = json.dumps(DRAWING).replace(f'"fps_worst": {json.dumps(DRAWING["fps_worst"])}',
                                       f'"fps_worst": {value}')
    assert str(value) in body
    answer = client.post("/api/reports/drawing", data=body, headers=DEV_GROUP)
    bad_request(answer, log, "fps_worst")


def test_an_optional_whole_number_too_large_for_a_float_is_dropped(client, log):
    body = json.dumps(DRAWING | {"processors": 1}).replace('"processors": 1',
                                                           f'"processors": {10 ** 400}')
    answer = client.post("/api/reports/drawing", data=body, headers=DEV_GROUP)
    assert answer.status_code == 204
    [line] = written(log, "drawing_report")
    assert "processors" not in line


class Counted(io.BytesIO):
    """A request body that counts the bytes the front server takes from it."""

    def __init__(self, body):
        super().__init__(body)
        self.taken = 0

    def _count(self, data):
        self.taken += len(data)
        return data

    def read(self, size=-1):
        return self._count(super().read(size))

    def read1(self, size=-1):
        return self._count(super().read1(size))

    def readline(self, size=-1):
        return self._count(super().readline(size))

    def readinto(self, buffer):
        taken = super().readinto(buffer)
        self.taken += taken
        return taken


def unmeasured(client, body):
    """A report sent without Content-Length, its body ended by the stream."""
    stream = body if isinstance(body, Counted) else io.BytesIO(body)
    return client.post("/api/reports/failure", headers=DEV_GROUP, environ_overrides={
        "wsgi.input": stream, "CONTENT_LENGTH": None,
        "wsgi.input_terminated": True})


def test_a_report_without_a_length_is_read_no_further_than_its_size(client, log):
    # A body sixty-four times the limit: only one byte past the limit is taken from it.
    stream = Counted(json.dumps(
        EXAMPLE | {"detail": "x" * (64 * reports.MAX_REPORT_BYTES)}).encode())
    answer = unmeasured(client, stream)
    assert answer.status_code == 400 and answer.get_json()["code"] == "front.bad_request"
    assert "without Content-Length" in answer.get_json()["detail"]
    assert 0 < stream.taken <= reports.MAX_REPORT_BYTES + 1
    assert unmeasured(client, json.dumps(EXAMPLE).encode()).status_code == 204
    assert len(written(log, "failure_report")) == 1


def measured(client, body):
    """A report sent with a Content-Length that says its whole size."""
    stream = body if isinstance(body, Counted) else Counted(body)
    return client.post("/api/reports/failure", headers=DEV_GROUP, environ_overrides={
        "wsgi.input": stream, "CONTENT_LENGTH": str(len(stream.getvalue()))})


def test_a_report_whose_length_is_over_its_size_is_refused_before_any_of_it_is_taken(
        client, log):
    stream = Counted(json.dumps(EXAMPLE | {"detail": "x" * reports.MAX_REPORT_BYTES})
                     .encode())
    answer = measured(client, stream)
    assert answer.status_code == 400 and answer.get_json()["code"] == "front.bad_request"
    assert "without Content-Length" not in answer.get_json()["detail"]
    assert stream.taken == 0
    assert not written(log, "failure_report")


def padded(size):
    """The example as a body of exactly `size` bytes: JSON allows spaces after the object."""
    body = json.dumps(EXAMPLE).encode()
    return body + b" " * (size - len(body))


def test_a_report_of_exactly_its_size_is_read_and_one_byte_more_is_refused(client, log):
    limit = reports.MAX_REPORT_BYTES
    assert measured(client, padded(limit)).status_code == 204
    over = Counted(padded(limit + 1))
    assert measured(client, over).status_code == 400 and over.taken == 0
    assert unmeasured(client, padded(limit)).status_code == 204
    assert unmeasured(client, padded(limit + 1)).status_code == 400
    assert len(written(log, "failure_report")) == 2


def too_many(answer):
    assert answer.status_code == 429
    report = answer.get_json()
    assert report["code"] == "front.too_many_reports" and report["retryable"] is False
    return report


def test_a_seventh_report_of_one_page_in_a_minute_is_refused(client, clock, log):
    for _ in range(reports.REPORTS_PER_PAGE_PER_MINUTE):
        assert send(client, "failure", EXAMPLE).status_code == 204
    too_many(send(client, "drawing", DRAWING | {"page": EXAMPLE["page"]}))
    assert len(written(log, "failure_report")) == 6
    # Another page of the same user is not.
    assert send(client, "failure", EXAMPLE | {"page": "another-page"}).status_code == 204
    clock.advance(60)
    assert send(client, "failure", EXAMPLE).status_code == 204


def test_a_refused_report_is_not_counted(client):
    for _ in range(reports.REPORTS_PER_PAGE_PER_MINUTE):
        send(client, "failure", EXAMPLE | {"what": "nothing of the list"})
    assert send(client, "failure", EXAMPLE).status_code == 204


def test_the_limit_is_counted_for_the_user_and_the_page(tmp_path, clock, log):
    app = front(tmp_path, clock, log)
    first, second = app.test_client(), app.test_client()
    sign_in(first)
    second.set_cookie(COOKIE_NAME, CookieKey(KEY).seal(Identity(
        "another-user", "Another User", (("dev-group", "Development Group"),), None,
        int(clock.now()))))
    for _ in range(reports.REPORTS_PER_PAGE_PER_MINUTE):
        send(first, "failure", EXAMPLE)
    too_many(send(first, "failure", EXAMPLE))
    assert send(second, "failure", EXAMPLE).status_code == 204


def test_a_report_without_a_sign_in_is_refused(tmp_path, clock, log):
    client = front(tmp_path, clock, log).test_client()
    for kind, body in (("failure", EXAMPLE), ("drawing", DRAWING)):
        answer = send(client, kind, body)
        assert answer.status_code == 401
        assert answer.get_json()["code"] == "front.not_signed_in"
    assert not written(log, "failure_report")


@pytest.mark.parametrize("headers", [{"X-PenguinSlicer-Group": "not-my-group"},
                                     {"X-PenguinSlicer-Group": ""}])
def test_a_report_naming_a_group_not_the_users_is_written_without_the_group(client, log,
                                                                            headers):
    assert send(client, "failure", EXAMPLE, headers).status_code == 204
    [line] = written(log, "failure_report")
    assert "group" not in line
    assert not written(log, "refused")


def test_a_report_without_a_group_or_a_page_version_is_written_without_them(client, log):
    answer = client.post("/api/reports/failure", data=json.dumps(EXAMPLE),
                         headers={"X-PenguinSlicer-Page": "not a version"})
    assert answer.status_code == 204
    [line] = written(log, "failure_report")
    assert "group" not in line and "page_version" not in line
