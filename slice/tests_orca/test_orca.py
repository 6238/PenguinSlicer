"""The upstream check: the real Orca Slicer, few and meaningful. Each test pins down one
behaviour of the pinned Orca the slice service relies on, and says which in its first
docstring line ("Protects: ..."). When a new Orca breaks an assumption, the test named
after it fails. `make test-upstream` (also `make test-orca`), one Orca at a time.
"""
import filecmp
import json
import math
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from flatten_orca_profiles import CATALOG_OUT, bbl_profile_dir, build_catalog, library_profile_dir, write_catalog, \
    write_profiles
from helpers import (CONTRACTS, FIXTURES, PLATE_ID, SUBMISSION_ID, USER_KEY, box_stl, l_prism_stl, make_part,
                     part_from_stl, phase_2, pinned_orca_version, sha256, submit, upload)
from measure_plate import SUPPORTS_OFF, SUPPORTS_ON, hub_stl, plate_layout
from penguin_slice.errors import error_report
from penguin_slice.mesh import read_binary_stl
from penguin_slice.plate import instance_hull, instance_matrix
from penguin_slice.plate_3mf import LEFT_OFF_MESSAGE, write_plate_3mf
from penguin_slice.print_config import validate_overrides, write_process_with_overrides
from penguin_slice.slicer import (DEFAULT_PROFILES, ORCA_STAGES, PROFILE_DIR, SAMPLE_STL, SliceCancelled, SliceError,
                                  SliceProfiles, Stop, orca_bin, plate_object_names, slice_plate, slice_stl)

EXAMPLE = CONTRACTS / "examples" / "plate-configuration.json"
EXAMPLE_PARTS = CONTRACTS / "examples" / "parts"
ERROR_EXAMPLE = CONTRACTS / "examples" / "error-report.json"
ERROR_ORCA_SENTENCE_EXAMPLE = CONTRACTS / "examples" / "error-report-orca-sentence.json"
BAD = FIXTURES / "bad_stls"


def gcode_settings(archive):
    with zipfile.ZipFile(archive) as zf:
        gcode = zf.read("Metadata/plate_1.gcode").decode("utf-8", "replace")
    settings = dict(line[2:].split(" = ", 1) for line in gcode.splitlines() if line.startswith("; ") and " = " in line)
    return settings, gcode


def one_instance_plate(work, stl_bytes, name, x=150.0, y=150.0):
    """A plate 3MF with one instance of the part, written past the plate configuration checks."""
    (work / "stls").mkdir(parents=True, exist_ok=True)
    parts = {"a": part_from_stl(work / "stls", name, stl_bytes)}
    write_plate_3mf(work / "plate.3mf", [{"ref": "a", "orientation": "+z", "angle": 0, "x": x, "y": y}], parts)
    return work / "plate.3mf"


def profiles_with(work, supports):
    process = write_process_with_overrides(DEFAULT_PROFILES.process,
                                           validate_overrides(SUPPORTS_ON if supports == "on" else SUPPORTS_OFF),
                                           work / "process.json")
    return SliceProfiles(DEFAULT_PROFILES.printer, DEFAULT_PROFILES.filament, process)


def slice_failure(model, profiles, out):
    with pytest.raises(SliceError) as caught:
        slice_plate(model, profiles, out)
    return caught.value, error_report(caught.value)


def test_installed_orca_runs_and_is_the_pinned_release(tmp_path):
    """Protects: the command-line options the slice service uses exist in this Orca."""
    result = subprocess.run([str(orca_bin()), "--help"], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-2000:]
    for option in ("--export-3mf", "--pipe", "--arrange", "--orient", "--slice", "--datadir", "--load-settings",
                   "--load-filaments", "--outputdir"):
        assert option in result.stdout, option
    stamp = (orca_bin().parent / "VERSION").read_text().split()
    assert stamp[0] == pinned_orca_version()
    assert stamp[1] in {"linux-x86_64", "linux-aarch64", "darwin-arm64"}


def phase_2_example():
    """The contract's example plate configuration in its phase 2 form: its parts named by the
    hashes of their files, in millimetres, with a plate id and a submission, and its overrides
    under Orca's own names (those of the phase 2 example, the same four settings)."""
    data = json.loads(EXAMPLE.read_text())
    for part in data["parts"].values():
        part.update(sha256=sha256((EXAMPLE_PARTS / part.pop("stl")).read_bytes()), units="mm")
    data["overrides"] = json.loads((CONTRACTS / "examples" / "plate-configuration-phase-2.json").read_text())["overrides"]
    return {"plate_id": PLATE_ID, "submission_id": SUBMISSION_ID, **data}


def through_the_http_interface(work, configuration, parts):
    """Upload each part of `parts` (bytes, in millimetres, or a tuple of bytes and units) and
    submit the phase 2 plate configuration through
    the HTTP interface (a test client of the real app, the real Orca), follow the event stream
    to the final report, fetch the sliced file and its summary: (stages, final report, file
    bytes, summary). Nothing of the slice job is left after."""
    from penguin_slice.jobs import FINAL
    from penguin_slice.web import create_app
    app = create_app(work, start_sweeper=False)
    client = app.test_client()
    headers = {"X-Penguin-User-Key": USER_KEY}
    for part in parts:
        data, units = part if isinstance(part, tuple) else (part, "mm")       # (bytes, units) for a part in inches
        assert upload(client, data, units=units).status_code == 201
    answer = submit(client, configuration)
    assert answer.status_code == 202, answer.get_json()
    job_id = answer.get_json()["job"]
    stages = []
    for chunk in client.get(f"/slices/{job_id}/events", headers=headers, buffered=False).response:
        report = json.loads((chunk.decode() if isinstance(chunk, bytes) else chunk).split("data: ", 1)[1])
        stages.append(report.get("stage"))
        if report["state"] in FINAL:
            break
    fetched = client.get(f"/slices/{job_id}/file", headers=headers)
    data = fetched.data if fetched.status_code == 200 else None
    fetched.close()
    summary = client.get(f"/slices/{job_id}/summary", headers=headers).get_json()
    app.extensions["penguin_slice_pool"].shutdown()
    return stages, report, data, summary


