#!/usr/bin/env python3
"""The look of the panel as a whole beside the mockup's: pictures of the mockup
(docs/mockups/print-wizard, version 8, standalone) and of the built page (wizard/dist/, served
by the fake front server) at 320, 480, 520 and 680 px, for the header and step tabs with the
panel line, a tooltip, the plate summary, the change details (a joined box), a notification, a
message, a card, a line, the page's confirmation and the panel line's amber and red retry
messages (the last three the mockup never drew), written in pairs to
docs/orchestration/phase-2/look/wizard-2/ with index.html, which shows each pair side by side.

Not a test: a person looks at the pairs. The built page is put in the mockup's state by its
own modules, with the mockup's words read from the mockup's page, so that each pair differs only
where the look differs. Each step waits on an event (an element appearing), never on a duration.

Usage: make -C wizard look (builds first).
"""
import datetime
import html
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from tests_browser.conftest import DIST, START, main_module  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer, error_report  # noqa: E402

MOCKUP = (WIZARD.parent / "docs" / "mockups" / "print-wizard" / "index.html").as_uri()
OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-2"
WIDTHS = [320, 480, 520, 680]
HEIGHT = 760
THINGS = [
    ("tabs", "The header and the step tabs, with the panel line's passing use after a held click"),
    ("tooltip", "The panel's own tooltip: a step circle's below 480 px, the reload glyph's from 480 px"),
    ("summary", "The plate summary on the Settings step, with its pill"),
    ("joined-box", "The change details, the joined box the pill opens"),
    ("notification", "A notification"),
    ("message", "A message (amber)"),
    ("card", "A card"),
    ("line", "A line: the Parts step's count under the list"),
    ("confirmation", "A confirmation (designed in the guide; the mockup has none)"),
    ("retry-amber", "The panel line in amber at 20 s of failures, counting down (the guide's; the mockup has none)"),
    ("retry-red", "The panel line in red with Try again (the guide's; the mockup has none)"),
]
PAD = 6


def clip(page, *selectors):
    """The box around the elements, in the page, a few pixels wider, within the panel."""
    boxes = [page.locator(s).first.bounding_box() for s in selectors]
    boxes = [b for b in boxes if b]
    panel = page.locator("#wizard").bounding_box()
    left = max(panel["x"], min(b["x"] for b in boxes) - PAD)
    top = max(panel["y"], min(b["y"] for b in boxes) - PAD)
    right = min(panel["x"] + panel["width"], max(b["x"] + b["width"] for b in boxes) + PAD)
    bottom = min(panel["y"] + panel["height"], max(b["y"] + b["height"] for b in boxes) + PAD)
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def shoot(page, name, *selectors):
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / name), clip=clip(page, *selectors))


# ---- the mockup

def mockup_at(browser, width):
    page = browser.new_page(viewport={"width": max(1200, width + 700), "height": HEIGHT + 200})
    page.goto(MOCKUP)
    page.wait_for_selector("#stepbar li.active")
    page.select_option("#sc-context", "standalone")
    page.wait_for_selector("#sa-slot #wizard")
    page.evaluate("w => { document.documentElement.style.setProperty('--panel-width', w + 'px'); window.Wizard.resize(); }", width)
    page.wait_for_function("w => document.getElementById('wizard').getBoundingClientRect().width === w", arg=width)
    return page


