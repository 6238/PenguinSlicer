"""Coming back, reloading for a new version and the page's reports about itself, in Chromium
(wizard/README-details.md, "When a user comes back", "Reloading for a new version", "What the
wizard reports about itself"): a refresh of a tab whose plate was sliced opens on the Preview step
with "Back where you were"; a page that sees a newer version reloads itself at a move between
steps, on the step it moved to, and says nothing; an uncaught error and a rejected promise nobody
handled are each sent as a page_failed report; leaving the Layout step after a drag, and the
Preview step after the layer preview drew, each sends one drawing summary with no part name.

The Layout view's test is on the real clock, since the view draws on the browser's animation
frames; every wait is for an event, never a duration."""
import json

from tests_browser.conftest import Wizard
from tests_browser.test_layout_step import bracket, drag, open_layout, settle, spacer
from tests_browser.test_preview_step import open_preview
from tests_browser.test_result_send import until_drawn

NEWER = "20261128T090000Z-ef45ab6"
BACK_SLICED = "Back where you were. Your plate was sliced and ready to send when you left."


def failure_reports(server):
    return [json.loads(body) for (method, path, body) in server.bodies if path == "/api/reports/failure"]


def drawing_reports(server):
    return [(json.loads(body), body.decode("utf-8")) for (method, path, body) in server.bodies if path == "/api/reports/drawing"]


def notices(w):
    return w.page.locator("#notices .n-what").all_inner_texts()


def test_a_refresh_of_a_sliced_plate_opens_the_preview_step_with_back_where_you_were(page, front_server):
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout';")
    asked = len([p for p in front_server.requests if p == "/api/slices/3f9a1c2b"])
    w.reload()
    w.until("return wizard.store.get().step === 'preview' && wizard.slicing.model().kind === 'done';")
    assert len([p for p in front_server.requests if p == "/api/slices/3f9a1c2b"]) == asked + 1
    w.until("return document.querySelectorAll('#notices .n-what').length === 1;")
    assert notices(w) == [BACK_SLICED]
    assert len([b for (m, p, b) in front_server.bodies if m == "POST" and p == "/api/slices"]) == 1
    assert w.problems == []


def test_a_newer_version_reloads_the_page_at_a_move_between_steps_on_that_step_saying_nothing(page, front_server):
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    # a deploy: the front server answers in a newer version, and serves the newer page
    front_server.version = NEWER
    front_server.page = front_server.page.replace("20261127T221405Z-0000000", NEWER)
    w.run("await wizard.api.get('/api/me');")
    assert w.run("return wizard.reloader.due();") is True
    with w.page.expect_navigation():
        w.page.click("#stepbar li[data-step=layout]")
    w.wait_opened()
    assert w.run("return wizard.version;") == NEWER
    w.until("return wizard.store.get().step === 'layout' && wizard.slicing.model().kind === 'done';")
    assert notices(w) == []
    assert w.run("return sessionStorage.getItem('penguinslicer.self_reload');") == ""
    assert w.run("return wizard.reloader.due();") is False
    assert w.problems == []


def test_an_uncaught_error_and_an_unhandled_rejection_are_each_sent_as_page_failed(page, front_server):
    # on the real clock: Playwright's fake clock throws a timer's error to the test, not to the page
    w = Wizard(page, front_server, fake_clock=False)
    w.page.evaluate("() => { window.__thrown = new Promise((r) => { setTimeout(() => { r(); throw new TypeError('a fault of the page made on purpose'); }, 0); }); }")
    w.run("await window.__thrown; await new Promise((r) => setTimeout(r, 0));")
    w.page.evaluate("() => { Promise.reject(new RangeError('a promise rejected on purpose')); }")
    for _ in range(500):
        if len([r for r in failure_reports(front_server) if r["what"] == "page_failed"]) >= 2:
            break
        w.run("return true;")
    sent = [r for r in failure_reports(front_server) if r["what"] == "page_failed"]
    assert [r["detail"].split("\n")[0] for r in sent] == [
        "uncaught: TypeError: a fault of the page made on purpose",
        "unhandled rejection: RangeError: a promise rejected on purpose"]
    assert all(r["step"] == "parts" for r in sent)


def test_leaving_the_layout_step_after_a_drag_sends_one_drawing_summary_with_no_part_name(page, front_server):
    w = open_layout(page, front_server, [spacer(), bracket()])
    w.run("wizard.layoutStep.view().topView(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    a = w.run("return wizard.layout.model().instances[0];")
    start = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [a["x"], a["y"]])
    end = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [a["x"] + 30, a["y"]])
    drag(w, start, end, steps=12)
    settle(w)
    w.page.click("#stepbar li[data-step=parts]")
    w.until("return wizard.store.get().step === 'parts';")
    for _ in range(500):
        if drawing_reports(front_server):
            break
        w.run("return true;")
    [(summary, text)] = drawing_reports(front_server)
    assert summary["view"] == "layout"
    assert summary["instances"] == 2
    assert summary["fps_typical"] > 0 and summary["fps_worst"] > 0
    assert summary["longest_hold_ms"] >= 0
    assert summary["drawing"] in ("software", "graphics_card")
    assert summary["panel_width_px"] > 0
    assert summary["in_onshape"] is False
    assert "first_layer_ms" not in summary
    assert "Spacer" not in text and "Bracket" not in text
    assert w.problems == []


def test_leaving_the_preview_step_after_the_layer_preview_drew_sends_its_drawing_summary(page, front_server):
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    until_drawn(w)
    # the layer bar driven down and up, so that frames are drawn while the view moves
    w.run("window.__driven = false; wizard.previewStep.view().drive('layers', 6).then(() => { window.__driven = true; });")
    for _ in range(400):
        if w.run("return window.__driven;"):
            break
        w.page.clock.run_for(50)
    assert w.run("return window.__driven;")
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout';")
    [(summary, text)] = drawing_reports(front_server)
    assert summary["view"] == "preview"
    assert summary["first_layer_ms"] >= 0
    assert summary["sliced_file_bytes"] > 0 and summary["sliced_file_lines"] > 0
    assert summary["instances"] == 2
    assert "Spacer" not in text and "Bracket" not in text
    assert w.problems == []
