"""The result of a sliced plate, a sliced plate that expires and the Send step in Chromium
(wizard/README-details.md, "The result", "A sliced plate that expires", "The Send step"): the print
time and filament, the quiet line and the warnings; the layer preview placed in the step with its
sliced file fetched for it, the readout and its two buttons, Reset view, the "?" and the colour key;
the expired message in place of the result and of Send at its moment; the Send step's card and its
one button, Download the sliced file, which saves the file by a plain link with a notification of
its true size. Every sentence is shown as text, at 320 px with no sideways scroll.

Time in the page is Playwright's fake clock, moved by the test; the layer preview draws on animation
frames, which run only as the test moves the clock, so a test that needs the view drawn moves it a
frame at a time until the page says the first layer is drawn, an event. The last test walks the
whole path on the page's real clock."""
import json

from tests_browser.conftest import Wizard
from tests_browser.fake_front_server import SLICED, error_report, example, progress_event, stream, version_event
from tests_browser.test_parts_step import no_sideways_scroll
from tests_browser.test_preview_step import PARTS, open_preview, running, submissions

JOB = "3f9a1c2b"
EVENTS = f"/api/slices/{JOB}/events"
SUMMARY = f"/api/slices/{JOB}/summary"
FILE = f"/api/slices/{JOB}/file"
DONE = example("wizard-front/slice-done.json")["progress"]
EXPIRED = "This plate's slice has expired."
EXPIRED_TODO = ("A sliced plate is kept for two hours after it is sliced or after its last print ends. "
                "Slice it again to print it; your parts, layout and settings are unchanged.")


def done(**details):
    return {**DONE, "sliced_file": {**DONE["sliced_file"], **details}}


def sliced_stream(server, **details):
    server.script("GET", EVENTS, stream(version_event(server.version), progress_event(done(**details))))


def until_drawn(w):
    """Moves the page's clock a frame at a time until the layer preview has drawn its first layer."""
    for _ in range(400):
        if w.run("return !document.getElementById('btn-layer-up').disabled;"):
            return
        w.page.clock.run_for(50)
    raise AssertionError("the layer preview never drew its first layer")


