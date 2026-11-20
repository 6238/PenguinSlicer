"""Limits of the slice service that concern parts, plates and slicing, and the sentences that
refuse them. Imports only os and re.

One source for every cap the plate configuration reader, the mesh reader and the plate
slice enforce, and for the sentence a student sees when one is reached; each sentence that
names a number is formatted from the cap, so the two cannot differ. The caps were set from
slices measured on an aarch64 Linux machine (slice/README.md, "Plate limits").
"""
import os
import re

# One part. The triangle cap bounds the time to read and check a part, not Orca's memory.
MAX_PART_TRIANGLES = 150_000
MAX_PART_BYTES = 84 + 50 * MAX_PART_TRIANGLES     # a binary STL of exactly that many triangles

# One plate, one plate configuration. Hex shaft spacers in a grid (slice/README.md, "Plate
# limits"): 100 peaked at 488 to 513 MB, 150 at 643 to 649 MB, 196 at 815 to 829 MB, 92 %
# of the 900 MB ceiling. 150 keeps more than a quarter of the ceiling free for small parts;
# the memory watchdog, not this count, is what protects the machine.
MAX_INSTANCES = 150
# Distinct parts the instances use. Not a measured limit: it bounds the upload (instances of
# one part share one STL file, so the upload is MAX_PARTS x MAX_PART_BYTES at most), and is
# what the old cap of 25 instances already implied. There is no cap on the triangles of the
# whole plate: none was measured to refuse a plate the watchdog would have stopped without
# also refusing plates that slice, so the watchdog alone decides.
MAX_PARTS = 25
PLATE_SLICE_TIMEOUT_S = 240                       # the sample part keeps slicer.DEFAULT_TIMEOUT_S

# The memory model: a rough estimate of Orca's peak resident memory for a plate, in MB,
#   (BASE + PER_INSTANCE * instances + PER_CM3 * part volume on the plate in cm3) * (SUPPORTS if supports on)
# where a part's volume is its mesh's when the mesh is watertight, else its bounding box's
# (mesh.analyse). Fitted as the upper envelope of the plates in slice/README.md, "Plate
# limits", it is wrong both ways on other plates (a 100 mm solid cube: 1,158 MB estimated,
# 269 MB measured; 25 hubs of 20,000 triangles: 792 MB estimated, 842 MB measured), so it
# refuses nothing: it is logged with each slice job and feeds nothing else.
# Refitting it (scripts/measure_plate.py --fit) belongs with the choice of hosting.
MEMORY_BASE_MB = 170.0
MEMORY_PER_INSTANCE_MB = 3.0
MEMORY_PER_CM3_MB = 0.985
MEMORY_SUPPORTS_FACTOR = 1.4
# The memory ceiling: a setting (environment variable), 900 MB by default. The slice
# service's memory watchdog (slicer.run_process) stops an Orca whose processes pass it.
MAX_PEAK_MB_ENV = "PENGUIN_SLICE_MAX_PEAK_MB"
DEFAULT_MAX_PEAK_MB = 900
_PEAK_MB_RE = re.compile(r"[0-9]{1,6}")           # plain ASCII digits only: no "²", no "٣"

# The time model for the expected_s of a progress report: seconds for Orca on a plate, the
# same shape as the memory model, fitted by hand to the same plates (within a factor of
# about two of each; the bunny slices slower per cm3 than the smooth organic body).
TIME_BASE_S = 1.0
TIME_PER_INSTANCE_S = 0.35
TIME_PER_CM3_S = 0.008
TIME_SUPPORTS_FACTOR = 1.3

# The stop rule for scripts/measure_plate.py: a measurement is stopped when Orca passes it.
MEASURE_STOP_MB = 3 * 1024                        # 3 GB: the memory watchdog's ceiling while measuring
MEASURE_MAX_SECONDS = 180

# The sentences, one per limit. {name} is filled in by the caller.
TOO_DETAILED_MESSAGE = ("{name} is too detailed to print here "
                        f"(over {MAX_PART_TRIANGLES:,} triangles).")
