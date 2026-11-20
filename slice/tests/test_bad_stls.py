"""The corpus of bad part files (fixtures/bad_stls/, written by fixtures/make_bad_stls.py)
through the plate configuration checks: each file gets a true error report or a documented warning,
never a crash or a hang. Then random bytes and randomly damaged good files thrown at the
reader (Hypothesis, derandomized: the same examples on every run, no example database).
"""
import json
import struct

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from helpers import FIXTURES, box_stl
from penguin_slice import limits
from penguin_slice.errors import error_report
from penguin_slice.mesh import Mesh, MeshError, read_binary_stl
from penguin_slice.service import read_plate_configuration

CORPUS = FIXTURES / "bad_stls"
FUZZ = settings(derandomize=True, database=None, max_examples=300, deadline=None,
                suppress_health_check=[HealthCheck.too_slow])


def make_bad_stls():
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_bad_stls", FIXTURES / "make_bad_stls.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(tmp_path, data, orientation="+z", angle=0):
    """read_plate_configuration on a plate configuration of one instance of `data` at the plate's centre: its
    error report, or its part warnings' codes."""
    (tmp_path / "part.stl").write_bytes(data)
    job = {"parts": {"p": {"name": "Part", "stl": "part.stl"}},
           "instances": [{"ref": "p", "orientation": orientation, "angle": angle, "x": 170.0, "y": 160.0}]}
    try:
        plate_configuration = read_plate_configuration(job, tmp_path)
    except Exception as exc:
        return error_report(exc)
    return [w["code"] for w in plate_configuration.part_warnings()]


# file -> (error code, the sentence) for a refusal, or the list of warning codes.
OUTCOMES = {
    "empty.stl": ("slice.part_unreadable", "The file for Part is empty."),
    "one_byte.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    "cut_mid_triangle.stl": ("slice.part_unreadable", "The file for Part is cut off before its end."),
    "count_larger.stl": ("slice.part_unreadable", "The file for Part is cut off before its end."),
    "count_smaller.stl": ("slice.part_unreadable", "The file for Part has extra data after its last triangle."),
    "count_zero.stl": ("slice.part_unreadable", "The file for Part has no triangles in it."),
    "ascii.stl": ("slice.part_not_binary", "The file for Part is a text STL; the slicer needs a binary STL."),
    # Once "is not an STL file".
    "ascii_capitals.stl": ("slice.part_not_binary", "The file for Part is a text STL; the slicer needs a binary STL."),
    "ascii_with_bom.stl": ("slice.part_not_binary", "The file for Part is a text STL; the slicer needs a binary STL."),
    # Once "cut off before its end": bytes 80 to 84 read as a count of millions of triangles.
    "pdf.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    "jpeg.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    "utf16_text.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    "png.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    "3mf.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    "text.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    # Over 84 bytes: once "cut off before its end".
    "html_error_page.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    "gzip.stl": ("slice.part_unreadable", "The file for Part is not an STL file."),
    # Every edge used twice: once "watertight", and Orca's -50 "No part is fully on the plate".
    "coincident_triangles.stl": ("slice.part_no_volume", "Part is a surface folded onto itself that encloses "
                                                         "nothing, so there is nothing to print."),
    "nan.stl": ("slice.part_unreadable", "The file for Part has coordinates that are not numbers."),
    "infinite.stl": ("slice.part_unreadable", "The file for Part has coordinates that are not numbers."),
    "absurd_coordinates.stl": ("slice.part_too_large", "Part is 1e+30 x 1e+30 x 1e+30 mm, larger than the printer "
                                                        "can print in any orientation (340.0 x 320.0 x 340.0 mm)."),
    "all_degenerate.stl": ("slice.part_no_volume",
                           "Part has no surface: every triangle in its file is a line or a point."),
    "single_triangle.stl": ("slice.part_no_volume",
                            "Part is loose triangles that enclose nothing, so there is nothing to print."),
    "flat_sheet.stl": ("slice.part_too_small", "Part is flat: it is 0.0 mm thick, too thin to print."),
    "open_box.stl": ["slice.part_not_watertight"],
    "slivers_and_lattice.stl": ["slice.part_not_watertight"],      # Orca then refuses it: tests_orca
    "inverted_normals.stl": ["slice.part_inside_out"],
    "self_intersecting.stl": [],                                     # not looked for; Orca slices it
    "two_shells.stl": [],
    "larger_than_plate.stl": ("slice.placement_off_plate", "Part #1 is not fully on the plate."),
    "taller_than_printer.stl": ("slice.placement_too_tall", "Part #1 is taller than the printer can print (340 mm)."),
    "inch_file.stl": ["slice.part_maybe_inches"],
    "thousandth_of_a_mm.stl": ("slice.part_too_small", "Part is too small to print (0.001 x 0.001 x 0.001 mm)."),
}


