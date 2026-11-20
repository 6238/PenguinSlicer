"""The printer, played by a stand-in with PrinterLink's methods.

It keeps the bytes it was sent, and once started it reports `running` under the name it
was uploaded as, without the extension, the way the H2S reports `subtask_name` (the
daemon's `job_name`). It is not the simulated printer (`delivery/simulator/`), which plays
the printer's own protocols over sockets; this one sits at the PrinterLink seam.
"""

import threading

IDENTITY = {'model': 'Stand-in', 'name': 'Stand-in printer', 'serial': 'STANDIN0001'}


def _stem(remote_name):
    return remote_name[:-len('.gcode.3mf')] if remote_name.endswith('.gcode.3mf') else remote_name


class StandInPrinter:
    def __init__(self, on_change=None):
        self._lock = threading.Lock()
        self._on_change = on_change
        self.received = {}                  # remote name -> bytes
        self.started = []
        self.deleted = []
        self._snapshot = self._idle()

    @staticmethod
    def _idle():
        return {'state': 'idle', 'file': '', 'job_name': '', 'percent': None,
                'remaining_min': None, 'layer': 0, 'layers': 0, 'error': None,
                'stage_code': 255, 'stage': 'idle', 'stage_label': 'Idle',
                'printer': dict(IDENTITY)}

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

    def upload(self, local_path, remote_name, *, progress=None, cancelled=None):
        with open(local_path, 'rb') as fh:
            data = fh.read()
        with self._lock:
            self.received[remote_name] = data
        if progress is not None:
            progress(len(data), len(data))
        self._change(f'received {remote_name} ({len(data)} bytes)')
        return f'the printer has all {len(data)} bytes'

    def delete(self, remote_name):
        with self._lock:
            self.received.pop(remote_name, None)
            self.deleted.append(remote_name)
        return True

    def start(self, remote_name):
        with self._lock:
            if remote_name not in self.received:
                return False
            self.started.append(remote_name)
            self._snapshot = dict(self._idle(), state='running', file=_stem(remote_name),
                                  job_name=_stem(remote_name), percent=0, remaining_min=1,
                                  layers=1, stage_code=0, stage='printing',
                                  stage_label='Printing')
        self._change(f'printing {remote_name}')
        return True

    def finish(self):
        """The print ends: the H2S reports FINISH under the same name."""
        with self._lock:
            self._snapshot = dict(self._snapshot, state='finished', percent=100,
                                  remaining_min=0)
        self._change('finished')