@pytest.fixture(scope="module")
def example_slice(tmp_path_factory):
    """The contract's example plate configuration, sliced once through the HTTP interface."""
    out = tmp_path_factory.mktemp("example")
    files = [(EXAMPLE_PARTS / name).read_bytes() for name in ("bracket.stl", "spacer.stl")]
    stages, report, data, summary = through_the_http_interface(out / "work", phase_2_example(), files)
    assert report["state"] == "done", report
    (out / summary["file"]).write_bytes(data)
    return out, summary, stages


def test_the_http_interface_slices_the_contract_example(example_slice):
    """Protects: the whole path with the real Orca (submit, follow, fetch the file and the
    summary), and the metadata read out of the sliced file (time, filament, layers, names)."""
    out, summary, stages = example_slice
    print(f"\n[orca] example summary: {json.dumps(summary)}; stages {stages}")
    assert summary["file"] == "Bracket_plus1-20261009-1432.gcode.3mf"
    assert list((out / "work").iterdir()) == [] or all(p.name.startswith("slice-") for p in (out / "work").iterdir())
    assert sorted(plate_object_names(out / summary["file"])) == ["Bracket #1", "Bracket #2", "Spacer #1"]
    assert summary["instances"] == 3
    assert summary["print_time_s"] > 0 and summary["filament_g"] > 0 and summary["filament_m"] > 0
    assert summary["layer_count"] == 200
    example = json.loads((CONTRACTS / "examples" / "sliced-file.json").read_text())
    assert list(example) == list(summary)
    assert {k: example[k] for k in ("file", "instances", "layer_count", "warnings", "part_warnings")} == \
        {k: summary[k] for k in ("file", "instances", "layer_count", "warnings", "part_warnings")}
    for key in ("print_time_s", "filament_m", "filament_g"):
        assert summary[key] == pytest.approx(example[key], rel=0.05), key


def test_a_rotation_and_a_part_in_inches_slice_where_the_checks_place_them(tmp_path):
    """Protects: the phase 2 plate configuration's two new ways to place a part reach Orca as
    the placement check sees them. The contract's phase 2 example with its fourth bracket laid
    by a `rotation` that is no one of the six orientations (its -x face down, then turned 30
    degrees about the vertical, at `angle` 15) and a fifth instance, a 1 x 1 x 0.5 inch block:
    every instance is sliced, and the first layer Orca prints for the laid bracket and for the
    block is where the slice service's own footprint puts them (within the real parts' 1 mm).

    The example's own rotation lays the bracket on the face of its convex hull across the L's
    open corner, which is no face of the part: the bracket then touches the plate along two
    edges only, and the pinned Orca fails the slice (-100, "floating regions"), with supports
    off and on, so this test uses a face of the part itself."""
    from test_frc_parts import PLACEMENT_TOLERANCE_MM, first_layer_box, first_layer_extrusions
    from penguin_slice.mesh import turned_footprint, orientation_footprints
    from penguin_slice.plate import quaternion_matrix
    example = json.loads((CONTRACTS / "examples" / "plate-configuration-phase-2.json").read_text())
    half, c15, s15 = 0.5 ** 0.5, math.cos(math.radians(15)), math.sin(math.radians(15))
    # qz(30 degrees) times the quaternion of '+x' (half, 0, -half, 0): the '+x' turn, then 30 degrees about z.
    example["instances"][3]["rotation"] = [c15 * half, s15 * half, -c15 * half, s15 * half]
    example["instances"][3]["angle"] = 15
    block = box_stl(1, 1, 0.5)
    example["parts"]["block"] = {"name": "Block", "sha256": sha256(block), "units": "in"}
    example["instances"].append({"ref": "block", "orientation": "+z", "angle": 0, "x": 80.0, "y": 240.0})
    parts = [(EXAMPLE_PARTS / name).read_bytes() for name in ("bracket.stl", "spacer.stl")]
    _stages, report, data, summary = through_the_http_interface(tmp_path / "work", example, parts + [(block, "in")])
    assert report["state"] == "done", report.get("error")
    sliced = tmp_path / summary["file"]
    sliced.write_bytes(data)
    assert sorted(plate_object_names(sliced)) == ["Block #1", "Bracket #1", "Bracket #2", "Bracket #3", "Spacer #1"]
    with zipfile.ZipFile(sliced) as zf:
        gcode = zf.read("Metadata/plate_1.gcode").decode()
    boxes = first_layer_extrusions(gcode)
    laid, inches = example["instances"][3], example["instances"][4]
    bracket = read_binary_stl(parts[0], "Bracket")
    rotation = [v / sum(q * q for q in laid["rotation"]) ** 0.5 for v in laid["rotation"]]
    laid = dict(laid, rotation=rotation)
    block = read_binary_stl(block, "Block", scale=25.4)
    expected = {"Bracket #3": first_layer_box(laid, bracket, turned_footprint(bracket, quaternion_matrix(rotation))),
                "Block #1": first_layer_box(inches, block, orientation_footprints(block)["+z"])}
    errors = {name: max(abs(a - b) for a, b in zip(boxes[name], box)) for name, box in expected.items()}
    print(f"\n[orca] phase 2 example with a block in inches: {json.dumps(summary)}; first-layer errors {errors}")
    assert expected["Block #1"][2] - expected["Block #1"][0] == pytest.approx(25.4, abs=1e-3)
    assert {name: e for name, e in errors.items() if e > PLACEMENT_TOLERANCE_MM} == {}


def test_catalog_profiles_and_overrides_reach_the_gcode(example_slice):
    """Protects: the profile fields the catalog and the overrides depend on reach Orca."""
    out, summary, _stages = example_slice
    settings, gcode = gcode_settings(out / summary["file"])
    assert f"; generated by OrcaSlicer {pinned_orca_version()} on " in gcode.split("\n", 3)[1]
    assert settings["nozzle_diameter"] == "0.4"
    assert settings["layer_height"] == "0.2"
    assert settings["filament_settings_id"] == '"Bambu PLA Basic @BBL H2S"'
    assert settings["sparse_infill_density"] == "20%"
    assert settings["wall_loops"] == "3"
    assert settings["enable_support"] == "0"
    assert settings["brim_type"] == "auto_brim"


