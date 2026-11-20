"""Limits of the slice service that concern parts, plates and slicing, and the sentences that
refuse them. Imports only os.

One source for every cap the plate job reader, the mesh reader and the plate slice
enforce, and for the sentence a student sees when one is reached; each sentence that names
a number is formatted from the cap, so the two cannot differ. The caps were set from
slices measured on an aarch64 Linux machine (slice/README.md, "Plate limits").
"""
import os

# One part. The triangle cap bounds the time to read and check a part, not Orca's memory.
MAX_PART_TRIANGLES = 150_000
MAX_PART_BYTES = 84 + 50 * MAX_PART_TRIANGLES     # a binary STL of exactly that many triangles

# One plate, one plate job.
MAX_COPIES = 25                                   # 30 peaked 1.5% under 900 MB; 25 leaves headroom
PLATE_SLICE_TIMEOUT_S = 240                       # the sample part keeps slicer.DEFAULT_TIMEOUT_S

# The memory model: a rough estimate of Orca's peak resident memory for a plate, in MB,
#   (BASE + PER_COPY * copies + PER_CM3 * part volume on the plate in cm3) * (SUPPORTS if supports on)
# where a part's volume is its mesh's when the mesh is watertight, else its bounding box's
# (mesh.analyse). Fitted as the upper envelope of the plates in slice/README.md, "Plate
# limits", it is wrong both ways on other plates (a 100 mm solid cube: 1,158 MB estimated,
# 269 MB measured; 25 hubs of 20,000 triangles: 792 MB estimated, 842 MB measured), so it
# refuses nothing: it is logged with each plate job and feeds nothing else. Refitting it
# (scripts/measure_plate.py --fit) belongs with the choice of hosting.
MEMORY_BASE_MB = 170.0
MEMORY_PER_COPY_MB = 3.0
MEMORY_PER_CM3_MB = 0.985
MEMORY_SUPPORTS_FACTOR = 1.4
# The memory ceiling: a setting (environment variable), 900 MB by default. The slice
# service's memory watchdog (slicer.run_process) stops an Orca whose processes pass it.
MAX_PEAK_MB_ENV = "PENGUIN_SLICE_MAX_PEAK_MB"
DEFAULT_MAX_PEAK_MB = 900

# The time model for the expected_s of a progress report: seconds for Orca on a plate, the
# same shape as the memory model, fitted by hand to the same plates (within a factor of
# about two of each; the bunny slices slower per cm3 than the smooth organic body).
TIME_BASE_S = 1.0
TIME_PER_COPY_S = 0.35
TIME_PER_CM3_S = 0.008
TIME_SUPPORTS_FACTOR = 1.3

# The stop rule for scripts/measure_plate.py: a measurement is stopped when Orca passes it.
MEASURE_STOP_MB = 3 * 1024                        # 3 GB: the memory watchdog's ceiling while measuring
MEASURE_MAX_SECONDS = 180

# The sentences, one per limit. {name} is filled in by the caller.
TOO_DETAILED_MESSAGE = ("{name} is too detailed to print here "
                        f"(over {MAX_PART_TRIANGLES:,} triangles).")
TOO_MANY_COPIES_MESSAGE = f"Up to {MAX_COPIES} copies per plate; print the rest in a second job."
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


def max_peak_mb(environ=None):
    """The memory ceiling in MB: PENGUIN_SLICE_MAX_PEAK_MB when it is a positive whole
    number, else DEFAULT_MAX_PEAK_MB."""
    raw = (os.environ if environ is None else environ).get(MAX_PEAK_MB_ENV, "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_MAX_PEAK_MB


def estimate_peak_mb(copy_volumes_mm3, supports_on):
    """The memory model's rough estimate for a plate whose copies have these volumes (for
    the log only)."""
    mb = MEMORY_BASE_MB + MEMORY_PER_COPY_MB * len(copy_volumes_mm3) + MEMORY_PER_CM3_MB * sum(copy_volumes_mm3) / 1000
    return round(mb * (MEMORY_SUPPORTS_FACTOR if supports_on else 1.0))


def estimate_seconds(copy_volumes_mm3, supports_on):
    """The time model's expected seconds of Orca for a plate."""
    s = TIME_BASE_S + TIME_PER_COPY_S * len(copy_volumes_mm3) + TIME_PER_CM3_S * sum(copy_volumes_mm3) / 1000
    return round(s * (TIME_SUPPORTS_FACTOR if supports_on else 1.0), 1)
