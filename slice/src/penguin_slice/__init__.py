"""The slice service: takes a plate job, runs Orca Slicer headless, returns a sliced file.

    from penguin_slice import slice_plate_job, error_report

    sliced = slice_plate_job("plate-job.json", "out/")
    sliced.path, sliced.summary

Every failure is an exception; error_report turns it into an error report. See
slice/README.md and contracts/plate-job.md, contracts/sliced-file.md.
"""
from .errors import error_report
from .service import PlateJobRefused, SlicedFile, read_plate_job, slice_plate_job

__all__ = ["PlateJobRefused", "SlicedFile", "error_report", "read_plate_job", "slice_plate_job"]
