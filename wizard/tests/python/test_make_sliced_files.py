"""wizard/trials/make_sliced_files.py: the first trial's three plates, written out as plate
configurations in wizard/trials/plates/, and the client that has a slice service slice each
one and saves its sliced file. The slice service here is a fake on a port the system chooses;
the real one is started by hand (wizard/trials/preview/README.md)."""
import hashlib
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from trials import make_sliced_files as msf

WIZARD = Path(__file__).resolve().parents[2]
PLATES = WIZARD / "trials" / "plates"

# Each footprint, x by y (mm), in the orientation the plates use, as the slice service measured
# them (slice/tests/frc_parts.py, FOOTPRINT_MM); the spacer is 5/8 inch across.
FOOTPRINT = {"clamp-plate-inner": (50.8, 50.8), "elevator-block-bottom-inner": (88.9, 63.5),
             "elevator-block-carriage": (88.9, 57.15), "elevator-block-top": (88.9, 82.55),
             "elevator-top-inner": (50.8, 57.15), "inner-spacer": (50.8, 50.8), "outer-clamp": (50.8, 50.8),
             "pulley-v3": (19.05, 19.05), "hex-spacer": (15.875, 15.875)}


def least_gap(configuration):
    """The least distance between two instances' footprints (rectangles; none is turned)."""
    boxes = []
    for i in configuration["instances"]:
        w, d = FOOTPRINT[i["ref"]]
        boxes.append((i["x"] - w / 2, i["y"] - d / 2, i["x"] + w / 2, i["y"] + d / 2))
    least = float("inf")
    for k, a in enumerate(boxes):
        for b in boxes[k + 1:]:
            dx = max(b[0] - a[2], a[0] - b[2], 0.0)
            dy = max(b[1] - a[3], a[1] - b[3], 0.0)
            least = min(least, (dx * dx + dy * dy) ** 0.5)
    return least, boxes


def test_the_committed_plates_are_what_the_script_writes(tmp_path):
    msf.write_plates(tmp_path)
    written = sorted(p.name for p in tmp_path.iterdir())
    assert written == ["blocks-12-supports.json", "four-each-b-supports.json", "spacers-150.json"]
    for name in written:
        assert (PLATES / name).read_bytes() == (tmp_path / name).read_bytes(), name


def test_four_each_b_is_two_of_each_real_part_mirrored_with_supports_on():
    configuration = msf.plate_configurations()["four-each-b-supports"]
    refs = [i["ref"] for i in configuration["instances"]]
    assert len(refs) == 16 and all(refs.count(ref) == 2 for ref in set(refs)) and len(set(refs)) == 8
    assert configuration["overrides"] == {"supports": "on"}
    tops = sorted(i["x"] for i in configuration["instances"] if i["ref"] == "elevator-block-top")
    assert tops == [188.0, 290.0]                        # four-each-a's 152 and 50, mirrored about 170
    assert least_gap(configuration)[0] >= 12.0           # the spacing with supports on


def test_blocks_12_is_three_by_four_bottom_inners_12_5_mm_apart_with_supports_on():
    configuration = msf.plate_configurations()["blocks-12-supports"]
    assert [i["ref"] for i in configuration["instances"]] == ["elevator-block-bottom-inner"] * 12
    assert {i["orientation"] for i in configuration["instances"]} == {"-z"}
    assert len({i["x"] for i in configuration["instances"]}) == 3
    assert len({i["y"] for i in configuration["instances"]}) == 4
    assert least_gap(configuration)[0] == pytest.approx(12.5)
    assert configuration["overrides"] == {"supports": "on"}


def test_spacers_150_is_13_by_12_less_6_22_mm_apart_with_supports_off():
    configuration = msf.plate_configurations()["spacers-150"]
    instances = configuration["instances"]
    assert len(instances) == 150 and {i["ref"] for i in instances} == {"hex-spacer"}
    xs, ys = sorted({i["x"] for i in instances}), sorted({i["y"] for i in instances})
    assert len(xs) == 13 and len(ys) == 12
    assert all(b - a == pytest.approx(22.0) for a, b in zip(xs, xs[1:]))
    assert configuration["overrides"] == {"supports": "off"}


@pytest.mark.parametrize("name", ["four-each-b-supports", "blocks-12-supports", "spacers-150"])
def test_every_plate_fits_inside_the_plate_margin_and_names_files_that_exist(name):
    configuration = msf.plate_configurations()[name]
    _, boxes = least_gap(configuration)
    assert all(b[0] >= 3 and b[1] >= 3 and b[2] <= 337 and b[3] <= 317 for b in boxes)
    files = msf.part_files(configuration)
    assert set(files) == set(configuration["parts"])
    assert all(path.is_file() for path in files.values())


ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@pytest.mark.parametrize("name", ["four-each-b-supports", "blocks-12-supports", "spacers-150"])
def test_every_plate_is_a_plate_configuration_in_its_phase_2_form(name):
    """contracts/plate-configuration.md, "Fields in phase 2" and "A part in phase 2": the plate's
    id and a submission's value, and each part named by the hash of its bytes and its units."""
    configuration = msf.plate_configurations()[name]
    assert set(configuration) == {"plate_id", "submission_id", "parts", "instances", "overrides"}
    assert ID.match(configuration["plate_id"]) and ID.match(configuration["submission_id"])
    files = msf.part_files(configuration)
    for key, part in configuration["parts"].items():
        assert set(part) == {"name", "sha256", "units"}
        assert part["units"] == "mm"
        assert part["sha256"] == hashlib.sha256(files[key].read_bytes()).hexdigest()


