import pytest

from penguin_delivery_relay import relay_of
from penguin_delivery_relay import relay as relay_module

from relay_fakes import CODE, SECRET, FakeClock, Caller, make_app


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def caller():
    return Caller()


@pytest.fixture
def app(caller, clock, tmp_path):
    return make_app(caller, clock, spool_dir=str(tmp_path / 'spool'))


@pytest.fixture
def relay(app):
    return relay_of(app).relay


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth():
    def headers(code=CODE, key=SECRET):
        return {'Authorization': f'Bearer {relay_module.issue_token(code, key)}'}
    return headers


@pytest.fixture
def https():
    """Keyword arguments that make a test-client request arrive over HTTPS."""
    return {'base_url': 'https://relay.test'}
