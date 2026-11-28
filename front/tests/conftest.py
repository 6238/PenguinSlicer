"""Guards every test of the fast suite is held to, and the fixtures most tests share.

- No network beyond loopback: a connection to, or a name lookup of, anything but the
  loopback address fails the test where it is made, naming the address. So no test can
  reach Onshape, R2 or anything else real, from the first test on.
- No sleeping: `time.sleep` fails the test. Time passes through the fake clock.
"""

import ipaddress
import socket
import time

import pytest

from front_fakes import FakeClock

_LOOPBACK_NAMES = {"localhost", "localhost.localdomain"}
_real_getaddrinfo = socket.getaddrinfo
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


class RealNetworkUsed(AssertionError):
    """A test reached for the network beyond the loopback address."""


def _is_loopback(host):
    if isinstance(host, bytes):
        host = host.decode()
    if host is None or host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def _check_address(address):
    if isinstance(address, tuple) and not _is_loopback(address[0]):
        raise RealNetworkUsed(f"a test connected to {address[0]!r}: the fast suite reaches "
                              "nothing beyond the loopback address")


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _is_loopback(host):
        raise RealNetworkUsed(f"a test looked up {host!r}: the fast suite reaches nothing "
                              "beyond the loopback address")
    return _real_getaddrinfo(host, *args, **kwargs)


def _guarded_connect(self, address):
    _check_address(address)
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    _check_address(address)
    return _real_connect_ex(self, address)


def _no_sleep(seconds):
    raise AssertionError(f"time.sleep({seconds!r}) was called: no test sleeps; move the "
                         "fake clock and wait on an event")


@pytest.fixture(autouse=True)
def _guards(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    monkeypatch.setattr(time, "sleep", _no_sleep)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def standin(clock):
    """The stand-in for the slice service on a port the system chooses, on the test's clock."""
    from slice_standin import SliceStandIn

    standin = SliceStandIn(clock)
    standin.start()
    yield standin
    standin.stop()
