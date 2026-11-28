"""The development identity and the cookie, with one cookie key (README-details.md, "The
development identity", "The cookie", "Running phase 2 on one machine"; contracts/
wizard-front-server.md, "Signed in" and "`GET /signin`")."""

import base64
import json
import re

import pytest

from front_helpers import KEY, Lines, front, sign_in
from onshape_standin import OnshapeStandIn
from penguin_front.cookie import (COOKIE_EXTEND_AFTER_S, COOKIE_FORMAT, COOKIE_LIFETIME_S,
                                  COOKIE_NAME, COOKIE_SIZE_LINE_BYTES, CookieKey, Identity)
from penguin_front.errors import FrontError
from penguin_front.identity import DEV_IDENTITY, signed_in

#: Werkzeug warns of a cookie past the browsers' 4 KB, which these tests make on purpose.
too_large = pytest.mark.filterwarnings("ignore:The 'penguinslicer' cookie is too large")

DAY = 86_400
DEV_COOKIE = {"user": ("dev-user", "Development User"),
              "groups": (("dev-group", "Development Group"),)}


def planted(app):
    """A request that needs a signed-in user and says who it is, planted by the test."""

    @app.get("/api/test-who")
    def who():
        identity = signed_in()
        return {"user": identity.user_id, "name": identity.user_name}

    @app.get("/api/test-refuse")
    def refuse():
        signed_in()
        raise FrontError("front.bad_request", "a refusal planted by the test")

    return app


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def app(tmp_path, clock, log):
    return planted(front(tmp_path, clock, log))


@pytest.fixture
def client(app):
    return app.test_client()


def cookie_header(answer):
    """The answer's Set-Cookie for the cookie, or None."""
    found = [value for value in answer.headers.getlist("Set-Cookie")
             if value.startswith(COOKIE_NAME + "=")]
    assert len(found) <= 1
    return found[0] if found else None


def cookie_value(answer):
    return cookie_header(answer).split(";", 1)[0].split("=", 1)[1]


# The development identity.

def test_signin_with_the_development_identity_sets_its_cookie_and_goes_to_return(client, log):
    onshape = OnshapeStandIn()
    onshape.start()
    try:
        answer = client.get("/signin?return=/%3Fplate%3D2")
    finally:
        onshape.stop()
    assert answer.status_code == 302 and answer.headers["Location"] == "/?plate=2"
    assert cookie_header(answer) is not None
    assert onshape.calls == []
    who = client.get("/api/test-who")
    assert who.status_code == 200
    assert who.get_json() == {"user": "dev-user", "name": "Development User"}
    [line] = log.events("sign_in")
    assert line == {"event": "sign_in", "user_key": "dev-user",
                    "user_name": "Development User",
                    "groups": [{"id": "dev-group", "name": "Development Group"}],
                    "dev_identity": True}


def test_the_development_identitys_four_values_are_the_tables():
    assert DEV_IDENTITY.user_id == "dev-user"
    assert DEV_IDENTITY.user_name == "Development User"
    assert DEV_IDENTITY.groups == (("dev-group", "Development Group"),)


@pytest.mark.parametrize("given", ["//other.example/", "https://other.example/", "x", "",
                                   "/\\other.example", "\\\\other.example", "/a\r\nSet-Cookie: x",
                                   "/a\tb", "/a\x7fb"])
def test_a_return_that_is_not_a_path_of_this_site_comes_back_as_slash(client, given):
    answer = client.get("/signin", query_string={"return": given})
    assert answer.status_code == 302 and answer.headers["Location"] == "/"


def test_a_signin_without_return_goes_to_slash(client):
    assert client.get("/signin").headers["Location"] == "/"


@pytest.mark.parametrize("given", ["/", "/?in=x&plate=2", "/assets/a.js", "/a//b"])
def test_a_return_that_is_a_path_of_this_site_is_kept(client, given):
    answer = client.get("/signin", query_string={"return": given})
    assert answer.headers["Location"] == given


def test_a_signed_in_browser_makes_the_trip_as_well_and_gets_a_fresh_cookie(client, clock):
    first = cookie_value(sign_in(client))
    clock.advance(5)
    second = cookie_value(sign_in(client))
    assert first != second
    assert client.get("/api/test-who").status_code == 200


def test_with_the_development_identity_off_signin_is_not_offered(tmp_path, clock, log):
    app = front(tmp_path, clock, log, PENGUIN_DEV_IDENTITY=None)
    answer = app.test_client().get("/signin")
    assert answer.status_code == 404
    report = answer.get_json()
    assert report["code"] == "front.no_such_request" and "phase 3" in report["detail"]
    assert cookie_header(answer) is None


#: The requests that need no signed-in user (README-details.md, "Which requests need a
#: signed-in user"), each answering in its own way without one.
NO_SIGN_IN = {"/", "/signin", "/signin/callback", "/api/signout", "/signed-out"}


