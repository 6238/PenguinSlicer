"""The commands. Everything that touches a network, a printer or a clock is injected, so
the whole suite runs in milliseconds.

Ported from the original daemon's test_main.py. Rewritten: `run` and `status` were driven
with mock.Mock relay clients, so "posts no snapshot" was an assertion about a mock; they now
use the shared FakeRelay, and the assertions are about what was sent. New: the command
dispatch in main(), run's last-resort error paths, a download directory left too open by
an older install, and status for a printer link that raises."""
import io
import os
import shutil
import signal
import stat
import tempfile
import unittest
from unittest import mock

from penguin_delivery_daemon import __main__ as main_mod
from penguin_delivery_daemon import config as cfg
from penguin_delivery_daemon import run_loop as rl
from penguin_delivery_daemon.relay_client import ChallengeDetected, RelayError

from daemon_fakes import FakeClock, FakeRelay


class TestCodeGeneration(unittest.TestCase):
    def test_the_alphabet_is_crockford_without_lookalikes(self):
        """The daemon must not import the relay (it is not installed beside it), so the
        alphabet lives in two places; delivery/tests pins the two copies together."""
        self.assertEqual(main_mod.ALPHABET, '0123456789ABCDEFGHJKMNPQRSTVWXYZ')

    def test_codes_are_eight_symbols_and_never_all_digits(self):
        for _ in range(300):
            code = main_mod.generate_pairing_code()
            self.assertEqual(len(code), 8)
            self.assertFalse(code.isdigit())
            for ch in code:
                self.assertIn(ch, main_mod.ALPHABET)

    def test_an_all_digit_draw_is_redrawn(self):
        """An all-digit code would load out of an unquoted YAML value as an int."""
        draws = list('01234567') + list('ABCDEFGH')
        with mock.patch.object(main_mod.secrets, 'choice',
                               lambda alphabet: draws.pop(0)):
            self.assertEqual(main_mod.generate_pairing_code(), 'ABCDEFGH')
        self.assertEqual(draws, [])

    def test_display_form(self):
        self.assertEqual(main_mod.format_pairing_code('7K3MQ9XW'), '7K3M-Q9XW')


class FakePrinterLink:
    """Stands in for printer.PrinterLink."""

    instances = []

    def __init__(self, ip, serial, access_code, **kwargs):
        self.ip, self.serial, self.access_code = ip, serial, access_code
        self.kwargs = kwargs
        self.connected = False
        self.connects = 0
        self.disconnects = 0
        self.snapshots = [{'state': 'idle', 'file': '', 'percent': None,
                           'remaining_min': None, 'layer': 0, 'layers': 0, 'error': None,
                           'printer': {'model': 'H2S', 'name': 'Shop H2S',
                                       'serial': serial}}]
        FakePrinterLink.instances.append(self)

    def connect(self):
        self.connected = True
        self.connects += 1

    def disconnect(self):
        self.connected = False
        self.disconnects += 1

    def snapshot(self):
        return self.snapshots[-1]


