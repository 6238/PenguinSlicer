"""The daemon runs wherever Python does: every platform-dependent choice with the platform
injected, the whole daemon imported with the Unix-only modules made unimportable, and the
source checked for the calls Windows lacks. Also the `record` command.

No Windows machine is needed: the choices are functions of the platform name, and the
import test hides `pwd`, `grp`, `fcntl`, `termios` and `resource` the way Windows lacks
them."""
import ast
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

import penguin_delivery_daemon
from penguin_delivery_daemon import __main__ as main_mod
from penguin_delivery_daemon import config as cfg
from penguin_delivery_daemon import paths

from daemon_fakes import H2S, FakeClock

PACKAGE = os.path.dirname(os.path.abspath(penguin_delivery_daemon.__file__))
UNIX_ONLY = ('pwd', 'grp', 'fcntl', 'termios', 'resource', 'syslog')


class TestTheHomeDirectory(unittest.TestCase):
    def test_windows_uses_local_app_data(self):
        home = paths.default_home(platform='win32', environ={'LOCALAPPDATA': r'C:\Users\x\AppData\Local'},
                                  expanduser=lambda p: r'C:\Users\x')
        self.assertEqual(home, os.path.join(r'C:\Users\x\AppData\Local', 'PenguinDelivery'))

    def test_windows_without_local_app_data_uses_the_user_folder(self):
        home = paths.default_home(platform='win32', environ={},
                                  expanduser=lambda p: r'C:\Users\x')
        self.assertEqual(home, os.path.join(r'C:\Users\x', 'PenguinDelivery'))

    def test_macos_and_linux_use_a_dot_folder_in_home(self):
        for platform in ('darwin', 'linux', 'freebsd14'):
            self.assertEqual(paths.default_home(platform=platform, environ={},
                                                expanduser=lambda p: '/home/x'),
                             '/home/x/.penguin-delivery')

    def test_everything_lives_in_the_one_home(self):
        home = paths.home_for('/data/pd')
        self.assertEqual((home.config, home.downloads, home.recordings),
                         ('/data/pd/config.toml', '/data/pd/downloads', '/data/pd/recordings'))
        self.assertEqual(paths.home_for(None, '/x/y/c.toml').root, '/x/y')
        self.assertEqual(paths.home_for(None, None, platform='linux', environ={},
                                        expanduser=lambda p: '/h').root, '/h/.penguin-delivery')

    def test_the_commands_resolve_the_home(self):
        args = main_mod.build_parser().parse_args(['run', '--home', '/data/pd'])
        main_mod.resolve_paths(args)
        self.assertEqual((args.config, args.download_dir),
                         ('/data/pd/config.toml', '/data/pd/downloads'))
        args = types.SimpleNamespace(home=None, config='/etc/pd/config.toml')
        main_mod.resolve_paths(args)
        self.assertEqual(args.download_dir, os.path.join(os.path.abspath('/etc/pd'),
                                                         'downloads'))

    def test_the_default_config_path_is_in_the_default_home(self):
        self.assertEqual(cfg.DEFAULT_CONFIG_PATH,
                         os.path.join(paths.default_home(), 'config.toml'))

    def test_every_command_takes_home(self):
        for command in ('pair', 'run', 'status', 'record'):
            args = main_mod.build_parser().parse_args([command, '--home', 'h'])
            self.assertEqual(args.home, 'h')


