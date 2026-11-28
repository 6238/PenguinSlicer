"""No secret in any log line or answer (README-details.md, "The log", its tests; the guide's
"How it is tested").

The search itself runs after every test of the fast suite (tests/conftest.py,
tests/secret_watch.py). These tests show that it finds a secret where one is written, in each
place it watches, and that it does not take the cookie, which an answer carries by design in
`Set-Cookie`, as a leak."""

import io
import json

import pytest

import secret_watch
from front_helpers import DEV_GROUP, KEY, Lines, front, sign_in
from penguin_front.buckets import FolderBucket
from penguin_front.cookie import COOKIE_NAME, CookieKey
from penguin_front.log import Log


@pytest.fixture
def watch():
    """The watch of this test, emptied after it: these tests write secrets on purpose."""
    found = secret_watch.current
    yield found
    found.texts.clear()


def test_a_cookie_key_given_to_the_front_server_is_watched(tmp_path, clock, watch):
    front(tmp_path, clock)
    assert KEY in watch.secrets


def test_a_cookie_key_made_at_start_is_watched_in_each_form_it_could_be_written(watch):
    CookieKey(bytes(range(32)))
    assert bytes(range(32)).hex() in watch.secrets
    assert "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8" in watch.secrets


def test_a_key_line_in_the_log_is_found(tmp_path, clock, watch):
    log = Log(clock, io.StringIO(), FolderBucket(tmp_path / "log", clock))
    CookieKey(KEY)
    log.write("leak", detail=f"the key is {KEY}")
    assert watch.leaks() == [("the log", KEY[:6] + "…")]


def test_a_sealed_cookie_in_a_gathered_line_is_found(tmp_path, clock, watch):
    log = Log(clock, io.StringIO(), FolderBucket(tmp_path / "log", clock))
    cookie = CookieKey(KEY).seal_fields({"a": 1})
    log.gather([{"component": "slice", "event": "leak", "detail": cookie}])
    assert ("the log's gathered lines", cookie[:6] + "…") in watch.leaks()


def test_a_secret_in_a_tests_stand_in_for_the_log_is_found(watch):
    watch.secret("a-token-only-this-test-uses")
    Lines().write("leak", token="a-token-only-this-test-uses")
    assert watch.leaks()


def test_a_secret_in_an_answer_is_found_and_the_cookie_in_set_cookie_is_not(tmp_path, clock,
                                                                           watch):
    app = front(tmp_path, clock)

    @app.get("/api/test-leak")
    def leak():
        return {"key": KEY}

    client = app.test_client()
    sign_in(client)
    assert client.get_cookie(COOKIE_NAME).value in watch.secrets
    assert watch.leaks() == []
    client.get("/api/test-leak", headers=DEV_GROUP)
    assert watch.leaks() == [("the answer to GET /api/test-leak", KEY[:6] + "…")]


def test_a_token_the_stand_in_for_onshape_issues_is_watched(watch):
    import httpx

    from onshape_standin import OnshapeStandIn

    onshape = OnshapeStandIn()
    url = onshape.start()
    try:
        approval = httpx.get(f"{url}/oauth/authorize", params={
            "response_type": "code", "client_id": "c", "redirect_uri": "http://127.0.0.1/cb",
            "state": "s"}, follow_redirects=False)
        code = approval.headers["Location"].split("code=")[1].split("&")[0]
        tokens = httpx.post(f"{url}/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": "http://127.0.0.1/cb"}).json()
    finally:
        onshape.stop()
    assert tokens["access_token"] in watch.secrets and tokens["refresh_token"] in watch.secrets


def test_a_short_value_is_not_searched_for(watch):
    watch.secret("abc")
    watch.text("somewhere", json.dumps({"x": "abc"}))
    assert watch.leaks() == []
