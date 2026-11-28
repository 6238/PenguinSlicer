"""scripts/fetch_orca_source.py, which fetches and verifies the pinned Orca's source for the
table of settings, with a made-up archive in place of GitHub's (no network)."""
import hashlib
import io
import tarfile

import pytest

from fetch_orca_source import ARCHIVE_URL, FetchError, fetch, main, pinned
from helpers import FIXTURES, INSTALL_ORCA
from make_settings_table import SOURCE_FILES

SOURCE = FIXTURES / "orca_source"


def archive(version="9.9.9", drop=(), extra=()):
    """A .tar.gz shaped like GitHub's archive of a tag: every file under one top folder."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for rel in SOURCE_FILES.values():
            if rel in drop:
                continue
            data = (SOURCE / rel).read_bytes()
            info = tarfile.TarInfo(f"OrcaSlicer-{version}/{rel}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name, data in extra:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def opener_for(data, seen):
    def opener(request):
        seen.append(request.full_url)
        if isinstance(data, Exception):
            raise data
        return Response(data)
    return opener


def digest(data):
    return hashlib.sha256(data).hexdigest()


def test_the_pin_is_read_from_the_installer():
    version, sha = pinned(INSTALL_ORCA.read_text())
    assert version == "2.4.2" and len(sha) == 64


def test_a_pin_without_its_source_checksum_is_refused():
    with pytest.raises(FetchError, match="SHA_SOURCE"):
        pinned('ORCA_VERSION="2.4.2"\n')


def test_fetches_verifies_and_keeps_only_the_three_files(tmp_path):
    data, seen = archive(extra=[("OrcaSlicer-9.9.9/README.md", b"not wanted")]), []
    dest = tmp_path / "orca-source"
    assert fetch("9.9.9", digest(data), dest, opener=opener_for(data, seen)) == digest(data)
    assert seen == [ARCHIVE_URL.format(version="9.9.9")]
    for rel in SOURCE_FILES.values():
        assert (dest / rel).read_bytes() == (SOURCE / rel).read_bytes()
    assert sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()) == sorted(
        ["VERSION", *SOURCE_FILES.values()])
    assert (dest / "VERSION").read_text() == f"9.9.9 {digest(data)}\n"


def test_a_second_fetch_of_the_same_pin_downloads_nothing(tmp_path):
    data, seen = archive(), []
    fetch("9.9.9", digest(data), tmp_path / "s", opener=opener_for(data, seen))
    fetch("9.9.9", digest(data), tmp_path / "s", opener=opener_for(data, seen))
    assert len(seen) == 1


def test_a_wrong_checksum_keeps_nothing(tmp_path):
    data = archive()
    dest = tmp_path / "s"
    with pytest.raises(FetchError, match=r"checksum mismatch.*expected 0{64}"):
        fetch("9.9.9", "0" * 64, dest, opener=opener_for(data, []))
    assert not dest.exists() and [p.name for p in tmp_path.iterdir()] == ["orca-placeholder"]   # conftest's


def test_a_wrong_checksum_leaves_an_earlier_source_as_it_was(tmp_path):
    data = archive()
    dest = tmp_path / "s"
    fetch("9.9.9", digest(data), dest, opener=opener_for(data, []))
    with pytest.raises(FetchError):
        fetch("9.9.8", "0" * 64, dest, opener=opener_for(archive("9.9.8"), []))
    assert (dest / "VERSION").read_text().startswith("9.9.9 ")


def test_trusting_the_download_records_its_checksum(tmp_path):
    data = archive()
    assert fetch("9.9.9", None, tmp_path / "s", opener=opener_for(data, [])) == digest(data)


def test_an_archive_missing_a_file_names_it(tmp_path):
    data = archive(drop=("src/slic3r/GUI/Tab.cpp",))
    with pytest.raises(FetchError, match="src/slic3r/GUI/Tab.cpp"):
        fetch("9.9.9", digest(data), tmp_path / "s", opener=opener_for(data, []))
    assert not (tmp_path / "s").exists()


def test_a_member_outside_the_top_folder_is_never_written(tmp_path):
    data = archive(extra=[("../escape.txt", b"x"), ("/abs.txt", b"x")])
    fetch("9.9.9", digest(data), tmp_path / "s", opener=opener_for(data, []))
    assert not (tmp_path / "escape.txt").exists()


def test_a_failed_download_is_explained(tmp_path):
    with pytest.raises(FetchError, match=r"download of .*v9.9.9.tar.gz failed: OSError: no network"):
        fetch("9.9.9", "0" * 64, tmp_path / "s", opener=opener_for(OSError("no network"), []))


def test_not_an_archive_is_explained(tmp_path):
    data = b"<html>rate limited</html>"
    with pytest.raises(FetchError, match="not a .tar.gz"):
        fetch("9.9.9", digest(data), tmp_path / "s", opener=opener_for(data, []))


def test_the_cache_keeps_a_verified_download(tmp_path):
    data, seen = archive(), []
    cache = tmp_path / "cache"
    fetch("9.9.9", digest(data), tmp_path / "a", opener=opener_for(data, seen), cache=cache)
    fetch("9.9.9", digest(data), tmp_path / "b", opener=opener_for(data, seen), cache=cache)
    assert len(seen) == 1 and (tmp_path / "b" / "VERSION").is_file()


def test_a_changed_archive_in_the_cache_is_refused_and_named(tmp_path):
    data, seen = archive(), []
    cache = tmp_path / "cache"
    cache.mkdir()
    cached = cache / "OrcaSlicer-9.9.9.tar.gz"
    cached.write_bytes(archive(extra=[("OrcaSlicer-9.9.9/planted.txt", b"x")]))
    dest = tmp_path / "s"
    with pytest.raises(FetchError, match=rf"checksum mismatch for the cached archive {cached}: expected "
                                         rf"{digest(data)}.*remove it"):
        fetch("9.9.9", digest(data), dest, opener=opener_for(data, seen), cache=cache)
    assert seen == [] and not dest.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cache", "orca-placeholder"]   # no work folder left


def test_a_download_that_fails_its_checksum_is_not_cached(tmp_path):
    cache = tmp_path / "cache"
    with pytest.raises(FetchError, match="checksum mismatch"):
        fetch("9.9.9", "0" * 64, tmp_path / "s", opener=opener_for(archive(), []), cache=cache)
    assert not (cache / "OrcaSlicer-9.9.9.tar.gz").exists()


def test_main_fetches_the_pin_and_reports_a_failure(tmp_path, capsys, monkeypatch):
    import fetch_orca_source
    data = archive("2.4.2")
    install = tmp_path / "install-orca.sh"
    install.write_text(f'ORCA_VERSION="2.4.2"\nSHA_SOURCE="{digest(data)}"\n')
    monkeypatch.setattr(fetch_orca_source.urllib.request, "urlopen", opener_for(data, []))
    assert main(["--install", str(install), "--dest", str(tmp_path / "s")]) == 0
    install.write_text('ORCA_VERSION="2.4.2"\nSHA_SOURCE="' + "0" * 64 + '"\n')
    assert main(["--install", str(install), "--dest", str(tmp_path / "t")]) == 1
    assert "fetch-orca-source: checksum mismatch" in capsys.readouterr().err
