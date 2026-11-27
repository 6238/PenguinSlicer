"""The real parts in contracts/examples/parts/real/ are the ones its README lists, unchanged."""
import hashlib
import re
import struct
from pathlib import Path

REAL = Path(__file__).resolve().parents[3] / "contracts" / "examples" / "parts" / "real"
ROW = re.compile(r"^\| `([a-z0-9-]+\.stl)` \| [^|]+ \| ([\d,]+) \| [^|]+ \| `([0-9a-f]{64})` \|$")


def listed():
    rows = [ROW.match(line) for line in (REAL / "README.md").read_text().splitlines()]
    return {m.group(1): (int(m.group(2).replace(",", "")), m.group(3)) for m in rows if m}


def test_the_readme_lists_the_eight_parts():
    assert sorted(listed()) == [
        "clamp-plate-inner.stl", "elevator-block-bottom-inner.stl", "elevator-block-carriage.stl",
        "elevator-block-top.stl", "elevator-top-inner.stl", "inner-spacer.stl", "outer-clamp.stl",
        "pulley-v3.stl"]


def test_every_stl_in_the_folder_is_listed():
    assert sorted(p.name for p in REAL.glob("*.stl")) == sorted(listed())


def test_each_part_has_its_listed_hash_and_triangles():
    for name, (triangles, sha256) in listed().items():
        data = (REAL / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == sha256, name
        assert struct.unpack_from("<I", data, 80)[0] == triangles, name
        assert len(data) == 84 + 50 * triangles, name
