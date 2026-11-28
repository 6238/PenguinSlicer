"""The browser tests drive Playwright's Chromium, headless, against the built page in
wizard/dist/ (`make -C wizard test-browser` builds it first) served by the fake front server.

Time in the page is Playwright's fake clock (`page.clock`), installed before the page loads, so
a test moves it (`page.clock.run_for(ms)`) and never waits a number of seconds. The page's one
random figure, the spread of the retry waits, is held at its middle, so the waits are exact.
The running wizard is reached as the page's own entry module exports it
(`(await import(<main.js>)).wizard`), never through a global."""
import datetime
import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from tests_browser.fake_front_server import FakeFrontServer

DIST = Path(__file__).resolve().parent.parent / "dist"
START = datetime.datetime(2026, 11, 28, 20, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture(scope="session")
def browser():
    if not (DIST / "index.html").is_file():
        pytest.fail("wizard/dist/ is not built: run make -C wizard test-browser, which builds it first")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def front_server():
    with FakeFrontServer(DIST) as server:
        yield server


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(10_000)            # a bound on each wait for an event, so a broken test fails soon
    try:
        yield page
    finally:
        context.close()


def main_module():
    """The built address of the page's entry module."""
    html = (DIST / "index.html").read_text(encoding="utf-8")
    return re.search(r'src="(/assets/main\.[0-9a-f]{12}\.js)"', html).group(1)


class Wizard:
    """The page with the wizard loaded at a width, its clock faked."""

    def __init__(self, page, server, width=320, height=720):
        self.page = page
        self.server = server
        self.problems = []
        page.on("console", lambda m: self.problems.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.problems.append(str(e)))
        page.add_init_script("Math.random = () => 0.5;")
        page.clock.install(time=START)
        page.set_viewport_size({"width": width, "height": height})
        page.goto(server.url)
        page.wait_for_selector('html[data-started="true"]', state="attached")
        page.clock.pause_at(START + datetime.timedelta(minutes=10))     # from here time moves only when a test moves it
        self.main = main_module()

    def until(self, condition, arg=None, tries=500):
        """Asks the page until `condition`, the body of a function of (wizard, arg), is true: each
        ask is a round trip to the page, an event, and no time is waited."""
        for _ in range(tries):
            if self.run(f"return Boolean((() => {{ {condition} }})());", arg):
                return
        raise AssertionError(f"the page never reached: {condition}")

    def run(self, body, arg=None):
        """Runs `body`, the text of an async function of (wizard, arg), against the running wizard."""
        return self.page.evaluate(
            f"async ([url, arg]) => {{ const {{ wizard }} = await import(url); return (async (wizard, arg) => {{ {body} }})(wizard, arg); }}",
            [self.main, arg])

    def set(self, patch):
        self.run("wizard.store.set(arg);", patch)

    def width(self, width, height=720):
        self.page.set_viewport_size({"width": width, "height": height})


@pytest.fixture
def wizard(page, front_server):
    def open_at(width=320, height=720):
        return Wizard(page, front_server, width, height)
    return open_at
