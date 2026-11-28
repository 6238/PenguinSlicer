"""The layer preview in Chromium, drawing in software on a machine without a graphics card
(wizard/README-details.md, "The layer preview"), tested coarsely, as that section says: on the small
real sliced files of wizard/tests/sliced/, the view draws something and not a blank or an error,
fills roughly the expected part of the view, shows the four colours, changes when the layer bar or
the view moves, shows the ghost of what is still to print, and draws again after its drawing
context is lost, twice in one page. The page is left on the real clock, since drawing goes frame
by frame; every wait is on an event of the page (the first layer drawn, the full look on the
screen), never on a duration. Whether the view looks right is a person's judgement of the test
renders (make -C wizard look-preview)."""
import json
from pathlib import Path

import pytest

from tests_browser.conftest import Wizard

WIZARD = Path(__file__).resolve().parent.parent
SLICED = WIZARD / "tests" / "sliced"
REAL = WIZARD.parent / "contracts" / "examples" / "parts" / "real"
MADE = WIZARD / "trials" / "parts"
MAIN_THREAD_HOLD_MS = 250
# The coarse checks of the look, the first trial's (wizard/trials/preview/run.py).
COVERED = 0.05
GROUP_SHOWN = 0.0005
CHANGED = 0.01
GHOST_SHOWN = 0.002


def asset(prefix):
    (found,) = (WIZARD / "dist" / "assets").glob(f"{prefix}.????????????.js")
    return f"/assets/{found.name}"


def part_file(ref):
    return MADE / f"{ref}.stl" if ref == "hex-spacer" else REAL / f"{ref}.stl"


def modules():
    return {name: asset(name) for name in ("layer-preview", "preview-worker", "frames", "clock", "drawing")}


# Puts a .gl-view in the Preview step, shown, and the layer preview in it, kept as
# window.__preview with what it reported; then shows the sliced file `arg.sliced` with the ghost
# of its plate's instances, each part read by the page's own worker.
OPEN = """
    const m = {};
    for (const [name, url] of Object.entries(arg.modules)) m[name] = await import(url);
    for (const s of document.querySelectorAll('section.step')) s.hidden = s.dataset.step !== 'preview';
    const host = document.createElement('div');
    host.className = 'gl-view';
    host.id = 'test-preview';
    document.querySelector('section[data-step="preview"]').append(host);
    const seen = window.__seen = { progress: [], layers: [], reports: [] };
    const view = window.__preview = m['layer-preview'].createLayerPreview(host, {
        frames: m.frames.realFrames, clock: m.clock.realClock, startWorker: m['preview-worker'].startPreviewWorker,
        software: true,
        report: (what, fields) => { seen.reports.push([what, fields.detail]); wizard.reports.failure(what, fields); },
        onProgress: (p) => seen.progress.push(p.stage), onLayer: (l) => seen.layers.push(l.index) });
    window.__colours = m.drawing;
    const bytes = await (await fetch('/test-files/' + arg.sliced)).arrayBuffer();
    let plate = null;
    if (arg.plate) {
        const meshes = {};
        for (const ref of Object.keys(arg.plate.parts)) {
            const stl = await (await fetch('/test-files/' + ref + '.stl')).arrayBuffer();
            const read = await wizard.geometry.read('preview-' + ref, stl, 'mm');
            if (!read.ok) return { read: read.error };
            meshes[ref] = wizard.geometry.mesh('preview-' + ref).positions;
        }
        plate = { instances: arg.plate.instances, meshes };
    }
    wizard.holdMeter.start();
    const answer = await view.show(bytes, plate);
    return { answer, held: wizard.holdMeter.stop(), summary: view.summary(), groups: view.groups() };
"""

# The share of the view that is not background, and in each group's colour (the walls at any of
# their shades), of the pixels of the full look; the first trial's look.js.
LOOK = """
    const { BACKGROUND, COLOURS } = window.__colours;
    const look = await window.__preview.look({ ghost: arg.ghost });
    window.__looks = window.__looks || {};
    window.__looks[arg.name] = look.pixels;
    const px = look.pixels, shades = [0.66, 0.75, 0.83, 0.92, 1];
    const ramps = COLOURS.map((c, g) => (g === 0 ? shades : [1]).map((s) => c.map((v) => v * s * 255)));
    const bg = BACKGROUND.map((v) => v * 255);
    const counts = [0, 0, 0, 0];
    let background = 0;
    for (let i = 0; i < px.length; i += 4) {
        const r = px[i], g = px[i + 1], b = px[i + 2];
        if (Math.abs(r - bg[0]) < 3 && Math.abs(g - bg[1]) < 3 && Math.abs(b - bg[2]) < 3) { background++; continue; }
        ramps.forEach((ramp, k) => { if (ramp.some((c) => Math.abs(c[0] - r) + Math.abs(c[1] - g) + Math.abs(c[2] - b) < 24)) counts[k]++; });
    }
    const all = px.length / 4;
    return { covered: 1 - background / all, groups: counts.map((c) => c / all), width: look.width, height: look.height };
"""

