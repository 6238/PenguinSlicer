"""The numpy STL reader, its limits and the six orientation footprints."""
import struct

import pytest

from helpers import box_stl, cylinder_stl
from penguin_slice import limits
from penguin_slice.mesh import MeshError, _hull, analyse, orientation_footprints, part_size_mm, part_warnings, read_binary_stl
from penguin_slice.plate import ORIENTATION_MATRICES, ORIENTATIONS

UNREADABLE = "The file for Box could not be read as a part."


def hull_box(hull):
    xs, ys = [p[0] for p in hull], [p[1] for p in hull]
    return min(xs), max(xs), min(ys), max(ys)


def signed_area(hull):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(hull, hull[1:] + hull[:1])) / 2


def read_or_error(triangles):
    """read_binary_stl on raw triangles (zero normals): the mesh, or the MeshError it raised."""
    body = b"".join(struct.pack("<12fH", 0, 0, 0, *[c for v in t for c in v], 0) for t in triangles)
    try:
        return read_binary_stl(b"x".ljust(80, b"\0") + struct.pack("<I", len(triangles)) + body, "Box")
    except MeshError as exc:
        return exc


@pytest.mark.parametrize("seed", range(5))
def test_the_fast_unique_rows_and_pairs_are_numpys(seed):
    import numpy as np
    from penguin_slice.mesh import _unique_pairs, _unique_rows
    rng = np.random.default_rng(seed)
    rows = rng.integers(-3, 4, size=(400, 3)).astype(np.float64) / 2     # many repeats
    unique, inverse = _unique_rows(rows)
    expected, expected_inverse = np.unique(rows, axis=0, return_inverse=True)
    assert np.array_equal(unique, expected) and np.array_equal(inverse, expected_inverse.reshape(-1))
    pairs = np.sort(rng.integers(0, 30, size=(300, 2)), axis=1)
    got, uses = _unique_pairs(pairs, 30)
    want, want_uses = np.unique(pairs, axis=0, return_counts=True)
    assert np.array_equal(got, want) and np.array_equal(uses, want_uses)


def test_reads_binary_box_and_size():
    mesh = read_binary_stl(box_stl(), "Box")
    assert mesh.triangles == 12
    assert mesh.vertices.shape == (8, 3)      # de-duplicated
    assert mesh.faces.shape == (12, 3)
    assert part_size_mm(mesh) == {"x": 10.0, "y": 20.0, "z": 30.0}


@pytest.mark.parametrize("data, message, detail", [
    (b"solid box\nendsolid box\n", "The file for Box is not an STL file.",
     "box.stl: 23 bytes of text, starting b'solid box\\nendsolid box\\n'"),
    # 84 bytes or more of text once read as a binary STL "cut off before its end".
    (b"<!DOCTYPE html><html><body>502 Bad Gateway</body></html>" * 4, "The file for Box is not an STL file.",
     "box.stl: 224 bytes of text, starting b'<!DOCTYPE html><html><body>502 Bad Gatew'"),
    (b'{"error": "Not Found", "status": 404}\n' * 3, "The file for Box is not an STL file.",
     "box.stl: 114 bytes of text, starting b'{\"error\": \"Not Found\", \"status\": 404}\\n{\"'"),
    (b"\x1f\x8b\x08\x00" + b"\x00" * 120, "The file for Box is not an STL file.", "box.stl: 124 bytes, a gzip archive"),
    (b"\x01\x02\x03", "The file for Box is not an STL file.",
     "box.stl: 3 bytes, shorter than the 84-byte header of a binary STL"),
    (box_stl()[:-1], "The file for Box is cut off before its end.",
     "box.stl: 683 bytes, not the 684 a binary STL of 12 triangles has"),
    (box_stl() + b"\0", "The file for Box has extra data after its last triangle.",
     "box.stl: 685 bytes, not the 684 a binary STL of 12 triangles has"),
    (b"", "The file for Box is empty.", "box.stl: 0 bytes"),
    (box_stl()[:84], "The file for Box is cut off before its end.",
     "box.stl: 84 bytes, not the 684 a binary STL of 12 triangles has"),
    (b" " * 80 + struct.pack("<I", 0), "The file for Box has no triangles in it.",
     "box.stl: 84 bytes; the header gives 0 triangles"),
], ids=["text", "html", "json", "gzip", "short-binary", "truncated", "extra", "empty", "header-only",
        "zero-triangles"])
def test_damaged_or_empty_refused_with_a_true_sentence(data, message, detail):
    with pytest.raises(MeshError) as caught:
        read_binary_stl(data, "Box", source="box.stl")
    assert caught.value.message == message
    assert (caught.value.error_code, caught.value.where) == ("slice.part_unreadable", {"part": "Box"})
    assert caught.value.details == detail


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_refused(value):
    data = bytearray(box_stl())
    data[84 + 12:84 + 16] = struct.pack("<f", value)
    with pytest.raises(MeshError) as caught:
        read_binary_stl(bytes(data), "Box")
    assert caught.value.message == "The file for Box has coordinates that are not numbers."
    assert caught.value.details == "the STL: 1 coordinates are not finite numbers"


