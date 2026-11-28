"""The real parts of the Popcorn Penguins' (FRC Team 6238) robot with the real Orca
(tests/fixtures/frc-parts/, plates in tests/frc_parts.py): each part alone, the mixed plate
of all eight, a plate a team would print, and the mechanical mentor's target of 4 instances
of every part on two plates, with supports off and on. Each through the HTTP interface at
the default profiles, and each must come back as a valid sliced file with every instance
where it was placed, a print time and filament within BAND of what was measured, and only
the warnings that are true. Orca's G-code is not the same bytes from one slice of a plate
to the next (slice/README-details.md, "The same plate, sliced again"), so what is pinned is what is
stable: the summary, the warnings and the placements, on every run of this suite.

Protects: the slice service's whole path on real, printed parts with the pinned Orca. A
new Orca that slices them differently fails here first (`make upgrade-orca` runs this).
"""
import json
import math
import re
import zipfile

import numpy as np
import pytest

import frc_parts
from helpers import Parts
from penguin_slice import plate as plate_module
from penguin_slice.errors import error_report
from penguin_slice.mesh import orientation_footprints, read_binary_stl
from penguin_slice.plate import SPACING_MM, SPACING_SUPPORTS_MM, instance_labels, instance_matrix
from penguin_slice.service import PlateConfigurationRefused, slice_plate_configuration
from penguin_slice.slicer import SliceError, _natural, plate_object_names
from test_orca import through_the_http_interface

# What each plate sliced to with the pinned Orca 2.4.2 (slices on an aarch64 Linux machine
# with 4 CPUs, slice/README-details.md, "The Popcorn Penguins' real parts"): print time (s), filament (g),
# layers, with supports off (MEASURED_SLICES) and on (MEASURED_SLICES_SUPPORTS). Between
# slices of one plate the print time moved by a few seconds in hours and the filament by
# 0.01 g (Orca's threads), so BAND is wide of that and far inside any real change.
MEASURED_SLICES = {
    "alone-clamp-plate-inner": (1072, 7.79, 20), "alone-elevator-block-bottom-inner": (6966, 64.04, 344),
    "alone-elevator-block-carriage": (4001, 39.72, 132), "alone-elevator-block-top": (4941, 50.23, 132),
    "alone-elevator-top-inner": (2727, 26.63, 106), "alone-inner-spacer": (663, 3.8, 5),
    "alone-outer-clamp": (1092, 8.19, 20), "alone-pulley-v3": (1070, 2.22, 74),
    "mixed": (19250, 202.15, 344), "team": (15051, 161.01, 132),
    "four-each-a": (36452, 403.18, 344), "four-each-b": (36467, 403.18, 344),
}
MEASURED_SLICES_SUPPORTS = {
    "four-each-a": (44306, 430.64, 344), "four-each-b": (44309, 430.64, 344),
}
BAND = 0.02
# Each instance's first-layer extrusions in the G-code (its brim left out) against the
# part's own points on the plate (within 0.05 mm of its lowest) placed by the instance.
# Measured within 0.47 mm (the outer wall's centre line lies half a 0.6 mm nozzle's line
# inside the outline; arcs, G2 and G3, followed along their sweep); the nearest other
# instance on these plates is 13 mm or more away, so a wrongly placed or wrongly paired
# instance is off by far more. Orca's bbox_objects is no help here: it includes the brim,
# up to 15 mm wide at the blocks. Supports are left out with the brim: with supports on they
# are printed in the object's own block and reach beyond its outline.
PLACEMENT_TOLERANCE_MM = 1.0
OBJECT_START = re.compile(r"^; printing object (.+) id:\d+ copy \d+$")
OBJECT_STOP = re.compile(r"^; stop printing object (.+) id:\d+ copy \d+$")
EXTRUSION = re.compile(r"([XYEIJ])(-?[\d.]+)")


def arc_points(x, y, move, clockwise):
    """Points along a G2 (clockwise) or G3 arc from (x, y) to the move's X Y about the centre
    at I J from the start, end included: enough to give the arc's extent within 0.1 mm."""
    cx, cy = x + float(move.get("I", 0)), y + float(move.get("J", 0))
    ex, ey = float(move.get("X", x)), float(move.get("Y", y))
    start, end = math.atan2(y - cy, x - cx), math.atan2(ey - cy, ex - cx)
    sweep = (start - end) % (2 * math.pi) if clockwise else (end - start) % (2 * math.pi)
    sweep = sweep or 2 * math.pi                                    # the same point: a whole circle
    radius = math.hypot(x - cx, y - cy)
    step = -1 if clockwise else 1
    return [(cx + radius * math.cos(start + step * sweep * k / 64), cy + radius * math.sin(start + step * sweep * k / 64))
            for k in range(1, 65)]

