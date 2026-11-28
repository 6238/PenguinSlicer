#!/usr/bin/env python3
"""Small real sliced files for the layer preview's tests.

The layer preview's fast tests and its tests in Chromium read real sliced files, small enough
to commit: one hex spacer with supports off (a few layers), and an Elevator Block Top with an
Elevator Block Carriage beside it, supports on (every one of the four groups). Their plate
configurations are written into this folder as `<name>.json` (`--write-plates`); a slice service
started by hand on the same machine, as wizard/trials/preview/README.md says for the trial's
plates, slices each through its HTTP interface with the trial's own client
(wizard/trials/make_sliced_files.py), and the sliced files are saved here as
`<name>.gcode.3mf` with their summaries. The files are committed with their SHA-256 in
README.md, which the fast suite checks.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "trials"))

import make_sliced_files as trial  # noqa: E402  (the trial's client, by path)


def plate_configurations():
    """{plate name: plate configuration}, for the layer preview's tests."""
    centre_x, centre_y = trial.PLATE_CENTRE
    spacer = [trial.instance("hex-spacer", centre_x, centre_y)]
    pair = [trial.instance("elevator-block-top", centre_x - 60, centre_y),
            trial.instance("elevator-block-carriage", centre_x + 60, centre_y)]
    return {"spacer-1": trial.configuration("spacer-1", spacer, False),
            "pair-supports": trial.configuration("pair-supports", pair, True)}


def write_plates(folder=HERE):
    for name, plate in plate_configurations().items():
        (Path(folder) / f"{name}.json").write_text(json.dumps(plate, indent=1) + "\n")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="the slice service, for example http://127.0.0.1:23456")
    parser.add_argument("--write-plates", action="store_true", help="write the plate configurations and stop")
    args = parser.parse_args(argv)
    if args.write_plates:
        write_plates()
        return 0
    if not args.url:
        print("--url is needed: the address of a slice service started by hand", file=sys.stderr)
        return 2
    for name, plate in plate_configurations().items():
        print(f"{name}: slicing", file=sys.stderr, flush=True)
        try:
            path = trial.slice_plate(args.url, name, HERE, plate=plate)
        except trial.SliceFailed as failed:
            print(failed, file=sys.stderr)
            return 1
        print(f"{name}: {path} ({path.stat().st_size:,} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
