#!/usr/bin/env python3
"""The Layout view's frame rate while dragging, at 150 instances, on this machine
(wizard/README-details.md, "Performance targets": 10 frames a second without a graphics card, 30
with one, at 150 instances of parts up to 150,000 triangles).

Two plates, each of 150 instances, arranged by the page itself: a mix of the real parts kept in the
repository (140 of Pulley v3 and one or two of each other real part, the second trial's mix) and
150 of `hub-150k.stl`, the largest part allowed. On each, one instance is dragged across the plate,
one pointer move on each animation frame, for DRAG_FRAMES frames, and then the selection of every
instance is turned by its rotation handle in the same way; the frames the view drew, their typical
and longest time, and the main thread's longest hold (the page's heartbeat) are recorded. Not a
test: the figures are written to docs/orchestration/phase-2/look/wizard-5b/frame-rate.json and
printed, with the machine's processors and memory as its cgroup gives them.

Usage: make -C wizard measure-layout (builds first).
"""
import json
import os
import platform
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from tests_browser.conftest import DIST, Wizard  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer  # noqa: E402

REAL = WIZARD.parent / "contracts" / "examples" / "parts" / "real"
MADE = WIZARD / "trials" / "parts"
OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-5b" / "frame-rate.json"
DRAG_FRAMES = 90
FPS_SOFTWARE = 10

PLATES = {
    "real-mix-150": [("pulley-v3.stl", REAL, 140), ("clamp-plate-inner.stl", REAL, 2), ("elevator-block-bottom-inner.stl", REAL, 1),
                     ("elevator-block-carriage.stl", REAL, 1), ("elevator-block-top.stl", REAL, 1), ("elevator-top-inner.stl", REAL, 1),
                     ("inner-spacer.stl", REAL, 2), ("outer-clamp.stl", REAL, 2)],
    "hub-150k-150": [("hub-150k.stl", MADE, 150)],
    "spacers-150": [("hex-spacer.stl", MADE, 150)],
}

# One pointer move on each animation frame, along a path across the view; the view draws on its
# own frames. Returns the frames drawn, the time taken and each frame's time.
DRIVE = """
    const view = wizard.layoutStep.view();
    const c = view.canvas;
    const r = c.getBoundingClientRect();
    const from = arg.from, to = arg.to, frames = arg.frames;
    const ev = (type, x, y, shift) => new PointerEvent(type, { clientX: x, clientY: y, button: 0, buttons: type === 'pointerup' ? 0 : 1,
        pointerId: 1, pointerType: 'mouse', isPrimary: true, bubbles: true, cancelable: true, shiftKey: Boolean(shift) });
    c.dispatchEvent(ev('pointerdown', from.x, from.y));
    const drawn0 = view.frames();
    wizard.holdMeter.start();
    const times = [];
    let last = performance.now();
    const t0 = last;
    await new Promise((done) => {
        let k = 0;
        function step(now) {
            times.push(now - last); last = now; k += 1;
            const t = k / frames;
            c.dispatchEvent(ev('pointermove', from.x + (to.x - from.x) * t, from.y + (to.y - from.y) * t));
            if (k < frames) requestAnimationFrame(step); else done();
        }
        requestAnimationFrame(step);
    });
    const elapsed = performance.now() - t0;
    const held = wizard.holdMeter.stop();
    c.dispatchEvent(ev('pointerup', to.x, to.y));
    await wizard.layout.idle();
    const drawn = view.frames() - drawn0;
    times.shift();
    times.sort((a, b) => a - b);
    return { frames: drawn, ms: elapsed, fps: drawn / (elapsed / 1000), median_frame_ms: times[Math.floor(times.length / 2)],
             worst_frame_ms: times[times.length - 1], held_ms: held };
"""


