"""The configuration: the built-in default, reading, the default served in place of an
invalid document with its log line, and the conditional write (README-details.md, "The
configuration"; contracts/configuration.md; contracts/wizard-front-server.md, "`GET` and
`PUT /api/configuration`")."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from front_helpers import KEY, Lines, front, sign_in
from penguin_front.cookie import COOKIE_NAME, CookieKey, Identity

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "examples"
PACKAGE = Path(__file__).resolve().parents[1] / "src" / "penguin_front"
DEFAULT = json.loads((EXAMPLES / "configuration-default.json").read_text())
HAND_WRITTEN = json.loads((EXAMPLES / "configuration-hand-written.json").read_text())
WRITE_REQUEST = json.loads((EXAMPLES / "wizard-front" / "configuration-write-request.json")
                           .read_text())
WRITTEN = json.loads((EXAMPLES / "wizard-front" / "configuration-written.json").read_text())
GROUP = {"X-PenguinSlicer-Group": "dev-group"}


@pytest.fixture
def log():
    return Lines()


@pytest.fixture
def app(tmp_path, clock, log):
    return front(tmp_path, clock, log)


@pytest.fixture
def client(app):
    client = app.test_client()
    sign_in(client)
    return client


@pytest.fixture
def saved(tmp_path):
    """The development group's saved document: write it as given (bytes, or JSON of an
    object) and give its path."""
    path = tmp_path / "state" / "config" / "dev-group.json"

    def place(document):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(document if isinstance(document, bytes)
                         else json.dumps(document).encode())
        return path

    return place


def read(client, **headers):
    return client.get("/api/configuration", headers={**GROUP, **headers})


def write(client, based_on, configuration, **extra):
    return client.put("/api/configuration", headers=GROUP,
                      json={"based_on": based_on, "configuration": configuration, **extra})


# The built-in default.

def test_the_front_servers_copy_of_the_default_is_the_contracts_file():
    assert (PACKAGE / "default_configuration.json").read_bytes() == \
        (EXAMPLES / "configuration-default.json").read_bytes()


def test_a_group_with_no_document_gets_the_default(client):
    answer = read(client)
    assert answer.status_code == 200 and answer.headers["Cache-Control"] == "no-store"
    assert answer.get_json() == {"configuration": DEFAULT, "source": "default",
                                 "name": "PenguinSlicer default", "revision": None}


def test_the_default_is_valid_by_the_front_servers_own_rules(client):
    answer = write(client, None, DEFAULT)
    assert answer.status_code == 200


# Reading.

def test_a_groups_valid_document_is_answered_with_its_name_and_revision(client, saved):
    path = saved(HAND_WRITTEN)
    answer = read(client).get_json()
    assert answer == {"configuration": HAND_WRITTEN, "source": "group",
                      "name": "Development Group",
                      "revision": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_the_group_may_be_named_in_the_query_of_the_get(client, saved):
    saved(HAND_WRITTEN)
    answer = client.get("/api/configuration", query_string={"group": "dev-group"})
    assert answer.get_json()["source"] == "group"


def test_a_read_for_a_group_the_cookie_does_not_list_is_refused(client, log):
    answer = client.get("/api/configuration",
                        headers={"X-PenguinSlicer-Group": "61a9c0d2e4b7f80012345678"})
    assert answer.status_code == 403
    assert answer.get_json()["code"] == "front.group_not_allowed"
    assert log.events("refused")


def test_a_read_without_a_sign_in_is_refused(app):
    answer = app.test_client().get("/api/configuration", headers=GROUP)
    assert answer.get_json()["code"] == "front.not_signed_in"


def test_each_group_reads_its_own_document(app, clock, tmp_path):
    other = tmp_path / "state" / "config" / "61a9c0d2e4b7f80012345678.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps(HAND_WRITTEN))
    client = app.test_client()
    client.set_cookie(COOKIE_NAME, CookieKey(KEY).seal(Identity(
        "u1", "Alex Chen", (("61a9c0d2e4b7f80012345678", "6238 (Popcorn Penguins)"),
                            ("6202bb11c0ffee0098765432", "FRC 1678")), None,
        int(clock.now()))))
    first = client.get("/api/configuration",
                       headers={"X-PenguinSlicer-Group": "61a9c0d2e4b7f80012345678"})
    second = client.get("/api/configuration",
                        headers={"X-PenguinSlicer-Group": "6202bb11c0ffee0098765432"})
    assert first.get_json()["name"] == "6238 (Popcorn Penguins)"
    assert first.get_json()["source"] == "group" and second.get_json()["source"] == "default"


def test_a_state_bucket_that_cannot_be_read_is_a_quiet_retry(tmp_path, clock):
    (tmp_path / "blocked").write_bytes(b"")
    app = front(tmp_path, clock, PENGUIN_STATE_DIR=str(tmp_path / "blocked"))
    client = app.test_client()
    sign_in(client)
    for answer in (read(client), write(client, None, DEFAULT)):
        assert answer.status_code == 503
        report = answer.get_json()
        assert report["code"] == "front.state_bucket_unreachable"
        assert report["retryable"] is True


# An invalid saved document: the default in its place, the file untouched, one line.

def changed(change):
    document = copy.deepcopy(HAND_WRITTEN)
    change(document)
    return document


def dropping(*keys):
    def change(document):
        target = document
        for key in keys[:-1]:
            target = target[key]
        del target[keys[-1]]
    return change


def setting(value, *keys):
    def change(document):
        target = document
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
    return change


P0 = ("filaments", 0, "profiles", 0)
INVALID = [
    # 1: too large, not JSON, not a JSON object.
    (1, "", b'{"format": 1, "note": "' + b"x" * 262_144 + b'"}'),
    (1, "", b"{not json"),
    (1, "", b"\xff\xfe\x00"),
    (1, "", b"[1, 2]"),
    (1, "", b""),
    # 2: the format.
    (2, "format", changed(dropping("format"))),
    (2, "format", changed(setting(2, "format"))),
    (2, "format", changed(setting(0, "format"))),
    (2, "format", changed(setting("1", "format"))),
    (2, "format", changed(setting(True, "format"))),
    (2, "format", changed(setting(1.0, "format"))),
    # 3: a field missing or not listed, in the document, a filament or a profile.
    (3, "printer", changed(dropping("printer"))),
    (3, "upload_units", changed(dropping("upload_units"))),
    (3, "filaments", changed(dropping("filaments"))),
    (3, "colour", changed(setting("#ffffff", "colour"))),
    (3, "filaments[1].colour", changed(dropping("filaments", 1, "colour"))),
    (3, "filaments[2].color", changed(setting("#ffffff", "filaments", 2, "color"))),
    (3, "filaments[0].profiles[1].purpose", changed(dropping("filaments", 0, "profiles", 1,
                                                             "purpose"))),
    (3, "filaments[0].profiles[0].process", changed(dropping(*P0, "process"))),
    (3, "filaments[0].profiles", changed(dropping("filaments", 0, "profiles"))),
    (3, "filaments[1].name", changed(dropping("filaments", 1, "name"))),
    (3, "filaments[0].profiles[0].name", changed(dropping(*P0, "name"))),
    (3, "filaments[0].profiles[0].purpose", changed(dropping(*P0, "purpose"))),
    (3, "filaments[0].profiles[0].printer", changed(dropping(*P0, "printer"))),
    (3, "filaments[0].profiles[0].overide", changed(setting({}, *P0, "overide"))),
    # 4: a wrong type, or a row's rule broken.
    (4, "printer", changed(setting(5, "printer"))),
    (4, "upload_units", changed(setting("cm", "upload_units"))),
    (4, "note", changed(setting("n" * 2001, "note"))),
    (4, "note", changed(setting(None, "note"))),
    (4, "filaments", changed(setting([], "filaments"))),
    (4, "filaments", changed(setting({}, "filaments"))),
    (4, "filaments", changed(lambda d: d["filaments"].extend(
        [dict(d["filaments"][0], name=f"F{n}") for n in range(18)]))),
    (4, "filaments[1]", changed(setting("PETG", "filaments", 1))),
    (4, "filaments[0].name", changed(setting("", "filaments", 0, "name"))),
    (4, "filaments[0].name", changed(setting("n" * 41, "filaments", 0, "name"))),
    (4, "filaments[0].name", changed(setting(["Black PETG"], "filaments", 0, "name"))),
    (4, "filaments[0].name", changed(setting({"a": 1}, "filaments", 0, "name"))),
    (4, "filaments[0].profiles[0].name", changed(setting(["x"], *P0, "name"))),
    (4, "filaments[0].profiles[0].name", changed(setting(5, *P0, "name"))),
    (4, "filaments[1].name", changed(setting("Black PETG", "filaments", 1, "name"))),
    (4, "filaments[0].colour", changed(setting("202020", "filaments", 0, "colour"))),
    (4, "filaments[0].colour", changed(setting("#20202", "filaments", 0, "colour"))),
    (4, "filaments[0].colour", changed(setting("#2020202", "filaments", 0, "colour"))),
    (4, "filaments[0].colour", changed(setting("#gggggg", "filaments", 0, "colour"))),
    (4, "filaments[0].colour", changed(setting("#202020\n", "filaments", 0, "colour"))),
    (4, "filaments[1].note", changed(setting(7, "filaments", 1, "note"))),
    (4, "filaments[0].profiles", changed(setting([], "filaments", 0, "profiles"))),
    (4, "filaments[0].profiles", changed(lambda d: d["filaments"][0]["profiles"].extend(
        [dict(d["filaments"][0]["profiles"][0], name=f"P{n}") for n in range(19)]))),
    (4, "filaments[0].profiles[0]", changed(setting(["x"], *P0))),
    (4, "filaments[0].profiles[1].name", changed(setting("Structural", "filaments", 0,
                                                         "profiles", 1, "name"))),
    (4, "filaments[0].profiles[0].name", changed(setting("", *P0, "name"))),
    (4, "filaments[0].profiles[0].purpose", changed(setting("p" * 121, *P0, "purpose"))),
    (4, "filaments[0].profiles[0].purpose", changed(setting("", *P0, "purpose"))),
    (4, "filaments[0].profiles[0].filament", changed(setting(None, *P0, "filament"))),
    (4, "filaments[0].profiles[0].process", changed(setting(["a"], *P0, "process"))),
    (4, "filaments[0].profiles[0].printer", changed(setting(1, *P0, "printer"))),
    (4, "filaments[0].profiles[0].overrides", changed(setting(["4"], *P0, "overrides"))),
    (4, "filaments[0].profiles[0].note", changed(setting(False, *P0, "note"))),
    # 5: a profile's printer not the document's.
    (5, "filaments[2].profiles[0].printer",
     changed(setting("Bambu Lab X1 Carbon 0.4 nozzle", "filaments", 2, "profiles", 0,
                     "printer"))),
    # 6: an override's value not a string, or its name not 1 to 100 characters.
    (6, "filaments[0].profiles[0].overrides.wall_loops",
     changed(setting(4, *P0, "overrides", "wall_loops"))),
    (6, "filaments[0].profiles[0].overrides.wall_loops",
     changed(setting(None, *P0, "overrides", "wall_loops"))),
    (6, "filaments[0].profiles[0].overrides.",
     changed(setting("1", *P0, "overrides", ""))),
    (6, "filaments[0].profiles[0].overrides." + "k" * 101,
     changed(setting("1", *P0, "overrides", "k" * 101))),
]


def case_id(case):
    return f"rule{case[0]}-{case[1] or 'document'}"


@pytest.mark.parametrize("rule, where, document", INVALID, ids=[case_id(c) for c in INVALID])
def test_an_invalid_saved_document_is_answered_as_the_default_left_untouched_and_logged(
        client, saved, log, rule, where, document):
    path = saved(document)
    before, stamp = path.read_bytes(), path.stat().st_mtime_ns
    answer = read(client)
    assert answer.status_code == 200
    body = answer.get_json()
    assert body["configuration"] == DEFAULT and body["source"] == "default"
    assert body["name"] == "PenguinSlicer default"
    assert body["revision"] == hashlib.sha256(before).hexdigest()
    assert path.read_bytes() == before and path.stat().st_mtime_ns == stamp
    [line] = log.events("configuration_invalid")
    assert (line["group"], line["rule"], line["path"]) == ("dev-group", rule, where)
    assert line["why"] and line["revision"] == body["revision"]
    assert log.events("error") == []


def as_json(document):
    """The document as a value a write can carry, or None for bytes that are not JSON (a
    body that is not JSON is `front.bad_request`, tested below)."""
    if not isinstance(document, bytes):
        return document
    try:
        return json.loads(document)
    except ValueError:
        return None


#: The invalid documents a write can carry.
WRITABLE = [(rule, where, as_json(document)) for rule, where, document in INVALID
            if as_json(document) is not None]


@pytest.mark.parametrize("rule, where, document", WRITABLE, ids=[case_id(c) for c in WRITABLE])
def test_a_write_of_an_invalid_document_is_refused_naming_the_rule_and_nothing_is_written(
        client, tmp_path, rule, where, document):
    answer = write(client, None, document)
    assert answer.status_code == 422
    report = answer.get_json()
    assert report["code"] == "front.configuration_invalid" and report["retryable"] is False
    assert report["message"].startswith("The configuration was not saved, because ")
    assert f"rule {rule}" in report["detail"] and where in report["detail"]
    assert not (tmp_path / "state" / "config" / "dev-group.json").exists()


def test_the_first_rule_broken_is_the_one_named(client, saved, log):
    document = changed(setting("cm", "upload_units"))
    document["extra"] = 1                       # rule 3, after rule 4 in the document
    document["filaments"][0]["profiles"][0]["overrides"]["wall_loops"] = 4   # rule 6
    saved(document)
    read(client)
    assert log.events("configuration_invalid")[0]["rule"] == 3


def test_a_mistake_found_first_in_the_document_is_named_among_one_rule(client, saved, log):
    document = changed(setting("", "filaments", 2, "name"))
    document["filaments"][1]["colour"] = "red"
    saved(document)
    read(client)
    assert log.events("configuration_invalid")[0]["path"] == "filaments[1].colour"


def test_the_hand_written_example_and_its_notes_are_valid(client, saved):
    saved(HAND_WRITTEN)
    assert read(client).get_json()["source"] == "group"


def test_names_are_compared_exactly_so_names_differing_by_case_are_two(client, saved):
    saved(changed(setting("black petg", "filaments", 1, "name")))
    assert read(client).get_json()["source"] == "group"


def test_a_document_of_exactly_256_kb_is_read(client, saved, log):
    document = copy.deepcopy(HAND_WRITTEN)
    document["note"] = ""
    text = json.dumps(document).encode()
    document["note"] = "n" * (262_144 - len(text))
    path = saved(document)
    assert path.stat().st_size == 262_144
    # Read, and found to break rule 4 (a note over 2,000 characters), not rule 1.
    assert read(client).get_json()["source"] == "default"
    assert log.events("configuration_invalid")[0]["rule"] == 4


# Writing.

def revision_of(client):
    return read(client).get_json()["revision"]


def test_a_write_based_on_null_creates_the_document_and_answers_its_revision(client, tmp_path):
    answer = write(client, None, HAND_WRITTEN)
    assert answer.status_code == 200 and answer.headers["Cache-Control"] == "no-store"
    body = answer.get_json()
    assert set(body) == set(WRITTEN) and body["source"] == "group"
    assert body["name"] == "Development Group"
    stored = (tmp_path / "state" / "config" / "dev-group.json").read_bytes()
    assert body["revision"] == hashlib.sha256(stored).hexdigest()
    assert json.loads(stored) == HAND_WRITTEN
    assert read(client).get_json() == {"configuration": HAND_WRITTEN, "source": "group",
                                       "name": "Development Group",
                                       "revision": body["revision"]}


def test_the_contracts_example_request_is_written(client):
    answer = write(client, None, WRITE_REQUEST["configuration"])
    assert answer.status_code == 200


def test_a_second_write_based_on_null_is_front_configuration_changed(client):
    assert write(client, None, HAND_WRITTEN).status_code == 200
    answer = write(client, None, DEFAULT)
    assert answer.status_code == 409
    assert answer.get_json()["code"] == "front.configuration_changed"
    assert read(client).get_json()["configuration"] == HAND_WRITTEN


def test_of_two_writes_based_on_one_revision_the_first_is_written_and_the_second_refused(
        client):
    write(client, None, HAND_WRITTEN)
    revision = revision_of(client)
    first = changed(setting("mm", "upload_units"))
    second = changed(setting("Draft only", "note"))
    assert write(client, revision, first).status_code == 200
    answer = write(client, revision, second)
    assert answer.status_code == 409
    assert answer.get_json()["code"] == "front.configuration_changed"
    assert read(client).get_json()["configuration"] == first


def test_a_write_repeated_after_its_first_attempt_was_written_answers_200(client):
    write(client, None, HAND_WRITTEN)
    revision = revision_of(client)
    document = changed(setting("mm", "upload_units"))
    first = write(client, revision, document)
    again = write(client, revision, document)
    assert again.status_code == 200 and again.get_json() == first.get_json()


def test_a_create_repeated_after_its_first_attempt_was_written_answers_200(client, log):
    first = write(client, None, HAND_WRITTEN)
    again = write(client, None, HAND_WRITTEN)
    assert again.status_code == 200 and again.get_json() == first.get_json()
    assert len(log.events("configuration_edited")) == 1


def test_a_write_based_on_a_revision_of_a_document_now_gone_is_refused(client):
    answer = write(client, "0" * 64, HAND_WRITTEN)
    assert answer.status_code == 409


def test_a_write_may_replace_an_invalid_saved_document(client, saved):
    saved(b"{not json")
    revision = revision_of(client)
    assert write(client, revision, HAND_WRITTEN).status_code == 200
    assert read(client).get_json()["source"] == "group"


def test_an_edit_writes_a_line_with_the_users_name_and_the_fields_that_changed(client, log):
    write(client, None, HAND_WRITTEN)
    [created] = log.events("configuration_edited")
    assert created["user_name"] == "Development User" and created["group"] == "dev-group"
    assert {"path": "upload_units", "old": None, "new": "in"} in created["changes"]
    document = changed(setting("mm", "upload_units"))
    document["filaments"][0]["profiles"][0]["overrides"]["wall_loops"] = "5"
    del document["note"]
    write(client, revision_of(client), document)
    edited = log.events("configuration_edited")[-1]
    assert edited["user_key"] == "dev-user" and edited["revision"]
    assert sorted(edited["changes"], key=lambda c: c["path"]) == [
        {"path": "filaments[0].profiles[0].overrides.wall_loops", "old": "4", "new": "5"},
        {"path": "note", "old": HAND_WRITTEN["note"], "new": None},
        {"path": "upload_units", "old": "in", "new": "mm"},
    ]


def test_an_edit_of_an_unreadable_document_lists_every_field_as_new(client, saved, log):
    saved(b"{not json")
    write(client, revision_of(client), DEFAULT)
    changes = log.events("configuration_edited")[0]["changes"]
    assert {"path": "printer", "old": None, "new": DEFAULT["printer"]} in changes


def test_an_edit_that_changes_nothing_writes_a_line_with_no_changes(client, log):
    write(client, None, HAND_WRITTEN)
    write(client, revision_of(client), HAND_WRITTEN)
    assert log.events("configuration_edited")[-1]["changes"] == []


def test_lists_that_change_length_are_listed_by_element(client, log):
    write(client, None, HAND_WRITTEN)
    document = copy.deepcopy(HAND_WRITTEN)
    document["filaments"].pop()
    document["filaments"][0]["profiles"][0]["overrides"] = {}
    write(client, revision_of(client), document)
    paths = {c["path"] for c in log.events("configuration_edited")[-1]["changes"]}
    assert "filaments[2].name" in paths
    assert "filaments[0].profiles[0].overrides" in paths


@pytest.mark.parametrize("body", [
    [], {"configuration": DEFAULT}, {"based_on": None}, {"based_on": 5, "configuration": DEFAULT},
    {"based_on": "", "configuration": DEFAULT},
])
def test_a_write_of_the_wrong_form_is_front_bad_request(client, body):
    answer = client.put("/api/configuration", headers=GROUP, json=body)
    assert answer.status_code == 400 and answer.get_json()["code"] == "front.bad_request"


def test_a_write_whose_body_is_not_json_is_front_bad_request(client):
    answer = client.put("/api/configuration", headers=GROUP, data=b"{not json")
    assert answer.get_json()["code"] == "front.bad_request"


def test_a_write_for_a_group_the_cookie_does_not_list_is_refused(client, tmp_path):
    answer = client.put("/api/configuration",
                        headers={"X-PenguinSlicer-Group": "61a9c0d2e4b7f80012345678"},
                        json={"based_on": None, "configuration": DEFAULT})
    assert answer.get_json()["code"] == "front.group_not_allowed"
    assert not (tmp_path / "state" / "config").exists()


def test_a_write_carries_the_format_number(client, tmp_path):
    write(client, None, HAND_WRITTEN)
    stored = json.loads((tmp_path / "state" / "config" / "dev-group.json").read_bytes())
    assert stored["format"] == 1


def test_a_written_document_larger_than_256_kb_is_refused_by_rule_1(client):
    document = copy.deepcopy(HAND_WRITTEN)
    document["filaments"][0]["profiles"][0]["overrides"] = {
        f"setting_{n:05d}": "v" * 90 for n in range(3000)}
    answer = write(client, None, document)
    assert answer.status_code == 422 and "rule 1" in answer.get_json()["detail"]
