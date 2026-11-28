"""The small real sliced files of the layer preview's tests, in wizard/tests/sliced/: the files its
README lists, unchanged, and plate configurations that are what wizard/tests/sliced/make_sliced.py
writes, so that the files can be made again from them."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

SLICED = Path(__file__).resolve().parents[1] / "sliced"
ROW = re.compile(r"^\| `([a-z0-9-]+)\.gcode\.3mf` \| [^|]+ \| ([\d,]+) \| `([0-9a-f]{64})` \|$")


def make_sliced():
    spec = importlib.util.spec_from_file_location("make_sliced", SLICED / "make_sliced.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def listed():
    rows = [ROW.match(line) for line in (SLICED / "README.md").read_text().splitlines()]
    return {m.group(1): (int(m.group(2).replace(",", "")), m.group(3)) for m in rows if m}


def test_the_readme_lists_every_sliced_file_and_each_has_its_size_and_hash():
    assert sorted(listed()) == sorted(p.name.removesuffix(".gcode.3mf") for p in SLICED.glob("*.gcode.3mf"))
    assert sorted(listed()) == ["pair-supports", "spacer-1"]
    for name, (size, sha256) in listed().items():
        data = (SLICED / f"{name}.gcode.3mf").read_bytes()
        assert len(data) == size, name
        assert hashlib.sha256(data).hexdigest() == sha256, name


def test_the_committed_plates_are_what_the_script_writes(tmp_path):
    module = make_sliced()
    module.write_plates(tmp_path)
    for name in module.plate_configurations():
        assert json.loads((tmp_path / f"{name}.json").read_text()) == json.loads((SLICED / f"{name}.json").read_text()), name


def test_each_sliced_file_has_its_plate_configuration_and_summary():
    for name in listed():
        assert (SLICED / f"{name}.json").is_file(), name
        summary = json.loads((SLICED / f"{name}.summary.json").read_text())
        assert summary["instances"] == len(json.loads((SLICED / f"{name}.json").read_text())["instances"]), name


def test_the_script_needs_the_slice_service_address():
    assert make_sliced().main([]) == 2
