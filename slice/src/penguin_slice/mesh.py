"""Reading a part's binary STL with numpy, and its footprints.

The pure-Python slicer.stl_bounds stays for the sample part only; a part can be 150,000
triangles, which numpy reads in a fraction of the time and memory.
"""
from dataclasses import dataclass

import numpy as np
import shapely

from . import limits
from .plate import ORIENTATION_MATRICES
from .slicer import _binary_triangle_count

_TRIANGLE = np.dtype([('normal', '<f4', (3,)), ('v0', '<f4', (3,)), ('v1', '<f4', (3,)),
                      ('v2', '<f4', (3,)), ('attr', '<u2')])
# Each orientation computed directly; its opposite is the same projection mirrored in one
# plate axis (index 0 for x, 1 for y), with the part turned upside down.
_MIRRORS = {'-z': ('+z', 1), '-x': ('+x', 0), '-y': ('+y', 1)}


class MeshError(Exception):
    """A part refused when it is read. `message` is one sentence for the user, `details`
    the measured value and the file for the log, `error_code` the error report's code and
    `where` the part. `remedy`, when set, replaces the code's remedy and `no_action` drops
    its action (service.check_part sets both for a part being added)."""

    def __init__(self, message, details="", error_code="slice.part_unreadable", where=None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.error_code = error_code
        self.where = where or {}
        self.remedy = None
        self.no_action = False


@dataclass
class Mesh:
    vertices: np.ndarray        # N x 3 float64, unique
    faces: np.ndarray           # M x 3 int, indices into vertices
    triangles: int
    health: dict = None         # analyse(): watertight, shells, volume and the rest, for checks and the log


# Warnings a part can carry: it is sliced, and the warning travels in the sliced file's
# summary (part_warnings). code -> sentence; {name} and the numbers filled in by part_warnings.
WARNINGS = {
    "slice.part_not_watertight": ("{name} has holes in its surface ({open_edges:,} open edges, {shells:,} "
                                  "separate pieces); if the slice fails or looks wrong, repair it in CAD."),
    "slice.part_inside_out": "{name} has its surface facing inwards; the slicer turns it the right way out.",
    "slice.part_maybe_inches": ("{name} is only {x} x {y} x {z} mm; if it was drawn in inches, export it "
                                "again in millimetres."),
}
# slice.part_not_watertight's sentence for a surface with no hole whose edges are shared by
# more than two faces (faces doubled, or two surfaces laid over each other): no holes to name.
OVERLAID_FACES_MESSAGE = ("{name} has faces laid on top of each other ({overused_edges:,} edges shared by more "
                          "than two faces, {shells:,} separate pieces); if the slice fails or looks wrong, repair it "
                          "in CAD.")
MAYBE_INCHES_MM = 5.0           # a part whose every side is under this may be an inch file read as mm
_PNG = b"\x89PNG\r\n\x1a\n"
_ZIP = b"PK\x03\x04"
_GZIP = b"\x1f\x8b"
_PDF = b"%PDF-"
_JPEG = b"\xff\xd8\xff"
_UTF8_BOM = b"\xef\xbb\xbf"
_SIGNATURES = ((_PNG, "a PNG image"), (_ZIP, "a zip archive (a 3MF is one)"), (_GZIP, "a gzip archive"),
               (_PDF, "a PDF document"), (_JPEG, "a JPEG image"), (b"\xff\xfe", "UTF-16 text"),
               (b"\xfe\xff", "UTF-16 text"))
# Bytes of text: printable ASCII, tab, newline, carriage return, and any byte of UTF-8
# beyond ASCII. Coordinates in a binary STL hold zero bytes and control bytes.
_TEXT_BYTES = bytes(range(32, 127)) + b"\t\n\r" + bytes(range(128, 256))


def _is_text(sample):
    return bool(sample) and not sample.translate(None, _TEXT_BYTES)


def _not_binary(data, name, source):
    """The MeshError for bytes that are not a binary STL: what they are, in a true sentence."""
    where = {"part": name}
    size = len(data)

    def refuse(sentence, detail, code="slice.part_unreadable"):
        return MeshError(sentence.format(name=name), f"{source}: {detail}", code, where)

    if size == 0:
        return refuse(limits.PART_EMPTY_MESSAGE, "0 bytes")
    # An ASCII STL in any case, with or without a UTF-8 byte-order mark.
    text_head = data[len(_UTF8_BOM):4096] if data.startswith(_UTF8_BOM) else data[:4096]
    if text_head.lstrip()[:5].lower() == b"solid" and b"facet" in text_head.lower():
        return refuse(limits.PART_ASCII_MESSAGE, f"{size:,} bytes of ASCII STL", "slice.part_not_binary")
    for signature, what in _SIGNATURES:
        if data.startswith(signature):
            return refuse(limits.PART_NOT_STL_MESSAGE, f"{size:,} bytes, {what}")
    if _is_text(data[:4096]):
        # An HTML or JSON error page, a note: a binary STL's triangles are never all text.
        return refuse(limits.PART_NOT_STL_MESSAGE, f"{size:,} bytes of text, starting {data[:40]!r}")
    if size < 84:
        return refuse(limits.PART_NOT_STL_MESSAGE, f"{size:,} bytes, shorter than the 84-byte header of a binary STL")
    count = int.from_bytes(data[80:84], "little")
    expected = 84 + 50 * count
    if count == 0:
        return refuse(limits.PART_NO_TRIANGLES_MESSAGE, f"{size:,} bytes; the header gives 0 triangles")
    detail = f"{size:,} bytes, not the {expected:,} a binary STL of {count:,} triangles has"
    if size < expected and expected > limits.MAX_PART_BYTES:
        # Bytes 80 to 84 describe a file larger than any part the service takes: they are not
        # a binary STL's triangle count (a PDF, an image, UTF-16 text), so nothing was cut off.
        return refuse(limits.PART_NOT_STL_MESSAGE, f"{detail}, over the {limits.MAX_PART_BYTES:,} bytes of the "
                                                   f"largest part: not a binary STL header")
    if size < expected:
        return refuse(limits.PART_CUT_OFF_MESSAGE, detail)
    return refuse(limits.PART_EXTRA_DATA_MESSAGE, detail)


def read_binary_stl(data, name, source="the STL", scale=1.0):
    """The mesh of a binary STL, refused with a MeshError the user can read. `source`
    (the file's path) leads the details. `scale` multiplies every coordinate about the STL's
    own origin before anything is measured (25.4 for a part in inches), so every check and
    every figure after it is in millimetres."""
    where = {"part": name}
    count = _binary_triangle_count(data)
    if not count:
        raise _not_binary(data, name, source)
    if count > limits.MAX_PART_TRIANGLES:
        raise MeshError(limits.TOO_DETAILED_MESSAGE.format(name=name),
                        f"{source}: {count:,} triangles, cap {limits.MAX_PART_TRIANGLES:,}", "slice.part_too_detailed",
                        where)
    records = np.frombuffer(data, dtype=_TRIANGLE, count=count, offset=84)
    corners = np.stack((records['v0'], records['v1'], records['v2']), axis=1).reshape(-1, 3)
    corners = corners.astype(np.float64) * scale
    finite = np.isfinite(corners)
    if not finite.all():
        raise MeshError(limits.NOT_FINITE_MESSAGE.format(name=name),
                        f"{source}: {int((~finite).sum()):,} coordinates are not finite numbers",
                        "slice.part_unreadable", where)
    vertices, inverse = _unique_rows(corners)
    mesh = Mesh(vertices, inverse.reshape(-1, 3), count)
    extent = vertices.max(axis=0) - vertices.min(axis=0)
    x, y, z = (round(float(v), 3) for v in extent)
    # float32 cannot hold 0.1 exactly, so a 0.1 mm side reads as 0.10000000149.
    thin = extent <= limits.MIN_PART_EXTENT_MM + 1e-6
    if thin.any():
        sentence = limits.TOO_SMALL_MESSAGE if thin.all() else limits.TOO_THIN_MESSAGE
        raise MeshError(sentence.format(name=name, x=x, y=y, z=z, thickness=round(float(extent.min()), 3)),
                        f"{source}: {x} x {y} x {z} mm, every side must be over {limits.MIN_PART_EXTENT_MM} mm",
                        "slice.part_too_small", where)
    mesh.health = analyse(mesh)
    if mesh.health["surface_triangles"] == 0:
        raise MeshError(limits.NO_SURFACE_MESSAGE.format(name=name),
                        f"{source}: all {count:,} triangles have no area", "slice.part_no_volume", where)
    if mesh.health["shared_edges"] == 0:
        raise MeshError(limits.LOOSE_TRIANGLES_MESSAGE.format(name=name),
                        f"{source}: {mesh.health['surface_triangles']:,} triangles, none shares an edge with another",
                        "slice.part_no_volume", where)
    if mesh.health["encloses_nothing"]:
        raise MeshError(limits.ENCLOSES_NOTHING_MESSAGE.format(name=name),
                        f"{source}: every edge is used twice, but the surface lies in one plane or encloses "
                        f"{mesh.health['enclosed_mm3']:.3g} mm3", "slice.part_no_volume", where)
    return mesh


def _unique_rows(rows):
    """np.unique(rows, axis=0, return_inverse=True) for an (n, 3) float array, the same
    rows in the same order, by one lexsort instead of a sort of structured rows (about six
    times faster on a part at the triangle cap)."""
    order = np.lexsort((rows[:, 2], rows[:, 1], rows[:, 0]))
    ordered = rows[order]
    first = np.empty(len(ordered), dtype=bool)
    first[:1] = True
    first[1:] = (ordered[1:] != ordered[:-1]).any(axis=1)
    inverse = np.empty(len(rows), dtype=np.intp)
    inverse[order] = np.cumsum(first) - 1
    return ordered[first], inverse


def _unique_pairs(pairs, count):
    """np.unique(pairs, axis=0, return_counts=True) for (k, 2) indices below `count`."""
    keys, uses = np.unique(pairs[:, 0].astype(np.int64) * count + pairs[:, 1], return_counts=True)
    return np.stack([keys // count, keys % count], axis=1), uses


def _components(edges, count):
    """The number of connected pieces among `count` vertices joined by `edges` (k x 2)."""
    parent = np.arange(count)
    a, b = edges[:, 0], edges[:, 1]
    while True:
        # Every vertex points at its root here; hook each root to the smaller root across
        # an edge, then jump every pointer to its new root. Labels only fall, so this ends.
        ra, rb = parent[a], parent[b]
        low = np.minimum(ra, rb)
        hooked = parent.copy()
        np.minimum.at(hooked, ra, low)
        np.minimum.at(hooked, rb, low)
        while True:
            jumped = hooked[hooked]
            if np.array_equal(jumped, hooked):
                break
            hooked = jumped
        if np.array_equal(hooked, parent):
            return int(len(np.unique(parent)))
        parent = hooked


def analyse(mesh):
    """What the checks and the server log need to know about a part's surface:

    - surface_triangles: triangles with an area (the rest are lines or points);
    - open_edges: edges used by one triangle only (holes); shared_edges: used by two or more;
      overused_edges: by three or more (not a simple surface);
    - watertight: every edge used by exactly two triangles;
    - shells: separate connected pieces of surface;
    - volume_mm3: the enclosed volume when watertight, else the bounding box's, with
      volume_basis "mesh" or "bounding box" (the memory model uses it);
    - inside_out: watertight with its faces wound inwards (a negative volume);
    - encloses_nothing: watertight, but every triangle lies in one plane or the enclosed
      volume (enclosed_mm3) is nil: faces laid on top of each other;
    Self-intersection is not looked for."""
    v = mesh.vertices
    tri = v[mesh.faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = np.linalg.norm(cross, axis=1)
    faces = mesh.faces[area > 1e-12]
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    unique, uses = _unique_pairs(edges, len(v)) if len(edges) else (edges, np.array([], int))
    extent = v.max(axis=0) - v.min(axis=0)
    watertight = bool(len(uses)) and bool((uses == 2).all())
    signed = float(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6.0)
    used_vertices = np.unique(faces) if len(faces) else np.array([], int)
    remap = np.full(len(v), -1)
    remap[used_vertices] = np.arange(len(used_vertices))
    shells = _components(remap[unique], len(used_vertices)) if len(used_vertices) else 0
    scale = float(extent.max())
    encloses_nothing = False
    if watertight:
        k = int(np.argmax(area))                       # the largest triangle's plane
        normal = cross[k] / area[k]
        in_plane = float(np.abs((v[used_vertices] - tri[k, 0]) @ normal).max()) <= 1e-6 * scale
        encloses_nothing = in_plane or abs(signed) <= 1e-9 * scale ** 3
    return {"encloses_nothing": encloses_nothing, "enclosed_mm3": abs(signed),"triangles": int(mesh.triangles), "surface_triangles": int(len(faces)),
            "open_edges": int((uses == 1).sum()), "shared_edges": int((uses >= 2).sum()),
            "overused_edges": int((uses > 2).sum()), "watertight": watertight, "shells": shells,
            "volume_mm3": round(abs(signed) if watertight else float(np.prod(extent)), 1),
            "volume_basis": "mesh" if watertight else "bounding box",
            "inside_out": watertight and signed < 0,
            "size_mm": [round(float(e), 3) for e in extent]}


def part_warnings(mesh, name, units="mm"):
    """The warnings a part that passed every check still carries: [{code, message, where,
    detail}], in the order of WARNINGS. A part labelled in inches is never said to be maybe
    in inches: the warning exists for a file in inches read as millimetres."""
    return health_warnings(mesh.health or analyse(mesh), name, units)


def health_warnings(health, name, units="mm"):
    """part_warnings from a part's analyse() alone: a part kept in the part store is named
    only when a plate configuration names it."""
    x, y, z = health["size_mm"]
    found = []
    if not health["watertight"]:
        # Not watertight: an edge used by one face (a hole), or by more than two.
        sentence = WARNINGS["slice.part_not_watertight"] if health["open_edges"] else OVERLAID_FACES_MESSAGE
        found.append(("slice.part_not_watertight", sentence, dict(open_edges=health["open_edges"],
                                                                  overused_edges=health["overused_edges"],
                                                                  shells=health["shells"])))
    if health["inside_out"]:
        found.append(("slice.part_inside_out", WARNINGS["slice.part_inside_out"], {}))
    if max(x, y, z) < MAYBE_INCHES_MM and units != "in":
        found.append(("slice.part_maybe_inches", WARNINGS["slice.part_maybe_inches"], dict(x=x, y=y, z=z)))
    detail = (f"{health['open_edges']:,} open edges, {health['overused_edges']:,} edges used by three or more "
              f"triangles, {health['shells']:,} shells, {x} x {y} x {z} mm")
    return [{"code": code, "message": sentence.format(name=name, **values), "where": {"part": name},
             "detail": detail} for code, sentence, values in found]


def part_size_mm(mesh):
    x, y, z = (mesh.vertices.max(axis=0) - mesh.vertices.min(axis=0)).tolist()
    return {'x': round(x, 3), 'y': round(y, 3), 'z': round(z, 3)}


def _hull(points):
    """Counterclockwise convex hull of 2D points, without the closing point."""
    geometry = shapely.MultiPoint(points).convex_hull
    if geometry.geom_type != 'Polygon':         # every point on one line: its bounding box
        geometry = shapely.MultiPoint(points).envelope
    if geometry.geom_type != 'Polygon':
        geometry = geometry.buffer(0.0005, cap_style='square')
    ring = shapely.geometry.polygon.orient(geometry, 1.0).exterior.coords
    return np.asarray(ring[:-1], dtype=np.float64)


def _footprint(hull, low, high):
    """The footprint dict for a hull and the rotated part's bounding box."""
    cx, cy = (low[0] + high[0]) / 2, (low[1] + high[1]) / 2
    centred = np.round(hull - (cx, cy), 3) + 0.0      # + 0.0 turns -0.0 into 0.0
    return {'hull': centred.tolist(), 'height': round(float(high[2] - low[2]), 3),
            'offset': [round(float(cx), 3) + 0.0, round(float(cy), 3) + 0.0, round(float(low[2]), 3) + 0.0]}


def turned_footprint(mesh, matrix):
    """The footprint of the part turned by a 3 x 3 row-major `matrix` (v' = M v), in the form
    of orientation_footprints' entries: for an instance laid by a general rotation."""
    rotated = mesh.vertices @ np.asarray(matrix, dtype=np.float64).T
    low, high = rotated.min(axis=0), rotated.max(axis=0)
    return _footprint(_hull(rotated[:, :2]), low, high)


ON_THE_PLATE_MM = 1e-3        # a vertex this close to the turned part's lowest z lies on the plate


def contact_area_mm2(mesh, matrix):
    """The area, in mm², of the part's own faces that lie on the plate once it is turned by
    `matrix`: the triangles whose three vertices are within ON_THE_PLATE_MM of its lowest
    point. Zero for a part that touches the plate only along an edge or at a point (a part
    laid on a face of its convex hull that bridges a hollow of it, for one)."""
    rotated = mesh.vertices @ np.asarray(matrix, dtype=np.float64).T
    on_plate = np.abs(rotated[:, 2] - rotated[:, 2].min()) <= ON_THE_PLATE_MM
    flat = mesh.faces[on_plate[mesh.faces].all(axis=1)]
    if len(flat) == 0:
        return 0.0
    a, b, c = (rotated[flat[:, i], :2] for i in range(3))
    cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    return float(np.abs(cross).sum() / 2)


def orientation_footprints(mesh):
    """{orientation: {'hull', 'height', 'offset'}} for each of plate.ORIENTATIONS.

    The hull is the convex hull of the rotated part seen from above, counterclockwise and
    centred on its bounding-box centre; offset is that centre and the lowest z after the
    rotation, so a viewer can place the mesh exactly where the slicer will.
    """
    footprints, computed = {}, {}
    for name in ('+z', '+x', '+y'):
        rotated = mesh.vertices @ np.asarray(ORIENTATION_MATRICES[name], dtype=np.float64).T
        low, high = rotated.min(axis=0), rotated.max(axis=0)
        hull = _hull(rotated[:, :2])
        computed[name] = (hull, low, high)
        footprints[name] = _footprint(hull, low, high)
    for name, (base, axis) in _MIRRORS.items():
        hull, low, high = computed[base]
        flip = np.array([-1.0 if i == axis else 1.0 for i in range(2)] + [-1.0])
        mirrored = (hull * flip[:2])[::-1]               # mirroring reverses the winding
        mirrored_low, mirrored_high = np.minimum(low * flip, high * flip), np.maximum(low * flip, high * flip)
        footprints[name] = _footprint(mirrored, mirrored_low, mirrored_high)
    return {name: footprints[name] for name in ORIENTATION_MATRICES}
