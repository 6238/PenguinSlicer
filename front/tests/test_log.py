"""The log's writer (README-details.md, "The log"): every line on standard output at once,
and gathered into one new file a minute in the log bucket, in folders by year, month and
day, named in UTC."""

import io
import json
import threading

import pytest

from front_fakes import Announcer
from penguin_front.app import create_app
from penguin_front.buckets import FolderBucket
from penguin_front.log import LOG_FLUSH_S, Log, utc_milliseconds
from penguin_front.settings import Settings

NAME = r"2026/11/27/\d{6}-[0-9a-f]{8}\.jsonl"


class Flushes(Announcer):
    def __init__(self):
        super().__init__()
        self.count = 0

    def __call__(self):
        self.count += 1
        self.announce()


@pytest.fixture
def bucket(tmp_path, clock):
    return FolderBucket(tmp_path / "log", clock)


@pytest.fixture
def stdout():
    return io.StringIO()


@pytest.fixture
def flushes():
    return Flushes()


@pytest.fixture
def log(clock, stdout, bucket, flushes):
    writer = Log(clock, stdout, bucket, on_flush=flushes)
    yield writer
    writer.stop()


def files(bucket):
    return [entry.name for entry in bucket.list("")]


def lines_of(bucket, name):
    return [json.loads(line) for line in bucket.get(name)[0].decode().splitlines()]


def test_a_line_carries_the_time_to_the_millisecond_the_component_and_the_event(log, clock,
                                                                                 stdout):
    clock.advance(0.25)
    line = log.write("start", version="20261127T221405Z-0000000")
    assert line == {"time": "2026-11-27T22:14:05.250Z", "component": "front",
                    "event": "start", "version": "20261127T221405Z-0000000"}
    assert json.loads(stdout.getvalue()) == line


def test_every_line_goes_to_standard_output_at_once_one_json_object_a_line(log, stdout):
    log.write("one", text="a\nb")
    log.write("two", value=3)
    printed = stdout.getvalue().splitlines()
    assert [json.loads(p)["event"] for p in printed] == ["one", "two"]
    assert json.loads(printed[0])["text"] == "a\nb"


def test_a_field_cannot_overwrite_the_time_the_component_or_the_event(log):
    line = log.write("e", time="then", component="slice", event="other")
    assert line["component"] == "front" and line["event"] == "e" and line["time"] != "then"


def test_a_value_json_cannot_hold_is_written_as_text(log):
    assert json.loads(json.dumps(log.write("e", where=object())))["where"].startswith("<object")


def test_a_number_json_cannot_hold_is_written_as_text(log, stdout):
    line = log.write("e", a=float("nan"), b=[float("inf")], c={"d": float("-inf")}, e=1.5)
    printed = json.loads(stdout.getvalue(), parse_constant=lambda name: pytest.fail(name))
    assert printed == line
    assert (line["a"], line["b"], line["c"], line["e"]) == ("nan", ["inf"], {"d": "-inf"}, 1.5)


def test_an_integer_too_long_to_write_as_digits_is_written_as_a_note(log, stdout):
    line = log.write("e", big=10**5000, small=-(10**4400), key={10**5000: "k"}, fine=10**4000)
    assert json.loads(stdout.getvalue()) == line
    assert line["big"] == "<int of 16610 bits, too long to write>"
    assert line["small"] == "<int of 14617 bits, too long to write>"
    assert line["key"] == {"<int of 16610 bits, too long to write>": "k"}
    assert line["fine"] == 10**4000


def test_a_value_whose_text_cannot_be_made_is_written_as_a_note(log, stdout):
    class Stubborn:
        def __str__(self):
            raise RuntimeError("no text")

    line = log.write("e", value=Stubborn(), key={Stubborn(): 1}, kept="yes")
    assert json.loads(stdout.getvalue()) == line
    assert line["value"] == "<Stubborn that cannot be written as text>"
    assert line["key"] == {"<Stubborn that cannot be written as text>": 1}
    assert line["kept"] == "yes"


