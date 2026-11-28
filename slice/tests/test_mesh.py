"""The numpy STL reader, its limits and the six orientation footprints."""
import struct

import pytest

from helpers import box_stl, cylinder_stl
from penguin_slice import limits
from penguin_slice.mesh import (MeshError, _hull, analyse, orientation_footprints, part_size_mm, part_warnings,
                                read_binary_stl, turned_footprint)
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


class TestUnits:
    """A part in inches is scaled by 25.4 about the STL's own origin before any check."""

    def test_a_part_in_inches_is_measured_25_4_times_larger(self):
        mesh = read_binary_stl(box_stl(1, 2, 0.5, origin=(1, 0, 0)), "Box", scale=25.4)
        assert mesh.health["size_mm"] == [25.4, 50.8, 12.7]
        assert mesh.vertices.min(axis=0).tolist() == pytest.approx([25.4, 0, 0])        # about the origin
        assert mesh.health["volume_mm3"] == pytest.approx(1 * 2 * 0.5 * 25.4 ** 3, abs=0.1)

    def test_too_small_is_judged_on_the_scaled_part(self):
        with pytest.raises(MeshError) as caught:
            read_binary_stl(box_stl(0.05, 0.05, 0.05), "Box")
        assert caught.value.error_code == "slice.part_too_small"
        read_binary_stl(box_stl(0.05, 0.05, 0.05), "Box", scale=25.4)       # 1.27 mm a side

    def test_a_small_part_in_inches_does_not_warn_of_inches(self):
        mesh = read_binary_stl(box_stl(0.15, 0.1, 0.1), "Box", scale=25.4)  # 3.81 mm: under 5 mm
        assert part_warnings(mesh, "Box", units="in") == []
        assert [w["code"] for w in part_warnings(mesh, "Box", units="mm")] == ["slice.part_maybe_inches"]


class TestTurnedFootprint:
    def test_a_turn_of_an_orientation_gives_its_footprint(self):
        mesh = read_binary_stl(box_stl(), "Box")
        for name, matrix in ORIENTATION_MATRICES.items():
            turned, oriented = turned_footprint(mesh, matrix), orientation_footprints(mesh)[name]
            assert (turned["height"], turned["offset"]) == (oriented["height"], oriented["offset"]), name
            assert sorted(map(tuple, turned["hull"])) == sorted(map(tuple, oriented["hull"])), name
            assert signed_area(turned["hull"]) > 0, name

    def test_a_turn_about_the_vertical_turns_the_footprint(self):
        mesh = read_binary_stl(box_stl(10, 20, 30), "Box")
        quarter = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
        footprint = turned_footprint(mesh, quarter)
        x0, x1, y0, y1 = hull_box(footprint["hull"])
        assert (x1 - x0, y1 - y0, footprint["height"]) == pytest.approx((20, 10, 30))
        assert footprint["offset"] == [-10.0, 5.0, 0.0]


class TestContactArea:
    """The area of the part's faces that lie on the plate once it is turned: zero for a part
    that touches the plate only along an edge or at a point, which the pinned Orca cannot
    give a first layer (slice.rests_on_an_edge)."""

    BRACKET = (__import__("helpers").CONTRACTS / "examples" / "parts" / "bracket.stl").read_bytes()
    HULL_FACE = (0.707106781, -0.588348405, 0.39223227, 0.0)     # the contract example's fourth instance

    def test_a_box_on_a_face_rests_on_that_face(self):
        from penguin_slice.mesh import contact_area_mm2
        mesh = read_binary_stl(box_stl(10, 20, 30), "Box")
        assert contact_area_mm2(mesh, ORIENTATION_MATRICES["+z"]) == pytest.approx(200)
        assert contact_area_mm2(mesh, ORIENTATION_MATRICES["+x"]) == pytest.approx(600)

    def test_a_box_on_an_edge_or_a_corner_has_none(self):
        import math
        from penguin_slice.mesh import contact_area_mm2
        from penguin_slice.plate import quaternion_matrix
        mesh = read_binary_stl(box_stl(10, 20, 30), "Box")
        on_edge = quaternion_matrix([math.cos(math.pi / 8), math.sin(math.pi / 8), 0, 0])
        assert contact_area_mm2(mesh, on_edge) == 0
        corner_up = quaternion_matrix([0.88807383, 0.32505758, -0.32505758, 0.0])
        assert contact_area_mm2(mesh, corner_up) == 0

    def test_the_bracket_on_its_hull_face_across_the_open_corner_has_none(self):
        from penguin_slice.mesh import contact_area_mm2
        from penguin_slice.plate import quaternion_matrix
        mesh = read_binary_stl(self.BRACKET, "Bracket")
        assert contact_area_mm2(mesh, quaternion_matrix(self.HULL_FACE)) == 0
        half = 0.5 ** 0.5
        assert contact_area_mm2(mesh, quaternion_matrix([half, 0, -half, 0])) == pytest.approx(360)   # its -x face

    def test_a_part_in_inches_is_measured_in_millimetres(self):
        from penguin_slice.mesh import contact_area_mm2
        mesh = read_binary_stl(box_stl(1, 1, 0.5), "Block", scale=25.4)
        assert contact_area_mm2(mesh, ORIENTATION_MATRICES["+z"]) == pytest.approx(25.4 ** 2)


