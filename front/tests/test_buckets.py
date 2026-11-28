"""The bucket interface (README-details.md, "The bucket interface"): one set of tests every
form passes. The fast suite runs it against the folder form, in a fresh temporary folder for
each test; the R2 form (phase 3) is added to `FORMS` and run outside the fast suite."""

import os
import threading

import pytest

from penguin_front import buckets
from penguin_front.buckets import (BadName, BucketUnavailable, ConditionFailed, FolderBucket,
                                   NotFound)

FORMS = ["folder"]
CHUNK = 64


@pytest.fixture(params=FORMS)
def bucket(request, tmp_path, clock):
    return FolderBucket(tmp_path / "bucket", clock, chunk_bytes=CHUNK)


def test_a_file_written_is_read_with_its_marker(bucket):
    marker = bucket.put("config/dev-group.json", b'{"format": 1}')
    body, read_marker = bucket.get("config/dev-group.json")
    assert body == b'{"format": 1}' and read_marker == marker


def test_writing_again_replaces_and_changes_the_marker(bucket):
    first = bucket.put("a", b"one")
    second = bucket.put("a", b"two")
    assert first != second and bucket.get("a") == (b"two", second)


def test_the_marker_follows_the_contents(bucket):
    assert bucket.put("a", b"same") == bucket.put("b", b"same")


def test_a_file_never_written_is_not_found(bucket):
    with pytest.raises(NotFound):
        bucket.get("sliced/u/j1.json")
    with pytest.raises(NotFound):
        bucket.open("nothing")


def test_a_name_under_a_file_is_not_found_and_deleting_it_is_harmless(bucket):
    bucket.put("a", b"a file")
    with pytest.raises(NotFound):
        bucket.get("a/b")
    bucket.delete("a/b")
    assert bucket.get("a")[0] == b"a file"


def test_a_conditional_write_succeeds_while_the_marker_is_unchanged(bucket):
    marker = bucket.put("config/g.json", b"v1")
    new = bucket.put("config/g.json", b"v2", if_marker=marker)
    assert bucket.get("config/g.json") == (b"v2", new)


def test_a_conditional_write_fails_once_the_file_changed(bucket):
    marker = bucket.put("config/g.json", b"v1")
    bucket.put("config/g.json", b"someone else's")
    with pytest.raises(ConditionFailed):
        bucket.put("config/g.json", b"v2", if_marker=marker)
    assert bucket.get("config/g.json")[0] == b"someone else's"


def test_a_conditional_write_fails_on_a_file_that_does_not_exist(bucket):
    with pytest.raises(ConditionFailed):
        bucket.put("config/g.json", b"v2", if_marker="0" * 64)


def test_a_conditional_create_succeeds_once_then_fails_because_the_file_exists(bucket):
    bucket.put("log/2026/11/27/221405-ab.jsonl", b"one", if_absent=True)
    with pytest.raises(ConditionFailed):
        bucket.put("log/2026/11/27/221405-ab.jsonl", b"two", if_absent=True)
    assert bucket.get("log/2026/11/27/221405-ab.jsonl")[0] == b"one"


def test_two_writers_racing_on_one_marker_leave_exactly_one_winner(bucket):
    marker = bucket.put("config/g.json", b"v1")
    results = []
    start = threading.Barrier(8)

    def writer(n):
        start.wait()
        try:
            bucket.put("config/g.json", f"writer {n}".encode(), if_marker=marker)
            results.append("won")
        except ConditionFailed:
            results.append("lost")

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["lost"] * 7 + ["won"]


