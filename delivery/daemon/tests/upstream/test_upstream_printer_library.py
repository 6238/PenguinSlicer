"""The upstream check for the printer library (`make test-upstream`).

Every behaviour of the pinned `bambulabs_api` (daemon/pyproject.toml) that the daemon
relies on, tested against the INSTALLED library, with no printer and no network: the
library's objects are built for real, and only their sockets are replaced. When a new
version breaks an assumption, the test that fails names it in its first line. The fakes in
daemon_fakes.py copy these behaviours for the fast suite, so a failure here also means
the fakes are out of date.

The simulated printer's suite (`delivery/simulator/`, also run by `make test-upstream`)
drives the same library over real loopback sockets."""
import inspect
import io
import json
import logging
import socket

import pytest

from penguin_delivery_daemon import printer as pr

bambulabs_api = pytest.importorskip('bambulabs_api')
from bambulabs_api import ftp_client as library_ftp       # noqa: E402
from bambulabs_api.states_info import GcodeState, PrintStatus  # noqa: E402

pytestmark = pytest.mark.upstream


def make_printer():
    return bambulabs_api.Printer('192.0.2.1', 'not-a-code', 'SERIAL0001')


def test_the_printer_is_built_from_ip_access_code_and_serial_without_any_network():
    """PROTECTS: PrinterLink._make calls Printer(ip, access_code, serial), and building it
    opens no socket (pair and status build one before anything is known to answer)."""
    printer = make_printer()
    assert (printer.ip_address, printer.access_code, printer.serial) == \
        ('192.0.2.1', 'not-a-code', 'SERIAL0001')


def test_the_calls_the_daemon_makes_exist_with_the_arguments_it_passes():
    """PROTECTS: every call in printer.py, by name and argument."""
    printer = make_printer()
    for name in ('mqtt_start', 'mqtt_stop', 'mqtt_client_connected', 'mqtt_dump',
                 'upload_file', 'start_print', 'delete_file'):
        assert callable(getattr(printer, name)), name
    start = inspect.signature(printer.start_print).parameters
    assert list(start)[:2] == ['filename', 'plate_number']
    assert {'use_ams', 'ams_mapping', 'flow_calibration'} <= set(start)
    assert list(inspect.signature(printer.upload_file).parameters)[:2] == ['file', 'filename']
    assert callable(printer.ftp_client.list_directory)


def test_each_status_document_reaches_the_message_hook_and_outlives_a_disconnect():
    """PROTECTS: PrinterLink measures the report's age from `mqtt_client.on_message_handler`,
    called once per document after it is merged, and relies on the library keeping its
    last document across a disconnect (so old figures come back with their old age)."""
    printer = make_printer()
    client = printer.mqtt_client
    calls = []
    client.on_message_handler = lambda *args: calls.append(len(args))
    message = type('Message', (), {'payload': json.dumps({'print': {'mc_percent': 7}})})
    client._on_message(client._client, None, message)
    assert calls == [4]
    assert printer.mqtt_dump()['print']['mc_percent'] == 7
    client._on_disconnect(client._client, None, None, None, None)
    assert printer.mqtt_dump()['print']['mc_percent'] == 7


def test_the_message_hook_gets_the_message_and_the_connect_hook_fires_on_each_connect():
    """PROTECTS: a whole picture (review 4, defect 1). PrinterLink reads the MQTT message,
    the hook's last argument, to see whether the document named `gcode_state`, and resets
    the picture to "not whole" from `mqtt_client.on_connect_handler`, which the library
    calls on every connect, its own reconnects included. The library merges a partial
    document onto what it holds, so without this a partial document after a reconnect
    reads as a whole one."""
    printer = make_printer()
    client = printer.mqtt_client
    seen, connects = [], []
    client.on_message_handler = lambda *args: seen.append(args[-1])
    client.on_connect_handler = lambda *args: connects.append(len(args))
    whole = type('Message', (), {'payload': json.dumps({'print': {'gcode_state': 'IDLE'}})})
    partial = type('Message', (), {'payload': json.dumps({'print': {'mc_percent': 3}})})
    client._on_message(client._client, None, whole)
    client._on_message(client._client, None, partial)
    assert [m.payload for m in seen] == [whole.payload, partial.payload]
    merged = printer.mqtt_dump()['print']
    assert (merged['gcode_state'], merged['mc_percent']) == ('IDLE', 3)   # merged
    client.pushall_aggressive = False         # no publish from inside the test
    success = type('Code', (), {'is_failure': False, '__eq__': lambda s, o: o == 0})()
    client._on_connect(client._client, None, None, success, None)
    assert connects == [6]


