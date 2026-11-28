#!/usr/bin/env python3
"""The look of the Layout step beside the mockup's: pictures of the whole panel of the mockup
(docs/mockups/print-wizard, version 8, standalone) and of the built page (wizard/dist/, served by
the fake front server) at 320, 480, 520 and 680 px, in each state of the step the mockup shows:
every instance fits; one instance selected, with its patches and rotation handle; two instances
too close; an instance across the plate's edge; an instance too tall; the list of gestures open.
Written in pairs to docs/orchestration/phase-2/look/wizard-5b/, with index.html, which shows each
pair side by side.

Not a test: a person looks at the pairs. The mockup's parts are its own made-up parts; the built
page's are the contract's bracket and a box of the Gusset Plate's size, so the shapes on the plate
differ while the panel around them should not. The mockup is put in each state by its scenario
strip; the built page by the user's own moves (files chosen, a click, a drag on the plate). Each
step waits on an event, never on a duration.

Usage: make -C wizard look-layout-step (builds first).
"""
import html
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from tests_browser.conftest import DIST, Wizard  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer  # noqa: E402
from tests_browser.test_parts_step import box_stl  # noqa: E402

MOCKUP = (WIZARD.parent / "docs" / "mockups" / "print-wizard" / "index.html").as_uri()
PARTS = WIZARD.parent / "contracts" / "examples" / "parts"
OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-5b"
WIDTHS = [320, 480, 520, 680]
HEIGHT = 900
STATES = [
    ("fit", "Every instance fits: the status line green"),
    ("selected", "One instance selected: its patches, the rotation handle, the selection line and its link"),
    ("too-close", "Two instances too close: the red status line and the message with Arrange"),
    ("off-plate", "An instance across the plate's edge"),
    ("too-tall", "An instance too tall, with Auto-orient"),
    ("help", "The list of gestures, behind \"?\""),
]
FRAMES = "await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));"


def shoot(page, name):
    OUT.mkdir(parents=True, exist_ok=True)
    if name.endswith("-wizard.png"):
        # the pointer away from the panel and no focus ring left by the keys the script pressed
        page.mouse.move(1, 1)
        page.evaluate("() => { if (document.activeElement && document.activeElement.classList.contains('gl-canvas')) document.activeElement.blur(); }")
    page.locator("#wizard").screenshot(path=str(OUT / name), animations="disabled")


def show_messages(page):
    """Scrolls the panel's body so that the step's messages are in sight, as a user would."""
    page.evaluate("() => { const b = document.getElementById('wiz-body'); const e = document.getElementById('layout-errors'); "
                  "b.scrollTop = Math.max(0, e.offsetTop - b.clientHeight + e.offsetHeight + 60); }")


# ---- the mockup

