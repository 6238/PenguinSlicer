"""The slice service's core: a part in, checked and kept; a plate configuration in, a sliced
file out.

The HTTP interface (web.py) is the slice service's one interface; this module is the code
it, and the tests, call.

**A part on arrival** (check_part, upload_part): the part's bytes, in its units, are read and
examined once, when it is uploaded by itself, before any plate names it (mesh.py: binary,
finite, not too detailed, not too small, a surface that encloses something), scaled to
millimetres by its units first, and tested against the largest printer of the profile
catalog (largest_plate). A part that passes is kept in the part store (part_store.py) with
what the checks found. An upload carries no part name, so its sentences say "This part".

**A plate configuration** (contracts/plate-configuration.md, "To be built": the phase 2
form) is checked by read_plate_configuration in a fixed order, refused at the first failure,
before anything reaches Orca:

1. the fields of the plate configuration, every part and every instance, and no field that
   is not listed (BAD_CONFIGURATION_MESSAGE): `plate_id` and `submission_id`, each part's
   `sha256` and `units`, each instance's one of `orientation` and `rotation`;
2. at most MAX_INSTANCES instances, using at most MAX_PARTS different parts;
3. the profiles and the overrides (print_config.py);
4. every instance's `ref` names a part of the plate configuration, and every part it names
   is in the part store under the request's user key, its hash and its units, else one
   refusal lists every missing part (`missing_parts`); each part then fits the chosen
   printer in some orientation;
5. the placement against the chosen printer's plate (plate.check_placement), each instance
   turned by its orientation or its rotation.

The memory model's estimate (limits.estimate_peak_mb) refuses nothing: it goes into the
log. Memory is guarded while Orca runs, by the watchdog at limits.max_peak_mb().

A part that passes with a finding that does not stop the slice (holes in its surface, a
surface facing inwards, a size that looks like inches) carries a warning: on its upload's
record without a name, and naming the part in the answer to a plate configuration and in
the sliced file's summary (part_warnings).

slice_plate_configuration then slices a checked plate configuration in a scratch directory
inside the output directory, renames the sliced file (contracts/sliced-file.md) to
`<out>/<delivered name>`, and removes the scratch directory whatever happens. Scratch
directories are named after the process that made them, so clean_stale_scratch can remove
those of a process that died.
"""
import functools
import hashlib
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
from .mesh import MeshError, health_warnings, orientation_footprints, read_binary_stl, turned_footprint
from .part_store import UNITS
from .plate import (MARGIN_MM, ORIENTATIONS, TOO_CLOSE_SUPPORTS_REMEDY, check_placement, instance_labels,
                    plate_from_printer, quaternion_matrix)
from .plate_3mf import delivered_file_name
from .plate_configuration import CheckedPart, PlateConfiguration, run_plate_configuration
from .print_config import (ProfileError, choose_profiles, load_catalog, printer_profile, supports_on,
                           validate_overrides)
from .slicer import DEFAULT_PROFILES, SliceError

# The plate configuration's fields, as contracts/plate-configuration.md lists them in "Fields
# in phase 2", "A part in phase 2" and "An instance in phase 2". tests/test_contracts.py
# compares these with the document's tables.
PLATE_CONFIGURATION_FIELDS = ("plate_id", "submission_id", "parts", "instances", "printer", "filament", "process",
                              "overrides", "local_time")
PART_FIELDS = ("name", "sha256", "units")
INSTANCE_FIELDS = ("ref", "orientation", "rotation", "angle", "x", "y")
# The sliced file's summary, as contracts/sliced-file.md lists it.
SUMMARY_FIELDS = ("file", "instances", "print_time_s", "filament_m", "filament_g", "layer_count", "warnings",
                  "part_warnings")

