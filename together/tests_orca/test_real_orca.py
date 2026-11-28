"""One walk from upload to download with the real Orca: a small real plate, sliced by the
pinned Orca through the slice service and stored by the front server, and the sliced file
downloaded is a real one as contracts/sliced-file.md describes it."""

import io
import json
import re
import zipfile

from joined.plates import clamp_plate

#: The real Orca's slice of one small plate takes seconds; this bounds it well clear of the
#: slice service's own time limit for a plate.
SLICE_BACKSTOP_S = 300


def test_a_real_plate_from_upload_to_download(page):
    configuration = clamp_plate(page, x=170.0, y=160.0)
    accepted = page.submit(configuration)
    stream = page.stream(accepted["id"]).wait_closed(backstop_s=SLICE_BACKSTOP_S)
    done = stream.final
    assert done is not None and done["state"] == "done", stream.reports[-3:]
    stages = [r.get("stage") for r in stream.reports]
    assert "slicing_mesh" in stages or "generating_gcode" in stages, stages
    details = done["sliced_file"]
    summary = details["summary"]
    assert re.fullmatch(r"Clamp_Plate_Inner-\d{8}-\d{4}\.gcode\.3mf", details["file"])
    assert summary["instances"] == 1
    assert summary["layer_count"] and summary["layer_count"] > 1
    assert summary["print_time_s"] and summary["print_time_s"] > 0
    assert summary["filament_g"] and summary["filament_g"] > 0

    body, headers = page.download(accepted["id"])
    assert headers["content-disposition"] == f'attachment; filename="{details["file"]}"'
    assert len(body) == details["size_bytes"] <= 52_428_800
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert archive.testzip() is None, "every entry passes its checksum"
        gcode = archive.read("Metadata/plate_1.gcode").decode("utf-8", "replace")
        assert archive.read("Metadata/slice_info.config")
        objects = json.loads(archive.read("Metadata/plate_1.json"))["bbox_objects"]
    layers = re.search(r"^; total layer number: (\d+)$", gcode, re.MULTILINE)
    assert layers is not None and int(layers.group(1)) == summary["layer_count"]
    # Each instance named `<part name> #<n>`, the name reduced as the plate configuration's
    # contract says ("Instance").
    assert [o["name"] for o in objects] == ["Clamp_Plate_Inner #1"]
    # The real G-code, not the stand-in's: moves that extrude, at the plate's real heights.
    assert len(gcode) > 100_000 and re.search(r"^G1 .*E[0-9.]+", gcode, re.MULTILINE)
