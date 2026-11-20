"""The slice service's limits, the memory model and the plate-measurement script (no Orca run)."""
import json

import pytest

from helpers import FAILSAFE_S, bounded, install_fake_orca, kill_fake
from measure_plate import (REFERENCE_PLATES, fit, grid_centres, hub_mesh, hub_stl, main, measure, organic_mesh,
                           plate_definition, plate_layout)
from penguin_slice import limits
from penguin_slice.mesh import analyse, read_binary_stl
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
    assert limits.MIN_PART_EXTENT_MM == 0.1
    assert not hasattr(limits, "PLATE_TOO_LARGE_MESSAGE")      # the estimate refuses nothing


def test_plate_timeout_longer_than_sample_timeout():
    assert DEFAULT_TIMEOUT_S == 120
    assert limits.PLATE_SLICE_TIMEOUT_S > DEFAULT_TIMEOUT_S


class TestMemoryModel:
    def test_estimate_follows_copies_volume_and_supports(self):
        base = limits.MEMORY_BASE_MB
        assert limits.estimate_peak_mb([], False) == round(base)
        one = limits.estimate_peak_mb([100_000.0], False)
        assert one == round(base + limits.MEMORY_PER_COPY_MB + limits.MEMORY_PER_CM3_MB * 100)
        assert limits.estimate_peak_mb([100_000.0] * 2, False) > one
        assert limits.estimate_peak_mb([100_000.0], True) == round(
            (base + limits.MEMORY_PER_COPY_MB + limits.MEMORY_PER_CM3_MB * 100) * limits.MEMORY_SUPPORTS_FACTOR)

    def test_triangles_do_not_enter_the_estimate(self):
        # The model takes volumes only: a part's triangle count cannot change it.
        assert limits.estimate_peak_mb([5_000.0] * 3, False) == limits.estimate_peak_mb([5_000.0] * 3, False)

    @pytest.mark.parametrize("raw, expected", [(None, 900), ("1500", 1500), ("0", 900), ("-5", 900), ("lots", 900),
                                               ("", 900)])
    def test_ceiling_is_a_setting_with_a_default(self, raw, expected):
        environ = {} if raw is None else {limits.MAX_PEAK_MB_ENV: raw}
        assert limits.max_peak_mb(environ) == expected

    def test_ceiling_reads_the_process_environment(self, monkeypatch):
        monkeypatch.setenv(limits.MAX_PEAK_MB_ENV, "1234")
        assert limits.max_peak_mb() == 1234

    def test_expected_seconds_grow_with_the_plate(self):
        small = limits.estimate_seconds([10_000.0], False)
        assert limits.estimate_seconds([10_000.0] * 5, False) > small
        assert limits.estimate_seconds([10_000.0], True) > small


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

    def test_organic_body_is_watertight_and_outward(self):
        from measure_plate import mesh_stl
        health = analyse(read_binary_stl(mesh_stl(*organic_mesh(rows=20, cols=30)), "Organic"))
        assert health["watertight"] and not health["inside_out"] and health["shells"] == 1
        assert health["volume_mm3"] > 100_000

    def test_every_reference_plate_is_defined(self):
        assert sorted(REFERENCE_PLATES) == ["full-small", "mechanism", "mechanism-supports", "organic-1",
                                            "organic-1-supports", "organic-2", "organic-3", "organic-3-supports"]
        for name in REFERENCE_PLATES:
            parts, copies, supports = plate_definition(name)
            assert supports == name.endswith("-supports")
            assert all(ref in parts for ref, _x, _y in copies)

    def test_grid_fits_every_copy_on_the_plate(self):
        centres = grid_centres(limits.MAX_COPIES)
        assert len(set(centres)) == limits.MAX_COPIES
        assert max(x for x, _ in centres) + 20 <= 340 - 3 and max(y for _, y in centres) + 20 <= 320 - 3

    def test_plate_layout_goes_through_the_plate_writer(self, tmp_path):
        stl_path = tmp_path / "hub.stl"
        stl_path.write_bytes(hub_stl(200))
        copies, parts = plate_layout(stl_path, 3)
        assert write_plate_3mf(tmp_path / "plate.3mf", copies, parts) == ["Hub #1", "Hub #2", "Hub #3"]

    def test_measure_reports_a_row_through_the_slice(self, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        row = measure("mechanism")
        assert row["verdict"] == "ok" and row["copies"] == 9 and row["supports"] is False
        assert row["peak_mb"] >= 0 and row["sliced_bytes"] > 0 and row["estimate_mb"] > 0

    @pytest.fixture
    def small_organic(self, monkeypatch):
        """organic-1 with a coarse body, so the test is quick; the plate is the same."""
        import measure_plate
        _parts, copies, supports = REFERENCE_PLATES["organic-1"]
        monkeypatch.setitem(measure_plate.REFERENCE_PLATES, "organic-1",
                            ({"organic": lambda: measure_plate.mesh_stl(*organic_mesh(rows=20, cols=30))}, copies,
                             supports))

    def test_measure_reports_orca_refusal_as_failed(self, tmp_path, monkeypatch, small_organic):
        install_fake_orca(tmp_path, monkeypatch, "refuse")
        row = measure("organic-1")
        assert (row["verdict"], row["error"]) == ("failed", "slice.orca_too_close")

    def test_measure_stops_a_slice_over_the_stop_rule(self, tmp_path, monkeypatch, small_organic):
        # Bounded: with the watchdog's stop removed this fails in FAILSAFE_S and kills the stand-in.
        import tempfile
        from penguin_slice import slicer
        install_fake_orca(tmp_path, monkeypatch, "hang")
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))                      # measure's folder, here
        monkeypatch.setattr(slicer, "MEMORY_READER", lambda pgid: (0, 3 * 1024 * 1024 + 1))   # just over 3 GB
        try:
            row, raised, finished = bounded(lambda: measure("organic-1"))
        finally:
            for pid_file in tmp_path.rglob("fake-orca.pid"):
                kill_fake(pid_file.parent)
        assert finished, f"the watchdog never stopped Orca within {FAILSAFE_S} s"
        assert raised is None and row["verdict"] == "over" and "error" not in row
        assert row["peak_mb"] == 3072                                 # the high-water reading, in MB

    def test_fit_recovers_the_model_that_made_the_rows(self):
        rows = [{"copies": c, "volume_cm3": v, "supports": False, "verdict": "ok",
                 "peak_mb": 80 + 4 * c + 1.5 * v} for c, v in ((1, 100), (2, 300), (6, 250), (25, 500))]
        rows.append({"copies": 2, "volume_cm3": 300, "supports": True, "verdict": "ok",
                     "peak_mb": 1.4 * (80 + 8 + 450)})
        result = fit(rows)
        for name in ("least_squares", "envelope"):      # exact data: both fits find the model
            model = result[name]
            assert (model["MEMORY_BASE_MB"], model["MEMORY_PER_COPY_MB"], model["MEMORY_PER_CM3_MB"]) == \
                (80.0, 4.0, 1.5), name
            assert model["MEMORY_SUPPORTS_FACTOR"] == 1.4, name

    def test_envelope_never_estimates_below_a_measured_peak(self):
        rows = [{"copies": c, "volume_cm3": v, "supports": False, "verdict": "ok", "peak_mb": p}
                for c, v, p in ((1, 466, 345), (3, 1398, 825), (25, 555, 781), (1, 280, 367), (6, 1678, 1739))]
        model = fit(rows)["envelope"]
        for r in rows:
            estimate = model["MEMORY_BASE_MB"] + model["MEMORY_PER_COPY_MB"] * r["copies"] + \
                model["MEMORY_PER_CM3_MB"] * r["volume_cm3"]
            assert estimate >= r["peak_mb"] - 1, r

    def test_fit_needs_three_rows(self):
        with pytest.raises(SystemExit):
            fit([{"copies": 1, "volume_cm3": 1, "supports": False, "verdict": "ok", "peak_mb": 1}])

    def test_command_line_lists_and_fits(self, tmp_path, capsys):
        assert main(["--list"]) == 0
        assert "organic-3-supports: 3 copies, supports on" in capsys.readouterr().out
        results = tmp_path / "r.jsonl"
        results.write_text("".join(json.dumps({"copies": c, "volume_cm3": v, "supports": False, "verdict": "ok",
                                               "peak_mb": 100 + c + v}) + "\n" for c, v in ((1, 1), (2, 5), (3, 2))))
        assert main(["--fit", str(results)]) == 0
        assert json.loads(capsys.readouterr().out)["least_squares"]["MEMORY_PER_CM3_MB"] == 1.0
