"""The current group's check and `GET /api/me` (README-details.md, "Groups and the current
group"; contracts/wizard-front-server.md, "The current group" and "`GET /api/me`")."""

import json
import re
from pathlib import Path

import pytest

from front_helpers import KEY, Lines, front, sign_in
from onshape_standin import OnshapeStandIn
from penguin_front.cookie import COOKIE_NAME, CookieKey, Identity
from penguin_front.identity import acts_for_group, current_group, signed_in
from test_rules import BUILT, offered

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "wizard-front"
#: The requests that act for a group (README-details.md, "Groups and the current group"),
#: as the application names them; those of this list the front server offers are checked.
ACTS_FOR_GROUP = {
    ("GET", "/api/configuration"), ("PUT", "/api/configuration"), ("POST", "/api/parts"),
    ("POST", "/api/slices"), ("GET", "/api/slices/<slice>"),
    ("GET", "/api/slices/<slice>/events"), ("GET", "/api/slices/<slice>/summary"),
    ("GET", "/api/slices/<slice>/file"),
}
EXAMPLE_ME = json.loads((EXAMPLES / "me.json").read_text())


def identity_of(answer, used_at):
    """The `Identity` an answer of `/api/me`'s form describes."""
    return Identity(answer["user"]["id"], answer["user"]["name"],
                    tuple((g["id"], g["name"]) for g in answer["groups"]), None, int(used_at))


def planted(app):
    @app.route("/api/test-group", methods=["GET", "POST"])
    @acts_for_group
    def for_group():
        return {"group": current_group(signed_in())}

    return app


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def app(tmp_path, clock, log):
    return planted(front(tmp_path, clock, log))


@pytest.fixture
def client(app, clock):
    """Signed in as the contract's example user, in its two groups."""
    client = app.test_client()
    client.set_cookie(COOKIE_NAME, CookieKey(KEY).seal(identity_of(EXAMPLE_ME, clock.now())))
    return client


FIRST, SECOND = (g["id"] for g in EXAMPLE_ME["groups"])


# GET /api/me.

def test_me_answers_the_cookies_user_and_groups_in_order_as_the_contracts_example(client):
    onshape = OnshapeStandIn()
    onshape.start()
    try:
        answer = client.get("/api/me")
    finally:
        onshape.stop()
    assert answer.status_code == 200 and answer.mimetype == "application/json"
    assert answer.get_json() == EXAMPLE_ME
    assert onshape.calls == []


def test_me_keeps_the_cookies_order_of_groups(app, clock):
    reordered = dict(EXAMPLE_ME, groups=list(reversed(EXAMPLE_ME["groups"])))
    client = app.test_client()
    client.set_cookie(COOKIE_NAME, CookieKey(KEY).seal(identity_of(reordered, clock.now())))
    assert client.get("/api/me").get_json()["groups"] == reordered["groups"]


def test_me_with_the_development_identity_answers_the_four_values_of_the_table(app):
    client = app.test_client()
    sign_in(client)
    assert client.get("/api/me").get_json() == {
        "user": {"id": "dev-user", "name": "Development User"},
        "groups": [{"id": "dev-group", "name": "Development Group"}]}


def test_me_without_a_cookie_is_front_not_signed_in(app):
    answer = app.test_client().get("/api/me")
    assert answer.status_code == 401 and answer.get_json()["code"] == "front.not_signed_in"


# The check of the current group.

def test_a_group_the_cookie_lists_is_accepted_in_the_header(client):
    for group in (FIRST, SECOND):
        answer = client.post("/api/test-group", headers={"X-PenguinSlicer-Group": group})
        assert answer.status_code == 200 and answer.get_json() == {"group": group}


def test_a_get_with_the_group_in_the_query_alone_is_accepted(client):
    answer = client.get("/api/test-group", query_string={"group": SECOND})
    assert answer.get_json() == {"group": SECOND}


def test_a_get_with_header_and_query_equal_is_accepted(client):
    answer = client.get("/api/test-group", query_string={"group": FIRST},
                        headers={"X-PenguinSlicer-Group": FIRST})
    assert answer.status_code == 200


def refused(answer, log, why):
    assert answer.status_code == 403
    report = answer.get_json()
    assert report["code"] == "front.group_not_allowed" and report["retryable"] is False
    [line] = log.events("refused")
    assert line["reason"] == "group_not_allowed" and line["why"] == why
    assert line["user_key"] == EXAMPLE_ME["user"]["id"]
    error = log.events("error")[-1]
    assert error["code"] == "front.group_not_allowed"
    assert error["user_key"] == EXAMPLE_ME["user"]["id"]
    return line


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_a_group_the_cookie_does_not_list_is_refused(client, log, method):
    answer = client.open("/api/test-group", method=method,
                         headers={"X-PenguinSlicer-Group": "dev-group"})
    line = refused(answer, log, "a group the cookie does not list")
    assert line["header"] == "dev-group"


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_no_group_named_is_refused(client, log, method):
    refused(client.open("/api/test-group", method=method), log, "no group named")


