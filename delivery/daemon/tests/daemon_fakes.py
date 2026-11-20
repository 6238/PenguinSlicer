"""Shared stand-ins for the daemon's tests: a clock, the relay client, the printer link and
bambulabs_api's Printer. None of them touches a socket, the real clock or the home
directory."""
import json
import os
import sys

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


class SimulatedTimeExceeded(BaseException):
    """A test's injected sleep ran past its bound. A BaseException, so no `except
    Exception` in the daemon swallows it: it reaches pytest with its message."""


#: The most simulated seconds, and the most calls, one injected sleep may add up to in a
#: test. Far beyond any test's honest waits (the longest is a day of staleness), far below
#: a wait with no end, which then fails in seconds instead of hanging the suite.
SLEEP_LIMIT_SECONDS = 2 * 24 * 3600
SLEEP_LIMIT_CALLS = 100_000


class SleepBound:
    """An injected sleep with a bound: after `seconds` simulated seconds or `calls` calls
    in all, the test fails with SimulatedTimeExceeded naming `what`."""

    def __init__(self, sleep, what, *, seconds=SLEEP_LIMIT_SECONDS, calls=SLEEP_LIMIT_CALLS):
        self.sleep = sleep
        self.what = what
        self.seconds = seconds
        self.calls = calls
        self.slept = 0.0
        self.count = 0

    def __call__(self, seconds):
        self.slept += max(0.0, float(seconds or 0))
        self.count += 1
        if self.slept > self.seconds or self.count > self.calls:
            caller = sys._getframe(1).f_code.co_name
            raise SimulatedTimeExceeded(
                f'{self.what}, sleeping in {caller}: its injected sleep passed '
                f'{self.seconds:.0f} simulated seconds or {self.calls} calls '
                f'({self.slept:.0f} s, {self.count} calls) and the test had not ended. '
                f'The wait in {caller} has no end.')
        return self.sleep(seconds)


#: The most steps (advances and sleeps together) one fake clock takes in a test. Far above
#: the busiest honest test (a day of simulated syncs, about 200,000 steps), far below a loop
#: with no end; past it the test fails with SimulatedTimeExceeded, and `slept`, which keeps
#: every sleep, never holds more than this many numbers.
CLOCK_STEP_LIMIT = 1_000_000


class StepCounter:
    """Counts a fake clock's steps and fails the test past CLOCK_STEP_LIMIT."""

    def __init__(self, what, limit=CLOCK_STEP_LIMIT):
        self.what = what
        self.limit = limit
        self.steps = 0

    def step(self):
        self.steps += 1
        if self.steps > self.limit:
            raise SimulatedTimeExceeded(
                f'{self.what} took more than {self.limit} steps and the test had not ended; '
                'a loop that moves simulated time has no end.')


class FakeClock:
    """A monotonic clock that moves only when a test or a sleep moves it."""

    def __init__(self, now=1000.0):
        self.now = now
        self.slept = []
        self.counter = StepCounter('the daemon\'s fake clock')

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.counter.step()
        self.now += seconds

    def sleep(self, seconds):
        self.counter.step()
        self.slept.append(seconds)
        self.now += seconds


class FakeRelay:
    """Stands in for RelayClient. Set an *_error to make the next call of that kind fail."""

    def __init__(self, token=None):
        self.token = token
        self.exchanges = []
        self.syncs = []
        self.progress = []
        self.acks = []
        self.ack_codes = []
        self.ack_details = []
        self.ack_fields = []
        self.downloads = []
        self.gates = []
        self.exchange_result = 'signed'
        self.exchange_error = None
        self.sync_job = None
        self.sync_error = None
        self.ack_result = True
        self.ack_error = None
        self.download_error = None
        self.download_errors = []       # one per attempt, in order; None succeeds
        self.gate_outcomes = []         # one per ask; an exception is raised; empty: 'start'
        self.content = b'3mf-bytes'

    def exchange(self, code):
        self.exchanges.append(code)
        if self.exchange_error:
            error, self.exchange_error = self.exchange_error, None
            raise error
        self.token = self.exchange_result
        return self.exchange_result

    def sync(self, snapshot, job_progress=None):
        self.syncs.append(snapshot)
        self.progress.append(job_progress)
        if self.sync_error:
            error, self.sync_error = self.sync_error, None
            raise error
        job, self.sync_job = self.sync_job, None
        return job

    def ack(self, job_id, ok, error=None, *, code=None, detail=None, fields=None):
        self.acks.append((job_id, ok, error))
        self.ack_codes.append(code)
        self.ack_details.append(detail)
        self.ack_fields.append(fields)
        if self.ack_error:
            failure, self.ack_error = self.ack_error, None
            raise failure
        return self.ack_result

    def start_gate(self, job_id, instance):
        self.gates.append((job_id, instance))
        if self.gate_outcomes:
            outcome = self.gate_outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return 'start'

    def download(self, path, dest, *, size=None, sha256=None, progress=None,
                 cancelled=None):
        self.downloads.append((path, dest))
        if self.download_errors:
            error = self.download_errors.pop(0)
            if error is not None:
                raise error
        if self.download_error:
            raise self.download_error
        with open(dest, 'wb') as fh:
            fh.write(self.content)
        if progress is not None:
            progress(len(self.content), size)


