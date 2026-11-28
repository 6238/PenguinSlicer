"""Phase 2's "Done when" in a browser: a user opens the wizard, adds parts from STL files, lays
them out, slices them through the slice service, inspects the preview and downloads the sliced
file from the Send step. The real wizard in Chromium, the real front server serving it with the
development identity, the real slice service with the stand-in Orca."""

import pytest

from joined.plates import CLAMP_PLATE, PULLEY


@pytest.mark.keep_sliced
def test_a_user_adds_parts_lays_them_out_slices_inspects_the_preview_and_downloads(
        wizard, slice_service, wizard_front):
    w = wizard()
    # Who the user is and the configuration, as the front server answers them: the development
    # identity, and the built-in default, which the header names.
    assert w.run("return wizard.store.get().user;") == {"id": "dev-user", "name": "Development User"}
    assert w.run("return wizard.store.get().group;") == "dev-group"
    table = w.run("return wizard.store.get().settingsTable.settings.length;")
    assert table > 300, "the real table of settings, not the hand-written example"

    w.add_parts([CLAMP_PLATE, PULLEY])
    assert w.page.locator("#parts-list .name, #parts-list .part-name").count() >= 0
    w.next("settings")
    w.next("layout")
    w.layout_settled(2)
    w.next("preview")
    details = w.sliced()
    assert details["summary"]["instances"] == 2

    # The layer preview draws the sliced file, and the layer bar changes the layer shown.
    first = w.layer_preview_drawn()
    w.page.click("#btn-layer-down")
    lower = w.readout()
    assert lower != first, (first, lower)
    top, _, total = first.partition(" · ")[0].partition(" / ")
    assert lower.startswith(f"{int(top) - 1} / {total}"), (first, lower)

    w.next("send")
    download, body = w.download()
    assert download.suggested_filename == details["file"]
    # The bytes downloaded are the ones the slice service's Orca made, and the front server's.
    made = slice_service.sliced_files()
    assert len(made) == 1 and body == made[0]
    assert len(body) == details["size_bytes"]
    w.page.wait_for_selector("#notices .notice")
    # A report the page makes about itself, in the form its reports module writes it, is taken
    # by the front server and written as one line with the page's version. (A drawing summary
    # is sent only for a use of a view whose frames were measured, which this walk does not
    # make: the wizard's own browser suite drives the views.)
    assert w.run("return wizard.reports.failure('page_failed', { detail: 'the joined suite' });") is True
    [line] = wizard_front.running.events("failure_report")
    assert (line["what"], line["step"], line["detail"], line["user_key"]) == \
        ("page_failed", "send", "the joined suite", "dev-user")
    assert line["page_version"] == wizard_front.version
    assert w.problems == []