def test_the_result_shows_the_figures_and_the_layer_preview_with_its_readout_and_buttons(page, front_server):
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    # while the file is read the readout says so and is busy, so a screen reader is not told each percent
    w.until("return document.getElementById('layer-readout').textContent.startsWith('Reading the sliced file');")
    assert w.page.locator("#layer-readout").get_attribute("aria-busy") == "true"
    assert w.page.locator("#preview-stats .stat strong").all_inner_texts() == ["36 min", "16 g PETG"]
    assert [t.split("\n")[-1] for t in w.page.locator("#preview-stats .stat").all_inner_texts()] == ["Print time", "Filament"]
    assert w.page.locator("#preview-stats .stat-line").inner_text() == "3 instances · 200 layers · sliced in 0:52"
    assert not w.page.locator(".result-warnings").is_visible()
    until_drawn(w)
    assert [p for (m, p, _) in front_server.bodies if p.startswith(FILE)] == [FILE]
    assert w.page.locator("#layer-slider").is_visible()
    readout = w.page.locator("#layer-readout")
    assert readout.get_attribute("aria-busy") == "false"
    assert readout.inner_text().startswith("13 / 13 · ")
    assert readout.inner_text().endswith(" mm")
    w.page.click("#btn-layer-down")
    assert readout.inner_text().startswith("12 / 13 · ")
    assert w.page.locator("#layer-slider").get_attribute("aria-valuenow") == "12"
    w.page.click("#btn-layer-up")
    assert readout.inner_text().startswith("13 / 13 · ")
    w.page.focus("#layer-slider")
    w.page.keyboard.press("ArrowDown")
    assert readout.inner_text().startswith("12 / 13 · ")
    assert w.page.locator("#btn-preview-view").inner_text() == "Reset view"
    w.page.click("#btn-preview-view")
    # the colour key: closed until asked for, four rows, closed by Escape, by its icon and by a click
    # elsewhere; a press on it never reaches the view
    key = w.page.locator("#pv-key")
    assert not key.is_visible()
    w.page.click("#btn-key")
    assert key.is_visible()
    assert key.locator("li").all_inner_texts() == ["Walls", "Infill", "Top and bottom surfaces", "Supports and brim"]
    assert w.page.locator("#btn-key").get_attribute("aria-expanded") == "true"
    w.page.keyboard.press("Escape")
    assert not key.is_visible()
    w.page.click("#btn-key")
    assert key.is_visible()
    w.page.click("#btn-key")
    assert not key.is_visible()
    assert w.page.locator("#btn-key").get_attribute("aria-expanded") == "false"
    w.page.click("#btn-key")
    w.page.evaluate("""() => {
        window.viewPresses = 0;
        document.querySelector('#viewer-container canvas').addEventListener('pointerdown', () => { window.viewPresses += 1; });
    }""")
    box = key.bounding_box()
    w.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    w.page.mouse.down()
    w.page.mouse.move(box["x"] + box["width"] / 2 + 40, box["y"] + box["height"] / 2 + 30)
    w.page.mouse.up()
    assert key.is_visible()                                        # a press on the key keeps it open
    assert w.page.evaluate("window.viewPresses") == 0
    w.page.mouse.click(5, 5)
    assert not key.is_visible()
    # the "?": how to move the view
    w.page.click("#btn-preview-help")
    assert w.page.locator("#preview-help").inner_text() == ("Drag to turn, right-drag to pan, scroll to zoom; "
                                                           "drag the bar on the right to go through the layers.")
    w.page.mouse.click(5, 5)
    assert not w.page.locator("#preview-help").is_visible()
    # one line at 320 px
    assert w.page.evaluate("() => { const r = document.getElementById('layer-readout'); return r.getClientRects().length; }") == 1
    assert no_sideways_scroll(page) == []
    assert not w.page.locator("#btn-next").is_disabled()
    assert w.problems == []


def test_the_readout_stays_one_line_at_320_px_with_the_longest_figures(page, front_server):
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    until_drawn(w)
    for text in ("132 / 132 · 31.7 mm", "4250 / 4250 · 339.9 mm"):
        lines = w.page.evaluate("""t => {
            const r = document.getElementById('layer-readout');
            r.textContent = t;
            const row = document.querySelector('.layer-row');
            const range = document.createRange();
            range.selectNodeContents(r);
            const lines = new Set([...range.getClientRects()].map((b) => Math.round(b.top)));
            const right = Math.max(...[...row.children].filter((c) => c.offsetParent !== null).map((c) => c.getBoundingClientRect().right));
            return {lines: lines.size, beyond: right > row.getBoundingClientRect().right + 0.5};
        }""", text)
        assert lines == {"lines": 1, "beyond": False}, text
    assert no_sideways_scroll(page) == []


def test_coming_back_to_the_step_finds_the_preview_drawn_without_fetching_the_file_again(page, front_server):
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    until_drawn(w)
    w.page.click("#btn-back")
    w.until("return wizard.store.get().step === 'layout';")
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'preview';")
    assert not w.page.locator("#btn-layer-up").is_disabled()
    assert [p for (m, p, _) in front_server.bodies if p.startswith(FILE)] == [FILE]
    assert len(submissions(front_server)) == 1


def test_the_warnings_show_in_amber_as_text(page, front_server):
    summary = {**DONE["sliced_file"]["summary"], "warnings": ["<i>Floating</i> regions on Bracket #2"],
               "part_warnings": [{"code": "slice.part_not_watertight", "message": "Spacer is not watertight.", "where": {"part": "p2"}, "detail": "never shown"}]}
    sliced_stream(front_server, summary=summary)
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    box = w.page.locator(".result-warnings")
    assert box.locator("li").all_inner_texts() == ["<i>Floating</i> regions on Bracket #2", "Spacer is not watertight."]
    assert box.locator("i").count() == 0
    colour = w.page.evaluate("getComputedStyle(document.querySelector('.result-warnings')).color")
    assert colour == "rgb(154, 103, 0)"                       # the panel's amber, --warn
    assert "never shown" not in w.page.locator("#preview-result").inner_text()


