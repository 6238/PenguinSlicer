"""The log's gathering of the slice service's lines (README-details.md, "The log";
contracts/slice-http-interface.md, "`GET /log?after=<n>`").

The stand-in for the slice service holds the lines a test gives it (`log_line`) and answers
`GET /log` as the contract says. A gathering is run by the test (`gather_once`); the minute's
file is written by the test flushing the log. Nothing waits a number of seconds."""

import io
import json

import pytest

from front_fakes import BACKSTOP_S
from front_helpers import Lines, nobody_listens
from penguin_front import gathering
from penguin_front.buckets import FolderBucket
from penguin_front.gathering import Gatherer
from penguin_front.log import Log
from penguin_front.records import read_record, write_record
from penguin_front.slice_client import SliceClient
from sliced_helpers import Failing, write_submitted

USER, OTHER = "dev-user", "another-user"


class Followed:
    """The following, as the gathering asks it: the group noted beside each slice job it
    follows."""

    def __init__(self, groups=None):
        self.groups = groups or {}

    def group_of(self, user_key, job):
        if (user_key, job) in self.groups:
            return True, self.groups[(user_key, job)]
        return False, None


class Kept(Log):
    """The log, as built, on a folder; `gathered` is every line kept from another
    component, as written."""

    def __init__(self, clock, root):
        self.out = io.StringIO()
        super().__init__(clock, self.out, FolderBucket(root, clock))
        self.gathered = []

    def gather(self, lines):
        self.gathered.extend(json.loads(json.dumps(line)) for line in lines)
        super().gather(lines)

    def own(self, event):
        return [json.loads(text) for text in self.out.getvalue().splitlines()
                if json.loads(text)["event"] == event]


@pytest.fixture
def state(tmp_path, clock):
    return Failing(tmp_path / "state", clock)


@pytest.fixture
def log(tmp_path, clock):
    return Kept(clock, tmp_path / "log")


@pytest.fixture
def client(standin):
    client = SliceClient(standin.url)
    yield client
    client.close()


def gatherer(clock, client, state, log, followed=None):
    return Gatherer(clock=clock, slice_client=client, bucket=state,
                    follower=followed or Followed(), log=log)


def asked(standin):
    return [r.query for r in standin.requests if r.path == "/log"]


def test_the_lines_are_fetched_in_order_with_the_last_number_passed_back_none_twice(
        clock, client, state, log, standin):
    for n in range(3):
        standin.log_line("slice_job", state="queued", job=f"j{n}", user_key=USER)
    found = gatherer(clock, client, state, log)
    found.gather_once()
    standin.log_line("slice_job", state="running", job="j0", user_key=USER)
    found.gather_once()
    found.gather_once()
    assert asked(standin) == ["after=0", "after=3", "after=4"]
    assert [line["n"] for line in log.gathered] == [1, 2, 3, 4]
    assert all(line["component"] == "slice" for line in log.gathered)


def test_the_lines_gain_the_group_of_their_slice_job(clock, client, state, log, standin):
    write_submitted(state, "jrec", "2026-11-27T22:00:00Z", group="group-of-rec")
    write_submitted(state, "jrec", "2026-11-27T22:00:00Z", user=OTHER, group="other-group")
    followed = Followed({(USER, "jfol"): "group-of-fol"})
    standin.log_line("slice_job", state="queued", job="jrec", user_key=USER)
    standin.log_line("slice_job", state="queued", job="jfol", user_key=USER)
    standin.log_line("slice_job", state="queued", job="jrec", user_key=OTHER)
    standin.log_line("slice_job", state="queued", job="jnone", user_key=USER)
    standin.log_line("part_stored", user_key=USER, sha256="9f2c")
    standin.log_line("start", version="x", group="a group the slice service wrote")
    standin.log_line("slice_job", job="j/../../x", user_key=USER)
    standin.log_line("slice_job", job="jrec", user_key="a/b")
    gatherer(clock, client, state, log, followed).gather_once()
    groups = [line.get("group") for line in log.gathered]
    assert groups == ["group-of-rec", "group-of-fol", "other-group", None, None, None, None,
                      None]
    assert "group" not in log.gathered[5]