def test_default_set_resolves_the_high_flow_nozzle_and_textured_plate(tmp_path):
    """Protects: the variant selection (nozzle_volume_type, curr_bed_type) reaches Orca."""
    result = slice_stl(SAMPLE_STL, tmp_path / "out")
    assert result.layer_count == 50
    settings, gcode = gcode_settings(result.output_path)
    with zipfile.ZipFile(result.output_path) as zf:
        plate = json.loads(zf.read("Metadata/plate_1.json").decode("utf-8"))
    assert settings["nozzle_volume_type"] == "High Flow"
    for key in ("printer_extruder_variant", "filament_extruder_variant", "print_extruder_variant"):
        assert settings[key] == '"Direct Drive High Flow"', key
    assert settings["nozzle_volume"] == "148"
    assert settings["nozzle_flush_dataset"] == "2"
    assert settings["nozzle_diameter"] == "0.6"
    assert settings["filament_type"] == "PETG"
    assert settings["curr_bed_type"] == "Textured PEI Plate"
    assert plate["bed_type"] == "textured_plate"
    assert "M190 S70" in gcode


@pytest.fixture
def stls(tmp_path):
    path = tmp_path / "stls"
    path.mkdir()
    return path


def test_rotated_instance_lands_where_the_placement_check_sees_it(tmp_path, stls):
    """Protects: placements and orientations in the plate file are kept (--arrange 0 --orient 0)."""
    process = json.loads((PROFILE_DIR / "process.json").read_text())
    process["brim_type"] = "no_brim"
    (tmp_path / "process.json").write_text(json.dumps(process, indent=4))
    profiles = SliceProfiles(PROFILE_DIR / "printer.json", PROFILE_DIR / "filament.json", tmp_path / "process.json")
    parts = {"a": make_part(stls, "Bar", (40, 10, 10))}
    instance = {"ref": "a", "orientation": "+z", "angle": 30, "x": 150.0, "y": 150.0}
    write_plate_3mf(tmp_path / "plate.3mf", [instance], parts)
    result = slice_plate(tmp_path / "plate.3mf", profiles, tmp_path / "out")
    with zipfile.ZipFile(result.output_path) as zf:
        bbox = json.loads(zf.read("Metadata/plate_1.json").decode("utf-8"))["bbox_objects"][0]["bbox"]
    hull = instance_hull(instance, parts["a"]["footprints"]["+z"])
    expected = [min(p[0] for p in hull), min(p[1] for p in hull), max(p[0] for p in hull), max(p[1] for p in hull)]
    assert bbox == pytest.approx(expected, abs=0.5)


# Three parts whose footprints tell every orientation and turn apart (an uncentred bar, the
# sheared L, a slab), interleaved, so the plate file's objects (grouped by part) and its
# build items (in instance order) are in different orders.
INTERLEAVED_ORDER = ["ell", "bar", "ell", "slab", "bar", "ell", "slab", "ell", "bar"]
INTERLEAVED_TURNS = [("+z", 0), ("+x", 30), ("+z", 275), ("+y", 90), ("-z", 45), ("+z", 37), ("+z", 200), ("-z", 10),
                     ("+x", 0)]
# Orca's bbox of an object is its first layer's; the bed-touching vertices give it to within
# 0.06 mm. A wrongly paired object is off by many millimetres.
INTERLEAVED_TOLERANCE_MM = 0.25