def mockup_pictures(browser, width):
    words = {}
    page = mockup_at(browser, width)
    page.click("#stepbar li[data-step=layout]")
    page.wait_for_selector("#step-why:not([hidden])")
    shoot(page, f"{width}-tabs-mockup.png", "#wiz-header")
    words["held"] = page.inner_text("#step-why")
    page.mouse.click(5, HEIGHT)                          # the next move ends the passing line
    target = "#stepbar li[data-step=layout]" if width < 480 else "#config-info .config-refresh"
    page.hover(target)
    page.wait_for_selector("#wiz-tip:not([hidden])")
    shoot(page, f"{width}-tooltip-mockup.png", "#wiz-header", "#wiz-tip")
    words["tip"] = page.inner_text("#wiz-tip")
    page.mouse.move(5, HEIGHT)

    # a notification: the next upload is armed to fail
    page.select_option("#sc-error", "export_fail")
    page.click("#sc-arm")
    page.evaluate("window.__mockUpload('Gusset Plate.stl')")
    page.wait_for_selector("#notices .notice")
    shoot(page, f"{width}-notification-mockup.png", "#notices .notice")
    words["notice"] = {"what": page.inner_text("#notices .n-what"), "todo": page.inner_text("#notices .n-todo")}
    page.click("#notices .n-x")

    # a message: a part that arrives with a warning
    page.select_option("#sc-error", "not_watertight")
    page.click("#sc-arm")
    page.evaluate("window.__mockUpload('Gusset Plate.stl')")
    page.wait_for_selector("#parts-list .msg.warn")
    shoot(page, f"{width}-message-mockup.png", "#parts-list .msg.warn")
    words["message"] = {"what": page.inner_text("#parts-list .msg.warn .what"), "todo": page.inner_text("#parts-list .msg.warn .todo")}

    # a line: the count under the parts list
    page.wait_for_function("() => document.getElementById('parts-total').textContent.trim() !== ''")
    shoot(page, f"{width}-line-mockup.png", "#parts-total")
    words["line"] = page.inner_text("#parts-total")

    # the plate summary and the change details
    page.wait_for_selector("#btn-next:not([disabled])")
    page.click("#btn-next")
    page.wait_for_selector("#wiz-summary:not([hidden])")
    page.select_option("#ov-infill", index=0 if page.eval_on_selector("#ov-infill", "s => s.selectedIndex") else 1)
    page.wait_for_selector("#chg-chip")
    shoot(page, f"{width}-summary-mockup.png", ".summary-wrap")
    words["summary"] = {
        "lines": page.locator("#wiz-summary .sum-line").all_inner_texts(),
        "full": page.eval_on_selector("#wiz-summary .sum-text", "e => e.dataset.tip || e.title || e.textContent"),
    }
    page.click("#chg-chip")
    page.wait_for_selector("#chg-pop:not([hidden])")
    shoot(page, f"{width}-joined-box-mockup.png", ".summary-wrap", "#chg-pop")
    words["changes"] = page.locator("#chg-pop li").all_inner_texts()
    page.keyboard.press("Escape")

    # a card: the Send step's summary card, after a slice
    page.click("#btn-next")
    page.wait_for_selector("section.step[data-step=layout]:not([hidden])")
    page.wait_for_selector("#btn-next:not([disabled])")
    page.click("#btn-next")
    page.wait_for_selector("#preview-result:not([hidden])", timeout=120_000)
    page.wait_for_selector("#btn-next:not([disabled])")
    page.click("#btn-next")
    page.wait_for_selector("#send-summary .card")
    shoot(page, f"{width}-card-mockup.png", "#send-summary .card")
    words["card"] = page.eval_on_selector("#send-summary .card", "e => e.innerHTML")
    page.close()
    return words


# ---- the built page

def wizard_at(browser, server, width):
    page = browser.new_page(viewport={"width": width, "height": HEIGHT})
    page.clock.install(time=datetime.datetime(2026, 11, 28, 20, 0, tzinfo=datetime.timezone.utc))
    page.goto(server.url)
    page.wait_for_selector('html[data-started="true"]', state="attached")
    return page


def run(page, body, arg=None):
    return page.evaluate(
        f"async ([url, arg]) => {{ const {{ wizard }} = await import(url); return (async (wizard, arg) => {{ {body} }})(wizard, arg); }}",
        [main_module(), arg])


CHANGE = re.compile(r"^(.*?) › (.*?): (.*) \(profile (.*)\)$")


