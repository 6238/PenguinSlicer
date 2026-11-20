"""Move the printer library's one pin and check the new version: `make upgrade-printer-library
VERSION=x.y.z`.

1. Writes `bambulabs_api==<VERSION>` in daemon/pyproject.toml, the one place it is stated.
2. Re-locks (`uv lock --upgrade-package bambulabs_api`) and installs (`uv sync`).
3. Looks for patches kept for the library (daemon/patches/bambulabs_api/<version>/). There
   are none today, and none is needed (see the guide). Any patch found stops the upgrade
   with a message, so a patch is never silently dropped or silently not applied.
4. Runs the upstream check (`make test-upstream`): the installed library's behaviour that
   the daemon relies on, and the daemon against the simulated printer.

It prints what changed in uv.lock for the library and what it pulls in. When the check
fails, the pin stays moved so the failure can be read; `make upgrade-printer-library
VERSION=<the old one>` moves it back.
"""

import os
import re
import subprocess
import sys

DELIVERY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT = os.path.join(DELIVERY, 'daemon', 'pyproject.toml')
PATCHES = os.path.join(DELIVERY, 'daemon', 'patches', 'bambulabs_api')
PIN_RE = re.compile(r'"bambulabs_api==([0-9][0-9A-Za-z.]*)"')
#: The library's own dependencies, pinned beside it to what the upstream check ran on.
FOLLOWERS = ('paho-mqtt', 'pillow')


def _follower_re(name):
    return re.compile(rf'"{re.escape(name)}(==[0-9][0-9A-Za-z.]*)?"')


def float_followers(text):
    """The followers' pins taken off, so the lock may move them if the library needs it."""
    for name in FOLLOWERS:
        text = _follower_re(name).sub(f'"{name}"', text, count=1)
    return text


def pin_followers(text, versions):
    """The followers pinned to `versions` ({name: version}, as uv.lock resolved them)."""
    for name in FOLLOWERS:
        if versions.get(name):
            text = _follower_re(name).sub(f'"{name}=={versions[name]}"', text, count=1)
    return text


def current_pin(text):
    match = PIN_RE.search(text)
    if not match:
        raise SystemExit(f'no bambulabs_api pin found in {PYPROJECT}')
    return match.group(1)


def move_pin(text, version):
    return PIN_RE.sub(f'"bambulabs_api=={version}"', text, count=1)


def patches_for(version, folder=PATCHES):
    """(the patches kept for `version`, the versions that have patches)."""
    if not os.path.isdir(folder):
        return [], []
    versions = sorted(name for name in os.listdir(folder)
                      if os.path.isdir(os.path.join(folder, name)))
    mine = os.path.join(folder, version)
    patches = sorted(os.listdir(mine)) if os.path.isdir(mine) else []
    return [p for p in patches if p.endswith('.patch')], versions


def locked_versions():
    """{package: version} for the library and what it pulls in, from uv.lock."""
    with open(os.path.join(DELIVERY, 'uv.lock'), encoding='utf-8') as fh:
        text = fh.read()
    found = {}
    for name in ('bambulabs-api', 'paho-mqtt', 'pillow'):
        match = re.search(rf'name = "{name}"\nversion = "([^"]+)"', text)
        found[name] = match.group(1) if match else None
    return found


def run(command):
    print('$', ' '.join(command), flush=True)
    return subprocess.run(command, cwd=DELIVERY).returncode


def main(argv):
    if len(argv) != 1 or not re.fullmatch(r'[0-9][0-9A-Za-z.]*', argv[0]):
        print('usage: upgrade_printer_library.py VERSION')
        return 2
    version = argv[0]
    with open(PYPROJECT, encoding='utf-8') as fh:
        text = fh.read()
    old = current_pin(text)
    patches, patched_versions = patches_for(version)
    stale = [v for v in patched_versions if v != version]
    if stale:
        print(f'patches are kept for bambulabs_api {", ".join(stale)} but not for {version}: '
              f'carry each one over to daemon/patches/bambulabs_api/{version}/ (or drop it, '
              'saying why in its note) before upgrading')
        return 3
    before = locked_versions()
    with open(PYPROJECT, 'w', encoding='utf-8') as fh:
        fh.write(float_followers(move_pin(text, version)))
    print(f'bambulabs_api pin: {old} -> {version}')
    lock = ['uv', 'lock', '--project', DELIVERY, '--upgrade-package', 'bambulabs_api']
    if run(lock) != 0:
        print('the new version could not be locked; the pin is moved, move it back with '
              f'VERSION={old}')
        return 4
    after = locked_versions()
    # Pin the library's own dependencies to what was resolved, so pip on the shop computer
    # installs exactly the set the upstream check runs on; re-lock to record the pins.
    with open(PYPROJECT, encoding='utf-8') as fh:
        moved = fh.read()
    with open(PYPROJECT, 'w', encoding='utf-8') as fh:
        fh.write(pin_followers(moved, after))
    for command in (['uv', 'lock', '--project', DELIVERY],
                    ['uv', 'sync', '--project', DELIVERY]):
        if run(command) != 0:
            print('the new version could not be locked or installed; the pin is moved, move '
                  f'it back with VERSION={old}')
            return 4
    for name in before:
        if before[name] != after[name]:
            print(f'uv.lock: {name} {before[name]} -> {after[name]}')
    if patches:
        # No patch is needed today, so applying one is not built: the first patch kept
        # must come with the step that applies it.
        print(f'patches are kept for {version} ({", ".join(patches)}), and this command '
              'does not apply patches yet: add that step before relying on the check')
        return 5
    status = run(['make', '-C', DELIVERY, 'test-upstream'])
    print('upstream check: ' + ('passed' if status == 0 else
                                'FAILED: read the first line of each failing test, which names '
                                'the assumption that broke'))
    return status


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
