"""The adapter from the slice service's exceptions to an error report
(contracts/error-report.md).

Each exception the slice service raises carries its error code (`error_code`), its
sentence for the student (`message`), the evidence for the log (`details`) and, when
known, the part or copy (`where`). The adapter adds the `remedy`, the `action`,
`retryable` and the stage from CODES. Orca's return codes and their error codes are in
slicer.ORCA_RETURN_CODES, the one table of them.
"""
from .jobs import GENERIC_FAILURE, JobFailure, QueueFull
from .mesh import MeshError
from .print_config import OverrideError, ProfileError
from .service import PlateJobRefused
from .slicer import UNSTARTABLE_MESSAGE, SliceError

# The queue's refusal had no sentence of its own; this is the original route's.
BUSY_MESSAGE = "The slicer is busy, try again in a minute."
SERVER_REMEDY = "Slice again; if it fails again, ask a mentor to check the print server."

# code -> (stage, retryable, action, remedy). Every code the slice service can produce;
# slice/README.md lists the same codes in this order, and tests/test_errors.py produces
# each on purpose and states what its report must say.
CODES = {
    "slice.bad_plate_job": ("checking", False, None,
                            "Lay out the plate again and send a new slice."),
    "slice.too_many_copies": ("checking", False, "lower_quantities",
                              "Lower the quantities and print the rest in a second job."),
    "slice.part_missing": ("checking", False, "refresh_parts",
                           "Load the parts again and send a new slice."),
    "slice.part_unreadable": ("checking", False, "refresh_parts",
                              "Export the part again and send a new slice."),
    "slice.part_too_detailed": ("checking", False, None,
                                "Export the part with a coarser tessellation, or simplify it, and slice again."),
    "slice.part_too_small": ("checking", False, None,
                             "Check the part's units and size, then slice again."),
    "slice.job_too_detailed": ("checking", False, "lower_quantities",
                               "Lower the quantities and print the rest in a second job."),
    "slice.unknown_printer": ("checking", False, None,
                              "Choose a printer from the list, or ask a mentor to add this one."),
    "slice.profiles_not_offered": ("checking", False, "choose_profiles",
                                   "Choose a filament and print settings from the lists and slice again."),
    "slice.bad_overrides": ("checking", False, "choose_profiles",
                            "Choose the print settings from the lists and slice again."),
    "slice.placement_off_plate": ("checking", False, "arrange",
                                  "Move the copy fully onto the plate, or press Arrange, and slice again."),
    "slice.placement_too_tall": ("checking", False, "choose_orientation",
                                 "Lay the part on another face so it is lower, and slice again."),
    "slice.placement_too_close": ("checking", False, "arrange",
                                  "Move the copies further apart, or press Arrange, and slice again."),
    "slice.busy": ("queued", True, None,
                   "Wait a minute and slice again."),
    "slice.orca_missing": ("slicing", False, None,
                           "Ask a mentor to check the print server; slicing is not set up on it."),
    "slice.orca_unstartable": ("slicing", False, None,
                               "Ask a mentor to check the print server; the slicer will not start on it."),
    "slice.timeout": ("slicing", True, "lower_quantities",
                      "Try again, or slice fewer copies at once."),
    "slice.orca_killed": ("slicing", True, "lower_quantities",
                          "Slice again; if it is stopped again, slice fewer copies at once."),
    "slice.orca_too_close": ("slicing", False, "arrange",
                             "Move the copies further apart, or press Arrange, and slice again."),
    "slice.crosses_edge": ("slicing", False, "arrange",
                           "Move the copy fully onto the plate, or press Arrange, and slice again."),
    "slice.empty_layers": ("slicing", False, None,
                           "Try another orientation or other print settings, and slice again."),
    "slice.nothing_on_plate": ("slicing", False, "arrange",
                               "Move the copies onto the plate, or press Arrange, and slice again."),
    "slice.orca_failed": ("slicing", False, None,
                          "Try another orientation or other print settings, and slice again."),
    "slice.no_output": ("slicing", True, None, SERVER_REMEDY),
    "slice.unreadable_output": ("slicing", True, None, SERVER_REMEDY),
    "slice.no_gcode": ("slicing", True, None, SERVER_REMEDY),
    "slice.left_off_plate": ("slicing", False, "arrange",
                             "Move every copy fully onto the plate, or press Arrange, and slice again."),
    "slice.output_unwritable": ("saving", False, None,
                                "Ask a mentor to check that the print server can write to its output folder, "
                                "then slice again."),
    "slice.unexpected": ("slicing", False, None, SERVER_REMEDY),
}

# The slice service's own exceptions: each carries message, details, error_code and where.
_OWN = (PlateJobRefused, MeshError, ProfileError, OverrideError, SliceError)


def _report(code, message, detail="", where=None):
    stage, retryable, action, remedy = CODES[code]
    report = {"code": code, "message": message, "where": dict(where or {}, stage=stage), "remedy": remedy,
              "retryable": retryable, "detail": detail}
    if action:
        report["action"] = action
    return report


def error_report(exc):
    """The error report for an exception the slice service raised."""
    if isinstance(exc, SliceError) and exc.code is not None:
        return _report(exc.error_code, exc.message, f"orca code {exc.code}\n{exc.details}", exc.where)
    if isinstance(exc, _OWN):
        return _report(exc.error_code, exc.message, exc.details, getattr(exc, "where", None))
    if isinstance(exc, QueueFull):
        return _report("slice.busy", BUSY_MESSAGE, "the job queue is full")
    if isinstance(exc, JobFailure) and exc.__cause__ is not None:
        return error_report(exc.__cause__)
    if isinstance(exc, JobFailure):
        return _report("slice.unexpected", GENERIC_FAILURE, f"JobFailure: {exc.message}\n{exc.details}")
    if isinstance(exc, RuntimeError) and str(exc).startswith("Orca Slicer is missing at "):
        return _report("slice.orca_missing", UNSTARTABLE_MESSAGE, str(exc))
    return _report("slice.unexpected", GENERIC_FAILURE, f"{type(exc).__name__}: {exc}")