PART_KEY_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}\Z')        # \Z: no trailing newline, unlike $
ID_RE = PART_KEY_RE                                          # a plate_id or a submission_id: the same form
SHA256_RE = re.compile(r'^[0-9a-f]{64}\Z')
ROTATION_TOLERANCE = 1e-6       # a rotation's length may differ from 1 by this much
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
# An upload carries no part name: its sentences name "this part" (capitalised where it
# starts one), as contracts/wizard-front-server.md's part record does.
UPLOAD_NAME = "this part"
UPLOAD_SOURCE = "upload"
# The remedy of every code POST /parts can answer. A part refused on arrival was never added,
# so its remedy is about adding it on the Parts step (slice/README.md, "When things go wrong":
# export the part again, simplify it, check its units), never about a slice; and its report
# carries no action. errors.CODES keeps the slice's remedies for the same codes.
UPLOAD_REMEDIES = {
    "slice.no_user_key": "Try again; if it happens again, the server needs fixing.",
    "slice.bad_units": "Choose millimetres or inches for the part and add it again.",
    "slice.bad_request": "Add the part again; if it happens again, the server needs fixing.",
    "slice.part_too_detailed": "Export the part with a coarser tessellation, or simplify it, and add it again.",
    "slice.part_unreadable": "Export the part again as an STL and add it again.",
    "slice.part_not_binary": "Export the part again as a binary STL and add it again.",
    "slice.part_too_small": "Check the part's units and size, and add it again.",
    "slice.part_no_volume": "Make the part a closed solid in CAD, export it again and add it again.",
    "slice.part_too_large": "Check the part's units, or split the part in CAD so each piece fits, and add the pieces.",
    "slice.scratch_unwritable": ("Add the part again in a few minutes; if it fails again, the server needs more free "
                                 "disk space."),
    "slice.profile_unreadable": "Add the part again later; if it fails again, the server needs fixing.",
    "slice.unexpected": "Add the part again; if it fails again, the server needs fixing.",
}
UPLOAD_PROFILE_UNREADABLE_MESSAGE = "The slicer could not read its printer settings, so it could not check this part."

# The sentences of a refused plate configuration. The limits' sentences come from limits.py.
BAD_CONFIGURATION_MESSAGE = "This plate configuration could not be read: {problem}."
PART_NOT_LISTED_MESSAGE = "An instance on the plate names a part this plate configuration does not include."
PARTS_MISSING_MESSAGE = "The slicer no longer has {count} of this plate's parts."
PART_MISSING_MESSAGE = "The slicer no longer has one of this plate's parts."
PARTS_MISSING_REMEDY = "Add the parts again and slice again."
OUTPUT_UNWRITABLE_MESSAGE = "The print server could not save the sliced file."
PROFILE_UNREADABLE_MESSAGE = "The print server's settings for this printer could not be read."
PLACEMENT_CODES = {"off_plate": "slice.placement_off_plate", "too_tall": "slice.placement_too_tall",
                   "too_close": "slice.placement_too_close"}


