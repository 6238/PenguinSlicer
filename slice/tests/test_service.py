"""service.py: reading and checking a plate job, and slicing it through a fake Orca."""
import copy as copying
import json
from pathlib import Path

import pytest

from helpers import box_stl, install_fake_orca, write_plate_job
from penguin_slice import error_report, limits, service
from penguin_slice.mesh import MeshError
from penguin_slice.plate_3mf import LEFT_OFF_MESSAGE
from penguin_slice.print_config import CHOOSE_PROFILES_MESSAGE, OverrideError, ProfileError
from penguin_slice.service import (BAD_JOB_MESSAGE, PART_NOT_LISTED_MESSAGE, PlateJobRefused, read_plate_job,
                                   slice_plate_job)
from penguin_slice.slicer import DEFAULT_PROFILES, SliceError

P4 = "Bambu Lab H2S 0.4 nozzle"


def plate_job(**changes):
    job = {
        "parts": {"box": {"name": "Box", "stl": "box.stl"}, "peg": {"name": "Peg", "stl": "peg.stl"}},
        "copies": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0},
                   {"ref": "box", "orientation": "+z", "angle": 90, "x": 100, "y": 50.0},
                   {"ref": "peg", "orientation": "+x", "angle": 15, "x": 150.0, "y": 50.0}],
        "local_time": "20261009-1432",
    }
    job.update(changes)
    return job


