#!/usr/bin/env python3
"""The layer preview's speed without a graphics card: the first trial of phase 2.

`make -C wizard trials-preview` runs this file. For each candidate method (a page of its own
in this folder) and each of the three real sliced files in wizard/trials/sliced/ (made by
wizard/trials/make_sliced_files.py), it opens the page in Playwright's Chromium, which draws
3D in software on a machine without a graphics card, turns the view and drags the layer bar
along fixed paths, and records the frames a second, the longest hold of the main thread, the
time to the first layer and the page's memory, as wizard/README-details.md, "How the trials
and measurements are run", says. It checks the look coarsely, makes test renders at fixed
angles, and writes one JSON file for each method and plate, the renders, and report.html,
which shows them side by side. It exits 1 when no method reaches the builder's part of
passing on all three plates, after writing everything.
"""
import argparse
import html
import json
import os
import platform
import sys
import threading
from pathlib import Path

PREVIEW = Path(__file__).resolve().parent
TRIALS = PREVIEW.parent
RESULTS = PREVIEW / "results"
SLICED = TRIALS / "sliced"

METHODS = {"A": "a-every.html", "B": "b-moving.html", "C": "c-progressive.html"}
PLATES = ["four-each-b-supports", "blocks-12-supports", "spacers-150"]
VIEWS = ["default", "top", "edge-on", "edge-on-side", "zoom", "zoom-edge-on", "zoom-top"]
GROUPS = ["walls", "infill", "surfaces", "supports"]
# The targets (wizard/README-details.md, "The layer preview" and "Performance targets").
FPS_SOFTWARE = 10
HOLD_MS = 250
FIRST_LAYER_S = 5
PAGE_MEMORY_MB = 1024
# The coarse checks of the look: the plate covers at least this much of the view, a colour
# counts as shown at this share of the view, and the layer bar changes this much of it.
COVERED = 0.05
GROUP_SHOWN = 0.0005
CHANGED = 0.01
VIEW_SIZE = (640, 480)


# ------------------------------------------------------------------ the machine

def cgroup_cpus(text):
    """Processors as the cgroup gives them: its quota over its period; None when unlimited."""
    parts = text.split()
    if len(parts) != 2 or parts[0] == "max":
        return None
    return int(parts[0]) / int(parts[1])


def cgroup_memory_gb(text):
    text = text.strip()
    return None if not text or text == "max" else int(text) / 2 ** 30


def read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def machine():
    return {
        "cpus": cgroup_cpus(read("/sys/fs/cgroup/cpu.max")),
        "memory_gb": cgroup_memory_gb(read("/sys/fs/cgroup/memory.max")),
        "processors_the_kernel_shows": os.cpu_count(),
        "arch": platform.machine(),
        "system": platform.system(),
    }


# ------------------------------------------------------------------ passing

def verdict(m):
    """The builder's part of passing for one method on one plate."""
    frames = min(m["turn"]["fps_typical"], m["layers"]["fps_typical"]) >= FPS_SOFTWARE
    hold = max(m["turn"]["longest_hold_ms"], m["layers"]["longest_hold_ms"], m["load"]["longest_hold_ms"]) <= HOLD_MS
    look = m["look"]
    look_ok = (look["covered"] >= COVERED and look["groups_seen"] >= look["groups_present"]
               and look["changes_with_layer"] >= CHANGED and bool(look["draws_after_context_lost"]))
    return {"frames": frames, "hold": hold, "look": look_ok, "passes": frames and hold and look_ok}


def slowest_fps(per_plate):
    return min(min(m["turn"]["fps_typical"], m["layers"]["fps_typical"]) for m in per_plate.values())


def choose(results):
    """The method the Preview step is built on: the fastest that passes on every plate, or,
    when none does, the fastest with the required look, with the target missed."""
    passing = [name for name, per_plate in results.items() if all(verdict(m)["passes"] for m in per_plate.values())]
    pool = passing or list(results)
    best = max(pool, key=lambda name: slowest_fps(results[name]))
    return {"method": best, "passes": bool(passing)}


# ------------------------------------------------------------------ the report