def wizard_pictures(browser, server, width, words):
    page = wizard_at(browser, server, width)
    run(page, "wizard.store.set({configName: '6238 (Popcorn Penguins)'});")
    page.click("#stepbar li[data-step=layout]")
    page.wait_for_selector("#step-why:not([hidden])")
    shoot(page, f"{width}-tabs-wizard.png", "#wiz-header")
    # the mockup's passing line stays through its tooltip (its move away falls outside its
    # panel), so the wizard's stays too: both pages in one state. A move away (no press) and
    # back starts the tooltip's rest afresh.
    page.mouse.move(5, HEIGHT - 5)
    target = "#stepbar li[data-step=layout]" if width < 480 else "#config-refresh"
    page.hover(target)
    page.clock.run_for(150)
    page.wait_for_selector("#wiz-tip:not([hidden])")
    shoot(page, f"{width}-tooltip-wizard.png", "#wiz-header", "#wiz-tip")
    page.mouse.move(5, HEIGHT - 5)

    run(page, "wizard.panel.notify({kind: 'error', what: arg.what, todo: arg.todo});", words["notice"])
    shoot(page, f"{width}-notification-wizard.png", "#notices .notice")
    page.click("#notices .n-x")

    run(page, """const m = wizard.panel.tell.message({kind: 'warn', what: arg.what, todo: arg.todo});
                 m.id = 'look-message'; document.querySelector('section.step[data-step=parts]').append(m);""", words["message"])
    shoot(page, f"{width}-message-wizard.png", "#look-message")

    run(page, """const l = wizard.panel.tell.line(arg); l.id = 'look-line';
                 document.querySelector('section.step[data-step=parts]').append(l);""", words["line"])
    shoot(page, f"{width}-line-wizard.png", "#look-line")

    first = re.match(r"(\d+) parts? · (\d+) instances?", words["summary"]["lines"][0])
    filament, profile = words["summary"]["lines"][1].split(" · ", 1)
    full = words["summary"]["full"].split(" · ", 1)[0]
    changes = [dict(zip(["section", "label", "value", "profile"], CHANGE.match(line).groups())) for line in words["changes"]]
    profile = re.sub(r"\+\d+ changes?$", "", profile).strip()
    run(page, "wizard.store.set(arg);", {"step": "settings", "plate": {
        "parts": int(first.group(1)), "instances": int(first.group(2)), "filament": filament,
        "filamentFull": full, "profile": profile, "changes": changes}})
    shoot(page, f"{width}-summary-wizard.png", ".summary-wrap")
    page.click("#chg-chip")
    page.wait_for_selector("#chg-pop:not([hidden])")
    shoot(page, f"{width}-joined-box-wizard.png", ".summary-wrap", "#chg-pop")
    page.keyboard.press("Escape")

    run(page, """wizard.store.set({sliced: true, step: 'send'});
                 const nodes = new DOMParser().parseFromString(arg, 'text/html').body.childNodes;
                 const c = wizard.panel.tell.card(...nodes); c.id = 'look-card';
                 document.querySelector('section.step[data-step=send]').append(c);""", words["card"])
    shoot(page, f"{width}-card-wizard.png", "#look-card")

    run(page, """wizard.store.set({step: 'parts'});
                 const b = document.createElement('button'); b.id = 'look-new-plate'; b.className = 'btn small'; b.textContent = 'New plate';
                 document.querySelector('section.step[data-step=parts]').append(b);
                 wizard.panel.tell.confirm(b, {question: 'Start a new plate? The parts on this plate are dropped.', go: 'New plate', keep: 'Keep this plate'});""")
    page.wait_for_selector(".confirm-pop")
    shoot(page, f"{width}-confirmation-wizard.png", "#look-new-plate", ".confirm-pop")
    page.close()


