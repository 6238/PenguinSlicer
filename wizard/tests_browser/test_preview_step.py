"""The Preview step's submitting, following and failures in Chromium (wizard/README-details.md,
"The slicing card", "No room to wait", "When a slice fails"): the plate submitted on entering the
step, the slicing card drawn from the progress stream with no Cancel button, its times moving with
the page's clock, the placeholder once the plate is sliced and Next to the Send step, the amber
message of no room to wait, and a failure's red message with its buttons and Orca's sentence
under folded Details, each sentence as text, at 320 px with no sideways scroll.

Time in the page is Playwright's fake clock: the card's times move only when a test moves it. The
Layout step's view draws on animation frames, which the paused clock never runs; the plate's
instances join it all the same, from the worker, an event the test waits on."""
import json
from pathlib import Path

from tests_browser.conftest import Wizard
from tests_browser.fake_front_server import error_report, example, progress_event, stream, version_event
from tests_browser.test_parts_step import choose, no_sideways_scroll

PARTS = Path(__file__).resolve().parent.parent.parent / "contracts" / "examples" / "parts"
JOB = "3f9a1c2b"
EVENTS = f"/api/slices/{JOB}/events"


def running(**fields):
    return {"job": JOB, "state": "running", "stage": "generating_infill", "stage_label": "Generating infill",
            "fraction": 0.42, "elapsed_s": 31.5, "expected_s": 75, "sequence": 17, **fields}


def open_preview(page, server, width=320):
    """The wizard with the contract's bracket and spacer on the plate, laid out, on the Preview step."""
    w = Wizard(page, server, width=width)
    w.page.check("#upload-units input[value=mm]")
    choose(w, ("Bracket.stl", (PARTS / "bracket.stl").read_bytes()), ("Spacer.stl", (PARTS / "spacer.stl").read_bytes()))
    w.until("return wizard.parts.rows().length === 2 && wizard.parts.rows().every((r) => !r.arriving && r.drawn);")
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout' && wizard.layout.model().instances.length === 2 "
            "&& wizard.layout.model().instances.every((i) => i.bounds) && wizard.layout.model().status.ok;")
    w.run("await wizard.layout.idle();")
    w.page.click("#stepbar li[data-step=preview]")
    w.until("return wizard.store.get().step === 'preview' && wizard.slicing.model().kind !== 'idle';")
    return w


def submissions(server):
    return [json.loads(body) for (method, path, body) in server.bodies if method == "POST" and path == "/api/slices"]


def test_entering_the_step_submits_the_plate_and_the_card_waits_behind_others_with_no_cancel(page, front_server):
    front_server.script("GET", EVENTS, stream(version_event(front_server.version), hold=True))
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'card';")
    [sent] = submissions(front_server)
    assert [i["ref"] for i in sent["instances"]] == ["p1", "p2"]
    assert sent["parts"]["p1"]["name"] == "Bracket"
    assert w.page.locator("#slice-card").is_visible()
    assert w.page.locator("#slice-stage").inner_text() == "Waiting for the slicer: 2 slices ahead of yours."
    assert w.page.locator("#slice-pct").inner_text() == ""
    assert w.page.locator("#slice-expected").inner_text() == ""
    assert w.page.locator(".slice-times").inner_text().startswith("0:00 waited")
    assert w.page.locator("#slice-stages li").count() == 13
    assert w.page.locator("#slice-stages li.now").inner_text() == "Waiting for the slicer"
    assert w.page.locator(".slice-actions").inner_text() == "Slicing goes on if you step back; change the plate and it starts again."
    assert w.page.locator("#slice-card button").count() == 0                  # no Cancel slice
    w.page.clock.run_for(12_000)
    assert w.page.locator("#slice-elapsed").inner_text() == "0:12"
    assert w.page.locator("#btn-next").is_disabled()
    assert no_sideways_scroll(page) == []
    assert w.problems == []


