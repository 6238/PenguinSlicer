#!/usr/bin/env python3
"""Move the Orca Slicer pin to another release: `make upgrade-orca VERSION=x.y.z`.

1. Reads the release from GitHub's API and takes the SHA-256 digest GitHub computed for
   each of the three assets scripts/install-orca.sh installs (Linux x86_64, Linux aarch64,
   macOS); a release missing an asset or a digest stops here, nothing changed.
2. Stops when patches/orca/ holds a patch: patching Orca means building it from source,
   which this command does not do, and a patch to Orca is the owner's decision.
3. Installs that release beside the installed one, in tools/orca.next, with a staged copy
   of scripts/install-orca.sh holding the new pin (it verifies the download against it); a
   failure here changes nothing.
4. Rewrites the pin, ORCA_VERSION and the three SHA_ lines of scripts/install-orca.sh,
   the one place the version is stated; moves tools/orca to tools/orca.previous and
   tools/orca.next to tools/orca; regenerates the profiles and the catalog from the new
   Orca's own profiles (scripts/flatten_orca_profiles.py), and runs the upstream check
   (make test-upstream). When that passes, tools/orca.previous is removed; when it fails,
   the message says how to go back.

Every step prints what it did; the first that fails stops the command with its reason.
The regenerated files are left for review (see slice/README.md, "Taking a new upstream
version"); nothing is committed.

Standard library only. GH_TOKEN, when set, is sent to GitHub to lift the rate limit; it is
never printed.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

SLICE_ROOT = Path(__file__).resolve().parents[1]
INSTALL = SLICE_ROOT / "scripts" / "install-orca.sh"
FLATTEN = SLICE_ROOT / "scripts" / "flatten_orca_profiles.py"
PATCHES = SLICE_ROOT / "patches" / "orca"
TOOLS = SLICE_ROOT / "tools"
STAGED_INSTALL = ".install-orca.next.sh"
API = "https://api.github.com/repos/OrcaSlicer/OrcaSlicer/releases/tags/v{version}"
# pin line -> the asset's name, as scripts/install-orca.sh names them.
ASSETS = {
    "SHA_LINUX_X86_64": "OrcaSlicer_Linux_AppImage_Ubuntu2404_V{version}.AppImage",
    "SHA_LINUX_AARCH64": "OrcaSlicer_Linux_AppImage_Ubuntu2404_aarch64_V{version}.AppImage",
    "SHA_MACOS": "OrcaSlicer_Mac_universal_V{version}.dmg",
}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[A-Za-z0-9.]+)?\Z")


class UpgradeError(Exception):
    """A step that cannot go on; its message says why."""


def fetch_release(version, token=None, opener=urllib.request.urlopen):
    request = urllib.request.Request(API.format(version=version), headers={"Accept": "application/vnd.github+json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with opener(request) as response:
            return json.load(response)
    except Exception as exc:          # HTTP 404, no network, not JSON: all stop the upgrade
        raise UpgradeError(f"could not read release v{version} from GitHub: {type(exc).__name__}: {exc}") from None


def digests(release, version):
    """{pin line: sha256} for the three assets, from GitHub's own digests."""
    by_name = {asset.get("name"): asset for asset in release.get("assets", []) if isinstance(asset, dict)}
    found = {}
    for line, pattern in ASSETS.items():
        name = pattern.format(version=version)
        asset = by_name.get(name)
        if asset is None:
            raise UpgradeError(f"release v{version} has no asset {name}")
        digest = asset.get("digest") or ""
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise UpgradeError(f"GitHub gives no SHA-256 digest for {name}; verify it by hand before pinning")
        found[line] = digest.split(":", 1)[1]
    return found


def check_patches(directory=PATCHES):
    patches = sorted(directory.glob("*.patch")) if directory.is_dir() else []
    if patches:
        raise UpgradeError(f"{len(patches)} patch(es) in {directory}: patching Orca needs a source build, which "
                           f"this command does not do, and a patch to Orca is the owner's decision (slice/README.md, "
                           f"\"Taking a new upstream version\")")