def test_a_group_found_once_is_not_read_again(clock, client, state, log, standin):
    write_submitted(state, "jrec", "2026-11-27T22:00:00Z", group="group-of-rec")
    found = gatherer(clock, client, state, log)
    standin.log_line("slice_job", state="queued", job="jrec", user_key=USER)
    found.gather_once()
    state.refuse_reads = True  # the cursor is read once, and the group is remembered
    standin.log_line("slice_job", state="running", job="jrec", user_key=USER)
    found.gather_once()
    assert [line["group"] for line in log.gathered] == ["group-of-rec"] * 2


def test_a_record_that_cannot_be_read_leaves_the_line_without_a_group(clock, client, state,
                                                                       log, standin):
    write_submitted(state, "jrec", "2026-11-27T22:00:00Z", group="group-of-rec")
    found = gatherer(clock, client, state, log)
    found.gather_once()  # the cursor read while the state bucket answers
    state.refuse_reads = True
    standin.log_line("slice_job", state="queued", job="jrec", user_key=USER)
    found.gather_once()
    state.refuse_reads = False
    standin.log_line("slice_job", state="running", job="jrec", user_key=USER)
    found.gather_once()
    assert [line.get("group") for line in log.gathered] == [None, "group-of-rec"]


def test_an_answer_with_more_is_followed_at_once(clock, client, state, log, standin):
    standin.log_page = 2
    for n in range(5):
        standin.log_line("slice_job", job=f"j{n}", user_key=USER)
    gatherer(clock, client, state, log).gather_once()
    assert asked(standin) == ["after=0", "after=2", "after=4"]
    assert [line["n"] for line in log.gathered] == [1, 2, 3, 4, 5]


def test_a_changed_process_starts_again_from_zero(clock, client, state, log, standin):
    for n in range(3):
        standin.log_line("slice_job", job=f"j{n}", user_key=USER)
    found = gatherer(clock, client, state, log)
    found.gather_once()
    first = standin.process
    standin.restart()
    standin.log_line("start", version="new")
    standin.log_line("slice_job", job="jnew", user_key=USER)
    found.gather_once()
    assert asked(standin) == ["after=0", "after=3", "after=0"]
    assert [line["event"] for line in log.gathered] == ["slice_job"] * 3 + \
        ["start", "slice_job"]
    [changed] = log.own("slice_log_process_changed")
    assert (changed["previous"], changed["process"], changed["after"]) == \
        (first, standin.process, 3)


def test_a_dropped_count_is_written_as_a_line(clock, client, state, log, standin):
    standin.log_capacity = 2
    for n in range(5):
        standin.log_line("slice_job", job=f"j{n}", user_key=USER)
    gatherer(clock, client, state, log).gather_once()
    [dropped] = log.own("slice_log_lines_dropped")
    assert (dropped["dropped"], dropped["after"], dropped["process"]) == \
        (3, 0, standin.process)
    assert [line["n"] for line in log.gathered] == [4, 5]


def test_a_restarted_front_server_goes_on_from_where_the_last_one_stopped(
        clock, client, state, log, standin):
    for n in range(3):
        standin.log_line("slice_job", job=f"j{n}", user_key=USER)
    gatherer(clock, client, state, log).gather_once()
    standin.log_line("slice_job", job="j3", user_key=USER)
    gatherer(clock, client, state, log).gather_once()
    assert asked(standin) == ["after=0", "after=3"]
    assert [line["n"] for line in log.gathered] == [1, 2, 3, 4]
    record, _ = read_record(state, gathering.CURSOR, gathering.CURSOR_KIND, Lines())
    assert record == {"format": 1, "process": standin.process, "after": 4}


def test_a_restarted_front_server_beside_a_new_slice_service_starts_from_zero(
        clock, client, state, log, standin):
    standin.log_line("slice_job", job="j0", user_key=USER)
    gatherer(clock, client, state, log).gather_once()
    standin.restart()
    standin.log_line("start", version="new")
    gatherer(clock, client, state, log).gather_once()
    assert asked(standin) == ["after=0", "after=1", "after=0"]
    assert [line["event"] for line in log.gathered] == ["slice_job", "start"]


