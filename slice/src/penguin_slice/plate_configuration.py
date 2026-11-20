"""One checked plate configuration (the instances, the parts they use, the profiles) and
its slice job's work on it: the plate 3MF, the Orca run and the name guard.

service.py builds a PlateConfiguration once the plate configuration has passed every check
and calls run_plate_configuration in the slice job's own scratch directory.
"""
from dataclasses import dataclass, field
from pathlib import Path

from .plate_3mf import check_plate_names, write_plate_3mf
from .print_config import write_process_with_overrides
from .slicer import SCRATCH_UNWRITABLE_MESSAGE, SliceError, SliceProfiles, plate_object_names, slice_plate

MODEL_FILE = "plate.3mf"
PROCESS_FILE = "process.json"
SLICE_DIR = "slice"


@dataclass
class CheckedPart:
    """One part of a plate configuration, as it passed the checks (service._read_part)."""
    name: str
    stl_path: Path
    footprints: dict
    triangles: int
    health: dict = field(default_factory=dict)       # mesh.analyse
    warnings: list = field(default_factory=list)     # mesh.part_warnings


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

    def triangles(self):
        return sum(self.parts[instance['ref']].triangles for instance in self.instances)

    def part_warnings(self):
        """Every part's warnings, in the order the instances first use the parts."""
        return [warning for part in self.parts.values() for warning in part.warnings]

    def describe(self):
        """The plate configuration for the server log: profiles, overrides, parts and instances."""
        return {
            "printer": self.printer, "filament": self.filament, "process": self.process,
            "overrides": dict(self.overrides), "supports_on": self.supports_on,
            "estimated_peak_mb": self.estimated_peak_mb, "memory_ceiling_mb": self.memory_ceiling_mb,
            "expected_s": self.expected_s,
            "parts": {ref: {"name": p.name, "triangles": p.triangles, **{k: p.health.get(k) for k in (
                "size_mm", "volume_mm3", "volume_basis", "watertight", "shells", "open_edges")},
                "warnings": [w["code"] for w in p.warnings]} for ref, p in self.parts.items()},
            "instances": [{"name": label, **instance} for label, instance in zip(self.labels, self.instances)],
        }


ONE_INSTANCE_MEMORY_REMEDY = "Split the part in CAD into smaller pieces, or simplify it, and slice again."
ONE_INSTANCE_TIMEOUT_REMEDY = "Try again; if it is too slow again, simplify the part or split it in CAD."
PART_REASONS = ("slice.no_layers", "slice.print_empty")


def _fit_to_plate(exc, configuration):
    """What Orca's failure can say about this plate that Orca did not: on a plate of one
    instance, out of memory or a timeout cannot be helped by removing instances; with one
    part, Orca's reason for an empty print is that part's."""
    if len(configuration.instances) == 1:
        if exc.error_code == "slice.out_of_memory":
            exc.remedy, exc.no_action = ONE_INSTANCE_MEMORY_REMEDY, True
        elif exc.error_code == "slice.timeout":
            exc.remedy, exc.no_action = ONE_INSTANCE_TIMEOUT_REMEDY, True
    if exc.error_code in PART_REASONS and len(configuration.parts) == 1:
        exc.where = dict(exc.where, part=next(iter(configuration.parts.values())).name)


def run_plate_configuration(configuration, scratch, stop=None, on_progress=None):
    """Write the plate's 3MF and the slice job's process file (the chosen process with the
    overrides merged), slice and check that Orca sliced every instance. Returns the
    SliceResult; raises SliceError or SliceCancelled."""
    scratch = Path(scratch)
    report = on_progress or (lambda stage, fraction, message: None)
    report("building_plate", None, "Building the plate")
    model = scratch / MODEL_FILE
    parts = {ref: {'name': part.name, 'stl_path': part.stl_path, 'footprints': part.footprints}
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
    return result