def test_pushall_and_the_paho_client_disconnect_exist():
    """PROTECTS: PrinterLink.request_report calls mqtt_client.pushall(), and disconnect()
    calls the paho client's disconnect() before mqtt_stop() so the network thread ends at
    once instead of after its one-second poll."""
    printer = make_printer()
    assert callable(printer.mqtt_client.pushall)
    assert callable(printer.mqtt_client._client.disconnect)


def test_the_ftps_client_has_the_unwrap_option_and_uses_it_in_storbinary():
    """PROTECTS: PrinterLink sets ftp_client.ftps.unwrap = True so the upload's data
    connection is closed with a TLS shutdown (TLS 1.3 otherwise loses the file's end)."""
    printer = make_printer()
    assert printer.ftp_client.ftps.unwrap is False                  # the library's default
    assert 'self.unwrap' in inspect.getsource(library_ftp.ImplicitFTP_TLS.storbinary)
    link = pr.PrinterLink('192.0.2.1', 'SERIAL0001', 'not-a-code')
    assert link._make().ftp_client.ftps.unwrap is True


def test_the_ports_the_simulated_printer_moves_are_where_printer_link_sets_them():
    """PROTECTS: PrinterLink(ports=...) sets ftp_client.port and mqtt_client._port, and
    both are read only when connecting."""
    printer = make_printer()
    assert printer.ftp_client.port == 990
    assert printer.mqtt_client._port == 8883


def test_the_mqtt_client_lets_printer_link_suppress_callback_exceptions():
    """PROTECTS: PrinterLink sets mqtt_client._client.suppress_exceptions, so one status
    document that is not JSON cannot end the library's network thread."""
    printer = make_printer()
    assert printer.mqtt_client._client.suppress_exceptions is False   # the default
    with pytest.raises(json.JSONDecodeError):
        printer.mqtt_client._on_message(None, None, type('M', (), {'payload': b'not json'}))


def test_status_documents_are_merged_into_mqtt_dump_print():
    """PROTECTS: map_status reads mqtt_dump()['print'], which merges every document the
    printer sent (a field missing from one delta keeps its last value)."""
    printer = make_printer()
    client = printer.mqtt_client
    for doc in ({'print': {'gcode_state': 'RUNNING', 'mc_percent': 1, 'subtask_name': 'p'}},
                {'print': {'mc_percent': 2}}):
        client._on_message(None, None, type('M', (), {'payload': json.dumps(doc).encode()}))
    assert printer.mqtt_dump()['print'] == {'gcode_state': 'RUNNING', 'mc_percent': 2,
                                            'subtask_name': 'p'}


def test_the_gcode_states_are_the_ones_map_status_knows():
    """PROTECTS: GCODE_STATE_MAP covers every GcodeState the library names."""
    assert {state.value for state in GcodeState} == set(pr.GCODE_STATE_MAP)


def test_the_print_stages_are_the_ones_printer_stages_names():
    """PROTECTS: PRINTER_STAGES and STG_PAUSED against the library's PrintStatus: the same
    numbers, and every PAUSED_* (and M400_PAUSE) counted as paused."""
    # UNKNOWN (None) is the library's answer for a number it does not know, which
    # printer_stage names `stage_<n>` instead.
    numbers = {status.value for status in PrintStatus if status.value is not None}
    assert numbers == set(pr.PRINTER_STAGES)
    paused = {s.value for s in PrintStatus
              if s.name.startswith('PAUSED_') or s.name == 'M400_PAUSE'}
    assert paused == set(pr.STG_PAUSED)
    assert PrintStatus.IDLE.value == pr.STG_IDLE


