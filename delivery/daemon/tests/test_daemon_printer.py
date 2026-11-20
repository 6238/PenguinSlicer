"""The printer wrapper: the state mapping, the job-suffixed file name, and the thin shim
over bambulabs_api with the library replaced by a fake.

Ported from the original daemon's test_printer.py. Rewritten: the check that importing the
module does not import bambulabs_api ran a second interpreter; it now reads the module's
source, which is faster and also catches an import the library's presence would hide.
Temporary files are now pytest-free tempfile directories removed after each test. New:
discovery's timeout on an injected clock, disconnect, and the exact start arguments. The
part of the original slice/daemon contract test that needs no slicer code (no material
names in the daemon) is here; the rest waits for the sliced-file contract."""
import ast
import os
import re
import secrets
import shutil
import socket
import tempfile
import unittest

import pytest

from penguin_delivery_daemon import printer as pr

from daemon_fakes import FTP_TRANSFER_COMPLETE, H2S, FakeBambuPrinter, FakeClock


class TestStateMapping(unittest.TestCase):
    """Pinned by the fixture. The relay only ever sees these six state names, whatever the
    printer's own vocabulary is."""

    def test_idle(self):
        self.assertEqual(pr.map_status(H2S['idle'])['state'], pr.IDLE)

    def test_preparing_counts_as_running(self):
        self.assertEqual(pr.map_status(H2S['preparing'])['state'], pr.RUNNING)

    def test_heating_counts_as_running_even_while_gcode_state_says_idle(self):
        """The printer reports IDLE with a preparation stage for the first few seconds
        after a start command. Showing 'Printer idle' there would read as a failed send."""
        self.assertEqual(pr.map_status(H2S['heating_while_idle_state'])['state'], pr.RUNNING)

    def test_running(self):
        snap = pr.map_status(H2S['running'])
        self.assertEqual(snap, {'state': pr.RUNNING, 'file': 'sample_part-j8f3a2c1.gcode.3mf',
                                'percent': 42, 'remaining_min': 31, 'layer': 87,
                                'layers': 210, 'error': None,
                                'printer': {'model': None, 'name': None, 'serial': None}})

    def test_the_real_h2s_report_maps_to_running_with_its_progress(self):
        """What the H2S really sent on 2026-10-09: the state and the progress fields."""
        snap = pr.map_status(H2S['running_as_reported_by_h2s'])
        self.assertEqual(snap['state'], pr.RUNNING)
        self.assertEqual((snap['percent'], snap['remaining_min'], snap['layer'],
                          snap['layers']), (0, 17, 0, 50))

    @pytest.mark.known_fault
    def test_known_fault_the_real_h2s_report_gives_the_archive_path_as_file(self):
        """KNOWN FAULT 1, to be fixed in hardening. `file` is filled from `gcode_file`, the
        G-code path inside the archive, before `subtask_name`, so it never names the
        uploaded file: see the known-fault tests in test_daemon_run_loop.py. Hardening
        flips this to expect the uploaded name."""
        snap = pr.map_status(H2S['running_as_reported_by_h2s'])
        self.assertEqual(snap['file'], '/data/Metadata/plate_1.gcode')

    @pytest.mark.known_fault
    def test_known_fault_subtask_name_is_used_only_when_gcode_file_is_empty(self):
        """KNOWN FAULT 1, to be fixed in hardening: the same field order as above."""
        snap = pr.map_status(dict(H2S['running'], gcode_file='', subtask_name='sub'))
        self.assertEqual(snap['file'], 'sub')

    def test_paused(self):
        self.assertEqual(pr.map_status(H2S['paused'])['state'], pr.PAUSED)

    def test_a_paused_stage_while_running_is_paused(self):
        self.assertEqual(pr.map_status(dict(H2S['running'], stg_cur=17))['state'], pr.PAUSED)

    def test_finished(self):
        self.assertEqual(pr.map_status(H2S['finished'])['state'], pr.FINISHED)

    def test_failed_reports_the_hms_code(self):
        snap = pr.map_status(H2S['failed_with_hms'])
        self.assertEqual(snap['state'], pr.ERROR)
        self.assertEqual(snap['error'], 'HMS_0300_0100_0001_0004')

    def test_a_print_error_without_hms_still_reports_something(self):
        snap = pr.map_status(dict(H2S['running'], print_error=50336003, hms=[]))
        self.assertEqual(snap['state'], pr.ERROR)
        self.assertEqual(snap['error'], 'PRINT_ERROR_03001103')

    def test_an_unknown_gcode_state_falls_back_to_idle(self):
        snap = pr.map_status({'gcode_state': 'SOMETHING_NEW', 'stg_cur': 255})
        self.assertEqual(snap['state'], pr.IDLE)

    def test_unparseable_numbers_become_none_or_zero(self):
        snap = pr.map_status({'gcode_state': 'RUNNING', 'stg_cur': 'x', 'mc_percent': 'x',
                              'layer_num': None, 'hms': ['not an entry']})
        self.assertEqual((snap['state'], snap['percent'], snap['layer'], snap['error']),
                         (pr.RUNNING, None, 0, None))

    def test_an_empty_report_is_unreachable(self):
        self.assertEqual(pr.map_status({})['state'], pr.UNREACHABLE)
        self.assertEqual(pr.map_status(None)['state'], pr.UNREACHABLE)

    SNAPSHOT_KEYS = {'state', 'file', 'percent', 'remaining_min', 'layer', 'layers',
                     'error', 'printer'}

    def test_the_snapshot_has_exactly_the_keys_the_relay_expects(self):
        self.assertEqual(set(pr.map_status(H2S['running'])), self.SNAPSHOT_KEYS)

    def test_the_unreachable_snapshot_has_the_same_keys(self):
        self.assertEqual(set(pr.map_status({})), self.SNAPSHOT_KEYS)


