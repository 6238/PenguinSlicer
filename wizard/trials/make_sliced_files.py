#!/usr/bin/env python3
"""The first trial's three real sliced files.

Writes the three plates of the layer preview's trial as plate configurations into
wizard/trials/plates/ (`--write-plates`), and has a slice service started by hand on the same
machine slice each one through its HTTP interface as built today (a plate configuration with
its STL files), saving the sliced file and its summary into wizard/trials/sliced/, which is not
committed. How to start the slice service, with the real-Orca lock and the memory ceiling the
blocks plate needs, is in wizard/trials/preview/README.md.

The plates (wizard/README-details.md, "How the trials and measurements are run"):

- four-each-b-supports: the slice service's plate four-each-b (slice/tests/frc_parts.py),
  16 instances, 2 of each real part, supports on. The wizard reads no other component's
  folder, so the positions are written here again, from that file.
- blocks-12-supports: twelve Elevator Block Bottom Inners, 3 by 4, 12.5 mm apart, supports on.
- spacers-150: 150 of wizard/trials/parts/hex-spacer.stl, 13 by 12 less 6, 22 mm apart,
  supports off.
"""
import argparse
import http.client
import json
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

WIZARD = Path(__file__).resolve().parent.parent
TRIALS = WIZARD / "trials"
PLATES_DIR = TRIALS / "plates"
SLICED_DIR = TRIALS / "sliced"
REAL = WIZARD.parent / "contracts" / "examples" / "parts" / "real"
MADE = TRIALS / "parts"
PLATE_CENTRE = (170.0, 160.0)          # the H2S plate, 340 x 320 mm
FINAL = {"done", "failed", "cancelled"}
TIMEOUT_S = 600                        # a socket that says nothing for this long is a failure

# ref -> (file, the part's name, the axis that points up: its largest flat face on the plate)
PARTS = {
    "clamp-plate-inner": (REAL / "clamp-plate-inner.stl", "Clamp Plate Inner", "-x"),
    "elevator-block-bottom-inner": (REAL / "elevator-block-bottom-inner.stl", "Elevator Block Bottom Inner", "-z"),
    "elevator-block-carriage": (REAL / "elevator-block-carriage.stl", "Elevator Block Carriage", "+y"),
    "elevator-block-top": (REAL / "elevator-block-top.stl", "Elevator Block Top", "+y"),
    "elevator-top-inner": (REAL / "elevator-top-inner.stl", "Elevator Top Inner", "+y"),
    "inner-spacer": (REAL / "inner-spacer.stl", "Inner Spacer", "+x"),
    "outer-clamp": (REAL / "outer-clamp.stl", "Outer Clamp", "-x"),
    "pulley-v3": (REAL / "pulley-v3.stl", "Pulley v3", "+x"),
    "hex-spacer": (MADE / "hex-spacer.stl", "Hex Spacer", "+z"),
}


class SliceFailed(Exception):
    """A plate that could not be sliced, in a sentence naming the plate and the reason."""


def instance(ref, x, y):
    return {"ref": ref, "orientation": PARTS[ref][2], "angle": 0, "x": round(float(x), 6), "y": round(float(y), 6)}


def configuration(instances, supports):
    refs = list(dict.fromkeys(i["ref"] for i in instances))
    return {"parts": {ref: {"name": PARTS[ref][1], "stl": PARTS[ref][0].name} for ref in refs},
            "instances": instances, "overrides": {"supports": "on" if supports else "off"}}