def mockup_pictures(browser, width):
    page = browser.new_page(viewport={"width": max(1200, width + 700), "height": HEIGHT + 200})
    page.goto(MOCKUP)
    page.wait_for_selector("#stepbar li.active")
    page.select_option("#sc-context", "standalone")
    page.wait_for_selector("#sa-slot #wizard")
    page.evaluate("w => { document.documentElement.style.setProperty('--panel-width', w + 'px'); window.Wizard.resize(); }", width)
    page.wait_for_function("w => document.getElementById('wizard').getBoundingClientRect().width === w", arg=width)
    for count, name in enumerate(["L Bracket.stl", "Gusset Plate.stl"], start=1):
        page.evaluate("n => window.__mockUpload(n)", name)
        page.wait_for_function("c => document.querySelectorAll('#parts-list .part-item:not(.arriving)').length === c", arg=count)
    page.click("#stepbar li[data-step=layout]")
    page.wait_for_selector("section.step[data-step=layout]:not([hidden]) #layout-view canvas")
    page.evaluate(f"async () => {{ {FRAMES} {FRAMES} }}")
    page.mouse.move(5, HEIGHT + 150)
    shoot(page, f"{width}-fit-mockup.png")

    at = page.evaluate("() => document.getElementById('layout-view').__screenOf('c3')")
    page.mouse.click(at["x"], at["y"])
    page.wait_for_function("() => document.getElementById('layout-view').__patches().length > 0")
    page.evaluate(f"async () => {{ {FRAMES} }}")
    page.mouse.move(5, HEIGHT + 150)
    shoot(page, f"{width}-selected-mockup.png")
    page.keyboard.press("Escape")

    for state in ["too_close", "off_plate", "too_tall"]:
        page.select_option("#sc-error", state)
        page.click("#sc-arm")            # on the Layout step the mockup applies it at once
        page.wait_for_selector("#layout-errors .msg.error")
        page.evaluate(f"async () => {{ {FRAMES} {FRAMES} }}")
        page.mouse.move(5, HEIGHT + 150)
        show_messages(page)
        shoot(page, f"{width}-{state.replace('_', '-')}-mockup.png")
        page.click("#layout-errors .msg.error .acts .btn")
        page.wait_for_function("() => !document.querySelector('#layout-errors .msg.error')")
        page.evaluate("() => { document.getElementById('wiz-body').scrollTop = 0; }")

    page.click("#btn-layout-help")
    page.wait_for_selector("#layout-help:not([hidden])")
    shoot(page, f"{width}-help-mockup.png")
    page.close()


# ---- the built page

def wizard_pictures(browser, server, width):
    page = browser.new_page()
    w = Wizard(page, server, width=width, height=HEIGHT, fake_clock=False)
    w.run("wizard.store.set({configName: '6238 (Popcorn Penguins)'});")
    w.page.check("#upload-units input[value=mm]")
    gusset = box_stl(b"gusset", (50.8, 50.8, 6.35))
    w.page.set_input_files("#f-upload", [
        {"name": "L Bracket.stl", "mimeType": "application/octet-stream", "buffer": (PARTS / "bracket.stl").read_bytes()},
        {"name": "Gusset Plate.stl", "mimeType": "application/octet-stream", "buffer": gusset},
    ])
    w.until("return wizard.parts.rows().length === 2 && wizard.parts.rows().every((r) => !r.arriving && r.drawn);")
    w.page.click("#stepbar li[data-step=layout]")

    def settle():
        w.until("return (async () => { await wizard.layout.idle(); return true; })();")
        w.run(f"await wizard.layout.idle(); wizard.layoutStep.view().invalidate(); {FRAMES} {FRAMES}")

    w.until("return wizard.layoutStep.view() && wizard.layout.model().instances.length === 2 && wizard.layout.model().instances.every((i) => i.bounds);")
    settle()
    page.mouse.move(1, 1)
    shoot(page, f"{width}-fit-wizard.png")

    first = w.run("return wizard.layout.model().instances[0];")
    at = w.run("return wizard.layoutStep.view().plateAt(arg[0], arg[1]);", [first["x"], first["y"]])
    page.mouse.click(at["x"], at["y"])
    w.until("return wizard.layoutStep.view().patchesInSight().length > 0;")
    settle()
    page.mouse.move(1, 1)
    shoot(page, f"{width}-selected-wizard.png")
    page.keyboard.press("Escape")

    # the second instance dragged to 2 mm behind the first
    w.run("const [a, b] = wizard.layout.model().instances; const ad = a.bounds[3] - a.bounds[1], bd = b.bounds[3] - b.bounds[1]; "
          "wizard.layout.place([{ id: b.id, x: a.x, y: a.y + ad / 2 + bd / 2 + 2 }]); await wizard.layout.endDrag();")
    settle()
    w.page.wait_for_selector("#layout-errors .msg.error")
    show_messages(page)
    shoot(page, f"{width}-too-close-wizard.png")
    w.page.click("#layout-errors .msg.error .acts .btn")
    w.until("return !document.querySelector('#layout-errors .msg.error');")
    w.run("document.getElementById('wiz-body').scrollTop = 0;")

    a = w.run("return wizard.layout.model().instances[1];")
    w.run("wizard.layout.place([{ id: arg.id, x: 12, y: arg.y }]); await wizard.layout.endDrag();", a)
    settle()
    w.page.wait_for_selector("#layout-errors .msg.error")
    show_messages(page)
    shoot(page, f"{width}-off-plate-wizard.png")
    w.page.click("#layout-errors .msg.error .acts .btn")
    w.until("return !document.querySelector('#layout-errors .msg.error');")
    w.run("document.getElementById('wiz-body').scrollTop = 0;")

    # a rib standing on its end: 353 mm tall
    w.page.click("#stepbar li[data-step=parts]")
    w.page.set_input_files("#f-upload", [{"name": "Shooter Hood Rib.stl", "mimeType": "application/octet-stream", "buffer": box_stl(b"rib", (10.0, 12.0, 353.0))}])
    w.until("return wizard.parts.rows().length === 3 && wizard.parts.rows().every((r) => !r.arriving && r.drawn);")
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.layout.model().instances.length === 3 && wizard.layout.model().instances.every((i) => i.bounds);")
    settle()
    rib = w.run("return wizard.layout.model().instances[2];")
    w.run("wizard.layout.select(arg, 'only'); await wizard.layout.model().link.run();", rib["id"])
    settle()
    w.run("wizard.layout.select(null, 'none');")
    w.page.wait_for_selector("#layout-errors .msg.error")
    settle()
    show_messages(page)
    page.mouse.move(1, 1)
    shoot(page, f"{width}-too-tall-wizard.png")
    w.page.click("#layout-errors .msg.error .acts .btn")
    w.until("return !document.querySelector('#layout-errors .msg.error');")
    w.run("document.getElementById('wiz-body').scrollTop = 0;")
    settle()

    w.page.click("#btn-layout-help")
    shoot(page, f"{width}-help-wizard.png")
    page.close()


