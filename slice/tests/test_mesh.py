"""The numpy STL reader, its limits and the six orientation footprints."""
import struct

import pytest

from helpers import box_stl, cylinder_stl
from penguin_slice import limits
from penguin_slice.mesh import MeshError, _hull, orientation_footprints, part_size_mm, read_binary_stl
from penguin_slice.plate import ORIENTATION_MATRICES, ORIENTATIONS

UNREADABLE = "The file for Box could not be read as a part."


def hull_box(hull):
    xs, ys = [p[0] for p in hull], [p[1] for p in hull]
    return min(xs), max(xs), min(ys), max(ys)


def signed_area(hull):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(hull, hull[1:] + hull[:1])) / 2


def test_reads_binary_box_and_size():
    mesh = read_binary_stl(box_stl(), "Box")
    assert mesh.triangles == 12
    assert mesh.vertices.shape == (8, 3)      # de-duplicated
    assert mesh.faces.shape == (12, 3)
    assert part_size_mm(mesh) == {"x": 10.0, "y": 20.0, "z": 30.0}


@pytest.mark.parametrize("data, detail", [
    (b"solid box\nendsolid box\n", "box.stl: 23 bytes, shorter than the 84-byte header of a binary STL"),
    (box_stl()[:-1], "box.stl: 683 bytes, not the 684 a binary STL of 12 triangles has"),
    (b"", "box.stl: 0 bytes, shorter than the 84-byte header of a binary STL"),
    (box_stl()[:84], "box.stl: 84 bytes, not the 684 a binary STL of 12 triangles has"),
    (b" " * 80 + struct.pack("<I", 0), "box.stl: the header gives 0 triangles"),
], ids=["ascii", "truncated", "empty", "header-only", "zero-triangles"])
def test_ascii_truncated_or_empty_refused(data, detail):
    with pytest.raises(MeshError) as caught:
        read_binary_stl(data, "Box", source="box.stl")
    assert caught.value.message == UNREADABLE
    assert (caught.value.error_code, caught.value.where) == ("slice.part_unreadable", {"part": "Box"})
    assert caught.value.details == detail


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_refused(value):
    data = bytearray(box_stl())
    data[84 + 12:84 + 16] = struct.pack("<f", value)
    with pytest.raises(MeshError) as caught:
        read_binary_stl(bytes(data), "Box")
    assert caught.value.message == UNREADABLE
    assert caught.value.details == "the STL: 1 coordinates are not finite numbers"


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
    assert caught.value.message == "Shim is too small to print (under 0.1 mm)."
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
