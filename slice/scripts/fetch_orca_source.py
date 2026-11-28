#!/usr/bin/env python3
"""Fetch the pinned Orca's source into tools/orca-source/: `make -C slice orca-source`.

The table of settings is made from Orca's source (scripts/make_settings_table.py), so taking
an Orca version needs its source as well as its release. This downloads GitHub's archive of
the version's tag, verifies it against `SHA_SOURCE`, pinned beside `ORCA_VERSION` in
scripts/install-orca.sh, and keeps only the three files the generator reads (about 1.2 MB of
a 131 MB archive), with a VERSION stamp. Idempotent: nothing is downloaded when the stamp
already records this version and checksum. A failure keeps nothing new and leaves an earlier
source as it was. `PENGUIN_SLICE_ORCA_CACHE` keeps each verified archive and reuses it.

GitHub publishes no checksum of a tag's archive, so `make upgrade-orca` fetches a new
version's archive without one (`trust`) and pins the checksum of what it downloaded;
every later fetch is verified against that pin. Standard library only; members are read by
name and written by this script, never extracted, so no path in the archive is followed.
"""
import argparse
import hashlib
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from make_settings_table import SOURCE_DIR, SOURCE_FILES

SLICE_ROOT = Path(__file__).resolve().parents[1]
INSTALL = SLICE_ROOT / "scripts" / "install-orca.sh"
ARCHIVE_URL = "https://github.com/OrcaSlicer/OrcaSlicer/archive/refs/tags/v{version}.tar.gz"
CHUNK = 1 << 20


class FetchError(Exception):
    """The source could not be fetched; the message says why."""


def pinned(install_text):
    """(version, sha256) of the source, from install-orca.sh's ORCA_VERSION and SHA_SOURCE."""
    version = re.search(r'^ORCA_VERSION="([^"]+)"$', install_text, re.M)
    sha = re.search(r'^SHA_SOURCE="([0-9a-f]{64})"$', install_text, re.M)
    if not (version and sha):
        raise FetchError("install-orca.sh pins no ORCA_VERSION with its SHA_SOURCE")
    return version.group(1), sha.group(1)


def _stamp(version, sha):
    return f"{version} {sha}\n"


def _download(url, target, opener):
    hasher = hashlib.sha256()
    try:
        with opener(urllib.request.Request(url)) as response, open(target, "wb") as out:
            while chunk := response.read(CHUNK):
                hasher.update(chunk)
                out.write(chunk)
    except Exception as exc:          # HTTP 404, no network: all stop the fetch
        raise FetchError(f"download of {url} failed: {type(exc).__name__}: {exc}") from None
    return hasher.hexdigest()


def _sha_of(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(CHUNK):
            hasher.update(chunk)
    return hasher.hexdigest()


def _extract(archive, version, into):
    """The three source files from the archive, written into `into` by their own paths."""
    wanted = {f"OrcaSlicer-{version}/{rel}": rel for rel in SOURCE_FILES.values()}
    try:
        with tarfile.open(archive, mode="r:gz") as tar:
            for member in tar:
                rel = wanted.pop(member.name, None)
                if rel is None or not member.isfile():
                    continue
                target = into / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise FetchError(f"the download is not a .tar.gz of Orca's source: {exc}") from None
    if wanted:
        raise FetchError(f"the archive of v{version} lacks {', '.join(sorted(wanted.values()))}")


def fetch(version, sha, dest=SOURCE_DIR, *, opener=None, cache=None):
    """Fetch v`version`'s source into `dest`, verified against `sha` (None: trust the
    download); return the archive's SHA-256."""
    dest, opener = Path(dest), opener or urllib.request.urlopen
    if sha and (dest / "VERSION").is_file() and (dest / "VERSION").read_text() == _stamp(version, sha):
        return sha
    url = ARCHIVE_URL.format(version=version)
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".orca-source-", dir=dest.parent))
    try:
        cached = Path(cache) / f"OrcaSlicer-{version}.tar.gz" if cache else None
        archive = work / "source.tar.gz"
        if cached and cached.is_file():
            shutil.copyfile(cached, archive)
            actual = _sha_of(archive)
        else:
            actual = _download(url, archive, opener)
        if sha and actual != sha:
            raise FetchError(f"checksum mismatch for {url}: expected {sha}, got {actual}; download deleted")
        tree = work / "tree"
        _extract(archive, version, tree)
        (tree / "VERSION").write_text(_stamp(version, actual))
        if cached and not cached.is_file():
            cached.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(archive, cached)
        shutil.rmtree(dest, ignore_errors=True)
        tree.rename(dest)
        return actual
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--install", default=str(INSTALL), help="the installer holding the pin")
    parser.add_argument("--dest", default=str(SOURCE_DIR))
    args = parser.parse_args(argv)
    try:
        version, sha = pinned(Path(args.install).read_text())
        fetch(version, sha, args.dest, cache=os.environ.get("PENGUIN_SLICE_ORCA_CACHE") or None)
    except FetchError as exc:
        print(f"fetch-orca-source: {exc}", file=sys.stderr)
        return 1
    print(f"fetch-orca-source: Orca {version}'s source at {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
