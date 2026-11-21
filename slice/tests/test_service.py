"""service.py: reading and checking a plate configuration, and slicing it through a fake Orca."""
import copy as copying
import json
import os
from pathlib import Path

import pytest

from helpers import box_stl, install_fake_orca, spacer_grid, spacer_stl, write_plate_configuration
from penguin_slice import limits, service, slicer
from penguin_slice.errors import CODES, error_report
from penguin_slice import plate_configuration as plate_configuration_module
from penguin_slice.mesh import MeshError
from penguin_slice.plate_3mf import LEFT_OFF_MESSAGE
from penguin_slice.print_config import CHOOSE_PROFILES_MESSAGE, OverrideError, ProfileError
from penguin_slice.service import (BAD_CONFIGURATION_MESSAGE, PART_NOT_LISTED_MESSAGE, PlateConfigurationRefused, read_plate_configuration,
                                   slice_plate_configuration)
from penguin_slice.slicer import DEFAULT_PROFILES, SliceError

P4 = "Bambu Lab H2S 0.4 nozzle"


def plate_configuration(**changes):
    job = {
        "parts": {"box": {"name": "Box", "stl": "box.stl"}, "peg": {"name": "Peg", "stl": "peg.stl"}},
        "instances": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0},
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
    with pytest.raises(PlateConfigurationRefused) as caught:
        read_plate_configuration(data, base)
    return caught.value


def refused_confined(data, base):
    with pytest.raises(PlateConfigurationRefused) as caught:
        read_plate_configuration(data, base, confine_to=base)
    return caught.value


