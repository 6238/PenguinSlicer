"""Shared set-up for the fast suite.

Every test runs with PENGUIN_SLICE_ORCA pointing at a placeholder file in its own
temporary directory: a test that forgets to replace subprocess.run can never start the
real Orca (the placeholder is not executable, so the slice fails at once with
"The slicer could not be started."), and no test depends on whether Orca is installed.
"""
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent / "scripts"
for _path in (TESTS, SCRIPTS):          # helpers.py and the scripts, for every worker and import mode
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


@pytest.fixture(autouse=True)
def placeholder_orca(tmp_path, monkeypatch):
    path = tmp_path / "orca-placeholder" / "orca-slicer"
    path.parent.mkdir()
    path.write_text("not a program\n")
    monkeypatch.setenv("PENGUIN_SLICE_ORCA", str(path))
    return path