class TestHmsSeverity(unittest.TestCase):
    """An HMS entry is information. Only a fatal or serious one means the print stopped."""

    INFO = 0x00040001        # severity 4, info
    COMMON = 0x00030001      # severity 3, common -- e.g. the filament runout pause
    SERIOUS = 0x00020001     # severity 2, serious
    FATAL = 0x00010004       # severity 1, fatal

    def snap(self, base, *codes, attrs=None):
        attrs = attrs or [50331904] * len(codes)
        return pr.map_status(dict(H2S[base], hms=[{'attr': a, 'code': c}
                                                  for a, c in zip(attrs, codes)]))

    def test_an_info_entry_leaves_a_running_print_running_and_is_reported(self):
        snap = self.snap('running', self.INFO)
        self.assertEqual((snap['state'], snap['error']), (pr.RUNNING, 'HMS_0300_0100_0004_0001'))

    def test_a_pause_with_an_entry_is_still_paused(self):
        snap = self.snap('paused', self.COMMON)
        self.assertEqual((snap['state'], snap['error']), (pr.PAUSED, 'HMS_0300_0100_0003_0001'))

    def test_a_fatal_entry_stops_a_running_print(self):
        self.assertEqual(self.snap('running', self.FATAL)['state'], pr.ERROR)

    def test_a_failed_state_is_an_error_whatever_the_entry_says(self):
        self.assertEqual(self.snap('failed_with_hms', self.INFO)['state'], pr.ERROR)

    def test_a_fatal_entry_behind_an_info_entry_still_stops_the_print(self):
        snap = self.snap('running', self.INFO, self.FATAL)
        self.assertEqual((snap['state'], snap['error']), (pr.ERROR, 'HMS_0300_0100_0001_0004'))

    def test_a_fatal_entry_ahead_of_an_info_entry_is_the_one_reported(self):
        snap = self.snap('running', self.FATAL, self.INFO)
        self.assertEqual((snap['state'], snap['error']), (pr.ERROR, 'HMS_0300_0100_0001_0004'))

    def test_a_serious_entry_stops_the_print_too(self):
        snap = self.snap('running', self.INFO, self.SERIOUS)
        self.assertEqual((snap['state'], snap['error']), (pr.ERROR, 'HMS_0300_0100_0002_0001'))

    def test_the_first_of_two_equally_severe_entries_is_reported(self):
        snap = self.snap('running', self.INFO, self.INFO, attrs=[50331904, 50331905])
        self.assertEqual((snap['state'], snap['error']), (pr.RUNNING, 'HMS_0300_0100_0004_0001'))

    def test_several_informational_entries_leave_the_print_running(self):
        snap = self.snap('running', self.COMMON, self.INFO)
        self.assertEqual((snap['state'], snap['error']), (pr.RUNNING, 'HMS_0300_0100_0003_0001'))

    def test_an_entry_with_no_code_never_outranks_a_real_fault(self):
        snap = pr.map_status(dict(H2S['running'],
                                  hms=[{}, {'attr': 50331904, 'code': self.FATAL}]))
        self.assertEqual((snap['state'], snap['error']), (pr.ERROR, 'HMS_0300_0100_0001_0004'))