def repin(text, version, shas):
    """install-orca.sh's text with the new ORCA_VERSION and SHA_ lines."""
    lines = {"ORCA_VERSION": version, **shas}
    for name, value in lines.items():
        text, count = re.subn(rf'^{name}="[^"]*"$', f'{name}="{value}"', text, flags=re.M)
        if count != 1:
            raise UpgradeError(f"{INSTALL.name} has {count} {name} lines, not one")
    return text


def run(step, cmd, env=None):
    print(f"upgrade-orca: {step}: {' '.join(str(c) for c in cmd)}", flush=True)
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise UpgradeError(f"{step} failed (exit {result.returncode})")


def pinned_version(text):
    match = re.search(r'^ORCA_VERSION="([^"]*)"$', text, re.M)
    return match.group(1) if match else "the previous version"


def upgrade(version, *, token=None, opener=urllib.request.urlopen, runner=run, install=INSTALL,
            patches=PATCHES, tools=TOOLS):
    """Steps 1 to 4 of the module's description. The new release is installed and verified
    beside the installed one (tools/orca.next, by a staged copy of install-orca.sh holding
    the new pin) before anything is replaced: a failed download or checksum leaves the pin
    and tools/orca as they were. Only then is the pin moved and tools/orca swapped, the old
    one kept as tools/orca.previous until the upstream check has passed."""
    if not VERSION_RE.fullmatch(version):
        raise UpgradeError(f"{version!r} is not a version such as 2.5.1")
    shas = digests(fetch_release(version, token, opener), version)
    print(f"upgrade-orca: release v{version}: " + ", ".join(f"{k} {v[:12]}..." for k, v in shas.items()))
    check_patches(patches)
    old_text = install.read_text()
    new_text = repin(old_text, version, shas)
    old_version = pinned_version(old_text)
    staged = install.with_name(STAGED_INSTALL)       # beside it: the script finds slice/ from its own place
    current, following, previous = tools / "orca", tools / "orca.next", tools / "orca.previous"
    staged.write_text(new_text)
    staged.chmod(0o755)
    try:
        runner("install beside the current Orca", [str(staged)],
               env=dict(os.environ, PENGUIN_SLICE_ORCA_DEST=str(following)))
    except UpgradeError:
        shutil.rmtree(following, ignore_errors=True)
        raise UpgradeError(f"the install of {version} failed; nothing was changed (the pin is still "
                           f"{old_version} and {current} is untouched)") from None
    finally:
        staged.unlink(missing_ok=True)
    install.write_text(new_text)
    shutil.rmtree(previous, ignore_errors=True)
    if current.exists():
        current.rename(previous)
    following.rename(current)
    print(f"upgrade-orca: pinned {version} in {install}; Orca {version} at {current}, {old_version} kept at "
          f"{previous}")
    try:
        runner("regenerate profiles and catalog", [sys.executable, str(FLATTEN)])
        runner("upstream check", ["make", "-C", str(SLICE_ROOT), "test-upstream"])
    except UpgradeError as exc:
        raise UpgradeError(f"{exc}. Orca {version} is installed and pinned; {old_version} is kept at {previous}. "
                           f"Each failing test of the upstream check names, in its \"Protects:\" line and its "
                           f"message, the assumption that broke and what to fix (for Orca's debug log: "
                           f"slicer.LOG_WARNING_RE and tests/fake_orca.py's LOG_WARNING). To go back: make "
                           f"upgrade-orca VERSION={old_version}") from None
    shutil.rmtree(previous, ignore_errors=True)
    print(f"upgrade-orca: Orca {version} pinned, installed, regenerated and checked; review the diff of "
          f"src/penguin_slice/profiles/ before committing")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="the Orca Slicer release, for example 2.5.1")
    args = parser.parse_args(argv)
    try:
        upgrade(args.version, token=os.environ.get("GH_TOKEN"))
    except UpgradeError as exc:
        print(f"upgrade-orca: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
