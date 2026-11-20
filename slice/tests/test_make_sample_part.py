"""The fixed sample part is a small, closed, binary STL in millimetres."""
import struct

from make_sample_part import write_l_bracket
from penguin_slice.slicer import SAMPLE_STL


def read_triangles(data):
    count = struct.unpack("<I", data[80:84])[0]
    return [struct.unpack("<12fH", data[84 + i * 50: 84 + (i + 1) * 50])[3:12] for i in range(count)]


def test_generator_writes_twenty_triangle_l_bracket(tmp_path):
    path = tmp_path / "part.stl"
    assert write_l_bracket(path) == 20
    data = path.read_bytes()
    assert len(data) == 84 + 20 * 50
    values = read_triangles(data)
    xs = [t[i] for t in values for i in (0, 3, 6)]
    ys = [t[i] for t in values for i in (1, 4, 7)]
    zs = [t[i] for t in values for i in (2, 5, 8)]
    assert (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)) == (0.0, 40.0, 0.0, 30.0, 0.0, 12.0)


def test_mesh_is_closed(tmp_path):
    # Every directed edge must be matched by its reverse exactly once.
    path = tmp_path / "part.stl"
    write_l_bracket(path)
    edges = {}
    for t in read_triangles(path.read_bytes()):
        a, b, c = t[0:3], t[3:6], t[6:9]
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(u, v)] = edges.get((u, v), 0) + 1
    for (u, v), n in edges.items():
        assert n == 1, f"edge {u}->{v} used {n} times"
        assert edges.get((v, u), 0) == 1, f"edge {u}->{v} has no twin"


def test_checked_in_stl_matches_generator(tmp_path):
    path = tmp_path / "part.stl"
    write_l_bracket(path)
    assert SAMPLE_STL.read_bytes() == path.read_bytes()
