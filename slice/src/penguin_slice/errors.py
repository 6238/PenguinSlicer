"""The adapter from the slice service's exceptions to an error report
(contracts/error-report.md).

Each exception the slice service raises carries its error code (`error_code`), its
sentence for the student (`message`), the evidence for the log (`details`) and, when
known, the part, instance or height (`where`). The adapter adds the `remedy`, the `action`,
`retryable` and the stage from CODES. Orca's return codes and their error codes are in
slicer.ORCA_RETURN_CODES, the one table of them.
"""
from .jobs import GENERIC_FAILURE, JobFailure, QueueFull, exception_text
from .mesh import MeshError
from .print_config import OverrideError, ProfileError
from .service import PlateConfigurationRefused
from .slicer import UNSTARTABLE_MESSAGE, SliceCancelled, SliceError

# The queue's refusal had no sentence of its own; this is the original route's.
BUSY_MESSAGE = "The slicer is busy, try again in a minute."
SERVER_REMEDY = "Slice again; if it fails again, ask a mentor to check the print server."
REEXPORT_REMEDY = "Export the part again and send a new slice."

# code -> (stage, retryable, action, remedy). Every code the slice service can produce;
# slice/README.md lists the same codes in this order, and tests/test_errors.py produces
# each on purpose and states what its report must say.
CODES = {
    "slice.bad_plate_configuration": ("checking", False, None,
                                      "Lay out the plate again and send a new slice."),
    "slice.too_many_instances": ("checking", False, "lower_quantities",
                                 "Lower the quantities and print the rest on a second plate."),
    "slice.too_many_parts": ("checking", False, None,
                             "Use fewer different parts on this plate and print the rest on a second plate."),
    "slice.unknown_printer": ("checking", False, None,
                              "Choose a printer from the list, or ask a mentor to add this one."),
    "slice.profiles_not_offered": ("checking", False, "choose_profiles",
                                   "Choose a filament and print settings from the lists and slice again."),
    "slice.bad_overrides": ("checking", False, "choose_profiles",
                            "Choose the print settings from the lists and slice again."),
    "slice.profile_unreadable": ("checking", False, None,
                                 "Ask a mentor to check the print server's profiles; `make upgrade-orca` with the "
                                 "pinned version writes them again."),
    "slice.part_missing": ("checking", False, "refresh_parts",
                           "Load the parts again and send a new slice."),
    "slice.part_unreadable": ("checking", False, "refresh_parts", REEXPORT_REMEDY),
    "slice.part_not_binary": ("checking", False, None,
                              "Export the part again as a binary STL and send a new slice."),
    "slice.part_too_detailed": ("checking", False, None,
                                "Export the part with a coarser tessellation, or simplify it, and slice again."),
    "slice.part_too_small": ("checking", False, None,
                             "Check the part's units and size, then slice again."),
    "slice.part_no_volume": ("checking", False, None,
                             "Make the part a closed solid in CAD, export it again and send a new slice."),
    "slice.part_too_large": ("checking", False, None,
                             "Check the part's units, or split the part in CAD so each piece fits, "
                             "and slice again."),
    "slice.placement_off_plate": ("checking", False, "arrange",
                                  "Move the instance fully onto the plate, or press Arrange, and slice again."),
    "slice.placement_too_tall": ("checking", False, "choose_orientation",
                                 "Lay the part on another face so it is lower, and slice again."),
    "slice.placement_too_close": ("checking", False, "arrange",
                                  "Move the instances further apart, or press Arrange, and slice again."),
    "slice.busy": ("queued", True, None,
                   "Wait a minute and slice again."),
    "slice.scratch_unwritable": ("building", True, None,
                                 "Ask a mentor to check the print server's free disk space and its work folder, "
                                 "then slice again."),
    "slice.orca_missing": ("slicing", False, None,
                           "Ask a mentor to check the print server; slicing is not set up on it."),
    "slice.orca_unstartable": ("slicing", False, None,
                               "Ask a mentor to check the print server; the slicer will not start on it."),
    "slice.timeout": ("slicing", True, "lower_quantities",
                      "Try again, or slice fewer instances at once."),
    "slice.cancelled": ("slicing", True, None,
                        "Send the slice again when you want it."),
    "slice.out_of_memory": ("slicing", False, "lower_quantities",
                            "Remove some instances or the largest part and print them on a second plate."),
    "slice.orca_crashed": ("slicing", False, None,
                           "Try another orientation or other print settings; if it crashes again, ask a mentor "
                           "to check the part."),
    "slice.orca_killed": ("slicing", True, None, SERVER_REMEDY),
    "slice.orca_too_close": ("slicing", False, "arrange",
                             "Move the instances further apart, or press Arrange, and slice again."),
    "slice.crosses_edge": ("slicing", False, "arrange",
                           "Move the instance fully onto the plate, or press Arrange, and slice again."),
    "slice.empty_layers": ("slicing", False, "enable_supports",
                           "Turn Supports on, or repair the part in CAD so it has no gap, and slice again."),
    "slice.empty_layers_with_supports": ("slicing", False, None,
                                         "Repair the part in CAD so it has no gap or loose surfaces, export it "
                                         "again and slice again."),
    "slice.no_layers": ("slicing", False, None,
                        "Repair the part in CAD so it is a closed solid, check its size and thickness, export it "
                        "again and slice again."),
    "slice.print_empty": ("slicing", False, None,
                          "Check the part's size and units, make thin features thicker than the nozzle, and slice "
                          "again."),
    "slice.nothing_on_plate": ("slicing", False, "arrange",
                               "Move the instances onto the plate, or press Arrange, and slice again."),
    "slice.orca_failed": ("slicing", False, None,
                          "Try another orientation or other print settings, and slice again."),
    "slice.no_output": ("slicing", True, None, SERVER_REMEDY),
    "slice.unreadable_output": ("slicing", True, None, SERVER_REMEDY),
    "slice.no_gcode": ("slicing", True, None, SERVER_REMEDY),
    "slice.left_off_plate": ("slicing", False, "arrange",
                             "Move every instance fully onto the plate, or press Arrange, and slice again."),
    "slice.output_unwritable": ("saving", False, None,
                                "Ask a mentor to check that the print server can write to its output folder, "
                                "then slice again."),
    "slice.unknown_job": ("fetching", False, None,
                          "Send the slice again."),
    "slice.not_ready": ("fetching", True, None,
                        "Wait for the slice to finish, then fetch the sliced file."),
    "slice.file_gone": ("fetching", False, None,
                        "Send the slice again."),
    "slice.bad_request": ("fetching", False, None,
                          "Ask a mentor to check the program that sent this request; the print server does not "
                          "offer it."),
    "slice.unexpected": ("slicing", False, None, SERVER_REMEDY),
}

# The slice service's own exceptions: each carries message, details, error_code and where.
_OWN = (PlateConfigurationRefused, MeshError, ProfileError, OverrideError, SliceError, SliceCancelled)


def report_for_code(code, message, detail="", where=None):
    """The error report for `code` with its sentence and evidence (the HTTP interface's own)."""
    return _report(code, message, detail, where)


def _report(code, message, detail="", where=None, remedy=None, no_action=False):
    stage, retryable, action, default_remedy = CODES[code]
    report = {"code": code, "message": message, "where": dict(where or {}, stage=stage),
              "remedy": remedy or default_remedy, "retryable": retryable, "detail": detail}
    if action and not no_action:
        report["action"] = action
    return report


def error_report(exc):
    """The error report for an exception the slice service raised. A SliceError may carry
    its own remedy and drop the code's action (plate_configuration.run_plate_configuration
    sets them)."""
    if isinstance(exc, SliceError):
        detail = f"orca code {exc.code}\n{exc.details}" if exc.code is not None else exc.details
        return _report(exc.error_code, exc.message, detail, exc.where, exc.remedy, exc.no_action)
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
    return _report("slice.unexpected", GENERIC_FAILURE, exception_text(exc))
