"""The walk of phase 2's "Done when", over HTTP as the wizard makes it: sign in, read who the
user is, the configuration and the table of settings, upload real parts, submit a plate,
follow its progress stream to the end, read the sliced file's details and download it."""

import io
import re
import zipfile

from joined.plates import CLAMP_PLATE, PULLEY, Placed, clamp_plate, first_profile, plate

DEV_ME = {"user": {"id": "dev-user", "name": "Development User"},
          "groups": [{"id": "dev-group", "name": "Development Group"}]}
STAGES = ["queued", "building_plate", "slicing", "loading", "preparing", "slicing_mesh",
          "generating_walls", "generating_infill", "generating_supports", "optimizing_toolpath",
          "generating_gcode", "exporting", "reading_result"]


def test_sign_in_and_read_what_a_page_reads_when_it_opens(page, slice_service):
    assert page.me() == DEV_ME
    configuration = page.configuration()
    assert configuration["source"] == "default"
    assert configuration["name"] == "PenguinSlicer default"
    assert configuration["revision"] is None
    profile = first_profile(configuration["configuration"])

    table, headers = page.settings_table(gzip=True)
    assert headers["content-encoding"] == "gzip"
    plain, plain_headers = page.settings_table(gzip=False)
    assert "content-encoding" not in plain_headers
    assert table == plain
    assert table["format"] == 1 and table["orca_version"] == "2.4.2"
    # What the configuration names is what the running slice service offers.
    catalog = table["catalog"]
    assert profile["printer"] in [p["name"] for p in catalog["printers"]]
    assert profile["filament"] in [f["name"] for f in catalog["filaments"]]
    assert profile["process"] in [p["name"] for p in catalog["processes"]]
    assert set(table["process_values"][profile["process"]]) == {s["name"] for s in table["settings"]}


def test_a_quiet_slice_keeps_both_streams_open(page, slice_service, front_server):
    """While Orca reports nothing, the slice service repeats its latest report every 15
    seconds and the front server sends the page a comment line at least as often; neither
    stream is given up as silent. About 16 seconds, the one test that waits for a quiet
    stream's first keep-alive: the stand-in Orca ends itself after 25."""
    slice_service.orca_mode("gate")
    accepted = page.submit(clamp_plate(page))
    stream = page.stream(accepted["id"])
    held = stream.wait_for_stage("slicing_mesh")
    stream.wait_for_comment()
    assert stream.reports[-1] == held, "the slice service's repeat is not passed on again"
    slice_service.release_orca()
    assert stream.wait_closed().final["state"] == "done"
    assert front_server.running.events("slice_stream_reopening") == []


def test_from_upload_to_download(page, slice_service, front_server):
    profile = first_profile(page.configuration()["configuration"])
    clamp = page.upload(CLAMP_PLATE)
    assert clamp["units"] == "mm" and clamp["measurements"]["triangles"] == 8756
    assert clamp["measurements"]["size_mm"] == [4.762, 50.8, 50.8]
    pulley = page.upload(PULLEY)
    # The same bytes again answer the same record.
    assert page.upload(CLAMP_PLATE) == clamp

    configuration = plate([Placed("clamp", "Clamp Plate Inner", clamp, [("+x", 0, 100.0, 100.0)]),
                           Placed("pulley", "Pulley v3", pulley,
                                  [("+z", 0, 220.0, 100.0), ("+z", 90, 220.0, 200.0)])], profile)
    accepted = page.submit(configuration)
    assert accepted["plate_id"] == configuration["plate_id"]
    assert accepted["submission_id"] == configuration["submission_id"]
    assert accepted["progress"]["job"] == accepted["id"]
    # The latest report when the answer was made: the first, waiting with nothing ahead, or,
    # since nothing else waits, already a later one (seam-front-slice.md, mismatch 1).
    first = accepted["progress"]
    assert first["state"] in ("queued", "running")
    assert first["state"] == "running" or first["ahead"] == 0

    stream = page.stream(accepted["id"]).wait_closed()
    assert stream.events[0] == ("version", {"version": front_server.version})
    reports = stream.reports
    sequences = [r["sequence"] for r in reports]
    assert sequences == sorted(set(sequences)), "each report once, in order"
    stages = [r["stage"] for r in reports if r.get("stage") in STAGES]
    assert [STAGES.index(s) for s in stages] == sorted(STAGES.index(s) for s in stages), \
        "a slice job never goes back to an earlier stage"
    done = stream.final
    assert done["state"] == "done" and done["job"] == accepted["id"]
    details = done["sliced_file"]
    assert details["slice"] == accepted["id"]
    assert re.fullmatch(r"Clamp_Plate_Inner_plus1-\d{8}-\d{4}\.gcode\.3mf", details["file"])
    summary = details["summary"]
    assert summary["file"] == details["file"]
    assert summary["instances"] == 3
    assert 0 < details["expires_in_s"] <= 7200

    # Asking again, and the sliced file's details, answer the same.
    assert page.ask(accepted["id"])["sliced_file"]["summary"] == summary
    asked = page.summary(accepted["id"])
    assert {k: v for k, v in asked.items() if k != "expires_in_s"} == \
        {k: v for k, v in details.items() if k != "expires_in_s"}

    body, headers = page.download(accepted["id"])
    assert headers["content-type"] == "application/octet-stream"
    assert headers["content-disposition"] == f'attachment; filename="{details["file"]}"'
    assert int(headers["content-length"]) == len(body) == details["size_bytes"]
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
    assert {"Metadata/plate_1.gcode", "Metadata/slice_info.config", "Metadata/plate_1.json"} <= names
    # Download's plain link, the group in the query, gives the same bytes.
    assert page.download(accepted["id"], by_link=True)[0] == body

    # The front server told the slice service it had stored the file, and the slice service
    # deleted its copy.
    deleted = [line for line in slice_service.lines("slice_job")
               if line.get("job") == accepted["id"] and line.get("state") == "file_deleted"]
    assert len(deleted) == 1
