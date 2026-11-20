"""The slice service's command line.

    uv run python -m penguin_slice slice <plate-job.json> --out <dir>

Prints the sliced file's summary as JSON on stdout and exits 0, or prints the error
report as JSON on stderr and exits 1.
"""
import argparse
import json
import sys

from .errors import error_report
from .service import slice_plate_job


def main(argv=None, stdout=None, stderr=None):
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    parser = argparse.ArgumentParser(prog="python -m penguin_slice", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    slice_cmd = commands.add_parser("slice", help="slice a plate job into a sliced file")
    slice_cmd.add_argument("plate_job", help="the plate job file (JSON)")
    slice_cmd.add_argument("--out", required=True, help="the directory the sliced file is written to")
    args = parser.parse_args(argv)
    try:
        sliced = slice_plate_job(args.plate_job, args.out)
    except Exception as exc:  # every failure leaves as an error report
        print(json.dumps(error_report(exc), indent=2), file=stderr)
        return 1
    print(json.dumps(sliced.summary, indent=2), file=stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