def test_a_container_that_cannot_be_read_is_written_as_a_note(log, stdout):
    class BrokenList(list):
        def __iter__(self):
            raise RuntimeError("no items")

    class BrokenDict(dict):
        def items(self):
            raise RuntimeError("no items")

    class BrokenTuple(tuple):
        def __iter__(self):
            raise RuntimeError("no items")

    line = log.write("e", items=BrokenList([1]), table=BrokenDict(a=1),
                     pair=BrokenTuple((1, 2)), inside=[BrokenList()], kept="yes")
    assert json.loads(stdout.getvalue()) == line
    assert line["items"] == "<BrokenList that cannot be read>"
    assert line["table"] == "<BrokenDict that cannot be read>"
    assert line["pair"] == "<BrokenTuple that cannot be read>"
    assert line["inside"] == ["<BrokenList that cannot be read>"]
    assert line["kept"] == "yes"


def test_gathered_lines_that_cannot_be_read_are_kept_as_notes(log, bucket):
    class BrokenDict(dict):
        def items(self):
            raise RuntimeError("no items")

    log.gather([{"component": "slice", "event": "e", "x": BrokenDict(a=1)}])
    [kept] = lines_of(bucket, log.flush())
    assert kept["x"] == "<BrokenDict that cannot be read>"


def test_keys_that_are_not_text_are_written_as_text(log):
    line = log.write("e", counts={1: "one", (2, 3): "pair", None: "none"})
    assert line["counts"] == {"1": "one", "(2, 3)": "pair", "None": "none"}


def test_a_value_that_holds_itself_is_written_and_the_line_kept(log, stdout):
    circle = {"name": "circle"}
    circle["self"] = circle
    ring = [1]
    ring.append(ring)
    line = log.write("e", circle=circle, ring=ring)
    assert line["circle"]["name"] == "circle" and isinstance(line["circle"]["self"], str)
    assert line["ring"][0] == 1 and isinstance(line["ring"][1], str)
    assert json.loads(stdout.getvalue()) == line


def test_a_value_too_deep_to_write_is_written_as_a_note_and_the_line_kept(log, stdout):
    deep = []
    for _ in range(100_000):
        deep = [deep]
    line = log.write("e", deep=deep, kept="yes")
    assert line["kept"] == "yes" and json.loads(stdout.getvalue()) == line
    written, levels = line["deep"], 0
    while isinstance(written, list):
        written, levels = written[0], levels + 1
    assert written == "<list nested past 64 levels>" and levels == 63


def test_gathered_lines_json_cannot_hold_are_kept_as_text(log, bucket):
    log.gather([{"component": "slice", "event": "e", "x": float("nan"), 7: "seven"}])
    name = log.flush()
    [kept] = lines_of(bucket, name)
    assert kept["x"] == "nan" and kept["7"] == "seven"


def test_a_line_may_be_written_for_another_component(log, stdout):
    line = log.write_as("wizard", "report_failure", what="storage_refused")
    assert line["component"] == "wizard" and json.loads(stdout.getvalue()) == line


def test_a_minutes_lines_of_every_component_become_one_new_file(log, bucket, clock, flushes):
    log.start()
    log.write("start")
    log.write_as("wizard", "report_drawing", view="layout")
    log.gather([{"n": 1, "time": "2026-11-27T22:14:05.412Z", "component": "slice",
                 "event": "slice_job", "job": "j1"}])
    clock.wait_for_sleepers(1)
    clock.advance(LOG_FLUSH_S)
    flushes.wait_for(lambda: flushes.count == 1, "the first minute's file")
    [name] = files(bucket)
    assert __import__("re").fullmatch(NAME, name)
    assert name.startswith("2026/11/27/221505-")
    assert [(line["component"], line["event"]) for line in lines_of(bucket, name)] == [
        ("front", "start"), ("wizard", "report_drawing"), ("slice", "slice_job")]


def test_the_gathered_lines_of_another_component_are_not_printed_again(log, stdout):
    log.gather([{"component": "slice", "event": "slice_job"}])
    assert stdout.getvalue() == ""


