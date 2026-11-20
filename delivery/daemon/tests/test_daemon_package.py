"""Static checks on the daemon's package: its one pin of its dependencies, its version and
User-Agent, and what it may import."""
import ast
import os
import shutil
import sys
import tomllib
import unittest

import penguin_delivery_daemon

DAEMON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        """It runs on the daemon's computer, where nothing else is installed: never the relay,
        never Flask."""
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