def test_a_sliced_file_the_preview_cannot_read_is_an_amber_message_in_place_of_the_view(page, front_server):
    front_server.script("GET", FILE, (200, b"not a zip archive"))
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    for _ in range(200):
        if w.run("return Boolean(document.querySelector('.preview-view-message .msg'));"):
            break
        w.page.clock.run_for(50)
    box = w.page.locator(".preview-view-message .msg.warn")
    assert box.locator(".what").inner_text() == "PenguinSlicer could not read this plate's sliced file to draw its preview."
    assert box.locator("button").all_inner_texts() == ["Slice again"]
    assert not w.page.locator(".preview-view-box").is_visible()
    assert w.page.locator("#layer-readout").get_attribute("aria-busy") == "false"
    assert w.page.locator("#preview-stats .stat strong").all_inner_texts() == ["36 min", "16 g PETG"]
    assert not w.page.locator("#btn-next").is_disabled()


def test_the_expired_message_replaces_the_result_at_its_moment_and_slice_again_slices(page, front_server):
    sliced_stream(front_server, expires_in_s=30)
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'done';")
    w.page.clock.run_for(29_000)
    assert w.page.locator("#preview-result").is_visible()
    w.page.clock.run_for(1_000)
    w.until("return wizard.slicing.model().kind === 'expired';")
    assert not w.page.locator("#preview-result").is_visible()
    box = w.page.locator("#preview-errors .msg.info")
    assert box.locator(".what").inner_text() == EXPIRED
    assert box.locator(".todo").inner_text() == EXPIRED_TODO
    assert box.locator("button").all_inner_texts() == ["Slice again"]
    assert w.page.locator("#btn-next").is_disabled()
    assert len(submissions(front_server)) == 1
    box.locator("button").click()
    w.until("return wizard.slicing.model().kind === 'done';")
    sent = submissions(front_server)
    assert len(sent) == 2
    assert sent[0]["submission_id"] != sent[1]["submission_id"]
    assert no_sideways_scroll(page) == []


def open_send(page, server, **details):
    sliced_stream(server, **details)
    w = open_preview(page, server)
    w.until("return wizard.slicing.model().kind === 'done';")
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'send';")
    return w


def test_the_send_step_has_the_card_and_one_button_and_nothing_that_names_a_printer(page, front_server):
    w = open_send(page, front_server)
    card = w.page.locator("#send-summary .card")
    assert card.locator("dt").all_inner_texts() == ["Instances", "Print time", "Filament"]
    dd = card.locator("dd")
    assert dd.nth(0).locator(".big").inner_text() == "2 on one plate"
    assert dd.nth(0).locator("li").all_inner_texts() == ["Bracket", "Spacer"]
    assert dd.nth(1).inner_text() == "36 min"
    assert dd.nth(2).inner_text() == "16 g of PETG"
    assert w.page.locator("#final-action button").all_inner_texts() == ["Download the sliced file"]
    assert not w.page.locator("#btn-do").is_disabled()
    assert w.page.locator("#btn-do-caret").count() == 0
    assert w.page.locator(".clear-plate").count() == 0
    text = w.page.locator("#wizard").inner_text().lower()
    for word in ("printer", "pair", "send to"):
        assert word not in text
    assert no_sideways_scroll(page) == []


def test_download_saves_the_file_by_a_link_with_the_group_and_leaves_a_notification_of_its_true_size(page, front_server):
    w = open_send(page, front_server)
    group = w.run("return wizard.store.get().group;")
    with w.page.expect_download() as caught:
        w.page.click("#btn-do")
    download = caught.value
    assert download.suggested_filename == "Bracket_plus1-20261009-1432.gcode.3mf"
    assert download.url.endswith(f"{FILE}?group={group}")
    with open(download.path(), "rb") as saved:
        assert saved.read() == SLICED.read_bytes()
    asked = [p for (m, p, _) in front_server.bodies if p.startswith(SUMMARY)]
    assert asked == [SUMMARY]
    assert w.page.locator("#notices .notice .n-what").all_inner_texts() == ["Downloaded the sliced file of 2 instances (1.8 MB)."]