class TestHmsFormatting(unittest.TestCase):
    def test_attr_and_code_become_the_four_group_form(self):
        self.assertEqual(pr.format_hms(50331904, 65540), 'HMS_0300_0100_0001_0004')


class TestFileNames(unittest.TestCase):
    def test_the_job_id_goes_before_the_compound_extension(self):
        self.assertEqual(pr.suffixed_name('sample_part.gcode.3mf', 'j8f3a2c1'),
                         'sample_part-j8f3a2c1.gcode.3mf')

    def test_a_plain_3mf_and_a_plain_gcode_work_too(self):
        self.assertEqual(pr.suffixed_name('part.3mf', 'j1'), 'part-j1.3mf')
        self.assertEqual(pr.suffixed_name('part.gcode', 'j1'), 'part-j1.gcode')

    def test_an_unknown_extension_still_gets_the_suffix(self):
        self.assertEqual(pr.suffixed_name('part.bin', 'j1'), 'part-j1.bin')

    def test_stripping_the_suffix_round_trips(self):
        name = pr.suffixed_name('sample_part.gcode.3mf', 'j8f3a2c1')
        self.assertEqual(pr.strip_job_suffix(name), 'sample_part.gcode.3mf')

    def test_a_real_generated_job_id_round_trips(self):
        """The relay builds the id as 'j' + secrets.token_hex(4)."""
        for _ in range(200):
            job_id = 'j' + secrets.token_hex(4)
            name = pr.suffixed_name('sample_part.gcode.3mf', job_id)
            self.assertEqual(pr.strip_job_suffix(name), 'sample_part.gcode.3mf')

    def test_stripping_leaves_a_file_the_daemon_did_not_name(self):
        for name in ('someone-else.gcode.3mf', 'part-jaded.gcode.3mf',
                     'part-jbeadedface.gcode.3mf', 'no-extension'):
            self.assertEqual(pr.strip_job_suffix(name), name)


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def sliced_file(self, content=b'3mf-bytes'):
        path = os.path.join(self.tmp, 'job.gcode.3mf')
        with open(path, 'wb') as fh:
            fh.write(content)
        return path