@pytest.fixture
def base(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    (folder / "box.stl").write_bytes(box_stl(20, 20, 10))
    (folder / "peg.stl").write_bytes(box_stl(8, 8, 30))
    return folder


def refused(data, base):
    with pytest.raises(PlateJobRefused) as caught:
        read_plate_job(data, base)
    return caught.value


class TestRead:
    def test_good_plate_job_becomes_a_plate_job(self, base):
        job = read_plate_job(plate_job(), base)
        assert [c["ref"] for c in job.copies] == ["box", "box", "peg"]
        assert job.parts["box"].stl_path == base / "box.stl"
        assert job.parts["box"].triangles == 12
        assert set(job.parts["box"].footprints) == {"+z", "-z", "+x", "-x", "+y", "-y"}
        assert job.triangles() == 36
        assert job.profiles == DEFAULT_PROFILES
        assert job.overrides == {}
        assert job.delivered_name == "Box_plus1-20261009-1432.gcode.3mf"

    def test_only_the_copy_fields_are_kept(self, base):
        data = plate_job()
        data["copies"][0]["colour"] = "red"
        data["unknown"] = 1
        assert set(read_plate_job(data, base).copies[0]) == {"ref", "orientation", "angle", "x", "y"}

    def test_parts_no_copy_names_are_not_read(self, base):
        data = plate_job()
        data["parts"]["unused"] = {"name": "Unused", "stl": "missing.stl"}
        assert set(read_plate_job(data, base).parts) == {"box", "peg"}

    def test_absolute_stl_path(self, base, tmp_path):
        data = plate_job()
        data["parts"]["box"]["stl"] = str(base / "box.stl")
        data["parts"]["peg"]["stl"] = str(base / "peg.stl")
        assert read_plate_job(data, tmp_path / "elsewhere").parts["box"].stl_path == base / "box.stl"

    def test_catalog_profiles_and_overrides(self, base):
        job = read_plate_job(plate_job(printer=P4, filament="Bambu PLA Basic @BBL H2S",
                                       process="0.20mm Standard @BBL H2S",
                                       overrides={"infill": 40, "brim": "off"}), base)
        assert job.profiles.printer.name == "Bambu_Lab_H2S_0.4_nozzle.json"
        assert job.overrides == {"sparse_infill_density": "40%", "brim_type": "no_brim"}
        assert (job.filament, job.process) == ("Bambu PLA Basic @BBL H2S", "0.20mm Standard @BBL H2S")

    @pytest.mark.parametrize("change", [
        lambda d: "not an object",
        lambda d: dict(d, copies=[]),
        lambda d: dict(d, copies="box"),
        lambda d: {k: v for k, v in d.items() if k != "copies"},
        lambda d: dict(d, parts=[]),
        lambda d: {k: v for k, v in d.items() if k != "parts"},
        lambda d: d["copies"][0].update(orientation="up"),
        lambda d: d["copies"][0].update(angle=360),
        lambda d: d["copies"][0].update(angle=-1),
        lambda d: d["copies"][0].update(angle=45.0),
        lambda d: d["copies"][0].update(angle=True),
        lambda d: d["copies"][0].update(x="50"),
        lambda d: d["copies"][0].update(y=float("nan")),
        lambda d: d["copies"][0].update(x=True),
        lambda d: d["copies"][0].update(x=10 ** 400),             # an integer no float can hold
        lambda d: d["copies"][0].update(y=-(10 ** 400)),
        lambda d: d["copies"][0].update(ref="has space"),
        lambda d: d["copies"][0].update(ref="x" * 65),
        lambda d: d["copies"][0].update(ref="box\n"),
        lambda d: d["copies"][0].pop("y"),
        lambda d: d["copies"].append("box"),
        lambda d: d["parts"]["box"].update(name=""),
        lambda d: d["parts"]["box"].update(name=None),
        lambda d: d["parts"]["box"].update(stl=""),
        lambda d: d["parts"]["box"].pop("stl"),
        lambda d: d["parts"].update({"bad key": {"name": "X", "stl": "x.stl"}}),
        lambda d: d["parts"].update(box="box.stl"),
    ])
    def test_fields_refused(self, base, change):
        data = plate_job()
        result = change(data)
        if result is not None:
            data = result
        error = refused(data, base)
        assert error.message == BAD_JOB_MESSAGE == "This request could not be read."
        assert error.error_code == "slice.bad_plate_job"
        assert error.details.startswith(("the plate job is", "copies is", "copy 0 is", "copy 3 is", "parts is",
                                          "part 'box' is", "part 'bad key' is")), error.details

    def test_large_integer_coordinate_is_a_refusal_not_a_bug(self, base):
        data = plate_job()
        data["copies"][1]["x"] = 10 ** 400
        report = error_report(refused(data, base))
        assert report["code"] == "slice.bad_plate_job"
        assert report["detail"].startswith("copy 1 is not {ref, orientation, angle, x, y} with valid values")

    def test_large_but_finite_integer_is_a_number(self, base):
        data = plate_job()
        data["copies"][2]["x"] = 10 ** 300            # a float holds it; the placement refuses it
        assert refused(data, base).error_code == "slice.placement_off_plate"

    def test_too_many_copies(self, base):
        copies = [{"ref": "peg", "orientation": "+z", "angle": 0, "x": 20.0 + 15 * i, "y": 20.0}
                  for i in range(limits.MAX_COPIES + 1)]
        error = refused(plate_job(copies=copies), base)
        assert error.message == "Up to 25 copies per plate; print the rest in a second job."
        assert error.details == "26 copies, cap 25"

    def test_exactly_max_copies_pass_this_check(self, base):
        copies = [{"ref": "peg", "orientation": "+z", "angle": 0, "x": 20.0 + 15 * (i % 20), "y": 20.0 + 15 * (i // 20)}
                  for i in range(limits.MAX_COPIES)]
        assert len(read_plate_job(plate_job(copies=copies), base).copies) == limits.MAX_COPIES

    def test_copy_naming_no_listed_part(self, base):
        data = plate_job()
        data["copies"][2]["ref"] = "gear"
        error = refused(data, base)
        assert error.message == PART_NOT_LISTED_MESSAGE
        assert error.error_code == "slice.part_missing"
        assert error.details == "copy 2 names part 'gear', which parts does not list"

    def test_missing_stl_file(self, base):
        (base / "peg.stl").unlink()
        error = refused(plate_job(), base)
        assert (error.error_code, error.message) == ("slice.part_missing", "The file for Peg is missing.")
        assert error.details == f"part 'peg': no STL file at {base / 'peg.stl'}"
        assert error.where == {"part": "Peg"}

    def test_stl_file_that_cannot_be_opened(self, base, monkeypatch):
        # A permission the server lacks. Path.read_bytes is replaced for the one file, so the
        # test does not depend on the user running it (root reads anything).
        real_read_bytes = Path.read_bytes

        def read_bytes(path):
            if path.name == "peg.stl":
                raise PermissionError(13, "Permission denied", str(path))
            return real_read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", read_bytes)
        report = error_report(refused(plate_job(), base))
        assert (report["code"], report["message"]) == ("slice.part_unreadable", "The file for Peg could not be opened.")
        assert report["where"] == {"part": "Peg", "stage": "checking"}
        assert report["detail"] == f"part 'peg': [Errno 13] Permission denied: '{base / 'peg.stl'}'"

    def test_stl_over_the_byte_cap_is_refused_before_it_is_read(self, base, monkeypatch):
        with open(base / "peg.stl", "r+b") as fh:
            fh.truncate(limits.MAX_PART_BYTES + 1)
        read = []
        real_read = service.read_binary_stl

        def recording_read(data, name, source):
            read.append((data, name))
            return real_read(data, name, source)

        monkeypatch.setattr(service, "read_binary_stl", recording_read)
        with pytest.raises(MeshError) as caught:
            read_plate_job(plate_job(), base)
        assert caught.value.message == "Peg is too detailed to print here (over 150,000 triangles)."
        assert caught.value.details == f"{base / 'peg.stl'}: 7,500,085 bytes, cap 7,500,084"
        assert [args[1] for args in read] == ["Box"]            # Box read; Peg refused unread

    @pytest.mark.parametrize("data, message, detail", [
        (b"solid peg\nendsolid peg\n", "The file for Peg could not be read as a part.",
         "23 bytes, shorter than the 84-byte header of a binary STL"),
        (box_stl(8, 8, 0.05), "Peg is too small to print (under 0.1 mm).",
         "8.0 x 8.0 x 0.05 mm, every side must be over 0.1 mm"),
    ])
    def test_unusable_stl(self, base, data, message, detail):
        (base / "peg.stl").write_bytes(data)
        with pytest.raises(MeshError) as caught:
            read_plate_job(plate_job(), base)
        assert caught.value.message == message
        assert caught.value.details == f"{base / 'peg.stl'}: {detail}"

    def test_job_triangles_cap(self, base, monkeypatch):
        # The three copies hold 36 triangles; the cap is lowered rather than the parts made
        # 150,000 triangles each, which would only make the test slow.
        monkeypatch.setattr(limits, "MAX_JOB_TRIANGLES", 35)
        error = refused(plate_job(), base)
        assert error.message == "These copies are too detailed to slice together; lower the quantities."
        assert error.details == "36 triangles over 3 copies, cap 35"
        monkeypatch.setattr(limits, "MAX_JOB_TRIANGLES", 36)
        assert read_plate_job(plate_job(), base).triangles() == 36

    def test_unknown_printer(self, base):
        with pytest.raises(ProfileError) as caught:
            read_plate_job(plate_job(printer="Bambu Lab X9"), base)
        assert "Bambu Lab X9" in caught.value.message

    def test_filament_not_for_this_printer(self, base):
        with pytest.raises(ProfileError) as caught:
            read_plate_job(plate_job(printer=P4, filament="Generic PETG @BBL H2S",
                                     process="0.24mm Balanced Quality @BBL H2S 0.6 nozzle"), base)
        assert caught.value.message == CHOOSE_PROFILES_MESSAGE

    def test_bad_overrides(self, base):
        with pytest.raises(OverrideError) as caught:
            read_plate_job(plate_job(overrides={"infill": 25}), base)
        assert caught.value.details == "override 'infill' is 25, not one of [10, 15, 20, 30, 40, 60, 100]"

    @pytest.mark.parametrize("copies, rule, message, where", [
        ([{"ref": "box", "orientation": "+z", "angle": 0, "x": 5.0, "y": 50.0}], "off_plate",
         "Box #1 is not fully on the plate.", {"part": "Box", "copy": "Box #1"}),
        ([{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0},
          {"ref": "box", "orientation": "+z", "angle": 0, "x": 72.0, "y": 50.0}], "too_close",
         "Box #1 and Box #2 are closer than 5 mm.", {"part": "Box", "copy": "Box #1"}),
    ])
    def test_placement_refused_with_its_rule(self, base, copies, rule, message, where):
        error = refused(plate_job(copies=copies), base)
        assert (error.rule, error.message, error.where) == (rule, message, where)
        assert error.details == message

    def test_too_tall(self, base):
        (base / "peg.stl").write_bytes(box_stl(8, 8, 345))
        data = plate_job()
        data["copies"][2]["orientation"] = "+z"
        error = refused(data, base)
        assert error.rule == "too_tall"
        assert error.message == "Peg #1 is taller than the printer can print (340 mm)."
        assert error.where == {"part": "Peg", "copy": "Peg #1"}

    def test_every_placement_problem_is_in_the_details(self, base):
        copies = [{"ref": "box", "orientation": "+z", "angle": 0, "x": 5.0, "y": 50.0},
                  {"ref": "box", "orientation": "+z", "angle": 0, "x": 20.0, "y": 50.0}]
        error = refused(plate_job(copies=copies), base)
        assert error.details == "Box #1 is not fully on the plate.; Box #1 and Box #2 are closer than 5 mm."


class TestSlice:
    def test_slices_into_the_output_folder_and_removes_scratch(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        sliced = slice_plate_job(write_plate_job(base, plate_job(), {}), out)
        assert sliced.path == out / "Box_plus1-20261009-1432.gcode.3mf"
        assert sliced.path.is_file()
        assert sliced.summary == {"file": "Box_plus1-20261009-1432.gcode.3mf", "copies": 3, "print_time_s": 600.0,
                                  "filament_m": 1.5, "filament_g": 4.5, "layer_count": 42, "warnings": []}
        assert sorted(p.name for p in out.iterdir()) == [sliced.path.name]

    def test_json_value_with_base_dir(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        sliced = slice_plate_job(plate_job(), tmp_path / "a" / "b", base_dir=base)
        assert sliced.path.parent == (tmp_path / "a" / "b").resolve()

    def test_json_value_without_base_dir_reads_against_the_current_folder(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        monkeypatch.chdir(base)
        assert slice_plate_job(plate_job(), tmp_path / "out").summary["copies"] == 3

    def test_copy_left_off_by_orca_fails_and_leaves_nothing(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "drop")
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_job(write_plate_job(base, plate_job(), {}), out)
        assert caught.value.message == LEFT_OFF_MESSAGE
        assert caught.value.details == "expected 3 objects, found 2; missing ['Peg #1']; unexpected []"
        assert list(out.iterdir()) == []

    def test_orca_refusal_fails_and_leaves_nothing(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "refuse")
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_job(write_plate_job(base, plate_job(), {}), out)
        assert (caught.value.code, caught.value.message) == (-101, "Parts are too close together; spread them out.")
        # Orca's own reason (result.json's error_string) is kept before the scratch folder goes.
        assert caught.value.details == ("exit code 155\norca error_string: too close\n"
                                        "Some objects are too close together")
        assert list(out.iterdir()) == []

    def test_orca_output_that_is_not_utf8_is_kept_not_fatal(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "garbled")
        with pytest.raises(SliceError) as caught:
            slice_plate_job(write_plate_job(base, plate_job(), {}), tmp_path / "out")
        report = error_report(caught.value)
        assert report["code"] == "slice.orca_too_close"
        assert "Br�cket is too close" in report["detail"]

    def test_output_folder_that_is_a_file(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        out.write_text("not a folder")
        with pytest.raises(SliceError) as caught:
            slice_plate_job(write_plate_job(base, plate_job(), {}), out)
        report = error_report(caught.value)
        assert (report["code"], report["message"]) == ("slice.output_unwritable",
                                                       "The print server could not save the sliced file.")
        assert str(out) in report["detail"]
        assert out.read_text() == "not a folder"

    def test_folder_with_the_sliced_files_name_is_not_success(self, base, tmp_path, monkeypatch):
        # shutil.move would have put the file inside the folder and reported the folder.
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        (out / "Box_plus1-20261009-1432.gcode.3mf").mkdir(parents=True)
        with pytest.raises(SliceError) as caught:
            slice_plate_job(write_plate_job(base, plate_job(), {}), out)
        report = error_report(caught.value)
        assert report["code"] == "slice.output_unwritable"
        assert "Box_plus1-20261009-1432.gcode.3mf" in report["detail"]
        assert [p.name for p in out.iterdir()] == ["Box_plus1-20261009-1432.gcode.3mf"]     # scratch removed
        assert list((out / "Box_plus1-20261009-1432.gcode.3mf").iterdir()) == []

    def test_stl_that_vanishes_after_the_check(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        real_read = service.read_plate_job

        def read_then_lose_the_stl(data, base_dir):
            job = real_read(data, base_dir)
            (base / "peg.stl").unlink()
            return job

        monkeypatch.setattr(service, "read_plate_job", read_then_lose_the_stl)
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_job(write_plate_job(base, plate_job(), {}), out)
        report = error_report(caught.value)
        assert (report["code"], report["message"], report["where"]) == (
            "slice.part_missing", "The file for Peg is missing.", {"part": "Peg", "stage": "checking"})
        assert list(out.iterdir()) == []

    def test_orca_gets_absolute_paths_and_no_arrange(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        seen = {}
        real_run = __import__("subprocess").run

        def spy(cmd, **kwargs):
            seen["cmd"], seen["cwd"] = cmd, kwargs["cwd"]
            return real_run(cmd, **kwargs)

        monkeypatch.setattr("penguin_slice.slicer.subprocess.run", spy)
        slice_plate_job(write_plate_job(base, plate_job(), {}), tmp_path / "out")
        cmd = seen["cmd"]
        assert cmd[cmd.index("--arrange") + 1] == "0" and cmd[cmd.index("--orient") + 1] == "0"
        assert cmd[-1].endswith("/plate.3mf") and cmd[-1].startswith(str((tmp_path / "out").resolve()))

    def test_refusal_happens_before_any_output_folder_is_made(self, base, tmp_path):
        out = tmp_path / "out"
        with pytest.raises(PlateJobRefused):
            slice_plate_job(plate_job(copies=[]), out, base_dir=base)
        assert not out.exists()

    def test_unreadable_plate_job_file(self, tmp_path):
        path = tmp_path / "plate-job.json"
        path.write_text("{not json")
        with pytest.raises(PlateJobRefused) as caught:
            slice_plate_job(path, tmp_path / "out")
        assert caught.value.message == BAD_JOB_MESSAGE
        assert caught.value.details.startswith(f"{path}: Expecting property name")

    def test_missing_plate_job_file(self, tmp_path):
        with pytest.raises(PlateJobRefused) as caught:
            slice_plate_job(str(tmp_path / "nope.json"), tmp_path / "out")
        assert caught.value.message == BAD_JOB_MESSAGE
        assert "No such file or directory" in caught.value.details

    def test_existing_file_of_the_same_name_is_replaced(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        out.mkdir()
        (out / "Box_plus1-20261009-1432.gcode.3mf").write_text("old")
        sliced = slice_plate_job(write_plate_job(base, plate_job(), {}), out)
        assert sliced.path.read_bytes()[:2] == b"PK"


def test_plate_job_value_is_not_changed(base):
    data = plate_job()
    before = copying.deepcopy(data)
    read_plate_job(data, base)
    assert data == before
    assert json.dumps(data)