def test_a_download_refused_as_expired_shows_the_front_servers_sentence_in_place_of_the_button(page, front_server):
    w = open_send(page, front_server)
    gone = error_report("front.sliced_file_expired")
    front_server.script("GET", SUMMARY, (410, gone))
    w.page.click("#btn-do")
    w.until("return wizard.slicing.model().kind === 'expired';")
    box = w.page.locator("#send-printer .msg.info")
    assert box.locator(".what").inner_text() == gone["message"]
    assert box.locator("button").all_inner_texts() == ["Slice again"]
    assert not w.page.locator("#final-action").is_visible()
    assert w.page.locator("#send-summary .card").is_visible()
    assert "never shown" not in w.page.locator("#wizard").inner_text()
    box.locator("button").click()
    w.until("return wizard.store.get().step === 'preview' && wizard.slicing.model().kind === 'done';")
    assert len(submissions(front_server)) == 2


def test_on_the_send_step_the_expired_message_takes_the_place_of_send_at_its_moment(page, front_server):
    w = open_send(page, front_server, expires_in_s=60)
    w.page.clock.run_for(59_000)
    assert w.page.locator("#final-action").is_visible()
    w.page.clock.run_for(1_000)
    w.until("return wizard.slicing.model().kind === 'expired';")
    assert w.page.locator("#send-printer .msg.info .what").inner_text() == EXPIRED
    assert not w.page.locator("#final-action").is_visible()


def test_a_download_refused_otherwise_shows_its_sentences_and_keeps_the_button(page, front_server):
    w = open_send(page, front_server)
    front_server.script("GET", SUMMARY, (404, error_report("front.slice_unknown")))
    w.page.click("#btn-do")
    w.until("return Boolean(document.querySelector('#send-errors .msg.error'));")
    assert w.page.locator("#send-errors .what").inner_text() == error_report("front.slice_unknown")["message"]
    assert w.page.locator("#final-action").is_visible()


def downloads_of(w):
    """The downloads the browser starts, as they are told to the test."""
    caught = []
    w.page.on("download", lambda d: caught.append(d))
    return caught


def test_a_download_answered_without_the_details_is_a_red_message_and_nothing_is_saved(page, front_server):
    w = open_send(page, front_server)
    caught = downloads_of(w)
    front_server.script("GET", SUMMARY, (200, {"sliced_file": {"summary": {}}}))
    w.page.click("#btn-do")
    w.until("return Boolean(document.querySelector('#send-errors .msg.error'));")
    assert w.page.locator("#send-errors .what").inner_text() == "The server gave an answer this page cannot read."
    assert w.page.locator("#send-errors .todo").inner_text() == "Reload the page to try again."
    assert w.page.locator("#final-action").is_visible()
    assert w.page.locator("#notices .notice").count() == 0
    assert [p for (m, p, _) in front_server.bodies if p.startswith(FILE)] == [FILE]      # the preview's fetch only
    assert caught == []
    assert w.problems == []


def test_a_second_press_while_a_download_is_under_way_does_nothing(page, front_server):
    w = open_send(page, front_server)
    caught = downloads_of(w)
    held = []
    w.page.route(f"**{SUMMARY}", lambda route: held.append(route))
    w.page.click("#btn-do")
    w.until("return true;")
    w.page.click("#btn-do")
    for _ in range(100):                     # each ask is a round trip, in which the routes are told
        if held:
            break
        w.run("return true;")
    assert len(held) == 1
    # the button looks busy while the details are on their way, and no longer once they are in
    assert w.page.locator("#btn-do").get_attribute("aria-busy") == "true"
    assert w.run("return getComputedStyle(document.querySelector('#btn-do')).cursor;") == "progress"
    with w.page.expect_download():
        held[0].continue_()
    w.page.wait_for_selector("#notices .notice")
    assert w.page.locator("#btn-do").get_attribute("aria-busy") == "false"
    for _ in range(20):                      # a second request would be told in these round trips
        w.run("return true;")
    assert len(held) == 1
    assert [p for (m, p, _) in front_server.bodies if p.startswith(SUMMARY)] == [SUMMARY]
    assert len(caught) == 1
    assert w.page.locator("#notices .notice").count() == 1


