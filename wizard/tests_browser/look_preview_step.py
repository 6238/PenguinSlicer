#!/usr/bin/env python3
"""The look of the Preview step's slicing card and failures beside the mockup's: pictures of the
whole panel of the mockup (docs/mockups/print-wizard, version 8, standalone) and of the built page
(wizard/dist/, served by the fake front server) at 320, 480, 520 and 680 px, in each state of the
step the mockup shows: slicing; the connection lost (no news); reconnected; empty layers with
supports off, Details folded and opened; empty layers with supports on (the mockup's faulty mesh);
too slow. Then the states the mockup never drew, the built page's alone: waiting behind others,
waiting while the slicer restarts, the slicer restarted, no room to wait, and an instance resting
on an edge. Written in pairs to docs/orchestration/phase-2/look/wizard-6/, with index.html, which
shows each pair side by side.

Not a test: a person looks at the pairs. The mockup's sentences of a failure are its own made-up
ones; the built page shows the slice service's, from the contracts' examples and the slice
service's own sentences, so the words of a failure differ while its look should not. Both pages run
on Playwright's fake clock, moved by the script; every wait is for an event.

Usage: make -C wizard look-preview-step (builds first).
"""
import datetime
import html
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from tests_browser.conftest import DIST, START, Wizard  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer, error_report, example, progress_event, stream, version_event  # noqa: E402
from tests_browser.test_parts_step import box_stl  # noqa: E402

MOCKUP = (WIZARD.parent / "docs" / "mockups" / "print-wizard" / "index.html").as_uri()
PARTS = WIZARD.parent / "contracts" / "examples" / "parts"
OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-6"
WIDTHS = [320, 480, 520, 680]
HEIGHT = 900
JOB = "3f9a1c2b"
EVENTS = f"/api/slices/{JOB}/events"
STATES = [
    ("slicing", "Slicing: the ring, the stage, the times, the bar and the stages"),
    ("no-news", "The connection lost: the figures stop and the time-left line says there is no news"),
    ("reconnected", "Reconnected: the line on the card"),
    ("empty-layers", "Empty layers, supports off: Turn on Supports and slice again, Back to Layout, Details folded"),
    ("empty-layers-details", "The same with Details opened: Orca's own sentence"),
    ("empty-layers-supports", "Empty layers with supports on (the mockup's faulty mesh): Back to Parts"),
    ("timeout", "Too slow: Slice again, Back to Parts"),
    ("waiting", "Waiting behind other slices (the mockup never drew it)"),
    ("restarting", "Waiting while the slicer restarts (the mockup never drew it)"),
    ("restarted", "The slicer restarted, so the slice began again (the mockup never drew it)"),
    ("busy", "No room to wait: the amber message (the mockup never drew it)"),
    ("rests-on-an-edge", "An instance resting on an edge: Back to Layout only (the mockup never drew it)"),
]


def shoot(page, name):
    OUT.mkdir(parents=True, exist_ok=True)
    page.mouse.move(1, 1)
    page.locator("#wizard").screenshot(path=str(OUT / name), animations="disabled")


# ---- the mockup

def mockup_page(browser, width):
    page = browser.new_page(viewport={"width": max(1200, width + 700), "height": HEIGHT + 200})
    page.add_init_script("Math.random = () => 0.5;")
    page.clock.install(time=START)
    page.goto(MOCKUP)
    page.wait_for_selector("#stepbar li.active")
    page.clock.pause_at(START + datetime.timedelta(minutes=10))
    page.select_option("#sc-context", "standalone")
    page.wait_for_selector("#sa-slot #wizard")
    page.evaluate("w => { document.documentElement.style.setProperty('--panel-width', w + 'px'); window.Wizard.resize(); }", width)
    page.wait_for_function("w => document.getElementById('wizard').getBoundingClientRect().width === w", arg=width)
    for count, name in enumerate(["L Bracket.stl", "Gusset Plate.stl"], start=1):
        page.evaluate("n => window.__mockUpload(n)", name)
        for _ in range(200):
            if page.evaluate("c => document.querySelectorAll('#parts-list .part-item:not(.arriving)').length === c", count):
                break
            page.clock.run_for(100)
    return page


def run_until(page, condition, step=100, tries=4000):
    for _ in range(tries):
        if page.evaluate(f"() => Boolean({condition})"):
            return
        page.clock.run_for(step)
    raise AssertionError(f"the mockup never reached: {condition}")


def mockup_to_preview(page, arm=None, supports=False):
    if supports:
        page.click("#stepbar li[data-step=setup]")
        page.select_option("#ov-supports", index=1)
    if arm:
        page.select_option("#sc-error", arm)
        page.click("#sc-arm")
    page.click("#stepbar li[data-step=layout]")
    page.clock.run_for(500)
    page.click("#stepbar li[data-step=preview]")
    run_until(page, "!document.getElementById('slice-card').hidden || document.querySelector('#preview-errors .msg')")