def report_html(results, chosen, mach, render_dir):
    def f(v, digits=1):
        return "–" if v is None else f"{v:,.{digits}f}"

    def get(m, *keys):
        for key in keys:
            m = m.get(key) if isinstance(m, dict) else None
        return m

    plates = list(dict.fromkeys(p for per_plate in results.values() for p in per_plate))
    rows = []
    for plate in plates:
        for name, per_plate in results.items():
            m = per_plate.get(plate)
            if not m:
                continue
            v = verdict(m)
            first = get(m, "first_layer_ms")
            hold = max(m["turn"]["longest_hold_ms"], m["layers"]["longest_hold_ms"], m["load"]["longest_hold_ms"])
            rows.append(
                f"<tr><td>{html.escape(plate)}</td><td>{name}</td><td>{f(first and first / 1000, 2)} s</td>"
                f"<td>{f(m['turn']['fps_typical'])} / {f(get(m, 'turn', 'fps_worst'))}</td>"
                f"<td>{f(m['layers']['fps_typical'])} / {f(get(m, 'layers', 'fps_worst'))}</td>"
                f"<td>{f(hold, 0)} ms</td><td>{f(get(m, 'turn', 'rest_ms'), 0)} ms</td>"
                f"<td>{f(get(m, 'memory', 'page_peak_mb'), 0)} MB</td>"
                f"<td>{'passes' if v['passes'] else 'misses: ' + ', '.join(k for k in ('frames', 'hold', 'look') if not v[k])}</td></tr>")
    pictures = []
    for plate in plates:
        cells = []
        for name, per_plate in results.items():
            m = per_plate.get(plate)
            if not m:
                continue
            imgs = "".join(
                f'<figure><img src="{render_dir(name, plate)}/{html.escape(r)}" alt="{name}, {html.escape(plate)}, {html.escape(r)}" '
                f'loading="lazy"><figcaption>{html.escape(r[:-4])}</figcaption></figure>' for r in m.get("renders", []))
            cells.append(f"<section><h3>{name}</h3><div class=\"renders\">{imgs}</div></section>")
        pictures.append(f"<h2 id=\"{html.escape(plate)}\">{html.escape(plate)}</h2>{''.join(cells)}")
    word = "passes" if chosen["passes"] else "misses the target and is the fastest with the required look"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Layer preview trial</title>
<style>
body {{ margin: 24px 24px 48px; max-width: 76ch; background: #1a1714; color: #f1ebdf;
  font: 16px/24px "IBM Plex Sans", system-ui, sans-serif; }}