class PlateConfigurationRefused(Exception):
    """A plate configuration refused before slicing. `message` is one sentence for the
    user, `details` the evidence for the log, `rule` the placement rule (off_plate,
    too_tall, too_close) when the placement failed, `where` the part and instance when
    known (or the parts missing from the part store), `error_code` the error report's code."""

    def __init__(self, message, details="", rule=None, where=None, error_code="slice.bad_plate_configuration",
                 remedy=None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.rule = rule
        self.where = where or {}
        self.error_code = error_code
        self.remedy = remedy            # when set, replaces the code's remedy (errors.CODES)


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


def _rotation_problem(i, rotation):
    if not (isinstance(rotation, list) and len(rotation) == 4 and all(_is_number(v) for v in rotation)):
        return f"instance {i} has a rotation that is not a list of 4 finite numbers (got {_short(rotation)})"
    length = math.sqrt(sum(float(v) * float(v) for v in rotation))
    if abs(length - 1) > ROTATION_TOLERANCE:
        return f"instance {i} has a rotation of length {length:.9g}, not a unit quaternion (within " \
               f"{ROTATION_TOLERANCE:g} of 1)"
    return None


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
    if ("orientation" in instance) == ("rotation" in instance):
        return f"instance {i} has {'both' if 'orientation' in instance else 'neither'} an orientation and a rotation, " \
               f"not exactly one"
    if "rotation" in instance:
        problem = _rotation_problem(i, instance["rotation"])
        if problem:
            return problem
    elif instance["orientation"] not in ORIENTATIONS:
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
    if not (isinstance(part.get("name"), str) and part["name"] != ""):
        return f"part {key!r} has no name (got {_short(part.get('name'))})"
    if len(part["name"]) > MAX_PART_NAME_CHARS:
        return f"part {key!r} has a name of {len(part['name']):,} characters, longer than the " \
               f"{MAX_PART_NAME_CHARS} a part name may have"
    if not (isinstance(part.get("sha256"), str) and SHA256_RE.fullmatch(part["sha256"])):
        return f"part {key!r} has no sha256 of 64 lowercase hexadecimal characters (got {_short(part.get('sha256'))})"
    if part.get("units") not in UNITS:
        return f"part {key!r} has units that are not \"mm\" or \"in\" (got {_short(part.get('units'))})"
    return None


def _refuse_fields(data):
    """Step 1: what is wrong with the fields, in words a user can act on, or None."""
    if not isinstance(data, dict):
        return "it is not a JSON object"
    unknown = sorted(set(data) - set(PLATE_CONFIGURATION_FIELDS))
    if unknown:
        return f"it has fields this plate configuration format does not have: {', '.join(map(str, unknown))[:120]}"
    for name in ("plate_id", "submission_id"):
        value = data.get(name)
        if not (isinstance(value, str) and ID_RE.fullmatch(value)):
            return f"its {name} is not 1 to 64 letters, digits, - or _ (got {_short(value)})"
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


def _g(value):
    return f"{value:.4g}" if abs(value) < 1e6 else f"{value:.3g}"


def _size(health):
    return dict(zip("xyz", (_g(v) for v in health["size_mm"])))


def _plate_dims(plate):
    return {"px": round(plate["max"][0] - plate["min"][0], 1), "py": round(plate["max"][1] - plate["min"][1], 1),
            "pz": round(plate["height"], 1)}


def _server_profiles(fn):
    """fn(), with a profile file of the server's own that is missing or not a profile turned
    into slice.profile_unreadable."""
    try:
        return fn()
    except ProfileError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProfileError(PROFILE_UNREADABLE_MESSAGE, f"{type(exc).__name__}: {exc}"[:500],
                           error_code="slice.profile_unreadable") from None


@functools.lru_cache(maxsize=1)
def _largest_plate():
    catalog = load_catalog()
    paths = [DEFAULT_PROFILES.printer] + [catalog.profile_path("printer", name) for name in catalog.printer_names()]
    plates = [plate_from_printer(json.loads(Path(path).read_text(encoding="utf-8"))) for path in paths]
    width = max(p["max"][0] - p["min"][0] for p in plates)
    depth = max(p["max"][1] - p["min"][1] for p in plates)
    return {"min": [0.0, 0.0], "max": [width, depth], "height": max(p["height"] for p in plates),
            "margin": MARGIN_MM, "printer": "the largest printer of the profile catalog"}


def largest_plate():
    """The plate a part is tested against on arrival: the widest, deepest and tallest of the
    default printer and every printer of the profile catalog, so the fit test stays a
    necessary one (a part it refuses fits no printer)."""
    return _server_profiles(_largest_plate)


def _capitalised(text):
    return text[:1].upper() + text[1:]


def check_part(data, units):
    """The checks on a part when it arrives: its analysis for the part store
    ({footprints, health, triangles}), or a MeshError (ProfileError when the server's own
    printer profiles cannot be read). The part is read in its units, scaled to millimetres
    first; its sentences say "This part" and its report's `where` names nothing, since an
    upload carries no name. Its refusals carry UPLOAD_REMEDIES' remedy and no action."""
    try:
        plate = largest_plate()
    except ProfileError as exc:
        exc.message, exc.remedy, exc.no_action = UPLOAD_PROFILE_UNREADABLE_MESSAGE, UPLOAD_REMEDIES[exc.error_code], True
        raise
    try:
        mesh = read_binary_stl(data, UPLOAD_NAME, source=UPLOAD_SOURCE, scale=UNITS[units])
        footprints = orientation_footprints(mesh)
        if not _fits_somewhere(footprints, plate):
            raise MeshError(limits.PART_TOO_LARGE_ANY_PRINTER_MESSAGE.format(name=UPLOAD_NAME, **_size(mesh.health),
                                                                             **_plate_dims(plate)),
                            f"{UPLOAD_SOURCE}: {mesh.health['size_mm']} mm in {units}, against {plate['printer']} "
                            f"({plate['max'][0]} x {plate['max'][1]} x {plate['height']} mm)",
                            "slice.part_too_large")
    except MeshError as exc:
        exc.message, exc.where = _capitalised(exc.message), {}
        exc.remedy, exc.no_action = UPLOAD_REMEDIES[exc.error_code], True
        raise
    return {"footprints": footprints, "health": mesh.health, "triangles": mesh.triangles}


def part_record(entry):
    """The part's record (contracts/slice-http-interface.md, "POST /parts"): its hash, units,
    measurements and warnings, without `where`, since an upload carries no part name."""
    health = entry.analysis["health"]
    warnings = [{"code": w["code"], "message": _capitalised(w["message"]), "detail": w["detail"]}
                for w in health_warnings(health, UPLOAD_NAME, entry.units)]
    return {"sha256": entry.sha256, "units": entry.units,
            "measurements": {"triangles": entry.analysis["triangles"], "size_mm": list(health["size_mm"]),
                             "volume_mm3": health["volume_mm3"] if health["watertight"] else None},
            "warnings": warnings}


def upload_part(store, user_key, units, data):
    """Check one uploaded part and keep it in the part store: (its record, its StoredPart,
    whether it was new). The same bytes again under the same user key and units answer the
    same record and count as a use. Raises MeshError, ProfileError, or OSError when the part
    store cannot be written."""
    sha256 = hashlib.sha256(data).hexdigest()
    entry = store.get(user_key, sha256, units)
    if entry is not None:
        store.touch([entry])
        return part_record(entry), entry, False
    analysis = check_part(data, units)
    entry, new = store.put(user_key, units, sha256, data, analysis)     # not new when another upload was first
    return part_record(entry), entry, new


def _listed(problems):
    """The placement problems' sentences for a refusal's detail: at most MAX_LISTED_PROBLEMS."""
    listed = "; ".join(p["message"] for p in problems[:MAX_LISTED_PROBLEMS])
    if len(problems) > MAX_LISTED_PROBLEMS:
        listed += f"; and {len(problems) - MAX_LISTED_PROBLEMS:,} more"
    return listed


def parts_missing(missing):
    """The one refusal of a plate configuration whose parts the part store does not hold:
    `missing` is [{key, sha256, units}] in the order of the plate configuration's parts."""
    message = PART_MISSING_MESSAGE if len(missing) == 1 else PARTS_MISSING_MESSAGE.format(count=len(missing))
    detail = "missing from the part store: " + ", ".join(f"{m['sha256']} ({m['units']})" for m in missing)
    return PlateConfigurationRefused(message, detail, where={"missing_parts": [dict(m) for m in missing]},
                                     error_code="slice.part_missing", remedy=PARTS_MISSING_REMEDY)


def _checked_part(key, part, entry, plate):
    """Step 4 for one part found in the part store: its CheckedPart, or slice.part_too_large
    when it fits the plate's own printer in no orientation."""
    name, health = part["name"], entry.analysis["health"]
    footprints = dict(entry.analysis["footprints"])
    if not _fits_somewhere(footprints, plate):
        raise MeshError(limits.PART_TOO_LARGE_MESSAGE.format(name=name, **_size(health), **_plate_dims(plate)),
                        f"part {key!r} ({entry.sha256}, {entry.units}): {health['size_mm']} mm on printer "
                        f"{plate.get('printer')!r}", "slice.part_too_large", {"part": name})
    return CheckedPart(name=name, stl_path=entry.path, footprints=footprints, triangles=entry.analysis["triangles"],
                       health=health, warnings=health_warnings(health, name, entry.units), scale=UNITS[entry.units],
                       sha256=entry.sha256, units=entry.units)


def _place_rotations(instances, entries):
    """The footprint of each rotation an instance turns its part by, added to that part's
    footprints under the rotation (plate.turn_of). The part's file is read once, in its
    units; a file gone from the part store meanwhile makes the part missing."""
    meshes = {}
    for instance in instances:
        if "rotation" not in instance:
            continue
        ref, turn = instance["ref"], tuple(instance["rotation"])
        part = entries[ref]
        if turn in part.footprints:
            continue
        if ref not in meshes:
            try:
                data = part.stl_path.read_bytes()
            except OSError:
                raise parts_missing([{"key": ref, "sha256": part.sha256, "units": part.units}]) from None
            meshes[ref] = read_binary_stl(data, part.name, source=str(part.stl_path), scale=part.scale)
        part.footprints[turn] = turned_footprint(meshes[ref], quaternion_matrix(turn))


def _normalised(instance):
    """An instance's fields, its rotation divided by its length (contracts/plate-configuration.md)."""
    kept = {key: instance[key] for key in INSTANCE_FIELDS if key in instance}
    if "rotation" in kept:
        length = math.sqrt(sum(float(v) * float(v) for v in kept["rotation"]))
        kept["rotation"] = [float(v) / length for v in kept["rotation"]]
    return kept


def read_plate_configuration(data, find, environ=None):
    """The PlateConfiguration for a plate configuration's JSON value in its phase 2 form.
    `find(sha256, units)` is the part store's entry under the request's user key, or None.
    Raises PlateConfigurationRefused, MeshError, ProfileError or OverrideError."""
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
    instances = [_normalised(c) for c in instances]
    filament, process = data.get("filament"), data.get("process")
    overrides = validate_overrides(data.get("overrides"))

    def choose():
        profiles = choose_profiles(data.get("printer"), filament, process)
        supports = supports_on(profiles, overrides)
        return profiles, supports, plate_from_printer(printer_profile(profiles), supports)
    profiles, supports, plate = _server_profiles(choose)
    parts = data["parts"]
    for i, c in enumerate(instances):
        if c["ref"] not in parts:
            raise PlateConfigurationRefused(PART_NOT_LISTED_MESSAGE,
                                            f"instance {i} names part {c['ref']!r}, which parts does not list",
                                            error_code="slice.part_missing")
    found, missing = {}, []
    for key, part in parts.items():
        if key in used:
            found[key] = find(part["sha256"], part["units"])
            if found[key] is None:
                missing.append({"key": key, "sha256": part["sha256"], "units": part["units"]})
    if missing:
        raise parts_missing(missing)
    entries = {ref: _checked_part(ref, parts[ref], found[ref], plate) for ref in used}
    _place_rotations(instances, entries)
    volumes = [entries[c["ref"]].health["volume_mm3"] for c in instances]
    placed = {ref: {"name": e.name, "footprints": e.footprints} for ref, e in entries.items()}
    problems = check_placement(instances, placed, plate)
    labels = instance_labels([placed[c["ref"]]["name"] for c in instances])
    if problems:
        first = problems[0]
        index = first["instances"][0]
        where = {"part": placed[instances[index]["ref"]]["name"], "instance": labels[index]}
        remedy = None
        if first["rule"] == "too_close":
            where["other_instance"] = labels[first["instances"][1]]
            remedy = TOO_CLOSE_SUPPORTS_REMEDY if supports else None
        raise PlateConfigurationRefused(first["message"], _listed(problems), rule=first["rule"], where=where,
                                        error_code=PLACEMENT_CODES[first["rule"]], remedy=remedy)
    return PlateConfiguration(instances=instances, parts=entries, profiles=profiles, overrides=overrides,
                              filament=filament, process=process, printer=data.get("printer"), labels=labels,
                              supports_on=supports, estimated_peak_mb=limits.estimate_peak_mb(volumes, supports),
                              memory_ceiling_mb=limits.max_peak_mb(environ),
                              expected_s=limits.estimate_seconds(volumes, supports),
                              delivered_name=delivered_file_name([e.name for e in entries.values()],
                                                                 data.get("local_time")),
                              plate_id=data["plate_id"], submission_id=data["submission_id"],
                              stored={ref: found[ref] for ref in used})


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


def make_scratch(root, label=""):
    """A new scratch directory under `root`, named slice-<pid>-<start time>-<label><random>:
    clean_stale_scratch removes it once this process is gone."""
    return Path(tempfile.mkdtemp(prefix=f"{SCRATCH_PREFIX}{os.getpid()}-{_process_start(os.getpid())}-{label}",
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


def slice_plate_configuration(configuration, out_dir, *, stop=None, on_progress=None):
    """Slice a checked PlateConfiguration (read_plate_configuration) and return its
    SlicedFile: the sliced file at `<out_dir>/<delivered name>` and its summary. The HTTP
    interface's worker calls it. `stop` reaches the plate write (plate_3mf.write_plate_3mf)
    and the Orca run (slicer.run_process), `on_progress` the Orca run. Raises SliceError,
    SliceCancelled, or RuntimeError when Orca is not installed; errors.error_report turns
    any of them into an error report."""
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