def mockup_pictures(browser, width):
    page = mockup_page(browser, width)
    mockup_to_preview(page)
    run_until(page, "parseInt(document.getElementById('slice-pct').textContent) >= 40")
    shoot(page, f"{width}-slicing-mockup.png")
    page.close()

    page = mockup_page(browser, width)
    mockup_to_preview(page, arm="conn_lost")
    run_until(page, "document.getElementById('slice-card').classList.contains('stalled') && !document.getElementById('slice-conn').hidden", step=50)
    page.clock.run_for(2500)
    shoot(page, f"{width}-no-news-mockup.png")
    run_until(page, "document.getElementById('slice-conn').classList.contains('back')", step=100)
    shoot(page, f"{width}-reconnected-mockup.png")
    page.close()

    page = mockup_page(browser, width)
    mockup_to_preview(page, arm="empty_layers")
    run_until(page, "document.querySelector('#preview-errors .msg.error')")
    shoot(page, f"{width}-empty-layers-mockup.png")
    page.click("#preview-errors details summary")
    shoot(page, f"{width}-empty-layers-details-mockup.png")
    page.close()

    page = mockup_page(browser, width)
    mockup_to_preview(page, arm="faulty_mesh", supports=True)
    run_until(page, "document.querySelector('#preview-errors .msg.error')")
    shoot(page, f"{width}-empty-layers-supports-mockup.png")
    page.close()

    page = mockup_page(browser, width)
    mockup_to_preview(page, arm="timeout")
    run_until(page, "document.querySelector('#preview-errors .msg.error')", step=1000)
    shoot(page, f"{width}-timeout-mockup.png")
    page.close()


# ---- the built page

def running(**fields):
    return {"job": JOB, "state": "running", "stage": "generating_infill", "stage_label": "Generating infill",
            "fraction": 0.42, "elapsed_s": 31.5, "expected_s": 75, "sequence": 17, **fields}


def failed(error, sequence=20):
    return running(state="failed", error=error, sequence=sequence)


def wizard_page(browser, server, width):
    page = browser.new_page()
    w = Wizard(page, server, width=width, height=HEIGHT)
    w.run("wizard.store.set({configName: '6238 (Popcorn Penguins)'});")
    w.page.check("#upload-units input[value=mm]")
    gusset = box_stl(b"gusset", (50.8, 50.8, 6.35))
    w.page.set_input_files("#f-upload", [
        {"name": "L Bracket.stl", "mimeType": "application/octet-stream", "buffer": (PARTS / "bracket.stl").read_bytes()},
        {"name": "Gusset Plate.stl", "mimeType": "application/octet-stream", "buffer": gusset},
    ])
    w.until("return wizard.parts.rows().length === 2 && wizard.parts.rows().every((r) => !r.arriving && r.drawn);")
    w.page.click("#stepbar li[data-step=layout]")
    w.until("return wizard.layout.model().instances.length === 2 && wizard.layout.model().instances.every((i) => i.bounds) && wizard.layout.model().status.ok;")
    w.run("await wizard.layout.idle();")
    return w


def to_preview(w, kind="card"):
    w.page.click("#stepbar li[data-step=preview]")
    w.until(f"return wizard.slicing.model().kind === '{kind}';")


