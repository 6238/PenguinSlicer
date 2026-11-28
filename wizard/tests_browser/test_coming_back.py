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


def drawing_answered(response):
    return response.url.endswith("/api/reports/drawing")


def drive_layers(w):
    """Drives the layer preview's bar down and up on the fake clock, so that frames are drawn while
    the view moves."""
    w.run("window.__driven = false; wizard.previewStep.view().drive('layers', 6).then(() => { window.__driven = true; });")
    for _ in range(400):
        if w.run("return window.__driven;"):
            break
        w.page.clock.run_for(50)
    assert w.run("return window.__driven;")


def page_failed(response):
    request = response.request
    return request.url.endswith("/api/reports/failure") and '"page_failed"' in (request.post_data or "")


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


def test_a_page_loaded_before_a_deploy_draws_the_layer_preview_when_its_files_are_gone_from_the_server(page, front_server):
    # the page fetches every file of its own code when it loads and nothing later by name: the
    # preview's worker, started only when a sliced plate is shown, included
    w = Wizard(page, front_server)
    w.until("return true;")
    front_server.assets_gone = True
    from tests_browser.test_preview_step import PARTS
    from tests_browser.test_parts_step import choose
    w.page.check("#upload-units input[value=mm]")
    choose(w, ("Bracket.stl", (PARTS / "bracket.stl").read_bytes()), ("Spacer.stl", (PARTS / "spacer.stl").read_bytes()))
    w.until("return wizard.parts.rows().length === 2 && wizard.parts.rows().every((r) => !r.arriving && r.drawn);")
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout' && wizard.layout.model().instances.length === 2 "
            "&& wizard.layout.model().instances.every((i) => i.bounds) && wizard.layout.model().status.ok;")
    w.run("await wizard.layout.idle();")
    w.page.click("#stepbar li[data-step=preview]")
    w.until("return wizard.slicing.model().kind === 'done';")
    until_drawn(w)
    assert [p for p in front_server.requests if p.startswith("/assets/")] == [p for p in front_server.requests[:w.opening_requests] if p.startswith("/assets/")]
    assert w.page.locator(".preview-view-message").inner_text() == ""


def test_an_uncaught_error_and_an_unhandled_rejection_are_each_sent_as_page_failed(page, front_server):
    # on the real clock: Playwright's fake clock throws a timer's error to the test, not to the page
    w = Wizard(page, front_server, fake_clock=False)
    # each wait is for the front server's answer to the report, so the fake server holds its body
    with w.page.expect_response(page_failed):
        w.page.evaluate("() => { setTimeout(() => { throw new TypeError('a fault of the page made on purpose'); }, 0); }")
    with w.page.expect_response(page_failed):
        w.page.evaluate("() => { Promise.reject(new RangeError('a promise rejected on purpose')); }")
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
    with w.page.expect_response(lambda r: r.url.endswith("/api/reports/drawing")):
        w.page.click("#stepbar li[data-step=parts]")
    w.until("return wizard.store.get().step === 'parts';")
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


LOSE_LAYOUT = """
    const view = wizard.layoutStep.view(), ext = view.renderer.getContext().getExtension('WEBGL_lose_context');
    await new Promise((resolve) => { view.canvas.addEventListener('webglcontextlost', resolve, { once: true }); ext.loseContext(); });
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const before = view.frames();
    await new Promise((resolve) => { view.canvas.addEventListener('webglcontextrestored', resolve, { once: true }); ext.restoreContext(); });
    for (let i = 0; i < 200 && view.frames() === before; i += 1) await new Promise((r) => requestAnimationFrame(r));
    return view.frames() > before;
"""


