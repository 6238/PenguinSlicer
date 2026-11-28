"""part_store.py: the folder of uploaded parts, its user keys' folders, its two hours, its
limit on disk and a slice job's hold on a part (slice/README-details.md, "The part store")."""
import os
import threading

import pytest

from helpers import USER_KEY, Parts, box_stl, sha256
from penguin_slice import part_store
from penguin_slice.limits import SettingError
from penguin_slice.part_store import PartStore, PartsGone, max_bytes, user_folder


def parts(n, size=10.0):
    """`n` different closed boxes."""
    return [box_stl(size, size, size + i) for i in range(n)]


class TestUserFolder:
    @pytest.mark.parametrize("key", ["../../etc", "/", "", ".", "..", "a/b", "a\\b", "\0", "x" * 10_000, "é",
                                     "\udc80", "C:\\Windows", " "])
    def test_a_user_key_never_names_a_path_outside_its_folder(self, tmp_path, key):
        name = user_folder(key)
        assert len(name) == 64 and set(name) <= set("0123456789abcdef")
        assert (tmp_path / name).resolve().parent == tmp_path.resolve()

    def test_two_user_keys_never_share_a_folder(self):
        keys = ["a", "A", "a ", " a", "a\n", "é", "e\u0301", "user-a", "user-b", "0", "00", "\udc80", "\x80"]
        assert len({user_folder(k) for k in keys}) == len(keys)

    def test_the_same_user_key_gets_the_same_folder_in_every_process(self):
        # SHA-256 of the UTF-8 bytes: no table, nothing to lose at a restart.
        assert user_folder("user-a") == sha256(b"user-a")
        assert user_folder("é") == sha256("é".encode("utf-8"))

    def test_a_part_is_kept_in_its_user_keys_folder(self, tmp_path):
        store = Parts(tmp_path)
        store.add(box_stl(), user_key="../../outside")
        (entry,) = [store.store.get("../../outside", sha256(box_stl()), "mm")]
        assert entry.path.parent == store.store.root / user_folder("../../outside")
        assert entry.path.name == f"{sha256(box_stl())}-mm.stl" and entry.path.read_bytes() == box_stl()
        assert not (tmp_path.parent / "outside").exists()


class TestFinding:
    def test_a_part_is_found_only_under_its_user_key_its_hash_and_its_units(self, tmp_path):
        store = Parts(tmp_path)
        digest = store.add(box_stl())["sha256"]
        assert store.store.get(USER_KEY, digest, "mm") is not None
        assert store.store.get("user-b", digest, "mm") is None
        assert store.store.get(USER_KEY, digest, "in") is None
        assert store.store.get(USER_KEY, "0" * 64, "mm") is None

    def test_two_users_who_upload_one_file_each_have_their_own_entry(self, tmp_path):
        store = Parts(tmp_path)
        store.add(box_stl(), user_key="a")
        store.add(box_stl(), user_key="b")
        a, b = (store.store.get(k, sha256(box_stl()), "mm") for k in ("a", "b"))
        assert a.path != b.path and len(store.store) == 2


class TestTwoHours:
    def test_a_part_unused_for_two_hours_is_gone_and_one_used_in_between_is_kept(self, tmp_path):
        store = Parts(tmp_path)
        old, used = parts(2)
        store.add(old)
        store.add(used)
        store.clock[0] += 3600
        store.store.touch([store.store.get(USER_KEY, sha256(used), "mm")])     # a slice job names it
        store.clock[0] += 3599
        assert store.store.sweep() == 0
        store.clock[0] += 1                                                       # 7,200 s after the upload
        assert store.store.sweep() == 1
        assert store.store.get(USER_KEY, sha256(old), "mm") is None
        assert store.store.get(USER_KEY, sha256(used), "mm") is not None
        assert not (store.store.root / user_folder(USER_KEY) / f"{sha256(old)}-mm.stl").exists()
        store.clock[0] += 3600
        assert store.store.sweep() == 1 and len(store.store) == 0

    def test_a_repeated_upload_renews_the_two_hours(self, tmp_path):
        store = Parts(tmp_path)
        store.add(box_stl())
        store.clock[0] += 7000
        store.add(box_stl())
        store.clock[0] += 7000
        assert store.store.sweep() == 0 and len(store.store) == 1

    def test_the_figure_is_two_hours(self):
        assert part_store.PART_STORE_TTL_S == 7200


