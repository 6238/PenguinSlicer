"""The stand-in for Onshape answers as Onshape's OAuth and its user and company calls do, and
counts the calls it receives (README-details.md, "The fast suite"). No test calls Onshape:
the guards of conftest.py refuse any address beyond loopback."""

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from onshape_standin import OnshapeStandIn

REDIRECT = "http://127.0.0.1:1/signin/callback"


@pytest.fixture
def onshape():
    s = OnshapeStandIn()
    s.start()
    yield s
    s.stop()


@pytest.fixture
def http(onshape):
    with httpx.Client(base_url=onshape.url, timeout=10) as client:
        yield client


def approve(http, state="st4te"):
    answer = http.get("/oauth/authorize", params={
        "response_type": "code", "client_id": "test-client", "redirect_uri": REDIRECT,
        "state": state})
    assert answer.status_code == 302
    location = urlsplit(answer.headers["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT
    return {k: v[0] for k, v in parse_qs(location.query).items()}


def exchange(http, code):
    return http.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "client_id": "test-client",
        "client_secret": "test-secret", "redirect_uri": REDIRECT})


def test_a_whole_sign_in_counts_two_calls(onshape, http):
    returned = approve(http)
    assert returned["state"] == "st4te"
    tokens = exchange(http, returned["code"]).json()
    assert tokens["token_type"] == "Bearer" and tokens["expires_in"] == 3600
    bearer = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert http.get("/api/users/sessioninfo", headers=bearer).json() == onshape.user
    assert http.get("/api/companies", headers=bearer).json() == {"items": onshape.companies}
    assert onshape.calls == [("GET", "/api/users/sessioninfo"), ("GET", "/api/companies")]


def test_a_user_who_refuses_is_sent_back_with_access_denied(onshape, http):
    onshape.refuse_approval = True
    returned = approve(http)
    assert returned == {"error": "access_denied", "state": "st4te"}


def test_a_code_is_spent_once_and_a_made_up_code_is_refused(http):
    code = approve(http)["code"]
    assert exchange(http, code).status_code == 200
    for spent in (code, "made-up"):
        refused = exchange(http, spent)
        assert refused.status_code == 400 and refused.json()["error"] == "invalid_grant"


def test_a_refused_code_and_a_bad_token(onshape, http):
    onshape.refuse_codes = True
    assert exchange(http, approve(http)["code"]).status_code == 400
    answer = http.get("/api/users/sessioninfo", headers={"Authorization": "Bearer nonsense"})
    assert answer.status_code == 401
    assert http.get("/api/companies").status_code == 401


def test_a_refresh_gives_new_tokens(http):
    tokens = exchange(http, approve(http)["code"]).json()
    renewed = http.post("/oauth/token", data={"grant_type": "refresh_token",
                                              "refresh_token": tokens["refresh_token"]})
    assert renewed.status_code == 200
    assert renewed.json()["access_token"] != tokens["access_token"]
    assert http.post("/oauth/token", data={"grant_type": "refresh_token",
                                           "refresh_token": "nonsense"}).status_code == 400


def test_an_account_with_no_company_gets_an_empty_list(onshape, http):
    onshape.companies = []
    tokens = exchange(http, approve(http)["code"]).json()
    bearer = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert http.get("/api/companies", headers=bearer).json() == {"items": []}


def test_an_unreachable_onshape_refuses_connections(onshape, http):
    onshape.unreachable()
    with pytest.raises(httpx.ConnectError):
        http.get("/oauth/authorize")
    onshape.reachable()
    assert http.get("/api/companies").status_code == 401
