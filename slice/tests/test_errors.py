"""errors.error_report: every code the slice service can produce, each produced on purpose
by the code that really raises it, and the shape of every report.

The expected sentence, remedy, action, retryable flag, stage and evidence of every code are
written out here, not read from errors.CODES, so a change to that table fails a test.
"""
import io
import json
import re
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from helpers import (CONTRACTS, FAILSAFE_S, FIXTURES, Parts, bounded, box_stl, install_fake_orca, kill_fake,
                     part_entry, phase_2, submit, upload)
from penguin_slice import limits, plate_configuration as plate_configuration_module, service as service_module, slicer
from penguin_slice.errors import error_report
from penguin_slice.errors import CODES
from penguin_slice.jobs import JobFailure, JobPool, QueueFull
from penguin_slice.service import slice_plate_configuration
from penguin_slice.slicer import OrcaExit

REQUIRED = {"code": str, "message": str, "remedy": str, "retryable": bool, "detail": str}
OPTIONAL = {"where": dict, "action": str}
WHERE_KEYS = {"part", "instance", "other_instance", "height_mm", "stage", "missing_parts"}
STAGES = {"checking", "queued", "building", "slicing", "saving", "fetching"}
BOX = box_stl(20, 20, 10)


def plate_configuration(**changes):
    job = phase_2({"box": ("Box", BOX)}, [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0}])
    job.update(changes)
    return job


