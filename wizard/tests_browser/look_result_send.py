#!/usr/bin/env python3
"""The look of the Preview step's result and of the Send step beside the mockup's: pictures of the
whole panel of the mockup (docs/mockups/print-wizard, version 8, standalone) and of the built page
(wizard/dist/, served by the fake front server) at 320, 480, 520 and 680 px, in each state the
mockup shows: the result with the layer preview at its top layer; the colour key open; the "?"
open; the Send step; the Send step after Download; the Send step with no printer paired (the
mockup's nearest to phase 2's Send step, which has no printer). Then the states the mockup never
drew, the built page's alone: the expired message on the Preview step and on the Send step, the
result with warnings, and a sliced file the preview cannot read. Written in pairs to
docs/orchestration/phase-2/look/wizard-8/, with index.html, which shows each pair side by side.

Not a test: a person looks at the pairs. The built page draws a real sliced file (an Elevator
Block Top and an Elevator Block Carriage, supports on, wizard/tests/sliced/pair-supports) of the
same two real parts, which the mockup's own fake slice of its own parts cannot be; so the toolpaths
and the figures differ while the look should not. Both pages run on Playwright's fake clock, moved
by the script; every wait is for an event.

Usage: make -C wizard look-result-send (builds first).
"""
import html
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from tests_browser.conftest import DIST, Wizard  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer, error_report, example, progress_event, stream, version_event  # noqa: E402
from tests_browser.look_preview_step import mockup_page, mockup_to_preview, run_until  # noqa: E402

REAL = WIZARD.parent / "contracts" / "examples" / "parts" / "real"
SLICED = WIZARD / "tests" / "sliced"
OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-8"
WIDTHS = [320, 480, 520, 680]
HEIGHT = 900
JOB = "3f9a1c2b"
STATES = [
    ("result", "The result: print time and filament, the quiet line, the layer preview at its top layer, the readout and its buttons"),
    ("key", "The colour key open"),
    ("help", "The \"?\" open: how to move the view"),
    ("send", "The Send step: what will be printed, and the one button (the mockup's with a printer paired)"),
    ("send-unpaired", "The Send step beside the mockup's with no printer paired, its nearest to phase 2's"),
    ("download", "After Download: the notification of the plate and the file's size"),
    ("expired-preview", "The expired message in place of the result (the mockup never drew it)"),
    ("expired-send", "The expired message in place of Send (the mockup never drew it)"),
    ("warnings", "The result with the slice service's warnings in amber (the mockup never drew it)"),
    ("unreadable", "A sliced file the preview cannot read: the amber message in place of the view (the mockup never drew it)"),
]


def shoot(page, name):
    OUT.mkdir(parents=True, exist_ok=True)
    page.mouse.move(1, 1)
    page.locator("#wizard").screenshot(path=str(OUT / name), animations="disabled")


# ---- the mockup

def mockup_sliced(browser, width, printer=None):
    page = mockup_page(browser, width)
    if printer:
        page.select_option("#sc-printer", printer)
    mockup_to_preview(page)
    run_until(page, "!document.getElementById('preview-result').hidden", step=200)
    page.clock.run_for(3000)                   # its viewer draws on animation frames
    return page


def mockup_pictures(browser, width):
    page = mockup_sliced(browser, width)
    shoot(page, f"{width}-result-mockup.png")
    page.click("#btn-key")
    page.clock.run_for(200)
    shoot(page, f"{width}-key-mockup.png")
    page.keyboard.press("Escape")
    page.click("#btn-preview-help")
    page.clock.run_for(200)
    shoot(page, f"{width}-help-mockup.png")
    page.mouse.click(2, 2)
    page.click("#btn-next")
    page.clock.run_for(500)
    shoot(page, f"{width}-send-mockup.png")
    page.click("#btn-do-caret")
    page.click("#do-menu [data-action=download]")
    page.click("#btn-do")
    page.clock.run_for(300)
    shoot(page, f"{width}-download-mockup.png")
    page.close()

    page = mockup_sliced(browser, width, printer="unpaired")
    page.click("#btn-next")
    page.clock.run_for(500)
    shoot(page, f"{width}-send-unpaired-mockup.png")
    page.close()


# ---- the built page

def done(**details):
    summary = json.loads((SLICED / "pair-supports.summary.json").read_text(encoding="utf-8"))
    sliced = {**example("wizard-front/slice-summary.json")["sliced_file"], "file": summary["file"],
              "size_bytes": (SLICED / "pair-supports.gcode.3mf").stat().st_size, "summary": summary}
    base = example("wizard-front/slice-done.json")["progress"]
    return {**base, "elapsed_s": 41.3, "sliced_file": {**sliced, **details}}


