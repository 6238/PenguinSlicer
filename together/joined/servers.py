"""The two servers, each started from its start command
(front/README-details.md, "Running phase 2 on one machine") on a port the system chooses,
with fresh folders, and found listening by the line each writes when it listens.

- `SliceService`: `python -m penguin_slice serve --work <folder> --port 0`, its Orca named by
  `PENGUIN_SLICE_ORCA`. With the stand-in Orca, the wrapper the suite writes reads the
  stand-in's mode from a file at each slice, so a test chooses how the next slice goes
  (`orca_mode`) without starting the slice service again. A restart starts a new slice
  service process on the same port, since the front server was told one address.
- `FrontServer`: `python -m penguin_front serve --port 0` with the development identity, a
  cookie key given (so that a restart signs nobody out), the slice service's address, a
  state folder, a log folder and a folder of page files.
"""

import json
import os
import secrets
import signal
import stat
import sys
import threading
from pathlib import Path

import httpx

from .paths import FAKE_ORCA, FRONT_PYTHON, ROOT, SLICE_PYTHON
from .processes import Running
from .waits import BACKSTOP_S

LOOPBACK = "127.0.0.1"
#: The development identity's user key (front/README-details.md, "The development identity's
#: values"), which the front server sends the slice service on its behalf.
DEV_USER_KEY = "dev-user"
USER_KEY_HEADER = "X-Penguin-User-Key"


def _clean_environ(extra):
    """This process's environment without any PenguinSlicer setting of its own, then `extra`:
    each server sees only what the test gives it."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PENGUIN_")}
    env.update({k: str(v) for k, v in extra.items()})
    return env


def write_fake_orca(folder):
    """The wrapper `PENGUIN_SLICE_ORCA` names: it runs the slice service's stand-in Orca with
    Python in the mode the file `orca-mode` beside it holds at that moment. Gives (wrapper,
    mode file)."""
    folder.mkdir(parents=True, exist_ok=True)
    mode_file = folder / "orca-mode"
    mode_file.write_text("ok\n")
    wrapper = folder / "fake-orca"
    wrapper.write_text("#!/bin/sh\n"
                       f'mode=$(cat "{mode_file}")\n'
                       f'exec "{sys.executable}" -I -S "{FAKE_ORCA}" --mode "$mode" "$@"\n')
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return wrapper, mode_file


class SliceService:
    def __init__(self, folder, *, orca=None, env=None):
        """`orca`: the Orca to run (the stand-in, written here, when None); `env`: settings
        of the slice service's own."""
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.work = self.folder / "work"
        self.mode_file = None
        if orca is None:
            orca, self.mode_file = write_fake_orca(self.folder / "orca")
        self.orca = orca
        self.env = dict(env or {})
        self.port = 0
        self.running = None
        self.previous = []
        self.starts = 0

    @property
    def url(self):
        return f"http://{LOOPBACK}:{self.port}"

    def orca_mode(self, mode):
        """How the stand-in Orca slices from the next slice on (slice/tests/fake_orca.py)."""
        self.mode_file.write_text(mode + "\n")

    def release_orca(self):
        """Let the one stand-in Orca held in mode `gate` go on and slice: one byte into the
        FIFO it made in its output folder before its first progress message. Opening the FIFO
        waits until that Orca opens it to read, which is the event; the backstop fails the
        test should it never."""
        gates = list(self.work.rglob("fake-orca.gate"))
        assert len(gates) == 1, f"one Orca held at its gate, not {gates}"
        opened = threading.Event()

        def write():
            with open(gates[0], "wb") as fh:
                opened.set()
                fh.write(b"g")
        writer = threading.Thread(target=write, daemon=True, name="orca-gate")
        writer.start()
        writer.join(BACKSTOP_S)
        assert opened.is_set(), f"no Orca read {gates[0]} within the backstop"

    def start(self):
        """Start a slice service process and wait until it listens: on a port the system
        chooses the first time, on the same one after."""
        self.starts += 1
        argv = [SLICE_PYTHON, "-m", "penguin_slice", "serve", "--work", self.work,
                "--host", LOOPBACK, "--port", self.port]
        self.running = Running(f"slice-{self.starts}", argv, cwd=ROOT,
                               env=_clean_environ({"PENGUIN_SLICE_ORCA": self.orca, **self.env}),
                               log_path=self.folder / "slice.log")
        started = self.running.wait_for_event("slice_service_started")
        self.port = started["port"]
        return self

    def stop(self):
        """Ask it to stop once, as a deploy does (SIGTERM); it finishes its running slice and
        waits for the front server to collect the sliced file before it exits."""
        self.running.signal(signal.SIGTERM)

    def wait_stopped(self):
        code = self.running.wait_for_exit()
        self._retire()
        return code

    def crash(self):
        """End it and its Orca at once, as a container that dies does."""
        self.running.kill()
        self._retire()

    def restart(self):
        """After `wait_stopped` or `crash`: a new process on the same port."""
        return self.start()

    def _retire(self):
        self.previous.append(self.running)

    def request(self, method, path, *, user_key=DEV_USER_KEY, **kwargs):
        """One request to the slice service's HTTP interface directly, as the front server
        makes it: for a test to compare what the page was given with the slice service's own
        answer."""
        headers = {USER_KEY_HEADER: user_key} if user_key else {}
        with httpx.Client(base_url=self.url, trust_env=False, timeout=BACKSTOP_S) as client:
            return client.request(method, path, headers={**headers, **kwargs.pop("headers", {})},
                                  **kwargs)

    def lines(self, event=None):
        """The JSON lines of every slice service process so far, oldest first."""
        found = []
        for running in _each(self.previous, self.running):
            found.extend(running.events(event))
        return found

    def close(self):
        for running in _each(self.previous, self.running):
            running.close()


