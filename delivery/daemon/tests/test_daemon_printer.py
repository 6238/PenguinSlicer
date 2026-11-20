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

    def test_idle_is_no_print_whatever_the_stage_code_says(self):
        """Round 3, defect 1: the main state decides whether a print is going on. The port
        read IDLE with a preparation stage as a print in its first seconds; the fixture
        invents that document, and an idle printer with a left-over or unknown stage was
        then read as printing for ever. A real print's first seconds are on the hardware
        checklist; until then the start wait simply goes on until RUNNING arrives."""
        self.assertEqual(pr.map_status(H2S['heating_while_idle_state'])['state'], pr.IDLE)
        for stage in (-1, 99, 7, 16, 6, 'x'):
            with self.subTest(stg_cur=stage):
                snap = pr.map_status(dict(H2S['idle'], stg_cur=stage))
                self.assertEqual(snap['state'], pr.IDLE)

    def test_running(self):
        snap = pr.map_status(H2S['running'])
        self.assertEqual(snap, {'state': pr.RUNNING, 'file': 'sample_part-j8f3a2c1',
                                'job_name': 'sample_part-j8f3a2c1', 'stage_code': 0,
                                'stage': 'printing', 'stage_label': 'Printing',
                                'percent': 42, 'remaining_min': 31, 'layer': 87,
                                'layers': 210, 'error': None, 'waiting_for': None,
                                'waiting_label': None, 'at_the_printer': None,
                                'unrecognised': None, 'whole': True,
                                'printer': {'model': None, 'name': None, 'serial': None}})

    def test_the_real_h2s_report_maps_to_running_with_its_progress(self):
        """What the H2S really sent on 2026-10-09: the state and the progress fields."""
        snap = pr.map_status(H2S['running_as_reported_by_h2s'])
        self.assertEqual(snap['state'], pr.RUNNING)
        self.assertEqual((snap['percent'], snap['remaining_min'], snap['layer'],
                          snap['layers']), (0, 17, 0, 50))
        self.assertEqual((snap['stage_code'], snap['stage']), (14, 'cleaning_nozzle'))

    def test_the_real_h2s_report_names_our_file_by_its_subtask_name(self):
        """Known fault 1, fixed: `gcode_file` is the G-code path inside the archive and
        names nothing; `subtask_name` is our name without .gcode.3mf, and it decides."""
        snap = pr.map_status(H2S['running_as_reported_by_h2s'])
        self.assertEqual(snap['job_name'], 'sample_part-jb345bf38')
        self.assertEqual(snap['file'], 'sample_part-jb345bf38')
        self.assertTrue(pr.reports_file(snap, 'sample_part-jb345bf38.gcode.3mf'))
        self.assertFalse(pr.reports_file(snap, 'sample_part-j00000001.gcode.3mf'))

    def test_the_archive_path_is_the_file_only_when_there_is_no_subtask_name(self):
        snap = pr.map_status(dict(H2S['running'], gcode_file='/data/Metadata/plate_1.gcode',
                                  subtask_name=''))
        self.assertEqual((snap['file'], snap['job_name']), ('/data/Metadata/plate_1.gcode', ''))

    def test_a_printer_that_reports_the_whole_name_is_recognised_too(self):
        self.assertTrue(pr.reports_file({'file': 'p-j8f3a2c1.gcode.3mf', 'job_name': ''},
                                        'p-j8f3a2c1.gcode.3mf'))

    def test_every_stage_code_has_a_name_and_an_unknown_one_is_named_honestly(self):
        for code, (name, label) in pr.PRINTER_STAGES.items():
            self.assertRegex(name, r'^[a-z_]+$')
            self.assertTrue(label[0].isupper(), label)
        self.assertEqual(pr.printer_stage(77), ('stage_77', 'Busy (stage 77)'))
        self.assertEqual(pr.printer_stage(None), (None, None))
        snap = pr.map_status(dict(H2S['running'], stg_cur=77))
        self.assertEqual((snap['stage'], snap['state']), ('stage_77', pr.RUNNING))

    def test_a_document_that_is_not_a_mapping_is_unreachable(self):
        for junk in ('not json', ['a'], 42):
            self.assertEqual(pr.map_status(junk)['state'], pr.UNREACHABLE)

    def test_unknown_fields_are_ignored(self):
        snap = pr.map_status(dict(H2S['running'], brand_new_field={'x': 1}, nozzle_temper=220))
        self.assertEqual(snap, pr.map_status(H2S['running']))

    def test_a_hms_field_that_is_not_a_list_is_ignored(self):
        snap = pr.map_status(dict(H2S['running'], hms='garbage'))
        self.assertEqual((snap['state'], snap['error']), (pr.RUNNING, None))

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

    def test_a_print_error_while_running_is_the_printer_waiting_for_a_person(self):
        """Round 2, defect 1: an error code set while the print runs is not an end."""
        snap = pr.map_status(dict(H2S['running'], print_error=50336003, hms=[]))
        self.assertEqual(snap['state'], pr.PAUSED)
        self.assertEqual(snap['error'], 'PRINT_ERROR_03001103')
        self.assertEqual(snap['waiting_for'], 'printer_error')
        self.assertIn("printer's screen", snap['at_the_printer'])

    def test_an_unknown_gcode_state_is_unrecognised_as_a_whole_never_an_end(self):
        for stage in (255, 0, 16, -1, None):
            with self.subTest(stg_cur=stage):
                snap = pr.map_status({'gcode_state': 'SOMETHING_NEW', 'stg_cur': stage})
                self.assertEqual(snap['state'], pr.UNRECOGNISED_STATE)
                self.assertIn("gcode_state 'SOMETHING_NEW'", snap['unrecognised'])

    def test_unparseable_numbers_become_none_or_zero(self):
        snap = pr.map_status({'gcode_state': 'RUNNING', 'stg_cur': 'x', 'mc_percent': 'x',
                              'layer_num': None, 'hms': ['not an entry']})
        self.assertEqual((snap['state'], snap['percent'], snap['layer'], snap['error']),
                         (pr.RUNNING, None, 0, None))

    def test_an_empty_report_is_unreachable(self):
        self.assertEqual(pr.map_status({})['state'], pr.UNREACHABLE)
        self.assertEqual(pr.map_status(None)['state'], pr.UNREACHABLE)

    SNAPSHOT_KEYS = {'state', 'file', 'job_name', 'stage_code', 'stage', 'stage_label',
                     'percent', 'remaining_min', 'layer', 'layers', 'error', 'printer',
                     'waiting_for', 'waiting_label', 'at_the_printer', 'unrecognised',
                     'whole'}

    def test_the_snapshot_has_exactly_the_keys_the_relay_expects(self):
        self.assertEqual(set(pr.map_status(H2S['running'])), self.SNAPSHOT_KEYS)

    def test_the_unreachable_snapshot_has_the_same_keys(self):
        self.assertEqual(set(pr.map_status({})), self.SNAPSHOT_KEYS)