def test_each_minute_writes_a_new_file_and_never_touches_one_written(log, bucket, clock,
                                                                    flushes):
    log.start()
    for minute in range(3):
        log.write("tick", minute=minute)
        clock.wait_for_sleepers(1)
        clock.advance(LOG_FLUSH_S)
        flushes.wait_for(lambda: flushes.count == minute + 1, f"minute {minute}")
    written = files(bucket)
    assert len(written) == 3
    assert [lines_of(bucket, name)[0]["minute"] for name in written] == [0, 1, 2]
    for name in written:
        assert len(lines_of(bucket, name)) == 1


def test_a_minute_with_no_lines_writes_no_file(log, bucket, clock, flushes):
    log.start()
    clock.wait_for_sleepers(1)
    clock.advance(LOG_FLUSH_S)
    flushes.wait_for(lambda: flushes.count == 1, "the empty minute")
    assert files(bucket) == []


def test_the_folders_are_by_year_month_and_day_in_utc(log, bucket, clock):
    clock.advance(2 * 3600)  # 2026-11-28T00:14:05Z: Friday evening in Pacific time
    log.write("late")
    log.flush()
    [name] = files(bucket)
    assert name.startswith("2026/11/28/001405-")


def test_a_file_name_taken_already_is_never_written_over(log, bucket, monkeypatch):
    names = iter(["aaaaaaaa", "aaaaaaaa", "bbbbbbbb"])
    monkeypatch.setattr("penguin_front.log._file_suffix", lambda: next(names))
    log.write("first")
    log.flush()
    log.write("second")
    log.flush()
    assert [lines_of(bucket, n)[0]["event"] for n in files(bucket)] == ["first", "second"]
    assert files(bucket)[1].endswith("-bbbbbbbb.jsonl")


def test_no_free_name_in_a_few_attempts_keeps_the_lines_for_the_next_minute(log, bucket,
                                                                            monkeypatch,
                                                                            stdout):
    monkeypatch.setattr("penguin_front.log._file_suffix", lambda: "aaaaaaaa")
    log.write("first")
    log.flush()
    log.write("second")
    assert log.flush() is None
    assert json.loads(stdout.getvalue().splitlines()[-1])["event"] == "log_bucket_unwritable"
    monkeypatch.setattr("penguin_front.log._file_suffix", lambda: "bbbbbbbb")
    assert lines_of(bucket, log.flush())[0]["event"] == "second"


def test_a_log_folder_that_cannot_be_written_keeps_the_lines_for_the_next_minute(
        tmp_path, clock, stdout):
    blocker = tmp_path / "log"
    blocker.write_bytes(b"")
    writer = Log(clock, stdout, FolderBucket(blocker, clock))
    writer.write("kept")
    assert writer.flush() is None
    assert json.loads(stdout.getvalue().splitlines()[-1])["event"] == "log_bucket_unwritable"
    blocker.unlink()
    name = writer.flush()
    assert [line["event"] for line in lines_of(FolderBucket(blocker, clock), name)] == ["kept"]


def test_lines_kept_past_their_bound_are_dropped_oldest_first_and_counted(tmp_path, clock,
                                                                          stdout):
    blocker = tmp_path / "log"
    blocker.write_bytes(b"")
    writer = Log(clock, stdout, FolderBucket(blocker, clock), max_pending=3)
    for n in range(5):
        writer.write("line", n=n)
    writer.flush()
    blocker.unlink()
    name = writer.flush()
    written = lines_of(FolderBucket(blocker, clock), name)
    assert [line.get("n") for line in written] == [None, 2, 3, 4]
    assert written[0]["event"] == "log_lines_dropped" and written[0]["dropped"] == 2


def test_the_lines_kept_after_a_failed_file_are_counted_without_the_note_of_drops(
        tmp_path, clock, stdout):
    blocker = tmp_path / "log"
    blocker.write_bytes(b"")
    writer = Log(clock, stdout, FolderBucket(blocker, clock), max_pending=3)
    for n in range(5):
        writer.write("line", n=n)
    writer.flush()
    failures = [json.loads(text) for text in stdout.getvalue().splitlines()
                if json.loads(text)["event"] == "log_bucket_unwritable"]
    assert [failure["lines_kept"] for failure in failures] == [3]


def test_a_count_of_dropped_lines_alone_is_still_written(tmp_path, clock, stdout):
    bucket = FolderBucket(tmp_path / "log", clock)
    writer = Log(clock, stdout, bucket, max_pending=0)
    writer.write("dropped at once")
    [note] = lines_of(bucket, writer.flush())
    assert (note["event"], note["dropped"]) == ("log_lines_dropped", 1)