def test_the_corpus_is_what_its_script_writes():
    module = make_bad_stls()
    assert sorted(p.name for p in CORPUS.iterdir()) == sorted(module.CASES) == sorted(OUTCOMES)
    for name, build in module.CASES.items():
        assert (CORPUS / name).read_bytes() == build(), name


@pytest.mark.parametrize("name", sorted(OUTCOMES))
def test_each_bad_file_gets_a_true_answer(tmp_path, name):
    outcome = check(tmp_path, (CORPUS / name).read_bytes())
    expected = OUTCOMES[name]
    if isinstance(expected, list):
        assert outcome == expected, name
    else:
        assert (outcome["code"], outcome["message"]) == expected, name
        assert outcome["where"].get("part") == "Part"
        assert outcome["detail"]


def test_a_tall_part_laid_on_its_side_is_accepted(tmp_path):
    # 350 mm long on its side: it fits the 340 x 320 plate only turned towards the diagonal.
    assert check(tmp_path, (CORPUS / "taller_than_printer.stl").read_bytes(), orientation="+x", angle=43) == []


@pytest.fixture(scope="module")
def dense(tmp_path_factory):
    module = make_bad_stls()
    return {n: module.dense_stl(n) for n in (limits.MAX_PART_TRIANGLES, limits.MAX_PART_TRIANGLES + 1)}


def test_a_dense_part_at_the_triangle_limit_is_read(tmp_path, dense):
    data = dense[limits.MAX_PART_TRIANGLES]
    assert struct.unpack("<I", data[80:84])[0] == limits.MAX_PART_TRIANGLES
    assert check(tmp_path, data) == ["slice.part_not_watertight"]


def test_a_dense_part_just_over_the_limit_is_refused(tmp_path, dense):
    report = check(tmp_path, dense[limits.MAX_PART_TRIANGLES + 1])
    assert report["code"] == "slice.part_too_detailed"
    assert report["message"] == "Part is too detailed to print here (over 150,000 triangles)."


def read_or_refuse(data):
    """The reader's only allowed outcomes: a mesh, or its own error with a sentence."""
    try:
        mesh = read_binary_stl(data, "Fuzz", source="fuzz.stl")
    except MeshError as exc:
        assert exc.message.endswith(".") and exc.error_code.startswith("slice.part_")
        assert exc.where == {"part": "Fuzz"}
        json.dumps(error_report(exc))
        return None
    assert isinstance(mesh, Mesh) and mesh.health is not None
    return mesh


@FUZZ
@given(st.binary(max_size=2048))
def test_random_bytes(data):
    read_or_refuse(data)


@FUZZ
@given(st.integers(0, 2 ** 32 - 1), st.binary(max_size=600))
def test_random_bytes_behind_a_header(count, body):
    read_or_refuse(b"\0" * 80 + struct.pack("<I", count) + body)


GOOD = box_stl(20, 20, 10)


@FUZZ
@given(st.lists(st.tuples(st.integers(0, len(GOOD) - 1), st.integers(0, 255)), min_size=1, max_size=20))
def test_a_good_file_with_bytes_changed(changes):
    data = bytearray(GOOD)
    for index, value in changes:
        data[index] = value
    read_or_refuse(bytes(data))


@FUZZ
@given(st.integers(0, len(GOOD)), st.binary(max_size=120), st.booleans())
def test_a_good_file_cut_or_padded(at, extra, cut):
    data = GOOD[:at] if cut else GOOD[:at] + extra + GOOD[at:]
    read_or_refuse(data)


@FUZZ
@given(st.lists(st.floats(allow_nan=True, allow_infinity=True, width=32), min_size=9, max_size=9))
def test_any_coordinates_in_one_triangle(values):
    data = bytearray(GOOD)
    data[84 + 12:84 + 48] = struct.pack("<9f", *values)
    read_or_refuse(bytes(data))
