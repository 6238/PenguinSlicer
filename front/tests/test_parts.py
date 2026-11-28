"""The user key, and uploading a part with its limit on how fast (README-details.md, "The user
key" and "Parts"; contracts/wizard-front-server.md, "`POST /api/parts`"; contracts/
slice-http-interface.md, "`POST /parts?units=`")."""

import io
import json
import struct
from pathlib import Path

import httpx
import pytest

from front_helpers import DEV_GROUP, Lines, environ, front, shut, sign_in
from penguin_front import parts
from penguin_front.app import create_app
from penguin_front.ratelimit import RateLimit
from penguin_front.settings import Settings
from penguin_front.slice_client import SliceClient

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"
BRACKET = (EXAMPLES / "parts" / "bracket.stl").read_bytes()
OVER_SIZE = (EXAMPLES / "error-report-part-over-size.json").read_bytes()


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def app(tmp_path, clock, log, standin):
    app = front(tmp_path, clock, log, PENGUIN_SLICE_URL=standin.url)
    yield app
    shut(app, standin)


@pytest.fixture
def client(app):
    client = app.test_client()
    sign_in(client)
    return client


def upload(client, body=BRACKET, units="mm", headers=None, **extra):
    query = {} if units is None else {"units": units}
    return client.post("/api/parts", data=body, query_string=query,
                       content_type="application/octet-stream",
                       headers={**DEV_GROUP, **(headers or {})}, **extra)


def uploads(standin):
    return [r for r in standin.requests if r.method == "POST" and r.path == "/parts"]


def stl(triangles):
    """A binary STL of `triangles` triangles, each the same small one."""
    one = struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0)
    return b"\0" * 80 + struct.pack("<I", triangles) + one * triangles


def raw_upload(client, stream, length, units="mm"):
    """An upload whose body is `stream` and whose `Content-Length` is `length` as given (None
    for none), set in the environment directly, since the test client would measure the
    stream itself."""
    return client.post("/api/parts", query_string={"units": units}, headers=DEV_GROUP,
                       environ_overrides={"wsgi.input": stream,
                                          "CONTENT_LENGTH": None if length is None
                                          else str(length)})


class Unreadable(io.BytesIO):
    """A request body that fails the test if anything reads it."""

    def read(self, *_args):
        raise AssertionError("the body was read")

    readinto = readline = read1 = read


# The part passes through.

def test_an_uploaded_part_reaches_the_slice_service_byte_for_byte_with_the_user_key(
        client, standin):
    answer = upload(client, units="in")
    assert answer.status_code == 201
    [sent] = uploads(standin)
    assert sent.body == BRACKET and sent.user_key == "dev-user" and sent.query == "units=in"
    assert sent.headers["content-length"] == str(len(BRACKET))
    assert sent.headers["content-type"] == "application/octet-stream"
    assert "transfer-encoding" not in sent.headers
    record = standin.parts["dev-user"][(answer.get_json()["sha256"], "in")]
    assert answer.get_json() == record
    assert answer.headers["Cache-Control"] == "no-store"


def test_the_slice_services_record_reaches_the_page_byte_for_byte(client, standin):
    record = json.loads((EXAMPLES / "wizard-front" / "part-record.json").read_text())
    standin.answer_next("POST", "/parts", 201, record)
    answer = upload(client)
    assert answer.status_code == 201 and answer.mimetype == "application/json"
    assert answer.data == json.dumps(record).encode()


def test_a_repeat_of_the_same_bytes_and_units_answers_the_same_record(client, standin):
    first, second = upload(client), upload(client)
    assert first.data == second.data and len(uploads(standin)) == 2


