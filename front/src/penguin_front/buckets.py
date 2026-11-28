"""The bucket interface: how the front server reaches the state bucket and the log bucket
(README-details.md, "The bucket interface").

Two forms give the same operations: R2, hosted (phase 3), and a folder, on one machine
(`FolderBucket`, phase 2). The operations:

- `open(name)`: a file to read in pieces, with its marker, size and store time;
  `get(name)`: the whole of a small file and its marker;
- `put(name, data, if_marker=None, if_absent=False)`: write a file from bytes, an iterable
  of byte pieces or a binary file object, and give its new marker; with `if_marker`, only if
  the file's marker is still that one; with `if_absent`, only if no such file exists;
  otherwise `ConditionFailed`, and nothing is written;
- `delete(name)`: remove a file; a file already gone is not an error;
- `copy_onto_itself(name)`: give the file a new store time, keeping its contents;
- `list(prefix)`: every file whose name starts with `prefix`, by name.

A file's **marker** changes whenever its contents change. Reads and writes pass in pieces of
at most `chunk_bytes`, so a sliced file is never held whole in memory. A file that is not
there is `NotFound`; a store that fails is `BucketUnavailable`, which the requests that read
or write the state bucket answer `front.state_bucket_unreachable`.
"""

import hashlib
import os
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path

#: The largest piece a read or a write holds in memory.
CHUNK_BYTES = 1 << 20
#: The longest name a file may have, as R2's limit on a key.
MAX_NAME_BYTES = 1024
#: The longest part between two `/` a name may have, as a file system's limit on one file's
#: or folder's name (255 bytes), so the folder form takes every name the R2 form takes.
MAX_PART_BYTES = 255
#: The start of a temporary file's name in the folder form; no name may start so.
TEMPORARY = ".tmp-"


class NotFound(LookupError):
    """No file of that name."""


class ConditionFailed(Exception):
    """A conditional write found the file changed, or already there, or not there."""


class BucketUnavailable(Exception):
    """The store failed: it could not be read or written."""


class BadName(ValueError):
    """A name no file may have."""


@dataclass(frozen=True)
class Entry:
    name: str
    size: int
    #: When the file was last stored, in seconds since the epoch on the front server's clock.
    stored_at: float


def check_name(name):
    """Refuse a name that could leave the bucket, hide a file, or differ between forms."""
    parts = name.split("/")
    if not name or len(name.encode()) > MAX_NAME_BYTES or "\\" in name or "\0" in name \
            or any(part in ("", ".", "..") or part.startswith(".")
                   or len(part.encode()) > MAX_PART_BYTES for part in parts):
        raise BadName(f"no file may be named {name!r}")
    return parts


def _pieces(data, chunk_bytes):
    if isinstance(data, (bytes, bytearray, memoryview)):
        data = bytes(data)
        for start in range(0, len(data), chunk_bytes):
            yield data[start:start + chunk_bytes]
        if not data:
            yield b""
    elif hasattr(data, "read"):
        while piece := data.read(chunk_bytes):
            yield piece
    else:
        yield from data


class Stored:
    """A file opened for reading: its marker, size and store time, and its bytes in pieces.
    Used as a context manager, which closes it."""

    def __init__(self, handle, marker, size, stored_at, chunk_bytes):
        self._handle = handle
        self.marker = marker
        self.size = size
        self.stored_at = stored_at
        self._chunk_bytes = chunk_bytes

    def chunks(self):
        while piece := self._handle.read(self._chunk_bytes):
            yield piece

    def read(self):
        return b"".join(self.chunks())

    def close(self):
        self._handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


