"""Builders shared by the fast suite: binary STL shapes, parts, archives and the fake Orca."""
import json
import re
import stat
import sys
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


def write_plate_job(directory, plate_job, stls):
    """Write `stls` ({file name: bytes}) and the plate job JSON into `directory`; its path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in stls.items():
        (directory / name).write_bytes(data)
    path = directory / "plate-job.json"
    path.write_text(json.dumps(plate_job))
    return path