class SilentPrinterLink(FakePrinterLink):
    """A printer that never reports: wrong access code, or Developer Mode off."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.snapshots = [{'state': 'unreachable', 'file': '', 'percent': None,
                           'remaining_min': None, 'layer': 0, 'layers': 0,
                           'error': None, 'printer': {'model': None, 'name': None,
                                                      'serial': None}}]


class PairTestCase(unittest.TestCase):
    def setUp(self):
        FakePrinterLink.instances = []
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = os.path.join(self.dir, 'config.toml')
        self.out = io.StringIO()
        self.clock = FakeClock()

    def run_pair(self, answers, argv=None, discovered=(), link=FakePrinterLink):
        argv = list(argv or []) + ['--config', self.path]
        args = main_mod.build_parser().parse_args(['pair'] + argv)
        with mock.patch.object(main_mod, 'PrinterLink', link), \
             mock.patch.object(main_mod, 'discover', lambda **kw: list(discovered)):
            return main_mod.cmd_pair(args, ask=iter(answers).__next__, out=self.out,
                                     clock=self.clock, sleep=self.clock.sleep)


class TestPair(PairTestCase):
    def test_a_typed_ip_and_serial_are_written(self):
        code = self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        self.assertEqual(code, 0)
        written = cfg.load_config(self.path)
        self.assertEqual(written.printer_ip, '10.0.0.42')
        self.assertEqual(written.printer_serial, '01P00A')
        self.assertEqual(written.access_code, '12345678')
        self.assertEqual(len(written.pairing_code), 8)
        self.assertEqual(written.token, '')
        self.assertEqual(written.backend_url, cfg.DEFAULT_BACKEND_URL)

    def test_the_yaml_lines_are_printed_for_pasting(self):
        self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        text = self.out.getvalue()
        self.assertIn('printing:', text)
        self.assertIn('pairing_code:', text)
        code = cfg.load_config(self.path).pairing_code
        self.assertIn(main_mod.format_pairing_code(code), text)

    def test_a_discovered_printer_needs_only_the_access_code(self):
        found = [{'serial': '01P00A', 'model': 'H2S', 'name': 'Shop H2S',
                  'ip': '10.0.0.42'}]
        self.run_pair(['1', '12345678'], discovered=found)
        written = cfg.load_config(self.path)
        self.assertEqual(written.printer_ip, '10.0.0.42')
        self.assertEqual(written.printer_serial, '01P00A')

    def test_the_backend_url_is_printed_so_a_typo_is_visible(self):
        self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        self.assertIn(cfg.DEFAULT_BACKEND_URL, self.out.getvalue())

    def test_an_http_backend_is_refused_without_dev(self):
        rc = self.run_pair(['10.0.0.42', '01P00A', '12345678'],
                           argv=['--backend', 'http://192.168.1.5:6238'])
        self.assertNotEqual(rc, 0)
        self.assertFalse(os.path.exists(self.path))

    def test_an_http_backend_is_accepted_with_dev_and_recorded(self):
        rc = self.run_pair(['10.0.0.42', '01P00A', '12345678'],
                           argv=['--backend', 'http://192.168.1.5:6238', '--dev'])
        self.assertEqual(rc, 0)
        written = cfg.load_config(self.path)
        self.assertTrue(written.dev)
        self.assertEqual(written.backend_url, 'http://192.168.1.5:6238')

    def test_re_running_keeps_the_code(self):
        self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        first = cfg.load_config(self.path).pairing_code
        self.out = io.StringIO()
        self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        self.assertEqual(cfg.load_config(self.path).pairing_code, first)

    def test_new_code_replaces_it(self):
        self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        first = cfg.load_config(self.path).pairing_code
        self.out = io.StringIO()
        self.run_pair(['10.0.0.42', '01P00A', '12345678'], argv=['--new-code'])
        self.assertNotEqual(cfg.load_config(self.path).pairing_code, first)

    def test_a_printer_that_never_answers_refuses_to_continue(self):
        rc = self.run_pair(['10.0.0.42', '01P00A', '12345678'], link=SilentPrinterLink)
        self.assertNotEqual(rc, 0)
        text = self.out.getvalue()
        self.assertIn('LAN', text)
        self.assertIn('Developer Mode', text)
        self.assertFalse(os.path.exists(self.path))

    def test_it_waits_on_the_injected_clock_and_not_on_time_sleep(self):
        self.run_pair(['10.0.0.42', '01P00A', '12345678'], link=SilentPrinterLink)
        self.assertGreater(len(self.clock.slept), 1)

    def test_the_printer_link_is_closed_either_way(self):
        self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        self.assertEqual(FakePrinterLink.instances[-1].disconnects, 1)
        self.run_pair(['10.0.0.42', '01P00A', '12345678'], link=SilentPrinterLink)
        self.assertEqual(FakePrinterLink.instances[-1].disconnects, 1)

    def test_the_access_code_is_never_echoed(self):
        self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        self.assertNotIn('12345678', self.out.getvalue())

    def test_pair_says_how_to_run_the_daemon_by_hand(self):
        """The daemon runs by hand on any platform: pair writes the file and says how to
        run the daemon, and that is all."""
        self.run_pair(['10.0.0.42', '01P00A', '12345678'])
        self.assertIn(f'python -m penguin_delivery_daemon run --home {self.dir}',
                      self.out.getvalue())


class TestPairPrompting(PairTestCase):
    def test_an_empty_answer_is_asked_again(self):
        self.run_pair(['', '10.0.0.42', '', '01P00A', '', '12345678'])
        written = cfg.load_config(self.path)
        self.assertEqual(written.printer_ip, '10.0.0.42')
        self.assertEqual(written.printer_serial, '01P00A')
        self.assertEqual(written.access_code, '12345678')

    def test_an_empty_answer_at_the_menu_is_asked_again(self):
        found = [{'serial': '01P00A', 'model': 'H2S', 'name': 'Shop H2S',
                  'ip': '10.0.0.42'}]
        self.run_pair(['', '1', '12345678'], discovered=found)
        self.assertEqual(self.out.getvalue().count('printer: '), 2)
        self.assertEqual(cfg.load_config(self.path).printer_ip, '10.0.0.42')

    def test_a_number_that_is_not_on_the_menu_is_asked_again(self):
        found = [{'serial': '01P00A', 'model': 'H2S', 'name': 'Shop H2S',
                  'ip': '10.0.0.42'}]
        self.run_pair(['9', '1', '12345678'], discovered=found)
        self.assertIn('There is no printer 9', self.out.getvalue())
        self.assertEqual(cfg.load_config(self.path).printer_ip, '10.0.0.42')

    def test_an_ip_typed_at_the_menu_is_taken_as_an_address(self):
        found = [{'serial': '01P00A', 'model': 'H2S', 'name': 'Shop H2S',
                  'ip': '10.0.0.42'}]
        self.run_pair(['10.0.0.99', '01P00B', '12345678'], discovered=found)
        written = cfg.load_config(self.path)
        self.assertEqual(written.printer_ip, '10.0.0.99')
        self.assertEqual(written.printer_serial, '01P00B')

    def test_a_printer_link_that_raises_is_a_message_not_a_traceback(self):
        class Exploding(FakePrinterLink):
            def connect(self):
                raise RuntimeError('No module named bambulabs_api')

        rc = self.run_pair(['10.0.0.42', '01P00A', '12345678'], link=Exploding)
        self.assertNotEqual(rc, 0)
        text = self.out.getvalue()
        self.assertIn('No module named bambulabs_api', text)
        self.assertIn('Developer Mode', text)
        self.assertFalse(os.path.exists(self.path))

    def test_a_printer_link_that_cannot_even_be_built_is_a_message_too(self):
        def explode(*a, **kw):
            raise OSError('invalid address')

        rc = self.run_pair(['not-an-ip', '01P00A', '12345678'], link=explode)
        self.assertNotEqual(rc, 0)
        self.assertIn('invalid address', self.out.getvalue())
        self.assertFalse(os.path.exists(self.path))

    def test_dev_is_recorded_only_for_a_plain_http_backend(self):
        rc = self.run_pair(['10.0.0.42', '01P00A', '12345678'], argv=['--dev'])
        self.assertEqual(rc, 0)
        self.assertFalse(cfg.load_config(self.path).dev)
        self.assertIn('--dev was not needed', self.out.getvalue())

    def test_discovery_that_cannot_listen_falls_back_to_a_typed_address(self):
        def refuse(**kwargs):
            raise OSError('address already in use')

        args = main_mod.build_parser().parse_args(['pair', '--config', self.path])
        answers = iter(['10.0.0.42', '01P00A', '12345678'])
        with mock.patch.object(main_mod, 'PrinterLink', FakePrinterLink), \
             mock.patch.object(main_mod, 'discover', refuse):
            rc = main_mod.cmd_pair(args, ask=answers.__next__, out=self.out,
                                   clock=self.clock, sleep=self.clock.sleep)
        self.assertEqual(rc, 0)
        self.assertIn('Could not listen for printers (address already in use)',
                      self.out.getvalue())
        self.assertEqual(cfg.load_config(self.path).printer_ip, '10.0.0.42')

    def test_an_unreadable_old_config_is_replaced_with_a_new_code(self):
        with open(self.path, 'w') as fh:
            fh.write('pairing_code = "7K3M')          # a pair that died mid-write
        self.assertEqual(self.run_pair(['10.0.0.42', '01P00A', '12345678']), 0)
        code = cfg.load_config(self.path).pairing_code
        self.assertTrue(main_mod.is_pairing_code(code))

    def test_a_backend_that_is_not_a_url_is_refused_before_any_question(self):
        rc = self.run_pair([], argv=['--backend', 'penguins'])
        self.assertEqual(rc, 2)
        self.assertIn('is not a backend URL', self.out.getvalue())


class RecordingExecutor(rl.InlineExecutor):
    def __init__(self):
        self.shutdowns = 0

    def shutdown(self, wait=True):
        self.shutdowns += 1


class RunTestCase(unittest.TestCase):
    def setUp(self):
        FakePrinterLink.instances = []
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = os.path.join(self.dir, 'config.toml')
        self.downloads = os.path.join(self.dir, 'downloads')
        self.out = io.StringIO()
        self.clock = FakeClock()
        self.executor = RecordingExecutor()
        self.loops = []

    def write_config(self, **overrides):
        values = dict(backend_url='https://example.test', printer_ip='10.0.0.42',
                      printer_serial='01P00A', access_code='12345678',
                      pairing_code='7K3MQ9XW', token='signed')
        values.update(overrides)
        cfg.save_config(cfg.DaemonConfig(**values), path=self.path)

    def _stop(self, seconds):
        raise KeyboardInterrupt

    def run_run(self, link=FakePrinterLink, sleep=None):
        """Runs the real RunLoop, so the real preflight check runs, with the tick sleep
        replaced by a Ctrl-C: one tick, then out."""
        args = main_mod.build_parser().parse_args(['run', '--config', self.path])
        self.relay = relay = FakeRelay(token='signed')
        self.relay_args = []

        def make_relay(*a, **kw):
            self.relay_args.append((a, kw))
            return relay

        def make_loop(config, client, printer, **kwargs):
            kwargs['executor'] = self.executor
            kwargs['sleep'] = self._stop
            loop = rl.RunLoop(config, client, printer, **kwargs)
            self.loops.append(loop)
            return loop

        with mock.patch.object(main_mod, 'PrinterLink', link), \
             mock.patch.object(main_mod, 'RelayClient', make_relay), \
             mock.patch.object(main_mod, 'RunLoop', make_loop):
            return main_mod.cmd_run(args, out=self.out, download_dir=self.downloads,
                                    clock=self.clock, sleep=sleep or self.clock.sleep)


class TestRun(RunTestCase):
    def test_ctrl_c_shuts_the_executor_down_and_exits_zero(self):
        self.write_config()
        self.assertEqual(self.run_run(), 0)
        self.assertEqual(self.executor.shutdowns, 1)
        self.assertEqual(FakePrinterLink.instances[-1].connects, 1)
        self.assertEqual(FakePrinterLink.instances[-1].disconnects, 1)
        self.assertIn('stopping', self.out.getvalue())

    def test_several_interrupts_at_once_stop_it_quietly(self):
        """Review 6, defect 7: Ctrl-C sent to the program and to its wrappers at once is
        several SIGINTs in a row. The first stops the daemon; the rest, arriving while it
        logs "stopping" and shuts down, change nothing and raise nothing."""
        def interrupt(*_args, **_kwargs):
            os.kill(os.getpid(), signal.SIGINT)

        self.addCleanup(signal.signal, signal.SIGINT, signal.getsignal(signal.SIGINT))
        self._stop = interrupt
        executor_shutdown = self.executor.shutdown

        def shutdown(wait=True):
            interrupt()
            interrupt()
            executor_shutdown(wait)

        self.executor.shutdown = shutdown
        self.write_config()
        with mock.patch.object(FakePrinterLink, 'disconnect', interrupt, create=True):
            self.assertEqual(self.run_run(), 0)
        self.assertEqual(self.executor.shutdowns, 1)
        self.assertTrue(self.out.getvalue().rstrip().endswith('stopping'))

    def test_off_the_main_thread_the_interrupts_are_left_alone(self):
        """Only the main thread may take SIGINT; elsewhere the handler is not installed and
        nothing is put back."""
        import threading
        before = signal.getsignal(signal.SIGINT)
        interrupts = main_mod._InterruptOnce()
        worker = threading.Thread(target=lambda: (interrupts.install(),
                                                  interrupts.uninstall()))
        worker.start()
        worker.join(5)
        self.assertFalse(interrupts.installed)
        self.assertIs(signal.getsignal(signal.SIGINT), before)

    def test_the_note_of_a_start_lives_in_the_daemons_home(self):
        """Review 5, defect 3: `run` keeps the note of a start command beside its
        configuration, so the next run finds it."""
        self.write_config()
        self.run_run()
        self.assertEqual(self.loops[-1].start_record_path,
                         os.path.join(os.path.dirname(os.path.abspath(self.path)),
                                      'start.json'))

    def test_one_tick_syncs_the_printers_snapshot_with_the_saved_token(self):
        self.write_config()
        self.run_run()
        self.assertEqual(self.relay_args, [(('https://example.test',), {'token': 'signed'})])
        self.assertEqual([s['state'] for s in self.relay.syncs], ['idle'])
        self.assertIn('running against https://example.test', self.out.getvalue())

    def test_a_config_without_a_token_starts_by_exchanging(self):
        self.write_config(token='')
        self.run_run()
        self.assertEqual(self.relay_args[0][1], {'token': None})

    def test_a_value_error_from_the_loop_exits_two(self):
        """The backstop behind the early backend check."""
        self.write_config()
        with mock.patch.object(rl.RunLoop, 'preflight',
                               side_effect=ValueError('not a backend URL')):
            self.assertEqual(self.run_run(), 2)
        self.assertIn('error: not a backend URL', self.out.getvalue())
        self.assertEqual(self.executor.shutdowns, 1)

    def test_a_plain_http_backend_is_refused(self):
        self.write_config(backend_url='http://192.168.1.5:6238')
        rc = self.run_run()
        self.assertNotEqual(rc, 0)
        self.assertIn('http://192.168.1.5:6238', self.out.getvalue())
        # Refused before anything is opened: no loop, no printer connection.
        self.assertEqual(self.loops, [])
        self.assertEqual(FakePrinterLink.instances, [])

    def test_a_printer_connect_that_raises_exits_non_zero_without_a_traceback(self):
        class Exploding(FakePrinterLink):
            def connect(self):
                raise RuntimeError('No module named bambulabs_api')

        self.write_config()
        rc = self.run_run(link=Exploding)
        self.assertNotEqual(rc, 0)
        self.assertIn('No module named bambulabs_api', self.out.getvalue())
        self.assertEqual(self.executor.shutdowns, 1)

    def test_dev_mode_accepts_it_with_a_warning(self):
        self.write_config(backend_url='http://192.168.1.5:6238', dev=True)
        self.assertEqual(self.run_run(), 0)
        text = self.out.getvalue()
        self.assertIn('WARNING', text)
        self.assertIn('http://192.168.1.5:6238', text)

    def test_the_download_directory_is_created_and_private(self):
        """In the daemon's home, readable only by the user who runs it."""
        self.write_config()
        self.run_run()
        self.assertTrue(os.path.isdir(self.downloads))
        self.assertEqual(stat.S_IMODE(os.stat(self.downloads).st_mode), 0o700)
        self.assertEqual(self.loops[0].download_dir, self.downloads)

    def test_a_download_directory_left_too_open_is_made_private(self):
        os.makedirs(self.downloads, mode=0o777)
        os.chmod(self.downloads, 0o777)
        self.write_config()
        self.run_run()
        self.assertEqual(stat.S_IMODE(os.stat(self.downloads).st_mode), 0o700)

    def test_a_config_with_no_pairing_code_is_waited_for_not_exited_on(self):
        """An unpaired config cannot exchange anything; waiting, it says why."""
        self.write_config(pairing_code='')

        def fix_it_after_two_waits(seconds):
            self.clock.sleep(seconds)
            if len(self.clock.slept) == 2:
                self.write_config(pairing_code='7K3MQ9XW')

        self.assertEqual(self.run_run(sleep=fix_it_after_two_waits), 0)
        text = self.out.getvalue()
        self.assertIn('run `python -m penguin_delivery_daemon pair` first', text)
        self.assertNotIn('sudo', text)
        self.assertEqual(len(self.clock.slept), 2)
        self.assertEqual(self.clock.slept, [5.0, 5.0])

    def test_the_waiting_message_is_logged_once_a_minute_not_every_five_seconds(self):
        self.write_config(pairing_code='')

        def fix_it_after_a_while(seconds):
            self.clock.sleep(seconds)
            if len(self.clock.slept) == 5:
                self.write_config(pairing_code='7K3MQ9XW')

        self.run_run(sleep=fix_it_after_a_while)
        self.assertEqual(self.out.getvalue().count('no pairing code'), 1)

    def test_ctrl_c_while_waiting_is_not_a_crash(self):
        self.write_config(pairing_code='')
        self.assertEqual(self.run_run(sleep=self._stop), 0)
        self.assertIn('stopping', self.out.getvalue())

    def test_a_pairing_code_that_is_not_eight_alphabet_symbols_is_not_one(self):
        self.assertTrue(main_mod.is_pairing_code('7K3MQ9XW'))
        for bad in ('', '7K3M-Q9XW', '7K3MQ9X', '7K3MQ9XWW', '7k3mq9xw', 'IIIIIIII', None):
            self.assertFalse(main_mod.is_pairing_code(bad), bad)

    def test_a_missing_config_file_is_waited_for(self):
        """`run` can be started before `pair`."""
        waited = []
        config = cfg.DaemonConfig(backend_url='https://example.test',
                                  printer_ip='10.0.0.42', printer_serial='01P00A',
                                  access_code='12345678', pairing_code='7K3MQ9XW',
                                  token='signed', path=self.path)

        def fake_wait(path, **kwargs):
            waited.append(path)
            return config

        with mock.patch.object(cfg, 'wait_for_config', fake_wait):
            self.assertEqual(self.run_run(), 0)
        self.assertEqual(waited, [self.path])