def test_a_writer_held_between_its_check_and_its_rename_shuts_out_a_second(tmp_path, clock,
                                                                           monkeypatch):
    # The folder form's own test: the first writer is held inside its rename, the second
    # is started and either finishes (no lock: two winners) or reaches the lock; only then
    # is the first let go. No duration is waited on.
    bucket = FolderBucket(tmp_path / "bucket", clock, chunk_bytes=CHUNK)
    marker = bucket.put("config/g.json", b"v1")
    real_replace, real_lock = buckets.os.replace, bucket._lock
    first_in_rename, let_first_go, second_got_on = (threading.Event(), threading.Event(),
                                                    threading.Event())
    results = {}

    def held_replace(source, target):
        if threading.current_thread().name == "first":
            first_in_rename.set()
            let_first_go.wait()
        return real_replace(source, target)

    class AnnouncingLock:
        def __enter__(self):
            if threading.current_thread().name == "second":
                second_got_on.set()
            return real_lock.__enter__()

        def __exit__(self, *exc):
            return real_lock.__exit__(*exc)

    def writer():
        name = threading.current_thread().name
        try:
            bucket.put("config/g.json", name.encode(), if_marker=marker)
            results[name] = "won"
        except ConditionFailed:
            results[name] = "lost"
        finally:
            if name == "second":
                second_got_on.set()

    monkeypatch.setattr(buckets.os, "replace", held_replace)
    bucket._lock = AnnouncingLock()
    first = threading.Thread(target=writer, name="first")
    first.start()
    first_in_rename.wait()
    second = threading.Thread(target=writer, name="second")
    second.start()
    second_got_on.wait()
    let_first_go.set()
    first.join()
    second.join()
    assert results == {"first": "won", "second": "lost"}
    assert bucket.get("config/g.json")[0] == b"first"


def test_a_name_that_is_a_folder_is_not_found_and_deleting_it_is_harmless(bucket):
    bucket.put("a/b", b"a file under a")
    with pytest.raises(NotFound):
        bucket.get("a")
    with pytest.raises(NotFound):
        bucket.open("a")
    bucket.delete("a")
    assert bucket.get("a/b")[0] == b"a file under a"


def test_a_listing_under_a_file_is_empty(bucket):
    bucket.put("a", b"a file")
    assert bucket.list("a/") == [] and bucket.list("a/b/") == []
    assert [e.name for e in bucket.list("a")] == ["a"]


def test_delete_removes_and_a_repeat_is_harmless(bucket):
    bucket.put("sliced/u/j1.gcode.3mf", b"bytes")
    bucket.delete("sliced/u/j1.gcode.3mf")
    bucket.delete("sliced/u/j1.gcode.3mf")
    with pytest.raises(NotFound):
        bucket.get("sliced/u/j1.gcode.3mf")


def test_copy_onto_itself_gives_a_new_store_time_and_keeps_the_contents(bucket, clock):
    marker = bucket.put("sliced/u/j1.gcode.3mf", b"bytes")
    written = bucket.list("sliced/u/")[0].stored_at
    clock.advance(3600)
    refreshed = bucket.copy_onto_itself("sliced/u/j1.gcode.3mf")
    assert refreshed == written + 3600
    assert bucket.list("sliced/u/")[0].stored_at == refreshed
    assert bucket.get("sliced/u/j1.gcode.3mf") == (b"bytes", marker)
    with pytest.raises(NotFound):
        bucket.copy_onto_itself("sliced/u/none")


def test_a_listing_under_a_prefix(bucket, clock):
    bucket.put("sliced/u1/j1.json", b"1")
    clock.advance(1)
    bucket.put("sliced/u1/j2.json", b"22")
    bucket.put("sliced/u2/j3.json", b"333")
    bucket.put("config/g.json", b"4444")
    listed = bucket.list("sliced/u1/")
    assert [(e.name, e.size) for e in listed] == [("sliced/u1/j1.json", 1),
                                                   ("sliced/u1/j2.json", 2)]
    assert listed[1].stored_at - listed[0].stored_at == 1
    assert [e.name for e in bucket.list("sliced/")] == [
        "sliced/u1/j1.json", "sliced/u1/j2.json", "sliced/u2/j3.json"]
    assert [e.name for e in bucket.list("sliced/u1/j2")] == ["sliced/u1/j2.json"]
    assert len(bucket.list("")) == 4
    assert bucket.list("nothing/") == []


def test_a_listing_of_an_empty_bucket_is_empty(bucket):
    assert bucket.list("") == []


def test_an_empty_file_is_written_and_read(bucket):
    marker = bucket.put("empty", b"")
    assert bucket.get("empty") == (b"", marker)