def test_each_plate_has_its_own_id():
    ids = [c["plate_id"] for c in msf.plate_configurations().values()]
    assert len(set(ids)) == 3


class FakeSliceService:
    """Answers POST /parts, POST /slices, the event stream, the file and the summary, as told,
    and keeps every request: (method, path, headers, body)."""

    def __init__(self, post_status=202, post_body=None, reports=None, file_bytes=b"PK fake", part_status=201,
                 part_body=None, file_status=200, file_body=None):
        self.received = []
        self.post_status = post_status
        self.post_body = post_body if post_body is not None else {"job": "j1", "progress": {}, "part_warnings": []}
        self.reports = reports if reports is not None else [
            {"job": "j1", "state": "running", "elapsed_s": 1, "sequence": 1, "fraction": 0.5},
            {"job": "j1", "state": "done", "elapsed_s": 2, "sequence": 2, "fraction": 1}]
        self.file_bytes = file_bytes
        self.part_status, self.part_body = part_status, part_body
        self.file_status, self.file_body = file_status, file_body
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def answer(self, status, body, content_type="application/json"):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def keep(self, body=b""):
                fake.received.append((self.command, self.path, dict(self.headers), body))

            def do_POST(self):
                length = int(self.headers["Content-Length"])
                body = self.rfile.read(length)
                self.keep(body)
                if self.path.startswith("/parts?"):
                    record = fake.part_body if fake.part_body is not None else {
                        "sha256": hashlib.sha256(body).hexdigest(), "units": self.path.split("units=")[1],
                        "measurements": {}, "warnings": []}
                    self.answer(fake.part_status, record)
                else:
                    self.answer(fake.post_status, fake.post_body)

            def do_GET(self):
                self.keep()
                if self.path == "/slices/j1/events":
                    body = "".join(f"data: {json.dumps(r)}\n\n" for r in fake.reports).encode()
                    self.answer(200, body, "text/event-stream")
                elif self.path == "/slices/j1/file":
                    if fake.file_status != 200:
                        self.answer(fake.file_status, fake.file_body)
                    else:
                        self.answer(200, fake.file_bytes, "application/octet-stream")
                elif self.path == "/slices/j1/summary":
                    self.answer(200, {"file": "x.gcode.3mf", "layer_count": 13})
                else:
                    self.answer(404, {"code": "slice.unknown_job"})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()


def test_a_plate_sliced_is_saved_with_its_summary(tmp_path):
    with FakeSliceService(file_bytes=b"PK the sliced file") as service:
        path = msf.slice_plate(service.url, "spacers-150", tmp_path)
    assert path == tmp_path / "spacers-150.gcode.3mf"
    assert path.read_bytes() == b"PK the sliced file"
    assert json.loads((tmp_path / "spacers-150.summary.json").read_text())["layer_count"] == 13
    assert [(m, p) for m, p, _, _ in service.received] == [
        ("POST", "/parts?units=mm"), ("POST", "/slices"), ("GET", "/slices/j1/events"),
        ("GET", "/slices/j1/file"), ("GET", "/slices/j1/summary")]


def test_each_part_is_uploaded_by_itself_and_the_plate_configuration_names_it_by_hash(tmp_path):
    with FakeSliceService() as service:
        msf.slice_plate(service.url, "four-each-b-supports", tmp_path)
    uploads = [(path, headers, body) for method, path, headers, body in service.received if path.startswith("/parts")]
    assert len(uploads) == 8                                     # eight different parts, each once
    for path, headers, body in uploads:
        assert path == "/parts?units=mm" and headers["Content-Type"] == "application/octet-stream"
    spacer = (WIZARD.parent / "contracts" / "examples" / "parts" / "real" / "inner-spacer.stl").read_bytes()
    assert spacer in [body for _, _, body in uploads]
    (_, _, headers, body), = [r for r in service.received if r[1] == "/slices"]
    assert headers["Content-Type"] == "application/json"
    sent = json.loads(body)
    committed = msf.plate_configurations()["four-each-b-supports"]
    assert sent["parts"] == committed["parts"] and sent["instances"] == committed["instances"]
    assert sent["plate_id"] == committed["plate_id"]
    # A new value for each submission (contracts/plate-configuration.md, "The submission's value").
    assert sent["submission_id"] != committed["submission_id"] and ID.match(sent["submission_id"])


