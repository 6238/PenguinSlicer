#!/usr/bin/env python3
"""Laying on a face, auto-orient and Arrange on real exported parts: the second trial of phase 2.

`make -C wizard trials-geometry` runs this file. It starts the trials' server on a port the
system chooses, opens wizard/trials/geometry/index.html in Playwright's Chromium (headless; the
geometry draws nothing, so no graphics card is involved), and through that page drives the
wizard's own worker, wizard/src/geometry.worker.js:

- for each of the eight real parts and the two made parts: the hull faces and patches found
  and the way auto-orient lays the part, written to results/<part>.json, and one picture of the
  part as modelled and as laid, with its patches drawn, in pictures/<part>.png;
- the four times of wizard/README-details.md, "How the trials and measurements are run":
  the patches of hub-150k.stl after selecting it (PATCHES_MS), its auto-orient after it arrives
  (AUTO_ORIENT_MS), Arrange of 150 instances of hex-spacer.stl and of a mix of the real parts
  (ARRANGE_MS), and each placement check of a drag at 150 instances (one frame at 10 a second);
- the machine's processors and memory as its cgroup gives them, in results/summary.json.

It exits 1, naming each, when a time is missed or a real part has a flat face with no hull
patch; the results are written either way.
"""
import base64
import json
import os
import platform
import posixpath
import sys
import threading
from functools import partial
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
TRIALS = HERE.parent
WIZARD = TRIALS.parent
sys.path.insert(0, str(TRIALS))
import serve  # noqa: E402  (the trials' server, beside this folder)

RESULTS = HERE / "results"
PICTURES = HERE / "pictures"
SRC = WIZARD / "src"

PATCHES_MS = 100
AUTO_ORIENT_MS = 1000
ARRANGE_MS = 2000
DRAG_CHECK_MS = 100
# The default set of profiles' printer, the Bambu Lab H2S: its printable area and height.
H2S = {"min": [0, 0], "max": [340, 320], "height": 340}

REAL = [
    ("clamp-plate-inner", "Clamp Plate Inner"),
    ("elevator-block-bottom-inner", "Elevator Block Bottom Inner"),
    ("elevator-block-carriage", "Elevator Block Carriage"),
    ("elevator-block-top", "Elevator Block Top"),
    ("elevator-top-inner", "Elevator Top Inner"),
    ("inner-spacer", "Inner Spacer"),
    ("outer-clamp", "Outer Clamp"),
    ("pulley-v3", "Pulley v3"),
]
MADE = [("hub-150k", "Hub 150k"), ("hex-spacer", "Hex Spacer")]
# The mix of real parts for Arrange at 150 instances: every real part, the large ones once or
# twice and the one small part, the pulley, for the rest, so that the plate is nearly full.
MIX = {"clamp-plate-inner": 2, "elevator-block-bottom-inner": 1, "elevator-block-carriage": 1,
       "elevator-block-top": 1, "elevator-top-inner": 1, "inner-spacer": 2, "outer-clamp": 2,
       "pulley-v3": 140}


class GeometryTrialHandler(serve.TrialsHandler):
    """The trials' server, with the wizard's own modules at /src/ so that the page runs the real
    worker. The same guards as the trials' server: no '..', no NUL, no symbolic link out."""

    def translate_path(self, path):
        clean = unquote(urlsplit(path).path)
        if clean.startswith("/src/"):
            if "\0" in clean or any(part == ".." for part in clean.split("/")):
                return serve.NOWHERE
            target = (SRC / posixpath.normpath(clean[len("/src/"):])).resolve()
            if not target.is_relative_to(SRC.resolve()):
                return serve.NOWHERE
            return str(target)
        return super().translate_path(path)

    def log_message(self, format, *args):  # noqa: A002  (the name the base class gives it)
        pass


