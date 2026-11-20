"""Shared stand-ins for the daemon's tests: a clock, the relay client, the printer link and
bambulabs_api's Printer. None of them touches a socket, the real clock or the home
directory."""
import json
import os

from penguin_delivery_daemon import printer as pr

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')

with open(os.path.join(FIXTURES, 'h2s_status.json')) as _fh:
    H2S = json.load(_fh)

IDLE = {'state': pr.IDLE, 'file': '', 'percent': None, 'remaining_min': None,
        'layer': 0, 'layers': 0, 'error': None,
        'printer': {'model': 'H2S', 'name': 'Shop H2S', 'serial': '01P00A'}}

JOB = {'id': 'j8f3a2c1', 'download_path': '/printer/download/tok',
       'filename': 'sample_part.gcode.3mf', 'created_at': 1_789_300_000}
SUFFIXED = 'sample_part-j8f3a2c1.gcode.3mf'

#: What a successful upload returns. The pinned bambulabs_api's Printer.upload_file returns
#: what ftplib's storbinary returns, the server's final reply line; PrinterLink.upload hands
#: it back unchanged. After a failure during the transfer the library returns None instead.
FTP_TRANSFER_COMPLETE = '226 Transfer complete.'


def running(file_name):
    return dict(IDLE, state=pr.RUNNING, file=file_name, percent=3, remaining_min=41)


class FakeClock:
    """A monotonic clock that moves only when a test or a sleep moves it."""

    def __init__(self, now=1000.0):
        self.now = now
        self.slept = []

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class FakeRelay:
    """Stands in for RelayClient. Set an *_error to make the next call of that kind fail."""

    def __init__(self, token=None):
        self.token = token
        self.exchanges = []
        self.syncs = []
        self.acks = []
        self.downloads = []
        self.exchange_result = 'signed'
        self.exchange_error = None
        self.sync_job = None
        self.sync_error = None
        self.ack_result = True
        self.ack_error = None
        self.download_error = None
        self.content = b'3mf-bytes'

    def exchange(self, code):
        self.exchanges.append(code)
        if self.exchange_error:
            error, self.exchange_error = self.exchange_error, None
            raise error
        self.token = self.exchange_result
        return self.exchange_result

    def sync(self, snapshot):
        self.syncs.append(snapshot)
        if self.sync_error:
            error, self.sync_error = self.sync_error, None
            raise error
        job, self.sync_job = self.sync_job, None
        return job

    def ack(self, job_id, ok, error=None):
        self.acks.append((job_id, ok, error))
        if self.ack_error:
            failure, self.ack_error = self.ack_error, None
            raise failure
        return self.ack_result

    def download(self, path, dest):
        self.downloads.append((path, dest))
        if self.download_error:
            raise self.download_error
        with open(dest, 'wb') as fh:
            fh.write(self.content)


class FakePrinter:
    """Stands in for PrinterLink. `starts_running` makes start() behave like a printer that
    picks the file up at once and reports it under the name it was uploaded as."""

    def __init__(self, snapshot=None, starts_running=False):
        self._snapshot = snapshot or dict(IDLE)
        self.uploads = []
        self.starts = []
        self.upload_error = None
        self.start_result = True
        self.starts_running = starts_running
        self.snapshot_calls = 0

    def set(self, snapshot):
        self._snapshot = snapshot

    def snapshot(self):
        self.snapshot_calls += 1
        return dict(self._snapshot)

    def upload(self, local_path, remote_name):
        if self.upload_error:
            raise self.upload_error
        with open(local_path, 'rb') as fh:
            self.uploads.append((remote_name, fh.read()))
        return FTP_TRANSFER_COMPLETE         # what PrinterLink.upload returns on success

    def start(self, remote_name):
        self.starts.append(remote_name)
        if self.starts_running and self.start_result:
            self.set(running(remote_name))
        return self.start_result


class StepExecutor:
    """Holds a submitted job until the test releases it, the way a job thread would still
    be running while the loop keeps ticking."""

    def __init__(self):
        self.pending = []
        self.shutdowns = 0

    def submit(self, fn, *args, **kwargs):
        self.pending.append((fn, args, kwargs))

    def release(self):
        fn, args, kwargs = self.pending.pop(0)
        fn(*args, **kwargs)

    def shutdown(self, wait=True):
        self.shutdowns += 1


class FakeBambuPrinter:
    """Stands in for bambulabs_api.Printer, with the method names and return conventions of
    the pinned bambulabs_api (daemon/pyproject.toml): upload_file returns the FTP server's
    final reply on success and None when its own FTPS code caught a failure during the
    transfer (a refused connection or login raises instead)."""

    def __init__(self, ip_address, access_code, serial):
        self.ip_address, self.access_code, self.serial = ip_address, access_code, serial
        self.report = {}
        self.started = None
        self.uploaded = None
        self.mqtt_running = False
        self.connected = True
        self.upload_returns_none = False
        self.report_after_start = None

    def mqtt_start(self):
        self.mqtt_running = True

    def mqtt_stop(self):
        self.mqtt_running = False

    def camera_start(self):          # must never be called: Pillow frames on a small Pi
        raise AssertionError('the daemon must not start the camera')

    def mqtt_client_connected(self):
        return self.connected

    def mqtt_dump(self):
        return {'print': self.report}

    def upload_file(self, file_obj, filename):
        data = file_obj.read()
        file_obj.close()
        if self.upload_returns_none:
            return None              # what the library returns after logging a failure
        self.uploaded = (filename, data)
        return FTP_TRANSFER_COMPLETE

    def start_print(self, filename, plate_number, use_ams=True, ams_mapping=(0,),
                    skip_objects=None, flow_calibration=True):
        self.started = {'filename': filename, 'plate_number': plate_number,
                        'use_ams': use_ams, 'ams_mapping': list(ams_mapping),
                        'flow_calibration': flow_calibration}
        if self.report_after_start is not None:
            self.report = self.report_after_start(filename)
        return True
