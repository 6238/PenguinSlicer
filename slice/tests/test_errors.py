"""errors.error_report: every code the slice service can produce, each produced on purpose
by the code that really raises it, and the shape of every report.

The expected sentence, remedy, action, retryable flag, stage and evidence of every code are
written out here, not read from errors.CODES, so a change to that table fails a test.
"""
import json
import re
import subprocess
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from helpers import CONTRACTS, box_stl, install_fake_orca, write_plate_job
from penguin_slice import error_report, limits, plate_job as plate_job_module, slicer
from penguin_slice.errors import CODES
from penguin_slice.jobs import JobFailure, JobPool, QueueFull
from penguin_slice.service import read_plate_job, slice_plate_job

REQUIRED = {"code": str, "message": str, "remedy": str, "retryable": bool, "detail": str}
OPTIONAL = {"where": dict, "action": str}
WHERE_KEYS = {"part", "copy", "height_mm", "stage"}
ORCA_GENERAL_FAILURE = "Failed slicing the model. Please verify the slicing of all plates on Orca Slicer before uploading."


def plate_job(**changes):
    job = {"parts": {"box": {"name": "Box", "stl": "box.stl"}},
           "copies": [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0}]}
    job.update(changes)
    return job


class Scene:
    """A folder with a 20 x 20 x 10 mm box part, and ways to fail."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp, self.monkeypatch = tmp_path, monkeypatch
        self.base = tmp_path / "job"
        self.base.mkdir(parents=True)
        self.out = tmp_path / "out"
        (self.base / "box.stl").write_bytes(box_stl(20, 20, 10))

    def read(self, data):
        return read_plate_job(data, self.base)

    def slice(self, data=None):
        return slice_plate_job(write_plate_job(self.base, data or plate_job(), {}), self.out)

    def slice_with_run(self, fake_run):
        with mock.patch.object(slicer.subprocess, "run", fake_run):
            return self.slice()

    def orca_exit(self, returncode, return_code=None, archive=None, error_string=None):
        def fake_run(cmd, **kwargs):
            out = Path(cmd[cmd.index("--outputdir") + 1])
            if return_code is not None:
                result = {"return_code": return_code}
                if error_string is not None:
                    result["error_string"] = error_string
                (out / "result.json").write_text(json.dumps(result))
            if archive is not None:
                archive(out / cmd[cmd.index("--export-3mf") + 1])
            return subprocess.CompletedProcess(cmd, returncode, stdout="orca output line\n", stderr="")
        return self.slice_with_run(fake_run)


def not_a_zip(path):
    path.write_bytes(b"not a zip")


def no_gcode(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Metadata/slice_info.config", "")


def timeout(cmd, **kwargs):
    raise subprocess.TimeoutExpired(cmd, kwargs["timeout"], output="still slicing\n")


def busy(scene):
    pool = JobPool(lambda job_id, payload: {}, executor=mock.Mock(), max_queued=0)
    pool.submit()


def stl(scene, data):
    (scene.base / "box.stl").write_bytes(data)
    scene.read(plate_job())


def oversize(scene):
    with open(scene.base / "box.stl", "r+b") as fh:
        fh.truncate(limits.MAX_PART_BYTES + 1)
    scene.read(plate_job())


def job_too_detailed(scene):
    scene.monkeypatch.setattr(limits, "MAX_JOB_TRIANGLES", 11)
    scene.read(plate_job())


def fake_orca(mode):
    def produce(scene):
        install_fake_orca(scene.tmp, scene.monkeypatch, mode)
        scene.slice()
    return produce


def orca_missing(scene):
    scene.monkeypatch.setenv(slicer.ORCA_ENV, str(scene.tmp / "nowhere" / "orca-slicer"))
    scene.slice()


def output_is_a_file(scene):
    scene.out.write_text("a file where the output folder should be")
    scene.slice()


def bug_in_the_pipeline(scene):
    # A defect in the slice service's own code, reached through the entry point.
    def broken(*args, **kwargs):
        return 1 / 0
    scene.monkeypatch.setattr(plate_job_module, "write_plate_3mf", broken)
    scene.slice()


TWO = [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0},
       {"ref": "box", "orientation": "+z", "angle": 0, "x": 70.0, "y": 50.0}]
SERVER = "Slice again; if it fails again, ask a mentor to check the print server."


class Expected:
    """What the caller sees for one code; `detail` is a piece of the evidence it must hold."""

    def __init__(self, producer, message, stage, retryable, action, remedy, detail):
        self.producer, self.message, self.stage = producer, message, stage
        self.retryable, self.action, self.remedy, self.detail = retryable, action, remedy, detail


EXPECTED = {
    "slice.bad_plate_job": Expected(
        lambda s: s.read(plate_job(copies=[])), "This request could not be read.", "checking", False, None,
        "Lay out the plate again and send a new slice.", "copies is not a non-empty list"),
    "slice.too_many_copies": Expected(
        lambda s: s.read(plate_job(copies=TWO * 13)), "Up to 25 copies per plate; print the rest in a second job.",
        "checking", False, "lower_quantities", "Lower the quantities and print the rest in a second job.",
        "26 copies, cap 25"),
    "slice.part_missing": Expected(
        lambda s: s.read(plate_job(parts={})), "A copy on the plate names a part this request does not include.",
        "checking", False, "refresh_parts", "Load the parts again and send a new slice.",
        "copy 0 names part 'box', which parts does not list"),
    "slice.part_unreadable": Expected(
        lambda s: stl(s, b"solid box\nendsolid box\n"), "The file for Box could not be read as a part.",
        "checking", False, "refresh_parts", "Export the part again and send a new slice.",
        "box.stl: 23 bytes, shorter than the 84-byte header of a binary STL"),
    "slice.part_too_detailed": Expected(
        oversize, "Box is too detailed to print here (over 150,000 triangles).", "checking", False, None,
        "Export the part with a coarser tessellation, or simplify it, and slice again.",
        "box.stl: 7,500,085 bytes, cap 7,500,084"),
    "slice.part_too_small": Expected(
        lambda s: stl(s, box_stl(20, 20, 0.05)), "Box is too small to print (under 0.1 mm).", "checking", False, None,
        "Check the part's units and size, then slice again.", "box.stl: 20.0 x 20.0 x 0.05 mm"),
    "slice.job_too_detailed": Expected(
        job_too_detailed, "These copies are too detailed to slice together; lower the quantities.", "checking",
        False, "lower_quantities", "Lower the quantities and print the rest in a second job.",
        "12 triangles over 1 copies, cap 11"),
    "slice.unknown_printer": Expected(
        lambda s: s.read(plate_job(printer="Nope")), "The printer 'Nope' is not one the slicer knows.", "checking",
        False, None, "Choose a printer from the list, or ask a mentor to add this one.",
        "printer 'Nope' is not in the catalog"),
    "slice.profiles_not_offered": Expected(
        lambda s: s.read(plate_job(filament="Bambu PLA Basic @BBL H2S")),
        "Choose a filament and print settings from the list.", "checking", False, "choose_profiles",
        "Choose a filament and print settings from the lists and slice again.",
        "filament 'Bambu PLA Basic @BBL H2S' or process None is not offered with the default set"),
    "slice.bad_overrides": Expected(
        lambda s: s.read(plate_job(overrides={"walls": 5})),
        "These print settings could not be read; choose them from the lists.", "checking", False, "choose_profiles",
        "Choose the print settings from the lists and slice again.", "override 'walls' is 5, not one of [2, 3, 4, 6]"),
    "slice.placement_off_plate": Expected(
        lambda s: s.read(plate_job(copies=[dict(TWO[0], x=1.0)])), "Box #1 is not fully on the plate.", "checking",
        False, "arrange", "Move the copy fully onto the plate, or press Arrange, and slice again.",
        "Box #1 is not fully on the plate."),
    "slice.placement_too_tall": Expected(
        lambda s: stl(s, box_stl(20, 20, 341)), "Box #1 is taller than the printer can print (340 mm).", "checking",
        False, "choose_orientation", "Lay the part on another face so it is lower, and slice again.",
        "Box #1 is taller than the printer can print (340 mm)."),
    "slice.placement_too_close": Expected(
        lambda s: s.read(plate_job(copies=TWO)), "Box #1 and Box #2 are closer than 5 mm.", "checking", False,
        "arrange", "Move the copies further apart, or press Arrange, and slice again.",
        "Box #1 and Box #2 are closer than 5 mm."),
    "slice.busy": Expected(
        busy, "The slicer is busy, try again in a minute.", "queued", True, None, "Wait a minute and slice again.",
        "the job queue is full"),
    "slice.orca_missing": Expected(
        orca_missing, "The slicer could not be started.", "slicing", False, None,
        "Ask a mentor to check the print server; slicing is not set up on it.", "Orca Slicer is missing at "),
    "slice.orca_unstartable": Expected(
        lambda s: s.slice(), "The slicer could not be started.", "slicing", False, None,
        "Ask a mentor to check the print server; the slicer will not start on it.", "Permission denied"),
    "slice.timeout": Expected(
        lambda s: s.slice_with_run(timeout), "The slicer took too long on this part.", "slicing", True,
        "lower_quantities", "Try again, or slice fewer copies at once.", "orca code timeout\nstill slicing"),
    "slice.orca_killed": Expected(
        lambda s: s.orca_exit(-9), "The print server stopped the slicer before it finished.", "slicing", True,
        "lower_quantities", "Slice again; if it is stopped again, slice fewer copies at once.",
        "killed by signal 9 (SIGKILL)\norca output line"),
    "slice.orca_too_close": Expected(
        fake_orca("refuse"), "Parts are too close together; spread them out.", "slicing", False, "arrange",
        "Move the copies further apart, or press Arrange, and slice again.",
        "orca code -101\nexit code 155\norca error_string: too close\nSome objects are too close together"),
    "slice.crosses_edge": Expected(
        lambda s: s.orca_exit(204, -52), "A part crosses the edge of the plate.", "slicing", False, "arrange",
        "Move the copy fully onto the plate, or press Arrange, and slice again.",
        "orca code -52\nexit code 204\norca output line"),
    "slice.empty_layers": Expected(
        lambda s: s.orca_exit(156, -100, error_string=ORCA_GENERAL_FAILURE),
        "A part has no flat face on the plate; choose another Lay flat.", "slicing", False, None,
        "Try another orientation or other print settings, and slice again.",
        f"orca code -100\nexit code 156\norca error_string: {ORCA_GENERAL_FAILURE}\norca output line"),
    "slice.nothing_on_plate": Expected(
        lambda s: s.orca_exit(206, -50), "No part is fully on the plate.", "slicing", False, "arrange",
        "Move the copies onto the plate, or press Arrange, and slice again.", "orca code -50\nexit code 206"),
    "slice.orca_failed": Expected(
        lambda s: s.orca_exit(250, -6), "The slicer could not process this part.", "slicing", False, None,
        "Try another orientation or other print settings, and slice again.", "orca code -6\nexit code 250"),
    "slice.no_output": Expected(
        lambda s: s.orca_exit(0), "The slicer produced no output file.", "slicing", True, None, SERVER,
        "orca output line"),
    "slice.unreadable_output": Expected(
        lambda s: s.orca_exit(0, archive=not_a_zip), "The slicer output could not be read.", "slicing", True, None,
        SERVER, "plate.gcode.3mf is not a zip archive"),
    "slice.no_gcode": Expected(
        lambda s: s.orca_exit(0, archive=no_gcode), "The slicer output is missing its G-code.", "slicing", True,
        None, SERVER, "archive entries:\nMetadata/slice_info.config"),
    "slice.left_off_plate": Expected(
        fake_orca("drop"), "A part was left off the plate.", "slicing", False, "arrange",
        "Move every copy fully onto the plate, or press Arrange, and slice again.",
        "expected 1 objects, found 0; missing ['Box #1']; unexpected []"),
    "slice.output_unwritable": Expected(
        output_is_a_file, "The print server could not save the sliced file.", "saving", False, None,
        "Ask a mentor to check that the print server can write to its output folder, then slice again.",
        "File exists"),
    "slice.unexpected": Expected(
        bug_in_the_pipeline, "The slicer failed unexpectedly.", "slicing", False, None, SERVER,
        "ZeroDivisionError: division by zero"),
}


def produce(code, tmp_path, monkeypatch):
    with pytest.raises(Exception) as caught:
        EXPECTED[code].producer(Scene(tmp_path, monkeypatch))
    return caught.value, error_report(caught.value)


def assert_report_shape(report):
    for key, kind in REQUIRED.items():
        assert isinstance(report[key], kind), key
    for key in set(report) - set(REQUIRED):
        assert key in OPTIONAL and isinstance(report[key], OPTIONAL[key]), key
    assert set(report.get("where", {})) <= WHERE_KEYS
    assert report["message"].endswith(".") and report["remedy"].endswith(".")
    json.dumps(report)


def test_every_code_is_expected():
    assert list(EXPECTED) == list(CODES)


@pytest.mark.parametrize("code", list(EXPECTED))
def test_failure_produces_its_code(code, tmp_path, monkeypatch):
    _exc, report = produce(code, tmp_path, monkeypatch)
    expected = EXPECTED[code]
    assert report["code"] == code
    assert_report_shape(report)
    assert report["message"] == expected.message
    assert report["where"]["stage"] == expected.stage
    assert report["retryable"] is expected.retryable
    assert report.get("action") == expected.action
    assert report["remedy"] == expected.remedy
    assert expected.detail in report["detail"]


def test_orca_refusal_detail_leads_with_orca_code(tmp_path, monkeypatch):
    _exc, report = produce("slice.crosses_edge", tmp_path, monkeypatch)
    assert report["detail"].splitlines()[:3] == ["orca code -52", "exit code 204", "orca output line"]


def test_timeout_detail_keeps_what_orca_printed(tmp_path, monkeypatch):
    _exc, report = produce("slice.timeout", tmp_path, monkeypatch)
    assert report["detail"] == "orca code timeout\nstill slicing"


@pytest.mark.known_fault
def test_known_fault_orca_minus_100_is_always_called_no_flat_face(tmp_path, monkeypatch):
    # Orca's -100 is its general slicing failure (the real Orca gives it for a part with a
    # gap between two layers, which has a flat face on the plate). The sentence is the
    # earlier application's and is untrue for that part; hardening makes it follow Orca's
    # reason. This pins today's sentence so the change is deliberate.
    _exc, report = produce("slice.empty_layers", tmp_path, monkeypatch)
    assert report["message"] == "A part has no flat face on the plate; choose another Lay flat."
    assert ORCA_GENERAL_FAILURE in report["detail"]


@pytest.mark.parametrize("code, where", [
    ("slice.part_missing", {}),
    ("slice.part_unreadable", {"part": "Box"}), ("slice.part_too_small", {"part": "Box"}),
    ("slice.part_too_detailed", {"part": "Box"}),
    ("slice.placement_too_close", {"part": "Box", "copy": "Box #1"}),
    ("slice.placement_too_tall", {"part": "Box", "copy": "Box #1"}),
    ("slice.left_off_plate", {"copy": "Box #1"}),
])
def test_where_names_the_part_and_copy(code, where, tmp_path, monkeypatch):
    _exc, report = produce(code, tmp_path, monkeypatch)
    assert {k: v for k, v in report["where"].items() if k != "stage"} == where


def test_job_failure_reports_the_failure_that_caused_it(tmp_path):
    # A worker wraps a SliceError in a JobFailure, as the original print path's worker did.
    with pytest.raises(JobFailure) as caught:
        try:
            slicer.slice_plate(tmp_path / "plate.3mf", slicer.DEFAULT_PROFILES, tmp_path / "out")
        except slicer.SliceError as exc:
            raise JobFailure(exc.message, exc.details) from exc
    report = error_report(caught.value)
    assert report["code"] == "slice.orca_unstartable"
    assert "Permission denied" in report["detail"]


def test_job_failure_without_a_cause_is_unexpected_and_keeps_its_words():
    report = error_report(JobFailure("The worker gave up.", "worker said no"))
    assert (report["code"], report["message"]) == ("slice.unexpected", "The slicer failed unexpectedly.")
    assert report["detail"] == "JobFailure: The worker gave up.\nworker said no"


def test_mesh_error_with_an_unknown_sentence_is_still_a_part_report():
    from penguin_slice.mesh import MeshError
    report = error_report(MeshError("Something new about a part."))
    assert (report["code"], report["message"], report["where"]) == (
        "slice.part_unreadable", "Something new about a part.", {"stage": "checking"})


def test_unexpected_detail_names_the_exception():
    assert error_report(KeyError("plate"))["detail"] == "KeyError: 'plate'"


def test_queue_full_is_retryable():
    report = error_report(QueueFull())
    assert report["retryable"] is True and report["code"] == "slice.busy"


def test_codes_are_stable_names():
    for code in CODES:
        assert re.fullmatch(r"slice\.[a-z_]+", code), code


def test_reports_never_carry_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SLICE_TEST_TOKEN", "s3cr3t-value")
    for code in ("slice.orca_unstartable", "slice.orca_too_close", "slice.unexpected"):
        _exc, report = produce(code, tmp_path / code, monkeypatch)
        assert "s3cr3t-value" not in json.dumps(report)


def test_contract_example_is_a_report_the_service_produces(tmp_path, monkeypatch):
    """contracts/examples/error-report.json is what the real Orca's -101 gave (tests_orca
    checks its detail); here every field but the detail must be what the code gives."""
    example = json.loads((CONTRACTS / "examples" / "error-report.json").read_text())
    assert_report_shape(example)
    _exc, report = produce(example["code"], tmp_path, monkeypatch)
    assert {k: v for k, v in report.items() if k != "detail"} == {k: v for k, v in example.items() if k != "detail"}
    assert example["detail"].splitlines()[:2] == ["orca code -101", "exit code 155"]