def make_server():
    httpd = serve.make_server("127.0.0.1", 0)
    httpd.RequestHandlerClass = partial(GeometryTrialHandler, directory=str(TRIALS))
    return httpd


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def machine(browser_version, page_machine):
    """The machine's processors and memory as its cgroup gives them, and what the VM reports."""
    cpu_max = read_text("/sys/fs/cgroup/cpu.max")
    memory_max = read_text("/sys/fs/cgroup/memory.max")
    processors = None
    if cpu_max and cpu_max.split()[0] != "max":
        quota, period = cpu_max.split()
        processors = int(quota) / int(period)
    memory_gib = int(memory_max) / 2**30 if memory_max and memory_max != "max" else None
    return {
        "architecture": platform.machine(), "system": platform.system(),
        "cgroup_cpu_max": cpu_max, "cgroup_processors": processors,
        "cgroup_memory_max": memory_max, "cgroup_memory_gib": memory_gib,
        "processors_the_vm_reports": os.cpu_count(), "chromium": browser_version,
        "browser_hardware_concurrency": page_machine["hardwareConcurrency"],
        "graphics": "none: Chromium headless, the geometry draws nothing",
    }


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    from playwright.sync_api import sync_playwright

    RESULTS.mkdir(exist_ok=True)
    PICTURES.mkdir(exist_ok=True)
    httpd = make_server()
    host, port = httpd.server_address[:2]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"
    missed = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"{base}/geometry/index.html")
            page.wait_for_function("document.documentElement.dataset.ready === 'true'")
            parts = {}
            for key, name in REAL + MADE:
                url = f"/parts/real/{key}.stl" if (key, name) in REAL else f"/parts/{key}.stl"
                result = page.evaluate("spec => window.trial.part(spec)", {"url": url, "key": key, "name": name})
                picture = result.pop("picture")
                (PICTURES / f"{key}.png").write_bytes(base64.b64decode(picture.split(",", 1)[1]))
                write_json(RESULTS / f"{key}.json", result)
                parts[key] = result
                t = result["timing"]
                print(f"{name}: {len(result['faces']['patches'])} patches, "
                      f"arrival {t['arrivalToBestWayMs']['worst']:.0f} ms, "
                      f"selecting {t['selectingToPatchesMs']['worst']:.1f} ms", flush=True)

            spacers = page.evaluate("spec => window.trial.arrange(spec)", {
                "parts": [{"url": "/parts/hex-spacer.stl", "key": "hex-spacer", "name": "Hex Spacer", "count": 150}],
                "printer": H2S})
            spacer_drag = page.evaluate("spec => window.trial.drag(spec)", {
                "plateConfiguration": spacers["plateConfiguration"],
                "parts": [{"key": "hex-spacer"}], "printer": H2S})
            mix_parts = [{"url": f"/parts/real/{k}.stl", "key": k, "name": dict(REAL)[k], "count": c} for k, c in MIX.items()]
            mix = page.evaluate("spec => window.trial.arrange(spec)", {"parts": mix_parts, "printer": H2S})
            mix_drag = page.evaluate("spec => window.trial.drag(spec)", {
                "plateConfiguration": mix["plateConfiguration"], "parts": mix_parts, "printer": H2S})
            for name, arranged, dragged in (("arrange-spacers-150", spacers, spacer_drag), ("arrange-mix-150", mix, mix_drag)):
                picture = arranged.pop("picture")
                (PICTURES / f"{name}.png").write_bytes(base64.b64decode(picture.split(",", 1)[1]))
                write_json(RESULTS / f"{name}.json", {**arranged, "drag": dragged})
            held = page.evaluate("window.trial.heldWhileTimed()")
            held_any = page.evaluate("window.trial.longestAnyMs()")
            page_machine = page.evaluate("window.trial.machine()")
            version = browser.version
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()

    hub = parts["hub-150k"]["timing"]
    targets = [
        ("patches of hub-150k.stl after selecting it", hub["selectingToPatchesMs"]["worst"], PATCHES_MS),
        ("auto-orient of hub-150k.stl after it arrives", hub["arrivalToBestWayMs"]["worst"], AUTO_ORIENT_MS),
        ("Arrange of 150 hex-spacer.stl", spacers["arrangeMs"]["worst"], ARRANGE_MS),
        ("Arrange of a mix of 150 real parts", mix["arrangeMs"]["worst"], ARRANGE_MS),
        ("placement check of a drag at 150 hex-spacer.stl", spacer_drag["checkMs"]["worst"], DRAG_CHECK_MS),
        ("placement check of a drag at 150 of the mix", mix_drag["checkMs"]["worst"], DRAG_CHECK_MS),
    ]
    times = [{"what": what, "worst_ms": round(ms, 2), "target_ms": target, "met": ms <= target}
             for what, ms, target in targets]
    for t in times:
        if not t["met"]:
            missed.append(f"{t['what']}: {t['worst_ms']} ms, the target {t['target_ms']} ms")
    flat = {}
    for key, _ in REAL:
        without = [f for f in parts[key]["flatFaces"] if not f["patch"]]
        flat[key] = {"flat_faces": len(parts[key]["flatFaces"]), "without_hull_patch": without}
        for f in without:
            missed.append(f"{key}: a flat face of {f['area']} mm² facing {f['normal']} has no hull patch "
                          f"(dropped: {f['dropped']}; a bounding-box patch lays it that way: {f['coveredByBoxPatch']})")
    summary = {
        "machine": machine(version, page_machine),
        "times": times,
        "flat_faces": flat,
        "patches": {key: {"hull": sum(1 for q in parts[key]["faces"]["patches"] if q["kind"] == "hull"),
                          "box": [q["side"] for q in parts[key]["faces"]["patches"] if q["kind"] == "box"],
                          "laid_on": parts[key]["orient"]["patch"],
                          "height_mm": round(parts[key]["orient"]["height"], 2)}
                    for key in parts},
        "arrange": {"spacers-150": {"placed": spacers["placed"], "packer": spacers["packer"]},
                    "mix-150": {"placed": mix["placed"], "packer": mix["packer"]}},
        "main_thread_held_while_timed": held,
        "main_thread_held_by_the_trial_page_itself_ms": held_any,
        "main_thread_note": "For each timed step: the longest gap between beats of a 10 ms heartbeat on the main "
                            "thread (how long the page could not answer while the worker worked) and the longest "
                            "long task the browser reported in the same time. On hub-150k the browser reports a "
                            "long task of about a second that no heartbeat gap and no answer's time shows, so the "
                            "heartbeat is the figure that counts. The second figure includes the trial page's own "
                            "drawing of its pictures and its untimed counts on the main thread, which the wizard "
                            "does not do.",
        "page_errors": errors,
        "round_parts": "The round parts exported from Onshape at its coarse and fine settings can only come "
                       "from the owner; until they arrive the trial's round parts are pulley-v3.stl and "
                       "inner-spacer.stl, as wizard/README-details.md says.",
        "missed": missed,
    }
    write_json(RESULTS / "summary.json", summary)
    for t in times:
        print(f"{'met   ' if t['met'] else 'MISSED'} {t['what']}: {t['worst_ms']} ms (target {t['target_ms']} ms)")
    if errors:
        missed.append(f"the page reported errors: {errors}")
    for m in missed:
        print(f"missed: {m}", file=sys.stderr)
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