h1, h2, h3 {{ font-weight: 600; margin: 24px 0 12px; }} h1 {{ font-size: 24px; }} h2 {{ font-size: 20px; }} h3 {{ font-size: 16px; }}
p {{ margin: 0 0 12px; }} a {{ color: #e08a52; text-decoration: none; }} a:hover {{ text-decoration: underline; }}
.wide {{ overflow-x: auto; max-width: none; }}
table {{ border-collapse: collapse; }} th {{ font: 600 12px/24px "IBM Plex Mono", monospace; text-transform: uppercase;
  border-bottom: 2px solid #a89e8b; text-align: left; padding: 0 12px 0 0; }}
td {{ vertical-align: top; border-bottom: 1px solid #4a3f33; padding: 6px 12px 6px 0; white-space: nowrap; }}
.renders {{ display: flex; flex-wrap: wrap; gap: 12px; max-width: none; }}
figure {{ margin: 0; }} figure img {{ width: 320px; height: 240px; display: block; border: 1px solid #4a3f33; }}
figcaption {{ color: #a89e8b; font-size: 12px; }}
</style></head><body>
<h1>Layer preview trial</h1>
<p>Method {chosen['method']} {word}. The machine: {f(mach.get('cpus'))} processors and {f(mach.get('memory_gb'))} GB of
memory as its cgroup gives them ({html.escape(str(mach.get('arch')))}), {html.escape(str(mach.get('browser', '')))},
drawing in software ({html.escape(str(mach.get('renderer', '')))}). Frames a second are typical / worst; the hold is the
longest the main thread was held, loading, moving or coming to rest; "rest" is the time from the end of a turn until the
full look is on the screen. The builder's part of passing: {FPS_SOFTWARE} frames a second typical on both paths, no hold
over {HOLD_MS} ms, and the coarse checks of the look.</p>
<div class="wide"><table><thead><tr><th>Plate</th><th>Method</th><th>First layer</th><th>Turning</th><th>Layer bar</th>
<th>Longest hold</th><th>Rest</th><th>Page memory</th><th>Verdict</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table></div>
{''.join(pictures)}
</body></html>
"""


def previous_results(out, skip, plates):
    """The figures already in `out` of the methods not measured this time, so that the report
    still shows every method when only some are measured again."""
    found = {}
    for name in METHODS:
        if name in skip:
            continue
        for plate in plates:
            path = Path(out) / f"{name}-{plate}.json"
            if path.is_file():
                found.setdefault(name, {})[plate] = json.loads(path.read_text())
    return found


# ------------------------------------------------------------------ measuring

def process_memory(browser):
    """Each Chromium process's resident memory and high-water mark, in MB."""
    try:
        cdp = browser.new_browser_cdp_session()
        infos = cdp.send("SystemInfo.getProcessInfo")["processInfo"]
    except Exception as error:                      # an older browser without the method
        return {"error": str(error)}
    out = {}
    for info in infos:
        status = read(f"/proc/{info['id']}/status")
        fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
        rss = int(fields.get("VmRSS", "0 kB").split()[0]) / 1024
        hwm = int(fields.get("VmHWM", "0 kB").split()[0]) / 1024
        kind = info["type"].lower()
        prev = out.get(kind, {"rss_mb": 0, "peak_mb": 0})
        out[kind] = {"rss_mb": max(prev["rss_mb"], rss), "peak_mb": max(prev["peak_mb"], hwm)}
    return out


def measure(playwright, port, name, plate, steps, views, out_dir):
    browser = playwright.chromium.launch(headless=True)
    try:
        page = browser.new_page(viewport={"width": VIEW_SIZE[0] + 120, "height": VIEW_SIZE[1] + 160})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{port}/preview/{METHODS[name]}?plate={plate}&w={VIEW_SIZE[0]}&h={VIEW_SIZE[1]}")
        page.wait_for_function("window.trial && (window.trial.ready || window.trial.failed)", timeout=900_000)
        failed = page.evaluate("trial.failed || null")
        if failed:
            raise RuntimeError(f"{name} on {plate}: {failed}")
        m = page.evaluate("""() => ({ first_layer_ms: trial.first_layer_ms, full_look_ms: trial.full_look_ms,
            data_ms: trial.data_ms, stats: trial.stats, layer_count: trial.layers, decimate: trial.decimate,
            load: { longest_hold_ms: Math.max(0, ...trial.holds.map(([, d]) => d)) },
            renderer: (() => { const gl = document.createElement('canvas').getContext('webgl2');
              const e = gl && gl.getExtension('WEBGL_debug_renderer_info');
              return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : null; })() })""")
        m["method"], m["plate"], m["browser"] = name, plate, f"Chromium {browser.version}"
        m["load_average_before"] = os.getloadavg()
        m["turn"] = page.evaluate(f"trial.turn({steps})")
        m["layers"] = page.evaluate(f"trial.dragLayers({steps})")
        m["load_average_after"] = os.getloadavg()
        memory = process_memory(browser)
        memory.update(page.evaluate("trial.memory()"))
        peaks = [memory.get(kind, {}).get("peak_mb", 0) for kind in ("renderer", "gpu")]
        memory["page_peak_mb"] = sum(peaks)
        m["memory"] = memory
        layers = m["layer_count"]
        mid = max(1, layers // 2)
        top_look = page.evaluate("trial.look()")
        page.evaluate(f"trial.setLayer({mid})")
        mid_look = page.evaluate("trial.look()")
        present = [g for g, n in enumerate(m["stats"]["groups"]) if n > 0]
        seen = [g for g in present if max(top_look["groups"][g], mid_look["groups"][g]) >= GROUP_SHOWN]
        changes = page.evaluate(f"trial.lookChanges({layers}, {mid})")
        page.evaluate(f"trial.setLayer({layers})")
        page.evaluate("trial.loseContext()")
        after = page.evaluate("trial.look()")
        m["look"] = {"covered": top_look["covered"], "groups_top": top_look["groups"], "groups_mid_layer": mid_look["groups"],
                     "groups_present": len(present), "groups_seen": len(seen),
                     "changes_with_layer": changes, "draws_after_context_lost": after["covered"] >= COVERED,
                     "context_lost": page.evaluate("trial.contextLost || 0")}
        renders = []
        folder = out_dir / name / plate
        folder.mkdir(parents=True, exist_ok=True)
        canvas = page.locator("#view")

        def shot(label):
            canvas.screenshot(path=str(folder / f"{label}.png"))
            renders.append(f"{label}.png")

        for view in views:
            page.evaluate(f"trial.setView('{view}')")
            shot(view)
        page.evaluate("trial.setView('default')")
        page.evaluate(f"trial.setLayer({mid})")
        shot(f"default-layer-{mid}")
        if "zoom" in views:
            page.evaluate("trial.setView('zoom')")
            shot(f"zoom-layer-{mid}")
            page.evaluate("trial.setView('default')")
        page.evaluate(f"trial.setLayer({layers})")
        page.evaluate("trial.showMoving()")
        shot("default-moving")
        page.evaluate("trial.stopMoving()")
        m["renders"] = renders
        m["errors"] = errors + page.evaluate("trial.errors")
        m["verdict"] = verdict(m)
        return m
    finally:
        browser.close()


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--methods", default=",".join(METHODS))
    parser.add_argument("--plates", default=",".join(PLATES))
    parser.add_argument("--steps", type=int, default=60, help="frames in each path")
    parser.add_argument("--all-views", default="C", help="the methods rendered at every view; the others at the default view")
    parser.add_argument("--out", default=str(RESULTS))
    args = parser.parse_args(argv)
    methods, plates = args.methods.split(","), args.plates.split(",")
    for plate in plates:
        if not (SLICED / f"{plate}.gcode.3mf").is_file():
            print(f"{SLICED / (plate + '.gcode.3mf')} is missing: make the sliced files first, as "
                  "wizard/trials/preview/README.md says.", file=sys.stderr)
            return 2
    sys.path.insert(0, str(TRIALS))
    import serve
    from playwright.sync_api import sync_playwright

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    httpd = serve.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    results = {}
    mach = machine()
    try:
        with sync_playwright() as playwright:
            for name in methods:
                for plate in plates:
                    print(f"{name} on {plate}…", file=sys.stderr, flush=True)
                    views = VIEWS if name in args.all_views.split(",") else ["default"]
                    m = measure(playwright, httpd.server_address[1], name, plate, args.steps, views, out)
                    m["machine"] = mach
                    results.setdefault(name, {})[plate] = m
                    (out / f"{name}-{plate}.json").write_text(json.dumps(m, indent=1) + "\n")
                    v = m["verdict"]
                    print(f"  turning {m['turn']['fps_typical']:.1f} fps, layer bar {m['layers']['fps_typical']:.1f} fps, "
                          f"longest hold {max(m['turn']['longest_hold_ms'], m['layers']['longest_hold_ms'], m['load']['longest_hold_ms']):.0f} ms, "
                          f"{'passes' if v['passes'] else 'misses'}", file=sys.stderr, flush=True)
                    mach.setdefault("browser", m["browser"])
                    mach.setdefault("renderer", m["renderer"])
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
    results = {name: per_plate for name, per_plate in
               sorted({**previous_results(out, methods, plates), **results}.items())}
    chosen = choose(results)
    (PREVIEW / "report.html").write_text(report_html(
        results, chosen, mach, render_dir=lambda m, p: os.path.relpath(out / m / p, PREVIEW)))
    (out / "chosen.json").write_text(json.dumps(chosen) + "\n")
    print(f"Method {chosen['method']} {'passes' if chosen['passes'] else 'misses the target'}; "
          f"{PREVIEW / 'report.html'} shows the figures and the renders.", file=sys.stderr)
    return 0 if chosen["passes"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
