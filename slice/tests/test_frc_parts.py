"""The eight real parts of the Popcorn Penguins' (FRC Team 6238) robot, read and checked as
the slice service reads every part (tests/fixtures/frc-parts/README.md). They were printed
and work on the robot, so a refusal, a warning or a wrong figure here is a defect in the
slice service. Each part is read once (the module's fixture: all eight together, 0.17 to
0.19 s in three runs, slice/README-details.md, "Tests"); the figures are tests/frc_parts.py's,
measured once from the files.
"""
import zipfile
from collections import Counter

import pytest

import frc_parts
from penguin_slice import limits
from penguin_slice.plate import ORIENTATIONS, check_placement, plate_from_printer
from penguin_slice.plate_3mf import write_plate_3mf
from helpers import Parts
from penguin_slice.print_config import choose_profiles, printer_profile

H2S = plate_from_printer(printer_profile(choose_profiles(None, None, None)))
H2S_SUPPORTS = plate_from_printer(printer_profile(choose_profiles(None, None, None)), supports=True)


@pytest.fixture(scope="module")
def mixed(tmp_path_factory):
    """The mixed plate (one instance of every part) through the checks on arrival, each part
    uploaded to a part store, and the plate configuration checks."""
    configuration = frc_parts.plate_configuration(frc_parts.MIXED)
    parts = Parts(tmp_path_factory.mktemp("frc-parts"))
    for data in frc_parts.files_for(configuration):
        parts.add(data)
    return parts.read(configuration, environ={})


def test_every_part_is_in_the_folder_with_its_licence_note():
    files = sorted(p.name for p in frc_parts.FRC_PARTS_DIR.iterdir())
    assert files == sorted([file for file, _name, _o in frc_parts.PARTS.values()] + ["README.md"])
    readme = (frc_parts.FRC_PARTS_DIR / "README.md").read_text()
    assert "Copyright (c) 2026 Popcorn Penguins, Inc." in readme and "MIT" in readme
    for _file, name, _o in frc_parts.PARTS.values():
        assert f"{name}.stl" in readme, name                        # the original file name


def test_the_mixed_plate_of_all_eight_parts_passes_every_check(mixed):
    assert mixed.labels == ["Elevator_Block_Top #1", "Elevator_Block_Bottom_Inner #1", "Elevator_Block_Carriage #1",
                            "Elevator_Top_Inner #1", "Clamp_Plate_Inner #1", "Outer_Clamp #1", "Inner_Spacer #1",
                            "Pulley_v3 #1"]
    assert mixed.part_warnings() == []
    assert mixed.memory_ceiling_mb == limits.DEFAULT_MAX_PEAK_MB


@pytest.mark.parametrize("ref", sorted(frc_parts.PARTS))
def test_what_the_slice_service_reports_about_each_part(mixed, ref):
    """Triangles, size, volume, a closed surface of one shell, no warning: every one true of
    the file (a watertight part from Onshape's export)."""
    part = mixed.parts[ref]
    triangles, size, volume = frc_parts.MEASURED[ref]
    assert part.name == frc_parts.PARTS[ref][1]
    assert part.triangles == part.health["surface_triangles"] == triangles
    assert part.health["size_mm"] == size
    assert part.health["volume_mm3"] == volume and part.health["volume_basis"] == "mesh"
    assert (part.health["watertight"], part.health["shells"], part.health["open_edges"],
            part.health["overused_edges"], part.health["inside_out"]) == (True, 1, 0, 0, False)
    assert part.warnings == []


@pytest.mark.parametrize("ref", sorted(frc_parts.PARTS))
def test_each_resting_position_of_each_part(mixed, ref):
    """Every orientation's height is the part's size along the axis that points up, and the
    orientation the team prints it in has the footprint the plates are laid out with."""
    part = mixed.parts[ref]
    _triangles, size, _volume = frc_parts.MEASURED[ref]
    for orientation in ORIENTATIONS:
        assert part.footprints[orientation]["height"] == size["xyz".index(orientation[1])], orientation
    hull = part.footprints[frc_parts.PARTS[ref][2]]["hull"]
    width = max(p[0] for p in hull) - min(p[0] for p in hull)
    depth = max(p[1] for p in hull) - min(p[1] for p in hull)
    assert (width, depth) == pytest.approx(frc_parts.FOOTPRINT_MM[ref], abs=0.002)


@pytest.mark.parametrize("supports", [False, True])
@pytest.mark.parametrize("plate", ["mixed", "team", "four-each-a", "four-each-b"])
def test_the_plates_the_real_orca_suite_slices_pass_the_placement_check(mixed, plate, supports):
    """With supports off and on: every example plate leaves the larger spacing supports need."""
    placed = {ref: {"name": p.name, "footprints": p.footprints} for ref, p in mixed.parts.items()}
    assert check_placement(frc_parts.PLATES[plate], placed, H2S_SUPPORTS if supports else H2S) == []


def test_the_slice_service_hands_orca_the_same_plate_every_time(mixed, tmp_path):
    """Protects: two writes of one plate configuration give a plate 3MF with the same
    entries, byte for byte (the zip's own time stamps aside), so any difference between two
    slices of it is Orca's (slice/README-details.md, "The same plate, sliced again"). The pulleys and
    spacers of plate four-each-a, the two smallest parts, to keep the write short."""
    instances = [i for i in frc_parts.FOUR_EACH_A if i["ref"] in ("pulley-v3", "inner-spacer")]
    parts = {ref: {"name": p.name, "stl_path": p.stl_path, "footprints": p.footprints}
             for ref, p in mixed.parts.items()}
    written = []
    for run in ("first", "second"):
        write_plate_3mf(tmp_path / f"{run}.3mf", instances, parts)
        with zipfile.ZipFile(tmp_path / f"{run}.3mf") as zf:
            written.append({name: zf.read(name) for name in zf.namelist()})
    assert written[0] == written[1]
    assert len(written[0]["3D/3dmodel.model"]) > 500_000            # the meshes are in it


def test_the_two_plates_hold_four_instances_of_every_part():
    """The mechanical mentor's target: 4 instances of each part, 32 in all, on two plates."""
    held = Counter(i["ref"] for plate in frc_parts.FOUR_EACH.values() for i in plate)
    assert held == {ref: 4 for ref in frc_parts.PARTS}
    assert all(i["orientation"] == frc_parts.PARTS[i["ref"]][2] and i["angle"] == 0
               for plate in frc_parts.FOUR_EACH.values() for i in plate)