def test_lines_written_while_a_file_fails_are_kept_after_the_lines_it_held(tmp_path, clock,
                                                                          stdout):
    class FailingWhileWriting:
        def put(self, name, body, **_condition):
            writer.write("meanwhile")
            raise OSError("the store failed")

    writer = Log(clock, stdout, FailingWhileWriting())
    writer.write("held")
    writer.flush()
    writer.bucket = FolderBucket(tmp_path / "log", clock)
    assert [line["event"] for line in lines_of(writer.bucket, writer.flush())] == [
        "held", "meanwhile"]


def test_lines_written_while_a_file_fails_stay_within_the_bound(tmp_path, clock, stdout):
    class FailingWhileWriting:
        def put(self, name, body, **_condition):
            for n in range(3):
                writer.write("meanwhile", n=n)
            raise OSError("the store failed")

    writer = Log(clock, stdout, FailingWhileWriting(), max_pending=3)
    for n in range(3):
        writer.write("held", n=n)
    writer.flush()
    writer.bucket = FolderBucket(tmp_path / "log", clock)
    written = lines_of(writer.bucket, writer.flush())
    assert [(line["event"], line.get("n")) for line in written] == [
        ("log_lines_dropped", None), ("meanwhile", 0), ("meanwhile", 1), ("meanwhile", 2)]
    assert written[0]["dropped"] == 3


def test_the_minutes_loop_runs_with_no_one_told_of_each_file(tmp_path, clock, stdout):
    class Announcing(FolderBucket):
        changes = Announcer()

        def put(self, *args, **kwargs):
            marker = super().put(*args, **kwargs)
            self.changes.announce()
            return marker

    bucket = Announcing(tmp_path / "log", clock)
    writer = Log(clock, stdout, bucket)
    writer.start()
    writer.write("one")
    clock.wait_for_sleepers(1)
    clock.advance(LOG_FLUSH_S)
    bucket.changes.wait_for(lambda: len(bucket.list("")) == 1, "the minute's file")
    writer.stop()


def test_a_standard_output_that_fails_changes_nothing(clock, bucket):
    class Broken:
        def write(self, _text):
            raise BrokenPipeError("closed")

        def flush(self):
            raise BrokenPipeError("closed")

    writer = Log(clock, Broken(), bucket)
    writer.write("still gathered")
    assert lines_of(bucket, writer.flush())[0]["event"] == "still gathered"


def test_a_stop_writes_what_was_gathered(log, bucket):
    log.start()
    log.write("last words")
    log.stop()
    [name] = files(bucket)
    assert lines_of(bucket, name)[0]["event"] == "last words"
    log.stop()


def test_lines_written_from_many_threads_are_each_kept_once(log, bucket):
    def writer(n):
        for k in range(50):
            log.write("t", thread=n, k=k)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    written = lines_of(bucket, log.flush())
    assert sorted((line["thread"], line["k"]) for line in written) == \
        sorted((n, k) for n in range(8) for k in range(50))


def test_the_log_folder_failing_leaves_every_answer_unchanged(tmp_path, clock, stdout):
    blocker = tmp_path / "log"
    blocker.write_bytes(b"")
    good = Log(clock, io.StringIO(), FolderBucket(tmp_path / "good", clock))
    broken = Log(clock, stdout, FolderBucket(blocker, clock))
    settings = Settings.from_environ({"PENGUIN_DEV_IDENTITY": "1"})
    answers = []
    for writer in (good, broken):
        client = create_app(settings, clock=clock, log=writer, version="x").test_client()
        answer = client.get("/nothing")
        writer.flush()
        answers.append((answer.status_code, answer.get_json(), dict(answer.headers)))
    assert answers[0] == answers[1]


def test_the_time_of_a_line_is_utc_to_the_millisecond():
    assert utc_milliseconds(1_795_817_645.4129) == "2026-11-27T22:14:05.412Z"
    assert utc_milliseconds(1_795_817_645.9999) == "2026-11-27T22:14:05.999Z"
