"""A slice service process for tests/test_orca_runner.py: slices a plate with the fake Orca
named by PENGUIN_SLICE_ORCA (mode hang), prints `orca <pid>` once Orca reports progress,
and waits to be killed.

    python service_until_killed.py <plate.3mf> <output dir>
"""
import sys
import threading
from pathlib import Path

from penguin_slice import slicer


def main(model, out):
    told = threading.Event()

    def on_progress(stage, fraction, message):
        if stage != "slicing" and not told.is_set():      # Orca's own first message: its pid is written
            told.set()
            print("orca", (Path(out) / "fake-orca.pid").read_text(), flush=True)

    slicer.slice_plate(model, slicer.DEFAULT_PROFILES, out, on_progress=on_progress)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