# The warnings that are true of the parts in the orientation the team prints them in, and
# that Orca gives: every block and the Elevator Top Inner has a ceiling over a pocket or a
# hole, printed as a bridge with nothing under it ("floating cantilever"; with supports on
# Orca no longer gives it); inside the pulley's bore a hub ring starts 4.76 mm above the
# plate with nothing under it and joins the rest only 0.8 mm higher ("floating regions").
# The flat clamps and the spacer warn of nothing. With supports on Orca warns of nothing:
# the supports hold up every one of those overhangs.
TRUE_WARNINGS = {
    "elevator-block-bottom-inner": "floating cantilever", "elevator-block-carriage": "floating cantilever",
    "elevator-block-top": "floating cantilever", "elevator-top-inner": "floating cantilever",
    "pulley-v3": "floating regions",
}
WARNING = "It seems object {label} has {kind}. Please re-orient the object or enable support generation."

SLICED_PLATES = [*((f"alone-{ref}", "off") for ref in sorted(frc_parts.PARTS)), ("mixed", "off"), ("team", "off"),
                 ("four-each-a", "off"), ("four-each-b", "off"), ("four-each-a", "on"), ("four-each-b", "on")]


def expected_warnings(instances, supports):
    if supports == "on":
        return []
    labels = instance_labels([frc_parts.PARTS[i["ref"]][1] for i in instances])
    found = [WARNING.format(label=label, kind=TRUE_WARNINGS[i["ref"]])
             for label, i in zip(labels, instances) if i["ref"] in TRUE_WARNINGS]
    return sorted(found, key=_natural)


def first_layer_box(instance, mesh, footprint):
    """The box of the part's points on the plate (within 0.05 mm of its lowest), placed by
    the instance: what Orca's bbox_objects gives for a part's first layer."""
    m = np.asarray(instance_matrix(plate_module.turn_of(instance), instance["angle"], footprint["offset"],
                                   instance["x"], instance["y"]), dtype=np.float64)
    points = mesh.vertices @ m[:, :3].T + m[:, 3]
    low = points[points[:, 2] < points[:, 2].min() + 0.05]
    return [low[:, 0].min(), low[:, 1].min(), low[:, 0].max(), low[:, 1].max()]


def first_layer_extrusions(gcode):
    """{object name: [x0, y0, x1, y1]} of every extruding move of the first layer printed
    for that object, brim left out."""
    layer = gcode.split("; CHANGE_LAYER", 2)[1]
    found, current, feature, x, y = {}, None, None, None, None
    for line in layer.splitlines():
        if line.startswith("; FEATURE:"):
            feature = line.split(":", 1)[1].strip()
        elif start := OBJECT_START.match(line):
            current = start.group(1)
        elif OBJECT_STOP.match(line):
            current = None
        elif line.startswith(("G0 ", "G1 ", "G2 ", "G3 ")):
            move = dict(EXTRUSION.findall(line.split(";")[0]))
            if line.startswith(("G2 ", "G3 ")) and x is not None and ("I" in move or "J" in move):
                points = arc_points(x, y, move, line.startswith("G2 "))
            else:
                points = [(float(move.get("X", x or 0.0)), float(move.get("Y", y or 0.0)))]
            if current and feature != "Brim" and not (feature or "").startswith("Support") \
                    and float(move.get("E", 0)) > 0:
                box = found.setdefault(current, [*points[0], *points[0]])
                for px, py in points:
                    box[:] = [min(box[0], px), min(box[1], py), max(box[2], px), max(box[3], py)]
            x, y = points[-1]
    return found


@pytest.fixture(scope="module")
def meshes():
    """{ref: (mesh, footprints)} of every part, read once."""
    found = {}
    for ref in frc_parts.PARTS:
        mesh = read_binary_stl(frc_parts.stl_bytes(ref), ref)
        found[ref] = (mesh, orientation_footprints(mesh))
    return found


@pytest.mark.parametrize("plate, supports", SLICED_PLATES)
def test_the_real_parts_slice_through_the_http_interface(tmp_path, meshes, plate, supports):
    instances = frc_parts.PLATES[plate]
    configuration = frc_parts.plate_configuration(instances)
    if supports == "on":
        configuration["overrides"] = {"supports": "on"}
    _stages, report, data, summary = through_the_http_interface(tmp_path / "work", configuration,
                                                                frc_parts.files_for(configuration))
    assert report["state"] == "done", report                   # no error report
    sliced = tmp_path / summary["file"]
    sliced.write_bytes(data)
    print(f"\n[orca] {plate}, supports {supports}: {len(data):,} bytes, {json.dumps(summary)}")
    labels = instance_labels([frc_parts.PARTS[i["ref"]][1] for i in instances])
    assert summary["instances"] == len(instances)
    assert sorted(plate_object_names(sliced)) == sorted(labels)
    with zipfile.ZipFile(sliced) as zf:
        assert zf.testzip() is None
        gcode = zf.read("Metadata/plate_1.gcode").decode()
    boxes = first_layer_extrusions(gcode)
    assert sorted(boxes) == sorted(labels)
    markers = [f"; {block}_BLOCK_{end}" for block in ("HEADER", "CONFIG", "EXECUTABLE") for end in ("START", "END")]
    at = [gcode.find(marker + "\n") for marker in markers]
    assert -1 not in at and at == sorted(at), dict(zip(markers, at))           # a whole G-code file
    print_time, filament, layers = (MEASURED_SLICES_SUPPORTS if supports == "on" else MEASURED_SLICES)[plate]
    assert summary["layer_count"] == layers
    assert summary["print_time_s"] == pytest.approx(print_time, rel=BAND)
    assert summary["filament_g"] == pytest.approx(filament, rel=BAND)
    assert summary["part_warnings"] == []
    assert summary["warnings"] == expected_warnings(instances, supports)
    errors = {}
    for label, instance in zip(labels, instances):
        mesh, footprints = meshes[instance["ref"]]
        expected = first_layer_box(instance, mesh, footprints[instance["orientation"]])
        errors[label] = max(abs(a - b) for a, b in zip(boxes[label], expected))
    print(f"[orca] {plate}, supports {supports}: worst first-layer box error {max(errors.values()):.4f} mm over "
          f"{len(labels)} instances")
    assert {label: e for label, e in errors.items() if e > PLACEMENT_TOLERANCE_MM} == {}