class TestLimitOnDisk:
    def test_one_user_keys_thirty_parts_are_all_kept_under_a_generous_limit(self, tmp_path):
        store = Parts(tmp_path)
        for data in parts(30):
            store.add(data)
        assert len(store.store) == 30 and store.store.total_bytes() == 30 * 684

    def test_past_the_limit_the_least_recently_used_part_of_any_user_key_goes(self, tmp_path):
        store = Parts(tmp_path, max_bytes=3 * 684)              # three boxes of 684 bytes
        first, second, third, fourth = parts(4)
        store.add(first, user_key="a")
        store.clock[0] += 1
        store.add(second, user_key="b")
        store.clock[0] += 1
        store.add(third, user_key="a")
        store.clock[0] += 1
        store.store.touch([store.store.get("a", sha256(first), "mm")])        # first is now the most recent
        store.clock[0] += 1
        store.add(fourth, user_key="c")
        assert store.store.get("b", sha256(second), "mm") is None             # b's part, the least recently used
        assert {(e.user_key, e.sha256) for e in store.store._entries.values()} == {
            ("a", sha256(first)), ("a", sha256(third)), ("c", sha256(fourth))}
        assert store.store.total_bytes() == 3 * 684

    def test_the_part_just_added_is_never_the_one_removed(self, tmp_path):
        store = Parts(tmp_path, max_bytes=684)
        first, second = parts(2)
        store.add(first)
        store.clock[0] -= 10                                     # a clock that went back: the new part looks older
        store.add(second)
        assert store.store.get(USER_KEY, sha256(second), "mm") is not None
        assert store.store.get(USER_KEY, sha256(first), "mm") is None

    @pytest.mark.parametrize("raw, expected", [("", 1024 * 1024 * 1024), ("8", 8 * 1024 * 1024),
                                               ("2048", 2048 * 1024 * 1024)])
    def test_the_setting(self, raw, expected):
        assert max_bytes({part_store.MAX_MB_ENV: raw} if raw else {}) == expected

    @pytest.mark.parametrize("raw", ["7", "0", "-5", "1e3", " 100", "²", "12345678", "lots"])
    def test_a_bad_setting_is_refused_naming_it(self, raw):
        with pytest.raises(SettingError) as caught:
            max_bytes({part_store.MAX_MB_ENV: raw})
        assert "PENGUIN_SLICE_PART_STORE_MAX_MB" in str(caught.value) and "1024 MB" in str(caught.value)

    def test_the_setting_is_read_from_the_environment(self, monkeypatch):
        monkeypatch.setenv(part_store.MAX_MB_ENV, "16")
        assert max_bytes() == 16 * 1024 * 1024


class TestHold:
    def test_removing_a_part_does_not_touch_a_slice_job_that_holds_it(self, tmp_path):
        store = Parts(tmp_path)
        store.add(box_stl())
        entry = store.store.get(USER_KEY, sha256(box_stl()), "mm")
        held = store.store.hold([entry], tmp_path / "job" / "parts")
        store.clock[0] += 7200
        assert store.store.sweep() == 1 and not entry.path.exists()
        assert held[(entry.sha256, "mm")].read_bytes() == box_stl()

    def test_a_hold_is_a_hard_link(self, tmp_path):
        store = Parts(tmp_path)
        store.add(box_stl())
        entry = store.store.get(USER_KEY, sha256(box_stl()), "mm")
        target = store.store.hold([entry, entry], tmp_path / "job")[(entry.sha256, "mm")]
        assert os.stat(target).st_ino == os.stat(entry.path).st_ino

    def test_without_hard_links_the_hold_is_a_copy(self, tmp_path, monkeypatch):
        store = Parts(tmp_path)
        store.add(box_stl())
        entry = store.store.get(USER_KEY, sha256(box_stl()), "mm")
        monkeypatch.setattr(part_store.os, "link", lambda *a: (_ for _ in ()).throw(OSError(18, "Cross-device link")))
        target = store.store.hold([entry], tmp_path / "job")[(entry.sha256, "mm")]
        assert target.read_bytes() == box_stl() and os.stat(target).st_ino != os.stat(entry.path).st_ino

    def test_a_part_removed_before_the_hold_is_named_and_nothing_is_held(self, tmp_path):
        store = Parts(tmp_path, max_bytes=684)
        first, second = parts(2)
        store.add(first)
        entry = store.store.get(USER_KEY, sha256(first), "mm")
        store.clock[0] += 1
        store.add(second)                                   # first pushed out
        with pytest.raises(PartsGone) as caught:
            store.store.hold([entry], tmp_path / "job")
        assert caught.value.entries == [entry] and not (tmp_path / "job").exists()


class TestWriting:
    def test_a_part_store_that_cannot_be_written_raises(self, tmp_path, monkeypatch):
        store = Parts(tmp_path)
        monkeypatch.setattr(part_store.os, "fdopen", lambda *a, **k: (_ for _ in ()).throw(
            OSError(28, "No space left on device")))
        with pytest.raises(OSError):
            store.add(box_stl())
        assert len(store.store) == 0
        assert list((store.store.root / user_folder(USER_KEY)).iterdir()) == []     # no half-written file

    def test_uploads_from_many_threads_are_all_kept(self, tmp_path):
        store = Parts(tmp_path)
        boxes = parts(20)
        threads = [threading.Thread(target=store.add, args=(data,), kwargs={"user_key": f"u{i % 3}"})
                   for i, data in enumerate(boxes)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        assert len(store.store) == 20

    def test_the_store_folder_is_made(self, tmp_path):
        assert PartStore(tmp_path / "a" / "b", 1).root.is_dir()
