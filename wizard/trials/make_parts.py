#!/usr/bin/env python3
"""Write the trials' made parts into wizard/trials/parts/, deterministically.

- hub-150k.stl: a closed hub of exactly 150,000 triangles, the shape the slice service's
  measurements used, written anew here: a ring 40 mm across and 20 mm tall with a 12 mm
  bore and 3 mm fillets on its four edges, a surface of revolution in near-square facets
  (300 around, 250 along the cross-section), as a finely exported round part is. Its flat
  base lies on z = 0.
- hex-spacer.stl: the slice service's reference spacer, written anew: a spacer for a 3/8 inch
  hex shaft, 1/8 inch thick, round outside (48 sides) and 5/8 inch across, 216 triangles.

Both are binary STL, closed, wound outwards, with each triangle's normal. Each coordinate is
rounded to a millionth of a millimetre before it is stored, so the bytes do not hang on the
last bit of the machine's sine and cosine. The committed files must equal what this script
writes (tests/python/test_make_parts.py). Usage: make_parts.py [FOLDER]. Standard library only.
"""
import math
import struct
import sys
from pathlib import Path

PARTS = Path(__file__).resolve().parent / "parts"

HUB_BORE_MM = 6.0          # radius: a 12 mm bore
HUB_OUTER_MM = 20.0        # radius: 40 mm across
HUB_HEIGHT_MM = 20.0
HUB_FILLET_MM = 3.0
HUB_AROUND = 300           # facets around the axis
HUB_ALONG = 250            # facets along the cross-section; 2 x 300 x 250 = 150,000 triangles

INCH_MM = 25.4
SPACER_OUTSIDE_MM = 5 / 8 * INCH_MM
SPACER_HEX_FLATS_MM = 3 / 8 * INCH_MM
SPACER_THICKNESS_MM = 1 / 8 * INCH_MM
SPACER_SIDES = 48          # the round outside; 8 for each side of the hexagon


def _point(x, y, z):
    return (round(x, 6) + 0.0, round(y, 6) + 0.0, round(z, 6) + 0.0)  # + 0.0: no negative zero