def wizard_pictures(browser, server, width):
    v = version_event(server.version)
    # slicing
    server.script("GET", EVENTS, stream(v, progress_event(running()), hold=True))
    w = wizard_page(browser, server, width)
    to_preview(w)
    w.until("return wizard.slicing.model().card.pct === '42%';")
    w.page.clock.run_for(3000)
    shoot(w.page, f"{width}-slicing-wizard.png")
    w.page.close()

    # no news, then reconnected
    first = stream(v, progress_event(running()), hold=True)
    quiet = stream(v, hold=True)
    server.script("GET", EVENTS, first, quiet, stream(v, progress_event(running(fraction=0.61, elapsed_s=81, sequence=30)), hold=True))
    w = wizard_page(browser, server, width)
    to_preview(w)
    w.until("return wizard.slicing.model().card.pct === '42%';")
    w.page.clock.run_for(46_000)                 # 45 s with nothing: the stream counts as failed
    w.until("return wizard.slicing.model().card.stalled;")
    first.release()
    w.page.clock.run_for(1000)
    shoot(w.page, f"{width}-no-news-wizard.png")
    quiet.release()
    w.until("return wizard.slicing.model().card.conn && wizard.slicing.model().card.conn.kind === 'back';")
    w.page.clock.run_for(1000)
    shoot(w.page, f"{width}-reconnected-wizard.png")
    w.page.close()

    # empty layers, supports off, then with Details opened
    server.script("GET", EVENTS, stream(v, progress_event(failed(example("error-report-orca-sentence.json")))))
    w = wizard_page(browser, server, width)
    to_preview(w, "failed")
    shoot(w.page, f"{width}-empty-layers-wizard.png")
    w.page.click("#preview-errors details summary")
    shoot(w.page, f"{width}-empty-layers-details-wizard.png")
    w.page.close()

    # empty layers, supports on: the slice service's sentences of that failure
    gap = {**example("error-report-orca-sentence.json"), "code": "slice.empty_layers_with_supports",
           "remedy": "Repair the part in CAD so it has no gap or loose surfaces, export it again and slice again."}
    del gap["action"]
    server.script("GET", EVENTS, stream(v, progress_event(failed(gap))))
    w = wizard_page(browser, server, width)
    to_preview(w, "failed")
    shoot(w.page, f"{width}-empty-layers-supports-wizard.png")
    w.page.close()

    # too slow
    slow = error_report("slice.timeout", message="The slicer took too long on this plate.",
                        remedy="Try again, or slice fewer instances at once.", retryable=True, action="lower_quantities")
    server.script("GET", EVENTS, stream(v, progress_event(failed(slow))))
    w = wizard_page(browser, server, width)
    to_preview(w, "failed")
    shoot(w.page, f"{width}-timeout-wizard.png")
    w.page.close()

    # waiting behind others
    server.script("GET", EVENTS, stream(v, hold=True))
    w = wizard_page(browser, server, width)
    to_preview(w)
    w.page.clock.run_for(12_000)
    shoot(w.page, f"{width}-waiting-wizard.png")
    w.page.close()

    # waiting while the slicer restarts
    stopping = error_report("slice.stopping", message="The slicer is restarting.",
                            remedy="Your plate will be sliced as soon as the slicer is back.", retryable=True)
    server.script("POST", "/api/slices", *[(503, stopping)] * 10)
    w = wizard_page(browser, server, width)
    to_preview(w)
    w.until("return wizard.slicing.model().card.stage.startsWith('The slicer is restarting');")
    w.page.clock.run_for(8_000)
    shoot(w.page, f"{width}-restarting-wizard.png")
    w.page.close()
    server.scripts.pop(("POST", "/api/slices"), None)

    # the slicer restarted: a waiting slice ended at the stop, submitted again by itself
    server.script("GET", EVENTS, stream(v, progress_event(running(state="cancelled", cancel_reason="shutdown", sequence=18))),
                  stream(v, progress_event(running(stage="building_plate", stage_label="Building the plate", fraction=None, elapsed_s=2.0, sequence=3)), hold=True))
    w = wizard_page(browser, server, width)
    to_preview(w)
    w.until("return wizard.slicing.model().card.conn && wizard.slicing.model().card.conn.kind === 'restart';")
    w.page.clock.run_for(1000)
    shoot(w.page, f"{width}-restarted-wizard.png")
    w.page.close()

    # no room to wait
    busy = error_report("slice.busy", message="The slicer is busy, try again in a minute.", remedy="Wait a minute and slice again.", retryable=True)
    server.script("POST", "/api/slices", (503, busy))
    w = wizard_page(browser, server, width)
    to_preview(w, "busy")
    shoot(w.page, f"{width}-busy-wizard.png")
    w.page.close()

    # resting on an edge
    server.script("GET", EVENTS, stream(v, progress_event(failed(example("error-report-rests-on-an-edge.json")))))
    w = wizard_page(browser, server, width)
    to_preview(w, "failed")
    shoot(w.page, f"{width}-rests-on-an-edge-wizard.png")
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
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>The Preview step's slicing and failures beside the mockup</title>"
        "<style>body{margin:24px;font:14px/1.45 system-ui,sans-serif;background:#fff;color:#1f2328}"
        ".pair{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}figure{margin:0}"
        "img{border:1px solid #d0d7de;display:block}figcaption{color:#5a6570;font-size:12px;margin-top:4px}"
        "h3{font-size:14px;margin:24px 0 8px}</style></head><body>"
        "<h1>The Preview step's slicing and failures beside the mockup</h1>"
        "<p>Each pair is the mockup's whole panel (left) and the built page's (right) at the same width, in the same state. "
        "A failure's sentences differ: the mockup's are its own, the built page's the slice service's. "
        "The mockup's slicing card has Cancel slice, which the wizard leaves out on purpose. "
        "Made by <code>make -C wizard look-preview-step</code>.</p>"
        + "".join(rows) + "</body></html>",
        encoding="utf-8")


def main():
    with sync_playwright() as playwright, FakeFrontServer(DIST) as server:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                mockup_pictures(browser, width)
                wizard_pictures(browser, server, width)
                print(f"look-preview-step: {width} px done")
        finally:
            browser.close()
    write_index()
    print(f"look-preview-step: wrote {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