def test_a_refused_downloads_message_goes_once_a_changed_plate_is_sliced(page, front_server):
    w = open_send(page, front_server)
    front_server.script("GET", SUMMARY, (404, error_report("front.slice_unknown")))
    w.page.click("#btn-do")
    w.until("return Boolean(document.querySelector('#send-errors .msg.error'));")
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout';")
    w.run("const [a] = wizard.layout.model().instances; wizard.layout.place([{ id: a.id, x: a.x + 5, y: a.y }]); await wizard.layout.endDrag(); await wizard.layout.idle();")
    w.until("return wizard.store.get().sliced === false;")
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'preview' && wizard.slicing.model().kind === 'done';")
    assert len(submissions(front_server)) == 2
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'send';")
    assert w.page.locator("#send-errors .msg").count() == 0
    assert w.page.locator("#final-action").is_visible()


def test_a_slice_that_ends_on_the_layout_step_draws_no_preview_until_the_step_is_in_sight(page, front_server):
    first = stream(version_event(front_server.version), progress_event(running()), hold=True)
    front_server.script("GET", EVENTS, first, stream(version_event(front_server.version), progress_event(done())))
    w = open_preview(page, front_server)
    w.until("return wizard.slicing.model().kind === 'card';")
    w.page.click("#btn-back")
    w.until("return wizard.store.get().step === 'layout';")
    first.release()
    for _ in range(200):                     # the page reopens the stream that closed, on its clock
        if w.run("return wizard.slicing.model().kind === 'done';"):
            break
        w.page.clock.run_for(500)
    assert w.run("return wizard.slicing.model().kind === 'done';")
    assert w.run("return wizard.previewStep.view() === null;")
    assert w.page.locator("#layer-readout").inner_text() == ""
    assert [p for (m, p, _) in front_server.bodies if p.startswith(FILE)] == []
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'preview';")
    until_drawn(w)
    assert [p for (m, p, _) in front_server.bodies if p.startswith(FILE)] == [FILE]
    assert len(submissions(front_server)) == 1


def test_the_whole_path_on_the_real_clock_parts_layout_slice_preview_and_download(page, front_server):
    """A user adds parts, lays them out, slices, inspects the preview and downloads, as phase 2's
    Done when says, against the fake front server on the page's own clock."""
    w = Wizard(page, front_server, width=480, height=900, fake_clock=False)
    w.page.check("#upload-units input[value=mm]")
    w.page.set_input_files("#f-upload", [{"name": n, "mimeType": "application/octet-stream", "buffer": (PARTS / n.lower()).read_bytes()}
                                         for n in ("Bracket.stl", "Spacer.stl")])
    w.until("return wizard.parts.rows().length === 2 && wizard.parts.rows().every((r) => !r.arriving && r.drawn);")
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'settings';")
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'layout' && wizard.layout.model().status.ok && wizard.layout.model().instances.length === 2;")
    w.run("await wizard.layout.idle();")
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'preview';")
    w.page.wait_for_function("() => !document.getElementById('btn-layer-up').disabled")
    assert w.page.locator("#layer-readout").inner_text().startswith("13 / 13")
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'send';")
    with w.page.expect_download() as caught:
        w.page.click("#btn-do")
    assert caught.value.suggested_filename.endswith(".gcode.3mf")
    w.page.wait_for_selector("#notices .notice")
    [sent] = submissions(front_server)
    assert sorted(p["name"] for p in sent["parts"].values()) == ["Bracket", "Spacer"]
    assert json.loads(json.dumps(sent))["instances"]
    assert w.problems == []