class Scene:
    """A part store with a 20 x 20 x 10 mm box part uploaded, and ways to fail."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp, self.monkeypatch = tmp_path, monkeypatch
        self.parts = Parts(tmp_path)
        self.parts.add(BOX)
        self.out = tmp_path / "out"

    def read(self, data):
        return self.parts.read(data)

    def upload(self, data):
        return self.parts.add(data)

    def slice(self, data=None, **kwargs):
        return slice_plate_configuration(self.read(data or plate_configuration()), self.out, **kwargs)

    def web(self, executor=None):
        from penguin_slice.web import create_app, slice_worker
        pool = JobPool(slice_worker, executor=executor or mock.Mock(), error_report=error_report)
        return create_app(self.tmp / "work", pool, start_sweeper=False).test_client(), pool

    def orca_exit(self, returncode, return_code=None, archive=None):
        """Orca replaced at slicer.run_process: it writes result.json and the archive."""
        self.monkeypatch.setenv(slicer.ORCA_ENV, str(FIXTURES / "slice_info.config"))      # a file that exists

        def fake_run(cmd, **kwargs):
            out = Path(cmd[cmd.index("--outputdir") + 1])
            if return_code is not None:
                (out / "result.json").write_text(json.dumps({"return_code": return_code}))
            if archive is not None:
                archive(out / cmd[cmd.index("--export-3mf") + 1])
            return OrcaExit(returncode, "orca output line")
        with mock.patch.object(slicer, "run_process", fake_run):
            return self.slice()


def no_gcode(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Metadata/slice_info.config", "")


def busy(scene):
    pool = JobPool(lambda job_id, payload, context: {}, executor=mock.Mock(), max_queued=0)
    pool.submit()


def stl(scene, data):
    """`data` uploaded as a part (the checks on arrival)."""
    scene.upload(data)


def placed(scene, data):
    """`data` uploaded, then a plate of one instance of it at (50, 50)."""
    scene.upload(data)
    scene.read(plate_configuration(parts={"box": part_entry("Box", data)}))


def oversize(scene):
    """An upload whose Content-Length is one byte over the cap, through the HTTP interface."""
    client, _pool = scene.web()
    return client.post("/parts?units=mm", headers={"X-Penguin-User-Key": "user-a"},
                       environ_overrides={"CONTENT_LENGTH": str(limits.MAX_PART_BYTES + 1)},
                       content_type="application/octet-stream").get_json()


def no_user_key(scene):
    client, _pool = scene.web()
    return upload(client, BOX, user_key=None).get_json()


def bad_units(scene):
    client, _pool = scene.web()
    return upload(client, BOX, units="cm").get_json()


def parts_gone(scene):
    """A plate whose part the part store does not hold (another user key's)."""
    scene.parts.read(plate_configuration(), user_key="user-b")


def profile_unreadable(scene):
    # The server's own printer profile damaged on disk.
    broken = scene.tmp / "printer.json"
    broken.write_text("{not a profile")
    scene.monkeypatch.setattr(service_module, "printer_profile",
                              lambda profiles: __import__("json").loads(broken.read_text()))
    scene.read(plate_configuration())


def over_the_memory_ceiling(instances):
    """The memory watchdog stops a stand-in Orca whose processes read 2,050 MB, over the
    default ceiling. Bounded: with the watchdog's stop removed this fails in FAILSAFE_S and
    kills the stand-in."""
    def produce(scene):
        scene.monkeypatch.setattr(slicer, "MEMORY_READER", lambda pgid: (2050 * 1024, 2050 * 1024))
        install_fake_orca(scene.tmp, scene.monkeypatch, "hang")
        try:
            _returned, raised, finished = bounded(lambda: scene.slice(plate_configuration(instances=instances)))
        finally:
            for out in scene.out.rglob("fake-orca.pid"):
                kill_fake(out.parent)
        assert finished, f"the watchdog never stopped Orca within {FAILSAFE_S} s"
        assert raised is not None, "the slice over the ceiling succeeded"
        raise raised
    return produce


def fake_orca(mode, **slice_kwargs):
    def produce(scene):
        install_fake_orca(scene.tmp, scene.monkeypatch, mode)
        scene.slice(**slice_kwargs)
    return produce


def with_supports(scene):
    install_fake_orca(scene.tmp, scene.monkeypatch, "empty_layers")
    scene.slice(plate_configuration(overrides={"enable_support": "1"}))


def timeout(scene):
    timers = slicer.TIMER
    install_fake_orca(scene.tmp, scene.monkeypatch, "hang")
    scene.slice(plate_configuration(instances=SPACED), on_progress=lambda stage, fraction, message: stage == "slicing_mesh" and timers.made[-1].fire())


def cancelled(scene):
    stop = slicer.Stop()
    install_fake_orca(scene.tmp, scene.monkeypatch, "hang")
    scene.slice(stop=stop, on_progress=lambda stage, fraction, message: stage == "slicing_mesh" and stop.set())


def orca_missing(scene):
    scene.monkeypatch.setenv(slicer.ORCA_ENV, str(scene.tmp / "nowhere" / "orca-slicer"))
    scene.slice()


def output_is_a_file(scene):
    scene.out.write_text("a file where the output folder should be")
    scene.slice()


def disk_full(scene):
    def full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    scene.monkeypatch.setattr(plate_configuration_module, "write_plate_3mf", full)
    scene.slice()


def through_the_web(path):
    """A report the HTTP interface answers with: an unknown job, or the file of a queued one."""
    def produce(scene):
        client, pool = scene.web()
        headers = {"X-Penguin-User-Key": "user-a"}
        upload(client, BOX)
        if path == "file":
            job_id = submit(client, plate_configuration()).get_json()["job"]
            return client.get(f"/slices/{job_id}/file", headers=headers).get_json()
        if path == "gone":
            install_fake_orca(scene.tmp, scene.monkeypatch, "ok")
            pool._executor = ImmediateExecutor()
            job_id = submit(client, plate_configuration()).get_json()["job"]
            Path(pool.result(job_id)["path"]).unlink()          # the sliced file left the disk
            return client.get(f"/slices/{job_id}/file", headers=headers).get_json()
        if path == "nothing":
            return client.get("/nothing").get_json()
        return client.get("/slices/j0000", headers=headers).get_json()
    return produce


class ImmediateExecutor:
    def submit(self, fn, *args):
        fn(*args)


def bug_in_the_pipeline(scene):
    # A defect in the slice service's own code, reached through the entry point.
    def broken(*args, **kwargs):
        return 1 / 0
    scene.monkeypatch.setattr(plate_configuration_module, "write_plate_3mf", broken)
    scene.slice()


TWO = [{"ref": "box", "orientation": "+z", "angle": 0, "x": 50.0, "y": 50.0},
       {"ref": "box", "orientation": "+z", "angle": 0, "x": 70.0, "y": 50.0}]
SPACED = [dict(TWO[0]), dict(TWO[1], x=80.0)]
SERVER = "Slice again; if it fails again, ask a mentor to check the print server."
# Written out, not imported, so a change to the remedies fails a test.
TOO_CLOSE_REMEDY = ("Spread the instances out (or press Arrange), or move some instances to a second plate, and "
                    "slice again.")
TOO_CLOSE_SUPPORTS_REMEDY = ("Spread the instances out (or press Arrange), turn supports off, or move some instances "
                             "to a second plate, and slice again.")
ASCII_BOX = b"solid box\n facet normal 0 0 1\n  outer loop\n   vertex 0 0 0\n" + b" " * 100 + b"\nendsolid box\n"
LOOSE = (FIXTURES / "bad_stls" / "single_triangle.stl").read_bytes()
EMPTY_LAYERS = "Box #1 has nothing to print between 9.9 and 11.34 mm high, so the layers above would start in mid-air."


class Expected:
    """What the caller sees for one code; `detail` is a piece of the evidence it must hold."""

    def __init__(self, producer, message, stage, retryable, action, remedy, detail):
        self.producer, self.message, self.stage = producer, message, stage
        self.retryable, self.action, self.remedy, self.detail = retryable, action, remedy, detail


EXPECTED = {
    "slice.no_user_key": Expected(
        no_user_key, "The slicer was not told whose request this is.", "checking", False, None,
        "Try again; if it happens again, the server needs fixing.", "POST /parts without X-Penguin-User-Key"),
    "slice.bad_plate_configuration": Expected(
        lambda s: s.read(plate_configuration(instances=[])), "This plate configuration could not be read: it has no instances.", "checking",
        False, None, "Lay out the plate again and send a new slice.", "it has no instances"),
    "slice.too_many_instances": Expected(
        lambda s: s.read(plate_configuration(instances=[TWO[0]] * 151)),
        "This plate has 151 instances; the slicer takes up to 150 on one plate, so print the rest on a second plate.",
        "checking", False, "lower_quantities", "Lower the quantities and print the rest on a second plate.",
        "151 instances, cap 150"),
    "slice.too_many_parts": Expected(
        lambda s: s.read(plate_configuration(parts={f"p{i}": part_entry("Box", BOX) for i in range(26)},
                                             instances=[dict(TWO[0], ref=f"p{i}") for i in range(26)])),
        "This plate uses 26 different parts; the slicer takes up to 25 on one plate, so print the rest on a second "
        "plate.", "checking", False, None, "Use fewer different parts on this plate and print the rest on a second "
        "plate.",
        "26 different parts, cap 25"),
    "slice.unknown_printer": Expected(
        lambda s: s.read(plate_configuration(printer="Nope")), "The printer 'Nope' is not one the slicer knows.", "checking",
        False, None, "Choose a printer from the list, or ask a mentor to add this one.",
        "printer 'Nope' is not in the catalog"),
    "slice.profiles_not_offered": Expected(
        lambda s: s.read(plate_configuration(filament="Bambu PLA Basic @BBL H2S")),
        "Choose a filament and print settings from the list.", "checking", False, "choose_profiles",
        "Choose a filament and print settings from the lists and slice again.",
        "filament 'Bambu PLA Basic @BBL H2S' or process None is not offered with the default set"),
    "slice.bad_overrides": Expected(
        lambda s: s.read(plate_configuration(overrides={"wall_loops": "5.5"})),
        "Wall loops (Strength, Walls) must be a whole number, not '5.5'.", "checking", False, "choose_profiles",
        "Change that setting to a value it takes, or back to the profile's, and slice again.",
        "override 'wall_loops' is '5.5', not of the form integer"),
    "slice.profile_unreadable": Expected(
        profile_unreadable, "The print server's settings for this printer could not be read.", "checking", False,
        None, "Ask a mentor to check the print server's profiles; `make upgrade-orca` with the pinned version writes "
              "them again.", "JSONDecodeError"),
    "slice.part_missing": Expected(
        lambda s: s.read(plate_configuration(parts={})), "An instance on the plate names a part this plate configuration does not include.",
        "checking", False, "refresh_parts", "Load the parts again and send a new slice.",
        "instance 0 names part 'box', which parts does not list"),
    "slice.bad_units": Expected(
        bad_units, "The slicer was not told whether this part is in millimetres or inches.", "checking", False, None,
        "Choose millimetres or inches for the part and add it again.", "units 'cm', not 'mm' or 'in'"),
    # The part checks run when a part is added, on the Parts step: their remedies are about
    # adding it (service.UPLOAD_REMEDIES); the same codes from a slice are tested below.
    "slice.part_unreadable": Expected(
        lambda s: stl(s, b""), "The file for this part is empty.", "checking", False, None,
        "Export the part again as an STL and add it again.", "upload: 0 bytes"),
    "slice.part_not_binary": Expected(
        lambda s: stl(s, ASCII_BOX), "The file for this part is a text STL; the slicer needs a binary STL.",
        "checking", False, None, "Export the part again as a binary STL and add it again.", "bytes of ASCII STL"),
    "slice.part_too_detailed": Expected(
        oversize, "This part is too detailed to print here (over 7,500,084 bytes, the size of 150,000 triangles).",
        "checking", False, None, "Export the part with a coarser tessellation, or simplify it, and add it again.",
        "upload Content-Length 7,500,085 bytes, cap 7,500,084"),
    "slice.part_too_small": Expected(
        lambda s: stl(s, box_stl(0.05, 0.05, 0.05)), "This part is too small to print (0.05 x 0.05 x 0.05 mm).",
        "checking", False, None, "Check the part's units and size, and add it again.",
        "upload: 0.05 x 0.05 x 0.05 mm"),
    "slice.part_no_volume": Expected(
        lambda s: stl(s, LOOSE), "This part is loose triangles that enclose nothing, so there is nothing to print.",
        "checking", False, None, "Make the part a closed solid in CAD, export it again and add it again.",
        "1 triangles, none shares an edge with another"),
    "slice.part_too_large": Expected(
        lambda s: stl(s, box_stl(500, 500, 500)),
        "This part is 500 x 500 x 500 mm, larger than any printer here can print in any orientation (the largest "
        "prints 340.0 x 320.0 x 340.0 mm).", "checking", False, None,
        "Check the part's units, or split the part in CAD so each piece fits, and add the pieces.", "upload: "),
    "slice.placement_off_plate": Expected(
        lambda s: s.read(plate_configuration(instances=[dict(TWO[0], x=1.0)])), "Box #1 is not fully on the plate.", "checking",
        False, "arrange", "Move the instance fully onto the plate, or press Arrange, and slice again.",
        "Box #1 is not fully on the plate."),
    "slice.placement_too_tall": Expected(
        lambda s: placed(s, box_stl(20, 20, 341)), "Box #1 is taller than the printer can print (340 mm).", "checking",
        False, "choose_orientation", "Lay the part on another face so it is lower, and slice again.",
        "Box #1 is taller than the printer can print (340 mm)."),
    "slice.placement_too_close": Expected(
        lambda s: s.read(plate_configuration(instances=TWO)), "Box #1 and Box #2 are closer than 5 mm.", "checking", False,
        "arrange", TOO_CLOSE_REMEDY, "Box #1 and Box #2 are closer than 5 mm."),
    "slice.busy": Expected(
        busy, "The slicer is busy, try again in a minute.", "queued", True, None, "Wait a minute and slice again.",
        "the job queue is full"),
    "slice.scratch_unwritable": Expected(
        disk_full, "The print server could not write the slicer's working files.", "building", True, None,
        "Ask a mentor to check the print server's free disk space and its work folder, then slice again.",
        "No space left on device"),
    "slice.orca_missing": Expected(
        orca_missing, "The slicer could not be started.", "slicing", False, None,
        "Ask a mentor to check the print server; slicing is not set up on it.", "Orca Slicer is missing at "),
    "slice.orca_unstartable": Expected(
        lambda s: s.slice(), "The slicer could not be started.", "slicing", False, None,
        "Ask a mentor to check the print server; the slicer will not start on it.", "Permission denied"),
    "slice.timeout": Expected(
        timeout, "The slicer took too long on this plate.", "slicing", True, "lower_quantities",
        "Try again, or slice fewer instances at once.", "orca code timeout\nstopped by the slice service (timeout)"),
    "slice.cancelled": Expected(
        cancelled, "The slice was cancelled.", "slicing", True, None, "Send the slice again when you want it.",
        "stopped by the slice service (cancel) with SIGTERM"),
    "slice.out_of_memory": Expected(
        over_the_memory_ceiling(SPACED), "This plate is too large to slice: the slicer needed more than the 2,000 MB "
                                         "of memory the print server allows.", "slicing", False,
        "lower_quantities", "Remove some instances or the largest part and print them on a second plate.",
        "Orca's processes reached a peak of 2,099,200 kB (the watchdog's high-water reading of Orca's processes)"),
    "slice.orca_crashed": Expected(
        fake_orca("segv"), "The slicer crashed while slicing this plate.", "slicing", False, None,
        "Try another orientation or other print settings; if it crashes again, ask a mentor to check the part.",
        "ended by signal 11 (SIGSEGV), not sent by the slice service"),
    "slice.orca_killed": Expected(
        fake_orca("sigterm"), "Something on the print server stopped the slicer before it finished.", "slicing",
        True, None, SERVER, "ended by signal 15 (SIGTERM), not sent by the slice service"),
    "slice.orca_too_close": Expected(
        fake_orca("refuse"), "Two instances are too close together: the slicer found that their paths would meet.",
        "slicing", False, "arrange", TOO_CLOSE_REMEDY,
        "orca code -101\nexit code 155\norca error_string: too close\nSome objects are too close together"),
    "slice.crosses_edge": Expected(
        lambda s: s.orca_exit(204, -52), "A part crosses the edge of the plate.", "slicing", False, "arrange",
        "Move the instance fully onto the plate, or press Arrange, and slice again.",
        "orca code -52\nexit code 204\norca output line"),
    "slice.empty_layers": Expected(
        fake_orca("empty_layers"), EMPTY_LAYERS, "slicing", False, "enable_supports",
        "Turn Supports on, or repair the part in CAD so it has no gap, and slice again.",
        "orca warning_message: Object can't be printed for empty layer between 9.9 and 11.34."),
    "slice.empty_layers_with_supports": Expected(
        with_supports, EMPTY_LAYERS, "slicing", False, None,
        "Repair the part in CAD so it has no gap or loose surfaces, export it again and slice again.",
        "orca warning_message: Object can't be printed for empty layer"),
    "slice.no_layers": Expected(
        fake_orca("no_layers"), "The slicer found no layers to print: a part's surface may have holes, or a part may "
                                "be too thin to slice.", "slicing", False, None,
        "Repair the part in CAD so it is a closed solid, check its size and thickness, export it again and slice "
        "again.", "orca said: No layers were detected. You might want to repair your STL file(s)"),
    "slice.print_empty": Expected(
        fake_orca("print_empty"), "The slicer found nothing it can print with these settings: a part may be thinner "
                                  "than the nozzle can print.", "slicing", False, None,
        "Check the part's size and units, make thin features thicker than the nozzle, and slice again.",
        "orca said: The print is empty. The model is not printable with current print settings."),
    "slice.nothing_on_plate": Expected(
        lambda s: s.orca_exit(206, -50), "No part is fully on the plate.", "slicing", False, "arrange",
        "Move the instances onto the plate, or press Arrange, and slice again.", "orca code -50\nexit code 206"),
    "slice.orca_failed": Expected(
        fake_orca("general"), "The slicer could not slice this plate.", "slicing", False, None,
        "Try another orientation or other print settings, and slice again.",
        "orca code -100\nexit code 156\norca error_string: Failed slicing the model."),
    "slice.no_output": Expected(
        fake_orca("no_output"), "The slicer finished without writing the sliced file.", "slicing", True, None,
        SERVER, ""),
    "slice.unreadable_output": Expected(
        fake_orca("truncated"), "The sliced file the slicer wrote is damaged.", "slicing", True, None, SERVER,
        "plate.gcode.3mf is not a zip archive"),
    "slice.no_gcode": Expected(
        lambda s: s.orca_exit(0, archive=no_gcode), "The sliced file the slicer wrote has no G-code in it.", "slicing",
        True, None, SERVER, "archive entries:\nMetadata/slice_info.config"),
    "slice.left_off_plate": Expected(
        fake_orca("drop"), "A part was left off the plate.", "slicing", False, "arrange",
        "Move every instance fully onto the plate, or press Arrange, and slice again.",
        "expected 1 objects, found 0; missing ['Box #1']; unexpected []"),
    "slice.output_unwritable": Expected(
        output_is_a_file, "The print server could not save the sliced file.", "saving", False, None,
        "Ask a mentor to check that the print server can write to its output folder, then slice again.",
        "File exists"),
    "slice.unknown_job": Expected(
        through_the_web("progress"), "The print server does not know this slice; it may have expired.", "fetching",
        False, None, "Send the slice again.", "job 'j0000'"),
    "slice.not_ready": Expected(
        through_the_web("file"), "The sliced file is not ready yet.", "fetching", True, None,
        "Wait for the slice to finish, then fetch the sliced file.", "is queued"),
    "slice.file_gone": Expected(
        through_the_web("gone"), "The sliced file is no longer on the print server.", "fetching", False, None,
        "Send the slice again.", "FileNotFoundError"),
    "slice.bad_request": Expected(
        through_the_web("nothing"), "The print server does not offer GET /nothing.", "fetching", False, None,
        "Ask a mentor to check the program that sent this request; the print server does not offer it.",
        "HTTP 404 Not Found"),
    "slice.unexpected": Expected(
        bug_in_the_pipeline, "The slicer failed unexpectedly.", "slicing", False, None, SERVER,
        "ZeroDivisionError: division by zero"),
}


def produce(code, tmp_path, monkeypatch):
    """The error report for `code`: from the exception its producer raises, or the report
    a producer that goes through the HTTP interface returns."""
    try:
        returned = EXPECTED[code].producer(Scene(tmp_path, monkeypatch))
    except Exception as exc:
        return exc, error_report(exc)
    assert isinstance(returned, dict), f"{code}: the producer neither raised nor returned a report"
    return None, returned


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


def test_every_stage_is_a_known_stage():
    assert {stage for stage, *_ in CODES.values()} == STAGES


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


def upload_without_a_length(scene):
    """An upload whose body comes without a Content-Length (Transfer-Encoding: chunked)."""
    client, _pool = scene.web()
    return client.post("/parts?units=mm", headers={"X-Penguin-User-Key": "user-a", "Transfer-Encoding": "chunked"},
                       content_type="application/octet-stream", input_stream=io.BytesIO(BOX),
                       environ_overrides={"wsgi.input_terminated": True}).get_json()


def part_store_full(scene):
    """An upload the part store cannot keep: its disk is full."""
    def full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    client, _pool = scene.web()
    scene.monkeypatch.setattr("penguin_slice.part_store.os.fdopen", full)
    return upload(client, BOX).get_json()


# The two upload failures whose codes are shared with other failures: their own sentence and
# remedy, written out (a user adding a part on the Parts step reads them).
UPLOAD_EXPECTED = {
    "no_content_length": ("slice.bad_request", Expected(
        upload_without_a_length, "The slicer was not told how large this part is.", "fetching", False, None,
        "Add the part again; if it happens again, the server needs fixing.", "upload without Content-Length")),
    "part_store_full": ("slice.scratch_unwritable", Expected(
        part_store_full, "The slicer could not keep this part.", "building", True, None,
        "Add the part again in a few minutes; if it fails again, the server needs more free disk space.",
        "No space left on device")),
}


@pytest.mark.parametrize("case", list(UPLOAD_EXPECTED))
def test_an_upload_failure_says_what_to_do_about_the_upload(case, tmp_path, monkeypatch):
    code, expected = UPLOAD_EXPECTED[case]
    report = expected.producer(Scene(tmp_path, monkeypatch))
    assert report["code"] == code
    assert_report_shape(report)
    assert report["message"] == expected.message
    assert report["where"]["stage"] == expected.stage
    assert report["retryable"] is expected.retryable
    assert report.get("action") == expected.action
    assert report["remedy"] == expected.remedy
    assert expected.detail in report["detail"]
    assert not re.search(r"mentor|print server|slice again", report["message"] + report["remedy"], re.I)


def web_upload(data, units="mm"):
    def produce(scene):
        client, _pool = scene.web()
        return upload(client, data, units=units).get_json()
    return produce


def over_the_triangle_cap(scene):
    scene.monkeypatch.setattr(limits, "MAX_PART_TRIANGLES", 11)
    return web_upload(BOX)(scene)                   # 12 triangles


def profiles_unreadable_on_upload(scene):
    """The server's own printer profiles cannot be read when a part arrives (the largest plate)."""
    def broken():
        raise ValueError("Expecting property name enclosed in double quotes")
    scene.monkeypatch.setattr(service_module, "_largest_plate", broken)
    return web_upload(BOX)(scene)


def cut_off_upload(scene):
    """An upload whose body ends before its Content-Length: the connection was lost."""
    client, _pool = scene.web()
    return client.post("/parts?units=mm", headers={"X-Penguin-User-Key": "user-a"},
                       content_type="application/octet-stream", input_stream=io.BytesIO(BOX[:100]),
                       environ_overrides={"CONTENT_LENGTH": str(len(BOX))}).get_json()


def bug_while_a_part_arrives(scene):
    scene.monkeypatch.setattr("penguin_slice.web.upload_part", lambda *a: 1 / 0)
    return web_upload(BOX)(scene)


# Every code POST /parts can answer, through the HTTP interface, with the remedy a user reads
# on the Parts step (slice/README.md, "When things go wrong": export the part again, simplify
# it, check its units). Written out, not imported, so a change to them fails a test.
UPLOAD_ANSWERS = {
    "no_user_key": ("slice.no_user_key", no_user_key, "Try again; if it happens again, the server needs fixing."),
    "bad_units": ("slice.bad_units", bad_units, "Choose millimetres or inches for the part and add it again."),
    "no_content_length": ("slice.bad_request", upload_without_a_length,
                          "Add the part again; if it happens again, the server needs fixing."),
    "cut_off": ("slice.bad_request", cut_off_upload,
                "Add the part again; if it happens again, the server needs fixing."),
    "content_length_over_cap": ("slice.part_too_detailed", oversize,
                                "Export the part with a coarser tessellation, or simplify it, and add it again."),
    "triangles_over_cap": ("slice.part_too_detailed", over_the_triangle_cap,
                           "Export the part with a coarser tessellation, or simplify it, and add it again."),
    "empty": ("slice.part_unreadable", web_upload(b""), "Export the part again as an STL and add it again."),
    "text_stl": ("slice.part_not_binary", web_upload(ASCII_BOX),
                 "Export the part again as a binary STL and add it again."),
    "too_small": ("slice.part_too_small", web_upload(box_stl(0.05, 0.05, 0.05)),
                  "Check the part's units and size, and add it again."),
    "no_volume": ("slice.part_no_volume", web_upload(LOOSE),
                  "Make the part a closed solid in CAD, export it again and add it again."),
    "too_large": ("slice.part_too_large", web_upload(box_stl(500, 500, 500)),
                  "Check the part's units, or split the part in CAD so each piece fits, and add the pieces."),
    "part_store_full": ("slice.scratch_unwritable", part_store_full,
                        "Add the part again in a few minutes; if it fails again, the server needs more free disk "
                        "space."),
    "profiles_unreadable": ("slice.profile_unreadable", profiles_unreadable_on_upload,
                            "Add the part again later; if it fails again, the server needs fixing."),
    "bug": ("slice.unexpected", bug_while_a_part_arrives,
            "Add the part again; if it fails again, the server needs fixing."),
}


def test_upload_answers_cover_every_code_post_parts_answers():
    from penguin_slice.service import UPLOAD_REMEDIES
    assert {code for code, _p, _r in UPLOAD_ANSWERS.values()} == set(UPLOAD_REMEDIES)


@pytest.mark.parametrize("case", list(UPLOAD_ANSWERS))
def test_every_upload_refusal_says_what_to_do_on_the_parts_step(case, tmp_path, monkeypatch):
    """No remedy of an upload asks for a slice, a mentor or the print server, and none
    carries an action: the part was never added, so there is nothing to slice again."""
    code, producer, remedy = UPLOAD_ANSWERS[case]
    report = producer(Scene(tmp_path, monkeypatch))
    assert report["code"] == code
    assert_report_shape(report)
    assert report["remedy"] == remedy
    assert "action" not in report
    assert not re.search(r"mentor|print server|slic", report["remedy"], re.I)
    assert not re.search(r"mentor|student|team|print server|slice again|new slice", report["message"], re.I)


def test_an_upload_cut_off_says_the_part_did_not_arrive_whole(tmp_path, monkeypatch):
    report = cut_off_upload(Scene(tmp_path, monkeypatch))
    assert (report["message"], report["detail"]) == ("This part did not arrive whole.", "HTTP 400 Bad Request")


def test_the_upload_message_for_unreadable_profiles_is_about_the_part(tmp_path, monkeypatch):
    report = profiles_unreadable_on_upload(Scene(tmp_path, monkeypatch))
    assert report["message"] == "The slicer could not read its printer settings, so it could not check this part."
    assert "Expecting property name" in report["detail"]


# The part codes from a slice (a part read again for a plate) keep the slice's remedies.
SLICE_PART_REMEDIES = {
    "slice.part_unreadable": ("refresh_parts", "Export the part again and send a new slice."),
    "slice.part_not_binary": (None, "Export the part again as a binary STL and send a new slice."),
    "slice.part_too_detailed": (None, "Export the part with a coarser tessellation, or simplify it, and slice again."),
    "slice.part_too_small": (None, "Check the part's units and size, then slice again."),
    "slice.part_no_volume": (None, "Make the part a closed solid in CAD, export it again and send a new slice."),
    "slice.part_too_large": (None, "Check the part's units, or split the part in CAD so each piece fits, and "
                                   "slice again."),
}


@pytest.mark.parametrize("code", list(SLICE_PART_REMEDIES))
def test_a_part_code_from_a_slice_keeps_the_slices_remedy(code):
    from penguin_slice.mesh import MeshError
    report = error_report(MeshError("A part could not be read.", "x", code))
    assert (report.get("action"), report["remedy"]) == SLICE_PART_REMEDIES[code]


def test_the_three_ways_orca_can_end_on_a_signal_are_distinct(tmp_path, monkeypatch):
    """A kill for memory, a crash, a stop by someone else, and the service's own stops."""
    reports = {code: produce(code, tmp_path / code, monkeypatch)[1]
               for code in ("slice.orca_crashed", "slice.orca_killed", "slice.timeout", "slice.cancelled",
                            "slice.out_of_memory")}       # last: its producer replaces the memory reader
    assert len({r["message"] for r in reports.values()}) == 5
    assert len({r["remedy"] for r in reports.values()}) == 5


def test_orca_refusal_detail_leads_with_orca_code(tmp_path, monkeypatch):
    _exc, report = produce("slice.crosses_edge", tmp_path, monkeypatch)
    assert report["detail"].splitlines()[:3] == ["orca code -52", "exit code 204", "orca output line"]


def test_empty_layers_name_the_instance_and_the_height(tmp_path, monkeypatch):
    _exc, report = produce("slice.empty_layers", tmp_path, monkeypatch)
    assert report["where"] == {"instance": "Box #1", "height_mm": 9.9, "stage": "slicing"}


def test_with_supports_on_no_action_is_offered_that_cannot_help(tmp_path, monkeypatch):
    _exc, report = produce("slice.empty_layers_with_supports", tmp_path, monkeypatch)
    assert "action" not in report and "Supports" not in report["remedy"]


def test_with_supports_on_the_placement_check_asks_for_the_supports_spacing(tmp_path, monkeypatch):
    """SPACED is 10 mm apart: enough with supports off, refused with them on, before Orca
    runs, with both instances named and a remedy that offers turning supports off."""
    scene = Scene(tmp_path, monkeypatch)
    with pytest.raises(service_module.PlateConfigurationRefused) as caught:
        scene.read(plate_configuration(instances=SPACED, overrides={"enable_support": "1"}))
    report = error_report(caught.value)
    assert report["code"] == "slice.placement_too_close"
    assert report["message"] == "Box #1 and Box #2 are closer than 12 mm, the room supports need between instances."
    assert report["where"] == {"part": "Box", "instance": "Box #1", "other_instance": "Box #2", "stage": "checking"}
    assert (report["remedy"], report["action"]) == (TOO_CLOSE_SUPPORTS_REMEDY, "arrange")
    scene.read(plate_configuration(instances=SPACED))                                   # supports off: passes
    scene.read(plate_configuration(instances=[TWO[0], dict(TWO[1], x=82.0)], overrides={"enable_support": "1"}))  # 12


def test_a_wide_brim_passes_the_placement_check_and_orca_refuses_it(tmp_path, monkeypatch):
    """A brim (or a raft, or printing one object at a time) makes an instance need more room;
    the placement check does not know it, so a plate 5 mm apart passes and Orca's -101 comes
    back as slice.orca_too_close."""
    scene = Scene(tmp_path, monkeypatch)
    apart_5 = [TWO[0], dict(TWO[1], x=75.0)]            # 20 mm boxes, footprints 5 mm apart
    brim = {"brim_type": "outer_only", "brim_width": "10"}
    assert scene.read(plate_configuration(instances=apart_5, overrides=brim)).overrides == brim
    install_fake_orca(tmp_path, monkeypatch, "refuse")
    with pytest.raises(slicer.SliceError) as caught:
        scene.slice(plate_configuration(instances=apart_5, overrides=brim))
    assert error_report(caught.value)["code"] == "slice.orca_too_close"


def test_a_table_of_settings_that_cannot_be_read(tmp_path, monkeypatch):
    """The server's own table damaged on disk: a plate with settings is refused with the
    server's failure, and the route that serves the table answers 500 with the same report."""
    from penguin_slice import settings_table
    broken = tmp_path / "table.json"
    broken.write_text("{not a table")
    monkeypatch.setattr(settings_table, "TABLE_PATH", broken)
    settings_table.load.cache_clear()
    try:
        scene = Scene(tmp_path, monkeypatch)
        with pytest.raises(settings_table.TableUnreadable) as caught:
            scene.read(plate_configuration(overrides={"wall_loops": "3"}))
        report = error_report(caught.value)
        assert_report_shape(report)
        assert (report["code"], report["message"]) == ("slice.profile_unreadable",
                                                       "The slicer could not read its table of settings.")
        assert "JSONDecodeError" in report["detail"] and report["where"] == {"stage": "checking"}
        from penguin_slice.web import create_app, slice_worker
        logs = []
        pool = JobPool(slice_worker, executor=mock.Mock(), error_report=error_report)
        client = create_app(tmp_path / "work", pool, start_sweeper=False, log=logs.append).test_client()
        answer = client.get("/settings-table")
        assert answer.status_code == 500
        assert answer.get_json()["code"] == "slice.profile_unreadable"
        assert logs[-1]["event"] == "slice_http_error" and logs[-1]["path"] == "/settings-table"
        assert logs[-1]["error_code"] == "slice.profile_unreadable"
        assert str(broken) in logs[-1]["error_detail"] and "JSONDecodeError" in logs[-1]["error_detail"]
    finally:
        settings_table.load.cache_clear()


PAIR_MEETS = "Box #1 and Box #2 are too close together: the slicer found that their paths would meet"
ANY_MEETS = "Two instances are too close together: the slicer found that their paths would meet"
SUPPORTS_CLAUSE = ", most likely their supports, which need more room between instances."


@pytest.mark.parametrize("mode, supports, message, where, remedy", [
    ("refuse_logged", "off", PAIR_MEETS + ".", {"instance": "Box #1", "other_instance": "Box #2"}, TOO_CLOSE_REMEDY),
    ("refuse_logged", "on", PAIR_MEETS + SUPPORTS_CLAUSE, {"instance": "Box #1", "other_instance": "Box #2"},
     TOO_CLOSE_SUPPORTS_REMEDY),
    ("refuse", "on", ANY_MEETS + SUPPORTS_CLAUSE, {}, TOO_CLOSE_SUPPORTS_REMEDY),
])
def test_orcas_too_close_names_the_pair_from_its_debug_log(mode, supports, message, where, remedy, tmp_path,
                                                           monkeypatch):
    """Orca's -101 for a plate the checks passed: the pair its debug log names (its line
    names the second instance first), the supports as the likely cause when they are on."""
    scene = Scene(tmp_path, monkeypatch)
    install_fake_orca(tmp_path, monkeypatch, mode)
    with pytest.raises(slicer.SliceError) as caught:
        scene.slice(plate_configuration(instances=[TWO[0], dict(TWO[1], x=95.0)],
                                        overrides={"enable_support": "1" if supports == "on" else "0"}))
    report = error_report(caught.value)
    assert_report_shape(report)
    assert (report["code"], report["message"], report["remedy"]) == ("slice.orca_too_close", message, remedy)
    assert report["where"] == dict(where, stage="slicing")
    assert ("orca debug log: paths meet between Box #1 and Box #2" in report["detail"]) is bool(where)


def test_out_of_memory_on_a_plate_of_one_instance_does_not_say_remove_instances(tmp_path, monkeypatch):
    scene = Scene(tmp_path, monkeypatch)
    with pytest.raises(slicer.SliceError) as caught:
        over_the_memory_ceiling(plate_configuration()["instances"])(scene)
    report = error_report(caught.value)
    assert report["code"] == "slice.out_of_memory"
    assert report["remedy"] == "Split the part in CAD into smaller pieces, or simplify it, and slice again."
    assert "action" not in report and "instances" not in report["remedy"]


@pytest.mark.parametrize("code", ["slice.no_layers", "slice.print_empty"])
def test_orcas_reason_for_nothing_to_slice_names_the_only_part(code, tmp_path, monkeypatch):
    _exc, report = produce(code, tmp_path, monkeypatch)
    assert report["where"] == {"part": "Box", "stage": "slicing"}


def test_with_two_parts_orcas_reason_names_none(tmp_path, monkeypatch):
    scene = Scene(tmp_path, monkeypatch)
    scene.upload(box_stl(8, 8, 8))
    install_fake_orca(tmp_path, monkeypatch, "no_layers")
    job = plate_configuration(parts={"box": part_entry("Box", BOX), "peg": part_entry("Peg", box_stl(8, 8, 8))},
                              instances=[TWO[0], dict(TWO[1], ref="peg", x=90.0)])
    with pytest.raises(slicer.SliceError) as caught:
        scene.slice(job)
    assert error_report(caught.value)["where"] == {"stage": "slicing"}


@pytest.mark.parametrize("code, where", [
    ("slice.part_missing", {}),
    # On arrival a part has no name: its refusals name none.
    ("slice.part_unreadable", {}), ("slice.part_too_small", {}), ("slice.part_too_detailed", {}),
    ("slice.part_too_large", {}), ("slice.part_no_volume", {}), ("slice.part_not_binary", {}),
    ("slice.placement_too_close", {"part": "Box", "instance": "Box #1", "other_instance": "Box #2"}),
    ("slice.placement_too_tall", {"part": "Box", "instance": "Box #1"}),
    ("slice.left_off_plate", {"instance": "Box #1"}),
])
def test_where_names_the_part_and_instance(code, where, tmp_path, monkeypatch):
    _exc, report = produce(code, tmp_path, monkeypatch)
    assert {k: v for k, v in report["where"].items() if k != "stage"} == where


def test_parts_missing_from_the_part_store_list_every_one(tmp_path, monkeypatch):
    scene = Scene(tmp_path, monkeypatch)
    with pytest.raises(service_module.PlateConfigurationRefused) as caught:
        parts_gone(scene)
    report = error_report(caught.value)
    assert_report_shape(report)
    assert (report["code"], report["action"], report["retryable"], report["remedy"]) == (
        "slice.part_missing", "refresh_parts", False, "Add the parts again and slice again.")
    assert [m["key"] for m in report["where"]["missing_parts"]] == ["box"]


def test_the_contracts_parts_missing_example_is_what_the_code_produces(tmp_path, monkeypatch):
    example = json.loads((CONTRACTS / "examples" / "error-report-parts-missing.json").read_text())
    missing = example["where"]["missing_parts"]
    assert error_report(service_module.parts_missing(missing)) == example


def test_job_failure_reports_the_failure_that_caused_it(tmp_path):
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


def test_an_unexpected_detail_never_grows_without_bound():
    # A bug whose message carries what a caller sent: the detail is cut.
    detail = error_report(KeyError("k" * 300_000))["detail"]
    assert detail.startswith("KeyError: 'kkk") and detail.endswith(" [cut]") and len(detail) <= 2010


def test_queue_full_is_retryable():
    report = error_report(QueueFull())
    assert report["retryable"] is True and report["code"] == "slice.busy"


def test_codes_are_stable_names():
    for code in CODES:
        assert re.fullmatch(r"slice\.[a-z_]+", code), code


def test_reports_never_carry_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SLICE_TEST_TOKEN", "s3cr3t-value")
    for code in ("slice.orca_unstartable", "slice.orca_too_close", "slice.unexpected", "slice.out_of_memory"):
        _exc, report = produce(code, tmp_path / code, monkeypatch)
        assert "s3cr3t-value" not in json.dumps(report)


def test_contract_example_is_a_report_the_service_produces(tmp_path, monkeypatch):
    """contracts/examples/error-report.json is what the real Orca's empty-layer refusal
    gave for the corpus' slivers_and_lattice part (tests_orca checks it); here every field
    but the message's instance name, the where and the detail must be what the code gives."""
    example = json.loads((CONTRACTS / "examples" / "error-report.json").read_text())
    assert_report_shape(example)
    _exc, report = produce(example["code"], tmp_path, monkeypatch)
    same = ("code", "remedy", "action", "retryable")
    assert {k: report.get(k) for k in same} == {k: example.get(k) for k in same}
    assert example["detail"].splitlines()[:2] == ["orca code -100", "exit code 156"]
