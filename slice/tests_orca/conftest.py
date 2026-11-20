"""The tests that run the real Orca Slicer: `make test-orca`. Orca must be installed
(`make install`), at slice/tools/orca or where PENGUIN_SLICE_ORCA points."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _path in (ROOT / "tests", ROOT / "scripts"):        # helpers.py and the scripts
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from penguin_slice.slicer import orca_bin  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def orca_installed():
    if not orca_bin().is_file():
        pytest.fail(f"Orca Slicer is missing at {orca_bin()}; run `make install`")