def _each(previous, current):
    """Each process once, oldest first."""
    seen = []
    for running in [*previous, current]:
        if running is not None and all(running is not other for other in seen):
            seen.append(running)
    return seen


def page_files(folder):
    """A folder of page files the front server can serve, until the wizard's build is used
    here: `index.html` with the version's placeholder, and no assets."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>PenguinSlicer</title>'
        '<meta name="penguinslicer-version" content="__PENGUINSLICER_VERSION__">\n')
    return folder


class FrontServer:
    def __init__(self, folder, slice_url, *, wizard_dist=None, env=None):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.state = self.folder / "state"
        self.log_dir = self.folder / "log"
        self.wizard_dist = wizard_dist or page_files(self.folder / "pages")
        self.slice_url = slice_url
        self.cookie_key = secrets.token_urlsafe(32)
        self.env = dict(env or {})
        self.port = 0
        self.running = None
        self.previous = []
        self.starts = 0
        self.version = None

    @property
    def url(self):
        return f"http://{LOOPBACK}:{self.port}"

    def start(self):
        """Start a front server and wait until it listens; on the same port after the first."""
        self.starts += 1
        argv = [FRONT_PYTHON, "-m", "penguin_front", "serve", "--host", LOOPBACK,
                "--port", self.port]
        env = _clean_environ({
            "PENGUIN_DEV_IDENTITY": "1", "PENGUIN_SLICE_URL": self.slice_url,
            "PENGUIN_STATE_DIR": self.state, "PENGUIN_LOG_DIR": self.log_dir,
            "PENGUIN_WIZARD_DIST": self.wizard_dist, "PENGUIN_COOKIE_KEY": self.cookie_key,
            **self.env})
        self.running = Running(f"front-{self.starts}", argv, cwd=ROOT, env=env,
                               log_path=self.folder / "front.log")
        started = self.running.wait_for_event("start")
        self.port = started["port"]
        self.version = started["version"]
        return self

    def stop(self):
        """Stop it as a deploy does (SIGTERM) and wait until it has exited, its log written.
        A stop is clean or the test fails: exit status 0 and the stop line written."""
        self.running.signal(signal.SIGTERM)
        code = self.running.wait_for_exit()
        self.previous.append(self.running)
        assert code == 0, f"the front server's stop ended with exit status {code}"
        assert self.running.events("stop"), "the front server's stop wrote no stop line"
        return code

    def restart(self):
        return self.start()

    def gathered(self):
        """Every line in the log folder's files, in the order of their `time`: two files of
        the same second are named in no order of writing."""
        lines = []
        for path in self.log_dir.rglob("*.jsonl"):
            lines.extend(json.loads(text) for text in path.read_text().splitlines() if text)
        return sorted(lines, key=lambda line: line.get("time", ""))

    def close(self):
        for running in _each(self.previous, self.running):
            running.close()
