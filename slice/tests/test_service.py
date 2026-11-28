"""service.py: checking a part on arrival, reading and checking a plate configuration in its
phase 2 form against the part store, and slicing it through a fake Orca."""
import copy as copying
import json
import os
from pathlib import Path

import pytest

from helpers import (PLATE_ID, SUBMISSION_ID, USER_KEY, Parts, box_stl, install_fake_orca, part_entry, sha256,
                     spacer_grid, spacer_stl)
from penguin_slice import limits, service, slicer
from penguin_slice.errors import CODES, error_report
from penguin_slice import plate_configuration as plate_configuration_module
from penguin_slice.mesh import MeshError
from penguin_slice.plate_3mf import LEFT_OFF_MESSAGE
from penguin_slice.print_config import CHOOSE_PROFILES_MESSAGE, OverrideError, ProfileError
from penguin_slice.service import (BAD_CONFIGURATION_MESSAGE, PART_NOT_LISTED_MESSAGE, PlateConfigurationRefused,
                                   slice_plate_configuration)
from penguin_slice.slicer import DEFAULT_PROFILES, SliceError

P4 = "Bambu Lab H2S 0.4 nozzle"
BOX = box_stl(20, 20, 10)
PEG = box_stl(8, 8, 30)


def plate_configuration(**changes):
    job = {
        "plate_id": PLATE_ID, "submission_id": SUBMISSION_ID,
        "parts": {"box": part_entry("Box", BOX), "peg": part_entry("Peg", PEG)},
        "instances": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0},
                      {"ref": "box", "orientation": "+z", "angle": 90, "x": 100, "y": 50.0},
                      {"ref": "peg", "orientation": "+x", "angle": 15, "x": 150.0, "y": 50.0}],
        "local_time": "20261009-1432",
    }
    job.update(changes)
    return job


@pytest.fixture
def base(tmp_path):
    """The part store with the box and the peg uploaded under USER_KEY."""
    parts = Parts(tmp_path)
    parts.add(BOX)
    parts.add(PEG)
    return parts


def refused(data, base):
    with pytest.raises(PlateConfigurationRefused) as caught:
        base.read(data)
    return caught.value


def with_peg(base, data):
    """The plate configuration with the peg's part replaced by `data`, uploaded first."""
    base.add(data)
    configuration = plate_configuration()
    configuration["parts"]["peg"] = part_entry("Peg", data)
    return configuration


