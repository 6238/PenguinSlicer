"""Scenarios of common use that neither half of a seam can show alone (docs/orchestration/
phase-2/seam-wizard-front.md, "Which scenarios the joined suite adds"): the real wizard in
Chromium over the real front server and the real slice service with the stand-in Orca.

- A slice that fails: the slice service's error report reaches the user's eyes unchanged, with
  the wizard's buttons for its code, and its one action slices the plate again.
- A plate changed while it slices and again after it is sliced: each later slice replaces the
  earlier one, and the page shows the newest result and downloads its sliced file.
- A page reloaded while its slice runs: it comes back to the same slice job, submits nothing
  again, and shows that slice job's result.
"""

import pytest

from joined.plates import CLAMP_PLATE, PULLEY

SLICING_MESH = "Slicing the parts into layers"


def slice_job_lines(slice_service, state):
    return [line for line in slice_service.lines("slice_job") if line["state"] == state]


def test_a_failed_slice_shows_the_slice_services_own_sentences_and_its_action_slices_again(
        wizard, slice_service):
    slice_service.orca_mode("empty_layers")
    w = wizard()
    w.to_preview([CLAMP_PLATE])
    w.until("return wizard.slicing.model().kind === 'failed';", what="the failed slice")

    [failed] = slice_job_lines(slice_service, "failed")
    own = slice_service.request("GET", f"/slices/{failed['job']}").json()["error"]
    assert own["code"] == "slice.empty_layers"
    box = w.page.locator("#preview-errors .msg.error")
    # The slice service's sentences, as it wrote them, and nothing of its detail.
    assert box.locator(".what").inner_text() == own["message"]
    assert box.locator(".todo").inner_text() == own["remedy"]
    assert own["detail"] not in box.inner_text()
    assert box.locator(".acts button").all_inner_texts() == ["Turn on Supports and slice again", "Back to Layout"]
    details = box.locator("details")
    if own.get("orca_sentence"):
        details.locator("summary").click()
        assert details.inner_text().endswith(f"Orca Slicer: {own['orca_sentence']}")
    else:
        assert details.count() == 0
    assert w.page.locator("#btn-next").is_disabled()

    # Its action: supports on, and the same plate sliced again, which the slice service accepts
    # with the setting in Orca's form.
    slice_service.orca_mode("ok")
    box.locator(".acts button", has_text="Turn on Supports and slice again").click()
    details_of_slice = w.sliced(other_than=failed["job"])
    [queued] = [line for line in slice_job_lines(slice_service, "queued")
                if line["job"] == details_of_slice["slice"]]
    assert queued["overrides"]["enable_support"] == "1"
    assert queued["plate_id"] == slice_job_lines(slice_service, "queued")[0]["plate_id"]
    assert w.problems == []


def move_first_instance(w, distance):
    """What a drag of the first instance on the Layout view ends in: the layout's own move, as
    the wizard's browser tests make it (its 3D view is tested in the wizard's own suite). The
    first of the four directions, `distance` mm away, where every instance still fits; gives
    the instance's new place."""
    moved = w.run("""
        const [a] = wizard.layout.model().instances;
        const from = { x: a.x, y: a.y };
        for (const [dx, dy] of [[arg, 0], [-arg, 0], [0, arg], [0, -arg]]) {
          wizard.layout.place([{ id: a.id, x: from.x + dx, y: from.y + dy }]);
          await wizard.layout.endDrag(); await wizard.layout.idle();
          if (wizard.layout.model().status.ok) return { x: from.x + dx, y: from.y + dy };
        }
        return null;""", distance)
    assert moved is not None, "no direction leaves the plate fitting"
    w.until("return wizard.store.get().sliced === false;", what="the moved plate, not sliced")
    return moved


@pytest.mark.keep_sliced
def test_a_plate_changed_while_slicing_and_after_replaces_its_slice_and_shows_the_newest(
        wizard, slice_service):
    slice_service.orca_mode("gate")
    w = wizard()
    w.to_preview([CLAMP_PLATE, PULLEY])
    w.card_stage(SLICING_MESH)
    [first] = slice_job_lines(slice_service, "running")

    # Changed while it slices: the slice goes on until the page submits the changed plate,
    # which replaces it.
    w.go("layout")
    move_first_instance(w, 5.0)
    slice_service.orca_mode("ok")
    w.go("preview")
    second = w.sliced()
    replaced = [line for line in slice_job_lines(slice_service, "cancelled") if line["job"] == first["job"]]
    assert len(replaced) == 1
    assert slice_service.request("GET", f"/slices/{first['job']}").json()["cancel_reason"] == "replaced"
    assert second["slice"] != first["job"]
    queued = {line["job"]: line for line in slice_job_lines(slice_service, "queued")}
    assert queued[second["slice"]]["plate_id"] == first["plate_id"]
    assert queued[second["slice"]]["submission_id"] != first["submission_id"]
    w.layer_preview_drawn()

    # Changed after it is sliced: the result goes, and entering the Preview step slices the
    # changed plate; the page shows the new result, and Download gives its sliced file.
    w.go("layout")
    move_first_instance(w, 10.0)
    w.go("preview")
    third = w.sliced(other_than=second["slice"])
    assert third["slice"] not in (first["job"], second["slice"])
    assert w.run("return wizard.slicing.model().slice;") == third["slice"]
    moved = {i["ref"]: i["x"] for i in queued[second["slice"]]["instances"]}
    queued = {line["job"]: line for line in slice_job_lines(slice_service, "queued")}
    assert {i["ref"]: i["x"] for i in queued[third["slice"]]["instances"]} != moved
    w.layer_preview_drawn()
    w.next("send")
    download, body = w.download()
    assert download.suggested_filename == third["file"]
    made = slice_service.sliced_files()
    assert len(made) == 2 and body == made[-1]
    assert w.problems == []


def test_a_page_reloaded_while_its_slice_runs_follows_the_same_slice_job_to_its_result(
        wizard, slice_service):
    slice_service.orca_mode("gate")
    w = wizard()
    w.to_preview([CLAMP_PLATE])
    w.card_stage(SLICING_MESH)
    [running] = slice_job_lines(slice_service, "running")

    # A refresh mid-slice: the page comes back to the Preview step following the slice job it
    # submitted, with no second submission, and shows that slice job's result when it ends.
    w.reload()
    assert w.step() == "preview"
    w.card_stage(SLICING_MESH)
    slice_service.release_orca()
    details = w.sliced()
    assert details["slice"] == running["job"]
    assert [line["job"] for line in slice_job_lines(slice_service, "queued")] == [running["job"]]
    w.layer_preview_drawn()
    assert w.problems == []