def _normal(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (nx / length, ny / length, nz / length)


def stl_bytes(label, vertices, faces):
    """A binary STL of the indexed mesh."""
    body = [label.encode("ascii").ljust(80, b"\0"), struct.pack("<I", len(faces))]
    for i, j, k in faces:
        a, b, c = vertices[i], vertices[j], vertices[k]
        body.append(struct.pack("<12fH", *_normal(a, b, c), *a, *b, *c, 0))
    return b"".join(body)


def _hub_section(s):
    """The point at arc length `s` along the hub's cross-section, as (r, z): a rectangle with
    rounded corners, run counter-clockwise in the (r, z) plane from the inner end of the base:
    base outwards, outer wall up, top inwards, bore down."""
    r0, r1, h, f = HUB_BORE_MM, HUB_OUTER_MM, HUB_HEIGHT_MM, HUB_FILLET_MM
    quarter = math.pi * f / 2
    # (length, the point at a distance t along the piece)
    pieces = [
        (r1 - r0 - 2 * f, lambda t: (r0 + f + t, 0.0)),
        (quarter, lambda t: (r1 - f + f * math.sin(t / f), f - f * math.cos(t / f))),
        (h - 2 * f, lambda t: (r1, f + t)),
        (quarter, lambda t: (r1 - f + f * math.cos(t / f), h - f + f * math.sin(t / f))),
        (r1 - r0 - 2 * f, lambda t: (r1 - f - t, h)),
        (quarter, lambda t: (r0 + f - f * math.sin(t / f), h - f + f * math.cos(t / f))),
        (h - 2 * f, lambda t: (r0, h - f - t)),
        (quarter, lambda t: (r0 + f - f * math.cos(t / f), f - f * math.sin(t / f))),
    ]
    for length, at in pieces:
        if s < length:
            return at(s)
        s -= length
    raise ValueError("past the end of the cross-section")


def hub_mesh():
    r0, r1, h, f = HUB_BORE_MM, HUB_OUTER_MM, HUB_HEIGHT_MM, HUB_FILLET_MM
    total = 2 * (r1 - r0 - 2 * f) + 2 * (h - 2 * f) + 2 * math.pi * f
    section = [_hub_section(total * i / HUB_ALONG) for i in range(HUB_ALONG)]
    angles = [2 * math.pi * j / HUB_AROUND for j in range(HUB_AROUND)]
    ring = [(math.cos(t), math.sin(t)) for t in angles]
    vertices = [_point(r * c, r * s, z) for r, z in section for c, s in ring]
    faces = []
    for i in range(HUB_ALONG):
        i2 = (i + 1) % HUB_ALONG
        for j in range(HUB_AROUND):
            j2 = (j + 1) % HUB_AROUND
            a, b = i * HUB_AROUND + j, i2 * HUB_AROUND + j
            c, d = i2 * HUB_AROUND + j2, i * HUB_AROUND + j2
            faces += [(a, d, c), (a, c, b)]   # around, then along: the normal points out
    return vertices, faces


def hex_spacer_mesh():
    r_out = SPACER_OUTSIDE_MM / 2
    r_hex = SPACER_HEX_FLATS_MM / 2 / math.cos(math.pi / 6)   # to the hexagon's corners
    t = SPACER_THICKNESS_MM
    n = SPACER_SIDES
    per_side = n // 6
    rim = [(r_out * math.cos(2 * math.pi * k / n), r_out * math.sin(2 * math.pi * k / n)) for k in range(n)]
    hexagon = [(r_hex * math.cos(math.pi / 3 * j), r_hex * math.sin(math.pi / 3 * j)) for j in range(6)]
    flat = rim + hexagon
    vertices = [_point(x, y, 0.0) for x, y in flat] + [_point(x, y, t) for x, y in flat]
    top = len(flat)

    def outer(k):
        return k % n

    def corner(j):
        return n + j % 6

    # The annulus between the rim and the hexagon, counter-clockwise seen from above: each
    # rim segment fans to the nearer corner, and one triangle spans each side of the hexagon.
    annulus = []
    for j in range(6):
        for k in range(j * per_side, (j + 1) * per_side):
            nearer = j if k < j * per_side + per_side // 2 else j + 1
            annulus.append((outer(k), outer(k + 1), corner(nearer)))
        annulus.append((corner(j), outer(j * per_side + per_side // 2), corner(j + 1)))
    faces = [(a + top, b + top, c + top) for a, b, c in annulus]
    faces += [(a, c, b) for a, b, c in annulus]                    # the bottom faces down
    for k in range(n):                                             # the round outside
        a, b = outer(k), outer(k + 1)
        faces += [(a, b, b + top), (a, b + top, a + top)]
    for j in range(6):                                             # the hex hole faces the axis
        a, b = corner(j), corner(j + 1)
        faces += [(a, b + top, b), (a, a + top, b + top)]
    return vertices, faces


def hub_stl():
    return stl_bytes("PenguinSlicer trials: hub 40 x 20 mm, 12 mm bore, 150,000 triangles", *hub_mesh())


def hex_spacer_stl():
    return stl_bytes("PenguinSlicer trials: spacer for a 3/8 in hex shaft, 5/8 in across, 1/8 in thick",
                     *hex_spacer_mesh())


def write_parts(folder=PARTS):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = {"hub-150k.stl": hub_stl(), "hex-spacer.stl": hex_spacer_stl()}
    for name, data in written.items():
        (folder / name).write_bytes(data)
    return {name: (len(data) - 84) // 50 for name, data in written.items()}


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else PARTS
    for name, triangles in write_parts(target).items():
        print(f"wrote {target / name} ({triangles:,} triangles)")
