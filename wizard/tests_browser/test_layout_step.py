"""The Layout step in Chromium (wizard/README-details.md, "The Layout step"), its 3D view tested
coarsely as the details file asks: it draws, it fills roughly the expected part of the view, a drag
moves an instance, a problem shows its message, the rotation handle stays on its circle and Shift
snaps, a patch lays an instance down, the four keys do what the table says and Delete, Ctrl+D,
Ctrl+Z and Ctrl+Y do nothing, and the step works at 320 px with no sideways scroll at each width.
Chromium draws the view in software on a machine without a graphics card.

The page is left on the real clock here (`fake_clock=False`), since the view draws on the
browser's animation frames, which a paused fake clock never runs; every wait is for an event (the
page asked again until a state is reached), never a duration."""
from pathlib import Path

import pytest

from tests_browser.conftest import Wizard
from tests_browser.test_parts_step import choose, no_sideways_scroll

PARTS = Path(__file__).resolve().parent.parent.parent / "contracts" / "examples" / "parts"
LAYOUT = "section.step[data-step=layout]"
MAIN_THREAD_HOLD_MS = 250


def open_layout(page, server, files, width=320, quantities=None):
    w = Wizard(page, server, width=width, fake_clock=False)
    w.page.check("#upload-units input[value=mm]")       # the contract's parts are in millimetres
    choose(w, *files)
    w.until(f"return wizard.parts.rows().length === {len(files)} && wizard.parts.rows().every((r) => !r.arriving && r.drawn);")
    for key_index, qty in (quantities or {}).items():
        w.run("wizard.parts.setQuantity(wizard.parts.rows()[arg[0]].key, arg[1]);", [key_index, qty])
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.store.get().step === 'layout' && wizard.layout.model().instances.length > 0 "
            "&& wizard.layout.model().instances.every((i) => i.bounds) && wizard.layoutStep.view() && wizard.layoutStep.view().frames() > 0;")
    settle(w)
    return w


def settle(w):
    """Until the layout has nothing in hand and the view has drawn what it shows."""
    w.until("return (async () => { await wizard.layout.idle(); return true; })();")
    w.run("await wizard.layout.idle(); const v = wizard.layoutStep.view(); v.invalidate(); "
          "await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")


def spacer():
    return ("Spacer.stl", (PARTS / "spacer.stl").read_bytes())


def bracket():
    return ("Bracket.stl", (PARTS / "bracket.stl").read_bytes())


PIXELS = """
    const c = wizard.layoutStep.view().canvas;
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    const w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
    const px = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
    let background = 0, plate = 0, coloured = 0;
    for (let i = 0; i < px.length; i += 4) {
        const r = px[i], g = px[i + 1], b = px[i + 2];
        if (Math.abs(r - 0xf2) < 4 && Math.abs(g - 0xf4) < 4 && Math.abs(b - 0xf7) < 4) background++;
        else if (Math.max(r, g, b) - Math.min(r, g, b) > 24) coloured++;
        else plate++;
    }
    const n = w * h;
    return { background: background / n, plate: plate / n, coloured: coloured / n, w, h };
"""


def test_the_view_draws_the_plate_and_its_instances_filling_roughly_the_expected_part_of_it(page, front_server):
    w = open_layout(page, front_server, [spacer(), bracket()])
    w.run("wizard.layoutStep.view().viewPlate(true); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    shares = w.run(PIXELS)
    # seen from above, the plate fills most of the view and the two instances a small part of it
    assert 0.35 < shares["plate"] < 0.95, shares
    assert 0.002 < shares["coloured"] < 0.2, shares
    assert w.page.locator("#layout-alert").inner_text() == "✓ All 2 instances fit the plate."
    assert w.page.locator("#layout-info").inner_text() == "Bambu Lab H2S 0.6 nozzle: plate 340 × 320 mm, up to 340 mm tall, 5 mm apart"
    assert w.page.locator("#layout-selection").inner_text() == "2 instances on the plate."
    assert w.problems == []


def drag(w, start, end, steps=8, button="left", shift=False):
    p = w.page
    p.mouse.move(start["x"], start["y"])
    if shift:
        p.keyboard.down("Shift")
    p.mouse.down(button=button)
    for k in range(1, steps + 1):
        p.mouse.move(start["x"] + (end["x"] - start["x"]) * k / steps, start["y"] + (end["y"] - start["y"]) * k / steps)
    p.mouse.up(button=button)
    if shift:
        p.keyboard.up("Shift")


def test_a_drag_moves_an_instance_and_a_problem_shows_its_message(page, front_server):
    w = open_layout(page, front_server, [spacer()], quantities={0: 2})
    w.run("wizard.layoutStep.view().topView(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    a, b = w.run("return wizard.layout.model().instances.map((i) => ({ id: i.id, x: i.x, y: i.y }));")
    end = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [a["x"] + 20, a["y"] + 5])
    there = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [b["x"], b["y"]])
    # from the instance's middle on the plate, so the move on the plate is the pointer's
    drag(w, there, end)
    settle(w)
    moved = w.run("return wizard.layout.model().instances[1];")
    assert abs(moved["x"] - (a["x"] + 20)) < 3 and abs(moved["y"] - (a["y"] + 5)) < 3, (moved, a)
    errors = w.page.locator("#layout-errors .msg.error .what")
    assert errors.count() == 1
    assert errors.inner_text() == "Spacer #1 and Spacer #2 are 0 mm apart; instances need 5 mm between them with supports off."
    assert w.page.locator("#layout-alert").get_attribute("class") == "layout-alert"
    assert w.page.locator("#layout-alert .first").inner_text() == errors.inner_text()
    assert w.page.locator("#btn-next").is_disabled()
    assert w.page.locator("#layout-errors .fix-first").inner_text() == "Fix this before Next:"
    # its button fixes it
    w.page.click("#layout-errors .msg.error .acts .btn")
    settle(w)
    assert w.page.locator("#layout-errors .msg.error").count() == 0
    assert w.page.locator("#layout-errors .msg.ok .what").inner_text() == "Arranged 2 instances."
    assert not w.page.locator("#btn-next").is_disabled()
    assert w.problems == []


