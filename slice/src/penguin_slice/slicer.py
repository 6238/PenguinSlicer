"""Run Orca Slicer's command line on an STL or a plate 3MF and read back what it wrote.

The one module that runs Orca and reads the files Orca writes (the seam for upstream
changes): its command line, its return codes (one table, ORCA_RETURN_CODES), what it says
through --pipe while slicing (ORCA_STAGES), the reasons it gives in result.json, and the
sliced file's entries (the G-code header, slice_info.config, plate_1.json). The Orca
version is pinned in scripts/install-orca.sh alone.

Orca is found at the path in the environment variable PENGUIN_SLICE_ORCA when it is set,
otherwise at slice/tools/orca/orca-slicer (installed by scripts/install-orca.sh); there is
no PATH lookup. The binary is looked for when a slice starts, not at import, so the fast
tests run without Orca.

How Orca is run (run_process): in a session of its own, so it and every child it starts
form one process group; with stdout and stderr read as they arrive into a bounded tail,
never held whole; with its progress read from a FIFO given to --pipe; on Linux with
PR_SET_PDEATHSIG, so Orca dies with the thread that started it even when this process is
killed outright. A stop (a cancel, or the timeout) sends SIGTERM to the group, waits
`grace_s` for Orca to go, then sends SIGKILL; whatever is left of the group is killed once
Orca has exited, and Orca is reaped only after that, so the group id cannot be reused
under us. A stop counts only when Orca was still running at the moment it was to be
signalled (waitid with WNOHANG and WNOWAIT): one asked after Orca ended by itself is never
sent and never reported. Of two stops, the first asked is the one reported (Stop keeps it).

The memory watchdog (run_process's `memory_ceiling_kb`): while Orca runs, a thread samples
Orca's whole process group every MEMORY_SAMPLE_S (MEMORY_READER, from /proc), reading each
process's current resident memory and the kernel's high-water mark of it (VmHWM), so a
spike between two samples is seen at the next one. When the group's peak passes the
ceiling it stops Orca as a cancel does, with the reason "memory"; the slice then fails with
slice.out_of_memory and the measured peak in its detail. That, and a rise in the kernel's
out-of-memory kill count, are the only grounds on which a slice is reported out of memory
after a kill (besides Orca's own bad_alloc). The peak reported anywhere (OrcaExit.peak_kb)
is the higher of the watchdog's last high-water reading and the kernel's ru_maxrss of Orca
at exit (wait4), so it is never under the true peak of Orca itself.

A stop is reported only when it is what ended Orca. A run that was sent only SIGTERM but
ended on another signal (someone else's SIGKILL, a crash), or that was already ending when
the stop was asked (orca_dying: a zombie, exiting, writing a core file, or a fatal signal
pending), is reported by how it really ended; the stop is kept in OrcaExit.overtaken and
named only in the detail.

How a run ends is decided in one place, settle(): a complete sliced file (_result says
what complete means) is never discarded by a stop the slice service decides on itself. If
Orca exited 0, or was stopped for a timeout or by the watchdog, and its sliced file is
complete, the slice succeeds; a stop is then recorded in SliceResult.stop_note, and a peak
over the ceiling in SliceResult.memory_note. A cancel (the caller's, an abandoned job's, a
shutdown's) that ended Orca discards the file. Only then does a stop count, and only then
Orca's own failure.
"""
import collections
import ctypes
import json
import os
import re
import selectors
import signal
import struct
import subprocess
import sys
import threading
import time
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .limits import MAX_PEAK_MB_ENV, PLATE_SLICE_TIMEOUT_S, max_peak_mb

PKG = Path(__file__).resolve().parent      # the penguin_slice package directory
SLICE_ROOT = PKG.parents[1]                # the slice/ project directory (src layout)
ORCA_ENV = "PENGUIN_SLICE_ORCA"
DEFAULT_ORCA_BIN = SLICE_ROOT / "tools" / "orca" / "orca-slicer"
PROFILE_DIR = PKG / "profiles"
SAMPLE_STL = PKG / "sample_part.stl"
DEFAULT_TIMEOUT_S = 120
STOP_GRACE_S = 5.0            # SIGTERM to SIGKILL
TIMER = threading.Timer       # the timeout's timer; the fast suite replaces it
MEMORY_SAMPLE_S = 0.25        # the memory watchdog's cadence (it waits on Orca's exit, not a sleep)
MEMORY_STOP_REASON = "stopped at the memory ceiling"     # SliceError.reason of a watchdog stop
ARCHIVE_SUFFIX = ".gcode.3mf"
GCODE_ENTRY = "Metadata/plate_1.gcode"
SLICE_INFO_ENTRY = "Metadata/slice_info.config"
PLATE_JSON_ENTRY = "Metadata/plate_1.json"
PLATE_ENTRIES = (GCODE_ENTRY, PLATE_JSON_ENTRY)     # the entries a plate's sliced file must have
# The stops the slice service decides on itself: one that ends Orca after it wrote a
# complete sliced file does not discard the file. A cancel does.
KEEPING_STOPS = ("timeout", "memory")
RESULT_JSON = "result.json"
PROGRESS_FIFO = "orca-progress.fifo"
DETAIL_LINES = 20
TAIL_LINES = 200              # lines of Orca's output kept in memory while it runs
MAX_LINE_BYTES = 4096         # a longer line is cut; the rest of it is dropped
GCODE_HEAD_BYTES = 4096       # enough for Orca's header block
BINARY_HEADER_BYTES = 84      # 80-byte comment plus a uint32 triangle count
BINARY_TRIANGLE_BYTES = 50    # 12 floats plus a uint16 attribute word
PLATE_ARCHIVE = "plate" + ARCHIVE_SUFFIX

