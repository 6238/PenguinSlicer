#!/usr/bin/env python3
"""The look of the Settings step and advanced mode beside the mockup's: pictures of the whole panel
of the mockup (docs/mockups/print-wizard, version 8, standalone) and of the built page (wizard/dist/,
served by the fake front server) at 320, 480, 520 and 680 px, in each state the mockup shows: the
step with no change; the step with two quick changes (the caution, the changes box); advanced mode
with those changes (the accordion below 480 px, the rail from 480 px); advanced mode with a
section or setting group closed; a value refused where it is typed; Reset all asking first. Written
in pairs to docs/orchestration/phase-2/look/wizard-5a/, with index.html, which shows each pair side
by side.

Not a test: a person looks at the pairs. So that each pair differs only where the look differs,
the built page is given a configuration and a table of settings made from the mockup's own sample
(its filament, its profiles and their values, its settings with their sections, setting groups,
labels and ranges), read from the mockup's page, and it is put in each state by the user's own
moves. Each step waits on an event, never on a duration.

Usage: make -C wizard look-settings-step (builds first).
"""
import datetime
import hashlib
import html
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

WIZARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIZARD))

from tests_browser.conftest import DIST, START, main_module  # noqa: E402
from tests_browser.fake_front_server import FakeFrontServer, example  # noqa: E402
from tests_browser.test_parts_step import box_stl  # noqa: E402

MOCKUP = (WIZARD.parent / "docs" / "mockups" / "print-wizard" / "index.html").as_uri()
OUT = WIZARD.parent / "docs" / "orchestration" / "phase-2" / "look" / "wizard-5a"
WIDTHS = [320, 480, 520, 680]
HEIGHT = 760
PRINTER = "Bambu Lab H2S 0.6 nozzle"
STATES = [
    ("step", "The Settings step with no change: Filament, Profile, the four quick changes, Advanced mode"),
    ("changed", "Two quick changes: the caution under the Profile menu and the changes box"),
    ("advanced", "Advanced mode with those changes: the accordion below 480 px, the rail from 480 px"),
    ("closed", "Advanced mode with a section (below 480 px) or a setting group (from 480 px) closed"),
    ("refused", "A value out of range refused where it is typed"),
    ("reset-all", "Reset all asking first (the mockup: the button armed; the guide: a confirmation)"),
]


def shoot(page, name):
    OUT.mkdir(parents=True, exist_ok=True)
    page.mouse.move(5, HEIGHT - 5)
    page.locator("#wizard").screenshot(path=str(OUT / name), animations="disabled")


# ---- the mockup

def mockup_page(browser, width):
    page = browser.new_page(viewport={"width": max(1200, width + 700), "height": HEIGHT + 200})
    page.goto(MOCKUP)
    page.wait_for_selector("#stepbar li.active")
    page.select_option("#sc-context", "standalone")
    page.select_option("#sc-speed", "real")
    page.wait_for_selector("#sa-slot #wizard")
    page.evaluate("w => { document.documentElement.style.setProperty('--panel-width', w + 'px'); window.Wizard.resize(); }", width)
    page.wait_for_function("w => document.getElementById('wizard').getBoundingClientRect().width === w", arg=width)
    page.evaluate("n => window.__mockUpload(n)", "Gusset Plate.stl")
    page.wait_for_function("() => document.querySelectorAll('#parts-list .part-item:not(.arriving)').length === 1")
    page.click("#stepbar li[data-step=setup]")
    page.wait_for_selector("section.step[data-step=setup]:not([hidden])")
    return page


def mockup_sample(browser):
    """The mockup's own sample: its settings, profiles, filament and quick changes."""
    page = mockup_page(browser, 320)
    sample = page.evaluate("""() => { const M = window.MockSettings; return {
        settings: M.SETTINGS.map((s) => ({ key: s.key, group: s.group, sub: s.sub, label: s.label, type: s.type,
            unit: s.unit, min: s.min, max: s.max, step: s.step, options: s.options || null })),
        profiles: M.profilesOf('petg').map((p) => ({ id: p.id, name: p.name, about: p.about, values: p.values })),
        filament: M.FILAMENTS[0].name }; }""")
    page.close()
    return sample


