"""The browser tests drive Playwright's Chromium, headless, against the built page in
wizard/dist/ (`make -C wizard test-browser` builds it first) served by the fake front server."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from tests_browser.fake_front_server import FakeFrontServer

DIST = Path(__file__).resolve().parent.parent / "dist"


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
    try:
        yield page
    finally:
        context.close()
