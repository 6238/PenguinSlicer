"""A stand-in for Orca Slicer's command line, for the fast suite.

Run through a wrapper helpers.install_fake_orca writes: `python -I fake_orca.py --mode
<mode> <orca arguments>`. It reads the plate 3MF named last on the command line and
writes the files the pinned Orca (scripts/install-orca.sh) writes into --outputdir, in the
shape the slice service reads: the archive named by --export-3mf (Metadata/plate_1.gcode
with its header, Metadata/slice_info.config, Metadata/plate_1.json) and result.json. It
sends progress messages through the FIFO named by --pipe, in the shape the pinned Orca
sends them (tests_orca pins that shape). It also writes fake-orca-argv.json, the
arguments it was given, and fake-orca.pid, its process id.

Modes:
    ok            slice every object, sending Orca's progress messages first;
    drop          leave the last object out with exit 0, as Orca does with an instance off the plate;
    refuse        refuse the plate with return code -101 (exit status 155);
    refuse_logged the same, its debug log naming the last and first objects as the pair whose paths meet;
    garbled       refuse as `refuse` does, printing a line that is not UTF-8 first;
    empty_layers  refuse with -100 and the empty-layer warning Orca writes into result.json;
    general       refuse with -100 and only Orca's general error_string;
    general_warned  the same, with a floating-regions warning in the debug log (--logfile);
    no_layers     refuse with -100, printing Orca's "No layers were detected." first;
    print_empty   refuse with -100, printing Orca's "The print is empty." first;
    exit_127      exit 127 with the loader's words, as Orca with a library missing does;
    unknown_code  refuse with a return code the slice service does not know (-77);
    bad_alloc     print std::bad_alloc and refuse with -100, as Orca under RLIMIT_AS does;
    sigkill       die on SIGKILL, as the kernel's out-of-memory killer does it;
    segv, abort   crash with SIGSEGV or SIGABRT;
    sigterm       die on SIGTERM sent by someone else;
    exit_bare     exit 1 with no result.json;
    exit_137      exit 137 with no result.json, as a wrapper that does not exec reports SIGKILL;
    bad_result    exit 156 with a result.json that is not JSON;
    no_output     exit 0 without writing the archive;
    truncated     exit 0 with an archive cut off half way;
    corrupt       exit 0 with an archive whose G-code entry fails its checksum;
    hang          send one progress message, then wait for a signal;
    gate          make the FIFO fake-orca.gate in --outputdir, send one progress message, wait
                  until a test writes a byte into the FIFO (open_gate), then slice as `ok` does;
    hang_hard     the same, ignoring SIGTERM;
    tmp_then_hang      write the whole archive under Orca's temporary name (<archive>.tmp) only,
                       say "All done, Success", then wait for a signal: the real Orca at
                       "Exporting 3mf", the file not yet renamed to its final name;
    half_then_hang     write the first half of the archive under its final name, then say
                       "All done, Success" and wait for a signal;
    written_then_hang  write the whole archive under its final name and no result.json, then
                       say "All done, Success" and wait for a signal: the real Orca in the
                       moment between writing its sliced file and exiting;
    child         start a child that outlives this process, then slice as `ok` does;
    flood         print FLOOD_BYTES of output (one very long line among them), then slice.
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
HEADER = "; HEADER_BLOCK_START\n; total layer number: 42\n; HEADER_BLOCK_END\n"
SLICE_INFO = ('<?xml version="1.0" encoding="UTF-8"?>\n<config><plate>'
              '<metadata key="prediction" value="600"/><metadata key="weight" value="4.5"/>'
              '<filament id="1" used_m="1.5" used_g="4.5"/></plate></config>\n')
FLOOD_BYTES = 8 * 1024 * 1024
GATE = "fake-orca.gate"           # mode gate's FIFO, in --outputdir
GENERAL = "Failed slicing the model. Please verify the slicing of all plates on Orca Slicer before uploading."
# Orca's words on stdout, as the pinned Orca prints them (tests_orca pins them).
NO_LAYERS = ("No layers were detected. You might want to repair your STL file(s) or check their size or thickness "
             "and retry.\n")
PRINT_EMPTY = "The print is empty. The model is not printable with current print settings."
# A warning in Orca's debug log, as the pinned Orca writes it at --debug 3 (tests_orca pins it).
LOG_WARNING = ("cli_status_callback: percent=-1, warning_step=7, message=It seems object {name} has floating "
               "regions. Please re-orient the object or enable support generation., message_type=2, flag=32")
# The debug log's line for a -101, as the pinned Orca writes it (tests_orca pins it).
CONFLICT = "gcode path conflicts found between {} and {}"
LOADER = ("orca-slicer: error while loading shared libraries: libpangoft2-1.0.so.0: cannot open shared object file: "
          "No such file or directory")
# The stand-in, and the child it can start, end themselves after this long whatever they
# were asked to do (SIGALRM, whose default action ends a process): a test that fails to
# stop one can never leave it behind. No mode needs a second.
LIMIT_S = 25
CHILD = ("import fcntl, signal, sys\nsignal.alarm(%d)\nlock = open(sys.argv[1], 'w')\nfcntl.flock(lock, fcntl.LOCK_EX)\n"
         "print('locked', flush=True)\nwhile True: signal.pause()\n" % LIMIT_S)
PROGRESS = [("Start to load files", 1), ("Loading files finished", 2), ("Prepare slicing", 3),
            ("Slicing begins", 6), ("Slicing mesh", 7), ("Generating walls", 16), ("Generating G-code", 75),
            ("Exporting 3mf", 97), ("All done, Success", 100)]


class Pipe:
    def __init__(self, argv):
        self.fh = open(argv[argv.index("--pipe") + 1], "w") if "--pipe" in argv else None

    def send(self, message, percent):
        if self.fh:
            self.fh.write(json.dumps({"message": message, "plate_count": 1, "plate_index": 1,
                                      "plate_percent": percent, "total_percent": percent}) + "\n")
            self.fh.flush()


def refuse(out, code, error_string, warning=None, line="run found error, return %d, exit..."):
    result = {"return_code": code, "error_string": error_string}
    if warning is not None:
        result["sliced_plates"] = [{"id": 1, "warning_message": warning}]
    (out / "result.json").write_text(json.dumps(result))
    print(line % code if "%d" in line else line, flush=True)
    return (code + 256) % 256


def wait_for_a_signal(pipe, ignore_term):
    if ignore_term:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    print("fake orca: slicing", flush=True)
    pipe.send("Slicing mesh", 7)
    while True:
        signal.pause()


def layered_gcode(layers=42, moves=2000):
    """G-code a page can draw, in the pinned Orca's markers: the header's 42 layers, each opened
    by `; CHANGE_LAYER`, `; Z_HEIGHT:` and `; LAYER_HEIGHT:`, with its share of `moves` extruding
    moves (relative E, as Orca's M83) under a `; FEATURE:`, inside a 50 x 43 mm square."""
    out = [HEADER, "M83\nG90\n"]
    for layer in range(layers):
        z = round(0.2 * (layer + 1), 2)
        out.append(f"; CHANGE_LAYER\n; Z_HEIGHT: {z}\n; LAYER_HEIGHT: 0.2\nG1 Z{z} F600\n"
                   "; FEATURE: Outer wall\n; LINE_WIDTH: 0.42\n")
        for i in range(layer * moves // layers, (layer + 1) * moves // layers):
            out.append(f"G1 X{100 + i % 50} Y{100 + i * 7 % 43} E0.{i + 1}\n")
    return "".join(out)


def write_archive(path, names):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Metadata/plate_1.gcode", layered_gcode())
        zf.writestr("Metadata/slice_info.config", SLICE_INFO)
        zf.writestr("Metadata/plate_1.json", json.dumps({"bbox_objects": [{"name": n} for n in names]}))


def main(argv):
    signal.alarm(LIMIT_S)
    mode = argv[argv.index("--mode") + 1]
    out = Path(argv[argv.index("--outputdir") + 1])
    archive = out / argv[argv.index("--export-3mf") + 1]
    (out / "fake-orca-argv.json").write_text(json.dumps(argv))
    (out / "fake-orca.pid").write_text(str(os.getpid()))
    lock = open(out / "fake-orca.lock", "w")             # held until this process is gone
    fcntl.flock(lock, fcntl.LOCK_EX)
    pipe = Pipe(argv)
    with zipfile.ZipFile(argv[-1]) as zf:
        root = ET.fromstring(zf.read("3D/3dmodel.model"))
    names = [obj.get("name") for obj in root.iter(NS + "object")]
    if mode in ("hang", "hang_hard"):
        wait_for_a_signal(pipe, mode == "hang_hard")
    if mode == "gate":
        gate = out / GATE
        os.mkfifo(gate)
        pipe.send("Slicing mesh", 7)
        with open(gate, "rb") as fh:          # blocks until the test opens the gate and writes to it
            fh.read(1)
        mode = "ok"
    if mode == "child":
        # The child holds an exclusive lock on fake-orca-child.lock for as long as it lives,
        # so a test can wait for its death without sleeping.
        child = subprocess.Popen([sys.executable, "-I", "-S", "-c", CHILD, str(out / "fake-orca-child.lock")],
                                 stdout=subprocess.PIPE)
        child.stdout.readline()                                 # the lock is taken
        (out / "fake-orca-child.pid").write_text(str(child.pid))
    if mode == "flood":
        chunk = "x" * 1023 + "\n"
        sys.stdout.write("y" * (2 * 1024 * 1024) + "\n")       # one line of 2 MB
        for _ in range(FLOOD_BYTES // len(chunk)):
            sys.stdout.write(chunk)
        sys.stdout.write("fake orca: last line\n")
        sys.stdout.flush()
    if mode == "garbled":
        sys.stdout.buffer.write(b"Br\xe4cket is too close\n")     # Latin-1, not UTF-8
        sys.stdout.flush()
        mode = "refuse"
    if mode == "refuse_logged":
        log = Path(argv[argv.index("--logfile") + 1])
        log.write_text("gcode path conflicts check takes 0.08 secs.\n" + CONFLICT.format(names[-1], names[0]) + "\n"
                       + "plate 1: found slicing result conflict!\n")
        mode = "refuse"
    if mode == "refuse":
        (out / "result.json").write_text(json.dumps({"return_code": -101, "error_string": "too close"}))
        print("Some objects are too close together")
        return 155
    if mode == "empty_layers":
        return refuse(out, -100, GENERAL, f"Object can't be printed for empty layer between 9.9 and 11.34.\n"
                                          f"Object: {names[0]}\nMaybe parts of the object at these height are "
                                          f"too thin, or the object has faulty mesh")
    if mode == "general":
        return refuse(out, -100, GENERAL)
    if mode == "general_warned":
        log = Path(argv[argv.index("--logfile") + 1])
        # The warning twice, as the real log has it (the callback, then the manager's update).
        log.write_text("cli_callback_mgr_t::start enter.\n" + (LOG_WARNING.format(name=names[0]) + "\n") * 2
                       + "found slicing or export error for partplate 1\n")
        print("Errors", flush=True)
        return refuse(out, -100, GENERAL)
    if mode in ("no_layers", "print_empty"):
        print(NO_LAYERS if mode == "no_layers" else PRINT_EMPTY, flush=True)
        return refuse(out, -100, GENERAL)
    if mode == "exit_127":
        print(LOADER, flush=True)
        return 127
    if mode == "unknown_code":
        return refuse(out, -77, "Something Orca has never said before.")
    if mode == "bad_alloc":
        print("std::bad_alloc", flush=True)
        return refuse(out, -100, GENERAL)
    if mode in ("sigkill", "segv", "abort", "sigterm"):
        print("fake orca: about to stop", flush=True)
        os.kill(os.getpid(), {"sigkill": signal.SIGKILL, "segv": signal.SIGSEGV, "abort": signal.SIGABRT,
                              "sigterm": signal.SIGTERM}[mode])
    if mode == "exit_bare":
        print("fake orca: giving up", flush=True)
        return 1
    if mode == "exit_137":
        print("Killed", flush=True)
        return 137
    if mode == "bad_result":
        (out / "result.json").write_text('{"return_code": -100, "error_str')
        print("run found error, return -100, exit...", flush=True)
        return 156
    if mode in ("tmp_then_hang", "half_then_hang", "written_then_hang"):
        for message, percent in PROGRESS[:-1]:
            pipe.send(message, percent)
        target = archive.with_name(archive.name + ".tmp") if mode == "tmp_then_hang" else archive
        write_archive(target, names)
        if mode == "half_then_hang":
            data = archive.read_bytes()
            archive.write_bytes(data[:len(data) // 2])
        pipe.send(*PROGRESS[-1])
        while True:
            signal.pause()
    for message, percent in PROGRESS:
        pipe.send(message, percent)
    if mode == "no_output":
        return 0
    if mode == "drop":
        names = names[:-1]
    write_archive(archive, names)
    if mode == "truncated":
        data = archive.read_bytes()
        archive.write_bytes(data[:len(data) // 2])
    if mode == "corrupt":
        data = bytearray(archive.read_bytes())
        data[1000:1040] = b"\x00" * 40         # inside the deflated G-code, the first entry
        archive.write_bytes(bytes(data))
    (out / "result.json").write_text(json.dumps({"return_code": 0, "sliced_plates": [{"warning_message": ""}]}))
    print("fake orca: sliced", len(names), "objects")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
