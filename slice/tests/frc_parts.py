"""The eight real parts of FRC Team 6238's robot (tests/fixtures/frc-parts/, README there)
and the plate configurations built from them, shared by the fast suite (reading and checking
each part) and the real-Orca suite (slicing them alone and on two plates).

Every figure here was measured once from the files with the slice service's own code
(mesh.read_binary_stl, mesh.analyse, mesh.orientation_footprints) and written in by hand,
so a change in what the slice service reports about a real part fails a test.
"""
import hashlib
from pathlib import Path

FRC_PARTS_DIR = Path(__file__).resolve().parent / "fixtures" / "frc-parts"

# ref -> (file, the name a student would give it, the orientation the team prints it in:
# its largest flat face on the plate).
PARTS = {
    "clamp-plate-inner": ("clamp-plate-inner.stl", "Clamp Plate Inner", "-x"),
    "elevator-block-bottom-inner": ("elevator-block-bottom-inner.stl", "Elevator Block Bottom Inner", "-z"),
    "elevator-block-carriage": ("elevator-block-carriage.stl", "Elevator Block Carriage", "+y"),
    "elevator-block-top": ("elevator-block-top.stl", "Elevator Block Top", "+y"),
    "elevator-top-inner": ("elevator-top-inner.stl", "Elevator Top Inner", "+y"),
    "inner-spacer": ("inner-spacer.stl", "Inner Spacer", "+x"),
    "outer-clamp": ("outer-clamp.stl", "Outer Clamp", "-x"),
    "pulley-v3": ("pulley-v3.stl", "Pulley v3", "+x"),
}

# What the slice service reports about each part, measured: triangles, size (mm, as
# exported; each resting position's height is the size along the axis that points up), and
# enclosed volume (mm3). Every part is watertight, one shell, wound outwards, with no open
# edge: none of the slice service's part warnings is true of any.
MEASURED = {
    "clamp-plate-inner": (8_756, [4.762, 50.8, 50.8], 8_642.1),
    "elevator-block-bottom-inner": (39_054, [88.9, 63.5, 82.55], 127_522.2),
    "elevator-block-carriage": (23_580, [88.9, 31.75, 57.15], 80_017.8),
    "elevator-block-top": (34_998, [88.9, 31.75, 82.55], 95_926.8),
    "elevator-top-inner": (19_392, [50.8, 25.4, 57.15], 46_841.8),
    "inner-spacer": (2_908, [1.262, 50.8, 50.8], 3_110.7),
    "outer-clamp": (8_724, [4.762, 50.8, 50.8], 9_405.5),
    "pulley-v3": (4_608, [17.78, 19.05, 19.05], 2_155.6),
}


def stl_bytes(ref):
    return (FRC_PARTS_DIR / PARTS[ref][0]).read_bytes()


def instance(ref, x, y, angle=0):
    return {"ref": ref, "orientation": PARTS[ref][2], "angle": angle, "x": float(x), "y": float(y)}


def plate_configuration(instances):
    """The phase 2 plate configuration of `instances` at the default profiles, each part named
    by the hash of its file, in millimetres."""
    refs = list(dict.fromkeys(i["ref"] for i in instances))
    return {"plate_id": "frc-plate", "submission_id": "frc-submission",
            "parts": {ref: {"name": PARTS[ref][1], "sha256": hashlib.sha256(stl_bytes(ref)).hexdigest(),
                            "units": "mm"} for ref in refs},
            "instances": instances}


def files_for(configuration):
    """[bytes] of each part of the plate configuration, to upload before it is submitted."""
    return [stl_bytes(ref) for ref in configuration["parts"]]


# Each part alone, in the middle of the H2S plate (340 x 320 mm).
ALONE = {ref: [instance(ref, 170, 160)] for ref in PARTS}

# The plates from here to FULL leave at least 12.5 mm between footprints, more than the
# placement check's spacing with supports on (plate.SPACING_SUPPORTS_MM, 12 mm), so each
# slices with supports off and on. The FULL plates below are spaced as they say.

# All eight, one instance each: the three blocks in a row at the front, the five smaller
# parts in a row behind them, every gap 14 mm or more.
MIXED = [instance("elevator-block-top", 60, 55), instance("elevator-block-bottom-inner", 165, 50),
         instance("elevator-block-carriage", 270, 45), instance("elevator-top-inner", 40, 150),
         instance("clamp-plate-inner", 110, 150), instance("outer-clamp", 180, 150),
         instance("inner-spacer", 250, 150), instance("pulley-v3", 310, 150)]