def test_every_request_but_the_exceptions_refuses_one_without_a_cookie(tmp_path, clock):
    from test_rules import offered

    app = front(tmp_path, clock)
    client = app.test_client()
    found = offered(app)
    assert {path for _method, path in found} & NO_SIGN_IN == {"/", "/signin"}
    for method, rule in sorted(found):
        if rule in NO_SIGN_IN:
            continue
        path = re.sub(r"<[^>]+>", "panel.3f9a1c2b7e04.js", rule)
        answer = client.open(path, method=method, json={},
                             headers={"X-PenguinSlicer-Group": "dev-group"})
        assert answer.status_code == 401, (method, rule)
        assert answer.get_json()["code"] == "front.not_signed_in"


# The cookie.

def test_the_cookie_on_one_machine_is_httponly_lax_and_not_secure(client):
    header = cookie_header(sign_in(client))
    attributes = {part.strip().split("=", 1)[0].lower(): part.strip()
                  for part in header.split(";")[1:]}
    assert "httponly" in attributes and attributes["path"] == "Path=/"
    assert attributes["samesite"] == "SameSite=Lax"
    assert "secure" not in attributes
    assert attributes["max-age"] == f"Max-Age={COOKIE_LIFETIME_S}"


def test_the_cookie_hosted_is_httponly_secure_samesite_none(tmp_path, clock):
    app = front(tmp_path, clock, PENGUIN_BASE_URL="https://penguinslicer.popcornpenguins.com")
    header = cookie_header(sign_in(app.test_client()))
    parts = [part.strip() for part in header.split(";")[1:]]
    assert "HttpOnly" in parts and "Secure" in parts and "SameSite=None" in parts
    assert "Path=/" in parts


def test_no_cookie_is_no_sign_in(client):
    answer = client.get("/api/test-who")
    assert answer.status_code == 401
    assert answer.get_json()["code"] == "front.not_signed_in"
    assert answer.get_json()["retryable"] is False


