"""The joined suite's fixtures: for each test, a slice service and a front server of its own,
started from their start commands on ports the system chooses, with fresh folders, and the
page that drives the front server over HTTP. A test that needs a setting of the slice
service's own marks itself `@pytest.mark.slice_env(NAME="value")`; one that compares a
download with what the stand-in Orca made marks itself `@pytest.mark.keep_sliced`.

The browser tests take the same `slice_service`, and `wizard_front`, a front server serving the
wizard's build (`make -C wizard build`, which `make -C together test` runs first), and drive it
through Chromium with `wizard` in place of `page`.
"""

import pytest
from playwright.sync_api import sync_playwright

from joined.browser import WIZARD_DIST, Wizard
from joined.page import Page
from joined.servers import FrontServer, SliceService


def pytest_configure(config):
    config.addinivalue_line("markers", "slice_env(**settings): settings of the slice service's own")
    config.addinivalue_line("markers", "keep_sliced: keep a copy of each sliced file the stand-in "
                                       "Orca writes (SliceService.sliced_files)")


@pytest.fixture
def slice_service(tmp_path, request):
    marker = request.node.get_closest_marker("slice_env")
    service = SliceService(tmp_path / "slice", env=marker.kwargs if marker else None,
                           keep_sliced=request.node.get_closest_marker("keep_sliced") is not None)
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


@pytest.fixture(scope="session")
def browser():
    if not (WIZARD_DIST / "index.html").is_file():
        pytest.fail(f"the wizard is not built at {WIZARD_DIST}: make -C wizard build "
                    "(make -C together test runs it first)")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def wizard_front(tmp_path, slice_service):
    """The front server serving the wizard's build, with the development identity."""
    front = FrontServer(tmp_path / "front", slice_service.url, wizard_dist=WIZARD_DIST)
    try:
        yield front.start()
    finally:
        front.close()


@pytest.fixture
def wizard(browser, wizard_front):
    """`wizard(width=…)`: a tab of a fresh browser profile with the wizard opened in it. A
    second call opens a second tab in the same profile."""
    context = browser.new_context(accept_downloads=True)
    tabs = []

    def open_tab(**size):
        tab = Wizard(context, wizard_front, **size).open()
        tabs.append(tab)
        return tab

    try:
        yield open_tab
    finally:
        context.close()
