"""Helpers the tests of the front server's requests share: a log that keeps its lines, a
wizard's built folder made by the test, and the application built on fresh folders.

Nothing here reads the real clock or sleeps."""

import socket
from pathlib import Path

from penguin_front.app import create_app
from penguin_front.settings import Settings

VERSION = "20261127T221405Z-1a2b3c4"
#: A cookie key only the tests use; never a real one.
KEY = "a-cookie-key-only-the-tests-use-7f3a"
#: The placeholder the wizard's build leaves in its page (contracts/wizard-front-server.md,
#: "The wizard's built files").
PLACEHOLDER = '<meta name="penguinslicer-version" content="__PENGUINSLICER_VERSION__">'
#: The assets of the built folder the tests make, by name, with their bytes.
ASSETS = {
    "panel.3f9a1c2b7e04.js": b"console.log('the wizard');\n",
    "panel.0a1b2c3d4e5f.css": b"body { margin: 0; }\n",
    "plex-sans.9f8e7d6c5b4a.woff2": bytes(range(256)),
}


class Lines:
    """A stand-in for the log: every line written, in order."""

    def __init__(self):
        self.lines = []

    def write(self, event, **fields):
        self.lines.append({"event": event, **fields})

    def events(self, event):
        return [line for line in self.lines if line["event"] == event]


def make_dist(folder, *, index=True, placeholder=True):
    """A wizard's built folder of the contract's layout: `index.html` naming its assets under
    `/assets/`, and `assets/` holding them, flat."""
    folder = Path(folder)
    (folder / "assets").mkdir(parents=True, exist_ok=True)
    for name, data in ASSETS.items():
        (folder / "assets" / name).write_bytes(data)
    if index:
        meta = PLACEHOLDER if placeholder else '<meta name="penguinslicer-version" content="">'
        (folder / "index.html").write_text(
            "<!doctype html>\n<html><head>" + meta +
            '<link rel="stylesheet" href="/assets/panel.0a1b2c3d4e5f.css">'
            '<script type="module" src="/assets/panel.3f9a1c2b7e04.js"></script>'
            "</head><body></body></html>\n")
    return folder


def nobody_listens():
    """An address on the loopback where nothing listens: a port the system chose and gave
    back, so no test reaches a slice service another program runs on its default port."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{probe.getsockname()[1]}"


def environ(tmp_path, **extra):
    """The settings of a front server on fresh folders under `tmp_path`, with the development
    identity on and a fixed cookie key; a value of None in `extra` removes that setting."""
    dist = tmp_path / "dist"
    if not dist.exists():
        make_dist(dist)
    settings = {"PENGUIN_DEV_IDENTITY": "1", "PENGUIN_COOKIE_KEY": KEY,
                "PENGUIN_STATE_DIR": str(tmp_path / "state"),
                "PENGUIN_LOG_DIR": str(tmp_path / "log"),
                "PENGUIN_WIZARD_DIST": str(dist), "PENGUIN_SLICE_URL": nobody_listens()}
    settings.update(extra)
    return {name: value for name, value in settings.items() if value is not None}


def front(tmp_path, clock, log=None, *, version=VERSION, **extra):
    """The front server's application on fresh folders; `extra` as for `environ`."""
    return create_app(Settings.from_environ(environ(tmp_path, **extra)), clock=clock,
                      log=log if log is not None else Lines(), version=version)


def sign_in(client):
    """Sign the development identity in through `/signin`, as the page's trip does."""
    answer = client.get("/signin")
    assert answer.status_code == 302, answer.get_data(as_text=True)
    return answer
