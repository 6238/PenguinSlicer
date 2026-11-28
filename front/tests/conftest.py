"""Guards every test of the fast suite is held to, and the fixtures most tests share.

- No network beyond loopback: a connection to, or a name lookup of, anything but the
  loopback address fails the test where it is made, naming the address. So no test can
  reach Onshape, R2 or anything else real, from the first test on.
- No sleeping: `time.sleep` fails the test. Time passes through the fake clock.
- No secret written: a log line or an answer of the front server holding a secret the test
  used fails the test (tests/secret_watch.py).
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


@pytest.fixture(autouse=True)
def _no_secret_written(monkeypatch):
    """No log line and no answer of the front server holds a secret the test used
    (tests/secret_watch.py). Set up before every other fixture, so torn down after them:
    what an application writes as it is shut is watched too."""
    import json

    from flask import Flask, request

    import secret_watch
    from penguin_front.cookie import CookieKey
    from penguin_front.log import Log, line_text

    watch = secret_watch.Watch()
    secret_watch.current = watch
    real_init, real_seal = CookieKey.__init__, CookieKey.seal_bytes
    real_print, real_gather = Log._print, Log.gather
    real_process = Flask.process_response

    def init(self, secret):
        watch.secret(secret)
        real_init(self, secret)

    def seal(self, plain):
        value = real_seal(self, plain)
        watch.secret(value)
        return value

    def printed(self, text):
        watch.text("the log", text)
        real_print(self, text)

    def gathered(self, lines):
        lines = list(lines)
        for line in lines:
            watch.text("the log's gathered lines", line_text(line))
        real_gather(self, lines)

    def process(self, response):
        response = real_process(self, response)
        if self.name == "penguin_front":
            where = f"the answer to {request.method} {request.path}"
            watch.text(where, json.dumps([(k, v) for k, v in response.headers.items()
                                          if k.lower() != "set-cookie"]))
            if not response.is_streamed and not response.direct_passthrough:
                watch.text(where, response.get_data().decode("utf-8", "replace"))
        return response

    monkeypatch.setattr(CookieKey, "__init__", init)
    monkeypatch.setattr(CookieKey, "seal_bytes", seal)
    monkeypatch.setattr(Log, "_print", printed)
    monkeypatch.setattr(Log, "gather", gathered)
    monkeypatch.setattr(Flask, "process_response", process)
    yield watch
    secret_watch.current = secret_watch.Watch()
    leaks = watch.leaks()
    assert not leaks, f"a secret was written: {leaks[:5]}"


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