class FolderBucket:
    """The folder form: one folder stands for the bucket, a file's name is its path under it.

    A write goes to a temporary file beside its place and is renamed over it, so a reader
    sees the old file or the new, never half of one; a write that fails partway leaves the
    old file as it was. The marker is the SHA-256 of the contents. The store time is the
    file's modification time, set from the front server's clock. A lock makes each
    conditional write's check and rename one step: the front server is one process."""

    def __init__(self, root, clock, chunk_bytes=CHUNK_BYTES):
        self.root = Path(root)
        self.clock = clock
        self.chunk_bytes = chunk_bytes
        self._lock = threading.Lock()

    def _path(self, name):
        return self.root.joinpath(*check_name(name))

    def _marker_of(self, handle):
        digest = hashlib.sha256()
        while piece := handle.read(self.chunk_bytes):
            digest.update(piece)
        handle.seek(0)
        return digest.hexdigest()

    def open(self, name):
        path = self._path(name)
        try:
            self._check_root()
            with self._lock:
                handle = path.open("rb")
            with _closed_on_failure(handle):
                marker = self._marker_of(handle)
                info = os.fstat(handle.fileno())
        except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
            # NotADirectoryError: a folder of the name is a file; IsADirectoryError: the name
            # is a folder, of other files' names. Either way no such file exists.
            raise NotFound(name) from None
        except OSError as exc:
            raise BucketUnavailable(f"reading {name}: {exc}") from None
        return Stored(handle, marker, info.st_size, info.st_mtime_ns / 1e9, self.chunk_bytes)

    def _check_root(self):
        """The bucket's own folder being a file is a broken store, not a missing file."""
        if self.root.exists() and not self.root.is_dir():
            raise BucketUnavailable(f"{self.root} is not a folder")

    def get(self, name):
        with self.open(name) as stored:
            return stored.read(), stored.marker

    def put(self, name, data, *, if_marker=None, if_absent=False):
        path = self._path(name)
        temporary = path.with_name(f"{TEMPORARY}{secrets.token_hex(8)}")
        digest = hashlib.sha256()
        source = iter(_pieces(data, self.chunk_bytes))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("wb") as out:
                while (piece := _next_piece(source)) is not None:
                    digest.update(piece)
                    out.write(piece)
            self._stamp(temporary)
            with self._lock:
                self._check(path, name, if_marker, if_absent)
                os.replace(temporary, path)
        except BaseException as exc:
            _remove_quietly(temporary)
            if isinstance(exc, _SourceFailed):
                raise exc.__cause__ from None
            if isinstance(exc, OSError):
                raise BucketUnavailable(f"writing {name}: {exc}") from None
            raise
        return digest.hexdigest()

    def _check(self, path, name, if_marker, if_absent):
        if if_absent and path.exists():
            raise ConditionFailed(f"{name} already exists")
        if if_marker is not None:
            try:
                with path.open("rb") as handle:
                    current = self._marker_of(handle)
            except FileNotFoundError:
                raise ConditionFailed(f"{name} does not exist") from None
            if current != if_marker:
                raise ConditionFailed(f"{name} has changed")

    def _stamp(self, path):
        moment = int(round(self.clock.now() * 1e9))
        os.utime(path, ns=(moment, moment))

    def delete(self, name):
        path = self._path(name)
        self._check_root()
        try:
            with self._lock:
                path.unlink(missing_ok=True)
        except (NotADirectoryError, IsADirectoryError):
            return  # a folder of the name is a file, or the name is a folder: no such file
        except OSError as exc:
            raise BucketUnavailable(f"deleting {name}: {exc}") from None

    def copy_onto_itself(self, name):
        path = self._path(name)
        self._check_root()
        try:
            with self._lock:
                if not path.is_file():
                    raise NotFound(name)
                self._stamp(path)
                return path.stat().st_mtime_ns / 1e9
        except OSError as exc:  # pragma: no cover - a file that vanished between two calls
            raise BucketUnavailable(f"refreshing {name}: {exc}") from None

    def list(self, prefix):
        folder_part = prefix.rsplit("/", 1)[0] if "/" in prefix else ""
        start = self.root.joinpath(*check_name(folder_part)) if folder_part else self.root
        entries = []
        self._check_root()
        try:
            for folder, folders, files in os.walk(start, onerror=_raise):
                folders[:] = [f for f in folders if not f.startswith(".")]
                for file in files:
                    if file.startswith("."):
                        continue
                    path = Path(folder, file)
                    name = path.relative_to(self.root).as_posix()
                    if name.startswith(prefix):
                        info = path.stat()
                        entries.append(Entry(name, info.st_size, info.st_mtime_ns / 1e9))
        except (FileNotFoundError, NotADirectoryError):
            return []  # nothing there, or a file where the prefix's folder would be
        except OSError as exc:
            raise BucketUnavailable(f"listing {prefix!r}: {exc}") from None
        return sorted(entries, key=lambda e: e.name)


def _raise(error):
    raise error


class _closed_on_failure:
    def __init__(self, handle):
        self._handle = handle

    def __enter__(self):
        return self._handle

    def __exit__(self, kind, _value, _trace):
        if kind is not None:  # pragma: no cover - a read failing after the open succeeded
            self._handle.close()


class _SourceFailed(Exception):
    """The data being written failed (its cause), not the store."""


def _next_piece(source):
    """The source's next piece, or None at its end; a failure of the source is told apart
    from a failure of the store, since only the store's is `BucketUnavailable`."""
    try:
        return next(source)
    except StopIteration:
        return None
    except BaseException as exc:
        raise _SourceFailed() from exc


def _remove_quietly(path):
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