class TestStatus(unittest.TestCase):
    def setUp(self):
        FakePrinterLink.instances = []
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = os.path.join(self.dir, 'config.toml')
        cfg.save_config(cfg.DaemonConfig(
            backend_url='https://example.test', printer_ip='10.0.0.42',
            printer_serial='01P00A', access_code='12345678',
            pairing_code='7K3MQ9XW', token='signed'), path=self.path)
        self.out = io.StringIO()
        self.clock = FakeClock()

    def run_status(self, relay, link=FakePrinterLink, path=None):
        args = main_mod.build_parser().parse_args(
            ['status', '--config', path or self.path])
        with mock.patch.object(main_mod, 'PrinterLink', link), \
             mock.patch.object(main_mod, 'RelayClient', lambda *a, **kw: relay):
            return main_mod.cmd_status(args, out=self.out, clock=self.clock,
                                       sleep=self.clock.sleep)

    @staticmethod
    def healthy_relay(error=None):
        relay = PingingRelay(token='signed')
        relay.ping_error = error
        return relay

    def test_it_prints_the_non_secret_fields_and_never_the_secrets(self):
        self.assertEqual(self.run_status(self.healthy_relay()), 0)
        text = self.out.getvalue()
        self.assertIn('10.0.0.42', text)
        self.assertIn('7K3M-Q9XW', text)
        self.assertIn('https://example.test', text)
        self.assertIn('printer: answering, state idle', text)
        self.assertIn('backend: reachable, waiting=False online=True', text)
        self.assertIn('dev mode: no', text)
        self.assertNotIn('12345678', text)      # the printer's LAN access code
        self.assertNotIn('signed', text)        # the daemon token

    def test_it_says_whether_a_token_is_set(self):
        self.run_status(self.healthy_relay())
        self.assertIn('token: set', self.out.getvalue())

    def test_it_says_when_no_token_or_code_is_set(self):
        config = cfg.load_config(self.path)
        config.token = ''
        config.pairing_code = ''
        cfg.save_config(config, path=self.path)
        self.run_status(self.healthy_relay())
        self.assertIn('token: not set', self.out.getvalue())
        self.assertIn('pairing code: (none)', self.out.getvalue())

    def test_a_cloudflare_challenge_is_named(self):
        self.run_status(self.healthy_relay(ChallengeDetected('got HTML from the backend')))
        self.assertIn('backend: blocked by a bot challenge -- got HTML from the backend',
                      self.out.getvalue())

    def test_a_backend_that_is_not_reachable_is_named(self):
        self.run_status(self.healthy_relay(RelayError('connection refused')))
        self.assertIn('backend: not reachable (connection refused)', self.out.getvalue())

    def test_a_printer_that_never_answers_is_named(self):
        self.run_status(self.healthy_relay(), link=SilentPrinterLink)
        text = self.out.getvalue()
        self.assertIn('Developer Mode', text)
        self.assertEqual(FakePrinterLink.instances[-1].disconnects, 1)
        self.assertEqual(self.clock.slept, [main_mod.CONNECT_POLL_SECONDS] * int(
            main_mod.STATUS_WAIT_SECONDS / main_mod.CONNECT_POLL_SECONDS))

    def test_a_printer_link_that_raises_is_named_and_closed(self):
        class Exploding(FakePrinterLink):
            def connect(self):
                raise RuntimeError('no route to printer')

        self.run_status(self.healthy_relay(), link=Exploding)
        self.assertIn('printer: could not connect (no route to printer)', self.out.getvalue())
        self.assertEqual(FakePrinterLink.instances[-1].disconnects, 1)

    def test_it_posts_no_snapshot(self):
        relay = self.healthy_relay()
        self.run_status(relay)
        self.assertEqual(relay.syncs, [])
        self.assertEqual(relay.pings, 1)

    def test_no_config_file_says_to_run_pair(self):
        missing = os.path.join(self.dir, 'gone.toml')
        rc = self.run_status(self.healthy_relay(), path=missing)
        self.assertEqual(rc, 1)
        self.assertIn('Run `python -m penguin_delivery_daemon pair` first.',
                      self.out.getvalue())