def test_slicing_draws_the_ring_the_stage_the_times_and_the_current_stage(page, front_server):
    front_server.script("GET", EVENTS, stream(version_event(front_server.version), progress_event(running()), hold=True))
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'card' && wizard.slicing.model().card.pct === '42%';")
    w.page.clock.run_for(1000)
    assert w.page.locator("#slice-pct").inner_text() == "42%"
    assert w.page.locator("#slice-stage").inner_text() == "Generating infill"
    assert w.page.locator(".slice-times").inner_text() == "0:32 elapsed · about 0:42 left"
    assert w.page.locator("#slice-stages li.now").inner_text() == "Generating infill"
    assert w.page.locator("#slice-stages li.done").count() == 7
    width = w.page.evaluate("document.getElementById('slice-bar-fill').style.width")
    assert width == "42%"
    assert w.page.locator("#g-layers rect.on").count() == 2
    assert no_sideways_scroll(page) == []


def test_a_sliced_plate_shows_its_placeholder_and_next_goes_to_the_send_step(page, front_server):
    w = open_preview(page, front_server)          # the default stream ends with the example's done report
    w.until("return wizard.slicing.model().kind === 'done';")
    assert not w.page.locator("#slice-card").is_visible()
    assert w.page.locator("#preview-result").inner_text() == "The plate is sliced. Its print time, filament and layer preview will show here."
    assert not w.page.locator("#btn-next").is_disabled()
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'send';")
    assert not w.page.locator("#btn-do").is_disabled()


def test_no_room_to_wait_is_an_amber_message_with_slice_again(page, front_server):
    busy = error_report("slice.busy", message="The slicer is busy, try again in a minute.", remedy="Wait a minute and slice again.", retryable=True)
    front_server.script("POST", "/api/slices", (503, busy))
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'busy';")
    box = w.page.locator("#preview-errors .msg.warn")
    assert box.locator(".what").inner_text() == "The slicer is busy, try again in a minute."
    assert box.locator(".todo").inner_text() == "Wait a minute and slice again. Your plate is unchanged."
    assert box.locator("button").all_inner_texts() == ["Slice again"]
    box.locator("button").click()
    w.until("return wizard.slicing.model().kind === 'done';")
    assert len(submissions(front_server)) == 2
    assert no_sideways_scroll(page) == []


def test_a_failed_slice_is_a_red_message_with_its_buttons_and_orcas_sentence_under_details(page, front_server):
    error = {**example("error-report-orca-sentence.json"), "message": "<b>Tower #1</b> has nothing to print & more."}
    front_server.script("GET", EVENTS, stream(version_event(front_server.version), progress_event(running(state="failed", error=error, sequence=20))))
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'failed';")
    box = w.page.locator("#preview-errors .msg.error")
    assert box.locator(".what").inner_text() == "<b>Tower #1</b> has nothing to print & more."
    assert box.locator(".what b").count() == 0                                # text, not markup
    assert box.locator(".todo").inner_text() == error["remedy"]
    assert box.locator(".acts button").all_inner_texts() == ["Turn on Supports and slice again", "Back to Layout"]
    details = box.locator("details")
    assert details.get_attribute("open") is None                             # folded
    assert details.locator("summary").inner_text() == "Details"
    details.locator("summary").click()
    assert details.inner_text().endswith("Orca Slicer: Object can't be printed for empty layer between 9.9 and 11.34.")
    assert "orca code" not in box.inner_text()                               # the detail is never shown
    assert w.page.locator("#btn-next").is_disabled()
    box.locator(".acts button", has_text="Back to Layout").click()
    w.until("return wizard.store.get().step === 'layout';")
    assert no_sideways_scroll(page) == []


def test_rests_on_an_edge_offers_back_to_layout_only(page, front_server):
    error = example("error-report-rests-on-an-edge.json")
    front_server.script("GET", EVENTS, stream(version_event(front_server.version), progress_event(running(state="failed", error=error, sequence=20))))
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'failed';")
    box = w.page.locator("#preview-errors .msg.error")
    assert box.locator(".what").inner_text() == error["message"]
    assert box.locator(".acts button").all_inner_texts() == ["Back to Layout"]
    assert box.locator("details").count() == 0
