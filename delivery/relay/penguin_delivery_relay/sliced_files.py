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
"""

import os
import secrets
import shutil
import tempfile
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class HeldFile:
    code: str
    job_id: str
    filename: str
    path: str
    owned: bool          # True when the relay made this copy and must delete it


class SlicedFileStore:
    def __init__(self, spool_dir=None):
        self._spool_dir = spool_dir
        self._lock = threading.Lock()
        self._files = {}             # download token -> HeldFile
        self._awaiting_claim = set()  # tokens added but not yet confirmed or discarded

    def _spool(self):
        if self._spool_dir is None:
            self._spool_dir = tempfile.mkdtemp(prefix='penguin-delivery-relay-')
        os.makedirs(self._spool_dir, exist_ok=True)
        return self._spool_dir

    def add(self, code, job_id, sliced_file):
        """Hold a sliced file for a job. Returns its download token.

        A stream is copied here, once, before the send is decided. The entry waits for its
        claim, untouched by prune, until the send calls confirm() or discard()."""
        owned = sliced_file.stream is not None
        if owned:
            handle, path = tempfile.mkstemp(prefix=f'{job_id}-', suffix='.gcode.3mf',
                                            dir=self._spool())
            try:
                with os.fdopen(handle, 'wb') as out:
                    shutil.copyfileobj(sliced_file.stream, out)
            except BaseException:
                _unlink(path)
                raise
        else:
            path = sliced_file.path
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._files[token] = HeldFile(code, job_id, sliced_file.filename, path, owned)
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
