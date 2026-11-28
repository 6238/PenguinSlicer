#!/usr/bin/env python3
"""The look of the Parts step beside the mockup's: pictures of the whole panel of the mockup
(docs/mockups/print-wizard, version 8, standalone, its uploads read in inches) and of the built
page (wizard/dist/, served by the fake front server) at 320, 480, 520 and 680 px, in each state
of the step the mockup shows: empty; a part arriving; parts listed; a part with a warning on its
row; a part that cannot be used, as a notification; a part whose upload is slow; parts past 150
instances, with the red message. And, on the built page only, the screens the mockup never drew:
New plate's confirmation, a part over the size limit, the twenty-sixth part and a part the page
cannot draw. Written in pairs to docs/orchestration/phase-2/look/wizard-4/, with index.html,
which shows each pair side by side.

Not a test: a person looks at the pairs. The built page is put in the mockup's state by the
user's own moves (files chosen in the upload area, a quantity typed) and by the fake front
server's answers, which carry the mockup's words and sizes read from the mockup's page, so that
each pair differs only where the look differs. Each step waits on an event, never on a duration.

Usage: make -C wizard look-parts-step (builds first).
"""
import datetime
import hashlib
import html
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from tests_browser.conftest import DIST, START, main_module  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer, error_report, example  # noqa: E402
from tests_browser.test_parts_step import box_stl  # noqa: E402

MOCKUP = (WIZARD.parent / "docs" / "mockups" / "print-wizard" / "index.html").as_uri()
OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-4"
WIDTHS = [320, 480, 520, 680]
HEIGHT = 760
FILES = ["Gusset Plate.stl", "L Bracket.stl", "Shooter Hood Rib.stl", "Elevator Block.stl"]
STATES = [
    ("empty", "The empty step: the upload area, with the switch beside it (the mockup: a line)"),
    ("arriving", "A part arriving, its bar and \"Uploading…\""),
    ("listed", "Two parts listed, and the line under the list"),
    ("warning", "A part with a warning on its row, in amber"),
    ("notification", "A part that cannot be used, as a notification"),
    ("slow", "A part whose upload is slow, at 4 s"),
    ("too-many", "Parts past 150 instances: the red message under the list, Next off"),
    ("new-plate", "New plate's confirmation (designed in the guide; the mockup has none)"),
    ("over-size", "A part over the size limit (designed in the guide; the mockup has none)"),
    ("twenty-sixth", "The twenty-sixth part (designed in the guide; the mockup has none)"),
    ("not-drawable", "A part the page cannot draw (designed in the guide; the mockup has none)"),
]


# The red message under the list is below the fold at every width: both pages scroll to it.
SCROLL_DOWN = "() => { const b = document.getElementById('wiz-body'); b.scrollTop = b.scrollHeight; }"


def shoot(page, name):
    OUT.mkdir(parents=True, exist_ok=True)
    page.locator("#wizard").screenshot(path=str(OUT / name), animations="disabled")


# ---- the mockup