class TestRead:
    def test_good_plate_configuration_becomes_a_plate_configuration(self, base):
        job = read_plate_configuration(plate_configuration(), base)
        assert [c["ref"] for c in job.instances] == ["box", "box", "peg"]
        assert job.parts["box"].stl_path == base / "box.stl"
        assert job.parts["box"].triangles == 12
        assert set(job.parts["box"].footprints) == {"+z", "-z", "+x", "-x", "+y", "-y"}
        assert job.triangles() == 36
        assert job.profiles == DEFAULT_PROFILES
        assert job.overrides == {}
        assert job.delivered_name == "Box_plus1-20261009-1432.gcode.3mf"

    @pytest.mark.parametrize("stl", ["box.stl\u0000x", "b" * 5000, "parts/" + "c" * 256 + ".stl",
                                     "é" * 128 + ".stl"])
    def test_an_stl_that_is_no_usable_file_name_is_a_bad_plate_configuration(self, base, stl):
        # Once "The slicer failed unexpectedly" (ValueError: embedded null byte, ENAMETOOLONG).
        error = refused(plate_configuration(parts={"box": {"name": "Box", "stl": stl}}), base)
        assert error.error_code == "slice.bad_plate_configuration"
        assert error.message == "This plate configuration could not be read: part 'box' has an stl that is not a usable " \
                                "file name (got " + repr(stl)[:120] + ")."

    def test_a_long_stl_within_the_limits_is_only_missing(self, base):
        error = refused(plate_configuration(parts={"box": {"name": "Box", "stl": "d" * 255}}), base)
        assert error.error_code == "slice.part_missing"

    @pytest.mark.parametrize("change, detail", [
        (lambda d: d["instances"][0].update(colour="red"),
         "instance 0 has fields this plate configuration format does not have: colour"),
        (lambda d: d.update(overides={"supports": "on"}),
         "it has fields this plate configuration format does not have: overides"),
        (lambda d: d["parts"]["box"].update(units="inch"),
         "part 'box' has fields this plate configuration format does not have: units"),
    ])
    def test_a_field_that_is_not_listed_is_refused_not_ignored(self, base, change, detail):
        # A misspelled `overrides` once meant no overrides at all, silently.
        data = plate_configuration()
        change(data)
        error = refused(data, base)
        assert error.details == detail
        assert error.message == f"This plate configuration could not be read: {detail}."

    def test_parts_no_instance_names_are_not_read(self, base):
        data = plate_configuration()
        data["parts"]["unused"] = {"name": "Unused", "stl": "missing.stl"}
        assert set(read_plate_configuration(data, base).parts) == {"box", "peg"}

    def test_absolute_stl_path(self, base, tmp_path):
        data = plate_configuration()
        data["parts"]["box"]["stl"] = str(base / "box.stl")
        data["parts"]["peg"]["stl"] = str(base / "peg.stl")
        assert read_plate_configuration(data, tmp_path / "elsewhere").parts["box"].stl_path == base / "box.stl"

    def test_catalog_profiles_and_overrides(self, base):
        job = read_plate_configuration(plate_configuration(printer=P4, filament="Bambu PLA Basic @BBL H2S",
                                       process="0.20mm Standard @BBL H2S",
                                       overrides={"infill": 40, "brim": "off"}), base)
        assert job.profiles.printer.name == "Bambu_Lab_H2S_0.4_nozzle.json"
        assert job.overrides == {"sparse_infill_density": "40%", "brim_type": "no_brim"}
        assert (job.filament, job.process) == ("Bambu PLA Basic @BBL H2S", "0.20mm Standard @BBL H2S")

    @pytest.mark.parametrize("change", [
        lambda d: "not an object",
        lambda d: dict(d, instances=[]),
        lambda d: dict(d, instances="box"),
        lambda d: {k: v for k, v in d.items() if k != "instances"},
        lambda d: dict(d, parts=[]),
        lambda d: {k: v for k, v in d.items() if k != "parts"},
        lambda d: d["instances"][0].update(orientation="up"),
        lambda d: d["instances"][0].update(angle=360),
        lambda d: d["instances"][0].update(angle=-1),
        lambda d: d["instances"][0].update(angle=45.0),
        lambda d: d["instances"][0].update(angle=True),
        lambda d: d["instances"][0].update(x="50"),
        lambda d: d["instances"][0].update(y=float("nan")),
        lambda d: d["instances"][0].update(x=True),
        lambda d: d["instances"][0].update(x=10 ** 400),             # an integer no float can hold
        lambda d: d["instances"][0].update(y=-(10 ** 400)),
        lambda d: d["instances"][0].update(ref="has space"),
        lambda d: d["instances"][0].update(ref="x" * 65),
        lambda d: d["instances"][0].update(ref="box\n"),
        lambda d: d["instances"][0].pop("y"),
        lambda d: d["instances"].append("box"),
        lambda d: d["parts"]["box"].update(name=""),
        lambda d: d["parts"]["box"].update(name=None),
        lambda d: d["parts"]["box"].update(stl=""),
        lambda d: d["parts"]["box"].pop("stl"),
        lambda d: d["parts"].update({"bad key": {"name": "X", "stl": "x.stl"}}),
        lambda d: d["parts"].update(box="box.stl"),
    ])
    def test_fields_refused(self, base, change):
        data = plate_configuration()
        result = change(data)
        if result is not None:
            data = result
        error = refused(data, base)
        assert error.message == BAD_CONFIGURATION_MESSAGE.format(problem=error.details)
        assert error.error_code == "slice.bad_plate_configuration"
        assert error.details.startswith(("it is not", "it has no instances", "instance 0 has", "instance 3 is", "its parts",
                                          "part 'box' has", "part 'box' is", "part key 'bad key'")), error.details

    @pytest.mark.parametrize("change, detail", [
        (lambda d: d["instances"][0].update(orientation="up"),
         "instance 0 has an orientation that is not one of +z, -z, +x, -x, +y, -y (got 'up')"),
        (lambda d: d["instances"][0].update(angle=360), "instance 0 has an angle that is not a whole number from 0 to 359 "
                                                     "(got 360)"),
        (lambda d: d["instances"][0].update(x="50"), "instance 0 has a position x that is not a finite number (got '50')"),
        (lambda d: d["instances"][0].update(ref=None), "instance 0 has no valid ref (got None)"),
        (lambda d: d["parts"]["box"].update(name=""), "part 'box' has no name (got '')"),
        (lambda d: d.update(parts={"box": "box.stl"}), "part 'box' is not an object"),
    ])
    def test_the_refusal_says_what_is_wrong(self, base, change, detail):
        data = plate_configuration()
        change(data)
        assert refused(data, base).details == detail

    def test_a_part_name_over_the_limit_is_refused(self, base):
        # A name of 300,000 characters was once accepted: 300 kB in each log line and in the
        # sentence to the student.
        data = plate_configuration()
        data["parts"]["box"]["name"] = "N" * 300_000
        error = refused(data, base)
        assert error.error_code == "slice.bad_plate_configuration"
        assert error.message == ("This plate configuration could not be read: part 'box' has a name of 300,000 characters, "
                                 "longer than the 200 a part name may have.")

    def test_a_part_name_at_the_limit_is_read(self, base):
        data = plate_configuration()
        data["parts"]["box"]["name"] = "N" * service.MAX_PART_NAME_CHARS
        assert read_plate_configuration(data, base).parts["box"].name == "N" * 200

    @pytest.mark.parametrize("field", ["printer", "filament", "process"])
    def test_a_profile_name_over_the_limit_is_refused(self, base, field):
        error = refused(plate_configuration(**{field: "P" * 300_000}), base)
        assert error.error_code == "slice.bad_plate_configuration"
        assert error.message == (f"This plate configuration could not be read: its {field} is a name of 300,000 characters, "
                                 f"longer than the 200 a profile name may have.")

    @pytest.mark.parametrize("printer", [["x"] * 100_000, "deep"])
    def test_a_printer_that_is_not_a_name_gives_a_short_sentence(self, base, printer):
        if printer == "deep":
            printer = []
            for _ in range(100_000):
                printer = [printer]
        with pytest.raises(ProfileError) as caught:
            read_plate_configuration(plate_configuration(printer=printer), base)
        report = error_report(caught.value)
        assert report["code"] == "slice.unknown_printer"
        assert len(report["message"]) < 200 and len(report["detail"]) < 400

    def test_filament_and_process_that_are_not_names_give_a_short_detail(self, base):
        with pytest.raises(ProfileError) as caught:
            read_plate_configuration(plate_configuration(printer=P4, filament=["x"] * 100_000, process={"a": "y" * 100_000}), base)
        assert caught.value.message == CHOOSE_PROFILES_MESSAGE and len(caught.value.details) < 400

    def test_no_caller_text_makes_a_sentence_or_detail_grow_without_bound(self, base):
        # Every text field of a plate configuration at a hostile length: each refusal stays short.
        huge = "Z" * 300_000
        cases = [lambda d: d["parts"]["box"].update(name=huge), lambda d: d["parts"]["box"].update(stl=huge),
                 lambda d: d["parts"].update({huge: {"name": "X", "stl": "x.stl"}}),
                 lambda d: d["instances"][0].update(ref=huge), lambda d: d["instances"][0].update(orientation=huge),
                 lambda d: d["instances"][0].update(x=huge), lambda d: d.update({huge: 1}),
                 lambda d: d["instances"][0].update({huge: 1}), lambda d: d["parts"]["box"].update({huge: 1}),
                 lambda d: d.update(printer=huge), lambda d: d.update(overrides={huge: "on"}),
                 lambda d: d.update(overrides={"supports": huge})]
        for change in cases:
            data = plate_configuration()
            change(data)
            with pytest.raises(Exception) as caught:      # noqa: PT011 - each is its own refusal
                read_plate_configuration(data, base)
            report = error_report(caught.value)
            assert report["code"] != "slice.unexpected", report
            assert len(report["message"]) < 300 and len(report["detail"]) < 2000, report["code"]

    def test_large_integer_coordinate_is_a_refusal_not_a_bug(self, base):
        data = plate_configuration()
        data["instances"][1]["x"] = 10 ** 400
        report = error_report(refused(data, base))
        assert report["code"] == "slice.bad_plate_configuration"
        assert report["detail"].startswith("instance 1 has a position x that is not a finite number")

    def test_a_value_nested_too_deeply_to_print_is_still_a_refusal(self, base):
        data = plate_configuration()
        deep = []
        for _ in range(100_000):
            deep = [deep]
        data["instances"][0]["x"] = deep
        assert refused(data, base).details == ("instance 0 has a position x that is not a finite number "
                                               "(got a value nested too deeply)")

    def test_large_but_finite_integer_is_a_number(self, base):
        data = plate_configuration()
        data["instances"][2]["x"] = 10 ** 300            # a float holds it; the placement refuses it
        assert refused(data, base).error_code == "slice.placement_off_plate"

    def test_too_many_instances(self, base):
        instances = [{"ref": "peg", "orientation": "+z", "angle": 0, "x": 20.0 + 15 * i, "y": 20.0}
                     for i in range(limits.MAX_INSTANCES + 1)]
        error = refused(plate_configuration(instances=instances), base)
        assert error.error_code == "slice.too_many_instances"
        assert error.message == ("This plate has 151 instances; the slicer takes up to 150 on one plate, so print "
                                 "the rest on a second plate.")
        assert error.details == "151 instances, cap 150"

    def test_the_reference_plate_of_100_spacers_is_accepted(self, base):
        # A team's 10 by 10 grid of hex shaft spacers: one part, one STL file, 100 instances.
        (base / "spacer.stl").write_bytes(spacer_stl())
        data = {"parts": {"spacer": {"name": "Spacer", "stl": "spacer.stl"}}, "instances": spacer_grid(100)}
        configuration = read_plate_configuration(data, base, confine_to=base)
        assert len(configuration.instances) == 100 and list(configuration.parts) == ["spacer"]
        assert configuration.labels[0] == "Spacer #1" and configuration.labels[-1] == "Spacer #100"
        assert configuration.parts["spacer"].health["watertight"] and configuration.part_warnings() == []
        assert configuration.parts["spacer"].health["size_mm"] == pytest.approx([15.875, 15.875, 3.175])

    def test_the_most_instances_of_spacers_are_accepted_and_one_more_refused(self, base):
        (base / "spacer.stl").write_bytes(spacer_stl())
        parts = {"spacer": {"name": "Spacer", "stl": "spacer.stl"}}
        grid = spacer_grid(limits.MAX_INSTANCES + 1, side=13, pitch_mm=21.5)
        accepted = read_plate_configuration({"parts": parts, "instances": grid[:-1]}, base)
        assert len(accepted.instances) == limits.MAX_INSTANCES
        error = refused({"parts": parts, "instances": grid}, base)
        assert (error.error_code, error.message) == (
            "slice.too_many_instances", "This plate has 151 instances; the slicer takes up to 150 on one plate, so "
                                        "print the rest on a second plate.")

    def test_too_many_different_parts(self, base):
        parts = {f"p{i}": {"name": f"P{i}", "stl": "peg.stl"} for i in range(limits.MAX_PARTS + 1)}
        instances = [{"ref": f"p{i}", "orientation": "+z", "angle": 0, "x": 20.0 + 15 * (i % 20),
                      "y": 20.0 + 15 * (i // 20)} for i in range(limits.MAX_PARTS + 1)]
        error = refused({"parts": parts, "instances": instances}, base)
        assert (error.error_code, error.details) == ("slice.too_many_parts", "26 different parts, cap 25")
        assert error.message == ("This plate uses 26 different parts; the slicer takes up to 25 on one plate, so "
                                 "print the rest on a second plate.")
        parts.pop(f"p{limits.MAX_PARTS}")                       # 25 parts pass this check
        assert len(read_plate_configuration({"parts": parts, "instances": instances[:-1]}, base).parts) == 25

    def test_no_cap_on_the_triangles_of_the_whole_plate(self, base, monkeypatch):
        # Unmeasured, it only added a way to refuse: the memory watchdog decides such plates.
        # The part reader is replaced, so no 7.5 MB part is read; the placement is not this test's.
        monkeypatch.setattr(service, "_read_part", lambda key, part, *a, **k: service.CheckedPart(
            name=part["name"], stl_path=base / part["stl"], footprints={}, triangles=limits.MAX_PART_TRIANGLES,
            health={"volume_mm3": 1.0}))
        monkeypatch.setattr(service, "check_placement", lambda *a: [])
        instances = [{"ref": "box", "orientation": "+z", "angle": 0, "x": 100.0, "y": 100.0}] * limits.MAX_INSTANCES
        configuration = read_plate_configuration(plate_configuration(instances=instances), base)
        assert configuration.triangles() == limits.MAX_INSTANCES * limits.MAX_PART_TRIANGLES == 22_500_000
        assert not hasattr(limits, "MAX_PLATE_TRIANGLES") and "slice.plate_too_detailed" not in CODES

    def test_instances_piled_on_one_spot_give_a_bounded_detail(self, base):
        # 150 instances on one spot are 11,175 pairs too close; the detail lists 20 of them.
        instances = [{"ref": "peg", "orientation": "+z", "angle": 0, "x": 100.0, "y": 100.0}] * limits.MAX_INSTANCES
        error = refused(plate_configuration(instances=instances), base)
        assert error.error_code == "slice.placement_too_close"
        assert error.details.count("closer than") == 20
        assert error.details.endswith("; and 11,155 more") and len(error.details) < 2_000

    def test_exactly_max_instances_pass_this_check(self, base):
        instances = [{"ref": "peg", "orientation": "+z", "angle": 0, "x": 20.0 + 15 * (i % 20), "y": 20.0 + 15 * (i // 20)}
                  for i in range(limits.MAX_INSTANCES)]
        assert len(read_plate_configuration(plate_configuration(instances=instances), base).instances) == limits.MAX_INSTANCES

    def test_instance_naming_no_listed_part(self, base):
        data = plate_configuration()
        data["instances"][2]["ref"] = "gear"
        error = refused(data, base)
        assert error.message == PART_NOT_LISTED_MESSAGE
        assert error.error_code == "slice.part_missing"
        assert error.details == "instance 2 names part 'gear', which parts does not list"

    def test_missing_stl_file(self, base):
        (base / "peg.stl").unlink()
        error = refused(plate_configuration(), base)
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
        report = error_report(refused(plate_configuration(), base))
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
            read_plate_configuration(plate_configuration(), base)
        assert caught.value.message == "Peg is too detailed to print here (over 150,000 triangles)."
        assert caught.value.details == f"{base / 'peg.stl'}: 7,500,085 bytes, cap 7,500,084"
        assert [args[1] for args in read] == ["Box"]            # Box read; Peg refused unread

    @pytest.mark.parametrize("data, message, detail", [
        (b"solid peg\nendsolid peg\n", "The file for Peg is not an STL file.",
         "23 bytes of text, starting b'solid peg\\nendsolid peg\\n'"),
        (box_stl(8, 8, 0.05), "Peg is flat: it is 0.05 mm thick, too thin to print.",
         "8.0 x 8.0 x 0.05 mm, every side must be over 0.1 mm"),
    ])
    def test_unusable_stl(self, base, data, message, detail):
        (base / "peg.stl").write_bytes(data)
        with pytest.raises(MeshError) as caught:
            read_plate_configuration(plate_configuration(), base)
        assert caught.value.message == message
        assert caught.value.details == f"{base / 'peg.stl'}: {detail}"

    def test_a_memory_estimate_over_the_ceiling_refuses_nothing(self, base, monkeypatch):
        # The estimate is rough (a 100 mm solid cube: 1,158 MB estimated, 269 MB measured),
        # so it is only logged; the watchdog guards memory while Orca runs.
        monkeypatch.setenv(limits.MAX_PEAK_MB_ENV, "180")
        job = read_plate_configuration(plate_configuration(), base)
        estimate = limits.estimate_peak_mb([4000.0, 4000.0, 1920.0], False)
        assert job.estimated_peak_mb == estimate > 180
        assert job.memory_ceiling_mb == 180
        assert (job.describe()["estimated_peak_mb"], job.describe()["memory_ceiling_mb"]) == (estimate, 180)

    def test_a_solid_block_the_old_estimate_refused_is_read(self, base):
        (base / "peg.stl").write_bytes(box_stl(150, 150, 150))
        job = read_plate_configuration(plate_configuration(instances=[{"ref": "peg", "orientation": "+z", "angle": 0, "x": 170.0,
                                                "y": 160.0}]), base)
        assert job.estimated_peak_mb > limits.DEFAULT_MAX_PEAK_MB and job.memory_ceiling_mb == 2000

    def test_supports_raise_the_estimate(self, base):
        off = read_plate_configuration(plate_configuration(overrides={"supports": "off"}), base)
        on = read_plate_configuration(plate_configuration(overrides={"supports": "on"}), base)
        assert (off.supports_on, on.supports_on) == (False, True)
        assert on.estimated_peak_mb > off.estimated_peak_mb and on.expected_s > off.expected_s

    def test_a_part_that_fits_no_orientation_is_refused_by_name(self, base):
        (base / "peg.stl").write_bytes(box_stl(400, 400, 400))
        with pytest.raises(MeshError) as caught:
            read_plate_configuration(plate_configuration(), base)
        assert caught.value.error_code == "slice.part_too_large"
        assert caught.value.message == ("Peg is 400 x 400 x 400 mm, larger than the printer can print in any "
                                        "orientation (340.0 x 320.0 x 340.0 mm).")

    def test_a_long_part_that_fits_only_turned_is_not_refused_as_too_large(self, base):
        # 400 mm long: it fits the 340 x 320 plate only on the diagonal, so the part check
        # lets it through and the placement decides.
        (base / "peg.stl").write_bytes(box_stl(400, 10, 10))
        data = plate_configuration(instances=[{"ref": "peg", "orientation": "+z", "angle": 43, "x": 170.0, "y": 160.0}])
        assert read_plate_configuration(data, base).parts["peg"].name == "Peg"

    def test_stl_paths_can_be_confined_to_a_folder(self, base, tmp_path):
        outside = tmp_path / "outside.stl"
        outside.write_bytes(box_stl(8, 8, 30))
        data = plate_configuration()
        data["parts"]["peg"]["stl"] = "../outside.stl"
        error = refused_confined(data, base)
        assert (error.error_code, error.message) == (
            "slice.part_missing", "The file for Peg is not one of the files sent with this plate configuration.")
        data["parts"]["peg"]["stl"] = str(outside)
        assert refused_confined(data, base).error_code == "slice.part_missing"
        assert read_plate_configuration(plate_configuration(), base, confine_to=base).parts["peg"].stl_path == (base / "peg.stl").resolve()

    def test_part_warnings_travel_with_the_plate_configuration(self, base):
        (base / "peg.stl").write_bytes(box_stl(2, 1, 0.5))
        job = read_plate_configuration(plate_configuration(), base)
        assert [w["code"] for w in job.part_warnings()] == ["slice.part_maybe_inches"]
        assert job.part_warnings()[0]["message"] == ("Peg is only 2.0 x 1.0 x 0.5 mm; if it was drawn in inches, "
                                                     "export it again in millimetres.")
        assert job.describe()["parts"]["peg"]["warnings"] == ["slice.part_maybe_inches"]

    def test_unknown_printer(self, base):
        with pytest.raises(ProfileError) as caught:
            read_plate_configuration(plate_configuration(printer="Bambu Lab X9"), base)
        assert "Bambu Lab X9" in caught.value.message

    def test_filament_not_for_this_printer(self, base):
        with pytest.raises(ProfileError) as caught:
            read_plate_configuration(plate_configuration(printer=P4, filament="Generic PETG @BBL H2S",
                                     process="0.24mm Balanced Quality @BBL H2S 0.6 nozzle"), base)
        assert caught.value.message == CHOOSE_PROFILES_MESSAGE

    def test_bad_overrides(self, base):
        with pytest.raises(OverrideError) as caught:
            read_plate_configuration(plate_configuration(overrides={"infill": 25}), base)
        assert caught.value.details == "override 'infill' is 25, not one of [10, 15, 20, 30, 40, 60, 100]"

    @pytest.mark.parametrize("instances, rule, message, where", [
        ([{"ref": "box", "orientation": "+z", "angle": 0, "x": 5.0, "y": 50.0}], "off_plate",
         "Box #1 is not fully on the plate.", {"part": "Box", "instance": "Box #1"}),
        ([{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0},
          {"ref": "box", "orientation": "+z", "angle": 0, "x": 72.0, "y": 50.0}], "too_close",
         "Box #1 and Box #2 are closer than 5 mm.", {"part": "Box", "instance": "Box #1", "other_instance": "Box #2"}),
    ])
    def test_placement_refused_with_its_rule(self, base, instances, rule, message, where):
        error = refused(plate_configuration(instances=instances), base)
        assert (error.rule, error.message, error.where) == (rule, message, where)
        assert error.details == message

    def test_too_tall(self, base):
        (base / "peg.stl").write_bytes(box_stl(8, 8, 345))
        data = plate_configuration()
        data["instances"][2]["orientation"] = "+z"
        error = refused(data, base)
        assert error.rule == "too_tall"
        assert error.message == "Peg #1 is taller than the printer can print (340 mm)."
        assert error.where == {"part": "Peg", "instance": "Peg #1"}

    def test_every_placement_problem_is_in_the_details(self, base):
        instances = [{"ref": "box", "orientation": "+z", "angle": 0, "x": 5.0, "y": 50.0},
                  {"ref": "box", "orientation": "+z", "angle": 0, "x": 20.0, "y": 50.0}]
        error = refused(plate_configuration(instances=instances), base)
        assert error.details == "Box #1 is not fully on the plate.; Box #1 and Box #2 are closer than 5 mm."


class TestSlice:
    def test_slices_into_the_output_folder_and_removes_scratch(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        sliced = slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out)
        assert sliced.path == out / "Box_plus1-20261009-1432.gcode.3mf"
        assert sliced.path.is_file()
        assert sliced.summary == {"file": "Box_plus1-20261009-1432.gcode.3mf", "instances": 3, "print_time_s": 600.0,
                                  "filament_m": 1.5, "filament_g": 4.5, "layer_count": 42, "warnings": [],
                                  "part_warnings": []}
        assert sorted(p.name for p in out.iterdir()) == [sliced.path.name]
        assert sliced.peak_rss_kb > 0

    def test_json_value_with_base_dir(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        sliced = slice_plate_configuration(plate_configuration(), tmp_path / "a" / "b", base_dir=base)
        assert sliced.path.parent == (tmp_path / "a" / "b").resolve()

    def test_json_value_without_base_dir_reads_against_the_current_folder(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        monkeypatch.chdir(base)
        assert slice_plate_configuration(plate_configuration(), tmp_path / "out").summary["instances"] == 3

    def test_instance_left_off_by_orca_fails_and_leaves_nothing(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "drop")
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out)
        assert caught.value.message == LEFT_OFF_MESSAGE
        assert caught.value.details == "expected 3 objects, found 2; missing ['Peg #1']; unexpected []"
        assert list(out.iterdir()) == []

    def test_orca_refusal_fails_and_leaves_nothing(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "refuse")
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out)
        assert (caught.value.code, caught.value.message) == (
            -101, "Two instances are too close together: the slicer found that their paths would meet.")
        # Orca's own reason (result.json's error_string) is kept before the scratch folder goes.
        assert caught.value.details == ("exit code 155\norca error_string: too close\n"
                                        "Some objects are too close together")
        assert list(out.iterdir()) == []

    def test_orca_output_that_is_not_utf8_is_kept_not_fatal(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "garbled")
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), tmp_path / "out")
        report = error_report(caught.value)
        assert report["code"] == "slice.orca_too_close"
        assert "Br�cket is too close" in report["detail"]

    def test_output_folder_that_is_a_file(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        out.write_text("not a folder")
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out)
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
            slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out)
        report = error_report(caught.value)
        assert report["code"] == "slice.output_unwritable"
        assert "Box_plus1-20261009-1432.gcode.3mf" in report["detail"]
        assert [p.name for p in out.iterdir()] == ["Box_plus1-20261009-1432.gcode.3mf"]     # scratch removed
        assert list((out / "Box_plus1-20261009-1432.gcode.3mf").iterdir()) == []

    def test_stl_that_vanishes_after_the_check(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        real_read = service.read_plate_configuration

        def read_then_lose_the_stl(data, base_dir):
            job = real_read(data, base_dir)
            (base / "peg.stl").unlink()
            return job

        monkeypatch.setattr(service, "read_plate_configuration", read_then_lose_the_stl)
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out)
        report = error_report(caught.value)
        assert (report["code"], report["message"], report["where"]) == (
            "slice.part_missing", "The file for Peg is missing.", {"part": "Peg", "stage": "checking"})
        assert list(out.iterdir()) == []

    def test_orca_gets_absolute_paths_and_no_arrange(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        seen = {}
        real_run = slicer.run_process

        def spy(cmd, **kwargs):
            seen["cmd"], seen["cwd"] = cmd, kwargs["cwd"]
            return real_run(cmd, **kwargs)

        monkeypatch.setattr(slicer, "run_process", spy)
        slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), tmp_path / "out")
        cmd = seen["cmd"]
        assert cmd[cmd.index("--arrange") + 1] == "0" and cmd[cmd.index("--orient") + 1] == "0"
        assert cmd[-1].endswith("/plate.3mf") and cmd[-1].startswith(str((tmp_path / "out").resolve()))

    def test_refusal_happens_before_any_output_folder_is_made(self, base, tmp_path):
        out = tmp_path / "out"
        with pytest.raises(PlateConfigurationRefused):
            slice_plate_configuration(plate_configuration(instances=[]), out, base_dir=base)
        assert not out.exists()

    def test_unreadable_plate_configuration_file(self, tmp_path):
        path = tmp_path / "plate-configuration.json"
        path.write_text("{not json")
        with pytest.raises(PlateConfigurationRefused) as caught:
            slice_plate_configuration(path, tmp_path / "out")
        assert caught.value.message == "This plate configuration could not be read: it is not a readable JSON file."
        assert caught.value.details.startswith(f"{path}: JSONDecodeError: Expecting property name")

    def test_plate_configuration_file_nested_too_deeply_for_python(self, tmp_path):
        # 100,000 nested brackets make json.loads raise RecursionError: still a bad plate configuration.
        path = tmp_path / "plate-configuration.json"
        path.write_text("[" * 100_000 + "]" * 100_000)
        with pytest.raises(PlateConfigurationRefused) as caught:
            slice_plate_configuration(path, tmp_path / "out")
        report = error_report(caught.value)
        assert report["code"] == "slice.bad_plate_configuration"
        assert report["detail"].startswith(f"{path}: RecursionError")

    def test_missing_plate_configuration_file(self, tmp_path):
        with pytest.raises(PlateConfigurationRefused) as caught:
            slice_plate_configuration(str(tmp_path / "nope.json"), tmp_path / "out")
        assert caught.value.message == "This plate configuration could not be read: it is not a readable JSON file."
        assert "No such file or directory" in caught.value.details

    def test_disk_full_while_the_plate_is_written(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")

        def full(*args, **kwargs):
            raise OSError(28, "No space left on device")
        monkeypatch.setattr(plate_configuration_module, "write_plate_3mf", full)
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out)
        report = error_report(caught.value)
        assert (report["code"], report["message"]) == ("slice.scratch_unwritable",
                                                       "The print server could not write the slicer's working files.")
        assert report["detail"] == "OSError: [Errno 28] No space left on device"
        assert report["retryable"] is True
        assert list(out.iterdir()) == []

    def test_cancel_and_progress_reach_orca(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "hang")
        stop, stages = slicer.Stop(), []

        def on_progress(stage, fraction, message):
            stages.append(stage)
            if stage == "slicing_mesh":
                stop.set("cancel")
        out = tmp_path / "out"
        with pytest.raises(slicer.SliceCancelled):
            slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out, stop=stop, on_progress=on_progress)
        assert stages == ["building_plate", "slicing", "slicing_mesh"]
        assert list(out.iterdir()) == []

    def test_scratch_of_a_dead_process_is_removed_and_ours_kept(self, tmp_path):
        ours = service.make_scratch(tmp_path)
        dead = tmp_path / "slice-999999999-5-abc"
        dead.mkdir()
        reused = tmp_path / f"slice-{os.getpid()}-1-abc"          # our pid, another start time
        reused.mkdir()
        other = tmp_path / "unrelated"
        other.mkdir()
        (tmp_path / "slice-1-2-a-file").write_text("not a folder")
        assert sorted(service.clean_stale_scratch(tmp_path)) == sorted([dead.name, reused.name])
        assert ours.is_dir() and other.is_dir() and (tmp_path / "slice-1-2-a-file").exists()
        assert service.clean_stale_scratch(tmp_path / "missing") == []

    def test_min_width_of_degenerate_hulls(self):
        assert service._min_width([]) == (0.0, 0.0)
        assert service._min_width([[0, 0], [3, 4]]) == (0.0, 4.0)
        least, diameter = service._min_width([[0, 0], [0, 0], [10, 0], [10, 2], [0, 2]])
        assert least == 2.0 and diameter == pytest.approx(10.198, abs=1e-3)

    def test_process_start_of_a_process_we_may_not_see(self, monkeypatch):
        monkeypatch.setattr(Path, "read_text", lambda p, *a, **k: (_ for _ in ()).throw(PermissionError()))
        assert service._process_start(1) is None

    def test_process_start_without_proc_of_another_users_process(self, monkeypatch):
        real_exists = Path.exists
        monkeypatch.setattr(Path, "exists", lambda p: False if str(p) == "/proc/self/stat" else real_exists(p))
        monkeypatch.setattr(Path, "read_text", lambda p, *a, **k: (_ for _ in ()).throw(FileNotFoundError()))

        def kill(pid, sig):
            raise PermissionError()
        monkeypatch.setattr(service.os, "kill", kill)
        assert service._process_start(1) == 0

    def test_a_missing_catalog_is_a_server_profile_problem(self, base, monkeypatch):
        from penguin_slice import print_config
        monkeypatch.setattr(print_config, "load_catalog", lambda: print_config.Catalog.load(base / "no-catalog"))
        with pytest.raises(ProfileError) as caught:
            read_plate_configuration(plate_configuration(printer=P4, filament="Bambu PLA Basic @BBL H2S",
                                     process="0.20mm Standard @BBL H2S"), base)
        assert caught.value.error_code == "slice.profile_unreadable"
        assert caught.value.details.startswith("FileNotFoundError")

    def test_process_start_without_proc(self, monkeypatch):
        real_exists = Path.exists
        monkeypatch.setattr(Path, "exists", lambda p: False if str(p) == "/proc/self/stat" else real_exists(p))
        monkeypatch.setattr(Path, "read_text", lambda p, *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
        assert service._process_start(os.getpid()) == 0
        assert service._process_start(999999999) is None

    def test_existing_file_of_the_same_name_is_replaced(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        out.mkdir()
        (out / "Box_plus1-20261009-1432.gcode.3mf").write_text("old")
        sliced = slice_plate_configuration(write_plate_configuration(base, plate_configuration(), {}), out)
        assert sliced.path.read_bytes()[:2] == b"PK"


def test_plate_configuration_value_is_not_changed(base):
    data = plate_configuration()
    before = copying.deepcopy(data)
    read_plate_configuration(data, base)
    assert data == before
    assert json.dumps(data)