SLICE_FAILED_MESSAGE = "The slicer could not slice this plate."
UNSTARTABLE_MESSAGE = "The slicer could not be started."
TIMEOUT_MESSAGE = "The slicer took too long on this plate."
KILLED_MESSAGE = "Something on the print server stopped the slicer before it finished."
CRASHED_MESSAGE = "The slicer crashed while slicing this plate."
OUT_OF_MEMORY_MESSAGE = "This plate is too large to slice: the slicer ran out of memory."
MEMORY_CEILING_MESSAGE = ("This plate is too large to slice: the slicer needed more than the {ceiling_mb:,} MB "
                          "of memory the print server allows.")
NO_LAYERS_MESSAGE = ("The slicer found no layers to print: a part's surface may have holes, or a part may be "
                     "too thin to slice.")
PRINT_EMPTY_MESSAGE = ("The slicer found nothing it can print with these settings: a part may be thinner than "
                       "the nozzle can print.")
CANCELLED_MESSAGE = "The slice was cancelled."
SCRATCH_UNWRITABLE_MESSAGE = "The print server could not write the slicer's working files."
NO_OUTPUT_MESSAGE = "The slicer finished without writing the sliced file."
UNREADABLE_MESSAGE = "The sliced file the slicer wrote is damaged."
NO_GCODE_MESSAGE = "The sliced file the slicer wrote has no G-code in it."
EMPTY_LAYERS_MESSAGE = ("{copy} has nothing to print between {low} and {high} mm high, so the layers above "
                        "would start in mid-air.")
EMPTY_LAYERS_NO_COPY_MESSAGE = ("A part has nothing to print between {low} and {high} mm high, so the layers "
                                "above would start in mid-air.")

# Orca's return codes for a plate it refused, observed with the pinned Orca and
# --arrange 0: return code -> (error code, sentence). The only table of them. A part
# entirely off the plate is not among them: Orca leaves it out silently, which
# plate_3mf.py's name guard catches. -100 is Orca's general slicing failure: its sentence
# is chosen from Orca's reason (orca_failure), this entry is the fallback.
ORCA_RETURN_CODES = {
    -101: ("slice.orca_too_close", "Parts are too close together; spread them out."),
    -52: ("slice.crosses_edge", "A part crosses the edge of the plate."),
    -100: ("slice.orca_failed", SLICE_FAILED_MESSAGE),
    -50: ("slice.nothing_on_plate", "No part is fully on the plate."),
}
# Orca's reasons, as its result.json and log word them (pinned Orca).
EMPTY_LAYER_RE = re.compile(r"empty layer between (-?\d+(?:\.\d+)?) and (-?\d+(?:\.\d+)?)")
OBJECT_RE = re.compile(r"^Object: (.+)$", re.M)
# Words in Orca's output that mean an allocation failed (std::bad_alloc under RLIMIT_AS).
OUT_OF_MEMORY_RE = re.compile(r"bad_alloc|out of memory|Cannot allocate memory", re.I)
# Orca's own reasons on stdout for a plate with nothing to slice (return code -100, its
# result.json holding only the general error_string): reason -> (error code, sentence).
ORCA_OUTPUT_REASONS = (
    (re.compile(r"^No layers were detected\..*$", re.M), "slice.no_layers", NO_LAYERS_MESSAGE),
    (re.compile(r"^The print is empty\..*$", re.M), "slice.print_empty", PRINT_EMPTY_MESSAGE),
)
# Exit statuses of a program the shell or the loader could not start: 126 not executable,
# 127 not found or a shared library that cannot be loaded.
UNSTARTABLE_EXITS = (126, 127)
# Signals that mean Orca itself failed.
CRASH_SIGNALS = {signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS, signal.SIGFPE, signal.SIGILL, signal.SIGTRAP,
                 signal.SIGSYS}