def mockup_pictures(browser, width):
    page = mockup_page(browser, width)
    shoot(page, f"{width}-step-mockup.png")
    page.select_option("#ov-walls", "6")
    page.select_option("#ov-brim", "no_brim")
    shoot(page, f"{width}-changed-mockup.png")
    page.click("#adv-effect-btn")
    page.wait_for_selector("#advanced:not([hidden])")
    page.evaluate("() => document.activeElement.blur()")
    shoot(page, f"{width}-advanced-mockup.png")
    closer = "#adv-sec-Quality" if width < 480 else "#adv-grp-Quality-Layer-height"
    page.click(closer)
    page.evaluate("() => document.activeElement.blur()")
    shoot(page, f"{width}-closed-mockup.png")
    page.click(closer)
    refuse(page, "#adv-layer_height", "0.9")
    shoot(page, f"{width}-refused-mockup.png")
    page.click("#adv-reset-all")
    shoot(page, f"{width}-reset-all-mockup.png")
    page.close()


def refuse(page, selector, value):
    page.fill(selector, value)
    page.locator(selector).dispatch_event("change")
    page.wait_for_selector(".adv-row .bad")
    page.evaluate("() => document.activeElement.blur()")


# ---- the built page, given the mockup's sample

def table_and_configuration(sample):
    """A table of settings and a configuration in the contracts' shapes, made from the mockup's sample."""
    settings = []
    for s in sample["settings"]:
        entry = {"name": s["key"], "label": s["label"], "section": s["group"], "group": s["sub"],
                 "explanation": "", "per_variant": False}
        if s["type"] == "num":
            form = "percent" if s["unit"] == "%" else ("integer" if s["step"] >= 1 and float(s["min"]).is_integer() else "decimal")
            entry.update(kind="number", number_form=form, min=s["min"], max=s["max"])
            if s["unit"] and s["unit"] != "%":
                entry["unit"] = s["unit"]
            elif s["unit"] == "%":
                entry["unit"] = "%"
        elif s["type"] == "sel":
            entry.update(kind="choice", choices=[{"value": o["value"], "label": o["text"]} for o in s["options"]])
        else:
            entry.update(kind="choice", choices=[{"value": "0", "label": "Off"}, {"value": "1", "label": "On"}])
        settings.append(entry)
    kinds = {s["key"]: s for s in sample["settings"]}

    def written(key, v):
        s = kinds[key]
        if s["type"] == "bool":
            return "1" if v else "0"
        if s["type"] == "num":
            text = f"{v:g}" if isinstance(v, float) else str(v)
            return text + "%" if s["unit"] == "%" else text
        return str(v)

    process = {f"{p['id']} @mockup": {k: written(k, p["values"][k]) for k in kinds} for p in sample["profiles"]}
    table = {"format": 1, "orca_version": "2.4.2", "settings": settings, "process_values": process,
             "catalog": {"printers": [example("settings-table.json")["catalog"]["printers"][0]],
                         "filaments": [{"name": "Generic PETG @BBL H2S", "printers": [PRINTER]}],
                         "processes": [{"name": n, "printers": [PRINTER]} for n in process]}}
    configuration = {"format": 1, "printer": PRINTER, "upload_units": "in", "filaments": [
        {"name": sample["filament"], "colour": "#2f6f8f", "profiles": [
            {"name": p["name"], "purpose": p["about"], "printer": PRINTER, "filament": "Generic PETG @BBL H2S",
             "process": f"{p['id']} @mockup"} for p in sample["profiles"]]}]}
    return table, configuration


def run(page, body, arg=None):
    return page.evaluate(
        f"async ([url, arg]) => {{ const {{ wizard }} = await import(url); return (async (wizard, arg) => {{ {body} }})(wizard, arg); }}",
        [main_module(), arg])