class TestPrinterLink(TempDirTestCase):
    def link(self, factory=FakeBambuPrinter):
        return pr.PrinterLink('10.0.0.42', '01P00A', '12345678', model='H2S',
                              name='Shop H2S', printer_factory=factory)

    def test_connect_starts_mqtt_only_with_the_configured_printer(self):
        link = self.link()
        printer = link.connect()
        self.assertTrue(printer.mqtt_running)        # and camera_start would have raised
        self.assertEqual((printer.ip_address, printer.access_code, printer.serial),
                         ('10.0.0.42', '12345678', '01P00A'))

    def test_snapshot_before_connect_or_any_report_is_unreachable(self):
        link = self.link()
        self.assertEqual(link.snapshot()['state'], pr.UNREACHABLE)
        link.connect()
        self.assertEqual(link.snapshot()['state'], pr.UNREACHABLE)

    def test_snapshot_carries_the_printer_identity(self):
        link = self.link()
        link.connect()
        link._printer.report = H2S['running']
        self.assertEqual(link.snapshot()['printer'],
                         {'model': 'H2S', 'name': 'Shop H2S', 'serial': '01P00A'})

    def test_a_disconnected_client_reports_unreachable(self):
        link = self.link()
        link.connect()
        link._printer.report = H2S['running']
        link._printer.connected = False
        self.assertEqual(link.snapshot()['state'], pr.UNREACHABLE)

    def test_disconnect_stops_mqtt_and_forgets_the_printer(self):
        link = self.link()
        printer = link.connect()
        link.disconnect()
        self.assertFalse(printer.mqtt_running)
        self.assertEqual(link.snapshot()['state'], pr.UNREACHABLE)
        link.disconnect()                           # twice is harmless

    def test_a_disconnect_that_raises_is_swallowed(self):
        class Stubborn(FakeBambuPrinter):
            def mqtt_stop(self):
                raise RuntimeError('already gone')

        link = self.link(Stubborn)
        link.connect()
        link.disconnect()
        self.assertIsNone(link._printer)

    def test_upload_sends_the_bytes_under_the_suffixed_name(self):
        link = self.link()
        link.connect()
        self.assertEqual(link.upload(self.sliced_file(), 'sample_part-j8f3a2c1.gcode.3mf'),
                         FTP_TRANSFER_COMPLETE)
        self.assertEqual(link._printer.uploaded,
                         ('sample_part-j8f3a2c1.gcode.3mf', b'3mf-bytes'))

    @pytest.mark.known_fault
    def test_known_fault_upload_passes_on_the_none_of_a_swallowed_failure(self):
        """KNOWN FAULT 2, to be fixed in hardening. bambulabs_api returns None after it
        swallows a failure during the transfer, and PrinterLink.upload hands that back as
        if it were a result: see the known fault in test_daemon_run_loop.py. Hardening
        flips this to expect an exception."""
        link = self.link()
        link.connect()
        link._printer.upload_returns_none = True
        self.assertIsNone(link.upload(self.sliced_file(), 'x.gcode.3mf'))

    def test_start_uses_plate_one_the_external_spool_and_flow_calibration(self):
        link = self.link()
        link.connect()
        self.assertTrue(link.start('sample_part-j8f3a2c1.gcode.3mf'))
        self.assertEqual(link._printer.started, {
            'filename': 'sample_part-j8f3a2c1.gcode.3mf', 'plate_number': 1,
            'use_ams': False, 'ams_mapping': [0], 'flow_calibration': True})

    def test_upload_and_start_before_connect_say_so(self):
        link = pr.PrinterLink('10.0.0.42', '01P00A', '12345678')
        with self.assertRaisesRegex(RuntimeError, 'not connected'):
            link.upload('/nonexistent', 'x.3mf')
        with self.assertRaisesRegex(RuntimeError, 'not connected'):
            link.start('x.3mf')

    def test_a_failed_upload_does_not_leak_the_file_handle(self):
        class Refusing(FakeBambuPrinter):
            def upload_file(self, file_obj, filename):
                self.attempted = file_obj
                raise OSError('ftps refused')

        link = self.link(Refusing)
        link.connect()
        with self.assertRaises(OSError):
            link.upload(self.sliced_file(), 'sample_part-j8f3a2c1.gcode.3mf')
        self.assertTrue(link._printer.attempted.closed)

    def test_snapshot_never_raises_when_the_library_misbehaves(self):
        class Exploding(FakeBambuPrinter):
            def mqtt_dump(self):
                raise RuntimeError('mqtt is gone')

        link = self.link(Exploding)
        link.connect()
        self.assertEqual(link.snapshot()['state'], pr.UNREACHABLE)


class FakeSocket:
    """A UDP socket that never touches the network: recvfrom hands back the queued items in
    order, raising any that are exceptions, and then raises a real socket error."""

    def __init__(self, packets=(), membership_error=None, clock=None, tick=1.0):
        self.packets = list(packets)
        self.membership_error = membership_error
        self.options = []
        self.timeout = None
        self.closed = False
        self.clock = clock
        self.tick = tick

    def setsockopt(self, level, optname, value):
        self.options.append((level, optname, value))
        if optname == socket.IP_ADD_MEMBERSHIP and self.membership_error is not None:
            raise self.membership_error

    def settimeout(self, value):
        self.timeout = value

    def recvfrom(self, _bufsize):
        if self.clock is not None:
            self.clock.advance(self.tick)        # a one-second socket timeout, on the fake
        if self.packets:
            item = self.packets.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        raise OSError('the interface went away')

    def close(self):
        self.closed = True


ANNOUNCEMENT = (b'NOTIFY * HTTP/1.1\r\n'
                b'HOST: 239.255.255.250:2021\r\n'
                b'USN: 01P00A123456789\r\n'
                b'DevModel.bambu.com: BL-H2S\r\n'
                b'DevName.bambu.com: Shop H2S\r\n\r\n')


