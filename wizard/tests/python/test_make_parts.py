"""The trials' made parts: wizard/trials/make_parts.py writes hub-150k.stl and hex-spacer.stl
deterministically, and the committed files are exactly what it writes."""
import math
import struct
from collections import Counter
from pathlib import Path

import pytest

from trials import make_parts

PARTS = Path(__file__).resolve().parents[2] / "trials" / "parts"
INCH = 25.4


def read_stl(data):
    count = struct.unpack_from("<I", data, 80)[0]
    assert len(data) == 84 + 50 * count
    triangles = []
    for k in range(count):
        values = struct.unpack_from("<12f", data, 84 + 50 * k)
        triangles.append((values[0:3], (values[3:6], values[6:9], values[9:12])))
    return triangles


def assert_closed_and_outward(triangles):
    """Every edge is used by exactly two triangles, once each way, and the signed volume is
    positive (wound outwards)."""
    edges = Counter()
    volume = 0.0
    for _, (a, b, c) in triangles:
        for p, q in ((a, b), (b, c), (c, a)):
            edges[(p, q)] += 1
        volume += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                   + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    for (p, q), n in edges.items():
        assert n == 1, f"edge {p}-{q} used {n} times the same way"
        assert edges.get((q, p)) == 1, f"edge {p}-{q} has no opposite"
    assert volume > 0
    return volume


def assert_normals_agree(triangles):
    for normal, (a, b, c) in triangles:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        length = math.sqrt(sum(x * x for x in n))
        assert length > 0, "a degenerate triangle"
        assert sum(normal[i] * n[i] / length for i in range(3)) > 0.999


def bounds(triangles):
    points = [p for _, tri in triangles for p in tri]
    return [(min(p[i] for p in points), max(p[i] for p in points)) for i in range(3)]


@pytest.fixture(scope="module")
def hub():
    return read_stl(make_parts.hub_stl())


@pytest.fixture(scope="module")
def spacer():
    return read_stl(make_parts.hex_spacer_stl())


def test_the_hub_has_exactly_150000_triangles(hub):
    assert len(hub) == 150_000


def test_the_hub_is_closed_and_wound_outwards(hub):
    volume = assert_closed_and_outward(hub)
    # A 40 x 20 mm ring with a 12 mm bore and 3 mm fillets: a little under the plain ring.
    plain = math.pi * (20.0 ** 2 - 6.0 ** 2) * 20.0
    assert 0.9 * plain < volume < plain


def test_the_hubs_normals_agree_with_its_winding(hub):
    assert_normals_agree(hub)


def test_the_hub_is_40_across_and_20_tall_with_its_base_on_the_plate(hub):
    (x0, x1), (y0, y1), (z0, z1) = bounds(hub)
    assert x1 - x0 == pytest.approx(40.0, abs=1e-3)
    assert y1 - y0 == pytest.approx(40.0, abs=1e-3)
    assert (z0, z1) == (0.0, 20.0)
    on_plate = [t for t in hub if all(p[2] == 0.0 for p in t[1])]
    assert len(on_plate) > 1000, "the flat base is not on z = 0"


def test_the_hub_has_a_12_mm_bore(hub):
    radii = [math.hypot(p[0], p[1]) for _, tri in hub for p in tri]
    assert min(radii) == pytest.approx(6.0, abs=1e-3)
    assert max(radii) == pytest.approx(20.0, abs=1e-3)


def test_the_spacer_has_216_triangles(spacer):
    assert len(spacer) == 216


def test_the_spacer_is_closed_and_wound_outwards(spacer):
    assert_closed_and_outward(spacer)
    assert_normals_agree(spacer)


def test_the_spacer_fits_a_3_8_inch_hex_shaft_and_is_5_8_inch_across_and_1_8_inch_thick(spacer):
    (x0, x1), (y0, y1), (z0, z1) = bounds(spacer)
    assert x1 - x0 == pytest.approx(5 / 8 * INCH, abs=1e-4)
    assert (z0, z1) == (0.0, pytest.approx(1 / 8 * INCH, abs=1e-5))
    points = {p for _, tri in spacer for p in tri}
    inner = sorted({round(math.hypot(p[0], p[1]), 4) for p in points})
    corner = 3 / 8 * INCH / 2 / math.cos(math.pi / 6)
    assert inner[0] == pytest.approx(corner, abs=1e-4)
    assert inner[-1] == pytest.approx(5 / 16 * INCH, abs=1e-4)


def test_writing_twice_gives_the_same_bytes():
    assert make_parts.hub_stl() == make_parts.hub_stl()
    assert make_parts.hex_spacer_stl() == make_parts.hex_spacer_stl()


def test_the_committed_parts_are_what_the_script_writes(tmp_path):
    make_parts.write_parts(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["hex-spacer.stl", "hub-150k.stl"]
    for name in ("hub-150k.stl", "hex-spacer.stl"):
        assert (PARTS / name).read_bytes() == (tmp_path / name).read_bytes(), (
            f"{name} differs from make_parts.py's output: run make -C wizard trials-parts")