# What Orca says through --pipe while it slices, observed with the pinned Orca: its
# message -> the slice service's stage. A message not listed keeps the current stage.
ORCA_STAGES = {
    "Start to load files": "loading",
    "Loading files finished": "loading",
    "Prepare slicing": "preparing",
    "Slicing begins": "slicing_mesh",
    "Slicing mesh": "slicing_mesh",
    "Generating walls": "generating_walls",
    "Generating infill regions": "generating_infill",
    "Generating infill toolpath": "generating_infill",
    "Checking support necessity": "generating_supports",
    "Generating support": "generating_supports",
    "Generating supports": "generating_supports",
    "Detect overhangs for auto-lift": "optimizing_toolpath",
    "Optimizing toolpath": "optimizing_toolpath",
    "Generating G-code": "generating_gcode",
    "Slicing finished": "exporting",
    "Generate thumbnails": "exporting",
    "Exporting 3mf": "exporting",
    "All done, Success": "exporting",
}
# Reading a damaged zip entry can fail in any of these ways.
_ZIP_READ_ERRORS = (zipfile.BadZipFile, zlib.error, EOFError, OSError, NotImplementedError)
# Orca gets only these variables from the caller's environment; anything else
# (tokens, client secrets) stays out of the subprocess. HOME is Orca's own, in the
# scratch folder. The wrapper tools/orca/orca-slicer sets APPDIR and LD_LIBRARY_PATH itself.
ENV_ALLOWLIST = ("PATH", "TMPDIR", "LANG", "USER", "LOGNAME")
_PR_SET_PDEATHSIG = 1


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

    `message` is one sentence fit for the student; `details` is the evidence for the
    server log (Orca's code and reason, the last lines it printed); `code` is Orca's exit
    code (slice_stl) or its return code (slice_plate), "timeout", or None when Orca did
    not report one. `error_code` is the error report's code; `where` the part, copy and
    height, when known. `reason` is Orca's own reason, for the log; `peak_rss_kb` and
    `wall_s` describe the Orca run, when there was one. `remedy`, when set, replaces the
    code's remedy, and `no_action` drops its action (a plate of one copy cannot lose one)."""

    def __init__(self, message, details="", code=None, error_code="slice.orca_failed", where=None, reason="",
                 run=None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.code = code
        self.error_code = error_code
        self.where = where or {}
        self.reason = reason
        self.peak_rss_kb = run.peak_kb if run else None
        self.wall_s = run.wall_s if run else None
        self.remedy = None
        self.no_action = False


class SliceCancelled(Exception):
    """The slice was cancelled and Orca is gone."""

    error_code = "slice.cancelled"

    def __init__(self, details=""):
        super().__init__(CANCELLED_MESSAGE)
        self.message = CANCELLED_MESSAGE
        self.details = details
        self.where = {}


@dataclass
class SliceResult:
    output_path: Path
    print_time_s: float | None
    filament_m: float | None
    filament_g: float | None
    layer_count: int | None
    warnings: list = field(default_factory=list)
    peak_rss_kb: int | None = None
    wall_s: float | None = None
    memory_note: str | None = None      # set when Orca's peak passed the ceiling and it finished first
    stop_note: str | None = None        # set when a stop reached Orca after its sliced file was complete

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


class Stop:
    """A request to stop a running Orca: set() by a cancel, the timer or the watchdog, read
    by run_process. The first reason set is kept: a later set() wakes the listeners again
    but never changes what is reported."""

    def __init__(self):
        self._lock = threading.Lock()
        self._listeners = []
        self.reason = None

    def set(self, reason="cancel"):
        with self._lock:
            if self.reason is None:
                self.reason = reason
            listeners = list(self._listeners)
        for listener in listeners:
            listener()

    def is_set(self):
        return self.reason is not None

    def listen(self, listener):
        with self._lock:
            self._listeners.append(listener)
            already = self.reason is not None
        if already:
            listener()


@dataclass
class OrcaExit:
    """How an Orca run ended. `returncode` is Popen's (negative: the signal); `stopped` is
    "cancel", "timeout" or "memory" (the watchdog) when the slice service stopped it;
    `escalated` when SIGTERM was not enough; `output` the tail of what it printed;
    `peak_rss_kb` the kernel's ru_maxrss of Orca at exit; `memory_peak_kb` the highest peak
    of Orca's process group the watchdog read (the sum of its processes' high-water marks),
    and `memory_ceiling_kb` its ceiling, when it ran. `overtaken` is the reason of a stop
    that was asked and sent but is not what ended Orca (then `stopped` is None), with
    `overtaken_dying` when Orca was already ending as it was asked."""
    returncode: int
    output: str
    stopped: str | None = None
    escalated: bool = False
    peak_rss_kb: int | None = None
    wall_s: float | None = None
    oom_kills: int | None = None
    memory_peak_kb: int | None = None
    memory_ceiling_kb: int | None = None
    overtaken: str | None = None
    overtaken_dying: bool = False

    @property
    def peak_kb(self):
        """The peak memory reported for this run: the higher of the watchdog's reading and
        ru_maxrss, never under either; None when neither is known."""
        known = [kb for kb in (self.peak_rss_kb, self.memory_peak_kb) if kb is not None]
        return max(known) if known else None

    def over_ceiling(self):
        return self.memory_ceiling_kb is not None and (self.peak_kb or 0) > self.memory_ceiling_kb


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
        "--pipe", str(output_dir / PROGRESS_FIFO),
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
        "--pipe", str(output_dir / PROGRESS_FIFO),
        "--export-3mf", PLATE_ARCHIVE,
        "--outputdir", str(output_dir),
        str(model_3mf),
    ]


def _tail(text, n=DETAIL_LINES):
    return "\n".join(text.splitlines()[-n:])


def orca_env(output_dir):
    """Orca's environment: the allowlist, plus a private HOME and private XDG directories
    under output_dir (short names: Wayland's socket path must stay under 108 bytes)."""
    output_dir = Path(output_dir)
    home = output_dir / "home"
    config_home = output_dir / "xdg-config"
    runtime_dir = output_dir / "xdg-runtime"
    for directory in (home, config_home, runtime_dir):
        directory.mkdir(exist_ok=True)
    os.chmod(runtime_dir, 0o700)
    env = {name: os.environ[name] for name in ENV_ALLOWLIST if name in os.environ}
    env.update({"HOME": str(home), "XDG_CONFIG_HOME": str(config_home), "XDG_RUNTIME_DIR": str(runtime_dir),
                "LC_ALL": "C"})
    return env


def _child_setup():  # pragma: no cover  (runs in the forked child, which coverage does not see)
    """Runs in the child between fork and exec: die with the parent thread (Linux).
    tests/test_orca_runner.py's test_orca_does_not_outlive_a_service_that_is_killed
    fails without it."""
    _LIBC.prctl(_PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)


_LIBC = ctypes.CDLL(None, use_errno=True) if sys.platform.startswith("linux") else None


def _oom_kills():
    """The kernel's count of out-of-memory kills in this cgroup, or None when unknown."""
    try:
        text = Path("/sys/fs/cgroup/memory.events").read_text()
    except OSError:
        return None
    match = re.search(r"^oom_kill (\d+)$", text, re.M)
    return int(match.group(1)) if match else None


_STATUS_KB_RE = re.compile(rb"^(VmRSS|VmHWM):\s+(\d+) kB$", re.M)


def group_memory_kb(pgid, proc="/proc"):
    """(resident kB, high-water kB) of process group `pgid`: each summed over the group's
    processes from `proc`/<pid>/status (VmRSS, and VmHWM, the kernel's peak of VmRSS since
    the process started), the group found from `proc`/<pid>/stat. None when there is no
    such table. A process that exits while the table is read is skipped: any error reading
    its entry means it is gone."""
    try:
        entries = os.listdir(proc)
    except OSError:
        return None
    rss = hwm = 0
    for name in entries:
        if not name.isdigit():
            continue
        try:
            with open(os.path.join(proc, name, "stat"), "rb") as fh:
                fields = fh.read().rsplit(b")", 1)[-1].split()
            if int(fields[2]) != pgid:              # after the name: state, ppid, pgrp, ...
                continue
            with open(os.path.join(proc, name, "status"), "rb") as fh:
                values = dict(_STATUS_KB_RE.findall(fh.read()))
        except (OSError, ValueError, IndexError):
            continue
        rss += int(values.get(b"VmRSS", 0))
        hwm += int(values.get(b"VmHWM", values.get(b"VmRSS", 0)))
    return rss, hwm


MEMORY_READER = group_memory_kb   # the watchdog's reader; the fast suite injects one

_PF_EXITING = 0x4                 # the kernel's task flag for a process in exit (stat field 9)
# Signals whose default action does not end a process.
_HARMLESS_BY_DEFAULT = {signal.SIGCHLD, signal.SIGCONT, signal.SIGURG, signal.SIGWINCH, signal.SIGSTOP,
                        signal.SIGTSTP, signal.SIGTTIN, signal.SIGTTOU}
_STATUS_FIELD_RE = re.compile(rb"^(\w+):\s*(\S+)", re.M)


def orca_dying(pid, proc="/proc"):
    """Whether process `pid` is already ending: a zombie, in exit (PF_EXITING), writing a
    core file, or with a signal pending that will end it (SIGKILL, or one it neither
    handles, ignores nor blocks and whose default action ends a process; the kernel turns
    such a signal into a pending SIGKILL at once). Read from `proc`/<pid>/status, then
    `proc`/<pid>/stat; False when either cannot be read."""
    try:
        with open(os.path.join(proc, str(pid), "status"), "rb") as fh:
            status = dict(_STATUS_FIELD_RE.findall(fh.read()))
        with open(os.path.join(proc, str(pid), "stat"), "rb") as fh:
            fields = fh.read().rsplit(b")", 1)[-1].split()
        state, flags = fields[0], int(fields[6])          # after the name: state, ppid, ..., flags
        pending = int(status[b"SigPnd"], 16) | int(status[b"ShdPnd"], 16)
        handled = int(status[b"SigBlk"], 16) | int(status[b"SigIgn"], 16) | int(status[b"SigCgt"], 16)
    except (OSError, ValueError, IndexError, KeyError):
        return False
    if state in (b"Z", b"X", b"x") or flags & _PF_EXITING or status.get(b"CoreDumping") == b"1":
        return True
    if pending & (1 << (signal.SIGKILL - 1)):
        return True
    fatal = pending & ~handled
    return any(fatal & (1 << (number - 1)) and number not in _HARMLESS_BY_DEFAULT for number in range(1, 65))


DYING_PROBE = orca_dying          # the stop's probe of Orca's state; tests inject one


class _LineReader:
    """Splits a byte stream into lines, cutting any line at MAX_LINE_BYTES."""

    def __init__(self, on_line):
        self._buffer = b""
        self._dropping = False
        self._on_line = on_line

    def feed(self, chunk):
        data = self._buffer + chunk
        lines = data.split(b"\n")
        self._buffer = lines.pop()
        for line in lines:
            if self._dropping:
                self._dropping = False
                continue
            self._emit(line)
        if len(self._buffer) > MAX_LINE_BYTES:
            if not self._dropping:
                self._emit(self._buffer[:MAX_LINE_BYTES] + b" [line cut]")
            self._dropping = True
            self._buffer = b""

    def close(self):
        if self._buffer and not self._dropping:
            self._emit(self._buffer)
        self._buffer = b""

    def _emit(self, line):
        self._on_line(line.decode("utf-8", errors="replace").rstrip("\r"))


def _pump(streams, wake_fd):
    """Read every stream in `streams` ({fd: _LineReader}) until each reaches its end, or
    until `wake_fd` is readable (Orca and its group are gone); then read what is left
    without blocking. One thread; never holds more than the readers keep."""
    selector = selectors.DefaultSelector()
    for fd in streams:
        selector.register(fd, selectors.EVENT_READ)
    selector.register(wake_fd, selectors.EVENT_READ)
    open_fds = set(streams)
    try:
        while open_fds:
            for key, _events in selector.select():
                if key.fd == wake_fd:
                    for fd in list(open_fds):
                        _drain(fd, streams[fd])
                    return
                chunk = os.read(key.fd, 65536)
                if chunk:
                    streams[key.fd].feed(chunk)
                else:
                    selector.unregister(key.fd)
                    open_fds.discard(key.fd)
    finally:
        selector.close()
        for reader in streams.values():
            reader.close()


def _drain(fd, reader):
    os.set_blocking(fd, False)
    try:
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return
            reader.feed(chunk)
    except BlockingIOError:
        return


def _progress_line(line, on_progress):
    """One line from --pipe: Orca's JSON progress message, to on_progress(stage, fraction,
    message). Anything that is not such a message is ignored."""
    try:
        data = json.loads(line)
    except ValueError:
        return
    if not isinstance(data, dict) or not isinstance(data.get("message"), str):
        return
    percent = data.get("total_percent")
    fraction = None
    if isinstance(percent, (int, float)) and not isinstance(percent, bool) and 0 <= percent <= 100:
        fraction = percent / 100
    on_progress(ORCA_STAGES.get(data["message"]), fraction, data["message"])


def run_process(cmd, *, cwd, env, timeout_s, stop=None, on_progress=None, grace_s=None,
                timer=None, progress_fifo=None, clock=time.monotonic, memory_ceiling_kb=None,
                memory_reader=None, sample_s=None):
    """Run Orca and wait for it and its whole process group to be gone. Returns OrcaExit.

    `stop` (a Stop) ends the run early; `timer(timeout_s, fn)` (threading.Timer by
    default; tests inject one) sets it with reason "timeout". `progress_fifo` is a FIFO
    (os.mkfifo) whose path is given to --pipe: it is read while Orca runs, each message
    passed to `on_progress`, and removed afterwards. Once Orca has started, `on_progress`
    gets the stage "slicing" before any message of Orca's. With `memory_ceiling_kb`, the
    watchdog samples `memory_reader(pgid)` (MEMORY_READER by default) at once and then every
    `sample_s` (MEMORY_SAMPLE_S) until Orca exits, and sets `stop` with reason "memory"
    when a sample's peak (the higher of its resident and high-water figures) passes the
    ceiling. A stop is sent only when Orca is still running once it has been asked, and is
    reported in `stopped` only when it is what ended Orca: when Orca was already ending
    (DYING_PROBE, read just before the SIGTERM) or, sent only SIGTERM, ended on another
    signal, the reason goes into `overtaken` instead. Raises OSError when Orca cannot be
    started."""
    stop = stop or Stop()
    on_progress = on_progress or (lambda stage, fraction, message: None)
    tail = collections.deque(maxlen=TAIL_LINES)
    streams = {}
    fifo_fds = []
    if progress_fifo is not None:
        # Open both ends ourselves: the read end so Orca's open never blocks, a write end so
        # the read end sees no end of file before Orca has opened it.
        read_fd = os.open(progress_fifo, os.O_RDONLY | os.O_NONBLOCK)
        fifo_fds = [read_fd, os.open(progress_fifo, os.O_WRONLY | os.O_NONBLOCK)]
        os.set_blocking(read_fd, True)
        streams[read_fd] = _LineReader(lambda line: _progress_line(line, on_progress))
    oom_before = _oom_kills()
    started = clock()
    try:
        proc = subprocess.Popen(cmd, env=env, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True,
                                preexec_fn=_child_setup if _LIBC is not None else None)
    except BaseException:
        for fd in fifo_fds:
            os.close(fd)
        if progress_fifo is not None:
            Path(progress_fifo).unlink(missing_ok=True)
        raise
    streams[proc.stdout.fileno()] = _LineReader(tail.append)
    # Before the pump starts, so no message of Orca's can be overtaken by it.
    on_progress("slicing", None, "Slicing the plate")
    wake_r, wake_w = os.pipe()
    exited = threading.Event()
    wake = threading.Event()
    memory = {"peak_kb": None}

    def note_exit():
        try:
            _wait_for_exit(proc.pid)
        finally:            # set even if the wait fails, so the watchdog and the stop can never wait for ever
            exited.set()
            wake.set()

    def watch_memory():
        reader = memory_reader or MEMORY_READER
        interval = MEMORY_SAMPLE_S if sample_s is None else sample_s
        while True:
            reading = reader(proc.pid)
            if reading is not None:
                peak = max(reading)                  # (resident, high-water)
                memory["peak_kb"] = max(memory["peak_kb"] or 0, peak)
                if peak > memory_ceiling_kb:
                    stop.set("memory")
                    return
            if exited.wait(interval):
                return

    pump = threading.Thread(target=_pump, args=(streams, wake_r), name="orca-output", daemon=True)
    waiter = threading.Thread(target=note_exit, name="orca-wait", daemon=True)
    watchdog = threading.Thread(target=watch_memory, name="orca-memory", daemon=True) \
        if memory_ceiling_kb is not None else None
    pump.start()
    waiter.start()
    if watchdog:
        watchdog.start()
    stop.listen(wake.set)
    deadline = (timer or TIMER)(timeout_s, lambda: stop.set("timeout"))
    deadline.daemon = True
    deadline.start()
    escalated = dying = False
    try:
        wake.wait()
        # A stop counts only if Orca is still running now that it has been asked: one asked
        # as Orca ends by itself (before the waiter thread has noted the exit) is not sent.
        stopped = stop.reason if stop.is_set() and not exited.is_set() and _still_running(proc.pid) else None
        if stopped:
            dying = DYING_PROBE(proc.pid)            # already ending: the stop will not be what ends it
            _signal_group(proc.pid, signal.SIGTERM)
            if not exited.wait(STOP_GRACE_S if grace_s is None else grace_s):
                escalated = True
                _signal_group(proc.pid, signal.SIGKILL)
                exited.wait()
    finally:
        deadline.cancel()
        _signal_group(proc.pid, signal.SIGKILL)       # anything Orca left behind
        # Reap only once the waiter has noted the exit: reaping first would fail its wait. This
        # matters when the wait above ends by an exception (an interrupt): Orca is killed here.
        exited.wait()
        _pid, status, usage = os.wait4(proc.pid, 0)
        proc.returncode = os.waitstatus_to_exitcode(status)
        waiter.join()
        if watchdog:
            watchdog.join()
        os.write(wake_w, b"x")
        pump.join()
        proc.stdout.close()
        for fd in fifo_fds + [wake_r, wake_w]:
            os.close(fd)
        if progress_fifo is not None:
            Path(progress_fifo).unlink(missing_ok=True)
    oom_after = _oom_kills()
    oom = oom_after - oom_before if oom_before is not None and oom_after is not None else None
    overtaken = None
    if stopped and (dying or (not escalated and proc.returncode < 0 and -proc.returncode != signal.SIGTERM)):
        # Sent only SIGTERM, Orca ended on another signal; or it was ending already: the stop
        # did not end it, so how it ended is what is reported. (The wrapper execs Orca, so
        # the return code is Orca's own.)
        overtaken, stopped = stopped, None
    return OrcaExit(returncode=proc.returncode, output="\n".join(tail), stopped=stopped, escalated=escalated,
                    peak_rss_kb=usage.ru_maxrss // (1024 if sys.platform == "darwin" else 1),
                    wall_s=round(clock() - started, 3), oom_kills=oom, memory_peak_kb=memory["peak_kb"],
                    memory_ceiling_kb=memory_ceiling_kb, overtaken=overtaken, overtaken_dying=dying)


def _wait_for_exit(pid):
    """Block until child `pid` has exited, without reaping it: the group id stays ours."""
    os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT)