class TestAnalyse:
    def test_closed_box(self):
        health = analyse(read_binary_stl(box_stl(10, 20, 30), "Box"))
        assert health == {"triangles": 12, "surface_triangles": 12, "open_edges": 0, "shared_edges": 18,
                          "overused_edges": 0, "watertight": True, "shells": 1, "volume_mm3": 6000.0,
                          "volume_basis": "mesh", "inside_out": False, "size_mm": [10.0, 20.0, 30.0],
                          "encloses_nothing": False, "enclosed_mm3": pytest.approx(6000.0)}

    @pytest.mark.parametrize("winding", ["same", "opposite"])
    def test_coincident_triangles_enclose_nothing(self, winding):
        # Every edge used twice, so "watertight": once passed to Orca, which answered -50.
        t = [(0, 0, 0), (30, 0, 5), (0, 30, 9)]
        mesh = read_or_error([t, t if winding == "same" else t[::-1]])
        assert mesh.error_code == "slice.part_no_volume"
        assert mesh.message == "Box is a surface folded onto itself that encloses nothing, so there is nothing to " \
                               "print."
    def test_open_mesh_uses_its_bounding_box_volume(self):
        data = box_stl(10, 10, 10)
        open_box = data[:80] + struct.pack("<I", 10) + data[84 + 100:]
        health = analyse(read_binary_stl(open_box, "Open"))
        assert (health["watertight"], health["open_edges"], health["volume_basis"], health["volume_mm3"]) == \
            (False, 4, "bounding box", 1000.0)

    def test_two_boxes_are_two_shells(self):
        a, b = box_stl(10, 10, 10), box_stl(10, 10, 10, origin=(20, 0, 0))
        both = a[:80] + struct.pack("<I", 24) + a[84:] + b[84:]
        assert analyse(read_binary_stl(both, "Two"))["shells"] == 2

    def test_a_long_chain_of_pieces_is_counted_exactly(self):
        # Many shells and a long one: the label propagation must converge on both.
        assert analyse(read_binary_stl(cylinder_stl(segments=400), "Cyl"))["shells"] == 1

    def test_inside_out_box(self):
        data = bytearray(box_stl(10, 10, 10))
        for i in range(12):
            start = 84 + 50 * i + 12
            v1, v2 = data[start + 12:start + 24], data[start + 24:start + 36]
            data[start + 12:start + 24], data[start + 24:start + 36] = v2, v1
        health = analyse(read_binary_stl(bytes(data), "Inverted"))
        assert health["inside_out"] and health["volume_mm3"] == 1000.0


class TestWarnings:
    def test_a_clean_part_has_none(self):
        assert part_warnings(read_binary_stl(box_stl(), "Box"), "Box") == []

    def test_each_warning_names_the_part(self):
        data = box_stl(2, 1, 0.5)
        open_box = data[:80] + struct.pack("<I", 10) + data[84 + 100:]
        found = part_warnings(read_binary_stl(open_box, "Shim"), "Shim")
        assert [w["code"] for w in found] == ["slice.part_not_watertight", "slice.part_maybe_inches"]
        assert found[0]["message"] == ("Shim has holes in its surface (4 open edges, 1 separate pieces); if the "
                                       "slice fails or looks wrong, repair it in CAD.")
        assert all(w["where"] == {"part": "Shim"} for w in found)
        assert found[0]["detail"].startswith("4 open edges, 0 edges used by three or more triangles, 1 shells")

    @pytest.mark.parametrize("label", ["every face doubled", "a box and its mirror image"])
    def test_a_closed_surface_with_faces_laid_on_each_other_is_not_said_to_have_holes(self, label):
        # Such a part was once warned to have "holes in its surface (0 open edges, ...)".
        box = box_stl(20, 20, 10)
        count = struct.unpack("<I", box[80:84])[0]
        second = box[84:]
        if label == "a box and its mirror image":
            mirrored = bytearray(second)
            for i in range(count):                   # swap two vertices: the faces wound the other way
                start = 50 * i + 12
                mirrored[start + 12:start + 24], mirrored[start + 24:start + 36] = \
                    second[start + 24:start + 36], second[start + 12:start + 24]
            second = bytes(mirrored)
        data = box[:80] + struct.pack("<I", 2 * count) + box[84:] + second
        mesh = read_binary_stl(data, "Box")
        found = part_warnings(mesh, "Box")
        assert [w["code"] for w in found] == ["slice.part_not_watertight"]
        assert found[0]["message"] == ("Box has faces laid on top of each other (18 edges shared by more than two "
                                       "faces, 1 separate pieces); if the slice fails or looks wrong, repair it in "
                                       "CAD.")
        assert "holes" not in found[0]["message"]

    def test_holes_and_faces_on_each_other_together_are_said_to_be_holes(self):
        box = box_stl(20, 20, 10)
        count = struct.unpack("<I", box[80:84])[0]
        data = box[:80] + struct.pack("<I", count) + box[84:-50] + box[84:134]    # one face gone, one doubled
        mesh = read_binary_stl(data, "Box")
        assert mesh.health["open_edges"] > 0 and mesh.health["overused_edges"] > 0
        found = part_warnings(mesh, "Box")
        assert found[0]["message"].startswith(f"Box has holes in its surface ({mesh.health['open_edges']} open edges, ")

    def test_warnings_from_a_mesh_without_health(self):
        mesh = read_binary_stl(box_stl(), "Box")
        mesh.health = None
        assert part_warnings(mesh, "Box") == []


