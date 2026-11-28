"""scripts/upgrade_orca.py, the command that moves the Orca pin, with a recorded release
and stand-ins for the install, the regeneration and the upstream check (no network)."""
import io
import json
import re
from pathlib import Path

import pytest

from helpers import INSTALL_ORCA
from upgrade_orca import ASSETS, UpgradeError, check_patches, digests, fetch_release, main, repin, upgrade

SHAS = {"SHA_LINUX_X86_64": "1" * 64, "SHA_LINUX_AARCH64": "2" * 64, "SHA_MACOS": "3" * 64}


def release(version="2.5.1", **drop):
    assets = [{"name": pattern.format(version=version), "digest": f"sha256:{SHAS[line]}"}
              for line, pattern in ASSETS.items() if line not in drop]
    return {"tag_name": f"v{version}", "assets": assets + [{"name": "OrcaSlicer_Windows.zip"}, "junk"]}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def opener_for(body, seen=None):
    def opener(request):
        if seen is not None:
            seen.append(request)
        if isinstance(body, Exception):
            raise body
        return Response(json.dumps(body).encode())
    return opener


def test_digests_come_from_githubs_own_digest_of_each_asset():
    assert digests(release(), "2.5.1") == SHAS


def test_a_missing_asset_stops_the_upgrade():
    with pytest.raises(UpgradeError, match="has no asset OrcaSlicer_Mac_universal_V2.5.1.dmg"):
        digests(release(SHA_MACOS=True), "2.5.1")


def test_an_asset_without_a_digest_stops_the_upgrade():
    body = release()
    body["assets"][0]["digest"] = None
    with pytest.raises(UpgradeError, match="no SHA-256 digest"):
        digests(body, "2.5.1")


def test_the_token_is_sent_and_a_failure_is_explained():
    seen = []
    assert fetch_release("2.5.1", "fake-token", opener_for(release(), seen))["tag_name"] == "v2.5.1"
    assert seen[0].get_header("Authorization") == "Bearer fake-token"
    assert seen[0].full_url.endswith("/releases/tags/v2.5.1")
    with pytest.raises(UpgradeError, match="could not read release v9.9.9"):
        fetch_release("9.9.9", None, opener_for(OSError("no network")))


def test_repin_rewrites_the_four_lines_of_the_real_installer():
    text = repin(INSTALL_ORCA.read_text(), "2.5.1", SHAS)
    assert 'ORCA_VERSION="2.5.1"' in text and f'SHA_MACOS="{"3" * 64}"' in text
    assert text.count("ORCA_VERSION=") == 1


def test_repin_refuses_an_installer_without_its_pin():
    with pytest.raises(UpgradeError, match="has 0 ORCA_VERSION lines"):
        repin("#!/bin/sh\n", "2.5.1", SHAS)


def test_a_patch_stops_the_upgrade(tmp_path):
    check_patches(tmp_path / "none")
    (tmp_path / "2.4.2-warnings.patch").write_text("--- a\n+++ b\n")
    with pytest.raises(UpgradeError, match="1 patch"):
        check_patches(tmp_path)


class Installs:
    """A stand-in runner: the install writes a VERSION into PENGUIN_SLICE_ORCA_DEST (the
    pin it was handed, read from the staged script), or fails at the step named `fail`."""

    def __init__(self, fail=None):
        self.steps, self.fail, self.staged = [], fail, []

    def __call__(self, step, cmd, env=None):
        self.steps.append(step)
        if step.startswith("install"):
            self.staged.append(Path(cmd[0]).read_text())
            if self.fail != "install":
                dest = Path(env["PENGUIN_SLICE_ORCA_DEST"])
                dest.mkdir(parents=True)
                (dest / "VERSION").write_text(re.search(r'ORCA_VERSION="([^"]+)"', self.staged[-1]).group(1))
        if step == self.fail or (self.fail == "install" and step.startswith("install")):
            raise UpgradeError(f"{step} failed (exit 1)")


@pytest.fixture
def tree(tmp_path):
    """An installer pinned at 2.4.2 and an installed Orca 2.4.2."""
    (tmp_path / "scripts").mkdir()
    install = tmp_path / "scripts" / "install-orca.sh"
    install.write_text(INSTALL_ORCA.read_text())
    (tmp_path / "tools" / "orca").mkdir(parents=True)
    (tmp_path / "tools" / "orca" / "VERSION").write_text("2.4.2")
    return tmp_path, install


SOURCE_SHA = "4" * 64


def fetches_source(fail=False):
    """A stand-in for fetching the source: writes a VERSION into the folder it is given and
    answers the archive's checksum, or fails."""
    def fetcher(version, dest):
        dest.mkdir(parents=True)
        (dest / "VERSION").write_text(version)
        if fail:
            raise UpgradeError("download of the archive failed: OSError: no network")
        return SOURCE_SHA
    return fetcher


def run_upgrade(tree, runner, source_fetcher=None):
    root, install = tree
    upgrade("2.5.1", opener=opener_for(release()), runner=runner, install=install, patches=root / "patches",
            tools=root / "tools", source_fetcher=source_fetcher or fetches_source())


