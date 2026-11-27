#!/usr/bin/env python3
"""Fail, naming the version, when Node is older than 24.

The wizard's fast suite runs on Node's own test runner (`node --test`), which needs Node 24
or later. Usage: check_node.py [NODE]; NODE defaults to `node`. Standard library only, so
that it runs before the project's environment exists.
"""
import re
import subprocess
import sys

MIN_MAJOR = 24
NEED = f"the wizard's tests need Node {MIN_MAJOR} or later."


def check(version_text):
    """None when `version_text` (what `node --version` prints) is Node 24 or later, else the
    sentence that says why not."""
    text = version_text.strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", text)
    if not match:
        return f"Could not read Node's version from {text!r}: {NEED}"
    if int(match.group(1)) < MIN_MAJOR:
        return f"Node {text[1:]} is older than {MIN_MAJOR}: {NEED}"
    return None


def main(argv):
    node = argv[1] if len(argv) > 1 else "node"
    try:
        result = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, PermissionError):
        print(f"Node was not found as {node!r}: {NEED}", file=sys.stderr)
        return 1
    message = check(result.stdout)
    if message:
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
