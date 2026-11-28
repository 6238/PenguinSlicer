"""Each row of the architecture's table "The slice container restarts" that needs a page
(docs/architecture.md, "What a restart does"), in a browser: the real wizard in Chromium, the
slice service restarted at that row's moment, and what the user sees asserted on the page.

- A slice was waiting or running: a page that is open uploads its parts again and submits the
  same plate, unasked; a page that is closed does so when it is next opened; a slice still
  waiting when the slice service is asked to stop is ended early and its page submits it again
  by itself.
- A user submits a plate while the slice service is stopping: the slice is shown as waiting,
  with words saying the slicer is restarting, until the new slice service accepts it.
- A slice had finished: nothing changes.

The row of a print being sent or printing waits for phase 5's printer."""

from joined.plates import CLAMP_PLATE, PULLEY

SLICING_MESH = "Slicing the parts into layers"
RESTARTING = "The slicer is restarting; your plate will start when it is back."
RESTARTED = "The slicer restarted, so this slice began again."
BACK_SLICING = "Back where you were. Your plate was still slicing when you left; see below."


def jobs(slice_service, state):
    """The slice jobs every slice service process so far wrote a line of `state` for."""
    return [line["job"] for line in slice_service.lines("slice_job") if line["state"] == state]


def test_an_open_page_submits_again_by_itself_after_the_slice_container_dies_mid_slice(
        wizard, slice_service):
    slice_service.orca_mode("gate")
    w = wizard()
    w.to_preview([CLAMP_PLATE])
    w.card_stage(SLICING_MESH)
    [first] = jobs(slice_service, "running")

    slice_service.crash()
    slice_service.orca_mode("ok")
    slice_service.restart()
    # The front server's following ends, the page is told the slice job is unknown, and,
    # submitted less than two hours ago, it uploads its part again and submits the same plate.
    w.until("const m = wizard.slicing.model(); return m.kind === 'card' && m.card.conn?.text === arg;",
            arg=RESTARTED, what="the card saying the slicer restarted")
    details = w.sliced()
    assert details["slice"] != first
    # Sliced by the new slice service process, whose part store began empty: the page uploaded
    # the part again before it could be accepted.
    assert [line["job"] for line in slice_service.running.events("slice_job")
            if line["state"] == "done"] == [details["slice"]]
    w.layer_preview_drawn()
    assert w.problems == []


def test_a_page_closed_while_its_slice_is_cut_off_slices_it_again_when_next_opened(
        wizard, slice_service):
    slice_service.orca_mode("gate")
    w = wizard()
    w.to_preview([CLAMP_PLATE])
    w.card_stage(SLICING_MESH)
    w.close()

    slice_service.crash()
    slice_service.orca_mode("ok")
    slice_service.restart()
    # The tab is opened again within two hours: it takes up its plate, finds the slice job
    # unknown, and submits the plate again by itself, where the user left it.
    again = wizard()
    assert again.step() == "preview"
    details = again.sliced()
    assert jobs(slice_service, "done") == [details["slice"]]
    again.layer_preview_drawn()
    assert again.problems == []


def test_a_stop_ends_the_waiting_slice_which_waits_while_the_slicer_restarts_and_then_slices(
        wizard, slice_service):
    """Rows: a slice still waiting when the slice service is asked to stop is ended early and
    submitted again by its page; that submission, made while the slice service stops, shows the
    slice waiting with words saying the slicer is restarting, until the new slice service
    accepts it. The running slice is finished and stored before the slice service exits."""
    slice_service.orca_mode("gate")
    running = wizard()
    running.to_preview([CLAMP_PLATE])
    running.card_stage(SLICING_MESH)
    slice_service.orca_mode("ok")
    # A second tab has a plate of its own, which waits behind the first.
    waiting = wizard()
    waiting.to_preview([PULLEY])
    waiting.card_stage("Waiting for the slicer: 1 slice ahead of yours.")

    slice_service.stop()
    waiting.card_stage(RESTARTING)
    assert waiting.stage_line() == RESTARTING
    [ended] = [line for line in slice_service.lines("slice_job") if line["state"] == "cancelled"]

    slice_service.release_orca()
    assert running.sliced()["slice"] not in (None, ended["job"])
    assert slice_service.wait_stopped() == 0
    slice_service.restart()
    details = waiting.sliced()
    assert details["slice"] != ended["job"]
    assert details["summary"]["instances"] == 1
    waiting.layer_preview_drawn()
    assert running.problems == [] and waiting.problems == []


def test_a_finished_slice_is_unchanged_after_the_slice_container_restarts(wizard, slice_service):
    w = wizard()
    w.to_preview([CLAMP_PLATE])
    details = w.sliced()
    before = w.layer_preview_drawn()

    slice_service.crash()
    slice_service.restart()
    # Nothing changes for the user: the page shows the result, and after a refresh too, the
    # sliced file read from the state bucket for the layer preview and for Download.
    w.reload()
    assert w.step() == "preview"
    after = w.sliced()
    assert after.pop("expires_in_s") <= details.pop("expires_in_s")
    assert after == details
    assert w.layer_preview_drawn() == before
    w.next("send")
    _download, body = w.download()
    assert len(body) == details["size_bytes"]
    assert jobs(slice_service, "queued") == [details["slice"]]
    assert w.problems == []