def test_an_upload_writes_a_line_with_the_user_key_the_group_and_the_part(client, log):
    record = upload(client, units="in").get_json()
    [line] = log.events("part_uploaded")
    assert line == {"event": "part_uploaded", "user_key": "dev-user", "group": "dev-group",
                    "sha256": record["sha256"], "units": "in", "bytes": len(BRACKET),
                    "triangles": (len(BRACKET) - 84) // 50, "warnings": 0}
    assert record["measurements"]["triangles"] == line["triangles"]


# The user key comes from the cookie alone.

def test_a_user_key_in_the_body_query_or_headers_is_never_read(client, standin):
    answer = client.post("/api/parts", data=BRACKET,
                         query_string={"units": "mm", "user_key": "someone-else"},
                         headers={**DEV_GROUP, "X-Penguin-User-Key": "someone-else",
                                  "X-PenguinSlicer-User": "someone-else"})
    assert answer.status_code == 201
    assert [r.user_key for r in uploads(standin)] == ["dev-user"]
    assert uploads(standin)[0].query == "units=mm"


# Refusals of the slice service, passed unchanged.

@pytest.mark.parametrize("code, status", [
    ("slice.part_unreadable", 422), ("slice.part_not_binary", 422),
    ("slice.part_too_small", 422), ("slice.part_no_volume", 422),
    ("slice.part_too_large", 422), ("slice.part_too_detailed", 413),
    ("slice.bad_units", 400), ("slice.scratch_unwritable", 500),
])
def test_each_refusal_of_the_slice_service_reaches_the_page_unchanged(client, standin, log,
                                                                      code, status):
    report = {"code": code, "message": "m", "where": {"stage": "checking"}, "remedy": "r",
              "retryable": False, "detail": "d"}
    standin.answer_next("POST", "/parts", status, report)
    answer = upload(client)
    assert answer.status_code == status and answer.data == json.dumps(report).encode()
    assert log.events("error")[-1]["code"] == code
    assert log.events("part_uploaded") == []


def test_units_neither_mm_nor_in_are_refused_by_the_slice_service(client, standin):
    for units in (None, "cm"):
        answer = upload(client, units=units)
        assert answer.status_code == 400 and answer.get_json()["code"] == "slice.bad_units"
    assert [r.query for r in uploads(standin)] == ["", "units=cm"]


def test_a_part_the_slice_service_cannot_read_is_its_refusal(client):
    answer = upload(client, body=b"solid text\nendsolid\n")
    assert answer.status_code == 422 and answer.get_json()["code"] == "slice.part_unreadable"


def test_the_slice_services_no_user_key_is_the_front_servers_fault(client, standin, log):
    no_key = json.loads((EXAMPLES / "slice-http" / "no-user-key.json").read_text())
    standin.answer_next("POST", "/parts", 400, no_key)
    answer = upload(client)
    assert answer.status_code == 500 and answer.get_json()["code"] == "front.unexpected"
    assert "slice.no_user_key" in log.events("error")[-1]["trace"]


@pytest.mark.parametrize("body", [{"code": "front.x"}, ["a list"], {"message": "m"}])
def test_an_answer_that_is_neither_record_nor_report_is_unexpected(client, standin, body):
    standin.answer_next("POST", "/parts", 502, body)
    answer = upload(client)
    assert answer.status_code == 500 and answer.get_json()["code"] == "front.unexpected"


def test_the_slice_service_not_answering_is_front_slice_unreachable(client, standin):
    standin.unreachable()
    answer = upload(client)
    assert answer.status_code == 503
    assert answer.get_json()["code"] == "front.slice_unreachable"
    assert answer.get_json()["retryable"] is True


# The size.

def test_a_content_length_over_the_limit_is_refused_before_any_byte_is_read(client, standin):
    answer = raw_upload(client, Unreadable(), 7_500_085)
    # The example's report, field for field and in its order (the file is laid out for
    # reading; the slice service's suite compares its answer the same way).
    assert answer.status_code == 413
    assert list(answer.get_json().items()) == list(json.loads(OVER_SIZE).items())
    assert answer.headers["Content-Type"] == "application/json"
    assert uploads(standin) == []


def test_the_over_size_refusals_detail_gives_the_length_sent(client):
    answer = raw_upload(client, Unreadable(), 9_000_000)
    report = answer.get_json()
    assert report["code"] == "slice.part_too_detailed"
    assert report["detail"] == "upload Content-Length 9,000,000 bytes, cap 7,500,084"


def test_a_part_of_exactly_the_limit_passes(client, standin):
    body = stl(150_000)
    assert len(body) == 7_500_084 == parts.MAX_PART_BYTES
    answer = upload(client, body=body)
    assert answer.status_code == 201
    assert uploads(standin)[0].body == body


def test_an_upload_without_content_length_is_front_bad_request(client, standin, log):
    answer = raw_upload(client, io.BytesIO(BRACKET), None)
    assert answer.status_code == 400 and answer.get_json()["code"] == "front.bad_request"
    assert "Content-Length" in answer.get_json()["detail"]
    assert uploads(standin) == []


def test_an_upload_cut_short_of_its_content_length_is_front_bad_request(client, standin):
    answer = raw_upload(client, io.BytesIO(BRACKET[:1000]), len(BRACKET))
    assert answer.status_code == 400 and answer.get_json()["code"] == "front.bad_request"
    assert "parts" not in standin.parts


@pytest.mark.parametrize("body", [b"not json", b"[1]",
                                  b'{"measurements": 5, "warnings": 3}'])
def test_a_success_of_another_shape_passes_unchanged_and_its_line_has_nulls(client, standin,
                                                                           log, body):
    @standin.app.before_request
    def odd():
        from flask import Response

        return Response(body, 201, mimetype="application/json")

    answer = upload(client)
    assert answer.status_code == 201 and answer.data == body
    [line] = log.events("part_uploaded")
    assert line["sha256"] is None and line["triangles"] is None and line["warnings"] == 0


def test_a_body_that_ends_short_without_the_servers_notice_is_front_bad_request():
    # The web framework raises on a body cut short; were it ever to give an empty piece
    # instead, the upload stops there rather than looping.
    from penguin_front.errors import FrontError

    with pytest.raises(FrontError, match="short of its Content-Length"):
        list(parts._pieces(io.BytesIO(b"abc"), 10))


# Passed in pieces.

def test_the_part_passes_in_pieces_never_held_whole(tmp_path, clock, log):
    # The body the browser sends is counted as the front server reads it; the slice
    # service's side reads the upload piece by piece and notes, after each piece, how far
    # ahead of it the front server has read. That difference is all the front server holds.
    body = stl(150_000)
    source = io.BytesIO(body)
    held = []

    class SliceService(httpx.BaseTransport):
        # Not httpx.MockTransport, which reads the whole request before its handler runs.
        def handle_request(self, request):
            received = 0
            for piece in request.stream:
                received += len(piece)
                held.append(source.tell() - received)
            held.append(("received", received))
            return httpx.Response(201, stream=httpx.ByteStream(b'{"sha256": "x"}'))

    app = create_app(Settings.from_environ(environ(tmp_path)), clock=clock, log=log,
                     slice_client=SliceClient("http://slice.invalid",
                                              transport=SliceService()))
    client = app.test_client()
    sign_in(client)
    answer = raw_upload(client, source, len(body))
    assert answer.status_code == 201, log.lines[-1].get("trace")
    assert held.pop() == ("received", len(body))
    assert len(held) > 1 and max(held) <= parts.PIECE_BYTES < len(body)


# Signed in, and the group.

def test_an_upload_without_a_sign_in_is_refused_and_nothing_is_sent(app, standin):
    answer = app.test_client().post("/api/parts?units=mm", data=BRACKET, headers=DEV_GROUP)
    assert answer.status_code == 401 and uploads(standin) == []


def test_an_upload_naming_a_group_not_the_users_is_refused_and_nothing_is_sent(client,
                                                                               standin):
    answer = upload(client, headers={"X-PenguinSlicer-Group": "a-group-of-nobody"})
    assert answer.status_code == 403 and answer.get_json()["code"] == "front.group_not_allowed"
    assert uploads(standin) == []


# How fast.

def test_the_limit_is_120_uploads_a_minute_for_each_user():
    assert parts.PART_UPLOADS_PER_MINUTE == 120


def test_past_the_limit_an_upload_is_too_many_requests_with_retry_after(
        tmp_path, clock, log, standin, monkeypatch):
    monkeypatch.setattr(parts, "PART_UPLOADS_PER_MINUTE", 3)
    app = front(tmp_path, clock, log, PENGUIN_SLICE_URL=standin.url)
    try:
        client = app.test_client()
        sign_in(client)
        for _ in range(3):
            assert upload(client).status_code == 201
            clock.advance(10)
        refused = upload(client)
        assert refused.status_code == 429
        report = refused.get_json()
        assert report["code"] == "front.too_many_requests" and report["retryable"] is True
        assert refused.headers["Retry-After"] == "30"
        assert len(uploads(standin)) == 3
        assert log.events("error")[-1]["code"] == "front.too_many_requests"
        clock.advance(29)
        assert upload(client).headers["Retry-After"] == "1"
        clock.advance(1)
        assert upload(client).status_code == 201
    finally:
        shut(app)


def test_a_refused_upload_does_not_count_toward_the_limit(tmp_path, clock, log, standin,
                                                          monkeypatch):
    monkeypatch.setattr(parts, "PART_UPLOADS_PER_MINUTE", 1)
    app = front(tmp_path, clock, log, PENGUIN_SLICE_URL=standin.url)
    try:
        client = app.test_client()
        sign_in(client)
        assert raw_upload(client, Unreadable(), 7_500_085).status_code == 413
        assert upload(client).status_code == 201
        assert upload(client).status_code == 429
    finally:
        shut(app)


def test_the_limit_holds_for_each_user_by_itself(clock):
    limit = RateLimit(clock, 2)
    assert limit.take("a") is None and limit.take("a") is None
    assert limit.take("a") == 60
    assert limit.take("b") is None
    clock.advance(59.5)
    assert limit.take("a") == 1
    clock.advance(0.5)
    assert limit.take("a") is None


def test_the_limit_forgets_a_user_whose_minute_has_passed(clock):
    limit = RateLimit(clock, 2)
    limit.take("a")
    clock.advance(60)
    limit.take("b")
    assert limit.users() == 1