class FakePrinter:
    """Stands in for PrinterLink. `starts_running` makes start() behave like a printer that
    picks the file up at once and reports it under the name it was uploaded as."""

    def __init__(self, snapshot=None, starts_running=False):
        self._snapshot = snapshot or dict(IDLE)
        self.uploads = []
        self.starts = []
        self.deleted = []
        self.upload_error = None
        self.upload_errors = []         # one per attempt, in order; None succeeds
        self.start_result = True
        self.start_error = None
        self.starts_running = starts_running
        self.snapshot_calls = 0

    def set(self, snapshot):
        self._snapshot = snapshot

    def snapshot(self):
        self.snapshot_calls += 1
        return dict(self._snapshot)

    def upload(self, local_path, remote_name, *, progress=None, cancelled=None):
        if self.upload_errors:
            error = self.upload_errors.pop(0)
            if error is not None:
                raise error
        if self.upload_error:
            raise self.upload_error
        if cancelled is not None and cancelled():
            raise pr.UploadCancelled('cancelled')
        with open(local_path, 'rb') as fh:
            data = fh.read()
        self.uploads.append((remote_name, data))
        if progress is not None:
            progress(len(data), len(data))
        return f'the printer has all {len(data)} bytes'

    def delete(self, remote_name):
        self.deleted.append(remote_name)
        return True

    def start(self, remote_name):
        self.starts.append(remote_name)
        if self.start_error is not None:
            raise self.start_error
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


class _FakeFtpClient:
    """bambulabs_api's PrinterFTPClient as far as PrinterLink uses it: `ftps` (whose
    timeout is set) and list_directory, which answers (reply, LIST lines) or, after a
    swallowed failure, None."""

    def __init__(self, printer):
        self._printer = printer
        self.ftps = type('FakeFTPS', (), {'timeout': None})()

    def list_directory(self, path=None):
        if self._printer.list_fails:
            return None
        lines = [f'-rw-rw-rw- 1 root root {len(data)} Nov 19 18:00 {name}'
                 for name, data in sorted(self._printer.files.items())]
        return '226 Transfer complete.', lines


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
        self.upload_returns_none = False    # a failure during the transfer: nothing arrives
        self.arrives_but_426 = False        # the H2S case: all bytes arrive, reply 426
        self.short_by = 0                   # the reply says 226 but bytes are missing
        self.upload_raises = None           # a refused connection or login
        self.list_fails = False
        self.files = {}                     # what the printer's FTP server lists
        self.deleted = []
        self.report_after_start = None
        self.ftp_client = _FakeFtpClient(self)

    def delete_file(self, file_path):
        self.deleted.append(file_path)
        self.files.pop(file_path, None)
        return '250 Delete operation successful.'

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
        """Like the library: blocks of 32768 bytes read from the file object; a failure
        during the transfer is logged and swallowed (None); the file object is closed."""
        import logging
        logger = logging.getLogger('bambulabs_api')
        if self.upload_raises is not None:
            file_obj.close()
            raise Exception(f'Exception occurred during file upload: {self.upload_raises}')
        chunks = []
        try:
            while True:
                block = file_obj.read(32768)
                if not block:
                    break
                chunks.append(block)
        except Exception as e:                       # what connect_and_run does
            logger.error(f'Failed to execute function: {e}')
            self.files[filename] = b''.join(chunks)  # a partial file is left behind
            return None
        finally:
            file_obj.close()
        data = b''.join(chunks)
        if self.upload_returns_none:
            logger.error('Failed to execute function: 550 Could not create file.')
            return None              # what the library returns after logging a failure
        if self.short_by:
            data = data[:-self.short_by]
        self.files[filename] = data
        self.uploaded = (filename, data)
        if self.arrives_but_426:
            logger.error('Failed to execute function: 426 Failure reading network stream.')
            return None
        return FTP_TRANSFER_COMPLETE

    def start_print(self, filename, plate_number, use_ams=True, ams_mapping=(0,),
                    skip_objects=None, flow_calibration=True):
        self.started = {'filename': filename, 'plate_number': plate_number,
                        'use_ams': use_ams, 'ams_mapping': list(ams_mapping),
                        'flow_calibration': flow_calibration}
        if self.report_after_start is not None:
            self.report = self.report_after_start(filename)
        return True