def paused_page(browser, server, width):
    """The built page with its clock paused and its retry spread at its middle, so that the
    retry waits are exact and time moves only when this script moves it."""
    page = browser.new_page(viewport={"width": width, "height": HEIGHT})
    page.add_init_script("Math.random = () => 0.5;")
    page.clock.install(time=START)
    page.goto(server.url)
    page.wait_for_selector('html[data-started="true"]', state="attached")
    page.clock.pause_at(START + datetime.timedelta(minutes=10))
    return page


def until_waiting(page):
    """Asks the page until its one failed request waits for its next attempt: events, no time."""
    for _ in range(500):
        if run(page, "return wizard.api.waiting() === 1;"):
            return
    raise RuntimeError("the page never waited to retry")


def retry_pictures(browser, server, width):
    # amber: every attempt fails at once; attempts at 1, 3, 7 and 15 s, then 20 s
    page = paused_page(browser, server, width)
    run(page, "wizard.store.set({configName: '6238 (Popcorn Penguins)'});")
    page.route("**/api/me", lambda route: route.abort())
    with page.expect_event("requestfailed"):
        run(page, "wizard.api.get('/api/me'); return null;")
    for wait in [1000, 2000, 4000, 8000]:
        until_waiting(page)
        with page.expect_event("requestfailed"):
            page.clock.run_for(wait)
    until_waiting(page)
    page.clock.run_for(5000)
    page.wait_for_selector("#step-why.slow:not([hidden])")
    shoot(page, f"{width}-retry-amber-wizard.png", "#wiz-header")
    page.close()

    # red: the front server asks for a wait past the 300 s, so no attempt is left to count down to
    page = paused_page(browser, server, width)
    run(page, "wizard.store.set({configName: '6238 (Popcorn Penguins)'});")
    page.route("**/api/me", lambda route: route.fulfill(
        status=429, headers={"X-PenguinSlicer-Version": server.version, "Retry-After": "400"},
        content_type="application/json", body=json.dumps(error_report("front.too_many_requests", retryable=True))))
    run(page, "wizard.api.get('/api/me'); return null;")
    until_waiting(page)
    page.clock.run_for(20000)
    page.wait_for_function("() => document.getElementById('step-why').textContent.includes('could not be reached')")
    shoot(page, f"{width}-retry-red-wizard.png", "#wiz-header")
    page.close()


def write_index():
    rows = []
    for width in WIDTHS:
        rows.append(f"<h2>{width} px</h2>")
        for thing, says in THINGS:
            mock = f"{width}-{thing}-mockup.png"
            mine = f"{width}-{thing}-wizard.png"
            left = f'<img src="{mock}" alt="the mockup">' if (OUT / mock).exists() else "<p>The mockup has none.</p>"
            rows.append(f'<h3>{html.escape(says)}</h3><div class="pair"><figure>{left}<figcaption>Mockup, version 8</figcaption></figure>'
                        f'<figure><img src="{mine}" alt="the wizard"><figcaption>The wizard, as built</figcaption></figure></div>')
    (OUT / "index.html").write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>The panel beside the mockup</title>"
        "<style>body{margin:24px;font:14px/1.45 system-ui,sans-serif;background:#fff;color:#1f2328}"
        ".pair{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}figure{margin:0}"
        "img{border:1px solid #d0d7de;display:block}figcaption{color:#5a6570;font-size:12px;margin-top:4px}"
        "h3{font-size:14px;margin:24px 0 8px}</style></head><body>"
        "<h1>The panel as a whole beside the mockup</h1>"
        "<p>Each pair is the mockup (left) and the built page (right) at the same width, in the same state, "
        "with the mockup's words. Made by <code>make -C wizard look</code>.</p>" + "".join(rows) + "</body></html>",
        encoding="utf-8")


def main():
    with sync_playwright() as playwright, FakeFrontServer(DIST) as server:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                words = mockup_pictures(browser, width)
                wizard_pictures(browser, server, width, words)
                retry_pictures(browser, server, width)
                print(f"look: {width} px done")
        finally:
            browser.close()
    write_index()
    print(f"look: wrote {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
