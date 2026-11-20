"""Write the corpus of bad part files in bad_stls/, one small file per hostile case.

    uv run --project slice python slice/tests/fixtures/make_bad_stls.py

Deterministic: the checked-in files must equal what this script writes, byte for byte
(tests/test_bad_stls.py). Each case is a function of no arguments returning the file's
bytes. The two dense meshes at the part triangle cap are 7.5 MB each, so they are not
checked in: tests build them with dense_stl().

Only numpy and the standard library; the meshes are written here, independently of the
slice service's reader.
"""
import gzip
import io
import struct
import sys
import zipfile
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "bad_stls"
RECORD = np.dtype([("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
BOX_FACES = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4),
             (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6), (1, 3, 5), (3, 7, 5)]


def triangles_stl(tris, label=b"penguin slice bad part corpus", count=None):
    """A binary STL of an array of triangles (n, 3, 3); `count` overrides the header's count."""
    tris = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        length = np.linalg.norm(normals, axis=1, keepdims=True)
        normals = np.where(length > 0, normals / np.where(length > 0, length, 1), 0)
    body = np.zeros(len(tris), dtype=RECORD)
    body["normal"] = np.nan_to_num(normals)
    with np.errstate(over="ignore", invalid="ignore"):
        body["v"] = tris
    n = len(tris) if count is None else count
    return label.ljust(80, b"\0") + struct.pack("<I", n) + body.tobytes()


def box_tris(sx, sy, sz, origin=(0.0, 0.0, 0.0)):
    x0, y0, z0 = origin
    corners = np.array([[x0 + dx * sx, y0 + dy * sy, z0 + dz * sz]
                        for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)], dtype=np.float64)
    return corners[np.asarray(BOX_FACES)]


def box(sx=20.0, sy=20.0, sz=10.0, origin=(0.0, 0.0, 0.0)):
    return triangles_stl(box_tris(sx, sy, sz, origin))


def ascii_box():
    lines = ["solid box"]
    for tri in box_tris(20, 20, 10):
        lines += ["  facet normal 0 0 0", "    outer loop"]
        lines += ["      vertex %g %g %g" % tuple(v) for v in tri]
        lines += ["    endloop", "  endfacet"]
    lines.append("endsolid box")
    return ("\n".join(lines) + "\n").encode("ascii")


def png():
    # The PNG signature and an IHDR chunk: the start of any PNG image.
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0) \
        + b"\x90wS\xde" + b"\0" * 64


def threemf():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        info = zipfile.ZipInfo("3D/3dmodel.model", date_time=(2026, 1, 1, 0, 0, 0))
        zf.writestr(info, '<?xml version="1.0"?><model unit="millimeter"/>')
    return buffer.getvalue()


def nan_coordinate():
    tris = box_tris(20, 20, 10)
    tris[3, 1, 2] = np.nan
    return triangles_stl(tris)


def infinite_coordinate():
    tris = box_tris(20, 20, 10)
    tris[0, 0, 0] = np.inf
    return triangles_stl(tris)


def absurd_coordinates():
    # A box 1e30 mm across: finite in float32, larger than any plate.
    return triangles_stl(box_tris(1e30, 1e30, 1e30))


def all_degenerate():
    # Twelve triangles whose three corners lie on one line, spread over a 20 mm box.
    tris = []
    for i in range(12):
        a = np.array([i, 0.0, 0.0])
        tris.append([a, a + (10, 10, 5), a + (20, 20, 10)])
    return triangles_stl(tris)


def single_triangle():
    return triangles_stl([[(0, 0, 0), (20, 0, 0), (0, 20, 10)]])


def flat_sheet():
    # A 20 x 20 mm square on z = 0, both sides: no thickness and no volume.
    a, b, c, d = (0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)
    return triangles_stl([[a, b, c], [a, c, d], [a, c, b], [a, d, c]])


def open_box():
    # A box with its top missing: every top edge belongs to one triangle only.
    tris = box_tris(20, 20, 10)
    return triangles_stl(np.delete(tris, [2, 3], axis=0))


def inverted_normals():
    # A closed box with every triangle wound the wrong way: the surface faces inwards.
    return triangles_stl(box_tris(20, 20, 10)[:, ::-1])


def self_intersecting():
    # Two closed boxes that pass through each other, in one shell list.
    return triangles_stl(np.concatenate([box_tris(20, 20, 10), box_tris(10, 10, 20, origin=(5, 5, -5))]))


def two_shells():
    return triangles_stl(np.concatenate([box_tris(20, 20, 10), box_tris(20, 20, 10, origin=(40, 0, 0))]))


def slivers_and_lattice():
    """A small stand-in for the not-watertight tower that failed every slice with supports
    off: a solid base, a solid cap floating 3 mm above an open lattice of single-sided
    strips (no volume, so those layers slice empty), and 300 zero-thickness slivers."""
    rng = np.random.default_rng(6238)
    parts = [box_tris(20, 20, 10), box_tris(20, 20, 6, origin=(0, 0, 11))]
    for i in range(6):                                  # the open lattice between them
        x = 2.0 + 3.2 * i
        parts.append(np.array([[(x, 0, 10), (x + 0.5, 20, 11), (x, 20, 11)]]))
        parts.append(np.array([[(0, x, 10), (20, x + 0.5, 11), (20, x, 11)]]))
    for _ in range(300):                                # slivers inside the solids: two corners the same
        p = rng.uniform((1, 1, 1), (19, 19, 9)) + (0, 0, 10 * rng.integers(0, 2) * 1.1)
        q = p + rng.uniform(-0.5, 0.5, 3)
        parts.append(np.array([[p, q, p]]))
    return triangles_stl(np.concatenate(parts))