def tight_plate(gap):
    """The pairs that needed the most room in the measurements (slice/README-details.md, "Spacing"),
    `gap` mm apart: two Elevator Block Tops one behind the other with a Carriage behind them,
    and three Elevator Top Inners, two side by side and one behind."""
    top, carriage, inner = (frc_parts.FOOTPRINT_MM[r] for r in ("elevator-block-top", "elevator-block-carriage",
                                                                 "elevator-top-inner"))
    y_top2 = 50 + top[1] + gap
    x_inner = 60 + top[0] / 2 + gap + inner[0] / 2
    return [frc_parts.instance("elevator-block-top", 60, 50), frc_parts.instance("elevator-block-top", 60, y_top2),
            frc_parts.instance("elevator-block-carriage", 60, y_top2 + top[1] / 2 + gap + carriage[1] / 2),
            frc_parts.instance("elevator-top-inner", x_inner, 50),
            frc_parts.instance("elevator-top-inner", x_inner + inner[0] + gap, 50),
            frc_parts.instance("elevator-top-inner", x_inner + inner[0] + gap, 50 + inner[1] + gap)]


def slice_or_report(tmp_path, instances, supports):
    """The real parts' plate through the slice service: (summary, None) or (None, error report)."""
    configuration = frc_parts.plate_configuration(instances)
    configuration["overrides"] = {"supports": supports}
    parts = Parts(tmp_path)
    for data in frc_parts.files_for(configuration):
        parts.add(data)
    try:
        sliced = slice_plate_configuration(parts.read(configuration), tmp_path / "out")
    except (SliceError, PlateConfigurationRefused) as exc:
        return None, error_report(exc)
    return sliced.summary, None


@pytest.mark.parametrize("supports, gap", [("off", SPACING_MM), ("on", SPACING_SUPPORTS_MM)])
def test_the_placement_checks_spacing_is_enough_for_orca(tmp_path, supports, gap):
    """Protects: plate.SPACING_MM and SPACING_SUPPORTS_MM. The tightest pairs measured,
    exactly the spacing apart, pass the placement check and slice; a new Orca whose supports
    need more room fails here, not in front of a student."""
    summary, report = slice_or_report(tmp_path, tight_plate(gap), supports)
    assert report is None, report
    assert summary["instances"] == 6


def test_orca_names_the_pair_whose_supports_meet(tmp_path, monkeypatch):
    """Protects: Orca's -101 for instances whose supports meet, and its debug log line
    naming the pair (slicer.LOG_CONFLICT_RE, tests/fake_orca.py's CONFLICT). Two Elevator
    Block Tops 5 mm apart, one behind the other, supports on, the placement check's supports
    spacing lowered to let them reach Orca (measured: Orca refuses them up to 8 mm apart)."""
    monkeypatch.setattr(plate_module, "SPACING_SUPPORTS_MM", SPACING_MM)
    top = frc_parts.FOOTPRINT_MM["elevator-block-top"]
    instances = [frc_parts.instance("elevator-block-top", 170, 100),
                 frc_parts.instance("elevator-block-top", 170, 100 + top[1] + 5)]
    summary, report = slice_or_report(tmp_path, instances, "on")
    assert summary is None
    print(f"\n[orca] two Tops 5 mm apart with supports: {json.dumps(report)[:600]}")
    assert report["code"] == "slice.orca_too_close"
    assert report["where"] == {"instance": "Elevator_Block_Top #1", "other_instance": "Elevator_Block_Top #2",
                               "stage": "slicing"}
    assert report["message"] == ("Elevator_Block_Top #1 and Elevator_Block_Top #2 are too close together: the slicer "
                                 "found that their paths would meet, most likely their supports, which need more "
                                 "room between instances.")
    assert "turn supports off" in report["remedy"] and "second plate" in report["remedy"]
    assert "orca debug log: paths meet between Elevator_Block_Top #1 and Elevator_Block_Top #2" in report["detail"]