def test_every_request_carries_the_user_key(tmp_path):
    with FakeSliceService() as service:
        msf.slice_plate(service.url, "spacers-150", tmp_path, user_key="someone")
    assert {headers.get("X-Penguin-User-Key") for _, _, headers, _ in service.received} == {"someone"}


def test_a_part_the_slice_service_refuses_says_its_code_and_sentence(tmp_path):
    refusal = {"code": "slice.part_too_detailed", "message": "This part is too detailed.", "retryable": False, "detail": ""}
    with FakeSliceService(part_status=413, part_body=refusal) as service:
        with pytest.raises(msf.SliceFailed) as failed:
            msf.slice_plate(service.url, "spacers-150", tmp_path)
    assert str(failed.value) == ("spacers-150: the slice service refused the part hex-spacer "
                                 "(HTTP 413, slice.part_too_detailed): This part is too detailed.")
    assert [p for _, p, _, _ in service.received] == ["/parts?units=mm"]
    assert not list(tmp_path.iterdir())


def test_a_part_kept_under_another_hash_is_a_failure(tmp_path):
    record = {"sha256": "0" * 64, "units": "mm", "measurements": {}, "warnings": []}
    with FakeSliceService(part_body=record) as service:
        with pytest.raises(msf.SliceFailed) as failed:
            msf.slice_plate(service.url, "spacers-150", tmp_path)
    assert str(failed.value).startswith(f"spacers-150: the slice service kept the part hex-spacer as {'0' * 64} in mm, not as ")
    assert [p for _, p, _, _ in service.received] == ["/parts?units=mm"]


def test_a_sliced_file_that_is_not_there_is_a_failure_and_nothing_is_saved(tmp_path):
    gone = {"code": "slice.file_gone", "message": "The sliced file is no longer on the print server.",
            "retryable": False, "detail": ""}
    with FakeSliceService(file_status=410, file_body=gone) as service:
        with pytest.raises(msf.SliceFailed) as failed:
            msf.slice_plate(service.url, "spacers-150", tmp_path)
    assert str(failed.value) == ("spacers-150: /slices/j1/file answered HTTP 410 (slice.file_gone): "
                                 "The sliced file is no longer on the print server.")
    assert not list(tmp_path.iterdir())


def test_the_command_line_without_a_slice_service_exits_2(capsys):
    assert msf.main(["--plate", "spacers-150"]) == 2
    assert "--url is needed: the address of a slice service started by hand" in capsys.readouterr().err


def test_a_plate_the_slice_service_refuses_says_its_code_and_sentence(tmp_path):
    refusal = {"code": "slice.placement_too_close", "message": "Two instances are too close.",
               "retryable": False, "detail": ""}
    with FakeSliceService(post_status=422, post_body=refusal) as service:
        with pytest.raises(msf.SliceFailed) as failed:
            msf.slice_plate(service.url, "spacers-150", tmp_path)
    assert str(failed.value) == ("spacers-150: the slice service refused it (HTTP 422, slice.placement_too_close): "
                                 "Two instances are too close.")
    assert not list(tmp_path.iterdir())


def test_a_slice_that_fails_says_its_code_and_sentence(tmp_path):
    reports = [{"job": "j1", "state": "failed", "elapsed_s": 3, "sequence": 4,
                "error": {"code": "slice.out_of_memory", "message": "The plate needs more memory."}}]
    with FakeSliceService(reports=reports) as service:
        with pytest.raises(msf.SliceFailed) as failed:
            msf.slice_plate(service.url, "blocks-12-supports", tmp_path)
    assert str(failed.value) == ("blocks-12-supports: the slice failed (slice.out_of_memory): "
                                 "The plate needs more memory.")


def test_a_stream_that_ends_before_a_final_report_is_a_failure(tmp_path):
    reports = [{"job": "j1", "state": "running", "elapsed_s": 1, "sequence": 1}]
    with FakeSliceService(reports=reports) as service:
        with pytest.raises(msf.SliceFailed) as failed:
            msf.slice_plate(service.url, "spacers-150", tmp_path)
    assert str(failed.value) == "spacers-150: the progress stream ended before the slice job did (last state: running)"


def test_a_slice_service_that_cannot_be_reached_is_named(tmp_path):
    with FakeSliceService() as service:
        url = service.url
    with pytest.raises(msf.SliceFailed) as failed:
        msf.slice_plate(url, "spacers-150", tmp_path)
    assert str(failed.value).startswith(f"spacers-150: no slice service answers at {url} (")


def test_the_command_line_names_an_unknown_plate_and_exits_2(capsys):
    assert msf.main(["--url", "http://127.0.0.1:1", "--plate", "no-such-plate"]) == 2
    assert "no-such-plate is not one of: blocks-12-supports, four-each-b-supports, spacers-150" in capsys.readouterr().err


def test_the_command_line_writes_the_plates_without_a_slice_service(tmp_path):
    assert msf.main(["--write-plates", "--plates-dir", str(tmp_path)]) == 0
    assert (tmp_path / "spacers-150.json").is_file()