def test_a_click_selects_an_instance_and_the_selection_line_names_it(page, front_server):
    w = open_layout(page, front_server, [spacer()])
    w.run("wizard.layoutStep.view().topView(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    (a,) = w.run("return wizard.layout.model().instances.map((i) => ({ id: i.id, x: i.x, y: i.y }));")
    at = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [a["x"], a["y"]])
    w.page.mouse.click(at["x"], at["y"])
    w.until("return wizard.layout.model().selected.length === 1;")
    assert w.page.locator("#layout-selection").inner_text() == "Spacer #1 40 × 30 mm, 10 mm tall"
    assert w.page.locator("#layout-orient").is_hidden()
    # a click on empty plate clears it
    empty = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [a["x"], a["y"] + 40])
    w.page.mouse.click(empty["x"], empty["y"])
    w.until("return wizard.layout.model().selected.length === 0;")


def test_the_rotation_handle_stays_on_its_circle_through_a_drag_and_shift_snaps_to_45_degrees(page, front_server):
    w = open_layout(page, front_server, [bracket()])
    w.run("wizard.layoutStep.view().topView(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    (a,) = w.run("return wizard.layout.model().instances.map((i) => ({ id: i.id }));")
    w.run("wizard.layout.select(arg, 'only');", a["id"])
    settle(w)
    h = w.run("return wizard.layoutStep.view().handleAt();")
    assert h is not None
    circle0 = w.run("return wizard.layoutStep.view().handleCircle();")
    centre = w.run("const b = wizard.layout.model().instances[0].bounds; return wizard.layoutStep.view().plateAt((b[0] + b[2]) / 2, (b[1] + b[3]) / 2);")
    p = w.page
    p.mouse.move(h["x"], h["y"])
    assert w.run("return wizard.layoutStep.view().pointerLine();") == "Drag to turn · Shift: 45° steps"
    p.mouse.down()
    radii = []
    import math
    r = math.hypot(h["x"] - centre["x"], h["y"] - centre["y"])
    a0 = math.atan2(h["y"] - centre["y"], h["x"] - centre["x"])
    for k in range(1, 9):
        ang = a0 - math.radians(5 * k)
        p.mouse.move(centre["x"] + r * math.cos(ang), centre["y"] + r * math.sin(ang))
        w.run("await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
        radii.append(w.run("return wizard.layoutStep.view().handleCircle();")["r"])
    readout = p.locator("#layout-view .turn-readout").inner_text()
    assert readout.startswith("↺ "), readout
    assert all(abs(x - circle0["r"]) < 1e-6 for x in radii), (circle0, radii)
    # Shift, pressed mid-drag, snaps at once
    p.keyboard.down("Shift")
    w.run("await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    snapped = w.run("return wizard.layout.plateAngle(wizard.layout.model().instances[0].id);")
    assert abs(snapped / 45 - round(snapped / 45)) < 1e-6, snapped
    assert round(snapped) % 360 == 45
    p.mouse.up()
    p.keyboard.up("Shift")
    settle(w)
    kept = w.run("return wizard.layout.model().instances[0];")
    assert isinstance(kept["angle"], int)
    assert w.problems == []


def test_a_click_on_a_patch_lays_the_instance_down_and_the_pointer_line_says_what_it_gives(page, front_server):
    w = open_layout(page, front_server, [spacer()])
    (a,) = w.run("return wizard.layout.model().instances.map((i) => ({ id: i.id, lay: i.lay }));")
    w.run("wizard.layout.select(arg, 'only');", a["id"])
    w.until("return wizard.layoutStep.view().patchesInSight().some((p) => p.pickable);")
    patch = w.run("return wizard.layoutStep.view().patchesInSight().find((p) => p.pickable);")
    w.page.mouse.move(patch["x"], patch["y"])
    line = w.run("return wizard.layoutStep.view().pointerLine();")
    assert line.startswith("Lay it on this ") and line.endswith(" tall"), line
    w.page.mouse.click(patch["x"], patch["y"])
    w.until("return wizard.layout.model().instances[0].lay.join() !== arg.join();", a["lay"])
    settle(w)
    assert w.page.locator("#layout-orient .linkish").inner_text() == "Put back as modelled"
    assert w.problems == []


def test_the_four_keys_and_the_keys_that_do_nothing(page, front_server):
    w = open_layout(page, front_server, [spacer()], quantities={0: 3})
    before = w.run("return wizard.layout.model().instances.map(({ id, x, y, angle }) => ({ id, x, y, angle }));")
    w.page.focus("#layout-view canvas")
    w.page.keyboard.press("Control+a")
    w.until("return wizard.layout.model().selected.length === 3;")
    assert w.page.locator("#layout-selection").inner_text() == "3 instances move and turn together"
    for key in ["Delete", "Control+d", "Control+z", "Control+y", "Backspace"]:
        w.page.keyboard.press(key)
    settle(w)
    assert w.run("return wizard.layout.model().instances.map(({ id, x, y, angle }) => ({ id, x, y, angle }));") == before
    assert w.run("return wizard.parts.rows()[0].quantity;") == 3
    w.page.keyboard.press("Escape")
    w.until("return wizard.layout.model().selected.length === 0;")
    w.page.keyboard.press("Control+1")
    w.page.keyboard.press("f")
    settle(w)
    assert w.problems == []


@pytest.mark.parametrize("width", [320, 479, 480, 519, 520, 679, 680])
def test_the_step_has_no_sideways_scroll_and_its_view_is_square_then_4_by_3(page, front_server, width):
    w = open_layout(page, front_server, [spacer(), bracket()], width=width)
    w.run("wizard.layout.select(wizard.layout.model().instances[0].id, 'only');")
    settle(w)
    assert no_sideways_scroll(w.page) == []
    box = w.page.locator("#layout-view").bounding_box()
    ratio = box["width"] / box["height"]
    panel = w.run("return document.getElementById('wizard').getBoundingClientRect().width;")
    assert abs(ratio - (4 / 3 if panel >= 520 else 1)) < 0.02, (panel, ratio)


def test_the_help_opens_with_the_list_of_gestures_and_closes_on_escape(page, front_server):
    w = open_layout(page, front_server, [spacer()])
    w.page.click("#btn-layout-help")
    assert w.page.locator("#layout-help").is_visible()
    assert w.page.locator("#layout-gestures").inner_text().startswith("Drag an instance to move it")
    assert w.page.locator("#layout-more li").count() == 5
    w.page.keyboard.press("Escape")
    assert w.page.locator("#layout-help").is_hidden()


def test_a_malformed_stl_of_the_largest_size_ends_in_a_notification_without_holding_the_page(page, front_server):
    """What the second trial left to the page: a malformed file chosen on the Parts step ends in the
    notification of a part the page cannot draw, from the main thread, which is held under 250 ms."""
    bad = bytearray(7_500_084)
    bad[80:84] = (150_001).to_bytes(4, "little")
    front_server.files["/test-files/bad.stl"] = bytes(bad)
    w = Wizard(page, front_server, fake_clock=False)
    # The file as a drop hands it to the page (the test's own fetch stands in for the user's
    # disk, so that putting 7.5 MB into the page is not counted as the page's own hold).
    w.run("const bytes = await (await fetch('/test-files/bad.stl')).arrayBuffer(); "
          "window.__bad = new File([bytes], 'bad.stl', { type: 'application/octet-stream' });")
    w.run("wizard.holdMeter.start(); wizard.parts.addFiles([window.__bad]);")
    w.page.wait_for_selector("#notices .notice.error")
    held = w.run("return wizard.holdMeter.stop();")
    assert w.page.locator("#notices .n-what").inner_text() == "bad: PenguinSlicer could not show this part, so it cannot be imported."
    assert held < MAIN_THREAD_HOLD_MS, held
