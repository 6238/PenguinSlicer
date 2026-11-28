"""The layer preview in Chromium, drawing in software on a machine without a graphics card
(wizard/README-details.md, "The layer preview"), tested coarsely, as that section says: on the small
real sliced files of wizard/tests/sliced/, the view draws something and not a blank or an error,
fills roughly the expected part of the view, shows the four colours, changes when the layer bar or
the view moves, shows the ghost of what is still to print, and draws again after its drawing
context is lost, twice in one page. The page is left on the real clock, since drawing goes frame
by frame; every wait is on an event of the page (the first layer drawn, the full look on the
screen), never on a duration, and no test holds a duration measured on that clock to a target:
the figures against the targets are measure-preview's. Whether the view looks right is a person's
judgement of the test renders (make -C wizard measure-preview)."""
import json
from pathlib import Path

import pytest

from tests_browser.conftest import Wizard

WIZARD = Path(__file__).resolve().parent.parent
SLICED = WIZARD / "tests" / "sliced"
REAL = WIZARD.parent / "contracts" / "examples" / "parts" / "real"
MADE = WIZARD / "trials" / "parts"
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
    const seen = window.__seen = { progress: [], layers: [], reports: [], failures: [], workers: [] };
    // Each worker the view starts, kept to see when the view stops it.
    const startWorker = () => {
        const port = m['preview-worker'].startPreviewWorker(), kept = { terminated: false };
        seen.workers.push(kept);
        return { ...port, terminate: () => { kept.terminated = true; port.terminate(); } };
    };
    const view = window.__preview = m['layer-preview'].createLayerPreview(host, {
        frames: m.frames.realFrames, clock: m.clock.realClock, startWorker,
        software: true,
        report: (what, fields) => { seen.reports.push([what, fields.detail]); wizard.reports.failure(what, fields); },
        onFailure: (error) => seen.failures.push(error),
        onProgress: (p) => seen.progress.push(p.stage), onLayer: (l) => seen.layers.push(l.index) });
    window.__colours = m.drawing;
    if (arg.sliced === null) return { created: true };
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
    # the mockup's ids, for the Preview step around the view
    assert page.locator("#test-preview #layer-slider #ls-thumb #ls-label").text_content() == "Layer 1"
    assert page.locator("#test-preview #layer-slider #ls-fill").count() == 1
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
    # Durations on the real clock: that they are measured, not how long they are (measure-preview's).
    assert summary["first_layer_ms"] > 0
    assert summary["longest_hold_ms"] >= 0
    assert summary["fps_typical"] is None and summary["fps_worst"] is None, "no frame rate before the view has moved"
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


# The view's WebGL 2 made to fail on purpose: `window.__break` names the call that throws, only on
# the layer preview's own canvas.
BREAK = """
    for (const name of ['createVertexArray', 'drawElements']) {
        const real = WebGL2RenderingContext.prototype[name];
        WebGL2RenderingContext.prototype[name] = function (...args) {
            if (window.__break === name && this.canvas.closest && this.canvas.closest('#test-preview')) throw new Error('broken on purpose in ' + name);
            return real.apply(this, args);
        };
    }
"""


def test_drawing_code_that_fails_while_building_ends_in_the_wizards_report_one_report_and_no_bar(page, front_server):
    front_server.files["/test-files/spacer-1.gcode.3mf"] = (SLICED / "spacer-1.gcode.3mf").read_bytes()
    page.add_init_script(BREAK)
    w = Wizard(page, front_server, width=680, height=900, fake_clock=False)
    w.run("window.__break = 'createVertexArray';")
    with page.expect_request(lambda r: r.url.endswith("/api/reports/failure")) as sent:
        opened = w.run(OPEN, {"modules": modules(), "sliced": "spacer-1.gcode.3mf", "plate": None})
    error = opened["answer"]["error"]
    assert error["code"] == "wizard.preview_failed"
    assert error["message"] == "PenguinSlicer could not draw the layer preview of this plate."
    body = json.loads(sent.value.post_data)
    assert body["what"] == "page_failed"
    assert "broken on purpose in createVertexArray" in body["detail"]
    assert page.locator("#test-preview .layer-slider").is_hidden(), "a failed view shows no bar that moves nothing"
    seen = w.run("return window.__seen;")
    assert [what for what, _ in seen["reports"]] == ["page_failed"], "reported once"
    assert seen["failures"] == [], "a failure before the first layer is the show's answer"
    assert w.problems == []