class TestHmsSeverity(unittest.TestCase):
    """An HMS entry is information. A fatal or serious one makes the printer wait for a
    person (`paused`, never an end); only the printer's own FAILED state ends the print."""

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

    def test_a_fatal_entry_makes_a_running_print_wait_for_a_person(self):
        snap = self.snap('running', self.FATAL)
        self.assertEqual((snap['state'], snap['waiting_for']), (pr.PAUSED, 'printer_error'))

    def test_a_failed_state_is_an_error_whatever_the_entry_says(self):
        self.assertEqual(self.snap('failed_with_hms', self.INFO)['state'], pr.ERROR)

    def test_a_fatal_entry_behind_an_info_entry_still_counts(self):
        snap = self.snap('running', self.INFO, self.FATAL)
        self.assertEqual((snap['state'], snap['error']), (pr.PAUSED, 'HMS_0300_0100_0001_0004'))

    def test_a_fatal_entry_ahead_of_an_info_entry_is_the_one_reported(self):
        snap = self.snap('running', self.FATAL, self.INFO)
        self.assertEqual((snap['state'], snap['error']), (pr.PAUSED, 'HMS_0300_0100_0001_0004'))

    def test_a_serious_entry_makes_the_printer_wait_too(self):
        snap = self.snap('running', self.INFO, self.SERIOUS)
        self.assertEqual((snap['state'], snap['error']), (pr.PAUSED, 'HMS_0300_0100_0002_0001'))
        self.assertEqual(snap['waiting_label'], 'The printer reported a serious fault')

    def test_a_serious_entry_on_an_idle_printer_is_how_the_print_ended(self):
        snap = self.snap('idle', self.SERIOUS)
        self.assertEqual(snap['state'], pr.ERROR)

    def test_an_unknown_severity_is_kept_and_the_print_goes_on(self):
        snap = self.snap('running', 0x00090001)
        self.assertEqual((snap['state'], snap['unrecognised']), (pr.RUNNING, 'hms severity 9'))

    def test_the_first_of_two_equally_severe_entries_is_reported(self):
        snap = self.snap('running', self.INFO, self.INFO, attrs=[50331904, 50331905])
        self.assertEqual((snap['state'], snap['error']), (pr.RUNNING, 'HMS_0300_0100_0004_0001'))

    def test_several_informational_entries_leave_the_print_running(self):
        snap = self.snap('running', self.COMMON, self.INFO)
        self.assertEqual((snap['state'], snap['error']), (pr.RUNNING, 'HMS_0300_0100_0003_0001'))

    def test_an_entry_with_no_code_never_outranks_a_real_fault(self):
        snap = pr.map_status(dict(H2S['running'],
                                  hms=[{}, {'attr': 50331904, 'code': self.FATAL}]))
        self.assertEqual((snap['state'], snap['error']), (pr.PAUSED, 'HMS_0300_0100_0001_0004'))