def mockup_pictures(browser, width):
    """Shoots the mockup's states and returns its words: each part's size and the sentences."""
    words = {"dims": {}}
    page = browser.new_page(viewport={"width": max(1200, width + 700), "height": HEIGHT + 200})
    page.goto(MOCKUP)
    page.wait_for_selector("#stepbar li.active")
    page.select_option("#sc-context", "standalone")
    page.select_option("#sc-speed", "real")
    page.wait_for_selector("#sa-slot #wizard")
    page.evaluate("w => { document.documentElement.style.setProperty('--panel-width', w + 'px'); window.Wizard.resize(); }", width)
    page.wait_for_function("w => document.getElementById('wizard').getBoundingClientRect().width === w", arg=width)
    shoot(page, f"{width}-empty-mockup.png")

    def upload(name, count):
        page.evaluate("n => window.__mockUpload(n)", name)
        page.wait_for_function("c => document.querySelectorAll('#parts-list .part-item').length === c", arg=count)

    def arrived(count):
        page.wait_for_function("c => document.querySelectorAll('#parts-list .part-item:not(.arriving)').length === c", arg=count)

    def dims_of(index, name):
        words["dims"][name] = page.locator("#parts-list .part-item .dims").nth(index).inner_text()

    upload(FILES[0], 1)
    page.wait_for_selector("#parts-list .part-item.arriving")
    shoot(page, f"{width}-arriving-mockup.png")
    arrived(1)
    dims_of(0, FILES[0])
    upload(FILES[1], 2)
    arrived(2)
    dims_of(1, FILES[1])
    page.mouse.move(5, HEIGHT + 150)
    shoot(page, f"{width}-listed-mockup.png")
    words["line"] = page.inner_text("#parts-total")

    page.select_option("#sc-error", "not_watertight")
    page.click("#sc-arm")
    upload(FILES[2], 3)
    arrived(3)
    dims_of(2, FILES[2])
    page.wait_for_selector("#parts-list .msg.warn")
    shoot(page, f"{width}-warning-mockup.png")
    words["warning"] = {"what": page.inner_text("#parts-list .msg.warn .what"), "todo": page.inner_text("#parts-list .msg.warn .todo")}

    page.select_option("#sc-error", "export_fail")
    page.click("#sc-arm")
    page.evaluate("n => window.__mockUpload(n)", "bracket.stl")
    page.wait_for_selector("#notices .notice")
    arrived(3)
    shoot(page, f"{width}-notification-mockup.png")
    words["notice"] = {"what": page.inner_text("#notices .n-what"), "todo": page.inner_text("#notices .n-todo")}
    page.click("#notices .n-x")

    page.select_option("#sc-error", "server_slow")
    page.click("#sc-arm")
    upload(FILES[3], 4)
    page.wait_for_selector("#parts-list .dims.slow", timeout=30_000)
    shoot(page, f"{width}-slow-mockup.png")
    arrived(4)
    dims_of(3, FILES[3])

    qty = page.locator("#parts-list .part-qty").nth(0)
    qty.fill("150")
    qty.dispatch_event("change")
    page.wait_for_selector("#parts-total .msg.error")
    page.mouse.move(5, HEIGHT + 150)
    page.evaluate(SCROLL_DOWN)
    shoot(page, f"{width}-too-many-mockup.png")
    page.close()
    return words


# ---- the built page

def size_mm(dims):
    """The millimetres behind a size the mockup shows, "2.000 × 2.000 × 0.188 in"."""
    figures = [float(v) for v in re.findall(r"[\d.]+", dims)]
    return [round(v * 25.4, 4) for v in figures] if dims.endswith(" in") else figures


def record_of(data, dims, warning=None):
    record = {**example("wizard-front/part-record.json"), "sha256": hashlib.sha256(data).hexdigest(), "units": "in", "warnings": []}
    record["measurements"] = {**record["measurements"], "size_mm": size_mm(dims)}
    if warning:
        record["warnings"] = [{"code": "slice.part_not_watertight", "message": warning, "detail": "open edges 14"}]
    return record


def run(page, body, arg=None):
    return page.evaluate(
        f"async ([url, arg]) => {{ const {{ wizard }} = await import(url); return (async (wizard, arg) => {{ {body} }})(wizard, arg); }}",
        [main_module(), arg])


def until(page, condition, arg=None):
    for _ in range(1000):
        if run(page, f"return Boolean((() => {{ {condition} }})());", arg):
            return
    raise RuntimeError(f"the page never reached: {condition}")


def choose(page, name, data):
    page.set_input_files("#f-upload", [{"name": name, "mimeType": "application/octet-stream", "buffer": data}])


def wizard_page(browser, server, width):
    page = browser.new_page(viewport={"width": width, "height": HEIGHT})
    page.add_init_script("Math.random = () => 0.5;")
    page.clock.install(time=START)
    page.goto(server.url)
    page.wait_for_selector('html[data-opened="true"]', state="attached")
    page.clock.pause_at(START + datetime.timedelta(minutes=10))
    return page


def settled(page, count):
    until(page, f"return wizard.parts.rows().length === {count} && wizard.parts.rows().every((r) => !r.arriving && r.drawn) "
                f"&& document.querySelectorAll('#parts-list canvas.thumb').length === {count};")


