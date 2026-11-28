"""Where the checkout's pieces are. The suite runs each component from its own project's
environment and reads only the contracts' examples and the slice service's stand-in Orca, a
script it runs, never a module it imports."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SLICE = ROOT / "slice"
FRONT = ROOT / "front"
EXAMPLES = ROOT / "contracts" / "examples"
REAL_PARTS = EXAMPLES / "parts" / "real"

#: Each component's own environment, made by `make -C <component> install`. The suite runs
#: its Python directly rather than through `uv run`, so that a signal the suite sends reaches
#: the server itself and not a wrapper that would pass it on a second time.
SLICE_PYTHON = SLICE / ".venv" / "bin" / "python"
FRONT_PYTHON = FRONT / ".venv" / "bin" / "python"

#: The slice service's stand-in for Orca's command line (slice/tests/fake_orca.py), run with
#: Python by a wrapper the suite writes: the file is not executable by itself.
FAKE_ORCA = SLICE / "tests" / "fake_orca.py"
#: The pinned real Orca, installed by `make -C slice install-orca`.
REAL_ORCA = SLICE / "tools" / "orca" / "orca-slicer"
