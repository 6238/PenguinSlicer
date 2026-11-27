"""The note of a start command, kept in the daemon's home so the hold survives a restart.

The daemon writes it (`start.json` in its home, paths.py) BEFORE it sends a start command
to the printer, marks it `sent` once the command has gone, and removes it when the
evidence settles what became of the command (see "How a start is decided" in README-details.md).
A daemon that starts and finds the note holds the printer until the evidence settles it,
without help from the relay, which may have restarted too.

What it holds: which printer (its serial), which file (the job id and the name on the
printer), whether the command is known to have gone (`phase`), and when it was written by
the clock of the daemon's computer. That time is for a person reading the file
only: the daemon's computer's clock may be hours wrong or jump, so no wait is ever measured from it.

Writing is safe against a crash mid-write: the note is written whole to a temporary file,
flushed to the disk, and renamed over the old one (`os.replace`, which replaces an existing
file on Windows too), so the file is always either the old note, the new one, or absent.
A note that is there but cannot be read or understood is `Damaged`: it holds the printer
like any other, never frees it.
"""

import json
import os
import time

VERSION = 1
#: Written before the command goes: whether it reached the printer is not known.
SENDING = 'sending'
#: Written after the command went (or raised on its way: it may have reached the printer).
SENT = 'sent'
PHASES = (SENDING, SENT)
#: A note is a few hundred bytes; anything far larger is not one.
MAX_BYTES = 64 * 1024


class Damaged:
    """A note that is there and cannot be read or understood. `reason` is for the log."""

    def __init__(self, reason):
        self.reason = reason

    def __repr__(self):
        return f'Damaged({self.reason!r})'


def load(path):
    """The note at `path`: None when there is none, a dict (`job_id`, `remote_name`,
    `printer`, `phase`, `written_at`) when it is whole, else a Damaged."""
    try:
        with open(path, 'rb') as fh:
            data = fh.read(MAX_BYTES + 1)
    except FileNotFoundError:
        return None
    except OSError as e:
        return Damaged(f'could not be read ({e.__class__.__name__}: {e})')
    if len(data) > MAX_BYTES:
        return Damaged(f'is larger than {MAX_BYTES} bytes')
    try:
        note = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as e:
        return Damaged(f'is not readable JSON ({e.__class__.__name__})')
    if not isinstance(note, dict) or note.get('version') != VERSION:
        return Damaged('is not a note of this version')
    for key in ('job_id', 'remote_name', 'printer'):
        if not isinstance(note.get(key), str) or (key != 'printer' and not note[key]):
            return Damaged(f'has no usable {key}')
    if note.get('phase') not in PHASES:
        return Damaged('has no usable phase')
    return {'job_id': note['job_id'], 'remote_name': note['remote_name'],
            'printer': note['printer'], 'phase': note['phase'],
            'written_at': note.get('written_at')}


def save(path, *, job_id, remote_name, printer, phase, wall=time.time):
    """Write the note whole, or raise OSError and leave the old one (or none) in place."""
    note = {'version': VERSION, 'job_id': job_id, 'remote_name': remote_name,
            'printer': printer or '', 'phase': phase,
            'written_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(wall()))}
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = f'{path}.tmp'
    try:
        handle = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(handle, 'wb') as fh:
            fh.write(json.dumps(note).encode('utf-8'))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def clear(path):
    """Remove the note. True when it is gone (or was never there)."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True