class TestFirstLayerSection:
    """The part's section a given height above its lowest point once it is turned, the shape
    the slicer's first layer is cut from: a curved part that touches the plate at a point or
    along a line is millimetres across there, a part on an edge a fraction of a line."""

    AT, HALF_LINE = 0.15, 0.31          # the default process: half its 0.3 mm first layer, half its 0.62 mm line

    def section(self, stl, matrix, name="Part"):
        from penguin_slice.mesh import first_layer_section
        return first_layer_section(read_binary_stl(stl, name), matrix, self.AT)

    def test_a_box_on_a_face_is_cut_to_that_face(self):
        assert self.section(box_stl(10, 20, 30), ORIENTATION_MATRICES["+z"]).area == pytest.approx(200)

    def test_a_box_on_an_edge_is_a_strip_narrower_than_a_line(self):
        import math
        from penguin_slice.plate import quaternion_matrix
        on_edge = quaternion_matrix([math.cos(math.pi / 8), math.sin(math.pi / 8), 0, 0])
        section = self.section(box_stl(10, 20, 30), on_edge)
        assert section.area == pytest.approx(10 * 2 * self.AT, rel=1e-3)        # 10 mm long, 0.3 mm wide
        assert section.buffer(-self.HALF_LINE).is_empty

    def test_the_bracket_on_its_hull_face_is_two_strips_narrower_than_a_line(self):
        from penguin_slice.plate import quaternion_matrix
        section = self.section(TestContactArea.BRACKET, quaternion_matrix(TestContactArea.HULL_FACE), "Bracket")
        assert section.area > 0 and section.buffer(-self.HALF_LINE).is_empty

    def test_a_ball_on_its_pole_is_millimetres_across(self):
        from helpers import ball_stl
        from penguin_slice.mesh import contact_area_mm2
        mesh_matrix = ORIENTATION_MATRICES["+z"]
        assert contact_area_mm2(read_binary_stl(ball_stl(), "Ball"), mesh_matrix) == 0
        section = self.section(ball_stl(), mesh_matrix, "Ball")
        assert section.area > 10 and not section.buffer(-self.HALF_LINE).is_empty

    def test_a_tube_lying_on_a_line_of_vertices_is_millimetres_across(self):
        from penguin_slice.mesh import contact_area_mm2
        tube = cylinder_stl(10, 40, segments=48)          # vertices at 0 and 180 degrees: '+x' lays a line on the plate
        assert contact_area_mm2(read_binary_stl(tube, "Tube"), ORIENTATION_MATRICES["+x"]) == 0
        section = self.section(tube, ORIENTATION_MATRICES["+x"], "Tube")
        assert section.area > 40 and not section.buffer(-self.HALF_LINE).is_empty

    def test_above_the_part_or_through_an_open_surface_it_is_empty(self):
        from types import SimpleNamespace
        from penguin_slice.mesh import first_layer_section
        box = read_binary_stl(box_stl(10, 20, 30), "Box")
        assert first_layer_section(box, ORIENTATION_MATRICES["+z"], 31).is_empty
        # The box without one side (the reader refuses so open a part; a part read before may be).
        open_box = SimpleNamespace(vertices=box.vertices, faces=box.faces[[0, 1, 2, 3, 6, 7, 8, 9, 10, 11]])
        cut = first_layer_section(box, ORIENTATION_MATRICES["+z"], self.AT)
        assert cut.area == pytest.approx(200)
        assert first_layer_section(open_box, ORIENTATION_MATRICES["+z"], self.AT).is_empty   # a U, no outline

    def test_a_part_with_a_hole_through_it_keeps_the_hole(self):
        import numpy as np
        from helpers import mesh_stl
        outer, inner = (read_binary_stl(box_stl(s, s, 5, origin=(o, o, 0)), "x") for s, o in ((20, 0), (10, 5)))
        # The inner box's faces turned inward: a 20 mm square with a 10 mm square hole through it.
        stl = mesh_stl(np.vstack([outer.vertices, inner.vertices]),
                       np.vstack([outer.faces, inner.faces[:, ::-1] + len(outer.vertices)]))
        assert self.section(stl, ORIENTATION_MATRICES["+z"]).area == pytest.approx(300)


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
