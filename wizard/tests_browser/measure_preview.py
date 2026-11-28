"""The layer preview measured in the page, and its test renders (`make -C wizard measure-preview`).

For each plate, the wizard's built page in Playwright's Chromium, headless, on this machine (which
draws 3D in software), at a panel 680 px wide, the view the mockup's .gl-view in the Preview step:
the sliced file is fetched and shown with the ghost of its instances, and the script records the
time to the first layer and to the full look, the frames a second typical and worst while turning
the view and while dragging the layer bar along the first trial's paths (60 frames each), the
longest hold of the main thread by the page's own heartbeat and by the browser's long tasks, the
peak memory of the page's renderer and graphics processes, and the coarse checks of the look,
then makes the test renders at the fixed angles. One JSON file for each plate and the renders go
to docs/orchestration/phase-2/look/wizard-7/, with an index.html showing them.

The plates are the first trial's three (their sliced files in wizard/trials/sliced/, made as
wizard/trials/preview/README.md says, not committed) and the committed pair-supports of
wizard/tests/sliced/. A plate whose sliced file is missing is skipped and said so.
"""
import argparse
import html
import json
import os
import platform
import sys
from pathlib import Path

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from playwright.sync_api import sync_playwright  # noqa: E402

from tests_browser.conftest import DIST, Wizard  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer  # noqa: E402
from tests_browser.test_layer_preview import (  # noqa: E402
    CHANGED_SHARE, COVERED, GHOST_SHOWN, GROUP_SHOWN, LOOK, LOSE, CHANGED, modules, part_file)

OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-7"
TRIALS = WIZARD / "trials"
PLATES = {
    "four-each-b-supports": (TRIALS / "sliced" / "four-each-b-supports.gcode.3mf", TRIALS / "plates" / "four-each-b-supports.json"),
    "blocks-12-supports": (TRIALS / "sliced" / "blocks-12-supports.gcode.3mf", TRIALS / "plates" / "blocks-12-supports.json"),
    "spacers-150": (TRIALS / "sliced" / "spacers-150.gcode.3mf", TRIALS / "plates" / "spacers-150.json"),
    "pair-supports": (WIZARD / "tests" / "sliced" / "pair-supports.gcode.3mf", WIZARD / "tests" / "sliced" / "pair-supports.json"),
}
WIDTH = 680

# As the tests' OPEN, but the first layer timed from before the fetch, as the trial timed it, and
# the browser's long tasks kept for the comparison with the trial's figures.
OPEN = """
    window.__longtasks = [];
    try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__longtasks.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true }); } catch {}
    const m = {};
    for (const [name, url] of Object.entries(arg.modules)) m[name] = await import(url);
    for (const s of document.querySelectorAll('section.step')) s.hidden = s.dataset.step !== 'preview';
    const host = document.createElement('div');
    host.className = 'gl-view';
    host.id = 'test-preview';
    document.querySelector('section[data-step="preview"]').append(host);
    const view = window.__preview = m['layer-preview'].createLayerPreview(host, {
        frames: m.frames.realFrames, clock: m.clock.realClock, startWorker: m['preview-worker'].startPreviewWorker, software: true });
    window.__colours = m.drawing;
    const meshes = {};
    for (const ref of Object.keys(arg.plate.parts)) {
        const stl = await (await fetch('/test-files/' + ref + '.stl')).arrayBuffer();
        await wizard.geometry.read('preview-' + ref, stl, 'mm');
        meshes[ref] = wizard.geometry.mesh('preview-' + ref).positions;
    }
    const since = m.frames.realFrames.now();
    wizard.holdMeter.start();
    const t0 = performance.now();
    const bytes = await (await fetch('/test-files/' + arg.sliced)).arrayBuffer();
    const fetched = performance.now() - t0;
    const answer = await view.show(bytes, { instances: arg.plate.instances, meshes }, { since });
    const held = wizard.holdMeter.stop();
    await view.untilRest();
    const full = performance.now() - t0;
    const box = host.getBoundingClientRect();
    return { answer, fetch_ms: fetched, load_hold_ms: held, full_look_ms: full, summary: view.summary(),
             decimate: view.decimate(), groups: view.groups(), view_px: [Math.round(box.width), Math.round(box.height)],
             renderer: (() => { const gl = document.createElement('canvas').getContext('webgl2');
               const e = gl && gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : null; })() };
"""

