"""The joined suite's fixtures: for each test, a slice service and a front server of its own,
started from their start commands on ports the system chooses, with fresh folders, and the
page that drives the front server. A test that needs a setting of the slice service's own
marks itself `@pytest.mark.slice_env(NAME="value")`.

The browser tests of a later batch take the same `slice_service` and `front_server` and drive
them through a browser in place of `page`.
"""

import pytest

from joined.page import Page
from joined.servers import FrontServer, SliceService


def pytest_configure(config):
    config.addinivalue_line("markers", "slice_env(**settings): settings of the slice service's own")


@pytest.fixture
def slice_service(tmp_path, request):
    marker = request.node.get_closest_marker("slice_env")
    service = SliceService(tmp_path / "slice", env=marker.kwargs if marker else None)
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