# A plate a team would print: two blocks with the small parts of the clamps and pulleys
# around them (4 inner spacers, 3 outer clamps, 3 clamp plates, 4 pulleys), every gap
# 14 mm or more.
TEAM = ([instance("elevator-block-top", 60, 55), instance("elevator-block-carriage", 175, 45)]
        + [instance("pulley-v3", x, y) for x, y in ((245, 30), (280, 30), (245, 65), (280, 65))]
        + [instance("inner-spacer", x, 150) for x in (40, 105, 170, 235)]
        + [instance("outer-clamp", x, y) for x, y in ((300, 150), (40, 220), (105, 220))]
        + [instance("clamp-plate-inner", x, 220) for x in (170, 235, 300)])

# The footprint of each part in its orientation, x by y (mm), as orientation_footprints gives it.
FOOTPRINT_MM = {
    "clamp-plate-inner": (50.8, 50.8), "elevator-block-bottom-inner": (88.9, 63.5),
    "elevator-block-carriage": (88.9, 57.15), "elevator-block-top": (88.9, 82.55),
    "elevator-top-inner": (50.8, 57.15), "inner-spacer": (50.8, 50.8), "outer-clamp": (50.8, 50.8),
    "pulley-v3": (19.05, 19.05),
}
PLATE_CENTRE = (170.0, 160.0)       # the H2S plate, 340 x 320 mm


def grid(refs, columns, rows, gap_x, gap_y, count=None):
    """`count` instances (all the cells by default) in `columns` x `rows` cells centred on the
    plate, row by row, `gap_x` and `gap_y` mm between footprints; `refs` is one part's ref or
    a list cycled through the cells. Every part in one grid has the same footprint."""
    refs = [refs] if isinstance(refs, str) else refs
    width, depth = FOOTPRINT_MM[refs[0]]
    pitch_x, pitch_y = width + gap_x, depth + gap_y
    count = columns * rows if count is None else count
    return [instance(refs[k % len(refs)], PLATE_CENTRE[0] + (k % columns - (columns - 1) / 2) * pitch_x,
                     PLATE_CENTRE[1] + (k // columns - (rows - 1) / 2) * pitch_y) for k in range(count)]


# The mechanical mentor's target: 4 instances of every part (32 in all) on two H2S plates,
# every instance in the orientation the team prints it in, none turned. Each plate holds 2
# instances of every part (16), so the large blocks, which cost the memory, are shared out:
# two columns of an Elevator Block Top, a Bottom Inner and a Carriage (the columns 231 mm
# deep of the 314 mm the margins leave), a pulley above each, and two columns of an Elevator
# Top Inner, a Clamp Plate Inner, an Outer Clamp and an Inner Spacer beside them; every gap
# 13 to 14.2 mm. four-each-b is four-each-a mirrored left to right.
FOUR_EACH_A = ([instance(ref, x, y) for x in (50, 152) for ref, y in
                (("elevator-block-top", 47), ("elevator-block-bottom-inner", 134),
                 ("elevator-block-carriage", 208), ("pulley-v3", 275))]
               + [instance(ref, x, y) for x in (236, 300) for ref, y in
                  (("elevator-top-inner", 34), ("clamp-plate-inner", 101), ("outer-clamp", 165),
                   ("inner-spacer", 229))])
FOUR_EACH_B = [dict(i, x=2 * PLATE_CENTRE[0] - i["x"]) for i in FOUR_EACH_A]
FOUR_EACH = {"four-each-a": FOUR_EACH_A, "four-each-b": FOUR_EACH_B}

# Full plates, measured for the detailed guide's memory figures and not sliced by the real-Orca suite
# (see slice/README-details.md, "Plate limits"): as many instances of one part as fit the plate,
# and a full plate of the small parts, with supports off (gaps 5.8 to 10 mm); and the
# heaviest of them spaced for supports, measured with supports on. full-pulleys (150
# instances) passed 2,500 MB.
FULL = {
    "full-elevator-block-top": grid("elevator-block-top", 3, 3, 10, 10),
    "full-elevator-block-bottom-inner": grid("elevator-block-bottom-inner", 3, 4, 10, 10),
    "full-elevator-block-bottom-inner-spaced": grid("elevator-block-bottom-inner", 3, 4, 12.5, 12.5),
    "full-elevator-block-carriage": grid("elevator-block-carriage", 3, 5, 10, 6),
    "full-elevator-top-inner": grid("elevator-top-inner", 5, 5, 10, 6),
    "full-clamps-and-spacers": grid(["clamp-plate-inner", "outer-clamp", "inner-spacer"], 6, 5, 5.8, 10),
    "full-pulleys": grid("pulley-v3", 13, 12, 7, 7, count=150),
}

PLATES = {**{f"alone-{ref}": instances for ref, instances in ALONE.items()}, "mixed": MIXED, "team": TEAM, **FOUR_EACH,
          **FULL}