def machine():
    cpu = Path("/sys/fs/cgroup/cpu.max").read_text().split()
    mem = Path("/sys/fs/cgroup/memory.max").read_text().strip()
    cpus = int(cpu[0]) / int(cpu[1]) if cpu[0] != "max" else os.cpu_count()
    return {"machine": platform.machine(), "processors": cpus, "memory_gb": round(int(mem) / 2**30, 1) if mem != "max" else None}


def measure(browser, server, name, parts):
    page = browser.new_page(viewport={"width": 520, "height": 900})
    page.set_default_timeout(600_000)
    for file, folder, _ in parts:
        server.files[f"/test-files/{file}"] = (folder / file).read_bytes()
    w = Wizard(page, server, width=520, height=900, fake_clock=False)
    w.page.check("#upload-units input[value=mm]")
    files = [{"name": f, "mimeType": "application/octet-stream", "buffer": (folder / f).read_bytes()} for f, folder, _ in parts]
    w.page.set_input_files("#f-upload", files)
    w.until(f"return wizard.parts.rows().length === {len(parts)} && wizard.parts.rows().every((r) => !r.arriving && r.drawn);", tries=100_000)
    for n, (_, _, qty) in enumerate(parts):
        w.run("wizard.parts.setQuantity(wizard.parts.rows()[arg[0]].key, arg[1]);", [n, qty])
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.layout.model().instances.length === 150 && wizard.layout.model().instances.every((i) => i.bounds) "
            "&& wizard.layoutStep.view() && wizard.layoutStep.view().frames() > 0;", tries=100_000)
    w.run("await wizard.layout.idle(); wizard.layoutStep.view().viewPlate(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    model = w.run("const m = wizard.layout.model(); return { onPlate: m.instances.filter((i) => !i.beside).length, first: m.instances.find((i) => !i.beside) };")
    first = model["first"]
    start = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [first["x"], first["y"]])
    end = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [first["x"] + 60, first["y"] + 40])
    dragging = w.run(DRIVE, {"from": start, "to": end, "frames": DRAG_FRAMES})
    # every instance selected, turned by its handle
    w.run("wizard.layout.selectAll(); await wizard.layout.idle(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));")
    h = w.run("return wizard.layoutStep.view().handleAt();")
    turning = None
    if h:
        circle_end = w.run("const b = wizard.layout.model().instances.filter((i) => !i.beside).map((i) => i.bounds); "
                           "const x = (Math.min(...b.map((v) => v[0])) + Math.max(...b.map((v) => v[2]))) / 2; "
                           "const y = (Math.min(...b.map((v) => v[1])) + Math.max(...b.map((v) => v[3]))) / 2; "
                           "return wizard.layoutStep.view().plateAt(x + 150, y);")
        turning = w.run(DRIVE, {"from": h, "to": circle_end, "frames": DRAG_FRAMES})
    triangles = w.run("return wizard.layout.model().instances.reduce((n, i) => n + wizard.geometry.mesh(i.part).positions.length / 9, 0);")
    page.close()
    return {"instances": 150, "on_plate": model["onPlate"], "triangles_drawn": triangles, "dragging": dragging, "turning_all": turning}


def main():
    results = {"target_fps_without_graphics_card": FPS_SOFTWARE, **machine(), "chromium": None, "plates": {}}
    with sync_playwright() as pw, FakeFrontServer(DIST) as server:
        browser = pw.chromium.launch(headless=True)
        results["chromium"] = browser.version
        for name, parts in PLATES.items():
            results["plates"][name] = measure(browser, server, name, parts)
            m = results["plates"][name]
            print(f"{name}: {m['on_plate']} of 150 on the plate, {m['triangles_drawn']:,} triangles; dragging {m['dragging']['fps']:.1f} fps "
                  f"(median frame {m['dragging']['median_frame_ms']:.0f} ms, worst {m['dragging']['worst_frame_ms']:.0f} ms, held {m['dragging']['held_ms']} ms)"
                  + (f"; turning all {m['turning_all']['fps']:.1f} fps" if m["turning_all"] else ""))
        browser.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