class TestWhatTheReportMeans(unittest.TestCase):
    """Round 2, defect 1: every value the daemon reads, classified in PRINTER_VALUES. Only
    the printer's own end (FINISH, FAILED, or idle with an error code) is an end."""

    RUN = dict(H2S['running'], print_error=0, hms=[])

    def doc(self, **fields):
        return pr.map_status(dict(self.RUN, **fields))

    def test_every_value_is_in_one_of_the_six_classes(self):
        kinds = {pr.GOING, pr.WAITING, pr.ENDED_WELL, pr.ENDED_BADLY, pr.NO_PRINT,
                 pr.UNRECOGNISED}
        for (field, value), (kind, name, label, remedy) in pr.PRINTER_VALUES.items():
            with self.subTest(field=field, value=value):
                self.assertIn(kind, kinds)
                self.assertRegex(name, r'^[a-z_]+$')
                self.assertTrue(label[0].isupper())
                # Waiting for a person always says what to do at the printer, as a sentence.
                self.assertEqual(remedy is not None, kind == pr.WAITING)
                if remedy:
                    self.assertTrue(remedy[0].isupper() and remedy.endswith('.'), remedy)

    def test_every_waiting_stage_reads_as_paused_with_what_to_do(self):
        for code in pr.STG_PAUSED:
            with self.subTest(stg_cur=code):
                snap = self.doc(stg_cur=code)
                self.assertEqual(snap['state'], pr.PAUSED)
                self.assertEqual(snap['waiting_for'], pr.PRINTER_STAGES[code][0])
                self.assertEqual(snap['at_the_printer'], pr.PRINTER_VALUES[('stg_cur', code)][3])

    def test_every_working_stage_reads_as_running(self):
        for code, (kind, *_rest) in pr.STAGE_VALUES.items():
            if kind == pr.GOING:
                with self.subTest(stg_cur=code):
                    self.assertEqual(self.doc(stg_cur=code)['state'], pr.RUNNING)

    def test_the_waiting_cases_of_the_brief(self):
        """Paused at the printer, door open, filament run out, an error code while paused
        or running, a serious fault: each is the printer waiting, with its reason."""
        cases = {
            'paused at the printer': (dict(gcode_state='PAUSE', stg_cur=16), 'paused_by_user'),
            'paused, no stage': (dict(gcode_state='PAUSE', stg_cur=0), 'paused'),
            'door open': (dict(gcode_state='PAUSE', stg_cur=17, print_error=0x0500400E),
                          'paused_cover_open'),
            'filament run out': (dict(gcode_state='PAUSE', stg_cur=6, print_error=0x07008011),
                                 'paused_filament_runout'),
            'error code while paused': (dict(gcode_state='PAUSE', stg_cur=0,
                                             print_error=0x07008011), 'printer_error'),
            'error code while running': (dict(print_error=0x07008011), 'printer_error'),
            'serious fault while running': (dict(hms=[{'attr': 0x07008000,
                                                       'code': 0x00020001}]), 'printer_error'),
        }
        for name, (fields, reason) in cases.items():
            with self.subTest(name):
                snap = self.doc(**fields)
                self.assertEqual((snap['state'], snap['waiting_for']), (pr.PAUSED, reason))
                self.assertTrue(snap['at_the_printer'])

    def test_the_ends(self):
        self.assertEqual(self.doc(gcode_state='FINISH', stg_cur=255)['state'], pr.FINISHED)
        self.assertEqual(self.doc(gcode_state='FAILED', stg_cur=255)['state'], pr.ERROR)
        self.assertEqual(self.doc(gcode_state='FAILED', print_error=0x07008011)['state'],
                         pr.ERROR)
        self.assertEqual(self.doc(gcode_state='IDLE', stg_cur=255,
                                  print_error=0x07008011)['state'], pr.ERROR)
        # A finish outranks a code left set.
        self.assertEqual(self.doc(gcode_state='FINISH', print_error=0x07008011)['state'],
                         pr.FINISHED)

    def test_an_unknown_stage_under_a_going_state_is_going_and_kept(self):
        for state, expected in (('RUNNING', pr.RUNNING), ('PREPARE', pr.RUNNING),
                                ('PAUSE', pr.PAUSED)):
            with self.subTest(gcode_state=state):
                snap = self.doc(gcode_state=state, stg_cur=90)
                self.assertEqual((snap['state'], snap['unrecognised']),
                                 (expected, "stg_cur '90'"))
                self.assertEqual(snap['stage'], 'stage_90')

    def test_an_unknown_stage_under_idle_is_no_print_and_kept(self):
        """The reviewer's case, `IDLE` with stage -1, and its neighbours."""
        for stage in (-1, 90):
            with self.subTest(stg_cur=stage):
                snap = self.doc(gcode_state='IDLE', stg_cur=stage)
                self.assertEqual((snap['state'], snap['unrecognised']),
                                 (pr.IDLE, f"stg_cur '{stage}'"))

    def test_the_librarys_unknown_placeholder_is_unrecognised(self):
        snap = self.doc(gcode_state='UNKNOWN')
        self.assertEqual((snap['state'], snap['unrecognised']), (pr.UNRECOGNISED_STATE, None))

    def test_a_document_with_no_main_state_says_nothing_about_a_print(self):
        """Review 4, defect 1: the reviewer's document (someone else's print at 43 percent,
        no `gcode_state`) read as idle, and a start went out on it. A picture with no main
        state is unrecognised as a whole and not whole, whatever its stage, figures or
        name say."""
        reviewers = {'mc_percent': 43, 'mc_remaining_time': 12, 'layer_num': 5,
                     'subtask_name': 'someone_elses_print'}
        for document in (reviewers, {'mc_percent': 3}, {'stg_cur': 255}, {'stg_cur': 2},
                         {'stg_cur': 17}, {'stg_cur': 255, 'print_error': 1},
                         {'stg_cur': -1}, {'gcode_state': None, 'stg_cur': 255},
                         {'gcode_state': '', 'mc_percent': 0}):
            with self.subTest(document=document):
                snap = pr.map_status(document)
                self.assertEqual(snap['state'], pr.UNRECOGNISED_STATE)
                self.assertTrue(snap['unrecognised'].startswith(pr.NO_MAIN_STATE))
                self.assertIs(snap['whole'], False)

    def test_a_document_with_a_main_state_is_whole(self):
        self.assertIs(pr.map_status(H2S['idle'])['whole'], True)
        self.assertIs(pr.map_status({})['whole'], False)

    def test_the_guide_prints_the_table(self):
        guide = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                             'README.md')
        with open(guide, encoding='utf-8') as fh:
            self.assertIn(pr.values_table(), fh.read())


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
                         'the printer has all 9 bytes')
        self.assertEqual(link._printer.uploaded,
                         ('sample_part-j8f3a2c1.gcode.3mf', b'3mf-bytes'))
        self.assertEqual(link._printer.ftp_client.ftps.timeout, pr.UPLOAD_SOCKET_TIMEOUT)

    def test_a_swallowed_failure_with_nothing_on_the_printer_is_an_upload_failure(self):
        """Known fault 2, fixed: the library's None is no longer passed on as a result."""
        link = self.link()
        link.connect()
        link._printer.upload_returns_none = True
        with self.assertRaises(pr.UploadFailed) as caught:
            link.upload(self.sliced_file(), 'x.gcode.3mf')
        self.assertEqual(str(caught.exception),
                         'the printer did not confirm that the file arrived')
        self.assertIn('550 Could not create file', caught.exception.detail)

    def test_the_426_after_a_whole_file_is_a_success_and_looks_like_none(self):
        """The H2S case: the library logs an error and returns None, but every byte
        arrived. The printer's listing decides, and nothing reaches the log as an error."""
        forwarded = []
        link = pr.PrinterLink('10.0.0.42', '01P00A', '12345678',
                              printer_factory=FakeBambuPrinter, log=forwarded.append)
        link.connect()
        link._printer.arrives_but_426 = True
        note = link.upload(self.sliced_file(), 'x.gcode.3mf')
        self.assertEqual(note, 'the printer has all 9 bytes (its FTP server answered '
                               'nothing; that is harmless)')
        self.assertEqual(forwarded, [])

    def test_a_226_for_a_short_file_is_an_upload_failure(self):
        link = self.link()
        link.connect()
        link._printer.short_by = 4
        with self.assertRaisesRegex(pr.UploadFailed, 'the printer has 5 of 9 bytes'):
            link.upload(self.sliced_file(), 'x.gcode.3mf')

    def test_a_226_the_printer_cannot_confirm_is_accepted_and_says_so(self):
        link = self.link()
        link.connect()
        link._printer.list_fails = True
        self.assertEqual(link.upload(self.sliced_file(), 'x.gcode.3mf'),
                         'sent 9 bytes; the printer did not list its files to confirm')

    def test_a_refused_upload_is_an_upload_failure_naming_the_cause(self):
        link = self.link()
        link.connect()
        link._printer.upload_raises = 'Login incorrect'
        with self.assertRaisesRegex(pr.UploadFailed, 'Login incorrect'):
            link.upload(self.sliced_file(), 'x.gcode.3mf')

    def test_progress_counts_the_bytes_sent(self):
        link = self.link()
        link.connect()
        path = self.sliced_file(content=b'x' * 70000)
        seen = []
        link.upload(path, 'x.gcode.3mf', progress=lambda sent, total: seen.append((sent, total)))
        self.assertEqual(seen, [(32768, 70000), (65536, 70000), (70000, 70000)])

    def test_a_cancel_stops_the_upload_and_says_so(self):
        link = self.link()
        link.connect()
        path = self.sliced_file(content=b'x' * 70000)
        asked = {'n': 0}

        def cancelled():
            asked['n'] += 1
            return asked['n'] > 2                 # after two blocks

        with self.assertRaises(pr.UploadCancelled):
            link.upload(path, 'x.gcode.3mf', cancelled=cancelled)
        self.assertEqual(len(link._printer.files['x.gcode.3mf']), 65536)   # partial
        self.assertEqual(link.delete('x.gcode.3mf'),
                         (pr.REMOVED, '250 Delete operation successful.'))
        self.assertEqual(link._printer.deleted, ['x.gcode.3mf'])

    def forwarding_link(self, printer_factory=FakeBambuPrinter):
        forwarded = []
        link = pr.PrinterLink('10.0.0.42', '01P00A', '12345678',
                              printer_factory=printer_factory, log=forwarded.append)
        link.connect()
        return link, forwarded

    def test_a_delete_the_printer_confirms_is_removed(self):
        link, forwarded = self.forwarding_link()
        link._printer.files['x.gcode.3mf'] = b'x'
        self.assertEqual(link.delete('x.gcode.3mf'),
                         (pr.REMOVED, '250 Delete operation successful.'))
        self.assertEqual((link._printer.deleted, link._printer.files, forwarded),
                         (['x.gcode.3mf'], {}, []))

    def test_a_file_the_printer_does_not_have_is_said_so_from_its_answer(self):
        """Review 6, defect 6, and delivery review 2, defects 1 and 2: the delete is always
        sent, and NOT_ON_PRINTER comes from the printer's own answer that there is no such
        file. The library logs that answer as a failure; it is kept off the daemon's log,
        so nothing there looks like an error."""
        link, forwarded = self.forwarding_link()
        link._printer.files['other.gcode.3mf'] = b'x'
        self.assertEqual(link.delete('x.gcode.3mf'), (pr.NOT_ON_PRINTER, '550 No such file.'))
        self.assertEqual((link._printer.deleted, forwarded), (['x.gcode.3mf'], []))

    def test_the_answer_decides_and_no_listing_is_asked(self):
        """Delivery review 2, defects 1 and 2: a listing is never taken as proof either way.
        The file is on the printer though no listing shows it under the name sent, or no
        listing can be had at all: the delete is sent and the printer's answer decides."""
        listings = [['-rw-rw-rw- 1 root root 9 Nov 19 18:00 X.GCODE.3MF'],   # spelled otherwise
                    [], None, 'fails']
        for lines in listings:
            with self.subTest(lines=lines):
                link = self.link()
                link.connect()
                link._printer.files['x.gcode.3mf'] = b'x'
                if lines == 'fails':
                    link._printer.list_fails = True
                else:
                    link._printer.list_lines = lines
                self.assertEqual(link.delete('x.gcode.3mf')[0], pr.REMOVED)
                self.assertEqual(link._printer.deleted, ['x.gcode.3mf'])

    def test_a_file_never_there_is_not_said_removed_whatever_the_listing(self):
        """Delivery review 2, defect 2: the first listing failed and a second one lacked the
        name, and the file that was never there was said to be removed."""
        for list_fails in (True, False):
            with self.subTest(list_fails=list_fails):
                link = self.link()
                link.connect()
                link._printer.list_fails = list_fails
                self.assertEqual(link.delete('x.gcode.3mf')[0], pr.NOT_ON_PRINTER)

    def test_any_other_answer_is_a_delete_that_could_not_be_confirmed(self):
        """Only "there is no such file" is NOT_ON_PRINTER: a 550 that says something else,
        a 4xx, a reply ftplib would not take as success, no answer at all, or no
        connection, is UNCONFIRMED with the printer's answer, and none of it reaches the
        daemon's log as a library error."""
        cases = [
            ('delete_failure', '550 Permission denied.', '550 Permission denied.'),
            ('delete_failure', '550 Delete operation failed.', '550 Delete operation failed.'),
            ('delete_failure', '421 Timeout.', '421 Timeout.'),
            ('delete_failure', '', 'no answer'),
            ('delete_reply', '226 Odd.', '226 Odd.'),
            ('delete_raises', ConnectionRefusedError('[Errno 111] Connection refused'),
             'no connection: [Errno 111] Connection refused'),
            # Delivery review 3, defect 1: the library logs the error that ended the
            # delete, and a timeout or a reset is no answer from the printer.
            ('delete_failure', 'timed out', 'no answer: timed out'),
            ('delete_failure', '[Errno 104] Connection reset by peer',
             'no answer: [Errno 104] Connection reset by peer'),
        ]
        for field, value, answer in cases:
            with self.subTest(field=field, value=value):
                link, forwarded = self.forwarding_link()
                link._printer.files['x.gcode.3mf'] = b'x'
                setattr(link._printer, field, value)
                self.assertEqual(link.delete('x.gcode.3mf'), (pr.UNCONFIRMED, answer))
                self.assertEqual(forwarded, [])

    def test_a_connection_dropped_during_the_delete_is_said_so(self):
        """Delivery review 3, defect 1: a connection dropped during the DELE is ftplib's
        EOFError, whose text is empty, so the library logs the failure with nothing after
        it. That is no answer, and the answer says the connection dropped."""

        class Dropping(FakeBambuPrinter):
            def delete_file(self, file_path):
                import logging
                self.deleted.append(file_path)
                logging.getLogger('bambulabs_api').error('Failed to execute function: ')
                return None

        link, forwarded = self.forwarding_link(Dropping)
        self.assertEqual(link.delete('x.gcode.3mf'),
                         (pr.UNCONFIRMED, 'no answer: the connection dropped'))
        self.assertEqual(forwarded, [])

    def test_only_a_three_digit_reply_is_the_printers_answer(self):
        for answer, is_reply in [('550 Permission denied.', True), ('226 Odd.', True),
                                 ('no answer', False), ('no answer: timed out', False),
                                 ('no connection: gone', False), ('', False)]:
            with self.subTest(answer=answer):
                self.assertIs(pr.is_printer_reply(answer), is_reply)

    def test_a_200_is_a_confirmed_delete_as_ftplib_takes_it(self):
        link = self.link()
        link.connect()
        link._printer.delete_reply = '200 OK.'
        self.assertEqual(link.delete('x.gcode.3mf'), (pr.REMOVED, '200 OK.'))

    def test_delete_never_raises(self):
        class Refusing(FakeBambuPrinter):
            def delete_file(self, file_path):
                raise OSError('gone')

        link = self.link(Refusing)
        link.connect()
        link._printer.files['x.gcode.3mf'] = b'x'
        self.assertEqual(link.delete('x.gcode.3mf'), (pr.UNCONFIRMED, 'no connection: gone'))

    def test_a_delete_with_no_printer_never_raises(self):
        link = self.link()
        self.assertEqual(link.delete('x.gcode.3mf')[0], pr.UNCONFIRMED)

    def test_the_size_check_skips_a_line_it_cannot_read(self):
        link = self.link()
        link.connect()
        link._printer.list_lines = ['drwxrwxrwx 1 root root cache',
                                    '-rw-rw-rw- 1 root root 9 Nov 19 18:00 x.gcode.3mf']
        self.assertEqual(link.remote_size('x.gcode.3mf'), 9)

    def test_the_size_check_with_no_list_of_lines_lists_nothing(self):
        link = self.link()
        link.connect()
        link._printer.list_lines = None
        self.assertIsNone(link.remote_size('x.gcode.3mf'))

    def test_the_library_log_is_kept_off_the_console_and_warnings_become_one_plain_line(self):
        import logging
        forwarded = []
        link = pr.PrinterLink('10.0.0.42', '01P00A', '12345678',
                              printer_factory=FakeBambuPrinter, log=forwarded.append)
        link.connect()
        library = logging.getLogger('bambulabs_api')
        self.assertFalse(library.propagate)
        library.info('Connecting to FTP server...')
        library.warning('Connection failed with result code 5')
        self.assertEqual(forwarded, ['printer library said: Connection failed with result code 5'])

    def test_the_library_log_can_be_written_from_another_thread_after_this_one(self):
        """Regression: the handler once overrode logging.Handler.release, so its lock was
        never released and the library's MQTT thread hung on its first log line. Found by
        the simulated printer; the lock is reentrant, so only a second thread shows it."""
        import logging
        import threading
        pr.take_over_library_log(None)
        library = logging.getLogger('bambulabs_api')
        library.info('first, on this thread')
        done = threading.Event()
        thread = threading.Thread(target=lambda: (library.info('second'), done.set()),
                                  daemon=True)
        thread.start()
        self.assertTrue(done.wait(5), 'the library log handler is still locked')

    def test_the_report_age_grows_while_the_report_stands_still(self):
        clock = FakeClock()
        link = pr.PrinterLink('10.0.0.42', '01P00A', '12345678',
                              printer_factory=FakeBambuPrinter, clock=clock)
        link.connect()
        link._printer.report = dict(H2S['running'])
        self.assertEqual(link.snapshot()['report_age_s'], 0)
        clock.advance(90)
        self.assertEqual(link.snapshot()['report_age_s'], 90)
        link._printer.report = dict(H2S['running'], mc_percent=43)
        self.assertEqual(link.snapshot()['report_age_s'], 0)

    def test_old_figures_keep_their_old_age_across_a_disconnect(self):
        """Defect 4 (a): the library keeps its last document across a disconnect. Back on
        a reconnect where the printer said nothing, it is the same old document, so its
        age goes on from when it arrived; it never reads as new."""
        clock = FakeClock()
        link = pr.PrinterLink('10.0.0.42', '01P00A', '12345678',
                              printer_factory=FakeBambuPrinter, clock=clock)
        link.connect()
        link._printer.report = dict(H2S['running'])
        self.assertEqual(link.snapshot()['report_age_s'], 0)
        link._printer.connected = False
        clock.advance(300)
        gone = link.snapshot()
        self.assertEqual((gone['state'], gone['report_age_s']), (pr.UNREACHABLE, 300))
        link._printer.connected = True
        back = link.snapshot()
        self.assertEqual((back['state'], back['report_age_s']), (pr.RUNNING, 300))

    def test_the_age_is_that_of_the_last_document_the_library_says_arrived(self):
        clock = FakeClock()

        class Hooked(FakeBambuPrinter):
            def __init__(self, *a):
                super().__init__(*a)
                self.mqtt_client = type('Client', (), {'on_message_handler': None,
                                                       'pushall': lambda s: asks.append(1)})()

        asks = []
        heard = []
        link = pr.PrinterLink('10.0.0.42', '01P00A', '12345678', printer_factory=Hooked,
                              clock=clock)
        link.on_document = lambda: heard.append(clock())
        printer = link.connect()
        printer.report = dict(H2S['running'])
        printer.mqtt_client.on_message_handler(None, None, None, None)   # a document
        clock.advance(40)
        # The same document again, unchanged, still counts as the printer speaking.
        printer.mqtt_client.on_message_handler(None, None, None, None)
        clock.advance(5)
        self.assertEqual(link.snapshot()['report_age_s'], 5)
        self.assertEqual(heard, [1000.0, 1040.0])
        link.request_report()
        self.assertEqual(asks, [1])

    def test_the_picture_is_whole_only_after_a_main_state_since_the_connection(self):
        """Review 4, defect 1: the library keeps its merged document across a reconnect,
        so a partial document merged onto the last connection's IDLE read as a fresh idle
        printer. Until a document carrying `gcode_state` arrives on this connection the
        snapshot says `whole: False` (and the run loop does not count it as fresh)."""
        import json as _json

        class Message:
            def __init__(self, document):
                self.payload = _json.dumps(document).encode()

        class Hooked(FakeBambuPrinter):
            def __init__(self, *a):
                super().__init__(*a)
                self.mqtt_client = type('Client', (), {'on_message_handler': None,
                                                       'on_connect_handler': None})()

        link = pr.PrinterLink('10.0.0.42', '01P00A', '12345678', printer_factory=Hooked,
                              clock=FakeClock())
        printer = link.connect()
        printer.report = dict(H2S['idle'])          # left from before: merged, old
        self.assertIs(link.snapshot()['whole'], False)
        hook = printer.mqtt_client.on_message_handler
        printer.report = dict(H2S['idle'], mc_percent=43, subtask_name='someone_elses')
        hook(None, None, None, Message({'print': {'mc_percent': 43}}))   # partial
        self.assertIs(link.snapshot()['whole'], False)
        hook(None, None, None, Message({'print': {'gcode_state': 'IDLE'}}))
        self.assertIs(link.snapshot()['whole'], True)
        hook(None, None, None, Message({'print': {'mc_percent': 44}}))   # partial again
        self.assertIs(link.snapshot()['whole'], True)
        printer.mqtt_client.on_connect_handler(None, None, None, None, None, None)
        self.assertIs(link.snapshot()['whole'], False)                   # a reconnect
        hook(None, None, None, type('Garbled', (), {'payload': b'not json'})())
        self.assertIs(link.snapshot()['whole'], False)
        hook(None, None, None, None)                                     # no message
        self.assertIs(link.snapshot()['whole'], False)

    def test_request_report_never_raises(self):
        link = self.link()
        link.request_report()                        # not connected
        link.connect()
        link.request_report()                        # a stand-in without a client

    def test_a_multi_megabyte_upload_keeps_small_bounded_evidence(self):
        """Defect 2: the library logs each 32 kB block's bytes at debug level, and an
        error line per block when the transfer goes wrong. Neither the memory an upload
        holds nor the evidence it returns grows with the file."""
        import logging
        import tracemalloc

        class Chatty(FakeBambuPrinter):
            def upload_file(self, file_obj, filename):
                logger = logging.getLogger('bambulabs_api')
                sent = 0
                while True:
                    block = file_obj.read(32768)
                    if not block:
                        break
                    sent += len(block)
                    logger.debug(f'Uploaded {block} bytes')
                    logger.error(f'Failed to execute function: block {sent} {block[:4000]}')
                file_obj.close()
                self.files[filename] = b'x' * 10   # a short file: the upload failed
                return None

        link = self.link(Chatty)
        link.connect()
        path = self.sliced_file(content=b'\x00\x01' * (4 * 1024 * 1024))      # 8 MB
        # Only the daemon's own handler, as in the daemon: pytest's log capture attaches
        # handlers of its own to the logger, which keep every line for its report.
        library = logging.getLogger('bambulabs_api')
        saved = library.handlers[:]
        library.handlers[:] = [pr._LIBRARY_LOG]
        tracemalloc.start()
        try:
            with self.assertRaises(pr.UploadFailed) as caught:
                link.upload(path, 'x.gcode.3mf')
            _current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            library.handlers[:] = saved
        self.assertLess(peak, 2 * 1024 * 1024)
        detail = caught.exception.detail
        self.assertLess(len(detail), (pr.CAPTURE_LINES + 1) * (pr.CAPTURE_LINE_CHARS + 2)
                        + 200)
        self.assertIn('more lines from the printer library were dropped', detail)
        self.assertNotIn('Uploaded', detail)          # the debug block lines are never kept

    def test_the_simulated_printer_ports_reach_the_library(self):
        class Lib(FakeBambuPrinter):
            def __init__(self, *a):
                super().__init__(*a)
                self.mqtt_client = type('M', (), {'_port': 8883})()
                self.ftp_client.port = 990

        link = pr.PrinterLink('127.0.0.1', 'S', 'c', printer_factory=Lib,
                              ports={'mqtt': 18883, 'ftps': 10990})
        # The ports are applied only to the real library's object; a factory is used as
        # it is. So this pins only that a factory-made printer is left alone.
        printer = link.connect()
        self.assertEqual((printer.mqtt_client._port, printer.ftp_client.port), (8883, 990))

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
        with self.assertRaisesRegex(pr.UploadFailed, 'ftps refused'):
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