def test_the_layout_view_draws_again_after_its_drawing_context_is_lost_twice_and_reports_each_loss(page, front_server):
    from tests_browser.test_layout_step import PIXELS
    w = open_layout(page, front_server, [spacer(), bracket()])
    w.run("wizard.layoutStep.view().viewPlate(true); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    for n in (1, 2):
        with page.expect_request(lambda r: r.url.endswith("/api/reports/failure")) as sent:
            assert w.run(LOSE_LAYOUT) is True, (n, "a frame drawn after the context came back")
        assert json.loads(sent.value.post_data)["what"] == "drawing_context_lost"
        assert json.loads(sent.value.post_data)["step"] == "layout"
        shares = w.run(PIXELS)
        assert 0.35 < shares["plate"] < 0.95, (n, shares)
        assert 0.002 < shares["coloured"] < 0.2, (n, shares)
    assert w.problems == []


def test_leaving_the_preview_step_after_the_layer_preview_drew_sends_its_drawing_summary(page, front_server):
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    until_drawn(w)
    drive_layers(w)
    with w.page.expect_response(drawing_answered):
        w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout';")
    [(summary, text)] = drawing_reports(front_server)
    assert summary["view"] == "preview"
    assert summary["first_layer_ms"] >= 0
    assert summary["sliced_file_bytes"] > 0 and summary["sliced_file_lines"] > 0
    assert summary["instances"] == 2
    assert "Spacer" not in text and "Bracket" not in text
    assert w.problems == []


AWAY_MS = 60_000


def test_a_second_use_of_the_layer_preview_is_timed_from_its_own_opening_and_measured_afresh(page, front_server):
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    until_drawn(w)
    drive_layers(w)
    with w.page.expect_response(drawing_answered):
        w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout';")
    # a minute away on the Layout step, then the same sliced plate's Preview step again
    w.page.clock.run_for(AWAY_MS)
    w.page.click("#stepbar li[data-step=preview]")
    w.until("return wizard.store.get().step === 'preview';")
    for _ in range(400):
        if w.run("return wizard.previewStep.view().summary().first_layer_ms !== null;"):
            break
        w.page.clock.run_for(50)
    # a use is sent only with frames drawn while the view moved
    drive_layers(w)
    with w.page.expect_response(drawing_answered):
        w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout';")
    [(first, _), (second, _)] = drawing_reports(front_server)
    assert first["view"] == second["view"] == "preview"
    assert 0 <= second["first_layer_ms"] < AWAY_MS, ("timed from the second opening", second["first_layer_ms"])
    assert w.problems == []


PAUSE_FRAMES = 120


def drag_across(w, dx, pause=False):
    """Drags the first instance `dx` millimetres; with `pause`, the mouse held still halfway for
    PAUSE_FRAMES of the browser's animation frames, so that the drag's longest interval between
    frames drawn while moving is that pause (an event counted, never a duration waited)."""
    w.run("wizard.layoutStep.view().topView(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    a = w.run("return wizard.layout.model().instances[0];")
    start = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [a["x"], a["y"]])
    end = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [a["x"] + dx, a["y"]])
    p, steps = w.page, 12
    p.mouse.move(start["x"], start["y"])
    p.mouse.down()
    for k in range(1, steps + 1):
        p.mouse.move(start["x"] + (end["x"] - start["x"]) * k / steps, start["y"] + (end["y"] - start["y"]) * k / steps)
        if pause and k == steps // 2:
            w.run("for (let i = 0; i < arg; i += 1) await new Promise((r) => requestAnimationFrame(r));", PAUSE_FRAMES)
    p.mouse.up()
    settle(w)


def test_a_second_use_of_the_layout_view_measures_its_figures_afresh(page, front_server):
    w = open_layout(page, front_server, [spacer(), bracket()])
    drag_across(w, 30, pause=True)
    with w.page.expect_response(drawing_answered):
        w.page.click("#stepbar li[data-step=parts]")
    w.until("return wizard.store.get().step === 'parts';")
    # the Layout step shown again, and one drag with no pause
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout';")
    settle(w)
    drag_across(w, -30)
    with w.page.expect_response(drawing_answered):
        w.page.click("#stepbar li[data-step=parts]")
    w.until("return wizard.store.get().step === 'parts';")
    [(first, _), (second, _)] = drawing_reports(front_server)
    assert first["view"] == second["view"] == "layout"
    # a figure carried over from the first use would put the first use's pause in the second's worst
    assert second["fps_worst"] > first["fps_worst"], (first, second)
    assert w.problems == []