def test_a_listing_never_shows_a_temporary_file_or_folder(bucket, tmp_path):
    bucket.put("d/a", b"x")
    (tmp_path / "bucket" / "d" / ".tmp-left-by-a-crash").write_bytes(b"half")
    (tmp_path / "bucket" / ".hidden").mkdir()
    (tmp_path / "bucket" / ".hidden" / "b").write_bytes(b"y")
    assert [e.name for e in bucket.list("")] == ["d/a"]


def test_a_stream_larger_than_the_memory_chunk_passes_in_pieces(bucket):
    pieces = [bytes([n]) * CHUNK for n in range(5)] + [b"tail"]
    bucket.put("sliced/u/j1.gcode.3mf", iter(pieces))
    with bucket.open("sliced/u/j1.gcode.3mf") as stored:
        assert stored.size == 5 * CHUNK + 4
        read = list(stored.chunks())
    assert all(len(piece) <= CHUNK for piece in read) and len(read) == 6
    assert b"".join(read) == b"".join(pieces)


def test_a_file_like_source_is_read_in_pieces(bucket, tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"x" * (3 * CHUNK))
    with source.open("rb") as handle:
        bucket.put("f", handle)
    assert bucket.get("f")[0] == b"x" * (3 * CHUNK)


def test_a_stream_that_fails_halfway_leaves_nothing_written(bucket):
    def failing():
        yield b"half"
        raise ConnectionError("cut")

    bucket.put("sliced/u/j1.gcode.3mf", b"before")
    with pytest.raises(ConnectionError):
        bucket.put("sliced/u/j1.gcode.3mf", failing())
    assert bucket.get("sliced/u/j1.gcode.3mf")[0] == b"before"
    with pytest.raises(ConnectionError):
        bucket.put("sliced/u/j2.gcode.3mf", failing())
    assert [e.name for e in bucket.list("")] == ["sliced/u/j1.gcode.3mf"]


@pytest.mark.parametrize("name", ["", "/abs", "a//b", "a/../b", "..", "a/./b", ".hidden",
                                  "a/.tmp-x", "a\\b", "a\0b", "a/", "x" * 1025, "x" * 256,
                                  "a/" + "y" * 256, "é" * 128 + "/b", "a/\udc80"])
def test_a_name_of_the_wrong_form_is_refused_before_any_file_is_touched(bucket, name):
    with pytest.raises(BadName):
        bucket.put(name, b"x")
    with pytest.raises(BadName):
        bucket.get(name)


def test_a_name_of_parts_of_255_bytes_and_1024_bytes_in_all_is_written_and_read(bucket):
    longest_part = "x" * 255
    longest = "/".join(["a" * 255, "b" * 255, "c" * 255, "d" * 254, "e"])
    assert len(longest.encode()) == 1024
    for name in (longest_part, "a/" + "é" * 127, longest):
        bucket.put(name, b"kept")
        assert bucket.get(name)[0] == b"kept"


def test_a_bucket_that_cannot_be_written_is_unavailable(tmp_path, clock):
    blocker = tmp_path / "not-a-folder"
    blocker.write_bytes(b"")
    broken = FolderBucket(blocker, clock)
    for attempt in (lambda: broken.put("a", b"x"), lambda: broken.get("a"),
                    lambda: broken.list(""), lambda: broken.delete("a"),
                    lambda: broken.copy_onto_itself("a")):
        with pytest.raises(BucketUnavailable):
            attempt()


def test_a_folder_that_cannot_be_read_is_unavailable(tmp_path, clock):
    if os.geteuid() == 0:  # pragma: no cover - permissions do not bind the root user
        pytest.skip("permissions do not bind the root user")
    bucket = FolderBucket(tmp_path / "b", clock)
    bucket.put("d/a", b"x")
    (tmp_path / "b" / "d").chmod(0)
    try:
        with pytest.raises(BucketUnavailable):
            bucket.get("d/a")
        with pytest.raises(BucketUnavailable):
            bucket.list("d/")
        with pytest.raises(BucketUnavailable):
            bucket.delete("d/a")
    finally:
        (tmp_path / "b" / "d").chmod(0o755)
