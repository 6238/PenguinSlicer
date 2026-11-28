"""One checked plate configuration (the instances, the parts they use, the profiles) and
its slice job's work on it: the plate 3MF, the Orca run and the name guard.

service.py builds a PlateConfiguration once the plate configuration has passed every check
and calls run_plate_configuration in the slice job's own scratch directory.
"""
from dataclasses import dataclass, field
from pathlib import Path

from . import limits
from .mesh import contact_area_mm2, read_binary_stl
from .plate import turn_matrix, turn_of
from .plate_3mf import check_plate_names, write_plate_3mf
from .print_config import write_process_with_overrides
from .slicer import SCRATCH_UNWRITABLE_MESSAGE, SliceError, SliceProfiles, plate_object_names, slice_plate

MODEL_FILE = "plate.3mf"
PROCESS_FILE = "process.json"
SLICE_DIR = "slice"


@dataclass
class CheckedPart:
    """One part of a plate configuration, as it passed the checks (service._checked_part).
    `stl_path` is its file in the part store, and once the slice job is accepted the slice
    job's own hold on it; `footprints` are under each turn its instances use
    (plate.turn_of); `scale` turns its units into millimetres."""
    name: str
    stl_path: Path
    footprints: dict
    triangles: int
    health: dict = field(default_factory=dict)       # mesh.analyse
    warnings: list = field(default_factory=list)     # mesh.part_warnings
    scale: float = 1.0
    sha256: str | None = None
    units: str = "mm"


@dataclass
class PlateConfiguration:
    """`profiles` are the chosen catalog (or default) files; `overrides` are Orca process
    keys from print_config.validate_overrides; `filament` and `process` are the names;
    `labels` the instances' names; `estimated_peak_mb` and `expected_s` the memory and time
    models' estimates (limits.py)."""
    instances: list[dict]
    parts: dict[str, CheckedPart]
    profiles: SliceProfiles
    overrides: dict[str, str]
    filament: str | None
    process: str | None
    delivered_name: str
    printer: str | None = None
    labels: list = field(default_factory=list)
    supports_on: bool = False
    estimated_peak_mb: int | None = None
    expected_s: float | None = None
    memory_ceiling_mb: int | None = None  # the watchdog's ceiling; None: limits.max_peak_mb()
    work_dir: Path | None = None        # the HTTP interface's folder for this slice job's files
    plate_id: str | None = None
    submission_id: str | None = None
    stored: dict = field(default_factory=dict)     # ref -> its part_store.StoredPart

    def triangles(self):
        return sum(self.parts[instance['ref']].triangles for instance in self.instances)

    def part_warnings(self):
        """Every part's warnings, in the order the instances first use the parts."""
        return [warning for part in self.parts.values() for warning in part.warnings]

    def describe(self):
        """The plate configuration for the server log: profiles, overrides, parts and instances."""
        return {
            "plate_id": self.plate_id, "submission_id": self.submission_id,
            "printer": self.printer, "filament": self.filament, "process": self.process,
            "overrides": dict(self.overrides), "supports_on": self.supports_on,
            "estimated_peak_mb": self.estimated_peak_mb, "memory_ceiling_mb": self.memory_ceiling_mb,
            "expected_s": self.expected_s,
            "parts": {ref: {"name": p.name, "sha256": p.sha256, "units": p.units, "triangles": p.triangles,
                            **{k: p.health.get(k) for k in (
                "size_mm", "volume_mm3", "volume_basis", "watertight", "shells", "open_edges")},
                "warnings": [w["code"] for w in p.warnings]} for ref, p in self.parts.items()},
            "instances": [{"name": label, **instance} for label, instance in zip(self.labels, self.instances)],
        }


ONE_INSTANCE_MEMORY_REMEDY = "Split the part in CAD into smaller pieces, or simplify it, and slice again."
ONE_INSTANCE_TIMEOUT_REMEDY = "Try again; if it is too slow again, simplify the part or split it in CAD."
PART_REASONS = ("slice.no_layers", "slice.print_empty")
REST_AREA_MM2 = 0.01          # an instance whose faces on the plate add up to less rests on no face
REST_MESSAGE = ("{label} touches the plate only along an edge or at a point, so the slicer can give it no first "
                "layer.")
REST_REMEDY = "Lay the part on one of its own flat faces, or turn on supports with a raft, and slice again."
REST_REMEDY_SUPPORTS = "Lay the part on one of its own flat faces, or add a raft, and slice again."