def wizard_pictures(browser, server, width, words):
    page = wizard_page(browser, server, width)
    run(page, "wizard.store.set({configName: '6238 (Popcorn Penguins)'});")
    shoot(page, f"{width}-empty-wizard.png")
    files = {name: box_stl(name.encode()) for name in FILES}

    held = []
    page.route("**/api/parts*", lambda route: held.append(route))
    server.script("POST", "/api/parts", (201, record_of(files[FILES[0]], words["dims"][FILES[0]])))
    choose(page, FILES[0], files[FILES[0]])
    page.wait_for_selector("#parts-list .part-item.arriving")
    until(page, "return wizard.parts.rows()[0].drawn && document.querySelector('#parts-list canvas.thumb');")
    shoot(page, f"{width}-arriving-wizard.png")
    for route in held:
        route.continue_()
    page.unroute("**/api/parts*")
    settled(page, 1)

    server.script("POST", "/api/parts", (201, record_of(files[FILES[1]], words["dims"][FILES[1]])))
    choose(page, FILES[1], files[FILES[1]])
    settled(page, 2)
    shoot(page, f"{width}-listed-wizard.png")

    warning = f"{words['warning']['what']} {words['warning']['todo']}"
    server.script("POST", "/api/parts", (201, record_of(files[FILES[2]], words["dims"][FILES[2]], warning)))
    choose(page, FILES[2], files[FILES[2]])
    settled(page, 3)
    shoot(page, f"{width}-warning-wizard.png")

    todo = words["notice"]["todo"].replace("Your other parts are fine. ", "")
    server.script("POST", "/api/parts", (422, error_report("slice.part_unreadable", message=words["notice"]["what"], remedy=todo)))
    choose(page, "bracket.stl", box_stl(b"bracket"))
    page.wait_for_selector("#notices .notice")
    until(page, "return wizard.parts.rows().length === 3;")
    shoot(page, f"{width}-notification-wizard.png")
    page.click("#notices .n-x")

    page.route("**/api/parts*", lambda route: route.abort())
    choose(page, FILES[3], files[FILES[3]])
    page.wait_for_selector("#parts-list .part-item.arriving")
    until(page, "return wizard.api.waiting() === 1;")
    page.clock.run_for(4000)
    page.wait_for_selector("#parts-list .dims.slow")
    shoot(page, f"{width}-slow-wizard.png")
    page.unroute("**/api/parts*")
    server.script("POST", "/api/parts", (201, record_of(files[FILES[3]], words["dims"][FILES[3]])))
    run(page, "wizard.api.board.retryNow();")
    settled(page, 4)

    qty = page.locator("#parts-list .part-qty").nth(0)
    qty.fill("150")
    qty.dispatch_event("change")
    page.wait_for_selector("#parts-total .msg.error")
    page.evaluate(SCROLL_DOWN)
    shoot(page, f"{width}-too-many-wizard.png")
    qty.fill("1")
    qty.dispatch_event("change")
    page.wait_for_function("() => !document.querySelector('#parts-total .msg')")
    page.evaluate("() => { document.getElementById('wiz-body').scrollTop = 0; }")

    page.click("section.step[data-step=parts] .new-plate .btn")
    page.wait_for_selector(".confirm-pop")
    shoot(page, f"{width}-new-plate-wizard.png")
    page.keyboard.press("Escape")

    choose(page, "bracket.stl", b"\x00" * 9_100_000)
    page.wait_for_selector("#notices .notice")
    shoot(page, f"{width}-over-size-wizard.png")
    page.click("#notices .n-x")

    page.set_input_files("#f-upload", [{"name": f"Part {i}.stl", "mimeType": "application/octet-stream", "buffer": box_stl(f"p{i}".encode())}
                                       for i in range(22)])
    until(page, "return wizard.parts.rows().length === 25 && document.querySelector('#notices .notice');")
    settled(page, 25)
    page.evaluate("() => document.getElementById('wiz-body').scrollTop = 0")
    shoot(page, f"{width}-twenty-sixth-wizard.png")
    page.close()

    page = wizard_page(browser, server, width)
    run(page, "wizard.store.set({configName: '6238 (Popcorn Penguins)'});")
    choose(page, "broken.stl", b"\x00" * 84)
    page.wait_for_selector("#notices .notice")
    shoot(page, f"{width}-not-drawable-wizard.png")
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
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>The Parts step beside the mockup</title>"
        "<style>body{margin:24px;font:14px/1.45 system-ui,sans-serif;background:#fff;color:#1f2328}"
        ".pair{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}figure{margin:0}"
        "img{border:1px solid #d0d7de;display:block}figcaption{color:#5a6570;font-size:12px;margin-top:4px}"
        "h3{font-size:14px;margin:24px 0 8px}</style></head><body>"
        "<h1>The Parts step beside the mockup</h1>"
        "<p>Each pair is the mockup's whole panel (left) and the built page's (right) at the same width, in the same state, "
        "with the mockup's words and sizes. Made by <code>make -C wizard look-parts-step</code>.</p>" + "".join(rows) + "</body></html>",
        encoding="utf-8")


def main():
    with sync_playwright() as playwright, FakeFrontServer(DIST) as server:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                words = mockup_pictures(browser, width)
                wizard_pictures(browser, server, width, words)
                print(f"look-parts-step: {width} px done")
        finally:
            browser.close()
    write_index()
    print(f"look-parts-step: wrote {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