def wizard_sliced(browser, server, width, file=None, **details):
    """The built page with the two real parts on the plate, laid out, sliced, on the Preview step,
    its layer preview drawn and at rest."""
    server.script("GET", f"/api/slices/{JOB}/events", stream(version_event(server.version), progress_event(done(**details))))
    server.script("GET", f"/api/slices/{JOB}/file", (200, file if file is not None else (SLICED / "pair-supports.gcode.3mf").read_bytes()))
    page = browser.new_page()
    w = Wizard(page, server, width=width, height=HEIGHT)
    w.run("wizard.store.set({configName: '6238 (Popcorn Penguins)'});")
    w.page.check("#upload-units input[value=mm]")
    w.page.set_input_files("#f-upload", [
        {"name": f"{name}.stl", "mimeType": "application/octet-stream", "buffer": (REAL / f"{ref}.stl").read_bytes()}
        for ref, name in (("elevator-block-top", "Elevator Block Top"), ("elevator-block-carriage", "Elevator Block Carriage"))])
    w.until("return wizard.parts.rows().length === 2 && wizard.parts.rows().every((r) => !r.arriving && r.drawn);")
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.layout.model().instances.length === 2 && wizard.layout.model().instances.every((i) => i.bounds) && wizard.layout.model().status.ok;")
    w.run("await wizard.layout.idle();")
    w.page.click("#stepbar li[data-step=preview]")
    w.until("return wizard.slicing.model().kind === 'done';")
    if file is not None:
        for _ in range(400):
            if w.run("return Boolean(document.querySelector('.preview-view-message .msg'));"):
                return w
            w.page.clock.run_for(50)
        raise AssertionError("the preview never failed")
    for _ in range(1200):
        if w.run("const v = wizard.previewStep.view(); return Boolean(v && !document.getElementById('btn-layer-up').disabled && v.atRest());"):
            return w
        w.page.clock.run_for(50)
    raise AssertionError("the layer preview never came to rest")


def wizard_pictures(browser, server, width):
    w = wizard_sliced(browser, server, width)
    shoot(w.page, f"{width}-result-wizard.png")
    w.page.click("#btn-key")
    shoot(w.page, f"{width}-key-wizard.png")
    w.page.keyboard.press("Escape")
    w.page.click("#btn-preview-help")
    shoot(w.page, f"{width}-help-wizard.png")
    w.page.mouse.click(2, 2)
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'send';")
    shoot(w.page, f"{width}-send-wizard.png")
    shoot(w.page, f"{width}-send-unpaired-wizard.png")
    server.script("GET", f"/api/slices/{JOB}/summary", (200, {"sliced_file": done()["sliced_file"]}))
    with w.page.expect_download():
        w.page.click("#btn-do")
    w.page.wait_for_selector("#notices .notice")
    shoot(w.page, f"{width}-download-wizard.png")
    w.page.close()

    # the expired message, on the Preview step and on the Send step
    w = wizard_sliced(browser, server, width, expires_in_s=600)
    w.page.clock.run_for(600_000)
    w.until("return wizard.slicing.model().kind === 'expired';")
    shoot(w.page, f"{width}-expired-preview-wizard.png")
    w.page.close()
    w = wizard_sliced(browser, server, width)
    w.page.click("#btn-next")
    w.until("return wizard.store.get().step === 'send';")
    server.script("GET", f"/api/slices/{JOB}/summary", (410, error_report(
        "front.sliced_file_expired", message="This plate's sliced file has expired: a sliced file is kept for two hours.",
        remedy="Slice the plate again to print it.")))
    w.page.click("#btn-do")
    w.until("return wizard.slicing.model().kind === 'expired';")
    shoot(w.page, f"{width}-expired-send-wizard.png")
    w.page.close()

    # warnings, and a sliced file the preview cannot read
    summary = json.loads((SLICED / "pair-supports.summary.json").read_text(encoding="utf-8"))
    summary["warnings"] = ["Floating regions on Elevator Block Carriage #1, at 12.6 mm."]
    summary["part_warnings"] = [{"code": "slice.part_not_watertight", "message": "Elevator Block Top has 4 open edges; Orca closed them.", "where": {"part": "p1"}, "detail": "x"}]
    w = wizard_sliced(browser, server, width, summary=summary)
    shoot(w.page, f"{width}-warnings-wizard.png")
    w.page.close()
    w = wizard_sliced(browser, server, width, file=b"not a sliced file")
    shoot(w.page, f"{width}-unreadable-wizard.png")
    w.page.close()


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
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>The result and the Send step beside the mockup</title>"
        "<style>body{margin:24px;font:14px/1.45 system-ui,sans-serif;background:#fff;color:#1f2328}"
        ".pair{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}figure{margin:0}"
        "img{border:1px solid #d0d7de;display:block}figcaption{color:#5a6570;font-size:12px;margin-top:4px}"
        "h3{font-size:14px;margin:24px 0 8px}</style></head><body>"
        "<h1>The result and the Send step beside the mockup</h1>"
        "<p>Each pair is the mockup's whole panel (left) and the built page's (right) at the same width, in the same state. "
        "The built page draws a real sliced file of two real parts; the mockup draws its own fake slice of its own parts, "
        "so the toolpaths and the figures differ. Phase 2's Send step has no printer: no printer's name, no plate-clear line, "
        "no caret and no printer-status icon. Made by <code>make -C wizard look-result-send</code>.</p>"
        + "".join(rows) + "</body></html>",
        encoding="utf-8")


def main():
    with sync_playwright() as playwright, FakeFrontServer(DIST) as server:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                mockup_pictures(browser, width)
                wizard_pictures(browser, server, width)
                print(f"look-result-send: {width} px done")
        finally:
            browser.close()
    write_index()
    print(f"look-result-send: wrote {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
