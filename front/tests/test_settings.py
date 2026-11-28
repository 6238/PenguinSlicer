"""The settings and their defaults (README-details.md, "Secrets and settings" and "Running
phase 2 on one machine")."""

from pathlib import Path

import pytest

from penguin_front import settings as settings_module
from penguin_front.__main__ import DEFAULT_HOST, DEFAULT_PORT, parse_args
from penguin_front.settings import Settings, SettingError
from penguin_front.version import version_at

REPOSITORY = Path(__file__).resolve().parents[2]
DEV = {"PENGUIN_DEV_IDENTITY": "1"}
KEY = "a-cookie-key-only-the-tests-use-7f3a"


def test_with_no_setting_given_the_front_server_uses_the_tables_defaults():
    s = Settings.from_environ(DEV)
    assert s.dev_identity is True
    assert s.slice_url == "http://127.0.0.1:8640"
    assert s.state_dir == Path("/var/tmp/penguin-front/state")
    assert s.log_dir == Path("/var/tmp/penguin-front/log")
    assert s.wizard_dist == REPOSITORY / "wizard" / "dist"
    assert s.version is None
    assert s.base_url == "http://127.0.0.1:8600"
    assert s.cookie_key is None
    assert s.groups_reread_s is None
    assert s.threads == 100
    assert s.stop_s is None


def test_with_no_argument_given_the_front_server_listens_on_8600_of_the_loopback_address():
    args = parse_args(["serve"])
    assert (args.host, args.port) == ("127.0.0.1", 8600) == (DEFAULT_HOST, DEFAULT_PORT)
    args = parse_args(["serve", "--host", "0.0.0.0", "--port", "20001"])
    assert (args.host, args.port) == ("0.0.0.0", 20001)


def test_each_setting_is_read():
    s = Settings.from_environ({
        "PENGUIN_DEV_IDENTITY": "", "PENGUIN_COOKIE_KEY": KEY,
        "PENGUIN_SLICE_URL": "http://slice.internal:8640/",
        "PENGUIN_STATE_DIR": "/srv/state", "PENGUIN_LOG_DIR": "/srv/log",
        "PENGUIN_WIZARD_DIST": "/srv/dist", "PENGUIN_VERSION": "20261127T221405Z-1a2b3c4",
        "PENGUIN_BASE_URL": "https://penguinslicer.popcornpenguins.com/",
        "PENGUIN_GROUPS_REREAD": "86400", "PENGUIN_FRONT_THREADS": "40",
        "PENGUIN_FRONT_STOP_S": "25"})
    assert s.dev_identity is False
    assert s.cookie_key == KEY
    assert s.slice_url == "http://slice.internal:8640"
    assert (s.state_dir, s.log_dir, s.wizard_dist) == (Path("/srv/state"), Path("/srv/log"),
                                                       Path("/srv/dist"))
    assert s.version == "20261127T221405Z-1a2b3c4"
    assert s.base_url == "https://penguinslicer.popcornpenguins.com"
    assert (s.groups_reread_s, s.threads, s.stop_s) == (86400, 40, 25)


def test_the_development_identity_is_off_when_unset_or_zero():
    for value in (None, "", "0"):
        env = {"PENGUIN_COOKIE_KEY": KEY}
        if value is not None:
            env["PENGUIN_DEV_IDENTITY"] = value
        assert Settings.from_environ(env).dev_identity is False


def test_groups_reread_never_is_none():
    assert Settings.from_environ(dict(DEV, PENGUIN_GROUPS_REREAD="never")).groups_reread_s is None


def test_a_missing_cookie_key_with_the_development_identity_off_stops_the_start():
    with pytest.raises(SettingError) as refused:
        Settings.from_environ({})
    assert "PENGUIN_COOKIE_KEY" in str(refused.value)
    with pytest.raises(SettingError, match="PENGUIN_COOKIE_KEY"):
        Settings.from_environ({"PENGUIN_COOKIE_KEY": ""})


@pytest.mark.parametrize("name, value", [
    ("PENGUIN_DEV_IDENTITY", "yes"),
    ("PENGUIN_SLICE_URL", "127.0.0.1:8640"),
    ("PENGUIN_SLICE_URL", "ftp://127.0.0.1"),
    ("PENGUIN_SLICE_URL", "http://"),
    ("PENGUIN_SLICE_URL", "http://127.0.0.1:8640/slices"),
    ("PENGUIN_SLICE_URL", "http://127.0.0.1:99999"),
    ("PENGUIN_SLICE_URL", "http://127.0.0.1:0"),
    ("PENGUIN_SLICE_URL", "http://127.0.0.1:port"),
    ("PENGUIN_BASE_URL", "https://user:password@penguinslicer.example"),
    ("PENGUIN_BASE_URL", "https://user@penguinslicer.example"),
    ("PENGUIN_VERSION", "20261327T221405Z-1a2b3c4"),
    ("PENGUIN_VERSION", "20261131T221405Z-1a2b3c4"),
    ("PENGUIN_VERSION", "20261127T251405Z-1a2b3c4"),
    ("PENGUIN_BASE_URL", "penguinslicer.popcornpenguins.com"),
    ("PENGUIN_STATE_DIR", "relative/state"),
    ("PENGUIN_LOG_DIR", "relative/log"),
    ("PENGUIN_WIZARD_DIST", "relative/dist"),
    ("PENGUIN_VERSION", "20261127-1a2b3c4"),
    ("PENGUIN_VERSION", "20261127T221405Z-1A2B3C4"),
    ("PENGUIN_VERSION", "20261127T221405Z-1a2b3c4 "),
    ("PENGUIN_GROUPS_REREAD", "daily"),
    ("PENGUIN_GROUPS_REREAD", "0"),
    ("PENGUIN_FRONT_THREADS", "0"),
    ("PENGUIN_FRONT_THREADS", "1001"),
    ("PENGUIN_FRONT_THREADS", "many"),
    ("PENGUIN_FRONT_STOP_S", "-1"),
    ("PENGUIN_FRONT_STOP_S", "1.5"),
])
def test_a_setting_of_the_wrong_form_stops_the_start_naming_it(name, value):
    with pytest.raises(SettingError) as refused:
        Settings.from_environ(dict(DEV, **{name: value}))
    assert str(refused.value).startswith(f"{name}: ")


def test_a_refused_secret_is_never_quoted():
    # The cookie key's only rule in this phase is that it is not empty, and its value is
    # never in a message or in the settings' printed form.
    s = Settings.from_environ({"PENGUIN_COOKIE_KEY": KEY})
    assert KEY not in repr(s) and KEY not in str(s)


def test_the_repository_default_for_the_wizards_files_is_the_checkouts_wizard_dist():
    assert settings_module.CHECKOUT == REPOSITORY


def test_a_version_from_a_checkout_is_the_start_moment_in_utc_then_seven_zeros():
    assert version_at(1_795_817_645.9) =="20261127T221405Z-0000000"