def grid(ref, columns, rows, pitch_x, pitch_y, count=None):
    count = columns * rows if count is None else count
    return [instance(ref, PLATE_CENTRE[0] + (k % columns - (columns - 1) / 2) * pitch_x,
                     PLATE_CENTRE[1] + (k // columns - (rows - 1) / 2) * pitch_y) for k in range(count)]


def plate_configurations():
    """{plate name: plate configuration}, in the order the trial reports them."""
    four_each_a = ([instance(ref, x, y) for x in (50, 152) for ref, y in
                    (("elevator-block-top", 47), ("elevator-block-bottom-inner", 134),
                     ("elevator-block-carriage", 208), ("pulley-v3", 275))]
                   + [instance(ref, x, y) for x in (236, 300) for ref, y in
                      (("elevator-top-inner", 34), ("clamp-plate-inner", 101), ("outer-clamp", 165),
                       ("inner-spacer", 229))])
    four_each_b = [dict(i, x=2 * PLATE_CENTRE[0] - i["x"]) for i in four_each_a]
    # The block's footprint is 88.9 by 63.5 mm, so 12.5 mm apart is a pitch of 101.4 by 76.
    blocks = grid("elevator-block-bottom-inner", 3, 4, 88.9 + 12.5, 63.5 + 12.5)
    spacers = grid("hex-spacer", 13, 12, 22.0, 22.0, count=150)
    return {"four-each-b-supports": configuration(four_each_b, True),
            "blocks-12-supports": configuration(blocks, True),
            "spacers-150": configuration(spacers, False)}


def write_plates(folder=PLATES_DIR):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name, plate in plate_configurations().items():
        (folder / f"{name}.json").write_text(json.dumps(plate, indent=1) + "\n")


def part_files(plate):
    """{the stl file name the HTTP interface receives: the file on disk}."""
    by_name = {path.name: path for path, _, _ in PARTS.values()}
    return {part["stl"]: by_name[part["stl"]] for part in plate["parts"].values()}


def multipart(plate):
    boundary = uuid.uuid4().hex
    chunks = [f'--{boundary}\r\nContent-Disposition: form-data; name="plate_configuration"\r\n'
              f"Content-Type: application/json\r\n\r\n".encode(), json.dumps(plate).encode(), b"\r\n"]
    for name, path in part_files(plate).items():
        chunks += [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}"\r\n'
                   f"Content-Type: application/octet-stream\r\n\r\n".encode(), path.read_bytes(), b"\r\n"]
    chunks.append(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


def sentence(report):
    return f"{report.get('code', 'no code')}): {report.get('message', 'no sentence')}"


def slice_plate(url, name, out_dir=SLICED_DIR, plate=None):
    """Has the slice service at `url` slice the plate `name`, follows its progress stream to its
    final report, and saves `<name>.gcode.3mf` and `<name>.summary.json` in `out_dir`."""
    plate = plate_configurations()[name] if plate is None else plate
    address = urlsplit(url)
    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=TIMEOUT_S)
    try:
        content_type, body = multipart(plate)
        try:
            connection.request("POST", "/slices", body, {"Content-Type": content_type})
            answer = connection.getresponse()
        except OSError as error:
            raise SliceFailed(f"{name}: no slice service answers at {url} ({error})") from None
        payload = json.loads(answer.read() or b"{}")
        if answer.status != 202:
            raise SliceFailed(f"{name}: the slice service refused it (HTTP {answer.status}, {sentence(payload)}")
        job = payload["job"]
        last = follow(connection, job)
        if last is None or last["state"] not in FINAL:
            state = last["state"] if last else "none"
            raise SliceFailed(f"{name}: the progress stream ended before the slice job did (last state: {state})")
        if last["state"] != "done":
            error = last.get("error") or {"code": f"slice job {last['state']}", "message": str(last)}
            raise SliceFailed(f"{name}: the slice {last['state']} ({sentence(error)}")
        sliced = fetch(connection, f"/slices/{job}/file", name)
        summary = fetch(connection, f"/slices/{job}/summary", name)
    finally:
        connection.close()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.gcode.3mf"
    path.write_bytes(sliced)
    (out_dir / f"{name}.summary.json").write_bytes(summary)
    return path


def follow(connection, job):
    """The last progress report of the slice job's event stream."""
    connection.request("GET", f"/slices/{job}/events")
    answer = connection.getresponse()
    last = None
    for line in answer:
        line = line.strip()
        if line.startswith(b"data:"):
            last = json.loads(line[5:])
            print(f"  {last['state']} {last.get('stage', '')} {last.get('fraction', '')} "
                  f"{last['elapsed_s']} s", file=sys.stderr, flush=True)
            if last["state"] in FINAL:
                break
    answer.close()
    return last


def fetch(connection, path, name):
    connection.request("GET", path)
    answer = connection.getresponse()
    body = answer.read()
    if answer.status != 200:
        raise SliceFailed(f"{name}: {path} answered HTTP {answer.status} ({sentence(json.loads(body or b'{}'))}")
    return body


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="the slice service, for example http://127.0.0.1:23456")
    parser.add_argument("--plate", action="append", help="a plate to slice (all three when left out)")
    parser.add_argument("--out", default=str(SLICED_DIR))
    parser.add_argument("--write-plates", action="store_true", help="write the plate configurations and stop")
    parser.add_argument("--plates-dir", default=str(PLATES_DIR))
    args = parser.parse_args(argv)
    if args.write_plates:
        write_plates(args.plates_dir)
        return 0
    known = plate_configurations()
    for name in args.plate or known:
        if name not in known:
            print(f"{name} is not one of: {', '.join(sorted(known))}", file=sys.stderr)
            return 2
    if not args.url:
        print("--url is needed: the address of a slice service started by hand", file=sys.stderr)
        return 2
    for name in args.plate or known:
        print(f"{name}: slicing", file=sys.stderr, flush=True)
        try:
            path = slice_plate(args.url, name, args.out)
        except SliceFailed as failed:
            print(failed, file=sys.stderr)
            return 1
        print(f"{name}: {path} ({path.stat().st_size:,} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