class PingingRelay(FakeRelay):
    def __init__(self, token=None):
        super().__init__(token)
        self.pings = 0
        self.ping_error = None

    def ping(self):
        self.pings += 1
        if self.ping_error is not None:
            raise self.ping_error
        return {'ok': True, 'waiting': False, 'online': True}


class TestMain(unittest.TestCase):
    def test_each_command_runs_its_function_with_the_parsed_arguments(self):
        for command in ('pair', 'run', 'status'):
            seen = []
            with mock.patch.object(main_mod, f'cmd_{command}',
                                   lambda args: seen.append(args.command) or 7):
                self.assertEqual(main_mod.main([command, '--config', 'x.toml']), 7)
            self.assertEqual(seen, [command])


class TestParser(unittest.TestCase):
    def test_the_three_commands_exist(self):
        parser = main_mod.build_parser()
        for command in ('pair', 'run', 'status'):
            self.assertEqual(parser.parse_args([command]).command, command)

    def test_pair_takes_new_code_backend_and_dev(self):
        args = main_mod.build_parser().parse_args(
            ['pair', '--new-code', '--backend', 'http://x.test', '--dev'])
        self.assertTrue(args.new_code)
        self.assertTrue(args.dev)
        self.assertEqual(args.backend, 'http://x.test')

    def test_every_command_takes_its_own_config_path(self):
        for command in ('pair', 'run', 'status'):
            args = main_mod.build_parser().parse_args([command, '--config', '/tmp/c.toml'])
            self.assertEqual(args.config, '/tmp/c.toml')

    def test_no_command_prints_the_help_and_fails(self):
        out = io.StringIO()
        with mock.patch('sys.stdout', out):
            rc = main_mod.main([])
        self.assertNotEqual(rc, 0)
        self.assertIn('pair', out.getvalue())


if __name__ == '__main__':
    unittest.main()
