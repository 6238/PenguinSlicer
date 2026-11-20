"""Run Orca Slicer's command line on an STL or a plate 3MF and read back what it wrote.

The one module that runs Orca and reads the files Orca writes: its return codes (one
table, ORCA_RETURN_CODES), result.json, and the sliced file's entries (the G-code header,
slice_info.config, plate_1.json). The Orca version is pinned in scripts/install-orca.sh
alone.

Orca is found at the path in the environment variable PENGUIN_SLICE_ORCA when it is set,
otherwise at slice/tools/orca/orca-slicer (installed by scripts/install-orca.sh); there is
no PATH lookup. The binary is looked for when a slice starts, not at import, so the fast
tests run without Orca. slice_stl (the sample part) uses the default set in profiles/;
slice_plate takes the SliceProfiles print_config.py chose: catalog profiles from
profiles/catalog/, or the default set.
"""
import json
import os
import re
import signal
import struct
import subprocess
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .limits import PLATE_SLICE_TIMEOUT_S

PKG = Path(__file__).resolve().parent      # the penguin_slice package directory
SLICE_ROOT = PKG.parents[1]                # the slice/ project directory (src layout)
ORCA_ENV = "PENGUIN_SLICE_ORCA"
DEFAULT_ORCA_BIN = SLICE_ROOT / "tools" / "orca" / "orca-slicer"
PROFILE_DIR = PKG / "profiles"
SAMPLE_STL = PKG / "sample_part.stl"
DEFAULT_TIMEOUT_S = 120
ARCHIVE_SUFFIX = ".gcode.3mf"
GCODE_ENTRY = "Metadata/plate_1.gcode"
SLICE_INFO_ENTRY = "Metadata/slice_info.config"
PLATE_JSON_ENTRY = "Metadata/plate_1.json"
RESULT_JSON = "result.json"
DETAIL_LINES = 20
GCODE_HEAD_BYTES = 4096       # enough for Orca's header block
BINARY_HEADER_BYTES = 84      # 80-byte comment plus a uint32 triangle count
BINARY_TRIANGLE_BYTES = 50    # 12 floats plus a uint16 attribute word
PLATE_ARCHIVE = "plate" + ARCHIVE_SUFFIX

SLICE_FAILED_MESSAGE = "The slicer could not process this part."
UNSTARTABLE_MESSAGE = "The slicer could not be started."
TIMEOUT_MESSAGE = "The slicer took too long on this part."
KILLED_MESSAGE = "The print server stopped the slicer before it finished."
NO_OUTPUT_MESSAGE = "The slicer produced no output file."
UNREADABLE_MESSAGE = "The slicer output could not be read."
NO_GCODE_MESSAGE = "The slicer output is missing its G-code."

# Orca's return codes for a plate it refused, observed with the pinned Orca and
# --arrange 0: return code -> (error code, sentence). The only table of them. A part
# entirely off the plate is not among them: Orca leaves it out silently, which
# plate_3mf.py's name guard catches. -100 is Orca's general slicing failure; its sentence
# is the earlier application's and is known to be untrue for most causes (hardening).
ORCA_RETURN_CODES = {
    -101: ("slice.orca_too_close", "Parts are too close together; spread them out."),
    -52: ("slice.crosses_edge", "A part crosses the edge of the plate."),
    -100: ("slice.empty_layers", "A part has no flat face on the plate; choose another Lay flat."),
    -50: ("slice.nothing_on_plate", "No part is fully on the plate."),
}
# Reading a damaged zip entry can fail in any of these ways.
_ZIP_READ_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, OSError, NotImplementedError)
# Orca gets only these variables from the caller's environment; anything else
# (tokens, client secrets) stays out of the subprocess. The wrapper
# tools/orca/orca-slicer sets APPDIR and LD_LIBRARY_PATH itself.
ENV_ALLOWLIST = ("PATH", "HOME", "TMPDIR", "LANG", "USER", "LOGNAME")


def orca_bin():
    """The Orca wrapper this process uses: PENGUIN_SLICE_ORCA, else slice/tools/orca."""
    configured = os.environ.get(ORCA_ENV)
    return Path(configured) if configured else DEFAULT_ORCA_BIN


def _require_binary():
    path = orca_bin()
    if not path.is_file():
        raise RuntimeError(f"Orca Slicer is missing at {path}; run `make install`")
    return path


