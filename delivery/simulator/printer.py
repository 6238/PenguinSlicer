"""A simulated Bambu H2S for the daemon to talk to over real loopback sockets.

It speaks as much of the printer's two protocols as the pinned printer library uses:

- **MQTT 3.1.1 over TLS** (the printer's port 8883): CONNECT with user `bblp` and the
  access code (a wrong code is refused with return code 5), SUBSCRIBE to
  `device/<serial>/report`, PUBLISH of status documents there, PUBLISH of commands to
  `device/<serial>/request` (`pushall` answers with the whole status; `project_file`
  starts the uploaded file), PINGREQ, DISCONNECT. QoS 0 only, as the library uses it.
- **Implicit FTPS** (the printer's port 990): TLS from the first byte; USER, PASS (the
  access code), PBSZ, PROT P, TYPE, PASV, STOR, LIST, DELE, QUIT, with the data
  connection in TLS too.

Both listen on 127.0.0.1 on ports the system picks. The certificate is a throwaway
self-signed one made with `openssl` at start, in a private temporary directory.

What happens is scripted by a scenario (scenarios/*.json, see scenarios/README.md): the
idle status, how the upload is answered, how the start command is answered, and the
status documents of the print, which the caller plays one step at a time with `step()`.
Nothing advances on its own, so a test decides every moment; the waits are events.

The sequences are INVENTED from the one real status document the first hardware test
recorded (daemon/tests/fixtures/h2s_status.json, `running_as_reported_by_h2s`) and from
what the hardware test notes say the H2S reports. `python -m penguin_delivery_daemon
record` captures real ones; a recording replaces a scenario's `print` steps as it is.
"""

import json
import os
import select
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import threading

SCENARIOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scenarios')


def load_scenario(name):
    """A scenario by name. One that names a `recording` (a file `record` wrote, beside the
    scenarios) takes its print steps from the recording, document by document."""
    with open(os.path.join(SCENARIOS, f'{name}.json'), encoding='utf-8') as fh:
        scenario = json.load(fh)
    if scenario.get('base'):
        # A failure scenario says only what differs from the scenario it is based on.
        scenario = {**load_scenario(scenario['base']), **scenario}
    if scenario.get('recording'):
        scenario['print'] = read_recording(os.path.join(SCENARIOS, scenario['recording']))
    return scenario


def read_recording(path):
    """The status documents of a recording, in order: what `record` saves, one JSON line
    each, `{"t": seconds, "print": {...}}`."""
    with open(path, encoding='utf-8') as fh:
        return [json.loads(line)['print'] for line in fh if line.strip()]


def scenario_names():
    return sorted(name[:-5] for name in os.listdir(SCENARIOS) if name.endswith('.json'))


def _make_certificate(folder):
    key, cert = os.path.join(folder, 'key.pem'), os.path.join(folder, 'cert.pem')
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout',
                    key, '-out', cert, '-days', '1', '-subj', '/CN=simulated-printer'],
                   check=True, capture_output=True, timeout=60)
    return cert, key


def _fill(value, names):
    """Put the uploaded file's names into a scenario's status document."""
    if isinstance(value, str):
        return value.format(**names)
    if isinstance(value, dict):
        return {k: _fill(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, names) for v in value]
    return value


# --- MQTT ---------------------------------------------------------------------------------

def _read_exact(sock, count):
    data = b''
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError('closed')
        data += chunk
    return data


def _read_packet(sock):
    first = _read_exact(sock, 1)[0]
    multiplier, length = 1, 0
    while True:
        byte = _read_exact(sock, 1)[0]
        length += (byte & 0x7F) * multiplier
        if not byte & 0x80:
            break
        multiplier *= 128
    return first >> 4, first & 0x0F, _read_exact(sock, length) if length else b''


def _packet(kind, flags, body):
    length, encoded = len(body), b''
    while True:
        byte = length % 128
        length //= 128
        encoded += bytes([byte | (0x80 if length else 0)])
        if not length:
            break
    return bytes([(kind << 4) | flags]) + encoded + body


def _string(data, offset):
    (size,) = struct.unpack_from('!H', data, offset)
    return data[offset + 2:offset + 2 + size].decode('utf-8'), offset + 2 + size