DRIVE = """
    const t = performance.now();
    wizard.holdMeter.start();
    const r = await window.__preview.drive(arg.kind, arg.steps);
    r.longest_hold_ms = wizard.holdMeter.stop();
    r.longest_task_ms = Math.max(0, ...window.__longtasks.filter(([s]) => s >= t).map(([, d]) => d));
    return r;
"""


def read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def machine():
    cpu = read("/sys/fs/cgroup/cpu.max").split()
    mem = read("/sys/fs/cgroup/memory.max").strip()
    return {"cpus": int(cpu[0]) / int(cpu[1]) if len(cpu) == 2 and cpu[0] != "max" else None,
            "memory_gb": int(mem) / 2 ** 30 if mem and mem != "max" else None,
            "arch": platform.machine(), "system": platform.system()}


def process_memory(browser):
    """The peak resident memory (VmHWM) of the renderer and graphics processes, in MiB (the kernel's KiB over
    1,024), the unit of PAGE_MEMORY_MB's 1,024; the fields keep the name `_mb`."""
    cdp = browser.new_browser_cdp_session()
    out = {}
    for info in cdp.send("SystemInfo.getProcessInfo")["processInfo"]:
        fields = dict(line.split(":", 1) for line in read(f"/proc/{info['id']}/status").splitlines() if ":" in line)
        hwm = int(fields.get("VmHWM", "0 kB").split()[0]) / 1024
        kind = info["type"].lower()
        out[kind] = max(out.get(kind, 0), hwm)
    out["page_peak_mb"] = out.get("renderer", 0) + out.get("gpu", 0)
    return out


def say(name, what):
    print(f"{name}: {what}", file=sys.stderr, flush=True)