def test_a_cookie_changed_by_a_single_byte_is_no_sign_in(client):
    value = cookie_value(sign_in(client))
    raw = bytearray(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
    for position in (0, 13, len(raw) // 2, len(raw) - 1):
        changed = bytearray(raw)
        changed[position] ^= 0x01
        text = base64.urlsafe_b64encode(bytes(changed)).decode().rstrip("=")
        client.set_cookie(COOKIE_NAME, text)
        assert client.get("/api/test-who").status_code == 401, position


@too_large
@pytest.mark.parametrize("text", ["", "x", "!!!!", "a" * 10, "a" * 5000, "é"])
def test_a_cookie_that_is_not_one_of_ours_is_no_sign_in(client, text):
    client.set_cookie(COOKIE_NAME, text)
    assert client.get("/api/test-who").get_json()["code"] == "front.not_signed_in"


def test_a_cookie_made_with_an_unknown_key_is_no_sign_in(client, clock):
    other = CookieKey("another-key-the-front-server-never-had")
    client.set_cookie(COOKIE_NAME, other.seal(DEV_IDENTITY.used(clock.now())))
    assert client.get("/api/test-who").status_code == 401


def test_a_cookie_used_29_days_after_its_last_use_is_read_and_moves_the_30_days_on(client,
                                                                                  clock):
    sign_in(client)
    clock.advance(29 * DAY)
    answer = client.get("/api/test-who")
    assert answer.status_code == 200 and cookie_header(answer) is not None
    clock.advance(29 * DAY)
    assert client.get("/api/test-who").status_code == 200


def test_a_cookie_unused_for_30_days_is_no_sign_in(client, clock):
    sign_in(client)
    clock.advance(COOKIE_LIFETIME_S - 1)
    assert client.get("/api/test-who").status_code == 200
    client.get("/signin")  # a new cookie; then thirty days with no use
    clock.advance(COOKIE_LIFETIME_S)
    assert client.get("/api/test-who").get_json()["code"] == "front.not_signed_in"


def test_a_cookie_used_every_20_days_for_a_year_is_still_read(client, clock):
    sign_in(client)
    signed_in_at = clock.now()
    while clock.now() - signed_in_at < 365 * DAY:
        clock.advance(20 * DAY)
        assert client.get("/api/test-who").status_code == 200


def test_an_answer_within_a_day_of_the_last_extension_carries_no_set_cookie(client, clock):
    sign_in(client)
    clock.advance(COOKIE_EXTEND_AFTER_S)
    assert cookie_header(client.get("/api/test-who")) is None
    clock.advance(1)
    assert cookie_header(client.get("/api/test-who")) is not None
    clock.advance(DAY - 1)
    assert cookie_header(client.get("/api/test-who")) is None


def test_an_error_answer_to_a_signed_in_request_extends_the_cookie_too(client, clock):
    sign_in(client)
    clock.advance(2 * DAY)
    answer = client.get("/api/test-refuse")
    assert answer.status_code == 400 and cookie_header(answer) is not None


def test_an_answer_to_a_request_that_reads_no_cookie_carries_none(client, clock):
    sign_in(client)
    clock.advance(2 * DAY)
    assert cookie_header(client.get("/api/nothing")) is None


def test_a_restart_with_the_same_key_reads_every_cookie_set_before_it(tmp_path, clock):
    before = front(tmp_path, clock).test_client()
    value = cookie_value(sign_in(before))
    after = planted(front(tmp_path, clock)).test_client()
    after.set_cookie(COOKIE_NAME, value)
    assert after.get("/api/test-who").get_json()["user"] == "dev-user"


def test_a_restart_with_another_key_reads_no_cookie_set_before_it(tmp_path, clock):
    value = cookie_value(sign_in(front(tmp_path, clock).test_client()))
    after = planted(front(tmp_path, clock, PENGUIN_COOKIE_KEY="a-key-after-the-restart"))
    client = after.test_client()
    client.set_cookie(COOKIE_NAME, value)
    assert client.get("/api/test-who").status_code == 401


def test_without_a_cookie_key_a_key_is_made_in_memory_and_a_restart_signs_in_again(
        tmp_path, clock):
    # The line saying so is written by the start (tests/test_server.py).
    first = front(tmp_path, clock, PENGUIN_COOKIE_KEY=None).test_client()
    value = cookie_value(sign_in(first))
    second = planted(front(tmp_path, clock, PENGUIN_COOKIE_KEY=None)).test_client()
    second.set_cookie(COOKIE_NAME, value)
    assert second.get("/api/test-who").get_json()["code"] == "front.not_signed_in"
    sign_in(second)
    assert second.get("/api/test-who").status_code == 200


# What the cookie holds, its format, and its size.

def test_the_cookie_holds_its_fields_encrypted_and_nothing_readable(client, clock):
    value = cookie_value(sign_in(client))
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    assert b"dev-user" not in raw and b"Development" not in raw
    opened = CookieKey(KEY).open(value, clock.now())
    assert opened == Identity("dev-user", "Development User",
                              (("dev-group", "Development Group"),), None, int(clock.now()))


def test_a_cookie_of_this_format_and_of_every_earlier_one_is_read(clock):
    key = CookieKey(KEY)
    for format_number in range(1, COOKIE_FORMAT + 1):
        text = key.seal_fields({"format": format_number, "user": {"id": "u", "name": "U"},
                                "groups": [{"id": "g", "name": "G"}], "tokens": None,
                                "used_at": int(clock.now())})
        assert key.open(text, clock.now()).user_id == "u"


@pytest.mark.parametrize("fields", [
    {"format": COOKIE_FORMAT + 1},
    {"format": 0}, {"format": "1"}, {"format": True}, {"format": None},
    {"used_at": "yesterday"}, {"used_at": None},
    {"user": "dev-user"}, {"user": {"id": "", "name": "U"}}, {"user": {"id": 5, "name": "U"}},
    {"groups": []}, {"groups": [{"id": "g"}]}, {"groups": "g"},
    {"groups": [{"id": "g", "name": 3}]},
])
def test_a_cookie_of_a_format_or_shape_this_front_server_does_not_read_is_no_sign_in(clock,
                                                                                    fields):
    key = CookieKey(KEY)
    whole = {"format": 1, "user": {"id": "u", "name": "U"},
             "groups": [{"id": "g", "name": "G"}], "tokens": None,
             "used_at": int(clock.now()), **fields}
    assert key.open(key.seal_fields(whole), clock.now()) is None


def test_sealed_text_that_is_not_a_json_object_is_no_sign_in(clock):
    key = CookieKey(KEY)
    assert key.open(key.seal_bytes(b"[1, 2]"), clock.now()) is None
    assert key.open(key.seal_bytes(b"\xff not json"), clock.now()) is None


@too_large
def test_the_cookie_of_a_user_with_sixty_groups_of_80_character_names_is_set_and_its_size_said(
        tmp_path, clock, capsys):
    log = Lines()
    app = front(tmp_path, clock, log)
    many = Identity("5f0c2a9e1b7d4c3a8e6f1234", "A" * 80,
                    tuple((f"{n:024x}", chr(65 + n % 26) * 80) for n in range(60)),
                    {"access": "a" * 40, "refresh": "r" * 40}, int(clock.now()))
    with app.test_request_context("/"):
        from penguin_front.identity import set_cookie_for
        response = app.response_class("")
        set_cookie_for(response, many)
    header = cookie_header(response)
    size = len(header.split(";", 1)[0])
    [line] = log.events("cookie_large")
    assert line["bytes"] == size and size > COOKIE_SIZE_LINE_BYTES
    assert line["user_key"] == "5f0c2a9e1b7d4c3a8e6f1234" and line["groups"] == 60
    with capsys.disabled():
        print(f"\nthe cookie of a user with sixty groups of 80-character names: {size} bytes")


def test_the_development_identitys_cookie_is_well_under_the_size_line(client, log):
    size = len(cookie_header(sign_in(client)).split(";", 1)[0])
    assert size < COOKIE_SIZE_LINE_BYTES and log.events("cookie_large") == []


def test_no_line_holds_the_cookie_or_the_key(client, clock, log):
    value = cookie_value(sign_in(client))
    clock.advance(2 * DAY)
    client.get("/api/test-who")
    client.get("/api/nothing")
    text = json.dumps(log.lines)
    assert value not in text and KEY not in text
    assert not re.search(r"penguinslicer=", text)
