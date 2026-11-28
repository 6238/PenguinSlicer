#!/usr/bin/env python3
"""The picture of each kept part as its row on the Parts step will show it: the real parts of
contracts/examples/parts/real/ and the trials' made parts of wizard/trials/parts/, each read and
drawn by the built page's own worker in Chromium, at the row's 44 px at twice the density (88
pixels), in the first of the parts' colours, written as PNG files to
docs/orchestration/phase-2/look/wizard-3/.

Not a test: a person looks at the pictures. It also prints, for each part, the longest hold of
the main thread while the part was read and its picture drawn and put on the page, measured by
the page's own heartbeat on the real clock; the figure the details file gives is the largest of
these. Each step waits on an event (the worker's answer), never on a duration.

Usage: make -C wizard look-parts (builds first).
"""
import base64
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from tests_browser.conftest import DIST, main_module  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer  # noqa: E402

OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-3"
PARTS = sorted((WIZARD.parent / "contracts" / "examples" / "parts" / "real").glob("*.stl")) + \
    sorted((WIZARD / "trials" / "parts").glob("*.stl"))

DRAW = """
    const bytes = await (await fetch('/look-parts/' + arg.name)).arrayBuffer();
    const { partPicture, partColour } = await import(arg.picture);
    wizard.holdMeter.start();
    const read = await wizard.geometry.read(arg.name, bytes, 'mm');
    let picture = null;
    if (read.ok) {
        picture = await partPicture({ geometry: wizard.geometry, key: arg.name, colour: partColour(0), pixelRatio: 2, document });
        if (picture.ok) document.body.append(picture.canvas);
    }
    const held = wizard.holdMeter.stop();
    if (!picture || !picture.ok) return { held, error: read.ok ? picture.error : read.error };
    return { held, png: picture.canvas.toDataURL('image/png') };
"""


def picture_module():
    (found,) = (DIST / "assets").glob("part-picture.????????????.js")
    return f"/assets/{found.name}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    longest = 0
    failed = False
    with sync_playwright() as playwright, FakeFrontServer(DIST) as server:
        for path in PARTS:
            server.files[f"/look-parts/{path.name}"] = path.read_bytes()
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(server.url)
            page.wait_for_selector('html[data-opened="true"]', state="attached")
            for path in PARTS:
                result = page.evaluate(
                    f"async ([url, arg]) => {{ const {{ wizard }} = await import(url); return (async (wizard, arg) => {{ {DRAW} }})(wizard, arg); }}",
                    [main_module(), {"name": path.name, "picture": picture_module()}])
                if "error" in result:
                    print(f"look-parts: {path.name}: {result['error']['code']}", file=sys.stderr)
                    failed = True
                    continue
                png = base64.b64decode(result["png"].split(",", 1)[1])
                (OUT / f"{path.stem}.png").write_bytes(png)
                longest = max(longest, result["held"])
                print(f"look-parts: {path.name}: main thread held at most {result['held']} ms")
        finally:
            browser.close()
    print(f"look-parts: wrote {len(PARTS)} pictures to {OUT}; the longest hold was {longest} ms")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