def _still_running(pid):
    """Whether child `pid` has not exited yet; it is not reaped either way (WNOWAIT)."""
    return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None


def _signal_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _run_orca(cmd, output_dir, timeout_s, stop=None, on_progress=None, memory_ceiling_mb=None):
    """Run Orca in output_dir with its private environment, under the memory watchdog with
    `memory_ceiling_mb` (limits.max_peak_mb() when None); its OrcaExit, for settle() to
    judge. Raises RuntimeError when the binary is missing, SliceError when the scratch
    folder cannot be written or Orca cannot start."""
    _require_binary()
    output_dir = Path(output_dir)
    fifo = output_dir / PROGRESS_FIFO
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        env = orca_env(output_dir)
        os.mkfifo(fifo, 0o600)
    except OSError as exc:
        raise SliceError(SCRATCH_UNWRITABLE_MESSAGE, f"{type(exc).__name__}: {exc}",
                         error_code="slice.scratch_unwritable") from None
    ceiling_mb = max_peak_mb() if memory_ceiling_mb is None else memory_ceiling_mb
    try:
        run = run_process(cmd, cwd=output_dir, env=env, timeout_s=timeout_s, stop=stop, on_progress=on_progress,
                          progress_fifo=fifo, memory_ceiling_kb=ceiling_mb * 1024)
    except OSError as exc:
        # The wrapper is missing, not executable, or not this architecture.
        raise SliceError(UNSTARTABLE_MESSAGE, f"{type(exc).__name__}: {exc}",
                         error_code="slice.orca_unstartable") from None
    return run