class SliceError(Exception):
    """A slice that produced no usable archive.

    `message` is one sentence fit for the student; `details` is the last
    twenty lines of Orca's output (or the archive listing) for the server log;
    `code` is Orca's exit code (slice_stl) or its return code (slice_plate), "timeout",
    or None when Orca did not report one. `error_code` is the error report's code;
    `where` the part or copy, when known.
    """

    def __init__(self, message, details="", code=None, error_code="slice.orca_failed", where=None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.code = code
        self.error_code = error_code
        self.where = where or {}


@dataclass
class SliceResult:
    output_path: Path
    print_time_s: float | None
    filament_m: float | None
    filament_g: float | None
    layer_count: int | None
    warnings: list = field(default_factory=list)

    def summary(self):
        return {"print_time_s": self.print_time_s, "filament_m": self.filament_m,
                "filament_g": self.filament_g, "layer_count": self.layer_count,
                "warnings": list(self.warnings)}


@dataclass(frozen=True)
class SliceProfiles:
    printer: Path
    filament: Path
    process: Path


DEFAULT_PROFILES = SliceProfiles(PROFILE_DIR / "printer.json", PROFILE_DIR / "filament.json",
                                 PROFILE_DIR / "process.json")


def build_command(stl_path, output_dir):
    # Orca runs with cwd=output_dir, so every path handed to it must be
    # absolute: a relative one would be read against the wrong directory.
    stl_path = Path(stl_path).resolve()
    output_dir = Path(output_dir).resolve()
    archive_name = stl_path.stem + ARCHIVE_SUFFIX
    return [
        str(orca_bin()),
        "--datadir", str(output_dir / "datadir"),
        "--load-settings", f"{PROFILE_DIR / 'printer.json'};{PROFILE_DIR / 'process.json'}",
        "--load-filaments", str(PROFILE_DIR / "filament.json"),
        "--arrange", "1",
        "--slice", "0",
        "--export-3mf", archive_name,
        "--outputdir", str(output_dir),
        str(stl_path),
    ]


def build_plate_command(model_3mf, profiles, output_dir):
    """The plate's command: placement is the 3MF's, so Orca must neither arrange nor orient
    (leaving --arrange out arranges). Paths absolute, as in build_command."""
    model_3mf = Path(model_3mf).resolve()
    output_dir = Path(output_dir).resolve()
    return [
        str(orca_bin()),
        "--datadir", str(output_dir / "datadir"),
        "--load-settings", f"{Path(profiles.printer).resolve()};{Path(profiles.process).resolve()}",
        "--load-filaments", str(Path(profiles.filament).resolve()),
        "--arrange", "0",
        "--orient", "0",
        "--slice", "0",
        "--export-3mf", PLATE_ARCHIVE,
        "--outputdir", str(output_dir),
        str(model_3mf),
    ]


def _tail(text, n=DETAIL_LINES):
    return "\n".join(text.splitlines()[-n:])


def orca_env(output_dir):
    """Orca's environment: the allowlist, plus private XDG directories under output_dir."""
    output_dir = Path(output_dir)
    config_home = output_dir / "xdg-config"
    runtime_dir = output_dir / "xdg-runtime"
    config_home.mkdir(exist_ok=True)
    runtime_dir.mkdir(exist_ok=True)
    os.chmod(runtime_dir, 0o700)
    env = {name: os.environ[name] for name in ENV_ALLOWLIST if name in os.environ}
    env.update({"XDG_CONFIG_HOME": str(config_home), "XDG_RUNTIME_DIR": str(runtime_dir), "LC_ALL": "C"})
    return env


def _run_orca(cmd, output_dir, timeout_s):
    """Run Orca in output_dir with its private environment; the completed process and its
    combined output. Raises RuntimeError when the binary is missing, SliceError when Orca
    cannot start or runs out of time."""
    _require_binary()
    env = orca_env(output_dir)
    try:
        # Orca's output is not always UTF-8 (a part name, a path); undecodable bytes are
        # replaced rather than failing a slice that worked.
        proc = subprocess.run(cmd, env=env, cwd=str(output_dir), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout_s, stdin=subprocess.DEVNULL)
    except OSError as exc:
        # The wrapper is missing, not executable, or not this architecture.
        raise SliceError(UNSTARTABLE_MESSAGE, str(exc), error_code="slice.orca_unstartable") from None
    except subprocess.TimeoutExpired as exc:
        captured = exc.stdout or ""
        if isinstance(captured, bytes):
            captured = captured.decode(errors="replace")
        raise SliceError(TIMEOUT_MESSAGE, _tail(captured), code="timeout", error_code="slice.timeout") from None
    return proc, (proc.stdout or "") + (proc.stderr or "")


def _failure_details(exit_code, output, error_string=""):
    # The exit code leads, then Orca's own reason when it gave one, then the last lines of
    # output: `details` stays at DETAIL_LINES lines and the code is always visible.
    lead = [f"exit code {exit_code}"]
    if error_string:
        lead.append(f"orca error_string: {error_string}")
    return "\n".join(lead + [_tail(output, DETAIL_LINES - len(lead))])


def _killed(returncode, output):
    """The SliceError for an Orca the operating system stopped (a negative return code),
    for example the kernel's out-of-memory killer: not a fault of the part."""
    number = -returncode
    try:
        name = signal.Signals(number).name
    except ValueError:
        name = "unknown signal"
    return SliceError(KILLED_MESSAGE, f"killed by signal {number} ({name})\n" + _tail(output, DETAIL_LINES - 1),
                      error_code="slice.orca_killed")


def _result(archive, output_dir, output):
    if not archive.is_file():
        raise SliceError(NO_OUTPUT_MESSAGE, _tail(output), error_code="slice.no_output")
    return SliceResult(output_path=archive, **read_summary(archive, output_dir))


def slice_stl(stl_path, output_dir, timeout_s=DEFAULT_TIMEOUT_S):
    """Slice `stl_path` into `output_dir/<stem>.gcode.3mf` and return a SliceResult."""
    stl_path = Path(stl_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    proc, output = _run_orca(build_command(stl_path, output_dir), output_dir, timeout_s)
    if proc.returncode < 0:
        raise _killed(proc.returncode, output)
    if proc.returncode != 0:
        raise SliceError(SLICE_FAILED_MESSAGE, _failure_details(proc.returncode, output), code=proc.returncode)
    return _result(output_dir / (stl_path.stem + ARCHIVE_SUFFIX), output_dir, output)


def read_result_json(output_dir):
    """Orca's result.json in `output_dir` as a dict; {} when it is missing, unreadable or
    not a JSON object (Orca on macOS writes none)."""
    try:
        data = json.loads((Path(output_dir) / RESULT_JSON).read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def orca_return_code(output_dir, exit_code):
    """Orca's own return code: result.json's return_code, else the exit status read as a
    negative byte (exit 155 is -101), else None."""
    code = read_result_json(output_dir).get("return_code")
    if isinstance(code, int) and not isinstance(code, bool) and code != 0:
        return code
    if exit_code > 127:
        return exit_code - 256
    return None


def orca_error_string(output_dir):
    """Orca's own words for a failure, from result.json's error_string; "" when none."""
    text = read_result_json(output_dir).get("error_string")
    return text.strip() if isinstance(text, str) else ""


def slice_plate(model_3mf, profiles, output_dir, timeout_s=PLATE_SLICE_TIMEOUT_S):
    """Slice a plate 3MF (plate_3mf.py) into `output_dir/plate.gcode.3mf` with the
    placement as written; return a SliceResult."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    proc, output = _run_orca(build_plate_command(model_3mf, profiles, output_dir), output_dir, timeout_s)
    if proc.returncode < 0:
        raise _killed(proc.returncode, output)
    if proc.returncode != 0:
        code = orca_return_code(output_dir, proc.returncode)
        error_code, message = ORCA_RETURN_CODES.get(code, ("slice.orca_failed", SLICE_FAILED_MESSAGE))
        details = _failure_details(proc.returncode, output, orca_error_string(output_dir))
        raise SliceError(message, details, code, error_code=error_code)
    return _result(output_dir / PLATE_ARCHIVE, output_dir, output)


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unreadable(archive_path, problem):
    return SliceError(UNREADABLE_MESSAGE, f"{Path(archive_path).name}: {problem}", error_code="slice.unreadable_output")


def _warnings(result):
    """Orca's warnings from result.json's sliced_plates, whatever shape the file has: a
    shape this code does not expect gives no warnings, never a failure."""
    plates = result.get("sliced_plates")
    if not isinstance(plates, list):
        return []
    texts = (plate.get("warning_message") for plate in plates if isinstance(plate, dict))
    return [text.strip() for text in texts if isinstance(text, str) and text.strip()]


def read_summary(archive_path, output_dir):
    """Read print time, filament and layer count from the archive and result.json."""
    archive_path = Path(archive_path)
    try:
        zf = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile:
        raise SliceError(UNREADABLE_MESSAGE, f"{archive_path.name} is not a zip archive",
                         error_code="slice.unreadable_output") from None
    with zf:
        names = zf.namelist()
        if GCODE_ENTRY not in names:
            raise SliceError(NO_GCODE_MESSAGE, "archive entries:\n" + "\n".join(names), error_code="slice.no_gcode")
        try:
            # A real plate's G-code runs to hundreds of megabytes; the header we
            # want is the first few lines, so decompress only that much of it.
            with zf.open(GCODE_ENTRY) as fh:
                gcode_head = fh.read(GCODE_HEAD_BYTES).decode("utf-8", errors="replace")
            info = zf.read(SLICE_INFO_ENTRY).decode("utf-8", errors="replace") if SLICE_INFO_ENTRY in names else ""
        except _ZIP_READ_ERRORS as exc:
            raise _unreadable(archive_path, repr(exc)) from None

    def meta(key):
        m = re.search(r'<metadata key="%s" value="([^"]*)"' % re.escape(key), info)
        return _float(m.group(1)) if m else None

    used_m = None
    m = re.search(r'<filament [^>]*used_m="([^"]*)"', info)
    if m:
        used_m = _float(m.group(1))
    layers = None
    m = re.search(r"^; total layer number: (\d+)", gcode_head, re.M)
    if m:
        layers = int(m.group(1))

    return {"print_time_s": meta("prediction"), "filament_g": meta("weight"),
            "filament_m": used_m, "layer_count": layers, "warnings": _warnings(read_result_json(output_dir))}


def plate_object_names(archive):
    """The object names Orca sliced onto plate 1, from the archive's Metadata/plate_1.json.
    Raises SliceError (slice.unreadable_output) when that entry cannot be read or its
    bbox_objects is not a list of objects."""
    try:
        with zipfile.ZipFile(archive) as zf:
            plate = json.loads(zf.read(PLATE_JSON_ENTRY).decode("utf-8"))
    except (KeyError, ValueError, *_ZIP_READ_ERRORS) as exc:
        raise SliceError(UNREADABLE_MESSAGE, f"{PLATE_JSON_ENTRY}: {exc!r}",
                         error_code="slice.unreadable_output") from None
    objects = plate.get("bbox_objects") if isinstance(plate, dict) else None
    if not isinstance(objects, list) or not all(isinstance(obj, dict) for obj in objects):
        raise SliceError(UNREADABLE_MESSAGE, f"{PLATE_JSON_ENTRY}: bbox_objects is not a list of objects: "
                                             f"{objects!r}"[:300], error_code="slice.unreadable_output")
    return [str(obj.get("name") or "") for obj in objects]


def _binary_triangle_count(data):
    """Triangle count if `data` is a binary STL, else None.

    A binary STL is exactly an 84-byte header plus 50 bytes per triangle. The
    leading word is not a reliable test: binary files written by some tools
    begin with "solid" too, so only the length decides.
    """
    if len(data) < BINARY_HEADER_BYTES:
        return None
    count = struct.unpack("<I", data[80:84])[0]
    if len(data) != BINARY_HEADER_BYTES + BINARY_TRIANGLE_BYTES * count:
        return None
    return count


def stl_bounds(data):
    """Return (min_corner, max_corner, triangle_count) of a binary or ASCII STL."""
    count = _binary_triangle_count(data)
    vertices = []
    if count is not None:
        for i in range(count):
            start = BINARY_HEADER_BYTES + i * BINARY_TRIANGLE_BYTES
            rec = struct.unpack("<12fH", data[start: start + BINARY_TRIANGLE_BYTES])
            vertices.extend((rec[3:6], rec[6:9], rec[9:12]))
    else:
        text = data.decode("utf-8", errors="replace")
        for m in re.finditer(r"vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", text):
            vertices.append(tuple(float(v) for v in m.groups()))
        count = len(vertices) // 3
    if not vertices:
        raise ValueError("STL has no triangles")
    lo = tuple(min(v[i] for v in vertices) for i in range(3))
    hi = tuple(max(v[i] for v in vertices) for i in range(3))
    return lo, hi, count


def _load_profile(name):
    with open(PROFILE_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def default_printer_profile():
    """The default printer profile (profiles/printer.json), the sample part's printer."""
    return _load_profile("printer.json")


def _bed_size(printer):
    corners = []
    for corner in printer.get("printable_area", []):
        x, y = corner.lower().split("x")
        corners.append((float(x), float(y)))
    if not corners:
        return {"x": None, "y": None}
    return {"x": max(c[0] for c in corners) - min(c[0] for c in corners),
            "y": max(c[1] for c in corners) - min(c[1] for c in corners)}


def part_info(stl_path=SAMPLE_STL):
    """Names and numbers for the sample part before slicing."""
    stl_path = Path(stl_path)
    lo, hi, count = stl_bounds(stl_path.read_bytes())
    printer = _load_profile("printer.json")
    filament = _load_profile("filament.json")
    process = _load_profile("process.json")
    return {
        "part": {"name": stl_path.stem, "file": stl_path.name,
                 "size_mm": {"x": round(hi[0] - lo[0], 3), "y": round(hi[1] - lo[1], 3), "z": round(hi[2] - lo[2], 3)},
                 "triangles": count},
        "printer": {"name": printer.get("name"), "bed_mm": _bed_size(printer),
                    "height_mm": _float(printer.get("printable_height"))},
        "filament": {"name": filament.get("name")},
        "process": {"name": process.get("name"), "layer_height_mm": _float(process.get("layer_height"))},
    }
