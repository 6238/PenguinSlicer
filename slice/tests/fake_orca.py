"""A stand-in for Orca Slicer's command line, for the fast suite.

Run through a wrapper helpers.fake_orca writes: `python -I fake_orca.py --mode <mode> <orca
arguments>`. It reads the plate 3MF named last on the command line and writes the files
the pinned Orca (scripts/install-orca.sh) writes into --outputdir, in the shape the slice
service reads: the archive named by --export-3mf (Metadata/plate_1.gcode with its header,
Metadata/slice_info.config, Metadata/plate_1.json) and result.json. It also writes
fake-orca-argv.json, the arguments it was given.

Modes:
    ok       slice every object;
    drop     leave the last object out with exit 0, as Orca does with a copy off the plate;
    refuse   refuse the plate with return code -101 (exit status 155);
    garbled  refuse as `refuse` does, printing a line that is not UTF-8 first.
"""
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
HEADER = "; HEADER_BLOCK_START\n; total layer number: 42\n; HEADER_BLOCK_END\n"
SLICE_INFO = ('<?xml version="1.0" encoding="UTF-8"?>\n<config><plate>'
              '<metadata key="prediction" value="600"/><metadata key="weight" value="4.5"/>'
              '<filament id="1" used_m="1.5" used_g="4.5"/></plate></config>\n')


def main(argv):
    mode = argv[argv.index("--mode") + 1]
    out = Path(argv[argv.index("--outputdir") + 1])
    archive = out / argv[argv.index("--export-3mf") + 1]
    (out / "fake-orca-argv.json").write_text(json.dumps(argv))
    with zipfile.ZipFile(argv[-1]) as zf:
        root = ET.fromstring(zf.read("3D/3dmodel.model"))
    names = [obj.get("name") for obj in root.iter(NS + "object")]
    if mode == "garbled":
        sys.stdout.buffer.write(b"Br\xe4cket is too close\n")     # Latin-1, not UTF-8
        sys.stdout.flush()
        mode = "refuse"
    if mode == "refuse":
        (out / "result.json").write_text(json.dumps({"return_code": -101, "error_string": "too close"}))
        print("Some objects are too close together")
        return 155
    if mode == "drop":
        names = names[:-1]
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Metadata/plate_1.gcode", HEADER + "G1 X1 Y1\n")
        zf.writestr("Metadata/slice_info.config", SLICE_INFO)
        zf.writestr("Metadata/plate_1.json", json.dumps({"bbox_objects": [{"name": n} for n in names]}))
    (out / "result.json").write_text(json.dumps({"return_code": 0, "sliced_plates": [{"warning_message": ""}]}))
    print("fake orca: sliced", len(names), "objects")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