def settle(run, archive, output_dir, supports_on=None, entries=(GCODE_ENTRY,)):
    """How an Orca run ended, decided here and nowhere else: the SliceResult, or the
    exception for its error report. In this order:

    1. A complete sliced file is never discarded by a stop the slice service decides on:
       when Orca exited 0, or was stopped for a timeout or by the watchdog (KEEPING_STOPS),
       and `archive` is complete (_result, with `entries`), the slice succeeds. A stop
       that reached Orca is recorded in stop_note, a peak over the ceiling in memory_note.
    2. A stop the slice service sent and that ended Orca (run.stopped, the first reason
       asked): "memory" is slice.out_of_memory, "timeout" slice.timeout, any other (a
       cancel, an abandoned job, a shutdown) SliceCancelled, even with a complete file.
    3. Orca's own ending: its failure's error report, or the sliced file's own fault. A stop
       that was asked but did not end Orca (run.overtaken) is named in the detail."""
    if run.returncode == 0 or run.stopped in KEEPING_STOPS:
        try:
            return _result(archive, output_dir, run, entries)
        except SliceError:
            if not run.stopped:
                raise
    if run.stopped:
        raise _stop_error(run)
    exc = _exit_error(run, output_dir, supports_on)
    if run.overtaken:
        first, _, rest = exc.details.partition("\n")
        exc.details = "\n".join(part for part in (first, _overtaken_text(run), rest) if part)
    raise exc


