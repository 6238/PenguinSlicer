"""Builders shared by the fast suite: binary STL shapes, parts, archives and the fake Orca."""
import fcntl
import hashlib
import json
import os
import queue
import re
import signal
import stat
import sys
import threading
import zipfile
from pathlib import Path

import numpy as np

from penguin_slice.mesh import orientation_footprints, read_binary_stl

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
SLICE_ROOT = TESTS.parent
REPO_ROOT = SLICE_ROOT.parent
CONTRACTS = REPO_ROOT / "contracts"
FAKE_ORCA = TESTS / "fake_orca.py"
INSTALL_ORCA = SLICE_ROOT / "scripts" / "install-orca.sh"


FAILSAFE_S = 10          # a wait on a process, a thread or an event gives up after this; reached only by a failing test


def bounded(fn):
    """fn() in a thread, given FAILSAFE_S to return: (returned, raised, finished). A run
    that hangs fails its test instead of hanging the suite; the caller kills what is left
    (kill_fake)."""
    outcome = {}

    def target():
        try:
            outcome["returned"] = fn()
        except BaseException as exc:      # noqa: BLE001 - handed back to the test
            outcome["raised"] = exc
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(FAILSAFE_S)
    return outcome.get("returned"), outcome.get("raised"), not thread.is_alive()


def kill_fake(out):
    """SIGKILL the stand-in Orca whose files are in `out` if it still holds its lock (the
    kernel drops the lock when it exits, so a pid reused by another process is never hit),
    for a test that is failing. One that exits meanwhile is not an error."""
    try:
        pid = int((Path(out) / "fake-orca.pid").read_text())
        with open(Path(out) / "fake-orca.lock", "a") as fh:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return                                   # the lock is free: it is gone
            except BlockingIOError:
                pass
        os.kill(pid, signal.SIGKILL)
    except (OSError, ValueError):
        return


def pinned_orca_version():
    """The Orca version pinned in scripts/install-orca.sh, the one place it is stated."""
    match = re.search(r'^ORCA_VERSION="([^"]+)"$', INSTALL_ORCA.read_text(), re.M)
    assert match, "scripts/install-orca.sh has no ORCA_VERSION line"
    return match.group(1)


def mesh_stl(vertices, faces):
    """A binary STL of an indexed mesh, with real normals."""
    tris = np.asarray(vertices, dtype=np.float64)[np.asarray(faces)]
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    record = np.dtype([('normal', '<f4', 3), ('v', '<f4', (3, 3)), ('attr', '<u2')])
    body = np.zeros(len(tris), dtype=record)
    body['normal'] = normals
    body['v'] = tris
    return b'part'.ljust(80, b'\0') + np.uint32(len(tris)).tobytes() + body.tobytes()


def box_stl(sx=10.0, sy=20.0, sz=30.0, origin=(0.0, 0.0, 0.0)):
    """A binary STL of an axis-aligned box with one corner at `origin`."""
    x0, y0, z0 = origin
    corners = np.array([[x0 + dx * sx, y0 + dy * sy, z0 + dz * sz]
                        for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)], dtype=np.float64)
    faces = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
             (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]
    return mesh_stl(corners, faces)


def l_prism_stl(origin=(0.0, 0.0, 0.0)):
    """An L-shaped prism with unequal arms and its top sheared in x and y, so that no view of
    it is symmetric: a reversed angle or a wrong orientation changes its footprint."""
    outline = [(0, 0), (30, 0), (30, 8), (8, 8), (8, 18), (0, 18)]
    x0, y0, z0 = origin
    bottom = [(x0 + x, y0 + y, z0) for x, y in outline]
    top = [(x0 + x + 4, y0 + y + 2, z0 + 12) for x, y in outline]
    n = len(outline)
    faces = [(0, i + 1, i) for i in range(1, n - 1)]                 # the bottom, a fan from (0, 0)
    faces += [(n, n + i, n + i + 1) for i in range(1, n - 1)]        # the top
    for i in range(n):
        j = (i + 1) % n
        faces += [(i, j, n + j), (i, n + j, n + i)]
    return mesh_stl(bottom + top, faces)


def cylinder_stl(radius=10.0, height=15.0, segments=64):
    """A closed upright cylinder on z = 0, centred on the z axis."""
    angles = np.linspace(0.0, 2 * np.pi, segments, endpoint=False)
    ring = np.stack([radius * np.cos(angles), radius * np.sin(angles)], axis=1)
    vertices = np.vstack([np.hstack([ring, np.zeros((segments, 1))]),
                          np.hstack([ring, np.full((segments, 1), height)]),
                          [[0, 0, 0], [0, 0, height]]])
    bottom, top = 2 * segments, 2 * segments + 1
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces += [(i, j, segments + j), (i, segments + j, segments + i), (bottom, j, i),
                  (top, segments + i, segments + j)]
    return mesh_stl(vertices, faces)