def _encode_string(text):
    raw = text.encode('utf-8')
    return struct.pack('!H', len(raw)) + raw


class SimulatedPrinter:
    """Start with `start()`, stop with `stop()`; or use it as a context manager."""

    def __init__(self, scenario, *, serial='SIM00H2S0001', access_code='12345678'):
        self.scenario = load_scenario(scenario) if isinstance(scenario, str) else scenario
        self.serial = serial
        self.access_code = access_code
        self.files = {}                    # name -> bytes, what the FTPS server holds
        self.commands = []                 # every command document received
        self.started = []                  # the files the printer started
        self.published = []                # every status document sent
        self.logins = []                   # (protocol, accepted)
        self.status = dict(self.scenario['idle'])
        self.steps = []
        self.silent = False
        self.pushalls = 0                  # how many times the library asked for it all
        self._io_locks = {}                # id(MQTT connection) -> its I/O lock
        # False: a pushall is heard and not answered, as a printer whose stream is quiet.
        self.answer_pushall = self.scenario.get('pushall', 'answer') == 'answer'
        self._lock = threading.Lock()
        self.changed = threading.Condition()   # notified on every login, file and command
        self._subscribers = []
        self._threads = []
        self._sockets = []
        self._stopping = threading.Event()
        self._folder = None

    # -- lifecycle ---------------------------------------------------------------------

    def start(self):
        self._folder = tempfile.mkdtemp(prefix='simulated-printer-')
        cert, key = _make_certificate(self._folder)
        self._tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._tls.load_cert_chain(cert, key)
        if self.scenario.get('tls') == '1.3':
            # TLS 1.3 sends session tickets after the handshake; a client that closes the
            # upload's data connection without reading them turns the close into a reset,
            # and the end of the file can be lost. PrinterLink sets the library's `unwrap`
            # option, which closes with a TLS shutdown first; the tls13 scenario proves it.
            self._tls.minimum_version = ssl.TLSVersion.TLSv1_3
        else:
            self._tls.maximum_version = ssl.TLSVersion.TLSv1_2
        self.mqtt_port = self._listen(self._serve_mqtt)
        self.ftps_port = self._listen(self._serve_ftps)
        return self

    def stop(self):
        self._stopping.set()
        for sock in list(self._sockets):
            # shutdown, not only close: it is what wakes a thread blocked in accept or recv.
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except (OSError, ValueError):
                pass
            try:
                sock.close()
            except OSError:
                pass
        for thread in self._threads:
            thread.join(timeout=5)
        if self._folder:
            shutil.rmtree(self._folder, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        return False

    @property
    def ports(self):
        return {'mqtt': self.mqtt_port, 'ftps': self.ftps_port}

    def _note(self):
        with self.changed:
            self.changed.notify_all()

    def wait_for(self, predicate, timeout=10):
        """Wait, on an event, until `predicate()` holds for the printer's own record (a
        login seen, a file stored). Returns whether it did."""
        with self.changed:
            return self.changed.wait_for(predicate, timeout)

    def _listen(self, handler):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 0))
        server.listen(8)
        self._sockets.append(server)

        def accept():
            while not self._stopping.is_set():
                try:
                    conn, _addr = server.accept()
                except OSError:
                    return
                self._sockets.append(conn)
                thread = threading.Thread(target=self._guard, args=(handler, conn),
                                          daemon=True)
                self._threads.append(thread)
                thread.start()

        thread = threading.Thread(target=accept, daemon=True)
        self._threads.append(thread)
        thread.start()
        return server.getsockname()[1]

    def _guard(self, handler, conn):
        try:
            handler(conn)
        except (OSError, ConnectionError, ssl.SSLError, ValueError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    # -- the scenario --------------------------------------------------------------------

    def publish(self, document=None, *, raw=None):
        """Send a status document (merged into the current status) to every subscriber;
        `raw` sends bytes as they are (a document that is not JSON)."""
        with self._lock:
            if document is not None:
                self.status.update(document)
                payload = json.dumps({'print': document}).encode()
                self.published.append(dict(document))
            else:
                payload = raw
            subscribers = list(self._subscribers)
        if self.silent:
            return
        topic = f'device/{self.serial}/report'
        packet = _packet(3, 0, _encode_string(topic) + payload)
        for conn in subscribers:
            self._send(conn, packet)

    def _io_lock(self, conn):
        with self._lock:
            return self._io_locks.setdefault(id(conn), threading.Lock())

    def _send(self, conn, packet):
        """Write to an MQTT connection under its I/O lock: one TLS socket must never be
        read on one thread while another writes to it (OpenSSL's state is not shared
        safely between threads, and a status document could be lost)."""
        try:
            with self._io_lock(conn):
                conn.sendall(packet)
        except (OSError, ValueError):
            pass

    def drop_mqtt(self):
        """Cut every MQTT connection, as a printer that drops off the network does. The
        library reconnects on its own; what it hears then is the scenario's `pushall`."""
        with self._lock:
            subscribers, self._subscribers = list(self._subscribers), []
        for conn in subscribers:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except (OSError, ValueError):
                pass
            try:
                conn.close()
            except OSError:
                pass

    def step(self):
        """Send the next status document of the print. False when there is none."""
        with self._lock:
            if not self.steps:
                return False
            document = self.steps.pop(0)
        self.publish(document)
        return True

    def _start_print(self, command):
        name = command.get('file') or ''
        stem = name[:-len('.gcode.3mf')] if name.endswith('.gcode.3mf') else name
        answer = self.scenario.get('start', 'accept')
        with self._lock:
            self.commands.append(command)
        self._note()
        if answer == 'ignore' or name not in self.files:
            return
        names = {'subtask': stem, 'file': name,
                 'other': self.scenario.get('other_subtask', 'someone_elses_part')}
        self.started.append(name)
        with self._lock:
            self.steps = [_fill(step, names) for step in self.scenario.get('print', [])]
        self.step()                    # the printer answers a start at once

    # -- MQTT ------------------------------------------------------------------------------

    def _serve_mqtt(self, raw):
        conn = self._tls.wrap_socket(raw, server_side=True)
        self._sockets.append(conn)
        kind, _flags, body = _read_packet(conn)
        if kind != 1:
            return
        offset = 2 + struct.unpack_from('!H', body, 0)[0] + 1   # protocol name, level
        flags = body[offset]
        offset += 3                                              # flags, keep-alive
        _client_id, offset = _string(body, offset)
        if flags & 0x04:                                         # a will
            _topic, offset = _string(body, offset)
            _message, offset = _string(body, offset)
        username = password = None
        if flags & 0x80:
            username, offset = _string(body, offset)
        if flags & 0x40:
            password, offset = _string(body, offset)
        accepted = username == 'bblp' and password == self.access_code
        self.logins.append(('mqtt', accepted))
        self._note()
        conn.sendall(_packet(2, 0, bytes([0, 0 if accepted else 5])))
        if not accepted:
            return
        lock = self._io_lock(conn)
        while not self._stopping.is_set():
            # Wait for the client's next packet WITHOUT the lock, so status documents can
            # be written meanwhile; then read it whole and answer under the lock.
            if not conn.pending():
                readable, _, _ = select.select([conn], [], [], 0.2)
                if not readable:
                    continue
            command = None
            with lock:
                kind, flags, body = _read_packet(conn)
                if kind == 8:                                    # SUBSCRIBE
                    packet_id = body[:2]
                    topics, offset = [], 2
                    while offset < len(body):
                        topic, offset = _string(body, offset)
                        offset += 1
                        topics.append(topic)
                    conn.sendall(_packet(9, 0, packet_id + bytes([0] * len(topics))))
                elif kind == 3:                                  # PUBLISH
                    topic, offset = _string(body, 0)
                    if (flags >> 1) & 0x03:
                        offset += 2
                    command = body[offset:]
                elif kind == 12:                                 # PINGREQ
                    conn.sendall(_packet(13, 0, b''))
                elif kind == 14:                                 # DISCONNECT
                    return
            if kind == 8:
                with self._lock:
                    self._subscribers.append(conn)
            if command is not None:
                self._command(command)                           # answers via _send

    def _command(self, payload):
        try:
            document = json.loads(payload)
        except ValueError:
            return
        if 'pushing' in document:
            with self._lock:
                self.pushalls += 1
                status = dict(self.status)
            self._note()
            if self.answer_pushall:
                self.publish(status)
        command = document.get('print') or {}
        if command.get('command') == 'project_file':
            self._start_print(command)

    # -- FTPS --------------------------------------------------------------------------------

    def _serve_ftps(self, raw):
        conn = self._tls.wrap_socket(raw, server_side=True)
        self._sockets.append(conn)
        reader = conn.makefile('rb')

        def reply(line):
            conn.sendall(f'{line}\r\n'.encode())

        reply('220 Simulated printer ready.')
        data_listener = None
        user = None
        authenticated = False
        upload = self.scenario.get('upload', {})
        while not self._stopping.is_set():
            line = reader.readline()
            if not line:
                return
            verb, _, argument = line.decode('utf-8', 'replace').strip().partition(' ')
            verb = verb.upper()
            if verb == 'USER':
                user = argument
                reply('331 Password required.')
            elif verb == 'PASS':
                authenticated = user == 'bblp' and argument == self.access_code
                self.logins.append(('ftps', authenticated))
                self._note()
                reply('230 Logged in.' if authenticated else '530 Login incorrect.')
            elif not authenticated and verb != 'QUIT':
                reply('530 Please log in.')
            elif verb in ('PBSZ', 'PROT', 'TYPE'):
                reply('200 OK.')
            elif verb == 'PASV':
                data_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                data_listener.bind(('127.0.0.1', 0))
                data_listener.listen(1)
                self._sockets.append(data_listener)
                port = data_listener.getsockname()[1]
                reply(f'227 Entering Passive Mode (127,0,0,1,{port >> 8},{port & 0xFF}).')
            elif verb in ('STOR', 'LIST'):
                if data_listener is None:
                    reply('425 Use PASV first.')
                    continue
                if verb == 'STOR' and upload.get('refuse'):
                    reply('550 Could not create file.')
                    continue
                reply('150 Opening data connection.')
                data_raw, _ = data_listener.accept()
                data_listener.close()
                data_listener = None
                data = self._tls.wrap_socket(data_raw, server_side=True)
                if verb == 'LIST':
                    with self._lock:
                        files = sorted(self.files.items())
                    for name, content in files:
                        data.sendall(f'-rw-rw-rw- 1 root root {len(content)} Nov 19 18:00 '
                                     f'{name}\r\n'.encode())
                    # ftplib ends a listing with a TLS shutdown of its own and waits for
                    # ours, so the listing is closed the same way.
                    try:
                        data.unwrap().close()
                    except (OSError, ssl.SSLError):
                        data.close()
                    reply('226 Transfer complete.')
                    continue
                received = self._receive(data, upload)
                keep = received
                if upload.get('short_by'):
                    keep = received[:-upload['short_by']]
                with self._lock:
                    self.files[argument] = keep
                self._note()
                if upload.get('cut_bytes') is not None:
                    reply('426 Connection closed; transfer aborted.')
                else:
                    reply(upload.get('reply', '226 Transfer complete.'))
            elif verb == 'DELE':
                with self._lock:
                    existed = self.files.pop(argument, None) is not None
                reply('250 Deleted.' if existed else '550 No such file.')
            elif verb == 'QUIT':
                reply('221 Bye.')
                return
            else:
                reply('502 Not implemented.')

    def _receive(self, data, upload):
        received = b''
        limit = upload.get('cut_bytes')
        try:
            while True:
                if limit is not None and len(received) >= limit:
                    break                        # the printer drops the connection
                chunk = data.recv(65536)
                if not chunk:
                    # The client's TLS close (the library's `unwrap`): answer it, as a
                    # well-behaved server does, so the client's close completes.
                    try:
                        data.unwrap()
                    except (OSError, ssl.SSLError, ValueError):
                        pass
                    break
                received += chunk
        except (OSError, ssl.SSLError):
            pass
        finally:
            try:
                data.close()
            except OSError:
                pass
        return received
