"""The slice service's entry point: a plate job in, a sliced file out.

read_plate_job checks a plate job (contracts/plate-job.md) in a fixed order and refuses it
at the first failure, before anything reaches Orca:

1. the fields of every part and copy (BAD_JOB_MESSAGE);
2. at most MAX_COPIES copies;
3. every copy's `ref` names a part of the plate job whose STL file exists, and every such
   STL file reads as a part (mesh.py: binary, finite, not too detailed, not too small);
4. the copies' triangles, summed, at most MAX_JOB_TRIANGLES;
5. the profiles and the overrides (print_config.py);
6. the placement against the chosen printer's plate (plate.check_placement).

slice_plate_job then slices it in a scratch directory inside the output directory, renames
the sliced file (contracts/sliced-file.md) to `<out>/<delivered name>`, and removes the
scratch directory whatever happens.
"""
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import limits
from .mesh import MeshError, orientation_footprints, read_binary_stl
from .plate import ORIENTATIONS, check_placement, copy_labels, plate_from_printer
from .plate_3mf import delivered_file_name
from .plate_job import JobPart, PlateJob, run_plate_job
from .print_config import choose_profiles, printer_profile, validate_overrides
from .slicer import SliceError

# The plate job's fields, as contracts/plate-job.md lists them. tests/test_contracts.py
# compares these with the document's tables.
PLATE_JOB_FIELDS = ("parts", "copies", "printer", "filament", "process", "overrides", "local_time")
PART_FIELDS = ("name", "stl")
COPY_FIELDS = ("ref", "orientation", "angle", "x", "y")
# The sliced file's summary, as contracts/sliced-file.md lists it.
SUMMARY_FIELDS = ("file", "copies", "print_time_s", "filament_m", "filament_g", "layer_count", "warnings")

PART_KEY_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}\Z')        # \Z: no trailing newline, unlike $

# The sentences of a refused plate job. The limits' sentences come from limits.py.
BAD_JOB_MESSAGE = "This request could not be read."
PART_NOT_LISTED_MESSAGE = "A copy on the plate names a part this request does not include."
PART_FILE_MISSING_MESSAGE = "The file for {name} is missing."
PART_FILE_UNOPENABLE_MESSAGE = "The file for {name} could not be opened."
OUTPUT_UNWRITABLE_MESSAGE = "The print server could not save the sliced file."
PLACEMENT_CODES = {"off_plate": "slice.placement_off_plate", "too_tall": "slice.placement_too_tall",
                   "too_close": "slice.placement_too_close"}


class PlateJobRefused(Exception):
    """A plate job refused before slicing. `message` is one sentence for the student,
    `details` the evidence for the log, `rule` the placement rule (off_plate, too_tall,
    too_close) when the placement failed, `where` the part and copy when known,
    `error_code` the error report's code."""

    def __init__(self, message, details="", rule=None, where=None, error_code="slice.bad_plate_job"):
        super().__init__(message)
        self.message = message
        self.details = details
        self.rule = rule
        self.where = where or {}
        self.error_code = error_code


@dataclass
class SlicedFile:
    path: Path
    summary: dict


def _is_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:       # an integer too large for a float, such as 10**400
        return False


def _valid_copy(copy):
    return (isinstance(copy, dict) and isinstance(copy.get("ref"), str)
            and PART_KEY_RE.fullmatch(copy["ref"]) is not None
            and copy.get("orientation") in ORIENTATIONS
            and isinstance(copy.get("angle"), int) and not isinstance(copy["angle"], bool)
            and 0 <= copy["angle"] <= 359
            and _is_number(copy.get("x")) and _is_number(copy.get("y")))


def _valid_part(key, part):
    return (isinstance(key, str) and PART_KEY_RE.fullmatch(key) is not None and isinstance(part, dict)
            and isinstance(part.get("name"), str) and part["name"] != ""
            and isinstance(part.get("stl"), str) and part["stl"] != "")


def _refuse_fields(data):
    """Step 1: BAD_JOB_MESSAGE with what was wrong, or None."""
    if not isinstance(data, dict):
        return "the plate job is not a JSON object"
    copies, parts = data.get("copies"), data.get("parts")
    if not isinstance(copies, list) or not copies:
        return "copies is not a non-empty list"
    for i, copy in enumerate(copies):
        if not _valid_copy(copy):
            return f"copy {i} is not {{ref, orientation, angle, x, y}} with valid values: {copy!r}"[:300]
    if not isinstance(parts, dict):
        return "parts is not an object"
    for key, part in parts.items():
        if not _valid_part(key, part):
            return f"part {key!r} is not {{name, stl}} with a valid key: {part!r}"[:300]
    return None


def _read_part(key, part, base_dir):
    """Step 3 for one part: its JobPart, or a refusal."""
    name = part["name"]
    path = Path(part["stl"])
    if not path.is_absolute():
        path = Path(base_dir) / path
    if not path.is_file():
        raise PlateJobRefused(PART_FILE_MISSING_MESSAGE.format(name=name), f"part {key!r}: no STL file at {path}",
                              where={"part": name}, error_code="slice.part_missing")
    try:
        size = path.stat().st_size
        if size > limits.MAX_PART_BYTES:
            raise MeshError(limits.TOO_DETAILED_MESSAGE.format(name=name),
                            f"{path}: {size:,} bytes, cap {limits.MAX_PART_BYTES:,}", "slice.part_too_detailed",
                            {"part": name})
        data = path.read_bytes()
    except OSError as exc:
        raise PlateJobRefused(PART_FILE_UNOPENABLE_MESSAGE.format(name=name), f"part {key!r}: {exc}",
                              where={"part": name}, error_code="slice.part_unreadable") from None
    mesh = read_binary_stl(data, name, source=str(path))
    return JobPart(name=part["name"], stl_path=path, footprints=orientation_footprints(mesh),
                   triangles=mesh.triangles)


def read_plate_job(data, base_dir):
    """The PlateJob for a plate job's JSON value; relative STL paths are read against
    `base_dir`. Raises PlateJobRefused, MeshError, ProfileError or OverrideError."""
    problem = _refuse_fields(data)
    if problem:
        raise PlateJobRefused(BAD_JOB_MESSAGE, problem)
    copies = data["copies"]
    if len(copies) > limits.MAX_COPIES:
        raise PlateJobRefused(limits.TOO_MANY_COPIES_MESSAGE, f"{len(copies)} copies, cap {limits.MAX_COPIES}",
                              error_code="slice.too_many_copies")
    copies = [{key: c[key] for key in COPY_FIELDS} for c in copies]
    parts = data["parts"]
    entries = {}
    for i, c in enumerate(copies):
        if c["ref"] in entries:
            continue
        if c["ref"] not in parts:
            raise PlateJobRefused(PART_NOT_LISTED_MESSAGE, f"copy {i} names part {c['ref']!r}, which parts does not list",
                                  error_code="slice.part_missing")
        entries[c["ref"]] = _read_part(c["ref"], parts[c["ref"]], base_dir)
    triangles = sum(entries[c["ref"]].triangles for c in copies)
    if triangles > limits.MAX_JOB_TRIANGLES:
        raise PlateJobRefused(limits.JOB_TRIANGLES_MESSAGE,
                              f"{triangles:,} triangles over {len(copies)} copies, cap {limits.MAX_JOB_TRIANGLES:,}",
                              error_code="slice.job_too_detailed")
    filament, process = data.get("filament"), data.get("process")
    profiles = choose_profiles(data.get("printer"), filament, process)
    overrides = validate_overrides(data.get("overrides"))
    plate = plate_from_printer(printer_profile(profiles))
    placed = {ref: {"name": e.name, "footprints": e.footprints} for ref, e in entries.items()}
    problems = check_placement(copies, placed, plate)
    if problems:
        first = problems[0]
        labels = copy_labels([placed[c["ref"]]["name"] for c in copies])
        index = first["copies"][0]
        raise PlateJobRefused(first["message"], "; ".join(p["message"] for p in problems), rule=first["rule"],
                              where={"part": placed[copies[index]["ref"]]["name"], "copy": labels[index]},
                              error_code=PLACEMENT_CODES[first["rule"]])
    return PlateJob(copies=copies, parts=entries, profiles=profiles, overrides=overrides,
                    filament=filament, process=process,
                    delivered_name=delivered_file_name([e.name for e in entries.values()], data.get("local_time")))


def _load(plate_job, base_dir):
    """(JSON value, base directory) for a path to a plate job file or a JSON value."""
    if isinstance(plate_job, (str, Path)):
        path = Path(plate_job)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PlateJobRefused(BAD_JOB_MESSAGE, f"{path}: {exc}") from None
        return data, Path(base_dir) if base_dir is not None else path.resolve().parent
    return plate_job, Path(base_dir) if base_dir is not None else Path.cwd()


def _unwritable(exc):
    return SliceError(OUTPUT_UNWRITABLE_MESSAGE, str(exc), error_code="slice.output_unwritable")


def slice_plate_job(plate_job, out_dir, *, base_dir=None):
    """Slice a plate job and return its SlicedFile: the sliced file at
    `<out_dir>/<delivered name>` and its summary.

    `plate_job` is a path to a plate job file, whose STL paths are read against the file's
    own directory, or the plate job's JSON value, whose STL paths are read against
    `base_dir` (default: the current directory). Raises PlateJobRefused, MeshError,
    ProfileError, OverrideError, SliceError, or RuntimeError when Orca is not installed;
    errors.error_report turns any of them into an error report."""
    data, base = _load(plate_job, base_dir)
    job = read_plate_job(data, base)
    out_dir = Path(out_dir).resolve()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix="slice-", dir=out_dir))
    except OSError as exc:
        raise _unwritable(exc) from None
    final = out_dir / job.delivered_name
    try:
        result = run_plate_job(job, scratch)
        try:
            # The scratch folder is inside out_dir, so this is a rename on one file system:
            # it replaces a file of the same name and fails on a folder of that name, so
            # `final` is always the sliced file itself.
            os.replace(result.output_path, final)
        except OSError as exc:
            raise _unwritable(exc) from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    summary = {"file": job.delivered_name, "copies": len(job.copies), **result.summary()}
    return SlicedFile(path=final, summary=summary)
