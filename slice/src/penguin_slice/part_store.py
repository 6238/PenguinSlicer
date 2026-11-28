"""The part store: the slice service's folder of uploaded parts (slice/README-details.md,
"The part store").

A part is kept under its user key, the SHA-256 hash of its bytes and its units label
together, and found only under all three, so two users who upload the same file each have
their own entry and nobody learns whether someone else uploaded a given file. The store is a
cache: the browser's storage is the record of a user's parts, and a page whose part is gone
uploads it again.

On disk, one folder per user key, named by user_folder (the SHA-256 hash of the user key's
UTF-8 bytes, in 64 lowercase hexadecimal characters): a user key is an arbitrary string from
outside, so it is never used as a name itself. A hash names no path outside the store
(no `/`, no `..`, never empty, never too long), two different user keys never share a
folder (that would take a collision of SHA-256), and the same user key gets the same folder
in every process, with no table to lose at a restart. Each part is the file
`<sha256>-<units>.stl` in its user key's folder, its bytes exactly as they arrived.

The rules: a part stays PART_STORE_TTL_S (two hours) after it was last used, its upload and
each slice job that names it being uses (sweep removes the rest); the parts of every user key
together take at most `max_bytes`, past which the least recently used parts of any user key
are removed; there is no count of parts for one user key. A slice job takes its own hold on
each part's file when it is accepted (hold: a hard link into its folder), so removing a part
never touches a slice job already accepted. The store's folder is new in each slice service
process, so the part store is empty when the slice service starts.

The index is in this process's memory, behind one lock; every change to the folder is made
under it.
"""
import hashlib
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .limits import SettingError

PART_STORE_TTL_S = 7200                 # a part is kept this long after it was last used
MAX_MB_ENV = "PENGUIN_SLICE_PART_STORE_MAX_MB"
DEFAULT_MAX_MB = 1024                   # the starting figure for one machine; the disk was never measured
MIN_MAX_MB = 8                          # room for the largest part the slice service takes (7.5 MB)
UNITS = {"mm": 1.0, "in": 25.4}         # a units label and the scale that turns it into millimetres
_MB_RE = re.compile(r"[0-9]{1,7}")
BAD_MAX_MB_MESSAGE = ("The setting {env} is {value}, which is not a whole number of megabytes from "
                      f"{MIN_MAX_MB} to 9999999 written in the digits 0 to 9; set it so, or unset it for the "
                      f"default of {DEFAULT_MAX_MB} MB.")


def max_bytes(environ=None):
    """The limit on the disk the part store may take in all, in bytes: DEFAULT_MAX_MB when
    PENGUIN_SLICE_PART_STORE_MAX_MB is unset or empty, else its value in MB, 1 to 7 plain ASCII
    digits and at least MIN_MAX_MB. Raises SettingError (naming the setting) for anything else."""
    raw = (os.environ if environ is None else environ).get(MAX_MB_ENV, "")
    if raw == "":
        return DEFAULT_MAX_MB * 1024 * 1024
    if not _MB_RE.fullmatch(raw) or int(raw) < MIN_MAX_MB:
        raise SettingError(BAD_MAX_MB_MESSAGE.format(env=MAX_MB_ENV, value=repr(raw[:40])))
    return int(raw) * 1024 * 1024


def user_folder(user_key):
    """The name of a user key's folder in the part store (see the module's text)."""
    return hashlib.sha256(user_key.encode("utf-8", "surrogatepass")).hexdigest()


@dataclass
class StoredPart:
    """One entry of the part store. `analysis` is what the checks on arrival found
    (service.check_part): the footprints, the health and the triangles."""
    user_key: str
    sha256: str
    units: str
    path: Path
    size: int
    analysis: dict
    last_used: float


class PartsGone(Exception):
    """Parts removed from the part store between being found and being held: `entries`."""

    def __init__(self, entries):
        super().__init__(f"{len(entries)} parts gone from the part store")
        self.entries = entries


class PartStore:
    """The part store in the folder `root` (made when missing). `clock` is the time of the
    two hours; a test moves a fake one."""

    def __init__(self, root, max_bytes, ttl_s=PART_STORE_TTL_S, clock=time.monotonic):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self._ttl_s = ttl_s
        self._clock = clock
        self._lock = threading.Lock()
        self._entries = {}              # (user_key, sha256, units) -> StoredPart

    def get(self, user_key, sha256, units):
        """The entry under the three, or None. Finding a part is not a use of it."""
        with self._lock:
            return self._entries.get((user_key, sha256, units))

    def put(self, user_key, units, sha256, data, analysis):
        """Keep `data` (whose hash is `sha256`) under the three; the new entry. The bytes are
        written under a temporary name and renamed, so a part's file is always whole. Past the
        limit on disk, the least recently used parts of any user key are removed. Raises
        OSError when the folder cannot be written (a full disk)."""
        folder = self.root / user_folder(user_key)
        path = folder / f"{sha256}-{units}.stl"
        with self._lock:
            folder.mkdir(exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=folder, prefix=".upload-")
            try:
                with os.fdopen(handle, "wb") as fh:
                    fh.write(data)
                os.replace(temporary, path)
            except BaseException:
                Path(temporary).unlink(missing_ok=True)
                raise
            entry = StoredPart(user_key, sha256, units, path, len(data), analysis, self._clock())
            self._entries[(user_key, sha256, units)] = entry
            self._evict(keep=entry)
            return entry

    def touch(self, entries):
        """A use of each entry: its two hours start again."""
        now = self._clock()
        with self._lock:
            for entry in entries:
                entry.last_used = now

    def hold(self, entries, directory):
        """A slice job's own hold on each entry's file: {entry's sha256 and units: the held
        path} in `directory` (a hard link, or a copy where the file system has none), taken
        under the lock so no part is removed half-way. Raises PartsGone for entries no longer
        in the store, holding none; OSError when `directory` cannot be written."""
        directory = Path(directory)
        with self._lock:
            gone = [e for e in entries if self._entries.get((e.user_key, e.sha256, e.units)) is not e]
            if gone:
                raise PartsGone(gone)
            directory.mkdir(parents=True, exist_ok=True)
            held = {}
            for entry in entries:
                target = directory / entry.path.name
                if target.exists():
                    held[(entry.sha256, entry.units)] = target
                    continue
                try:
                    os.link(entry.path, target)
                except OSError:
                    shutil.copyfile(entry.path, target)
                held[(entry.sha256, entry.units)] = target
            return held

    def sweep(self, now=None):
        """Remove every part unused for the two hours; how many were removed."""
        now = self._clock() if now is None else now
        with self._lock:
            expired = [e for e in self._entries.values() if now - e.last_used >= self._ttl_s]
            for entry in expired:
                self._remove(entry)
            return len(expired)

    def total_bytes(self):
        with self._lock:
            return sum(e.size for e in self._entries.values())

    def __len__(self):
        with self._lock:
            return len(self._entries)

    def _evict(self, keep):
        """Under the lock: the least recently used parts, of any user key, until the store is
        within its limit; never `keep`, the part just added."""
        total = sum(e.size for e in self._entries.values())
        for entry in sorted(self._entries.values(), key=lambda e: e.last_used):
            if total <= self.max_bytes:
                return
            if entry is not keep:
                total -= entry.size
                self._remove(entry)

    def _remove(self, entry):
        self._entries.pop((entry.user_key, entry.sha256, entry.units), None)
        entry.path.unlink(missing_ok=True)