@pytest.mark.parametrize("cursor", [
    {"process": 7, "after": 1}, {"process": "p1", "after": -1}, {"process": "p1"},
    {"process": "p1", "after": True},
])
def test_a_cursor_of_another_form_is_taken_as_none(clock, client, state, log, standin,
                                                   cursor):
    write_record(state, gathering.CURSOR, gathering.CURSOR_KIND, cursor)
    standin.log_line("slice_job", job="j0", user_key=USER)
    gatherer(clock, client, state, log).gather_once()
    assert asked(standin) == ["after=0"]


def test_a_cursor_of_a_newer_format_is_taken_as_none(clock, client, state, log, standin):
    state.put(gathering.CURSOR, json.dumps({"format": 99, "process": standin.process,
                                            "after": 1}).encode())
    standin.log_line("slice_job", job="j0", user_key=USER)
    gatherer(clock, client, state, log).gather_once()
    assert asked(standin) == ["after=0"] and len(log.gathered) == 1


def test_a_cursor_that_cannot_be_read_waits_for_the_next_minute(clock, client, state, log,
                                                                standin):
    standin.log_line("slice_job", job="j0", user_key=USER)
    found = gatherer(clock, client, state, log)
    state.refuse_reads = True
    found.gather_once()
    assert asked(standin) == []
    assert log.own("slice_log_cursor_unreadable")
    state.refuse_reads = False
    found.gather_once()
    assert asked(standin) == ["after=0"]


def test_a_cursor_that_cannot_be_written_is_kept_in_memory(clock, client, state, log,
                                                          standin):
    standin.log_line("slice_job", job="j0", user_key=USER)
    found = gatherer(clock, client, state, log)
    state.refuse_writes = True
    found.gather_once()
    standin.log_line("slice_job", job="j1", user_key=USER)
    found.gather_once()
    assert asked(standin) == ["after=0", "after=1"]
    assert len(log.own("slice_log_cursor_unwritten")) == 2
    state.refuse_writes = False
    found.gather_once()
    record, _ = read_record(state, gathering.CURSOR, gathering.CURSOR_KIND, Lines())
    assert record["after"] == 2


def test_nothing_new_writes_no_cursor_again(clock, client, state, log, standin):
    standin.log_line("slice_job", job="j0", user_key=USER)
    found = gatherer(clock, client, state, log)
    found.gather_once()
    state.refuse_writes = True
    found.gather_once()
    assert not log.own("slice_log_cursor_unwritten")


def test_a_slice_service_that_does_not_answer_is_said_once_until_it_answers(
        clock, state, log, standin):
    client = SliceClient(nobody_listens())
    found = gatherer(clock, client, state, log)
    found.gather_once()
    found.gather_once()
    assert len(log.own("slice_log_unavailable")) == 1
    client.close()
    client = SliceClient(standin.url)
    found._slice = client
    found.gather_once()
    found._slice = SliceClient(nobody_listens())
    found.gather_once()
    assert len(log.own("slice_log_unavailable")) == 2
    client.close()


@pytest.mark.parametrize("status, body, why", [
    (404, {"code": "slice.bad_request"}, "answered 404"),
    (200, {"process": "", "lines": [], "dropped": 0, "more": False}, "not the log"),
    (200, {"process": "p1", "lines": {}, "dropped": 0, "more": False}, "not the log"),
    (200, {"process": "p1", "lines": [], "dropped": -1, "more": False}, "not the log"),
    (200, {"process": "p1", "lines": [], "dropped": True, "more": False}, "not the log"),
    (200, {"process": "p1", "lines": [], "dropped": 0, "more": 1}, "not the log"),
    (200, ["not an object"], "not the log"),
])
def test_an_answer_that_is_not_the_log_is_said_and_gathers_nothing(clock, client, state,
                                                                    log, standin, status,
                                                                    body, why):
    standin.answer_next("GET", "/log", status, body)
    gatherer(clock, client, state, log).gather_once()
    [line] = log.own("slice_log_unavailable")
    assert why in line["why"]
    assert log.gathered == []


