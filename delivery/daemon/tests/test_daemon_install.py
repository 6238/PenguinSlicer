"""Static checks on the installer, the package metadata and the hardware smoke script.

The installer cannot be executed here -- it makes users, writes to /opt and /etc, and talks
to apt -- so these tests read it. They exist to catch the mistakes that would only show up
on a Pi in a shop at the worst possible moment.

Ported from the original daemon's test_install_script.py, with the paths of the new
repository. New: the pins in requirements.txt and pyproject.toml must agree, and the
package's version and User-Agent (from the original test_smoke_import.py)."""
import ast
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
import unittest

import penguin_delivery_daemon

DAEMON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(DAEMON, 'install.sh')
PACKAGE = os.path.dirname(os.path.abspath(penguin_delivery_daemon.__file__))

# Left behind by tools, never part of the daemon's source: hidden files and folders
# (.DS_Store, .pytest_cache), compiled files, and editors' swap, backup and lock files.
_NOT_SOURCE_DIRS = {'__pycache__'}
_NOT_SOURCE_SUFFIXES = ('.pyc', '.pyo', '.swp', '.swo', '.swx', '~', '.bak', '.orig', '.tmp')


def _is_source(name):
    return not (name.startswith('.') or name.startswith('#') or name.startswith('~$')
                or name.endswith(_NOT_SOURCE_SUFFIXES))


def files_stating_a_version(folder, versions):
    """(offending, checked): the daemon's source files under `folder` that name one of
    `versions`, and every file looked at, both relative to `folder`. pyproject.toml, the
    one pin, is left out. Files are searched as bytes, never decoded, so a file that is not
    UTF-8 text can neither fail the check nor hide a version from it."""
    needles = [v.encode('ascii') for v in versions]
    offending, checked = [], []
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in _NOT_SOURCE_DIRS and _is_source(d))
        for name in sorted(files):
            path = os.path.join(root, name)
            relative = os.path.relpath(path, folder)
            if relative == 'pyproject.toml' or not _is_source(name):
                continue
            checked.append(relative)
            with open(path, 'rb') as fh:
                data = fh.read()
            if any(needle in data for needle in needles):
                offending.append(relative)
    return offending, checked


class TestInstallScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SCRIPT) as fh:
            cls.text = fh.read()

    def test_it_is_executable(self):
        self.assertTrue(os.stat(SCRIPT).st_mode & stat.S_IXUSR)

    def test_it_parses_as_shell(self):
        """A typo in a heredoc or a quote only shows up on the Pi otherwise."""
        bash = shutil.which('bash')
        if not bash:
            self.skipTest('bash is not installed')
        result = subprocess.run([bash, '-n', SCRIPT], capture_output=True, text=True,
                                timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_it_fails_fast(self):
        self.assertIn('set -euo pipefail', self.text)

    def test_the_placeholders_are_guarded(self):
        """Nothing is pinned yet. The guard is what stops a half-finished installer from
        downloading a tarball named REPLACE_BEFORE_MERGE."""
        self.assertIn('DAEMON_SHA="REPLACE_BEFORE_MERGE"', self.text)
        self.assertIn('SOURCE_REPOSITORY="REPLACE_BEFORE_MERGE"', self.text)
        self.assertRegex(self.text, r'if\s+\[\s+"\$DAEMON_SHA"\s+=\s+"REPLACE_BEFORE_MERGE"')
        self.assertRegex(self.text, r'\[\s+"\$SOURCE_REPOSITORY"\s+=\s+"REPLACE_BEFORE_MERGE"')

    def test_it_requires_a_64_bit_userland(self):
        """There is no 32-bit Pillow wheel on PyPI, so an armv7l install would try to build
        it from source and fail after a long wait. The userland is tested, not the kernel:
        a 32-bit OS on a Pi 4 reports `uname -m` as armv8l."""
        self.assertIn('ARCH="$(dpkg --print-architecture)"', self.text)
        self.assertIn('"$ARCH" != "arm64"', self.text)
        self.assertNotIn('$(uname', self.text)

    def test_it_installs_wheels_only_into_a_venv(self):
        self.assertIn('--only-binary=:all:', self.text)
        self.assertIn('python3-venv', self.text)
        self.assertIn('-r "$REQUIREMENTS"', self.text)

    def test_the_pins_are_read_from_pyproject_toml_and_nowhere_else(self):
        self.assertIn("'*/delivery/daemon/pyproject.toml'", self.text)
        self.assertIn('["project"]["dependencies"]', self.text)
        self.assertNotRegex(self.text, r'==\d')            # no version written here
        self.assertNotIn('requirements.txt', self.text)

    def test_it_downloads_the_pinned_commit_and_extracts_only_the_daemon_package(self):
        self.assertIn('https://github.com/$SOURCE_REPOSITORY/archive/$DAEMON_SHA.tar.gz',
                      self.text)
        # Three levels: <repository>-<sha>, delivery and daemon, so the package lands at
        # $APP_DIR/penguin_delivery_daemon and `python -m penguin_delivery_daemon` works.
        self.assertIn("--strip-components=3 \\\n  '*/delivery/daemon/penguin_delivery_daemon/*'",
                      self.text)

    def test_the_wrapper_runs_the_package_out_of_the_venv(self):
        self.assertIn('exec env PYTHONPATH="$APP_DIR" "$VENV_DIR/bin/python" -m '
                      'penguin_delivery_daemon', self.text)

    def test_an_upgrade_removes_the_code_of_an_install_made_before_the_port(self):
        self.assertIn('rm -rf "${APP_DIR:?}/printer_daemon"', self.text)

    def test_it_creates_the_service_user_and_enables_without_starting(self):
        self.assertIn('useradd --system', self.text)
        self.assertIn('SERVICE_USER="penguincam"', self.text)
        self.assertIn('systemctl enable', self.text)
        self.assertNotIn('systemctl start', self.text)

    def test_the_unit_restarts_always(self):
        self.assertIn('Restart=always', self.text)
        self.assertIn('ExecStart=$WRAPPER run', self.text)

    def test_pair_is_run_with_stdin_from_the_tty(self):
        """The script itself arrived on standard input from the curl pipe, so pair would
        read the rest of the script as its answers without this."""
        self.assertRegex(self.text, r'pair\s*<\s*/dev/tty')

    def test_the_config_directory_is_handed_to_the_service_user_after_pairing(self):
        match = re.search(r'pair\s*<\s*/dev/tty', self.text)
        self.assertIsNotNone(match)
        self.assertRegex(self.text[match.start():],
                         r'chown[^\n]*"\$SERVICE_USER:\$SERVICE_USER"[^\n]*\$CONFIG_DIR')

    def test_the_unit_is_hardened(self):
        for directive in ('NoNewPrivileges=true', 'ProtectSystem=strict',
                          'ProtectHome=true', 'PrivateTmp=true'):
            self.assertIn(directive, self.text)
        match = re.search(r'^ReadWritePaths=(.+)$', self.text, re.MULTILINE)
        self.assertIsNotNone(match, 'the unit grants no writable path')
        self.assertEqual(match.group(1), '$CONFIG_DIR -$DOWNLOAD_DIR')

    def test_the_service_user_does_not_own_its_own_code(self):
        self.assertNotRegex(self.text,
                            r'chown[^\n]*"\$SERVICE_USER:\$SERVICE_USER"[^\n]*INSTALL_DIR')

    def test_the_download_directory_matches_the_daemon_and_is_private(self):
        from penguin_delivery_daemon import __main__ as main_mod
        self.assertIn(f'DOWNLOAD_DIR="{main_mod.DOWNLOAD_DIR}"', self.text)
        self.assertRegex(self.text, r'chown\s+"\$SERVICE_USER:\$SERVICE_USER"\s+"\$DOWNLOAD_DIR"')
        self.assertRegex(self.text, r'chmod\s+700\s+"\$DOWNLOAD_DIR"')

    def test_the_config_directory_matches_the_daemon(self):
        from penguin_delivery_daemon import config as cfg
        self.assertIn(f'CONFIG_DIR="{os.path.dirname(cfg.DEFAULT_CONFIG_PATH)}"', self.text)

    def test_the_documented_command_is_a_github_raw_url_with_dash_f(self):
        self.assertIn('curl -fsSL https://raw.githubusercontent.com/', self.text)
        self.assertIn('/delivery/daemon/install.sh | sudo bash', self.text)

    def test_it_never_passes_dev(self):
        """A shop install must not be able to talk plain HTTP."""
        self.assertNotIn('--dev', self.text)

    def test_it_contains_no_secret(self):
        self.assertNotRegex(self.text, r'(?i)(api[_-]?key|password|secret|token)\s*=')


class TestPackageMetadata(unittest.TestCase):
    def test_every_dependency_is_pinned_exactly_in_pyproject(self):
        """daemon/pyproject.toml is the one place an upstream version is stated."""
        with open(os.path.join(DAEMON, 'pyproject.toml'), 'rb') as fh:
            declared = tomllib.load(fh)['project']['dependencies']
        self.assertEqual(sorted(d.split('==')[0] for d in declared),
                         ['bambulabs_api', 'paho-mqtt', 'pillow', 'requests', 'tomli-w'])
        for dependency in declared:
            self.assertRegex(dependency, r'^[A-Za-z0-9_.-]+==\d+(\.\d+)*$')

    def test_no_other_file_of_the_daemon_states_an_upstream_version(self):
        """Every file of the daemon's source, fixtures included: a fixture that names a
        version goes stale on the next upgrade without anything failing."""
        with open(os.path.join(DAEMON, 'pyproject.toml'), 'rb') as fh:
            pins = tomllib.load(fh)['project']['dependencies']
        versions = [p.split('==')[1] for p in pins]
        offending, checked = files_stating_a_version(DAEMON, versions)
        self.assertEqual(offending, [])
        self.assertIn(os.path.join('tests', 'fixtures', 'h2s_status.json'), checked)
        self.assertIn(os.path.join('penguin_delivery_daemon', 'printer.py'), checked)

    def test_a_stray_binary_or_editor_file_neither_fails_nor_hides_the_check(self):
        """A macOS .DS_Store, an editor's swap file or a backup is not the daemon's source:
        it is skipped, whatever bytes it holds. A file that IS source but not UTF-8 text is
        searched as bytes, so it can neither fail the check by not decoding nor hide a
        version by being binary."""
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(DAEMON, os.path.join(folder, 'daemon'),
                            ignore=shutil.ignore_patterns('__pycache__'))
            copy = os.path.join(folder, 'daemon')
            # Built here so this very file does not name it.
            probe = '.'.join(['97', '31', '53'])
            stray = b'\x00\x00\x00\x01Bud1\xff\xfe ' + probe.encode() + b' \x80'
            for name in ('.DS_Store', os.path.join('tests', '.test_x.py.swp'),
                         os.path.join('penguin_delivery_daemon', 'run_loop.py~'),
                         os.path.join('tests', '#scratch#')):
                with open(os.path.join(copy, name), 'wb') as fh:
                    fh.write(stray)
            self.assertEqual(files_stating_a_version(copy, [probe])[0], [])
            # A binary that is part of the source and names the version is still caught.
            with open(os.path.join(copy, 'tests', 'fixtures', 'capture.bin'), 'wb') as fh:
                fh.write(stray)
            self.assertEqual(files_stating_a_version(copy, [probe])[0],
                             [os.path.join('tests', 'fixtures', 'capture.bin')])

    def test_only_printer_py_talks_to_the_printer_library(self):
        """The seam: a change in bambulabs_api is absorbed in printer.py alone."""
        for name in sorted(os.listdir(PACKAGE)):
            if not name.endswith('.py') or name == 'printer.py':
                continue
            with open(os.path.join(PACKAGE, name), encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertNotIn('bambulabs_api', [a.name for a in node.names], name)
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotEqual((node.module or '').split('.')[0], 'bambulabs_api',
                                        name)

    def test_the_versions_agree(self):
        with open(os.path.join(DAEMON, 'pyproject.toml'), 'rb') as fh:
            self.assertEqual(tomllib.load(fh)['project']['version'],
                             penguin_delivery_daemon.VERSION)

    def test_the_user_agent_names_the_version(self):
        self.assertEqual(penguin_delivery_daemon.USER_AGENT,
                         f'penguincam-printer/{penguin_delivery_daemon.VERSION}')

    def test_the_daemon_imports_only_itself_the_standard_library_and_its_pins(self):
        """It runs on a Pi where nothing else is installed: never the relay, never Flask."""
        allowed = {'penguin_delivery_daemon', 'requests', 'tomli_w', 'bambulabs_api'}
        for name in sorted(os.listdir(PACKAGE)):
            if not name.endswith('.py'):
                continue
            with open(os.path.join(PACKAGE, name), encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split('.')[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    roots = [node.module.split('.')[0]]
                else:
                    continue
                for root in roots:
                    self.assertTrue(root in allowed or root in sys.stdlib_module_names,
                                    f'{name} imports {root}')