def test_an_empty_group_is_refused(client, log):
    refused(client.post("/api/test-group", headers={"X-PenguinSlicer-Group": ""}), log,
            "no group named")


def test_header_and_query_that_differ_are_refused(client, log):
    answer = client.get("/api/test-group", query_string={"group": SECOND},
                        headers={"X-PenguinSlicer-Group": FIRST})
    line = refused(answer, log, "the header and the query name different groups")
    assert (line["header"], line["query"]) == (FIRST, SECOND)


def test_a_get_naming_two_different_groups_in_the_query_is_refused(client, log):
    answer = client.get(f"/api/test-group?group={FIRST}&group={SECOND}")
    line = refused(answer, log, "the query names more than one group")
    assert line["query"] == FIRST


def test_a_get_naming_one_group_twice_in_the_query_is_accepted(client):
    answer = client.get(f"/api/test-group?group={FIRST}&group={FIRST}")
    assert answer.get_json() == {"group": FIRST}


def test_the_refusal_line_and_the_error_line_carry_the_same_path_as_sent(client, log):
    answer = client.post("/api/test-%67roup", headers={"X-PenguinSlicer-Group": "dev-group"})
    line = refused(answer, log, "a group the cookie does not list")
    assert line["path"] == log.events("error")[-1]["path"] == "/api/test-%67roup"


def test_a_changing_request_with_the_group_in_the_query_alone_is_refused(client, log):
    refused(client.post("/api/test-group", query_string={"group": FIRST}), log,
            "no group named")


def test_a_group_named_by_case_or_spaces_unlike_the_cookie_is_refused(client, log):
    refused(client.post("/api/test-group", headers={"X-PenguinSlicer-Group": FIRST.upper()}),
            log, "a group the cookie does not list")


def test_a_long_group_is_cut_in_the_refusal_line(client, log):
    answer = client.post("/api/test-group", headers={"X-PenguinSlicer-Group": "g" * 5000})
    assert len(refused(answer, log, "a group the cookie does not list")["header"]) == 200


def test_the_check_needs_a_sign_in_first(app):
    answer = app.test_client().post("/api/test-group", headers={"X-PenguinSlicer-Group": FIRST})
    assert answer.get_json()["code"] == "front.not_signed_in"


def test_an_error_line_after_the_check_carries_the_group(app, client, log):
    @app.get("/api/test-group-then-refuse")
    def group_then_refuse():
        from penguin_front.errors import FrontError

        current_group(signed_in())
        raise FrontError("front.bad_request", "a refusal planted by the test")

    client.get("/api/test-group-then-refuse", headers={"X-PenguinSlicer-Group": SECOND})
    assert log.events("error")[-1]["group"] == SECOND


def test_no_request_reads_the_groups_again_however_old_the_cookie(client, clock):
    onshape = OnshapeStandIn()
    onshape.start()
    try:
        for _ in range(3):
            clock.advance(29 * 86_400)
            client.get("/api/me")
            client.post("/api/test-group", headers={"X-PenguinSlicer-Group": "dev-group"})
    finally:
        onshape.stop()
    assert onshape.calls == []


# Every request that acts for a group, found from the application.

def marked(app):
    return {(method, rule.rule) for rule in app.url_map.iter_rules()
            for method in rule.methods - {"HEAD", "OPTIONS"}
            if getattr(app.view_functions[rule.endpoint], "penguin_acts_for_group", False)
            and not rule.rule.startswith("/api/test-")}


def test_the_requests_marked_as_acting_for_a_group_are_the_details_files_built_so_far(
        tmp_path, clock):
    app = front(tmp_path, clock)
    assert marked(app) == ACTS_FOR_GROUP & BUILT
    assert marked(app) <= offered(app)


#: Each way of naming the group: the header, the query, and whether a `GET` and a changing
#: request are accepted (a changing request reads the header alone).
NAMINGS = [
    (FIRST, None, True, True),
    ("dev-group", None, False, False),
    (None, None, False, False),
    (FIRST, SECOND, False, True),
    (None, FIRST, True, False),
    (None, [FIRST, SECOND], False, False),
]


@pytest.mark.parametrize("header, query, get_accepted, change_accepted", NAMINGS)
def test_every_request_that_acts_for_a_group_checks_it(tmp_path, clock, header, query,
                                                       get_accepted, change_accepted):
    log = Lines()
    app = front(tmp_path, clock, log)
    client = app.test_client()
    client.set_cookie(COOKIE_NAME, CookieKey(KEY).seal(identity_of(EXAMPLE_ME, clock.now())))
    headers = {"X-PenguinSlicer-Group": header} if header else {}
    query_string = {"group": query} if query else None
    refusals = 0
    for method, rule in sorted(marked(app)):
        path = re.sub(r"<[^>]+>", "j1", rule)
        answer = client.open(path, method=method, headers=headers, json={},
                             query_string=query_string)
        code = (answer.get_json() or {}).get("code")
        accepted = get_accepted if method == "GET" else change_accepted
        if accepted:
            assert code != "front.group_not_allowed", (method, rule)
        else:
            assert code == "front.group_not_allowed", (method, rule)
            refusals += 1
    assert len(log.events("refused")) == refusals