class TestRead:
    def test_good_plate_configuration_becomes_a_plate_configuration(self, base):
        job = base.read(plate_configuration())
        assert [c["ref"] for c in job.instances] == ["box", "box", "peg"]
        assert job.parts["box"].stl_path == base.store.get(USER_KEY, sha256(BOX), "mm").path
        assert job.parts["box"].triangles == 12
        assert set(job.parts["box"].footprints) == {"+z", "-z", "+x", "-x", "+y", "-y"}
        assert job.triangles() == 36
        assert job.profiles == DEFAULT_PROFILES
        assert job.overrides == {}
        assert job.delivered_name == "Box_plus1-20261009-1432.gcode.3mf"
        assert (job.plate_id, job.submission_id) == (PLATE_ID, SUBMISSION_ID)
        assert job.describe()["parts"]["box"]["sha256"] == sha256(BOX)
        assert (job.describe()["plate_id"], job.describe()["submission_id"]) == (PLATE_ID, SUBMISSION_ID)

    def test_the_contracts_phase_2_example_is_accepted_once_its_parts_are_uploaded(self, tmp_path):
        """contracts/examples/plate-configuration-phase-2.json as it is, its overrides under
        Orca's own names."""
        from helpers import CONTRACTS
        example = json.loads((CONTRACTS / "examples" / "plate-configuration-phase-2.json").read_text())
        parts = Parts(tmp_path)
        for name in ("bracket.stl", "spacer.stl"):
            parts.add((CONTRACTS / "examples" / "parts" / name).read_bytes())
        configuration = parts.read(example)
        assert configuration.overrides == example["overrides"]
        assert [c["ref"] for c in configuration.instances] == ["bracket", "bracket", "spacer", "bracket"]
        assert configuration.instances[3]["rotation"] == pytest.approx([0.707106781, -0.588348405, 0.39223227, 0.0],
                                                                       abs=1e-6)
        assert configuration.profiles.printer.name == "Bambu_Lab_H2S_0.4_nozzle.json"

    @pytest.mark.parametrize("change, detail", [
        (lambda d: d["instances"][0].update(colour="red"),
         "instance 0 has fields this plate configuration format does not have: colour"),
        (lambda d: d.update(overides={"enable_support": "1"}),
         "it has fields this plate configuration format does not have: overides"),
        (lambda d: d["parts"]["box"].update(stl="box.stl"),
         "part 'box' has fields this plate configuration format does not have: stl"),
    ])
    def test_a_field_that_is_not_listed_is_refused_not_ignored(self, base, change, detail):
        # A misspelled `overrides` once meant no overrides at all, silently.
        data = plate_configuration()
        change(data)
        error = refused(data, base)
        assert error.details == detail
        assert error.message == f"This plate configuration could not be read: {detail}."

    def test_parts_no_instance_names_are_not_looked_for(self, base):
        data = plate_configuration()
        data["parts"]["unused"] = part_entry("Unused", b"never uploaded")
        assert set(base.read(data).parts) == {"box", "peg"}

    def test_catalog_profiles_and_overrides(self, base):
        job = base.read(plate_configuration(printer=P4, filament="Bambu PLA Basic @BBL H2S",
                                            process="0.20mm Standard @BBL H2S",
                                            overrides={"sparse_infill_density": "40%", "brim_type": "no_brim"}))
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
        lambda d: {k: v for k, v in d.items() if k != "plate_id"},
        lambda d: {k: v for k, v in d.items() if k != "submission_id"},
        lambda d: d.update(plate_id=""),
        lambda d: d.update(plate_id="p" * 65),
        lambda d: d.update(plate_id="has space"),
        lambda d: d.update(submission_id=7),
        lambda d: d.update(submission_id="s\n"),
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
        lambda d: d["instances"][0].pop("orientation"),
        lambda d: d["instances"][0].update(rotation=[1.0, 0.0, 0.0, 0.0]),
        lambda d: d["instances"].append("box"),
        lambda d: d["parts"]["box"].update(name=""),
        lambda d: d["parts"]["box"].update(name=None),
        lambda d: d["parts"]["box"].pop("sha256"),
        lambda d: d["parts"]["box"].update(sha256="F" * 64),
        lambda d: d["parts"]["box"].update(sha256="f" * 63),
        lambda d: d["parts"]["box"].update(sha256="f" * 64 + "\n"),
        lambda d: d["parts"]["box"].pop("units"),
        lambda d: d["parts"]["box"].update(units="cm"),
        lambda d: d["parts"]["box"].update(units=None),
        lambda d: d["parts"].update({"bad key": part_entry("X", BOX)}),
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
        assert error.details.startswith(("it is not", "it has no instances", "its plate_id", "its submission_id",
                                         "instance 0 has", "instance 3 is", "its parts", "part 'box' has",
                                         "part 'box' is", "part key 'bad key'")), error.details

    @pytest.mark.parametrize("change, detail", [
        (lambda d: d["instances"][0].update(orientation="up"),
         "instance 0 has an orientation that is not one of +z, -z, +x, -x, +y, -y (got 'up')"),
        (lambda d: d["instances"][0].update(angle=360), "instance 0 has an angle that is not a whole number from 0 to 359 "
                                                     "(got 360)"),
        (lambda d: d["instances"][0].update(x="50"), "instance 0 has a position x that is not a finite number (got '50')"),
        (lambda d: d["instances"][0].update(ref=None), "instance 0 has no valid ref (got None)"),
        (lambda d: d["parts"]["box"].update(name=""), "part 'box' has no name (got '')"),
        (lambda d: d.update(parts={"box": "box.stl"}), "part 'box' is not an object"),
        (lambda d: d.update(plate_id=None), "its plate_id is not 1 to 64 letters, digits, - or _ (got None)"),
        (lambda d: d["parts"]["box"].update(units="cm"), "part 'box' has units that are not \"mm\" or \"in\" (got 'cm')"),
        (lambda d: d["parts"]["box"].update(sha256="abc"),
         "part 'box' has no sha256 of 64 lowercase hexadecimal characters (got 'abc')"),
        (lambda d: d["instances"][0].update(rotation=[1.0, 0.0, 0.0, 0.0]),
         "instance 0 has both an orientation and a rotation, not exactly one"),
        (lambda d: d["instances"][0].pop("orientation"), "instance 0 has neither an orientation and a rotation, "
                                                         "not exactly one"),
    ])
    def test_the_refusal_says_what_is_wrong(self, base, change, detail):
        data = plate_configuration()
        change(data)
        assert refused(data, base).details == detail

    @pytest.mark.parametrize("rotation, detail", [
        ([1.001, 0.0, 0.0, 0.0], "instance 0 has a rotation of length 1.001, not a unit quaternion (within 1e-06 of 1)"),
        ([0.999998, 0.0, 0.0, 0.0], "instance 0 has a rotation of length 0.999998, not a unit quaternion (within 1e-06 of 1)"),
        ([0.0, 0.0, 0.0, 0.0], "instance 0 has a rotation of length 0, not a unit quaternion (within 1e-06 of 1)"),
        ([1.0, 0.0, 0.0], "instance 0 has a rotation that is not a list of 4 finite numbers (got [1.0, 0.0, 0.0])"),
        ([1.0, 0.0, 0.0, 0.0, 0.0], "instance 0 has a rotation that is not a list of 4 finite numbers "
                                    "(got [1.0, 0.0, 0.0, 0.0, 0.0])"),
        ([1.0, 0.0, 0.0, "0"], "instance 0 has a rotation that is not a list of 4 finite numbers "
                               "(got [1.0, 0.0, 0.0, '0'])"),
        ([1.0, 0.0, 0.0, float("nan")], "instance 0 has a rotation that is not a list of 4 finite numbers "
                                        "(got [1.0, 0.0, 0.0, nan])"),
        ([True, 0, 0, 0], "instance 0 has a rotation that is not a list of 4 finite numbers (got [True, 0, 0, 0])"),
        ("+z", "instance 0 has a rotation that is not a list of 4 finite numbers (got '+z')"),
    ])
    def test_a_rotation_that_is_not_a_unit_quaternion_is_refused(self, base, rotation, detail):
        data = plate_configuration()
        data["instances"][0].pop("orientation")
        data["instances"][0]["rotation"] = rotation
        error = refused(data, base)
        assert (error.error_code, error.details) == ("slice.bad_plate_configuration", detail)

    def test_a_rotation_within_a_millionth_of_unit_length_is_divided_by_its_length(self, base):
        data = plate_configuration()
        data["instances"][0].pop("orientation")
        data["instances"][0]["rotation"] = [1.0000009, 0.0, 0.0, 0.0]
        job = base.read(data)
        assert job.instances[0]["rotation"] == [1.0, 0.0, 0.0, 0.0]
        assert job.parts["box"].footprints[(1.0, 0.0, 0.0, 0.0)]["hull"] == job.parts["box"].footprints["+z"]["hull"]
        assert job.describe()["instances"][0]["rotation"] == [1.0, 0.0, 0.0, 0.0]

    def test_the_id_forms_at_their_limits_are_read(self, base):
        job = base.read(plate_configuration(plate_id="P" * 64, submission_id="a-b_C9"))
        assert (job.plate_id, job.submission_id) == ("P" * 64, "a-b_C9")

    def test_a_part_name_over_the_limit_is_refused(self, base):
        # A name of 300,000 characters was once accepted: 300 kB in each log line and in the
        # sentence to the user.
        data = plate_configuration()
        data["parts"]["box"]["name"] = "N" * 300_000
        error = refused(data, base)
        assert error.error_code == "slice.bad_plate_configuration"
        assert error.message == ("This plate configuration could not be read: part 'box' has a name of 300,000 characters, "
                                 "longer than the 200 a part name may have.")

    def test_a_part_name_at_the_limit_is_read(self, base):
        data = plate_configuration()
        data["parts"]["box"]["name"] = "N" * service.MAX_PART_NAME_CHARS
        assert base.read(data).parts["box"].name == "N" * 200

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
            base.read(plate_configuration(printer=printer))
        report = error_report(caught.value)
        assert report["code"] == "slice.unknown_printer"
        assert len(report["message"]) < 200 and len(report["detail"]) < 400

    def test_filament_and_process_that_are_not_names_give_a_short_detail(self, base):
        with pytest.raises(ProfileError) as caught:
            base.read(plate_configuration(printer=P4, filament=["x"] * 100_000, process={"a": "y" * 100_000}))
        assert caught.value.message == CHOOSE_PROFILES_MESSAGE and len(caught.value.details) < 400

    def test_no_caller_text_makes_a_sentence_or_detail_grow_without_bound(self, base):
        # Every text field of a plate configuration at a hostile length: each refusal stays short.
        huge = "Z" * 300_000
        cases = [lambda d: d["parts"]["box"].update(name=huge), lambda d: d["parts"]["box"].update(sha256=huge),
                 lambda d: d["parts"]["box"].update(units=huge), lambda d: d.update(plate_id=huge),
                 lambda d: d.update(submission_id=huge),
                 lambda d: d["parts"].update({huge: part_entry("X", BOX)}),
                 lambda d: d["instances"][0].update(ref=huge), lambda d: d["instances"][0].update(orientation=huge),
                 lambda d: d["instances"][0].update(x=huge), lambda d: d.update({huge: 1}),
                 lambda d: d["instances"][0].update({huge: 1}), lambda d: d["parts"]["box"].update({huge: 1}),
                 lambda d: d.update(printer=huge), lambda d: d.update(overrides={huge: "on"}),
                 lambda d: d.update(overrides={"enable_support": huge})]
        for change in cases:
            data = plate_configuration()
            change(data)
            with pytest.raises(Exception) as caught:      # noqa: PT011 - each is its own refusal
                base.read(data)
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
        # A 10 by 10 grid of hex shaft spacers: one part, uploaded once, 100 instances.
        base.add(spacer_stl())
        data = plate_configuration(parts={"spacer": part_entry("Spacer", spacer_stl())}, instances=spacer_grid(100))
        configuration = base.read(data)
        assert len(configuration.instances) == 100 and list(configuration.parts) == ["spacer"]
        assert configuration.labels[0] == "Spacer #1" and configuration.labels[-1] == "Spacer #100"
        assert configuration.parts["spacer"].health["watertight"] and configuration.part_warnings() == []
        assert configuration.parts["spacer"].health["size_mm"] == pytest.approx([15.875, 15.875, 3.175])

    def test_the_most_instances_of_spacers_are_accepted_and_one_more_refused(self, base):
        base.add(spacer_stl())
        parts = {"spacer": part_entry("Spacer", spacer_stl())}
        grid = spacer_grid(limits.MAX_INSTANCES + 1, side=13, pitch_mm=21.5)
        accepted = base.read(plate_configuration(parts=parts, instances=grid[:-1]))
        assert len(accepted.instances) == limits.MAX_INSTANCES
        error = refused(plate_configuration(parts=parts, instances=grid), base)
        assert (error.error_code, error.message) == (
            "slice.too_many_instances", "This plate has 151 instances; the slicer takes up to 150 on one plate, so "
                                        "print the rest on a second plate.")

    def test_too_many_different_parts(self, base):
        parts = {f"p{i}": part_entry(f"P{i}", PEG) for i in range(limits.MAX_PARTS + 1)}
        instances = [{"ref": f"p{i}", "orientation": "+z", "angle": 0, "x": 20.0 + 15 * (i % 20),
                      "y": 20.0 + 15 * (i // 20)} for i in range(limits.MAX_PARTS + 1)]
        error = refused(plate_configuration(parts=parts, instances=instances), base)
        assert (error.error_code, error.details) == ("slice.too_many_parts", "26 different parts, cap 25")
        assert error.message == ("This plate uses 26 different parts; the slicer takes up to 25 on one plate, so "
                                 "print the rest on a second plate.")
        parts.pop(f"p{limits.MAX_PARTS}")                       # 25 parts pass this check
        assert len(base.read(plate_configuration(parts=parts, instances=instances[:-1])).parts) == 25

    def test_no_cap_on_the_triangles_of_the_whole_plate(self, base, monkeypatch):
        # Unmeasured, it only added a way to refuse: the memory watchdog decides such plates.
        # The part check is replaced, so no 7.5 MB part is read; the placement is not this test's.
        monkeypatch.setattr(service, "_checked_part", lambda key, part, entry, plate: service.CheckedPart(
            name=part["name"], stl_path=entry.path, footprints={}, triangles=limits.MAX_PART_TRIANGLES,
            health={"volume_mm3": 1.0}))
        monkeypatch.setattr(service, "check_placement", lambda *a: [])
        instances = [{"ref": "box", "orientation": "+z", "angle": 0, "x": 100.0, "y": 100.0}] * limits.MAX_INSTANCES
        configuration = base.read(plate_configuration(instances=instances))
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
        assert len(base.read(plate_configuration(instances=instances)).instances) == limits.MAX_INSTANCES

    def test_instance_naming_no_listed_part(self, base):
        data = plate_configuration()
        data["instances"][2]["ref"] = "gear"
        error = refused(data, base)
        assert error.message == PART_NOT_LISTED_MESSAGE
        assert error.error_code == "slice.part_missing"
        assert error.details == "instance 2 names part 'gear', which parts does not list"
        assert "missing_parts" not in error_report(error)["where"]

    def test_parts_missing_from_the_part_store_are_listed_in_one_report(self, tmp_path):
        parts = Parts(tmp_path)
        report = error_report(refused(plate_configuration(), parts))
        assert report == {
            "code": "slice.part_missing", "message": "The slicer no longer has 2 of this plate's parts.",
            "where": {"stage": "checking", "missing_parts": [
                {"key": "box", "sha256": sha256(BOX), "units": "mm"},
                {"key": "peg", "sha256": sha256(PEG), "units": "mm"}]},
            "remedy": "Add the parts again and slice again.", "action": "refresh_parts", "retryable": False,
            "detail": f"missing from the part store: {sha256(BOX)} (mm), {sha256(PEG)} (mm)"}
        parts.add(BOX)
        parts.add(PEG)
        assert parts.read(plate_configuration()).submission_id == SUBMISSION_ID     # the same submission, accepted

    def test_the_missing_parts_come_in_the_order_of_parts(self, tmp_path):
        parts = Parts(tmp_path)
        data = plate_configuration()
        data["parts"] = {"peg": data["parts"]["peg"], "box": data["parts"]["box"]}
        report = error_report(refused(data, parts))
        assert [m["key"] for m in report["where"]["missing_parts"]] == ["peg", "box"]

    def test_one_missing_part_is_said_so(self, base, tmp_path):
        other = box_stl(9, 9, 9)
        data = with_peg(base, other)
        data["parts"]["peg"] = part_entry("Peg", box_stl(9, 9, 9.5))
        report = error_report(refused(data, base))
        assert report["message"] == "The slicer no longer has one of this plate's parts."
        assert [m["key"] for m in report["where"]["missing_parts"]] == ["peg"]

    def test_a_part_of_another_user_key_is_missing(self, base):
        report = error_report(pytest.raises(PlateConfigurationRefused, base.read, plate_configuration(),
                                            user_key="user-b").value)
        assert report["code"] == "slice.part_missing" and len(report["where"]["missing_parts"]) == 2

    def test_a_hash_under_other_units_is_missing(self, base):
        data = plate_configuration()
        data["parts"]["peg"]["units"] = "in"
        report = error_report(refused(data, base))
        assert report["where"]["missing_parts"] == [{"key": "peg", "sha256": sha256(PEG), "units": "in"}]

    def test_a_memory_estimate_over_the_ceiling_refuses_nothing(self, base, monkeypatch):
        # The estimate is rough (a 100 mm solid cube: 1,158 MB estimated, 269 MB measured),
        # so it is only logged; the watchdog guards memory while Orca runs.
        monkeypatch.setenv(limits.MAX_PEAK_MB_ENV, "180")
        job = base.read(plate_configuration())
        estimate = limits.estimate_peak_mb([4000.0, 4000.0, 1920.0], False)
        assert job.estimated_peak_mb == estimate > 180
        assert job.memory_ceiling_mb == 180
        assert (job.describe()["estimated_peak_mb"], job.describe()["memory_ceiling_mb"]) == (estimate, 180)

    def test_a_solid_block_the_old_estimate_refused_is_read(self, base):
        data = with_peg(base, box_stl(150, 150, 150))
        data["instances"] = [{"ref": "peg", "orientation": "+z", "angle": 0, "x": 170.0, "y": 160.0}]
        job = base.read(data)
        assert job.estimated_peak_mb > limits.DEFAULT_MAX_PEAK_MB and job.memory_ceiling_mb == 2000

    def test_supports_raise_the_estimate(self, base):
        off = base.read(plate_configuration(overrides={"enable_support": "0"}))
        on = base.read(plate_configuration(overrides={"enable_support": "1"}))
        assert (off.supports_on, on.supports_on) == (False, True)
        assert abs(on.estimated_peak_mb - off.estimated_peak_mb * limits.MEMORY_SUPPORTS_FACTOR) <= 1   # both rounded
        assert on.expected_s > off.expected_s

    def test_supports_on_through_the_process_profile(self, base, tmp_path, monkeypatch):
        """A process profile whose own enable_support is "1", and no override: supports are on,
        with the 12 mm spacing and the supports factor; an override of "0" turns them off."""
        from penguin_slice import service
        from penguin_slice.slicer import DEFAULT_PROFILES, SliceProfiles
        process = json.loads(DEFAULT_PROFILES.process.read_text())
        process["enable_support"] = "1"
        (tmp_path / "supported.json").write_text(json.dumps(process))
        supported = SliceProfiles(DEFAULT_PROFILES.printer, DEFAULT_PROFILES.filament, tmp_path / "supported.json")
        plain = base.read(plate_configuration())
        monkeypatch.setattr(service, "choose_profiles", lambda *args, **kwargs: supported)
        on = base.read(plate_configuration())
        assert (plain.supports_on, on.supports_on) == (False, True)
        assert abs(on.estimated_peak_mb - plain.estimated_peak_mb * limits.MEMORY_SUPPORTS_FACTOR) <= 1
        assert base.read(plate_configuration(overrides={"enable_support": "0"})).supports_on is False
        apart_8 = [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0},
                   {"ref": "box", "orientation": "+z", "angle": 0, "x": 78.0, "y": 50.0}]       # 20 mm boxes, 8 apart
        with pytest.raises(Exception) as caught:      # noqa: PT011 - the placement check's refusal
            base.read(plate_configuration(instances=apart_8))
        assert error_report(caught.value)["code"] == "slice.placement_too_close"
        assert base.read(plate_configuration(instances=apart_8, overrides={"enable_support": "0"})).supports_on is False

    def test_a_part_too_large_for_the_plates_printer_but_not_the_largest_is_refused_at_submission(self, base,
                                                                                                  monkeypatch):
        # The catalog the test supplies: the largest printer is 500 mm a side, the plate's own 340 x 320.
        from penguin_slice import part_store
        monkeypatch.setattr(service, "largest_plate", lambda: {"min": [0.0, 0.0], "max": [500.0, 500.0],
                                                               "height": 500.0, "margin": 3.0, "printer": "a large one"})
        big = box_stl(400, 400, 100)
        assert base.add(big)["sha256"] == sha256(big)                      # accepted on arrival
        data = with_peg(base, big)
        with pytest.raises(MeshError) as caught:
            base.read(data)
        report = error_report(caught.value)
        assert (report["code"], report["where"]) == ("slice.part_too_large", {"part": "Peg", "stage": "checking"})
        assert report["message"] == ("Peg is 400 x 400 x 100 mm, larger than the printer can print in any "
                                     "orientation (340.0 x 320.0 x 340.0 mm).")
        assert part_store.UNITS == {"mm": 1.0, "in": 25.4}

    def test_a_long_part_that_fits_only_turned_is_not_refused_as_too_large(self, base):
        # 400 mm long: it fits the 340 x 320 plate only on the diagonal, so the part check
        # lets it through and the placement decides.
        data = with_peg(base, box_stl(400, 10, 10))
        data["instances"] = [{"ref": "peg", "orientation": "+z", "angle": 43, "x": 170.0, "y": 160.0}]
        assert base.read(data).parts["peg"].name == "Peg"

    def test_part_warnings_travel_with_the_plate_configuration_naming_the_part(self, base):
        data = with_peg(base, box_stl(2, 1, 0.5))
        job = base.read(data)
        assert [w["code"] for w in job.part_warnings()] == ["slice.part_maybe_inches"]
        assert job.part_warnings()[0]["message"] == ("Peg is only 2.0 x 1.0 x 0.5 mm; if it was drawn in inches, "
                                                     "export it again in millimetres.")
        assert job.part_warnings()[0]["where"] == {"part": "Peg"}
        assert job.describe()["parts"]["peg"]["warnings"] == ["slice.part_maybe_inches"]

    def test_a_part_in_inches_is_measured_and_placed_25_4_times_larger(self, base):
        small = box_stl(2, 1, 0.5)
        base.add(small, units="in")
        data = plate_configuration()
        data["parts"]["peg"] = part_entry("Peg", small, "in")
        data["instances"] = [{"ref": "peg", "orientation": "+z", "angle": 0, "x": 100.0, "y": 100.0}]
        job = base.read(data)
        peg = job.parts["peg"]
        assert (peg.scale, peg.units) == (25.4, "in")
        assert peg.health["size_mm"] == pytest.approx([50.8, 25.4, 12.7])
        xs = [p[0] for p in peg.footprints["+z"]["hull"]]
        assert max(xs) - min(xs) == pytest.approx(50.8, abs=1e-3)
        assert job.part_warnings() == []                     # labelled in inches: never "maybe inches"
        data["instances"][0]["x"] = 25.0                     # 50.8 mm wide: 25.0 - 25.4 is off the plate
        assert refused(data, base).error_code == "slice.placement_off_plate"

    def test_unknown_printer(self, base):
        with pytest.raises(ProfileError) as caught:
            base.read(plate_configuration(printer="Bambu Lab X9"))
        assert "Bambu Lab X9" in caught.value.message

    def test_filament_not_for_this_printer(self, base):
        with pytest.raises(ProfileError) as caught:
            base.read(plate_configuration(printer=P4, filament="Generic PETG @BBL H2S",
                                          process="0.24mm Balanced Quality @BBL H2S 0.6 nozzle"))
        assert caught.value.message == CHOOSE_PROFILES_MESSAGE

    def test_bad_overrides(self, base):
        with pytest.raises(OverrideError) as caught:
            base.read(plate_configuration(overrides={"sparse_infill_density": "125%"}))
        assert caught.value.details == "override 'sparse_infill_density' is 125%, above max 100"
        assert caught.value.message == "Sparse infill density (Strength, Infill) must be at most 100%, not 125%."

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
        data = with_peg(base, box_stl(8, 8, 345))
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

    def test_a_rotation_lays_the_part_by_the_contracts_matrix(self, base):
        # A quarter turn about y (the matrix of '+x'): the peg's 30 mm side lies along x.
        half = 0.5 ** 0.5
        data = plate_configuration()
        data["instances"][2] = {"ref": "peg", "rotation": [half, 0.0, -half, 0.0], "angle": 15, "x": 150.0, "y": 50.0}
        job = base.read(data)
        peg = job.parts["peg"]
        turned = peg.footprints[tuple(job.instances[2]["rotation"])]
        assert turned["height"] == pytest.approx(peg.footprints["+x"]["height"]) == 8.0
        for got, expected in zip(sorted(map(tuple, turned["hull"])), sorted(map(tuple, peg.footprints["+x"]["hull"]))):
            assert got == pytest.approx(expected, abs=1e-3)

    def test_a_rotation_whose_part_is_gone_from_the_store_makes_it_missing(self, base, monkeypatch):
        half = 0.5 ** 0.5
        data = plate_configuration()
        data["instances"][2] = {"ref": "peg", "rotation": [half, 0.0, -half, 0.0], "angle": 15, "x": 150.0, "y": 50.0}
        base.store.get(USER_KEY, sha256(PEG), "mm").path.unlink()
        report = error_report(refused(data, base))
        assert report["where"]["missing_parts"] == [{"key": "peg", "sha256": sha256(PEG), "units": "mm"}]

    def test_two_instances_with_one_rotation_read_the_part_once(self, base, monkeypatch):
        half = 0.5 ** 0.5
        reads = []
        real = service.read_binary_stl
        monkeypatch.setattr(service, "read_binary_stl", lambda *a, **k: reads.append(a[1]) or real(*a, **k))
        data = plate_configuration()
        data["instances"][1] = {"ref": "box", "rotation": [half, 0.0, 0.0, half], "angle": 0, "x": 100.0, "y": 50.0}
        data["instances"][0] = {"ref": "box", "rotation": [half, 0.0, 0.0, half], "angle": 0, "x": 50.0, "y": 50.0}
        data["instances"][2] = {"ref": "box", "rotation": [1.0, 0.0, 0.0, 0.0], "angle": 0, "x": 150.0, "y": 50.0}
        base.read(data)
        assert reads == ["Box"]


class TestCheckPart:
    """A part on arrival (service.upload_part): the checks, in its units, against the largest
    printer of the profile catalog; its sentences say "This part"."""

    def test_a_good_part_gives_its_record(self, base):
        record = base.add(box_stl(40, 30, 12))
        assert record == {"sha256": sha256(box_stl(40, 30, 12)), "units": "mm",
                          "measurements": {"triangles": 12, "size_mm": [40.0, 30.0, 12.0], "volume_mm3": 14400.0},
                          "warnings": []}

    def test_a_surface_that_is_not_closed_has_no_volume(self, base):
        from helpers import FIXTURES
        record = base.add((FIXTURES / "bad_stls" / "open_box.stl").read_bytes())
        assert record["measurements"]["volume_mm3"] is None
        assert [w["code"] for w in record["warnings"]] == ["slice.part_not_watertight"]
        assert record["warnings"][0]["message"].startswith("This part has holes in its surface")
        assert set(record["warnings"][0]) == {"code", "message", "detail"}            # no where: no name

    @pytest.mark.parametrize("data, code, message", [
        (b"", "slice.part_unreadable", "The file for this part is empty."),
        (b"solid peg\nendsolid peg\n", "slice.part_unreadable", "The file for this part is not an STL file."),
        (box_stl(8, 8, 0.05), "slice.part_too_small", "This part is flat: it is 0.05 mm thick, too thin to print."),
        (box_stl(0.05, 0.05, 0.05), "slice.part_too_small", "This part is too small to print (0.05 x 0.05 x 0.05 mm)."),
        (box_stl(500, 500, 500), "slice.part_too_large",
         "This part is 500 x 500 x 500 mm, larger than any printer here can print in any orientation (the largest "
         "prints 340.0 x 320.0 x 340.0 mm)."),
    ])
    def test_a_part_that_cannot_be_sliced_is_refused_naming_no_part(self, base, data, code, message):
        with pytest.raises(MeshError) as caught:
            base.add(data)
        report = error_report(caught.value)
        assert (report["code"], report["message"], report["where"]) == (code, message, {"stage": "checking"})
        assert report["detail"].startswith("upload: ")

    def test_the_checks_run_on_the_part_in_its_units(self, base):
        tiny = box_stl(0.05, 0.05, 0.05)
        record = base.add(tiny, units="in")                   # 1.27 mm a side: not too small
        assert record["measurements"]["size_mm"] == [1.27, 1.27, 1.27] and record["warnings"] == []
        with pytest.raises(MeshError) as caught:
            base.add(box_stl(15, 15, 15), units="in")         # 381 mm a side: too large
        assert caught.value.error_code == "slice.part_too_large"

    def test_a_small_part_in_millimetres_warns_of_inches_and_in_inches_does_not(self, base):
        small = box_stl(2, 1, 0.5)
        assert [w["code"] for w in base.add(small)["warnings"]] == ["slice.part_maybe_inches"]
        assert base.add(small)["warnings"][0]["message"] == ("This part is only 2.0 x 1.0 x 0.5 mm; if it was drawn "
                                                             "in inches, export it again in millimetres.")
        assert base.add(small, units="in")["warnings"] == []

    def test_one_file_under_both_units_is_two_entries(self, base):
        data = box_stl(2, 1, 0.5)
        mm, inches = base.add(data), base.add(data, units="in")
        assert mm["sha256"] == inches["sha256"] and (mm["units"], inches["units"]) == ("mm", "in")
        assert mm["measurements"] != inches["measurements"]
        assert base.store.get(USER_KEY, mm["sha256"], "mm") is not base.store.get(USER_KEY, mm["sha256"], "in")

    def test_the_same_bytes_again_answer_the_same_record_without_a_new_check(self, base, monkeypatch):
        first = base.add(box_stl(5, 6, 7))
        monkeypatch.setattr(service, "check_part", lambda data, units: 1 / 0)
        assert base.add(box_stl(5, 6, 7)) == first

    def test_the_largest_printer_is_the_envelope_of_the_catalog(self):
        plate = service.largest_plate()
        assert (plate["max"], plate["height"]) == ([340.0, 320.0], 340.0)

    def test_a_catalog_that_cannot_be_read_is_a_server_profile_problem(self, base, monkeypatch):
        from penguin_slice import print_config
        service._largest_plate.cache_clear()
        monkeypatch.setattr(service, "load_catalog", lambda: print_config.Catalog.load(Path("/no-catalog")))
        try:
            with pytest.raises(ProfileError) as caught:
                base.add(box_stl(9, 9, 9))
        finally:
            service._largest_plate.cache_clear()
        assert caught.value.error_code == "slice.profile_unreadable"


def sliced_by(base, data=None):
    return base.read(data or plate_configuration())


class TestSlice:
    def test_slices_into_the_output_folder_and_removes_scratch(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        sliced = slice_plate_configuration(sliced_by(base), out)
        assert sliced.path == out / "Box_plus1-20261009-1432.gcode.3mf"
        assert sliced.path.is_file()
        assert sliced.summary == {"file": "Box_plus1-20261009-1432.gcode.3mf", "instances": 3, "print_time_s": 600.0,
                                  "filament_m": 1.5, "filament_g": 4.5, "layer_count": 42, "warnings": [],
                                  "part_warnings": []}
        assert sorted(p.name for p in out.iterdir()) == [sliced.path.name]
        assert sliced.peak_rss_kb > 0

    def test_the_output_folder_is_made(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        sliced = slice_plate_configuration(sliced_by(base), tmp_path / "a" / "b")
        assert sliced.path.parent == (tmp_path / "a" / "b").resolve()

    def test_instance_left_off_by_orca_fails_and_leaves_nothing(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "drop")
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(sliced_by(base), out)
        assert caught.value.message == LEFT_OFF_MESSAGE
        assert caught.value.details == "expected 3 objects, found 2; missing ['Peg #1']; unexpected []"
        assert list(out.iterdir()) == []

    def test_orca_refusal_fails_and_leaves_nothing(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "refuse")
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(sliced_by(base), out)
        assert (caught.value.code, caught.value.message) == (
            -101, "Two instances are too close together: the slicer found that their paths would meet.")
        # Orca's own reason (result.json's error_string) is kept before the scratch folder goes.
        assert caught.value.details == ("exit code 155\norca error_string: too close\n"
                                        "Some objects are too close together")
        assert list(out.iterdir()) == []

    def test_orca_output_that_is_not_utf8_is_kept_not_fatal(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "garbled")
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(sliced_by(base), tmp_path / "out")
        report = error_report(caught.value)
        assert report["code"] == "slice.orca_too_close"
        assert "Br�cket is too close" in report["detail"]

    def test_output_folder_that_is_a_file(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        out = tmp_path / "out"
        out.write_text("not a folder")
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(sliced_by(base), out)
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
            slice_plate_configuration(sliced_by(base), out)
        report = error_report(caught.value)
        assert report["code"] == "slice.output_unwritable"
        assert "Box_plus1-20261009-1432.gcode.3mf" in report["detail"]
        assert [p.name for p in out.iterdir()] == ["Box_plus1-20261009-1432.gcode.3mf"]     # scratch removed
        assert list((out / "Box_plus1-20261009-1432.gcode.3mf").iterdir()) == []

    def test_stl_that_vanishes_after_the_check(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")
        configuration = sliced_by(base)
        configuration.parts["peg"].stl_path.unlink()
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(configuration, out)
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
        slice_plate_configuration(sliced_by(base), tmp_path / "out")
        cmd = seen["cmd"]
        assert cmd[cmd.index("--arrange") + 1] == "0" and cmd[cmd.index("--orient") + 1] == "0"
        assert cmd[-1].endswith("/plate.3mf") and cmd[-1].startswith(str((tmp_path / "out").resolve()))

    def test_disk_full_while_the_plate_is_written(self, base, tmp_path, monkeypatch):
        install_fake_orca(tmp_path, monkeypatch, "ok")

        def full(*args, **kwargs):
            raise OSError(28, "No space left on device")
        monkeypatch.setattr(plate_configuration_module, "write_plate_3mf", full)
        out = tmp_path / "out"
        with pytest.raises(SliceError) as caught:
            slice_plate_configuration(sliced_by(base), out)
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
            slice_plate_configuration(sliced_by(base), out, stop=stop, on_progress=on_progress)
        assert stages == ["building_plate", "slicing", "slicing_mesh"]
        assert list(out.iterdir()) == []

    def test_scratch_of_a_dead_process_is_removed_and_ours_kept(self, tmp_path):
        ours = service.make_scratch(tmp_path)
        store = service.make_scratch(tmp_path, "parts-")
        dead = tmp_path / "slice-999999999-5-abc"
        dead.mkdir()
        dead_store = tmp_path / "slice-999999999-5-parts-abc"
        dead_store.mkdir()
        reused = tmp_path / f"slice-{os.getpid()}-1-abc"          # our pid, another start time
        reused.mkdir()
        other = tmp_path / "unrelated"
        other.mkdir()
        (tmp_path / "slice-1-2-a-file").write_text("not a folder")
        assert sorted(service.clean_stale_scratch(tmp_path)) == sorted([dead.name, dead_store.name, reused.name])
        assert ours.is_dir() and store.is_dir() and other.is_dir() and (tmp_path / "slice-1-2-a-file").exists()
        assert store.name.startswith(f"slice-{os.getpid()}-") and "-parts-" in store.name
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

    def test_a_missing_catalog_is_a_server_profile_problem(self, base, monkeypatch, tmp_path):
        from penguin_slice import print_config
        monkeypatch.setattr(print_config, "load_catalog", lambda: print_config.Catalog.load(tmp_path / "no-catalog"))
        with pytest.raises(ProfileError) as caught:
            base.read(plate_configuration(printer=P4, filament="Bambu PLA Basic @BBL H2S",
                                          process="0.20mm Standard @BBL H2S"))
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
        sliced = slice_plate_configuration(sliced_by(base), out)
        assert sliced.path.read_bytes()[:2] == b"PK"

    def test_a_part_in_inches_reaches_orca_in_millimetres(self, base, tmp_path, monkeypatch):
        import zipfile
        import xml.etree.ElementTree as ET
        install_fake_orca(tmp_path, monkeypatch, "ok")
        small = box_stl(2, 1, 0.5)
        base.add(small, units="in")
        data = plate_configuration(parts={"peg": part_entry("Peg", small, "in")},
                                   instances=[{"ref": "peg", "orientation": "+z", "angle": 0, "x": 100.0, "y": 100.0}])
        written = {}
        real = plate_configuration_module.write_plate_3mf

        def keep(path, *args, **kwargs):
            names = real(path, *args, **kwargs)
            written["model"] = zipfile.ZipFile(path).read("3D/3dmodel.model")
            return names
        monkeypatch.setattr(plate_configuration_module, "write_plate_3mf", keep)
        slice_plate_configuration(base.read(data), tmp_path / "out")
        ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
        vertices = [[float(v.get(k)) for k in "xyz"] for v in ET.fromstring(written["model"]).iter(f"{{{ns['m']}}}vertex")]
        spans = [max(v[i] for v in vertices) - min(v[i] for v in vertices) for i in range(3)]
        assert spans == pytest.approx([50.8, 25.4, 12.7], abs=1e-3)


def test_plate_configuration_value_is_not_changed(base):
    data = plate_configuration()
    data["instances"][0] = {"ref": "box", "rotation": [1.0000009, 0.0, 0.0, 0.0], "angle": 0, "x": 50.0, "y": 50.0}
    before = copying.deepcopy(data)
    base.read(data)
    assert data == before
    assert json.dumps(data)