def html_error_page():
    # What a web server sends instead of the part when something fails: text, over 84 bytes.
    return (b"<!DOCTYPE html>\n<html><head><title>502 Bad Gateway</title></head>\n"
            b"<body><h1>502 Bad Gateway</h1><p>The server could not export the part.</p></body></html>\n")


def ascii_capitals():
    # An ASCII STL written in capitals, as some exporters write it.
    return ascii_box().upper()


def ascii_with_bom():
    # An ASCII STL that starts with a UTF-8 byte-order mark.
    return b"\xef\xbb\xbf" + ascii_box()


def pdf():
    # The start of a PDF with a compressed stream: zero and control bytes after a text header.
    head = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Length 980 /Filter /FlateDecode >>\nstream\n"
    body = bytes((i * 37 + 11) % 256 for i in range(980))
    return head + body + b"\nendstream\nendobj\n"


def jpeg():
    # A JPEG's start-of-image and JFIF header, then entropy-coded bytes.
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + \
        bytes((i * 91 + 7) % 256 for i in range(2040))


def utf16_text():
    # An HTML error page saved as UTF-16 with no byte-order mark: every other byte is zero,
    # and bytes 80 to 84 read as a triangle count in the millions.
    return html_error_page().decode("ascii").encode("utf-16-le")


def gzipped_box():
    # A good box STL, gzip-compressed (fixed mtime, so the bytes do not change).
    return gzip.compress(box(), mtime=0)


def coincident_triangles():
    # Two triangles on top of each other: every edge used twice, yet nothing enclosed.
    t = [(0, 0, 0), (30, 0, 5), (0, 30, 9)]
    return triangles_stl([t, t[::-1]])


def larger_than_plate():
    return box(400, 30, 10)


def taller_than_printer():
    return box(20, 20, 350)


def inch_file():
    # A 2 x 1 x 0.5 inch block exported in inches and read as millimetres.
    return box(2.0, 1.0, 0.5)


def thousandth_of_a_mm():
    return box(0.001, 0.001, 0.001)


CASES = {
    "empty.stl": lambda: b"",
    "one_byte.stl": lambda: b"\x00",
    "cut_mid_triangle.stl": lambda: box()[:-25],
    "count_larger.stl": lambda: triangles_stl(box_tris(20, 20, 10), count=13),
    "count_smaller.stl": lambda: triangles_stl(box_tris(20, 20, 10), count=11),
    "count_zero.stl": lambda: triangles_stl(np.zeros((0, 3, 3))),
    "ascii.stl": ascii_box,
    "ascii_capitals.stl": ascii_capitals,
    "ascii_with_bom.stl": ascii_with_bom,
    "pdf.stl": pdf,
    "jpeg.stl": jpeg,
    "utf16_text.stl": utf16_text,
    "png.stl": png,
    "3mf.stl": threemf,
    "text.stl": lambda: b"This is a note about the part, not the part itself.\n",
    "html_error_page.stl": html_error_page,
    "gzip.stl": gzipped_box,
    "coincident_triangles.stl": coincident_triangles,
    "nan.stl": nan_coordinate,
    "infinite.stl": infinite_coordinate,
    "absurd_coordinates.stl": absurd_coordinates,
    "all_degenerate.stl": all_degenerate,
    "single_triangle.stl": single_triangle,
    "flat_sheet.stl": flat_sheet,
    "open_box.stl": open_box,
    "slivers_and_lattice.stl": slivers_and_lattice,
    "inverted_normals.stl": inverted_normals,
    "self_intersecting.stl": self_intersecting,
    "two_shells.stl": two_shells,
    "larger_than_plate.stl": larger_than_plate,
    "taller_than_printer.stl": taller_than_printer,
    "inch_file.stl": inch_file,
    "thousandth_of_a_mm.stl": thousandth_of_a_mm,
}


def dense_stl(triangles):
    """A finely divided ramp, 40 x 40 x 10 mm, of exactly `triangles` triangles: a strip of
    thin quads, plus one triangle when the count is odd. Only its size in triangles matters."""
    n = triangles // 2
    xs = np.linspace(0.0, 40.0, n + 1)
    a = np.stack([xs[:-1], np.zeros(n), np.zeros(n)], axis=1)
    b = np.stack([xs[1:], np.zeros(n), np.zeros(n)], axis=1)
    c = np.stack([xs[1:], np.full(n, 40.0), np.full(n, 10.0)], axis=1)
    d = np.stack([xs[:-1], np.full(n, 40.0), np.full(n, 10.0)], axis=1)
    tris = [np.stack([a, b, c], axis=1), np.stack([a, c, d], axis=1)]
    if triangles % 2:
        tris.append(np.array([[(0, 0, 0), (40, 0, 0), (20, -5, 0)]]))
    return triangles_stl(np.concatenate(tris))


def main():
    OUT.mkdir(exist_ok=True)
    for name, build in CASES.items():
        (OUT / name).write_bytes(build())
    print(f"wrote {len(CASES)} files to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