class TestNothingUnixOnly(unittest.TestCase):
    def test_the_whole_daemon_imports_with_the_unix_only_modules_missing(self):
        """Run in a fresh interpreter, so the hidden modules are hidden from the start."""
        blocked = ', '.join(repr(m) for m in UNIX_ONLY)
        program = (
            'import sys\n'
            f'for name in ({blocked},):\n'
            '    sys.modules[name] = None\n'
            'import importlib, pkgutil, penguin_delivery_daemon as p\n'
            'for m in pkgutil.iter_modules(p.__path__):\n'
            '    importlib.import_module("penguin_delivery_daemon." + m.name)\n'
            'from penguin_delivery_daemon import __main__ as main\n'
            'main.build_parser().parse_args(["run", "--home", "x"])\n'
            'print("ok")\n')
        result = subprocess.run([sys.executable, '-I', '-c', program], capture_output=True,
                                text=True, timeout=60,
                                env={'PYTHONPATH': os.pathsep.join(sys.path)})
        self.assertEqual(result.stdout.strip(), 'ok', result.stderr)

    def test_the_source_uses_nothing_windows_lacks(self):
        forbidden_calls = {('os', 'geteuid'), ('os', 'getuid'), ('os', 'rename'),
                           ('os', 'fork'), ('os', 'killpg'), ('signal', 'SIGHUP'),
                           ('signal', 'SIGKILL'), ('signal', 'SIGUSR1'), ('os', 'getpgid')}
        for name in sorted(os.listdir(PACKAGE)):
            if not name.endswith('.py'):
                continue
            with open(os.path.join(PACKAGE, name), encoding='utf-8') as fh:
                source = fh.read()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    self.assertNotIn((node.value.id, node.attr), forbidden_calls,
                                     f'{name}: {node.value.id}.{node.attr}')
                if isinstance(node, (ast.Import, ast.ImportFrom)) and node.col_offset == 0:
                    roots = ([a.name.split('.')[0] for a in node.names]
                             if isinstance(node, ast.Import)
                             else [(node.module or '').split('.')[0]])
                    for root in roots:
                        self.assertNotIn(root, UNIX_ONLY, f'{name} imports {root} at the top')

    def test_no_unix_path_is_written_into_the_source(self):
        allowed = set()
        for name in sorted(os.listdir(PACKAGE)):
            if not name.endswith('.py'):
                continue
            with open(os.path.join(PACKAGE, name), encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and node.value.startswith(('/etc/', '/var/', '/usr/', '/tmp/'))):
                    self.assertIn((name, node.value), allowed)

    def test_the_config_file_is_replaced_atomically_with_os_replace(self):
        """os.rename fails on Windows when the target exists; os.replace does not."""
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, 'config.toml')
        cfg.save_config(cfg.DaemonConfig(pairing_code='7K3MQ9XW'), path=path)
        cfg.save_config(cfg.DaemonConfig(pairing_code='ABCD2345'), path=path)
        self.assertEqual(cfg.load_config(path).pairing_code, 'ABCD2345')
        self.assertEqual(os.listdir(folder), ['config.toml'])


class FakeLink:
    def __init__(self, reports):
        self.reports = list(reports)
        self.connected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def raw_report(self):
        return self.reports.pop(0) if self.reports else {}


class TestRecord(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        cfg.save_config(cfg.DaemonConfig(printer_ip='10.0.0.42', printer_serial='S',
                                         access_code='87654321', pairing_code='7K3MQ9XW'),
                        path=os.path.join(self.home, 'config.toml'))

    def record(self, reports, seconds=3.0):
        clock = FakeClock()
        out = io.StringIO()
        args = main_mod.build_parser().parse_args(
            ['record', '--home', self.home, '--seconds', str(seconds)])
        link = FakeLink(reports)
        code = main_mod.cmd_record(args, out=out, clock=clock, sleep=clock.sleep, link=link)
        return code, out.getvalue(), link

    def test_each_changed_status_document_is_one_json_line(self):
        code, said, link = self.record([H2S['idle'], H2S['idle'], H2S['running'], {},
                                        H2S['finished']])
        self.assertEqual(code, 0)
        self.assertFalse(link.connected)
        folder = os.path.join(self.home, 'recordings')
        [name] = os.listdir(folder)
        with open(os.path.join(folder, name), encoding='utf-8') as fh:
            lines = [json.loads(line) for line in fh]
        self.assertEqual([line['print']['gcode_state'] for line in lines],
                         ['IDLE', 'RUNNING', 'FINISH'])
        self.assertEqual([line['t'] for line in lines], [0.0, 1.0, 2.0])
        self.assertIn('saved 3 status documents', said)
        self.assertNotIn('87654321', said)

    def test_without_a_config_it_says_to_pair_first(self):
        args = main_mod.build_parser().parse_args(['record', '--home',
                                                   os.path.join(self.home, 'none')])
        out = io.StringIO()
        self.assertEqual(main_mod.cmd_record(args, out=out), 1)
        self.assertIn('run pair first', out.getvalue())

    def test_a_link_that_fails_is_a_message(self):
        class Broken(FakeLink):
            def connect(self):
                raise OSError('no route to host')

        clock = FakeClock()
        out = io.StringIO()
        args = main_mod.build_parser().parse_args(['record', '--home', self.home])
        self.assertEqual(main_mod.cmd_record(args, out=out, clock=clock, sleep=clock.sleep,
                                             link=Broken([])), 1)
        self.assertIn('could not record: no route to host', out.getvalue())

    def test_ctrl_c_stops_it_cleanly(self):
        clock = FakeClock()

        def sleep(seconds):
            raise KeyboardInterrupt

        out = io.StringIO()
        args = main_mod.build_parser().parse_args(['record', '--home', self.home,
                                                   '--out', os.path.join(self.home, 'r.jsonl')])
        self.assertEqual(main_mod.cmd_record(args, out=out, clock=clock, sleep=sleep,
                                             link=FakeLink([H2S['idle']])), 0)
        self.assertIn('saved 1 status documents', out.getvalue())