def part_from_stl(directory, name, stl):
    """A parts[ref] entry for write_plate_3mf, its STL written under `directory`."""
    path = Path(directory) / f'{len(list(Path(directory).iterdir()))}.stl'
    path.write_bytes(stl)
    return {'name': name, 'stl_path': path, 'footprints': orientation_footprints(read_binary_stl(stl, name))}


def make_part(directory, name, size, origin=(0.0, 0.0, 0.0)):
    return part_from_stl(directory, name, box_stl(*size, origin=origin))


def cylinder_part(directory, name, radius, height):
    return part_from_stl(directory, name, cylinder_stl(radius, height, segments=48))


def write_names_archive(path, names):
    """A sliced file holding only Metadata/plate_1.json with these object names."""
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('Metadata/plate_1.json', json.dumps({'bbox_objects': [{'name': n} for n in names]}))


def make_archive(path, gcode_header=True, slice_info=True):
    """A sliced file with the recorded Orca header and slice_info fixtures."""
    with zipfile.ZipFile(path, "w") as zf:
        if gcode_header:
            zf.writestr("Metadata/plate_1.gcode", (FIXTURES / "plate_1_header.gcode").read_text())
        if slice_info:
            zf.writestr("Metadata/slice_info.config", (FIXTURES / "slice_info.config").read_text())
        zf.writestr("[Content_Types].xml", "<Types/>")


