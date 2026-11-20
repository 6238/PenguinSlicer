"""The printer, played by a stand-in with PrinterLink's four methods.

It behaves like the fake printer in the daemon's own tests: it keeps the bytes it was sent,
and once started it reports `running` with the file under the name it was uploaded as. It
is deliberately NOT a simulated Bambu printer (that is the hardening pass): a real H2S
reports a different `file`, which is the known fault the daemon's tests pin.
"""

import threading

IDENTITY = {'model': 'Stand-in', 'name': 'Stand-in printer', 'serial': 'STANDIN0001'}


class StandInPrinter:
    def __init__(self, on_change=None):
        self._lock = threading.Lock()
        self._on_change = on_change
        self.received = {}                  # remote name -> bytes
        self.started = []
        self._snapshot = self._idle()

    @staticmethod
    def _idle():
        return {'state': 'idle', 'file': '', 'percent': None, 'remaining_min': None,
                'layer': 0, 'layers': 0, 'error': None, 'printer': dict(IDENTITY)}

    def _change(self, text):
        if self._on_change:
            self._on_change(text)

    def connect(self):
        return self

    def disconnect(self):
        pass

    def snapshot(self):
        with self._lock:
            return dict(self._snapshot, printer=dict(self._snapshot['printer']))

    def upload(self, local_path, remote_name):
        with open(local_path, 'rb') as fh:
            data = fh.read()
        with self._lock:
            self.received[remote_name] = data
        self._change(f'received {remote_name} ({len(data)} bytes)')
        return '226 Transfer complete.'     # the FTP reply PrinterLink.upload returns

    def start(self, remote_name):
        with self._lock:
            if remote_name not in self.received:
                return False
            self.started.append(remote_name)
            self._snapshot = dict(self._idle(), state='running', file=remote_name,
                                  percent=0, remaining_min=1, layers=1)
        self._change(f'printing {remote_name}')
        return True