def test_lines_of_another_form_are_dropped_and_counted(clock, client, state, log, standin):
    lines = [{"n": 1, "event": "a", "component": "slice"}, "not an object",
             {"event": "no number"}, {"n": True, "event": "b"}, {"n": 1, "event": "again"},
             {"n": 2, "event": "c", "component": "slice"}]
    standin.answer_next("GET", "/log", 200, {"process": "p1", "lines": lines, "dropped": 0,
                                             "more": False})
    gatherer(clock, client, state, log).gather_once()
    assert [line["event"] for line in log.gathered] == ["a", "c"]
    [line] = log.own("slice_log_lines_unreadable")
    assert (line["count"], line["process"]) == (4, "p1")


def test_an_answer_saying_more_with_no_lines_ends_the_gathering(clock, client, state, log,
                                                                standin):
    standin.answer_next("GET", "/log", 200, {"process": "p1", "lines": [], "dropped": 0,
                                             "more": True})
    gatherer(clock, client, state, log).gather_once()
    assert asked(standin) == ["after=0"]


def test_one_gathering_asks_at_most_its_bound(clock, client, state, log, standin,
                                              monkeypatch):
    monkeypatch.setattr(gathering, "MAX_ASKS", 3)
    standin.log_page = 1
    for n in range(5):
        standin.log_line("slice_job", job=f"j{n}", user_key=USER)
    found = gatherer(clock, client, state, log)
    found.gather_once()
    assert asked(standin) == ["after=0", "after=1", "after=2"]
    found.gather_once()
    assert [line["n"] for line in log.gathered] == [1, 2, 3, 4, 5]


def test_a_minutes_lines_of_every_component_are_one_file_and_none_is_printed_again(
        tmp_path, clock, client, state, log, standin):
    write_submitted(state, "jrec", "2026-11-27T22:00:00Z", group="group-of-rec")
    standin.log_line("slice_job", state="queued", job="jrec", user_key=USER)
    log.write("sign_in", user_key=USER)
    log.write_as("wizard", "failure_report", user_key=USER)
    gatherer(clock, client, state, log).gather_once()
    name = log.flush()
    [path] = list((tmp_path / "log").rglob("*.jsonl"))
    assert str(path.relative_to(tmp_path / "log")) == name
    written = [json.loads(text) for text in path.read_text().splitlines()]
    assert [(line["component"], line["event"]) for line in written] == [
        ("front", "sign_in"), ("wizard", "failure_report"), ("slice", "slice_job")]
    assert written[2]["group"] == "group-of-rec"
    assert '"slice_job"' not in log.out.getvalue()


def test_the_loop_gathers_once_a_minute_on_the_clock(clock, client, state, log, standin):
    found = gatherer(clock, client, state, log)
    found.start()
    try:
        found.loop.wait_for_runs(1)
        standin.log_line("slice_job", job="j0", user_key=USER)
        clock.wait_for_sleepers(1)
        clock.advance(gathering.LOG_GATHER_S)
        found.loop.wait_for_runs(2, BACKSTOP_S)
    finally:
        found.stop()
    assert asked(standin) == ["after=0", "after=0"]
    assert [line["n"] for line in log.gathered] == [1]


def test_the_following_tells_the_group_noted_beside_a_slice_job(tmp_path, clock, standin):
    from front_helpers import shut
    from sliced_helpers import queued

    from penguin_front.app import create_app
    from penguin_front.settings import Settings
    from front_helpers import environ

    app = create_app(Settings.from_environ(environ(tmp_path, PENGUIN_SLICE_URL=standin.url)),
                     clock=clock, log=Lines())
    try:
        follower = app.extensions["penguin_front"]["follower"]
        standin.add_job("j1", USER, "p", "s", queued("j1"))
        follower.follow(USER, "j1", "dev-group")
        assert follower.group_of(USER, "j1") == (True, "dev-group")
        assert follower.group_of(OTHER, "j1") == (False, None)
        assert follower.group_of(USER, "j2") == (False, None)
        assert isinstance(app.extensions["penguin_front"]["gatherer"], Gatherer)
    finally:
        shut(app, standin)