def test_upgrade_installs_beside_then_pins_regenerates_and_checks(tree):
    root, install = tree
    runner = Installs()
    run_upgrade(tree, runner)
    assert runner.steps == ["install beside the current Orca", "regenerate profiles and catalog",
                            "regenerate the table of settings", "upstream check"]
    assert 'ORCA_VERSION="2.5.1"' in runner.staged[0]           # the install got the new pin
    assert 'ORCA_VERSION="2.5.1"' in install.read_text()
    assert f'SHA_SOURCE="{SOURCE_SHA}"' in install.read_text()       # the source's checksum, as downloaded
    assert (root / "tools" / "orca" / "VERSION").read_text() == "2.5.1"
    assert (root / "tools" / "orca-source" / "VERSION").read_text() == "2.5.1"
    assert sorted(p.name for p in (root / "tools").iterdir()) == ["orca", "orca-source"]   # nothing previous or next
    assert sorted(p.name for p in install.parent.iterdir()) == ["install-orca.sh"]     # no staged script left


def test_a_failed_download_changes_nothing(tree):
    # Once the pin was moved first and tools/orca removed, so a failure left no Orca.
    root, install = tree
    before = install.read_text()
    with pytest.raises(UpgradeError, match=r"the install of 2.5.1 failed; nothing was changed \(the pin is still "
                                           r"2.4.2"):
        run_upgrade(tree, Installs(fail="install"))
    assert install.read_text() == before
    assert (root / "tools" / "orca" / "VERSION").read_text() == "2.4.2"
    assert sorted(p.name for p in (root / "tools").iterdir()) == ["orca"]
    assert sorted(p.name for p in install.parent.iterdir()) == ["install-orca.sh"]


def test_a_failed_fetch_of_the_source_changes_nothing(tree):
    root, install = tree
    before = install.read_text()
    runner = Installs()
    with pytest.raises(UpgradeError, match=r"the source of 2.5.1 could not be fetched \(download of the archive "
                                           r"failed.*\); nothing was changed \(the pin is still 2.4.2\)"):
        run_upgrade(tree, runner, fetches_source(fail=True))
    assert runner.steps == [] and install.read_text() == before
    assert sorted(p.name for p in (root / "tools").iterdir()) == ["orca"]


def test_the_real_fetcher_reports_its_failure_as_the_upgrades(tmp_path, monkeypatch):
    import fetch_orca_source
    import upgrade_orca

    def fails(version, sha, dest, cache=None):
        raise fetch_orca_source.FetchError("checksum mismatch")
    monkeypatch.setattr(fetch_orca_source, "fetch", fails)
    with pytest.raises(UpgradeError, match="checksum mismatch"):
        upgrade_orca.fetch_source("2.5.1", tmp_path / "s")


@pytest.mark.parametrize("step", ["regenerate profiles and catalog", "regenerate the table of settings",
                                  "upstream check"])
def test_a_failed_check_after_the_swap_says_how_to_go_back(tree, step):
    root, install = tree
    with pytest.raises(UpgradeError, match=rf"{step} failed \(exit 1\)\. Orca 2.5.1 is installed and pinned; 2.4.2 "
                                           r"is kept at .*orca.previous\. Each failing test of the upstream check "
                                           r"names.*what to fix \(for Orca's debug log: slicer.LOG_WARNING_RE and "
                                           r"tests/fake_orca.py's LOG_WARNING\); the table's generator names each "
                                           r"new setting to classify in src/penguin_slice/settings/"
                                           r"classification.json\. To go back: make upgrade-orca VERSION=2.4.2"):
        run_upgrade(tree, Installs(fail=step))
    assert (root / "tools" / "orca.previous" / "VERSION").read_text() == "2.4.2"
    assert (root / "tools" / "orca" / "VERSION").read_text() == "2.5.1"


def test_a_first_install_has_nothing_to_keep(tree):
    root, _install = tree
    (root / "tools" / "orca" / "VERSION").unlink()
    (root / "tools" / "orca").rmdir()
    run_upgrade(tree, Installs())
    assert (root / "tools" / "orca" / "VERSION").read_text() == "2.5.1"


def test_the_old_version_is_named_even_without_a_pin_line():
    from upgrade_orca import pinned_version
    assert pinned_version('ORCA_VERSION="2.4.2"\n') == "2.4.2"
    assert pinned_version("#!/bin/sh\n") == "the previous version"


def test_nothing_changes_when_the_release_cannot_be_read(tmp_path):
    install = tmp_path / "install-orca.sh"
    install.write_text(INSTALL_ORCA.read_text())
    before = install.read_text()
    with pytest.raises(UpgradeError):
        upgrade("2.5.1", opener=opener_for(release(SHA_LINUX_AARCH64=True)), runner=None, install=install)
    assert install.read_text() == before


def test_a_version_that_is_not_one(tmp_path):
    with pytest.raises(UpgradeError, match="is not a version"):
        upgrade("latest; rm -rf /", opener=None)


def test_a_failing_step_stops_with_its_name(monkeypatch):
    import upgrade_orca

    class Done:
        returncode = 3
    monkeypatch.setattr(upgrade_orca.subprocess, "run", lambda cmd, env=None: Done())
    with pytest.raises(UpgradeError, match=r"install failed \(exit 3\)"):
        upgrade_orca.run("install", ["x"])


def test_main_reports_a_failure_on_stderr(capsys):
    assert main(["not-a-version"]) == 1
    assert "upgrade-orca: 'not-a-version' is not a version" in capsys.readouterr().err