def test_drawing_code_that_fails_after_the_first_layer_is_told_to_the_caller_and_reported_once(page, front_server):
    page.add_init_script(BREAK)
    w, opened = open_view(page, front_server, "spacer-1")
    assert opened["answer"]["ok"] is True
    w.run("window.__break = 'drawElements';")
    with page.expect_request(lambda r: r.url.endswith("/api/reports/failure")) as sent:
        w.run("window.__preview.setLayer(3);")
        w.until("return window.__seen.failures.length > 0;")
    seen = w.run("return window.__seen;")
    assert [f["code"] for f in seen["failures"]] == ["wizard.preview_failed"]
    assert "broken on purpose in drawElements" in seen["failures"][0]["detail"]
    assert json.loads(sent.value.post_data)["what"] == "page_failed"
    assert [what for what, _ in seen["reports"]] == ["page_failed"]
    assert page.locator("#test-preview .layer-slider").is_hidden()
    assert w.run("return window.__preview.state().scheduled;") is False
    # The caller may show the file again, which draws once the fault is gone.
    again = w.run("""
        window.__break = null;
        const bytes = await (await fetch('/test-files/spacer-1.gcode.3mf')).arrayBuffer();
        return await window.__preview.show(bytes, null);
    """)
    assert again == {"ok": True, "layers": 13}
    assert page.locator("#test-preview .layer-slider").is_visible()
    assert w.problems == []


def test_a_later_show_or_destroy_stops_the_earlier_show_and_its_worker_at_once(page, front_server):
    front_server.files["/test-files/pair-supports.gcode.3mf"] = (SLICED / "pair-supports.gcode.3mf").read_bytes()
    w = Wizard(page, front_server, width=680, height=900, fake_clock=False)
    w.run(OPEN, {"modules": modules(), "sliced": None, "plate": None})
    r = w.run("""
        const view = window.__preview, seen = window.__seen;
        const bytes = await (await fetch('/test-files/pair-supports.gcode.3mf')).arrayBuffer();
        const first = view.show(bytes, null);
        const second = view.show(bytes, null);
        const firstStopped = seen.workers[0].terminated, secondStopped = seen.workers[1].terminated;
        const answers = [await first, await second];
        const third = view.show(bytes, null);
        view.destroy();
        const thirdStopped = seen.workers[2].terminated;
        return { answers, firstStopped, secondStopped, thirdStopped, third: await third, workers: seen.workers.length,
                 left: document.querySelectorAll('#test-preview canvas, #test-preview .layer-slider').length };
    """)
    assert r["answers"][0] == {"ok": False, "stopped": True}
    assert r["firstStopped"] is True and r["secondStopped"] is False, "the earlier worker is stopped at once"
    assert r["answers"][1] == {"ok": True, "layers": 132}
    assert r["third"] == {"ok": False, "stopped": True}
    assert r["thirdStopped"] is True
    assert r["workers"] == 3
    assert r["left"] == 0
    assert w.problems == []


# The walls' pixels of the full look without the ghost: the share at the walls' blue darkened (any
# shade under 0.95) and the share lightened (1.05 or over), each pixel's shade read from its blue.
WALL_SHADES = """
    const { COLOURS } = window.__colours;
    const look = await window.__preview.look({ ghost: false });
    const px = look.pixels, base = COLOURS[0].map((v) => v * 255);
    let darker = 0, lighter = 0;
    for (let i = 0; i < px.length; i += 4) {
        const s = px[i + 2] / base[2];
        if (Math.abs(px[i] - base[0] * s) + Math.abs(px[i + 1] - base[1] * s) > 10) continue;
        if (s < 0.95 && s > 0.5) darker++;
        else if (s >= 1.05 && s < 1.7) lighter++;
    }
    const all = px.length / 4;
    return { darker: darker / all, lighter: lighter / all };
"""


def test_the_walls_are_shaded_by_darkening_only(page, front_server):
    w, opened = open_view(page, front_server, "pair-supports")
    assert opened["answer"]["ok"] is True
    w.run("window.__preview.setLayer(100);")
    for view in ("default", "edge-on", "edge-on-side"):
        w.run(f"await window.__preview.setView('{view}');")
        shades = w.run(WALL_SHADES)
        assert shades["darker"] >= GROUP_SHOWN, (view, shades)
        assert shades["lighter"] == 0, (view, shades)
    assert w.problems == []
