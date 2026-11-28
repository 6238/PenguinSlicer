"""Phase 2's "Done when" with the real Orca, in a browser: a small real part added from its STL
file in the wizard, laid out by the wizard, one setting changed in advanced mode, the plate
configuration the page made sliced by the pinned Orca through the slice service, the layer
preview drawing the real sliced file and the layer bar changing it, and the file downloaded
from the Send step. Under the real-Orca lock (`make -C together test-orca`)."""

import io
import json
import re
import zipfile

from joined.plates import PULLEY

#: The real Orca's slice of one small part takes seconds; this bounds it well clear of the
#: slice service's own time limit for a plate.
SLICE_BACKSTOP_MS = 300_000


def test_a_plate_the_page_made_is_sliced_by_the_real_orca_and_drawn_and_downloaded(wizard):
    # At 320 px advanced mode lists every section in one column.
    w = wizard(width=320, height=900)
    w.add_parts([PULLEY])
    w.next("settings")
    w.page.click("#btn-advanced:visible, #adv-effect-btn:visible")
    w.page.wait_for_selector("#advanced:not([hidden])")
    w.page.fill("#adv-sparse_infill_density", "35")
    w.page.locator("#adv-sparse_infill_density").dispatch_event("change")
    assert w.page.locator("#advanced .bad").count() == 0
    w.page.click("#adv-done")
    w.next("layout")
    w.layout_settled(1)
    w.next("preview")
    w.until("const m = wizard.slicing.model(); return (m.kind === 'done' && m.details) "
            "|| ['failed', 'busy', 'expired'].includes(m.kind);", what="the real Orca's slice",
            backstop_ms=SLICE_BACKSTOP_MS)
    details = w.sliced()
    summary = details["summary"]
    assert re.fullmatch(r"pulley-v3-\d{8}-\d{4}\.gcode\.3mf", details["file"]), details["file"]
    assert summary["instances"] == 1 and summary["layer_count"] > 1

    # The layer preview draws the real sliced file: its top layer first, the bar going down.
    first = w.layer_preview_drawn()
    assert first.startswith(f"{summary['layer_count']} / {summary['layer_count']} · "), first
    w.page.click("#btn-layer-down")
    assert w.readout().startswith(f"{summary['layer_count'] - 1} / {summary['layer_count']} · ")

    w.next("send")
    download, body = w.download()
    assert download.suggested_filename == details["file"]
    assert len(body) == details["size_bytes"]
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert archive.testzip() is None
        used = json.loads(archive.read("Metadata/project_settings.config"))
        objects = json.loads(archive.read("Metadata/plate_1.json"))["bbox_objects"]
    # The setting changed in advanced mode is the one the real Orca sliced with.
    assert used["sparse_infill_density"] == "35%"
    assert [o["name"] for o in objects] == ["pulley-v3 #1"]
    assert w.problems == []