def test_the_start_command_names_the_plate_file_and_the_ftp_url():
    """PROTECTS: start_print(name, 1, ...) sends project_file for Metadata/plate_1.gcode of
    our uploaded file, which is what makes the printer report it as subtask_name."""
    printer = make_printer()
    sent = []
    printer.mqtt_client._PrinterMQTTClient__publish_command = \
        lambda payload: sent.append(payload) or True
    assert printer.start_print('part-j8f3a2c1.gcode.3mf', pr.PLATE_NUMBER, use_ams=False,
                               ams_mapping=[0], flow_calibration=True) is True
    command = sent[0]['print']
    assert command['command'] == 'project_file'
    assert command['param'] == 'Metadata/plate_1.gcode'
    assert command['file'] == 'part-j8f3a2c1.gcode.3mf'
    assert command['url'] == 'ftp:///part-j8f3a2c1.gcode.3mf'
    assert command['use_ams'] is False


class FakeFTPS:
    """The library's ImplicitFTP_TLS with its sockets taken out."""

    def __init__(self, fail_in_transfer=None, refuse_login=False):
        self.fail_in_transfer = fail_in_transfer
        self.refuse_login = refuse_login
        self.stored = b''
        self.closed = False
        self.blocks = []
        self.timeout = None

    def connect(self, host, port):
        self.address = (host, port)

    def login(self, user, password):
        if self.refuse_login:
            raise library_ftp.ftplib.error_perm('530 Login incorrect.')

    def prot_p(self):
        return '200 PROT now Private.'

    def storbinary(self, cmd, fp, blocksize=8192, callback=None):
        while True:
            block = fp.read(blocksize)
            if not block:
                break
            self.blocks.append(len(block))
            self.stored += block
            if self.fail_in_transfer and len(self.stored) >= self.fail_in_transfer:
                raise library_ftp.ftplib.error_temp('426 Failure reading network stream.')
        return '226 Transfer complete.'

    def close(self):
        self.closed = True


def ftp_with(fake):
    client = library_ftp.PrinterFTPClient('192.0.2.1', 'not-a-code')
    client.ftps = fake
    return client


def test_a_successful_upload_returns_the_servers_final_reply_in_32k_blocks():
    """PROTECTS: PrinterLink.upload treats a '226' reply as the transfer completing, and
    its progress counts the blocks ftplib reads (32768 bytes each)."""
    fake = FakeFTPS()
    reply = ftp_with(fake).upload_file(io.BytesIO(b'x' * 70000), 'p.gcode.3mf')
    assert reply == '226 Transfer complete.'
    assert fake.blocks == [32768, 32768, 4464]
    assert fake.closed


def test_a_failure_during_the_transfer_is_logged_and_swallowed_as_none(caplog):
    """PROTECTS: known fault 2's cause. A failure inside the transfer returns None and logs
    'Failed to execute function: ...' at ERROR on the bambulabs_api logger, which is why
    PrinterLink judges by the printer's listing and takes that logger over."""
    fake = FakeFTPS(fail_in_transfer=1)
    logger = logging.getLogger('bambulabs_api')
    previous = logger.propagate
    logger.propagate = True
    try:
        with caplog.at_level(logging.ERROR, logger='bambulabs_api'):
            assert ftp_with(fake).upload_file(io.BytesIO(b'abc'), 'p.gcode.3mf') is None
    finally:
        logger.propagate = previous
    assert 'Failed to execute function: 426 Failure reading network stream.' in caplog.text


def test_an_exception_from_the_file_object_is_swallowed_too():
    """PROTECTS: a cancel raised by PrinterLink's reader inside the transfer comes back as
    None, which is why PrinterLink remembers that it cancelled."""

    class Cancelling(io.BytesIO):
        def read(self, size=-1):
            raise pr.UploadCancelled('cancelled')

    assert ftp_with(FakeFTPS()).upload_file(Cancelling(b'abc'), 'p.gcode.3mf') is None


def test_a_refused_login_raises_out_of_the_library():
    """PROTECTS: a wrong access code is outside the swallowing try, so it raises (and
    PrinterLink reports 'the printer refused the upload')."""
    with pytest.raises(library_ftp.ftplib.error_perm):
        ftp_with(FakeFTPS(refuse_login=True)).upload_file(io.BytesIO(b'a'), 'p.gcode.3mf')