def corrupt_entry(path, entry, content, others=()):
    """A zip at `path` whose `entry` is listed and opens, but whose compressed data is
    damaged (every byte 0xFF: a deflate block of the reserved type). `others` are
    (name, content) pairs written intact before it."""
    path = Path(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in others:
            zf.writestr(name, data)
        zf.writestr(entry, content)
    with zipfile.ZipFile(path) as zf:
        info = zf.getinfo(entry)
    raw = bytearray(path.read_bytes())
    name_len = int.from_bytes(raw[info.header_offset + 26:info.header_offset + 28], "little")
    extra_len = int.from_bytes(raw[info.header_offset + 28:info.header_offset + 30], "little")
    start = info.header_offset + 30 + name_len + extra_len
    raw[start:start + info.compress_size] = b"\xff" * info.compress_size
    path.write_bytes(bytes(raw))


def install_fake_orca(directory, monkeypatch, mode="ok"):
    """Point PENGUIN_SLICE_ORCA at a wrapper that runs fake_orca.py in `mode`."""
    wrapper = Path(directory) / f"fake-orca-{mode}"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I -S "{FAKE_ORCA}" --mode {mode} "$@"\n')
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PENGUIN_SLICE_ORCA", str(wrapper))
    return wrapper


class ManualTimer:
    """A stand-in for threading.Timer that fires only when a test calls fire()."""

    def __init__(self, interval, fn):
        self.interval, self.fn, self.daemon, self.cancelled = interval, fn, False, False

    def start(self):
        pass

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.fn()


class ManualTicks:
    """The sweeper's clock for a test (JobPool.start_sweeper(wait=...)): the sweeper waits on
    it for each interval, and the interval passes only when the test calls tick(); stop()
    ends the wait as the pool's closing does. `intervals` are the intervals it was asked to
    wait. Nothing waits a duration: the failsafe is reached only by a failing test."""

    def __init__(self):
        self.intervals = []
        self._queue = queue.Queue()

    def __call__(self, interval_s):
        self.intervals.append(interval_s)
        return self._queue.get(timeout=FAILSAFE_S)

    def tick(self):
        self._queue.put(False)

    def stop(self):
        self._queue.put(True)


class ManualTimers:
    """A timer factory for slicer.run_process(timer=...): the timers it made, in order."""

    def __init__(self):
        self.made = []

    def __call__(self, interval, fn):
        self.made.append(ManualTimer(interval, fn))
        return self.made[-1]


USER_KEY = "user-a"            # the user key the tests' parts and slice jobs are under
PLATE_ID = "plate-1"
SUBMISSION_ID = "submission-1"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def part_entry(name, data, units="mm"):
    """A part of a phase 2 plate configuration, named by the hash of `data`."""
    return {"name": name, "sha256": sha256(data), "units": units}


def phase_2(parts, instances, **fields):
    """A phase 2 plate configuration: `parts` is {key: (name, bytes)} or {key: (name, bytes, units)}."""
    data = {"plate_id": PLATE_ID, "submission_id": SUBMISSION_ID,
            "parts": {key: part_entry(*part) for key, part in parts.items()}, "instances": instances}
    data.update(fields)
    return data


class Parts:
    """A part store in a test's folder (its clock a list the test moves: `clock[0]`), and the
    plate configurations read against it."""

    def __init__(self, directory, max_bytes=1024 * 1024 * 1024, ttl_s=None):
        from penguin_slice.part_store import PART_STORE_TTL_S, PartStore
        self.clock = [1000.0]
        self.store = PartStore(Path(directory) / "store", max_bytes, ttl_s=ttl_s or PART_STORE_TTL_S,
                               clock=lambda: self.clock[0])

    def add(self, data, units="mm", user_key=USER_KEY):
        """Upload `data` (service.upload_part): its record."""
        from penguin_slice.service import upload_part
        return upload_part(self.store, user_key, units, data)[0]

    def find(self, user_key=USER_KEY):
        return lambda digest, units: self.store.get(user_key, digest, units)

    def read(self, data, user_key=USER_KEY, environ=None):
        from penguin_slice.service import read_plate_configuration
        return read_plate_configuration(data, self.find(user_key), environ=environ)


def upload(client, data, units="mm", user_key=USER_KEY):
    """POST /parts of `data` through a Flask test client: the answer."""
    query = "" if units is None else f"?units={units}"
    headers = {} if user_key is None else {"X-Penguin-User-Key": user_key}
    # Content-Length as every HTTP client sends it, for an empty body too (the test client leaves it out).
    return client.post(f"/parts{query}", data=data, headers=headers, content_type="application/octet-stream",
                       environ_overrides={"CONTENT_LENGTH": str(len(data))})


def submit(client, plate_configuration, user_key=USER_KEY):
    """POST /slices of a plate configuration as JSON through a Flask test client: the answer."""
    headers = {} if user_key is None else {"X-Penguin-User-Key": user_key}
    return client.post("/slices", data=json.dumps(plate_configuration), headers=headers,
                       content_type="application/json")


INCH_MM = 25.4


def spacer_stl(outside=5 / 8 * INCH_MM, hex_flats=3 / 8 * INCH_MM, thickness=1 / 8 * INCH_MM, segments=48):
    """The reference plate's part: a hex shaft spacer for a 3/8 inch hex shaft, 1/8 inch
    thick, round outside and 5/8 inch across. A closed binary STL of 216 triangles: the
    top and bottom annuli are zipped between the outer circle (`segments` points) and the
    hexagon (corners at 0, 60, ... degrees), then the outer and inner walls."""
    r_out = outside / 2
    r_hex = hex_flats / 2 / np.cos(np.pi / 6)
    outer = [(r_out * np.cos(2 * np.pi * k / segments), r_out * np.sin(2 * np.pi * k / segments))
             for k in range(segments)]
    inner = [(r_hex * np.cos(2 * np.pi * j / 6), r_hex * np.sin(2 * np.pi * j / 6)) for j in range(6)]
    n_o, n_i = len(outer), len(inner)
    vertices = [(x, y, 0.0) for x, y in outer + inner] + [(x, y, thickness) for x, y in outer + inner]
    top = n_o + n_i                                   # the index of the first top vertex
    ring = []                                         # the annulus, as (outer or inner, index) triples
    i = j = 0
    while i < n_o or j < n_i:
        if i < n_o and (i + 1) / n_o <= (j + 1) / n_i + 1e-12:
            ring.append((i % n_o, (i + 1) % n_o, n_o + j % n_i))
            i += 1
        else:
            ring.append((i % n_o, n_o + (j + 1) % n_i, n_o + j % n_i))
            j += 1
    faces = [(a + top, b + top, c + top) for a, b, c in ring] + [(a, c, b) for a, b, c in ring]
    for k in range(n_o):
        k2 = (k + 1) % n_o
        faces += [(k, k2, top + k2), (k, top + k2, top + k)]
    for k in range(n_i):
        a, b = n_o + k, n_o + (k + 1) % n_i
        faces += [(a, top + b, b), (a, top + a, top + b)]
    return mesh_stl(vertices, faces)


def spacer_grid(count=100, side=10, pitch_mm=22.0, centre=(170.0, 160.0), ref="spacer"):
    """The reference plate's instances: `count` spacers in rows of `side`, `pitch_mm` apart,
    centred on the default printer's plate."""
    return [{"ref": ref, "orientation": "+z", "angle": 0,
             "x": centre[0] + (k % side - (side - 1) / 2) * pitch_mm,
             "y": centre[1] + (k // side - (side - 1) / 2) * pitch_mm} for k in range(count)]
