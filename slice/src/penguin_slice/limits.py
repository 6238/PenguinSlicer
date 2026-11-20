"""Limits of the slice service that concern parts, plates and slicing, and the sentences that
refuse them. No imports.

One source for every cap the plate job reader, the mesh reader and the plate slice
enforce, and for the sentence a student sees when one is reached; each sentence that names
a number is formatted from the cap, so the two cannot differ. The caps were set from
slices measured on an aarch64 Linux machine; the plates measured at these limits are
recorded in jobs.py's sizing note.
"""

# One part.
MAX_PART_TRIANGLES = 150_000
MAX_PART_BYTES = 84 + 50 * MAX_PART_TRIANGLES     # a binary STL of exactly that many triangles

# One plate, one plate job.
MAX_COPIES = 25                                   # 30 peaked 1.5% under the 900 MB rule; 25 leaves headroom
MAX_JOB_TRIANGLES = 300_000                       # summed over every copy on the plate
PLATE_SLICE_TIMEOUT_S = 240                       # the sample part keeps slicer.DEFAULT_TIMEOUT_S

# The stop rule for scripts/measure_plate.py: a plate at the limits must stay inside
# both, or MAX_JOB_TRIANGLES comes down.
MEASURE_MAX_PEAK_KB = 921_600                     # 900 MB, as Linux reports ru_maxrss
MEASURE_MAX_SECONDS = 180

# The sentences, one per limit. {name} is filled in by the caller.
TOO_DETAILED_MESSAGE = ("{name} is too detailed to print here "
                        f"(over {MAX_PART_TRIANGLES:,} triangles).")
TOO_MANY_COPIES_MESSAGE = f"Up to {MAX_COPIES} copies per plate; print the rest in a second job."
JOB_TRIANGLES_MESSAGE = "These copies are too detailed to slice together; lower the quantities."
TOO_SMALL_MESSAGE = "{name} is too small to print (under 0.1 mm)."
MIN_PART_EXTENT_MM = 0.1                          # TOO_SMALL_MESSAGE's 0.1 mm
PART_UNREADABLE_MESSAGE = "The file for {name} could not be read as a part."