def _fit_to_plate(exc, configuration):
    """What Orca's failure can say about this plate that Orca did not: on a plate of one
    instance, out of memory, a sliced file too large or a timeout cannot be helped by
    removing instances; with one
    part, Orca's reason for an empty print is that part's."""
    if len(configuration.instances) == 1:
        if exc.error_code in ("slice.out_of_memory", "slice.output_too_large"):
            exc.remedy, exc.no_action = ONE_INSTANCE_MEMORY_REMEDY, True
        elif exc.error_code == "slice.timeout":
            exc.remedy, exc.no_action = ONE_INSTANCE_TIMEOUT_REMEDY, True
    if exc.error_code in PART_REASONS and len(configuration.parts) == 1:
        exc.where = dict(exc.where, part=next(iter(configuration.parts.values())).name)
    if exc.error_code == "slice.orca_failed" and exc.code == -100:
        _explain_an_edge(exc, configuration)


def resting_on_no_face(configuration):
    """The labels of the instances that touch the plate only along an edge or at a point
    (mesh.contact_area_mm2 under REST_AREA_MM2), in the order of the instances."""
    meshes, areas, labels = {}, {}, []
    for label, instance in zip(configuration.labels, configuration.instances):
        part = configuration.parts[instance['ref']]
        if instance['ref'] not in meshes:
            meshes[instance['ref']] = read_binary_stl(part.stl_path.read_bytes(), part.name, scale=part.scale)
        turn = (instance['ref'], turn_of(instance))
        if turn not in areas:
            areas[turn] = contact_area_mm2(meshes[instance['ref']], turn_matrix(turn[1]))
        if areas[turn] < REST_AREA_MM2:
            labels.append(label)
    return labels


def _explain_an_edge(exc, configuration):
    """Orca's general failure, when an instance rests on no face of its own: the pinned Orca
    then finds its first layer empty ("One object has an empty first layer and can't be
    printed", a reason it writes to no file) and refuses the plate, with supports off and on;
    with supports and a raft it slices. A part that cannot be read again leaves Orca's
    general failure as it is."""
    try:
        labels = resting_on_no_face(configuration)
    except Exception:          # noqa: BLE001 - the explanation is a help, never a new failure
        return
    if not labels:
        return
    exc.error_code = "slice.rests_on_an_edge"
    exc.message = REST_MESSAGE.format(label=labels[0])
    exc.where = dict(exc.where, instance=labels[0])
    exc.remedy = REST_REMEDY_SUPPORTS if configuration.supports_on else REST_REMEDY
    exc.details = f"resting on no face of its own: {', '.join(labels)}\n{exc.details}"


def run_plate_configuration(configuration, scratch, stop=None, on_progress=None):
    """Write the plate's 3MF and the slice job's process file (the chosen process with the
    overrides merged), slice and check that Orca sliced every instance. Returns the
    SliceResult; raises SliceError or SliceCancelled."""
    scratch = Path(scratch)
    report = on_progress or (lambda stage, fraction, message: None)
    report("building_plate", None, "Building the plate")
    model = scratch / MODEL_FILE
    parts = {ref: {'name': part.name, 'stl_path': part.stl_path, 'footprints': part.footprints, 'scale': part.scale}
             for ref, part in configuration.parts.items()}
    try:
        names = write_plate_3mf(model, configuration.instances, parts, stop=stop)
        process = write_process_with_overrides(configuration.profiles.process, configuration.overrides,
                                               scratch / PROCESS_FILE)
    except OSError as exc:
        # A full disk, or a scratch folder that cannot be written.
        raise SliceError(SCRATCH_UNWRITABLE_MESSAGE, f"{type(exc).__name__}: {exc}",
                         error_code="slice.scratch_unwritable") from None
    profiles = SliceProfiles(configuration.profiles.printer, configuration.profiles.filament, process)
    try:
        result = slice_plate(model, profiles, scratch / SLICE_DIR, stop=stop, on_progress=on_progress,
                             memory_ceiling_mb=configuration.memory_ceiling_mb)
    except SliceError as exc:
        _fit_to_plate(exc, configuration)
        raise
    report("reading_result", None, "Reading the sliced file")
    check_plate_names(names, plate_object_names(result.output_path))
    try:
        _check_size(result.output_path)
    except SliceError as exc:
        _fit_to_plate(exc, configuration)
        raise
    return result


def _check_size(path):
    """The third guard after a good slice: a sliced file is at most limits.MAX_SLICED_FILE_BYTES."""
    size, cap = Path(path).stat().st_size, limits.MAX_SLICED_FILE_BYTES
    if size > cap:
        raise SliceError(limits.OUTPUT_TOO_LARGE_MESSAGE,
                         f"{Path(path).name}: {size:,} bytes, over the limit of {cap:,} bytes",
                         error_code="slice.output_too_large")