def until(page, condition, arg=None):
    for _ in range(1000):
        if run(page, f"return Boolean((() => {{ {condition} }})());", arg):
            return
    raise RuntimeError(f"the page never reached: {condition}")


def wizard_pictures(browser, server, width, table, configuration):
    answer = (200, {"configuration": configuration, "source": "group", "name": "6238 (Popcorn Penguins)", "revision": "r1"})
    server.script("GET", "/api/configuration", answer)
    server.script("GET", "/api/settings-table", (200, table))
    page = browser.new_page(viewport={"width": width, "height": HEIGHT})
    page.add_init_script("Math.random = () => 0.5;")
    page.clock.install(time=START)
    page.goto(server.url)
    page.wait_for_selector('html[data-opened="true"]', state="attached")
    page.clock.pause_at(START + datetime.timedelta(minutes=10))
    data = box_stl(b"Gusset Plate", (50.8, 50.8, 6.35))
    record = {**example("wizard-front/part-record.json"), "sha256": hashlib.sha256(data).hexdigest(), "units": "in", "warnings": []}
    server.script("POST", "/api/parts", (201, record))
    page.set_input_files("#f-upload", [{"name": "Gusset Plate.stl", "mimeType": "application/octet-stream", "buffer": data}])
    until(page, "return wizard.parts.rows().length === 1 && !wizard.parts.rows()[0].arriving;")
    page.click("#stepbar li[data-step=settings]")
    page.wait_for_selector("section.step[data-step=settings]:not([hidden])")
    shoot(page, f"{width}-step-wizard.png")
    page.select_option("#ov-walls", "6")
    page.select_option("#ov-brim", "no_brim")
    shoot(page, f"{width}-changed-wizard.png")
    page.click("#adv-effect-btn")
    page.wait_for_selector("#advanced:not([hidden])")
    page.wait_for_selector("#advanced.wide" if width >= 480 else "#advanced:not(.wide)", state="attached")
    page.evaluate("() => document.activeElement.blur()")
    shoot(page, f"{width}-advanced-wizard.png")
    closer = "#adv-sec-Quality" if width < 480 else "#adv-grp-Quality-Layer-height"
    page.click(closer)
    page.evaluate("() => document.activeElement.blur()")
    shoot(page, f"{width}-closed-wizard.png")
    page.click(closer)
    refuse(page, "#adv-layer_height", "0.9")
    shoot(page, f"{width}-refused-wizard.png")
    page.click("#adv-reset-all")
    page.wait_for_selector(".confirm-pop")
    shoot(page, f"{width}-reset-all-wizard.png")
    page.keyboard.press("Escape")
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
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>The Settings step beside the mockup</title>"
        "<style>body{margin:24px;font:14px/1.45 system-ui,sans-serif;background:#fff;color:#1f2328}"
        ".pair{display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap}figure{margin:0}"
        "img{border:1px solid #d0d7de;display:block}figcaption{color:#5a6570;font-size:12px;margin-top:4px}"
        "h3{font-size:14px;margin:24px 0 8px}</style></head><body>"
        "<h1>The Settings step and advanced mode beside the mockup</h1>"
        "<p>Each pair is the mockup's whole panel (left) and the built page's (right) at the same width, in the same state. "
        "The built page is given a configuration and a table of settings made from the mockup's own sample of settings and "
        "profiles. Made by <code>make -C wizard look-settings-step</code>.</p>" + "".join(rows) + "</body></html>",
        encoding="utf-8")


def main():
    with sync_playwright() as playwright, FakeFrontServer(DIST) as server:
        browser = playwright.chromium.launch(headless=True)
        try:
            table, configuration = table_and_configuration(mockup_sample(browser))
            for width in WIDTHS:
                mockup_pictures(browser, width)
                wizard_pictures(browser, server, width, table, configuration)
                print(f"look-settings-step: {width} px done")
        finally:
            browser.close()
    write_index()
    print(f"look-settings-step: wrote {OUT / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