TOO_MANY_INSTANCES_MESSAGE = ("This plate has {count:,} instances; the slicer takes up to "
                              f"{MAX_INSTANCES} on one plate, so print the rest on a second plate.")
TOO_MANY_PARTS_MESSAGE = ("This plate uses {count:,} different parts; the slicer takes up to "
                          f"{MAX_PARTS} on one plate, so print the rest on a second plate.")
TOO_SMALL_MESSAGE = "{name} is too small to print ({x} x {y} x {z} mm)."
TOO_THIN_MESSAGE = "{name} is flat: it is {thickness} mm thick, too thin to print."
MIN_PART_EXTENT_MM = 0.1                          # a part must be more than this in every direction
NO_SURFACE_MESSAGE = "{name} has no surface: every triangle in its file is a line or a point."
LOOSE_TRIANGLES_MESSAGE = "{name} is loose triangles that enclose nothing, so there is nothing to print."
ENCLOSES_NOTHING_MESSAGE = ("{name} is a surface folded onto itself that encloses nothing, so there is nothing "
                            "to print.")
PART_TOO_LARGE_MESSAGE = ("{name} is {x} x {y} x {z} mm, larger than the printer can print in any orientation "
                          "({px} x {py} x {pz} mm).")
PART_UNREADABLE_MESSAGE = "The file for {name} could not be read as a part."
PART_EMPTY_MESSAGE = "The file for {name} is empty."
PART_NOT_STL_MESSAGE = "The file for {name} is not an STL file."
PART_ASCII_MESSAGE = "The file for {name} is a text STL; the slicer needs a binary STL."
PART_NO_TRIANGLES_MESSAGE = "The file for {name} has no triangles in it."
PART_CUT_OFF_MESSAGE = "The file for {name} is cut off before its end."
PART_EXTRA_DATA_MESSAGE = "The file for {name} has extra data after its last triangle."
NOT_FINITE_MESSAGE = "The file for {name} has coordinates that are not numbers."
BAD_SETTING_MESSAGE = ("The setting {env} is {value}, which is not a whole number of megabytes from 1 to "
                       "999999 written in the digits 0 to 9; set it so, or unset it for the default of "
                       f"{DEFAULT_MAX_PEAK_MB} MB.")


class SettingError(ValueError):
    """A setting of the slice service's that it refuses at start; the message names it."""


def max_peak_mb(environ=None):
    """The memory ceiling in MB: DEFAULT_MAX_PEAK_MB when PENGUIN_SLICE_MAX_PEAK_MB is unset
    or empty, else its value, which must be 1 to 6 plain ASCII digits and not 0. Raises
    SettingError (naming the setting) for anything else."""
    raw = (os.environ if environ is None else environ).get(MAX_PEAK_MB_ENV, "")
    if raw == "":
        return DEFAULT_MAX_PEAK_MB
    if not _PEAK_MB_RE.fullmatch(raw) or int(raw) == 0:
        raise SettingError(BAD_SETTING_MESSAGE.format(env=MAX_PEAK_MB_ENV, value=repr(raw[:40])))
    return int(raw)


def estimate_peak_mb(instance_volumes_mm3, supports_on):
    """The memory model's rough estimate for a plate whose instances have these volumes (for
    the log only)."""
    mb = MEMORY_BASE_MB + MEMORY_PER_INSTANCE_MB * len(instance_volumes_mm3) + \
        MEMORY_PER_CM3_MB * sum(instance_volumes_mm3) / 1000
    return round(mb * (MEMORY_SUPPORTS_FACTOR if supports_on else 1.0))


def estimate_seconds(instance_volumes_mm3, supports_on):
    """The time model's expected seconds of Orca for a plate."""
    s = TIME_BASE_S + TIME_PER_INSTANCE_S * len(instance_volumes_mm3) + \
        TIME_PER_CM3_S * sum(instance_volumes_mm3) / 1000
    return round(s * (TIME_SUPPORTS_FACTOR if supports_on else 1.0), 1)
