"""One plate job: the copies, the parts they use, the profiles, and running the slice.

service.py builds a PlateJob once the plate job has passed every check and calls
run_plate_job in the plate job's own scratch directory.
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
class JobPart:
    name: str
    stl_path: Path
    footprints: dict
    triangles: int
    health: dict = field(default_factory=dict)       # mesh.analyse
    warnings: list = field(default_factory=list)     # mesh.part_warnings


@dataclass
class PlateJob:
    """`profiles` are the chosen catalog (or default) files; `overrides` are Orca process
    keys from print_config.validate_overrides; `filament` and `process` are the names;
    `labels` the copies' names; `estimated_peak_mb` and `expected_s` the memory and time
    models' estimates (limits.py)."""
    copies: list[dict]
    parts: dict[str, JobPart]
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
    work_dir: Path | None = None        # the HTTP face's folder for this job's files

    def triangles(self):
        return sum(self.parts[copy['ref']].triangles for copy in self.copies)

    def part_warnings(self):
        """Every part's warnings, in the order the copies first use the parts."""
        return [warning for part in self.parts.values() for warning in part.warnings]

    def describe(self):
        """The plate job for the server log: profiles, overrides, parts and copies."""
        return {
            "printer": self.printer, "filament": self.filament, "process": self.process,
            "overrides": dict(self.overrides), "supports_on": self.supports_on,
            "estimated_peak_mb": self.estimated_peak_mb, "memory_ceiling_mb": self.memory_ceiling_mb,
            "expected_s": self.expected_s,
            "parts": {ref: {"name": p.name, "triangles": p.triangles, **{k: p.health.get(k) for k in (
                "size_mm", "volume_mm3", "volume_basis", "watertight", "shells", "open_edges")},
                "warnings": [w["code"] for w in p.warnings]} for ref, p in self.parts.items()},
            "copies": [{"name": label, **copy} for label, copy in zip(self.labels, self.copies)],
        }


ONE_COPY_MEMORY_REMEDY = "Split the part in CAD into smaller pieces, or simplify it, and slice again."
PART_REASONS = ("slice.no_layers", "slice.print_empty")


def _fit_to_plate(exc, job):
    """What Orca's failure can say about this plate that Orca did not: on a plate of one
    copy, out of memory cannot be helped by removing copies; with one part, Orca's reason
    for an empty print is that part's."""
    if exc.error_code == "slice.out_of_memory" and len(job.copies) == 1:
        exc.remedy, exc.no_action = ONE_COPY_MEMORY_REMEDY, True
    if exc.error_code in PART_REASONS and len(job.parts) == 1:
        exc.where = dict(exc.where, part=next(iter(job.parts.values())).name)


def run_plate_job(job, scratch, stop=None, on_progress=None):
    """Write the plate's 3MF and the job's process file (the chosen process with the
    overrides merged), slice and check that Orca sliced every copy. Returns the
    SliceResult; raises SliceError or SliceCancelled."""
    scratch = Path(scratch)
    report = on_progress or (lambda stage, fraction, message: None)
    report("building_plate", None, "Building the plate")
    model = scratch / MODEL_FILE
    parts = {ref: {'name': part.name, 'stl_path': part.stl_path, 'footprints': part.footprints}
             for ref, part in job.parts.items()}
    try:
        names = write_plate_3mf(model, job.copies, parts)
        process = write_process_with_overrides(job.profiles.process, job.overrides, scratch / PROCESS_FILE)
    except OSError as exc:
        # A full disk, or a scratch folder that cannot be written.
        raise SliceError(SCRATCH_UNWRITABLE_MESSAGE, f"{type(exc).__name__}: {exc}",
                         error_code="slice.scratch_unwritable") from None
    profiles = SliceProfiles(job.profiles.printer, job.profiles.filament, process)
    try:
        result = slice_plate(model, profiles, scratch / SLICE_DIR, stop=stop, on_progress=on_progress,
                             memory_ceiling_mb=job.memory_ceiling_mb)
    except SliceError as exc:
        _fit_to_plate(exc, job)
        raise
    report("reading_result", None, "Reading the sliced file")
    check_plate_names(names, plate_object_names(result.output_path))
    return result