def _overtaken_text(run):
    if run.overtaken_dying:
        return f"it was already ending when the slice service asked it to stop ({run.overtaken})"
    return f"the slice service had asked it to stop ({run.overtaken}) and sent SIGTERM, which is not what ended it"


def _ceiling_text(run):
    return f"the ceiling of {run.memory_ceiling_kb:,} kB ({MAX_PEAK_MB_ENV}={run.memory_ceiling_kb // 1024})"


def _peak_text(run):
    """The peak and where it was read: never under the true peak of Orca itself."""
    sources = [f"{label} {kb:,} kB" for label, kb in (("the watchdog's high-water reading", run.memory_peak_kb),
                                                     ("Orca's ru_maxrss at exit", run.peak_rss_kb))
               if kb is not None]
    return f"a peak of {run.peak_kb:,} kB ({', '.join(sources)})"


def _stop_error(run):
    """The exception for a stop the slice service sent to a running Orca."""
    if run.stopped == "memory":
        return SliceError(MEMORY_CEILING_MESSAGE.format(ceiling_mb=run.memory_ceiling_kb // 1024),
                          f"{_stop_detail(run)}: Orca's processes reached {_peak_text(run)}, over "
                          f"{_ceiling_text(run)}\n" + _tail(run.output, DETAIL_LINES - 1),
                          error_code="slice.out_of_memory", reason=MEMORY_STOP_REASON, run=run)
    if run.stopped == "timeout":
        return SliceError(TIMEOUT_MESSAGE, _stop_detail(run) + "\n" + _tail(run.output, DETAIL_LINES - 1),
                          code="timeout", error_code="slice.timeout", run=run)
    return SliceCancelled(_stop_detail(run))          # a cancel, an abandoned job, a shutdown


def _stop_detail(run):
    how = "SIGTERM, then SIGKILL after the grace time" if run.escalated else "SIGTERM"
    return f"stopped by the slice service ({run.stopped}) with {how} after {run.wall_s} s"


def _signal_name(number):
    try:
        return signal.Signals(number).name
    except ValueError:
        return "unknown signal"


def _failure_details(exit_code, output, reasons=()):
    # The exit code leads, then Orca's own reasons when it gave them, then the last lines of
    # output: the code is always visible and the reasons are never cut.
    lead = [f"exit code {exit_code}"] + [f"orca {name}: {text}" for name, text in reasons if text]
    return "\n".join(lead + [_tail(output, max(DETAIL_LINES - len(lead), 5))])


def _out_of_memory(run, reason=""):
    return OUT_OF_MEMORY_RE.search(run.output) or OUT_OF_MEMORY_RE.search(reason)


def _signal_failure(run):
    """The SliceError for an Orca that ended on a signal the slice service did not send."""
    number = -run.returncode
    name = _signal_name(number)
    evidence = f"ended by signal {number} ({name}), not sent by the slice service"
    if run.oom_kills:
        evidence += f"; the kernel's oom_kill count rose by {run.oom_kills}"
    elif run.oom_kills == 0:
        evidence += "; the kernel's oom_kill count did not change"
    else:
        evidence += "; the kernel's oom_kill count could not be read"
    detail = evidence + "\n" + _tail(run.output, DETAIL_LINES - 1)
    if run.oom_kills or _out_of_memory(run):
        # Only the kernel's own count, or Orca's own words, say a kill was for memory; a
        # SIGKILL with neither came from someone else (slice.orca_killed below).
        return SliceError(OUT_OF_MEMORY_MESSAGE, detail, error_code="slice.out_of_memory", run=run)
    if number in CRASH_SIGNALS:
        return SliceError(CRASHED_MESSAGE, detail, error_code="slice.orca_crashed", run=run)
    return SliceError(KILLED_MESSAGE, detail, error_code="slice.orca_killed", run=run)


def _exit_status_signal(run):
    """A wrapper that does not exec turns a signal into exit status 128 + N; that N, or None."""
    number = run.returncode - 128
    if 0 < number < 65 and "run found error, return" not in run.output:
        return number
    return None


def _complete_text(entries):
    return (f"it opens, its directory is intact, it has {' and '.join(entries)}, and every entry reads back with "
            f"its checksum")


def _result(archive, output_dir, run, entries=(GCODE_ENTRY,)):
    """The SliceResult of a complete sliced file, else the SliceError of its fault. Complete
    means, for a normal success and after a stop alike: the file is there under its final
    name (Orca writes `<name>.tmp` and renames it once written); it opens as a zip, which
    needs the end-of-central-directory record and the central directory, the last bytes a
    zip writer writes, so a file cut anywhere fails; the G-code header reads; every entry
    in `entries` is listed; and every entry listed decompresses and matches its CRC-32."""
    if not archive.is_file():
        raise SliceError(NO_OUTPUT_MESSAGE, _tail(run.output), error_code="slice.no_output", run=run)
    summary = read_summary(archive, output_dir)
    verify_archive(archive, entries)
    note = stop_note = None
    if run.over_ceiling():
        how = ("the watchdog stopped Orca only after it had written the complete sliced file" if run.stopped == "memory"
               else "Orca finished before the watchdog stopped it")
        note = f"Orca's processes reached {_peak_text(run)}, over {_ceiling_text(run)}, and {how}: the sliced file " \
               f"is delivered"
    if run.stopped:
        stop_note = (f"{_stop_detail(run)}, after Orca had written the complete sliced file ({_complete_text(entries)}):"
                     f" the sliced file is delivered")
        if not (Path(output_dir) / RESULT_JSON).is_file():
            stop_note += "; Orca had not written result.json, so any warnings of its own are not known"
    return SliceResult(output_path=archive, peak_rss_kb=run.peak_kb, wall_s=run.wall_s, memory_note=note,
                       stop_note=stop_note, **summary)


def _exit_error(run, output_dir, supports_on=None):
    """The SliceError for a run that failed by itself (a signal, or a non-zero exit;
    supports_on: whether the plate was sliced with supports, None for unknown)."""
    if run.returncode < 0:
        return _signal_failure(run)
    if run.returncode in UNSTARTABLE_EXITS and not read_result_json(output_dir):
        return SliceError(UNSTARTABLE_MESSAGE, f"exit code {run.returncode}: Orca did not start (the wrapper or the "
                                               f"loader failed)\n" + _tail(run.output, DETAIL_LINES - 1),
                          error_code="slice.orca_unstartable", reason=_tail(run.output, 1), run=run)
    if not read_result_json(output_dir) and _exit_status_signal(run) is not None:
        return _signal_failure(OrcaExit(-_exit_status_signal(run), run.output, peak_rss_kb=run.peak_rss_kb,
                                        wall_s=run.wall_s, oom_kills=run.oom_kills,
                                        memory_peak_kb=run.memory_peak_kb))
    return orca_failure(run, output_dir, supports_on)


def orca_failure(run, output_dir, supports_on=None):
    """The SliceError for a non-zero exit, its sentence chosen from Orca's own reason."""
    code = orca_return_code(output_dir, run.returncode)
    error_string = orca_error_string(output_dir)
    warnings = _warnings(read_result_json(output_dir))
    said = [(m.group(0).strip(), error_code, message) for pattern, error_code, message in ORCA_OUTPUT_REASONS
            for m in [pattern.search(run.output)] if m]
    reason = "\n".join([text for text, _c, _m in said] + [error_string] + warnings).strip()
    details = _failure_details(run.returncode, run.output,
                               [("said", text) for text, _c, _m in said] + [("error_string", error_string)]
                               + [("warning_message", w) for w in warnings])
    if _out_of_memory(run, reason):
        return SliceError(OUT_OF_MEMORY_MESSAGE, details, code, error_code="slice.out_of_memory", reason=reason,
                          run=run)
    empty = next((m for m in map(EMPTY_LAYER_RE.search, warnings) if m), None)
    if empty:
        names = [m.group(1).strip() for w in warnings for m in [OBJECT_RE.search(w)] if m]
        copy = names[0] if names else None
        low, high = empty.group(1), empty.group(2)
        where = {"height_mm": float(low)}
        if copy:
            where["copy"] = copy
        message = (EMPTY_LAYERS_MESSAGE.format(copy=copy, low=low, high=high) if copy
                   else EMPTY_LAYERS_NO_COPY_MESSAGE.format(low=low, high=high))
        error_code = "slice.empty_layers_with_supports" if supports_on else "slice.empty_layers"
        return SliceError(message, details, code, error_code=error_code, where=where, reason=reason, run=run)
    if said:
        _text, error_code, message = said[0]
        return SliceError(message, details, code, error_code=error_code, reason=reason, run=run)
    error_code, message = ORCA_RETURN_CODES.get(code, ("slice.orca_failed", SLICE_FAILED_MESSAGE))
    return SliceError(message, details, code, error_code=error_code, reason=reason, run=run)


def slice_stl(stl_path, output_dir, timeout_s=DEFAULT_TIMEOUT_S, stop=None, on_progress=None):
    """Slice `stl_path` into `output_dir/<stem>.gcode.3mf` and return a SliceResult."""
    stl_path = Path(stl_path).resolve()
    output_dir = Path(output_dir).resolve()
    run = _run_orca(build_command(stl_path, output_dir), output_dir, timeout_s, stop, on_progress)
    return settle(run, output_dir / (stl_path.stem + ARCHIVE_SUFFIX), output_dir)


def read_result_json(output_dir):
    """Orca's result.json in `output_dir` as a dict; {} when it is missing, unreadable or
    not a JSON object (Orca on macOS writes none)."""
    try:
        data = json.loads((Path(output_dir) / RESULT_JSON).read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, RecursionError):
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


def process_supports_on(process_path):
    """Whether a process profile slices with supports: its enable_support is "1"."""
    try:
        with open(process_path, encoding="utf-8") as fh:
            return str(json.load(fh).get("enable_support", "0")) == "1"
    except (OSError, ValueError, AttributeError):
        return None


def slice_plate(model_3mf, profiles, output_dir, timeout_s=PLATE_SLICE_TIMEOUT_S, stop=None, on_progress=None,
                memory_ceiling_mb=None):
    """Slice a plate 3MF (plate_3mf.py) into `output_dir/plate.gcode.3mf` with the
    placement as written, Orca stopped at `memory_ceiling_mb` (limits.max_peak_mb() when
    None); return a SliceResult."""
    output_dir = Path(output_dir).resolve()
    run = _run_orca(build_plate_command(model_3mf, profiles, output_dir), output_dir, timeout_s, stop, on_progress,
                    memory_ceiling_mb)
    return settle(run, output_dir / PLATE_ARCHIVE, output_dir, process_supports_on(profiles.process),
                  entries=PLATE_ENTRIES)


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
    except (zipfile.BadZipFile, OSError) as exc:
        raise SliceError(UNREADABLE_MESSAGE, f"{archive_path.name} is not a zip archive ({exc})",
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


def verify_archive(archive, entries=()):
    """Read every entry once, checking each against its CRC-32, so a sliced file cut short
    or damaged anywhere is refused before it is delivered (slice.unreadable_output); and
    refuse one that lacks any of `entries`."""
    try:
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
            bad = zf.testzip()
    except _ZIP_READ_ERRORS as exc:
        raise _unreadable(archive, repr(exc)) from None
    missing = [entry for entry in entries if entry not in names]
    if missing:
        raise _unreadable(archive, f"the sliced file has no entry {', '.join(missing)}")
    if bad is not None:
        raise _unreadable(archive, f"entry {bad} fails its checksum")


def plate_object_names(archive):
    """The object names Orca sliced onto plate 1, from the archive's Metadata/plate_1.json.
    Raises SliceError (slice.unreadable_output) when that entry cannot be read or its
    bbox_objects is not a list of objects."""
    try:
        with zipfile.ZipFile(archive) as zf:
            plate = json.loads(zf.read(PLATE_JSON_ENTRY).decode("utf-8"))
    except (KeyError, ValueError, RecursionError, *_ZIP_READ_ERRORS) as exc:
        raise SliceError(UNREADABLE_MESSAGE, f"{PLATE_JSON_ENTRY}: {exc!r}"[:300],
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
