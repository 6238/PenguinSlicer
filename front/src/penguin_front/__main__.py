"""The front server's one command: serve PenguinSlicer's address.

    uv run --project front python -m penguin_front serve [--host 127.0.0.1] [--port 8600]

The settings come from the environment (settings.py); a setting it refuses stops the start
before it listens, with a message naming the setting on standard error and exit status 2.
"""

import argparse
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8600


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="python -m penguin_front",
                                     description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    serve_cmd = commands.add_parser("serve", help="serve PenguinSlicer's address")
    serve_cmd.add_argument("--host", default=DEFAULT_HOST)
    serve_cmd.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args(argv)


def main(argv=None, environ=None, stdout=None, stderr=None):
    from .server import serve

    args = parse_args(sys.argv[1:] if argv is None else argv)
    return serve(args, environ=environ, stdout=stdout or sys.stdout,
                 stderr=stderr or sys.stderr)


if __name__ == "__main__":  # pragma: no cover - the command line's entry
    sys.exit(main())