def write_index():
    rows = []
    for width in WIDTHS:
        rows.append(f"<h2>{width} px</h2>")
        for state, says in STATES:
            mock = f"{width}-{state}-mockup.png"
            mine = f"{width}-{state}-wizard.png"
            left = f'<img src="{mock}" alt="the mockup">' if (OUT / mock).exists() else "<p>The mockup has none.</p>"
            rows.append(f'<h3>{html.escape(says)}</h3><div class="pair"><figure>{left}<figcaption>Mockup, version 8</figcaption></figure>'
                        f'<figure><img src="{mine}" alt="the wizard"><figcaption>The wizard, as built</figcaption></figure></div>')
    (OUT / "index.html").write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>The Layout step beside the mockup</title>"
        "<style>body{margin:24px;font:14px/1.45 system-ui,sans-serif;background:#fff;color:#1f2328}"
        ".pair{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}figure{margin:0}"
        "img{border:1px solid #d0d7de;display:block}figcaption{color:#5a6570;font-size:12px;margin-top:4px}"
        "h3{font-size:14px;margin:24px 0 8px}</style></head><body>"
        "<h1>The Layout step beside the mockup</h1>"
        "<p>Each pair is the mockup's whole panel (left) and the built page's (right) at the same width, in the same state. "
        "The parts on the plate differ: the mockup's are its own made-up parts. The frame rate at 150 instances is in "
        "<a href=\"frame-rate.json\">frame-rate.json</a>. Made by <code>make -C wizard look-layout-step</code>.</p>"
        + "".join(rows) + "</body></html>",
        encoding="utf-8")


def main():
    with sync_playwright() as playwright, FakeFrontServer(DIST) as server:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                mockup_pictures(browser, width)
                wizard_pictures(browser, server, width)
                print(f"look-layout-step: {width} px done")
        finally:
            browser.close()
    write_index()
    print(f"look-layout-step: wrote {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