CHANGED_SHARE = """
    const a = window.__looks[arg.a], b = window.__looks[arg.b];
    let changed = 0;
    for (let i = 0; i < a.length; i += 4) if (a[i] !== b[i] || a[i + 1] !== b[i + 1] || a[i + 2] !== b[i + 2]) changed++;
    return changed / (a.length / 4);
"""

LOSE = """
    const view = window.__preview, ext = view.canvas.getContext('webgl2').getExtension('WEBGL_lose_context');
    await new Promise((resolve) => { view.canvas.addEventListener('webglcontextlost', resolve, { once: true }); ext.loseContext(); });
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    await new Promise((resolve) => { view.canvas.addEventListener('webglcontextrestored', resolve, { once: true }); ext.restoreContext(); });
    await view.untilRest();
"""


def open_view(page, server, sliced, width=680):
    plate = json.loads((SLICED / f"{sliced}.json").read_text())
    server.files[f"/test-files/{sliced}.gcode.3mf"] = (SLICED / f"{sliced}.gcode.3mf").read_bytes()
    for ref in plate["parts"]:
        server.files[f"/test-files/{ref}.stl"] = part_file(ref).read_bytes()
    w = Wizard(page, server, width=width, height=900, fake_clock=False)
    opened = w.run(OPEN, {"modules": modules(), "sliced": f"{sliced}.gcode.3mf", "plate": plate})
    return w, opened


def look(w, name, ghost=True):
    return w.run(LOOK, {"name": name, "ghost": ghost})


def changed(w, a, b):
    return w.run(CHANGED_SHARE, {"a": a, "b": b})


def test_a_sliced_file_with_supports_draws_its_four_colours_its_ghost_and_changes_with_the_bar(page, front_server):
    w, opened = open_view(page, front_server, "pair-supports")
    assert opened["answer"] == {"ok": True, "layers": 132}, opened
    assert opened["held"] < MAIN_THREAD_HOLD_MS, opened
    top = look(w, "top")
    assert top["covered"] >= COVERED, top
    assert top["width"] > 300 and top["height"] > 200, top
    layers = w.run("return window.__preview.layer();")
    assert layers["index"] == 131 and layers["layers"] == 132
    w.run("window.__preview.setLayer(65);")
    look(w, "mid")
    mid = look(w, "mid-bare", ghost=False)
    for g, name in enumerate(("walls", "infill", "surfaces", "supports")):
        assert max(top["groups"][g], mid["groups"][g]) >= GROUP_SHOWN, (name, top, mid)
    assert changed(w, "top", "mid-bare") >= CHANGED
    assert changed(w, "mid", "mid-bare") >= GHOST_SHOWN, "the ghost of what is still to print shows above the cut"
    # the view turned to look from above changes what is drawn
    w.run("await window.__preview.setView('top');")
    look(w, "from-above")
    assert changed(w, "mid", "from-above") >= CHANGED
    assert w.problems == []


def test_the_view_draws_again_after_its_drawing_context_is_lost_twice_and_reports_each_loss(page, front_server):
    w, opened = open_view(page, front_server, "pair-supports")
    assert opened["answer"]["ok"] is True
    w.run("window.__preview.setLayer(65);")
    for n in (1, 2):
        with page.expect_request(lambda r: r.url.endswith("/api/reports/failure")) as sent:
            w.run(LOSE)
        assert json.loads(sent.value.post_data)["what"] == "drawing_context_lost"
        after = look(w, f"after-{n}")
        bare = look(w, f"after-{n}-bare", ghost=False)
        assert after["covered"] >= COVERED, (n, after)
        assert changed(w, f"after-{n}", f"after-{n}-bare") >= GHOST_SHOWN, (n, "the ghost is drawn again too")
        assert bare["covered"] >= COVERED
    assert w.problems == []


def test_a_plate_without_supports_draws_its_three_groups_and_no_fourth(page, front_server):
    w, opened = open_view(page, front_server, "spacer-1")
    assert opened["answer"] == {"ok": True, "layers": 13}
    assert opened["groups"][3] == 0
    top = look(w, "top")
    assert top["covered"] >= 0.002, top          # one spacer 16 mm across, framed on itself
    w.run("window.__preview.setLayer(6);")
    mid = look(w, "mid-bare", ghost=False)
    for g in (0, 1, 2):
        assert max(top["groups"][g], mid["groups"][g]) >= GROUP_SHOWN, (g, top, mid)
    assert w.problems == []


