"""The slice service's limits and the plate-measurement script (no Orca run)."""
import math

from helpers import install_fake_orca
from measure_plate import grid_centres, hub_mesh, hub_stl, main, measure, plate_layout, plate_parts
from penguin_slice import limits
from penguin_slice.plate_3mf import write_plate_3mf
from penguin_slice.slicer import DEFAULT_TIMEOUT_S, _binary_triangle_count


def test_part_bytes_follow_part_triangles():
    assert limits.MAX_PART_BYTES == 7_500_084 == 84 + 50 * limits.MAX_PART_TRIANGLES


def test_copies_cap():
    assert limits.MAX_COPIES == 25


def test_sentences_follow_the_caps():
    assert limits.TOO_DETAILED_MESSAGE.format(name="Gear") == \
        "Gear is too detailed to print here (over 150,000 triangles)."
    assert limits.TOO_MANY_COPIES_MESSAGE == "Up to 25 copies per plate; print the rest in a second job."
    assert limits.TOO_SMALL_MESSAGE.format(name="Shim") == "Shim is too small to print (under 0.1 mm)."
    assert limits.MIN_PART_EXTENT_MM == 0.1


def test_one_part_always_fits_a_job():
    assert limits.MAX_JOB_TRIANGLES >= limits.MAX_PART_TRIANGLES


def test_plate_timeout_longer_than_sample_timeout():
    assert DEFAULT_TIMEOUT_S == 120
    assert limits.PLATE_SLICE_TIMEOUT_S > DEFAULT_TIMEOUT_S


class TestMeasurePlate:
    def test_hub_triangle_count_and_closed_shell(self):
        count = _binary_triangle_count(hub_stl(10_000))
        assert count is not None                      # the binary length rule holds
        assert 9_500 <= count <= 10_000
        _vertices, faces = hub_mesh(10_000)
        edges = {}
        for a, b, c in faces.tolist():
            for edge in ((a, b), (b, c), (c, a)):
                edges[edge] = edges.get(edge, 0) + 1
        # Closed and consistently wound: every directed edge once, its reverse once.
        assert all(n == 1 and edges.get((y, x)) == 1 for (x, y), n in edges.items())

    def test_plates_follow_the_limits(self):
        assert plate_parts("max-copies") == (limits.MAX_COPIES, limits.MAX_JOB_TRIANGLES // limits.MAX_COPIES)
        assert plate_parts("max-copies", triangles=275_000) == (limits.MAX_COPIES, 11_000)
        copies, part = plate_parts("max-part")
        assert part == limits.MAX_PART_TRIANGLES
        assert copies == math.ceil(limits.MAX_JOB_TRIANGLES / limits.MAX_PART_TRIANGLES)
        assert plate_parts("max-part", part_triangles=50_000) == (6, 50_000)

    def test_grid_fits_every_copy_on_the_plate(self):
        centres = grid_centres(limits.MAX_COPIES)
        assert len(set(centres)) == limits.MAX_COPIES
        assert max(x for x, _ in centres) + 20 <= 340 - 3 and max(y for _, y in centres) + 20 <= 320 - 3

    def test_measure_plate_goes_through_the_plate_writer(self, tmp_path):
        stl_path = tmp_path / "hub.stl"
        stl_path.write_bytes(hub_stl(200))
        copies, parts = plate_layout(stl_path, 3)
        assert write_plate_3mf(tmp_path / "plate.3mf", copies, parts) == ["Hub #1", "Hub #2", "Hub #3"]
        assert [(c["x"], c["y"]) for c in copies] == [(40.0, 40.0), (90.0, 40.0), (140.0, 40.0)]
        assert all(c["orientation"] == "+z" and c["angle"] == 0 for c in copies)

    def test_measure_reports_ok_through_the_slice(self, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        line, verdict = measure("max-copies", triangles=limits.MAX_COPIES * 128)
        assert verdict == "ok"
        assert line.startswith(f"plate=max-copies copies={limits.MAX_COPIES} triangles=")
        assert line.endswith(" exit=0 names=ok verdict=ok")

    def test_measure_reports_orca_refusal_as_failed(self, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "refuse")
        line, verdict = measure("max-copies", triangles=limits.MAX_COPIES * 128)
        assert verdict == "failed"
        assert " exit=-101 names=missing verdict=failed" in line

    def test_options_that_do_not_apply_are_refused(self, capsys):
        for argv in (["--plate", "max-part", "--triangles", "5"], ["--plate", "max-copies", "--part-triangles", "5"]):
            try:
                main(argv)
            except SystemExit as exc:
                assert exc.code == 2
            else:
                raise AssertionError(f"{argv} was accepted")
        assert "applies to the" in capsys.readouterr().err