def test_the_printer_closes_the_file_object_whatever_happens():
    """PROTECTS: PrinterLink.upload leaves the closing to the library on success."""
    printer = make_printer()
    printer.ftp_client.ftps = FakeFTPS()
    handle = io.BytesIO(b'abc')
    printer.upload_file(handle, 'p.gcode.3mf')
    assert handle.closed


def test_the_upload_timeout_printer_link_sets_is_the_one_ftplib_uses():
    """PROTECTS: PrinterLink sets ftp_client.ftps.timeout; ftplib reads self.timeout when
    connect() is called without one, which is how the library calls it."""
    ftps = library_ftp.ImplicitFTP_TLS()
    assert hasattr(ftps, 'timeout')
    source = inspect.getsource(library_ftp.PrinterFTPClient.connect_and_run)
    assert 'self.ftps.connect(host=self.server_ip, port=self.port)' in source


def test_the_listing_is_returned_as_reply_and_lines():
    """PROTECTS: PrinterLink.remote_size reads list_directory() as (reply, LIST lines)."""

    class Listing(FakeFTPS):
        def retrlines(self, cmd, callback):
            callback('-rw-rw-rw- 1 root root 9 Nov 19 18:00 p-j8f3a2c1.gcode.3mf')
            return '226 Transfer complete.'

    reply, lines = ftp_with(Listing()).list_directory()
    assert reply.startswith('226')
    link = pr.PrinterLink('192.0.2.1', 'S', 'c')
    link._printer = type('P', (), {'ftp_client': ftp_with(Listing())})()
    assert link.remote_size('p-j8f3a2c1.gcode.3mf') == 9


def test_a_delete_returns_the_reply_or_logs_and_swallows_the_printers_answer():
    """PROTECTS: PrinterLink.delete words its outcome from the printer's answer: the
    library's delete_file returns the server's reply when ftplib takes it as success (250
    or 200), and for a 5xx or 4xx logs 'Failed to execute function: <the reply>' and
    returns None. ftplib's own delete is used here, with only the socket taken out."""

    class Answering(library_ftp.ImplicitFTP_TLS):
        def __init__(self, answer):
            super().__init__()
            self.answer, self.sent = answer, []

        def connect(self, host, port):
            pass

        def login(self, user, password):
            pass

        def prot_p(self):
            return '200 PROT now Private.'

        def putcmd(self, line):
            self.sent.append(line)

        def getmultiline(self):
            return self.answer

        def close(self):
            pass

    pr.take_over_library_log(None)
    for answer, outcome in [('250 Delete operation successful.', pr.REMOVED),
                            ('550 No such file.', pr.NOT_ON_PRINTER),
                            ('550 Permission denied.', pr.UNCONFIRMED),
                            ('421 Timeout.', pr.UNCONFIRMED)]:
        client = ftp_with(Answering(answer))
        link = pr.PrinterLink('192.0.2.1', 'S', 'c')
        link._printer = type('P', (), {'delete_file': staticmethod(client.delete_file)})()
        assert link.delete('p-j8f3a2c1.gcode.3mf') == (outcome, answer)
        assert client.ftps.sent == ['DELE p-j8f3a2c1.gcode.3mf']

    # Delivery review 3, defect 1: when the printer gives no answer, the library logs the
    # error that ended the delete (a timeout's text, or nothing for ftplib's EOFError on a
    # dropped connection), and PrinterLink.delete says there was no answer.
    class Silent(Answering):
        def __init__(self, error):
            super().__init__(None)
            self.error = error

        def getmultiline(self):
            raise self.error

    for error, answer in [(socket.timeout('timed out'), 'no answer: timed out'),
                          (EOFError(), 'no answer: the connection dropped')]:
        client = ftp_with(Silent(error))
        link = pr.PrinterLink('192.0.2.1', 'S', 'c')
        link._printer = type('P', (), {'delete_file': staticmethod(client.delete_file)})()
        assert link.delete('p-j8f3a2c1.gcode.3mf') == (pr.UNCONFIRMED, answer)
        assert client.ftps.sent == ['DELE p-j8f3a2c1.gcode.3mf']