def test_the_layer_bar_moves_by_keys_and_tells_a_screen_reader_its_layer(page, front_server):
    w, opened = open_view(page, front_server, "spacer-1")
    assert opened["answer"]["ok"] is True
    bar = page.locator("#test-preview .layer-slider")
    assert bar.get_attribute("role") == "slider"
    assert bar.get_attribute("aria-valuenow") == "13"
    assert bar.get_attribute("aria-valuetext") == "Layer 13 of 13, 3.2 mm high"
    bar.focus()
    page.keyboard.press("ArrowDown")
    assert bar.get_attribute("aria-valuenow") == "12"
    page.keyboard.press("Home")
    assert bar.get_attribute("aria-valuenow") == "1"
    assert page.locator("#test-preview .ls-thumb span").text_content() == "Layer 1"
    page.keyboard.press("End")
    assert bar.get_attribute("aria-valuenow") == "13"
    assert w.run("return window.__seen.layers;")[-3:] == [11, 0, 12]
    # the two small buttons under the view step one layer, never past the ends
    w.run("window.__preview.stepLayer(-1); window.__preview.stepLayer(-1);")
    assert bar.get_attribute("aria-valuenow") == "11"
    w.run("window.__preview.stepLayer(1); window.__preview.stepLayer(1); window.__preview.stepLayer(1);")
    assert bar.get_attribute("aria-valuenow") == "13"


def test_reset_view_puts_the_camera_back_after_a_turn(page, front_server):
    w, opened = open_view(page, front_server, "spacer-1")
    assert opened["answer"]["ok"] is True
    look(w, "first")
    box = page.locator("#test-preview canvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 + 120, box["y"] + box["height"] / 2 + 40, steps=6)
    page.mouse.up()
    look(w, "turned")
    assert changed(w, "first", "turned") >= CHANGED, "a left-drag turns the view"
    w.run("window.__preview.resetView();")
    look(w, "reset")
    assert changed(w, "first", "reset") == 0


def test_dragging_the_bar_goes_through_the_layers_with_the_look_while_moving(page, front_server):
    w, opened = open_view(page, front_server, "pair-supports")
    assert opened["answer"]["ok"] is True
    box = page.locator("#test-preview .layer-slider").bounding_box()
    x = box["x"] + box["width"] / 2
    page.mouse.move(x, box["y"] + 2)
    page.mouse.down()
    page.mouse.move(x, box["y"] + box["height"] / 2, steps=8)
    assert w.run("return window.__preview.atRest();") is False, "the bar held down is a move"
    page.mouse.up()
    index = w.run("return window.__preview.layer().index;")
    assert 50 < index < 80, index
    w.run("await window.__preview.untilRest();")
    assert w.run("return window.__preview.atRest();") is True


def test_the_sliced_file_is_read_off_the_main_thread_with_progress_and_a_drawing_summary(page, front_server):
    w, opened = open_view(page, front_server, "pair-supports")
    assert w.run("return [...new Set(window.__seen.progress)];") == ["unpacking", "reading", "preparing"]
    summary = opened["summary"]
    assert summary["view"] == "preview"
    assert summary["instances"] == 2
    assert summary["sliced_file_bytes"] == (SLICED / "pair-supports.gcode.3mf").stat().st_size
    assert summary["sliced_file_lines"] > 200_000
    assert 0 < summary["first_layer_ms"] < 5000
    assert summary["longest_hold_ms"] < MAIN_THREAD_HOLD_MS
    moved = w.run("return await window.__preview.drive('turn', 12);")
    assert moved["frames"] >= 12
    after = w.run("return window.__preview.summary();")
    assert after["fps_typical"] > 0 and after["fps_worst"] > 0


def test_a_browser_without_3d_drawing_ends_in_the_wizards_report_and_one_report_to_the_server(page, front_server):
    """A browser whose WebGL 2 is turned off gives no context: the view says so, never a blank."""
    front_server.files["/test-files/spacer-1.gcode.3mf"] = (SLICED / "spacer-1.gcode.3mf").read_bytes()
    page.add_init_script("""
        const get = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (kind, ...rest) { return kind === 'webgl2' && this.closest('#test-preview') ? null : get.call(this, kind, ...rest); };
    """)
    w = Wizard(page, front_server, width=680, height=900, fake_clock=False)
    with page.expect_request(lambda r: r.url.endswith("/api/reports/failure")) as sent:
        opened = w.run(OPEN, {"modules": modules(), "sliced": "spacer-1.gcode.3mf", "plate": None})
    error = opened["answer"]["error"]
    assert error["code"] == "wizard.preview_not_drawable"
    assert error["message"] == "This browser cannot draw the layer preview: its 3D drawing is turned off or missing."
    assert json.loads(sent.value.post_data)["what"] == "page_failed"
    assert w.problems == []


def test_a_file_that_is_not_a_sliced_file_ends_in_the_wizards_report_and_one_report_to_the_server(page, front_server):
    front_server.files["/test-files/bad.gcode.3mf"] = b"this is not an archive"
    w = Wizard(page, front_server, width=680, height=900, fake_clock=False)
    with page.expect_request(lambda r: r.url.endswith("/api/reports/failure")) as sent:
        opened = w.run(OPEN, {"modules": modules(), "sliced": "bad.gcode.3mf", "plate": None})
    assert opened["answer"]["ok"] is False
    error = opened["answer"]["error"]
    assert error["code"] == "wizard.preview_unreadable"
    assert error["message"] == "PenguinSlicer could not read this plate's sliced file to draw its preview."
    body = json.loads(sent.value.post_data)
    assert body["what"] == "page_failed"
    assert "not a zip archive" in body["detail"]
    assert page.locator("#test-preview .layer-slider").is_hidden()
    assert w.problems == []
