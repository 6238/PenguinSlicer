"""The real-Orca walk's fixtures: the same two servers as the joined suite, the slice service
running the pinned real Orca. Run only by `make -C together test-orca`, which holds the
real-Orca lock for the whole run."""

import pytest

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