def test_triangle_cap():
    count = limits.MAX_PART_TRIANGLES + 1
    data = b" " * 80 + struct.pack("<I", count) + bytes(50 * count)
    with pytest.raises(MeshError) as caught:
        read_binary_stl(data, "Gear", source="gear.stl")
    assert caught.value.message == "Gear is too detailed to print here (over 150,000 triangles)."
    assert (caught.value.error_code, caught.value.details) == ("slice.part_too_detailed",
                                                               "gear.stl: 150,001 triangles, cap 150,000")


def test_tiny_part_refused_at_the_limit_and_accepted_above_it():
    with pytest.raises(MeshError) as caught:
        read_binary_stl(box_stl(10, 20, 0.1), "Shim", source="shim.stl")
    assert caught.value.message == "Shim is flat: it is 0.1 mm thick, too thin to print."
    assert (caught.value.error_code, caught.value.details) == (
        "slice.part_too_small", "shim.stl: 10.0 x 20.0 x 0.1 mm, every side must be over 0.1 mm")
    read_binary_stl(box_stl(10, 20, 0.11), "Shim")


@pytest.mark.parametrize("name", ORIENTATIONS)
def test_matrices_put_the_named_axis_up(name):
    sign = 1 if name[0] == "+" else -1
    axis = "xyz".index(name[1])
    assert [row[axis] * sign for row in ORIENTATION_MATRICES[name]] == [0, 0, 1]


def test_footprints_six_orientations():
    footprints = orientation_footprints(read_binary_stl(box_stl(), "Box"))
    assert list(footprints) == list(ORIENTATION_MATRICES)
    spans = {"+z": (10, 20, 30), "-z": (10, 20, 30), "+x": (30, 20, 10), "-x": (30, 20, 10),
             "+y": (10, 30, 20), "-y": (10, 30, 20)}
    for name, (sx, sy, height) in spans.items():
        footprint = footprints[name]
        x0, x1, y0, y1 = hull_box(footprint["hull"])
        assert (x1 - x0, y1 - y0) == pytest.approx((sx, sy), abs=1e-3), name
        assert (x0 + x1, y0 + y1) == pytest.approx((0, 0), abs=1e-3), name       # centred on (0, 0)
        assert footprint["height"] == pytest.approx(height, abs=1e-3), name
        assert signed_area(footprint["hull"]) > 0, name                           # counterclockwise
    # offset: the bounding-box centre and lowest point after the matrix.
    assert footprints["+z"]["offset"] == [5.0, 10.0, 0.0]
    assert footprints["-z"]["offset"] == [5.0, -10.0, -30.0]
    assert footprints["+x"]["offset"] == [-15.0, 10.0, 0.0]
    assert footprints["-x"]["offset"] == [15.0, 10.0, -10.0]
    assert footprints["+y"]["offset"] == [5.0, -15.0, 0.0]
    assert footprints["-y"]["offset"] == [5.0, 15.0, -20.0]


def test_opposite_orientations_mirror():
    footprints = orientation_footprints(read_binary_stl(cylinder_stl(), "Cylinder"))
    plus, minus = footprints["+z"]["hull"], footprints["-z"]["hull"]
    assert sorted((x, -y) for x, y in plus) == sorted(map(tuple, minus))
    assert footprints["+z"]["height"] == footprints["-z"]["height"]
    assert signed_area(minus) > 0
    assert len(plus) > 60                   # a 64-segment cylinder's hull


def test_hull_of_collinear_points_is_their_box():
    hull = _hull([(0, 0), (5, 5), (10, 10)])
    assert hull_box(hull.tolist()) == (0, 10, 0, 10)


def test_hull_of_one_point_is_a_square_one_micrometre_wide():
    hull = _hull([(0, 0), (0, 0)]).tolist()
    assert hull_box(hull) == pytest.approx((-0.0005, 0.0005, -0.0005, 0.0005))
    assert signed_area(hull) > 0


def test_hull_of_points_on_an_axis_is_a_zero_area_ring():
    # Known, kept by the port: shapely's envelope of points on one axis is a Polygon of zero
    # area, so the buffer branch never runs and the hull has no area. A real part cannot
    # reach this (the too-small check needs extent in every direction).
    hull = _hull([(0, 0), (5, 0), (10, 0)]).tolist()
    assert hull_box(hull) == (0, 10, 0, 0)
    assert signed_area(hull) == 0
