"""The format number on every record the front server writes to the state bucket
(README-details.md, "The bucket interface"; contracts/README.md, "Rules")."""

import json

import pytest

from penguin_front import records
from penguin_front.buckets import FolderBucket, NotFound
from penguin_front.records import UnreadableRecord, read_record, write_record


class Lines:
    def __init__(self):
        self.lines = []

    def write(self, event, **fields):
        self.lines.append({"event": event, **fields})


@pytest.fixture
def bucket(tmp_path, clock):
    return FolderBucket(tmp_path / "state", clock)


@pytest.mark.parametrize("kind", sorted(records.FORMATS))
def test_every_record_written_carries_its_kinds_format_number(bucket, kind):
    write_record(bucket, f"{kind}/r.json", kind, {"slice": "j1"})
    stored = json.loads(bucket.get(f"{kind}/r.json")[0])
    assert stored["format"] == records.FORMATS[kind] and stored["slice"] == "j1"


def test_a_record_that_names_another_format_is_written_with_the_front_servers(bucket):
    write_record(bucket, "r.json", "sliced_file", {"format": 99, "slice": "j1"})
    assert json.loads(bucket.get("r.json")[0])["format"] == records.FORMATS["sliced_file"]


def test_the_formats_count_from_one():
    assert records.FORMATS and all(isinstance(n, int) and n >= 1
                                   for n in records.FORMATS.values())


def test_a_record_written_is_read_with_its_marker(bucket):
    marker = write_record(bucket, "r.json", "sliced_file", {"slice": "j1"})
    record, read_marker = read_record(bucket, "r.json", "sliced_file", Lines())
    assert record == {"format": 1, "slice": "j1"} and read_marker == marker


def test_a_conditional_write_of_a_record_passes_its_condition_on(bucket):
    marker = write_record(bucket, "r.json", "configuration", {"v": 1}, if_absent=True)
    write_record(bucket, "r.json", "configuration", {"v": 2}, if_marker=marker)
    assert read_record(bucket, "r.json", "configuration", Lines())[0]["v"] == 2


def test_a_record_of_the_previous_format_is_read(bucket, monkeypatch):
    write_record(bucket, "r.json", "sliced_file", {"slice": "j1"})
    monkeypatch.setitem(records.FORMATS, "sliced_file", 2)
    record, _marker = read_record(bucket, "r.json", "sliced_file", Lines())
    assert record["format"] == 1


@pytest.mark.parametrize("stored, found", [
    (b'{"format": 2, "slice": "j1"}', 2),
    (b'{"slice": "j1"}', None),
    (b'{"format": "1"}', "1"),
    (b'{"format": true}', True),
    (b'{"format": 0}', 0),
])
def test_a_record_of_a_format_it_does_not_know_is_refused_and_logged(bucket, stored, found):
    bucket.put("sliced/u/j1.json", stored)
    log = Lines()
    with pytest.raises(UnreadableRecord):
        read_record(bucket, "sliced/u/j1.json", "sliced_file", log)
    assert log.lines == [{"event": "record_unreadable", "record": "sliced/u/j1.json",
                          "kind": "sliced_file", "format": found, "reads_up_to": 1,
                          "why": log.lines[0]["why"]}]


@pytest.mark.parametrize("stored", [b"not json", b"[1]", b"\xff"])
def test_a_record_that_is_not_a_json_object_is_refused_and_logged(bucket, stored):
    bucket.put("r.json", stored)
    log = Lines()
    with pytest.raises(UnreadableRecord):
        read_record(bucket, "r.json", "sliced_file", log)
    assert log.lines[0]["event"] == "record_unreadable" and log.lines[0]["format"] is None


def test_a_record_not_there_is_not_found(bucket):
    with pytest.raises(NotFound):
        read_record(bucket, "r.json", "sliced_file", Lines())


def test_a_record_of_a_kind_the_front_server_does_not_write_is_a_fault(bucket):
    with pytest.raises(KeyError):
        write_record(bucket, "r.json", "no_such_kind", {})