class TestDiscovery(unittest.TestCase):
    def discover_with(self, sock, **kwargs):
        return pr.discover(timeout=5.0, sock_factory=lambda: sock, **kwargs)

    def test_it_joins_the_ssdp_multicast_group(self):
        """Binding UDP 2021 is not enough on Linux: without the membership the kernel drops
        every announcement and discovery silently finds nothing."""
        sock = FakeSocket()
        self.discover_with(sock)
        joins = [opt for opt in sock.options if opt[1] == socket.IP_ADD_MEMBERSHIP]
        self.assertEqual(joins, [(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                  socket.inet_aton('239.255.255.250')
                                  + socket.inet_aton('0.0.0.0'))])
        self.assertEqual(sock.timeout, 1.0)

    def test_an_announcement_becomes_an_entry(self):
        found = self.discover_with(FakeSocket([(ANNOUNCEMENT, ('10.0.0.42', 2021))]))
        self.assertEqual(found, [{'serial': '01P00A123456789', 'model': 'BL-H2S',
                                  'name': 'Shop H2S', 'ip': '10.0.0.42'}])

    def test_a_repeated_announcement_is_one_entry_and_one_without_a_serial_is_skipped(self):
        found = self.discover_with(FakeSocket([
            (ANNOUNCEMENT, ('10.0.0.42', 2021)), (b'NOTIFY * HTTP/1.1\r\n\r\n', ('x', 1)),
            (ANNOUNCEMENT, ('10.0.0.43', 2021))]))
        self.assertEqual([entry['ip'] for entry in found], ['10.0.0.43'])

    def test_a_network_that_refuses_membership_still_listens(self):
        sock = FakeSocket([(ANNOUNCEMENT, ('10.0.0.42', 2021))],
                          membership_error=OSError('no such device'))
        self.assertEqual(len(self.discover_with(sock)), 1)

    def test_it_listens_until_the_deadline_through_quiet_seconds(self):
        """socket.timeout is a quiet second, not an error: keep listening until the
        deadline, measured on the injected clock."""
        clock = FakeClock()
        quiet = [socket.timeout()] * 10
        sock = FakeSocket([socket.timeout(), (ANNOUNCEMENT, ('10.0.0.42', 2021))] + quiet,
                          clock=clock)
        found = self.discover_with(sock, clock=clock)
        self.assertEqual(len(found), 1)
        self.assertEqual(clock.now, 1005.0)                  # five quiet seconds, no more
        self.assertTrue(sock.closed)

    def test_the_socket_is_closed_even_when_the_loop_breaks(self):
        sock = FakeSocket()
        self.discover_with(sock)
        self.assertTrue(sock.closed)

    def test_a_close_that_raises_is_swallowed(self):
        sock = FakeSocket()
        sock.close = lambda: (_ for _ in ()).throw(OSError('bad fd'))
        self.assertEqual(self.discover_with(sock), [])


class TestTheLibraryStaysUnimported(unittest.TestCase):
    def test_bambulabs_api_is_imported_only_inside_a_function(self):
        """The lazy import is what lets the daemon's other modules and tests run without
        the library. Read the source: a module-level import is the fault to catch, and
        whether the library happens to be installed must not hide it."""
        with open(pr.__file__, encoding='utf-8') as fh:
            source = fh.read()
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                module = getattr(node, 'module', None) or ''
                self.assertNotIn('bambulabs_api', names + [module])
        link_class = next(n for n in tree.body
                          if isinstance(n, ast.ClassDef) and n.name == 'PrinterLink')
        self.assertIn('import bambulabs_api', ast.get_source_segment(source, link_class))


class TestTheDaemonNamesNoMaterial(unittest.TestCase):
    def test_the_daemon_names_no_material_plate_or_nozzle(self):
        """Everything the printer needs to know about the filament, the plate and the
        nozzle travels inside the sliced file, which is why the slice service can change
        profiles without touching the daemon."""
        with open(pr.__file__, encoding='utf-8') as fh:
            source = fh.read()
        code = '\n'.join(line for line in source.splitlines()
                         if not line.lstrip().startswith('#'))
        code = re.sub(r'"""(?:.|\n)*?"""', '', code)      # drop the docstrings
        for word in ('PETG', 'PLA', 'ABS', 'Textured', 'High Flow', 'nozzle_diameter'):
            self.assertIsNone(re.search(r'\b' + word.replace(' ', r'\s') + r'\b', code), word)