def test_interleaved_parts_each_land_where_their_own_instance_is_placed(tmp_path, stls):
    """Protects: Orca pairs each build item with its object by objectid, not by position, so
    every instance of an interleaved plate of several parts keeps its position, orientation
    and name (the objects are written grouped by part, the build items in instance order)."""
    process = json.loads((PROFILE_DIR / "process.json").read_text())
    process["brim_type"] = "no_brim"
    (tmp_path / "process.json").write_text(json.dumps(process, indent=4))
    profiles = SliceProfiles(PROFILE_DIR / "printer.json", PROFILE_DIR / "filament.json", tmp_path / "process.json")
    stl_bytes = {"bar": box_stl(40, 10, 6, origin=(5.0, -3.0, 2.0)), "ell": l_prism_stl(origin=(7.0, -4.0, 3.0)),
                 "slab": box_stl(24, 16, 4)}
    parts = {ref: part_from_stl(stls, name, stl_bytes[ref]) for ref, name in
             (("bar", "Bar"), ("ell", "Ell"), ("slab", "Slab"))}
    instances = [{"ref": ref, "orientation": o, "angle": a, "x": 60.0 + 70 * (n % 3) + 3 * n,
                  "y": 60.0 + 80 * (n // 3) - 2 * n}
                 for n, (ref, (o, a)) in enumerate(zip(INTERLEAVED_ORDER, INTERLEAVED_TURNS))]
    names = write_plate_3mf(tmp_path / "plate.3mf", instances, parts)
    result = slice_plate(tmp_path / "plate.3mf", profiles, tmp_path / "out")
    with zipfile.ZipFile(result.output_path) as zf:
        found = {o["name"]: o["bbox"] for o in json.loads(zf.read("Metadata/plate_1.json").decode())["bbox_objects"]}
    assert sorted(found) == sorted(names)
    offsets = {}
    for name, placed in zip(names, instances):
        footprint = parts[placed["ref"]]["footprints"][placed["orientation"]]
        m = instance_matrix(placed["orientation"], placed["angle"], footprint["offset"], placed["x"], placed["y"])
        points = [[sum(m[i][k] * v[k] for k in range(3)) + m[i][3] for i in range(3)]
                  for v in read_binary_stl(stl_bytes[placed["ref"]], name).vertices.tolist()]
        floor = min(p[2] for p in points)
        low = [p for p in points if p[2] < floor + 0.05]
        expected = [min(p[0] for p in low), min(p[1] for p in low), max(p[0] for p in low), max(p[1] for p in low)]
        offsets[name] = max(abs(a - b) for a, b in zip(found[name], expected))
    print(f"\n[orca] interleaved plate: worst bbox error {max(offsets.values()):.3f} mm over {len(names)} instances")
    assert {name: off for name, off in offsets.items() if off > INTERLEAVED_TOLERANCE_MM} == {}


def test_overlapping_instances_are_refused_by_orca(tmp_path, stls):
    """Protects: return code -101, its error_string, and the debug log's line naming the pair
    (slicer.LOG_CONFLICT_RE)."""
    parts = {"a": make_part(stls, "Box", (20, 20, 10))}
    instances = [{"ref": "a", "orientation": "+z", "angle": 0, "x": 100.0, "y": 100.0},
              {"ref": "a", "orientation": "+z", "angle": 0, "x": 110.0, "y": 100.0}]
    write_plate_3mf(tmp_path / "plate.3mf", instances, parts)
    exc, report = slice_failure(tmp_path / "plate.3mf", DEFAULT_PROFILES, tmp_path / "out")
    assert exc.code == -101 and report["code"] == "slice.orca_too_close"
    assert report["where"] == {"instance": "Box #1", "other_instance": "Box #2", "stage": "slicing"}
    assert report["message"] == ("Box #1 and Box #2 are too close together: the slicer found that their paths would "
                                 "meet.")
    assert report["detail"].splitlines()[:4] == [
        "orca code -101", "exit code 155", "orca debug log: paths meet between Box #1 and Box #2",
        "orca error_string: G-code conflicts detected after slicing. Please make "
        "sure the 3mf file can be successfully sliced in the latest Orca Slicer. If the file slices normally in Orca "
        "Slicer, try moving the wipe tower further from other models, as we use more conservative parameters for "
        "it during upload."]
    import fake_orca                                   # the fast suite's stand-in writes the same line
    logged = (tmp_path / "out" / "orca.log").read_text(errors="replace").splitlines()
    assert {fake_orca.CONFLICT.format("Box #2", "Box #1"), fake_orca.CONFLICT.format("Box #1", "Box #2")} & set(logged)


def test_the_only_instance_across_the_edge_gives_minus_50(tmp_path):
    """Protects: return code -50 (no part fully on the plate) and its error_string."""
    model = one_instance_plate(tmp_path, box_stl(40, 40, 10), "Edge", x=5.0, y=150.0)
    exc, report = slice_failure(model, DEFAULT_PROFILES, tmp_path / "out")
    print(f"\n[orca] the only instance across the edge: {json.dumps(report)}")
    assert (exc.code, report["code"]) == (-50, "slice.nothing_on_plate")
    assert "orca error_string: One of the plate is empty or has no object fully inside it." in report["detail"]


def test_one_instance_of_two_across_the_edge(tmp_path, stls):
    """Protects: what Orca does with one instance partly off the plate beside one fully on it."""
    parts = {"a": make_part(stls, "Edge", (40, 40, 10))}
    instances = [{"ref": "a", "orientation": "+z", "angle": 0, "x": 150.0, "y": 150.0},
              {"ref": "a", "orientation": "+z", "angle": 0, "x": 5.0, "y": 150.0}]
    write_plate_3mf(tmp_path / "plate.3mf", instances, parts)
    exc, report = slice_failure(tmp_path / "plate.3mf", DEFAULT_PROFILES, tmp_path / "out")
    print(f"\n[orca] one of two across the edge: {json.dumps(report)}")
    assert (exc.code, report["code"]) == (-52, "slice.crosses_edge")


@pytest.fixture(scope="module")
def empty_layers(tmp_path_factory):
    """The corpus' stand-in for the not-watertight tower, sliced with supports off and on."""
    reports = {}
    for supports in ("off", "on"):
        work = tmp_path_factory.mktemp(f"lattice-{supports}")
        model = one_instance_plate(work, (BAD / "slivers_and_lattice.stl").read_bytes(), "Tower")
        exc, report = slice_failure(model, profiles_with(work, supports), work / "out")
        print(f"\n[orca] slivers and lattice, supports {supports}: {json.dumps(report)}")
        reports[supports] = (exc, report)
    return reports


def test_empty_layers_with_supports_off(empty_layers):
    """Protects: return code -100 and the empty-layer warning_message in result.json
    (its wording, the heights and the "Object:" line), read before cleanup."""
    exc, report = empty_layers["off"]
    assert exc.code == -100
    assert report["code"] == "slice.empty_layers"
    assert report["message"] == ("Tower #1 has nothing to print between 9.9 and 11.34 mm high, so the layers above "
                                 "would start in mid-air.")
    assert report["where"] == {"instance": "Tower #1", "height_mm": 9.9, "stage": "slicing"}
    assert report["action"] == "enable_supports"
    lines = report["detail"].splitlines()
    assert lines[:3] == ["orca code -100", "exit code 156", "orca error_string: Failed slicing the model. Please "
                         "verify the slicing of all plates on Orca Slicer before uploading."]
    assert lines[3] == "orca warning_message: Object can't be printed for empty layer between 9.9 and 11.34."
    # contracts/examples/error-report.json is this report as built before phase 2, without
    # Orca's own sentence; error-report-orca-sentence.json is this report whole.
    example = json.loads(ERROR_EXAMPLE.read_text())
    assert {k: v for k, v in report.items() if k not in ("detail", "orca_sentence")} == \
        {k: v for k, v in example.items() if k != "detail"}
    assert lines[:6] == example["detail"].splitlines()[:6]
    with_sentence = json.loads(ERROR_ORCA_SENTENCE_EXAMPLE.read_text())
    assert {k: v for k, v in report.items() if k != "detail"} == \
        {k: v for k, v in with_sentence.items() if k != "detail"}


def test_orcas_empty_layer_sentence_is_pinned(empty_layers):
    """Protects: the wording of Orca's own sentence about a gap, which the error reports of
    the two failures about a gap quote to the user as orca_sentence (item 13)."""
    for supports, high in (("off", "11.34"), ("on", "10.62")):
        _exc, report = empty_layers[supports]
        assert report["orca_sentence"] == f"Object can't be printed for empty layer between 9.9 and {high}.", supports


def test_empty_layers_with_supports_on_ask_for_a_repair(empty_layers):
    """Protects: the same refusal with supports on, so the action must not be supports."""
    _exc, report = empty_layers["on"]
    assert report["code"] == "slice.empty_layers_with_supports"
    assert "action" not in report and report["where"]["instance"] == "Tower #1"


def test_a_warning_after_a_good_slice(tmp_path):
    """Protects: the shape of result.json after a good slice with a warning (sliced_plates)."""
    model = one_instance_plate(tmp_path, (BAD / "self_intersecting.stl").read_bytes(), "Cross")
    result = slice_plate(model, DEFAULT_PROFILES, tmp_path / "out")
    assert result.warnings == ["It seems object Cross #1 has floating cantilever. Please re-orient the object or "
                               "enable support generation."]


@pytest.mark.parametrize("name", ["open_box.stl", "inverted_normals.stl", "two_shells.stl", "inch_file.stl"])
def test_parts_the_checks_only_warn_about_slice(tmp_path, name):
    """Protects: the decision to warn, not refuse: the pinned Orca slices these parts."""
    model = one_instance_plate(tmp_path, (BAD / name).read_bytes(), "Part")
    assert slice_plate(model, DEFAULT_PROFILES, tmp_path / "out").layer_count > 0


def test_progress_messages_are_the_ones_the_stage_table_knows(tmp_path):
    """Protects: what Orca sends through --pipe while slicing: JSON lines with message and
    total_percent, each message one ORCA_STAGES knows, the percent rising; and that the
    slice service's own "slicing" stage comes first."""
    (tmp_path / "hub.stl").write_bytes(hub_stl(20_000))
    instances, parts = plate_layout(tmp_path / "hub.stl", 6)
    write_plate_3mf(tmp_path / "plate.3mf", instances, parts)
    seen = []
    slice_plate(tmp_path / "plate.3mf", DEFAULT_PROFILES, tmp_path / "out",
                on_progress=lambda *args: seen.append(args))
    print(f"\n[orca] progress: {seen}")
    assert seen[0] == ("slicing", None, "Slicing the plate")             # the service's own, before Orca's
    seen = seen[1:]
    messages = [message for _stage, _fraction, message in seen]
    assert set(messages) <= set(ORCA_STAGES), set(messages) - set(ORCA_STAGES)
    assert {"Generating G-code", "All done, Success"} <= set(messages)
    fractions = [f for _s, f, m in seen if f is not None and m not in ("Generate thumbnails",)]
    assert fractions[-1] == 1.0 and all(0 <= f <= 1 for f in fractions)
    assert fractions == sorted(fractions), fractions                     # the percent rises


def test_the_fake_orca_sends_what_the_real_one_sends(tmp_path, monkeypatch):
    """Protects: tests/fake_orca.py from drifting: its progress lines carry the real keys."""
    import fake_orca
    from penguin_slice import slicer
    raw, real = [], slicer._progress_line

    def keep(line, on_progress):
        raw.append(json.loads(line))
        real(line, on_progress)
    monkeypatch.setattr(slicer, "_progress_line", keep)
    slice_stl(SAMPLE_STL, tmp_path / "out")
    pipe = fake_orca.Pipe(["--pipe", str(tmp_path / "fake.jsonl")])
    pipe.send("Slicing mesh", 7)
    pipe.fh.close()
    fake_keys = set(json.loads((tmp_path / "fake.jsonl").read_text()))
    assert raw and all(set(message) == fake_keys for message in raw)
    assert {m for m, _p in fake_orca.PROGRESS} <= set(ORCA_STAGES)


@pytest.fixture
def heavy_plate(tmp_path):
    (tmp_path / "hub.stl").write_bytes(hub_stl(20_000))
    instances, parts = plate_layout(tmp_path / "hub.stl", 6)
    write_plate_3mf(tmp_path / "plate.3mf", instances, parts)
    return tmp_path / "plate.3mf"


def orca_processes_in(directory):
    """The processes whose working folder is `directory`. A process that exits while the
    table is read is skipped: any error reading its entry means it is gone."""
    found, wanted = [], os.path.realpath(directory)
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            if os.readlink(f"/proc/{name}/cwd") == wanted:
                found.append(int(name))
        except OSError:
            continue
    return found


def test_cancel_stops_the_real_orca(tmp_path, heavy_plate):
    """Protects: Orca stops on SIGTERM to its process group and leaves no process behind."""
    stop = Stop()
    out = tmp_path / "out"
    with pytest.raises(SliceCancelled) as caught:
        slice_plate(heavy_plate, DEFAULT_PROFILES, out, stop=stop,
                    on_progress=lambda stage, fraction, message: stage == "generating_walls" and stop.set())
    print(f"\n[orca] cancel: {caught.value.details}")
    assert orca_processes_in(out) == []


def test_timeout_stops_the_real_orca(tmp_path, heavy_plate):
    """Protects: the timeout path with a real Orca (a 0.5 s limit on a 2 s plate)."""
    out = tmp_path / "out"
    exc, report = slice_failure_timeout(heavy_plate, out)
    assert report["code"] == "slice.timeout"
    assert orca_processes_in(out) == []


def freeze_and_stop(out, wanted, stop, reason, monkeypatch):
    """on_progress: at Orca's message `wanted`, freeze Orca (SIGSTOP, so it can neither go on
    nor exit by itself), then ask the stop. A frozen process takes no SIGTERM, so the
    group is sent SIGCONT just after the stop's SIGTERM: the pending SIGTERM ends Orca
    before it runs on."""
    import signal

    from penguin_slice import slicer
    real_signal = slicer._signal_group

    def signal_group(pgid, sig):
        real_signal(pgid, sig)
        if sig == signal.SIGTERM:
            real_signal(pgid, signal.SIGCONT)
    monkeypatch.setattr(slicer, "_signal_group", signal_group)

    def on_progress(stage, fraction, message):
        if message == wanted:
            for pid in orca_processes_in(out):
                os.kill(pid, signal.SIGSTOP)
            stop.set(reason)
    return on_progress


@pytest.mark.parametrize("reason", ["timeout", "memory"])
def test_a_stop_after_orca_wrote_its_sliced_file_delivers_it(tmp_path, heavy_plate, reason, monkeypatch):
    """Protects: the pinned Orca has written its sliced file, complete and under its final
    name, when it says "All done, Success", and has not yet exited. A timeout or a watchdog
    stop that lands there delivers the file, with the stop recorded (stop_note)."""
    stop, out = Stop(), tmp_path / "out"
    result = slice_plate(heavy_plate, DEFAULT_PROFILES, out, stop=stop,
                         on_progress=freeze_and_stop(out, "All done, Success", stop, reason, monkeypatch))
    print(f"\n[orca] {reason} at All done, Success: {result.stop_note}")
    assert result.stop_note.startswith(f"stopped by the slice service ({reason}) with SIGTERM after ")
    assert result.layer_count > 0 and len(plate_object_names(result.output_path)) == 6
    assert orca_processes_in(out) == []


def test_a_stop_while_orca_writes_its_sliced_file_is_the_stop(tmp_path, heavy_plate, monkeypatch):
    """Protects: while the pinned Orca writes its sliced file ("Exporting 3mf") the file is
    not yet under its final name, so a timeout there fails as slice.timeout, never with a
    half-written file delivered."""
    stop, out = Stop(), tmp_path / "out"
    with pytest.raises(SliceError) as caught:
        slice_plate(heavy_plate, DEFAULT_PROFILES, out, stop=stop,
                    on_progress=freeze_and_stop(out, "Exporting 3mf", stop, "timeout", monkeypatch))
    report = error_report(caught.value)
    print(f"\n[orca] timeout at Exporting 3mf: {report['detail'].splitlines()[1]}")
    assert report["code"] == "slice.timeout" and "(timeout) with SIGTERM after " in report["detail"]
    assert not (out / "plate.gcode.3mf").exists()
    assert orca_processes_in(out) == []


def test_an_outside_kill_just_before_a_timeout_is_reported_as_the_kill(tmp_path, heavy_plate):
    """Protects: the signal a real Orca ends on. Someone else's SIGKILL, then a timeout asked
    at once: the slice is reported slice.orca_killed (or slice.out_of_memory if the kernel's
    count moved), never slice.timeout."""
    import signal
    stop, out = Stop(), tmp_path / "out"

    def on_progress(stage, fraction, message):
        if stage == "generating_walls":
            for pid in orca_processes_in(out):
                os.kill(pid, signal.SIGKILL)
            stop.set("timeout")
    with pytest.raises(SliceError) as caught:
        slice_plate(heavy_plate, DEFAULT_PROFILES, out, stop=stop, on_progress=on_progress)
    report = error_report(caught.value)
    print(f"\n[orca] outside SIGKILL then a timeout: {report['code']}: {report['detail'].splitlines()[:2]}")
    assert report["code"] in ("slice.orca_killed", "slice.out_of_memory")
    assert "asked it to stop (timeout)" in report["detail"]
    assert orca_processes_in(out) == []


def slice_failure_timeout(model, out):
    with pytest.raises(SliceError) as caught:
        slice_plate(model, DEFAULT_PROFILES, out, timeout_s=0.5)
    return caught.value, error_report(caught.value)


def test_out_of_memory_under_an_address_space_limit(tmp_path, heavy_plate, monkeypatch):
    """Protects: what Orca does when memory runs out. Under RLIMIT_AS of 1 GB it prints
    std::bad_alloc and returns -100; the service reports slice.out_of_memory."""
    wrapper = tmp_path / "orca-limited"
    wrapper.write_text(f'#!/usr/bin/env bash\nulimit -v 1000000\nexec "{orca_bin()}" "$@"\n')
    wrapper.chmod(0o755)
    monkeypatch.setenv("PENGUIN_SLICE_ORCA", str(wrapper))
    exc, report = slice_failure(heavy_plate, DEFAULT_PROFILES, tmp_path / "out")
    print(f"\n[orca] under RLIMIT_AS 1 GB: {json.dumps(report)}")
    assert report["code"] == "slice.out_of_memory"
    assert "bad_alloc" in report["detail"]


def test_the_memory_watchdog_stops_a_real_orca_at_the_ceiling(tmp_path, heavy_plate):
    """Protects: the memory watchdog's reading of a real Orca's process group. With a
    ceiling of 100 MB (a real slice of this plate passes 200 MB) the slice is stopped and
    reported out of memory with the measured peak, and no Orca is left."""
    out = tmp_path / "out"
    with pytest.raises(SliceError) as caught:
        slice_plate(heavy_plate, DEFAULT_PROFILES, out, memory_ceiling_mb=100)
    report = error_report(caught.value)
    print(f"\n[orca] memory watchdog at 100 MB: {json.dumps(report)}")
    assert report["code"] == "slice.out_of_memory"
    assert report["message"] == ("This plate is too large to slice: the slicer needed more than the 100 MB of "
                                 "memory the print server allows.")
    assert report["detail"].startswith("stopped by the slice service (memory) with SIGTERM")
    assert "over the ceiling of 102,400 kB" in report["detail"]
    assert orca_processes_in(out) == []


def test_the_watchdog_sees_a_real_orcas_peak_through_its_high_water_mark(tmp_path, heavy_plate):
    """Protects: the kernel's VmHWM of the pinned Orca, which the watchdog reads (Orca's
    resident memory peaks in spikes shorter than the watchdog's cadence, so reading the
    current figure missed them). A first slice measures the plate's peak; a second at a
    ceiling 5 % under it is either stopped at the ceiling or, if Orca finished between two
    samples, delivered with the note that its peak passed the ceiling: never delivered
    silently. The peak reported is the watchdog's reading of Orca alone; with the sample that
    follows "All done, Success" it reaches the kernel's ru_maxrss of Orca (which, from a
    test process smaller than Orca's peak, is Orca's own)."""
    from penguin_slice import slicer
    runs, real = [], slicer.run_process

    def keep(*args, **kwargs):
        runs.append(real(*args, **kwargs))
        return runs[-1]
    slicer.run_process = keep
    try:
        first = slice_plate(heavy_plate, DEFAULT_PROFILES, tmp_path / "first")
    finally:
        slicer.run_process = real
    peak_kb = first.peak_rss_kb
    print(f"\n[orca] watchdog {runs[0].memory_peak_kb:,} kB, ru_maxrss {runs[0].peak_rss_kb:,} kB")
    assert peak_kb == runs[0].memory_peak_kb >= 0.98 * runs[0].peak_rss_kb
    ceiling_mb = int(peak_kb * 0.95) // 1024
    print(f"\n[orca] heavy plate peak {peak_kb:,} kB; second slice at {ceiling_mb} MB")
    try:
        second = slice_plate(heavy_plate, DEFAULT_PROFILES, tmp_path / "second", memory_ceiling_mb=ceiling_mb)
    except SliceError as exc:
        report = error_report(exc)
        print(f"[orca] stopped: {report['detail'].splitlines()[0]}")
        assert report["code"] == "slice.out_of_memory"
        assert exc.peak_rss_kb > ceiling_mb * 1024
        match = re.search(r"a peak of ([\d,]+) kB \(the watchdog's high-water reading of Orca's processes\)",
                          report["detail"])
        assert int(match.group(1).replace(",", "")) == exc.peak_rss_kb
    else:
        print(f"[orca] delivered: {second.memory_note}")
        assert second.peak_rss_kb > ceiling_mb * 1024
        assert second.memory_note and "the sliced file is delivered" in second.memory_note
    assert orca_processes_in(tmp_path / "second") == []


@pytest.mark.parametrize("name, stl, code, words", [
    ("half_box", box_stl()[:80] + (6).to_bytes(4, "little") + box_stl()[84:84 + 300], "slice.no_layers",
     "No layers were detected. You might want to repair your STL file(s) or check their size or thickness and "
     "retry."),
    ("tiny_cube", box_stl(0.15, 0.15, 0.15), "slice.print_empty",
     "The print is empty. The model is not printable with current print settings."),
])
def test_orcas_words_for_a_plate_with_nothing_to_slice(tmp_path, name, stl, code, words):
    """Protects: the two lines Orca prints on stdout, with return code -100 and only the
    general error_string, for a part with no layers and for an empty print
    (ORCA_OUTPUT_REASONS); each becomes its own error report."""
    model = one_instance_plate(tmp_path, stl, "Part")
    exc, report = slice_failure(model, DEFAULT_PROFILES, tmp_path / "out")
    print(f"\n[orca] {name}: {json.dumps(report)}")
    assert (exc.code, report["code"]) == (-100, code)
    assert exc.reason.splitlines()[0] == words
    assert f"orca said: {words}" in report["detail"]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the Linux loader")
def test_an_orca_that_cannot_load_its_libraries_is_unstartable(tmp_path, monkeypatch):
    """Protects: Orca's binary started without its library path (as after a host library
    went missing) exits 127 with the loader's words and no result.json; the report says the
    slicer could not start, not that the plate is at fault."""
    binary = orca_bin().parent / "squashfs-root" / "bin" / "orca-slicer"
    wrapper = tmp_path / "orca-without-libraries"
    wrapper.write_text(f'#!/bin/sh\nexec "{binary}" "$@"\n')
    wrapper.chmod(0o755)
    monkeypatch.setenv("PENGUIN_SLICE_ORCA", str(wrapper))
    exc, report = slice_failure(one_instance_plate(tmp_path, box_stl(), "Box"), DEFAULT_PROFILES, tmp_path / "out")
    print(f"\n[orca] without its libraries: {json.dumps(report)}")
    assert report["code"] == "slice.orca_unstartable"
    assert report["detail"].startswith("exit code 127: Orca did not start")
    assert "error while loading shared libraries" in report["detail"]


def block_on_a_stem_stl():
    """A 20 x 20 x 5 mm block on a stem 0.4 mm across and 30 mm tall, too thin for the
    nozzle: the pinned Orca fails it with only its general error_string (its own reason,
    "One object has an empty first layer", is thrown, collected and lost), and its debug log
    holds the warning it reported while slicing: floating regions."""
    import numpy as np
    from penguin_slice.mesh import read_binary_stl
    from helpers import mesh_stl
    stem, block = (read_binary_stl(box_stl(*size, origin=origin), "x") for size, origin in
                   (((0.4, 0.4, 30.5), (9.8, 9.8, 0.0)), ((20, 20, 5), (0.0, 0.0, 30.0))))
    return mesh_stl(np.vstack([stem.vertices, block.vertices]),
                    np.vstack([stem.faces, block.faces + len(stem.vertices)]))


def test_orcas_reason_for_a_general_failure_is_read_from_its_debug_log(tmp_path):
    """Protects: the format of the pinned Orca's debug log (slicer.LOG_WARNING_RE, read by
    slicer.orca_log_warnings at --debug 3): a part that fails with only "The slicer could not
    slice this plate" gets the warning Orca logged. If this fails after an upgrade, look at
    the new Orca's orca.log for the plate (printed below) and fix LOG_WARNING_RE and
    tests/fake_orca.py's LOG_WARNING together."""
    import fake_orca
    from penguin_slice import slicer
    model = one_instance_plate(tmp_path, block_on_a_stem_stl(), "Block")
    out = tmp_path / "out"
    exc, report = slice_failure(model, DEFAULT_PROFILES, out)
    print(f"\n[orca] block on a stem: {json.dumps(report)}")
    assert (exc.code, report["code"]) == (-100, "slice.orca_failed")
    warning = "It seems object Block #1 has floating regions. Please re-orient the object or enable support generation."
    assert report["message"] == ("The slicer could not slice this plate. It also warned, though this may not be why "
                                 f"it failed: {warning}"), \
        "the debug log's format changed: fix slicer.LOG_WARNING_RE and tests/fake_orca.py's LOG_WARNING"
    assert f"orca debug log warning: {warning}" in report["detail"]
    assert slicer.LOG_WARNING_RE.search(fake_orca.LOG_WARNING.format(name="Block #1"))     # the stand-in's line


def mushroom_stl():
    """A 20 x 20 x 5 mm cap on a stem 3 mm across and 30 mm tall: it slices alone, and the
    pinned Orca warns of a floating cantilever while doing so."""
    import numpy as np
    from penguin_slice.mesh import read_binary_stl
    from helpers import mesh_stl
    stem, cap = (read_binary_stl(box_stl(*size, origin=origin), "x") for size, origin in
                 (((3, 3, 30.5), (8.5, 8.5, 0.0)), ((20, 20, 5), (0.0, 0.0, 30.0))))
    return mesh_stl(np.vstack([stem.vertices, cap.vertices]), np.vstack([stem.faces, cap.faces + len(stem.vertices)]))


def test_a_sound_parts_warning_is_not_given_as_the_reason_another_part_failed(tmp_path):
    """Protects: the debug log names no culprit. A mushroom that slices alone (with a
    "floating cantilever" warning) beside a needle 0.3 mm across and 300 mm tall, which fails
    with no reason in any file: the sentence keeps the general failure first and gives the
    mushroom's warning only as one that may be unrelated."""
    from penguin_slice import slicer
    (tmp_path / "stls").mkdir()
    parts = {"m": part_from_stl(tmp_path / "stls", "Mushroom", mushroom_stl()),
             "n": part_from_stl(tmp_path / "stls", "Needle", box_stl(0.3, 0.3, 300))}
    write_plate_3mf(tmp_path / "plate.3mf", [{"ref": "m", "orientation": "+z", "angle": 0, "x": 100.0, "y": 150.0},
                                             {"ref": "n", "orientation": "+z", "angle": 0, "x": 220.0, "y": 150.0}],
                    parts)
    exc, report = slice_failure(tmp_path / "plate.3mf", DEFAULT_PROFILES, tmp_path / "out")
    print(f"\n[orca] mushroom beside a needle: {json.dumps(report)}")
    assert (exc.code, report["code"]) == (-100, "slice.orca_failed")
    warning = ("It seems object Mushroom #1 has floating cantilever. Please re-orient the object or enable support "
               "generation.")
    assert report["message"] == slicer.SLICE_FAILED_WARNED_MESSAGE.format(warnings=warning) == (
        f"The slicer could not slice this plate. It also warned, though this may not be why it failed: {warning}")
    assert "Needle" not in report["message"]                     # the needle's reason reaches no file


def test_the_reference_plate_of_100_spacers(tmp_path):
    """Protects: the measurement behind MAX_INSTANCES (slice/README-details.md, "Plate limits"). 100
    hex shaft spacers in a 10 by 10 grid, through the HTTP interface: delivered with every
    instance, under the default memory ceiling, its peak, time and size printed."""
    import time
    from helpers import spacer_grid, spacer_stl
    configuration = phase_2({"spacer": ("Spacer", spacer_stl())}, spacer_grid(100))
    started = time.monotonic()
    _stages, report, data, summary = through_the_http_interface(tmp_path / "work", configuration, [spacer_stl()])
    seconds = time.monotonic() - started
    assert report["state"] == "done", report
    (tmp_path / summary["file"]).write_bytes(data)
    names = plate_object_names(tmp_path / summary["file"])
    print(f"\n[orca] 100 spacers: {seconds:.1f} s, {len(data):,} bytes, {summary['layer_count']} layers")
    assert len(names) == 100 and summary["instances"] == 100 and summary["layer_count"] > 0
    assert seconds < 60


def test_the_peak_of_the_reference_plate(tmp_path):
    """Protects: the peak memory of the 100-spacer plate, the watchdog's reading of Orca
    alone, under the default ceiling with room to spare (measured 488 to 513 MB)."""
    from helpers import part_from_stl, spacer_grid, spacer_stl
    (tmp_path / "stls").mkdir()
    write_plate_3mf(tmp_path / "plate.3mf", spacer_grid(100), {"spacer": part_from_stl(tmp_path / "stls", "Spacer",
                                                                                        spacer_stl())})
    result = slice_plate(tmp_path / "plate.3mf", DEFAULT_PROFILES, tmp_path / "out")
    print(f"\n[orca] 100 spacers: peak {result.peak_rss_kb:,} kB, Orca {result.wall_s} s, "
          f"{result.output_path.stat().st_size:,} bytes")
    assert 100 * 1024 < result.peak_rss_kb < 800 * 1024 and result.memory_note is None


def test_instance_entirely_off_the_plate_is_caught_by_the_name_guard(tmp_path, stls):
    """Protects: Orca leaves a instance entirely off the plate out without an error."""
    from penguin_slice.plate_3mf import check_plate_names
    parts = {"a": make_part(stls, "Box", (20, 20, 10))}
    instances = [{"ref": "a", "orientation": "+z", "angle": 0, "x": 100.0, "y": 100.0},
              {"ref": "a", "orientation": "+z", "angle": 0, "x": 600.0, "y": 100.0}]
    names = write_plate_3mf(tmp_path / "plate.3mf", instances, parts)
    result = slice_plate(tmp_path / "plate.3mf", DEFAULT_PROFILES, tmp_path / "out")
    with pytest.raises(SliceError) as caught:
        check_plate_names(names, plate_object_names(result.output_path))
    assert caught.value.message == LEFT_OFF_MESSAGE
    assert "missing ['Box #2']" in caught.value.details


def test_checked_in_profiles_and_catalog_match_the_installed_orca(tmp_path):
    """Protects: the profile catalog built from Orca's own profiles (regenerate after an upgrade)."""
    write_profiles(bbl_profile_dir(), tmp_path / "profiles")
    for name in ("printer.json", "filament.json", "process.json"):
        assert filecmp.cmp(tmp_path / "profiles" / name, PROFILE_DIR / name, shallow=False), name
    catalog = build_catalog(bbl_profile_dir(), library_profile_dir())
    write_catalog(catalog, tmp_path / "catalog")
    built = sorted(p.relative_to(tmp_path / "catalog").as_posix() for p in (tmp_path / "catalog").rglob("*.json"))
    committed = sorted(p.relative_to(CATALOG_OUT).as_posix() for p in CATALOG_OUT.rglob("*.json"))
    assert built == committed
    for rel in built:
        assert filecmp.cmp(tmp_path / "catalog" / rel, CATALOG_OUT / rel, shallow=False), rel
    assert catalog["index"]["skipped"]