def measure(browser, name, sliced, plate_path, steps):
    plate = json.loads(plate_path.read_text())
    with FakeFrontServer(DIST) as server:
        server.files[f"/test-files/{name}.gcode.3mf"] = sliced.read_bytes()
        for ref in plate["parts"]:
            server.files[f"/test-files/{ref}.stl"] = part_file(ref).read_bytes()
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(600_000)
        try:
            w = Wizard(page, server, width=WIDTH, height=900, fake_clock=False)
            say(name, "opened; showing the sliced file")
            m = w.run(OPEN, {"modules": modules(), "sliced": f"{name}.gcode.3mf", "plate": plate})
            say(name, "drawn; turning and dragging the bar")
            if not m["answer"].get("ok"):
                raise RuntimeError(f"{name}: {m['answer']}")
            m["plate"], m["browser"] = name, f"Chromium {browser.version}"
            m["load_longest_task_ms"] = w.run("return Math.max(0, ...window.__longtasks.map(([, d]) => d));")
            m["load_average_before"] = os.getloadavg()
            m["turn"] = w.run(DRIVE, {"kind": "turn", "steps": steps})
            m["layers"] = w.run(DRIVE, {"kind": "layers", "steps": steps})
            m["load_average_after"] = os.getloadavg()
            m["memory"] = process_memory(browser)
            say(name, "the coarse checks of the look")
            layers = m["answer"]["layers"]
            mid = max(0, layers // 2 - 1)
            look = lambda label, ghost=True: w.run(LOOK, {"name": label, "ghost": ghost})  # noqa: E731
            changed = lambda a, b: w.run(CHANGED_SHARE, {"a": a, "b": b})  # noqa: E731
            top = look("top")
            w.run(f"window.__preview.setLayer({mid});")
            look("mid")
            bare = look("mid-bare", False)
            present = [g for g, n in enumerate(m["groups"]) if n > 0]
            seen = [g for g in present if max(top["groups"][g], bare["groups"][g]) >= GROUP_SHOWN]
            m["look"] = {"covered": top["covered"], "groups_top": top["groups"], "groups_mid_layer": bare["groups"],
                         "groups_present": len(present), "groups_seen": len(seen),
                         "changes_with_layer": changed("top", "mid-bare"), "ghost_mid_layer": changed("mid", "mid-bare")}
            w.run(LOSE)
            after = look("after")
            look("after-bare", False)
            m["look"].update({"covered_after_context_lost": after["covered"], "ghost_after_context_lost": changed("after", "after-bare")})
            ok = (m["look"]["covered"] >= COVERED and m["look"]["groups_seen"] >= m["look"]["groups_present"]
                  and m["look"]["changes_with_layer"] >= CHANGED and m["look"]["ghost_mid_layer"] >= GHOST_SHOWN
                  and m["look"]["covered_after_context_lost"] >= COVERED and m["look"]["ghost_after_context_lost"] >= GHOST_SHOWN)
            m["look"]["passes"] = ok
            say(name, "the renders")
            renders = []
            folder = OUT / name
            folder.mkdir(parents=True, exist_ok=True)
            view = page.locator("#test-preview")

            def shot(label):
                view.screenshot(path=str(folder / f"{label}.png"))
                renders.append(f"{label}.png")

            w.run(f"window.__preview.setLayer({layers - 1});")
            for v in w.run("return window.__preview.views;"):
                w.run(f"await window.__preview.setView('{v}');")
                shot(v)
            w.run("await window.__preview.setView('default');")
            w.run(f"window.__preview.setLayer({mid}); await window.__preview.untilRest();")
            shot(f"default-layer-{mid + 1}")
            w.run("await window.__preview.setView('zoom');")
            shot(f"zoom-layer-{mid + 1}")
            w.run("await window.__preview.setView('default');")
            w.run(f"window.__preview.setLayer({layers - 1}); await window.__preview.untilRest();")
            w.run("await window.__preview.showMoving();")
            shot("default-moving")
            w.run("await window.__preview.stillAgain();")
            m["renders"] = renders
            m["problems"] = w.problems
            return m
        finally:
            context.close()


def index_html(results, mach):
    def f(v, digits=1):
        return "–" if v is None else f"{v:,.{digits}f}"
    rows, pictures = [], []
    for name, m in results.items():
        hold = max(m["load_hold_ms"], m["turn"]["longest_hold_ms"], m["layers"]["longest_hold_ms"])
        task = max(m["load_longest_task_ms"], m["turn"]["longest_task_ms"], m["layers"]["longest_task_ms"])
        rows.append(f"<tr><td>{html.escape(name)}</td><td>{f(m['summary']['first_layer_ms'] / 1000, 2)} / {f(m['full_look_ms'] / 1000, 2)} s</td>"
                    f"<td>{f(m['turn']['fps_typical'])} / {f(m['turn']['fps_worst'])}</td>"
                    f"<td>{f(m['layers']['fps_typical'])} / {f(m['layers']['fps_worst'])}</td>"
                    f"<td>{f(hold, 0)} / {f(task, 0)} ms</td><td>{f(m['memory']['page_peak_mb'], 0)} MB</td>"
                    f"<td>{m['decimate']}</td><td>{'passes' if m['look']['passes'] else 'misses'}</td></tr>")
        imgs = "".join(f'<figure><img src="{html.escape(name)}/{html.escape(r)}" alt="{html.escape(name)}, {html.escape(r[:-4])}" '
                       f'loading="lazy"><figcaption>{html.escape(r[:-4])}</figcaption></figure>' for r in m["renders"])
        pictures.append(f"<h2 id=\"{html.escape(name)}\">{html.escape(name)}</h2><div class=\"renders\">{imgs}</div>")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Layer preview measured</title>
<style>
body {{ margin: 24px 24px 48px; max-width: 76ch; background: #1a1714; color: #f1ebdf;
  font: 16px/24px "IBM Plex Sans", system-ui, sans-serif; }}
h1, h2 {{ font-weight: 600; margin: 24px 0 12px; }} h1 {{ font-size: 24px; }} h2 {{ font-size: 20px; }}
p {{ margin: 0 0 12px; }} a {{ color: #e08a52; text-decoration: none; }} a:hover {{ text-decoration: underline; }}
.wide {{ overflow-x: auto; max-width: none; }}
table {{ border-collapse: collapse; }} th {{ font: 600 12px/24px "IBM Plex Mono", monospace; text-transform: uppercase;
  border-bottom: 2px solid #a89e8b; text-align: left; padding: 0 12px 0 0; }}
td {{ vertical-align: top; border-bottom: 1px solid #4a3f33; padding: 6px 12px 6px 0; white-space: nowrap; }}
.renders {{ display: flex; flex-wrap: wrap; gap: 12px; max-width: none; }}
figure {{ margin: 0; }} figure img {{ width: 324px; display: block; border: 1px solid #4a3f33; }}
figcaption {{ color: #a89e8b; font-size: 12px; }}
</style></head><body>
<h1>Layer preview measured</h1>
<p>The wizard's layer preview, built on method C of the first trial, measured in its own page in headless
Chromium drawing in software ({html.escape(str(next(iter(results.values()))['renderer']))}), on
{f(mach.get('cpus'))} processors and {f(mach.get('memory_gb'))} GB of memory as the cgroup gives them
({html.escape(mach['arch'])}), shared with other work. Frames a second are typical / worst over 60 frames; the hold is
the page's own heartbeat / the browser's longest task; first / full is seconds from fetching the sliced file to the
first layer drawn and to the full look.</p>
<div class="wide"><table><thead><tr><th>Plate</th><th>First / full</th><th>Turning</th><th>Layer bar</th>
<th>Longest hold</th><th>Page memory</th><th>D</th><th>Look</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table></div>
{''.join(pictures)}
</body></html>
"""


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plates", default=",".join(PLATES))
    parser.add_argument("--steps", type=int, default=60)
    args = parser.parse_args(argv)
    if not (DIST / "index.html").is_file():
        print("wizard/dist/ is not built: run make -C wizard measure-preview, which builds it first", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    mach = machine()
    results = {}
    with sync_playwright() as playwright:
        for name in args.plates.split(","):
            sliced, plate = PLATES[name]
            if not sliced.is_file():
                print(f"{name}: {sliced} is missing, skipped (wizard/trials/preview/README.md says how to make it)", file=sys.stderr)
                continue
            print(f"{name}: measuring", file=sys.stderr, flush=True)
            # A browser of its own for each plate: the graphics process's high-water mark lasts as
            # long as the browser does, so a shared one would carry one plate's peak into the next.
            browser = playwright.chromium.launch(headless=True)
            try:
                m = measure(browser, name, sliced, plate, args.steps)
            finally:
                browser.close()
            m["machine"] = mach
            (OUT / f"{name}.json").write_text(json.dumps(m, indent=1) + "\n")
            results[name] = m
            print(f"{name}: first {m['summary']['first_layer_ms']:.0f} ms, turn {m['turn']['fps_typical']:.1f}/{m['turn']['fps_worst']:.1f}, "
                  f"bar {m['layers']['fps_typical']:.1f}/{m['layers']['fps_worst']:.1f}, holds {m['load_hold_ms']:.0f}/{m['turn']['longest_hold_ms']:.0f}/"
                  f"{m['layers']['longest_hold_ms']:.0f} ms, memory {m['memory']['page_peak_mb']:.0f} MB, look {m['look']['passes']}", file=sys.stderr, flush=True)
    if results:
        (OUT / "index.html").write_text(index_html(results, mach))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
