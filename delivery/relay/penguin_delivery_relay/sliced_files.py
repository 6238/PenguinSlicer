"""The sliced files the relay is holding for the daemon to download.

In the original relay, the application's own download route served the sliced file and the job
carried that route's path. A standalone relay serves the file itself: each job gets a
fresh download token, and the job's `download_path` is `/printer/download/<token>`. The
token in the path is the whole authority, exactly as before: the daemon sends no bearer
header for the download.

A file is held for as long as the relay holds its job. `prune` drops every entry whose job
is no longer held (acknowledged or expired), and deletes the relay's own copy of a file
that arrived as a stream. A file that arrived as a path belongs to the caller and is never
deleted here.

A send holds the file BEFORE it claims the job (the job's download path names the token),
so for that moment the store holds a file whose job the relay does not hold yet. `add`
therefore marks the entry as waiting for its claim, `prune` leaves such an entry alone, and
the send ends the wait with `confirm` (the claim succeeded) or `discard` (it did not).
Without that mark, any other request's housekeeping landing in between would drop the file
of a send that is about to be accepted.

Each held file carries its size and SHA-256, which travel to the daemon with the job so
a download that is short, long or damaged is caught there.

**After a restart.** The relay keeps its jobs in memory, so a restarted relay holds no job,
and every copy left in its spool directory by the process before it is an orphan. The
first use of the spool directory removes every file in it that this store names
(`j<hex>-*.gcode.3mf` and its partial copies); nothing else in the directory is touched.
The spool directory therefore belongs to one relay process: two processes must not share
one (they could not share jobs anyway).
"""

import hashlib
import os
import re
import secrets
import tempfile
import threading
from dataclasses import dataclass

# The names this store gives its copies: the job id, a dash, mkstemp's letters.
_SPOOL_NAME_RE = re.compile(r'^j[0-9a-f]{7,8}-[A-Za-z0-9_]+\.gcode\.3mf$')
_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class HeldFile:
    code: str
    job_id: str
    filename: str
    path: str
    owned: bool          # True when the relay made this copy and must delete it
    size: int = 0
    sha256: str = ''


def _digest_of(path):
    digest, size = hashlib.sha256(), 0
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b''):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


class SlicedFileStore:
    def __init__(self, spool_dir=None):
        self._spool_dir = spool_dir
        self._swept = False
        self._lock = threading.Lock()
        self._files = {}             # download token -> HeldFile
        self._awaiting_claim = set()  # tokens added but not yet confirmed or discarded

    def _spool(self):
        with self._lock:
            if self._spool_dir is None:
                self._spool_dir = tempfile.mkdtemp(prefix='penguin-delivery-relay-')
                self._swept = True             # brand new: nothing to sweep
            os.makedirs(self._spool_dir, exist_ok=True)
            if not self._swept:
                self._swept = True
                self._sweep_orphans()
            return self._spool_dir

    def sweep(self):
        """Remove the orphans a previous relay process left in the spool directory. Run on
        the first use of the directory; create_app calls it at start. Returns the names."""
        if self._spool_dir is None or not os.path.isdir(self._spool_dir):
            return []
        with self._lock:
            self._swept = True
            return self._sweep_orphans()

    def _sweep_orphans(self):
        held = {held.path for held in self._files.values()}
        removed = []
        for name in sorted(os.listdir(self._spool_dir)):
            path = os.path.join(self._spool_dir, name)
            if (_SPOOL_NAME_RE.match(name) and path not in held
                    and os.path.isfile(path)):
                _unlink(path)
                removed.append(name)
        return removed

    def add(self, code, job_id, sliced_file):
        """Hold a sliced file for a job. Returns its download token.

        A stream is copied here, once, before the send is decided. The entry waits for its
        claim, untouched by prune, until the send calls confirm() or discard()."""
        owned = sliced_file.stream is not None
        if owned:
            handle, path = tempfile.mkstemp(prefix=f'{job_id}-', suffix='.gcode.3mf',
                                            dir=self._spool())
            digest, size = hashlib.sha256(), 0
            try:
                with os.fdopen(handle, 'wb') as out:
                    while True:
                        chunk = sliced_file.stream.read(_CHUNK)
                        if not chunk:
                            break
                        if not isinstance(chunk, (bytes, bytearray)):
                            raise TypeError(f'the stream gave {type(chunk).__name__}, '
                                            'not bytes')
                        digest.update(chunk)
                        size += len(chunk)
                        out.write(chunk)
            except BaseException:
                _unlink(path)
                raise
            sha256 = digest.hexdigest()
        else:
            path = sliced_file.path
            size, sha256 = _digest_of(path)
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._files[token] = HeldFile(code, job_id, sliced_file.filename, path, owned,
                                          size, sha256)
            self._awaiting_claim.add(token)
        return token

    def confirm(self, token):
        """The job of this entry is now held: from here on prune judges it like any other."""
        with self._lock:
            self._awaiting_claim.discard(token)

    def get(self, token):
        with self._lock:
            return self._files.get(token)

    def discard(self, token):
        with self._lock:
            held = self._files.pop(token, None)
            self._awaiting_claim.discard(token)
        if held is not None and held.owned:
            _unlink(held.path)

    def prune(self, is_held):
        """Drop every file whose job `is_held(code, job_id)` says is gone, except those
        still waiting for their claim."""
        with self._lock:
            entries = [(token, held) for token, held in self._files.items()
                       if token not in self._awaiting_claim]
        for token, held in entries:
            if not is_held(held.code, held.job_id):
                self.discard(token)

    def __len__(self):
        with self._lock:
            return len(self._files)


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass
