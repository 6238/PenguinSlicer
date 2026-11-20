"""The slice service's core: a plate configuration in, a sliced file out.

The HTTP interface (web.py) is the slice service's one interface; this module is the code
it, and the tests, call. read_plate_configuration checks a plate configuration
(contracts/plate-configuration.md) in a fixed order and refuses it at the first failure,
before anything reaches Orca:

1. the fields of the plate configuration, every part and every instance, and no field that
   is not listed (BAD_CONFIGURATION_MESSAGE);
2. at most MAX_INSTANCES instances, using at most MAX_PARTS different parts;
3. the profiles and the overrides (print_config.py);
4. every instance's `ref` names a part of the plate configuration whose STL file exists
   (inside `confine_to` when one is given), and every such STL file reads as a part
   (mesh.py: binary, finite, not too detailed, not too small, a surface that encloses
   something), and fits the chosen printer in some orientation;
5. the placement against the chosen printer's plate (plate.check_placement).

The memory model's estimate (limits.estimate_peak_mb) refuses nothing: it goes into the
log. Memory is guarded while Orca runs, by the watchdog at limits.max_peak_mb().

A part that passes with a finding that does not stop the slice (holes in its surface, a
surface facing inwards, a size that looks like inches) carries a warning, which travels in
the sliced file's summary as part_warnings.

slice_plate_configuration then slices it in a scratch directory inside the output
directory, renames the sliced file (contracts/sliced-file.md) to `<out>/<delivered name>`,
and removes the scratch directory whatever happens. Scratch directories are named after the
process that made them, so clean_stale_scratch can remove those of a process that died.
"""
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import limits
from .mesh import MeshError, orientation_footprints, part_size_mm, part_warnings, read_binary_stl
from .plate import ORIENTATIONS, check_placement, instance_labels, plate_from_printer
from .plate_3mf import delivered_file_name
from .plate_configuration import CheckedPart, PlateConfiguration, run_plate_configuration
from .print_config import ProfileError, choose_profiles, printer_profile, supports_on, validate_overrides
from .slicer import SliceError

# The plate configuration's fields, as contracts/plate-configuration.md lists them.
# tests/test_contracts.py compares these with the document's tables.
PLATE_CONFIGURATION_FIELDS = ("parts", "instances", "printer", "filament", "process", "overrides", "local_time")
PART_FIELDS = ("name", "stl")
INSTANCE_FIELDS = ("ref", "orientation", "angle", "x", "y")
# The sliced file's summary, as contracts/sliced-file.md lists it.
SUMMARY_FIELDS = ("file", "instances", "print_time_s", "filament_m", "filament_g", "layer_count", "warnings",
                  "part_warnings")

PART_KEY_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}\Z')        # \Z: no trailing newline, unlike $
MAX_STL_PATH_CHARS = 1024     # a part's stl: a path no file system here refuses for its length
MAX_FILE_NAME_BYTES = 255     # each piece of that path (Linux NAME_MAX)
# A part's name, and a profile's: generous for any real name (Onshape's and Orca's run to
# tens of characters), so no sentence, detail or log line grows with what a caller sends.
MAX_PART_NAME_CHARS = 200
MAX_PROFILE_NAME_CHARS = 200
PROFILE_FIELDS = ("printer", "filament", "process")
# The placement problems a refusal's detail lists, at most: 100 instances on one spot are
# 4,950 pairs too close, and no detail or log line grows with what a caller sends.
MAX_LISTED_PROBLEMS = 20
SCRATCH_PREFIX = "slice-"
_SCRATCH_RE = re.compile(r'^slice-(\d+)-(\d+)-')

# The sentences of a refused plate configuration. The limits' sentences come from limits.py.
BAD_CONFIGURATION_MESSAGE = "This plate configuration could not be read: {problem}."
PART_NOT_LISTED_MESSAGE = "An instance on the plate names a part this plate configuration does not include."
PART_FILE_MISSING_MESSAGE = "The file for {name} is missing."
PART_FILE_UNOPENABLE_MESSAGE = "The file for {name} could not be opened."
PART_FILE_OUTSIDE_MESSAGE = "The file for {name} is not one of the files sent with this plate configuration."
OUTPUT_UNWRITABLE_MESSAGE = "The print server could not save the sliced file."
PROFILE_UNREADABLE_MESSAGE = "The print server's settings for this printer could not be read."
PLACEMENT_CODES = {"off_plate": "slice.placement_off_plate", "too_tall": "slice.placement_too_tall",
                   "too_close": "slice.placement_too_close"}


class PlateConfigurationRefused(Exception):
    """A plate configuration refused before slicing. `message` is one sentence for the
    student, `details` the evidence for the log, `rule` the placement rule (off_plate,
    too_tall, too_close) when the placement failed, `where` the part and instance when
    known, `error_code` the error report's code."""

    def __init__(self, message, details="", rule=None, where=None, error_code="slice.bad_plate_configuration"):
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
    peak_rss_kb: int | None = None
    wall_s: float | None = None
    memory_note: str | None = None      # slicer.SliceResult.memory_note: the peak passed the ceiling
    stop_note: str | None = None        # slicer.SliceResult.stop_note: a stop reached Orca after the file was complete


def _is_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:       # an integer too large for a float, such as 10**400
        return False


def _short(value):
    try:
        return repr(value)[:120]
    except RecursionError:
        return "a value nested too deeply"


def _instance_problem(i, instance):
    if not isinstance(instance, dict):
        return f"instance {i} is not an object"
    unknown = sorted(set(instance) - set(INSTANCE_FIELDS))
    if unknown:
        return f"instance {i} has fields this plate configuration format does not have: " \
               f"{', '.join(map(str, unknown))[:120]}"
    ref = instance.get("ref")
    if not (isinstance(ref, str) and PART_KEY_RE.fullmatch(ref)):
        return f"instance {i} has no valid ref (got {_short(ref)})"
    if instance.get("orientation") not in ORIENTATIONS:
        return f"instance {i} has an orientation that is not one of {', '.join(ORIENTATIONS)} " \
               f"(got {_short(instance.get('orientation'))})"
    angle = instance.get("angle")
    if not (isinstance(angle, int) and not isinstance(angle, bool) and 0 <= angle <= 359):
        return f"instance {i} has an angle that is not a whole number from 0 to 359 (got {_short(angle)})"
    for axis in ("x", "y"):
        if not _is_number(instance.get(axis)):
            return f"instance {i} has a position {axis} that is not a finite number " \
                   f"(got {_short(instance.get(axis))})"
    return None


def _part_problem(key, part):
    if not (isinstance(key, str) and PART_KEY_RE.fullmatch(key)):
        return f"part key {_short(key)} is not 1 to 64 letters, digits, - or _"
    if not isinstance(part, dict):
        return f"part {key!r} is not an object"
    unknown = sorted(set(part) - set(PART_FIELDS))
    if unknown:
        return f"part {key!r} has fields this plate configuration format does not have: " \
               f"{', '.join(map(str, unknown))[:120]}"
    for name in PART_FIELDS:
        if not (isinstance(part.get(name), str) and part[name] != ""):
            return f"part {key!r} has no {name} (got {_short(part.get(name))})"
    if len(part["name"]) > MAX_PART_NAME_CHARS:
        return f"part {key!r} has a name of {len(part['name']):,} characters, longer than the " \
               f"{MAX_PART_NAME_CHARS} a part name may have"
    stl = part["stl"]
    if "\0" in stl or len(stl) > MAX_STL_PATH_CHARS or \
            any(len(piece.encode("utf-8", "surrogatepass")) > MAX_FILE_NAME_BYTES for piece in stl.split("/")):
        return f"part {key!r} has an stl that is not a usable file name (got {_short(stl)})"
    return None


def _refuse_fields(data):
    """Step 1: what is wrong with the fields, in words a student can act on, or None."""
    if not isinstance(data, dict):
        return "it is not a JSON object"
    unknown = sorted(set(data) - set(PLATE_CONFIGURATION_FIELDS))
    if unknown:
        return f"it has fields this plate configuration format does not have: {', '.join(map(str, unknown))[:120]}"
    for name in PROFILE_FIELDS:
        value = data.get(name)
        if isinstance(value, str) and len(value) > MAX_PROFILE_NAME_CHARS:
            return f"its {name} is a name of {len(value):,} characters, longer than the {MAX_PROFILE_NAME_CHARS} " \
                   f"a profile name may have"
    instances, parts = data.get("instances"), data.get("parts")
    if not isinstance(instances, list) or not instances:
        return "it has no instances"
    for i, instance in enumerate(instances):
        problem = _instance_problem(i, instance)
        if problem:
            return problem
    if not isinstance(parts, dict):
        return "its parts are not an object"
    for key, part in parts.items():
        problem = _part_problem(key, part)
        if problem:
            return problem
    return None


def _min_width(hull):
    """The convex hull's least width over every direction (rotating calipers), and its diameter."""
    points = np.asarray(hull, dtype=np.float64)
    if len(points) < 3:
        return 0.0, float(np.ptp(points, axis=0).max()) if len(points) else 0.0
    best = math.inf
    for a, b in zip(points, np.roll(points, -1, axis=0)):
        edge = b - a
        length = math.hypot(*edge)
        if length > 0:
            rel = points - a
            best = min(best, float(np.abs(edge[0] * rel[:, 1] - edge[1] * rel[:, 0]).max() / length))
    diameter = float(np.sqrt(((points[:, None, :] - points[None, :, :]) ** 2).sum(-1)).max())
    return best, diameter


def _fits_somewhere(footprints, plate):
    """Whether the part could stand on the plate in some orientation at some angle: a
    necessary test (its least width fits the plate's short side, its diameter the diagonal,
    its height the printable height), so a part it refuses can truly fit nowhere."""
    width = plate["max"][0] - plate["min"][0] - 2 * plate["margin"]
    depth = plate["max"][1] - plate["min"][1] - 2 * plate["margin"]
    for footprint in footprints.values():
        least, diameter = _min_width(footprint["hull"])
        if (footprint["height"] <= plate["height"] + 1e-6 and least <= min(width, depth) + 1e-6
                and diameter <= math.hypot(width, depth) + 1e-6):
            return True
    return False


def _stl_path(key, part, base_dir, confine_to):
    name = part["name"]
    path = Path(part["stl"])
    if not path.is_absolute():
        path = Path(base_dir) / path
    if confine_to is not None:
        root = Path(confine_to).resolve()
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            raise PlateConfigurationRefused(PART_FILE_OUTSIDE_MESSAGE.format(name=name),
                                            f"part {key!r}: {part['stl']!r} resolves outside {root}",
                                            where={"part": name}, error_code="slice.part_missing")
        path = resolved
    return path


def _read_part(key, part, base_dir, plate, confine_to=None):
    """Step 4 for one part: its CheckedPart, or a refusal."""
    name = part["name"]
    path = _stl_path(key, part, base_dir, confine_to)
    if not path.is_file():
        raise PlateConfigurationRefused(PART_FILE_MISSING_MESSAGE.format(name=name),
                                        f"part {key!r}: no STL file at {path}",
                                        where={"part": name}, error_code="slice.part_missing")
    try:
        size = path.stat().st_size
        if size > limits.MAX_PART_BYTES:
            raise MeshError(limits.TOO_DETAILED_MESSAGE.format(name=name),
                            f"{path}: {size:,} bytes, cap {limits.MAX_PART_BYTES:,}", "slice.part_too_detailed",
                            {"part": name})
        data = path.read_bytes()
    except OSError as exc:
        raise PlateConfigurationRefused(PART_FILE_UNOPENABLE_MESSAGE.format(name=name), f"part {key!r}: {exc}",
                                        where={"part": name}, error_code="slice.part_unreadable") from None
    mesh = read_binary_stl(data, name, source=str(path))
    footprints = orientation_footprints(mesh)
    if not _fits_somewhere(footprints, plate):
        size_mm = part_size_mm(mesh)
        px, py = (round(plate["max"][i] - plate["min"][i], 1) for i in (0, 1))
        raise MeshError(limits.PART_TOO_LARGE_MESSAGE.format(name=name, px=px, py=py, pz=round(plate["height"], 1),
                                                             x=_g(size_mm["x"]), y=_g(size_mm["y"]),
                                                             z=_g(size_mm["z"])),
                        f"{path}: {size_mm} mm on printer {plate.get('printer')!r}", "slice.part_too_large",
                        {"part": name})
    return CheckedPart(name=name, stl_path=path, footprints=footprints, triangles=mesh.triangles, health=mesh.health,
                   warnings=part_warnings(mesh, name))


def _g(value):
    return f"{value:.4g}" if abs(value) < 1e6 else f"{value:.3g}"


def _listed(problems):
    """The placement problems' sentences for a refusal's detail: at most MAX_LISTED_PROBLEMS."""
    listed = "; ".join(p["message"] for p in problems[:MAX_LISTED_PROBLEMS])
    if len(problems) > MAX_LISTED_PROBLEMS:
        listed += f"; and {len(problems) - MAX_LISTED_PROBLEMS:,} more"
    return listed


def read_plate_configuration(data, base_dir, confine_to=None, environ=None):
    """The PlateConfiguration for a plate configuration's JSON value; relative STL paths are
    read against `base_dir`, and must stay inside `confine_to` when it is given. Raises
    PlateConfigurationRefused, MeshError, ProfileError or OverrideError."""
    problem = _refuse_fields(data)
    if problem:
        raise PlateConfigurationRefused(BAD_CONFIGURATION_MESSAGE.format(problem=problem), problem)
    instances = data["instances"]
    if len(instances) > limits.MAX_INSTANCES:
        raise PlateConfigurationRefused(limits.TOO_MANY_INSTANCES_MESSAGE.format(count=len(instances)),
                                        f"{len(instances)} instances, cap {limits.MAX_INSTANCES}",
                                        error_code="slice.too_many_instances")
    used = list(dict.fromkeys(instance["ref"] for instance in instances))
    if len(used) > limits.MAX_PARTS:
        raise PlateConfigurationRefused(limits.TOO_MANY_PARTS_MESSAGE.format(count=len(used)),
                                        f"{len(used)} different parts, cap {limits.MAX_PARTS}",
                                        error_code="slice.too_many_parts")
    instances = [{key: c[key] for key in INSTANCE_FIELDS} for c in instances]
    filament, process = data.get("filament"), data.get("process")
    overrides = validate_overrides(data.get("overrides"))
    try:
        profiles = choose_profiles(data.get("printer"), filament, process)
        plate = plate_from_printer(printer_profile(profiles))
        supports = supports_on(profiles, overrides)
    except ProfileError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # A profile file of the server's own that is missing or not a profile.
        raise ProfileError(PROFILE_UNREADABLE_MESSAGE, f"{type(exc).__name__}: {exc}"[:500],
                           error_code="slice.profile_unreadable") from None
    parts = data["parts"]
    entries = {}
    for i, c in enumerate(instances):
        if c["ref"] in entries:
            continue
        if c["ref"] not in parts:
            raise PlateConfigurationRefused(PART_NOT_LISTED_MESSAGE,
                                            f"instance {i} names part {c['ref']!r}, which parts does not list",
                                            error_code="slice.part_missing")
        entries[c["ref"]] = _read_part(c["ref"], parts[c["ref"]], base_dir, plate, confine_to)
    volumes = [entries[c["ref"]].health["volume_mm3"] for c in instances]
    placed = {ref: {"name": e.name, "footprints": e.footprints} for ref, e in entries.items()}
    problems = check_placement(instances, placed, plate)
    labels = instance_labels([placed[c["ref"]]["name"] for c in instances])
    if problems:
        first = problems[0]
        index = first["instances"][0]
        raise PlateConfigurationRefused(first["message"], _listed(problems), rule=first["rule"],
                                        where={"part": placed[instances[index]["ref"]]["name"],
                                               "instance": labels[index]},
                                        error_code=PLACEMENT_CODES[first["rule"]])
    return PlateConfiguration(instances=instances, parts=entries, profiles=profiles, overrides=overrides,
                              filament=filament, process=process, printer=data.get("printer"), labels=labels,
                              supports_on=supports, estimated_peak_mb=limits.estimate_peak_mb(volumes, supports),
                              memory_ceiling_mb=limits.max_peak_mb(environ),
                              expected_s=limits.estimate_seconds(volumes, supports),
                              delivered_name=delivered_file_name([e.name for e in entries.values()],
                                                                 data.get("local_time")))


def load_plate_configuration(plate_configuration, base_dir=None):
    """(JSON value, base directory) for a path to a plate configuration file or a JSON value."""
    if isinstance(plate_configuration, (str, Path)):
        path = Path(plate_configuration)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as exc:
            # RecursionError: JSON nested more deeply than Python's parser can follow.
            problem = "it is not a readable JSON file"
            raise PlateConfigurationRefused(BAD_CONFIGURATION_MESSAGE.format(problem=problem),
                                            f"{path}: {type(exc).__name__}: {exc}"[:500]) from None
        return data, Path(base_dir) if base_dir is not None else path.resolve().parent
    return plate_configuration, Path(base_dir) if base_dir is not None else Path.cwd()


def _unwritable(exc):
    return SliceError(OUTPUT_UNWRITABLE_MESSAGE, f"{type(exc).__name__}: {exc}", error_code="slice.output_unwritable")


def _process_start(pid):
    """The process's start time in clock ticks since boot (Linux), 0 elsewhere, None when it
    is not running."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        if not Path("/proc/self/stat").exists():          # no /proc: ask the kernel instead
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return None
            except PermissionError:
                return 0
            return 0
        return None
    except OSError:
        return None
    return int(stat.rsplit(")", 1)[1].split()[19])


def make_scratch(root):
    """A new scratch directory under `root`, named slice-<pid>-<start time>-<random>."""
    return Path(tempfile.mkdtemp(prefix=f"{SCRATCH_PREFIX}{os.getpid()}-{_process_start(os.getpid())}-",
                                 dir=root))


def clean_stale_scratch(root):
    """Remove the scratch directories under `root` left by a process that is no longer
    running (its pid gone, or reused by a process that started at another time). Returns
    the names removed."""
    removed = []
    try:
        entries = sorted(Path(root).iterdir())
    except OSError:
        return removed
    for entry in entries:
        match = _SCRATCH_RE.match(entry.name)
        if not match or not entry.is_dir():
            continue
        pid, started = int(match.group(1)), int(match.group(2))
        if _process_start(pid) != started:
            shutil.rmtree(entry, ignore_errors=True)
            removed.append(entry.name)
    return removed


def slice_plate_configuration(plate_configuration, out_dir, *, base_dir=None, configuration=None, stop=None,
                              on_progress=None):
    """Slice a plate configuration and return its SlicedFile: the sliced file at
    `<out_dir>/<delivered name>` and its summary. The HTTP interface's worker calls it.

    `plate_configuration` is a path to a plate configuration file, whose STL paths are read
    against the file's own directory, or the plate configuration's JSON value, whose STL
    paths are read against `base_dir` (default: the current directory). `configuration`,
    when given, is the PlateConfiguration read_plate_configuration already made for it.
    `stop` reaches the plate write (plate_3mf.write_plate_3mf) and the Orca run
    (slicer.run_process), `on_progress` the Orca run. Raises
    PlateConfigurationRefused, MeshError, ProfileError, OverrideError, SliceError,
    SliceCancelled, or RuntimeError when Orca is not installed; errors.error_report turns
    any of them into an error report."""
    if configuration is None:
        data, base = load_plate_configuration(plate_configuration, base_dir)
        configuration = read_plate_configuration(data, base)
    out_dir = Path(out_dir).resolve()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        clean_stale_scratch(out_dir)          # left by a process that died mid-slice
        scratch = make_scratch(out_dir)
    except OSError as exc:
        raise _unwritable(exc) from None
    final = out_dir / configuration.delivered_name
    try:
        result = run_plate_configuration(configuration, scratch, stop=stop, on_progress=on_progress)
        try:
            # The scratch folder is inside out_dir, so this is a rename on one file system:
            # it replaces a file of the same name and fails on a folder of that name, so
            # `final` is always the sliced file itself.
            os.replace(result.output_path, final)
        except OSError as exc:
            raise _unwritable(exc) from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    summary = {"file": configuration.delivered_name, "instances": len(configuration.instances), **result.summary(),
               "part_warnings": configuration.part_warnings()}
    return SlicedFile(path=final, summary=summary, peak_rss_kb=result.peak_rss_kb, wall_s=result.wall_s,
                      memory_note=result.memory_note, stop_note=result.stop_note)
