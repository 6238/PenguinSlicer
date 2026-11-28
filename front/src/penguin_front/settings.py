"""The front server's settings, read once at start from its environment.

The names and the defaults on one machine are those of README-details.md, "Running phase 2
on one machine". A setting of the wrong form, or a secret the front server needs and lacks,
stops the start with a `SettingError` whose message names the setting and never quotes a
secret's value.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .version import is_version

#: The checkout the front server runs from: front/src/penguin_front/ is three folders down.
CHECKOUT = Path(__file__).resolve().parents[3]

DEFAULT_SLICE_URL = "http://127.0.0.1:8640"
DEFAULT_STATE_DIR = Path("/var/tmp/penguin-front/state")
DEFAULT_LOG_DIR = Path("/var/tmp/penguin-front/log")
DEFAULT_BASE_URL = "http://127.0.0.1:8600"
DEFAULT_THREADS = 100
#: The most threads the setting allows: ten times the design's figure, far past what one
#: process's memory is sized for, and a bound against a typing mistake.
MAX_THREADS = 1000


class SettingError(ValueError):
    """A setting the front server cannot start with. The message starts with its name."""

    def __init__(self, name, reason):
        super().__init__(f"{name}: {reason}")
        self.setting = name


@dataclass(frozen=True)
class Settings:
    dev_identity: bool
    slice_url: str
    state_dir: Path
    log_dir: Path
    wizard_dist: Path
    #: None: made from the start moment (version.version_at).
    version: str | None
    base_url: str
    #: None only with the development identity on: a key is then made at start.
    cookie_key: str | None = field(repr=False)
    #: None: never read the groups again on a schedule.
    groups_reread_s: int | None
    threads: int
    #: None: no bound of the front server's own on a stop.
    stop_s: int | None

    @classmethod
    def from_environ(cls, environ=None):
        env = os.environ if environ is None else environ
        dev_identity = _flag(env, "PENGUIN_DEV_IDENTITY")
        cookie_key = env.get("PENGUIN_COOKIE_KEY") or None
        if cookie_key is None and not dev_identity:
            raise SettingError("PENGUIN_COOKIE_KEY", "the cookie key is required unless the "
                                                     "development identity is on")
        version = env.get("PENGUIN_VERSION") or None
        if version is not None and not _real_version(version):
            raise SettingError("PENGUIN_VERSION", f"{version!r} is not of the form "
                                                  "YYYYMMDDTHHMMSSZ-<seven hex digits> "
                                                  "with a real date and time")
        return cls(
            dev_identity=dev_identity,
            slice_url=_address(env, "PENGUIN_SLICE_URL", DEFAULT_SLICE_URL),
            state_dir=_folder(env, "PENGUIN_STATE_DIR", DEFAULT_STATE_DIR),
            log_dir=_folder(env, "PENGUIN_LOG_DIR", DEFAULT_LOG_DIR),
            wizard_dist=_folder(env, "PENGUIN_WIZARD_DIST", CHECKOUT / "wizard" / "dist"),
            version=version,
            base_url=_address(env, "PENGUIN_BASE_URL", DEFAULT_BASE_URL),
            cookie_key=cookie_key,
            groups_reread_s=_seconds_or_never(env, "PENGUIN_GROUPS_REREAD"),
            threads=_whole(env, "PENGUIN_FRONT_THREADS", DEFAULT_THREADS, 1, MAX_THREADS),
            stop_s=_whole(env, "PENGUIN_FRONT_STOP_S", None, 1, None),
        )


def _flag(env, name):
    value = env.get(name, "")
    if value in ("", "0"):
        return False
    if value == "1":
        return True
    raise SettingError(name, f"{value!r} is neither 1 (on) nor unset (off)")


def _real_version(text):
    """The version's form, and its moment a real one (no month 13, no 25 o'clock)."""
    if not is_version(text):
        return False
    try:
        datetime.strptime(text[:16], "%Y%m%dT%H%M%SZ")
    except ValueError:
        return False
    return True


def _address(env, name, default):
    """An http or https address with no path and no user: a scheme, a host and perhaps a
    port from 1 to 65535."""
    value = env.get(name) or default
    parts = urlsplit(value)
    try:
        port = parts.port  # None when no port is given
    except ValueError:  # a port that is not a number, or past 65535
        port = 0
    if parts.scheme not in ("http", "https") or not parts.hostname \
            or parts.path not in ("", "/") or parts.query or parts.fragment \
            or "@" in parts.netloc or port == 0:
        raise SettingError(name, f"{value!r} is not an address such as {default}")
    return value.rstrip("/")


def _folder(env, name, default):
    value = env.get(name)
    if not value:
        return default
    path = Path(value)
    if not path.is_absolute():
        raise SettingError(name, f"{value!r} is not an absolute path")
    return path


def _whole(env, name, default, low, high):
    value = env.get(name)
    if not value:
        return default
    if not re.fullmatch(r"[0-9]{1,9}", value) or int(value) < low or (high is not None and int(value) > high):
        bound = f"from {low} to {high}" if high is not None else f"of at least {low}"
        raise SettingError(name, f"{value!r} is not a whole number {bound}")
    return int(value)


def _seconds_or_never(env, name):
    value = env.get(name, "never") or "never"
    if value == "never":
        return None
    return _whole({name: value}, name, None, 1, None)
