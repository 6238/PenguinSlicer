"""Tests for scripts/install-orca.sh. No network: uname and curl are faked on PATH.

Each test copies the script into its own temporary slice/ layout (scripts/ beside
tools/), so it exercises the script's own idea of where Orca goes.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from helpers import INSTALL_ORCA, pinned_orca_version

SCRIPT = INSTALL_ORCA
V = pinned_orca_version()      # read from the script itself: the one place the version is stated
RELEASE = f"https://github.com/OrcaSlicer/OrcaSlicer/releases/download/v{V}/"


class Sandbox:
    def __init__(self, root):
        self.root = root
        (root / "scripts").mkdir(parents=True)
        self.script = root / "scripts" / "install-orca.sh"
        shutil.copy(SCRIPT, self.script)
        self.script.chmod(0o755)
        self.fakebin = root / "fakebin"
        self.fakebin.mkdir()
        self.dest = root / "tools" / "orca"
        self.calls = root / "curl-calls"

    def fake(self, name, body):
        path = self.fakebin / name
        path.write_text("#!/usr/bin/env bash\n" + body)
        path.chmod(0o755)

    def fake_uname(self, system, machine):
        self.fake("uname", 'case "$1" in -m) echo %s;; *) echo %s;; esac\n' % (machine, system))

    def fake_curl_garbage(self):
        # Writes junk to whatever -o names and records each URL, and where it was written.
        self.fake("curl", 'out=""; while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift;; '
                          'http*) echo "$1" >> "%s";; esac; shift; done\n'
                          'echo "$out" >> "%s.out"\n'
                          'mkdir -p "$(dirname "$out")"; echo garbage > "$out"\n' % (self.calls, self.calls))

    def run(self):
        env = dict(os.environ, PATH=f"{self.fakebin}:{os.environ['PATH']}")
        return subprocess.run(["bash", str(self.script)], env=env, capture_output=True, text=True, timeout=60)


@pytest.fixture
def box(tmp_path):
    return Sandbox(tmp_path / "slice")


def test_installs_into_tools_orca_of_the_slice_project(box):
    box.fake_uname("Linux", "x86_64")
    box.fake_curl_garbage()
    box.run()
    # The checksum fails, but the download went to <slice>/tools/orca, not a level above.
    written = Path(f"{box.calls}.out").read_text().splitlines()
    assert written == [str(box.dest / "download" / f"OrcaSlicer_Linux_AppImage_Ubuntu2404_V{V}.AppImage")]
    assert not (box.root.parent / "tools").exists()
    assert box.calls.read_text().splitlines() == [RELEASE + f"OrcaSlicer_Linux_AppImage_Ubuntu2404_V{V}.AppImage"]


def test_refuses_unknown_platform_naming_both_values(box):
    box.fake_uname("FreeBSD", "amd64")
    box.fake_curl_garbage()
    result = box.run()
    assert result.returncode != 0
    assert "FreeBSD" in result.stderr and "amd64" in result.stderr
    assert not box.calls.exists(), "must not download"
    assert not (box.dest / "VERSION").exists()


def test_exits_without_downloading_when_version_and_arch_match(box):
    box.fake_uname("Linux", "aarch64")
    box.fake_curl_garbage()
    box.dest.mkdir(parents=True)
    (box.dest / "VERSION").write_text(f"{V} linux-aarch64\n")
    wrapper = box.dest / "orca-slicer"
    wrapper.write_text("#!/bin/sh\nexit 0\n")
    wrapper.chmod(0o755)
    result = box.run()
    assert result.returncode == 0, result.stderr
    assert "already installed" in result.stdout
    assert not box.calls.exists(), "must not download"
    assert (box.dest / "VERSION").read_text().strip() == f"{V} linux-aarch64"


def test_replaces_install_from_another_architecture(box):
    box.fake_uname("Linux", "aarch64")
    box.fake_curl_garbage()
    box.dest.mkdir(parents=True)
    (box.dest / "VERSION").write_text(f"{V} darwin-arm64\n")
    (box.dest / "orca-slicer").write_text("#!/bin/sh\nexit 0\n")
    (box.dest / "orca-slicer").chmod(0o755)
    result = box.run()
    # The fake download is garbage, so the run must fail at the checksum, proving it tried
    # to replace the foreign install rather than trusting it. The wrapper is executable,
    # so only the architecture half of the stamp can have forced the reinstall.
    assert result.returncode != 0
    assert box.calls.exists(), "must download"
    assert not (box.dest / "VERSION").exists(), "stale VERSION must be removed"


def test_checksum_mismatch_deletes_download_and_fails(box):
    box.fake_uname("Linux", "x86_64")
    box.fake_curl_garbage()
    result = box.run()
    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr
    assert not box.dest.exists(), "corrupt download must be deleted"


def test_failed_download_is_reported_and_cleaned_up(box):
    box.fake_uname("Linux", "x86_64")
    box.fake("curl", "exit 22\n")
    result = box.run()
    assert result.returncode != 0
    assert f"download of OrcaSlicer_Linux_AppImage_Ubuntu2404_V{V}.AppImage failed" in result.stderr
    assert not box.dest.exists()


def test_downloads_the_asset_for_the_platform(box):
    box.fake_uname("Darwin", "arm64")
    box.fake_curl_garbage()
    box.run()
    assert box.calls.read_text().splitlines() == [RELEASE + f"OrcaSlicer_Mac_universal_V{V}.dmg"]
