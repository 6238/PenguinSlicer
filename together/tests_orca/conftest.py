"""The real-Orca walks' fixtures: the same two servers as the joined suite, the slice service
running the pinned real Orca, and for the browser walk the front server serving the wizard's
build and Chromium. Run only by `make -C together test-orca`, which holds the real-Orca lock for
the whole run."""

import pytest
from playwright.sync_api import sync_playwright

from joined.browser import WIZARD_DIST, Wizard
from joined.page import Page
from joined.paths import REAL_ORCA
from joined.servers import FrontServer, SliceService


@pytest.fixture
def slice_service(tmp_path):
    assert REAL_ORCA.is_file(), f"the pinned Orca is not installed at {REAL_ORCA}: make -C slice install-orca"
    service = SliceService(tmp_path / "slice", orca=REAL_ORCA)
    try:
        yield service.start()
    finally:
        service.close()


@pytest.fixture
def front_server(tmp_path, slice_service):
    front = FrontServer(tmp_path / "front", slice_service.url)
    try:
        yield front.start()
    finally:
        front.close()


@pytest.fixture
def page(front_server):
    page = Page(front_server).sign_in()
    try:
        yield page
    finally:
        page.close()


@pytest.fixture
def wizard(tmp_path, slice_service):
    """`wizard(width=…)`: a tab of the wizard served by a front server of its own, in Chromium."""
    assert (WIZARD_DIST / "index.html").is_file(), f"the wizard is not built at {WIZARD_DIST}: make -C wizard build"
    front = FrontServer(tmp_path / "wizard-front", slice_service.url, wizard_dist=WIZARD_DIST).start()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        try:
            yield lambda **size: Wizard(context, front, **size).open()
        finally:
            context.close()
            browser.close()
            front.close()
